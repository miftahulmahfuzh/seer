"""M0147 — Does width protect, or only cost? The same book's slot count asked on both price
histories at once.

Source: a variation of M0133, reserved by Sera 20261014-1312. It exists because two methods
measured the same axis on the same morning and reached opposite conclusions, and the difference
between them was not the method but the tape.

**The contradiction this method is built to resolve.** M0139 swept name counts on a tape that
actually invests the deposits and recorded worst falls of 20.6%, 19.6%, 20.7% and 19.9% at 20,
35, 50 and 70 names: flat, and not even ordered, across a 3.5x widening. It concluded that width
buys no safety behind a market switch, and it is exactly right about the history it read. M0133
then asked the narrower version of the same question -- 20 names against 40 -- on the
survivorship-check store, and the two answers differed by a factor of six: 22.7% -> 21.6% on the
dev store, 1.1 points; 29.4% -> 23.2% on the check store, 6.2 points. That second number is not
academic. The real-money bar is a 25% fall (``tuning.MAX_DRAWDOWN``), so on the fuller history
the 20-name book is outside it and the 40-name book is inside, and since D16 the hard gate reads
exactly that figure.

**Why the dev store cannot answer this question, stated as a mechanism rather than a suspicion.**
Spreading money across more names is protection against *one company failing on its own*. The dev
store prices no delisted name: ``survivorship_coverage.py`` puts it at 48% of index members in
1996 rising to 74% in 2014, and the 522 members it cannot price are overwhelmingly the ones that
went bankrupt or were bought (AABA, AAMRQ and their kind). A tape with the single-name collapses
removed can show what width *costs* -- more fees, more names below the top of the ranking -- and
can never show what it *saves*, because the thing it saves you from is not in the file. If that
is right, every slot-count decision this lab holds, the paper roster's twenty names included, was
settled on a measurement that was structurally blind in one direction.

**What this method does.** One engine, one screen, one ranking, one fee schedule, one funding
plan. Exactly two things vary: **how many names the book holds** -- 20, 30, 40, 55, 70 -- and, in
one sixth arm, **whether the market switch is on at all**. Then every arm is re-read through
``lab survivorship`` on the check store, which is report-only and costs no look, and the two
worst-fall curves are reported *paired*, width by width. The divergence between the curves is the
result; neither curve alone is.

**The engine is M0133's, imported rather than re-derived.** ``ASYM`` and ``AsymParams`` come from
that module, so the two methods share one implementation and a difference between them can only
be the slot count, the rebalance basis or the gate. The ranking: for each F4-screened member,
take the past 252 sessions, divide the stock's summed return on SPY's up days by SPY's own, do
the same on SPY's down days, and rank on the first less the second -- hold the K highest, equal
money, and sit entirely in cash whenever SPY closes under its 200-day average. ``inner.trend`` is
``None`` in every arm because the gate is the allocator's own, which keeps member eligibility
bit-identical between the gated and ungated arms.

**The rebalance basis is ``target``, and that is a deliberate change from the parent.**
``monthly-hold-frac-gotrade-tband`` measures the top-up band against 20% of the holding's own
target rather than 1% of the whole account. Under the equity basis the band does not scale with
the slot, so it binds harder the wider the book gets and a wide book is partly a cash position
whose fall is flattered -- M0123 measured a 100-name basket at 51% invested against 96%. This
method measures falls *at width*, which is precisely where that artefact would bite, so the fixed
basis is not optional here. M0139 priced the leak in this turnover regime at 0.00, 0.36, 0.72 and
1.43 points of invested share at 20, 35, 50 and 70 names -- small, because a gated book that turns
over roughly nine times a year already feeds its deposits in through churn. This book turns over
less (1,118 trades at 20 names against M0007's 1,607), so the leak could be larger here than
M0139 found; the recorded exposure column is what settles it, and the W20 and W40 arms sit
directly against M0133's recorded equity-basis twins so the basis change is measured and not
assumed.

Assumptions written down before the run:

- **The family is the reserved idea row's, ``stock-portfolio-construction``, not M0133's
  ``stock-updown-asymmetry``.** The subject here is slot count, the ranking is borrowed scaffolding,
  and M0123 -- the lab's other slot-count method -- already sits in that family. The lab's naming
  lesson (insight 92) says to name a family by what a method ranks on, and the counter-argument is
  noted: by that rule this file would read ``stock-updown-asymmetry``. It does not matter for
  safety, because D14 reads the curve rather than the string and this book will be behavioural kin
  of whatever it moves with once it has run; it matters only for how the backlog reads.
- **Promotion is not available and that is accepted up front.** The parent M0133 is dev-eligible
  and promotion-refused: its 20-name arm reads 0.91 behavioural correlation with a test-failed
  book against a 0.85 line, and this method's ancestry runs M0133 -> M0110. The value here is the
  measurement and the correction factor it yields for every past width decision, not a candidate.
- **The 70-name arms are structurally short in 1996 and nowhere else.** ``factor_weights``
  weights each chosen name 1/top rather than 1/len(chosen), so a book asking for 70 and finding
  64 is 64/70 invested by construction. The screen admits 64-97 names in 1996, 102-124 in 1997
  and 129 or more every year after, so at most six names are missing, in one year of twenty. Any
  exposure gap outside 1996 is the band or the gate, never the screen.
- **Deposits soften every fall in this file alike** (10,000,000 IDR opening, 5,000,000 IDR on the
  25th of each month, 237 deposits), so these numbers may be lined up against M0133's, M0139's and
  M0110's, which are funded identically, and against no unfunded trial anywhere.
- Pure: every piece reads only bars dated <= ``data_date``, and the preset is looked up by id so
  the file names the rule set exactly as the trial will record it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20_NOTREND
from seer_engine.lab.methods.m0128_near_miss_fixed_tape import MONTHLY_TBAND
from seer_engine.lab.methods.m0133_gated_updown_asymmetry import ASYM, AsymParams
from seer_engine.sim.rules import rule_owner_inputs

ADDED = date(2026, 10, 14)

#: The widths swept. 20 is the roster's number and M0133's headline; 70 is M0139's widest rung.
WIDTHS: tuple[int, ...] = (20, 30, 40, 55, 70)


def _params(top: int, gate: str = "sma200") -> AsymParams:
    """M0133's asymmetry rank with only the slot count (and, in one arm, the gate) moved."""
    return AsymParams(replace(N20_NOTREND, top=top), gate=gate)


def _v(suffix: str, top: int, rationale: str, gate: str = "sma200") -> Candidate:
    return Candidate(id=f"M0147-{suffix}", family="M0147", rules=MONTHLY_TBAND, allocator=ASYM,
                     params=_params(top, gate), rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(MONTHLY_TBAND))


METHOD = Method(
    id="M0147",
    name="Does width protect, or only cost? Ask it on the history that has the failures in it",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref=(
        "M0133 for the engine, the 20- and 40-name equity-basis rungs and the 6.2-point "
        "check-store gap; M0139 for the flat dev-store width curve this contradicts and for the "
        "band-basis arithmetic; M0123 for the equity-basis cash leak; M0110-DP20-UP and M0133-N40 "
        "for the ungated 20- and 40-name rungs the sixth arm extends"
    ),
    parent_id="M0133",
    hypothesis=(
        "A measurement, pre-registered so that it is held to numbers rather than to a story. Two "
        "methods measured book width on the same morning and disagreed by a factor of six, and "
        "the difference between them was the price history, not the method. M0139 swept 20, 35, "
        "50 and 70 names on a tape that invests the deposits and recorded worst falls of 20.6%, "
        "19.6%, 20.7% and 19.9% -- flat and unordered across a 3.5x widening -- and concluded "
        "that width buys no safety behind a market switch. M0133 asked 20 against 40 on the "
        "survivorship-check store and found 22.7% -> 21.6% on the dev store (1.1 points) against "
        "29.4% -> 23.2% on the check store (6.2 points), which straddles the owner's 25% "
        "real-money bar. The mechanism that reconciles them is plain and is the thing under test: "
        "width is protection against ONE company failing alone, the dev store prices no delisted "
        "name (48% of index members in 1996 rising to 74% in 2014, the missing 522 "
        "disproportionately the bankrupt and the bought-out), so a tape with the single-name "
        "collapses removed can show only what width costs and never what it saves. If that is "
        "right, every slot-count result this lab holds -- the paper roster's twenty names "
        "included -- was read off a measurement blind in one direction. "
        "WHAT IS RUN. M0133's engine imported verbatim (rank F4-screened members on upside "
        "participation minus downside participation over 252 sessions, hold the K highest in "
        "equal slots, all cash while SPY is under its 200-day average), at K = 20, 30, 40, 55 and "
        "70, plus one ungated 70-name arm. Fractional shares, Gotrade's real fees, the owner's "
        "plan (10,000,000 IDR opening, 5,000,000 IDR on the 25th), against a SPY fed the "
        "identical deposits on the identical days. The preset is monthly-hold-frac-gotrade-tband, "
        "the target basis, because the equity basis leaves a wide book partly in cash and this "
        "method measures falls AT WIDTH, which is exactly where that artefact bites; W20 and W40 "
        "sit against M0133's recorded equity-basis twins so the basis change is measured, not "
        "assumed. Every arm is then re-read on the check store through lab survivorship, which is "
        "report-only, records no trial and spends no look. "
        "WHAT IS PREDICTED, in numbers, before any result. (1) THE DEV CURVE IS FLAT. The five "
        "gated dev-store falls should sit inside 20.5% to 23.5% with no reliable ordering in "
        "width, reproducing M0139's finding on a second engine: 20 names near M0133's 22.7%, 70 "
        "names no more than 2 points gentler. (2) THE CHECK CURVE FALLS, MONOTONICALLY. The same "
        "five arms on the check store should start near 29.4% at 20 names and decline every rung: "
        "roughly 26% at 30, 23% at 40 (M0133's recorded figure, which the basis change should "
        "move by under a point), 21.5% at 55 and 20.5% at 70. Equivalently, the paired gap "
        "between the two curves should shrink from about 6.7 points at 20 names to under 1.5 "
        "points at 70, because a wide book has little left for the missing failures to take. "
        "(3) THE PRICE OF THAT PROTECTION IS RETURN. Funded return should decay with width as it "
        "did in both parents -- M0133 gave up 2.1 points a year from 20 to 40 names, M0139 2.8 "
        "points from 20 to 70 -- so the 70-name arm is predicted between 11% and 13.5% a year "
        "against the 20-name arm's 15.6% and deposit-matched SPY's 7.2%. Both halves belong in "
        "the verdict: protection that costs more than it saves is not a recommendation. "
        "(4) THE DECISION NUMBER IS MAR ON THE CHECK STORE. If dev-store MAR picks 20 names while "
        "check-store MAR picks 40 or 55, then the lab's entire width record is biased narrow by a "
        "knowable amount, and that correction factor -- not this book -- is the deliverable. "
        "(5) THE SIXTH ARM SAYS WHETHER THE GATE IS WHY WIDTH LOOKS USELESS. Ungated, the "
        "recorded dev falls are 74.0% at 20 names (M0110-DP20-UP) and 69.1% at 40 (M0133-N40), "
        "already 4.9 points of width effect where the gated arms show 1.1. Ungated 70 is "
        "predicted at 60% to 67% on dev and deeper still on the check store. If width moves an "
        "ungated book on dev and not a gated one, then the switch has already removed the falls "
        "spreading out can help with, and M0139's conclusion is right about gated books and wrong "
        "as a general claim -- which is the open question M0139's own analysis named as the more "
        "valuable of its two. PROMOTION IS NOT AVAILABLE: the line runs M0133 -> M0110 and "
        "M0133's 20-name arm reads 0.91 behavioural correlation with a test-failed book against a "
        "0.85 line. Accepted before the run."
    ),
    expected_failure=(
        "The failure that would matter most is the dull one: BOTH CURVES FLAT. If the check-store "
        "fall sits within 1.5 points across 20 to 70 names, then M0133's 6.2 points was one "
        "pair's idiosyncrasy -- two arms, one comparison, no curve -- M0139's conclusion stands "
        "unchanged and unqualified, and the honest verdict says so first and plainly rather than "
        "hunting for a width effect in a subgroup. That outcome is worth the id: it would stop "
        "the lab spending further ids on slot counts. "
        "Specific failures written now. (1) THE CURVE COULD GO THE WRONG WAY. A wider book owns "
        "more of the shortlist and therefore more of the companies the dev store cannot price, so "
        "the check store could punish width rather than reward it -- which is exactly what "
        "happened to M0123's all-shortlist basket, which lost its entire edge there. A rising "
        "check-store fall curve would mean width concentrates survivorship exposure instead of "
        "diluting single-name risk, and would be a stronger argument for twenty names than any "
        "dev-store number. (2) ONE ERA COULD BE DOING ALL THE WORK. If the whole check-store width "
        "effect is 2008 and the 2009-2015 falls are identical across widths, then this is a "
        "measurement of one crisis and not of width, and the verdict must say which years the gap "
        "lives in before it says anything else -- 2009-2015 is the best-covered stretch and the "
        "one most like today. (3) REPRODUCTION FIRST. lab survivorship prints a dev re-run beside "
        "the recorded trial; if any arm does not reproduce, its side-by-side is meaningless and "
        "must be dropped from the curve rather than quoted. The same applies to the W20 and W40 "
        "arms against M0133's equity-basis twins: if the basis change moves the dev fall by more "
        "than a point, the two methods' numbers are not interchangeable and the curve must be read "
        "inside this method alone. (4) FEES AND FILL AT THE WIDE END. Gotrade's schedule bites "
        "hardest on small orders and this account ramps from 10,000,000 IDR, so a 70-name book "
        "holds slots near 18 USD in its early years; some of the return decay with width will be "
        "fees rather than signal decay, and trade counts and turnover must be quoted so the two "
        "can be told apart. The 70-name arms are also structurally short by up to six names in "
        "1996, and any exposure gap inside that year belongs to the screen. (5) THE CHECK STORE "
        "IS A CROSS-CHECK, NOT TRUTH. It adds most of the members the dev store cannot price, not "
        "all of them, and real collapses were kept while data errors were cleaned -- a judgement "
        "call. It is not a gate here, lab run and lab test refuse it, and nothing in this method "
        "may be reported as though its numbers were the dev store's. (6) DEPOSITS SOFTEN EVERY "
        "FALL HERE ALIKE and no figure may be lined up against an unfunded trial. (7) THE "
        "UNGATED ARM WILL FAIL THE SCREEN and is expected to: a 60%-plus fall is outside the 50% "
        "dev screen, let alone the 25% real-money bar. It is evidence about the mechanism, never "
        "a candidate, and must not be reported as a near miss."
    ),
    candidates=(
        _v("W20", 20, "Twenty names, the roster's width, on the fixed tape: the curve's left end"),
        _v("W30", 30, "Thirty names: the first rung past the roster, where the check-store gap should start closing"),
        _v("W40", 40, "Forty names: the width that stayed inside the owner's 25% fall limit on the fuller history"),
        _v("W55", 55, "Fifty-five names: the rung that says whether the protection keeps accruing or flattens"),
        _v("W70", 70, "Seventy names, M0139's widest rung, where the dev tape showed no safety at all"),
        _v("W70-NOGATE", 70, "Seventy names with the market switch off: does width protect a book that "
                             "has not already stepped out of the fall?", gate="none"),
    ),
    seen_keys=(
        "concept:book-width-read-on-the-survivorship-check-store",
        "concept:width-protection-versus-width-cost-paired-curve",
    ),
)
