"""M0373 -- A standalone VVIX stand-aside gate, with no 200-day switch underneath: cash only while
volatility-of-volatility sits near the very top of its own trailing-year range, back in once it has
actually settled toward its own average, not after a fixed number of weeks.

Variation on M0370. Source paper unchanged: Huang, Schlag, Shaliastovich & Thapar (2019),
"Volatility-of-Volatility Risk", Journal of Financial and Quantitative Analysis 54(6), 2423-2452.
Reserved by Sera 20261026-0703.

M0370 stacked a VVIX gate on F4's SPY 200-day switch, firing whenever VVIX closed at or above
1.20x the median of its own trailing 252 sessions, re-checked weekly, cash for a FIXED
stand_down_weeks regardless of what VVIX did next. It was rejected: at that bar VVIX fired on
13.3% of eligible sessions -- far too often to read as "tail risk" -- and a frame-matched blind
draw at the same rate captured most of the lead over the plain switch, because the lab's weekly
read cadence was separately shown to cost several points a year against a monthly one (M0370's own
analysis; CLAUDE.md's "gate cadence" lessons).

This file tests the gauge on its own terms instead of patching the same shape:
  1. **Standalone** -- SPY is held at full weight whenever the gate is not firing, with no F4
     switch underneath it. A VVIX-only signal should stand or fall on its own effect size, not be
     allowed to borrow the switch's.
  2. **Rarer** -- fired when VVIX(d) is at or above the 90th (GATE-90) or 95th (GATE-95) percentile
     of its own trailing 252 sessions, not a fifth above the median. Near the top of its own range,
     the way a tail-risk warning should read, rather than "persistently a bit elevated".
  3. **Recovery-timed, not calendar-timed** -- once fired, SPY stays in cash until VVIX has
     actually fallen back to at or below the median of its own trailing 252 sessions (a session-by-
     session, stateless backward scan, as M0177's hysteresis gate and M0370's own stand-down scan),
     not for a fixed number of weeks. A sharp, short-lived spike that reverts in two weeks costs two
     weeks of cash; a slow-burning episode that takes four months costs four months, win or lose.
  4. **Monthly, not weekly** -- decided and resized monthly (``monthly-hold-frac-gotrade``), the
     cadence CLAUDE.md's lessons say this gate family should have been read at from the start.

Measured against the dev store before this file was committed (not a trial; nothing here spends a
look). Of 1,962 eligible sessions (>=252 prior VVIX rows, a fresh reading, 2008-01-03 through
2015-10-16): the 90th-percentile bar fired on 238 sessions (12.1%) and the 95th on 135 (6.9%) --
both rarer than M0370's 13.3%, as the "near the top" framing intends, though the gap narrows once
chained into recovery-based stand-downs (below). Resolved through the recovery rule into
contiguous episodes: GATE-90 produced 20 episodes covering 589 of all 5,722 sessions in the window
(10.3%), mean episode length 29.5 sessions (about 5.9 weeks); GATE-95 produced 14 episodes covering
537 sessions (9.4%), mean length 38.4 sessions (about 7.7 weeks). The longest observed episode was
101 sessions for both tiers -- real VVIX recoveries never approached the 200-session backward-scan
bound this file uses (below), so that bound is a pure engineering cap, not a lever that shaped the
result. On the 274 actual monthly decision dates in the window, both tiers show the account in
cash on 26 of them (9.5%) -- the same months, because a handful of the year's long episodes
dominate the monthly sample however the daily threshold is drawn.

The recovery-based exit is itself something M0370 never tested: its fixed stand-down could not
tell "VVIX spiked and is still elevated" from "VVIX spiked and already recovered", so every
VVIX-Nw variant paid the same N weeks of cash regardless of how the episode actually played out.
If recovery timing carries real information, letting the exit track VVIX rather than the calendar
should show up as a cleaner cost-for-safety trade than M0370's fixed-week arms did.

BLIND-90 and BLIND-95 are the frame-matched, no-opinion controls the lab's dressing rule requires
whenever an arm steps aside on a signal (same habit, no information): a hash of the seed and the
session's own date fires at the SAME measured session-level rate as its GATE twin (``BLIND_RATE``,
fixed before any trial, never re-derived from a recorded result), and once fired stays in cash for
a FIXED number of sessions equal to that tier's measured mean episode length (``BLIND_DURATION``) --
never reading VVIX's value, only its freshness, so a blind arm also trades like the plain switch
before 2008. ALWAYS is the third control the lab's dressing rule also wants: SPY held at full
weight every session, no gate of any kind (F1's own ``TimingAllocator`` with ``rule="always"``, no
new code) -- the "opinion removed" baseline a standalone arm needs, since M0370's own baseline
(the 200-day switch alone) does not apply once the switch itself is gone.

Success: GATE-90 or GATE-95 beats total-return SPY with worst fall <= 25%, PF >= 1.3, DSR >= 0.90,
a positive 2009-2015 edge and a majority of walk-forward folds, beats ALWAYS by more than fees
alone would predict, AND clears its BLIND twin by more than the two tiers would be expected to
differ from each other -- otherwise the lead is the time spent in cash, not the recovery timing.
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
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 10, 26)

FEAR = "VVIX"
TRAIL = 252  # trailing sessions behind the percentile/median baseline (about a year), excluding today
STALE_DAYS = 7  # a VVIX row older than this is no reading at all (gate cannot fire or recover)
# Bound on how far back the recovery scan looks for an unresolved fire, in trading sessions. Purely
# an engineering cap so `lookback()` stays inside the lab's 473-bar smoke-test ceiling (TRAIL +
# RECOVERY_CAP_SESSIONS = 452): measured on the dev store, the longest real episode at either tier
# was 101 sessions, well inside this bound, so the cap never actually binds in the window tested.
RECOVERY_CAP_SESSIONS = 200

Mode = Literal["gate", "blind"]
Tier = Literal["top90", "top95"]

TIER_QUANTILE: Mapping[Tier, float] = {"top90": 0.90, "top95": 0.95}
# Calibration measured against the dev store before this file was committed (not a trial; nothing
# here spends a look): the fraction of eligible sessions (2008-01-03 through 2015-10-16, 1,962
# sessions) whose VVIX close crossed that tier's own trailing-252-session percentile, and the mean
# length in trading sessions of the stand-downs the recovery rule produced from those fires. Fixed
# once, used only to calibrate BLIND's hash rate and fixed duration; never re-derived from a trial.
BLIND_RATE: Mapping[Tier, float] = {"top90": 238 / 1962, "top95": 135 / 1962}
BLIND_DURATION: Mapping[Tier, int] = {"top90": 29, "top95": 38}  # sessions (~5.9 and ~7.7 weeks)


def _percentile(values: tuple[float, ...], q: float) -> float:
    """Linear-interpolated percentile (0 < q < 1) of ``values``, ascending."""
    s = sorted(values)
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _reading(series: MarketSeries, d: date) -> tuple[float, ...] | None:
    """The TRAIL rows strictly before ``d``, as a plain tuple of values, when ``d`` itself has a
    fresh VVIX row with >= TRAIL prior rows; None when there is no eligible reading at ``d``."""
    rows = series.upto(FEAR, d, last=TRAIL + 1)
    if len(rows) < TRAIL + 1:
        return None
    if (d - rows[-1][0]).days > STALE_DAYS:
        return None
    return rows[-1][1], tuple(v for _, v in rows[:-1])


@dataclass(frozen=True, slots=True)
class Params:
    """``mode="gate"`` reads VVIX itself; ``mode="blind"`` reads only VVIX's own freshness (never
    its value) and fires on a fixed hash instead, at that tier's measured ``BLIND_RATE`` for a
    fixed ``BLIND_DURATION``. ``tier`` picks the dial end (gate) or which twin to mimic (blind)."""

    mode: Mode
    tier: Tier
    seed: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.mode, str):
            raise TypeError(f"mode must be a str, got {type(self.mode).__name__}")
        if self.mode not in ("gate", "blind"):
            raise ValueError(f"mode must be 'gate' or 'blind', got {self.mode!r}")
        if not isinstance(self.tier, str):
            raise TypeError(f"tier must be a str, got {type(self.tier).__name__}")
        if self.tier not in ("top90", "top95"):
            raise ValueError(f"tier must be 'top90' or 'top95', got {self.tier!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {
            "mode": self.mode,
            "tier": self.tier,
            "seed": str(self.seed),
            "quantile": repr(TIER_QUANTILE[self.tier]) if self.mode == "gate" else "n/a",
            "trail": str(TRAIL),
            "stale_days": str(STALE_DAYS),
            "recovery_cap_sessions": str(RECOVERY_CAP_SESSIONS) if self.mode == "gate" else "n/a",
            "blind_rate": repr(BLIND_RATE[self.tier]) if self.mode == "blind" else "n/a",
            "blind_duration_sessions": str(BLIND_DURATION[self.tier]) if self.mode == "blind" else "n/a",
        }


def _check(params: object) -> Params:
    if not isinstance(params, Params):
        raise TypeError(f"params must be Params, got {type(params).__name__}")
    return params


def gate_fired(series: MarketSeries, d: date, q: float) -> bool:
    """True when VVIX(d) is at or above the ``q`` percentile of the TRAIL rows strictly before d."""
    reading = _reading(series, d)
    if reading is None:
        return False
    today, base = reading
    return today >= _percentile(base, q)


def gate_recovered(series: MarketSeries, d: date) -> bool:
    """True when VVIX(d) has fallen back to at or below the median of the TRAIL rows before d."""
    reading = _reading(series, d)
    if reading is None:
        return False
    today, base = reading
    return today <= statistics.median(base)


def blind_fired(series: MarketSeries, d: date, seed: int, tier: Tier) -> bool:
    """A fixed hash of ``seed``, ``tier`` and ``d``, true at that tier's ``BLIND_RATE`` among
    eligible sessions (same eligibility as ``gate_fired``), never reading VVIX's value. Pure."""
    if _reading(series, d) is None:
        return False
    key = f"{seed}|{tier}|{d.isoformat()}".encode()
    h = int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")
    return (h % 10_000_000) < round(BLIND_RATE[tier] * 10_000_000)


def gate_standing_down(history: Mapping[str, History], series: MarketSeries, data_date: date, q: float) -> bool:
    """Stateless recovery scan: True when the most recent of {a fire, a recovery} at or before
    ``data_date``, within RECOVERY_CAP_SESSIONS trading sessions, is a fire rather than a recovery.
    No such event in the window: not standing down (matches the no-VVIX-yet era before 2008)."""
    h = history.get("SPY")
    if h is None:
        return True
    i = h.index_of(data_date)
    if i is None:
        return True
    for j in range(i, max(i - RECOVERY_CAP_SESSIONS, -1), -1):
        d = h.dates[j].item()
        if gate_fired(series, d, q):
            return True
        if gate_recovered(series, d):
            return False
    return False


def blind_standing_down(history: Mapping[str, History], series: MarketSeries, data_date: date, seed: int, tier: Tier) -> bool:
    """A fire within the tier's fixed BLIND_DURATION trading sessions through ``data_date``
    (inclusive) -- frame-matched to ``gate_standing_down``'s habit, with no VVIX value read."""
    h = history.get("SPY")
    if h is None:
        return True
    i = h.index_of(data_date)
    if i is None:
        return True
    duration = BLIND_DURATION[tier]
    for j in range(max(i - duration + 1, 0), i + 1):
        d = h.dates[j].item()
        if blind_fired(series, d, seed, tier):
            return True
    return False


def standing_down(history: Mapping[str, History], series: MarketSeries, data_date: date, p: Params) -> bool:
    if p.mode == "gate":
        return gate_standing_down(history, series, data_date, TIER_QUANTILE[p.tier])
    return blind_standing_down(history, series, data_date, p.seed, p.tier)


@dataclass(frozen=True, slots=True, eq=False)
class Prepared:
    history: Mapping[str, History]
    series: MarketSeries


class RecoveryGateAllocator:
    """SPY at full weight unless the VVIX (or blind) stand-down is active; no trend switch of any
    kind underneath -- see module docstring."""

    id = "M0373"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        if p.mode == "gate":
            return TRAIL + RECOVERY_CAP_SESSIONS
        return TRAIL + BLIND_DURATION[p.tier]

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


GATE = RecoveryGateAllocator()

ALWAYS_PARAMS = TimingParams(hold="SPY", signal="SPY", rule="always")


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0373-{suffix}", family="M0373", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0373",
    name=(
        "A standalone volatility-of-volatility gate, no switch underneath: cash only near the top "
        "of VVIX's own range, back once it has actually settled, not on a calendar"
    ),
    family="macro-vvix-tail-gate",
    source_kind="variation",
    source_ref=(
        "Huang, Schlag, Shaliastovich & Thapar (2019), Volatility-of-Volatility Risk, "
        "Journal of Financial and Quantitative Analysis 54(6), 2423-2452 -- a variation on M0370 "
        "(standalone instead of stacked, a rarer percentile bar instead of 1.20x the median, a "
        "recovery-timed exit instead of a fixed number of weeks, monthly read instead of weekly)"
    ),
    parent_id="M0370",
    hypothesis=(
        "M0370 stacked a VVIX stand-down on F4's 200-day switch, firing at 1.20x the trailing-year "
        "median (13.3% of eligible sessions, 2008-2015) and exiting after a fixed number of weeks "
        "regardless of whether VVIX had actually settled. It was rejected: the gate mostly "
        "re-confirmed a switch that was already off, and a frame-matched blind draw at the same "
        "rate captured most of its lead -- the weekly read cadence itself was separately shown to "
        "cost several points a year against a monthly one. This file removes every one of those "
        "three confounds at once rather than patching the same shape: no switch underneath (SPY is "
        "held whenever the gate is not firing, full stop, so a VVIX effect cannot borrow the "
        "switch's), a rarer percentile bar (90th or 95th of VVIX's own trailing 252 sessions, "
        "measured on the dev store at 12.1% and 6.9% of eligible sessions respectively, both lower "
        "than M0370's 13.3%), a recovery-timed exit (cash until VVIX falls back to at or below its "
        "own trailing median, a session-by-session scan, not a fixed number of weeks -- chaining "
        "into 20 episodes averaging 29.5 sessions for the 90th-percentile bar and 14 episodes "
        "averaging 38.4 sessions for the 95th, 9.3-10.3% of all sessions in cash either way), and a "
        "monthly decision and resize cadence instead of weekly. BLIND-90 and BLIND-95 are the "
        "dressing twins: a hash fired at each tier's own measured rate, cash for that tier's fixed "
        "mean episode length, no VVIX value read at all -- pricing the habit of stepping aside this "
        "often, separate from whether VVIX chose the moments. ALWAYS is the always-invested "
        "baseline a standalone arm needs, since M0370's own baseline (the switch alone) no longer "
        "applies once the switch is gone. Success: GATE-90 or GATE-95 beats total-return SPY with "
        "worst fall <= 25%, PF >= 1.3, DSR >= 0.90, a positive 2009-2015 edge and a majority of "
        "walk-forward folds, beats ALWAYS by more than fees alone would predict, AND clears its "
        "BLIND twin by more than the two tiers would be expected to differ from each other."
    ),
    expected_failure=(
        "VVIX and VIX spikes mostly co-occur because both react to the same equity sell-offs, so "
        "even a standalone, rarer, recovery-timed VVIX gate is likely to end up avoiding much the "
        "same weeks a plain trend switch would have avoided for free, at the cost of extra whipsaw "
        "around re-entries a switch would not have made. Removing the underlying switch does not "
        "remove that overlap; it only removes the switch's own confound from the comparison. The "
        "recovery-based exit is the genuinely new mechanism here (M0370 never isolated it), and it "
        "is also the one most likely to look better than it is: VVIX can hover just above its own "
        "median for long stretches without ever closing the recovery condition, so a single episode "
        "that never quite recovers could pin the book in cash for most of the backward-scan window -- "
        "the measured 101-session longest episode suggests this did not happen on the dev store, "
        "but a single different threshold draw could change that. At 6.9-12.1% of eligible sessions "
        "firing, 'near the top of its own range' is still far more common than a true tail-risk "
        "warning, which is exactly what the BLIND twins exist to catch: expect them to capture most "
        "of GATE-90/95's lead over ALWAYS, the same outcome M0370 found at a looser threshold and a "
        "fixed exit. The gate is silent before 2008-01-03 (fewer than 252 prior VVIX rows), so every "
        "variant trades exactly like ALWAYS over 1996-2007 and the whole comparison lives in "
        "2008-2015, the fuller-coverage half of the dev window -- any edge that does appear should "
        "be checked against `lab survivorship` before it is trusted. Published 2019, after the dev "
        "window and most of the test window, so a dev result says nothing about whether the "
        "mechanism has since been arbitraged away."
    ),
    candidates=(
        _v("ALWAYS", TIMING, ALWAYS_PARAMS,
           "Control: SPY held at full weight every session, no gate of any kind"),
        _v("GATE-90", GATE, Params(mode="gate", tier="top90"),
           "Cash while VVIX sits at or above the 90th percentile of its own trailing year, back "
           "once it has fallen to at or below that year's median"),
        _v("GATE-95", GATE, Params(mode="gate", tier="top95"),
           "The same recovery-timed gate, a rarer 95th-percentile bar (the dial's other end)"),
        _v("BLIND-90", GATE, Params(mode="blind", tier="top90", seed=1),
           "Frame-matched control: a hash fires at GATE-90's own measured rate, cash for GATE-90's "
           "measured mean episode length, no VVIX value read"),
        _v("BLIND-95", GATE, Params(mode="blind", tier="top95", seed=1),
           "The same blind control, calibrated to GATE-95's rate and mean episode length"),
    ),
    seen_keys=(
        "concept:vvix-tail-risk",
        "concept:volatility-of-volatility",
        "concept:recovery-based-exit",
        "concept:percentile-threshold-gate",
        "concept:frame-matched-blind-draw",
    ),
)
