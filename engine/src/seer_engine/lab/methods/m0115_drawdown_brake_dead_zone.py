"""M0115 — The dead-zone brake: ignore every fall under a threshold, then taper hard.

Source: variation on M0109 (the proportional own-drawdown brake; Black & Perold 1992 CPPI, Grossman
& Zhou 1993 reduced to a dial). Idea: M0109 measured the brake and found it cheap in the crashes it
was built for and expensive everywhere else -- it gave up about 10 points a year in 2009-2015,
a stretch whose unbraked worst fall was only about 15%. A taper that starts at zero trims on every
routine dip, and a routine dip that bounces costs the trimmed slice twice (sold low, bought back
high). A DEAD ZONE removes that: exposure stays at 1 until the shadow book is ``start`` below its
one-year high, and only then falls in a straight line to ``floor`` by ``taper``.

THE BOOK AND THE SHADOW ARE M0109'S, UNCHANGED. The 50 most-traded index members at equal weight,
the gross membership-free shadow index rebuilt from bars, the trailing one-year high, the weekly
clock and every other constant are imported from M0109 rather than copied, so the only thing that
moves between M0109's variants and these is the exposure curve. ``BrakeParams`` cannot gain a field
without moving every M0109 digest, so ``DeadZoneParams`` subclasses it and carries ``start``; the
allocator has its own id, ``M0115``.

THE DIAL. At drawdown ``dd`` of the shadow: exposure is 1 for ``dd <= start``; above it,
``1 - (dd - start) / (taper - start)``, clipped to ``[floor, 1]`` and rounded to the nearest
``STEP`` (M0109's 0.05). ``taper`` is the drawdown at which the account reaches ``floor``, so
START15-T35 is all cash at a 35% fall and half exposure at a 25% fall. ``taper = None`` is the
control, exposure 1 always.

THE ARMS. START15-T35, START15-T45, START10-T30 and START20-T40 are the dead-zone ladder (two
depths of zone, and two slopes at the 15% zone). CTRL is the same book never braked, on the weekly
clock: it is the no-opinion arm, and it repeats M0109-EW-ALL-W's book under a new digest, so it
records as a book twin of M0109 and is never counted as a new book. START0-T20 is the
reproduction arm: a zero-width zone at M0109's 20% taper must reproduce M0109-TAPER-20-W's curve
exactly. If it does not, the new exposure function is wrong and nothing else in the run can be
read. It is also, by construction, a book twin and costs no look.

All arms trade the weekly resize preset at Gotrade's real fees, in fractional shares.
Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import build_grid
from seer_engine.lab.methods.m0109_book_drawdown_brake import (
    ONE,
    STEP,
    WEEKLY,
    BrakeParams,
    BrakePrepared,
    DrawdownBrake,
    book_rows,
    book_targets,
    braked,
    chosen,
    prepared_rows,
    shadow_drawdown,
    shadow_wealth,
)
from seer_engine.sim.book import Target
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 10)


@dataclass(frozen=True, slots=True)
class DeadZoneParams(BrakeParams):
    """M0109's book and brake plus the width of the zone in which the brake does nothing."""

    start: Decimal = Decimal("0")  # shadow drawdown below which exposure stays 1

    def __post_init__(self) -> None:
        BrakeParams.__post_init__(self)
        if not isinstance(self.start, Decimal) or not self.start.is_finite():
            raise TypeError(f"start must be a Decimal, got {self.start!r}")
        if not 0 <= self.start < 1:
            raise ValueError(f"start must be a Decimal in [0, 1), got {self.start}")
        if self.taper is not None and self.taper <= self.start:
            raise ValueError(f"taper {self.taper} must exceed start {self.start}")

    def as_dict(self) -> dict[str, str]:
        out = BrakeParams.as_dict(self)
        out["start"] = str(self.start)
        return out


def _check(params: object) -> DeadZoneParams:
    if not isinstance(params, DeadZoneParams):
        raise TypeError(f"params must be DeadZoneParams, got {type(params).__name__}")
    return params


def exposure(drawdown: float | None, p: DeadZoneParams) -> Decimal:
    """1 inside the dead zone, then a straight line to ``floor`` at ``taper``."""
    if p.taper is None or drawdown is None or not np.isfinite(drawdown) or drawdown <= float(p.start):
        return ONE
    raw = 1.0 - (drawdown - float(p.start)) / float(p.taper - p.start)
    clipped = min(1.0, max(float(p.floor), raw))
    stepped = (Decimal(repr(clipped)) / STEP).quantize(ONE, rounding=ROUND_HALF_UP) * STEP
    return min(ONE, max(p.floor, stepped))


class DeadZoneBrake(DrawdownBrake):
    """M0109's book and shadow with the dead-zone exposure curve on top."""

    id = "M0115"

    def lookback(self, params: Any) -> int:
        _check(params)
        return super().lookback(params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_check(params))

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_check(params))

    def uses_members(self, params: Any) -> bool:
        return super().uses_members(_check(params))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        base = book_targets(book_rows(history, members, data_date, p), p)
        if not base or p.taper is None:
            return base
        grid = build_grid(history, p.market)
        if grid is None:
            return base
        universe = frozenset(history)

        def picks_at(d: date) -> tuple[str, ...]:
            return tuple(r.symbol for r in chosen(book_rows(history, universe, d, p), p))

        wealth = shadow_wealth(grid, picks_at)
        return braked(base, exposure(shadow_drawdown(grid, wealth, data_date, p), p))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BrakePrepared):
            raise TypeError(f"prepared must be BrakePrepared, got {type(prepared).__name__}")
        p = _check(params)
        base = book_targets(prepared_rows(prepared.factor, members, data_date, p), p)
        if not base or p.taper is None:
            return base
        grid, wealth = prepared.shadow(p)
        return braked(base, exposure(shadow_drawdown(grid, wealth, data_date, p), p))


DEAD_ZONE = DeadZoneBrake()


def _v(suffix: str, start: str | None, taper: str | None, rationale: str) -> Candidate:
    params = DeadZoneParams(
        start=Decimal(start or "0"),
        taper=None if taper is None else Decimal(taper),
    )
    return Candidate(id=f"M0115-{suffix}", family="M0115", rules=WEEKLY, allocator=DEAD_ZONE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0115",
    name="The dead-zone brake: ignore every fall under 15%, then taper hard",
    family="book-drawdown-brake",
    source_kind="variation",
    source_ref="M0109 (the proportional own-drawdown brake), with a dead zone added before the taper",
    parent_id="M0109",
    hypothesis=(
        "M0109's brake paid about 10 points a year in 2009-2015 on routine dips, because the "
        "unbraked book's worst fall in that stretch was only about 15%: a brake whose taper starts "
        "at zero trims on every wobble, and a wobble that bounces costs the trimmed slice twice. "
        "A dead zone keeps exposure at 1 until the shadow book is `start` below its one-year high, "
        "then falls linearly to cash by `taper`. Everything else is M0109's, imported unchanged: "
        "the 50 most-traded index members at equal weight, the gross membership-free shadow, the "
        "one-year high, the weekly clock, fractional shares at Gotrade's real fees on the owner's "
        "monthly deposits. Arms: START15-T35, START15-T45 (the 15% zone at two slopes), START10-T30 "
        "and START20-T40 (a shallower and a deeper zone), CTRL (never braked, weekly: the "
        "no-opinion arm, a recorded book twin of M0109-EW-ALL-W), and START0-T20 (a zero-width zone "
        "at M0109's 20% taper, which must reproduce M0109-TAPER-20-W exactly and so tests the new "
        "exposure curve, itself a book twin). Success: cut the 2009-2015 cost against CTRL from "
        "about 10 points a year to under 3 while keeping most of the 2000-2002 and 2008-2009 "
        "saving. Assumed here, before any result: 'most' means at least half of M0109's saving in "
        "worst fall. Eligibility would still need a braked book to beat SPY TR on deposit-matched "
        "money, worst fall under 20% and a majority of folds; the plain book underneath already "
        "trailed SPY in M0109, so a pass is unlikely and the measurement is the point. The "
        "shadow's one-year high was fixed by M0109 on unbraked exposure statistics alone; "
        "nothing about it is retuned here. The idea is a brake published in the portfolio "
        "insurance literature (1990s), long before the dev window ends, so any edge in the "
        "early years may already have been traded away."
    ),
    expected_failure=(
        "The dead zone only moves the pain. Crashes start as 15% falls, so the brake gives up the "
        "first 15 points of every crash and then has to cut harder, from a lower base, into the "
        "fastest part of the drop: the worst fall may come out well above M0109's 17% and above "
        "the 20% bar. The 2009-2015 saving may also be small, because the stretch holds a 15.1% "
        "fall and a dead zone sized exactly to it can still be crossed by 2011's V-shaped dip. "
        "The competing explanation, M0116's, is that the cost is the re-entry and not the exit; "
        "if so a dead zone leaves most of the 10 points in place. And the base book is a bet "
        "against SPY's big-company shape whatever the brake does, so every arm may still trail "
        "SPY TR after 2009."
    ),
    candidates=(
        _v("START15-T35", "0.15", "0.35",
           "Dead zone to a 15% fall, then a straight line to cash at 35%"),
        _v("START15-T45", "0.15", "0.45",
           "Same 15% zone, gentler slope: all cash only at a 45% fall"),
        _v("START10-T30", "0.10", "0.30",
           "Shallower zone: 10% ignored, cash at 30%"),
        _v("START20-T40", "0.20", "0.40",
           "Deeper zone: 20% ignored, cash at 40%"),
        _v("CTRL", None, None,
           "No-opinion arm: the same book weekly, never braked (book twin of M0109-EW-ALL-W)"),
        _v("START0-T20", "0", "0.20",
           "Reproduction arm: zero-width zone at a 20% taper, must equal M0109-TAPER-20-W"),
    ),
    seen_keys=(
        "concept:drawdown-brake-dead-zone",
        "concept:own-drawdown-proportional-brake",
    ),
)
