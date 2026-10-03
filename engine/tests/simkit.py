"""Builders for simulator tests: synthetic bars, orders and portfolios.

Shared by every tests/test_sim_*.py (phases 1-4). Strings in, exact Decimals out; a float
is refused so no binary rounding sneaks into a hand-checked number. Dates may be given as
ISO strings or ``date`` values.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from seer_engine.prices import Bar
from seer_engine.sim.model import Order, Portfolio, q

Num = str | int | Decimal
Day = str | date


def D(s: Day) -> date:
    """``date.fromisoformat(s)``; a ``date`` passes through."""
    return s if isinstance(s, date) else date.fromisoformat(s)


def P(x: Num) -> Decimal:
    """An exact Decimal quantized to 4 dp (half-up). Floats are refused."""
    if isinstance(x, (float, bool)):
        raise TypeError(f"use a str, int or Decimal, not {type(x).__name__}")
    return q(x if isinstance(x, Decimal) else Decimal(x))


def bar(symbol: str, d: Day, o: Num, h: Num, l: Num, c: Num, volume: int = 1_000_000) -> Bar:  # noqa: E741
    """A Bar for ``symbol`` on ``d`` with exact 4-dp prices."""
    return Bar(symbol, D(d), P(o), P(h), P(l), P(c), volume)


def day(*bars: Bar) -> dict[str, Bar]:
    """One session's bars keyed by symbol, as ``step`` takes them."""
    return {b.symbol: b for b in bars}


def pending(
    symbol: str,
    session_date: Day,
    limit: Num,
    tp: Num,
    sl: Num,
    shares: int,
    slot: int = 1,
    last: Num | None = None,
) -> Order:
    """A pending bracket for ``session_date``; ``last`` defaults to ``limit``."""
    return Order(
        session_date=D(session_date),
        slot=slot,
        symbol=symbol,
        last_price=P(limit if last is None else last),
        limit_price=P(limit),
        tp_price=P(tp),
        sl_price=P(sl),
        shares=shares,
    )


def opened(
    symbol: str,
    fill_date: Day,
    fill_price: Num,
    tp: Num,
    sl: Num,
    shares: int,
    days_held: int,
    slot: int = 1,
    limit: Num | None = None,
) -> Order:
    """An open position filled on ``fill_date`` (also its session_date) at ``fill_price``;
    ``limit`` (and last_price) default to ``fill_price``."""
    lim = P(fill_price if limit is None else limit)
    return Order(
        session_date=D(fill_date),
        slot=slot,
        symbol=symbol,
        last_price=lim,
        limit_price=lim,
        tp_price=P(tp),
        sl_price=P(sl),
        shares=shares,
        status="open",
        fill_date=D(fill_date),
        fill_price=P(fill_price),
        days_held=days_held,
    )


def portfolio(
    cash: Num,
    *orders: Order,
    marks: Mapping[str, Num] | None = None,
    last_session: Day | None = None,
    equity: Num | None = None,
) -> Portfolio:
    """A Portfolio holding ``orders`` (sorted by slot for you).

    ``marks`` defaults to each open order's fill price. ``equity`` defaults to
    ``cash + Σ shares × mark`` over the open orders.
    """
    live = tuple(sorted(orders, key=lambda o: o.slot))
    if marks is None:
        mark_map = {o.symbol: o.fill_price for o in live if o.status == "open"}
    else:
        mark_map = {s: P(v) for s, v in marks.items()}
    cash_d = P(cash)
    if equity is None:
        eq = q(cash_d + sum((o.shares * mark_map[o.symbol] for o in live if o.status == "open"), Decimal(0)))
    else:
        eq = P(equity)
    return Portfolio(
        cash=cash_d,
        equity=eq,
        orders=live,
        marks=tuple(sorted(mark_map.items())),
        last_session=None if last_session is None else D(last_session),
    )
