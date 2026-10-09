"""M0054 — Drizzle picks without the cash periods: park in SPY instead of cash when the trend switch is off.

Source: a variation of M0044 (and through it M0036-BLEND, Da, Gurun & Warachka 2014's
frog-in-the-pan continuity ranked together with 12-1 momentum).
Idea: M0036-BLEND and M0044 earn their whole edge over SPY in 2002-2008, when the SPY-200 trend
switch held them in cash through the crash, and trail SPY by 4.8 to 7.1 points a year in
2009-2015. That separates two things the lab has been scoring as one: the switch's cash and the
picking. This method keeps the picks and changes only what the book holds while the switch is off.

    * ALWAYS-IN: the switch removed; the same twenty drizzle-blend names every month, always.
    * PARK-SPY: the switch kept, but while it is off the whole book holds SPY instead of cash.
    * HALF-PARK: the switch kept; while it is off, half the book holds SPY and half is cash.

The PARK allocator calls M0036's ``FROG`` with the trend switch on; when ``trend_on`` reads off
it targets SPY at ``park`` of equity. Same screen, top-20, equal weights, monthly, fractional
shares at Gotrade's real fees on ``monthly-hold-frac-gotrade``. No leverage. Every piece reads
only bars dated <= d.
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
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND, ResidPrepared
from seer_engine.lab.methods.m0036_frog_in_the_pan import FROG, FipParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import trend_on

ADDED = date(2026, 10, 9)


@dataclass(frozen=True, slots=True)
class ParkParams:
    inner: FipParams  # must carry a trend switch: the park only fills the switch's off months
    park: Decimal = Decimal(1)  # share of equity held in ``hold`` while the switch is off
    hold: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FipParams):
            raise TypeError(f"inner must be FipParams, got {type(self.inner).__name__}")
        if self.inner.inner.trend is None:
            raise ValueError("inner must have a trend switch; without one there is nothing to park")
        if not isinstance(self.park, Decimal) or not Decimal(0) < self.park <= Decimal(1):
            raise ValueError(f"park must be a Decimal in (0, 1], got {self.park!r}")
        if not isinstance(self.hold, str) or not self.hold:
            raise ValueError(f"hold must be a non-empty symbol, got {self.hold!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"park": str(self.park), "hold": self.hold}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ParkParams:
    if not isinstance(params, ParkParams):
        raise TypeError(f"params must be ParkParams, got {type(params).__name__}")
    return params


def _parked(history: Mapping[str, History], data_date: date, p: ParkParams) -> tuple[Target, ...]:
    h = history.get(p.hold)
    if h is None or h.index_of(data_date) is None:
        return ()
    t = target_from_close(p.hold, last_close(h, data_date), p.park)
    return () if t is None else (t,)


class DrizzleParkAllocator:
    """M0036's drizzle-blend book while the SPY-200 switch is on; ``park`` of equity in SPY while off."""

    id = "M0054"

    def lookback(self, params: Any) -> int:
        return FROG.lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted(set(FROG.symbols(p.inner)) | {p.hold}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).hold,)

    def uses_members(self, params: Any) -> bool:
        return FROG.uses_members(_check(params).inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner.inner):
            return _parked(history, data_date, p)
        return FROG.targets(history, members, data_date, held, p.inner)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return FROG.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner.inner):
            return _parked(prepared.history, data_date, p)
        return FROG.targets_prepared(prepared, members, data_date, held, p.inner)


PARK = DrizzleParkAllocator()
BLEND = FipParams(N20, mode="blend", base="momentum")  # M0036-BLEND's params, verbatim
BLEND_NOTREND = FipParams(N20_NOTREND, mode="blend", base="momentum")


def _c(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0054-{suffix}", family="M0054", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0054",
    name="Drizzle picks without the cash periods: park in SPY instead of cash when the trend switch is off",
    family="stock-momentum-attention",
    source_kind="variation",
    source_ref="M0044 / M0036-BLEND (Da, Gurun & Warachka 2014), with the SPY-200 switch's cash "
               "replaced by SPY or removed, on monthly-hold-frac-gotrade",
    parent_id="M0044",
    hypothesis=(
        "The drizzle blend (M0036-BLEND: twenty stocks ranked on 12-1 momentum rank plus "
        "continuity rank) and its braked twin M0044 earn their whole edge over SPY in 2002-2008, "
        "when the SPY-200 trend switch held them in cash through the crash, and trail SPY by 4.8 "
        "(BLEND) to 7.1 (M0044-TV14) points a year in 2009-2015, the best-covered era of the "
        "data. That says the stock picking itself may add nothing and the switch's cash is doing "
        "the work. This method separates the two. ALWAYS-IN removes the switch and holds the same "
        "twenty picks every month; it measures the picking alone. PARK-SPY keeps the switch but "
        "holds SPY instead of cash while it is off, so the book is always in the market and the "
        "picks only ever replace SPY; HALF-PARK holds half SPY, half cash while the switch is off. "
        "Same screen, monthly, equal weights, fractional shares at Gotrade's real fees, 5,000,000 "
        "IDR added on the 25th. Expected: in 2009-2015 the switch was on almost all the time, so "
        "all three variants should look like BLEND there and still trail SPY by roughly 4-5 points "
        "a year; if ALWAYS-IN trails SPY over 2009-2015, the drizzle signal adds nothing in this "
        "universe in the modern era and the family should be closed. Over the whole dev window "
        "ALWAYS-IN and PARK-SPY should take the full 2000-2002 and 2008 falls (SPY fell about "
        "55%), so their worst fall breaks the 20% limit by a wide margin, while HALF-PARK lands "
        "between. None of the three is expected to be eligible; the method is registered as the "
        "diagnostic the family's next decision rests on."
    ),
    expected_failure=(
        "The way this fails to be informative: the switch was not idle in 2009-2015 (it was off "
        "for parts of 2010, 2011 and 2015), so ALWAYS-IN's 2009-2015 gap differs from BLEND's for "
        "switch reasons, not picking reasons; the within-run comparison PARK-SPY vs ALWAYS-IN "
        "then carries the answer. The way it fails as a strategy: worst fall 40% or more for "
        "ALWAYS-IN and PARK-SPY in 2008, at most a point a year of return over SPY in exchange, "
        "and a luck score far below 0.90. A surprise would be ALWAYS-IN beating SPY in 2009-2015, "
        "which would mean the switch's whipsaws, not the picking, cost BLEND its modern-era return."
    ),
    candidates=(
        _c("ALWAYS-IN", FROG, BLEND_NOTREND,
           "The drizzle-blend twenty with the trend switch removed: the picking alone"),
        _c("PARK-SPY", PARK, ParkParams(BLEND, Decimal(1)),
           "Drizzle-blend twenty while SPY is above its 200-day average, all SPY while it is below"),
        _c("HALF-PARK", PARK, ParkParams(BLEND, Decimal("0.5")),
           "Drizzle-blend twenty while the switch is on; half SPY, half cash while it is off"),
    ),
    seen_keys=("concept:frog-in-the-pan-park-spy", "concept:frog-in-the-pan-no-trend-switch"),
)
