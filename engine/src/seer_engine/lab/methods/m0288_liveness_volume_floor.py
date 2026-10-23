"""M0288 — Is a traded-volume floor a general survivorship brake, or a news-book quirk?

Source: variation of M0284, which turned the news-day book's event volume bar five ways; the
chassis is M0032 (M0007-N20-RAW in fractional shares at Gotrade's real fees on the owner's
deposits), itself M0007's realistic twin (Blitz, Huij & Martens 2011, residual momentum).

Idea: M0284 set out to ask whether the news-day book was short of jumps, and found a second,
unasked-for straight line on the way. Measured dev store minus survivorship-check store, funded,
a year: no volume bar -3.3 points, 2x -1.3, 2.5x -1.0, 3x -1.6, 4x +0.6. The strictest rung is
the only arm in the whole method that earns MORE once the companies that died or were bought are
put back, and its best-covered-era lead goes from +0.7% to +1.8%. The reading that fits is that a
volume condition is a **liveness** proxy and not a news proxy: a company the market is actively
trading still exists, so a price move on ordinary volume is disproportionately a thin, fading name
of exactly the kind the dev store prices and the check store exposes.

If that reading is right it has nothing to do with news days and should transfer to any price-only
screen. This method tests it on a book with no events in it at all: the residual-momentum book the
paper roster trades, with one requirement added to the pool and nothing else moved.

**The floor is cross-sectional, not absolute, and that is a deliberate choice.** A fixed dollar
bar would bind on almost nothing in 1996 and on almost everything in 2014 -- dollar volumes grew
by more than an order of magnitude across the dev window -- so an absolute bar is a disguised
date filter and its ladder would measure the era, not the liveness. Each rung instead drops the
bottom ``dv_pct`` percent of that day's own eligible pool by 20-day mean dollar volume, which is
scale-free and nests exactly. It is also dollar volume and not market capitalisation: the lab's
market-cap figure is unadjusted share count against split-adjusted closes and is wrong by an
arbitrary per-symbol factor, while dollar volume is sound.

    ===========  ========  =================================================================
    arm          dv_pct    what it asks of a pick
    ===========  ========  =================================================================
    ``DV00``     0%        nothing: F4's own $20M screen and no more -- **the reference rung**
    ``DV20``     20%       not in the least-traded fifth of today's pool
    ``DV40``     40%       in the better-traded three fifths
    ``DV60``     60%       in the better-traded two fifths
    ``DV80``     80%       in the most-traded fifth only
    ===========  ========  =================================================================

``DV00`` is the arm with no opinion in it: the whole book, never stepping aside, with the dial
set to off. Every other rung is read against it directly, and it must reproduce M0032's recorded
trial bar for bar. A new allocator id is needed (not ``RESIDMOM``) because ``config_digest``
reads the allocator id and ``DV00``'s parameters are M0032's exactly; without it the reference
rung would collide with M0032's recorded configuration and could never run. The allocator
forwards every other decision to M0007's code, so the two are the same arithmetic and any
difference in the numbers is the dial.

**Measured before writing this file, so the ladder is known not to be degenerate** (238 decision
months, 1996-2015, dev store). The floor binds hard and monotonically on the picks: names shared
with the no-floor book are 20.00, 16.36, 12.69, 8.47 and 4.40 of 20 as the rungs rise. And,
unlike every filter M0277 and M0279 tried, it does **not** starve the book: the eligible pool has
a median of 262 names for 20 slots, so the rungs hold 20.00, 20.00, 20.00, 20.00 and 19.87 names
on average, with only ``DV80`` ever short (11 months of 238, never below 13 names). That matters
because M0279 measured the cost of empty slots at 2 to 6 points a year, and this design cannot
incur it. Any return difference between rungs is the picks, not cash.

Pure: the floor reads one feature F4 already computed from bars ending at d, and nothing else is
touched, so nothing dated after the data date is read.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    RESIDMOM,
    FACTOR_SYMBOLS,
    ResidParams,
    ResidPrepared,
    build_grid,
    residual_scores,
    resid_lookback,
    targets_from_scores,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorRow, factor_rows, trend_on

ADDED = date(2026, 10, 23)


@dataclass(frozen=True, slots=True)
class FloorParams:
    """``inner`` is M0032's configuration verbatim; ``dv_pct`` is the only dial."""

    inner: ResidParams
    dv_pct: int = 0  # drop the bottom this percent of the day's pool by 20-day dollar volume

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if isinstance(self.dv_pct, bool) or not isinstance(self.dv_pct, int):
            raise TypeError(f"dv_pct must be an int, got {type(self.dv_pct).__name__}")
        if not 0 <= self.dv_pct < 100:
            raise ValueError(f"dv_pct must be in [0, 100), got {self.dv_pct}")

    def as_dict(self) -> dict[str, str]:
        out = {"dv_pct": str(self.dv_pct)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def apply_floor(rows: list[FactorRow], dv_pct: int) -> list[FactorRow]:
    """``rows`` less the worst-traded ``dv_pct`` percent by dollar volume, back in symbol order.

    The cut is by rank and not by an interpolated percentile, so the rungs nest exactly: the set
    kept at a higher ``dv_pct`` is always a subset of the one kept below it. Ties are broken by
    symbol ascending, as everywhere else in the lab. ``dv_pct`` of 0 returns ``rows`` unchanged,
    which is what makes the reference rung bit-identical to the parent's path.
    """
    if dv_pct <= 0 or not rows:
        return rows
    keep = len(rows) - math.floor(len(rows) * dv_pct / 100)
    by_dv = sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[:keep]
    return sorted(by_dv, key=lambda r: r.symbol)


def _check(params: object) -> FloorParams:
    if not isinstance(params, FloorParams):
        raise TypeError(f"params must be FloorParams, got {type(params).__name__}")
    return params


class VolumeFloorAllocator:
    """M0032's residual-momentum book with a cross-sectional dollar-volume floor on the pool.

    Held symbols get no special treatment, exactly as in M0007: the targets are the new top set,
    so a name that falls out of it is signal-exited by the book engine.
    """

    id = "M0288"

    def lookback(self, params: Any) -> int:
        return resid_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).inner
        return tuple(sorted({p.market, *FACTOR_SYMBOLS(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = p.inner
        if not trend_on(history, data_date, inner.inner):
            return ()
        rows = apply_floor(factor_rows(history, members, data_date, inner.inner), p.dv_pct)
        if not rows:
            return ()
        grid = build_grid(history, inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return targets_from_scores(rows, scores, inner)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = p.inner
        if not trend_on(prepared.history, data_date, inner.inner):
            return ()
        rows = apply_floor(prepared.factor.rows_on(members, data_date, inner.inner), p.dv_pct)
        if not rows:
            return ()
        grid = prepared.grid(inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return targets_from_scores(rows, scores, inner)


DVFLOOR = VolumeFloorAllocator()

#: M0032-N20-RAW-FRAC-GT's configuration, which every rung shares but for ``dv_pct``.
BASE = ResidParams(N20, scaled=False)


def _v(suffix: str, dv_pct: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0288-{suffix}", family="M0288", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DVFLOOR, params=FloorParams(BASE, dv_pct), rationale=rationale,
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0288",
    name="A traded-volume floor as a general survivorship brake on a price-only stock screen",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref=(
        "variation of M0284 (its volume-bar ladder and the dev-minus-check-store line it "
        "produced), carried onto M0032's chassis -- M0007-N20-RAW in fractional shares at "
        "Gotrade's real fees on the owner's deposits (Blitz, Huij & Martens 2011, Residual "
        "momentum, J. Empirical Finance 18(3), 506-521)"
    ),
    parent_id="M0284",
    hypothesis=(
        "M0284 turned the news-day book's event volume bar five ways and found a second, "
        "independent straight line nobody asked for: dev store minus survivorship-check store, "
        "funded, a year, ran -3.3 points with no bar, -1.3 at 2x, -1.0 at 2.5x, -1.6 at 3x and "
        "+0.6 at 4x. The strictest rung is the only arm in that method that earns MORE with the "
        "dead companies put back, and its 2009-2015 lead went from +0.7% to +1.8%. The reading "
        "is that a volume condition is a liveness proxy and not a news proxy: a company the "
        "market is actively trading still exists, so a price move on ordinary volume is "
        "disproportionately a thin, fading name of the kind the dev store prices and the check "
        "store exposes. If that is general rather than a quirk of event books, it must transfer "
        "to a screen with no events in it. This runs it on M0032's chassis verbatim -- top-20 "
        "raw cumulative residual momentum, F4's screen, the SPY-200 monthly trend switch, equal "
        "weights, fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade, the "
        "owner's 5,000,000 IDR monthly deposits -- adding one requirement to the pool and moving "
        "nothing else: a pick must not be in the worst-traded dv_pct percent of that day's own "
        "eligible names by 20-day mean dollar volume. Five rungs, a ladder and not a pair, "
        "because two points cannot read a slope: DV00 (no floor, the reference arm with no "
        "opinion in it, which must reproduce M0032's recorded trial bar for bar), DV20, DV40, "
        "DV60 and DV80. The cut is cross-sectional and not a fixed dollar bar on purpose: dollar "
        "volumes grew by more than an order of magnitude across the dev window, so an absolute "
        "bar is a disguised date filter whose ladder would measure the era. I measured the "
        "geometry before writing this file, over all 238 decision months: the dial binds hard "
        "and monotonically (names shared with the no-floor book are 20.00, 16.36, 12.69, 8.47 "
        "and 4.40 of 20), and -- unlike all six filters M0277 and M0279 tried -- it does not "
        "starve the book, holding 20.00, 20.00, 20.00, 20.00 and 19.87 names on average, so "
        "M0279's 2-to-6-point cost of parking empty slots cannot be the explanation for anything "
        "seen here. The measurement that matters is NOT the dev return: it is the dev-minus-"
        "check-store gap, rung by rung, which lab survivorship prints. Success for the idea: "
        "that gap narrows monotonically as the floor rises across at least four rungs and sits "
        "within half a point of zero at the top rung, while under 1 point a year of dev return "
        "is given up. Success for the gate, separately: an arm with a worst fall under the "
        "screen that beats total-return SPY with DSR >= 0.90, on the check store as well as dev."
    ),
    expected_failure=(
        "The effect may be specific to event books. A news day's volume spike is a different "
        "animal from a momentum name's ordinary turnover -- M0284's dial asked whether TODAY was "
        "busy for this stock, while this one asks whether this stock is busy compared to its "
        "peers -- so the transfer may simply not happen and the ladder be flat in the gap, which "
        "would mean the liveness reading was a coincidence of the news chassis. The second way "
        "it fails is that a dollar-volume floor is a crowding tilt as much as a liveness one: it "
        "pushes the book toward the names everyone is already trading, and a crowded name is "
        "where a published edge fades first, so the strict rungs may lose dev return steadily "
        "even while their survivorship gap closes -- and since residual momentum was published "
        "in 2011, inside this window, the fade is the base case and 2009-2015 is where it would "
        "show. Third, the floor tilts toward the largest companies, and insight 91 says the dev "
        "store's edge sits with the smaller index members, so the strict rungs may converge on "
        "SPY's own big-company drift and beat nothing. Fourth, the whole chassis inherits "
        "M0007's worst fall near 19-20%, which this dial has no reason to touch, so the "
        "drawdown screen may reject every rung regardless of what the gap does. And fifth, even "
        "a clean monotone result here is evidence about how to BUILD books and not a candidate: "
        "the check store is a cross-check and not a gate, so an arm that only looks better there "
        "can never be promoted on that basis."
    ),
    candidates=(
        _v("DV00", 0,
           "No floor: M0032's book unchanged, the reference rung with no opinion about volume"),
        _v("DV20", 20, "Not in the least-traded fifth of today's eligible pool"),
        _v("DV40", 40, "In the better-traded three fifths"),
        _v("DV60", 60, "In the better-traded two fifths"),
        _v("DV80", 80, "The most-traded fifth only: the strictest liveness bar the pool allows"),
    ),
    seen_keys=(
        "concept:dollar-volume-floor-survivorship-brake",
        "concept:liveness-filter-dose-response",
    ),
)
