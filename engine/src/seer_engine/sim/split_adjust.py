"""Split recompute for live orders (design §8; handover §4 and §7).

When a split executes on session S, the nightly job rescales stored bars backwards by
``factor = split_to / split_from`` (the same number as ``seer_engine.splits.Split.factor``: 10 for
a 10-for-1, 1/32 for a 1-for-32 reverse split). A live order's prices and share count were set in
pre-split units, so ``apply_split`` rewrites them in post-split units. Call it after session S-1's
``step`` and before stepping S, with ``session_date = S``.

Rules (plan Decisions, "Reverse-split rounding" and "Split factor convention"):

- Every price of a live order for the symbol (last, limit, TP, SL, fill) becomes ``q(p / factor)``.
- Shares become ``floor(shares * factor)``.
- An open position's fractional remainder is paid as cash in lieu, ``q(fraction * adjusted mark)``,
  with no cost and outside ``pnl_usd``. The amount is on the ``split`` event's ``cash_usd``.
- An open position whose shares floor to 0 is paid out entirely in lieu. It closes with a forced
  ``exit`` event in pre-split units (reason ``time``, exit at the last mark, ``pnl_usd`` = cash in
  lieu - buy cost), so the sum of ``pnl_usd`` still reconciles with cash for that trade.
- A pending order whose shares floor to 0 expires (``expire`` event, the order as it was).
- The symbol's mark is rescaled. Other symbols, ``equity`` and ``last_session`` are untouched.

The ratio is handled as an exact fraction. ``Split.factor`` for a 1-for-3 is the 28-digit Decimal
0.3333…, and 300 x that is 99.999…, which floors to 99 instead of 100. The factor is therefore
read as the nearest fraction with a denominator of at most ``_MAX_SPLIT_DENOMINATOR``; a factor that
is not within ``_RATIO_TOLERANCE`` (relative) of such a fraction is rejected.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction

from seer_engine import dates
from seer_engine.prices import PRICE_QUANTUM
from seer_engine.sim.model import Event, Order, Portfolio, buy_cost

_MAX_SPLIT_DENOMINATOR = 1_000_000
_RATIO_TOLERANCE = Fraction(1, 10**20)
_QUANTA_PER_UNIT = Fraction(1) / Fraction(PRICE_QUANTUM)  # 10_000


def _q_exact(x: Fraction) -> Decimal:
    """``x`` (>= 0) rounded half-up to PRICE_QUANTUM, computed without intermediate rounding."""
    if x < 0:
        raise ValueError(f"negative amount: {x}")
    scaled = x * _QUANTA_PER_UNIT
    quanta = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    return Decimal(quanta) * PRICE_QUANTUM


def _split_ratio(factor: Decimal) -> Fraction:
    """The exact split ratio behind ``factor``. Raises TypeError/ValueError on a bad factor."""
    if not isinstance(factor, Decimal):
        raise TypeError(f"factor must be a Decimal, got {type(factor).__name__}")
    if not factor.is_finite() or factor <= 0:
        raise ValueError(f"factor must be a positive finite Decimal: {factor!r}")
    exact = Fraction(factor)
    ratio = exact.limit_denominator(_MAX_SPLIT_DENOMINATOR)
    if abs(ratio - exact) > ratio * _RATIO_TOLERANCE:
        raise ValueError(f"factor is not a split ratio: {factor!r}")
    if ratio == 1:
        raise ValueError(f"factor 1 is not a split: {factor!r}")
    return ratio


def _check_session(portfolio: Portfolio, session_date: date) -> None:
    if isinstance(session_date, datetime) or not isinstance(session_date, date):
        raise TypeError(f"session_date must be a date, got {type(session_date).__name__}")
    if not dates.is_session(session_date):
        raise ValueError(f"{session_date} is not an NYSE session")
    if portfolio.last_session is not None and session_date <= portfolio.last_session:
        raise ValueError(
            f"split session {session_date} must be after the last stepped session "
            f"{portfolio.last_session}"
        )


def _rescale_price(price: Decimal, ratio: Fraction) -> Decimal:
    return _q_exact(Fraction(price) / ratio)


def _split_shares(shares: int, ratio: Fraction) -> tuple[int, Fraction]:
    """``(floor(shares * ratio), fractional remainder)`` in post-split shares."""
    total = shares * ratio
    whole = total.numerator // total.denominator
    return whole, total - whole


def _rescale_order(order: Order, ratio: Fraction, shares: int) -> Order:
    """``order`` in post-split units. Raises ValueError (before building anything) when the
    rescaled prices cannot be held at 4 dp: a price rounds to 0, or SL rounds up to TP."""
    last = _rescale_price(order.last_price, ratio)
    limit = _rescale_price(order.limit_price, ratio)
    tp = _rescale_price(order.tp_price, ratio)
    sl = _rescale_price(order.sl_price, ratio)
    fill = None if order.fill_price is None else _rescale_price(order.fill_price, ratio)
    if min(last, limit, tp, sl) <= 0 or (fill is not None and fill <= 0) or sl >= tp:
        raise ValueError(
            f"{order.symbol} (slot {order.slot}): a split of ratio {ratio} leaves prices that "
            f"4 dp cannot hold (limit {limit}, tp {tp}, sl {sl}, fill {fill})"
        )
    return replace(
        order,
        shares=shares,
        last_price=last,
        limit_price=limit,
        tp_price=tp,
        sl_price=sl,
        fill_price=fill,
    )


def apply_split(
    portfolio: Portfolio, symbol: str, factor: Decimal, session_date: date
) -> tuple[Portfolio, tuple[Event, ...]]:
    """Rewrite ``symbol``'s live orders and mark in post-split units for a split executing on
    ``session_date``.

    Returns the new portfolio and one event per live order of ``symbol``, in slot order:
    ``split`` (adjusted; ``cash_usd`` = cash in lieu for an open position, None for a pending
    order), ``expire`` (pending order floored to 0 shares) or ``exit`` (open position floored to
    0 shares, ``forced=True``). A portfolio with nothing in ``symbol`` is returned as is, with no
    events. The caller applies each split exactly once (``split_adjustments`` guarantees that).
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    if not isinstance(symbol, str):
        raise TypeError(f"symbol must be a str, got {type(symbol).__name__}")
    if not symbol:
        raise ValueError("empty symbol")
    ratio = _split_ratio(factor)
    _check_session(portfolio, session_date)

    old_mark = portfolio.mark(symbol)
    if old_mark is None and all(o.symbol != symbol for o in portfolio.orders):
        return portfolio, ()
    new_mark = None if old_mark is None else _rescale_price(old_mark, ratio)
    if new_mark is not None and new_mark <= 0:
        raise ValueError(
            f"{symbol}: a split of ratio {ratio} leaves a mark ({old_mark} -> {new_mark}) "
            f"that 4 dp cannot hold"
        )

    kept: list[Order] = []
    events: list[Event] = []
    cash = portfolio.cash
    still_open = False
    liquidated = False
    for order in portfolio.orders:  # Portfolio keeps orders sorted by slot
        if order.symbol != symbol:
            kept.append(order)
            continue
        whole, fraction = _split_shares(order.shares, ratio)
        if order.status == "pending":
            if whole == 0:
                expired = replace(order, status="expired")
                events.append(Event(session_date=session_date, kind="expire", order=expired))
                continue
            adjusted = _rescale_order(order, ratio, whole)
            kept.append(adjusted)
            events.append(Event(session_date=session_date, kind="split", order=adjusted))
            continue
        # status == "open"
        if new_mark is None or order.fill_price is None:
            raise ValueError(f"open {symbol} order in slot {order.slot} has no mark or fill price")
        in_lieu = _q_exact(fraction * Fraction(new_mark))
        cash += in_lieu
        if whole == 0:
            closed = replace(
                order,
                status="closed",
                exit_date=session_date,
                exit_price=old_mark,
                exit_reason="time",
                pnl_usd=in_lieu - buy_cost(order.fill_price, order.shares),
            )
            events.append(
                Event(session_date=session_date, kind="exit", order=closed, forced=True, cash_usd=in_lieu)
            )
            liquidated = True
            continue
        adjusted = _rescale_order(order, ratio, whole)
        kept.append(adjusted)
        still_open = True
        events.append(Event(session_date=session_date, kind="split", order=adjusted, cash_usd=in_lieu))

    drop_mark = liquidated and not still_open
    marks = tuple(
        (s, new_mark if s == symbol else m)
        for s, m in portfolio.marks
        if not (s == symbol and drop_mark)
    )
    new_portfolio = replace(portfolio, cash=cash, orders=tuple(kept), marks=marks)
    return new_portfolio, tuple(events)
