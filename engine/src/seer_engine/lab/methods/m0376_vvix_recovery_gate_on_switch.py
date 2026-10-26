"""M0376 -- The rarer, recovery-timed VVIX gate M0373 proved was real, re-stacked on F4's SPY
200-day switch: cash whenever EITHER the switch is off OR volatility-of-volatility sits near the
top of its own range and has not yet recovered, decided monthly throughout.

Variation on M0373. Source paper unchanged: Huang, Schlag, Shaliastovich & Thapar (2019),
"Volatility-of-Volatility Risk", Journal of Financial and Quantitative Analysis 54(6), 2423-2452.
Reserved by Sera 20261026-0703.

This family has now tried the gauge two ways. M0370 stacked a loose, fixed-week VVIX gate (fires
at 1.20x the trailing-year median, 13.3% of eligible sessions) on the 200-day switch at a weekly
cadence: rejected, because the gate mostly re-confirmed a switch already off and a blind twin at
the same rate captured most of its lead. M0373 then stripped the switch out entirely, made the
trigger rarer (90th/95th percentile of VVIX's own trailing year) and recovery-timed (cash until
VVIX falls back to its own trailing median, not a fixed number of weeks), and read monthly: also
rejected, but for a different reason -- GATE-90 and GATE-95 clearly beat their own coin-flip twins
by 4.4-5.2 points a year (the first time this family's real arm has clearly beaten its blind
control; recorded trials #1298-#1301), so the timing information is real. What sank it was the
missing switch: standalone, VVIX's short, sharp spikes cannot catch a slow grinding decline the
way a 200-day trend filter can, and the worst fall widened to 47.4% (worst year 2002, -21.6%),
nearly double the ~20% every M0370 variant held.

M0373's own recorded verdict asked for exactly this next step: take the two pieces that just
proved themselves -- the rarer percentile trigger and, above all, the recovery-based exit, which
had never been isolated from a fixed-week exit before -- and put them back on top of the 200-day
switch, at the monthly cadence throughout that the lab's own cadence lessons call for (CLAUDE.md;
M0370's own analysis), not M0370's weekly re-check. The allocator here is new code (M0370's switch
check plus M0373's percentile/recovery gate functions, reused directly rather than re-derived),
but reuses M0373's pure gate/recovery/blind functions (``gate_standing_down``,
``blind_standing_down``, their shared ``Params``) unmodified, and F4's own trend condition
(``strategies.f_factor.trend_on``) unmodified.

Candidates: GATE-90 and GATE-95 are the switch plus the recovery gate at each tier; BLIND-90 and
BLIND-95 are the dressing twins the lab's rule requires whenever an arm steps aside on a signal --
a hash fired at that tier's own measured rate (the SAME ``BLIND_RATE``/``BLIND_DURATION``
calibration M0373 measured against the dev store before its own file was committed: VVIX's
firing/episode statistics do not depend on the switch, since both GATE and BLIND here read/scan
VVIX exactly as M0373 did, only gated by one more AND condition), restacked on the same switch, no
VVIX value read. No plain-switch control is registered: SPY behind only the 200-day switch,
monthly-hold-frac-gotrade, no VVIX gate at all, is config-identical to a trial already on record --
M0251-SPY-200 (``TimingParams(hold="SPY", signal="SPY", rule="sma", n=200)``, trial in the dev
window (trial #815), funded +9.2%/yr vs SPY TR's own +7.7% for the same deposits, worst fall
18.9%; ``lab run`` refuses a second trial of an identical
configuration, digests ignoring the id) -- so GATE-90/95 and BLIND-90/95 are compared against that
recorded trial directly, exactly as M0373 compared its own arms against M0251-HOLD. This also
completes the family's 2x2 on the switch dressing question across two pre-registrations: switch
alone (M0251-SPY-200, real condition, no VVIX habit), switch + blind stand-down (M0370's own
BLIND-2W/4W, habit with no opinion), and now switch + VVIX stand-down, both ways, here.

Success: GATE-90 or GATE-95 beats total-return SPY with worst fall <= 25%, PF >= 1.3, DSR >= 0.90,
a positive 2009-2015 edge and a majority of walk-forward folds, beats M0251-SPY-200's recorded
funded return by more than fees alone would predict, AND clears its BLIND twin by more than the
two tiers would be expected to differ from each other -- otherwise the lead is the time spent in
cash, not the recovery timing, and the family (both the stacked and the standalone route now
tried) is exhausted.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0373_vvix_recovery_gate import (
    BLIND_DURATION,
    BLIND_RATE,
    RECOVERY_CAP_SESSIONS,
    TIER_QUANTILE,
    TRAIL,
    Params,
    blind_standing_down,
    gate_standing_down,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 26)

# F4's own trend gate (strategies.f_factor.trend_on): close(d) > SMA(200) of SPY's last 200 closes,
# strict. Constructed once; trend_on reads only ``.trend`` off it. Identical to M0370's own _TREND.
_TREND = FactorParams(rank="momentum", top=1, trend=("SPY", 200))


def _check(params: object) -> Params:
    if not isinstance(params, Params):
        raise TypeError(f"params must be Params, got {type(params).__name__}")
    return params


def standing_down(history: Mapping[str, History], series: MarketSeries, data_date: date, p: Params) -> bool:
    """M0373's own recovery/blind stand-down, unmodified: percentile-and-recovery for ``mode="gate"``,
    a frame-matched hash for ``mode="blind"``. Independent of whether the switch is on."""
    if p.mode == "gate":
        return gate_standing_down(history, series, data_date, TIER_QUANTILE[p.tier])
    return blind_standing_down(history, series, data_date, p.seed, p.tier)


@dataclass(frozen=True, slots=True, eq=False)
class Prepared:
    history: Mapping[str, History]
    series: MarketSeries


class SwitchAndRecoveryGateAllocator:
    """SPY at full weight unless EITHER F4's 200-day switch is off OR the VVIX (or blind)
    recovery-timed stand-down is active; cash otherwise. See module docstring."""

    id = "M0376"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        gate_need = TRAIL + RECOVERY_CAP_SESSIONS if p.mode == "gate" else TRAIL + BLIND_DURATION[p.tier]
        return max(gate_need, 200)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def _run(self, history: Mapping[str, History], series: MarketSeries, data_date: date,
              held: frozenset[str], p: Params) -> tuple[Target, ...]:
        if len(series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        if not trend_on(history, data_date, _TREND):
            return ()
        if standing_down(history, series, data_date, p):
            return ()
        h = history.get("SPY")
        if h is None or (h.index_of(data_date) is None and "SPY" not in held):
            return ()  # a symbol with no bar dated d is never a NEW target
        target = target_from_close("SPY", last_close(h, data_date), equal_weight(1))
        return () if target is None else (target,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no gate reading and no target."""
        return self._run(history, EMPTY_SERIES, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> Prepared:
        return Prepared(history, EMPTY_SERIES)

    def prepare_market(self, market: Any) -> Prepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return Prepared(market.history, series)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Prepared):
            raise TypeError(f"prepared must be Prepared, got {type(prepared).__name__}")
        return self._run(prepared.history, prepared.series, data_date, held, _check(params))


GATE_ON_SWITCH = SwitchAndRecoveryGateAllocator()


def _v(suffix: str, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0376-{suffix}", family="M0376", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=GATE_ON_SWITCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0376",
    name=(
        "The rarer, recovery-timed VVIX gate re-stacked on F4's 200-day switch, monthly throughout"
    ),
    family="macro-vvix-tail-gate",
    source_kind="variation",
    source_ref=(
        "Huang, Schlag, Shaliastovich & Thapar (2019), Volatility-of-Volatility Risk, "
        "Journal of Financial and Quantitative Analysis 54(6), 2423-2452 -- a variation on M0373 "
        "(restores the 200-day switch M0373 removed, keeping M0373's rarer percentile trigger and "
        "recovery-timed exit rather than M0370's looser threshold and fixed-week exit)"
    ),
    parent_id="M0373",
    hypothesis=(
        "M0373 found that a rarer (90th/95th percentile), recovery-timed VVIX gate, standing alone "
        "with no trend switch underneath it, carries real timing information: GATE-90 and GATE-95 "
        "clearly beat their own coin-flip twins by 4.4-5.2 points a year (recorded trials "
        "#1298-#1301), the first time this family's real arm has clearly beaten its blind control. "
        "But standalone it still lost to simply staying invested, and its worst fall widened to "
        "47.4% (worst year 2002, -21.6%) -- VVIX's short, sharp spikes are not built to catch a "
        "slow grinding decline the way the 200-day trend switch M0370 used is, which kept every one "
        "of its own variants' worst falls near 20%. This file tests the piece that actually proved "
        "itself -- the rarer percentile trigger and, above all, the recovery-based exit, which has "
        "never been isolated from a fixed-week exit before M0373 -- placed back on top of the "
        "200-day switch, at a monthly cadence throughout (no weekly re-check, the cadence M0370's "
        "own analysis and CLAUDE.md's cadence lessons say costs several points a year for no "
        "safety). GATE-90 and GATE-95 reuse M0373's own percentile-and-recovery gate functions "
        "unmodified, combined with F4's trend condition: cash whenever EITHER the switch is off OR "
        "the gate is standing down. BLIND-90 and BLIND-95 are the dressing twins the lab's rule "
        "requires whenever an arm steps aside on a signal -- the same hash fired at each tier's own "
        "measured rate and mean episode length M0373 calibrated against the dev store before its "
        "own file was committed (unchanged here, since VVIX's firing and recovery statistics do not "
        "depend on the switch), restacked on the same switch, no VVIX value read. No plain-switch "
        "control is registered: SPY behind only the 200-day switch at this cadence is "
        "config-identical to the already-recorded M0251-SPY-200 trial, so GATE-90/95 and BLIND-90/95 "
        "are compared against that recorded trial directly, exactly as M0373 compared its own arms "
        "against M0251-HOLD. Success: GATE-90 or GATE-95 beats total-return SPY with worst fall "
        "<= 25%, PF >= 1.3, DSR >= 0.90, a positive 2009-2015 edge and a majority of walk-forward "
        "folds, beats M0251-SPY-200's recorded funded return by more than fees alone would predict, "
        "AND clears its BLIND twin by more than the two tiers would be expected to differ from each "
        "other."
    ),
    expected_failure=(
        "VVIX and VIX spikes mostly co-occur because both react to the same equity sell-offs, and "
        "the 200-day switch is itself slow -- it only turns off well after a decline is underway. "
        "The two failure modes this file cannot distinguish in advance: (1) by the time the switch "
        "has already turned off, VVIX has very likely already spiked too, so the gate mostly "
        "re-confirms a book that is already in cash and adds nothing but a few extra weeks of "
        "whipsaw around re-entry -- the exact mechanism that sank M0370's looser, weekly version; "
        "or (2) the rarer, recovery-timed version is genuinely different because it can catch a "
        "sharp, short correction that never breaks the 200-day trend, in which case it earns its "
        "keep as an early warning the switch alone would have missed. Expect the BLIND twins to "
        "separate these: if GATE-90/95 and BLIND-90/95 land close together, the lead (if any) over "
        "M0251-SPY-200 is the habit of stepping aside, not the timing, repeating M0370's outcome "
        "despite the improved gate shape. The gate is silent before 2008-01-03 (fewer than 252 prior "
        "VVIX rows), so every variant trades exactly like M0251-SPY-200 over 1996-2007 and the whole "
        "comparison lives in 2008-2015, the fuller-coverage half of the dev window -- any edge that "
        "does appear should be checked against `lab survivorship` before it is trusted. Restoring "
        "the switch should at minimum restore the ~20% worst-fall discipline M0370's variants held, "
        "since the switch's own exit dominates in a slow decline; if the worst fall is still much "
        "wider than that, the gate's extra cash periods are doing something unexpected to the "
        "re-entry timing. Published 2019, after the dev window and most of the test window, so a "
        "dev result here says nothing about whether the mechanism has since been arbitraged away. "
        "If the gate adds nothing once the switch is restored, both routes this family has now "
        "tried -- patch the stacked design (M0370), and go it alone (M0373) -- will have failed for "
        "distinct, well-understood reasons, and M0373's own recorded opinion already said not to "
        "spend a further id sweeping the percentile threshold or the recovery baseline beyond this."
    ),
    candidates=(
        _v("GATE-90", Params(mode="gate", tier="top90"),
           "The 200-day switch, plus cash whenever VVIX sits at or above the 90th percentile of "
           "its own trailing year, back once it has recovered to at or below that year's median"),
        _v("GATE-95", Params(mode="gate", tier="top95"),
           "The same switch-plus-recovery-gate, a rarer 95th-percentile bar (the dial's other end)"),
        _v("BLIND-90", Params(mode="blind", tier="top90", seed=1),
           "Frame-matched control: the switch, plus a hash firing at GATE-90's own measured rate "
           "for GATE-90's own measured mean episode length, no VVIX value read"),
        _v("BLIND-95", Params(mode="blind", tier="top95", seed=1),
           "The same blind control restacked on the switch, calibrated to GATE-95's rate and mean "
           "episode length"),
    ),
    seen_keys=(
        "concept:vvix-tail-risk",
        "concept:volatility-of-volatility",
        "concept:recovery-based-exit",
        "concept:percentile-threshold-gate",
        "concept:frame-matched-blind-draw",
        "concept:recovery-percentile-vvix-gate-stacked-on-trend-switch",
    ),
)
