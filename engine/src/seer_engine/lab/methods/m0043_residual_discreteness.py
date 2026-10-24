"""M0043 — Residual information discreteness: count the up and down days of the residual, not the price.

Parent: M0036 (Da, Gurun & Warachka 2014, "Frog in the Pan", RFS 27(7)). M0036 counted the up and
down days of each stock's TOTAL daily return and sorted two pools by it. On the total-momentum
pool the drizzle book beat its jumps mirror; on the residual-momentum pool the two were
indistinguishable. The residual pool is ranked on the market-model residual, but the count still
read the raw price, whose sign pattern is mostly the market's. So the count carried no
information about the stream the ranking cared about.

This method changes that one thing. On data date d it fits M0007-N20-RAW's market model (18-month
OLS of the stock on SPY, ending ``skip`` sessions before d), forms the residual daily series over
the 12-month formation window, and computes

    ID = sign(cumulative residual) x (share of negative residual days - share of positive ones)

Everything else is M0036's frame verbatim: F4's screen, the SPY-200 trend gate, the ``pool``
highest raw residual momentum names, top-20, monthly, equal weights, fractional shares at
Gotrade's real fees. ``choose`` and ``targets_from_rows`` are M0036's, imported, so the only
difference between this book and M0036's RM-CONT/RM-DISC is the stream the days are counted on.

The fourth variant has no opinion in it: ``pool == top`` makes the continuity sort a no-op, so it
is the plain residual book through the same allocator, the same habit and the same fees. Without
it the lab could tell a real separation from a lucky one but not whether the sort is worth what
the churn it causes costs. Every piece reads only bars dated <= d.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    MIN_FRAC,
    ReturnGrid,
    _ols,
    build_grid,
    residual_scores,
)
from seer_engine.lab.methods.m0036_frog_in_the_pan import (
    FipParams,
    FrogInThePanAllocator,
    choose,
    targets_from_rows,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import FactorRow

ADDED = date(2026, 10, 24)
BETA_N = 378  # sessions of the market-model fit, as M0007-N20-RAW


def residual_continuity_scores(
    grid: ReturnGrid, symbols: list[str], data_date: date, params: FipParams
) -> dict[str, float]:
    """Each symbol's residual continuity (minus residual information discreteness) on ``data_date``.

    Higher is more continuous: the residual drift was earned as a drizzle rather than in jumps.
    The residual is the stock's daily return less alpha and beta times the market's, with alpha
    and beta fitted over the ``BETA_N`` sessions ending ``skip`` before d, exactly as
    ``residual_scores`` forms it. Absent = too little of either window to score.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    end = j - params.skip
    b0 = end - BETA_N + 1
    f0 = end - params.fip_n + 1
    mrow = grid.row.get(params.market)
    if end < 0 or b0 < 0 or f0 < 0 or mrow is None:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)

    mb = grid.rets[mrow, b0 : end + 1]
    rb = grid.rets[idx, b0 : end + 1]
    ok_b = np.isfinite(rb) & np.isfinite(mb)[None, :]
    enough_b = ok_b.sum(axis=1) >= max(3, math.ceil(MIN_FRAC * BETA_N))
    alpha, beta, fitted = _ols(rb, np.broadcast_to(mb, rb.shape), ok_b)

    mw = grid.rets[mrow, f0 : end + 1]
    rw = grid.rets[idx, f0 : end + 1]
    ok = np.isfinite(rw) & np.isfinite(mw)[None, :]
    m = ok.sum(axis=1)
    enough_w = m >= max(3, math.ceil(MIN_FRAC * params.fip_n))

    with np.errstate(divide="ignore", invalid="ignore"):
        resid = rw - alpha[:, None] - beta[:, None] * mw[None, :]
        cum = np.where(ok, resid, 0.0).sum(axis=1)
        up = (ok & (resid > 0.0)).sum(axis=1)
        down = (ok & (resid < 0.0)).sum(axis=1)
        score = -(np.sign(cum) * (down - up) / np.where(m > 0, m, 1))

    live = enough_b & enough_w & fitted & np.isfinite(score)
    return {names[k]: float(score[k]) for k in (int(v) for v in np.flatnonzero(live))}


class ResidualDiscretenessAllocator(FrogInThePanAllocator):
    """M0036's book with the continuity counted on the residual stream. Residual pool only."""

    id = "M0043"

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: ReturnGrid | None, data_date: date, params: FipParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        if params.base != "residual":
            raise ValueError("M0043 ranks on the residual pool only")
        symbols = [r.symbol for r in rows]
        cont = residual_continuity_scores(grid, symbols, data_date, params)
        if not cont:
            return ()
        base = residual_scores(grid, symbols, data_date, params.resid())
        return targets_from_rows(choose(rows, base, cont, params), params)


RESDISC = ResidualDiscretenessAllocator()


def _v(suffix: str, params: FipParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0043-{suffix}", family="M0043", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=RESDISC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0043",
    name="Residual information discreteness: count the up and down days of the residual, not the price",
    family="stock-momentum-attention",
    source_kind="variation",
    source_ref=(
        "Da, Gurun & Warachka (2014), Frog in the Pan: Continuous Information and Momentum, "
        "Review of Financial Studies 27(7), 2171-2218 (SSRN 1777988); lab parent M0036"
    ),
    parent_id="M0036",
    hypothesis=(
        "M0036 found the frog-in-the-pan effect alive on the total-momentum pool (drizzle 12.08% a "
        "year money-weighted vs jumps 9.78%) and dead on the residual pool (11.90% vs 11.99%). "
        "The tempting explanation, that residual winners are already continuous, was measured "
        "on 76 quarterly dates and is false. What remains is a measurement mismatch: M0036 "
        "counted up and down days on each stock's total return while the residual pool is ranked "
        "on the market-model residual, and a raw price's sign pattern is mostly the market's. This "
        "method counts them on the residual daily series itself (the 18-month SPY market model "
        "M0007-N20-RAW uses, residual over the 12-1 window) and sorts the top-40 residual "
        "momentum pool by it. Frame unchanged: F4's screen, SPY-200 trend gate, top-20, monthly, "
        "equal weights, fractional at Gotrade's real fees on the monthly-hold-frac-gotrade preset, "
        "funded 5,000,000 IDR on the 25th. Variants: RES-CONT (most continuous residual), "
        "RES-DISC (its mirror, mandatory: it is what made M0036's total-pool result mean "
        "anything), RES-BLEND (residual-momentum rank plus residual-continuity rank over the "
        "whole eligible set) and RES-PLAIN, the arm with no opinion in it (pool equals book "
        "size, so the sort does nothing: the plain residual book through the same allocator and "
        "fees), which prices what the sort adds against the habit of holding the residual "
        "pool. The paper dates from 2014 and is widely cited, so any dev edge is likely "
        "pre-crowd; 2009-2015 is the first filter. I expect separation to come back at about "
        "the size it had on the total pool (2 points a year, a quarter less turnover) and the worst "
        "fall to stay near 20-22%, so rejection on the fall as M0036 was: this buys quality per "
        "trade, not safety. If it separates, it is a cheap quality gain on the book the owner "
        "already trades; if not, the attention effect is absent for residual winners and the "
        "family closes."
    ),
    expected_failure=(
        "RES-CONT and RES-DISC land within half a point of each other again, which would say "
        "the effect is absent for residual winners in a 539-name large-cap index universe, "
        "where limited attention is arbitraged out. Or the separation appears but RES-CONT "
        "does not beat RES-PLAIN, so the sort is no better than no sort once costs are "
        "counted. Either way the worst fall stays over 20% and the method is rejected on it, "
        "since halving the pool to 40 does nothing about the trend gate's late exits."
    ),
    candidates=(
        _v("RES-CONT", FipParams(N20, mode="continuous", base="residual"),
           "Top-40 by raw residual momentum, then the 20 most continuous by the residual's own up/down days"),
        _v("RES-DISC", FipParams(N20, mode="discrete", base="residual"),
           "The mirror: the same 40 residual winners, then the 20 most discrete on the residual stream"),
        _v("RES-BLEND", FipParams(N20, mode="blend", base="residual"),
           "No pool: rank the eligible set on residual-momentum rank plus residual-continuity rank"),
        _v("RES-PLAIN", FipParams(N20, mode="continuous", base="residual", pool=20),
           "No opinion: pool equals book size, so the plain residual top-20 through the same allocator and fees"),
    ),
    seen_keys=(
        "concept:residual-information-discreteness",
        "concept:frog-in-the-pan",
        "concept:information-discreteness",
        "doi:10.1093/rfs/hhu003",
    ),
)
