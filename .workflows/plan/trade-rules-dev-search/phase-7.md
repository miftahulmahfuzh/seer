# Phase 7: Families F4/F5/F6: stock factors

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R3 — no look-ahead and P4 identity for every new strategy family; the prepared and single-window paths agree (here: F4 momentum, F5 low volatility, F6 momentum + low vol)
**Depends on:** Phase 2 (and, through it, Phase 1)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

After this phase, `seer_engine.strategies.f_factor` exists. It has `FactorParams` and the
`FACTOR` allocator (id `"FAC"`), which turns index-member history at a `data_date` close into
ranked, weighted `Target`s: 12-1 momentum, low volatility, or momentum-then-low-vol. There are
equal or inverse-vol weights, an optional SPY trend gate, and SPY is never targeted.

`prepare` is vectorized in the style of `prepare_a`. It produces features that are bit-identical
to the single-window path, so `targets_prepared(prepare(H), …) == targets({s: h.upto(d)}, …)`.
`tests/test_f_factor.py` proves this with hand-computed features and the P4-identity and
no-look-ahead checks. The registry rows F4-…, F5-… and F6-… (phase 11) can then be built.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates (all in `engine/src/seer_engine/strategies/f_factor.py`, a new pure module):**
- `FactorParams` (frozen, slots), with fields and defaults exactly as in the index contract:
  `rank`, `top=10`, `mom_n=252`, `mom_skip=21`, `vol_n=60`, `pool=50`, `sizing="equal"`,
  `min_dollar_volume=20_000_000.0`, `min_price=5.0`, `trend=("SPY", 200)`.
  - It validates in `__post_init__`. It has `as_dict() -> dict[str, str]` with the key order
    `rank, top, mom_n, mom_skip, vol_n, pool, sizing, min_dollar_volume, min_price, trend`.
  - `trend` is rendered as `"SPY:200"`, or `"none"`.
- `FactorAllocator` with `id = "FAC"`, and `FACTOR = FactorAllocator()`. It implements the
  phase-2 `Allocator` protocol:
  - `lookback(params)`;
  - `symbols(params)`, which is `(trend[0],)` or `()`;
  - `holds(params)`, which is `()`;
  - `uses_members(params)`, which is `True`;
  - `targets(history, members, data_date, held, params)`;
  - `prepare(history) -> FactorPrepared`;
  - `targets_prepared(prepared, members, data_date, held, params)`.
- Helpers, public so that tests and the reconciler can name them:
  - `DV_N = 20`;
  - `EXCLUDED = frozenset({"SPY"})`;
  - `MAX_TOP = 1000`;
  - `Rank` and `Sizing` (Literals);
  - `FactorRow(symbol, close, momentum, vol, dollar_volume)`;
  - `FactorPrepared`, with `.rows_on(members, d, params)`, `.column(key)` and `.cache`;
  - `prepare_factor(history)`;
  - `factor_lookback(params)`, which is `max(mom_n+1, vol_n+1, 20, trend n or 0)`;
  - `factor_rows(history, members, d, params)`;
  - `trend_on(history, d, params)`;
  - `rank_rows(rows, params)`;
  - `factor_weights(chosen, params)`;
  - `targets_from_rows(rows, params)`.

**Signature changes:** none.

**Requires (from earlier phases), assumed landed exactly as in the index contract:**

Phase 1, `seer_engine/sim/book.py`:
- `Target(symbol, weight, last, limit=None, stop=None, take=None)`, frozen, with value equality;
- `WEIGHT_QUANTUM = Decimal("0.000001")`;
- `to_weight(x: float | Decimal) -> Decimal`, which quantizes DOWN, takes floats through
  `repr`, and raises `ValueError` when the result is <= 0;
- `equal_weight(n) -> Decimal`.

This phase imports them from `seer_engine.sim.book`, not from `seer_engine.sim`, because
`WEIGHT_QUANTUM` is not in the contracted `sim/__init__` export list.

Phase 2, `seer_engine/strategies/allocator.py`:
- `Allocator`, the `runtime_checkable` Protocol, with `lookback`, `symbols`, `holds` and
  `uses_members` as **methods taking params**, and an `id` attribute;
- `target_from_close(symbol, close: float, weight, *, limit=None, stop=None, take=None) -> Target | None`,
  which returns `Target(symbol, weight, last=q(to_decimal(close)))` when called with no bracket
  prices.

Phase 2, `seer_engine/strategies/indicators.py`:
- `return_window(close, n, skip=0)`, which returns `c[:, -1-skip] / c[:, -1-n] − 1`.
  - It is end-relative: it reads only the columns `-1-n` and `-1-skip`.
  - It returns NaN rows when `W < n + 1`.
  - It requires `0 <= skip < n`.
  - It is called through `indicators.rolling(..., n=…, skip=…)` (keyword arguments).

Phase 2, `engine/tests/allocatorkit.py` (plan index D-E, phase 2's kit is canonical):
- `assert_p4_identity(allocator, history, members_fn, dates, held_sets, params, *,
  max_weight_sum=Decimal(1), check_lookback=True) -> int`: for each data date, held set and
  params value, single-window == full-history == prepared == lookback-tail targets.
- `assert_no_lookahead(allocator, history, members_fn, sessions, held_sets, params) -> int`:
  for each session `S`, with `d = prev_session(S)`, every bar dated `>= S` changed and deleted
  leaves both paths unchanged.
- `members_fn` is a callable `date -> AbstractSet[str]`; `held_sets` and `params` are non-empty
  lists. Both return the non-empty count, which the tests assert is > 0.

**Leaves alone (owned by others):**
- `strategies/allocator.py`, `strategies/indicators.py` and `tests/allocatorkit.py` (Phase 2);
- `strategies/__init__.py` (no export is added; consumers import `seer_engine.strategies.f_factor`
  directly);
- `sim/*` (Phase 1);
- `backtest/*` (Phases 3, 9–12);
- `strategies/f_index.py` (5), `f_rotation.py` (6), `f_swing.py` (8);
- every frozen file listed in the index.

## Decisions made in this phase (record for the reconciler)

| Ambiguity | Decision | Why |
|---|---|---|
| The contract's `prepare(history)` takes no params, but momentum and vol windows differ per candidate (`mom_n` 252/126, `vol_n` 60/252) | `FactorPrepared` holds the param-independent columns: dates, sym, nbars, close, 20-day dollar volume. It builds each `("mom", n, skip)` and `("vol", n)` column **lazily on first use** and caches it in `FactorPrepared.cache`. A single prepared object serves every FAC candidate | Phase 9 prepares once per `allocator.id`. Computing every possible window up front is impossible |
| How bit-identity is guaranteed | Every feature comes from an end-relative window function (`return_window`, `stdev_return_window`, `mean_dollar_volume_window`, `sma_window`), whose result depends only on the last k columns, in a fixed operation order. So `rolling(fn, window=n+1)` and a single `lookback`-wide window give the same float. Eligibility uses one shared `_eligible_mask` in both paths, and selection uses one shared `targets_from_rows` | The `indicators` bit-identity rule, already proven by `prepare_a` |
| Lookback | `max(mom_n + 1, vol_n + 1, DV_N=20, trend n)`. Every member needs this many bars through d, whatever the `rank` (lowvol still needs momentum to be finite) | Contract: "eligible: … >= lookback bars through d, finite features". A single number keeps phase 9's `candidate_window` simple |
| Volatility 0 | Ineligible (`vol > 0` is part of "finite features") | `inverse_vol` divides by it. A flat price is not a real stock |
| `min_price` validation | Must be `>= 0.01`, so `target_from_close` never rounds a close to 0 | Removes a silent-drop path |
| Equal weights when fewer than `top` names qualify | Each chosen name gets `equal_weight(top)`. The rest is cash | The same as ROT's `equal_weight(top)`. Exposure does not jump up when the universe thins |
| `inverse_vol` total | `w_i = to_weight((1/vol_i) / Σ(1/vol) × k / top)`, where k is the number of chosen names. The sum is computed left to right in rank order. A weight that floors below `WEIGHT_QUANTUM` drops its name | The same total exposure as `equal`. Floors keep Σ <= 1 exactly |
| Trend gate data | Off (`()`, all cash) when the trend symbol is absent from `history`, has no bar dated d, or has fewer than n bars through d. On when close > SMA(n), strictly | Conservative. Never trade on a stale or missing signal |
| `held` | It is validated as an `AbstractSet` and otherwise ignored. The targets are exactly the new top set | Contract: "Held symbols are kept only if they rank in the new top (rebalance)" |
| SPY | Excluded by symbol even if a membership set lists it | Contract: "symbol not 'SPY'". Belt and braces |
| Order of targets | Rank order: momentum descending for `momentum`; vol ascending for `lowvol` and `mom_lowvol` | Contract: "Targets are in rank order" |
| Dtypes | `sym` and `nbars` are int32 | Memory at about 3.7M rows. They are indices only and never reach a float |

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/f_factor.py` | create (`:1`) | the whole module: params, features, eligibility, ranking, weights, trend gate, `FactorPrepared`, `FACTOR` |
| `engine/tests/test_f_factor.py` | create (`:1`) | 78 tests (40 functions, with parametrization) |

No other file changes. Both new files sit flat in their directories, so `test_strategy_purity.py`
covers `f_factor.py` through its existing glob (`strategies/*.py`).

## Implementation Steps

### Step 1: Create the factor module
**File:** `engine/src/seer_engine/strategies/f_factor.py:1` (new file)
**Change:** write the module below verbatim.
**Code:**
```python
"""Families F4/F5/F6: cross-sectional stock factors over index members (P7a, handover §4.B).

One allocator, ``FACTOR`` (id ``"FAC"``); ``Candidate.family`` carries F4, F5 or F6.

On ``data_date`` d, a symbol is **eligible** when all of these hold:
    it is a member on d and is not ``"SPY"``; it has a bar dated d and at least
    ``factor_lookback(params)`` bars through d; its momentum, volatility and dollar volume are
    finite; volatility > 0; 20-day mean close×volume > ``min_dollar_volume`` (strict); and
    close >= ``min_price``.
Features, each a function of the symbol's bars ending at d only:
    momentum      = return_window(close, mom_n, mom_skip)   (12-1: c[-22] / c[-253] − 1)
    volatility    = stdev_return_window(close, vol_n)       (population stdev of one-bar returns)
    dollar volume = mean_dollar_volume_window(close, volume, 20)
Ranking (ties broken by symbol ascending):
    momentum   — momentum descending, the first ``top``;
    lowvol     — volatility ascending, the first ``top``;
    mom_lowvol — the ``pool`` highest-momentum names, then among them volatility ascending, the first ``top``.
Weights: ``equal`` gives every chosen name ``equal_weight(top)`` (fewer than ``top`` eligible names
leave the rest in cash); ``inverse_vol`` gives ``to_weight((1/vol_i) / Σ(1/vol) × k / top)`` for the
k chosen names — the same total exposure as ``equal`` — floor-quantized so Σ <= 1. A weight that
floors to zero drops its name.
Trend gate: when ``trend = (symbol, n)``, nothing is targeted (all cash) unless that symbol has a
bar dated d, at least n bars through d, and close > SMA(n) (strict).
Held positions get no special treatment: the targets are exactly the new top set, so a held name
that falls out of it is signal-exited by the book engine (a rebalance).

Every window function is end-relative and bit-identical however long its window (see
``indicators``), so ``prepare`` computes rolling features over each symbol's whole history and
``targets_prepared`` equals ``targets`` on ``upto(d)`` bit for bit (the Allocator contract).
Volatility and momentum columns depend on the params, so ``FactorPrepared`` computes each
(mom_n, mom_skip) and vol_n column lazily, once, and keeps it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    return_window,
    rolling,
    sma_window,
    stdev_return_window,
)

DV_N = 20  # dollar-volume window, as Strategy A
EXCLUDED: frozenset[str] = frozenset({"SPY"})  # never a factor target, even if listed as a member
MAX_TOP = 1000  # equal_weight(top) stays >= 0.001

Rank = Literal["momentum", "lowvol", "mom_lowvol"]
Sizing = Literal["equal", "inverse_vol"]
_RANKS: tuple[str, ...] = ("momentum", "lowvol", "mom_lowvol")
_SIZINGS: tuple[str, ...] = ("equal", "inverse_vol")


def _plain(x: float | Decimal) -> str:
    """``x`` as a plain decimal string without trailing zeros: 5.0 -> "5", 20000000.0 -> "20000000"."""
    d = Decimal(repr(x)) if isinstance(x, float) else x
    return format(d.normalize(), "f")


def _check_int(name: str, v: object, lo: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo:
        raise ValueError(f"{name} must be >= {lo}, got {v}")
    return v


def _check_float(name: str, v: object) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    out = float(v)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {out!r}")
    return out


@dataclass(frozen=True, slots=True)
class FactorParams:
    """F4/F5/F6 parameters. Defaults are the plan contract's."""

    rank: Rank
    top: int = 10  # holdings
    mom_n: int = 252
    mom_skip: int = 21  # 12-1 momentum = return_window(c, mom_n, mom_skip)
    vol_n: int = 60  # stdev_return_window(c, vol_n)
    pool: int = 50  # mom_lowvol: the `pool` highest-momentum names, then the `top` lowest vol
    sizing: Sizing = "equal"
    min_dollar_volume: float = 20_000_000.0  # 20-day mean close×volume > this (strict)
    min_price: float = 5.0  # close >= min_price
    trend: tuple[str, int] | None = ("SPY", 200)  # all cash unless trend[0] close > SMA(trend[1]) on d

    def __post_init__(self) -> None:
        if not isinstance(self.rank, str):
            raise TypeError(f"rank must be a str, got {type(self.rank).__name__}")
        if self.rank not in _RANKS:
            raise ValueError(f"rank must be one of {_RANKS}, got {self.rank!r}")
        _check_int("top", self.top, 1)
        if self.top > MAX_TOP:
            raise ValueError(f"top must be <= {MAX_TOP}, got {self.top}")
        _check_int("mom_n", self.mom_n, 2)
        _check_int("mom_skip", self.mom_skip, 0)
        if self.mom_skip >= self.mom_n:
            raise ValueError(f"mom_skip must be < mom_n, got {self.mom_skip} >= {self.mom_n}")
        _check_int("vol_n", self.vol_n, 2)
        _check_int("pool", self.pool, 1)
        if self.rank == "mom_lowvol" and self.pool < self.top:
            raise ValueError(f"pool must be >= top for mom_lowvol, got pool={self.pool} top={self.top}")
        if not isinstance(self.sizing, str):
            raise TypeError(f"sizing must be a str, got {type(self.sizing).__name__}")
        if self.sizing not in _SIZINGS:
            raise ValueError(f"sizing must be one of {_SIZINGS}, got {self.sizing!r}")
        dv = _check_float("min_dollar_volume", self.min_dollar_volume)
        if dv < 0.0:
            raise ValueError(f"min_dollar_volume must be >= 0, got {dv}")
        object.__setattr__(self, "min_dollar_volume", dv)
        price = _check_float("min_price", self.min_price)
        if price < 0.01:
            raise ValueError(f"min_price must be >= 0.01, got {price}")
        object.__setattr__(self, "min_price", price)
        if self.trend is not None:
            if not isinstance(self.trend, tuple) or len(self.trend) != 2:
                raise TypeError(f"trend must be None or a (symbol, n) tuple, got {self.trend!r}")
            symbol, n = self.trend
            if not isinstance(symbol, str) or not symbol:
                raise ValueError(f"trend symbol must be a non-empty str, got {symbol!r}")
            _check_int("trend n", n, 1)

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        return {
            "rank": self.rank,
            "top": str(self.top),
            "mom_n": str(self.mom_n),
            "mom_skip": str(self.mom_skip),
            "vol_n": str(self.vol_n),
            "pool": str(self.pool),
            "sizing": self.sizing,
            "min_dollar_volume": _plain(self.min_dollar_volume),
            "min_price": _plain(self.min_price),
            "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
        }


def _check_params(params: object) -> FactorParams:
    if not isinstance(params, FactorParams):
        raise TypeError(f"params must be FactorParams, got {type(params).__name__}")
    return params


def factor_lookback(params: FactorParams) -> int:
    """Bars each read symbol needs through d: max(mom_n + 1, vol_n + 1, 20, trend n)."""
    _check_params(params)
    trend_n = params.trend[1] if params.trend is not None else 0
    return max(params.mom_n + 1, params.vol_n + 1, DV_N, trend_n)


@dataclass(frozen=True, slots=True)
class FactorRow:
    """One eligible symbol's features at a ``data_date`` close (float, bit-identical across paths)."""

    symbol: str
    close: float
    momentum: float
    vol: float
    dollar_volume: float


def _eligible_mask(
    close: np.ndarray, mom: np.ndarray, vol: np.ndarray, dv: np.ndarray, params: FactorParams
) -> np.ndarray:
    """The feature part of eligibility, shared verbatim by both paths."""
    return (
        np.isfinite(close)
        & np.isfinite(mom)
        & np.isfinite(vol)
        & np.isfinite(dv)
        & (vol > 0.0)
        & (dv > params.min_dollar_volume)
        & (close >= params.min_price)
    )


def factor_rows(
    history: Mapping[str, History], members: Set[str], data_date: date, params: FactorParams
) -> list[FactorRow]:
    """Eligible members' features on ``data_date``, sorted by symbol (the single-window path).

    Reads each member's last ``factor_lookback(params)`` bars ending at ``data_date``; later bars
    are never read.
    """
    _check_params(params)
    as_day(data_date)
    lb = factor_lookback(params)
    symbols: list[str] = []
    ends: list[int] = []
    for symbol in sorted(members):
        if symbol in EXCLUDED:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < lb:
            continue
        symbols.append(symbol)
        ends.append(i + 1)
    if not symbols:
        return []
    close = np.stack([history[s].close[e - lb : e] for s, e in zip(symbols, ends, strict=True)])
    volume = np.stack([history[s].volume[e - lb : e] for s, e in zip(symbols, ends, strict=True)])
    with np.errstate(divide="ignore", invalid="ignore"):
        mom = return_window(close, params.mom_n, params.mom_skip)
        vol = stdev_return_window(close, params.vol_n)
        dv = mean_dollar_volume_window(close, volume, DV_N)
    last = close[:, -1]
    mask = _eligible_mask(last, mom, vol, dv, params)
    return [
        FactorRow(symbols[k], float(last[k]), float(mom[k]), float(vol[k]), float(dv[k]))
        for k in (int(j) for j in np.flatnonzero(mask))
    ]


def trend_on(history: Mapping[str, History], data_date: date, params: FactorParams) -> bool:
    """The trend gate on ``data_date``: True when ``params.trend`` is None, else close > SMA(n) (strict).

    False when the trend symbol is absent, has no bar dated ``data_date`` or fewer than n bars
    through it. Reads only bars dated on or before ``data_date``.
    """
    _check_params(params)
    as_day(data_date)
    if params.trend is None:
        return True
    symbol, n = params.trend
    h = history.get(symbol)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    window = h.close[i + 1 - n : i + 1].reshape(1, n)
    sma = sma_window(window, n)[0]
    return bool(window[0, -1] > sma)


def rank_rows(rows: Sequence[FactorRow], params: FactorParams) -> list[FactorRow]:
    """The chosen rows, in rank order (ties by symbol ascending)."""
    _check_params(params)
    by_momentum = sorted(rows, key=lambda r: (-r.momentum, r.symbol))
    if params.rank == "momentum":
        return by_momentum[: params.top]
    if params.rank == "lowvol":
        return sorted(rows, key=lambda r: (r.vol, r.symbol))[: params.top]
    pool = by_momentum[: params.pool]
    return sorted(pool, key=lambda r: (r.vol, r.symbol))[: params.top]


def _floor_weight(x: float) -> Decimal | None:
    """``to_weight(x)``, or None when ``x`` floors to zero (or is not a finite positive float)."""
    if not np.isfinite(x) or Decimal(repr(x)) < WEIGHT_QUANTUM:
        return None
    return to_weight(x)


def factor_weights(chosen: Sequence[FactorRow], params: FactorParams) -> list[Decimal | None]:
    """One weight per chosen row (None = floors to zero, the row is dropped). Σ of the non-None <= 1."""
    _check_params(params)
    if not chosen:
        return []
    if params.sizing == "equal":
        w = equal_weight(params.top)
        return [w for _ in chosen]
    inverse = [1.0 / r.vol for r in chosen]
    total = 0.0
    for x in inverse:
        total = total + x
    scale = len(chosen) / params.top
    return [_floor_weight(x / total * scale) for x in inverse]


def targets_from_rows(rows: Sequence[FactorRow], params: FactorParams) -> tuple[Target, ...]:
    """Rank, weigh and price ``rows``: Targets with no limit, stop or take, in rank order."""
    chosen = rank_rows(rows, params)
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


def _check_held(held: object) -> None:
    if not isinstance(held, Set):
        raise TypeError(f"held must be a set of symbols, got {type(held).__name__}")


_EMPTY_F64 = np.empty(0, dtype=np.float64)
_EMPTY_F64.setflags(write=False)


@dataclass(frozen=True, slots=True, eq=False)
class FactorPrepared:
    """Param-independent columns for every (symbol, date) with at least ``DV_N`` bars through it.

    Columnar, ordered by (date, symbol). ``momentum``/``vol`` columns depend on the params, so
    ``column`` computes each one on first use from ``history`` and caches it in ``cache``.
    """

    symbols: tuple[str, ...]  # sorted; ``sym`` indexes into it
    dates: np.ndarray  # datetime64[D], ascending
    sym: np.ndarray  # int32
    nbars: np.ndarray  # int32: bars through that date (the row's index in its history + 1)
    close: np.ndarray  # float64
    dollar_volume: np.ndarray  # float64, mean_dollar_volume_window over DV_N
    history: Mapping[str, History] = field(repr=False)
    order: np.ndarray = field(repr=False)  # the (date, symbol) permutation of the per-symbol concatenation
    cache: dict[tuple[Any, ...], np.ndarray] = field(default_factory=dict, repr=False)

    def _rows(self, data_date: date) -> tuple[int, int]:
        day = as_day(data_date)
        lo = int(np.searchsorted(self.dates, day, side="left"))
        hi = int(np.searchsorted(self.dates, day, side="right"))
        return lo, hi

    def _included(self) -> list[History]:
        return [self.history[s] for s in self.symbols if len(self.history[s]) >= DV_N]

    def column(self, key: tuple[Any, ...]) -> np.ndarray:
        """``("mom", n, skip)`` or ``("vol", n)`` over every row, computed once and cached."""
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        parts: list[np.ndarray] = []
        for h in self._included():
            with np.errstate(divide="ignore", invalid="ignore"):
                if key[0] == "mom":
                    full = rolling(return_window, h.close, window=key[1] + 1, n=key[1], skip=key[2])
                elif key[0] == "vol":
                    full = rolling(stdev_return_window, h.close, window=key[1] + 1, n=key[1])
                else:
                    raise ValueError(f"unknown feature column {key!r}")
            parts.append(full[DV_N - 1 :])
        col = np.concatenate(parts)[self.order] if parts else _EMPTY_F64.copy()
        col.setflags(write=False)
        self.cache[key] = col
        return col

    def rows_on(self, members: Set[str], data_date: date, params: FactorParams) -> list[FactorRow]:
        """Eligible members' features on ``data_date``, sorted by symbol (== ``factor_rows`` on ``upto``)."""
        _check_params(params)
        lo, hi = self._rows(data_date)
        if lo == hi:
            return []
        window = slice(lo, hi)
        mom = self.column(("mom", params.mom_n, params.mom_skip))[window]
        vol = self.column(("vol", params.vol_n))[window]
        close = self.close[window]
        dv = self.dollar_volume[window]
        mask = (self.nbars[window] >= factor_lookback(params)) & _eligible_mask(close, mom, vol, dv, params)
        out: list[FactorRow] = []
        for j in (int(j) for j in np.flatnonzero(mask)):
            symbol = self.symbols[int(self.sym[lo + j])]
            if symbol in EXCLUDED or symbol not in members:
                continue
            out.append(FactorRow(symbol, float(close[j]), float(mom[j]), float(vol[j]), float(dv[j])))
        return out


def prepare_factor(history: Mapping[str, History]) -> FactorPrepared:
    """Rolling param-independent columns over every symbol's whole history (see ``FactorPrepared``)."""
    symbols = tuple(sorted(history))
    kept = {s: history[s] for s in symbols}
    parts: dict[str, list[np.ndarray]] = {k: [] for k in ("dates", "sym", "nbars", "close", "dv")}
    for k, symbol in enumerate(symbols):
        h = kept[symbol]
        if len(h) < DV_N:
            continue
        start = DV_N - 1
        parts["dates"].append(h.dates[start:])
        parts["sym"].append(np.full(len(h) - start, k, dtype=np.int32))
        parts["nbars"].append(np.arange(start + 1, len(h) + 1, dtype=np.int32))
        parts["close"].append(h.close[start:])
        parts["dv"].append(rolling(mean_dollar_volume_window, h.close, h.volume, window=DV_N, n=DV_N)[start:])
    if not parts["dates"]:
        empty_i = np.empty(0, dtype=np.int32)
        return FactorPrepared(
            symbols,
            np.empty(0, dtype="datetime64[D]"),
            empty_i,
            empty_i,
            _EMPTY_F64,
            _EMPTY_F64,
            history=kept,
            order=np.empty(0, dtype=np.int64),
        )
    dates = np.concatenate(parts["dates"])
    order = np.argsort(dates, kind="stable")  # symbols were appended in sorted order

    def col(key: str) -> np.ndarray:
        arr = np.concatenate(parts[key])[order]
        arr.setflags(write=False)
        return arr

    order.setflags(write=False)
    return FactorPrepared(
        symbols,
        col("dates"),
        col("sym"),
        col("nbars"),
        col("close"),
        col("dv"),
        history=kept,
        order=order,
    )


class FactorAllocator:
    """F4/F5/F6 behind the ``Allocator`` protocol."""

    id = "FAC"

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check_params(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check_params(params)
        return () if p.trend is None else (p.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_params(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_params(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _check_params(params)
        _check_held(held)
        if not trend_on(history, data_date, p):
            return ()
        return targets_from_rows(factor_rows(history, members, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> FactorPrepared:
        return prepare_factor(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        p = _check_params(params)
        _check_held(held)
        if not trend_on(prepared.history, data_date, p):
            return ()
        return targets_from_rows(prepared.rows_on(members, data_date, p), p)


FACTOR = FactorAllocator()
```
**Impact:** a new pure module and nothing else.
- Importing it loads only numpy, `seer_engine.sim.book`, `strategies.allocator`,
  `strategies.base` and `strategies.indicators`. None of them is forbidden by the purity glob.
- No existing caller changes.

### Step 2: Create the tests
**File:** `engine/tests/test_f_factor.py:1` (new file)
**Change:** write the test module below verbatim. It imports `stratkit` (existing) and
`allocatorkit` (phase 2).

`test_allocatorkit_p4_identity` and `test_allocatorkit_no_look_ahead` are the only places that
use `allocatorkit`, with phase 2's exact names and signatures (plan index D-E).
- The inline tests (`test_prepared_rows_are_bit_identical_and_targets_equal`,
  `test_no_look_ahead`) prove R3 on their own as well.

**Code:**
```python
"""Families F4/F5/F6: stock factors (P7a phase 7; requirement R3).

Hand-computed features, eligibility, the three rankings, weights, the trend gate, held
semantics, P4 identity (prepared rows bit-identical to single-window rows) and no look-ahead.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity
from stratkit import drop_days, hist, mutate_from, session_days, truncate_before

from seer_engine.dates import prev_session
from seer_engine.prices import to_decimal
from seer_engine.sim import q
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    DV_N,
    EXCLUDED,
    FACTOR,
    FactorAllocator,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    rank_rows,
    targets_from_rows,
    trend_on,
)

# lookback 20: mom = c[-2]/c[-6] − 1, vol over 3 returns, no trend, no dollar-volume floor
SMALL = FactorParams("momentum", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=0.0)


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


def wiggle(n: int, first: float = 50.0, growth: float = 0.0, amp: float = 0.2) -> list[float]:
    """Geometric growth with an alternating ±amp wiggle (volatility > 0, momentum monotone in growth)."""
    return [first * (1.0 + growth) ** t + (amp if t % 2 else -amp) for t in range(n)]


def walk(seed: int, n: int, first: float = 50.0, drift: float = 0.0003, sigma: float = 0.015) -> list[float]:
    rng = np.random.default_rng(seed)
    return [float(x) for x in first * np.cumprod(1.0 + rng.normal(drift, sigma, n))]


def py_stdev(c: Sequence[float], n: int) -> float:
    r = [c[i] / c[i - 1] - 1.0 for i in range(len(c) - n, len(c))]
    mean = r[0]
    for x in r[1:]:
        mean = mean + x
    mean = mean / n
    acc = (r[0] - mean) * (r[0] - mean)
    for x in r[1:]:
        acc = acc + (x - mean) * (x - mean)
    return math.sqrt(acc / n)


def py_dollar_volume(c: Sequence[float], v: Sequence[float]) -> float:
    first = len(c) - DV_N
    acc = c[first] * v[first]
    for j in range(first + 1, len(c)):
        acc = acc + c[j] * v[j]
    return acc / DV_N


def row(symbol: str, momentum: float, vol: float, close: float = 50.0) -> FactorRow:
    return FactorRow(symbol, close, momentum, vol, 1e9)


# ---- params, protocol ----------------------------------------------------------------------


def test_factor_implements_the_allocator_protocol():
    assert isinstance(FACTOR, FactorAllocator)
    assert isinstance(FACTOR, Allocator)
    assert FACTOR.id == "FAC"
    assert EXCLUDED == frozenset({"SPY"})


def test_defaults_are_the_contract_values():
    p = FactorParams("momentum")
    assert (p.top, p.mom_n, p.mom_skip, p.vol_n, p.pool) == (10, 252, 21, 60, 50)
    assert (p.sizing, p.min_dollar_volume, p.min_price, p.trend) == ("equal", 20_000_000.0, 5.0, ("SPY", 200))


def test_as_dict_is_plain_and_ordered():
    assert FactorParams("mom_lowvol", top=20, sizing="inverse_vol").as_dict() == {
        "rank": "mom_lowvol",
        "top": "20",
        "mom_n": "252",
        "mom_skip": "21",
        "vol_n": "60",
        "pool": "50",
        "sizing": "inverse_vol",
        "min_dollar_volume": "20000000",
        "min_price": "5",
        "trend": "SPY:200",
    }
    d = FactorParams("lowvol", trend=None, min_price=7.5, min_dollar_volume=1_500_000).as_dict()
    assert list(d) == ["rank", "top", "mom_n", "mom_skip", "vol_n", "pool", "sizing", "min_dollar_volume", "min_price", "trend"]
    assert (d["trend"], d["min_price"], d["min_dollar_volume"]) == ("none", "7.5", "1500000")


def test_int_floats_are_coerced():
    p = FactorParams("momentum", min_dollar_volume=0, min_price=5)
    assert isinstance(p.min_dollar_volume, float) and isinstance(p.min_price, float)


@pytest.mark.parametrize(
    "kw, exc",
    [
        ({"rank": "value"}, ValueError),
        ({"rank": 1}, TypeError),
        ({"top": 0}, ValueError),
        ({"top": 1001}, ValueError),
        ({"top": True}, TypeError),
        ({"top": 2.0}, TypeError),
        ({"mom_n": 1}, ValueError),
        ({"mom_skip": -1}, ValueError),
        ({"mom_n": 21, "mom_skip": 21}, ValueError),
        ({"vol_n": 1}, ValueError),
        ({"pool": 0}, ValueError),
        ({"rank": "mom_lowvol", "top": 11, "pool": 10}, ValueError),
        ({"sizing": "risk_parity"}, ValueError),
        ({"min_dollar_volume": -1.0}, ValueError),
        ({"min_dollar_volume": float("nan")}, ValueError),
        ({"min_dollar_volume": "1"}, TypeError),
        ({"min_price": 0.0}, ValueError),
        ({"min_price": float("inf")}, ValueError),
        ({"trend": ["SPY", 200]}, TypeError),
        ({"trend": ("SPY",)}, TypeError),
        ({"trend": ("", 200)}, ValueError),
        ({"trend": ("SPY", 0)}, ValueError),
        ({"trend": ("SPY", 200.0)}, TypeError),
    ],
)
def test_params_reject_bad_values(kw, exc):
    kw = {"rank": "momentum", **kw}
    with pytest.raises(exc):
        FactorParams(**kw)


def test_pool_below_top_is_fine_outside_mom_lowvol():
    assert FactorParams("momentum", top=20, pool=5).pool == 5


@pytest.mark.parametrize(
    "params, expected",
    [
        (FactorParams("momentum"), 253),
        (FactorParams("momentum", mom_n=126), 200),  # the SPY 200-day trend dominates
        (FactorParams("momentum", mom_n=126, trend=None), 127),
        (FactorParams("lowvol", vol_n=252), 253),
        (SMALL, 20),  # the 20-day dollar volume dominates
        (FactorParams("lowvol", trend=("SPY", 300)), 300),
    ],
)
def test_lookback_covers_every_window(params, expected):
    assert factor_lookback(params) == expected
    assert FACTOR.lookback(params) == expected


def test_symbols_holds_and_members():
    assert FACTOR.symbols(FactorParams("momentum")) == ("SPY",)
    assert FACTOR.symbols(FactorParams("momentum", trend=("QQQ", 100))) == ("QQQ",)
    assert FACTOR.symbols(FactorParams("momentum", trend=None)) == ()
    assert FACTOR.holds(FactorParams("momentum")) == ()
    assert FACTOR.uses_members(FactorParams("lowvol")) is True


def test_wrong_types_raise():
    days = session_days(30)
    history = {"AAA": hist("AAA", wiggle(30), days=days)}
    d = days[-1]
    with pytest.raises(TypeError):
        FACTOR.targets(history, {"AAA"}, d, frozenset(), object())
    with pytest.raises(TypeError):
        FACTOR.targets(history, {"AAA"}, d, ["AAA"], SMALL)
    with pytest.raises(TypeError):
        FACTOR.targets(history, {"AAA"}, datetime(2019, 2, 13), frozenset(), SMALL)
    with pytest.raises(TypeError):
        FACTOR.targets_prepared(object(), {"AAA"}, d, frozenset(), SMALL)
    with pytest.raises(TypeError):
        FACTOR.targets_prepared(FACTOR.prepare(history), {"AAA"}, d, frozenset(), "params")
    with pytest.raises(TypeError):
        FACTOR.lookback(None)


# ---- hand-computed features ----------------------------------------------------------------


def test_12_1_momentum_vol_and_dollar_volume_hand_computed():
    days = session_days(260)
    c = wiggle(260, growth=0.001)
    v = [1_000_000.0 + 1000.0 * t for t in range(260)]
    history = {"AAA": hist("AAA", c, days=days, volumes=v)}
    params = FactorParams("momentum", trend=None)
    [r] = factor_rows(history, {"AAA"}, days[-1], params)
    assert r.symbol == "AAA"
    assert r.close == c[-1]
    assert r.momentum == c[259 - 21] / c[259 - 252] - 1.0  # 12-1: skip the last month
    assert r.vol == py_stdev(c, 60)
    assert r.dollar_volume == py_dollar_volume(c, v)


def test_6_1_momentum_hand_computed():
    days = session_days(260)
    c = wiggle(260, growth=0.002)
    history = {"AAA": hist("AAA", c, days=days)}
    [r] = factor_rows(history, {"AAA"}, days[-1], FactorParams("momentum", mom_n=126, trend=None))
    assert r.momentum == c[259 - 21] / c[259 - 126] - 1.0


def test_vol_window_follows_vol_n():
    days = session_days(260)
    c = walk(3, 260)
    history = {"AAA": hist("AAA", c, days=days)}
    [r] = factor_rows(history, {"AAA"}, days[-1], FactorParams("lowvol", vol_n=252, trend=None))
    assert r.vol == py_stdev(c, 252)


def test_features_read_only_bars_through_data_date():
    days = session_days(40)
    c = wiggle(40, growth=0.01)
    history = {"AAA": hist("AAA", c, days=days)}
    d = days[29]
    [r] = factor_rows(history, {"AAA"}, d, SMALL)
    assert r.close == c[29]
    assert r.momentum == c[28] / c[24] - 1.0
    assert r.vol == py_stdev(c[:30], 3)
    assert factor_rows(upto_all(history, d), {"AAA"}, d, SMALL) == [r]


# ---- eligibility ---------------------------------------------------------------------------


def test_eligibility_each_condition():
    days = session_days(30)
    d = days[-1]
    history = {
        "OK": hist("OK", wiggle(30), days=days),
        "EXACT": hist("EXACT", wiggle(20), days=days[10:]),  # exactly lookback (20) bars through d
        "SHORT": hist("SHORT", wiggle(19), days=days[11:]),  # one bar short
        "GAP": hist("GAP", wiggle(29), days=days[:29]),  # no bar dated d
        "NONMEM": hist("NONMEM", wiggle(30), days=days),  # not a member
        "SPY": hist("SPY", wiggle(30, growth=0.05), days=days),  # a member here, never a target
        "FLAT": hist("FLAT", [50.0] * 30, days=days),  # volatility 0
    }
    members = frozenset(history) - {"NONMEM"} | {"ABSENT"}  # ABSENT has no history at all
    assert [r.symbol for r in factor_rows(history, members, d, SMALL)] == ["EXACT", "OK"]
    prepared = FACTOR.prepare(history)
    assert prepared.rows_on(members, d, SMALL) == factor_rows(history, members, d, SMALL)


def test_dollar_volume_floor_is_strict():
    days = session_days(30)
    c = wiggle(30)
    history = {"AAA": hist("AAA", c, days=days, volume=400_000.0)}
    dv = py_dollar_volume(c, [400_000.0] * 30)
    at = FactorParams("momentum", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=dv)
    below = FactorParams("momentum", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=dv - 1.0)
    assert factor_rows(history, {"AAA"}, days[-1], at) == []
    assert [r.symbol for r in factor_rows(history, {"AAA"}, days[-1], below)] == ["AAA"]


@pytest.mark.parametrize("last, eligible", [(5.0, True), (4.99, False), (5.01, True)])
def test_min_price_is_inclusive(last, eligible):
    days = session_days(30)
    c = wiggle(29, first=6.0, amp=0.1) + [last]
    history = {"AAA": hist("AAA", c, days=days)}
    got = factor_rows(history, {"AAA"}, days[-1], SMALL)
    assert bool(got) is eligible


# ---- rankings ------------------------------------------------------------------------------


def test_momentum_ranking_desc_with_symbol_tiebreak():
    rows = [row("CCC", 0.10, 0.02), row("BBB", 0.30, 0.01), row("AAA", 0.30, 0.03), row("DDD", -0.05, 0.01)]
    p = FactorParams("momentum", top=3)
    assert [r.symbol for r in rank_rows(rows, p)] == ["AAA", "BBB", "CCC"]


def test_lowvol_ranking_asc_with_symbol_tiebreak():
    rows = [row("CCC", 0.10, 0.02), row("BBB", 0.30, 0.01), row("AAA", -0.30, 0.01), row("DDD", 0.5, 0.05)]
    p = FactorParams("lowvol", top=3)
    assert [r.symbol for r in rank_rows(rows, p)] == ["AAA", "BBB", "CCC"]


def test_mom_lowvol_takes_the_lowest_vol_inside_the_momentum_pool():
    rows = [
        row("AAA", 0.30, 0.03),
        row("BBB", 0.20, 0.01),
        row("CCC", 0.10, 0.005),  # the calmest name, but outside the 3-name momentum pool
        row("DDD", 0.25, 0.02),
    ]
    p = FactorParams("mom_lowvol", top=2, pool=3)
    assert [r.symbol for r in rank_rows(rows, p)] == ["BBB", "DDD"]
    assert [r.symbol for r in rank_rows(rows, FactorParams("mom_lowvol", top=2, pool=4))] == ["CCC", "BBB"]


def test_mom_lowvol_pool_ties_by_symbol():
    rows = [row("BBB", 0.2, 0.01), row("AAA", 0.2, 0.02), row("CCC", 0.1, 0.001)]
    assert [r.symbol for r in rank_rows(rows, FactorParams("mom_lowvol", top=1, pool=1))] == ["AAA"]


def test_end_to_end_momentum_ranking_on_bars():
    days = session_days(30)
    history = {
        "AAA": hist("AAA", wiggle(30, growth=0.002), days=days),
        "BBB": hist("BBB", wiggle(30, growth=0.004), days=days),
        "CCC": hist("CCC", wiggle(30, growth=0.001), days=days),
        "TWIN": hist("TWIN", wiggle(30, growth=0.004), days=days),  # ties BBB exactly
    }
    got = FACTOR.targets(history, frozenset(history), days[-1], frozenset(), SMALL)
    assert [t.symbol for t in got] == ["BBB", "TWIN"]


def test_end_to_end_lowvol_ranking_on_bars():
    days = session_days(30)
    history = {
        "CALM": hist("CALM", wiggle(30, amp=0.05), days=days),
        "MID": hist("MID", wiggle(30, amp=0.2), days=days),
        "WILD": hist("WILD", wiggle(30, amp=1.0), days=days),
    }
    p = FactorParams("lowvol", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=0.0)
    got = FACTOR.targets(history, frozenset(history), days[-1], frozenset(), p)
    assert [t.symbol for t in got] == ["CALM", "MID"]


# ---- weights and targets -------------------------------------------------------------------


def test_equal_weights_use_top_even_when_fewer_names_qualify():
    chosen = [row("AAA", 0.3, 0.01), row("BBB", 0.2, 0.02)]
    assert factor_weights(chosen, FactorParams("momentum", top=4)) == [Decimal("0.25"), Decimal("0.25")]
    assert factor_weights(chosen, FactorParams("momentum", top=3)) == [equal_weight(3)] * 2
    assert factor_weights([], FactorParams("momentum", top=3)) == []


def test_inverse_vol_weights_hand_computed():
    chosen = [row("AAA", 0.3, 0.01), row("BBB", 0.2, 0.02)]
    full = FactorParams("momentum", top=2, sizing="inverse_vol")
    half = FactorParams("momentum", top=4, sizing="inverse_vol")
    assert factor_weights(chosen, full) == [Decimal("0.666666"), Decimal("0.333333")]  # 100/150, 50/150
    assert factor_weights(chosen, half) == [Decimal("0.333333"), Decimal("0.166666")]  # × 2/4


def test_inverse_vol_weights_are_quantized_and_sum_to_at_most_one():
    rng = np.random.default_rng(7)
    for top in (1, 3, 10, 20, 50):
        vols = rng.uniform(0.002, 0.08, top)
        chosen = [row(f"S{k:03d}", 0.1, float(v)) for k, v in enumerate(vols)]
        weights = factor_weights(chosen, FactorParams("momentum", top=top, sizing="inverse_vol"))
        assert all(w is not None and w > 0 and w % WEIGHT_QUANTUM == 0 for w in weights)
        assert sum(weights) <= Decimal(1)
        assert sum(weights) > Decimal(1) - Decimal(top) * WEIGHT_QUANTUM
        calmest = int(np.argmin(vols))
        assert weights[calmest] == max(weights)  # calmer -> heavier


def test_inverse_vol_drops_a_weight_that_floors_to_zero():
    chosen = [row("CALM", 0.3, 1e-9), row("WILD", 0.2, 1.0)]
    params = FactorParams("lowvol", top=2, sizing="inverse_vol")
    assert factor_weights(chosen, params) == [Decimal("0.999999"), None]
    assert [t.symbol for t in targets_from_rows(chosen, params)] == ["CALM"]


def test_targets_are_priced_at_the_close_without_brackets():
    days = session_days(30)
    c = wiggle(30, growth=0.003)
    history = {"AAA": hist("AAA", c, days=days), "BBB": hist("BBB", wiggle(30, growth=0.001), days=days)}
    got = FACTOR.targets(history, frozenset(history), days[-1], frozenset(), SMALL)
    assert got[0] == Target("AAA", equal_weight(2), q(to_decimal(c[-1])))
    assert all(t.limit is None and t.stop is None and t.take is None for t in got)
    assert sum(t.weight for t in got) <= 1


def test_members_only_and_spy_never_a_target():
    days = session_days(30)
    history = {
        "SPY": hist("SPY", wiggle(30, growth=0.02), days=days),  # the strongest momentum
        "AAA": hist("AAA", wiggle(30, growth=0.002), days=days),
        "OUT": hist("OUT", wiggle(30, growth=0.01), days=days),
    }
    members = frozenset({"SPY", "AAA"})
    for params in (SMALL, FactorParams("lowvol", top=3, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=0.0)):
        got = FACTOR.targets(history, members, days[-1], frozenset(), params)
        assert [t.symbol for t in got] == ["AAA"]
        assert FACTOR.targets_prepared(FACTOR.prepare(history), members, days[-1], frozenset(), params) == got


# ---- trend gate ----------------------------------------------------------------------------

TRENDED = FactorParams("momentum", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=("SPY", 10), min_dollar_volume=0.0)


def gate_history(spy: list[float] | None, spy_days: list[date] | None = None) -> tuple[list[date], dict[str, History]]:
    days = session_days(30)
    history = {"AAA": hist("AAA", wiggle(30, growth=0.002), days=days)}
    if spy is not None:
        history["SPY"] = hist("SPY", spy, days=spy_days or days[: len(spy)])
    return days, history


@pytest.mark.parametrize(
    "case, on",
    [
        ("rising", True),
        ("falling", False),
        ("flat", False),  # close == SMA: strict
        ("missing", False),
        ("no_bar_on_d", False),
        ("short", False),  # fewer than n bars through d
    ],
)
def test_trend_gate(case, on):
    days = session_days(30)
    spy = {
        "rising": ([100.0 + t for t in range(30)], days),
        "falling": ([200.0 - t for t in range(30)], days),
        "flat": ([100.0] * 30, days),
        "missing": (None, None),
        "no_bar_on_d": ([100.0 + t for t in range(29)], days[:29]),
        "short": ([100.0 + t for t in range(9)], days[21:]),
    }[case]
    _, history = gate_history(*spy)
    d = days[-1]
    assert trend_on(history, d, TRENDED) is on
    got = FACTOR.targets(history, frozenset({"AAA"}), d, frozenset(), TRENDED)
    assert bool(got) is on
    assert FACTOR.targets_prepared(FACTOR.prepare(history), frozenset({"AAA"}), d, frozenset(), TRENDED) == got


def test_trend_gate_reads_only_through_data_date():
    days = session_days(30)
    spy = [100.0 + t for t in range(25)] + [10.0] * 5  # collapses after days[24]
    _, history = gate_history(spy, days)
    assert trend_on(history, days[24], TRENDED) is True
    assert trend_on(history, days[29], TRENDED) is False


def test_no_trend_means_always_on():
    _, history = gate_history(None)
    assert trend_on(history, session_days(30)[-1], SMALL) is True


# ---- held semantics ------------------------------------------------------------------------


def test_held_names_are_kept_only_if_they_rank_in_the_new_top():
    days = session_days(30)
    history = {
        "AAA": hist("AAA", wiggle(30, growth=0.004), days=days),
        "BBB": hist("BBB", wiggle(30, growth=0.003), days=days),
        "CCC": hist("CCC", wiggle(30, growth=0.001), days=days),  # third: outside top 2
    }
    members = frozenset(history)
    d = days[-1]
    fresh = FACTOR.targets(history, members, d, frozenset(), SMALL)
    assert [t.symbol for t in fresh] == ["AAA", "BBB"]
    for held in (frozenset({"CCC"}), frozenset({"AAA", "CCC"}), frozenset({"AAA", "BBB"}), frozenset({"GONE"})):
        assert FACTOR.targets(history, members, d, held, SMALL) == fresh
        assert FACTOR.targets_prepared(FACTOR.prepare(history), members, d, held, SMALL) == fresh


# ---- P4 identity ---------------------------------------------------------------------------


def contract_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(330)
    history = {s: hist(s, walk(k, 330), days=days) for k, s in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"))}
    history["TWIN"] = hist("TWIN", [float(x) for x in history["AAA"].close], days=days)  # ties with AAA
    history["LATE"] = hist("LATE", walk(20, 250, first=30.0), days=days[80:])
    history["GONE"] = hist("GONE", walk(21, 280, first=70.0), days=days[:280])
    history["GAPPY"] = drop_days(hist("GAPPY", walk(22, 330), days=days), days[100:105] + [days[250]])
    history["THIN"] = hist("THIN", walk(23, 330), days=days, volume=1000.0)
    cheap = [5.0 + 0.6 * math.sin(t / 15.0) + (0.05 if t % 2 else -0.05) for t in range(330)]
    history["CHEAP"] = hist("CHEAP", cheap, days=days, volume=10_000_000.0)  # crosses min_price = 5 often
    history["SPY"] = hist("SPY", walk(30, 330, first=100.0, drift=0.0004, sigma=0.02), days=days)
    return days, history


def contract_members(days: list[date]):
    def members(d: date) -> frozenset[str]:
        out = {"AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "TWIN", "GONE", "GAPPY", "THIN", "CHEAP", "SPY"}
        if d >= days[200]:
            out.add("LATE")
        if days[240] <= d < days[260]:
            out.discard("BBB")
        return frozenset(out)

    return members


CONTRACT_PARAMS = [
    FactorParams("momentum", top=3, mom_n=40, mom_skip=5, vol_n=20, trend=None),
    FactorParams("lowvol", top=4, mom_n=40, mom_skip=5, vol_n=30, trend=("SPY", 30)),
    FactorParams("mom_lowvol", top=2, pool=5, mom_n=60, mom_skip=10, vol_n=20, sizing="inverse_vol", trend=("SPY", 50)),
    FactorParams("momentum", top=4, mom_n=20, mom_skip=0, vol_n=10, sizing="inverse_vol", trend=None),
]


@pytest.mark.parametrize("params", CONTRACT_PARAMS, ids=["mom", "lowvol-trend", "ml-ivol-trend", "mom-noskip-ivol"])
def test_prepared_rows_are_bit_identical_and_targets_equal(params):
    days, history = contract_set()
    members = contract_members(days)
    prepared = FACTOR.prepare(history)
    assert isinstance(prepared, FactorPrepared)
    nonempty = 0
    for d in days[15:]:
        visible = upto_all(history, d)
        m = members(d)
        rows = factor_rows(visible, m, d, params)
        assert prepared.rows_on(m, d, params) == rows, d  # bit-identical floats
        assert factor_rows(history, m, d, params) == rows, d  # later bars ignored
        for held in (frozenset(), frozenset({"AAA", "GONE"})):
            expected = FACTOR.targets(visible, m, d, held, params)
            assert FACTOR.targets_prepared(prepared, m, d, held, params) == expected, d
            assert FACTOR.targets(history, m, d, held, params) == expected, d
            assert sum(t.weight for t in expected) <= 1
            assert "SPY" not in {t.symbol for t in expected}
            nonempty += bool(expected)
    assert nonempty > 100


def test_default_params_identity_on_a_long_history():
    days, history = contract_set()
    members = contract_members(days)
    prepared = FACTOR.prepare(history)
    for params in (FactorParams("momentum"), FactorParams("mom_lowvol", top=3, pool=6, sizing="inverse_vol")):
        nonempty = 0
        for d in days[250:]:
            visible = upto_all(history, d)
            m = members(d)
            assert prepared.rows_on(m, d, params) == factor_rows(visible, m, d, params), d
            expected = FACTOR.targets(visible, m, d, frozenset(), params)
            assert FACTOR.targets_prepared(prepared, m, d, frozenset(), params) == expected, d
            nonempty += bool(expected)
        assert nonempty > 0


def test_prepared_caches_each_feature_column_once():
    days, history = contract_set()
    prepared = FACTOR.prepare(history)
    p = CONTRACT_PARAMS[0]
    prepared.rows_on(frozenset(history), days[100], p)
    col = prepared.column(("mom", p.mom_n, p.mom_skip))
    prepared.rows_on(frozenset(history), days[101], p)
    assert prepared.column(("mom", p.mom_n, p.mom_skip)) is col
    assert set(prepared.cache) == {("mom", 40, 5), ("vol", 20)}
    assert not col.flags.writeable


def test_prepare_on_short_or_empty_history():
    short = {"X": hist("X", wiggle(DV_N - 1))}
    d = session_days(DV_N - 1)[-1]
    for history in ({}, short):
        prepared = FACTOR.prepare(history)
        assert prepared.rows_on({"X"}, d, SMALL) == []
        assert FACTOR.targets_prepared(prepared, {"X"}, d, frozenset(), SMALL) == ()
        assert FACTOR.targets(history, {"X"}, d, frozenset(), SMALL) == ()


def test_allocatorkit_p4_identity():
    days, history = contract_set()
    members = contract_members(days)
    held_sets = [frozenset(), frozenset({"AAA", "GONE"})]
    assert assert_p4_identity(FACTOR, history, members, days[40::7], held_sets, CONTRACT_PARAMS) > 0


# ---- no look-ahead -------------------------------------------------------------------------


@pytest.mark.parametrize("mutation", ["change", "truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S leaves S's targets unchanged."""
    days, history = contract_set()
    members = contract_members(days)
    prepared = FACTOR.prepare(history)
    nonempty = 0
    for s in days[70::9]:
        data_date = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        else:
            future = {k: truncate_before(h, s) for k, h in history.items()}
        future_prepared = FACTOR.prepare(future)
        m = members(data_date)
        for params in CONTRACT_PARAMS:
            before = FACTOR.targets(history, m, data_date, frozenset(), params)
            assert FACTOR.targets(future, m, data_date, frozenset(), params) == before, s
            assert FACTOR.targets_prepared(future_prepared, m, data_date, frozenset(), params) == before, s
            assert FACTOR.targets_prepared(prepared, m, data_date, frozenset(), params) == before, s
            nonempty += bool(before)
    assert nonempty >= 10


def test_the_mutation_does_change_rows_read_on_s():
    # Guards test_no_look_ahead: the same mutation, read at data_date = S, changes the features.
    days, history = contract_set()
    members = contract_members(days)
    s = days[200]
    future = {k: mutate_from(h, s) for k, h in history.items()}
    p = CONTRACT_PARAMS[0]
    assert factor_rows(future, members(s), s, p) != factor_rows(history, members(s), s, p)


def test_allocatorkit_no_look_ahead():
    days, history = contract_set()
    members = contract_members(days)
    assert assert_no_lookahead(FACTOR, history, members, days[70::23], [frozenset()], CONTRACT_PARAMS) > 0
```
**Impact:** 78 new tests. No existing test is edited.

What the tests cover, mapped to the phase scope:

| Scope item | Tests |
|---|---|
| 12-1 momentum, 6-1 momentum, vol (`stdev_return_window`), dollar volume, hand-computed | `test_12_1_momentum_vol_and_dollar_volume_hand_computed`, `test_6_1_momentum_hand_computed`, `test_vol_window_follows_vol_n`, `test_features_read_only_bars_through_data_date` |
| `min_price` and dollar-volume eligibility | `test_min_price_is_inclusive` (3 cases), `test_dollar_volume_floor_is_strict`, `test_eligibility_each_condition` (lookback boundary, no bar on d, non-member, absent history, SPY, vol 0) |
| momentum/lowvol/mom_lowvol rankings with symbol tie-breaks; pool selection | `test_momentum_ranking_desc_with_symbol_tiebreak`, `test_lowvol_ranking_asc_with_symbol_tiebreak`, `test_mom_lowvol_takes_the_lowest_vol_inside_the_momentum_pool`, `test_mom_lowvol_pool_ties_by_symbol`, `test_end_to_end_momentum_ranking_on_bars` (TWIN tie), `test_end_to_end_lowvol_ranking_on_bars` |
| inverse_vol weights, floor-quantized, Σ <= 1 | `test_inverse_vol_weights_hand_computed`, `test_inverse_vol_weights_are_quantized_and_sum_to_at_most_one`, `test_inverse_vol_drops_a_weight_that_floors_to_zero`, `test_equal_weights_use_top_even_when_fewer_names_qualify` |
| trend gate | `test_trend_gate` (6 cases), `test_trend_gate_reads_only_through_data_date`, `test_no_trend_means_always_on` |
| members only; SPY never a target | `test_members_only_and_spy_never_a_target`; plus a `"SPY" not in targets` assert on every contract date |
| held semantics (rebalance) | `test_held_names_are_kept_only_if_they_rank_in_the_new_top`; plus `held={"AAA","GONE"}` in the contract loop |
| P4 identity with bit-identical features | `test_prepared_rows_are_bit_identical_and_targets_equal` (4 param sets × every date × 2 helds), `test_default_params_identity_on_a_long_history`, `test_allocatorkit_p4_identity` |
| no look-ahead | `test_no_look_ahead` (change and truncate), `test_the_mutation_does_change_rows_read_on_s` (the guard), `test_allocatorkit_no_look_ahead` |
| prepared mechanics | `test_prepared_caches_each_feature_column_once`, `test_prepare_on_short_or_empty_history` |
| params and protocol | `test_factor_implements_the_allocator_protocol`, `test_defaults_are_the_contract_values`, `test_as_dict_is_plain_and_ordered`, `test_int_floats_are_coerced`, `test_params_reject_bad_values` (23 cases), `test_pool_below_top_is_fine_outside_mom_lowvol`, `test_lookback_covers_every_window` (6 cases), `test_symbols_holds_and_members`, `test_wrong_types_raise` |

## Verification

**Pre-flight:** `engine/.venv` is the **worktree's** venv. `docker start seer-pg`.

**Build:**
```
engine/.venv/bin/python -c "from seer_engine.strategies.f_factor import FACTOR, FactorParams; print(FACTOR.id, FACTOR.lookback(FactorParams('momentum')))"
```
This prints `FAC 253`.

**Tests:**
- `engine/.venv/bin/pytest engine/tests/test_f_factor.py -q` gives **78 passed**.
- `engine/.venv/bin/pytest engine/tests/test_strategy_purity.py -q` passes. Its glob now
  includes `seer_engine.strategies.f_factor`.
- `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
  is green with **0 skipped**. The passed count is the post-phase-2 baseline + 78 (+ whatever
  phases 1–6 and 8 have added, if they landed first). Log the number.

**Manual check (prototype evidence, recorded while planning):**
- The module and these tests were prototyped against stand-ins for `Target`, `to_weight`,
  `equal_weight`, `target_from_close` and `return_window` that follow the index contract. 78/78
  passed in about 3.5 s. The two kit tests were later rewritten by the reconciler to phase 2's
  real kit API (D-E, same test count); if they fail on the real kit, fix the call, never the kit.
- Scale probe: 1,000 symbols × 5,000 sessions (about 3.7M prepared rows) on a synthetic market.
  - `prepare` takes 0.4 s.
  - A lazy column build plus 226 monthly `targets_prepared` calls takes 0.1–2.2 s per parameter
    set; `vol_n=252` is the slowest.
  - Peak RSS for the whole process, histories included, is about 590 MB.
- Re-run the scale probe on the real store if phase 12 reports memory pressure. `FactorPrepared`
  keeps a reference to the histories (no copy), plus about 9 columns × 3.7M rows.

**Frozen set check:** `git diff --stat 2546a92 -- <frozen paths from the index>` prints nothing.

**Exit criteria:** `seer_engine.strategies.f_factor` exists, and `test_f_factor.py` passes 78
tests. The purity glob covers the module. The full suite is green with 0 skipped. No file
outside the two above changed.

## Handoffs

- **Phase 11 (registry, R5):** import `from seer_engine.strategies.f_factor import FACTOR, FactorParams`.
  The module is not re-exported from `strategies/__init__.py`.
  - Rows 33–45 and 53 map to `FactorParams(rank=…)` with `rank ∈ {"momentum","lowvol","mom_lowvol"}`
    and `sizing="inverse_vol"` for row 38.
  - Row 37 (`mom_n=126`, trend on) has `lookback == 200`, because the SPY 200-day gate dominates.
- **Phase 9 (dev runner, R4/R5):**
  - `FACTOR.symbols(params)` is `("SPY",)` with the default trend, and `()` with `trend=None`.
  - `FACTOR.holds(params)` is always `()`, so FAC candidates contribute no `etf:` owner input.
  - One `FactorPrepared` can be shared by every FAC candidate. It lazily caches each
    (mom_n, mom_skip) and vol_n column.
- **Phase 2 (`VolTargetAllocator`/`BlendAllocator`):** their `LazyPrepared` calls
  `FACTOR.prepare(history)` once per wrapper id (about 0.4 s each), separately from the `FAC`
  candidates' own prepared value. That is harmless; phase 9's per-id cache (plan index D-D) does
  not dedupe it, by design. No action is required.
- **Phases 5, 6 and 8 (consistency):**
  - This phase renders `trend` in `as_dict` as `"SYMBOL:N"`, or `"none"`: the shared encoding
    (plan index D-F), which phases 5, 6 and 8 also use.
  - Its gate is off (cash) when the trend symbol lacks a bar on d or has fewer than n bars, as
    phases 6 and 8 do (phase 5 keeps a held hold on an unknown signal; see its decisions).
  - Phase 11's `candidate_digest` walks the dataclass fields (not `as_dict`), so the digests pin
    the field values themselves.
- **Phase 10 (report):** the survivorship caveat (D4) applies to F4/F5/F6 with full force.
  Momentum is flattered most of all (handover §4.B). This phase computes nothing about it; the
  report and the pre-registration must say it.

## Rollback

`git revert` this phase's commit, or delete `engine/src/seer_engine/strategies/f_factor.py` and
`engine/tests/test_f_factor.py`. Nothing else references them until phase 11, which depends on
this phase and would be reverted first.
