"""M0174 — Companies that move least with the rest of the market: low correlation, not low volatility.

Source: Asness, Frazzini, Gormsen & Pedersen (2020), "Betting against correlation: Testing theories
of the low-risk effect", Journal of Financial Economics 135(3), doi:10.1016/j.jfineco.2019.07.003.
The quarterly, banded frame borrows M0169's (F4's member screen, a keep band, slots left over in
SPY).
Idea: a stock's beta is its volatility times its correlation with the market. Low-volatility books
are already in this lab; AFGP's point is that the correlation half earns a premium on its own once
volatility is held fixed, which they read as leverage-constrained investors overpaying for the
names that move with the market. Han et al. argue much of it is a small-company effect, so among
index members it should be weaker; this book is a direct test on big companies.

The signal. On a re-pick date d, take SPY's last 3 * 252 + 3 sessions through d and each member's
last close on or before each of those dates. Correlation = Pearson correlation of the member's
overlapping 3-day log returns with SPY's (AFGP's overlapping-3-day construction, which absorbs
non-synchronous closes) over those 3 years. Volatility = standard deviation of the member's last
252 daily log returns. A member needs a bar dated d and history back past the window's first date.

The ranking. ``neutral`` (the idea): split the scored members into volatility terciles, rank each
tercile by correlation, and score each member by its rank inside its tercile as a fraction (0 =
lowest correlation of its tercile). Ranking everyone by that fraction takes the lowest-correlation
names from each tercile in turn, so the book holds calm, middling and jumpy stocks alike and is
not a low-volatility book. With ``neutral`` off the fraction is the plain correlation rank across
everyone. ``high`` flips the correlation order (the control: the names that move most with SPY).

The band. On the last close of March, June, September and December the book re-ranks; a held name
whose fraction is under ``keep_pct`` percent stays, the rest are sold, free slots filled from the
top. Between re-picks a holding leaves only when it stops being a member or loses its bar, its slot
sitting in SPY. A book holding no stock picks in full at once. With ``inner.trend`` set the whole
book is cash while SPY is under its 200-day average.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
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
HORIZON = 3  # sessions per overlapping return
CORR_N = 3 * 252  # sessions of 3-day returns in the correlation
VOL_N = 252  # daily returns in the volatility
SPAN = CORR_N + HORIZON  # sessions back from d to the window's first close
REPICK_MONTHS = (3, 6, 9, 12)


@dataclass(frozen=True, slots=True)
class CorrParams:
    """``inner`` is F4's screen, book size and optional switch; ``keep_pct`` the rank fraction (in
    percent) a holding must stay under; ``neutral`` ranks inside volatility terciles; ``high``
    ranks the most correlated first (the control)."""

    inner: FactorParams
    keep_pct: int = 40
    neutral: bool = True
    high: bool = False
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.keep_pct, bool) or not isinstance(self.keep_pct, int):
            raise TypeError(f"keep_pct must be an int, got {type(self.keep_pct).__name__}")
        if not 0 < self.keep_pct <= 100:
            raise ValueError(f"keep_pct must be in (0, 100], got {self.keep_pct}")
        for name in ("neutral", "high"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool, got {type(getattr(self, name)).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep_pct": str(self.keep_pct), "neutral": str(self.neutral).lower(),
               "high": str(self.high).lower(), "market": self.market,
               "horizon": str(HORIZON), "corr_n": str(CORR_N), "vol_n": str(VOL_N),
               "repick_months": ",".join(str(m) for m in REPICK_MONTHS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CorrParams:
    if not isinstance(params, CorrParams):
        raise TypeError(f"params must be CorrParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class CorrPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared | None


def features(history: Mapping[str, History], symbols: list[str], data_date: date,
             market: str) -> dict[str, tuple[float, float]]:
    """Each symbol's (correlation with ``market``, volatility) on ``data_date``; unscoreable left out."""
    mh = history.get(market)
    if mh is None:
        return {}
    i = mh.index_of(data_date)
    if i is None or i < SPAN:
        return {}
    when = mh.dates[i - SPAN: i + 1]
    lm = np.log(mh.close[i - SPAN: i + 1])
    m3 = lm[HORIZON:] - lm[:-HORIZON]
    mz = m3 - m3.mean()
    msd = float(np.sqrt((mz * mz).sum()))
    if not msd > 0.0:
        return {}
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
        lc = np.log(c)
        r3 = lc[HORIZON:] - lc[:-HORIZON]
        z = r3 - r3.mean()
        sd = float(np.sqrt((z * z).sum()))
        if not sd > 0.0:
            continue
        rho = float((z * mz).sum() / (sd * msd))
        vol = float(np.std(np.diff(lc[-(VOL_N + 1):]), ddof=1))
        if np.isfinite(rho) and np.isfinite(vol):
            out[s] = (rho, vol)
    return out


def scored(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: CorrParams) -> dict[str, float]:
    """Each eligible symbol's rank fraction in [0, 1): 0 is the first name the book wants."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    feat = features(history, pool, data_date, p.market)
    if not feat:
        return {}
    sign = -1.0 if p.high else 1.0
    if p.neutral:
        by_vol = sorted(feat, key=lambda s: (feat[s][1], s))
        n = len(by_vol)
        groups = [by_vol[k * n // 3: (k + 1) * n // 3] for k in range(3)]
    else:
        groups = [sorted(feat)]
    out: dict[str, float] = {}
    for g in groups:
        order = sorted(g, key=lambda s: (sign * feat[s][0], s))
        for k, s in enumerate(order):
            out[s] = k / len(order)
    return out


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: CorrParams) -> tuple[Target, ...]:
    stocks = sorted(s for s in held if s != p.market and s not in EXCLUDED)
    if not stocks or data_date.month in REPICK_MONTHS:
        frac = scored(history, rows, data_date, p)
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


class CorrAllocator:
    """The screened members least correlated with SPY inside their volatility tercile, quarterly."""

    id = "M0174"

    def lookback(self, params: Any) -> int:
        # As M0069: the screen's and the switch's need only, not the 3-year correlation window. A
        # member without SPAN + 1 bars is not scored yet and its slot holds SPY; declaring SPAN here
        # would only push the run's start past MEMBERSHIP_START for no gain (SPY has the 3 years
        # by January 1996).
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

    def _run(self, prepared: CorrPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CorrParams) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, members, rows, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(CorrPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CorrPrepared:
        return CorrPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CorrPrepared):
            raise TypeError(f"prepared must be CorrPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


CORR = CorrAllocator()


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: CorrParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0174-{suffix}", family="M0174", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CORR, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


SW = ("SPY", 200)

METHOD = Method(
    id="M0174",
    name=(
        "Companies that move least with the rest of the market: low correlation, not low "
        "volatility (betting against correlation)"
    ),
    family="stock-low-correlation",
    source_kind="paper",
    source_ref=(
        "Asness, Frazzini, Gormsen & Pedersen (2020), Betting against correlation: Testing "
        "theories of the low-risk effect, JFE 135(3), doi:10.1016/j.jfineco.2019.07.003"
    ),
    parent_id=None,
    hypothesis=(
        "AFGP (circulated 2017, published 2020, so the whole dev window predates the paper, though "
        "betting against beta, its parent, was public from 2010) split the low-risk effect into "
        "volatility and correlation: within volatility buckets, stocks with low correlation to the "
        "market earn more, which they read as leverage-constrained investors overpaying for "
        "high-correlation names. Han et al. argue much of it is a size effect, so among S&P 500 / "
        "Nasdaq-100 members it should be weaker; this is a direct test on big companies. On the "
        "last close of each quarter, among members passing F4's $5 / $20M screen, compute each "
        "one's correlation with SPY from 3 years of overlapping 3-day log returns and its 1-year "
        "daily volatility; rank by correlation inside each volatility tercile (rank fraction, 0 = "
        "lowest), hold the 20 with the lowest fraction at 1/20 each (so about a third from each "
        "tercile: not a low-volatility book), keep a holding while its fraction stays under 40%, "
        "unfilled slots in SPY, fractional shares at Gotrade's real fees on the owner's deposits. "
        "Variants: C20 (the idea, no switch), C20-SW (behind F4's SPY-200 switch), C40-SW (a "
        "40-name rung), H20-SW (control: the 20 highest-correlation, same band and switch), "
        "P20-SW (plain lowest correlation across everyone, no tercile split, to show what the "
        "split adds). Success: C20-SW beats total-return SPY with worst fall <= 25%, PF >= 1.3, a "
        "majority of walk-forward folds and a positive 2009-2015 edge, and H20-SW trails it "
        "clearly."
    ),
    expected_failure=(
        "Among big companies low correlation is mostly utilities, staples, gold miners and odd "
        "one-offs, even inside a volatility tercile, so the book is a defensive sector bet that "
        "ties SPY in bad years and trails it badly in the 2009-2015 rise, like the lab's earlier "
        "calm-stock books; the high-correlation control (tech and financials) wins the 1990s and "
        "2009-2015 and loses 2000-2002 and 2008, so the pair's gap is a sector cycle, not a "
        "premium. Low correlation also tends to mean thin, less followed members, so the book "
        "leans small and loses to SPY's big-company drift, and survivorship may flatter it."
    ),
    candidates=(
        _v("C20", CorrParams(_screen(20)),
           "The 20 lowest-correlation members inside their volatility tercile, quarterly, kept under 40%, no switch"),
        _v("C20-SW", CorrParams(_screen(20, SW)),
           "The same quarterly banded low-correlation book behind the SPY 200-day switch"),
        _v("C40-SW", CorrParams(_screen(40, SW)),
           "A 40-name rung of the low-correlation book behind the switch"),
        _v("H20-SW", CorrParams(_screen(20, SW), high=True),
           "Control: the 20 highest-correlation members inside their volatility tercile, same band and switch"),
        _v("P20-SW", CorrParams(_screen(20, SW), neutral=False),
           "Plain lowest correlation across all members (no volatility split) behind the switch"),
    ),
    seen_keys=(
        "concept:betting-against-correlation",
        "concept:low-market-correlation",
        "concept:volatility-neutral-low-risk",
    ),
)
