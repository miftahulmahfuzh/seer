"""M0188 — Steady beaters at market risk: the members with the highest three-year lead over SPY
after their beta, beta kept near one.

Source: variation of M0180 (and its parent M0179), Sera batch 20261017-1752; CAPM alpha as a
stock-level ranking is textbook (Jensen 1968), and its persistence in single stocks is weak in the
literature; a three-year winner screen overlaps long-term reversal (De Bondt & Thaler 1985).
Idea: the coskewness books earned their lead over SPY from the equal-weight shape, not the signal
(M0184: the idea and its opposite earned the same month by month). Rank on what is left after
market risk instead: each member's three-year weekly CAPM alpha, among members whose beta is near
one, so the book carries about SPY's risk and cannot win by being a high-beta book.

The measures. On a re-pick date d, from WEEKS non-overlapping weekly log returns (every fifth
close counting back from d, M0179's and M0184's window), each member's beta to SPY
(cov(z, m) / var(m)), its alpha (mean(r) - beta * mean(m), weekly, in log units) and its alpha
t-statistic (alpha over its OLS standard error, se_e * sqrt(1/n + mean(m)^2 / (n var(m))), with
se_e the residual standard deviation). Alpha is measured on raw returns, not returns over
Treasury bills: with beta held between BAND_LO and BAND_HI the bill rate shifts every name by
(1 - beta) * rf, at most 0.2 * rf a year, which is small beside the cross-section of three-year
alphas (an assumption written before the run).

The ranking. Only members with beta in [BAND_LO, BAND_HI] are eligible. ``score = "alpha"`` ranks
them by alpha, highest first; ``score = "tstat"`` by the alpha t-statistic, the steadier version
(a large alpha from one wild year scores low). ``low`` flips the order: the paired control holds
the lowest-alpha names in the same band.

The band. As M0184: on the last close of March, June, September and December the book re-ranks; a
held name whose rank fraction is under ``keep_pct`` percent stays, the rest are sold, free slots
filled from the top. Between re-picks a holding leaves only when it stops being a member or loses
its bar, its slot sitting in SPY. No market switch: the idea row asks for none, and every switch in
the lab has cost the 2009-2015 years.

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
BAND_LO = 0.8
BAND_HI = 1.2
SCORES = ("alpha", "tstat")


@dataclass(frozen=True, slots=True)
class SteadyAlphaParams:
    """``inner`` is F4's screen and book size; ``score`` what is ranked (``alpha`` or its
    ``tstat``); ``keep_pct`` the rank fraction (in percent) a holding must stay under; ``low``
    ranks the lowest first (the control)."""

    inner: FactorParams
    score: str = "alpha"
    keep_pct: int = 40
    low: bool = False
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.score not in SCORES:
            raise ValueError(f"score must be one of {SCORES}, got {self.score!r}")
        if isinstance(self.keep_pct, bool) or not isinstance(self.keep_pct, int):
            raise TypeError(f"keep_pct must be an int, got {type(self.keep_pct).__name__}")
        if not 0 < self.keep_pct <= 100:
            raise ValueError(f"keep_pct must be in (0, 100], got {self.keep_pct}")
        if not isinstance(self.low, bool):
            raise TypeError(f"low must be a bool, got {type(self.low).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"score": self.score, "keep_pct": str(self.keep_pct),
               "low": str(self.low).lower(), "market": self.market,
               "step": str(STEP), "weeks": str(WEEKS), "band": f"{BAND_LO},{BAND_HI}",
               "repick_months": ",".join(str(m) for m in REPICK_MONTHS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SteadyAlphaParams:
    if not isinstance(params, SteadyAlphaParams):
        raise TypeError(f"params must be SteadyAlphaParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class SteadyAlphaPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared | None


def measures(history: Mapping[str, History], symbols: list[str], data_date: date,
             market: str) -> dict[str, tuple[float, float, float]]:
    """Each symbol's (beta, alpha, alpha t-statistic) against ``market`` on ``data_date``, from
    the weekly window; unscoreable symbols left out."""
    mh = history.get(market)
    if mh is None:
        return {}
    i = mh.index_of(data_date)
    if i is None or i < SPAN:
        return {}
    when = mh.dates[i - SPAN: i + 1: STEP]
    rm = np.diff(np.log(mh.close[i - SPAN: i + 1: STEP]))
    n = len(rm)
    mean_m = float(rm.mean())
    m = rm - mean_m
    var_m = float((m * m).mean())
    if not var_m > 0.0:
        return {}
    lever = np.sqrt(1.0 / n + mean_m * mean_m / (n * var_m))
    out: dict[str, tuple[float, float, float]] = {}
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
        mean_r = float(r.mean())
        z = r - mean_r
        beta = float((z * m).mean()) / var_m
        alpha = mean_r - beta * mean_m
        e = z - beta * m
        se = float(np.sqrt((e * e).sum() / (n - 2)))
        if not se > 0.0:
            continue
        t = alpha / (se * lever)
        if np.isfinite(beta) and np.isfinite(alpha) and np.isfinite(t):
            out[s] = (beta, alpha, float(t))
    return out


def scored(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: SteadyAlphaParams) -> dict[str, float]:
    """Each in-band symbol's rank fraction in [0, 1): 0 is the first name the book wants."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    ms = measures(history, pool, data_date, p.market)
    band = [s for s in ms if BAND_LO <= ms[s][0] <= BAND_HI]
    if not band:
        return {}
    k = 1 if p.score == "alpha" else 2
    sign = 1.0 if p.low else -1.0
    order = sorted(band, key=lambda s: (sign * ms[s][k], s))
    return {s: n / len(order) for n, s in enumerate(order)}


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: SteadyAlphaParams) -> tuple[Target, ...]:
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


class SteadyAlphaAllocator:
    """Screened members with beta to SPY near one, ranked by three-year weekly CAPM alpha (or its
    t-statistic), quarterly, banded."""

    id = "M0188"

    def lookback(self, params: Any) -> int:
        # As M0184: the screen's need only, not the 3-year window. A member without SPAN + 1 bars
        # is not scored yet and its slot holds SPY.
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

    def _run(self, prepared: SteadyAlphaPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SteadyAlphaParams) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, members, rows, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(SteadyAlphaPrepared(history, None), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> SteadyAlphaPrepared:
        return SteadyAlphaPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SteadyAlphaPrepared):
            raise TypeError(f"prepared must be SteadyAlphaPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


STEADY_ALPHA = SteadyAlphaAllocator()


def _screen(top: int) -> FactorParams:
    return FactorParams(rank="momentum", top=top)  # the rank is unused: only the screen


def _v(suffix: str, params: SteadyAlphaParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0188-{suffix}", family="M0188", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=STEADY_ALPHA, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0188",
    name=(
        "Steady beaters at market risk: the members with the highest three-year lead over SPY "
        "after their beta, beta kept near one"
    ),
    family="stock-alpha-persistence",
    source_kind="variation",
    source_ref=(
        "variation of M0180 (the coskewness frame of M0179/M0184, ranked on CAPM alpha instead); "
        "Jensen (1968) alpha; De Bondt & Thaler (1985) long-term reversal as the counter-claim"
    ),
    parent_id="M0180",
    hypothesis=(
        "The coskewness books (M0179, M0180, M0184) beat SPY over 1996-2015 from the equal-weight "
        "shape, not the signal: the idea and its opposite earned the same month by month. Rank "
        "members instead on what is left after market risk. Each quarter, among members passing "
        "F4's $5 / $20M screen, measure from 156 weekly log returns each member's beta to SPY, its "
        "CAPM alpha (mean return less beta times SPY's mean, on raw returns, not over bills: an "
        "assumption, small with beta near one) and the alpha's t-statistic. Keep only members "
        "with beta between 0.8 and 1.2, so the book carries about SPY's risk and cannot win by "
        "being high-beta. Hold the top 20 or 40 at equal weight, keep a holding while its rank "
        "fraction stays under 40%, unfilled slots in SPY, quarterly, no market switch, fractional "
        "shares at Gotrade's real fees on the owner's monthly top-up. Variants: A20 (highest "
        "alpha, 20 names), A40 (40 names), T20 and T40 (highest alpha t-statistic, the 'steady' "
        "reading, where one wild year cannot carry a name), and the paired control L20 (lowest "
        "alpha in the same band), kept in the pool so the walk-forward selection can pick against "
        "the idea. Alpha persistence in single stocks is a weak published idea (Jensen 1968 "
        "measured it in funds; the stock-level form is folklore, with long-term reversal, De "
        "Bondt and Thaler 1985, the published counter-claim). Designed from the dev window only. "
        "Success: A20 or T20 beats total-return SPY on the deposits with worst fall <= 25%, PF >= "
        "1.3, a majority of walk-forward folds, a positive 2009-2015 edge, and L20 trails it "
        "clearly month by month."
    ),
    expected_failure=(
        "Long-term reversal: a three-year alpha leader is a three-year winner, and past winners "
        "over three to five years tend to give back, so the high-alpha book trails its own "
        "low-alpha control, or matches it, as every control in the last three batches did. The "
        "book still holds 20-40 equal-weighted members, so it keeps the equal-weight lean "
        "against SPY's big-company drift and trails SPY in 2009-2015 whatever the ranking does. "
        "No switch means a 2008 fall near SPY's 55%, failing the 25% bar and the 50% dev screen "
        "if the band's names fall harder than SPY. Three-year alpha is noisy (its t-statistic "
        "rarely exceeds 2), so the T variants mostly re-sort noise. The walk-forward picks the "
        "control in some folds and the gate refuses on folds."
    ),
    candidates=(
        _v("A20", SteadyAlphaParams(_screen(20)),
           "The 20 members with the highest three-year alpha among betas 0.8 to 1.2"),
        _v("A40", SteadyAlphaParams(_screen(40)),
           "A 40-name rung of the same book"),
        _v("T20", SteadyAlphaParams(_screen(20), score="tstat"),
           "The 20 steadiest beaters: highest alpha t-statistic among betas 0.8 to 1.2"),
        _v("T40", SteadyAlphaParams(_screen(40), score="tstat"),
           "A 40-name rung of the steadiest beaters"),
        _v("L20", SteadyAlphaParams(_screen(20), low=True),
           "Control for A20: the 20 lowest three-year alphas in the same beta band"),
    ),
    seen_keys=(
        "concept:beta-banded-capm-alpha",
        "concept:stock-alpha-persistence",
        "concept:alpha-tstat-steady-beaters",
    ),
)
