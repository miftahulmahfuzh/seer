> Adopted from `TRADE_RULES_DEV_SEARCH_PLAN.md` phase 5. Source: `.workflows/plan/trade-rules-dev-search/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: Families F1/F10/F11: index timing and calendar

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R3 — no look-ahead and P4 identity for the F1/F10/F11 families; the prepared and single-window paths agree
**Depends on:** Phase 2 (and, through it, Phase 1)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

After this phase, `seer_engine.strategies.f_index` provides two pure allocators behind phase 2's
`Allocator` protocol:
- `TIMING` (id `"F1"`) holds one index ETF while its signal is on. It has four rules (`sma`,
  `month_sma`, `abs_mom`, `always`). F10 is the same allocator with a 2x `hold`.
- `CALENDAR` (id `"F11"`) holds an ETF over the turn of each month, with an optional trend gate.

Both have hand-checked signal tests, calendar tests around month ends, holidays, short months
and an unscheduled closure, and P4-identity and no-look-ahead proofs. Phase 11 can then register
candidates 1, 3–22 and 53–54 with the exact params from the index's Registry table.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates** (all in `engine/src/seer_engine/strategies/f_index.py`, new):
- `TimingParams(hold: str, signal: str, rule: Literal["sma","month_sma","abs_mom","always"], n: int = 200)`:
  frozen, slots. `__post_init__` raises TypeError or ValueError. `as_dict() -> dict[str, str]`
  returns the keys `hold, signal, rule, n`, in that order.
- `CalendarParams(hold: str, days_before: int = 1, days_after: int = 3, trend: tuple[str, int] | None = None)`:
  frozen, slots. `__post_init__` checks that each of `days_before` and `days_after` is in
  [0, 10] and that they sum to ≥ 1. `as_dict()` returns the keys `hold, days_before, days_after,
  trend`, in that order. trend renders as `"none"` or `"SPY:200"`.
- `TimingAllocator` with `id = "F1"`, and the singleton `TIMING`.
- `CalendarAllocator` with `id = "F11"`, and the singleton `CALENDAR`.
- `IndexPrepared(history: Mapping[str, History])`: the `prepare()` value (a frozen
  `MappingProxyType` copy of the histories).
- Public pure helpers, for phases 6–8 to reuse if they want (not required):
  - `above_sma(h, d, n) -> bool | None`
  - `above_month_sma(h, d, n) -> bool | None`
  - `positive_momentum(h, d, n) -> bool | None`
  - `timing_state(history, d, params) -> bool | None`
  - `turn_of_month(session, days_before, days_after) -> bool`
- Constants: `TIMING_RULES`, `MAX_SESSIONS_PER_MONTH = 23`, `MAX_CALENDAR_DAYS = 10` and
  `FULL_WEIGHT = equal_weight(1)`.
- `engine/tests/test_f_index.py` (new): 109 test items.

**Signature changes:** none.

**Allocator method values (phase 9's `candidate_window` and phase 11's registry rely on these):**

| params | `lookback` | `symbols` | `holds` | `uses_members` |
|---|---|---|---|---|
| `TimingParams(rule="sma", n)` | `n` | `sorted({hold, signal})` | `(hold,)` | `False` |
| `TimingParams(rule="abs_mom", n)` | `n + 1` | same | same | `False` |
| `TimingParams(rule="month_sma", n)` | `23 * n` (at least n completed months, proven by a test) | same | same | `False` |
| `TimingParams(rule="always")` | `1` (n is ignored) | `sorted({hold, signal})` (the signal is still listed) | same | `False` |
| `CalendarParams(trend=None)` | `1` | `(hold,)` | `(hold,)` | `False` |
| `CalendarParams(trend=(s, n))` | `n` | `sorted({hold, s})` | `(hold,)` | `False` |

**Requires (from earlier phases), exactly as the index contract states:**
- Phase 1, via `seer_engine.sim` exports:
  - `Target(symbol, weight, last, limit=None, stop=None, take=None)`, which accepts
    `weight == Decimal("1.000000")`;
  - `equal_weight(1) == Decimal("1.000000")`.
- Phase 2, `seer_engine.strategies.allocator`:
  - `Allocator`, a `runtime_checkable` Protocol;
  - `target_from_close(symbol, close: float, weight: Decimal) -> Target | None`. Its `last` is
    `q(to_decimal(close))`, and it returns `None` when that is ≤ 0;
  - `month_end_closes(h: History, data_date: date) -> np.ndarray`. It gives a float64 array of
    the last close of each completed calendar month, ascending. A month whose last NYSE session
    is `data_date` counts as completed. It reads only bars ≤ `data_date`.
- Phase 2, `seer_engine.strategies.indicators.return_window(close, n, skip=0)`: a (rows, W)
  window gives `c[:, -1-skip] / c[:, -1-n] − 1`.
- Phase 2, `engine/tests/allocatorkit.py` (plan index D-E, phase 2's kit is canonical):
  `assert_p4_identity(allocator, history, members_fn, dates, held_sets, params, *,
  max_weight_sum=Decimal(1), check_lookback=True) -> int` and
  `assert_no_lookahead(allocator, history, members_fn, sessions, held_sets, params) -> int`,
  with `held_sets` and `params` as non-empty **lists**, `dates` as data dates and `sessions` as
  sessions S. Used by exactly one test, `test_allocatorkit_contract`. The full P4-identity and
  no-look-ahead assertions are also made locally with `stratkit`'s existing helpers.

**Leaves alone (owned by others):**
- `strategies/allocator.py`, `indicators.py` and `tests/allocatorkit.py` (phase 2);
- `sim/*` (phase 1);
- `strategies/f_rotation.py` (phase 6), `f_factor.py` (phase 7) and `f_swing.py` (phase 8);
- `strategies/__init__.py`. It is **not** edited. Consumers import from
  `seer_engine.strategies.f_index` directly.
- `backtest/*`, including `backtest/registry.py` (phase 11), which imports `TIMING`,
  `CALENDAR`, `TimingParams` and `CalendarParams` from here.

## Decisions made in this phase (record in the index's Decisions table)

| Fork | Chosen | Why |
|---|---|---|
| The signal has no bar dated d (a data gap, or no history) | The state is **unknown**. A held `hold` is kept, at its latest close ≤ d. Otherwise the result is `()` | No information means no trade. A gap must not create a round trip (which would add a fake "trade" to D8's count) |
| `hold` has no bar dated d | It is never a new target (the index contract). A held `hold` with an "on" or unknown state is kept at its latest close ≤ d | The same as `PicksAllocator`'s held-symbol rule |
| Too little history for the rule (including the trend gate) | Off | Not enough data is not an "on" signal. At the start nothing is held, so this only delays entry |
| `always` | It never reads the signal. `n` is ignored, but it must still be ≥ 1. `symbols` still lists the signal | REF-SPY-HOLD uses `T(SPY,SPY,always,1)`. Listing the signal keeps `symbols` uniform |
| The `month_sma` lookback | `23 × n` sessions (23 = the most NYSE sessions in any month from 1993 to 2026, measured) | `candidate_window` needs a bar count. 23n consecutive sessions always contain n completed months, as `test_month_sma_lookback_always_spans_n_completed_months` checks on 1993–2016 |
| A single `lookback` int for `hold ≠ signal` | It applies to `hold` as well. For example, `T(QLD,QQQ,sma,200)` starts 200 QLD bars after QLD's launch | The protocol has one int. This is conservative and costs some months of dev window only for F10 |
| The calendar's knowledge of future sessions | The NYSE calendar from `seer_engine.dates` (`pandas_market_calendars`) is treated as known when deciding on d, including unscheduled closures such as Hurricane Sandy in 2012 | It is calendar data, not price data, and no bar after d is read. With `days_before = 1`, an unscheduled closure has never moved a month's last session in 1993–2015 |
| `trend` text in `as_dict` | `"none"`, or `f"{symbol}:{n}"` | It is plain and deterministic, and it is the shared encoding of every family (plan index D-F) |
| `prepare` | A frozen copy of the mapping. `targets_prepared` runs `targets` on it | F1 and F11 read a few bars per decision. A ~5,700-session run costs milliseconds, so identity holds by construction and needs no second code path |
| Symbol validation | Non-empty, no surrounding spaces, upper-case | It catches `"spy"` typos in the registry |

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/f_index.py` | create (new file, lines 1–380) | `TimingParams`, `CalendarParams`, `IndexPrepared`, signal helpers, `turn_of_month`, `TimingAllocator`/`TIMING`, `CalendarAllocator`/`CALENDAR` |
| `engine/tests/test_f_index.py` | create (new file, lines 1–497) | 109 test items: params, the protocol surface, hand-checked signals, the calendar window, missing bars and `held`, P4 identity and no look-ahead, and the allocatorkit cross-check |

No existing file is edited. The purity glob in `tests/test_strategy_purity.py` (`strategies/*.py`)
picks up `f_index.py` automatically. The module imports only `numpy`, `seer_engine.dates`,
`seer_engine.sim`, `seer_engine.strategies.{allocator,base,indicators}` and the stdlib (`types`,
`dataclasses`, `datetime`, `collections.abc`, `typing`). Probed: importing `seer_engine.dates`
loads none of psycopg, requests, yfinance or `seer_engine.bars`.

## Implementation Steps

### Step 1: Create the module
**File:** `engine/src/seer_engine/strategies/f_index.py:1` (new)
**Change:** Write the whole file below.
**Code:**
```python
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
```
**Impact:**
- Additive only.
- `tests/test_strategy_purity.py` now also scans this module. It has no clock, random, print or
  open, and imports only pure modules.
- The import needs phase 1's `Target` and `equal_weight` to be exported from `seer_engine.sim`,
  and phase 2's `allocator.py` and `indicators.return_window`.

### Step 2: Create the tests
**File:** `engine/tests/test_f_index.py:1` (new)
**Change:** Write the whole file below.

What it proves:
- **Params:**
  - type and value validation, 10 bad `TimingParams` and 11 bad `CalendarParams`;
  - `as_dict` key order and text;
  - frozen and hashable.
- **The protocol surface:**
  - `isinstance(..., Allocator)`;
  - the ids `F1` and `F11`;
  - the lookback/symbols/holds/uses_members table above, 9 cases;
  - the `23 × n` month-coverage proof on the real NYSE calendar for 1993–2016;
  - wrong param or prepared types raise TypeError;
  - `prepare` snapshot isolation.
- **Hand-checked signals:**
  - `sma`: on, off, equal (strict), only the last n bars read, too short;
  - `month_sma`: 6 cases, including April 30 2019 ending its month, which flips the answer
    against April 29;
  - `abs_mom`: positive, exactly 0 (strict), negative, base n back, too short;
  - `always`, with no signal history at all;
  - `hold ≠ signal`.
  - The `Target` fields: weight 1, `last` = the 4-dp half-up close, no limit/stop/take.
- **Missing bars and `held`:**
  - a hold without a bar on d is never a new target, and a held one is kept at its last close;
  - a signal without a bar on d keeps only what is held;
  - `held` never changes a known decision (4 held sets).
- **The calendar:** 33 `turn_of_month` cases, which cover:
  - Good Friday at a month end (2018-03-29);
  - Good Friday among the first sessions (April 2021);
  - New Year;
  - February 2019 with `days_before = 2`;
  - a weekend month end;
  - July 4 inside the first four sessions;
  - the Hurricane Sandy closure (2012-10-26 counts among the last two sessions);
  - one side set to zero;
  - non-sessions rejected.

  The tests also check that the traded session is `next_session(d)` (the exact list of "on"
  data dates around Good Friday 2018), that a held position is exited out of the window, and the
  trend gate: up, down, equal (strict), unknown with and without a held position, and too short.
- **R3:** `test_p4_identity_and_no_look_ahead`, over 7 param sets × 240 sessions × 3 held sets:
  - `targets(H)`, `targets(upto d)` and `targets_prepared(prepare(H))` are equal;
  - so are `targets` after **changing** every bar dated ≥ S and after **deleting** every bar
    dated ≥ S, and `targets_prepared(prepare(changed))`;
  - on and off both occur, so the test is not vacuous;
  - `last == q(close on d)` except for a held symbol kept across a gap.
  - The guard `test_the_mutation_does_change_a_decision_read_at_s` shows that the mutation
    matters when it is visible.
  - `test_allocatorkit_contract` runs phase 2's shared checker over the same 7 param sets.

**Code:**
```python
"""Families F1/F10/F11 (strategies/f_index.py): index timing and the turn-of-month calendar."""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest
from stratkit import drop_days, hist, mutate_from, session_days, truncate_before

from seer_engine.dates import next_session, prev_session, sessions
from seer_engine.sim import Target
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import (
    CALENDAR,
    MAX_SESSIONS_PER_MONTH,
    TIMING,
    CalendarAllocator,
    CalendarParams,
    IndexPrepared,
    TimingAllocator,
    TimingParams,
    turn_of_month,
)

NONE: frozenset[str] = frozenset()
NO_MEMBERS: frozenset[str] = frozenset()
D0 = date(2019, 1, 2)  # stratkit.START: hist() bars run on consecutive sessions from here


def T(hold: str, signal: str, rule: str, n: int) -> TimingParams:  # noqa: N802 — the plan index's notation
    return TimingParams(hold=hold, signal=signal, rule=rule, n=n)


def full(symbol: str, last: str) -> Target:
    return Target(symbol, Decimal("1"), Decimal(last))


def last_day(h: History) -> date:
    d = h.last_date()
    assert d is not None
    return d


def run(allocator, history, d, params, held=NONE):
    return allocator.targets(history, NO_MEMBERS, d, held, params)


# ---- params --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kw, exc",
    [
        ({"hold": "", "signal": "SPY", "rule": "sma"}, ValueError),
        ({"hold": "spy", "signal": "SPY", "rule": "sma"}, ValueError),
        ({"hold": " SPY", "signal": "SPY", "rule": "sma"}, ValueError),
        ({"hold": 1, "signal": "SPY", "rule": "sma"}, TypeError),
        ({"hold": "SPY", "signal": None, "rule": "sma"}, TypeError),
        ({"hold": "SPY", "signal": "SPY", "rule": "ema"}, ValueError),
        ({"hold": "SPY", "signal": "SPY", "rule": 3}, TypeError),
        ({"hold": "SPY", "signal": "SPY", "rule": "sma", "n": 0}, ValueError),
        ({"hold": "SPY", "signal": "SPY", "rule": "sma", "n": True}, TypeError),
        ({"hold": "SPY", "signal": "SPY", "rule": "sma", "n": 200.0}, TypeError),
    ],
)
def test_timing_params_reject_bad_values(kw, exc):
    with pytest.raises(exc):
        TimingParams(**kw)


@pytest.mark.parametrize(
    "kw, exc",
    [
        ({"hold": ""}, ValueError),
        ({"hold": "SPY", "days_before": -1}, ValueError),
        ({"hold": "SPY", "days_after": 11}, ValueError),
        ({"hold": "SPY", "days_before": 0, "days_after": 0}, ValueError),
        ({"hold": "SPY", "days_before": 1.0}, TypeError),
        ({"hold": "SPY", "days_after": False}, TypeError),
        ({"hold": "SPY", "trend": ["SPY", 200]}, TypeError),
        ({"hold": "SPY", "trend": ("SPY",)}, TypeError),
        ({"hold": "SPY", "trend": ("SPY", 0)}, ValueError),
        ({"hold": "SPY", "trend": ("spy", 200)}, ValueError),
        ({"hold": "SPY", "trend": ("SPY", "200")}, TypeError),
    ],
)
def test_calendar_params_reject_bad_values(kw, exc):
    with pytest.raises(exc):
        CalendarParams(**kw)


def test_params_defaults_and_as_dict_in_fixed_order():
    p = TimingParams(hold="SSO", signal="SPY", rule="month_sma", n=10)
    assert p.as_dict() == {"hold": "SSO", "signal": "SPY", "rule": "month_sma", "n": "10"}
    assert list(p.as_dict()) == ["hold", "signal", "rule", "n"]
    assert TimingParams(hold="SPY", signal="SPY", rule="sma").n == 200
    c = CalendarParams("QQQ")
    assert (c.days_before, c.days_after, c.trend) == (1, 3, None)
    assert c.as_dict() == {"hold": "QQQ", "days_before": "1", "days_after": "3", "trend": "none"}
    assert list(c.as_dict()) == ["hold", "days_before", "days_after", "trend"]
    assert CalendarParams("QQQ", 2, 0, ("QQQ", 200)).as_dict()["trend"] == "QQQ:200"
    assert CalendarParams("SPY", 0, 1).days_before == 0  # one side may be zero


def test_params_are_frozen_and_hashable():
    p = T("SPY", "SPY", "sma", 200)
    with pytest.raises(AttributeError):
        p.n = 100  # type: ignore[misc]
    assert hash(p) == hash(T("SPY", "SPY", "sma", 200))
    assert hash(CalendarParams("SPY", 1, 3, ("SPY", 200))) == hash(CalendarParams("SPY", 1, 3, ("SPY", 200)))


# ---- the protocol surface ------------------------------------------------------------------------


def test_singletons_implement_the_allocator_protocol():
    assert isinstance(TIMING, TimingAllocator) and isinstance(CALENDAR, CalendarAllocator)
    assert isinstance(TIMING, Allocator) and isinstance(CALENDAR, Allocator)
    assert (TIMING.id, CALENDAR.id) == ("F1", "F11")


@pytest.mark.parametrize(
    "allocator, params, lookback, symbols, holds",
    [
        (TIMING, T("SPY", "SPY", "sma", 200), 200, ("SPY",), ("SPY",)),
        (TIMING, T("QQQ", "SPY", "sma", 200), 200, ("QQQ", "SPY"), ("QQQ",)),
        (TIMING, T("SSO", "SPY", "month_sma", 10), MAX_SESSIONS_PER_MONTH * 10, ("SPY", "SSO"), ("SSO",)),
        (TIMING, T("SPY", "SPY", "abs_mom", 252), 253, ("SPY",), ("SPY",)),
        (TIMING, T("SPY", "SPY", "always", 1), 1, ("SPY",), ("SPY",)),
        (TIMING, T("QLD", "QQQ", "always", 200), 1, ("QLD", "QQQ"), ("QLD",)),
        (CALENDAR, CalendarParams("SPY", 1, 3, None), 1, ("SPY",), ("SPY",)),
        (CALENDAR, CalendarParams("SPY", 1, 3, ("SPY", 200)), 200, ("SPY",), ("SPY",)),
        (CALENDAR, CalendarParams("QQQ", 1, 3, ("SPY", 150)), 150, ("QQQ", "SPY"), ("QQQ",)),
    ],
)
def test_lookback_symbols_holds_and_members(allocator, params, lookback, symbols, holds):
    assert allocator.lookback(params) == lookback
    assert allocator.symbols(params) == symbols
    assert allocator.holds(params) == holds
    assert set(allocator.holds(params)) <= set(allocator.symbols(params))
    assert allocator.uses_members(params) is False


def test_month_sma_lookback_always_spans_n_completed_months():
    # 23 × n consecutive sessions end on any day and still contain n completed month ends.
    days = sessions(date(1993, 1, 4), date(2016, 12, 30))
    n = 10
    need = TIMING.lookback(T("SPY", "SPY", "month_sma", n))
    for end in range(need - 1, len(days), 7):
        window = days[end + 1 - need : end + 1]
        d = window[-1]
        completed = {(x.year, x.month) for x in window if (x.year, x.month) != (d.year, d.month)}
        if next_session(d).month != d.month:
            completed.add((d.year, d.month))  # d ends its month
        assert len(completed) >= n, d


def test_wrong_params_or_prepared_types_raise():
    h = {"SPY": hist("SPY", [1.0, 2.0, 3.0])}
    cal = CalendarParams("SPY")
    tim = T("SPY", "SPY", "sma", 3)
    for method in ("lookback", "symbols", "holds", "uses_members"):
        with pytest.raises(TypeError):
            getattr(TIMING, method)(cal)
        with pytest.raises(TypeError):
            getattr(CALENDAR, method)(tim)
    with pytest.raises(TypeError):
        run(TIMING, h, D0, cal)
    with pytest.raises(TypeError):
        run(CALENDAR, h, D0, tim)
    with pytest.raises(TypeError):
        TIMING.targets_prepared(h, NO_MEMBERS, D0, NONE, tim)  # a plain dict is not IndexPrepared
    with pytest.raises(TypeError):
        run(TIMING, h, D0.isoformat(), tim)


def test_prepare_freezes_a_snapshot_of_the_mapping():
    h = {"SPY": hist("SPY", [1.0, 2.0, 3.0])}
    prepared = TIMING.prepare(h)
    assert isinstance(prepared, IndexPrepared) and isinstance(CALENDAR.prepare(h), IndexPrepared)
    h["SPY"] = hist("SPY", [3.0, 2.0, 1.0])  # later edits to the caller's dict do not leak in
    d = date(2019, 1, 4)
    assert TIMING.targets_prepared(prepared, NO_MEMBERS, d, NONE, T("SPY", "SPY", "sma", 3)) == (full("SPY", "3"),)
    assert TIMING.targets_prepared(TIMING.prepare({}), NO_MEMBERS, d, NONE, T("SPY", "SPY", "sma", 3)) == ()


# ---- F1 signals, hand-checked --------------------------------------------------------------------


@pytest.mark.parametrize(
    "closes, on",
    [
        ([1.0, 2.0, 3.0], True),  # SMA3 = 2, close 3
        ([3.0, 2.0, 1.0], False),  # SMA3 = 2, close 1
        ([2.0, 2.0, 2.0], False),  # close == SMA: strict
        ([100.0, 1.0, 2.0, 3.0], True),  # only the last 3 closes are averaged
        ([1.0, 2.0], False),  # fewer than n bars: off
    ],
)
def test_sma_rule_hand_checked(closes, on):
    h = {"SPY": hist("SPY", closes)}
    got = run(TIMING, h, last_day(h["SPY"]), T("SPY", "SPY", "sma", 3))
    assert got == ((full("SPY", f"{closes[-1]:.4f}"),) if on else ())


def test_target_is_full_weight_at_the_data_date_close_with_no_bracket():
    h = {"SPY": hist("SPY", [10.0, 11.0, 123.45675])}  # SMA3 = 48.15…; close rounds half-up
    (t,) = run(TIMING, h, last_day(h["SPY"]), T("SPY", "SPY", "sma", 3))
    assert t == Target("SPY", Decimal("1"), Decimal("123.4568"))
    assert (t.limit, t.stop, t.take) == (None, None, None)
    assert t.weight == Decimal(1) and t.last.as_tuple().exponent == -4


def month_history(values: dict[int, float], last: date) -> History:
    """SPY closes constant within each 2019 month (``values[month]``), every session to ``last``."""
    days = sessions(D0, last)
    return hist("SPY", [values[d.month] for d in days], days=days)


@pytest.mark.parametrize(
    "n, d, on",
    [
        (3, date(2019, 4, 29), True),  # completed Jan–Mar: mean(10, 20, 30) = 20 < 25
        (3, date(2019, 4, 30), False),  # Apr 30 ends April: mean(20, 30, 25) = 25, close 25 (strict)
        (3, date(2019, 5, 15), True),  # mean(20, 30, 25) = 25 < 26
        (2, date(2019, 5, 15), False),  # mean(30, 25) = 27.5 > 26
        (4, date(2019, 5, 15), True),  # mean(10, 20, 30, 25) = 21.25
        (5, date(2019, 5, 15), False),  # only 4 completed months: off
    ],
)
def test_month_sma_rule_hand_checked(n, d, on):
    h = {"SPY": month_history({1: 10.0, 2: 20.0, 3: 30.0, 4: 25.0, 5: 26.0}, date(2019, 5, 31))}
    got = run(TIMING, h, d, T("SPY", "SPY", "month_sma", n))
    close = 26.0 if d.month == 5 else 25.0
    assert got == ((full("SPY", f"{close:.4f}"),) if on else ())


@pytest.mark.parametrize(
    "closes, on",
    [
        ([10.0, 11.0, 12.0, 10.5], True),  # 10.5 / 10 − 1 = 0.05
        ([10.0, 11.0, 12.0, 10.0], False),  # exactly 0: strict
        ([10.0, 11.0, 12.0, 9.9], False),
        ([1.0, 10.0, 11.0, 12.0, 10.5], True),  # the base is n sessions back, not the first bar
        ([11.0, 12.0, 10.5], False),  # fewer than n + 1 bars: off
    ],
)
def test_abs_mom_rule_hand_checked(closes, on):
    h = {"SPY": hist("SPY", closes)}
    got = run(TIMING, h, last_day(h["SPY"]), T("SPY", "SPY", "abs_mom", 3))
    assert got == ((full("SPY", f"{closes[-1]:.4f}"),) if on else ())


def test_always_ignores_the_signal_and_n():
    spy = hist("SPY", [5.0])
    assert run(TIMING, {"SPY": spy}, D0, T("SPY", "SPY", "always", 1)) == (full("SPY", "5"),)
    qqq = hist("QQQ", [7.25, 7.5])
    d = last_day(qqq)
    assert run(TIMING, {"QQQ": qqq}, d, T("QQQ", "SPY", "always", 200)) == (full("QQQ", "7.5"),)


def test_hold_can_differ_from_the_signal():
    qqq = hist("QQQ", [50.0, 50.1, 50.25])
    up = {"SPY": hist("SPY", [1.0, 2.0, 3.0]), "QQQ": qqq}
    down = {"SPY": hist("SPY", [3.0, 2.0, 1.0]), "QQQ": qqq}
    d = last_day(qqq)
    p = T("QQQ", "SPY", "sma", 3)
    assert run(TIMING, up, d, p) == (full("QQQ", "50.25"),)
    assert run(TIMING, down, d, p) == ()
    assert run(TIMING, down, d, p, frozenset({"QQQ"})) == ()  # off: a held hold is signal-exited


# ---- missing bars and the held passthrough -------------------------------------------------------


def test_a_hold_without_a_bar_on_d_is_never_a_new_target():
    days = session_days(3)
    history = {"SPY": hist("SPY", [1.0, 2.0, 3.0], days=days), "QQQ": hist("QQQ", [40.0, 41.0], days=days[:2])}
    p = T("QQQ", "SPY", "sma", 3)
    assert run(TIMING, history, days[2], p) == ()
    # held: kept at its latest close before d, so the engine does not sell on a data gap
    assert run(TIMING, history, days[2], p, frozenset({"QQQ"})) == (full("QQQ", "41"),)
    assert run(TIMING, {"SPY": history["SPY"]}, days[2], p, frozenset({"QQQ"})) == ()  # no history at all


def test_a_signal_without_a_bar_on_d_keeps_only_what_is_held():
    days = session_days(4)
    spy = drop_days(hist("SPY", [1.0, 2.0, 3.0, 4.0], days=days), [days[3]])
    qqq = hist("QQQ", [40.0, 41.0, 42.0, 43.0], days=days)
    p = T("QQQ", "SPY", "sma", 3)
    assert run(TIMING, {"SPY": spy, "QQQ": qqq}, days[3], p) == ()
    assert run(TIMING, {"SPY": spy, "QQQ": qqq}, days[3], p, frozenset({"QQQ"})) == (full("QQQ", "43"),)
    # the signal is the hold and has no bar dated d: a held position is kept at its last close
    same = T("SPY", "SPY", "sma", 3)
    assert run(TIMING, {"SPY": spy}, days[3], same) == ()
    assert run(TIMING, {"SPY": spy}, days[3], same, frozenset({"SPY"})) == (full("SPY", "3"),)
    assert run(TIMING, {"QQQ": qqq}, days[3], p) == ()  # the signal's history is absent: unknown


@pytest.mark.parametrize("held", [NONE, frozenset({"SPY"}), frozenset({"BIL"}), frozenset({"SPY", "BIL"})])
def test_held_does_not_change_a_known_decision(held):
    up = {"SPY": hist("SPY", [1.0, 2.0, 3.0])}
    down = {"SPY": hist("SPY", [3.0, 2.0, 1.0])}
    d = last_day(up["SPY"])
    p = T("SPY", "SPY", "sma", 3)
    assert run(TIMING, up, d, p, held) == (full("SPY", "3"),)
    assert run(TIMING, down, d, p, held) == ()


# ---- F11: the turn-of-month window ---------------------------------------------------------------


@pytest.mark.parametrize(
    "session, before, after, on",
    [
        # March 2018 ends on Maundy Thursday (Good Friday 2018-03-30 closed)
        (date(2018, 3, 28), 1, 3, False),
        (date(2018, 3, 29), 1, 3, True),
        (date(2018, 4, 2), 1, 3, True),
        (date(2018, 4, 4), 1, 3, True),
        (date(2018, 4, 5), 1, 3, False),
        # Good Friday 2021-04-02 inside the first sessions of April: Apr 1, 5, 6
        (date(2021, 3, 30), 1, 3, False),
        (date(2021, 3, 31), 1, 3, True),
        (date(2021, 4, 1), 1, 3, True),
        (date(2021, 4, 5), 1, 3, True),
        (date(2021, 4, 6), 1, 3, True),
        (date(2021, 4, 7), 1, 3, False),
        # New Year: Dec 31 2018, then Jan 2, 3, 4 2019
        (date(2018, 12, 28), 1, 3, False),
        (date(2018, 12, 31), 1, 3, True),
        (date(2019, 1, 2), 1, 3, True),
        (date(2019, 1, 4), 1, 3, True),
        (date(2019, 1, 7), 1, 3, False),
        # a short month (February 2019 ends Thursday the 28th), two sessions before
        (date(2019, 2, 26), 2, 3, False),
        (date(2019, 2, 27), 2, 3, True),
        (date(2019, 2, 28), 2, 3, True),
        (date(2019, 3, 1), 2, 3, True),
        (date(2019, 3, 5), 2, 3, True),
        (date(2019, 3, 6), 2, 3, False),
        # a month ending on a weekend (March 2019 ends Sunday the 31st)
        (date(2019, 3, 28), 1, 3, False),
        (date(2019, 3, 29), 1, 3, True),
        # Independence Day inside the first four sessions of July 2019: Jul 1, 2, 3, 5
        (date(2019, 7, 3), 1, 4, True),
        (date(2019, 7, 5), 1, 4, True),
        (date(2019, 7, 8), 1, 4, False),
        # Hurricane Sandy closed Oct 29–30 2012: the last two sessions of October are Oct 26 and 31
        (date(2012, 10, 25), 2, 3, False),
        (date(2012, 10, 26), 2, 3, True),
        (date(2012, 10, 31), 2, 3, True),
        # one side switched off
        (date(2019, 1, 31), 0, 3, False),
        (date(2019, 1, 2), 1, 0, False),
        (date(2019, 1, 31), 1, 0, True),
    ],
)
def test_turn_of_month_window(session, before, after, on):
    assert turn_of_month(session, before, after) is on


@pytest.mark.parametrize("day", [date(2018, 3, 30), date(2019, 1, 5), date(2019, 1, 1)])
def test_turn_of_month_rejects_a_non_session(day):
    with pytest.raises(ValueError):
        turn_of_month(day, 1, 3)


def test_calendar_trades_the_next_session():
    days = sessions(date(2018, 1, 2), date(2018, 4, 30))
    spy = hist("SPY", [100.0 + 0.25 * t for t in range(len(days))], days=days)
    p = CalendarParams("SPY", 1, 3)
    on = [d for d in sessions(date(2018, 3, 20), date(2018, 4, 10)) if run(CALENDAR, {"SPY": spy}, d, p)]
    # decided on d for S = next_session(d): Mar 28 -> Mar 29 (last of March), Mar 29 -> Apr 2 (over Good
    # Friday), Apr 2 -> Apr 3, Apr 3 -> Apr 4; Apr 4 -> Apr 5 is the 4th session of April
    assert on == [date(2018, 3, 28), date(2018, 3, 29), date(2018, 4, 2), date(2018, 4, 3)]
    d = date(2018, 3, 29)
    (t,) = run(CALENDAR, {"SPY": spy}, d, p)
    assert t == Target("SPY", Decimal("1"), Decimal(f"{float(spy.close[spy.index_of(d)]):.4f}"))


def test_calendar_out_of_window_exits_even_a_held_position():
    days = sessions(date(2018, 1, 2), date(2018, 4, 30))
    spy = hist("SPY", [100.0 + 0.25 * t for t in range(len(days))], days=days)
    assert run(CALENDAR, {"SPY": spy}, date(2018, 4, 4), CalendarParams("SPY"), frozenset({"SPY"})) == ()


def test_calendar_trend_gate():
    days = sessions(date(2018, 1, 2), date(2018, 4, 30))
    up = hist("SPY", [100.0 + 0.25 * t for t in range(len(days))], days=days)
    down = hist("SPY", [200.0 - 0.25 * t for t in range(len(days))], days=days)
    flat = hist("SPY", [150.0] * len(days), days=days)
    qqq = hist("QQQ", [50.0 + 0.1 * t for t in range(len(days))], days=days)
    d = date(2018, 3, 29)  # in the window (S = Apr 2)
    gated = CalendarParams("QQQ", 1, 3, ("SPY", 20))
    q_last = f"{float(qqq.close[qqq.index_of(d)]):.4f}"
    assert run(CALENDAR, {"SPY": up, "QQQ": qqq}, d, gated) == (full("QQQ", q_last),)
    assert run(CALENDAR, {"SPY": down, "QQQ": qqq}, d, gated) == ()
    assert run(CALENDAR, {"SPY": flat, "QQQ": qqq}, d, gated) == ()  # close == SMA: strict
    assert run(CALENDAR, {"SPY": down, "QQQ": qqq}, d, gated, frozenset({"QQQ"})) == ()
    # the trend instrument has no bar dated d: unknown -> keep only what is held
    gap = drop_days(up, [d])
    assert run(CALENDAR, {"SPY": gap, "QQQ": qqq}, d, gated) == ()
    assert run(CALENDAR, {"SPY": gap, "QQQ": qqq}, d, gated, frozenset({"QQQ"})) == (full("QQQ", q_last),)
    # too little trend history: off
    short = CalendarParams("QQQ", 1, 3, ("SPY", len(sessions(date(2018, 1, 2), d)) + 1))
    assert run(CALENDAR, {"SPY": up, "QQQ": qqq}, d, short) == ()


# ---- P4 identity and no look-ahead ---------------------------------------------------------------

CONTRACT_PARAMS = [
    (TIMING, T("SPY", "SPY", "sma", 50)),
    (TIMING, T("QQQ", "SPY", "sma", 20)),
    (TIMING, T("SPY", "SPY", "month_sma", 3)),
    (TIMING, T("QQQ", "QQQ", "abs_mom", 30)),
    (TIMING, T("SPY", "SPY", "always", 1)),
    (CALENDAR, CalendarParams("SPY", 1, 3, None)),
    (CALENDAR, CalendarParams("QQQ", 2, 2, ("SPY", 20))),
]
CONTRACT_IDS = ["sma50", "qqq-on-spy", "month-sma3", "abs-mom30", "always", "tom", "tom-trend"]


def contract_set() -> tuple[list[date], dict[str, History]]:
    """~14 months of waves (the signals flip), QQQ with a gap, BIL flat."""
    days = session_days(300, date(2018, 1, 2))
    spy = [100.0 + 12.0 * math.sin(t / 17.0) + 0.04 * t for t in range(300)]
    qqq = [60.0 + 9.0 * math.sin(t / 11.0 + 1.0) + 0.03 * t for t in range(300)]
    return days, {
        "SPY": hist("SPY", spy, days=days),
        "QQQ": drop_days(hist("QQQ", qqq, days=days), days[150:153] + [days[220]]),
        "BIL": hist("BIL", [91.5] * 300, days=days),
    }


@pytest.mark.parametrize("allocator, params", CONTRACT_PARAMS, ids=CONTRACT_IDS)
def test_p4_identity_and_no_look_ahead(allocator, params):
    """Prepared == single-window == full history; changing or deleting every bar dated >= S changes nothing."""
    days, history = contract_set()
    prepared = allocator.prepare(history)
    hold = allocator.holds(params)[0]
    on = off = 0
    for s in days[60:]:
        d = prev_session(s)
        changed = {k: mutate_from(h, s) for k, h in history.items()}
        cut = {k: truncate_before(h, s) for k, h in history.items()}
        for held in (NONE, frozenset({hold}), frozenset({"BIL"})):
            base = allocator.targets(history, NO_MEMBERS, d, held, params)
            assert allocator.targets({k: h.upto(d) for k, h in history.items()}, NO_MEMBERS, d, held, params) == base
            assert allocator.targets_prepared(prepared, NO_MEMBERS, d, held, params) == base, d
            assert allocator.targets(changed, NO_MEMBERS, d, held, params) == base, d
            assert allocator.targets(cut, NO_MEMBERS, d, held, params) == base, d
            assert allocator.targets_prepared(allocator.prepare(changed), NO_MEMBERS, d, held, params) == base, d
            assert len(base) <= 1 and sum(t.weight for t in base) <= 1
            for t in base:
                h = history[t.symbol]
                i = h.index_of(d)
                if i is not None:
                    assert t.last == Decimal(f"{float(h.close[i]):.4f}")
                else:
                    assert t.symbol in held  # a gap: only a held symbol is kept
        on += bool(allocator.targets(history, NO_MEMBERS, d, NONE, params))
        off += not allocator.targets(history, NO_MEMBERS, d, NONE, params)
    assert on > 0  # not vacuous
    if params != T("SPY", "SPY", "always", 1):
        assert off > 0  # the signal flips inside the window


def test_the_mutation_does_change_a_decision_read_at_s():
    # Guards test_p4_identity_and_no_look_ahead: the same mutation, read at data_date = S, matters.
    days, history = contract_set()
    p = T("SPY", "SPY", "sma", 50)
    differs = 0
    for s in days[60:]:
        changed = {k: mutate_from(h, s) for k, h in history.items()}
        differs += run(TIMING, changed, s, p) != run(TIMING, history, s, p)
    assert differs > 0


def test_allocatorkit_contract():
    """The shared phase-2 checkers agree (tests/allocatorkit.py; plan index D-E)."""
    from allocatorkit import assert_no_lookahead, assert_p4_identity

    days, history = contract_set()
    data_dates = [prev_session(s) for s in days[60:]]
    for allocator, params in CONTRACT_PARAMS:
        held_sets = [NONE, frozenset({allocator.holds(params)[0]})]
        assert assert_p4_identity(allocator, history, lambda d: NO_MEMBERS, data_dates, held_sets, [params]) > 0
        assert assert_no_lookahead(allocator, history, lambda d: NO_MEMBERS, days[60::10], held_sets, [params]) > 0
```

**The kit.** Only `test_allocatorkit_contract` touches `tests/allocatorkit.py`, with phase 2's
exact names and signatures. `check_lookback` stays on: every `lookback` in the table above covers
the bars its rule reads (a held `hold` without a bar on d is kept at its latest close, which
`allocatorkit.tail` keeps). Do not move the local R3 assertions into the kit.

**Impact:** 109 new test items. Nothing else changes.

**Verified before writing this plan:**
- Both files above ran green, 109 passed in 2.3 s, in the worktree venv.
- They ran against throwaway stubs of the phase-1/phase-2 contract pieces: `Target`,
  `to_weight`, `equal_weight`, `target_from_close`, `month_end_closes` (with the contract's
  "the month of d counts when d is its last session" rule), `return_window` and a no-op kit
  checker. The reconciler rewrote `test_allocatorkit_contract` to phase 2's real kit API (D-E);
  if it fails on the real kit, fix the call, never the kit or the allocator's contract.
- The real NYSE dates were checked with `seer_engine.dates`:
  - 2018-03-29 is the last session of March 2018;
  - April 2021 starts 1, 5, 6;
  - January 2019 starts 2, 3, 4;
  - February 2019 ends on the 28th;
  - July 2019 starts 1, 2, 3, 5;
  - October 2012 ends 26, 31;
  - the most sessions in any month from 1993 to 2026 is 23.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/trade-rules-dev-search && engine/.venv/bin/python -c "from seer_engine.strategies.f_index import TIMING, CALENDAR, TimingParams, CalendarParams; print(TIMING.id, CALENDAR.id)"` prints `F1 F11`.

**Tests:**
- `engine/.venv/bin/pytest engine/tests/test_f_index.py -q`: 109 passed.
- `engine/.venv/bin/pytest engine/tests/test_strategy_purity.py -q`: green, and the glob includes
  `seer_engine.strategies.f_index`.
- The full suite: `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
  is green with 0 skipped. The passed count is (the count after phases 1–2 and any other landed
  phase) + 109.

Use the worktree's own `engine/.venv`, never `/home/miftah/seer/engine/.venv`.

**Manual check:**
- `git diff --stat 2546a92 -- <frozen set>` prints nothing.
- `git status` shows only the two new files.

**Exit criteria:**
- `f_index.py` and `test_f_index.py` exist exactly as above.
- 109 new tests pass.
- The purity tests pass with the new module globbed.
- The full suite is green with 0 skipped.

## Handoffs

- **Phase 11 (R5):**
  - It imports `TIMING`, `CALENDAR`, `TimingParams` and `CalendarParams` from
    `seer_engine.strategies.f_index`.
  - The registry table's `T(h,s,rule,n)` is `TimingParams(hold=h, signal=s, rule=rule, n=n)`.
  - `CalendarParams(SPY,1,3,None)` is positional `(hold, days_before, days_after, trend)`.
  - `candidate_digest` will see `as_dict()` keys in the order given above.
- **Phase 9 (R4/R5):**
  - `candidate_window` uses `lookback`/`symbols`/`uses_members` from the table above. The
    `month_sma` lookback is `23 × n` (230 for the 10-month rule, so about 11 months of warm-up).
  - `candidate_owner_inputs` sees `holds = ("SSO",)` / `("QLD",)` for F10, which yields
    `"leverage"` plus `etf:SSO` / `etf:QLD`.
- **Phase 2 (R3):** the kit call uses phase 2's exact API (plan index D-E). Nothing is asked of
  phase 2.
- **Phases 6–8 (R3):**
  - `above_sma` here is the "close > SMA(n), strict, None without a bar on d" trend test that
    phases 6–8 also need. They keep their own (no cross-family import).
  - `as_dict` encoding is shared by every family (plan index D-F): `(symbol, n)` → `"SYM:n"`,
    `None` → `"none"`, a symbol tuple → comma-joined sorted symbols. Phases 6–8 already match.
- **Index Decisions table:** the reconciler added this phase's two cross-phase rows (the gap or
  unknown-signal hold passthrough, and the calendar treated as known in advance).
- **Not done (drive-by):** the registry rows' rationale text and any "sell in May" or
  pre-holiday variant of F11 (handover §4.B). Neither is in the 54-entry registry. Later D6
  appends would need a new params field. That would be a new phase's work, not this one.

## Rollback

Delete `engine/src/seer_engine/strategies/f_index.py` and `engine/tests/test_f_index.py` (or
`git revert` this phase's commit). Nothing else references them until phase 11 lands. If phase 11
has landed, revert it first.
