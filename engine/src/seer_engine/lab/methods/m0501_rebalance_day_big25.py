"""M0501 — Does the day a monthly big-stock book rebalances matter, when it costs no extra trades?

Variation of M0500 (option-expiration week). M0500 found that switching into the 25 largest index
members for expiration week alone cost ~12 points a year in fees and earned no premium over a
first-Friday or post-expiration week. The one fee-free form of the idea is a book that is always
the big 25, equal weight, re-picked once a month, with only the *day* of the re-pick varied. Every
arm re-picks the same number of times a year, so any gap between arms is the trading day (plus the
noise of drawing the same size ranking on different dates).

Arms, all on M0079's ``daily-hold-frac-gotrade`` (fractional, Gotrade's real fees, asked every
session; names are ranked once on the decision date R and held until the next R):

    * **DAY-FIRST**: re-pick at the first session of the month (the lab's default day).
    * **DAY-WEEK1**: re-pick Monday of the week ending the month's first Friday.
    * **DAY-OPEX**: re-pick Monday of option-expiration week (third-Friday week).
    * **DAY-POST**: re-pick Monday of the week after expiration.
    * **FIRST-MONTHLY**: chassis control. The same first-session re-pick on the native monthly
      preset ``monthly-hold-frac-gotrade``; prices what the daily chassis (band resizes between
      re-picks) costs or earns against the lab's own monthly cadence.

Assumptions written before any result. The book is decided on the close before the fill session
(the first session of the chosen week) and fills at its open, as in M0500. Size is market value,
one share class per company (identical share count, larger value kept), over the standard member
screen with the trend gate off. With no share counts or no names the arm holds SPY, identically on
every arm. DAY-OPEX equals M0500-BIG-ALWAYS in construction; its allocator id differs so the digest
is new, and it is expected to record as that arm's book twin, not a new book. Pure: reads only bars
and share counts dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from functools import lru_cache
from typing import Any

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0079_dividend_announcement_window import DAILY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0500_opex_week_big_stocks import (
    BENCH,
    LOOKBACK,
    TOP,
    OpexPrepared,
    _rows,
    _spy,
    biggest,
    week_of,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import prepare_factor

ADDED = date(2026, 11, 8)
DAYS = ("first", "week1", "opex", "post")


@dataclass(frozen=True, slots=True)
class DayParams:
    """``day`` which session of the month the book is re-picked on."""

    day: str = "first"
    top: int = TOP

    def __post_init__(self) -> None:
        if self.day not in DAYS:
            raise ValueError(f"day must be one of {DAYS}, got {self.day!r}")
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 100:
            raise ValueError(f"top must be an int in [1, 100], got {self.top!r}")

    def as_dict(self) -> dict[str, str]:
        return {"day": self.day, "top": str(self.top), "rank": "market-value",
                "class_rule": "identical-share-count"}


def _check(params: object) -> DayParams:
    if not isinstance(params, DayParams):
        raise TypeError(f"params must be DayParams, got {type(params).__name__}")
    return params


@lru_cache(maxsize=None)
def fill_session(year: int, month: int, day: str) -> date | None:
    """The session the month's re-pick fills on (its first session of the chosen week)."""
    if day == "first":
        ss = dates.sessions(date(year, month, 1), date(year, month, 7))
        return ss[0] if ss else None
    wk = week_of(year, month, day)
    return wk[0] if wk else None


def decision_date(data_date: date, day: str) -> date | None:
    """R: the latest re-pick's decision date on or before ``data_date``."""
    s = dates.next_session(data_date)
    latest = None
    for dm in (-2, -1, 0, 1):
        m = s.month + dm
        y = s.year + (m - 1) // 12
        f = fill_session(y, (m - 1) % 12 + 1, day)
        if f is None:
            continue
        r = dates.prev_session(f)
        if r <= data_date and (latest is None or r > latest):
            latest = r
    return latest


def _run(prep: OpexPrepared, members: AbstractSet[str], d: date, p: DayParams) -> tuple[Target, ...]:
    if prep.market is None:  # the market-aware contract: no panel, no targets, on every arm
        return ()
    r = decision_date(d, p.day)
    if r is None:
        return _spy(prep.history, d)
    names = biggest(prep, _rows(prep, members, r), r, p.top)
    w = equal_weight(p.top)
    out: list[Target] = []
    for s in names:
        h = prep.history.get(s)
        if h is None or h.index_of(d) is None:
            continue  # no bar today: the slot sits in cash rather than guess a price
        t = target_from_close(s, last_close(h, d), w)
        if t is not None:
            out.append(t)
    return tuple(out) if out else _spy(prep.history, d)


class RebalanceDayAllocator:
    """The 25 largest index members, equal weight, re-picked once a month on the chosen day."""

    id = "M0501"
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
        _check(params)
        return True

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


DAY = RebalanceDayAllocator()


def _v(suffix: str, day: str, rationale: str, rules: Any = DAILY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0501-{suffix}", family="M0501", rules=rules, allocator=DAY,
                     params=DayParams(day), rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0501",
    name="Rebalance day of a monthly big-stock book: does the trading day matter when the number of trades is the same?",
    family="stock-option-expiration-week",
    source_kind="variation",
    source_ref="M0500",
    parent_id="M0500",
    hypothesis=(
        "M0500 (Stivers & Sun 2013, a published anomaly that has had a decade to fade) found no "
        "expiration-week premium and a ~12 point a year fee bill from switching. The fee-free form "
        "of the question: hold the 25 largest point-in-time index members (market value, one class "
        "per company), equal weight, fractional, at Gotrade's real fees, always invested, re-picked "
        "once a month, and vary only the re-pick day: the first session of the month (DAY-FIRST, the "
        "lab default), Monday of the first-Friday week (DAY-WEEK1), Monday of expiration week "
        "(DAY-OPEX) and Monday after it (DAY-POST). Same trades a year in every arm, so a gap is "
        "the day. FIRST-MONTHLY is the chassis control: the same first-session pick on the native "
        "monthly preset. DAY-OPEX is M0500-BIG-ALWAYS rebuilt under a new id and should record as "
        "its book twin. Expected: the four daily arms land within a few points a year of one "
        "another, inside the blind-draw noise the lab measured on M0440, and none beats SPY; a "
        "spread of the four arms is the lab's own estimate of how much a pure choice of day moves "
        "a result. The test is the spread, not a win: if it is wide, calendar-day luck is a "
        "confound for every monthly book the lab has ever scored."
    ),
    expected_failure=(
        "All arms trail SPY: M0500's always-invested big-25 book made +5.6% a year against SPY's "
        "+7.2% on deposits, with a 50% worst fall, and size-picking the largest names is close to "
        "owning SPY with extra fees. The four re-pick days differ by under ~1.5 points a year and "
        "the order is not the paper's (no expiration-week premium). FIRST-MONTHLY differs from "
        "DAY-FIRST by the daily chassis's band resizes only. Nothing is eligible: the worst fall "
        "and the 2009-2015 gap to SPY fail first."
    ),
    candidates=(
        _v("DAY-FIRST", "first", "Re-pick on the first session of the month: the lab default day"),
        _v("DAY-WEEK1", "week1", "Re-pick Monday of the first-Friday week"),
        _v("DAY-OPEX", "opex", "Re-pick Monday of option-expiration week: M0500-BIG-ALWAYS's book"),
        _v("DAY-POST", "post", "Re-pick Monday of the week after expiration"),
        _v("FIRST-MONTHLY", "first", "Chassis control: the first-session pick on the monthly preset",
           rules=replace(MONTHLY_HOLD_FRAC_GOTRADE)),
    ),
    seen_keys=("concept:rebalance-day-big-stocks",),
)
