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
