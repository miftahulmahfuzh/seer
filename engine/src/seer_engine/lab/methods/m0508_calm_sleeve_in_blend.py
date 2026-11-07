"""M0508 — A calm sleeve inside a blend: steady-risk stocks as the low-fall partner to the recent-winners book.

Source: variation on M0505 (steady-risk book) and M0506 (recent winners with a keep band). Both
sleeves already exist as allocators; this method writes no new allocator, only a BLEND of two of
them. Recent-winners momentum (Jegadeesh & Titman 1993) and vol-of-vol (Baltussen et al. 2018) are
both published, so dev may overstate either; say so.

Each sleeve keeps its own SPY 200-day switch (N20's trend), so both step aside together and the
blend is in cash whenever the host is. That keeps the comparison with the recorded parts fair.

Arms (five): B30 (30% steady sleeve + 70% winners BAND70: the treatment), B50 (50/50: dose), ERR30
(30% ERRATIC sleeve, the mirror), BLIND30 (30% blind draw sleeve, seed 505: no opinion in the
sleeve) and B30-NOSW (the treatment with no switch on either sleeve: prices the switch). The parts
alone are recorded already (M0506-BAND70 and M0505-STEADY) and are the comparison, not new arms.
SUCCESS: B30 worst fall under M0506-BAND70's, funded return within 1 point of it, beats BLIND30 and
ERR30 funded, positive 2009-2015 edge vs SPY.
"""
from __future__ import annotations

from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0505_vol_of_vol import VOLOFVOL
from seer_engine.lab.methods.m0505_vol_of_vol import TimeParams as CalmParams
from seer_engine.lab.methods.m0506_recent_winners_band import BANDBOOK
from seer_engine.lab.methods.m0506_recent_winners_band import TimeParams as WinParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from dataclasses import replace
from datetime import date

from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart

ADDED = date(2026, 11, 7)
NOSW = replace(N20, trend=None)

WIN = WinParams(N20, "win", 0, 70)
WIN_NOSW = WinParams(NOSW, "win", 0, 70)


def _mix(calm_share: str, calm: CalmParams, win: WinParams = WIN) -> BlendParams:
    c = Decimal(calm_share)
    return BlendParams((BlendPart(BANDBOOK, win, Decimal(1) - c), BlendPart(VOLOFVOL, calm, c)))


def _v(suffix: str, params: BlendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0508-{suffix}", family="M0508",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=BLEND, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0508",
    name="A calm sleeve inside a blend: steady-risk stocks beside the recent-winners book",
    family="stock-multi-factor-blend",
    source_kind="variation",
    source_ref="M0505-STEADY (steady-risk book) and M0506-BAND70 (60-session winners, 70% keep band); "
               "Jegadeesh & Titman (1993); Baltussen et al. (2018)",
    parent_id="M0505",
    hypothesis=(
        "M0505's steady-risk book had a 20.5% worst fall against 24-25% for random draws behind the "
        "same switch but earned only +8.5% a year funded, while M0506's winners book (BAND70) earned "
        "+14.6% with a 24.6% worst fall and a DSR of 0.898 against the 0.90 bar, so its fall is the "
        "binding fault. Both ideas are published (1993, 2018), so dev may overstate them and the edge "
        "may fade after 2015. Hypothesis: the steady sleeve is a low-fall partner that cuts the "
        "winners book's fall by more than it costs in return. Arms, all monthly, fractional, Gotrade "
        "real fees, each sleeve behind its own 200-day SPY switch (so both go to cash together): "
        "B30 = 70% BAND70 winners + 30% steady-risk book (treatment); B50 = 50/50 (dose); ERR30 = 70% "
        "winners + 30% the ERRATIC-risk book (mirror: the sleeve's signal inverted); BLIND30 = 70% "
        "winners + 30% blind draw of 20 (seed 505, no opinion in the sleeve, the control for what any "
        "extra 30% of diversification does); B30-NOSW = B30 with no switch on either sleeve (prices "
        "the switch). The parts alone are the recorded M0506-BAND70 and M0505-STEADY, the comparison "
        "and not new arms. Predictions, written now: B30's worst fall lands between the two parts' "
        "(about 22-23%), its funded return falls 1-3 points below BAND70, and B30 does not beat "
        "BLIND30 by more than a point, because a blind draw diversifies about as well as a steady "
        "pick. SUCCESS: B30 worst fall under BAND70's and funded return within 1 point of it, B30 "
        "beats BLIND30 and ERR30 funded, and a positive 2009-2015 edge vs SPY."
    ),
    expected_failure=(
        "The two sleeves are both long US large caps behind one switch, so they move together and the "
        "blend's fall is just the average of the parts, no better than a random sleeve (BLIND30). The "
        "30% sleeve holds 20 names at 1.5% of equity, about a $19 order on the lab's 20M IDR start, "
        "and Gotrade's minimum fee makes that slice expensive to trade monthly, so B30 can lose more "
        "to fees than the calm sleeve saves in falls. A fall that stays above 20% is a fail on its own, "
        "and a winners-based book from a published anomaly is likely to fade after 2015."
    ),
    candidates=(
        _v("B30", _mix("0.30", CalmParams(N20, "steady")), "70% winners BAND70 + 30% steady-risk sleeve"),
        _v("B50", _mix("0.50", CalmParams(N20, "steady")), "50/50 winners and steady-risk sleeve: dose"),
        _v("ERR30", _mix("0.30", CalmParams(N20, "erratic")), "Mirror: 30% erratic-risk sleeve"),
        _v("BLIND30", _mix("0.30", CalmParams(N20, "blind", 505)),
           "Control: 30% blind draw sleeve, seed 505, no opinion in the sleeve"),
        _v("B30-NOSW", _mix("0.30", CalmParams(NOSW, "steady"), WIN_NOSW),
           "B30 with no switch on either sleeve: prices the switch"),
    ),
    seen_keys=(
        "concept:calm-sleeve-in-momentum-blend",
    ),
)
