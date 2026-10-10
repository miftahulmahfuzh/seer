"""M0079 — Hold a stock only between the day its dividend is announced and the day it goes ex.

Source: Kalay & Loewenstein (1985), "Predictable events and excess returns: the case of dividend
announcements", Journal of Financial Economics 14(3), 423-449; Hartzmark & Solomon (2013), "The
dividend month premium", Journal of Financial Economics 109(3), 640-660.
Idea: prices drift up around a scheduled dividend announcement and on toward the ex-date, as
dividend-seeking buyers arrive before the payment. M0051 could only guess the dividend month from
past ex-dates and lost after fees; the store now carries the board's declaration date for most
dividends (``Market.dividends.announced_on``), so the window can open on the day it really opens.

The frame is F4's -- point-in-time S&P 500 / Nasdaq-100 members, the $5 price and $20M daily
dollar-volume screen, the SPY 200-day trend switch -- re-decided every session (a daily book,
fractional shares at Gotrade's real fees), with the ranking replaced by the dividend calendar.

An *event* is one dividend of a member, read point in time on data date d:

    * ``timing="announce"``: the dividend is known from ``Announcement.known`` (its declaration
      day when dated, else its ex-date), exactly as ``announced_on(symbol, d)`` returns it;
    * ``timing="ex"`` (the paired control): every dividend is known only from its ex-date, the
      only timing the lab had before the announcement data -- read from the same calendar, keeping
      only dividends with ``ex_date <= d`` and treating ``known = ex_date``;
    * ``declared_only``: drop dividends that carry no declaration date, in either timing, so a
      pair compares the same dividends and only the timing differs.

An event is *regular* when the amount is at least ``1 - CUT_TOL`` and at most ``1 + SPECIAL``
times the median of the up to four earlier payments with ex-dates in the 400 days before its own
(a cut, a first payment and a one-off special are not regular). A regular event is *live* on d:

    * ``exit="ex"``: from its known day while the session after d is before its ex-date, so the
      book buys at the open after the announcement, holds through the last close before the
      ex-date (the cash dividend is credited) and sells at the ex-date's open;
    * ``exit="thru"``: the same, held one session more -- through the ex-date's close, sold at the
      next session's open -- so the ex-day itself is in the window;
    * ``exit="hold"``: for ``hold`` sessions counted from its known day (the same fixed hold in
      both timings, so the pair differs only in when the clock starts).

Live events are ranked held names first, then the newest known day, then the symbol; the first
``inner.top`` are held at equal weight 1/top and the rest of the book is in SPY. Behind the trend
switch the book is all cash while SPY is below its 200-day average.

Without the market's calendar (the history-only ``prepare``/``targets`` path, or an empty
calendar) nothing is targeted, which is the market-aware allocator contract.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, Announcement, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
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

ADDED = date(2026, 10, 10)
BASE_DAYS = 400  # the window before an ex-date that sets the regular-payment baseline
BASE_N = 4  # payments in the baseline median
CUT_TOL = Decimal("0.01")  # below 99% of the baseline is a cut
SPECIAL = Decimal("1.00")  # above twice the baseline is a one-off special
TAIL = 4  # the latest known dividends a live event can be among (windows are weeks long)

Timing = Literal["announce", "ex"]
Exit = Literal["ex", "thru", "hold"]
_TIMINGS: tuple[str, ...] = ("announce", "ex")
_EXITS: tuple[str, ...] = ("ex", "thru", "hold")

# The book re-decides every session: a dividend window is two to six weeks long, so a monthly or
# weekly book would miss most of it. Same levers as monthly-hold-frac-gotrade (fractional, open
# limit, resize to target, Gotrade's fees) on a daily clock. No preset of this id exists yet, so a
# winner needs one before `promote` (a feature-wish, not a reason to run it at another cadence).
DAILY_HOLD_FRAC_GOTRADE = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="daily-hold-frac-gotrade", cadence="daily")


@dataclass(frozen=True, slots=True)
class WindowParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines the event window."""

    inner: FactorParams
    timing: Timing = "announce"
    exit: Exit = "ex"
    hold: int = 14
    declared_only: bool = False
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.timing, str) or self.timing not in _TIMINGS:
            raise ValueError(f"timing must be one of {_TIMINGS}, got {self.timing!r}")
        if not isinstance(self.exit, str) or self.exit not in _EXITS:
            raise ValueError(f"exit must be one of {_EXITS}, got {self.exit!r}")
        if self.timing == "ex" and self.exit != "hold":
            raise ValueError("timing 'ex' has no window before the ex-date: use exit 'hold'")
        if isinstance(self.hold, bool) or not isinstance(self.hold, int) or self.hold < 1:
            raise ValueError(f"hold must be an int >= 1, got {self.hold!r}")
        if not isinstance(self.declared_only, bool):
            raise TypeError(f"declared_only must be a bool, got {type(self.declared_only).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "timing": self.timing,
            "exit": self.exit,
            "hold": str(self.hold),
            "declared_only": str(self.declared_only).lower(),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> WindowParams:
    if not isinstance(params, WindowParams):
        raise TypeError(f"params must be WindowParams, got {type(params).__name__}")
    return params


def known_events(calendar: DividendCalendar, symbol: str, data_date: date,
                 p: WindowParams) -> list[Announcement]:
    """``symbol``'s dividends known on ``data_date`` under ``p.timing``, ascending by ex-date."""
    items = calendar.announced_on(symbol, data_date)
    if p.timing == "ex":
        items = tuple(a._replace(known=a.ex_date) for a in items if a.ex_date <= data_date)
    return sorted(items, key=lambda a: a.ex_date)


def regular(events: list[Announcement], i: int) -> bool:
    """True when ``events[i]`` is neither a cut, a first payment nor a one-off special."""
    e = events[i]
    since = e.ex_date - timedelta(days=BASE_DAYS)
    prior = [a.amount for a in events[:i] if a.ex_date > since][-BASE_N:]
    if not prior:
        return False
    base = statistics.median(prior)
    return base * (1 - CUT_TOL) <= e.amount <= base * (1 + SPECIAL)


def _sessions_since(h: History, known: date, data_date: date) -> int | None:
    """Sessions in ``(known, data_date]`` on ``h``'s own bars; None without a bar dated ``data_date``."""
    i = h.index_of(data_date)
    if i is None:
        return None
    k = int(np.searchsorted(h.dates, np.datetime64(known, "D"), side="right")) - 1
    return i - k


def live_known(h: History, events: list[Announcement], data_date: date, next_session: date,
               p: WindowParams) -> date | None:
    """The known day of ``events``' newest live regular event on ``data_date``, else None."""
    for i in range(len(events) - 1, max(-1, len(events) - 1 - TAIL), -1):
        e = events[i]
        if p.declared_only and not e.declared:
            continue
        if e.known > data_date:
            continue
        if p.exit == "ex":
            if not (e.declared and next_session < e.ex_date):
                continue
        elif p.exit == "thru":
            if not (e.declared and next_session <= e.ex_date):
                continue
        else:
            n = _sessions_since(h, e.known, data_date)
            if n is None or n >= p.hold:
                continue
        if not regular(events, i):
            continue
        return e.known
    return None


@dataclass
class WindowPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    calendar: DividendCalendar = field(repr=False)


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: WindowParams) -> tuple[Target, ...]:
    nxt = dates.next_session(data_date)
    live: list[tuple[int, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        h = history.get(r.symbol)
        if h is None:
            continue
        k = live_known(h, known_events(calendar, r.symbol, data_date, p), data_date, nxt, p)
        if k is None:
            continue
        live.append((0 if r.symbol in held else 1, -k.toordinal(), r.symbol, r))
    live.sort(key=lambda t: (t[0], t[1], t[2]))
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for _, _, _, r in live[: p.inner.top]:
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


class DividendWindowAllocator:
    """Members inside a live dividend window (announcement to ex, or a fixed hold); rest SPY."""

    id = "M0079"
    market_fields = ("dividends",)  # ranks on Market.dividends, never on Market.fundamentals

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

    def _run(self, prepared: WindowPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: WindowParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no calendar: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, rows, prepared.calendar, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target."""
        return self._run(WindowPrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> WindowPrepared:
        return WindowPrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> WindowPrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return WindowPrepared(market.history, prepare_factor(market.history), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, WindowPrepared):
            raise TypeError(f"prepared must be WindowPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


WINDOW = DividendWindowAllocator()

T20 = replace(N20, rank="lowvol")  # F4's screen and SPY-200 switch; the rank field is unused here


def _v(suffix: str, params: WindowParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0079-{suffix}", family="M0079", rules=DAILY_HOLD_FRAC_GOTRADE,
                     allocator=WINDOW, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0079",
    name="Hold a stock only between the day its dividend is announced and the day it goes ex",
    family="stock-dividend-announcement-window",
    source_kind="paper",
    source_ref=(
        "Kalay & Loewenstein (1985), Predictable events and excess returns: the case of dividend "
        "announcements, JFE 14(3); Hartzmark & Solomon (2013), The dividend month premium, JFE 109(3)"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1985 (Kalay and Loewenstein) and 2011-2013 (Hartzmark and Solomon), so the "
        "announcement-window premium was public for the whole dev window; it survives only if it "
        "is a steady demand effect (dividend-seeking buyers arriving before the payment) rather "
        "than a mispricing. Prices drift up from a regular dividend's announcement toward its "
        "ex-date. Batch theme (sera-20261010-1742): does the paid-for declaration date improve a "
        "method? Book: F4's members and liquidity screen behind the SPY 200-day switch, re-decided "
        "every session on a daily clock (daily-hold-frac-gotrade: monthly-hold-frac-gotrade's "
        "levers -- fractional, open limit, resize to target, Gotrade's real fees -- with a daily "
        "cadence, because a window is two to six weeks long), up to 20 names at 5% each, held names "
        "first then the newest announcement, the rest in SPY. Only regular dividends: within 99% to "
        "200% of the median of the up to four payments in the prior 400 days (no cuts, first "
        "payments or specials). Variants. ANN-TOEX: buy at the open after a declared dividend's "
        "announcement, hold through the last close before the ex-date (the dividend is credited), "
        "sell at the ex-date's open -- the paper's window. ANN-H14 / EX-H14: the same 14-session hold "
        "(about the median window) started from the dividend's known day, which is the declaration "
        "when dated and the ex-date otherwise (ANN), or always the ex-date (EX, the control: the "
        "only timing the lab had before). ANN-H14-DEC / EX-H14-DEC: the same pair keeping only "
        "dividends with a declaration date in both arms, so coverage cannot blur the comparison. "
        "EX-TOEX is impossible (no window before an ex-date the book only learns on the ex-date), "
        "so ANN-TOEX's paired control is EX-H14-DEC. ANN-THRU: ANN-TOEX held one session more, "
        "through the ex-date's close, to include the ex-day itself. The value of the data is the "
        "paired difference ANN minus EX (funded CAGR, worst fall, DSR, the 2009-2015 era, the "
        "walk-forward folds), not the absolute result. Success for the data: ANN-H14-DEC beats "
        "EX-H14-DEC and ANN-TOEX beats EX-H14-DEC. Success for the method: a variant beats "
        "total-return SPY on dev within the 20% worst fall and keeps a positive edge in 2009-2015."
    ),
    expected_failure=(
        "The announcement-window premium is a fraction of a percent per event (Kalay and Loewenstein "
        "report well under 1% over the window), while each event costs a 5% slot a buy and a sell at "
        "Gotrade's fees plus a matching SPY trim and add, about 0.5-1% of the slot each round trip at "
        "$50-70 slots; the book may trade 300-500 events a year and pay more in fees than the window "
        "earns, trailing SPY as M0051 did. The names are dividend payers, value-ish, lower-growth "
        "stocks that trailed SPY's big-company growth in 1997-2000 and from 2009, so the book may lag "
        "SPY in 2009-2015 even if the timing helps. Most of the price reaction to the announcement "
        "itself happens on the announcement day, before a next-open buy, so the announcement arm "
        "may only catch the slower run-up and ANN minus EX may be near zero. Behind the SPY-200 "
        "switch the 1998 and 2011 fast falls land before the switch turns, but at 20 x 5% plus SPY "
        "the book is close to SPY's own fall, so the worst fall should sit near the 20% limit. Not "
        "modelled and against the method: the book is credited every dividend in full, but the owner "
        "loses 15-30% of it to US withholding tax, and ANN-TOEX and ANN-THRU exist to collect "
        "dividends, so their real result is worse by roughly 0.1-0.3 points a year than the lab's."
    ),
    candidates=(
        _v("ANN-TOEX", WindowParams(T20, timing="announce", exit="ex", declared_only=True),
           "Buy after a declared regular dividend is announced, sell at the ex-date's open (dividend collected)"),
        _v("ANN-THRU", WindowParams(T20, timing="announce", exit="thru", declared_only=True),
           "The same window held through the ex-date's close, sold the session after"),
        _v("ANN-H14", WindowParams(T20, timing="announce", exit="hold", hold=14),
           "14 sessions from the known day: the declaration when dated, else the ex-date"),
        _v("EX-H14", WindowParams(T20, timing="ex", exit="hold", hold=14),
           "Control: 14 sessions from the ex-date, the only timing the lab had before the data"),
        _v("ANN-H14-DEC", WindowParams(T20, timing="announce", exit="hold", hold=14, declared_only=True),
           "14 sessions from the declaration, declared dividends only"),
        _v("EX-H14-DEC", WindowParams(T20, timing="ex", exit="hold", hold=14, declared_only=True),
           "Control: 14 sessions from the ex-date, the same declared dividends only"),
    ),
    seen_keys=(
        "concept:dividend-announcement-window",
        "concept:dividend-announcement-premium",
        "concept:pre-ex-dividend-run-up",
        "doi:10.1016/0304-405X(85)90007-2",
    ),
)
