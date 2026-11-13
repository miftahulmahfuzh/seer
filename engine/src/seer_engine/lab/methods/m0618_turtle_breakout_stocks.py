"""M0618 -- Turtle breakout stocks: buy a name when it closes at a new 100-day high, sell it when it
closes under its 50-day low, behind the 200-day switch.

Source: Donchian channel trend entries (Zarattini, Pagani and Barbon's crypto trend paper, and the
1980s Turtle rules before it); the lab tests the long-only stock version. Channel breakouts are
old and widely published, so dev may overstate them after the crowd traded them.

Idea. Every stock book in this lab ranks names on a signal and re-picks on a calendar. A Donchian
channel is an event rule: a name enters the day its close exceeds its highest close of the prior
``entry_n`` sessions and leaves the day its close falls below its lowest close of the prior
``exit_n`` sessions. Holding time is set by the price path, so a name that keeps trending is never
sold for a re-rank, and a name that stalls is cut without waiting for a month end.

Frame. F4's screen (20-day dollar volume over $20M, close at least $5, 253 bars of history) on
point-in-time index members; the ``universe`` (100) most traded of those are eligible to ENTER.
At most ``slots`` (20) names at 1/20 each; free slots sit in cash. When more names break out than
there are free slots, the largest ``entry_n``-session gain goes first (ties by symbol). A held
name stays in the book whether or not it is still among the 100 most traded: only its own exit
rule (or the switch) removes it. Behind the SPY 200-day switch (F4's ``trend``): when SPY closes
at or under its 200-day average every position is sold and none is opened.

Trading. Daily cadence, fractional shares, Gotrade's real fees, and NO resizing: a position is
bought at 1/20 of equity on its entry day and left alone until its exit. A resizing book would
trade every day to chase 5%, which is the opposite of what a hold-the-trend rule is for. Deposits
(the owner's monthly top-up) therefore wait in cash until the next entry sizes against the larger
equity; that is part of the price of an event rule.

Arms (six):
  BRK100-50     treatment: enter on a 100-day high close, exit under the 50-day low close.
  BRK55-20      the classic turtle windows (55 in, 20 out).
  BRK200-100    the slow channel.
  BRK100-50-RAND  Control: the same slots, the same exit rule and the same entry COUNT each day as
                the treatment would take, but the entered names are a hash draw (seed 6181, keyed
                on the date) from the same screened pool of 100, with no breakout condition. This
                prices the entry rule apart from the exit rule and the switch.
  BRK100-CAL63  Control: the same breakout entry, but a name is sold when 63 sessions have passed
                since its latest breakout (a stateless reading: held while a new 100-day high
                close has printed within the last 63 sessions). Prices the path-set holding time
                against a calendar one.
  BRK100-50-NOSW  the treatment never switching to cash: the no-opinion arm the lab's dressing rule
                owes for the 200-day switch.
No recorded trial holds this book on this chassis, so none is cited in place of running.

SUCCESS: BRK100-50 beats total-return SPY on deposit-matched money, beats the random-entry control
by more than 2 points a year funded, has a positive 2009-2015 edge, and keeps its worst fall under
25%.
Pure: reads only bars dated <= data_date.
"""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.control_draw import entry_key
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 13)
NOSW = replace(N20, trend=None)

# Daily decisions, no resize: monthly-hold-frac-gotrade's fractional, open-limit, real-fee levers on
# a daily clock without the equity-band resize, so a held name is left alone until it exits. No
# preset of this id exists yet, so a winner needs one before `promote` (a feature-wish).
DAILY_HOLD_FRAC_GOTRADE_NORESIZE = replace(
    MONTHLY_HOLD_FRAC_GOTRADE,
    id="daily-hold-frac-gotrade-noresize",
    cadence="daily",
    resize=False,
)

_MODES = ("brk", "blind")
_EXITS = ("low", "calendar")


@dataclass(frozen=True, slots=True)
class DonchianParams:
    """``inner`` is F4's screen and the switch; the rest is the channel and the book."""

    inner: FactorParams
    entry_n: int = 100
    exit_n: int = 50
    mode: str = "brk"
    exit_kind: str = "low"
    hold_n: int = 63
    universe: int = 100
    slots: int = 20
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        if self.exit_kind not in _EXITS:
            raise ValueError(f"exit_kind must be one of {_EXITS}, got {self.exit_kind!r}")
        for name in ("entry_n", "exit_n", "hold_n", "universe", "slots", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be an int >= 0, got {v!r}")
        for name in ("entry_n", "exit_n", "hold_n", "universe", "slots"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")

    def as_dict(self) -> dict[str, str]:
        out = {
            "entry_n": str(self.entry_n),
            "exit_n": str(self.exit_n),
            "mode": self.mode,
            "exit_kind": self.exit_kind,
            "hold_n": str(self.hold_n),
            "universe": str(self.universe),
            "slots": str(self.slots),
            "seed": str(self.seed),
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> DonchianParams:
    if not isinstance(params, DonchianParams):
        raise TypeError(f"params must be DonchianParams, got {type(params).__name__}")
    return params


def broke_out(closes: np.ndarray, i: int, n: int) -> bool:
    """True when ``closes[i]`` is strictly above every close in the ``n`` sessions before it."""
    if i < n:
        return False
    return bool(closes[i] > np.max(closes[i - n : i]))


def fell_through(closes: np.ndarray, i: int, n: int) -> bool:
    """True when ``closes[i]`` is strictly below every close in the ``n`` sessions before it."""
    if i < n:
        return False
    return bool(closes[i] < np.min(closes[i - n : i]))


def broke_out_within(closes: np.ndarray, i: int, n: int, within: int) -> bool:
    """True when a breakout (see ``broke_out``) printed on any of the last ``within`` sessions."""
    return any(broke_out(closes, j, n) for j in range(max(i - within + 1, n), i + 1))


class DonchianAllocator:
    """Event-driven long-only channel book: keep a held name until its exit fires, fill free slots."""

    id = "M0618"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.entry_n + p.hold_n + 2, p.exit_n + 2)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return () if p.inner.trend is None else (p.inner.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _kept(self, history: Mapping[str, History], held: frozenset[str], data_date: date,
              p: DonchianParams) -> list[Target]:
        w = equal_weight(p.slots)
        out: list[Target] = []
        for s in sorted(held):
            if len(out) == p.slots:
                break
            h = history.get(s)
            if h is None:
                continue
            i = h.index_of(data_date)
            if i is not None:
                closes = h.close
                if p.exit_kind == "low":
                    if fell_through(closes, i, p.exit_n):
                        continue
                elif not broke_out_within(closes, i, p.entry_n, p.hold_n):
                    continue
            px = last_close(h, data_date)  # a name with no bar today is carried at its last close
            t = None if px is None else target_from_close(s, px, w)
            if t is not None:
                out.append(t)
        return out

    def _run(self, history: Mapping[str, History], rows: Any, data_date: date, held: frozenset[str],
             p: DonchianParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        kept = self._kept(history, held, data_date, p)
        free = p.slots - len(kept)
        if free <= 0:
            return tuple(kept)
        have = {t.symbol for t in kept}
        pool = sorted(
            (r for r in rows if r.symbol not in EXCLUDED),
            key=lambda r: (-r.dollar_volume, r.symbol),
        )[: p.universe]
        brk: list[tuple[float, str]] = []
        for r in pool:
            if r.symbol in have:
                continue
            h = history.get(r.symbol)
            i = None if h is None else h.index_of(data_date)
            if h is None or i is None or i < p.entry_n:
                continue
            if broke_out(h.close, i, p.entry_n):
                brk.append((-float(h.close[i] / h.close[i - p.entry_n] - 1.0), r.symbol))
        brk.sort()
        take = min(free, len(brk))
        if p.mode == "brk":
            picks = [s for _, s in brk[:take]]
        else:  # blind: the same count the breakouts would have taken, drawn from the same pool
            names = sorted(
                (r.symbol for r in pool if r.symbol not in have),
                key=lambda s: (entry_key("M0618", p.seed, s, data_date), s),
            )
            picks = names[:take]
        out = list(kept)
        w = equal_weight(p.slots)
        for s in picks:
            px = last_close(history[s], data_date)
            t = None if px is None else target_from_close(s, px, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = factor_rows(history, members, data_date, p.inner)
        return self._run(history, rows, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> tuple[Mapping[str, History], FactorPrepared]:
        return history, prepare_factor(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        history, factor = prepared
        rows = factor.rows_on(members, data_date, p.inner)
        return self._run(history, rows, data_date, held, p)


ALLOC = DonchianAllocator()


def _v(suffix: str, params: DonchianParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0618-{suffix}",
        family="M0618",
        rules=DAILY_HOLD_FRAC_GOTRADE_NORESIZE,
        allocator=ALLOC,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0618",
    name=(
        "Turtle breakout stocks: buy a name when it closes at a new 100-day high, sell it when it "
        "closes under its 50-day low, behind the 200-day switch"
    ),
    family="stock-donchian-breakout",
    source_kind="blog",
    source_ref=(
        "https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/ "
        "(Zarattini, Pagani, Barbon: Donchian-channel trend entries with volatility sizing; the lab "
        "tests the long-only stock version)"
    ),
    hypothesis=(
        "Every stock book in this lab ranks names on a signal and re-picks on a calendar. A Donchian "
        "channel is an event rule instead: a name enters the book the day its close exceeds its "
        "highest close of the prior 100 sessions and leaves the day it closes below its lowest close "
        "of the prior 50 sessions, so holding time is set by the price path, not the calendar, and a "
        "name that keeps trending is never sold for a re-rank. Universe: the 100 most-traded index "
        "members, at most 20 slots of 5%, fresh breakouts fill empty slots by largest 100-day gain, "
        "unfilled slots sit in cash; behind the SPY 200-day switch like the lab's other books. "
        "Everything runs in fractional shares at Gotrade's real fees on the owner's monthly deposits, "
        "daily decisions and no resizing (a daily-hold-frac-gotrade-noresize preset; none exists, so "
        "a winner needs one before promote). Arms: BRK100-50 (the treatment), BRK55-20 (the classic "
        "turtle windows), BRK200-100 (slow), BRK100-50-RAND (Control: the same slots, exit rule and "
        "daily entry count, entered names drawn blind from the same pool of 100, so the entry rule is "
        "priced apart from the exit rule), BRK100-CAL63 (Control: the same breakout entry with a "
        "calendar exit, 63 sessions after the latest breakout, to price the path-set holding time), "
        "and BRK100-50-NOSW (the treatment never switching to cash, the no-opinion arm for the "
        "switch). No recorded trial holds these books on this chassis, so nothing is cited in place "
        "of running. Closest recorded: the 52-week-high momentum books (M0015, M0017, M0232), which "
        "rank on nearness to a high without an event trigger or a stop-low exit, and M0462's own-"
        "drawdown exit. Breakout channels were published in the 1980s and re-popularised in 2023, so "
        "dev may overstate them. SUCCESS: a lead over SPY on deposit-matched money above the "
        "random-entry control by more than 2 points a year, a positive 2009-2015 edge, worst fall "
        "under 25%."
    ),
    expected_failure=(
        "Breakouts in the busiest names are already crowded momentum and the 50-day-low exit whipsaws "
        "at real fees, so the book lands on plain momentum's results at higher turnover. The "
        "random-entry control, which keeps the same exits, comes within 2 points a year of the "
        "treatment: the exit rule and the switch, not the breakout, do the work. Nothing beats SPY in "
        "2009-2015."
    ),
    candidates=(
        _v("BRK100-50", DonchianParams(N20, 100, 50), "enter on a 100-day high close, exit under the 50-day low close"),
        _v("BRK55-20", DonchianParams(N20, 55, 20), "the classic turtle windows: 55 in, 20 out"),
        _v("BRK200-100", DonchianParams(N20, 200, 100), "the slow channel: 200 in, 100 out"),
        _v("BRK100-50-RAND", DonchianParams(N20, 100, 50, mode="blind", seed=6181),
           "Control: same exits and daily entry count as BRK100-50, entered names a blind draw from the same pool of 100"),
        _v("BRK100-CAL63", DonchianParams(N20, 100, 50, exit_kind="calendar", hold_n=63),
           "Control: the same breakout entry, calendar exit 63 sessions after the latest breakout"),
        _v("BRK100-50-NOSW", DonchianParams(NOSW, 100, 50),
           "the treatment never switching to cash: the no-opinion arm for the 200-day switch"),
    ),
    seen_keys=("concept:donchian-breakout-stocks",),
)
