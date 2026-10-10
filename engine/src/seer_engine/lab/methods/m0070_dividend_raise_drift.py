"""M0070 — Follow a dividend raise: buy big companies right after they raise or start their dividend.

Source: Michaely, Thaler & Womack (1995), "Price reactions to dividend initiations and
omissions: overreaction or drift?", Journal of Finance 50(2), 573-608 (NBER w4778, 1994);
Boehme & Sorescu (2002), "The long-run performance following dividend initiations and
resumptions: underreaction or product of chance?", Journal of Finance 57(2).
Idea: a dividend raise is a costly signal of a manager's confidence, and the price is reported
to keep drifting up for months after it (about +7.5% in the 12 months after an initiation in the
1995 paper). The store holds every member's cash dividends by ex-date, so the event is visible
point in time on its ex-date (weeks after the announcement, which is the price of not having
announcement dates).

The frame is F4's -- point-in-time S&P 500 / Nasdaq-100 members, the $5 price and $20M daily
dollar-volume screen, optionally the SPY 200-day trend switch, monthly, fractional shares at
Gotrade's real fees on ``monthly-hold-frac-gotrade`` -- with the ranking replaced by the
dividend calendar (``Market.dividends``, read only through ``known_on(symbol, data_date)``).

A member's *latest event* on data date d is its most recent ex-date e <= d, amount a, with
d - e < ``hold_days`` calendar days. The *baseline* is the median of the up to four payments
with ex-dates in the 400 days before e. The event is:

    * a *raise* when a >= baseline x (1 + ``raise_min``) and a <= baseline x (1 + ``raise_max``)
      (the cap drops one-off special dividends, which look like a doubling or more);
    * an *initiation* when no payment went ex in the 400 days before e and the stock has bars
      at least 400 days before e (so the first payment in the store's history is not counted);
    * *flat* when |a / baseline - 1| <= ``flat_tol`` (the control's event).

``kind="raise"`` holds raises and initiations; ``kind="flat"`` holds flat events. Live events
are ranked held names first (a name keeps its slot while its event is live and it passes the
screen), then the newest ex-date, then the symbol; the ``inner.top`` first are held at equal
weight 1/top and the weight the empty slots leave goes to SPY. Behind the trend switch (when
``inner.trend`` is set) the book is all cash while SPY is below its 200-day average.

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

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
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
BASE_DAYS = 400  # the window before an ex-date that sets the baseline / proves no prior payment
BASE_N = 4  # payments in the baseline median

Kind = Literal["raise", "flat"]
_KINDS: tuple[str, ...] = ("raise", "flat")


@dataclass(frozen=True, slots=True)
class RaiseParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines the event."""

    inner: FactorParams
    kind: Kind = "raise"
    raise_min: Decimal = Decimal("0.10")
    raise_max: Decimal = Decimal("1.00")
    flat_tol: Decimal = Decimal("0.01")
    hold_days: int = 182
    park: bool = True
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.kind, str) or self.kind not in _KINDS:
            raise ValueError(f"kind must be one of {_KINDS}, got {self.kind!r}")
        for name in ("raise_min", "raise_max", "flat_tol"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite() or v < 0:
                raise ValueError(f"{name} must be a finite Decimal >= 0, got {v!r}")
        if self.raise_max <= self.raise_min:
            raise ValueError("raise_max must be above raise_min")
        if isinstance(self.hold_days, bool) or not isinstance(self.hold_days, int) or self.hold_days < 20:
            raise ValueError(f"hold_days must be an int >= 20, got {self.hold_days!r}")
        if not isinstance(self.park, bool):
            raise TypeError(f"park must be a bool, got {type(self.park).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "kind": self.kind,
            "raise_min": str(self.raise_min),
            "raise_max": str(self.raise_max),
            "flat_tol": str(self.flat_tol),
            "hold_days": str(self.hold_days),
            "park": str(self.park).lower(),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> RaiseParams:
    if not isinstance(params, RaiseParams):
        raise TypeError(f"params must be RaiseParams, got {type(params).__name__}")
    return params


def classify(paid: tuple[tuple[date, Decimal], ...], first_bar: date | None,
             p: RaiseParams) -> str | None:
    """The kind of the latest payment in ``paid``: 'raise', 'init', 'flat' or None (anything else)."""
    if not paid:
        return None
    e, a = paid[-1]
    since = e - timedelta(days=BASE_DAYS)
    prior = [amt for d, amt in paid[:-1] if d > since][-BASE_N:]
    if not prior:
        if first_bar is not None and first_bar <= since:
            return "init"
        return None
    base = statistics.median(prior)
    ratio = a / base - 1
    if p.raise_min <= ratio <= p.raise_max:
        return "raise"
    if abs(ratio) <= p.flat_tol:
        return "flat"
    return None


def live_event(paid: tuple[tuple[date, Decimal], ...], first_bar: date | None, data_date: date,
               p: RaiseParams) -> date | None:
    """The ex-date of the latest payment when it is live and of the book's kind, else None."""
    if not paid:
        return None
    e = paid[-1][0]
    if (data_date - e).days >= p.hold_days:
        return None
    k = classify(paid, first_bar, p)
    wanted = ("raise", "init") if p.kind == "raise" else ("flat",)
    return e if k in wanted else None


@dataclass
class RaisePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    calendar: DividendCalendar = field(repr=False)


def _first_bar(h: History | None) -> date | None:
    if h is None or len(h) == 0:
        return None
    return h.dates[0].astype(object)


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: RaiseParams) -> tuple[Target, ...]:
    live: list[tuple[int, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        paid = calendar.known_on(r.symbol, data_date)
        e = live_event(paid, _first_bar(history.get(r.symbol)), data_date, p)
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


class DividendRaiseAllocator:
    """Members whose latest dividend was a raise or a first payment, held while it is young; rest SPY."""

    id = "M0070"
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
        p = _check(params)
        return (p.market,) if p.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: RaiseParams) -> tuple[Target, ...]:
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


RAISE = DividendRaiseAllocator()

T20 = replace(N20, rank="lowvol")  # F4's screen and SPY-200 switch; the rank field is unused here
NOT20 = replace(N20_NOTREND, rank="lowvol")

def _v(suffix: str, params: RaiseParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0070-{suffix}", family="M0070", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=RAISE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0070",
    name="Follow a dividend raise: buy big companies right after they raise or start their dividend, hold for months",
    family="stock-dividend-change-drift",
    source_kind="paper",
    source_ref=(
        "Michaely, Thaler & Womack (1995), Price Reactions to Dividend Initiations and Omissions, "
        "JF 50(2); https://www.nber.org/papers/w4778; Boehme & Sorescu (2002), JF 57(2)"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1994-1995 (NBER w4778, then the Journal of Finance), so most of the dev window "
        "(1996-2015) is after the crowd could know it; it survives only if the signal is slow "
        "enough that nobody arbitraged it. A dividend raise is a manager's costly signal of "
        "confidence, and Michaely, Thaler and Womack report the price keeps drifting up for months "
        "after an initiation (about +7.5% over 12 months). The store holds every member's cash "
        "dividends by ex-date, so the event is visible point in time on the ex-date. A member's "
        "latest payment is a raise when it is 10% or more above the median of its up-to-four "
        "previous payments in the prior 400 days (and no more than double, which drops one-off "
        "specials), or an initiation when nothing went ex in the 400 days before and the stock has "
        "price history from before that. Inside F4's liquidity and membership screen, hold up to "
        "20 such names at 5% each while the event is younger than the hold (held names keep their "
        "slot; then the newest ex-dates), park the rest in SPY, re-picked monthly, in fractional "
        "shares at Gotrade's real fees on monthly-hold-frac-gotrade. It ranks on a corporate "
        "decision, not past returns, so its picks should move apart from the failed momentum books. "
        "Variants: R10-H6-T (raise >= 10%, hold 182 days, behind the SPY-200 switch), R10-H12-T "
        "(hold 365 days), R25-H6-T (raise >= 25%), R10-H6 (no switch: the picking alone, always "
        "invested) and FLAT-H6-T (control: payers whose latest dividend was unchanged within 1%, "
        "same hold and switch), so R10-H6-T minus FLAT-H6-T isolates the raise from merely being a "
        "steady payer. Success: a raise variant beats total-return SPY on dev within the 20% worst "
        "fall, beats FLAT-H6-T, and keeps a positive edge over SPY in 2009-2015."
    ),
    expected_failure=(
        "The drift was reported mainly for equal-weighted small stocks, and Boehme and Sorescu "
        "(2002) found it largely disappears once measured carefully; among big index members it may "
        "be gone. The ex-date lags the announcement by two to six weeks, so part of any drift is "
        "already in the price before the book can see it. Many big payers raise every year by "
        "10% or more, so the raise set may be large and close to an equal-weight 'dividend "
        "grower' index: value-ish, lower-volatility names that trailed SPY's big-company growth "
        "in 1997-2000 and from 2009, so the book may lag SPY in exactly the 2009-2015 years that "
        "matter. Behind the SPY-200 switch the 1998 and 2011 fast falls still land before the "
        "switch turns, so the worst fall may sit near the 20% limit; the ungated R10-H6 should "
        "take most of SPY's 2008 fall (well over 20%). Not modelled and against the method: the "
        "book is credited 100% of every dividend while the owner loses 15-30% to US withholding "
        "tax, though at about SPY's yield this costs no more than holding SPY does. If FLAT-H6-T "
        "does as well as the raise books, the raise carries no information."
    ),
    candidates=(
        _v("R10-H6-T", RaiseParams(T20),
           "Raises of 10%+ or first payments, held 6 months, up to 20 at 5% each, rest SPY, behind the SPY-200 switch"),
        _v("R10-H12-T", RaiseParams(T20, hold_days=365),
           "Same, held 12 months: the paper's drift horizon"),
        _v("R25-H6-T", RaiseParams(T20, raise_min=Decimal("0.25")),
           "Only big raises (25%+) or first payments, held 6 months, behind the switch"),
        _v("R10-H6", RaiseParams(NOT20),
           "No switch: the raise picking alone on top of SPY, always invested"),
        _v("FLAT-H6-T", RaiseParams(T20, kind="flat"),
           "Control: payers whose latest dividend was unchanged (within 1%), same hold and switch"),
    ),
    seen_keys=(
        "concept:dividend-initiation-drift",
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "nber:w4778",
    ),
)
