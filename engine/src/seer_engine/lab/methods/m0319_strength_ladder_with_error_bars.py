"""M0319 -- How much jumpiness must a book throw out before the honest tape pays it back? The
strength ladder, with error bars this time.

Source: variation of M0303 (itself a variation of M0293 / M0283). The question comes from the
lab's own record, not from a paper.

M0303 KILLED THE GENERAL CLAIM. It tested whether a filter declared SAFETY reads better on the
survivorship-check store than on the dev store while a filter declared RETURN reads worse, on six
versions of M0197-Y20-SW that each throw away one quarter of the scored pool. It failed: the two
declared-safety filters (drop the jumpiest quarter by 60-day realised volatility, drop the
thinnest-traded quarter) finished 11.8 points apart, surrounding both declared-return filters, and
four identical blind draws the parent method (M0293) had already registered at this same host --
seeds 293, 294, 295, 296, all dropping a quarter at random -- spread 7.71 points on the very same
meter. The whole ladder the idea was built on (2.37 points) sat inside that one coin's width.
"Reads better on the honest tape" tells you almost nothing about what a screen is FOR.

But three points in that twelve-version population escaped their own draws' range on the worst
fall AND earned more a year, and every one of them is a jumpiness measure at a serious dose: this
host's own VOL arm (drop the jumpiest quarter by 60-day realised volatility, fall 28.2% -> 21.1%,
a 7.10-point gain, +0.59 pts/yr, luck score 0.945 -> 0.969, M0303 trial #1065 against the dev
history and `lab survivorship M0303` for the honest-tape figure); M0293's HI50 (drop the jumpiest
HALF by market beta, fall 25.2% -> 19.6%, +0.68 pts/yr, M0293 trial #990); and, gate off, M0293's
HI25-NOSW (M0293 trial #994, fall improves 2.70 points against a same-strength blind floor of
+0.51, though it gives up 0.79 pts/yr). THE FLAW THIS MUST FIX, named in the idea row that
reserved this id: those three points use two different jumpiness measures (volatility, beta) at
two different strengths (a quarter, a half), so "a dose effect" has not been earned. A ladder
needs the measure held fixed while only the strength moves, and -- M0303's deeper finding -- every
rung needs its OWN same-strength draws, because a blind draw dropping half is not the control for
a screen dropping a quarter: how much you throw away is itself part of what is being measured.
Nobody had measured that before this run.

THE DESIGN. Hold the measure fixed at 60-day realised volatility (M0303's VOL, the only one of
the four opinionated M0303 arms that cleared its own draw) and move only the strength: a quarter,
a half, two thirds of the pool. Every arm is M0197-Y20-SW's chassis unchanged, at Gotrade's real
fees, the SPY 200-day switch left on for the reasons M0303 gave (every book this diagnostic will
ever be applied to is gated; M0303's own gate-on ladder was no narrower than its gate-off one).
The 25% rung of that ladder is NOT re-run here -- it already exists, for free, with a stronger
error bar than any new rung in this method can afford:

  * the 25%-strength VOL arm is M0303-VOL (trial #1065, dev maxDD 28.2%);
  * the 25%-strength no-drop reference is M0303-REF / M0293-REF / M0197-Y20-SW (trial #1063,
    bar for bar the same book), read from the record rather than re-run, exactly as M0303 read it;
  * the 25%-strength blind draw ALREADY has FOUR independent seeds on this identical host --
    M0293-BLIND25 (seed 293) and M0293-BLIND25-S2/-S3/-S4 (seeds 294, 295, 296), proved bar-for-bar
    identical to what this method's own machinery would produce at the same seed, because M0303's
    BLIND arm (seed 293) reproduced M0293-BLIND25 exactly using the same ``draw``/``drop_count``
    functions this file also imports. The 25% rung of the ladder therefore already carries a
    four-draw error bar; adding a fifth draw at 25% here would spend variants on the one rung that
    least needs them.

What this method registers is the two rungs that do NOT exist yet, each with its own fixed-measure
VOL arm and its own pair of same-strength blind draws: 50% (``VOL50``, ``DRAW50-A``, ``DRAW50-B``,
seeds 450/451) and 65% (``VOL65``, ``DRAW65-A``, ``DRAW65-B``, seeds 650/651). Six variants, the
most MAX_VARIANTS allows, and the idea row's own stated compromise ("run two strengths with two
draws each plus the no-drop reference, or run three strengths and add the draws by amendment") is
resolved as: two NEW strengths with two draws each, with the no-drop reference and the 25% rung's
own four-draw error bar both read from the existing record at no new cost. Two draws per new rung
is thinner than the four the lab already has at 25% -- named now, in expected_failure below, as
the method's own known limitation, with the amendment path open if the result is close enough that
more seeds would change the verdict.

The allocator, the params class and the drop/survivor machinery are M0303's own ``DROPMETRIC``,
``DropMetricParams`` and ``HOST`` objects, imported rather than copied -- exactly why M0303 itself
imported M0293's ``draw``/``drop_count`` rather than reimplementing them -- so that drop_frac=0.50
and drop_frac=0.65 run through the identical chassis that produced the 25% rung, with no risk of a
quietly different host, screen or cost model creeping in between method files. Reusing the same
``DropMetricAllocator`` object (id ``M0303``) is safe and precedented (M0033 reused M0011's
allocator object unchanged for the same reason): the lab's own check
(``test_lab_methods.py::test_each_allocator_id_is_one_object``) only refuses two DIFFERENT objects
sharing an id, and this is the same object; and because ``drop_frac`` differs from every recorded
M0303 configuration, every new candidate's config digest is new regardless of the shared id.

Success: the gain in worst fall (dev store minus survivorship-check store maxDD, the same sign
convention M0303 used) grows monotonically from the 25% rung (M0303-VOL, +7.10 already measured)
through 50% to 65%, and the 65% rung's gain sits outside the range its own two draws cover, on
both the fall and the funded return. Failure, likelier and still worth the id: the gain does not
grow with strength, or the top rung sits inside its own draws' range, in which case the two
pre-existing survivors (M0303-VOL and M0293-HI50) were two lucky draws out of the roughly three in
ten configurations that read better on the honest tape by chance (M0303's own 78-version census),
and the lab should stop quoting a survivorship-store gap as evidence that any single strategy is
safe.

Pure: every read is M0303's/M0197's -- bars dated <= data_date, the T10Y rows ``MarketSeries.upto``
returns for that date, the three F4 features the host already computes for that date, plus a hash
of the symbol. Market-aware (``market_fields = ("series",)``) for the same reason the host is.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0303_what_the_honest_tape_measures import (
    DROPMETRIC,
    HOST,
    DropMetricParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 23)


def _v(suffix: str, drop_frac: Decimal, metric: str, seed: int, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0319-{suffix}",
        family="M0319",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=DROPMETRIC,
        params=DropMetricParams(HOST, drop_frac=drop_frac, metric=metric, seed=seed),
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


HALF = Decimal("0.50")
TWO_THIRDS = Decimal("0.65")

METHOD = Method(
    id="M0319",
    name=(
        "How much jumpiness must a book throw out before the honest tape pays it back? The "
        "strength ladder, with error bars this time"
    ),
    family="stock-market-beta",
    source_kind="variation",
    source_ref=(
        "variation of M0303 (does a survivorship-store gap in worst fall tell safety from "
        "profit?), which found that the general claim fails but that dropping a large, fixed-"
        "measure slice of the jumpiest names (60-day realised volatility, or market beta) cleared "
        "its own blind draw at two different strengths of two different measures; this method "
        "holds the measure fixed at 60-day realised volatility and moves only the strength, with "
        "every new rung carrying its own same-strength blind draws"
    ),
    parent_id="M0303",
    hypothesis=(
        "M0303 found that a filter's label (safety or profit) does not predict whether it reads "
        "better once the dead companies are put back, and that the one ladder in its record that "
        "looked like a clean ordering (drop nothing, drop the calmest quarter, drop the jumpiest "
        "quarter, drop the jumpiest half) was 2.37 points wide against a 7.71-point coin measured "
        "on the same host. But three configurations in that same population -- all of them, "
        "without exception, a large dose of a jumpiness measure -- sat OUTSIDE their own draws' "
        "range and earned more a year: M0303-VOL (60-day realised volatility, drop a quarter, "
        "trial #1065), M0293-HI50 (market beta, drop a half, trial #990), and gate-off M0293-HI25-"
        "NOSW (market beta, drop a quarter, trial #994). Two different measures at two different "
        "strengths is not yet a dose-response ladder. THE TEST. Hold the measure fixed at 60-day "
        "realised volatility -- M0303's own VOL metric, already computed by the host's F4 screen "
        "and thrown away, so this method adds no new estimate -- and register two new strengths on "
        "the identical M0197-Y20-SW/Gotrade host, switch on: drop the jumpiest half (VOL50) and "
        "the jumpiest two thirds (VOL65) of the day's scored pool before the host ranks what is "
        "left. The pool is hundreds of F4-screened names deep at every strength tried here, so the "
        "book stays exactly 20 names, fully invested, in every arm; a drop changes WHICH names and "
        "never HOW MANY. Each new rung carries its own same-strength blind draw, not one but two, "
        "independent fixed per-symbol hashes (VOL50 against DRAW50-A/DRAW50-B at drop_frac=0.50; "
        "VOL65 against DRAW65-A/DRAW65-B at drop_frac=0.65) -- because M0303's central finding is "
        "that this meter has never had an error bar and a blind draw at one strength is not the "
        "control for a screen dropping a different amount. The 25% rung of the ladder is read from "
        "the existing record rather than re-run: M0303-VOL is the 25%-strength VOL arm, M0303-REF "
        "is the no-drop reference (bar for bar M0197-Y20-SW and M0293-REF), and M0293's four "
        "registered seeds at drop_frac=0.25 (BLIND25, BLIND25-S2, BLIND25-S3, BLIND25-S4 -- seeds "
        "293-296) are its same-strength draws, already proved bar-for-bar identical to this "
        "method's own machinery because M0303-BLIND reproduced M0293-BLIND25 exactly at seed 293 "
        "using the same drop/draw functions this file imports unchanged. That is a four-draw error "
        "bar on the bottom rung for free, stronger than either new rung in this method can afford "
        "within six variants. PREDICTION, written now: reading the change in worst fall from the "
        "dev store to the survivorship-check store (`lab survivorship`), positive meaning the book "
        "falls deeper once the dead companies are back, the gain rises monotonically across the "
        "three rungs -- 25% (+7.10, already measured), 50%, 65% -- and the 65% rung's gain sits "
        "outside the range its own two draws cover, on both the change in worst fall and the "
        "change in funded return. A monotone ladder whose top rung clears its own control is the "
        "dose-response result M0303 could not establish with two different measures; anything less "
        "closes the question M0303 opened."
    ),
    expected_failure=(
        "The likeliest failure, stated by M0303 itself: of 78 strategy versions measured on both "
        "tapes, roughly three in ten read better on either single meter by chance, and the three "
        "points this method is trying to turn into a ladder could simply be three instances of "
        "that same coin landing heads. Two draws per new rung is a thinner control than the four "
        "seeds already sitting under the 25% rung -- itself only barely enough, per M0303's own "
        "analysis, to bound a 7.71-point coin -- so a top rung that looks like it clears its two "
        "draws here may not clear a wider spread a third or fourth seed would reveal; if the result "
        "is close, the fix is an amendment adding more seeds at whichever strength is ambiguous, "
        "not a verdict on two draws alone. Second, strength and turnover are confounded by "
        "construction: dropping two thirds of the pool leaves a much smaller, more homogeneous "
        "candidate set than dropping a quarter, so the book may churn harder or hold a narrower "
        "slice of the index at 65% regardless of what volatility is doing, and a monotone-looking "
        "ladder could be a monotone turnover or concentration effect wearing a volatility label; "
        "the analysis must report each rung's turnover and the fraction of REF's holdings it still "
        "keeps, not only the fall. Third, at 65% the survivor pool is thin enough that the host may "
        "start running low on bond-like candidates in some years, pushing slots into SPY and "
        "changing exposure rather than selection; exposure must be read alongside the fall for "
        "every rung. Fourth, the SPY 200-day switch means the book sits in cash through most of "
        "the episodes where the missing companies actually died (2008, 2000-2002), so the whole "
        "ladder may be invisible here regardless of strength, exactly as M0303 named for its own "
        "arms -- this is accepted for the same reasons M0303 gave (every book this diagnostic will "
        "ever be applied to is gated; the gate-on ladder was no narrower than the gate-off one in "
        "the parent's own record). If none of the three rungs beats its own draws, or the gain does "
        "not rise with strength, the honest conclusion is that M0303's two survivors were noise, "
        "and the lab should retire the idea of reading a survivorship-store gap as safety evidence "
        "for any single strategy -- which is worth knowing and is why this is worth a method id "
        "even if it fails."
    ),
    candidates=(
        _v("VOL50", HALF, "vol-high", 293,
           "Drop the jumpiest half of the scored pool by 60-day realised volatility: the middle "
           "rung of the ladder, same measure as M0303-VOL at double the strength"),
        _v("DRAW50-A", HALF, "blind", 450,
           "A blind drop of the same half, seed 450: the middle rung's first same-strength draw"),
        _v("DRAW50-B", HALF, "blind", 451,
           "A blind drop of the same half, seed 451: the middle rung's second same-strength draw, "
           "so the control has a spread and not a point"),
        _v("VOL65", TWO_THIRDS, "vol-high", 293,
           "Drop the jumpiest two thirds of the scored pool by 60-day realised volatility: the top "
           "rung of the ladder, the deepest dose this chassis can take and still leave a pool"),
        _v("DRAW65-A", TWO_THIRDS, "blind", 650,
           "A blind drop of the same two thirds, seed 650: the top rung's first same-strength draw"),
        _v("DRAW65-B", TWO_THIRDS, "blind", 651,
           "A blind drop of the same two thirds, seed 651: the top rung's second same-strength "
           "draw -- the control the whole method's verdict turns on"),
    ),
    seen_keys=(
        "concept:dose-response-strength-ladder-with-matched-error-bars",
        "concept:survivorship-gap-as-a-safety-filter-diagnostic",
    ),
)
