"""M0077 — Sell or skip a stock the day its board cuts or stops the dividend: a cut alarm over two existing books.

Source: Michaely, Thaler & Womack (1995), "Price reactions to dividend initiations and
omissions: overreaction or drift?", Journal of Finance 50(2), 573-608 (NBER w4778, 1994;
post-omission drift of about -11% over a year); Grullon, Michaely & Swaminathan (2002), "Are
dividend changes a sign of firm maturity?", Journal of Business 75(3).
Idea: a board that cuts or stops its dividend is telling the market the business is worse than
the price says, and the papers report months of underperformance afterwards. Laid over a book we
already have, a cut alarm should drop the names about to drift down. The question this batch asks
is whether the declaration dates bought from EODHD make the alarm worth more than the ex-dates the
store already had, so every overlay is pre-registered twice: timed on the declaration day and
timed on the ex-date (the paired control), on the same host.

The overlay never ranks. On every data date d it removes *barred* names from the host's member
set and from the host's targets, then lets the host choose as it always does, so a barred
candidate is replaced by the host's next pick and a barred holding is sold at the host's next
check. A name is barred on d when one of its alarms fired on a day a with a <= d < a + bar_days.
An alarm is, for a stock's payments read with the overlay's timing (``known`` = the declaration
day when the store has one, else the ex-date, for ``timing="announce"``; ``known`` = the ex-date
for ``timing="ex"``):

    * a *cut* on payment i, firing on known_i, when amount_i <= ``cut_ratio`` x the median of the
      up-to-four previous payments that went ex in the 400 days before ex_i and were themselves
      known by known_i (at least two of them, so a first or second payment is never a cut);
    * an *omission* after payment k, firing on ex_k + ceil(``omit_mult`` x g), where g is the
      median gap between the last up-to-five ex-dates (k included) within 730 days before ex_k
      and known by known_k (at least three payments, g >= 20 days), when no later payment of the
      stock is known by that day. The alarm reads only what was known on its own day: either a
      next payment had been announced by then or it had not. It is anchored on the ex-date in
      both timings: some boards declare a payment a quarter ahead, and silence measured from such
      a declaration fires before the next one is due (a check of the store found 401 such false
      alarms), so the declaration dates speed up the cut alarm, not the omission alarm.

``timing="off"`` is the host alone: nothing is ever barred. Symbols the host reads or parks in
(SPY, the trend instrument) are never barred -- SPY's own distributions vary and must not switch
the book off. Without the market's calendar (the history-only ``prepare``/``targets`` path)
nothing is targeted, which is the market-aware allocator contract.
"""

from __future__ import annotations

import math
import statistics
from bisect import bisect_right
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0028_short_term_reversal import CALM_RESID, REVERSAL
from seer_engine.lab.methods.m0063_earnings_day_jump import JUMP, JumpParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import Allocator, prepare_for
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 10)
BASE_DAYS = 400  # a cut's baseline: payments that went ex in the 400 days before it
BASE_N = 4  # payments in the cut baseline median
GAP_DAYS = 730  # an omission's rhythm: ex-dates in the two years before the last payment
GAP_N = 5  # payments whose gaps set the rhythm
MIN_GAP = 20  # a rhythm under 20 days is noise, not a schedule

Timing = Literal["off", "announce", "ex"]
_TIMINGS: tuple[str, ...] = ("off", "announce", "ex")
_END = date(9999, 12, 31)  # "every row": the alarms are built per row from what that row's day knew


@dataclass(frozen=True, slots=True)
class CutParams:
    """``inner``/``inner_params`` are the host book; the rest defines the alarm and the bar."""

    inner: Allocator
    inner_params: Any
    timing: Timing = "announce"
    cut_ratio: Decimal = Decimal("0.75")
    omit_mult: Decimal = Decimal("1.5")
    bar_days: int = 182

    def __post_init__(self) -> None:
        if not isinstance(self.inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(self.inner).__name__}")
        if not isinstance(self.timing, str) or self.timing not in _TIMINGS:
            raise ValueError(f"timing must be one of {_TIMINGS}, got {self.timing!r}")
        if not isinstance(self.cut_ratio, Decimal) or not self.cut_ratio.is_finite() or not 0 < self.cut_ratio < 1:
            raise ValueError(f"cut_ratio must be a Decimal in (0, 1), got {self.cut_ratio!r}")
        if not isinstance(self.omit_mult, Decimal) or not self.omit_mult.is_finite() or self.omit_mult <= 1:
            raise ValueError(f"omit_mult must be a Decimal > 1, got {self.omit_mult!r}")
        if isinstance(self.bar_days, bool) or not isinstance(self.bar_days, int) or self.bar_days < 1:
            raise ValueError(f"bar_days must be an int >= 1, got {self.bar_days!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "inner": self.inner.id,
            "timing": self.timing,
            "cut_ratio": str(self.cut_ratio),
            "omit_mult": str(self.omit_mult),
            "bar_days": str(self.bar_days),
        }
        for k, v in self.inner_params.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CutParams:
    if not isinstance(params, CutParams):
        raise TypeError(f"params must be CutParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the alarms


def payments(calendar: DividendCalendar, symbol: str, timing: str) -> list[tuple[date, date, Decimal]]:
    """``(known, ex_date, amount)`` for every stored payment of ``symbol``, ascending by ex-date."""
    if timing == "announce":
        rows = [(a.known, a.ex_date, a.amount) for a in calendar.announced_on(symbol, _END)]
    else:
        rows = [(e, e, amt) for e, amt in calendar.known_on(symbol, _END)]
    rows.sort(key=lambda r: r[1])
    return rows


def alarms(rows: list[tuple[date, date, Decimal]], cut_ratio: Decimal, omit_mult: Decimal) -> list[date]:
    """The days a cut or omission alarm fired for one stock, ascending.

    Each alarm reads only payments known on or before the day it fires (see the module doc).
    """
    out: list[date] = []
    for i, (known, ex, amount) in enumerate(rows):
        seen = [r for r in rows[:i] if r[0] <= known]
        base = [r[2] for r in seen if r[1] > ex - timedelta(days=BASE_DAYS)][-BASE_N:]
        if len(base) >= 2 and amount <= cut_ratio * statistics.median(base):
            out.append(known)
        rhythm = [r[1] for r in seen if r[1] > ex - timedelta(days=GAP_DAYS)][-(GAP_N - 1):] + [ex]
        if len(rhythm) < 3:
            continue
        gap = statistics.median((b - a).days for a, b in zip(rhythm, rhythm[1:], strict=False))
        if gap < MIN_GAP:
            continue
        fire = ex + timedelta(days=math.ceil(float(omit_mult) * gap))
        if not any(r[1] > ex and r[0] <= fire for r in rows[i + 1:]):
            out.append(fire)
    return sorted(set(out))


@dataclass
class CutPrepared:
    history: Mapping[str, History] = field(repr=False)
    calendar: DividendCalendar = field(repr=False)
    market: Any = field(default=None, repr=False)
    _inner: list[tuple[Any, Any]] = field(default_factory=list, repr=False)
    _alarms: dict[tuple[str, str, Decimal, Decimal], list[date]] = field(default_factory=dict, repr=False)

    def inner(self, obj: Any) -> Any:
        for o, v in self._inner:
            if o is obj:
                return v
        v = obj.prepare(self.history) if self.market is None else prepare_for(obj, self.market)
        self._inner.append((obj, v))
        return v

    def barred(self, symbol: str, data_date: date, p: CutParams) -> bool:
        key = (symbol, p.timing, p.cut_ratio, p.omit_mult)
        fired = self._alarms.get(key)
        if fired is None:
            fired = alarms(payments(self.calendar, symbol, p.timing), p.cut_ratio, p.omit_mult)
            self._alarms[key] = fired
        j = bisect_right(fired, data_date)
        return j > 0 and (data_date - fired[j - 1]).days < p.bar_days


class DividendCutOverlay:
    """The host book with every name under a live cut or omission alarm removed; host alone when off."""

    id = "M0077"
    market_fields = ("dividends",)  # reads Market.dividends, never Market.fundamentals

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return p.inner.lookback(p.inner_params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(p.inner.symbols(p.inner_params))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(p.inner.holds(p.inner_params))

    def uses_members(self, params: Any) -> bool:
        p = _check(params)
        return bool(p.inner.uses_members(p.inner_params))

    def _run(self, prepared: CutPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CutParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no calendar: target nothing (market-aware contract)
            return ()
        inner = prepared.inner(p.inner)
        if p.timing == "off":
            return p.inner.targets_prepared(inner, members, data_date, held, p.inner_params)
        fixed = set(p.inner.symbols(p.inner_params)) | set(p.inner.holds(p.inner_params))
        barred = {s for s in set(members) | held
                  if s not in fixed and prepared.barred(s, data_date, p)}
        kept = frozenset(s for s in members if s not in barred)
        out = p.inner.targets_prepared(inner, kept, data_date, held - barred, p.inner_params)
        return tuple(t for t in out if t.symbol not in barred)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no alarm and no target."""
        return self._run(CutPrepared(history, EMPTY_DIVIDENDS), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CutPrepared:
        return CutPrepared(history, EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> CutPrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return CutPrepared(market.history, calendar, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CutPrepared):
            raise TypeError(f"prepared must be CutPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


CUT = DividendCutOverlay()

EDJ = JumpParams(N20)  # M0063-M-N20-TREND's host: monthly news-day jumps, 20 slots, SPY-200 switch


def _v(suffix: str, params: CutParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0077-{suffix}", family="M0077", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CUT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0077",
    name="Sell or skip a stock the day its board cuts or stops the dividend: a cut alarm laid over two books we already have",
    family="stock-dividend-cut-overlay",
    source_kind="paper",
    source_ref=(
        "Michaely, Thaler & Womack (1995), Price Reactions to Dividend Initiations and Omissions, "
        "JF 50(2); https://www.nber.org/papers/w4778; Grullon, Michaely & Swaminathan (2002), JB 75(3)"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1994-1995, so most of the dev window is after the crowd could know it. Batch "
        "sera-20261010-1742 asks whether the paid-for dividend declaration dates improve methods we "
        "already have. A board that cuts its dividend (the new amount at most 75% of the median of "
        "its up-to-four previous payments in the prior 400 days, at least two of them) or stops it "
        "(a regular payer, three or more payments, with nothing new known 1.5 of its usual gaps "
        "after the last ex-date, in both timings: measured from a declaration made a quarter "
        "ahead it fires falsely) is followed by months of underperformance in the papers (about -11% "
        "over a year after an omission). The overlay removes such a name from the host's universe "
        "for 182 days from the alarm: a held name is sold at the host's next monthly check and a "
        "candidate is skipped for the host's next pick. Two hosts that hold the names a cut is most "
        "likely to hit, both monthly, fractional, at Gotrade's real fees on "
        "monthly-hold-frac-gotrade: EDJ = M0063-M-N20-TREND (news-day jumps; close miss, +4.4 "
        "points a year over SPY with a 25% worst fall) and REV = M0028-CALM-RESID (last month's "
        "calm fallers, the most cut-prone names by construction). For each host: HOST (overlay off; "
        "must reproduce the host's recorded trial), ANN (alarm on the declaration day, the ex-date "
        "where the store has no declaration date, about 13% of payments) and EX (the paired "
        "control: the identical alarm on the ex-date, which is all the store knew before the "
        "EODHD pull). The value of the data is ANN minus EX on funded CAGR, worst fall, DSR, the "
        "2009-2015 era and the walk-forward folds; the value of the alarm itself is EX minus HOST. "
        "Assumed, not tested: the dated-only second pair is dropped because 87% of 1996-2015 "
        "payments carry a declaration date, so coverage gaps cannot move the pair much, and the "
        "six-variant cap is better spent on a second host. Success for the data: ANN beats EX on "
        "both hosts in the same direction; success for the alarm: ANN and EX both beat HOST."
    ),
    expected_failure=(
        "Cuts among big index members are rare (about 30 a year in the whole store, 290 in "
        "2008-2009), and both hosts sit in cash behind the SPY 200-day switch for most of 2008-2009, "
        "so the overlay changes few trades and every paired difference may be inside noise. The "
        "news-day host holds stocks that just jumped on good news, which rarely cut, so on EDJ the "
        "overlay should do almost nothing. The declaration lands about 19 days before the ex-date "
        "and the price falls on the declaration day itself, so neither arm escapes the first drop; "
        "the announcement arm only gains the drift between declaration and ex-date, and only when "
        "the two fall in different months of the host's monthly check. An omission has no row, so "
        "a gap in the store's dividend history (a missed payment in the data, a switch from "
        "quarterly to half-yearly) reads as an omission in both arms alike. Removing a fallen "
        "payer can also remove a bounce the reversal host was paid for, so on REV the alarm may "
        "cost money. Expected: |ANN - EX| under half a point a year on both hosts."
    ),
    candidates=(
        _v("EDJ-HOST", CutParams(JUMP, EDJ, timing="off"),
           "Host alone: the monthly news-day book (M0063-M-N20-TREND), overlay off"),
        _v("EDJ-ANN", CutParams(JUMP, EDJ, timing="announce"),
           "News-day book, cut/omission names barred 6 months from the declaration day"),
        _v("EDJ-EX", CutParams(JUMP, EDJ, timing="ex"),
           "Control: the same alarm timed on the ex-date"),
        _v("REV-HOST", CutParams(REVERSAL, CALM_RESID, timing="off"),
           "Host alone: last month's calm fallers (M0028-CALM-RESID), overlay off"),
        _v("REV-ANN", CutParams(REVERSAL, CALM_RESID, timing="announce"),
           "Calm-fallers book, cut/omission names barred 6 months from the declaration day"),
        _v("REV-EX", CutParams(REVERSAL, CALM_RESID, timing="ex"),
           "Control: the same alarm timed on the ex-date"),
    ),
    seen_keys=(
        "concept:dividend-cut-drift",
        "concept:dividend-omission-drift",
        "concept:dividend-announcement-timing",
        "nber:w4778",
    ),
)
