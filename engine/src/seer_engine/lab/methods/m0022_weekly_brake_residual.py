"""M0022 — RM's book with its volatility brake re-read every week.

Source: variation of M0011 (its RAW20-TV14-N21 variant, on paper as RM since 2026-10-07). The
owner accepts a weekly check if it performs better; M0020 showed a weekly check costs this book
nothing by itself (+15.3% vs +15.0% a year), so the question is whether a faster brake buys a
smaller worst fall, or room for more exposure at the same fall.
Idea: M0011's brake (hold less when the 20 picks together swung more than 14% a year over the last
month) is read once a month. Its binding drawdown is a fast shock that starts inside a month (Aug
1998): a weekly re-read cuts exposure within days instead of at the next month's start.

Mechanics. Rules ``MONTHLY_RANK_WEEKLY_RESIZE``: the basket is chosen on the first session of each
month exactly as M0011 does; on every other weekly decision the runner keeps that basket and
re-scales it by k = (this allocator's weight total) / (the basket's weight total at the rank)
(``book_runner._rescaled``). So on a resize week this allocator returns the month's basket (the
inner book's unscaled targets on the anchor date, the data date before the month's first session)
scaled by the brake re-read on ``data_date``: k is then exactly brake(now) / brake(at the rank).
The market filter (SPY above its 200-day average) is read at the monthly rank only, unless
``weekly_switch``: then a resize week with SPY below its average returns nothing, which takes the
book to cash for the rest of the month (the side effect M0013 found hidden in weekly resizing,
here as its own variant). Reads only bars dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import _scaled, basket_scale
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, ResidPrepared
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20, ResidVolParams
from seer_engine.lab.methods.m0020_stop_with_weekly_reentry import _refreshed, anchor_date
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import trend_on

ADDED = date(2026, 10, 7)


@dataclass(frozen=True, slots=True)
class WeeklyBrakeParams:
    inner: ResidVolParams
    weekly_switch: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidVolParams):
            raise TypeError(f"inner must be ResidVolParams, got {type(self.inner).__name__}")
        if not isinstance(self.weekly_switch, bool):
            raise TypeError("weekly_switch must be a bool")

    def as_dict(self) -> dict[str, str]:
        out = {"weekly_switch": "yes" if self.weekly_switch else "no"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> WeeklyBrakeParams:
    if not isinstance(params, WeeklyBrakeParams):
        raise TypeError(f"params must be WeeklyBrakeParams, got {type(params).__name__}")
    return params


def _braked(history: Mapping[str, History], basket: tuple[Target, ...], data_date: date,
            p: WeeklyBrakeParams) -> tuple[Target, ...]:
    if p.weekly_switch and not trend_on(history, data_date, p.inner.inner.inner):
        return ()
    fresh = _refreshed(basket, history, data_date, None)  # the month's weights, today's closes
    return _scaled(fresh, basket_scale(history, fresh, data_date, p.inner.n, p.inner.target_vol))


class WeeklyBrakeAllocator:
    """The month's residual-momentum basket, scaled by the brake read on ``data_date``."""

    id = "M0022"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(RESIDMOM.lookback(p.inner.inner) + 25, p.inner.n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.symbols(_check(params).inner.inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.holds(_check(params).inner.inner)

    def uses_members(self, params: Any) -> bool:
        return RESIDMOM.uses_members(_check(params).inner.inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        anchor = anchor_date(data_date)
        cut = {s: h.upto(anchor) for s, h in history.items()}
        basket = RESIDMOM.targets(cut, members, anchor, held, p.inner.inner)
        return _braked(history, basket, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        basket = RESIDMOM.targets_prepared(prepared, members, anchor_date(data_date), held, p.inner.inner)
        return _braked(prepared.history, basket, data_date, p)


WEEKLYBRAKE = WeeklyBrakeAllocator()


def _v(suffix: str, params: WeeklyBrakeParams, rationale: str, rules=MONTHLY_RANK_WEEKLY_RESIZE) -> Candidate:
    return Candidate(id=f"M0022-{suffix}", family="M0022", rules=rules, allocator=WEEKLYBRAKE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0022",
    name="RM's book with its volatility brake re-read every week",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="M0011 (M0011-RAW20-TV14-N21, on paper as RM); M0020 (weekly checking is free); "
               "M0004 and M0013 (weekly resizing on other books)",
    parent_id="M0011",
    hypothesis=(
        "M0011-RAW20-TV14-N21 (+10.8% a year, 14.1% max DD, DSR 0.897) reads its one-month brake "
        "once a month, so a shock that starts mid-month (Aug 1998) is met at full exposure. Reading "
        "the same brake every week cuts exposure within days: at TV14 the worst fall should drop to "
        "about 11-12% at a similar return, and the steadier curve should lift the Sharpe and the "
        "luck score; at TV16 the faster brake should keep the worst fall near 14% while return rises "
        "toward +12% a year, the best chance of a luck score at or above 0.95. Unlike M0004 (three-"
        "month reading on total-return momentum), a one-month reading changes within a month, so a "
        "weekly re-read carries new information."
    ),
    expected_failure=(
        "Volatility measured over a month lags a crash by days either way: the weekly cut comes "
        "after the first gap-down, the money sits out the rebound (momentum's falls snap back), "
        "and the extra trades cost more than the fall saved, as M0004 found for its three-month "
        "reading. The weekly market switch (W-TV14-SW) repeats M0013's whipsaw: out on a dip, back "
        "only at the next month."
    ),
    candidates=(
        _v("W-TV14", WeeklyBrakeParams(ResidVolParams(RAW20, Decimal("0.14"), 21)),
           "RM's exact book with the brake re-read weekly; market filter monthly"),
        _v("W-TV16", WeeklyBrakeParams(ResidVolParams(RAW20, Decimal("0.16"), 21)),
           "Same at a 16% swing limit: does the faster brake leave room for more exposure?"),
        _v("W-TV14-SW", WeeklyBrakeParams(ResidVolParams(RAW20, Decimal("0.14"), 21), weekly_switch=True),
           "W-TV14 plus the market filter re-read weekly (cash until the month ends when it trips)"),
    ),
    seen_keys=(
        "concept:residual-momentum-weekly-brake",
    ),
)
