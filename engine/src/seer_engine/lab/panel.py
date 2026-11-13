"""The signal panel: does a ranking order next month's returns across the whole pool? (stage one)

A book backtest asks whether one concentrated portfolio beat SPY. Random twins of a book with the
same dates and weights spread wider than a typical signal's effect, so a book cannot tell whether
its ranking did anything (plan index ``SERA_SIGNAL_PANEL_PLAN.md``, "Why"). The panel asks the
earlier question, on every pool member and every month at once: across the screened pool, do
higher scores go with higher next-month returns, beyond what momentum, beta, size and volatility
already explain? It is pure: no database, no clock, no files. ``lab panel`` (phase 3) loads the
stores, calls this module and records what it returns.

**The frame** (``build_frame``, built once per research store and shared by every signal):

- *Decision dates*: the last NYSE session of each month (``tree_rank.month_ends``), from the first
  month with a pool, through the last whose forward month ends on or before ``DEV_END``. A store
  whose window ends after ``DEV_END`` is refused: the panel never reads the test window.
- *Universe*: the members on the decision date d (``Market.membership``, so point in time), SPY
  excluded, that have a bar dated d.
- *Pool*: the universe names that pass ``tree_rank.SCREEN``, which is F4's screen with no trend
  switch. It is computed with ``f_factor.factor_rows``, the single-window twin of
  ``FactorPrepared.rows_on`` (equal by f_factor's contract), because ``prepare_factor`` would hold
  every symbol's every-bar columns in memory beside the store when the panel reads only
  month-ends.
- *Forward return*: a total return, from the close of the name's first bar after d to its last
  close on or before the session after the next decision date, plus the cash dividends gone ex
  after the entry bar and on or before the exit bar (``ResearchData.dividends``, split-adjusted
  like the closes). A name with no bar at the exit takes its last close. A name with no bar after
  d by the exit is dropped from that month's statistics and counted (``dropped_exits``). That is
  the survivorship store's dead name whose last bar fell on the decision date.
- *Controls*, from bars dated <= d: 12-1 momentum and 60-session volatility, F4's own windows;
  252-session beta to SPY on SPY's sessions, a name's close carried forward over its own gaps;
  size as log 20-session mean dollar volume. ``Market.market_value`` covers only part of the dev
  member-days, so it is not used.

**One month's reading.** In *score* mode the scorer's numbers for pool names are the signal.
A month is measured when at least ``MIN_SCORED`` pool names are scored, the rank correlation is
defined, and the regression below has full rank. Each measured month gives:

- *rank correlation*: Spearman's (Pearson's on ``rank01`` ranks) between score and forward return,
  over scored pool names with a return;
- *top-minus-pool spread*: the mean return of the top bucket (``top_size``: the higher of
  ``TOP_MIN`` and a ``TOP_FRACTION`` share of the scored names, ties broken by symbol) minus the
  mean return of every pool name with a return. The bucket is chosen before dropped names leave
  it, so it is what the signal picked;
- *controlled slope*: a Fama-MacBeth cross-section, forward return on an intercept, the score's
  rank standardised to one standard deviation, and the four controls (each clipped at its 1st and
  99th percentile, then standardised). The slope is next-month return per one standard deviation
  of score.

In *picks* mode (``panel_replay``, phase 4) the scorer names a pick set: any universe name it
gives a finite value. A month needs ``MIN_PICKS`` picks. The spread is picks minus pool, the
slope is on a 0/1 pick dummy over the pool plus the picks, and there is no rank correlation.

**Eras.** A month belongs to ``pre2009`` or ``2009-2015`` by its decision date (``ERA_SPLIT``),
and every month belongs to ``all``. Per era, from the monthly series: the mean of each reading
and its t-statistic, mean / (sd / sqrt(months)), the spread annualised as twelve times its
monthly mean, and the mean share of the top bucket replaced between consecutive measured months.
An era with fewer than ``MIN_ERA_MONTHS`` measured months is left out, so a reading never
carries a t-statistic computed from a handful of months.

**What this module does not do.** No false-discovery correction and no verdict (``panel_verdict``,
phase 2). Nothing here counts toward the luck gate's N. No store loading and no recording
(``lab panel``, phase 3).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

import numpy as np

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab.signal import Signal
from seer_engine.lab.tree_rank import SCREEN, month_ends
from seer_engine.strategies.b import rank01
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import DV_N, EXCLUDED, factor_rows
from seer_engine.strategies.indicators import mean_dollar_volume_window, return_window, stdev_return_window

if TYPE_CHECKING:
    from seer_engine.backtest.market import Market
    from seer_engine.research import ResearchData

RULE_ID = "panel-v1"
ERAS: tuple[str, ...] = ("all", "pre2009", "2009-2015")
ERA_SPLIT = date(2009, 1, 1)
TOP_FRACTION = 0.10  # top bucket = max(TOP_MIN, ceil(TOP_FRACTION * scored))
TOP_MIN = 10
MIN_SCORED = 30  # a month with fewer scored pool names is skipped ("score" mode)
MIN_PICKS = 5  # a month with fewer picks is skipped ("picks" mode)
MIN_ERA_MONTHS = 12  # an era with fewer measured months is left out of a reading
MARKET = "SPY"  # the beta control's market
MOM_N = SCREEN.mom_n  # 252: F4's 12-1 momentum, read off the screen so the two cannot drift
MOM_SKIP = SCREEN.mom_skip  # 21
VOL_N = SCREEN.vol_n  # 60
BETA_N = 252  # one-session returns in the beta window
WINDOW = max(MOM_N, BETA_N) + 1  # bars through d the controls read
CLIP_PCT = (1.0, 99.0)  # each control is clipped to these percentiles before it is standardised
CONTROLS: tuple[str, ...] = ("momentum", "beta", "volatility", "size")
MONTHS_PER_YEAR = 12
MODES: tuple[str, ...] = ("score", "picks")

Scorer = Callable[["Market", AbstractSet[str], date], Mapping[str, float]]
Mode = Literal["score", "picks"]


@dataclass(frozen=True, eq=False)
class PanelMonth:
    """One decision date's cross-section (module docstring, "The frame").

    ``symbols`` is the universe, sorted. ``in_pool``, ``ret`` and the rows of ``controls`` (one
    column per ``CONTROLS`` entry) are aligned with it. ``ret`` is NaN for a dropped name and a
    control is NaN where it cannot be read. ``pool`` is what a scorer is handed. ``row`` maps a
    symbol to its position. Every array is read-only.
    """

    day: date
    entry: date
    exit: date
    symbols: tuple[str, ...]
    in_pool: np.ndarray
    ret: np.ndarray
    controls: np.ndarray
    pool: frozenset[str]
    row: Mapping[str, int]


@dataclass(frozen=True, eq=False)
class PanelFrame:
    """A store's decision months, ascending, and the market every scorer reads through."""

    market: Market
    months: tuple[PanelMonth, ...]


@dataclass(frozen=True)
class EraStats:
    """One era's reading (module docstring, "Eras"). Every float is finite.

    ``spread_top`` is annualised; ``fm_slope`` is the mean *monthly* slope. ``ic_mean`` and
    ``ic_t`` are None in picks mode and only there. A t-statistic over fewer than two months, or
    over a series with no spread, is 0.0; ``top_turnover`` is 0.0 when no two measured months of
    the era are consecutive.
    """

    era: str
    months: int
    mean_pool: float
    mean_scored: float
    ic_mean: float | None
    ic_t: float | None
    spread_top: float
    spread_t: float
    fm_slope: float
    fm_t: float
    top_turnover: float


@dataclass(frozen=True)
class PanelReading:
    """What ``measure`` returns: one ``EraStats`` per era that has enough months, in ``ERAS`` order.

    ``picks_hash`` is sha256 over ``"{decision date}:{sorted top-bucket symbols, comma-joined}\\n"``
    for every measured month, ascending. Two panels with one pick set in every month share it.
    ``dropped_exits`` counts, over measured months, the names in the measured set with no bar
    after the decision date by the exit.
    """

    stats: tuple[EraStats, ...]
    picks_hash: str
    dropped_exits: int

    def era(self, name: str) -> EraStats | None:
        for s in self.stats:
            if s.era == name:
                return s
        return None


@dataclass(frozen=True)
class _MonthReading:
    index: int  # position in PanelFrame.months, so consecutive months can be told apart
    day: date
    pool: int  # pool names with a forward return
    scored: int  # pool names scored (score mode) or picks (picks mode)
    ic: float | None
    spread: float
    slope: float
    top: frozenset[str]
    dropped: int


def top_size(scored: int) -> int:
    """The top bucket for ``scored`` names: ``max(TOP_MIN, ceil(TOP_FRACTION * scored))``.

    The product is rounded before the ceiling so binary float noise cannot add a name.
    """
    return max(TOP_MIN, math.ceil(round(TOP_FRACTION * scored, 9)))


# --------------------------------------------------------------------------- the frame


def build_frame(data: ResearchData) -> PanelFrame:
    """The stock-by-month frame of ``data`` (module docstring). Built once per store.

    ValueError when the store's window ends after ``DEV_END`` (the panel reads the dev window
    only) or the store has too few SPY bars for the beta control.
    """
    window = data.window
    if window.end > DEV_END:
        raise ValueError(
            f"the panel reads the dev window only, which ends {DEV_END}; this store's "
            f"{window.name} window ends {window.end}"
        )
    market = data.market
    spy = market.history.get(MARKET)
    if spy is None or len(spy) <= BETA_N:
        raise ValueError(f"the panel needs {BETA_N + 1} or more {MARKET} bars for the beta control")
    calendar = month_ends(spy.dates[0].item(), window.end)
    paid = _dividend_index(data.dividends)
    months: list[PanelMonth] = []
    for day, following in zip(calendar, calendar[1:]):
        exit_ = dates.next_session(following)
        if exit_ > window.end:
            break
        month = _month(market, spy, paid, day, dates.next_session(day), exit_)
        if month is not None:
            months.append(month)
    return PanelFrame(market, tuple(months))


def _dividend_index(dividends: Mapping[str, Mapping[date, Decimal]]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """symbol -> (ex-dates ascending, cumulative cash with a leading 0): a range sum is two lookups."""
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for symbol, by_date in dividends.items():
        items = sorted(by_date.items())
        if not items:
            continue
        days = np.array([d for d, _ in items], dtype="datetime64[D]")
        cum = np.concatenate(([0.0], np.cumsum([float(amount) for _, amount in items])))
        out[symbol] = (days, cum)
    return out


def _paid(index: Mapping[str, tuple[np.ndarray, np.ndarray]], symbol: str, after: np.datetime64,
          through: np.datetime64) -> float:
    """Cash per share gone ex in (``after``, ``through``]."""
    entry = index.get(symbol)
    if entry is None:
        return 0.0
    days, cum = entry
    lo = int(np.searchsorted(days, after, side="right"))
    hi = int(np.searchsorted(days, through, side="right"))
    return float(cum[hi] - cum[lo])


def _forward(h: History, index: Mapping[str, tuple[np.ndarray, np.ndarray]], day: date, exit_: date) -> float:
    """Total return from the first close after ``day`` to the last close on or before ``exit_``; NaN
    when there is no bar in between (the name is dropped) or a close is unusable."""
    i = int(np.searchsorted(h.dates, as_day(day), side="right"))
    stop = as_day(exit_)
    if i >= len(h) or h.dates[i] > stop:
        return math.nan
    j = int(np.searchsorted(h.dates, stop, side="right")) - 1
    c0 = float(h.close[i])
    c1 = float(h.close[j])
    if not (math.isfinite(c0) and math.isfinite(c1) and c0 > 0.0):
        return math.nan
    return (c1 + _paid(index, h.symbol, h.dates[i], h.dates[j])) / c0 - 1.0


def _beta(stock: np.ndarray, spy_close: np.ndarray) -> np.ndarray:
    """Each row's beta to SPY over aligned closes (rows x BETA_N + 1); NaN where a close is missing."""
    with np.errstate(divide="ignore", invalid="ignore"):
        r = stock[:, 1:] / stock[:, :-1] - 1.0
        m = spy_close[1:] / spy_close[:-1] - 1.0
        mc = m - m.mean()
        var = float(mc @ mc)
        if not (math.isfinite(var) and var > 0.0):
            return np.full(stock.shape[0], np.nan)
        rc = r - r.mean(axis=1, keepdims=True)
        out = (rc @ mc) / var
    out[~np.isfinite(out)] = np.nan
    return out


def _month(market: Market, spy: History, paid: Mapping[str, tuple[np.ndarray, np.ndarray]], day: date,
           entry: date, exit_: date) -> PanelMonth | None:
    """``day``'s cross-section, or None when no member passes the screen that day."""
    history = market.history
    members = market.membership.members_on(day)
    pool = frozenset(r.symbol for r in factor_rows(history, members, day, SCREEN))
    if not pool:
        return None
    symbols = tuple(sorted(
        s for s in members if s not in EXCLUDED and s in history and history[s].index_of(day) is not None
    ))
    k = len(symbols)
    close = np.full((k, WINDOW), np.nan)
    volume = np.full((k, WINDOW), np.nan)
    aligned = np.full((k, BETA_N + 1), np.nan)
    j = spy.index_of(day)
    spy_days = spy.dates[j - BETA_N : j + 1] if j is not None and j >= BETA_N else None
    ret = np.full(k, np.nan)
    for row, symbol in enumerate(symbols):
        h = history[symbol]
        i = h.index_of(day)
        lo = max(0, i + 1 - WINDOW)
        n = i + 1 - lo
        close[row, WINDOW - n :] = h.close[lo : i + 1]
        volume[row, WINDOW - n :] = h.volume[lo : i + 1]
        if spy_days is not None:
            idx = np.searchsorted(h.dates, spy_days, side="right") - 1
            if idx[0] >= 0:
                aligned[row] = h.close[idx]
        ret[row] = _forward(h, paid, day, exit_)
    with np.errstate(divide="ignore", invalid="ignore"):
        momentum = return_window(close, MOM_N, MOM_SKIP)
        volatility = stdev_return_window(close, VOL_N)
        dollar_volume = mean_dollar_volume_window(close, volume, DV_N)
        size = np.log(np.where(dollar_volume > 0.0, dollar_volume, np.nan))
    beta = _beta(aligned, spy.close[j - BETA_N : j + 1]) if spy_days is not None else np.full(k, np.nan)
    controls = np.column_stack((momentum, beta, volatility, size))
    controls[~np.isfinite(controls)] = np.nan
    in_pool = np.array([s in pool for s in symbols], dtype=bool)
    for arr in (in_pool, ret, controls):
        arr.setflags(write=False)
    return PanelMonth(day, entry, exit_, symbols, in_pool, ret, controls, pool,
                      {s: r for r, s in enumerate(symbols)})


# --------------------------------------------------------------------------- measuring


def signal_scorer(signal: Signal) -> Scorer:
    """A registered signal as a scorer. ``Signal.scores`` applies the look-ahead cut itself."""
    return signal.scores


def measure(frame: PanelFrame, scorer: Scorer, *, mode: Mode = "score") -> PanelReading:
    """``scorer`` read on every month of ``frame`` (module docstring, "One month's reading", "Eras").

    ``scorer(market, pool, d)`` returns symbol -> number. Symbols outside the month's universe are
    ignored, and in score mode so are those outside the pool. A NaN means no opinion. TypeError
    when it returns anything but a Mapping of numbers; ValueError for an unknown ``mode``.

    A scorer that never yields a measurable month (in picks mode: never ``MIN_PICKS`` picks, e.g.
    an arm whose switch is always off) is not an error: ``measure`` returns a reading with empty
    ``stats`` and never raises for it. Phase 4 reports such an arm as skipped (too few picks) and
    records nothing for it; phase 3 records nothing for a signal with no whole-window era.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    readings: list[_MonthReading] = []
    for index, month in enumerate(frame.months):
        values = _aligned(scorer(frame.market, month.pool, month.day), month)
        reading = _read(month, index, values, mode)
        if reading is not None:
            readings.append(reading)
    stats = tuple(s for s in (_era_stats(era, readings) for era in ERAS) if s is not None)
    return PanelReading(stats, _picks_hash(readings), sum(r.dropped for r in readings))


def _aligned(raw: object, month: PanelMonth) -> np.ndarray:
    if not isinstance(raw, Mapping):
        raise TypeError(f"a scorer returns a Mapping of symbol -> number, got {type(raw).__name__}")
    out = np.full(len(month.symbols), np.nan)
    for symbol, value in raw.items():
        j = month.row.get(symbol)
        if j is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
            raise TypeError(f"the score for {symbol} on {month.day} must be a number, got {type(value).__name__}")
        out[j] = float(value)
    out[~np.isfinite(out)] = np.nan
    return out


def _read(month: PanelMonth, index: int, values: np.ndarray, mode: str) -> _MonthReading | None:
    """One month's reading, or None when the month cannot be measured."""
    has_ret = np.isfinite(month.ret)
    base = month.in_pool & has_ret
    if not base.any():
        return None
    known = np.isfinite(month.controls).all(axis=1)
    if mode == "score":
        opinion = month.in_pool & np.isfinite(values)
        scored = int(opinion.sum())
        if scored < MIN_SCORED:
            return None
        selected = _top(month, values, opinion, top_size(scored))
        valid = opinion & has_ret
        if int(valid.sum()) < 3:
            return None
        ic = _corr(rank01(values[valid]), rank01(month.ret[valid]))
        if ic is None:
            return None
        sample = valid & known
        x = _rank_z(values[sample])
        dropped = int((month.in_pool & ~has_ret).sum())
    else:
        opinion = np.isfinite(values)
        scored = int(opinion.sum())
        if scored < MIN_PICKS:
            return None
        selected = opinion
        ic = None
        sample = (base | (opinion & has_ret)) & known
        x = opinion[sample].astype(np.float64)
        dropped = int(((month.in_pool | opinion) & ~has_ret).sum())
    held = selected & has_ret
    if x is None or not held.any():
        return None
    slope = _slope(month.ret[sample], x, month.controls[sample])
    if slope is None:
        return None
    spread = float(month.ret[held].mean() - month.ret[base].mean())
    top = frozenset(month.symbols[j] for j in np.flatnonzero(selected))
    return _MonthReading(index, month.day, int(base.sum()), scored, ic, spread, slope, top, dropped)


def _top(month: PanelMonth, values: np.ndarray, opinion: np.ndarray, k: int) -> np.ndarray:
    """The ``k`` highest-scored names among ``opinion``, ties broken by symbol ascending."""
    order = sorted((int(j) for j in np.flatnonzero(opinion)), key=lambda j: (-values[j], month.symbols[j]))[:k]
    out = np.zeros(len(month.symbols), dtype=bool)
    out[order] = True
    return out


def _corr(a: np.ndarray, b: np.ndarray) -> float | None:
    """Pearson's correlation, or None when either side has no spread."""
    if a.shape[0] < 3:
        return None
    a = a - a.mean()
    b = b - b.mean()
    den = math.sqrt(float(a @ a) * float(b @ b))
    if not den > 0.0:
        return None
    return float(a @ b) / den


def _rank_z(v: np.ndarray) -> np.ndarray | None:
    """``v``'s ranks standardised to mean 0, sd 1; None when there is no spread."""
    if v.shape[0] < 2:
        return None
    r = rank01(np.ascontiguousarray(v, dtype=np.float64))
    sd = float(r.std())
    if not sd > 0.0:
        return None
    return (r - r.mean()) / sd


def _clip_z(c: np.ndarray) -> np.ndarray | None:
    """A control clipped to its ``CLIP_PCT`` percentiles, then standardised; None when constant."""
    lo, hi = np.percentile(c, CLIP_PCT)
    c = np.clip(c, lo, hi)
    sd = float(c.std())
    if not sd > 0.0:
        return None
    return (c - c.mean()) / sd


def _slope(y: np.ndarray, x: np.ndarray, controls: np.ndarray) -> float | None:
    """The coefficient on ``x`` in y ~ 1 + x + controls, or None when the cross-section is too small
    or the design is rank-deficient (a constant control, or ``x`` collinear with the rest)."""
    n = y.shape[0]
    if n < MIN_SCORED:
        return None
    columns = [np.ones(n), x]
    for c in controls.T:
        z = _clip_z(c)
        if z is None:
            return None
        columns.append(z)
    design = np.column_stack(columns)
    if np.linalg.matrix_rank(design) < design.shape[1]:
        return None
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    return float(coef[1])


def _in_era(era: str, day: date) -> bool:
    if era == "all":
        return True
    if era == "pre2009":
        return day < ERA_SPLIT
    return day >= ERA_SPLIT


def _t(x: np.ndarray) -> float:
    n = x.shape[0]
    if n < 2:
        return 0.0
    sd = float(np.std(x, ddof=1))
    if not sd > 0.0:
        return 0.0
    return float(np.mean(x)) / (sd / math.sqrt(n))


def _turnover(rows: list[_MonthReading]) -> float:
    """Mean share of the top bucket replaced between consecutive measured months; 0.0 with no pair."""
    shares = [
        1.0 - len(a.top & b.top) / len(b.top)
        for a, b in zip(rows, rows[1:])
        if b.index == a.index + 1 and b.top
    ]
    return float(np.mean(shares)) if shares else 0.0


def _era_stats(era: str, readings: list[_MonthReading]) -> EraStats | None:
    rows = [r for r in readings if _in_era(era, r.day)]
    if len(rows) < MIN_ERA_MONTHS:
        return None
    spreads = np.array([r.spread for r in rows])
    slopes = np.array([r.slope for r in rows])
    if any(r.ic is None for r in rows):
        ic_mean: float | None = None
        ic_t: float | None = None
    else:
        ics = np.array([r.ic for r in rows])
        ic_mean = float(ics.mean())
        ic_t = _t(ics)
    return EraStats(
        era=era,
        months=len(rows),
        mean_pool=float(np.mean([r.pool for r in rows])),
        mean_scored=float(np.mean([r.scored for r in rows])),
        ic_mean=ic_mean,
        ic_t=ic_t,
        spread_top=float(spreads.mean()) * MONTHS_PER_YEAR,
        spread_t=_t(spreads),
        fm_slope=float(slopes.mean()),
        fm_t=_t(slopes),
        top_turnover=_turnover(rows),
    )


def _picks_hash(readings: list[_MonthReading]) -> str:
    digest = hashlib.sha256()
    for r in readings:
        digest.update(f"{r.day.isoformat()}:{','.join(sorted(r.top))}\n".encode("utf-8"))
    return digest.hexdigest()
