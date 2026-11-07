"""M0504 — Gold-sensitive stocks: index members ranked on how strongly their weekly returns move with gold.

Source: knowledge (commodity and inflation-sensitivity factor ideas; no widely traded stock-picking
anomaly built on a stock's gold loading, so the dev window is not crowded by it). On each monthly
pick date d, over 52 weekly marks (5 sessions apart, ending on d) regress each member's weekly log
return on SPY's weekly log return and on the weekly log change in the store's GOLD series, one
shared design matrix; the gold loading is the second coefficient, net of the market. Frame is
M0504's: N20 host, 20 equal monthly slots, fractional shares at Gotrade real fees, SPY 200-day
switch. A name needs a bar dated d and history back past the first mark; with no GOLD row within
7 days of d nothing is scored and the book is empty that month (all arms alike).

Arms (six): HIGH (most gold-sensitive), LOW (least, the mirror), R1 and R2 (blind draws, seeds
504, 505, behind the switch: the draw noise), R1-NOSW (blind draw, no switch: always invested,
no opinion) and BETA (control: the highest market beta from the same fit, because gold-sensitive
stocks are often miners and cyclicals with high beta, so the loading adds something only if it
beats plain beta).
SUCCESS: HIGH beats the better of R1/R2 by more than 2 points a year funded, LOW loses to R1, HIGH
beats BETA, positive 2009-2015 edge vs SPY.
"""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
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

ADDED = date(2026, 11, 7)
MODES = ("high", "low", "beta", "blind")
WEEKS = 52
STEP = 5
STALE_DAYS = 7
GOLD = "GOLD"
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "high"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "weeks": str(WEEKS), "step": str(STEP), "series": GOLD}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TimeParams:
    if not isinstance(params, TimeParams):
        raise TypeError(f"params must be TimeParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], series: MarketSeries, symbols: list[str],
                 data_date: date) -> dict[str, tuple[float, float]]:
    """Each symbol's (gold loading, market beta) from one weekly fit; unscoreable names left out."""
    mh = history.get(MARKET)
    if mh is None:
        return {}
    i = mh.index_of(data_date)
    span = WEEKS * STEP
    if i is None or i < span:
        return {}
    rows = series.upto(GOLD, data_date, last=span + 40)
    if not rows or (data_date - rows[-1][0]).days > STALE_DAYS:
        return {}
    idx = np.arange(i - span, i + 1, STEP)
    when = mh.dates[idx]
    gd = np.array([d for d, _ in rows], dtype="datetime64[D]")
    gv = np.array([v for _, v in rows], dtype=float)
    k = np.searchsorted(gd, when, side="right") - 1
    if bool(np.any(k < 0)) or bool(np.any(gv[k] <= 0.0)):
        return {}
    dg = np.diff(np.log(gv[k]))
    m = np.diff(np.log(mh.close[idx]))
    x = np.column_stack([np.ones_like(m), m, dg])
    if np.linalg.matrix_rank(x) < 3:
        return {}
    solve = np.linalg.pinv(x.T @ x) @ x.T
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        j = None if h is None else h.index_of(data_date)
        if j is None or h.dates[0] > when[0]:
            continue
        pos = np.searchsorted(h.dates[: j + 1], when, side="right") - 1
        c = h.close[pos]
        if not bool(np.all(np.isfinite(c))) or bool(np.any(c <= 0.0)):
            continue
        coef = solve @ np.diff(np.log(c))
        g, b = float(coef[2]), float(coef[1])
        if np.isfinite(g) and np.isfinite(b):
            out[s] = (g, b)
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: TimeParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "high":
        key = {r.symbol: (-score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "low":
        key = {r.symbol: (score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "beta":
        key = {r.symbol: (-score[r.symbol][1], 0.0) for r in pool}
    else:
        key = {r.symbol: (float(draw(params.seed, r.symbol)), 0.0) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class TimePrepared:
    history: Mapping[str, History] = field(repr=False)
    series: MarketSeries = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class GoldBetaAllocator:
    """The lab's index-member book ranked on each stock's weekly loading on gold, net of SPY.
    No GOLD series (history-only path): no targets, by the market-aware contract."""

    id = "M0504"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), WEEKS * STEP + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {MARKET}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: TimePrepared, members: AbstractSet[str], data_date: date,
             p: TimeParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != MARKET)
        if data_date not in prepared.cache:
            prepared.cache[data_date] = scored_names(prepared.history, prepared.series, syms,
                                                     data_date)
        return targets_from_rows(choose(rows, prepared.cache[data_date], p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path has no GOLD, so no ranking and no target."""
        return self._run(TimePrepared(history, EMPTY_SERIES, None), members, data_date,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> TimePrepared:
        return TimePrepared(history, EMPTY_SERIES, prepare_factor(history))

    def prepare_market(self, market: Any) -> TimePrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return TimePrepared(market.history, series, prepare_factor(market.history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TimePrepared):
            raise TypeError(f"prepared must be TimePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


GOLDBETA = GoldBetaAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0504-{suffix}", family="M0504",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=GOLDBETA, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0504",
    name="Gold-sensitive stocks: the index members whose returns move most with gold",
    family="stock-gold-beta",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "Stocks differ in how their returns move with gold, after allowing for the market: miners "
        "and inflation or safe-haven sensitive names at one end, rate-sensitive growth at the other. "
        "No widely traded stock-picking anomaly rests on this loading (the commodity cousin of the "
        "treasury-beta books), so the dev window is not crowded by it. On each monthly pick date, "
        "among F4-screened point-in-time index members, regress 52 weekly log returns (marks 5 "
        "sessions apart) on SPY's weekly log return and the weekly log change in GOLD, one shared "
        "fit; hold the 20 with the highest gold loading in equal fractional slots at Gotrade real "
        "fees behind SPY's 200-day switch. Arms: HIGH, LOW (mirror), BETA (control: highest market "
        "beta from the same fit, since gold-sensitive names are cyclical and high-beta), R1 and R2 "
        "(blind draws, seeds 504, 505, switch on) and R1-NOSW (always invested, no opinion: prices "
        "the switch and acting). SUCCESS: HIGH beats the better of R1/R2 by more than 2 points a "
        "year funded, LOW loses to R1, HIGH beats BETA, positive 2009-2015 edge vs SPY. "
        "Predictions, written now: HIGH does not beat SPY in 2009-2015 (gold's 2011 peak and 2013 "
        "crash cut against it) and LOW, the gold-insensitive end, is the better arm."
    ),
    expected_failure=(
        "The gold loading is a noisy weekly regression coefficient, so the ranking is close to "
        "random and the arms match the blind draws; or HIGH is a miner-and-energy book that trades "
        "the 2000s commodity boom (a regime, not an edge) and loses it after 2009."
    ),
    candidates=(
        _v("HIGH", TimeParams(N20, "high"), "Most gold-sensitive, behind the switch"),
        _v("LOW", TimeParams(N20, "low"), "Least gold-sensitive: the mirror"),
        _v("BETA", TimeParams(N20, "beta"), "Control: highest market beta from the same fit"),
        _v("R1", TimeParams(N20, "blind", 504), "Control: hash draw of 20, seed 504, behind the switch"),
        _v("R2", TimeParams(N20, "blind", 505), "Control: hash draw of 20, seed 505, measures draw noise"),
        _v("R1-NOSW", TimeParams(NOSW, "blind", 504), "Always invested, no opinion: prices acting on either"),
    ),
    seen_keys=(
        "concept:gold-beta",
    ),
)
