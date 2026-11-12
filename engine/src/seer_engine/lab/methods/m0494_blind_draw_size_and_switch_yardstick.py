"""M0494 — The random-pick yardstick: how much of a good book is just the switch and the pool?

Source: variation of M0452. M0452's "blind" arm -- a hash draw of 20 names from the F4-screened
pool, behind SPY's 200-day switch -- earned +10.2% a year funded (SPY +7.2%), a 22.6% worst fall
and DSR 0.942, beating M0452's own clever low-anchor sort. That result sits beside M0440's, which
measured how often a random 20 clears the dev screen by luck alone across six draws at one size.
Neither answers the question this method asks: how much of a random book's result comes from the
*size* of the book and from the switch, as opposed to the one draw's luck. Register one fixed
hash draw (seed 494) and read it at 10, 20 and 40 names, with and without the SPY 200-day switch:
six arms, the lab's cap, holding the seed fixed so only size and switch vary.

No opinion anywhere in this method: every arm is a hash draw from the F4-screened, point-in-time
index members, fractional shares at Gotrade's real fees, monthly. It is a yardstick, not a find,
and no arm here is meant to be promoted. Reuses M0438's blind-draw allocator and scoring
unchanged -- the jump-return score it computes is discarded by blind mode, used only to keep the
pool restricted to names the host can score on the same bars as every other arm in the lab's
blind-draw family (M0438, M0440), so these six draws are drawn from the same pool shape as the
yardsticks already on record.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N10, N20
from seer_engine.lab.methods.m0438_signed_jump_return_sort import JUMP, NOSW, JumpParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 12)
SEED = 494

N10_NOSW = replace(N10, trend=None)
N40 = replace(N20, top=40)
N40_NOSW = replace(N40, trend=None)


def _v(suffix: str, inner, rationale: str) -> Candidate:
    return Candidate(id=f"M0494-{suffix}", family="M0494",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=JUMP,
                     params=JumpParams(inner, "blind", SEED),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0494",
    name="The random-pick yardstick: how much of a good book is just the switch and the pool",
    family="blind-draw-baseline",
    source_kind="variation",
    source_ref="M0452; Sera 20261112-2024",
    parent_id="M0452",
    hypothesis=(
        "In M0452 a random 20 behind SPY's 200-day switch earned +10.2% a year funded (SPY "
        "+7.2%) with a 22.6% worst fall and DSR 0.942, beating the clever low-anchor sort. Test "
        "random draws at 10, 20 and 40 names, with and without the switch, always-invested and "
        "fractional at Gotrade fees, to price what the switch and pool alone give so sorts can "
        "be judged against it. One hash draw (seed 494), held fixed across all six arms, so only "
        "book size and the switch vary -- seed-to-seed luck is M0440's question, not this one. "
        "SUCCESS: a readable size effect (return and worst fall move monotonically, or don't, "
        "from 10 to 40 names) and a readable switch effect (each switched arm has a shallower "
        "worst fall and less time invested than its always-invested twin) that match the sense "
        "of M0452's and M0440's draws. Predictions, written now: funded return falls as the book "
        "widens from 10 to 40 (concentration risk pays, on average, in this one draw); the "
        "switch costs some of that return in a rising window but shrinks the worst fall at every "
        "size; no arm is dev-eligible on its own, because none of them has an opinion to be "
        "eligible for."
    ),
    expected_failure=(
        "One draw's size curve can run either way by chance -- a hash draw of 10 could easily "
        "beat the draw of 40 even if wider books are not reliably worse, because this is one "
        "path through the lab's luck distribution (M0440 measured a multi-point spread between "
        "draws of the same size). Six arms from one seed cannot separate 'this is how size and "
        "the switch work' from 'this is how seed 494 happened to fall'; that would need the "
        "cross of several seeds with several sizes, which this method does not attempt and a "
        "follow-up should queue. No arm has a ranking, so none of this is a tradeable strategy; "
        "it only prices the parts of M0452's and M0440's results that were never about the sort."
    ),
    candidates=(
        _v("D10-SW", N10, "Hash draw of 10, seed 494, behind the switch"),
        _v("D10-NOSW", N10_NOSW, "Hash draw of 10, seed 494, always invested"),
        _v("D20-SW", N20, "Hash draw of 20, seed 494, behind the switch"),
        _v("D20-NOSW", NOSW, "Hash draw of 20, seed 494, always invested"),
        _v("D40-SW", N40, "Hash draw of 40, seed 494, behind the switch"),
        _v("D40-NOSW", N40_NOSW, "Hash draw of 40, seed 494, always invested"),
    ),
    seen_keys=(
        "concept:blind-draw-size-and-switch-yardstick",
    ),
)
