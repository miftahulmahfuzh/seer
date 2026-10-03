"""Whole-share sizing of ranked picks into free slots (design §5, handover §3 sizing row).

Each night, after session S's close, a strategy hands over its ranked picks for the next session.
``size_picks`` turns them into pending bracket orders:

* slot budget = equity ÷ 4, using the equity at the last snapshot (S's close), so it is recomputed
  every session;
* budget = min(slot budget, cash − buy cost of every pending order already placed for that
  session), so a position that has risen in value cannot lend new picks cash that does not exist;
* shares = floor(budget / (limit × 1.001)), so the buy cost including the 0.1 % charge fits;
* fewer than 1 share → rejected ``lt_one_share``; a symbol already live (open or pending) or
  repeated in the picks → rejected ``held`` (no adding to a holding); no free slot → ``no_slot``.

Picks are handled in the given order (the strategy's rank), and each placed pick takes the lowest
free slot. Pure and deterministic: no I/O, no clock, no randomness, Decimal only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

from seer_engine.dates import is_session
from seer_engine.sim.model import COST_RATE, SLOTS, Order, Portfolio, buy_cost, q

RejectReason = Literal["no_slot", "held", "lt_one_share"]

_ONE_PLUS_COST = Decimal(1) + COST_RATE


def _price(name: str, value: object) -> Decimal:
    """``value`` as a positive 4-dp Decimal; anything that is not a Decimal is a TypeError."""
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite, got {value!r}")
    v = q(value)
    if v <= 0:
        raise ValueError(f"{name} must be > 0, got {value!r}")
    return v


@dataclass(frozen=True, slots=True)
class Pick:
    """One ranked pick for the next session: the bracket a strategy proposes, before sizing."""

    symbol: str
    last_price: Decimal
    limit_price: Decimal
    tp_price: Decimal
    sl_price: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str):
            raise TypeError(f"symbol must be a str, got {type(self.symbol).__name__}")
        if not self.symbol:
            raise ValueError("symbol must be non-empty")
        for name in ("last_price", "limit_price", "tp_price", "sl_price"):
            object.__setattr__(self, name, _price(name, getattr(self, name)))
        if not self.sl_price < self.limit_price < self.tp_price:
            raise ValueError(
                f"{self.symbol}: need sl < limit < tp, got "
                f"sl={self.sl_price} limit={self.limit_price} tp={self.tp_price}"
            )


@dataclass(frozen=True, slots=True)
class Rejection:
    symbol: str
    reason: RejectReason


@dataclass(frozen=True, slots=True)
class SizingResult:
    portfolio: Portfolio
    placed: tuple[Order, ...]
    rejected: tuple[Rejection, ...]


def _check_session_date(portfolio: Portfolio, session_date: object) -> None:
    if not isinstance(session_date, date) or isinstance(session_date, datetime):
        raise TypeError(f"session_date must be a date, got {type(session_date).__name__}")
    if not is_session(session_date):
        raise ValueError(f"{session_date} is not an NYSE session")
    if portfolio.last_session is not None and session_date <= portfolio.last_session:
        raise ValueError(
            f"session_date {session_date} must be after the last stepped session "
            f"{portfolio.last_session}"
        )


def _whole_shares(budget: Decimal, limit_price: Decimal) -> int:
    """floor(budget / (limit × 1.001)), never letting limit × shares × 1.001 exceed ``budget``."""
    if budget <= 0:
        return 0
    unit = limit_price * _ONE_PLUS_COST
    shares = int((budget / unit).to_integral_value(rounding=ROUND_FLOOR))
    # Decimal division rounds to 28 significant digits; a quotient a hair under an integer could
    # round up to it. Step back so the exact cost always fits.
    while shares > 0 and unit * shares > budget:
        shares -= 1
    return max(shares, 0)


def size_picks(portfolio: Portfolio, picks: Sequence[Pick], session_date: date) -> SizingResult:
    """Size ``picks`` (in rank order) into ``portfolio``'s free slots for ``session_date``.

    ``session_date`` is the session the brackets are placed for (the next session after the
    portfolio's last stepped one). Returns the portfolio with the new pending orders added, the
    orders placed (in pick order), and the picks rejected (in pick order). Cash is not touched:
    a pending order reserves cash only through the sizing cap, and pays at fill.
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    _check_session_date(portfolio, session_date)
    picks = tuple(picks)
    for p in picks:
        if not isinstance(p, Pick):
            raise TypeError(f"picks must be Pick values, got {type(p).__name__}")
    pending = portfolio.pending_orders()
    for o in pending:
        if o.session_date != session_date:
            raise ValueError(
                f"pending order {o.symbol} is for {o.session_date}, not {session_date}; "
                f"step that session before sizing"
            )
    if not picks:
        return SizingResult(portfolio=portfolio, placed=(), rejected=())

    free = list(portfolio.free_slots())
    taken = set(portfolio.held_symbols())  # every live order, pending included (no adding)
    seen: set[str] = set()
    committed = sum((buy_cost(o.limit_price, o.shares) for o in pending), Decimal(0))
    slot_budget = q(portfolio.equity / SLOTS)

    placed: list[Order] = []
    rejected: list[Rejection] = []
    for pick in picks:
        duplicate = pick.symbol in seen
        seen.add(pick.symbol)
        if duplicate or pick.symbol in taken:
            rejected.append(Rejection(symbol=pick.symbol, reason="held"))
            continue
        if not free:
            rejected.append(Rejection(symbol=pick.symbol, reason="no_slot"))
            continue
        budget = min(slot_budget, portfolio.cash - committed)
        shares = _whole_shares(budget, pick.limit_price)
        if shares < 1:
            rejected.append(Rejection(symbol=pick.symbol, reason="lt_one_share"))
            continue
        order = Order(
            session_date=session_date,
            slot=free.pop(0),
            symbol=pick.symbol,
            last_price=pick.last_price,
            limit_price=pick.limit_price,
            tp_price=pick.tp_price,
            sl_price=pick.sl_price,
            shares=shares,
        )
        placed.append(order)
        committed += buy_cost(order.limit_price, order.shares)

    if not placed:
        return SizingResult(portfolio=portfolio, placed=(), rejected=tuple(rejected))
    orders = tuple(sorted(portfolio.orders + tuple(placed), key=lambda o: o.slot))
    return SizingResult(
        portfolio=replace(portfolio, orders=orders),
        placed=tuple(placed),
        rejected=tuple(rejected),
    )
