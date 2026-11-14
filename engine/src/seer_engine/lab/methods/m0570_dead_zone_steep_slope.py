"""M0570 -- The dead-zone brake with an independent slope: wait out a wide zone, then cut hard.

Source: variation on M0550 (the volatility-sized dead zone), itself on M0115 (the fixed dead zone)
and M0109 (the proportional own-drawdown brake). Idea: M0115 and M0550 both traced one trade-off --
a wider dead zone is cheaper in calm years and gives back crash protection -- and both read it as
one knob. But in neither was the slope past the zone ever made steep. M0115's slopes ran 20 to 30
points of further fall before cash; M0550's ran 2 further standard deviations whatever the zone.
A wide zone followed by a gentle slope is still mostly invested deep into a crash, so the
protection those methods lost may belong to the gentle slope and not to the wide zone. This method
holds the zone where the recorded arms had it and moves only the slope: cash within 5 or 10 points
of further fall, or within half or one further standard deviation.

NO NEW CODE. The book, the shadow index, the one-year high, the weekly clock and both exposure
curves are M0109's, M0115's and M0550's, imported unchanged. ``DeadZoneParams`` already carries
``start`` and ``taper`` as two free numbers, and ``VolZoneParams`` already carries ``slope_sds``;
the recorded arms simply never set them steep. So every arm here is one of those two allocators at
a setting the lab has not run, and the only thing that differs from a recorded arm is the slope.

THE ARMS. Three slope ladders, each completed by recorded rungs that are cited and not re-run:

  * 20% zone: Z20-S05 (cash at a 25% fall), Z20-S10 (cash at 30%), and the recorded
    M0115-START20-T40 (cash at 40%, trial 1938).
  * 15% zone: Z15-S05 (cash at 20%), Z15-S10 (cash at 25%), and the recorded M0115-START15-T35
    and M0115-START15-T45 (trials 1935, 1936).
  * 4-standard-deviation zone: VOL4-S05 (cash half an SD further), VOL4-S1 (one SD further), and
    the recorded M0550-VOL4 (two SDs further, trial 2044).

Exposure moves in M0109's 0.05 steps and is read weekly, so a 5-point slope is in practice close
to a switch: all in above the zone, all out a little below it.

THE CONTROL IS CITED, NOT RE-RUN. The same book never braked, on the weekly clock, is
M0109-EW-ALL-W (trial 354; recorded again as M0115-CTRL and M0550-CTRL). It is the no-opinion arm
for every comparison here, and running it a fourth time would record a twin row and no evidence.

All arms trade the weekly resize preset at Gotrade's real fees, in fractional shares.
Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0109_book_drawdown_brake import WEEKLY
from seer_engine.lab.methods.m0115_drawdown_brake_dead_zone import DEAD_ZONE, DeadZoneParams
from seer_engine.lab.methods.m0550_vol_sized_dead_zone import VOL_ZONE, VolZoneParams

ADDED = date(2026, 11, 14)


def _fixed(suffix: str, start: str, taper: str, rationale: str) -> Candidate:
    params = DeadZoneParams(start=Decimal(start), taper=Decimal(taper))
    return Candidate(id=f"M0570-{suffix}", family="M0570", rules=WEEKLY, allocator=DEAD_ZONE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


def _vol(suffix: str, slope_sds: str, rationale: str) -> Candidate:
    params = VolZoneParams(taper=Decimal("1"), vol_mult=Decimal("4"), slope_sds=Decimal(slope_sds))
    return Candidate(id=f"M0570-{suffix}", family="M0570", rules=WEEKLY, allocator=VOL_ZONE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0570",
    name=(
        "The dead-zone brake with an independent slope: cut hard once triggered, instead of "
        "tapering from wherever the zone ends"
    ),
    family="book-drawdown-brake",
    source_kind="variation",
    source_ref=(
        "M0550 (the volatility-sized dead zone) and M0115 (the fixed dead zone), with the zone "
        "held at their recorded widths and only the slope past it made steep"
    ),
    parent_id="M0550",
    hypothesis=(
        "M0115 and M0550 both found one monotonic trade-off: however the dead-zone width is "
        "chosen (fixed, or sized from trailing volatility), a wider zone is cheaper in calm years "
        "and gives back more crash protection. Neither ever ran a steep slope: M0115 reached cash "
        "20 to 30 points of fall past the zone, M0550 two standard deviations past it. This "
        "method separates the two dials. It keeps the zone at recorded widths and makes only the "
        "slope steep, on M0109's book unchanged (the 50 most-traded index members at equal "
        "weight, the gross membership-free shadow, the one-year high, the weekly clock, "
        "fractional shares at Gotrade's real fees on the owner's monthly deposits), using "
        "M0115's and M0550's own allocators at settings they never ran. Arms: Z20-S05 and "
        "Z20-S10 (a 20% zone, cash at a 25% and a 30% fall), Z15-S05 and Z15-S10 (a 15% zone, "
        "cash at 20% and 25%), VOL4-S05 and VOL4-S1 (M0550's 4-standard-deviation zone, cash "
        "half and one standard deviation further). Each ladder is completed by recorded rungs, "
        "cited and not re-run: M0115-START20-T40 (trial 1938) for the 20% zone, "
        "M0115-START15-T35 and M0115-START15-T45 (trials 1935, 1936) for the 15% zone, M0550-VOL4 "
        "(trial 2044) for the volatility zone. The no-opinion arm is also cited: the same book "
        "never braked on the weekly clock is M0109-EW-ALL-W (trial 354). The recorded curve, as "
        "calm-year cost against never braking in 2009-2015 and worst fall: 9.9 points a year and "
        "17.8% with no zone, 5.6 and 28.0% at a 10% zone, 4.3 and 41.1% at 15%, 4.1 and 47.1% at "
        "20%, 2.5 and 48.3% at the 4-SD zone. Success, pre-registered: an arm that sits off that "
        "curve, meaning a 2009-2015 cost under 4.1 points a year (no dearer than the recorded "
        "15-20% zones) with a worst fall under 35% (well inside the 41-47% those zones gave). "
        "The stronger bar M0550 set, under 3 points with a worst fall under 25%, is reported "
        "too. If the two dials are one knob in disguise, each steep arm lands beside its own "
        "ladder's recorded rung and the slope is closed as a direction. Eligibility would still "
        "need a braked book to beat SPY TR on deposit-matched money with a worst fall under 20% "
        "and a majority of folds; the plain book underneath trailed SPY in M0109, M0115 and "
        "M0550, so a pass is unlikely and the measurement is the point. Portfolio insurance of "
        "this kind was published around 1990, long before the dev window ends."
    ),
    expected_failure=(
        "A steep slope is a stop-loss, and a stop-loss sells the bottom. The recorded 15% zone "
        "already showed the slope barely mattering: cash at 35% and cash at 45% gave 41.1% and "
        "41.3% worst falls, which says the damage is done inside the zone and in the re-entry, "
        "not on the slope. Three ways it fails. First, the worst fall may not improve much, "
        "because the account has already lost the whole zone before the cut and then misses the "
        "rebound: the brake reads the shadow book against its one-year high, so after a deep "
        "fall it stays in cash until the shadow climbs back inside the zone, and re-enters "
        "higher than it left. Second, the calm-year cost may rise instead of holding: a gentle "
        "slope trims a little on a dip that just crosses the zone, a steep one sells everything "
        "and buys it back a few weeks later, paying the round trip on the whole account. 2011's "
        "fall crossed 15%. Third, with exposure moving in 5-point steps on a weekly clock, a "
        "5-point slope and a 10-point slope may trade almost identically, so the two rungs of "
        "each ladder could be nearly one curve. And whatever the brake does, the book underneath "
        "is a bet against SPY's big-company shape and may still trail SPY TR after 2009."
    ),
    candidates=(
        _fixed("Z20-S05", "0.20", "0.25",
               "20% dead zone, then cash within 5 further points (all cash at a 25% fall)"),
        _fixed("Z20-S10", "0.20", "0.30",
               "20% dead zone, then cash within 10 further points (all cash at a 30% fall)"),
        _fixed("Z15-S05", "0.15", "0.20",
               "15% dead zone, then cash within 5 further points (all cash at a 20% fall)"),
        _fixed("Z15-S10", "0.15", "0.25",
               "15% dead zone, then cash within 10 further points (all cash at a 25% fall)"),
        _vol("VOL4-S05", "0.5",
             "M0550's 4-SD dead zone, then cash half a standard deviation further"),
        _vol("VOL4-S1", "1",
             "M0550's 4-SD dead zone, then cash one standard deviation further"),
    ),
    panel_exempt=(
        "chassis: a brake on the book's own account over M0109-EW-ALL-W's picks (the 50 "
        "most-traded index members at equal weight, a recorded book); only the exposure slope "
        "past the dead zone changes, the picks are the host's"
    ),
    seen_keys=(
        "concept:dead-zone-brake-independent-steep-slope",
        "concept:drawdown-brake-dead-zone",
        "concept:volatility-scaled-dead-zone",
    ),
)
