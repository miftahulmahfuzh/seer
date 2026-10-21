"""M0270 -- The price of idle cash is a curve, not a slope: map it before drawing another control.

Source: variation of M0266, which measured the slope of return against exposure for the first time
and, in doing so, found two things that invalidate an assumption the lab has been making silently
for months. M0127 supplies the band rungs; M0109 the deliberately neutral 50-name base book.
Insight 527 is the statement that the lab has no basis for any exposure tolerance at all.

WHAT PROMPTED THIS, AND WHY IT IS A CORRECTNESS JOB RATHER THAN A SEARCH FOR AN EDGE. M0266 held
exposure fixed on both sides of a comparison so that only the trimming moved, and it needed a
ruler to do it: two arms identical in everything but how much of the account they left in cash.
That ruler priced A POINT OF BEING INVESTED, and nobody had ever measured that number before.

  * On the dev store it came out at 0.0661 points a year of money-weighted return, and 0.4212
    points of worst fall, per point of the account left out of the market, over the 78.5%-to-88.6%
    range (arms ``M0266-L`` and ``M0266-LS``, trials 892 and 897).
  * On the survivorship-check store the IDENTICAL scale step over the 79.9%-to-89.4% range was
    worth 0.0078 points a year. The same book, the same dates, the same cash step: a factor of
    EIGHT smaller. The worst-fall slope, meanwhile, held up at about 0.61.
  * Inside the dev store the top of the range is visibly steeper than the bottom. The band-0 pair
    ``M0266-T00`` and ``M0266-T00M`` spans 88.7% to 98.6% and implies 0.0596 points per point;
    the loose pair spans 78.5% to 88.6% and implies 0.0661. On the check store the same arithmetic
    at the top implies roughly 0.05 against 0.0078 measured at the bottom -- a six-fold bend
    inside one book.

Two things follow and both are bad for work already done. FIRST, every exposure-matched control
this lab draws assumes return is a straight line in exposure, and the line is bent -- that
includes the matched arms M0266 itself used and every control drawn that way in future. SECOND, a
cash buffer sized on one copy of the price history DOES NOT stay sized on another: M0266's
calibration held to 0.12 points on dev against a half-point tolerance and left its matched arms
0.90 and 0.75 points UNDER the control on the check store, past tolerance, so M0266 published NO
split for that store. That refusal was the right call and it is the standard this method is held
to. The deliverable here is the tolerance that refusal had no basis to choose.

Nothing here is a candidate. The base book holds the fifty most-traded index members at equal
weight with no gate, no brake and no stock picking; every version of it loses to a deposit-matched
SPY and falls more than 50%, twice the owner's limit. This is a ruler being calibrated.

-------------------------------------------------------------------------------------------------
THE DESIGN

Six arms, one dial. M0266's allocator byte for byte -- subclassed, not re-implemented, so the two
cannot drift apart -- under a new allocator id so that the digests are distinct. M0127's band of
zero on EVERY arm. The only field that moves between arms is ``scale``, the multiplier on every
target weight, and the only thing that changes with it is how much of the account the book
deliberately leaves in cash.

  scale   1.00   0.94   0.88   0.82   0.76   0.70

Six round numbers, evenly spaced 0.06 apart, spanning 70% to 100% of full weight. They are ROUND
NUMBERS and not derived from any recorded exposure, because here the exposure is the x axis rather
than something to be matched. Even spacing is deliberate: uneven rungs invite a reader to see
curvature that is really an artefact of where the rungs were put.

WHY BAND 0 ON EVERY ARM AND NOT THE LOOSE BAND. The idea row that reserved this id called for the
loose equity-basis band throughout, so that the trimming channel would be switched off. The
purpose of that instruction is that the trimming must be held CONSTANT across the ladder, and band
0 serves it equally well: every arm trims identically, on every month start, at every rung. What
the loose band cannot do is reach the part of the curve that matters. Under the loose band a
deposit can open a new holding but can never top up an existing one, so idle cash accumulates and
the book settles at 88.6% invested AT FULL WEIGHT -- that is its ceiling, and scaling only moves
it down. The bend M0266 detected lives between 88.6% and 98.6%, and real books live there too.
A loose-band ladder over scales 0.70 to 1.00 would map 58% to 88% and would miss the bend entirely
and by construction. Band 0 makes realised exposure track the scale closely and puts the top rung
exactly where the question is. The deviation is recorded here, in the pre-registration commit,
with its reason, and it costs nothing that the idea row was buying: M0266 already measured the
trimming channel at matched exposure on dev at -0.10 points a year, near enough to zero that the
two chassis sit on top of each other in level, and M0266's loose-band pair stands as the
external cross-check on the bottom of this ladder.

THERE IS NO CALIBRATION, AND THAT IS THE POINT. M0266's buffer was computed to HIT a target
exposure measured on one store, and that is exactly what failed to transfer. This method aims at
no exposure at all. The scales are fixed; the realised exposure is READ, per store, and each
store's curve is drawn against its own realised x values. A design that never aims at an exposure
cannot fail to transfer one, so the pre-registered answer to "what will you do if the calibration
does not transfer to the second store" is that the question has been designed out. What replaces
it is an x-axis sanity check, below, which can fail and which would stop the analysis.

-------------------------------------------------------------------------------------------------
THE TWO HYPOTHESES THE LADDER DISTINGUISHES, WRITTEN BEFORE ANY RETURN IS COMPUTED

The lab's current practice assumes ADDITIVE linearity: return(x) = a + s*x with s a constant of
the book, so a control one point off may be corrected by subtracting s. The arithmetic that
produced M0266's two routes to a split is this assumption and nothing else.

The competing shape is MULTIPLICATIVE, a straight line through the ORIGIN: return(x) = x * r,
where r is what the fully invested book earns, because money in cash earns nothing and the
portfolio is a weighted blend of the book and zero. Under that shape the slope is not a constant
of the lab at all; it is a property of each book, equal to its own return per unit of exposure,
and a control must be corrected by DIVIDING by exposure rather than by subtracting a slope.

  Multiplicative predicts the dev slope at 6.95 / 0.9857 = 7.05 points per unit = 0.0705 per
  point, against 0.0596 measured on the band-0 pair and 0.0661 on the loose pair -- close, and
  slightly over-predicting, which would make the curve faintly concave.

  Multiplicative predicts the check store's slope at 4.17 / 0.894 = 0.0466 per point, against
  0.0078 measured. It is wrong there by a factor of six, and that gap is the single most
  interesting number M0266 left behind.

THE THIRD SHAPE, AND MY ACTUAL PRIOR. Cash is not merely a drag; on a violent book it is also a
brake, and a funded book with monthly deposits is paid for being less violent through the sequence
of its returns. The same book falls 57% on the dev store and 72% on the check store. So my prior
is that the slope is the book's return per unit of exposure MINUS what the cash buys back in
smoothness, that the second term grows with the book's violence, and that this is why the honest
tape's slope nearly vanished while its worst-fall slope did not. If that is right, the slope is a
property of the BOOK AND ITS TAPE jointly, no constant may be carried between stores or between
books, and the only safe control is one matched on exposure rather than corrected for it.

-------------------------------------------------------------------------------------------------
WHAT IS PREDICTED, IN NUMBERS, BEFORE ANY RESULT

 1. THE X AXIS IS SOUND. Realised average exposure is strictly decreasing in scale on both stores,
    and on dev each rung lands within 0.5 of a point of scale * 0.9857 (the recorded exposure of
    ``M0266-T00``, which is this ladder's top rung in all but its allocator id): 98.6, 92.7, 86.8,
    80.9, 74.9, 69.0. If exposure is not monotone in scale, the x axis is broken and NOTHING below
    may be read; the analysis would report that and stop.
 2. THE TOP RUNG REPRODUCES M0266-T00 TO THE DIGIT on dev -- same total return, same worst fall,
    same profit factor, same 1338 trades -- because the subclass changes only the allocator's id.
    A mismatch is a bug and must be chased before anything else is read.
 3. THE CURVE IS READABLE ON DEV AND MARGINAL ON THE CHECK STORE. At a dev slope near 0.06 the
    rungs are about 5.9 points of exposure apart, so adjacent arms should differ by roughly 0.35
    points a year -- comfortably larger than any path jitter. On the check store, at the 0.0078
    measured at the bottom, adjacent arms would differ by 0.05 points a year, which path effects
    can swamp. I expect at least one sign flip between consecutive rungs on the check store and
    none on dev.
 4. THE CURVE IS CONVEX ON DEV: the top rung pair is steeper than the bottom rung pair, because
    the lost compounding of a cash buffer is worth more when more of the book is working. M0266's
    two pairs point the other way by a hair (0.0596 at the top against 0.0661 at the bottom) but
    they are measured on two different bands, which is exactly the confound this ladder removes.
    I am recording the prediction against the existing evidence on purpose: if it is wrong, this
    file says so afterwards.
 5. THE WORST FALL IS THE WELL-BEHAVED AXIS. Worst fall against exposure should be close to a
    straight line on both stores, at about 0.42 points per point on dev and 0.61 on the check
    store, because a cash buffer de-risks mechanically and in proportion. If return is bent and
    fall is straight, then an exposure-matched control is far safer as a safety claim than as a
    return claim, and that asymmetry is itself the finding.
 6. TURNOVER FALLS WITH SCALE AND FEES RISE AS A SHARE OF EQUITY. A scaled-down book places
    smaller orders and pays Gotrade's per-order minimum on more of them, so cost per unit of
    equity rises as exposure falls. That bends the bottom of the curve DOWN independently of any
    market effect, and the analysis must quote turnover beside return so a fee artefact is not
    read as a market one.
 7. NO ARM IS A CANDIDATE. The base book loses to a deposit-matched SPY and falls past 50%; the
    scale field has no preset and no resolver entry, so every arm is unpromotable by construction.
    Eligibility here would be reported and would still not be promoted.

THE DELIVERABLE, DEFINED NOW SO IT CANNOT BE CHOSEN AFTERWARDS. Fit the global straight line
through the six points of each store. For every pair of rungs, compare the return difference the
global line predicts with the one measured. The published tolerance is the largest exposure gap
over which that error stays under 0.10 points a year -- a tenth of a point, chosen because that is
the precision M0266 quoted its split to and because insight 527 says the lab has no basis for any
figure at all today. If consecutive local slopes disagree in SIGN on the dev store, no tolerance
is published and the deliverable becomes the opposite instruction: match exposure exactly, do not
correct for it.

-------------------------------------------------------------------------------------------------
TRAPS ON THIS HOST, ALL PREVIOUSLY MEASURED

  * TRADE COUNT IS A DEAD METER HERE (insight 495). M0127's five arms and M0266's six all recorded
    an IDENTICAL 1338 trades while idle cash moved from 11.4% to 1.4%. The resize legs fold into
    the ranking's own orders and the counter cannot see them. Read EXPOSURE and TURNOVER only.
  * A RATIO ACROSS TWO STORE VINTAGES IS NOT A COMPARISON (insight 482). All six arms load each
    store once and run in one sweep, so every within-store difference is clean by construction,
    and ``store_fingerprint`` is printed for both stores beside every number.
  * A CONTROL MATCHED ON TRADES AND TURNOVER IS STILL NOT RETURN-NEUTRAL (insight 479). This
    method is the measurement of how far that goes for exposure, and claims nothing wider.
  * INSIGHT 528 SUPERSEDES 494: at matched exposure the trimming makes the fall SHALLOWER, not
    deeper. The old mechanism story -- rebalancing buys the faller so it falls deeper -- is
    measured false and is not inherited here.
  * THE BAND LEVER IS ``TradeRules.resize_band`` through the post-pins ``LEVERS_SINCE_PINS`` path.
    It is reused from M0127, not duplicated: ``T00`` is imported.
  * NO ARM REVERSES ANOTHER, so the lab's no-opinion-arm rule does not bite. A dose-response
    ladder is its own control: six rungs of one dial, each the others' reference, and a shape that
    cannot be produced by a lucky draw the way a single pair can.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0127_slot_relative_resize_band import T00
from seer_engine.lab.methods.m0266_exposure_matched_rebalance import (
    ScaledBandParams,
    ScaledMostTradedEqualWeight,
)
from seer_engine.sim.rules import TradeRules

ADDED = date(2026, 10, 21)

#: The band every arm runs: zero, so every holding is traded back to its slot on every month
#: start. Imported from M0127 rather than re-declared, so the two methods cannot drift apart.
#: Constant across the whole ladder, which is what leaves ``scale`` as the only moving part.
BAND: TradeRules = T00

#: The ladder. Six round numbers, evenly spaced 0.06 apart, spanning 70% to 100% of full weight.
#: Fixed here before any return was computed, and chosen on round numbers rather than on any
#: recorded exposure, because exposure is the axis being measured rather than a thing to match.
SCALES: tuple[Decimal, ...] = (
    Decimal("1.00"),
    Decimal("0.94"),
    Decimal("0.88"),
    Decimal("0.82"),
    Decimal("0.76"),
    Decimal("0.70"),
)

#: ``M0266-T00``'s recorded average exposure on the dev store (trial 893), the one number used to
#: PREDICT where the rungs land. It is a prediction and not a calibration: no arm's scale is
#: derived from it, and the realised exposures are read per store rather than aimed at.
EXPOSURE_AT_FULL_WEIGHT = Decimal("0.9856884609713539")


class ExposureLadderBook(ScaledMostTradedEqualWeight):
    """M0266's allocator exactly, under a new id so the ladder's digests are distinct.

    Subclassed rather than copied on purpose. ``config_text`` identifies a trial by its rules, its
    allocator **id** and its params, so the id alone separates this ladder's top rung from
    ``M0266-T00`` in the database while guaranteeing -- by inheritance, not by inspection -- that
    the two compute byte-identical targets. That is what makes prediction 2 a real check: if the
    top rung does not reproduce trial 893 to the digit, something outside this file moved.
    """

    id = "M0270"


BOOK = ExposureLadderBook()


def _v(scale: Decimal) -> Candidate:
    pct = int(scale * 100)
    predicted = scale * EXPOSURE_AT_FULL_WEIGHT * 100
    return Candidate(
        id=f"M0270-S{pct:03d}",
        family="M0270",
        rules=BAND,
        allocator=BOOK,
        params=ScaledBandParams(scale=scale),
        rationale=(
            f"Rung {pct}% of full weight; predicted average exposure {predicted:.1f}% on the dev "
            f"store"
        ),
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0270",
    name=(
        "The price of idle cash is a curve, not a slope: map it before drawing another "
        "exposure-matched control"
    ),
    family="portfolio-rebalancing",
    source_kind="variation",
    source_ref=(
        "M0266, which priced a point of being invested for the first time and found the number "
        "eight times smaller on the survivorship-check store than on the dev store over the same "
        "range, and whose own exposure calibration failed to transfer between the two; M0127 for "
        "the band rungs; M0109 for the neutral 50-name base book; insight 527, which says the lab "
        "has no basis for any exposure tolerance at all"
    ),
    parent_id="M0266",
    hypothesis=(
        "Every exposure-matched control this lab draws assumes return is a straight line in how "
        "invested a book is, and M0266 measured that line for the first time and found it bent. "
        "Its ruler priced a point of the account left out of the market at 0.0661 points a year "
        "of money-weighted return on the dev store over the 78.5-to-88.6 percent range, and at "
        "0.0078 on the survivorship-check store over the 79.9-to-89.4 percent range -- the same "
        "book, the same dates, the same cash step, a factor of eight apart -- while the worst-fall "
        "slope held up at 0.42 and 0.61. Inside the dev store the top of the range is already "
        "visibly steeper than the bottom. So map the curve rather than assume it. Six arms, one "
        "dial: M0266's allocator subclassed unchanged under a new allocator id, M0127's band of "
        "zero on every arm so the trimming is held constant throughout, and six target-weight "
        "scales fixed on round numbers at 1.00, 0.94, 0.88, 0.82, 0.76 and 0.70, evenly spaced "
        "0.06 apart. THERE IS NO CALIBRATION AND THAT IS THE DESIGN: M0266's buffer was computed "
        "to hit an exposure measured on one store and that is precisely what failed to transfer, "
        "so this ladder aims at no exposure at all. The scales are fixed, the realised exposure is "
        "read per store, and each store's curve is drawn against its own x values, which means a "
        "transfer failure cannot occur by construction. Band zero rather than the loose band "
        "because the loose band caps exposure at 88.6 percent at full weight and therefore cannot "
        "reach the 88.6-to-98.6 percent stretch where M0266 found the bend and where real books "
        "live. The ladder distinguishes two shapes: the additive straight line the lab assumes "
        "today, where a control one point off may be corrected by subtracting a constant slope, "
        "and a line through the origin, where return is simply exposure times what the fully "
        "invested book earns and a control must be corrected by dividing rather than subtracting. "
        "The second predicts 0.0705 per point on dev against 0.0596 measured, and 0.0466 on the "
        "check store against 0.0078 measured, so it is close on one store and wrong by six times "
        "on the other. My actual prior is a third shape: the slope is the book's return per unit "
        "of exposure minus what cash buys back in smoothness, the second term grows with the "
        "book's violence, and that is why the honest tape's return slope nearly vanished while "
        "its worst-fall slope did not -- the same book falls 57 percent on one store and 72 on "
        "the other. PREDICTIONS, written now. (1) Realised exposure is strictly decreasing in "
        "scale on both stores and lands on dev within half a point of 98.6, 92.7, 86.8, 80.9, "
        "74.9 and 69.0 percent; if it is not monotone the x axis is broken and nothing may be "
        "read. (2) The top rung reproduces M0266-T00 to the digit on dev, because the subclass "
        "changes only the allocator id. (3) The curve is readable on dev, where adjacent rungs "
        "should differ by about 0.35 points a year, and marginal on the check store, where they "
        "would differ by 0.05; at least one sign flip between consecutive rungs is expected there "
        "and none on dev. (4) The curve is convex on dev, the top pair steeper than the bottom "
        "pair, against M0266's two pairs which point the other way by a hair on two different "
        "bands. (5) Worst fall against exposure is close to straight on both stores, near 0.42 "
        "and 0.61 points per point, so an exposure-matched control is far safer as a safety claim "
        "than as a return claim. (6) Turnover falls with scale while fees rise as a share of "
        "equity, because a smaller book pays the per-order minimum on more of its orders, which "
        "bends the bottom of the curve down for a reason that is not a market reason. (7) No arm "
        "is a candidate: the base book loses to a deposit-matched SPY and falls past 50 percent, "
        "and the scale field has no preset, so every arm is unpromotable by construction. THE "
        "DELIVERABLE, defined now so it cannot be chosen afterwards: fit the global straight line "
        "through each store's six points, compare every rung pair's measured return difference "
        "with the one that line predicts, and publish as the tolerance the largest exposure gap "
        "over which the error stays under 0.10 points a year. If consecutive local slopes "
        "disagree in sign on the dev store, no tolerance is published and the deliverable becomes "
        "the opposite instruction: match exposure exactly rather than correct for it. Fractional "
        "shares, Gotrade's real fees, the owner's funding plan. Success is a measurement."
    ),
    expected_failure=(
        "The likeliest failure is that the curve is too noisy to read on the survivorship-check "
        "store, and I am expecting it rather than hoping against it. At the 0.0078 points a year "
        "per point M0266 measured there, consecutive rungs six points of exposure apart differ by "
        "0.05 points a year, which is the same size as the path jitter between two books that "
        "hold the same names in different amounts through 2008. If consecutive rungs disagree in "
        "sign on that store, the honest reading is not that the curve bends in some interesting "
        "way but that there is no usable curve there at all, and the published answer must then "
        "be that an exposure-matched control on the honest tape has to match exactly, because "
        "nothing in the record supports correcting for a gap of any size. The second failure is "
        "the same thing on dev, which would be worse and would mean five rungs over thirty points "
        "of exposure on one book are five points rather than a function; in that case the method "
        "publishes no tolerance and says the lab must match exposure exactly. The third is that "
        "the whole shape turns out to be the fee schedule rather than the market: a book at 70 "
        "percent of full weight places orders 30 percent smaller and pays Gotrade's per-order "
        "minimum on a larger share of them, so the bottom rungs are penalised for a reason that "
        "has nothing to do with being out of the market, and if the bend sits entirely in the "
        "cost column then this is a measurement of a 20,000,000 IDR account's order economics and "
        "the verdict must say so rather than dress it as a market finding. The fourth is paths "
        "again, the caveat M0266 carried and this method inherits: every rung holds its buffer as "
        "a deliberate near-constant share re-set monthly, which is not the shape of the drifting "
        "idle cash a real book carries, so the curve prices a DELIBERATE buffer and may not "
        "transfer to a book whose cash is an accident. The fifth is that the dev and check stores "
        "disagree so completely that no single sentence covers both, in which case the "
        "deliverable is per-store and the lab must be told plainly that it may not carry an "
        "exposure correction from one copy of the history to another -- which is already the "
        "lesson M0266 paid for once. The sixth is that the ladder confirms the straight line "
        "everyone assumed, over the whole thirty points, on both stores. That would be a dull "
        "result and a genuinely useful one, and it must be reported with the same emphasis as a "
        "bend rather than buried as a non-finding."
    ),
    candidates=tuple(_v(s) for s in SCALES),
    seen_keys=(
        "concept:exposure-return-curve-ladder",
        "concept:price-of-a-point-of-exposure",
        "concept:exposure-matched-control-tolerance",
    ),
)
