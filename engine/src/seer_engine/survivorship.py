"""The survivorship-check store's cleaning: EODHD series for the members the dev store never served.

Pure, apart from :func:`read_series`, which reads one symbol's cached EODHD answers (``eod/``,
``splits/`` and ``dividends/`` under ``engine/.cache/eodhd``) and nothing else -- no network, no
store, no database. ``commands/survivorship_store.py`` is the impure edge that writes the store.

**Why it exists.** ``engine/.research`` holds bars for 539 of the 1061 symbols it requested; the
other 522 are mostly companies that died (bankruptcies, buyouts, renamed tickers). Every lab
result was measured without them. The paid EODHD month downloaded their raw daily history, and
this module turns it into bars in the dev store's own conventions -- split-adjusted, not
dividend-adjusted, 4 dp, integer volume -- so a second, clearly marked store can say how much
the gap flattered the lab.

**The rules, in the order they run** (the constants below; each was calibrated on the real cache
on 2026-10-10 and the phase-1 plan records the measured counts):

1. *Invalid rows.* A close that is missing or not positive removes the row, and so does a
   zero-volume row whose open, high, low and close are one number: a filler carrying the last
   price forward, not a trade (58,705 of the 1,192,432 cached rows inside the dev window; CFC
   prints 60.00 for weeks in 2000). A missing or non-positive open, high or low becomes the close.
2. *Listed splits, checked one by one.* EODHD's "raw" prices are sometimes already adjusted for
   a split it lists (AVP 1998-09-14, BRCM 1999-02-18). A listed split is applied only when the
   raw close actually fell by about its ratio across its date -- when ``|ln(q * ratio)|`` is
   smaller than ``|ln(q)|`` for the raw one-day ratio ``q`` -- and skipped when the raw prices
   already carry it, or when no raw row lies on both sides of it. Decided on the whole raw
   series, so a split after 2015 is checked against the rows around it.
3. *Window.* Rows outside ``STORE_START..DEV_END`` and rows on a day that is not an NYSE
   session are dropped (D9: the dev store never holds a row after 2015-10-16).
4. *Splices (reused tickers).* The series is cut into segments at every hole of more than
   :data:`HOLE_SESSIONS` NYSE sessions. Every segment with a row inside the membership span
   (first to last member session) is the member company -- a ticker cannot be reused while its
   company is in the index -- and is kept, holes and all. A segment wholly outside that span
   sits across a long hole and may be another company under the same code (CTX after 2012, BSC
   after 2008-05, CGP, BGEN): it is cut and the symbol reads ``trimmed``. A symbol with no
   segment inside its span (IACI, JH) is ``dropped``.
5. *Tail.* The kept rows end :data:`TAIL_GRACE_SESSIONS` sessions after the last member
   session, so a book holding a company that leaves the index still exits at a real price, and
   a code reused later without a hole cannot leak in.
6. *Split adjustment.* Prices are divided, and volume multiplied, by the product of the applied
   splits dated after the row.
7. *Scale breaks.* A one-day move within :data:`CLOSE_TOL` of a simple ratio, whose open moved by
   the same ratio (:data:`OPEN_TOL`), that persists :data:`PERSIST_ROWS` rows on both sides and
   whose volume moved inversely (:data:`VOLUME_TOL`) is a split EODHD neither lists nor applied
   correctly (BCR 2003-09-10): the rows before it are rescaled. A crash fails the open test --
   CVH 2008-10-22 opened 36% down and closed 51% down -- so it is never "repaired" away.
8. *Spikes.* A run of at most :data:`SPIKE_MAX_ROWS` rows that moves beyond :data:`JUMP` from the
   last good close and comes back within :data:`SPIKE_BACK` of it is a data error (CFC's
   alternating 1/12-scale rows): the rows are removed.
9. *Islands.* Two consecutive persistent moves beyond :data:`JUMP` whose ratios cancel to within
   :data:`ISLAND_TOL`, at most :data:`ISLAND_MAX_ROWS` rows apart, bracket a stretch the vendor
   printed at the wrong scale (CERN 1993-12-22..1994-12-21 at 15x): the stretch is rescaled
   so both edges carry the same small residual move.
10. *What is left.* Each remaining move beyond :data:`JUMP` is **genuine** when the volume on
   its day or the next is at least :data:`SURGE_MIN` times the median of the
   :data:`SURGE_ROWS` rows before, or when it is a fall within :data:`TERMINAL_SESSIONS` sessions
   of the end of the membership or of the series -- that is what a collapse looks like (ENRNQ
   2001-11-28, WAMUQ 2008-09-26, CVH 2008-10-22), and it stays: dropping it would bring
   survivorship bias back by the side door. Any other such move is **suspect** (no volume
   behind it: a vendor level error, EA 2003-11-18 x0.118). A suspect move before the membership
   span cuts the rows before it; one after the span cuts the rows from it on; one inside the
   span is repaired by rescaling every row before it by the move, so the later prices stand as
   printed and no return but that one day's changes. More than :data:`ABSURD_MAX_MOVES` suspect
   moves inside the span, or more than that many genuine ones, drops the symbol: that is not a
   company's price history (FBF).
11. *Bars the loader would refuse.* After rounding to 4 dp a close of 0.0000 removes the row; an
   open, high or low of 0.0000 becomes the close; high and low are widened to contain open and
   close, and a wick beyond :data:`WICK` times the body is cut back to the body.

Dividends come from ``dividends/<SYM>.json``'s ``value`` -- EODHD's split-adjusted amount: on the
28,008 dev-store dividends with a same-day EODHD row, 97.5% agree within 1% -- USD only, clipped
to the kept bars, refused when one payment exceeds :data:`MAX_DIVIDEND_YIELD` of the prior close.

**The seam for a second source** (phase 2's alias fill): :class:`SourceSeries` is source-agnostic,
:func:`clean_symbol` takes one, and :func:`best_of` picks among several cleaned candidates for one
symbol the one covering the most member days.
"""

from __future__ import annotations

import json
import math
import statistics
from bisect import bisect_left
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from seer_engine import research
from seer_engine.bars import to_volume
from seer_engine.prices import to_decimal
from seer_engine.yahoo import DIVIDEND_QUANTUM

EODHD_SOURCE = "eodhd"

HOLE_SESSIONS = 10
TAIL_GRACE_SESSIONS = 21
JUMP = 2.0
SCALE_MIN = 1.4
SIMPLE_RATIOS: tuple[float, ...] = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 20.0)
CLOSE_TOL = 0.05
OPEN_TOL = 0.05
PERSIST_ROWS = 5
PERSIST_TOL = 0.15
VOLUME_TOL = 3.0
SPIKE_MAX_ROWS = 5
SPIKE_BACK = 1.33
ISLAND_TOL = 1.25
ISLAND_MAX_ROWS = 1300
SURGE_MIN = 2.0
SURGE_ROWS = 20
TERMINAL_SESSIONS = 63
ABSURD_MAX_MOVES = 3
WICK = Decimal(3)
MAX_DIVIDEND_YIELD = Decimal("0.25")

KEPT = "kept"
REPAIRED = "repaired"
TRIMMED = "trimmed"
DROPPED = "dropped"
ACTIONS: tuple[str, ...] = (KEPT, REPAIRED, TRIMMED, DROPPED)

ZERO_PRICE = Decimal("0.0000")
REPORT_HEADER = (
    "symbol,source,code,action,member_days,covered_days,first,last,rows,raw_rows,"
    "splits_applied,splits_skipped,scale_repairs,island_repairs,level_repairs,rows_removed,fields_repaired,"
    "moves_kept,dividends,dividends_refused,reason"
)


# ---- value types ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawBar:
    """One vendor row, raw (not split-adjusted). Any price may be None or non-positive."""

    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None


@dataclass(frozen=True)
class Split:
    """A listed split: ``ratio`` new shares per old (2.0 for 2-for-1, 0.1 for 1-for-10)."""

    date: date
    ratio: float


@dataclass(frozen=True)
class RawDividend:
    ex_date: date
    value: Decimal | None  # split-adjusted, as the vendor reports it
    currency: str | None


@dataclass(frozen=True)
class SourceSeries:
    """Everything one source knows about one store symbol. Source-agnostic on purpose."""

    symbol: str  # the store's symbol (``BRK.B``), never the vendor's code
    source: str  # ``eodhd``; phase 2 adds its alias source
    code: str  # the vendor code the rows were fetched under (``BRK-B.US``)
    bars: tuple[RawBar, ...]
    splits: tuple[Split, ...] = ()
    dividends: tuple[RawDividend, ...] = ()


@dataclass(frozen=True)
class CleanBar:
    date: date
    open: Decimal  # 4 dp
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class Cleaned:
    """One symbol after cleaning: what goes into the store and what the report says about it."""

    symbol: str
    source: str
    code: str
    action: str  # one of ACTIONS
    reason: str  # plain words, never empty, no commas
    member_days: int = 0
    raw_rows: int = 0
    bars: tuple[CleanBar, ...] = ()
    dividends: tuple[tuple[date, Decimal], ...] = ()
    covered_days: int = 0
    splits_applied: int = 0
    splits_skipped: int = 0
    scale_repairs: int = 0
    island_repairs: int = 0
    level_repairs: int = 0
    rows_removed: int = 0
    fields_repaired: int = 0
    moves_kept: int = 0
    dividends_refused: int = 0

    @property
    def first(self) -> date | None:
        return self.bars[0].date if self.bars else None

    @property
    def last(self) -> date | None:
        return self.bars[-1].date if self.bars else None

    def report_line(self) -> str:
        """This symbol's ``cleaning_report.csv`` row (:data:`REPORT_HEADER` order)."""
        cells = (
            self.symbol, self.source, self.code, self.action, self.member_days,
            self.covered_days, self.first or "", self.last or "", len(self.bars), self.raw_rows,
            self.splits_applied, self.splits_skipped, self.scale_repairs, self.island_repairs,
            self.level_repairs,
            self.rows_removed, self.fields_repaired, self.moves_kept, len(self.dividends),
            self.dividends_refused, report_text(self.reason),
        )
        return ",".join(str(c) for c in cells)


@dataclass(frozen=True)
class YearCoverage:
    """Member-days in one calendar year, and how many of them have a bar before and after."""

    year: int
    member_days: int
    before: int
    after: int


# ---- reading the cache ---------------------------------------------------------------------


def parse_split(text: object) -> float:
    """``"2.000000/1.000000"`` -> 2.0 (new shares per old). ValueError on anything else."""
    new, sep, old = str(text).partition("/")
    try:
        ratio = float(new) / float(old) if sep else float("nan")
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"not a split ratio: {text!r}") from exc
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError(f"not a split ratio: {text!r}")
    return ratio


def _number(raw: object) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _decimal(raw: object) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _day(raw: object) -> date | None:
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def parse_bars(rows: object) -> tuple[RawBar, ...]:
    """EODHD ``/eod`` JSON (a list of dicts, or None) as RawBars, ascending, one per date."""
    if not isinstance(rows, list):
        return ()
    by_date: dict[date, RawBar] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        d = _day(raw.get("date"))
        if d is None:
            continue
        by_date[d] = RawBar(
            date=d,
            open=_number(raw.get("open")),
            high=_number(raw.get("high")),
            low=_number(raw.get("low")),
            close=_number(raw.get("close")),
            volume=_number(raw.get("volume")),
        )
    return tuple(by_date[d] for d in sorted(by_date))


def parse_splits(rows: object) -> tuple[Split, ...]:
    """EODHD ``/splits`` JSON (a list, or None) as Splits, ascending; unparsable rows skipped."""
    if not isinstance(rows, list):
        return ()
    out: list[Split] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        d = _day(raw.get("date"))
        try:
            ratio = parse_split(raw.get("split", ""))
        except ValueError:
            continue
        if d is not None:
            out.append(Split(d, ratio))
    return tuple(sorted(out, key=lambda s: s.date))


def parse_dividend_rows(rows: object) -> tuple[RawDividend, ...]:
    """The ``rows`` of a cached ``dividends/<SYM>.json`` as RawDividends, ascending."""
    if not isinstance(rows, list):
        return ()
    out: list[RawDividend] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        d = _day(raw.get("date"))
        if d is None:
            continue
        currency = raw.get("currency")
        out.append(RawDividend(d, _decimal(raw.get("value")), currency if isinstance(currency, str) else None))
    return tuple(sorted(out, key=lambda r: r.ex_date))


def eodhd_code(symbol: str) -> str:
    """The store symbol in EODHD form (``BRK.B`` -> ``BRK-B.US``); same rule as ``eodhd.ticker``."""
    return symbol.strip().upper().replace(".", "-") + ".US"


def read_series(cache: Path, symbol: str) -> SourceSeries | None:
    """The cached EODHD answers for ``symbol``; None when ``eod/<symbol>.json`` was never fetched.

    A fetched-but-404 symbol (its file holds ``null``) is a SourceSeries with no bars, so the
    report can say "EODHD has no series" rather than "never fetched".
    """
    cache = Path(cache)
    eod_path = cache / "eod" / f"{symbol}.json"
    if not eod_path.is_file():
        return None
    div_doc = _load_json(cache / "dividends" / f"{symbol}.json")
    return SourceSeries(
        symbol=symbol,
        source=EODHD_SOURCE,
        code=eodhd_code(symbol),
        bars=parse_bars(_load_json(eod_path)),
        splits=parse_splits(_load_json(cache / "splits" / f"{symbol}.json")),
        dividends=parse_dividend_rows(div_doc.get("rows") if isinstance(div_doc, dict) else None),
    )


# ---- membership and sessions ---------------------------------------------------------------


def member_sessions(
    intervals: Iterable[tuple[str, date, date | None]], symbol: str, sessions: Sequence[date]
) -> tuple[date, ...]:
    """The sessions in ``sessions`` on which ``symbol`` is a member: ``start <= d < end``."""
    days: set[date] = set()
    for s, start, end in intervals:
        if s != symbol:
            continue
        lo = bisect_left(sessions, start)
        hi = len(sessions) if end is None else bisect_left(sessions, end)
        days.update(sessions[lo:hi])
    return tuple(sorted(days))


# ---- cleaning ------------------------------------------------------------------------------


def report_text(reason: str) -> str:
    """A report cell: no commas (the report CSVs are unquoted), never empty."""
    return reason.replace(",", ";").replace("\n", " ").strip() or "-"


def _near(q: float, k: float, tol: float) -> bool:
    return abs(q / k - 1.0) <= tol


def _simple_ratio(q: float) -> float | None:
    """The simple ratio (or its inverse) within CLOSE_TOL of ``q``, else None."""
    for k in SIMPLE_RATIOS:
        for r in (k, 1.0 / k):
            if _near(q, r, CLOSE_TOL):
                return r
    return None


@dataclass
class _Rows:
    """Mutable working columns for one symbol: floats, volume included, until rounding."""

    dates: list[date]
    o: list[float]
    h: list[float]
    lo: list[float]
    c: list[float]
    v: list[float]

    def take(self, keep: Iterable[int]) -> None:
        keep = list(keep)
        for name in ("dates", "o", "h", "lo", "c", "v"):
            column = getattr(self, name)
            setattr(self, name, [column[i] for i in keep])

    def scale(self, lo: int, hi: int, price: float, volume: float = 1.0) -> None:
        """Multiply prices of rows ``lo..hi-1`` by ``price`` and their volume by ``volume``."""
        for j in range(lo, hi):
            self.o[j] *= price
            self.h[j] *= price
            self.lo[j] *= price
            self.c[j] *= price
            self.v[j] *= volume

    def __len__(self) -> int:
        return len(self.dates)


def _invalid(b: RawBar) -> bool:
    """Rule 1's removals: no positive close, or a zero-volume filler at one price."""
    if b.close is None or b.close <= 0:
        return True
    return not b.volume and b.open == b.high == b.low == b.close


def _valid_rows(bars: Sequence[RawBar]) -> tuple[_Rows, int]:
    """Rule 1: (the rows that are not :func:`_invalid`, open/high/low values repaired)."""
    rows = _Rows([], [], [], [], [], [])
    repaired = 0
    for b in bars:
        if _invalid(b):
            continue
        parts = (b.open, b.high, b.low)
        fixed = [x if x is not None and x > 0 else b.close for x in parts]
        repaired += sum(1 for x in parts if x is None or x <= 0)
        rows.dates.append(b.date)
        rows.o.append(fixed[0])
        rows.h.append(fixed[1])
        rows.lo.append(fixed[2])
        rows.c.append(b.close)
        rows.v.append(b.volume if b.volume is not None and b.volume > 0 else 0.0)
    return rows, repaired


def applied_splits(rows: _Rows, splits: Sequence[Split]) -> tuple[tuple[Split, ...], tuple[Split, ...]]:
    """Rule 2: (splits to apply, splits skipped), judged on the raw closes around each date."""
    applied: list[Split] = []
    skipped: list[Split] = []
    for s in splits:
        j = bisect_left(rows.dates, s.date)
        if j == 0 or j >= len(rows):
            skipped.append(s)
            continue
        q = rows.c[j] / rows.c[j - 1]
        (applied if abs(math.log(q * s.ratio)) < abs(math.log(q)) else skipped).append(s)
    return tuple(applied), tuple(skipped)


def _scale_break(rows: _Rows, i: int) -> float | None:
    """Rule 7: the factor to rescale the rows before ``i`` by, or None."""
    prev, cur = rows.c[i - 1], rows.c[i]
    q = cur / prev
    if max(q, 1.0 / q) < SCALE_MIN:
        return None
    k = _simple_ratio(q)
    if k is None or not _near(rows.o[i] / prev, k, OPEN_TOL):
        return None
    if i < PERSIST_ROWS or i + PERSIST_ROWS > len(rows):
        return None
    if not _near(statistics.median(rows.c[i - PERSIST_ROWS : i]), prev, PERSIST_TOL):
        return None
    if not _near(statistics.median(rows.c[i : i + PERSIST_ROWS]), cur, PERSIST_TOL):
        return None
    vb = statistics.median(rows.v[i - PERSIST_ROWS : i])
    va = statistics.median(rows.v[i : i + PERSIST_ROWS])
    if vb > 0 and va > 0 and not 1.0 / VOLUME_TOL <= (va / vb) * k <= VOLUME_TOL:
        return None
    return k


def _surge(rows: _Rows, i: int) -> float:
    """Volume on day ``i`` (or the next) over the median of the SURGE_ROWS rows before; 0 if unknown."""
    before = [v for v in rows.v[max(0, i - SURGE_ROWS) : i] if v > 0]
    if not before:
        return 0.0
    day = max(rows.v[i], rows.v[i + 1] if i + 1 < len(rows) else 0.0)
    return day / statistics.median(before)


def _moves(rows: _Rows) -> list[tuple[int, float]]:
    """Every (row, ratio) whose close moved beyond JUMP from the row before."""
    out = []
    for i in range(1, len(rows)):
        q = rows.c[i] / rows.c[i - 1]
        if max(q, 1.0 / q) > JUMP:
            out.append((i, q))
    return out


def clean_symbol(
    series: SourceSeries,
    member_days: Sequence[date],
    sessions: Sequence[date],
) -> Cleaned:
    """Clean one symbol's series against its membership (the module docstring's rules, in order).

    ``member_days`` are the dev-window sessions the symbol was an index member, ascending;
    ``sessions`` are every NYSE session ``STORE_START..DEV_END``, ascending. Never raises on bad
    vendor data: every outcome is a :class:`Cleaned` with an action and a reason.
    """
    head = dict(
        symbol=series.symbol, source=series.source, code=series.code,
        member_days=len(member_days), raw_rows=len(series.bars),
    )
    src = series.source
    if not member_days:
        return Cleaned(**head, action=DROPPED, reason="never an index member in the dev window")
    if not series.bars:
        return Cleaned(**head, action=DROPPED, reason=f"{src} has no daily series for {series.code}")
    index = {d: i for i, d in enumerate(sessions)}
    notes: list[str] = []

    # 1. invalid rows; 2. which listed splits the raw prices still need
    rows, fields = _valid_rows(series.bars)
    removed = sum(
        1 for b in series.bars
        if _invalid(b) and research.STORE_START <= b.date <= research.DEV_END
    )
    if not rows:
        return Cleaned(**head, action=DROPPED, reason=f"no {src} row has a positive close")
    use, skip = applied_splits(rows, series.splits)
    if skip:
        notes.append(f"{len(skip)} listed splits not applied (already in the raw prices or outside the series)")

    # 3. window and sessions
    raw_first, raw_last = rows.dates[0], rows.dates[-1]
    keep = [i for i, d in enumerate(rows.dates) if d in index]
    removed += sum(1 for d in rows.dates if research.STORE_START <= d <= research.DEV_END and d not in index)
    rows.take(keep)
    if not rows:
        return Cleaned(
            **head, action=DROPPED,
            reason=(
                f"{src} series {raw_first}..{raw_last} has no session inside "
                f"{research.STORE_START}..{research.DEV_END}"
            ),
        )

    # 4. splices
    m_first, m_last = member_days[0], member_days[-1]
    cuts = [0] + [
        i for i in range(1, len(rows))
        if index[rows.dates[i]] - index[rows.dates[i - 1]] - 1 > HOLE_SESSIONS
    ] + [len(rows)]
    touching = [
        (a, b) for a, b in zip(cuts[:-1], cuts[1:])
        if any(m_first <= rows.dates[j] <= m_last for j in range(a, b))
    ]
    if not touching:
        return Cleaned(
            **head, action=DROPPED,
            reason=(
                f"{src} series {rows.dates[0]}..{rows.dates[-1]} never trades inside the membership "
                f"{m_first}..{m_last}: another company under the same ticker"
            ),
        )
    lo_i, hi_i = touching[0][0], touching[-1][1]
    trimmed = False
    if lo_i > 0:
        trimmed = True
        notes.append(
            f"cut {lo_i} rows {rows.dates[0]}..{rows.dates[lo_i - 1]} across a hole of "
            f"{index[rows.dates[lo_i]] - index[rows.dates[lo_i - 1]] - 1} sessions before the membership"
        )
    if hi_i < len(rows):
        trimmed = True
        notes.append(
            f"cut {len(rows) - hi_i} rows {rows.dates[hi_i]}..{rows.dates[-1]} across a hole of "
            f"{index[rows.dates[hi_i]] - index[rows.dates[hi_i - 1]] - 1} sessions after the membership"
        )
    rows.take(range(lo_i, hi_i))

    # 5. tail
    tail_end = sessions[min(index[m_last] + TAIL_GRACE_SESSIONS, len(sessions) - 1)]
    rows.take(i for i, d in enumerate(rows.dates) if d <= tail_end)

    # 6. split adjustment
    for i, d in enumerate(rows.dates):
        f = math.prod(s.ratio for s in use if s.date > d)
        if f != 1.0:
            rows.scale(i, i + 1, 1.0 / f, f)

    # 7. scale breaks, latest first: rescaling the rows before i never changes an earlier ratio
    breaks = 0
    for i in range(len(rows) - 1, 0, -1):
        k = _scale_break(rows, i)
        if k is not None:
            rows.scale(0, i, k, 1.0 / k)
            breaks += 1
            notes.append(f"rescaled rows before {rows.dates[i]} by {k:g} (a split nobody applied)")

    # 8. spikes
    kept_rows = [0]
    spikes = 0
    i = 1
    while i < len(rows):
        g = kept_rows[-1]
        q = rows.c[i] / rows.c[g]
        if max(q, 1.0 / q) > JUMP:
            back = next(
                (j for j in range(i + 1, min(i + 1 + SPIKE_MAX_ROWS, len(rows)))
                 if 1.0 / SPIKE_BACK <= rows.c[j] / rows.c[g] <= SPIKE_BACK),
                None,
            )
            if back is not None:
                spikes += back - i
                i = back
                continue
        kept_rows.append(i)
        i += 1
    if spikes:
        notes.append(f"removed {spikes} spike rows that came straight back")
        removed += spikes
        rows.take(kept_rows)

    # 9. islands
    islands = 0
    changed = True
    while changed:
        changed = False
        moves = _moves(rows)
        for (a, qa), (b, qb) in zip(moves, moves[1:]):
            if b - a <= ISLAND_MAX_ROWS and abs(math.log(qa * qb)) <= math.log(ISLAND_TOL):
                f = math.sqrt(qb / qa)
                rows.scale(a, b, f)
                islands += 1
                notes.append(f"rescaled the stretch {rows.dates[a]}..{rows.dates[b - 1]} by {f:.4g} (printed at the wrong scale)")
                changed = True
                break

    # 10. what is left
    suspects: list[tuple[int, float]] = []
    genuine: list[tuple[int, float]] = []
    for i, q in _moves(rows):
        d = rows.dates[i]
        terminal = q < 1.0 and (
            index[m_last] - index[d] <= TERMINAL_SESSIONS or len(rows) - 1 - i <= TERMINAL_SESSIONS
        )
        (genuine if terminal or _surge(rows, i) >= SURGE_MIN else suspects).append((i, q))
    inside = [(i, q) for i, q in suspects if m_first <= rows.dates[i] <= m_last]
    if len(inside) > ABSURD_MAX_MOVES:
        listed = "; ".join(f"{rows.dates[i]} x{q:.3g}" for i, q in inside[:3])
        return Cleaned(
            **head, action=DROPPED,
            reason=(
                f"absurd: {len(inside)} one-day moves beyond {JUMP:g}x with no volume behind them "
                f"inside the membership (first {listed})"
            ),
            scale_repairs=breaks, island_repairs=islands, rows_removed=removed,
        )
    for i, q in sorted(inside, reverse=True):
        rows.scale(0, i, q)
        notes.append(
            f"rescaled rows before {rows.dates[i]} by {q:.4g}: a x{q:.3g} move with no volume behind it "
            "inside the membership (a vendor level error; the later prices are kept as printed)"
        )
    levels = len(inside)
    before = [i for i, _ in suspects if rows.dates[i] < m_first]
    after = [i for i, _ in suspects if rows.dates[i] > m_last]
    if before:
        cut = max(before)
        notes.append(f"cut {cut} rows before an unexplained move on {rows.dates[cut]} ahead of the membership")
        trimmed = True
    if after:
        cut = min(after)
        notes.append(f"cut {len(rows) - cut} rows from an unexplained move on {rows.dates[cut]} after the membership")
        trimmed = True
    lo_cut = max(before) if before else 0
    hi_cut = min(after) if after else len(rows)
    genuine_in = [(i, q) for i, q in genuine if lo_cut <= i < hi_cut and m_first <= rows.dates[i] <= m_last]
    if len(genuine_in) > ABSURD_MAX_MOVES:
        return Cleaned(
            **head, action=DROPPED,
            reason=(
                f"absurd: {len(genuine_in)} one-day moves beyond {JUMP:g}x inside the membership "
                f"(first {rows.dates[genuine_in[0][0]]})"
            ),
            scale_repairs=breaks, island_repairs=islands, rows_removed=removed,
        )
    moves_kept = [(i, q) for i, q in genuine if lo_cut <= i < hi_cut]
    if moves_kept:
        notes.append(
            f"kept {len(moves_kept)} one-day moves beyond {JUMP:g}x with volume behind them or at the "
            f"end ({'; '.join(f'{rows.dates[i]} x{q:.3g}' for i, q in moves_kept[:3])})"
        )
    rows.take(range(lo_cut, hi_cut))

    # 11. 4 dp and the bars the loader would refuse
    bars: list[CleanBar] = []
    for i in range(len(rows)):
        c = to_decimal(rows.c[i])
        if c <= ZERO_PRICE:
            removed += 1
            continue
        o, h, lo = (to_decimal(x) for x in (rows.o[i], rows.h[i], rows.lo[i]))
        fixes = 0
        if o <= ZERO_PRICE:
            o, fixes = c, fixes + 1
        if h <= ZERO_PRICE:
            h, fixes = c, fixes + 1
        if lo <= ZERO_PRICE:
            lo, fixes = c, fixes + 1
        top, bottom = max(o, c), min(o, c)
        if h < top:
            h, fixes = top, fixes + 1
        if lo > bottom:
            lo, fixes = bottom, fixes + 1
        if h > top * WICK:
            h, fixes = top, fixes + 1
        if lo * WICK < bottom:
            lo, fixes = bottom, fixes + 1
        fields += fixes
        bars.append(CleanBar(rows.dates[i], o, h, lo, c, to_volume(max(rows.v[i], 0.0))))
    member_set = set(member_days)
    covered = sum(1 for b in bars if b.date in member_set)
    if not covered:
        return Cleaned(
            **head, action=DROPPED, reason="no clean bar on a member day",
            scale_repairs=breaks, island_repairs=islands, rows_removed=removed,
        )

    dividends, refused = _dividends(series.dividends, bars)
    if refused:
        notes.append(f"refused {refused} dividends (not USD or above {MAX_DIVIDEND_YIELD:.0%} of the prior close)")
    if removed:
        notes.append(f"{removed} rows removed")
    if fields:
        notes.append(f"{fields} open/high/low values repaired")
    if covered < len(member_days):
        notes.append(f"covers {covered} of {len(member_days)} member days")
    action = TRIMMED if trimmed else REPAIRED if (breaks or islands or levels or removed or fields) else KEPT
    return Cleaned(
        **head,
        action=action,
        reason=report_text("; ".join(notes) if notes else "clean"),
        bars=tuple(bars),
        dividends=dividends,
        covered_days=covered,
        splits_applied=len(use),
        splits_skipped=len(skip),
        scale_repairs=breaks,
        island_repairs=islands,
        level_repairs=levels,
        rows_removed=removed,
        fields_repaired=fields,
        moves_kept=len(moves_kept),
        dividends_refused=refused,
    )


def _dividends(
    rows: Sequence[RawDividend], bars: Sequence[CleanBar]
) -> tuple[tuple[tuple[date, Decimal], ...], int]:
    """USD dividends inside the kept bars, 6 dp; refused when above MAX_DIVIDEND_YIELD."""
    if not bars:
        return (), 0
    days = [b.date for b in bars]
    out: dict[date, Decimal] = {}
    refused = 0
    for r in rows:
        if not days[0] <= r.ex_date <= min(days[-1], research.DEV_END):
            continue
        if r.value is None or r.value <= 0:
            continue
        if r.currency not in (None, "USD"):
            refused += 1
            continue
        amount = r.value.quantize(DIVIDEND_QUANTUM, rounding=ROUND_HALF_UP)
        if amount <= 0:
            continue
        i = bisect_left(days, r.ex_date) - 1
        if i < 0 or amount > bars[i].close * MAX_DIVIDEND_YIELD:
            refused += 1
            continue
        out[r.ex_date] = out.get(r.ex_date, Decimal(0)) + amount
    return tuple(sorted(out.items())), refused


def best_of(candidates: Sequence[Cleaned]) -> Cleaned:
    """Of several cleaned series for one symbol, the one covering the most member days.

    Ties, and a field where every candidate was dropped, go to the earliest candidate, so the
    original cache wins over a phase-2 alias unless the alias genuinely covers more.
    ValueError on an empty sequence or on candidates for different symbols.
    """
    if not candidates:
        raise ValueError("best_of needs at least one candidate")
    if len({c.symbol for c in candidates}) != 1:
        raise ValueError("best_of compares candidates for one symbol")
    best = candidates[0]
    for c in candidates[1:]:
        if c.action != DROPPED and (best.action == DROPPED or c.covered_days > best.covered_days):
            best = c
    return best


# ---- the store's text ----------------------------------------------------------------------


def bar_line(symbol: str, b: CleanBar) -> str:
    """One ``bars.csv`` line in the dev store's encoding: fixed 4 dp, integer volume."""
    return f"{symbol},{b.date.isoformat()},{b.open},{b.high},{b.low},{b.close},{b.volume}"


def amount_text(amount: Decimal) -> str:
    """A dividend amount the way ``dividends.csv`` writes it: at most 6 dp, no trailing zeros."""
    q = amount.quantize(DIVIDEND_QUANTUM, rounding=ROUND_HALF_UP).normalize()
    return format(q, "f")


def merge_sorted_lines(
    existing: Iterable[str], added: Mapping[str, Sequence[str]]
) -> Iterable[str]:
    """``existing`` data lines (grouped by symbol, symbols ascending) with ``added``'s groups
    inserted at their sorted place. Every line starts ``<symbol>,``.

    ValueError when ``existing`` is out of order or a symbol is in both: the merged file must be
    contiguous per symbol and ascending, or ``histories_from_frame`` refuses it.
    """
    pending = sorted(added)
    k = 0
    last: str | None = None
    for line in existing:
        symbol = line.split(",", 1)[0]
        if symbol != last:
            if last is not None and symbol < last:
                raise ValueError(f"the source lines are not sorted by symbol: {symbol} after {last}")
            if symbol in added:
                raise ValueError(f"{symbol} is in the source store and in the added series")
            while k < len(pending) and pending[k] < symbol:
                yield from added[pending[k]]
                k += 1
            last = symbol
        yield line
    while k < len(pending):
        yield from added[pending[k]]
        k += 1


# ---- coverage ------------------------------------------------------------------------------


def coverage_by_year(
    member_days: Mapping[str, Sequence[date]],
    before: Mapping[str, np.ndarray],
    after: Mapping[str, np.ndarray],
) -> tuple[YearCoverage, ...]:
    """Member-days per calendar year, and how many have a bar in ``before`` / ``after``.

    ``member_days`` maps each member symbol to its member sessions; ``before`` and ``after`` map
    a symbol to its bar dates as a ``datetime64[D]`` array (absent: no bars).
    """
    empty = np.array([], dtype="datetime64[D]")
    totals: dict[int, list[int]] = {}
    for symbol, days in member_days.items():
        if not days:
            continue
        arr = np.array(days, dtype="datetime64[D]")
        years = arr.astype("datetime64[Y]").astype(int) + 1970
        hit_b = np.isin(arr, before.get(symbol, empty))
        hit_a = np.isin(arr, after.get(symbol, empty))
        for y in np.unique(years):
            mask = years == y
            row = totals.setdefault(int(y), [0, 0, 0])
            row[0] += int(mask.sum())
            row[1] += int(hit_b[mask].sum())
            row[2] += int(hit_a[mask].sum())
    return tuple(YearCoverage(y, *totals[y]) for y in sorted(totals))
