"""Gotrade's fee schedule, fitted to the owner's real order receipts (Sean plan, phase 6).

Until 2026-10-07 every simulated trade paid one assumed number, ``TradeRules.cost_rate`` (0.1%
per side). The owner's 30 Gotrade order receipts (``tests/fixtures/gotrade_fees.json``, fee
columns only) show what an order really costs, and at the sizes the owner trades (a few tens of
dollars a slot) it is 3-5x that. This module is that schedule, as data plus one pure function.

One order of ``amount`` dollars (price × shares, rounded half-up to the cent) pays three
separately printed fees, each in cents:

- **trading fee**: ``trading_rate × amount`` rounded half-up to the cent, at least
  ``trading_min`` (only when ``trading_rate > 0``);
- **regulatory fee**: ``regulatory_rate × amount`` rounded UP to the cent, at most
  ``regulatory_cap``; a sell adds ``sell_extra_rate × amount`` rounded up to the cent, uncapped
  (the sell-side SEC fee + FINRA TAF + whatever Gotrade adds; see the fit below);
- **PPN** (Indonesian VAT): ``ppn_rate × (trading + regulatory)`` rounded HALF-DOWN to the cent.

A buy pays ``amount + total``; a sell receives ``amount − total``.

The fit (every number reproduced by ``tests/test_sim_costs.py``):

- 2025-06-10 (2 buys): no trading fee, no PPN; a 0.3% "regulatory" fee rounded up
  ($707.31 -> $2.13, $1,429.00 -> $4.29).
- 2025-06-26 .. 2025-07-22 (2 buys): trading 0.3% half-up ($1,832.90 -> $5.50, $592.41 ->
  $1.78); regulatory capped at $0.10.
- 2026-03-25 (3 buys): trading 0.3% half-up. Half-up, not up: $147.55 -> $0.44 (0.44265). The
  regulatory fee is 0.054% rounded up and capped at $0.11: $27.90 -> $0.02, $105.27 -> $0.06,
  $147.55 -> $0.08, $366.62 -> $0.11. Any rate in (0.0475%, 0.0542%] fits these with
  rounding up; 0.054% is the top of that band (conservative). LLY $366.62 paid $1.08, not the
  schedule's $1.10 (0.2946%, the only receipt off the schedule; it matches 0.3% of $360.00, as if
  the fee were taken on the order's requested notional): the schedule charges $0.02 more there,
  which errs on the side of cost.
- 2026-06-16 onward, the CURRENT regime (23 receipts: 22 buys, 1 sell): trading 0.2% half-up,
  minimum $0.10 (every $27.90 buy pays $0.10); regulatory as above, cap $0.11.
- PPN: 11% of (trading + regulatory), both as printed, rounded HALF-DOWN. Half-up fits 29 of 30
  and fails WDC 2026-06-16 ($2.39 + $0.11 = $2.50 -> 0.275 printed as $0.27); half-down fits
  all 30. Rounding the unrounded fees instead fails SPY 2025-06-26; rounding each fee's PPN
  separately fails LRCX 2026-03-25.
- Sells: ONE receipt (PLTR 2026-10-07, $72.51: trading $0.15, regulatory $0.07, PPN $0.02). The
  buy-side regulatory formula gives $0.04; the remaining $0.03 is modelled as an uncapped
  sell-only ``sell_extra_rate`` of 0.04%, rounded up. Any rate in (0.0276%, 0.0413%] fits; 0.04%
  sits near the top (conservative), and uncapped is the cautious reading of one data point. The
  statutory SEC fee alone is ~0.003%: this is far above it on purpose until more sells arrive
  (``seer sean calibrate`` reports every receipt's residual against this schedule).

Regime dates are the first receipt seen under each regime, not Gotrade's announcement dates:
an order between two receipts is priced by the earlier regime. ``on=None`` means the current
(latest) regime, which is what every backtest uses for every simulated date: the lab asks what
a method would cost the owner now, not what it would have cost in 2012.

Pure: no clock, no I/O, no floats.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from typing import Literal

from seer_engine.sim.model import q

CostModel = Literal["flat", "gotrade"]
COST_MODELS: tuple[str, ...] = ("flat", "gotrade")
Side = Literal["buy", "sell"]
SIDES: tuple[str, ...] = ("buy", "sell")
CENT = Decimal("0.01")
_ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class FeeParts:
    """One order's fees as Gotrade prints them, in dollars to the cent. ``total`` is their sum."""

    trading: Decimal
    regulatory: Decimal
    ppn: Decimal
    total: Decimal

    def __post_init__(self) -> None:
        for name in ("trading", "regulatory", "ppn", "total"):
            v = getattr(self, name)
            if not isinstance(v, Decimal):
                raise TypeError(f"{name} must be a Decimal, got {type(v).__name__}")
            if not v.is_finite() or v < 0:
                raise ValueError(f"{name} must be a finite amount >= 0, got {v}")
        if self.total != self.trading + self.regulatory + self.ppn:
            raise ValueError(
                f"total {self.total} != trading {self.trading} + regulatory {self.regulatory} + ppn {self.ppn}"
            )


@dataclass(frozen=True, slots=True)
class FeeRegime:
    """Gotrade's fees from ``since`` until the next regime (see the module docstring)."""

    since: date
    trading_rate: Decimal
    trading_min: Decimal
    regulatory_rate: Decimal
    regulatory_cap: Decimal | None
    sell_extra_rate: Decimal
    ppn_rate: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.since, datetime) or not isinstance(self.since, date):
            raise TypeError(f"since must be a date, got {type(self.since).__name__}")
        for name in ("trading_rate", "trading_min", "regulatory_rate", "sell_extra_rate", "ppn_rate"):
            v = getattr(self, name)
            if not isinstance(v, Decimal):
                raise TypeError(f"{name} must be a Decimal, got {type(v).__name__}")
            if not v.is_finite() or v < 0:
                raise ValueError(f"{name} must be a finite value >= 0, got {v}")
        if self.regulatory_cap is not None:
            if not isinstance(self.regulatory_cap, Decimal):
                raise TypeError(f"regulatory_cap must be a Decimal or None, got {type(self.regulatory_cap).__name__}")
            if not self.regulatory_cap.is_finite() or self.regulatory_cap <= 0:
                raise ValueError(f"regulatory_cap must be > 0, got {self.regulatory_cap}")

    def fees(self, side: Side, amount: Decimal) -> FeeParts:
        """The fees of one ``side`` order of ``amount`` dollars under this regime."""
        raw = _amount(amount)
        if side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {side!r}")
        if raw == 0:
            return FeeParts(_ZERO, _ZERO, _ZERO, _ZERO)
        # Any real order is at least a cent: a sub-cent sliver of a share is never free.
        cents = max(raw.quantize(CENT, rounding=ROUND_HALF_UP), CENT)
        trading = (cents * self.trading_rate).quantize(CENT, rounding=ROUND_HALF_UP)
        if self.trading_rate > 0 and trading < self.trading_min:
            trading = self.trading_min.quantize(CENT)
        regulatory = (cents * self.regulatory_rate).quantize(CENT, rounding=ROUND_UP)
        if self.regulatory_cap is not None and regulatory > self.regulatory_cap:
            regulatory = self.regulatory_cap.quantize(CENT)
        if side == "sell":
            regulatory += (cents * self.sell_extra_rate).quantize(CENT, rounding=ROUND_UP)
        ppn = ((trading + regulatory) * self.ppn_rate).quantize(CENT, rounding=ROUND_HALF_DOWN)
        return FeeParts(trading, regulatory, ppn, trading + regulatory + ppn)


@dataclass(frozen=True, slots=True)
class GotradeSchedule:
    """Gotrade's fee regimes, oldest first. ``regime_on(None)`` is the current (last) one."""

    regimes: tuple[FeeRegime, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.regimes, tuple) or not self.regimes:
            raise ValueError("regimes must be a non-empty tuple")
        for r in self.regimes:
            if not isinstance(r, FeeRegime):
                raise TypeError(f"regimes must hold FeeRegime values, got {type(r).__name__}")
        for a, b in zip(self.regimes, self.regimes[1:]):
            if b.since <= a.since:
                raise ValueError(f"regimes must be strictly ascending by since: {b.since} after {a.since}")

    @property
    def current(self) -> FeeRegime:
        return self.regimes[-1]

    def regime_on(self, on: date | None) -> FeeRegime:
        """The regime in force on ``on`` (the last one whose ``since <= on``); None = current.

        ValueError when ``on`` is before the first regime (no receipt says what Gotrade
        charged then).
        """
        if on is None:
            return self.regimes[-1]
        if isinstance(on, datetime) or not isinstance(on, date):
            raise TypeError(f"on must be a date or None, got {type(on).__name__}")
        found: FeeRegime | None = None
        for r in self.regimes:
            if r.since <= on:
                found = r
        if found is None:
            raise ValueError(f"no Gotrade fee schedule is known before {self.regimes[0].since} (asked for {on})")
        return found

    def fee_parts(self, side: Side, amount: Decimal, on: date | None = None) -> FeeParts:
        return self.regime_on(on).fees(side, amount)


def _amount(amount: object) -> Decimal:
    """``amount`` as a Decimal; TypeError for a non-Decimal (floats refused), ValueError for a
    negative or non-finite one."""
    if isinstance(amount, bool) or not isinstance(amount, (Decimal, int)):
        raise TypeError(f"amount must be a Decimal, got {type(amount).__name__}")
    a = Decimal(amount)
    if not a.is_finite() or a < 0:
        raise ValueError(f"amount must be a finite dollar amount >= 0, got {amount}")
    return a


_PPN = Decimal("0.11")
_REG_RATE = Decimal("0.00054")
_SELL_EXTRA = Decimal("0.0004")
_MIN = Decimal("0.10")

GOTRADE = GotradeSchedule(
    regimes=(
        FeeRegime(
            since=date(2025, 6, 10),
            trading_rate=Decimal(0),
            trading_min=Decimal(0),
            regulatory_rate=Decimal("0.003"),
            regulatory_cap=None,
            sell_extra_rate=Decimal(0),
            ppn_rate=Decimal(0),
        ),
        FeeRegime(
            since=date(2025, 6, 26),
            trading_rate=Decimal("0.003"),
            trading_min=_MIN,
            regulatory_rate=_REG_RATE,
            regulatory_cap=Decimal("0.10"),
            sell_extra_rate=_SELL_EXTRA,
            ppn_rate=_PPN,
        ),
        FeeRegime(
            since=date(2026, 3, 25),
            trading_rate=Decimal("0.003"),
            trading_min=_MIN,
            regulatory_rate=_REG_RATE,
            regulatory_cap=Decimal("0.11"),
            sell_extra_rate=_SELL_EXTRA,
            ppn_rate=_PPN,
        ),
        FeeRegime(
            since=date(2026, 6, 16),
            trading_rate=Decimal("0.002"),
            trading_min=_MIN,
            regulatory_rate=_REG_RATE,
            regulatory_cap=Decimal("0.11"),
            sell_extra_rate=_SELL_EXTRA,
            ppn_rate=_PPN,
        ),
    )
)


def fee_parts(side: Side, amount: Decimal, on: date | None = None) -> FeeParts:
    """Gotrade's fees for one ``side`` ("buy"/"sell") order of ``amount`` dollars on ``on``
    (None: the current regime). ``amount`` is rounded half-up to the cent first (at least $0.01
    when it is above zero); an amount of exactly 0 pays nothing (there is no order)."""
    return GOTRADE.fee_parts(side, amount, on)


def gotrade_cash(side: Side, price: Decimal, shares: Decimal | int) -> tuple[Decimal, Decimal]:
    """``(cash, fee)`` of one simulated order at today's schedule: amount ``q(price × shares)``;
    a buy's cash out is ``amount + fee``; a sell's proceeds are ``amount − fee`` with the fee
    capped at the amount (a dust sale never costs more than it brings in)."""
    amount = q(price * shares)
    fee = fee_parts(side, amount).total
    if side == "sell":
        fee = min(fee, amount)
        return amount - fee, fee
    return amount + fee, fee


def gotrade_shares_for(budget: Decimal, price: Decimal, quantum: Decimal) -> Decimal:
    """The most shares, a multiple of ``quantum``, whose buy cash (``gotrade_cash("buy", …)``)
    is <= ``budget``; 0 when none fits. Exact: the minimum fee makes cost non-linear in shares,
    but it never falls as shares grow, so the answer is found by bisection between a count that
    surely fits (shares the budget less the budget's own fee buys) and one that surely does not
    (shares the whole budget buys, fees ignored)."""
    for name, value in (("budget", budget), ("price", price), ("quantum", quantum)):
        if not isinstance(value, Decimal):
            raise TypeError(f"{name} must be a Decimal, got {type(value).__name__}")
    if quantum <= 0:
        raise ValueError(f"quantum must be > 0, got {quantum}")
    if price <= 0:
        raise ValueError(f"price must be > 0, got {price}")
    if budget <= 0:
        return quantum * 0

    def fits(k: int) -> bool:
        return gotrade_cash("buy", price, quantum * k)[0] <= budget

    step = price * quantum
    hi = int((budget / step).to_integral_value(rounding=ROUND_FLOOR))
    room = budget - fee_parts("buy", q(budget)).total
    lo = int((room / step).to_integral_value(rounding=ROUND_FLOOR)) if room > 0 else 0
    lo = min(lo, hi)
    if lo > 0 and not fits(lo):
        lo = 0  # never expected (see above); bisection needs a count that fits
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(mid):
            lo = mid
        else:
            hi = mid - 1
    return quantum * lo
