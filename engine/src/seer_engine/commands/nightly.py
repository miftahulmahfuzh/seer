"""nightly: append the newest session(s) from Massive, apply splits, record dividends and USD/IDR, write the run.

Flow (all bars, splits, dividends, FX and the run's success land in ONE transaction):
  1. purge demo data if a demo run exists (own transaction; rolled back under --dry-run)
  2. rd = run_dates(now); start_run -> None means this session already succeeded -> exit 0, no writes
  3. missing sessions = after SPY's latest bar .. rd.data_date (at most MAX_GAP)
  4. fetch everything into memory (grouped daily + splits + cash dividends per session, latest FX);
     no DB writes. Each session's wanted set is the universe set plus the symbols paper state
     holds or has pending; coverage is checked over the universe set only
  5. one transaction: apply splits to pre-existing history (bars and dividends), upsert bars,
     upsert dividends, upsert FX, finish_run
  6. any exception after start_run: rollback, fail_run(error) in its own transaction, exit 1
"""
from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

import psycopg

from seer_engine import bars, config, dates, db, demo, dividends, fx, http, massive, runs, splits, universe
from seer_engine.bars import Bar
from seer_engine.dividends import Dividend
from seer_engine.splits import Split

log = logging.getLogger(__name__)

HELP = "Fetch the latest session's bars (Massive), splits, cash dividends and USD/IDR; write one runs row"

MAX_GAP = 30
MIN_COVERAGE = 0.90
MAX_ERROR_LEN = 2000

FxFetcher = Callable[[], tuple[date, Decimal]]


class NightlyError(RuntimeError):
    """A precondition or data-quality check failed; the run is marked failed."""


@dataclass(frozen=True)
class Fetched:
    sessions: list[date]
    bars_by_session: dict[date, list[Bar]]
    splits: list[Split]
    first_opens: dict[str, Decimal]
    fx_row: tuple[date, Decimal]
    dividends: list[Dividend]


def _parse_now(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--now must be ISO 8601 (e.g. 2026-10-02T23:00:00Z): {value!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        metavar="ISO8601",
        help="pretend the current time is this (UTC if no offset); for tests and replays",
    )


def run(args: argparse.Namespace) -> int:
    try:
        api_key = config.require("MASSIVE_API_KEY")
    except config.ConfigError as e:
        log.error("%s", e)
        return 2  # same code cli.main gives any ConfigError (phase 1): a setup problem, not a failed run
    now = getattr(args, "now", None) or datetime.now(timezone.utc)
    conn = db.connect()
    try:
        return execute(
            conn,
            now=now,
            client=massive.Client(api_key),
            dry_run=bool(args.dry_run),
            secret=api_key,
        )
    finally:
        conn.close()


def _error_text(e: BaseException, secret: str | None) -> str:
    text = http.redact(f"{type(e).__name__}: {e}")
    if secret:
        text = text.replace(secret, "***")
    return text[:MAX_ERROR_LEN]


def execute(
    conn: psycopg.Connection,
    *,
    now: datetime,
    client: massive.MassiveSource,
    dry_run: bool = False,
    fetch_fx: FxFetcher | None = None,
    secret: str | None = None,
) -> int:
    """Run one nightly pass against `conn`. Returns the process exit code (0 ok / no-op, 1 failed)."""
    fetch_fx = fetch_fx if fetch_fx is not None else fx.fetch_latest
    demo.purge_demo_if_needed(conn, dry_run)

    rd = dates.run_dates(now)
    log.info("now %s -> data_date %s, session_date %s", now.isoformat(), rd.data_date, rd.session_date)

    with db.transaction(conn, dry_run):
        run_id = runs.start_run(conn, rd)
    if run_id is None:
        log.info("session %s already succeeded; nothing to do", rd.session_date)
        return 0
    if dry_run:
        log.info("dry-run: would start a run for session %s", rd.session_date)

    try:
        fetched = _fetch(conn, client, rd, fetch_fx)
        _write(conn, rd, fetched, run_id, dry_run)
    except Exception as e:  # noqa: BLE001 - every failure must become a failed run
        message = _error_text(e, secret)
        conn.rollback()
        log.error("nightly failed for session %s: %s", rd.session_date, message)
        if dry_run:
            log.info("dry-run: would mark the run failed")
            return 1
        with db.transaction(conn, False):
            runs.fail_run(conn, run_id, message)
        return 1
    return 0


def _fetch(
    conn: psycopg.Connection,
    client: massive.MassiveSource,
    rd: dates.RunDates,
    fetch_fx: FxFetcher,
) -> Fetched:
    """All reads and network fetches. Writes nothing; leaves no transaction open."""
    try:
        last = bars.latest_bar_date(conn, universe.BENCHMARK)
        if last is None:
            raise NightlyError(f"no {universe.BENCHMARK} bars stored; run `backfill` first")
        missing = dates.sessions(dates.next_session(last), rd.data_date) if last < rd.data_date else []
        if len(missing) > MAX_GAP:
            raise NightlyError(
                f"gap of {len(missing)} sessions ({missing[0]}..{missing[-1]}) exceeds {MAX_GAP}; "
                f"run `backfill --start {missing[0]}` first"
            )
        wanted = {d: set(universe.symbols_for_bars(conn, d)) for d in missing}
        held = {d: universe.paper_symbols(conn, d) for d in missing}
    finally:
        conn.rollback()

    for d in missing:
        if wanted[d] <= {universe.BENCHMARK}:
            raise NightlyError(f"universe is empty for {d}; run `universe refresh` first")

    if missing:
        log.info("fetching %d session(s): %s..%s", len(missing), missing[0], missing[-1])
    else:
        log.info("bars already reach %s; no sessions to fetch", rd.data_date)

    bars_by_session: dict[date, list[Bar]] = {}
    first_opens: dict[str, Decimal] = {}
    fetched_splits: list[Split] = []
    fetched_dividends: list[Dividend] = []
    for d in missing:
        got = client.grouped(d)
        want = wanted[d]
        if universe.BENCHMARK not in got:
            raise NightlyError(f"{universe.BENCHMARK} missing from grouped daily for {d}")
        present = sorted(want & got.keys())
        absent = sorted(want - got.keys())
        coverage = len(present) / len(want)
        if coverage < MIN_COVERAGE:
            raise NightlyError(
                f"grouped daily for {d} covers {len(present)}/{len(want)} universe symbols "
                f"({coverage:.1%}) < {MIN_COVERAGE:.0%}"
            )
        if absent:
            log.warning(
                "%s: %d universe symbol(s) absent from grouped daily (renamed, delisted or halted?): %s",
                d,
                len(absent),
                ", ".join(absent),
            )
        # Paper-held symbols outside the universe set: stored when present, never counted in the
        # coverage above. Absent ones only warn: the paper step force-closes a position whose
        # bars ended, as the runners do.
        extra = held[d] - want
        extra_present = sorted(extra & got.keys())
        extra_absent = sorted(extra - got.keys())
        if extra_absent:
            log.warning(
                "%s: %d paper-held symbol(s) outside the universe absent from grouped daily: %s",
                d,
                len(extra_absent),
                ", ".join(extra_absent),
            )
        session_bars = [got[s] for s in sorted(set(present) | set(extra_present))]
        bars_by_session[d] = session_bars
        for b in session_bars:
            first_opens.setdefault(b.symbol, b.open)
        fetched_splits.extend(client.splits(d))
        fetched_dividends.extend(client.dividends(d))

    fx_row = fetch_fx()

    split_symbols = {s.symbol for s in fetched_splits}
    tracked = set().union(*wanted.values(), *held.values()) if missing else set()
    try:
        with_bars = splits.symbols_with_bars(conn, split_symbols - tracked)
    finally:
        conn.rollback()
    relevant = [s for s in fetched_splits if s.symbol in tracked or s.symbol in with_bars]
    if fetched_splits:
        log.info("splits: %d fetched, %d relevant", len(fetched_splits), len(relevant))

    dividend_symbols = tracked | {universe.BENCHMARK}
    cash = dividends.adjust_for_splits(
        dividends.totals(x for x in fetched_dividends if x.symbol in dividend_symbols),
        relevant,
    )
    if fetched_dividends:
        log.info("dividends: %d cash row(s) fetched, %d tracked (symbol, ex-date)", len(fetched_dividends), len(cash))

    return Fetched(
        sessions=list(missing),
        bars_by_session=bars_by_session,
        splits=relevant,
        first_opens=first_opens,
        fx_row=fx_row,
        dividends=cash,
    )


def _write(
    conn: psycopg.Connection,
    rd: dates.RunDates,
    f: Fetched,
    run_id: int,
    dry_run: bool,
) -> None:
    """The single data transaction. Under dry-run it runs fully and is rolled back."""
    with db.transaction(conn, dry_run):
        if dry_run:
            # The run row from the dry start was rolled back; recreate it inside this
            # (also rolled back) transaction so finish_run exercises a real row.
            dry_id = runs.start_run(conn, rd)
            if dry_id is not None:
                run_id = dry_id
        # Splits first: they rewrite pre-existing bars and dividends only. The fetched bars and
        # dividends below are already in post-split units and must not be rewritten again.
        outcomes = splits.apply_splits(conn, f.splits, f.first_opens)
        changed = 0
        for d in f.sessions:
            changed += bars.upsert_bars(conn, f.bars_by_session[d])
        dividends_changed = dividends.upsert_dividends(conn, f.dividends)
        fx_changed = fx.upsert_fx(conn, [f.fx_row])
        runs.finish_run(conn, run_id)
        total = sum(len(f.bars_by_session[d]) for d in f.sessions)
        applied = sum(1 for o in outcomes if o.applied)
        log.info(
            "%s %d bars (%d changed) over %d session(s), %d split(s) recorded (%d applied), "
            "%d dividend(s) (%d changed), fx %s=%s (%d changed), run %s success",
            "dry-run: would write" if dry_run else "wrote",
            total,
            changed,
            len(f.sessions),
            sum(1 for o in outcomes if o.recorded),
            applied,
            len(f.dividends),
            dividends_changed,
            f.fx_row[0],
            f.fx_row[1],
            fx_changed,
            run_id,
        )
    if dry_run:
        log.info("dry-run: rolled back; nothing written")
