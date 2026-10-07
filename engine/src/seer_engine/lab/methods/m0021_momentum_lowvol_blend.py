"""M0021 — Blend the residual-momentum book with a calm-stock book: two engines in one portfolio.

Source: general knowledge (momentum and low volatility as low-correlated factor premia; Asness,
Moskowitz & Pedersen 2013 on combining styles; Blitz & van Vliet 2007 on the low-volatility
anomaly), built from the lab's own parts: M0007's residual-momentum book (and M0011's brake on
it) and P7a's F5 calm-stock book.
Idea: every risk control tried on the residual-momentum book so far sells after a fall. A second
source of return whose bad periods do not line up with momentum's should shrink the worst fall
without selling anything: half the equity runs the residual-momentum top 20, half runs the 20
calmest members (lowest 60-day volatility), both re-picked monthly behind the SPY 200-day filter.

No new allocator: the lab's ``BLEND`` runs each sleeve on its fixed share of equity, and a stock
picked by both sleeves gets the sum of its two weights. Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20, RESIDVOL, ResidVolParams
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_factor import FACTOR, FactorParams

ADDED = date(2026, 10, 7)

CALM20 = FactorParams(rank="lowvol", top=20)  # F5-LV60-N20-TREND's book, verbatim
BRAKED = ResidVolParams(RAW20, Decimal("0.14"), 21)  # M0011-RAW20-TV14-N21 (on paper as RM)


def _blend(mom_share: str, *, braked: bool) -> BlendParams:
    mom = Decimal(mom_share)
    momentum = BlendPart(RESIDVOL, BRAKED, mom) if braked else BlendPart(RESIDMOM, RAW20, mom)
    return BlendParams((momentum, BlendPart(FACTOR, CALM20, Decimal(1) - mom)))


def _v(suffix: str, params: BlendParams, rationale: str, rules=MONTHLY_HOLD) -> Candidate:
    return Candidate(id=f"M0021-{suffix}", family="M0021", rules=rules, allocator=BLEND,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0021",
    name="Blend the residual-momentum book with a calm-stock book: two different engines in one portfolio",
    family="stock-multi-factor-blend",
    source_kind="knowledge",
    source_ref="M0007-N20-RAW, M0011-RAW20-TV14-N21 and F5-LV60-N20-TREND blended with BLEND; "
               "Asness, Moskowitz & Pedersen (2013); Blitz & van Vliet (2007)",
    parent_id="M0011",
    hypothesis=(
        "Every risk control tried on the residual-momentum book (stops, basket brakes, weekly "
        "re-entry) sells after a fall; only the volatility brake helped. A second return source "
        "whose bad periods differ should cut the worst fall without selling: the calmest members "
        "lag in strong markets but held up in 2000-02 and 2008. 50% M0007-N20-RAW (+15.0% a year, "
        "19.6% worst fall) plus 50% F5-LV60-N20-TREND (+7.6%, 31.4% worst fall alone, but a "
        "different worst stretch) should land near +11-13% a year with a worst fall near 13-15% "
        "and a higher Sharpe than either half; braking the momentum half as M0011 does should "
        "take the worst fall toward 10-12% at +9-10% a year. A 70/30 split keeps more of "
        "momentum's return and should still sit under the 20% limit."
    ),
    expected_failure=(
        "The calm book's own 31% worst fall came with the SPY filter on, so it is a fall inside "
        "a rising market (the 1999 flight from utilities and staples into tech), and the blend "
        "inherits half of it; worse, calm stocks and momentum overlap in calm bull years and both "
        "halves fall together in sharp shocks (Aug 1998, Oct 2008), so the worst fall is only a "
        "little smaller while return is diluted toward SPY's and the luck score drops."
    ),
    candidates=(
        _v("B50-RAW", _blend("0.5", braked=False),
           "Half residual momentum (M0007-N20-RAW), half the 20 calmest members (F5-LV60-N20-TREND)"),
        _v("B50-TV14", _blend("0.5", braked=True),
           "Same, with M0011's one-month volatility brake on the momentum half (RM's book)"),
        _v("B70-RAW", _blend("0.7", braked=False),
           "70% residual momentum, 30% calm stocks: keep more of momentum's return"),
    ),
    seen_keys=(
        "concept:momentum-lowvol-blend",
        "concept:multi-factor-blend",
    ),
)
