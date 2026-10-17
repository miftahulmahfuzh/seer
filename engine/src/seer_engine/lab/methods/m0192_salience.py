"""M0192 — Stocks whose bad days stood out: the salience score of Cosemans & Frehen, long the low end.

Source: Cosemans & Frehen (2021), Salience theory and stock prices: Empirical evidence, Journal of
Financial Economics 140(2), 460-483; the theory is Bordalo, Gennaioli & Shleifer (2012, 2013).
Idea: investors weigh a stock's past days by how much each stood out against the market that day.
A stock whose loudest days last month were gains looks like a winner and gets overbought; one whose
loudest days were losses gets oversold. The paper sorts US stocks on that score each month and the
low-salience end (stand-out losses) beats the high end the next month, and says the gap is not
plain one-month reversal, lottery demand or news.

The score, on data date d, for each name in F4's screen (point-in-time members, $5 price, $20M
20-day dollar volume) over the last ``window`` sessions of M0007's return grid:

    * the market's return each day is the equal-weighted average of the screened names' returns
      that day (the paper uses the equal-weighted market; the screen is the cross-section the lab
      can price point in time);
    * a day's salience is |r - m| / (|r| + |m| + theta), theta = 0.1 (the paper's value);
    * the stock's days are ranked by salience, most salient first (k = 1, 2, ...; ties by date);
    * each day gets the weight delta**k / mean(delta**k), delta = 0.7, so the weights average 1;
    * the score is mean((weight - 1) * r): the covariance of the salience weights with returns.
      Negative means the loudest days were losses.

Why the cross-section's own average and not SPY: the salience of a day is about what the stock did
next to everything else investors saw, and SPY is cap-weighted, so on a narrow-market day it would
make half the index look salient. The equal-weighted screen average is the paper's choice.

The book. Rank the scores, lowest first (``side="low"``; ``"high"`` is the paired control, the
paper's losing end). A held name still ranked inside ``keep`` stays; the free slots are filled
from the top of the ranking, ``top`` slots of 1/top each. Unfilled slots sit in SPY. With
``inner.trend`` set the whole book is cash while SPY is under its 200-day average, as in F4.
``signal="reversal"`` swaps the score for the plain sum of the same window's daily returns, so the
reversal control shares every other piece: screen, band, slots, switch, fees. If the salience book
does not clear the reversal book, the score is reversal under another name.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits. Every piece reads calendar columns at or before d only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    ResidPrepared,
    ReturnGrid,
    build_grid,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 17)
MIN_FRAC = 0.8  # a window needs this share of usable daily returns before a name is scored
SIGNALS = ("salience", "reversal")
SIDES = ("low", "high")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class SalienceParams:
    """``inner`` is F4's screen, trend gate and book size; the rest is the signal and the band.

    ``inner.rank`` never selects here; ``"momentum"`` keeps the screened universe identical to
    M0007's and M0158's, name for name.
    """

    inner: FactorParams
    keep: int = 40
    window: int = 21
    signal: str = "salience"
    side: str = "low"
    theta: float = 0.1
    delta: float = 0.7
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("keep", "window"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.window < 5:
            raise ValueError(f"window must be >= 5, got {self.window}")
        if self.keep < self.inner.top:
            raise ValueError(f"keep must be >= top, got {self.keep} < {self.inner.top}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if not (self.theta > 0.0 and 0.0 < self.delta < 1.0):
            raise ValueError(f"need theta > 0 and 0 < delta < 1, got {self.theta}, {self.delta}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep": str(self.keep), "window": str(self.window), "signal": self.signal,
               "side": self.side, "theta": repr(self.theta), "delta": repr(self.delta),
               "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SalienceParams:
    if not isinstance(params, SalienceParams):
        raise TypeError(f"params must be SalienceParams, got {type(params).__name__}")
    return params


def salience_lookback(params: SalienceParams) -> int:
    return max(factor_lookback(params.inner), params.window + 2)


# --------------------------------------------------------------------------- the signal


def scores(grid: ReturnGrid, symbols: list[str], data_date: date,
           params: SalienceParams) -> dict[str, float]:
    """Each symbol's score on ``data_date`` (salience covariance or window return); absent = too thin."""
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    f0 = j - params.window + 1
    if f0 < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    r = grid.rets[idx, f0 : j + 1]
    ok = np.isfinite(r)
    enough = ok.sum(axis=1) >= max(3, math.ceil(MIN_FRAC * params.window))
    if params.signal == "reversal":
        score = np.where(ok, r, 0.0).sum(axis=1)
    else:
        cnt = ok.sum(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            m = np.where(cnt > 0, np.where(ok, r, 0.0).sum(axis=0) / np.where(cnt > 0, cnt, 1), np.nan)
            sal = np.abs(r - m[None, :]) / (np.abs(r) + np.abs(m)[None, :] + params.theta)
        valid = ok & np.isfinite(sal)
        key = np.where(valid, -sal, np.inf)  # most salient first, unusable days last
        order = np.argsort(key, axis=1, kind="stable")
        rank = np.empty_like(order)
        rows = np.arange(order.shape[0])[:, None]
        rank[rows, order] = np.arange(order.shape[1])[None, :] + 1
        dk = np.where(valid, params.delta ** rank.astype(np.float64), 0.0)
        nv = valid.sum(axis=1).astype(np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            w = dk / (dk.sum(axis=1) / nv)[:, None]
            score = np.where(valid, (w - 1.0) * np.where(valid, r, 0.0), 0.0).sum(axis=1) / nv
        enough = enough & (valid.sum(axis=1) >= max(3, math.ceil(MIN_FRAC * params.window)))
    live = enough & np.isfinite(score)
    return {names[k]: float(score[k]) for k in (int(v) for v in np.flatnonzero(live))}


def choose(history: Mapping[str, History], rows: list[FactorRow], sc: Mapping[str, float],
           data_date: date, held: frozenset[str], p: SalienceParams) -> tuple[Target, ...]:
    """The band: held names ranked inside ``keep`` stay, the rest of ``top`` filled from the top."""
    sign = 1.0 if p.side == "low" else -1.0
    usable = [r.symbol for r in rows if r.symbol in sc and r.symbol not in EXCLUDED]
    order = sorted(usable, key=lambda s: (sign * sc[s], s))
    rank = {s: i for i, s in enumerate(order)}
    kept = sorted((s for s in held if rank.get(s, p.keep) < p.keep), key=lambda s: rank[s])
    picks = kept[: p.inner.top]
    for s in order:
        if len(picks) >= p.inner.top:
            break
        if s not in picks:
            picks.append(s)
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks:
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


class SalienceAllocator:
    """The ``top`` lowest (or highest) salience scores among screened names, held inside a band."""

    id = "M0192"

    def lookback(self, params: Any) -> int:
        return salience_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: ReturnGrid | None, data_date: date, held: frozenset[str],
                 p: SalienceParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        sc = scores(grid, [r.symbol for r in rows], data_date, p)
        return choose(history, rows, sc, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_grid(history, p.market), data_date, held, p)

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
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, held, p)


SALIENCE = SalienceAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)
N40 = FactorParams(rank="momentum", top=40, trend=TREND)
N20_NOSW = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: SalienceParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0192-{suffix}", family="M0192", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SALIENCE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0192",
    name=("Stocks whose bad days stood out: buy the members whose recent losses looked worst next "
          "to the market, sell the ones whose gains stood out"),
    family="stock-salience",
    source_kind="paper",
    source_ref=("Cosemans & Frehen (2021), Salience theory and stock prices: Empirical evidence, "
                "JFE 140, 460-483"),
    hypothesis=(
        "Salience theory (Bordalo, Gennaioli, Shleifer) says investors overweight a stock's "
        "returns that stand out most against the market's on the same day. A stock whose biggest "
        "stand-out days last month were gains gets overbought and earns less next month; one whose "
        "stand-out days were losses gets oversold and earns more. Cosemans and Frehen (2021) build "
        "the salience score from the past month's daily returns against the equal-weighted market "
        "and find the low-salience (salient-downside) stocks beat the high ones in US stocks "
        "1926-2015, not explained by reversal, lottery demand or news. Published 2021, so the whole "
        "dev window is before publication, but their sample covers it, so this is in-sample for the "
        "paper. Build: each month, among F4-screened members, the salience-weighted return "
        "covariance from the last 21 daily close-to-close returns against the equal-weighted "
        "screen average (theta 0.1, delta 0.7, the paper's values); hold the 20 most negative "
        "scores, equal 5% slots, monthly, keeping a holding while it ranks inside the top 40 "
        "(a band to cut turnover), unfilled slots in SPY, behind the SPY 200-day switch. "
        "Fractional shares at Gotrade's real fees (monthly-hold-frac-gotrade) on the owner's "
        "monthly top-up. Arms: S-N40 (40 names, band 80), S-N20-NOSW (no switch). Controls in the "
        "same pool: HIGH-N20, the paper's losing end (most positive salience), which should trail "
        "the main book clearly; REV-N20, a plain one-month reversal book (lowest 21-day return) on "
        "the identical screen, band, slots and switch, so salience can be told apart from reversal. "
        "Success: beats SPY TR with worst fall <= 25%, PF >= 1.3, a majority of walk-forward folds "
        "and a positive 2009-2015 edge, with a clear gap over both controls."
    ),
    expected_failure=(
        "Salience-downside stocks are mostly last month's losers, so the low-salience book may be "
        "short-term reversal under another name: the lab's reversal books (the plain bounce book "
        "and the standardised residual bounce book) both trailed SPY on the deposits, the best at "
        "6.9% a year vs 7.2%, fell 28-35% at worst and lagged in 2009-2015. Monthly turnover on 20 "
        "small slots at Gotrade's minimum fees eats a one-month effect the paper measured gross of "
        "costs; the band helps only if a name stays salient-low for more than a month, which a "
        "one-month signal rarely does. The paper's long-short spread lives largely in the short "
        "leg (overbought high-salience stocks), which a long-only book cannot trade. In crashes "
        "the stocks with stand-out losses keep falling and the 200-day switch reacts late, so the "
        "no-switch arm may fall well past 25%. Equal slots in index members lean small against "
        "SPY's big-company drift (insight 91), which hurts most in 2013-2015."
    ),
    candidates=(
        _v("S-N20", SalienceParams(N20, keep=40),
           "20 most negative salience scores over 21 sessions, held while inside the top 40"),
        _v("S-N40", SalienceParams(N40, keep=80),
           "Same signal, 40 names, band 80: does width tame the falling-knife months?"),
        _v("S-N20-NOSW", SalienceParams(N20_NOSW, keep=40),
           "The main book without the SPY 200-day switch, as the paper trades it"),
        _v("HIGH-N20", SalienceParams(N20, keep=40, side="high"),
           "Control: the paper's losing end, the 20 most positive salience scores"),
        _v("REV-N20", SalienceParams(N20, keep=40, signal="reversal"),
           "Control: plain one-month reversal on the same screen, band, slots and switch"),
    ),
    seen_keys=(
        "concept:salience-theory",
        "concept:salience-weighted-return",
    ),
)
