"""SPY buy-and-hold benchmark curves (handover §3 "Benchmark details", "SPY dividends").

Pure: no database, no files, no clock. ``io.read_dividends`` (phase 5) reads
``engine/data/spy_dividends.csv`` and hands its text to :func:`parse_dividends`.

Rules, identical for both curves:

- The curve starts with ``Snapshot(prev_session(start), cash0, cash0)``, so total return
  ``last / first - 1`` is measured from the starting cash, exactly like the strategy's run.
- At the **open** of ``start`` buy ``floor(cash0 / (open × 1.001))`` whole shares; cash pays
  ``sim.buy_cost(open, shares)``; the remainder sits idle.
- Every session from ``start`` to ``end`` is marked at its close:
  ``equity = q(cash + shares × close)``. Nothing is ever sold (the end is marked, not
  liquidated, as the strategy's open positions are).
- Total return only (``spy_tr``): a dividend with ``start < ex_date <= end`` is credited on
  its ex-date session (the holder at the previous close is paid): ``cash += q(shares ×
  amount)``, then ``floor(cash / (close × 1.001))`` more shares are bought at that close
  with ``sim.buy_cost``. A dividend on ``start`` itself is not credited (bought at the open,
  not a holder at the previous close). Price-only (``spy_price``) ignores dividends.
- Every NYSE session in the window must have a SPY bar; a missing one raises ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from seer_engine.dates import prev_session, sessions
from seer_engine.prices import Bar
from seer_engine.sim import COST_RATE, Snapshot, buy_cost, q
from seer_engine.sim.rules import SHARE_QUANTUM

DIVIDENDS_HEADER = "ex_date,amount_usd"
PRICE_CURVE = "spy_price"
TOTAL_RETURN_CURVE = "spy_tr"


@dataclass(frozen=True, slots=True)
class Dividend:
    """One cash dividend: ``amount`` USD per share, paid to holders at the close before ``ex_date``."""

    ex_date: date
    amount: Decimal


@dataclass(frozen=True)
class BenchmarkCurve:
    """A buy-and-hold equity curve.

    ``snapshots[0]`` is ``Snapshot(prev_session(start), cash0, cash0)``; then one per session
    ``start..end``. ``shares`` and ``cash`` are the holding after ``end``; ``dividends_usd`` is
    the total cash dividends credited (0 for the price-only curve).
    """

    name: str
    snapshots: tuple[Snapshot, ...]
    shares: int | Decimal  # whole shares, or a multiple of SHARE_QUANTUM when fractional
    cash: Decimal
    dividends_usd: Decimal


def parse_dividends(text: str) -> tuple[Dividend, ...]:
    """Parse ``ex_date,amount_usd`` CSV text into dividends.

    The first non-empty line must be the header exactly. Blank lines are ignored. Each row
    needs an ISO date and a finite decimal amount > 0; dates must be strictly ascending (so
    unique). Any violation raises ``ValueError`` naming the 1-based line number.
    """
    lines = text.splitlines()
    rows: list[Dividend] = []
    header_seen = False
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        if not header_seen:
            if line != DIVIDENDS_HEADER:
                raise ValueError(f"line {number}: expected header {DIVIDENDS_HEADER!r}, got {line!r}")
            header_seen = True
            continue
        fields = line.split(",")
        if len(fields) != 2:
            raise ValueError(f"line {number}: expected 2 fields, got {len(fields)}: {line!r}")
        try:
            ex_date = date.fromisoformat(fields[0].strip())
        except ValueError as exc:
            raise ValueError(f"line {number}: bad ex_date {fields[0]!r}") from exc
        try:
            amount = Decimal(fields[1].strip())
        except InvalidOperation as exc:
            raise ValueError(f"line {number}: bad amount_usd {fields[1]!r}") from exc
        if not amount.is_finite() or amount <= 0:
            raise ValueError(f"line {number}: amount_usd must be > 0, got {fields[1]!r}")
        if rows and ex_date <= rows[-1].ex_date:
            raise ValueError(f"line {number}: ex_date {ex_date} is not after {rows[-1].ex_date}")
        rows.append(Dividend(ex_date=ex_date, amount=amount))
    if not header_seen:
        raise ValueError(f"no header: expected {DIVIDENDS_HEADER!r}")
    return tuple(rows)


def _whole_shares(cash: Decimal, price: Decimal) -> int:
    """The most whole shares ``cash`` buys at ``price`` after the 0.1% cost."""
    n = int(cash // (price * (1 + COST_RATE)))
    # q() rounds half-up; never let the rounded cost exceed the cash.
    while n > 0 and buy_cost(price, n) > cash:
        n -= 1
    return n


def _fractional_shares(cash: Decimal, price: Decimal) -> Decimal:
    """The most shares ``cash`` buys at ``price`` after the 0.1% cost, in multiples of
    ``SHARE_QUANTUM`` (0.0001): the paper benchmark (Gotrade sells SPY in fractions)."""
    unit = price * (1 + COST_RATE)
    n = (cash / unit).quantize(SHARE_QUANTUM, rounding=ROUND_FLOOR)
    while n > 0 and fractional_buy_cost(price, n) > cash:
        n -= SHARE_QUANTUM
    return n if n > 0 else Decimal(0)


def fractional_buy_cost(price: Decimal, shares: Decimal) -> Decimal:
    """``buy_cost`` for a fractional share count: ``q(price × n × 1.001)``."""
    return q(price * shares * (1 + COST_RATE))


def _bar(spy: Mapping[date, Bar], d: date) -> Bar:
    bar = spy.get(d)
    if bar is None:
        raise ValueError(f"no SPY bar on session {d}")
    if not isinstance(bar, Bar):
        raise TypeError(f"SPY bar on {d} must be a Bar, got {type(bar).__name__}")
    if bar.date != d:
        raise ValueError(f"SPY bar keyed {d} is dated {bar.date}")
    return bar


def buy_and_hold(
    spy: Mapping[date, Bar],
    start: date,
    end: date,
    initial_cash: Decimal,
    *,
    dividends: Sequence[Dividend] = (),
    name: str,
    fractional: bool = False,
) -> BenchmarkCurve:
    """Buy SPY at ``start``'s open, hold, mark every close through ``end``.

    ``dividends`` empty gives the price-only curve; SPY's dividends give the total-return
    curve. Raises ``ValueError`` when ``start``/``end`` are not sessions, ``end < start``,
    ``initial_cash <= 0``, a dividend list is not strictly ascending, a dividend inside
    ``(start, end]`` is not dated on a session, or a session has no SPY bar.

    ``fractional`` buys in multiples of ``SHARE_QUANTUM`` instead of whole shares (the paper
    benchmark since 2026-10-07; every backtest keeps the whole-share default).
    """
    if not isinstance(initial_cash, Decimal):
        raise TypeError(f"initial_cash must be a Decimal, got {type(initial_cash).__name__}")
    cash0 = q(initial_cash)
    if cash0 <= 0:
        raise ValueError(f"initial_cash must be > 0, got {initial_cash}")
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    window = sessions(start, end)
    if not window or window[0] != start:
        raise ValueError(f"start {start} is not an NYSE session")
    if window[-1] != end:
        raise ValueError(f"end {end} is not an NYSE session")
    for prev, cur in zip(dividends, dividends[1:]):
        if cur.ex_date <= prev.ex_date:
            raise ValueError(f"dividends not strictly ascending at {cur.ex_date}")
    in_window = set(window)
    paid: dict[date, Decimal] = {}
    for div in dividends:
        if start < div.ex_date <= end:
            if div.ex_date not in in_window:
                raise ValueError(f"dividend ex_date {div.ex_date} is not an NYSE session")
            paid[div.ex_date] = div.amount

    snaps: list[Snapshot] = [Snapshot(date=prev_session(start), cash_usd=cash0, equity_usd=cash0)]
    first = _bar(spy, start)
    if fractional:
        shares: int | Decimal = _fractional_shares(cash0, first.open)
        cash = cash0 - fractional_buy_cost(first.open, shares)
    else:
        shares = _whole_shares(cash0, first.open)
        cash = cash0 - buy_cost(first.open, shares)
    credited = Decimal("0.0000")
    for d in window:
        bar = _bar(spy, d)
        amount = paid.get(d)
        if amount is not None:
            income = q(shares * amount)
            cash += income
            credited += income
            if fractional:
                extra = _fractional_shares(cash, bar.close)
                cash -= fractional_buy_cost(bar.close, extra)
                shares += extra
            else:
                more = _whole_shares(cash, bar.close)
                cash -= buy_cost(bar.close, more)
                shares += more
        snaps.append(Snapshot(date=d, cash_usd=cash, equity_usd=q(cash + shares * bar.close)))
    return BenchmarkCurve(
        name=name,
        snapshots=tuple(snaps),
        shares=shares,
        cash=cash,
        dividends_usd=credited,
    )


def spy_curves(
    spy: Mapping[date, Bar],
    start: date,
    end: date,
    initial_cash: Decimal,
    dividends: Sequence[Dividend],
) -> tuple[BenchmarkCurve, BenchmarkCurve]:
    """``(spy_price, spy_tr)``: the price-only and total-return SPY curves over one window."""
    price = buy_and_hold(spy, start, end, initial_cash, name=PRICE_CURVE)
    total = buy_and_hold(spy, start, end, initial_cash, dividends=dividends, name=TOTAL_RETURN_CURVE)
    return price, total
