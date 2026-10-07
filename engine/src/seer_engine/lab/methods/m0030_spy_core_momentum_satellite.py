"""M0030 — Hold the market as the core and add momentum on top: an SPY core with a residual-momentum satellite.

Source: a variation of M0029, after its test-window look; the lab's P7a F9 (a timed SPY core with
a plain-momentum satellite, +12.2% a year at a 19.2% worst fall on dev, failing only the old 15%
limit and a luck score it never had the moments to compute) is the closest prior.
Idea: M0029 (70% residual momentum, 30% calm stocks, fractional) was fully invested on 2016-2026
and still made 7.4% a year vs SPY's 13.6%: the decade's risk was lagging a few mega-cap leaders,
which an equal-weight 40-stock book barely owns. A core that holds SPY itself owns those leaders by
construction; a residual-momentum satellite (M0007-N20-RAW's book) adds the dev window's edge.

No new allocator: ``BLEND`` of the index ``TIMING`` allocator (hold SPY) and ``RESIDMOM``, each on
its fixed share of equity, in fractional shares (``monthly-hold-frac``) as paper would trade it.
Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 10, 7)

TIMED_SPY = TimingParams(hold="SPY", signal="SPY", rule="sma", n=200)  # F1/F9's core, verbatim
ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")


def _blend(core: TimingParams, core_share: str) -> BlendParams:
    c = Decimal(core_share)
    return BlendParams((BlendPart(TIMING, core, c), BlendPart(RESIDMOM, RAW20, Decimal(1) - c)))


def _v(suffix: str, params: BlendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0030-{suffix}", family="M0030", rules=MONTHLY_HOLD_FRAC, allocator=BLEND,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0030",
    name="Hold the market as the core and add momentum on top: an SPY core with a residual-momentum satellite",
    family="stock-core-satellite",
    source_kind="variation",
    source_ref="M0029's test look; P7a F9-SPY200M70-MOM30; M0007-N20-RAW as the satellite",
    parent_id="M0029",
    hypothesis=(
        "M0029's test look showed the 2016-2026 risk was lagging a few mega-cap leaders, not "
        "crashing. Holding SPY itself as the core owns those leaders by construction, and the "
        "residual-momentum satellite (M0007-N20-RAW, +15.0% a year on dev) adds the edge. On dev, "
        "with the SPY 200-day filter on both parts: 70% core + 30% satellite (C70T) should land "
        "near F9's +12% a year at a worst fall under 20% (F9 had 19.2% with a weaker satellite), "
        "and 50/50 (C50T) near +13% at a similar worst fall, both with a smoother ride than either "
        "part alone and so a luck score above 0.90. The always-on core (C50A, the satellite still "
        "filtered) is evidence for what the filter costs and buys: it should break the 20% limit "
        "in 2008 (SPY fell about 55%; half of that is about 27%)."
    ),
    expected_failure=(
        "A timed SPY core is F1's 200-day rule, whose dev record is a fraction of a point a year "
        "ahead of SPY with whipsaw exits; the satellite carries all of the edge, so the 70% core "
        "dilutes it to barely above SPY and the luck score falls short of 0.90. The 50/50 version "
        "inherits the momentum book's 1998 shock at half weight plus the core's whipsaws and lands "
        "near the 20% limit. C50A breaks the limit in 2008."
    ),
    candidates=(
        _v("C70T", _blend(TIMED_SPY, "0.7"), "70% SPY under its 200-day filter, 30% residual-momentum top 20"),
        _v("C50T", _blend(TIMED_SPY, "0.5"), "50% SPY under its 200-day filter, 50% residual-momentum top 20"),
        _v("C50A", _blend(ALWAYS_SPY, "0.5"),
           "50% SPY always held, 50% residual-momentum top 20 (still filtered): what the core's filter buys"),
    ),
    seen_keys=("concept:spy-core-momentum-satellite", "concept:core-satellite"),
)
