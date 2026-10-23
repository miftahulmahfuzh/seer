"""M0306 — The same error bar, for the book that keeps its safety switch on.

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
falls sixty percent is being applied, daily, to books that fall thirty. Nobody has measured
whether it transfers, in which direction, or by how much — and the lab has no second instrument
to catch the mistake if it does not.

**What this file registers.** The identical population, on the gated chassis. Seeds 2 through 19
of M0295's engine with ``inner=GATED``, ``side="matched"``, ``industries=3``,
``leader="largest"`` — the same allocator object, the same params class, the same real fees, the
same deposits, differing from M0296's draws in exactly one field and from each other in exactly
one field. Seed 1 is **not** here: it is already recorded, as ``M0295-MATCHED-T3``, produced by
the engine this file imports, and re-registering it would run one configuration twice under a
renamed allocator — the thing the lab forbids and the reason ``config_digest`` ignores the
candidate id. So the gated draw population is ``M0295-MATCHED-T3`` plus the eighteen registered
here: **nineteen gated draws against nineteen switch-off draws.**

**Why nineteen and not the seven the idea row asked for, decided before any arm ran.** The idea
row reserved six draws and allowed an amendment to nineteen "if the first seven leave the
question open". They cannot do otherwise, and the reason is arithmetic rather than judgement:
**the range of a sample grows with the size of the sample.** The spread of seven draws from a
fixed distribution is systematically narrower than the spread of nineteen draws from that same
distribution, by a wide margin and with no exceptions. The comparison this method exists to make
is gated spread against switch-off spread, and the switch-off spread is a nineteen-draw range.
Reading a seven-draw gated range beside it would have found the gated chassis "narrower" even if
the two distributions were identical — it would have manufactured the paper's own conclusion out
of sample size, and the lab would have had no way to tell. So all three blocks are pre-registered
in this one commit, before any of them runs, and the comparison is nineteen against nineteen.
That costs nothing extra in method ids and removes every choice about when to stop.

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
worst fall, worst year, gains-to-losses, turnover and trades — and the ratio of each to M0296's
switch-off spread. A secondary reading comes free: the rank of M0295's gated idea arm
``M0295-FOLLOW-T3`` inside its own nineteen-draw gated population, whole window, which M0295's
verdict ("a blind draw beat following the biggest name's lead") asserted against a single draw
and could not then calibrate.

**The reading rule, fixed here before any arm runs.** Report every seed. No seed is dropped for
any reason, none is added beyond nineteen, and no window other than the full dev window and the
2009-2015 slice is read. The spread statistic is the plain range, min to max, because that is the
statistic M0296 published and the two must be comparable; the standard deviation is reported
beside it because the range is the more sample-size-sensitive of the two and a reader deserves
both. The ranks are reported whatever they are.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits, identical to M0296's draws and to the two M0295 arms this is read against.
Pure: the engine is M0295's, which reads only bars dated at or before d and has no clock,
randomness, file or network of its own.

Assumptions, written before the run:

1. A seed is an arbitrary label. Seeds 2-19 are as good a sample of "a blind three-industry
   gated draw" as any other eighteen would be, and seed 1's recorded gated trial belongs in the
   same population as the eighteen run here. The key is blake2b of the seed, the industry name
   and the month; nothing gives any seed a privileged position.
2. Using the *same* seeds as M0296 pairs the two populations draw for draw, so the comparison can
   be read as nineteen matched pairs as well as two independent spreads. That is strictly more
   information than independent seeds would have given, and it costs nothing.
3. The family is ``stock-portfolio-construction``, as the reserved idea row set it, rather than
   M0296's ``stock-industry-lead-lag``. Every arm here is a hash draw with no lead-lag opinion in
   it, so what it varies is construction, not a signal. The kin rule reads behaviour rather than
   the family string, so nothing in the hard gate turns on this choice.
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

#: The seeds this block spends. 1 is not here: it is already recorded, as ``M0295-MATCHED-T3``,
#: and re-running it would measure one configuration twice.
SEEDS = (2, 3, 4, 5, 6, 7)


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


# --------------------------------------------------------------------------- amendments

#: Seeds 8-13 and 14-19 take the gated population from seven draws to nineteen, matching
#: M0296's switch-off population exactly. Both blocks are pre-registered by the commit that adds
#: them, **before** any of the three blocks is run, and all three are read by the one rule in
#: this file's docstring. They are separate blocks only because a batch carries at most six
#: variants.
AMEND_1_SEEDS = (8, 9, 10, 11, 12, 13)
AMEND_2_SEEDS = (14, 15, 16, 17, 18, 19)

_WHY = (
    "The range of a sample grows with the size of the sample, and this method's whole purpose "
    "is to compare a gated spread against the nineteen-draw switch-off spread M0296 published. "
    "A seven-draw gated range read beside a nineteen-draw switch-off range would come out "
    "narrower even if the two underlying distributions were identical, which is precisely the "
    "conclusion the method is supposed to be able to refute. So the population is taken to "
    "nineteen, the same nineteen seeds, and the comparison is matched draw for draw as well as "
    "spread against spread.\n\n"
    "This block is pre-registered in the same commit as the first six and before any arm has "
    "run, so there is no result to have been tempted by. The reading rule admits no choices: "
    "every seed is run, every seed is reported, the statistic is the plain range with the "
    "standard deviation beside it, and the only windows read are the full dev window and the "
    "2009-2015 slice."
)

_HYP = (
    "The SPY 200-day switch narrows the spread of identical blind draws by more than its time "
    "out of the market accounts for. M0295's gated arms hold exposure 0.694 against 0.964 for "
    "its switch-off arms, so pure dilution by time invested predicts a gated-to-switch-off "
    "spread ratio of 0.720. The hypothesis is that the measured ratio on the worst fall comes "
    "in clearly below 0.720 — the switch clipping the tail that separates a lucky draw from an "
    "unlucky one — while the ratio on money return sits near 0.720, because the switch has no "
    "view on which names a draw picks while it is invested. If that holds, the lab may read a "
    "fall difference between gated twins at a much finer resolution than M0296's ruler allows, "
    "and must keep reading return differences at roughly M0296's resolution scaled by exposure."
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
    "exposure dial with no effect on draw noise beyond arithmetic, and this method's nineteen "
    "runs will have bought a multiplication the lab could have done from M0296 for nothing. The "
    "third is that the gated draws inherit M0296's shape so completely that the ranks of the "
    "gated idea arm and the switch-off idea arm inside their populations are identical, which "
    "would say the switch changes no comparison the lab has ever made."
)

AMEND_1 = Amendment(
    added=ADDED,
    why=_WHY,
    hypothesis=_HYP,
    expected_failure=_EXP,
    candidates=tuple(_draw(s) for s in AMEND_1_SEEDS),
)

AMEND_2 = Amendment(
    added=ADDED,
    why=(
        "The second half of the same widening, pre-registered in the same commit and read by "
        "the same rule. It is a separate block only because a batch carries at most six "
        "variants. Seeds 14-19 take the gated population to nineteen, matching M0296's "
        "switch-off population seed for seed."
    ),
    hypothesis=_HYP,
    expected_failure=_EXP,
    candidates=tuple(_draw(s) for s in AMEND_2_SEEDS),
)


METHOD = Method(
    id="M0306",
    name="The same error bar for the book that keeps its safety switch",
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
        "to 33.9 percent where its switch-off arms fall 58.1 and 59.9. So the published error "
        "bar is being applied to books it was not measured on, and nobody knows whether it "
        "overstates or understates them. This method registers the identical draw population on "
        "the gated chassis — M0295's engine with inner=GATED, side=matched, leader=largest, "
        "three industries, seeds 2 through 19 — read beside the recorded gated draw "
        "M0295-MATCHED-T3 (seed 1) and the recorded gated idea arm M0295-FOLLOW-T3, giving "
        "nineteen gated draws against M0296's nineteen switch-off draws, seed for seed. The "
        "pre-registered null is dilution by time invested: the gated arms hold exposure 0.694 "
        "against 0.964, so if the switch does nothing but keep the book out of the market the "
        "spread ratio should be 0.720 on every meter. The hypothesis is that the worst-fall "
        "ratio comes in clearly below 0.720 while the money-return ratio sits near it. Success "
        "is not a strategy and no arm is expected to be eligible: the deliverable is the width "
        "of the ruler the lab has used on every gated comparison in its record, and whether it "
        "can be derived from the one it already has."
    ),
    expected_failure=_EXP,
    candidates=tuple(_draw(s) for s in SEEDS),
    amendments=(AMEND_1, AMEND_2),
    seen_keys=("concept:gated-blind-draw-error-bar", "concept:draw-noise-on-a-gated-chassis",
               "concept:exposure-dilution-null-for-control-noise"),
)
