"""M0334 — Gradual cash switch: scale the 12-1 momentum book out as SPY nears its 200-day line.

Source: variation of M0332 (its plain 12-1 control and its no-switch twin).
Idea: M0332 showed the SPY 200-day switch is what keeps a 20-name momentum book survivable (worst
fall 61-67% without it, 23-25% with it). The switch is all or nothing, and in a rising decade the
time it spends in cash is a large part of the shortfall to SPY. Hold the picker fixed (12-1, top
20, equal weight, F4's screen) and replace the gate with a graded one: the invested fraction is
a straight ramp in SPY's distance from its 200-day average, stepped to 5% so the book does not
re-size every month for nothing. The ramps pick where the ladder sits relative to the line.

``GRAD`` reuses ``FACTOR`` with the gate off and scales each target's weight by that fraction;
the picker is untouched, so the arms differ only in how much of the book is out. Pure; reads only
bars dated <= data_date.
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
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FACTOR, FactorParams, factor_lookback
from seer_engine.strategies.indicators import sma_window

ADDED = date(2026, 10, 24)

STEP = Decimal("0.05")
PICK = FactorParams(rank="momentum", top=20, mom_n=252, mom_skip=21, trend=None)


@dataclass(frozen=True, slots=True)
class Params:
    """Exposure ladder. ``flat`` > 0 holds that percent always (no opinion); otherwise the
    invested fraction is 100% when SPY is ``full`` percent or more above its 200-day average,
    0% when it is ``zero`` percent or more below, and a straight line between."""

    full: int = 0
    zero: int = 0
    flat: int = 0
    sma_n: int = 200

    def as_dict(self) -> dict[str, str]:
        return {"full_pct": str(self.full), "zero_pct": str(self.zero), "flat_pct": str(self.flat),
                "sma_n": str(self.sma_n)}


def exposure(history: Mapping[str, History], data_date: date, p: Params) -> Decimal:
    """Invested fraction on data_date, floored to STEP; 0 when SPY has too few bars."""
    if p.flat:
        return Decimal(p.flat) / 100
    h = history.get("SPY")
    i = None if h is None else h.index_of(data_date)
    if h is None or i is None or i + 1 < p.sma_n:
        return Decimal(0)
    window = h.close[i + 1 - p.sma_n : i + 1].reshape(1, p.sma_n)
    dist = float(window[0, -1] / sma_window(window, p.sma_n)[0] - 1.0) * 100.0  # percent
    lo, hi = -float(p.zero), float(p.full)
    f = 1.0 if dist >= hi else 0.0 if dist <= lo else (dist - lo) / (hi - lo)
    return (Decimal(repr(f)) / STEP).to_integral_value(rounding="ROUND_DOWN") * STEP


class GradAlloc:
    """The F4 12-1 top-20 targets with every weight scaled by the SPY-ladder fraction."""

    id = "M0334"

    def lookback(self, params: Params) -> int:
        return max(factor_lookback(PICK), params.sma_n)

    def symbols(self, params: Params) -> tuple[str, ...]:
        return ("SPY",)

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Params) -> bool:
        return True

    def _scale(self, base: tuple[Target, ...], f: Decimal) -> tuple[Target, ...]:
        if f <= 0:
            return ()
        out = []
        for t in base:
            try:
                out.append(replace(t, weight=to_weight(t.weight * f)))
            except ValueError:  # a slice that floors to nothing
                continue
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        f = exposure(history, data_date, params)
        if f <= 0:
            return ()
        return self._scale(FACTOR.targets(history, members, data_date, held, PICK), f)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return FACTOR.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        f = exposure(prepared.history, data_date, params)
        if f <= 0:
            return ()
        return self._scale(FACTOR.targets_prepared(prepared, members, data_date, held, PICK), f)


GRAD = GradAlloc()


def _g(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0334-{suffix}", family="M0334", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=GRAD, params=params, rationale=rationale, added=ADDED, owner_inputs=())


def _f(suffix: str, trend, rationale: str) -> Candidate:
    return Candidate(id=f"M0334-{suffix}", family="M0334", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FACTOR, params=replace(PICK, trend=trend), rationale=rationale,
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0334",
    name="Gradual cash switch: scale the momentum book out as SPY nears its 200-day line",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="M0332",
    parent_id="M0332",
    hypothesis=(
        "M0332 found the SPY 200-day switch is what keeps a 20-name 12-1 momentum book inside the "
        "fall bar (23-25% worst fall with it, 61-67% without). Hold the picker fixed (12-1, top 20, "
        "equal weight, monthly, fractional, Gotrade fees) and swap the all-or-nothing gate for an "
        "invested fraction that is a straight ramp in SPY's distance from its 200-day average, in "
        "5% steps. Three ramps: UP (full at 3% above the line, zero at the line: exits early), "
        "DOWN (full at the line, zero at 5% below: exits late), MID (full at 3% above, zero at 3% "
        "below). Arms beside them: the hard switch (the M0332 control, re-run here), no switch, and "
        "a flat 50% book with no opinion at all, which prices the benefit of simply holding less "
        "against the ramps. Question: does a graded exit keep the fall at or under the screen with "
        "less time in cash, and does the ramp beat the flat 50%, or is it just a smaller bet? "
        "Trend rules are old (Faber 2007 and earlier), so the dev window sits after publication; "
        "2009-2015 is the first filter, being a bull decade where cash time costs most."
    ),
    expected_failure=(
        "The ramps fail the fall bar like M0287's graded vote: a partial exposure is never fully "
        "out in 2008 and the book loses a slice of the crash that the hard switch avoids, so the "
        "worst fall rises above the hard switch's 23% without enough extra return to pay for it. "
        "UP may trade the same as the hard switch and only add fees; DOWN is the likely worst "
        "(holding through the first leg of a fall). The flat 50% arm probably wins on fall and "
        "loses on return, which would say the ramp is a smaller bet and not a better one. In "
        "2009-2015 every arm lags SPY through the 2011 and 2015 dips."),
    candidates=(
        _f("HARD", ("SPY", 200), "control: the hard all-or-nothing switch, 12-1 top 20"),
        _f("NOSW", None, "dressing: always invested, no opinion, the switch's full price"),
        _g("UP", Params(full=3, zero=0), "ramp: full 3% above the line, zero at the line"),
        _g("DOWN", Params(full=0, zero=5), "ramp: full at the line, zero 5% below it"),
        _g("MID", Params(full=3, zero=3), "ramp: full 3% above, zero 3% below"),
        _g("HALF", Params(flat=50), "dressing: always half invested, no opinion about the market"),
    ),
    seen_keys=("concept:graded-trend-exposure-ramp", "concept:spy-200d-gradual-cash-switch"),
)
