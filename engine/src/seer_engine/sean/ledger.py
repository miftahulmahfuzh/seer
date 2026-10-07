"""Sean's ledger: the owner's real Gotrade orders -> holdings and profit/loss.

The Python twin of ``web/lib/sean/ledger.ts`` (plan contract B). Both must reproduce
``web/lib/sean/fixtures/ledger.json``; a change to one is a change to both.

Average-cost method, fees in the cost basis, orders applied in ``(executed_at, id)`` order:

- buy:  shares += s; cost += total_usd (trade amount plus every fee).
- sell: sold = min(s, shares held). If sold > 0: avg = cost / held; proceeds = total_usd when
  sold is the whole receipt, else total_usd * sold / s (the shares sold beyond what Sean knows
  of, and their money, are ignored); realized += proceeds - sold * avg; cost -= sold * avg;
  shares -= sold. A sell of a stock Sean never saw bought therefore changes nothing but the
  fees: booking its whole proceeds as profit would invent gains the size of the position.
  A position left under 1e-9 shares is closed (shares = cost = 0).
- fees += trading + regulatory + PPN, on every order (the clamped part included).

An order belongs to the New York calendar date of its ``executed_at`` (its trade date): a
03:10 WIB fill is the previous US session. At date ``d`` the orders with trade date <= d
are applied, and each holding is valued at its last close on or before ``d`` or, with no
close at all, at the price of its last order applied so far.

Money is kept unrounded and rounded to cents (half away from zero) only on output; shares
round to 9 decimals on output. Pure: no database, no network, no floats.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/New_York")
CENT = Decimal("0.01")
SHARE_QUANTUM = Decimal("0.000000001")
DUST = Decimal("1e-9")
SIDES = ("buy", "sell")
_ZERO = Decimal(0)
_MONEY_FIELDS = ("price", "shares", "total_usd", "trading_fee_usd", "regulatory_fee_usd", "ppn_usd")

# symbol -> ascending (session date, close)
Closes = Mapping[str, Sequence[tuple[date, Decimal]]]


def money(x: Decimal) -> Decimal:
    """``x`` rounded to cents, half away from zero (Decimal's ROUND_HALF_UP)."""
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def share_count(x: Decimal) -> Decimal:
    """``x`` rounded to 9 decimals, half away from zero."""
    return x.quantize(SHARE_QUANTUM, rounding=ROUND_HALF_UP)


def _dec(value: object, field: str) -> Decimal:
    """An exact Decimal from a Decimal, int or numeric string. Floats are refused."""
    if isinstance(value, (bool, float)):
        raise TypeError(f"{field}: {value!r} is not an exact number (floats are refused)")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(value)
    raise TypeError(f"{field}: expected a number, got {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class Order:
    """One filled Gotrade order, the columns of ``sean_orders`` the ledger reads."""

    id: int
    symbol: str
    side: str
    executed_at: datetime
    price: Decimal
    shares: Decimal
    total_usd: Decimal
    trading_fee_usd: Decimal
    regulatory_fee_usd: Decimal
    ppn_usd: Decimal

    def __post_init__(self) -> None:
        if self.side not in SIDES:
            raise ValueError(f"order {self.id}: side must be buy or sell, got {self.side!r}")
        if not self.symbol:
            raise ValueError(f"order {self.id}: empty symbol")
        if not isinstance(self.executed_at, datetime) or self.executed_at.utcoffset() is None:
            raise ValueError(f"order {self.id}: executed_at must be a timezone-aware datetime")
        for name in _MONEY_FIELDS:
            if not isinstance(getattr(self, name), Decimal):
                raise TypeError(f"order {self.id}: {name} must be a Decimal")
        if self.shares <= 0:
            raise ValueError(f"order {self.id}: shares must be positive, got {self.shares}")

    @property
    def trade_date(self) -> date:
        """The New York calendar date of the fill: the US session it belongs to."""
        return self.executed_at.astimezone(MARKET_TZ).date()

    @property
    def fees_usd(self) -> Decimal:
        return self.trading_fee_usd + self.regulatory_fee_usd + self.ppn_usd


@dataclass(frozen=True, slots=True)
class Holding:
    """An open position on output: 9-decimal shares, cost basis in cents (fees included)."""

    symbol: str
    shares: Decimal
    cost_usd: Decimal


@dataclass(frozen=True, slots=True)
class Ledger:
    """Every order applied: open holdings by symbol, cumulative realized P&L and fees."""

    holdings: tuple[Holding, ...]
    realized_usd: Decimal
    fees_usd: Decimal


@dataclass(frozen=True, slots=True)
class PnlPoint:
    """One date's marks, in cents. The fields are the ``sean_equity`` columns."""

    day: date
    value_usd: Decimal
    cost_usd: Decimal
    realized_usd: Decimal
    unrealized_usd: Decimal
    pnl_usd: Decimal
    fees_usd: Decimal


def order_from_mapping(m: Mapping[str, object]) -> Order:
    """An Order from a fixture object or a row dict keyed by ``sean_orders`` column names.

    ``executed_at`` may be an ISO 8601 string with an offset or an aware datetime; numbers
    may be strings, ints or Decimals.
    """
    at = m["executed_at"]
    if isinstance(at, str):
        at = datetime.fromisoformat(at)
    if not isinstance(at, datetime):
        raise TypeError(f"executed_at: expected an ISO string or datetime, got {at!r}")
    return Order(
        id=int(str(m["id"])),
        symbol=str(m["symbol"]),
        side=str(m["side"]),
        executed_at=at,
        price=_dec(m["price"], "price"),
        shares=_dec(m["shares"], "shares"),
        total_usd=_dec(m["total_usd"], "total_usd"),
        trading_fee_usd=_dec(m["trading_fee_usd"], "trading_fee_usd"),
        regulatory_fee_usd=_dec(m["regulatory_fee_usd"], "regulatory_fee_usd"),
        ppn_usd=_dec(m["ppn_usd"], "ppn_usd"),
    )


def closes_from_mapping(
    m: Mapping[str, Iterable[Mapping[str, object]]],
) -> dict[str, list[tuple[date, Decimal]]]:
    """``{symbol: [{"date": "YYYY-MM-DD", "close": "1.23"}, ...]}`` -> sorted Closes."""
    out: dict[str, list[tuple[date, Decimal]]] = {}
    for symbol, rows in m.items():
        out[symbol] = sorted(
            (date.fromisoformat(str(r["date"])), _dec(r["close"], "close")) for r in rows
        )
    return out


def sort_orders(orders: Iterable[Order]) -> list[Order]:
    """Orders in ledger order: ``executed_at``, then ``id``."""
    return sorted(orders, key=lambda o: (o.executed_at, o.id))


def close_on_or_before(series: Sequence[tuple[date, Decimal]], d: date) -> Decimal | None:
    """The last close dated on or before ``d`` in an ascending series, or None."""
    i = bisect.bisect_right(series, d, key=lambda row: row[0])
    return series[i - 1][1] if i else None


class _Book:
    """The running ledger. Unrounded Decimals throughout."""

    __slots__ = ("shares", "cost", "realized", "fees", "last_price")

    def __init__(self) -> None:
        self.shares: dict[str, Decimal] = {}
        self.cost: dict[str, Decimal] = {}
        self.realized = _ZERO
        self.fees = _ZERO
        self.last_price: dict[str, Decimal] = {}

    def apply(self, o: Order) -> None:
        held = self.shares.get(o.symbol, _ZERO)
        cost = self.cost.get(o.symbol, _ZERO)
        if o.side == "buy":
            held += o.shares
            cost += o.total_usd
        else:
            sold = min(o.shares, held)
            if sold > 0:
                avg = cost / held
                # Pro rata (contract B, as web/lib/sean/ledger.ts): only the shares Sean knows of,
                # and their share of the receipt's total, count. Multiply first, then divide.
                proceeds = o.total_usd if sold == o.shares else o.total_usd * sold / o.shares
                self.realized += proceeds - sold * avg
                cost -= sold * avg
                held -= sold
        if held < DUST:
            self.shares.pop(o.symbol, None)
            self.cost.pop(o.symbol, None)
        else:
            self.shares[o.symbol] = held
            self.cost[o.symbol] = cost
        self.fees += o.fees_usd
        self.last_price[o.symbol] = o.price

    def value(self, d: date, closes: Closes) -> Decimal:
        total = _ZERO
        for symbol, held in self.shares.items():
            price = close_on_or_before(closes.get(symbol, ()), d)
            if price is None:
                price = self.last_price[symbol]
            total += held * price
        return total

    def point(self, d: date, closes: Closes) -> PnlPoint:
        value = self.value(d, closes)
        cost = sum(self.cost.values(), _ZERO)
        unrealized = value - cost
        return PnlPoint(
            day=d,
            value_usd=money(value),
            cost_usd=money(cost),
            realized_usd=money(self.realized),
            unrealized_usd=money(unrealized),
            pnl_usd=money(self.realized + unrealized),
            fees_usd=money(self.fees),
        )


def build_ledger(orders: Iterable[Order]) -> Ledger:
    """Apply every order; open holdings sorted by symbol."""
    book = _Book()
    for o in sort_orders(orders):
        book.apply(o)
    holdings = tuple(
        Holding(symbol, share_count(book.shares[symbol]), money(book.cost[symbol]))
        for symbol in sorted(book.shares)
    )
    return Ledger(holdings=holdings, realized_usd=money(book.realized), fees_usd=money(book.fees))


def pnl_series(orders: Iterable[Order], days: Iterable[date], closes: Closes) -> list[PnlPoint]:
    """One PnlPoint per date in ``days`` (strictly ascending), each counting the orders whose
    trade date is on or before it."""
    wanted = list(days)
    for a, b in zip(wanted, wanted[1:]):
        if b <= a:
            raise ValueError(f"days must be strictly ascending: {a} then {b}")
    ordered = sort_orders(orders)
    book = _Book()
    out: list[PnlPoint] = []
    i = 0
    for d in wanted:
        while i < len(ordered) and ordered[i].trade_date <= d:
            book.apply(ordered[i])
            i += 1
        out.append(book.point(d, closes))
    return out


def pnl_at(orders: Iterable[Order], d: date, closes: Closes) -> PnlPoint:
    """The marks at one date."""
    return pnl_series(orders, [d], closes)[0]
