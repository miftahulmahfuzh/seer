"""M0225 — The honest yardstick, repaired: the size-weighted top 100 once multi-class companies have a size.

Source: variation of M0221 (the cap-weighted top N), its analysis and the data-wish it queued on
multi-class share counts; reserved by Sera batch 20261018-2051, which asked for M0221's six arms
carried here unchanged as the pre-registered twin on the repaired store.

Why it exists. M0221 asked whether a book shaped like the market, built from the store's own
members, tracks SPY. It did not: about 2 points a year behind over 1996-2015 and 5 to 6 behind in
2009-2015, and about 2.7 points a year of the 2009-2015 gap survived taking fees, deposits and cash
drag out by hand. Its analysis named the cause it could see: Visa, Mastercard, Meta, Berkshire,
Comcast, UPS, Ford and Alphabet after 2014 had prices but no company size, because they file their
share count per class (or in tags the reader skipped). Since 2026-10-18 the store reads the count
class by class from each filing (2009 on) and folds unlisted classes into the listed one they
convert into. Nothing else changed: the prices are byte-identical, so every M0221 trial still
compares like for like and the only thing that differs between M0221's run and this one is the
size data.

How. The allocator is M0221's ``CapTopAllocator`` unchanged, under its own id (``M0225``): a
trial's configuration is its rules, its allocator id and its params, and M0221's six configurations
already ran on the dev window. A new id is the honest way to record the same rule measured on new
data: it is one more look the lab counts, which is what re-measuring after a data change is. The
blind control's hash order is M0221's own (``draw`` keys on "M0221", not on the allocator id), so
R50 holds exactly the names M0221's R50 would have held wherever both stores size them.

The share-class rule is M0221's too, and it is still right on the repaired store. Two listed
classes that trade (GOOG/GOOGL from 2014-04-03, FOX/FOXA, NWS/NWSA, LBTYA/LBTYK in their spans) now
answer each class's own count, which differ, so both stay and add up to the company. Before
2014-04-03 the index lists Google's one class under both tickers and both answer the identical
whole-company count; the identical-count collapse keeps one. In the dev window it collapses
nothing else.

Originals: M0221's six arms, params identical (C50, C100, C20, C50-SW, E50, R50). Amendment 1,
pre-registered in the same commit as the originals and run straight after them with
``lab run --amend``: E100, the equal-weight top 100, the one arm M0225's own hypothesis adds
(the 6-variant cap per batch is why it rides as an amendment rather than a seventh original).

Assumptions written before any result. 2009-2015 market-value coverage rose from 62-69% to 62-75%
of member-days; what is still unknown is mostly members with no bars at all (Celgene, Alexion,
Express Scripts, Walgreens, Time Warner, DirecTV...), foreign filers on 20-F/40-F and a few
successor tickers. So the repair can close only the part of the gap that came from missing sizes,
not the part that came from missing prices. Rules are ``monthly-hold-frac-gotrade``. Pure: reads
only bars and share counts dated <= ``data_date``.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0221_cap_weighted_top_n import (
    CapTopAllocator,
    CapTopParams,
    WeightMatchedCapTopAllocator,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 18)


class RepairedCapTopAllocator(CapTopAllocator):
    """M0221's cap-weighted top N, recorded under M0225: the same rule on the repaired size data."""

    id = "M0225"


CAPTOP = RepairedCapTopAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: CapTopParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0225-{suffix}", family="M0225", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CAPTOP, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


E100_AMENDMENT = Amendment(
    added=ADDED,
    why="The equal-weight top 100 beside the size-weighted top 100, on the repaired store",
    hypothesis=(
        "Pre-registered in the same commit as the six originals, before any result. M0221 found "
        "that within the top 50, equal weight beat size weight in 2009-2015 (14.4% a year against "
        "11.9%), partly because the giants that led that era had no size and could not be held "
        "at their true weight. E100 holds the same top 100 as C100 at 1/100 each. Prediction: on "
        "the repaired store the size-weighted top 100 closes on the equal-weight top 100 in "
        "2009-2015, so the 2009-2015 lead of equal weight over size weight shrinks from M0221's "
        "2.5 points (top 50) to under a point; over 1996-2015 E100 earns about the same as C100 "
        "within a point, and trails SPY."
    ),
    expected_failure=(
        "A hundred equal slots on a 20M IDR account are about $15 each at the start, where "
        "Gotrade's minimum fees bite hardest, so E100 may trail on fees alone in the early years. "
        "And if equal weight still leads size weight by 2 points or more in 2009-2015, the gap "
        "was not the missing sizes but the missing prices (the acquired winners the store cannot "
        "price) or a real tilt of that era away from the biggest names."
    ),
    candidates=(
        _v("E100", CapTopParams(100, weighting="equal", cap=None, trend=None),
           "Contrast: the same top 100 by market value at equal weight, no switch"),
    ),
)


# ---- amendment 2 (2026-10-20): the honest control this method has never had --------------------
#
# M0225 has no shape-matched control at all. Its margin is still quoted against R50, which trades
# 0.195x and turns over 0.424x what C50 does -- a stone, not a measuring stick. The previous set
# deliberately did not draw one: the identical chassis had just missed on M0221 at 1.95x turnover,
# and drawing the twin under the same rule would have spent a run to re-observe the same structural
# miss under a different id. The rule that closes that axis now exists (`lab.control_weight`), so
# the twin is drawn with both halves at once: M0221's matched draw for the names and the weight
# assignment for the vector.
#
# The hash namespace stays M0221's (`DRAW_KEY`, inherited through `WeightMatchedCapTopAllocator`),
# so this arm draws the same names AND pays them the same rungs as M0221's wherever both stores
# size the same company -- which is the only way the before-and-after measures the data repair and
# nothing else. That is the same reason `draw` hardcodes "M0221" and it now covers two axes.

WEIGHT_AMENDED = date(2026, 10, 20)


class RepairedWeightMatchedAllocator(WeightMatchedCapTopAllocator):
    """M0221's weight-matched blind book, recorded under M0225: the same rule on the repaired data.

    Not one line of behaviour differs from ``M0221-A2``. A new allocator id is the honest way to
    record the same rule measured on new data -- a trial's configuration is its rules, its
    allocator id and its params, and M0221's is already recorded -- and it is also the only way,
    since ``trials`` carries a global ``UNIQUE (config_digest, window)``.
    """

    id = "M0225-A2"


WMATCHED = RepairedWeightMatchedAllocator()


def _aw(suffix: str, allocator: Any, params: CapTopParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate: its own ``added``, its own allocator, and the declaration of which
    recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``). It is DECLARED and never
    inferred from the target, and it sits outside ``config_digest`` because ``config_text`` names
    its three attributes by hand. An arm that declares nothing retires nothing, so leaving this off
    would leave M0225 blocked after the measurement was taken."""
    return Candidate(id=f"M0225-{suffix}", family="M0225", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=WEIGHT_AMENDED,
                     owner_inputs=(), supersedes=supersedes)


WEIGHT_AMENDMENT = Amendment(
    added=WEIGHT_AMENDED,
    why=(
        "M0225 has no shape-matched control at all: its margin is quoted against R50, which trades "
        "0.195x and turns over 0.424x the book it controls, and the twin was deliberately not "
        "drawn until a rule existed that closes the weight axis as well as the name axis"
    ),
    hypothesis=(
        "Written before this arm ran. C50 earned 5.85% a year of the owner's money on the dev "
        "window and R50 earned 6.74% against the same 7.19% SPY total return, so the recorded "
        "reading is that the blind draw BEATS the book by 0.89 points -- and R50 got there on 73 "
        "trades where C50 paid for 375. R50's hash carries no date term, so it drew fifty names "
        "once in 1996 and held them for twenty years; the only fees it ever paid were the ones "
        "membership forced on it. C50-PLC is the same fifty-name blind book with two things "
        "changed and nothing else: the number of names it re-draws each month is C50's own number "
        "of entrants that month, and the weights it pays them are C50's own weights that month, "
        "largest first, down a ladder that puts the names it already held above the ones entering "
        "this month. Predictions. Shape, and it is the one that decides whether the money reading "
        "is admissible: C50-PLC lands inside 0.80x-1.25x of C50 on both trades and turnover. "
        "Twin, and it is the sharpest prediction available here because the twin has already run: "
        "M0221's identical arm landed at 372 trades and 0.4620 turnover against a book re-run at "
        "375 and 0.4568, and earned 9.94% against that book's 5.85%. M0225's book re-runs on "
        "today's store at the same 375 and 0.4568 -- the repair is exactly what made M0221's book "
        "read like M0225's -- so this arm should land within about 0.02x of M0221's on both axes "
        "and within a few tenths of a point of its 9.94%, and a wider gap than that is the "
        "remaining share-count difference showing up in the control, which is itself worth "
        "knowing. Money: an honest control trades about five times as often as R50 and pays those "
        "fees, which on its own would make it earn LESS than R50's 6.74% -- but M0221's twin says "
        "the ladder's effect dominates the fee bill by a wide margin, so the prediction here is "
        "the uncomfortable one: this control earns MORE than R50, C50's deficit WIDENS from -0.89 "
        "to somewhere near -4, and the lab will have replaced a small unexplained gap with a large "
        "one. No arm of this method is for promotion; it is a yardstick."
    ),
    expected_failure=(
        "M0221's own matched draw on this identical chassis landed at 1.03x trades and 1.95x "
        "turnover, so the name axis is the half already known to work here and the weight axis is "
        "the half the new rule closes. M0225's E50 pays 1.68x against M0221's 1.60x on identical "
        "names and identical trades, so the repaired store is slightly MORE dispersed and the "
        "control has slightly further to travel; if this arm misses the band where M0221's "
        "cleared it, the repair is the difference and that is the finding. Second, paying a "
        "foreign vector can raise turnover rather than lower it: C50 is cheap because a "
        "cap-weighted book is nearly drift-neutral, and a control whose target moves with the real "
        "book's prices while its holding moves with its own crosses the 1%-of-equity resize band "
        "more often, not less. If that is what happens, it is the finding, it is recorded, and no "
        "fifth assignment rule is tried. Third, and this is the one that would matter most: the "
        "margin this arm produces may be large and may not be about stock picking at all. A "
        "control matched on trades and turnover is still a FIXED-weight book pushed back to its "
        "proportions every month, while the book it controls lets its biggest companies run and "
        "never trims them, and rebalancing is a return source in its own right -- this chassis "
        "already shows a smaller version of it, since E50 earns more than C50 on identical names. "
        "If the deficit lands near M0221's -4, that reading is the honest one and it must be "
        "published with the mechanism beside it, not as evidence that blind picking beats size. "
        "Fourth, one blind draw is one sample: the top rung sits on a single name for twenty "
        "years, and seed 1 is the only seed either twin has. A second seed is not run here and the "
        "arm is not re-drawn for a better number under any result."
    ),
    candidates=(
        _aw("C50-PLC", WMATCHED, CapTopParams(50, pick="random", seed=1, trend=None),
            "Placebo, shape-matched on both axes: the same fifty-name blind book hash-drawn at "
            "C50's own monthly churn, and paid C50's own weight vector instead of its own sizes",
            supersedes=("M0225-R50",)),
    ),
)

METHOD = Method(
    id="M0225",
    name=(
        "The honest yardstick, repaired: the size-weighted top 100 once multi-class companies "
        "have a size"
    ),
    family="market-shape-yardstick",
    source_kind="variation",
    source_ref="M0221 analysis; data-wish on multi-class share counts",
    parent_id="M0221",
    hypothesis=(
        "M0221's size-weighted top 100 trailed SPY by about 2 points a year without fees in "
        "2009-2015, and Visa, Mastercard, Meta, Berkshire, Comcast and UPS had no company size in "
        "the store. Once share counts are summed across classes, re-run the same top 100 and top "
        "50 (10% ceiling, no switch, fractional, Gotrade fees) beside an equal-weight top 100. "
        "Prediction: the fee-free gap to SPY in 2009-2015 shrinks to about a point a year; "
        "whatever remains is the members with no prices at all, which only a fuller price history "
        "can close. If it tracks SPY, adopt its curve as a store-matched second yardstick for "
        "every member book. Sera 20261018-2051 adds: carry M0221's six arms unchanged (top 20, 50 "
        "and 100 by size, the switched top 50, the equal-weight top 50 and the blind-draw "
        "control) as the pre-registered twin on the repaired store, so the before-and-after "
        "comparison measures the data fix and nothing else; the equal-weight top 100 runs as this "
        "method's first amendment. Funded predictions against M0221's recorded trials: C100 and "
        "C50 gain 1 to 3 points a year in 2009-2015 (C50 from 11.9% toward 14%, C100 from 10.3% "
        "toward 13%, SPY 16.6%) and about half a point a year over 1996-2015; C20 gains the most "
        "in 2009-2015, because Visa, Mastercard, Meta and Berkshire enter a 20-name book at once; "
        "E50 and R50 move least, because they never weighted by size or never ranked by it. No "
        "arm is for promotion: success is a ruler that tracks SPY, and cap weighting is the market "
        "itself, not a published anomaly."
    ),
    expected_failure=(
        "Most of the 2009-2015 gap was the members with no prices at all, not the members with "
        "no size: coverage of member-days rose only from 62-69% to 62-75%, and the unpriced "
        "names (Celgene, Alexion, Express Scripts, Walgreens, Time Warner, DirecTV, Activision, "
        "Electronic Arts) were among the era's best large companies. If C100 still trails SPY by "
        "4 points a year or more in 2009-2015 (M0221 was 6.3), the repair closed a small part of "
        "the gap and the ruler stays bent until the prices arrive. Second, the switched top 50 "
        "may stay dev-eligible exactly as M0221's did, by sitting out 2008; that is not a "
        "candidate and the same fold rule refuses it. Third, fees on a 100-name book at about "
        "$15 a slot dominate the early years whatever the size data says. Fourth, folding "
        "Berkshire A into B and Visa B/C into A may raise those two to the 10% ceiling in the "
        "top 20, so C20's gain may be capped by its own ceiling."
    ),
    candidates=(
        _v("C50", CapTopParams(50, trend=None),
           "M0221-C50 unchanged: top 50 by market value, cap-weighted, 10% ceiling, no switch"),
        _v("C100", CapTopParams(100, trend=None),
           "M0221-C100 unchanged: top 100 by market value, cap-weighted, 10% ceiling, no switch"),
        _v("C20", CapTopParams(20, trend=None),
           "M0221-C20 unchanged: top 20 by market value, cap-weighted, 10% ceiling, no switch"),
        _v("C50-SW", CapTopParams(50, trend=SW),
           "M0221-C50-SW unchanged: top 50 by market value, cap-weighted, behind the 200-day switch"),
        _v("E50", CapTopParams(50, weighting="equal", cap=None, trend=None),
           "M0221-E50 unchanged: the same top 50 by market value at equal weight, no switch"),
        _v("R50", CapTopParams(50, pick="random", seed=1, trend=None),
           "M0221-R50 unchanged: 50 members in a fixed size-blind hash order, cap-weighted"),
    ),
    seen_keys=(
        "concept:cap-weighted-top-n-repaired-share-classes",
        "concept:market-shape-yardstick-before-after-data-fix",
    ),
    amendments=(E100_AMENDMENT, WEIGHT_AMENDMENT),
)
