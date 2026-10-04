"""Families F2 and F3: ETF rotation by momentum (handover §4.B; plan phase 6).

F2 (dual momentum, GEM-style) and F3 (sector rotation) are one allocator with different
``RotationParams``. ``Candidate.family`` carries the F2/F3 label; the allocator id is ``ROT``.

On ``data_date``'s close:

1. **Trend gate** (``trend = (symbol, n)``): unless that symbol has a bar dated ``data_date``,
   at least ``n`` bars through it, and its close is > SMA(n) of its daily closes (strict),
   every slot is unused (steps 2–3 are skipped).
2. **Ranking**: every ETF of ``universe`` that is *eligible* is ranked by its momentum
   ``c[-1] / c[-1-lookback] − 1`` (``indicators.return_window``, skip 0), highest first, ties
   by symbol ascending. Eligible: a bar dated ``data_date``, at least ``lookback + 1`` bars
   through it, a finite momentum, and a close that rounds (``prices.to_decimal``) to > 0. An
   ETF that is missing from the history, has no bar that day or is too short is left out for
   that date only; it never takes a slot.
3. **Selection**: the first ``top`` ranked ETFs, each at ``equal_weight(top)``. With
   ``absolute``, an ETF whose momentum is not > 0 (strict) leaves its slot unused.
4. **Fallback**: the unused slots (``top`` − selected) go to ``fallback`` as one target of
   weight ``equal_weight(top) × unused``, ranked last, when ``fallback`` has a bar dated
   ``data_date`` with a positive close; otherwise they stay in cash.

``held`` and ``members`` are ignored: the targets are a pure function of the ETFs' bars, so a
held ETF that is not in the new selection is signal-exited by the engine at the next open
(a rebalance), and no index member is read.

Every value is a function of the bars dated on or before ``data_date`` only: windows are
sliced at ``History.index_of(data_date)``. So ``targets`` on full histories, ``targets`` on
``upto(data_date)`` histories and ``targets_prepared`` return the same tuple (P4 identity).
Pure: no database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any

import numpy as np

from seer_engine.prices import to_decimal
from seer_engine.sim import Target, equal_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import return_window, sma_window

NONE_TEXT = "none"  # as_dict() text of an unset optional field


def _symbol(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str, got {type(value).__name__}")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty symbol without spaces, got {value!r}")
    return value


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < 1:
        raise ValueError(f"{name} must be >= 1, got {value}")
    return value


@dataclass(frozen=True, slots=True)
class RotationParams:
    """One F2/F3 rotation, fixed per candidate (see the module docstring for the rule)."""

    universe: tuple[str, ...]  # the ranked ETFs: sorted, unique, >= 2
    lookback: int  # momentum = c[-1] / c[-1-lookback] − 1 (return_window, skip 0); >= 1
    top: int  # keep the top K by momentum, each at equal_weight(top); 1 <= top <= len(universe)
    absolute: bool = True  # a slot is used only when that ETF's momentum > 0 (strict)
    fallback: str | None = None  # unused slots go here (when it has a bar on data_date), else cash
    trend: tuple[str, int] | None = None  # every slot unused unless trend[0] close > SMA(trend[1])

    def __post_init__(self) -> None:
        if not isinstance(self.universe, tuple):
            raise TypeError(f"universe must be a tuple, got {type(self.universe).__name__}")
        for s in self.universe:
            _symbol("universe symbol", s)
        if len(self.universe) < 2:
            raise ValueError(f"universe needs >= 2 ETFs, got {len(self.universe)}")
        if list(self.universe) != sorted(set(self.universe)):
            raise ValueError(f"universe must be sorted and unique, got {self.universe!r}")
        _positive_int("lookback", self.lookback)
        _positive_int("top", self.top)
        if self.top > len(self.universe):
            raise ValueError(f"top must be <= len(universe) = {len(self.universe)}, got {self.top}")
        if not isinstance(self.absolute, bool):
            raise TypeError(f"absolute must be a bool, got {type(self.absolute).__name__}")
        if self.fallback is not None:
            _symbol("fallback", self.fallback)
            if self.fallback in self.universe:
                raise ValueError(f"fallback {self.fallback} must not be in the universe")
        if self.trend is not None:
            if not isinstance(self.trend, tuple) or len(self.trend) != 2:
                raise TypeError(f"trend must be a (symbol, n) tuple or None, got {self.trend!r}")
            _symbol("trend symbol", self.trend[0])
            _positive_int("trend n", self.trend[1])

    def as_dict(self) -> dict[str, str]:
        """Every parameter as text, in a fixed key order (dev report and pre-registration)."""
        return {
            "universe": ",".join(self.universe),
            "lookback": str(self.lookback),
            "top": str(self.top),
            "absolute": "true" if self.absolute else "false",
            "fallback": self.fallback if self.fallback is not None else NONE_TEXT,
            "trend": f"{self.trend[0]}:{self.trend[1]}" if self.trend is not None else NONE_TEXT,
        }


def _params(params: object) -> RotationParams:
    if not isinstance(params, RotationParams):
        raise TypeError(f"params must be RotationParams, got {type(params).__name__}")
    return params


def _close_on(h: History | None, data_date: date) -> tuple[int, float] | None:
    """(row, close) of ``h``'s bar dated ``data_date`` when its close rounds to > 0, else None."""
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None:
        return None
    close = float(h.close[i])
    if not np.isfinite(close) or to_decimal(close) <= 0:
        return None
    return i, close


def momentum_at(h: History | None, data_date: date, lookback: int) -> tuple[float, float] | None:
    """(momentum, close) of ``h`` on ``data_date``, or None when it is not eligible that day.

    Momentum = return_window over the ``lookback + 1`` closes ending at ``data_date``.
    """
    found = _close_on(h, data_date)
    if found is None:
        return None
    i, close = found
    if i < lookback:  # fewer than lookback + 1 bars through data_date
        return None
    assert h is not None
    window = h.close[i - lookback : i + 1].reshape(1, lookback + 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        m = float(return_window(window, lookback)[0])
    if not np.isfinite(m):
        return None
    return m, close


def trend_on(h: History | None, data_date: date, n: int) -> bool:
    """``h``'s close on ``data_date`` > SMA(n) of its daily closes (strict); False without the bars."""
    found = _close_on(h, data_date)
    if found is None:
        return False
    i, close = found
    if i + 1 < n:
        return False
    assert h is not None
    window = h.close[i + 1 - n : i + 1].reshape(1, n)
    sma = float(sma_window(window, n)[0])
    return bool(np.isfinite(sma) and close > sma)


def rotation_targets(history: Mapping[str, History], data_date: date, params: RotationParams) -> tuple[Target, ...]:
    """The rotation's targets for the session after ``data_date``, in rank order (fallback last)."""
    as_day(data_date)
    weight = equal_weight(params.top)
    chosen: list[Target] = []
    gate = params.trend is None or trend_on(history.get(params.trend[0]), data_date, params.trend[1])
    if gate:
        ranked: list[tuple[float, str, float]] = []
        for symbol in params.universe:
            found = momentum_at(history.get(symbol), data_date, params.lookback)
            if found is not None:
                ranked.append((found[0], symbol, found[1]))
        ranked.sort(key=lambda r: (-r[0], r[1]))
        for m, symbol, close in ranked[: params.top]:
            if params.absolute and not m > 0.0:
                continue
            target = target_from_close(symbol, close, weight)
            if target is not None:
                chosen.append(target)
    unused = params.top - len(chosen)
    if unused > 0 and params.fallback is not None:
        found_fb = _close_on(history.get(params.fallback), data_date)
        if found_fb is not None:
            target = target_from_close(params.fallback, found_fb[1], weight * unused)
            if target is not None:
                chosen.append(target)
    return tuple(chosen)


@dataclass(frozen=True, slots=True, eq=False)
class RotationPrepared:
    """``prepare``'s output: the histories as given (read-only view). The rotation's features
    depend on ``lookback``, a parameter, so nothing is precomputed; ``targets_prepared`` slices
    at ``data_date`` exactly as ``targets`` does."""

    history: Mapping[str, History]


class RotationAllocator:
    """F2/F3 behind the ``Allocator`` protocol (strategies/allocator.py)."""

    id = "ROT"

    def lookback(self, params: Any) -> int:
        p = _params(params)
        return max(p.lookback + 1, p.trend[1] if p.trend is not None else 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _params(params)
        read = set(p.universe)
        if p.fallback is not None:
            read.add(p.fallback)
        if p.trend is not None:
            read.add(p.trend[0])
        return tuple(sorted(read))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _params(params)
        held = set(p.universe)
        if p.fallback is not None:
            held.add(p.fallback)
        return tuple(sorted(held))

    def uses_members(self, params: Any) -> bool:
        _params(params)
        return False

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return rotation_targets(history, data_date, _params(params))

    def prepare(self, history: Mapping[str, History]) -> RotationPrepared:
        return RotationPrepared(MappingProxyType(dict(history)))

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, RotationPrepared):
            raise TypeError(f"prepared must be RotationPrepared, got {type(prepared).__name__}")
        return rotation_targets(prepared.history, data_date, _params(params))


ROTATION = RotationAllocator()
