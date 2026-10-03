# Phase 1: B model interface + scikit-learn dependency

**Plan set:** `STRATEGY_B_RANKER_PLAN.md`
**Analysis:** `20261003-180843-B6R1_code_analyzer.md`
**Satisfies:** R5 (model determinism), R6 (purity of the new module), R9 (scikit-learn reaches CI) — B's model can be fit, predicted, identified by content and serialized, the same bits every time
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

After this phase, `seer_engine.strategies.b_model` exists exactly as the plan index's shared
contract describes. It fits the pre-registered tree (B) and ridge (B-linear) models, predicts
per row bit-identically, gives each model a content digest as its identity, ranks features by
split gain or |coef| × std, and pickles and unpickles models. scikit-learn `>=1.9,<1.10` is a
declared engine dependency, so `pip install -e 'engine[dev]'` (local and CI) installs it. A test
file proves the determinism the handover pre-registers, including across OpenMP thread counts.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates** (all in `engine/src/seer_engine/strategies/b_model.py`, new; names and semantics exactly as the index contract):
- constants `TREE = "tree"`, `RIDGE = "ridge"`, `KINDS = (TREE, RIDGE)`, `TREE_PARAMS` (the handover's 8 settings), `RIDGE_ALPHA = 1.0`, `BLOCK_ROWS = 65_536`;
- `RidgeFit(coef: np.ndarray, intercept: float)` — `@dataclass(frozen=True, slots=True, eq=False)`, `coef` read-only float64;
- `BModel(kind, n_features, digest, estimator)` — `@dataclass(frozen=True, eq=False)` with `__eq__`/`__hash__` on `(kind, n_features, digest)`, `predict(X) -> float64 (rows,)`, `as_dict() -> {"kind", "digest"}`;
- `check_xy(X, y) -> None`, `fit_tree(X, y, *, threads=None) -> BModel`, `fit_ridge(X, y, alpha=RIDGE_ALPHA) -> BModel`, `fit(kind, X, y) -> BModel`, `importance(model, X) -> tuple[float, ...]`, `r2(y, pred) -> float | None`, `dumps(model) -> bytes`, `loads(data) -> BModel`, `sha256(data) -> str`.
- Private helpers (not contract): `_matrix`, `_vector`, `_threads`, `_tree_digest`, `_ridge_digest`, `_column_sums`, `_sum`, `_sum_sq`, `_column_std`, `_shares`.
- `engine/tests/test_b_model.py` (new): **29 tests** (25 functions; 4 of them parametrized over `KINDS`).
- `engine/pyproject.toml`: dependency `"scikit-learn>=1.9,<1.10"`.

**Error behavior (callers in phases 4 and 6 rely on it):**
- `check_xy` / `fit_*`: `TypeError` when X or y is not an `np.ndarray` or not float64; `ValueError` when X is not 2-D, y not 1-D, rows differ, 0 rows or 0 columns, or any non-finite value.
- `BModel.predict`: `TypeError` for non-ndarray / non-float64; `ValueError` for non-2-D or wrong column count; 0 rows → `np.empty(0, float64)` without touching the estimator. NaN is not rejected by `predict` (B's designs are finite by construction, phase 2).
- `fit_tree(threads=)`: `ValueError` unless `None` or an `int >= 1` (bools rejected).
- `fit_ridge(alpha=)`: `ValueError` unless finite and `>= 0`.
- `fit`: `ValueError` on an unknown kind. `dumps`: `TypeError` on a non-`BModel`. `loads`: `ValueError` on a malformed payload.
- `importance`: X shape-checked against `n_features` (`ValueError`); the TREE branch ignores X's values; the RIDGE branch needs ≥ 1 row.
- `r2`: `ValueError` on length mismatch or empty input; `None` when `SS_tot == 0`.

**Determinism facts this phase establishes (and tests):**
- Two `fit_*` calls on equal data give `==` models, equal digests and **byte-identical `dumps`**.
- `fit_tree(threads=1)`, `threads=2` and `threads=None` give equal digests; separate processes under `OMP_NUM_THREADS=1` and `4` give equal digests and predictions.
- **`dumps(loads(blob)) != blob` for a TREE model is possible** (pickle re-frames the memo of an unpickled estimator: measured +26 bytes on a 443 KB pickle). Identity across a round trip is `loads(blob) == model` (digest recomputed), never re-pickled bytes. See Handoffs (phase 6, 7).
- The tree digest hashes `nodes.tobytes()`; the node dtype is packed (itemsize 56 == sum of field sizes, `isalignedstruct` False, verified on 1.9.1), so there are no uninitialized padding bytes.

**Requires (from earlier phases):** nothing.
**Constraint placed on phase 2:** `strategies/__init__.py` must not import `b_model` (the index already says so). `test_module_is_pure_and_imports_cleanly` asserts `import seer_engine.strategies` leaves `sklearn` out of `sys.modules`; phase 2's exports keep that true.
**Leaves alone (owned by others):** `strategies/b.py`, `strategies/__init__.py`, `strategies/indicators.py` (phase 2); `backtest/labels.py` (phase 3); `backtest/b_walkforward.py` (phase 4); `backtest/b_report.py` (phase 5); `backtest/io.py`, `commands/backtest_b.py` (phase 6); docs, `STRATEGY_B_FROZEN`, `test_strategy_b_frozen.py` (phase 7); every out-of-scope file in the index (`sim/*`, `a.py`, `a2.py`, `base.py`, `runner.py`, `walkforward.py`, …); every existing test file.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/pyproject.toml:17` | modify | add `"scikit-learn>=1.9,<1.10",` after `"python-dotenv>=1.0",` in `dependencies` |
| `engine/src/seer_engine/strategies/b_model.py` | create | the whole module (Step 2) |
| `engine/tests/test_b_model.py` | create | 29 tests (Step 3) |

No other file changes. `test_strategy_purity.py` covers the new module through its glob without
edits; `.github/workflows/engine-ci.yml` already runs `pip install -e 'engine[dev]'`.

## Implementation Steps

### Step 0: Worktree venv

From the worktree root (index invariant 1; never use `/home/miftah/seer/engine/.venv`):

```bash
cd /home/miftah/.worktrees/seer/strategy-b-ranker
test -x engine/.venv/bin/python || python3 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'      # re-run after Step 1 so scikit-learn lands
docker start seer-pg
```

### Step 1: Pin scikit-learn
**File:** `engine/pyproject.toml:17`
**Change:** add one dependency line after `"python-dotenv>=1.0",`. The resulting block:
**Code:**
```toml
dependencies = [
  "psycopg[binary]>=3.2",
  "pandas>=2.2",
  "numpy>=2",
  "pandas_market_calendars>=5.0",
  "yfinance>=1.0",
  "requests>=2.32",
  "python-dotenv>=1.0",
  "scikit-learn>=1.9,<1.10",
]
```
**Impact:** `pip install -e 'engine[dev]'` pulls scikit-learn 1.9.x plus scipy, joblib and
threadpoolctl (scikit-learn's own dependencies). `b_model.py` imports `threadpoolctl` directly;
it is a hard requirement of every scikit-learn 1.9 release, so it is not listed separately (a
drive-by pin would be scope creep). Then re-run `engine/.venv/bin/pip install -e 'engine[dev]'`.

### Step 2: Create the model module
**File:** `engine/src/seer_engine/strategies/b_model.py` (new)
**Change:** the whole file below. It was run against scikit-learn 1.9.1 / numpy 2.4.6 /
threadpoolctl 3.7.0 / Python 3.11 in a scratch copy of the engine before this plan was written:
the 29 tests in Step 3 and `test_strategy_purity.py` pass, also pinned to 2 cores with
`OMP_NUM_THREADS=2` (CI shape). Purity: no `logging`/`time`/`random`/`urllib` import, no
`.random`/`.now`/`.today` attribute, no `open`/`print` call (`random_state=0` is a keyword
inside `TREE_PARAMS`, not an attribute). Ridge at 1.2M × 18 fits in 0.18 s and predicts in
0.08 s.
**Code:**
```python
"""Strategy B's models: fit, predict, identity and serialization. Pure.

Two fixed models, pre-registered in docs/handover/2026-10-03-strategy-b-ranker.md §3:

- ``TREE`` (B, the gated model): scikit-learn ``HistGradientBoostingRegressor`` with the
  handover's fixed hyperparameters (``TREE_PARAMS``). No hyperparameter search.
- ``RIDGE`` (B-linear, information only): ridge regression, alpha ``RIDGE_ALPHA``, in numpy
  closed form with an unpenalized intercept.

Determinism (handover §3 "Determinism"; plan Decisions D9, D10):

- A model's identity is ``BModel.digest``, the sha256 of its functional content: the tree's
  baseline and every node array, or the ridge coefficients and intercept. Two ``BModel``\\ s are
  equal when kind, feature count and digest are, so a ``ParamsSchedule`` of models compares by
  content, never by object identity.
- ``predict`` is per-row bit-identical: row i's value never depends on the other rows or on the
  batch size. The tree sums its trees per row in a fixed order (scikit-learn's predictor); the
  ridge model adds ``X[:, j] * coef[j]`` in an explicit column loop.
- The ridge fit accumulates ``XᵀX`` and ``Xᵀy`` over fixed ``BLOCK_ROWS`` blocks with
  ``np.einsum(..., optimize=False)``, which never calls BLAS, and solves the 18×18 system under a
  one-thread BLAS limit. Its result depends on the data only, never on thread counts.
- ``fit_tree(..., threads=n)`` fits under ``threadpoolctl.threadpool_limits(n)``. The walk-forward
  compares ``threads=1`` against the default to run the pre-registered determinism probe.

Feature importance is split gain for the tree and |coef| × population std for ridge: permutation
importance would need randomness, which this module may not use (tests/test_strategy_purity.py).

The tree digest reads scikit-learn's private ``_baseline_prediction`` and ``_predictors``;
``engine/pyproject.toml`` pins scikit-learn's minor version (``>=1.9,<1.10``) for that reason and
so a pickled model stays loadable.
"""

from __future__ import annotations

import hashlib
import math
import pickle
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

TREE = "tree"
RIDGE = "ridge"
KINDS: tuple[str, ...] = (TREE, RIDGE)

# Pre-registered (handover §3 "Model (gated)"); never searched, never changed after a result.
TREE_PARAMS: dict[str, object] = dict(
    loss="squared_error",
    learning_rate=0.05,
    max_iter=300,
    max_leaf_nodes=15,
    min_samples_leaf=200,
    l2_regularization=1.0,
    early_stopping=False,
    random_state=0,
)
# Pre-registered (handover §3 "Model (information only)").
RIDGE_ALPHA = 1.0
# Rows per accumulation block in every reduction here; results depend on the data only.
BLOCK_ROWS = 65_536


@dataclass(frozen=True, slots=True, eq=False)
class RidgeFit:
    """A fitted ridge model: ``pred = intercept + Σ_j X[:, j] * coef[j]``."""

    coef: np.ndarray  # float64 (n_features,), read-only
    intercept: float


@dataclass(frozen=True, eq=False)
class BModel:
    """A fitted B model. Identity is ``(kind, n_features, digest)``; the estimator is the payload."""

    kind: str
    n_features: int
    digest: str
    estimator: Any  # fitted HistGradientBoostingRegressor (TREE) | RidgeFit (RIDGE)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BModel):
            return NotImplemented
        return (self.kind, self.n_features, self.digest) == (other.kind, other.n_features, other.digest)

    def __hash__(self) -> int:
        return hash((self.kind, self.n_features, self.digest))

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predicted net return per row, float64 ``(rows,)``. Per-row bit-identical (module doc)."""
        X = _matrix("X", X, self.n_features)
        rows = X.shape[0]
        if rows == 0:
            return np.empty(0, dtype=np.float64)
        if self.kind == TREE:
            return np.asarray(self.estimator.predict(X), dtype=np.float64)
        fit: RidgeFit = self.estimator
        acc = np.full(rows, fit.intercept, dtype=np.float64)
        for j in range(self.n_features):
            acc = acc + X[:, j] * fit.coef[j]
        return acc

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "digest": self.digest}


def _matrix(name: str, X: object, n_features: int | None = None) -> np.ndarray:
    if not isinstance(X, np.ndarray):
        raise TypeError(f"{name} must be a numpy array, got {type(X).__name__}")
    if X.dtype != np.float64:
        raise TypeError(f"{name} must be float64, got {X.dtype}")
    if X.ndim != 2:
        raise ValueError(f"{name} must be 2-D (rows, features), got {X.ndim}-D")
    if n_features is not None and X.shape[1] != n_features:
        raise ValueError(f"{name} has {X.shape[1]} columns, the model expects {n_features}")
    return X


def _vector(name: str, y: object) -> np.ndarray:
    if not isinstance(y, np.ndarray):
        raise TypeError(f"{name} must be a numpy array, got {type(y).__name__}")
    if y.dtype != np.float64:
        raise TypeError(f"{name} must be float64, got {y.dtype}")
    if y.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got {y.ndim}-D")
    return y


def check_xy(X: np.ndarray, y: np.ndarray) -> None:
    """Training input: X 2-D float64 finite with >= 1 row and >= 1 column; y 1-D float64 finite, same rows."""
    X = _matrix("X", X)
    y = _vector("y", y)
    if X.shape[0] < 1 or X.shape[1] < 1:
        raise ValueError(f"X must have at least one row and one column, got shape {X.shape}")
    if y.shape[0] != X.shape[0]:
        raise ValueError(f"X has {X.shape[0]} rows but y has {y.shape[0]}")
    if not np.isfinite(X).all():
        raise ValueError("X has a non-finite value")
    if not np.isfinite(y).all():
        raise ValueError("y has a non-finite value")


def _threads(threads: object) -> int | None:
    if threads is None:
        return None
    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise ValueError(f"threads must be None or an int >= 1, got {threads!r}")
    return threads


def _tree_digest(estimator: HistGradientBoostingRegressor) -> str:
    """sha256 of the baseline, then every predictor's node array, in iteration order."""
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(estimator._baseline_prediction, dtype=np.float64).tobytes())
    for iteration in estimator._predictors:
        for predictor in iteration:
            h.update(np.ascontiguousarray(predictor.nodes).tobytes())
    return h.hexdigest()


def _ridge_digest(fit: RidgeFit) -> str:
    return hashlib.sha256(fit.coef.tobytes() + np.float64(fit.intercept).tobytes()).hexdigest()


def fit_tree(X: np.ndarray, y: np.ndarray, *, threads: int | None = None) -> BModel:
    """Fit B's tree model with ``TREE_PARAMS``; ``threads`` caps OpenMP/BLAS threads for the fit."""
    check_xy(X, y)
    limit = _threads(threads)
    estimator = HistGradientBoostingRegressor(**TREE_PARAMS)
    if limit is None:
        estimator.fit(X, y)
    else:
        with threadpool_limits(limits=limit):
            estimator.fit(X, y)
    return BModel(TREE, int(X.shape[1]), _tree_digest(estimator), estimator)


def _column_sums(X: np.ndarray) -> np.ndarray:
    """Σ over rows per column: fixed blocks, each by einsum (no BLAS), blocks added in order."""
    acc = np.zeros(X.shape[1], dtype=np.float64)
    for start in range(0, X.shape[0], BLOCK_ROWS):
        acc = acc + np.einsum("ij->j", X[start : start + BLOCK_ROWS], optimize=False)
    return acc


def _sum(y: np.ndarray) -> float:
    """Σ y: fixed blocks, each by einsum, blocks added in order."""
    acc = 0.0
    for start in range(0, y.shape[0], BLOCK_ROWS):
        acc = acc + float(np.einsum("i->", y[start : start + BLOCK_ROWS], optimize=False))
    return acc


def _sum_sq(d: np.ndarray) -> float:
    """Σ d²: fixed blocks, each by einsum, blocks added in order."""
    acc = 0.0
    for start in range(0, d.shape[0], BLOCK_ROWS):
        block = d[start : start + BLOCK_ROWS]
        acc = acc + float(np.einsum("i,i->", block, block, optimize=False))
    return acc


def _column_std(X: np.ndarray) -> np.ndarray:
    """Population (ddof 0) std per column: block-summed mean, then block-summed squared deviations."""
    X = np.ascontiguousarray(X)
    rows = X.shape[0]
    mean = _column_sums(X) / rows
    acc = np.zeros(X.shape[1], dtype=np.float64)
    for start in range(0, rows, BLOCK_ROWS):
        dev = X[start : start + BLOCK_ROWS] - mean
        acc = acc + np.einsum("ij,ij->j", dev, dev, optimize=False)
    return np.sqrt(acc / rows)


def fit_ridge(X: np.ndarray, y: np.ndarray, alpha: float = RIDGE_ALPHA) -> BModel:
    """Ridge in closed form with an unpenalized intercept (plan D9).

    Centre X and y on their means, accumulate ``XcᵀXc`` and ``Xcᵀyc`` per ``BLOCK_ROWS`` block
    with ``einsum(optimize=False)``, solve ``(XcᵀXc + alpha·I) coef = Xcᵀyc`` under a one-thread
    BLAS limit, then ``intercept = ybar - Σ_j xbar_j·coef_j`` in an explicit loop.
    """
    check_xy(X, y)
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not math.isfinite(alpha) or alpha < 0:
        raise ValueError(f"alpha must be a finite number >= 0, got {alpha!r}")
    X = np.ascontiguousarray(X)
    y = np.ascontiguousarray(y)
    rows, n = X.shape
    xbar = _column_sums(X) / rows
    ybar = _sum(y) / rows
    xtx = np.zeros((n, n), dtype=np.float64)
    xty = np.zeros(n, dtype=np.float64)
    for start in range(0, rows, BLOCK_ROWS):
        xc = X[start : start + BLOCK_ROWS] - xbar
        yc = y[start : start + BLOCK_ROWS] - ybar
        xtx = xtx + np.einsum("ij,ik->jk", xc, xc, optimize=False)
        xty = xty + np.einsum("ij,i->j", xc, yc, optimize=False)
    system = xtx + float(alpha) * np.eye(n, dtype=np.float64)
    with threadpool_limits(limits=1):
        coef = np.linalg.solve(system, xty)
    coef = np.ascontiguousarray(coef, dtype=np.float64)
    coef.setflags(write=False)
    intercept = float(ybar)
    for j in range(n):
        intercept = intercept - float(xbar[j]) * float(coef[j])
    fit = RidgeFit(coef, intercept)
    return BModel(RIDGE, int(n), _ridge_digest(fit), fit)


def fit(kind: str, X: np.ndarray, y: np.ndarray) -> BModel:
    """Fit the model of ``kind`` (``TREE`` or ``RIDGE``) with its pre-registered settings."""
    if kind == TREE:
        return fit_tree(X, y)
    if kind == RIDGE:
        return fit_ridge(X, y)
    raise ValueError(f"unknown model kind {kind!r}; expected one of {KINDS}")


def _shares(weights: list[float]) -> tuple[float, ...]:
    total = 0.0
    for w in weights:
        total = total + w
    if total == 0.0:
        return tuple(0.0 for _ in weights)
    return tuple(w / total for w in weights)


def importance(model: BModel, X: np.ndarray) -> tuple[float, ...]:
    """One share per feature, summing to 1.0 (all 0.0 when there is nothing to share).

    TREE: total split gain per feature over every non-leaf node of every tree (``X`` is only
    shape-checked). RIDGE: ``|coef_j| × population std of X[:, j]``.
    """
    X = _matrix("X", X, model.n_features)
    if model.kind == TREE:
        gains = [0.0] * model.n_features
        for iteration in model.estimator._predictors:
            for predictor in iteration:
                nodes = predictor.nodes
                for feature, gain, leaf in zip(
                    nodes["feature_idx"].tolist(), nodes["gain"].tolist(), nodes["is_leaf"].tolist()
                ):
                    if not leaf:
                        gains[feature] = gains[feature] + gain
        return _shares(gains)
    if X.shape[0] < 1:
        raise ValueError("X must have at least one row for ridge importance")
    std = _column_std(X)
    coef = model.estimator.coef
    return _shares([abs(float(coef[j])) * float(std[j]) for j in range(model.n_features)])


def r2(y: np.ndarray, pred: np.ndarray) -> float | None:
    """``1 - SS_res / SS_tot``; None when ``SS_tot == 0`` (constant y). Block-summed."""
    y = _vector("y", y)
    pred = _vector("pred", pred)
    if y.shape[0] != pred.shape[0] or y.shape[0] < 1:
        raise ValueError(f"y and pred must have the same, non-zero length: {y.shape[0]} vs {pred.shape[0]}")
    y = np.ascontiguousarray(y)
    pred = np.ascontiguousarray(pred)
    ybar = _sum(y) / y.shape[0]
    ss_tot = _sum_sq(y - ybar)
    if ss_tot == 0.0:
        return None
    ss_res = _sum_sq(y - pred)
    return 1.0 - ss_res / ss_tot


def dumps(model: BModel) -> bytes:
    """The model artifact: ``pickle.dumps((kind, n_features, estimator), protocol=5)``."""
    if not isinstance(model, BModel):
        raise TypeError(f"expected a BModel, got {type(model).__name__}")
    return pickle.dumps((model.kind, model.n_features, model.estimator), protocol=5)


def loads(data: bytes) -> BModel:
    """Inverse of ``dumps``. The digest is recomputed from the estimator, never trusted from the bytes.

    Only for artifacts this project wrote and committed: unpickling runs code from the payload.
    """
    payload = pickle.loads(data)
    if not isinstance(payload, tuple) or len(payload) != 3:
        raise ValueError("not a B model artifact: expected (kind, n_features, estimator)")
    kind, n_features, estimator = payload
    if kind not in KINDS:
        raise ValueError(f"unknown model kind {kind!r} in artifact")
    if isinstance(n_features, bool) or not isinstance(n_features, int) or n_features < 1:
        raise ValueError(f"bad n_features {n_features!r} in artifact")
    if kind == TREE:
        if not isinstance(estimator, HistGradientBoostingRegressor) or not hasattr(estimator, "_predictors"):
            raise ValueError("tree artifact does not hold a fitted HistGradientBoostingRegressor")
        if int(estimator.n_features_in_) != n_features:
            raise ValueError(f"tree artifact fitted on {estimator.n_features_in_} features, header says {n_features}")
        return BModel(TREE, n_features, _tree_digest(estimator), estimator)
    if not isinstance(estimator, RidgeFit):
        raise ValueError("ridge artifact does not hold a RidgeFit")
    coef = np.array(estimator.coef, dtype=np.float64)
    if coef.shape != (n_features,):
        raise ValueError(f"ridge artifact coef shape {coef.shape}, header says ({n_features},)")
    coef.setflags(write=False)
    ridge = RidgeFit(coef, float(estimator.intercept))
    return BModel(RIDGE, n_features, _ridge_digest(ridge), ridge)


def sha256(data: bytes) -> str:
    """Hex sha256 of ``data`` (the artifact's checksum in ``STRATEGY_B_FROZEN``)."""
    return hashlib.sha256(data).hexdigest()
```
**Impact:** new module only; nothing imports it yet. Notes for the implementer:
- `predict` for TREE delegates to `HistGradientBoostingRegressor.predict`, which sums trees per
  row in iteration order (OpenMP splits rows, never a row's sum), so it is batch-independent;
  the tests pin this with batch, one-by-one, chunks of 7, reversed order and Fortran layout.
- `fit_ridge` normalizes layout with `np.ascontiguousarray` before the block loop, so a
  Fortran-ordered or sliced X gives the same bits as a C-ordered copy. `np.linalg.solve` runs
  under `threadpool_limits(limits=1)` so the 18×18 LAPACK call is single-threaded regardless of
  the BLAS pool.
- `intercept` and the importance shares are Python floats; the loops are explicit so the
  summation order is fixed.
- `loads` copies `coef` and sets it read-only again (unpickled arrays come back writeable).

### Step 3: Tests
**File:** `engine/tests/test_b_model.py` (new)
**Change:** the whole file below. It imports `_module_name` and `_pure_sources` from
`test_strategy_purity` (tests already import sibling test modules, e.g.
`test_backtest_walkforward.py:27`), which imports no `test_*` function, so nothing is collected
twice. The test may use `np.random.default_rng`; the module may not.
**Code:**
```python
"""Strategy B's model interface: fit, per-row prediction, identity, determinism, serialization.

docs/handover/2026-10-03-strategy-b-ranker.md §3 "Model", "Determinism", "Dependency"; plan
Decisions D9 (ridge), D10 (tree), D11 (importance), D15 (artifact). The test may draw random
numbers; the module may not (tests/test_strategy_purity.py).
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import sklearn

import seer_engine
from seer_engine.strategies import b_model
from seer_engine.strategies.b_model import (
    BLOCK_ROWS,
    KINDS,
    RIDGE,
    RIDGE_ALPHA,
    TREE,
    TREE_PARAMS,
    BModel,
    RidgeFit,
    check_xy,
    dumps,
    fit,
    fit_ridge,
    fit_tree,
    importance,
    loads,
    r2,
    sha256,
)
from test_strategy_purity import _module_name, _pure_sources

N_FEATURES = 18
PKG_SRC = Path(seer_engine.__file__).resolve().parent.parent


def _data(rows: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic (X, y): 18 uniform features, a signal in features 0, 3 and 5, Gaussian noise."""
    rng = np.random.default_rng(seed)
    X = rng.random((rows, N_FEATURES))
    y = (X[:, 0] - 0.5) * 0.02 + X[:, 3] * X[:, 5] * 0.01 + rng.normal(0.0, 0.01, rows)
    return X, y


@pytest.fixture(scope="module")
def data() -> tuple[np.ndarray, np.ndarray]:
    return _data(4_000, seed=11)


@pytest.fixture(scope="module")
def models(data: tuple[np.ndarray, np.ndarray]) -> dict[str, BModel]:
    X, y = data
    return {TREE: fit_tree(X, y), RIDGE: fit_ridge(X, y)}


def test_hyperparameters_are_the_pre_registered_ones():
    assert KINDS == (TREE, RIDGE) == ("tree", "ridge")
    assert TREE_PARAMS == {
        "loss": "squared_error",
        "learning_rate": 0.05,
        "max_iter": 300,
        "max_leaf_nodes": 15,
        "min_samples_leaf": 200,
        "l2_regularization": 1.0,
        "early_stopping": False,
        "random_state": 0,
    }
    assert RIDGE_ALPHA == 1.0
    assert BLOCK_ROWS == 65_536


def test_scikit_learn_is_the_pinned_minor():
    assert sklearn.__version__.startswith("1.9.")


def test_tree_fits_the_signal_and_predicts_float64(data, models):
    X, y = data
    model = models[TREE]
    assert model.kind == TREE and model.n_features == N_FEATURES
    pred = model.predict(X)
    assert pred.dtype == np.float64 and pred.shape == (X.shape[0],)
    assert r2(y, pred) > 0.3
    assert len(model.estimator._predictors) == 300


def test_ridge_matches_a_hand_solved_case():
    # Centred X is [[-1,-1],[1,-1],[-1,1],[1,1]], so XcᵀXc = 4·I; y = 1 + 2·x1 - x2 exactly.
    X = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 2.0], [2.0, 2.0]])
    y = np.array([1.0, 5.0, -1.0, 3.0])
    # alpha = 1: Xcᵀyc = (8, -4), coef = (8, -4) / 5, intercept = 2 - 1·1.6 - 1·(-0.8) = 1.2.
    ridge = fit_ridge(X, y)
    assert ridge.estimator.coef.tolist() == pytest.approx([1.6, -0.8], abs=1e-12)
    assert ridge.estimator.intercept == pytest.approx(1.2, abs=1e-12)
    # alpha = 0 is ordinary least squares and recovers the generating line.
    ols = fit_ridge(X, y, alpha=0.0)
    assert ols.estimator.coef.tolist() == pytest.approx([2.0, -1.0], abs=1e-12)
    assert ols.estimator.intercept == pytest.approx(1.0, abs=1e-12)
    assert ols.predict(X).tolist() == pytest.approx(y.tolist(), abs=1e-12)


def test_ridge_agrees_with_a_direct_solve_across_blocks():
    # More rows than one block, so the per-block accumulation is exercised.
    X, y = _data(BLOCK_ROWS + 4_321, seed=5)
    model = fit_ridge(X, y, alpha=2.5)
    xbar = X.mean(axis=0)
    ybar = y.mean()
    xc = X - xbar
    coef = np.linalg.solve(xc.T @ xc + 2.5 * np.eye(N_FEATURES), xc.T @ (y - ybar))
    assert model.estimator.coef.tolist() == pytest.approx(coef.tolist(), rel=1e-9, abs=1e-12)
    assert model.estimator.intercept == pytest.approx(ybar - float(xbar @ coef), abs=1e-12)


def test_ridge_intercept_is_not_penalized():
    X, y = _data(2_000, seed=6)
    y = y + 3.0
    model = fit_ridge(X, y, alpha=1e12)
    assert np.abs(model.estimator.coef).max() < 1e-9
    assert model.estimator.intercept == pytest.approx(float(y.mean()), abs=1e-9)


def test_ridge_coefficients_are_read_only(models):
    coef = models[RIDGE].estimator.coef
    assert coef.dtype == np.float64 and coef.shape == (N_FEATURES,)
    with pytest.raises(ValueError):
        coef[0] = 1.0


def test_ridge_predict_is_the_explicit_column_loop(data, models):
    X, _ = data
    model = models[RIDGE]
    expected = np.full(X.shape[0], model.estimator.intercept)
    for j in range(N_FEATURES):
        expected = expected + X[:, j] * model.estimator.coef[j]
    assert np.array_equal(model.predict(X), expected)


@pytest.mark.parametrize("kind", KINDS)
def test_predictions_are_per_row_bit_identical(kind, data, models):
    X, _ = data
    model = models[kind]
    rows = X[:500]
    batch = model.predict(rows)
    one_by_one = np.concatenate([model.predict(rows[i : i + 1]) for i in range(rows.shape[0])])
    chunks = np.concatenate([model.predict(rows[i : i + 7]) for i in range(0, rows.shape[0], 7)])
    reversed_rows = model.predict(np.ascontiguousarray(rows[::-1]))[::-1]
    fortran = model.predict(np.asfortranarray(rows))
    assert np.array_equal(batch, one_by_one)
    assert np.array_equal(batch, chunks)
    assert np.array_equal(batch, reversed_rows)
    assert np.array_equal(batch, fortran)
    assert np.array_equal(batch, model.predict(X)[:500])


@pytest.mark.parametrize("kind", KINDS)
def test_two_fits_of_the_same_data_are_equal(kind, data, models):
    X, y = data
    again = fit(kind, X.copy(), y.copy())
    first = models[kind]
    assert again == first and hash(again) == hash(first)
    assert again.digest == first.digest and again.as_dict() == first.as_dict() == {"kind": kind, "digest": first.digest}
    assert again.estimator is not first.estimator
    assert np.array_equal(again.predict(X), first.predict(X))
    assert dumps(again) == dumps(first)


def test_identity_is_kind_features_and_digest(data, models):
    X, y = data
    tree, ridge = models[TREE], models[RIDGE]
    other_tree = fit_tree(X, y + 0.001)
    other_ridge = fit_ridge(X, y + 0.001)
    assert other_tree != tree and other_tree.digest != tree.digest
    assert other_ridge != ridge and other_ridge.digest != ridge.digest
    assert tree != ridge
    assert BModel(TREE, N_FEATURES, tree.digest, None) == tree
    assert BModel(RIDGE, N_FEATURES, tree.digest, None) != tree
    assert BModel(TREE, N_FEATURES - 1, tree.digest, None) != tree
    assert tree != tree.digest
    assert len({tree, ridge, BModel(TREE, N_FEATURES, tree.digest, None)}) == 2
    assert all(len(m.digest) == 64 and int(m.digest, 16) >= 0 for m in (tree, ridge))


def test_digests_follow_the_contract_formula(models):
    tree, ridge = models[TREE], models[RIDGE]
    h = hashlib.sha256()
    h.update(np.asarray(tree.estimator._baseline_prediction, dtype=np.float64).tobytes())
    for iteration in tree.estimator._predictors:
        for predictor in iteration:
            h.update(predictor.nodes.tobytes())
    assert tree.digest == h.hexdigest()
    fit_ = ridge.estimator
    expected = hashlib.sha256(fit_.coef.tobytes() + np.float64(fit_.intercept).tobytes()).hexdigest()
    assert ridge.digest == expected


def test_thread_limit_does_not_change_the_tree(data, models):
    X, y = data
    one = fit_tree(X, y, threads=1)
    two = fit_tree(X, y, threads=2)
    assert one == two == models[TREE]
    assert np.array_equal(one.predict(X), models[TREE].predict(X))
    for bad in (0, -1, 1.0, True, "1"):
        with pytest.raises(ValueError):
            fit_tree(X, y, threads=bad)


_THREAD_PROBE = """
import hashlib, json
import numpy as np
from seer_engine.strategies.b_model import fit_tree
rng = np.random.default_rng(20261003)
X = rng.random((50_000, 18))
y = (X[:, 0] - 0.5) * 0.02 + X[:, 3] * X[:, 5] * 0.01 + rng.normal(0.0, 0.03, 50_000)
model = fit_tree(X, y)
pred = model.predict(X)
print(json.dumps({"digest": model.digest, "pred": hashlib.sha256(pred.tobytes()).hexdigest()}))
"""


def _probe(threads: int) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["OMP_NUM_THREADS"] = str(threads)
    env["OPENBLAS_NUM_THREADS"] = str(threads)
    out = subprocess.run(
        [sys.executable, "-c", _THREAD_PROBE],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=300,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_tree_is_bit_identical_across_thread_counts():
    """Handover §3 "Determinism": OMP_NUM_THREADS=1 and 4 give the same model and predictions."""
    single = _probe(1)
    multi = _probe(4)
    assert single == multi
    assert len(single["digest"]) == 64


@pytest.mark.parametrize("kind", KINDS)
def test_dumps_loads_round_trip(kind, data, models):
    X, _ = data
    model = models[kind]
    blob = dumps(model)
    back = loads(blob)
    assert back == model and back.digest == model.digest
    assert back.kind == kind and back.n_features == N_FEATURES
    assert np.array_equal(back.predict(X), model.predict(X))
    # Re-pickling an unpickled estimator may frame its memo differently, so the bytes are not
    # compared; the artifact's identity is its own sha256 plus the digest loads() recomputes.
    assert loads(dumps(back)) == model
    assert sha256(blob) == hashlib.sha256(blob).hexdigest()
    assert pickle.loads(blob)[:2] == (kind, N_FEATURES)


def test_loads_recomputes_the_digest(models):
    ridge = models[RIDGE]
    kind, n, est = pickle.loads(dumps(ridge))
    tampered = RidgeFit(est.coef + 1e-6, est.intercept)
    other = loads(pickle.dumps((kind, n, tampered), protocol=5))
    assert other != ridge and other.digest != ridge.digest
    assert not other.estimator.coef.flags.writeable
    with pytest.raises(ValueError):
        loads(pickle.dumps(("forest", n, est), protocol=5))
    with pytest.raises(ValueError):
        loads(pickle.dumps((RIDGE, n + 1, est), protocol=5))
    with pytest.raises(ValueError):
        loads(pickle.dumps((TREE, n, est), protocol=5))
    with pytest.raises(ValueError):
        loads(pickle.dumps([kind, n, est], protocol=5))
    with pytest.raises(TypeError):
        dumps(est)


def test_sha256_is_the_hex_digest():
    assert sha256(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_tree_importance_is_split_gain_shares(data, models):
    X, _ = data
    model = models[TREE]
    shares = importance(model, X)
    assert len(shares) == N_FEATURES and all(isinstance(s, float) and s >= 0.0 for s in shares)
    assert sum(shares) == pytest.approx(1.0, abs=1e-12)
    top3 = sorted(range(N_FEATURES), key=lambda j: -shares[j])[:3]
    assert set(top3) == {0, 3, 5}
    gains = [0.0] * N_FEATURES
    for iteration in model.estimator._predictors:
        for predictor in iteration:
            for node in predictor.nodes:
                if not node["is_leaf"]:
                    gains[int(node["feature_idx"])] += float(node["gain"])
    assert list(shares) == pytest.approx([g / sum(gains) for g in gains], rel=1e-12)
    assert importance(model, X[:1]) == shares


def test_ridge_importance_is_abs_coef_times_std(data, models):
    X, _ = data
    model = models[RIDGE]
    shares = importance(model, X)
    weights = np.abs(model.estimator.coef) * X.std(axis=0)
    assert list(shares) == pytest.approx((weights / weights.sum()).tolist(), rel=1e-9)
    assert sum(shares) == pytest.approx(1.0, abs=1e-12)


def test_importance_is_all_zero_without_signal():
    X, _ = _data(1_000, seed=7)
    y = np.full(1_000, 0.25)
    for kind in KINDS:
        assert importance(fit(kind, X, y), X) == (0.0,) * N_FEATURES


def test_r2():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert r2(y, y.copy()) == 1.0
    assert r2(y, np.full(4, 2.5)) == 0.0
    # SS_res = 0.25·4 = 1.0, SS_tot = 5.0.
    assert r2(y, y + 0.5) == pytest.approx(0.8, abs=1e-15)
    assert r2(np.full(3, 2.0), np.array([1.0, 2.0, 3.0])) is None
    with pytest.raises(ValueError):
        r2(y, y[:3])
    with pytest.raises(ValueError):
        r2(np.empty(0), np.empty(0))
    with pytest.raises(TypeError):
        r2(y.astype(np.float32), y)


def test_check_xy_rejects_bad_training_input():
    X, y = _data(10, seed=1)
    check_xy(X, y)
    with pytest.raises(TypeError):
        check_xy(X.tolist(), y)
    with pytest.raises(TypeError):
        check_xy(X.astype(np.float32), y)
    with pytest.raises(TypeError):
        check_xy(X, y.astype(np.int64))
    with pytest.raises(ValueError):
        check_xy(X[0], y)
    with pytest.raises(ValueError):
        check_xy(X, y[:, None])
    with pytest.raises(ValueError):
        check_xy(X, y[:9])
    with pytest.raises(ValueError):
        check_xy(X[:0], y[:0])
    for bad in (np.nan, np.inf, -np.inf):
        Xb = X.copy()
        Xb[3, 4] = bad
        with pytest.raises(ValueError):
            check_xy(Xb, y)
        yb = y.copy()
        yb[2] = bad
        with pytest.raises(ValueError):
            check_xy(X, yb)
    for kind in KINDS:
        with pytest.raises(ValueError):
            fit(kind, X[:0], y[:0])
    with pytest.raises(ValueError):
        fit_ridge(X, y, alpha=-1.0)
    with pytest.raises(ValueError):
        fit_ridge(X, y, alpha=float("nan"))


@pytest.mark.parametrize("kind", KINDS)
def test_predict_validates_shape_and_handles_zero_rows(kind, data, models):
    X, _ = data
    model = models[kind]
    empty = model.predict(np.empty((0, N_FEATURES)))
    assert empty.dtype == np.float64 and empty.shape == (0,)
    with pytest.raises(ValueError):
        model.predict(X[:, :17])
    with pytest.raises(ValueError):
        model.predict(X[0])
    with pytest.raises(TypeError):
        model.predict(X.astype(np.float32))
    with pytest.raises(ValueError):
        importance(model, X[:, :17])


def test_fit_dispatches_by_kind(data, models):
    X, y = data
    assert fit(TREE, X, y) == models[TREE]
    assert fit(RIDGE, X, y) == models[RIDGE]
    with pytest.raises(ValueError):
        fit("forest", X, y)


def test_module_is_pure_and_imports_cleanly():
    names = {_module_name(p) for p in _pure_sources()}
    assert "seer_engine.strategies.b_model" in names
    assert b_model.__name__ == "seer_engine.strategies.b_model"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC) + os.pathsep + env.get("PYTHONPATH", "")
    code = (
        "import sys\n"
        "import seer_engine.strategies\n"
        "before = 'sklearn' in sys.modules\n"
        "import seer_engine.strategies.b_model\n"
        "bad = [m for m in ('psycopg', 'requests', 'yfinance', 'seer_engine.bars') if m in sys.modules]\n"
        "print(before, ','.join(bad))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True, timeout=120
    )
    # The strategies package never loads scikit-learn on its own; only b_model does.
    assert out.stdout.strip() == "False"
```
**Impact:** +29 tests. Wall time about 11 s on the 24-core box (the cross-process thread probe
is about 3.7 s, the tree fixtures about 2 s); about 11 s pinned to 2 cores.

Test inventory (29):

| # | Test | Count |
|---|---|---|
| 1 | `test_hyperparameters_are_the_pre_registered_ones` | 1 |
| 2 | `test_scikit_learn_is_the_pinned_minor` | 1 |
| 3 | `test_tree_fits_the_signal_and_predicts_float64` | 1 |
| 4 | `test_ridge_matches_a_hand_solved_case` (alpha 1 and alpha 0) | 1 |
| 5 | `test_ridge_agrees_with_a_direct_solve_across_blocks` (BLOCK_ROWS + 4,321 rows) | 1 |
| 6 | `test_ridge_intercept_is_not_penalized` | 1 |
| 7 | `test_ridge_coefficients_are_read_only` | 1 |
| 8 | `test_ridge_predict_is_the_explicit_column_loop` | 1 |
| 9 | `test_predictions_are_per_row_bit_identical[tree/ridge]` | 2 |
| 10 | `test_two_fits_of_the_same_data_are_equal[tree/ridge]` (incl. byte-identical `dumps`) | 2 |
| 11 | `test_identity_is_kind_features_and_digest` | 1 |
| 12 | `test_digests_follow_the_contract_formula` | 1 |
| 13 | `test_thread_limit_does_not_change_the_tree` (threads 1, 2, None; bad values) | 1 |
| 14 | `test_tree_is_bit_identical_across_thread_counts` (subprocess, OMP 1 vs 4, 50k × 18) | 1 |
| 15 | `test_dumps_loads_round_trip[tree/ridge]` | 2 |
| 16 | `test_loads_recomputes_the_digest` (tampered payload, malformed payloads) | 1 |
| 17 | `test_sha256_is_the_hex_digest` | 1 |
| 18 | `test_tree_importance_is_split_gain_shares` (top 3 = the signal features 0, 3, 5) | 1 |
| 19 | `test_ridge_importance_is_abs_coef_times_std` | 1 |
| 20 | `test_importance_is_all_zero_without_signal` (constant y: single-leaf trees, zero coef) | 1 |
| 21 | `test_r2` | 1 |
| 22 | `test_check_xy_rejects_bad_training_input` | 1 |
| 23 | `test_predict_validates_shape_and_handles_zero_rows[tree/ridge]` | 2 |
| 24 | `test_fit_dispatches_by_kind` | 1 |
| 25 | `test_module_is_pure_and_imports_cleanly` (glob covers it; fresh import loads no forbidden module; `seer_engine.strategies` alone loads no sklearn) | 1 |

## Verification

**Build:** `engine/.venv/bin/pip install -e 'engine[dev]' && engine/.venv/bin/python -c "import sklearn, seer_engine.strategies.b_model as m; print(sklearn.__version__, m.KINDS)"` → `1.9.x ('tree', 'ridge')`
**Tests:**
```bash
cd /home/miftah/.worktrees/seer/strategy-b-ranker
engine/.venv/bin/pytest engine/tests/test_b_model.py engine/tests/test_strategy_purity.py -q   # 32 passed
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q   # 790 passed, 0 skipped
git diff --stat 0e91d8a -- engine/src/seer_engine/sim engine/src/seer_engine/strategies/a.py engine/src/seer_engine/strategies/a2.py engine/src/seer_engine/strategies/base.py engine/src/seer_engine/backtest engine/src/seer_engine/commands engine/tests/test_strategy_purity.py   # empty
```
**Manual check:** `git status` shows exactly the three files in **Files** (plus nothing under
`engine/src/*.egg-info` tracked).
**Exit criteria:** the full suite is green with **0 skipped** at **761 + 29 = 790 passed** on this
phase alone (phases 1, 2 and 3 run concurrently: with phase 2 merged 849, with phase 3 merged
820, with both 879; see the index's count table);
`test_strategy_purity.py` lists `seer_engine.strategies.b_model` among the pure modules and
passes; `pip install -e 'engine[dev]'` installs scikit-learn 1.9.x.

## Handoffs

- **Phase 4 (`b_walkforward`)**: `probe_determinism` is `fit_tree(X, y, threads=1).digest ==
  fit_tree(X, y).digest` — both calls exist with exactly that signature. `train_folds` should
  call `fit(kind, X, y)`, `importance(model, X)` and `r2(y, model.predict(X))`; `r2` returns
  `None` for a constant label vector, so `FoldModel.r2` is `float | None` as the contract says.
  Training X/y must be float64 ndarrays with no NaN (filter unresolved labels first) or
  `check_xy` raises.
- **Phase 6 (`io.write_model_artifact`)**: write `b_model.dumps(model)` bytes and return
  `b_model.sha256(bytes)`. Do **not** re-derive bytes from a loaded model: re-pickling an
  unpickled tree may differ by a few framing bytes. A fresh fit's `dumps` is byte-identical
  across runs (tested), so "the artifact is rewritten byte-identically" on a re-run holds.
- **Phase 7 (`test_strategy_b_frozen.py`, pass branch)**: tie the artifact by
  `sha256(file bytes) == STRATEGY_B_FROZEN.sha256` and `b_model.loads(file bytes).digest ==` the
  report's `last-fold-model` digest. Never assert `dumps(loads(bytes)) == bytes`.
- **Phase 2**: keep `strategies/__init__.py` free of any `b_model` import (asserted here).
- **Phase 7 (readme, R9)**: document `b_model` (kinds, hyperparameters, digest identity,
  determinism probe, artifact format, the scikit-learn pin and why it is a minor pin).
- Not done, deliberately: listing `threadpoolctl` in `pyproject.toml` (transitive via
  scikit-learn); any README edit (phase 7, and the user's rule is README at release).

## Rollback

Revert this phase's commit: it deletes `b_model.py` and `test_b_model.py` and drops the one
`pyproject.toml` line. Then `engine/.venv/bin/pip install -e 'engine[dev]'` (scikit-learn may stay
installed in the venv harmlessly). Phases 4 and 6 import `b_model`, so they cannot land without it.
