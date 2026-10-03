"""Strategy A2: Strategy A v1 plus pre-registered variants V0–V3 (P3b rework, handover §3).

Every variant uses Strategy A's features, setup and bracket unchanged (``strategies/a.py``,
which this module never edits). A variant only adds rules on top:

    V0 ``control``            Strategy A v1 exactly: rank by (RSI(2), symbol).
    V1 ``regime``             V0, plus no new picks on a ``data_date`` where SPY's close <= SPY's
                              SMA(200). Regime on <=> close > SMA(200), STRICT; equality is off.
    V2 ``regime_calm``        V1, but rank by (ATR(14) / close, RSI(2), symbol) ascending.
    V3 ``regime_calm_floor``  V2, plus a candidate needs close >= ``FLOOR_PRICE`` (10.0, inclusive).

The regime reads ``REGIME_SYMBOL``'s bars from the SAME history mapping the picks come from
(SPY is in ``Market.history`` but never a universe member). SPY's SMA(200) is ``sma_window``
over its last ``LOOKBACK`` closes ending at ``data_date``, so the backtest (``prepare_a2``,
rolling) and the nightly job (``regime_on``, one window) compute bit-identical floats. SPY
missing, without a bar on ``data_date`` or with fewer than ``LOOKBACK`` bars through it means the
regime is OFF. SPY itself is never a pick, even when a caller lists it in ``members``.

The variant is a field of ``A2Params`` so one selection can run over every (variant, grid)
combination and a params schedule can switch variant by date. Pure: no database, network,
clock or randomness (tests/test_strategy_purity.py).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.sim import Pick
from seer_engine.strategies.a import (
    LOOKBACK,
    SMA_N,
    AParams,
    APrepared,
    Features,
    _bracket,
    _setup,
    features_at,
    prepare_a,
)
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import rolling, sma_window

REGIME_SYMBOL = "SPY"  # == seer_engine.universe.BENCHMARK (tested; universe imports psycopg, so not imported here)
FLOOR_PRICE = 10.0  # V3: close >= FLOOR_PRICE (inclusive). Fixed by the handover, never tuned.
VARIANTS: tuple[str, ...] = ("control", "regime", "regime_calm", "regime_calm_floor")  # V0..V3

_REGIME_VARIANTS = frozenset(VARIANTS[1:])  # V1..V3: no new picks while the regime is off
_CALM_VARIANTS = frozenset(VARIANTS[2:])  # V2..V3: rank by ATR(14) / close first
_FLOOR_VARIANTS = frozenset(VARIANTS[3:])  # V3: close >= FLOOR_PRICE


@dataclass(frozen=True, slots=True)
class A2Params:
    """A variant name plus Strategy A's five tunable parameters (defaults: V0 with design §4 values)."""

    variant: str = "control"  # one of VARIANTS
    rsi_max: float = 10.0  # the five below mean exactly what they mean in AParams
    limit_atr: Decimal = Decimal("0.5")
    tp_atr: Decimal = Decimal("1.0")
    sl_atr: Decimal = Decimal("1.5")
    min_dollar_volume: float = 20_000_000.0

    def __post_init__(self) -> None:
        if not isinstance(self.variant, str):
            raise TypeError(f"variant must be a str, got {type(self.variant).__name__}")
        if self.variant not in VARIANTS:
            raise ValueError(f"variant must be one of {', '.join(VARIANTS)}, got {self.variant!r}")
        a = self.a_params()  # validates the five A fields exactly as AParams does
        object.__setattr__(self, "rsi_max", a.rsi_max)
        object.__setattr__(self, "min_dollar_volume", a.min_dollar_volume)

    def a_params(self) -> AParams:
        """Strategy A's params with the same five values."""
        return AParams(
            rsi_max=self.rsi_max,
            limit_atr=self.limit_atr,
            tp_atr=self.tp_atr,
            sl_atr=self.sl_atr,
            min_dollar_volume=self.min_dollar_volume,
        )

    def as_dict(self) -> dict[str, str]:
        """``variant`` first, then ``AParams.as_dict()``'s five plain decimal strings in its order."""
        return {"variant": self.variant, **self.a_params().as_dict()}

    @classmethod
    def from_a(cls, variant: str, p: AParams) -> A2Params:
        """``variant`` with ``p``'s five values."""
        if not isinstance(p, AParams):
            raise TypeError(f"p must be AParams, got {type(p).__name__}")
        return cls(
            variant=variant,
            rsi_max=p.rsi_max,
            limit_atr=p.limit_atr,
            tp_atr=p.tp_atr,
            sl_atr=p.sl_atr,
            min_dollar_volume=p.min_dollar_volume,
        )


A2_DESIGN_PARAMS = A2Params()  # V0 with the design values: the walk-forward's none-qualifies fallback
# Set by phase 6 ONLY if the P3b gate passes, to the last fold's selection, with a comment naming
# the report (tests/test_strategy_a2_frozen.py ties the two). None means A2 is not frozen.
STRATEGY_A2_PARAMS: A2Params | None = None


def _check_params(params: object) -> A2Params:
    if not isinstance(params, A2Params):
        raise TypeError(f"params must be A2Params, got {type(params).__name__}")
    return params


def regime_on(spy: History | None, data_date: date) -> bool:
    """True iff SPY's close on ``data_date`` is STRICTLY above its SMA(200).

    SMA(200) = ``sma_window`` over SPY's last ``LOOKBACK`` closes ending at ``data_date``; later
    bars are never read. ``spy`` None, no SPY bar dated ``data_date``, or fewer than ``LOOKBACK``
    bars through it -> False (the regime is off, so V1..V3 make no new picks).
    """
    as_day(data_date)
    if spy is None:
        return False
    i = spy.index_of(data_date)
    if i is None or i + 1 < LOOKBACK:
        return False
    window = spy.close[i + 1 - LOOKBACK : i + 1].reshape(1, LOOKBACK)
    sma = sma_window(window, SMA_N)
    return bool(spy.close[i] > sma[0])


def picks_from_features_a2(
    features: Iterable[Features],
    members: Set[str],
    params: A2Params,
    regime: bool,
) -> list[Pick]:
    """Ranked A2 picks from Strategy A features under ``params.variant``'s rules.

    V1..V3 with ``regime`` False -> []. Candidates: member, not ``REGIME_SYMBOL``, Strategy A's
    setup and a valid bracket; V3 also needs ``close >= FLOOR_PRICE``. Ranked ascending by
    (RSI, symbol) for V0/V1 and by (ATR / close, RSI, symbol) for V2/V3. Uncapped.
    """
    params = _check_params(params)
    if params.variant in _REGIME_VARIANTS and not regime:
        return []
    a = params.a_params()
    calm = params.variant in _CALM_VARIANTS
    floor = params.variant in _FLOOR_VARIANTS
    ranked: list[tuple[tuple[Any, ...], Pick]] = []
    for f in features:
        if f.symbol not in members or f.symbol == REGIME_SYMBOL or not _setup(f, a):
            continue
        if floor and not f.close >= FLOOR_PRICE:
            continue
        pick = _bracket(f, a)
        if pick is None:
            continue
        # _bracket rejects last <= 0 after rounding, so f.close > 0 here.
        key = (f.atr / f.close, f.rsi, f.symbol) if calm else (f.rsi, f.symbol)
        ranked.append((key, pick))
    ranked.sort(key=lambda r: r[0])
    return [pick for _, pick in ranked]


@dataclass(frozen=True, slots=True, eq=False)
class A2Prepared:
    """Strategy A's prepared features plus SPY's regime on every date it is defined.

    ``a`` is ``prepare_a(history)`` unchanged (it includes SPY's rows, which the rules drop).
    ``regime_dates``: every SPY bar date with at least ``LOOKBACK`` bars through it, ascending.
    ``regime``: SPY close > rolling SMA(200) on that date, bit-identical to ``regime_on``.
    """

    a: APrepared
    regime_dates: np.ndarray  # datetime64[D], ascending
    regime: np.ndarray  # bool, same length

    def regime_on(self, data_date: date) -> bool:
        """``regime_on(SPY.upto(data_date), data_date)``: False when ``data_date`` has no regime row."""
        day = as_day(data_date)
        i = int(np.searchsorted(self.regime_dates, day, side="left"))
        if i == self.regime_dates.shape[0] or self.regime_dates[i] != day:
            return False
        return bool(self.regime[i])


def prepare_a2(history: Mapping[str, History]) -> A2Prepared:
    """``prepare_a(history)`` plus SPY's rolling regime column (see ``A2Prepared``)."""
    a = prepare_a(history)
    spy = history.get(REGIME_SYMBOL)
    if spy is None or len(spy) < LOOKBACK:
        dates = np.empty(0, dtype="datetime64[D]")
        regime = np.empty(0, dtype=np.bool_)
    else:
        start = LOOKBACK - 1
        sma = rolling(sma_window, spy.close, window=LOOKBACK, n=SMA_N)[start:]
        dates = spy.dates[start:].copy()
        regime = spy.close[start:] > sma
    dates.setflags(write=False)
    regime.setflags(write=False)
    return A2Prepared(a, dates, regime)


def picks_prepared_a2(prepared: A2Prepared, members: Set[str], data_date: date, params: A2Params) -> list[Pick]:
    """``picks_from_features_a2`` on ``prepared``'s rows for ``data_date``, with a vectorized pre-filter.

    The pre-filter is Strategy A's (the same strict comparisons as ``a._setup``); every survivor
    is re-checked by ``picks_from_features_a2``, so the result is exactly
    ``picks_from_features_a2(prepared.a.features_on(d), members, params, prepared.regime_on(d))``.
    """
    if not isinstance(prepared, A2Prepared):
        raise TypeError(f"prepared must be A2Prepared, got {type(prepared).__name__}")
    params = _check_params(params)
    regime = prepared.regime_on(data_date)
    if params.variant in _REGIME_VARIANTS and not regime:
        return []
    p = prepared.a
    lo, hi = p._rows(data_date)
    if lo == hi:
        return []
    window = slice(lo, hi)
    mask = (
        (p.close[window] > p.sma[window])
        & (p.rsi[window] < params.rsi_max)
        & (p.dollar_volume[window] > params.min_dollar_volume)
    )
    candidates = []
    for j in np.flatnonzero(mask):
        k = lo + int(j)
        symbol = p.symbols[int(p.sym[k])]
        if symbol in members and symbol != REGIME_SYMBOL:
            candidates.append(p._features(k, data_date))
    return picks_from_features_a2(candidates, members, params, regime)


class StrategyA2:
    """Strategy A2 behind the ``Strategy`` protocol."""

    id = "A2"
    lookback = LOOKBACK

    def picks(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        params = _check_params(params)
        regime = regime_on(history.get(REGIME_SYMBOL), data_date)
        if params.variant in _REGIME_VARIANTS and not regime:
            return []
        member_history = {s: h for s, h in history.items() if s in members}
        return picks_from_features_a2(features_at(member_history, data_date), members, params, regime)

    def prepare(self, history: Mapping[str, History]) -> A2Prepared:
        return prepare_a2(history)

    def picks_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        return picks_prepared_a2(prepared, members, data_date, params)


STRATEGY_A2 = StrategyA2()
