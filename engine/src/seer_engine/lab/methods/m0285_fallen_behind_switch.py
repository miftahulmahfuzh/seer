"""M0285 — The fallen after the storm: the members furthest below their 200-day average, bought only
while SPY is above its own 200-day average.

Variation of M0282 (moving-average distance; Avramov, Kaplanski & Subrahmanyam, working paper 2018).
Reserved by Sera batch 20261023-2029 as an ``idea`` row; this file refines it and keeps its id.

WHY. M0282's mirror arm BOT20 (the 20 sized members whose 21-day average sits furthest below their
200-day average) beat its top arm on the dev store, almost all of it in 2009-2015, and fell 69% (86%
on the survivorship-check store) because it held the fallen straight through 2000-2002 and 2008.
This method asks whether the bounce can be kept without the fall by putting the one market filter
the lab already uses in front of it. Long-term reversal itself is old and published (De Bondt &
Thaler 1985), so a dev lead is likely to be a lead of the era, not a discovery.

REUSE, NAMED. The picking logic is M0282's, imported unchanged (``MadParams``, ``MadAllocator``):
the same pool, band (hold 20, keep while inside 40), equal slots, monthly, fractional shares at
Gotrade's real fees. ``FallenAllocator`` only carries its own id, because the lab's digest reads
the allocator id and M0282 has already run BOT20 and TOP20-SW: with M0282's id two of this
method's four arms would be refused as repeats. **So BOT20 and TOP20-SW below are the same rules
as M0282's arms of the same name, re-run under this id so all four arms share one frame**; their
numbers should reproduce M0282's, and a difference is a finding about the lab, not the method.

ARMS.
    BOT20-SW      the 20 lowest MAD behind the SPY 200-day switch (all cash while SPY closes at or
                  below its 200-day average): the treatment
    BOT20-SW-PLC  placebo: a blind hash-order draw with TOP20's book size and entry count, behind
                  the same switch -- the no-opinion arm; it prices what the switch plus the
                  monthly habit does to a book that holds no view
    TOP20-SW      M0282's one eligible arm, for the same-frame comparison
    BOT20         no switch: the habit-off twin, so the switch's effect is priced, not assumed

Pure: no clock, randomness, files or network; reads only bars dated on or before ``data_date`` and
share counts filed by it.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0282_moving_average_distance import MadAllocator, MadParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 10, 23)


class FallenAllocator(MadAllocator):
    """M0282's allocator under its own id (see the module docstring for why)."""

    id = "M0285"


FALLEN = FallenAllocator()


def _v(suffix: str, params: MadParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0285-{suffix}", family="M0285", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FALLEN, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0285",
    name=("The fallen after the storm: the members furthest below their 200-day average, bought "
          "only while SPY is above its own 200-day average"),
    family="stock-moving-average-distance",
    source_kind="variation",
    source_ref="Variation of M0282; long-term reversal after De Bondt & Thaler (1985).",
    parent_id="M0282",
    hypothesis=(
        "M0282's mirror arm (the 20 sized members whose 21-day average sits furthest below their "
        "200-day average) beat the top arm on the dev store by 3.9 points a year, almost all from "
        "the 2009-2015 bounce (+19.1 points a year vs SPY; +15.9 on the survivorship-check store), "
        "but fell 69% (86% on the check store) because it held the fallen straight through "
        "2000-2002 and 2008. Test whether the bounce can be kept without the fall: the same pool, "
        "band (top 40), equal slots, fractional shares at Gotrade's real fees on the owner's "
        "monthly top-up, behind the SPY 200-day switch. Arms: BOT20-SW; BOT20-SW-PLC (a matched "
        "blind draw behind the same switch, the no-opinion arm); TOP20-SW (M0282's eligible arm "
        "re-run, for a same-frame comparison); and BOT20 with no switch (the habit-off twin). "
        "Prediction written before any result: BOT20-SW beats its switched draw by 2+ points a "
        "year and leads SPY in 2009-2015 on both stores."
    ),
    expected_failure=(
        "In order of likelihood. (1) This is long-term reversal, which the lab has rejected "
        "(M0069, M0073); the switch re-enters after the bounce has begun, so it misses the "
        "steepest part of the rebound, and the check store's dead companies take back the rest. "
        "(2) BOT20-SW ties its switched draw: whatever lead BOT20 had was the 2009 rebound "
        "alone, which no ranking is needed to catch. (3) The switch's cash drag in a rising "
        "2009-2015 leaves the book behind SPY there, the first filter. (4) The published-anomaly "
        "fade: reversal is old, so a dev lead is likely to be an old edge. Any of these is a "
        "rejection, not a reason to tune the windows afterwards. Read the survivorship-check "
        "store before believing any lead."
    ),
    candidates=(
        _v("BOT20-SW", MadParams(signal="bottom", switch=True),
           "The 20 sized members furthest below their 200-day average, held while inside the "
           "bottom 40, all cash while SPY closes at or below its 200-day average"),
        _v("BOT20-SW-PLC", MadParams(signal="control", switch=True, seed=1),
           "Placebo behind the same switch: top-book size and monthly entries drawn blind from "
           "the same pool, no opinion on which names"),
        _v("TOP20-SW", MadParams(signal="top", switch=True),
           "M0282's eligible arm re-run under this id for a same-frame comparison"),
        _v("BOT20", MadParams(signal="bottom"),
           "No switch: the habit-off twin of BOT20-SW (M0282's mirror arm re-run under this id)"),
    ),
    seen_keys=(
        "concept:long-term-reversal-trend-switch",
        "concept:moving-average-distance-mirror-switched",
    ),
)
