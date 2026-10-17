"""M0093 — A true lottery spike, not just a jumpy stock: rank big members on their biggest recent days measured against their own normal swing.

Parent: M0091, which ranked F4-screened index members on raw MAX5 (the mean of the five largest
daily returns over 21 sessions). Its lowest-MAX book filled with calm utilities, staples and drug
makers, tied SPY TR on the owner's deposits and fell 30%; its highest-MAX control did better. Among
big liquid companies raw MAX turned out to be a volatility ranking, and volatility earned more over
1996-2015.

Bali, Cakici & Whitelaw (2011, JFE 99(2), working paper 2009) argue the overpricing comes from the
spike itself -- a lottery-like payoff investors chase -- and not from volatility. This method takes
volatility out of the ranking key:

    SMAX(s) = MAX_k over the last ``window`` bar pairs  /  stdev of the ``scale`` daily returns
              that end where the MAX window starts

so the rank asks "how extreme was the biggest day for this stock", not "how jumpy is this stock".
The scale is measured on the ``scale`` returns *before* the MAX window, so a spike does not inflate
its own yardstick (a stock whose normal is calm and that just had a 6-sigma day scores high; a
stock that always moves 4% a day scores low however big its days). A name is scored only when
every bar pair in both windows has finite positive prices and the scale is positive.

The frame is M0091's, unchanged: F4's point-in-time members, the $5 price and 20M-dollar volume
screen, the SPY 200-day trend gate (cash when SPY closes at or below its 200-day average),
monthly, equal weights, fractional shares at Gotrade's real fees on ``monthly-hold-frac-gotrade``.
``side="low"`` holds the ``top`` lowest-SMAX names; ``side="high"`` the ``top`` highest, the paired
control the paper says must trail.

Assumptions, written before the run: the reserved idea named a 60-day yardstick; it is taken as
the 60 returns preceding the MAX window rather than overlapping it (the reason above). Bars are
split- and dividend-adjusted. Reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import N40, targets_from_rows
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 17)

Side = Literal["low", "high"]
_SIDES: tuple[str, ...] = ("low", "high")


@dataclass(frozen=True, slots=True)
class ScaledMaxParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; the rest is the ranking."""

    inner: FactorParams
    side: Side = "low"
    k: int = 5  # how many of the largest daily returns are averaged
    window: int = 21  # bar pairs in the MAX window (one trading month)
    scale: int = 60  # daily returns before the MAX window whose stdev is the yardstick

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        for name in ("k", "window", "scale"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.k < 1:
            raise ValueError(f"k must be >= 1, got {self.k}")
        if self.window < 5 or self.window < self.k:
            raise ValueError(f"window must be >= max(5, k), got {self.window}")
        if self.scale < 20:
            raise ValueError(f"scale must be >= 20, got {self.scale}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "k": str(self.k), "window": str(self.window),
               "scale": str(self.scale)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> ScaledMaxParams:
    if not isinstance(params, ScaledMaxParams):
        raise TypeError(f"params must be ScaledMaxParams, got {type(params).__name__}")
    return params


def scaled_lookback(params: ScaledMaxParams) -> int:
    return max(factor_lookback(params.inner), params.window + params.scale + 1)


def scaled_max(h: History, data_date: date, window: int, k: int, scale: int) -> float | None:
    """MAX_k over the last ``window`` returns, over the stdev of the ``scale`` returns before them."""
    i = h.index_of(data_date)
    n = window + scale
    if i is None or i < n:
        return None
    c = h.close[i - n : i + 1]
    if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
        return None
    r = c[1:] / c[:-1] - 1.0
    sd = float(np.std(r[:scale], ddof=1))
    if not (np.isfinite(sd) and sd > 0.0):
        return None
    x = float(np.mean(np.sort(r[scale:])[-k:])) / sd
    return x if np.isfinite(x) else None


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           params: ScaledMaxParams) -> list[FactorRow]:
    scored: list[tuple[float, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED:
            continue
        h = history.get(r.symbol)
        if h is None:
            continue
        x = scaled_max(h, data_date, params.window, params.k, params.scale)
        if x is None:
            continue
        key = x if params.side == "low" else -x
        scored.append((key, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored[: params.inner.top]]


@dataclass
class ScaledMaxPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class ScaledLotteryAllocator:
    """F4's book ranked on MAX scaled by the stock's own earlier daily swing.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0093"

    def lookback(self, params: Any) -> int:
        return scaled_lookback(_check(params))

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

    def prepare(self, history: Mapping[str, History]) -> ScaledMaxPrepared:
        return ScaledMaxPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ScaledMaxPrepared):
            raise TypeError(f"prepared must be ScaledMaxPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.history, data_date, p), p)


SCALED_LOTTERY = ScaledLotteryAllocator()


def _v(suffix: str, params: ScaledMaxParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0093-{suffix}", family="M0093", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SCALED_LOTTERY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0093",
    name=("A true lottery spike, not just a jumpy stock: rank big members on their biggest recent "
          "day measured against their own normal swing"),
    family="stock-lottery-avoidance",
    source_kind="variation",
    source_ref=(
        "Bali, Cakici and Whitelaw (2011), Maxing out: stocks as lotteries and the cross-section of "
        "expected returns, JFE 99(2), 427-446, doi:10.1016/j.jfineco.2010.08.014; variation of M0091"
    ),
    parent_id="M0091",
    hypothesis=(
        "M0091 showed that raw MAX among big index members is a volatility measure: the lowest-MAX "
        "book was a low-volatility book that tied SPY and fell 30%, and the highest-MAX control "
        "beat it. BCW (2011, working paper 2009) argue the overpricing comes from the spike "
        "itself, not from volatility. Scale MAX5 over the last 21 sessions by the stdev of the 60 "
        "daily returns before that window, so the rank asks how extreme the biggest days were for "
        "this stock, not how jumpy the stock is. Book: the 20 lowest scaled-MAX F4-screened "
        "point-in-time S&P 500 / Nasdaq-100 members ($5 price, 20M-dollar volume) at 5% each, "
        "behind the SPY 200-day switch, monthly, fractional shares at Gotrade's real fees "
        "(monthly-hold-frac-gotrade). Variants: LO5-S60-N20-T (the book), LO1-S60-N20-T (single "
        "biggest day, scaled), LO5-S60-N40-T (40 names), LO5-S120-N20-T (a 120-day yardstick), and "
        "HI5-S60-N20-T, the paired control holding the 20 highest scaled spikes, which must trail. "
        "Success: a LO variant beats SPY TR on dev within the 20% drawdown limit, the control "
        "trails it clearly, the edge is positive in 2009-2015 and holds in a majority of "
        "walk-forward folds."
    ),
    expected_failure=(
        "Once volatility is taken out, MAX among liquid large caps carries little information: "
        "the low book becomes a near-random, index-like equal-weight book of members whose last "
        "month was unremarkable for them, and it trails SPY's big-company drift (equal weighting "
        "tilts small inside the S&P). The high side is partly the names that just had an "
        "earnings jump or news shock, and the lab has seen post-earnings drift pay in this "
        "universe, so the control may beat the book again -- the spike as good news, not as a "
        "lottery ticket. A published anomaly fades, and BCW circulated from 2009, so whatever "
        "edge shows is likely front-loaded before 2009. The trend switch cannot catch fast "
        "crashes like August 1998, so the worst fall is likely above 20% as in the parent."
    ),
    candidates=(
        _v("LO5-S60-N20-T", ScaledMaxParams(N20, side="low", k=5, scale=60),
           "The 20 lowest scaled-MAX5 members, behind the SPY 200-day switch: the book"),
        _v("LO1-S60-N20-T", ScaledMaxParams(N20, side="low", k=1, scale=60),
           "The 20 lowest scaled single-day MAX members, behind the switch"),
        _v("LO5-S60-N40-T", ScaledMaxParams(N40, side="low", k=5, scale=60),
           "The 40 lowest scaled-MAX5 members, behind the switch: broader"),
        _v("LO5-S120-N20-T", ScaledMaxParams(N20, side="low", k=5, scale=120),
           "The 20 lowest scaled-MAX5 members against a 120-day yardstick, behind the switch"),
        _v("HI5-S60-N20-T", ScaledMaxParams(N20, side="high", k=5, scale=60),
           "The 20 highest scaled-MAX5 members, behind the switch: the control, expected to trail"),
    ),
    seen_keys=(
        "concept:max-effect",
        "concept:scaled-max",
        "concept:idiosyncratic-spike",
    ),
)
