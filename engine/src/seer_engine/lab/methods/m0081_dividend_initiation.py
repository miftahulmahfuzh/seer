"""M0081 — Buy a company the week its board declares its first-ever dividend.

Source: Michaely, Thaler & Womack (1995), "Price reactions to dividend initiations and
omissions: overreaction or drift?", JF 50(2) (about +7.5% over the 12 months after an
initiation); Asquith & Mullins (1983), JB 56(1); Boehme & Sorescu (2002), JF 57(2), on
resumptions. Batch sera-20261010-1742: does the paid-for declaration-date data help?

M0070 mixed initiations in with raises and, because it reads only the *latest* payment, an
initiation stopped counting at the company's second dividend about a quarter later. Here the
event is the initiation alone and it lives for ``hold_days`` from its own event date whatever
the company pays afterwards.

A member's *event* on data date d is its most recent dividend (in the arm's event-date order)
that either

    * is the first dividend in the store for that symbol, or
    * follows the previous one by at least ``resume_days`` (a resumption after a long gap),

and whose event date is at least ``BASE_DAYS`` after the symbol's first bar (so the first
payment the store happens to see is not mistaken for a first payment). The event date is

    * ``timing="announced"``: the dividend's ``known`` day from ``announced_on(symbol, d)`` --
      the declaration date when the store has one, else the ex-date;
    * ``timing="ex"``: the ex-date, for the dividends of ``announced_on(symbol, d)`` whose
      ex-date is on or before d (``known_on``'s set, re-ordered by ex-date): the paired control.

Live events (d - event < ``hold_days``) among F4-screened point-in-time members are ranked held
names first, then the newest event, then the symbol; the first ``inner.top`` are held at equal
weight 1/top and the rest of the book sits in SPY. Behind the SPY-200 switch the book is all
cash while SPY is below its 200-day average. Without the market's calendar nothing is targeted
(the market-aware allocator contract).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import T20, RaisePrepared, _first_bar
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import (
    WEEKLY_HOLD_FRAC_GOTRADE,
    events,
)
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

ADDED = date(2026, 10, 10)
BASE_DAYS = 400  # bars needed before an event, so the store's first-seen payment is not a "first"

Timing = Literal["announced", "ex"]
_TIMINGS: tuple[str, ...] = ("announced", "ex")


@dataclass(frozen=True, slots=True)
class InitParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines and times the event."""

    inner: FactorParams
    timing: Timing = "announced"
    hold_days: int = 365
    resume_days: int = 730
    park: bool = True
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.timing, str) or self.timing not in _TIMINGS:
            raise ValueError(f"timing must be one of {_TIMINGS}, got {self.timing!r}")
        for name in ("hold_days", "resume_days"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 20:
                raise ValueError(f"{name} must be an int >= 20, got {v!r}")
        if not isinstance(self.park, bool):
            raise TypeError(f"park must be a bool, got {type(self.park).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "timing": self.timing,
            "hold_days": str(self.hold_days),
            "resume_days": str(self.resume_days),
            "park": str(self.park).lower(),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> InitParams:
    if not isinstance(params, InitParams):
        raise TypeError(f"params must be InitParams, got {type(params).__name__}")
    return params


def initiation(paid: tuple[tuple[date, Decimal], ...], first_bar: date | None, data_date: date,
               p: InitParams) -> date | None:
    """The event date of the newest initiation or resumption in ``paid`` while it is live, else None."""
    if first_bar is None:
        return None
    for i in range(len(paid) - 1, -1, -1):
        e = paid[i][0]
        if (data_date - e).days >= p.hold_days:
            return None
        if i > 0 and (e - paid[i - 1][0]).days < p.resume_days:
            continue
        if first_bar <= e - timedelta(days=BASE_DAYS):
            return e
    return None


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: InitParams) -> tuple[Target, ...]:
    live: list[tuple[int, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        paid, _ = events(calendar, r.symbol, data_date, p.timing)
        e = initiation(paid, _first_bar(history.get(r.symbol)), data_date, p)
        if e is None:
            continue
        live.append((0 if r.symbol in held else 1, -e.toordinal(), r.symbol, r))
    live.sort(key=lambda t: (t[0], t[1], t[2]))
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for _, _, _, r in live[: p.inner.top]:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    if p.park:
        rest = Decimal(1) - w * len(out)
        mh = history.get(p.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(p.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


class DividendInitiationAllocator:
    """Members that just started (or restarted) paying a dividend, held a year; rest SPY."""

    id = "M0081"
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
        p = _check(params)
        return (p.market,) if p.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: InitParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
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


INITIATION = DividendInitiationAllocator()

T10 = replace(T20, top=10)  # F4's screen and SPY-200 switch, 10 slots at 10%


def _v(suffix: str, params: InitParams, rationale: str, rules: Any = WEEKLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0081-{suffix}", family="M0081", rules=rules, allocator=INITIATION,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0081",
    name="Buy a company the week its board declares its first-ever dividend",
    family="stock-dividend-initiation",
    source_kind="paper",
    source_ref=(
        "Michaely, Thaler & Womack (1995) JF 50(2): about +7.5% over 12 months after initiations; "
        "Asquith & Mullins (1983) JB 56(1); Boehme & Sorescu (2002) JF 57(2) on resumptions; "
        "declaration dates from the one-month EODHD pull (2026-10-10)"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1983-1995, so the whole dev window is after the crowd could know it. A first "
        "dividend is the strongest form of the dividend signal in the papers: a ~3% announcement "
        "jump and months of upward drift. M0070 counted initiations only until the company's next "
        "payment (about a quarter) and saw them on the ex-date. Here: a point-in-time S&P 500 / "
        "Nasdaq-100 member passing F4's $5 price and $20M dollar-volume screen whose dividend is "
        "its first in the store (with 400+ days of price history before it) or comes 730+ days "
        "after its previous one (a resumption). Held for hold_days from the event date whatever it "
        "pays later, up to 10 names at 10% (slots doubled from the idea's 20 x 5% because events "
        "are rare: a pre-run count found about 60 first-ever and 30 resumption events among members "
        "in 1996-2015, 4-5 a year, bunched in 2003-2004 and 2010-2013), held names first then the "
        "newest event, the rest in SPY, behind the SPY-200 switch, fractional at Gotrade's real "
        "fees. Paired design, pre-registered: each announced arm (event = declaration date, else "
        "the ex-date; declaration lead median 15 days on these events, 86% dated) has an ex-date "
        "twin with identical rules, both re-picked weekly so the head start is not wasted (lesson "
        "of M0077; weekly-hold-frac-gotrade has no preset, dev only). A-W12/X-W12 hold a year, "
        "A-W6/X-W6 six months, A-M12/X-M12 a year on the monthly preset (a promotable twin pair). "
        "The quantity of interest is announced minus ex on funded CAGR, worst fall, DSR, 2009-2015 "
        "and walk-forward folds. Success for the data: A-W12 beats X-W12 and A-W6 beats X-W6 by "
        "half a point a year or more on the deposits. Assumed, not tested: the declared-only pair "
        "is dropped (86% dated, so an undated event moves both arms alike); the idea's broader "
        "all-store-stocks variant is dropped because the store holds only today's survivors, so a "
        "non-member in 1998 is there because it later grew into the index (look-ahead); a one-off "
        "special dividend from a non-payer counts as an initiation (no frequency is known then)."
    ),
    expected_failure=(
        "Initiations by index members are rare, so the book is mostly SPY (about 40-60% in stocks "
        "at best) and the arms differ on a handful of events: the paired difference may be within "
        "noise of zero in either direction. The ~3% announcement jump happens on the declaration "
        "day itself, before even the weekly book buys at the next open, so the announced arm gains "
        "only the drift between the jump and the ex-date. Initiators are often maturing growth "
        "companies (Microsoft 2003, Apple-like tech in 2010-2013): their next year may follow tech, "
        "not the dividend. The weekly arms pay more Gotrade fees and churn the SPY-200 switch "
        "(M0076's weekly arms fell 32% at worst against 21% monthly), so the weekly variants likely "
        "break the 20% worst-fall bar and may lag SPY. A widely published 1990s anomaly: even a real "
        "dev edge is likely to fade after 2015. Withholding tax on dividends is not modelled."
    ),
    candidates=(
        _v("A-W12", InitParams(T10, "announced", hold_days=365),
           "First/resumed dividends seen on the declaration day, held a year, re-picked weekly"),
        _v("X-W12", InitParams(T10, "ex", hold_days=365),
           "Paired control: the same events seen on the ex-date, held a year, weekly"),
        _v("A-W6", InitParams(T10, "announced", hold_days=182),
           "Declaration-day timing, held six months, weekly"),
        _v("X-W6", InitParams(T10, "ex", hold_days=182),
           "Paired control: ex-date timing, held six months, weekly"),
        _v("A-M12", InitParams(T10, "announced", hold_days=365),
           "Declaration-day timing, held a year, re-picked monthly (promotable preset)",
           MONTHLY_HOLD_FRAC_GOTRADE),
        _v("X-M12", InitParams(T10, "ex", hold_days=365),
           "Paired control: ex-date timing, held a year, monthly", MONTHLY_HOLD_FRAC_GOTRADE),
    ),
    seen_keys=(
        "concept:dividend-initiation",
        "concept:dividend-resumption",
        "concept:dividend-announcement-timing",
        "nber:w4778",
    ),
)
