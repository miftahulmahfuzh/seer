"""M0296 — Read the industry-lead-lag book against a spread of blind draws, not one.

Source: variation of M0295 (the industry bellwether lead-lag book). The measurement question is
the lab's own: insight 585 and M0295's closing analysis both ask for an error bar on a
twenty-name three-industry book over a seven-year slice, because the lab has been quoting such
slices for months without one.

Idea in one line: M0295's only unresolved number is a 2009-2015 lead of about four points a year
of the always-invested follow book over its always-invested blind draw, measured against **one**
coin-toss seed over a 6.75-year slice. Seed noise alone is worth 2.0-2.6 points over the full
twenty years and is wider over a shorter slice, so that lead may be nothing at all. This method
widens the control from one draw to a population of draws and reads the follow book's position
inside it.

**What this file registers, and why it is not what the reserved idea row said.** The idea row
asked for the identical gate-off follow book plus six blind draws, seeds 1 through 6. The
gate-off follow book and the seed-1 gate-off draw are **already recorded**, as
``M0295-FOLLOW-T3-NOGATE`` and ``M0295-MATCHED-T3-NOGATE``, produced by the engine this file
imports. Re-registering them here would run one configuration twice under a renamed allocator,
which is the thing the lab forbids and the reason ``config_digest`` ignores the candidate id. So
all six slots go to **new** seeds, 2 through 7, and the comparison reads:

    * the follow book: M0295-FOLLOW-T3-NOGATE, recorded, not re-run;
    * the draw population: M0295-MATCHED-T3-NOGATE (seed 1) **plus** this method's seeds 2-7,
      seven draws in total — one more than the idea row asked for, at no extra cost.

That is strictly more evidence than re-running two known configurations would have bought, and it
keeps every arm on one engine: this file imports M0295's allocator **object** and its params
class, so the seven draws and the follow book differ in nothing but the seed and the side.

**The construction, unchanged from M0295.** On data date d, among F4's screened members (close
>= $5, 20-day mean dollar volume > $20M, at least 253 bars), label each with its Fama-French 12
industry; keep industries with at least 5 pool members and a computable leader return; drop each
industry's most-traded member from its own followers; choose 3 industries; split 20 equal slots
over them 7/7/6; inside each industry take followers in a fixed month-keyed hash order; unfilled
slots hold SPY. ``side="matched"`` chooses the three industries by blake2b(seed | industry |
year-month) instead of by the leader's last-month return. **The SPY 200-day switch is off in
every arm** (``inner=OPEN``), exactly as in the two recorded arms this is read against, so the
comparison is about picking alone and the switch's time in cash cannot confound the era split —
which matters because a rising 2009-2015 is precisely where time in cash is most expensive
(insight 462).

**What a spread of draws buys that one draw cannot.** One control answers "did the idea beat this
coin toss". Seven answer "where does the idea sit in the distribution of coin tosses", which is
the only form of the question that can be wrong. The spread of the seven draws is itself the
deliverable: it is the lab's first measured error bar for a twenty-name three-industry book, over
the full window **and** over the 2009-2015 slice, and every future shape-matched control on a
book of this shape can be read against it.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits, identical to the arms this is compared with. Pure: the engine is M0295's, which
reads only bars dated at or before d and has no clock, randomness, file or network of its own.

Assumption, written before the run: a draw's seed is an arbitrary label, so seeds 2-7 are as
good a sample of "a blind three-industry draw" as seeds 1-6 would have been, and seed 1's
recorded trial belongs in the same population as the six run here. Nothing in the hash gives any
seed a privileged position; the key is blake2b of the seed, the industry name and the month.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0295_industry_bellwether_lead_lag import (
    LEADLAG,
    OPEN,
    LeadLagParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 23)

#: The seeds this method spends. 1 is not here: it is already recorded, as
#: ``M0295-MATCHED-T3-NOGATE``, and re-running it would measure one configuration twice.
SEEDS = (2, 3, 4, 5, 6, 7)


def _draw(seed: int) -> Candidate:
    return Candidate(
        id=f"M0296-DRAW-S{seed}",
        family="M0296",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=LEADLAG,
        params=LeadLagParams(inner=OPEN, industries=3, side="matched", leader="largest",
                             seed=seed),
        rationale=(
            f"blind draw {seed} of seven: three industries drawn in hash order, the same 7/7/6 "
            "split, the same opinion-free member order, always invested — a placebo shaped like "
            "the book it controls, differing from the other draws in nothing but the seed"
        ),
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0296",
    name="Read the industry-lead-lag book against a spread of blind draws, not one",
    family="stock-industry-lead-lag",
    source_kind="variation",
    source_ref="M0295",
    parent_id="M0295",
    hypothesis=(
        "M0295 left exactly one number unresolved. Always invested, with the safety switch off "
        "in both arms, its industry-follow book led its single blind-draw control by about 4.1 "
        "points a year over 2009-2015 on the dev store and 4.3 on the survivorship-check store, "
        "while trailing that same control by 0.4 points a year over the whole twenty years. A "
        "sign that flips between eras, measured over a 6.75-year slice against ONE coin-toss "
        "seed, is the exact shape of draw noise: seed alone is worth 2.0-2.6 points a year on a "
        "twenty-year window, and a seven-year slice is noisier still. So this method turns the "
        "single control into a population. It registers six more blind draws — seeds 2 through "
        "7, identical in every other respect, on the same engine, the same three-industry split, "
        "the same Fama-French 12 taxonomy, the same opinion-free member order, the same real "
        "Gotrade fees, and the safety switch off in every arm. Read beside the two already "
        "recorded gate-off arms of M0295 that this engine produced, that gives one follow book "
        "against seven draws. Success: the follow book sits clearly ABOVE all seven draws over "
        "2009-2015 and outside their range over the full window, in which case the lead is real "
        "and the pre-2009 sign flip becomes the thing to explain. The second deliverable does "
        "not depend on the first: the spread of seven draws is the lab's first measured error "
        "bar for a twenty-name three-industry book, whole-window and over the 2009-2015 slice, "
        "and every shape-matched control the lab reads from now on can be sized against it."
    ),
    expected_failure=(
        "The follow book sits INSIDE the spread of the seven draws over 2009-2015, which closes "
        "the industry lead-lag line for good: choosing three industries by their biggest "
        "member's last month would then be worth nothing that a coin toss is not, in the era "
        "the lab cares most about, having already been worth nothing over the full window. That "
        "is the likely outcome, because M0216 priced industry rotation at roughly nothing after "
        "2009 and because a 4-point gap on a 6.75-year slice is inside what a single seed can "
        "produce. The second expected failure is about the instrument rather than the idea: the "
        "six draws may land so close together — same pool, same screen, same slot count, same "
        "monthly re-pick, only the industry labels shuffled — that the error bar comes out "
        "implausibly narrow, because three industries drawn from the same nine or ten eligible "
        "ones overlap heavily by construction and the draws are not really independent books. "
        "If that happens the spread understates true draw noise and must be reported as a lower "
        "bound, not as the error bar. Third: every arm is always invested through 2008, so all "
        "seven will fall far past the 20% limit and none will be dev-eligible. That is expected "
        "and is not a result; this method is an instrument, and its product is a measurement, "
        "not a candidate."
    ),
    candidates=tuple(_draw(s) for s in SEEDS),
    seen_keys=("concept:blind-draw-seed-spread", "concept:control-error-bar",
               "concept:industry-draw-population"),
)
