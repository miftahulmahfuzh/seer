> Adopted from `TRADE_RULES_DEV_SEARCH_PLAN.md` phase 6. Source: `.workflows/plan/trade-rules-dev-search/phase-6.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 6: Families F2/F3: ETF rotation

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R3 — no look-ahead and P4 identity for the F2 (dual momentum) and F3 (sector rotation) families; the prepared and single-window paths agree
**Depends on:** Phase 2 (and, through it, Phase 1)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

After this phase, `seer_engine.strategies.f_rotation` provides `RotationParams`, `RotationAllocator` and its
singleton `ROTATION` (allocator id `"ROT"`), exactly as the plan's shared contract says. One allocator
serves registry rows 23–32: F2 (dual momentum) and F3 (sector rotation by momentum). It ranks ETFs by
`return_window` momentum, keeps the top K at `equal_weight(top)`, and can apply an absolute-momentum
filter, a fallback ETF and a trend gate. Its `targets`, its `targets` on `upto(d)` histories and
`targets_prepared` return the same tuple on every date, and they read no bar dated after `data_date`.
`tests/test_f_rotation.py` proves this.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates** (all in `engine/src/seer_engine/strategies/f_rotation.py`, new, flat in `strategies/`, so the purity glob covers it):
- `RotationParams`, a frozen slots dataclass:
  - fields: `universe: tuple[str, ...]`, `lookback: int`, `top: int`, `absolute: bool = True`,
    `fallback: str | None = None`, `trend: tuple[str, int] | None = None`;
  - `__post_init__` validation;
  - `as_dict() -> dict[str, str]`.
- `RotationAllocator`, with the class attribute `id = "ROT"` and the full `Allocator` protocol:
  `lookback`, `symbols`, `holds`, `uses_members`, `targets`, `prepare` and `targets_prepared`.
- `ROTATION = RotationAllocator()`.
- `RotationPrepared`, a frozen dataclass with `eq=False` and one field,
  `history: Mapping[str, History]`.
- Module-level pure helpers, public so that tests and later readers can call them:
  - `rotation_targets(history, data_date, params) -> tuple[Target, ...]`;
  - `momentum_at(h, data_date, lookback) -> tuple[float, float] | None`;
  - `trend_on(h, data_date, n) -> bool`;
  - the constant `NONE_TEXT = "none"`.
- `engine/tests/test_f_rotation.py` (new): 39 tests (22 functions, one of them parametrized 18 ways).

**Signature changes:** none (no existing symbol is touched)

**Exact semantics (the reconciler and phases 9–11 rely on these):**

`lookback(p)`, `symbols(p)`, `holds(p)` and `uses_members(p)`:
- `lookback(p)` = `max(p.lookback + 1, p.trend[1] if p.trend else 1)`.
  - Momentum needs `lookback + 1` closes, and the trend SMA needs `n` closes.
  - Example: `F3-SEC-TOP3-6M-TREND` → 200; `F2-SPYQQQ-12M` → 253.
- `symbols(p)` = sorted(universe ∪ {fallback} ∪ {trend[0]}).
- `holds(p)` = sorted(universe ∪ {fallback}). It never contains the trend symbol unless that
  symbol is also in the universe.
- `uses_members(p)` is always `False`.

`targets` ignores `members` and `held`:
- Targets are a pure function of the ETFs' bars through `data_date`.
- A held ETF missing from the new selection is left out, so the engine signal-exits it (a
  rebalance).
- A held ETF with no bar on `d` is also left out ("excluded that date"). The engine marks it
  `exit_pending` or sells it at the open.

Eligibility of an ETF on `d`. All of these must hold:
- a bar dated `d`;
- at least `lookback + 1` bars through `d`;
- a finite momentum;
- `to_decimal(close_d) > 0`.

Momentum = `return_window(close[i-lookback : i+1].reshape(1, lookback+1), lookback)[0]`, computed
under `np.errstate(divide="ignore", invalid="ignore")`. A zero past close gives `inf`, so that ETF
is not eligible.

Ranking: `(-momentum, symbol)` ascending. Take the first `top`. With `absolute`, a selected ETF
whose momentum is not > 0 (strict) leaves its slot unused.

Fallback: `unused = top − len(selected)`. When `unused > 0`, the fallback has a bar dated `d` and
its close rounds to > 0, one fallback target is appended **last**, with weight
`equal_weight(top) × unused` (a Decimal multiple of `WEIGHT_QUANTUM`). Otherwise the unused weight
stays in cash.
- `top = 3` with every slot unused gives the fallback 0.999999, which leaves 0.000001 in cash.
  This is deliberate and keeps the weight on the quantum.

Trend gate `(sym, n)`: "on" needs all of these:
- `sym` has a bar dated `d`;
- at least `n` bars through `d`;
- `close_d > sma_window(last n closes, n)` (strict).

Anything else is "off": a missing history, no bar on `d`, too few bars or an equal close. Off
means every slot is unused, so all the weight goes to the fallback or to cash.

The trend symbol may be in the universe.

Every `Target` has `last = q(to_decimal(close on d))` and `limit`, `stop` and `take` all `None`. It
is built through `allocator.target_from_close(symbol, close, weight)`.

`as_dict()` keys, in this order: `universe`, `lookback`, `top`, `absolute`, `fallback`, `trend`.

| Key | Text |
|---|---|
| `universe` | `",".join(universe)` |
| `lookback` | `str(int)` |
| `top` | `str(int)` |
| `absolute` | `"true"` or `"false"` |
| `fallback` | the symbol, or `"none"` |
| `trend` | `f"{sym}:{n}"`, or `"none"` |

Example: `RotationParams(("QQQ","SPY"),252,1).as_dict()` ==
`{"universe":"QQQ,SPY","lookback":"252","top":"1","absolute":"true","fallback":"none","trend":"none"}`.

`RotationParams` validation:

| Condition | Error |
|---|---|
| `universe` is not a tuple | TypeError |
| a universe element is not a str | TypeError |
| a universe element is empty or has surrounding spaces | ValueError |
| `universe` has fewer than 2 ETFs, or is not sorted and unique | ValueError |
| `lookback` or `top` is not an int, or is a bool | TypeError |
| `lookback` < 1 or `top` < 1 | ValueError |
| `top > len(universe)` | ValueError |
| `absolute` is not a bool | TypeError |
| `fallback` is not a str | TypeError |
| `fallback` is empty | ValueError |
| `fallback` is in `universe` | ValueError |
| `trend` is not a 2-tuple | TypeError |
| `trend[0]` is not a str, or `trend[1]` is not an int | TypeError |
| `trend[1]` < 1 | ValueError |

Wrong types elsewhere:
- Every allocator method raises `TypeError` for params that are not a `RotationParams`.
- `targets_prepared` raises `TypeError` for a `prepared` that is not a `RotationPrepared`.
- A `data_date` that is not a `date` raises `TypeError` (through `base.as_day`).

**Requires (from earlier phases):**
- Phase 1, `seer_engine.sim`, which exports:
  - `Target(symbol, weight, last, limit=None, stop=None, take=None)`: a frozen dataclass with
    value equality, whose weight must be a multiple of `WEIGHT_QUANTUM`, > 0 and ≤ 1;
  - `equal_weight(n) -> Decimal`, with `equal_weight(3) == Decimal("0.333333")`;
  - `q` (exists today).
- Phase 2:
  - `seer_engine.strategies.allocator.Allocator` (a `runtime_checkable` Protocol);
  - `seer_engine.strategies.allocator.target_from_close(symbol: str, close: float, weight: Decimal, *, limit=None, stop=None, take=None) -> Target | None`;
  - `seer_engine.strategies.indicators.return_window(close: np.ndarray (rows, W), n: int, skip: int = 0) -> np.ndarray`,
    which is `c[:, -1-skip] / c[:, -1-n] − 1`, with NaN rows when `W < n + 1`.
- Phase 2: `engine/tests/allocatorkit.py` (plan index D-E, phase 2's kit is canonical):
  `assert_p4_identity(allocator, history, members_fn, dates, held_sets, params, *,
  max_weight_sum=Decimal(1), check_lookback=True) -> int` and
  `assert_no_lookahead(allocator, history, members_fn, sessions, held_sets, params) -> int`
  (`held_sets` and `params` are non-empty lists).
  - The kit is called in **one** test only (`test_allocatorkit_contract`, the last function of the
    test file).
  - The file's own `test_p4_identity_and_no_look_ahead` proves P4 identity and no look-ahead
    directly, with stratkit's `mutate_from`/`truncate_before`, so R3 does not depend on the kit
    alone.

**Leaves alone (owned by others):**
- `sim/rules.py` and `sim/book.py` (Phase 1);
- `strategies/allocator.py`, `strategies/indicators.py` and `tests/allocatorkit.py` (Phase 2);
- `backtest/book_runner.py` (Phase 3);
- `seer_engine/research.py`, including `SECTOR_ETFS` (Phase 4). `f_rotation.py` never imports
  `research` (it is impure). The registry passes the sector tuple as `universe`;
- `strategies/f_index.py` (Phase 5), `f_factor.py` (Phase 7) and `f_swing.py` (Phase 8);
- `backtest/dev.py`, `dev_report.py` and `registry.py` (Phases 9–11);
- `strategies/__init__.py`. It is not edited; `f_rotation` is imported by its module path.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/f_rotation.py` | create (line 1) | the whole module below |
| `engine/tests/test_f_rotation.py` | create (line 1) | the whole test file below |

No other file is touched. `tests/test_strategy_purity.py` already globs `strategies/*.py`, so it covers
the new module without an edit.

## Implementation Steps

### Step 1: Create the rotation module
**File:** `engine/src/seer_engine/strategies/f_rotation.py:1` (new file)
**Change:** add the module, exactly as below.
**Code:**
```python
"""Families F2 and F3: ETF rotation by momentum (handover §4.B; plan phase 6).

F2 (dual momentum, GEM-style) and F3 (sector rotation) are one allocator with different
``RotationParams``. ``Candidate.family`` carries the F2/F3 label; the allocator id is ``ROT``.

On ``data_date``'s close:

1. **Trend gate** (``trend = (symbol, n)``): unless that symbol has a bar dated ``data_date``,
   at least ``n`` bars through it, and its close is > SMA(n) of its daily closes (strict),
   every slot is unused (steps 2–3 are skipped).
2. **Ranking**: every ETF of ``universe`` that is *eligible* is ranked by its momentum
   ``c[-1] / c[-1-lookback] − 1`` (``indicators.return_window``, skip 0), highest first, ties
   by symbol ascending. Eligible: a bar dated ``data_date``, at least ``lookback + 1`` bars
   through it, a finite momentum, and a close that rounds (``prices.to_decimal``) to > 0. An
   ETF that is missing from the history, has no bar that day or is too short is left out for
   that date only; it never takes a slot.
3. **Selection**: the first ``top`` ranked ETFs, each at ``equal_weight(top)``. With
   ``absolute``, an ETF whose momentum is not > 0 (strict) leaves its slot unused.
4. **Fallback**: the unused slots (``top`` − selected) go to ``fallback`` as one target of
   weight ``equal_weight(top) × unused``, ranked last, when ``fallback`` has a bar dated
   ``data_date`` with a positive close; otherwise they stay in cash.

``held`` and ``members`` are ignored: the targets are a pure function of the ETFs' bars, so a
held ETF that is not in the new selection is signal-exited by the engine at the next open
(a rebalance), and no index member is read.

Every value is a function of the bars dated on or before ``data_date`` only: windows are
sliced at ``History.index_of(data_date)``. So ``targets`` on full histories, ``targets`` on
``upto(data_date)`` histories and ``targets_prepared`` return the same tuple (P4 identity).
Pure: no database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any

import numpy as np

from seer_engine.prices import to_decimal
from seer_engine.sim import Target, equal_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import return_window, sma_window

NONE_TEXT = "none"  # as_dict() text of an unset optional field


def _symbol(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str, got {type(value).__name__}")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty symbol without spaces, got {value!r}")
    return value


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < 1:
        raise ValueError(f"{name} must be >= 1, got {value}")
    return value


@dataclass(frozen=True, slots=True)
class RotationParams:
    """One F2/F3 rotation, fixed per candidate (see the module docstring for the rule)."""

    universe: tuple[str, ...]  # the ranked ETFs: sorted, unique, >= 2
    lookback: int  # momentum = c[-1] / c[-1-lookback] − 1 (return_window, skip 0); >= 1
    top: int  # keep the top K by momentum, each at equal_weight(top); 1 <= top <= len(universe)
    absolute: bool = True  # a slot is used only when that ETF's momentum > 0 (strict)
    fallback: str | None = None  # unused slots go here (when it has a bar on data_date), else cash
    trend: tuple[str, int] | None = None  # every slot unused unless trend[0] close > SMA(trend[1])

    def __post_init__(self) -> None:
        if not isinstance(self.universe, tuple):
            raise TypeError(f"universe must be a tuple, got {type(self.universe).__name__}")
        for s in self.universe:
            _symbol("universe symbol", s)
        if len(self.universe) < 2:
            raise ValueError(f"universe needs >= 2 ETFs, got {len(self.universe)}")
        if list(self.universe) != sorted(set(self.universe)):
            raise ValueError(f"universe must be sorted and unique, got {self.universe!r}")
        _positive_int("lookback", self.lookback)
        _positive_int("top", self.top)
        if self.top > len(self.universe):
            raise ValueError(f"top must be <= len(universe) = {len(self.universe)}, got {self.top}")
        if not isinstance(self.absolute, bool):
            raise TypeError(f"absolute must be a bool, got {type(self.absolute).__name__}")
        if self.fallback is not None:
            _symbol("fallback", self.fallback)
            if self.fallback in self.universe:
                raise ValueError(f"fallback {self.fallback} must not be in the universe")
        if self.trend is not None:
            if not isinstance(self.trend, tuple) or len(self.trend) != 2:
                raise TypeError(f"trend must be a (symbol, n) tuple or None, got {self.trend!r}")
            _symbol("trend symbol", self.trend[0])
            _positive_int("trend n", self.trend[1])

    def as_dict(self) -> dict[str, str]:
        """Every parameter as text, in a fixed key order (dev report and pre-registration)."""
        return {
            "universe": ",".join(self.universe),
            "lookback": str(self.lookback),
            "top": str(self.top),
            "absolute": "true" if self.absolute else "false",
            "fallback": self.fallback if self.fallback is not None else NONE_TEXT,
            "trend": f"{self.trend[0]}:{self.trend[1]}" if self.trend is not None else NONE_TEXT,
        }


def _params(params: object) -> RotationParams:
    if not isinstance(params, RotationParams):
        raise TypeError(f"params must be RotationParams, got {type(params).__name__}")
    return params


def _close_on(h: History | None, data_date: date) -> tuple[int, float] | None:
    """(row, close) of ``h``'s bar dated ``data_date`` when its close rounds to > 0, else None."""
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None:
        return None
    close = float(h.close[i])
    if not np.isfinite(close) or to_decimal(close) <= 0:
        return None
    return i, close


def momentum_at(h: History | None, data_date: date, lookback: int) -> tuple[float, float] | None:
    """(momentum, close) of ``h`` on ``data_date``, or None when it is not eligible that day.

    Momentum = return_window over the ``lookback + 1`` closes ending at ``data_date``.
    """
    found = _close_on(h, data_date)
    if found is None:
        return None
    i, close = found
    if i < lookback:  # fewer than lookback + 1 bars through data_date
        return None
    assert h is not None
    window = h.close[i - lookback : i + 1].reshape(1, lookback + 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        m = float(return_window(window, lookback)[0])
    if not np.isfinite(m):
        return None
    return m, close


def trend_on(h: History | None, data_date: date, n: int) -> bool:
    """``h``'s close on ``data_date`` > SMA(n) of its daily closes (strict); False without the bars."""
    found = _close_on(h, data_date)
    if found is None:
        return False
    i, close = found
    if i + 1 < n:
        return False
    assert h is not None
    window = h.close[i + 1 - n : i + 1].reshape(1, n)
    sma = float(sma_window(window, n)[0])
    return bool(np.isfinite(sma) and close > sma)


def rotation_targets(history: Mapping[str, History], data_date: date, params: RotationParams) -> tuple[Target, ...]:
    """The rotation's targets for the session after ``data_date``, in rank order (fallback last)."""
    as_day(data_date)
    weight = equal_weight(params.top)
    chosen: list[Target] = []
    gate = params.trend is None or trend_on(history.get(params.trend[0]), data_date, params.trend[1])
    if gate:
        ranked: list[tuple[float, str, float]] = []
        for symbol in params.universe:
            found = momentum_at(history.get(symbol), data_date, params.lookback)
            if found is not None:
                ranked.append((found[0], symbol, found[1]))
        ranked.sort(key=lambda r: (-r[0], r[1]))
        for m, symbol, close in ranked[: params.top]:
            if params.absolute and not m > 0.0:
                continue
            target = target_from_close(symbol, close, weight)
            if target is not None:
                chosen.append(target)
    unused = params.top - len(chosen)
    if unused > 0 and params.fallback is not None:
        found_fb = _close_on(history.get(params.fallback), data_date)
        if found_fb is not None:
            target = target_from_close(params.fallback, found_fb[1], weight * unused)
            if target is not None:
                chosen.append(target)
    return tuple(chosen)


@dataclass(frozen=True, slots=True, eq=False)
class RotationPrepared:
    """``prepare``'s output: the histories as given (read-only view). The rotation's features
    depend on ``lookback``, a parameter, so nothing is precomputed; ``targets_prepared`` slices
    at ``data_date`` exactly as ``targets`` does."""

    history: Mapping[str, History]


class RotationAllocator:
    """F2/F3 behind the ``Allocator`` protocol (strategies/allocator.py)."""

    id = "ROT"

    def lookback(self, params: Any) -> int:
        p = _params(params)
        return max(p.lookback + 1, p.trend[1] if p.trend is not None else 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _params(params)
        read = set(p.universe)
        if p.fallback is not None:
            read.add(p.fallback)
        if p.trend is not None:
            read.add(p.trend[0])
        return tuple(sorted(read))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _params(params)
        held = set(p.universe)
        if p.fallback is not None:
            held.add(p.fallback)
        return tuple(sorted(held))

    def uses_members(self, params: Any) -> bool:
        _params(params)
        return False

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return rotation_targets(history, data_date, _params(params))

    def prepare(self, history: Mapping[str, History]) -> RotationPrepared:
        return RotationPrepared(MappingProxyType(dict(history)))

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, RotationPrepared):
            raise TypeError(f"prepared must be RotationPrepared, got {type(prepared).__name__}")
        return rotation_targets(prepared.history, data_date, _params(params))


ROTATION = RotationAllocator()
```
**Impact:** none on existing code. It is a new, pure module. The only imports are `numpy`, `types`, `seer_engine.prices`,
`seer_engine.sim`, `seer_engine.strategies.{allocator, base, indicators}` (no psycopg/requests/yfinance/time/
random/logging; no `.now`/`.today`/`.random`; no `print`/`open`). The two `assert h is not None` lines are type
narrowing only (`_close_on` already returned None for a missing history).

### Step 2: Create the test file
**File:** `engine/tests/test_f_rotation.py:1` (new file)
**Change:** add the tests, exactly as below.
- The tests use the existing `tests/stratkit.py` (`hist`, `session_days`, `drop_days`,
  `mutate_from`, `truncate_before`) and phase 2's `tests/allocatorkit.py`.
- Every hand-checked case uses lookback 2 on 12 sessions of flat 100 closes followed by one final
  close. So momentum is `last / 100 − 1`, and the expected `Target`s are written out literally.
**Code:**
```python
"""Families F2/F3: ETF rotation (plan phase 6; handover §4.B F2/F3, §7 R3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import allocatorkit
import numpy as np
import pytest
from stratkit import drop_days, hist, mutate_from, session_days, truncate_before

from seer_engine.dates import prev_session
from seer_engine.prices import to_decimal
from seer_engine.sim import Target, equal_weight, q
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import History
from seer_engine.strategies.f_rotation import (
    ROTATION,
    RotationAllocator,
    RotationParams,
    RotationPrepared,
)

DAYS = session_days(12)
D = DAYS[-1]  # the data_date of every hand-checked case
NOTHING: frozenset[str] = frozenset()


def flat_then(last: float, base: float = 100.0, n: int = 12) -> list[float]:
    """``n`` closes: ``base`` repeated, then ``last`` on the final session (D)."""
    return [base] * (n - 1) + [last]


def tgt(symbol: str, weight: str, close: float) -> Target:
    return Target(symbol, Decimal(weight), q(to_decimal(close)))


def run(history: dict[str, History], params: RotationParams, held: frozenset[str] = NOTHING) -> tuple[Target, ...]:
    """ROTATION.targets on D, after checking targets_prepared agrees."""
    got = ROTATION.targets(history, NOTHING, D, held, params)
    assert ROTATION.targets_prepared(ROTATION.prepare(history), NOTHING, D, held, params) == got
    return got


def P(universe: tuple[str, ...] = ("AAA", "BBB", "CCC"), lookback: int = 2, top: int = 1, **kw: object) -> RotationParams:
    return RotationParams(universe, lookback, top, **kw)  # type: ignore[arg-type]


IEF = hist("IEF", [80.0] * 12)


# ---- params -------------------------------------------------------------------------------


def test_params_defaults_and_as_dict():
    p = RotationParams(("QQQ", "SPY"), 252, 1)
    assert (p.absolute, p.fallback, p.trend) == (True, None, None)
    assert p.as_dict() == {
        "universe": "QQQ,SPY",
        "lookback": "252",
        "top": "1",
        "absolute": "true",
        "fallback": "none",
        "trend": "none",
    }
    full = RotationParams(("XLB", "XLE", "XLK"), 126, 3, False, "IEF", ("SPY", 200))
    assert full.as_dict() == {
        "universe": "XLB,XLE,XLK",
        "lookback": "126",
        "top": "3",
        "absolute": "false",
        "fallback": "IEF",
        "trend": "SPY:200",
    }
    assert list(full.as_dict()) == ["universe", "lookback", "top", "absolute", "fallback", "trend"]


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"universe": ["QQQ", "SPY"]}, TypeError),
        ({"universe": ("SPY", "QQQ")}, ValueError),  # not sorted
        ({"universe": ("QQQ", "QQQ")}, ValueError),  # not unique
        ({"universe": ("SPY",), "top": 1}, ValueError),  # < 2 ETFs
        ({"universe": ("QQQ", "")}, ValueError),
        ({"universe": ("QQQ", 1)}, TypeError),
        ({"lookback": 0}, ValueError),
        ({"lookback": True}, TypeError),
        ({"lookback": 2.0}, TypeError),
        ({"top": 0}, ValueError),
        ({"top": 3}, ValueError),  # > len(universe)
        ({"absolute": 1}, TypeError),
        ({"fallback": "SPY"}, ValueError),  # inside the universe
        ({"fallback": ""}, ValueError),
        ({"trend": ("SPY",)}, TypeError),
        ({"trend": ["SPY", 200]}, TypeError),
        ({"trend": ("SPY", 0)}, ValueError),
        ({"trend": (200, "SPY")}, TypeError),
    ],
)
def test_params_validation(kwargs, error):
    base = {"universe": ("QQQ", "SPY"), "lookback": 252, "top": 1}
    with pytest.raises(error):
        RotationParams(**{**base, **kwargs})


def test_params_are_frozen():
    p = RotationParams(("QQQ", "SPY"), 252, 1)
    with pytest.raises(AttributeError):
        p.top = 2  # type: ignore[misc]


# ---- the allocator's shape -----------------------------------------------------------------


def test_allocator_shape():
    assert isinstance(ROTATION, RotationAllocator)
    assert isinstance(ROTATION, Allocator)
    assert ROTATION.id == "ROT"
    plain = RotationParams(("QQQ", "SPY"), 252, 1)
    assert ROTATION.lookback(plain) == 253
    assert ROTATION.symbols(plain) == ("QQQ", "SPY")
    assert ROTATION.holds(plain) == ("QQQ", "SPY")
    assert ROTATION.uses_members(plain) is False
    full = RotationParams(("XLB", "XLE"), 126, 1, True, "IEF", ("SPY", 200))
    assert ROTATION.lookback(full) == 200  # the trend SMA needs more bars than the momentum
    assert ROTATION.symbols(full) == ("IEF", "SPY", "XLB", "XLE")
    assert ROTATION.holds(full) == ("IEF", "XLB", "XLE")  # reads SPY, never holds it
    short_trend = RotationParams(("XLB", "XLE"), 126, 1, True, None, ("XLE", 50))
    assert ROTATION.lookback(short_trend) == 127
    assert ROTATION.symbols(short_trend) == ("XLB", "XLE")


def test_wrong_types_raise():
    h = {"AAA": hist("AAA", flat_then(110.0))}
    for call in (
        lambda: ROTATION.lookback(object()),
        lambda: ROTATION.symbols(None),
        lambda: ROTATION.holds("x"),
        lambda: ROTATION.uses_members(1),
        lambda: ROTATION.targets(h, NOTHING, D, NOTHING, object()),
        lambda: ROTATION.targets_prepared(h, NOTHING, D, NOTHING, P()),
    ):
        with pytest.raises(TypeError):
            call()
    prepared = ROTATION.prepare(h)
    assert isinstance(prepared, RotationPrepared)
    with pytest.raises(TypeError):
        ROTATION.targets(h, NOTHING, D.isoformat(), NOTHING, P())  # type: ignore[arg-type]


# ---- ranking, top K, weights ---------------------------------------------------------------


def three(a: float, b: float, c: float) -> dict[str, History]:
    return {
        "AAA": hist("AAA", flat_then(a)),
        "BBB": hist("BBB", flat_then(b)),
        "CCC": hist("CCC", flat_then(c)),
    }


def test_ranks_by_momentum_highest_first():
    h = three(110.0, 120.0, 105.0)  # momentum 0.10, 0.20, 0.05
    assert run(h, P(top=1)) == (tgt("BBB", "1", 120.0),)
    assert run(h, P(top=2)) == (tgt("BBB", "0.5", 120.0), tgt("AAA", "0.5", 110.0))
    assert run(h, P(top=3)) == (
        tgt("BBB", "0.333333", 120.0),
        tgt("AAA", "0.333333", 110.0),
        tgt("CCC", "0.333333", 105.0),
    )
    assert equal_weight(3) == Decimal("0.333333")


def test_ties_are_broken_by_symbol():
    h = three(110.0, 110.0, 110.0)
    assert run(h, P(top=1)) == (tgt("AAA", "1", 110.0),)
    assert run(h, P(top=2)) == (tgt("AAA", "0.5", 110.0), tgt("BBB", "0.5", 110.0))
    h2 = three(105.0, 110.0, 110.0)
    assert run(h2, P(top=1)) == (tgt("BBB", "1", 110.0),)


def test_momentum_uses_exactly_lookback_sessions():
    # AAA: 50 six sessions back, 80 now -> +60% over 5 sessions, 0% over 2.
    # BBB: +10% over both.
    h = {
        "AAA": hist("AAA", [100.0] * 6 + [50.0] + [80.0] * 5),
        "BBB": hist("BBB", flat_then(110.0)),
    }
    assert run(h, P(("AAA", "BBB"), lookback=5)) == (tgt("AAA", "1", 80.0),)
    assert run(h, P(("AAA", "BBB"), lookback=2)) == (tgt("BBB", "1", 110.0),)
    # lookback 6 reaches the 100 before the dip: AAA -20%, BBB +10%.
    assert run(h, P(("AAA", "BBB"), lookback=6)) == (tgt("BBB", "1", 110.0),)


# ---- the absolute filter -------------------------------------------------------------------


def test_absolute_filter_leaves_non_positive_slots_unused():
    h = three(110.0, 95.0, 100.0)  # +0.10, -0.05, 0.00 (zero is not > 0)
    assert run(h, P(top=3)) == (tgt("AAA", "0.333333", 110.0),)
    assert run(h, P(top=3, absolute=False)) == (
        tgt("AAA", "0.333333", 110.0),
        tgt("CCC", "0.333333", 100.0),
        tgt("BBB", "0.333333", 95.0),
    )
    all_down = three(90.0, 95.0, 99.0)
    assert run(all_down, P(top=2)) == ()
    assert run(all_down, P(top=1, absolute=False)) == (tgt("CCC", "1", 99.0),)


# ---- the fallback --------------------------------------------------------------------------


def test_fallback_takes_the_unused_slots():
    h = {**three(110.0, 95.0, 90.0), "IEF": IEF}
    assert run(h, P(top=1, fallback="IEF")) == (tgt("AAA", "1", 110.0),)
    assert run(h, P(top=3, fallback="IEF")) == (tgt("AAA", "0.333333", 110.0), tgt("IEF", "0.666666", 80.0))
    assert run(h, P(top=2, fallback="IEF")) == (tgt("AAA", "0.5", 110.0), tgt("IEF", "0.5", 80.0))
    down = {**three(90.0, 95.0, 99.0), "IEF": IEF}
    assert run(down, P(top=1, fallback="IEF")) == (tgt("IEF", "1", 80.0),)
    assert run(down, P(top=3, fallback="IEF")) == (tgt("IEF", "0.999999", 80.0),)
    # every slot used: no fallback target
    assert run(down, P(top=2, absolute=False, fallback="IEF")) == (
        tgt("CCC", "0.5", 99.0),
        tgt("BBB", "0.5", 95.0),
    )


def test_fallback_without_a_bar_on_the_data_date_means_cash():
    base = three(110.0, 95.0, 90.0)
    gap = {**base, "IEF": drop_days(IEF, [D])}
    assert run(gap, P(top=3, fallback="IEF")) == (tgt("AAA", "0.333333", 110.0),)
    assert run(base, P(top=3, fallback="IEF")) == (tgt("AAA", "0.333333", 110.0),)  # not in the history at all
    zero = {**base, "IEF": hist("IEF", [80.0] * 11 + [0.00001])}  # rounds to 0.0000
    assert run(zero, P(top=3, fallback="IEF")) == (tgt("AAA", "0.333333", 110.0),)


# ---- the trend gate ------------------------------------------------------------------------


def test_trend_gate_on_and_off():
    rising = hist("SPY", [100.0 + t for t in range(12)])  # close 111 > SMA3 110
    falling = hist("SPY", [111.0 - t for t in range(12)])  # close 100 < SMA3 101
    flat = hist("SPY", [100.0] * 12)  # close == SMA3: not on (strict)
    base = {**three(110.0, 120.0, 105.0), "IEF": IEF}
    p = P(top=2, fallback="IEF", trend=("SPY", 3))
    assert run({**base, "SPY": rising}, p) == (tgt("BBB", "0.5", 120.0), tgt("AAA", "0.5", 110.0))
    assert run({**base, "SPY": falling}, p) == (tgt("IEF", "1", 80.0),)
    assert run({**base, "SPY": flat}, p) == (tgt("IEF", "1", 80.0),)
    no_fallback = P(top=2, trend=("SPY", 3))
    assert run({**base, "SPY": falling}, no_fallback) == ()


def test_trend_gate_is_off_without_the_signal_bars():
    base = {**three(110.0, 120.0, 105.0), "IEF": IEF}
    p = P(top=1, fallback="IEF", trend=("SPY", 3))
    rising = hist("SPY", [100.0 + t for t in range(12)])
    assert run({**base, "SPY": rising}, p) == (tgt("BBB", "1", 120.0),)
    assert run(base, p) == (tgt("IEF", "1", 80.0),)  # no SPY history
    assert run({**base, "SPY": drop_days(rising, [D])}, p) == (tgt("IEF", "1", 80.0),)  # no bar on D
    short = hist("SPY", [110.0, 111.0], days=DAYS[-2:])  # 2 bars < 3
    assert run({**base, "SPY": short}, p) == (tgt("IEF", "1", 80.0),)
    exactly = hist("SPY", [109.0, 110.0, 111.0], days=DAYS[-3:])  # 3 bars: SMA3 = 110 < 111
    assert run({**base, "SPY": exactly}, p) == (tgt("BBB", "1", 120.0),)


def test_trend_symbol_may_be_in_the_universe():
    h = three(110.0, 120.0, 105.0)
    p = P(top=1, trend=("AAA", 12))  # AAA: 100 × 11 then 110 > SMA12
    assert run(h, p) == (tgt("BBB", "1", 120.0),)
    assert ROTATION.symbols(p) == ("AAA", "BBB", "CCC")


# ---- missing and short ETFs ----------------------------------------------------------------


def test_missing_or_short_etfs_are_excluded_that_date():
    h = {
        "AAA": hist("AAA", [100.0, 300.0], days=DAYS[-2:]),  # 2 bars < lookback + 1 = 3
        "BBB": drop_days(hist("BBB", flat_then(200.0)), [D]),  # best, but no bar on D
        "CCC": hist("CCC", flat_then(105.0)),
        # DDD: not in the history at all
        "IEF": IEF,
    }
    p = P(("AAA", "BBB", "CCC", "DDD"), top=2, fallback="IEF")
    assert run(h, p) == (tgt("CCC", "0.5", 105.0), tgt("IEF", "0.5", 80.0))
    # exactly lookback + 1 bars is enough
    h["AAA"] = hist("AAA", [100.0, 100.0, 130.0], days=DAYS[-3:])
    assert run(h, p) == (tgt("AAA", "0.5", 130.0), tgt("CCC", "0.5", 105.0))


def test_a_close_that_rounds_to_zero_is_not_eligible():
    h = {"AAA": hist("AAA", flat_then(0.00001)), "BBB": hist("BBB", flat_then(90.0))}
    assert run(h, P(("AAA", "BBB"), top=2, absolute=False)) == (tgt("BBB", "0.5", 90.0),)


def test_a_zero_past_close_is_not_eligible():
    h = {"AAA": hist("AAA", [100.0] * 9 + [0.0, 100.0, 110.0]), "BBB": hist("BBB", flat_then(90.0))}
    assert run(h, P(("AAA", "BBB"), top=1, absolute=False)) == (tgt("BBB", "1", 90.0),)


# ---- held and members ----------------------------------------------------------------------


def test_held_is_passed_through_untouched_and_never_kept():
    h = {**three(110.0, 120.0, 95.0), "IEF": IEF}
    p = P(top=1, fallback="IEF")
    want = (tgt("BBB", "1", 120.0),)
    assert run(h, p) == want
    # AAA held and no longer the top: it is dropped (the engine signal-exits it at the open)
    assert run(h, p, held=frozenset({"AAA"})) == want
    assert run(h, p, held=frozenset({"BBB"})) == want  # held and still the top: same weight
    assert run(h, p, held=frozenset({"CCC", "IEF", "ZZZ"})) == want
    # a held ETF with a bar on D but negative momentum is dropped under the absolute filter
    assert run(h, P(top=3, fallback="IEF"), held=frozenset({"CCC"})) == (
        tgt("BBB", "0.333333", 120.0),
        tgt("AAA", "0.333333", 110.0),
        tgt("IEF", "0.333333", 80.0),
    )
    # a held ETF with no bar on D is excluded too (no momentum that date)
    gap = {**h, "BBB": drop_days(h["BBB"], [D])}
    assert run(gap, p, held=frozenset({"BBB"})) == (tgt("AAA", "1", 110.0),)


def test_members_are_ignored():
    h = three(110.0, 120.0, 105.0)
    p = P(top=2)
    want = ROTATION.targets(h, NOTHING, D, NOTHING, p)
    assert ROTATION.targets(h, frozenset({"AAA"}), D, NOTHING, p) == want
    assert ROTATION.targets(h, frozenset({"MSFT", "AAPL"}), D, NOTHING, p) == want


# ---- P4 identity and no look-ahead ---------------------------------------------------------

N = 200
CONTRACT_DAYS = session_days(N)


def walk(seed: int, n: int = N, drift: float = 0.0004, vol: float = 0.012) -> list[float]:
    rng = np.random.default_rng(seed)
    return [float(x) for x in np.round(100.0 * np.cumprod(1.0 + rng.normal(drift, vol, n)), 4)]


def contract_set() -> dict[str, History]:
    days = CONTRACT_DAYS
    return {
        "AAA": hist("AAA", walk(1)),
        "BBB": drop_days(hist("BBB", walk(2, drift=0.001)), [days[50], days[51], days[120]]),
        "CCC": hist("CCC", walk(3, drift=-0.0005)),
        "DDD": hist("DDD", walk(4, n=N - 80, drift=0.002), days=days[80:]),  # launches late
        "IEF": drop_days(hist("IEF", walk(5, vol=0.003)), [days[100], days[150]]),
        "SPY": hist("SPY", walk(6, drift=0.0006)),
    }


CONTRACT_PARAMS = (
    RotationParams(("AAA", "BBB", "CCC", "DDD"), 20, 1),
    RotationParams(("AAA", "BBB", "CCC", "DDD"), 20, 2, False, "IEF"),
    RotationParams(("AAA", "BBB", "CCC", "DDD"), 63, 3, True, "IEF", ("SPY", 50)),
    RotationParams(("AAA", "BBB"), 5, 2, True, "IEF", ("SPY", 10)),
)
HELDS = (NOTHING, frozenset({"AAA", "IEF"}), frozenset({"DDD", "ZZZ"}))


def check_targets(history: dict[str, History], d: date, params: RotationParams, got: tuple[Target, ...]) -> None:
    symbols = [t.symbol for t in got]
    assert len(set(symbols)) == len(symbols)
    assert set(symbols) <= set(ROTATION.holds(params))
    assert sum((t.weight for t in got), Decimal(0)) <= 1
    for t in got:
        i = history[t.symbol].index_of(d)
        assert i is not None  # never a target without a bar on d
        assert t.last == q(to_decimal(float(history[t.symbol].close[i])))
        assert (t.limit, t.stop, t.take) == (None, None, None)


def test_p4_identity_and_no_look_ahead():
    history = contract_set()
    prepared = ROTATION.prepare(history)
    sizes: set[int] = set()
    fallback_seen = 0
    for s in CONTRACT_DAYS[1:]:
        d = prev_session(s)
        upto = {k: h.upto(d) for k, h in history.items()}
        changed = {k: mutate_from(h, s) for k, h in history.items()}
        cut = {k: truncate_before(h, s) for k, h in history.items()}
        for params in CONTRACT_PARAMS:
            for held in HELDS:
                want = ROTATION.targets(upto, NOTHING, d, held, params)
                assert ROTATION.targets_prepared(prepared, NOTHING, d, held, params) == want, (s, params)
                assert ROTATION.targets(history, NOTHING, d, held, params) == want, (s, params)
                assert ROTATION.targets(changed, NOTHING, d, held, params) == want, (s, params)
                assert ROTATION.targets(cut, NOTHING, d, held, params) == want, (s, params)
                assert ROTATION.targets_prepared(ROTATION.prepare(changed), NOTHING, d, held, params) == want
                check_targets(history, d, params, want)
                sizes.add(len(want))
                fallback_seen += any(t.symbol == "IEF" for t in want)
    assert sizes >= {0, 1, 2, 3}  # not vacuous: empty, single, pair and triple target sets all occur
    assert fallback_seen > 0


def test_the_mutation_does_change_later_targets():
    # Guards test_p4_identity_and_no_look_ahead: read at data_date = s, the mutation is visible.
    history = contract_set()
    p = CONTRACT_PARAMS[1]
    changed_any = False
    for s in CONTRACT_DAYS[100:]:
        changed = {k: mutate_from(h, s, lambda x: x[::-1].copy()) for k, h in history.items()}
        if ROTATION.targets(changed, NOTHING, s, NOTHING, p) != ROTATION.targets(history, NOTHING, s, NOTHING, p):
            changed_any = True
            break
    assert changed_any


def test_allocatorkit_contract():
    history = contract_set()
    members = lambda d: NOTHING  # noqa: E731
    dates = [prev_session(s) for s in CONTRACT_DAYS[1::7]]
    assert allocatorkit.assert_p4_identity(ROTATION, history, members, dates, list(HELDS), list(CONTRACT_PARAMS)) > 0
    sessions = list(CONTRACT_DAYS[1::13])
    assert allocatorkit.assert_no_lookahead(ROTATION, history, members, sessions, list(HELDS), list(CONTRACT_PARAMS)) > 0
```
**Impact:** adds 39 tests (22 test functions; `test_params_validation` is parametrized 18 ways). No existing test
changes.

What each group proves (the phase-scope checklist):

| Scope item | Test(s) |
|---|---|
| momentum ranking, ties by symbol | `test_ranks_by_momentum_highest_first`, `test_ties_are_broken_by_symbol`, `test_momentum_uses_exactly_lookback_sessions` |
| top-K equal weights | `test_ranks_by_momentum_highest_first` (0.5 / 0.333333 / 1) |
| absolute filter (strict > 0) | `test_absolute_filter_leaves_non_positive_slots_unused` |
| fallback with / without a bar on d | `test_fallback_takes_the_unused_slots`, `test_fallback_without_a_bar_on_the_data_date_means_cash` |
| trend gate | `test_trend_gate_on_and_off`, `test_trend_gate_is_off_without_the_signal_bars`, `test_trend_symbol_may_be_in_the_universe` |
| missing / too-few-bars ETFs excluded that date | `test_missing_or_short_etfs_are_excluded_that_date`, `test_a_close_that_rounds_to_zero_is_not_eligible`, `test_a_zero_past_close_is_not_eligible` |
| held passthrough (rebalance drop) | `test_held_is_passed_through_untouched_and_never_kept`, `test_members_are_ignored` |
| lookback / symbols / holds / uses_members | `test_allocator_shape` |
| params validation + `as_dict()` | `test_params_defaults_and_as_dict`, `test_params_validation`, `test_params_are_frozen`, `test_wrong_types_raise` |
| P4 identity + no look-ahead | `test_p4_identity_and_no_look_ahead` (direct, 199 sessions × 4 params × 3 helds, incl. a late-launching ETF, gaps in a ranked ETF and the fallback; asserts the result set is non-vacuous: sizes 0–3 and the fallback all occur), `test_the_mutation_does_change_later_targets` (guard), `test_allocatorkit_contract` (via the kit) |

Every case was dry-run before this plan was written. The run used the worktree venv on `2546a92`,
with throwaway shims for phase 1's `Target`/`equal_weight` and phase 2's
`target_from_close`/`Allocator`/`return_window` and a stand-in kit checker, implemented as the
shared contract defines them. **All 39 passed.** The reconciler then rewrote
`test_allocatorkit_contract` to phase 2's real kit API (D-E). The non-vacuity assertions (`sizes >= {0, 1, 2, 3}`,
`fallback_seen > 0`, and the mutation guard) hold on the seeded data.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/trade-rules-dev-search && engine/.venv/bin/python -c "from seer_engine.strategies.f_rotation import ROTATION, RotationParams; print(ROTATION.id)"` prints `ROT`
**Tests:**
- `engine/.venv/bin/pytest engine/tests/test_f_rotation.py engine/tests/test_strategy_purity.py -q`
  passes. The rotation file contributes 39 tests.
- The whole suite, run with `docker start seer-pg` first:
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`.
  - It must pass with **0 skipped**.
  - The passed count must be the count after phases 1–2 **+ 39**. Log both numbers.
  - Use the worktree's own `engine/.venv`, never main's.
**Manual check:** `git diff --stat 2546a92 -- <frozen set from the plan index>` prints nothing; `git status` shows
only the two new files.
**Exit criteria:** `f_rotation.py` exists with `ROTATION.id == "ROT"`. The 39 rotation tests pass. The purity
glob loads the module with no forbidden import. The suite is green with 0 skipped.

## Handoffs

- **Phase 9 (`candidate_window`).** As contracted, it requires every symbol in `symbols(params)`,
  plus SPY, to have `>= lookback(params)` bars. That includes the **fallback**, even though the
  fallback needs only a bar on `d`. The effect: `F2-SPYQQQ-12M-IEF`, `F2-GEM-SPYEFA-IEF` and
  `F3-SEC-TOP3-6M-IEF` start only when IEF (launched 2002-07) has 253, 253 and 127 bars. That is
  later than their siblings without IEF.
  - This is conservative and correct, so it is not changed here.
  - If phase 9 or the reconciler wants an earlier start, it is phase 9's rule to change, not this
    module's.
  - The allocator already behaves correctly before the fallback has history: the unused slots go
    to cash.
- **Phase 10 (`rows_csv` / pre-registration).** `as_dict()["universe"]` contains commas
  (`"XLB,XLE,…"`). Any CSV that embeds `as_dict()` values must quote them, as `csv.writer` does.
  The trend is rendered `"SPY:200"` and an unset value `"none"`.
  - These spellings are the shared encoding (plan index D-F) and match phases 5, 7 and 8.
- **Phase 11 (registry).** It must pass `universe` already **sorted** (`RotationParams` raises
  otherwise):
  - `("QQQ","SPY")` and `("EFA","SPY")` are sorted;
  - `research.SECTOR_ETFS` is sorted (`XLB…XLY`).

  `fallback` must not be in `universe`. Rows 23–32 satisfy both. Owner inputs are phase 9's
  `candidate_owner_inputs`: `holds()` exposes `IEF`, `EFA` and the sector ETFs, so those rows get
  `etf:*` flags.
- **Phase 2 (kit shape).** `test_allocatorkit_contract` uses phase 2's exact names and
  signatures (plan index D-E). If it fails on the real kit, fix the call, never the kit.

## Rollback

Delete `engine/src/seer_engine/strategies/f_rotation.py` and `engine/tests/test_f_rotation.py`, or `git revert` the phase
commit. Nothing else references them until phase 11, so the revert is clean as long as phase 11 has not landed.
