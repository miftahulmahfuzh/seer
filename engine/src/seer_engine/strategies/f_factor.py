"""Families F4/F5/F6: cross-sectional stock factors over index members (P7a, handover §4.B).

One allocator, ``FACTOR`` (id ``"FAC"``); ``Candidate.family`` carries F4, F5 or F6.

On ``data_date`` d, a symbol is **eligible** when all of these hold:
    it is a member on d and is not ``"SPY"``; it has a bar dated d and at least
    ``factor_lookback(params)`` bars through d; its momentum, volatility and dollar volume are
    finite; volatility > 0; 20-day mean close×volume > ``min_dollar_volume`` (strict); and
    close >= ``min_price``.
Features, each a function of the symbol's bars ending at d only:
    momentum      = return_window(close, mom_n, mom_skip)   (12-1: c[-22] / c[-253] − 1)
    volatility    = stdev_return_window(close, vol_n)       (population stdev of one-bar returns)
    dollar volume = mean_dollar_volume_window(close, volume, 20)
Ranking (ties broken by symbol ascending):
    momentum   — momentum descending, the first ``top``;
    lowvol     — volatility ascending, the first ``top``;
    mom_lowvol — the ``pool`` highest-momentum names, then among them volatility ascending, the first ``top``.
Weights: ``equal`` gives every chosen name ``equal_weight(top)`` (fewer than ``top`` eligible names
leave the rest in cash); ``inverse_vol`` gives ``to_weight((1/vol_i) / Σ(1/vol) × k / top)`` for the
k chosen names — the same total exposure as ``equal`` — floor-quantized so Σ <= 1. A weight that
floors to zero drops its name.
Trend gate: when ``trend = (symbol, n)``, nothing is targeted (all cash) unless that symbol has a
bar dated d, at least n bars through d, and close > SMA(n) (strict).
Held positions get no special treatment: the targets are exactly the new top set, so a held name
that falls out of it is signal-exited by the book engine (a rebalance).

Every window function is end-relative and bit-identical however long its window (see
``indicators``), so ``prepare`` computes rolling features over each symbol's whole history and
``targets_prepared`` equals ``targets`` on ``upto(d)`` bit for bit (the Allocator contract).
Volatility and momentum columns depend on the params, so ``FactorPrepared`` computes each
(mom_n, mom_skip) and vol_n column lazily, once, and keeps it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    return_window,
    rolling,
    sma_window,
    stdev_return_window,
)

DV_N = 20  # dollar-volume window, as Strategy A
EXCLUDED: frozenset[str] = frozenset({"SPY"})  # never a factor target, even if listed as a member
MAX_TOP = 1000  # equal_weight(top) stays >= 0.001

Rank = Literal["momentum", "lowvol", "mom_lowvol"]
Sizing = Literal["equal", "inverse_vol"]
_RANKS: tuple[str, ...] = ("momentum", "lowvol", "mom_lowvol")
_SIZINGS: tuple[str, ...] = ("equal", "inverse_vol")


def _plain(x: float | Decimal) -> str:
    """``x`` as a plain decimal string without trailing zeros: 5.0 -> "5", 20000000.0 -> "20000000"."""
    d = Decimal(repr(x)) if isinstance(x, float) else x
    return format(d.normalize(), "f")


def _check_int(name: str, v: object, lo: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo:
        raise ValueError(f"{name} must be >= {lo}, got {v}")
    return v


def _check_float(name: str, v: object) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    out = float(v)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite, got {out!r}")
    return out


@dataclass(frozen=True, slots=True)
class FactorParams:
    """F4/F5/F6 parameters. Defaults are the plan contract's."""

    rank: Rank
    top: int = 10  # holdings
    mom_n: int = 252
    mom_skip: int = 21  # 12-1 momentum = return_window(c, mom_n, mom_skip)
    vol_n: int = 60  # stdev_return_window(c, vol_n)
    pool: int = 50  # mom_lowvol: the `pool` highest-momentum names, then the `top` lowest vol
    sizing: Sizing = "equal"
    min_dollar_volume: float = 20_000_000.0  # 20-day mean close×volume > this (strict)
    min_price: float = 5.0  # close >= min_price
    trend: tuple[str, int] | None = ("SPY", 200)  # all cash unless trend[0] close > SMA(trend[1]) on d

    def __post_init__(self) -> None:
        if not isinstance(self.rank, str):
            raise TypeError(f"rank must be a str, got {type(self.rank).__name__}")
        if self.rank not in _RANKS:
            raise ValueError(f"rank must be one of {_RANKS}, got {self.rank!r}")
        _check_int("top", self.top, 1)
        if self.top > MAX_TOP:
            raise ValueError(f"top must be <= {MAX_TOP}, got {self.top}")
        _check_int("mom_n", self.mom_n, 2)
        _check_int("mom_skip", self.mom_skip, 0)
        if self.mom_skip >= self.mom_n:
            raise ValueError(f"mom_skip must be < mom_n, got {self.mom_skip} >= {self.mom_n}")
        _check_int("vol_n", self.vol_n, 2)
        _check_int("pool", self.pool, 1)
        if self.rank == "mom_lowvol" and self.pool < self.top:
            raise ValueError(f"pool must be >= top for mom_lowvol, got pool={self.pool} top={self.top}")
        if not isinstance(self.sizing, str):
            raise TypeError(f"sizing must be a str, got {type(self.sizing).__name__}")
        if self.sizing not in _SIZINGS:
            raise ValueError(f"sizing must be one of {_SIZINGS}, got {self.sizing!r}")
        dv = _check_float("min_dollar_volume", self.min_dollar_volume)
        if dv < 0.0:
            raise ValueError(f"min_dollar_volume must be >= 0, got {dv}")
        object.__setattr__(self, "min_dollar_volume", dv)
        price = _check_float("min_price", self.min_price)
        if price < 0.01:
            raise ValueError(f"min_price must be >= 0.01, got {price}")
        object.__setattr__(self, "min_price", price)
        if self.trend is not None:
            if not isinstance(self.trend, tuple) or len(self.trend) != 2:
                raise TypeError(f"trend must be None or a (symbol, n) tuple, got {self.trend!r}")
            symbol, n = self.trend
            if not isinstance(symbol, str) or not symbol:
                raise ValueError(f"trend symbol must be a non-empty str, got {symbol!r}")
            _check_int("trend n", n, 1)

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        return {
            "rank": self.rank,
            "top": str(self.top),
            "mom_n": str(self.mom_n),
            "mom_skip": str(self.mom_skip),
            "vol_n": str(self.vol_n),
            "pool": str(self.pool),
            "sizing": self.sizing,
            "min_dollar_volume": _plain(self.min_dollar_volume),
            "min_price": _plain(self.min_price),
            "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
        }


def _check_params(params: object) -> FactorParams:
    if not isinstance(params, FactorParams):
        raise TypeError(f"params must be FactorParams, got {type(params).__name__}")
    return params


def factor_lookback(params: FactorParams) -> int:
    """Bars each read symbol needs through d: max(mom_n + 1, vol_n + 1, 20, trend n)."""
    _check_params(params)
    trend_n = params.trend[1] if params.trend is not None else 0
    return max(params.mom_n + 1, params.vol_n + 1, DV_N, trend_n)


@dataclass(frozen=True, slots=True)
class FactorRow:
    """One eligible symbol's features at a ``data_date`` close (float, bit-identical across paths)."""

    symbol: str
    close: float
    momentum: float
    vol: float
    dollar_volume: float


def _eligible_mask(
    close: np.ndarray, mom: np.ndarray, vol: np.ndarray, dv: np.ndarray, params: FactorParams
) -> np.ndarray:
    """The feature part of eligibility, shared verbatim by both paths."""
    return (
        np.isfinite(close)
        & np.isfinite(mom)
        & np.isfinite(vol)
        & np.isfinite(dv)
        & (vol > 0.0)
        & (dv > params.min_dollar_volume)
        & (close >= params.min_price)
    )


def factor_rows(
    history: Mapping[str, History], members: Set[str], data_date: date, params: FactorParams
) -> list[FactorRow]:
    """Eligible members' features on ``data_date``, sorted by symbol (the single-window path).

    Reads each member's last ``factor_lookback(params)`` bars ending at ``data_date``; later bars
    are never read.
    """
    _check_params(params)
    as_day(data_date)
    lb = factor_lookback(params)
    symbols: list[str] = []
    ends: list[int] = []
    for symbol in sorted(members):
        if symbol in EXCLUDED:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < lb:
            continue
        symbols.append(symbol)
        ends.append(i + 1)
    if not symbols:
        return []
    close = np.stack([history[s].close[e - lb : e] for s, e in zip(symbols, ends, strict=True)])
    volume = np.stack([history[s].volume[e - lb : e] for s, e in zip(symbols, ends, strict=True)])
    with np.errstate(divide="ignore", invalid="ignore"):
        mom = return_window(close, params.mom_n, params.mom_skip)
        vol = stdev_return_window(close, params.vol_n)
        dv = mean_dollar_volume_window(close, volume, DV_N)
    last = close[:, -1]
    mask = _eligible_mask(last, mom, vol, dv, params)
    return [
        FactorRow(symbols[k], float(last[k]), float(mom[k]), float(vol[k]), float(dv[k]))
        for k in (int(j) for j in np.flatnonzero(mask))
    ]


def trend_on(history: Mapping[str, History], data_date: date, params: FactorParams) -> bool:
    """The trend gate on ``data_date``: True when ``params.trend`` is None, else close > SMA(n) (strict).

    False when the trend symbol is absent, has no bar dated ``data_date`` or fewer than n bars
    through it. Reads only bars dated on or before ``data_date``.
    """
    _check_params(params)
    as_day(data_date)
    if params.trend is None:
        return True
    symbol, n = params.trend
    h = history.get(symbol)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    window = h.close[i + 1 - n : i + 1].reshape(1, n)
    sma = sma_window(window, n)[0]
    return bool(window[0, -1] > sma)


def rank_rows(rows: Sequence[FactorRow], params: FactorParams) -> list[FactorRow]:
    """The chosen rows, in rank order (ties by symbol ascending)."""
    _check_params(params)
    by_momentum = sorted(rows, key=lambda r: (-r.momentum, r.symbol))
    if params.rank == "momentum":
        return by_momentum[: params.top]
    if params.rank == "lowvol":
        return sorted(rows, key=lambda r: (r.vol, r.symbol))[: params.top]
    pool = by_momentum[: params.pool]
    return sorted(pool, key=lambda r: (r.vol, r.symbol))[: params.top]


def _floor_weight(x: float) -> Decimal | None:
    """``to_weight(x)``, or None when ``x`` floors to zero (or is not a finite positive float)."""
    if not np.isfinite(x) or Decimal(repr(x)) < WEIGHT_QUANTUM:
        return None
    return to_weight(x)


def factor_weights(chosen: Sequence[FactorRow], params: FactorParams) -> list[Decimal | None]:
    """One weight per chosen row (None = floors to zero, the row is dropped). Σ of the non-None <= 1."""
    _check_params(params)
    if not chosen:
        return []
    if params.sizing == "equal":
        w = equal_weight(params.top)
        return [w for _ in chosen]
    inverse = [1.0 / r.vol for r in chosen]
    total = 0.0
    for x in inverse:
        total = total + x
    scale = len(chosen) / params.top
    return [_floor_weight(x / total * scale) for x in inverse]


def targets_from_rows(rows: Sequence[FactorRow], params: FactorParams) -> tuple[Target, ...]:
    """Rank, weigh and price ``rows``: Targets with no limit, stop or take, in rank order."""
    chosen = rank_rows(rows, params)
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


def _check_held(held: object) -> None:
    if not isinstance(held, Set):
        raise TypeError(f"held must be a set of symbols, got {type(held).__name__}")


_EMPTY_F64 = np.empty(0, dtype=np.float64)
_EMPTY_F64.setflags(write=False)


@dataclass(frozen=True, slots=True, eq=False)
class FactorPrepared:
    """Param-independent columns for every (symbol, date) with at least ``DV_N`` bars through it.

    Columnar, ordered by (date, symbol). ``momentum``/``vol`` columns depend on the params, so
    ``column`` computes each one on first use from ``history`` and caches it in ``cache``.
    """

    symbols: tuple[str, ...]  # sorted; ``sym`` indexes into it
    dates: np.ndarray  # datetime64[D], ascending
    sym: np.ndarray  # int32
    nbars: np.ndarray  # int32: bars through that date (the row's index in its history + 1)
    close: np.ndarray  # float64
    dollar_volume: np.ndarray  # float64, mean_dollar_volume_window over DV_N
    history: Mapping[str, History] = field(repr=False)
    order: np.ndarray = field(repr=False)  # the (date, symbol) permutation of the per-symbol concatenation
    cache: dict[tuple[Any, ...], np.ndarray] = field(default_factory=dict, repr=False)

    def _rows(self, data_date: date) -> tuple[int, int]:
        day = as_day(data_date)
        lo = int(np.searchsorted(self.dates, day, side="left"))
        hi = int(np.searchsorted(self.dates, day, side="right"))
        return lo, hi

    def _included(self) -> list[History]:
        return [self.history[s] for s in self.symbols if len(self.history[s]) >= DV_N]

    def column(self, key: tuple[Any, ...]) -> np.ndarray:
        """``("mom", n, skip)`` or ``("vol", n)`` over every row, computed once and cached."""
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        parts: list[np.ndarray] = []
        for h in self._included():
            with np.errstate(divide="ignore", invalid="ignore"):
                if key[0] == "mom":
                    full = rolling(return_window, h.close, window=key[1] + 1, n=key[1], skip=key[2])
                elif key[0] == "vol":
                    full = rolling(stdev_return_window, h.close, window=key[1] + 1, n=key[1])
                else:
                    raise ValueError(f"unknown feature column {key!r}")
            parts.append(full[DV_N - 1 :])
        col = np.concatenate(parts)[self.order] if parts else _EMPTY_F64.copy()
        col.setflags(write=False)
        self.cache[key] = col
        return col

    def rows_on(self, members: Set[str], data_date: date, params: FactorParams) -> list[FactorRow]:
        """Eligible members' features on ``data_date``, sorted by symbol (== ``factor_rows`` on ``upto``)."""
        _check_params(params)
        lo, hi = self._rows(data_date)
        if lo == hi:
            return []
        window = slice(lo, hi)
        mom = self.column(("mom", params.mom_n, params.mom_skip))[window]
        vol = self.column(("vol", params.vol_n))[window]
        close = self.close[window]
        dv = self.dollar_volume[window]
        mask = (self.nbars[window] >= factor_lookback(params)) & _eligible_mask(close, mom, vol, dv, params)
        out: list[FactorRow] = []
        for j in (int(j) for j in np.flatnonzero(mask)):
            symbol = self.symbols[int(self.sym[lo + j])]
            if symbol in EXCLUDED or symbol not in members:
                continue
            out.append(FactorRow(symbol, float(close[j]), float(mom[j]), float(vol[j]), float(dv[j])))
        return out


def prepare_factor(history: Mapping[str, History]) -> FactorPrepared:
    """Rolling param-independent columns over every symbol's whole history (see ``FactorPrepared``)."""
    symbols = tuple(sorted(history))
    kept = {s: history[s] for s in symbols}
    parts: dict[str, list[np.ndarray]] = {k: [] for k in ("dates", "sym", "nbars", "close", "dv")}
    for k, symbol in enumerate(symbols):
        h = kept[symbol]
        if len(h) < DV_N:
            continue
        start = DV_N - 1
        parts["dates"].append(h.dates[start:])
        parts["sym"].append(np.full(len(h) - start, k, dtype=np.int32))
        parts["nbars"].append(np.arange(start + 1, len(h) + 1, dtype=np.int32))
        parts["close"].append(h.close[start:])
        parts["dv"].append(rolling(mean_dollar_volume_window, h.close, h.volume, window=DV_N, n=DV_N)[start:])
    if not parts["dates"]:
        empty_i = np.empty(0, dtype=np.int32)
        return FactorPrepared(
            symbols,
            np.empty(0, dtype="datetime64[D]"),
            empty_i,
            empty_i,
            _EMPTY_F64,
            _EMPTY_F64,
            history=kept,
            order=np.empty(0, dtype=np.int64),
        )
    dates = np.concatenate(parts["dates"])
    order = np.argsort(dates, kind="stable")  # symbols were appended in sorted order

    def col(key: str) -> np.ndarray:
        arr = np.concatenate(parts[key])[order]
        arr.setflags(write=False)
        return arr

    order.setflags(write=False)
    return FactorPrepared(
        symbols,
        col("dates"),
        col("sym"),
        col("nbars"),
        col("close"),
        col("dv"),
        history=kept,
        order=order,
    )


class FactorAllocator:
    """F4/F5/F6 behind the ``Allocator`` protocol."""

    id = "FAC"

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check_params(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check_params(params)
        return () if p.trend is None else (p.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check_params(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check_params(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _check_params(params)
        _check_held(held)
        if not trend_on(history, data_date, p):
            return ()
        return targets_from_rows(factor_rows(history, members, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> FactorPrepared:
        return prepare_factor(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        p = _check_params(params)
        _check_held(held)
        if not trend_on(prepared.history, data_date, p):
            return ()
        return targets_from_rows(prepared.rows_on(members, data_date, p), p)


FACTOR = FactorAllocator()
