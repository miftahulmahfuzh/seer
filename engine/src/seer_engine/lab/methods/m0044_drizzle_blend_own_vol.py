"""M0044 — A brake on the quietest book: the drizzle blend under an own-volatility target.

Source: a variation of M0036 (its M0036-BLEND: Da, Gurun & Warachka 2014's frog-in-the-pan
continuity ranked together with 12-1 momentum) with M0001's own-volatility overlay (Barroso &
Santa-Clara 2015), at the targets M0033 measured on the real-fee residual book.
Idea: M0036-BLEND has the best gains-to-losses ratio of any real-fee book in the lab and the
lowest turnover, and fails one condition only: a 22.28% worst fall against the 20% limit, taken
in the summer of 1998. Scale every weight by ``min(1, target_vol / the target basket's own
annualized volatility over the last n sessions)`` and the fall comes down; the question is the
price in return. Nothing else changes: same screen, trend gate, top-20, monthly, equal weights,
fractional shares at Gotrade's real fees on ``monthly-hold-frac-gotrade``.

The allocator takes M0036's targets unchanged (``FROG``) and applies M0001's ``basket_scale`` /
``_scaled`` exactly as M0011 does on the residual book. Freed weight is cash. No leverage.
``target_vol=None`` is the no-brake control: it re-states M0036-BLEND under this allocator so the
braked variants are compared within one run. Every piece reads only bars dated <= d.
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
from seer_engine.lab.methods.m0007_residual_momentum import N20, ResidPrepared
from seer_engine.lab.methods.m0036_frog_in_the_pan import FROG, FipParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 9)


@dataclass(frozen=True, slots=True)
class FrogVolParams:
    inner: FipParams
    target_vol: Decimal | None = Decimal("0.18")  # None = no brake (the control)
    n: int = 21

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FipParams):
            raise TypeError(f"inner must be FipParams, got {type(self.inner).__name__}")
        if self.target_vol is not None and (
                not isinstance(self.target_vol, Decimal) or not self.target_vol > 0):
            raise ValueError(f"target_vol must be a positive Decimal or None, got {self.target_vol!r}")
        if isinstance(self.n, bool) or not isinstance(self.n, int) or self.n < 5:
            raise ValueError(f"n must be an int >= 5, got {self.n!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"target_vol": "none" if self.target_vol is None else str(self.target_vol),
               "n": str(self.n)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> FrogVolParams:
    if not isinstance(params, FrogVolParams):
        raise TypeError(f"params must be FrogVolParams, got {type(params).__name__}")
    return params


def _braked(history: Mapping[str, History], inner: tuple[Target, ...], data_date: date,
            p: FrogVolParams) -> tuple[Target, ...]:
    if p.target_vol is None:
        return inner
    return _scaled(inner, basket_scale(history, inner, data_date, p.n, p.target_vol))


class FrogOwnVolAllocator:
    """M0036's drizzle-blend targets scaled by target_vol / the basket's own realized vol."""

    id = "M0044"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(FROG.lookback(p.inner), p.n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return FROG.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        return FROG.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        return FROG.uses_members(_check(params).inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = FROG.targets(history, members, data_date, held, p.inner)
        return _braked(history, inner, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return FROG.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = FROG.targets_prepared(prepared, members, data_date, held, p.inner)
        return _braked(prepared.history, inner, data_date, p)


FROGVOL = FrogOwnVolAllocator()
BLEND = FipParams(N20, mode="blend", base="momentum")  # M0036-BLEND's params, verbatim


def _v(suffix: str, target_vol: str | None, rationale: str) -> Candidate:
    tv = None if target_vol is None else Decimal(target_vol)
    return Candidate(id=f"M0044-{suffix}", family="M0044", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FROGVOL, params=FrogVolParams(BLEND, tv, 21),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0044",
    name="A brake on the quietest book: the drizzle blend under an own-volatility target",
    family="stock-momentum-attention",
    source_kind="variation",
    source_ref="M0036-BLEND (Da, Gurun & Warachka 2014) + M0001's own-volatility overlay "
               "(Barroso & Santa-Clara 2015) at M0033's targets, on monthly-hold-frac-gotrade",
    parent_id="M0036",
    hypothesis=(
        "M0036-BLEND has the best gains-to-losses ratio of any real-fee book in the lab (2.17) "
        "and the lowest turnover (6.42 against 8.4-9.5 for every other real-fee book), earning "
        "11.95% a year money-weighted against 7.19% for deposit-matched SPY, and it fails one "
        "condition only: a 22.28% worst fall against the 20% limit, taken between 17 July and 31 "
        "August 1998. Low turnover matters here because a position-size brake works by trading "
        "exposure up and down, and at Gotrade's real fees the cheapest book to brake is the one "
        "that already trades least. This method puts M0001's own-volatility target over "
        "M0036-BLEND's picks, at the same targets M0033 measured on the residual book, and "
        "nothing else changes. M0033 priced this exact brake on a sibling: on M0032 it took the "
        "fall from 20.65% to 19.98% at a 22% target (costing 1.2 points of annual money-weighted "
        "return), to 19.94% at 18% (2.1 points) and to 16.39% at 14% (3.9 points). I therefore "
        "EXPECT THIS TO FAIL, and I am registering it so the expectation is measured rather than "
        "assumed: buying 2.3 points of fall at roughly a point and a half of return per point of "
        "fall would cost about three points and land near 9% a year, still above the "
        "deposit-matched market but well below the 13.68% of the book the owner already has, and "
        "the luck score would likely drop below the 0.90 bar as the daily Sharpe falls. The one "
        "way it surprises me is if the drizzle book's falls are concentrated in weeks where the "
        "BOOK itself was visibly jumpy beforehand -- 1998 and 2011 were both preceded by rising "
        "volatility, unlike the calm pre-fall markets that defeated M0002 -- in which case the "
        "brake catches more of the fall per point of return than it did on the residual book. "
        "Variants: own-vol targets of 22%, 18% and 14% on a 21-session reading, plus one "
        "no-brake control re-stating BLEND under the same allocator so the comparison is "
        "within-run; the control should reproduce M0036-BLEND's numbers exactly."
    ),
    expected_failure=(
        "The 1998 fall arrived faster than a one-month volatility reading can follow, so the "
        "light 22% target sits at full exposure through it and buys almost nothing, the 18% "
        "target buys about a point of fall and stays above 20%, and only the 14% target clears "
        "the limit -- at a cost of three to four points of yearly return and a luck score under "
        "0.90. A second way it fails: a calm, continuous-momentum basket has low own volatility "
        "most of the time, so the brake binds rarely and then all at once, and the monthly "
        "resize trades it places at the bottom of a fall lock in losses that the unbraked book "
        "would have recovered; the braked variants then lose return without a matching fall cut."
    ),
    candidates=(
        _v("TV22-N21", "0.22", "The lightest brake: binds only in a crash"),
        _v("TV18-N21", "0.18", "The middle target: expected to buy about a point of fall"),
        _v("TV14-N21", "0.14", "The hard brake: expected to clear 20% at a large cost in return"),
        _v("NOBRAKE", None, "Control: M0036-BLEND re-stated under this allocator, no brake"),
    ),
    seen_keys=("concept:frog-in-the-pan-own-vol",),
)
