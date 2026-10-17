"""M0197 — Stocks that shrug off bond-yield moves: rank members by their weekly sensitivity to the
10-year Treasury yield, net of the market's own move.

Source: D.E. Shaw research note on Treasury beta (caia.org/node/6853); Maio & Santa-Clara,
short-rate innovations and CAPM anomalies; Driessen, Kuiper & Beilo, "Does interest rate exposure
explain the low-volatility anomaly?" (Tilburg). Reserved by Sera 20261017-1808. The frame is
M0191's, which is M0179's: F4's member screen, 20 names at equal weight, quarterly re-picks, a
40% keep band, slots left over in SPY -- the same frame the placebo M0187 filled in a meaningless
order, so this book is judged against that placebo and not only against SPY.
Idea: stocks differ in how they move when yields change, after allowing for the market. Bond-like
stocks rise when yields fall; growth and cyclical stocks the other way. Several papers say this
exposure is priced and explains part of the low-risk premium.

The signal. On a re-pick date d, take SPY's sessions i - STEP*k for k = WEEKS..0 (WEEKS + 1
points STEP sessions apart, about one year of weekly marks ending on d). The yield at each mark is
the store's T10Y value on or before it (read once through ``upto``), and its change dY is in
percentage points. Each member's last close on or before each mark gives WEEKS weekly log returns
r; SPY's give m. One least-squares fit r = a + b*m + c*dY, shared design matrix, gives every member
its market beta b and its yield loading c. Weekly rather than daily because a yield change and a
stock's reaction need not land on the same close (bond and stock markets close at different times
on some days, and holidays differ). A member needs a bar dated d and history back past the first
mark. With no T10Y row within STALE_DAYS of d, nothing is scored that day and the book holds what
it had (or SPY).

The ranking. Rank fraction in [0, 1), 0 = the first pick. ``side``: "bond" puts the most negative
c first (the stocks that rise most when yields fall); "opp" the most positive c (the paired
control, the stocks that rise when yields rise); "neutral" the smallest |c| (rate-neutral).

The band and the switch: as M0191 (re-rank on the last close of each quarter, keep a holding under
``keep_pct``, between re-picks a holding leaves only when it stops being a member). The switch is
set explicitly on every variant: trend=None for the no-switch rungs (FactorParams defaults to the
SPY 200-day switch, M0188's slip).

Market-aware (``market_fields = ("series",)``): the history-only path has no yield, so by the
contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 17)
WEEKS = 52  # one year of weekly returns
STEP = 5  # sessions between marks
RATE = "T10Y"
STALE_DAYS = 7  # the yield's last row must be this recent on a re-pick date
REPICK_MONTHS = (3, 6, 9, 12)
SIDES = ("bond", "opp", "neutral")


@dataclass(frozen=True, slots=True)
class YieldBetaParams:
    """``inner`` is F4's screen, book size and switch (set explicitly by every variant);
    ``keep_pct`` the rank fraction (in percent) a holding must stay under; ``side`` which end of
    the yield loading the book wants first (see the module docstring)."""

    inner: FactorParams
    keep_pct: int = 40
    side: str = "bond"
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.keep_pct, bool) or not isinstance(self.keep_pct, int):
            raise TypeError(f"keep_pct must be an int, got {type(self.keep_pct).__name__}")
        if not 0 < self.keep_pct <= 100:
            raise ValueError(f"keep_pct must be in (0, 100], got {self.keep_pct}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep_pct": str(self.keep_pct), "side": self.side, "market": self.market,
               "weeks": str(WEEKS), "step": str(STEP), "rate": RATE,
               "stale_days": str(STALE_DAYS),
               "repick_months": ",".join(str(m) for m in REPICK_MONTHS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> YieldBetaParams:
    if not isinstance(params, YieldBetaParams):
        raise TypeError(f"params must be YieldBetaParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class YieldBetaPrepared:
    history: Mapping[str, History]
    series: MarketSeries
    factor: FactorPrepared | None


def loadings(history: Mapping[str, History], series: MarketSeries, symbols: list[str],
             data_date: date, market: str) -> dict[str, tuple[float, float]]:
    """Each symbol's (market beta, yield loading) on ``data_date``; unscoreable symbols left out."""
    mh = history.get(market)
    if mh is None:
        return {}
    i = mh.index_of(data_date)
    span = WEEKS * STEP
    if i is None or i < span:
        return {}
    rows = series.upto(RATE, data_date, last=span + 40)
    if not rows or (data_date - rows[-1][0]).days > STALE_DAYS:
        return {}
    idx = np.arange(i - span, i + 1, STEP)
    when = mh.dates[idx]
    yd = np.array([d for d, _ in rows], dtype="datetime64[D]")
    yv = np.array([v for _, v in rows], dtype=float)
    k = np.searchsorted(yd, when, side="right") - 1
    if bool(np.any(k < 0)):
        return {}
    dy = np.diff(yv[k])
    m = np.diff(np.log(mh.close[idx]))
    x = np.column_stack([np.ones_like(m), m, dy])
    if np.linalg.matrix_rank(x) < 3:
        return {}
    solve = np.linalg.pinv(x.T @ x) @ x.T  # (3, WEEKS), shared by every member
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        j = None if h is None else h.index_of(data_date)
        if j is None or h.dates[0] > when[0]:
            continue
        pos = np.searchsorted(h.dates[: j + 1], when, side="right") - 1
        c = h.close[pos]
        if not bool(np.all(np.isfinite(c))) or bool(np.any(c <= 0.0)):
            continue
        coef = solve @ np.diff(np.log(c))
        b, v = float(coef[1]), float(coef[2])
        if np.isfinite(b) and np.isfinite(v):
            out[s] = (b, v)
    return out


def scored(history: Mapping[str, History], series: MarketSeries, rows: list[FactorRow],
           data_date: date, p: YieldBetaParams) -> dict[str, float]:
    """Each eligible symbol's rank fraction in [0, 1): 0 is the first name the book wants."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    lv = loadings(history, series, pool, data_date, p.market)
    if not lv:
        return {}
    if p.side == "bond":
        key = {s: bv[1] for s, bv in lv.items()}
    elif p.side == "opp":
        key = {s: -bv[1] for s, bv in lv.items()}
    else:
        key = {s: abs(bv[1]) for s, bv in lv.items()}
    order = sorted(lv, key=lambda s: (key[s], s))
    return {s: k / len(order) for k, s in enumerate(order)}


def choose(history: Mapping[str, History], members: AbstractSet[str], frac: Mapping[str, float],
           data_date: date, held: frozenset[str], p: YieldBetaParams) -> tuple[Target, ...]:
    """M0179's banded quarterly chooser, fed ``frac`` (its own reads coskewness, and it is frozen)."""
    stocks = sorted(s for s in held if s != p.market and s not in EXCLUDED)
    if not stocks or data_date.month in REPICK_MONTHS:
        order = [s for _, s in sorted((v, s) for s, v in frac.items())]
        cut = p.keep_pct / 100.0
        kept = sorted((s for s in stocks if frac.get(s, 1.0) < cut), key=lambda s: (frac[s], s))
        picks = kept[: p.inner.top]
        for s in order:
            if len(picks) >= p.inner.top:
                break
            if s not in picks:
                picks.append(s)
    else:  # between re-picks: keep every holding that is still a member with a bar today
        picks = [s for s in stocks if s in members][: p.inner.top]
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks:
        h = history.get(s)
        if h is None or h.index_of(data_date) is None:
            continue
        t = target_from_close(s, last_close(h, data_date), w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


class YieldBetaAllocator:
    """The screened members ranked on their weekly loading on 10-year yield changes, net of the
    market, quarterly, banded; slots left over in SPY. No yield (history-only path): no targets."""

    id = "M0197"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        # As M0191: the screen's and the switch's need only. A member without a year of bars is not
        # scored yet and its slot holds SPY.
        return factor_lookback(_check(params).inner)

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

    def _run(self, prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: YieldBetaParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        stocks = [s for s in held if s != p.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = scored(prepared.history, prepared.series, rows, data_date, p) if repick else {}
        return choose(prepared.history, members, frac, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no yield, so no ranking and no target."""
        return self._run(YieldBetaPrepared(history, EMPTY_SERIES, None), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> YieldBetaPrepared:
        return YieldBetaPrepared(history, EMPTY_SERIES, prepare_factor(history))

    def prepare_market(self, market: Any) -> YieldBetaPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return YieldBetaPrepared(market.history, series, prepare_factor(market.history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, YieldBetaPrepared):
            raise TypeError(f"prepared must be YieldBetaPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


YIELDBETA = YieldBetaAllocator()


def _screen(top: int, trend: tuple[str, int] | None) -> FactorParams:
    # trend has no default here: FactorParams' own default is the SPY 200-day switch, and every
    # variant must say which it means (M0188's slip). The rank is unused: only the screen.
    return FactorParams(rank="momentum", top=top, trend=trend)


def _v(suffix: str, params: YieldBetaParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0197-{suffix}", family="M0197", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=YIELDBETA, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


SW = ("SPY", 200)

METHOD = Method(
    id="M0197",
    name=(
        "Stocks that shrug off bond-yield moves: rank members by their sensitivity to the 10-year "
        "Treasury yield, after the market's own move"
    ),
    family="stock-treasury-beta",
    source_kind="paper",
    source_ref=(
        "D.E. Shaw research note on Treasury beta (caia.org/node/6853); Maio & Santa-Clara, "
        "short-rate innovations and CAPM anomalies; Driessen et al., Does interest rate exposure "
        "explain the low volatility anomaly? (Tilburg)"
    ),
    parent_id=None,
    hypothesis=(
        "Stocks differ in how they move when bond yields change, after allowing for the market: "
        "bond-like stocks (utilities, staples, steady payers) rise when yields fall, growth and "
        "cyclical stocks the other way. Several papers (2010s; so the whole dev window is before "
        "publication and any edge may have faded since) say rate exposure is priced and explains "
        "part of the low-risk premium. On the last close of each quarter, among members passing "
        "F4's $5 / $20M screen, regress 52 weekly log returns (marks 5 sessions apart) on SPY's "
        "weekly log return and the weekly change in the 10-year Treasury yield in percentage "
        "points (one shared fit, so the yield loading is net of the market), hold 20 names at "
        "1/20 each, keep a holding while its rank fraction stays under 40%, unfilled slots in "
        "SPY, fractional shares at Gotrade's real fees on the owner's deposits. Variants, each "
        "with and without the SPY 200-day switch set explicitly (trend=None on the no-switch "
        "rungs): Y20, the 20 members whose prices rise most when yields fall (the bond-like "
        "side); Y20-OPP, the 20 with the most positive loading (the paired control, kept in the "
        "same pool so the walk-forward selection can pick against the idea); N20, the 20 with "
        "the smallest absolute loading (rate-neutral). Judged beside the meaningless placebo in "
        "the same frame (M0187, +8.8% to +11.9% a year on the deposits without the switch, "
        "+10.3% to +11.0% with it, SPY +7.2%), and each variant's beta to SPY is reported. "
        "Success: Y20 or Y20-SW beats total-return SPY and the placebo's range, worst fall "
        "<= 25%, PF >= 1.3, a majority of walk-forward folds, a positive 2009-2015 edge, does not "
        "trail in the 2013 rate jump, and clearly beats Y20-OPP."
    ),
    expected_failure=(
        "It is a sector bet and a falling-rate bet, not a priced exposure. A ranking probe run "
        "before this file was committed (rankings and in-window loadings only, no later returns) "
        "showed the bond-like side to be utilities and REITs in most years (2004-12-31: DUK, ED, "
        "AEP, EIX, FE, EXC...; 2013 and 2015: VTR, WELL, DOC, SPG, PLD, CMS, WEC, NEE) and the "
        "opposite side banks, life insurers and energy (SCHW, MET, PRU, LNC, ZION, BAC, RIG, FCX). "
        "Beta is not the main tilt: the bond side's average beta was 0.72 in 1999, about 1.0 in "
        "2004, 2013 and 2015, and 2.0 on 2008-06-30, when the one-year fit put Fannie, Freddie, "
        "KeyCorp, Fifth Third and REITs on the bond side; the correlation between beta and the "
        "yield loading across members ran from -0.41 to 0.20. So: Y20 rides 1996-2015's falling "
        "yields through utilities and REITs, is hit in 2008 by the financials the 2007-08 fit "
        "picked up, and is hit in the 2013 rate jump (the taper scare, May-September) when REITs "
        "and utilities fell hardest; it fails 'beats SPY' in 2009-2015 or lands inside the "
        "placebo's range. Y20-OPP, a banks-and-energy book, loses 2008 badly. N20 behaves like "
        "the placebo, since a small loading carries no information, and that is its use: if N20 "
        "matches Y20, the ranking added nothing. Without the switch every book falls about 50% "
        "in 2008, like the placebo; with it the worst fall may pass 25% but DSR at N about 127 "
        "will not reach 0.90 unless the lead is well above the placebo's. The published "
        "evidence is mostly on portfolios sorted across all stocks; among big index members a "
        "20-name equal-weight book is mainly the frame."
    ),
    candidates=(
        _v("Y20", YieldBetaParams(_screen(20, None), side="bond"),
           "The 20 members that rise most when the 10-year yield falls, net of the market, no "
           "switch"),
        _v("Y20-SW", YieldBetaParams(_screen(20, SW), side="bond"),
           "The bond-like book behind the SPY 200-day switch"),
        _v("Y20-OPP", YieldBetaParams(_screen(20, None), side="opp"),
           "Control: the 20 members that rise most when the yield rises, no switch"),
        _v("Y20-OPP-SW", YieldBetaParams(_screen(20, SW), side="opp"),
           "Control behind the SPY 200-day switch"),
        _v("N20", YieldBetaParams(_screen(20, None), side="neutral"),
           "The 20 members least moved by yield changes (rate-neutral), no switch"),
        _v("N20-SW", YieldBetaParams(_screen(20, SW), side="neutral"),
           "The rate-neutral book behind the SPY 200-day switch"),
    ),
    seen_keys=(
        "concept:treasury-beta",
        "concept:interest-rate-exposure",
    ),
)
