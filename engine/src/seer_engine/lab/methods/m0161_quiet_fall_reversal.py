"""M0161 — Quiet fallers bounce, loud fallers keep falling: residual reversal split by the fall's trading volume.

Source: Conrad, Hameed & Niden (1994), Volume and autocovariances in short-horizon individual
security returns, Journal of Finance 49(4) 1305-1329; Da, Liu & Schaumburg (2014), A closer look
at the short-term return reversal, Management Science 60(3) 658-674. Variation of M0158.
Idea: M0158 ranked last fortnight's fallers by their market-model residual, scaled by the stock's
own swing, and lost to SPY because too many of its fallers kept falling (2007). The literature's
answer is *why* the stock fell. A fall on thin trading is more likely someone leaning on a quiet
book (a liquidity shock that is paid back); a fall on heavy trading is more likely news the market
is still digesting, and it continues. So M0158's exact score is kept and the pool is split by the
fall's volume: QUIET holds only fallers whose formation-window volume is below their own normal,
LOUD only those above it. M0158-Z10-N20 is the unsplit control, already recorded at the same
screen, gate, slots and fees, so one run measures the split three ways.

On data date d, inside F4's liquidity and membership screen and behind its SPY-200 switch:

    * the score is M0158's: the formation residual over the last ``rev_n`` sessions divided by
      sigma*sqrt(rev_n), the fit and sigma from the ``beta_n`` sessions before the window;
    * the volume ratio is the stock's mean daily share volume over the same ``rev_n`` sessions
      divided by its mean daily share volume over the same ``beta_n`` sessions the fit used;
    * ``side="quiet"`` keeps names with ratio < ``cut``, ``"loud"`` names with ratio > ``cut``; a
      ratio exactly at the cut counts on both sides (see ``split_scores``);
    * the ``top`` most negative scores among those kept are held, equal weight, for a month.

Why share volume and not dollar volume: the fall itself shrinks dollar volume, so a dollar ratio
would call most fallers quiet for a reason that has nothing to do with how hard they were traded.
Share volume is assumed split-adjusted in the store, as the prices are; a split inside the
baseline year would otherwise distort the ratio for that one name for a year.

Why mean against mean, not mean against median: both windows are then measured the same way, so
the cut at 1.0 means "traded less than usual" without a skew bias that would push almost every
stock into the loud side (a day-volume distribution's mean sits well above its median).

Every piece reads only calendar columns at or before d.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import ResidPrepared, ReturnGrid, build_grid
from seer_engine.lab.methods.m0158_standardised_residual_reversal import (
    N20,
    MIN_FRAC,
    ZRevParams,
    targets_from_scores,
    zrev_lookback,
    zrev_scores,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import FactorRow, factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 17)

Side = Literal["quiet", "loud"]
_SIDES: tuple[str, ...] = ("quiet", "loud")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class QuietParams:
    """``zrev`` is M0158's whole signal and book; ``side`` and ``cut`` split it by volume."""

    zrev: ZRevParams
    side: Side = "quiet"
    cut: Decimal = Decimal("1")  # formation-window volume over baseline volume

    def __post_init__(self) -> None:
        if not isinstance(self.zrev, ZRevParams):
            raise TypeError(f"zrev must be ZRevParams, got {type(self.zrev).__name__}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if not isinstance(self.cut, Decimal) or not self.cut > 0:
            raise ValueError(f"cut must be a positive Decimal, got {self.cut!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "cut": str(self.cut)}
        for k, v in self.zrev.as_dict().items():
            out[f"zrev.{k}"] = v
        return out


def _check(params: object) -> QuietParams:
    if not isinstance(params, QuietParams):
        raise TypeError(f"params must be QuietParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- volume


def build_volume_grid(history: Mapping[str, History], grid: ReturnGrid) -> np.ndarray:
    """Share volume laid on ``grid``'s calendar and row order; NaN where no usable bar."""
    cal = grid.dates
    ncal = len(cal)
    vols = np.full((len(grid.symbols), ncal), np.nan, dtype=np.float64)
    for k, symbol in enumerate(grid.symbols):
        h = history.get(symbol)
        if h is None or len(h) == 0:
            continue
        pos = np.searchsorted(cal, h.dates)
        inside = pos < ncal
        safe = np.where(inside, pos, 0)
        on_cal = inside & (cal[safe] == h.dates)
        good = on_cal & np.isfinite(h.volume) & (h.volume > 0.0)
        vols[k, safe[good]] = h.volume[good]
    vols.setflags(write=False)
    return vols


def volume_ratios(grid: ReturnGrid, vols: np.ndarray, symbols: list[str], data_date: date,
                  params: ZRevParams) -> dict[str, float]:
    """Mean formation-window volume over mean baseline volume, per symbol; absent = too thin."""
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    f0 = j - params.rev_n + 1
    b_end = f0 - 1
    b0 = b_end - params.beta_n + 1
    if b0 < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    fw = vols[idx, f0 : j + 1]
    bw = vols[idx, b0 : b_end + 1]
    nf = np.isfinite(fw).sum(axis=1)
    nb = np.isfinite(bw).sum(axis=1)
    enough = (nf >= max(3, math.ceil(MIN_FRAC * params.rev_n))) & (
        nb >= max(3, math.ceil(MIN_FRAC * params.beta_n)))
    with np.errstate(divide="ignore", invalid="ignore"):
        fm = np.where(np.isfinite(fw), fw, 0.0).sum(axis=1) / nf
        bm = np.where(np.isfinite(bw), bw, 0.0).sum(axis=1) / nb
        ratio = fm / bm
    live = enough & np.isfinite(ratio) & (bm > 0.0)
    return {names[k]: float(ratio[k]) for k in (int(v) for v in np.flatnonzero(live))}


def split_scores(scores: Mapping[str, float], ratios: Mapping[str, float],
                 params: QuietParams) -> dict[str, float]:
    """The scores of the names on ``params.side`` of the volume cut; no ratio = not scored.

    A ratio exactly equal to the cut is kept on both sides. Real daily volume never lands two
    averages of hundreds of different numbers on exactly 1.0, so this decides nothing in a run;
    the synthetic contract market trades a constant volume every day, and there it lets either
    side be exercised end to end instead of one of them always targeting nothing.
    """
    cut = float(params.cut)
    if params.side == "quiet":
        return {s: v for s, v in scores.items() if s in ratios and ratios[s] <= cut}
    return {s: v for s, v in scores.items() if s in ratios and ratios[s] >= cut}


# --------------------------------------------------------------------------- the allocator


@dataclass
class QuietPrepared:
    """M0158's prepared columns plus one volume grid per market calendar, built on first use."""

    resid: ResidPrepared = field(repr=False)
    vgrids: dict[str, np.ndarray | None] = field(default_factory=dict, repr=False)

    def volumes(self, market: str) -> np.ndarray | None:
        if market not in self.vgrids:
            grid = self.resid.grid(market)
            self.vgrids[market] = (None if grid is None
                                   else build_volume_grid(self.resid.history, grid))
        return self.vgrids[market]


class QuietFallReversalAllocator:
    """M0158's most negative standardised residuals, only on one side of the volume cut.

    Held symbols get no special treatment: the targets are exactly the new set, so a name that
    leaves it is signal-exited by the book engine.
    """

    id = "M0161"

    def lookback(self, params: Any) -> int:
        return zrev_lookback(_check(params).zrev)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).zrev
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

    def _targets(self, rows: list[FactorRow], grid: ReturnGrid | None, vols: np.ndarray | None,
                 data_date: date, params: QuietParams) -> tuple[Target, ...]:
        if not rows or grid is None or vols is None:
            return ()
        symbols = [r.symbol for r in rows]
        scores = zrev_scores(grid, symbols, data_date, params.zrev)
        ratios = volume_ratios(grid, vols, symbols, data_date, params.zrev)
        return targets_from_scores(rows, split_scores(scores, ratios, params), params.zrev)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.zrev.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.zrev.inner)
        grid = build_grid(history, p.zrev.market)
        vols = None if grid is None else build_volume_grid(history, grid)
        return self._targets(rows, grid, vols, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> QuietPrepared:
        return QuietPrepared(ResidPrepared(history, prepare_factor(history)))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, QuietPrepared):
            raise TypeError(f"prepared must be QuietPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.resid.history, data_date, p.zrev.inner):
            return ()
        rows = prepared.resid.factor.rows_on(members, data_date, p.zrev.inner)
        return self._targets(rows, prepared.resid.grid(p.zrev.market),
                             prepared.volumes(p.zrev.market), data_date, p)


QUIET = QuietFallReversalAllocator()

Z10 = ZRevParams(N20, rev_n=10)
Z21 = ZRevParams(N20)


def _v(suffix: str, params: QuietParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0161-{suffix}", family="M0161", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=QUIET, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0161",
    name=("Quiet fallers bounce, loud fallers keep falling: one-month residual reversal only among "
          "big members whose fall came on below-normal trading volume"),
    family="stock-short-term-reversal",
    source_kind="variation",
    parent_id="M0158",
    source_ref=(
        "Conrad, Hameed & Niden 1994, Journal of Finance 49(4) 1305-1329 'Volume and "
        "autocovariances in short-horizon individual security returns'; Da, Liu & Schaumburg 2014, "
        "Management Science 60(3) 658-674 'A closer look at the short-term return reversal'"
    ),
    hypothesis=(
        "Published 1994 (and 2014 for the news/no-news split), so the volume split was public "
        "for the whole dev window. Conrad, Hameed & Niden find that weekly losers on LOW volume "
        "reverse while losers on HIGH volume do not; Da, Liu & Schaumburg find reversal lives in "
        "the part of the fall that is not news. The standardised-residual bounce book (M0158) "
        "earned 6.9% a year on the owner's deposits with a two-week window vs SPY's 7.2%, and its "
        "worst year (2007) came from fallers that kept falling. Keeping its score exactly -- the "
        "10-session market-model residual divided by the stock's own residual swing, the fit on "
        "the 252 sessions before the window -- and holding only names whose mean share volume "
        "over the window is below their mean over that year should remove the news-driven "
        "fallers and keep the bounces. Book: liquid index-member screen, SPY-200 switch, 20 equal "
        "fractional slots, monthly re-pick at Gotrade's real fees (monthly-hold-frac-gotrade) on "
        "the owner's deposits. Arms: QUIET-Z10-N20 (main), LOUD-Z10-N20 (the same score on the "
        "heavy-volume fallers only: the literature says it should do worst), QUIET-Z21-N20 (the "
        "one-month window, where M0158 was weakest at 3.9%, so the split's effect can be read "
        "where there was most to fix). The unsplit control is M0158-Z10-N20, already recorded on "
        "the same screen, gate, slots and fees. Assumptions: share volume, not dollar volume (the "
        "fall itself shrinks dollar volume); store volume is split-adjusted like the prices; cut "
        "at 1.0, mean against mean. Success: QUIET beats total-return SPY on the deposits with a "
        "worst fall under 25%, profit factor >= 1.3, a positive edge in 2009-2015, AND beats LOUD "
        "by at least a point a year (otherwise the split is not real)."
    ),
    expected_failure=(
        "The split halves a pool that was already thin, so the quiet book's 20 names are drawn "
        "from fewer and less extreme fallers and the signal weakens. Fees are unchanged: the "
        "book still turns over nearly fully each month at Gotrade's minimum fees on small slots, "
        "which took most of M0158's premium. The 1994 effect was measured on weekly returns in the "
        "1980s, before decimal ticks (2001) narrowed the liquidity premium reversal is paid from, "
        "so whatever edge exists is likely in 1996-2002 and gone by 2009-2015. Quiet fallers are "
        "also likely to be calm, low-beta names, which leans the book toward low volatility and "
        "lags SPY's big-company drift in narrow markets (1998-99, 2013). If QUIET and LOUD earn "
        "within a point a year of each other, the volume split says nothing in this universe, and "
        "short-term reversal should be closed for this lab."
    ),
    candidates=(
        _v("QUIET-Z10-N20", QuietParams(Z10),
           "M0158's two-week standardised residual, only fallers that traded below their own normal volume"),
        _v("LOUD-Z10-N20", QuietParams(Z10, side="loud"),
           "Same score, only fallers that traded above their normal volume: the side that should keep falling"),
        _v("QUIET-Z21-N20", QuietParams(Z21),
           "Quiet fallers on the one-month window, where the unsplit book was weakest"),
    ),
    seen_keys=(
        "concept:volume-conditioned-reversal",
        "concept:quiet-fall-reversal",
        "concept:low-volume-losers-reverse",
    ),
)
