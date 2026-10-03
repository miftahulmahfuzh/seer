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
