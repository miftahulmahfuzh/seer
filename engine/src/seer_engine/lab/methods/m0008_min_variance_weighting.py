"""M0008 — Minimum-variance weighting of the momentum book (covariance, not exposure).

Source: Clarke, de Silva & Thorley (2006), "Minimum-variance portfolios in the U.S. equity
market", Journal of Portfolio Management 33(1); Ledoit & Wolf (2004), "A well-conditioned
estimator for large-dimensional covariance matrices", Journal of Multivariate Analysis 88(2).

Idea: M0001 showed that cutting the momentum book's gross exposure to hit a volatility target
buys drawdown at a near-linear price in return (TV10 to TV12: +1.5 pts CAGR for +1.9 pts max
DD), so its frontier passes through max DD 13% only at a CAGR below SPY's. That linearity is a
property of scaling ONE book up and down. Diversification is the way around it: hold the SAME
top-20 12-1 momentum names at full exposure, but set the RELATIVE weights to minimise the
portfolio's variance under a Ledoit-Wolf shrunk covariance matrix, long only and capped per
name so the solution cannot collapse into three stocks. Correlation-aware weighting lowers
portfolio volatility without lowering invested exposure, so the cash drag that capped M0001's
CAGR never appears. This is neither a volatility target nor a low-volatility screen (P7a's
F5/F6 already tested *selecting* calm names): selection stays pure momentum, only the
weighting changes.

The allocator wraps FACTOR. On data date d it takes the inner targets, measures each name's
last ``n`` daily returns through d, shrinks the sample covariance toward a scaled identity by
the Ledoit-Wolf (2004) analytic intensity, and solves

    minimise  w' S w   subject to   Σ w = 1,  0 <= w_i <= cap

by projected gradient descent with an exact projection onto the capped simplex. The solved
weights are then scaled by the inner targets' total weight, so the book's gross exposure is
exactly what FACTOR asked for and the freed-weight-is-cash behaviour of M0001 never happens.
A cap below 1/k (k = names) would make the constraint set empty, so the cap used is
max(cap, 1/k). If any name lacks ``n`` returns through d the inner weights are kept unchanged.
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
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import LazyPrepared, scale_weight
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import FACTOR, FactorParams

ADDED = date(2026, 10, 6)
PGD_STEPS = 400  # projected-gradient iterations; fixed, so the solve is deterministic


@dataclass(frozen=True, slots=True)
class MinVarParams:
    """FACTOR's selection, plus the covariance window and the per-name weight cap."""

    inner_params: FactorParams
    cap: Decimal = Decimal("0.10")  # per-name share of the book; max(cap, 1/k) is used
    n: int = 252  # daily returns behind the covariance estimate

    def __post_init__(self) -> None:
        if not isinstance(self.cap, Decimal):
            raise TypeError(f"cap must be a Decimal, got {type(self.cap).__name__}")
        if not self.cap.is_finite() or not (0 < self.cap <= 1):
            raise ValueError(f"cap must be in (0, 1], got {self.cap}")
        if isinstance(self.n, bool) or not isinstance(self.n, int):
            raise TypeError(f"n must be an int, got {type(self.n).__name__}")
        if self.n < 20:
            raise ValueError(f"n must be >= 20, got {self.n}")

    def as_dict(self) -> dict[str, str]:
        out = {"cap": str(self.cap), "n": str(self.n)}
        for k, v in self.inner_params.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _returns(h: History, data_date: date, n: int) -> np.ndarray | None:
    """The last ``n`` one-bar returns of ``h`` through ``data_date``, or None when unusable."""
    end = int(np.searchsorted(h.dates, as_day(data_date), side="right"))
    if end < n + 1:
        return None
    c = h.close[end - n - 1 : end]
    if not np.all(np.isfinite(c)) or np.any(c <= 0):
        return None
    return np.asarray(c[1:] / c[:-1] - 1.0, dtype=np.float64)


def returns_matrix(history: Mapping[str, History], targets: tuple[Target, ...], data_date: date,
                   n: int) -> np.ndarray | None:
    """A (k, n) matrix of the targets' returns in target order, or None when any name lacks them."""
    rows: list[np.ndarray] = []
    for t in targets:
        h = history.get(t.symbol)
        r = None if h is None else _returns(h, data_date, n)
        if r is None:
            return None
        rows.append(r)
    if len(rows) < 2:
        return None
    return np.vstack(rows)


def shrunk_cov(x: np.ndarray) -> np.ndarray | None:
    """Ledoit-Wolf (2004) covariance: the sample matrix pulled toward (trace/k) × I.

    The shrinkage intensity is their analytic one, b²/d², under the normalized inner product
    <A,B> = trace(A B') / k. The sum over observations of ||x_t x_t' − S||² reduces to
    Σ_t (x_t'x_t)² − n ||S||_F², which is what is computed here.
    """
    k, n = x.shape
    m = x - x.mean(axis=1, keepdims=True)
    s = (m @ m.T) / n
    if not np.all(np.isfinite(s)):
        return None
    mu = float(np.trace(s)) / k
    if not math.isfinite(mu) or mu <= 0.0:
        return None
    f = mu * np.eye(k, dtype=np.float64)
    d2 = float(np.sum((s - f) ** 2)) / k
    if not math.isfinite(d2) or d2 <= 0.0:
        return f
    qt = np.sum(m * m, axis=0)
    acc = float(np.sum(qt * qt)) - n * float(np.sum(s * s))
    if not math.isfinite(acc) or acc < 0.0:
        return None
    b2 = min(acc / (k * n * n), d2)
    shrink = b2 / d2
    out = shrink * f + (1.0 - shrink) * s
    return out if np.all(np.isfinite(out)) else None


def project_capped_simplex(y: np.ndarray, cap: float) -> np.ndarray:
    """The Euclidean projection of ``y`` onto {w : Σ w = 1, 0 <= w <= cap}, exactly.

    g(θ) = Σ clip(y − θ, 0, cap) is continuous, piecewise linear and non-increasing, with its
    kinks at the 2k values y_i and y_i − cap. g is cap × k >= 1 at the smallest kink and 0 at
    the largest, so the θ with g(θ) = 1 sits in one kink interval and is found by interpolating
    linearly inside it. ``cap × k >= 1`` is the caller's job (see ``min_var_weights``).
    """
    bp = np.sort(np.concatenate((y, y - cap)))
    g = np.clip(y[None, :] - bp[:, None], 0.0, cap).sum(axis=1)
    j = int(np.searchsorted(-g, -1.0, side="left"))  # first kink with g <= 1
    if j <= 0:
        theta = float(bp[0])
    elif j >= bp.size:
        theta = float(bp[-1])
    else:
        lo, hi = float(g[j - 1]), float(g[j])
        span = lo - hi
        frac = 0.0 if span <= 0.0 else (lo - 1.0) / span
        theta = float(bp[j - 1]) + frac * (float(bp[j]) - float(bp[j - 1]))
    return np.clip(y - theta, 0.0, cap)


def min_var_weights(cov: np.ndarray, cap: float) -> np.ndarray | None:
    """Long-only minimum-variance weights under a per-name cap, or None when unsolvable.

    Projected gradient descent from equal weights, a fixed ``PGD_STEPS`` iterations with step
    1 / (2 trace(cov)). trace(cov) >= the largest eigenvalue of a positive semi-definite
    matrix, so the step never exceeds 1 / L for the gradient 2 cov w and the iteration
    converges monotonically; a fixed count keeps the result a pure function of its inputs.
    """
    k = int(cov.shape[0])
    c = max(float(cap), 1.0 / k)
    tr = float(np.trace(cov))
    if not math.isfinite(tr) or tr <= 0.0:
        return None
    step = 1.0 / (2.0 * tr)
    w = np.full(k, 1.0 / k, dtype=np.float64)
    for _ in range(PGD_STEPS):
        w = project_capped_simplex(w - step * (2.0 * (cov @ w)), c)
    if not np.all(np.isfinite(w)) or float(np.sum(w)) <= 0.0:
        return None
    return w


def reweighted(history: Mapping[str, History], inner: tuple[Target, ...], data_date: date,
               params: MinVarParams) -> tuple[Target, ...]:
    """``inner`` with minimum-variance relative weights at the same total exposure."""
    if len(inner) < 2:
        return inner
    x = returns_matrix(history, inner, data_date, params.n)
    if x is None:
        return inner
    cov = shrunk_cov(x)
    if cov is None:
        return inner
    w = min_var_weights(cov, float(params.cap))
    if w is None:
        return inner
    total = Decimal(0)
    for t in inner:
        total += t.weight
    if total <= 0:
        return inner
    out: list[Target] = []
    for t, wi in zip(inner, w, strict=True):
        weight = scale_weight(total, Decimal(repr(float(wi))))
        if weight is not None:
            out.append(replace(t, weight=weight))
    return tuple(out)


class MinVarAllocator:
    """FACTOR's chosen names, re-weighted to minimum variance at FACTOR's own total exposure."""

    id = "M0008"

    def lookback(self, params: MinVarParams) -> int:
        return max(FACTOR.lookback(params.inner_params), params.n + 1)

    def symbols(self, params: MinVarParams) -> tuple[str, ...]:
        return tuple(FACTOR.symbols(params.inner_params))

    def holds(self, params: MinVarParams) -> tuple[str, ...]:
        return tuple(FACTOR.holds(params.inner_params))

    def uses_members(self, params: MinVarParams) -> bool:
        return bool(FACTOR.uses_members(params.inner_params))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: MinVarParams) -> tuple[Target, ...]:
        inner = FACTOR.targets(history, members, data_date, held, params.inner_params)
        return reweighted(history, inner, data_date, params)

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return LazyPrepared(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: MinVarParams) -> tuple[Target, ...]:
        inner = FACTOR.targets_prepared(prepared.of(FACTOR), members, data_date, held, params.inner_params)
        return reweighted(prepared.history, inner, data_date, params)


MINVAR = MinVarAllocator()
MOM20_TREND = FactorParams(rank="momentum", top=20)  # F4-MOM12-N20-TREND's inner params
MOM30_TREND = FactorParams(rank="momentum", top=30)
MOM20_NOTREND = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: MinVarParams, rationale: str, rules=MONTHLY_HOLD) -> Candidate:
    return Candidate(id=f"M0008-{suffix}", family="M0008", rules=rules, allocator=MINVAR,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0008",
    name="Minimum-variance weighting of the momentum book",
    family="stock-portfolio-construction",
    source_kind="paper",
    source_ref=(
        "Clarke, de Silva & Thorley (2006), Minimum-variance portfolios in the U.S. equity market, "
        "JPM 33(1); Ledoit & Wolf (2004), A well-conditioned estimator for large-dimensional "
        "covariance matrices, J. Multivariate Analysis 88(2)"
    ),
    parent_id="M0001",
    hypothesis=(
        "F4-MOM12-N20-TREND beat SPY TR (CAGR +16.2% vs +7.9%, PF 2.27) and failed only on max DD "
        "(22.2%); M0001 cut that drawdown to 11-13% but only by holding cash, which cost so much "
        "return that CAGR fell to 6-7.6%, below SPY. Keeping the same names at full exposure and "
        "setting their relative weights to minimise portfolio variance under a Ledoit-Wolf shrunk "
        "covariance matrix (long only, per-name cap) should cut max DD below 15% through "
        "diversification rather than through cash, leaving CAGR above SPY TR."
    ),
    expected_failure=(
        "Momentum's top 20 are a single crowded bet: in 2008 and 2011 their pairwise correlations "
        "go to ~0.9, so there is no low-correlation corner for the optimiser to hide in and max DD "
        "stays near 20%. Failing that, the covariance estimate is backward-looking and tilts the "
        "book toward names that were calm and are about to break, trading 2-4 pts of CAGR for only "
        "2-3 pts of drawdown -- the same near-linear frontier M0001 found, reached a different way."
    ),
    candidates=(
        _v("C10", MinVarParams(MOM20_TREND, Decimal("0.10"), 252),
           "Top-20 12-1 momentum, SPY trend filter, min-variance weights capped at 10% a name"),
        _v("C15", MinVarParams(MOM20_TREND, Decimal("0.15"), 252),
           "Same with a looser 15% cap: lets the optimiser concentrate where it wants"),
        _v("C10-H126", MinVarParams(MOM20_TREND, Decimal("0.10"), 126),
           "10% cap on a 6-month covariance: reacts faster to a change in correlation regime"),
        _v("N30-C07", MinVarParams(MOM30_TREND, Decimal("0.07"), 252),
           "Thirty names at a 7% cap: more raw material for the optimiser to diversify across"),
        _v("C10-NOTREND", MinVarParams(MOM20_NOTREND, Decimal("0.10"), 252),
           "No SPY trend gate: min-variance weighting alone as the crash guard"),
    ),
    seen_keys=(
        "concept:min-variance-weighting",
        "concept:ledoit-wolf-shrinkage",
        "url:https://doi.org/10.1016/S0047-259X(03)00096-4",
    ),
)
