# Phase 2: B features, ranks, candidates, `StrategyB`

**Plan set:** `STRATEGY_B_RANKER_PLAN.md`
**Analysis:** `20261003-180843-B6R1_code_analyzer.md`
**Satisfies:** R2 (features hand-computed, rolling == single window, ranks among d's candidates with ties averaged, SPY through `data_date` only), R3 (P4 identity and no look-ahead with a fixed fake model, SPY bars dated ≥ S included), R6 (purity glob covers `b.py`)
**Depends on:** none (runs in parallel with phases 1 and 3)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

After this phase, `seer_engine.strategies.b` turns bar history into Strategy B's per-date design
matrix: 15 per-symbol features, each ranked among that date's candidates, plus 3 raw SPY features.
It also turns any per-row `Predictor` into ranked, bracketed `Pick`s through `StrategyB`. Two paths
build the design: the rolling one (`prepare_b` + `BPrepared.design_on`) and the single-window one
(`design_at`). They are bit-identical, and neither reads a bar dated after `data_date`, SPY's
included. Two window functions, `mean_window` and `stdev_return_window`, are added to
`indicators.py` under its bit-identity rule. This phase contains no model fitting and no
scikit-learn; `b.py` never imports `b_model`.

## Interface Contract

The plan index's shared contract, implemented exactly. Additions are marked **(+)**; the
reconciler should check them against phases 4, 5 and 7.

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `indicators.mean_window(x, n)` and `indicators.stdev_return_window(close, n)` (`strategies/indicators.py`, inserted between `mean_dollar_volume_window` and `rolling`). `_one_bar_return(close, i)` is a private helper **(+)**.
- `strategies/b.py`. It contains:
  - **Constants:** `LOOKBACK = 200`, `SPY_SYMBOL = "SPY"`, `MIN_DOLLAR_VOLUME = 20_000_000.0`, `RETURN_HORIZONS = (1, 5, 20, 60, 120)`, `SYMBOL_FEATURES` (15), `SPY_FEATURES` (3), `FEATURE_NAMES` (18), `RAW_COLUMNS` (18: `SYMBOL_FEATURES + ("close", "atr", "dollar_volume")`).
  - **(+) public helper constants:** `N_SYMBOL = 15`, `N_FEATURES = 18`, `CLOSE_COL = 15`, `ATR_COL = 16`, `DV_COL = 17`, `SMA_FAST_N = 50`, `SMA_SLOW_N = 200`, `RSI_FAST_N = 2`, `RSI_SLOW_N = 14`, `ATR_N = 14`, `STDEV_N = 20`, `DV_N = 20`, `VOLUME_FAST_N = 5`, `VOLUME_SLOW_N = 20`, `SPY_RETURN_HORIZONS = (5, 20)`.
  - **Functions:** `window_features(o, h, l, c, v) -> (rows, 18)`, `spy_window_features(c) -> (rows, 3)`, `rank01(x)`.
  - **`Design(data_date, symbols, X, close, atr)`.** It is frozen, slots, and `eq=False`, and its arrays are read-only. **(+)** `__post_init__` checks the date type and the shapes (it raises `TypeError` or `ValueError`), and **(+)** `__len__` returns the number of rows.
  - **`BPrepared(symbols, dates, sym, raw, spy_dates, spy)`**, with `.design_on(members, data_date) -> Design`. Its private `_rows` and `_spy_row` methods are **(+)**.
    - **(+)** `BPrepared.symbols` is the sorted symbols **excluding `SPY_SYMBOL`**, and SPY never has a row.
  - **More functions:** `prepare_b(history) -> BPrepared` and `design_at(history, members, data_date) -> Design`.
  - **`Predictor`.** It is a `Protocol`, and **(+)** it is `@runtime_checkable`, so `isinstance(x, Predictor)` checks that a `predict` attribute exists.
  - **`BParams(model)`.** It is frozen and slots, and its eq and hash come from the model. **(+)** `__post_init__` raises `TypeError` when the model has no `predict`.
  - **`bracket(symbol, close, atr) -> Pick | None`.** It is `a._bracket(a.Features(symbol, date.min, close, nan, nan, atr, nan), a.DESIGN_PARAMS)`. **(+)** It returns None, rather than raising, when `close` or `atr` is not finite (`to_decimal` raises on a non-finite float).
  - **`picks_from_design(design, params) -> list[Pick]`.** It raises `TypeError` on a non-`Design` or non-`BParams` argument. **(+)** It raises `ValueError` when `predict` returns anything but a float64 array of shape `(m,)`.
  - **`FrozenModel(report, artifact, train_end, sha256)`.**
  - **`STRATEGY_B_FROZEN: FrozenModel | None = None`**, under a two-line comment (quoted in Step 2).
  - **`StrategyB`** (`id = "B"`, `lookback = LOOKBACK`) and **`STRATEGY_B`**.
- **Semantics of `rank01` (+):**
  - it raises `ValueError` when its input is not a 1-D float64 array or holds a non-finite value;
  - `-0.0` and `0.0` tie;
  - n == 0 returns an empty float64 array, and n == 1 returns `[0.5]`.
- **New tests:** `tests/test_indicators_b.py` (11 tests) and `tests/test_strategy_b.py` (48 tests).

**Signature changes:** none to existing symbols.

`strategies/__init__.py` re-exports from `b.py`: `FEATURE_NAMES`, `STRATEGY_B`, `BParams`,
`BPrepared`, `Design`, `FrozenModel`, `Predictor`, `StrategyB`, `design_at`, `picks_from_design`
and `prepare_b`. **(+)** It does **not** re-export `STRATEGY_B_FROZEN`. A name re-exported from
the package would hold a copy taken at import, so a monkeypatch or phase 7's edit read through
`seer_engine.strategies.STRATEGY_B_FROZEN` could go stale. Phases 5 and 6 read it as
`seer_engine.strategies.b.STRATEGY_B_FROZEN`, at call time, as the index already says.

**Requires (from earlier phases):** nothing; no dependency. Phase 1's `b_model.BModel.predict`
must return a **float64 ndarray of shape `(rows,)`** exactly, or `picks_from_design` raises
`ValueError`. The contract already says so ("float64 (rows,)"), and this phase enforces it.

**Provides to later phases:**
- **Phase 4:**
  - `BPrepared.design_on(members, d)`. It gives each date's candidate rows, sorted by symbol, `X` (m, 18), `close` and `atr`.
  - `b.bracket(symbol, float(close), float(atr))`. It gives the 4-dp Decimal bracket, or None when the bracket is invalid.
  - `BParams(model)` and `STRATEGY_B`.
  - `picks_from_design`. Its emptiness rule is pred > 0.0, strict, and NaN never qualifies.
- **Phase 5:** `FEATURE_NAMES` and `FrozenModel`.
- **Phase 7:** the exact placeholder lines to replace.

**Leaves alone (owned by others):**
- `strategies/b_model.py` and `engine/pyproject.toml` (phase 1);
- `backtest/labels.py` (phase 3);
- `backtest/b_walkforward.py` (phase 4);
- `backtest/b_report.py` (phase 5);
- `backtest/io.py` and `commands/backtest_b.py` (phase 6);
- the value of `STRATEGY_B_FROZEN` and `tests/test_strategy_b_frozen.py` (phase 7).

Never touched:
- `strategies/a.py`, `a2.py` and `base.py`;
- every existing function in `indicators.py`;
- `tests/test_indicators.py`, `tests/stratkit.py` and `tests/simkit.py`;
- everything under `backtest/` and `sim/`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/indicators.py` | modify (additive) | Insert `mean_window`, `_one_bar_return` and `stdev_return_window` after `mean_dollar_volume_window` (ends at line 141) and before `def rolling` (line 144). Nothing else changes, the module docstring included |
| `engine/src/seer_engine/strategies/b.py` | create | Strategy B: features, ranks, candidates, design matrix, params, picks, `FrozenModel`, `STRATEGY_B` |
| `engine/src/seer_engine/strategies/__init__.py` | modify | Docstring (lines 1–6) mentions `b`. Add the `from seer_engine.strategies.b import (...)` block after the `a2` import (after line 28). Add 11 names to `__all__` (lines 31–51) |
| `engine/tests/test_indicators_b.py` | create | 11 tests: hand-computed values, warm-up, flat series, zero close, rolling bit-identity, input validation |
| `engine/tests/test_strategy_b.py` | create | 48 tests: features, ranks, candidates, SPY, bracket, picks, P4 identity with 5 fake models, no look-ahead, SPY never picked, constants, no sklearn on import |

## Design notes (why the code looks the way it does)

- **One builder, two paths.**
  - `window_features` maps each row to its own 18 raw values, using only elementwise numpy and
    the indicators' column loops (`sma_window`, `wilder_rsi_window`, `wilder_atr_window`,
    `mean_dollar_volume_window`, and the new `mean_window` and `stdev_return_window`). So a
    window computed alone (`design_at`: `np.stack` of slices) gives the same bits as the same
    window inside a `sliding_window_view` (`prepare_b`).
  - Both paths then call the same private `_design(data_date, names, raw, spy_row)`. It applies
    the candidate mask (`dv > MIN_DOLLAR_VOLUME` and all 15 raw values finite), then `rank01`
    per column among the survivors, then broadcasts SPY's raw row.
  - So bit identity reduces to identical raw rows, which the tests pin.
- **Members are filtered before ranking.**
  - `design_on` keeps member rows only (`np.fromiter` over at most ~600 rows), then `_design`
    applies the liquidity and finiteness rules.
  - `design_at` skips non-members before stacking.
  - In both, the rank universe is exactly "candidates on d" (handover §3, D5): members, not SPY,
    a bar on d, ≥ 200 bars, liquid, finite.
  - Bracket validity is **not** a candidate rule (D5). `picks_from_design` drops an invalid
    bracket after ranking.
- **SPY gates the whole date.** When SPY's 3 features are undefined on d (SPY missing, no bar
  dated d, or fewer than 200 bars through d), the design is empty and `picks` returns `[]`
  without calling the model.
- **Division by zero** (a zero close or volume) gives inf or NaN. That makes the row a
  non-candidate. `np.errstate` silences numpy's warnings only and changes no value.
- **`range_pos`** uses `np.where(wide, (c - l) / np.where(wide, h - l, 1.0), 0.5)`, so a flat bar
  gives exactly 0.5 and never divides by zero.
- **`rank01`:**
  - a stable argsort, then the run starts of equal sorted values;
  - the mean 1-based rank of a run covering positions `start .. end-1` is `(start + end + 1) / 2`
    (exact in float);
  - scaled as `(rank - 1) / (n - 1)`.

  The result depends only on the values, so it is permutation-equivariant (tested).
- **Speed**, measured on synthetic data shaped like Neon (663 symbols × 2,950 bars, about 1.82M
  rows; numpy 2.4.6, Python 3.11, this WSL2 box):

  | Step | Time |
  |---|---|
  | `prepare_b` | **5.0 s** (A's `prepare` is 2.8 s; B computes about twice the column loops: RSI 2 and 14, ATR, SMA 50 and 200, stdev, volume means) |
  | `design_on` | **0.5 ms** per call with 500 members, so 2,200 × 3 calls ≈ 3.3 s |
  | `design_at` | about 9 ms per date |

- **Memory:** `raw` is 1.82M × 18 × 8 B ≈ 262 MB, and the concatenate-then-reorder step briefly
  doubles it to about 525 MB. That is acceptable for a one-shot command, and it is noted under
  Risks.

## Implementation Steps

### Step 1: Add `mean_window` and `stdev_return_window` to `indicators.py`
**File:** `engine/src/seer_engine/strategies/indicators.py`. Insert after line 141
(`    return acc / n`, the end of `mean_dollar_volume_window`) and before line 144
(`def rolling(`). Keep two blank lines on each side.

**Change:** additive. No existing line changes.
- No new attribute in the code is in `test_indicators.py`'s `FORBIDDEN_REDUCTIONS` (`sum`,
  `mean`, `cumsum`, …). That AST test scans the whole file, so it covers the new functions
  without being edited.
- `np.sqrt` and `np.errstate` are allowed.
**Code** (inserted verbatim):
```python
def mean_window(x: np.ndarray, n: int) -> np.ndarray:
    """Mean of the last ``n`` columns of ``x``: summed left to right, then divided by ``n``.

    Any series (Strategy B: volume). NaN for every row when ``W < n``.
    """
    x = _matrix("x", x)
    n = _period(n)
    w = x.shape[1]
    if w < n:
        return _nan_rows(x)
    return _column_mean(x, w - n, n)


def _one_bar_return(close: np.ndarray, i: int) -> np.ndarray:
    return close[:, i] / close[:, i - 1] - 1.0


def stdev_return_window(close: np.ndarray, n: int) -> np.ndarray:
    """Population (ddof 0) standard deviation of the last ``n`` one-bar returns.

    ``r_i = c_i / c_{i-1} - 1`` for the last ``n`` bars (i = W-n .. W-1). mean = Σ r / n, summed
    left to right; var = Σ (r - mean)^2 / n, summed left to right; result ``sqrt(var)``. A zero
    previous close gives a non-finite value (numpy's division warning suppressed). NaN for every
    row when the window has fewer than ``n`` returns (``W < n + 1``).
    """
    close = _matrix("close", close)
    n = _period(n)
    w = close.shape[1]
    if w < n + 1:
        return _nan_rows(close)
    first = w - n
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = _one_bar_return(close, first)
        for i in range(first + 1, w):
            mean = mean + _one_bar_return(close, i)
        mean = mean / n
        dev = _one_bar_return(close, first) - mean
        acc = dev * dev
        for i in range(first + 1, w):
            dev = _one_bar_return(close, i) - mean
            acc = acc + dev * dev
        return np.sqrt(acc / n)
```
**Impact:** none on existing callers. `test_indicators.py` still passes, its AST rule included.

### Step 2: Create `strategies/b.py`
**File:** `engine/src/seer_engine/strategies/b.py` (new)

**Change:** the whole module below.
- It imports from `seer_engine.sim`, `strategies.a` (`DESIGN_PARAMS`, `Features`, `_bracket`),
  `strategies.base` and `strategies.indicators` only.
- It does **not** import `b_model`, `universe`, `sklearn`, `logging`, `time` or `random`.

**Phase 7 placeholder.** These exact three lines are what phase 7 replaces on a pass:
```python
# Set by P6a phase 7 ONLY if the gate passes (tests/test_strategy_b_frozen.py ties it to the report).
# None means Strategy B is not frozen.
STRATEGY_B_FROZEN: FrozenModel | None = None
```
**Code:**
```python
"""Strategy B: a learned cross-sectional ranker (roadmap P6a, handover 2026-10-03 §3).

Candidates on ``data_date`` d (Strategy A's eligible set):
    a member on d, not ``SPY_SYMBOL``, a bar dated d, at least ``LOOKBACK`` bars through d,
    20-day mean close×volume > ``MIN_DOLLAR_VOLUME`` (strict), all 15 raw ``SYMBOL_FEATURES``
    finite, AND SPY's three features defined on d (SPY has a bar dated d and ``LOOKBACK`` bars
    through it). No candidates otherwise.
Features (``FEATURE_NAMES``, 18 model columns): the 15 ``SYMBOL_FEATURES``, each turned into a
cross-sectional rank in [0, 1] among d's candidates (``rank01``, ties averaged), then SPY's 3 raw
``SPY_FEATURES``, the same for every candidate of d. Every raw value is a function of the last
``LOOKBACK`` bars ending at d only, computed under the indicators' bit-identity rule, so the
backtest (``prepare_b``: sliding windows) and the nightly job (``design_at``: one window per
symbol) build bit-identical ``Design`` matrices.
Picks: the model's prediction per candidate; keep pred > 0.0 (strict); order by (-pred, symbol);
each gets Strategy A's design bracket (``a._bracket`` with ``a.DESIGN_PARAMS``); an invalid
bracket drops the candidate. Zero picks is a valid night.

The model is opaque here: anything with ``predict(X) -> float64 (rows,)`` (``Predictor``). This
module never imports ``b_model`` (scikit-learn), so ``import seer_engine.strategies`` stays light.
Pure: no database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, runtime_checkable

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from seer_engine.sim import Pick
from seer_engine.strategies.a import DESIGN_PARAMS, Features, _bracket
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    mean_window,
    sma_window,
    stdev_return_window,
    wilder_atr_window,
    wilder_rsi_window,
)

LOOKBACK = 200  # == a.LOOKBACK (tested)
SPY_SYMBOL = "SPY"  # == a2.REGIME_SYMBOL == universe.BENCHMARK (tested; universe imports psycopg, so not imported)
MIN_DOLLAR_VOLUME = 20_000_000.0  # == a.DESIGN_PARAMS.min_dollar_volume (tested); candidate needs dv > this
RETURN_HORIZONS: tuple[int, ...] = (1, 5, 20, 60, 120)
SYMBOL_FEATURES: tuple[str, ...] = (
    "ret_1",
    "ret_5",
    "ret_20",
    "ret_60",
    "ret_120",
    "close_sma50",
    "close_sma200",
    "rsi_2",
    "rsi_14",
    "atr_pct",
    "stdev_20",
    "dollar_volume_20",
    "volume_5_20",
    "gap",
    "range_pos",
)  # 15, each ranked among the date's candidates
SPY_FEATURES: tuple[str, ...] = ("spy_ret_5", "spy_ret_20", "spy_close_sma200")  # 3, raw
FEATURE_NAMES: tuple[str, ...] = SYMBOL_FEATURES + SPY_FEATURES  # the 18 model columns, in this order
RAW_COLUMNS: tuple[str, ...] = SYMBOL_FEATURES + ("close", "atr", "dollar_volume")  # window_features' 18 columns

N_SYMBOL = len(SYMBOL_FEATURES)  # 15
N_FEATURES = len(FEATURE_NAMES)  # 18
CLOSE_COL = RAW_COLUMNS.index("close")  # 15
ATR_COL = RAW_COLUMNS.index("atr")  # 16
DV_COL = RAW_COLUMNS.index("dollar_volume")  # 17

SMA_FAST_N = 50
SMA_SLOW_N = 200
RSI_FAST_N = 2
RSI_SLOW_N = 14
ATR_N = 14
STDEV_N = 20
DV_N = 20
VOLUME_FAST_N = 5
VOLUME_SLOW_N = 20
SPY_RETURN_HORIZONS: tuple[int, ...] = (5, 20)

_NO_DATE = date.min  # a._bracket never reads Features.data_date


# ---- raw features on (rows, LOOKBACK) windows ------------------------------------------------


def _window(name: str, x: object) -> np.ndarray:
    if not isinstance(x, np.ndarray) or x.dtype != np.float64 or x.ndim != 2 or x.shape[1] != LOOKBACK:
        raise ValueError(f"{name} must be a 2-D float64 array (rows, {LOOKBACK})")
    return x


def _ret(c: np.ndarray, k: int) -> np.ndarray:
    """``c[-1] / c[-1-k] - 1`` per row: the return over the last ``k`` bars."""
    return c[:, -1] / c[:, -1 - k] - 1.0


def _close_over_sma(c: np.ndarray, n: int) -> np.ndarray:
    return c[:, -1] / sma_window(c, n) - 1.0


def window_features(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray) -> np.ndarray:  # noqa: E741
    """Raw per-symbol values for ``(rows, LOOKBACK)`` windows, oldest bar first: ``(rows, 18)`` float64.

    Columns ``RAW_COLUMNS``: the 15 ``SYMBOL_FEATURES`` raw values, then the last close, ATR(14)
    and the 20-day mean dollar volume. Row i depends only on row i of the inputs, bit for bit
    (elementwise numpy plus the indicators' column loops), so a window computed alone equals the
    same window computed among any others. Division by zero yields a non-finite value, which
    makes the row a non-candidate; numpy's warnings for it are suppressed.
    """
    o, h, l, c, v = (_window(n, x) for n, x in zip("ohlcv", (o, h, l, c, v), strict=True))  # noqa: E741
    rows = c.shape[0]
    out = np.empty((rows, len(RAW_COLUMNS)), dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        last = c[:, -1]
        atr = wilder_atr_window(h, l, c, ATR_N)
        dv = mean_dollar_volume_window(c, v, DV_N)
        for j, k in enumerate(RETURN_HORIZONS):  # columns 0..4: ret_1 .. ret_120
            out[:, j] = _ret(c, k)
        out[:, 5] = _close_over_sma(c, SMA_FAST_N)
        out[:, 6] = _close_over_sma(c, SMA_SLOW_N)
        out[:, 7] = wilder_rsi_window(c, RSI_FAST_N)
        out[:, 8] = wilder_rsi_window(c, RSI_SLOW_N)
        out[:, 9] = atr / last
        out[:, 10] = stdev_return_window(c, STDEV_N)
        out[:, 11] = dv
        out[:, 12] = mean_window(v, VOLUME_FAST_N) / mean_window(v, VOLUME_SLOW_N)
        out[:, 13] = o[:, -1] / c[:, -2] - 1.0
        hi, lo = h[:, -1], l[:, -1]
        wide = hi > lo
        out[:, 14] = np.where(wide, (last - lo) / np.where(wide, hi - lo, 1.0), 0.5)
        out[:, CLOSE_COL] = last
        out[:, ATR_COL] = atr
        out[:, DV_COL] = dv
    return out


def spy_window_features(c: np.ndarray) -> np.ndarray:
    """SPY's raw ``SPY_FEATURES`` for ``(rows, LOOKBACK)`` close windows: ``(rows, 3)`` float64.

    ``spy_ret_5``, ``spy_ret_20`` (as ``ret_k``) and ``spy_close_sma200`` (as ``close_sma200``).
    """
    c = _window("c", c)
    out = np.empty((c.shape[0], len(SPY_FEATURES)), dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        for j, k in enumerate(SPY_RETURN_HORIZONS):
            out[:, j] = _ret(c, k)
        out[:, 2] = _close_over_sma(c, SMA_SLOW_N)
    return out


def rank01(x: np.ndarray) -> np.ndarray:
    """Cross-sectional rank of each entry of 1-D finite ``x``, scaled into [0, 1].

    Average ranks (1-based; equal values share the mean of their positions), then
    ``(rank - 1) / (n - 1)``. n == 1 -> [0.5]; n == 0 -> an empty array. Order-independent:
    a stable argsort, then equal runs share one rank, so the result depends only on the values.
    """
    if not isinstance(x, np.ndarray) or x.dtype != np.float64 or x.ndim != 1:
        raise ValueError("rank01 needs a 1-D float64 array")
    n = x.shape[0]
    if n == 0:
        return np.empty(0, dtype=np.float64)
    if not bool(np.isfinite(x).all()):
        raise ValueError("rank01 needs finite values")
    if n == 1:
        return np.full(1, 0.5, dtype=np.float64)
    order = np.argsort(x, kind="stable")
    xs = x[order]
    starts = np.flatnonzero(np.concatenate(([True], xs[1:] != xs[:-1])))
    ends = np.concatenate((starts[1:], [n]))
    mean_rank = (starts + ends + 1).astype(np.float64) / 2.0  # 1-based mean of positions start+1 .. end
    ranks = np.empty(n, dtype=np.float64)
    ranks[order] = np.repeat(mean_rank, ends - starts)
    return (ranks - 1.0) / float(n - 1)


# ---- the design matrix of one data_date --------------------------------------------------------


def _readonly(arr: np.ndarray) -> np.ndarray:
    arr.setflags(write=False)
    return arr


@dataclass(frozen=True, slots=True, eq=False)
class Design:
    """The candidates of one ``data_date``: what the model sees and what a pick needs.

    ``symbols`` ascending; ``X`` row i is ``symbols[i]``: ``rank01`` of each ``SYMBOL_FEATURES``
    column among these m rows, then SPY's 3 raw values. ``close`` and ``atr`` feed the bracket.
    """

    data_date: date
    symbols: tuple[str, ...]
    X: np.ndarray  # (m, 18) float64, read-only
    close: np.ndarray  # (m,) float64, read-only
    atr: np.ndarray  # (m,) float64, read-only

    def __post_init__(self) -> None:
        as_day(self.data_date)
        if not isinstance(self.symbols, tuple):
            raise TypeError("symbols must be a tuple")
        m = len(self.symbols)
        for name, shape in (("X", (m, N_FEATURES)), ("close", (m,)), ("atr", (m,))):
            arr = getattr(self, name)
            if not isinstance(arr, np.ndarray) or arr.dtype != np.float64 or arr.shape != shape:
                raise ValueError(f"Design.{name} must be a float64 array of shape {shape}")

    def __len__(self) -> int:
        return len(self.symbols)


def _empty_design(data_date: date) -> Design:
    return Design(
        data_date,
        (),
        _readonly(np.empty((0, N_FEATURES), dtype=np.float64)),
        _readonly(np.empty(0, dtype=np.float64)),
        _readonly(np.empty(0, dtype=np.float64)),
    )


def _candidate_mask(raw: np.ndarray) -> np.ndarray:
    """Rows of ``raw`` (window_features output) passing the liquidity floor with 15 finite features."""
    return (raw[:, DV_COL] > MIN_DOLLAR_VOLUME) & np.isfinite(raw[:, :N_SYMBOL]).all(axis=1)


def _design(data_date: date, symbols: list[str], raw: np.ndarray, spy_row: np.ndarray) -> Design:
    """The ``Design`` from the raw rows of ``symbols`` (ascending, members, not SPY) on ``data_date``.

    The ONE builder both paths share: candidates filtered by ``_candidate_mask``, ranks per
    column among the survivors only, SPY's raw values broadcast.
    """
    keep = _candidate_mask(raw)
    if not bool(keep.any()):
        return _empty_design(data_date)
    cand = raw[keep]
    names = tuple(s for s, k in zip(symbols, keep.tolist(), strict=True) if k)
    m = len(names)
    X = np.empty((m, N_FEATURES), dtype=np.float64)
    for j in range(N_SYMBOL):
        X[:, j] = rank01(np.ascontiguousarray(cand[:, j]))
    X[:, N_SYMBOL:] = spy_row
    return Design(
        data_date,
        names,
        _readonly(X),
        _readonly(cand[:, CLOSE_COL].copy()),
        _readonly(cand[:, ATR_COL].copy()),
    )


@dataclass(frozen=True, slots=True, eq=False)
class BPrepared:
    """Strategy B's raw features for every (symbol, date) with ``LOOKBACK`` bars, plus SPY's.

    Columnar, ordered by (date, symbol). ``symbols`` is sorted and excludes ``SPY_SYMBOL``
    (SPY never has a row). Built once by ``prepare_b``; ranks are NOT stored, because they
    depend on the members passed at pick time (``design_on``).
    """

    symbols: tuple[str, ...]  # sorted, SPY excluded; ``sym`` indexes into it
    dates: np.ndarray  # datetime64[D] ascending, one per row
    sym: np.ndarray  # int64
    raw: np.ndarray  # (rows, 18) float64, RAW_COLUMNS, read-only
    spy_dates: np.ndarray  # datetime64[D] ascending: SPY dates with >= LOOKBACK bars through them
    spy: np.ndarray  # (k, 3) float64 SPY_FEATURES, read-only

    def _rows(self, data_date: date) -> tuple[int, int]:
        day = as_day(data_date)
        lo = int(np.searchsorted(self.dates, day, side="left"))
        hi = int(np.searchsorted(self.dates, day, side="right"))
        return lo, hi

    def _spy_row(self, data_date: date) -> np.ndarray | None:
        day = as_day(data_date)
        i = int(np.searchsorted(self.spy_dates, day, side="left"))
        if i == self.spy_dates.shape[0] or self.spy_dates[i] != day:
            return None
        return self.spy[i]

    def design_on(self, members: Set[str], data_date: date) -> Design:
        """The candidates of ``data_date`` among ``members`` (== ``design_at`` on the same bars).

        Empty (0 rows) when SPY's features are undefined on ``data_date`` or nothing qualifies.
        """
        spy_row = self._spy_row(data_date)
        lo, hi = self._rows(data_date)
        if spy_row is None or lo == hi:
            return _empty_design(data_date)
        sym = self.sym[lo:hi].tolist()
        member = np.fromiter((self.symbols[k] in members for k in sym), dtype=np.bool_, count=hi - lo)
        if not bool(member.any()):
            return _empty_design(data_date)
        rows = np.flatnonzero(member) + lo
        names = [self.symbols[int(self.sym[k])] for k in rows]
        return _design(data_date, names, self.raw[rows], spy_row)


def _empty_prepared(symbols: tuple[str, ...], spy_dates: np.ndarray, spy: np.ndarray) -> BPrepared:
    return BPrepared(
        symbols,
        _readonly(np.empty(0, dtype="datetime64[D]")),
        _readonly(np.empty(0, dtype=np.int64)),
        _readonly(np.empty((0, len(RAW_COLUMNS)), dtype=np.float64)),
        spy_dates,
        spy,
    )


def _spy_prepared(history: Mapping[str, History]) -> tuple[np.ndarray, np.ndarray]:
    spy = history.get(SPY_SYMBOL)
    if spy is None or len(spy) < LOOKBACK:
        return (
            _readonly(np.empty(0, dtype="datetime64[D]")),
            _readonly(np.empty((0, len(SPY_FEATURES)), dtype=np.float64)),
        )
    dates = spy.dates[LOOKBACK - 1 :].copy()
    feats = spy_window_features(sliding_window_view(spy.close, LOOKBACK))
    return _readonly(dates), _readonly(feats)


def prepare_b(history: Mapping[str, History]) -> BPrepared:
    """Raw B features over every symbol's whole history, by sliding windows (see ``BPrepared``)."""
    symbols = tuple(sorted(s for s in history if s != SPY_SYMBOL))
    spy_dates, spy = _spy_prepared(history)
    dates_parts: list[np.ndarray] = []
    sym_parts: list[np.ndarray] = []
    raw_parts: list[np.ndarray] = []
    for k, symbol in enumerate(symbols):
        h = history[symbol]
        if len(h) < LOOKBACK:
            continue
        windows = [sliding_window_view(getattr(h, f), LOOKBACK) for f in ("open", "high", "low", "close", "volume")]
        dates_parts.append(h.dates[LOOKBACK - 1 :])
        sym_parts.append(np.full(len(h) - LOOKBACK + 1, k, dtype=np.int64))
        raw_parts.append(window_features(*windows))
    if not dates_parts:
        return _empty_prepared(symbols, spy_dates, spy)
    dates = np.concatenate(dates_parts)
    order = np.argsort(dates, kind="stable")  # symbols were appended in sorted order
    return BPrepared(
        symbols,
        _readonly(dates[order]),
        _readonly(np.concatenate(sym_parts)[order]),
        _readonly(np.concatenate(raw_parts)[order]),
        spy_dates,
        spy,
    )


def _spy_row_at(history: Mapping[str, History], data_date: date) -> np.ndarray | None:
    spy = history.get(SPY_SYMBOL)
    if spy is None:
        return None
    i = spy.index_of(data_date)
    if i is None or i + 1 < LOOKBACK:
        return None
    return spy_window_features(spy.close[i + 1 - LOOKBACK : i + 1].reshape(1, LOOKBACK))[0]


def design_at(history: Mapping[str, History], members: Set[str], data_date: date) -> Design:
    """The candidates of ``data_date`` from one window per symbol: the nightly (single-window) path.

    Reads each symbol's last ``LOOKBACK`` bars ending at ``data_date`` only, SPY's included, so
    ``history`` may hold later bars. Equal, bit for bit, to
    ``prepare_b({s: h.upto(d) for s, h in history.items()}).design_on(members, d)``.
    """
    as_day(data_date)
    spy_row = _spy_row_at(history, data_date)
    if spy_row is None:
        return _empty_design(data_date)
    names: list[str] = []
    ends: list[int] = []
    for symbol in sorted(history):
        if symbol == SPY_SYMBOL or symbol not in members:
            continue
        i = history[symbol].index_of(data_date)
        if i is None or i + 1 < LOOKBACK:
            continue
        names.append(symbol)
        ends.append(i + 1)
    if not names:
        return _empty_design(data_date)

    def stack(field: str) -> np.ndarray:
        return np.stack([getattr(history[s], field)[e - LOOKBACK : e] for s, e in zip(names, ends, strict=True)])

    raw = window_features(stack("open"), stack("high"), stack("low"), stack("close"), stack("volume"))
    return _design(data_date, names, raw, spy_row)


# ---- the model, the params, the picks ----------------------------------------------------------


@runtime_checkable
class Predictor(Protocol):
    """A fitted model: float64 ``(rows,)`` predictions for a float64 ``(rows, 18)`` design matrix.

    Row i's prediction must depend on row i only (``b_model.BModel`` guarantees it).
    """

    def predict(self, X: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class BParams:
    """Strategy B's params: the fitted model. Equality and hash come from the model."""

    model: Predictor

    def __post_init__(self) -> None:
        if not isinstance(self.model, Predictor):
            raise TypeError(f"model must have a predict method, got {type(self.model).__name__}")


def bracket(symbol: str, close: float, atr: float) -> Pick | None:
    """Strategy A's design bracket for ``symbol``: limit −0.5 ATR, TP +1.0 ATR, SL −1.5 ATR, 4-dp Decimal.

    ``a._bracket`` with ``a.DESIGN_PARAMS``; None when it is invalid, or when ``close`` or
    ``atr`` is not finite.
    """
    if not (np.isfinite(close) and np.isfinite(atr)):
        return None
    return _bracket(Features(symbol, _NO_DATE, float(close), np.nan, np.nan, float(atr), np.nan), DESIGN_PARAMS)


def picks_from_design(design: Design, params: BParams) -> list[Pick]:
    """Ranked B picks: candidates with prediction > 0.0, by (-prediction, symbol), each bracketed.

    An empty design returns [] without calling the model. A candidate with an invalid bracket
    is dropped after ranking. Uncapped: the simulator fills free slots in this order.
    """
    if not isinstance(design, Design):
        raise TypeError(f"design must be a Design, got {type(design).__name__}")
    if not isinstance(params, BParams):
        raise TypeError(f"params must be BParams, got {type(params).__name__}")
    m = len(design.symbols)
    if m == 0:
        return []
    pred = params.model.predict(design.X)
    if not isinstance(pred, np.ndarray) or pred.dtype != np.float64 or pred.shape != (m,):
        raise ValueError(f"predict must return a float64 array of shape ({m},)")
    ranked = sorted((-float(pred[k]), design.symbols[k], k) for k in np.flatnonzero(pred > 0.0).tolist())
    picks: list[Pick] = []
    for _, symbol, k in ranked:
        pick = bracket(symbol, float(design.close[k]), float(design.atr[k]))
        if pick is not None:
            picks.append(pick)
    return picks


# ---- the frozen model (P6a phase 7) -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FrozenModel:
    """The deployed B model: its report, its committed artifact, its training cut-off and its SHA-256."""

    report: str  # "docs/backtests/<end>-strategy-b-walkforward.md"
    artifact: str  # "engine/data/models/<end>-strategy-b.pkl"
    train_end: date  # the last fold's tune_end
    sha256: str  # hex digest of the artifact bytes


# Set by P6a phase 7 ONLY if the gate passes (tests/test_strategy_b_frozen.py ties it to the report).
# None means Strategy B is not frozen.
STRATEGY_B_FROZEN: FrozenModel | None = None


# ---- the Strategy protocol ---------------------------------------------------------------------


def _check_params(params: object) -> BParams:
    if not isinstance(params, BParams):
        raise TypeError(f"params must be BParams, got {type(params).__name__}")
    return params


class StrategyB:
    """Strategy B behind the ``Strategy`` protocol.

    CONTRACT: ``picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d)}, M, d, p)`` for every p.
    """

    id = "B"
    lookback = LOOKBACK

    def picks(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        params = _check_params(params)
        return picks_from_design(design_at(history, members, data_date), params)

    def prepare(self, history: Mapping[str, History]) -> BPrepared:
        return prepare_b(history)

    def picks_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        if not isinstance(prepared, BPrepared):
            raise TypeError(f"prepared must be BPrepared, got {type(prepared).__name__}")
        params = _check_params(params)
        return picks_from_design(prepared.design_on(members, data_date), params)


STRATEGY_B = StrategyB()
```
**Impact:** new module.
- The purity glob picks it up: `test_strategy_purity.py` imports it fresh, and its AST check
  finds no forbidden name. `date.min` and `np.errstate` are allowed.
- Nothing imports it yet, except `__init__` (Step 3).

### Step 3: Export B from the package
**File:** `engine/src/seer_engine/strategies/__init__.py`. The whole file is replaced (51 lines
today):
- the docstring (lines 1–6) gains the `b` sentence;
- a new import block goes after the `a2` block (line 28);
- `__all__` (lines 31–51) gains `FEATURE_NAMES`, `STRATEGY_B`, `BParams`, `BPrepared`, `Design`,
  `FrozenModel`, `Predictor`, `StrategyB`, `design_at`, `picks_from_design` and `prepare_b`, in
  the existing order: constants, then classes, then functions, each alphabetical.

**Change:** it re-exports from `b.py` only. **Never** add `b_model` here: `import
seer_engine.strategies` must not load scikit-learn (`test_strategy_b.py::test_importing_strategies_loads_neither_b_model_nor_sklearn`).
**Code** (full file):
```python
"""Trading strategies: pure functions from daily bar history to ranked ``sim.Pick``s.

``base`` holds the interface every strategy implements (P3 Strategy A, P6 B and C) and the
``History`` bar container; ``indicators`` the window functions; ``a`` Strategy A; ``a2``
Strategy A2, the P3b rework (Strategy A plus the pre-registered variants V0–V3); ``b``
Strategy B, the P6a learned cross-sectional ranker (features, ranks, candidates, picks; the
model fitting lives in ``b_model``, which this package never imports, so importing it does not
load scikit-learn). Pure: no database, network, clock or randomness
(tests/test_strategy_purity.py).
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
from seer_engine.strategies.a2 import (
    A2_DESIGN_PARAMS,
    STRATEGY_A2,
    STRATEGY_A2_PARAMS,
    VARIANTS,
    A2Params,
    A2Prepared,
    StrategyA2,
)
from seer_engine.strategies.b import (
    FEATURE_NAMES,
    STRATEGY_B,
    BParams,
    BPrepared,
    Design,
    FrozenModel,
    Predictor,
    StrategyB,
    design_at,
    picks_from_design,
    prepare_b,
)
from seer_engine.strategies.base import History, Strategy, history_from_bars

__all__ = [
    "A2_DESIGN_PARAMS",
    "DESIGN_PARAMS",
    "FEATURE_NAMES",
    "STRATEGY_A",
    "STRATEGY_A2",
    "STRATEGY_A2_PARAMS",
    "STRATEGY_A_PARAMS",
    "STRATEGY_B",
    "VARIANTS",
    "A2Params",
    "A2Prepared",
    "AParams",
    "APrepared",
    "BParams",
    "BPrepared",
    "Design",
    "Features",
    "FrozenModel",
    "History",
    "Predictor",
    "Strategy",
    "StrategyA",
    "StrategyA2",
    "StrategyB",
    "design_at",
    "features_at",
    "history_from_bars",
    "picks_from_design",
    "picks_from_features",
    "prepare_b",
]
```
**Impact:** `from seer_engine.strategies import STRATEGY_B, BParams, ...` works. Every existing
import is unchanged.

### Step 4: Tests for the new window functions
**File:** `engine/tests/test_indicators_b.py` (new). There are **11 tests**:
- 3 `mean_window`;
- 4 `stdev_return_window`;
- 3 parametrized rolling bit-identity cases;
- 1 input validation.

`tests/test_indicators.py` is **not** edited. Its AST rule test already covers the new code.

The hand-computed stdev case uses exact binary fractions (closes 8, 10, 5, 5, 10 → returns 0.25,
−0.5, 0, 1). That makes it an `==` check against `math.sqrt(0.29296875)`.
**Code:**
```python
"""Strategy B's window functions (P6a handover §3 "Features", §6.2): mean_window, stdev_return_window.

The bit-identity rule itself (no reduction along the time axis) is enforced for the whole of
indicators.py by tests/test_indicators.py, which covers these functions without being edited.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from seer_engine.strategies.indicators import (
    mean_window,
    rolling,
    sma_window,
    stdev_return_window,
)


def rows(*r: list[float]) -> np.ndarray:
    return np.array(r, dtype=np.float64)


# ---- mean_window ---------------------------------------------------------------------------


def test_mean_window_is_the_mean_of_the_last_n_columns():
    # (300 + 400 + 500) / 3 = 400; columns 0 and 1 are ignored. Each row is its own window.
    out = mean_window(rows([100, 200, 300, 400, 500], [0, 0, 1, 2, 6]), 3)
    assert out.tolist() == [400.0, 3.0]


def test_mean_window_warm_up_boundary():
    assert math.isnan(mean_window(rows([1, 2]), 3)[0])  # W = n - 1
    assert mean_window(rows([1, 2, 3]), 3).tolist() == [2.0]  # W = n


def test_mean_window_equals_sma_window_bit_for_bit():
    x = np.random.default_rng(3).uniform(1e5, 5e7, size=(40, 200))
    for n in (1, 5, 20, 200):
        assert mean_window(x, n).tobytes() == sma_window(x, n).tobytes()


# ---- stdev_return_window -------------------------------------------------------------------


def test_stdev_return_window_hand_computed():
    # closes 8, 10, 5, 5, 10 -> returns 0.25, -0.5, 0.0, 1.0 (all exact binary fractions)
    # mean = 0.75 / 4 = 0.1875; deviations 0.0625, -0.6875, -0.1875, 0.8125
    # squares 0.00390625 + 0.47265625 + 0.03515625 + 0.66015625 = 1.171875; / 4 = 0.29296875
    assert stdev_return_window(rows([8, 10, 5, 5, 10]), 4).tolist() == [math.sqrt(0.29296875)]


def test_stdev_return_window_reads_only_the_last_n_returns():
    # n = 2 on 1, 8, 10, 5: returns 0.25, -0.5 (the 1 -> 8 return is outside the window)
    # mean = -0.125; deviations 0.375, -0.375; var = 0.140625; stdev = 0.375 exactly
    assert stdev_return_window(rows([1, 8, 10, 5]), 2).tolist() == [0.375]
    # population (ddof 0), not sample: a sample stdev would be 0.375 * sqrt(2)
    r = [10.0 / 8.0 - 1.0, 5.0 / 10.0 - 1.0, 6.0 / 5.0 - 1.0]
    mean = (r[0] + r[1] + r[2]) / 3
    var = ((r[0] - mean) ** 2 + (r[1] - mean) ** 2 + (r[2] - mean) ** 2) / 3
    assert stdev_return_window(rows([8, 10, 5, 6]), 3)[0] == pytest.approx(math.sqrt(var), rel=1e-15)


def test_stdev_return_window_warm_up_boundary_and_flat_series():
    assert math.isnan(stdev_return_window(rows([10, 11]), 2)[0])  # 1 return < n = 2
    assert stdev_return_window(rows([8, 10, 5]), 2).tolist() == [0.375]  # W = n + 1
    assert stdev_return_window(rows([7, 7, 7, 7, 7]), 4).tolist() == [0.0]


def test_stdev_return_window_zero_previous_close_is_not_finite():
    out = stdev_return_window(rows([1, 0, 2, 3], [1, 2, 3, 4]), 3)
    assert not np.isfinite(out[0]) and np.isfinite(out[1])


# ---- rolling is bit-identical to one window ------------------------------------------------


def _random_series(seed: int, t: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    close = np.round(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, t))), 4)
    volume = np.round(rng.uniform(1e5, 5e7, t))
    return close, volume


CASES = [
    ("mean_v5", mean_window, "v", {"n": 5}),
    ("mean_v20", mean_window, "v", {"n": 20}),
    ("stdev_c20", stdev_return_window, "c", {"n": 20}),
]


@pytest.mark.parametrize(("name", "fn", "field", "kw"), CASES, ids=[c[0] for c in CASES])
def test_rolling_is_bit_identical_to_one_window(name, fn, field, kw):
    """``rolling(...)[t]`` == ``fn`` on the 200 bars ending at t alone, with ``==``, not approx."""
    c, v = _random_series(11, 600)
    series = c if field == "c" else v
    out = rolling(fn, series, window=200, **kw)
    assert np.isnan(out[:199]).all()
    for t in range(199, 600):
        alone = fn(series[None, t - 199 : t + 1].copy(), **kw)
        assert alone[0] == out[t], f"{name} differs at t={t}"
    picked = list(range(199, 600, 37))
    stacked = fn(np.stack([series[t - 199 : t + 1] for t in picked]), **kw)
    assert stacked.tolist() == out[picked].tolist()


def test_new_window_functions_reject_bad_input():
    for fn in (mean_window, stdev_return_window):
        with pytest.raises(ValueError, match="2-D"):
            fn(np.array([1.0, 2.0, 3.0]), 2)
        with pytest.raises(ValueError, match="2-D"):
            fn(np.array([[1, 2, 3]], dtype=np.int64), 2)
        with pytest.raises(ValueError, match="n must be"):
            fn(rows([1.0, 2.0, 3.0]), 0)
        with pytest.raises(ValueError, match="n must be"):
            fn(rows([1.0, 2.0, 3.0]), True)
```
**Impact:** +11 tests.

### Step 5: Tests for Strategy B
**File:** `engine/tests/test_strategy_b.py` (new). There are **48 tests** (35 functions, with
parametrized cases counted). By requirement:

**R2 · features:**
- `test_window_features_hand_computed`: the closes 100..299 window with a special last bar,
  covering all 15 raw values plus close, ATR and dollar volume. Every value is exact except
  `stdev_20`, which is checked with `approx(rel=1e-12)` against a Python-loop computation.
- `test_window_features_read_only_the_last_lookback_bars`
- `test_range_pos_is_one_half_on_a_flat_bar_and_spans_zero_to_one`
- `test_spy_window_features_hand_computed`
- `test_window_functions_reject_bad_shapes`
- `test_window_features_rows_are_independent_bit_for_bit`

**R2 · rolling == single window:**
- `test_prepare_raw_rows_equal_single_window_features`: every row, plus every SPY row.
- `test_design_on_equals_design_at_bit_for_bit_on_every_date`: `tobytes()` equality on 130 dates,
  three ways (`design_on`, `design_at` on the full history, and `prepare_b(upto(d))`).

**R2 · ranks:**
- `test_rank01_hand_computed` (7 cases: distinct, pair tie, triple tie, all equal, n = 1, n = 0,
  signed zero)
- `test_rank01_is_order_independent`
- `test_rank01_rejects_bad_input`
- `test_design_ranks_and_spy_columns_hand_checked`: SAW and TWIN tie on every raw value, so they
  share the mean rank.
- `test_ranks_use_the_members_on_d_only`: a non-member's mutated bars leave the members' ranks
  bit-identical.
- `test_liquidity_floor_is_strict` (2 cases: dollar volume of exactly 2e7 is excluded, 2.00001e7
  is kept)
- `test_a_non_finite_raw_feature_excludes_the_candidate`

**R2 · SPY through d:**
- `test_spy_features_read_spy_bars_through_d_only`
- `test_no_candidates_when_spy_is_missing_short_or_has_no_bar_on_d`: covers missing, 199 bars,
  no bar on d, and exactly 200 bars, where the features are defined.

**Picks:**
- `test_bracket_is_strategy_a_design_bracket`: hand-computed 4-dp half-up rounding, and the
  invalid and non-finite cases.
- `test_picks_keep_positive_predictions_only_ordered_with_symbol_ties`: 0.0, negative and NaN
  are excluded, and a tie at 0.5 is broken by symbol.
- `test_picks_drop_invalid_brackets_after_ranking`
- `test_an_empty_design_never_calls_the_model`
- `test_picks_reject_bad_predictions_and_types`
- `test_design_validates_its_shapes`
- `test_bparams_equality_hash_and_validation`
- `test_wrong_param_prepared_or_date_types_raise`

**R3 · P4 identity:**
- `test_picks_prepared_equals_picks_on_every_date`: 5 fake models (momentum, reversion,
  spy_gated, all_positive, all_negative) × 130 dates. Members change over time, and SPY is
  listed as a member near the end.
- `test_the_models_disagree_so_the_contract_test_is_not_vacuous`

**R3 · no look-ahead:**
- `test_no_look_ahead` (4 cases: every bar from S changed; every bar from S truncated; only
  SPY's bars from S halved; only SPY's truncated)
- `test_the_spy_mutation_does_change_later_designs_and_picks`: the guard.

**SPY never picked, and edge cases:**
- `test_spy_is_never_a_pick_even_as_a_liquid_member`
- `test_prepare_on_empty_or_short_history`

**Constants and wiring:**
- `test_constants`:
  - `SPY_SYMBOL == universe.BENCHMARK == a2.REGIME_SYMBOL`;
  - `MIN_DOLLAR_VOLUME == a.DESIGN_PARAMS.min_dollar_volume`;
  - `LOOKBACK == a.LOOKBACK`;
  - the feature names;
  - `STRATEGY_B_FROZEN is None or isinstance(..., FrozenModel)`. This deliberately does **not**
    assert None, so phase 7 can set it without editing this file.
- `test_strategy_b_implements_the_protocol`
- `test_importing_strategies_loads_neither_b_model_nor_sklearn`: a fresh subprocess.

The fakes are frozen dataclasses (`Linear`, `Fixed`, `Exploding`, `Bad`), so `BParams` stays
hashable. `Linear.predict` is an explicit column loop: per-row and batch-independent, the
property a real `BModel` guarantees.
**Code:**
```python
"""Strategy B's features, ranks, candidates and picks (P6a handover §3, §6.2, §6.3; plan D5–D8).

The model is a fake here (any per-row ``Predictor``): the real tree and ridge models are
phase 4's to test through the same ``STRATEGY_B``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pytest
from simkit import P
from stratkit import dip, drop_days, hist, mutate_from, sawtooth, session_days, truncate_before, uptrend

import seer_engine
from seer_engine import universe
from seer_engine.dates import prev_session
from seer_engine.sim import Pick
from seer_engine.strategies import (
    DESIGN_PARAMS,
    FEATURE_NAMES,
    STRATEGY_B,
    BParams,
    BPrepared,
    Design,
    FrozenModel,
    History,
    Predictor,
    Strategy,
    design_at,
    picks_from_design,
    prepare_b,
)
from seer_engine.strategies import a as strategy_a
from seer_engine.strategies import a2 as strategy_a2
from seer_engine.strategies import b
from seer_engine.strategies.b import (
    LOOKBACK,
    MIN_DOLLAR_VOLUME,
    RAW_COLUMNS,
    SPY_FEATURES,
    SPY_SYMBOL,
    STRATEGY_B_FROZEN,
    SYMBOL_FEATURES,
    bracket,
    rank01,
    spy_window_features,
    window_features,
)
from seer_engine.strategies.indicators import stdev_return_window


@dataclass(frozen=True)
class Linear:
    """A fake fitted model: ``bias + Σ_j X[:, j] * weights[j]``, row by row (an explicit column loop)."""

    weights: tuple[float, ...]
    bias: float = 0.0

    def predict(self, X: np.ndarray) -> np.ndarray:
        acc = np.full(X.shape[0], self.bias, dtype=np.float64)
        for j, w in enumerate(self.weights):
            acc = acc + X[:, j] * w
        return acc


def weights(**named: float) -> tuple[float, ...]:
    return tuple(float(named.get(name, 0.0)) for name in FEATURE_NAMES)


@dataclass(frozen=True)
class Fixed:
    """A fake model returning ``values`` as they are (for hand-built designs)."""

    values: tuple[float, ...]

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert X.shape[0] == len(self.values)
        return np.array(self.values, dtype=np.float64)


@dataclass(frozen=True)
class Exploding:
    def predict(self, X: np.ndarray) -> np.ndarray:
        raise AssertionError("predict must not be called")


MODELS = {
    "momentum": BParams(Linear(weights(ret_5=1.0, ret_20=0.5, rsi_2=-0.4), bias=-0.6)),
    "reversion": BParams(Linear(weights(ret_1=-1.0, close_sma50=-0.3, range_pos=-0.2), bias=0.7)),
    "spy_gated": BParams(Linear(weights(ret_20=1.0, spy_ret_20=40.0), bias=-0.6)),
    "all_positive": BParams(Linear(weights(), bias=1.0)),
    "all_negative": BParams(Linear(weights(), bias=-1.0)),
}


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


def symbols(picks: list[Pick]) -> list[str]:
    return [p.symbol for p in picks]


def same_design(x: Design, y: Design) -> bool:
    """Bit-for-bit equality of two designs."""
    return (
        x.data_date == y.data_date
        and x.symbols == y.symbols
        and x.X.shape == y.X.shape
        and x.X.tobytes() == y.X.tobytes()
        and x.close.tobytes() == y.close.tobytes()
        and x.atr.tobytes() == y.atr.tobytes()
    )


# ---- constants -----------------------------------------------------------------------------


def test_constants():
    assert SPY_SYMBOL == universe.BENCHMARK == strategy_a2.REGIME_SYMBOL == "SPY"
    assert MIN_DOLLAR_VOLUME == DESIGN_PARAMS.min_dollar_volume == 20_000_000.0
    assert LOOKBACK == strategy_a.LOOKBACK == 200
    assert b.RETURN_HORIZONS == (1, 5, 20, 60, 120)
    assert len(SYMBOL_FEATURES) == 15 and len(SPY_FEATURES) == 3
    assert FEATURE_NAMES == SYMBOL_FEATURES + SPY_FEATURES and len(FEATURE_NAMES) == 18
    assert len(set(FEATURE_NAMES)) == 18
    assert RAW_COLUMNS == SYMBOL_FEATURES + ("close", "atr", "dollar_volume")
    assert STRATEGY_B_FROZEN is None or isinstance(STRATEGY_B_FROZEN, FrozenModel)


def test_strategy_b_implements_the_protocol():
    assert isinstance(STRATEGY_B, Strategy)
    assert (STRATEGY_B.id, STRATEGY_B.lookback) == ("B", 200)
    assert isinstance(Linear(weights()), Predictor)


def test_importing_strategies_loads_neither_b_model_nor_sklearn():
    pkg = Path(seer_engine.__file__).resolve().parent
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pkg.parent) + os.pathsep + env.get("PYTHONPATH", "")
    code = (
        "import sys\n"
        "import seer_engine.strategies, seer_engine.strategies.b\n"
        "print(','.join(m for m in ('sklearn', 'seer_engine.strategies.b_model') if m in sys.modules))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True, timeout=120)
    assert out.stdout.strip() == ""


# ---- raw features, hand-computed -----------------------------------------------------------


def hand_window() -> History:
    """200 bars: closes 100..299 (high/low = close ± 0.5, open = close), except the last bar
    (open 300, high 301, low 298, close 299); volume 1e6, the last 5 bars 3e6."""
    closes = [100.0 + t for t in range(200)]
    opens = closes[:-1] + [300.0]
    highs = [c + 0.5 for c in closes[:-1]] + [301.0]
    lows = [c - 0.5 for c in closes[:-1]] + [298.0]
    volumes = [1e6] * 195 + [3e6] * 5
    return hist("HAND", closes, opens=opens, highs=highs, lows=lows, volumes=volumes)


def as_window(h: History) -> list[np.ndarray]:
    return [getattr(h, f)[-LOOKBACK:].reshape(1, LOOKBACK).copy() for f in ("open", "high", "low", "close", "volume")]


def test_window_features_hand_computed():
    h = hand_window()
    raw = window_features(*as_window(h))
    assert raw.shape == (1, 18) and raw.dtype == np.float64
    got = dict(zip(RAW_COLUMNS, raw[0].tolist(), strict=True))
    # returns over k bars: 299 / (299 - k) - 1
    for k in (1, 5, 20, 60, 120):
        assert got[f"ret_{k}"] == 299.0 / (299.0 - k) - 1.0, k
    # SMA(50) = mean(250..299) = 274.5; SMA(200) = mean(100..299) = 199.5 (exact sums)
    assert got["close_sma50"] == 299.0 / 274.5 - 1.0
    assert got["close_sma200"] == 299.0 / 199.5 - 1.0
    # strictly rising closes: no loss, so both Wilder RSIs are 100
    assert got["rsi_2"] == got["rsi_14"] == 100.0
    # TR = max(1, |c+0.5 - (c-1)|, |c-0.5 - (c-1)|) = 1.5 on every bar but the last; the last bar's
    # TR = max(301-298, |301-298|, |298-298|) = 3. Seed 1.5, the recursion keeps 1.5, then (1.5·13 + 3)/14.
    atr = (1.5 * 13.0 + 3.0) / 14.0
    assert got["atr"] == atr
    assert got["atr_pct"] == atr / 299.0
    # stdev of the last 20 one-bar returns (280/279 - 1 .. 299/298 - 1), population
    r = [(280.0 + i) / (279.0 + i) - 1.0 for i in range(20)]
    mean = sum(r) / 20
    var = sum((x - mean) ** 2 for x in r) / 20
    assert got["stdev_20"] == pytest.approx(var**0.5, rel=1e-12)
    # dollar volume: (1e6·(280+…+294) + 3e6·(295+…+299)) / 20 = (4.305e9 + 4.455e9) / 20
    assert got["dollar_volume_20"] == got["dollar_volume"] == 4.38e8
    # mean volume 5 = 3e6; mean volume 20 = (15·1e6 + 5·3e6) / 20 = 1.5e6
    assert got["volume_5_20"] == 2.0
    assert got["gap"] == 300.0 / 298.0 - 1.0
    assert got["range_pos"] == 1.0 / 3.0
    assert got["close"] == 299.0


def test_window_features_read_only_the_last_lookback_bars():
    h = hand_window()
    longer = hist(
        "HAND",
        [5.0] * 30 + h.close.tolist(),
        opens=[5.0] * 30 + h.open.tolist(),
        highs=[9.0] * 30 + h.high.tolist(),
        lows=[1.0] * 30 + h.low.tolist(),
        volumes=[1.0] * 30 + h.volume.tolist(),
    )
    assert window_features(*as_window(longer)).tobytes() == window_features(*as_window(h)).tobytes()


def test_range_pos_is_one_half_on_a_flat_bar_and_spans_zero_to_one():
    o, hi, lo, c, v = as_window(hand_window())
    for last_close, last_high, last_low, expected in ((299.0, 299.0, 299.0, 0.5), (298.0, 301.0, 298.0, 0.0), (301.0, 301.0, 298.0, 1.0)):
        cc, hh, ll = c.copy(), hi.copy(), lo.copy()
        cc[0, -1], hh[0, -1], ll[0, -1] = last_close, last_high, last_low
        assert window_features(o, hh, ll, cc, v)[0, RAW_COLUMNS.index("range_pos")] == expected


def test_spy_window_features_hand_computed():
    c = np.array([[200.0 + t for t in range(200)]])
    assert spy_window_features(c).tolist() == [[399.0 / 394.0 - 1.0, 399.0 / 379.0 - 1.0, 399.0 / 299.5 - 1.0]]


def test_window_functions_reject_bad_shapes():
    good = np.ones((2, LOOKBACK))
    with pytest.raises(ValueError, match="2-D"):
        window_features(good, good, good, np.ones((2, LOOKBACK - 1)), good)
    with pytest.raises(ValueError, match="2-D"):
        window_features(good, good, good, good, np.ones((2, LOOKBACK), dtype=np.int64))
    with pytest.raises(ValueError, match="2-D"):
        spy_window_features(np.ones(LOOKBACK))


def test_window_features_rows_are_independent_bit_for_bit():
    rng = np.random.default_rng(5)
    c = np.round(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, (9, LOOKBACK)), axis=1)), 4)
    o = np.round(c * (1.0 + rng.uniform(-0.01, 0.01, c.shape)), 4)
    h = np.round(np.maximum(o, c) * (1.0 + rng.uniform(0.0, 0.02, c.shape)), 4)
    lo = np.round(np.minimum(o, c) * (1.0 - rng.uniform(0.0, 0.02, c.shape)), 4)
    v = np.round(rng.uniform(1e5, 5e7, c.shape))
    together = window_features(o, h, lo, c, v)
    for i in range(9):
        alone = window_features(*(x[i : i + 1].copy() for x in (o, h, lo, c, v)))
        assert alone.tobytes() == together[i : i + 1].tobytes(), i
    assert together[:, RAW_COLUMNS.index("stdev_20")].tobytes() == stdev_return_window(c, 20).tobytes()


# ---- rank01 --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("x", "expected"),
    [
        ([3.0, 1.0, 2.0], [1.0, 0.0, 0.5]),
        ([2.0, 1.0, 3.0, 2.0], [0.5, 0.0, 1.0, 0.5]),  # ranks 2.5, 1, 4, 2.5 -> (r - 1) / 3
        ([1.0, 2.0, 2.0, 2.0, 5.0], [0.0, 0.5, 0.5, 0.5, 1.0]),  # ranks 1, 3, 3, 3, 5
        ([7.0, 7.0, 7.0], [0.5, 0.5, 0.5]),
        ([4.0], [0.5]),
        ([], []),
        ([0.0, -0.0, 1.0], [0.25, 0.25, 1.0]),  # signed zeros are equal, so tied
    ],
    ids=["distinct", "pair_tie", "triple_tie", "all_equal", "one", "none", "signed_zero"],
)
def test_rank01_hand_computed(x, expected):
    out = rank01(np.array(x, dtype=np.float64))
    assert out.dtype == np.float64 and out.tolist() == expected


def test_rank01_is_order_independent():
    rng = np.random.default_rng(9)
    x = rng.integers(0, 12, 60).astype(np.float64)  # many ties
    base = rank01(x)
    for _ in range(5):
        perm = rng.permutation(60)
        assert rank01(x[perm]).tobytes() == base[perm].tobytes()
    assert ((base >= 0.0) & (base <= 1.0)).all()


def test_rank01_rejects_bad_input():
    for bad in (np.array([1.0, np.nan]), np.array([np.inf, 1.0]), np.array([1, 2]), np.ones((2, 2)), [1.0, 2.0]):
        with pytest.raises(ValueError):
            rank01(bad)


# ---- the contract set ------------------------------------------------------------------------


def spy_closes(n: int) -> list[float]:
    """Rise 0.2/day for 250 bars, fall 1.5/day for 25, then rise 2.0/day."""
    out: list[float] = []
    for t in range(n):
        if t < 250:
            out.append(100.0 + 0.2 * t)
        elif t < 275:
            out.append(out[-1] - 1.5)
        else:
            out.append(out[-1] + 2.0)
    return out


def contract_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(320)
    return days, {
        "SAW": hist("SAW", sawtooth(320), days=days),
        "TWIN": hist("TWIN", sawtooth(320), days=days),  # every raw feature ties with SAW's
        "DIP": hist("DIP", dip(dip(dip(uptrend(320), 229), 260), 290, drop=2.0), days=days),
        "LATE": hist("LATE", sawtooth(260, first=40.0, up=0.9, down=0.5), days=days[60:], volume=2e6),
        "GAPPY": drop_days(hist("GAPPY", sawtooth(320, first=70.0), days=days), days[100:105] + [days[250]]),
        "GONE": hist("GONE", sawtooth(270, first=90.0), days=days[:270]),
        "THIN": hist("THIN", dip(uptrend(320), 229), days=days, volume=1000.0),
        "FALL": hist("FALL", uptrend(320, first=150.0, step=-0.2), days=days, spread=1.0, volume=3e6),
        SPY_SYMBOL: drop_days(hist(SPY_SYMBOL, spy_closes(320), days=days, volume=1e8), [days[240]]),
    }


def contract_members(days: list[date], d: date, *, spy: bool) -> frozenset[str]:
    out = {"SAW", "TWIN", "DIP", "LATE", "GAPPY", "GONE", "THIN", "FALL"}
    if d < days[280]:
        out.discard("LATE")
    if days[230] <= d < days[260]:
        out.discard("SAW")
    if spy:
        out.add(SPY_SYMBOL)
    return frozenset(out)


def test_prepare_raw_rows_equal_single_window_features():
    days, history = contract_set()
    prepared = prepare_b(history)
    assert isinstance(prepared, BPrepared)
    assert prepared.symbols == tuple(sorted(s for s in history if s != SPY_SYMBOL))
    assert prepared.raw.shape == (prepared.dates.shape[0], 18) and not prepared.raw.flags.writeable
    keys = list(zip(prepared.dates.tolist(), prepared.sym.tolist(), strict=True))
    assert keys == sorted(keys)  # ordered by (date, symbol)
    for k in range(prepared.dates.shape[0]):
        h = history[prepared.symbols[int(prepared.sym[k])]]
        i = h.index_of(prepared.dates[k].item())
        assert i is not None and i + 1 >= LOOKBACK
        alone = window_features(*(getattr(h, f)[None, i + 1 - LOOKBACK : i + 1].copy() for f in ("open", "high", "low", "close", "volume")))
        assert alone[0].tobytes() == prepared.raw[k].tobytes(), k
    spy = history[SPY_SYMBOL]
    assert prepared.spy_dates.tolist() == spy.dates[LOOKBACK - 1 :].tolist()
    for k, d in enumerate(prepared.spy_dates.tolist()):
        i = spy.index_of(d)
        assert spy_window_features(spy.close[None, i + 1 - LOOKBACK : i + 1].copy())[0].tobytes() == prepared.spy[k].tobytes()


def test_design_on_equals_design_at_bit_for_bit_on_every_date():
    days, history = contract_set()
    prepared = prepare_b(history)
    sizes = []
    for d in days[190:]:
        members = contract_members(days, d, spy=d >= days[300])
        expected = design_at(upto_all(history, d), members, d)
        assert same_design(prepared.design_on(members, d), expected), d
        assert same_design(design_at(history, members, d), expected), d  # later bars ignored
        assert same_design(prepare_b(upto_all(history, d)).design_on(members, d), expected), d
        assert SPY_SYMBOL not in expected.symbols
        assert not expected.X.flags.writeable
        sizes.append(len(expected))
    assert max(sizes) >= 5 and 0 in sizes  # SPY's missing day 240 empties that date


def test_design_ranks_and_spy_columns_hand_checked():
    days, history = contract_set()
    d = days[300]
    design = design_at(history, {"SAW", "TWIN", "FALL", "THIN"}, d)
    assert design.symbols == ("FALL", "SAW", "TWIN")  # THIN fails the liquidity floor
    raw = window_features(*(np.stack([getattr(history[s], f)[days.index(d) + 1 - LOOKBACK : days.index(d) + 1] for s in design.symbols]) for f in ("open", "high", "low", "close", "volume")))
    for j in range(15):
        col = raw[:, j]
        # SAW and TWIN tie on every raw value: both get the mean rank; FALL is below or above both
        assert design.X[1, j] == design.X[2, j] == (0.75 if col[0] < col[1] else 0.25 if col[0] > col[1] else 0.5), SYMBOL_FEATURES[j]
        assert design.X[0, j] == (0.0 if col[0] < col[1] else 1.0 if col[0] > col[1] else 0.5), SYMBOL_FEATURES[j]
    spy = history[SPY_SYMBOL]
    i = spy.index_of(d)
    spy_row = spy_window_features(spy.close[None, i + 1 - LOOKBACK : i + 1].copy())[0]
    assert (design.X[:, 15:] == spy_row).all()
    assert design.close.tolist() == raw[:, RAW_COLUMNS.index("close")].tolist()
    assert design.atr.tolist() == raw[:, RAW_COLUMNS.index("atr")].tolist()


def test_ranks_use_the_members_on_d_only():
    days, history = contract_set()
    d = days[300]
    prepared = prepare_b(history)
    three = prepared.design_on({"SAW", "DIP", "FALL"}, d)
    two = prepared.design_on({"SAW", "DIP"}, d)
    assert two.symbols == ("DIP", "SAW")
    assert sorted(two.X[:, 0].tolist()) == [0.0, 1.0]  # two candidates: ranks 0 and 1
    assert three.X[:, :15].tobytes() != two.X[:, :15].tobytes()
    # a non-member's bars never touch the members' ranks
    changed = {**history, "FALL": mutate_from(history["FALL"], days[0], lambda x: x * 0.25 + 1.0)}
    assert same_design(prepare_b(changed).design_on({"SAW", "DIP"}, d), two)
    assert same_design(design_at(changed, {"SAW", "DIP"}, d), two)


@pytest.mark.parametrize(("volume", "kept"), [(200_000.0, False), (200_001.0, True)])
def test_liquidity_floor_is_strict(volume, kept):
    # close 100 every bar: 20-day mean dollar volume = 100 × volume; 2e7 exactly is NOT above the floor
    days = session_days(200)
    history = {
        "AAA": hist("AAA", [100.0] * 200, days=days, volume=volume),
        "BBB": hist("BBB", uptrend(200), days=days, volume=1e6),
        SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(200, first=300.0), days=days),
    }
    for design in (design_at(history, {"AAA", "BBB"}, days[-1]), prepare_b(history).design_on({"AAA", "BBB"}, days[-1])):
        assert design.symbols == (("AAA", "BBB") if kept else ("BBB",))


def test_a_non_finite_raw_feature_excludes_the_candidate():
    # ZERO's close 120 bars before d is 0.0, so ret_120 = c / 0 - 1 = inf: not a candidate on d.
    days = session_days(201)
    closes = uptrend(201)
    closes[200 - 120] = 0.0
    history = {
        "ZERO": hist("ZERO", closes, days=days),
        "OK": hist("OK", uptrend(201), days=days),
        SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(201, first=300.0), days=days),
    }
    d = days[200]
    assert window_features(*as_window(history["ZERO"]))[0, 4] == np.inf
    for design in (design_at(history, {"ZERO", "OK"}, d), prepare_b(history).design_on({"ZERO", "OK"}, d)):
        assert design.symbols == ("OK",)


# ---- SPY: features through d only, and no candidates without them --------------------------


def test_spy_features_read_spy_bars_through_d_only():
    days, history = contract_set()
    d = days[260]
    members = contract_members(days, d, spy=False)
    base = design_at(history, members, d)
    assert len(base) > 0
    spy = history[SPY_SYMBOL]
    i = spy.index_of(d)
    assert base.X[0, 15:].tolist() == spy_window_features(spy.close[None, i + 1 - LOOKBACK : i + 1].copy())[0].tolist()
    later = days[days.index(d) + 1]
    for spy_future in (mutate_from(spy, later, lambda x: x * 0.5), truncate_before(spy, later)):
        future = {**history, SPY_SYMBOL: spy_future}
        assert same_design(design_at(future, members, d), base)
        assert same_design(prepare_b(future).design_on(members, d), base)


def test_no_candidates_when_spy_is_missing_short_or_has_no_bar_on_d():
    days, history = contract_set()
    d = days[260]
    members = contract_members(days, d, spy=False)
    assert len(design_at(history, members, d)) > 0  # guard
    spy = history[SPY_SYMBOL]
    cases = {
        "missing": {s: h for s, h in history.items() if s != SPY_SYMBOL},
        "short": {**history, SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(199), days=days[62:261])},  # 199 bars through d
        "no bar on d": {**history, SPY_SYMBOL: drop_days(spy, [d])},
    }
    for name, h in cases.items():
        for design in (design_at(h, members, d), prepare_b(h).design_on(members, d)):
            assert len(design) == 0 and design.X.shape == (0, 18), name
        for model in MODELS.values():
            assert STRATEGY_B.picks(h, members, d, model) == [], name
    exactly = {**history, SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(200), days=days[61:261])}  # 200 bars: defined
    assert same_design(design_at(exactly, members, d), prepare_b(exactly).design_on(members, d))
    assert len(design_at(exactly, members, d)) > 0


# ---- bracket and picks_from_design -----------------------------------------------------------


def test_bracket_is_strategy_a_design_bracket():
    # last 100, ATR 2: limit 100 - 1 = 99, tp 99 + 2 = 101, sl 99 - 3 = 96
    assert bracket("AAA", 100.0, 2.0) == Pick("AAA", P("100"), P("99"), P("101"), P("96"))
    # 4-dp rounding, half-up: ATR 0.33333 -> to_decimal 0.3333; limit q(10 - 0.16665) = 9.8334,
    # tp q(9.8334 + 0.3333) = 10.1667, sl q(9.8334 - 0.49995) = q(9.33345) = 9.3335
    assert bracket("BBB", 10.0, 0.33333) == Pick("BBB", P("10"), P("9.8334"), P("10.1667"), P("9.3335"))
    assert bracket("AAA", 100.0, 0.0) is None  # tp == limit
    assert bracket("AAA", 1.0, 1.0) is None  # sl <= 0
    assert bracket("AAA", 0.00001, 0.000001) is None  # last rounds to 0
    assert bracket("AAA", float("nan"), 1.0) is None
    assert bracket("AAA", 100.0, float("inf")) is None


def hand_design(close: list[float], atr: list[float], names: tuple[str, ...]) -> Design:
    m = len(names)
    return Design(date(2020, 1, 2), names, np.zeros((m, 18)), np.array(close), np.array(atr))


def test_picks_keep_positive_predictions_only_ordered_with_symbol_ties():
    design = hand_design([100.0] * 6, [2.0] * 6, ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF"))
    preds = (0.5, 0.0, -0.1, 0.5, 1e-12, float("nan"))  # 0.0 is not > 0 (strict); NaN never qualifies
    got = picks_from_design(design, BParams(Fixed(preds)))
    assert symbols(got) == ["AAA", "DDD", "EEE"]  # 0.5 (AAA before DDD by symbol), then 1e-12
    assert got[0] == bracket("AAA", 100.0, 2.0)


def test_picks_drop_invalid_brackets_after_ranking():
    design = hand_design([100.0, 100.0, 50.0], [2.0, 0.0, 1.0], ("AAA", "BAD", "CCC"))
    got = picks_from_design(design, BParams(Fixed((0.1, 0.9, 0.2))))
    assert symbols(got) == ["CCC", "AAA"]  # BAD ranked first, then dropped (ATR 0: tp == limit)


def test_an_empty_design_never_calls_the_model():
    empty = hand_design([], [], ())
    assert picks_from_design(empty, BParams(Exploding())) == []
    days, history = contract_set()
    d = days[240]  # SPY has no bar: no candidates
    assert STRATEGY_B.picks(history, contract_members(days, d, spy=False), d, BParams(Exploding())) == []
    assert STRATEGY_B.picks_prepared(prepare_b(history), contract_members(days, d, spy=False), d, BParams(Exploding())) == []


@dataclass(frozen=True)
class Bad:
    out: object

    def predict(self, X: np.ndarray) -> object:
        return self.out


def test_picks_reject_bad_predictions_and_types():
    design = hand_design([100.0, 100.0], [2.0, 2.0], ("AAA", "BBB"))
    for out in (np.ones(3), np.ones((2, 1)), np.ones(2, dtype=np.float32), [1.0, 1.0]):
        with pytest.raises(ValueError):
            picks_from_design(design, BParams(Bad(out)))
    with pytest.raises(TypeError):
        picks_from_design(design, Linear(weights()))  # a model is not BParams
    with pytest.raises(TypeError):
        picks_from_design("design", MODELS["all_positive"])


def test_design_validates_its_shapes():
    with pytest.raises(ValueError):
        Design(date(2020, 1, 2), ("AAA",), np.zeros((1, 17)), np.zeros(1), np.zeros(1))
    with pytest.raises(ValueError):
        Design(date(2020, 1, 2), ("AAA",), np.zeros((1, 18)), np.zeros(2), np.zeros(1))
    with pytest.raises(TypeError):
        Design(date(2020, 1, 2), ["AAA"], np.zeros((1, 18)), np.zeros(1), np.zeros(1))
    with pytest.raises(TypeError):
        Design(datetime(2020, 1, 2), (), np.zeros((0, 18)), np.zeros(0), np.zeros(0))


def test_bparams_equality_hash_and_validation():
    a = BParams(Linear(weights(ret_1=1.0), bias=0.5))
    assert a == BParams(Linear(weights(ret_1=1.0), bias=0.5))
    assert hash(a) == hash(BParams(Linear(weights(ret_1=1.0), bias=0.5)))
    assert a != BParams(Linear(weights(ret_1=1.0), bias=0.25))
    assert len(set(MODELS.values())) == len(MODELS)
    for bad in (None, 1.0, "model", object()):
        with pytest.raises(TypeError):
            BParams(bad)


def test_wrong_param_prepared_or_date_types_raise():
    days, history = contract_set()
    d = days[260]
    members = contract_members(days, d, spy=False)
    prepared = prepare_b(history)
    p = MODELS["all_positive"]
    with pytest.raises(TypeError):
        STRATEGY_B.picks(history, members, d, DESIGN_PARAMS)
    with pytest.raises(TypeError):
        STRATEGY_B.picks(history, members, d, Linear(weights()))
    with pytest.raises(TypeError):
        STRATEGY_B.picks_prepared(prepared, members, d, None)
    with pytest.raises(TypeError):
        STRATEGY_B.picks_prepared(strategy_a.STRATEGY_A.prepare(history), members, d, p)
    with pytest.raises(TypeError):
        STRATEGY_B.picks(history, members, datetime(2020, 3, 2), p)
    with pytest.raises(TypeError):
        prepared.design_on(members, "2020-03-02")
    with pytest.raises(TypeError):
        design_at(history, members, datetime(2020, 3, 2))


# ---- the contract: picks_prepared == picks on every date, for every model -------------------


@pytest.mark.parametrize("name", list(MODELS))
def test_picks_prepared_equals_picks_on_every_date(name):
    params = MODELS[name]
    days, history = contract_set()
    prepared = STRATEGY_B.prepare(history)
    nonempty = 0
    for d in days[190:]:
        visible = upto_all(history, d)
        members = contract_members(days, d, spy=d >= days[300])  # SPY listed as a member near the end
        expected = STRATEGY_B.picks(visible, members, d, params)
        assert STRATEGY_B.picks_prepared(prepared, members, d, params) == expected, d
        assert STRATEGY_B.picks(history, members, d, params) == expected, d  # later bars ignored
        assert expected == picks_from_design(design_at(visible, members, d), params), d
        assert SPY_SYMBOL not in symbols(expected), d
        nonempty += bool(expected)
    if name == "all_negative":
        assert nonempty == 0
    else:
        assert nonempty > 0


def test_the_models_disagree_so_the_contract_test_is_not_vacuous():
    days, history = contract_set()
    prepared = prepare_b(history)
    differ = {"momentum": 0, "reversion": 0, "spy_gated": 0}
    for d in days[200:]:
        members = contract_members(days, d, spy=False)
        everyone = STRATEGY_B.picks_prepared(prepared, members, d, MODELS["all_positive"])
        for name in differ:
            got = STRATEGY_B.picks_prepared(prepared, members, d, MODELS[name])
            differ[name] += bool(everyone) and got != everyone
    assert all(n > 0 for n in differ.values()), differ


# ---- no look-ahead, SPY's bars included ------------------------------------------------------


def lookahead_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(260)
    return days, {
        "DIP": hist("DIP", dip(uptrend(260), 229), days=days),
        "DIP2": hist("DIP2", dip(dip(uptrend(260, first=80.0, step=0.15), 240), 250, days=3), days=days),
        "SAW": hist("SAW", sawtooth(260), days=days),
        "FALL": hist("FALL", uptrend(260, first=150.0, step=-0.2), days=days, spread=1.0, volume=3e6),
        SPY_SYMBOL: hist(SPY_SYMBOL, spy_closes(260), days=days, volume=1e8),
    }


def halve(x: np.ndarray) -> np.ndarray:
    return x * 0.5


@pytest.mark.parametrize("mutation", ["change", "truncate", "spy_only_halve", "spy_only_truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S, SPY's included, leaves S's picks unchanged."""
    days, history = lookahead_set()
    prepared = prepare_b(history)
    members = frozenset(history)  # SPY listed too: it is never a candidate
    nonempty = 0
    for s in days[200:]:
        data_date = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        elif mutation == "truncate":
            future = {k: truncate_before(h, s) for k, h in history.items()}
        elif mutation == "spy_only_halve":
            future = {**history, SPY_SYMBOL: mutate_from(history[SPY_SYMBOL], s, halve)}
        else:
            future = {**history, SPY_SYMBOL: truncate_before(history[SPY_SYMBOL], s)}
        future_prepared = prepare_b(future)
        assert same_design(future_prepared.design_on(members, data_date), prepared.design_on(members, data_date)), s
        for name, params in MODELS.items():
            before = STRATEGY_B.picks(history, members, data_date, params)
            assert STRATEGY_B.picks(future, members, data_date, params) == before, (s, name)
            assert STRATEGY_B.picks_prepared(future_prepared, members, data_date, params) == before, (s, name)
            assert STRATEGY_B.picks_prepared(prepared, members, data_date, params) == before, (s, name)
            nonempty += bool(before)
    assert nonempty > 0


def test_the_spy_mutation_does_change_later_designs_and_picks():
    # Guards test_no_look_ahead: the same SPY mutation, read at data_date = S, changes the SPY
    # columns, and the SPY-gated model's picks with them.
    days, history = lookahead_set()
    members = frozenset(history)
    changed = 0
    for s in days[200:]:
        future = {**history, SPY_SYMBOL: mutate_from(history[SPY_SYMBOL], s, halve)}
        before = design_at(history, members, s)
        after = design_at(future, members, s)
        assert before.symbols == after.symbols and len(before) > 0
        assert before.X[:, :15].tobytes() == after.X[:, :15].tobytes()
        assert before.X[:, 15:].tobytes() != after.X[:, 15:].tobytes()
        p = MODELS["spy_gated"]
        changed += STRATEGY_B.picks(future, members, s, p) != STRATEGY_B.picks(history, members, s, p)
    assert changed > 0


# ---- SPY is never a pick; empty and short histories ------------------------------------------


def test_spy_is_never_a_pick_even_as_a_liquid_member():
    days, history = lookahead_set()
    d = days[230]
    members = frozenset(history)
    prepared = prepare_b(history)
    assert SPY_SYMBOL not in prepared.symbols
    picks = STRATEGY_B.picks(history, members, d, MODELS["all_positive"])
    assert symbols(picks) == sorted(s for s in history if s != SPY_SYMBOL)  # every candidate, by symbol
    assert STRATEGY_B.picks_prepared(prepared, members, d, MODELS["all_positive"]) == picks
    assert STRATEGY_B.picks(history, {SPY_SYMBOL}, d, MODELS["all_positive"]) == []


def test_prepare_on_empty_or_short_history():
    d = date(2019, 6, 3)
    short = {"X": hist("X", sawtooth(150)), SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(150))}
    for history in ({}, short):
        prepared = prepare_b(history)
        assert prepared.raw.shape == (0, 18) and prepared.spy.shape == (0, 3)
        assert len(prepared.design_on({"X"}, d)) == 0
        assert STRATEGY_B.picks_prepared(prepared, {"X"}, d, MODELS["all_positive"]) == []
        assert STRATEGY_B.picks(history, {"X"}, d, MODELS["all_positive"]) == []
```
**Impact:** +48 tests. Measured wall time is about 25 s for both new files together. The slowest
tests are the design bit-identity test (3.9 s) and each `test_no_look_ahead` case (about 2.8 s).

## Verification

**Setup** (once per worktree, from `/home/miftah/.worktrees/seer/strategy-b-ranker`):
`python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`. Never use
`/home/miftah/seer/engine/.venv`. Then run `docker start seer-pg`.

**Build:** `engine/.venv/bin/python -c "import seer_engine.strategies as s, sys; assert 'sklearn' not in sys.modules; print(s.STRATEGY_B.id)"` prints `B`.

**Tests:**
- New files first:
  `engine/.venv/bin/pytest engine/tests/test_indicators_b.py engine/tests/test_strategy_b.py engine/tests/test_indicators.py engine/tests/test_strategy_purity.py -q`
- Then the full suite:
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`

**Expected count:**
- On its own, on `0e91d8a`: **761 + 59 = 820 passed, 0 skipped.**
- With phases 1 and 3 merged: 820 + their counts. Any other number is a finding.

**Pre-verified:** the exact code above was run in a scratch copy of the tree at `0e91d8a`, with
numpy 2.4.6 and Python 3.11:
- all 59 new tests pass;
- `test_indicators.py`, `test_strategy_purity.py`, `test_strategy_a.py` and
  `test_strategy_a2.py` stay green.

**Untouched-file check:**
`git diff --stat 0e91d8a -- engine/src/seer_engine/strategies/a.py engine/src/seer_engine/strategies/a2.py engine/src/seer_engine/strategies/base.py engine/tests/test_indicators.py engine/tests/stratkit.py engine/src/seer_engine/backtest engine/src/seer_engine/sim`
prints nothing. `git diff 0e91d8a -- engine/src/seer_engine/strategies/indicators.py` shows
additions only, with no `-` line.

**Manual check (optional performance):** on Neon's cached market, `STRATEGY_B.prepare(market.history)`
should take about 5 s, and `design_on` should take under 1 ms per date.

**Exit criteria:**
- the suite is green with 0 skipped and 59 more tests than before;
- `test_strategy_purity.py` lists `seer_engine.strategies.b`;
- `import seer_engine.strategies` loads no `sklearn`;
- no out-of-scope file differs from `0e91d8a`.

## Handoffs

- **Phase 1 (R5):** `BModel.predict` must return a float64 ndarray of shape `(rows,)`, never
  float32 and never `(rows, 1)`. Otherwise `picks_from_design` raises `ValueError`. HGB's
  `predict` returns float64, and the ridge loop must start from `np.full(rows, intercept,
  dtype=np.float64)`.
- **Phase 4 (R1/R3/R4):**
  - Build `CandidateTable` rows by calling `prepared.design_on(market.membership.members_on(d), d)`
    per data date. Its `X`, `close`, `atr` and `symbols` are already in (symbol) order, and an
    empty `Design` has `X.shape == (0, 18)`.
  - Use `b.bracket(sym, float(close), float(atr))` for limit, TP and SL, as `float(Decimal)`.
    `None` means an invalid bracket, so the row gets NaN.
  - `passed_nights` must mirror `picks_from_design`'s emptiness exactly: pred > 0.0 (strict),
    NaN never qualifies, and the bracket must be valid.
- **Phase 5:**
  - read `b.FEATURE_NAMES` (18, in model column order) for the importance tables;
  - read the frozen model as `seer_engine.strategies.b.STRATEGY_B_FROZEN`, which is **not**
    re-exported from the package;
  - render `FrozenModel.train_end` with `.isoformat()`.
- **Phase 7 (R8):** replace exactly the three placeholder lines quoted in Step 2 with the comment
  naming the report and a `FrozenModel(...)` value. `test_constants` here already accepts either
  None or a `FrozenModel`, so this phase's tests need no edit.
- **Docs (phase 7, R9):** `engine/package_readme.md` should document:
  - the feature list (`RAW_COLUMNS`), the candidate rule, the `rank01` tie rule and SPY's
    whole-date gate;
  - `prepare_b`'s measured 5.0 s and about 262 MB of raw columns.

  This phase does not edit the readme.
- **Not done here (scope):** a `log` transform of `dollar_volume_20` (D6: the rank is
  identical) and any feature beyond the handover's list.

## Risks

- **Memory peak:** about 525 MB transiently in `prepare_b` on the full market (262 MB of `raw`
  plus the reorder copy). Phase 6 runs A2's `prepare` (A's columns, about 70 MB) in the same
  process. That is fine on this box. If it ever matters, preallocate `raw` and fill it in date
  order (no change in values).
- **`prepare_b` is about 5 s versus A's 2.8 s.** That is within "seconds" (handover §3
  "Runtime") and runs once per command.
- **The rank feature set changes with members.** This is intended: ranks are cross-sectional
  among d's candidates (handover §3). Phase 4 must pass the same `members_on(d)` the runner uses,
  or the training X will not equal the traded X.

## Rollback

Delete `strategies/b.py`, `tests/test_indicators_b.py` and `tests/test_strategy_b.py`. Restore
`strategies/__init__.py` and `strategies/indicators.py` from `0e91d8a`:
`git checkout 0e91d8a -- engine/src/seer_engine/strategies/__init__.py engine/src/seer_engine/strategies/indicators.py`.
Nothing else depends on this phase until phase 4 lands.
