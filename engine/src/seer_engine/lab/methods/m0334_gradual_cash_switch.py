"""M0334 — Gradual cash switch: scale the 12-1 momentum book out as SPY nears its 200-day line.

Source: variation of M0332. Its 12-1 hard-switch and no-switch trials are the controls.
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
from seer_engine.lab.method import Amendment, Method
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



# --------------------------------------------------------------------------- amendment 1

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0334 registered a flat half-weight book as its no-opinion arm and never registered the "
        "flat full-weight one, so the three ramps are priced against a book that is already "
        "half out of the market. The full rung of the method's own dial is the missing zero."
    ),
    hypothesis=(
        "M0334's hypothesis names M0332-M12-1-NOSW as the always-invested reference and reads it "
        "from the lab rather than re-running it, which was correct under the no-re-rolls rule and "
        "leaves the method's own run without a zero in it. M0389 then measured that a step-aside "
        "habit priced against another step-aside arm -- and a half-weight book is one -- is "
        "charged roughly half its standalone cost. This arm is the same picker, the same screen, "
        "the same monthly fractional Gotrade chassis and the same lookback as UP, DOWN, MID and "
        "HALF, at the one rung of the method's own exposure dial that never steps aside: "
        "``Params(flat=100)``, invested fraction 1 on every decision session, no bar read to "
        "decide it. It opens 1996-01-03 with the recorded four. The difference against it is what "
        "each ramp's cash time costs; the difference between that and M0334-HALF's is how much of "
        "the recorded safety was the ramp and how much was simply holding less. Success is those "
        "two terms separated, plus a check that this arm reproduces M0332-M12-1-NOSW -- the same "
        "book through a different allocator id -- which is the same reproduction check "
        "M0113-SMA200 was built to make against M0084-MONTHLY."
    ),
    expected_failure=(
        "The reproduction check may fail, and if it does the fault is almost certainly the "
        "scaling path rather than the picker: ``_scale`` rebuilds every target through "
        "``to_weight(t.weight * f)`` even at f = 1, and a rounding difference there would show up "
        "as a small, persistent drift against M0332-M12-1-NOSW. A drift of that kind invalidates "
        "every bill read off this arm and must be reported before any of them is quoted. Second, "
        "M0334's expected_failure already predicted that a partial exit fails the fall bar, and "
        "this arm will fail it by much more: M0332 recorded 61-67% worst falls for the unswitched "
        "20-name momentum book against the recorded 22.32% to 35.29% here. That is the arm "
        "working. Third, M0334-HALF is also an always-invested arm -- always invested at half "
        "weight, 49.48% exposure, 1474 trades -- and a reader could take it for the zero; the "
        "analysis must keep the two apart, because the whole point is that holding less is itself "
        "a safety device with a price. Fourth, this arm runs later than the arms it prices, and "
        "the fidelity evidence is the exact three-way reproduction of one configuration across "
        "two run dates measured on 2026-10-27."
    ),
    candidates=(
        _g("ALWAYS", Params(flat=100),
           "Yardstick: the same 12-1 top-20 book held at full weight on every decision session, "
           "no ramp and no opinion about the market, so what the ramps' cash time costs can be "
           "read off directly instead of against a book that is already half out"),
    ),
)


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
        "below). Beside them a flat 50% book with no opinion at all, which "
        "prices the benefit of simply holding less against the ramps. The hard switch and the "
        "always-invested book are M0332-M12-1 and M0332-M12-1-NOSW, already recorded on this "
        "exact configuration (the runner refuses a repeat), so they are read from the lab, not "
        "re-run; they share the preset, picker and store. Question: does a graded exit keep the fall at or under the screen with "
        "less time in cash, and does the ramp beat the flat 50%, or is it just a smaller bet? "
        "Trend rules are old (Faber 2007 and earlier), so the dev window sits after publication; "
        "2009-2015 is the first filter, being a bull decade where cash time costs most."
    ),
    expected_failure=(
        "The ramps fail the fall bar like M0287's graded vote: a partial exposure is never fully "
        "out in 2008 and the book loses a slice of the crash that the hard switch avoids, so the "
        "worst fall rises above the hard switch's 23% (M0332-M12-1) without enough extra return to pay for it. "
        "UP may trade the same as the hard switch and only add fees; DOWN is the likely worst "
        "(holding through the first leg of a fall). The flat 50% arm probably wins on fall and "
        "loses on return, which would say the ramp is a smaller bet and not a better one. In "
        "2009-2015 every arm lags SPY through the 2011 and 2015 dips."),
    candidates=(
        _g("UP", Params(full=3, zero=0), "ramp: full 3% above the line, zero at the line"),
        _g("DOWN", Params(full=0, zero=5), "ramp: full at the line, zero 5% below it"),
        _g("MID", Params(full=3, zero=3), "ramp: full 3% above, zero 3% below"),
        _g("HALF", Params(flat=50), "dressing: always half invested, no opinion about the market"),
    ),
    amendments=(AMEND_ALWAYS,),
    seen_keys=("concept:graded-trend-exposure-ramp", "concept:spy-200d-gradual-cash-switch"),
)
