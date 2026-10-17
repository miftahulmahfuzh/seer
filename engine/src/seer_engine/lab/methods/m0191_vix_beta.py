"""M0191 — Stocks that suffer when fear jumps: rank by sensitivity to daily VIX changes and own the
least exposed (the most negative VIX loading).

Source: Ang, Hodrick, Xing & Zhang (2006), "The Cross-Section of Volatility and Expected Returns",
Journal of Finance 61(1), 259-299 (aggregate-volatility risk, their Table I/II: sensitivity to
daily changes in VXO). Reserved by Sera 20261017-1752 (M0190 was the same idea row with garbled
wording, dropped before it ran). The quarterly, banded frame is M0179's (F4's member screen, a
40% keep band, slots left over in SPY).
Idea: a stock whose return rises when market volatility jumps is insurance against bad times, so
investors pay up for it and it earns less; a stock whose return falls when fear jumps, over and
above what its market beta already says, should earn more. AHXZ report about 1% a month between
the extreme quintiles. Published 2006, so 2006-2015 of the dev window is after publication.

The signal. On a re-pick date d, take SPY's last DAYS + 1 sessions through d. The fear index for
each of those sessions is the store's VIX value on or before it (``MarketSeries.value_on``
semantics, read once through ``upto``), and its daily change dV is in index points. Each member's
last close on or before each session gives DAYS daily log returns r; SPY's give m. One least-
squares fit r = a + b*m + c*dV, shared design matrix, gives every member its market beta b and its
VIX loading c. Because m is in the fit, c is the loading on the part of the fear change the
market's own move does not explain (AHXZ's partial loading), not beta in disguise by
construction -- but the two regressors are collinear, and a ranking probe before commit
(2008-06-30: corr(b, c) = 0.81 across members) showed the most negative c to be low-beta names
in stressed years. Whether the book is a beta tilt is what the trial's curve and N20-MB reveal. Raw
returns, not excess (the T-bill rate is near constant over a day and falls into a). A member needs
a bar dated d and history back past the window's first session. With no fear-index row within
STALE_DAYS of d, nothing is scored that day and the book holds what it had (or SPY).

The ranking. Rank fraction in [0, 1), 0 = the most negative c (the first pick); ``positive`` flips
the order (the control: the fear hedges). ``beta_band`` keeps only members whose b is within that
distance of 1.0 before ranking, so the book cannot be a beta tilt at all (the test of the expected
failure).

The band and the switch: as M0179 (re-rank on the last close of each quarter, keep a holding under
``keep_pct``, between re-picks a holding leaves only when it stops being a member).

Market-aware (``market_fields = ("series",)``): the history-only path has no fear index, so by the
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
DAYS = 252  # one year of daily returns
FEAR = "VIX"
STALE_DAYS = 7  # the fear index's last row must be this recent on a re-pick date
REPICK_MONTHS = (3, 6, 9, 12)


@dataclass(frozen=True, slots=True)
class VixBetaParams:
    """``inner`` is F4's screen, book size and optional switch; ``keep_pct`` the rank fraction (in
    percent) a holding must stay under; ``positive`` ranks the most positive VIX loading first
    (the control); ``beta_band_pct`` > 0 ranks only members whose market beta is within that many
    hundredths of 1.0."""

    inner: FactorParams
    keep_pct: int = 40
    positive: bool = False
    beta_band_pct: int = 0
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("keep_pct", "beta_band_pct"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if not 0 < self.keep_pct <= 100:
            raise ValueError(f"keep_pct must be in (0, 100], got {self.keep_pct}")
        if not 0 <= self.beta_band_pct <= 100:
            raise ValueError(f"beta_band_pct must be in [0, 100], got {self.beta_band_pct}")
        if not isinstance(self.positive, bool):
            raise TypeError(f"positive must be a bool, got {type(self.positive).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep_pct": str(self.keep_pct), "positive": str(self.positive).lower(),
               "beta_band_pct": str(self.beta_band_pct), "market": self.market,
               "days": str(DAYS), "fear": FEAR, "stale_days": str(STALE_DAYS),
               "repick_months": ",".join(str(m) for m in REPICK_MONTHS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> VixBetaParams:
    if not isinstance(params, VixBetaParams):
        raise TypeError(f"params must be VixBetaParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class VixBetaPrepared:
    history: Mapping[str, History]
    series: MarketSeries
    factor: FactorPrepared | None


def loadings(history: Mapping[str, History], series: MarketSeries, symbols: list[str],
             data_date: date, market: str) -> dict[str, tuple[float, float]]:
    """Each symbol's (market beta, VIX loading) on ``data_date``; unscoreable symbols left out."""
    mh = history.get(market)
    if mh is None:
        return {}
    i = mh.index_of(data_date)
    if i is None or i < DAYS:
        return {}
    rows = series.upto(FEAR, data_date, last=DAYS + 40)
    if not rows or (data_date - rows[-1][0]).days > STALE_DAYS:
        return {}
    when = mh.dates[i - DAYS: i + 1]
    vd = np.array([d for d, _ in rows], dtype="datetime64[D]")
    vv = np.array([v for _, v in rows], dtype=float)
    k = np.searchsorted(vd, when, side="right") - 1
    if bool(np.any(k < 0)):
        return {}
    dv = np.diff(vv[k])
    m = np.diff(np.log(mh.close[i - DAYS: i + 1]))
    x = np.column_stack([np.ones_like(m), m, dv])
    if np.linalg.matrix_rank(x) < 3:
        return {}
    solve = np.linalg.pinv(x.T @ x) @ x.T  # (3, DAYS), shared by every member
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
           data_date: date, p: VixBetaParams) -> dict[str, float]:
    """Each eligible symbol's rank fraction in [0, 1): 0 is the first name the book wants."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    lv = loadings(history, series, pool, data_date, p.market)
    if p.beta_band_pct:
        band = p.beta_band_pct / 100.0
        lv = {s: bv for s, bv in lv.items() if abs(bv[0] - 1.0) <= band}
    if not lv:
        return {}
    sign = -1.0 if p.positive else 1.0
    order = sorted(lv, key=lambda s: (sign * lv[s][1], s))
    return {s: k / len(order) for k, s in enumerate(order)}


def choose(history: Mapping[str, History], members: AbstractSet[str], frac: Mapping[str, float],
           data_date: date, held: frozenset[str], p: VixBetaParams) -> tuple[Target, ...]:
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


class VixBetaAllocator:
    """The screened members with the most negative partial loading on daily VIX changes,
    quarterly, banded; slots left over in SPY. No fear index (history-only path): no targets."""

    id = "M0191"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        # As M0179: the screen's and the switch's need only. A member without DAYS + 1 bars is not
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

    def _run(self, prepared: VixBetaPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: VixBetaParams) -> tuple[Target, ...]:
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
        """The history-only path: no fear index, so no ranking and no target."""
        return self._run(VixBetaPrepared(history, EMPTY_SERIES, None), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> VixBetaPrepared:
        return VixBetaPrepared(history, EMPTY_SERIES, prepare_factor(history))

    def prepare_market(self, market: Any) -> VixBetaPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return VixBetaPrepared(market.history, series, prepare_factor(market.history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, VixBetaPrepared):
            raise TypeError(f"prepared must be VixBetaPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


VIXBETA = VixBetaAllocator()


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: VixBetaParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0191-{suffix}", family="M0191", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=VIXBETA, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


SW = ("SPY", 200)

METHOD = Method(
    id="M0191",
    name=(
        "Stocks that suffer when fear jumps: rank by sensitivity to daily VIX changes and own the "
        "least exposed"
    ),
    family="stock-volatility-risk-beta",
    source_kind="paper",
    source_ref=(
        "Ang, Hodrick, Xing & Zhang (2006), The Cross-Section of Volatility and Expected Returns, "
        "JF 61(1)"
    ),
    parent_id=None,
    hypothesis=(
        "Ang, Hodrick, Xing and Zhang (published 2006, so 2006-2015 of the dev window is after "
        "publication and the edge may have faded) find that stocks whose returns rise when market "
        "volatility jumps earn less, because investors pay for that insurance, so the stocks with "
        "the most negative loading on daily fear-index changes earn more (about 1% a month "
        "between extreme quintiles in their sample). Unlike coskewness, which the lab twice found "
        "to be a high-beta, regime-bound tilt (M0179, M0185), this reads a stock's exposure to "
        "fear itself, beyond its market beta. On the last close of each quarter, among members "
        "passing F4's $5 / $20M screen, regress 252 daily log returns on SPY's daily log return "
        "and the daily VIX change in points (one shared fit, so the VIX loading is net of beta); "
        "hold the 20 most negative loadings at 1/20 each, keep a holding while its rank fraction "
        "stays under 40%, unfilled slots in SPY, fractional shares at Gotrade's real fees on the "
        "owner's deposits. Variants: N20 (the idea), N40 (a 40-name rung), P20 (control: the 20 "
        "most positive loadings, the fear hedges), N20-SW (behind F4's SPY-200 switch), N20-MB "
        "(ranked only among members whose market beta is within 0.25 of 1, so the book cannot be "
        "a beta tilt). Success: N20 or N20-SW beats total-return SPY with worst fall <= 25%, "
        "PF >= 1.3, a majority of walk-forward folds and a positive 2009-2015 edge, P20 trails it "
        "clearly, and N20-MB keeps most of the gap (the edge is not beta)."
    ),
    expected_failure=(
        "The VIX loading is beta in disguise, with an era-dependent sign. Daily VIX changes and "
        "SPY's return move together (correlation near -0.7), so the partial loading is collinear "
        "with beta. A ranking probe run before this file was committed (rankings only, no "
        "returns) showed it: on 2008-06-30 the loading and beta correlate at 0.81 across members, "
        "the 20 most negative loadings average beta 0.49 and the 20 most positive 2.34 "
        "(homebuilders, Fannie, Freddie, Citi); on 1999-12-31 the correlation is 0.18 and on "
        "2013-12-31 0.35. So N20 is mostly a low-beta book in stressed years and a mixed one in "
        "calm years, the control P20 is a leveraged-financials bet, and the gap between them is "
        "the low-beta anomaly (already in the lab as calm stocks) plus 2008. Expect N20 to fall "
        "less than SPY in 2008 but trail it in the 1995-1999 and 2009-2015 rallies, failing "
        "'beats SPY'; N20-MB, with beta held near 1, loses most of the gap to P20. The published "
        "premium lives in small stocks and is post-publication from 2006; among index members it "
        "may be gone, and an equal-weight 20-name book loses to SPY's big-company drift."
    ),
    candidates=(
        _v("N20", VixBetaParams(_screen(20)),
           "The 20 most negative VIX-loading members, quarterly, kept under 40%, no switch"),
        _v("N40", VixBetaParams(_screen(40)),
           "A 40-name rung of the negative VIX-loading book, no switch"),
        _v("P20", VixBetaParams(_screen(20), positive=True),
           "Control: the 20 most positive VIX-loading members (the fear hedges), same band"),
        _v("N20-SW", VixBetaParams(_screen(20, SW)),
           "The negative VIX-loading book behind the SPY 200-day switch"),
        _v("N20-MB", VixBetaParams(_screen(20), beta_band_pct=25),
           "Ranked only among members with market beta within 0.25 of 1: the edge without beta"),
    ),
    seen_keys=(
        "concept:aggregate-volatility-risk",
        "concept:vix-beta",
    ),
)
