"""M0179 — Companies that crash with the market: the stocks investors shun for falling hardest when
the market moves most (coskewness).

Source: Harvey & Siddique (2000), "Conditional Skewness in Asset Pricing Tests", Journal of Finance
55(3), 1263-1295; revisited in Critical Finance Review (2023). The quarterly, banded frame is
M0174's (F4's member screen, a keep band, slots left over in SPY).
Idea: investors like assets that pay off in the market's extremes and dislike those that do worst
when the market swings hardest, so a stock whose returns fall when the squared market return is
large (negative coskewness) should be priced lower and earn more. HS report about 3.6% a year for
the spread; this lab has never tested it, and it needs only daily prices and SPY.

The signal. On a re-pick date d, take SPY's last WEEKS * 5 + 1 sessions through d and sample every
fifth close counting back from d: WEEKS non-overlapping weekly log returns (weekly, not daily, so
non-synchronous closes matter less; weekly, not monthly, so three years give 156 points instead
of 36). Each member's last close on or before each sampled date gives its weekly returns. With the
market's demeaned return m and the member's CAPM residual e (its demeaned return less beta * m),
standardized coskewness (HS eq. 11) = mean(e * m^2) / (sqrt(mean(e^2)) * mean(m^2)). It is unit-free,
so the most negative names are not simply the most volatile ones. With ``gamma`` set the score is
instead the regression coefficient on m^2 in r = a + b*m + g*m^2 (the idea row's wording), which
scales with the stock's own volatility. Raw returns, not excess: a constant T-bill rate falls into
the intercept and the demeaning, and the 13-week rate barely moves within a week (an assumption).
A member needs a bar dated d and history back past the window's first date.

The ranking. Rank fraction in [0, 1), 0 = the most negative coskewness (the book's first pick);
``positive`` flips the order (the control: the names that hold up best in market extremes).

The band. As M0174: on the last close of March, June, September and December the book re-ranks; a
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


@dataclass(frozen=True, slots=True)
class CoskewParams:
    """``inner`` is F4's screen, book size and optional switch; ``keep_pct`` the rank fraction (in
    percent) a holding must stay under; ``gamma`` scores by the raw m^2 coefficient instead of
    standardized coskewness; ``positive`` ranks the most positive first (the control)."""

    inner: FactorParams
    keep_pct: int = 40
    gamma: bool = False
    positive: bool = False
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.keep_pct, bool) or not isinstance(self.keep_pct, int):
            raise TypeError(f"keep_pct must be an int, got {type(self.keep_pct).__name__}")
        if not 0 < self.keep_pct <= 100:
            raise ValueError(f"keep_pct must be in (0, 100], got {self.keep_pct}")
        for name in ("gamma", "positive"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool, got {type(getattr(self, name)).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep_pct": str(self.keep_pct), "gamma": str(self.gamma).lower(),
               "positive": str(self.positive).lower(), "market": self.market,
               "step": str(STEP), "weeks": str(WEEKS),
               "repick_months": ",".join(str(m) for m in REPICK_MONTHS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CoskewParams:
    if not isinstance(params, CoskewParams):
        raise TypeError(f"params must be CoskewParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class CoskewPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared | None


def coskewness(history: Mapping[str, History], symbols: list[str], data_date: date, market: str,
               gamma: bool) -> dict[str, float]:
    """Each symbol's coskewness with ``market`` on ``data_date``; unscoreable symbols left out."""
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
    if gamma:  # design matrix of r = a + b*m + g*m^2, shared by every member
        x = np.column_stack([np.ones_like(m), m, m2])
        xtx_inv = np.linalg.pinv(x.T @ x)
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
        if gamma:
            v = float((xtx_inv @ (x.T @ r))[2])
        else:
            z = r - r.mean()
            e = z - (float((z * m).mean()) / var_m) * m
            se = float(np.sqrt((e * e).mean()))
            if not se > 0.0:
                continue
            v = float((e * m2).mean()) / (se * var_m)
        if np.isfinite(v):
            out[s] = v
    return out


def scored(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: CoskewParams) -> dict[str, float]:
    """Each eligible symbol's rank fraction in [0, 1): 0 is the first name the book wants."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    cs = coskewness(history, pool, data_date, p.market, p.gamma)
    if not cs:
        return {}
    sign = -1.0 if p.positive else 1.0
    order = sorted(cs, key=lambda s: (sign * cs[s], s))
    return {s: k / len(order) for k, s in enumerate(order)}


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: CoskewParams) -> tuple[Target, ...]:
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


class CoskewAllocator:
    """The screened members with the most negative coskewness with SPY, quarterly, banded."""

    id = "M0179"

    def lookback(self, params: Any) -> int:
        # As M0174: the screen's and the switch's need only, not the 3-year window. A member
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

    def _run(self, prepared: CoskewPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CoskewParams) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, members, rows, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(CoskewPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CoskewPrepared:
        return CoskewPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CoskewPrepared):
            raise TypeError(f"prepared must be CoskewPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


COSKEW = CoskewAllocator()


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: CoskewParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0179-{suffix}", family="M0179", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=COSKEW, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


SW = ("SPY", 200)

METHOD = Method(
    id="M0179",
    name=(
        "Companies that crash with the market: own the stocks investors shun for falling hardest "
        "when the market falls hardest (coskewness)"
    ),
    family="stock-coskewness",
    source_kind="paper",
    source_ref=(
        "Harvey & Siddique (2000), Conditional Skewness in Asset Pricing Tests, JF 55(3); "
        "revisited in Critical Finance Review 2023"
    ),
    parent_id=None,
    hypothesis=(
        "Harvey and Siddique (published 2000, so most of the dev window is after publication and "
        "the 2023 revisit says the premium survived) find about 3.6% a year for systematic "
        "skewness: investors pay up for stocks that do well in market extremes, so the stocks with "
        "the most negative coskewness, the ones that fall hardest when the market swings hardest, "
        "earn more. On the last close of each quarter, among members passing F4's $5 / $20M "
        "screen, compute each one's standardized coskewness with SPY from 156 non-overlapping "
        "weekly log returns (3 years; the CAPM residual against the squared demeaned market "
        "return, HS eq. 11; raw returns, a constant T-bill rate falls into the demeaning); hold "
        "the 20 most negative at 1/20 each, keep a holding while its rank fraction stays under "
        "40%, unfilled slots in SPY, fractional shares at Gotrade's real fees on the owner's "
        "deposits. Variants: N20 (the idea, no switch), N20-SW (behind F4's SPY-200 switch), "
        "N40-SW (a 40-name rung), P20-SW (control: the 20 most positive, same band and switch), "
        "G20-SW (scored by the raw regression coefficient on the squared market return, beta "
        "controlled, as the idea row worded it; it scales with the stock's own volatility). "
        "Success: N20-SW or N20 beats total-return SPY with worst fall <= 25%, PF >= 1.3, a "
        "majority of walk-forward folds and a positive 2009-2015 edge, and P20-SW trails it "
        "clearly."
    ),
    expected_failure=(
        "Negative-coskewness names are the high-beta, crash-prone ones (financials, cyclicals, "
        "tech in 2000), so the book falls hardest in 2008 and 2000-2002 and its worst fall breaks "
        "25% without the switch; the lab's record on crash repair says the switch will not save "
        "it either, selling low and buying back high. Weekly coskewness over three years is a "
        "noisy estimate dominated by one or two crash weeks, so the ranking mostly re-sorts by the "
        "last crash's losers and the gap to the control is a sector cycle, not a premium. The "
        "published premium lives in small stocks and fades after 2000; among index members and "
        "in 2009-2015 it may be gone, and the equal-weight book loses to SPY's big-company drift."
    ),
    candidates=(
        _v("N20", CoskewParams(_screen(20)),
           "The 20 most negative-coskewness members, quarterly, kept under 40%, no switch"),
        _v("N20-SW", CoskewParams(_screen(20, SW)),
           "The same quarterly banded negative-coskewness book behind the SPY 200-day switch"),
        _v("N40-SW", CoskewParams(_screen(40, SW)),
           "A 40-name rung of the negative-coskewness book behind the switch"),
        _v("P20-SW", CoskewParams(_screen(20, SW), positive=True),
           "Control: the 20 most positive-coskewness members, same band and switch"),
        _v("G20-SW", CoskewParams(_screen(20, SW), gamma=True),
           "Scored by the raw squared-market coefficient with beta controlled, behind the switch"),
    ),
    seen_keys=(
        "concept:coskewness",
        "concept:systematic-skewness",
    ),
)
