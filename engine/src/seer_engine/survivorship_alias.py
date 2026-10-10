"""survivorship_alias -- the EODHD code an index member with no usable series trades under.

The survivorship-check store (``commands/survivorship_store``) fills the dev store's unserved
members from ``engine/.cache/eodhd/eod/<SYM>.json``, fetched under the store's own symbol. About
two hundred come back with nothing on their member days: the code now belongs to someone else
(``DOW`` is Dow Inc since 2019) or the company traded under another one (WorldCom is ``MCWEQ``).
EODHD keeps old companies under suffixed codes in its symbol lists -- ``DELL_old``, ``AT_old1``,
``TRW1`` -- so this module, offline:

1. lists candidate codes per member from ``symbols-US-delisted.json`` / ``symbols-US-live.json``:
   a hand-checked hint (``engine/data/eodhd_alias_hints.csv``), the normalized company name from
   ``ticker_cik.csv``, ``ticker_aliases.csv``, the class-share spelling (``GFS.A`` -> ``GFSA``),
   the bankruptcy stem (``ABKFQ`` -> ``ABKF``), and the vendor's own suffixes (``_old``,
   ``_oldN``, ``N``) -- never the store symbol's own code, which is what came back empty;
2. accepts a candidate only when its fetched series has at least ``MIN_MEMBER_ROWS`` rows on the
   member's index days and passes the same cleaning every other symbol gets. Two fitting
   candidates that are different price series resolve to none ("ambiguous"), unless exactly one
   of them was found by hint or name.

``fetch`` is the only network path (through an injected ``eodhd.Client``-like object) and writes
under ``<cache>/alias/`` only: ``probe/<CODE>.json`` per candidate and ``<SYM>.json`` per accepted
member. ``alias_sources`` turns the accepted alias files into ``survivorship.SourceSeries`` that
``commands/survivorship_store.plan_build`` takes as ``extra_sources``: each is cleaned there like
the cache's own series and ``survivorship.best_of`` keeps whichever covers more member days.
``report_rows`` then says, per target, what happened (``alias_report.csv``). ``eod/``, ``splits/``
and ``dividends/`` are only ever read.
"""

from __future__ import annotations

import csv
import functools
import io
import json
import logging
import os
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from seer_engine import dates, eodhd, research
from seer_engine import survivorship as sv
from seer_engine.backtest.market import Membership

log = logging.getLogger(__name__)

ALIAS_DIR = "alias"
PROBE_DIR = "probe"
ALIAS_SOURCE = "eodhd-alias"  # SourceSeries.source / Cleaned.source of an alias series
DELISTED_FILE = "symbols-US-delisted.json"
LIVE_FILE = "symbols-US-live.json"
NAMES_FILE = "ticker_cik.csv"
ALIASES_FILE = "ticker_aliases.csv"
HINTS_FILE = "eodhd_alias_hints.csv"
REPORT_FILE = "alias_report.csv"
REPORT_HEADER = ("symbol", "code", "name", "matched_by", "accepted", "reason")

#: Symbol-list types that are never an operating company's common stock. "ETF" stays allowed:
#: EODHD mislabels some delisted stocks (``PWER_old`` Power-One is typed ETF); the series test
#: rejects real funds, which do not trade on a 1990s member's days under its old code.
SKIP_TYPES = frozenset(
    {"FUND", "Mutual Fund", "Preferred Stock", "Warrant", "Unit", "Notes", "Bond", "BOND", "INDEX"}
)
MAX_CANDIDATES = 4  # per member, best match kinds first; caps the /eod probes at ~4 calls
MIN_MEMBER_ROWS = 20  # a month of sessions on member days before a code counts as overlapping
SAME_CLOSE_TOL = 0.005  # two codes whose closes agree within 0.5% ...
SAME_SERIES_SHARE = 0.95  # ... on 95% of shared member days are one company listed twice
EODHD_DELISTED_FROM = date(1997, 12, 31)  # where most delisted series begin (handover §3)
MATCH_ORDER = ("hint", "name", "alias", "class", "bankruptcy", "code-variant")
NAMED = frozenset({"hint", "name"})

#: Phase 1's classifications that put a symbol's bars into the store (everything but DROPPED).
USABLE_ACTIONS = frozenset({sv.KEPT, sv.REPAIRED, sv.TRIMMED})

NAME_STOP = frozenset(
    {
        "A", "AG", "AND", "B", "CL", "CO", "COMPANY", "CORP", "CORPORATION", "DE", "DEL", "GROUP",
        "HOLDING", "HOLDINGS", "INC", "INTERNATIONAL", "INTL", "LIMITED", "LLC", "LP", "LTD", "NEW",
        "NV", "NW", "OLD", "PLC", "SA", "THE",
    }
)

#: ``clean(series, intervals) -> result`` where ``result.action`` / ``result.reason`` are phase
#: 1's classification (``phase1_clean`` in production; a fake in the resolver tests).
Clean = Callable[[sv.SourceSeries, Sequence[tuple[date, date | None]]], Any]

_TAIL = re.compile(r"(.+?)(?:_old\d*|\d)")
_STATE = re.compile(r"/[A-Z]{2,3}/")


# ---- listings and names --------------------------------------------------------------------


@dataclass(frozen=True)
class Listing:
    code: str
    name: str
    type: str
    exchange: str
    delisted: bool


@dataclass(frozen=True)
class Listings:
    by_code: Mapping[str, Listing]
    by_root: Mapping[str, tuple[str, ...]]
    by_name: Mapping[str, tuple[str, ...]]

    @classmethod
    def of(cls, listings: Iterable[Listing]) -> Listings:
        by_code: dict[str, Listing] = {}
        for item in listings:
            by_code.setdefault(item.code, item)
        roots: dict[str, list[str]] = {}
        names: dict[str, list[str]] = {}
        for code, item in by_code.items():
            roots.setdefault(code_root(code), []).append(code)
            key = normalize_name(item.name)
            if key:
                names.setdefault(key, []).append(code)
        return cls(
            by_code=by_code,
            by_root={k: tuple(sorted(v)) for k, v in roots.items()},
            by_name={k: tuple(sorted(v)) for k, v in names.items()},
        )


@dataclass(frozen=True)
class Sources:
    """Everything the resolver reads besides the probes: the vendor's lists and engine/data."""

    listings: Listings
    names: Mapping[str, tuple[str, ...]]  # store symbol -> company names (ticker_cik.csv)
    aliases: Mapping[str, frozenset[str]]  # store symbol -> other tickers (ticker_aliases.csv, both ways)
    hints: Mapping[str, tuple[str, ...]]  # store symbol -> hinted codes


def code_root(code: str) -> str:
    """A vendor code without EODHD's re-listing suffix: ``DELL_old`` / ``AT_old1`` / ``TRW1`` -> stem."""
    m = _TAIL.fullmatch(code)
    return m.group(1) if m else code


def normalize_name(name: str | None) -> str:
    """Company name reduced for equality: ``DOW CHEMICAL CO /DE/`` == ``The Dow Chemical Company``."""
    text = (name or "").upper().replace("&", " AND ")
    text = _STATE.sub(" ", text)
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return " ".join(w for w in text.split() if w not in NAME_STOP)


def load_listings(cache_root: Path) -> Listings:
    """Both symbol lists, delisted first (a code in both keeps its delisted row); funds etc. skipped."""
    items: list[Listing] = []
    for filename, delisted in ((DELISTED_FILE, True), (LIVE_FILE, False)):
        path = Path(cache_root) / filename
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"{path}: expected a JSON list of symbols")
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            code = str(raw.get("Code") or "").strip()
            kind = str(raw.get("Type") or "")
            if not code or kind in SKIP_TYPES:
                continue
            items.append(
                Listing(code, str(raw.get("Name") or ""), kind, str(raw.get("Exchange") or ""), delisted)
            )
    return Listings.of(items)


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_sources(cache_root: Path, data_dir: Path) -> Sources:
    names: dict[str, list[str]] = {}
    for row in _csv_rows(Path(data_dir) / NAMES_FILE):
        if row.get("company_name"):
            names.setdefault(row["symbol"], []).append(row["company_name"])
    aliases: dict[str, set[str]] = {}
    for row in _csv_rows(Path(data_dir) / ALIASES_FILE):
        old, new = row.get("old", ""), row.get("new", "")
        if old and new:
            aliases.setdefault(old, set()).add(new)
            aliases.setdefault(new, set()).add(old)
    hints: dict[str, list[str]] = {}
    for row in _csv_rows(Path(data_dir) / HINTS_FILE):
        if row.get("symbol") and row.get("code"):
            hints.setdefault(row["symbol"], []).append(row["code"].strip())
    return Sources(
        listings=load_listings(cache_root),
        names={k: tuple(v) for k, v in names.items()},
        aliases={k: frozenset(v) for k, v in aliases.items()},
        hints={k: tuple(v) for k, v in hints.items()},
    )


# ---- candidates ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    code: str
    name: str
    matched_by: str  # one of MATCH_ORDER


def _base_code(symbol: str) -> str:
    return eodhd.ticker(symbol)[: -len(".US")]


def candidates(symbol: str, sources: Sources) -> tuple[Candidate, ...]:
    """Other EODHD codes ``symbol`` may trade under, best match kind first, at most MAX_CANDIDATES.

    The store symbol's own code is excluded: its series is ``eod/<SYM>.json``, already tried."""
    listings = sources.listings
    base = _base_code(symbol)
    found: dict[str, str] = {}

    def add(codes: Iterable[str], kind: str) -> None:
        for code in codes:
            if code != base and code in listings.by_code and code not in found:
                found[code] = kind

    add(sources.hints.get(symbol, ()), "hint")
    for company in sources.names.get(symbol, ()):
        key = normalize_name(company)
        if key:
            add(listings.by_name.get(key, ()), "name")
    for other in sorted(sources.aliases.get(symbol, ())):
        add(listings.by_root.get(_base_code(other), ()), "alias")
    if "." in symbol:
        head, _, tail = symbol.partition(".")
        for stem in (head + tail, head):  # GFS.A -> GFSA, GFS
            add(listings.by_root.get(stem, ()), "class")
    if len(base) >= 4 and base.endswith("Q"):
        stem = base.rstrip("Q")  # ABKFQ -> ABKF, MTLQQ -> MTL
        stems = [stem] + ([stem[:-1]] if stem.endswith("E") and len(stem) >= 4 else [])  # WCOEQ -> WCO
        for s in stems:
            for q in ("", "Q", "QQ"):
                add(listings.by_root.get(s + q, ()), "bankruptcy")
    add(listings.by_root.get(base, ()), "code-variant")
    ranked = sorted(found.items(), key=lambda kv: (MATCH_ORDER.index(kv[1]), kv[0]))
    return tuple(
        Candidate(code, listings.by_code[code].name, kind) for code, kind in ranked[:MAX_CANDIDATES]
    )


# ---- series tests --------------------------------------------------------------------------


def _on_member_day(day: date, intervals: Sequence[tuple[date, date | None]], end: date) -> bool:
    if day < research.MEMBERSHIP_START or day > end:
        return False
    return any(start <= day and (stop is None or day < stop) for start, stop in intervals)


def member_closes(
    rows: Any, intervals: Sequence[tuple[date, date | None]], end: date = research.DEV_END
) -> dict[date, float]:
    """Raw closes of ``rows`` (an /eod list) on the member's index days inside the dev window."""
    out: dict[date, float] = {}
    if not isinstance(rows, list):
        return out
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        try:
            day = date.fromisoformat(str(raw.get("date"))[:10])
            close = float(raw.get("close"))
        except (TypeError, ValueError):
            continue
        if close > 0 and _on_member_day(day, intervals, end):
            out[day] = close
    return out


def same_series(a: Mapping[date, float], b: Mapping[date, float]) -> bool:
    """One company under two codes: closes within SAME_CLOSE_TOL on SAME_SERIES_SHARE of shared days."""
    common = a.keys() & b.keys()
    if len(common) < MIN_MEMBER_ROWS:
        return False
    agree = sum(1 for d in common if abs(a[d] / b[d] - 1.0) <= SAME_CLOSE_TOL)
    return agree >= SAME_SERIES_SHARE * len(common)


def series_of(symbol: str, code: str, doc: Mapping[str, Any], *, dividends: bool = True) -> sv.SourceSeries:
    """A probe or alias doc as phase 1's ``SourceSeries`` for the store symbol ``symbol``.

    ``doc["dividends"]`` is the raw ``/div`` list (same row shape as the cached
    ``dividends/<SYM>.json`` rows); ``dividends=False`` while choosing, when it is not fetched yet."""
    return sv.SourceSeries(
        symbol=symbol,
        source=ALIAS_SOURCE,
        code=eodhd.exchange_code(code),
        bars=sv.parse_bars(doc.get("eod")),
        splits=sv.parse_splits(doc.get("splits")),
        dividends=sv.parse_dividend_rows(doc.get("dividends")) if dividends else (),
    )


@dataclass(frozen=True)
class Resolution:
    symbol: str
    code: str | None
    name: str
    matched_by: str
    accepted: bool
    reason: str
    candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class _Fit:
    cand: Candidate
    closes: Mapping[date, float]


def choose(
    symbol: str,
    cands: Sequence[Candidate],
    probes: Mapping[str, Mapping[str, Any]],
    intervals: Sequence[tuple[date, date | None]],
    *,
    clean: Clean,
    end: date = research.DEV_END,
) -> Resolution:
    """The one code whose series fits ``symbol``'s membership, or None with the reason."""
    cands = tuple(cands)
    if not cands:
        return Resolution(symbol, None, "", "", False, "no candidate code in EODHD's symbol lists")
    fits: list[_Fit] = []
    notes: list[str] = []
    for cand in cands:
        doc = probes.get(cand.code)
        if doc is None:
            notes.append(f"{cand.code} not fetched")
            continue
        closes = member_closes(doc.get("eod"), intervals, end)
        if len(closes) < MIN_MEMBER_ROWS:
            notes.append(f"{cand.code} has {len(closes)} rows on member days")
            continue
        if "splits" not in doc:
            notes.append(f"{cand.code} splits not fetched")
            continue
        result = clean(series_of(symbol, cand.code, doc, dividends=False), intervals)
        if result.action not in USABLE_ACTIONS:
            notes.append(f"{cand.code} {result.action} ({result.reason})")
            continue
        fits.append(_Fit(cand, closes))
    if not fits:
        return Resolution(symbol, None, "", "", False, "no candidate fits: " + "; ".join(notes), cands)

    groups: list[list[_Fit]] = []
    for fit in fits:
        for group in groups:
            if same_series(group[0].closes, fit.closes):
                group.append(fit)
                break
        else:
            groups.append([fit])
    note = ""
    if len(groups) > 1:
        named = [g for g in groups if any(f.cand.matched_by in NAMED for f in g)]
        others = lambda keep: ", ".join(f.cand.code for g in groups if g is not keep for f in g)  # noqa: E731
        if len(named) != 1:
            listed = " vs ".join("/".join(f.cand.code for f in g) for g in groups)
            return Resolution(symbol, None, "", "", False, f"ambiguous: {listed} all fit", cands)
        chosen = named[0]
        note = f"; named match preferred over {others(chosen)}"
    else:
        chosen = groups[0]
    best = min(chosen, key=lambda f: (-len(f.closes), MATCH_ORDER.index(f.cand.matched_by), f.cand.code))
    if len(chosen) > 1:
        note += "; same series as " + ", ".join(f.cand.code for f in chosen if f is not best)
    return Resolution(
        symbol,
        best.cand.code,
        best.cand.name,
        best.cand.matched_by,
        True,
        f"{len(best.closes)} rows on member days{note}",
        cands,
    )


# ---- cache IO ------------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def probe_path(alias_dir: Path, code: str) -> Path:
    return Path(alias_dir) / PROBE_DIR / f"{code}.json"


def alias_path(alias_dir: Path, symbol: str) -> Path:
    return Path(alias_dir) / f"{symbol}.json"


def read_probe(alias_dir: Path, code: str) -> dict[str, Any] | None:
    doc = _read_json(probe_path(alias_dir, code))
    return doc if isinstance(doc, dict) else None


def read_alias(alias_dir: Path, symbol: str) -> dict[str, Any] | None:
    doc = _read_json(alias_path(alias_dir, symbol))
    return doc if isinstance(doc, dict) else None


# ---- membership and targets ----------------------------------------------------------------


def intervals_by_symbol(members: Membership) -> dict[str, tuple[tuple[date, date | None], ...]]:
    out: dict[str, list[tuple[date, date | None]]] = {}
    for symbol, start, end in members.intervals:
        out.setdefault(symbol, []).append((start, end))
    return {k: tuple(sorted(v, key=lambda iv: iv[0])) for k, v in out.items()}


@functools.lru_cache(maxsize=1)
def _sessions() -> tuple[tuple[date, ...], tuple[date, ...]]:
    """(every NYSE session STORE_START..DEV_END, those on or after MEMBERSHIP_START) -- the two
    sequences ``commands/survivorship_store.plan_build`` hands ``clean_symbol``."""
    sessions = tuple(dates.sessions(research.STORE_START, research.DEV_END))
    return sessions, tuple(d for d in sessions if d >= research.MEMBERSHIP_START)


def phase1_clean(series: sv.SourceSeries, intervals: Sequence[tuple[date, date | None]]) -> sv.Cleaned:
    """Phase 1's cleaning of one series against one member's intervals, exactly as ``plan_build``
    calls it (same sessions, same member days)."""
    sessions, member_window = _sessions()
    days = sv.member_sessions(
        ((series.symbol, start, end) for start, end in intervals), series.symbol, member_window
    )
    return sv.clean_symbol(series, days, sessions)


def targets(
    cache_root: Path,
    symbols: Iterable[str],
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
    *,
    clean: Clean,
) -> list[str]:
    """The unserved members whose original pull does not clean to a usable series, sorted.

    The same verdict phase 1's build reaches: a symbol never fetched (``read_series`` None) or
    cleaned to ``dropped``. On the real cache: phase 1's 200 drops."""
    out: list[str] = []
    for symbol in sorted(set(symbols)):
        if symbol in research.RESEARCH_ETFS:
            continue
        primary = sv.read_series(Path(cache_root), symbol)
        if primary is None or clean(primary, by_symbol.get(symbol, ())).action not in USABLE_ACTIONS:
            out.append(symbol)
    return out


def resolve(
    symbols: Iterable[str],
    *,
    sources: Sources,
    alias_dir: Path,
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
    clean: Clean,
    end: date = research.DEV_END,
) -> list[Resolution]:
    """Offline: candidates for every symbol and the choice the cached probes support."""
    out: list[Resolution] = []
    for symbol in symbols:
        cands = candidates(symbol, sources)
        probes = {c.code: p for c in cands if (p := read_probe(alias_dir, c.code)) is not None}
        out.append(choose(symbol, cands, probes, by_symbol.get(symbol, ()), clean=clean, end=end))
    return out


# ---- network: the injected client ----------------------------------------------------------


@dataclass
class FetchStats:
    calls: int = 0
    accepted: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)


def fetch(
    client: Any,
    alias_dir: Path,
    symbols: Sequence[str],
    *,
    sources: Sources,
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
    clean: Clean,
    refetch: bool = False,
    end: date = research.DEV_END,
) -> FetchStats:
    """Probe every candidate's /eod, fetch /splits where it overlaps, /div for the accepted code.

    Resumable: a member with ``alias/<SYM>.json`` is skipped and a cached probe is reused unless
    ``refetch``. A failed call skips that member (recorded in ``failed``); the rest go on."""
    stats = FetchStats()
    alias_dir = Path(alias_dir)
    for n, symbol in enumerate(symbols, 1):
        if not refetch and alias_path(alias_dir, symbol).is_file():
            stats.skipped += 1
            continue
        cands = candidates(symbol, sources)
        intervals = by_symbol.get(symbol, ())
        try:
            probes: dict[str, dict[str, Any]] = {}
            for cand in cands:
                doc = None if refetch else read_probe(alias_dir, cand.code)
                if doc is None:
                    doc = {"code": cand.code, "name": cand.name, "fetched": _now(), "eod": client.eod(cand.code)}
                    stats.calls += 1
                    _write_json(probe_path(alias_dir, cand.code), doc)
                if "splits" not in doc and len(member_closes(doc.get("eod"), intervals, end)) >= MIN_MEMBER_ROWS:
                    doc = {**doc, "splits": client.splits(cand.code)}
                    stats.calls += 1
                    _write_json(probe_path(alias_dir, cand.code), doc)
                probes[cand.code] = doc
            res = choose(symbol, cands, probes, intervals, clean=clean, end=end)
            if res.accepted and res.code is not None:
                dividends = client.dividends_by_code(res.code)
                stats.calls += 1
                chosen = probes[res.code]
                _write_json(
                    alias_path(alias_dir, symbol),
                    {
                        "symbol": symbol,
                        "code": res.code,
                        "name": res.name,
                        "matched_by": res.matched_by,
                        "fetched": _now(),
                        "eod": chosen.get("eod"),
                        "splits": chosen.get("splits"),
                        "dividends": dividends,
                    },
                )
                stats.accepted += 1
        except eodhd.EodhdError as exc:
            log.error("alias fetch: %s failed: %s", symbol, exc)
            stats.failed.append(symbol)
        if n % 25 == 0:
            log.info("alias fetch: %d of %d members, %d calls", n, len(symbols), stats.calls)
    return stats


# ---- the build's second source -------------------------------------------------------------


@dataclass(frozen=True)
class ReportRow:
    symbol: str
    code: str
    name: str
    matched_by: str
    accepted: bool
    reason: str


def _fetched_alias(alias_dir: Path, res: Resolution) -> dict[str, Any] | None:
    """The alias file for an accepted resolution, only when it holds the resolved code."""
    if not res.accepted or res.code is None:
        return None
    doc = read_alias(alias_dir, res.symbol)
    return doc if doc is not None and doc.get("code") == res.code else None


def alias_sources(
    alias_dir: Path, resolutions: Iterable[Resolution]
) -> dict[str, tuple[sv.SourceSeries, ...]]:
    """``plan_build``'s ``extra_sources``: one alias ``SourceSeries`` per accepted, fetched
    resolution, cleaned in the build with the alias code's own splits and dividends (the cached
    ``dividends/<SYM>.json`` belongs to whoever holds the store symbol now). A stale alias file
    whose code is not the resolution's is not offered."""
    out: dict[str, tuple[sv.SourceSeries, ...]] = {}
    for res in resolutions:
        doc = _fetched_alias(alias_dir, res)
        if doc is not None and res.code is not None:
            out[res.symbol] = (series_of(res.symbol, res.code, doc),)
    return out


def report_rows(
    resolutions: Iterable[Resolution],
    chosen: Mapping[str, Any],
    *,
    alias_dir: Path,
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
    clean: Clean,
) -> list[ReportRow]:
    """One ``alias_report.csv`` row per target, after the build chose: ``chosen`` is
    ``BuildPlan.cleaned`` (``Cleaned.source == ALIAS_SOURCE`` when ``best_of`` took the alias)."""
    rows: list[ReportRow] = []
    for res in resolutions:
        if not res.accepted or res.code is None:
            rows.append(ReportRow(res.symbol, "", "", "", False, res.reason))
            continue
        doc = _fetched_alias(alias_dir, res)
        if doc is None:
            held = read_alias(alias_dir, res.symbol)
            state = "is missing" if held is None else f"holds {held.get('code')}"
            rows.append(
                ReportRow(
                    res.symbol, res.code, res.name, res.matched_by, False,
                    f"{res.code} fits but alias/{res.symbol}.json {state}; run --fetch-aliases",
                )
            )
            continue
        result = chosen.get(res.symbol)
        if result is not None and getattr(result, "source", None) == ALIAS_SOURCE:
            rows.append(
                ReportRow(res.symbol, res.code, res.name, res.matched_by, True, f"{result.action}: {res.reason}")
            )
            continue
        alias = clean(series_of(res.symbol, res.code, doc), by_symbol.get(res.symbol, ()))
        why = (
            f"cleaning with dividends: {alias.action} ({alias.reason})"
            if alias.action not in USABLE_ACTIONS
            else f"not used: the original series covers at least as many member days ({alias.reason})"
        )
        rows.append(ReportRow(res.symbol, res.code, res.name, res.matched_by, False, why))
    return rows


def report_text(rows: Iterable[ReportRow]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(REPORT_HEADER)
    for r in sorted(rows, key=lambda r: r.symbol):
        writer.writerow([r.symbol, r.code, r.name, r.matched_by, "yes" if r.accepted else "no", r.reason])
    return buf.getvalue()


def summary(
    resolutions: Sequence[Resolution],
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
) -> list[str]:
    """Plain counts: how many members appear under another code at all, and how many fit."""
    total = len(resolutions)
    early = sum(
        1
        for r in resolutions
        if by_symbol.get(r.symbol) and all(stop is not None and stop <= EODHD_DELISTED_FROM for _, stop in by_symbol[r.symbol])
    )
    with_code = [r for r in resolutions if r.candidates]
    kinds = {k: sum(1 for r in with_code if r.candidates[0].matched_by == k) for k in MATCH_ORDER}
    accepted = sum(r.accepted for r in resolutions)
    ambiguous = sum(r.reason.startswith("ambiguous") for r in resolutions)
    prefix = "no candidate fits: "
    unfetched = sum(
        1
        for r in resolutions
        if r.reason.startswith(prefix)
        and all(note.endswith(" not fetched") for note in r.reason[len(prefix):].split("; "))
    )
    return [
        f"alias resolution over {total} members with no usable series "
        f"({early} left the index on or before {EODHD_DELISTED_FROM}, where EODHD's delisted history mostly starts)",
        f"  appear under another EODHD code: {len(with_code)} "
        f"(best match: " + ", ".join(f"{k} {v}" for k, v in kinds.items()) + ")",
        f"  under no other code at all: {total - len(with_code)}",
        f"  accepted {accepted}, ambiguous {ambiguous}, not fetched yet {unfetched}, "
        f"no candidate fits {len(with_code) - accepted - ambiguous - unfetched}",
    ]
