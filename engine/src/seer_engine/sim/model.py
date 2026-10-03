"""Simulator value types and money arithmetic (design §5, fill-simulator handover §3).

Everything here is an immutable value. Money and prices are ``Decimal`` quantized to 4
decimals half-up (``PRICE_QUANTUM``, matching ``numeric(12,4)`` / ``numeric(14,4)``);
shares are ``int``. A ``float`` never enters: every constructor and helper raises
``TypeError`` on a non-Decimal price or amount.

``Order`` mirrors the ``orders`` table columns (minus strategy_id, company, explanation,
id and created_at) so P4 can persist it without translation. A ``Portfolio`` holds only
LIVE orders (pending and open); a terminal order (closed, expired) leaves the portfolio
and appears exactly once, inside the ``Event`` that ended it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from seer_engine.prices import PRICE_QUANTUM

SLOTS = 4
TIME_STOP_DAYS = 5
COST_RATE = Decimal("0.001")

OrderStatus = Literal["pending", "open", "closed", "expired"]
ExitReason = Literal["tp", "sl", "time", "gap"]
EventKind = Literal["fill", "expire", "exit", "split"]

_STATUSES: tuple[str, ...] = ("pending", "open", "closed", "expired")
_LIVE: tuple[str, ...] = ("pending", "open")
_EXIT_REASONS: tuple[str, ...] = ("tp", "sl", "time", "gap")
_EVENT_KINDS: tuple[str, ...] = ("fill", "expire", "exit", "split")


# --------------------------------------------------------------------------- validation


def _decimal(name: str, x: object) -> Decimal:
    """``x`` if it is a finite Decimal; TypeError for any other type (float included)."""
    if not isinstance(x, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(x).__name__}")
    if not x.is_finite():
        raise ValueError(f"{name} must be finite, got {x!r}")
    return x


def _positive(name: str, x: object) -> Decimal:
    d = _decimal(name, x)
    if d <= 0:
        raise ValueError(f"{name} must be > 0, got {d}")
    return d


def _int(name: str, x: object) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{name} must be an int, got {type(x).__name__}")
    return x


def _date(name: str, x: object) -> date:
    if isinstance(x, datetime) or not isinstance(x, date):
        raise TypeError(f"{name} must be a date, got {type(x).__name__}")
    return x


# --------------------------------------------------------------------------- money


def q(x: Decimal) -> Decimal:
    """``x`` quantized to 4 decimals, ROUND_HALF_UP (the schema's numeric rounding)."""
    return _decimal("value", x).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)


def buy_cost(price: Decimal, shares: int) -> Decimal:
    """Cash paid to buy ``shares`` at ``price``, including the 0.1% cost: q(p × n × 1.001)."""
    _positive("price", price)
    if _int("shares", shares) < 0:
        raise ValueError(f"shares must be >= 0, got {shares}")
    return q(price * shares * (1 + COST_RATE))


def sell_proceeds(price: Decimal, shares: int) -> Decimal:
    """Cash received selling ``shares`` at ``price``, net of the 0.1% cost: q(p × n × 0.999)."""
    _positive("price", price)
    if _int("shares", shares) < 0:
        raise ValueError(f"shares must be >= 0, got {shares}")
    return q(price * shares * (1 - COST_RATE))


def initial_cash_usd(idr: Decimal, usd_idr: Decimal) -> Decimal:
    """Starting capital in USD: q(idr / usd_idr), with ``usd_idr`` the IDR price of 1 USD."""
    return q(_positive("idr", idr) / _positive("usd_idr", usd_idr))


# --------------------------------------------------------------------------- orders


@dataclass(frozen=True, slots=True)
class Order:
    """One bracket order, shaped like an ``orders`` row.

    ``days_held`` counts sessions the position has been open: the fill session is day 1,
    every later session adds 1 (with or without a bar). An exit at the open of a session
    records the count before that session; an intraday exit includes it.
    """

    session_date: date
    slot: int
    symbol: str
    last_price: Decimal
    limit_price: Decimal
    tp_price: Decimal
    sl_price: Decimal
    shares: int
    status: OrderStatus = "pending"
    fill_date: date | None = None
    fill_price: Decimal | None = None
    days_held: int = 0
    exit_date: date | None = None
    exit_price: Decimal | None = None
    exit_reason: ExitReason | None = None
    pnl_usd: Decimal | None = None

    def __post_init__(self) -> None:
        _date("session_date", self.session_date)
        if not (1 <= _int("slot", self.slot) <= SLOTS):
            raise ValueError(f"slot must be 1..{SLOTS}, got {self.slot}")
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(f"symbol must be a non-empty str, got {self.symbol!r}")
        _positive("last_price", self.last_price)
        _positive("limit_price", self.limit_price)
        _positive("tp_price", self.tp_price)
        _positive("sl_price", self.sl_price)
        if self.sl_price >= self.tp_price:
            raise ValueError(f"sl_price {self.sl_price} must be below tp_price {self.tp_price}")
        if _int("shares", self.shares) < 1:
            raise ValueError(f"shares must be >= 1, got {self.shares}")
        if self.status not in _STATUSES:
            raise ValueError(f"unknown status {self.status!r}")
        if _int("days_held", self.days_held) < 0:
            raise ValueError(f"days_held must be >= 0, got {self.days_held}")
        filled = self.status in ("open", "closed")
        if filled:
            if self.fill_date is None or self.fill_price is None:
                raise ValueError(f"a {self.status} order needs fill_date and fill_price")
            _date("fill_date", self.fill_date)
            _positive("fill_price", self.fill_price)
            if self.days_held < 1:
                raise ValueError(f"a {self.status} order has days_held >= 1")
        elif self.fill_date is not None or self.fill_price is not None or self.days_held != 0:
            raise ValueError(f"a {self.status} order has no fill and days_held 0")
        if self.status == "closed":
            if self.exit_date is None or self.exit_price is None or self.pnl_usd is None:
                raise ValueError("a closed order needs exit_date, exit_price and pnl_usd")
            _date("exit_date", self.exit_date)
            _positive("exit_price", self.exit_price)
            if self.exit_reason not in _EXIT_REASONS:
                raise ValueError(f"unknown exit_reason {self.exit_reason!r}")
            _decimal("pnl_usd", self.pnl_usd)
        elif (
            self.exit_date is not None
            or self.exit_price is not None
            or self.exit_reason is not None
            or self.pnl_usd is not None
        ):
            raise ValueError(f"a {self.status} order has no exit fields")


# --------------------------------------------------------------------------- portfolio


@dataclass(frozen=True, slots=True)
class Portfolio:
    """One strategy's state between sessions.

    - ``cash``: real cash, 4 dp. Pending orders reserve nothing here.
    - ``equity``: equity at the last snapshot (initial cash before the first session).
    - ``orders``: LIVE orders only (pending + open), sorted by slot, at most one per slot,
      at most one per symbol.
    - ``marks``: last known close for every OPEN order's symbol, sorted by symbol.
    - ``last_session``: the last session stepped, or None before the first.
    """

    cash: Decimal
    equity: Decimal
    orders: tuple[Order, ...] = ()
    marks: tuple[tuple[str, Decimal], ...] = ()
    last_session: date | None = None

    def __post_init__(self) -> None:
        _decimal("cash", self.cash)
        _decimal("equity", self.equity)
        if not isinstance(self.orders, tuple):
            raise TypeError("orders must be a tuple")
        if not isinstance(self.marks, tuple):
            raise TypeError("marks must be a tuple")
        if self.last_session is not None:
            _date("last_session", self.last_session)
        if len(self.orders) > SLOTS:
            raise ValueError(f"at most {SLOTS} live orders, got {len(self.orders)}")
        prev_slot = 0
        symbols: list[str] = []
        for o in self.orders:
            if not isinstance(o, Order):
                raise TypeError(f"orders must hold Order values, got {type(o).__name__}")
            if o.status not in _LIVE:
                raise ValueError(f"portfolio holds live orders only, got {o.status!r} ({o.symbol})")
            if o.slot <= prev_slot:
                raise ValueError("orders must be sorted by slot with one order per slot")
            prev_slot = o.slot
            if o.symbol in symbols:
                raise ValueError(f"symbol {o.symbol} appears in two live orders")
            symbols.append(o.symbol)
        prev_symbol = ""
        for item in self.marks:
            if not (isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)):
                raise TypeError("marks must be (symbol, Decimal) pairs")
            if item[0] <= prev_symbol:
                raise ValueError("marks must be sorted by symbol, one per symbol")
            prev_symbol = item[0]
            _positive(f"mark {item[0]}", item[1])
        open_symbols = sorted(o.symbol for o in self.orders if o.status == "open")
        if [s for s, _ in self.marks] != open_symbols:
            raise ValueError(
                f"marks must cover exactly the open symbols {open_symbols}, "
                f"got {[s for s, _ in self.marks]}"
            )

    def open_orders(self) -> tuple[Order, ...]:
        """Open positions, by slot."""
        return tuple(o for o in self.orders if o.status == "open")

    def pending_orders(self) -> tuple[Order, ...]:
        """Pending orders, by slot."""
        return tuple(o for o in self.orders if o.status == "pending")

    def free_slots(self) -> tuple[int, ...]:
        """Slots with no live order, ascending."""
        used = [o.slot for o in self.orders]
        return tuple(s for s in range(1, SLOTS + 1) if s not in used)

    def held_symbols(self) -> tuple[str, ...]:
        """Symbols of every LIVE order (open and pending), sorted. "No adding" means a
        symbol here cannot take a new order."""
        return tuple(sorted(o.symbol for o in self.orders))

    def mark(self, symbol: str) -> Decimal | None:
        """Last known close for an open symbol, or None."""
        for s, price in self.marks:
            if s == symbol:
                return price
        return None


def new_portfolio(cash_usd: Decimal) -> Portfolio:
    """An empty portfolio with ``cash = equity = q(cash_usd)``."""
    cash = q(_positive("cash_usd", cash_usd))
    return Portfolio(cash=cash, equity=cash)


# --------------------------------------------------------------------------- results


@dataclass(frozen=True, slots=True)
class Event:
    """Something that happened to one order.

    ``order`` is the order's state AFTER the event (a terminal order lives only here).
    ``cash_usd`` is the cash it moved: ``-buy_cost`` on a fill, ``+sell_proceeds`` on an
    exit, ``+cash in lieu`` on a split, None when no cash moved. ``forced`` marks an exit
    at the last known close made without a bar: ``close_unpriced``, or a split that floors
    an open position to 0 shares (``split_adjust.apply_split``).
    """

    session_date: date
    kind: EventKind
    order: Order
    forced: bool = False
    cash_usd: Decimal | None = None

    def __post_init__(self) -> None:
        _date("session_date", self.session_date)
        if self.kind not in _EVENT_KINDS:
            raise ValueError(f"unknown event kind {self.kind!r}")
        if not isinstance(self.order, Order):
            raise TypeError("order must be an Order")
        if not isinstance(self.forced, bool):
            raise TypeError("forced must be a bool")
        if self.cash_usd is not None:
            _decimal("cash_usd", self.cash_usd)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One ``equity_snapshots`` row: cash and equity at a session's close."""

    date: date
    cash_usd: Decimal
    equity_usd: Decimal


@dataclass(frozen=True, slots=True)
class StepResult:
    portfolio: Portfolio
    events: tuple[Event, ...]
    snapshot: Snapshot
