"""M0306 — Finish the gated coin: take the switch-on draw population from seven to nineteen.

Source: variation of M0296 (the blind-draw spread for the industry lead-lag book). The question
is the lab's own, and it is a question about the lab's instruments rather than about the market.

**What M0296 bought, and the hole it left.** M0296 ran nineteen identical rules that differed in
nothing but a coin toss — three industries drawn blind from a hash of the seed, the industry name
and the month, twenty equal slots split 7/7/6, members taken in a fixed opinion-free order,
fractional shares at Gotrade's real fees on the owner's monthly deposits. Read together with
``M0295-MATCHED-T3-NOGATE`` (seed 1, recorded), those nineteen draws gave the lab its first
measured error bar: money return on the owner's deposits spanning 1.53% to 9.06% a year, worst
fall spanning 49.0% to 69.7%, worst year spanning −23.5% to −55.0%, turnover 20.58 to 21.44 and
trades 4,011 to 4,120. That is the number every shape-matched control in the lab's record has
been read against since.

**But every one of those nineteen was always invested, and that is not the chassis the lab
uses.** ``inner=OPEN`` turns the SPY 200-day switch off. Every near miss on the leaderboard keeps
it on, and the switch is exactly what flattens the fall: M0295's four gated arms fall 27.6% to
33.9% where its two switch-off arms fall 58.1% and 59.9%. An error bar measured on a chassis that
falls sixty percent is being applied, daily, to books that fall thirty.

**What this file registers, and why it is not what the reserved idea row said.** The idea row
asked for six gated draws, seeds 2 through 7, and allowed an amendment to nineteen "if the first
seven leave the question open". Seeds 2 through 7 are gone: M0307, a sibling exploration started
minutes before this one and parented to the same M0296, registered and ran the identical six
configurations, and ``lab run`` refused this method's first block as a repeat of
``M0307-GDRAW-S2``. That refusal recorded nothing — M0306 held no trial, no amendment and no
source sha when this file was rewritten — so this pre-registration is being written before any
result of its own exists, which is the only condition the freeze cares about. The duplication is
noted here rather than hidden, because a reader comparing the two files deserves to know which
seeds came from which run.

So the six slots move to **seeds 8 through 13**, the amendment to **seeds 14 through 19**, and
what M0306 contributes is the thing M0307 could not: the other twelve draws. The gated population
then reads

    M0295-MATCHED-T3  (seed 1, recorded by M0295)
  + M0307-GDRAW-S2 .. S7   (seeds 2-7, recorded by M0307)
  + M0306-GDRAW-S8 .. S19  (seeds 8-19, this method)
  = nineteen gated draws, on the same engine, differing only in the seed.

**Why that completion is the whole point, and not a tidying-up.** The range of a sample grows
with the size of the sample. The spread of seven draws from a fixed distribution is
systematically narrower than the spread of nineteen draws from that same distribution, by a wide
margin and with no exceptions. The comparison both M0307 and this method exist to make is gated
spread against switch-off spread, and the switch-off spread is a **nineteen**-draw range. Reading
a seven-draw gated range beside it finds the gated chassis "narrower" even when the two
distributions are identical: it manufactures the conclusion out of sample size alone. M0307's own
pre-registered expected failure names this exactly — "seven gated draws may land so close
together that the measured range is dominated by whichever single seed happens to sit furthest
out, in which case this buys a lower bound on the gated width rather than the width". M0306 is
what turns that lower bound into the width, and it is the only way the two spreads can be put
side by side without the sample size deciding the answer. Nineteen against nineteen, seed for
seed, on the same hashes.

**The null this method is really testing, written as a number.** The switch does not depend on
the seed. Every gated draw sits in cash in exactly the same months as every other gated draw,
because they all read the same SPY 200-day average; they differ only in what they hold while they
are invested. M0295's gated arms show exposure 0.694 against 0.964 for the switch-off arms. So
the dullest possible explanation of any narrowing is **dilution by time invested**: the draws
have 72% as much time in which to differ, so they should differ by about 72% as much.

    exposure ratio = 0.694 / 0.964 = 0.720

That is the pre-registered null, and it makes the result readable instead of merely descriptive:

  * a gated-to-switch-off spread ratio near **0.72** on the money return means the switch buys no
    narrowing at all beyond holding the book out of the market, and the gated error bar can be
    obtained from the switch-off one by multiplying — no new measurement needed, ever;
  * a ratio **well below 0.72** on the worst fall means the switch genuinely clips the tail that
    separates a lucky draw from an unlucky one, and the lab has been using a ruler far too wide
    for every gated comparison it has made;
  * a ratio **above 0.72** means the switch *amplifies* seed noise — plausible, because a book
    that steps in and out re-enters on a seed-dependent set of names at seed-independent moments,
    and the lab would then have been using a ruler too narrow.

**What the deliverable is, and what it is not.** Success is not a strategy. No arm here is
expected to be dev-eligible and none is designed to be: each is a placebo by construction, with
no opinion in it anywhere. The deliverable is six numbers — the gated spread in money return,
worst fall, worst year, gains-to-losses, turnover and trades, measured on all nineteen draws —
and the ratio of each to M0296's switch-off spread. Two readings come free. The first is how far
the seven-draw gated range understated the nineteen-draw one, which is the correction factor
every future short draw population in this lab will need. The second is the rank of M0295's gated
idea arm ``M0295-FOLLOW-T3`` inside its own nineteen-draw gated population, which M0295's verdict
("a blind draw beat following the biggest name's lead") asserted against a single draw and could
not then calibrate.

**The reading rule, fixed here before any arm runs.** Report every seed. No seed is dropped for
any reason, none is added beyond nineteen, and no window other than the full dev window and the
2009-2015 slice is read. The spread statistic is the plain range, min to max, because that is the
statistic M0296 published and the two must be comparable; the standard deviation is reported
beside it because the range is the more sample-size-sensitive of the two and a reader deserves
both. The seven-draw-versus-nineteen-draw correction is computed from this method's own draws, by
reading the first seven of the gated population and then all nineteen, so it is measured rather
than assumed. The ranks are reported whatever they are.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits, identical to M0296's draws, to M0307's draws, and to the two M0295 arms this is
read against. Pure: the engine is M0295's, which reads only bars dated at or before d and has no
clock, randomness, file or network of its own.

Assumptions, written before the run:

1. A seed is an arbitrary label. Seeds 8-19 are as good a sample of "a blind three-industry
   gated draw" as any other twelve would be, and the seven gated trials already recorded by
   M0295 and M0307 belong in the same population as the twelve run here. The key is blake2b of
   the seed, the industry name and the month; nothing gives any seed a privileged position.
2. Pooling across method ids is sound because the configurations are identical in every field
   but the seed and were produced by the same imported allocator object at the same store
   fingerprint. The lab's digest ignores the candidate id for exactly this reason.
3. Using the *same* nineteen seeds as M0296 pairs the two populations draw for draw, so the
   comparison can be read as nineteen matched pairs as well as two independent spreads. That is
   strictly more information than independent seeds would have given, and it costs nothing.
4. The family is ``stock-portfolio-construction``, as the reserved idea row set it, rather than
   M0296's ``stock-industry-lead-lag`` or M0307's ``market-shape-yardstick``. Every arm here is a
   hash draw with no lead-lag opinion in it, so what it varies is construction, not a signal. The
   kin rule reads behaviour rather than the family string, so nothing in the hard gate turns on
   this choice.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0295_industry_bellwether_lead_lag import (
    GATED,
    LEADLAG,
    LeadLagParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 23)

#: The seeds this block spends. 1 is already recorded as ``M0295-MATCHED-T3`` and 2-7 as
#: ``M0307-GDRAW-S2..S7``; re-running any of them would measure one configuration twice.
SEEDS = (8, 9, 10, 11, 12, 13)


def _draw(seed: int) -> Candidate:
    return Candidate(
        id=f"M0306-GDRAW-S{seed}",
        family="M0306",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=LEADLAG,
        params=LeadLagParams(inner=GATED, industries=3, side="matched", leader="largest",
                             seed=seed),
        rationale=(
            f"gated blind draw {seed} of nineteen: three industries drawn in hash order, the "
            "same 7/7/6 split, the same opinion-free member order, and the SPY 200-day switch "
            "ON — M0296's draw seed on the chassis the lab's near misses actually use, "
            "differing from that draw in one field and from the other gated draws in one field"
        ),
        added=ADDED,
        owner_inputs=(),
    )


# --------------------------------------------------------------------------- amendment

#: Seeds 14-19 take the gated population to nineteen, matching M0296's switch-off population
#: seed for seed. Pre-registered by the commit that adds it, **before** either block is run, and
#: read by the one rule in this file's docstring. It is a separate block only because a batch
#: carries at most six variants.
AMEND_1_SEEDS = (14, 15, 16, 17, 18, 19)

AMEND_1 = Amendment(
    added=ADDED,
    why=(
        "The second half of one widening, pre-registered in the same commit as the first and "
        "before either runs. The range of a sample grows with the size of the sample, so a "
        "gated population smaller than M0296's nineteen switch-off draws cannot be compared "
        "with them: it would read narrower even if the two distributions were identical. "
        "Thirteen gated draws is not nineteen, and stopping at thirteen would leave the "
        "comparison exactly as unreadable as stopping at seven did. Splitting the twelve into "
        "two blocks is a batch-size limit and nothing else; the reading rule is unchanged and "
        "admits no choices, because every seed from 8 to 19 is run and reported whatever it "
        "does."
    ),
    hypothesis=(
        "The gated spread measured on all nineteen draws is materially wider than the same "
        "spread measured on the first seven, by enough that the seven-draw reading would have "
        "misstated how much the switch narrows the coin. Under the exposure-dilution null the "
        "nineteen-draw gated spread should sit near 0.720 of M0296's nineteen-draw switch-off "
        "spread on the money return, and clearly below 0.720 on the worst fall."
    ),
    expected_failure=(
        "Seeds 14-19 land inside the range the first thirteen already covered, the measured "
        "spread stops widening, and the nineteen-draw gated bar turns out to be the "
        "thirteen-draw bar — which would mean three industries drawn from roughly ten eligible "
        "ones overlap so heavily that the draw population saturates, and that the honest gated "
        "error bar is a lower bound no matter how many seeds are spent."
    ),
    candidates=tuple(_draw(s) for s in AMEND_1_SEEDS),
)

_EXP = (
    "The expected failure is that the gated draws cluster so tightly on the fall — because the "
    "switch takes every one of them to cash in the same months, and the deepest part of every "
    "draw's 2008 is a month the switch sits out — that the fall spread comes out near zero and "
    "the SHAPE of the distribution rather than its width becomes the finding. That would be "
    "worth knowing on its own: it would mean the lab may read a fall difference between gated "
    "twins and may never read a return difference, and it would retire the worst fall as a "
    "discriminator between gated books. The second likely failure is the opposite and worse: "
    "the ratio lands near 0.720 on every meter at once, the switch turns out to be a pure "
    "exposure dial with no effect on draw noise beyond arithmetic, and these twelve runs will "
    "have bought a multiplication the lab could have done from M0296 for nothing. The third is "
    "that seeds 8-19 land inside the range M0307's seven already covered, so the population "
    "saturates and the gated bar is a lower bound however many seeds are spent — in which case "
    "the only safe ruler for a gated comparison remains the switch-off one, and the lab must go "
    "on treating every single-control claim as the one-in-two claim it is."
)


METHOD = Method(
    id="M0306",
    name="Finish the gated coin: the switch-on draw population from seven to nineteen",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref="M0296",
    parent_id="M0296",
    hypothesis=(
        "M0296 measured how far pure chance moves a twenty-name three-industry book re-picked "
        "monthly at real fees, and the answer was large: nineteen identical rules differing "
        "only in a coin toss spanned 7.5 points a year of money return on the owner's deposits, "
        "20.7 points of worst fall and 31.5 points of worst year, while trades varied 2.7 "
        "percent and turnover 4.1 percent. Every one of those nineteen was ALWAYS INVESTED, and "
        "that is not the chassis the lab uses. Every near miss on the leaderboard keeps the SPY "
        "200-day switch, and the switch is what flattens the fall: M0295's gated arms fall 27.6 "
        "to 33.9 percent where its switch-off arms fall 58.1 and 59.9. M0307 began the gated "
        "half of this measurement and got seven draws into it. Seven is not enough to put "
        "beside nineteen, because the range of a sample grows with the size of the sample: a "
        "seven-draw gated range read against a nineteen-draw switch-off range comes out "
        "narrower even when the two distributions are identical, which is the very conclusion "
        "the measurement is supposed to be able to refute. This method runs the missing twelve "
        "— M0295's engine with inner=GATED, side=matched, leader=largest, three industries, "
        "seeds 8 through 19 — so the gated population reaches nineteen and can be read against "
        "M0296's nineteen seed for seed. The pre-registered null is dilution by time invested: "
        "the gated arms hold exposure 0.694 against 0.964, so if the switch does nothing but "
        "keep the book out of the market the spread ratio should be 0.720 on every meter. The "
        "hypothesis is that the worst-fall ratio comes in clearly below 0.720 while the "
        "money-return ratio sits near it, and that the nineteen-draw gated spread is materially "
        "wider than the seven-draw one. Success is not a strategy and no arm is expected to be "
        "eligible: the deliverable is the width of the ruler the lab has used on every gated "
        "comparison in its record, whether it can be derived from the one it already has, and "
        "how badly a short draw population understates it."
    ),
    expected_failure=_EXP,
    candidates=tuple(_draw(s) for s in SEEDS),
    amendments=(AMEND_1,),
    seen_keys=("concept:gated-draw-population-completed-to-nineteen",
               "concept:draw-population-size-correction",
               "concept:exposure-dilution-null-for-control-noise"),
)
