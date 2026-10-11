"""M0102 — Long dividend-raise streaks: big companies that have raised their dividend every year for years.

Source: S&P 500 Dividend Aristocrats index methodology (25 straight years of raises, launched
2005); ProShares, "Dividends, Drawdowns & Rebounds" (2005-2018 study of the Aristocrats); the
store-side frame is M0070's (F4's member screen, ``Market.dividends``).
Idea: a persistence screen, not an event. A company that has raised its dividend every calendar
year for K years has shown, year after year, that its cash keeps growing; the published claim is
that such companies fell much less in 2000-02 and 2008 (Aristocrats -22% vs the S&P's -38% in 2008)
and kept up afterwards. Every dividend-change book so far (M0070-M0096) traded the *event* and lost
to SPY in 2009-2015 behind the SPY-200 switch; M0096 showed it was the switch, not the dividend
stocks, that lost there. So the main variants carry no switch, and one control carries it.

Why calendar years and a median, and not a trailing twelve-month sum: a trailing sum jitters with
payment timing (an ex-date that slips over the window edge reads as a cut, then as a raise), and
the book would churn on it at Gotrade's fees. A completed calendar year changes only on 1 January,
which is also how the Aristocrats are reviewed, and the *median* payment of the year is blind to
how many payments landed in it and to a one-off special dividend. On data date d, for every
completed year Y < d.year, ``level(Y)`` = the median of the amounts with an ex-date in Y (amounts
are split-adjusted in the store, read only through ``known_on(symbol, d)``); a year with no payment
has no level. The *streak* is the number of consecutive years, counting back from d.year - 1, with
``level(Y) > level(Y - 1) x (1 + raise_min)``; ``raise_min`` = 0.5% keeps split-adjustment rounding
(0.33333 vs 0.33334) from reading as a raise. A member qualifies when its streak is >= ``years``.

Thin early years, without lookahead: the store's dividends start in 1993, so a 5-year streak is
first readable in January 1999, 7 years in 2001, 10 years in 2004. Until enough members qualify the
empty slots sit in SPY, so the early dev years are mostly SPY by construction. That is the honest
reading of what the data can say then, not a fault to be patched.

The book: F4's screen ($5 price, $20M 20-day dollar volume, point-in-time S&P 500 / Nasdaq-100
members), qualifiers ranked by the longest streak (capped at ``MAX_YEARS``), then the larger
dollar volume (leans toward the big names SPY is made of), then the symbol; the ``top`` first at
1/top each, the rest of the money in SPY. Re-picked monthly on ``monthly-hold-frac-gotrade``
(fractional shares, Gotrade's real fees); the streak only changes in January, so the monthly look
mostly re-confirms the book and the turnover is what the screen and the dividend dates force.
With ``inner.trend`` set (the control) the whole book is cash while SPY is under its 200-day
average, exactly as F4. Without the market's dividend calendar nothing is targeted, which is the
market-aware allocator contract.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 11)
MAX_YEARS = 25  # the streak is counted back at most this far (the Aristocrats' own bar)


@dataclass(frozen=True, slots=True)
class StreakParams:
    """``inner`` is F4's screen, book size and optional trend switch; ``years`` the streak bar."""

    inner: FactorParams
    years: int = 5
    raise_min: Decimal = Decimal("0.005")
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.years, bool) or not isinstance(self.years, int) or not 1 <= self.years <= MAX_YEARS:
            raise ValueError(f"years must be an int in [1, {MAX_YEARS}], got {self.years!r}")
        if not isinstance(self.raise_min, Decimal) or not self.raise_min.is_finite() or self.raise_min < 0:
            raise ValueError(f"raise_min must be a finite Decimal >= 0, got {self.raise_min!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"years": str(self.years), "raise_min": str(self.raise_min), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> StreakParams:
    if not isinstance(params, StreakParams):
        raise TypeError(f"params must be StreakParams, got {type(params).__name__}")
    return params


def streak(paid: tuple[tuple[date, Decimal], ...], data_date: date, raise_min: Decimal) -> int:
    """Consecutive completed calendar years, back from ``data_date.year - 1``, whose median payment rose."""
    by_year: dict[int, list[Decimal]] = {}
    for d, amount in paid:
        if d.year < data_date.year:
            by_year.setdefault(d.year, []).append(amount)
    n = 0
    y = data_date.year - 1
    while n < MAX_YEARS:
        now, before = by_year.get(y), by_year.get(y - 1)
        if not now or not before:
            break
        if statistics.median(now) <= statistics.median(before) * (1 + raise_min):
            break
        n += 1
        y -= 1
    return n


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, p: StreakParams) -> tuple[Target, ...]:
    picks: list[tuple[int, float, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        k = streak(calendar.known_on(r.symbol, data_date), data_date, p.raise_min)
        if k >= p.years:
            picks.append((-k, -r.dollar_volume, r.symbol, r))
    picks.sort(key=lambda t: (t[0], t[1], t[2]))
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for _, _, _, r in picks[: p.inner.top]:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


class StreakAllocator:
    """Members with a K-year run of yearly dividend raises, longest runs first, the rest in SPY."""

    id = "M0102"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
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

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             p: StreakParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, rows, prepared.calendar, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no streak and no target."""
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> RaisePrepared:
        return RaisePrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> RaisePrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return RaisePrepared(market.history, prepare_factor(market.history), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


STREAK = StreakAllocator()


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: StreakParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0102-{suffix}", family="M0102", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=STREAK, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0102",
    name="Long dividend-raise streaks: big companies that have raised their dividend every year for many years, held with no safety switch",
    family="stock-dividend-growth-streak",
    source_kind="blog",
    source_ref=(
        "S&P 500 Dividend Aristocrats index methodology; ProShares 'Dividends, Drawdowns & "
        "Rebounds' (2005-2018), https://www.etf.com/sections/etf-industry-perspective/"
        "proshares-dividends-drawdowns-rebounds"
    ),
    parent_id=None,
    hypothesis=(
        "Published as an index in 2005 (S&P 500 Dividend Aristocrats) and marketed as a fund from "
        "2013, so most of the dev window is before the crowd bought it as a product. Among "
        "point-in-time S&P 500 / Nasdaq-100 members passing F4's $5 / $20M screen, hold those "
        "whose median dividend payment has risen (by more than 0.5%) in each of the last K "
        "completed calendar years (amounts split-adjusted, ex-dates <= the data date), longest "
        "streak first then the most traded, up to N names at 1/N each, the rest in SPY, re-picked "
        "monthly, fractional shares at Gotrade's real fees, with NO SPY-200 switch in the main "
        "variants. The store's dividends begin in 1993, so a 5-year streak is first readable in "
        "1999 (7 in 2001, 10 in 2004); until then the empty slots sit in SPY. A company that keeps "
        "raising every year has cash that keeps growing; such books are claimed to fall much less "
        "in 2000-02 and 2008 and keep up afterwards, which is exactly where our books lost. "
        "Variants: K5-N40 (the idea), K7-N40, K10-N40 (longer, rarer streaks), K5-N25 (more "
        "concentrated), K5-N40-SW (control: the same book behind F4's SPY-200 switch, to price the "
        "switch on a streak book). It ranks on a run of dividend raises, so the family is "
        "dividend-growth-streak, not dividend-change-drift. Success: K5-N40 beats total-return SPY "
        "on the deposits, worst fall <= 20% without a switch, a positive edge in 2009-2015 and a "
        "majority of walk-forward folds."
    ),
    expected_failure=(
        "The streak book is the same utilities-staples-industrials basket as the calm raisers "
        "(it may move with M0088's book) and lags the growth-led 1998-99 and 2009-2015 runs, so "
        "it fails 'beats SPY' and the folds; with no switch the worst fall may still pass 20% in "
        "2008 (the published -22% was the index, not a 40-name equal-weight book of our members). "
        "Early dev years are mostly SPY by construction, so the 1996-2003 result says little and "
        "the edge has to be earned 2004-2015. The evidence is a fund issuer's, not a paper's. "
        "Survivorship flatters it: a company that cut and later died is missing from the dev "
        "store, while the streak itself is the survivor's mark, so the survivorship check store "
        "must be read before any verdict. Withholding tax on dividends is not modelled."
    ),
    candidates=(
        _v("K5-N40", StreakParams(_screen(40), 5),
           "Five straight yearly raises, up to 40 names, longest streaks first, no switch"),
        _v("K7-N40", StreakParams(_screen(40), 7),
           "Seven straight yearly raises, up to 40 names, no switch"),
        _v("K10-N40", StreakParams(_screen(40), 10),
           "Ten straight yearly raises, up to 40 names, no switch"),
        _v("K5-N25", StreakParams(_screen(25), 5),
           "Five straight yearly raises, up to 25 names (more concentrated), no switch"),
        _v("K5-N40-SW", StreakParams(_screen(40, ("SPY", 200)), 5),
           "Control: the five-year streak book behind the SPY 200-day switch"),
    ),
    seen_keys=(
        "concept:dividend-growth-streak",
        "concept:dividend-aristocrats",
    ),
)
