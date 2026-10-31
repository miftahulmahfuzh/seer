"""M0065 — Which day of the month the momentum book rebalances: first session, second-last, mid-month.

Source: variation of M0052 (turn-of-month tilt, rejected: the extra round trip cost more than the
effect earned), on the M0032 residual-momentum book. Turn-of-month: Ariel (1987), Lakonishok & Smidt
(1988), McConnell & Xu (2008) -- all published long before 2015, so the dev window can only show
what the crowd had not yet traded away.
Idea: a book that already rebalances every month pays the round trip anyway, so moving the day it
trades costs nothing extra. M0052 priced the turn as an *added* trade at about 1.2% of the money
moved per month; this method asks the cheaper question, whether the same book trades better on one
day of the month than another.

Chassis. The lab's monthly cadence can only decide on the first session of a month, so this
allocator runs on a daily cadence and does the calendar itself: on data date d it finds the latest
rebalance session at or before next_session(d), ranks as of the session before it (the "anchor",
which is <= d), and returns that basket re-priced at today's close. Between rebalance days the
basket is the same names at the same weights, so the engine's resize band is all that trades.
Ranking, screen, trend gate and equal weights are M0007-N20-RAW verbatim (``RESIDMOM``).
The control that matters is the FIRST arm: the first-session rebalance on this same daily chassis,
so the chassis's own cost (daily resize checks, deposits waiting for a rebalance) cancels out of
every comparison; it is also compared to M0032's recorded trial, which ran on the monthly preset.

Pure: every bar read is dated <= data_date (the anchor is never after it).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from functools import lru_cache
from typing import Any

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import DAILY_SWITCH
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 31)

# Daily decisions (the calendar is done in the allocator), resized, fractional, Gotrade's real
# fees. Same preset M0052 used: it runs on dev, and a win would need a feature-wish for a preset.
DAILY_RESIZE_FRAC_GOTRADE = replace(
    DAILY_SWITCH, id="daily-resize-frac-gotrade", resize=True, fractional=True, cost_model="gotrade"
)

# 0-based index of the session the rebalance TRADES on (at its open), negative from the month's end.
SLOTS: dict[str, int] = {"first": 0, "penult": -2, "mid": 9}


@dataclass(frozen=True, slots=True)
class DayParams:
    resid: ResidParams
    slot: str = "first"

    def __post_init__(self) -> None:
        if self.slot not in SLOTS:
            raise ValueError(f"slot must be one of {sorted(SLOTS)}, got {self.slot!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"slot": self.slot, "slot_index": str(SLOTS[self.slot])}
        for k, v in self.resid.as_dict().items():
            out[f"resid.{k}"] = v
        return out


@lru_cache(maxsize=4096)
def _month_sessions(year: int, month: int) -> tuple[date, ...]:
    first = date(year, month, 1)
    last = date(year + (month == 12), month % 12 + 1, 1)
    return tuple(s for s in dates.sessions(first, last) if s.month == month)


def rebalance_session(year: int, month: int, slot: str) -> date:
    return _month_sessions(year, month)[SLOTS[slot]]


def anchor(data_date: date, slot: str) -> date:
    """The decision date of the latest rebalance whose trade session is <= next_session(data_date).

    Never after ``data_date``: the trade session is at or before the next session, so the session
    before it is at or before ``data_date``.
    """
    t0 = dates.next_session(data_date)
    y, m = t0.year, t0.month
    trade = rebalance_session(y, m, slot)
    if trade > t0:
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        trade = rebalance_session(y, m, slot)
    return dates.prev_session(trade)


@dataclass(slots=True, eq=False)
class _Prepared:
    inner: ResidPrepared
    cache: dict[Any, tuple[Target, ...]] = field(default_factory=dict)


class RebalanceDayAllocator:
    """M0007's residual-momentum book, re-ranked only on the slot's day and held in between."""

    id = "M0065"

    def lookback(self, params: DayParams) -> int:
        return RESIDMOM.lookback(params.resid) + 45  # room for the anchor to sit a month back

    def symbols(self, params: DayParams) -> tuple[str, ...]:
        return RESIDMOM.symbols(params.resid)

    def holds(self, params: DayParams) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: DayParams) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: DayParams) -> tuple[Target, ...]:
        return self.targets_prepared(self.prepare(history), members, data_date, held, params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return _Prepared(RESIDMOM.prepare(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: DayParams) -> tuple[Target, ...]:
        at = anchor(data_date, params.slot)
        key = (at, params.slot, params.resid.scaled)
        basket = prepared.cache.get(key)
        if basket is None:
            basket = RESIDMOM.targets_prepared(prepared.inner, members, at, held, params.resid)
            prepared.cache[key] = basket
        out: list[Target] = []
        for t in basket:
            c = last_close(prepared.inner.history.get(t.symbol), data_date)
            fresh = None if c is None else target_from_close(t.symbol, c, t.weight)
            if fresh is not None:
                out.append(fresh)
        return tuple(out)


ALLOC = RebalanceDayAllocator()


def _v(suffix: str, slot: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0065-{suffix}", family="M0065", rules=DAILY_RESIZE_FRAC_GOTRADE,
                     allocator=ALLOC, params=DayParams(ResidParams(N20, scaled=False), slot),
                     added=ADDED, owner_inputs=(), rationale=rationale)


METHOD = Method(
    id="M0065",
    name="Time the monthly rebalance to the month's turn: the same momentum book, traded on the "
         "second-last session instead of the first",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="M0052",
    parent_id="M0052",
    hypothesis=(
        "M0052 showed that buying the turn of the month as an extra trade costs about 1.2% of the "
        "money moved per month at Gotrade's fees, far more than the effect earns. A book that "
        "already rebalances monthly pays that trip anyway, so moving its rebalance from the first "
        "session of the month to the second-last one costs nothing extra, and fresh money (the "
        "25th-of-month deposit and the new picks) would be invested before the month-end inflow "
        "days rather than after them. Test: M0007-N20-RAW's raw top-20 residual-momentum book at "
        "real Gotrade fees in fractional shares, with only the rebalance day moved: FIRST (first "
        "session, the control on this chassis), PENULT (second-last session, the treatment), MID "
        "(tenth session, a mid-month control that has no turn in it). Turn-of-month was published "
        "in 1987-1988 and was widely traded by 2000, so the dev window can only show what was "
        "left of it. Evidence only: a momentum book is kin of the failed momentum books by "
        "behaviour, so it can never be promoted."
    ),
    expected_failure=(
        "A difference within noise: under half a point a year between PENULT and FIRST, because "
        "on SPY in 1996-2015 the turn-of-month days were no better than a mid-month week and a "
        "twenty-stock book holds each name for several months, so a few sessions of trade timing "
        "moves its entry price by well under the monthly noise. A second way it fails is the "
        "chassis: this book runs on the daily cadence with a resize band, so the control may "
        "differ from M0032's monthly-preset record by more than any day effect, in which case "
        "only the within-chassis gaps (PENULT vs FIRST vs MID) are readable. Hypothesis and "
        "all arms fixed before any result."
    ),
    candidates=(
        _v("FIRST", "first",
           "Control: rebalance on the first session of the month, the lab's usual day, on this daily chassis"),
        _v("PENULT", "penult",
           "Treatment: rebalance on the second-last session of the month, before the month-end inflow days"),
        _v("MID", "mid",
           "Control: rebalance on the tenth session, a mid-month day with no turn in it"),
    ),
    seen_keys=("concept:rebalance-day-turn-of-month",),
)
