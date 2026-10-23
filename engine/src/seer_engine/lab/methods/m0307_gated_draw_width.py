"""M0307 — Measure the coin's width behind the switch, where the lab's comparisons actually live.

Source: variation of M0296 (the blind-draw spread on the industry lead-lag book).

**What the reserved idea row asked for, and why this file is not quite that.** M0307 was queued
as a report: walk every recorded method that carries a control arm, compute the idea arm's lead
over its control, and print it beside the measured coin width so that every lead inside the noise
can be flagged. The row wrote its own blocker into ``expected_failure``: the width M0296 measured
does not obviously transfer, because it was measured on one chassis and a width scales with book
size, turnover and whether a safety switch is kept. The row's fallback was to give up on the
width and flag only the comparisons resting on a single control, where the arithmetic ceiling
already settles the matter without any width at all.

That fallback is worth having and the analysis will still deliver it. But the blocker is
measurable, and measuring it is worth more than conceding it, because the gap between the width
the lab *has* and the width the lab *needs* is not a vague scaling question — it is one dial.

**The one dial.** M0296 ran eighteen draws, seeds 2 through 19, and read them together with
M0295's recorded seed-1 draw as a population of nineteen. Every one of them runs with the SPY
200-day switch OFF (``inner=OPEN``), deliberately, so that time in cash could not confound its
era split. That population therefore prices the coin for an always-invested book. But the lab is not an
always-invested place: it clusters by its gate, almost every recorded method keeps the switch,
and nearly every idea-versus-control comparison the idea row wants to audit is a gated arm
against a gated control. Auditing gated claims against an ungated error bar is the wrong
measurement, and it errs in the expensive direction — if the gated coin is narrower, an ungated
bar over-flags, and the audit would retire real findings as noise.

So this method spends its six slots buying the missing half of the bar: the identical blind draw,
the identical engine, the identical seeds, with the switch ON.

**The design is paired, which is why six slots are enough.** The gated seed-1 draw is already
recorded as ``M0295-MATCHED-T3``, and the ungated seeds 1 through 7 are already recorded as
``M0295-MATCHED-T3-NOGATE`` plus ``M0296-DRAW-S2`` through ``-S7``. This file registers gated
seeds 2 through 7. That completes two populations of seven over the **same seven hashes**:

    gated:   M0295-MATCHED-T3 (seed 1) + M0307-GDRAW-S2..S7
    ungated: M0295-MATCHED-T3-NOGATE (seed 1) + M0296-DRAW-S2..S7

Nothing is re-run — a configuration runs once per window and ``config_digest`` ignores the
candidate id — and the two populations differ in exactly one field, ``inner.trend``. Comparing a
spread of seven with a spread of nineteen would be a sample-size artefact, since a range grows
with the number of draws; comparing seven with the *same seven* is not. The nineteen ungated
draws stay what they are, the lab's widest ungated sample, and are read only as a sanity check on
the seven-draw ungated range this comparison uses.

**The construction, unchanged from M0295 and M0296.** On data date d, among the screened members
(close >= $5, 20-day mean dollar volume > $20M, at least 253 bars), label each with its
Fama-French 12 industry; keep industries with at least 5 pool members and a computable leader
return; drop each industry's most-traded member from its own followers; choose 3 industries;
split 20 equal slots over them 7/7/6; inside each industry take followers in a fixed month-keyed
hash order; unfilled slots hold SPY. ``side="matched"`` draws the three industries by
blake2b(seed | industry | year-month) rather than by any opinion about leaders, so every arm here
is opinion-free by construction: these are placebos, and the spread of placebos is the whole
deliverable. ``inner=GATED`` is M0295's own gated parameter object, the SPY 200-day switch that
the recorded gated arms already ran.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits, identical to every arm this is read against.

**Why a method whose arms contain no idea is still a method.** None of these six arms is trying to
beat SPY and none is expected to be eligible. The deliverable is a number the lab will reuse: how
far apart two identical, opinion-free, gated books drift on nothing but a hash. Every future
claim of the form "the idea arm beat its control by X" on a gated book is readable against it,
and the lab currently has no such number at all. M0296 bought the ungated half; this buys the half
the lab actually uses.

Pure: the engine is M0295's, which reads only bars dated at or before d and has no clock,
randomness, file or network of its own. The seed enters only through a fixed blake2b of the seed,
the industry name and the decision's month.

Assumptions, written before the run:
  * a seed is an arbitrary label, so gated seeds 1-7 are as fair a sample of "a gated blind draw"
    as any other seven, and the recorded gated seed-1 draw belongs in the same population as the
    six run here — the same assumption M0296 wrote down and the same hash that justifies it;
  * the switch is the right dial to vary first, ahead of book size and turnover, because it is
    the dial that splits the lab's own population: the lab clusters by its gate, so a gated bar
    and an ungated bar between them cover most recorded comparisons, where a bar per book size
    would cost one method id each and never finish.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0295_industry_bellwether_lead_lag import (
    GATED,
    LEADLAG,
    LeadLagParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 23)

#: The seeds this method spends. 1 is absent on purpose: the gated seed-1 draw is already
#: recorded as ``M0295-MATCHED-T3``, and re-running it would measure one configuration twice.
#: These six are exactly the seeds M0296 ran ungated, so the two populations pair hash for hash.
SEEDS = (2, 3, 4, 5, 6, 7)


def _draw(seed: int) -> Candidate:
    return Candidate(
        id=f"M0307-GDRAW-S{seed}",
        family="M0307",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=LEADLAG,
        params=LeadLagParams(inner=GATED, industries=3, side="matched", leader="largest",
                             seed=seed),
        rationale=(
            f"gated blind draw {seed} of seven: three industries drawn in hash order, the same "
            "7/7/6 split, the same opinion-free member order, the SPY 200-day switch kept — the "
            f"twin of the recorded ungated draw on seed {seed}, differing from it in the switch "
            "alone and from its gated siblings in the seed alone"
        ),
        added=ADDED,
        owner_inputs=(),
    )


_HYP = (
    "Behind the SPY 200-day switch the coin is narrower than the lab's only measured error bar "
    "says, and markedly narrower in the fall than in the return. The seven gated draws should "
    "span less of the twenty-year money return than the same seven hashes span ungated, and "
    "should span far less worst fall, because the switch stands the whole population in cash "
    "through the episodes where blind draws diverge most — a draw's fall is decided mostly by "
    "which names it happened to hold into 2008, and a book that is out of the market in 2008 "
    "cannot express that difference. If that holds, the lab has been holding the wrong yardstick: "
    "its recorded idea-versus-control claims are overwhelmingly gated, the only width it has "
    "measured is ungated, and using the ungated width to audit them would retire real findings "
    "as noise. Success for this method is not eligibility — no arm here has an opinion and none "
    "should be eligible — but a usable gated width, stated as a range and a typical distance "
    "from the middle on both the return and the fall, that the audit in the analysis can then "
    "apply to the lab's own record."
)

_EXP = (
    "The likeliest failure is that the gated width in RETURN barely narrows. The switch is a "
    "common factor: it moves every draw into cash on the same days, so it may subtract roughly "
    "the same amount from all seven and leave the picking noise — which is what the seeds "
    "actually differ in — untouched. The fall would still compress, but a bar that narrows on "
    "one axis and not the other is harder to use than one number, and the honest report would "
    "then be two separate bars rather than a tidier one. The second failure is subtler and "
    "worse: seven gated draws may land so close together that the measured range is dominated "
    "by whichever single seed happens to sit furthest out, in which case this buys a lower bound "
    "on the gated width rather than the width, exactly as M0296 feared for its own first seven. "
    "The third is that three industries drawn from roughly ten eligible ones overlap so heavily "
    "that gated draws are near-duplicates of each other, and the bar produced is too narrow to "
    "be safe to audit with — which would be a finding, but a disappointing one, because it would "
    "mean the only safe bar is still the ungated one. If any of the three lands, the analysis "
    "falls back to the idea row's own fallback and flags the comparisons that rest on a single "
    "control arm, which needs no width at all: beating one control can never support better "
    "than a one-in-two claim, whatever the gap looks like."
)


METHOD = Method(
    id="M0307",
    name="The coin's width behind the switch",
    family="market-shape-yardstick",
    source_kind="variation",
    source_ref="M0296",
    parent_id="M0296",
    hypothesis=_HYP,
    expected_failure=_EXP,
    candidates=tuple(_draw(s) for s in SEEDS),
    seen_keys=(
        "concept:gated-blind-draw-width",
        "concept:coin-width-transfers-across-the-switch",
        "concept:audit-single-control-comparisons",
    ),
)
