"""M0013 — Momentum braked by the basket's own drawdown, not its volatility (M0002 variation).

Source: variation of M0002, driven by its result: every variant beat SPY (+10.6 to +13.6% a year
vs +7.9%) but the worst fall stayed at 17.5-21.8%, because the falls (Mar-Aug 2006, Aug 1998,
Apr-Jun 2010, Apr-Sep 2011) happen with SPY above its 200-day average and the book's own 3-month
volatility near its median: realized volatility is coincident with the loss, not ahead of it.

Idea: brake on the loss itself. On data date d the allocator takes FACTOR's targets and measures
one basket: the symbols the book holds tonight (``held``), equal-weighted, or FACTOR's fresh
targets when nothing is held (the first rank, or after a full stop-out). From that basket's
daily returns over the last ``peak_n`` sessions through d it builds a wealth curve and reads its
distance below its own peak, ``dd`` (<= 0). Then

  scale = 1                                  when dd > -d
  scale = 1 - (1 - floor) x (-dd - d) / d    between -d and -2d (linear)
  scale = floor                              at or below -2d

and every inner weight is multiplied by ``scale``. Freed weight is cash; never leverage.
``basket="targets"`` measures FACTOR's fresh picks instead of the held book: by construction
those are near their highs, so that variant is a control for the selection effect.

The rank clock stays monthly (F4's basket); most variants re-check the brake weekly or daily
through the rank/resize cadence split, which holds the monthly basket and re-scales it only.
A floor of 0 empties the book; with nothing held, the brake re-measures the fresh picks, which
in practice means "out until the next monthly re-rank".
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD, MONTHLY_RANK_WEEKLY_RESIZE
from seer_engine.strategies.allocator import LazyPrepared, scale_weight
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import FACTOR, FactorParams

ADDED = date(2026, 10, 6)

Basket = Literal["held", "targets"]
_BASKETS: tuple[str, ...] = ("held", "targets")

MONTHLY_RANK_DAILY_RESIZE = replace(MONTHLY_HOLD, id="monthly-rank-daily-resize", resize_cadence="daily")


@dataclass(frozen=True, slots=True)
class BrakeParams:
    """FACTOR params plus the drawdown brake."""

    inner_params: FactorParams
    d: Decimal = Decimal("0.08")  # brake starts at a d fall from the peak, bottoms out at 2d
    floor: Decimal = Decimal("0.25")  # exposure left at or below a 2d fall
    peak_n: int = 126  # sessions the peak is taken over (about six months)
    basket: Basket = "held"

    def __post_init__(self) -> None:
        if self.basket not in _BASKETS:
            raise ValueError(f"basket must be one of {_BASKETS}, got {self.basket!r}")
        if isinstance(self.peak_n, bool) or not isinstance(self.peak_n, int) or self.peak_n < 2:
            raise ValueError(f"peak_n must be an int >= 2, got {self.peak_n!r}")
        if not isinstance(self.d, Decimal) or not (0 < self.d < Decimal("0.5")):
            raise ValueError(f"d must be a Decimal in (0, 0.5), got {self.d!r}")
        if not isinstance(self.floor, Decimal) or not (0 <= self.floor < 1):
            raise ValueError(f"floor must be a Decimal in [0, 1), got {self.floor!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"d": str(self.d), "floor": str(self.floor), "peak_n": str(self.peak_n),
               "basket": self.basket}
        for k, v in self.inner_params.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _window(h: History | None, data_date: date, n: int) -> np.ndarray | None:
    """``h``'s last ``n`` + 1 closes through ``data_date``, or None when it has fewer or bad ones."""
    if h is None:
        return None
    end = int(np.searchsorted(h.dates, as_day(data_date), side="right"))
    if end < n + 1:
        return None
    w = h.close[end - n - 1 : end]
    if not np.all(np.isfinite(w)) or np.any(w <= 0.0):
        return None
    return w


def basket_drawdown(history: Mapping[str, History], symbols: tuple[str, ...], data_date: date,
                    n: int) -> float | None:
    """The equal-weight basket's distance below its ``n``-session peak through d (<= 0), or None."""
    rets: list[np.ndarray] = []
    for s in sorted(set(symbols)):
        w = _window(history.get(s), data_date, n)
        if w is not None:
            rets.append(w[1:] / w[:-1] - 1.0)
    if not rets:
        return None
    basket = np.mean(np.vstack(rets), axis=0)
    wealth = np.concatenate((np.ones(1), np.cumprod(1.0 + basket)))
    if not np.all(np.isfinite(wealth)):
        return None
    dd = float(wealth[-1] / np.max(wealth) - 1.0)
    return dd if math.isfinite(dd) else None


def brake_scale(dd: float | None, params: BrakeParams) -> Decimal | None:
    """The weight multiplier below 1, or None when the book stays fully invested."""
    if dd is None:
        return None
    d = float(params.d)
    fall = -dd
    if fall <= d:
        return None
    floor = float(params.floor)
    scale = floor if fall >= 2.0 * d else 1.0 - (1.0 - floor) * (fall - d) / d
    return Decimal(repr(max(scale, 0.0)))


def _scaled(targets: tuple[Target, ...], scale: Decimal | None) -> tuple[Target, ...]:
    if scale is None:
        return targets
    out: list[Target] = []
    for t in targets:
        w = scale_weight(t.weight, scale)
        if w is not None:
            out.append(replace(t, weight=w))
    return tuple(out)


def _braked(history: Mapping[str, History], inner: tuple[Target, ...], data_date: date,
            held: frozenset[str], params: BrakeParams) -> tuple[Target, ...]:
    if params.basket == "held" and held:
        symbols = tuple(sorted(held))
    else:
        symbols = tuple(t.symbol for t in inner)
    dd = basket_drawdown(history, symbols, data_date, params.peak_n)
    return _scaled(inner, brake_scale(dd, params))


class DrawdownBrakeAllocator:
    """FACTOR's targets, scaled down while the measured basket is well below its six-month peak."""

    id = "M0013"

    def lookback(self, params: BrakeParams) -> int:
        return max(FACTOR.lookback(params.inner_params), params.peak_n + 1)

    def symbols(self, params: BrakeParams) -> tuple[str, ...]:
        return tuple(FACTOR.symbols(params.inner_params))

    def holds(self, params: BrakeParams) -> tuple[str, ...]:
        return tuple(FACTOR.holds(params.inner_params))

    def uses_members(self, params: BrakeParams) -> bool:
        return bool(FACTOR.uses_members(params.inner_params))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: BrakeParams) -> tuple[Target, ...]:
        inner = FACTOR.targets(history, members, data_date, held, params.inner_params)
        return _braked(history, inner, data_date, held, params)

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: BrakeParams) -> tuple[Target, ...]:
        inner = FACTOR.targets_prepared(prepared.of(FACTOR), members, data_date, held,
                                        params.inner_params)
        return _braked(prepared.history, inner, data_date, held, params)


BRAKE = DrawdownBrakeAllocator()
MOM20_TREND = FactorParams(rank="momentum", top=20)  # F4-MOM12-N20-TREND's inner params


def _v(suffix: str, params: BrakeParams, rules, rationale: str) -> Candidate:
    return Candidate(id=f"M0013-{suffix}", family="M0013", rules=rules, allocator=BRAKE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0013",
    name="Momentum braked by the basket's own drawdown, not its volatility",
    family="stock-momentum-risk-managed",
    source_kind="variation",
    source_ref="M0002",
    parent_id="M0002",
    hypothesis=(
        "M0002's worst falls (Mar-Aug 2006, Aug 1998, Apr-Jun 2010, Apr-Sep 2011) happened with SPY "
        "above its 200-day average and the book's 3-month vol near its median, so the vol gate was "
        "shut while the loss was made. A brake on the held basket's own distance below its 126-day "
        "peak (full size above -d, linear down to a floor by -2d), checked weekly on the monthly "
        "basket, fires within a week of a reversal. It should cut max DD below M0002-REL-85's 18.4%, "
        "toward 15%, at a smaller CAGR cost than vol scaling because it de-risks only during the "
        "fall itself; HELD-D8-MW should land at max DD <= 15% with CAGR above SPY TR's +7.9%."
    ),
    expected_failure=(
        "Whipsaw. Momentum unwinds are sharp V-shapes (2009, 2001): the brake sells near the bottom "
        "and the book misses the rebound until the basket makes a new high, so CAGR drops 2-4 points "
        "while max DD only falls to 16-17%, because the first -d of every fall is taken at full "
        "size and the 2006 unwind was a series of -8% steps. The 'targets' control should do "
        "nothing (fresh momentum picks sit near their highs), and the monthly-only variant should "
        "react too late to matter."
    ),
    candidates=(
        _v("HELD-D8-MW", BrakeParams(MOM20_TREND, Decimal("0.08"), Decimal("0.25")),
           MONTHLY_RANK_WEEKLY_RESIZE, "Main bet: held basket, brake from -8% to a 25% floor at -16%, weekly check"),
        _v("HELD-D6-MW", BrakeParams(MOM20_TREND, Decimal("0.06"), Decimal("0.25")),
           MONTHLY_RANK_WEEKLY_RESIZE, "Earlier brake: from -6% down to 25% at -12%"),
        _v("HELD-D8-F0-MW", BrakeParams(MOM20_TREND, Decimal("0.08"), Decimal("0")),
           MONTHLY_RANK_WEEKLY_RESIZE, "Full stop at -16%: out until the next monthly re-rank"),
        _v("HELD-D8-MD", BrakeParams(MOM20_TREND, Decimal("0.08"), Decimal("0.25")),
           MONTHLY_RANK_DAILY_RESIZE, "Same brake checked daily: the fastest reaction the split allows"),
        _v("HELD-D8-M", BrakeParams(MOM20_TREND, Decimal("0.08"), Decimal("0.25")),
           MONTHLY_HOLD, "Monthly check only: the one shape paper trading can run today"),
        _v("TGT-D8-MW", BrakeParams(MOM20_TREND, Decimal("0.08"), Decimal("0.25"), basket="targets"),
           MONTHLY_RANK_WEEKLY_RESIZE, "Control: measure the fresh picks, not the held book"),
    ),
    seen_keys=(
        "concept:momentum-basket-own-drawdown-brake",
        "concept:drawdown-gate-vs-vol-gate",
    ),
)
