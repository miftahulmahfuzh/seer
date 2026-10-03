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
