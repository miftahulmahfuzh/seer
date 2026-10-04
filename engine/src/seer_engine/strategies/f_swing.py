"""Family F7: longer-horizon mean reversion over index members (P7a, handover §4.B F7, D12).

A's idea (buy the oversold in an uptrend) under other trade levers: a longer horizon (the
rules' time stop, 10 or 20 sessions), no take-profit by default, and a signal exit at the next
open. This is a NEW candidate family under D12, never Strategy A re-run: it shares A's
indicator conventions (``strategies.indicators``), not A's module.

New entry, on ``data_date`` (all strict), for index members not already held:
    RSI(rsi_n) < rsi_max,  close > SMA(sma_n),  20-day mean close×volume > min_dollar_volume,
    and, when ``market_trend = (M, n)`` is set, M's close > SMA(n) of M's closes on data_date.
Entry target, Decimal at 4 dp (``sim.q``), from ``last = to_decimal(close)``, ``atr = to_decimal(ATR14)``:
    limit = q(last − limit_atr·atr)   (entry "dip")   or   last   (entry "close")
    stop  = q(limit − stop_atr·atr)   (None when stop_atr is None)
    take  = q(limit + take_atr·atr)   (None when take_atr is None)
built by ``allocator.target_from_close``, which drops the candidate when a price is <= 0 after
rounding or the ordering stop < limit < take fails (A's ``_bracket`` convention).

Held symbols: kept as a price-less target at weight ``equal_weight(slots)`` unless the exit
signal fires on data_date: close > SMA(exit_sma), or RSI(rsi_n) > exit_rsi (each strict, each
optional). A held symbol with no bar dated data_date, with too little history, or no longer an
index member is kept: there is nothing to decide on, and the engine's stop and time stop still
apply. Kept symbols come first, in symbol order (at most ``slots`` of them), then new entries by
(RSI ascending, symbol) until there are ``slots`` targets. The market-trend gate stops new
entries only.

Every member indicator is a function of the symbol's last ``member_window(params)`` bars
through data_date (Wilder recursions seeded inside that window), so ``targets`` and
``targets_prepared`` compute bit-identical floats. ``prepare`` rolls the indicator columns once
for the prepared periods (window 200, RSI(2), SMA(200), SMA(5): the defaults, which every
registry candidate uses); params with other periods are served by the single-window path on the
prepared history, so the P4 identity holds for every params value.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from seer_engine.prices import to_decimal
from seer_engine.sim import Target, equal_weight, q
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    rolling,
    sma_window,
    wilder_atr_window,
    wilder_rsi_window,
)

WINDOW = 200  # the minimum member window (A's LOOKBACK convention)
ATR_N = 14
DV_N = 20
MAX_SLOTS = 100
PREPARED_RSI_N = 2  # the periods prepare() rolls; other periods use the single-window path
PREPARED_SMA_N = 200
PREPARED_EXIT_SMA = 5

SwingEntry = Literal["dip", "close"]
_ENTRIES: tuple[str, ...] = ("dip", "close")


# --------------------------------------------------------------------------- params


def _plain(x: float | int | Decimal) -> str:
    """``x`` as a plain decimal string without trailing zeros: 10.0 -> "10", Decimal("0.50") -> "0.5"."""
    d = Decimal(repr(x)) if isinstance(x, float) else Decimal(x)
    return format(d.normalize(), "f")


def _check_int(name: str, v: object, lo: int, hi: int | None = None) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{name} must be an int, got {type(v).__name__}")
    if v < lo or (hi is not None and v > hi):
        bound = f">= {lo}" if hi is None else f"in {lo}..{hi}"
        raise ValueError(f"{name} must be {bound}, got {v}")
    return v


def _check_float(name: str, v: object) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(v).__name__}")
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite, got {v!r}")
    return f


def _check_decimal(name: str, v: object) -> Decimal:
    if not isinstance(v, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(v).__name__}")
    if not v.is_finite():
        raise ValueError(f"{name} must be finite, got {v!r}")
    return v


@dataclass(frozen=True, slots=True)
class SwingParams:
    """F7's fixed parameters. Defaults are the registry's base candidate (F7-RSI2-T20-DIP)."""

    slots: int = 4  # weight equal_weight(slots); kept + new <= slots (self-capped)
    rsi_n: int = 2
    rsi_max: float = 10.0  # setup: RSI(rsi_n) < rsi_max (strict)
    sma_n: int = 200  # setup: close > SMA(sma_n) (strict)
    entry: SwingEntry = "dip"  # Target.limit: dip = last − limit_atr × ATR14; close = last
    limit_atr: Decimal = Decimal("0.5")
    stop_atr: Decimal | None = Decimal("2.5")  # Target.stop = limit − stop_atr × ATR14 (None: no stop)
    take_atr: Decimal | None = None  # Target.take = limit + take_atr × ATR14 (None: no TP)
    exit_sma: int | None = 5  # signal exit when close > SMA(exit_sma) (strict)
    exit_rsi: float | None = None  # ... or when RSI(rsi_n) > exit_rsi (strict)
    min_dollar_volume: float = 20_000_000.0  # setup: 20-day mean close×volume > this (strict)
    market_trend: tuple[str, int] | None = None  # no NEW entries unless M close > SMA(n) of M; held kept

    def __post_init__(self) -> None:
        _check_int("slots", self.slots, 1, MAX_SLOTS)
        _check_int("rsi_n", self.rsi_n, 1)
        _check_int("sma_n", self.sma_n, 1)
        if self.exit_sma is not None:
            _check_int("exit_sma", self.exit_sma, 1)
        for name in ("rsi_max", "min_dollar_volume"):
            object.__setattr__(self, name, _check_float(name, getattr(self, name)))
        if not 0.0 < self.rsi_max <= 100.0:
            raise ValueError(f"rsi_max must be in (0, 100], got {self.rsi_max}")
        if self.min_dollar_volume < 0.0:
            raise ValueError(f"min_dollar_volume must be >= 0, got {self.min_dollar_volume}")
        if self.exit_rsi is not None:
            object.__setattr__(self, "exit_rsi", _check_float("exit_rsi", self.exit_rsi))
            if not 0.0 <= self.exit_rsi < 100.0:
                raise ValueError(f"exit_rsi must be in [0, 100), got {self.exit_rsi}")
        if not isinstance(self.entry, str):
            raise TypeError(f"entry must be a str, got {type(self.entry).__name__}")
        if self.entry not in _ENTRIES:
            raise ValueError(f"entry must be one of {_ENTRIES}, got {self.entry!r}")
        if _check_decimal("limit_atr", self.limit_atr) < 0:
            raise ValueError(f"limit_atr must be >= 0, got {self.limit_atr}")
        for name in ("stop_atr", "take_atr"):
            v = getattr(self, name)
            if v is not None and _check_decimal(name, v) <= 0:
                raise ValueError(f"{name} must be > 0 or None, got {v}")
        if self.market_trend is not None:
            t = self.market_trend
            if not isinstance(t, tuple) or len(t) != 2:
                raise TypeError(f"market_trend must be a (symbol, n) tuple or None, got {t!r}")
            if not isinstance(t[0], str) or not t[0]:
                raise TypeError(f"market_trend symbol must be a non-empty str, got {t[0]!r}")
            _check_int("market_trend n", t[1], 1)

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""

        def opt(v: float | int | Decimal | None) -> str:
            return "none" if v is None else _plain(v)

        trend = "none" if self.market_trend is None else f"{self.market_trend[0]}:{self.market_trend[1]}"
        return {
            "slots": _plain(self.slots),
            "rsi_n": _plain(self.rsi_n),
            "rsi_max": _plain(self.rsi_max),
            "sma_n": _plain(self.sma_n),
            "entry": self.entry,
            "limit_atr": _plain(self.limit_atr),
            "stop_atr": opt(self.stop_atr),
            "take_atr": opt(self.take_atr),
            "exit_sma": opt(self.exit_sma),
            "exit_rsi": opt(self.exit_rsi),
            "min_dollar_volume": _plain(self.min_dollar_volume),
            "market_trend": trend,
        }


def _params(params: Any) -> SwingParams:
    if not isinstance(params, SwingParams):
        raise TypeError(f"params must be SwingParams, got {type(params).__name__}")
    return params


def _held(held: Any) -> frozenset[str]:
    if not isinstance(held, AbstractSet):
        raise TypeError(f"held must be a set of symbols, got {type(held).__name__}")
    return frozenset(held)


def member_window(params: SwingParams) -> int:
    """Bars each member symbol needs through data_date; every member indicator reads exactly these."""
    n = max(WINDOW, params.sma_n, params.rsi_n + 1)
    if params.exit_sma is not None:
        n = max(n, params.exit_sma)
    return n


def swing_lookback(params: SwingParams) -> int:
    """``Allocator.lookback``: the member window, or the market-trend SMA when that is longer."""
    n = member_window(params)
    if params.market_trend is not None:
        n = max(n, params.market_trend[1])
    return n


# --------------------------------------------------------------------------- features


@dataclass(frozen=True, slots=True)
class SwingFeatures:
    """F7's indicator values for one symbol at one ``data_date`` close."""

    symbol: str
    data_date: date
    close: float
    sma: float  # SMA(sma_n)
    exit_sma: float | None  # SMA(exit_sma); None when params.exit_sma is None
    rsi: float  # Wilder RSI(rsi_n)
    atr: float  # Wilder ATR(14)
    dollar_volume: float  # 20-day mean close × volume


def features_at(
    history: Mapping[str, History], symbols: Iterable[str], data_date: date, params: SwingParams
) -> tuple[SwingFeatures, ...]:
    """Features of every symbol in ``symbols`` eligible on ``data_date``, sorted by symbol.

    Eligible: in ``history``, a bar dated ``data_date``, and at least ``member_window(params)``
    bars through it. Computed on exactly those last bars; later bars are never read.
    """
    p = _params(params)
    as_day(data_date)
    w = member_window(p)
    names: list[str] = []
    rows: list[int] = []
    for symbol in sorted(set(symbols)):
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < w:
            continue
        names.append(symbol)
        rows.append(i)
    if not names:
        return ()

    def stack(field: str) -> np.ndarray:
        return np.stack([getattr(history[s], field)[i + 1 - w : i + 1] for s, i in zip(names, rows, strict=True)])

    close, high, low, volume = stack("close"), stack("high"), stack("low"), stack("volume")
    sma = sma_window(close, p.sma_n)
    exit_sma = None if p.exit_sma is None else sma_window(close, p.exit_sma)
    rsi = wilder_rsi_window(close, p.rsi_n)
    atr = wilder_atr_window(high, low, close, ATR_N)
    dv = mean_dollar_volume_window(close, volume, DV_N)
    last = close[:, -1]
    return tuple(
        SwingFeatures(
            s,
            data_date,
            float(last[k]),
            float(sma[k]),
            None if exit_sma is None else float(exit_sma[k]),
            float(rsi[k]),
            float(atr[k]),
            float(dv[k]),
        )
        for k, s in enumerate(names)
    )


@dataclass(frozen=True, slots=True, eq=False)
class SwingPrepared:
    """F7's param-independent features for every (symbol, date) with ``WINDOW`` bars through it.

    Columnar, ordered by (date, symbol), rolled for the prepared periods (RSI(2), SMA(200),
    SMA(5), ATR(14), DV(20)) over a ``WINDOW``-bar window. ``history`` is kept for held symbols'
    last closes, the market-trend gate and params the columns do not cover.
    """

    history: Mapping[str, History]
    symbols: tuple[str, ...]  # sorted; ``sym`` indexes into it
    index: Mapping[str, int]  # symbol -> its position in ``symbols``
    dates: np.ndarray  # datetime64[D], ascending
    sym: np.ndarray  # int64; ascending within one date
    close: np.ndarray  # float64 columns, one row per (symbol, date)
    sma: np.ndarray
    exit_sma: np.ndarray
    rsi: np.ndarray
    atr: np.ndarray
    dollar_volume: np.ndarray

    def covers(self, params: SwingParams) -> bool:
        """True when the rolled columns are exactly what ``features_at`` computes for ``params``."""
        p = _params(params)
        return (
            member_window(p) == WINDOW
            and p.rsi_n == PREPARED_RSI_N
            and p.sma_n == PREPARED_SMA_N
            and p.exit_sma in (None, PREPARED_EXIT_SMA)
        )

    def _rows(self, data_date: date) -> tuple[int, int]:
        day = as_day(data_date)
        lo = int(np.searchsorted(self.dates, day, side="left"))
        hi = int(np.searchsorted(self.dates, day, side="right"))
        return lo, hi

    def _features(self, k: int, data_date: date, params: SwingParams) -> SwingFeatures:
        return SwingFeatures(
            self.symbols[int(self.sym[k])],
            data_date,
            float(self.close[k]),
            float(self.sma[k]),
            None if params.exit_sma is None else float(self.exit_sma[k]),
            float(self.rsi[k]),
            float(self.atr[k]),
            float(self.dollar_volume[k]),
        )

    def feature(self, symbol: str, data_date: date, params: SwingParams) -> SwingFeatures | None:
        """``symbol``'s row on ``data_date``, or None when it has none (requires ``covers(params)``)."""
        k = self.index.get(symbol)
        if k is None:
            return None
        lo, hi = self._rows(data_date)
        j = lo + int(np.searchsorted(self.sym[lo:hi], k, side="left"))
        if j < hi and int(self.sym[j]) == k:
            return self._features(j, data_date, params)
        return None

    def features_on(self, data_date: date, params: SwingParams) -> tuple[SwingFeatures, ...]:
        """Every row on ``data_date``, sorted by symbol (== ``features_at`` over every symbol)."""
        if not self.covers(params):
            raise ValueError("params use periods the prepared columns do not cover")
        lo, hi = self._rows(data_date)
        return tuple(self._features(k, data_date, params) for k in range(lo, hi))


def _readonly(arr: np.ndarray) -> np.ndarray:
    arr.setflags(write=False)
    return arr


def prepare_swing(history: Mapping[str, History]) -> SwingPrepared:
    """Rolling F7 features over every symbol's whole history (see ``SwingPrepared``)."""
    frozen = MappingProxyType(dict(sorted(history.items())))
    symbols = tuple(frozen)
    index = MappingProxyType({s: k for k, s in enumerate(symbols)})
    keys = ("dates", "sym", "close", "sma", "exit_sma", "rsi", "atr", "dv")
    parts: dict[str, list[np.ndarray]] = {key: [] for key in keys}
    start = WINDOW - 1
    for k, symbol in enumerate(symbols):
        h = frozen[symbol]
        if len(h) < WINDOW:
            continue
        parts["dates"].append(h.dates[start:])
        parts["sym"].append(np.full(len(h) - start, k, dtype=np.int64))
        parts["close"].append(h.close[start:])
        parts["sma"].append(rolling(sma_window, h.close, window=WINDOW, n=PREPARED_SMA_N)[start:])
        parts["exit_sma"].append(rolling(sma_window, h.close, window=WINDOW, n=PREPARED_EXIT_SMA)[start:])
        parts["rsi"].append(rolling(wilder_rsi_window, h.close, window=WINDOW, n=PREPARED_RSI_N)[start:])
        parts["atr"].append(rolling(wilder_atr_window, h.high, h.low, h.close, window=WINDOW, n=ATR_N)[start:])
        parts["dv"].append(rolling(mean_dollar_volume_window, h.close, h.volume, window=WINDOW, n=DV_N)[start:])
    if not parts["dates"]:
        empty = _readonly(np.empty(0, dtype=np.float64))
        return SwingPrepared(
            frozen,
            symbols,
            index,
            _readonly(np.empty(0, dtype="datetime64[D]")),
            _readonly(np.empty(0, dtype=np.int64)),
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
        )
    dates = np.concatenate(parts["dates"])
    order = np.argsort(dates, kind="stable")  # symbols were appended in sorted order

    def col(key: str) -> np.ndarray:
        return _readonly(np.concatenate(parts[key])[order])

    return SwingPrepared(
        frozen,
        symbols,
        index,
        col("dates"),
        col("sym"),
        col("close"),
        col("sma"),
        col("exit_sma"),
        col("rsi"),
        col("atr"),
        col("dv"),
    )


# --------------------------------------------------------------------------- decisions


def has_setup(f: SwingFeatures, params: SwingParams) -> bool:
    """The entry setup (each comparison strict); a non-finite close or ATR never qualifies."""
    return (
        f.rsi < params.rsi_max
        and f.close > f.sma
        and f.dollar_volume > params.min_dollar_volume
        and math.isfinite(f.close)
        and math.isfinite(f.atr)
    )


def has_exit_signal(f: SwingFeatures, params: SwingParams) -> bool:
    """close > SMA(exit_sma), or RSI(rsi_n) > exit_rsi (each strict, each only when set)."""
    if params.exit_sma is not None and f.exit_sma is not None and f.close > f.exit_sma:
        return True
    return params.exit_rsi is not None and f.rsi > params.exit_rsi


def entry_target(f: SwingFeatures, params: SwingParams) -> Target | None:
    """The new-entry ``Target`` (weight ``equal_weight(slots)``), or None for an invalid bracket.

    Prices are computed in Decimal at 4 dp exactly as A's bracket, then handed to
    ``target_from_close`` as floats: a 4-dp Decimal survives float -> repr -> Decimal exactly.
    """
    last = to_decimal(f.close)
    atr = to_decimal(f.atr)
    limit = last if params.entry == "close" else q(last - params.limit_atr * atr)
    stop = None if params.stop_atr is None else q(limit - params.stop_atr * atr)
    take = None if params.take_atr is None else q(limit + params.take_atr * atr)
    return target_from_close(
        f.symbol,
        f.close,
        equal_weight(params.slots),
        limit=float(limit),
        stop=None if stop is None else float(stop),
        take=None if take is None else float(take),
    )


def rank_entries(candidates: Iterable[SwingFeatures], params: SwingParams, free: int) -> tuple[Target, ...]:
    """The first ``free`` valid entries among ``candidates`` passing the setup, by (RSI, symbol)."""
    ranked: list[tuple[float, str, Target]] = []
    for f in candidates:
        if not has_setup(f, params):
            continue
        t = entry_target(f, params)
        if t is not None:
            ranked.append((f.rsi, f.symbol, t))
    ranked.sort(key=lambda r: (r[0], r[1]))
    return tuple(t for _, _, t in ranked[: max(free, 0)])


def trend_on(history: Mapping[str, History], trend: tuple[str, int] | None, data_date: date) -> bool:
    """The market-trend gate: True when unset; else M has a bar on data_date, >= n bars, close > SMA(n)."""
    if trend is None:
        return True
    symbol, n = trend
    h = history.get(symbol)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    window = h.close[i + 1 - n : i + 1].reshape(1, n)
    return float(h.close[i]) > float(sma_window(window, n)[0])


def _last_close(h: History, data_date: date) -> float | None:
    j = int(np.searchsorted(h.dates, as_day(data_date), side="right")) - 1
    return float(h.close[j]) if j >= 0 else None


def _kept(
    held: frozenset[str],
    history: Mapping[str, History],
    data_date: date,
    params: SwingParams,
    feature_of: Callable[[str], SwingFeatures | None],
) -> list[Target]:
    """Held symbols F7 still wants, in symbol order, at most ``slots``, as price-less targets."""
    weight = equal_weight(params.slots)
    out: list[Target] = []
    for symbol in sorted(held):
        if len(out) == params.slots:
            break
        f = feature_of(symbol)
        if f is not None:
            if has_exit_signal(f, params):
                continue
            close: float | None = f.close
        else:
            h = history.get(symbol)
            close = None if h is None else _last_close(h, data_date)
        if close is None or not math.isfinite(close):
            continue
        t = target_from_close(symbol, close, weight)
        if t is not None:
            out.append(t)
    return out


def _decide(
    kept: list[Target],
    candidates: Callable[[], Iterable[SwingFeatures]],
    gate: Callable[[], bool],
    params: SwingParams,
) -> tuple[Target, ...]:
    free = params.slots - len(kept)
    if free <= 0 or not gate():
        return tuple(kept)
    return tuple(kept) + rank_entries(candidates(), params, free)


# --------------------------------------------------------------------------- allocator


class SwingAllocator:
    """F7 behind the ``Allocator`` protocol."""

    id = "F7"

    def lookback(self, params: Any) -> int:
        return swing_lookback(_params(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _params(params)
        return () if p.market_trend is None else (p.market_trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _params(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _params(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _params(params)
        held_set = _held(held)
        feats = {f.symbol: f for f in features_at(history, set(members) | held_set, data_date, p)}
        kept = _kept(held_set, history, data_date, p, feats.get)
        return _decide(
            kept,
            lambda: [f for s, f in feats.items() if s in members and s not in held_set],
            lambda: trend_on(history, p.market_trend, data_date),
            p,
        )

    def prepare(self, history: Mapping[str, History]) -> SwingPrepared:
        return prepare_swing(history)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, SwingPrepared):
            raise TypeError(f"prepared must be SwingPrepared, got {type(prepared).__name__}")
        p = _params(params)
        if not prepared.covers(p):
            return self.targets(prepared.history, members, data_date, held, p)
        held_set = _held(held)
        as_day(data_date)
        kept = _kept(held_set, prepared.history, data_date, p, lambda s: prepared.feature(s, data_date, p))

        def candidates() -> list[SwingFeatures]:
            lo, hi = prepared._rows(data_date)
            window = slice(lo, hi)
            mask = (
                (prepared.close[window] > prepared.sma[window])
                & (prepared.rsi[window] < p.rsi_max)
                & (prepared.dollar_volume[window] > p.min_dollar_volume)
            )
            out: list[SwingFeatures] = []
            for j in np.flatnonzero(mask):
                k = lo + int(j)
                symbol = prepared.symbols[int(prepared.sym[k])]
                if symbol in members and symbol not in held_set:
                    out.append(prepared._features(k, data_date, p))
            return out

        return _decide(kept, candidates, lambda: trend_on(prepared.history, p.market_trend, data_date), p)


SWING = SwingAllocator()
