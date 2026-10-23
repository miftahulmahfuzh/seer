"""M0300 — The size-to-equal dial again, with every rung pinned to the same exposure, so the
weighting term is one number instead of a range.

Source: variation of M0292 (the five-rung size-to-equal dial: monotone on every axis, funded
return 7.55% to 10.28% a year, worst fall 50.0% to 57.5%, and an end-to-end gap of 2.73 points a
year that could not be attributed because average exposure slid 91.22% to 97.52% with the rung),
and through it M0286, M0281/M0224/M0226 and M0222. M0127 (the rebalance-band ladder: the band is
what sets a held book's exposure -- 88.6% at 1% of equity, 98.6% with the band shut), M0266 and
M0270 (a point of exposure is priced by its era, 0.005 to 0.173 points a year, never a constant),
insight 492 (cash in lumps costs more than cash spread evenly). Reserved by Sera 20261023-1305 as
M0300.

THE ONE THING THIS METHOD EXISTS TO FIX. M0292 turned a clean dial and got a clean line, but two
numbers moved together. Each rung's weight is market value raised to a power, and the cadence was
M0286's EQ-DEPOSIT: a January anchor, never a sale to fund a buy, the month's deposit handed to
the names furthest below target. At the size end a holding's weight drifts the way its *target*
drifts, because market value is shares times price -- so the deposit finds almost no gap to fill
and the money banks as cash. At the equal end the targets stand still while prices move, gaps
open every month, and the deposit is spent. Weighting and exposure are collinear there by
construction, and M0292 could only report a range: a point of exposure has never been worth more
than 0.17 points a year on this chassis, so the 6.30-point exposure spread carries at most 1.07
of the 2.73, leaving **1.6 to 2.7 points** for the weighting itself. That range is the open term.

HOW THE RUNGS ARE PINNED. Two levers, both already in the lab, and neither of them the weighting:

- ``months=1, deposit=False``: the weights are re-set from scratch every month, so no rung carries
  an anchor and no rung has a deposit rule that depends on which names drift.
- ``monthly-hold-frac-gotrade-tband00``: the rebalance band shut to zero, so every non-zero gap is
  beyond it and every holding is traded back to its exact target each month. M0127 measured this
  lever end to end on a 20-name book -- 88.6%, 93.4%, 96.2%, 97.8%, 98.6% average exposure as the
  band closes from 1% of equity to nothing -- and M0266, M0270, M0271 and M0287 have all measured
  on the zero rung since, because a book that rebalances completely every month is the only
  chassis on which an exposure experiment means what it says.

The band is the lever that matters and the lab's own record says so: M0286 ran the size book at
``months=1`` already (M0286-MONTHLY) and still came out at 91.4% exposure against the equal book's
97.1%, because under a 20%-of-target band a size-weighted holding almost never drifts far enough
off its own drifting target to trade. Shut the band and it must.

THE SIXTH ARM IS A BRIDGE, NOT A RUNG. ``SIZE-M12`` is M0292-SIZE's parameters unchanged -- power
1, the January anchor, deposit steering, the 5% ceiling -- with the band shut and nothing else
touched. It is the one arm that moves a single lever against a recorded trial, and it buys two
readings the ladder alone cannot give:

- ``SIZE-M12`` against the recorded ``M0292-SIZE`` is the **exposure term at the size end**,
  measured rather than bounded: the same book, the same cadence, 91.22% exposure against whatever
  the shut band delivers.
- ``SIZE-M12`` against this method's own ``SIZE`` is the **cadence term** at matched exposure and
  matched fee structure: anchor-carried weights with deposit steering, against fresh monthly
  weights.

It is the habit-off half of a 2x2 whose habit-on half is ``SIZE``, it answers "is the opinion
worth what the habit costs" for the one habit this method introduces, and it costs no method id.

WHAT WAS MEASURED BEFORE THIS FILE WAS COMMITTED, so the predictions below can be read against
what was already known. A book-construction probe: no backtest, no return, no fall, no era
number. Three findings, each of which fixed a prediction and nothing else.

(1) The book is 137 names at the end of 1998, 220 in 2003, 294 in 2008 and 392 on the last dev
session. It is wide, and it gets wider.

(2) The method is not inert. The reserved row's second expected failure was that a zero band on a
book of several hundred sub-one-percent weights would produce orders below what Gotrade will fill,
the engine would refuse them, and exposure would not actually equalise. At plausible account sizes
($6k in 1998 rising to $120k by 2015) the share of book weight sitting in slots too small to clear
the fee floor at all is 0.002% at the size end in 1998 and 0.000% everywhere else. There is no
dead tail. That failure mode is ruled out in advance.

(3) **The fee slope the reserved row feared is real in level and absent in slope.** Gotrade's
trading fee has a $0.10 floor per order, and a monthly full rebalance sends one order per held
name: 137 to 392 orders a month at every rung alike. The floor therefore dominates, and the
estimated annual fee drag runs 3.3% of the account in 1998, 1.6% in 2003, 1.1% in 2008 and 0.5% in
2015 -- large, and **flat across the rungs to within 0.03 points a year at every date sampled**
(worst case 2015: 0.48% at power 0 against 0.51% at power 1). The drag is a level charge every
rung pays, not a slope that could masquerade as weighting. The estimate assumes the same average
monthly gap at every name; it is an order-count argument, and the order count is identical by
construction.

That probe is why this method is worth a method id: the two ways it could have been uninformative
were checked first and neither bites. What it cannot pre-empt is the *level*: every rung here pays
roughly a point a year more in fees than M0292's rungs did, so this ladder's returns are not
comparable to M0292's returns one for one. That is exactly why the bridge arm exists -- a
one-lever comparison inside the same fee regime.

Nothing here is a candidate and the hypothesis says so before any result. M0292's rungs fall 50%
to 58% in 2008 against the owner's 25% bar; a weighting dial with its exposure pinned does not
touch that, and pinning exposure near 100% can only make the fall deeper. Success is a
measurement.

Market-aware: reads ``shares`` (company size); without it, or without the market's membership
calendar, it targets nothing. Pure: reads only bars, share counts and index membership dated <= d.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0292_size_to_equal_dial import PowerParams, SizeToEqualDialAllocator
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND00

ADDED = date(2026, 10, 23)


class ExposurePinnedDialAllocator(SizeToEqualDialAllocator):
    """M0292's allocator exactly, under a new id so this ladder's digests are distinct.

    Subclassed rather than re-implemented, for the reason M0270 gives for doing the same to
    M0266's: the two ladders must not be able to drift apart. A recorded trial's digest is its
    allocator id plus its params plus its rule set, so the id alone keeps M0300's rungs separate
    from M0292's while the weighting arithmetic stays byte for byte the same code.

    ``SIZE-M12`` therefore differs from the recorded ``M0292-SIZE`` in its rule set and in this
    id, and in nothing else that touches a weight.
    """

    id = "M0300"


DIAL = ExposurePinnedDialAllocator()

# months=1, deposit=False: the weights are re-set from scratch every month, so no rung carries an
# anchor and no rung's cash flow depends on which names drifted. PowerParams refuses deposit=True
# at months=1 ("a book re-weighted every month has no month for the deposit to steer"), which is
# the validator agreeing with the design.
PINNED = {"months": 1, "deposit": False}


def _v(suffix: str, params: PowerParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0300-{suffix}", family="M0300",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND00, allocator=DIAL, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0300",
    name=(
        "Hold every rung of the size-to-equal dial at the same exposure, so the weighting term "
        "is one number instead of a range"
    ),
    family="portfolio-rebalancing",
    source_kind="variation",
    source_ref=(
        "M0292 (the size-to-equal dial: monotone everywhere, end-to-end gap 2.73 points a year, "
        "but average exposure slid 91.22% to 97.52% with the rung, so weighting and exposure are "
        "collinear there by construction and the honest answer was a 1.6-to-2.7 range); M0286 "
        "(the re-weighting cadence 2x2, and M0286-MONTHLY showing that re-weighting monthly does "
        "NOT fix exposure under a live band: 91.4% against the equal book's 97.1%); M0127 (the "
        "rebalance-band ladder: 88.6%, 93.4%, 96.2%, 97.8%, 98.6% exposure as the band closes to "
        "zero, which is what makes the band and not the cadence the right lever); M0266 and M0270 "
        "(the price of a point of exposure is an era, 0.005 to 0.173 points a year, never a "
        "constant); M0222 (the market-value core and the 5% per-company ceiling); insight 492 "
        "(cash in lumps costs more than cash spread evenly)"
    ),
    parent_id="M0292",
    hypothesis=(
        "M0292 measured a perfectly monotone size-to-equal dial -- funded return 7.55% a year at "
        "pure market-value weighting rising to 10.28% at equal slices over identical names, with "
        "the worst fall rising 50.0% to 57.5% alongside it -- and then could not say how much of "
        "that 2.73-point end-to-end gap was the weighting. Average exposure slid from 91.22% at "
        "the size end to 97.52% at the equal end, because its deposit-steered January-anchor "
        "cadence finds gaps to fill in an equal-weighted book and almost none in a size-weighted "
        "one, where each holding's weight drifts the way its own target drifts. The reportable "
        "answer was a range, 1.6 to 2.7 points a year, and the unqualified 2.8 points M0286 "
        "published was withdrawn. This method runs the identical five rungs -- power 0, 0.25, "
        "0.5, 0.75 and 1 on each name's market value, rescaled and capped at 5%, over the same "
        "F4-screened index members with a known point-in-time size, one listed class per "
        "identical share count -- with the two levers that pin exposure and touch no weight: the "
        "weights are re-set from scratch every month (months=1, no anchor, no deposit rule), and "
        "the rebalance band is shut to zero so every holding is traded back to its exact target "
        "every month. The band is the lever the lab's own record points at: M0286 already ran "
        "this book at months=1 under a 20%-of-target band and still came out at 91.4% exposure "
        "against the equal book's 97.1%, while M0127's band ladder moved a 20-name book's "
        "exposure from 88.6% to 98.6% by closing the band alone. The sixth arm is not a rung: "
        "SIZE-M12 is M0292-SIZE's parameters unchanged with only the band shut, so it prices the "
        "exposure term at the size end against a recorded trial by moving one lever, and prices "
        "the cadence term against this method's own SIZE at matched exposure and matched fees. "
        "Predictions, written before any result. (1) Average exposure is flat to within half a "
        "point across all five rungs and lands near 98-99%, which is the check that the fix "
        "worked; if it is not flat, nothing else here is readable and the verdict must say so "
        "first. (2) The funded return ladder stays monotone and rising toward EQUAL, because the "
        "internal evidence says exposure is not the main term -- carrying the whole 2.73 would "
        "need a point of exposure to be worth 0.43 points a year, against a best-ever measured "
        "0.17 on this chassis and about nothing in 2003-2008. (3) The end-to-end gap lands "
        "between 1.6 and 2.4 points a year rather than 2.73, and what it falls short by IS the "
        "exposure term, measured rather than bounded. (4) The worst fall still rises toward "
        "EQUAL and every rung still falls far past the owner's 25% bar, deeper than M0292's "
        "because pinned exposure means no cash cushion in 2008. (5) SIZE-M12 lands above "
        "M0292-SIZE's recorded 7.55% a year by roughly the exposure term, since it buys about 7 "
        "points of exposure for the fee cost of a full monthly rebalance. Nothing here is a "
        "candidate: a weighting dial cannot fix a 50%-plus fall, and pinning exposure can only "
        "deepen it. Success is a measurement, and the measurement closes the oldest open "
        "assumption this lab holds."
    ),
    expected_failure=(
        "The headline risk is that the pin does not hold. If average exposure still slopes across "
        "the rungs -- because a zero band cannot overcome something else that is size-dependent, "
        "or because the wide tail of a size-weighted book cannot be filled at the account sizes "
        "the early window runs at -- then this method has bought nothing and the verdict must say "
        "so in its first line rather than quoting a gap. A book-construction probe run before "
        "this file was committed says the dead tail is 0.002% of book weight at worst and zero "
        "almost everywhere, so inertness is ruled out, but the probe cannot prove the engine's "
        "realised exposure is flat; only the run can. Second, forcing a full rebalance every "
        "month on a 137-to-392-name book is expensive: the same probe estimates 3.3% of the "
        "account a year in fees in 1998, falling to 0.5% by 2015, because Gotrade's $0.10 per "
        "order floor is charged on one order per held name per month. That level is paid by every "
        "rung and it will push this whole ladder below M0292's, so the two ladders' returns are "
        "NOT comparable one for one and only the bridge arm's one-lever comparison is. The probe "
        "also says the drag is flat across rungs to within 0.03 points a year, but it assumes an "
        "equal average gap at every name; real small-company weights move more, so the equal end "
        "may trade slightly larger orders and pay slightly less of the floor, which would bias "
        "the ladder in the direction it is predicted to slope. Turnover and the shortfall "
        "decomposition must be reported per rung, and if the fee spread across rungs exceeds the "
        "exposure spread it replaced then nothing was gained and the verdict must say so. Third, "
        "the rungs may not separate at all: market value is distributed so unevenly that raising "
        "it to 0.25 is already most of the way to equal weighting, and M0292 is the only evidence "
        "they do separate. Fourth, the dev store cannot price about 40% of member-days and the "
        "missing names skew small, so every rung nearer equal is flattered here; the "
        "survivorship-check store must be read for all six arms, and M0292's unusual result -- "
        "the slope survived the honest tape even though the level did not -- is what this must be "
        "checked against. Fifth, pinning exposure near 100% removes the accidental cash cushion "
        "that let M0292's size end fall only 50%, so a deeper fall at every rung is expected "
        "rather than a surprise, and it makes a bad book worse without making it informative "
        "about anything but weighting. Finally the whole exercise is about a book that can never "
        "be a candidate: a clean answer changes what the lab believes about weighting and "
        "promotes nothing."
    ),
    candidates=(
        _v("EQUAL", PowerParams(power=Decimal("0"), **PINNED),
           "Power 0: every screened member at the identical weight, re-set monthly with the band "
           "shut -- the equal end of the dial with no cash allowed to bank"),
        _v("P25", PowerParams(power=Decimal("0.25"), **PINNED),
           "Power 0.25: a quarter of the way from equal slices toward the market's own shape"),
        _v("P50", PowerParams(power=Decimal("0.5"), **PINNED),
           "Power 0.5: the square root of market value, the halfway rung"),
        _v("P75", PowerParams(power=Decimal("0.75"), **PINNED),
           "Power 0.75: three quarters of the way toward the market's own shape"),
        _v("SIZE", PowerParams(power=Decimal("1"), **PINNED),
           "Power 1: each name at its market value, capped at 5% -- the market's own shape, with "
           "the same pin as every other rung"),
        _v("SIZE-M12", PowerParams(power=Decimal("1")),
           "The bridge, not a rung: M0292-SIZE's parameters unchanged -- the January anchor and "
           "deposit steering -- with only the rebalance band shut. One lever against a recorded "
           "trial, which prices the exposure term at the size end; and one lever against this "
           "method's own SIZE, which prices the cadence"),
    ),
    seen_keys=(
        "concept:exposure-pinned-weighting-dial",
        "concept:size-weighting-power-dial",
        "concept:equal-weight-vs-cap-weight",
        "concept:market-cap-weight",
        "concept:whole-market-core",
        "concept:weight-ceiling",
        "concept:rebalance-band-ladder",
        "concept:dose-response-ladder",
    ),
)
