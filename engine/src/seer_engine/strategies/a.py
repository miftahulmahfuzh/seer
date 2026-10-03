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
# Frozen by P3 (Strategy A + 10-year backtest), run on Neon data through 2026-10-02.
# Selected by the fixed 81-run grid on the IN-SAMPLE window 2015-10-19..2021-12-31 only:
# highest in-sample total return among runs with max drawdown <= 15% and profit factor >= 1.3
# (DESIGN_PARAMS when none qualifies). The out-of-sample window 2022-01-03..2026-10-02 was run once
# with these values and never tuned on. Gate verdict: FAILED.
# Report: docs/backtests/2026-10-02-strategy-a.md
# tests/test_strategy_a_frozen.py fails if these drift from that report's frozen-params line.
# Changing any value resets the forward clock: re-run `seer_engine backtest` and commit its report.
STRATEGY_A_PARAMS: AParams = AParams(
    rsi_max=10.0,
    limit_atr=Decimal("0.5"),
    tp_atr=Decimal("1.0"),
    sl_atr=Decimal("1.5"),
    min_dollar_volume=20_000_000.0,
)


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
