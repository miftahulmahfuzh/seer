"""M0001 — Momentum scaled by its own realized volatility (risk-managed momentum).

Source: Barroso & Santa-Clara (2015), "Momentum has its moments", Journal of Financial
Economics 116(1); also Daniel & Moskowitz (2016), "Momentum crashes".
Idea: momentum's risk is predictable from its own recent volatility, and its crashes come in
high-volatility spells. Scaling the momentum book by target_vol / (its own realized vol) keeps
most of the return and cuts the crash drawdowns. P7a's best near miss, F4-MOM12-N20-TREND
(CAGR +16.2%, PF 2.27, max DD 22.2%), failed only on max DD; P7a scaled by *SPY's* volatility
(F1-*-VT, F6-ML-P50-N10-VT12), never by the book's own.

The allocator wraps FACTOR. On data date d it takes the inner targets, forms the basket of
their symbols at the inner weights (renormalized to 1), measures the basket's annualized
volatility from the last ``n`` daily returns of each symbol through d (a symbol with fewer
than n + 1 bars through d is left out of the estimate), and multiplies every weight by
min(1, target_vol / vol). Freed weight is cash. No leverage.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD, WEEKLY_HOLD
from seer_engine.strategies.allocator import LazyPrepared, scale_weight
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import FACTOR, FactorParams

ADDED = date(2026, 10, 4)
TRADING_DAYS = 252


@dataclass(frozen=True, slots=True)
class OwnVolParams:
    inner_params: FactorParams
    target_vol: Decimal = Decimal("0.12")
    n: int = 63

    def as_dict(self) -> dict[str, str]:
        out = {"target_vol": str(self.target_vol), "n": str(self.n)}
        for k, v in self.inner_params.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _returns(h: History, data_date: date, n: int) -> np.ndarray | None:
    end = int(np.searchsorted(h.dates, as_day(data_date), side="right"))
    if end < n + 1:
        return None
    c = h.close[end - n - 1 : end]
    if not np.all(np.isfinite(c)) or np.any(c <= 0):
        return None
    return c[1:] / c[:-1] - 1.0


def basket_scale(history: Mapping[str, History], targets: tuple[Target, ...], data_date: date,
                 n: int, target_vol: Decimal) -> Decimal | None:
    """min(1, target_vol / annualized vol of the weight-normalized basket), or None (no scaling)."""
    parts: list[tuple[float, np.ndarray]] = []
    for t in sorted(targets, key=lambda t: t.symbol):
        h = history.get(t.symbol)
        r = None if h is None else _returns(h, data_date, n)
        if r is not None:
            parts.append((float(t.weight), r))
    total = 0.0
    for w, _ in parts:
        total += w
    if not parts or total <= 0.0:
        return None
    basket = np.zeros(n, dtype=np.float64)
    for w, r in parts:
        basket = basket + (w / total) * r
    mean = 0.0
    for x in basket:
        mean += float(x)
    mean /= n
    var = 0.0
    for x in basket:
        var += (float(x) - mean) ** 2
    sd = math.sqrt(var / n) * math.sqrt(TRADING_DAYS)
    if not math.isfinite(sd) or sd <= 0.0:
        return None
    scale = float(target_vol) / sd
    if not math.isfinite(scale) or scale >= 1.0:
        return None
    return Decimal(repr(scale))


def _scaled(targets: tuple[Target, ...], scale: Decimal | None) -> tuple[Target, ...]:
    if scale is None:
        return targets
    out: list[Target] = []
    for t in targets:
        w = scale_weight(t.weight, scale)
        if w is not None:
            out.append(replace(t, weight=w))
    return tuple(out)


class OwnVolAllocator:
    """FACTOR's targets scaled by target_vol / the target basket's own realized volatility."""

    id = "M0001"

    def lookback(self, params: OwnVolParams) -> int:
        return max(FACTOR.lookback(params.inner_params), params.n + 1)

    def symbols(self, params: OwnVolParams) -> tuple[str, ...]:
        return tuple(FACTOR.symbols(params.inner_params))

    def holds(self, params: OwnVolParams) -> tuple[str, ...]:
        return tuple(FACTOR.holds(params.inner_params))

    def uses_members(self, params: OwnVolParams) -> bool:
        return bool(FACTOR.uses_members(params.inner_params))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: OwnVolParams) -> tuple[Target, ...]:
        inner = FACTOR.targets(history, members, data_date, held, params.inner_params)
        return _scaled(inner, basket_scale(history, inner, data_date, params.n, params.target_vol))

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: OwnVolParams) -> tuple[Target, ...]:
        inner = FACTOR.targets_prepared(prepared.of(FACTOR), members, data_date, held, params.inner_params)
        return _scaled(inner, basket_scale(prepared.history, inner, data_date, params.n, params.target_vol))


OWNVOL = OwnVolAllocator()
MOM20_TREND = FactorParams(rank="momentum", top=20)  # F4-MOM12-N20-TREND's inner params


def _v(suffix: str, params: OwnVolParams, rationale: str, rules=MONTHLY_HOLD) -> Candidate:
    return Candidate(id=f"M0001-{suffix}", family="M0001", rules=rules, allocator=OWNVOL,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0001",
    name="Momentum scaled by its own realized volatility",
    family="stock-momentum-risk-managed",
    source_kind="paper",
    source_ref="Barroso & Santa-Clara (2015), Momentum has its moments, JFE 116(1); Daniel & Moskowitz (2016), Momentum crashes, JFE 122(2)",
    hypothesis=(
        "F4-MOM12-N20-TREND beat SPY TR (CAGR +16.2% vs +7.9%, PF 2.27) and failed only on max DD "
        "(22.2%). Scaling its book by target_vol over its own 3-month realized volatility cuts "
        "exposure in exactly the high-vol spells where momentum crashes, so max DD falls under 15% "
        "while CAGR stays above SPY's."
    ),
    expected_failure=(
        "Monthly rebalancing reacts too slowly: a fast crash (Oct 2008, Aug 2011) does its damage "
        "inside one month before the scale updates, leaving max DD at 16-20%; or the 10% target "
        "cuts CAGR below SPY TR."
    ),
    candidates=(
        _v("TV10", OwnVolParams(MOM20_TREND, Decimal("0.10"), 63),
           "Top-20 12-1 momentum, SPY trend filter, scaled to 10% own vol"),
        _v("TV12", OwnVolParams(MOM20_TREND, Decimal("0.12"), 63),
           "Same at 12% own vol: more return, more drawdown"),
        _v("TV10-W", OwnVolParams(MOM20_TREND, Decimal("0.10"), 63),
           "10% own vol, weekly re-rank and re-scale: faster reaction to a crash", rules=WEEKLY_HOLD),
        _v("TV10-NOTREND", OwnVolParams(FactorParams(rank="momentum", top=20, trend=None), Decimal("0.10"), 126),
           "No SPY trend filter: own-vol scaling alone as the crash guard (Barroso's setup)"),
    ),
    seen_keys=(
        "concept:momentum-own-vol-scaling",
        "url:https://doi.org/10.1016/j.jfineco.2014.11.010",
    ),
)
