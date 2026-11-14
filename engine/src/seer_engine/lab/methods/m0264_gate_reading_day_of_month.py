"""M0264 -- Is the lab's own monthly gate reading a lucky day of the month?

Source: variation of M0262 (its anchored-gate overlay, its host book and its 454-bar lookback all
carried, the grid's coordinate replaced by a day of the month); Faber (2007), "A Quantitative
Approach to Tactical Asset Allocation", JWM 9(4), for the long-moving-average switch itself. The
switch is nineteen years old and this method changes nothing about what it says or how often it is
asked -- only the DAY OF THE MONTH it is asked on. So no fade argument applies to the rule.

Every figure below is the MONEY-WEIGHTED return on the owner's own monthly deposits -- what
``lab show`` prints as "your money earned" -- read back from ``lab show M0262`` and
``lab show M0088`` on 2026-11-14.

WHAT IS LEFT UNMEASURED. M0261 and M0262 slid the date a gate is read at about TWO readings a
year, and M0262 found its two maximally separated pairs about 1.1 points a year apart (9.8%
against 8.7% on the calendar-locked grid, 9.6% against 8.5% on the calendar-free one), with one
arm falling 41.8% where the monthly reading fell 18.7%. Nobody has slid the date at the rarity
the lab actually runs: twelve readings a year. Every monthly book in the lab acts on the first
session of each calendar month from the previous session's close (``sim.rules.is_rank_session``),
so every gate in the lab is read at the LAST session of a month. Nobody chose that session.

WHAT THE ALLOCATOR CAN AND CANNOT MOVE. On a monthly rule set the allocator runs only on the
monthly decision sessions, so the day the book ACTS on cannot move without a new rule set, and an
arm on another rule set is another book, not another reading. What can move is the day the gate
is READ: an arm with ``gate_day = k`` asks the gate on the newest session on or before the data
date that is the k-th session of its own calendar month (the month's last session when the month
is shorter than k), and acts on that answer at the usual monthly session. The anchor is never
later than the data date, so every arm is strictly safer on look-ahead than the native reading.

**That makes this ladder a day-of-month ladder and a STALENESS ladder at once, and the two cannot
be separated on this chassis.** A reading taken on the 5th session of a month is acted on about
sixteen sessions later; one taken on the 17th about four. A result that moves steadily with the
rung is about the age of the reading. A result that jumps about with no order is about the date.
The analysis must say which it saw and must not call a steady slope "luck of the day".

THE IDEA ROW'S TOP RUNG WAS EMPTY, AND A COUNT CAUGHT IT. The row asked for the 5th, 9th, 13th,
17th and 21st session of the month. A feasibility count on SPY's dev-store bars, made before this
file was written and reading no return (237 monthly decisions, 1996-01-03 to 2015-10-16; the
script compares the gate's yes/no at the anchor with its yes/no at the data date): the 21st
session, clamped, IS the month's last session in 156 of 237 months and at most two sessions
before it in the rest, and its reading differs from the native one in **0 of 237** months. That
arm would be the native book under another label -- a ladder rung that measured nothing. The
other four rungs differ from the native reading in 15 (17th), 18 (13th), 23 (9th) and 21 (5th)
months, and the 1st session of the month -- the reading a full month old, the far end of the axis
the row left out -- differs in 15. So the 21st is replaced by the 1st. The change is forced by a
count of calendar positions and yes/no readings, not by any return.

THE SIX ARMS, all M0088-C-LIVE-63's book verbatim on ``monthly-hold-frac-gotrade``:

    arm      gate read on                 sessions before acting   readings that differ, of 237
    NATIVE   the month's last session     0                        --   (control: trial 289's book)
    D17      17th session of the month    about 4,  at most 6      15
    D13      13th session                 about 8,  at most 10     18
    D9       9th session                  about 12, at most 14     23
    D5       5th session                  about 16, at most 18     21
    D1       1st session                  about 20, at most 22     15

NATIVE is a control and not a new book: it is M0088-C-LIVE-63, first recorded as trial 289 and
repeated as M0261-NATIVE and M0262-NATIVE (trial 863): 10.6% a year of the owner's money, an
18.7% worst fall, 528 trades. It is re-run here, declared, because every paired difference this
method reports must be measured against a zero rung from the same run on the same store, and
because its exact reproduction is the proof the overlay is the host.

THE PRE-REGISTERED PREDICTION, carried from the idea row. The spread of money-weighted return
across the six arms (best minus worst) is UNDER 0.5 points a year: at twelve readings a year
nobody is ever committed to a bad reading for longer than a month, which is the mechanism M0262
found. The surprise worth auditing the lab for is a spread OVER 1.0 point. Between the two the
result is unreadable and must be reported as such. On the fall: no arm falls more than 5 points
deeper than NATIVE.

THE LOOKBACK is 454 at every rung, M0261's and M0262's own number, so the three ladders are
scored under identical arithmetic. The need here is 200 bars plus at most 22 of staleness.

No hand-written always-invested arm: no arm here reverses another, and the gate's own bill on
this book is M0262's registered amendment, not this method's question.

Pure: no clock, no randomness, no network, no file, no printing. Reads only bars and dividends
dated on or before ``data_date``, plus the published NYSE calendar.
"""

from __future__ import annotations

import calendar
from bisect import bisect_left
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared
from seer_engine.lab.methods.m0088_calm_big_raisers import CALM, CalmParams, X, choose
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 11, 14)

#: The furthest behind the data date an anchor may sit, in sessions: M0261's and M0262's own
#: number, carried so all three ladders share one lookback. This grid needs at most 22.
MAX_ANCHOR_GAP = 254

#: The gate's window, which is ``inner.trend``'s length for every book on this chassis.
TREND_N = 200

#: No NYSE month has more sessions than this, so a larger ``gate_day`` could only ever mean "the
#: last session", which is the native reading and not a rung.
MAX_GATE_DAY = 23


@lru_cache(maxsize=None)
def _month_sessions(year: int, month: int) -> tuple[date, ...]:
    """Every NYSE session of one calendar month, from the published calendar. No price is read."""
    return tuple(dates.sessions(date(year, month, 1),
                                date(year, month, calendar.monthrange(year, month)[1])))


def opens_reading(d: date, day: int) -> bool:
    """True when ``d`` is the ``day``-th session of its month, or its last when it is shorter.

    Reads ``d`` and the published exchange calendar and nothing else -- not a price, not how many
    bars the caller holds -- so the prepared path and the lookback-window path answer alike.
    """
    ms = _month_sessions(d.year, d.month)
    i = bisect_left(ms, d)
    if i == len(ms) or ms[i] != d:
        return False
    return i + 1 == min(day, len(ms))


def day_anchor(h: History | None, data_date: date, day: int) -> date:
    """The newest bar of ``h`` on or before ``data_date`` that opens a reading.

    ``data_date`` itself when no such bar is on hand. Never later than ``data_date``. The walk is
    at most 22 bars over the dev window (measured), so it is literal rather than vectorised.
    """
    if h is None:
        return data_date
    i = h.index_of(data_date)
    if i is None:
        return data_date
    for j in range(i, -1, -1):
        a = h.dates[j].item()
        if opens_reading(a, day):
            return a
    return data_date


@dataclass(frozen=True, slots=True)
class DayParams:
    """``book`` is M0088-C-LIVE-63's book, carried whole; ``gate_day`` is WHEN its gate is read.

    ``gate_day = None`` is the native reading, at the data date. Otherwise it names the session
    of the calendar month the gate is asked on.
    """

    book: CalmParams
    gate_day: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.book, CalmParams):
            raise TypeError(f"book must be CalmParams, got {type(self.book).__name__}")
        if self.book.ann.base.inner.trend is None:
            raise ValueError("book must carry a trend symbol and length for the anchor to read")
        if self.gate_day is None:
            return
        if isinstance(self.gate_day, bool) or not isinstance(self.gate_day, int):
            raise ValueError(f"gate_day must be an int or None, got {self.gate_day!r}")
        if not 1 <= self.gate_day <= MAX_GATE_DAY:
            raise ValueError(f"gate_day must lie in [1, {MAX_GATE_DAY}], got {self.gate_day}")

    def as_dict(self) -> dict[str, str]:
        native = self.gate_day is None
        out = {
            "gate_day": "native" if native else str(self.gate_day),
            "gate_reads": "the last session of each month" if native
            else f"session {self.gate_day} of each month",
        }
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> DayParams:
    if not isinstance(params, DayParams):
        raise TypeError(f"params must be DayParams, got {type(params).__name__}")
    return params


class DayGateAllocator:
    """M0088's calm-raisers book, with its own 200-day gate read on a chosen day of the month."""

    id = "M0264"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        """454 bars at every rung, so no arm's scored window differs from another's."""
        return max(CALM.lookback(_check(params).book), TREND_N + MAX_ANCHOR_GAP)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return CALM.symbols(_check(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return CALM.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return CALM.uses_members(_check(params).book)

    def _on(self, history: Mapping[str, History], data_date: date, p: DayParams) -> bool:
        """The one thing this allocator replaces: the DATE the gate is read at.

        The gate is ``f_factor.trend_on`` in both branches. The native rung runs the host's own
        code path, because its job is to reproduce a recorded trial.
        """
        inner = p.book.ann.base.inner
        if p.gate_day is None:
            return trend_on(history, data_date, inner)
        return trend_on(history, day_anchor(history.get(inner.trend[0]), data_date, p.gate_day),
                        inner)

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: DayParams) -> tuple[Target, ...]:
        """M0088's own ``_run``, with exactly the gate's date replaced."""
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        inner = p.book.ann.base.inner
        if not self._on(prepared.history, data_date, p):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        return choose(prepared.history, rows, prepared.calendar, data_date, held, p.book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target."""
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> RaisePrepared:
        return CALM.prepare(history)

    def prepare_market(self, market: Any) -> RaisePrepared:
        return CALM.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


DAYGATE = DayGateAllocator()

#: M0088-C-LIVE-63's configuration, verbatim: the calm half of the live raisers on a 63-session
#: swing. First recorded as trial 289.
BOOK = CalmParams(X, "calm", "live", 63)

#: The ladder, as (suffix, gate_day). ``None`` is the native reading.
LADDER: tuple[tuple[str, int | None], ...] = (
    ("NATIVE", None),
    ("D17", 17),
    ("D13", 13),
    ("D9", 9),
    ("D5", 5),
    ("D1", 1),
)

_RATIONALE = {
    "NATIVE": "Control: M0088-C-LIVE-63's book (first recorded as trial 289, repeated as "
              "M0262-NATIVE), the gate read at the data date through the host's own code path. "
              "The zero rung every other arm is paired against; not a new book. If it does not "
              "reproduce 10.6% of the owner's money, an 18.7% fall and 528 trades, every paired "
              "difference here is void.",
    "D17": "the gate read on the 17th session of the month and acted on about four sessions "
           "later: the freshest rung whose reading ever differs from the native one (15 of 237 "
           "months).",
    "D13": "the gate read on the 13th session, about eight sessions before acting (differs from "
           "native in 18 of 237 months).",
    "D9": "the gate read on the 9th session, about twelve sessions before acting (differs from "
          "native in 23 of 237 months, the most of any rung).",
    "D5": "the gate read on the 5th session, about sixteen sessions before acting (differs from "
          "native in 21 of 237 months).",
    "D1": "the gate read on the month's first session and acted on at the next month's first "
          "session: a reading a full month old, the far end of the axis. Replaces the idea "
          "row's 21st-session rung, whose reading never differs from the native one.",
}


def _v(suffix: str, gate_day: int | None) -> Candidate:
    return Candidate(id=f"M0264-{suffix}", family="M0264", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DAYGATE, params=DayParams(BOOK, gate_day),
                     rationale=_RATIONALE[suffix], added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0264",
    name="Is the lab's own monthly reading itself a lucky day? The same gate read twelve times a "
         "year, slid across every session of the month",
    family="market-trend-switch",
    source_kind="variation",
    source_ref=(
        "variation of M0262 (its anchored-gate overlay, its host book and its 454-bar lookback "
        "all carried, the grid's coordinate replaced by a day of the month); Faber (2007), A "
        "Quantitative Approach to Tactical Asset Allocation, JWM 9(4), for the switch itself"
    ),
    parent_id="M0262",
    panel_exempt=(
        "market: the day of the month the SPY 200-day switch is read on, over M0088-C-LIVE-63's "
        "picks carried verbatim"
    ),
    hypothesis=(
        "Published 2007 (the long-moving-average switch), so nothing in the rule is a new anomaly "
        "and no fade argument applies; this method changes nothing about what the switch says or "
        "how often it is asked, only the DAY OF THE MONTH it is asked on. Every figure is the "
        "MONEY-WEIGHTED return on the owner's own monthly deposits, read back from the lab on "
        "2026-11-14. WHAT IS LEFT UNMEASURED. M0261 and M0262 slid the date a gate is read at "
        "about two readings a year, and M0262 found its two maximally separated pairs about 1.1 "
        "points a year apart (9.8% against 8.7% calendar-locked, 9.6% against 8.5% "
        "calendar-free), with one arm falling 41.8% where the monthly reading fell 18.7%. Its "
        "mechanism was commitment length: a rarely read gate is stuck with a bad reading for "
        "months. Nobody has slid the date at the rarity the lab actually runs, twelve readings a "
        "year. Every monthly book in the lab acts on the first session of each calendar month "
        "from the previous session's close, so every gate in the lab is read at the LAST session "
        "of a month, and nobody chose that session. WHAT CAN MOVE. On a monthly rule set the "
        "allocator runs only on the monthly decision sessions, so the day the book ACTS on cannot "
        "move here; the day the gate is READ can. An arm with gate day k asks the switch on the "
        "newest session on or before the data date that is the k-th session of its own calendar "
        "month (the month's last when the month is shorter), and acts on that answer at the "
        "usual monthly session. The anchor is never later than the data date, so no arm can look "
        "ahead. THIS MAKES THE LADDER A DAY-OF-MONTH LADDER AND A STALENESS LADDER AT ONCE, and "
        "the two cannot be separated on this chassis: a reading from the 5th session is acted on "
        "about sixteen sessions later, one from the 17th about four. A result that moves "
        "steadily with the rung is about the age of the reading; a result that jumps about with "
        "no order is about the date. THE IDEA ROW'S TOP RUNG WAS EMPTY AND A COUNT CAUGHT IT "
        "BEFORE THIS FILE WAS WRITTEN. The row asked for the 5th, 9th, 13th, 17th and 21st "
        "session. A feasibility count on SPY's dev-store bars that reads no return (237 monthly "
        "decisions, 1996-01-03 to 2015-10-16, the switch's yes/no at the anchor against its "
        "yes/no at the data date) found the 21st session, clamped, is the month's last session "
        "in 156 of 237 months and at most two sessions before it otherwise, and its reading "
        "differs from the native one in 0 of 237 months: that arm would be the native book under "
        "another label. The other rungs differ in 15 (17th), 18 (13th), 23 (9th) and 21 (5th) "
        "months, and the month's 1st session -- a reading a full month old, the far end the row "
        "left out -- in 15. So the 21st is replaced by the 1st, on a count and not on any "
        "return. THE SIX ARMS all hold M0088-C-LIVE-63's book verbatim on "
        "monthly-hold-frac-gotrade, fractional shares at Gotrade's real fees: NATIVE, D17, D13, "
        "D9, D5 and D1. NATIVE IS A CONTROL AND NOT A NEW BOOK: it is M0088-C-LIVE-63, first "
        "recorded as trial 289 and repeated as M0262-NATIVE at trial 863 (10.6% a year of the "
        "owner's money against 7.2% for the same deposits in SPY, an 18.7% worst fall, 528 "
        "trades). It is re-run, declared, because every paired difference must be measured "
        "against a zero rung from the same run on the same store, and because its exact "
        "reproduction is the proof the overlay is the host. THE PRE-REGISTERED PREDICTION, "
        "carried from the idea row: the spread of money-weighted return across the six arms, "
        "best minus worst, is UNDER 0.5 points a year, because at twelve readings a year nobody "
        "is committed to a bad reading for longer than a month. THE SURPRISE worth auditing the "
        "lab for is a spread OVER 1.0 point, which would mean the last-session convention is a "
        "fitted choice nobody checked. Between 0.5 and 1.0 the result is unreadable and is "
        "reported as that. On the fall: no arm falls more than 5 points deeper than NATIVE. THE "
        "LOOKBACK is 454 at every rung, M0261's and M0262's own, so the three ladders share one "
        "arithmetic; this grid needs 200 bars plus at most 22. SUCCESS IS A MEASUREMENT, NOT "
        "ELIGIBILITY: an arm that clears the screen is the host's book read on another day, a "
        "draw from the distribution this method measures and not a configuration to promote, "
        "and no test-window look is spent under any outcome. Assumed without asking: that "
        "swapping the row's empty 21st-session rung for the 1st is a refinement and not a "
        "different method; that carrying the host's picks verbatim behind a market-wide switch "
        "is a market exemption from the panel, as the coordinator directed; and that no "
        "always-invested arm belongs here, because no arm reverses another and the switch's own "
        "bill on this book is M0262's registered amendment."
    ),
    expected_failure=(
        "First and most likely: THE SPREAD IS SMALL AND THE METHOD ONLY CONFIRMS THE CONVENTION "
        "IS SAFE. That is the prediction coming true and a thin result: it closes the series and "
        "nobody should spend another id on when a monthly gate is read. Second, A STEADY SLOPE "
        "MISREAD AS LUCK. The rungs are ordered by the age of the reading, so the natural way "
        "for the spread to exceed a point is for older readings to do steadily worse (or, "
        "because an older reading flips less often and trades less, steadily better). That "
        "would be a finding about staleness, already half-known from M0260's cadence ladder, "
        "and not evidence the lab stands on a lucky session. Third, TWO SLOW CRASHES. The dev "
        "window's falls of 2000-2002 and 2007-2009 were slow, and a reading two or three weeks "
        "old costs little in a slow fall; 1987 and 2020 are what a fast one looks like and "
        "neither is in the window, so a small spread here does not promise a small one there. "
        "Fourth, THE SPREAD IS A HANDFUL OF MONTHS. Each rung differs from the native reading in "
        "only 15 to 23 of 237 months, so any gap is the luck of those few months and six arms "
        "are six draws, not a distribution; the measured noise between blind draws on this "
        "chassis is wider than the half point this method predicts. Fifth, THE CONTROL MIGHT "
        "DRIFT: if NATIVE does not reproduce the host's recorded row on today's store, the "
        "paired differences are still measured within one run, but the comparison with M0262's "
        "ladder is void and must not be quoted. Sixth, SIX ARMS ON ONE BOOK: the host is "
        "dev-eligible on its own record, so an arm here may read eligible for the same reason, "
        "and promoting it would be promoting a reading date. Seventh, interest on idle cash is "
        "not modelled, and falls on every arm about equally."
    ),
    candidates=tuple(_v(suffix, day) for suffix, day in LADDER),
    seen_keys=(
        "concept:gate-reading-day-of-month",
        "concept:monthly-gate-reading-staleness-ladder",
    ),
)
