"""M0607 — SPY's 200-day switch with the cash leg paying the Treasury bill yield.

Source: variation of M0545, whose analysis said to change what the book holds while out, not
when it leaves. M0434 and M0545 closed the switch's length and hysteresis as dials on SPY alone.
The one dial left is the money's pay while the switch is out. Here the simulator credits idle
cash the T13W three-month bill yield, point in time (``cash_yield``), the same lever M0251 and
M0339 used. The allocator is M0545's (SPY at full weight, monthly check) unchanged: out means
no position, and the rules decide what the cash earns. Reads only bars dated <= ``data_date``.
Pure.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0545_spy_fast_out_slow_in import SWITCH, PairParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 13)

CASH = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-cash", cash_yield="T13W")


def _v(suffix: str, params: PairParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0607-{suffix}", family="M0607", rules=CASH,
                     allocator=SWITCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=("cash-yield",))


METHOD = Method(
    id="M0607",
    name="Parked cash earns Treasury yield: SPY's 200-day switch with bills while out",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0545, whose analysis said to change what the book holds while out",
    parent_id="M0545",
    hypothesis=(
        "M0434 and M0545 closed the switch's length and hysteresis as dials on SPY alone: the "
        "plain 200-day rule is the best the family offers and still trails SPY after 2009. The "
        "untested dial is what the money does while out. Hold SPY above its 200-day average "
        "(monthly, fractional, Gotrade fees, owner deposits) and credit idle cash the T13W bill "
        "yield while out. Arms: SMA200-CASH (treatment, the new book) and PAIR150-250-CASH "
        "(M0545's pair with the same cash pay). Controls are CITED, not re-run: the plain "
        "no-yield 200-day switch is M0084-MONTHLY, first recorded as trial 349 (also "
        "M0545-SMA200), and the always-invested no-opinion book is M0084-ALWAYS, trial 347; "
        "both match on rules, allocator and params. The gap SMA200-CASH minus trial 349 is the "
        "pure value of the bill yield, since nothing else differs. The always book prices what "
        "acting costs. Cash-yield credit is a known small add (M0339: about 0.9 point a year "
        "over 20 years, nothing in 2009-2015; M0251's cash arm lost to its no-cash twin on a "
        "different book), and the 200-day switch is old (Faber 2007), so expect fade. Judged "
        "first on 2009-2015. SUCCESS: SMA200-CASH beats SPY TR on funded return, worst fall "
        "within the bar, folds majority, DSR >= 0.90 at the N in force. Readable if it fails: "
        "the cash dial is closed and the post-2009 shortfall is missed recoveries."
    ),
    expected_failure=(
        "2009-2015 yields were near zero, so the yield adds almost nothing there, and the "
        "post-2009 shortfall is the missed recoveries, not the cash. Monthly checks mean trade "
        "counts in the tens, so profit factor and the luck bar mean little. The cash-yield "
        "owner input is unverified, so even a pass cannot be promoted to paper until the owner "
        "confirms Gotrade pays or the book holds a bill ETF."
    ),
    candidates=(
        _v("SMA200-CASH", PairParams(200, 200),
           "Treatment: the plain 200-day switch, idle cash credited the T13W bill yield"),
        _v("PAIR150-250-CASH", PairParams(150, 250),
           "Treatment: M0545's 150-out 250-in pair, idle cash credited the T13W bill yield"),
    ),
    seen_keys=(
        "concept:spy-200d-switch-cash-earns-bill-yield",
    ),
)
