"""market_series -- the market-wide daily series (VIX family, Treasury yields, gold) in the store.

    python -m seer_engine market_series                          # coverage report only, no writes
    python -m seer_engine market_series --refresh                # write market_series.csv
    python -m seer_engine market_series --refresh --store /home/miftah/seer/engine/.research-sv

Reads only EODHD's raw answers already cached under ``engine/.cache/eodhd/market/<TICKER>.json``
during the paid month (gitignored; the licence is personal, so raw rows never enter git or
``web/``). No network and no token: this command cannot fetch a missing file.

Normalization (plan Decision D5), each verified against published yields when it was written:

- VIX, VIX9D, VXN, VVIX: the close as-is, in index points.
- VIX3M: ``VIX3M.INDX`` wherever it has a close, else ``VXV.INDX`` (its name until 2007-11-13).
  The two agree on 1,987 of the 1,996 dev-window sessions both have, and differ by at most 1.05
  points (2014-10-15); the report prints the agreement on every run.
- T13W: ``IRX.INDX`` close, already a yield in percent.
- T5Y, T10Y, T30Y: ``FVX`` / ``TNX`` / ``TYX`` close divided by 10. The vendor index is the yield
  times ten: TNX 65.48 on 2000-01-03 is a 6.548% ten-year yield.
- GOLD: ``XAUUSD.FOREX`` close, USD per ounce.

Rows dated before ``research.STORE_START`` or after the store's window end, rows on a day that
was not an NYSE session (bond and FX markets publish on some stock-market holidays), and rows
with no close are dropped and counted in the report. ``--refresh`` writes through
``research.refresh_market_series``: every other store file is carried over byte for byte, so the
price fingerprint the lab compares trials on does not move. The global ``--dry-run`` writes
nothing.

Exit codes: 0 ok; 2 the store's manifest is missing or unreadable, a cache file is missing or
unreadable, a series has no row in the window, or the refresh was refused.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from seer_engine import config, dates, research
from seer_engine.backtest.window import Window

log = logging.getLogger(__name__)

HELP = (
    "Report the market series (VIX family, Treasury yields, gold) cached from EODHD and write "
    "them into a research store as market_series.csv (--refresh). Cache only, no network."
)

CACHE_DIR = config.REPO_ROOT / "engine" / ".cache" / "eodhd" / "market"

_ONE = Decimal(1)
_TEN = Decimal(10)


@dataclass(frozen=True)
class Source:
    """One store series and where it comes from.

    ``tickers`` are cache file stems in preference order: on each date the first one with a close
    supplies the value. ``divisor`` turns the vendor close into ``unit``.
    """

    series: str
    tickers: tuple[str, ...]
    divisor: Decimal
    unit: str


SOURCES: tuple[Source, ...] = (
    Source("GOLD", ("XAUUSD.FOREX",), _ONE, "USD/oz"),
    Source("T10Y", ("TNX.INDX",), _TEN, "percent"),
    Source("T13W", ("IRX.INDX",), _ONE, "percent"),
    Source("T30Y", ("TYX.INDX",), _TEN, "percent"),
    Source("T5Y", ("FVX.INDX",), _TEN, "percent"),
    Source("VIX", ("VIX.INDX",), _ONE, "points"),
    Source("VIX3M", ("VIX3M.INDX", "VXV.INDX"), _ONE, "points"),
    Source("VIX9D", ("VIX9D.INDX",), _ONE, "points"),
    Source("VVIX", ("VVIX.INDX",), _ONE, "points"),
    Source("VXN", ("VXN.INDX",), _ONE, "points"),
)  # in research.MARKET_SERIES_NAMES order; tests/test_market_series.py pins the equality


class CacheError(ValueError):
    """A cache file is missing, unreadable, or not EODHD's /eod answer shape."""


def _close(raw: object) -> Decimal | None:
    """A vendor close as a finite Decimal, or None when there is none."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, Decimal):
        return raw if raw.is_finite() else None
    return None


def read_ticker(cache: Path, ticker: str) -> dict[date, Decimal | None]:
    """``date -> close`` from ``<cache>/<ticker>.json``, decimals exact (``parse_float=Decimal``)."""
    path = Path(cache) / f"{ticker}.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except FileNotFoundError as exc:
        raise CacheError(
            f"{path}: not in the cache; it was downloaded during the paid EODHD month and this "
            "command never fetches"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CacheError(f"{path}: not valid JSON ({exc})") from exc
    if doc is None:
        raise CacheError(f"{path}: EODHD returned nothing for {ticker}")
    if not isinstance(doc, list):
        raise CacheError(f"{path}: expected a list of daily rows, got {type(doc).__name__}")
    out: dict[date, Decimal | None] = {}
    for i, row in enumerate(doc):
        if not isinstance(row, dict) or "date" not in row:
            raise CacheError(f"{path}[{i}]: expected an object with a date")
        try:
            d = date.fromisoformat(row["date"])
        except (TypeError, ValueError) as exc:
            raise CacheError(f"{path}[{i}]: bad date {row['date']!r}") from exc
        if d in out:
            raise CacheError(f"{path}: two rows dated {d}")
        out[d] = _close(row.get("close"))
    return out


@dataclass(frozen=True)
class SeriesReport:
    """One series after normalization: the rows to store and what was dropped on the way."""

    series: str
    unit: str
    rows: tuple[tuple[date, Decimal], ...]  # ascending, already divided into ``unit``
    by_ticker: tuple[tuple[str, int], ...]  # rows each ticker supplied, in preference order
    outside: int  # dated before STORE_START or after the window end
    off_session: int  # inside the window, not an NYSE session
    no_close: int  # an NYSE session in the window where no ticker had a close
    overlap: int  # kept sessions where two or more tickers had a close (0 for one ticker)
    differ: int  # of those, sessions where the closes were not equal
    max_diff: Decimal | None  # the largest close spread among them, vendor units
    max_diff_date: date | None


def normalize(
    source: Source, raw: Mapping[str, Mapping[date, Decimal | None]], window: Window
) -> SeriesReport:
    """``source``'s rows for ``window``: clipped, NYSE sessions only, divided into its unit."""
    all_dates = sorted({d for t in source.tickers for d in raw[t]})
    rows: list[tuple[date, Decimal]] = []
    taken = {t: 0 for t in source.tickers}
    outside = off_session = no_close = overlap = differ = 0
    max_diff: Decimal | None = None
    max_diff_date: date | None = None
    for d in all_dates:
        if d < research.STORE_START or d > window.end:
            outside += 1
            continue
        if not dates.is_session(d):
            off_session += 1
            continue
        closes = [(t, raw[t][d]) for t in source.tickers if raw[t].get(d) is not None]
        if not closes:
            no_close += 1
            continue
        ticker, close = closes[0]
        rows.append((d, close / source.divisor))
        taken[ticker] += 1
        if len(closes) > 1:
            overlap += 1
            values = [c for _, c in closes]
            spread = max(values) - min(values)
            if spread:
                differ += 1
            if max_diff is None or spread > max_diff:
                max_diff, max_diff_date = spread, d
    return SeriesReport(
        series=source.series,
        unit=source.unit,
        rows=tuple(rows),
        by_ticker=tuple((t, taken[t]) for t in source.tickers),
        outside=outside,
        off_session=off_session,
        no_close=no_close,
        overlap=overlap,
        differ=differ,
        max_diff=max_diff,
        max_diff_date=max_diff_date,
    )


def rows_for_store(reports: Sequence[SeriesReport]) -> list[tuple[str, date, Decimal]]:
    """Every report's rows as ``research.refresh_market_series`` takes them."""
    return [(r.series, d, v) for r in reports for d, v in r.rows]


def format_report(
    reports: Sequence[SeriesReport],
    *,
    cache: Path,
    store: Path,
    window: Window,
    members: Sequence[date],
) -> str:
    """The per-series coverage table, then one agreement line per spliced series."""
    have = set(members)
    lines = [
        f"market series from {cache}, for {store} ({window.name} window): rows "
        f"{research.STORE_START.isoformat()}..{window.end.isoformat()}, NYSE sessions only",
        (
            f"member days: {len(members)} sessions, {members[0].isoformat()}..{members[-1].isoformat()}"
            if members
            else "member days: none in this window"
        ),
        "",
        f"{'series':<6} {'unit':<8} {'rows':>5}  {'first':<10}  {'last':<10}  "
        f"{'member days':>15}  {'off-session':>11} {'outside':>7} {'no close':>8}  source",
    ]
    for r in reports:
        covered = sum(1 for d, _ in r.rows if d in have)
        share = f"{covered} ({covered / len(members):.1%})" if members else "-"
        first = r.rows[0][0].isoformat() if r.rows else "-"
        last = r.rows[-1][0].isoformat() if r.rows else "-"
        source = ", ".join(f"{t} {n}" for t, n in r.by_ticker)
        lines.append(
            f"{r.series:<6} {r.unit:<8} {len(r.rows):>5}  {first:<10}  {last:<10}  {share:>15}  "
            f"{r.off_session:>11} {r.outside:>7} {r.no_close:>8}  {source}"
        )
    for r in reports:
        if len(r.by_ticker) < 2:
            continue
        preferred, *others = (t for t, _ in r.by_ticker)
        head = f"{r.series}: {preferred} wherever it has a close, else {', '.join(others)}"
        if r.overlap:
            lines.append(
                f"{head}; on the {r.overlap} sessions both have, they differ on {r.differ}, by at "
                f"most {r.max_diff} ({r.max_diff_date.isoformat()})"
            )
        else:
            lines.append(f"{head}; they never overlap in this window")
    lines.append(f"{sum(len(r.rows) for r in reports)} rows in {len(reports)} series")
    return "\n".join(lines)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--refresh", action="store_true", help="write market_series.csv into the store")
    p.add_argument(
        "--store", type=Path, default=None, help=f"store directory (default {research.STORE_DIR})"
    )
    p.add_argument("--cache", type=Path, default=CACHE_DIR, help=f"EODHD market cache (default {CACHE_DIR})")


def run(args: argparse.Namespace) -> int:
    store = Path(args.store) if args.store else research.STORE_DIR
    cache = Path(args.cache)
    dry_run = bool(getattr(args, "dry_run", False))
    try:
        window = research.declared_window(store)
    except ValueError as exc:
        print(f"market_series: {exc}")
        return 2
    try:
        raw = {t: read_ticker(cache, t) for s in SOURCES for t in s.tickers}
    except CacheError as exc:
        print(f"market_series: {exc}")
        return 2
    reports = tuple(normalize(s, raw, window) for s in SOURCES)
    members = dates.sessions(max(window.start, research.MEMBERSHIP_START), window.end)
    print(format_report(reports, cache=cache, store=store, window=window, members=members))
    if not args.refresh:
        return 0
    empty = [r.series for r in reports if not r.rows]
    if empty:
        print(f"market_series: no rows in the window for {', '.join(empty)}; nothing written")
        return 2
    rows = rows_for_store(reports)
    if dry_run:
        print(f"dry run: would write {len(rows)} rows to {store / research.MARKET_SERIES_FILE}")
        return 0
    before = json.loads((store / research.MANIFEST_FILE).read_text(encoding="utf-8"))
    try:
        manifest = research.refresh_market_series(store, rows, window=window)
    except (research.ResearchStoreError, ValueError) as exc:
        print(f"market_series: {exc}")
        return 2
    price_before = research.price_fingerprint_of(before["files"])
    price_after = research.price_fingerprint_of(manifest["files"])
    print(
        f"wrote {len(rows)} rows ({len(reports)} series) into {store}; fingerprint "
        f"{before['fingerprint']} -> {manifest['fingerprint']}; price fingerprint "
        f"{price_after} ({'unchanged' if price_after == price_before else 'CHANGED from ' + price_before}); "
        f"purpose {manifest.get('purpose', '-')}"
    )
    return 0 if price_after == price_before else 2
