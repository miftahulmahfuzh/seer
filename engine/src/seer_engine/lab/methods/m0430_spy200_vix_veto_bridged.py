"""M0430 — SPY's 200-day switch with a veto that reads the whole crash, not the last dip.

Source: variation of M0422, whose reversed arm never took effect. Its veto read the most recent
run of closes under the 200-day average, and in June 2009 that was a two-session dip with a fear
peak of 31, not the 2008 crash (peak 80.9). With a small peak in view the "fear has drained"
test never fired, so the veto produced the control's trades exactly and the sign of the signal
stayed unmeasured.

The fix is the episode, and only the episode: runs under the average that are separated by
fewer than BRIDGE sessions above it are one episode (an assumption: 63 sessions, a quarter, is
mine), and the peak is the highest VIX close inside the whole bridged span. The exit is the
plain 200-day exit in every arm and the way back in is the plain 200-day re-entry; a veto arm
refuses that re-entry while VIX stands ``fall`` or more under the episode peak, for VETO_WINDOW
sessions after the episode's last below-average close (the expiry is an assumption; without
one the veto could hold a book out for good). ALWAYS is the no-opinion arm, to price the habit
of switching apart from the opinion. Same frame as M0422 so the paired difference is the veto:
SPY only, monthly, fractional, Gotrade fees, M0404's 253-bar lookback. Reads only bars dated
<= ``data_date``. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0404_spy200_rebound_reentry import (
    BENCH,
    EXIT_GATE,
    LOOKBACK,
    SMA_N,
)
from seer_engine.lab.methods.m0422_spy200_vix_fall_reentry import (
    VIX,
    FallParams,
    VixFallTrendSwitch,
    _below,
    _check,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import trend_on

ADDED = date(2026, 11, 1)
#: Sessions above the 200-day average that still count as one episode.
BRIDGE = 63
#: Sessions after the episode's last below-average close during which the veto still reads it.
VETO_WINDOW = 63
_VIX_ROWS = LOOKBACK + 10


def bridged_episode(h: History, i: int) -> tuple[int, int, int] | None:
    """The latest below-200-day episode at or before bar ``i``: (start, end, sessions_since_end).

    Runs under the average split by fewer than BRIDGE sessions above it are merged. None when
    history is short or no below-average close lies inside the lookback.
    """
    if i + 1 < SMA_N:
        return None
    close = h.close
    lo = max(SMA_N - 1, i - (LOOKBACK - 1))
    j = i
    while j >= lo and not _below(close, j):
        j -= 1
    if j < lo:
        return None
    end = j
    start = j
    above = 0
    while j >= lo:
        if _below(close, j):
            start, above = j, 0
        else:
            above += 1
            if above >= BRIDGE:
                break
        j -= 1
    return start, end, i - end


def bridged_peak(h: History, series: MarketSeries, start: int, end: int,
                 data_date: date) -> float | None:
    """Highest VIX close dated inside bars ``start``..``end`` of SPY's history."""
    d0 = h.dates[start].astype("datetime64[D]").astype(object)
    d1 = h.dates[end].astype("datetime64[D]").astype(object)
    vals = [v for d, v in series.upto(VIX, data_date, last=_VIX_ROWS) if d0 <= d <= d1]
    return max(vals) if vals else None


def fear_draining(h: History, series: MarketSeries, data_date: date, fall: float) -> bool:
    """True when VIX is at least ``fall`` under the peak of the bridged episode just ended."""
    i = h.index_of(data_date)
    if i is None:
        return False
    ep = bridged_episode(h, i)
    if ep is None:
        return False
    start, end, gap = ep
    if gap > VETO_WINDOW:
        return False
    peak = bridged_peak(h, series, start, end, data_date)
    now = series.value_on(VIX, data_date)
    if peak is None or now is None or peak <= 0:
        return False
    return bool(now <= peak * (1.0 - fall))


class BridgedVetoSwitch(VixFallTrendSwitch):
    """100% SPY, plain 200-day exit, a veto on the way back in that reads the whole crash."""

    id = "M0430"

    def _on(self, history: Mapping[str, History], series: MarketSeries, data_date: date,
            held: frozenset[str], p: FallParams) -> bool:
        if p.entry == "always":
            return True
        plain = trend_on(history, data_date, EXIT_GATE)
        h = history.get(BENCH)
        if BENCH in held or p.entry == "sma200" or h is None:
            return plain
        return plain and not fear_draining(h, series, data_date, p.fall)


SWITCH = BridgedVetoSwitch()


def _v(suffix: str, params: FallParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0430-{suffix}", family="M0430", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SWITCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0430",
    name="SPY's 200-day switch, kept out while the fear index drains (veto made to bind)",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0422, whose reversed arm never took effect",
    parent_id="M0422",
    hypothesis=(
        "The 200-day switch is old (1992 banded, 2007 Faber) and VIX has traded since 1993, so "
        "no fresh anomaly and little fade argument. M0422 found that coming back early on a "
        "fear drop matched the plain switch at best and deepened the worst fall; its reversed "
        "arm, refusing the 200-day re-entry while fear drains, produced the control's trades "
        "exactly because it read a 2-session dip in June 2009 (peak 31) instead of the 2008 "
        "crash (peak 80.9). Here episodes separated by under 63 sessions above the average are "
        "merged, so the peak is the crash's. Arms fixed before the run: SPY200 (plain switch, "
        "control), VETOTHIRD and VETOHALF (200-day re-entry refused while VIX stands 1/3 or "
        "1/2 under the bridged episode peak, for 63 sessions after its end) and ALWAYS (SPY "
        "every session, no opinion, to price the habit apart from the opinion). VETOTHIRD "
        "blocks more than VETOHALF. Binding is a precondition: the veto arms must trade "
        "differently from SPY200, checked on the dev store before registering, reading only "
        "whether trades differ. SUCCESS: a veto arm beats SPY200 in 2009-2015 with a worst "
        "fall no deeper than SPY200's, a majority of walk-forward folds, DSR >= 0.90. "
        "Assumptions: BRIDGE 63 and VETO_WINDOW 63 are mine; peak capped at the 253-session "
        "lookback."
    ),
    expected_failure=(
        "Holding off re-entry after the 200-day says buy means missing the first leg up: V "
        "recoveries (2009, 2020-style) pay most just after fear has drained, so the veto likely "
        "costs return and may deepen the opportunity gap while only helping a double-dip "
        "(2001-2002, 2008 rallies) it rarely meets. Trade counts stay in the tens, so profit "
        "factor and the luck bar are close to meaningless. 2009-2015 had no bear market, so a "
        "result there can be good for the wrong reason. No interest on cash is modelled, which "
        "flatters the veto's time out. M0376, M0381 and M0389 found VIX overlays on this switch "
        "cost return and added nothing in 2008, the prior against this."
    ),
    candidates=(
        _v("SPY200", FallParams("sma200"), "Control: plain symmetric 200-day switch, monthly"),
        _v("VETOTHIRD", FallParams("veto", 1 / 3),
           "200-day re-entry refused while VIX is a third under the bridged episode peak"),
        _v("VETOHALF", FallParams("veto", 0.5),
           "As VETOTHIRD but only while VIX is half under the peak: blocks less"),
        _v("ALWAYS", FallParams("always"), "No-opinion arm: SPY held every session"),
    ),
    seen_keys=(
        "concept:vix-drain-veto-of-sma200-reentry",
        "concept:bridged-episode-fear-peak",
    ),
)
