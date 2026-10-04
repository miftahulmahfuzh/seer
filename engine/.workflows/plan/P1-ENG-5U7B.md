> Adopted from `TRADE_RULES_DEV_SEARCH_PLAN.md` phase 8. Source: `.workflows/plan/trade-rules-dev-search/phase-8.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 8: Family F7: longer-horizon mean reversion

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R3 — no look-ahead and P4 identity for the F7 family; the prepared and single-window paths agree
**Depends on:** Phase 2 (and, through it, Phase 1)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

`seer_engine.strategies.f_swing` exists and provides `SwingParams` and the `SWING` allocator (id `"F7"`). F7 takes A's idea (buy the oversold in an uptrend) and runs it under longer-horizon levers: no TP by default, a signal exit at the next open, and a time stop set by the rules. It is a new candidate family (handover D12), not Strategy A re-run. F7 implements the phase-2 `Allocator` protocol exactly. Its vectorized `prepare` path returns bit-identical results to its single-window path, and the tests prove P4 identity and no look-ahead.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates** (all in `engine/src/seer_engine/strategies/f_swing.py`, a new flat module, so the purity glob covers it):
- `SwingParams` is a frozen dataclass with slots. Its fields, in order and with the exact defaults from the index contract: `slots=4`, `rsi_n=2`, `rsi_max=10.0`, `sma_n=200`, `entry="dip"`, `limit_atr=Decimal("0.5")`, `stop_atr=Decimal("2.5")`, `take_atr=None`, `exit_sma=5`, `exit_rsi=None`, `min_dollar_volume=20_000_000.0`, `market_trend=None`.
  - `__post_init__` validates every field. A wrong type raises `TypeError` and a bad range raises `ValueError`. Ints given for `rsi_max`, `exit_rsi` and `min_dollar_volume` are coerced to float, like `AParams`.
  - `as_dict() -> dict[str, str]` returns the 12 keys in field order. Numbers are plain decimals (A's `_plain` convention). `None` is written as `"none"`, and `market_trend` is written as `"SPY:200"`.
- `SwingAllocator`, with `id = "F7"`, and its singleton `SWING = SwingAllocator()`.
  - `lookback(p) = swing_lookback(p)`.
  - `symbols(p)` is `(market_trend[0],)`, or `()` when there is no market trend.
  - `holds(p)` is `()`.
  - `uses_members(p)` is `True`.
  - It also has `targets`, `prepare` and `targets_prepared`.
- Public helpers, used by the tests:
  - constants `WINDOW = 200`, `ATR_N = 14`, `DV_N = 20`, `MAX_SLOTS = 100`, `PREPARED_RSI_N = 2`, `PREPARED_SMA_N = 200`, `PREPARED_EXIT_SMA = 5`;
  - `SwingEntry = Literal["dip", "close"]`;
  - `SwingFeatures`;
  - `features_at(history, symbols, data_date, params)`;
  - `SwingPrepared` (with `covers`, `feature`, `features_on`);
  - `prepare_swing`;
  - `member_window`, `swing_lookback`;
  - `has_setup`, `has_exit_signal`;
  - `entry_target`, `rank_entries`;
  - `trend_on`.

**Signature changes:** none.

**Requires (from earlier phases):**
- From Phase 1, exported from `seer_engine.sim`: `Target` and `equal_weight`. `q` is already exported.
- From Phase 2:
  - `seer_engine.strategies.allocator.target_from_close(symbol, close: float, weight: Decimal, *, limit: float | None = None, stop: float | None = None, take: float | None = None) -> Target | None`. It returns `None` when a price is `<= 0` after rounding, or when `stop < (limit or last) < take` fails. It applies **no** constraint between `limit` and `last` (F7's `entry="close"` passes `limit == last`).
  - `seer_engine.strategies.allocator.Allocator`, a `runtime_checkable` Protocol.
  - `tests/allocatorkit.py` (plan index D-E, phase 2's kit is canonical): `assert_p4_identity(allocator, history, members_fn, dates, held_sets, params, *, max_weight_sum=Decimal(1), check_lookback=True) -> int` and `assert_no_lookahead(allocator, history, members_fn, sessions, held_sets, params) -> int`. `members_fn` is a callable of the data date; `held_sets` and `params` are non-empty lists (the same held sets on every date); both return the count of non-empty results. Only `test_kit_identity_and_no_look_ahead` uses the kit. Every other test in this file is self-contained and proves the same property inline, including the date-dependent `held_path`.

**Leaves alone (owned by others):**
- `strategies/allocator.py`, `strategies/indicators.py` and `tests/allocatorkit.py` (Phase 2).
- `strategies/a.py`, which is read for conventions only and **not imported**: constants and `_plain` are re-declared locally.
- `strategies/__init__.py`: F7 is **not** added to the package exports. Consumers import `seer_engine.strategies.f_swing` directly.
- `sim/*` (Phase 1).
- `backtest/*` (Phases 3, 9–12).
- The other families: `f_index.py`, `f_rotation.py` and `f_factor.py`.

## Decisions taken in this phase (ambiguities resolved)

1. **The prepared path covers only the default periods.**
   - Why: `prepare(history)` takes no params, and Wilder RSI and ATR depend on the window length.
   - `prepare_swing` rolls one fixed column set: window 200, RSI(2), SMA(200), SMA(5), ATR(14) and DV(20).
   - `targets_prepared` uses those columns only when `SwingPrepared.covers(params)` holds. That means `member_window == 200`, `rsi_n == 2`, `sma_n == 200` and `exit_sma` is either 5 or None.
   - For any other params it calls the single-window `targets` on `prepared.history`. The P4 identity therefore holds for **every** params value by construction.
   - Every registry candidate (index rows 46–52 and 54) uses the default periods, so the dev run always takes the vectorized path.
2. **The member window** is `member_window(p) = max(200, sma_n, rsi_n + 1, exit_sma or 1)`. Every member indicator reads exactly these last bars through `data_date`. That matches A's 200-bar convention, so the RSI(2) seed equals A's.
   - `Allocator.lookback(p) = max(member_window(p), market_trend n)`.
   - The trend SMA reads only its own last `n` closes and never widens member windows.
3. **Entry prices are Decimal, as in A, and pass through `target_from_close` as floats.**
   - `last = to_decimal(close)`, `atr = to_decimal(ATR14)`.
   - `limit = q(last − limit_atr·atr)` for the dip entry, or `last` for the close entry.
   - `stop = q(limit − stop_atr·atr)` and `take = q(limit + take_atr·atr)`, each computed from the **rounded** limit.
   - The three prices are then handed to `target_from_close` as `float(Decimal)`. A 4-dp Decimal survives float → repr → Decimal → `q` exactly (probed on 200,000 random values in ±1e6: 0 mismatches).
   - So F7 gets A's exact bracket arithmetic and still uses the shared helper the scope requires. If Phase 2's helper also accepts `Decimal`, passing the Decimals directly is behaviour-identical.
4. **Held symbols.**
   - A held symbol is **kept** unless its exit signal fires on `data_date`.
   - "Nothing to decide on" also means keep. This covers a held symbol with no bar on `data_date`, one with too few bars for the member window, and one that is no longer a member.
   - A kept target has no limit, stop or take. Its `last` is `q(to_decimal(most recent close <= data_date))`, as in `PicksAllocator`.
   - A held symbol that is absent from `history`, or has no close on or before `data_date`, is not returned, so the engine signal-exits it (or sets `exit_pending`). In practice this cannot happen.
   - A held symbol is never a "new" candidate on the same night, even after an exit signal.
5. **Kept are capped at `slots`.** Kept targets are truncated to the first `slots` in symbol order, so that Σ weight ≤ 1 always holds and `step_book` never raises.
   - This can only matter when `held` holds more F7 symbols than `slots`. That happens if a book's holdings come from elsewhere, such as an overlap in a BLEND part, or a test.
6. **The market-trend gate**: `trend_on` is True when `market_trend` is None. Otherwise the gate symbol needs a bar dated `data_date`, at least `n` bars, and `close > SMA(n)`, all strict.
   - A missing symbol or too short a history counts as **shut**: no new entries, and held symbols are still kept.
   - The gate is evaluated only when a slot is free.
7. **An exit-signal configuration is allowed to be empty.** With `exit_sma=None` and `exit_rsi=None`, positions leave only by stop, take or time stop.
   - `exit_rsi` must lie in `[0, 100)`. At 100, `RSI > 100` could never fire.
8. **The setup also requires a finite close and a finite ATR.** A NaN ATR would make `to_decimal` raise. Comparisons against a NaN SMA, RSI or DV are already False.
9. **`SwingFeatures.exit_sma` is `float | None`, not NaN.**
   - Why: NaN would break dataclass equality (`nan != nan`) and so break the bit-identity test.
   - It is `None` whenever `params.exit_sma is None`, on both paths.
10. **`as_dict` encoding**: `"none"` for `None`, and `"SYM:n"` for `market_trend`. It is the shared encoding of every family (plan index D-F). Phase 10 renders `as_dict()`; phase 11's `candidate_digest` walks the dataclass fields instead.
11. **`MAX_SLOTS = 100`**: `slots` is validated to `1..100`, which keeps `equal_weight(slots)` well away from `WEIGHT_QUANTUM`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/f_swing.py` | create (new file, line 1) | The whole F7 family: params, features, the prepared columns, decisions and the allocator |
| `engine/tests/test_f_swing.py` | create (new file, line 1) | 87 tests: params, features, setup and exit (each condition alone), 4-dp prices, invalid orderings, ranking, held and slots, the trend gate, P4 identity, no look-ahead, and the kit checkers |

No existing file is modified.

## Implementation Steps

### Step 1: Create the F7 module
**File:** `engine/src/seer_engine/strategies/f_swing.py:1` (new)
**Change:** Create the module below verbatim. It is pure. Its imports are `math`, `collections.abc`, `dataclasses`, `datetime`, `decimal`, `types.MappingProxyType`, `typing`, `numpy`, `seer_engine.prices`, `seer_engine.sim`, `seer_engine.strategies.allocator`, `.base` and `.indicators`. It has no clock, randomness, logging, print or open. It sits flat in `strategies/`, so `tests/test_strategy_purity.py` picks it up with no edit.
**Code:**
```python
"""Family F7: longer-horizon mean reversion over index members (P7a, handover §4.B F7, D12).

A's idea (buy the oversold in an uptrend) under other trade levers: a longer horizon (the
rules' time stop, 10 or 20 sessions), no take-profit by default, and a signal exit at the next
open. This is a NEW candidate family under D12, never Strategy A re-run: it shares A's
indicator conventions (``strategies.indicators``), not A's module.

New entry, on ``data_date`` (all strict), for index members not already held:
    RSI(rsi_n) < rsi_max,  close > SMA(sma_n),  20-day mean close×volume > min_dollar_volume,
    and, when ``market_trend = (M, n)`` is set, M's close > SMA(n) of M's closes on data_date.
Entry target, Decimal at 4 dp (``sim.q``), from ``last = to_decimal(close)``, ``atr = to_decimal(ATR14)``:
    limit = q(last − limit_atr·atr)   (entry "dip")   or   last   (entry "close")
    stop  = q(limit − stop_atr·atr)   (None when stop_atr is None)
    take  = q(limit + take_atr·atr)   (None when take_atr is None)
built by ``allocator.target_from_close``, which drops the candidate when a price is <= 0 after
rounding or the ordering stop < limit < take fails (A's ``_bracket`` convention).

Held symbols: kept as a price-less target at weight ``equal_weight(slots)`` unless the exit
signal fires on data_date: close > SMA(exit_sma), or RSI(rsi_n) > exit_rsi (each strict, each
optional). A held symbol with no bar dated data_date, with too little history, or no longer an
index member is kept: there is nothing to decide on, and the engine's stop and time stop still
apply. Kept symbols come first, in symbol order (at most ``slots`` of them), then new entries by
(RSI ascending, symbol) until there are ``slots`` targets. The market-trend gate stops new
entries only.

Every member indicator is a function of the symbol's last ``member_window(params)`` bars
through data_date (Wilder recursions seeded inside that window), so ``targets`` and
``targets_prepared`` compute bit-identical floats. ``prepare`` rolls the indicator columns once
for the prepared periods (window 200, RSI(2), SMA(200), SMA(5): the defaults, which every
registry candidate uses); params with other periods are served by the single-window path on the
prepared history, so the P4 identity holds for every params value.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from seer_engine.prices import to_decimal
from seer_engine.sim import Target, equal_weight, q
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    rolling,
    sma_window,
    wilder_atr_window,
    wilder_rsi_window,
)

WINDOW = 200  # the minimum member window (A's LOOKBACK convention)
ATR_N = 14
DV_N = 20
MAX_SLOTS = 100
PREPARED_RSI_N = 2  # the periods prepare() rolls; other periods use the single-window path
PREPARED_SMA_N = 200
PREPARED_EXIT_SMA = 5

SwingEntry = Literal["dip", "close"]
_ENTRIES: tuple[str, ...] = ("dip", "close")


# --------------------------------------------------------------------------- params


def _plain(x: float | int | Decimal) -> str:
    """``x`` as a plain decimal string without trailing zeros: 10.0 -> "10", Decimal("0.50") -> "0.5"."""
    d = Decimal(repr(x)) if isinstance(x, float) else Decimal(x)
    return format(d.normalize(), "f")


def _check_int(name: str, v: object, lo: int, hi: int | None = None) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo or (hi is not None and v > hi):
        bound = f">= {lo}" if hi is None else f"in {lo}..{hi}"
        raise ValueError(f"{name} must be {bound}, got {v}")
    return v


def _check_float(name: str, v: object) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite, got {v!r}")
    return f


def _check_decimal(name: str, v: object) -> Decimal:
    if not isinstance(v, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(v).__name__}")
    if not v.is_finite():
        raise ValueError(f"{name} must be finite, got {v!r}")
    return v


@dataclass(frozen=True, slots=True)
class SwingParams:
    """F7's fixed parameters. Defaults are the registry's base candidate (F7-RSI2-T20-DIP)."""

    slots: int = 4  # weight equal_weight(slots); kept + new <= slots (self-capped)
    rsi_n: int = 2
    rsi_max: float = 10.0  # setup: RSI(rsi_n) < rsi_max (strict)
    sma_n: int = 200  # setup: close > SMA(sma_n) (strict)
    entry: SwingEntry = "dip"  # Target.limit: dip = last − limit_atr × ATR14; close = last
    limit_atr: Decimal = Decimal("0.5")
    stop_atr: Decimal | None = Decimal("2.5")  # Target.stop = limit − stop_atr × ATR14 (None: no stop)
    take_atr: Decimal | None = None  # Target.take = limit + take_atr × ATR14 (None: no TP)
    exit_sma: int | None = 5  # signal exit when close > SMA(exit_sma) (strict)
    exit_rsi: float | None = None  # ... or when RSI(rsi_n) > exit_rsi (strict)
    min_dollar_volume: float = 20_000_000.0  # setup: 20-day mean close×volume > this (strict)
    market_trend: tuple[str, int] | None = None  # no NEW entries unless M close > SMA(n) of M; held kept

    def __post_init__(self) -> None:
        _check_int("slots", self.slots, 1, MAX_SLOTS)
        _check_int("rsi_n", self.rsi_n, 1)
        _check_int("sma_n", self.sma_n, 1)
        if self.exit_sma is not None:
            _check_int("exit_sma", self.exit_sma, 1)
        for name in ("rsi_max", "min_dollar_volume"):
            object.__setattr__(self, name, _check_float(name, getattr(self, name)))
        if not 0.0 < self.rsi_max <= 100.0:
            raise ValueError(f"rsi_max must be in (0, 100], got {self.rsi_max}")
        if self.min_dollar_volume < 0.0:
            raise ValueError(f"min_dollar_volume must be >= 0, got {self.min_dollar_volume}")
        if self.exit_rsi is not None:
            object.__setattr__(self, "exit_rsi", _check_float("exit_rsi", self.exit_rsi))
            if not 0.0 <= self.exit_rsi < 100.0:
                raise ValueError(f"exit_rsi must be in [0, 100), got {self.exit_rsi}")
        if not isinstance(self.entry, str):
            raise TypeError(f"entry must be a str, got {type(self.entry).__name__}")
        if self.entry not in _ENTRIES:
            raise ValueError(f"entry must be one of {_ENTRIES}, got {self.entry!r}")
        if _check_decimal("limit_atr", self.limit_atr) < 0:
            raise ValueError(f"limit_atr must be >= 0, got {self.limit_atr}")
        for name in ("stop_atr", "take_atr"):
            v = getattr(self, name)
            if v is not None and _check_decimal(name, v) <= 0:
                raise ValueError(f"{name} must be > 0 or None, got {v}")
        if self.market_trend is not None:
            t = self.market_trend
            if not isinstance(t, tuple) or len(t) != 2:
                raise TypeError(f"market_trend must be a (symbol, n) tuple or None, got {t!r}")
            if not isinstance(t[0], str) or not t[0]:
                raise TypeError(f"market_trend symbol must be a non-empty str, got {t[0]!r}")
            _check_int("market_trend n", t[1], 1)

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""

        def opt(v: float | int | Decimal | None) -> str:
            return "none" if v is None else _plain(v)

        trend = "none" if self.market_trend is None else f"{self.market_trend[0]}:{self.market_trend[1]}"
        return {
            "slots": _plain(self.slots),
            "rsi_n": _plain(self.rsi_n),
            "rsi_max": _plain(self.rsi_max),
            "sma_n": _plain(self.sma_n),
            "entry": self.entry,
            "limit_atr": _plain(self.limit_atr),
            "stop_atr": opt(self.stop_atr),
            "take_atr": opt(self.take_atr),
            "exit_sma": opt(self.exit_sma),
            "exit_rsi": opt(self.exit_rsi),
            "min_dollar_volume": _plain(self.min_dollar_volume),
            "market_trend": trend,
        }


def _params(params: Any) -> SwingParams:
    if not isinstance(params, SwingParams):
        raise TypeError(f"params must be SwingParams, got {type(params).__name__}")
    return params


def _held(held: Any) -> frozenset[str]:
    if not isinstance(held, AbstractSet):
        raise TypeError(f"held must be a set of symbols, got {type(held).__name__}")
    return frozenset(held)


def member_window(params: SwingParams) -> int:
    """Bars each member symbol needs through data_date; every member indicator reads exactly these."""
    n = max(WINDOW, params.sma_n, params.rsi_n + 1)
    if params.exit_sma is not None:
        n = max(n, params.exit_sma)
    return n


def swing_lookback(params: SwingParams) -> int:
    """``Allocator.lookback``: the member window, or the market-trend SMA when that is longer."""
    n = member_window(params)
    if params.market_trend is not None:
        n = max(n, params.market_trend[1])
    return n


# --------------------------------------------------------------------------- features


@dataclass(frozen=True, slots=True)
class SwingFeatures:
    """F7's indicator values for one symbol at one ``data_date`` close."""

    symbol: str
    data_date: date
    close: float
    sma: float  # SMA(sma_n)
    exit_sma: float | None  # SMA(exit_sma); None when params.exit_sma is None
    rsi: float  # Wilder RSI(rsi_n)
    atr: float  # Wilder ATR(14)
    dollar_volume: float  # 20-day mean close × volume


def features_at(
    history: Mapping[str, History], symbols: Iterable[str], data_date: date, params: SwingParams
) -> tuple[SwingFeatures, ...]:
    """Features of every symbol in ``symbols`` eligible on ``data_date``, sorted by symbol.

    Eligible: in ``history``, a bar dated ``data_date``, and at least ``member_window(params)``
    bars through it. Computed on exactly those last bars; later bars are never read.
    """
    p = _params(params)
    as_day(data_date)
    w = member_window(p)
    names: list[str] = []
    rows: list[int] = []
    for symbol in sorted(set(symbols)):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < w:
            continue
        names.append(symbol)
        rows.append(i)
    if not names:
        return ()

    def stack(field: str) -> np.ndarray:
        return np.stack([getattr(history[s], field)[i + 1 - w : i + 1] for s, i in zip(names, rows, strict=True)])

    close, high, low, volume = stack("close"), stack("high"), stack("low"), stack("volume")
    sma = sma_window(close, p.sma_n)
    exit_sma = None if p.exit_sma is None else sma_window(close, p.exit_sma)
    rsi = wilder_rsi_window(close, p.rsi_n)
    atr = wilder_atr_window(high, low, close, ATR_N)
    dv = mean_dollar_volume_window(close, volume, DV_N)
    last = close[:, -1]
    return tuple(
        SwingFeatures(
            s,
            data_date,
            float(last[k]),
            float(sma[k]),
            None if exit_sma is None else float(exit_sma[k]),
            float(rsi[k]),
            float(atr[k]),
            float(dv[k]),
        )
        for k, s in enumerate(names)
    )


@dataclass(frozen=True, slots=True, eq=False)
class SwingPrepared:
    """F7's param-independent features for every (symbol, date) with ``WINDOW`` bars through it.

    Columnar, ordered by (date, symbol), rolled for the prepared periods (RSI(2), SMA(200),
    SMA(5), ATR(14), DV(20)) over a ``WINDOW``-bar window. ``history`` is kept for held symbols'
    last closes, the market-trend gate and params the columns do not cover.
    """

    history: Mapping[str, History]
    symbols: tuple[str, ...]  # sorted; ``sym`` indexes into it
    index: Mapping[str, int]  # symbol -> its position in ``symbols``
    dates: np.ndarray  # datetime64[D], ascending
    sym: np.ndarray  # int64; ascending within one date
    close: np.ndarray  # float64 columns, one row per (symbol, date)
    sma: np.ndarray
    exit_sma: np.ndarray
    rsi: np.ndarray
    atr: np.ndarray
    dollar_volume: np.ndarray

    def covers(self, params: SwingParams) -> bool:
        """True when the rolled columns are exactly what ``features_at`` computes for ``params``."""
        p = _params(params)
        return (
            member_window(p) == WINDOW
            and p.rsi_n == PREPARED_RSI_N
            and p.sma_n == PREPARED_SMA_N
            and p.exit_sma in (None, PREPARED_EXIT_SMA)
        )

    def _rows(self, data_date: date) -> tuple[int, int]:
        day = as_day(data_date)
        lo = int(np.searchsorted(self.dates, day, side="left"))
        hi = int(np.searchsorted(self.dates, day, side="right"))
        return lo, hi

    def _features(self, k: int, data_date: date, params: SwingParams) -> SwingFeatures:
        return SwingFeatures(
            self.symbols[int(self.sym[k])],
            data_date,
            float(self.close[k]),
            float(self.sma[k]),
            None if params.exit_sma is None else float(self.exit_sma[k]),
            float(self.rsi[k]),
            float(self.atr[k]),
            float(self.dollar_volume[k]),
        )

    def feature(self, symbol: str, data_date: date, params: SwingParams) -> SwingFeatures | None:
        """``symbol``'s row on ``data_date``, or None when it has none (requires ``covers(params)``)."""
        k = self.index.get(symbol)
        if k is None:
            return None
        lo, hi = self._rows(data_date)
        j = lo + int(np.searchsorted(self.sym[lo:hi], k, side="left"))
        if j < hi and int(self.sym[j]) == k:
            return self._features(j, data_date, params)
        return None

    def features_on(self, data_date: date, params: SwingParams) -> tuple[SwingFeatures, ...]:
        """Every row on ``data_date``, sorted by symbol (== ``features_at`` over every symbol)."""
        if not self.covers(params):
            raise ValueError("params use periods the prepared columns do not cover")
        lo, hi = self._rows(data_date)
        return tuple(self._features(k, data_date, params) for k in range(lo, hi))


def _readonly(arr: np.ndarray) -> np.ndarray:
    arr.setflags(write=False)
    return arr


def prepare_swing(history: Mapping[str, History]) -> SwingPrepared:
    """Rolling F7 features over every symbol's whole history (see ``SwingPrepared``)."""
    frozen = MappingProxyType(dict(sorted(history.items())))
    symbols = tuple(frozen)
    index = MappingProxyType({s: k for k, s in enumerate(symbols)})
    keys = ("dates", "sym", "close", "sma", "exit_sma", "rsi", "atr", "dv")
    parts: dict[str, list[np.ndarray]] = {key: [] for key in keys}
    start = WINDOW - 1
    for k, symbol in enumerate(symbols):
        h = frozen[symbol]
        if len(h) < WINDOW:
            continue
        parts["dates"].append(h.dates[start:])
        parts["sym"].append(np.full(len(h) - start, k, dtype=np.int64))
        parts["close"].append(h.close[start:])
        parts["sma"].append(rolling(sma_window, h.close, window=WINDOW, n=PREPARED_SMA_N)[start:])
        parts["exit_sma"].append(rolling(sma_window, h.close, window=WINDOW, n=PREPARED_EXIT_SMA)[start:])
        parts["rsi"].append(rolling(wilder_rsi_window, h.close, window=WINDOW, n=PREPARED_RSI_N)[start:])
        parts["atr"].append(rolling(wilder_atr_window, h.high, h.low, h.close, window=WINDOW, n=ATR_N)[start:])
        parts["dv"].append(rolling(mean_dollar_volume_window, h.close, h.volume, window=WINDOW, n=DV_N)[start:])
    if not parts["dates"]:
        empty = _readonly(np.empty(0, dtype=np.float64))
        return SwingPrepared(
            frozen,
            symbols,
            index,
            _readonly(np.empty(0, dtype="datetime64[D]")),
            _readonly(np.empty(0, dtype=np.int64)),
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
        )
    dates = np.concatenate(parts["dates"])
    order = np.argsort(dates, kind="stable")  # symbols were appended in sorted order

    def col(key: str) -> np.ndarray:
        return _readonly(np.concatenate(parts[key])[order])

    return SwingPrepared(
        frozen,
        symbols,
        index,
        col("dates"),
        col("sym"),
        col("close"),
        col("sma"),
        col("exit_sma"),
        col("rsi"),
        col("atr"),
        col("dv"),
    )


# --------------------------------------------------------------------------- decisions


def has_setup(f: SwingFeatures, params: SwingParams) -> bool:
    """The entry setup (each comparison strict); a non-finite close or ATR never qualifies."""
    return (
        f.rsi < params.rsi_max
        and f.close > f.sma
        and f.dollar_volume > params.min_dollar_volume
        and math.isfinite(f.close)
        and math.isfinite(f.atr)
    )


def has_exit_signal(f: SwingFeatures, params: SwingParams) -> bool:
    """close > SMA(exit_sma), or RSI(rsi_n) > exit_rsi (each strict, each only when set)."""
    if params.exit_sma is not None and f.exit_sma is not None and f.close > f.exit_sma:
        return True
    return params.exit_rsi is not None and f.rsi > params.exit_rsi


def entry_target(f: SwingFeatures, params: SwingParams) -> Target | None:
    """The new-entry ``Target`` (weight ``equal_weight(slots)``), or None for an invalid bracket.

    Prices are computed in Decimal at 4 dp exactly as A's bracket, then handed to
    ``target_from_close`` as floats: a 4-dp Decimal survives float -> repr -> Decimal exactly.
    """
    last = to_decimal(f.close)
    atr = to_decimal(f.atr)
    limit = last if params.entry == "close" else q(last - params.limit_atr * atr)
    stop = None if params.stop_atr is None else q(limit - params.stop_atr * atr)
    take = None if params.take_atr is None else q(limit + params.take_atr * atr)
    return target_from_close(
        f.symbol,
        f.close,
        equal_weight(params.slots),
        limit=float(limit),
        stop=None if stop is None else float(stop),
        take=None if take is None else float(take),
    )


def rank_entries(candidates: Iterable[SwingFeatures], params: SwingParams, free: int) -> tuple[Target, ...]:
    """The first ``free`` valid entries among ``candidates`` passing the setup, by (RSI, symbol)."""
    ranked: list[tuple[float, str, Target]] = []
    for f in candidates:
        if not has_setup(f, params):
            continue
        t = entry_target(f, params)
        if t is not None:
            ranked.append((f.rsi, f.symbol, t))
    ranked.sort(key=lambda r: (r[0], r[1]))
    return tuple(t for _, _, t in ranked[: max(free, 0)])


def trend_on(history: Mapping[str, History], trend: tuple[str, int] | None, data_date: date) -> bool:
    """The market-trend gate: True when unset; else M has a bar on data_date, >= n bars, close > SMA(n)."""
    if trend is None:
        return True
    symbol, n = trend
    h = history.get(symbol)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    window = h.close[i + 1 - n : i + 1].reshape(1, n)
    return float(h.close[i]) > float(sma_window(window, n)[0])


def _last_close(h: History, data_date: date) -> float | None:
    j = int(np.searchsorted(h.dates, as_day(data_date), side="right")) - 1
    return float(h.close[j]) if j >= 0 else None


def _kept(
    held: frozenset[str],
    history: Mapping[str, History],
    data_date: date,
    params: SwingParams,
    feature_of: Callable[[str], SwingFeatures | None],
) -> list[Target]:
    """Held symbols F7 still wants, in symbol order, at most ``slots``, as price-less targets."""
    weight = equal_weight(params.slots)
    out: list[Target] = []
    for symbol in sorted(held):
        if len(out) == params.slots:
            break
        f = feature_of(symbol)
        if f is not None:
            if has_exit_signal(f, params):
                continue
            close: float | None = f.close
        else:
            h = history.get(symbol)
            close = None if h is None else _last_close(h, data_date)
        if close is None or not math.isfinite(close):
            continue
        t = target_from_close(symbol, close, weight)
        if t is not None:
            out.append(t)
    return out


def _decide(
    kept: list[Target],
    candidates: Callable[[], Iterable[SwingFeatures]],
    gate: Callable[[], bool],
    params: SwingParams,
) -> tuple[Target, ...]:
    free = params.slots - len(kept)
    if free <= 0 or not gate():
        return tuple(kept)
    return tuple(kept) + rank_entries(candidates(), params, free)


# --------------------------------------------------------------------------- allocator


class SwingAllocator:
    """F7 behind the ``Allocator`` protocol."""

    id = "F7"

    def lookback(self, params: Any) -> int:
        return swing_lookback(_params(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _params(params)
        return () if p.market_trend is None else (p.market_trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _params(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _params(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _params(params)
        held_set = _held(held)
        feats = {f.symbol: f for f in features_at(history, set(members) | held_set, data_date, p)}
        kept = _kept(held_set, history, data_date, p, feats.get)
        return _decide(
            kept,
            lambda: [f for s, f in feats.items() if s in members and s not in held_set],
            lambda: trend_on(history, p.market_trend, data_date),
            p,
        )

    def prepare(self, history: Mapping[str, History]) -> SwingPrepared:
        return prepare_swing(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, SwingPrepared):
            raise TypeError(f"prepared must be SwingPrepared, got {type(prepared).__name__}")
        p = _params(params)
        if not prepared.covers(p):
            return self.targets(prepared.history, members, data_date, held, p)
        held_set = _held(held)
        as_day(data_date)
        kept = _kept(held_set, prepared.history, data_date, p, lambda s: prepared.feature(s, data_date, p))

        def candidates() -> list[SwingFeatures]:
            lo, hi = prepared._rows(data_date)
            window = slice(lo, hi)
            mask = (
                (prepared.close[window] > prepared.sma[window])
                & (prepared.rsi[window] < p.rsi_max)
                & (prepared.dollar_volume[window] > p.min_dollar_volume)
            )
            out: list[SwingFeatures] = []
            for j in np.flatnonzero(mask):
                k = lo + int(j)
                symbol = prepared.symbols[int(prepared.sym[k])]
                if symbol in members and symbol not in held_set:
                    out.append(prepared._features(k, data_date, p))
            return out

        return _decide(kept, candidates, lambda: trend_on(prepared.history, p.market_trend, data_date), p)


SWING = SwingAllocator()
```
**Impact:** this is a new module, so nothing existing changes. `tests/test_strategy_purity.py` now also imports `seer_engine.strategies.f_swing` in a fresh interpreter. That import needs Phase 1's `Target` and `equal_weight` and Phase 2's `allocator.target_from_close`.

### Step 2: Create the tests
**File:** `engine/tests/test_f_swing.py:1` (new)
**Change:** Create the test file below verbatim. It uses the existing `tests/stratkit.py` (`hist`, `uptrend`, `dip`, `sawtooth`, `session_days`, `mutate_from`, `truncate_before`, `drop_days`) and `tests/simkit.py` (`P`). It also uses Phase 2's `tests/allocatorkit.py`, but only in the last test.
Hand-computed anchors:
- The `DIP` series is Strategy A's dip-in-uptrend test series: close 120.9, SMA200 112.935, RSI(2) 100/28, ATR 206.8/196 → 1.0551, and SMA5 122.1.
- Dip entry: limit 120.3725, stop q(117.73475) = 117.7348.
- Close entry: stop q(118.26225) = 118.2623.
- Take 1 ATR: 121.4276.

The whole file was run against contract-faithful stand-ins for `Target`, `equal_weight`, `target_from_close`, `Allocator` and two kit checkers: **87 passed in about 29 s**. The slowest tests are the two `test_no_look_ahead` cases and the kit test, at about 6 s each. The reconciler then rewrote the kit test to phase 2's real API (D-E, same count); its two params × three held sets × 100 dates (with the lookback-tail check) may take a few seconds longer.
**Code:**
```python
"""Family F7: longer-horizon mean reversion (P7a phase 8; handover §4.B F7, D12; plan R3)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity
from simkit import P
from stratkit import dip, drop_days, hist, mutate_from, sawtooth, session_days, truncate_before, uptrend

from seer_engine.dates import prev_session
from seer_engine.sim import Target, equal_weight
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import History
from seer_engine.strategies.f_swing import (
    ATR_N,
    DV_N,
    SWING,
    WINDOW,
    SwingFeatures,
    SwingParams,
    SwingPrepared,
    entry_target,
    features_at,
    has_exit_signal,
    has_setup,
    member_window,
    rank_entries,
    swing_lookback,
    trend_on,
)

DEFAULT = SwingParams()
QUARTER = Decimal("0.25")


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


def sf(
    symbol: str = "AAA",
    *,
    close: float = 50.0,
    sma: float = 40.0,
    exit_sma: float | None = 55.0,
    rsi: float = 5.0,
    atr: float = 1.0,
    dollar_volume: float = 100_000_000.0,
) -> SwingFeatures:
    """A SwingFeatures row that passes the default setup and has no exit signal, unless overridden."""
    return SwingFeatures(symbol, date(2019, 1, 2), close, sma, exit_sma, rsi, atr, dollar_volume)


def dip_set() -> tuple[list[date], dict[str, History]]:
    """Day 229 is a dip in every DIP* series (RSI(2) well below 10, close above SMA200)."""
    days = session_days(230)
    return days, {
        "DIP": hist("DIP", dip(uptrend(230), 229), days=days),
        "DIPB": hist("DIPB", dip(uptrend(230), 229, drop=2.0), days=days),
        "DIPC": hist("DIPC", dip(uptrend(230, first=90.0), 229, drop=1.5), days=days),
        "UP": hist("UP", uptrend(230, first=60.0), days=days),
    }


# ---- params ---------------------------------------------------------------------------------


def test_defaults_and_as_dict():
    assert (WINDOW, ATR_N, DV_N) == (200, 14, 20)
    assert DEFAULT == SwingParams(
        4, 2, 10.0, 200, "dip", Decimal("0.5"), Decimal("2.5"), None, 5, None, 20_000_000.0, None
    )
    assert list(DEFAULT.as_dict().items()) == [
        ("slots", "4"),
        ("rsi_n", "2"),
        ("rsi_max", "10"),
        ("sma_n", "200"),
        ("entry", "dip"),
        ("limit_atr", "0.5"),
        ("stop_atr", "2.5"),
        ("take_atr", "none"),
        ("exit_sma", "5"),
        ("exit_rsi", "none"),
        ("min_dollar_volume", "20000000"),
        ("market_trend", "none"),
    ]
    p = SwingParams(
        slots=8, rsi_max=5, entry="close", stop_atr=None, take_atr=Decimal("1.50"), exit_sma=None,
        exit_rsi=70, market_trend=("SPY", 200),
    )
    assert isinstance(p.rsi_max, float) and isinstance(p.exit_rsi, float)
    assert p.as_dict() == {
        "slots": "8", "rsi_n": "2", "rsi_max": "5", "sma_n": "200", "entry": "close", "limit_atr": "0.5",
        "stop_atr": "none", "take_atr": "1.5", "exit_sma": "none", "exit_rsi": "70",
        "min_dollar_volume": "20000000", "market_trend": "SPY:200",
    }


@pytest.mark.parametrize(
    ("kw", "exc"),
    [
        ({"slots": 0}, ValueError),
        ({"slots": 101}, ValueError),
        ({"slots": True}, TypeError),
        ({"slots": 4.0}, TypeError),
        ({"rsi_n": 0}, ValueError),
        ({"sma_n": 0}, ValueError),
        ({"rsi_max": 0.0}, ValueError),
        ({"rsi_max": 100.5}, ValueError),
        ({"rsi_max": "10"}, TypeError),
        ({"rsi_max": float("nan")}, ValueError),
        ({"entry": "open"}, ValueError),
        ({"entry": 1}, TypeError),
        ({"limit_atr": 0.5}, TypeError),
        ({"limit_atr": Decimal("-0.1")}, ValueError),
        ({"stop_atr": Decimal("0")}, ValueError),
        ({"stop_atr": 2.5}, TypeError),
        ({"take_atr": Decimal("-1")}, ValueError),
        ({"take_atr": Decimal("NaN")}, ValueError),
        ({"exit_sma": 0}, ValueError),
        ({"exit_rsi": 100.0}, ValueError),
        ({"exit_rsi": -1.0}, ValueError),
        ({"min_dollar_volume": -1.0}, ValueError),
        ({"market_trend": ["SPY", 200]}, TypeError),
        ({"market_trend": ("SPY",)}, TypeError),
        ({"market_trend": ("", 200)}, TypeError),
        ({"market_trend": ("SPY", 0)}, ValueError),
    ],
)
def test_params_reject_bad_values(kw, exc):
    with pytest.raises(exc):
        SwingParams(**kw)


def test_windows_and_lookback():
    assert member_window(DEFAULT) == swing_lookback(DEFAULT) == 200
    assert member_window(SwingParams(sma_n=250)) == 250
    assert member_window(SwingParams(exit_sma=300)) == 300
    p = SwingParams(market_trend=("SPY", 260))
    assert (member_window(p), swing_lookback(p)) == (200, 260)  # the trend never widens member windows


def test_swing_implements_the_allocator_protocol():
    assert isinstance(SWING, Allocator)
    assert SWING.id == "F7"
    assert SWING.lookback(DEFAULT) == 200
    assert SWING.symbols(DEFAULT) == ()
    assert SWING.symbols(SwingParams(market_trend=("SPY", 200))) == ("SPY",)
    assert SWING.holds(DEFAULT) == ()
    assert SWING.uses_members(DEFAULT) is True


def test_wrong_types_raise():
    days, history = dip_set()
    d = days[-1]
    with pytest.raises(TypeError, match="SwingParams"):
        SWING.targets(history, {"DIP"}, d, frozenset(), object())
    with pytest.raises(TypeError, match="SwingParams"):
        SWING.lookback({"slots": 4})
    with pytest.raises(TypeError, match="held"):
        SWING.targets(history, {"DIP"}, d, ["DIP"], DEFAULT)
    with pytest.raises(TypeError, match="SwingPrepared"):
        SWING.targets_prepared(object(), {"DIP"}, d, frozenset(), DEFAULT)


# ---- features -------------------------------------------------------------------------------


def test_features_hand_computed_on_the_dip():
    # The Strategy A dip (tests/test_strategy_a.py): close 120.9, SMA200 112.935, RSI(2) 100/28,
    # ATR(14) 206.8/196, DV 121.8e6. SMA(5) = (122.5 + 122.6 + 122.7 + 121.8 + 120.9) / 5 = 122.1.
    days, history = dip_set()
    [f] = features_at(history, ["DIP"], days[229], DEFAULT)
    assert (f.symbol, f.data_date) == ("DIP", days[229])
    assert f.close == pytest.approx(120.9, rel=1e-12)
    assert f.sma == pytest.approx(112.935, rel=1e-12)
    assert f.exit_sma == pytest.approx(122.1, rel=1e-12)
    assert f.rsi == pytest.approx(100 / 28, rel=1e-9)
    assert f.atr == pytest.approx(206.8 / 196, rel=1e-12)
    assert f.dollar_volume == pytest.approx(121.8e6, rel=1e-12)
    [g] = features_at(history, ["DIP"], days[229], SwingParams(exit_sma=None))
    assert g.exit_sma is None and g.rsi == f.rsi


def test_features_eligibility_and_order():
    days = session_days(201)
    closes = sawtooth(201)
    h199 = {"X": hist("X", closes[:199], days=days[:199])}
    h200 = {"X": hist("X", closes[:200], days=days[:200])}
    assert features_at(h199, ["X"], days[198], DEFAULT) == ()
    assert [f.symbol for f in features_at(h200, ["X", "X", "NOPE"], days[199], DEFAULT)] == ["X"]
    gappy = {"X": drop_days(hist("X", closes, days=days), [days[200]])}
    assert features_at(gappy, ["X"], days[200], DEFAULT) == ()
    many = {s: hist(s, sawtooth(200)) for s in ("MMM", "AAA", "ZZZ")}
    assert [f.symbol for f in features_at(many, ["ZZZ", "AAA", "MMM"], many["AAA"].last_date(), DEFAULT)] == [
        "AAA", "MMM", "ZZZ",
    ]
    assert features_at(h200, ["X"], days[199], SwingParams(sma_n=201)) == ()  # window 201 > 200 bars


def test_features_read_only_the_member_window():
    days = session_days(300)
    tail = sawtooth(200, first=150.0)
    a = {"X": hist("X", [50.0 + t for t in range(100)] + tail, days=days)}
    b = {"X": hist("X", [999.0 - t for t in range(100)] + tail, days=days)}
    c = {"X": hist("X", tail, days=days[100:])}
    assert features_at(a, ["X"], days[-1], DEFAULT) == features_at(b, ["X"], days[-1], DEFAULT)
    assert features_at(b, ["X"], days[-1], DEFAULT) == features_at(c, ["X"], days[-1], DEFAULT)


# ---- setup and exit signal, each condition alone --------------------------------------------


@pytest.mark.parametrize(
    ("kw", "passes"),
    [
        ({}, True),
        ({"rsi": 10.0}, False),  # RSI exactly rsi_max: strict
        ({"rsi": 9.999999}, True),
        ({"close": 40.0, "sma": 40.0}, False),  # close == SMA: strict
        ({"close": 39.0, "sma": 40.0}, False),
        ({"dollar_volume": 20_000_000.0}, False),  # exactly the floor: strict
        ({"dollar_volume": 20_000_000.5}, True),
        ({"sma": float("nan")}, False),
        ({"atr": float("nan")}, False),
        ({"exit_sma": 10.0}, True),  # an exit signal does not block the setup
    ],
)
def test_setup_each_condition_alone(kw, passes):
    assert has_setup(sf(**kw), DEFAULT) is passes


@pytest.mark.parametrize(
    ("kw", "params", "exits"),
    [
        ({}, DEFAULT, False),  # close 50 < SMA5 55
        ({"exit_sma": 50.0}, DEFAULT, False),  # close == SMA5: strict
        ({"exit_sma": 49.99}, DEFAULT, True),
        ({"exit_sma": 10.0}, SwingParams(exit_sma=None), False),  # SMA exit off
        ({"rsi": 70.0}, SwingParams(exit_rsi=70.0), False),  # RSI == exit_rsi: strict
        ({"rsi": 70.01}, SwingParams(exit_rsi=70.0), True),
        ({"rsi": 99.0}, DEFAULT, False),  # RSI exit off by default
        ({"exit_sma": 10.0, "rsi": 99.0}, SwingParams(exit_sma=None, exit_rsi=None), False),  # never by signal
        ({"exit_sma": None}, DEFAULT, False),  # no SMA value: nothing to decide
    ],
)
def test_exit_signal_each_condition_alone(kw, params, exits):
    assert has_exit_signal(sf(**kw), params) is exits


# ---- entry targets --------------------------------------------------------------------------


def test_dip_target_hand_computed():
    # last = 120.9000, ATR -> 1.0551; limit = q(120.9 - 0.52755) = 120.3725 (half-up);
    # stop = q(120.3725 - 2.5 × 1.0551) = q(117.73475) = 117.7348; no take
    days, history = dip_set()
    assert SWING.targets(history, {"DIP"}, days[229], frozenset(), DEFAULT) == (
        Target("DIP", QUARTER, P("120.9"), P("120.3725"), P("117.7348"), None),
    )


def test_close_entry_and_take_hand_computed():
    days, history = dip_set()
    # entry close: limit = last = 120.9; stop = q(120.9 - 2.63775) = q(118.26225) = 118.2623
    close = SwingParams(entry="close")
    assert SWING.targets(history, {"DIP"}, days[229], frozenset(), close) == (
        Target("DIP", QUARTER, P("120.9"), P("120.9"), P("118.2623"), None),
    )
    # take 1 ATR above the dip limit: q(120.3725 + 1.0551) = 121.4276; no stop
    take = SwingParams(take_atr=Decimal("1.0"), stop_atr=None)
    assert SWING.targets(history, {"DIP"}, days[229], frozenset(), take) == (
        Target("DIP", QUARTER, P("120.9"), P("120.3725"), None, P("121.4276")),
    )


@pytest.mark.parametrize(
    ("atr", "limit", "stop"),
    [
        # atr 1.2345: limit = q(50 - 0.61725) = 49.3828; stop = q(49.3828 - 3.08625) = q(46.29655) = 46.2966
        (1.2345, "49.3828", "46.2966"),
        # ATR quantized first: 1.23456789 -> 1.2346; limit = q(50 - 0.6173) = 49.3827;
        # stop = q(49.3827 - 3.0865) = 46.2962
        (1.23456789, "49.3827", "46.2962"),
    ],
)
def test_entry_prices_at_four_dp(atr, limit, stop):
    assert entry_target(sf(close=50.0, atr=atr), DEFAULT) == Target("AAA", QUARTER, P("50"), P(limit), P(stop), None)


@pytest.mark.parametrize(
    ("close", "atr", "params"),
    [
        (1.0, 3.0, DEFAULT),  # limit = 1 - 1.5 < 0
        (1.0, 2.0, DEFAULT),  # limit = 0
        (1.0, 0.4, DEFAULT),  # limit 0.8, stop = 0.8 - 1.0 < 0
        (50.0, 0.0, DEFAULT),  # zero ATR: stop == limit
        (50.0, 0.00004, DEFAULT),  # ATR rounds to 0.0000: stop == limit
        (50.0, 0.0001, SwingParams(stop_atr=None, take_atr=Decimal("0.25"))),  # take = q(50 + 0.000025) == limit
        (0.00004, 0.00001, DEFAULT),  # last rounds to 0.0000
    ],
)
def test_invalid_orderings_are_dropped_not_raised(close, atr, params):
    f = sf(close=close, sma=close / 2, atr=atr)
    assert entry_target(f, params) is None
    assert rank_entries([f], params, 4) == ()


def test_no_stop_no_take_is_a_plain_limit():
    # zero ATR with no stop and no TP: limit == last is a valid target
    assert entry_target(sf(close=50.0, atr=0.0), SwingParams(stop_atr=None)) == Target(
        "AAA", QUARTER, P("50"), P("50"), None, None
    )


def test_weight_is_one_over_slots():
    for slots, w in ((1, "1"), (3, "0.333333"), (8, "0.125")):
        t = entry_target(sf(), SwingParams(slots=slots))
        assert t is not None and t.weight == Decimal(w) == equal_weight(slots)


def test_rank_entries_by_rsi_then_symbol_and_capped():
    feats = [
        sf("MMM", rsi=3.0),
        sf("ZZZ", rsi=1.0),
        sf("AAA", rsi=3.0),
        sf("BBB", rsi=7.0),
        sf("CCC", rsi=2.0),
        sf("NOP", rsi=12.0),  # fails the setup
    ]
    assert [t.symbol for t in rank_entries(feats, DEFAULT, 10)] == ["ZZZ", "CCC", "AAA", "MMM", "BBB"]
    assert [t.symbol for t in rank_entries(feats, DEFAULT, 2)] == ["ZZZ", "CCC"]
    assert rank_entries(feats, DEFAULT, 0) == ()


# ---- held symbols, slots and the market gate (through targets) ------------------------------


def test_new_entries_ranked_and_non_members_excluded():
    days, history = dip_set()
    d = days[229]
    got = SWING.targets(history, {"DIP", "DIPB", "DIPC", "UP"}, d, frozenset(), DEFAULT)
    rsi = {f.symbol: f.rsi for f in features_at(history, history, d, DEFAULT)}
    assert rsi["DIPB"] < rsi["DIPC"] < rsi["DIP"] < 10.0 < rsi["UP"]  # the scenario is what it claims
    assert [t.symbol for t in got] == ["DIPB", "DIPC", "DIP"]  # UP has no dip
    assert [t.symbol for t in SWING.targets(history, {"DIP"}, d, frozenset(), DEFAULT)] == ["DIP"]
    assert SWING.targets(history, frozenset(), d, frozenset(), DEFAULT) == ()


def test_held_kept_first_in_symbol_order_then_new_until_slots():
    days, history = dip_set()
    d = days[229]
    members = frozenset(history)
    # DIPC and DIP are held without an exit signal (close < SMA5); DIPB is the one new entry that fits
    got = SWING.targets(history, members, d, frozenset({"DIPC", "DIP"}), SwingParams(slots=3))
    third = Decimal("0.333333")
    assert [(t.symbol, t.limit, t.stop, t.take) for t in got] == [
        ("DIP", None, None, None),
        ("DIPC", None, None, None),
        ("DIPB", got[2].limit, got[2].stop, None),
    ]
    assert got[2].limit is not None and got[2].stop is not None
    assert all(t.weight == third for t in got)
    assert got[0].last == P("120.9")  # kept targets carry the data_date close
    # slots full with kept: no new entry at all
    full = SWING.targets(history, members, d, frozenset({"DIPC", "DIP"}), SwingParams(slots=2))
    assert [t.symbol for t in full] == ["DIP", "DIPC"]


def test_held_with_exit_signal_is_dropped_and_frees_its_slot():
    days, history = dip_set()
    d = days[229]
    # UP rises every day: close > SMA5, so it is signal-exited (not returned); its slot goes to a new entry
    got = SWING.targets(history, frozenset(history), d, frozenset({"UP"}), SwingParams(slots=1))
    assert [t.symbol for t in got] == ["DIPB"]
    # RSI exit: UP's RSI(2) is 100 > 50; DIP's 3.6 is not
    rsi_exit = SwingParams(exit_sma=None, exit_rsi=50.0, slots=2)
    got = SWING.targets(history, frozenset(), d, frozenset({"UP", "DIP"}), rsi_exit)
    assert [t.symbol for t in got] == ["DIP"]
    # both exits off: held forever by signal
    never = SwingParams(exit_sma=None, exit_rsi=None)
    assert [t.symbol for t in SWING.targets(history, frozenset(), d, frozenset({"UP"}), never)] == ["UP"]


def test_held_without_a_bar_on_data_date_is_kept_at_its_last_close():
    days, history = dip_set()
    gappy = dict(history, DIP=drop_days(history["DIP"], [days[229]]))
    got = SWING.targets(gappy, frozenset(gappy), days[229], frozenset({"DIP"}), SwingParams(slots=1))
    # day 228's close: 100 + 22.8 - 1 = 121.8
    assert got == (Target("DIP", Decimal("1"), P("121.8")),)
    # a held symbol with no bar at all on or before data_date, or not in history, is not returned
    assert SWING.targets(gappy, frozenset(), days[0], frozenset({"NOPE"}), DEFAULT) == ()


def test_held_that_left_the_index_is_kept_until_it_exits():
    days, history = dip_set()
    d = days[229]
    # DIP is no longer a member: kept while held (no exit signal), never a new entry otherwise
    assert [t.symbol for t in SWING.targets(history, frozenset({"UP"}), d, frozenset({"DIP"}), DEFAULT)] == ["DIP"]
    assert SWING.targets(history, frozenset({"UP"}), d, frozenset(), DEFAULT) == ()
    # with too little history to compute features it is still kept
    short = {"DIP": hist("DIP", dip(uptrend(50), 49), days=days[180:])}
    assert [t.symbol for t in SWING.targets(short, frozenset(), d, frozenset({"DIP"}), DEFAULT)] == ["DIP"]


def test_kept_never_exceed_slots():
    days, history = dip_set()
    got = SWING.targets(history, frozenset(), days[229], frozenset({"DIP", "DIPB", "DIPC"}), SwingParams(slots=2))
    assert [t.symbol for t in got] == ["DIP", "DIPB"]  # symbol order, truncated at slots
    assert sum(t.weight for t in got) <= 1


def market(closes: list[float], days: list[date]) -> History:
    return hist("SPY", closes, days=days)


def test_market_trend_gates_new_entries_only():
    days, history = dip_set()
    d = days[229]
    gated = SwingParams(market_trend=("SPY", 200))
    up = dict(history, SPY=market(uptrend(230, first=200.0), days))
    down = dict(history, SPY=market([300.0 - 0.1 * t for t in range(230)], days))
    members = frozenset({"DIP", "DIPB", "DIPC"})
    assert [t.symbol for t in SWING.targets(up, members, d, frozenset(), gated)] == ["DIPB", "DIPC", "DIP"]
    assert SWING.targets(down, members, d, frozenset(), gated) == ()
    # held are kept when the gate is shut
    assert [t.symbol for t in SWING.targets(down, members, d, frozenset({"DIPC"}), gated)] == ["DIPC"]
    # no SPY, too little SPY history, or no SPY bar on data_date: shut
    assert SWING.targets(history, members, d, frozenset(), gated) == ()
    short = dict(history, SPY=market(uptrend(199), days[31:]))
    assert SWING.targets(short, members, d, frozenset(), gated) == ()
    gap = dict(up, SPY=drop_days(up["SPY"], [d]))
    assert SWING.targets(gap, members, d, frozenset(), gated) == ()


def test_trend_on_is_strict():
    days = session_days(200)
    flat = {"SPY": market([100.0] * 200, days)}
    assert trend_on(flat, ("SPY", 200), days[-1]) is False  # close == SMA
    assert trend_on(flat, None, days[-1]) is True
    rising = {"SPY": market(uptrend(200), days)}
    assert trend_on(rising, ("SPY", 200), days[-1]) is True
    assert trend_on(rising, ("SPY", 201), days[-1]) is False


# ---- the targets / targets_prepared contract -------------------------------------------------


def contract_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(320)
    spy = uptrend(260, first=200.0) + [225.9 - 0.8 * t for t in range(60)]
    return days, {
        "SAW": hist("SAW", sawtooth(320), days=days),
        "DIP": hist("DIP", dip(dip(dip(uptrend(320), 229), 260), 290, drop=2.0), days=days),
        "DIP2": hist("DIP2", dip(dip(uptrend(320, first=80.0, step=0.15), 240), 250, days=3), days=days),
        "DIP3": hist("DIP3", dip(dip(uptrend(320, first=50.0, step=0.05), 233, drop=0.8), 284, drop=0.6), days=days),
        "LATE": hist("LATE", dip(uptrend(260, first=40.0), 255, drop=0.7), days=days[60:]),
        "GAPPY": drop_days(
            hist("GAPPY", dip(uptrend(320, first=70.0), 235, drop=0.9), days=days), days[100:105] + [days[236]]
        ),
        "GONE": hist("GONE", dip(uptrend(270, first=90.0), 250, drop=1.2), days=days[:270]),
        "THIN": hist("THIN", dip(uptrend(320), 229), days=days, volume=1000.0),
        "SPY": hist("SPY", spy, days=days),
    }


def contract_members(days: list[date]) -> Callable[[date], frozenset[str]]:
    def members(d: date) -> frozenset[str]:
        out = {"SAW", "DIP", "DIP2", "DIP3", "GAPPY", "GONE", "THIN"}
        if d >= days[280]:
            out.add("LATE")
        if d >= days[255]:
            out.discard("DIP2")  # leaves the index while possibly held
        return frozenset(out)

    return members


def held_path(history: dict[str, History], days: list[date], members, params: SwingParams) -> dict[date, frozenset[str]]:
    """Held on each data_date = what the single-window path targeted the day before (fills ignored)."""
    held: frozenset[str] = frozenset()
    out: dict[date, frozenset[str]] = {}
    for d in days:
        out[d] = held
        held = frozenset(t.symbol for t in SWING.targets(upto_all(history, d), members(d), d, held, params))
    return out


CONTRACT_PARAMS = [
    DEFAULT,
    SwingParams(rsi_max=60.0),
    SwingParams(slots=2, entry="close", take_atr=Decimal("1.0"), exit_sma=None, exit_rsi=70.0),
    SwingParams(market_trend=("SPY", 200)),
    SwingParams(stop_atr=None, rsi_max=100.0, slots=8),
    SwingParams(rsi_n=3, rsi_max=30.0),  # not covered by the prepared columns: single-window path
    SwingParams(sma_n=220),  # member window 220: single-window path
]
CONTRACT_IDS = ["default", "loose", "close-take-rsi-exit", "trend", "nostop-wide", "rsi3", "sma220"]


@pytest.mark.parametrize("params", CONTRACT_PARAMS, ids=CONTRACT_IDS)
def test_targets_prepared_equals_targets_on_every_date(params):
    days, history = contract_set()
    members = contract_members(days)
    held = held_path(history, days[190:], members, params)
    prepared = SWING.prepare(history)
    assert isinstance(prepared, SwingPrepared)
    kept_days = new_days = exits = 0
    for d in days[190:]:
        visible = upto_all(history, d)
        if prepared.covers(params):
            assert prepared.features_on(d, params) == features_at(visible, visible, d, params), d  # bit-identical
        expected = SWING.targets(visible, members(d), d, held[d], params)
        assert SWING.targets_prepared(prepared, members(d), d, held[d], params) == expected, d
        assert SWING.targets(history, members(d), d, held[d], params) == expected, d  # later bars ignored
        symbols = [t.symbol for t in expected]
        assert len(set(symbols)) == len(symbols) and sum(t.weight for t in expected) <= 1
        kept_days += any(s in held[d] for s in symbols)
        new_days += any(s not in held[d] for s in symbols)
        exits += len(held[d] - set(symbols))
    assert kept_days > 0 and new_days > 0 and exits > 0  # every branch fired: the check is not vacuous


def test_prepared_coverage():
    _, history = contract_set()
    prepared = SWING.prepare(history)
    assert prepared.covers(DEFAULT) and prepared.covers(SwingParams(exit_sma=None, exit_rsi=60.0))
    assert prepared.covers(SwingParams(market_trend=("SPY", 300)))  # the trend reads history directly
    for p in (SwingParams(rsi_n=3), SwingParams(sma_n=150), SwingParams(exit_sma=10), SwingParams(exit_sma=250)):
        assert not prepared.covers(p)
        with pytest.raises(ValueError, match="cover"):
            prepared.features_on(date(2019, 11, 1), p)


def test_prepare_on_short_or_empty_history():
    short = {"X": hist("X", sawtooth(150))}
    d = date(2019, 6, 3)
    for history in ({}, short):
        prepared = SWING.prepare(history)
        assert prepared.features_on(d, DEFAULT) == ()
        assert SWING.targets_prepared(prepared, {"X"}, d, frozenset(), DEFAULT) == ()
        assert SWING.targets(history, {"X"}, d, frozenset(), DEFAULT) == ()
    # a held symbol with a short history is kept on both paths
    prepared = SWING.prepare(short)
    want = SWING.targets(short, {"X"}, d, frozenset({"X"}), DEFAULT)
    assert [t.symbol for t in want] == ["X"]
    assert SWING.targets_prepared(prepared, {"X"}, d, frozenset({"X"}), DEFAULT) == want


# ---- no look-ahead --------------------------------------------------------------------------


LOOK_AHEAD_PARAMS = (DEFAULT, SwingParams(market_trend=("SPY", 200)), SwingParams(rsi_n=3, rsi_max=30.0))


@pytest.mark.parametrize("mutation", ["change", "truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S leaves S's targets unchanged."""
    days, history = contract_set()
    members = contract_members(days)
    prepared = SWING.prepare(history)
    held = {p: held_path(history, days[220:], members, p) for p in LOOK_AHEAD_PARAMS}
    nonempty = 0
    for s in days[221:]:
        d = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        else:
            future = {k: truncate_before(h, s) for k, h in history.items()}
        future_prepared = SWING.prepare(future)
        for params in LOOK_AHEAD_PARAMS:
            h = held[params][d]
            before = SWING.targets(history, members(d), d, h, params)
            assert SWING.targets(future, members(d), d, h, params) == before, s
            assert SWING.targets_prepared(future_prepared, members(d), d, h, params) == before, s
            assert SWING.targets_prepared(prepared, members(d), d, h, params) == before, s
            nonempty += bool(before)
    assert nonempty > 0


def test_the_mutation_does_change_later_targets():
    # Guards test_no_look_ahead: the same mutation, read at data_date = S, changes the targets.
    days, history = contract_set()
    s = days[229]
    future = {k: mutate_from(h, s) for k, h in history.items()}
    members = frozenset(history) - {"SPY"}
    loose = SwingParams(rsi_max=100.0)
    assert SWING.targets(future, members, s, frozenset(), loose) != SWING.targets(history, members, s, frozenset(), loose)


def test_kit_identity_and_no_look_ahead():
    """The shared phase-2 checkers (tests/allocatorkit.py; plan index D-E) agree on F7."""
    days, history = contract_set()
    members = contract_members(days)
    # Fixed held sets on every date: nothing, two dipping members (one leaves the index at day
    # 255), and a gappy member plus one whose bars end at day 270 (kept at its last close).
    held_sets = [frozenset(), frozenset({"DIP", "DIP2"}), frozenset({"GAPPY", "GONE"})]
    params = [DEFAULT, SwingParams(market_trend=("SPY", 200))]
    assert assert_p4_identity(SWING, history, members, days[220:], held_sets, params) > 0
    assert assert_no_lookahead(SWING, history, members, days[221:300:3], held_sets, params) > 0
```
**Impact:** this adds 87 tests to the suite. Baseline is 970 on `2546a92`, plus whatever Phases 1–7 add. The phase log records the observed collected count.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/trade-rules-dev-search && engine/.venv/bin/python -c "import seer_engine.strategies.f_swing as m; print(m.SWING.id, m.SwingParams().as_dict())"`
- Uses the worktree's own venv, never main's.

**Tests:**
- `engine/.venv/bin/pytest engine/tests/test_f_swing.py engine/tests/test_strategy_purity.py -q`
- Then the full suite, after `docker start seer-pg`: `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`. It must report 0 skipped.

**Manual check:**
- `git diff --stat 2546a92 -- engine/src/seer_engine/strategies/a.py engine/src/seer_engine/strategies/base.py engine/src/seer_engine/strategies/__init__.py engine/src/seer_engine/strategies/indicators.py` must show no change from this phase. Phase 2's additive `return_window` in `indicators.py` is the only expected diff there.
- `git status` must list only the two new files.

**Exit criteria:**
- `test_f_swing.py` passes 87 of 87.
- The purity tests list `seer_engine.strategies.f_swing` among the pure modules and pass.
- The full suite is green with 0 skipped.
- No other file is changed.

## Handoffs

- **Phase 3 (book runner), about idle symbols — settled, plan index D-J.** `run_book` passes the allocator `held = book.held() − {rules.idle_symbol}`, so F7 never sees (or keeps) an idle BIL position. No registry row pairs F7 with idle rules anyway (rows 46–52 and 54 use the `SWING_*` presets).
- **Phase 11 (registry).** Import `SWING` and `SwingParams` from `seer_engine.strategies.f_swing`; they are not in `strategies/__init__`. `SW(...)` in the index table maps 1:1 onto `SwingParams` keyword fields:
  - `SW(entry=close)` → `SwingParams(entry="close")`;
  - `SW(slots=8)`;
  - `SW(market_trend=(SPY,200))` → `SwingParams(market_trend=("SPY", 200))`;
  - `SW(stop_atr=None)`.
  - `candidate_digest` can hash `SwingParams.as_dict()`, whose order is fixed and tested.
- **Phase 9 (`candidate_window`).** `SWING.symbols(p)` is `()` unless a market trend is set, and `uses_members` is True. So F7 candidates start at the first session where SPY has `lookback` (200) bars **and** `prev_session(S) >= MEMBERSHIP_START`. That follows the contract with no special case. Individual members become eligible only once they have 200 bars of their own.
- **Phase 2 (kit naming).** `test_kit_identity_and_no_look_ahead` uses phase 2's exact names and signatures (plan index D-E). If it fails on the real kit, fix the call, never the kit.
- **`as_dict` encoding (plan index D-F).** F7 encodes `None` as `"none"` and a `(symbol, n)` pair as `"SYM:n"`, the same as phases 5–7.
- **Row 54 (F9 BLEND of TIMING + SWING under `SWING_T20`).** The TIMING core's SPY target has no limit; phase 1's D-B fallback buys it like `open_limit`. F7's own entries keep their limits.
- **Possible later cleanup (no phase owns it in P7a).** `trend_on` duplicates the "close > SMA(n) of a fixed symbol" gate that Phases 5–7 probably implement too. Consolidating it into `allocator.py` would be a Phase-2-owned change; it is not done here.

## Rollback

Delete `engine/src/seer_engine/strategies/f_swing.py` and `engine/tests/test_f_swing.py`, or `git revert` this phase's commit. Nothing else references them until Phase 11.
