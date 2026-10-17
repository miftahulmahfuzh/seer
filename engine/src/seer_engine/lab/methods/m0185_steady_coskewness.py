"""M0185 — A steadier coskewness signal: longer windows and ranks averaged over a year, so the picks
stop flipping.

Source: variation of M0179 (Harvey & Siddique 2000, "Conditional Skewness in Asset Pricing Tests",
JF 55(3)), owner-directed coskewness batch of 2026-10-17. The quarterly, banded frame is M0179's.
Idea: in every walk-forward fold M0179's selection preferred its positive-coskewness control, so
the edge did not carry from one stretch to the next. Part of that may be estimation noise: a third
moment from 156 weekly returns is dominated by one or two crash weeks, so each quarter's ranking
mostly re-sorts by the last shock's losers. Two smoothers, isolated and combined: a five-year
window (260 weekly returns), and each stock's rank averaged over the last four quarters.

The signal. As M0179's standardized coskewness (HS eq. 11), with the window ``weeks`` long: on a
scoring date take SPY's last ``weeks * 5 + 1`` sessions and sample every fifth close back from it;
each member's last close on or before each sampled date gives its weekly log returns. With the
market's demeaned return m and the member's CAPM residual e, coskewness = mean(e * m^2) /
(sqrt(mean(e^2)) * mean(m^2)). The raw-slope score (M0179-G20-SW) is not carried over: it scales
with the stock's own volatility, which is the beta question M0184 owns.

The smoothing. With ``quarters`` = 4, a re-pick date d is scored at d and at the SPY sessions 63,
126 and 189 before it, each among the same pool (today's screened members). Each date's scores
become rank fractions in [0, 1); a member's fractions are averaged over the dates it could be
scored on (it must be scoreable at d itself), and the averages are ranked again, so the keep band
reads the same 40% of the pool however many dates were averaged. Every scoring date is <= d, so
the averaging reads nothing new: it is the ranking the book would have seen on those dates, held
over. Only today's pool is ranked at every lag (an assumption): a name screened out a quarter ago
but screened in today is still judged on its old behaviour, which is what the signal measures.

The window's cost. Five years of weekly returns need bars from 1991 for a 1996 score; the store
starts in 1993, so until about 1998 no member is scoreable and the book sits in SPY (and with the
averaging, the early years rank on fewer lags). This is the idea's price, not a bug, and it is
named in the expected failure: the 1990s boom, where M0179 earned part of its lead, is mostly SPY.

The ranking, band and switch are M0179's: re-pick on the last close of each quarter; a holding
stays while its fraction is under ``keep_pct`` percent; between re-picks a holding leaves only when
it stops being a member or loses its bar; unfilled slots sit in SPY; with ``inner.trend`` set the
whole book is cash while SPY is under its 200-day average. ``positive`` ranks the most positive
first (the paired control, Sera rule since M0178).

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
QUARTER = 63  # sessions between averaged scoring dates
REPICK_MONTHS = (3, 6, 9, 12)


@dataclass(frozen=True, slots=True)
class SteadyParams:
    """``inner`` is F4's screen, book size and optional switch; ``weeks`` the coskewness window in
    weekly returns; ``quarters`` how many quarterly scoring dates the rank is averaged over (1 is
    no averaging); ``keep_pct`` the rank fraction (in percent) a holding must stay under;
    ``positive`` ranks the most positive first (the control)."""

    inner: FactorParams
    weeks: int = 260
    quarters: int = 4
    keep_pct: int = 40
    positive: bool = False
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name, lo, hi in (("weeks", 26, 520), ("quarters", 1, 8), ("keep_pct", 1, 100)):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
            if not lo <= v <= hi:
                raise ValueError(f"{name} must be in [{lo}, {hi}], got {v}")
        if not isinstance(self.positive, bool):
            raise TypeError(f"positive must be a bool, got {type(self.positive).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"weeks": str(self.weeks), "quarters": str(self.quarters),
               "keep_pct": str(self.keep_pct), "positive": str(self.positive).lower(),
               "market": self.market, "step": str(STEP), "quarter_sessions": str(QUARTER),
               "repick_months": ",".join(str(m) for m in REPICK_MONTHS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SteadyParams:
    if not isinstance(params, SteadyParams):
        raise TypeError(f"params must be SteadyParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class SteadyPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared | None


def coskewness_at(history: Mapping[str, History], symbols: list[str], data_date: date, lag: int,
                  weeks: int, market: str) -> dict[str, float]:
    """Each symbol's standardized coskewness with ``market`` over the ``weeks`` weekly returns
    ending ``lag`` market sessions before ``data_date``; unscoreable symbols left out. Only bars
    dated <= ``data_date`` are read."""
    mh = history.get(market)
    if mh is None:
        return {}
    i0 = mh.index_of(data_date)
    span = weeks * STEP
    if i0 is None:
        return {}
    i = i0 - lag
    if i < span:
        return {}
    when = mh.dates[i - span: i + 1: STEP]
    rm = np.diff(np.log(mh.close[i - span: i + 1: STEP]))
    m = rm - rm.mean()
    m2 = m * m
    var_m = float(m2.mean())
    if not var_m > 0.0:
        return {}
    out: dict[str, float] = {}
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
        e = z - (float((z * m).mean()) / var_m) * m
        se = float(np.sqrt((e * e).mean()))
        if not se > 0.0:
            continue
        v = float((e * m2).mean()) / (se * var_m)
        if np.isfinite(v):
            out[s] = v
    return out


def _fractions(score: Mapping[str, float]) -> dict[str, float]:
    order = sorted(score, key=lambda s: (score[s], s))
    return {s: k / len(order) for k, s in enumerate(order)}


def scored(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: SteadyParams) -> dict[str, float]:
    """Each eligible symbol's rank fraction in [0, 1): 0 is the first name the book wants."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    sign = -1.0 if p.positive else 1.0
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for q in range(p.quarters):
        cs = coskewness_at(history, pool, data_date, q * QUARTER, p.weeks, p.market)
        if q == 0:
            pool = sorted(cs)  # a member must be scoreable today
        if not cs:
            if q == 0:
                return {}
            continue
        for s, f in _fractions({s: sign * v for s, v in cs.items() if s in pool}).items():
            sums[s] = sums.get(s, 0.0) + f
            counts[s] = counts.get(s, 0) + 1
    return _fractions({s: sums[s] / counts[s] for s in sums})


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: SteadyParams) -> tuple[Target, ...]:
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


class SteadyCoskewAllocator:
    """The screened members with the most negative smoothed coskewness with SPY, quarterly,
    banded."""

    id = "M0185"

    def lookback(self, params: Any) -> int:
        # As M0179: the screen's and the switch's need only, not the five-year window. A member
        # without the window's bars is not scored yet and its slot holds SPY.
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

    def _run(self, prepared: SteadyPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SteadyParams) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, members, rows, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(SteadyPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> SteadyPrepared:
        return SteadyPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SteadyPrepared):
            raise TypeError(f"prepared must be SteadyPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


STEADY = SteadyCoskewAllocator()


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: SteadyParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0185-{suffix}", family="M0185", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=STEADY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


SW = ("SPY", 200)

METHOD = Method(
    id="M0185",
    name=(
        "A steadier coskewness signal: longer windows and ranks averaged over a year, so the "
        "picks stop flipping"
    ),
    family="stock-coskewness",
    source_kind="variation",
    source_ref=(
        "variation of M0179 (Harvey & Siddique 2000, Conditional Skewness in Asset Pricing "
        "Tests, JF 55(3)); owner-directed coskewness batch 2026-10-17"
    ),
    parent_id="M0179",
    hypothesis=(
        "In every walk-forward fold M0179's selection preferred its positive-coskewness control, "
        "so the edge did not carry from one stretch to the next. Part of that may be noise: a "
        "third moment from 156 weekly returns is dominated by one or two crash weeks. Smooth it "
        "two ways, isolated and combined: a five-year window (260 weekly returns), and each "
        "stock's rank averaged over its last four quarterly scorings (today and 63, 126, 189 "
        "sessions back, among today's screened pool, re-ranked so the 40% keep band means the "
        "same). Otherwise M0179's frame: F4's $5 / $20M screen, re-pick each quarter's last "
        "close, keep a holding under 40%, unfilled slots in SPY, fractional shares at Gotrade's "
        "real fees on the owner's monthly top-up. Variants: S20 (both smoothers, 20 names, no "
        "switch: the idea), S40-SW (both, 40 names, SPY 200-day switch: the shape that was "
        "eligible in M0179), W20 (five-year window only), A20 (three-year window, four-quarter "
        "average only), and the paired controls C20 and C40-SW (the most positive names, same "
        "smoothing, paired with S20 and S40-SW). Published 2000, so the dev window is mostly "
        "after publication. Designed from the dev window only; the owner's 2018-2026 run of "
        "M0179 chose nothing here. Report M0179-N20 and M0179-N40-SW beside the results and each "
        "variant's beta to SPY. Success: turnover falls against M0179, the dev edge over SPY TR "
        "holds with worst fall <= 25% (for the switched book), S beats its paired control, the "
        "walk-forward selection picks a negative-coskewness variant in a majority of folds and "
        "wins them, and the 2009-2015 edge is positive."
    ),
    expected_failure=(
        "The control's lead before each fold was real: crash-prone stocks pay only in a few "
        "episodes (the late 1990s boom, the 2003-2007 recovery) and smoothing cannot create "
        "persistence the premium does not have, so the folds stay split. A five-year window "
        "leaves the book in SPY until about 1998 (the store starts in 1993), cutting the 1990s "
        "years where M0179 earned part of its lead, so the twenty-year edge shrinks. A smoother "
        "rank sorts more steadily into high-beta cyclicals, so the no-switch books still fall "
        "near 50% in 2008 and the switched one trails SPY in 2009-2015 as M0179's did. The "
        "equal-weight book also bets against SPY's big-company drift, a published anomaly the "
        "lab expects to fade."
    ),
    candidates=(
        _v("S20", SteadyParams(_screen(20)),
           "Five-year window and four-quarter averaged rank, 20 names, no switch: the idea"),
        _v("S40-SW", SteadyParams(_screen(40, SW)),
           "Both smoothers, 40 names, behind the SPY 200-day switch"),
        _v("W20", SteadyParams(_screen(20), quarters=1),
           "Five-year window only, no rank averaging, 20 names, no switch"),
        _v("A20", SteadyParams(_screen(20), weeks=156),
           "M0179's three-year window with the four-quarter averaged rank, 20 names, no switch"),
        _v("C20", SteadyParams(_screen(20), positive=True),
           "Control paired with S20: the 20 most positive, same smoothing, no switch"),
        _v("C40-SW", SteadyParams(_screen(40, SW), positive=True),
           "Control paired with S40-SW: the 40 most positive, same smoothing, behind the switch"),
    ),
    seen_keys=(
        "concept:coskewness-smoothed",
        "concept:rank-averaging",
    ),
)
