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
