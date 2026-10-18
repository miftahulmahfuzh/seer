"""The research store's two size files: ``shares.csv`` and ``splits.csv``. Pure.

Company size on day t is ``shares x the close as it printed on t``. Both halves have to be in the
store, fingerprinted, for a lab trial that ranks on size to be reproducible: the share history
(``engine/data/shares_outstanding_pre2009.csv`` and ``shares_xbrl_classes.csv`` joined to the
store's XBRL facts through the date-scoped ticker map and attributed to each listed class through
``share_classes.csv``, ``history.SharesHistory``) and the split list that turns the store's
split-adjusted closes back into printed ones (``splits`` module docstring).

``shares.csv`` -- ``symbol,from,shares,counted,filed,source,accession``, sorted by symbol then
``from``. **Change points, not filings:** each row is the answer ``SharesHistory.shares_on`` gives
from ``from`` until the symbol's next row, with ``shares`` (and the rest) empty where the answer is
"unknown" (no figure filed yet, the newest one older than 400 days, or no filer behind the ticker
that day). Writing the resolved answers instead of the raw filings is what lets the reader be a
bisect: the join rule (later filing wins; a same-day tie goes to the per-class reading, then the
companyfacts tag), the ticker-to-filer map, the class table and the age limit are applied once,
here, and a store reader can never apply them differently. The rows are exact, not sampled:
``shares_on``'s answer can only change on a filing date, a ticker-map boundary or the day a figure
ages out -- the class table is keyed on each figure's own count date, so it adds no day of its
own -- and :func:`change_points` evaluates it on every one of those days
(``tests/test_shares_store.py`` checks it against a day-by-day evaluation). ``from >= filed`` on
every row: nothing is readable before it was public.

``splits.csv`` -- ``symbol,date,ratio``, sorted by symbol then date. The splits the vendor applied
to the store's adjusted closes, each effective from its ex-date, inside ``STORE_START..window end``;
plus, per symbol with any, **one undated row** (``date`` empty) holding the product of the splits
it applied after the window ended and up to the day the bars were downloaded. That row is the
price of keeping D9 -- no row of the store is dated after its window -- while still being able to
undo an adjustment Yahoo made in 2020 to a 2015 close. It is read only by
``ShareCounts.raw_factor``.

The shares are the same for every store that shares a membership (dev and survivorship-check: the
survivorship build copies the file byte for byte); the splits are the store's own, because they
describe its own bars.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from seer_engine import cik as cikmod
from seer_engine.backtest.market import ShareCount, ShareCounts
from seer_engine.shares import class_table, history

SHARES_HEADER = "symbol,from,shares,counted,filed,source,accession"
SPLITS_HEADER = "symbol,date,ratio"
SOURCES = (history.SOURCE_COVER, history.SOURCE_XBRL, history.SOURCE_XBRL_CLASS)


@dataclass(frozen=True)
class ShareLine:
    """One change point: the answer from ``start`` on (``obs`` None: unknown)."""

    symbol: str
    start: date
    obs: history.Observation | None


def _key(obs: history.Observation | None) -> tuple | None:
    if obs is None:
        return None
    return (obs.shares, obs.as_of or obs.filed, obs.filed, obs.source, obs.accession)


def _candidates(
    hist: history.SharesHistory, symbol: str, start: date, end: date
) -> list[date]:
    """Every day ``hist.shares_on(symbol, .)`` can change on, inside ``[start, end]``."""
    days: set[date] = {start}
    tenures = hist.index.get(symbol, ())
    for row in tenures:
        days.add(row.start_date)
        if row.end_date is not None:
            days.add(row.end_date)
    figures: list[tuple[date, date]] = []  # (filed, counted)
    for row in tenures:
        if row.cik is None:
            continue
        for r in hist._rows.get(row.cik, ()):
            figures.append((r.filed, r.as_of or r.filed))
        for k in hist._class_rows.get(row.cik, ()):
            figures.append((k.filed, k.as_of or k.filed))
    for x in hist._xbrl.get(symbol, ()):
        figures.append((x.filed, x.period_end))
    for filed, counted in figures:
        days.add(filed)
        if hist.max_age_days is not None:
            days.add(date.fromordinal(counted.toordinal() + hist.max_age_days + 1))
    return sorted(d for d in days if start <= d <= end)


def change_points(
    hist: history.SharesHistory, symbols: Iterable[str], start: date, end: date
) -> list[ShareLine]:
    """``hist.shares_on`` for each symbol over ``[start, end]``, as change points (module docstring).

    A symbol's first row is its first known answer; "unknown" before it is implicit, so a symbol
    that is never known has no row at all.
    """
    out: list[ShareLine] = []
    for symbol in sorted(set(symbols)):
        prev: tuple | None = None
        started = False
        for d in _candidates(hist, symbol, start, end):
            obs = hist.shares_on(symbol, d)
            k = _key(obs)
            if not started:
                if obs is None:
                    continue
                started = True
            elif k == prev:
                continue
            out.append(ShareLine(symbol, d, obs))
            prev = k
    return out


def _num(x: float) -> str:
    """A positive float as short exact text: integers without a trailing ``.0``."""
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def shares_lines(rows: Sequence[ShareLine]) -> list[str]:
    """``shares.csv``'s data lines (sorted, deterministic)."""
    lines = []
    for r in sorted(rows, key=lambda r: (r.symbol, r.start)):
        if r.obs is None:
            lines.append(f"{r.symbol},{r.start.isoformat()},,,,,")
            continue
        o = r.obs
        if o.filed > r.start:
            raise ValueError(f"{r.symbol} {r.start}: a figure filed {o.filed} read before it was public")
        lines.append(
            f"{r.symbol},{r.start.isoformat()},{_num(o.shares)},{(o.as_of or o.filed).isoformat()},"
            f"{o.filed.isoformat()},{o.source},{o.accession}"
        )
    return lines


def split_lines(
    splits: Mapping[str, Sequence[history.SplitLike]],
    *,
    store_start: date,
    window_end: date,
    basis: date,
) -> list[str]:
    """``splits.csv``'s data lines. Per symbol: the splits in ``(store_start, window_end]`` dated,
    then the product of those in ``(window_end, basis]`` as one undated row (omitted when there
    are none). A split before ``store_start`` adjusts no stored price and one after ``basis`` had
    not happened when the bars were downloaded; both are left out."""
    if basis < window_end:
        raise ValueError(f"the adjustment basis {basis} is before the window end {window_end}")
    lines: list[str] = []
    for symbol in sorted(splits):
        dated: dict[date, float] = {}
        after = 1.0
        for s in splits[symbol]:
            ratio = float(s.ratio)
            if not (math.isfinite(ratio) and ratio > 0):
                raise ValueError(f"{symbol} {s.date}: split ratio must be positive, got {s.ratio!r}")
            if store_start < s.date <= window_end:
                dated[s.date] = dated.get(s.date, 1.0) * ratio
            elif window_end < s.date <= basis:
                after *= ratio
        lines.extend(f"{symbol},{d.isoformat()},{dated[d]!r}" for d in sorted(dated) if dated[d] != 1.0)
        if after != 1.0:
            lines.append(f"{symbol},,{after!r}")
    return lines


#: A foreign private issuer's annual and interim reports state its ORDINARY shares, while the
#: index member is its American depositary share (NetEase: 3.29 billion ordinary shares, 25 to
#: an ADS), so the count times the ADS price is the company 25 times over. Their figures are not
#: used; a 10-K/10-Q filer's are.
FOREIGN_FORMS = frozenset({"20-F", "20-F/A", "40-F", "40-F/A", "6-K", "6-K/A"})
#: A figure this many times above or below the median of the company's other figures filed within
#: :data:`SCALE_WINDOW_DAYS` is a filer's unit error, not a share count (Yum! Brands' 10-Q of
#: 2016-10-11 tags 367,005,511,000,000; Garmin's 2016 10-Qs tag 208,077,418,000). No split or
#: issuance moves a count fifty-fold within two years.
SCALE_LIMIT = 50.0
SCALE_WINDOW_DAYS = 730


def usable_xbrl(facts: Iterable) -> tuple[list, dict[str, list]]:
    """``(kept, dropped)``: the store's XBRL share facts less foreign issuers' and unit errors.

    ``facts`` are ``fundamentals.Fact``-shaped (``symbol``, ``tag``, ``val``, ``filed``, ``form``).
    ``dropped`` maps a reason to the facts dropped for it, so the caller can say what it left out.
    The cover-page rows before 2009 went through ``shares.checks``; these are the same figures'
    tagged form and had no such pass until here.
    """
    import bisect
    import statistics

    dropped: dict[str, list] = {"foreign filer": [], "unit error": []}
    domestic = []
    for f in facts:
        if getattr(f, "form", "") in FOREIGN_FORMS:
            dropped["foreign filer"].append(f)
        else:
            domestic.append(f)
    by: dict[str, list] = {}
    for f in domestic:
        if f.tag in history.XBRL_TAGS and math.isfinite(f.val) and f.val > 0:
            by.setdefault(f.symbol, []).append(f)
    bad: set[int] = set()
    for group in by.values():
        group.sort(key=lambda f: f.filed)
        days = [f.filed.toordinal() for f in group]
        for i, f in enumerate(group):
            lo = bisect.bisect_left(days, days[i] - SCALE_WINDOW_DAYS)
            hi = bisect.bisect_right(days, days[i] + SCALE_WINDOW_DAYS)
            others = [g.val for j, g in enumerate(group[lo:hi], start=lo) if j != i]
            if len(others) < 2:
                continue
            ratio = f.val / statistics.median(others)
            if ratio >= SCALE_LIMIT or ratio <= 1.0 / SCALE_LIMIT:
                bad.add(id(f))
    kept = []
    for f in domestic:
        (dropped["unit error"] if id(f) in bad else kept).append(f)
    return kept, dropped


#: How far from a split's ex-date the closes either side of it may be to judge it (a week).
EVIDENCE_GAP_DAYS = 7
#: Only a split of at least this ratio (either way) is judged on the closes: a smaller one is the
#: size of an ordinary day's move -- or of a spin-off's real price drop the adjustment only partly
#: offsets (Lennar's 1.033 for Millrose, 2025) -- and one day's ratio cannot tell it from noise.
#: The nightly's split guard uses the same line (``docs/runbooks/data-pipeline.md``, Splits).
EVIDENCE_MIN_RATIO = 1.25


def applied_by_vendor(
    listed: Sequence[history.SplitLike],
    closes: Sequence[tuple[Sequence[date], Sequence[float]]],
) -> tuple[list[history.SplitLike], list[history.SplitLike]]:
    """``(applied, not applied)``: which of a vendor's listed splits its adjusted closes carry.

    Yahoo lists spin-offs as fractional "splits" (IBM's Kyndryl as 1.046 on 2021-11-04, GE's two
    as 1.281 and 1.253) and adjusts the closes for some of them and not others. Undoing an
    adjustment that was never made would misstate the printed price by the ratio, so each listed
    split is judged on the adjusted closes themselves -- ``closes`` is one or more ``(dates,
    closes)`` series of the same vendor, ascending, tried in order: across the ex-date an applied
    split leaves the series continuous, and one never applied shows the price falling by about its
    ratio. It counts as applied when ``|ln q|`` is smaller than ``|ln(q x ratio)|`` for the one-day
    ratio ``q`` (the mirror of ``survivorship.applied_splits``, which judges raw closes), when no
    series has a close within a week on both sides of it -- the list is then all there is -- and
    when its ratio is under :data:`EVIDENCE_MIN_RATIO` either way, too small to judge.
    """
    import bisect

    applied: list[history.SplitLike] = []
    dropped: list[history.SplitLike] = []
    for s in listed:
        verdict: bool | None = None
        if abs(math.log(float(s.ratio))) < math.log(EVIDENCE_MIN_RATIO):
            applied.append(s)
            continue
        for days, values in closes:
            i = bisect.bisect_left(days, s.date)
            if i == 0 or i == len(days):
                continue
            before, after = days[i - 1], days[i]
            if (s.date - before).days > EVIDENCE_GAP_DAYS or (after - s.date).days > EVIDENCE_GAP_DAYS:
                continue
            q = values[i] / values[i - 1]
            if not (q > 0 and math.isfinite(q)):
                continue
            verdict = abs(math.log(q)) < abs(math.log(q * float(s.ratio)))
            break
        (applied if verdict is not False else dropped).append(s)
    return applied, dropped


# --- readers ----------------------------------------------------------------------------


def _lines(path: Path, header: str) -> list[tuple[int, str]]:
    raw = path.read_bytes()
    if b"\r" in raw:
        raise ValueError(f"{path.name}: expected header {header!r} and LF-terminated lines")
    text = raw.decode("utf-8")
    lines = text.split("\n")
    if not text.endswith("\n") or lines[0] != header:
        raise ValueError(f"{path.name}: expected header {header!r} and LF-terminated lines")
    out = list(enumerate(lines[1:-1], start=2))
    for n, line in out:
        if not line:
            raise ValueError(f"{path.name}:{n}: empty line")
    return out


def _day(raw: str, where: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{where}: bad date {raw!r}") from exc


def _positive(raw: str, where: str) -> float:
    try:
        x = float(raw)
    except ValueError as exc:
        raise ValueError(f"{where}: bad number {raw!r}") from exc
    if not (math.isfinite(x) and x > 0):
        raise ValueError(f"{where}: {raw!r} must be a positive number")
    return x


def read_shares(path: Path, end: date) -> dict[str, list[tuple[date, ShareCount | None]]]:
    """``shares.csv`` as ``symbol -> [(from, ShareCount | None)]``. Strict: sorted, no row dated
    after ``end`` (D9), every figure public by its ``from`` day, a known source."""
    out: dict[str, list[tuple[date, ShareCount | None]]] = {}
    prev: tuple[str, date] | None = None
    for n, line in _lines(path, SHARES_HEADER):
        where = f"{path.name}:{n}"
        f = line.split(",")
        if len(f) != 7:
            raise ValueError(f"{where}: expected 7 fields, got {len(f)}")
        symbol, raw_from, raw_shares, raw_counted, raw_filed, source, accession = f
        start = _day(raw_from, where)
        if start > end:
            raise ValueError(f"{where}: a {symbol} share row dated {start} is after the window end {end} (D9)")
        if prev is not None and (symbol, start) <= prev:
            raise ValueError(f"{where}: rows must be sorted by symbol then date, each date once")
        prev = (symbol, start)
        if not raw_shares:
            if raw_counted or raw_filed or source or accession:
                raise ValueError(f"{where}: an unknown row must leave every other field empty")
            out.setdefault(symbol, []).append((start, None))
            continue
        filed = _day(raw_filed, where)
        if filed > start:
            raise ValueError(f"{where}: {symbol} filed {filed}, read from {start} (look-ahead)")
        if source not in SOURCES:
            raise ValueError(f"{where}: unknown source {source!r}")
        count = ShareCount(_positive(raw_shares, where), _day(raw_counted, where), filed, source)
        out.setdefault(symbol, []).append((start, count))
    return out


def read_splits(path: Path, start: date, end: date) -> dict[str, tuple[list[tuple[date, float]], float]]:
    """``splits.csv`` as ``symbol -> (dated splits, after-window product)``. Strict: dated rows in
    ``(start, end]`` (D9), sorted, one undated row per symbol at most, after its dated rows."""
    out: dict[str, tuple[list[tuple[date, float]], float]] = {}
    prev: tuple[str, date] | None = None
    closed: set[str] = set()
    for n, line in _lines(path, SPLITS_HEADER):
        where = f"{path.name}:{n}"
        f = line.split(",")
        if len(f) != 3:
            raise ValueError(f"{where}: expected 3 fields, got {len(f)}")
        symbol, raw_day, raw_ratio = f
        ratio = _positive(raw_ratio, where)
        if symbol in closed:
            raise ValueError(f"{where}: {symbol} has a row after its undated (after-window) row")
        dated, after = out.get(symbol, ([], 1.0))
        if not raw_day:
            closed.add(symbol)
            out[symbol] = (dated, ratio)
            continue
        d = _day(raw_day, where)
        if d > end:
            raise ValueError(f"{where}: a {symbol} split dated {d} is after the window end {end} (D9)")
        if d <= start:
            raise ValueError(f"{where}: a {symbol} split dated {d} adjusts no stored price")
        if prev is not None and (symbol, d) <= prev:
            raise ValueError(f"{where}: rows must be sorted by symbol then date, each date once")
        prev = (symbol, d)
        dated.append((d, ratio))
        out[symbol] = (dated, after)
    return out


def load_counts(shares_path: Path | None, splits_path: Path | None, start: date, end: date) -> ShareCounts:
    """A ``ShareCounts`` from the two files (either may be absent)."""
    rows = read_shares(shares_path, end) if shares_path is not None else {}
    splits = read_splits(splits_path, start, end) if splits_path is not None else {}
    return ShareCounts(rows, splits)


def history_for(
    xbrl: Iterable[history.XbrlFact],
    data_dir: Path = history.DATA_DIR,
    *,
    class_rows: Iterable[history.ClassReading] = (),
) -> history.SharesHistory:
    """The vendored cover rows, ticker map and class table joined to ``xbrl`` and the per-class
    rows, at the default age limit."""
    return history.SharesHistory(
        history.load_rows(data_dir / history.SHARES_FILE),
        cikmod.load_index_with_history(data_dir),
        xbrl,
        class_rows=class_rows,
        table=class_table.load_table(data_dir / class_table.TABLE_FILE),
    )
