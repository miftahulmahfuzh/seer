"""M0007 — Residual momentum: rank on market-model residuals, not total returns.

Source: Blitz, Huij & Martens (2011), "Residual momentum", Journal of Empirical Finance 18(3);
Blitz, Hanauer & Vidojevic (2020), "The idiosyncratic momentum anomaly", IRFA 69.
Idea: every momentum method in the lab so far (P7a's F4, and M0001/M0004 on top of it) ranks on
total return, which carries the market-beta component. After a bear market the winners are the
low-beta names and the losers the high-beta ones, so the book is implicitly short beta exactly
when the market rebounds — that is the momentum crash, and it is what kept F4-MOM12-N20-TREND
at a 22.2% max drawdown. Ranking instead on the momentum of market-model RESIDUALS strips the
beta component out of the *signal* rather than out of the *exposure*, which is the trade M0001
could not avoid (it bought a 11-13% drawdown with 1.5-2 points of CAGR).

The allocator reuses F4's universe screen, trend gate, book size and weighting verbatim
(``f_factor``), and replaces only the ranking key. On data date d, for each eligible member:

    * the market model is estimated by OLS on daily returns over the ``beta_n`` sessions ending
      at d - ``skip`` (so the skipped month never touches the estimate):
      r_i,t = alpha_i + beta_i * r_m,t + e_i,t;
    * the signal is the residual's 12-1 momentum: the ``mom_n`` residuals ending at d - ``skip``,
      summed and (when ``scaled``) divided by their own standard deviation — Blitz's
      t-statistic-like scaling, which is what turns the raw residual into "idiosyncratic
      momentum";
    * the ``top`` highest scores are held, equal-weighted, exactly as F4 does.

Returns are plain total-price returns, not excess-of-cash returns: the lab store has no
risk-free series, and at a daily horizon the risk-free rate is absorbed into alpha, which the
residual subtracts anyway. A daily return is used only when it spans exactly one session of the
market symbol's own calendar, so a halted or missing bar drops that one observation instead of
silently stretching a return across a gap; a name needs 80% of each window to be scored.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
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

ADDED = date(2026, 10, 6)
MIN_FRAC = 0.8  # a window needs this share of usable daily returns before a name is scored


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ResidParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; the rest is the ranking key.

    ``inner.rank`` never selects here (this allocator does the ranking); it still fixes the
    eligibility screen and the lookback, so keeping it at ``"momentum"`` makes the candidate
    universe identical to F4-MOM12-N<top>-TREND's, name for name.
    """

    inner: FactorParams
    beta_n: int = 378  # daily returns in the market-model estimate (18 months)
    mom_n: int = 252  # daily residuals accumulated into the signal (12 months)
    skip: int = 21  # sessions skipped before d (the "-1" of 12-1)
    scaled: bool = True  # divide the cumulative residual by its own stdev (Blitz's scaling)
    market: str = "SPY"

    def __post_init__(self) -> None:
        for name in ("beta_n", "mom_n", "skip"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.beta_n < 20:
            raise ValueError(f"beta_n must be >= 20, got {self.beta_n}")
        if self.mom_n < 20:
            raise ValueError(f"mom_n must be >= 20, got {self.mom_n}")
        if self.skip < 0:
            raise ValueError(f"skip must be >= 0, got {self.skip}")
        if self.beta_n < self.mom_n:
            raise ValueError(f"beta_n must be >= mom_n, got {self.beta_n} < {self.mom_n}")
        if not isinstance(self.scaled, bool):
            raise TypeError(f"scaled must be a bool, got {type(self.scaled).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "beta_n": str(self.beta_n),
            "mom_n": str(self.mom_n),
            "skip": str(self.skip),
            "scaled": "yes" if self.scaled else "no",
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def resid_lookback(params: ResidParams) -> int:
    """Bars through d the decision needs: the longer window, plus the skip, plus one close."""
    return max(factor_lookback(params.inner), params.skip + params.beta_n + 2,
               params.skip + params.mom_n + 2)


# --------------------------------------------------------------------------- the return grid


@dataclass(frozen=True, slots=True, eq=False)
class ReturnGrid:
    """Daily returns of every symbol laid on the market symbol's session calendar.

    ``rets[k, t]`` is symbol ``symbols[k]``'s return into calendar session ``dates[t]``, and is
    NaN unless that symbol has bars dated ``dates[t]`` and ``dates[t - 1]`` back to back. The
    grid is a function of the bars alone, so the columns at or before any date d are identical
    whether it was built from the whole history or from history cut at d.
    """

    symbols: tuple[str, ...]
    row: Mapping[str, int]
    dates: np.ndarray  # datetime64[D], the market symbol's sessions, ascending
    rets: np.ndarray  # (len(symbols), len(dates)) float64, NaN where unusable


def build_grid(history: Mapping[str, History], market: str) -> ReturnGrid | None:
    """``history`` on ``market``'s calendar, or None when the market symbol has too few bars."""
    m = history.get(market)
    if m is None or len(m) < 2:
        return None
    cal = m.dates
    ncal = len(cal)
    symbols = tuple(sorted(history))
    rets = np.full((len(symbols), ncal), np.nan, dtype=np.float64)
    for k, symbol in enumerate(symbols):
        h = history[symbol]
        n = len(h)
        if n < 2:
            continue
        pos = np.searchsorted(cal, h.dates)
        inside = pos < ncal
        safe = np.where(inside, pos, 0)
        on_cal = inside & (cal[safe] == h.dates)
        prev, cur = h.close[:-1], h.close[1:]
        with np.errstate(divide="ignore", invalid="ignore"):
            step_ret = cur / prev - 1.0
        usable = np.isfinite(prev) & np.isfinite(cur) & (prev > 0.0) & np.isfinite(step_ret)
        keep = np.zeros(n, dtype=bool)
        keep[1:] = usable & on_cal[1:] & on_cal[:-1] & (safe[1:] == safe[:-1] + 1)
        rets[k, safe[keep]] = step_ret[keep[1:]]
    rets.setflags(write=False)
    return ReturnGrid(symbols, {s: k for k, s in enumerate(symbols)}, cal, rets)


def _ols(y: np.ndarray, x: np.ndarray, ok: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-row OLS of ``y`` on ``x`` over the ``ok`` entries: (alpha, beta, usable-row mask)."""
    n = ok.sum(axis=1).astype(np.float64)
    yz = np.where(ok, y, 0.0)
    xz = np.where(ok, x, 0.0)
    sx = xz.sum(axis=1)
    sy = yz.sum(axis=1)
    sxx = (xz * xz).sum(axis=1)
    sxy = (xz * yz).sum(axis=1)
    den = n * sxx - sx * sx
    good = np.isfinite(den) & (den != 0.0) & (n > 2.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.where(good, (n * sxy - sx * sy) / np.where(good, den, 1.0), np.nan)
        alpha = np.where(good, (sy - beta * sx) / np.where(n > 0.0, n, 1.0), np.nan)
    return alpha, beta, good & np.isfinite(alpha) & np.isfinite(beta)


def residual_scores(
    grid: ReturnGrid, symbols: list[str], data_date: date, params: ResidParams
) -> dict[str, float]:
    """Each symbol's residual-momentum score on ``data_date`` (absent = not scorable).

    Reads only calendar columns at or before ``data_date``.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    end = j - params.skip
    b0 = end - params.beta_n + 1
    r0 = end - params.mom_n + 1
    if end < 0 or b0 < 0 or r0 < 0:
        return {}
    mrow = grid.row.get(params.market)
    if mrow is None:
        return {}
    rows = [grid.row[s] for s in symbols if s in grid.row]
    names = [s for s in symbols if s in grid.row]
    if not rows:
        return {}
    idx = np.asarray(rows, dtype=np.int64)

    mb = grid.rets[mrow, b0 : end + 1]
    rb = grid.rets[idx, b0 : end + 1]
    ok_b = np.isfinite(rb) & np.isfinite(mb)[None, :]
    enough_b = ok_b.sum(axis=1) >= max(3, math.ceil(MIN_FRAC * params.beta_n))
    alpha, beta, fitted = _ols(rb, np.broadcast_to(mb, rb.shape), ok_b)

    mw = grid.rets[mrow, r0 : end + 1]
    rw = grid.rets[idx, r0 : end + 1]
    ok_w = np.isfinite(rw) & np.isfinite(mw)[None, :]
    m = ok_w.sum(axis=1)
    enough_w = m >= max(3, math.ceil(MIN_FRAC * params.mom_n))

    with np.errstate(divide="ignore", invalid="ignore"):
        resid = rw - alpha[:, None] - beta[:, None] * mw[None, :]
        rz = np.where(ok_w, resid, 0.0)
        cum = rz.sum(axis=1)
        mean = cum / np.where(m > 0, m, 1)
        dev = np.where(ok_w, resid - mean[:, None], 0.0)
        sd = np.sqrt((dev * dev).sum(axis=1) / np.where(m > 0, m, 1))
        score = np.where(sd > 0.0, cum / np.where(sd > 0.0, sd, 1.0), np.nan) if params.scaled else cum

    live = enough_b & enough_w & fitted & np.isfinite(score)
    return {names[k]: float(score[k]) for k in (int(v) for v in np.flatnonzero(live))}


def targets_from_scores(
    rows: list[FactorRow], scores: Mapping[str, float], params: ResidParams
) -> tuple[Target, ...]:
    """F4's weighting and pricing applied to the ``top`` highest residual scores."""
    scorable = [r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED]
    chosen = sorted(scorable, key=lambda r: (-scores[r.symbol], r.symbol))[: params.inner.top]
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class ResidPrepared:
    """F4's rolling feature columns plus one return grid per market symbol, built on first use."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    grids: dict[str, ReturnGrid | None] = field(default_factory=dict, repr=False)

    def grid(self, market: str) -> ReturnGrid | None:
        if market not in self.grids:
            self.grids[market] = build_grid(self.history, market)
        return self.grids[market]


def FACTOR_SYMBOLS(inner: FactorParams) -> tuple[str, ...]:
    """The fixed symbols F4 reads for ``inner`` (its trend symbol, if any)."""
    return () if inner.trend is None else (inner.trend[0],)


def _check(params: object) -> ResidParams:
    if not isinstance(params, ResidParams):
        raise TypeError(f"params must be ResidParams, got {type(params).__name__}")
    return params


class ResidualMomentumAllocator:
    """F4's book, ranked on market-model residual momentum instead of total-return momentum.

    Held symbols get no special treatment: the targets are exactly the new top set, so a name
    that falls out of it is signal-exited by the book engine, as in F4.
    """

    id = "M0007"

    def lookback(self, params: Any) -> int:
        return resid_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({p.market, *FACTOR_SYMBOLS(p.inner)}))

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
        if not rows:
            return ()
        grid = build_grid(history, p.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p)
        return targets_from_scores(rows, scores, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        grid = prepared.grid(p.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p)
        return targets_from_scores(rows, scores, p)


RESIDMOM = ResidualMomentumAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)  # F4-MOM12-N20-TREND's screen
N10 = FactorParams(rank="momentum", top=10, trend=TREND)  # F4-MOM12-N10-TREND's screen
N30 = FactorParams(rank="momentum", top=30, trend=TREND)
N20_NOTREND = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: ResidParams, rationale: str, rules=MONTHLY_HOLD) -> Candidate:
    return Candidate(id=f"M0007-{suffix}", family="M0007", rules=rules, allocator=RESIDMOM,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0007",
    name="Residual momentum: rank on market-model residual returns, not total returns",
    family="stock-residual-momentum",
    source_kind="paper",
    source_ref=(
        "Blitz, Huij & Martens (2011), Residual momentum, J. Empirical Finance 18(3), 506-521; "
        "Blitz, Hanauer & Vidojevic (2020), The idiosyncratic momentum anomaly, IRFA 69"
    ),
    hypothesis=(
        "Total-return momentum carries the market-beta component that makes momentum crash: after "
        "a bear market the winners are low-beta and the losers high-beta, so a rebound runs the "
        "book over. That is why F4-MOM12-N20-TREND beat SPY TR (+16.2% vs +7.9% CAGR, PF 2.27) and "
        "still drew down 22.2%. Ranking on the momentum of market-model residuals removes the beta "
        "component from the signal itself, so the book stays fully invested and is no longer short "
        "beta into a rebound. The literature reports the same return at about half the volatility "
        "and much smaller skew. With F4's screen, trend gate and equal weights unchanged, this "
        "should beat SPY TR with max DD under 15% WITHOUT cutting gross exposure, which is the "
        "trade M0001's own-vol scaling could not avoid."
    ),
    expected_failure=(
        "The residual signal is noisier than total momentum, not safer: dividing by the residual "
        "stdev tilts the book toward low-idiosyncratic-vol names whose residual drift is tiny, so "
        "CAGR falls to SPY's or below while max DD stays near 20% because the 2008-09 and 2000-02 "
        "drawdowns were market-wide, not momentum-specific, and the SPY trend gate was already "
        "catching whatever part of them a long-only book can catch."
    ),
    candidates=(
        _v("N20", ResidParams(N20),
           "Top-20 scaled residual momentum, SPY-200 trend gate: F4-MOM12-N20-TREND's book, new rank key"),
        _v("N10", ResidParams(N10),
           "Top-10: the concentrated book, where total momentum drew down 28.2%"),
        _v("N30", ResidParams(N30),
           "Top-30: more names, to see whether residual ranking still pays when it is diluted"),
        _v("N20-RAW", ResidParams(N20, scaled=False),
           "Top-20 on the raw cumulative residual: isolates Blitz's stdev scaling from the residual itself"),
        _v("N20-NOTREND", ResidParams(N20_NOTREND),
           "No SPY trend gate: the paper's claim is that the signal alone tames the crash"),
    ),
    seen_keys=(
        "concept:residual-momentum",
        "concept:idiosyncratic-momentum",
        "doi:10.1016/j.jempfin.2011.01.003",
    ),
)
