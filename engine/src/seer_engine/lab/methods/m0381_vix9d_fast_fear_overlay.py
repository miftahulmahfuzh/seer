"""M0381 — A nine-day fear reading as an extra brake on the 200-day switch.

Source: variation of M0039 (the VIX term-structure gate). CBOE's VIX9D is a nine-calendar-day
option-implied volatility index; the lab's dev store carries it from 2011-01-03 only. Reserved
by Sera 20261026-1017.

Idea: every volatility overlay the lab has put on top of the 200-day switch has lost to running
the switch alone. The ones tried read a one-month horizon (spot VIX) against a three-month one
(VIX3M), and M0039 found that pair *lagged* the switch in 2008 rather than leading it. A
nine-day reading is the shortest-dated fear gauge that exists, so if any options-implied series
turns early enough to be worth its cost, it is this one. This method asks that question directly
and with its mirror attached, so the answer separates a real signal from a lucky one and prices
the habit as well as the opinion.

The chassis is deliberately the *switch itself*, not raw SPY. M0039 gated raw SPY and could not
clear the drawdown bar on any variant, because the 2000-2002 and 2008 falls sat outside the
series' coverage. Here the 200-day switch is the host and handles those falls; the volatility
reading can only take the book to cash on days the switch would otherwise be invested. The
overlay is therefore strictly subtractive, and its whole measurable effect is 2011-2015.

On ``data_date`` d, from SPY's own bars through d and ``Market.series``:

    * the switch (``switch=True``): on iff close(d) > SMA(200) of SPY's last 200 daily closes
      (strict), using ``f_index.above_sma`` so SWITCH is the lab's existing SPY-200 rule, bar for
      bar. ``switch=False`` holds SPY always and is the no-opinion arm.
    * the overlay (``overlay``), read only when the switch is on:
        ``"none"``     no overlay.
        ``"v9d"``      cash when VIX9D(d) / VIX(d) >= ``threshold``: the nine-day reading at or
                       above the one-month reading, i.e. fear concentrated in the next two weeks.
        ``"v9d_inv"``  the exact mirror: cash when that ratio is < ``threshold``. With a fresh
                       reading the two are complements, so V9D and V9D-INV between them spend the
                       same days in cash. If the mirror does as well, the reading carries nothing.
        ``"ts"``       cash when VIX(d) / VIX3M(d) >= ``threshold``: M0039's one-month-vs-three-
                       month reading, on this chassis, over these years, as the reference the
                       nine-day reading has to beat.

A series row older than ``STALE_DAYS`` calendar days (M0039's convention, imported) is no
reading, and no reading never forces cash. VIX9D begins 2011-01-03 and VIX3M 2006-07-17, so each
overlay variant is its SWITCH control trade for trade until its series starts: the paired
difference V9D - SWITCH is the nine-day reading's effect over 2011-2015 alone, and nothing else.

Cash earns nothing (no T-bill credit), as in M0039.

Market-aware: ``prepare_market`` carries the series. The history-only path has no series and
targets nothing, per the lab's market-aware contract -- including the SWITCH and ALWAYS arms,
whose params never read a series. The contract is a property of the allocator, not of the
params, and holding every arm to it keeps all five on one allocator and so one comparison.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0039_vix_term_structure_gate import (
    DAILY_HOLD_FRAC_GOTRADE,
    STALE_DAYS,
    _fresh,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import above_sma

ADDED = date(2026, 10, 26)

FULL_WEIGHT = equal_weight(1)

Overlay = Literal["none", "v9d", "v9d_inv", "ts"]
OVERLAYS: tuple[str, ...] = ("none", "v9d", "v9d_inv", "ts")


@dataclass(frozen=True, slots=True)
class Vol9Params:
    """Hold SPY while the switch is on and the overlay has not called for cash."""

    switch: bool = True  # the SPY-200 switch as host; False = always invested (no opinion)
    overlay: Overlay = "none"
    threshold: float = 1.0  # the ratio at or above which "v9d"/"ts" go to cash
    n: int = 200  # the switch's SMA length, in daily closes

    def __post_init__(self) -> None:
        if not isinstance(self.switch, bool):
            raise TypeError(f"switch must be a bool, got {type(self.switch).__name__}")
        if not isinstance(self.overlay, str):
            raise TypeError(f"overlay must be a str, got {type(self.overlay).__name__}")
        if self.overlay not in OVERLAYS:
            raise ValueError(f"overlay must be one of {OVERLAYS}, got {self.overlay!r}")
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, float) or not self.threshold > 0:
            raise ValueError(f"threshold must be a positive float, got {self.threshold!r}")
        if isinstance(self.n, bool) or not isinstance(self.n, int) or self.n < 2:
            raise ValueError(f"n must be an int >= 2, got {self.n!r}")

    def as_dict(self) -> dict[str, str]:
        return {"switch": str(self.switch), "overlay": self.overlay,
                "threshold": repr(self.threshold), "n": str(self.n)}


def _check(params: object) -> Vol9Params:
    if not isinstance(params, Vol9Params):
        raise TypeError(f"params must be Vol9Params, got {type(params).__name__}")
    return params


def _ratio(series: MarketSeries, data_date: date, fast: str, slow: str) -> float | None:
    """fast/slow on d from rows dated <= d, or None when either leg is stale or unusable."""
    f = series.upto(fast, data_date, last=1)
    s = series.upto(slow, data_date, last=1)
    if not _fresh(f, data_date) or not _fresh(s, data_date) or s[-1][1] <= 0:
        return None
    return f[-1][1] / s[-1][1]


def overlay_allows(series: MarketSeries, data_date: date, p: Vol9Params) -> bool:
    """True when the overlay lets the book stay invested. No reading is never a reason for cash."""
    if p.overlay == "none":
        return True
    if p.overlay == "ts":
        r = _ratio(series, data_date, "VIX", "VIX3M")
        return True if r is None else r < p.threshold
    r = _ratio(series, data_date, "VIX9D", "VIX")
    if r is None:
        return True
    return r < p.threshold if p.overlay == "v9d" else r >= p.threshold


@dataclass(frozen=True, slots=True, eq=False)
class Vol9Prepared:
    history: Mapping[str, History]
    series: MarketSeries


class Vol9Allocator:
    """SPY at full weight while the switch is on and the overlay allows it; otherwise cash."""

    id = "M0381"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        return _check(params).n

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def _run(self, prepared: Vol9Prepared, data_date: date, held: frozenset[str],
             p: Vol9Params) -> tuple[Target, ...]:
        if len(prepared.series) == 0:
            return ()  # market-aware contract: no panel, no target (every arm, not just the gated)
        h = prepared.history.get("SPY")
        if h is None:
            return ()
        state: bool | None = above_sma(h, data_date, p.n) if p.switch else (
            True if h.index_of(data_date) is not None else None)
        if state is None:  # no bar dated d: keep SPY only if it is already held, never a new entry
            if "SPY" not in held:
                return ()
            t = target_from_close("SPY", last_close(h, data_date), FULL_WEIGHT)
            return () if t is None else (t,)
        if not state or not overlay_allows(prepared.series, data_date, p):
            return ()
        t = target_from_close("SPY", last_close(h, data_date), FULL_WEIGHT)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(Vol9Prepared(history, EMPTY_SERIES), data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> Vol9Prepared:
        return Vol9Prepared(history, EMPTY_SERIES)

    def prepare_market(self, market: Any) -> Vol9Prepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return Vol9Prepared(market.history, series)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Vol9Prepared):
            raise TypeError(f"prepared must be Vol9Prepared, got {type(prepared).__name__}")
        return self._run(prepared, data_date, held, _check(params))


VOL9 = Vol9Allocator()


def _v(suffix: str, params: Vol9Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0381-{suffix}", family="M0381", rules=DAILY_HOLD_FRAC_GOTRADE,
                     allocator=VOL9, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0381",
    name=("A much faster fear-of-the-moment reading (9-day vs 30-day options fear) as a gate on "
          "the switch, the last volatility-based overlay worth checking"),
    family="volatility-term-structure-gate",
    source_kind="variation",
    source_ref="M0039",
    parent_id="M0039",
    hypothesis=(
        "Every volatility overlay the lab has put on the 200-day switch has lost to the switch "
        "alone: M0039's one-month-vs-three-month term structure lagged the switch in 2008 rather "
        "than leading it, and the fear-of-fear triggers that followed it failed too. All of them "
        "read a one-month horizon. VIX9D is a nine-calendar-day reading, the shortest-dated fear "
        "gauge published, and the lab has never tried it: if any options series turns early "
        "enough to pay for itself on top of the switch, it is this one. The chassis is the SPY-200 "
        "switch itself (SPY at full weight, decided every session, fractional shares at Gotrade's "
        "real fees), not raw SPY, because M0039 showed a raw-SPY host cannot clear the drawdown "
        "bar when the series does not cover 2000-2002. The overlay is strictly subtractive: it can "
        "only move the book to cash on days the switch is already invested. Five arms, one "
        "pre-registration: SWITCH (the switch alone, the habit with no opinion in it), V9D (cash "
        "while VIX9D/VIX >= 1.00, the treatment), V9D-INV (the exact mirror, cash while that ratio "
        "is < 1.00, so a reading that carries nothing shows up as the mirror doing as well), TS "
        "(M0039's VIX/VIX3M >= 1.00 reading on this same chassis and these same years, the "
        "reference the nine-day reading has to beat) and ALWAYS (SPY held every session, no switch "
        "and no overlay, which prices what the habit of stepping aside costs, so a dead rule can "
        "be told from a badly dressed one). Success: V9D beats SWITCH on funded return with no "
        "deeper worst fall, beats its own mirror by more than the lab's measured draw noise, and "
        "beats TS over the years both can read. Assumed: cash earns nothing, a series row older "
        "than seven calendar days is no reading and never forces cash, the reading is taken from "
        "day d's close and traded at the next open, and the threshold is fixed at 1.00 with no "
        "sweep, so no dial is fitted after the fact."
    ),
    expected_failure=(
        "VIX9D starts 2011-01-03 in the lab's store, so the overlay is inert for the first "
        "eighteen of the dev window's twenty-three years and V9D is SWITCH trade for trade until "
        "2011. The five years it can read, 2011 to October 2015, contain no bear market at all, "
        "which is the only condition a crash brake exists for. So the most likely result by far is "
        "that every firing of the nine-day reading is a false alarm: the book sells after a scare, "
        "pays Gotrade's fees, misses the rebound days that follow fear spikes, and buys back "
        "higher. V9D should therefore land a little below SWITCH over 2011-2015 and be "
        "indistinguishable from it over the whole window, which is itself the finding -- a series "
        "covering five of twenty-three years cannot move a twenty-three-year book however good it "
        "is. The mirror V9D-INV is expected to do about as well as V9D, because a ratio near 1.00 "
        "flips often and neither side of it should predict the next few weeks in a rally. TS is "
        "expected to repeat M0039's result. ALWAYS should beat all four on return over this "
        "window and lose badly on worst fall, since it holds through 2000-2002 and 2008, which is "
        "what makes it the right price tag for the habit rather than a candidate. Eligibility is "
        "not expected for any arm: the switch arms should clear the drawdown bar but the lab's "
        "trend-switch family has never cleared the luck bar at this N, and ALWAYS is SPY with fees "
        "and so cannot beat SPY. If this fails as expected, the lab should stop putting "
        "options-implied volatility readings on top of the 200-day switch and look for an early "
        "warning that watches something the switch does not already watch. Measured on the dev "
        "store before this ran, and recorded here so no dial is fitted afterwards: over the 1206 "
        "sessions from 2011-01-03 to 2015-10-16 that carry both series, VIX9D/VIX is at or above "
        "1.00 on 414 of them (34.3%), against 98 (8.1%) for VIX/VIX3M, and 92 of those 98 days are "
        "also VIX9D days. So the nine-day reading is a strictly busier, earlier version of the "
        "one-month one, and V9D will sit in cash about a third of the invested days of a rally "
        "with no bear market in it. That also means V9D-INV is NOT cost-matched to V9D -- the "
        "mirror is in cash roughly two thirds of the time, not one third -- so the pair reads the "
        "sign of the signal, not its price, and the price has to be recovered from the gap between "
        "ALWAYS and SWITCH rather than read off the mirror directly."
    ),
    candidates=(
        _v("SWITCH", Vol9Params(True, "none"),
           "Control: the SPY-200 switch alone, daily, fractional, at Gotrade's real fees."),
        _v("V9D", Vol9Params(True, "v9d"),
           "Treatment: also cash while the nine-day fear reading is at or above the one-month one."),
        _v("V9D-INV", Vol9Params(True, "v9d_inv"),
           "Mirror: also cash while that same ratio is below 1.00, the exact complement of V9D."),
        _v("TS", Vol9Params(True, "ts"),
           "Reference: M0039's one-month-vs-three-month reading on this chassis and these years."),
        _v("ALWAYS", Vol9Params(False, "none"),
           "No opinion: SPY held every session, so the switch's own cost can be read off."),
    ),
    seen_keys=(
        "concept:vix9d-short-dated-fear-overlay",
        "concept:volatility-term-structure-on-200day-switch",
    ),
)
