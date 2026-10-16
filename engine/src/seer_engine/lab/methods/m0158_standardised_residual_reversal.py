"""M0158 — Bounce of the stock's own surprise: residual reversal standardised by the stock's own swing.

Source: Blitz, Huij, Lansdorp & Verbeek (2013), Short-term residual reversal, Journal of Financial
Markets 16(3) 477-504; Huij & Lansdorp (2017) revisit it out of sample.
Idea: plain one-month reversal buys last month's biggest fallers, and the biggest fallers are
mostly the jumpiest stocks, so the book ends up long risk and crashes with it (M0028's
PLAIN-RESID: +3.5% a year on the deposits vs SPY's +7.2%, a 35% fall). Blitz et al. rank instead
on the *standardised* residual: last month's return the market does not explain, divided by how
much the stock's residual normally swings. A calm stock that fell three of its own sigmas ranks
ahead of a wild one that fell twice as far in percent. That is a different pick list from M0028's
filtered one, which cut jumpy names with a hard calm-half screen and a 200-day trend filter.

Why the market model is fitted on *daily* returns over the year before the window, where the
paper fits 36 monthly returns: the lab's allocator contract says a decision may depend only on the
bars its lookback declares, and declaring three years would push the run's start from 1996 to 1997
and could not be checked on the contract's fixture at all. A year of daily residuals gives about
250 observations for the residual's standard deviation, more than 36 monthly ones, at the price of
some day-to-day noise the formation month does not share. The beta is the same one M0028 fitted,
so M0028's unfiltered residual book (PLAIN-RESID) is this method's control with the
standardisation switched off: same screen, same 20 names, same gate, same fees.

On data date d, inside F4's liquidity and membership screen (20-day dollar volume over $20M,
price at least $5) and behind its SPY-200 trend gate:

    * the ``beta_n`` sessions before the formation window give each stock a daily market-model fit
      (alpha, beta) and the standard deviation of its daily residuals, sigma;
    * the formation residual is the sum of the stock's daily returns over the last ``rev_n``
      sessions less beta times the market's, with no alpha (alpha is a drift estimate, not part
      of the surprise), the same residual M0028 ranked on;
    * the score divides it by sigma*sqrt(rev_n), the residual's normal swing over a window that
      long;
    * the ``top`` most negative scores are held, equal weight, for a month.

Every piece reads only calendar columns at or before d, through M0007's return grid, so a day
counts only when the stock has back-to-back bars on the market's calendar.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    ResidPrepared,
    ReturnGrid,
    build_grid,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 16)
MIN_FRAC = 0.8  # a window needs this share of usable daily returns before a name is scored


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ZRevParams:
    """``inner`` is F4's screen, trend gate and book size; the rest is the reversal signal.

    ``inner.rank`` never selects here; keeping it at ``"momentum"`` makes the screened universe
    identical to M0007's and M0028's, name for name.
    """

    inner: FactorParams
    rev_n: int = 21  # sessions in the formation window
    beta_n: int = 252  # sessions before the formation window the fit and sigma come from
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("rev_n", "beta_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.rev_n < 5:
            raise ValueError(f"rev_n must be >= 5, got {self.rev_n}")
        if self.beta_n < 60:
            raise ValueError(f"beta_n must be >= 60, got {self.beta_n}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"rev_n": str(self.rev_n), "beta_n": str(self.beta_n), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ZRevParams:
    if not isinstance(params, ZRevParams):
        raise TypeError(f"params must be ZRevParams, got {type(params).__name__}")
    return params


def zrev_lookback(params: ZRevParams) -> int:
    """Bars through d the decision needs: the screen's, and the fit plus formation windows."""
    return max(factor_lookback(params.inner), params.beta_n + params.rev_n + 2)


# --------------------------------------------------------------------------- the signal


def zrev_scores(
    grid: ReturnGrid, symbols: list[str], data_date: date, params: ZRevParams
) -> dict[str, float]:
    """Each symbol's standardised formation-window residual on ``data_date``; lower = bigger fall.

    Absent = too little of a window to fit or score. Reads only calendar columns at or before
    ``data_date``.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    f0 = j - params.rev_n + 1
    b_end = f0 - 1
    b0 = b_end - params.beta_n + 1
    if b0 < 0:
        return {}
    mrow = grid.row.get(params.market)
    if mrow is None:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)

    rw = grid.rets[idx, f0 : j + 1]
    mw = grid.rets[mrow, f0 : j + 1]
    ok_w = np.isfinite(rw) & np.isfinite(mw)[None, :]
    enough = ok_w.sum(axis=1) >= max(3, math.ceil(MIN_FRAC * params.rev_n))

    rb = grid.rets[idx, b0 : b_end + 1]
    mb = grid.rets[mrow, b0 : b_end + 1]
    ok_b = np.isfinite(rb) & np.isfinite(mb)[None, :]
    n = ok_b.sum(axis=1).astype(np.float64)
    enough = enough & (n >= max(3, math.ceil(MIN_FRAC * params.beta_n)))
    xz = np.where(ok_b, np.broadcast_to(mb, rb.shape), 0.0)
    yz = np.where(ok_b, rb, 0.0)
    sx, sy = xz.sum(axis=1), yz.sum(axis=1)
    den = n * (xz * xz).sum(axis=1) - sx * sx
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.where(den != 0.0, (n * (xz * yz).sum(axis=1) - sx * sy) / np.where(den != 0.0, den, 1.0),
                        np.nan)
        alpha = (sy - beta * sx) / n
        e = np.where(ok_b, rb - alpha[:, None] - beta[:, None] * mb[None, :], 0.0)
        sigma = np.sqrt((e * e).sum(axis=1) / (n - 2.0))
        resid = np.where(ok_w, rw - beta[:, None] * mw[None, :], 0.0).sum(axis=1)
        score = resid / (sigma * math.sqrt(params.rev_n))

    live = enough & np.isfinite(score) & (sigma > 0.0)
    return {names[k]: float(score[k]) for k in (int(v) for v in np.flatnonzero(live))}


def targets_from_scores(rows: list[FactorRow], scores: Mapping[str, float],
                        params: ZRevParams) -> tuple[Target, ...]:
    """F4's equal weighting and pricing applied to the ``top`` most negative scores."""
    scorable = [r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED]
    chosen = sorted(scorable, key=lambda r: (scores[r.symbol], r.symbol))[: params.inner.top]
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


class StandardisedResidualReversalAllocator:
    """Last month's most negative standardised residuals among screened names, held for a month.

    Held symbols get no special treatment: the targets are exactly the new set, so a name that
    leaves it is signal-exited by the book engine.
    """

    id = "M0158"

    def lookback(self, params: Any) -> int:
        return zrev_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, rows: list[FactorRow], grid: ReturnGrid | None, data_date: date,
                 params: ZRevParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        scores = zrev_scores(grid, [r.symbol for r in rows], data_date, params)
        return targets_from_scores(rows, scores, params)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(rows, build_grid(history, p.market), data_date, p)

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
        return self._targets(rows, prepared.grid(p.market), data_date, p)


ZREV = StandardisedResidualReversalAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)
N35 = FactorParams(rank="momentum", top=35, trend=TREND)


def _v(suffix: str, params: ZRevParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0158-{suffix}", family="M0158", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ZREV, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0158",
    name=("Bounce of the stock's own surprise: short-term reversal on market-model residuals, "
          "standardised by the stock's own swing"),
    family="stock-short-term-reversal",
    source_kind="paper",
    source_ref=(
        "Blitz, Huij, Lansdorp & Verbeek 2013, Journal of Financial Markets 16(3) 477-504 "
        "'Short-term residual reversal'; Huij & Lansdorp 2017 revisit"
    ),
    hypothesis=(
        "Published 2013, on US data to 2010, so the dev window (to 2015) is mostly before the "
        "crowd. Blitz et al. show that reversing last month's RESIDUAL return -- the part the "
        "market does not explain -- divided by the stock's own residual volatility earns about "
        "twice a plain reversal with roughly half its risk, and survives trading costs among large "
        "caps after 1990. The standardisation is the point: plain reversal buys the jumpiest "
        "fallers and so crashes with risk (the lab's unfiltered residual bounce book earned +3.5% "
        "a year on the deposits vs SPY's +7.2% and fell 35%), while a z-score ranks a calm stock "
        "that fell three of its own sigmas ahead of a wild one that fell further in percent. Book: "
        "each month, inside the liquid index-member screen and behind the SPY-200 switch, hold the "
        "20 most negative standardised residuals over the last 21 sessions, the residual from a "
        "market-model fit on the 252 daily returns before the window (the paper fits 36 monthly "
        "returns; the lab's lookback contract forces a year of daily ones), equal slots, fractional "
        "shares at Gotrade's real fees (monthly-hold-frac-gotrade) on the owner's monthly deposits. "
        "Arms: Z10-N20 uses a 10-session window (the reversal literature finds the bounce sharpest "
        "in the shortest windows); Z21-N35 holds 35 names (spreads the falling-knife risk). The "
        "control with the standardisation switched off is already recorded: the earlier bounce "
        "book's unfiltered residual variant uses the same screen, beta, 20 names, gate and fees. "
        "Success: beat total-return SPY on the deposits with a worst "
        "fall under 25%, profit factor >= 1.3, and a positive edge in 2009-2015."
    ),
    expected_failure=(
        "Monthly turnover near 100% at Gotrade's minimum fees on 20 small slots eats most of a "
        "premium the paper measured at institutional costs; the earlier calm bounce book traded 16 "
        "times its size a year and kept only +0.3 points over SPY. Reversal is a liquidity-provision "
        "premium that shrank sharply after decimal ticks (2001) and is widely published, so what "
        "edge there is likely sits in 1996-2002 and is gone by 2009-2015. In crises fallers keep "
        "falling (August 1998, autumn 2008) and the 200-day switch reacts late, so the worst fall "
        "may pass 25%. Third, z-scoring leans the picks toward calm, low-beta names, which pulls the "
        "book toward a low-volatility tilt that lags SPY in strong bull years like 1998-99 and "
        "2013. Behaviourally it should sit far from the failed momentum books; if its monthly "
        "returns still correlate at 0.6+ with them it is the long-only market tie again."
    ),
    candidates=(
        _v("Z21-N20", ZRevParams(N20),
           "20 most negative 21-session residuals, each divided by the stock's own residual swing"),
        _v("Z10-N20", ZRevParams(N20, rev_n=10),
           "Same, on a 10-session formation window: is the bounce sharper over two weeks?"),
        _v("Z21-N35", ZRevParams(N35),
           "Same signal, 35 names: does width tame the falling-knife months?"),
    ),
    seen_keys=(
        "concept:standardised-residual-reversal",
        "concept:residual-reversal-zscore",
    ),
)
