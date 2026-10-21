"""M0271 -- Is the safety switch's famous premium anything but its time in cash? A delay ladder.

Source: variation of M0270, which measured for the first time what a point of the account left
out of the market is worth, era by era, on a deliberately opinion-free 50-name book. Insight 532
is the hypothesis this method exists to test; insight 463 is the figure it is aimed at; insights
516 and 529 are the two independent results that already point the same way; insight 533 is the
warning that a slope read from two points is not a measurement.

-------------------------------------------------------------------------------------------------
WHAT THIS IS ABOUT

The lab holds one number it treats as a constant of the shared SPY 200-day switch: a premium of
**3.6 points a year since 2009**, swept across all 824 recorded trials, barely moving from book to
book, and most of the typical post-2009 shortfall (insight 463). It has always read as a stubborn
property of the switch -- something a cleverer switch could reduce.

M0270 has just priced the other half of that arithmetic directly, on the dev store, in exactly
that era: on the opinion-free 50-name equal-weight book, one point of the account held in cash
cost **0.1732 points a year** of de-funded lead over 2009-2015, read off six evenly spaced rungs
whose consecutive local slopes were 0.0343-to-0.0414-shaped straight (whole-window) and whose era
column was the straightest in the ladder. Divide: 3.6 / 0.1732 = **20.8 points of exposure**.

Measured on this store, on monthly decision dates, over 2009-2015, the plain SPY 200-day gate is
out of the market on **15 of 82 decisions, 18.29%** -- about 18 points of a 98.6%-invested book.
18.0 x 0.1732 = **3.12 points a year**. The gate's famous premium and its time in cash agree to
within half a point before any backtest is run.

So the hypothesis is that THE SWITCH'S COST IS NOT A PROPERTY OF THE SWITCH. It is how long the
switch stays out, multiplied by what being out was worth in the only era anyone measures -- and
there is no judgement in it at all. If that is right, every attempt this lab has made to tune the
switch (M0245's confirmation, M0258's price band, M0260's cadence, M0261's phase, M0262's session
grid) was adjusting something that does not set the price, and the only dial that does is how long
the rule stays out.

TWO INDEPENDENT RESULTS ALREADY POINT THE SAME WAY, which is why this is worth a method id rather
than a shrug. Insight 516: twenty thousand uninformed sticky switches drawn at the real gate's own
transition rate put the real gate at the **38th percentile of its own imitators** over 2009-2015
(+3.47 against the average placebo's +3.87) -- worse than a coin flip with the same habits.
Insight 529: the lab's books cluster by their GATE and not by their ideas (gated x gated +0.633
against ungated x ungated +0.064), and projecting the gate-alone book out collapses the lab-wide
median resemblance from 0.288 to 0.070. A component that explains most of a shortfall, most of the
cross-book correlation, and loses to its own placebo is a component that may be doing nothing but
holding cash.

-------------------------------------------------------------------------------------------------
THE DESIGN: MOVE TIME-IN-CASH DELIBERATELY, HOLD THE SIGNAL FIXED

Reading the gate's price off the recorded trials cannot settle it, because every gated book in
this lab sits behind the SAME rule read on the SAME monthly dates: four of the five live books go
to cash on the identical 28.3% of their decision days. Exposure is not a lever there; it is a
constant with noise around it. So this method makes exposure the independent variable.

**One book, one dial.** The base book is M0266's allocator -- subclassed from M0270's own subclass
so all three cannot drift apart -- the 50 most-traded index members at equal weight, band 0, no
stock picking, no brake, no memory, at full scale. On top of it sits the lab's shared gate,
``f_factor.trend_on`` with ``("SPY", 200)``, unmodified: nothing about what the gate SAYS is
re-implemented here. The only thing that moves between arms is a **re-entry delay**: the book
stays in cash until the gate has been continuously on for at least ``delay`` sessions.

    arm    delay            what it is
    OFF    gate off         no opinion: always invested. The reference, and M0270-S100's twin
    D000   0 sessions       the lab's shared gate, plain and unmodified
    D006   6 sessions       back in a week and a bit later
    D016   16 sessions      back in three weeks later
    D030   30 sessions      back in six weeks later
    D042   42 sessions      back in two months later

THE RUNGS ARE EVENLY SPACED IN THE X AXIS, WHICH IS CASH, NOT IN THE DIAL. The delays were chosen
from the gate's OWN CALENDAR, read off SPY's bars before anything ran and reading no return at
all: over 2009-2015 they put the book out of the market on 18.29, 23.17, 28.05, 34.15 and 39.02
percent of monthly decisions, five steps of 4.9, 4.9, 6.1 and 4.9 points. Even spacing in the
measured x is what M0270's note asks for -- uneven rungs invite a reader to see curvature that is
really an artefact of where the rungs were put -- and spacing the DIAL evenly instead would have
bunched three rungs into the first five points of cash. This is not a calibration in M0266's
sense: nothing is aimed at an exposure recorded on another store, and the realised exposures are
read afterwards rather than targeted. A delay measured in SESSIONS rather than in months is
deliberate too -- the gate clears on a daily date, the book decides on a monthly one, so a session
delay binds on a graded share of episodes and the x axis comes out smooth rather than in steps.

THE LADDER STOPS AT 42 SESSIONS BECAUSE THE SMOKE FIXTURE STOPS IT THERE, and the reason is
recorded here rather than hidden. ``tests/test_lab_methods.py`` drives every allocator over six
probe sessions of a 473-bar synthetic market and refuses an allocator that targets nothing at all
of them; the longest unbroken run of gate-on sessions at any probe date in that fixture is 55, and
the earliest probe has only 251 bars behind it against the 200 the average needs. A delay past
about 48 sessions therefore reads as a dead allocator to a test whose job is to catch dead
allocators, and shrinking that frozen fixture to fit one experiment is the wrong trade. The cost
is a 21-point lever instead of a 36-point one, and it is smaller than it looks: the question is
what happens between the no-gate arm at 1.4 points of cash and the plain gate at 19.5, so a ladder
anchored CLOSE to the gate's own operating point extrapolates back over that gap better than one
stretched far past it.

**The delay moves time in cash without touching a single exit.** Every arm leaves the market on
exactly the same days for exactly the same reason. They differ only in how long they wait before
coming back. That is what makes the ladder a dose-response experiment on exposure rather than a
new timing rule: nobody is claiming a delay is a good idea, and no arm here is a candidate.

**THE NO-OPINION ARM IS REGISTERED (insight 523).** ``OFF`` is the same book never stepping aside
and never switching, so the cost of the HABIT is recoverable rather than cancelling out across a
pair. Twenty-two of the lab's twenty-eight reversed pairs cannot be priced because nobody
registered theirs; this one can.

-------------------------------------------------------------------------------------------------
THE DELIVERABLE, DEFINED NOW SO IT CANNOT BE CHOSEN AFTERWARDS

Work in points of CASH (100 minus realised average exposure) against DE-FUNDED LEAD over SPY TR in
points a year, per era, with 2009-2015 the era the claim is about.

 1. **Fit the straight line through the five delay rungs** (D000..D042), which span roughly 19 to
    40 points of cash -- a 21-point lever on five evenly spaced points, which is what insight 533
    demands after M0266 read an eight-fold store gap off two. Its slope ``s`` is the price of a
    point of EPISODIC cash at the gate's own boundary.
 2. **Extrapolate that line back to the OFF arm's own cash level** (about 1.4 points) and call the
    prediction ``P``. Call the OFF arm's measured lead ``A``. The extrapolation reaches 18 points
    beyond the nearest rung, which is the single largest weakness in this design and is stated
    here rather than discovered later; the residual against M0270's independently measured 0.1732
    (item 3) does not depend on it, which is why both are reported.
    * ``P ~ A`` means the gate's own 18 points of cash are priced exactly like the delay's cash:
      the switch's decision carries no information and the hypothesis stands.
    * ``A < P`` means the gate's cash was CHEAPER than the delay's -- it sat out worse months than
      it waited through, so the switch's exit decision does carry information, and three separate
      lines of evidence this week were misread.
    * ``A > P`` means the gate was out at better moments than the delay was, which would be
      anti-skill and would be reported as such.
 3. **The headline residual.** ``R = (A - lead(D000)) - 0.1732 x (cash(D000) - cash(OFF))``: the
    gate's measured cost minus what its time in cash alone should cost at M0270's measured era
    price, on the identical chassis, store and era. The hypothesis predicts ``R = 0``.
 4. **The noise band is internal and is not borrowed.** It is the root-mean-square residual of the
    five delay rungs about their own fitted line -- the only honest measure of path jitter on this
    chassis, because every rung is the same book on the same tape with one dial moved. M0270's
    rung-pair errors on this chassis ran 0.000 to 0.034 points a year, so a band near a twentieth
    of a point is expected; the lab-wide 3.1 points a year of year-to-year noise is a different
    quantity about different books and is NOT the yardstick here.

PRE-REGISTERED THRESHOLDS. ``|R| <= 0.5`` points a year CONFIRMS the hypothesis: the switch is a
cash dial with a story attached. ``|R| >= 1.0`` points a year, with a rung scatter under 0.2,
FALSIFIES it and says the switch has real timing skill worth about ``R`` a year. Between 0.5 and
1.0 the answer is "mostly cash, with a residual too small to tune against", and the method says so
rather than rounding to whichever end is more interesting.

-------------------------------------------------------------------------------------------------
WHAT IS PREDICTED, IN NUMBERS, BEFORE ANY RESULT

The gate's own calendar is read off SPY's bars on this store and costs no backtest, so the x axis
is known in advance. Monthly decisions out of the market, and the implied exposure at a
98.57%-invested base book:

    arm    2009-2015: out of 82 decisions, implied exposure | whole window: out of 238, implied
    OFF       0  ( 0.00%)   98.6%                            |    0  ( 0.00%)   98.6%
    D000     15  (18.29%)   80.5%                            |   63  (26.47%)   72.5%
    D006     19  (23.17%)   75.7%                            |   83  (34.87%)   64.2%
    D016     23  (28.05%)   70.9%                            |   93  (39.08%)   60.0%
    D030     28  (34.15%)   64.9%                            |  105  (44.12%)   55.1%
    D042     32  (39.02%)   60.1%                            |  113  (47.48%)   51.8%

The implied exposure is the out-share applied to the base book's own 98.57%, so it is a PREDICTION
and not a target. The claim is about 2009-2015, so the fit, the extrapolation and the residual all
use the 2009-2015 column, with exposure re-measured over that era's sessions from the run's own
snapshots rather than taken from the whole-window average a trial records.

 1. REALISED EXPOSURE IS STRICTLY DECREASING IN DELAY on both windows and lands within 2 points of
    the implied columns above -- 98.6, 80.5, 75.7, 70.9, 64.9, 60.1 over 2009-2015, and 98.6,
    72.5, 64.2, 60.0, 55.1, 51.8 whole window. If it is not monotone the x axis is broken and
    nothing below may be read.
 2. ``OFF`` REPRODUCES ``M0270-S100`` TO THE DIGIT on the dev store -- same total return, same
    worst fall, same 1338 trades -- because with the gate switched off the subclass computes
    M0270's scale-1 targets and nothing else changed. A mismatch is a bug and is chased before
    anything else is read. This is also what licenses using M0270's 0.1732 at all: it is the same
    chassis, the same store and the same era, not a constant carried in from elsewhere.
 3. 2009-2015 LEADS, if the hypothesis holds exactly, starting from M0270-S100's recorded +0.52
    at 1.43 points of cash: D000 -2.60, D006 -3.44, D016 -4.27, D030 -5.31, D042 -6.14 points a
    year. The lab's "3.6 is a constant of the switch" would instead put D000 at -3.08.
 4. THE DELAY SLOPE WILL COME OUT ABOVE 0.1732, and this is the prediction I am least sure of. The
    delay's cash is bought in the weeks just AFTER the market crosses back above its own average,
    and in a decade of recoveries and no bear market those weeks were strong. If ``s`` lands near
    0.1732 anyway, then even the most expensive-looking cash on this tape is priced like ordinary
    cash, and the hypothesis survives in its strongest form.
 5. THE WHOLE WINDOW GOES THE OTHER WAY AND MUST BE REPORTED ANYWAY. Over 1996-2015 the gate
    carries 2000 and 2008, where the delay rungs carry them too and more of them. I expect the
    gate to look good there and the longer delays to look better still on worst fall while losing
    return, and none of that touches the 2009-2015 claim. The 2003-2008 era, where M0270 priced
    cash at 0.0051 a point, is where the switch should look nearly free.
 6. TURNOVER IS NEARLY CONSTANT ACROSS THE DELAY RUNGS and falls slightly at the long end, because
    a delay can swallow a whole episode and save a round trip rather than add one. ``OFF`` pays no
    gate round trips at all, so the OFF-to-D000 step mixes the gate's cash with the gate's fees;
    the analysis runs zero-fee twins of all six arms outside the registry to split them, exactly
    as M0270 did. TRADE COUNT IS A DEAD METER (insight 495) and is printed for completeness only.
 7. NO ARM IS A CANDIDATE. The base book loses to a deposit-matched SPY and falls past 50%; the
    delay field has no preset and no resolver entry; eligibility would be reported and would still
    not be promoted.
 8. BOTH STORES IN ONE SWEEP (insight 482). The dev store answers the claim; the
    survivorship-check store is loaded in the same process and reported beside it, with both
    fingerprints printed, because a ratio drawn across two store vintages is not a comparison.

-------------------------------------------------------------------------------------------------
TRAPS ON THIS HOST, ALL PREVIOUSLY MEASURED

  * A SLOPE READ FROM TWO POINTS IS NOT A MEASUREMENT (insight 533). Five delay rungs, evenly
    spaced, over 36 points of cash.
  * AN UNDER-SHAPED CONTROL'S MARGIN HAS UNKNOWN SIGN (insight 481). ``OFF`` is not under-shaped:
    it is the identical allocator with one boolean removed, and it is a dose-response reference
    rather than a draw.
  * THE LAB'S OWN GATE-OFF MACHINERY ALREADY EXISTS (``lab gate``) and is used in the analysis as
    the across-the-lab half: the ladder prices the gate on ONE book precisely, and a gate-off
    sweep over recorded gated books asks whether the same arithmetic holds where the lab actually
    lives. Neither half is quoted without the other.
  * MARKET-SERIES READS ESCAPE THE LOOKBACK CAP, HISTORY BARS DO NOT. This allocator reads SPY
    through ``history`` and so is capped at 473 bars; it declares 284 (200 for the average plus 84
    for the longest delay), which is inside the cap and inside the smoke fixture.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0127_slot_relative_resize_band import T00
from seer_engine.lab.methods.m0266_exposure_matched_rebalance import ScaledBandParams
from seer_engine.lab.methods.m0270_exposure_return_curve import ExposureLadderBook
from seer_engine.sim.book import Target
from seer_engine.sim.rules import TradeRules
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, FactorPrepared, trend_on

ADDED = date(2026, 10, 21)

#: The band every arm runs: zero, so every holding is traded back to its slot on every month
#: start. M0127's object, imported through the same chain M0266 and M0270 use, so the three
#: methods' chassis cannot drift apart.
BAND: TradeRules = T00

#: The shared gate, in the one spelling every gated book in this lab expresses it:
#: ``FactorParams.trend == ("SPY", 200)``, read by ``f_factor.trend_on``. ``FactorParams()``
#: carries exactly that by default; no other field of it is read here, because the ranking on this
#: book is M0266's dollar-volume screen and not a factor rank -- ``rank`` is required by the
#: dataclass and is never read on this path.
GATE = FactorParams(rank="momentum")
GATE_N = 200

#: The ladder, in sessions of continuous gate-on required before the book comes back. ``None`` is
#: the gate switched off entirely -- the no-opinion arm. Fixed here, in the pre-registration
#: commit, before any return was computed.
DELAYS: tuple[int | None, ...] = (None, 0, 6, 16, 30, 42)

#: The longest delay, and the extra SPY bars the walk-back needs beyond the 200-bar average. The
#: cap is the smoke fixture's, not the idea's: see the ladder note in the module docstring.
MAX_DELAY = 42

#: ``M0270-S100``'s recorded average exposure on the dev store: the base book at full scale with
#: no gate, which is what the ``OFF`` arm is. Used only to PREDICT where the rungs land, never to
#: calibrate one.
EXPOSURE_AT_FULL_WEIGHT = 0.9856884609713539


@dataclass(frozen=True, slots=True)
class DelayedGateParams:
    """The base book's params, plus the one field this method adds: a re-entry delay.

    ``delay`` is the number of consecutive sessions the shared SPY 200-day gate must already have
    been on before the book is allowed back in. ``0`` is the gate exactly as every other book in
    this lab reads it. ``None`` switches the gate off altogether, which is the no-opinion arm.

    The base book is carried as a whole ``ScaledBandParams`` rather than re-typed, so this
    method's arms and M0266's and M0270's cannot drift apart, and so the recorded config digests
    of those methods are untouched (a shared params class may not gain a field -- it would move
    every digest that already references it).
    """

    book: ScaledBandParams = ScaledBandParams()
    delay: int | None = 0

    def __post_init__(self) -> None:
        if not isinstance(self.book, ScaledBandParams):
            raise TypeError(f"book must be ScaledBandParams, got {type(self.book).__name__}")
        if self.delay is None:
            return
        if isinstance(self.delay, bool) or not isinstance(self.delay, int):
            raise TypeError(f"delay must be None or an int, got {self.delay!r}")
        if not 0 <= self.delay <= MAX_DELAY:
            raise ValueError(f"delay must be in 0..{MAX_DELAY} sessions, got {self.delay}")

    def as_dict(self) -> dict[str, str]:
        out = dict(self.book.as_dict())
        out["gate"] = "off" if self.delay is None else f"SPY:{GATE_N}"
        out["reentry_delay_sessions"] = "none" if self.delay is None else str(self.delay)
        return out


def _check(params: object) -> DelayedGateParams:
    if not isinstance(params, DelayedGateParams):
        raise TypeError(f"params must be DelayedGateParams, got {type(params).__name__}")
    return params


def gate_clear(history: Mapping[str, History], data_date: date, delay: int | None) -> bool:
    """Is the book allowed in on ``data_date``?

    ``None``: always, the gate is off. Otherwise the shared gate must be on at ``data_date`` AND
    at every one of the ``delay`` SPY sessions before it -- "continuously on for at least ``delay``
    sessions", which is the same reading of the delay used to size the ladder before it ran.

    The walk steps back through SPY's own bar dates, so every date handed to ``trend_on`` is a
    session SPY actually has, and ``trend_on``'s own "no bar dated d" guard never fires for a
    reason other than the data date itself. Reads only bars dated <= ``data_date``.
    """
    if delay is None:
        return True
    if not trend_on(history, data_date, GATE):
        return False
    h = history.get("SPY")
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None:
        return False
    if i < delay:
        return False
    for k in range(i - delay, i):
        if not trend_on(history, h.dates[k].astype(object), GATE):
            return False
    return True


class DelayedGateBook(ExposureLadderBook):
    """M0270's base book -- hence M0266's, by inheritance -- behind the shared gate with a delay.

    Subclassed twice over rather than copied, so that the ``OFF`` arm is guaranteed, not merely
    believed, to compute M0270-S100's targets. The only overrides are ``id`` (so the digests are
    distinct), ``symbols`` (SPY is now read, and must be loaded), ``lookback`` (the gate's average
    plus the longest walk-back) and the two target paths, each of which asks ``gate_clear`` first
    and otherwise delegates to the parent unchanged.
    """

    id = "M0271"

    def lookback(self, params: Any) -> int:
        """242 bars: the gate's 200-bar average plus the 42-session walk-back of the longest rung.

        THE SAME VALUE AT EVERY RUNG, including ``OFF``, so no arm's scored window differs from
        another's -- which is what keeps every paired difference in this method a difference in
        the delay alone. Comfortably inside the 473-bar cap the smoke fixture imposes.
        """
        return max(super().lookback(_check(params).book), GATE_N + MAX_DELAY)

    def symbols(self, params: Any) -> tuple[str, ...]:
        """SPY, which the gate reads. ``None`` delay still declares it: an arm must not change
        which instruments the store loads, or the arms stop being the same measurement."""
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return super().uses_members(_check(params).book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        q = _check(params)
        if not gate_clear(history, data_date, q.delay):
            return ()
        return super().targets(history, members, data_date, held, q.book)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        q = _check(params)
        if not gate_clear(prepared.history, data_date, q.delay):
            return ()
        return super().targets_prepared(prepared, members, data_date, held, q.book)


BOOK = DelayedGateBook()

#: The gate's own calendar on this store, measured before the ladder ran and costing no backtest:
#: monthly decision sessions out of the market, 2009-2015 (82 decisions) and whole window (238).
#: Predictions only; the realised exposures are read, never aimed at.
OUT_SHARE: Mapping[int | None, tuple[float, float]] = {
    None: (0.0000, 0.0000),
    0: (0.1829, 0.2647),
    6: (0.2317, 0.3487),
    16: (0.2805, 0.3908),
    30: (0.3415, 0.4412),
    42: (0.3902, 0.4748),
}


def _v(delay: int | None) -> Candidate:
    era, whole = OUT_SHARE[delay]
    if delay is None:
        suffix, what = "OFF", "no gate at all: the no-opinion arm, always invested"
    elif delay == 0:
        suffix, what = "D000", "the shared SPY 200-day gate, plain and unmodified"
    else:
        suffix = f"D{delay:03d}"
        what = (
            f"the shared SPY 200-day gate, back in only once it has been on for {delay} "
            f"consecutive sessions"
        )
    return Candidate(
        id=f"M0271-{suffix}",
        family="M0271",
        rules=BAND,
        allocator=BOOK,
        params=DelayedGateParams(delay=delay),
        rationale=(
            f"{what}; out of the market on {era * 100:.2f}% of monthly decisions in 2009-2015 and "
            f"{whole * 100:.2f}% whole window, so predicted average exposure "
            f"{(1 - whole) * EXPOSURE_AT_FULL_WEIGHT * 100:.1f}% over the scored window"
        ),
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0271",
    name=(
        "Is the safety switch's famous premium anything but its time in cash? A re-entry-delay "
        "ladder on an opinion-free book"
    ),
    family="market-trend-switch",
    source_kind="variation",
    source_ref=(
        "M0270, which priced a point of cash at 0.1732 points a year over 2009-2015 on this exact "
        "book; insight 463, the 3.6-points-a-year constant swept across 824 trials; insight 532, "
        "the hypothesis; insight 516, the real gate at the 38th percentile of 20,000 uninformed "
        "imitators with its own habits; insight 529, the lab clustering by its gate rather than "
        "by its ideas; insight 533, that a slope read from two points is not a measurement"
    ),
    parent_id="M0270",
    hypothesis=(
        "The lab treats 3.6 points a year as a constant of the shared SPY 200-day switch: swept "
        "across all 824 recorded trials since 2009, barely moving from book to book, and most of "
        "the typical post-2009 shortfall. M0270 has now priced the other half of that arithmetic "
        "on the same opinion-free 50-name book, in the same era, on the same store: one point of "
        "the account held in cash cost 0.1732 points a year over 2009-2015. Divide and the switch "
        "is worth 20.8 points of exposure. Measured off SPY's own bars before this ran, the plain "
        "gate is out of the market on 15 of 82 monthly decisions over 2009-2015 -- 18.29 percent, "
        "about 18 points of a 98.6-percent-invested book -- and 18.0 times 0.1732 is 3.12 points "
        "a year. The premium and the time in cash agree to within half a point with no backtest "
        "at all. SO THE HYPOTHESIS IS THAT THE SWITCH'S COST IS NOT A PROPERTY OF THE SWITCH: it "
        "is how long the rule stays out, priced at what being out was worth in the era, with no "
        "judgement in it. Two independent results already point the same way. Twenty thousand "
        "uninformed sticky switches drawn at the real gate's own transition rate put the real "
        "gate at the 38th percentile of its own imitators over 2009-2015. And the lab's books "
        "cluster by the gate they share rather than by the ideas inside them, at 0.633 against "
        "0.064, with the lab-wide resemblance collapsing from 0.288 to 0.070 once the gate-alone "
        "book is projected out. THE RECORDED TRIALS CANNOT SETTLE IT, because every gated book "
        "here sits behind the same rule read on the same monthly dates and four of the five live "
        "books go to cash on the identical 28.3 percent of their decision days: exposure is a "
        "constant there, not a lever. So this method makes exposure the independent variable. One "
        "book -- M0266's allocator, subclassed from M0270's own subclass so all three cannot "
        "drift apart, the 50 most-traded index members at equal weight, band zero, no picking, no "
        "brake, full scale -- behind the lab's shared gate, with one dial: a re-entry delay of 0, 6, "
        "16, 30 and 42 sessions of continuous gate-on required before the book comes back, plus "
        "the gate switched off entirely as the no-opinion arm. Every arm leaves the market "
        "on exactly the same days for exactly the same reason; they differ only in how long they "
        "wait, so time in cash moves deliberately while the signal is held fixed. Measured in "
        "advance off SPY's bars and reading no return at all, the five gated rungs are out on 18.29, "
        "23.17, 28.05, 34.15 and 39.02 percent of 2009-2015 decisions -- five steps of 4.9, 4.9, "
        "6.1 and 4.9 points, so the rungs are evenly spaced in the x axis, which is cash, rather "
        "than in the dial. That is a 21-point lever on five points, which is what insight 533 "
        "demands after M0266 read an eight-fold store gap off two. The ladder stops at 42 "
        "sessions because the smoke fixture that catches dead allocators stops it there, and "
        "shrinking a frozen fixture to fit one experiment is the wrong trade; a ladder anchored "
        "close to the gate's own operating point also extrapolates back to the no-gate arm "
        "better than one stretched far past it. THE "
        "DELIVERABLE, fixed now. Fit the straight line through the five delay rungs in points of "
        "cash against de-funded lead; its slope is the price of episodic cash at the gate's own "
        "boundary. Extrapolate it back to the no-gate arm's cash level and compare the prediction "
        "P with that arm's measured lead A. P equal to A means the gate's own 18 points of cash "
        "are priced exactly like the delay's and the switch's decision carries no information. A "
        "below P means the gate's cash was cheaper than the delay's, so the exit decision does "
        "carry information and three lines of evidence this week were misread. A above P is "
        "anti-skill and would be reported as such. The headline residual is the gate's measured "
        "cost minus 0.1732 times its own points of cash, and the hypothesis predicts zero. The "
        "noise band is internal and is not borrowed: the root-mean-square residual of the five "
        "rungs about their own fitted line, because every rung is the same book on the same tape "
        "with one dial moved, and M0270's rung-pair errors on this chassis ran 0.000 to 0.034 "
        "points a year. A residual within half a point a year confirms the hypothesis; one of a "
        "point or more, with a rung scatter under 0.2, falsifies it and says the switch has real "
        "timing skill worth about that much a year; in between the answer is 'mostly cash, with a "
        "residual too small to tune against'. PREDICTIONS. Realised exposure is strictly "
        "decreasing in delay and lands within 2 points of 98.6, 80.5, 75.7, 70.9, 64.9 and 60.1 "
        "percent over 2009-2015, the era the claim is about, with exposure re-measured over that "
        "era's own sessions rather than taken from the whole-window average a trial records; if "
        "it is not monotone the x axis is broken and nothing may be read. The no-gate "
        "arm reproduces M0270-S100 to the digit on dev, which is what licenses using 0.1732 at "
        "all. If the hypothesis holds exactly the 2009-2015 leads are plus 0.52, minus 2.60, "
        "minus 3.44, minus 4.27, minus 5.31 and minus 6.14 points a year, where the "
        "'3.6 is a constant' reading would instead put the plain gate at minus 3.08. The "
        "prediction I am least sure of is that the delay slope comes out ABOVE 0.1732, because "
        "the delay buys its cash in the weeks just after the market crosses back above its own "
        "average and in a decade of recoveries those weeks were strong; if it lands near 0.1732 "
        "anyway the hypothesis survives in its strongest form. The whole window goes the other "
        "way, carries 2000 and 2008, and is reported anyway without being allowed to touch the "
        "2009-2015 claim. Turnover is near-constant across the rungs and falls slightly at the "
        "long end because a delay can swallow an episode and save a round trip; the no-gate arm "
        "pays no gate round trips at all, so zero-fee twins of all six arms are run outside the "
        "registry to split the gate's cash from the gate's fees, exactly as M0270 did, and trade "
        "count is a dead meter on this host and is printed for completeness only. Both stores are "
        "loaded in one process with both fingerprints printed, because a ratio across two store "
        "vintages is not a comparison. No arm is a candidate: the base book loses to a "
        "deposit-matched SPY and falls past 50 percent, and the delay field has no preset and no "
        "resolver entry, so eligibility would be reported and would still not be promoted. "
        "Fractional shares, Gotrade's real fees, the owner's funding plan. Success is a "
        "measurement."
    ),
    expected_failure=(
        "THE LIKELIEST FAILURE IS THAT THE DELAY'S CASH IS NOT THE GATE'S CASH, and the ladder "
        "answers a neighbouring question instead of the one asked. A re-entry delay buys its "
        "extra cash in the weeks immediately after the market crosses back above its own average "
        "-- early recoveries, which in 2009-2015 were the strongest weeks on the tape. The gate's "
        "own cash is bought while the market is below that average. If those two kinds of cash "
        "turn out to be priced very differently, the back-extrapolation from the delay rungs to "
        "the no-gate arm is an extrapolation across a boundary rather than along a curve, and the "
        "honest reading is that the ladder priced the re-entry margin and not the switch. The "
        "method must then say so, and the residual against M0270's 0.1732 -- which is cash spread "
        "evenly over every session rather than bunched into episodes -- becomes the primary "
        "number instead of the extrapolation. THE SECOND FAILURE IS THE SHAPE OF THE CASH rather "
        "than its timing. M0270's 0.1732 was measured on cash held as a constant fraction every "
        "day; this method's cash is all-or-nothing, in episodes. Two books with the same average "
        "exposure and different cash shapes do not have to earn the same return, because "
        "compounding is not linear along a path, and nothing in the lab has ever measured that "
        "difference. If the no-gate arm's measured lead sits far from the delay line for that "
        "reason, the finding is about the shape of cash and not about the switch's judgement, and "
        "it would be a real finding that nonetheless does not answer the question. THE THIRD is "
        "fees. The no-gate arm never pays a gate round trip, and insight 462 already split the "
        "equal-weight book's post-2009 shortfall into 3.6 points of gate and 3.8 of fees, so the "
        "one step this method most needs to be clean is the one most polluted. The zero-fee twins "
        "are the answer and they are run for all six arms, but if the gross and net ladders "
        "disagree about the sign of the residual then the method has not settled anything and "
        "must say which half it believes and why. THE FOURTH is that 2009-2015 is 82 monthly "
        "decisions and five re-entries. Five episodes is not a sample; one unusually good or bad "
        "re-entry moves the whole delay slope, and a residual of half a point could be one month "
        "in 2011. The analysis must report how much of the residual rides on the single largest "
        "episode, and if one episode carries most of it the verdict is 'not settled on this era' "
        "rather than a number. THE FIFTH is that the base book is not a book anyone would trade: "
        "it falls past 50 percent and loses to SPY at every rung, so its 2009-2015 lead is a small "
        "difference between two large and violent numbers, and the price of cash measured on it "
        "may not be the price of cash on a 20-name momentum book that actually picks. That is the "
        "cost of using an opinion-free chassis, it is deliberate, and the across-the-lab half of "
        "the analysis -- a gate-off sweep over recorded gated books, which costs no method id -- "
        "exists precisely to check whether the arithmetic holds where the lab actually lives. THE "
        "SIXTH is the dull one and would be the most useful: the residual comes out at zero, the "
        "switch is confirmed to be a cash dial, and the lab has spent six method ids this month "
        "tuning a dial that was never connected to the price. That must be reported with the same "
        "emphasis as a surprise rather than buried as a non-finding."
    ),
    candidates=tuple(_v(d) for d in DELAYS),
    seen_keys=(
        "concept:gate-premium-is-time-in-cash",
        "concept:reentry-delay-ladder",
        "concept:gate-cash-priced-at-era-slope",
    ),
)
