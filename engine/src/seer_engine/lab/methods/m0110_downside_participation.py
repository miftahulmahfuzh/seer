"""M0110 — Companies that sit out the market's bad days: rank on how much of the market's falls a
stock actually joined in.

Source: a variation of M0108 (the stocks whose own worst twelve-month fall was mildest), which was
rejected because its book still fell 42.5%. The measure it ranked on mixes two different things --
how much a stock fell because the whole market fell, and how much it fell on its own account -- and
in 2008 the first term swamped the second, so the rank turned to noise in exactly the moment it was
hired for. This method splits those two terms apart and ranks on each of them separately, so the
verdict can say which half (if either) buys shelter. The published form of the market half is Ang,
Chen & Xing (2006), "Downside Risk", Review of Financial Studies 19(4), 1191-1239; the practitioner
form is the plain downside capture ratio.

The two halves, both measured over the ``window`` daily returns ending at d, on SPY's calendar:

* **downside participation** (``side="shelter"`` / ``"exposed"``). Keep only the sessions on which
  SPY closed down, and take the stock's summed return on those sessions divided by SPY's summed
  return on the same sessions. 0.6 means "when the market fell, this name gave back about three
  fifths of it"; a negative value means it rose while the market fell. ``"shelter"`` holds the
  lowest, ``"exposed"`` the highest -- the paired control, which must fall harder or the signal is
  not reading what it claims to.
* **the up/down asymmetry** (``side="spread"``). Upside participation measured the same way on
  SPY's up sessions, minus the downside participation, highest first. A stock that merely does
  nothing in both directions is cash with extra fees, and the plain shelter rank cannot tell it
  apart from one that genuinely protects; this rank can.
* **idiosyncratic fall** (``side="idio"``). The other half of M0108's mixed measure, isolated: fit
  the market model on the window (OLS of the stock's daily returns on SPY's), cumulate the
  residuals, and take the worst peak-to-trough fall of that cumulative residual. This is the part
  of a company's drawdown that was its own doing, with the market's part removed. Lowest first.

Together, M0108's rank = (roughly) these two halves added. If neither half alone produces a book
that falls materially less than M0108's 42.5%, that is decisive evidence that the real-money
drawdown bar cannot be reached by stock selection alone, which closes the whole line.

The frame is F4's, inherited from M0108 unchanged -- point-in-time S&P 500 / Nasdaq-100 members,
the $5 price and 20M-dollar volume screen, monthly re-picks, equal weights, fractional shares at
Gotrade's real fees on ``monthly-hold-frac-gotrade`` -- with **no trend gate**: the question is
whether shelter can be bought by selection alone, and a market switch would confound it.

Assumptions, written before the run:

- The reserved idea named a sixth variant: the same twenty names weighted by dollar volume rather
  than equally, to measure the equal-weighting handicap on this book directly. M0122 ran that
  measurement an hour before this method was written, across three different parents, and closed
  it: trading-value weighting cost 0.4 to 1.2 points of return a year on every one of them and cost
  DSR on every one. Spending a variant slot to re-measure a settled number would waste it, so the
  slot goes to ``IDIO20`` instead, which answers the question this method actually exists to
  answer: which half of M0108's signal, if either, was the useful one.
- The idea described the asymmetry rank as up-participation *divided by* down-participation. It is
  computed here as up *minus* down. The ratio's denominator passes through zero exactly for the
  names that shelter best, which is the most interesting part of the cross-section, and near that
  point the ratio explodes and then flips sign -- it would rank the best names worst. The
  difference is monotone in the right direction everywhere and needs no guard.
- Returns are plain total-price returns on split- and dividend-adjusted bars, so an ex-dividend day
  is not read as a fall. A daily return is used only when it spans exactly one session of SPY's own
  calendar (``build_grid``), so a halted or missing bar drops that observation rather than
  stretching a return across a gap.
- A name is scored only when it has at least 80% of the window's down sessions (and, for the
  asymmetry rank, of its up sessions too), and at least 20 of them. ``idio`` wants 80% of the whole
  window. Everything else is unscorable and simply not held.
- No skip month. Downside participation is a risk measure, not a return signal, so there is no
  momentum-reversal reason to hold the last month out of the estimate.
- ``inner.rank`` is unused: this allocator re-ranks every eligible row itself. It is kept at
  ``"momentum"`` so the recorded screen reads identically to M0108's and to every other F4-framed
  method; the momentum column still gates eligibility through its finiteness.
- Reads only bars dated <= d.
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
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20_NOTREND,
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
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
)

ADDED = date(2026, 10, 14)

MIN_FRAC = 0.8  # share of the window's qualifying sessions a name needs before it is scored
MIN_DAYS = 20  # and at least this many, whatever the window holds
MIN_MOVE = 1e-3  # the summed market move a participation ratio divides by must be at least this

Side = Literal["shelter", "exposed", "spread", "idio"]
_SIDES: tuple[str, ...] = ("shelter", "exposed", "spread", "idio")


@dataclass(frozen=True, slots=True)
class CaptureParams:
    """``inner`` is F4's screen, book size and weighting; the rest is the ranking key."""

    inner: FactorParams
    side: Side = "shelter"
    window: int = 252  # daily returns in the estimate (252 = one year)
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if isinstance(self.window, bool) or not isinstance(self.window, int):
            raise TypeError(f"window must be an int, got {type(self.window).__name__}")
        if self.window < 60:
            raise ValueError(f"window must be >= 60, got {self.window}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "window": str(self.window), "market": self.market}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> CaptureParams:
    if not isinstance(params, CaptureParams):
        raise TypeError(f"params must be CaptureParams, got {type(params).__name__}")
    return params


def capture_lookback(params: CaptureParams) -> int:
    """Bars each read symbol needs through d: F4's screen, or the window of returns if longer."""
    return max(factor_lookback(params.inner), params.window + 1)


def _need(total: int) -> int:
    """How many usable sessions of a ``total``-session pool a name needs before it is scored."""
    return max(MIN_DAYS, math.ceil(MIN_FRAC * total))


def _participation(
    r: np.ndarray, m: np.ndarray, mask: np.ndarray, total: int
) -> tuple[np.ndarray, np.ndarray]:
    """Per-row (participation, usable) over the ``mask`` sessions.

    Participation is the row's summed return over the sessions it actually has, divided by the
    market's summed return over those *same* sessions, so a row with gaps is not compared against
    a market sum it never experienced.
    """
    ok = np.isfinite(r) & mask[None, :]
    num = np.where(ok, r, 0.0).sum(axis=1)
    den = np.where(ok, np.broadcast_to(m, r.shape), 0.0).sum(axis=1)
    usable = (ok.sum(axis=1) >= _need(total)) & (np.abs(den) >= MIN_MOVE)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(usable, num / np.where(usable, den, 1.0), np.nan)
    return out, usable & np.isfinite(out)


def _idio_drawdown(r: np.ndarray, m: np.ndarray, ok: np.ndarray, window: int
                   ) -> tuple[np.ndarray, np.ndarray]:
    """Per-row (worst fall of the cumulative market-model residual, usable).

    The market model is fitted by OLS over the usable sessions of the window; the residual series
    is cumulated from zero and the answer is the deepest peak-to-trough fall of that curve. 0.25
    means "the part of this name's path that the market does not explain was 25 points below its
    own best at the worst moment".
    """
    x = np.broadcast_to(m, r.shape)
    n = ok.sum(axis=1).astype(np.float64)
    yz = np.where(ok, r, 0.0)
    xz = np.where(ok, x, 0.0)
    sx, sy = xz.sum(axis=1), yz.sum(axis=1)
    sxx, sxy = (xz * xz).sum(axis=1), (xz * yz).sum(axis=1)
    den = n * sxx - sx * sx
    fitted = np.isfinite(den) & (den != 0.0) & (n >= float(_need(window)))
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.where(fitted, (n * sxy - sx * sy) / np.where(fitted, den, 1.0), np.nan)
        alpha = np.where(fitted, (sy - beta * sx) / np.where(n > 0.0, n, 1.0), np.nan)
        resid = np.where(ok, r - alpha[:, None] - beta[:, None] * x, 0.0)
    equity = np.concatenate([np.zeros((r.shape[0], 1)), np.cumsum(resid, axis=1)], axis=1)
    fall = np.max(np.maximum.accumulate(equity, axis=1) - equity, axis=1)
    usable = fitted & np.isfinite(beta) & np.isfinite(alpha) & np.isfinite(fall)
    return fall, usable


def capture_scores(
    grid: ReturnGrid, symbols: list[str], data_date: date, params: CaptureParams
) -> dict[str, float]:
    """Each symbol's score on ``data_date``, **lowest ranked first** (absent = not scorable).

    Reads only calendar columns at or before ``data_date``.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    w0 = j - params.window + 1
    if w0 < 1:  # column 0 of the grid can hold no return
        return {}
    mrow = grid.row.get(params.market)
    if mrow is None:
        return {}
    names = [s for s in symbols if s in grid.row and s not in EXCLUDED]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    m = grid.rets[mrow, w0 : j + 1]
    r = grid.rets[idx, w0 : j + 1]
    finite = np.isfinite(m)

    if params.side == "idio":
        score, live = _idio_drawdown(r, m, np.isfinite(r) & finite[None, :], params.window)
    else:
        down = finite & (m < 0.0)
        n_down = int(down.sum())
        if n_down < MIN_DAYS:
            return {}
        dn, live = _participation(r, m, down, n_down)
        if params.side == "shelter":
            score = dn
        elif params.side == "exposed":
            score = -dn
        else:  # spread: the most asymmetric names first, so negate (up - down)
            up = finite & (m > 0.0)
            n_up = int(up.sum())
            if n_up < MIN_DAYS:
                return {}
            upc, live_up = _participation(r, m, up, n_up)
            live = live & live_up
            score = -(upc - dn)
    good = live & np.isfinite(score)
    return {names[k]: float(score[k]) for k in (int(v) for v in np.flatnonzero(good))}


def targets_from_scores(
    rows: list[FactorRow], scores: Mapping[str, float], params: CaptureParams
) -> tuple[Target, ...]:
    """F4's weighting and pricing applied to the ``top`` lowest scores; ties by symbol ascending."""
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


@dataclass(frozen=True, slots=True, eq=False)
class CapturePrepared:
    """F4's rolling feature columns plus one return grid per market symbol, built on first use."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    grids: dict[str, ReturnGrid | None] = field(default_factory=dict, repr=False)

    def grid(self, market: str) -> ReturnGrid | None:
        if market not in self.grids:
            self.grids[market] = build_grid(self.history, market)
        return self.grids[market]


class DownsideParticipationAllocator:
    """F4's screen and book, ranked on how much of the market's falls each member joined in.

    No trend gate: the book is always invested. Held symbols get no special treatment -- a name
    that leaves the chosen set is signal-exited by the book engine.
    """

    id = "M0110"

    def lookback(self, params: Any) -> int:
        return capture_lookback(_check(params))

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

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = factor_rows(history, members, data_date, p.inner)
        if not rows:
            return ()
        grid = build_grid(history, p.market)
        if grid is None:
            return ()
        return targets_from_scores(rows, capture_scores(grid, [r.symbol for r in rows], data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> CapturePrepared:
        return CapturePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapturePrepared):
            raise TypeError(f"prepared must be CapturePrepared, got {type(prepared).__name__}")
        p = _check(params)
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        grid = prepared.grid(p.market)
        if grid is None:
            return ()
        return targets_from_scores(rows, capture_scores(grid, [r.symbol for r in rows], data_date, p), p)


CAPTURE = DownsideParticipationAllocator()

N20 = N20_NOTREND  # F4's screen, 20 equal slots, always invested
N40 = replace(N20_NOTREND, top=40)


def _v(suffix: str, params: CaptureParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0110-{suffix}", family="M0110", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CAPTURE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0110",
    name=("Companies that sit out the market's bad days: rank on how much of the market's falls a "
          "stock actually joined in"),
    family="stock-downside-participation",
    source_kind="variation",
    source_ref=(
        "variation of M0108 (own worst twelve-month fall), splitting its signal into a market "
        "half and an own-account half; Ang, Chen and Xing (2006), 'Downside Risk', Review of "
        "Financial Studies 19(4), 1191-1239 is the published form of the market half"
    ),
    parent_id="M0108",
    hypothesis=(
        "M0108 ranked big index members on their own worst twelve-month fall and the book still "
        "fell 42.5%, because that measure mixes two things: how much a stock fell because the "
        "whole market fell, and how much it fell on its own account. In 2008 the first term "
        "swamped the second, so the rank turned to noise in exactly the moment it was hired for, "
        "and the steadiest names through 2006-07 were banks and utilities. This separates the two "
        "terms and ranks on each alone. For each F4-screened member, over the past 252 sessions "
        "take only the sessions on which SPY closed down, and measure the stock's downside "
        "participation: the sum of its returns on those days divided by the sum of SPY's returns "
        "on those days. Hold the 20 lowest at 5% each, equal weighted, monthly, fractional shares "
        "at Gotrade's real fees, no market switch -- the point is to find out whether shelter can "
        "be bought by selection alone, and a switch would confound it. Variants: DP20 and DP40; "
        "DP20-UP, which ranks on upside participation minus downside participation, because a "
        "stock that simply does nothing in both directions is cash with extra fees; HI20, the "
        "paired control holding the 20 highest downside participants, which must fall harder; and "
        "IDIO20, which holds the 20 whose *market-model residual* fell least -- M0108's other "
        "half, isolated, so the verdict can attribute any result to one term or the other. "
        "Success: a DP variant beats SPY TR on deposit-matched money, the control falls visibly "
        "harder, AND -- the condition M0108 failed -- the worst fall is materially under the 42% "
        "that ranking on the raw fall produced. Even a book that trails SPY but genuinely halves "
        "the crash would be the first evidence in this lab that shelter is purchasable by "
        "selection."
    ),
    expected_failure=(
        "Downside participation is close to beta measured on half the sample, and low-beta books "
        "trail badly through growth runs, so the likeliest outcome is 2 to 3 points a year below "
        "SPY through 2009-2015 with a fall still well over the 25% real-money bar. The published "
        "form dates from 2006 and the low-risk anomaly beside it has been crowded since, so even "
        "a clean dev-window edge should be expected to fade out of sample. If the fall does not "
        "improve on M0108's 42.5% on either half of the split -- neither the market term nor the "
        "idiosyncratic one -- that is the decisive evidence that the drawdown bar cannot be "
        "reached by stock selection at all, which is worth knowing and should close the whole "
        "line rather than spawn another variation of it."
    ),
    candidates=(
        _v("DP20", CaptureParams(N20, side="shelter"),
           "The 20 members that joined in least of the market's down days: the book"),
        _v("DP40", CaptureParams(N40, side="shelter"),
           "The same rank over 40 slots: broader, less single-stock risk, same signal"),
        _v("DP20-UP", CaptureParams(N20, side="spread"),
           "The 20 most asymmetric: most of the up days, least of the down days"),
        _v("HI20", CaptureParams(N20, side="exposed"),
           "The 20 that joined in most of the market's down days: the control, must fall harder"),
        _v("IDIO20", CaptureParams(N20, side="idio"),
           "The 20 whose own-account path fell least once the market's part is removed"),
    ),
    seen_keys=(
        "concept:downside-participation-capture-ratio",
        "concept:up-down-capture-asymmetry",
        "concept:idiosyncratic-drawdown-cross-section",
    ),
)
