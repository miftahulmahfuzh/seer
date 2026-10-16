"""M0104 — Beaten-down companies as a small crash cushion beside SPY: 80% SPY, 20% the five-year losers.

Source: variation of M0073 (turnaround losers) and its parent M0069 (De Bondt & Thaler 1985,
long-term reversal), reserved by Sera batch 20261016-2034.
Idea: the five-year losers and the turnaround losers earned all their lead over SPY in 2000-2002
and 2009, and as stand-alone books they fell over half in 2008. They are a crash-season partner,
not a book to hold alone. Held as a fixed 20% slice beside an 80% SPY core, their 2000-2002 lead
could lift the core in a tech-style crash while the core keeps SPY's big-company drift -- the drift
every equal-slot book in this lab has lost to since 2018.

No new allocator: ``BLEND`` of the index ``TIMING`` allocator holding SPY at all times and the
parents' own allocators on their recorded params, each on its fixed share of equity. The
satellites park their unfilled slots in SPY too, so before about 1998 (when few members have five
years of bars) the book is close to all SPY. Every variant trades fractional shares at Gotrade's
real fees on ``monthly-hold-frac-gotrade``: the preset resizes held positions back to target each
month, which is the monthly rebalance the idea asks for. The lab runner funds every variant on the
owner's real deposits (10M IDR to start, 5M IDR on the 25th of each month), and SPY in the
benchmark pays the same fees on the same deposits.

Assumptions, written before the run (Sera's note asked for every book variant fractional at real
fees on the owner's deposits; that is the only preset used):
- "the confirmed-turn picks, or plain losers": both run, as separate variants, on the parents'
  exact params (M0073-UP-N20 and M0069-L60-N20), so each slice is a recorded book.
- One dose check, 70/30 on the confirmed-turn slice, fixed now: if the slice is a cushion, more
  of it should cushion more; if it is a drag after 2009, more of it should drag more.
- The control is 80% SPY beside the five-year WINNERS (M0069-W60-N20): the same equal-slot,
  20-name shape on the opposite side of the same sort, so any edge the losers slice shows over it
  belongs to "beaten down", not to "a small equal-weight slice next to SPY".
- No trend gate anywhere: a cushion that goes to cash when SPY falls is no cushion.

Pure: every piece reads only bars dated <= d; no clock, randomness or I/O.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0069_long_term_reversal import LTR, LtrParams
from seer_engine.lab.methods.m0069_long_term_reversal import F60 as L_F60
from seer_engine.lab.methods.m0073_turnaround_losers import TURN, TurnParams
from seer_engine.lab.methods.m0073_turnaround_losers import F60 as T_F60
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 10, 16)

ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")

UP_N20 = TurnParams(T_F60, pick="confirmed")  # M0073-UP-N20's params, verbatim
L60_N20 = LtrParams(L_F60, side="losers")  # M0069-L60-N20's params, verbatim
W60_N20 = LtrParams(L_F60, side="winners")  # M0069-W60-N20's params, verbatim


def _blend(core_share: str, satellite, params) -> BlendParams:
    c = Decimal(core_share)
    return BlendParams((BlendPart(TIMING, ALWAYS_SPY, c), BlendPart(satellite, params, Decimal(1) - c)))


def _v(suffix: str, params: BlendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0104-{suffix}", family="M0104", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BLEND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0104",
    name="Beaten-down companies as a small crash cushion beside SPY: 80% SPY, 20% the five-year losers, rebalanced monthly",
    family="stock-core-satellite",
    source_kind="variation",
    source_ref=(
        "Variation of M0073 and M0069 (De Bondt & Thaler 1985, Does the Stock Market Overreact?, "
        "Journal of Finance 40(3)); the core-satellite frame of M0030"
    ),
    parent_id="M0073",
    hypothesis=(
        "Long-term reversal was published in 1985, so the dev window is already after the crowd "
        "knew it. The five-year losers (M0069) and the turnaround losers (M0073) earned all their "
        "lead over SPY in 2000-2002 and 2009, and fell over half in 2008 as stand-alone books. As a "
        "fixed slice beside an always-held SPY core, their 2000-2002 lead (about +20 points a year "
        "while SPY fell) should lift the core in a tech-style crash, while the core keeps SPY's "
        "big-company drift. Each month the book holds 80% SPY and 20% a losers slice, resized back "
        "to those shares, fractional at Gotrade's real fees on monthly-hold-frac-gotrade, on the "
        "owner's deposits. Variants: C80-UP (20% M0073-UP-N20: losers that have turned up, the best "
        "stand-alone version), C80-L60 (20% M0069-L60-N20: the plain 20 biggest five-year losers), "
        "C70-UP (30% of the confirmed-turn slice: the dose check), and C80-W60 (the control: 20% "
        "the five-year WINNERS, the same shape on the other side of the sort). Success: a losers "
        "variant beats SPY TR on dev, beats the winners control, leads SPY in 2000-2002, and the "
        "dose check moves the same way as the slice."
    ),
    expected_failure=(
        "SPY alone fell about 55% from its 2007 peak, and an 80% SPY core with an unbraked 20% "
        "slice of beaten-down companies cannot fall much less than that: every variant should break "
        "the 20% worst-fall limit by a wide margin, so none can be eligible and the trial is worth "
        "running only for what it says about the slice. Since 2009 the losers slice trails SPY, so "
        "each blend should trail SPY by about a point a year in exactly the years most like today, "
        "and the dose check should trail by more. Survivorship flatters this slice more than almost "
        "any other book: the losers that went on to die are missing from the store, and those are "
        "the crash-season names. The whole-window lead, if any, will likely be a fraction of a "
        "point and earned before 2003."
    ),
    candidates=(
        _v("C80-UP", _blend("0.8", TURN, UP_N20),
           "80% SPY, 20% losers that have turned up (M0073-UP-N20), resized monthly"),
        _v("C80-L60", _blend("0.8", LTR, L60_N20),
           "80% SPY, 20% the plain 20 biggest five-year losers (M0069-L60-N20), resized monthly"),
        _v("C70-UP", _blend("0.7", TURN, UP_N20),
           "Dose check: 70% SPY, 30% the confirmed-turn losers"),
        _v("C80-W60", _blend("0.8", LTR, W60_N20),
           "Control: 80% SPY, 20% the five-year WINNERS, the same shape on the other side of the sort"),
    ),
    seen_keys=(
        "concept:long-term-reversal-crash-cushion",
        "concept:core-satellite-spy-losers",
    ),
)
