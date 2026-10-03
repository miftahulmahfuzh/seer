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
