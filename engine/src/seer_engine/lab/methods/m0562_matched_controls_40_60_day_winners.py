"""M0562 — Matched coin-flip controls for the 40- and 60-day winners books.

Source: variation on M0513. M0513 gave the 120/180/250-session winners books a coin-flip twin that
trades at the same cadence (same window, same 100% never-sell band) and found the winners still led
by 3.8-6.5 points a year, with the post-2009 edge drifting from +1.8 (120) to -1.1 (180) to -2.3 (250)
as the window lengthened. The short end, 40 and 60 sessions, nearest the 1993 published effect, has
never had such a twin: M0509's W40-B100 has no matched control, and M0506's 60-day book ran with a
band that was not 100%. This method fills that gap with M0513's frame unchanged (N20 host, 20 equal
monthly slots, F4-screened point-in-time index members, fractional shares, Gotrade real fees via
MONTHLY_HOLD_FRAC_GOTRADE, SPY 200-day switch) and the same allocator object, so digests compare arm
for arm.

The 40-day winners arm is NOT re-registered: M0509-W40-B100 is the recorded winners book it is read
against. Two blind seeds per window read the draw-noise width at each.
"""
from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0509_keep_band_ladder import LADDER, TimeParams
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 13)


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0562-{suffix}", family="M0562",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=LADDER, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0562",
    name="Matched coin-flip controls for the 40- and 60-day winners windows",
    family="stock-momentum-short-window",
    source_kind="variation",
    source_ref="M0513: pace-matched controls at 120/180/250 sessions; the 40/60 end was never "
               "matched",
    parent_id="M0513",
    hypothesis=(
        "M0509's 40-session winners book (W40-B100, the recorded winners arm read here) and a "
        "60-session winners book have never had a coin-flip twin at the same window and 100% "
        "keep band. Five arms: two blind seeds at 40 sessions (5621, 5622), a 60-session winners "
        "arm, and two blind seeds at 60 sessions (5623, 5624). Success means a winners lead over "
        "the best matched blind draw above 2 points a year funded, at both windows, and a "
        "positive 2009-2015 edge over SPY for the winners arm; the drift seen in M0513 (+1.8, "
        "-1.1, -2.3 post-2009 at 120/180/250) predicts the shortest windows hold the best "
        "post-2009 edge. Momentum at this horizon was published in 1993 and the lab's "
        "post-2009 record on this family is weak, so a fade is the default expectation."
    ),
    expected_failure=(
        "The matched blind draws land within 2 points of the winners (so trading less, not "
        "picking winners, explains the lead), or the post-2009 edge is negative at 40 and 60 "
        "too, and the winners arm inherits the kin block that stopped its siblings from "
        "promotion."
    ),
    candidates=(
        _v("W40-RAND-A", TimeParams(N20, "blind", 5621, 100, 40),
           "Control: hash draw of 20, seed 5621, 100% keep band, 40-session pool, matched to "
           "M0509-W40-B100"),
        _v("W40-RAND-B", TimeParams(N20, "blind", 5622, 100, 40),
           "Control: hash draw of 20, seed 5622, 100% keep band, 40-session pool, second seed"),
        _v("W60-B100", TimeParams(N20, "win", 0, 100, 60),
           "60-session winners, 100% keep band (new window)"),
        _v("W60-RAND-A", TimeParams(N20, "blind", 5623, 100, 60),
           "Control: hash draw of 20, seed 5623, 100% keep band, 60-session pool, matched to "
           "W60-B100"),
        _v("W60-RAND-B", TimeParams(N20, "blind", 5624, 100, 60),
           "Control: hash draw of 20, seed 5624, 100% keep band, 60-session pool, second seed"),
    ),
    seen_keys=(
        "concept:keep-band-random-control-with-100pct-band",
        "concept:matched-pace-control-at-40-and-60-sessions",
    ),
)
