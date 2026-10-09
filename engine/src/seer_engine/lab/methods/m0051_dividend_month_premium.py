"""M0051 — Buy the stocks about to pay their dividend: the dividend-month premium.

Source: Hartzmark & Solomon (2013), "The dividend month premium", Journal of Financial Economics
109(3), 640-660, doi:10.1016/j.jfineco.2013.02.015 (working paper from 2011).
Idea: stocks earn more in the months they are predicted to pay a dividend -- predicted from the
dividend history alone -- because investors who want dividends buy ahead of the ex-date. The
paper reports about 0.4-0.5 points a month on 1927-2011 US stocks.

The frame is F4's -- point-in-time S&P 500 / Nasdaq-100 members, the $5 price and $20M daily
dollar-volume screen, optionally the SPY 200-day trend gate, monthly, fractional shares at
Gotrade's real fees on ``monthly-hold-frac-gotrade`` -- with the ranking replaced by the
dividend calendar (``Market.dividends``, read only through ``known_on(symbol, data_date)``):

    * the holding month M is the month of the session after ``data_date`` (the rank session is
      the month's first session and ``data_date`` the last session before it);
    * a member is a *predicted payer* for M when it went ex-dividend in calendar month M-12 or
      in month M-3 (the paper's annual and quarterly predictions). Both months lie before
      ``data_date``, so only ex-dates already known are read;
    * trailing yield = the cash paid with ex-dates in the 365 days through ``data_date``, over
      the close on ``data_date`` (both in split-adjusted units).

``pick="all"`` holds every predicted payer equal weight; ``pick="yield"`` the ``top`` highest
trailing yields among them; ``pick="lowvol"`` the ``top`` lowest 60-day volatilities among them.
``when="off"`` turns the predicted set inside out: members that paid in the last year but are
NOT predicted to pay in M -- the control, which the paper says should trail.

Without the market's calendar (the history-only ``prepare``/``targets`` path) nobody is a
predicted payer and nothing is targeted, which is the market-aware allocator contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
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

ADDED = date(2026, 10, 9)
MAX_NAMES = 1000  # equal_weight(n) stays >= the weight quantum

Pick = Literal["all", "yield", "lowvol"]
When = Literal["on", "off"]
_PICKS: tuple[str, ...] = ("all", "yield", "lowvol")
_WHENS: tuple[str, ...] = ("on", "off")


@dataclass(frozen=True, slots=True)
class DivMonthParams:
    """``inner`` is F4's screen and trend gate (its ``top`` sizes the yield/lowvol books)."""

    inner: FactorParams
    pick: Pick = "all"
    when: When = "on"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.pick, str) or self.pick not in _PICKS:
            raise ValueError(f"pick must be one of {_PICKS}, got {self.pick!r}")
        if not isinstance(self.when, str) or self.when not in _WHENS:
            raise ValueError(f"when must be one of {_WHENS}, got {self.when!r}")
        if self.when == "off" and self.pick == "all":
            raise ValueError("the off-month control ranks its names; use pick='yield' or 'lowvol'")

    def as_dict(self) -> dict[str, str]:
        out = {"pick": self.pick, "when": self.when}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> DivMonthParams:
    if not isinstance(params, DivMonthParams):
        raise TypeError(f"params must be DivMonthParams, got {type(params).__name__}")
    return params


def _month_back(year: int, month: int, k: int) -> tuple[int, int]:
    """The calendar month ``k`` months before (year, month)."""
    m = year * 12 + (month - 1) - k
    return m // 12, m % 12 + 1


def holding_month(data_date: date) -> tuple[int, int]:
    """(year, month) of the session after ``data_date``: the month the book is about to hold."""
    s = dates.next_session(data_date)
    return s.year, s.month


def predicted(paid: tuple[tuple[date, Decimal], ...], month: tuple[int, int]) -> bool:
    """True when an ex-date in ``paid`` falls in calendar month M-12 or M-3 of ``month``."""
    wanted = {_month_back(*month, 12), _month_back(*month, 3)}
    return any((d.year, d.month) in wanted for d, _ in paid)


def trailing_yield(paid: tuple[tuple[date, Decimal], ...], close: float, data_date: date) -> float:
    """Cash paid with ex-dates in the 365 days through ``data_date``, over ``close``."""
    since = data_date - timedelta(days=365)
    cash = sum((a for d, a in paid if d > since), Decimal(0))
    return float(cash) / close if close > 0.0 else 0.0


def choose(rows: list[FactorRow], calendar: DividendCalendar, data_date: date,
           params: DivMonthParams) -> list[FactorRow]:
    month = holding_month(data_date)
    scored: list[tuple[float, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED:
            continue
        paid = calendar.known_on(r.symbol, data_date)
        if not paid:
            continue
        y = trailing_yield(paid, r.close, data_date)
        hit = predicted(paid, month)
        if params.when == "on" and not hit:
            continue
        if params.when == "off" and (hit or y <= 0.0):
            continue
        key = -y if params.pick == "yield" else (r.vol if params.pick == "lowvol" else 0.0)
        scored.append((key, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    keep = MAX_NAMES if params.pick == "all" else params.inner.top
    return [r for _, _, r in scored[:keep]]


def targets_from_rows(chosen: list[FactorRow], params: DivMonthParams) -> tuple[Target, ...]:
    if not chosen:
        return ()
    w = equal_weight(len(chosen) if params.pick == "all" else params.inner.top)
    out: list[Target] = []
    for row in chosen:
        target = target_from_close(row.symbol, row.close, w)
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass
class DivMonthPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    calendar: DividendCalendar = field(repr=False)


class DividendMonthAllocator:
    """Members predicted to go ex-dividend in the coming month, from the point-in-time calendar.

    Held symbols get no special treatment: a name not predicted next month is signal-exited.
    """

    id = "M0051"
    market_fields = ("dividends",)  # ranks on Market.dividends, never on Market.fundamentals

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no predicted payer and no target."""
        return self.targets_with_calendar(history, EMPTY_DIVIDENDS, members, data_date, params)

    def targets_with_calendar(self, history: Mapping[str, History], calendar: DividendCalendar,
                              members: AbstractSet[str], data_date: date, params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from_rows(choose(rows, calendar, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> DivMonthPrepared:
        return DivMonthPrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> DivMonthPrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return DivMonthPrepared(market.history, prepare_factor(market.history), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DivMonthPrepared):
            raise TypeError(f"prepared must be DivMonthPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.calendar, data_date, p), p)


DIVMONTH = DividendMonthAllocator()

T20 = replace(N20, rank="lowvol")  # F4's screen and gate; the rank field is unused here
NOT20 = replace(N20_NOTREND, rank="lowvol")


def _v(suffix: str, params: DivMonthParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0051-{suffix}", family="M0051", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DIVMONTH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0051",
    name="Buy the stocks about to pay their dividend: the dividend-month premium",
    family="stock-dividend-calendar",
    source_kind="paper",
    source_ref=(
        "Hartzmark & Solomon (2013), The dividend month premium, J. Financial Economics 109(3), "
        "640-660, doi:10.1016/j.jfineco.2013.02.015"
    ),
    parent_id=None,
    hypothesis=(
        "Hartzmark and Solomon (working paper 2011, published 2013) find stocks earn about 0.4-0.5 "
        "points a month more in months they are predicted to pay a dividend -- they paid one in the "
        "same calendar month a year earlier, or three months earlier -- with returns rising into the "
        "ex-date, consistent with price pressure from investors who want dividends. It is predicted "
        "from the dividend history alone, which the research store holds and the market now carries "
        "point in time. This is a calendar mechanism the lab has never tried: it reads neither past "
        "return nor volatility rank as its signal, so its picks should be largely unrelated to the "
        "momentum books that failed their looks. Each month, among F4's screened members, hold the "
        "stocks predicted to go ex-dividend in the coming month, equal weight, in fractional shares "
        "at Gotrade's real fees on monthly-hold-frac-gotrade. Variants: ALL-T (every predicted "
        "payer, behind the SPY 200-day gate), ALL (every predicted payer, always invested), Y20-T "
        "(the 20 highest trailing yields among them, gated), LV20-T (the 20 calmest among them, "
        "gated) and OFF20-T (the control: the 20 highest-yield payers NOT predicted to pay this "
        "month, gated), so Y20-T minus OFF20-T isolates the month effect from the yield effect. "
        "Success: a predicted-payer variant beats SPY TR on dev within the 20% drawdown limit, "
        "beats its off-month control, and keeps a positive edge in 2009-2015."
    ),
    expected_failure=(
        "The paper's sample ends in 2011 and its working paper circulated from 2011, so the dev "
        "window covers the pre-publication years only; any edge here is the kind that fades once "
        "traded. A quarter to a third of large caps pay in any month, so ALL is close to an "
        "equal-weight dividend-payer index (100+ names): it tilts to smaller, value-ish members and "
        "bets against SPY's big-company drift, and near-total monthly turnover pays Gotrade's $0.10 "
        "minimum on every order, which on a 10M IDR start is several percent a year by itself. "
        "Not modelled and against the method: the book engine credits 100% of each dividend in "
        "cash, but the owner's account loses the US withholding tax on every dividend (30%, or 15% "
        "under the Indonesia treaty with a W-8BEN). A book that rotates into each month's payers "
        "collects roughly three times SPY's dividend yield, so the unmodelled tax drag is about 1-2 "
        "points a year larger than on SPY; the analysis will estimate it from the dividends the run "
        "credited. In 2008 payers fell with the market, so the ungated ALL book should fall well "
        "over 20%, and even gated, 1998-2002 value-versus-growth swings may leave it behind SPY "
        "for years. The off-month control may do as well as Y20-T, which would mean the yield "
        "tilt, not the calendar, carries any result."
    ),
    candidates=(
        _v("ALL-T", DivMonthParams(T20, pick="all"),
           "Every screened member predicted to go ex-dividend next month, equal weight, behind the SPY 200-day gate"),
        _v("ALL", DivMonthParams(NOT20, pick="all"),
           "Every predicted payer, always invested: the paper's portfolio, long only"),
        _v("Y20-T", DivMonthParams(T20, pick="yield"),
           "The 20 highest trailing-yield predicted payers, behind the gate: the biggest dividends about to land"),
        _v("LV20-T", DivMonthParams(T20, pick="lowvol"),
           "The 20 calmest predicted payers (60-day volatility), behind the gate"),
        _v("OFF20-T", DivMonthParams(T20, pick="yield", when="off"),
           "Control: the 20 highest-yield payers NOT predicted to pay next month, behind the gate"),
    ),
    seen_keys=(
        "concept:dividend-month-premium",
        "concept:dividend-calendar",
        "concept:predicted-dividend",
        "doi:10.1016/j.jfineco.2013.02.015",
    ),
)
