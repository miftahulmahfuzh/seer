"""M0237 — An SPY core with a near-the-high high-volatility satellite.

Source: variation of M0232 (Chen, Chen, Tu, Wang & Wang 2026, proximity to the 52-week high and
the risk-return trade-off) on M0030's core-satellite frame; reserved by Sera 20261108-0813.

Idea: M0232-NEAR-HIVOL was the one stock-picking book the lab has measured that kept its edge on
the survivorship-check store, but as a twenty-name equal-weight book it lost to SPY in 2009-2015
and its twenty-year lead was earned in 2002-2008. The container, not the signal, is the suspect:
an equal-weight twenty-name book bets against the market's shape before it picks a stock. So the
tilt is asked to be only a slice. No new allocator: ``BLEND`` of the always-held SPY core
(``TIMING`` with ``rule="always"``, M0030's C50A core) and M0232's own allocator with its recorded
NEAR-HIVOL or PLC1 params. The SPY 200-day switch lives inside M0232's params, so it applies to
the satellite only and the core keeps compounding, which is what the idea asks for.

Assumption written down before any result: the idea names seven arms (three weights of the tilt,
three weights of the placebo, a pure-SPY control) and a method carries at most six variants. The
pure-SPY control is dropped because the lab's own benchmark is deposit-matched total-return SPY at
the same real fees and the same funding, which is exactly that control.

Pure: every read is of bars dated <= ``data_date``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0232_proximity_conditioned_risk import (
    N20,
    PROX,
    ProxRiskParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 11, 8)

ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")  # the core never steps aside
NEAR_HIVOL = ProxRiskParams(N20, band=4, pick="hivol")  # M0232-NEAR-HIVOL's params, verbatim
PLC1 = ProxRiskParams(N20, band=None, pick="placebo", seed=1)  # M0232-PLC1's params, verbatim


def _mix(sat: ProxRiskParams, sat_share: str) -> BlendParams:
    s = Decimal(sat_share)
    return BlendParams((BlendPart(TIMING, ALWAYS_SPY, Decimal(1) - s), BlendPart(PROX, sat, s)))


def _v(suffix: str, params: BlendParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0237-{suffix}", family="M0237",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=BLEND, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0237",
    name=("SPY core with a near-the-high high-volatility satellite: keep the market's shape, "
          "add the one tilt that survives the honest tape"),
    family="M0237",
    source_kind="variation",
    source_ref=("M0232-NEAR-HIVOL and its placebo M0232-PLC1; frame of M0030's core-satellite "
                "blend; reserved by Sera 20261108-0813"),
    parent_id="M0232",
    hypothesis=(
        "M0232-NEAR-HIVOL (the twenty wildest names inside the fifth of the index closest to its "
        "52-week high) was the only arm of six that beat SPY on the owner's deposits (+10.0% vs "
        "+7.2% a year), the only one the breadth report called 'pays in both' narrow and broad "
        "markets (+1.2% / +2.6%), and the only stock-picking book this lab has measured that EARNS "
        "MORE on the survivorship-check store (+10.0% -> +11.4%, worst fall 23.5% -> 24.9%) while "
        "its mirror FAR-HIVOL collapsed (+7.1% -> +3.6%, fall 40.9% -> 56.1%). But as a standalone "
        "twenty-name equal-weight book it lost to SPY by 6.9 points a year in 2009-2015 and its "
        "whole twenty-year lead came from 2002-2008 (folds 2 of 4, won 2003-2008, lost "
        "2009-2014). The diagnosis is not the signal, it is the container: an equal-weight "
        "twenty-name book is betting against the market's shape before it picks a stock, and since "
        "2018 that bet has lost for every strategy this lab has tried. So stop asking the tilt to "
        "be the whole book. Arms, all on M0030's core-satellite frame at Gotrade's real fees in "
        "fractional shares on the owner's monthly top-up, with the SPY 200-day switch applied to "
        "the SATELLITE only so the core keeps compounding: C70-S30, C50-S50 and C30-S70 holding "
        "that much always-held SPY and the rest in M0232-NEAR-HIVOL's twenty names; and the "
        "placebo mixes, the same weights with the satellite filled by M0232-PLC1's hash-order "
        "placebo, so any lead has to come from the tilt and not from the mix. The idea's pure-SPY control is the lab's own deposit-matched total-return SPY benchmark (same fees, same funding), so it is not a seventh arm: a method carries at most six variants. "
        "SUCCESS, and "
        "this is the only test that matters: a mix beats deposit-matched SPY TR in 2009-2015 by a "
        "positive margin, keeps its worst fall under 20%, and beats its own placebo mix by 1 point "
        "a year or more. Note the published-anomaly discount: the anchoring effect behind this "
        "dates to 2004 and the dev window can only show it before the crowd traded it."
    ),
    expected_failure=(
        "The satellite's 2002-2008 edge is the only thing it has, so every mix lands between SPY "
        "and NEAR-HIVOL in exactly the proportion of its weight, which would prove the tilt adds "
        "nothing the core does not already own and would close the 52-week-high direction for "
        "good. Two more ways it fails: the always-held core takes the 2008 fall in full on its "
        "70% to 30% share, so the worst fall may break 20% before the tilt matters; and the "
        "satellite's own SPY switch moves it to cash while the core stays in, so each mix holds "
        "more SPY than its label in a downturn and the lead over SPY shrinks toward zero by "
        "construction. If the placebo mix lands within a point of the tilt mix, the whole result "
        "is the mix and not the pick."
    ),
    candidates=(
        _v("C70-S30", _mix(NEAR_HIVOL, "0.3"),
           "70% always-held SPY, 30% near-the-high high-volatility twenty"),
        _v("C50-S50", _mix(NEAR_HIVOL, "0.5"),
           "50% always-held SPY, 50% near-the-high high-volatility twenty"),
        _v("C30-S70", _mix(NEAR_HIVOL, "0.7"),
           "30% always-held SPY, 70% near-the-high high-volatility twenty"),
        _v("C70-S30-PLC1", _mix(PLC1, "0.3"),
           "70% always-held SPY, 30% hash-order placebo twenty: the tilt's own control at 70/30"),
        _v("C50-S50-PLC1", _mix(PLC1, "0.5"),
           "50% always-held SPY, 50% hash-order placebo twenty: the tilt's own control at 50/50"),
        _v("C30-S70-PLC1", _mix(PLC1, "0.7"),
           "30% always-held SPY, 70% hash-order placebo twenty: the tilt's own control at 30/70"),
    ),
    seen_keys=(
        "concept:spy-core-nearhigh-hivol-satellite",
        "concept:core-satellite-proximity-conditioned-risk",
    ),
)
