"""M0450 — Hold SPY with a fixed 20% slice of last month's 20 biggest losers, resized monthly.

Source: variation of M0165 (and M0104, M0069), reserved by Sera batch sera-20261101-1949.
Short-term reversal is Jegadeesh 1990, Evidence of Predictable Behavior of Security Returns,
Journal of Finance 45(3). M0165 found a beaten-down slice earns a few tenths of a point whenever it
is held and that a crash trigger only removes quiet months. M0450 swaps the five-year losers for the
one-month losers, a slice that needs no crash, and never switches it off.

No new allocator: ``BLEND`` of an always-SPY ``TIMING`` core and M0069's ``LTR`` ranker with the
formation window set to one month (21 sessions, no skipped days) and the 20 lowest returns, which
is the same pool, price floor and liquidity screen M0069 uses. ``side="winners"`` flips the sort
for the control. Everything reads bars dated <= d. Assumption: one month is 21 sessions; a fifth of
equity is 20%; the slice is 20 names, equal weight, resized on the monthly rebalance.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0069_long_term_reversal import F60, LTR, LtrParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 11, 1)

ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")
M1 = replace(F60, mom_n=21, mom_skip=0)  # the last 21 sessions' return
M1_SKIP = replace(F60, mom_n=26, mom_skip=5)  # same, skipping the latest week (bid-ask bounce)
LOSERS = LtrParams(M1, side="losers")
WINNERS = LtrParams(M1, side="winners")
LOSERS_SKIP = LtrParams(M1_SKIP, side="losers")


def _blend(share: str, params: LtrParams) -> BlendParams:
    s = Decimal(share)
    return BlendParams((BlendPart(TIMING, ALWAYS_SPY, Decimal(1) - s), BlendPart(LTR, params, s)))


def _v(suffix: str, allocator, params, rationale: str) -> Candidate:
    return Candidate(id=f"M0450-{suffix}", family="M0450", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0450",
    name="A small always-held slice of last month's biggest losers beside SPY",
    family="stock-core-satellite",
    source_kind="variation",
    source_ref="Variation of M0165 and M0104 (Jegadeesh 1990, Journal of Finance 45(3), short-term reversal)",
    parent_id="M0165",
    hypothesis=(
        "Short-term reversal was published in 1990, so the dev window is mostly after the crowd and "
        "the edge is likely faded. M0165 found a beaten-down slice earns a few tenths of a point "
        "over SPY whenever it is held, and that timing it with a crash trigger only removes quiet "
        "months. The 20 index members that fell most over the last month should rebound the next "
        "month, an edge that needs no crash. The book holds 80% SPY and a 20% slice of those 20 "
        "one-month losers, resized monthly, fractional at Gotrade's real fees on the owner's "
        "deposits. Variants: L1M (the idea), W1M (control: the one-month winners, same shape), "
        "L1M-SKIP (losers measured skipping the latest week, to avoid the bid-ask bounce), L1M-30 "
        "(30% dose check). The no-opinion arm (SPY always, same rules and fees) cannot be "
        "registered again: its digest repeats M0251-HOLD, which already ran, so the dressing "
        "comparison reads M0251-HOLD's recorded trial. Success: L1M beats SPY TR on dev, beats "
        "W1M and M0251-HOLD, and leads SPY in 2009-2015."
    ),
    expected_failure=(
        "Monthly turnover of the slice at Gotrade's fees eats the edge (a 20-name slice at 20% of "
        "equity is many small orders); the fall is still SPY's 55% because the slice is only a "
        "fifth; 2009-2015 trails SPY; one-month losers in a crash keep falling, so any lead may "
        "come from the winners side instead. Survivorship flatters losers: the ones that died are "
        "missing from the store."
    ),
    candidates=(
        _v("L1M", BLEND, _blend("0.2", LOSERS), "80% SPY, 20% the 20 one-month losers, resized monthly"),
        _v("W1M", BLEND, _blend("0.2", WINNERS), "Control: 20% the 20 one-month winners, same shape"),
        _v("L1M-SKIP", BLEND, _blend("0.2", LOSERS_SKIP), "Losers over sessions -26..-5, skipping the latest week"),
        _v("L1M-30", BLEND, _blend("0.3", LOSERS), "Dose check: 30% slice"),
    ),
    seen_keys=(
        "concept:one-month-reversal-always-held-slice",
        "concept:core-satellite-spy-losers",
    ),
)
