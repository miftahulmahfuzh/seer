"""M0513 — Hold-on control: random picks with a never-sell band, then 180- and 250-day winners.

Source: variation on M0509. M0509's best arm (120-session winners, 100% keep band — a holding is
sold only when it drops out of the scored pool) reached DSR 0.978 at N=329, funded +16.3%/yr vs the
best blind draw's +10.4%/yr. But M0509's blind draws (R3, R4) ran with NO band at all (keep_pct=0),
so they traded far more (324-382 times vs the winner arm's 200) and cannot say how much of that
5.9-point lead is the winner signal versus simply trading less. M0509's own close-out named this gap
and asked for it to be filled, plus two longer score windows it never tried (180 and 250 sessions).

This method: (a) runs the missing control — blind (random) picks at the SAME 100% band, at the
SAME 120-session window as the recorded M0509-W120-B100, with two seeds (one draw is not a control;
two reads the draw-noise width at this exact band setting); (b) extends the window sweep to 180 and
250 sessions, each as a winner arm paired with its own matched 100%-band random control, so every new
window's lead can be read against a control that trades at the same cadence rather than against
M0509's un-banded draws.

Frame is M0509's, unchanged: N20 host (20 equal monthly slots, F4-screened point-in-time index
members, fractional shares, Gotrade real fees, SPY 200-day switch). Same allocator object (reused,
not reimplemented) so the config digest is comparable arm for arm.
"""
from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0509_keep_band_ladder import LADDER, TimeParams
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 12)


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0513-{suffix}", family="M0513",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=LADDER, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0513",
    name="Hold-on control: random picks with a never-sell band, then 180 and 250 day winners",
    family="stock-momentum-short-window",
    source_kind="variation",
    source_ref="M0509-W120-B100: best eligible arm (DSR 0.978) whose own close-out named this "
               "missing control",
    parent_id="M0509",
    hypothesis=(
        "M0509 never ran random picks with a 100% keep band, so it cannot say whether the winner "
        "arms' lead over random (M0509-W120-B100 funded +16.3%/yr, 200 trades vs the best blind "
        "draw's +10.4%/yr, 324-382 trades, no band) is the ranking signal or just trading less "
        "often. Six arms, all at the 100% band (sell only on leaving the scored pool): two blind "
        "draws at the SAME 120-session window as the recorded W120-B100 (seeds 511, 512, so the "
        "draw-noise width at this exact band is read from two points, not one); 180- and 250-session "
        "winner arms, each paired with its own matched blind-draw control at the same window and "
        "band. Judged first on 2009-2015, the era M0509 found thinnest. Expect that random-with-"
        "band closes most of the 120-day gap, because selling 200 times instead of 380+ is itself "
        "worth real money in Gotrade fees and time-in-market; short-horizon momentum was published "
        "in 1993 and the lab's post-2009 record on this family has been weak."
    ),
    expected_failure=(
        "The random-with-band controls land close enough to W120-B100 (within the 2-point bar "
        "M0509 used to call a win) that trading less, not picking winners, explains most of the "
        "lead — and whatever the 180- and 250-day winner arms show, they inherit M0509's other "
        "problems: a thin or negative 2009-2015 edge and, if their behaviour moves with M0002, the "
        "same kin block that already stopped W120-B100 from being promoted."
    ),
    candidates=(
        _v("W120-RAND-A", TimeParams(N20, "blind", 511, 100, 120),
           "Control: hash draw of 20, seed 511, 100% keep band, 120-session pool — the control "
           "M0509-W120-B100 never had"),
        _v("W120-RAND-B", TimeParams(N20, "blind", 512, 100, 120),
           "Control: hash draw of 20, seed 512, 100% keep band, 120-session pool — second seed to "
           "read the draw-noise width at this band"),
        _v("W180-B100", TimeParams(N20, "win", 0, 100, 180),
           "180-session winners, 100% keep band (new window)"),
        _v("W180-RAND", TimeParams(N20, "blind", 513, 100, 180),
           "Control: hash draw of 20, seed 513, 100% keep band, 180-session pool — matched to "
           "W180-B100"),
        _v("W250-B100", TimeParams(N20, "win", 0, 100, 250),
           "250-session winners, 100% keep band (new window)"),
        _v("W250-RAND", TimeParams(N20, "blind", 514, 100, 250),
           "Control: hash draw of 20, seed 514, 100% keep band, 250-session pool — matched to "
           "W250-B100"),
    ),
    seen_keys=(
        "concept:keep-band-random-control-with-100pct-band",
    ),
)
