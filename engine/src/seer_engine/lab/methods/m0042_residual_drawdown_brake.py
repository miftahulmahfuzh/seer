"""M0042 — The real-fee fractional residual book under a drawdown brake (M0033 variation).

Source: variation of M0033, driven by its result. M0033's own-volatility brake could not cut the
residual book's worst fall (Jul-Aug 1998) because that fall starts in calm weather: a brake that
reads last month's jumpiness is off on the way in and on during the rebound. A drawdown brake
makes no forecast. It reads the held basket's distance below its own running peak and cuts
exposure once the loss passes a threshold.

Idea: reuse M0013's ``basket_drawdown`` and ``brake_scale`` unchanged (equal-weight basket of
what the book holds tonight, 126-session peak, full size above -d, linear down to ``floor`` at
-2d) on M0032-N20-RAW-FRAC-GT's own targets (``RESIDMOM`` with ``RAW20``). The allocator sees
bars only, never the account, so "the account's own fall" is the held basket's fall, exactly as
in M0013.

Why a third arm
---------------
A brake rides on a resize cadence: the brake only acts when the book is re-weighted, and a
weekly resize costs fees an unbraked monthly book never pays. Comparing a braked weekly book
with the monthly parent would mix the brake's opinion with the cost of acting on it. So one
variant (NOBRAKE-MW) runs the same weekly cadence with the brake held at scale 1 (floor 1): the
always-invested book with the opinion removed. Brake minus that arm is the opinion; that arm
minus the monthly parent is the habit. ``lab dressing M0042`` reads the pair.

Everything is fixed here before any result. Every piece reads only bars dated <= d.
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
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, ResidParams, ResidPrepared
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0013_basket_drawdown_brake import (
    MOM20_TREND,
    BrakeParams,
    _scaled,
    basket_drawdown,
    brake_scale,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import (
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
)
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 25)


@dataclass(frozen=True, slots=True)
class ResidBrakeParams:
    """RESIDMOM params plus M0013's drawdown brake; ``floor`` 1 switches the brake off."""

    inner: ResidParams
    d: Decimal = Decimal("0.08")
    floor: Decimal = Decimal("0.25")
    peak_n: int = 126

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if not isinstance(self.d, Decimal) or not (0 < self.d < Decimal("0.5")):
            raise ValueError(f"d must be a Decimal in (0, 0.5), got {self.d!r}")
        if not isinstance(self.floor, Decimal) or not (0 <= self.floor <= 1):
            raise ValueError(f"floor must be a Decimal in [0, 1], got {self.floor!r}")
        if isinstance(self.peak_n, bool) or not isinstance(self.peak_n, int) or self.peak_n < 2:
            raise ValueError(f"peak_n must be an int >= 2, got {self.peak_n!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"d": str(self.d), "floor": str(self.floor), "peak_n": str(self.peak_n)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ResidBrakeParams:
    if not isinstance(params, ResidBrakeParams):
        raise TypeError(f"params must be ResidBrakeParams, got {type(params).__name__}")
    return params


def _braked(history: Mapping[str, History], inner: tuple[Target, ...], data_date: date,
            held: frozenset[str], p: ResidBrakeParams) -> tuple[Target, ...]:
    if p.floor == 1:
        return inner
    symbols = tuple(sorted(held)) if held else tuple(t.symbol for t in inner)
    dd = basket_drawdown(history, symbols, data_date, p.peak_n)
    return _scaled(inner, brake_scale(dd, BrakeParams(MOM20_TREND, p.d, p.floor, p.peak_n)))


class ResidDrawdownBrakeAllocator:
    """RESIDMOM's targets scaled while the held basket sits well below its six-month peak."""

    id = "M0042"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(RESIDMOM.lookback(p.inner), p.peak_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        return RESIDMOM.uses_members(_check(params).inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = RESIDMOM.targets(history, members, data_date, held, p.inner)
        return _braked(history, inner, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = RESIDMOM.targets_prepared(prepared, members, data_date, held, p.inner)
        return _braked(prepared.history, inner, data_date, held, p)


RESIDBRAKE = ResidDrawdownBrakeAllocator()


def _v(suffix: str, d: str, floor: str, rules, rationale: str) -> Candidate:
    return Candidate(id=f"M0042-{suffix}", family="M0042", rules=rules, allocator=RESIDBRAKE,
                     params=ResidBrakeParams(RAW20, Decimal(d), Decimal(floor)),
                     added=ADDED, owner_inputs=(), rationale=rationale)


_MW = MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE

METHOD = Method(
    id="M0042",
    name="The real-fee fractional residual book under a drawdown brake",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="M0033 (own-volatility brake failed on the 1998 fall) + M0013's basket drawdown "
               "brake, on M0032-N20-RAW-FRAC-GT at Gotrade fees, funded monthly",
    parent_id="M0033",
    hypothesis=(
        "M0033's volatility brake left the residual book's worst fall at about 20% because the "
        "fall (Jul-Aug 1998) starts in calm weather and the brake reads the past. A brake on the "
        "held basket's own distance below its 126-day peak responds to the loss instead of "
        "predicting it: full size above -d, linear down to a 25% floor at -2d, re-checked weekly. "
        "Five variants fixed in advance: D8 (the main bet), D6 (earlier, expects whipsaw), D12 "
        "(later, expects too late to help), D8-M (monthly check, the cadence paper runs today) and "
        "NOBRAKE-MW (weekly cadence, brake off: the opinion-free arm). Published idea: "
        "drawdown-control overlays are old (Grossman-Zhou 1993); momentum crash literature "
        "(Daniel-Moskowitz 2016) is 2016, so a dev edge is pre-crowd. I expect the brake to cut "
        "the fall by 2-4 points at a cost of 1-3 points a year, a worse rate than the 0.76 "
        "points of return per point of fall M0011 measured, and I expect 2009-2015 to show it "
        "as pure drag because that era had no bear market."
    ),
    expected_failure=(
        "Whipsaw, as M0013 and M0019 found. The brake sells after the fall has started and "
        "buys back after the recovery has started, so the worst fall hardly moves and the "
        "return drops: V-shaped rebounds (2009) are missed until the basket makes a new high. "
        "The weekly cadence also pays more fees than the monthly parent's 1,607 trades, so "
        "NOBRAKE-MW may already trail M0032 before any brake opinion. If the best variant "
        "does not beat NOBRAKE-MW on return per point of fall, the book's drawdown cannot be "
        "managed and should be accepted."
    ),
    candidates=(
        _v("D8-MW", "0.08", "0.25", _MW,
           "Main bet: brake from -8% to a 25% floor at -16%, weekly check"),
        _v("D6-MW", "0.06", "0.25", _MW, "Earlier trigger: acts sooner, expects whipsaw"),
        _v("D12-MW", "0.12", "0.25", _MW, "Later trigger: expects too late to help"),
        _v("D8-M", "0.08", "0.25", MONTHLY_HOLD_FRAC_GOTRADE,
           "Same brake on a monthly check: the cadence paper trades today"),
        _v("NOBRAKE-MW", "0.08", "1", _MW,
           "Control with no opinion: weekly cadence, brake off, always invested"),
    ),
    seen_keys=("concept:residual-momentum-own-drawdown-brake-fractional-gotrade",),
)
