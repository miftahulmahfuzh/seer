"""M0422 — SPY's 200-day switch, bought back when the fear index has fallen from its peak.

Source: variation of M0404 (a fixed price rebound as the way back in), which M0404's own
analysis named as the last re-entry family left to price.
Idea: M0404 found that asking for a fixed 10-15% bounce off the lowest close put the book back
in during bear-market rallies and deepened the worst fall (26.5% against 18.9%). Price alone
cannot tell a bounce from a bottom. The fear index (VIX) is a second, independent reading of the
same crash: it spikes to a peak at the panic and drains as the panic passes. So the way back in
here is "VIX has closed a fixed fraction under its highest close of the current below-200-day
episode", which asks whether the panic is over rather than whether the price has bounced.

Frame, deliberately M0404's: SPY only at full weight, monthly check, fractional shares at
Gotrade's real fees on the owner's deposits, the same 253-bar lookback, so the paired difference
against the SPY200 control is the buy-back trigger alone. The exit is fixed in every arm (SPY
close strictly under its 200-day average, ``trend_on`` unchanged). Out of the market, an arm
comes back on the plain 200-day test OR on its own VIX trigger, whichever first.

"Episode": the run of consecutive SPY closes at or under their own 200-day average ending on
``data_date``, looking back at most LOOKBACK sessions. "Peak": the highest VIX close dated inside
that run. The VETO arm is the reversed rule: it keeps the 200-day exit and the 200-day
re-entry but refuses to re-enter while the fear index stands a third or more under the peak of
the most recent episode, and only for VETO_WINDOW sessions after that episode ended (an
assumption: without an expiry the veto could hold a book out for good). Reads only bars dated
<= ``data_date``. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0404_spy200_rebound_reentry import (
    BENCH,
    EXIT_GATE,
    LOOKBACK,
    SMA_N,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import trend_on

ADDED = date(2026, 11, 1)
VIX = "VIX"
#: Sessions after an episode ends during which the VETO arm still reads that episode's peak.
VETO_WINDOW = 63
#: Rows of VIX read per call: the episode cannot be longer than LOOKBACK sessions.
_VIX_ROWS = LOOKBACK + 10

Entry = Literal["sma200", "fall", "veto", "always"]
_ENTRIES: tuple[str, ...] = ("sma200", "fall", "veto", "always")


@dataclass(frozen=True, slots=True)
class FallParams:
    """How SPY is bought back. ``fall`` is the fraction VIX must be under its episode peak."""

    entry: Entry = "sma200"
    fall: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.entry, str) or self.entry not in _ENTRIES:
            raise ValueError(f"entry must be one of {_ENTRIES}, got {self.entry!r}")
        if isinstance(self.fall, bool) or not isinstance(self.fall, (int, float)):
            raise TypeError(f"fall must be a number, got {type(self.fall).__name__}")
        if self.entry in ("fall", "veto"):
            if not 0.0 < self.fall < 1.0:
                raise ValueError(f"fall must be in (0, 1), got {self.fall}")
        elif self.fall != 0.0:
            raise ValueError(f"fall must be 0 for entry={self.entry!r}, got {self.fall}")

    def as_dict(self) -> dict[str, str]:
        return {"entry": self.entry, "fall": str(self.fall)}


def _check(params: object) -> FallParams:
    if not isinstance(params, FallParams):
        raise TypeError(f"params must be FallParams, got {type(params).__name__}")
    return params


def _below(close: np.ndarray, j: int) -> bool:
    """True when the close at bar ``j`` is not above its own 200-day average."""
    return not close[j] > float(np.mean(close[j + 1 - SMA_N : j + 1]))


def last_episode(h: History, i: int) -> tuple[int, int, int] | None:
    """The most recent below-200-day run at or before bar ``i``: (start, end, sessions_since_end).

    ``sessions_since_end`` is 0 when bar ``i`` is itself inside the run. None when there is
    not enough history or no such run inside the lookback.
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
    while j >= lo and _below(close, j):
        j -= 1
    return j + 1, end, i - end


def episode_peak(h: History, series: MarketSeries, start: int, end: int,
                 data_date: date) -> float | None:
    """Highest VIX close dated inside bars ``start``..``end`` of SPY's history."""
    d0 = h.dates[start].astype("datetime64[D]").astype(object)
    d1 = h.dates[end].astype("datetime64[D]").astype(object)
    vals = [v for d, v in series.upto(VIX, data_date, last=_VIX_ROWS) if d0 <= d <= d1]
    return max(vals) if vals else None


def fear_fell(h: History, series: MarketSeries, data_date: date, fall: float,
              *, still_in: bool) -> bool:
    """True when VIX is at least ``fall`` under the peak of the relevant episode.

    ``still_in`` True reads the episode ``data_date`` is inside (the fast re-entry arms);
    False reads the most recent one that ended within VETO_WINDOW sessions (the veto arm).
    """
    i = h.index_of(data_date)
    if i is None:
        return False
    ep = last_episode(h, i)
    if ep is None:
        return False
    start, end, gap = ep
    if still_in and gap != 0:
        return False
    if not still_in and gap > VETO_WINDOW:
        return False
    peak = episode_peak(h, series, start, end, data_date)
    now = series.value_on(VIX, data_date)
    if peak is None or now is None or peak <= 0:
        return False
    return bool(now <= peak * (1.0 - fall))


@dataclass(frozen=True, slots=True, eq=False)
class Prepared:
    history: Mapping[str, History]
    series: MarketSeries


class VixFallTrendSwitch:
    """100% SPY, fixed 200-day exit, a variant's own way back in. Nothing else is held."""

    id = "M0422"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def _on(self, history: Mapping[str, History], series: MarketSeries, data_date: date,
            held: frozenset[str], p: FallParams) -> bool:
        if p.entry == "always":
            return True
        plain = trend_on(history, data_date, EXIT_GATE)
        h = history.get(BENCH)
        if BENCH in held or p.entry == "sma200" or h is None:
            return plain
        if p.entry == "fall":
            return plain or fear_fell(h, series, data_date, p.fall, still_in=True)
        # veto: the plain 200-day re-entry, refused while fear is draining from its peak
        return plain and not fear_fell(h, series, data_date, p.fall, still_in=False)

    def _run(self, history: Mapping[str, History], series: MarketSeries, data_date: date,
             held: frozenset[str], p: FallParams) -> tuple[Target, ...]:
        if len(series) == 0:  # market-aware contract: no series, no target
            return ()
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:
            return ()
        if not self._on(history, series, data_date, held, p):
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no target."""
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


SWITCH = VixFallTrendSwitch()


def _v(suffix: str, params: FallParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0422-{suffix}", family="M0422", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SWITCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0422",
    name="SPY's 200-day switch, bought back when the fear index has fallen from its peak",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0404 (the fixed price rebound), whose analysis named this trigger",
    parent_id="M0404",
    hypothesis=(
        "The 200-day switch is old (published 1992 banded, 2007 Faber) and VIX has traded since "
        "1993, so no fresh anomaly and little fade argument. M0404 showed that a fixed 10-15% price "
        "bounce off the trough as the way back in deepened the worst fall from 18.9% to 26.5%: "
        "price cannot tell a bear-market rally from a bottom. VIX is an independent read of the "
        "same crash. It peaks at the panic and drains as the panic passes, so 'VIX closed a "
        "third under its peak since the 200-day exit' asks whether the fear is over, not whether "
        "the price has bounced. Arms fixed before the run, monthly, SPY only, fractional, Gotrade "
        "fees, owner deposits, M0404's 253-bar lookback so the window matches: SPY200 (plain "
        "switch, control), THIRD, QUARTER and HALF (back in on the 200-day test OR once VIX "
        "closes 1/3, 1/4 or 1/2 under its highest close of the current below-200-day episode), "
        "VETO (the reversed rule: the 200-day re-entry is refused while VIX stands a third under "
        "the last episode's peak, for 63 sessions after it ends, so the book stays out while "
        "fear falls) and ALWAYS (SPY held every session, the no-opinion arm, so what the habit "
        "of switching costs can be separated from what the opinion earns, which a pair of "
        "reversed arms cannot show on its own). SUCCESS: a fall arm beats SPY200 in 2009-2015 "
        "with a worst fall no deeper than SPY200's, and beats VETO, a majority of walk-forward "
        "folds, DSR >= 0.90. Assumptions: the peak is the highest VIX close inside the current "
        "run of closes at or under SPY's own 200-day average, capped at 253 sessions; the veto "
        "window of 63 sessions is mine."
    ),
    expected_failure=(
        "A VIX that drops a third from a peak is routine inside a bear market: late 2008 and "
        "2001-2002 each had several such drains before the lows, so the fast trigger buys the "
        "rallies again and the worst fall deepens as in M0404. A small drop (QUARTER) from a "
        "low peak fires in days after a mild exit, which is a whipsaw machine; HALF is more "
        "protected but near the plain 200-day entry. Fear falling and price rising are close to "
        "the same event, so the arms may differ little from each other and from SPY200. Trade "
        "counts stay in the tens over 22 years, so profit factor and the luck bar are close to "
        "meaningless; funded return, worst fall and the 2009-2015 split are the readable "
        "numbers. 2009-2015 had no bear market, so a rule can look good there for the wrong "
        "reason. No interest on cash is modelled, which flatters SPY. M0376, M0381 and M0389 "
        "already found VIX-family overlays on this switch cost return and added nothing in "
        "2008, which is the prior against this."
    ),
    candidates=(
        _v("SPY200", FallParams("sma200"),
           "Control: the plain symmetric 200-day switch, monthly"),
        _v("THIRD", FallParams("fall", 1 / 3),
           "Out under the 200-day, back in once VIX is a third under its episode peak"),
        _v("QUARTER", FallParams("fall", 0.25),
           "As THIRD with a smaller drain required: earlier, noisier entry"),
        _v("HALF", FallParams("fall", 0.5),
           "As THIRD with half the peak gone: more proof the panic is over, later entry"),
        _v("VETO", FallParams("veto", 1 / 3),
           "Reversed rule: 200-day re-entry refused while VIX is a third under the last peak"),
        _v("ALWAYS", FallParams("always"),
           "No-opinion arm: SPY held every session, never in cash"),
    ),
    seen_keys=(
        "concept:vix-drain-reentry-after-sma200-exit",
        "concept:fear-index-fall-from-episode-peak",
        "concept:asymmetric-trend-switch-reentry",
    ),
)
