"""M0120 — A safety rule that cannot be fitted: step aside by the calendar, not by the chart.

Source: Bouman & Jacobsen (2002), "The Halloween Indicator, 'Sell in May and Go Away': Another
Puzzle", American Economic Review 92(5); and the lab's own M0084, which priced the SPY 200-day
switch on its own.
Idea: the lab's most expensive shared mechanism is the SPY 200-day switch. M0084 priced it with
the stocks taken away and found the monthly reading worth +1.4 points a year on the owner's
deposits (+9.1% against +7.7% for buy-and-hold SPY), the weekly reading worth -3.3, and every
version of it 6 to 11 points a year behind plain SPY in 2009-2015. Its one redeeming trade is
2008. This method asks whether the cheapest conceivable alternative does the same job: a clock
that never reads a price at all. Step out of the book for a fixed stretch of the calendar --
classically May to October -- and hold the rest of the year.

Three properties nothing else in the lab has, and they are the reason this is worth an id:

    * **It cannot be overfitted to the price series**, because it never reads the price series.
      There is no window length, no band, no cadence to tune. Both stretches tested here were
      named in print before the dev window opened (Bouman & Jacobsen 2002 for May-October;
      September and October as the two historically worst months is older folklore still).
    * **Its trade count is two flips a year**, so Gotrade's fee schedule barely touches it, where
      the weekly switch paid 0.7 points a year in fees alone (M0084).
    * **It would have been out of the market through September and October 2008 by
      construction**, a month before the 200-day switch reacted, rather than after the fall.

Priced the way M0084 priced the switch: as a dial, on a fixed underlying book, with the no-clock
control run through the identical fee, deposit and rounding path. Two underlying books, three
clock settings each, a 2x3 grid in which every paired difference is the clock alone:

    * **SPY** -- hold SPY at full weight. The clock measured naked, with no stock picking in the
      way, directly comparable to M0084's six readings of the switch (same rules preset, same
      253-bar lookback, therefore the same sessions and the same deposits).
    * **EW20** -- hold the 20 index members with the largest 20-day dollar volume, equal weight,
      re-picked monthly. A market-shaped book with **no fitted signal of its own**: it ranks on
      size-of-trading, not on anything that predicts return, so whatever the clock does to it is
      the clock and not an interaction with a stock-picking rule. It is also deliberately not kin
      to any test-failed method: the lab's four out-of-sample failures are momentum, residual
      momentum and their blends (M0002, M0021, M0022, M0029), and nothing here ranks on past
      return. The lab's standard eligibility screen (``f_factor.factor_rows``: a member on d, a
      bar dated d, 253 bars of history, 20-day dollar volume above $20m, close >= $5) is reused
      unchanged, with its trend gate switched **off** -- the whole point is that the only timing
      rule in this method is the calendar.

The three clock settings, read on the **traded session** ``S = next_session(d)`` and not on d,
because a monthly book decided on the last session of a month is filled on the first session of
the next one and it is the month it will be *held in* that the clock is about:

    * ``none``     -- always on. The control.
    * ``halloween``-- on iff S falls in November through April (Bouman & Jacobsen's window).
    * ``sepoct``   -- on except in September and October, the two months the folklore blames.

Off means cash: no idle symbol, as M0084 did, so the measured cost of stepping aside is an upper
bound (real cash paid 3-5% a year over most of the 1994-2007 part of this window, and the
halloween clock is out for half of every year, so the un-modelled interest is worth roughly 1.5
to 2.5 points a year to it).

Every variant shares one 253-bar lookback (``factor_lookback`` of the screen, which equals
M0084's constant), so all six are scored on exactly the same sessions, each paired difference is
the clock alone, and M0084's numbers are readable alongside these without an adjustment.

Reads only bars dated <= d. ``held`` is never read: the calendar does not depend on the book, so
a deposit can never move it. The NYSE session calendar is treated as known in advance, exactly
as ``f_index.CalendarAllocator`` treats it -- it is calendar knowledge, not price data, and no
bar dated after d is touched. Pure: no clock-reading, no randomness, no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Literal

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    factor_lookback,
    factor_rows,
    prepare_factor,
)

ADDED = date(2026, 10, 12)
BENCH = "SPY"  # the market leg, and the instrument whose bars fix the shared window
#: The lab's standard member screen, ranking switched off (we rank on dollar volume ourselves) and
#: the 200-day trend gate switched OFF: the calendar is the only timing rule in this method.
SCREEN = FactorParams(rank="momentum", top=20, trend=None)
LOOKBACK = factor_lookback(SCREEN)  # 253, the same constant M0084 ran on: one shared window
TOP = 20  # EW20 slots; equal_weight(20) = 0.05 each, the whole book invested when the clock is on

#: Bouman & Jacobsen's "winter": the months the Halloween clock holds.
WINTER: frozenset[int] = frozenset({11, 12, 1, 2, 3, 4})
#: The two months the older folklore blames, and the only ones the narrow clock sits out.
AUTUMN: frozenset[int] = frozenset({9, 10})

Book = Literal["spy", "ew"]
Clock = Literal["none", "halloween", "sepoct"]
_BOOKS: tuple[str, ...] = ("spy", "ew")
_CLOCKS: tuple[str, ...] = ("none", "halloween", "sepoct")


@dataclass(frozen=True, slots=True)
class ClockParams:
    """What is held when the clock is on, and which stretch of the calendar turns it off."""

    book: Book = "spy"
    clock: Clock = "none"
    top: int = TOP  # EW20 slots; read only when book == "ew"

    def __post_init__(self) -> None:
        if not isinstance(self.book, str) or self.book not in _BOOKS:
            raise ValueError(f"book must be one of {_BOOKS}, got {self.book!r}")
        if not isinstance(self.clock, str) or self.clock not in _CLOCKS:
            raise ValueError(f"clock must be one of {_CLOCKS}, got {self.clock!r}")
        if isinstance(self.top, bool) or not isinstance(self.top, int):
            raise TypeError(f"top must be an int, got {type(self.top).__name__}")
        if not 1 <= self.top <= 100:
            raise ValueError(f"top must be in [1, 100], got {self.top}")

    def as_dict(self) -> dict[str, str]:
        return {"book": self.book, "clock": self.clock, "top": str(self.top)}


def _check(params: object) -> ClockParams:
    if not isinstance(params, ClockParams):
        raise TypeError(f"params must be ClockParams, got {type(params).__name__}")
    return params


def clock_on(clock: Clock, data_date: date) -> bool:
    """Is the book held over the session this decision fills on?

    ``S = next_session(data_date)`` is the session a monthly rank is filled at, so S's calendar
    month is the month the position is actually held in. A decision taken on the last session of
    October therefore reads November, which is what "hold from November" means.
    """
    if clock == "none":
        return True
    month = dates.next_session(data_date).month
    if clock == "halloween":
        return month in WINTER
    return month not in AUTUMN


@dataclass(frozen=True, slots=True, eq=False)
class ClockPrepared:
    """Both views the two books need: SPY's own bars, and the screen's rolling features."""

    history: Mapping[str, History]
    factor: FactorPrepared


class CalendarClockAllocator:
    """The chosen book at full weight while the calendar says on, all cash while it says off."""

    id = "M0120"

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK  # one constant for every variant: all six scored on the same sessions

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)  # read by both books, so both start on the same session

    def holds(self, params: Any) -> tuple[str, ...]:
        return (BENCH,) if _check(params).book == "spy" else ()

    def uses_members(self, params: Any) -> bool:
        return _check(params).book == "ew"

    def _spy(self, history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: no new target
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def _ew(self, rows: list[Any], p: ClockParams) -> tuple[Target, ...]:
        """The ``top`` eligible members with the largest 20-day dollar volume, equal weight."""
        chosen = sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[: p.top]
        w = equal_weight(p.top)
        out: list[Target] = []
        for row in chosen:
            t = target_from_close(row.symbol, row.close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not clock_on(p.clock, data_date):
            return ()
        if p.book == "spy":
            return self._spy(history, data_date)
        return self._ew(factor_rows(history, members, data_date, SCREEN), p)

    def prepare(self, history: Mapping[str, History]) -> ClockPrepared:
        return ClockPrepared(MappingProxyType(dict(history)), prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ClockPrepared):
            raise TypeError(f"prepared must be ClockPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not clock_on(p.clock, data_date):
            return ()
        if p.book == "spy":
            return self._spy(prepared.history, data_date)
        return self._ew(prepared.factor.rows_on(members, data_date, SCREEN), p)


CLOCK = CalendarClockAllocator()


def _v(suffix: str, params: ClockParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0120-{suffix}", family="M0120", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CLOCK, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0120",
    name=(
        "A safety rule that cannot be fitted: step aside by the calendar, not by the chart"
    ),
    family="market-calendar-clock",
    source_kind="knowledge",
    source_ref=(
        "Bouman & Jacobsen (2002), The Halloween Indicator, 'Sell in May and Go Away': Another "
        "Puzzle, American Economic Review 92(5); the lab's own M0084 measurement of the SPY "
        "200-day switch"
    ),
    parent_id=None,
    hypothesis=(
        "Published 2002 and heavily publicised since, so the dev window's second half already "
        "sees a crowd that knows it, and a fade after 2009 is the base case rather than a "
        "surprise. THE POINT IS TO PRICE THE FRAME, NOT TO FIND AN EDGE, exactly as M0084 did "
        "for the 200-day switch: a 100%-SPY book cannot beat SPY except by sitting out falls for "
        "less than the rallies it also sits out, so no SPY-layer variant is expected to clear the "
        "go-live bars and none should be promoted. M0084 measured the switch alone and found the "
        "monthly reading worth +1.4 points a year on the owner's deposits (+9.1% against +7.7% "
        "for buy-and-hold SPY) at an 18.9% worst fall against SPY's 55%, the weekly reading worth "
        "-3.3 points, and every reading 6 to 11 points a year behind plain SPY in 2009-2015. The "
        "question here is whether a clock that never reads a price buys the same insurance more "
        "cheaply. It has three properties nothing else in the lab has: it cannot be overfitted to "
        "the price series because it never reads it (no window, no band, no cadence to tune, and "
        "both stretches were named in print before the dev window opened); it flips twice a year, "
        "so Gotrade's real fees barely touch it where the weekly switch paid 0.7 points a year in "
        "fees alone; and it was out through September and October 2008 by construction rather "
        "than by reacting. Six variants, a 2x3 grid of two underlying books by three clock "
        "settings, every paired difference the clock alone. SPY-ALWAYS and EW20-ALWAYS are the "
        "no-clock controls through the identical fee, deposit and rounding path; HALLOWEEN holds "
        "November through April (Bouman & Jacobsen's window); SEPOCT holds every month except "
        "September and October. The underlying EW20 book is the 20 index members with the largest "
        "20-day dollar volume, equal weight, monthly, with the lab's standard screen and its "
        "200-day trend gate switched OFF -- a market-shaped book that ranks on size of trading "
        "rather than on anything that forecasts return, so it has no fitted signal for the clock "
        "to interact with and no kin among the lab's four out-of-sample failures, all of which "
        "rank on past return. Every variant shares the 253-bar lookback M0084 ran on, so all six "
        "and all six of M0084's are scored on the same sessions and the same deposits. The "
        "hypothesis under test, stated as a number: the HALLOWEEN clock on SPY gives up no more "
        "than 2 points a year of funded return against SPY-ALWAYS while cutting the worst fall by "
        "at least 20 points, which would make it cheaper insurance than the monthly 200-day "
        "switch bought for a +1.4 point gain at a 36-point drawdown cut. The second question is "
        "whether the narrow SEPOCT clock keeps more of the return for most of the protection, "
        "since it is out for two months a year rather than six. The third is whether the clock is "
        "worth more on an equal-weight book of big names than on SPY, since the seasonal effect "
        "is documented as larger in the average stock than in the cap-weighted index. WHAT WILL "
        "BE REPORTED WHETHER IT FLATTERS THE CLOCK OR NOT: the clock's contribution in 2008 "
        "separately from its contribution in 2009-2015, and the count of distinct May-October "
        "stretches the whole twenty-year result actually rests on -- if the answer is two "
        "autumns, the analysis will say so in those words, because that is the 200-day switch's "
        "disease wearing a different coat."
    ),
    expected_failure=(
        "The most likely outcome is that the twenty-year result rests on two or three summers "
        "-- 1998, 2002 and 2008 -- and that stripping them leaves the clock costing money, which "
        "is exactly what M0084 found for the switch and what insights 89, 91 and 93 found for "
        "every twenty-year edge in the lab. In 2009-2015 almost every May-October stretch was "
        "positive (2010, 2011 and 2015 are the exceptions and only 2011 badly so), so the clock "
        "should lag plain SPY by 2 to 5 points a year in the era most like today, and the lab "
        "will have learned a price without learning a frame to use. The 2008 dodge is also likely "
        "to be far less clean than it looks: the Halloween clock holds November through April, so "
        "it was fully invested through November 2008 (-7%) and January-February 2009 (-8% and "
        "-11%), and may well breach the 20% drawdown bar on that leg alone despite sitting out "
        "September and October. Trade counts on the SPY layer will be tiny -- two flips a year, "
        "about 40 over the window -- so profit factor and DSR are close to meaningless there and "
        "the >= 100 trades condition fails by construction; the funded return, the worst fall and "
        "the era split are the only readable numbers on that layer. The EW20 layer has the "
        "opposite problem: 20 slots re-picked monthly with no trend gate of any kind, so "
        "EW20-ALWAYS should fall 50% or more in 2008 (M0024's ungated book fell 61%) and both "
        "clocked versions should breach 20% too, because neither clock is out in the autumn of "
        "2008 AND the winter that followed. Ranking big members by dollar volume may also simply "
        "reproduce SPY with extra fees and a small-company tilt, in which case the EW20 column "
        "adds nothing the SPY column did not already say. Not modelled, and it cuts in the "
        "clock's favour: interest on the cash held while the clock is off. The Halloween clock is "
        "out for half of every year and US cash paid 3-5% a year over most of 1994-2007, so the "
        "un-modelled interest is worth roughly 1.5 to 2.5 points a year to it, and every return "
        "reported for a clocked variant is therefore a lower bound. Finally, the whole exercise "
        "may be unanswerable at this sample size: twenty-one summers is twenty-one observations, "
        "the standard error on a seasonal mean that thin is several points a year, and no "
        "honest reading of it can separate a real calendar effect from a run of luck. If that is "
        "what the numbers say, the analysis will say it and the method will be rejected."
    ),
    candidates=(
        _v("SPY-ALWAYS", ClockParams("spy", "none"),
           "Control: hold SPY, no clock, through the same fee and deposit path as the rest"),
        _v("SPY-HALLOWEEN", ClockParams("spy", "halloween"),
           "SPY from November through April, cash from May through October"),
        _v("SPY-SEPOCT", ClockParams("spy", "sepoct"),
           "SPY every month except September and October, which are held in cash"),
        _v("EW20-ALWAYS", ClockParams("ew", "none"),
           "Control: the 20 most-traded index members, equal weight, monthly, no clock"),
        _v("EW20-HALLOWEEN", ClockParams("ew", "halloween"),
           "The same 20-name book, held November through April only"),
        _v("EW20-SEPOCT", ClockParams("ew", "sepoct"),
           "The same 20-name book, stood down in September and October only"),
    ),
    seen_keys=(
        "concept:halloween-indicator",
        "concept:sell-in-may-calendar-clock",
        "concept:september-october-avoidance",
        "concept:equal-weight-most-traded-members",
    ),
)
