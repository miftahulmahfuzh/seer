"""M0028 — A short-term bounce book: buy last month's biggest fallers among calm, uptrending stocks.

Source: Jegadeesh (1990), Evidence of predictable behavior of security returns, J. Finance 45(3);
Lehmann (1990), Fads, martingales and market efficiency, QJE 105(1); Blitz, Huij, Lansdorp &
Verbeek (2013), Short-term residual reversal, J. Financial Markets 16(3).
Idea: one-month reversal is the classic factor whose payoff runs against momentum's. Last month's
biggest fallers, measured against the market (the residual), tend to bounce the next month, and
momentum's worst months -- sharp rebounds of losers -- are reversal's best. Blitz et al. show the
residual version keeps most of the premium while shedding the factor bets that make plain
reversal crash. Restricting the fallers to calm stocks still above their own 200-day average
aims the book at liquidity-driven dips in healthy names rather than at companies breaking down.

On data date d, inside F4's liquidity and membership screen and behind its SPY-200 trend gate:

    * ``calm`` keeps the calmer ``calm_frac`` of the screened names by 60-day volatility;
    * ``sma_n`` keeps names whose close is above their own ``sma_n``-day average (None = off);
    * the score is the stock's return over the last ``rev_n`` sessions, either raw
      (``signal="raw"``) or net of beta times the market's return (``signal="residual"``), with
      beta fitted over the ``beta_n`` sessions before the formation window;
    * the ``top`` most negative scores are held, equal weight, for a month.

Every piece reads only bars dated <= d. The return grid is M0007's, so a day counts only when the
stock has back-to-back bars on the market's calendar.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
    ReturnGrid,
    build_grid,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart, target_from_close
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

ADDED = date(2026, 10, 9)
MIN_FRAC = 0.8  # a window needs this share of usable daily returns before a name is scored

Signal = Literal["residual", "raw"]
_SIGNALS: tuple[str, ...] = ("residual", "raw")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class RevParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; the rest picks the fallers.

    ``inner.rank`` never selects here; keeping it at ``"momentum"`` makes the screened universe
    identical to F4-MOM12-N<top>-TREND's and M0007's, name for name.
    """

    inner: FactorParams
    signal: Signal = "residual"
    rev_n: int = 21  # sessions in the formation window (one month)
    beta_n: int = 252  # sessions before the formation window the beta is fitted on
    calm_frac: Decimal = Decimal("0.5")  # keep the calmer share of the screened names (1 = off)
    sma_n: int | None = 200  # keep names above their own sma_n-day average (None = off)
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.signal, str) or self.signal not in _SIGNALS:
            raise ValueError(f"signal must be one of {_SIGNALS}, got {self.signal!r}")
        for name in ("rev_n", "beta_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.rev_n < 5:
            raise ValueError(f"rev_n must be >= 5, got {self.rev_n}")
        if self.beta_n < 20:
            raise ValueError(f"beta_n must be >= 20, got {self.beta_n}")
        if not isinstance(self.calm_frac, Decimal):
            raise TypeError(f"calm_frac must be a Decimal, got {type(self.calm_frac).__name__}")
        if not self.calm_frac.is_finite() or not 0 < self.calm_frac <= 1:
            raise ValueError(f"calm_frac must be in (0, 1], got {self.calm_frac}")
        if self.sma_n is not None and (isinstance(self.sma_n, bool) or not isinstance(self.sma_n, int)
                                       or self.sma_n < 2):
            raise ValueError(f"sma_n must be None or an int >= 2, got {self.sma_n!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "signal": self.signal,
            "rev_n": str(self.rev_n),
            "beta_n": str(self.beta_n),
            "calm_frac": str(self.calm_frac),
            "sma_n": "none" if self.sma_n is None else str(self.sma_n),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> RevParams:
    if not isinstance(params, RevParams):
        raise TypeError(f"params must be RevParams, got {type(params).__name__}")
    return params


def rev_lookback(params: RevParams) -> int:
    """Bars through d the decision needs: the screen's, the beta and formation windows', the SMA's."""
    need = max(factor_lookback(params.inner), params.beta_n + params.rev_n + 2)
    if params.sma_n is not None:
        need = max(need, params.sma_n)
    return need


# --------------------------------------------------------------------------- the signal


def reversal_scores(
    grid: ReturnGrid, symbols: list[str], data_date: date, params: RevParams
) -> dict[str, float]:
    """Each symbol's formation-window return on ``data_date`` (raw or net of beta x market).

    Lower is a bigger fall. Absent = too little of a window to be scored. Reads only calendar
    columns at or before ``data_date``.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    f0 = j - params.rev_n + 1
    b_end = f0 - 1
    b0 = b_end - params.beta_n + 1
    if f0 < 0 or (params.signal == "residual" and b0 < 0):
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

    if params.signal == "raw":
        score = np.where(ok_w, rw, 0.0).sum(axis=1)
    else:
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
            resid = rw - beta[:, None] * mw[None, :]
        score = np.where(ok_w, resid, 0.0).sum(axis=1)

    live = enough & np.isfinite(score)
    return {names[k]: float(score[k]) for k in (int(v) for v in np.flatnonzero(live))}


def screen(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           params: RevParams) -> list[FactorRow]:
    """The calm, uptrending part of the screened rows (symbol order kept)."""
    kept = [r for r in rows if r.symbol not in EXCLUDED]
    if params.calm_frac < 1 and kept:
        cut = math.ceil(float(params.calm_frac) * len(kept))
        calm = {r.symbol for r in sorted(kept, key=lambda r: (r.vol, r.symbol))[:cut]}
        kept = [r for r in kept if r.symbol in calm]
    if params.sma_n is None:
        return kept
    out: list[FactorRow] = []
    for r in kept:
        h = history.get(r.symbol)
        i = None if h is None else h.index_of(data_date)
        if h is None or i is None or i + 1 < params.sma_n:
            continue
        window = h.close[i + 1 - params.sma_n : i + 1]
        if np.all(np.isfinite(window)) and float(window[-1]) > float(window.mean()):
            out.append(r)
    return out


def targets_from_scores(rows: list[FactorRow], scores: Mapping[str, float],
                        params: RevParams) -> tuple[Target, ...]:
    """F4's weighting and pricing applied to the ``top`` most negative scores."""
    scorable = [r for r in rows if r.symbol in scores]
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


class ShortTermReversalAllocator:
    """Last month's biggest fallers among calm, uptrending screened names, held for a month.

    Held symbols get no special treatment: the targets are exactly the new set, so a name that
    leaves it is signal-exited by the book engine.
    """

    id = "M0028"

    def lookback(self, params: Any) -> int:
        return rev_lookback(_check(params))

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

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: ReturnGrid | None, data_date: date, params: RevParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        kept = screen(history, rows, data_date, params)
        if not kept:
            return ()
        scores = reversal_scores(grid, [r.symbol for r in kept], data_date, params)
        return targets_from_scores(kept, scores, params)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_grid(history, p.market), data_date, p)

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
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, p)


REVERSAL = ShortTermReversalAllocator()

CALM_RESID = RevParams(N20)
RM_RAW = ResidParams(N20, scaled=False)  # M0032's ranking: M0007-N20-RAW


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0028-{suffix}", family="M0028", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0028",
    name="A short-term bounce book: buy last month's biggest fallers among calm, uptrending stocks",
    family="stock-short-term-reversal",
    source_kind="paper",
    source_ref=(
        "Jegadeesh (1990), J. Finance 45(3); Lehmann (1990), QJE 105(1); Blitz, Huij, Lansdorp & "
        "Verbeek (2013), Short-term residual reversal, J. Financial Markets 16(3)"
    ),
    parent_id="M0024",
    hypothesis=(
        "M0024 showed a same-month seasonal book moves with the momentum books (monthly "
        "correlation 0.8), so blending it with residual momentum cut nothing. One-month reversal "
        "is the classic factor whose payoff runs against momentum's: last month's biggest fallers "
        "against the market bounce the next month, and momentum's bad months (sharp rebounds of "
        "losers, 2009, 2002-03) are reversal's good ones. Blitz et al. show the residual version "
        "keeps the premium while shedding the market and factor bets that make plain reversal "
        "crash. Restricting to the calmer half of F4's screened universe by 60-day volatility, "
        "and to names above their own 200-day average, aims the book at liquidity-driven dips in "
        "healthy, large names rather than at companies breaking down. Each month, behind the "
        "SPY-200 gate, CALM-RESID holds the 20 most negative one-month residual returns, equal "
        "weight, in fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade with "
        "the owner's monthly top-up. CALM-RAW ranks on the plain one-month return (does taking "
        "out the market matter?); PLAIN-RESID drops both the calm and the uptrend filters (do the "
        "filters matter?); CALM-RESID-N10 holds the 10 deepest fallers (is the bounce "
        "concentrated in the extremes?). BLEND-RM runs CALM-RESID 50/50 with the real-fee residual "
        "momentum book and is a correlation readout only: the residual-momentum family has a "
        "test-failed member, so the blend can never be promoted. Success for the standalone book "
        "is beating total-return SPY on the owner's deposits with a worst fall under 20%; success "
        "for the idea is a monthly correlation with the residual-momentum book well under 0.5."
    ),
    expected_failure=(
        "Turnover near 100% a month at Gotrade's real fee schedule -- a 5M IDR top-up split 20 "
        "ways is a slot of about 15 USD, which pays several tenths of a percent a side -- eats "
        "most of a large-cap reversal premium that was already small after the 1990s (the "
        "literature finds it decayed sharply in big liquid names once decimal ticks narrowed "
        "spreads in 2001). The book then lags SPY by the fee drag. The second failure is August "
        "1998 and late 2008, when fallers kept falling: a calm, uptrending name that drops hard in "
        "a month is often the first casualty of a regime turn, and the SPY gate reacts too late. "
        "Third, the calm-and-uptrend filters may themselves lean the book toward low-volatility "
        "quality, so its correlation with momentum ends up higher than the textbook negative."
    ),
    candidates=(
        _v("CALM-RESID", REVERSAL, CALM_RESID,
           "20 most negative one-month residual returns among calm (lower-half vol), above-SMA200 names"),
        _v("CALM-RAW", REVERSAL, RevParams(N20, signal="raw"),
           "Same filters, ranked on the plain one-month return: does removing the market matter?"),
        _v("PLAIN-RESID", REVERSAL, RevParams(N20, calm_frac=Decimal("1"), sma_n=None),
           "No calm or uptrend filter: one-month residual reversal across F4's whole screen"),
        _v("CALM-RESID-N10", REVERSAL,
           RevParams(FactorParams(rank="momentum", top=10, trend=("SPY", 200))),
           "Only the 10 deepest calm, uptrending fallers: is the bounce in the extremes?"),
        _v("BLEND-RM", BLEND,
           BlendParams((BlendPart(REVERSAL, CALM_RESID, Decimal("0.5")),
                        BlendPart(RESIDMOM, RM_RAW, Decimal("0.5")))),
           "Correlation readout only: CALM-RESID 50/50 with the real-fee raw residual momentum book"),
    ),
    seen_keys=(
        "concept:short-term-reversal",
        "concept:residual-reversal",
        "concept:one-month-reversal",
        "doi:10.1016/j.finmar.2012.05.001",
    ),
)
