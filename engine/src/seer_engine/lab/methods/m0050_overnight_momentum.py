"""M0050 — Momentum earned overnight only: rank on the gaps between yesterday's close and today's open.

Source: Lou, Polk & Skouras (2019), "A tug of war: overnight versus intraday expected returns",
Journal of Financial Economics 134(1), 192-213, doi:10.1016/j.jfineco.2019.03.011.
Idea: the paper splits each stock's daily return into the overnight leg (close to next open) and
the intraday leg (open to close) and finds that essentially all of momentum's abnormal return is
earned overnight, while the intraday leg of the same stocks runs the other way: individuals push
prices at the open, institutions lean against the characteristic during the day. The lab has
ranked on twelve-month return eleven ways and has never once separated WHEN the return was earned.

This method keeps M0036's frame verbatim -- F4's liquidity and membership screen, the SPY-200 trend
gate, top-20, monthly, equal weights, fractional shares at Gotrade's real fees on
``monthly-hold-frac-gotrade`` -- and changes only the ranking key. On data date d, over the
``n`` sessions ending ``skip`` sessions before d on the market symbol's calendar:

    overnight(s) = sum of log(open_t / close_{t-1})   (back-to-back bars only)
    intraday(s)  = sum of log(close_t / open_t)        (the same sessions)

and ``rank`` picks the key:

    * ``"overnight"``: the top names by overnight sum;
    * ``"intraday"``: the top names by intraday sum (the control the paper says should lose);
    * ``"total"``: F4's 12-1 total momentum in the same run (the yardstick);
    * ``"tug"``: overnight rank minus intraday rank over the whole eligible set -- the paper's
      tug-of-war spread, taken long only;
    * ``"total-overnight"``: the ``pool`` highest total-momentum names, then the ``top`` of them
      with the largest overnight sum -- momentum winners whose gain came overnight.

Assumption, written before the run: the research store's prices are split-adjusted and NOT
dividend-adjusted, and an allocator sees bars only, never the dividend file. The ex-dividend gap
therefore stays inside the overnight leg (about 2% a year for a 2% yielder). This is the same bias
F4's close-to-close momentum already carries, but here it lands on one leg only, so "overnight"
leans a little away from high-yield names. Every piece reads only bars dated <= d.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
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
    trend_on,
)

ADDED = date(2026, 10, 9)
MIN_FRAC = 0.8  # a window needs this share of usable sessions before a name is scored

Rank = Literal["overnight", "intraday", "total", "tug", "total-overnight"]
_RANKS: tuple[str, ...] = ("overnight", "intraday", "total", "tug", "total-overnight")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class OnParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; the rest is the ranking.

    ``inner.rank`` stays ``"momentum"`` so the eligible universe is F4-MOM12-N20-TREND's and
    M0036's name for name, and ``rank="total"`` reproduces F4's own ranking inside this run.
    """

    inner: FactorParams
    rank: Rank = "overnight"
    pool: int = 40  # "total-overnight" only: the total-momentum winners the overnight sort runs inside
    n: int = 231  # sessions in the window: 12-1 months, as F4's mom_n - mom_skip
    skip: int = 21  # sessions skipped before d (the "-1" of 12-1)
    market: str = "SPY"  # the calendar the daily legs are laid on

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.rank, str):
            raise TypeError(f"rank must be a str, got {type(self.rank).__name__}")
        if self.rank not in _RANKS:
            raise ValueError(f"rank must be one of {_RANKS}, got {self.rank!r}")
        for name in ("pool", "n", "skip"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.pool < self.inner.top:
            raise ValueError(f"pool must be >= inner.top, got pool={self.pool} top={self.inner.top}")
        if self.n < 20:
            raise ValueError(f"n must be >= 20, got {self.n}")
        if self.skip < 0:
            raise ValueError(f"skip must be >= 0, got {self.skip}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "rank": self.rank,
            "pool": str(self.pool),
            "n": str(self.n),
            "skip": str(self.skip),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> OnParams:
    if not isinstance(params, OnParams):
        raise TypeError(f"params must be OnParams, got {type(params).__name__}")
    return params


def on_lookback(params: OnParams) -> int:
    """Bars through d the decision needs: the screen's and the window's."""
    return max(factor_lookback(params.inner), params.skip + params.n + 2)


# --------------------------------------------------------------------------- the two legs


@dataclass(frozen=True, slots=True)
class LegGrid:
    """Each symbol's overnight and intraday log returns on the market symbol's calendar.

    ``night[k, t]`` is log(open / previous close) into session ``dates[t]`` and ``day[k, t]`` is
    log(close / open) on it; both are NaN unless the symbol has bars dated ``dates[t]`` and
    ``dates[t - 1]`` back to back with finite positive prices. A function of the bars alone, so the
    columns at or before any date d are the same whether built from whole or cut history.
    """

    row: Mapping[str, int]
    dates: np.ndarray
    night: np.ndarray
    day: np.ndarray


def build_legs(history: Mapping[str, History], market: str) -> LegGrid | None:
    m = history.get(market)
    if m is None or len(m) < 2:
        return None
    cal = m.dates
    ncal = len(cal)
    symbols = tuple(sorted(history))
    night = np.full((len(symbols), ncal), np.nan, dtype=np.float64)
    day = np.full((len(symbols), ncal), np.nan, dtype=np.float64)
    for k, symbol in enumerate(symbols):
        h = history[symbol]
        n = len(h)
        if n < 2:
            continue
        pos = np.searchsorted(cal, h.dates)
        inside = pos < ncal
        safe = np.where(inside, pos, 0)
        on_cal = inside & (cal[safe] == h.dates)
        prev_c, cur_o, cur_c = h.close[:-1], h.open[1:], h.close[1:]
        ok = (
            np.isfinite(prev_c) & np.isfinite(cur_o) & np.isfinite(cur_c)
            & (prev_c > 0.0) & (cur_o > 0.0) & (cur_c > 0.0)
        )
        keep = np.zeros(n, dtype=bool)
        keep[1:] = ok & on_cal[1:] & on_cal[:-1] & (safe[1:] == safe[:-1] + 1)
        kk = keep[1:]
        with np.errstate(divide="ignore", invalid="ignore"):
            night[k, safe[keep]] = np.log(cur_o[kk] / prev_c[kk])
            day[k, safe[keep]] = np.log(cur_c[kk] / cur_o[kk])
    night.setflags(write=False)
    day.setflags(write=False)
    return LegGrid({s: k for k, s in enumerate(symbols)}, cal, night, day)


def leg_sums(
    grid: LegGrid, symbols: list[str], data_date: date, params: OnParams
) -> tuple[dict[str, float], dict[str, float]]:
    """(overnight sum, intraday sum) per scorable symbol over the window ending ``skip`` before d."""
    d = as_day(data_date)
    j = int(np.searchsorted(grid.dates, d, side="right")) - 1
    if j < 0 or grid.dates[j] != d:
        return {}, {}
    end = j - params.skip
    f0 = end - params.n + 1
    if end < 0 or f0 < 0:
        return {}, {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}, {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    nt = grid.night[idx, f0 : end + 1]
    dy = grid.day[idx, f0 : end + 1]
    ok = np.isfinite(nt) & np.isfinite(dy)
    enough = ok.sum(axis=1) >= max(3, math.ceil(MIN_FRAC * params.n))
    on = np.where(ok, nt, 0.0).sum(axis=1)
    intra = np.where(ok, dy, 0.0).sum(axis=1)
    live = enough & np.isfinite(on) & np.isfinite(intra)
    keep = [int(v) for v in np.flatnonzero(live)]
    return ({names[k]: float(on[k]) for k in keep}, {names[k]: float(intra[k]) for k in keep})


def choose(
    rows: list[FactorRow], on: Mapping[str, float], intra: Mapping[str, float], params: OnParams
) -> list[FactorRow]:
    """The ``inner.top`` rows this method holds, in the order it ranked them."""
    scorable = [r for r in rows if r.symbol in on and r.symbol in intra and r.symbol not in EXCLUDED]
    if not scorable:
        return []
    top = params.inner.top
    if params.rank == "overnight":
        return sorted(scorable, key=lambda r: (-on[r.symbol], r.symbol))[:top]
    if params.rank == "intraday":
        return sorted(scorable, key=lambda r: (-intra[r.symbol], r.symbol))[:top]
    if params.rank == "total":
        return sorted(scorable, key=lambda r: (-r.momentum, r.symbol))[:top]
    if params.rank == "tug":
        by_on = {r.symbol: i for i, r in enumerate(sorted(scorable, key=lambda r: (on[r.symbol], r.symbol)))}
        by_id = {r.symbol: i for i, r in enumerate(sorted(scorable, key=lambda r: (intra[r.symbol], r.symbol)))}
        return sorted(scorable, key=lambda r: (-(by_on[r.symbol] - by_id[r.symbol]), r.symbol))[:top]
    winners = sorted(scorable, key=lambda r: (-r.momentum, r.symbol))[: params.pool]
    return sorted(winners, key=lambda r: (-on[r.symbol], r.symbol))[:top]


def targets_from_rows(chosen: list[FactorRow], params: OnParams) -> tuple[Target, ...]:
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


@dataclass
class OnPrepared:
    """F4's rolling feature columns plus one leg grid per market symbol, built on first use."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    grids: dict[str, LegGrid | None] = field(default_factory=dict, repr=False)

    def grid(self, market: str) -> LegGrid | None:
        if market not in self.grids:
            self.grids[market] = build_legs(self.history, market)
        return self.grids[market]


class OvernightMomentumAllocator:
    """F4's book, ranked on when the past year's return was earned (overnight vs intraday).

    Held symbols get no special treatment: the targets are exactly the new top set, so a name
    that falls out of it is signal-exited by the book engine, as in F4, M0007 and M0036.
    """

    id = "M0050"

    def lookback(self, params: Any) -> int:
        return on_lookback(_check(params))

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

    def _targets(self, rows: list[FactorRow], grid: LegGrid | None, data_date: date,
                 params: OnParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        on, intra = leg_sums(grid, [r.symbol for r in rows], data_date, params)
        if not on:
            return ()
        return targets_from_rows(choose(rows, on, intra, params), params)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(rows, build_legs(history, p.market), data_date, p)

    def prepare(self, history: Mapping[str, History]) -> OnPrepared:
        return OnPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, OnPrepared):
            raise TypeError(f"prepared must be OnPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(rows, prepared.grid(p.market), data_date, p)


OVERNIGHT = OvernightMomentumAllocator()


def _v(suffix: str, params: OnParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0050-{suffix}", family="M0050", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=OVERNIGHT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0050",
    name="Momentum earned overnight only: rank on the gaps between yesterday's close and today's open",
    family="stock-overnight-intraday",
    source_kind="paper",
    source_ref=(
        "Lou, Polk & Skouras (2019), A tug of war: overnight versus intraday expected returns, "
        "Journal of Financial Economics 134(1), 192-213, doi:10.1016/j.jfineco.2019.03.011"
    ),
    parent_id=None,
    hypothesis=(
        "Lou, Polk and Skouras find that essentially all of momentum's abnormal return is earned "
        "overnight (close to next open), while the intraday part (open to close) of the same "
        "stocks runs the other way, because individuals push prices overnight and institutions "
        "trade against the characteristic during the day; the split is strongest in large, "
        "high-price stocks, which is F4's universe. The lab has ranked on twelve-month total and "
        "residual return eleven ways and never separated WHEN the return was earned. Each month, "
        "among F4's screened members, rank on the sum of the last twelve months' (skip the latest "
        "month) overnight log returns and hold the top 20 equal weight behind the SPY 200-day "
        "gate, in fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade with the "
        "owner's funding. Variants: ON (overnight rank), ID (intraday rank, the control the paper "
        "says should lose), TOT (plain 12-1 total momentum in the same run, the yardstick), TUG "
        "(overnight rank minus intraday rank, the paper's tug-of-war spread as a long-only pick) "
        "and TOT-ON (the 40 best total-momentum names, then the 20 of them whose gain came most "
        "overnight). Success: ON or TOT-ON beats TOT on return per unit of worst fall and ID is "
        "the worst of the set. Assumption: the store's prices are split-adjusted, not dividend-"
        "adjusted, and an allocator cannot see dividends, so the ex-dividend gap stays inside the "
        "overnight leg; this tilts ON slightly away from high-yield names and is not corrected."
    ),
    expected_failure=(
        "Daily open prices before about 2001 are noisy (fractional ticks, opens recorded equal to "
        "the prior close on thin days) and split adjustment can leave rounding in the open, so the "
        "overnight sum carries measurement noise the close-to-close sum does not. Overnight returns "
        "are small and the twelve-month sum is dominated by a handful of earnings-announcement gaps, "
        "so ON may simply be an earnings-surprise momentum book with the same 20%-plus fall in "
        "1998 and 2008 as every other momentum book. Worse, ranking on the overnight leg alone "
        "rewards names with large gap risk -- high-volatility, high-news stocks -- so ON's worst "
        "fall may be larger than TOT's, not smaller. The intraday control may not lose either: in "
        "a large-cap universe the intraday leg is the institutional leg and may carry the "
        "low-volatility tilt that has helped every blend in this lab."
    ),
    candidates=(
        _v("ON", OnParams(N20, rank="overnight"),
           "Top 20 by the past year's (skip a month) summed overnight gaps"),
        _v("ID", OnParams(N20, rank="intraday"),
           "Top 20 by the same window's summed open-to-close moves: the control, expected worst"),
        _v("TOT", OnParams(N20, rank="total"),
           "F4's plain 12-1 total momentum in the same run: the yardstick"),
        _v("TUG", OnParams(N20, rank="tug"),
           "Overnight rank minus intraday rank: the paper's tug-of-war spread, long only"),
        _v("TOT-ON", OnParams(N20, rank="total-overnight"),
           "Top 40 by total momentum, then the 20 whose gain came most overnight"),
    ),
    seen_keys=(
        "concept:overnight-momentum",
        "concept:overnight-intraday-decomposition",
        "concept:tug-of-war",
        "doi:10.1016/j.jfineco.2019.03.011",
    ),
)
