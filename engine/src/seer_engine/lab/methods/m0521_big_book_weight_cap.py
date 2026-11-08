"""M0521 — Does weighting the big-company book by size, with a ceiling per name, close its gap to SPY?

Variation of M0501 (itself a variation of M0500). M0500 and M0501 held the 25 largest index
members *equal weight* and trailed SPY by 1.3 to 1.8 points a year whatever the re-pick day. SPY
is cap-weighted: Apple is ~7% of it and the 25th name well under 1%. An equal-weight big-25 book
therefore bets against SPY's shape even when it holds the very same names. This method keeps M0501's
chassis and names, and changes only the weights: size share, with an optional ceiling per name in
the style of M0047/M0034 (water-filling: the excess of a capped name is spread over the rest).

Arms, all on M0079's ``daily-hold-frac-gotrade`` (fractional, Gotrade's real fees, asked every
session; names ranked once on the first session of the month and held to the next one):

    * **EQ25**: the control. M0501-DAY-FIRST rebuilt under a new id; expected to record as that
      arm's book twin, not a new book.
    * **SIZE25**: 25 names weighted by market value, no ceiling. The most SPY-like version.
    * **SIZE25-CAP10**: the same with each name capped at 10% (the M0047 ceiling).
    * **SIZE25-CAP06**: capped at 6%, between equal (4%) and the 10% ceiling.
    * **SIZE50-CAP10**: 50 names, size weighted, capped at 10%: closer still to SPY's breadth.
    * **SPY-ALWAYS**: SPY only on the same chassis, the frame with no opinion. Expected to be a book
      twin of M0500-SPY-ALWAYS / M0485-SPY-ALWAYS.

Assumptions written before any result. The book is decided on the close before the first session
of the month and fills at its open, as in M0501. Size is market value, one share class per company
(identical share count, larger value kept), over the standard member screen with the trend gate
off. Weights sum to 1 while the book is fully invested; a name with no bar that day leaves its slot
in cash. With no share counts or no names the arm holds SPY. Pure: reads only bars and share counts
dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0079_dividend_announcement_window import DAILY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0500_opex_week_big_stocks import (
    BENCH,
    LOOKBACK,
    OpexPrepared,
    _rows,
    _spy,
)
from seer_engine.lab.methods.m0501_rebalance_day_big25 import decision_date
from seer_engine.sim.book import Target
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import prepare_factor

ADDED = date(2026, 11, 8)
WEIGHTINGS = ("equal", "size", "spy")


@dataclass(frozen=True, slots=True)
class CapParams:
    """``weighting`` equal | size | spy; ``cap`` the ceiling per name as a share of the book."""

    weighting: str = "equal"
    top: int = 25
    cap: float | None = None

    def __post_init__(self) -> None:
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 100:
            raise ValueError(f"top must be an int in [1, 100], got {self.top!r}")
        if self.cap is not None and not 1.0 / self.top <= self.cap <= 1.0:
            raise ValueError(f"cap must lie in [1/top, 1], got {self.cap!r}")

    def as_dict(self) -> dict[str, str]:
        return {"weighting": self.weighting, "top": str(self.top), "cap": str(self.cap),
                "rank": "market-value", "class_rule": "identical-share-count", "day": "first"}


def _check(params: object) -> CapParams:
    if not isinstance(params, CapParams):
        raise TypeError(f"params must be CapParams, got {type(params).__name__}")
    return params


def biggest_sized(prep: OpexPrepared, rows: list, r: date, top: int) -> list[tuple[str, float]]:
    """The ``top`` largest screened members by market value on R, one class per company."""
    mk = prep.market
    by_count: dict[float, tuple[float, str]] = {}
    for row in rows:
        v = mk.market_value(row.symbol, r)
        n = mk.shares_on(row.symbol, r)
        if v is None or n is None or not (np.isfinite(v) and v > 0.0):
            continue
        seen = by_count.get(n)
        if seen is None or (float(v), row.symbol) > seen:
            by_count[n] = (float(v), row.symbol)
    ranked = sorted(by_count.values(), key=lambda x: (-x[0], x[1]))[:top]
    return [(s, v) for v, s in ranked]


def weights(sized: list[tuple[str, float]], p: CapParams) -> list[Any]:
    """One weight per name: 1/top each, or the size share (capped, excess spread over the rest)."""
    if p.weighting == "equal":
        raw = np.full(len(sized), 1.0 / p.top)
    else:
        v = np.array([x for _, x in sized], dtype=np.float64)
        raw = v / float(v.sum()) * (len(sized) / p.top)
        if p.cap is not None:
            raw = _apply_ceiling(raw, float(p.cap))
    return [_floor_weight(float(x)) for x in raw]


def _run(prep: OpexPrepared, members: AbstractSet[str], d: date, p: CapParams) -> tuple[Target, ...]:
    if prep.market is None:  # the market-aware contract: no panel, no targets, on every arm
        return ()
    if p.weighting == "spy":
        return _spy(prep.history, d)
    r = decision_date(d, "first")
    if r is None:
        return _spy(prep.history, d)
    sized = biggest_sized(prep, _rows(prep, members, r), r, p.top)
    out: list[Target] = []
    for (s, _), w in zip(sized, weights(sized, p), strict=True):
        h = prep.history.get(s)
        if w is None or h is None or h.index_of(d) is None:
            continue  # no bar today: the slot sits in cash rather than guess a price
        t = target_from_close(s, last_close(h, d), w)
        if t is not None:
            out.append(t)
    return tuple(out) if out else _spy(prep.history, d)


class BigBookWeightAllocator:
    """The largest index members, equal or size weighted with a ceiling, re-picked monthly."""

    id = "M0521"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        return _check(params).weighting != "spy"

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no arm targets anything (the contract)."""
        return _run(OpexPrepared(history, None, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> OpexPrepared:
        return OpexPrepared(history, None, None)

    def prepare_market(self, market: Any) -> OpexPrepared:
        sized = hasattr(market, "market_value") and len(market.shares) > 0
        return OpexPrepared(market.history, prepare_factor(market.history), market if sized else None)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, OpexPrepared):
            raise TypeError(f"prepared must be OpexPrepared, got {type(prepared).__name__}")
        return _run(prepared, members, data_date, _check(params))


ALLOC = BigBookWeightAllocator()


def _v(suffix: str, params: CapParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0521-{suffix}", family="M0521", rules=DAILY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0521",
    name="Big-company book weighted by size with a ceiling per name, against SPY's own big-company drift",
    family="stock-size-tilt",
    source_kind="variation",
    source_ref="M0501",
    parent_id="M0501",
    hypothesis=(
        "M0500 and M0501 held the 25 largest point-in-time index members equal weight and trailed "
        "SPY by 1.3 to 1.8 points a year whatever the re-pick day. SPY is cap-weighted, so an "
        "equal-weight book of the same names bets against its shape. Cap-weighting is old and "
        "fully published (size weighting is the index itself), so no edge is claimed from it: the "
        "question is only how much of the shortfall is the weighting rather than fees and picking. "
        "Arms on M0079's daily-hold-frac-gotrade (fractional, real fees), re-picked on the first "
        "session of the month: EQ25 (control, M0501-DAY-FIRST's book), SIZE25 (size weights, no "
        "ceiling), SIZE25-CAP10 (10% ceiling, M0047 style), SIZE25-CAP06 (6% ceiling), SIZE50-CAP10 "
        "(50 names, 10% ceiling) and SPY-ALWAYS (frame with no opinion). Prediction: moving from "
        "equal to size weights closes part of the gap to SPY, SIZE50-CAP10 closest, with a "
        "dose order EQ25 < CAP06 < CAP10 < SIZE25 in return and the reverse in concentration. "
        "Test: the best size-weighted arm beats EQ25 by at least a point a year, and its gap to SPY "
        "is smaller than EQ25's in 2009-2015. Success against SPY itself is not expected."
    ),
    expected_failure=(
        "All arms still trail SPY: the big names are a book of 25-50 stocks paying Gotrade's fee on "
        "small slots every month, and 2009-2015 had the broad market, not the giants, lead the "
        "recovery in part. Size weighting concentrates in a handful of names (Apple, Exxon, "
        "Microsoft), so the worst fall deepens toward 50% like M0500's rather than easing, and the "
        "uncapped arm is a bet on a few companies. The dose ladder may collapse to one curve if "
        "the 6% and 10% ceilings bind on the same few names. SPY-ALWAYS should be a book twin."
    ),
    candidates=(
        _v("EQ25", CapParams("equal", 25), "Control: equal weight, M0501-DAY-FIRST's book"),
        _v("SIZE25", CapParams("size", 25), "25 names weighted by market value, no ceiling"),
        _v("SIZE25-CAP10", CapParams("size", 25, 0.10), "Size weights with a 10% ceiling per name"),
        _v("SIZE25-CAP06", CapParams("size", 25, 0.06), "Size weights with a 6% ceiling per name"),
        _v("SIZE50-CAP10", CapParams("size", 50, 0.10), "50 names, size weights, 10% ceiling"),
        _v("SPY-ALWAYS", CapParams("spy", 25), "Frame: SPY only through the same fee path"),
    ),
    seen_keys=("concept:size-weighted-big-book-with-cap",),
)
