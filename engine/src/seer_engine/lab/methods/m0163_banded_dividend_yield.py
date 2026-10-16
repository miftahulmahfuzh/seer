"""M0163 — The highest dividend yields among big companies, re-picked once a year, held inside a band.

Source: Novy-Marx & Velikov (2016), "A Taxonomy of Anomalies and Their Trading Costs", Review of
Financial Studies 29(1), doi:10.1093/rfs/hhv063 (the anomalies that survive real trading costs are
the low-turnover ones, value first, and a buy/hold band is the single most effective cost cure);
Fama & French (1993) for dividend yield as a value measure. The store-side frame is M0102's (F4's
member screen, ``Market.dividends``).
Idea: every book this lab has measured re-picks monthly, and at Gotrade's fees a small account
that turns its whole book over every month starts several points behind. Value is the slow
anomaly, and dividend yield is the one value measure the store can compute point in time without
fundamentals. Rank once a year, keep a holding until it falls well out of the top, and pay for
almost no trading at all.

The signal. On data date d, a member's *indicated* yearly dividend is the median amount it paid in
the trailing 365 days times its payment frequency, the frequency being the number of payments in
the trailing 730 days halved and rounded (at least 1). Why not the plain trailing-twelve-month sum:
it jitters with payment timing (a quarterly payer whose ex-date slips over the window edge reads
three or five payments, a third off its true yield), and a book ranked once a year would lock that
error in for twelve months. The median ignores a one-off special dividend. Yield = indicated
dividend / close on d (amounts and closes are both split-adjusted, dividends are not folded into
the bars). A yield above ``MAX_YIELD`` is treated as a data error and skipped; a member with no
payment in the last 365 days has no yield.

The universe. F4's screen ($5 price, $20M 20-day dollar volume, point-in-time S&P 500 / Nasdaq-100
members, at least a year of bars), then only the ``pool`` most traded of those by dollar volume:
the big companies SPY is made of, so the book is not quietly a small-company bet (insight 91).

The band. On a re-pick date (the last close of ``repick_month``, so the trades go in at the first
open of the next month; with the default 12 that is the first session of January) the pool is
ranked by yield, highest first. A held name ranked inside ``keep`` stays; a held name outside it,
or no longer in the pool, is sold; the free slots are filled from the top of the ranking. Between
re-pick dates nothing is re-ranked: a holding leaves only when it stops being an index member or
loses its bar, and its slot sits in SPY until the next re-pick. When the book holds no stock at all
(the first decision of a run, or the month the switch lets it back in) it picks in full at once,
so a run does not sit in SPY for up to eleven months waiting for December. ``keep == top`` is the
no-band control: a full re-pick on every re-pick date. Slots are 1/top each and the rest of the
money is in SPY. With ``inner.trend`` set the whole book is cash while SPY is under its 200-day
average, exactly as F4.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees. The allocator is
asked monthly; on the eleven months in between it re-targets the same names, so the only trades are
the monthly deposits going in and the 1% resize band. That is the turnover the method is about.
Without the market's dividend calendar nothing is targeted (the market-aware allocator contract).
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
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

ADDED = date(2026, 10, 16)
MAX_YIELD = 0.15  # above this the price or the amount is wrong, not the company generous
_YEAR = timedelta(days=365)
_TWO_YEARS = timedelta(days=730)


@dataclass(frozen=True, slots=True)
class YieldParams:
    """``inner`` is F4's screen, book size and optional switch; ``pool`` the most-traded cut;
    ``keep`` the rank a holding must stay inside; ``repick_month`` the data month of the re-pick
    (0 means every month)."""

    inner: FactorParams
    pool: int = 100
    keep: int = 40
    repick_month: int = 12
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("pool", "keep", "repick_month"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if not self.inner.top <= self.keep <= self.pool:
            raise ValueError(f"need top <= keep <= pool, got {self.inner.top}, {self.keep}, {self.pool}")
        if not 0 <= self.repick_month <= 12:
            raise ValueError(f"repick_month must be in [0, 12], got {self.repick_month}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"pool": str(self.pool), "keep": str(self.keep), "repick_month": str(self.repick_month),
               "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> YieldParams:
    if not isinstance(params, YieldParams):
        raise TypeError(f"params must be YieldParams, got {type(params).__name__}")
    return params


def indicated_dividend(paid: tuple[tuple[date, Decimal], ...], data_date: date) -> float | None:
    """Median payment of the last 365 days times the payment frequency read over 730 days."""
    last_year = [a for d, a in paid if data_date - d < _YEAR]
    if not last_year:
        return None
    n2 = sum(1 for d, _ in paid if data_date - d < _TWO_YEARS)
    freq = max(1, int(Decimal(n2) / 2 + Decimal("0.5")))  # round half up, never banker's
    return float(statistics.median(last_year)) * freq


def ranked(rows: list[FactorRow], calendar: DividendCalendar, data_date: date,
           p: YieldParams) -> list[FactorRow]:
    """The ``pool`` most traded eligible rows, ranked by indicated yield, highest first."""
    big = sorted((r for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market),
                 key=lambda r: (-r.dollar_volume, r.symbol))[: p.pool]
    scored: list[tuple[float, str, FactorRow]] = []
    for r in big:
        div = indicated_dividend(calendar.known_on(r.symbol, data_date), data_date)
        if div is None or r.close <= 0:
            continue
        y = div / r.close
        if 0 < y <= MAX_YIELD:
            scored.append((-y, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored]


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           calendar: DividendCalendar, data_date: date, held: frozenset[str],
           p: YieldParams) -> tuple[Target, ...]:
    stocks = sorted(s for s in held if s != p.market and s not in EXCLUDED)
    repick = not stocks or p.repick_month == 0 or data_date.month == p.repick_month
    if repick:
        order = [r.symbol for r in ranked(rows, calendar, data_date, p)]
        rank = {s: i for i, s in enumerate(order)}
        kept = [s for s in stocks if rank.get(s, p.keep) < p.keep]
        kept.sort(key=lambda s: rank[s])
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


class YieldAllocator:
    """The pool's highest dividend yields, re-ranked yearly, held while inside the keep band."""

    id = "M0163"
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
             held: frozenset[str], p: YieldParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, members, rows, prepared.calendar, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no yield and no target."""
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

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
        return self._run(prepared, members, data_date, held, _check(params))


YIELD = YieldAllocator()


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: YieldParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0163-{suffix}", family="M0163", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=YIELD, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0163",
    name="The highest dividend yields among big companies, re-picked once a year and held until they fall well out of the top",
    family="stock-dividend-yield-value",
    source_kind="paper",
    source_ref=(
        "Novy-Marx & Velikov (2016), A Taxonomy of Anomalies and Their Trading Costs, Rev. "
        "Financial Studies 29(1), doi:10.1093/rfs/hhv063; Fama & French (1993), dividend yield "
        "as a value measure"
    ),
    parent_id=None,
    hypothesis=(
        "Dividend yield as value is decades old (Fama-French 1988/1993) and the cost-and-band "
        "result was published in 2016, after the dev window, so the dev years are before the "
        "crowd traded the low-turnover framing, but not before it knew high yield. Every book "
        "measured so far re-picks monthly, and monthly full turnover on a small account starts "
        "several points behind at Gotrade's fees. Novy-Marx and Velikov find value survives "
        "costs and a buy/hold band is the best cost cure. Among point-in-time S&P 500 / "
        "Nasdaq-100 members passing F4's $5 / $20M screen, take the 100 most traded; on the last "
        "close of December rank them by indicated dividend yield (median payment of the last 365 "
        "days times the payment frequency read over 730 days, over the close; above 15% skipped "
        "as a data error); keep a holding ranked inside the top 40, sell the rest, fill to 20 "
        "names at 1/20 each from the top; between re-picks a name leaves only when it stops "
        "being a member, its slot sitting in SPY; a book holding no stock picks in full at once. "
        "Fractional shares at Gotrade's real fees on the owner's deposits. Variants: Y20-B40 (the "
        "idea), Y20-B40-SW (the same behind F4's SPY-200 switch), Y20-NOBAND (control: full "
        "yearly re-pick of 20, no band, to price the band), Y30-B60 (a wider, less "
        "sector-concentrated book), M20-B40 (control: the same band re-ranked monthly, to price "
        "the yearly cadence). Success: Y20-B40 beats total-return SPY with worst fall <= 25%, "
        "PF >= 1.3, a positive edge in 2009-2015 and a majority of walk-forward folds; and it "
        "should beat both controls, or the band and the cadence are not what helped."
    ),
    expected_failure=(
        "High yield among big companies is a sector bet (utilities, telecoms, energy, banks, "
        "tobacco and REITs) that lost badly in 2008, when the banks' yields looked highest just "
        "before they cut, and lagged the 1998-1999 growth run, so it trails SPY TR over "
        "1996-2015 or passes only by sitting in cash behind the switch. A yearly ranking is also "
        "slow to leave a name that is about to cut: the yield trap is held for up to a year. "
        "In 2009-2015 big tech and growth led, which a yield book barely owns, so the "
        "highest-coverage era is likely negative. The book is near M0088's calm big raisers and "
        "M0102's raise streaks in what it holds and may move with them. Survivorship flatters "
        "it: companies that cut and later died are missing from the dev store. Withholding tax "
        "on dividends (30% for an Indonesian holder, 15% under the treaty) is not modelled, and "
        "it bites a high-yield book harder than any other."
    ),
    candidates=(
        _v("Y20-B40", YieldParams(_screen(20), pool=100, keep=40),
           "Top 20 yields of the 100 most traded, re-ranked each December, kept while inside the top 40, no switch"),
        _v("Y20-B40-SW", YieldParams(_screen(20, ("SPY", 200)), pool=100, keep=40),
           "The same yearly banded yield book behind the SPY 200-day switch"),
        _v("Y20-NOBAND", YieldParams(_screen(20), pool=100, keep=20),
           "Control: the top 20 yields re-picked in full each December, no keep band"),
        _v("Y30-B60", YieldParams(_screen(30), pool=100, keep=60),
           "A wider book: top 30 yields, kept while inside the top 60, re-ranked each December"),
        _v("M20-B40", YieldParams(_screen(20), pool=100, keep=40, repick_month=0),
           "Control: the same 20-in, 40-out band re-ranked every month, to price the yearly cadence"),
    ),
    seen_keys=(
        "concept:dividend-yield-value",
        "concept:buy-hold-band",
        "concept:low-turnover-yearly-rebalance",
    ),
)
