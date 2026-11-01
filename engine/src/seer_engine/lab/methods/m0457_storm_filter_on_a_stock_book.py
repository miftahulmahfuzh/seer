"""M0457 — Storm filter as an add-on: M0428's swing-based cash step laid over a stock book.

Source: variation of M0428 (Moreira & Muir 2017, Volatility-Managed Portfolios).
M0428 found the variance rule beat its always-invested twin by 0.6 to 0.9 points a year on SPY
alone but SPY alone cannot clear the fall bar. Here the same rule (M0423's ``exposure``,
imported, not re-implemented) scales every weight of M0133's 20-name asymmetry book. The base
book is M0133's because its recorded 2009-2015 record leads SPY: the stretch most like today.

Two bases, so the add-on is priced where it should help most and where it should be redundant:
the ungated book (a 74% fall, nothing else protecting it) and the same book behind the 200-day
trend switch (M0389 found a fear brake adds nothing over that switch). Every treatment has two
always-invested twins with no opinion: FLAT95 at the equal average exposure and FLAT100. The
weights scale by SPY's exposure only; the book's own picks are untouched. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0133_gated_updown_asymmetry import ASYM, N20, AsymParams
from seer_engine.lab.methods.m0423_volatility_managed_spy import Params as ExpParams
from seer_engine.lab.methods.m0423_volatility_managed_spy import exposure
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 1)


@dataclass(frozen=True, slots=True)
class Params:
    """``gate`` is the base book's own switch (``none`` or ``sma200``); ``exp`` the exposure rule."""

    gate: str = "none"
    exp: ExpParams = ExpParams(mode="flat", flat=100)

    def as_dict(self) -> dict[str, str]:
        return {"gate": self.gate, **{f"exp.{k}": v for k, v in self.exp.as_dict().items()}}

    def base(self) -> AsymParams:
        return AsymParams(N20, gate=self.gate)  # type: ignore[arg-type]


def _scale(inner: tuple[Target, ...], w: Decimal) -> tuple[Target, ...]:
    """Every weight times ``w``, floored to the quantum; targets that floor to zero drop."""
    if w >= 1:
        return inner
    out: list[Target] = []
    for t in inner:
        nw = (t.weight * w).quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)
        if nw > 0:
            out.append(Target(t.symbol, nw, t.last, t.limit, t.stop, t.take))
    return tuple(out)


class StormFilteredBook:
    """M0133's book (gate per params), its weights multiplied by the SPY exposure rule."""

    id = "M0457"

    def lookback(self, params: Params) -> int:
        return max(ASYM.lookback(params.base()), params.exp.n + 1)

    def symbols(self, params: Params) -> tuple[str, ...]:
        return tuple(sorted(set(ASYM.symbols(params.base())) | {"SPY"}))

    def holds(self, params: Params) -> tuple[str, ...]:
        return ASYM.holds(params.base())

    def uses_members(self, params: Params) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        inner = ASYM.targets(history, members, data_date, held, params.base())
        return _scale(inner, exposure(history, data_date, params.exp))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return ASYM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        inner = ASYM.targets_prepared(prepared, members, data_date, held, params.base())
        return _scale(inner, exposure(prepared.history, data_date, params.exp))


ALLOC = StormFilteredBook()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0457-{suffix}", family="M0457", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


_VAR25 = ExpParams(mode="var", n=21, target_pct=25)
_F95 = ExpParams(mode="flat", flat=95)
_F100 = ExpParams(mode="flat", flat=100)

METHOD = Method(
    id="M0457",
    name="Storm filter as an add-on: does a swing-based cash step help a stock book more than it helps SPY alone?",
    family="volatility-managed-exposure",
    source_kind="variation",
    source_ref="M0428",
    parent_id="M0428",
    hypothesis=(
        "M0428 found a swing-based exposure rule (weight = min(1, 25%^2 / SPY's 21-day annualized "
        "variance), 5% steps, monthly) beats an always-invested twin by about 0.6 to 0.9 points a "
        "year and trims the worst fall a few points, but SPY alone cannot clear the fall bar. Lay "
        "the same rule over M0133's 20-name up/down-asymmetry stock book (fractional, Gotrade "
        "fees, weights scaled, picks untouched), the book with the best recorded 2009-2015 "
        "record among eligible dev books. Published 2017; the dev window ends before the crowd "
        "traded it. Two bases: ungated (74% fall, nothing else protecting it) and behind the "
        "200-day trend switch (M0389: a fear brake adds nothing over that switch). 2x3 arms: "
        "U-VAR25, U-FLAT95, U-FLAT100 and G-VAR25, G-FLAT95, G-FLAT100. FLAT95 is the equal "
        "average exposure control (0.945 is SPY's monthly mean weight under the rule, M0428 "
        "analysis, 1993-2015, read before this run, no return), FLAT100 the zero of the dial. "
        "The signal is real if VAR25 beats FLAT95 on worst fall without losing return; the rule "
        "helps a book if the ungated gain exceeds M0428's SPY gain; it is redundant if the gated "
        "gain is about zero. Pass needs the worst fall to cut materially (25% bar) and the "
        "2009-2015 edge to stay positive against SPY."
    ),
    expected_failure=(
        "The filter's storms are 2000-02 and 2008, and an ungated stock book falls 74% largely "
        "in single names and the 2008 slide, which SPY variance catches late (it steps out after "
        "the first big drop). Expect the ungated gain to be a few points of fall and no return "
        "gain, the fall staying far above 25%. Behind the 200-day switch, expect no gain at all, "
        "as M0389 found, and a small loss from monthly 5% re-sizes paying Gotrade minimum fees "
        "on 20 slots. Average exposure under 100% is cash time in the 2009-2015 rising decade, "
        "so VAR25 and FLAT95 probably both lag FLAT100 there."
    ),
    candidates=(
        _v("U-VAR25", Params("none", _VAR25), "ungated asymmetry book, storm filter at 25% target"),
        _v("U-FLAT95", Params("none", _F95), "control: ungated book always 95% invested"),
        _v("U-FLAT100", Params("none", _F100), "control: ungated book always fully invested"),
        _v("G-VAR25", Params("sma200", _VAR25), "trend-switched book, storm filter at 25% target"),
        _v("G-FLAT95", Params("sma200", _F95), "control: switched book always 95% when in"),
        _v("G-FLAT100", Params("sma200", _F100), "control: switched book, no storm filter"),
    ),
    seen_keys=("concept:storm-filter-overlay-on-stock-book",),
)
