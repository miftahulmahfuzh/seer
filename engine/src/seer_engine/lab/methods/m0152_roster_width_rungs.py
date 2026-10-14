"""M0152 — The roster's own width question, re-asked at the rungs nobody has run.

Source: a variation of M0147, reserved by Sera 20261014-1435. M0147 established the mechanism and
the shape of the curve on a different ranking engine; this method puts the rungs the roster's
actual decision needs onto the roster's actual book.

**The decision this exists to settle.** The paper roster holds twenty names of M0007-N20-RAW's
picks and the owner mirrors it with his own money. That twenty rests on M0007's N10/N20/N30 sweep,
measured on the dev store. M0147 has since shown that the dev store is structurally blind to the
only thing width is for, and the correction at the roster's width is not small: M0128-RAW20 --
which *is* the roster's picking rule traded the way the owner trades it, fractional shares, real
Gotrade fees, the fixed top-up band -- falls 20.65% on the dev store and 25.05% on the
survivorship-check store. The owner's real-money bar is a 25% fall. On the dev tape he has a
comfortable margin; on the fuller history he is a tenth of a point outside it.

**Why the dev store cannot see this, stated as mechanism and not as suspicion** (M0147, insight
from that run; not re-derived here). A book falls for one of two reasons: the whole market drops,
or one holding collapses on its own. The SPY 200-day gate in this book removes most of the first.
The dev store removes most of the second by not containing it -- ``survivorship_coverage.py`` puts
member coverage at 48% in 1996 rising to 74% in 2014, and the roughly 522 members it cannot price
are overwhelmingly the companies that went bankrupt or were bought. Spreading money over more
names is protection against exactly the failures that are missing from the file. So behind a
market gate, on that tape, width can only ever show what it *costs*.

**What is already measured, and is therefore quoted rather than re-run.** On this engine and this
preset the lab already holds four rungs, each with a dev and a check-store reading:

===== ====================== ========= =========== =========== =============
names  trial                  dev fall  check fall  dev %/yr    check %/yr
===== ====================== ========= =========== =========== =============
20     M0128-RAW20 (#388)     20.65%    25.05%      +13.68      +11.98
35     M0139-N35-TBAND (#437) 19.60%    20.11%      +13.05      +12.11
50     M0139-N50-TBAND (#438) 20.70%    19.97%      +11.33      +11.89
70     M0139-N70-TBAND (#439) 19.89%    19.75%      +10.89      +10.88
===== ====================== ========= =========== =========== =============

``lab run`` would refuse those four digests and should: they are recorded, funded identically
(10,000,000 IDR opening, 5,000,000 IDR on the 25th, 237 deposits), and comparable to the last
digit. The whole five-point collapse in the check-store fall happens between 20 and 35 names, and
there is nothing inside that interval. **That interval is the roster's decision.** This method
buys the three rungs that sit in and just past it -- 25, 30 and 45 -- and reports all seven as one
paired curve.

**Nothing varies but the slot count.** ``_picks`` is M0007-N20-RAW's parameters with ``top`` moved
and nothing else: the same F4 screen, the same 12-1 month cumulative market-model residual
ranking, the same equal money per slot, the same all-cash rule while SPY closes under its 200-day
average, on ``monthly-hold-frac-gotrade-tband``. It is built with the identical construction
M0139 used, from the same imported ``RAW20`` and ``TREND``, so a reading at 25 names and a reading
at 35 names differ in one integer and in nothing else.

Assumptions written down before the run:

- **PROMOTION IS NOT AVAILABLE AND IS NOT SOUGHT.** This line runs through M0007, which is
  test-failed, so the hard gate refuses it on kin (D9/D13) whatever it scores. The deliverable is
  a width number the owner can hold with real money, with its return cost stated. Any arm that
  comes out ELIGIBLE on the dev screen is a by-product and must not be reported as a candidate.
- **The family is the idea row's, ``stock-residual-momentum``,** which is also what this book
  ranks on (insight 92). The parent is M0147 because the question and the method of answering it
  are M0147's; the engine is M0007's.
- **The check store is a cross-check, not truth** (``EODHD_SURVIVORSHIP_MARKET_PLAN.md`` D1). It
  adds most of the members the dev store cannot price and not all of them, and real collapses were
  kept while data errors were cleaned, which is a judgement call. Nothing here may be reported as
  though its numbers were the dev store's, and no recommendation may rest on a margin thinner than
  that judgement call is worth -- which is why the decision rule below asks for a 2-point cushion
  under the owner's bar rather than for the bar itself.
- **Deposits soften every fall in this file alike,** so these numbers line up against M0128's,
  M0139's and M0147's, which are funded identically, and against no unfunded trial anywhere.
- **Fee drag is not re-litigated.** M0139 established that the return decay across width in this
  family is signal decay and not fees: the total fee bill *falls* as the book widens, because
  wider slots trade in smaller amounts against a schedule with a floor that a 20-name book hits
  less often per dollar. Trade counts are quoted so a reader can check, not so the question is
  re-opened.
- Pure: every arm reads only bars dated <= ``data_date``; the preset is looked up by id so the
  file names the rule set exactly as the trial will record it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, TREND
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0128_near_miss_fixed_tape import MONTHLY_TBAND
from seer_engine.sim.rules import rule_owner_inputs
from seer_engine.strategies.f_factor import FactorParams

ADDED = date(2026, 10, 14)

#: The rungs this method buys. 20, 35, 50 and 70 are recorded and are quoted, never re-run.
WIDTHS: tuple[int, ...] = (25, 30, 45)


def _picks(top: int):
    """M0007-N20-RAW's params with only ``top`` moved: same screen, same gate, same ranking.

    Constructed exactly as ``m0139_names_on_an_invested_tape._picks`` constructs it, from the same
    imported ``RAW20`` and ``TREND``, so that this method's rungs and M0139's belong to one curve.
    """
    return replace(RAW20, inner=FactorParams(rank="momentum", top=top, trend=TREND))


def _v(suffix: str, top: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0152-{suffix}", family="M0152", rules=MONTHLY_TBAND, allocator=RESIDMOM,
                     params=_picks(top), rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(MONTHLY_TBAND))


METHOD = Method(
    id="M0152",
    name="How wide should the roster be? The rungs between twenty and fifty, on both price histories",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref=(
        "M0147 for the mechanism, the paired-curve method and the finding that the dev store is "
        "blind to what width protects against; M0139 for the 35/50/70 rungs on this engine and "
        "for the finding that width's return decay is signal and not fees; M0128-RAW20 (trial "
        "#388) for the 20-name rung, which is the roster's own book at real fees on the fixed "
        "tape; docs/lab/survivorship/width-curve-cross-family-2026-10-14.csv for the recorded "
        "check-store readings of all four"
    ),
    parent_id="M0147",
    hypothesis=(
        "A measurement whose output is a number the owner will act on with real money, not a "
        "candidate. The paper roster holds twenty names and the owner mirrors it. Traded the way "
        "he actually trades it -- fractional shares, Gotrade's real fee schedule, the fixed "
        "top-up band, his 5,000,000 IDR monthly deposit -- that book falls 20.65% on the dev "
        "store and 25.05% on the survivorship-check store, against a real-money bar of 25%. The "
        "same picking rule at 35 names falls 20.11% on the check store and earns 0.13 of a point "
        "a year MORE there than the 20-name book does, so on the honest history that widening is "
        "not even a trade-off. Every one of those five points of protection arrives somewhere "
        "between 20 and 35 names and the lab has never run a single rung inside that interval. "
        "This method buys three: 25, 30 and 45 names, M0007-N20-RAW's picks verbatim with only "
        "the slot count moved, on monthly-hold-frac-gotrade-tband, funded on the owner's plan "
        "against a SPY fed the identical deposits on the identical days. Then lab survivorship "
        "re-reads all three on the check store -- report only, no trial, no look -- and the seven "
        "rungs are reported as ONE PAIRED CURVE, dev beside check at every width, with the return "
        "cost beside the fall at every width. "
        "WHAT IS PREDICTED, in numbers, before any result. (1) THE DEV CURVE IS FLAT AND SAYS "
        "NOTHING. All three new dev-store falls should land inside 19.3% to 21.0%, indistinguishable "
        "from the recorded 20.65 / 19.60 / 20.70 / 19.89 and with no reliable ordering in width. "
        "If the dev curve alone were the evidence, this method would conclude that width is free "
        "to skip -- which is precisely the error the roster's twenty was built on. (2) THE CHECK "
        "CURVE FALLS STEEPLY AND MONOTONICALLY ACROSS THE NEW RUNGS. Predicted check-store worst "
        "falls: about 23.5% at 25 names (range 22.0-24.5), about 21.5% at 30 (range 20.3-22.8), "
        "about 20.0% at 45 (range 19.5-20.6). Equivalently the paired gap between the histories "
        "should fall from +4.4 points at 20 names to about +2.5 at 25, +1.2 at 30 and under +0.5 "
        "by 45, closing on the same schedule M0147's asymmetry book showed (+6.7, +5.3, +1.6, "
        "+0.2, -0.3 at 20/30/40/55/70). (3) THE RETURN COST IS SMALL UNTIL ABOUT 40 NAMES AND "
        "THEN IS NOT. Dev funded return is predicted at 13.3-13.6%/yr at 25 names, 13.0-13.4 at "
        "30 and 11.6-12.4 at 45, against the recorded 13.68 at 20; check-store funded return at "
        "11.9-12.3, 12.0-12.3 and 11.8-12.2 against the recorded 11.98 at 20. The prediction with "
        "the sharpest edge on it: ON THE CHECK STORE, 30 NAMES COSTS NOTHING AT ALL -- its funded "
        "return lands within 0.3 of a point of the 20-name book's and quite possibly above it, "
        "while its worst fall is 3 to 4 points gentler. If that holds, the owner is not being "
        "asked to trade return for safety at all; he is being asked to stop paying for a "
        "concentration that only looked profitable on a tape with the failures removed. "
        "(4) THE DECISION RULE, fixed now so the result cannot choose it. The recommended width "
        "is THE NARROWEST RUNG WHOSE CHECK-STORE WORST FALL IS AT OR UNDER 23.0% -- the owner's "
        "25% bar less a 2-point cushion, because the check store is a cross-check and not truth "
        "and a recommendation resting on a tenth of a point of margin is not a recommendation -- "
        "PROVIDED its check-store funded return is within 1.0 point a year of the 20-name book's "
        "11.98%. If no rung satisfies both, the recommendation is the rung with the best "
        "check-store MAR and the verdict says plainly that the owner is being asked to buy safety "
        "with return. Predicted answer: 30 names, at no return cost on the check store and about "
        "0.4 of a point a year on the dev store. (5) WHEN, NOT ONLY HOW FAR. The survivorship "
        "report gives the size of the worst fall and never its date, so 'the five points is one "
        "bad year' cannot be excluded from its rows alone. This method will bound it directly: "
        "the de-funded equity curve of every arm on both stores is available in process, so the "
        "trough date and the peak date of each maximum fall will be computed and reported beside "
        "it, and the 2009-2015 era lead will be read in the same table. The prediction is that "
        "every worst fall on both stores is dated inside 2008-2009 and that the check store's "
        "extra depth at 20 names is dated there too -- the gate is off through most of that "
        "stretch but not all of it, and single-name collapses cluster in exactly those months. If "
        "the trough dates diverge between stores, or if a check-store trough lands in 2011 or "
        "2015 where the dev store's does not, that is a finding in its own right and leads the "
        "verdict. (6) MOM-FR-GT (M0002-REL-85), the roster's OTHER book, has no survivorship row "
        "at all and has never been checked this way. Not fixable inside this method id; it will "
        "be named in the verdict and queued as the next idea, because the owner should learn it "
        "here rather than discover it later. "
        "ELIGIBILITY IS NOT THE POINT AND PROMOTION IS REFUSED. Some or all of these arms will "
        "likely read ELIGIBLE against the dev screen, as M0139's three did. The line runs through "
        "M0007, which is test-failed, so hard gate (K) refuses promotion on kin whatever they "
        "score. Accepted before the run. Any eligible arm is a by-product and must not be "
        "reported as a near miss or as a roster candidate."
    ),
    expected_failure=(
        "The failure that would matter most is the one that leaves the owner where he started: "
        "THE CHECK CURVE IS A CLIFF, NOT A SLOPE. If 25 and 30 names both read near 25% on the "
        "check store and only 35 drops to 20%, then the five points arrive all at once somewhere "
        "the lab still cannot see, the three rungs priced nothing, and the honest answer is '35 "
        "names, because that is the narrowest width anyone has actually measured inside the bar'. "
        "That outcome must be stated first and plainly rather than dressed up as precision. It is "
        "still worth the id -- 35 would then be a measured recommendation instead of an "
        "extrapolated one -- but it is a worse result than the one predicted and the verdict must "
        "say so. "
        "Specific failures written now. (1) THE CURVE COULD RUN THE WRONG WAY. A wider book owns "
        "more of the shortlist and therefore more of the companies the dev store cannot price, so "
        "the check store could punish width instead of rewarding it, as it did to M0123's "
        "all-shortlist basket. A check-store fall that RISES from 25 to 45 names would mean width "
        "concentrates survivorship exposure rather than diluting single-name risk, and would be a "
        "stronger argument for keeping twenty names than any dev number -- and the verdict would "
        "have to carry it. (2) ONE ERA COULD BE DOING ALL THE WORK, and this is the named hole "
        "M0147 left open. If every arm's worst fall is dated 2008-2009 and the 2009-2015 era "
        "leads are flat across width, then this is a measurement of one crisis dressed as a "
        "measurement of width, and the owner is being advised on the basis of a single autumn. "
        "The trough dates are computed precisely so that this cannot be glossed over; if the "
        "answer is 'one crisis', the verdict leads with it and the recommendation is downgraded "
        "to a hedge rather than a number. (3) REPRODUCTION FIRST. lab survivorship prints a dev "
        "re-run beside the recorded trial. Any arm whose dev re-run does not match its recorded "
        "trial has a meaningless side-by-side and must be dropped from the curve rather than "
        "quoted. (4) THE 45-NAME ARM MAY COST MORE THAN THE 50-NAME ARM APPEARS TO. The recorded "
        "50-name dev return (11.33%) is 1.7 points below the 35-name arm's, so the decay between "
        "35 and 50 is steep; 45 is predicted near the bottom of that slide and its only job is to "
        "price it. If 45 reads better than 35 on both stores the recorded 50-name rung becomes "
        "the anomaly and must be re-examined, not quietly dropped. (5) FEES AND FILL AT THE WIDE "
        "END. This account ramps from 10,000,000 IDR, so a 45-name book holds slots near 28 USD "
        "in its early years, where Gotrade's schedule is a far larger share of the order. M0139 "
        "found the total bill falls with width in this family, but that was measured at 35, 50 "
        "and 70, not at 25; the trade counts are quoted so the claim stays checkable. (6) THE "
        "CHECK STORE IS NOT TRUTH, and a recommendation that depends on the difference between "
        "23.0% and 25.0% on it is a recommendation that depends on which data errors somebody "
        "chose to clean. That is why the decision rule asks for a 2-point cushion; if the chosen "
        "rung clears 23.0% by less than half a point, the verdict must say the margin is inside "
        "the cross-check's own uncertainty and recommend the next rung out. (7) DEPOSITS SOFTEN "
        "EVERY WORST FALL HERE ALIKE and no figure may be lined up against an unfunded trial. "
        "(8) THE RECOMMENDATION IS ABOUT WIDTH AND NOT ABOUT WHETHER TO HOLD THIS BOOK AT ALL. "
        "M0007 is test-failed and so is this book's lineage; nothing here says the roster's "
        "picking rule works. It says only that IF the owner holds it, holding it in twenty slots "
        "is the worst of the available widths on the only history that contains the failures."
    ),
    candidates=(
        _v("N25", 25, "Twenty-five names: the first rung past the roster, and the test of whether the "
                      "protection arrives gradually or in one step"),
        _v("N30", 30, "Thirty names: the rung predicted to clear the owner's fall bar with a cushion at "
                      "no return cost on the check store"),
        _v("N45", 45, "Forty-five names: prices the steep return decay between 35 and 50, and says "
                      "whether anything is still being bought past 35"),
    ),
    seen_keys=(
        "concept:residual-momentum-name-count",
        "concept:book-width-read-on-the-survivorship-check-store",
        "concept:roster-width-rungs-between-twenty-and-fifty",
    ),
)
