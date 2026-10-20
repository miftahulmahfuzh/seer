"""M0261 -- Past monthly, is the safety gate's reading an INTERVAL or a DATE?

Source: variation of M0260 (whose anchored-gate machinery and whose four monthly rungs are
carried, with the host book replaced); Faber (2007), "A Quantitative Approach to Tactical Asset
Allocation", JWM 9(4), for the long-moving-average switch itself and for evaluating it at a fixed
interval rather than continuously. The switch is nineteen years old and nothing in it is a new
anomaly, so no fade argument applies to the rule. What is new is the question, and M0260 is the
reason it can be asked at all.

Every figure below is the MONEY-WEIGHTED return on the owner's own monthly deposits -- what
`lab show` prints as "your money earned" -- because these books are funded with a monthly top-up
and the curve-shape columns beside them, as `backtest/metrics.py` says outright, "are not returns
at all". SPY's figure is the SAME deposits put into SPY over the same window. No total return and
no CAGR appears anywhere below as a return, except where a line says UNFUNDED, which marks the
SPY-alone prior grid and nothing else.

WHAT M0260 LEFT OPEN, AND WHY IT COULD NOT CLOSE IT ITSELF. M0260 swept how often a book reads its
SPY 200-day gate, on M0072-Z2-RAWRANK's earnings-jump book, from weekly to yearly. Below monthly
the answer was clean: reading weekly cost 7.01 points a year and 11.69 points of worst fall, 85%
of which was the gate's reading cadence rather than the book's re-pick frequency. Above monthly it
was not clean at all:

    rung                      money   worst fall
    monthly (native)         12.33%      23.80%
    quarterly   Mar/Jun/Sep/Dec  8.78%      33.64%
    half-yearly Jun/Dec      12.10%      30.34%
    yearly      Dec           8.64%      25.64%

Twice a year beat four times a year by 3.3 points of money and 3.3 points of fall. **And the
twice-a-year grid is a STRICT SUBSET of the four-times grid**: June and December are two of the
four dates March/June/September/December already reads. Reading strictly fewer of the same dates
cannot beat reading those dates plus others on any theory where the INTERVAL is what matters. So
past monthly the axis had stopped being a speed, and M0260 could not say what it had become,
because every rung of its ladder carried exactly one phase. Its handover recorded the shape as
"the one unresolved shape of the run" and queued this method to resolve it.

THE ONE-LINE ANSWER THIS METHOD IS BUILT TO TEST: past monthly the gate's reading interval is not
a dial at all, it is a LOTTERY OVER WHICH CALENDAR MONTHS GET READ, and the prize money in that
lottery is larger than the entire interval ladder M0260 measured.

THE PRIOR GRID, measured on the dev store before a word of this file was written, by
`docs/backtests/2026-10-20-gate-reading-phase.py`: SPY ALONE, a 200-bar average, a one-session lag,
a monthly acting calendar, the reading held exactly as it was taken. **This is a FEASIBILITY TABLE
AND A PRIOR, NOT A RESULT, AND IT IS UNFUNDED** -- a weight path on raw closes with no deposits,
no fees and no stock picking, so its percentages are plain CAGRs and are NOT comparable with the
money-weighted figures above. It holds the interval fixed and moves the phase: all three phases of
a quarterly reading, all six of a half-yearly one, all twelve of a yearly one.

    interval      phase span of UNFUNDED CAGR      span of worst fall
    quarterly     6.36% .. 9.43%   (3.07 pts)      -27.2% .. -19.0%   ( 8.2 pts)
    half-yearly   6.03% .. 9.76%   (3.73 pts)      -27.2% .. -19.4%   ( 7.8 pts)
    yearly        4.47% .. 9.02%   (4.55 pts)      -51.8% .. -19.4%   (32.4 pts)
    monthly (native, the rung every book in the lab runs today): 8.19%, -19.0%

Read those three spans against M0260's whole slow ladder, which spans 3.69 points of money from
its best rung to its worst. **Holding the interval fixed and moving only the phase moves the
result by as much as, or more than, changing the interval at all.** At a yearly reading the choice
between reading the gate each November and reading it each January is worth 4.55 points a year and
32.4 points of worst fall -- on SPY alone, with no stock picking anywhere in it. The grid also
reproduces M0260's zig-zag in its own shadow: its Mar/Jun/Sep/Dec row reads 6.36% against
Jun/Dec's 8.17%, the same sign and nearly the same size as the funded book's 8.78 against 12.10.
The grid independently reproduces the lab's recorded SPY-only trials the way M0258's and M0260's
studies did: its native monthly fall of 19.0% against M0084-MONTHLY's recorded 18.89%.

And the sting is in the third column of that table rather than the first. **The BEST phase of
every interval beats the native monthly reading** -- 9.43% quarterly, 9.76% half-yearly, 9.02%
yearly, against native's 8.19% -- while the AVERAGE phase of every interval loses to it (7.52%,
7.90%, 7.06%). There is always a slower reading that looks better than monthly. There is no way to
know in advance which one, and picking it after the fact is the definition of fitting the window.

THE ANCHOR, GENERALISED. With `month_index(d) = (d.year - 1970) * 12 + (d.month - 1)`:

    anchor(h, data_date, k, phase) = the newest bar a of h with a <= data_date such that
                                       (i)  a is the last session of its calendar month, and
                                       (ii) month_index(a) % k == phase
                                     falling back to data_date when no such bar is on hand

M0260's anchor is exactly this one at `phase = k - 1`, which is why its quarterly rung reads the
calendar quarters and its yearly rung reads Decembers. `test_lab_m0261_phase.py` asserts that
equality against M0260's own frozen function on every session of the smoke tape, rather than
asserting it in prose, so this file's four M0260-phase arms are provably its rungs and not
lookalikes. Holding `k` and moving `phase` changes NOTHING about how often the gate is read and
EVERYTHING about which dates it is read on. That is the whole instrument.

**The anchor is never later than the data date**, so every anchored arm is strictly SAFER on
look-ahead than the native reading the lab already runs. Condition (i) is decidable point in time:
for a bar older than the data date it is `month(dates[j]) != month(dates[j+1])`, which reads only
bars at or before the data date; for the bar dated the data date itself it is the calendar
question `dates.next_session(d).month != d.month`, which reads the published NYSE calendar and no
price at all. A calendar read inside a lab allocator is established practice --
`m0052_turn_of_month_tilt.py`, `m0120_calendar_clock.py` and seven others do it -- and
`allocatorkit.assert_no_lookahead` perturbs BARS, not the calendar.

**The fallback never fires inside the dev window, at any phase.** Job C of the prior walked all
237 monthly decision sessions from 1996-01-03 to DEV_END at all 21 (k, phase) pairs: zero
fallbacks, zero anchors later than their data date, and at worst 526 SPY bars standing behind an
anchor. On the 473-session smoke fixture it does fire, for the slow rungs, before the fixture's
first qualifying month end, and the test module asserts its exact shape there rather than
pretending it cannot happen.

THE HOST, AND WHY IT IS NOT M0072. M0260 ran on M0072-Z2-RAWRANK and this method must not, or it
measures the same book twice. The host here is **M0088-C-LIVE-63**, the calm big dividend-raisers
book, carried verbatim: M0076's ex-date event with a raise of 25% or more, the calmer half of the
live raisers by a 63-session daily swing, F4's five-dollar and twenty-million-dollar screen, 20
slots at 5%, SPY in the empty ones, a 182-day event hold, fractional shares at Gotrade's real fees
on the owner's monthly top-ups, all behind the same bare SPY-200 gate. Its recorded dev row (trial
289) earns 10.62% a year of the owner's money against SPY's 7.19%, falls 18.71%, makes 3.52 of
gains per 1 of losses on 528 trades and reads DSR 0.945 -- so it is eligible, it is UNDER the 20%
fall bar M0072's host is not, and it is the lab's strongest kin-clean book (M0088-C-LIVE-63,
M0101-CTRL, M0107-HOST and M0122-CALM-EQ are the same book in four wrappers and return the
identical row to the digit).

**It qualifies for this axis, and that was checked in its own code before anything was
pre-registered.** The handover's constraint is that the host's event hold must be counted in
sessions rather than keyed to the calendar, because a book whose re-pick grid is itself a calendar
grid would ALIAS with the gate's reading grid and the ladder would measure two things at once.
M0197's chooser keys on `data_date.month` and cannot host this axis at all. M0088's hold is
`live_event`'s `(data_date - e).days >= hold_days` -- an INTERVAL measured from a company's own
ex-date, which lands where that company's board put it and nowhere on a month-end grid. The book
re-picks monthly at every rung of this ladder and never changes that, so there is no second axis
in the room. **One honest caveat, stated here rather than discovered later:** US dividend ex-dates
do cluster on the calendar quarters, so this book's own refresh rhythm is not perfectly blind to a
quarterly grid. That is a reason to read the quarterly arm's result with care, not a reason to
reject the host -- and the k = 12 phase pair, whose two dates are six months apart, carries no such
objection at all.

THE SIX ARMS. All six hold M0088-C-LIVE-63's book verbatim on `monthly-hold-frac-gotrade`. ONLY
the date the gate is read at moves. Each arm is here for a structural reason, decided before any
of them ran, and none was chosen for how its phase scored on the prior grid.

    arm       k     phase   months read         why this arm exists
    NATIVE    none  --      every month end     the ladder's zero rung and the reproduction of
                                                M0088-C-LIVE-63's recorded row
    Q-MJSD      3       2   Mar/Jun/Sep/Dec     M0260's quarterly rung, on a second host
    H-JD        6       5   Jun/Dec             M0260's half-yearly rung, on a second host
    H-MS        6       2   Mar/Sep             the SAME INTERVAL as H-JD, the other dates
    Y-DEC      12      11   Dec                 M0260's yearly rung, on a second host
    Y-JUN      12       5   Jun                 the SAME INTERVAL as Y-DEC, six months away

Four of the six (NATIVE, Q-MJSD, H-JD, Y-DEC) are M0260's monthly ladder, rung for rung, on a book
picked by a different signal -- which is the generalisation test the handover asked for. The other
two hold an interval fixed and move the phase, which is the interval-versus-date test M0260 could
not run. The two questions share four arms, which is why both fit inside `MAX_VARIANTS = 6`.

**H-MS is not an arbitrary second phase: it is Q-MJSD's other half.** The months 2, 5, 8, 11 split
exactly into {5, 11} = Jun/Dec and {2, 8} = Mar/Sep, so the quarterly grid is precisely the union
of the two half-yearly grids, and the quarterly arm's anchor at any moment is simply whichever of
the two half-yearly arms' anchors is NEWER. Job B of the prior proves that session by session on
all 237 scored decision sessions. So Q-MJSD is the "read both phases" arm and H-JD and H-MS are
its halves, and the three together close a triangle:

    * a FRESHER reading can only help, so an interval story predicts Q-MJSD >= max(H-JD, H-MS);
    * M0260 measured Q-MJSD < H-JD on its own host, which that story cannot produce;
    * if Q-MJSD loses to BOTH halves here, no interval story survives on either host.

**Y-JUN is the maximal phase shift at the slowest interval.** June is six months from December,
the furthest two yearly readings can be from each other, and on the unfunded prior the pair reads
7.67% / -30.8% against 6.77% / -19.4%: nearly the same money, 11.4 points apart on the fall. If
that fall gap survives funding and stock picking, "read the gate once a year" is not one rule, it
is twelve rules wearing one name.

WHY A NEW ALLOCATOR ID AND NOT M0260'S. M0260's `CadenceParams` holds `book: ZParams` and
`gate_months` and has no phase field at all. Giving it one would move every recorded config digest
in the lab that carries it, and it could not hold this host's `CalmParams` in any case. The phase
therefore lives in a new dataclass behind a new allocator id. That costs one method id, and that
is the correct price. `gate_anchor` IS imported from M0260 for the one phase the two share, purely
so that the test module can prove the generalisation agrees with the frozen original; the running
code uses this file's own `phase_anchor`, so no behaviour is inherited by accident.

HOW THE OVERLAY WORKS, AND THE ONE THING IT REPLACES. `PhaseGateAllocator` delegates `symbols`,
`holds`, `uses_members`, `prepare` and `prepare_market` to M0088's `CALM`, and runs M0088's own
public `choose` on M0088's own prepared panel. Exactly one thing differs: the DATE at which
`f_factor.trend_on` is asked. At `gate_months is None` the date is the data date, which is the
host's own code path verbatim -- the native rung's job is to REPRODUCE a recorded trial, and a
reproduction runs the host's code rather than an anchor computed to equal it. At `gate_months = k`
it is `phase_anchor(...)`: the SAME function, the same symbol, the same 200-bar average, read at
an earlier date. Nothing about what the gate SAYS is re-implemented anywhere in this file.

`choose` is called directly, as M0258 and M0260 both called their host's target builder, because
M0088 exposes no seam between its gate test and its chooser. Unlike theirs, the function reached
for here is PUBLIC (`m0088.choose`), and the alternative -- handing `CALM` a gate-free twin of its
params -- would make the recorded row a lie: `config_text` digests `PhaseParams`, which holds the
book UNMODIFIED, so the row would say `trend=SPY:200` while the allocator ran something else.

THE LOOKBACK: 454, THE SAME AT EVERY RUNG. Reading a 200-bar average AT an anchor up to twelve
months old needs `200 + gap` bars on hand. Job C measured the worst gap over every scored session
at every phase of this grid: **234 sessions**. So 434 bars is the true requirement and
`MAX_ANCHOR_GAP = 254` carries twenty sessions of margin, which is deliberately M0260's own number
so the two methods' ladders are scored under identical arithmetic:
`lookback = max(CALM.lookback(book), 200 + 254) = 454`, the same for every arm, so no rung's
scored window differs from another's.

Widening from the host's 253 does NOT move the dev window's first scored session.
`dev.candidate_window` takes `ready = MEMBERSHIP_START` (1996-01-02, because this book reads index
members) and raises it to SPY's `lookback`-th bar date; SPY's 739th dev-store bar is 1996-01-02
and its 740th is 1996-01-03, so any lookback up to 739 leaves the window opening at 1996-01-03 --
M0088-C-LIVE-63's own first scored session, unchanged. **The standing rule is "never cross 739",
not "never widen".** 454 is also inside the 473-session smoke fixture's hard cap.

THE PRE-REGISTERED PREDICTION, WRITTEN DOWN BEFORE THE RUN, WITH SIGNS AND SIZES.

    1. THE PHASE IS WORTH AT LEAST AS MUCH AS THE INTERVAL, ON A REAL BOOK. The gap between the
       two half-yearly phases, |H-JD - H-MS|, is at least 1.5 points a year of the owner's money;
       and the gap between the two yearly phases, Y-DEC against Y-JUN, is at least 5 points of
       worst fall. Both pairs read the gate exactly as often as each other, so any gap at all is
       the dates. This is the claim the method is bought for, and it is falsified by both pairs
       landing inside a point of each other.
    2. THE TURN AT MONTHLY GENERALISES. NATIVE beats all four anchored M0260-phase arms on money.
       The lab has been running the best available cadence by accident on this book too.
    3. THE ZIG-ZAG REPRODUCES RATHER THAN SCRAMBLING -- and I am contradicting the idea row that
       reserved this id, which predicted the slow rungs would scramble. It was written before
       anyone measured a phase grid. The gate's on/off path at a given (k, phase) is a property of
       SPY and the calendar ALONE: it is byte for byte the same path on every book in the lab. Two
       long-equity books behind the same path share most of their monthly return pattern, so the
       ordering should largely carry over. Concretely: H-JD beats Q-MJSD on money here, as it did
       on M0072's book (12.10 against 8.78) and in the unfunded SPY-alone shadow (8.17 against
       6.36). If that reverses on a differently-picked book, then M0260's zig-zag WAS about
       M0072's holdings after all, and prediction 1 is the only part of this method that survives.
    4. THE NESTING PARADOX SURVIVES. Q-MJSD does not beat BOTH of its own halves on money, even
       though its reading is the fresher of the two at every single moment. A quarterly reading
       losing to a strict subset of its own dates is the cleanest possible demonstration that
       freshness is not what is being paid for past monthly.
    5. AT LEAST ONE SLOW ARM FALLS DEEPER THAN 24%, against NATIVE's recorded 18.71%, and I expect
       the deepest to be a k = 12 arm. A reading taken once a year is late to both of the window's
       exits by construction.
    6. THE REPRODUCTION IS EXACT. NATIVE returns M0088-C-LIVE-63's recorded row digit for digit --
       10.62% of the owner's money, an 18.71% worst fall, 528 trades, turnover 4.78, exposure
       0.704, gains 3.52 times losses. It runs under a new config digest because the allocator id
       and the params class differ, but nothing else about it differs. If it drifts, every paired
       difference this method reports is void and the run must be read as a null.

SUCCESS IS A MEASUREMENT, NOT ELIGIBILITY. Predictions 1 and 4 coming true would retire an entire
direction: nobody should ever again spend a method id on "read the gate every N months", because
the N is not the lever and the lever that is there -- which month -- is unknowable in advance and
fits the window when chosen after the fact. Prediction 1 failing -- the two phases of an interval
landing on top of each other on a funded book -- would mean the interval IS the dial after all,
M0260's zig-zag was noise in one book, and a finer interval ladder is worth building.

THE WALK-FORWARD MUST BE READ ARM BY ARM. `lab walkforward` picks each fold's variant by MAR, and
MAR favours whichever arm trades least. The slow rungs flip the gate less -- 28 flips at the
native reading against 5 to 12 at a yearly one on the unfunded prior -- so the folds are
structurally biased toward the slowest arms. M0245's folds picked its slowest rung in three of
four and M0260's picked a slow rung in three of four, two of which then lost. A fold majority won
by a yearly arm is evidence about turnover FIRST and about the phase second.

NO TEST-WINDOW LOOK IS SPENT HERE, UNDER ANY OUTCOME. Four are spent and all four failed. `lab
test` is not invoked by this method under any result, including an arm that clears every
condition.

WHAT IS ALREADY DEAD AROUND THIS GATE, AND WHY A PHASE SWEEP IS NONE OF IT. Turning the gate OFF
(helped 22 of 22 variants whole-window, 0 of 22 after 2009). A TIME LOCK on the switch (deepens
the fall from 20% to 32%; the suppressed flips were the 2008 exit). An account-reading DRAWDOWN
BRAKE (pays 10 points a year of 2009-2015 to save 40 of 2008). M0132's LEARNED fall-sizing brake.
VIX-LEVEL confirmation. EXIT-BUFFER-ONLY, CONFIRM-N-DAYS, PARTIAL EXPOSURE, FAST RE-ENTRY. And the
PRICE BAND, measured three times and buried by M0258. Every one of those changes WHAT THE GATE
SAYS. **This method changes nothing about what the gate says. The rule is Faber's, untouched: SPY
above its 200-day average or below it. Only the DATE the book asks is moved, and moved strictly
backwards, which cannot add information and cannot look ahead.**

Pure: no clock, no randomness, no network, no file, no printing. Reads only bars and dividends
dated on or before `data_date`, plus the published NYSE calendar. `held` is read only where M0088
reads it -- to let a name keep its slot -- and the anchor lives in the calendar and the price path,
never in the book, so a deposit cannot move it.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
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

#: The slowest reading this method will accept, in months. Twelve is "one date a year", which is
#: barely a gate at all; anything slower is a different question than the one asked.
MAX_GATE_MONTHS = 12

#: The furthest behind the data date an anchor of this grid can sit, in sessions. Measured by
#: ``docs/backtests/2026-10-20-gate-reading-phase.py`` over all 237 monthly decision sessions of
#: the dev window at all 21 (k, phase) pairs of the grid: the worst case is 234 sessions. 254
#: carries twenty sessions of margin and is deliberately M0260's own number, so the two methods'
#: ladders are scored under identical arithmetic. See THE LOOKBACK in the module docstring.
MAX_ANCHOR_GAP = 254

#: The gate's window, which is ``inner.trend``'s length for every book on this chassis. Named so
#: that the lookback arithmetic reads as the sentence it is rather than as a magic number.
TREND_N = 200

#: The month names, indexed by ``month_index(d) % 12``. Display only: ``months_read`` turns a
#: (k, phase) pair into the thing a human actually checks an arm by.
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def month_index(d: date) -> int:
    """Calendar months since January 1970: the grid's condition (ii) counts on this.

    The same definition M0260 uses, repeated rather than imported so that this file's anchor can
    be read on its own. ``test_lab_m0261_phase.py`` asserts the two agree on every session of the
    smoke tape, which is a stronger guarantee than a shared import would give -- an import proves
    the names are the same object, and the test proves the arithmetic is.
    """
    return (d.year - 1970) * 12 + (d.month - 1)


def months_read(k: int, phase: int) -> str:
    """The calendar months a (k, phase) grid reads, as the names a human checks an arm by."""
    return "/".join(MONTH_NAMES[m] for m in range(12) if m % k == phase % k)


def phase_anchor(h: History | None, data_date: date, k: int, phase: int) -> date:
    """The newest bar of ``h`` on or before ``data_date`` that opens a reading on this grid.

    The newest bar ``a <= data_date`` that is the last session of its calendar month AND whose
    ``month_index(a) % k == phase``; ``data_date`` itself when no such bar is on hand. This is
    M0260's ``gate_anchor`` with its hard-wired ``phase = k - 1`` lifted into an argument, and the
    test module asserts the two agree bar for bar at that phase.

    **Never later than ``data_date``**, which makes every anchored reading strictly safer on
    look-ahead than the native one the lab already runs.

    **Point-in-time.** "Last session of its calendar month" is answered two ways, and which one
    applies depends only on the bar's position relative to the data date, never on how much
    history the caller happens to hold -- which is why the prepared path (full history) and the
    single-window path agree bar for bar, and why the kit's lookback cut agrees too. For a bar
    older than the data date it is ``month(dates[j]) != month(dates[j + 1])``, and ``dates[j + 1]``
    is itself on or before the data date. For the bar dated the data date it is the calendar
    question ``dates.next_session(d).month != d.month``, which reads the published NYSE calendar
    and no price at all -- established practice in a lab allocator, and untouched by
    ``allocatorkit.assert_no_lookahead``, which perturbs bars.
    """
    if h is None:
        return data_date
    i = h.index_of(data_date)
    if i is None:
        return data_date
    want = phase % k
    for j in range(i, -1, -1):
        a = h.dates[j].item()
        if month_index(a) % k != want:
            continue
        nxt = h.dates[j + 1].item() if j < i else dates.next_session(a)
        if (nxt.year, nxt.month) != (a.year, a.month):
            return a
    return data_date


@dataclass(frozen=True, slots=True)
class PhaseParams:
    """``book`` is M0088-C-LIVE-63's book, carried whole; the rest is WHEN its gate is read.

    ``gate_months = None`` is the native reading -- the gate read at the data date, exactly as
    every book in the lab reads it -- and is legal here because the ladder needs a zero rung that
    runs through the same allocator id as its anchored ones. ``gate_phase`` must be absent exactly
    when ``gate_months`` is, and otherwise names which residue class of months the grid reads:
    M0260's grids are ``gate_phase = gate_months - 1``, and every other value is a phase shift of
    the same interval.
    """

    book: CalmParams
    gate_months: int | None = None
    gate_phase: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.book, CalmParams):
            raise TypeError(f"book must be CalmParams, got {type(self.book).__name__}")
        if self.book.ann.base.inner.trend is None:
            raise ValueError("book must carry a trend symbol and length for the anchor to read")
        if self.gate_months is None:
            if self.gate_phase is not None:
                raise ValueError("gate_phase must be None when the gate is read natively")
            return
        if isinstance(self.gate_months, bool) or not isinstance(self.gate_months, int):
            raise ValueError(f"gate_months must be an int or None, got {self.gate_months!r}")
        if not 1 <= self.gate_months <= MAX_GATE_MONTHS:
            raise ValueError(
                f"gate_months must lie in [1, {MAX_GATE_MONTHS}], got {self.gate_months}"
            )
        if isinstance(self.gate_phase, bool) or not isinstance(self.gate_phase, int):
            raise ValueError(f"gate_phase must be an int when gate_months is set, got "
                             f"{self.gate_phase!r}")
        if not 0 <= self.gate_phase < self.gate_months:
            raise ValueError(f"gate_phase must lie in [0, {self.gate_months - 1}], got "
                             f"{self.gate_phase}")

    def as_dict(self) -> dict[str, str]:
        """Every field as a plain string, the book's prefixed ``book.`` -- M0260's shape exactly.

        ``None`` renders "native" rather than "None" because this is the text a human reads on the
        method's page beside "3" and "12", and "the gate read natively" is what the arm is. The
        third key is derived rather than stored: the months are what anyone checking an arm
        actually wants to see, and "phase 2" alone is unreadable. The digest does not depend on
        any of this -- ``registry._canon`` walks the dataclass's fields -- but the recorded row
        does, and a row that said "None" would read as a missing value rather than as a rung.
        """
        native = self.gate_months is None
        out = {
            "gate_months": "native" if native else str(self.gate_months),
            "gate_phase": "native" if native else str(self.gate_phase),
            "gate_reads": "every month end" if native
            else months_read(self.gate_months, self.gate_phase or 0),
        }
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> PhaseParams:
    if not isinstance(params, PhaseParams):
        raise TypeError(f"params must be PhaseParams, got {type(params).__name__}")
    return params


class PhaseGateAllocator:
    """M0088's calm-raisers book, with its own 200-day gate read on a (k, phase) month-end grid."""

    id = "M0261"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        """454 bars: the host's 253, raised to cover a twelve-month anchor plus its 200-bar mean.

        THE SAME VALUE AT EVERY RUNG, so no arm's scored window differs from another's -- which is
        what keeps every paired difference this method reports a difference in the gate's reading
        date alone. The worst anchor gap was measured at 234 sessions over the dev window's own
        decision sessions and ``MAX_ANCHOR_GAP`` carries twenty more. Widening to 454 does NOT
        move the dev window's first scored session, because ``dev.candidate_window`` binds on
        ``MEMBERSHIP_START`` (1996-01-02) for any lookback up to 739.
        """
        return max(CALM.lookback(_check(params).book), TREND_N + MAX_ANCHOR_GAP)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return CALM.symbols(_check(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return CALM.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return CALM.uses_members(_check(params).book)

    def _on(self, history: Mapping[str, History], data_date: date, p: PhaseParams) -> bool:
        """The single thing this allocator exists to replace: the DATE the gate is read at.

        The gate itself is ``f_factor.trend_on`` in both branches -- the lab's own function, the
        same symbol, the same 200-bar average. Nothing about what the gate SAYS is re-implemented
        here. At ``gate_months = None`` the date is the data date, which is the host's own code
        path verbatim; the native rung's job is to reproduce a recorded trial, and a reproduction
        runs the host's code rather than an anchor computed to equal it.
        """
        inner = p.book.ann.base.inner
        if p.gate_months is None:
            return trend_on(history, data_date, inner)
        at = phase_anchor(history.get(inner.trend[0]), data_date, p.gate_months,
                          p.gate_phase or 0)
        return trend_on(history, at, inner)

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: PhaseParams) -> tuple[Target, ...]:
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


PHASEGATE = PhaseGateAllocator()

#: M0088-C-LIVE-63's configuration, verbatim: the calm half of the live raisers on a 63-session
#: swing. Trial 289 and, to the digit, M0101-CTRL, M0107-HOST and M0122-CALM-EQ.
BOOK = CalmParams(X, "calm", "live", 63)

#: The grid this method runs, as (k, phase) pairs. ``None`` is the native reading.
LADDER: tuple[tuple[int | None, int | None], ...] = (
    (None, None), (3, 2), (6, 5), (6, 2), (12, 11), (12, 5),
)


def _v(suffix: str, gate_months: int | None, gate_phase: int | None, rationale: str) -> Candidate:
    return Candidate(id=f"M0261-{suffix}", family="M0261", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=PHASEGATE,
                     params=PhaseParams(BOOK, gate_months, gate_phase),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0261",
    name="Past monthly, is a safety gate's reading speed real or is it just which month you "
         "happen to look? The same reading interval at different calendar dates, on a second book",
    family="market-trend-switch",
    source_kind="variation",
    source_ref=(
        "variation of M0260 (its anchored-gate machinery and its four monthly rungs carried, the "
        "host book replaced by M0088-C-LIVE-63's); Faber (2007), A Quantitative Approach to "
        "Tactical Asset Allocation, JWM 9(4), for the long-moving-average switch and for "
        "evaluating it at a fixed interval rather than continuously"
    ),
    parent_id="M0260",
    hypothesis=(
        "Published 2007 (the long-moving-average switch), so nothing in the rule is a new anomaly "
        "and no fade argument applies to it; what is new is the question. Every figure here is "
        "the MONEY-WEIGHTED return on the owner's own monthly deposits -- what the lab prints as "
        "'your money earned' -- except where a line says UNFUNDED, which marks the SPY-alone "
        "prior grid and nothing else. WHAT M0260 LEFT OPEN. M0260 swept how often a book reads "
        "its SPY 200-day gate, on M0072-Z2-RAWRANK's earnings-jump book. Below monthly the answer "
        "was clean: reading weekly cost 7.01 points a year and 11.69 points of worst fall, 85% of "
        "it the gate's reading cadence rather than the book's re-pick frequency. Above monthly it "
        "was not: monthly 12.33% and a 23.80% fall, quarterly (Mar/Jun/Sep/Dec) 8.78% and 33.64%, "
        "half-yearly (Jun/Dec) 12.10% and 30.34%, yearly (Dec) 8.64% and 25.64%. Twice a year "
        "beat four times a year by 3.3 points of money and 3.3 points of fall -- AND THE "
        "TWICE-A-YEAR GRID IS A STRICT SUBSET OF THE FOUR-TIMES GRID. Reading strictly fewer of "
        "the same dates cannot beat reading those dates plus others on any theory where the "
        "INTERVAL is what matters, so past monthly the axis had stopped being a speed, and M0260 "
        "could not say what it had become because every rung of its ladder carried exactly one "
        "phase. THE PRIOR GRID, measured on the dev store before a word of this file was written "
        "by docs/backtests/2026-10-20-gate-reading-phase.py (SPY ALONE, a 200-bar average, a "
        "one-session lag, a monthly acting calendar, the reading held as taken; UNFUNDED, so "
        "plain CAGRs that are NOT comparable with the money-weighted figures above), holds the "
        "interval fixed and moves the phase across all three phases of a quarterly reading, all "
        "six of a half-yearly one and all twelve of a yearly one: quarterly spans 6.36% to 9.43% "
        "(3.07 points) and -27.2% to -19.0%; half-yearly spans 6.03% to 9.76% (3.73 points) and "
        "-27.2% to -19.4%; yearly spans 4.47% to 9.02% (4.55 points) and -51.8% to -19.4%, a "
        "32.4-point span of worst fall; the native monthly reading every book in the lab runs "
        "today is 8.19% and -19.0%. M0260's whole slow ladder spans 3.69 points of money from its "
        "best rung to its worst, so HOLDING THE INTERVAL FIXED AND MOVING ONLY THE PHASE MOVES "
        "THE RESULT BY AS MUCH AS, OR MORE THAN, CHANGING THE INTERVAL AT ALL. The grid "
        "reproduces M0260's zig-zag in its own shadow (Mar/Jun/Sep/Dec 6.36% against Jun/Dec "
        "8.17%, the same sign and nearly the same size as the funded 8.78 against 12.10) and "
        "reproduces the lab's recorded SPY-only trials (native monthly fall 19.0% against "
        "M0084-MONTHLY's recorded 18.89%). The sting is that the BEST phase of every interval "
        "beats native monthly -- 9.43%, 9.76%, 9.02% against 8.19% -- while the AVERAGE phase of "
        "every interval loses to it (7.52%, 7.90%, 7.06%): there is always a slower reading that "
        "looks better than monthly, there is no way to know in advance which, and picking it "
        "after the fact is the definition of fitting the window. THE ANCHOR, with month_index(d) "
        "= (d.year - 1970) * 12 + (d.month - 1): the newest bar a <= data_date that is the last "
        "session of its calendar month and has month_index(a) % k == phase, falling back to "
        "data_date when none is on hand. M0260's anchor is this one at phase = k - 1, and the "
        "test module asserts that equality against M0260's own frozen function on every session "
        "of the smoke tape. It is never later than data_date, so every anchored arm is strictly "
        "SAFER on look-ahead than the native reading, and the fallback never fires inside the dev "
        "window: the prior walked all 237 monthly decision sessions from 1996-01-03 at all 21 "
        "(k, phase) pairs and found zero fallbacks, zero late anchors and at worst 526 SPY bars "
        "behind an anchor. THE HOST IS M0088-C-LIVE-63, not M0072, or the method would measure "
        "the same book twice: the calm big dividend-raisers book carried verbatim -- M0076's "
        "ex-date event with a raise of 25% or more, the calmer half of the live raisers by a "
        "63-session daily swing, F4's five-dollar and twenty-million screen, 20 slots at 5%, SPY "
        "in the empty ones, a 182-day event hold, fractional at Gotrade's real fees on the "
        "owner's monthly top-ups, behind the same bare SPY-200 gate. Its recorded dev row (trial "
        "289) earns 10.62% a year of the owner's money against SPY's 7.19%, falls 18.71%, makes "
        "3.52 of gains per 1 of losses on 528 trades and reads DSR 0.945, so it is eligible, it "
        "is UNDER the 20% fall bar M0072's host is not, and it is the lab's strongest kin-clean "
        "book (M0088-C-LIVE-63, M0101-CTRL, M0107-HOST and M0122-CALM-EQ are one book in four "
        "wrappers, identical to the digit). IT QUALIFIES FOR THIS AXIS and that was checked in "
        "its own code first: the handover's constraint is that the host's event hold must be an "
        "interval rather than a calendar grid, because a book whose re-pick grid IS a calendar "
        "grid would alias with the gate's reading grid; M0197's chooser keys on data_date.month "
        "and cannot host this axis at all, while M0088's hold is live_event's (data_date - e).days "
        ">= hold_days, an interval measured from a company's own ex-date, and the book re-picks "
        "monthly at every rung and never changes that. One honest caveat: US ex-dates do cluster "
        "on the calendar quarters, so this book's refresh rhythm is not perfectly blind to a "
        "quarterly grid -- a reason to read the quarterly arm with care, and no objection at all "
        "to the k = 12 pair, whose two dates are six months apart. THE SIX ARMS all hold that book "
        "verbatim on monthly-hold-frac-gotrade and move only the date the gate is read at: NATIVE "
        "(every month end: the zero rung and the reproduction), Q-MJSD (k=3 phase 2, "
        "Mar/Jun/Sep/Dec: M0260's quarterly rung on a second host), H-JD (k=6 phase 5, Jun/Dec: "
        "M0260's half-yearly rung), H-MS (k=6 phase 2, Mar/Sep: the SAME interval as H-JD, the "
        "other dates), Y-DEC (k=12 phase 11, Dec: M0260's yearly rung) and Y-JUN (k=12 phase 5, "
        "Jun: the same interval as Y-DEC, six months away). Four of the six are M0260's ladder "
        "rung for rung on a differently-picked book, which is the generalisation test; the other "
        "two hold an interval fixed and move the phase, which is the test M0260 could not run; "
        "the two questions share four arms, which is how both fit inside MAX_VARIANTS = 6. H-MS "
        "IS NOT AN ARBITRARY SECOND PHASE, IT IS Q-MJSD'S OTHER HALF: the months 2, 5, 8, 11 "
        "split exactly into {5, 11} = Jun/Dec and {2, 8} = Mar/Sep, so the quarterly grid is "
        "precisely the union of the two half-yearly grids and the quarterly arm's anchor is "
        "always whichever half-yearly anchor is NEWER -- proved session by session on all 237 "
        "scored decision sessions by the prior's Job B. So an interval story predicts Q-MJSD >= "
        "max(H-JD, H-MS), M0260 measured Q-MJSD < H-JD on its own host, and a Q-MJSD that loses "
        "to BOTH halves here leaves no interval story alive on either host. Y-JUN is the maximal "
        "phase shift at the slowest interval, six months from December, and on the unfunded prior "
        "the pair reads 7.67% / -30.8% against 6.77% / -19.4%: nearly the same money, 11.4 points "
        "apart on the fall. THE LOOKBACK IS 454 AT EVERY RUNG -- max(CALM.lookback(book), 200 + "
        "254) -- because reading a 200-bar average at an anchor up to twelve months old needs 200 "
        "+ gap bars and the worst gap over every scored session at every phase was measured at "
        "234; 254 is deliberately M0260's own margin so the two ladders are scored under "
        "identical arithmetic. Widening from the host's 253 does not move the first scored "
        "session, because dev.candidate_window binds on MEMBERSHIP_START (1996-01-02) for any "
        "lookback up to 739; the standing rule is 'never cross 739', not 'never widen', and 454 "
        "is also inside the 473-session smoke fixture's cap. THE PRE-REGISTERED PREDICTION, "
        "written before the run: (1) THE PHASE IS WORTH AT LEAST AS MUCH AS THE INTERVAL ON A "
        "REAL BOOK -- |H-JD minus H-MS| is at least 1.5 points a year of the owner's money, and "
        "Y-DEC against Y-JUN is at least 5 points of worst fall; both pairs read the gate exactly "
        "as often as each other, so any gap at all is the dates, and the claim is falsified by "
        "both pairs landing inside a point of each other; (2) THE TURN AT MONTHLY GENERALISES -- "
        "NATIVE beats all four anchored M0260-phase arms on money; (3) THE ZIG-ZAG REPRODUCES "
        "RATHER THAN SCRAMBLING, and this CONTRADICTS the idea row that reserved this id, which "
        "predicted a scramble and was written before anyone measured a phase grid: the gate's "
        "on/off path at a given (k, phase) is a property of SPY and the calendar ALONE and is "
        "byte for byte the same path on every book in the lab, so two long-equity books behind "
        "the same path share most of their monthly return pattern and the ordering should largely "
        "carry over -- concretely, H-JD beats Q-MJSD on money here as it did on M0072's book "
        "(12.10 against 8.78) and in the unfunded shadow (8.17 against 6.36), and a reversal "
        "would mean M0260's zig-zag was about M0072's holdings after all and prediction 1 is all "
        "that survives; (4) THE NESTING PARADOX SURVIVES -- Q-MJSD does not beat BOTH of its own "
        "halves on money even though its reading is the fresher of the two at every moment, which "
        "is the cleanest possible demonstration that freshness is not what is being paid for past "
        "monthly; (5) AT LEAST ONE SLOW ARM FALLS DEEPER THAN 24% against NATIVE's recorded "
        "18.71%, and I expect the deepest to be a k = 12 arm; (6) THE REPRODUCTION IS EXACT -- "
        "NATIVE returns M0088-C-LIVE-63's recorded row digit for digit, 10.62% of the owner's "
        "money, an 18.71% worst fall, 528 trades, turnover 4.78, exposure 0.704 and gains 3.52 "
        "times losses, and if it drifts then every paired difference here is void and the run is "
        "a null. SUCCESS IS A MEASUREMENT, NOT ELIGIBILITY: predictions 1 and 4 coming true would "
        "retire an entire direction, because nobody should then ever again spend a method id on "
        "'read the gate every N months' when the N is not the lever and the lever that is there "
        "-- which month -- is unknowable in advance and fits the window when chosen after the "
        "fact. Assumed without asking: that M0088-C-LIVE-63 is the right second host, because it "
        "is the lab's strongest kin-clean dev-eligible book, its signal (a dividend raise) shares "
        "nothing with M0072's (an earnings-day price jump), and its hold is an interval rather "
        "than a calendar grid; and that the two phase arms should be chosen structurally (the "
        "complement half, and the maximal shift) rather than for how their phases scored on the "
        "prior grid, so that the method cannot be accused of picking a phase to win."
    ),
    expected_failure=(
        "First and most likely: THE TWO PHASES OF AN INTERVAL LAND ON TOP OF EACH OTHER once the "
        "book is a funded, fee-paying stock book rather than SPY alone. The prior's phase spreads "
        "are measured on a weight path with no picking in it, and a book that is only 70% invested "
        "and holds twenty names may wash the dates out. That would be a clean null, it would mean "
        "the interval IS the dial after all and M0260's zig-zag was noise in one book, and it "
        "would be worth the id because a finer interval ladder would then be worth building -- "
        "which on the current evidence it is not. Second, THE DEV WINDOW HOLDS EXACTLY TWO "
        "CRASHES AND BOTH WERE SLOW, so any phase result is a statement about where 2000-2002 and "
        "2007-2009 happened to sit in the calendar. A phase that reads the gate each November "
        "looks catastrophic on this tape (-51.8% on the prior) largely because of where the 2008 "
        "exit fell relative to each November; 1987 and 2020 are what a FAST fall looks like and "
        "neither is in this window. That is not a flaw in the finding -- it is the finding: if a "
        "two-crash window can move a yearly reading by 32 points of worst fall depending on which "
        "month it is taken, then no yearly reading is a rule anyone can trust. But it does mean "
        "the SIZE of the phase effect is not transportable, only its existence. Third, THE HOST'S "
        "OWN DIVIDEND RHYTHM IS NOT PERFECTLY BLIND TO A QUARTERLY GRID. US ex-dates cluster on "
        "the calendar quarters, so Q-MJSD and H-MS and H-JD all read the gate at dates near which "
        "this book's own holdings refresh. The k = 12 pair is immune (six months apart, one "
        "reading a year) and is therefore the arm pair the first prediction should be judged on "
        "if the two disagree. Fourth, THE WALK-FORWARD WILL FLATTER THE SLOWEST ARMS. lab "
        "walkforward picks each fold's variant by MAR and MAR favours whichever arm trades least; "
        "the slow rungs flip the gate less (28 flips at the native reading against 5 to 12 at a "
        "yearly one on the prior), so the folds are structurally biased toward Y-DEC and Y-JUN. "
        "M0245's folds picked its slowest rung in three of four and M0260's picked a slow rung in "
        "three of four, two of which then lost. A fold majority won by a yearly arm is evidence "
        "about turnover FIRST. Fifth, SIX ARMS ON ONE BOOK IS A WIDE SEARCH AND THE LUCK GATE "
        "WILL SAY SO. The host's own recorded DSR is 0.945 at the N in force; every arm here is "
        "the same book with a different reading date, so an arm that happens to draw a lucky "
        "phase will look eligible for exactly the reason this method exists to expose. Any arm "
        "that clears the screen must be read as a draw from a distribution whose spread this "
        "method has measured, and NOT as a configuration to promote -- promoting the best phase "
        "of a slow reading would be the single most on-the-nose way to fail the lesson. Sixth, "
        "THE REPRODUCTION MIGHT DRIFT. The native arm runs the host's code through a new allocator "
        "id and a new params class; if its row does not come back digit for digit against trial "
        "289 then something in the overlay is not the host, every paired difference here is void, "
        "and the run must be reported as a null rather than patched. Seventh, as in every switch "
        "method the lab has run: interest on the cash held while the gate is off is not modelled, "
        "which flatters SPY and penalises every gated arm equally -- and it penalises the arms "
        "that sit out most, so each gap this method reports between a mostly-invested phase and a "
        "mostly-out one is a LOWER bound. The paired differences within one interval are "
        "unaffected, because two phases of one interval sit out for similar fractions of the "
        "tape. Eighth, this method cannot and does not settle what the RIGHT reading date is, "
        "only that the date matters; any arm that wins here is winning on this window's two "
        "crashes and nothing in the dev store can say whether it would win on a third."
    ),
    candidates=(
        _v("NATIVE", None, None,
           "The dose-response ladder's zero rung and the paired reproduction: the calm big "
           "dividend-raisers book behind its own unchanged 200-day switch, read at the data date "
           "as every book in the lab reads it, which on a monthly book is the one-month grid"),
        _v("Q-MJSD", 3, 2,
           "Second rung of the dose-response ladder: the same switch read once a calendar quarter "
           "-- March, June, September, December -- while the book goes on re-picking monthly, and "
           "the rung M0260 measured on its own host"),
        _v("H-JD", 6, 5,
           "Third rung of the dose-response ladder: the same switch read half-yearly at the June "
           "and December month ends, the rung that beat the quarterly one on M0260's host despite "
           "reading a strict subset of its dates"),
        _v("H-MS", 6, 2,
           "The dose-response ladder's half-yearly rung read at the OTHER dates -- March and "
           "September -- so the reading interval is identical to the June/December rung and only "
           "the calendar dates differ; together the two halves make up the quarterly rung exactly"),
        _v("Y-DEC", 12, 11,
           "Top rung of the dose-response ladder: the same switch read once a year at the December "
           "month end -- barely a gate at all, and the rung M0260 measured on its own host"),
        _v("Y-JUN", 12, 5,
           "The dose-response ladder's yearly rung read at the OTHER end of the calendar -- each "
           "June month end, six months from December, the furthest two once-a-year readings can "
           "sit from each other with the reading interval held identical"),
    ),
    seen_keys=(
        "concept:gate-reading-phase-ladder",
        "concept:same-interval-different-calendar-dates",
        "concept:nested-gate-grid-paradox",
    ),
)
