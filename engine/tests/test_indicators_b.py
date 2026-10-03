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
