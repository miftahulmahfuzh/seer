"""M0262 -- Is the gate's slow-reading spread a CALENDAR problem or a RARITY problem?

Source: variation of M0261 (whose anchored-gate overlay, whose host book and whose lookback are
all carried, with the grid's coordinate replaced); Faber (2007), "A Quantitative Approach to
Tactical Asset Allocation", JWM 9(4), for the long-moving-average switch itself. The switch is
nineteen years old, nothing in it is a new anomaly, and this method changes nothing about what it
says -- only the DATE it is asked. So no fade argument applies to the rule, and what is new is the
question.

Every figure below is the MONEY-WEIGHTED return on the owner's own monthly deposits -- what
``lab show`` prints as "your money earned" -- because these books are funded with a monthly
top-up, except where a line says UNFUNDED, which marks the SPY-alone prior grid and nothing else.
SPY's figure is the SAME deposits put into SPY over the same window.

WHAT M0261 SETTLED AND WHAT IT LEFT OPEN. M0261 measured, on M0088-C-LIVE-63's calm big
dividend-raisers book at Gotrade's real fees on the owner's deposits, that two readings of the
SPY-200 gate taken EXACTLY as often as each other but on different calendar months differ by 3.21
points a year of money (Jun/Dec 10.57% against Mar/Sep 7.36%), and that two once-a-year readings
six months apart differ by 8.2 points of worst fall (Dec 19.2% against Jun 27.4%). Both gaps are
LARGER than the whole weekly-to-yearly interval ladder, which spans 2.21 points of money and 4.5
of fall on the same book. So past monthly the gate's reading axis is not a speed. What it IS has
two candidate answers, and they prescribe opposite things:

    (A) THE CALENDAR IS THE PROBLEM. A month-end grid is an arbitrary human convention; the dev
        window's two crashes sit at particular places in it; a rule that fired on a SESSION COUNT
        instead would show a much smaller spread as its starting point slid. If so the lesson
        generalises far past this gate: several lab books re-pick monthly and several measure calm
        or strength over windows ending at month ends, and every one of them stands on a grid
        nobody chose. THAT WOULD BE AN AUDIT OF THE WHOLE LAB.

    (B) RARITY IS THE PROBLEM. A gate asked twice a year is a stale promise whatever grid it sits
        on; the spread is the irreducible variance of reading rarely; a session grid will spread
        just as wide. If so the lesson is narrow and already known -- read the gate every month --
        and no other book needs auditing.

THE IDEA ROW'S DESIGN WAS BROKEN, AND THE PRIOR IS WHAT CAUGHT IT. The row that reserved this id
specified "the same gate read every 126 TRADING DAYS, with the start offset slid across the
period", on the grounds that a session count has "no calendar anywhere in it". That sentence is
false, and ``docs/backtests/2026-10-20-gate-reading-sessions.py`` Job E proved it before a line of
this file was written. The NYSE ran 248 to 254 sessions in each whole year of the dev window and
averaged 251.8, so 126 sessions is half a year to within a fifth of a session, and a 126-session
reading drifts **-0.2 sessions a year** through the calendar -- which is to say it does not drift
at all. Measured over 1994-2015, its offset 0 reads ONLY in June, July and December, and its
offset 63 reads ONLY in March, April, September and October. **A 126-session grid is a calendar
grid wearing a session label.** Running it alone could only ever have produced "the session grid
spreads like the calendar grid", which is a near-tautology dressed as a finding, and the method id
would have been spent on nothing. A period coprime with the year's session count does drift: 131
sessions drifts -10.2 sessions a year and sweeps **all twelve calendar months** across the window,
at 1.92 readings a year against 126's 2.05 and the calendar half-yearly grid's 2.00 -- the same
rarity, no calendar lock.

So this method runs BOTH periods, and the comparison it is bought for is **between a
calendar-LOCKED session grid and a calendar-FREE one at the same rarity**, with M0261's calendar
grid as the third point of reference. That is a strictly better instrument than the row's, and the
change is forced by an arithmetic fact about the exchange calendar, not by any return: the drift
job reads no prices at all.

THE UNFUNDED PRIOR, measured on the dev store in ONE sweep in ONE process before this file existed
(SPY alone, a 200-bar average, a one-session lag, a monthly acting calendar, the reading held as
taken; UNFUNDED, so plain CAGRs that are NOT comparable with the money-weighted figures above).
Measuring both grids in one sweep is deliberate: a spread measured on one tape and compared with a
spread measured on another is not a comparison, and the file reproduces all seven numbers M0261's
own prior quotes, to the digit, as its proof that it is reading the same tape.

    grid                                 draws   range      sd   mean pair gap   fall sd
    SESSION period 126 (LOCKED)            126   5.78p   1.38p           1.55p      9.0p
    SESSION period 131 (FREE)              131   5.26p   1.31p           1.51p      8.1p
    CALENDAR half-yearly (M0261's)           6   3.73p   1.34p           1.78p      2.8p
    CALENDAR yearly (M0261's)               12   4.55p   1.32p           1.59p      9.1p

**Four grids at four different coordinates, and their standard deviations are 1.31, 1.32, 1.34
and 1.38 -- a span of seven hundredths of a point on figures of one and a third.** The range is
not the statistic to read here and the sd is, because a 131-offset grid out-ranges a 6-phase grid
for free: more draws spread wider whatever the mechanism. On the statistic that does not grow with
the draw count, removing the calendar entirely changes nothing. On the unfunded shadow, the answer
is (B), and it is not close.

THE SIX ARMS. All six hold M0088-C-LIVE-63's book verbatim on ``monthly-hold-frac-gotrade``. ONLY
the date the gate is read at moves, and it moves strictly backwards, so no arm can look ahead.

    arm        period  offset  readings/yr  calendar months read      why this arm exists
    NATIVE     --      --      ~12          all twelve                the zero rung, and the
                                                                      reproduction of the host
    LOCK-0     126      0      2.05         Jun/Jul/Dec               calendar-LOCKED, and the
                                                                      bridge back to M0261
    LOCK-63    126     63      2.04         Mar/Apr/Sep/Oct           the locked pair's other
                                                                      half, maximally separated
    FREE-0     131      0      1.97         all twelve                calendar-FREE
    FREE-33    131     33      1.97         all twelve                the free grid's quarter
                                                                      point
    FREE-65    131     65      1.97         all twelve                the free pair's other half,
                                                                      maximally separated

**The headline statistic is the MAXIMALLY SEPARATED PAIR at each period, and it is draw-matched by
construction.** LOCK-0 against LOCK-63 is two draws; FREE-0 against FREE-65 is two draws; M0261's
funded Jun/Dec against Mar/Sep was two draws. Half a period apart is exactly how Jun/Dec and
Mar/Sep sit on a six-month grid, so all three pairs have the same shape. FREE-33 is a third point,
there only so that the free pair's gap can be seen to be representative or not; it is never part
of the headline. The offsets were fixed on that structural argument -- maximal separation, plus
one quarter point -- and written into the prior script BEFORE the period-131 grid was computed, so
no offset here was chosen for how it scored.

**The locked pair is not a throwaway control: it is the bridge.** Unfunded, LOCK-0 and LOCK-63
read 8.55% and 6.69%, a gap of 1.86 points -- which is, to the hundredth, M0261's own unfunded
Jun/Dec against Mar/Sep gap of 1.86 points. That is what it should be, because offset 0 reads
Jun/Jul/Dec and offset 63 reads Mar/Apr/Sep/Oct. M0261 measured that same calendar pair FUNDED at
3.21 points, so the locked arms give this method a direct, same-shape handle on how much funding
and stock picking amplify a date gap on this exact book: **1.7 times**, if LOCK reproduces it.

THE LOOKBACK: 454, THE SAME AT EVERY RUNG -- ``max(CALM.lookback(book), 200 + 254)``, deliberately
M0261's own number so that the two methods' ladders are scored under identical arithmetic. The
probe measured the worst anchor gap over all 237 monthly decision sessions of the dev window at
all five anchored arms: **130 sessions**, so 330 bars is the true requirement and 454 carries 124
sessions of margin. Equal lookbacks at every rung are what keep every paired difference here a
difference in the reading date alone. Widening from the host's 253 does NOT move the dev window's
first scored session: ``dev.candidate_window`` binds on ``MEMBERSHIP_START`` (1996-01-02) for any
lookback up to 739, so the window still opens at 1996-01-03, M0088-C-LIVE-63's own first scored
session. The standing rule is "never cross 739", not "never widen", and 454 is also inside the
473-session smoke fixture's hard cap.

WHY THE GRID COUNTS FROM A FIXED CALENDAR EPOCH AND NOT FROM "THE SYMBOL'S FIRST BAR". The idea
row wrote the count as starting from the symbol's first bar. That cannot be used, and the reason
is a property of how the lab drives an allocator rather than a preference: on the single-symbol
path the allocator is handed a LOOKBACK WINDOW and on the prepared path a FULL history, so "the
first bar" is a different bar in the two paths and the anchor would move between them -- the same
configuration would score differently depending on which path ran it. ``session_index`` counts
NYSE sessions from the first session of 1990, which is path-independent, point-in-time, and reads
the published exchange calendar rather than any price. It loses nothing: sliding the epoch only
relabels which offset is called zero, and the prior sweeps every offset of both periods.

WHY A NEW ALLOCATOR ID AND NOT M0261'S. ``PhaseParams`` holds ``gate_months`` and ``gate_phase``
and has no period field. Giving it one would move every recorded config digest that carries it --
M0261's six rows included -- which the lab forbids. The session coordinate therefore lives in a
new dataclass behind a new allocator id, and that costs one method id, which is the correct price.
Nothing is imported from M0261's running code: the overlay is re-expressed here so that the test
module can assert the two agree where they must (the native path) without the agreement being a
tautology.

HOW THE OVERLAY WORKS, AND THE ONE THING IT REPLACES. ``SessionGateAllocator`` delegates
``symbols``, ``holds``, ``uses_members``, ``prepare`` and ``prepare_market`` to M0088's ``CALM``,
and runs M0088's own public ``choose`` on M0088's own prepared panel. Exactly one thing differs:
the DATE at which ``f_factor.trend_on`` is asked. At ``gate_period is None`` the date is the data
date, which is the host's own code path verbatim -- the native rung's job is to REPRODUCE a
recorded trial, and a reproduction runs the host's code rather than an anchor computed to equal
it. At ``gate_period = p`` it is ``offset_anchor(...)``: the SAME function, the same symbol, the
same 200-bar average, read at an earlier date. Nothing about what the gate SAYS is re-implemented
anywhere in this file.

THE PRE-REGISTERED PREDICTION, WRITTEN DOWN BEFORE THE RUN, WITH SIGNS AND SIZES.

    1. **(B) WINS ON A REAL FUNDED BOOK TOO.** The calendar-free pair's gap, |FREE-0 - FREE-65|,
       is at least 2.0 points a year of the owner's money -- at least two thirds of M0261's 3.21
       -- and the three free arms' standard deviation is at least 0.9 points. This is the claim
       the method is bought for. It is FALSIFIED by the free pair landing inside 1.0 point, which
       is the only outcome that would justify auditing the rest of the lab's calendar grids.
    2. **THE FREE GRID SPREADS AT LEAST AS WIDE AS THE LOCKED ONE.** |FREE-0 - FREE-65| >=
       |LOCK-0 - LOCK-63|, as it did unfunded (2.90 against 1.86). If removing the calendar made
       the spread SMALLER on a funded book, that is evidence for (A) that the shadow missed, and
       it must be reported as such rather than explained away.
    3. **THE LOCKED PAIR REPRODUCES M0261'S CALENDAR PAIR.** |LOCK-0 - LOCK-63| lands within 1.0
       point of M0261's funded 3.21, because the two pairs read nearly the same dates on nearly
       the same months. If it does not, the amplification from unfunded to funded is not stable on
       this book and every cross-method gap quoted in prediction 1 is softer than it reads.
    4. **NATIVE STILL WINS ON BOTH AXES AT ONCE.** The monthly reading beats all five anchored
       arms on money AND falls less deep than all five, as it did in M0261 (10.62% and 18.71%).
    5. **AT LEAST ONE FREE ARM FALLS DEEPER THAN 28%**, against NATIVE's recorded 18.71%. FREE-65
       is the one I expect it to be: unfunded it falls 43.4% against the locked pair's 27.0% and
       27.2%, because a drifting grid can land a reading just before a slow slide and hold it,
       where a month-end grid is at least pinned to a month boundary.
    6. **THE REPRODUCTION IS EXACT.** NATIVE returns M0088-C-LIVE-63's recorded row digit for
       digit -- 10.62% of the owner's money, an 18.71% worst fall, 528 trades, PF 3.52, exposure
       0.704 -- as M0261-NATIVE did (trial 854). It runs under a new config digest because the
       allocator id and the params class differ, but nothing else about it differs. If it drifts,
       every paired difference this method reports is void and the run must be read as a null.

SUCCESS IS A MEASUREMENT, NOT ELIGIBILITY. Prediction 1 coming true closes the question M0261
opened and closes it narrowly: the spread is rarity, the fix is "read the gate every month", and
no other book in the lab needs auditing for the grid it stands on. Prediction 1 failing -- a
calendar-free grid that does NOT spread -- would mean the lab is standing on an arbitrary human
convention in a dozen places and would be the most expensive finding of the batch. Either way an
arm that clears the screen is a draw from a distribution this method has measured, NOT a
configuration to promote.

NO TEST-WINDOW LOOK IS SPENT HERE, UNDER ANY OUTCOME. Four are spent and all four failed.

WHAT IS ALREADY DEAD AROUND THIS GATE, AND WHY A SESSION GRID IS NONE OF IT. Turning the gate OFF
(helped 22 of 22 variants whole-window, 0 of 22 after 2009). A TIME LOCK on the switch (deepens
the fall from 20% to 32%). An account-reading DRAWDOWN BRAKE (pays 10 points a year of 2009-2015
to save 40 of 2008). M0132's LEARNED fall-sizing brake. VIX-LEVEL confirmation. EXIT-BUFFER-ONLY,
CONFIRM-N-DAYS, PARTIAL EXPOSURE, FAST RE-ENTRY. The PRICE BAND, buried by M0258. And the reading
INTERVAL, swept weekly to yearly by M0260. Every one of those changes WHAT THE GATE SAYS or HOW
OFTEN it is asked. This method changes neither. The rule is Faber's, untouched; the rarity is
held fixed at about two readings a year; only the COORDINATE the dates are counted on moves.

Pure: no clock, no randomness, no network, no file, no printing. Reads only bars and dividends
dated on or before ``data_date``, plus the published NYSE calendar. ``held`` is read only where
M0088 reads it -- to let a name keep its slot -- and the anchor lives in the calendar and the
price path, never in the book, so a deposit cannot move it.
"""

from __future__ import annotations

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

ADDED = date(2026, 10, 20)

#: The year whose first NYSE session is session zero. Any epoch would do -- sliding it only
#: relabels which offset is called zero -- but it must be THE SAME ONE the prior script used, or
#: this file's offset 65 is not the offset 65 whose unfunded row the hypothesis quotes.
EPOCH_YEAR = 1990

#: The furthest behind the data date an anchor of this grid can sit, in sessions. Deliberately
#: M0261's own number so the two methods' ladders are scored under identical arithmetic. The probe
#: in ``docs/backtests/2026-10-20-gate-reading-sessions.py`` measured the worst gap over all 237
#: monthly decision sessions of the dev window at all five anchored arms: 130 sessions.
MAX_ANCHOR_GAP = 254

#: The slowest reading this method will accept, in sessions. A period of ``p`` can leave an anchor
#: ``p - 1`` sessions stale, so a period past ``MAX_ANCHOR_GAP + 1`` could ask for a 200-bar
#: average the lookback does not cover. The bound is therefore derived from the lookback rather
#: than chosen, which is what keeps the two numbers from drifting apart.
MAX_GATE_PERIOD = MAX_ANCHOR_GAP + 1

#: The gate's window, which is ``inner.trend``'s length for every book on this chassis.
TREND_N = 200


@lru_cache(maxsize=None)
def _year_sessions(year: int) -> tuple[date, ...]:
    """Every NYSE session of ``year``, from the published calendar. No price is read."""
    return tuple(dates.sessions(date(year, 1, 1), date(year, 12, 31)))


@lru_cache(maxsize=None)
def _year_base(year: int) -> int:
    """NYSE sessions from the epoch up to, but not including, 1 January of ``year``.

    Walks in both directions so that a bar older than the epoch gets a negative index rather than
    an exception. No store the lab runs has bars before 1990 -- the dev store opens in 1993 and
    the smoke fixture in 2013 -- but an allocator that raises on a date is an allocator that can
    fail a run for a reason that looks like the method, and this costs one branch to avoid.
    """
    if year == EPOCH_YEAR:
        return 0
    if year > EPOCH_YEAR:
        return _year_base(year - 1) + len(_year_sessions(year - 1))
    return _year_base(year + 1) - len(_year_sessions(year))


def session_index(d: date) -> int:
    """The number of NYSE sessions in [EPOCH_YEAR-01-01, ``d``], minus one.

    The session coordinate this method's grid is defined on, and the exact counterpart of M0261's
    ``month_index``: an absolute position read off the published exchange calendar, independent of
    whatever slice of history the caller happens to hold. That independence is the whole reason
    the grid is defined on this and not on a bar's position in the array it arrived in -- the lab
    hands an allocator a lookback window on one path and a full history on another, and a grid
    counted from "the first bar" would put the same configuration on two different schedules.

    Python's ``%`` returns a non-negative remainder for a positive modulus, so a pre-epoch date's
    negative index still lands on a well-defined rung of the grid.
    """
    ys = _year_sessions(d.year)
    return _year_base(d.year) + bisect_left(ys, d)


def offset_anchor(h: History | None, data_date: date, period: int, offset: int) -> date:
    """The newest bar of ``h`` on or before ``data_date`` whose session index opens a reading.

    The newest bar ``a <= data_date`` with ``session_index(a) % period == offset``; ``data_date``
    itself when no such bar is on hand. This is M0261's ``phase_anchor`` with its calendar
    coordinate -- "the last session of a calendar month whose month_index is right" -- replaced by
    a pure session count, and nothing else changed.

    **Never later than ``data_date``**, which makes every anchored reading strictly safer on
    look-ahead than the native one the lab already runs.

    **Point-in-time, and path-independent.** The test applied to a bar reads that bar's date and
    the published NYSE calendar, and nothing else: not its price, not its neighbours, not how many
    bars the caller is holding. So the prepared path (full history), the single-window path
    (lookback only) and the kit's lookback cut all answer the same question about the same bar,
    which is the property M0261's month-end anchor had to buy with a two-branch definition and
    this one gets for free.

    The walk is backwards and literal rather than vectorised. The worst case is ``period - 1``
    bars, which the probe measured at 130 over the dev window, and clarity is worth more than
    speed in the one function this method exists to introduce.
    """
    if h is None:
        return data_date
    i = h.index_of(data_date)
    if i is None:
        return data_date
    want = offset % period
    for j in range(i, -1, -1):
        a = h.dates[j].item()
        if session_index(a) % period == want:
            return a
    return data_date


@dataclass(frozen=True, slots=True)
class SessionParams:
    """``book`` is M0088-C-LIVE-63's book, carried whole; the rest is WHEN its gate is read.

    ``gate_period = None`` is the native reading -- the gate read at the data date, exactly as
    every book in the lab reads it -- and is legal here because the ladder needs a zero rung that
    runs through the same allocator id as its anchored ones. ``gate_offset`` must be absent
    exactly when ``gate_period`` is, and otherwise names which residue class of sessions the grid
    reads.
    """

    book: CalmParams
    gate_period: int | None = None
    gate_offset: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.book, CalmParams):
            raise TypeError(f"book must be CalmParams, got {type(self.book).__name__}")
        if self.book.ann.base.inner.trend is None:
            raise ValueError("book must carry a trend symbol and length for the anchor to read")
        if self.gate_period is None:
            if self.gate_offset is not None:
                raise ValueError("gate_offset must be None when the gate is read natively")
            return
        if isinstance(self.gate_period, bool) or not isinstance(self.gate_period, int):
            raise ValueError(f"gate_period must be an int or None, got {self.gate_period!r}")
        if not 1 <= self.gate_period <= MAX_GATE_PERIOD:
            raise ValueError(
                f"gate_period must lie in [1, {MAX_GATE_PERIOD}], got {self.gate_period}"
            )
        if isinstance(self.gate_offset, bool) or not isinstance(self.gate_offset, int):
            raise ValueError(f"gate_offset must be an int when gate_period is set, got "
                             f"{self.gate_offset!r}")
        if not 0 <= self.gate_offset < self.gate_period:
            raise ValueError(f"gate_offset must lie in [0, {self.gate_period - 1}], got "
                             f"{self.gate_offset}")

    def as_dict(self) -> dict[str, str]:
        """Every field as a plain string, the book's prefixed ``book.`` -- M0261's shape exactly.

        ``None`` renders "native" rather than "None" because this is the text a human reads on the
        method's page beside "126" and "131", and "the gate read natively" is what the arm is. The
        third key is derived rather than stored: "offset 65 of 131" is unreadable on its own, and
        what anyone checking an arm wants is the sentence. The digest does not depend on any of
        this -- ``registry._canon`` walks the dataclass's fields -- but the recorded row does.
        """
        native = self.gate_period is None
        out = {
            "gate_period": "native" if native else str(self.gate_period),
            "gate_offset": "native" if native else str(self.gate_offset),
            "gate_reads": "every month end" if native
            else f"every {self.gate_period} sessions, from offset {self.gate_offset}",
        }
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> SessionParams:
    if not isinstance(params, SessionParams):
        raise TypeError(f"params must be SessionParams, got {type(params).__name__}")
    return params


class SessionGateAllocator:
    """M0088's calm-raisers book, with its own 200-day gate read on a session-count grid."""

    id = "M0262"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        """454 bars: the host's 253, raised to cover a stale anchor plus its 200-bar mean.

        THE SAME VALUE AT EVERY RUNG, so no arm's scored window differs from another's -- which is
        what keeps every paired difference this method reports a difference in the gate's reading
        date alone. The worst anchor gap was measured at 130 sessions over the dev window's own
        decision sessions and ``MAX_ANCHOR_GAP`` carries 124 more. Widening to 454 does NOT move
        the dev window's first scored session, because ``dev.candidate_window`` binds on
        ``MEMBERSHIP_START`` (1996-01-02) for any lookback up to 739.
        """
        return max(CALM.lookback(_check(params).book), TREND_N + MAX_ANCHOR_GAP)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return CALM.symbols(_check(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return CALM.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return CALM.uses_members(_check(params).book)

    def _on(self, history: Mapping[str, History], data_date: date, p: SessionParams) -> bool:
        """The single thing this allocator exists to replace: the DATE the gate is read at.

        The gate itself is ``f_factor.trend_on`` in both branches -- the lab's own function, the
        same symbol, the same 200-bar average. Nothing about what the gate SAYS is re-implemented
        here. At ``gate_period = None`` the date is the data date, which is the host's own code
        path verbatim; the native rung's job is to reproduce a recorded trial, and a reproduction
        runs the host's code rather than an anchor computed to equal it.
        """
        inner = p.book.ann.base.inner
        if p.gate_period is None:
            return trend_on(history, data_date, inner)
        at = offset_anchor(history.get(inner.trend[0]), data_date, p.gate_period,
                           p.gate_offset or 0)
        return trend_on(history, at, inner)

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SessionParams) -> tuple[Target, ...]:
        """M0088's own ``_run``, line for line, with exactly the gate's DATE replaced.

        The empty-calendar guard first, because a market-aware allocator must target nothing when
        it is driven without its panel -- the contract ``test_lab_methods`` asserts for every such
        allocator. Then the gate, then M0088's public ``choose`` on M0088's own rows.
        """
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


SESSIONGATE = SessionGateAllocator()

#: M0088-C-LIVE-63's configuration, verbatim: the calm half of the live raisers on a 63-session
#: swing. Trial 289 and, to the digit, M0101-CTRL, M0107-HOST, M0122-CALM-EQ and M0261-NATIVE.
BOOK = CalmParams(X, "calm", "live", 63)

#: The period the drift job found CALENDAR-LOCKED: 126 sessions is 251.8 / 2 to within a fifth of
#: a session, so its readings drift -0.2 sessions a year and never leave their three or four
#: months. It is in this method as the control and as the bridge back to M0261's calendar grid.
LOCKED_PERIOD = 126

#: The period the drift job found calendar-free: 131 sessions drifts -10.2 sessions a year and
#: sweeps all twelve months across the window, at 1.92 readings a year against the locked grid's
#: 2.05 and M0261's half-yearly calendar grid's 2.00. The same rarity, no calendar.
FREE_PERIOD = 131

#: The grid this method runs, as (suffix, period, offset). ``None`` is the native reading. The
#: offsets are maximally separated pairs -- half a period apart, the shape of Jun/Dec against
#: Mar/Sep on a six-month grid -- plus one quarter point on the free grid.
LADDER: tuple[tuple[str, int | None, int | None], ...] = (
    ("NATIVE", None, None),
    ("LOCK-0", LOCKED_PERIOD, 0),
    ("LOCK-63", LOCKED_PERIOD, 63),
    ("FREE-0", FREE_PERIOD, 0),
    ("FREE-33", FREE_PERIOD, 33),
    ("FREE-65", FREE_PERIOD, 65),
)

_RATIONALE = {
    "NATIVE": "the zero rung: the gate read at the data date, the host's own code path, and the "
              "reproduction of M0088-C-LIVE-63's recorded row (10.62% of the owner's money, an "
              "18.71% fall, 528 trades). If this drifts, every paired difference here is void.",
    "LOCK-0": "a 126-session grid is a CALENDAR grid wearing a session label: 126 is half of the "
              "dev window's 251.8 sessions a year, so this arm's readings drift -0.2 sessions a "
              "year and land only in June, July and December. The control, and the bridge back "
              "to M0261's Jun/Dec arm. UNFUNDED prior 8.55%, -27.0%.",
    "LOCK-63": "the locked pair's other half, half a period away: reads only March, April, "
               "September and October, which is M0261's Mar/Sep arm by another name. The pair's "
               "unfunded gap is 1.86 points, to the hundredth the same as M0261's own unfunded "
               "Jun/Dec against Mar/Sep, which it measured FUNDED at 3.21. UNFUNDED 6.69%, -27.2%.",
    "FREE-0": "a 131-session grid drifts -10.2 sessions a year and sweeps all twelve calendar "
              "months across the window, at 1.92 readings a year against the locked grid's 2.05: "
              "the same rarity with the calendar taken out. UNFUNDED prior 9.11%, -19.4%.",
    "FREE-33": "the free grid's quarter point, present only so the free pair's gap can be seen to "
               "be representative or not. Never part of the headline statistic. UNFUNDED 8.67%, "
               "-20.8%.",
    "FREE-65": "the free pair's other half, half a period from FREE-0 and so the same shape as "
               "M0261's Jun/Dec against Mar/Sep. The pair's unfunded gap is 2.90 points, WIDER "
               "than the locked pair's 1.86. Expected to be the deepest faller of the six: a "
               "drifting grid can land a reading just before a slow slide and hold it. UNFUNDED "
               "6.21%, -43.4%.",
}


def _v(suffix: str, gate_period: int | None, gate_offset: int | None) -> Candidate:
    return Candidate(id=f"M0262-{suffix}", family="M0262", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SESSIONGATE,
                     params=SessionParams(BOOK, gate_period, gate_offset),
                     rationale=_RATIONALE[suffix], added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0262",
    name="Is a safety gate's slow-reading spread the calendar's fault or rarity's? The same gate "
         "read every N trading days, with the start slid across the period",
    family="market-trend-switch",
    source_kind="variation",
    source_ref=(
        "variation of M0261 (its anchored-gate overlay, its host book and its 454-bar lookback "
        "all carried, the grid's coordinate replaced); Faber (2007), A Quantitative Approach to "
        "Tactical Asset Allocation, JWM 9(4), for the long-moving-average switch itself"
    ),
    parent_id="M0261",
    hypothesis=(
        "Published 2007 (the long-moving-average switch), so nothing in the rule is a new anomaly "
        "and no fade argument applies to it; this method changes nothing about what the gate says "
        "or how often it is asked, only the COORDINATE its dates are counted on. Every figure "
        "here is the MONEY-WEIGHTED return on the owner's own monthly deposits -- what the lab "
        "prints as 'your money earned' -- except where a line says UNFUNDED, which marks the "
        "SPY-alone prior and nothing else. WHAT M0261 LEFT OPEN. M0261 measured, on "
        "M0088-C-LIVE-63's calm big dividend-raisers book at Gotrade's real fees on the owner's "
        "deposits, that two readings of the SPY-200 gate taken EXACTLY as often as each other but "
        "on different calendar months differ by 3.21 points a year of money (Jun/Dec 10.57% "
        "against Mar/Sep 7.36%), and that two once-a-year readings six months apart differ by 8.2 "
        "points of worst fall (Dec 19.2% against Jun 27.4%) -- both LARGER than the whole "
        "weekly-to-yearly interval ladder, which spans 2.21 points of money and 4.5 of fall on "
        "the same book. So past monthly the reading axis is not a speed, and two sentences fit "
        "that evidence while prescribing opposite things. (A) THE CALENDAR IS THE PROBLEM: a "
        "month-end grid is an arbitrary human convention, the dev window's two crashes sit at "
        "particular places in it, and a rule firing on a SESSION COUNT would spread far less as "
        "its start slid -- in which case several lab books that re-pick monthly or measure calm "
        "over windows ending at month ends are all standing on a grid nobody chose, and the whole "
        "lab needs auditing. (B) RARITY IS THE PROBLEM: a gate asked twice a year is a stale "
        "promise whatever grid it sits on, the spread is the irreducible variance of reading "
        "rarely, and a session grid will spread just as wide -- in which case the lesson is "
        "narrow and already known, read the gate every month, and no other book needs auditing. "
        "THE IDEA ROW'S DESIGN WAS BROKEN AND THE PRIOR CAUGHT IT BEFORE A LINE OF THE METHOD WAS "
        "WRITTEN. The row specified a 126-session period on the grounds that a session count has "
        "'no calendar anywhere in it'. That is false. The NYSE ran 248 to 254 sessions in each "
        "whole year of the dev window and averaged 251.8, so 126 sessions is half a year to "
        "within a fifth of a session: a 126-session reading drifts -0.2 sessions a year, which is "
        "to say it does not drift, and measured over 1994-2015 its offset 0 reads ONLY in June, "
        "July and December while its offset 63 reads ONLY in March, April, September and October. "
        "A 126-SESSION GRID IS A CALENDAR GRID WEARING A SESSION LABEL, and running it alone "
        "could only have produced a near-tautology. A period coprime with the year's session "
        "count does drift: 131 sessions drifts -10.2 sessions a year and sweeps all twelve "
        "calendar months, at 1.92 readings a year against 126's 2.05 and the calendar half-yearly "
        "grid's 2.00 -- the same rarity, no calendar lock. So this method runs BOTH periods and "
        "the comparison it is bought for is between a calendar-LOCKED session grid and a "
        "calendar-FREE one at matched rarity, with M0261's calendar grid as the third reference. "
        "That change is forced by an arithmetic fact about the exchange calendar, not by any "
        "return: the drift job reads no prices at all. THE UNFUNDED PRIOR, measured on the dev "
        "store in ONE sweep in ONE process by docs/backtests/2026-10-20-gate-reading-sessions.py "
        "before this file existed (SPY alone, a 200-bar average, a one-session lag, a monthly "
        "acting calendar, the reading held as taken; UNFUNDED, so plain CAGRs NOT comparable with "
        "the money-weighted figures above), and reproducing all seven numbers M0261's own prior "
        "quotes to the digit as its proof it reads the same tape: SESSION period 126 (LOCKED), "
        "126 offsets, range 5.78 points, standard deviation 1.38, mean pairwise gap 1.55, fall sd "
        "9.0; SESSION period 131 (FREE), 131 offsets, range 5.26, sd 1.31, mean pair gap 1.51, "
        "fall sd 8.1; CALENDAR half-yearly, 6 phases, range 3.73, sd 1.34, mean pair gap 1.78, "
        "fall sd 2.8; CALENDAR yearly, 12 phases, range 4.55, sd 1.32, mean pair gap 1.59, fall "
        "sd 9.1. FOUR GRIDS AT FOUR DIFFERENT COORDINATES AND THEIR STANDARD DEVIATIONS ARE 1.31, "
        "1.32, 1.34 AND 1.38 -- a span of seven hundredths of a point on figures of one and a "
        "third. The range is not the statistic to read and the sd is, because a 131-offset grid "
        "out-ranges a 6-phase grid for free: more draws spread wider whatever the mechanism. On "
        "the statistic that does not grow with the draw count, removing the calendar entirely "
        "changes nothing, so on the unfunded shadow the answer is (B) and it is not close. THE "
        "SIX ARMS all hold M0088-C-LIVE-63's book verbatim on monthly-hold-frac-gotrade and move "
        "only the date the gate is read at, strictly backwards: NATIVE (the zero rung and the "
        "reproduction), LOCK-0 (period 126 offset 0, reads Jun/Jul/Dec, unfunded 8.55% / -27.0%), "
        "LOCK-63 (period 126 offset 63, reads Mar/Apr/Sep/Oct, unfunded 6.69% / -27.2%), FREE-0 "
        "(period 131 offset 0, all twelve months, unfunded 9.11% / -19.4%), FREE-33 (period 131 "
        "offset 33, unfunded 8.67% / -20.8%) and FREE-65 (period 131 offset 65, unfunded 6.21% / "
        "-43.4%). THE HEADLINE STATISTIC IS THE MAXIMALLY SEPARATED PAIR AT EACH PERIOD AND IT IS "
        "DRAW-MATCHED BY CONSTRUCTION: LOCK-0 against LOCK-63 is two draws, FREE-0 against "
        "FREE-65 is two draws, and M0261's funded Jun/Dec against Mar/Sep was two draws; half a "
        "period apart is exactly how Jun/Dec and Mar/Sep sit on a six-month grid, so all three "
        "pairs have the same shape. FREE-33 is a third point, there only so the free pair's gap "
        "can be seen to be representative or not, and is never part of the headline. The offsets "
        "were fixed on that structural argument -- maximal separation plus one quarter point -- "
        "and written into the prior script BEFORE the period-131 grid was computed, so no offset "
        "here was chosen for how it scored. THE LOCKED PAIR IS THE BRIDGE, NOT A THROWAWAY: "
        "unfunded its gap is 1.86 points, which is to the hundredth M0261's own unfunded Jun/Dec "
        "against Mar/Sep gap of 1.86, as it should be since offset 0 reads Jun/Jul/Dec and offset "
        "63 reads Mar/Apr/Sep/Oct; M0261 measured that same calendar pair FUNDED at 3.21 points, "
        "so the locked arms give a direct same-shape handle on how much funding and stock picking "
        "amplify a date gap on this exact book -- 1.7 times, if LOCK reproduces it. THE GRID "
        "COUNTS FROM A FIXED CALENDAR EPOCH (the first NYSE session of 1990) AND NOT FROM 'THE "
        "SYMBOL'S FIRST BAR' as the idea row wrote it, because the lab hands an allocator a "
        "lookback window on one path and a full history on another, so 'the first bar' is a "
        "different bar in the two paths and the same configuration would score differently "
        "depending on which path ran it; session_index reads the published exchange calendar and "
        "no price, and sliding the epoch only relabels which offset is called zero. THE LOOKBACK "
        "IS 454 AT EVERY RUNG -- max(CALM.lookback(book), 200 + 254) -- deliberately M0261's own "
        "number so the two ladders are scored under identical arithmetic; the probe measured the "
        "worst anchor gap at 130 sessions over all 237 monthly decision sessions at all five "
        "anchored arms, with zero fallbacks and zero late anchors, so 330 bars is the true "
        "requirement and 454 carries 124 of margin; widening from the host's 253 does not move "
        "the first scored session, because dev.candidate_window binds on MEMBERSHIP_START "
        "(1996-01-02) for any lookback up to 739, and 454 is inside the 473-session smoke "
        "fixture's cap. A NEW ALLOCATOR ID is spent because PhaseParams holds gate_months and "
        "gate_phase and giving it a period field would move every recorded config digest that "
        "carries it, M0261's six rows included. THE PRE-REGISTERED PREDICTION, written before the "
        "run: (1) (B) WINS ON A REAL FUNDED BOOK TOO -- the calendar-free pair's gap |FREE-0 "
        "minus FREE-65| is at least 2.0 points a year of the owner's money, at least two thirds "
        "of M0261's 3.21, and the three free arms' standard deviation is at least 0.9 points; "
        "this is the claim the method is bought for and it is FALSIFIED by the free pair landing "
        "inside 1.0 point, which is the only outcome that would justify auditing the rest of the "
        "lab's calendar grids; (2) THE FREE GRID SPREADS AT LEAST AS WIDE AS THE LOCKED ONE, as "
        "it did unfunded (2.90 against 1.86), and a funded free pair that spreads LESS is "
        "evidence for (A) the shadow missed and must be reported as such rather than explained "
        "away; (3) THE LOCKED PAIR REPRODUCES M0261'S CALENDAR PAIR to within 1.0 point of its "
        "funded 3.21, and if it does not then the unfunded-to-funded amplification is not stable "
        "on this book and every cross-method gap in prediction 1 is softer than it reads; (4) "
        "NATIVE STILL WINS ON BOTH AXES AT ONCE, beating all five anchored arms on money and "
        "falling less deep than all five, as it did in M0261 (10.62% and 18.71%); (5) AT LEAST "
        "ONE FREE ARM FALLS DEEPER THAN 28% against NATIVE's 18.71%, and I expect FREE-65, which "
        "unfunded falls 43.4% against the locked pair's 27.0% and 27.2%, because a drifting grid "
        "can land a reading just before a slow slide and hold it where a month-end grid is at "
        "least pinned to a month boundary; (6) THE REPRODUCTION IS EXACT -- NATIVE returns "
        "M0088-C-LIVE-63's recorded row digit for digit, 10.62% of the owner's money, an 18.71% "
        "worst fall, 528 trades, gains 3.52 times losses and exposure 0.704, as M0261-NATIVE did "
        "at trial 854, and if it drifts every paired difference here is void and the run is a "
        "null. SUCCESS IS A MEASUREMENT, NOT ELIGIBILITY: prediction 1 coming true closes M0261's "
        "question narrowly -- the spread is rarity, the fix is read the gate every month, no "
        "other book needs auditing -- while prediction 1 failing would mean the lab is standing "
        "on an arbitrary human convention in a dozen places and would be the most expensive "
        "finding of the batch. Either way an arm that clears the screen is a draw from a "
        "distribution this method has measured, NOT a configuration to promote, and no "
        "test-window look is spent here under any outcome. Assumed without asking: that replacing "
        "the idea row's single 126-session period with a locked/free pair of periods is a "
        "refinement rather than a different method, because the row's own stated purpose was to "
        "take the calendar out and 126 demonstrably does not; and that 131 is the right free "
        "period because it is the nearest period to 126 that is coprime with the year's session "
        "count while holding the readings-a-year inside 4% of the calendar grid's."
    ),
    expected_failure=(
        "First and most likely: THE FREE PAIR SPREADS AS WIDE AS THE LOCKED ONE AND THE METHOD "
        "SIMPLY CONFIRMS WHAT THE SHADOW ALREADY SAID. That is a success for the prediction and a "
        "thin result for the lab -- it closes a question rather than opening a direction, and "
        "nobody should then spend another id on where a gate's dates are counted from. I am "
        "writing it down as the expected failure because 'the prior already answered it' is "
        "exactly the kind of result that tempts a write-up into overclaiming. Second, THE DEV "
        "WINDOW HOLDS EXACTLY TWO CRASHES AND BOTH WERE SLOW, so every number here is a statement "
        "about where 2000-2002 and 2007-2009 happened to sit relative to each grid. FREE-65's "
        "43.4% unfunded fall is one reading landing badly before one slide; 1987 and 2020 are "
        "what a FAST fall looks like and neither is in this window. The EXISTENCE of the spread "
        "transports; its SIZE does not. Third, THE HOST'S OWN DIVIDEND RHYTHM IS NOT BLIND TO THE "
        "CALENDAR. US ex-dates cluster on the calendar quarters, so the LOCKED arms read the gate "
        "at dates near which this book's own holdings refresh, while the FREE arms do not -- "
        "which means the locked-versus-free comparison carries a second difference besides the "
        "one it is measuring. It cuts AGAINST the free arms spreading wider, so prediction 2 "
        "coming true survives it; prediction 2 FAILING could be this and not the calendar, and "
        "the analysis must say so rather than claim (A). Fourth, THE FREE GRID IS ONLY FREE OVER "
        "A LONG WINDOW. 131 sessions drifts ten sessions a year, so across any five-year stretch "
        "a free arm still reads in roughly the same season; the calendar is removed over twenty "
        "years and merely blurred over five. A walk-forward fold is five years, so the fold "
        "record cannot separate locked from free at all and must not be read as if it could. "
        "Fifth, THE WALK-FORWARD WILL FLATTER THE SLOWEST ARMS. lab walkforward picks each fold's "
        "variant by MAR and MAR favours whichever arm trades least; the anchored arms flip the "
        "gate 7 to 14 times against the native reading's 28 on the prior, so the folds are "
        "structurally biased toward them. M0245's folds picked its slowest rung in three of four "
        "and M0260's picked a slow rung in three of four, two of which then lost. A fold majority "
        "won by an anchored arm is evidence about turnover FIRST. Sixth, SIX ARMS ON ONE BOOK IS "
        "A WIDE SEARCH AND THE LUCK GATE WILL SAY SO. The host's own recorded DSR is 0.945 at the "
        "N in force; every arm here is the same book with a different reading date, so an arm "
        "that draws a lucky offset will look eligible for exactly the reason this method exists "
        "to expose, and promoting it would be the single most on-the-nose way to fail the lesson. "
        "Seventh, THE REPRODUCTION MIGHT DRIFT: the native arm runs the host's code through a new "
        "allocator id and a new params class, and if its row does not come back digit for digit "
        "against trial 854 then something in the overlay is not the host, every paired difference "
        "is void, and the run must be reported as a null rather than patched. Eighth, as in every "
        "switch method the lab has run, interest on the cash held while the gate is off is not "
        "modelled; that is worth about 0.8 points a year before 2008 and nothing after it, and it "
        "falls on every arm here roughly equally because all six sit out a similar share of the "
        "window, so it cannot create or hide a gap between two arms."
    ),
    candidates=tuple(_v(suffix, period, offset) for suffix, period, offset in LADDER),
    seen_keys=(
        "concept:gate-reading-session-count-grid",
        "concept:calendar-locked-versus-calendar-free-grid",
        "concept:session-period-aliases-with-the-trading-year",
    ),
)
