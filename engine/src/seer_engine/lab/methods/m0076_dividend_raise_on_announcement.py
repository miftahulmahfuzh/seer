"""M0076 — Buy the big dividend raise on the day it is announced, not weeks later when it goes ex.

Source: variation of M0070 (its close miss R25-H6-T); Michaely, Thaler & Womack (1995), JF 50(2).
Idea: M0070 saw each raise only on its ex-date, a median ~20 days after the board declared it.
The store now carries declaration dates for ~87% of the dev window's dividends
(``Market.dividends.announced_on``), so the same book can see the raise when the market did.
The method is a paired experiment: every announcement-timed variant has an ex-date-timed twin
with otherwise identical rules, and the paired difference is the value of the data.

M0070's event logic (``classify`` / ``live_event``) is reused unchanged on a list of
``(event_date, amount)`` pairs, where the event date is

    * ``timing="announced"``: the dividend's ``known`` day from ``announced_on(symbol, d)`` --
      the declaration date when the store has one, else the ex-date;
    * ``timing="ex"``: the ex-date, for the dividends of ``announced_on(symbol, d)`` whose
      ex-date is on or before d (exactly ``known_on``'s set, re-ordered by ex-date).

The baseline window, the initiation test, the hold clock and the "newest event first" ranking
all run on that event date, so the announced arm also exits its hold ~20 days earlier: each arm
holds the same length of time from the day it could see the raise.

``declared_only`` (both arms alike) counts an event only when the latest dividend carries a
declaration date, so the pair compares the same events and the undated ~13% cannot blur it.

Everything else is M0070's: F4's member screen and SPY-200 switch, up to 20 names at 5%, the
rest in SPY, fractional shares at Gotrade's real fees.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import (
    T20,
    RaiseParams,
    RaisePrepared,
    _first_bar,
    live_event,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, WEEKLY_HOLD
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 10)

# Weekly re-pick in fractional shares at Gotrade's real fees (as M0063). No preset of this id
# exists: it runs on dev, and `promote` would need one (a feature-wish if it wins).
WEEKLY_HOLD_FRAC_GOTRADE = replace(WEEKLY_HOLD, id="weekly-hold-frac-gotrade", fractional=True,
                                   cost_model="gotrade")

Timing = Literal["announced", "ex"]
_TIMINGS: tuple[str, ...] = ("announced", "ex")


@dataclass(frozen=True, slots=True)
class AnnParams:
    """``base`` is M0070's event and book; ``timing`` picks the event date; ``declared_only`` the events."""

    base: RaiseParams
    timing: Timing = "announced"
    declared_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.base, RaiseParams):
            raise TypeError(f"base must be RaiseParams, got {type(self.base).__name__}")
        if not isinstance(self.timing, str) or self.timing not in _TIMINGS:
            raise ValueError(f"timing must be one of {_TIMINGS}, got {self.timing!r}")
        if not isinstance(self.declared_only, bool):
            raise TypeError(f"declared_only must be a bool, got {type(self.declared_only).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"timing": self.timing, "declared_only": str(self.declared_only).lower()}
        for k, v in self.base.as_dict().items():
            out[f"base.{k}"] = v
        return out


def _check(params: object) -> AnnParams:
    if not isinstance(params, AnnParams):
        raise TypeError(f"params must be AnnParams, got {type(params).__name__}")
    return params


def events(calendar: DividendCalendar, symbol: str, data_date: date,
           timing: str) -> tuple[tuple[tuple[date, Decimal], ...], bool]:
    """``(event_date, amount)`` pairs known on ``data_date``, ascending, and the latest one's ``declared``."""
    ann = calendar.announced_on(symbol, data_date)
    if timing == "announced":
        rows = [(a.known, a.ex_date, a.amount, a.declared) for a in ann]
    else:
        rows = sorted(((a.ex_date, a.ex_date, a.amount, a.declared) for a in ann if a.ex_date <= data_date),
                      key=lambda r: r[1])
    if not rows:
        return (), False
    return tuple((r[0], r[2]) for r in rows), rows[-1][3]


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: AnnParams) -> tuple[Target, ...]:
    b = p.base
    live: list[tuple[int, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == b.market:
            continue
        paid, declared = events(calendar, r.symbol, data_date, p.timing)
        if p.declared_only and not declared:
            continue
        e = live_event(paid, _first_bar(history.get(r.symbol)), data_date, b)
        if e is None:
            continue
        live.append((0 if r.symbol in held else 1, -e.toordinal(), r.symbol, r))
    live.sort(key=lambda t: (t[0], t[1], t[2]))
    w = equal_weight(b.inner.top)
    out: list[Target] = []
    for _, _, _, r in live[: b.inner.top]:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    if b.park:
        rest = Decimal(1) - w * len(out)
        mh = history.get(b.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(b.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


class AnnouncedRaiseAllocator:
    """M0070's big-raise book, with the raise seen on its declaration day or its ex-date."""

    id = "M0076"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).base.inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        b = _check(params).base
        fixed = {b.market}
        if b.inner.trend is not None:
            fixed.add(b.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        b = _check(params).base
        return (b.market,) if b.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: AnnParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, p.base.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.base.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.base.inner)
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


ANNOUNCED = AnnouncedRaiseAllocator()

R25 = RaiseParams(T20, raise_min=Decimal("0.25"))  # M0070-R25-H6-T's event and book


def _v(suffix: str, params: AnnParams, rationale: str, rules: Any = MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"M0076-{suffix}", family="M0076", rules=rules, allocator=ANNOUNCED,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0076",
    name="Buy the big dividend raise on the day it is announced, not weeks later when it goes ex",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0070 (R25-H6-T close miss); Michaely, Thaler & Womack (1995), JF 50(2); "
        "declaration dates from the one-month EODHD pull (2026-10-10)"
    ),
    parent_id="M0070",
    hypothesis=(
        "Published 1994-1995, so most of the dev window is after the crowd could know the "
        "dividend-change drift. M0070's big-raise book (latest dividend >= 25% over the median of "
        "the up-to-four prior payments in 400 days and at most double, or a first payment; up to "
        "20 F4-screened members at 5% while the event is under 182 days old, held names first then "
        "the newest event, rest in SPY, monthly, behind the SPY-200 switch, fractional at "
        "Gotrade's real fees) beat SPY by 3.7 points a year on the deposits but only saw each "
        "raise on its ex-date, a median 19-20 days after the board declared it (the store now "
        "has declaration dates for 85-93% of dividends each year 1996-2015). If part of the drift "
        "happens between declaration and ex-date, acting on the declaration day should add return. "
        "Paired design, pre-registered: each announced variant (event date = declaration date, "
        "else the ex-date) has an ex-date twin with identical rules; the hold clock, baseline and "
        "ranking run on each arm's own event date. A-M / X-M monthly re-pick (X-M should "
        "reproduce M0070-R25-H6-T); A-W / X-W re-pick weekly so a monthly clock does not waste a "
        "20-day head start (weekly-hold-frac-gotrade, no preset exists, dev only); A-M-D / X-M-D "
        "monthly counting only dividends that carry a declaration date, in both arms, so coverage "
        "gaps cannot blur the pair. The quantity of interest is announced minus ex on funded CAGR, "
        "worst fall, DSR, 2009-2015 and walk-forward folds; passing the gate is secondary. "
        "Success for the data: A-W beats X-W and A-M beats X-M by a point a year or more, with "
        "the declared-only pair agreeing in sign."
    ),
    expected_failure=(
        "The announcement-day jump (a percent or two for a raise) happens in one day, before even "
        "the weekly book can buy at the next open, while the slow months-long drift M0070 caught "
        "is the same in both arms, so the paired difference is about zero. The monthly pair "
        "differs little anyway: a 20-day earlier sighting often lands in the same monthly "
        "re-pick. Exiting 20 days earlier may give back drift as easily as it gains it. The "
        "weekly arms pay more Gotrade fees on 5% slots and the weekly SPY resize, which may eat "
        "any gain. M0070's own weaknesses carry over: worst fall near the 20% limit (21.9% "
        "in 1998-2002 fast falls before the switch turns), and lagging SPY in 2009-2015 when "
        "big-company growth led. A widely published anomaly from the 1990s: even a real dev "
        "edge is likely to fade after 2015. Withholding tax on dividends is not modelled."
    ),
    candidates=(
        _v("A-M", AnnParams(R25, "announced"),
           "Big raises seen on the declaration day, re-picked monthly"),
        _v("X-M", AnnParams(R25, "ex"),
           "Paired control: the same book seeing the raise on its ex-date (M0070-R25-H6-T)"),
        _v("A-W", AnnParams(R25, "announced"),
           "Big raises seen on the declaration day, re-picked weekly", WEEKLY_HOLD_FRAC_GOTRADE),
        _v("X-W", AnnParams(R25, "ex"),
           "Paired control: ex-date timing, re-picked weekly", WEEKLY_HOLD_FRAC_GOTRADE),
        _v("A-M-D", AnnParams(R25, "announced", declared_only=True),
           "Declaration-day timing, only dividends with a declaration date, monthly"),
        _v("X-M-D", AnnParams(R25, "ex", declared_only=True),
           "Paired control: ex-date timing on the same declared-only events, monthly"),
    ),
    seen_keys=(
        "concept:dividend-announcement-timing",
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "nber:w4778",
    ),
)
