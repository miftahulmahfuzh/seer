"""M0083 — Raises the market cheered: big dividend raises whose stock beat SPY over the two days after.

Source: variation of M0076 (itself M0070's big-raise book, R25-H6-T); Michaely, Thaler & Womack
(1995), JF 50(2); the earnings-jump books (M0063) for the "direction of the reaction" filter.
Idea: M0076 found that seeing a big raise on its declaration day instead of its ex-date adds no
timing value. What the declaration date does carry is the market's verdict on the news. Keep the
book, admit a raise only when the stock beat SPY over the two sessions starting its event date.

Each arm runs M0076's event logic (``events`` / ``live_event``) unchanged on its own event date
(``timing="announced"``: the declaration date, else the ex-date; ``timing="ex"``: the ex-date).
The latest live raise's *reaction* on data date d, for event date e:

    * t = the symbol's first session on or after e, t-1 the session before it; t+1 <= d is
      required (an event whose window has not closed yet is not admitted on d -- the next
      re-pick sees it);
    * reaction = TR(symbol, t-1 -> t+1) - TR(SPY, the same two dates), where
      TR(x, a -> b) = (close_b + every cash dividend of x with a < ex-date <= b) / close_a.

The store's closes are split-adjusted and NOT dividend-adjusted, so the add-back keeps the
ex-date arm from reading its own dividend's mechanical drop as a cold reception. Dividends are
read only through ``known_on(symbol, d)`` (ex-date <= d), SPY's included when the calendar has
them. ``reaction="up"`` admits reaction > 0, ``"down"`` reaction < 0 (the control); a missing
bar (no t-1, or SPY without a bar on either date) admits nothing.

Everything else is M0070's: F4's member screen and SPY-200 switch, up to 20 names at 5% while the
event is under 182 days old, held names first then the newest event, rest in SPY, monthly,
fractional shares at Gotrade's real fees.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared, _first_bar, live_event
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import R25, AnnParams
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 10)

Reaction = Literal["up", "down"]
_REACTIONS: tuple[str, ...] = ("up", "down")


@dataclass(frozen=True, slots=True)
class ReactParams:
    """``ann`` is M0076's book and timing; ``reaction`` the sign of the two-session excess admitted."""

    ann: AnnParams
    reaction: Reaction = "up"

    def __post_init__(self) -> None:
        if not isinstance(self.ann, AnnParams):
            raise TypeError(f"ann must be AnnParams, got {type(self.ann).__name__}")
        if not isinstance(self.reaction, str) or self.reaction not in _REACTIONS:
            raise ValueError(f"reaction must be one of {_REACTIONS}, got {self.reaction!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"reaction": self.reaction}
        for k, v in self.ann.as_dict().items():
            out[f"ann.{k}"] = v
        return out


def _check(params: object) -> ReactParams:
    if not isinstance(params, ReactParams):
        raise TypeError(f"params must be ReactParams, got {type(params).__name__}")
    return params


def event_rows(calendar: DividendCalendar, symbol: str, data_date: date,
               timing: str) -> list[tuple[date, date, Decimal, bool]]:
    """``(event_date, ex_date, amount, declared)`` known on ``data_date``, ascending by event date."""
    ann = calendar.announced_on(symbol, data_date)
    if timing == "announced":
        return [(a.known, a.ex_date, a.amount, a.declared) for a in ann]
    return sorted(((a.ex_date, a.ex_date, a.amount, a.declared) for a in ann if a.ex_date <= data_date),
                  key=lambda r: r[1])


def _cash(calendar: DividendCalendar, symbol: str, after: date, upto: date, data_date: date) -> float:
    """Cash dividends of ``symbol`` with ``after`` < ex-date <= ``upto``, as known on ``data_date``."""
    return float(sum((a for d, a in calendar.known_on(symbol, data_date) if after < d <= upto), Decimal(0)))


def reaction(h: History, market: History | None, calendar: DividendCalendar, market_symbol: str,
             e: date, data_date: date) -> float | None:
    """Total return of ``h`` minus SPY's over the two sessions starting ``e``, or None."""
    if market is None:
        return None
    i = int(np.searchsorted(h.dates, as_day(e), side="left"))
    if i < 1 or i + 1 >= len(h) or h.dates[i + 1] > as_day(data_date):
        return None
    d0: date = h.dates[i - 1].item()
    d2: date = h.dates[i + 1].item()
    j0, j2 = market.index_of(d0), market.index_of(d2)
    if j0 is None or j2 is None:
        return None
    c0, m0 = float(h.close[i - 1]), float(market.close[j0])
    if c0 <= 0 or m0 <= 0:
        return None
    s = (float(h.close[i + 1]) + _cash(calendar, h.symbol, d0, d2, data_date)) / c0
    m = (float(market.close[j2]) + _cash(calendar, market_symbol, d0, d2, data_date)) / m0
    out = s - m
    return out if np.isfinite(out) else None


def admitted(r: float | None, p: ReactParams) -> bool:
    if r is None:
        return False
    return r > 0 if p.reaction == "up" else r < 0


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: ReactParams) -> tuple[Target, ...]:
    a = p.ann
    b = a.base
    mh = history.get(b.market)
    live: list[tuple[int, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == b.market:
            continue
        ev = event_rows(calendar, r.symbol, data_date, a.timing)
        if not ev:
            continue
        if a.declared_only and not ev[-1][3]:
            continue
        h = history.get(r.symbol)
        e = live_event(tuple((x[0], x[2]) for x in ev), _first_bar(h), data_date, b)
        if e is None or h is None:
            continue
        if not admitted(reaction(h, mh, calendar, b.market, e, data_date), p):
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
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(b.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


class CheeredRaiseAllocator:
    """M0076's big-raise book, admitting only raises the market cheered (or, the control, did not)."""

    id = "M0083"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).ann.base.inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        b = _check(params).ann.base
        fixed = {b.market}
        if b.inner.trend is not None:
            fixed.add(b.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        b = _check(params).ann.base
        return (b.market,) if b.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: ReactParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        inner = p.ann.base.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
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


CHEERED = CheeredRaiseAllocator()


def _v(suffix: str, params: ReactParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0083-{suffix}", family="M0083", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CHEERED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0083",
    name="Raises the market cheered: big dividend raises whose stock beat SPY over the two days after the announcement",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0076 (M0070-R25-H6-T's book); Michaely, Thaler & Womack (1995), JF 50(2); "
        "reaction-direction filter after M0063; declaration dates from the one-month EODHD pull "
        "(2026-10-10)"
    ),
    parent_id="M0076",
    hypothesis=(
        "Published 1994-1995 (dividend-change drift) and the announcement-reaction literature is "
        "older still, so most of the dev window is after the crowd knew both. M0076 showed that "
        "seeing a big raise on its declaration day instead of its ex-date adds nothing to the "
        "timing (0.3-1.1 points a year worse in all three pairs): the one-day reaction is gone "
        "before the next open and the slow drift is caught either way. What the declaration date "
        "really carries is the market's reaction to the news. Keep M0070's monthly big-raise book "
        "(latest dividend >= 25% over the median of up to four prior payments in 400 days and at "
        "most double, or a first payment; up to 20 F4-screened members at 5% while the event is "
        "under 182 days old, held names first then the newest event, rest SPY, SPY-200 switch, "
        "fractional at Gotrade's real fees) but admit a raise only when its total return beat "
        "SPY's over the two sessions starting the event date (close before to close of the next "
        "session, dividends in the window added back since closes are not dividend-adjusted; the "
        "event waits until that window has closed). Variants, all monthly: A-UP announced and "
        "cheered (the idea); X-UP the paired ex-date control, the same filter over the two "
        "sessions starting the ex-date, all the old data allowed; A-DN / X-DN the reaction-"
        "negative controls; A-UP-D / X-UP-D the up pair counting only dividends that carry a "
        "declaration date, so the undated ~13% (whose announced reaction is really an ex-date "
        "reaction) cannot blur it. Unfiltered controls already exist: M0076-A-M (+10.3% a year "
        "funded) and M0076-X-M (+10.9%). The quantity of interest is A-UP minus X-UP on funded "
        "CAGR, worst fall, DSR, 2009-2015 and walk-forward folds, and UP minus DN in each arm. "
        "Success for the data: A-UP beats X-UP by a point a year or more and beats A-DN, with "
        "the dated pair agreeing in sign."
    ),
    expected_failure=(
        "The filter roughly halves the set of live raises, so fewer of the 20 slots fill and "
        "more of the book sits in SPY; the edge then shrinks toward SPY's whether the filter "
        "selects or not. The two-day excess return of a big company is mostly noise (market "
        "moves, unrelated news) rather than a verdict on the dividend, so A-UP and A-DN may "
        "differ by little; and short-term reversal (M0028) would make a hot two-day start a "
        "small negative. The ex-date control may score the same as the announced arm because "
        "the drift is slow and either window samples similar noise. M0070's weaknesses carry "
        "over: worst fall near the 20% limit (21-22% in fast falls before the SPY-200 switch "
        "turns), and lagging SPY in 2009-2015 when big-company growth led. A widely published "
        "anomaly from the 1990s: even a real dev edge is likely to fade after 2015. Withholding "
        "tax on dividends is not modelled."
    ),
    candidates=(
        _v("A-UP", ReactParams(AnnParams(R25, "announced"), "up"),
           "Big raises whose stock beat SPY over the two sessions from the declaration day"),
        _v("X-UP", ReactParams(AnnParams(R25, "ex"), "up"),
           "Paired control: the same filter over the two sessions from the ex-date"),
        _v("A-DN", ReactParams(AnnParams(R25, "announced"), "down"),
           "Reaction-negative control: raises that lagged SPY from the declaration day"),
        _v("X-DN", ReactParams(AnnParams(R25, "ex"), "down"),
           "Reaction-negative control on the ex-date"),
        _v("A-UP-D", ReactParams(AnnParams(R25, "announced", declared_only=True), "up"),
           "Cheered on the declaration day, only dividends that carry a declaration date"),
        _v("X-UP-D", ReactParams(AnnParams(R25, "ex", declared_only=True), "up"),
           "Paired control: cheered on the ex-date, the same dated-only events"),
    ),
    seen_keys=(
        "concept:dividend-announcement-reaction",
        "concept:dividend-announcement-timing",
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "nber:w4778",
    ),
)
