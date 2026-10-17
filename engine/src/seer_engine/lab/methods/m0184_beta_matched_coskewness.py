"""M0184 — Is coskewness just a riskier book? Rank by coskewness only among stocks that swing about
as much as the market (beta-matched coskewness).

Source: variation of M0179 (Harvey & Siddique 2000, JF 55(3)), owner-directed coskewness batch of
2026-10-17. The quarterly, banded frame, the member screen and the coskewness formula are M0179's.
Idea: M0179's most-negative-coskewness book beat SPY over 1996-2015 but fell 52% in 2008 with no
switch, which is what a high-beta book does. Standardized coskewness is computed on the CAPM
residual, so it is beta-free as a number, but the ranked book can still load on beta: the stocks
whose residuals fall in the market's big weeks are mostly cyclicals, financials and 2000-era tech.
This method holds beta fixed and asks whether the ranking still separates anything.

The measures. On a re-pick date d, from the same WEEKS non-overlapping weekly log returns M0179
uses (every fifth close counting back from d), each member's beta to SPY (cov(z, m) / var(m), the
same number M0179's residual subtracts) and its standardized coskewness (HS eq. 11). Beta is read
from the same three-year weekly window, not the idea row's 60-month monthly one: one window keeps
the two measures on the same weeks, and 156 weekly points estimate beta at least as well as 60
monthly ones (an assumption, written down before the run).

The ranking. ``match = "tercile"``: the scoreable members are cut into three equal beta buckets
(low, middle, high); within each bucket they are ranked by coskewness, most negative first, and a
name's rank fraction is its place within its own bucket. Picks are taken in order of that
fraction, so the book holds about a third of its names from each bucket and its beta sits near
the members' average whatever coskewness does. ``match = "band"``: only members with beta in
[BAND_LO, BAND_HI] are ranked, the rest are not eligible. ``positive`` flips the coskewness order
(the paired control: the names that hold up best in market extremes, same buckets).

The band. As M0179: on the last close of March, June, September and December the book re-ranks; a
held name whose fraction is under ``keep_pct`` percent stays, the rest are sold, free slots filled
from the top. Between re-picks a holding leaves only when it stops being a member or loses its bar,
its slot sitting in SPY. With ``inner.trend`` set the whole book is cash while SPY is under its
200-day average.

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
STEP = 5  # sessions per weekly return
WEEKS = 156  # three years of weekly returns
SPAN = WEEKS * STEP  # sessions back from d to the window's first close
REPICK_MONTHS = (3, 6, 9, 12)
BUCKETS = 3
BAND_LO = 0.8
BAND_HI = 1.2
MATCHES = ("tercile", "band")


@dataclass(frozen=True, slots=True)
class BetaCoskewParams:
    """``inner`` is F4's screen, book size and optional switch; ``match`` how beta is held fixed
    (``tercile`` ranks within three beta buckets, ``band`` keeps only betas in the band);
    ``keep_pct`` the rank fraction (in percent) a holding must stay under; ``positive`` ranks the
    most positive coskewness first (the control)."""

    inner: FactorParams
    match: str = "tercile"
    keep_pct: int = 40
    positive: bool = False
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.match not in MATCHES:
            raise ValueError(f"match must be one of {MATCHES}, got {self.match!r}")
        if isinstance(self.keep_pct, bool) or not isinstance(self.keep_pct, int):
            raise TypeError(f"keep_pct must be an int, got {type(self.keep_pct).__name__}")
        if not 0 < self.keep_pct <= 100:
            raise ValueError(f"keep_pct must be in (0, 100], got {self.keep_pct}")
        if not isinstance(self.positive, bool):
            raise TypeError(f"positive must be a bool, got {type(self.positive).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"match": self.match, "keep_pct": str(self.keep_pct),
               "positive": str(self.positive).lower(), "market": self.market,
               "step": str(STEP), "weeks": str(WEEKS), "buckets": str(BUCKETS),
               "band": f"{BAND_LO},{BAND_HI}",
               "repick_months": ",".join(str(m) for m in REPICK_MONTHS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> BetaCoskewParams:
    if not isinstance(params, BetaCoskewParams):
        raise TypeError(f"params must be BetaCoskewParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class BetaCoskewPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared | None


def measures(history: Mapping[str, History], symbols: list[str], data_date: date,
             market: str) -> dict[str, tuple[float, float]]:
    """Each symbol's (beta, standardized coskewness) with ``market`` on ``data_date``, from the
    same weekly window as M0179; unscoreable symbols left out."""
    mh = history.get(market)
    if mh is None:
        return {}
    i = mh.index_of(data_date)
    if i is None or i < SPAN:
        return {}
    when = mh.dates[i - SPAN: i + 1: STEP]
    rm = np.diff(np.log(mh.close[i - SPAN: i + 1: STEP]))
    m = rm - rm.mean()
    m2 = m * m
    var_m = float(m2.mean())
    if not var_m > 0.0:
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
        r = np.diff(np.log(c))
        z = r - r.mean()
        beta = float((z * m).mean()) / var_m
        e = z - beta * m
        se = float(np.sqrt((e * e).mean()))
        if not se > 0.0:
            continue
        v = float((e * m2).mean()) / (se * var_m)
        if np.isfinite(v) and np.isfinite(beta):
            out[s] = (beta, v)
    return out


def scored(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: BetaCoskewParams) -> dict[str, float]:
    """Each eligible symbol's rank fraction in [0, 1): 0 is among the first names the book wants.

    Tercile: the fraction is the name's place within its own beta bucket, so the first names of
    all three buckets share fraction 0 and the book draws evenly from them. Band: the place among
    the in-band names."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    ms = measures(history, pool, data_date, p.market)
    if not ms:
        return {}
    sign = -1.0 if p.positive else 1.0
    if p.match == "band":
        groups = [[s for s in ms if BAND_LO <= ms[s][0] <= BAND_HI]]
    else:
        by_beta = sorted(ms, key=lambda s: (ms[s][0], s))
        n = len(by_beta)
        groups = [by_beta[k * n // BUCKETS: (k + 1) * n // BUCKETS] for k in range(BUCKETS)]
    out: dict[str, float] = {}
    for g in groups:
        order = sorted(g, key=lambda s: (sign * ms[s][1], s))
        for k, s in enumerate(order):
            out[s] = k / len(order)
    return out


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: BetaCoskewParams) -> tuple[Target, ...]:
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


class BetaCoskewAllocator:
    """Screened members ranked by coskewness with SPY within beta buckets (or a beta band),
    quarterly, banded."""

    id = "M0184"

    def lookback(self, params: Any) -> int:
        # As M0179: the screen's and the switch's need only, not the 3-year window. A member
        # without SPAN + 1 bars is not scored yet and its slot holds SPY.
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

    def _run(self, prepared: BetaCoskewPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: BetaCoskewParams) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, members, rows, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(BetaCoskewPrepared(history, None), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> BetaCoskewPrepared:
        return BetaCoskewPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BetaCoskewPrepared):
            raise TypeError(f"prepared must be BetaCoskewPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


BETA_COSKEW = BetaCoskewAllocator()


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: BetaCoskewParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0184-{suffix}", family="M0184", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BETA_COSKEW, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


SW = ("SPY", 200)

METHOD = Method(
    id="M0184",
    name=(
        "Is coskewness just a riskier book? Rank by coskewness only among stocks that swing "
        "about as much as the market"
    ),
    family="stock-coskewness",
    source_kind="variation",
    source_ref=(
        "variation of M0179 (Harvey & Siddique 2000, JF 55(3)); owner-directed coskewness batch "
        "2026-10-17"
    ),
    parent_id="M0179",
    hypothesis=(
        "Harvey and Siddique (published 2000) price coskewness net of beta, but M0179's ranked "
        "book of the most negative-coskewness members may still be a disguised high-beta bet: it "
        "beat SPY over 1996-2015 on average and fell 52% in 2008 without the switch. Hold beta "
        "fixed and see whether the ranking still separates. Each quarter, among members passing "
        "F4's $5 / $20M screen, measure beta to SPY and standardized coskewness (HS eq. 11) from "
        "the same 156 weekly log returns M0179 uses (beta from that three-year weekly window, not "
        "a 60-month monthly one, so both measures share the same weeks: an assumption). Tercile "
        "match: cut the scored members into three equal beta buckets, rank coskewness most "
        "negative first within each bucket, and pick by within-bucket place, so about a third of "
        "the book comes from each bucket. Band match: rank only members with beta between 0.8 "
        "and 1.2. Hold 20 or 40 at equal weight, keep a holding while its fraction stays under "
        "40%, unfilled slots in SPY, quarterly, fractional shares at Gotrade's real fees on the "
        "owner's monthly top-up. Variants: T20 (tercile, no switch), T20-SW (behind F4's SPY "
        "200-day switch), T40-SW (40 names), B20 (band, no switch), and the paired controls "
        "TP20 and TP20-SW (most positive coskewness within the same buckets, matching T20 and "
        "T20-SW), kept in the pool so the walk-forward selection can pick against the idea. "
        "Every variant's own beta to SPY is reported, and M0179-N20 and M0179-N40-SW are shown "
        "beside the results. Designed only from the dev window: the owner's 2018-2026 run of "
        "M0179 is known and chose nothing here. Success: T20 or T20-SW beats total-return SPY "
        "with worst fall <= 25%, PF >= 1.3, a majority of walk-forward folds, a positive "
        "2009-2015 edge, and its paired control trails it clearly."
    ),
    expected_failure=(
        "Once beta is matched the spread between the negative and positive books collapses, "
        "because M0179's gap was a high-beta tilt riding the late-1990s and 2003-2007 runs; then "
        "the coskewness family is closed as a stock picker. The beta-matched books still hold "
        "20-40 equal-weighted members, so they keep the equal-weight lean against SPY's "
        "big-company drift and trail SPY in 2009-2015 regardless. The walk-forward again picks "
        "the control in some folds, as it did for M0179 and the low-correlation book, and the "
        "gate refuses on folds. A published anomaly (2000) is likely to have faded inside the "
        "dev window already, and three-year weekly coskewness is noisy, dominated by one or two "
        "crash weeks."
    ),
    candidates=(
        _v("T20", BetaCoskewParams(_screen(20)),
           "The most negative-coskewness members within each beta third, 20 names, no switch"),
        _v("T20-SW", BetaCoskewParams(_screen(20, SW)),
           "The same beta-matched book behind the SPY 200-day switch"),
        _v("T40-SW", BetaCoskewParams(_screen(40, SW)),
           "A 40-name rung of the beta-matched book behind the switch"),
        _v("B20", BetaCoskewParams(_screen(20), match="band"),
           "The most negative coskewness among members with beta 0.8 to 1.2, no switch"),
        _v("TP20", BetaCoskewParams(_screen(20), positive=True),
           "Control for T20: the most positive coskewness within each beta third, no switch"),
        _v("TP20-SW", BetaCoskewParams(_screen(20, SW), positive=True),
           "Control for T20-SW: the most positive within each beta third, behind the switch"),
    ),
    seen_keys=(
        "concept:beta-matched-coskewness",
        "concept:coskewness-net-of-beta",
    ),
)
