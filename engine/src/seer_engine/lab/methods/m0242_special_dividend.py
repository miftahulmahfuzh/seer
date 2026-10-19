"""M0242 — One-off cash: buy the companies that declare a special dividend.

Source: Brickley (1983), "Shareholder wealth, information signaling and the specially designated
dividend: an empirical study", Journal of Financial Economics 12(2), 187-209.
Idea: a special dividend is a one-off return of cash, several times the company's regular
payment. Brickley's point is that the *label* matters: a board that calls a payment "special"
tells the market not to expect it again, and yet he found the announcement carried good news
about the year ahead. M0070 built the opposite book -- it caps a raise at double the baseline
precisely to *throw specials away* as noise. This method picks up what M0070 discards and asks
whether the discarded pile is worth anything.

The store has no dividend *type* column, so "special" is inferred from the payment's own shape:
a payment at least ``special_min`` times the median of the up-to-four payments that went ex in
the 400 days before it, from a company with an established cadence (at least two of those prior
payments). That is the same baseline machinery M0070 uses, read above its raise cap instead of
below it. Measured on the dev store, the >= 2x rule fires 519 times in 1996-2015 (8-59 a year,
peaking in 2011-2012) and 69% of them carry a board declaration date.

The event is dated the day the market learned of it: the declaration date when the store has
one (``Market.dividends.announced_on``), else the ex-date. The allocator therefore declares
``market_fields = ("dividends", "announcements")``, so ``lab run`` refuses it on a store with no
declaration dates rather than silently measuring the ex-date twin.

The frame is M0070's and F4's: point-in-time S&P 500 / Nasdaq-100 members, the $5 price and
$20M daily dollar-volume screen, the SPY 200-day trend switch, monthly, fractional shares at
Gotrade's real fees. Ten slots rather than M0070's twenty, because specials are rare: at >= 2x
and a six-month hold the median month has nine live events, so ten slots keep the book close to
fully invested in its own picks instead of mostly in the SPY park. The slot weight the empty
slots leave goes to SPY, so an arm with fewer live events is automatically more SPY -- which is
honest, and which the analysis must read before comparing arms.

Three event modes share one allocator so the controls are the same book with a different
trigger:

    * ``"special"`` -- ratio >= ``special_min`` (and <= ``special_max`` when it is set);
    * ``"raise"`` -- ratio in [1 + ``raise_min``, ``special_min``): the ordinary increase
      control, the band M0070 actually trades;
    * ``"flat"`` -- |ratio - 1| <= ``flat_tol``: the same kind of mature payer in a quarter
      when it announced nothing at all.

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
from seer_engine.lab.methods.m0070_dividend_raise_drift import BASE_DAYS, BASE_N, T20, _first_bar
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

ADDED = date(2026, 10, 19)
MIN_PRIOR = 2  # payments the baseline needs before a cadence counts as established

Mode = Literal["special", "raise", "flat"]
_MODES: tuple[str, ...] = ("special", "raise", "flat")


@dataclass(frozen=True, slots=True)
class SpecialParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines the event."""

    inner: FactorParams
    mode: Mode = "special"
    special_min: Decimal = Decimal("2.0")
    special_max: Decimal | None = None
    raise_min: Decimal = Decimal("0.25")
    flat_tol: Decimal = Decimal("0.10")
    hold_days: int = 182
    park: bool = True
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.mode, str) or self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        for name in ("special_min", "raise_min", "flat_tol"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite() or v < 0:
                raise ValueError(f"{name} must be a finite Decimal >= 0, got {v!r}")
        if self.special_min <= 1:
            raise ValueError(f"special_min must be above 1, got {self.special_min!r}")
        if self.special_max is not None:
            if not isinstance(self.special_max, Decimal) or not self.special_max.is_finite():
                raise ValueError(f"special_max must be a finite Decimal, got {self.special_max!r}")
            if self.special_max <= self.special_min:
                raise ValueError("special_max must be above special_min")
        if Decimal(1) + self.raise_min >= self.special_min:
            raise ValueError("the raise band must end below special_min, or the modes overlap")
        if isinstance(self.hold_days, bool) or not isinstance(self.hold_days, int) or self.hold_days < 20:
            raise ValueError(f"hold_days must be an int >= 20, got {self.hold_days!r}")
        if not isinstance(self.park, bool):
            raise TypeError(f"park must be a bool, got {type(self.park).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "mode": self.mode,
            "special_min": str(self.special_min),
            "special_max": "none" if self.special_max is None else str(self.special_max),
            "raise_min": str(self.raise_min),
            "flat_tol": str(self.flat_tol),
            "hold_days": str(self.hold_days),
            "park": str(self.park).lower(),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SpecialParams:
    if not isinstance(params, SpecialParams):
        raise TypeError(f"params must be SpecialParams, got {type(params).__name__}")
    return params


def ratio_of(paid: tuple[tuple[date, Decimal], ...]) -> Decimal | None:
    """The latest payment as a multiple of the median of its up-to-four priors in 400 days.

    ``None`` when there is no payment, or fewer than ``MIN_PRIOR`` priors inside the window: a
    company with no settled cadence has no "regular payment" for a special to be special against,
    and the first payment after a long gap would otherwise read as an enormous one-off.
    """
    if not paid:
        return None
    e, a = paid[-1]
    since = e - timedelta(days=BASE_DAYS)
    prior = [amt for d, amt in paid[:-1] if d > since][-BASE_N:]
    if len(prior) < MIN_PRIOR:
        return None
    base = statistics.median(prior)
    if base <= 0:
        return None
    return Decimal(a) / Decimal(base)


def wanted(ratio: Decimal, p: SpecialParams) -> bool:
    """Whether a payment of this relative size is the event the arm trades."""
    if p.mode == "special":
        if ratio < p.special_min:
            return False
        return p.special_max is None or ratio <= p.special_max
    if p.mode == "raise":
        return Decimal(1) + p.raise_min <= ratio < p.special_min
    return abs(ratio - Decimal(1)) <= p.flat_tol


def live_event(calendar: DividendCalendar, symbol: str, data_date: date,
               p: SpecialParams) -> date | None:
    """The day the market learned of ``symbol``'s latest payment, when it is live and wanted.

    The payments are read through ``announced_on``, which orders them by the day they became
    known -- the board's declaration date where the store has one, else the ex-date. "Latest"
    therefore means latest *known*, and the hold clock runs from that day, so the book holds the
    same length of time from the day it could have acted.
    """
    ann = calendar.announced_on(symbol, data_date)
    if not ann:
        return None
    newest = ann[-1]
    if (data_date - newest.known).days >= p.hold_days:
        return None
    ratio = ratio_of(tuple((a.ex_date, a.amount) for a in sorted(ann, key=lambda x: x.ex_date)))
    if ratio is None or not wanted(ratio, p):
        return None
    return newest.known


@dataclass
class SpecialPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    calendar: DividendCalendar = field(repr=False)


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: SpecialParams) -> tuple[Target, ...]:
    live: list[tuple[int, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        e = live_event(calendar, r.symbol, data_date, p)
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


class SpecialDividendAllocator:
    """Members whose latest declared dividend was a one-off several times its usual size."""

    id = "M0242"
    market_fields = ("dividends", "announcements")

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

    def _run(self, prepared: SpecialPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SpecialParams) -> tuple[Target, ...]:
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
        return self._run(SpecialPrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> SpecialPrepared:
        return SpecialPrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> SpecialPrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return SpecialPrepared(market.history, prepare_factor(market.history), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SpecialPrepared):
            raise TypeError(f"prepared must be SpecialPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SPECIAL = SpecialDividendAllocator()

T10 = replace(T20, top=10)  # F4's screen and SPY-200 switch, ten slots: specials are rare


def _v(suffix: str, params: SpecialParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0242-{suffix}", family="M0242", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SPECIAL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0242",
    name="One-off cash: buy the companies that declare a special dividend, and see whether the market keeps rewarding them",
    family="stock-special-dividend",
    source_kind="paper",
    source_ref=(
        "Brickley (1983), Shareholder wealth, information signaling and the specially designated "
        "dividend: an empirical study, Journal of Financial Economics 12(2), 187-209; "
        "declaration dates from the store's dividend_announcements.csv (rebuilt 2026-10-19)"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1983, so the whole dev window (1996-2015) is after the crowd could know it; "
        "that is a reason to expect a faded edge, not a reason to skip the measurement, because "
        "the lab has no evidence on this event at all. A special dividend is a one-off return of "
        "cash, several times the company's regular payment. Brickley's finding is that boards pay "
        "one when they have cash the business does not need, and that the announcement still "
        "carried good news about the year ahead even though the label says 'do not expect this "
        "again'. M0070 built the mirror image of this book: it caps a raise at double the "
        "baseline precisely to throw specials out as noise, so this method trades exactly the "
        "pile M0070 discards, and the two together cover the whole distribution of dividend "
        "surprises. The store has no dividend type column, so a special is inferred from shape: a "
        "payment at least twice the median of the up-to-four payments that went ex in the 400 "
        "days before it, from a company with at least two such priors (an established cadence). "
        "Measured on the dev store that rule fires 519 times in 1996-2015, 8-59 a year, and 69% "
        "carry a board declaration date. Each event is dated the day the market learned of it -- "
        "the declaration date where the store has one, else the ex-date -- and held while it is "
        "younger than the hold. Inside F4's membership and liquidity screen and behind the "
        "SPY-200 switch, hold up to ten such names at 10% each (held names keep their slot, then "
        "the newest event), park the empty slots in SPY, re-picked monthly, fractional shares at "
        "Gotrade's real fees. Ten slots rather than M0070's twenty because specials are rare: at "
        "twice the baseline and a six-month hold the median month has nine live events, so ten "
        "slots keep the book in its own picks rather than in the park. Variants: S-H6 (the main "
        "arm), S-H12 (a twelve-month hold, which both lengthens the drift window and fills more "
        "slots), S-K5 (only payments five times the baseline or more -- purer specials, but only "
        "about three live a month, so that arm is mostly SPY by construction and its exposure "
        "must be read before its return), S-CAP (specials between two and twenty times, which "
        "drops the handful of enormous distributions that are really spin-offs and REIT "
        "conversions rather than a board handing back spare cash), and two controls on the same "
        "book and the same clock: R-H6, ordinary increases of 25% up to double (the band M0070 "
        "actually trades), and F-H6, the same mature payers in a quarter when the dividend did "
        "not change by more than 10%. Success: S-H6 beats total-return SPY on dev inside the 20% "
        "worst fall, beats both controls, and keeps a positive edge over SPY in 2009-2015."
    ),
    expected_failure=(
        "Three ways this most likely dies. First, selection: special dividends cluster in good "
        "times and among mature, cash-rich, value-shaped companies, so the book may be a quality "
        "and value tilt wearing an event costume -- exactly the shape that lagged SPY's "
        "big-company growth in 2009-2015, which is the era that matters most and the one that has "
        "killed every roster strategy so far. Second, timing: the announcement pop is one day, "
        "and a monthly book reading the close buys at the next open at best, so if the whole "
        "effect is the pop there is nothing left; M0076 measured exactly this for dividend raises "
        "and found the declaration-day arm no better than the ex-date arm. Third, the sample: 519 "
        "events over twenty years is thin, it is lumpy (59 in 2011 and 55 in 2012 against 7 in "
        "2002), and the 2012 cluster is a known tax event -- boards pulled specials forward "
        "before the expected 2013 dividend-tax rise -- so a large part of the dev sample is "
        "companies answering the tax code, not signalling confidence. A book that is mostly 2011-"
        "2012 is a book that measured one tax deadline. Also against it: the inferred label is "
        "not the board's label, so stock distributions, spin-off cash and REIT conversion "
        "payments are counted as specials even though they carry no confidence signal (S-CAP "
        "exists to size that); the SPY park means a thin arm is partly measuring SPY, so S-K5 may "
        "look fine for the wrong reason; the fast 1998, 2008 and 2011 falls land before the "
        "200-day switch turns, so the worst fall may sit near or above the 20% limit as M0070's "
        "did at 21-22%; and US withholding tax on dividends is not modelled, which bites harder "
        "here than anywhere else in the lab because the whole thesis is large cash payments."
    ),
    candidates=(
        _v("S-H6", SpecialParams(T10),
           "Specials of twice the usual payment or more, held 6 months from the declaration day, ten at 10%, rest SPY"),
        _v("S-H12", SpecialParams(T10, hold_days=365),
           "The same specials held twelve months: a longer drift window, and more slots filled"),
        _v("S-K5", SpecialParams(T10, special_min=Decimal("5.0")),
           "Only payments five times the usual or more: purer one-offs, but a thin and SPY-heavy book"),
        _v("S-CAP", SpecialParams(T10, special_max=Decimal("20.0")),
           "Specials between two and twenty times: drops spin-off and REIT-conversion distributions"),
        _v("R-H6", SpecialParams(T10, mode="raise"),
           "Control: ordinary increases of 25% up to double, the band M0070 trades, same book and clock"),
        _v("F-H6", SpecialParams(T10, mode="flat"),
           "Control: the same mature payers in a quarter when the dividend did not change by more than 10%"),
    ),
    seen_keys=(
        "concept:special-dividend",
        "concept:specially-designated-dividend",
        "concept:one-off-cash-distribution",
        "jfe:brickley-1983-sdd",
    ),
)
