"""M0294 — The smallest sleeve worth trading: when does a hand-picked slice stop paying its own fees?

Source: variation of M0283 (calm stocks beside SPY). The core-and-satellite frame is general
knowledge; the sleeve ideas themselves are M0278's beta ranking (Frazzini & Pedersen 2014, JFE)
and plain twelve-minus-one-month momentum (Jegadeesh & Titman 1993; widely traded since, so a
strong dev result is expected to fade -- the signal is not what this method is about).
Reserved by Sera batch 20261031-1503 as an ``idea`` row with M0283 as its parent; this file
refines it and keeps its id.

WHY. M0283 put 30 calm stocks beside SPY at five SPY shares. Per point of worst fall the book
earned 0.15 with a 30% sleeve (C70-LB), 0.20 with 50% and 0.24 with 70% -- the thin sleeve was the
only rung no better than SPY alone. The signal was identical at every rung; only the share changed.
The obvious reading is the fee schedule: Gotrade charges a minimum per order whatever the slot,
so a thirty-name sleeve that is 30% of the book has slots a third the size paying the same floor.
If so, the turning point belongs to the fee schedule and the name count, not to the signal, and
it should sit near the same share for a sleeve built on a different idea.

THE LADDER. "Sleeve share" below is the hand-picked slice's share of the book; the rest is SPY.

    sleeve            names   share   id          note
    calm (beta)        30      20%    L20-CALM30  the rung M0283 never ran (it stopped at 30%)
    calm (beta)        30      30/50/70%          ALREADY RECORDED as M0283 C70-LB, C50-LB,
                                                  C30-LB: same allocator, same params, same preset.
                                                  Re-registering them would be a duplicate
                                                  digest, so they are the comparison, not arms.
    calm (beta)        10      30%    L30-CALM10  narrowing at the SAME share: fewer, fatter slots
    momentum (12-1)    30      20/30/50/70%  M20/M30/M50/M70-MOM30   the second, unrelated sleeve

Six variants. Ten names at 50% (the other half of the narrowing test) is queued, not run: six is
the lab's ceiling for one pre-registration.

WHAT THE LADDER CAN AND CANNOT SAY. The comparison with M0283's recorded rungs is rung for rung:
same preset (``monthly-hold-frac-gotrade``), same fees, same funding, same window. The calm
sleeve's picks are bit-identical to M0283's because the allocator is imported, not copied. Momentum
here has no trend gate and no cash (``trend=None``): a mix that steps aside is a different method,
and a gate would add the switch's own cost to the thing being priced. Share classes of one company
may both enter the momentum sleeve (GOOG/GOOGL before 2014); with 30 names that is a small and
symmetric distortion and is not tuned.

No arm inverts another, so no third no-opinion arm is needed: SPY alone is the zero-sleeve rung and
is in every trial.

Pure: every piece reads only bars dated <= ``data_date``; no clock, randomness or I/O.
"""

from __future__ import annotations

from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0283_calm_beside_spy import CALM, ALWAYS_SPY, CalmParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING
from datetime import date

ADDED = date(2026, 10, 31)

CALM30 = CalmParams(30, side="low")
CALM10 = CalmParams(10, side="low")
MOM30 = FactorParams("momentum", top=30, trend=None)


def _mix(sleeve_share: str, allocator, params) -> BlendParams:
    """``sleeve_share`` of equity in the hand-picked sleeve, the rest in SPY at all times."""
    s = Decimal(sleeve_share)
    return BlendParams((BlendPart(TIMING, ALWAYS_SPY, Decimal(1) - s), BlendPart(allocator, params, s)))


def _v(suffix: str, params: BlendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0294-{suffix}", family="M0294", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BLEND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0294",
    name="The smallest sleeve worth trading: when does a hand-picked slice stop paying its own fees?",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref="lab M0283 (calm beside SPY), M0278; Frazzini & Pedersen (2014); Jegadeesh & Titman (1993)",
    parent_id="M0283",
    hypothesis=(
        "M0283 held 30 calm stocks beside SPY. Per point of worst fall the book earned 0.15 with a "
        "30% sleeve, 0.20 with 50% and 0.24 with 70%, so the thin sleeve was the one rung no better "
        "than SPY alone, though the signal never changed. Reading: Gotrade charges a minimum per "
        "order whatever the slot, so a thirty-name sleeve that is 30% of the book has slots a third "
        "the size paying the same floor, and below some share a sleeve cannot pay its own bill. If "
        "so, the turn is a property of the fee schedule and the name count, not of the signal. "
        "Arms: the calm 30-name sleeve at 20% (the rung M0283 never ran; its 30, 50 and 70% rungs "
        "are recorded and are the comparison); the calm sleeve narrowed to 10 names at the same 30% "
        "share; and a second, unrelated sleeve -- the 30 strongest twelve-minus-one-month momentum "
        "names, no gate, no cash -- at 20, 30, 50 and 70%. All monthly, fractional shares at "
        "Gotrade's real fees on the owner's monthly top-up, on M0283's own preset. Predictions "
        "written before any result: return per point of worst fall (MAR) is flat or falling from "
        "20% to 30% and rises monotonically above 30% for the calm sleeve; the momentum sleeve "
        "turns within one rung of the same share; and ten names at 30% sit above thirty names at "
        "30% (the fewer, fatter slots pay fewer minimums). Run lab names and lab turnover alongside "
        "to price the floor directly."
    ),
    expected_failure=(
        "Most likely the turn is not the fees. Trading cost is a few tenths of a point a year at "
        "this size, while a sleeve's share moves the book's market sensitivity by far more, so the "
        "ladder will track the sleeve's beta and the two sleeves will turn at different shares: a "
        "calm sleeve dilutes a rising market's pull and a momentum sleeve adds to it. A second way "
        "to fail: the momentum sleeve is a widely published edge (1993) that the dev window can "
        "only show from before the crowd traded it, and unfiltered it suffers the 2009 rebound, so "
        "its ladder may read the crash and not the fee floor. Third, the six arms cannot separate "
        "'the floor' from 'the share' unless ten names at 30% moves clearly; a small move would be "
        "noise at one draw. None of these is a reason to tune the share points or the name counts "
        "after the fact."
    ),
    candidates=(
        _v("L20-CALM30", _mix("0.2", CALM, CALM30),
           "20% the calm 30 beside 80% SPY: the thin rung M0283 never ran"),
        _v("L30-CALM10", _mix("0.3", CALM, CALM10),
           "30% the calm 10 beside 70% SPY: same share as M0283's thin rung, fewer fatter slots"),
        _v("M20-MOM30", _mix("0.2", FACTOR, MOM30),
           "Second sleeve, 20%: the 30 strongest 12-1 momentum names, no gate, beside 80% SPY"),
        _v("M30-MOM30", _mix("0.3", FACTOR, MOM30),
           "Second sleeve, 30%: the same momentum 30 beside 70% SPY"),
        _v("M50-MOM30", _mix("0.5", FACTOR, MOM30),
           "Second sleeve, 50%: the same momentum 30 beside 50% SPY"),
        _v("M70-MOM30", _mix("0.7", FACTOR, MOM30),
           "Second sleeve, 70%: the same momentum 30 beside 30% SPY"),
    ),
    seen_keys=(
        "concept:minimum-fee-floor-sleeve-share-threshold",
        "concept:core-satellite-sleeve-share-dial-two-signals",
    ),
)
