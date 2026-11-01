"""M0440 — Many blind draws as the yardstick: how often does a random 20 clear the luck bar?

Not a market idea; a question about the lab's own ruler. M0438 ran two blind draws of 20 from
the screened index members behind SPY's 200-day switch (seeds 438 and 439). They differed by
0.6 points a year in funded return and 14 points in worst fall, and one of the two was
dev-eligible by luck alone. M0433 saw the same thing on five draws (three of five passed the
dev screen). Two draws, or five on a different book, cannot say how *often* luck alone clears
the bar, and every later verdict of the form "it passed, so it must be real" leans on that rate.

This file registers six new hash draws (seeds 4401-4406) on exactly M0438's chassis, reusing
its allocator so nothing but the seed differs: point-in-time index members, the F4 screen, 20
equal slots, monthly, fractional shares at Gotrade's real fees, SPY 200-day switch on. The
draw is ``draw(seed, symbol)``, sticky in time and blind to everything about the stock.
Pooled with M0438's R1 and R2 (same chassis) the lab then holds eight blind draws.

The deliverable is a measured luck distribution: spread of funded return, worst fall and
luck score (DSR), and the share of draws clearing the dev screen and the 0.90 bar. No arm
has an opinion, so none is meant to be promoted; one that clears the screen is read as a
lucky draw, not as a find, and the hard gate (folds, kin) is expected to refuse it.
"""
from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0438_signed_jump_return_sort import JUMP, JumpParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 1)
SEEDS = (4401, 4402, 4403, 4404, 4405, 4406)


def _v(n: int, seed: int) -> Candidate:
    return Candidate(id=f"M0440-D{n}", family="M0440",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=JUMP,
                     params=JumpParams(N20, "blind", seed),
                     rationale=f"Blind draw of 20 from the screened members, seed {seed}, switch on",
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0440",
    name="Many blind draws as the yardstick: how often does a random 20 clear the luck bar?",
    family="blind-draw-baseline",
    source_kind="variation",
    source_ref="M0438",
    parent_id="M0438",
    hypothesis=(
        "M0438's two blind draws of 20 from the screened index members differed by 0.6 points "
        "a year in funded return and 14 points in worst fall, and one was eligible by luck "
        "alone; M0433's five draws showed three of five passing the dev screen. Register six "
        "more hash draws (seeds 4401-4406) on M0438's exact chassis: F4-screened point-in-time "
        "members, 20 equal slots, monthly, fractional shares at Gotrade fees, SPY 200-day "
        "switch on. No arm has an opinion. SUCCESS is a measured luck distribution: the range "
        "of funded return, worst fall and DSR over the six, and the share clearing the dev "
        "screen and DSR 0.90. Predictions, written now: funded return spans under 4 points a "
        "year; worst fall spans over 10 points; at least 2 of 6 clear the dev screen and at "
        "least 1 clears DSR 0.90; none beats SPY by a margin the span cannot explain; none "
        "passes the hard gate's fold and kin tests."
    ),
    expected_failure=(
        "No method signal to find; the value is the yardstick. Six draws still give a coarse "
        "rate (the 95% interval on 2 of 6 is wide), and the draws share one switch and one "
        "pool, so they are correlated through the market and understate the true spread. A "
        "high clear-rate says the screen is easy to pass by luck; a low one says M0438's R1 "
        "was unusual. Either reading is only as good as six."
    ),
    candidates=tuple(_v(i + 1, s) for i, s in enumerate(SEEDS)),
    seen_keys=("concept:six-blind-draws-luck-clear-rate-yardstick",),
)
