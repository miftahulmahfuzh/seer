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
- ``cost_model="gotrade"`` (a lab method on Gotrade's measured fees, ``sim.costs``): every buy
  above, the first one and each dividend reinvestment, pays Gotrade's schedule instead of 0.1%,
  and the share count is the most whose rounded cash fits (``sim.costs.gotrade_shares_for``), so
  a method and its benchmark pay alike. The default "flat" is every curve above, unchanged.
- ``contributions`` makes the curve **dollar-cost-averaged**: the same deposits the book received,
  landing as cash at the close of the first session on or after each calendar date and spent at
  that close through the same buy the dividend path uses. Empty (the default) is every curve
  above, unchanged. Without it, "beats SPY TR" compares a book fed 5,000,000 IDR a month against
  a single opening sum -- two books holding different money at different times.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from seer_engine.dates import prev_session, sessions
from seer_engine.prices import Bar
from seer_engine.sim import COST_RATE, Snapshot, buy_cost, q
from seer_engine.sim.costs import COST_MODELS, CostModel, gotrade_cash, gotrade_shares_for
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

    ``cashflows`` are the deposits this curve received, summed per landing session and ascending:
    ``()`` for a plain buy-and-hold, and the dollar-cost-averaging schedule for a curve built with
    ``contributions``. ``metrics.curve_metrics`` reads it, so the money-weighted return of the
    benchmark is computed from the same dollars on the same days as the book's.
    """

    name: str
    snapshots: tuple[Snapshot, ...]
    shares: int | Decimal  # whole shares, or a multiple of SHARE_QUANTUM when fractional
    cash: Decimal
    dividends_usd: Decimal
    cashflows: tuple[tuple[date, Decimal], ...] = ()


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


def _whole_shares(cash: Decimal, price: Decimal, cost_model: CostModel = "flat") -> int:
    """The most whole shares ``cash`` buys at ``price`` after the 0.1% cost (or, under
    "gotrade", after Gotrade's fees)."""
    if cost_model == "gotrade":
        return int(gotrade_shares_for(cash, price, Decimal(1)))
    n = int(cash // (price * (1 + COST_RATE)))
    # q() rounds half-up; never let the rounded cost exceed the cash.
    while n > 0 and buy_cost(price, n) > cash:
        n -= 1
    return n


def _fractional_shares(cash: Decimal, price: Decimal, cost_model: CostModel = "flat") -> Decimal:
    """The most shares ``cash`` buys at ``price`` after the 0.1% cost (or, under "gotrade",
    after Gotrade's fees), in multiples of ``SHARE_QUANTUM`` (0.0001): the paper benchmark
    (Gotrade sells SPY in fractions)."""
    if cost_model == "gotrade":
        n = gotrade_shares_for(cash, price, SHARE_QUANTUM)
        return n if n > 0 else Decimal(0)
    unit = price * (1 + COST_RATE)
    n = (cash / unit).quantize(SHARE_QUANTUM, rounding=ROUND_FLOOR)
    while n > 0 and fractional_buy_cost(price, n) > cash:
        n -= SHARE_QUANTUM
    return n if n > 0 else Decimal(0)


def fractional_buy_cost(price: Decimal, shares: Decimal, cost_model: CostModel = "flat") -> Decimal:
    """``buy_cost`` for a fractional share count: ``q(price × n × 1.001)``, or under "gotrade"
    ``q(price × n)`` plus Gotrade's fees (nothing for 0 shares)."""
    if cost_model == "gotrade":
        return gotrade_cash("buy", price, shares)[0]
    return q(price * shares * (1 + COST_RATE))


def _whole_buy_cost(price: Decimal, shares: int, cost_model: CostModel) -> Decimal:
    """``sim.buy_cost`` for whole shares, or under "gotrade" ``q(price × n)`` plus Gotrade's fees."""
    if cost_model == "gotrade":
        return gotrade_cash("buy", price, shares)[0]
    return buy_cost(price, shares)


def _bar(spy: Mapping[date, Bar], d: date) -> Bar:
    bar = spy.get(d)
    if bar is None:
        raise ValueError(f"no SPY bar on session {d}")
    if not isinstance(bar, Bar):
        raise TypeError(f"SPY bar on {d} must be a Bar, got {type(bar).__name__}")
    if bar.date != d:
        raise ValueError(f"SPY bar keyed {d} is dated {bar.date}")
    return bar


def _landing(window: Sequence[date], d: date) -> date | None:
    """The first session in ``window`` on or after ``d``; None when ``d`` is after the window.

    Resolved against the window already in hand rather than through ``dates.next_session``, so a
    deposit can never land outside the curve it funds. ``next_session`` is also strictly *after*
    its argument, which would push a deposit dated on a trading day to the following one.
    """
    i = bisect_left(window, d)
    return window[i] if i < len(window) else None


def buy_and_hold(
    spy: Mapping[date, Bar],
    start: date,
    end: date,
    initial_cash: Decimal,
    *,
    dividends: Sequence[Dividend] = (),
    name: str,
    fractional: bool = False,
    cost_model: CostModel = "flat",
    contributions: Sequence[tuple[date, Decimal]] = (),
) -> BenchmarkCurve:
    """Buy SPY at ``start``'s open, hold, mark every close through ``end``.

    ``dividends`` empty gives the price-only curve; SPY's dividends give the total-return
    curve. Raises ``ValueError`` when ``start``/``end`` are not sessions, ``end < start``,
    ``initial_cash <= 0``, a dividend list is not strictly ascending, a dividend inside
    ``(start, end]`` is not dated on a session, or a session has no SPY bar.

    ``fractional`` buys in multiples of ``SHARE_QUANTUM`` instead of whole shares (the paper
    benchmark since 2026-10-07; every backtest keeps the whole-share default).

    ``cost_model`` "gotrade" prices every buy with Gotrade's measured schedule (``sim.costs``)
    instead of 0.1%: the benchmark a ``cost_model="gotrade"`` lab method is measured against.
    ValueError for any other value than "flat"/"gotrade".

    ``contributions`` are ``(date, amount)`` deposits in USD, strictly ascending, each amount a
    ``Decimal`` > 0. This is the **dollar-cost-averaged** benchmark: the same money, paid in on
    the same days, put into SPY instead -- without it, "beats SPY TR" compares a book fed
    5,000,000 IDR a month against a single opening sum, which flatters the book in a rising
    market and punishes it in a falling one, because the two are holding different amounts at
    different times.

    Each deposit lands as cash at the close of the first session **on or after** its calendar
    date, and is spent at that close. The owner's schedule deposits on the 25th and the NYSE
    calendar produces the gap to the next session -- measured, a mean of 7.0 calendar days
    ranging 4 (Feb 2027) to 10 (Dec 2026) -- so the idle cash is reproduced rather than assumed
    away. A deposit whose landing session is on or before ``start``, or after ``end``, is
    dropped: the opening cash is the opening cash, exactly as a dividend dated on ``start`` is
    not credited. Two deposits landing on one session are summed and spent in one buy.

    SPY buys as the money arrives, while a book waits for its rotation, so SPY's idle gap is the
    shorter of the two and the benchmark is the harder to beat. That direction is deliberate.
    """
    if cost_model not in COST_MODELS:
        raise ValueError(f"unknown cost_model {cost_model!r}; expected one of {COST_MODELS}")
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

    deposits: dict[date, Decimal] = {}
    previous: date | None = None
    for when, amount in contributions:
        if isinstance(when, datetime) or not isinstance(when, date):
            raise TypeError(f"a contribution date must be a date, got {type(when).__name__}")
        if not isinstance(amount, Decimal):
            raise TypeError(f"a contribution amount must be a Decimal, got {type(amount).__name__}")
        if amount <= 0:
            raise ValueError(f"a contribution must be > 0, got {amount} on {when}")
        if previous is not None and when <= previous:
            raise ValueError(f"contributions not strictly ascending at {when}")
        previous = when
        session = _landing(window, when)
        if session is None or session <= start:
            continue
        deposits[session] = deposits.get(session, Decimal("0.0000")) + q(amount)

    snaps: list[Snapshot] = [Snapshot(date=prev_session(start), cash_usd=cash0, equity_usd=cash0)]
    first = _bar(spy, start)
    if fractional:
        shares: int | Decimal = _fractional_shares(cash0, first.open, cost_model)
        cash = cash0 - fractional_buy_cost(first.open, shares, cost_model)
    else:
        shares = _whole_shares(cash0, first.open, cost_model)
        cash = cash0 - _whole_buy_cost(first.open, shares, cost_model)
    credited = Decimal("0.0000")
    for d in window:
        bar = _bar(spy, d)
        reinvest = False
        amount = paid.get(d)
        if amount is not None:
            income = q(shares * amount)
            cash += income
            credited += income
            reinvest = True
        deposit = deposits.get(d)
        if deposit is not None:
            cash += deposit
            reinvest = True
        if reinvest:
            if fractional:
                extra = _fractional_shares(cash, bar.close, cost_model)
                cash -= fractional_buy_cost(bar.close, extra, cost_model)
                shares += extra
            else:
                more = _whole_shares(cash, bar.close, cost_model)
                cash -= _whole_buy_cost(bar.close, more, cost_model)
                shares += more
        snaps.append(Snapshot(date=d, cash_usd=cash, equity_usd=q(cash + shares * bar.close)))
    return BenchmarkCurve(
        name=name,
        snapshots=tuple(snaps),
        shares=shares,
        cash=cash,
        dividends_usd=credited,
        cashflows=tuple(sorted(deposits.items())),
    )


def spy_curves(
    spy: Mapping[date, Bar],
    start: date,
    end: date,
    initial_cash: Decimal,
    dividends: Sequence[Dividend],
    *,
    cost_model: CostModel = "flat",
    contributions: Sequence[tuple[date, Decimal]] = (),
) -> tuple[BenchmarkCurve, BenchmarkCurve]:
    """``(spy_price, spy_tr)``: the price-only and total-return SPY curves over one window,
    both paying ``cost_model`` and both receiving ``contributions`` (see ``buy_and_hold``).

    Both curves get the deposits, not just the total-return one: ``spy_price`` is the same
    comparison with dividends withheld, and a price-only curve fed differently from the
    total-return one would not be that.
    """
    price = buy_and_hold(
        spy, start, end, initial_cash, name=PRICE_CURVE, cost_model=cost_model,
        contributions=contributions,
    )
    total = buy_and_hold(
        spy, start, end, initial_cash, dividends=dividends, name=TOTAL_RETURN_CURVE,
        cost_model=cost_model, contributions=contributions,
    )
    return price, total
