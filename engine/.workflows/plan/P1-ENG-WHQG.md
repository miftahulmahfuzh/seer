> Adopted from `STRATEGY_A_BACKTEST_PLAN.md` phase 1. Source: `.workflows/plan/strategy-a-backtest/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Strategy interface, indicators, Strategy A

**Plan set:** `STRATEGY_A_BACKTEST_PLAN.md`
**Analysis:** `20261003-144506-Q8N4_code_analyzer.md`
**Satisfies:** R1 — Strategy A signals from data through `data_date` only → ranked `sim.Pick`s, behind a small pure strategy interface shared with P4/P6
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

After this phase, `seer_engine.strategies` exists. It holds the `Strategy` protocol and the
`History` bar container (`base.py`), the four indicator window functions plus `rolling`
(`indicators.py`), and Strategy A (`a.py`), whose `picks()` (the nightly path) and
`prepare()`/`picks_prepared()` (the backtest fast path) return identical ranked `sim.Pick` lists
on every date. `seer_engine.backtest` exists as a docstring-only package. A globbing purity test
covers both packages, so the modules phases 2–4 add are policed without editing it. `numpy>=2` is
declared.

Every code block below was run in a scratch copy of the tree at `d3a2e1d`:
**74 new tests pass, and 4 deliberate bugs were each caught** (look-ahead in `features_at`, a
non-strict RSI comparison, a reversed tie-break, `prepare` using a different RSI window). At full
data scale (663 symbols × 2,955 sessions, synthetic), `prepare` takes 3.7 s and builds
1.83 M rows (102 MB). `picks_prepared` over all 2,756 eligible dates takes 0.64 s, and one
nightly `picks` call takes 8 ms.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.strategies.base`: `History` (frozen, slots, `eq=False`; `__len__`, `upto`, `last_date`, `index_of`), `history_from_bars(symbol, bars) -> History`, `Strategy` (a `typing.Protocol`, `@runtime_checkable`), `as_day(d) -> np.datetime64` (helper: `date` → `datetime64[D]`; `TypeError` for a `datetime` or a non-date).
- `seer_engine.strategies.indicators`: `sma_window`, `wilder_rsi_window`, `wilder_atr_window`, `mean_dollar_volume_window`, `rolling`.
- `seer_engine.strategies.a`: `LOOKBACK = 200`, `SMA_N = 200`, `RSI_N = 2`, `ATR_N = 14`, `DV_N = 20`, `AParams` (+ `as_dict`), `DESIGN_PARAMS`, `STRATEGY_A_PARAMS` (= `DESIGN_PARAMS`), `Features`, `features_at`, `picks_from_features`, **`APrepared`** (+ `features_on(data_date) -> list[Features]`), `prepare_a(history) -> APrepared`, `picks_prepared_a(prepared, members, data_date, params) -> list[Pick]`, `StrategyA`, `STRATEGY_A`.
- `seer_engine.strategies` (`__init__`) re-exports: `DESIGN_PARAMS, STRATEGY_A, STRATEGY_A_PARAMS, AParams, APrepared, Features, History, Strategy, StrategyA, features_at, history_from_bars, picks_from_features`.
- `seer_engine.backtest` (`__init__`): docstring only, no imports.
- `engine/tests/stratkit.py`: `START`, `session_days`, `hist`, `uptrend`, `dip`, `sawtooth`, `mutate_from`, `truncate_before`, `drop_days`, `feat`.
- Config: `numpy>=2` in `[project].dependencies`.

**Signature changes:** none (all new).

**Exact signatures, as implemented (match the index's shared contract):**
```python
# base.py
@dataclass(frozen=True, slots=True, eq=False)
class History:
    symbol: str; dates: np.ndarray; open: np.ndarray; high: np.ndarray
    low: np.ndarray; close: np.ndarray; volume: np.ndarray
    def __len__(self) -> int
    def upto(self, d: date) -> History            # returns self when nothing is cut
    def last_date(self) -> date | None
    def index_of(self, d: date) -> int | None
def history_from_bars(symbol: str, bars: Sequence[Bar]) -> History   # arrays read-only
class Strategy(Protocol):
    id: str; lookback: int
    def picks(self, history: Mapping[str, History], members: Set[str], data_date: date, params: Any) -> list[Pick]
    def prepare(self, history: Mapping[str, History]) -> Any
    def picks_prepared(self, prepared: Any, members: Set[str], data_date: date, params: Any) -> list[Pick]
# indicators.py
def sma_window(close: np.ndarray, n: int) -> np.ndarray
def wilder_rsi_window(close: np.ndarray, n: int) -> np.ndarray
def wilder_atr_window(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray
def mean_dollar_volume_window(close: np.ndarray, volume: np.ndarray, n: int) -> np.ndarray
def rolling(fn: Callable[..., np.ndarray], *series: np.ndarray, window: int, **kw: object) -> np.ndarray
# a.py
@dataclass(frozen=True, slots=True)
class AParams:
    rsi_max: float = 10.0; limit_atr: Decimal = Decimal("0.5"); tp_atr: Decimal = Decimal("1.0")
    sl_atr: Decimal = Decimal("1.5"); min_dollar_volume: float = 20_000_000.0
    def as_dict(self) -> dict[str, str]   # DESIGN_PARAMS -> {"rsi_max": "10", "limit_atr": "0.5", "tp_atr": "1",
                                          #   "sl_atr": "1.5", "min_dollar_volume": "20000000"} (normalized, fixed order)
def features_at(history: Mapping[str, History], data_date: date) -> list[Features]
def picks_from_features(features: Iterable[Features], members: Set[str], params: AParams) -> list[Pick]
class StrategyA: id = "A"; lookback = LOOKBACK   # prepare() -> APrepared
STRATEGY_A = StrategyA()
```
(`Set` is `collections.abc.Set`, the same type as `typing.AbstractSet` in the index.)

**Behaviour the other phases can rely on:**
- `AParams.__post_init__` coerces `rsi_max`/`min_dollar_volume` to `float` (an `int` is accepted, a `bool` or `str` is a `TypeError`), and requires the three ATR multipliers to be finite `Decimal`s (`float` → `TypeError`). Valid ranges: `0 < rsi_max ≤ 100`, `min_dollar_volume ≥ 0`, `limit_atr ≥ 0`, `tp_atr > 0`, `sl_atr > 0`. All 81 grid values of phase 4 satisfy these.
- `as_dict()` writes each value as a normalized plain decimal string: `Decimal("1.0")` → `"1"`, `Decimal("2.0")` → `"2"`, `5.0` → `"5"`, `Decimal("0.75")` → `"0.75"`. Phases 4 and 6 should render params through `as_dict()` and never format them by hand, so the report and `test_strategy_a_frozen.py` agree.
- `StrategyA.picks` and `picks_prepared` raise `TypeError` unless `params` is an `AParams`. `picks_prepared` also raises `TypeError` unless `prepared` is an `APrepared`.
- `picks()` filters `history` to `members` before it computes anything, and reads only the last 200 bars dated `<= data_date`. So `picks(H, …) == picks({s: h.upto(d)}, …)` even when `H` holds bars after `d`. Phase 3 may pass full histories.
- `prepare(history)` accepts any mapping, SPY included; non-members are simply never picked. Symbols with fewer than 200 bars contribute no rows. An empty mapping gives an empty `APrepared`, and `picks_prepared` on it returns `[]`.
- Every `Pick` returned is valid (`last, limit, tp, sl > 0`, `sl < limit < tp`). Invalid brackets are dropped silently, never raised. The list is uncapped and ranked `(rsi, symbol)` ascending, and held symbols are not filtered out (`size_picks` rejects them as `held`).
- The purity test also forbids an attribute named `random` (so `numpy.random` too) in every pure module. Later phases' pure modules must not use `np.random`.

**Requires (from earlier phases):** nothing.
**Leaves alone (owned by others):** `seer_engine/sim/*`, `tests/test_sim_purity.py`, `tests/simkit.py` (imported, not edited), `backtest/benchmark.py` (Phase 2), `backtest/market.py` + `runner.py` (Phase 3), `backtest/metrics.py` + `tuning.py` + `report.py` (Phase 4), `backtest/io.py` + `commands/backtest.py` + `.gitignore` (Phase 5), the **value** of `STRATEGY_A_PARAMS` + `engine/package_readme.md` + `docs/ROADMAP.md` + `docs/backtests/*` (Phase 6).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/pyproject.toml:12` | modify | add `"numpy>=2",` after the `pandas` line (line 12), inside `dependencies` (lines 10–17) |
| `engine/src/seer_engine/strategies/__init__.py` | create | package docstring + re-exports |
| `engine/src/seer_engine/strategies/base.py` | create | `History`, `history_from_bars`, `Strategy`, `as_day` |
| `engine/src/seer_engine/strategies/indicators.py` | create | the four window functions + `rolling` |
| `engine/src/seer_engine/strategies/a.py` | create | Strategy A: params, features, picks, prepared fast path |
| `engine/src/seer_engine/backtest/__init__.py` | create | docstring only, no imports |
| `engine/tests/stratkit.py` | create | synthetic `History`/`Features` builders |
| `engine/tests/test_indicators.py` | create | 21 tests |
| `engine/tests/test_strategy_a.py` | create | 50 tests |
| `engine/tests/test_strategy_purity.py` | create | 3 tests, glob-based |

Ten files in all: one modified and nine new.

## Implementation Steps

### Step 0: Worktree venv
**File:** none (environment)
**Change:** The worktree has no `engine/.venv`. From the worktree root:
```bash
cd /home/miftah/.worktrees/seer/strategy-a-backtest
python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
engine/.venv/bin/python -c "import seer_engine, numpy; print(seer_engine.__file__, numpy.__version__)"
# must print .../strategy-a-backtest/engine/src/seer_engine/__init__.py and a 2.x version
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
# baseline: 374 passed, 0 skipped
```
Never use `/home/miftah/seer/engine/.venv`. It is an editable install of the main checkout and would test the wrong tree.
**Impact:** none on the tree.

### Step 1: Declare numpy
**File:** `engine/pyproject.toml:12`
**Change:** Add one line after `"pandas>=2.2",`. numpy 2.4.6 is already installed transitively through pandas. This makes the direct import honest. After editing, re-run `engine/.venv/bin/pip install -e 'engine[dev]'` (a no-op install that records the dependency).
**Code:** the full `dependencies` block (lines 10–18 after the edit):
```toml
dependencies = [
  "psycopg[binary]>=3.2",
  "pandas>=2.2",
  "numpy>=2",
  "pandas_market_calendars>=5.0",
  "yfinance>=1.0",
  "requests>=2.32",
  "python-dotenv>=1.0",
]
```
**Impact:** none at runtime.

### Step 2: `strategies/base.py` — `History` and the `Strategy` protocol
**File:** `engine/src/seer_engine/strategies/base.py` (new)
**Change:** The bar container and the interface. Notes:
- `History.__post_init__` validates dtype (`datetime64[D]` dates, `float64` fields), equal 1-D shapes and strictly ascending dates. That is O(n) per construction, a few µs at 2,955 bars. `upto` slices views (no copy) and returns `self` when nothing is cut.
- `last_date()` uses `datetime64[D].item()`, which returns a `datetime.date`.
- `history_from_bars` marks its arrays read-only, so a `History` built from bars cannot be mutated after `prepare` reads it.
- `Strategy` is `@runtime_checkable`, so tests can assert `isinstance(STRATEGY_A, Strategy)`.
**Code:**
```python
"""The strategy interface shared by the backtest (P3), nightly paper trading (P4) and P6.

A strategy maps per-symbol daily bar history at a ``data_date`` close to a ranked
``list[sim.Pick]`` for the next session. Pure: no database, network, clock or randomness
(enforced by tests/test_strategy_purity.py).

``History`` holds one symbol's bars as float64 numpy arrays. Floats exist only in indicator
math and threshold comparisons; prices handed to the simulator are 4-dp Decimals.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

import numpy as np

from seer_engine.prices import Bar
from seer_engine.sim import Pick

_PRICE_FIELDS = ("open", "high", "low", "close", "volume")


def as_day(d: object) -> np.datetime64:
    """``d`` (a ``date``, not a ``datetime``) as ``numpy.datetime64[D]``."""
    if not isinstance(d, date) or isinstance(d, datetime):
        raise TypeError(f"expected a date, got {type(d).__name__}")
    return np.datetime64(d, "D")


@dataclass(frozen=True, slots=True, eq=False)
class History:
    """One symbol's daily bars, ascending, one row per bar the symbol has (gaps allowed)."""

    symbol: str
    dates: np.ndarray  # dtype datetime64[D], strictly ascending
    open: np.ndarray  # float64, same length as dates
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray  # float64

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError("symbol must be a non-empty str")
        if not isinstance(self.dates, np.ndarray) or self.dates.dtype != np.dtype("datetime64[D]"):
            raise TypeError(f"{self.symbol}: dates must be a datetime64[D] array")
        if self.dates.ndim != 1:
            raise ValueError(f"{self.symbol}: dates must be 1-D")
        n = self.dates.shape[0]
        for name in _PRICE_FIELDS:
            arr = getattr(self, name)
            if not isinstance(arr, np.ndarray) or arr.dtype != np.float64:
                raise TypeError(f"{self.symbol}: {name} must be a float64 array")
            if arr.shape != (n,):
                raise ValueError(f"{self.symbol}: {name} has shape {arr.shape}, dates has ({n},)")
        if n > 1 and not bool(np.all(self.dates[1:] > self.dates[:-1])):
            raise ValueError(f"{self.symbol}: dates must be strictly ascending")

    def __len__(self) -> int:
        return int(self.dates.shape[0])

    def upto(self, d: date) -> History:
        """The bars dated on or before ``d``, as views of this history's arrays."""
        end = int(np.searchsorted(self.dates, as_day(d), side="right"))
        if end == len(self):
            return self
        return History(
            self.symbol,
            self.dates[:end],
            self.open[:end],
            self.high[:end],
            self.low[:end],
            self.close[:end],
            self.volume[:end],
        )

    def last_date(self) -> date | None:
        """The date of the last bar, or None when there is none."""
        if len(self) == 0:
            return None
        return self.dates[-1].item()

    def index_of(self, d: date) -> int | None:
        """The row of the bar dated ``d``, or None when the symbol has no bar that day."""
        day = as_day(d)
        i = int(np.searchsorted(self.dates, day, side="left"))
        if i < len(self) and self.dates[i] == day:
            return i
        return None


def _readonly(arr: np.ndarray) -> np.ndarray:
    arr.setflags(write=False)
    return arr


def history_from_bars(symbol: str, bars: Sequence[Bar]) -> History:
    """A ``History`` from ``Bar`` objects of one symbol, ascending by date (float(Decimal) per field)."""
    for b in bars:
        if not isinstance(b, Bar):
            raise TypeError(f"expected a Bar, got {type(b).__name__}")
        if b.symbol != symbol:
            raise ValueError(f"bar for {b.symbol} in the history of {symbol}")
    return History(
        symbol,
        _readonly(np.array([b.date for b in bars], dtype="datetime64[D]")),
        _readonly(np.array([float(b.open) for b in bars], dtype=np.float64)),
        _readonly(np.array([float(b.high) for b in bars], dtype=np.float64)),
        _readonly(np.array([float(b.low) for b in bars], dtype=np.float64)),
        _readonly(np.array([float(b.close) for b in bars], dtype=np.float64)),
        _readonly(np.array([float(b.volume) for b in bars], dtype=np.float64)),
    )


@runtime_checkable
class Strategy(Protocol):
    """What the backtest and the nightly job call. Pure and deterministic.

    CONTRACT: for every date d,
    ``picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d) for s, h in H.items()}, M, d, p)``.
    ``picks`` may be given longer histories than ``lookback``, and histories with bars after
    ``data_date``; it reads only the last ``lookback`` bars dated on or before ``data_date``.
    """

    id: str
    lookback: int

    def picks(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]: ...

    def prepare(self, history: Mapping[str, History]) -> Any: ...

    def picks_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]: ...
```
**Impact:** new module; nothing imports it yet.

### Step 3: `strategies/indicators.py` — window functions
**File:** `engine/src/seer_engine/strategies/indicators.py` (new)
**Change:** These implement the Decisions row "Indicator definitions" exactly. The **bit-identity rule** is what makes P4 parity hold. Each function loops over the columns in Python and uses only elementwise ufuncs (`+ - * /`, `abs`, `maximum`, `where`, comparisons). IEEE-754 rounds each of these correctly per element, so SIMD versus scalar and 1 row versus 2,756 rows give the same bits. There is no `np.sum`, `mean`, `cumsum` or `convolve`, because numpy's pairwise summation changes its rounding with the length. `test_indicators.py` enforces the rule with an AST scan and proves its consequence with `==` on 401 windows × 4 indicators.
Wilder update: `avg = (avg * float(n-1) + x) / n`. RSI uses `np.where(no_loss, 100.0, 100 - 100/(1 + avgG/safe_avgL))`, so no divide-by-zero warning fires and `avgL == 0` (flat windows included) gives exactly 100.
**Code:**
```python
"""Indicator window functions: SMA, Wilder RSI, Wilder ATR, mean dollar volume. Pure numpy.

Every window function takes 2-D float64 arrays shaped ``(rows, W)``: one row per window, the
oldest bar in column 0. It returns one float64 per row, NaN for every row when ``W`` is too
short for ``n``.

Bit-identity rule: these functions use only elementwise numpy operations and an explicit
Python loop over the columns. No ``sum``/``mean``/``cumsum``/``convolve`` along the time axis,
because numpy's pairwise summation changes the rounding with the array length. So a row's
result is the same float, bit for bit, whether it is computed alone (the nightly job: one
window of the last bars) or among thousands of sliding windows (the backtest: ``rolling``).
tests/test_indicators.py enforces both the rule and its consequence.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def _matrix(name: str, x: np.ndarray) -> np.ndarray:
    if not isinstance(x, np.ndarray) or x.dtype != np.float64 or x.ndim != 2:
        raise ValueError(f"{name} must be a 2-D float64 array (rows, W)")
    return x


def _period(n: object) -> int:
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError(f"n must be an int >= 1, got {n!r}")
    return n


def _same_shape(*arrays: np.ndarray) -> None:
    shape = arrays[0].shape
    for a in arrays[1:]:
        if a.shape != shape:
            raise ValueError(f"window arrays differ in shape: {shape} vs {a.shape}")


def _nan_rows(x: np.ndarray) -> np.ndarray:
    return np.full(x.shape[0], np.nan, dtype=np.float64)


def _column_mean(x: np.ndarray, first: int, n: int) -> np.ndarray:
    """Mean of columns ``first .. first+n-1``, summed left to right, then divided by n."""
    acc = x[:, first].copy()
    for j in range(first + 1, first + n):
        acc = acc + x[:, j]
    return acc / n


def sma_window(close: np.ndarray, n: int) -> np.ndarray:
    """Simple mean of the last ``n`` closes: summed left to right, then divided by ``n``."""
    close = _matrix("close", close)
    n = _period(n)
    w = close.shape[1]
    if w < n:
        return _nan_rows(close)
    return _column_mean(close, w - n, n)


def wilder_rsi_window(close: np.ndarray, n: int) -> np.ndarray:
    """Wilder RSI(n) over the whole window, seeded at its start.

    Changes ``d_i = c_i - c_{i-1}`` for i = 1..W-1; gain = max(d, 0), loss = max(-d, 0).
    Seed avgG/avgL = mean of the first ``n`` gains/losses; then ``avg = (avg*(n-1) + x) / n``
    for every later change. RSI = 100 when avgL == 0, else ``100 - 100 / (1 + avgG/avgL)``.
    NaN when the window has fewer than ``n`` changes (``W < n + 1``).
    """
    close = _matrix("close", close)
    n = _period(n)
    w = close.shape[1]
    if w < n + 1:
        return _nan_rows(close)
    avg_gain = np.zeros(close.shape[0], dtype=np.float64)
    avg_loss = np.zeros(close.shape[0], dtype=np.float64)
    for i in range(1, n + 1):
        d = close[:, i] - close[:, i - 1]
        avg_gain = avg_gain + np.where(d > 0.0, d, 0.0)
        avg_loss = avg_loss + np.where(d < 0.0, -d, 0.0)
    avg_gain = avg_gain / n
    avg_loss = avg_loss / n
    keep = float(n - 1)
    for i in range(n + 1, w):
        d = close[:, i] - close[:, i - 1]
        avg_gain = (avg_gain * keep + np.where(d > 0.0, d, 0.0)) / n
        avg_loss = (avg_loss * keep + np.where(d < 0.0, -d, 0.0)) / n
    no_loss = avg_loss == 0.0
    rs = avg_gain / np.where(no_loss, 1.0, avg_loss)
    return np.where(no_loss, 100.0, 100.0 - 100.0 / (1.0 + rs))


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray, i: int) -> np.ndarray:
    prev = close[:, i - 1]
    return np.maximum(
        high[:, i] - low[:, i],
        np.maximum(np.abs(high[:, i] - prev), np.abs(low[:, i] - prev)),
    )


def wilder_atr_window(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
    """Wilder ATR(n) over the whole window, seeded at its start.

    ``TR_i = max(h_i - l_i, |h_i - c_{i-1}|, |l_i - c_{i-1}|)`` for i = 1..W-1 (the window's
    first bar has no TR). Seed = mean of the first ``n`` TRs; then ``atr = (atr*(n-1) + TR) / n``.
    NaN when the window has fewer than ``n`` TRs (``W < n + 1``).
    """
    high = _matrix("high", high)
    low = _matrix("low", low)
    close = _matrix("close", close)
    _same_shape(high, low, close)
    n = _period(n)
    w = close.shape[1]
    if w < n + 1:
        return _nan_rows(close)
    atr = _true_range(high, low, close, 1)
    for i in range(2, n + 1):
        atr = atr + _true_range(high, low, close, i)
    atr = atr / n
    keep = float(n - 1)
    for i in range(n + 1, w):
        atr = (atr * keep + _true_range(high, low, close, i)) / n
    return atr


def mean_dollar_volume_window(close: np.ndarray, volume: np.ndarray, n: int) -> np.ndarray:
    """Mean of ``close * volume`` over the last ``n`` bars, summed left to right."""
    close = _matrix("close", close)
    volume = _matrix("volume", volume)
    _same_shape(close, volume)
    n = _period(n)
    w = close.shape[1]
    if w < n:
        return _nan_rows(close)
    first = w - n
    acc = close[:, first] * volume[:, first]
    for j in range(first + 1, w):
        acc = acc + close[:, j] * volume[:, j]
    return acc / n


def rolling(fn: Callable[..., np.ndarray], *series: np.ndarray, window: int, **kw: object) -> np.ndarray:
    """``fn`` over every sliding window of ``window`` bars of 1-D ``series``.

    Returns a length-T float64 array: NaN for t < window - 1, else ``fn`` applied to the
    ``window`` bars ending at t. Bit-identical to calling ``fn`` on that one window alone.
    """
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError(f"window must be an int >= 1, got {window!r}")
    if not series:
        raise ValueError("rolling needs at least one series")
    for s in series:
        if not isinstance(s, np.ndarray) or s.dtype != np.float64 or s.ndim != 1:
            raise ValueError("rolling series must be 1-D float64 arrays")
    t = series[0].shape[0]
    if any(s.shape[0] != t for s in series):
        raise ValueError("rolling series differ in length")
    out = np.full(t, np.nan, dtype=np.float64)
    if t >= window:
        views = [sliding_window_view(s, window) for s in series]
        out[window - 1 :] = fn(*views, **kw)
    return out
```
**Impact:** new module.

### Step 4: `strategies/a.py` — Strategy A
**File:** `engine/src/seer_engine/strategies/a.py` (new)
**Change:**
- `features_at` keeps symbols with a bar **on** `data_date` and `index + 1 >= LOOKBACK`. It stacks their last 200 bars into `(k, 200)` arrays and calls each window function once. Every indicator therefore sees exactly the 200-bar window, and Wilder RSI and ATR are seeded at the window's first bar. RSI(2) uses all 199 changes, ATR(14) all 199 TRs, SMA all 200 closes, and DV the last 20.
- `prepare_a` runs `rolling(fn, …, window=LOOKBACK, …)` per symbol over its whole history. **The window must be `LOOKBACK` for every indicator, RSI and ATR included, never `n + 1`.** Otherwise the Wilder seed point moves and the floats differ from `features_at` (mutation 4 in the Goal proves the test catches this). Rows from index 199 on are concatenated (symbols in sorted order) and stable-argsorted by date, so each date's rows are contiguous and in symbol order. Columns are read-only.
- `picks_prepared_a` slices one date's rows with two `searchsorted` calls and applies a vectorized pre-filter with the same strict comparisons (`>`, `<`, `>`). It builds `Features` only for survivors that are members, then hands them to `picks_from_features`, which re-checks every condition. So the result is by construction `picks_from_features(features_on(d), members, params)`, and the test proves `features_on(d) == features_at(upto(d), d)` bit for bit.
- `_bracket`: `last = to_decimal(close)`, `atr = to_decimal(atr)`, then `limit`/`tp`/`sl` through `sim.q`. A candidate is dropped when `last ≤ 0`, `limit ≤ 0`, `sl ≤ 0`, `sl ≥ limit` or `tp ≤ limit`. `last ≤ 0` extends the Decisions "Invalid picks" row for the same reason as `sl ≤ 0`: `Pick` requires every price > 0, and a close below 0.00005 rounds to 0.
- `STRATEGY_A_PARAMS: AParams = DESIGN_PARAMS` with the marker comment Phase 6 replaces.
**Code:**
```python
"""Strategy A: buy a short, sharp dip in an uptrend (design §4).

Setup, on ``data_date`` (all strict):
    close > SMA(200),  Wilder RSI(2) < ``rsi_max``,  20-day mean close×volume > ``min_dollar_volume``.
Bracket, in Decimal at 4 dp (``sim.q``), from ``last = to_decimal(close)`` and ``atr = to_decimal(ATR14)``:
    limit = q(last − limit_atr·atr),  tp = q(limit + tp_atr·atr),  sl = q(limit − sl_atr·atr).
A candidate is dropped when, after rounding, last ≤ 0, limit ≤ 0, sl ≤ 0, sl ≥ limit or tp ≤ limit.
Ranking: RSI(2) ascending, then symbol ascending. Every qualifying candidate is returned; the
simulator fills free slots in this order and rejects held symbols without using a slot.

Eligibility: a member on ``data_date``, a bar dated ``data_date``, and at least ``LOOKBACK``
bars through it. Every indicator is a function of the symbol's last ``LOOKBACK`` bars ending at
``data_date`` only (Wilder recursions are seeded inside that window), so the backtest and the
nightly job compute bit-identical floats however much history either one loads.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.prices import to_decimal
from seer_engine.sim import Pick, q
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    rolling,
    sma_window,
    wilder_atr_window,
    wilder_rsi_window,
)

LOOKBACK = 200
SMA_N = 200
RSI_N = 2
ATR_N = 14
DV_N = 20


def _plain(x: float | Decimal) -> str:
    """``x`` as a plain decimal string without trailing zeros: 10.0 -> "10", Decimal("0.50") -> "0.5"."""
    d = Decimal(repr(x)) if isinstance(x, float) else x
    return format(d.normalize(), "f")


@dataclass(frozen=True, slots=True)
class AParams:
    """Strategy A's tunable parameters. Defaults are the design §4 values."""

    rsi_max: float = 10.0  # setup: RSI(2) < rsi_max (strict)
    limit_atr: Decimal = Decimal("0.5")  # limit = last − limit_atr × ATR
    tp_atr: Decimal = Decimal("1.0")  # tp    = limit + tp_atr × ATR
    sl_atr: Decimal = Decimal("1.5")  # sl    = limit − sl_atr × ATR
    min_dollar_volume: float = 20_000_000.0  # setup: 20-day mean close×volume > this (strict)

    def __post_init__(self) -> None:
        for name in ("rsi_max", "min_dollar_volume"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError(f"{name} must be a float, got {type(v).__name__}")
            v = float(v)
            if not np.isfinite(v):
                raise ValueError(f"{name} must be finite, got {v!r}")
            object.__setattr__(self, name, v)
        if not 0.0 < self.rsi_max <= 100.0:
            raise ValueError(f"rsi_max must be in (0, 100], got {self.rsi_max}")
        if self.min_dollar_volume < 0.0:
            raise ValueError(f"min_dollar_volume must be >= 0, got {self.min_dollar_volume}")
        for name in ("limit_atr", "tp_atr", "sl_atr"):
            v = getattr(self, name)
            if not isinstance(v, Decimal):
                raise TypeError(f"{name} must be a Decimal, got {type(v).__name__}")
            if not v.is_finite():
                raise ValueError(f"{name} must be finite, got {v!r}")
        if self.limit_atr < 0:
            raise ValueError(f"limit_atr must be >= 0, got {self.limit_atr}")
        if self.tp_atr <= 0 or self.sl_atr <= 0:
            raise ValueError(f"tp_atr and sl_atr must be > 0, got {self.tp_atr}, {self.sl_atr}")

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain decimal string, in a fixed key order (report and P4 params)."""
        return {
            "rsi_max": _plain(self.rsi_max),
            "limit_atr": _plain(self.limit_atr),
            "tp_atr": _plain(self.tp_atr),
            "sl_atr": _plain(self.sl_atr),
            "min_dollar_volume": _plain(self.min_dollar_volume),
        }


DESIGN_PARAMS = AParams()
STRATEGY_A_PARAMS: AParams = DESIGN_PARAMS  # phase 6 replaces this with the frozen selection


@dataclass(frozen=True, slots=True)
class Features:
    """Strategy A's indicator values for one symbol at one ``data_date`` close."""

    symbol: str
    data_date: date
    close: float
    sma: float
    rsi: float
    atr: float
    dollar_volume: float


def features_at(history: Mapping[str, History], data_date: date) -> list[Features]:
    """Features of every eligible symbol on ``data_date``, sorted by symbol.

    Eligible: a bar dated ``data_date`` and at least ``LOOKBACK`` bars through it. Computed on
    the last ``LOOKBACK`` bars ending at ``data_date``; later bars are never read.
    """
    as_day(data_date)
    symbols: list[str] = []
    rows: list[int] = []
    for symbol in sorted(history):
        h = history[symbol]
        i = h.index_of(data_date)
        if i is None or i + 1 < LOOKBACK:
            continue
        symbols.append(symbol)
        rows.append(i)
    if not symbols:
        return []

    def stack(field: str) -> np.ndarray:
        return np.stack(
            [getattr(history[s], field)[i + 1 - LOOKBACK : i + 1] for s, i in zip(symbols, rows, strict=True)]
        )

    close, high, low, volume = stack("close"), stack("high"), stack("low"), stack("volume")
    sma = sma_window(close, SMA_N)
    rsi = wilder_rsi_window(close, RSI_N)
    atr = wilder_atr_window(high, low, close, ATR_N)
    dv = mean_dollar_volume_window(close, volume, DV_N)
    last = close[:, -1]
    return [
        Features(s, data_date, float(last[k]), float(sma[k]), float(rsi[k]), float(atr[k]), float(dv[k]))
        for k, s in enumerate(symbols)
    ]


def _setup(f: Features, params: AParams) -> bool:
    return f.close > f.sma and f.rsi < params.rsi_max and f.dollar_volume > params.min_dollar_volume


def _bracket(f: Features, params: AParams) -> Pick | None:
    last = to_decimal(f.close)
    atr = to_decimal(f.atr)
    limit = q(last - params.limit_atr * atr)
    tp = q(limit + params.tp_atr * atr)
    sl = q(limit - params.sl_atr * atr)
    if last <= 0 or limit <= 0 or sl <= 0 or sl >= limit or tp <= limit:
        return None
    return Pick(f.symbol, last, limit, tp, sl)


def picks_from_features(features: Iterable[Features], members: Set[str], params: AParams) -> list[Pick]:
    """Ranked picks: members passing the setup with a valid bracket, by (RSI, symbol) ascending."""
    if not isinstance(params, AParams):
        raise TypeError(f"params must be AParams, got {type(params).__name__}")
    ranked: list[tuple[float, str, Pick]] = []
    for f in features:
        if f.symbol not in members or not _setup(f, params):
            continue
        pick = _bracket(f, params)
        if pick is not None:
            ranked.append((f.rsi, f.symbol, pick))
    ranked.sort(key=lambda r: (r[0], r[1]))
    return [pick for _, _, pick in ranked]


@dataclass(frozen=True, slots=True, eq=False)
class APrepared:
    """Strategy A's param-independent features for every eligible (symbol, date) of a history.

    Columnar, ordered by (date, symbol). Built once by ``StrategyA.prepare``; every grid run reads it.
    """

    symbols: tuple[str, ...]  # sorted; ``sym`` indexes into it
    dates: np.ndarray  # datetime64[D], ascending
    sym: np.ndarray  # int64
    close: np.ndarray  # float64 columns, one row per eligible (symbol, date)
    sma: np.ndarray
    rsi: np.ndarray
    atr: np.ndarray
    dollar_volume: np.ndarray

    def _rows(self, data_date: date) -> tuple[int, int]:
        day = as_day(data_date)
        lo = int(np.searchsorted(self.dates, day, side="left"))
        hi = int(np.searchsorted(self.dates, day, side="right"))
        return lo, hi

    def _features(self, k: int, data_date: date) -> Features:
        return Features(
            self.symbols[int(self.sym[k])],
            data_date,
            float(self.close[k]),
            float(self.sma[k]),
            float(self.rsi[k]),
            float(self.atr[k]),
            float(self.dollar_volume[k]),
        )

    def features_on(self, data_date: date) -> list[Features]:
        """Every eligible symbol's features on ``data_date``, sorted by symbol (== ``features_at``)."""
        lo, hi = self._rows(data_date)
        return [self._features(k, data_date) for k in range(lo, hi)]


def prepare_a(history: Mapping[str, History]) -> APrepared:
    """Rolling Strategy A features over every symbol's whole history (see ``APrepared``)."""
    symbols = tuple(sorted(history))
    parts: dict[str, list[np.ndarray]] = {k: [] for k in ("dates", "sym", "close", "sma", "rsi", "atr", "dv")}
    for k, symbol in enumerate(symbols):
        h = history[symbol]
        if len(h) < LOOKBACK:
            continue
        start = LOOKBACK - 1
        parts["dates"].append(h.dates[start:])
        parts["sym"].append(np.full(len(h) - start, k, dtype=np.int64))
        parts["close"].append(h.close[start:])
        parts["sma"].append(rolling(sma_window, h.close, window=LOOKBACK, n=SMA_N)[start:])
        parts["rsi"].append(rolling(wilder_rsi_window, h.close, window=LOOKBACK, n=RSI_N)[start:])
        parts["atr"].append(rolling(wilder_atr_window, h.high, h.low, h.close, window=LOOKBACK, n=ATR_N)[start:])
        parts["dv"].append(rolling(mean_dollar_volume_window, h.close, h.volume, window=LOOKBACK, n=DV_N)[start:])
    if not parts["dates"]:
        empty = np.empty(0, dtype=np.float64)
        return APrepared(
            symbols, np.empty(0, dtype="datetime64[D]"), np.empty(0, dtype=np.int64), empty, empty, empty, empty, empty
        )
    dates = np.concatenate(parts["dates"])
    order = np.argsort(dates, kind="stable")  # symbols were appended in sorted order

    def col(key: str) -> np.ndarray:
        arr = np.concatenate(parts[key])[order]
        arr.setflags(write=False)
        return arr

    return APrepared(
        symbols, col("dates"), col("sym"), col("close"), col("sma"), col("rsi"), col("atr"), col("dv")
    )


def picks_prepared_a(prepared: APrepared, members: Set[str], data_date: date, params: AParams) -> list[Pick]:
    """``picks_from_features`` on ``prepared``'s rows for ``data_date``, with a vectorized pre-filter.

    The pre-filter applies the same strict comparisons as ``picks_from_features``, which
    re-checks every survivor, so the result is exactly ``picks_from_features(features_on(d), ...)``.
    """
    if not isinstance(prepared, APrepared):
        raise TypeError(f"prepared must be APrepared, got {type(prepared).__name__}")
    if not isinstance(params, AParams):
        raise TypeError(f"params must be AParams, got {type(params).__name__}")
    lo, hi = prepared._rows(data_date)
    if lo == hi:
        return []
    window = slice(lo, hi)
    mask = (
        (prepared.close[window] > prepared.sma[window])
        & (prepared.rsi[window] < params.rsi_max)
        & (prepared.dollar_volume[window] > params.min_dollar_volume)
    )
    candidates = []
    for j in np.flatnonzero(mask):
        k = lo + int(j)
        if prepared.symbols[int(prepared.sym[k])] in members:
            candidates.append(prepared._features(k, data_date))
    return picks_from_features(candidates, members, params)


class StrategyA:
    """Strategy A behind the ``Strategy`` protocol."""

    id = "A"
    lookback = LOOKBACK

    def picks(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        if not isinstance(params, AParams):
            raise TypeError(f"params must be AParams, got {type(params).__name__}")
        member_history = {s: h for s, h in history.items() if s in members}
        return picks_from_features(features_at(member_history, data_date), members, params)

    def prepare(self, history: Mapping[str, History]) -> APrepared:
        return prepare_a(history)

    def picks_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        return picks_prepared_a(prepared, members, data_date, params)


STRATEGY_A = StrategyA()
```
**Impact:** new module. The purity test (Step 7) covers it.

### Step 5: Package `__init__` files
**File:** `engine/src/seer_engine/strategies/__init__.py` (new)
**Code:**
```python
"""Trading strategies: pure functions from daily bar history to ranked ``sim.Pick``s.

``base`` holds the interface every strategy implements (P3 Strategy A, P6 B and C) and the
``History`` bar container; ``indicators`` the window functions; ``a`` Strategy A. Pure: no
database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from seer_engine.strategies.a import (
    DESIGN_PARAMS,
    STRATEGY_A,
    STRATEGY_A_PARAMS,
    AParams,
    APrepared,
    Features,
    StrategyA,
    features_at,
    picks_from_features,
)
from seer_engine.strategies.base import History, Strategy, history_from_bars

__all__ = [
    "DESIGN_PARAMS",
    "STRATEGY_A",
    "STRATEGY_A_PARAMS",
    "AParams",
    "APrepared",
    "Features",
    "History",
    "Strategy",
    "StrategyA",
    "features_at",
    "history_from_bars",
    "picks_from_features",
]
```
**File:** `engine/src/seer_engine/backtest/__init__.py` (new; docstring only, **no imports**)
**Code:**
```python
"""Seer backtest (P3): Strategy A over the point-in-time universe through the simulator.

Every module here except ``io`` is pure: no database, network, clock or randomness
(tests/test_strategy_purity.py). ``io`` and ``seer_engine.commands.backtest`` are the only
places that read the database or write files. See engine/package_readme.md.
"""
```
**Impact:** `import seer_engine.backtest` now works. Phases 2–5 add modules next to it.

### Step 6: `tests/stratkit.py` — synthetic builders
**File:** `engine/tests/stratkit.py` (new)
**Change:** These builders are shared with phases 3 and 4 (they may import them, and must not edit this file without a reconciler note). Dates are real NYSE sessions from `seer_engine.dates.sessions`, so `prev_session` lines up. `hist()` defaults: open = close, high/low = close ± 0.5, volume 1e6.
**Code:**
```python
"""Builders for strategy and backtest tests: synthetic ``History`` series and ``Features``.

Shared by tests/test_indicators.py, tests/test_strategy_a.py and the backtest tests. Dates are
real NYSE sessions (``seer_engine.dates``) so ``prev_session``/``next_session`` line up.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date

import numpy as np

from seer_engine.dates import sessions
from seer_engine.strategies.a import Features
from seer_engine.strategies.base import History

START = date(2019, 1, 2)


def session_days(n: int, start: date = START) -> list[date]:
    """The first ``n`` NYSE sessions on or after ``start``."""
    days = sessions(start, date(start.year + n // 200 + 2, 12, 31))
    assert len(days) >= n, "calendar range too short"
    return days[:n]


def _f64(values: Sequence[float]) -> np.ndarray:
    return np.asarray(values, dtype=np.float64)


def hist(
    symbol: str,
    closes: Sequence[float],
    *,
    days: Sequence[date] | None = None,
    start: date = START,
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    opens: Sequence[float] | None = None,
    volumes: Sequence[float] | None = None,
    spread: float = 0.5,
    volume: float = 1_000_000.0,
) -> History:
    """A History of ``closes`` on consecutive sessions from ``start`` (or on ``days``).

    Defaults: open = close, high = close + spread, low = close - spread, constant volume.
    """
    n = len(closes)
    days = list(days) if days is not None else session_days(n, start)
    assert len(days) == n, "one day per close"
    c = _f64(closes)
    return History(
        symbol,
        np.array(days, dtype="datetime64[D]"),
        _f64(opens) if opens is not None else c.copy(),
        _f64(highs) if highs is not None else c + spread,
        _f64(lows) if lows is not None else c - spread,
        c,
        _f64(volumes) if volumes is not None else np.full(n, volume, dtype=np.float64),
    )


def uptrend(n: int, first: float = 100.0, step: float = 0.1) -> list[float]:
    """``first, first+step, ...``: a steady rise (RSI(2) = 100, close > SMA200)."""
    return [first + step * t for t in range(n)]


def dip(closes: Sequence[float], at: int, drop: float = 1.0, days: int = 2) -> list[float]:
    """``closes`` with ``days`` consecutive drops of ``drop`` ending at index ``at``; later bars shift too."""
    out = list(closes)
    for t in range(at - days + 1, len(out)):
        out[t] -= drop * min(t - (at - days), days)
    return out


def sawtooth(n: int, first: float = 100.0, up: float = 1.2, down: float = 0.8) -> list[float]:
    """Alternating +up / -down closes: a rising trend whose RSI(2) is always strictly between 0 and 100."""
    out = [first]
    for t in range(1, n):
        out.append(out[-1] + (up if t % 2 else -down))
    return out


def mutate_from(h: History, d: date, fn: Callable[[np.ndarray], np.ndarray] = lambda x: x * 3.0 + 7.0) -> History:
    """``h`` with every price and volume of the bars dated on or after ``d`` replaced by ``fn(value)``."""
    cut = int(np.searchsorted(h.dates, np.datetime64(d, "D"), side="left"))

    def change(arr: np.ndarray) -> np.ndarray:
        out = arr.copy()
        out[cut:] = fn(out[cut:])
        return out

    return History(h.symbol, h.dates.copy(), change(h.open), change(h.high), change(h.low), change(h.close), change(h.volume))


def truncate_before(h: History, d: date) -> History:
    """``h`` without its bars dated on or after ``d`` (as if they never arrived)."""
    cut = int(np.searchsorted(h.dates, np.datetime64(d, "D"), side="left"))
    return History(h.symbol, h.dates[:cut], h.open[:cut], h.high[:cut], h.low[:cut], h.close[:cut], h.volume[:cut])


def drop_days(h: History, gone: Sequence[date]) -> History:
    """``h`` without the bars dated in ``gone`` (a gap in the symbol's history)."""
    keep = ~np.isin(h.dates, np.array(list(gone), dtype="datetime64[D]"))
    return History(h.symbol, h.dates[keep], h.open[keep], h.high[keep], h.low[keep], h.close[keep], h.volume[keep])


def feat(
    symbol: str = "AAA",
    *,
    data_date: date = START,
    close: float = 50.0,
    sma: float = 40.0,
    rsi: float = 5.0,
    atr: float = 1.0,
    dollar_volume: float = 100_000_000.0,
) -> Features:
    """A ``Features`` row that passes the design setup unless a field is overridden."""
    return Features(symbol, data_date, close, sma, rsi, atr, dollar_volume)
```

### Step 7: `tests/test_strategy_purity.py` — globbing purity test (3 tests)
**File:** `engine/tests/test_strategy_purity.py` (new; modelled on `test_sim_purity.py`, which stays untouched)
**Change:** Globs `strategies/*.py` and `backtest/*.py` minus `backtest/io.py`. It imports **every** globbed module in a fresh interpreter and checks `sys.modules`, then AST-scans the sources. It adds `"random"` to the forbidden attributes (catches `np.random`) on top of the sim test's list (invariant 5).
**Code:**
```python
"""Strategy and backtest core modules are pure (handover §6.8, plan invariant 2).

Globs ``seer_engine/strategies/*.py`` and ``seer_engine/backtest/*.py`` (every module except
``backtest/io.py``, the one impure edge), so modules added later are covered without editing
this file.

- Importing them in a fresh interpreter loads no psycopg, requests or yfinance, and never
  seer_engine.bars (which imports psycopg).
- Their source never reads the clock, draws random numbers, logs, prints or opens files.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import seer_engine

FORBIDDEN_MODULES = ("psycopg", "requests", "yfinance", "seer_engine.bars")
FORBIDDEN_IMPORT_ROOTS = {"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib", "socket"}
FORBIDDEN_ATTRS = {"now", "utcnow", "today", "fromtimestamp", "random"}  # "random" catches numpy.random
FORBIDDEN_CALLS = {"print", "open", "input"}
IMPURE = {("backtest", "io.py")}

PKG = Path(seer_engine.__file__).resolve().parent


def _pure_sources() -> list[Path]:
    files = []
    for package in ("strategies", "backtest"):
        files += [p for p in sorted((PKG / package).glob("*.py")) if (package, p.name) not in IMPURE]
    return files


def _module_name(path: Path) -> str:
    parts = ["seer_engine", path.parent.name]
    if path.stem != "__init__":
        parts.append(path.stem)
    return ".".join(parts)


def _fresh_python(code: str) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG.parent) + os.pathsep + env.get("PYTHONPATH", "")
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=120,
    )
    return out.stdout.strip()


def test_the_glob_finds_the_strategy_modules():
    names = {_module_name(p) for p in _pure_sources()}
    assert {
        "seer_engine.strategies",
        "seer_engine.strategies.base",
        "seer_engine.strategies.indicators",
        "seer_engine.strategies.a",
        "seer_engine.backtest",
    } <= names
    assert "seer_engine.backtest.io" not in names


def test_pure_modules_load_no_db_or_network_module():
    modules = sorted(_module_name(p) for p in _pure_sources())
    code = (
        "import importlib, sys\n"
        f"for m in {modules!r}:\n"
        "    importlib.import_module(m)\n"
        f"bad = [m for m in {FORBIDDEN_MODULES!r} if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    assert _fresh_python(code) == ""


def test_pure_sources_have_no_clock_randomness_or_io():
    problems: list[str] = []
    for path in _pure_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            where = f"{path.parent.name}/{path.name}:{getattr(node, 'lineno', '?')}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_IMPORT_ROOTS or alias.name == "seer_engine.bars":
                        problems.append(f"{where} import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS or node.module == "seer_engine.bars":
                    problems.append(f"{where} from {node.module} import ...")
                if node.module == "seer_engine" and any(a.name == "bars" for a in node.names):
                    problems.append(f"{where} from seer_engine import bars")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
                problems.append(f"{where} .{node.attr}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                problems.append(f"{where} {node.func.id}()")
    assert problems == []
```

### Step 8: `tests/test_indicators.py` (21 tests)
**File:** `engine/tests/test_indicators.py` (new)
**Hand computations** (also in the test comments):

| Case | Input | Expected |
|---|---|---|
| SMA(3) | `[1,2,3,4,5]` | `(3+4+5)/3 = 4.0`; `[1,2]` → NaN; `[1,2,3]` → 2.0 |
| RSI(2) Wilder | `[10, 11, 10.5, 12, 11]` → Δ `+1, −0.5, +1.5, −1` | seed G 0.5, L 0.25 → G 1.0, L 0.125 → G 0.5, L 0.5625 → `800/17 = 47.0588…` (`approx rel 1e-12`; float result is 1 ulp off `800/17`). A simple-average RSI would give 60 |
| RSI warm-up | `[10, 11]` / `[10, 11, 10.5]` | NaN / seed only `200/3` |
| RSI extremes | rising / falling / flat | `100 / 0 / 100` exactly |
| ATR(2) Wilder | H `10.5 11 11.25 12.5 11.5`, L `9.5 10 10.75 12 11`, C `10 10.75 11 12.25 11.25` | TR `1, 0.5, 1.5 (gap up), 1.25 (gap down)`; seed 0.75 → 1.125 → **1.1875** exactly |
| ATR warm-up | first 2 / first 3 bars | NaN / 0.75 |
| TR branches (n=1, prev close 10) | (10.5, 9.5) / (12, 11.5) / (8.5, 8) | 1.0 / 2.0 / 2.0 |
| DV(2) | C `10 20 30 40`, V `100 200 300 400` | `(9000+16000)/2 = 12500`; one bar → NaN; two → 2500 |

**Code:**
```python
"""Indicator window functions (handover §6.1) and the bit-identity rule behind P4 parity."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pytest

import seer_engine.strategies.indicators as ind
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    rolling,
    sma_window,
    wilder_atr_window,
    wilder_rsi_window,
)


def rows(*r: list[float]) -> np.ndarray:
    return np.array(r, dtype=np.float64)


# ---- SMA -----------------------------------------------------------------------------------


def test_sma_is_the_mean_of_the_last_n_closes():
    # (3 + 4 + 5) / 3 = 4; columns 1 and 2 are ignored.
    assert sma_window(rows([1, 2, 3, 4, 5]), 3).tolist() == [4.0]


def test_sma_warm_up_boundary():
    assert math.isnan(sma_window(rows([1, 2]), 3)[0])  # W = n - 1: no value
    assert sma_window(rows([1, 2, 3]), 3).tolist() == [2.0]  # W = n: first value


# ---- Wilder RSI ----------------------------------------------------------------------------


def test_wilder_rsi_hand_computed():
    # closes 10, 11, 10.5, 12, 11 -> changes +1, -0.5, +1.5, -1 (n = 2)
    # seed:  avgG = (1 + 0)/2 = 0.5          avgL = (0 + 0.5)/2 = 0.25
    # i = 3: avgG = (0.5*1 + 1.5)/2 = 1.0    avgL = (0.25*1 + 0)/2 = 0.125
    # i = 4: avgG = (1.0*1 + 0)/2 = 0.5      avgL = (0.125*1 + 1)/2 = 0.5625
    # RSI = 100 - 100/(1 + 0.5/0.5625) = 100 - 900/17 = 800/17 = 47.0588...
    # (A simple-average RSI(2) over the last two changes would give 60: Wilder is pinned.)
    assert wilder_rsi_window(rows([10, 11, 10.5, 12, 11]), 2)[0] == pytest.approx(800 / 17, rel=1e-12)


def test_wilder_rsi_warm_up_boundary():
    assert math.isnan(wilder_rsi_window(rows([10, 11]), 2)[0])  # 1 change < n = 2
    # W = n + 1: seed only. avgG = 0.5, avgL = 0.25 -> 100 - 100/3
    assert wilder_rsi_window(rows([10, 11, 10.5]), 2)[0] == pytest.approx(200 / 3, rel=1e-12)


def test_wilder_rsi_extremes():
    out = wilder_rsi_window(rows([1, 2, 3, 4], [4, 3, 2, 1], [5, 5, 5, 5]), 2)
    assert out.tolist() == [100.0, 0.0, 100.0]  # no loss -> 100 (flat included); no gain -> 0


# ---- Wilder ATR ----------------------------------------------------------------------------

H = [10.5, 11.0, 11.25, 12.5, 11.5]
L = [9.5, 10.0, 10.75, 12.0, 11.0]
C = [10.0, 10.75, 11.0, 12.25, 11.25]


def test_wilder_atr_hand_computed():
    # TR1 = max(11-10, |11-10|, |10-10|)              = 1.0
    # TR2 = max(11.25-10.75, |11.25-10.75|, |10.75-10.75|) = 0.5
    # TR3 = max(0.5, |12.5-11| = 1.5, |12-11| = 1)    = 1.5   (gap up: previous close counts)
    # TR4 = max(0.5, |11.5-12.25| = 0.75, |11-12.25| = 1.25) = 1.25 (gap down)
    # seed (n = 2) = (1 + 0.5)/2 = 0.75; then (0.75 + 1.5)/2 = 1.125; then (1.125 + 1.25)/2 = 1.1875
    assert wilder_atr_window(rows(H), rows(L), rows(C), 2).tolist() == [1.1875]


def test_wilder_atr_warm_up_boundary():
    assert math.isnan(wilder_atr_window(rows(H[:2]), rows(L[:2]), rows(C[:2]), 2)[0])  # 1 TR < n
    assert wilder_atr_window(rows(H[:3]), rows(L[:3]), rows(C[:3]), 2).tolist() == [0.75]  # seed only


@pytest.mark.parametrize(
    ("h1", "l1", "expected"),
    [
        (10.5, 9.5, 1.0),  # high - low dominates
        (12.0, 11.5, 2.0),  # |high - prev close| dominates (gap up)
        (8.5, 8.0, 2.0),  # |low - prev close| dominates (gap down)
    ],
)
def test_true_range_uses_the_previous_close(h1, l1, expected):
    # prev close = 10; n = 1 so the ATR is the single TR of the second bar
    assert wilder_atr_window(rows([10.2, h1]), rows([9.8, l1]), rows([10.0, 10.0]), 1).tolist() == [expected]


# ---- Dollar volume -------------------------------------------------------------------------


def test_mean_dollar_volume_hand_computed():
    # close*volume = 1000, 4000, 9000, 16000; last 2 -> (9000 + 16000)/2
    assert mean_dollar_volume_window(rows([10, 20, 30, 40]), rows([100, 200, 300, 400]), 2).tolist() == [12500.0]


def test_mean_dollar_volume_warm_up_boundary():
    assert math.isnan(mean_dollar_volume_window(rows([10]), rows([100]), 2)[0])
    assert mean_dollar_volume_window(rows([10, 20]), rows([100, 200]), 2).tolist() == [2500.0]


# ---- rows are independent, rolling, bit identity -------------------------------------------


def test_each_row_is_its_own_window():
    out = sma_window(rows([1, 2, 3], [10, 20, 30], [0, 0, 6]), 2)
    assert out.tolist() == [2.5, 25.0, 3.0]


def test_rolling_pads_the_warm_up_with_nan():
    out = rolling(sma_window, np.array([1, 2, 3, 4, 5], dtype=np.float64), window=3, n=3)
    assert np.isnan(out[:2]).all()
    assert out[2:].tolist() == [2.0, 3.0, 4.0]


def test_rolling_on_a_series_shorter_than_the_window_is_all_nan():
    out = rolling(sma_window, np.array([1, 2], dtype=np.float64), window=3, n=3)
    assert out.shape == (2,) and np.isnan(out).all()


def _random_bars(seed: int, t: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    close = np.round(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, t))), 4)
    high = np.round(close * (1.0 + rng.uniform(0.0, 0.03, t)), 4)
    low = np.round(close * (1.0 - rng.uniform(0.0, 0.03, t)), 4)
    volume = np.round(rng.uniform(1e5, 5e7, t))
    return high, low, close, volume


CASES = [
    ("sma", sma_window, ("c",), {"n": 200}),
    ("rsi", wilder_rsi_window, ("c",), {"n": 2}),
    ("atr", wilder_atr_window, ("h", "l", "c"), {"n": 14}),
    ("dv", mean_dollar_volume_window, ("c", "v"), {"n": 20}),
]


@pytest.mark.parametrize(("name", "fn", "fields", "kw"), CASES, ids=[c[0] for c in CASES])
def test_rolling_is_bit_identical_to_one_window(name, fn, fields, kw):
    """``rolling(...)[t]`` == ``fn`` on the 200 bars ending at t alone, with ``==``, not approx."""
    h, l, c, v = _random_bars(7, 600)  # noqa: E741
    series = {"h": h, "l": l, "c": c, "v": v}
    args = [series[f] for f in fields]
    out = rolling(fn, *args, window=200, **kw)
    assert np.isnan(out[:199]).all()
    for t in range(199, 600):
        alone = fn(*[a[None, t - 199 : t + 1].copy() for a in args], **kw)
        assert alone[0] == out[t], f"{name} differs at t={t}"
    # and among a different number of rows (12 stacked windows)
    picked = list(range(199, 600, 37))
    stacked = fn(*[np.stack([a[t - 199 : t + 1] for t in picked]) for a in args], **kw)
    assert stacked.tolist() == out[picked].tolist()


def test_window_functions_reject_one_dimensional_input():
    with pytest.raises(ValueError, match="2-D"):
        sma_window(np.array([1.0, 2.0]), 2)
    with pytest.raises(ValueError, match="n must be"):
        sma_window(rows([1.0, 2.0]), 0)
    with pytest.raises(ValueError, match="window"):
        rolling(sma_window, np.array([1.0, 2.0]), window=0, n=1)


FORBIDDEN_REDUCTIONS = {"sum", "mean", "cumsum", "nansum", "nanmean", "convolve", "average", "reduce", "einsum", "dot"}


def test_indicators_use_no_reduction_along_the_time_axis():
    """The bit-identity rule: only elementwise ops and an explicit column loop."""
    path = Path(ind.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = [
        f"{path.name}:{node.lineno} .{node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_REDUCTIONS
    ]
    assert found == []
```

### Step 9: `tests/test_strategy_a.py` (50 tests)
**File:** `engine/tests/test_strategy_a.py` (new)
**Hand computations:**
- **Line** (closes 1..200, H/L ±0.5, vol 1000): SMA = 100.5, RSI = 100, TR = max(1, 1.5, 0.5) = 1.5 → ATR = 1.5, DV = 1000·mean(181..200) = 190,500. All are exact floats.
- **Dip in uptrend** (`100 + 0.1t`, two net −0.9 days at t = 228, 229; data_date = day 229): close 120.9; SMA 112.95 − 0.015 = 112.935; RSI: G 0.1→0.05→0.025, L 0→0.45→0.675, RSI = 100 − 100/(1 + 1/27) = 100/28 = 3.5714…; ATR: TR 1.0 rising and 1.4 on drops, (13 + 1.4)/14 then (14.4·13/14 + 1.4)/14 = 206.8/196 = 1.05510…; DV = 121.8e6. Bracket: ATR → 1.0551, limit = q(120.9 − 0.52755) = **120.3725**, tp = q(120.3725 + 1.0551) = **121.4276**, sl = q(120.3725 − 1.58265) = q(118.78985) = **118.7899** (half-up).
- **Bracket at 4 dp** (close 50): ATR 1.2345 → limit q(49.38275) = 49.3828, tp 50.6173, sl q(47.53105) = 47.5311. ATR 1.23456789 → 1.2346 first → limit 49.3827, tp 50.6173, sl 47.5308. Params (0.25, 1.5, 2.0) with ATR 2: 49.5 / 52.5 / 45.5.
- **Invalid**: limit < 0, limit = 0, sl = 0, ATR 0, ATR rounds to 0, `sl_atr` 0.25 × ATR 0.0001 (sl rounds onto limit), `tp_atr` 0.25 × ATR 0.0001 (tp rounds onto limit), last rounds to 0. All return `[]`, and none raises.

Coverage of the exit criteria: setup filter, each condition alone (9 parametrized cases, strict boundaries included); ranking with the symbol tie-break, uncapped (6 candidates); non-members; JOIN at day 220 and LEAVE at day 240 checked on every date 199..259 through both paths; no look-ahead for every S in days 200..259, mutating **or** deleting every bar dated ≥ S across 3 symbols × 2 param sets × 3 code paths, with a non-vacuity guard and a companion test proving the mutation is visible at data_date = S; and the `picks_prepared == picks(upto)` contract on every date 190..319 of a 6-symbol set (late start, gaps, early end, thin volume, membership changes) under 3 param sets, plus `features_on == features_at` bit-identical.
**Code:**
```python
"""Strategy A and the strategy interface (handover §6.1–§6.3, plan Decisions)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from simkit import P, bar
from stratkit import (
    dip,
    drop_days,
    feat,
    hist,
    mutate_from,
    sawtooth,
    session_days,
    truncate_before,
    uptrend,
)

from seer_engine.dates import prev_session
from seer_engine.sim import Pick
from seer_engine.strategies import (
    DESIGN_PARAMS,
    STRATEGY_A,
    AParams,
    APrepared,
    History,
    Strategy,
    features_at,
    history_from_bars,
    picks_from_features,
)
from seer_engine.strategies.a import ATR_N, DV_N, LOOKBACK, RSI_N, SMA_N

PERMISSIVE = AParams(rsi_max=100.0)  # every RSI(2) strictly below 100 passes


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


# ---- params and identity -------------------------------------------------------------------


def test_design_params_are_the_design_values():
    assert (SMA_N, RSI_N, ATR_N, DV_N, LOOKBACK) == (200, 2, 14, 20, 200)
    assert DESIGN_PARAMS == AParams(10.0, Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), 20_000_000.0)
    assert DESIGN_PARAMS.as_dict() == {
        "rsi_max": "10",
        "limit_atr": "0.5",
        "tp_atr": "1",
        "sl_atr": "1.5",
        "min_dollar_volume": "20000000",
    }


def test_as_dict_is_plain_and_ordered():
    p = AParams(rsi_max=5, limit_atr=Decimal("0.25"), tp_atr=Decimal("0.75"), sl_atr=Decimal("2.0"))
    assert p.rsi_max == 5.0 and isinstance(p.rsi_max, float)
    assert list(p.as_dict().items()) == [
        ("rsi_max", "5"),
        ("limit_atr", "0.25"),
        ("tp_atr", "0.75"),
        ("sl_atr", "2"),
        ("min_dollar_volume", "20000000"),
    ]


@pytest.mark.parametrize(
    ("kw", "exc"),
    [
        ({"limit_atr": 0.5}, TypeError),
        ({"rsi_max": "10"}, TypeError),
        ({"rsi_max": 0.0}, ValueError),
        ({"rsi_max": 100.5}, ValueError),
        ({"tp_atr": Decimal("0")}, ValueError),
        ({"sl_atr": Decimal("-1")}, ValueError),
        ({"limit_atr": Decimal("-0.1")}, ValueError),
        ({"min_dollar_volume": -1.0}, ValueError),
    ],
)
def test_aparams_rejects_bad_values(kw, exc):
    with pytest.raises(exc):
        AParams(**kw)


def test_strategy_a_implements_the_protocol():
    assert isinstance(STRATEGY_A, Strategy)
    assert (STRATEGY_A.id, STRATEGY_A.lookback) == ("A", 200)


def test_wrong_param_or_prepared_types_raise():
    h = {"S": hist("S", sawtooth(210))}
    d = h["S"].last_date()
    with pytest.raises(TypeError):
        STRATEGY_A.picks(h, {"S"}, d, {"rsi_max": 10})
    with pytest.raises(TypeError):
        STRATEGY_A.picks_prepared(object(), {"S"}, d, DESIGN_PARAMS)
    with pytest.raises(TypeError):
        STRATEGY_A.picks_prepared(STRATEGY_A.prepare(h), {"S"}, d, None)


# ---- History -------------------------------------------------------------------------------


def test_history_upto_last_date_and_index_of():
    h = hist("X", [1.0, 2.0, 3.0, 4.0], days=[date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 7), date(2020, 1, 8)])
    assert len(h) == 4 and h.last_date() == date(2020, 1, 8)
    assert h.index_of(date(2020, 1, 7)) == 2
    assert h.index_of(date(2020, 1, 6)) is None  # a gap
    assert h.index_of(date(2020, 1, 9)) is None
    cut = h.upto(date(2020, 1, 6))
    assert len(cut) == 2 and cut.last_date() == date(2020, 1, 3) and cut.close.tolist() == [1.0, 2.0]
    assert h.upto(date(2020, 2, 1)) is h
    assert len(h.upto(date(2019, 12, 31))) == 0 and h.upto(date(2019, 12, 31)).last_date() is None


def test_history_validates_its_arrays():
    days = np.array([date(2020, 1, 3), date(2020, 1, 2)], dtype="datetime64[D]")
    one = np.ones(2, dtype=np.float64)
    with pytest.raises(ValueError, match="ascending"):
        History("X", days, one, one, one, one, one)
    with pytest.raises(TypeError, match="float64"):
        History("X", days[::-1], one, one, one, np.ones(2, dtype=np.int64), one)
    with pytest.raises(ValueError, match="shape"):
        History("X", days[::-1], one, one, one, np.ones(3), one)
    with pytest.raises(TypeError, match="datetime64"):
        History("X", np.array([1, 2]), one, one, one, one, one)


def test_history_from_bars_converts_decimals_to_floats():
    bars = [bar("X", "2020-01-02", "10", "11", "9.5", "10.1234", 500), bar("X", "2020-01-03", "10", "12", "9", "11", 7)]
    h = history_from_bars("X", bars)
    assert h.dates.tolist() == [date(2020, 1, 2), date(2020, 1, 3)]
    assert h.close.tolist() == [10.1234, 11.0] and h.volume.tolist() == [500.0, 7.0]
    assert h.high.tolist() == [11.0, 12.0] and h.low.tolist() == [9.5, 9.0] and h.open.tolist() == [10.0, 10.0]
    assert not h.close.flags.writeable
    with pytest.raises(ValueError, match="bar for Y"):
        history_from_bars("X", [bar("Y", "2020-01-02", "1", "1", "1", "1")])


# ---- features ------------------------------------------------------------------------------


def test_features_hand_computed_on_a_line():
    # closes 1..200, high = c + 0.5, low = c - 0.5, volume 1000
    # SMA200 = mean(1..200) = 100.5; RSI = 100 (no loss); TR = max(1, 1.5, 0.5) = 1.5 -> ATR 1.5;
    # dollar volume = 1000 * mean(181..200) = 190500
    h = {"LIN": hist("LIN", [float(t + 1) for t in range(200)], volume=1000.0)}
    d = h["LIN"].last_date()
    [f] = features_at(h, d)
    assert (f.symbol, f.data_date, f.close, f.sma, f.rsi, f.atr, f.dollar_volume) == (
        "LIN", d, 200.0, 100.5, 100.0, 1.5, 190500.0,
    )


def test_eligibility_needs_lookback_bars_and_a_bar_on_data_date():
    days = session_days(201)
    closes = sawtooth(201)
    h199 = {"X": hist("X", closes[:199], days=days[:199])}
    h200 = {"X": hist("X", closes[:200], days=days[:200])}
    assert features_at(h199, days[198]) == []  # 199 bars: not yet
    assert [f.symbol for f in features_at(h200, days[199])] == ["X"]  # 200 bars: eligible
    gappy = {"X": drop_days(hist("X", closes, days=days), [days[200]])}
    assert features_at(gappy, days[200]) == []  # no bar on data_date


def test_features_read_only_the_last_lookback_bars():
    days = session_days(300)
    tail = sawtooth(200, first=150.0)
    a = {"X": hist("X", [50.0 + t for t in range(100)] + tail, days=days)}
    b = {"X": hist("X", [999.0 - t for t in range(100)] + tail, days=days)}
    c = {"X": hist("X", tail, days=days[100:])}
    assert features_at(a, days[-1]) == features_at(b, days[-1]) == features_at(c, days[-1])


def test_features_are_sorted_by_symbol():
    h = {s: hist(s, sawtooth(200)) for s in ("MMM", "AAA", "ZZZ")}
    assert [f.symbol for f in features_at(h, h["AAA"].last_date())] == ["AAA", "MMM", "ZZZ"]


def test_dip_in_uptrend_hand_computed():
    # uptrend 100 + 0.1 t, then two days each net -0.9 at t = 228, 229 (data_date = day 229).
    # close  = 100 + 22.9 - 2 = 120.9
    # SMA200 = mean(100 + 0.1 t, t = 30..229) - (1 + 2)/200 = 112.95 - 0.015 = 112.935
    # RSI(2): avgG 0.1 -> 0.05 -> 0.025, avgL 0 -> 0.45 -> 0.675; 100 - 100/(1 + 1/27) = 100/28
    # ATR(14): TR 1.0 on rising days, 1.4 on the drops; (13 + 1.4)/14, then (14.4/14·13 + 1.4)/14 = 206.8/196
    # DV = 1e6 · (mean(100 + 0.1 t, t = 210..229) - 0.15) = 121.8e6
    days = session_days(230)
    h = {"DIP": hist("DIP", dip(uptrend(230), 229), days=days)}
    [f] = features_at(h, days[229])
    assert f.close == pytest.approx(120.9, rel=1e-12)
    assert f.sma == pytest.approx(112.935, rel=1e-12)
    assert f.rsi == pytest.approx(100 / 28, rel=1e-9)
    assert f.atr == pytest.approx(206.8 / 196, rel=1e-12)
    assert f.dollar_volume == pytest.approx(121.8e6, rel=1e-12)
    # last = 120.9000, ATR -> 1.0551; limit = q(120.9 - 0.52755) = 120.3725 (half-up)
    # tp = q(120.3725 + 1.0551) = 121.4276; sl = q(120.3725 - 1.58265) = 118.7899
    assert STRATEGY_A.picks(h, {"DIP"}, days[229], DESIGN_PARAMS) == [
        Pick("DIP", P("120.9"), P("120.3725"), P("121.4276"), P("118.7899"))
    ]


# ---- setup filter, each condition alone ----------------------------------------------------


@pytest.mark.parametrize(
    ("kw", "passes"),
    [
        ({}, True),
        ({"close": 40.0, "sma": 40.0}, False),  # close == SMA: strict
        ({"close": 39.0, "sma": 40.0}, False),  # below trend
        ({"rsi": 10.0}, False),  # RSI exactly rsi_max: strict
        ({"rsi": 9.999999}, True),
        ({"rsi": 50.0}, False),
        ({"dollar_volume": 20_000_000.0}, False),  # exactly the floor: strict
        ({"dollar_volume": 20_000_000.5}, True),
        ({"dollar_volume": 5_000_000.0}, False),
    ],
)
def test_setup_filter_each_condition_alone(kw, passes):
    out = picks_from_features([feat("AAA", **kw)], {"AAA"}, DESIGN_PARAMS)
    assert [p.symbol for p in out] == (["AAA"] if passes else [])


# ---- bracket prices ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("atr", "limit", "tp", "sl"),
    [
        # atr 1.2345: limit = q(50 - 0.61725) = 49.3828; tp = q(49.3828 + 1.2345) = 50.6173;
        # sl = q(49.3828 - 1.85175) = q(47.53105) = 47.5311 (half-up)
        (1.2345, "49.3828", "50.6173", "47.5311"),
        # ATR is quantized first: 1.23456789 -> 1.2346; limit = q(50 - 0.6173) = 49.3827;
        # tp = q(49.3827 + 1.2346) = 50.6173; sl = q(49.3827 - 1.8519) = 47.5308
        (1.23456789, "49.3827", "50.6173", "47.5308"),
    ],
)
def test_bracket_prices_at_four_dp(atr, limit, tp, sl):
    [pick] = picks_from_features([feat("AAA", close=50.0, atr=atr)], {"AAA"}, DESIGN_PARAMS)
    assert pick == Pick("AAA", P("50"), P(limit), P(tp), P(sl))


def test_bracket_follows_the_params():
    # limit = 50 - 0.25·2 = 49.5; tp = 49.5 + 1.5·2 = 52.5; sl = 49.5 - 2.0·2 = 45.5
    p = AParams(limit_atr=Decimal("0.25"), tp_atr=Decimal("1.5"), sl_atr=Decimal("2.0"))
    assert picks_from_features([feat("AAA", close=50.0, atr=2.0)], {"AAA"}, p) == [
        Pick("AAA", P("50"), P("49.5"), P("52.5"), P("45.5"))
    ]


@pytest.mark.parametrize(
    ("close", "atr", "params"),
    [
        (1.0, 3.0, DESIGN_PARAMS),  # limit = 1 - 1.5 < 0
        (1.0, 2.0, DESIGN_PARAMS),  # limit = 0
        (1.0, 0.5, DESIGN_PARAMS),  # limit 0.75, sl = 0.75 - 0.75 = 0
        (50.0, 0.0, DESIGN_PARAMS),  # zero ATR: sl == limit == tp
        (50.0, 0.00004, DESIGN_PARAMS),  # ATR rounds to 0.0000
        (50.0, 0.0001, AParams(sl_atr=Decimal("0.25"))),  # sl = q(50.0000 - 0.000025) == limit
        (50.0, 0.0001, AParams(tp_atr=Decimal("0.25"))),  # tp = q(50.0000 + 0.000025) == limit
        (0.00004, 0.00001, DESIGN_PARAMS),  # last rounds to 0.0000
    ],
)
def test_invalid_brackets_are_dropped_not_raised(close, atr, params):
    assert picks_from_features([feat("AAA", close=close, sma=close / 2, atr=atr)], {"AAA"}, params) == []


# ---- ranking and membership ----------------------------------------------------------------


def test_ranking_is_rsi_then_symbol_and_uncapped():
    features = [
        feat("MMM", rsi=3.0),
        feat("ZZZ", rsi=1.0),
        feat("AAA", rsi=3.0),
        feat("BBB", rsi=7.0),
        feat("CCC", rsi=2.0),
        feat("DDD", rsi=9.5),
    ]
    out = picks_from_features(features, {f.symbol for f in features}, DESIGN_PARAMS)
    assert [p.symbol for p in out] == ["ZZZ", "CCC", "AAA", "MMM", "BBB", "DDD"]


def test_non_members_are_excluded():
    features = [feat("AAA", rsi=1.0), feat("BBB", rsi=2.0)]
    assert [p.symbol for p in picks_from_features(features, {"BBB"}, DESIGN_PARAMS)] == ["BBB"]
    assert picks_from_features(features, frozenset(), DESIGN_PARAMS) == []


def test_symbols_joining_and_leaving_mid_window():
    days = session_days(260)
    history = {s: hist(s, sawtooth(260, first=f), days=days) for s, f in (("STAY", 100.0), ("JOIN", 80.0), ("LEAVE", 60.0))}
    join, leave = days[220], days[240]

    def members(d: date) -> frozenset[str]:
        return frozenset({"STAY"} | ({"JOIN"} if d >= join else set()) | ({"LEAVE"} if d < leave else set()))

    prepared = STRATEGY_A.prepare(history)
    for d in days[199:]:
        expected = sorted(members(d))
        got = STRATEGY_A.picks(history, members(d), d, PERMISSIVE)
        assert sorted(p.symbol for p in got) == expected, d
        assert STRATEGY_A.picks_prepared(prepared, members(d), d, PERMISSIVE) == got, d


# ---- no look-ahead -------------------------------------------------------------------------


def lookahead_set() -> dict[str, History]:
    days = session_days(260)
    return {
        "DIP": hist("DIP", dip(uptrend(260), 229), days=days),
        "DIP2": hist("DIP2", dip(dip(uptrend(260, first=80.0, step=0.15), 240), 250, days=3), days=days),
        "SAW": hist("SAW", sawtooth(260), days=days),
    }


@pytest.mark.parametrize("mutation", ["change", "truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S leaves S's picks unchanged."""
    history = lookahead_set()
    days = session_days(260)
    prepared = STRATEGY_A.prepare(history)
    nonempty = 0
    for s in days[200:]:
        data_date = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        else:
            future = {k: truncate_before(h, s) for k, h in history.items()}
        members = frozenset(history)
        for params in (DESIGN_PARAMS, PERMISSIVE):
            before = STRATEGY_A.picks(history, members, data_date, params)
            assert STRATEGY_A.picks(future, members, data_date, params) == before, s
            assert STRATEGY_A.picks_prepared(STRATEGY_A.prepare(future), members, data_date, params) == before, s
            assert STRATEGY_A.picks_prepared(prepared, members, data_date, params) == before, s
            nonempty += params is DESIGN_PARAMS and bool(before)
    assert nonempty >= 2  # the design setup fired on the dip days, so the check is not vacuous


def test_the_mutation_does_change_later_picks():
    # Guards test_no_look_ahead: the same mutation, read at data_date = S, changes the picks.
    history = lookahead_set()
    s = session_days(260)[230]
    future = {k: mutate_from(h, s) for k, h in history.items()}
    members = frozenset(history)
    assert STRATEGY_A.picks(future, members, s, PERMISSIVE) != STRATEGY_A.picks(history, members, s, PERMISSIVE)


# ---- the picks / picks_prepared contract ---------------------------------------------------


def contract_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(320)
    return days, {
        "SAW": hist("SAW", sawtooth(320), days=days),
        "DIP": hist("DIP", dip(dip(dip(uptrend(320), 229), 260), 290, drop=2.0), days=days),
        "LATE": hist("LATE", sawtooth(260, first=40.0, up=0.9, down=0.5), days=days[60:]),
        "GAPPY": drop_days(hist("GAPPY", sawtooth(320, first=70.0), days=days), days[100:105] + [days[250]]),
        "GONE": hist("GONE", sawtooth(270, first=90.0), days=days[:270]),
        "THIN": hist("THIN", dip(uptrend(320), 229), days=days, volume=1000.0),
    }


@pytest.mark.parametrize(
    "params",
    [DESIGN_PARAMS, PERMISSIVE, AParams(rsi_max=60.0, limit_atr=Decimal("0.25"), tp_atr=Decimal("1.5"))],
    ids=["design", "permissive", "mid"],
)
def test_picks_prepared_equals_picks_on_every_date(params):
    days, history = contract_set()

    def members(d: date) -> frozenset[str]:
        out = set(history) - {"LATE"} if d < days[280] else set(history)
        return frozenset(out - {"SAW"} if days[240] <= d < days[260] else out)

    prepared = STRATEGY_A.prepare(history)
    assert isinstance(prepared, APrepared)
    nonempty = 0
    for d in days[190:]:
        visible = upto_all(history, d)
        assert prepared.features_on(d) == features_at(visible, d), d  # bit-identical floats
        expected = STRATEGY_A.picks(visible, members(d), d, params)
        assert STRATEGY_A.picks_prepared(prepared, members(d), d, params) == expected, d
        assert STRATEGY_A.picks(history, members(d), d, params) == expected, d  # later bars ignored
        nonempty += bool(expected)
    assert nonempty > 0


def test_prepare_on_short_or_empty_history():
    short = {"X": hist("X", sawtooth(150))}
    for history in ({}, short):
        prepared = STRATEGY_A.prepare(history)
        assert prepared.features_on(date(2019, 6, 3)) == []
        assert STRATEGY_A.picks_prepared(prepared, {"X"}, date(2019, 6, 3), PERMISSIVE) == []
        assert STRATEGY_A.picks(history, {"X"}, date(2019, 6, 3), PERMISSIVE) == []
```

## Verification

**Build:** `engine/.venv/bin/pip install -e 'engine[dev]'` then `engine/.venv/bin/python -c "import seer_engine.strategies, seer_engine.backtest; print('ok')"`
**Tests (new files):** `engine/.venv/bin/pytest engine/tests/test_indicators.py engine/tests/test_strategy_a.py engine/tests/test_strategy_purity.py -q` → **74 passed** (21 + 50 + 3), about 9 s
**Tests (full):** `docker start seer-pg && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` → **448 passed, 0 skipped** (baseline 374 + 74). `grep -c SKIPPED` on `-rA` output = 0.
**Manual check:** `engine/.venv/bin/python -c "import sys, seer_engine.strategies.a; print([m for m in ('psycopg','requests','yfinance','seer_engine.bars') if m in sys.modules])"` prints `[]`.
**Exit criteria:** the full suite is 448 passed, 0 skipped (reconciler-measured on a scratch copy); `isinstance(STRATEGY_A, Strategy)`; `test_rolling_is_bit_identical_to_one_window`, `test_no_look_ahead[*]`, `test_picks_prepared_equals_picks_on_every_date[*]` and `test_symbols_joining_and_leaving_mid_window` are green; and `git diff --stat` touches only the 10 files above.

## Handoffs

- **Phase 3 (R2):** consume `STRATEGY_A.prepare(market.history)` once and pass it as `prepared=` to `run_backtest`. `picks_prepared` takes `members_on(data_date)` as any `Set[str]` (a `frozenset` is fine). `stratkit.hist`/`session_days`/`sawtooth`/`dip` are available for synthetic markets. `Market` may build `History` straight from float64 columns (no `Bar` objects needed); any 1-D `float64` arrays with a strictly ascending `datetime64[D]` date array pass validation.
- **Phase 4 (R4):** `tuning.grid()` builds `AParams(rsi_max=r, limit_atr=l, tp_atr=t, sl_atr=s)` from the grid tuples; the floats/Decimals in the index's `GRID_*` constants are accepted as-is. Render params with `AParams.as_dict()`.
- **Phase 6 (R4/R5/R6):** replace only the line `STRATEGY_A_PARAMS: AParams = DESIGN_PARAMS  # phase 6 replaces this with the frozen selection` in `a.py` (and its comment, naming the report). No phase-1 test asserts `STRATEGY_A_PARAMS == DESIGN_PARAMS`, so freezing different values breaks nothing. `strategies/__init__.py` re-exports the name, so no edit is needed there. Document in `package_readme.md`: the protocol and its equality contract, the bit-identity rule, the 200-bar window (P4 must load **≥ 200 bars ending at data_date** per symbol; more is harmless), the float/Decimal boundary, and the `last ≤ 0` drop rule added to the "Invalid picks" decision.
- **Decisions log (recorded by the reconciler):** this phase drops a candidate whose `last` rounds to `0.0000`, in addition to the four conditions in the "Invalid picks" row (same reason: `Pick` requires every price > 0); the index's "Invalid picks" row now lists it. It also adds `random` to the purity test's forbidden attributes (index Decisions "Purity scan"); the reconciler checked that every pure module of phases 2–4 passes the glob (scratch run of phases 1–5: 595 passed). Both are tightenings, and neither changes any result on real data.
- **P4 (out of this plan set):** call `STRATEGY_A.picks(history, members, data_date, STRATEGY_A_PARAMS)` with `history_from_bars` histories.

## Rollback

`git revert <phase-1 commit>`. It removes the nine new files and the `numpy` line. Nothing else depends on them until phases 2–6 land. No database or cache state is involved.
