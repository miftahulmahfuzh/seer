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
