"""One NYSE session of the order lifecycle (design §5, fill-simulator handover §3).

``step`` advances a portfolio through one session's split-adjusted bars. For every open
position, in slot order:

1. time stop: ``days_held >= TIME_STOP_DAYS`` and a bar → exit at the open, reason ``time``;
2. gap: ``open <= sl`` → exit at the open, reason ``gap``; ``open >= tp`` → exit at the
   open, reason ``tp``;
3. intraday: ``low <= sl`` → exit at sl, reason ``sl`` (checked first); else ``high > tp``
   → exit at tp, reason ``tp``;
4. otherwise it stays open, ``days_held`` + 1, marked at the close.

An open position with no bar has no event; ``days_held`` still + 1 and the mark stays at
its last known close. Then every pending order (all must be for this session):

5. fill when ``low < limit`` (strict) at ``min(open, limit)``, ``days_held`` = 1, marked
   at the close; a position filled today is not checked against TP/SL today;
6. otherwise (including no bar) it expires.

Events come out as all exits (by slot), then all fills (by slot), then all expiries
(by slot). The snapshot is ``cash + Σ shares × mark`` at the close.

Pure: no clock, no I/O, no randomness. The caller owns the calendar and the bars.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim.charges import bracket_rules, buy_cash, sell_cash
from seer_engine.sim.model import (
    TIME_STOP_DAYS,
    Event,
    ExitReason,
    Order,
    Portfolio,
    Snapshot,
    StepResult,
    q,
)
from seer_engine.sim.rules import DESIGN_V0, TradeRules


def _check_bar(symbol: str, bar: object, session_date: date) -> Bar:
    if not isinstance(bar, Bar):
        raise TypeError(f"bars[{symbol!r}] must be a Bar, got {type(bar).__name__}")
    if bar.symbol != symbol:
        raise ValueError(f"bars[{symbol!r}] holds a bar for {bar.symbol!r}")
    if bar.date != session_date:
        raise ValueError(f"bars[{symbol!r}] is dated {bar.date}, expected {session_date}")
    for field in ("open", "high", "low", "close"):
        value = getattr(bar, field)
        if not isinstance(value, Decimal):
            raise TypeError(f"{symbol} {field} must be a Decimal, got {type(value).__name__}")
        if not value.is_finite() or value <= 0:
            raise ValueError(f"{symbol} {field} must be a finite price > 0, got {value}")
    return bar


def _close(
    order: Order,
    when: date,
    price: Decimal,
    reason: ExitReason,
    days_held: int,
    rules: TradeRules,
) -> tuple[Order, Decimal]:
    """The closed order and the cash its sale brings in.

    ``pnl_usd = sell_cash - buy_cash`` under ``rules``, both priced the way the cash actually
    moved, so the sum of pnl reconciles with cash exactly under either cost model.
    """
    if order.fill_price is None:
        raise ValueError(f"{order.symbol} has no fill price")
    exit_price = q(price)
    proceeds = sell_cash(exit_price, order.shares, rules)
    pnl = proceeds - buy_cash(order.fill_price, order.shares, rules)
    closed = replace(
        order,
        status="closed",
        days_held=days_held,
        exit_date=when,
        exit_price=exit_price,
        exit_reason=reason,
        pnl_usd=pnl,
    )
    return closed, proceeds


def _exit_on_bar(order: Order, bar: Bar) -> tuple[Decimal, ExitReason, int] | None:
    """(exit price, reason, days_held) when the open position exits on ``bar``, else None."""
    if order.days_held >= TIME_STOP_DAYS:
        return bar.open, "time", order.days_held
    if bar.open <= order.sl_price:
        return bar.open, "gap", order.days_held
    if bar.open >= order.tp_price:
        return bar.open, "tp", order.days_held
    if bar.low <= order.sl_price:
        return order.sl_price, "sl", order.days_held + 1
    if bar.high > order.tp_price:
        return order.tp_price, "tp", order.days_held + 1
    return None


def _snapshot_equity(cash: Decimal, orders: Iterable[Order], marks: Mapping[str, Decimal]) -> Decimal:
    total = cash
    for o in orders:
        if o.status == "open":
            total += o.shares * marks[o.symbol]
    return q(total)


def _rebuild(
    cash: Decimal,
    equity: Decimal,
    live: list[Order],
    marks: Mapping[str, Decimal],
    last_session: date | None,
) -> Portfolio:
    orders = tuple(sorted(live, key=lambda o: o.slot))
    open_symbols = sorted(o.symbol for o in orders if o.status == "open")
    return Portfolio(
        cash=cash,
        equity=equity,
        orders=orders,
        marks=tuple((s, marks[s]) for s in open_symbols),
        last_session=last_session,
    )


def step(
    portfolio: Portfolio,
    session_date: date,
    bars: Mapping[str, Bar],
    *,
    rules: TradeRules = DESIGN_V0,
) -> StepResult:
    """Advance ``portfolio`` through the NYSE session ``session_date``.

    ``bars`` maps symbol → that session's split-adjusted ``Bar``; a symbol absent from it
    has no bar this session. Only bars for symbols with a live order are read (and
    validated); the rest are ignored.

    ``rules`` prices every fill and exit: ``DESIGN_V0`` (the default) charges the flat 0.1% a
    side the §5 records were closed at, ``DESIGN_V0_GOTRADE`` charges Gotrade's measured
    schedule including its $0.10 per-order minimum (``sim.charges``).

    Raises TypeError on a non-Decimal price or a wrong type, and ValueError when
    ``session_date`` is not an NYSE session, is not after ``portfolio.last_session``,
    differs from a pending order's ``session_date``, or ``rules`` are not a bracket rule set.
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    bracket_rules(rules)
    if isinstance(session_date, datetime) or not isinstance(session_date, date):
        raise TypeError(f"session_date must be a date, got {type(session_date).__name__}")
    if not isinstance(bars, Mapping):
        raise TypeError(f"bars must be a Mapping, got {type(bars).__name__}")
    if not dates.is_session(session_date):
        raise ValueError(f"{session_date} is not an NYSE session")
    if portfolio.last_session is not None and session_date <= portfolio.last_session:
        raise ValueError(f"{session_date} is not after the last session stepped ({portfolio.last_session})")
    for o in portfolio.pending_orders():
        if o.session_date != session_date:
            raise ValueError(
                f"pending order {o.symbol} (slot {o.slot}) is for {o.session_date}, not {session_date}"
            )
    day: dict[str, Bar] = {}
    for o in portfolio.orders:
        bar = bars.get(o.symbol)
        if bar is not None:
            day[o.symbol] = _check_bar(o.symbol, bar, session_date)

    cash = portfolio.cash
    marks: dict[str, Decimal] = dict(portfolio.marks)
    live: list[Order] = []
    exits: list[Event] = []
    fills: list[Event] = []
    expiries: list[Event] = []

    # (1)-(3) exits of open positions, at the open first, then intraday (SL before TP).
    for o in portfolio.open_orders():
        bar = day.get(o.symbol)
        if bar is None:
            live.append(replace(o, days_held=o.days_held + 1))
            continue
        hit = _exit_on_bar(o, bar)
        if hit is None:
            live.append(replace(o, days_held=o.days_held + 1))
            marks[o.symbol] = bar.close
            continue
        price, reason, days_held = hit
        closed, proceeds = _close(o, session_date, price, reason, days_held, rules)
        cash += proceeds
        del marks[o.symbol]
        exits.append(Event(session_date, "exit", closed, cash_usd=proceeds))

    # (4)-(5) fills of pending orders (strict low < limit), else expiry.
    for o in portfolio.pending_orders():
        bar = day.get(o.symbol)
        if bar is not None and bar.low < o.limit_price:
            fill_price = q(bar.open if bar.open < o.limit_price else o.limit_price)
            cost = buy_cash(fill_price, o.shares, rules)
            cash -= cost
            filled = replace(o, status="open", fill_date=session_date, fill_price=fill_price, days_held=1)
            marks[o.symbol] = bar.close
            live.append(filled)
            fills.append(Event(session_date, "fill", filled, cash_usd=-cost))
        else:
            expiries.append(Event(session_date, "expire", replace(o, status="expired")))

    # (6) mark to close.
    equity = _snapshot_equity(cash, live, marks)
    new = _rebuild(cash, equity, live, marks, session_date)
    return StepResult(
        portfolio=new,
        events=tuple(exits + fills + expiries),
        snapshot=Snapshot(date=session_date, cash_usd=cash, equity_usd=equity),
    )


def close_unpriced(
    portfolio: Portfolio,
    symbols: Iterable[str],
    *,
    rules: TradeRules = DESIGN_V0,
) -> tuple[Portfolio, tuple[Event, ...]]:
    """Force-close open positions that will never get another bar (delisted, halted for good).

    Each named position exits at its last known close (its mark), reason ``time``,
    ``exit_date = portfolio.last_session``, ``days_held`` unchanged, with ``forced=True``
    on its event. Cash takes the proceeds net of ``rules``' cost (the flat rate by default,
    Gotrade's measured schedule under ``cost_model="gotrade"``), and ``equity`` is
    recomputed as ``cash + Σ shares × mark`` for what is still open. Events are in slot
    order. Every symbol must belong to an open position; the caller decides that no
    further bar will come (a pure step cannot know it).
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    bracket_rules(rules)
    if isinstance(symbols, str):
        raise TypeError("symbols must be an iterable of symbols, not a single str")
    wanted: list[str] = []
    for s in symbols:
        if not isinstance(s, str):
            raise TypeError(f"symbol must be a str, got {type(s).__name__}")
        if s not in wanted:
            wanted.append(s)
    if not wanted:
        return portfolio, ()
    open_symbols = [o.symbol for o in portfolio.open_orders()]
    for s in wanted:
        if s not in open_symbols:
            raise ValueError(f"{s} is not an open position")
    when = portfolio.last_session
    if when is None:
        raise ValueError("cannot close a position before any session was stepped")

    cash = portfolio.cash
    marks: dict[str, Decimal] = dict(portfolio.marks)
    live: list[Order] = []
    events: list[Event] = []
    for o in portfolio.orders:
        if o.status != "open" or o.symbol not in wanted:
            live.append(o)
            continue
        closed, proceeds = _close(o, when, marks[o.symbol], "time", o.days_held, rules)
        cash += proceeds
        del marks[o.symbol]
        events.append(Event(when, "exit", closed, forced=True, cash_usd=proceeds))
    equity = _snapshot_equity(cash, live, marks)
    return _rebuild(cash, equity, live, marks, when), tuple(events)
