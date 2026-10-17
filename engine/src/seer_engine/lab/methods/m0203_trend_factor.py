"""M0203 — The trend factor: one score from price moving averages over every horizon.

Source: Han, Zhou & Zhu (2016), A trend factor: any economic gains from using information over
investment horizons?, Journal of Financial Economics 122(2), 352-375.
Idea: short-term reversal, momentum and long-term reversal are each one slice of the same price
path. The paper puts eleven moving averages of a stock's price (3 to 1000 days) into one monthly
cross-sectional regression, lets the data weigh each horizon, and forecasts next month's return
with the trailing twelve months' average slopes. The top decile of that forecast beat every
single-horizon sort in US stocks 1930-2014, and the paper says the combination, not any one
horizon, carries the edge.

The score, on data date d (the column ``j`` of SPY's session calendar):

    * each name's closes are laid on SPY's calendar; a moving average over L sessions exists only
      when all L closes are there (a gap leaves it undefined rather than averaged across);
    * a name's features at column t are MA_L(t) / close(t) for L in ``LAGS``, the paper's
      normalisation, which also makes them blind to the back-adjustment scale;
    * the sample columns are s_k = j - 21k. Regression k (k = 1..12) puts the return from s_k to
      s_(k-1) on the features at s_k, with an intercept, by least squares. Every number it reads
      is dated at or before d;
    * the forecast is the features at j times the average of the twelve slope vectors (the
      intercept is common to every name and cannot move the ranking, so it is dropped);
    * a regression needs at least ``MIN_NAMES`` names with every feature and a return; all twelve
      must exist, else nothing is scored on d and the book sits in SPY.

Which names train the regressions. ``Mapping[str, History]`` carries no membership history, so the
cross-section of every regression is F4's screened members **on d** (the names the book may buy),
read back at each sample column. That is no look-ahead -- d's membership is known on d -- but it
is a selection: a name added to the index in the last year got in partly by rising, so the slopes
lean slightly toward trend. Assumed small (additions are a few percent of the index a year) and
written down here rather than discovered later. The paper uses every NYSE/AMEX/Nasdaq name.

The book (``choose``), as M0192's frame: rank the forecasts, highest first. A held name still
ranked inside ``keep`` stays; free slots are filled from the top, ``top`` slots of 1/top each.
Unfilled slots sit in SPY, so before any name has the four years of history the 1000-day average
needs, the book is SPY. With ``inner.trend`` set, the whole book is cash while SPY is under its
200-day average, as in F4.

``signal="hash"`` is the same-frame placebo: the identical pool (only names the trend factor could
score on d), band, slots, SPY fill and switch, ranked by blake2b(seed | symbol | year-month)
instead of the forecast, as M0187. If the trend book does not clearly beat it, the frame earned
the result, not the forecast.

Assumption, written before the run: the reserved idea also named a plain 12-1 momentum book in the
same frame as a contrast. It is left out on purpose. The hard gate's behaviour test (hardgate D14)
reads every dev variant of a method, and a plain momentum variant would move with the test-failed
momentum books and make every variant here unpromotable. The comparison with momentum is made in
the analysis against the lab's recorded real-fee momentum books instead.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits. Pure: no clock, randomness, files or network; reads only columns at or before d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 17)
LAGS: tuple[int, ...] = (3, 5, 10, 20, 50, 100, 200, 400, 600, 800, 1000)  # the paper's eleven
STEP = 21  # sessions between sample columns: one month
MONTHS = 12  # regressions averaged into the forecast slopes
MIN_NAMES = 50  # names a regression needs (four times the regressors plus intercept)
SIGNALS = ("trend", "hash")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class TrendParams:
    """``inner`` is F4's screen, switch and book size; the rest is the signal and the band.

    ``inner.rank`` never selects here; ``"momentum"`` keeps the screened universe identical to
    M0007's, M0187's and M0192's, name for name.
    """

    inner: FactorParams
    keep: int = 40
    signal: str = "trend"
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("keep", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.keep < self.inner.top:
            raise ValueError(f"keep must be >= top, got {self.keep} < {self.inner.top}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep": str(self.keep), "signal": self.signal, "seed": str(self.seed),
               "market": self.market, "lags": ",".join(str(x) for x in LAGS),
               "step": str(STEP), "months": str(MONTHS), "min_names": str(MIN_NAMES)}
        if self.signal == "hash":
            out["hash"] = "blake2b-8"
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TrendParams:
    if not isinstance(params, TrendParams):
        raise TypeError(f"params must be TrendParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the close grid


@dataclass(frozen=True, slots=True, eq=False)
class CloseGrid:
    """Every symbol's closes on the market symbol's calendar, with prefix sums for the averages.

    ``csum[k, t]`` is the sum of the finite closes in columns < t and ``cnt[k, t]`` their count, so
    the average over columns (t - L, t] is (csum[t + 1] - csum[t + 1 - L]) / L when the count is L.
    A prefix sum through t reads columns <= t only and adds in the same order however much history
    follows, so the averages are bit-identical on history cut at d and on the whole history.
    """

    row: Mapping[str, int]
    dates: np.ndarray  # datetime64[D]
    close: np.ndarray  # (n_symbols, n_dates), NaN where the symbol has no bar that session
    csum: np.ndarray  # (n_symbols, n_dates + 1)
    cnt: np.ndarray  # (n_symbols, n_dates + 1) int64


def build_close_grid(history: Mapping[str, History], market: str) -> CloseGrid | None:
    m = history.get(market)
    if m is None or len(m) < 2:
        return None
    cal = m.dates
    ncal = len(cal)
    symbols = tuple(sorted(history))
    close = np.full((len(symbols), ncal), np.nan, dtype=np.float64)
    for k, symbol in enumerate(symbols):
        h = history[symbol]
        if len(h) == 0:
            continue
        pos = np.searchsorted(cal, h.dates)
        inside = pos < ncal
        safe = np.where(inside, pos, 0)
        on_cal = inside & (cal[safe] == h.dates)
        c = np.asarray(h.close, dtype=np.float64)
        good = on_cal & np.isfinite(c) & (c > 0.0)
        close[k, safe[good]] = c[good]
    ok = np.isfinite(close)
    csum = np.zeros((len(symbols), ncal + 1), dtype=np.float64)
    csum[:, 1:] = np.cumsum(np.where(ok, close, 0.0), axis=1)
    cnt = np.zeros((len(symbols), ncal + 1), dtype=np.int64)
    cnt[:, 1:] = np.cumsum(ok, axis=1)
    for a in (close, csum, cnt):
        a.setflags(write=False)
    return CloseGrid({s: k for k, s in enumerate(symbols)}, cal, close, csum, cnt)


def features(grid: CloseGrid, idx: np.ndarray, t: int) -> np.ndarray:
    """(len(idx), len(LAGS)) of MA_L(t) / close(t); NaN where an average or the close is missing."""
    out = np.full((len(idx), len(LAGS)), np.nan, dtype=np.float64)
    if t < 0:
        return out
    c = grid.close[idx, t]
    for i, lag in enumerate(LAGS):
        if t + 1 - lag < 0:
            continue
        s = grid.csum[idx, t + 1] - grid.csum[idx, t + 1 - lag]
        n = grid.cnt[idx, t + 1] - grid.cnt[idx, t + 1 - lag]
        with np.errstate(divide="ignore", invalid="ignore"):
            out[:, i] = np.where(n == lag, (s / lag) / c, np.nan)
    return out


# --------------------------------------------------------------------------- the signal


def forecasts(grid: CloseGrid, symbols: list[str], data_date: date) -> dict[str, float]:
    """Each symbol's trend forecast on ``data_date``; empty when any of the twelve fits is too thin."""
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j - STEP * MONTHS < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    slopes: list[np.ndarray] = []
    for k in range(1, MONTHS + 1):
        t0, t1 = j - STEP * k, j - STEP * (k - 1)
        x = features(grid, idx, t0)
        with np.errstate(divide="ignore", invalid="ignore"):
            y = grid.close[idx, t1] / grid.close[idx, t0] - 1.0
        ok = np.isfinite(x).all(axis=1) & np.isfinite(y)
        if int(ok.sum()) < MIN_NAMES:
            return {}
        a = np.column_stack([np.ones(int(ok.sum())), x[ok]])
        coef = np.linalg.lstsq(a, y[ok], rcond=None)[0]
        slopes.append(coef[1:])
    beta = np.mean(np.stack(slopes), axis=0)
    x = features(grid, idx, j)
    live = np.isfinite(x).all(axis=1)
    f = np.where(live, np.where(live[:, None], x, 0.0) @ beta, np.nan)
    return {names[k]: float(f[k]) for k in (int(v) for v in np.flatnonzero(live & np.isfinite(f)))}


def draw(seed: int, symbol: str, data_date: date) -> int:
    """The placebo's score: a fixed 64-bit hash of seed, symbol and the decision's month (M0187)."""
    key = f"{seed}|{symbol}|{data_date.year:04d}-{data_date.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def scored(grid: CloseGrid, rows: list[FactorRow], data_date: date, p: TrendParams) -> dict[str, float]:
    """Higher is better. The placebo keeps the trend factor's pool and replaces only the order."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    fc = forecasts(grid, pool, data_date)
    if p.signal == "trend":
        return fc
    return {s: -float(draw(p.seed, s, data_date)) for s in fc}


def choose(history: Mapping[str, History], rows: list[FactorRow], sc: Mapping[str, float],
           data_date: date, held: frozenset[str], p: TrendParams) -> tuple[Target, ...]:
    """The band: held names ranked inside ``keep`` stay, the rest of ``top`` filled from the top."""
    order = sorted(sc, key=lambda s: (-sc[s], s))
    rank = {s: i for i, s in enumerate(order)}
    kept = sorted((s for s in held if rank.get(s, p.keep) < p.keep), key=lambda s: rank[s])
    picks = kept[: p.inner.top]
    for s in order:
        if len(picks) >= p.inner.top:
            break
        if s not in picks:
            picks.append(s)
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks:
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class TrendPrepared:
    """F4's rolling columns plus one close grid per market symbol, built on first use."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    grids: dict[str, CloseGrid | None] = field(default_factory=dict, repr=False)

    def grid(self, market: str) -> CloseGrid | None:
        if market not in self.grids:
            self.grids[market] = build_close_grid(self.history, market)
        return self.grids[market]


class TrendFactorAllocator:
    """The ``top`` highest trend forecasts among screened members (or the placebo order), banded."""

    id = "M0203"

    def lookback(self, params: Any) -> int:
        # The screen's and the switch's need, as M0192: a name without the 1000-day history is not
        # scored yet and its slot holds SPY, so the window opens with the other F4 books.
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: CloseGrid | None, data_date: date, held: frozenset[str],
                 p: TrendParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        sc = scored(grid, rows, data_date, p)
        return choose(history, rows, sc, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_close_grid(history, p.market), data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> TrendPrepared:
        return TrendPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TrendPrepared):
            raise TypeError(f"prepared must be TrendPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, held, p)


TREND_FACTOR = TrendFactorAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)
N40 = FactorParams(rank="momentum", top=40, trend=TREND)
N20_NOSW = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: TrendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0203-{suffix}", family="M0203", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=TREND_FACTOR, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0203",
    name=("The trend factor: one score from price moving averages over every horizon, from three "
          "days to four years"),
    family="stock-trend-factor",
    source_kind="paper",
    source_ref=("Han, Zhou and Zhu (2016), A trend factor: any economic gains from using information "
                "over investment horizons?, Journal of Financial Economics 122(2)"),
    hypothesis=(
        "Each month-end, divide each screened member's 3, 5, 10, 20, 50, 100, 200, 400, 600, 800 "
        "and 1000-day moving averages by its price; regress the next month's return on these 11 "
        "ratios across members, once for each of the last 12 months (all data at or before the "
        "decision date); forecast with the average of the 12 slope vectors; hold the 20 highest "
        "forecasts in equal 5% slots, monthly, keeping a holding while it ranks inside the top 40, "
        "unfilled slots in SPY, behind the SPY 200-day switch (F4's screen and switch, M0192's "
        "band). Han, Zhou and Zhu (published 2016, working paper from 2013) find the combined "
        "trend signal beats short-term reversal, momentum and long-term reversal separately in US "
        "stocks 1930-2014, because it lets the data weight each horizon. The dev window ends in "
        "2015, so most of it predates the paper; this is in-sample for the paper. Arms: TF-N40 (40 "
        "names, band 80), TF-N20-NOSW (no switch). Control: HASH-N20, the same pool, band, slots, "
        "fill and switch in a fixed hash order (M0187's placebo). The plain 12-1 momentum contrast "
        "named when the idea was reserved is dropped: a momentum variant would tie the whole method "
        "to the test-failed momentum books through the behaviour test (hardgate D14); momentum is "
        "compared against the recorded real-fee momentum books instead. Fractional shares at "
        "Gotrade's real fees (monthly-hold-frac-gotrade) on the owner's monthly top-up. Success: "
        "beats SPY TR on dev with worst fall <= 25%, PF >= 1.3, a majority of walk-forward folds, "
        "a positive lead over SPY in 2009-2015, and beats the placebo by at least 2 points a year."
    ),
    expected_failure=(
        "The forecast's slopes are dominated by the short averages (3-20 days), which is one-month "
        "reversal, and by the long ones, which is momentum; in large caps at real fees the "
        "reversal part churns 20 small slots every month and the lab's reversal books all trailed "
        "SPY. The 11 ratios are almost collinear, so 12 noisy least-squares fits on a few hundred "
        "names give slopes that flip sign month to month and the book trades like the placebo. "
        "The paper's spread is long-short and much of it lives in small, illiquid names the screen "
        "excludes. A published anomaly with a big paper fades (insight on M0050), and equal slots "
        "lean small against SPY's big-company drift (insight 91), so 2009-2015 is likely to lag "
        "SPY even if the twenty-year average wins. If it does win, it may simply be momentum by "
        "another route and inherit momentum's 2009 crash, which the 200-day switch meets late."
    ),
    candidates=(
        _v("TF-N20", TrendParams(N20, keep=40),
           "20 highest trend forecasts, held while inside the top 40, behind the SPY 200-day switch"),
        _v("TF-N40", TrendParams(N40, keep=80),
           "Same forecast, 40 names, band 80: does width tame a noisy forecast?"),
        _v("TF-N20-NOSW", TrendParams(N20_NOSW, keep=40),
           "The main book without the SPY 200-day switch, as the paper trades it"),
        _v("HASH-N20", TrendParams(N20, keep=40, signal="hash"),
           "Placebo: the same pool, band, slots and switch in a fixed hash order"),
    ),
    seen_keys=(
        "concept:trend-factor",
        "concept:moving-average-cross-section",
    ),
)
