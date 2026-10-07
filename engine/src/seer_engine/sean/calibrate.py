"""``sean calibrate``: does ``sim/costs.py`` still charge what Gotrade charged?

The Gotrade fee schedule the lab prices trades with (``sim.costs``, Sean phase 6) was fitted to
the owner's own order receipts. Every receipt Sean stores in ``sean_orders`` is a fresh
measurement of that schedule, so this module replays it: for each stored order it asks
``costs.fee_parts`` what the schedule says the order should have paid on the order's own date, and
compares the three parts -- trading fee, regulatory fee, PPN (VAT) -- with what the receipt says.

An order dated on or after the first day of the regime in force now that is off by more than a
cent in any part means Gotrade changed its fees, or the fit was wrong: ``sean calibrate`` exits 1
and ``sim/costs.py`` needs a new dated regime. An order under an older regime is printed with its
residual and never fails the check -- a past regime cannot change any more, and its fit is Phase
6's own test.

Receipt dates are WIB calendar dates (Gotrade prints "October 07, 2026" + "21:55 WIB"), which is
what the regime boundaries were fitted to. This is deliberately not the New York trade date the
ledger uses (``sean.ledger``): a fee regime starts on the day Gotrade's app started charging it.

Pure except ``rows_from_db``. No clock, no network.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Protocol

from seer_engine.sim import costs

TOLERANCE = Decimal("0.01")  # a cent: PPN is rounded on Gotrade's side, 29 of 30 receipts exact
WIB = timezone(timedelta(hours=7), "WIB")
SIDES: tuple[str, ...] = ("buy", "sell")


class Fees(Protocol):
    """What a fee schedule says one order pays, part by part (``costs.FeeParts`` satisfies it)."""

    trading: Decimal
    regulatory: Decimal
    ppn: Decimal


FeeFn = Callable[..., Fees]  # fee(side, amount, on=date) -> Fees


@dataclass(frozen=True)
class PaidFees:
    """What one receipt says the order paid. Every money field is a non-negative ``Decimal``."""

    ref: str  # "order 12": how the report names the row
    on: date  # the receipt's WIB date
    side: str
    symbol: str  # "" when the source has none
    amount: Decimal
    trading: Decimal
    regulatory: Decimal
    ppn: Decimal

    def __post_init__(self) -> None:
        if self.side not in SIDES:
            raise ValueError(f"{self.ref}: side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.on, datetime) or not isinstance(self.on, date):
            raise TypeError(f"{self.ref}: on must be a date, got {type(self.on).__name__}")
        for name in ("amount", "trading", "regulatory", "ppn"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{self.ref}: {name} must be a Decimal, got {type(value).__name__}")
            if not value.is_finite() or value < 0:
                raise ValueError(f"{self.ref}: {name} must be a non-negative amount, got {value}")

    @property
    def total(self) -> Decimal:
        return self.trading + self.regulatory + self.ppn


@dataclass(frozen=True)
class Residual:
    """One order: what it paid, what the schedule says, and whether the order is in the current
    regime (and so able to fail the check)."""

    paid: PaidFees
    expected: Any  # Fees
    current: bool

    @property
    def gaps(self) -> tuple[Decimal, Decimal, Decimal]:
        """Paid minus expected for trading, regulatory and PPN, in that order."""
        e = self.expected
        return (
            self.paid.trading - Decimal(e.trading),
            self.paid.regulatory - Decimal(e.regulatory),
            self.paid.ppn - Decimal(e.ppn),
        )

    @property
    def gap(self) -> Decimal:
        """The largest absolute difference across the three parts."""
        return max(abs(g) for g in self.gaps)

    @property
    def ok(self) -> bool:
        return self.gap <= TOLERANCE

    @property
    def expected_total(self) -> Decimal:
        e = self.expected
        return Decimal(e.trading) + Decimal(e.regulatory) + Decimal(e.ppn)


@dataclass(frozen=True)
class Calibration:
    since: date  # first day of the regime in force now
    residuals: tuple[Residual, ...]

    @property
    def current(self) -> tuple[Residual, ...]:
        return tuple(r for r in self.residuals if r.current)

    @property
    def misses(self) -> tuple[Residual, ...]:
        return tuple(r for r in self.current if not r.ok)

    @property
    def passed(self) -> bool:
        return not self.misses


def current_since() -> date:
    """The first day of the fee regime in force now (Phase 6's ``GOTRADE.current``)."""
    return costs.GOTRADE.current.since


def check(paid: Iterable[PaidFees], *, since: date, fee: FeeFn = costs.fee_parts) -> Calibration:
    """Replay ``fee`` over every order, each on its own date. Order is preserved."""
    out = tuple(
        Residual(paid=p, expected=fee(p.side, p.amount, on=p.on), current=p.on >= since)
        for p in paid
    )
    return Calibration(since=since, residuals=out)


def _usd(x: Decimal) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


def format_report(cal: Calibration) -> str:
    """One line per order, then one sentence that says whether the schedule still holds."""
    rows = cal.residuals
    if not rows:
        return "Gotrade fee check: no orders stored yet, so there is nothing to check."
    since = cal.since.isoformat()
    current = cal.current
    lines = [
        f"Gotrade fee check: {len(rows)} order(s); {len(current)} since the current fee schedule "
        f"began on {since}.",
        "",
    ]
    for r in rows:
        p = r.paid
        e = r.expected
        if r.ok:
            verdict = "matches"
        elif r.current:
            verdict = f"OFF by up to {_usd(r.gap)}"
        else:
            verdict = f"older schedule, off by up to {_usd(r.gap)} (not checked)"
        lines.append(
            f"  {p.on.isoformat()}  {p.side:<4}  {(p.symbol or '-'):<6} {_usd(p.amount):>11}  "
            f"paid {_usd(p.total)} (trading {_usd(p.trading)}, regulatory {_usd(p.regulatory)}, "
            f"VAT {_usd(p.ppn)})  schedule {_usd(r.expected_total)} (trading "
            f"{_usd(Decimal(e.trading))}, regulatory {_usd(Decimal(e.regulatory))}, VAT "
            f"{_usd(Decimal(e.ppn))})  {verdict}"
        )
    lines.append("")
    if not current:
        lines.append(
            f"No order is dated on or after {since}, so the current fee schedule has nothing to be "
            f"checked against yet."
        )
    elif cal.passed:
        lines.append(
            f"All {len(current)} order(s) since {since} match the schedule to within a cent in "
            f"every part."
        )
    else:
        lines.append(
            f"{len(cal.misses)} of {len(current)} order(s) since {since} are off by more than a "
            f"cent. Gotrade's fees have changed or the fit was wrong: refit the schedule in "
            f"engine/src/seer_engine/sim/costs.py (add a new dated regime; never edit a past one) "
            f"and run this check again."
        )
    return "\n".join(lines)


def wib_date(at: datetime) -> date:
    """The WIB calendar date of a timezone-aware ``executed_at``."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError(f"executed_at must be a timezone-aware datetime, got {at!r}")
    return at.astimezone(WIB).date()


_ORDERS_SQL = """
SELECT id, side, symbol, executed_at, amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd
FROM sean_orders
ORDER BY executed_at, id
"""


def rows_from_db(conn: Any) -> tuple[PaidFees, ...]:
    """Every stored order's fees, oldest first (contract A columns; read only)."""
    out: list[PaidFees] = []
    for oid, side, symbol, at, amount, trading, regulatory, ppn in conn.execute(_ORDERS_SQL).fetchall():
        out.append(
            PaidFees(
                ref=f"order {oid}",
                on=wib_date(at),
                side=str(side),
                symbol=str(symbol),
                amount=Decimal(amount),
                trading=Decimal(trading),
                regulatory=Decimal(regulatory),
                ppn=Decimal(ppn),
            )
        )
    return tuple(out)
