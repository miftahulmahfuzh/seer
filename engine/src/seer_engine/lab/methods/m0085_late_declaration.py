"""M0085 — A late dividend declaration as a warning: step out of a stock whose board has not declared on its usual schedule.

Source: Kalay & Loewenstein (1985), "Predictable events and excess returns: the case of dividend
announcements", Journal of Financial Economics 14(3) (announcements made later than expected
carry worse news); Michaely, Thaler & Womack (1995), JF 50(2) (post-omission drift). Batch
sera-20261010-1742, M0076-M0081: the declaration date is worthless as an earlier BUY trigger. Only
a declaration schedule can say a board is LATE before the ex-date would have been due, so this
asks whether it is worth something as a SELL warning.

The overlay never ranks. On data date d it removes *late* names from the host's member set and
from its targets, then lets the host choose as it always does (a late candidate is replaced by the
host's next pick, a late holding is sold). For one stock, read its payments with the overlay's
timing -- ``"decl"``: each payment's ``known`` day (the declaration date when the store has one,
else the ex-date, M0076's convention); ``"ex"``: the ex-dates (the paired control, which reads no
declaration data) -- and take the distinct event days k_1 < k_2 < ... . After event k_i:

    * the stock is a *regular payer* when at least ``REG_N`` events fall in the ``REG_DAYS``
      calendar days ending at k_i and (``"decl"``) its last ``REG_N`` events are all declaration
      dates, so an undated payment's ex-date (about 20 days after its declaration would have
      been) never sets or breaks a schedule;
    * its usual spacing g is the median gap between its last ``GAP_N`` events (k_i included),
      and must be at least ``MIN_GAP`` days;
    * the stock turns *late* on the ``late_sessions``-th NYSE session after k_i + g, unless
      k_{i+1} came first, and stays late until k_{i+1} is known or ``CAP_DAYS`` have passed.

Each late spell reads only events known on its own day: on d it is late exactly when it fired on
or before d and no later event was known by d.

``sell="monthly"`` evaluates the host and the warning on the rules' own data date (monthly rules).
``sell="weekly"`` runs on weekly rules but keeps the host MONTHLY: the host chooses as of the
month's data date (the session before the month's first session, the date the monthly rules
would have used), with the SPY-200 switch read there too, and only the late warning is read
weekly, on d. ``timing="off"`` is the host alone. Symbols the host reads or parks in (SPY) are
never barred. Without the market's calendar nothing is targeted (market-aware contract).
"""

from __future__ import annotations

import statistics
from bisect import bisect_right
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import (
    ANNOUNCED,
    R25,
    WEEKLY_HOLD_FRAC_GOTRADE,
    AnnParams,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import Allocator, prepare_for
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 10)
REG_DAYS = 1095  # a regular payer: 8+ events in the last three years
REG_N = 8
GAP_N = 8  # the usual spacing: median of the gaps between the last 8 events
MIN_GAP = 20  # a spacing under 20 days is noise, not a schedule
CAP_DAYS = 182  # a late spell lasts at most half a year

Timing = Literal["off", "decl", "ex"]
Sell = Literal["monthly", "weekly"]
_TIMINGS: tuple[str, ...] = ("off", "decl", "ex")
_SELLS: tuple[str, ...] = ("monthly", "weekly")
_END = date(9999, 12, 31)


@dataclass(frozen=True, slots=True)
class LateParams:
    """``inner``/``inner_params`` are the host book; the rest defines the warning and its clock."""

    inner: Allocator
    inner_params: Any
    timing: Timing = "decl"
    sell: Sell = "monthly"
    late_sessions: int = 10

    def __post_init__(self) -> None:
        if not isinstance(self.inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(self.inner).__name__}")
        if not isinstance(self.timing, str) or self.timing not in _TIMINGS:
            raise ValueError(f"timing must be one of {_TIMINGS}, got {self.timing!r}")
        if not isinstance(self.sell, str) or self.sell not in _SELLS:
            raise ValueError(f"sell must be one of {_SELLS}, got {self.sell!r}")
        if isinstance(self.late_sessions, bool) or not isinstance(self.late_sessions, int) or self.late_sessions < 1:
            raise ValueError(f"late_sessions must be an int >= 1, got {self.late_sessions!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "inner": self.inner.id,
            "timing": self.timing,
            "sell": self.sell,
            "late_sessions": str(self.late_sessions),
        }
        for k, v in self.inner_params.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> LateParams:
    if not isinstance(params, LateParams):
        raise TypeError(f"params must be LateParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the warning


def event_days(calendar: DividendCalendar, symbol: str, timing: str) -> list[tuple[date, bool]]:
    """``(day, dated)`` for the distinct days a payment of ``symbol`` became visible, ascending.

    ``dated`` is True when the day is a declaration date (``"decl"``; a day shared by a dated and
    an undated payment counts as dated) and always True under ``"ex"``.
    """
    days: dict[date, bool] = {}
    if timing == "decl":
        for a in calendar.announced_on(symbol, _END):
            days[a.known] = days.get(a.known, False) or a.declared
    else:
        for e, _ in calendar.known_on(symbol, _END):
            days[e] = True
    return sorted(days.items())


def _nth_session_after(d: date, n: int) -> date:
    s = d
    for _ in range(n):
        s = dates.next_session(s)
    return s


def late_spells(events: list[tuple[date, bool]], late_sessions: int) -> list[tuple[date, date]]:
    """``(start, end)`` half-open spells during which the stock was late, ascending by start."""
    out: list[tuple[date, date]] = []
    days = [d for d, _ in events]
    for i, k in enumerate(days):
        recent = [x for x in days[: i + 1] if x > k - timedelta(days=REG_DAYS)]
        if len(recent) < REG_N or not all(ok for _, ok in events[i + 1 - REG_N: i + 1]):
            continue
        last = days[max(0, i + 1 - GAP_N): i + 1]
        g = statistics.median((b - a).days for a, b in zip(last, last[1:], strict=False))
        if g < MIN_GAP:
            continue
        fire = _nth_session_after(k + timedelta(days=int(g)), late_sessions)
        nxt = days[i + 1] if i + 1 < len(days) else None
        if nxt is not None and nxt <= fire:
            continue
        end = fire + timedelta(days=CAP_DAYS)
        if nxt is not None and nxt < end:
            end = nxt
        out.append((fire, end))
    return out


def month_data_date(data_date: date) -> date:
    """The data date the monthly rules use for the month of the session after ``data_date``."""
    first = dates.next_session(data_date)
    while dates.prev_session(first).month == first.month:
        first = dates.prev_session(first)
    return dates.prev_session(first)


@dataclass
class LatePrepared:
    history: Mapping[str, History] = field(repr=False)
    calendar: DividendCalendar = field(repr=False)
    market: Any = field(default=None, repr=False)
    _inner: list[tuple[Any, Any]] = field(default_factory=list, repr=False)
    _spells: dict[tuple[str, str, int], tuple[list[date], list[date]]] = field(default_factory=dict, repr=False)

    def inner(self, obj: Any) -> Any:
        for o, v in self._inner:
            if o is obj:
                return v
        v = obj.prepare(self.history) if self.market is None else prepare_for(obj, self.market)
        self._inner.append((obj, v))
        return v

    def late(self, symbol: str, data_date: date, p: LateParams) -> bool:
        key = (symbol, p.timing, p.late_sessions)
        got = self._spells.get(key)
        if got is None:
            spells = late_spells(event_days(self.calendar, symbol, p.timing), p.late_sessions)
            got = ([s for s, _ in spells], [e for _, e in spells])
            self._spells[key] = got
        starts, ends = got
        j = bisect_right(starts, data_date)
        return any(ends[t] > data_date for t in range(max(0, j - 2), j))


class LateDeclarationOverlay:
    """The host book with every name whose board is late on its usual schedule removed."""

    id = "M0085"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return p.inner.lookback(p.inner_params) + (30 if p.sell == "weekly" else 0)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(p.inner.symbols(p.inner_params))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(p.inner.holds(p.inner_params))

    def uses_members(self, params: Any) -> bool:
        p = _check(params)
        return bool(p.inner.uses_members(p.inner_params))

    def _run(self, prepared: LatePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: LateParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no calendar: target nothing (market-aware contract)
            return ()
        inner = prepared.inner(p.inner)
        host_date = data_date if p.sell == "monthly" else month_data_date(data_date)
        if p.timing == "off":
            return p.inner.targets_prepared(inner, members, host_date, held, p.inner_params)
        fixed = set(p.inner.symbols(p.inner_params)) | set(p.inner.holds(p.inner_params))
        barred = {s for s in set(members) | held
                  if s not in fixed and prepared.late(s, data_date, p)}
        kept = frozenset(s for s in members if s not in barred)
        out = p.inner.targets_prepared(inner, kept, host_date, held - barred, p.inner_params)
        return tuple(t for t in out if t.symbol not in barred)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no warning and no target."""
        return self._run(LatePrepared(history, EMPTY_DIVIDENDS), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> LatePrepared:
        return LatePrepared(history, EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> LatePrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return LatePrepared(market.history, calendar, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, LatePrepared):
            raise TypeError(f"prepared must be LatePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


LATE = LateDeclarationOverlay()

HOST = AnnParams(R25, "ex")  # M0076-X-M = M0070-R25-H6-T: big raises seen on the ex-date, monthly


def _v(suffix: str, params: LateParams, rationale: str) -> Candidate:
    rules = MONTHLY_HOLD_FRAC_GOTRADE if params.sell == "monthly" else WEEKLY_HOLD_FRAC_GOTRADE
    return Candidate(id=f"M0085-{suffix}", family="M0085", rules=rules, allocator=LATE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0085",
    name="A late dividend declaration as a warning: step out of a stock whose board has not declared on its usual schedule",
    family="stock-dividend-late-declaration",
    source_kind="knowledge",
    source_ref=(
        "Kalay & Loewenstein (1985), JFE 14(3), late announcements carry bad news; Michaely, "
        "Thaler & Womack (1995), JF 50(2), post-omission drift; batch finding M0076-M0081; "
        "declaration dates from the one-month EODHD pull (2026-10-10)"
    ),
    parent_id=None,
    hypothesis=(
        "Kalay and Loewenstein (1985) report that dividend announcements made later than the "
        "usual schedule carry worse news; published 1985, so the whole dev window is after it. "
        "Only declaration dates can show a board is late before the ex-date was due. A stock is a "
        "regular payer after an event when 8+ events fall in the prior 1095 days; its usual "
        "spacing is the median gap between its last 8 events (at least 20 days); under decl timing "
        "its last 8 events must all carry a declaration date; it turns late "
        "on the 10th NYSE session after last event + spacing with no new event known, and stays "
        "late until the next event is known or 182 days pass. The overlay removes late names from "
        "the host's universe and holdings. Host: M0076-X-M (= M0070-R25-H6-T, big dividend raises "
        "seen on the ex-date, up to 20 F4-screened members at 5%, rest in SPY, SPY-200 switch, "
        "monthly), the strongest dividend book, which holds stocks for six months after a raise "
        "and so meets their next declarations. Fractional at Gotrade's real fees. Six variants, a "
        "2x3 grid: timing off (HOST, must reproduce M0076-X-M) / decl (events on the declaration "
        "day, the ex-date where undated) / ex (paired control: events on the ex-date, the data "
        "the store had before the EODHD pull), each on monthly-hold-frac-gotrade (-M) and on "
        "weekly rules with the host still choosing monthly and only the warning read weekly (-W, "
        "weekly-hold-frac-gotrade, dev only; no weekly SPY switch: M0076/M0078 showed it costs "
        "3-5 points a year). The value of the data is DECL minus EX; the value of the warning is "
        "EX minus HOST; weekly minus monthly is the value of acting fast. Assumed: the "
        "late-event diagnostic (count of late spells and the 3- and 6-month return after them vs "
        "SPY, decl vs ex) is run as a report after the trials, not before. Counted before "
        "registering (counts only, no returns): about 170 late spells a year under decl vs about "
        "30 under ex, among some 400 payers, so declaration schedules are far noisier than "
        "ex-date schedules. The store drops dividends whose ex-date is after 2015-10-16, so "
        "declarations made in the last weeks of the window are missing and decl reads a few "
        "false late spells in Sep-Oct 2015 (both arms, decl more). Success: DECL-M beats "
        "HOST-M and EX-M on funded CAGR or worst fall by half a point or more, same sign on the "
        "weekly pair."
    ),
    expected_failure=(
        "Lateness is rare among big regular payers and mostly clerical: a board meeting moved, a "
        "holiday, a switch of quarter-end, a missing row in the data. The host only holds a name "
        "for six months after a raise, by when its board has just shown confidence, so few of its "
        "holdings ever go late; the overlay may change under 2% of trades like M0077's cut alarm. "
        "The ex-date schedule flags the same boards only a week or two later, so DECL minus EX "
        "is likely under half a point. The weekly arms pay Gotrade fees on weekly resizes of 5% "
        "slots and the SPY park, which may cost more than any warning saves. The host's own "
        "weaknesses carry over: worst fall 21.9%, over the 20% limit, and lagging SPY in "
        "2009-2015. Withholding tax on dividends is not modelled."
    ),
    candidates=(
        _v("HOST-M", LateParams(ANNOUNCED, HOST, timing="off"),
           "Host alone: the big-raise book seen on the ex-date (M0076-X-M), monthly"),
        _v("DECL-M", LateParams(ANNOUNCED, HOST, timing="decl"),
           "Late on its declaration schedule: barred, checked monthly"),
        _v("EX-M", LateParams(ANNOUNCED, HOST, timing="ex"),
           "Control: late on its ex-date schedule, checked monthly"),
        _v("HOST-W", LateParams(ANNOUNCED, HOST, timing="off", sell="weekly"),
           "Host alone on the weekly clock: monthly picks, weekly execution"),
        _v("DECL-W", LateParams(ANNOUNCED, HOST, timing="decl", sell="weekly"),
           "Late on its declaration schedule: sold at the next weekly check"),
        _v("EX-W", LateParams(ANNOUNCED, HOST, timing="ex", sell="weekly"),
           "Control: late on its ex-date schedule, sold at the next weekly check"),
    ),
    seen_keys=(
        "concept:dividend-late-declaration",
        "concept:dividend-announcement-timing",
        "concept:dividend-omission-drift",
        "nber:w4778",
    ),
)
