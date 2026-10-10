"""M0066 — The monthly earnings-day book under the weekly volatility brake.

Source: a variation of M0063 (its M0063-M-N20-TREND: the monthly news-day book; Brandt, Kishore,
Santa-Clara & Venkatachalam 2008) with M0022's weekly own-volatility brake (Barroso & Santa-Clara
2015, re-read every week), on ``monthly-rank-weekly-resize-frac-gotrade`` and the owner's monthly
top-up.
Idea: M0063-M-N20-TREND beat SPY by 4.4 points a year on dev, gains 1.93x its losses, DSR 0.918,
+17.7% vs +14.8% a year in 2009-2015, and failed only the worst fall: 25.2% funded (23.6% without
deposits, April-September 1998), because the monthly SPY-200 check could not react inside the
month. The weekly brake is the lab's one measured fix for a fall that starts inside a month.

Mechanics, as M0053. On the first decision of each month the basket is chosen on the anchor date
(the session before the month's first session) exactly as M0063-M-N20-TREND chooses it: the
SPY-200 switch, F4's screen, the live news-day events ranked by jump with held names first, 5%
slots, the rest parked in SPY. On every weekly decision the runner keeps that basket and uses the
allocator's answer for its total weight only: the same basket scaled by
``min(1, target_vol / the basket's own annualized volatility over the last n sessions)``, read on
``data_date``. The SPY park is part of the basket and is braked with it. Freed weight is cash.

``pick_at="data"`` (the W-MTREND variant) is the other repair: the picks are re-made weekly on
``data_date`` exactly as M0063-N20-TREND makes them, but the SPY-200 switch is read only on the
month's anchor date, so a dip under the line in mid-month does not sell the whole book. It runs
unbraked on the weekly real-fee preset M0063 assumed.

Assumptions written before the run: n = 21 sessions for the brake (M0022's and M0053's choice);
the brake reads the whole basket including its SPY park; with ``pick_at="anchor"`` the weekly
recomputation passes the current holdings as ``held``, which reproduces the month's basket because
every name in it is still live on the anchor date. Every piece reads only bars dated <=
``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import _scaled, basket_scale
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0020_stop_with_weekly_reentry import _refreshed, anchor_date
from seer_engine.lab.methods.m0063_earnings_day_jump import (
    JUMP,
    WEEKLY_HOLD_FRAC_GOTRADE,
    JumpParams,
    JumpPrepared,
    jump_lookback,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 10)

PickAt = Literal["anchor", "data"]


@dataclass(frozen=True, slots=True)
class BrakedJumpParams:
    """``inner`` is M0063's event book; ``target_vol`` None means no brake."""

    inner: JumpParams
    target_vol: Decimal | None = Decimal("0.16")
    n: int = 21
    pick_at: PickAt = "anchor"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, JumpParams):
            raise TypeError(f"inner must be JumpParams, got {type(self.inner).__name__}")
        if self.target_vol is not None and (not isinstance(self.target_vol, Decimal)
                                            or not self.target_vol > 0):
            raise ValueError(f"target_vol must be None or a positive Decimal, got {self.target_vol!r}")
        if isinstance(self.n, bool) or not isinstance(self.n, int) or self.n < 5:
            raise ValueError(f"n must be an int >= 5, got {self.n!r}")
        if self.pick_at not in ("anchor", "data"):
            raise ValueError(f"pick_at must be 'anchor' or 'data', got {self.pick_at!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "target_vol": "none" if self.target_vol is None else str(self.target_vol),
            "n": str(self.n),
            "pick_at": self.pick_at,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> BrakedJumpParams:
    if not isinstance(params, BrakedJumpParams):
        raise TypeError(f"params must be BrakedJumpParams, got {type(params).__name__}")
    return params


def _braked(history: Mapping[str, History], basket: tuple[Target, ...], data_date: date,
            p: BrakedJumpParams) -> tuple[Target, ...]:
    if p.target_vol is None:
        return basket
    fresh = _refreshed(basket, history, data_date, None)  # the month's weights, today's closes
    return _scaled(fresh, basket_scale(history, fresh, data_date, p.n, p.target_vol))


class BrakedJumpAllocator:
    """M0063's news-day basket with the SPY-200 switch read monthly, braked on ``data_date``."""

    id = "M0066"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(jump_lookback(p.inner) + 25, p.n + 1)  # the anchor can sit ~23 sessions back

    def symbols(self, params: Any) -> tuple[str, ...]:
        return JUMP.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        return JUMP.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _go(self, prepared: JumpPrepared, rows_on: Any, members: AbstractSet[str],
            data_date: date, held: frozenset[str], p: BrakedJumpParams) -> tuple[Target, ...]:
        anchor = anchor_date(data_date)
        if not trend_on(prepared.history, anchor, p.inner.inner):
            return ()
        pick = anchor if p.pick_at == "anchor" else data_date
        rows = rows_on(members, pick, p.inner.inner)
        basket = JUMP._targets(prepared, rows, pick, held, p.inner)
        return _braked(prepared.history, basket, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        anchor = anchor_date(data_date)
        cut = history if p.pick_at == "data" else {s: h.upto(anchor) for s, h in history.items()}
        prepared = JumpPrepared(cut, None)

        def rows_on(m: AbstractSet[str], d: date, inner: Any) -> list[Any]:
            return factor_rows(cut, m, d, inner)

        if not trend_on(history, anchor, p.inner.inner):
            return ()
        pick = anchor if p.pick_at == "anchor" else data_date
        basket = JUMP._targets(prepared, rows_on(members, pick, p.inner.inner), pick, held, p.inner)
        return _braked(history, basket, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> JumpPrepared:
        return JumpPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, JumpPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared JumpPrepared, got {type(prepared).__name__}")
        p = _check(params)
        return self._go(prepared, prepared.factor.rows_on, members, data_date, held, p)


BRAKEDJUMP = BrakedJumpAllocator()
M20 = JumpParams(N20)  # M0063-M-N20-TREND's params, verbatim
M20_ALWAYS = JumpParams(N20_NOTREND)


def _v(suffix: str, params: BrakedJumpParams, rationale: str,
       rules=MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0066-{suffix}", family="M0066", rules=rules, allocator=BRAKEDJUMP,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0066",
    name="The monthly earnings-day book under the weekly volatility brake: aimed at the summer-1998 fall",
    family="stock-event-drift",
    source_kind="variation",
    source_ref="M0063-M-N20-TREND (Brandt, Kishore, Santa-Clara & Venkatachalam 2008, SSRN 909563) "
               "+ M0022's weekly own-volatility brake (Barroso & Santa-Clara 2015), on "
               "monthly-rank-weekly-resize-frac-gotrade, funded monthly",
    parent_id="M0063",
    hypothesis=(
        "Published 2008, so the dev window can only show the edge from before and just after it "
        "was widely known; 2009-2015 is judged first. M0063-M-N20-TREND beat SPY by 4.4 points a "
        "year on dev with gains 1.93x its losses, a luck score of 0.918 and +17.7% vs +14.8% a "
        "year in 2009-2015, and failed only the worst fall: 25.2% funded (23.6% without deposits, "
        "April-September 1998), before the monthly SPY-200 check could react. Keep the monthly "
        "news-day pick exactly (volume >= 3x the 60-day median, an up gap, a 3-day jump >= 4 "
        "points over SPY, 20 slots of 5%, the rest in SPY, SPY-200 switch read monthly) and every "
        "week scale the whole basket by min(1, target / its own 21-session volatility), on "
        "monthly-rank-weekly-resize-frac-gotrade with the owner's funding. Variants: M-TV14, "
        "M-TV16, M-TV18 (brake targets 14/16/18% a year); M-ALWAYS-TV16 (no SPY-200 switch at "
        "all, the brake alone as crash protection: the weekly no-switch book beat SPY by 5 points "
        "a year in 2009-2015, so the switch may cost more than it saves); and W-MTREND (picks "
        "re-made weekly as M0063-N20-TREND, but the SPY-200 switch read only on the month's "
        "anchor date, unbraked, on M0063's assumed weekly-hold-frac-gotrade preset), which tests "
        "whether M0063's weekly book failed because of switch whipsaw rather than its picks. I "
        "expect M-TV16 to be the best trade-off: the basket is 5% slots plus an SPY park, so its "
        "own volatility should sit near 16-18% in calm years and the brake bites mainly in "
        "shocks. Success: at least one variant under the 20% fall limit that still beats "
        "total-return SPY with DSR >= 0.90 and beats SPY in 2009-2015."
    ),
    expected_failure=(
        "Every brake in this lab has cost about one point of yearly return per point of fall it "
        "saved, and this book's lead was earned partly in the 2009 rebound (+50% that year), when "
        "trailing volatility is still high and the brake holds the book partly in cash. That could "
        "push the luck score under 0.90 even if the fall passes. The 1998 fall was fast (mid-July "
        "to end of August): a one-month volatility reading may still be low at the first weekly "
        "check after the drop starts. Weekly resizing at Gotrade's real fees places many small "
        "orders on 5% slots of a small account. M-ALWAYS-TV16 may take too much of SPY's 2008 fall "
        "before the brake catches up. W-MTREND may still whipsaw within a month's picks and pay "
        "five times the turnover. And this is a published 2008 anomaly, so a strong dev result "
        "may have faded in 2016-2026."
    ),
    candidates=(
        _v("M-TV14", BrakedJumpParams(M20, Decimal("0.14")),
           "The monthly news-day book braked weekly to 14%: the hard brake"),
        _v("M-TV16", BrakedJumpParams(M20, Decimal("0.16")),
           "The monthly news-day book braked weekly to 16%: expected best trade-off"),
        _v("M-TV18", BrakedJumpParams(M20, Decimal("0.18")),
           "The monthly news-day book braked weekly to 18%: the light brake"),
        _v("M-ALWAYS-TV16", BrakedJumpParams(M20_ALWAYS, Decimal("0.16")),
           "No SPY-200 switch: the weekly brake alone guards the crashes"),
        _v("W-MTREND", BrakedJumpParams(M20, None, pick_at="data"),
           "Weekly picks, but the SPY-200 switch read only once a month; no brake",
           rules=WEEKLY_HOLD_FRAC_GOTRADE),
    ),
    seen_keys=("concept:earnings-drift-weekly-brake", "concept:event-drift-monthly-trend-switch"),
)
