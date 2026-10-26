"""M0370 — A second, independent gate on VVIX (volatility of volatility): stand aside for a few
weeks whenever it jumps far above its own trailing-year level, on top of (not instead of) F4's
SPY 200-day switch.

Source: Huang, Schlag, Shaliastovich & Thapar (2019), "Volatility-of-Volatility Risk", Journal of
Financial and Quantitative Analysis 54(6), 2423-2452. Reserved by Sera 20261026-0703.
Idea: VVIX prices how uncertain the options market is about the VIX itself, not about the stock
market directly -- a warning about a disorderly air-pocket in volatility, which HSST find predicts
near-term equity tail risk beyond the VIX level alone. The store has carried VVIX since inception
and the only method that has ever read it is M0144's machine-learned ranker, where it was one
column among many market-state features buried inside trees that the lab's own analysis found
added nothing; no rule-based, standalone test of VVIX has run. Host: SPY alone, not a stock-picking
book, so the test is kin-clean of every momentum family the lab has already failed (lab/hardgate.py
D14; `lab survivorship`'s coverage note and M0039's own precedent for the same reason). Decided
monthly, re-checked weekly (``monthly-rank-weekly-resize-frac-gotrade``), fractional shares at
Gotrade's real fees: SPY at full weight while BOTH F4's 200-day switch is on AND the VVIX gate has
not fired in the last ``stand_down_weeks``; cash otherwise.

The VVIX gate, read point in time through ``Market.series`` (``market_fields = ("series",)``): on
a session d with at least 252 prior VVIX rows, none older than 7 days, it fires when VVIX(d) is at
or above 1.20x the median of the 252 VVIX rows strictly before d (the same 1.20x ratio M0039 used
for its own VIX "spike" gate, not tuned for this idea). Once fired, the book is in cash on every
decision session that falls within ``stand_down_weeks`` x 5 trading sessions of that fire, found by
scanning SPY's own session dates back from d -- a stateless re-derivation, not carried state (as
M0177's hysteresis gate). Before 2008-01-03 the store has fewer than 252 VVIX rows and the gate
never fires, so a VVIX variant trades exactly like the plain switch until then (the lab's standing
rule for a series that starts late: M0039 for VIX3M, M0191 for VIX).

Measured against the dev store before this file was committed (not a trial; nothing here spends a
look): of 1,962 eligible sessions from 2008-01-03 to 2015-10-16, 260 (13.3%, about 1 session in
7.5) crossed 1.20x their own trailing-year median -- a far more common event than "tail risk"
suggests, because the trailing median is itself slow-moving and a sustained choppy stretch keeps
lifting the current value above even a year-old baseline. Consolidated into stand-downs, this
puts the 2-week gate out of the market on 106 of 1,186 weekly checks (8.9%) and the 4-week gate on
147 of 1,186 (12.4%). Variants: VVIX-2W and VVIX-4W sweep the dial's two ends; SWITCH is the plain
200-day switch with no VVIX gate at all (F1's own ``TimingAllocator``, no new code); BLIND-2W and
BLIND-4W are frame-matched controls, same stand-down length as their VVIX twin, but triggered by a
fixed hash of the seed and the session's own date at the SAME 13.3%-of-eligible-sessions rate the
VVIX gate measured above (``BLIND_RATE``, a constant fixed before any trial, not re-derived from a
recorded result) -- same habit, no opinion, so the pair prices what stepping aside this often costs
independent of whether VVIX timing is worth anything (the lab's "dressing" requirement: a reversed
or stepped-aside arm needs a no-opinion twin to separate the signal from the habit).

Success: VVIX-2W or VVIX-4W beats total-return SPY with worst fall <= 25%, PF >= 1.3, DSR >= 0.90,
a positive 2009-2015 edge and a majority of walk-forward folds, AND clears its BLIND twin by more
than the twins differ from each other -- otherwise the lead is the time spent in cash, not VVIX.
"""

from __future__ import annotations

import hashlib
import statistics
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 10, 26)

FEAR = "VVIX"
RATIO = 1.20  # fixed threshold: VVIX >= RATIO x its own trailing-year median fires the gate (M0039's SPIKE precedent)
TRAIL = 252  # trailing sessions behind the median baseline (about a year), excluding the session itself
STALE_DAYS = 7  # a VVIX row older than this is no reading at all (gate cannot fire, as M0039/M0191)
SESSIONS_PER_WEEK = 5  # trading sessions approximated per calendar week of stand-down
# The empirical fraction of eligible sessions (>= TRAIL prior VVIX rows, a fresh reading) that fired
# the VVIX gate on the dev store, measured once before this file was committed: 260 of 1,962 sessions,
# 2008-01-03 through 2015-10-16, at RATIO=1.20. Used only to calibrate BLIND's hash rate; never
# re-derived from a recorded trial.
BLIND_RATE = 260 / 1962

Mode = Literal["vvix", "blind"]

# F4's own trend gate (strategies.f_factor.trend_on): close(d) > SMA(200) of SPY's last 200 closes,
# strict. Constructed once; trend_on reads only ``.trend`` off it.
_TREND = FactorParams(rank="momentum", top=1, trend=("SPY", 200))


@dataclass(frozen=True, slots=True)
class Params:
    """``mode="vvix"`` reads VVIX; ``mode="blind"`` reads only VVIX's own freshness (never its
    value) and fires on a fixed hash instead, at ``BLIND_RATE``. ``stand_down_weeks`` is the dial
    (1-4 inclusive); ``seed`` only matters for ``blind``."""

    mode: Mode
    stand_down_weeks: int = 2
    seed: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.mode, str):
            raise TypeError(f"mode must be a str, got {type(self.mode).__name__}")
        if self.mode not in ("vvix", "blind"):
            raise ValueError(f"mode must be 'vvix' or 'blind', got {self.mode!r}")
        if isinstance(self.stand_down_weeks, bool) or not isinstance(self.stand_down_weeks, int):
            raise TypeError(f"stand_down_weeks must be an int, got {type(self.stand_down_weeks).__name__}")
        if not 1 <= self.stand_down_weeks <= 4:
            raise ValueError(f"stand_down_weeks must be in [1, 4], got {self.stand_down_weeks}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {
            "mode": self.mode,
            "stand_down_weeks": str(self.stand_down_weeks),
            "seed": str(self.seed),
            "ratio": repr(RATIO),
            "trail": str(TRAIL),
            "stale_days": str(STALE_DAYS),
            "sessions_per_week": str(SESSIONS_PER_WEEK),
            "blind_rate": repr(BLIND_RATE),
        }


def _check(params: object) -> Params:
    if not isinstance(params, Params):
        raise TypeError(f"params must be Params, got {type(params).__name__}")
    return params


def vvix_fired(series: MarketSeries, d: date) -> bool:
    """True when VVIX(d) is at or above ``RATIO`` x the median of the ``TRAIL`` rows strictly
    before d; False with fewer than ``TRAIL`` prior rows or a stale reading. Reads rows <= d."""
    rows = series.upto(FEAR, d, last=TRAIL + 1)
    if len(rows) < TRAIL + 1:
        return False
    if (d - rows[-1][0]).days > STALE_DAYS:
        return False
    median = statistics.median(v for _, v in rows[:-1])
    today = rows[-1][1]
    return median > 0 and today >= RATIO * median


def blind_fired(series: MarketSeries, d: date, seed: int) -> bool:
    """A fixed hash of ``seed`` and ``d``, true at ``BLIND_RATE`` of eligible sessions -- the same
    eligibility window as ``vvix_fired`` (fewer than ``TRAIL`` prior VVIX rows: never fires, so a
    blind variant also trades like the plain switch before VVIX exists), but never reads VVIX's
    value. Pure: a function of its inputs, no clock and no run-time randomness."""
    rows = series.upto(FEAR, d, last=TRAIL + 1)
    if len(rows) < TRAIL + 1:
        return False
    if (d - rows[-1][0]).days > STALE_DAYS:
        return False
    key = f"{seed}|{d.isoformat()}".encode()
    h = int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")
    return (h % 10_000_000) < round(BLIND_RATE * 10_000_000)


def standing_down(history: Mapping[str, History], series: MarketSeries, data_date: date, p: Params) -> bool:
    """True when a fire landed within the last ``stand_down_weeks`` x ``SESSIONS_PER_WEEK`` trading
    sessions through ``data_date`` (inclusive); a stateless scan over SPY's own session dates, as
    M0177's hysteresis gate. True (safe side) when SPY has no bar dated on or before ``data_date``."""
    h = history.get("SPY")
    if h is None:
        return True
    i = h.index_of(data_date)
    if i is None:
        return True
    scan = p.stand_down_weeks * SESSIONS_PER_WEEK
    for j in range(max(i - scan + 1, 0), i + 1):
        d = h.dates[j].item()
        hit = vvix_fired(series, d) if p.mode == "vvix" else blind_fired(series, d, p.seed)
        if hit:
            return True
    return False


@dataclass(frozen=True, slots=True, eq=False)
class Prepared:
    history: Mapping[str, History]
    series: MarketSeries


class StandDownAllocator:
    """SPY behind F4's 200-day switch, plus a second independent stand-down gate (see module
    docstring). Cash while either gate is off."""

    id = "M0370"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return 200 + p.stand_down_weeks * SESSIONS_PER_WEEK

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


STANDDOWN = StandDownAllocator()

SWITCH_PARAMS = TimingParams(hold="SPY", signal="SPY", rule="sma", n=200)


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0370-{suffix}", family="M0370", rules=MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0370",
    name=(
        "A second gate on volatility-of-volatility: stand aside a few weeks whenever VVIX jumps "
        "far above its own trailing-year level, on top of F4's SPY 200-day switch"
    ),
    family="macro-vvix-tail-gate",
    source_kind="paper",
    source_ref=(
        "Huang, Schlag, Shaliastovich & Thapar (2019), Volatility-of-Volatility Risk, "
        "Journal of Financial and Quantitative Analysis 54(6), 2423-2452"
    ),
    parent_id=None,
    hypothesis=(
        "Huang, Schlag, Shaliastovich and Thapar (published 2019, so the whole dev window to 2015 "
        "predates it and the dev result is a true out-of-sample test of the mechanism, not of a "
        "crowded trade) find that VVIX -- the uncertainty priced into the VIX itself, not into the "
        "stock market directly -- predicts near-term equity tail risk beyond the VIX level alone. "
        "The store has carried VVIX since inception but the only method ever to read it, M0144's "
        "learned ranker, buried it among many market-state columns the lab's own analysis found "
        "added nothing; no rule-based, standalone test has run. Host it on SPY alone (no stock "
        "picking, so the test is kin-clean of every momentum family already failed, unlike a "
        "factor book that would inherit that kin) behind F4's own 200-day switch, decided monthly "
        "and re-checked weekly, fractional shares at Gotrade's real fees. The VVIX gate is a "
        "second, independent layer: cash for stand_down_weeks whenever VVIX closes at or above "
        "1.20x the median of its own trailing 252 sessions (M0039's own 'spike' ratio, not tuned "
        "for this idea). Measured on the dev store before this file was committed: 260 of 1,962 "
        "eligible sessions (13.3%, 2008-2015) crossed that bar -- far more often than 'tail risk' "
        "suggests, because the trailing median is itself slow-moving. Variants: VVIX-2W and "
        "VVIX-4W sweep the one-to-four-week dial's ends; SWITCH is the plain 200-day switch with "
        "no VVIX gate (F1's existing allocator, unmodified); BLIND-2W and BLIND-4W are "
        "frame-matched controls, the same stand-down length as their VVIX twin but fired by a "
        "fixed hash at the SAME measured 13.3% rate, with no price or volatility information at "
        "all -- the no-opinion twin the lab's dressing check requires whenever an arm steps aside "
        "on a signal, so the VVIX pair's lead over the plain switch can be split into 'the timing "
        "was right' versus 'stepping aside this often helps regardless of when.' Success: a VVIX "
        "variant beats total-return SPY with worst fall <= 25%, PF >= 1.3, DSR >= 0.90, a positive "
        "2009-2015 edge and a majority of walk-forward folds, AND clears its BLIND twin by more "
        "than the two BLIND seeds would be expected to differ from each other."
    ),
    expected_failure=(
        "VVIX and VIX spikes mostly co-occur (both are reactions to the same equity sell-offs), so "
        "once F4's 200-day switch has already turned off, the VVIX gate rarely adds a NEW exit -- "
        "it mostly re-confirms a switch that is already out, and its only visible effect is a few "
        "extra weeks of whipsaw around the switch's own re-entries. At 13.3% of eligible sessions "
        "firing, the gate is active far too often to be a rare tail-risk warning: it reads more "
        "like 'VVIX is persistently elevated for stretches of a choppy market' than 'a jump', which "
        "is exactly the dressing check's job to catch -- expect BLIND-2W and BLIND-4W to capture "
        "most of VVIX-2W/4W's lead over SWITCH, because time spent in cash this often costs about "
        "the same whether or not VVIX chose the weeks. The gate is silent before 2008-01-03 (no "
        "252-session VVIX history), so a VVIX variant trades exactly like SWITCH over 1996-2007 and "
        "the whole comparison lives in 2008-2015 -- which is also the fuller-coverage half of the "
        "dev window (survivorship_coverage.py), so any edge that does appear should be checked "
        "against `lab survivorship` before it is trusted. Published 2019, well after the dev "
        "window and even after most of the test window, so a dev-window result says nothing about "
        "whether the signal has since been arbitraged away -- that risk is deferred to the test "
        "look, if one is ever spent here. Gotrade's fees on a single-instrument book that trades "
        "in and out several times a year are modest per trade but compound over 20 years; expect "
        "VVIX-4W to pay less in fees than VVIX-2W (fewer, longer stand-downs) but also to miss more "
        "of each recovery."
    ),
    candidates=(
        _v("SWITCH", TIMING, SWITCH_PARAMS,
           "Control: SPY behind only the 200-day switch on the same rules, no VVIX gate at all"),
        _v("VVIX-2W", STANDDOWN, Params(mode="vvix", stand_down_weeks=2),
           "The switch, plus cash for 2 weeks whenever VVIX crosses 1.20x its trailing-year median"),
        _v("VVIX-4W", STANDDOWN, Params(mode="vvix", stand_down_weeks=4),
           "The same gate, a 4-week stand-down (the dial's other end)"),
        _v("BLIND-2W", STANDDOWN, Params(mode="blind", stand_down_weeks=2, seed=1),
           "Frame-matched control: a 2-week stand-down fired by a hash at VVIX's own measured "
           "rate, no price or volatility information"),
        _v("BLIND-4W", STANDDOWN, Params(mode="blind", stand_down_weeks=4, seed=1),
           "The same blind control, a 4-week stand-down"),
    ),
    seen_keys=(
        "concept:volatility-of-volatility",
        "concept:vvix-tail-risk",
        "concept:stand-down-gate",
        "concept:frame-matched-blind-draw",
    ),
)
