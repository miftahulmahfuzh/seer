"""M0091 — Skip the lottery tickets: hold the big index members whose biggest one-day jump last month was smallest.

Source: Bali, Cakici & Whitelaw (2011), "Maxing out: stocks as lotteries and the cross-section of
expected returns", Journal of Financial Economics 99(2), 427-446, doi:10.1016/j.jfineco.2010.08.014.
Idea: investors overpay for stocks that just had a lottery-like single-day spike, so the stocks
with the largest daily returns over the past month (MAX) go on to trail and the lowest-MAX stocks
lead. BCW report a decile spread of more than 1% a month on 1962-2005, robust to size, momentum,
short-term reversal and skewness. The anomaly was published in 2011 (working paper 2009), so the
dev window (to 2015-10-16) sees it mostly before the crowd traded it.

The frame is F4's -- point-in-time members, the $5 price and 20M-dollar volume screen, the SPY
200-day trend gate (all cash when SPY closes at or below its 200-day average), monthly, equal
weights, fractional shares at Gotrade's real fees on ``monthly-hold-frac-gotrade`` -- with one
change: the ranking key is MAX over the ``window`` daily returns ending at d (the symbol's own
bars):

    MAX_k(s) = mean of the k largest of close_t / close_{t-1} - 1, t over the last ``window`` bars

``k=1`` is BCW's MAX; ``k=5`` is their less noisy MAX(5). A name is scored only when every one of
its ``window`` bar pairs has finite positive prices. ``side="low"`` holds the ``top`` lowest-MAX
names; ``side="high"`` holds the ``top`` highest (the paired control, which the paper says should
trail -- the effect must show as a spread, not only as low beta).

Assumptions, written before the run: the reserved idea said "rest in SPY"; with ``top`` equal
5% slots a full book is fully invested, so there is no rest to park, and a gate-off month is cash
as in every F4-framed method (M0058, M0071). Bars are split- and dividend-adjusted, so an
ex-dividend day does not show as a drop. Reads only bars dated <= d.
"""

from __future__ import annotations

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

ADDED = date(2026, 10, 11)

Side = Literal["low", "high"]
_SIDES: tuple[str, ...] = ("low", "high")


@dataclass(frozen=True, slots=True)
class MaxParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; the rest is the ranking."""

    inner: FactorParams
    side: Side = "low"
    k: int = 5  # how many of the largest daily returns are averaged
    window: int = 21  # bar pairs in the MAX window (one trading month)

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        for name in ("k", "window"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.k < 1:
            raise ValueError(f"k must be >= 1, got {self.k}")
        if self.window < 5 or self.window < self.k:
            raise ValueError(f"window must be >= max(5, k), got {self.window}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "k": str(self.k), "window": str(self.window)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> MaxParams:
    if not isinstance(params, MaxParams):
        raise TypeError(f"params must be MaxParams, got {type(params).__name__}")
    return params


def max_lookback(params: MaxParams) -> int:
    return max(factor_lookback(params.inner), params.window + 1)


def max_k(h: History, data_date: date, window: int, k: int) -> float | None:
    """Mean of the ``k`` largest daily returns over the ``window`` bar pairs ending at ``data_date``."""
    i = h.index_of(data_date)
    if i is None or i < window:
        return None
    c = h.close[i - window : i + 1]
    if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
        return None
    r = c[1:] / c[:-1] - 1.0
    x = float(np.mean(np.sort(r)[-k:]))
    return x if np.isfinite(x) else None


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           params: MaxParams) -> list[FactorRow]:
    scored: list[tuple[float, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED:
            continue
        h = history.get(r.symbol)
        if h is None:
            continue
        x = max_k(h, data_date, params.window, params.k)
        if x is None:
            continue
        key = x if params.side == "low" else -x
        scored.append((key, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored[: params.inner.top]]


def targets_from_rows(chosen: list[FactorRow], params: MaxParams) -> tuple[Target, ...]:
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass
class MaxPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class LotteryAvoidanceAllocator:
    """F4's book ranked on MAX, the largest recent daily returns.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0091"

    def lookback(self, params: Any) -> int:
        return max_lookback(_check(params))

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

    def prepare(self, history: Mapping[str, History]) -> MaxPrepared:
        return MaxPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, MaxPrepared):
            raise TypeError(f"prepared must be MaxPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.history, data_date, p), p)


LOTTERY = LotteryAvoidanceAllocator()

N40 = replace(N20, top=40)
N20_NOTREND = replace(N20, trend=None)


def _v(suffix: str, params: MaxParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0091-{suffix}", family="M0091", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LOTTERY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0091",
    name="Skip the lottery tickets: hold the big index members whose biggest one-day jump last month was smallest",
    family="stock-lottery-avoidance",
    source_kind="paper",
    source_ref=(
        "Bali, Cakici and Whitelaw (2011), Maxing out: stocks as lotteries and the cross-section of "
        "expected returns, JFE 99(2), 427-446, doi:10.1016/j.jfineco.2010.08.014"
    ),
    parent_id=None,
    hypothesis=(
        "Investors overpay for stocks that recently had a lottery-like single-day spike, so the "
        "stocks whose largest daily return over the past month (MAX) is highest go on to "
        "underperform and the lowest-MAX stocks outperform (BCW 2011, published 2011 with a 2009 "
        "working paper: a decile spread above 1% a month on 1962-2005, robust to size, momentum, "
        "reversal and skewness). Book: each month, among F4-screened point-in-time S&P 500 / "
        "Nasdaq-100 members ($5 price, 20M-dollar daily volume), rank on the average of the 5 "
        "largest daily returns over the last 21 sessions (MAX5, the less noisy variant) and hold "
        "the 20 lowest at 5% each, behind the SPY 200-day switch, monthly, fractional shares at "
        "Gotrade's real fees (monthly-hold-frac-gotrade). Variants: LO5-N20-T (the book), LO1-N20-T "
        "(BCW's single-day MAX), LO5-N40-T (40 names), LO5-N20 (no switch, always invested), and "
        "HI5-N20-T, the paired control holding the 20 highest-MAX names, which must trail: the "
        "effect has to show as a spread, not only as low beta. It ranks on a lottery measure, not "
        "on past trend, so it should not move with the failed momentum books. Success: a LO "
        "variant beats SPY TR on dev within the 20% drawdown limit, the control trails it clearly, "
        "and the edge holds in 2009-2015 and in a majority of walk-forward folds."
    ),
    expected_failure=(
        "In large caps MAX is mostly low volatility in disguise: the lowest-MAX names are the "
        "calm utilities, staples and drug makers, so the book is a low-beta book. Behind a trend "
        "switch it should have a shallow worst fall, but low-vol large caps lagged the 2009-2015 "
        "growth run and the late-1990s tech run, so the likeliest failure is trailing SPY TR on "
        "CAGR: a smoother ride that earns less. A published anomaly fades, and BCW was circulating "
        "from 2009, so whatever edge shows is likely front-loaded before 2009. The control may "
        "not trail by much in 1996-2000, when lottery stocks were the winners."
    ),
    candidates=(
        _v("LO5-N20-T", MaxParams(N20, side="low", k=5),
           "The 20 lowest-MAX5 members, behind the SPY 200-day switch: the book"),
        _v("LO1-N20-T", MaxParams(N20, side="low", k=1),
           "The 20 lowest single-day-MAX members, behind the switch: BCW's original measure"),
        _v("LO5-N40-T", MaxParams(N40, side="low", k=5),
           "The 40 lowest-MAX5 members, behind the switch: broader, less single-stock risk"),
        _v("LO5-N20", MaxParams(N20_NOTREND, side="low", k=5),
           "The 20 lowest-MAX5 members, always invested: does a calm book need the switch"),
        _v("HI5-N20-T", MaxParams(N20, side="high", k=5),
           "The 20 highest-MAX5 members, behind the switch: the control, expected to trail"),
    ),
    seen_keys=(
        "concept:max-effect",
        "concept:lottery-stocks",
        "doi:10.1016/j.jfineco.2010.08.014",
    ),
)
