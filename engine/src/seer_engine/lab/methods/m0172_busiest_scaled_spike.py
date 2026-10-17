"""M0172 — The spike filter on the busiest names only: rank the most-traded members on their biggest recent days against their own normal swing.

Parent: M0093, which ranked every F4-screened index member on scaled MAX5 (the mean of the five
largest daily returns over 21 sessions, over the stdev of the 60 daily returns before them) and
held the 20 lowest. The spread was real on dev -- the highest-spike control trailed the book by
about 6 points a year -- but the equal-weight book earned its lead in broad months, trailed SPY by
2.5% a year in 2009-2015 (5.7% with dead companies added back) and won 2 of 4 folds. That is the
signature of an equal-weight basket of index members tilting small against SPY's big-company
drift, not necessarily of the signal failing.

This method keeps M0093's ranking key untouched and changes only who may be ranked: before
scoring, the F4-screened rows are cut to the ``pool`` with the highest 20-day mean close x volume
(F4's own ``dollar_volume`` feature, ties broken by symbol). The store carries no market caps, so
trading value stands in for company size; the most-traded members are overwhelmingly the largest.
When fewer than ``pool`` members pass F4's screen (the 1990s, when the store prices about half of
the index), the pool is every one that does.

Assumptions, written before the run: the pool is cut on trading value measured on back-adjusted
closes, so a heavy dividend payer's 1990s trading value reads a little low next to a non-payer's;
the cross-section on one day is what is ranked, so the level error cancels and only that small
tilt remains. The scale is M0093's (60 returns before the MAX window). Everything else -- the $5
and 20M-dollar screen, the SPY 200-day switch, monthly, equal weights, fractional shares at
Gotrade's real fees on ``monthly-hold-frac-gotrade`` -- is the parent's. Reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0093_scaled_lottery_spike import (
    ScaledMaxParams,
    ScaledMaxPrepared,
    choose,
    scaled_lookback,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorRow,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 17)


@dataclass(frozen=True, slots=True)
class BusiestSpikeParams:
    """``ranking`` is M0093's scaled-spike ranking and book; ``pool`` the most-traded names it may rank."""

    ranking: ScaledMaxParams
    pool: int = 150

    def __post_init__(self) -> None:
        if not isinstance(self.ranking, ScaledMaxParams):
            raise TypeError(f"ranking must be ScaledMaxParams, got {type(self.ranking).__name__}")
        if isinstance(self.pool, bool) or not isinstance(self.pool, int):
            raise TypeError(f"pool must be an int, got {type(self.pool).__name__}")
        if self.pool < self.ranking.inner.top:
            raise ValueError(f"pool must be >= top, got pool={self.pool} top={self.ranking.inner.top}")

    @property
    def inner(self) -> FactorParams:  # the F4 params, under the name targets_from_rows reads
        return self.ranking.inner

    def as_dict(self) -> dict[str, str]:
        out = {"pool": str(self.pool)}
        for key, v in self.ranking.as_dict().items():
            out[f"ranking.{key}"] = v
        return out


def _check(params: object) -> BusiestSpikeParams:
    if not isinstance(params, BusiestSpikeParams):
        raise TypeError(f"params must be BusiestSpikeParams, got {type(params).__name__}")
    return params


def busiest(rows: list[FactorRow], pool: int) -> list[FactorRow]:
    """The ``pool`` rows with the highest 20-day mean trading value (ties by symbol)."""
    return sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[:pool]


class BusiestSpikeAllocator:
    """M0093's scaled-spike book, ranked only among the most-traded F4-screened members."""

    id = "M0172"

    def lookback(self, params: Any) -> int:
        return scaled_lookback(_check(params).ranking)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _pick(self, history: Mapping[str, History], rows: list[FactorRow], data_date: date,
              p: BusiestSpikeParams) -> tuple[Target, ...]:
        chosen = choose(busiest(rows, p.pool), history, data_date, p.ranking)
        return targets_from_rows(chosen, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        return self._pick(history, factor_rows(history, members, data_date, p.inner), data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ScaledMaxPrepared:
        return ScaledMaxPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ScaledMaxPrepared):
            raise TypeError(f"prepared must be ScaledMaxPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._pick(prepared.history, rows, data_date, p)


BUSIEST_SPIKE = BusiestSpikeAllocator()

N30 = replace(N20, top=30)


def _v(suffix: str, params: BusiestSpikeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0172-{suffix}", family="M0172", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BUSIEST_SPIKE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0172",
    name=("The spike filter on the busiest names only: rank the 150 most-traded members on their "
          "biggest recent days against their own normal swing"),
    family="stock-lottery-avoidance",
    source_kind="variation",
    source_ref=(
        "Bali, Cakici and Whitelaw (2011), Maxing out: stocks as lotteries and the cross-section of "
        "expected returns, JFE 99(2), 427-446 (working paper 2009); variation of M0093"
    ),
    parent_id="M0093",
    hypothesis=(
        "M0093 found a real spread: members whose biggest recent days were unusual for them "
        "trailed the quiet ones by about 6 points a year on dev, but the equal-weight quiet book "
        "earned its lead only in broad months, trailed SPY by 2.5% a year in 2009-2015 (5.7% with "
        "dead companies added back) and won 2 of 4 folds. That is the equal-weight small-company "
        "tilt fighting SPY's big-company drift, not the signal failing. Restrict the pool to the "
        "150 F4-screened members with the highest 20-day trading value (the store has no market "
        "caps; trading value stands in for size) and hold the 20 lowest scaled-MAX5 of those "
        "(MAX5 over 21 sessions over the stdev of the 60 returns before), at 5% each, behind the "
        "SPY 200-day switch, monthly, fractional shares at Gotrade's real fees "
        "(monthly-hold-frac-gotrade). Variants: LO5-P150-N20-T (the book), LO5-P100-N20-T (a "
        "tighter, bigger-company pool), LO5-P150-N30-T (30 names, closer to the pool's shape), and "
        "HI5-P150-N20-T, the paired control holding the 20 highest scaled spikes of the same pool, "
        "which must trail. BCW circulated from 2009, so the dev window sees mostly the pre-crowd "
        "years. Success needs a LO variant to beat SPY TR on dev within the drawdown limit, the "
        "control to trail it, a positive 2009-2015 edge and a walk-forward fold majority."
    ),
    expected_failure=(
        "Among the busiest names the spike carries less mispricing -- they are the best-arbitraged "
        "stocks, and the MAX effect is documented as strongest in small, illiquid names -- so the "
        "spread versus the control shrinks toward zero. The most-traded pool tilts to the crowd's "
        "favourites of the day (1999-2000 tech, 2007-2008 banks and energy), which deepened the "
        "worst fall when the lab weighted by trading value before, so the fall may exceed 25%. "
        "And 20 equal-weighted names out of 150 still tilt small inside that pool, so the "
        "2009-2015 gap may narrow without turning positive. A published anomaly fades: whatever "
        "edge shows is likely front-loaded before 2009."
    ),
    candidates=(
        _v("LO5-P150-N20-T", BusiestSpikeParams(ScaledMaxParams(N20, side="low"), pool=150),
           "The 20 lowest scaled-MAX5 of the 150 most-traded members, behind the switch: the book"),
        _v("LO5-P100-N20-T", BusiestSpikeParams(ScaledMaxParams(N20, side="low"), pool=100),
           "The 20 lowest scaled-MAX5 of the 100 most-traded members: bigger companies still"),
        _v("LO5-P150-N30-T", BusiestSpikeParams(ScaledMaxParams(N30, side="low"), pool=150),
           "The 30 lowest scaled-MAX5 of the 150 most-traded members: broader"),
        _v("HI5-P150-N20-T", BusiestSpikeParams(ScaledMaxParams(N20, side="high"), pool=150),
           "The 20 highest scaled-MAX5 of the 150 most-traded members: the control, expected to trail"),
    ),
    seen_keys=(
        "concept:scaled-max-busiest-pool",
        "concept:max-effect-large-caps",
    ),
)
