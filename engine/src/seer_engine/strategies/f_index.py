"""Families F1 and F10 (trend-timed index) and F11 (turn-of-month calendar). Pure.

Both allocators hold at most ONE instrument (``params.hold``) at full weight, or nothing. The
book engine signal-exits a held instrument the allocator stops returning, and the runner fills
the residual weight with ``rules.idle_symbol`` (T-bills) when the rules name one.

``TimingAllocator`` (id ``"F1"``; the registry's F10 candidates are the same allocator holding a
2x ETF). On ``data_date`` d, from the SIGNAL instrument's own bars through d:
    sma        close(d) > SMA(n) of the last n daily closes (strict)
    month_sma  close(d) > mean of the last n ``month_end_closes`` (strict; a month whose last
               NYSE session is d counts as completed, so close(d) is then in the mean)
    abs_mom    close(d) / close(n sessions earlier) − 1 > 0 (strict)
    always     on (the signal is not read; n is ignored)
Fewer bars than the rule needs, or a non-finite value: off. Means are summed left to right over
exactly the bars they cover (``indicators``' bit-identity rule), so the answer is the same float
however much history is loaded.

``CalendarAllocator`` (id ``"F11"``). The traded session is ``S = next_session(d)``. On iff S is
one of the last ``days_before`` NYSE sessions of its calendar month or one of the first
``days_after`` NYSE sessions of its month, and (with ``trend``) trend[0] close(d) > SMA(trend[1]).
The NYSE calendar (holidays and the unscheduled closures ``pandas_market_calendars`` records) is
treated as known in advance: it is calendar knowledge, not price data, and no bar dated after d
is read.

Shared target rule (``_hold_targets``), with ``state`` the signal's answer on d:
    off                                         -> ()
    unknown (the signal has no bar dated d)     -> keep ``hold`` only if it is held, else ()
    on                                          -> Target(hold, weight 1, last = close(d)) when
                                                   hold has a bar dated d; when it has none,
                                                   only a HELD hold is kept (last = its latest
                                                   close <= d) — never a new entry.
``held`` changes nothing else: the decision is a pure function of the signal and the calendar.

``prepare`` keeps a frozen view of the histories; ``targets_prepared`` runs the same code as
``targets`` on it, so the P4 identity (``Allocator`` contract) holds by construction.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass
from datetime import date, timedelta
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from seer_engine import dates
from seer_engine.sim import Target, equal_weight
from seer_engine.strategies.allocator import month_end_closes, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import return_window, sma_window

TimingRule = Literal["sma", "month_sma", "abs_mom", "always"]
TIMING_RULES: tuple[str, ...] = ("sma", "month_sma", "abs_mom", "always")
MAX_SESSIONS_PER_MONTH = 23  # the most NYSE sessions any calendar month has had (1993-2026, checked)
MAX_CALENDAR_DAYS = 10  # days_before / days_after upper bound (a sanity bound, not a tuning range)
FULL_WEIGHT = equal_weight(1)


def _symbol(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str, got {type(value).__name__}")
    if not value or value != value.strip() or value != value.upper():
        raise ValueError(f"{name} must be a non-empty upper-case symbol, got {value!r}")
    return value


def _count(name: str, value: object, low: int, high: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < low or (high is not None and value > high):
        bound = f">= {low}" if high is None else f"in [{low}, {high}]"
        raise ValueError(f"{name} must be {bound}, got {value}")
    return value


def _trend(value: object) -> tuple[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError(f"trend must be None or a (symbol, n) tuple, got {value!r}")
    _symbol("trend symbol", value[0])
    _count("trend n", value[1], 1)
    return value


def _plain_trend(trend: tuple[str, int] | None) -> str:
    return "none" if trend is None else f"{trend[0]}:{trend[1]}"


@dataclass(frozen=True, slots=True)
class TimingParams:
    """F1/F10: hold ``hold`` while ``signal``'s own bars say "on" under ``rule``."""

    hold: str  # the instrument held while on (SPY, QQQ, SSO, QLD)
    signal: str  # the instrument whose own bars decide
    rule: TimingRule
    n: int = 200  # sma: SMA(n) of daily closes; month_sma: n month-end closes; abs_mom: n sessions; always: ignored

    def __post_init__(self) -> None:
        _symbol("hold", self.hold)
        _symbol("signal", self.signal)
        if not isinstance(self.rule, str):
            raise TypeError(f"rule must be a str, got {type(self.rule).__name__}")
        if self.rule not in TIMING_RULES:
            raise ValueError(f"rule must be one of {TIMING_RULES}, got {self.rule!r}")
        _count("n", self.n, 1)

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        return {"hold": self.hold, "signal": self.signal, "rule": self.rule, "n": str(self.n)}


@dataclass(frozen=True, slots=True)
class CalendarParams:
    """F11: hold ``hold`` over the turn of each month, optionally only above a trend."""

    hold: str
    days_before: int = 1  # the last k NYSE sessions of a month …
    days_after: int = 3  # … and the first m NYSE sessions of the next month
    trend: tuple[str, int] | None = None  # also require trend[0] close(d) > SMA(trend[1]) (strict)

    def __post_init__(self) -> None:
        _symbol("hold", self.hold)
        _count("days_before", self.days_before, 0, MAX_CALENDAR_DAYS)
        _count("days_after", self.days_after, 0, MAX_CALENDAR_DAYS)
        if self.days_before + self.days_after == 0:
            raise ValueError("days_before + days_after must be >= 1 (the allocator would never hold)")
        _trend(self.trend)

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        return {
            "hold": self.hold,
            "days_before": str(self.days_before),
            "days_after": str(self.days_after),
            "trend": _plain_trend(self.trend),
        }


@dataclass(frozen=True, slots=True, eq=False)
class IndexPrepared:
    """The histories, frozen. F1 and F11 read a few bars per decision, so nothing is precomputed."""

    history: Mapping[str, History]


def _timing(params: Any) -> TimingParams:
    if not isinstance(params, TimingParams):
        raise TypeError(f"params must be TimingParams, got {type(params).__name__}")
    return params


def _calendar(params: Any) -> CalendarParams:
    if not isinstance(params, CalendarParams):
        raise TypeError(f"params must be CalendarParams, got {type(params).__name__}")
    return params


def _prepared(prepared: Any) -> IndexPrepared:
    if not isinstance(prepared, IndexPrepared):
        raise TypeError(f"prepared must be IndexPrepared, got {type(prepared).__name__}")
    return prepared


def _prepare(history: Mapping[str, History]) -> IndexPrepared:
    return IndexPrepared(MappingProxyType(dict(history)))


# ---- signals: True = on, False = off, None = unknown (no bar dated d) ----------------------------


def above_sma(h: History | None, data_date: date, n: int) -> bool | None:
    """close(d) > SMA(n) of the last n closes through d (strict). None without a bar dated d."""
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None:
        return None
    if i + 1 < n:
        return False
    sma = float(sma_window(h.close[i + 1 - n : i + 1].reshape(1, n), n)[0])
    close = float(h.close[i])
    return bool(np.isfinite(sma) and np.isfinite(close) and close > sma)


def above_month_sma(h: History | None, data_date: date, n: int) -> bool | None:
    """close(d) > mean of the last n completed month-end closes (strict). None without a bar dated d."""
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None:
        return None
    closes = month_end_closes(h.upto(data_date), data_date)
    if closes.shape[0] < n:
        return False
    window = np.ascontiguousarray(closes[-n:], dtype=np.float64).reshape(1, n)
    mean = float(sma_window(window, n)[0])
    close = float(h.close[i])
    return bool(np.isfinite(mean) and np.isfinite(close) and close > mean)


def positive_momentum(h: History | None, data_date: date, n: int) -> bool | None:
    """close(d) / close(n sessions earlier) − 1 > 0 (strict). None without a bar dated d."""
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None:
        return None
    if i < n:
        return False
    ret = float(return_window(h.close[i - n : i + 1].reshape(1, n + 1), n)[0])
    return bool(np.isfinite(ret) and ret > 0.0)


def timing_state(history: Mapping[str, History], data_date: date, params: TimingParams) -> bool | None:
    """``params.rule`` evaluated on ``params.signal``'s bars through ``data_date``."""
    p = _timing(params)
    if p.rule == "always":
        return True
    h = history.get(p.signal)
    if p.rule == "sma":
        return above_sma(h, data_date, p.n)
    if p.rule == "month_sma":
        return above_month_sma(h, data_date, p.n)
    return positive_momentum(h, data_date, p.n)


def _month_sessions(session: date) -> list[date]:
    first = session.replace(day=1)
    following = date(first.year + first.month // 12, first.month % 12 + 1, 1)
    return dates.sessions(first, following - timedelta(days=1))


def turn_of_month(session: date, days_before: int, days_after: int) -> bool:
    """True when ``session`` is one of the last ``days_before`` or first ``days_after`` NYSE sessions of its month."""
    as_day(session)
    _count("days_before", days_before, 0)
    _count("days_after", days_after, 0)
    if not dates.is_session(session):
        raise ValueError(f"{session} is not an NYSE session")
    month = _month_sessions(session)
    i = month.index(session)
    return i < days_after or i >= len(month) - days_before


# ---- the shared target rule --------------------------------------------------------------------


def _latest_row(h: History, data_date: date) -> int | None:
    j = int(np.searchsorted(h.dates, as_day(data_date), side="right")) - 1
    return None if j < 0 else j


def _hold_targets(
    history: Mapping[str, History], hold: str, data_date: date, held: Set[str], state: bool | None
) -> tuple[Target, ...]:
    if state is False or (state is None and hold not in held):
        return ()
    h = history.get(hold)
    if h is None:
        return ()
    i = h.index_of(data_date)
    if i is None:
        if hold not in held:
            return ()  # a symbol with no bar dated d is never a NEW target
        i = _latest_row(h, data_date)
        if i is None:
            return ()
    target = target_from_close(hold, float(h.close[i]), FULL_WEIGHT)
    return () if target is None else (target,)


# ---- the allocators ----------------------------------------------------------------------------


class TimingAllocator:
    """F1 (and F10 with a leveraged ``hold``) behind the ``Allocator`` protocol."""

    id = "F1"

    def lookback(self, params: Any) -> int:
        p = _timing(params)
        if p.rule == "sma":
            return p.n
        if p.rule == "abs_mom":
            return p.n + 1
        if p.rule == "month_sma":
            return MAX_SESSIONS_PER_MONTH * p.n  # always spans >= n completed months without gaps
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _timing(params)
        return tuple(sorted({p.hold, p.signal}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_timing(params).hold,)

    def uses_members(self, params: Any) -> bool:
        _timing(params)
        return False

    def targets(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _timing(params)
        as_day(data_date)
        return _hold_targets(history, p.hold, data_date, held, timing_state(history, data_date, p))

    def prepare(self, history: Mapping[str, History]) -> IndexPrepared:
        return _prepare(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self.targets(_prepared(prepared).history, members, data_date, held, params)


class CalendarAllocator:
    """F11 behind the ``Allocator`` protocol."""

    id = "F11"

    def lookback(self, params: Any) -> int:
        p = _calendar(params)
        return 1 if p.trend is None else p.trend[1]

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _calendar(params)
        return tuple(sorted({p.hold} | ({p.trend[0]} if p.trend is not None else set())))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_calendar(params).hold,)

    def uses_members(self, params: Any) -> bool:
        _calendar(params)
        return False

    def targets(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _calendar(params)
        as_day(data_date)
        if not turn_of_month(dates.next_session(data_date), p.days_before, p.days_after):
            return ()
        state = True if p.trend is None else above_sma(history.get(p.trend[0]), data_date, p.trend[1])
        return _hold_targets(history, p.hold, data_date, held, state)

    def prepare(self, history: Mapping[str, History]) -> IndexPrepared:
        return _prepare(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self.targets(_prepared(prepared).history, members, data_date, held, params)


TIMING = TimingAllocator()
CALENDAR = CalendarAllocator()
