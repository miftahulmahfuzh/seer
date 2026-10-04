> Adopted from `TRADE_RULES_DEV_SEARCH_PLAN.md` phase 2. Source: `.workflows/plan/trade-rules-dev-search/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Allocator protocol, adapters, overlays, return_window

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R3, R8. R3 is no look-ahead and P4 identity for every new family: this phase
provides the contract, its reusable test kit, and the proof for the adapter and the two overlays.
R8 is purity and determinism: the new module is pure, globbed, and has no unordered output.
**Depends on:** Phase 1 (`seer_engine.sim.book`: `Target`, `WEIGHT_QUANTUM`, `to_weight`, `equal_weight`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

After this phase, the book engine has its strategy interface:
- `strategies/allocator.py` defines the `Allocator` protocol;
- the shared helpers `target_from_close` and `month_end_closes` (plus `last_close`, `scale_weight`,
  `vol_scale` and `LazyPrepared`);
- the bracket-strategy adapter `PICKS`;
- the two overlays `BLEND` (F9) and `VOLTARGET` (L11);
- `strategies/indicators.py` gains `return_window`.

`tests/allocatorkit.py` is the one P4-identity / no-look-ahead / target-shape checker. Phases 5–8
import it. It is proven here: it accepts `PICKS`, `BLEND` and `VOLTARGET`, and it catches
deliberately broken allocators.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.

**Creates**
- In `seer_engine.strategies.allocator` (new file `engine/src/seer_engine/strategies/allocator.py`):
  - the protocol: `Allocator` (a `runtime_checkable` Protocol, exactly the index signature);
  - the helpers: `target_from_close`, `month_end_closes`, `last_close`, `scale_weight`,
    `vol_scale`, `LazyPrepared` and `TRADING_DAYS = 252`;
  - the adapter: `PicksParams`, `PicksAllocator`, `PICKS`;
  - the blend: `BlendPart`, `BlendParams`, `BlendAllocator`, `BLEND`;
  - the vol target: `VolTargetParams`, `VolTargetAllocator`, `VOLTARGET`.
- `seer_engine.strategies.indicators.return_window(close, n, skip=0)`.
- The test kit `engine/tests/allocatorkit.py`, with these exact signatures (phases 5–8 depend on them):
  ```python
  MembersFn = Callable[[date], AbstractSet[str]]
  def everyone(history: Mapping[str, History]) -> MembersFn
  def upto(history: Mapping[str, History], d: date) -> dict[str, History]
  def tail(history: Mapping[str, History], d: date, bars: int) -> dict[str, History]
  def assert_valid_targets(targets, history, data_date, held, *, max_weight_sum: Decimal | None = Decimal(1)) -> None
  def assert_p4_identity(allocator, history, members_fn, dates, held_sets, params, *,
                         max_weight_sum: Decimal | None = Decimal(1), check_lookback: bool = True) -> int
  def assert_no_lookahead(allocator, history, members_fn, sessions, held_sets, params) -> int
  # Fakes, reusable by later phases' tests (phase 3 / 9 may use them as cheap allocators):
  FixedParams(weights: tuple[tuple[str, Decimal], ...]); FixedAllocator (id "FAKE_FIXED"); FIXED
  MomentumParams(top: int = 2); MomentumFake(n: int = 5) (id "FAKE_MOM"); MOMENTUM = MomentumFake()
  ```
  - `dates` are data dates.
  - `sessions` are sessions S. The kit reads S's targets at `prev_session(S)`, then changes or
    deletes every bar dated on or after S.
  - `held_sets` and `params` are **non-empty lists or tuples**. `params` holds params values;
    passing a bare params value is a `TypeError`.
  - Both `assert_*` functions return the number of cases with a non-empty result, so callers
    can assert the check was not vacuous.

**Signature changes:** none. Every existing indicator and strategy function is untouched.

**Decisions this phase makes inside the contract** (confirmed by the reconciler; 1 and 2 are plan index D-D and D-A):
1. **`prepare(history)` has no params, but `PICKS`/`BLEND`/`VOLTARGET` keep their inner objects
   in params.**
   - Their `prepare` returns a `LazyPrepared(history)`. It runs each inner object's `prepare`
     on first use and caches the result by object identity.
   - The phase 9 dev runner's "prepare once per allocator id" therefore stays correct across
     candidates whose params name different inner objects.
2. **`PICKS` returns every pick, so Σ weight may exceed 1** (for example 4 held + 6 picks at
   0.25 each).
   - Under §5, a pick rejected at sizing (`lt_one_share`, cash) lets the next pick in. If the
     adapter truncated the list to the free slots, the exact V0_BOOK parity of phase 3 would
     break on real data, where sub-share slots are common (a slot is about $300).
   - So the engine's `max_positions` cap must pick the entrants.
   - **Settled (plan index Decisions, D-A):** phase 1's `step_book` checks Σ weight ≤ 1 only when
     `rules.max_positions is None`, so `PICKS` under `V0_BOOK` (`max_positions=4`) is accepted.
     Every other allocator keeps Σ weight ≤ 1, and the kit asserts it by default.
3. **`target_from_close` returns `None` for a non-finite price as well** as for a price <= 0
   after rounding or a broken ordering.
   - It raises `TypeError` for a bool, a str or any other non-number.
   - A bad `weight` raises (through `Target`).
4. **`BLEND`: a symbol targeted by several parts** gets the summed scaled weights, at its
   first-appearance rank, and keeps the **first** part's prices (`last`, `limit`, `stop`, `take`).
5. **Scaled weights that floor to 0 are dropped**, in both `BLEND` and `VOLTARGET`. They are
   never passed to `to_weight`, which would raise.
6. **`VOLTARGET`**
   - The window is the signal's last n+1 bars dated <= d. It does not need a bar dated d.
   - `VolTargetParams.n >= 2`.
   - "No scale" is represented as `vol_scale(...) is None`, and the inner tuple is then returned
     as is.
7. **`month_end_closes`**
   - Every month before `data_date`'s month is complete.
   - `data_date`'s own month is complete when `dates.next_session(data_date)` falls in a later
     month.
   - Each complete month contributes the close of **the symbol's own last bar** in that month.
8. **`held` must be a `frozenset`**, or `TypeError`. `members` must be a `collections.abc.Set`.
   The phase 3 runner passes `book.held()`, which is a frozenset.
9. **Params `as_dict()` exists on all three params classes.** Nested params are flattened with
   prefixes, because phase 9's `candidate_digest` and phase 10's report call `params.as_dict()`
   on every candidate:
   - `PicksParams`: `{"strategy", "slots", "params.<k>"…}`;
   - `BlendParams`: `{"part<i>.allocator", "part<i>.share", "part<i>.<k>"…}`;
   - `VolTargetParams`: `{"inner", "signal", "target_vol", "n", "inner.<k>"…}`.

   An inner params value without `as_dict` raises `TypeError` from `as_dict()` only.
10. **The protocols do not overlap.**
    - `isinstance(PICKS, Strategy)` is False, and `isinstance(STRATEGY_A, Allocator)` is False
      (tested).
    - Phase 3's `run_rules` can dispatch on these `isinstance` checks.

**Requires (from earlier phases)**
- Phase 1's `seer_engine/sim/book.py` exports `Target`, `WEIGHT_QUANTUM`, `to_weight` and
  `equal_weight` with these properties:
  - `Target` is a frozen (slots) dataclass with the keyword fields `symbol, weight, last, limit,
    stop, take`, value equality (`==`), and `dataclasses.replace` support.
  - `Target` raises `TypeError` on a float weight or price, and `ValueError` on weight 0.
  - `to_weight(Decimal)` floors to `WEIGHT_QUANTUM`.
  - `equal_weight(4) == Decimal("0.25")` and `equal_weight(3) == Decimal("0.333333")`.
- `seer_engine.sim` must keep exporting `Pick` and `q` (unchanged by phase 1).
- Importing `seer_engine.sim.book` must not import `seer_engine.strategies`, which would be a
  cycle: `strategies.base` imports `seer_engine.sim`.

**Leaves alone (owned by others)**
- `strategies/base.py`, `a.py`, `a2.py`, `b.py`, `b_model.py` and `strategies/__init__.py`. The
  new module is imported by its full path, `seer_engine.strategies.allocator`.
- Every existing indicator function and every existing test file.
- `sim/*` (phase 1), `backtest/book_runner.py` (phase 3), and the family modules (phases 5–8).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/allocator.py` | create | The protocol, the helpers, `PICKS`, `BLEND` and `VOLTARGET` (pure) |
| `engine/src/seer_engine/strategies/indicators.py` | modify (additive) | Insert `return_window` after `stdev_return_window` (after line 185, before `def rolling` at line 188) |
| `engine/tests/allocatorkit.py` | create | The reusable contract checks and two fake allocators |
| `engine/tests/test_allocator.py` | create | 55 tests: `return_window`, helpers, `PICKS`, `BLEND`, `VOLTARGET`, and the kit's self-tests |

`tests/test_strategy_purity.py` (glob `strategies/*.py`) and `tests/test_indicators.py`
(`test_indicators_use_no_reduction_along_the_time_axis`, an AST check over the whole of
`indicators.py`) cover the new code **without being edited**.

## Implementation Steps

### Step 1: Add `return_window` to the indicators
**File:** `engine/src/seer_engine/strategies/indicators.py`. Insert after line 185
(`        return np.sqrt(acc / n)`, the last line of `stdev_return_window`) and before line 188
(`def rolling(...)`). Keep exactly two blank lines on each side.
**Change:** a new window function.
- It reads only two columns, with an elementwise division, so it is bit-identical alone and
  under `rolling`.
- It uses no reduction, so the existing AST rule passes.
- Nothing existing is modified, including the module docstring.

**Code:**
```python
def return_window(close: np.ndarray, n: int, skip: int = 0) -> np.ndarray:
    """Return over ``n`` bars, ending ``skip`` bars before the window's last bar.

    ``c[:, -1-skip] / c[:, -1-n] - 1``: the close ``skip`` bars before the last, over the close
    ``n`` bars before the last. ``skip = 0`` is plain n-bar momentum; ``n = 252, skip = 21`` is
    12-1 momentum. Reads two columns only, so it is bit-identical alone and under ``rolling``.
    A zero base close gives a non-finite value (numpy's division warning suppressed). NaN for
    every row when the window has fewer than ``n + 1`` bars. Requires ``0 <= skip < n``.
    """
    close = _matrix("close", close)
    n = _period(n)
    if isinstance(skip, bool) or not isinstance(skip, int) or not 0 <= skip < n:
        raise ValueError(f"skip must be an int with 0 <= skip < n = {n}, got {skip!r}")
    w = close.shape[1]
    if w < n + 1:
        return _nan_rows(close)
    with np.errstate(divide="ignore", invalid="ignore"):
        return close[:, w - 1 - skip] / close[:, w - 1 - n] - 1.0
```
**Impact:** additive. `test_indicators_use_no_reduction_along_the_time_axis` now also scans this
function, and it uses no forbidden attribute.

### Step 2: Create `strategies/allocator.py`
**File:** `engine/src/seer_engine/strategies/allocator.py` (new)

**Change:** the whole module, as below.

Purity, so the existing glob passes:
- The imports are `seer_engine.dates`, `prices`, `sim`, `sim.book`, `strategies.base` and
  `strategies.indicators`, plus numpy and the stdlib.
- There is no clock, no random, no logging, no I/O and no `print`.

Determinism:
- Output order comes only from tuples, sorted sets and dict insertion order.
- `LazyPrepared` caches in a list compared by identity, never by hash order.

**Code:**
```python
"""Allocators: the strategy interface of the book engine (P7a), its shared helpers, one adapter and two overlays.

An allocator maps per-symbol bar history at a ``data_date`` close, plus the symbols the book
holds, to ranked ``sim.book.Target`` weights for the next session. ``sim.step_book`` turns
them into trades under a ``TradeRules`` value. Pure: no database, network, clock or randomness
(tests/test_strategy_purity.py globs this module).

CONTRACT (P4 identity), for every data date d, held set and params p::

    targets_prepared(prepare(H), M, d, held, p) == targets({s: h.upto(d) for s, h in H.items()}, M, d, held, p)

and ``targets`` reads only bars dated on or before d, however long the histories it is given.
Targets are in rank order with unique symbols, and every ``Target.last`` is the 4-dp close of
the symbol's last bar dated on or before d. A symbol with no bar dated d is never a new target
(only a held one may be kept). Σ weight <= 1, except for ``PICKS`` (see ``PicksAllocator``).
tests/allocatorkit.py checks all of this for every allocator.

``prepare(history)`` takes no params, so the adapter and overlays, whose inner objects live in
their params, prepare lazily: their prepared value is a ``LazyPrepared`` that runs each inner
object's ``prepare`` on first use and keeps the result, keyed by object identity.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any, Protocol, runtime_checkable

import numpy as np

from seer_engine import dates
from seer_engine.prices import to_decimal
from seer_engine.sim import Pick, q
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.base import History, Strategy, as_day
from seer_engine.strategies.indicators import stdev_return_window

TRADING_DAYS = 252  # vol annualization: daily stdev × sqrt(252)


# --------------------------------------------------------------------------- the protocol


@runtime_checkable
class Allocator(Protocol):
    """Maps history at data_date's close (plus what is held) to target weights for the next session."""

    id: str

    def lookback(self, params: Any) -> int: ...

    def symbols(self, params: Any) -> tuple[str, ...]: ...

    def holds(self, params: Any) -> tuple[str, ...]: ...

    def uses_members(self, params: Any) -> bool: ...

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]: ...

    def prepare(self, history: Mapping[str, History]) -> Any: ...

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]: ...


# --------------------------------------------------------------------------- shared helpers


def _plain(x: Decimal | int) -> str:
    """``x`` as a plain decimal string without trailing zeros: Decimal("0.120") -> "0.12"."""
    d = Decimal(x) if isinstance(x, int) else x
    return format(d.normalize(), "f")


def _price(name: str, x: object) -> Decimal | None:
    """``x`` as a 4-dp Decimal, or None when it is not finite. TypeError for a non-number."""
    if isinstance(x, bool) or not isinstance(x, (int, float, Decimal)):
        raise TypeError(f"{name} must be a float, int or Decimal, got {type(x).__name__}")
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, Decimal) and not x.is_finite():
        return None
    return q(to_decimal(x))


def target_from_close(
    symbol: str,
    close: float | Decimal,
    weight: Decimal,
    *,
    limit: float | Decimal | None = None,
    stop: float | Decimal | None = None,
    take: float | Decimal | None = None,
) -> Target | None:
    """A ``Target`` from float features, or None when its prices are unusable.

    Every price goes through ``prices.to_decimal`` (floats via their shortest repr) and
    ``sim.q``. None when any given price is not finite or is <= 0 after rounding, or when the
    ordering ``stop < ref < take`` fails, where ``ref`` is ``limit`` when given and the close
    otherwise (the ``a._bracket`` convention: an unusable bracket drops the candidate). A bad
    ``weight`` is a programming error and raises (``Target`` validates it).
    """
    last = _price("close", close)
    if last is None or last <= 0:
        return None
    given: dict[str, Decimal | None] = {}
    for name, x in (("limit", limit), ("stop", stop), ("take", take)):
        if x is None:
            given[name] = None
            continue
        p = _price(name, x)
        if p is None or p <= 0:
            return None
        given[name] = p
    ref = given["limit"] if given["limit"] is not None else last
    if given["stop"] is not None and not given["stop"] < ref:
        return None
    if given["take"] is not None and not given["take"] > ref:
        return None
    return Target(
        symbol=symbol,
        weight=weight,
        last=last,
        limit=given["limit"],
        stop=given["stop"],
        take=given["take"],
    )


def month_end_closes(h: History, data_date: date) -> np.ndarray:
    """Closes of the last bar of each completed calendar month, on or before ``data_date``, ascending.

    A month is completed when a later month has begun by ``data_date``: every month before
    ``data_date``'s, and ``data_date``'s own month when ``data_date`` is its last NYSE session
    (``dates.next_session`` falls in a later month). Each completed month contributes the close
    of the symbol's last bar dated in it (a month the symbol has no bar in contributes nothing).
    Reads only bars dated on or before ``data_date``. float64, a new array.
    """
    if not isinstance(h, History):
        raise TypeError(f"h must be a History, got {type(h).__name__}")
    day = as_day(data_date)
    end = int(np.searchsorted(h.dates, day, side="right"))
    if end == 0:
        return np.empty(0, dtype=np.float64)
    months = h.dates[:end].astype("datetime64[M]")
    ends = np.flatnonzero(months[1:] != months[:-1])
    after = dates.next_session(data_date)
    month_done = (after.year, after.month) != (data_date.year, data_date.month)
    if months[-1] < day.astype("datetime64[M]") or month_done:
        ends = np.append(ends, end - 1)
    return np.array(h.close[ends], dtype=np.float64)


def last_close(h: History | None, data_date: date) -> float | None:
    """The close of ``h``'s last bar dated on or before ``data_date``, or None when there is none."""
    if h is None:
        return None
    end = int(np.searchsorted(h.dates, as_day(data_date), side="right"))
    if end == 0:
        return None
    return float(h.close[end - 1])


def scale_weight(weight: Decimal, factor: Decimal) -> Decimal | None:
    """``to_weight(weight × factor)``, or None when the product floors to zero (the target is dropped)."""
    product = weight * factor
    if product.quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN) <= 0:
        return None
    return to_weight(product)


class LazyPrepared:
    """A history plus each inner object's ``prepare(history)``, computed on first use and kept.

    Inner objects (strategies, allocators) are keyed by identity, so one ``LazyPrepared`` serves
    every params value of an adapter or overlay, whichever inner objects those params name.
    """

    __slots__ = ("_cache", "history")

    def __init__(self, history: Mapping[str, History]) -> None:
        self.history: dict[str, History] = dict(history)
        self._cache: list[tuple[Any, Any]] = []

    def of(self, inner: Any) -> Any:
        for obj, value in self._cache:
            if obj is inner:
                return value
        value = inner.prepare(self.history)
        self._cache.append((inner, value))
        return value


def _lazy(prepared: object) -> LazyPrepared:
    if not isinstance(prepared, LazyPrepared):
        raise TypeError(f"prepared must be LazyPrepared, got {type(prepared).__name__}")
    return prepared


def _check_call(members: object, data_date: object, held: object) -> None:
    if not isinstance(members, AbstractSet):
        raise TypeError(f"members must be a set, got {type(members).__name__}")
    as_day(data_date)
    if not isinstance(held, frozenset):
        raise TypeError(f"held must be a frozenset, got {type(held).__name__}")


def _params_dict(name: str, params: Any) -> dict[str, str]:
    as_dict = getattr(params, "as_dict", None)
    if as_dict is None:
        raise TypeError(f"{name} ({type(params).__name__}) has no as_dict()")
    return dict(as_dict())


# --------------------------------------------------------------------------- PICKS: bracket strategies as targets


@dataclass(frozen=True, slots=True)
class PicksParams:
    """A bracket ``Strategy`` (A, A2, B), its params, and the slot count that sets each weight."""

    strategy: Strategy
    params: Any
    slots: int = 4  # weight = equal_weight(slots)

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, Strategy):
            raise TypeError(f"strategy must be a Strategy, got {type(self.strategy).__name__}")
        if isinstance(self.slots, bool) or not isinstance(self.slots, int):
            raise TypeError(f"slots must be an int, got {type(self.slots).__name__}")
        if self.slots < 1:
            raise ValueError(f"slots must be >= 1, got {self.slots}")

    def as_dict(self) -> dict[str, str]:
        out = {"strategy": self.strategy.id, "slots": str(self.slots)}
        for k, v in _params_dict("params", self.params).items():
            out[f"params.{k}"] = v
        return out


def _picks_params(params: object) -> PicksParams:
    if not isinstance(params, PicksParams):
        raise TypeError(f"params must be PicksParams, got {type(params).__name__}")
    return params


def _picks_targets(
    history: Mapping[str, History],
    picks: list[Pick],
    data_date: date,
    held: frozenset[str],
    params: PicksParams,
) -> tuple[Target, ...]:
    w = equal_weight(params.slots)
    out: list[Target] = []
    for symbol in sorted(held):
        close = last_close(history.get(symbol), data_date)
        if close is None:
            raise ValueError(f"held symbol {symbol} has no bar on or before {data_date}")
        out.append(Target(symbol=symbol, weight=w, last=q(to_decimal(close))))
    seen = set(held)
    for pick in picks:
        if pick.symbol in seen:
            continue
        seen.add(pick.symbol)
        out.append(
            Target(
                symbol=pick.symbol,
                weight=w,
                last=pick.last_price,
                limit=pick.limit_price,
                stop=pick.sl_price,
                take=pick.tp_price,
            )
        )
    return tuple(out)


class PicksAllocator:
    """A bracket ``Strategy`` behind the ``Allocator`` protocol (the V0_BOOK parity adapter).

    Targets: every held symbol first, in symbol order, at weight ``equal_weight(slots)`` with
    ``last`` = its last close on or before d and no limit, stop or take (so the engine keeps it
    and never resizes it); then each pick, in rank order, whose symbol is neither held nor seen
    before, as ``Target(symbol, w, last, limit, stop=sl, take=tp)``.

    Every pick is returned, not just ``slots`` of them: under §5 a pick rejected at sizing (too
    small, no cash) lets the next one in, so the engine's ``max_positions`` cap, not this
    adapter, must decide which picks get the free slots. Σ weight may therefore exceed 1. PICKS
    is valid only with rules whose ``max_positions`` equals ``params.slots`` (``V0_BOOK``).
    """

    id = "PICKS"

    def lookback(self, params: Any) -> int:
        return int(_picks_params(params).strategy.lookback)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _picks_params(params)
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _picks_params(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _picks_params(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _picks_params(params)
        _check_call(members, data_date, held)
        picks = p.strategy.picks(history, members, data_date, p.params)
        return _picks_targets(history, picks, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _picks_params(params)
        lazy = _lazy(prepared)
        _check_call(members, data_date, held)
        picks = p.strategy.picks_prepared(lazy.of(p.strategy), members, data_date, p.params)
        return _picks_targets(lazy.history, picks, data_date, held, p)


PICKS = PicksAllocator()


# --------------------------------------------------------------------------- BLEND: core + satellite (F9)


@dataclass(frozen=True, slots=True)
class BlendPart:
    """One sleeve of a blend: an allocator, its params, and the share of equity it runs."""

    allocator: Allocator
    params: Any
    share: Decimal  # (0, 1], a multiple of WEIGHT_QUANTUM

    def __post_init__(self) -> None:
        if not isinstance(self.allocator, Allocator):
            raise TypeError(f"allocator must be an Allocator, got {type(self.allocator).__name__}")
        if not isinstance(self.share, Decimal):
            raise TypeError(f"share must be a Decimal, got {type(self.share).__name__}")
        if not self.share.is_finite() or not 0 < self.share <= 1:
            raise ValueError(f"share must be in (0, 1], got {self.share}")
        if self.share % WEIGHT_QUANTUM != 0:
            raise ValueError(f"share must be a multiple of {WEIGHT_QUANTUM}, got {self.share}")


@dataclass(frozen=True, slots=True)
class BlendParams:
    parts: tuple[BlendPart, ...]  # >= 2 parts, Σ share <= 1

    def __post_init__(self) -> None:
        if not isinstance(self.parts, tuple):
            raise TypeError(f"parts must be a tuple, got {type(self.parts).__name__}")
        for part in self.parts:
            if not isinstance(part, BlendPart):
                raise TypeError(f"parts must be BlendPart values, got {type(part).__name__}")
        if len(self.parts) < 2:
            raise ValueError(f"a blend needs >= 2 parts, got {len(self.parts)}")
        total = sum((part.share for part in self.parts), Decimal(0))
        if total > 1:
            raise ValueError(f"part shares sum to {total} > 1")

    def as_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for i, part in enumerate(self.parts, start=1):
            out[f"part{i}.allocator"] = part.allocator.id
            out[f"part{i}.share"] = _plain(part.share)
            for k, v in _params_dict(f"part{i}.params", part.params).items():
                out[f"part{i}.{k}"] = v
        return out


def _blend_params(params: object) -> BlendParams:
    if not isinstance(params, BlendParams):
        raise TypeError(f"params must be BlendParams, got {type(params).__name__}")
    return params


def _part_held(params: BlendParams, held: frozenset[str]) -> list[frozenset[str]]:
    """held_i = held − ∪_{j≠i} holds(part j): a sleeve never sees another sleeve's fixed holdings."""
    holds = [frozenset(part.allocator.holds(part.params)) for part in params.parts]
    out = []
    for i in range(len(params.parts)):
        others: frozenset[str] = frozenset().union(*(h for j, h in enumerate(holds) if j != i))
        out.append(held - others)
    return out


def _merge(scaled: list[tuple[Decimal, tuple[Target, ...]]]) -> tuple[Target, ...]:
    """Weights × share (floored; zero drops), summed per symbol, ranked by first appearance.

    A symbol several sleeves target keeps the first sleeve's prices (last, limit, stop, take).
    """
    order: list[str] = []
    first: dict[str, Target] = {}
    total: dict[str, Decimal] = {}
    for share, targets in scaled:
        for t in targets:
            w = scale_weight(t.weight, share)
            if w is None:
                continue
            if t.symbol in first:
                total[t.symbol] += w
            else:
                order.append(t.symbol)
                first[t.symbol] = t
                total[t.symbol] = w
    return tuple(replace(first[s], weight=total[s]) for s in order)


class BlendAllocator:
    """Several allocators, each running a fixed share of equity (F9 core + satellite).

    Part i is called with ``held_i = held − ∪_{j≠i} holds(part j)``; its weights are scaled by
    its share and floored to WEIGHT_QUANTUM (targets that floor to zero are dropped). A symbol
    targeted by several parts gets the sum of its scaled weights, at the rank of its first
    appearance (part order, then rank within the part), with the first part's prices.
    """

    id = "BLEND"

    def lookback(self, params: Any) -> int:
        p = _blend_params(params)
        return max(part.allocator.lookback(part.params) for part in p.parts)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _blend_params(params)
        return tuple(sorted({s for part in p.parts for s in part.allocator.symbols(part.params)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _blend_params(params)
        return tuple(sorted({s for part in p.parts for s in part.allocator.holds(part.params)}))

    def uses_members(self, params: Any) -> bool:
        p = _blend_params(params)
        return any(part.allocator.uses_members(part.params) for part in p.parts)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _blend_params(params)
        _check_call(members, data_date, held)
        scaled = [
            (part.share, part.allocator.targets(history, members, data_date, part_held, part.params))
            for part, part_held in zip(p.parts, _part_held(p, held), strict=True)
        ]
        return _merge(scaled)

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _blend_params(params)
        lazy = _lazy(prepared)
        _check_call(members, data_date, held)
        scaled = [
            (
                part.share,
                part.allocator.targets_prepared(lazy.of(part.allocator), members, data_date, part_held, part.params),
            )
            for part, part_held in zip(p.parts, _part_held(p, held), strict=True)
        ]
        return _merge(scaled)


BLEND = BlendAllocator()


# --------------------------------------------------------------------------- VOLTARGET: volatility targeting (L11)


@dataclass(frozen=True, slots=True)
class VolTargetParams:
    inner: Allocator
    inner_params: Any
    signal: str = "SPY"  # whose daily returns measure volatility
    target_vol: Decimal = Decimal("0.12")  # annualized
    n: int = 20  # returns in the stdev window

    def __post_init__(self) -> None:
        if not isinstance(self.inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(self.inner).__name__}")
        if not isinstance(self.signal, str) or not self.signal:
            raise ValueError("signal must be a non-empty str")
        if not isinstance(self.target_vol, Decimal):
            raise TypeError(f"target_vol must be a Decimal, got {type(self.target_vol).__name__}")
        if not self.target_vol.is_finite() or self.target_vol <= 0:
            raise ValueError(f"target_vol must be > 0, got {self.target_vol}")
        if isinstance(self.n, bool) or not isinstance(self.n, int):
            raise TypeError(f"n must be an int, got {type(self.n).__name__}")
        if self.n < 2:
            raise ValueError(f"n must be >= 2, got {self.n}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "inner": self.inner.id,
            "signal": self.signal,
            "target_vol": _plain(self.target_vol),
            "n": str(self.n),
        }
        for k, v in _params_dict("inner_params", self.inner_params).items():
            out[f"inner.{k}"] = v
        return out


def _vol_params(params: object) -> VolTargetParams:
    if not isinstance(params, VolTargetParams):
        raise TypeError(f"params must be VolTargetParams, got {type(params).__name__}")
    return params


def vol_scale(signal: History | None, data_date: date, n: int, target_vol: Decimal) -> Decimal | None:
    """min(1, target_vol / (stdev_return_window(last n+1 closes through data_date, n) × sqrt(252))).

    Computed in float, returned as ``Decimal(repr(scale))``. None means "do not scale" (1): no
    signal history, fewer than n + 1 bars through ``data_date``, a zero or non-finite stdev, or a
    scale >= 1. Reads only bars dated on or before ``data_date``.
    """
    if signal is None:
        return None
    end = int(np.searchsorted(signal.dates, as_day(data_date), side="right"))
    if end < n + 1:
        return None
    window = signal.close[end - n - 1 : end][None, :]
    sd = float(stdev_return_window(window, n)[0])
    if not math.isfinite(sd) or sd <= 0.0:
        return None
    scale = float(target_vol) / (sd * math.sqrt(TRADING_DAYS))
    if not math.isfinite(scale) or scale >= 1.0:
        return None
    return Decimal(repr(scale))


def _scaled(targets: tuple[Target, ...], scale: Decimal | None) -> tuple[Target, ...]:
    if scale is None:
        return targets
    out: list[Target] = []
    for t in targets:
        w = scale_weight(t.weight, scale)
        if w is not None:
            out.append(replace(t, weight=w))
    return tuple(out)


class VolTargetAllocator:
    """Scales an inner allocator's weights down when the signal's recent volatility is high (L11).

    scale = min(1, target_vol / (stdev of the signal's last n daily returns × sqrt(252))); every
    inner weight × scale is floored to WEIGHT_QUANTUM and targets that floor to zero are dropped.
    Without n + 1 signal bars through d, or with a zero stdev, the inner targets pass unchanged.
    The freed weight is cash (or ``rules.idle_symbol``).
    """

    id = "VOLTARGET"

    def lookback(self, params: Any) -> int:
        p = _vol_params(params)
        return max(p.inner.lookback(p.inner_params), p.n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _vol_params(params)
        return tuple(sorted(set(p.inner.symbols(p.inner_params)) | {p.signal}))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _vol_params(params)
        return tuple(p.inner.holds(p.inner_params))

    def uses_members(self, params: Any) -> bool:
        p = _vol_params(params)
        return bool(p.inner.uses_members(p.inner_params))

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _vol_params(params)
        _check_call(members, data_date, held)
        inner = p.inner.targets(history, members, data_date, held, p.inner_params)
        return _scaled(inner, vol_scale(history.get(p.signal), data_date, p.n, p.target_vol))

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _vol_params(params)
        lazy = _lazy(prepared)
        _check_call(members, data_date, held)
        inner = p.inner.targets_prepared(lazy.of(p.inner), members, data_date, held, p.inner_params)
        return _scaled(inner, vol_scale(lazy.history.get(p.signal), data_date, p.n, p.target_vol))


VOLTARGET = VolTargetAllocator()
```
**Impact:** new module only. Nothing imports it yet; phases 3 and 5–12 will.

### Step 3: Create the reusable kit `tests/allocatorkit.py`
**File:** `engine/tests/allocatorkit.py` (new). Test modules import it as `from allocatorkit import ...`,
exactly like `stratkit` and `simkit`, because pytest puts `engine/tests` on `sys.path`.

**Change:** the contract checks and two fakes:
- `FixedAllocator` reads fixed symbols.
- `MomentumFake` reads members. Its `prepare` uses `rolling(return_window, …)`, so its
  prepared path is genuinely different code from its single-window path.

**Code:**
```python
"""Contract checks for every ``Allocator`` (P7a phases 2, 5–8) and two small fake allocators.

Every allocator test module runs the same three checks on its own synthetic histories:

- ``assert_valid_targets``: the shape of one ``targets`` result (types, unique symbols,
  Σ weight, ``last`` = the 4-dp close of the last bar on or before d, no new symbol without a
  bar dated d);
- ``assert_p4_identity``: ``targets_prepared(prepare(H), ...) == targets(H.upto(d), ...)`` and
  ``targets(H, ...) == targets(H.upto(d), ...)`` for every date, held set and params value, and
  (by default) the same result from histories cut to ``lookback(params)`` bars;
- ``assert_no_lookahead``: changing, or deleting, every bar dated on or after session S leaves
  S's targets (read at ``prev_session(S)``) unchanged, on both the single-window and the
  prepared path.

Each check returns how many cases produced a non-empty target tuple, so a caller can assert
the check was not vacuous. ``params`` is always a non-empty list or tuple of params values.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
from stratkit import mutate_from, truncate_before

from seer_engine.dates import prev_session
from seer_engine.prices import to_decimal
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import Allocator, last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.indicators import return_window, rolling

MembersFn = Callable[[date], AbstractSet[str]]


def everyone(history: Mapping[str, History]) -> MembersFn:
    """A members function: every symbol of ``history`` is a member on every date."""
    members = frozenset(history)
    return lambda d: members


def upto(history: Mapping[str, History], d: date) -> dict[str, History]:
    """Every history cut to its bars dated on or before ``d`` (the single-window input)."""
    return {s: h.upto(d) for s, h in history.items()}


def tail(history: Mapping[str, History], d: date, bars: int) -> dict[str, History]:
    """Every history cut to its last ``bars`` bars dated on or before ``d``."""
    out = {}
    for s, h in history.items():
        cut = h.upto(d)
        start = max(len(cut) - bars, 0)
        out[s] = History(
            s,
            cut.dates[start:],
            cut.open[start:],
            cut.high[start:],
            cut.low[start:],
            cut.close[start:],
            cut.volume[start:],
        )
    return out


def _params_list(params: object) -> tuple[Any, ...]:
    if not isinstance(params, (list, tuple)) or not params:
        raise TypeError("params must be a non-empty list or tuple of params values")
    return tuple(params)


def _held_list(held_sets: object) -> tuple[frozenset[str], ...]:
    if not isinstance(held_sets, (list, tuple)) or not held_sets:
        raise TypeError("held_sets must be a non-empty list or tuple of sets of symbols")
    return tuple(frozenset(h) for h in held_sets)


def assert_valid_targets(
    targets: object,
    history: Mapping[str, History],
    data_date: date,
    held: AbstractSet[str],
    *,
    max_weight_sum: Decimal | None = Decimal(1),
) -> None:
    """One ``targets`` result obeys the Allocator contract (``max_weight_sum=None`` skips Σ weight)."""
    assert isinstance(targets, tuple), f"targets must be a tuple, got {type(targets).__name__}"
    for t in targets:
        assert isinstance(t, Target), f"not a Target: {t!r}"
    symbols = [t.symbol for t in targets]
    assert len(set(symbols)) == len(symbols), f"duplicate symbols on {data_date}: {symbols}"
    if max_weight_sum is not None:
        total = sum((t.weight for t in targets), Decimal(0))
        assert total <= max_weight_sum, f"Σ weight {total} > {max_weight_sum} on {data_date}"
    for t in targets:
        h = history.get(t.symbol)
        assert h is not None, f"{t.symbol} targeted on {data_date} but has no history"
        if h.index_of(data_date) is None:
            assert t.symbol in held, f"{t.symbol} is a new target on {data_date} without a bar that day"
        close = last_close(h, data_date)
        assert close is not None, f"{t.symbol} has no bar on or before {data_date}"
        assert t.last == to_decimal(close), f"{t.symbol} last {t.last} != close {close} on {data_date}"


def assert_p4_identity(
    allocator: Allocator,
    history: Mapping[str, History],
    members_fn: MembersFn,
    dates: Sequence[date],
    held_sets: Sequence[AbstractSet[str]],
    params: Sequence[Any],
    *,
    max_weight_sum: Decimal | None = Decimal(1),
    check_lookback: bool = True,
) -> int:
    """The P4 identity on every (date, held set, params value); returns the non-empty count.

    For each case: the single-window result is valid (``assert_valid_targets``); ``targets`` on
    the full histories equals it (later bars are never read); ``targets_prepared`` on one
    ``prepare(history)`` equals it; and, with ``check_lookback``, ``targets`` on histories cut
    to their last ``lookback(params)`` bars through d equals it.
    """
    assert isinstance(allocator, Allocator), f"{allocator!r} is not an Allocator"
    params_list = _params_list(params)
    held_list = _held_list(held_sets)
    prepared = allocator.prepare(history)
    nonempty = 0
    for d in dates:
        members = frozenset(members_fn(d))
        window = upto(history, d)
        for held in held_list:
            for p in params_list:
                case = f"{allocator.id} on {d}, held={sorted(held)}, params={p!r}"
                single = allocator.targets(window, members, d, held, p)
                assert_valid_targets(single, history, d, held, max_weight_sum=max_weight_sum)
                assert allocator.targets(history, members, d, held, p) == single, f"reads bars after d: {case}"
                assert allocator.targets_prepared(prepared, members, d, held, p) == single, f"P4 identity: {case}"
                if check_lookback:
                    short = tail(history, d, allocator.lookback(p))
                    assert allocator.targets(short, members, d, held, p) == single, f"lookback too short: {case}"
                nonempty += bool(single)
    return nonempty


def assert_no_lookahead(
    allocator: Allocator,
    history: Mapping[str, History],
    members_fn: MembersFn,
    sessions: Sequence[date],
    held_sets: Sequence[AbstractSet[str]],
    params: Sequence[Any],
) -> int:
    """For each session S: targets read at ``prev_session(S)`` ignore every bar dated >= S.

    Two futures per S: every bar dated on or after S changed (``stratkit.mutate_from``) and
    deleted (``stratkit.truncate_before``). Both paths (``targets`` and ``targets_prepared`` on
    a fresh ``prepare``) must equal the result on the untouched history. Returns the non-empty count.
    """
    assert isinstance(allocator, Allocator), f"{allocator!r} is not an Allocator"
    params_list = _params_list(params)
    held_list = _held_list(held_sets)
    prepared = allocator.prepare(history)
    nonempty = 0
    for s in sessions:
        d = prev_session(s)
        members = frozenset(members_fn(d))
        futures = {
            "changed": {k: mutate_from(h, s) for k, h in history.items()},
            "deleted": {k: truncate_before(h, s) for k, h in history.items()},
        }
        prepared_futures = {name: allocator.prepare(f) for name, f in futures.items()}
        for held in held_list:
            for p in params_list:
                case = f"{allocator.id} for session {s}, held={sorted(held)}, params={p!r}"
                before = allocator.targets(history, members, d, held, p)
                assert allocator.targets_prepared(prepared, members, d, held, p) == before, f"P4 identity: {case}"
                for name, future in futures.items():
                    assert allocator.targets(future, members, d, held, p) == before, f"look-ahead ({name}): {case}"
                    got = allocator.targets_prepared(prepared_futures[name], members, d, held, p)
                    assert got == before, f"look-ahead, prepared ({name}): {case}"
                nonempty += bool(before)
    return nonempty


# --------------------------------------------------------------------------- fake allocators


def _plain(w: Decimal) -> str:
    return format(w.normalize(), "f")


@dataclass(frozen=True, slots=True)
class FixedParams:
    weights: tuple[tuple[str, Decimal], ...]  # (symbol, weight) in rank order

    def as_dict(self) -> dict[str, str]:
        return {s: _plain(w) for s, w in self.weights}


class FixedAllocator:
    """Fixed symbols at fixed weights, each while it has a bar on d; a held one without a bar is kept."""

    id = "FAKE_FIXED"

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({s for s, _ in params.weights}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return self.symbols(params)

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        out = []
        for symbol, w in params.weights:
            h = history.get(symbol)
            close = last_close(h, data_date)
            if close is None or (h.index_of(data_date) is None and symbol not in held):
                continue
            t = target_from_close(symbol, close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


FIXED = FixedAllocator()


@dataclass(frozen=True, slots=True)
class MomentumParams:
    top: int = 2

    def as_dict(self) -> dict[str, str]:
        return {"top": str(self.top)}


class MomentumFake:
    """Members with a bar on d ranked by ``n``-bar return (desc, then symbol); the top K with a
    positive return at ``equal_weight(top)``. ``prepare`` precomputes the returns with
    ``rolling``, so its path really differs from the single-window one."""

    id = "FAKE_MOM"

    def __init__(self, n: int = 5) -> None:
        self.n = n

    def lookback(self, params: Any) -> int:
        return self.n + 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Any) -> bool:
        return True

    def _ranked(self, rows: list[tuple[str, float, float]], params: MomentumParams) -> tuple[Target, ...]:
        rows = sorted((r for r in rows if np.isfinite(r[1]) and r[1] > 0.0), key=lambda r: (-r[1], r[0]))
        w = equal_weight(params.top)
        out = []
        for symbol, _, close in rows[: params.top]:
            t = target_from_close(symbol, close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        rows = []
        for s in sorted(history):
            h = history[s]
            i = h.index_of(data_date)
            if s not in members or i is None or i < self.n:
                continue
            mom = float(return_window(h.close[None, i - self.n : i + 1], self.n)[0])
            rows.append((s, mom, float(h.close[i])))
        return self._ranked(rows, params)

    def prepare(self, history):
        return {s: (h, rolling(return_window, h.close, window=self.n + 1, n=self.n)) for s, h in history.items()}

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        rows = []
        for s in sorted(prepared):
            h, mom = prepared[s]
            i = h.index_of(data_date)
            if s not in members or i is None or i < self.n:
                continue
            rows.append((s, float(mom[i]), float(h.close[i])))
        return self._ranked(rows, params)


MOMENTUM = MomentumFake()
```
**Impact:** test helper only. Phases 5–8 call `assert_p4_identity` and `assert_no_lookahead`
with their own histories:
- `max_weight_sum` defaults to 1.
- `check_lookback=True` proves that `lookback(params)` bars through d suffice. A family whose
  rule reads month-ends must set its `lookback` large enough, or pass `check_lookback=False`
  with a reason.

### Step 4: Create `tests/test_allocator.py`
**File:** `engine/tests/test_allocator.py` (new). It holds 55 tests (pytest node count,
parametrized cases included):
- 10 `return_window` (4 of them parametrized);
- 1 protocol;
- 15 `target_from_close` (12 of them parametrized);
- 3 `month_end_closes`;
- 2 helpers;
- 7 `PICKS`;
- 6 `BLEND`;
- 5 `VOLTARGET`;
- 6 kit self-tests.

**Code:**
```python
"""P7a phase 2: the Allocator protocol, its helpers, PICKS, BLEND, VOLTARGET, return_window, and the kit.

The P4 identity and no-look-ahead checks run through tests/allocatorkit.py, which phases 5–8
reuse; the kit's own checks are tested here against deliberately broken allocators.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from allocatorkit import (
    FIXED,
    MOMENTUM,
    FixedParams,
    MomentumParams,
    assert_no_lookahead,
    assert_p4_identity,
    assert_valid_targets,
    everyone,
    upto,
)
from stratkit import dip, drop_days, hist, sawtooth, session_days, uptrend

from seer_engine.dates import prev_session, sessions
from seer_engine.sim import Pick
from seer_engine.sim.book import Target
from seer_engine.strategies import STRATEGY_A, AParams, Strategy
from seer_engine.strategies.allocator import (
    BLEND,
    PICKS,
    VOLTARGET,
    Allocator,
    BlendAllocator,
    BlendParams,
    BlendPart,
    LazyPrepared,
    PicksAllocator,
    PicksParams,
    VolTargetAllocator,
    VolTargetParams,
    last_close,
    month_end_closes,
    scale_weight,
    target_from_close,
    vol_scale,
)
from seer_engine.strategies.indicators import return_window, rolling

D = Decimal
PERMISSIVE = AParams(rsi_max=100.0, min_dollar_volume=0.0)


def rows(*r: list[float]) -> np.ndarray:
    return np.array(r, dtype=np.float64)


# ---- fakes local to this module ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstParams:
    targets: tuple[Target, ...]
    holds: tuple[str, ...] = ()
    lookback: int = 1

    def as_dict(self) -> dict[str, str]:
        return {"targets": ",".join(t.symbol for t in self.targets)}


class ConstAllocator:
    """Returns ``params.targets`` verbatim and records every ``held`` it was called with."""

    id = "FAKE_CONST"

    def __init__(self) -> None:
        self.seen_held: list[frozenset[str]] = []
        self.prepare_calls = 0

    def lookback(self, params: Any) -> int:
        return params.lookback

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({t.symbol for t in params.targets}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return params.holds

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history, members, data_date, held, params):
        self.seen_held.append(held)
        return params.targets

    def prepare(self, history):
        self.prepare_calls += 1
        return "prepared"

    def targets_prepared(self, prepared, members, data_date, held, params):
        assert prepared == "prepared"
        return self.targets({}, members, data_date, held, params)


class MembersFake(ConstAllocator):
    id = "FAKE_MEMBERS"

    def uses_members(self, params: Any) -> bool:
        return True


class ListStrategy:
    """A Strategy returning a fixed pick list; counts prepare calls."""

    id = "LIST"
    lookback = 3

    def __init__(self, picks: list[Pick]) -> None:
        self._picks = picks
        self.prepare_calls = 0

    def picks(self, history, members, data_date, params):
        return list(self._picks)

    def prepare(self, history):
        self.prepare_calls += 1
        return None

    def picks_prepared(self, prepared, members, data_date, params):
        return list(self._picks)


class PeekAllocator:
    """BROKEN on purpose: reads each history's very last bar, whatever the data date."""

    id = "FAKE_PEEK"

    def lookback(self, params):
        return 1

    def symbols(self, params):
        return ()

    def holds(self, params):
        return ()

    def uses_members(self, params):
        return True

    def targets(self, history, members, data_date, held, params):
        out = []
        for s in sorted(history):
            h = history[s]
            i = h.index_of(data_date)
            if s in members and i is not None and h.close[-1] > h.close[i]:  # "a later bar is higher"
                out.append(target_from_close(s, float(h.close[i]), D("0.1")))
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params):
        return self.targets(prepared, members, data_date, held, params)


class ForgetfulAllocator(PeekAllocator):
    """BROKEN on purpose: honest single-window targets, but the prepared path returns nothing."""

    id = "FAKE_FORGET"

    def targets(self, history, members, data_date, held, params):
        return tuple(
            target_from_close(s, float(history[s].close[history[s].index_of(data_date)]), D("0.1"))
            for s in sorted(history)
            if s in members and history[s].index_of(data_date) is not None
        )

    def targets_prepared(self, prepared, members, data_date, held, params):
        return ()


def t(symbol: str, weight: str, last: str = "10", **prices: str) -> Target:
    return Target(symbol=symbol, weight=D(weight), last=D(last), **{k: D(v) for k, v in prices.items()})


# ---- return_window ------------------------------------------------------------------------


def test_return_window_hand_computed():
    assert return_window(rows([100, 110, 121]), 2).tolist() == [121.0 / 100.0 - 1.0]
    # Two rows, each its own window: 30/20 - 1 and 9/12 - 1.
    assert return_window(rows([10, 20, 30], [12, 3, 9]), 1).tolist() == [30.0 / 20.0 - 1.0, 9.0 / 3.0 - 1.0]


def test_return_window_reads_only_the_two_end_columns():
    # n = 2: c[-1] / c[-3] - 1; columns 0 and -2 are ignored.
    assert return_window(rows([999, 100, 7, 110]), 2).tolist() == [110.0 / 100.0 - 1.0]


def test_return_window_skip_is_the_12_1_shape():
    # n = 3, skip = 1: c[-2] / c[-4] - 1 = 200 / 100 - 1; the last close (120) is skipped.
    assert return_window(rows([100, 50, 200, 120]), 3, skip=1).tolist() == [1.0]
    assert return_window(rows([100, 50, 200, 120]), 3, 2).tolist() == [50.0 / 100.0 - 1.0]


def test_return_window_warm_up_boundary():
    assert math.isnan(return_window(rows([1, 2]), 2)[0])  # W = n
    assert return_window(rows([4, 1, 6]), 2).tolist() == [0.5]  # W = n + 1


def test_return_window_zero_base_is_not_finite_and_silent():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = return_window(rows([0, 1, 2], [0, 1, 0]), 2)
    assert math.isinf(out[0]) and math.isnan(out[1])


def test_return_window_rejects_bad_input():
    with pytest.raises(ValueError, match="2-D"):
        return_window(np.array([1.0, 2.0, 3.0]), 2)
    with pytest.raises(ValueError, match="n must be"):
        return_window(rows([1, 2, 3]), 0)
    for skip in (2, 3, -1, True, 1.0):
        with pytest.raises(ValueError, match="skip"):
            return_window(rows([1, 2, 3]), 2, skip)


@pytest.mark.parametrize(("n", "skip"), [(1, 0), (20, 0), (126, 21), (199, 21)])
def test_return_window_rolling_is_bit_identical_to_one_window(n, skip):
    rng = np.random.default_rng(7)
    close = np.round(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, 600))), 4)
    out = rolling(return_window, close, window=200, n=n, skip=skip)
    assert np.isnan(out[:199]).all()
    for i in range(199, 600):
        assert return_window(close[None, i - 199 : i + 1].copy(), n, skip)[0] == out[i], i


# ---- the protocol -------------------------------------------------------------------------


def test_the_adapters_are_allocators_and_not_strategies():
    for a in (PICKS, BLEND, VOLTARGET, FIXED, MOMENTUM):
        assert isinstance(a, Allocator)
        assert not isinstance(a, Strategy)
    assert not isinstance(STRATEGY_A, Allocator)
    assert (PICKS.id, BLEND.id, VOLTARGET.id) == ("PICKS", "BLEND", "VOLTARGET")
    assert isinstance(PICKS, PicksAllocator)
    assert isinstance(BLEND, BlendAllocator)
    assert isinstance(VOLTARGET, VolTargetAllocator)


# ---- target_from_close --------------------------------------------------------------------


def test_target_from_close_rounds_through_to_decimal():
    got = target_from_close("AAA", 101.23456, D("0.5"))
    assert got == Target(symbol="AAA", weight=D("0.5"), last=D("101.2346"))
    assert target_from_close("AAA", 0.1, D("1")).last == D("0.1000")  # shortest repr, not binary
    assert target_from_close("AAA", D("7.12345"), D("1")).last == D("7.1235")  # half-up


def test_target_from_close_bracket():
    got = target_from_close("AAA", 50.0, D("0.25"), limit=49.5, stop=47.0, take=51.25)
    assert got == Target(symbol="AAA", weight=D("0.25"), last=D("50.0000"), limit=D("49.5000"), stop=D("47.0000"), take=D("51.2500"))
    # Without a limit, stop and take are ordered around the close.
    assert target_from_close("AAA", 50.0, D("1"), stop=45.0, take=60.0).stop == D("45.0000")
    # A limit above the close is allowed (an open_limit-style entry).
    assert target_from_close("AAA", 50.0, D("1"), limit=51.0).limit == D("51.0000")


@pytest.mark.parametrize(
    "kw",
    [
        {"close": 0.0},
        {"close": -1.0},
        {"close": 0.00004},  # rounds to 0
        {"close": math.nan},
        {"close": math.inf},
        {"close": 50.0, "limit": 0.0},
        {"close": 50.0, "limit": math.nan},
        {"close": 50.0, "stop": 50.0},  # stop must be < the close (no limit)
        {"close": 50.0, "take": 50.0},  # take must be > the close
        {"close": 50.0, "limit": 49.0, "stop": 49.0},
        {"close": 50.0, "limit": 49.0, "take": 49.00004},  # rounds to the limit
        {"close": 50.0, "stop": -1.0},
    ],
)
def test_target_from_close_drops_unusable_prices(kw):
    close = kw.pop("close")
    assert target_from_close("AAA", close, D("0.5"), **kw) is None


def test_target_from_close_rejects_bad_types_and_weights():
    with pytest.raises(TypeError):
        target_from_close("AAA", True, D("0.5"))
    with pytest.raises(TypeError):
        target_from_close("AAA", "50", D("0.5"))
    with pytest.raises(TypeError):
        target_from_close("AAA", 50.0, 0.5)  # a float weight never reaches a Target
    with pytest.raises(ValueError):
        target_from_close("AAA", 50.0, D("0"))


# ---- month_end_closes ---------------------------------------------------------------------


def _jan_to_apr_2019():
    days = sessions(date(2019, 1, 2), date(2019, 4, 30))
    h = hist("AAA", [float(i + 1) for i in range(len(days))], days=days)
    return days, h


def _close_on(days, h, d) -> float:
    return float(h.close[days.index(d)])


def test_month_end_closes_completed_months_only():
    days, h = _jan_to_apr_2019()
    jan, feb, mar = (_close_on(days, h, x) for x in (date(2019, 1, 31), date(2019, 2, 28), date(2019, 3, 29)))
    assert month_end_closes(h, date(2019, 3, 15)).tolist() == [jan, feb]
    assert month_end_closes(h, date(2019, 3, 28)).tolist() == [jan, feb]
    assert month_end_closes(h, date(2019, 3, 29)).tolist() == [jan, feb, mar]  # its last session
    assert month_end_closes(h, date(2019, 3, 30)).tolist() == [jan, feb, mar]  # a Saturday after it
    assert month_end_closes(h, date(2019, 4, 1)).tolist() == [jan, feb, mar]
    assert month_end_closes(h, date(2019, 1, 30)).tolist() == []
    assert month_end_closes(h, date(2018, 12, 31)).tolist() == []
    out = month_end_closes(h, date(2019, 4, 30))
    assert out.dtype == np.float64 and out.tolist() == [jan, feb, mar, _close_on(days, h, date(2019, 4, 30))]


def test_month_end_closes_uses_the_symbols_own_last_bar_of_a_month():
    days, h = _jan_to_apr_2019()
    gappy = drop_days(h, [date(2019, 2, 28)])  # no bar on February's last session
    feb27 = _close_on(days, h, date(2019, 2, 27))
    assert month_end_closes(gappy, date(2019, 3, 15)).tolist()[-1] == feb27
    # A symbol whose bars stop in February: February is complete by mid-March.
    stopped = h.upto(date(2019, 2, 20))
    assert month_end_closes(stopped, date(2019, 3, 15)).tolist() == [
        _close_on(days, h, date(2019, 1, 31)),
        _close_on(days, h, date(2019, 2, 20)),
    ]


def test_month_end_closes_reads_no_later_bar():
    days, h = _jan_to_apr_2019()
    for d in days:
        assert month_end_closes(h, d).tolist() == month_end_closes(h.upto(d), d).tolist(), d
    with pytest.raises(TypeError):
        month_end_closes(h, np.datetime64("2019-03-01"))
    with pytest.raises(TypeError):
        month_end_closes("AAA", date(2019, 3, 1))


# ---- helpers ------------------------------------------------------------------------------


def test_last_close_and_scale_weight():
    days, h = _jan_to_apr_2019()
    assert last_close(h, date(2019, 1, 5)) == _close_on(days, h, date(2019, 1, 4))  # a Saturday
    assert last_close(h, date(2018, 12, 31)) is None
    assert last_close(None, date(2019, 1, 5)) is None
    assert scale_weight(D("0.5"), D("0.333333")) == D("0.166666")  # floored, not rounded
    assert scale_weight(D("0.000001"), D("0.5")) is None  # floors to zero: dropped
    assert scale_weight(D("0.25"), D("1")) == D("0.25")


def test_lazy_prepared_prepares_each_inner_object_once():
    inner, other = ConstAllocator(), ConstAllocator()
    lazy = LazyPrepared({})
    assert lazy.of(inner) == "prepared" and lazy.of(inner) == "prepared" and lazy.of(other) == "prepared"
    assert (inner.prepare_calls, other.prepare_calls) == (1, 1)


# ---- PICKS --------------------------------------------------------------------------------


def picks_set() -> tuple[list[date], dict]:
    days = session_days(260)
    return days, {
        "SAW": hist("SAW", sawtooth(260), days=days),
        "DIP": hist("DIP", dip(dip(uptrend(260), 229), 245, drop=2.0), days=days),
        "GAPPY": drop_days(hist("GAPPY", sawtooth(260, first=70.0), days=days), days[230:233]),
        "LATE": hist("LATE", sawtooth(240, first=40.0, up=0.9, down=0.5), days=days[20:]),
    }


def test_picks_targets_hold_first_then_the_strategys_picks():
    days, history = picks_set()
    d = days[240]
    params = PicksParams(STRATEGY_A, PERMISSIVE)
    members = frozenset(history)
    picks = STRATEGY_A.picks(history, members, d, PERMISSIVE)
    assert len(picks) >= 3
    held = frozenset({picks[1].symbol})
    got = PICKS.targets(history, members, d, held, params)
    w = D("0.25")
    expected = [Target(symbol=picks[1].symbol, weight=w, last=picks[1].last_price)]
    expected += [
        Target(symbol=p.symbol, weight=w, last=p.last_price, limit=p.limit_price, stop=p.sl_price, take=p.tp_price)
        for p in picks
        if p.symbol not in held
    ]
    assert got == tuple(expected)
    assert PICKS.targets(history, members, d, frozenset(), PicksParams(STRATEGY_A, PERMISSIVE, slots=3))[0].weight == D("0.333333")


def test_picks_keeps_a_held_symbol_without_a_bar_at_its_last_close():
    days, history = picks_set()
    d = days[231]  # GAPPY has no bar on days[230..232]
    got = PICKS.targets(history, frozenset(history), d, frozenset({"GAPPY"}), PicksParams(STRATEGY_A, PERMISSIVE))
    assert got[0] == Target(symbol="GAPPY", weight=D("0.25"), last=D(repr(float(history["GAPPY"].upto(d).close[-1]))).quantize(D("0.0001")))
    assert "GAPPY" not in [x.symbol for x in got[1:]]
    with pytest.raises(ValueError, match="held symbol NOPE"):
        PICKS.targets(history, frozenset(history), d, frozenset({"NOPE"}), PicksParams(STRATEGY_A, PERMISSIVE))


def test_picks_skips_held_and_repeated_picks():
    days = session_days(5)
    history = {s: hist(s, [10.0, 11.0, 12.0, 13.0, 14.0], days=days) for s in ("AAA", "BBB", "CCC")}
    pick = lambda s: Pick(s, D("14"), D("13.5"), D("15"), D("12"))  # noqa: E731
    strategy = ListStrategy([pick("BBB"), pick("AAA"), pick("BBB"), pick("CCC")])
    params = PicksParams(strategy, None, slots=2)
    got = PICKS.targets(history, frozenset(), days[-1], frozenset({"AAA"}), params)
    assert [x.symbol for x in got] == ["AAA", "BBB", "CCC"]
    assert got[0].limit is None and got[1].limit == D("13.5") and got[1].stop == D("12") and got[1].take == D("15")
    assert sum(x.weight for x in got) == D("1.5")  # PICKS may exceed 1: the engine's slot cap decides


def test_picks_prepares_the_strategy_once():
    days = session_days(5)
    history = {"AAA": hist("AAA", [10.0, 11.0, 12.0, 13.0, 14.0], days=days)}
    strategy = ListStrategy([])
    params = PicksParams(strategy, None)
    prepared = PICKS.prepare(history)
    for d in days:
        assert PICKS.targets_prepared(prepared, frozenset(), d, frozenset(), params) == ()
    assert strategy.prepare_calls == 1


def test_picks_metadata_and_validation():
    params = PicksParams(STRATEGY_A, PERMISSIVE)
    assert PICKS.lookback(params) == STRATEGY_A.lookback
    assert PICKS.symbols(params) == () and PICKS.holds(params) == ()
    assert PICKS.uses_members(params) is True
    assert params.as_dict() == {"strategy": "A", "slots": "4", **{f"params.{k}": v for k, v in PERMISSIVE.as_dict().items()}}
    with pytest.raises(TypeError):
        PicksParams(PICKS, None)
    with pytest.raises(TypeError):
        PicksParams(STRATEGY_A, PERMISSIVE, slots=True)
    with pytest.raises(ValueError):
        PicksParams(STRATEGY_A, PERMISSIVE, slots=0)
    with pytest.raises(TypeError, match="PicksParams"):
        PICKS.targets({}, frozenset(), date(2019, 1, 2), frozenset(), PERMISSIVE)
    with pytest.raises(TypeError, match="held"):
        PICKS.targets({}, frozenset(), date(2019, 1, 2), {"AAA"}, params)
    with pytest.raises(TypeError, match="LazyPrepared"):
        PICKS.targets_prepared({}, frozenset(), date(2019, 1, 2), frozenset(), params)


def test_picks_p4_identity():
    days, history = picks_set()
    held_sets = [frozenset(), frozenset({"SAW"}), frozenset({"GAPPY", "DIP"})]
    params = [PicksParams(STRATEGY_A, PERMISSIVE), PicksParams(STRATEGY_A, AParams(), slots=2)]
    n = assert_p4_identity(PICKS, history, everyone(history), days[200:], held_sets, params, max_weight_sum=None)
    assert n >= 60


def test_picks_no_lookahead():
    days, history = picks_set()
    held_sets = [frozenset(), frozenset({"GAPPY"})]
    params = [PicksParams(STRATEGY_A, PERMISSIVE)]
    assert assert_no_lookahead(PICKS, history, everyone(history), days[201:260:6], held_sets, params) >= 5


# ---- BLEND --------------------------------------------------------------------------------


def test_blend_scales_sums_and_ranks_by_first_appearance():
    core, sat = ConstAllocator(), ConstAllocator()
    params = BlendParams(
        (
            BlendPart(core, ConstParams((t("SPY", "1", stop="9"),)), D("0.7")),
            BlendPart(sat, ConstParams((t("QQQ", "0.5"), t("SPY", "0.5", limit="9.5"))), D("0.3")),
        )
    )
    got = BLEND.targets({}, frozenset(), date(2019, 1, 2), frozenset(), params)
    # SPY: 0.7 + 0.15 at rank 1 with the core's prices; QQQ: 0.15.
    assert got == (t("SPY", "0.85", stop="9"), t("QQQ", "0.15"))


def test_blend_floors_each_scaled_weight_and_drops_zeros():
    a, b = ConstAllocator(), ConstAllocator()
    params = BlendParams(
        (
            BlendPart(a, ConstParams((t("AAA", "0.5"), t("TINY", "0.000001"))), D("0.333333")),
            BlendPart(b, ConstParams((t("BBB", "1"),)), D("0.5")),
        )
    )
    got = BLEND.targets({}, frozenset(), date(2019, 1, 2), frozenset(), params)
    assert got == (t("AAA", "0.166666"), t("BBB", "0.5"))


def test_blend_parts_do_not_see_each_others_fixed_holdings():
    a, b = ConstAllocator(), ConstAllocator()
    params = BlendParams(
        (
            BlendPart(a, ConstParams((), holds=("SPY",)), D("0.5")),
            BlendPart(b, ConstParams((), holds=("QQQ", "TLT")), D("0.5")),
        )
    )
    held = frozenset({"SPY", "QQQ", "XYZ"})
    BLEND.targets({}, frozenset(), date(2019, 1, 2), held, params)
    BLEND.targets_prepared(BLEND.prepare({}), frozenset(), date(2019, 1, 2), held, params)
    assert a.seen_held == [frozenset({"SPY", "XYZ"})] * 2
    assert b.seen_held == [frozenset({"QQQ", "XYZ"})] * 2


def test_blend_metadata_validation_and_as_dict():
    a, m = ConstAllocator(), MembersFake()
    params = BlendParams(
        (
            BlendPart(a, ConstParams((t("SPY", "1"),), holds=("SPY",), lookback=200), D("0.6")),
            BlendPart(m, ConstParams((t("AAA", "1"), t("BBB", "1")), holds=("BBB",), lookback=60), D("0.4")),
        )
    )
    assert BLEND.lookback(params) == 200
    assert BLEND.symbols(params) == ("AAA", "BBB", "SPY")
    assert BLEND.holds(params) == ("BBB", "SPY")
    assert BLEND.uses_members(params) is True
    assert params.as_dict() == {
        "part1.allocator": "FAKE_CONST",
        "part1.share": "0.6",
        "part1.targets": "SPY",
        "part2.allocator": "FAKE_MEMBERS",
        "part2.share": "0.4",
        "part2.targets": "AAA,BBB",
    }
    part = BlendPart(a, ConstParams(()), D("0.5"))
    with pytest.raises(ValueError, match=">= 2 parts"):
        BlendParams((part,))
    with pytest.raises(ValueError, match="sum"):
        BlendParams((part, BlendPart(a, ConstParams(()), D("0.500001"))))
    with pytest.raises(TypeError):
        BlendParams([part, part])
    with pytest.raises(TypeError):
        BlendPart(STRATEGY_A, None, D("0.5"))
    with pytest.raises(TypeError):
        BlendPart(a, None, 0.5)
    for bad in ("0", "1.000001", "0.0000005", "NaN"):
        with pytest.raises(ValueError):
            BlendPart(a, None, D(bad))


def blend_set() -> tuple[list[date], dict]:
    days = session_days(80)
    return days, {
        "SPY": drop_days(hist("SPY", sawtooth(80, first=250.0), days=days), days[40:42]),
        "AAA": hist("AAA", uptrend(80, first=20.0, step=0.3), days=days),
        "BBB": hist("BBB", sawtooth(80, first=30.0, up=1.0, down=0.9), days=days),
        "CCC": hist("CCC", [50.0 - 0.2 * i for i in range(70)], days=days[10:]),
    }


def _stocks(d: date) -> frozenset[str]:
    return frozenset({"AAA", "BBB", "CCC"})


def test_blend_p4_identity_and_no_lookahead():
    days, history = blend_set()
    params = [
        BlendParams((BlendPart(FIXED, FixedParams((("SPY", D("1")),)), D("0.7")), BlendPart(MOMENTUM, MomentumParams(2), D("0.3")))),
        BlendParams((BlendPart(MOMENTUM, MomentumParams(1), D("0.5")), BlendPart(FIXED, FixedParams((("AAA", D("0.5")), ("SPY", D("0.5")))), D("0.5")))),
    ]
    held_sets = [frozenset(), frozenset({"SPY"}), frozenset({"SPY", "AAA"})]
    assert assert_p4_identity(BLEND, history, _stocks, days[5:], held_sets, params) >= 100
    assert assert_no_lookahead(BLEND, history, _stocks, days[10:80:7], held_sets, params) >= 20


def test_blend_prepares_each_part_once():
    a, b = ConstAllocator(), ConstAllocator()
    params = BlendParams((BlendPart(a, ConstParams(()), D("0.5")), BlendPart(b, ConstParams(()), D("0.5"))))
    prepared = BLEND.prepare({})
    for d in session_days(5):
        BLEND.targets_prepared(prepared, frozenset(), d, frozenset(), params)
    assert (a.prepare_calls, b.prepare_calls) == (1, 1)


# ---- VOLTARGET ----------------------------------------------------------------------------


def _signal(closes: list[float]) -> tuple[list[date], dict]:
    days = session_days(len(closes))
    return days, {"SPY": hist("SPY", closes, days=days)}


def test_voltarget_hand_computed_scale():
    # Returns +0.1 and -0.1: population stdev 0.1; scale = 0.12 / (0.1 × sqrt(252)) = 0.07559289...
    days, history = _signal([100.0, 110.0, 99.0])
    inner = ConstAllocator()
    params = VolTargetParams(inner, ConstParams((t("SPY", "1"), t("TLT", "0.000010"))), n=2)
    got = VOLTARGET.targets(history, frozenset(), days[2], frozenset(), params)
    assert got == (t("SPY", "0.075592"),)  # TLT: 0.00001 × 0.0756 floors to zero and is dropped
    assert vol_scale(history["SPY"], days[2], 2, D("0.12")) == D(repr(0.12 / (0.10000000000000003 * math.sqrt(252))))


def test_voltarget_passes_inner_targets_unchanged_when_it_cannot_or_need_not_scale():
    inner = ConstAllocator()
    targets = (t("SPY", "0.6"), t("TLT", "0.4"))
    params = VolTargetParams(inner, ConstParams(targets), n=2)
    calm_days, calm = _signal([100.0, 100.5, 100.0])  # ~11% annualized < 12%: scale >= 1
    assert VOLTARGET.targets(calm, frozenset(), calm_days[2], frozenset(), params) == targets
    flat_days, flat = _signal([100.0, 100.0, 100.0])  # zero stdev
    assert VOLTARGET.targets(flat, frozenset(), flat_days[2], frozenset(), params) == targets
    short_days, short = _signal([100.0, 110.0, 99.0])
    assert VOLTARGET.targets(short, frozenset(), short_days[1], frozenset(), params) == targets  # 2 bars < n + 1
    assert VOLTARGET.targets({}, frozenset(), short_days[2], frozenset(), params) == targets  # no signal history


def test_voltarget_metadata_validation_and_as_dict():
    inner = MembersFake()
    params = VolTargetParams(inner, ConstParams((t("AAA", "1"),), holds=("AAA",), lookback=10), signal="QQQ", target_vol=D("0.150"), n=20)
    assert VOLTARGET.lookback(params) == 21
    assert VOLTARGET.lookback(VolTargetParams(inner, ConstParams((), lookback=200))) == 200
    assert VOLTARGET.symbols(params) == ("AAA", "QQQ")
    assert VOLTARGET.holds(params) == ("AAA",)
    assert VOLTARGET.uses_members(params) is True
    assert params.as_dict() == {"inner": "FAKE_MEMBERS", "signal": "QQQ", "target_vol": "0.15", "n": "20", "inner.targets": "AAA"}
    with pytest.raises(TypeError):
        VolTargetParams(STRATEGY_A, None)
    with pytest.raises(TypeError):
        VolTargetParams(inner, None, target_vol=0.12)
    with pytest.raises(ValueError):
        VolTargetParams(inner, None, target_vol=D("0"))
    with pytest.raises(ValueError):
        VolTargetParams(inner, None, signal="")
    with pytest.raises(ValueError):
        VolTargetParams(inner, None, n=1)
    with pytest.raises(TypeError):
        VolTargetParams(inner, None, n=True)
    with pytest.raises(TypeError, match="VolTargetParams"):
        VOLTARGET.targets({}, frozenset(), date(2019, 1, 2), frozenset(), None)


def test_voltarget_p4_identity_and_no_lookahead():
    days, history = blend_set()
    params = [
        VolTargetParams(MOMENTUM, MomentumParams(2), n=5),
        VolTargetParams(FIXED, FixedParams((("SPY", D("1")),)), target_vol=D("0.05"), n=10),
    ]
    held_sets = [frozenset(), frozenset({"SPY"})]
    assert assert_p4_identity(VOLTARGET, history, _stocks, days[5:], held_sets, params) >= 100
    assert assert_no_lookahead(VOLTARGET, history, _stocks, days[12:80:7], held_sets, params) >= 15
    # Not vacuous: on most days the overlay really scales the inner weights down.
    d = days[60]
    inner = FIXED.targets(upto(history, d), _stocks(d), d, frozenset(), params[1].inner_params)
    outer = VOLTARGET.targets(upto(history, d), _stocks(d), d, frozenset(), params[1])
    assert outer[0].weight < inner[0].weight


def test_voltarget_prepares_the_inner_allocator_once():
    inner = ConstAllocator()
    days, history = _signal([100.0, 110.0, 99.0, 104.0])
    params = VolTargetParams(inner, ConstParams((t("SPY", "1"),)), n=2)
    prepared = VOLTARGET.prepare(history)
    for d in days:
        VOLTARGET.targets_prepared(prepared, frozenset(), d, frozenset(), params)
    assert inner.prepare_calls == 1


# ---- the kit catches broken allocators ----------------------------------------------------


def _kit_set() -> tuple[list[date], dict]:
    days = session_days(40)
    return days, {
        "UP": hist("UP", uptrend(40), days=days),
        "SAW": hist("SAW", sawtooth(40), days=days),
    }


def test_kit_catches_look_ahead():
    days, history = _kit_set()
    with pytest.raises(AssertionError, match="look-ahead|reads bars after"):
        assert_no_lookahead(PeekAllocator(), history, everyone(history), days[10:12], [frozenset()], [None])
    with pytest.raises(AssertionError, match="reads bars after"):
        assert_p4_identity(PeekAllocator(), history, everyone(history), days[10:12], [frozenset()], [None])


def test_kit_catches_a_broken_prepared_path():
    days, history = _kit_set()
    with pytest.raises(AssertionError, match="P4 identity"):
        assert_p4_identity(ForgetfulAllocator(), history, everyone(history), days[10:12], [frozenset()], [None])
    with pytest.raises(AssertionError, match="P4 identity"):
        assert_no_lookahead(ForgetfulAllocator(), history, everyone(history), days[10:12], [frozenset()], [None])


def test_kit_catches_a_lookback_that_is_too_short():
    days, history = blend_set()

    class Short(type(MOMENTUM)):
        def lookback(self, params):
            return 3  # needs n + 1 = 6

    with pytest.raises(AssertionError, match="lookback too short"):
        assert_p4_identity(Short(), history, _stocks, days[20:25], [frozenset()], [MomentumParams(2)])
    assert assert_p4_identity(MOMENTUM, history, _stocks, days[20:25], [frozenset()], [MomentumParams(2)]) == 5


def test_kit_target_shape_checks():
    days, history = _kit_set()
    d = days[10]
    up = target_from_close("UP", float(history["UP"].close[10]), D("0.6"))
    saw = target_from_close("SAW", float(history["SAW"].close[10]), D("0.6"))
    assert_valid_targets((up,), history, d, frozenset())
    with pytest.raises(AssertionError, match="tuple"):
        assert_valid_targets([up], history, d, frozenset())
    with pytest.raises(AssertionError, match="duplicate"):
        assert_valid_targets((up, up), history, d, frozenset(), max_weight_sum=None)
    with pytest.raises(AssertionError, match="Σ weight"):
        assert_valid_targets((up, saw), history, d, frozenset())
    assert_valid_targets((up, saw), history, d, frozenset(), max_weight_sum=None)
    with pytest.raises(AssertionError, match="last"):
        assert_valid_targets((t("UP", "0.5", last="1"),), history, d, frozenset())
    with pytest.raises(AssertionError, match="no history"):
        assert_valid_targets((t("NOPE", "0.5"),), history, d, frozenset())
    gappy = {"UP": drop_days(history["UP"], [d])}
    kept = target_from_close("UP", float(history["UP"].close[9]), D("0.5"))
    with pytest.raises(AssertionError, match="without a bar"):
        assert_valid_targets((kept,), gappy, d, frozenset())
    assert_valid_targets((kept,), gappy, d, frozenset({"UP"}))


def test_kit_rejects_a_bare_params_value():
    days, history = _kit_set()
    with pytest.raises(TypeError, match="params"):
        assert_p4_identity(FIXED, history, everyone(history), days[:2], [frozenset()], FixedParams((("UP", D("1")),)))
    with pytest.raises(TypeError, match="held_sets"):
        assert_p4_identity(FIXED, history, everyone(history), days[:2], frozenset(), [FixedParams((("UP", D("1")),))])


def test_kit_no_lookahead_uses_prev_session():
    # The data date of session S is prev_session(S): bars dated S itself are already "future".
    days, history = _kit_set()
    s = days[20]
    assert prev_session(s) == days[19]
    assert assert_no_lookahead(FIXED, history, everyone(history), [s], [frozenset()], [FixedParams((("UP", D("1")),))]) == 1
```
**Impact:** +55 tests. Nothing existing changes.

## Verification

**Pre-check:** `engine/.venv` is the worktree's own venv
(`/home/miftah/.worktrees/seer/trade-rules-dev-search/engine/.venv`), never main's. Run
`docker start seer-pg` first.

**Build:** `engine/.venv/bin/python -c "import seer_engine.strategies.allocator as m; print(m.PICKS.id, m.BLEND.id, m.VOLTARGET.id)"`
prints `PICKS BLEND VOLTARGET`.

**Focused tests:** `engine/.venv/bin/pytest engine/tests/test_allocator.py engine/tests/test_indicators.py engine/tests/test_indicators_b.py engine/tests/test_strategy_purity.py -q`
should show all passed, with `test_allocator.py` at 55.

**Full suite:** `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
should be green with 0 skipped. The collected count is (970 + phase 1's added tests) + 55. Log
the passed count in the phase log.

**Frozen set:** `git diff --stat 2546a92 -- engine/src/seer_engine/strategies/base.py engine/src/seer_engine/strategies/a.py engine/src/seer_engine/strategies/a2.py engine/src/seer_engine/strategies/b.py engine/src/seer_engine/strategies/b_model.py engine/src/seer_engine/strategies/__init__.py engine/tests/test_indicators.py engine/tests/test_indicators_b.py engine/tests/test_strategy_purity.py engine/tests/stratkit.py`
must print nothing. `git diff 2546a92 -- engine/src/seer_engine/strategies/indicators.py` should
show only added lines.

**Pre-validated:** this plan's code was executed before it was written down.
- The setup was a scratch copy of the tree at `2546a92`, plus a stub `sim/book.py` that
  implements exactly the phase 1 contract pieces listed under Requires.
- `test_allocator.py` gave 55 passed. `test_indicators.py`, `test_indicators_b.py` and
  `test_strategy_purity.py` also passed.
- If phase 1's real `Target` differs from the contract, for example a positional field order
  or a missing `replace` support, fix the call sites here. Never weaken the tests. All calls
  use keywords.

**Exit criteria:**
- The suite is green with 0 skipped.
- `test_strategy_purity` globs and passes `strategies/allocator.py`.
- The P4 identity and no look-ahead of `PICKS` (over Strategy A), `BLEND` and `VOLTARGET` (over
  the fake inner allocators) pass through `allocatorkit`.
- The kit rejects a look-ahead fake, a broken prepared-path fake and a lookback that is too short.

## Handoffs

- **H1 (phase 1, `sim/book.py`) — settled, plan index D-A:** `step_book` checks Σ weight ≤ 1
  **only when `rules.max_positions is None`** (phase 1 interface decision 1). `PICKS` returns held +
  every non-held pick at `equal_weight(slots)`, uncapped; with `V0_BOOK`'s cap of 4 the engine
  picks the entrants, exactly as `size_picks` does. Truncating in `PICKS` would break phase 3's
  V0_BOOK parity, so it is not done.
- **H2 (to phase 3, `book_runner.py`):**
  - Pass `held=book.held()` minus `rules.idle_symbol` (plan index D-J), which must be a
    `frozenset`.
  - For `prepared=`, pass the allocator's own `prepare(history)`. For PICKS/BLEND/VOLTARGET it
    is a `LazyPrepared`, cheap to build; the inner prepares run lazily on the first decision
    session.
  - `PICKS` with `V0_BOOK` relies on `max_positions=4` to choose entrants (H1).
  - Phase 3's `run_rules` can rely on Decision 10: `Allocator` and `Strategy` instances are
    disjoint under `isinstance`.
- **H3 (to phases 5–8):**
  - Use `target_from_close` for every target, `month_end_closes` for F1 `month_sma`, and
    `return_window` for momentum.
  - Use `scale_weight` (floor, drop at zero) for any multiplicative weight, such as F6
    `inverse_vol`.
  - Call `assert_p4_identity` and `assert_no_lookahead` with `params` as a **list**, and assert
    a minimum non-empty count.
  - Declare a `lookback` that covers every bar read, including month-ends (`check_lookback`
    enforces it).
- **H4 (to phases 9, 10 and 11):** `PicksParams`, `BlendParams` and `VolTargetParams` each have
  an `as_dict()` with flattened, prefixed keys in a fixed order (Decision 9). Registry params for
  F1/ROT/FAC/F7 must also implement `as_dict()`, as the index already says, because the overlays
  embed it. Encoding (plan index D-F): a `(symbol, n)` pair renders `"SYM:n"`, `None` renders
  `"none"`, a tuple of symbols renders comma-joined and sorted. Phase 10 renders `as_dict()`;
  phase 11's `candidate_digest` walks the dataclass fields instead.
- **H5 (to phases 9 and 12, plan index D-D):** every `prepare(history)` here is param-independent
  (`LazyPrepared` keys inner objects by identity), so one prepared value per `allocator.id` is
  correct for every candidate that uses the singleton `PICKS`, `BLEND` or `VOLTARGET`, whatever
  inner objects its params name.
- **Not done here (out of scope):** `strategies/__init__.py` does not re-export the allocator
  names. The scope forbids touching it, and every consumer imports
  `seer_engine.strategies.allocator` directly. Re-exporting is a later, optional cleanup.

## Rollback

Every change in this phase is additive:
- Delete `engine/src/seer_engine/strategies/allocator.py`, `engine/tests/allocatorkit.py` and
  `engine/tests/test_allocator.py`.
- Remove the `return_window` block from `indicators.py`.

Or simply `git revert` the phase commit. No other phase's file is touched. Phases 3 and 5–12
import this module, so reverting it after they land requires reverting them too.
