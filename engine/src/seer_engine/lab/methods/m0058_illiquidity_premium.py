"""M0058 — The illiquidity premium among large companies: hold the index names that trade thinnest for their size.

Source: Amihud (2002), "Illiquidity and stock returns: cross-section and time-series effects",
Journal of Financial Markets 5(1), 31-56, doi:10.1016/S1386-4181(01)00024-6.
Idea: Amihud's illiquidity is the average of |daily return| / daily dollar volume: how far the
price moves per dollar traded. Stocks that move more per dollar earn a premium for being harder to
trade. Inside the S&P 500 / Nasdaq-100 every name is trivially easy for a 20M IDR account to trade,
so the owner would collect a premium paid for a cost the account never bears.

The frame is F4's -- point-in-time members, the SPY-200 trend gate, monthly, equal weights,
fractional shares at Gotrade's real fees on ``monthly-hold-frac-gotrade`` -- with two changes:

    * the 20M-dollar-a-day volume floor is removed (``min_dollar_volume=0``): that floor cuts
      exactly the thin tail this method is about, and every index member is liquid enough for a
      $1,250 account; the $5 price floor stays;
    * the ranking key is Amihud illiquidity over the ``n`` bars ending at d (the symbol's own bars):

          illiq(s) = mean over t of |close_t / close_{t-1} - 1| / (close_t * volume_t)

      using only back-to-back bar pairs with finite positive prices and positive volume, and only
      when at least ``MIN_FRAC`` of the window is usable. Ranking is cross-sectional each month,
      so the fall in market-wide dollar volume over the decades never enters.

``side="illiquid"`` holds the ``top`` highest illiq names; ``side="liquid"`` holds the ``top``
lowest (the control, which the paper says should trail).

Assumption, written before the run: bars are split-adjusted in both price and volume (checked on
AAPL across its 2014 split: the dollar volume is continuous), so close x volume is a true dollar
volume up to the dividend adjustment, which is small and slow. Reads only bars dated <= d.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 9)
MIN_FRAC = 0.8  # a window needs this share of usable bar pairs before a name is scored

Side = Literal["illiquid", "liquid"]
_SIDES: tuple[str, ...] = ("illiquid", "liquid")


@dataclass(frozen=True, slots=True)
class IlliqParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; the rest is the ranking."""

    inner: FactorParams
    side: Side = "illiquid"
    n: int = 252  # bar pairs in the Amihud window

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if isinstance(self.n, bool) or not isinstance(self.n, int):
            raise TypeError(f"n must be an int, got {type(self.n).__name__}")
        if self.n < 20:
            raise ValueError(f"n must be >= 20, got {self.n}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "n": str(self.n)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> IlliqParams:
    if not isinstance(params, IlliqParams):
        raise TypeError(f"params must be IlliqParams, got {type(params).__name__}")
    return params


def illiq_lookback(params: IlliqParams) -> int:
    return max(factor_lookback(params.inner), params.n + 1)


def amihud(h: History, data_date: date, n: int) -> float | None:
    """Mean |return| per dollar traded over the ``n`` bar pairs ending at ``data_date``, or None."""
    i = h.index_of(data_date)
    if i is None or i < n:
        return None
    c = h.close[i - n : i + 1]
    v = h.volume[i - n + 1 : i + 1]
    prev, cur = c[:-1], c[1:]
    ok = np.isfinite(prev) & np.isfinite(cur) & np.isfinite(v) & (prev > 0.0) & (cur > 0.0) & (v > 0.0)
    if int(ok.sum()) < max(3, math.ceil(MIN_FRAC * n)):
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.abs(cur[ok] / prev[ok] - 1.0) / (cur[ok] * v[ok])
    x = float(np.mean(ratio))
    return x if math.isfinite(x) else None


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           params: IlliqParams) -> list[FactorRow]:
    scored: list[tuple[float, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED:
            continue
        h = history.get(r.symbol)
        if h is None:
            continue
        x = amihud(h, data_date, params.n)
        if x is None:
            continue
        key = -x if params.side == "illiquid" else x
        scored.append((key, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored[: params.inner.top]]


def targets_from_rows(chosen: list[FactorRow], params: IlliqParams) -> tuple[Target, ...]:
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass
class IlliqPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class IlliquidityAllocator:
    """F4's book without the volume floor, ranked on Amihud illiquidity.

    Held symbols get no special treatment: a name that leaves the top set is signal-exited.
    """

    id = "M0058"

    def lookback(self, params: Any) -> int:
        return illiq_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from_rows(choose(rows, history, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> IlliqPrepared:
        return IlliqPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IlliqPrepared):
            raise TypeError(f"prepared must be IlliqPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.history, data_date, p), p)


ILLIQ = IlliquidityAllocator()

OPEN20 = replace(N20, min_dollar_volume=0.0)  # F4's screen without the volume floor
OPEN30 = replace(OPEN20, top=30)
OPEN20_NOTREND = replace(OPEN20, trend=None)
OPEN30_NOTREND = replace(OPEN30, trend=None)


def _v(suffix: str, params: IlliqParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0058-{suffix}", family="M0058", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ILLIQ, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0058",
    name="The illiquidity premium among large companies: hold the S&P names that trade thinnest for their size",
    family="stock-illiquidity-premium",
    source_kind="paper",
    source_ref=(
        "Amihud (2002), Illiquidity and stock returns: cross-section and time-series effects, "
        "Journal of Financial Markets 5(1), 31-56, doi:10.1016/S1386-4181(01)00024-6"
    ),
    parent_id=None,
    hypothesis=(
        "Amihud shows that stocks whose prices move most per dollar traded (the average of absolute "
        "daily return divided by dollar volume) earn a premium for being harder to trade. Inside the "
        "point-in-time S&P 500 / Nasdaq-100 every name is easy for a 20M IDR account to trade, so "
        "the owner collects a premium for a cost it never pays. Each month, among members priced at "
        "$5 or more (F4's screen with its 20M-dollar volume floor removed, because that floor cuts "
        "exactly the thin tail), rank on Amihud illiquidity over the past 252 bars and hold the most "
        "illiquid names equal weight, in fractional shares at Gotrade's real fees on "
        "monthly-hold-frac-gotrade. Ranking is cross-sectional each month, so the decades-long rise "
        "in market-wide volume does not matter. Variants: ILL20-T and ILL30-T (20 / 30 most "
        "illiquid behind the SPY 200-day gate), ILL20 and ILL30 (no gate), and LIQ20-T (the 20 most "
        "liquid behind the gate: the control, which should trail). Success: an ILL variant beats "
        "SPY TR on dev within the drawdown limit, the control does worse, and the edge survives the "
        "walk-forward folds and the 2009-2015 high-coverage era."
    ),
    expected_failure=(
        "Among large caps, illiquidity is mostly smallness: the most illiquid S&P names are the "
        "smallest members, so this is a small-cap tilt, and the store's survivorship gap flatters "
        "small caps most (the small members that died are the ones missing). The edge may sit in "
        "2000-2006, the great small-and-value run, and vanish by 2009-2015. Small, thin members "
        "fell hard in 2008 and in the 2002 bottom, so without the trend gate the worst fall should "
        "break 20%, and even with it 1998 and 2008 may push it over. Thin names also cost more in "
        "real spreads than Gotrade's fee schedule charges, which the backtest does not see."
    ),
    candidates=(
        _v("ILL20-T", IlliqParams(OPEN20, side="illiquid"),
           "The 20 most illiquid members (Amihud, 252 bars), behind the SPY 200-day gate"),
        _v("ILL30-T", IlliqParams(OPEN30, side="illiquid"),
           "The 30 most illiquid members, behind the gate: more names, less single-stock risk"),
        _v("ILL20", IlliqParams(OPEN20_NOTREND, side="illiquid"),
           "The 20 most illiquid members, always invested"),
        _v("ILL30", IlliqParams(OPEN30_NOTREND, side="illiquid"),
           "The 30 most illiquid members, always invested"),
        _v("LIQ20-T", IlliqParams(OPEN20, side="liquid"),
           "The 20 most liquid members, behind the gate: the control, expected to trail"),
    ),
    seen_keys=(
        "concept:amihud-illiquidity",
        "concept:illiquidity-premium",
        "doi:10.1016/S1386-4181(01)00024-6",
    ),
)
