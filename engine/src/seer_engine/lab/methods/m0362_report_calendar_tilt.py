"""M0362 — The report calendar as a tilt: lean a book that already works toward names due to report.

Source: variation of M0159 (Frazzini & Lamont 2007, NBER w13090, the earnings announcement
premium). M0159 used the due-to-report calendar to *choose* names and lost to SPY as a standalone
book; its due-versus-not-due gap was real in 2009-2015 (about 5 points a year) but a calendar that
picks only a few dozen names pays full fees for a thin pool. Here the calendar picks nothing. The
host is M0354-M1's book, plain 12-1 top-20 momentum behind the SPY 200-day switch, whose names
are chosen exactly as before; the calendar only moves *weight* among the names already held.

``TILT`` wraps ``FACTOR``. It takes the picker's targets, marks each held name due (an event in the
coming month's window a year ago and another a quarter ago, M0159's ``is_due``) or not due (enough
events in the window but not due), then multiplies due names' weight by ``due_mult`` and not-due
names' weight by ``notdue_mult``; names with too little news history keep weight 1. Weights are
renormalised to the picker's original total, so the book is as invested as the host in every
arm and the tilt cannot hide leverage or extra cash. With both multipliers 1 the allocator returns
the host's targets untouched: that arm is the unmodified control and the fidelity check against
M0354-M1 in one. The mirror (``notdue_mult`` > 1) is the reversing arm, and the always-invested
switch-off twins carry no opinion on the gate, so the cost of acting on the calendar and the cost
of the switch are priced apart. Pure; reads only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0157_earnings_month_premium import PremiumPrepared, events
from seer_engine.lab.methods.m0159_due_to_report_volume_calendar import DueParams, is_due
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import scale_weight
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FACTOR, FactorParams, prepare_factor, trend_on

ADDED = date(2026, 11, 3)

SWITCH = ("SPY", 200)
TOP = 20


@dataclass(frozen=True, slots=True)
class Params:
    """Multipliers on the held names' weight; (1, 1) is the unmodified host."""

    due_mult: Decimal = Decimal(1)
    notdue_mult: Decimal = Decimal(1)
    switch: bool = True

    def __post_init__(self) -> None:
        for name in ("due_mult", "notdue_mult"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite() or v <= 0:
                raise ValueError(f"{name} must be a positive Decimal, got {v!r}")

    def as_dict(self) -> dict[str, str]:
        return {"due_mult": str(self.due_mult), "notdue_mult": str(self.notdue_mult),
                "switch": str(self.switch)}

    def picker(self) -> FactorParams:
        return FactorParams(rank="momentum", top=TOP, mom_n=252, mom_skip=21,
                            trend=SWITCH if self.switch else None)

    def calendar(self) -> DueParams:
        return DueParams(self.picker())


def _tilt(prepared: PremiumPrepared, base: tuple[Target, ...], data_date: date,
          params: Params) -> tuple[Target, ...]:
    if not base or (params.due_mult == 1 and params.notdue_mult == 1):
        return base
    cal = params.calendar()
    mults: list[Decimal] = []
    for t in base:
        m = Decimal(1)
        h = prepared.history.get(t.symbol)
        cols = prepared.cols(t.symbol, cal.vol_base)
        i = h.index_of(data_date) if h is not None else None
        if cols is not None and i is not None:
            ev = events(cols[0], cols[1], i, cal)  # type: ignore[arg-type]
            if is_due(ev, i, cal):
                m = params.due_mult
            elif ev.size >= cal.min_events:
                m = params.notdue_mult
        mults.append(m)
    total = sum((t.weight for t in base), Decimal(0))
    mass = sum((t.weight * m for t, m in zip(base, mults, strict=True)), Decimal(0))
    out: list[Target] = []
    for t, m in zip(base, mults, strict=True):
        w = scale_weight(t.weight, m * total / mass)
        if w is not None:
            out.append(replace(t, weight=w))
    return tuple(out)


class TiltAlloc:
    """FACTOR's 12-1 top-20 with the report calendar moving weight among the names it holds."""

    id = "M0362"

    def lookback(self, params: Params) -> int:
        cal = params.calendar()
        return max(FACTOR.lookback(params.picker()), cal.window + cal.vol_base + 1)

    def symbols(self, params: Params) -> tuple[str, ...]:
        return FACTOR.symbols(params.picker())

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Params) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(history, data_date, p):
            return ()
        base = FACTOR.targets(history, members, data_date, held, p)
        return _tilt(PremiumPrepared(history, None), base, data_date, params)

    def prepare(self, history: Mapping[str, History]) -> PremiumPrepared:
        return PremiumPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        if not isinstance(prepared, PremiumPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared PremiumPrepared, got {type(prepared).__name__}")
        p = params.picker()
        if not trend_on(prepared.history, data_date, p):
            return ()
        base = FACTOR.targets_prepared(prepared.factor, members, data_date, held, p)
        return _tilt(prepared, base, data_date, params)


TILT = TiltAlloc()

_D2, _D4 = Decimal(2), Decimal(4)


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0362-{suffix}", family="M0362", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=TILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0362",
    name="The report calendar as a tilt: plain 20-name momentum, weight leaned toward names due to report",
    family="stock-earnings-announcement-premium",
    source_kind="variation",
    source_ref="Frazzini & Lamont 2007, NBER w13090; variation of M0159",
    parent_id="M0159",
    hypothesis=(
        "M0159's due-to-report calendar separated due from not-due by about 5 points a year in "
        "2009-2015 (the anomaly was published in 2007) but lost to SPY as a standalone book and fell "
        "to SPY's return once dead companies were added back. Use it only as a tie-breaker inside an "
        "existing eligible book: M0354-M1, plain 12-1 top-20 momentum, equal weight, SPY 200-day "
        "switch, fractional at Gotrade's real fees (a full 20 names at about $28 a slot cannot be "
        "whole shares). Among the names the book already holds, give due names 2x (and 4x) the "
        "weight of the rest, renormalised to the same total. Arms: BASE (no tilt; reproduces "
        "M0354-M1), DUE2, DUE4, NOTDUE2 (the mirror, the not-due tilt), and the always-invested "
        "BASE-NOSW and DUE2-NOSW so the switch's cost is priced apart from the calendar's "
        "opinion. Question: does the tilt beat the unmodified book in 2009-2015 on the dev store "
        "and on the survivorship-check store? Close the family if not."
    ),
    expected_failure=(
        "A tilt moves weight among names the book already owns, so it can change little: about a "
        "quarter of held names are due in a given month and most picks are the biggest, most "
        "heavily followed companies, where the premium is smallest and fades after 2007. Expect "
        "DUE2 within noise of BASE, DUE4 adding fees from the monthly resize toward changing "
        "weights, and NOTDUE2 not clearly worse. If the mirror does as well as the due tilt, the "
        "calendar carries no information beyond reweighting noise."
    ),
    candidates=(
        _v("BASE", Params(), "control: unmodified host book; reproduces M0354-M1"),
        _v("DUE2", Params(due_mult=_D2), "treatment: due names at 2x weight, switch on"),
        _v("DUE4", Params(due_mult=_D4), "dial end: due names at 4x weight, switch on"),
        _v("NOTDUE2", Params(notdue_mult=_D2), "mirror control: not-due names at 2x weight"),
        _v("BASE-NOSW", Params(switch=False), "always-invested control, no switch, no tilt"),
        _v("DUE2-NOSW", Params(due_mult=_D2, switch=False), "treatment with the switch off, always invested"),
    ),
    seen_keys=("concept:report-calendar-tilt-inside-eligible-book",
               "concept:earnings-announcement-premium-volume-calendar"),
)
