"""M0596 — Does a wider random book really earn more, or was that one seed's luck? Cross
seeds with sizes.

Source: variation of M0494. M0494 read one hash draw (seed 494) at 10, 20 and 40 names, with
and without SPY's 200-day switch, and found funded return rising with book size at both switch
settings -- the opposite of its own written prediction that concentration would pay. M0440
separately drew six different seeds at one size (20 names) and found a 1.9-point spread in
funded return and a 6.1-point spread in worst fall across them. Neither number answers this
method's question: was M0494's size-return climb a property of book size, or of seed 494
landing on a lucky set of names at every size it was read at?

This file draws two more fixed hash seeds (596, 5961 -- new, chosen to differ from every seed
already on record: 438, 439, 4401-4406, 494) and reads each at 10, 20 and 40 names, switch on
only -- the switch question is M0452's and M0494's, not this one's, so it is held fixed to stay
inside the lab's six-arm cap. Pooled with M0494's own three switch-on arms (D10-SW, D20-SW,
D40-SW, seed 494, already recorded), the lab then holds a 3-seed x 3-size cross: nine readings
from three independent draws, enough to see whether the climb from 10 to 40 names repeats
across seeds or was one seed's shape.

No opinion anywhere in this method: every arm is a hash draw from the F4-screened, point-in-time
index members, fractional shares at Gotrade's real fees, monthly, switch on. It is a yardstick,
not a find, and no arm here is meant to be promoted. Reuses M0438's blind-draw allocator
unchanged, same as M0494 and M0440, so all three seeds are drawn from the same pool shape.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N10, N20
from seer_engine.lab.methods.m0438_signed_jump_return_sort import JUMP, JumpParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 12)
SEEDS = (596, 5961)
N40 = replace(N20, top=40)
SIZES = (("D10", N10), ("D20", N20), ("D40", N40))


def _v(size_suffix: str, inner, seed: int) -> Candidate:
    return Candidate(id=f"M0596-{size_suffix}-S{seed}", family="M0596",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=JUMP,
                     params=JumpParams(inner, "blind", seed),
                     rationale=f"Hash draw of {inner.top} from the F4-screened members, "
                               f"seed {seed}, behind the switch",
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0596",
    name=(
        "Does a wider random book really earn more, or was that one seed's luck? Cross seeds "
        "with sizes"
    ),
    family="blind-draw-baseline",
    source_kind="variation",
    source_ref="M0494; Sera 20261112-2024",
    parent_id="M0494",
    hypothesis=(
        "M0494 found funded return rising with book size (10 -> 20 -> 40 names) at both "
        "switch settings on one hash draw (seed 494), the opposite of its own prediction that "
        "concentration would pay, and M0440 separately showed six seeds at one size (20) "
        "spread across a 1.9-point return range and a 6.1-point worst-fall range. Register two "
        "new seeds (596, 5961) crossed with the same three sizes (10, 20, 40), switch on only, "
        "holding the switch question fixed since M0452 and M0494 already cover it. Pooled with "
        "M0494's own three switch-on arms this gives a 3-seed x 3-size cross. SUCCESS: the "
        "size-return ordering seen at seed 494 (10 < 20 < 40) repeats, in direction, at both new "
        "seeds, and the spread across seeds at a fixed size is smaller than the spread across "
        "sizes at a fixed seed -- i.e. size, not seed, is the bigger source of the pattern. "
        "Prediction, written now: the three seeds will NOT agree on the direction of the "
        "size-return relationship, because M0440 already measured a same-size seed spread wide "
        "enough to swamp a monotonic size effect over only three sizes; M0494's climb is more "
        "likely to be this one seed's path than a real size effect."
    ),
    expected_failure=(
        "Three seeds is still a small cross -- six readings from two seeds plus the three "
        "already on record, not a distribution -- so even a repeated ordering at this N could "
        "itself be a three-in-a-row coincidence (1 in 4 chance for a monotonic-or-reverse-"
        "monotonic pair of independent orderings by chance alone, roughly, ignoring draws "
        "sharing the same market days). No arm has a ranking, so none of this is a tradeable "
        "strategy; it only prices how much of M0494's size climb survives a second and third "
        "seed. A genuinely wider cross (more seeds, or more sizes) is a follow-up this method "
        "does not attempt."
    ),
    candidates=tuple(
        _v(suffix, inner, seed)
        for seed in SEEDS
        for suffix, inner in SIZES
    ),
    seen_keys=(
        "concept:blind-draw-seed-by-size-cross",
    ),
)
