"""M0245 -- The 200-day gate is insurance: find out which of its exits were claims.

Source: variation of M0241, whose SPLIT12-NOGATE arm priced the same switch on an event book.
Reserved by Sera 20261019-1014. The switch itself is old -- Brock, Lakonishok and LeBaron (1992)
for the banded moving-average rule, Faber (2007) for the ten-month version -- so nothing in the
*gate* is a new anomaly and no fade argument applies to it. What is new is the question.

WHY THIS METHOD EXISTS. The SPY 200-day gate sits under half the lab. Three methods have now
priced it (M0084 alone on SPY, M0113 on the way back in, M0136 on coming back in instalments)
and every one of them ended in the same uncomfortable place: over the full window the gate helps,
after 2009 it helps nothing. On M0241's event book it was worth 1.2 points a year and 38 points
of worst fall over twenty years, and cost about nine points a year over 2009-2015. The lab has
read that as the gate decaying. This method asks whether it decayed at all, or whether 2009-2015
simply contained no crash to claim on.

THE EPISODE LEDGER (measured on the dev store before this file was written; feasibility, not a
result, in the same spirit as M0241's split-count table). Reading the plain gate at each monthly
check on SPY's own total-return tape from 1994-01 to 2015-10 gives **eleven** off-spells:

    exit         back         months   SPY TR while out   deepest fall while out
    1994-03-31   1994-08-31        5         +8.2%            -5.3%
    1994-11-30   1995-01-31        2         +4.3%            -1.7%
    1998-08-31   1998-10-30        2        +11.8%            -9.7%
    1999-09-30   1999-10-29        1         +5.5%            -6.7%
    2000-09-29   2003-04-30       31        -36.1%           -45.8%     <- a claim
    2004-07-30   2004-10-29        3         +2.2%            -4.2%
    2005-04-29   2005-05-31        1         +3.5%            -1.8%
    2007-12-31   2009-06-30       18        -36.3%           -53.0%     <- a claim
    2010-05-28   2010-09-30        4         +6.6%            -8.9%
    2011-08-31   2012-01-31        5         +9.5%            -9.6%
    2015-08-31   2015-09-30        2         +0.7%            -5.6%

Two of the eleven were claims. The other nine cost, between them, 52 points of missed market.
**Every spell after 2009 was a premium and none was a claim**, because the dev window's
2009-2015 holds no bear market at all. So the gate's post-2009 record is not evidence that it
stopped working; it is six and a half years of paying for insurance nobody needed. That is a
different sentence from the one the lab has been writing, and it changes what to do about it.

WHAT IS VISIBLE AT THE MOMENT OF THE EXIT. If claims can be told from premiums on the day the
gate fires, the insurance becomes cheap. The ledger says the obvious tells all point the WRONG
WAY. How far SPY had broken below its average: the two claims were shallow breaks (-0.95% and
-1.96%) while the four deepest breaks (-9.5% in 1998, -4.9% in 2011, -4.8% in 2015, -3.6% in
1994) were every one of them a whipsaw. How frightened the market was: the claims fired at
ordinary volatility (17% annualised) while the three loudest exits (47%, 35%, 31%) were all
whipsaws. Crashes in this window arrived quietly and whipsaws arrived screaming. That kills the
depth filter and the volatility filter before either is pre-registered, and it explains after the
fact why M0084's 3% band bought nothing.

ONE TELL IS LEFT, AND IT IS NOT READ ON THE EXIT DAY. A whipsaw is a dip beneath an average that
is still climbing; a bear market is a dip beneath an average that has turned down. The slope of
the 200-day average cannot be read usefully at the instant of the break -- both claims broke
while the average was still rising -- but it can be read at EVERY monthly check afterwards, and
that is the rule this method tests: **stay invested while SPY is below its 200-day average as
long as that average is still rising, and go to cash only once it has turned down.**

Measured on the same tape at full exposure and no fees (feasibility again), that rule keeps both
crash exits -- it leaves in 2000-11 instead of 2000-09, and in 2008-02 instead of 2007-12, two
months late each time -- and skips the 1998, 1999, 2004, 2005 and 2010 whipsaws entirely. It
holds the worst fall at the gate's own level and earns more, at every slope window from five
sessions to a hundred and twenty-six, and its mirror (leave only while the average is RISING) is
a disaster on both axes. That is a dose-response with a mirror, which is the strongest evidence
shape this lab has.

WHY THIS IS NOT A FOURTH ATTEMPT AT HYSTERESIS. The lab has refused three: a wider threshold
(M0101), a different sell rule (M0143) and a waiting period (M0148). The last of those left a
standing rule -- do not pre-register a fourth without new evidence that the flips are noise --
and the ledger above IS that evidence: nine of eleven flips were noise and two were signal, and
they are told apart by something the earlier three never read. M0148's cool-off failed because it
counted MONTHS, and the months it blocked were the 2008 exit. This rule counts nothing; it reads
the shape of the market and blocks only the exits the market never justified.

THE HONEST WEAKNESS, WRITTEN BEFORE THE RUN. The dev window contains two crashes. A rule that
delays every exit by about two months looks good here because both of this window's crashes
happened to be slow. Two is not a sample. Nothing measured on dev can settle this; the folds are
the only within-window check and the test window, which holds 2020 and 2022, is the real one.

THE SIX ARMS. All hold nothing but SPY at full weight or nothing, fractional shares at Gotrade's
real fees on the owner's monthly top-ups, monthly, one shared lookback so every arm is scored on
the same sessions and each paired difference is the confirmation rule alone.

    * GATE -- the plain switch, the control every other arm is read against.
    * FALL21 / FALL63 / FALL126 -- leave only once the 200-day average is below where it stood
      21, 63 or 126 sessions ago. The dose-response ladder.
    * RISE21 -- the mirror: leave only while the average is still RISING. Buys the insurance
      precisely when the theory says it is worthless, and must be far worse on both axes.
    * CROSS -- leave only once the 50-day average is below the 200-day one. The famous death
      cross: the published rule this lab's own slope test has to beat to be worth anything.

The decision is a pure function of SPY's closes on ``data_date``: no state, no reading of the
book's own weight, nothing recovered from price. Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 19)

BENCH = "SPY"  # the only instrument this method ever holds
SMA_N = 200  # the gate's average, frozen in every arm
CROSS_N = 50  # the death cross's fast average
#: The longest slope window any arm reads, and the bound its validation enforces.
MAX_SLOPE_N = 126
#: One lookback for all six arms, so they are scored on exactly the same sessions: the 200-day
#: average, plus the oldest average a slope arm compares it with, plus the bar itself. Longer
#: than M0084's 253, so this method's window starts 1994-05-17 rather than 1994-01-28 and its
#: numbers are compared with the GATE arm here, never directly with M0084's.
LOOKBACK = SMA_N + MAX_SLOPE_N + 1
#: The lab's gate value, reused rather than re-implemented: the exit test is F4's, unchanged.
SMA_GATE = FactorParams(rank="momentum", trend=(BENCH, SMA_N))
FULL = equal_weight(1)

Confirm = Literal["none", "fall", "rise", "cross"]
_CONFIRMS: tuple[str, ...] = ("none", "fall", "rise", "cross")


@dataclass(frozen=True, slots=True)
class ConfirmParams:
    """What must agree with the 200-day break before the book goes to cash."""

    confirm: Confirm = "none"
    slope_n: int = 0  # sessions the 200-day average is compared with; 0 unless confirm is fall/rise

    def __post_init__(self) -> None:
        if not isinstance(self.confirm, str) or self.confirm not in _CONFIRMS:
            raise ValueError(f"confirm must be one of {_CONFIRMS}, got {self.confirm!r}")
        if isinstance(self.slope_n, bool) or not isinstance(self.slope_n, int):
            raise TypeError(f"slope_n must be an int, got {type(self.slope_n).__name__}")
        if self.confirm in ("fall", "rise"):
            if not 2 <= self.slope_n <= MAX_SLOPE_N:
                raise ValueError(f"slope_n must lie in [2, {MAX_SLOPE_N}], got {self.slope_n}")
        elif self.slope_n != 0:
            raise ValueError(f"slope_n must be 0 for confirm={self.confirm!r}, got {self.slope_n}")

    def as_dict(self) -> dict[str, str]:
        return {
            "confirm": self.confirm,
            "slope_n": str(self.slope_n),
            "sma_n": str(SMA_N),
            "cross_n": str(CROSS_N),
            "hold": BENCH,
        }


def _check(params: object) -> ConfirmParams:
    if not isinstance(params, ConfirmParams):
        raise TypeError(f"params must be ConfirmParams, got {type(params).__name__}")
    return params


def sma_on(h: History, data_date: date, n: int, back: int = 0) -> float | None:
    """The ``n``-day mean close ending ``back`` sessions before the bar dated ``data_date``.

    None when there is no bar dated ``data_date`` or too little history. Summed left to right
    over exactly the bars it covers, like every other mean in the engine, so the answer does not
    depend on how much history was loaded.
    """
    i = h.index_of(data_date)
    if i is None:
        return None
    i -= back
    if i + 1 < n or i < 0:
        return None
    return float(np.mean(h.close[i + 1 - n : i + 1]))


def confirmed(h: History | None, data_date: date, p: ConfirmParams) -> bool:
    """Does the slow market agree that this break is worth leaving on?

    ``none``: always, which is the plain gate. ``fall`` / ``rise``: the 200-day average is below
    (respectively at or above) where it stood ``slope_n`` sessions earlier. ``cross``: the
    50-day average is below the 200-day one. Unknown -- no bar dated ``data_date``, or too little
    history for the comparison -- answers True, so a reading this method cannot make falls back
    to the lab's plain gate rather than silently staying invested through a crash.
    """
    if p.confirm == "none" or h is None:
        return True
    now = sma_on(h, data_date, SMA_N)
    if now is None:
        return True
    if p.confirm == "cross":
        fast = sma_on(h, data_date, CROSS_N)
        return True if fast is None else fast < now
    then = sma_on(h, data_date, SMA_N, back=p.slope_n)
    if then is None:
        return True
    return now < then if p.confirm == "fall" else now >= then


class GateConfirmationSwitch:
    """SPY at full weight, or nothing: the 200-day gate, with a second opinion on the exit."""

    id = "M0245"

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
        return False  # SPY's own closes decide everything; index membership is never touched

    def _run(self, history: Mapping[str, History], data_date: date,
             p: ConfirmParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: no new target
            return ()
        if not trend_on(history, data_date, SMA_GATE) and confirmed(h, data_date, p):
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), FULL)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)  # SPY-only and cheap: nothing to precompute

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, _check(params))


ALLOC = GateConfirmationSwitch()


def _v(suffix: str, params: ConfirmParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0245-{suffix}", family="M0245", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0245",
    name="The 200-day gate is insurance: nine of its eleven exits were premiums, two were claims",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0241 (its SPLIT12-NOGATE arm priced the same switch on an event book)",
    parent_id="M0241",
    hypothesis=(
        "The lab reads the SPY 200-day gate as a rule that decayed: it helps over twenty years "
        "and helps nothing after 2009. Reading the gate's exits one at a time says something "
        "else. On SPY's own tape from 1994 to 2015 the monthly gate has eleven off-spells. Two "
        "were claims -- out from 2000-09 to 2003-04 while SPY fell 36.1%, and from 2007-12 to "
        "2009-06 while it fell 36.3% -- and nine were premiums, costing 52 points of missed "
        "market between them. Every spell after 2009 was a premium and none was a claim, because "
        "the dev window's 2009-2015 holds no bear market. So the gate did not stop working; it "
        "spent six and a half years insuring against something that never happened. If claims "
        "can be told from premiums the insurance gets cheap. The obvious tells point the wrong "
        "way: both claims broke only 1-2% below the average and fired at ordinary volatility, "
        "while the deepest breaks (9.5% in 1998) and the loudest (47% volatility in 2011) were "
        "whipsaws -- crashes arrived quietly and whipsaws arrived screaming, which is why "
        "M0084's 3% band bought nothing. One tell survives, and it is read at every later check "
        "rather than on the exit day: a whipsaw is a dip beneath an average that is still "
        "climbing, a bear market is a dip beneath an average that has turned down. So: stay "
        "invested below the 200-day average while that average is still rising, and go to cash "
        "only once it has turned down. Six arms hold nothing but SPY, fractional at Gotrade's "
        "real fees on the owner's monthly top-ups, on one shared lookback -- GATE (the plain "
        "switch, the control), FALL21 / FALL63 / FALL126 (leave only once the average is below "
        "where it stood 21, 63 or 126 sessions ago: the dose-response ladder), RISE21 (the "
        "mirror, leaving only while the average still rises, which must be far worse on both "
        "axes or the slope reading is noise) and CROSS (the famous 50-over-200 death cross, the "
        "published rule the lab's own test must beat). SUCCESS IS A MEASUREMENT, NOT "
        "ELIGIBILITY: a 100%-SPY book trades a few dozen times in twenty years, so it can never "
        "clear the 100-trade bar and its profit factor and luck score are meaningless; the "
        "paired differences against GATE, the worst fall and the 2009-2015 split are the result. "
        "The hypothesis under test is that a FALL arm keeps both crash exits, holds the worst "
        "fall at GATE's level and earns more than GATE both whole-window and over 2009-2015, "
        "while RISE21 fails on both axes. Note the lookback is 327 bars, not M0084's 253, so "
        "this window starts 1994-05-17: compare with the GATE arm here, never directly with "
        "M0084's numbers. Assumed without asking: that a rule shaped by looking at this window's "
        "eleven episodes is still worth one pre-registered method, because the alternative is to "
        "keep guessing at the gate from books that also hold stocks."
    ),
    expected_failure=(
        "The honest weakness is the sample. This window holds two crashes. Any rule that delays "
        "every exit by about two months will look good here because both of this window's "
        "crashes happened to be slow -- SPY broke its average in September 2000 and December "
        "2007 and kept falling for months afterwards, so an average that turns down a month or "
        "two later still catches almost all of both. A fast crash would be caught far too late, "
        "and a fast crash is exactly what 1987 and 2020 were. Nothing measured on the dev window "
        "can settle that; two is not a sample, the folds are the only within-window check, and "
        "the test window is the real one. The second risk is that the FALL arms simply trade "
        "less and this is a fee story rather than a signal story -- the ladder is the test, "
        "since a longer slope window trades still less and should keep improving if it is fees, "
        "while a signal should peak and turn. The third is that the slope filter re-enters while "
        "SPY is still below its average, which is a bear-market bounce by another name: if a "
        "FALL arm's worst fall comes in much deeper than GATE's 18.9%, the filter bought its "
        "return by standing inside a crash, and the result should be read as a failure however "
        "good the average is. Fourth, this is the lab's FOURTH attack on the same switch -- a "
        "wider threshold (M0101), a different sell rule (M0143) and a waiting period (M0148) "
        "were all refused -- and the standing rule from M0148 is not to try a fifth without new "
        "evidence that the flips are noise. The episode ledger is offered as that evidence, but "
        "if these arms also fail, that rule should harden into closing this family: the switch "
        "is then simply at its best and the lab should spend its ideas on what the book holds "
        "instead of on when it holds it. Not modelled, as in every earlier switch method: "
        "interest on the cash held while the gate is off, which flatters SPY and penalises every "
        "switched arm, so every gap reported is an upper bound on the switch's cost."
    ),
    candidates=(
        _v("GATE", ConfirmParams("none"),
           "Control: the plain monthly 200-day switch, every other arm's yardstick"),
        _v("FALL21", ConfirmParams("fall", 21),
           "Leave only once the 200-day average is below where it stood a month earlier"),
        _v("FALL63", ConfirmParams("fall", 63),
           "The same at a quarter: the middle rung of the dose-response ladder"),
        _v("FALL126", ConfirmParams("fall", 126),
           "The same at half a year: the slowest rung, and the fewest exits"),
        _v("RISE21", ConfirmParams("rise", 21),
           "The mirror: leave only while the average still rises, which should be a disaster"),
        _v("CROSS", ConfirmParams("cross"),
           "Leave only once the 50-day average is under the 200-day one: the famous death cross"),
    ),
    seen_keys=(
        "concept:sma200-slope-confirmed-exit",
        "concept:gate-exit-episode-ledger",
        "concept:death-cross-confirmation-on-the-lab-gate",
    ),
)
