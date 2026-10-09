"""M0053 — Overnight-picked winners under a weekly volatility brake.

Source: a variation of M0050 (its M0050-TOT-ON: the 40 best 12-1 total-momentum names, then the
20 of them whose past-year gain came most overnight; Lou, Polk & Skouras 2019) with M0022's
weekly own-volatility brake (Barroso & Santa-Clara 2015, re-read every week), on
``monthly-rank-weekly-resize-frac-gotrade`` and the owner's monthly top-up.
Idea: M0050-TOT-ON earned 15.1% a year on the owner's deposits at real fees (deposit-matched SPY
7.2%), DSR 0.956 at N=36, and failed one condition only: a 22.8% worst fall, taken in the summer
1998 shock. The weekly brake is the lab's one measured fix for a fall that starts inside a month:
on the residual book it took the worst fall from 14.1% (monthly brake) to 12.4% (weekly).

Mechanics, as M0022. On the first decision of each month the basket is chosen on the anchor date
(the session before the month's first session) exactly as M0050-TOT-ON chooses it, including the
SPY 200-day gate, which is read at the monthly rank only. On every weekly decision the runner keeps
that basket and the allocator returns it with today's closes and the month's weights, scaled by
``min(1, target_vol / the basket's own annualized volatility over the last n sessions)`` read on
``data_date``. Freed weight is cash; no leverage.

``pool_by="residual"`` replaces the total-momentum pool with M0007-N20-RAW's market-model residual
momentum (the real-fee residual book's ranking) and runs the same overnight sort inside it.

Assumptions written before the run: the 30-name version keeps M0050's pool-to-book ratio (pool 60
for 30 names). The ex-dividend gap stays inside the overnight leg, as in M0050 (allocators see no
dividends). Every piece reads only bars dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import _scaled, basket_scale
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    N30,
    ReturnGrid,
    build_grid,
    resid_lookback,
    residual_scores,
)
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0020_stop_with_weekly_reentry import _refreshed, anchor_date
from seer_engine.lab.methods.m0050_overnight_momentum import (
    LegGrid,
    OnParams,
    build_legs,
    leg_sums,
    on_lookback,
    targets_from_rows,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorPrepared,
    FactorRow,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 9)

PoolBy = Literal["total", "residual"]


@dataclass(frozen=True, slots=True)
class WeeklyOnParams:
    """``inner`` is M0050's ``total-overnight`` ranking; ``pool_by`` picks the pool it runs inside."""

    inner: OnParams
    target_vol: Decimal = Decimal("0.16")
    n: int = 21
    pool_by: PoolBy = "total"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, OnParams):
            raise TypeError(f"inner must be OnParams, got {type(self.inner).__name__}")
        if self.inner.rank != "total-overnight":
            raise ValueError(f"inner.rank must be 'total-overnight', got {self.inner.rank!r}")
        if not isinstance(self.target_vol, Decimal) or not self.target_vol > 0:
            raise ValueError(f"target_vol must be a positive Decimal, got {self.target_vol!r}")
        if isinstance(self.n, bool) or not isinstance(self.n, int) or self.n < 5:
            raise ValueError(f"n must be an int >= 5, got {self.n!r}")
        if self.pool_by not in ("total", "residual"):
            raise ValueError(f"pool_by must be 'total' or 'residual', got {self.pool_by!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"target_vol": str(self.target_vol), "n": str(self.n), "pool_by": self.pool_by}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> WeeklyOnParams:
    if not isinstance(params, WeeklyOnParams):
        raise TypeError(f"params must be WeeklyOnParams, got {type(params).__name__}")
    return params


def _resid(p: WeeklyOnParams):
    """M0007-N20-RAW's residual params on this book's screen (only the screen's ``top`` differs)."""
    return RAW20 if p.inner.inner == N20 else type(RAW20)(p.inner.inner, scaled=False)


def choose(rows: list[FactorRow], on: Mapping[str, float], pool_score: Mapping[str, float],
           p: WeeklyOnParams) -> list[FactorRow]:
    """The ``pool`` best rows by ``pool_score``, then the ``top`` of them by overnight sum."""
    scorable = [r for r in rows if r.symbol in on and r.symbol in pool_score and r.symbol not in EXCLUDED]
    winners = sorted(scorable, key=lambda r: (-pool_score[r.symbol], r.symbol))[: p.inner.pool]
    return sorted(winners, key=lambda r: (-on[r.symbol], r.symbol))[: p.inner.inner.top]


def _basket(rows: list[FactorRow], legs: LegGrid | None, grid: ReturnGrid | None, anchor: date,
            p: WeeklyOnParams) -> tuple[Target, ...]:
    if not rows or legs is None:
        return ()
    symbols = [r.symbol for r in rows]
    on, _ = leg_sums(legs, symbols, anchor, p.inner)
    if not on:
        return ()
    if p.pool_by == "total":
        score = {r.symbol: float(r.momentum) for r in rows}
    else:
        if grid is None:
            return ()
        score = residual_scores(grid, symbols, anchor, _resid(p))
    return targets_from_rows(choose(rows, on, score, p), p.inner)


def _braked(history: Mapping[str, History], basket: tuple[Target, ...], data_date: date,
            p: WeeklyOnParams) -> tuple[Target, ...]:
    fresh = _refreshed(basket, history, data_date, None)  # the month's weights, today's closes
    return _scaled(fresh, basket_scale(history, fresh, data_date, p.n, p.target_vol))


@dataclass
class WeeklyOnPrepared:
    """F4's rolling feature columns, M0050's leg grid and M0007's return grid, built on first use."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    legs: dict[str, LegGrid | None] = field(default_factory=dict, repr=False)
    grids: dict[str, ReturnGrid | None] = field(default_factory=dict, repr=False)

    def leg_grid(self, market: str) -> LegGrid | None:
        if market not in self.legs:
            self.legs[market] = build_legs(self.history, market)
        return self.legs[market]

    def return_grid(self, market: str) -> ReturnGrid | None:
        if market not in self.grids:
            self.grids[market] = build_grid(self.history, market)
        return self.grids[market]


class WeeklyOvernightAllocator:
    """The month's overnight-picked winners, scaled every week by the brake read on ``data_date``."""

    id = "M0053"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        need = on_lookback(p.inner)
        if p.pool_by == "residual":
            need = max(need, resid_lookback(_resid(p)))
        return max(need + 25, p.n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.inner.market}
        if p.inner.inner.trend is not None:
            fixed.add(p.inner.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        anchor = anchor_date(data_date)
        cut = {s: h.upto(anchor) for s, h in history.items()}
        if not trend_on(cut, anchor, p.inner.inner):
            return ()
        rows = factor_rows(cut, members, anchor, p.inner.inner)
        grid = build_grid(cut, p.inner.market) if p.pool_by == "residual" else None
        basket = _basket(rows, build_legs(cut, p.inner.market), grid, anchor, p)
        return _braked(history, basket, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> WeeklyOnPrepared:
        return WeeklyOnPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, WeeklyOnPrepared):
            raise TypeError(f"prepared must be WeeklyOnPrepared, got {type(prepared).__name__}")
        p = _check(params)
        anchor = anchor_date(data_date)
        if not trend_on(prepared.history, anchor, p.inner.inner):
            return ()
        rows = prepared.factor.rows_on(members, anchor, p.inner.inner)
        grid = prepared.return_grid(p.inner.market) if p.pool_by == "residual" else None
        basket = _basket(rows, prepared.leg_grid(p.inner.market), grid, anchor, p)
        return _braked(prepared.history, basket, data_date, p)


WEEKLYON = WeeklyOvernightAllocator()
TOTON20 = OnParams(N20, rank="total-overnight", pool=40)  # M0050-TOT-ON's params, verbatim
TOTON30 = OnParams(N30, rank="total-overnight", pool=60)


def _v(suffix: str, params: WeeklyOnParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0053-{suffix}", family="M0053", rules=MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
                     allocator=WEEKLYON, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0053",
    name="Overnight-picked winners under a weekly volatility brake: the 1998 fall is the only thing left to fix",
    family="stock-overnight-intraday",
    source_kind="variation",
    source_ref="M0050-TOT-ON (Lou, Polk & Skouras 2019) + M0022's weekly own-volatility brake "
               "(Barroso & Santa-Clara 2015), on monthly-rank-weekly-resize-frac-gotrade, funded monthly",
    parent_id="M0050",
    hypothesis=(
        "M0050-TOT-ON (the 40 best 12-1 momentum names, then the 20 whose gain came most "
        "overnight) earned 15.1% a year on the owner's deposits at real fees against 7.2% for "
        "deposit-matched SPY, DSR 0.956 at N=36, gains-to-losses 2.41, and failed one condition "
        "only: a 22.8% worst fall in the summer-1998 shock. That shock started inside a month, "
        "which is exactly the case a weekly re-read of the basket's own volatility was built for: "
        "on the residual book the weekly brake cut the worst fall from 14.1% to 12.4% at the same "
        "target. Keep TOT-ON's selection exactly, choose the basket monthly, and every week scale "
        "it by min(1, target / its own one-month volatility), on monthly-rank-weekly-resize-frac-"
        "gotrade with the owner's funding. Variants: targets of 14%, 16% and 18% a year on the "
        "20-name book; a 30-name book (pool 60) at 16%, which should be steadier and so brake less; "
        "and the overnight sort run inside the residual-momentum pool (M0007-N20-RAW's ranking, "
        "the real-fee residual book's) at 16%. I expect TOTON20-TV18 to be the best trade-off: the "
        "overnight book runs hotter than the residual book (it carries news-gap stocks), so an 18% "
        "target binds in shocks without clamping calm years, and should land near an 18-19% fall "
        "while keeping about 13.5-14% a year funded. Success: at least one version under the 20% "
        "fall limit with a funded return above the real-fee residual book's 13.7%. The residual-"
        "pool version should have the shallowest fall, because residual ranking strips out market "
        "beta before the overnight sort adds news exposure back."
    ),
    expected_failure=(
        "Every brake in this lab has cost about one point of yearly return per point of fall it "
        "saved (insight on M0044). Buying 2.8 points of fall at that rate leaves about 12% a year, "
        "under the residual book's 13.7%, so the success bar fails even if the fall bar passes. "
        "Worse, weekly resizing at Gotrade's real fees places many small orders on a 20-30 name "
        "book funded 5M IDR a month: each resize pays the 0.10 USD floor on slices worth tens of "
        "dollars, which can eat the overnight edge's 1.3-point lead over plain momentum. The 1998 "
        "fall was fast (mid-July to end of August): a one-month volatility reading may still be "
        "low at the first weekly check after the drop starts, so the light 18% target buys little. "
        "The 30-name version may dilute the overnight sort into plain momentum and lose the edge. "
        "The residual pool may conflict with the overnight sort: residual winners are the steady, "
        "low-gap names, so the overnight leg among them may be mostly dividend noise."
    ),
    candidates=(
        _v("TOTON20-TV14", WeeklyOnParams(TOTON20, Decimal("0.14"), 21),
           "M0050-TOT-ON braked weekly to 14%: the hard brake, the residual book's best target"),
        _v("TOTON20-TV16", WeeklyOnParams(TOTON20, Decimal("0.16"), 21),
           "M0050-TOT-ON braked weekly to 16%: the middle target"),
        _v("TOTON20-TV18", WeeklyOnParams(TOTON20, Decimal("0.18"), 21),
           "M0050-TOT-ON braked weekly to 18%: the light brake, expected best trade-off"),
        _v("TOTON30-TV16", WeeklyOnParams(TOTON30, Decimal("0.16"), 21),
           "30 names from the 60 best momentum names, braked weekly to 16%"),
        _v("RESON20-TV16", WeeklyOnParams(TOTON20, Decimal("0.16"), 21, pool_by="residual"),
           "The overnight sort inside the 40 best residual-momentum names, braked weekly to 16%"),
    ),
    seen_keys=("concept:overnight-momentum-weekly-brake", "concept:residual-overnight-momentum"),
)
