"""M0125 — Stop fighting the market's shape: the same fifty members, weighted by how heavily they trade.

Source: variation of M0117-C, the lab's signal-free control book; insight 91 (equal weighting as a
bet against the market's shape); M0034 for the dollar-volume weighting and the water-filling cap.

Idea: M0117-C holds the fifty most heavily traded index members in equal 2% slots, monthly, on the
owner's deposits at Gotrade's real fees, and earned 6.5% a year against SPY's 7.2% over 1996-2015
while falling 57%. It has no signal in it at all, so that half-point shortfall is the price of the
book's *shape*, paid before any picking starts. This method changes exactly one thing: how the
fifty slots are sized. The fifty names are M0117-C's, chosen the same way, on the same screen, on
the same cadence, rules preset and funding.

WHY THIS IS NOT M0122 OR M0034 AGAIN. Both of those weighted a book that already had a signal in it
(a momentum top-20, three event-drift books) by trading value, and both found that the weighting
mostly trades return for concentration. Neither asked the question on the base book with no signal,
which is the only place the answer says something about the lab's yardstick rather than about one
signal. If weighting the plain book closes the gap to SPY, then near misses that beat SPY by half
a point may only be winning the weighting fight; if it does not, insight 91's explanation of the
shortfall is wrong and the lab should stop blaming the shape.

WHAT THE WEIGHT READS. The 20-day mean of close times volume, which ``f_factor`` already computes
for every name as its liquidity screen. The lab's market-cap figure is known to be broken (an
unadjusted share count times a split-adjusted close), and EDGAR share counts begin in 2009; trading
value is sound from 1993 and is the size stand-in M0034 measured against market value (rank
correlation about 0.69 across the eligible set).

FIVE VARIANTS, ONE DIAL.
  * EQ: equal 2% slots, M0117-C's configuration under this allocator, the matched control so the
    comparison is inside one recorded batch.
  * DV: weight proportional to trading value, no ceiling. The full lean.
  * DV-C10 / DV-C05: the same, with no name above 10% / 5%, the excess spread over the names still
    under the ceiling (water-filling). Both ceilings are at least the 2% mean, so always feasible.
  * SQRT: weight proportional to the square root of trading value, the half-way house.

Every weight sums to the same total as the equal book (the names present / ``top``), so the dial
moves money between names and never changes how much is invested. Pure; reads only bars dated
<= ``data_date`` (the 20-day window ending on it).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0117_index_tenure_exclusion import TenureParams, liquid_rows
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import DV_N, FactorPrepared, prepare_factor

ADDED = date(2026, 10, 16)

#: How the chosen slots are sized. ``equal`` is M0117-C's; the rest read trading value.
WEIGHTINGS: tuple[str, ...] = ("equal", "dv", "sqrt")


@dataclass(frozen=True, slots=True)
class WeightParams:
    """M0117-C's book (``inner``, no exclusion) plus the one dial this method moves.

    ``cap`` is an absolute per-name ceiling (0.05 = 5% of the account), None for none.
    """

    inner: TenureParams = TenureParams()
    weighting: str = "equal"
    cap: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.inner, TenureParams):
            raise TypeError(f"inner must be TenureParams, got {type(self.inner).__name__}")
        if self.inner.min_tenure_months != 0:
            raise ValueError("inner must exclude nobody: this method holds M0117-C's universe")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if self.cap is not None:
            if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
                raise TypeError(f"cap must be a number or None, got {type(self.cap).__name__}")
            if not (1.0 / self.inner.top <= float(self.cap) <= 1.0):
                raise ValueError(f"cap must lie in [1/top, 1], got {self.cap}")
            if self.weighting == "equal":
                raise ValueError("cap is meaningless on equal weights")

    def as_dict(self) -> dict[str, str]:
        out = {"weighting": self.weighting, "cap": "none" if self.cap is None else repr(float(self.cap))}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> WeightParams:
    if not isinstance(params, WeightParams):
        raise TypeError(f"params must be WeightParams, got {type(params).__name__}")
    return params


def book_weights(dvs: list[float], p: WeightParams) -> list[Decimal | None]:
    """One weight per chosen name, Σ = len(dvs) / top, the same exposure as the equal book."""
    if not dvs:
        return []
    top = p.inner.top
    if p.weighting == "equal":
        eq = equal_weight(top)
        return [eq for _ in dvs]
    size = np.array(dvs, dtype=np.float64)
    raw = size if p.weighting == "dv" else np.sqrt(size)
    w = raw / float(raw.sum()) * (len(dvs) / top)
    if p.cap is not None:
        w = _apply_ceiling(w, float(p.cap))
    return [_floor_weight(float(x)) for x in w]


class VolumeWeightedIndexAllocator:
    """M0117-C's fifty most traded index members, sized by the dial in ``WeightParams``.

    Each month is a fresh pick: the targets are exactly the new top set, so a name that drops out
    is sold and a held name is resized to its new weight by the book engine.
    """

    id = "M0125"
    market_fields = ()  # members only, which every store carries

    def lookback(self, params: Any) -> int:
        _check(params)
        return DV_N

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, fp: FactorPrepared, members: AbstractSet[str], data_date: date, p: WeightParams) -> tuple[Target, ...]:
        rows = liquid_rows(fp, members, data_date, p.inner)
        rows.sort(key=lambda r: (-r[0], r[1]))  # most traded first, ties by symbol
        chosen = rows[: p.inner.top]
        out: list[Target] = []
        for (_, symbol, close), weight in zip(chosen, book_weights([r[0] for r in chosen], p), strict=True):
            if weight is None:
                continue
            target = target_from_close(symbol, close, weight)
            if target is not None:
                out.append(target)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(prepare_factor(history), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> FactorPrepared:
        return prepare_factor(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


VOLWEIGHT = VolumeWeightedIndexAllocator()


def _v(suffix: str, params: WeightParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0125-{suffix}", family="M0125", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=VOLWEIGHT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0125",
    name="Stop fighting the market's shape: the same fifty members, weighted by how heavily they trade instead of equally",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref=(
        "variation of M0117-C (the signal-free fifty-name control); insight 91; M0034 for the "
        "trading-value weighting and the per-name ceiling; M0122 for the same swap on picked books"
    ),
    parent_id="M0117",
    hypothesis=(
        "M0117 produced the control the lab never had: the fifty most heavily traded index members "
        "in equal 2% slots, on the owner's real deposits at Gotrade's real fees, earned 6.5% a year "
        "against SPY's 7.2% and fell 57%, over 1996-2015. That is a half-point-a-year structural "
        "handicap paid before any signal is added, and insight 91 says the cause is equal weighting "
        "betting against the market's shape. This tests the fix directly and changes exactly one "
        "thing: keep M0117-C's universe, screen, monthly cadence, rules preset (monthly-hold-frac-"
        "gotrade: fractional shares at Gotrade's real fees) and funding, and weight each holding by "
        "its 20-day mean dollar volume instead of 1/50. Dollar volume stands in for size because the "
        "lab's market-cap figure is broken and EDGAR share counts start in 2009, while trading value "
        "is sound from 1993 and needs no new data. Variants: EQ, M0117-C's equal weight re-run under "
        "this allocator as the matched control; DV, raw trading-value weight; DV-C10 and DV-C05, the "
        "same with no name above 10% or 5%; SQRT, square-root weight as a half-way house. M0122 "
        "already showed this swap costs return on books that carry a signal; this asks it on the "
        "book with none, which is what says whether the lab's yardstick is biased. M0123-TOP20 (the "
        "twenty most traded, equal) earned 7.3% against TOP50's 6.5%, a hint that leaning toward "
        "the biggest names helps the plain book. Success: a weighted version closes most of the "
        "half-point gap to SPY AND cuts the 57% fall materially, and does so in 2009-2015 too. "
        "Weighting by size is not a published anomaly; it is how SPY itself is built, so there is "
        "no edge here to fade -- the best outcome is matching SPY, not beating it."
    ),
    expected_failure=(
        "The most likely result is that no version beats SPY and none fixes the fall. Fifty large "
        "companies weighted by size is a rough copy of SPY with fifty names instead of five hundred, "
        "so at best it tracks SPY minus Gotrade's fees on monthly resizing, and minus the fee "
        "minimum's bite on the many small slots early on. The 57% fall is 2000-2002 and 2008, "
        "which SPY itself fell 55% through; weighting cannot remove a market fall, only reshuffle "
        "it, so the worst-fall condition probably stays failed on every variant and the luck score "
        "stays far under 0.90. The interesting failure is closing the return gap while keeping the "
        "fall, which would say the handicap and the risk have different causes. The uncapped DV "
        "version may concentrate in one or two giants (M0034's SIZE put up to 61% in one stock) and "
        "fall harder than equal in 2000-2002, when the most traded names were the tech leaders. "
        "Survivorship cuts against this test too: the dev store is missing many of the small dead "
        "members, so the equal-weight control is flattered and the gap it shows is understated."
    ),
    candidates=(
        _v("EQ", WeightParams(weighting="equal"),
           "Equal 2% slots: M0117-C's book under this allocator, the matched control"),
        _v("DV", WeightParams(weighting="dv"),
           "Each name weighted by its 20-day mean dollar volume, no ceiling"),
        _v("DV-C10", WeightParams(weighting="dv", cap=0.10),
           "Dollar-volume weights, no name above 10%, the excess spread over the rest"),
        _v("DV-C05", WeightParams(weighting="dv", cap=0.05),
           "Dollar-volume weights, no name above 5%, the excess spread over the rest"),
        _v("SQRT", WeightParams(weighting="sqrt"),
           "Weights proportional to the square root of dollar volume: half the concentration"),
    ),
    seen_keys=(
        "concept:size-weighted-index-book",
        "concept:equal-weight-versus-cap-weight-base-book",
    ),
)
