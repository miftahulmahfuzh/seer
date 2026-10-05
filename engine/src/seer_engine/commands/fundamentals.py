"""fundamentals -- resumable ingest of SEC EDGAR XBRL company facts (Gap B).

One ``data.sec.gov`` ``companyfacts`` call per CIK, resolved from the vendored dated
ticker->CIK map, for every S&P 500 / Nasdaq-100 ever-member since 2009-01-01. Symbols are
processed in batches and **each batch is written in its own transaction together with its
``fundamentals_log`` rows**, so a crash loses at most one batch and a re-run resumes where
it stopped -- the shape ``backfill`` uses.

The unit of work is the CIK, not the symbol. One CIK backs several tickers (GOOG/GOOGL,
CMCSA/CMCSK, BATRA/BATRK), so symbol-keyed work would fetch the same JSON twice and
double-count its rows; and one ticker maps to several CIKs over time, so a symbol-keyed log
row would carry two companies' outcomes. ``plan_jobs`` resolves every in-scope symbol, groups
by CIK and skips the CIKs already logged; ``CikResult.per_symbol`` fans the outcome back out
so the summary and the exit code stay per symbol.

Resuming is keyed on the log, so **widening a floor is not something a flag can express**:
``--retry-failed`` re-attempts ``failed`` and ``empty`` filers only, and a filer logged ``ok``
under a narrower ``--since-filed`` is skipped with its older facts still missing. The supported
way to re-fetch everything is ``--symbols`` with the whole member set: ``plan_jobs`` ignores the
log outright when it is given, so every resolved CIK is fetched without a row being deleted
anywhere. The facts upsert is idempotent, so a filer whose facts are unchanged still writes zero
rows, and re-running is always safe. Do NOT empty ``fundamentals_log`` to achieve this: it
destroys the resume ledger for a result ``--symbols`` reaches without destroying anything.

No dependency on ``bars``. 133 of the ever-members have no price history at all and they are
precisely the names this pipeline exists to cover, so nothing here reads ``bars``, joins
against it, or treats a missing bar as an error.

Point in time: every fact is stored with its ``filed`` date and its accession number, and
``accn`` is part of the row identity, so a restatement inserts a second row rather than
overwriting the figure it restates. ``period_end`` is never an availability date. Nothing
here derives anything: the concept ladder and the ``filed <= t`` selection are pure code in
``seer_engine.fundamentals``.

Storage. ``companyfacts`` for a large filer holds tens of thousands of facts across hundreds
of tags, so the ingest keeps only the taxonomy/tag pairs in ``ladder.LADDER_TAGS`` (phase 5
owns the list) and only facts with ``filed >= --since-filed``. Narrowing either is a deliberate
decision that costs a re-ingest, which is why both are visible constants and the summary prints
``pg_total_relation_size('fundamental_facts')``.

**These facts do not live on Neon.** Every write goes to the database ``.env.local-train``
names, because the only database read in the whole train/eval pipeline is ``fundamental_facts``
x ``ticker_cik`` and pointing that one read at a local Postgres takes Neon out of train/eval
entirely. Neon's ``fundamental_facts`` and ``fundamentals_log`` are deliberately truncated, so
the 0.5 GB free tier no longer bounds the filed floor; the only remaining bound on
``--since-filed`` is when XBRL began, and that is 2009.

Fair access is the SEC client's job, not this module's: ``sec.Client`` paces itself to
<= 10 req/s from the end of the previous call and sends the contact ``User-Agent``. This
command therefore adds no inter-batch sleep.

Idempotent: every write is an upsert guarded by ``IS DISTINCT FROM``; re-running with the
same arguments changes no ``fundamental_facts`` rows.
"""

from __future__ import annotations

import argparse
import logging
import math
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol

import psycopg

from seer_engine import cik, config, db, membership, sec, universe
from seer_engine.fundamentals.ladder import LADDER_TAGS
from seer_engine.sec import CompanyFacts, Fact

log = logging.getLogger(__name__)

HELP = "Load SEC EDGAR XBRL company facts for every index ever-member; resumable."

DEFAULT_SINCE = date(2009, 1, 1)
# 2009-01-01 at both ends, and it is the earliest floor worth having: XBRL did not exist
# before roughly FY2009, so there is nothing earlier to fetch at any price or from any vendor.
#
# THE TWO FLOORS MOVE TOGETHER, ALWAYS. `--since` picks WHICH members are ingested
# (_WINDOWS_SQL over the `universe` table) and bounds the window resolve_window_ciks resolves
# CIKs over; `--since-filed` picks WHICH of a fetched filer's facts are kept. A member admitted
# from 2009 whose facts are dropped below 2013 buys nothing, and a fact kept from 2009 for a
# member only admitted from 2015 is never fetched at all, because the member is out of scope.
# `options_from_args` enforces since_filed <= since, which 2009-01-01 <= 2009-01-01 satisfies.
#
# Lowering the filed floor costs no extra request: `companyfacts` returns a filer's whole
# history in one response whatever the floor, so the earlier 2013 cutoff was discarding rows
# that had already been downloaded. What it buys is the panel. The panel's load joins
# `fundamental_facts` to `ticker_cik` ON `filed >= start_date AND filed < end_date`
# (backtest/io.py:93-98), so a fact filed before the map's start_date for that symbol never
# reaches the panel at all -- which is why the filed floor and the vendored map's floor have
# to agree, and why 181,491 facts filed in 2013-2014 were stored and invisible.
#
# Coverage in 2009-2010 is partial and size-biased: XBRL phased in by filer size, large
# accelerated filers from roughly FY2009 and all filers by FY2011. Do not assume those years
# are as thick as 2013 onwards; the measured per-year counts are in
# docs/plans/2026-10-05-fundamental-panel-coverage.md section 3.
DEFAULT_SINCE_FILED = date(2009, 1, 1)
DEFAULT_BATCH_SIZE = 20
ERROR_MAX_LEN = 500

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_FAILED = "failed"

# The (taxonomy, tag) pairs stored are EXACTLY seer_engine.fundamentals.ladder.LADDER_TAGS --
# every rung of every concept the derivation reads, and nothing else. This command owns no
# list of its own, deliberately: if the ingest's allowlist and the ladder's rungs could drift,
# the ladder would silently read a tag nobody stored and a concept would go dark with no error.
# ladder.py is pure (no psycopg, no requests, no clock), so importing it here is the legal
# direction under invariant 5; the reverse would not be.
#
# Measured coverage over 8 dead filers lives in
# docs/plans/2026-10-05-delisted-and-fundamentals.md section 3.2: revenue, net income, assets,
# equity, operating cash flow, diluted EPS and shares outstanding are 8/8; operating income is
# 6/8 (SIVB, PXD missing); gross profit is only 2/8, which is why the cost-of-revenue rungs are
# in the ladder at all -- phase 5 derives Revenues - CostOfRevenue from them.
#
# ADDING A TAG COSTS A FULL RE-INGEST. It is added to ladder.py, never here.


class FundamentalsError(Exception):
    """A user-facing reason the ingest cannot start or continue (exit code 2)."""


class FactsSource(Protocol):
    """Anything returning parsed XBRL facts for a CIK. ``sec.Client`` satisfies it."""

    def company_facts(
        self, cik: str | int, *, tags: Collection[str] | None = None
    ) -> CompanyFacts: ...


@dataclass(frozen=True)
class Options:
    today: date
    since: date = DEFAULT_SINCE
    since_filed: date = DEFAULT_SINCE_FILED
    symbols: tuple[str, ...] | None = None
    retry_failed: bool = False
    batch_size: int = DEFAULT_BATCH_SIZE
    sync_map: bool = True
    dry_run: bool = False


@dataclass(frozen=True)
class CikJob:
    """One ``companyfacts`` fetch: a CIK and every in-scope symbol it backs.

    ``symbols`` is sorted and never empty. It holds more than one entry exactly when a share
    class pair is in scope (GOOG/GOOGL, CMCSA/CMCSK, BATRA/BATRK) -- the case C2 exists for.
    """

    cik: str  # 10-digit zero-padded
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class CikResult:
    """What one fetch produced. **This is what the log row is written from** (one per CIK)."""

    cik: str
    symbols: tuple[str, ...]
    status: str
    facts: tuple[Fact, ...] = ()
    error: str | None = None

    def per_symbol(self) -> tuple[SymbolResult, ...]:
        """The fan-out: the same outcome reported once for each symbol the CIK backs.

        The ONE place a CIK-keyed result becomes symbol-keyed output. The facts are **not**
        copied into the per-symbol records -- they belong to the CIK and counting them per
        symbol would double-count a share-class pair -- so ``SymbolResult.facts`` is left
        empty here and ``Summary.facts_fetched`` is accumulated from the ``CikResult``.
        """
        return tuple(
            SymbolResult(s, self.status, cik=self.cik, error=self.error) for s in self.symbols
        )


@dataclass(frozen=True)
class SymbolResult:
    """One line of the human summary. Not a unit of work and not a log row (C2)."""

    symbol: str
    status: str
    cik: str | None = None
    error: str | None = None


@dataclass
class Summary:
    ok: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: int = 0            # SYMBOLS whose CIK was already logged
    ciks_fetched: int = 0       # companyfacts calls actually made; <= len(ok) + len(empty)
    facts_fetched: int = 0      # accumulated per CIK, never per symbol (no double counting)
    facts_written: int = 0
    map_rows: int = 0
    map_changed: bool = False
    facts_bytes: int | None = None

    def exit_code(self) -> int:
        """1 when any symbol failed, else 0. ``empty`` is deliberately not an error: a
        filer with no facts in the ingest tag set is a fact about the filer, not a fault."""
        return 1 if self.failed else 0


# ------------------------------------------------------------------ CLI surface


def _iso_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a YYYY-MM-DD date: {text!r}") from exc


def _symbol_list(text: str) -> list[str]:
    try:
        items = [membership.normalize_ticker(part) for part in text.split(",") if part.strip()]
    except membership.MembershipError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not items:
        raise argparse.ArgumentTypeError("--symbols needs at least one symbol")
    return list(dict.fromkeys(items))


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--since",
        type=_iso_date,
        default=DEFAULT_SINCE,
        help=(
            "ingest every member on or after this date; this selects the MEMBER SET, not the "
            f"facts (default {DEFAULT_SINCE.isoformat()}; must be >= --since-filed)"
        ),
    )
    p.add_argument(
        "--since-filed",
        type=_iso_date,
        default=DEFAULT_SINCE_FILED,
        help=(
            "drop facts filed before this date; this selects the FACTS of a fetched filer "
            f"(default {DEFAULT_SINCE_FILED.isoformat()}, which is where XBRL begins -- there "
            "is nothing earlier to widen to; narrowing it costs a re-ingest to undo)"
        ),
    )
    p.add_argument(
        "--symbols",
        type=_symbol_list,
        default=None,
        help="comma list (e.g. ATVI,BRK.B) instead of the universe; ignores fundamentals_log",
    )
    p.add_argument(
        "--retry-failed",
        action="store_true",
        help=(
            "also re-attempt symbols logged as failed or empty; a filer logged ok is still "
            "skipped, so widening --since-filed needs --symbols, which ignores the log"
        ),
    )
    p.add_argument(
        "--batch-size",
        type=_positive_int,
        default=DEFAULT_BATCH_SIZE,
        help=f"CIKs per write transaction (default {DEFAULT_BATCH_SIZE})",
    )
    p.add_argument(
        "--no-sync-map",
        action="store_true",
        help="do not mirror engine/data/ticker_cik.csv into the ticker_cik table",
    )


def options_from_args(args: argparse.Namespace, now: datetime | None = None) -> Options:
    today = (now if now is not None else datetime.now(timezone.utc)).date()
    if args.since > today:
        raise FundamentalsError(f"--since {args.since} is in the future (today is {today})")
    if args.since_filed > args.since:
        raise FundamentalsError(
            f"--since-filed {args.since_filed} is after --since {args.since}: a fact has to be "
            "filed before the window opens to be usable on its first date"
        )
    return Options(
        today=today,
        since=args.since,
        since_filed=args.since_filed,
        symbols=tuple(args.symbols) if args.symbols else None,
        retry_failed=bool(args.retry_failed),
        batch_size=int(args.batch_size),
        sync_map=not bool(args.no_sync_map),
        dry_run=bool(args.dry_run),
    )


def run(args: argparse.Namespace) -> int:
    try:
        opts = options_from_args(args)
    except FundamentalsError as exc:
        log.error("fundamentals: %s", exc)
        return 2
    # Read the contact address before opening a connection, so a missing setting reports the
    # setting rather than a database error. `sec.require_contact` is phase 3's named accessor
    # (C4); the ConfigError is caught here for the same reason nightly.py:76-80 catches its
    # own -- a setup problem is exit 2, not a failed run -- and cli.main would give 2 anyway.
    try:
        contact = sec.require_contact()
    except config.ConfigError as exc:
        log.error("%s", exc)
        return 2
    client = sec.Client(contact)
    conn = db.connect()
    try:
        summary = ingest(conn, opts, source=client)
    except FundamentalsError as exc:
        log.error("fundamentals: %s", exc)
        return 2
    finally:
        conn.close()
    print(format_summary(summary, opts))
    return summary.exit_code()


# ------------------------------------------------------- the CIK map (phase-1 seam)


def load_cik_map(path: Path | None = None) -> Sequence[cik.CikRow]:
    """Phase 1's vendored, validated ticker->CIK map (C5).

    The only call into ``seer_engine.cik``. Rows expose ``symbol``, ``cik`` (a 10-digit
    zero-padded string, or ``cik.NO_FILER`` == "NONE" for a symbol with no EDGAR filer at all),
    ``start_date``, ``end_date`` (exclusive; None = still held), ``company_name``, ``source``
    and ``note``. If ``cik.py``'s loader is named or shaped differently, this function is the
    one place to change.
    """
    return cik.load_ticker_cik((cik.DATA_DIR / cik.TICKER_CIK_FILE) if path is None else path)


def resolve_cik(mappings: Iterable[cik.CikRow], symbol: str, on: date) -> cik.CikRow | None:
    """The mapping row that held ``symbol`` on ``on``, or None.

    A match needs ``start_date <= on`` and ``on < end_date`` (or an open interval). Keyed on
    (symbol, date) and never on the bare ticker, so CA on 2015-01-02 is CA Inc. and not the
    Xtrackers ETF that holds the ticker today. Phase 1's loader rejects overlapping intervals
    for one symbol, so at most one row can match. A row whose ``cik`` is ``cik.NO_FILER`` is
    returned, not skipped -- "this symbol has no filer" is an answer, and ``resolve_window_ciks``
    turns it into ``empty`` rather than ``failed``.
    """
    for mapping in mappings:
        if mapping.symbol != symbol:
            continue
        if mapping.start_date <= on and (mapping.end_date is None or on < mapping.end_date):
            return mapping
    return None


def resolve_window_ciks(
    mappings: Iterable[cik.CikRow], symbol: str, first_day: date, last_day: date
) -> tuple[tuple[str, ...], str, str | None]:
    """``(ciks, status, error)`` for ``symbol`` across its whole membership window.

    Returns one of three outcomes:

    * ``(ciks, STATUS_OK, None)``    -- every filer that backed the ticker while it was a
      member, oldest first. Usually one; **two when the registrant was reorganised
      mid-membership** (GOOG/GOOGL across the 2015-10-02 Alphabet holdco reorg, WRK across
      WestRock's 2018 reorg). Each is fetched separately, so nothing is mixed: facts are
      CIK-keyed and phase 6's panel joins ``ticker_cik`` **by date**, which is what picks the
      right filer's facts for any given ``t``.
    * ``(.., STATUS_EMPTY, note)``   -- the map says this symbol has **no EDGAR filer**
      (a ``NONE`` row, parsed to ``cik is None``). Not an error: ``Summary.exit_code`` treats
      ``empty`` as success, exactly as ``backfill`` does for a symbol with no bars.
    * ``(.., STATUS_FAILED, why)``   -- the map cannot answer: no row covering the window.

    This delegates to ``cik.filers``, whose own docstring names it "the ingest entry point:
    Phase 4 fetches ``companyfacts`` once per CIK returned here". It replaces an earlier
    two-endpoint probe that refused whenever the two ends disagreed. That probe could only
    ever fire on a legitimate reorg, never on a recycled ticker: ``engine/data/ticker_cik.csv``
    defends against recycling in the **data**, by truncating a recycled ticker's interval at
    the handover (CA ends 2018-11-06 and the Xtrackers row is simply absent; likewise MON,
    PLL, ALTR, LLL, DTV). So the probe cost GOOG, GOOGL and WRK their fundamentals and bought
    nothing -- see ``test_a_reorganised_registrant_yields_both_filers``.
    """
    rows = list(mappings)
    index = cik.build_index(rows)
    # `filers` treats `end` as exclusive; the window's last day is inclusive.
    numbers = cik.filers(symbol, index, first_day, last_day + timedelta(days=1))
    if numbers:
        return numbers, STATUS_OK, None

    # No usable filer. Distinguish "the map answered NONE" from "the map has no row".
    covering = [
        r for r in index.get(symbol, ())
        if r.start_date <= last_day and (r.end_date is None or first_day < r.end_date)
    ]
    none_row = next((r for r in covering if r.cik is None), None)
    if none_row is not None:
        return (), STATUS_EMPTY, (
            f"{symbol} has no EDGAR filer in engine/data/ticker_cik.csv: {none_row.note}"
        )
    return (), STATUS_FAILED, (
        f"no CIK for {symbol} over {first_day.isoformat()}..{last_day.isoformat()}: add a "
        f"dated row to engine/data/ticker_cik.csv (a ticker alone never identifies a company)"
    )


# ------------------------------------------- membership windows and job selection


# Same scope predicate as universe.all_symbols (universe.py:41-48), plus the window each
# symbol was a member for, so the CIK can be resolved by date. `end_date` is exclusive, so
# the last day of membership is `end_date - 1`. The window start is clamped to `since`
# because the universe runs back to 1996 while ticker_cik.csv covers the backtest era.
_WINDOWS_SQL = """
SELECT symbol,
       greatest(min(start_date), %(since)s)                     AS first_day,
       least(max(coalesce(end_date - 1, %(today)s)), %(today)s) AS last_day
FROM universe
WHERE end_date IS NULL OR end_date > %(since)s
GROUP BY symbol
ORDER BY symbol
"""


def membership_windows(
    conn: psycopg.Connection, since: date, today: date
) -> dict[str, tuple[date, date]]:
    """symbol -> (first day, last day) of index membership, for every ever-member since
    ``since``. The benchmark is excluded: SPY is an ETF trust and files no us-gaap XBRL."""
    rows = conn.execute(_WINDOWS_SQL, {"since": since, "today": today}).fetchall()
    out: dict[str, tuple[date, date]] = {}
    for symbol, first_day, last_day in rows:
        if symbol == universe.BENCHMARK:
            continue
        out[symbol] = (first_day, max(first_day, last_day))
    return out


def select_symbols(opts: Options, windows: dict[str, tuple[date, date]]) -> list[str]:
    """The in-scope symbols, before any CIK resolution.

    ``--symbols`` replaces the universe outright. Note what that means once the log is keyed by
    CIK: naming ``GOOG`` alone still fetches CIK 1652044 once and writes one log row, and the
    summary reports ``GOOG`` only, because ``GOOGL`` is not in the run. Naming both reports
    both from the one fetch.
    """
    if opts.symbols:
        return list(opts.symbols)
    candidates = sorted(windows)
    if not candidates:
        raise FundamentalsError(
            f"the universe table holds no member on or after {opts.since.isoformat()}; "
            "run `python -m seer_engine universe refresh` first"
        )
    return candidates


def plan_jobs(
    conn: psycopg.Connection,
    opts: Options,
    symbols: Sequence[str],
    windows: dict[str, tuple[date, date]],
    mappings: Sequence[cik.CikRow],
) -> tuple[list[CikJob], list[SymbolResult], int]:
    """``(jobs, unresolved, skipped)`` -- the heart of the CIK-keyed resume rule (C2).

    Resolution happens **before** the log is consulted, because the log's key is the CIK and a
    symbol does not have one until the dated map is asked. The three returns are:

    * ``jobs``       -- one per distinct CIK still to fetch, carrying every in-scope symbol it
      backs, sorted by (first symbol, cik) so batching is deterministic.
    * ``unresolved`` -- the symbols the map could not turn into a CIK: ``failed`` (no row, or
      two filers across the window) and ``empty`` (the map says ``NONE``). **These never get a
      ``fundamentals_log`` row** -- the table's primary key is a bigint CIK and there is none --
      so they are re-evaluated on every run, which is right: nothing was fetched and nothing
      stored. A ``failed`` one therefore keeps failing until ``ticker_cik.csv`` is re-vendored;
      a ``NONE`` one keeps reporting ``empty``, which is not an error.
    * ``skipped``    -- how many **symbols** were skipped because their CIK is already logged.
      Counted per symbol, not per CIK, because the summary line is per symbol.

    A share-class pair collapses here: ``GOOG`` and ``GOOGL`` resolve to the same CIK, so they
    produce ONE job with ``symbols == ("GOOG", "GOOGL")``, one ``company_facts`` call and one
    log row.
    """
    by_cik: dict[str, list[str]] = {}
    unresolved: list[SymbolResult] = []
    for symbol in symbols:
        window = windows.get(symbol, (opts.since, opts.today))
        numbers, status, why = resolve_window_ciks(mappings, symbol, *window)
        if not numbers:
            if status == STATUS_FAILED:
                log.warning("fundamentals: %s unresolved: %s", symbol, why)
            unresolved.append(
                SymbolResult(symbol, status, error=_error_text(str(why)) if why else None)
            )
            continue
        # Usually one CIK; two when the registrant was reorganised mid-membership. The
        # symbol is attached to each, so both filers' facts are fetched and the summary
        # still reports the symbol once per outcome.
        for number in numbers:
            by_cik.setdefault(number, []).append(symbol)

    # `--symbols` ignores the log outright -- that is what its help text promises and what
    # makes it the tool for re-fetching one filer after a fix. Everything else resumes.
    logged = {} if opts.symbols else _logged_statuses(conn, sorted(by_cik))
    done = {STATUS_OK} if opts.retry_failed else {STATUS_OK, STATUS_EMPTY, STATUS_FAILED}
    jobs: list[CikJob] = []
    skipped = 0
    for number, group in by_cik.items():
        if logged.get(number) in done:
            skipped += len(group)
            continue
        jobs.append(CikJob(cik=number, symbols=tuple(sorted(group))))
    jobs.sort(key=lambda j: (j.symbols[0], j.cik))
    return jobs, unresolved, skipped


def _logged_statuses(conn: psycopg.Connection, ciks: Sequence[str]) -> dict[str, str]:
    """CIK -> status, for the CIKs about to be fetched. Keyed by ``cik`` (C2): there is no
    ``symbol`` column in ``fundamentals_log``. The table's column is a ``bigint``; the keys
    returned here are the 10-digit zero-padded strings the rest of the module uses, so the
    round trip is ``int()`` out and ``sec.cik10()`` back."""
    if not ciks:
        return {}
    rows = conn.execute(
        "SELECT cik, status FROM fundamentals_log WHERE cik = ANY(%s)",
        ([int(c) for c in ciks],),
    ).fetchall()
    return {sec.cik10(number): status for number, status in rows}


# ----------------------------------------------------- per-CIK fetch and filtering


# ``_period_start`` is defined once, below, beside the writer that uses it.


def select_facts(facts: Iterable[Fact], since_filed: date) -> tuple[Fact, ...]:
    """The facts worth storing: in ``ladder.LADDER_TAGS`` and filed on or after ``since_filed``.

    Sorted into a deterministic order so a batch's COPY payload -- and therefore the test
    expectations -- do not depend on the order data.sec.gov happened to return.
    """
    kept = [f for f in facts if (f.taxonomy, f.tag) in LADDER_TAGS and f.filed >= since_filed]
    kept.sort(
        key=lambda f: (
            f.taxonomy, f.tag, f.unit, _period_start(f), f.period_end, f.accn, f.filed
        )
    )
    return tuple(kept)


def fetch_cik(job: CikJob, opts: Options, source: FactsSource) -> CikResult:
    """Fetch one CIK's facts. Never raises: every failure becomes a ``failed`` result so one
    dead filer cannot end the run.

    The CIK is already resolved -- ``plan_jobs`` did that, and did it once for the whole run
    rather than once per symbol. ``source.company_facts`` returns a ``sec.CompanyFacts``
    (C4), so the facts are read off ``.facts``; the tag filter is passed down so the client
    can skip parsing units the ladder does not read.
    """
    try:
        response = source.company_facts(job.cik, tags=tuple(sorted(t for _, t in LADDER_TAGS)))
    except sec.SecNotFound as exc:
        # C4: a 404 from data.sec.gov means this CIK has no companyfacts document at all.
        # That is a fact about the filer, not a fault, so it is `empty` and exits 0 -- the
        # same call `backfill` makes for a symbol with no bars.
        return CikResult(
            job.cik,
            job.symbols,
            STATUS_EMPTY,
            error=_error_text(f"no companyfacts document for CIK {job.cik}: {exc}"),
        )
    except Exception as exc:  # noqa: BLE001 - one filer's failure never ends the run
        error = _error_text(f"{type(exc).__name__}: {exc}")
        log.warning(
            "fundamentals: CIK %s (%s) failed: %s", job.cik, ", ".join(job.symbols), error
        )
        return CikResult(job.cik, job.symbols, STATUS_FAILED, error=error)
    kept = select_facts(response.facts, opts.since_filed)
    if not kept:
        return CikResult(
            job.cik,
            job.symbols,
            STATUS_EMPTY,
            error=(
                f"CIK {job.cik} returned no fact in the ingest tag set filed on or after "
                f"{opts.since_filed.isoformat()}"
            ),
        )
    return CikResult(job.cik, job.symbols, STATUS_OK, facts=kept)


def _error_text(text: str) -> str:
    return text if len(text) <= ERROR_MAX_LEN else text[: ERROR_MAX_LEN - 3] + "..."


# ----------------------------------------------------------------------- writes


def _to_numeric(value: Decimal | float | int | str) -> Decimal:
    """A fact value as an exact ``numeric``. Rejects bools and non-finite floats."""
    if isinstance(value, bool):
        raise TypeError("bool is not a fact value")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite fact value: {value!r}")
        number = Decimal(repr(value))
    else:
        try:
            number = Decimal(value)
        except (InvalidOperation, TypeError) as exc:
            raise ValueError(f"not a fact value: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"non-finite fact value: {value!r}")
    return number


_FACTS_TEMP = """
CREATE TEMP TABLE IF NOT EXISTS _seer_facts_in
(LIKE fundamental_facts INCLUDING DEFAULTS) ON COMMIT DELETE ROWS
"""

# Twelve columns, in phase 2's declared order. THERE IS NO `frame` COLUMN: phase 2 omitted
# SEC's canonical-frame annotation on purpose (nothing in the ladder reads it, and it costs
# ~10-22 MB of a 0.5 GB tier). sec.Fact still carries `frame`; it is simply not persisted.
_FACTS_COPY = (
    "COPY _seer_facts_in "
    "(cik, taxonomy, tag, unit, period_start, period_end, accn, val, fy, fp, form, filed) "
    "FROM STDIN"
)

# DISTINCT ON is required, not defensive: ON CONFLICT DO UPDATE cannot touch the same row
# twice in one statement, and companyfacts can repeat an identical entry inside a unit array.
# The conflict tuple IS the fact identity -- `accn` keeps a restatement as a separate row and
# `period_start` keeps a 10-K's Q4 figure from colliding with its full-year figure.
_FACTS_UPSERT = """
INSERT INTO fundamental_facts AS f
    (cik, taxonomy, tag, unit, period_start, period_end, accn, val, fy, fp, form, filed)
SELECT DISTINCT ON (cik, taxonomy, tag, unit, period_start, period_end, accn)
       cik, taxonomy, tag, unit, period_start, period_end, accn, val, fy, fp, form, filed
FROM _seer_facts_in
ORDER BY cik, taxonomy, tag, unit, period_start, period_end, accn, filed DESC, val DESC
ON CONFLICT (cik, taxonomy, tag, unit, period_start, period_end, accn) DO UPDATE
SET val = EXCLUDED.val,
    fy = EXCLUDED.fy,
    fp = EXCLUDED.fp,
    form = EXCLUDED.form,
    filed = EXCLUDED.filed
WHERE (f.val, f.fy, f.fp, f.form, f.filed)
      IS DISTINCT FROM
      (EXCLUDED.val, EXCLUDED.fy, EXCLUDED.fp, EXCLUDED.form, EXCLUDED.filed)
"""


def _period_start(fact: Fact) -> date:
    """``fact.period_start``, or ``fact.period_end`` when SEC omitted it (C1).

    ``period_start = period_end`` IS the stored encoding of "instantaneous"; phase 2's column
    is NOT NULL and in the primary key, and phase 5 maps the equality back to None on the read
    side. No us-gaap or dei duration fact has a one-day period, so the convention is
    unambiguous.
    """
    return fact.period_end if fact.period_start is None else fact.period_start


def upsert_facts(conn: psycopg.Connection, rows: Iterable[tuple[int, Fact]]) -> int:
    """Insert new facts and update changed ones; return how many rows were inserted or
    changed. ``rows`` pairs the already-resolved integer CIK with each fact -- phase 2's
    column is ``bigint``, so the 10-digit zero-padded string form never reaches the database.
    Facts identical to the stored row are skipped by the ``IS DISTINCT FROM`` guard, so an
    identical re-run returns 0. Does not commit."""
    batch = list(rows)
    if not batch:
        return 0
    with conn.cursor() as cur:
        cur.execute(_FACTS_TEMP)
        cur.execute("TRUNCATE _seer_facts_in")
        with cur.copy(_FACTS_COPY) as copy:
            for number, fact in batch:
                copy.write_row(
                    (
                        number,
                        fact.taxonomy,
                        fact.tag,
                        fact.unit,
                        _period_start(fact),
                        fact.period_end,
                        fact.accn,
                        _to_numeric(fact.val),
                        fact.fy,
                        fact.fp,
                        fact.form,
                        fact.filed,
                    )
                )
        cur.execute(_FACTS_UPSERT)
        changed = cur.rowcount
        cur.execute("TRUNCATE _seer_facts_in")
    return changed


# backfill's _LOG_UPSERT (backfill.py:360-376), including the guard that an attempt which
# fails never downgrades a filer already logged ok -- but KEYED BY cik, not symbol (C2), and
# with phase 2's `first_filed`/`last_filed` names. One row per companyfacts fetch.
_LOG_UPSERT = """
INSERT INTO fundamentals_log
    (cik, status, first_filed, last_filed, "rows", error, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, now())
ON CONFLICT (cik) DO UPDATE SET
    status = EXCLUDED.status,
    first_filed = EXCLUDED.first_filed,
    last_filed = EXCLUDED.last_filed,
    "rows" = EXCLUDED."rows",
    error = EXCLUDED.error,
    updated_at = EXCLUDED.updated_at
WHERE (fundamentals_log.status, fundamentals_log.first_filed, fundamentals_log.last_filed,
       fundamentals_log."rows", fundamentals_log.error)
      IS DISTINCT FROM
      (EXCLUDED.status, EXCLUDED.first_filed, EXCLUDED.last_filed,
       EXCLUDED."rows", EXCLUDED.error)
  AND NOT (fundamentals_log.status = 'ok' AND EXCLUDED.status = 'failed')
"""


def _write_batch(conn: psycopg.Connection, results: Sequence[CikResult], dry_run: bool) -> int:
    """One batch's facts and its log rows, in one transaction. A crash before the commit
    loses this batch and nothing else; the log rows are written with the facts they
    describe, so a resumed run can never skip a CIK whose facts were not stored.

    ``results`` is a sequence of ``CikResult``, one per distinct CIK -- the batch loop never
    sees a symbol. That is what makes the log row count equal the fetch count (C2), and it is
    why ``executemany`` cannot hit the same primary key twice in one call: ``plan_jobs``
    guarantees the CIKs in a batch are distinct.

    Symbols with no CIK never reach here. ``plan_jobs`` returns them separately and they get
    no log row at all, because the table's primary key is a ``bigint`` CIK and they have
    none. They are re-evaluated on the next run, which is correct: nothing was fetched and
    nothing was stored.
    """
    params = [
        (
            int(r.cik),
            r.status,
            min(f.filed for f in r.facts) if r.facts else None,
            max(f.filed for f in r.facts) if r.facts else None,
            len(r.facts),
            r.error,
        )
        for r in results
    ]
    with db.transaction(conn, dry_run):
        written = upsert_facts(conn, ((int(r.cik), f) for r in results for f in r.facts))
        with conn.cursor() as cur:
            cur.executemany(_LOG_UPSERT, params)
    return written


_MAP_SELECT = "SELECT symbol, cik, start_date, end_date, company, source, note FROM ticker_cik"
_MAP_INSERT = (
    "INSERT INTO ticker_cik (symbol, cik, start_date, end_date, company, source, note) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)


def sync_ticker_cik(
    conn: psycopg.Connection, mappings: Iterable[cik.CikRow], dry_run: bool
) -> tuple[int, bool]:
    """Mirror the vendored map into ``ticker_cik``: a full replace in one transaction, a
    no-op when the stored rows already equal the computed ones -- the shape
    ``universe refresh`` uses (commands/universe.py:306-312). Returns (rows, changed).

    Phase 2's column names, not phase 1's CSV header (C3): ``symbol``, and ``company`` for the
    CSV's ``company_name``. ``cik`` is a ``bigint``, so the CSV's 10-digit zero-padded string
    is parsed with ``int()``. **Rows whose CSV ``cik`` is ``cik.NO_FILER`` are skipped** --
    the column is NOT NULL and those symbols have no EDGAR filer to record. They are still
    resolvable from the CSV, which is what ``resolve_window_ciks`` reads; the table is a mirror
    for SQL joins (phase 6's panel load), not the source of truth.
    """
    wanted = {
        (
            m.symbol,
            int(m.cik),
            m.start_date,
            m.end_date,
            m.company_name,
            m.source,
            m.note or None,
        )
        for m in mappings
        if m.cik is not None
    }
    stored = {tuple(row) for row in conn.execute(_MAP_SELECT).fetchall()}
    if stored == wanted:
        conn.rollback()
        log.info("fundamentals: ticker_cik unchanged (%d rows)", len(wanted))
        return len(wanted), False
    ordered = sorted(wanted, key=lambda r: (r[0], r[2]))  # (symbol, start_date) -- the PK
    with db.transaction(conn, dry_run):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ticker_cik")
            cur.executemany(_MAP_INSERT, ordered)
    log.info("fundamentals: ticker_cik replaced with %d rows", len(wanted))
    return len(wanted), True


# ------------------------------------------------------------------ orchestration


def ingest(
    conn: psycopg.Connection,
    opts: Options,
    *,
    source: FactsSource,
    mappings: Sequence[cik.CikRow] | None = None,
) -> Summary:
    """Run the ingest on ``conn``. The SEC client is injected, so tests never touch the
    network and no sleep ever happens here.

    Order matters: the map is resolved and the jobs planned **before** the map mirror runs,
    so a dry run plans against exactly the rows a real run would.
    """
    summary = Summary()
    rows = list(load_cik_map()) if mappings is None else list(mappings)
    if not rows:
        raise FundamentalsError(
            "the vendored ticker->CIK map is empty; generate engine/data/ticker_cik.csv first"
        )

    windows = membership_windows(conn, opts.since, opts.today)
    symbols = select_symbols(opts, windows)
    jobs, unresolved, summary.skipped = plan_jobs(conn, opts, symbols, windows, rows)
    _end_read(conn)

    if opts.sync_map:
        summary.map_rows, summary.map_changed = sync_ticker_cik(conn, rows, opts.dry_run)
        _end_read(conn)

    for result in unresolved:
        _record(summary, result)
    _ingest_facts(conn, opts, jobs, summary, source)

    summary.facts_bytes = _facts_size(conn)
    _end_read(conn)
    _sort_summary(summary)
    return summary


def _ingest_facts(
    conn: psycopg.Connection,
    opts: Options,
    jobs: Sequence[CikJob],
    summary: Summary,
    source: FactsSource,
) -> None:
    """Fetch and write ``jobs`` in batches. ``batch_size`` counts **CIKs** -- one SEC call
    each -- not symbols; a batch of 20 is 20 fetches whether or not a share class is in it."""
    size = opts.batch_size
    batches = [list(jobs[i : i + size]) for i in range(0, len(jobs), size)]
    log.info(
        "fundamentals: %d CIKs covering %d symbols in %d batches (%d symbols skipped), "
        "facts filed on or after %s",
        len(jobs), sum(len(j.symbols) for j in jobs), len(batches), summary.skipped,
        opts.since_filed,
    )
    for number, batch in enumerate(batches, start=1):
        results = [fetch_cik(job, opts, source) for job in batch]
        written = _write_batch(conn, results, opts.dry_run)
        summary.facts_written += written
        for result in results:
            summary.ciks_fetched += 1
            summary.facts_fetched += len(result.facts)   # per CIK: never double-counted
            for per in result.per_symbol():
                _record(summary, per)
        log.info(
            "fundamentals: batch %d/%d done: %d ok, %d empty, %d failed, %d fact rows changed",
            number, len(batches),
            sum(r.status == STATUS_OK for r in results),
            sum(r.status == STATUS_EMPTY for r in results),
            sum(r.status == STATUS_FAILED for r in results),
            written,
        )


def _record(summary: Summary, result: SymbolResult) -> None:
    """File one symbol's outcome into the summary. The only writer of the three lists."""
    if result.status == STATUS_OK:
        summary.ok.append(result.symbol)
    elif result.status == STATUS_EMPTY:
        summary.empty.append(result.symbol)
    else:
        summary.failed.append(result.symbol)


def _sort_summary(summary: Summary) -> None:
    """The three lists are sorted at the end, because unresolved symbols are filed before the
    fetched ones and a share-class fan-out appends two at once. Deterministic output is what
    makes ``format_summary`` testable and a run-to-run diff meaningful."""
    summary.ok.sort()
    summary.empty.sort()
    summary.failed.sort()


def _facts_size(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT pg_total_relation_size('fundamental_facts')").fetchone()
    return int(row[0])


def _end_read(conn: psycopg.Connection) -> None:
    """Close the implicit read-only transaction so db.transaction starts at top level."""
    conn.rollback()


# ---------------------------------------------------------------------- summary


def format_summary(summary: Summary, opts: Options) -> str:
    lines = [
        f"fundamentals: members since {opts.since.isoformat()}, "
        f"facts filed on or after {opts.since_filed.isoformat()}"
        + (" (dry run: every write rolled back)" if opts.dry_run else ""),
    ]
    if opts.sync_map:
        state = "replaced" if summary.map_changed else "unchanged"
        lines.append(f"  ticker_cik: {summary.map_rows} rows, {state}")
    lines.append(
        f"  symbols: {len(summary.ok)} ok, {len(summary.empty)} empty, "
        f"{len(summary.failed)} failed, {summary.skipped} skipped (CIK already logged)"
    )
    # The counts above are per symbol; the fetch and the log are per CIK (C2). The two differ
    # by the share-class pairs in scope, and printing both is what tells the operator that
    # GOOG and GOOGL cost one SEC call and hold one fundamentals_log row between them.
    lines.append(
        f"  filers: {summary.ciks_fetched} companyfacts calls, "
        f"{summary.ciks_fetched} fundamentals_log rows written"
    )
    lines.append(
        f"  facts: {summary.facts_fetched:,} kept, "
        f"{summary.facts_written:,} inserted or changed"
    )
    if summary.failed:
        lines.append(f"  failed: {', '.join(summary.failed)}  (re-run with --retry-failed)")
    if summary.empty:
        lines.append(f"  empty: {', '.join(summary.empty)}")
    if summary.facts_bytes is not None:
        lines.append(
            f"  fundamental_facts table: {summary.facts_bytes / (1024 * 1024):.1f} MB "
            "(pg_total_relation_size)"
        )
    return "\n".join(lines)
