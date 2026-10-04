"""The book engine: target weights in, fills and holding episodes out (P7a, handover D2).

Every rule set except ``DESIGN_V0`` runs here. Each night a strategy (an allocator) hands over
the instruments it wants held after the next session's open, as ranked ``Target`` values with
weights; ``step_book`` turns them into sells and buys at that session's open, applies stops
and take-profits fixed at entry, credits dividends, and marks the book at the close.

One session, in this exact order (all money ``Decimal``; ``q`` at every product; buy cash
``q(p × n × (1 + c))``, sell proceeds ``q(p × n × (1 − c))``, fee ``q(p × n × c)``):

1. dividends (``rules.dividends``): each position held before S with an ex-date on S is
   credited ``q(shares × amount)``;
2. open exits, in symbol order, positions with a bar on S: time stop, then gap below the
   stop / at or above the take, then a signal exit (``exit_pending``, or a decision session
   whose targets omit the symbol). A position the targets drop that has no bar on S is
   marked ``exit_pending`` and sold at its next bar's open. Nothing sold here is re-bought on S;
3. trims (decision sessions; ``rules.resize`` or the idle instrument): a held target worth
   at least ``RESIZE_BAND × equity`` more than its target weight is sold down at the open;
4. buys, targets in rank order with the idle instrument last: new entries (``max_positions``
   counted as the night before, exactly as ``sim.size_picks``) and adds (same band as trims,
   upward), sized the night before from the last snapshot's equity and the cash the night's
   planned sells will bring, then filled at the open ("open") or when the low trades strictly
   below the limit, at ``min(open, limit)`` ("limit", "open_limit"); a new entry under "limit"
   whose target has no limit price is bought exactly like "open_limit" (limit ``q(last × 1.02)``);
   a held target with no limit price is never added to; a fill cash cannot cover
   is shrunk to what cash affords. A new position is not checked against its stop or take on
   its fill session;
5. intraday exits of positions held before S: ``low <= stop`` at the stop ("sl"), else
   ``high > take`` at the take ("tp");
6. survivors: ``days_held + 1``, marked at the close when there is a bar;
7. snapshot ``q(cash + Σ shares × mark)``.

Under ``V0_BOOK`` with every held symbol re-targeted and §5 brackets for new picks, this is
``sim.size_picks`` + ``sim.step`` exactly (the phase-3 parity test).

Splits (paper trading): ``apply_book_split`` rewrites a held position and the persisted targets
for a symbol in post-split units before the split's execution session is stepped, mirroring
``sim.apply_split`` (exact-fraction ratio, floored shares, cash in lieu, floor-to-zero forced close).

Pure: no clock, no I/O, no randomness. Floats are refused at every boundary.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_DOWN, ROUND_FLOOR, Decimal
from fractions import Fraction
from types import MappingProxyType
from typing import Literal

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim.model import q
from seer_engine.sim.rules import OPEN_LIMIT_BAND, RESIZE_BAND, SHARE_QUANTUM, TradeRules
from seer_engine.sim.split_adjust import _q_exact, _rescale_price, _split_ratio

WEIGHT_QUANTUM = Decimal("0.000001")

ExitReason = Literal["signal", "time", "gap", "tp", "sl", "forced"]
FillReason = Literal["entry", "add", "trim", "signal", "time", "gap", "tp", "sl", "forced"]
RejectReason = Literal["no_slot", "too_small", "unfilled", "no_bar", "cash"]

_ONE = Decimal(1)
_ZERO = Decimal(0)
_NO_DIVIDENDS: Mapping[str, Decimal] = MappingProxyType({})


# --------------------------------------------------------------------------- validation


def _decimal(name: str, x: object) -> Decimal:
    if not isinstance(x, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(x).__name__}")
    if not x.is_finite():
        raise ValueError(f"{name} must be finite, got {x!r}")
    return x


def _price(name: str, x: object) -> Decimal:
    """``x`` as a positive 4-dp Decimal (half-up); a float or other type is a TypeError."""
    v = q(_decimal(name, x))
    if v <= 0:
        raise ValueError(f"{name} must be > 0, got {x!r}")
    return v


def _symbol(name: str, x: object) -> str:
    if not isinstance(x, str):
        raise TypeError(f"{name} must be a str, got {type(x).__name__}")
    if not x:
        raise ValueError(f"{name} must be non-empty")
    return x


def _date(name: str, x: object) -> date:
    if isinstance(x, datetime) or not isinstance(x, date):
        raise TypeError(f"{name} must be a date, got {type(x).__name__}")
    return x


def _int(name: str, x: object) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{name} must be an int, got {type(x).__name__}")
    return x


# --------------------------------------------------------------------------- weights


def to_weight(x: float | Decimal) -> Decimal:
    """``x`` quantized DOWN to ``WEIGHT_QUANTUM``. Floats go through their shortest repr.

    ValueError when the result is not > 0 (or ``x`` is not finite); TypeError for a bool or a
    non-numeric value. An int is accepted.
    """
    if isinstance(x, bool):
        raise TypeError("bool is not a weight")
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError(f"weight must be finite, got {x!r}")
        d = Decimal(repr(x))
    elif isinstance(x, int):
        d = Decimal(x)
    elif isinstance(x, Decimal):
        if not x.is_finite():
            raise ValueError(f"weight must be finite, got {x!r}")
        d = x
    else:
        raise TypeError(f"weight must be a float or Decimal, got {type(x).__name__}")
    w = d.quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)
    if w <= 0:
        raise ValueError(f"weight {x!r} is not > 0 at {WEIGHT_QUANTUM}")
    return w


def equal_weight(n: int) -> Decimal:
    """``to_weight(1 / n)``: the weight of one of ``n`` equal slots."""
    if _int("n", n) < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    return to_weight(_ONE / n)


# --------------------------------------------------------------------------- values


@dataclass(frozen=True, slots=True)
class Target:
    """One instrument the strategy wants held after the next session's open, in rank order.

    ``weight`` in (0, 1], a multiple of ``WEIGHT_QUANTUM``. Prices are positive Decimals,
    quantized to 4 dp half-up (like ``sim.Pick``). ``stop`` must be below and ``take`` above the
    reference price (``limit``, or ``last`` when there is no limit). A float is a TypeError.
    """

    symbol: str
    weight: Decimal
    last: Decimal
    limit: Decimal | None = None
    stop: Decimal | None = None
    take: Decimal | None = None

    def __post_init__(self) -> None:
        _symbol("symbol", self.symbol)
        w = _decimal("weight", self.weight)
        if not (0 < w <= 1):
            raise ValueError(f"{self.symbol}: weight must be in (0, 1], got {w}")
        if w.quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN) != w:
            raise ValueError(f"{self.symbol}: weight {w} is not a multiple of {WEIGHT_QUANTUM}")
        object.__setattr__(self, "last", _price("last", self.last))
        for name in ("limit", "stop", "take"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _price(name, value))
        ref = self.limit if self.limit is not None else self.last
        if self.stop is not None and not self.stop < ref:
            raise ValueError(f"{self.symbol}: stop {self.stop} must be below {ref}")
        if self.take is not None and not self.take > ref:
            raise ValueError(f"{self.symbol}: take {self.take} must be above {ref}")


@dataclass(frozen=True, slots=True)
class Position:
    """One holding episode in progress. ``days_held`` counts sessions since the first fill
    (fill session = 1), exactly as ``sim.Order.days_held``."""

    symbol: str
    shares: Decimal
    mark: Decimal
    entry_date: date
    entry_price: Decimal
    days_held: int
    cost_usd: Decimal
    income_usd: Decimal
    stop: Decimal | None
    take: Decimal | None
    exit_pending: bool = False

    def __post_init__(self) -> None:
        _symbol("symbol", self.symbol)
        if _decimal("shares", self.shares) <= 0:
            raise ValueError(f"{self.symbol}: shares must be > 0, got {self.shares}")
        if _decimal("mark", self.mark) <= 0:
            raise ValueError(f"{self.symbol}: mark must be > 0, got {self.mark}")
        _date("entry_date", self.entry_date)
        if _decimal("entry_price", self.entry_price) <= 0:
            raise ValueError(f"{self.symbol}: entry_price must be > 0, got {self.entry_price}")
        if _int("days_held", self.days_held) < 1:
            raise ValueError(f"{self.symbol}: days_held must be >= 1, got {self.days_held}")
        _decimal("cost_usd", self.cost_usd)
        _decimal("income_usd", self.income_usd)
        if self.stop is not None:
            _decimal("stop", self.stop)
        if self.take is not None:
            _decimal("take", self.take)
        if not isinstance(self.exit_pending, bool):
            raise TypeError("exit_pending must be a bool")


@dataclass(frozen=True, slots=True)
class Book:
    """One rule set's state between sessions: real cash, the equity at the last snapshot
    (initial cash before the first session), and the open positions sorted by symbol."""

    cash: Decimal
    equity: Decimal
    positions: tuple[Position, ...] = ()
    last_session: date | None = None

    def __post_init__(self) -> None:
        _decimal("cash", self.cash)
        _decimal("equity", self.equity)
        if not isinstance(self.positions, tuple):
            raise TypeError("positions must be a tuple")
        prev = ""
        for p in self.positions:
            if not isinstance(p, Position):
                raise TypeError(f"positions must hold Position values, got {type(p).__name__}")
            if p.symbol <= prev:
                raise ValueError("positions must be sorted by symbol, one per symbol")
            prev = p.symbol
        if self.last_session is not None:
            _date("last_session", self.last_session)

    def held(self) -> frozenset[str]:
        """Every symbol with an open position."""
        return frozenset(p.symbol for p in self.positions)

    def position(self, symbol: str) -> Position | None:
        """The open position in ``symbol``, or None."""
        for p in self.positions:
            if p.symbol == symbol:
                return p
        return None


@dataclass(frozen=True, slots=True)
class Fill:
    session_date: date
    symbol: str
    side: Literal["buy", "sell"]
    shares: Decimal
    price: Decimal
    cash_usd: Decimal
    cost_usd: Decimal
    reason: FillReason


@dataclass(frozen=True, slots=True)
class Trade:
    """One closed holding episode: shares went 0 -> > 0 -> 0."""

    symbol: str
    entry_date: date
    exit_date: date
    entry_price: Decimal
    exit_price: Decimal
    days_held: int
    cost_usd: Decimal
    income_usd: Decimal
    pnl_usd: Decimal
    exit_reason: ExitReason
    idle: bool


@dataclass(frozen=True, slots=True)
class BookSnapshot:
    date: date
    cash_usd: Decimal
    equity_usd: Decimal
    invested_usd: Decimal


@dataclass(frozen=True, slots=True)
class BookStep:
    book: Book
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    dividends: tuple[tuple[str, Decimal], ...]
    rejected: tuple[tuple[str, RejectReason], ...]
    snapshot: BookSnapshot


@dataclass(frozen=True, slots=True)
class BookSplit:
    """What ``apply_book_split`` did to one symbol on its execution session.

    ``book``: the book in post-split units (``last_session`` unchanged). ``targets``: the
    targets passed in with the symbol's prices rescaled (None when None was passed).
    ``in_lieu``: cash paid for the fractional remainder (the whole payout on a floor-to-zero),
    already in ``book.cash`` and in the position's ``income_usd``. ``trade``/``fills``: the
    forced close when the position floored to zero shares, else None / ().
    """

    book: Book
    targets: tuple[Target, ...] | None
    in_lieu: Decimal
    trade: Trade | None
    fills: tuple[Fill, ...]


def new_book(cash_usd: Decimal) -> Book:
    """An empty book with ``cash = equity = q(cash_usd)``, which must be > 0."""
    cash = q(_decimal("cash_usd", cash_usd))
    if cash <= 0:
        raise ValueError(f"cash_usd must be > 0, got {cash_usd}")
    return Book(cash=cash, equity=cash)


# --------------------------------------------------------------------------- money


def _buy_cash(price: Decimal, shares: Decimal, rules: TradeRules) -> Decimal:
    return q(price * shares * (_ONE + rules.cost_rate))


def _sell_cash(price: Decimal, shares: Decimal, rules: TradeRules) -> Decimal:
    return q(price * shares * (_ONE - rules.cost_rate))


def _fee(price: Decimal, shares: Decimal, rules: TradeRules) -> Decimal:
    return q(price * shares * rules.cost_rate)


def _shares_for(budget: Decimal, price: Decimal, rules: TradeRules) -> Decimal:
    """The most shares whose unrounded buy cash ``price × n × (1 + c)`` fits ``budget``:
    whole shares (``sim.sizing._whole_shares``, step-back loop included) or, with
    ``rules.fractional``, multiples of ``SHARE_QUANTUM``. 0 when nothing fits."""
    if budget <= 0:
        return _ZERO
    unit = price * (_ONE + rules.cost_rate)
    if rules.fractional:
        shares = (budget / unit).quantize(SHARE_QUANTUM, rounding=ROUND_FLOOR)
        while shares > 0 and unit * shares > budget:
            shares -= SHARE_QUANTUM
    else:
        shares = Decimal(int((budget / unit).to_integral_value(rounding=ROUND_FLOOR)))
        while shares > 0 and unit * shares > budget:
            shares -= 1
    return shares if shares > 0 else _ZERO


def _desired_shares(equity: Decimal, weight: Decimal, last: Decimal, rules: TradeRules) -> Decimal:
    """Shares a target weight is worth at ``last``: ``_shares_for(q(equity × weight), last)``."""
    return _shares_for(q(equity * weight), last, rules)


def _sizing_price(t: Target, rules: TradeRules) -> Decimal:
    """The buy limit (and sizing price): ``t.limit`` under entry "limit" when the target has
    one; otherwise ``q(t.last × (1 + OPEN_LIMIT_BAND))`` ("open_limit", the sizing price of
    "open", and the fallback for a limit-entry target with no limit price: plan index D-B)."""
    if rules.entry == "limit" and t.limit is not None:
        return t.limit
    return q(t.last * (_ONE + OPEN_LIMIT_BAND))


def _check_bar(symbol: str, bar: object, session: date) -> Bar:
    if not isinstance(bar, Bar):
        raise TypeError(f"bars[{symbol!r}] must be a Bar, got {type(bar).__name__}")
    if bar.symbol != symbol:
        raise ValueError(f"bars[{symbol!r}] holds a bar for {bar.symbol!r}")
    if bar.date != session:
        raise ValueError(f"bars[{symbol!r}] is dated {bar.date}, expected {session}")
    for name in ("open", "high", "low", "close"):
        value = getattr(bar, name)
        if not isinstance(value, Decimal):
            raise TypeError(f"{symbol} {name} must be a Decimal, got {type(value).__name__}")
        if not value.is_finite() or value <= 0:
            raise ValueError(f"{symbol} {name} must be a finite price > 0, got {value}")
    return bar


def _close_out(
    p: Position, when: date, price: Decimal, reason: ExitReason, days_held: int, rules: TradeRules, fill_reason: FillReason
) -> tuple[Decimal, Fill, Trade]:
    """Sell all of ``p`` at ``price``: (proceeds, the sell fill, the closed episode)."""
    exit_price = q(price)
    proceeds = _sell_cash(exit_price, p.shares, rules)
    fill = Fill(
        session_date=when,
        symbol=p.symbol,
        side="sell",
        shares=p.shares,
        price=exit_price,
        cash_usd=proceeds,
        cost_usd=_fee(exit_price, p.shares, rules),
        reason=fill_reason,
    )
    income = p.income_usd + proceeds
    trade = Trade(
        symbol=p.symbol,
        entry_date=p.entry_date,
        exit_date=when,
        entry_price=p.entry_price,
        exit_price=exit_price,
        days_held=days_held,
        cost_usd=p.cost_usd,
        income_usd=income,
        pnl_usd=income - p.cost_usd,
        exit_reason=reason,
        idle=p.symbol == rules.idle_symbol,
    )
    return proceeds, fill, trade


def _valuation(cash: Decimal, positions: Iterable[Position], idle_symbol: str | None) -> tuple[Decimal, Decimal]:
    """(equity, invested): q(cash + Σ shares × mark) and q(Σ shares × mark) over non-idle."""
    total = cash
    invested = _ZERO
    for p in positions:
        value = p.shares * p.mark
        total += value
        if p.symbol != idle_symbol:
            invested += value
    return q(total), q(invested)


def _check_targets(targets: object, rules: TradeRules, idle_symbol_ok: bool) -> tuple[Target, ...] | None:
    if targets is None:
        return None
    if not isinstance(targets, tuple):
        raise TypeError(f"targets must be a tuple or None, got {type(targets).__name__}")
    seen: set[str] = set()
    total = _ZERO
    for t in targets:
        if not isinstance(t, Target):
            raise TypeError(f"targets must hold Target values, got {type(t).__name__}")
        if t.symbol in seen:
            raise ValueError(f"{t.symbol} appears twice in the targets")
        seen.add(t.symbol)
        if t.symbol == rules.idle_symbol and not idle_symbol_ok:
            raise ValueError(
                f"{t.symbol} is the idle instrument; only a caller that appended the idle target "
                f"(idle_symbol_ok=True) may target it"
            )
        total += t.weight
    if rules.max_positions is None and total > 1:
        # With max_positions set, targets beyond the free slots are rejected "no_slot" (§5 picks
        # are ranked past the slot count on purpose), so only an uncapped book enforces Σ <= 1.
        raise ValueError(f"target weights sum to {total} > 1")
    return targets


# --------------------------------------------------------------------------- one session


def step_book(
    book: Book,
    session: date,
    bars: Mapping[str, Bar],
    targets: tuple[Target, ...] | None,
    rules: TradeRules,
    dividends: Mapping[str, Decimal] = _NO_DIVIDENDS,
    idle_symbol_ok: bool = False,
) -> BookStep:
    """Advance ``book`` through the NYSE session ``session`` (see the module docstring).

    ``targets`` None: not a decision session (no signal exits, entries, trims or adds).
    ``targets`` (): a decision session that wants nothing (every position is signal-exited).
    ``dividends``: {symbol: cash amount per share} for ex-dates ON ``session``.
    ``idle_symbol_ok``: True when the caller appended the ``rules.idle_symbol`` target itself
    (the runner); otherwise a target for the idle instrument is a ValueError.

    TypeError on a wrong type (a float anywhere included). ValueError when ``rules.engine`` is
    not "book", ``session`` is not an NYSE session after ``book.last_session``, the targets
    repeat a symbol, or they weigh more than 1 while ``rules.max_positions`` is None. A new
    entry under entry "limit" with no limit price is bought like "open_limit" (never an error).
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"step_book runs engine 'book' rules only, got {rules.engine!r} ({rules.id})")
    _date("session", session)
    if not dates.is_session(session):
        raise ValueError(f"{session} is not an NYSE session")
    if book.last_session is not None and session <= book.last_session:
        raise ValueError(f"{session} is not after the last session stepped ({book.last_session})")
    if not isinstance(bars, Mapping):
        raise TypeError(f"bars must be a Mapping, got {type(bars).__name__}")
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    if not isinstance(idle_symbol_ok, bool):
        raise TypeError("idle_symbol_ok must be a bool")
    held_at_night = book.held()
    checked = _check_targets(targets, rules, idle_symbol_ok)
    wanted: dict[str, Target] | None = None if checked is None else {t.symbol: t for t in checked}

    day: dict[str, Bar] = {}
    for symbol in sorted(held_at_night | (frozenset(wanted) if wanted is not None else frozenset())):
        b = bars.get(symbol)
        if b is not None:
            day[symbol] = _check_bar(symbol, b, session)

    idle = rules.idle_symbol
    equity = book.equity
    cash = book.cash
    pos: dict[str, Position] = {p.symbol: p for p in book.positions}
    fills_open: list[Fill] = []
    fills_trim: list[Fill] = []
    fills_buy: list[Fill] = []
    fills_intraday: list[Fill] = []
    trades: list[Trade] = []
    credited: list[tuple[str, Decimal]] = []
    rejected: list[tuple[str, RejectReason]] = []

    # The night before S: planned signal exits and trims (they fund buys and free slots).
    night_exits: set[str] = set()
    planned = _ZERO
    for p in book.positions:
        if p.exit_pending or (wanted is not None and p.symbol not in wanted):
            night_exits.add(p.symbol)
            planned += _sell_cash(p.mark, p.shares, rules)
    if wanted is not None:
        for p in book.positions:
            t = wanted.get(p.symbol)
            if t is None or p.symbol in night_exits or not (rules.resize or p.symbol == idle):
                continue
            desired = _desired_shares(equity, t.weight, t.last, rules)
            excess = p.shares - desired
            if excess > 0 and excess * t.last >= RESIZE_BAND * equity:
                planned += _sell_cash(t.last, excess, rules)
    slots_used = sum(1 for p in book.positions if p.symbol != idle and p.symbol not in night_exits)

    # (1) dividends on the ex-date, to positions held at the previous close.
    if rules.dividends:
        for symbol in sorted(dividends):
            amount = _decimal(f"dividends[{symbol!r}]", dividends[symbol])
            if amount <= 0:
                raise ValueError(f"dividends[{symbol!r}] must be > 0, got {amount}")
            p = pos.get(symbol)
            if p is None:
                continue
            credit = q(p.shares * amount)
            cash += credit
            pos[symbol] = replace(p, income_usd=p.income_usd + credit)
            credited.append((symbol, credit))

    # (2) exits at the open: time stop, gap, signal.
    sold_at_open: set[str] = set()
    for symbol in sorted(pos):
        p = pos[symbol]
        b = day.get(symbol)
        dropped = p.exit_pending or (wanted is not None and symbol not in wanted)
        if b is None:
            if dropped and not p.exit_pending:
                pos[symbol] = replace(p, exit_pending=True)
            continue
        reason: ExitReason | None = None
        if rules.time_stop is not None and p.days_held >= rules.time_stop:
            reason = "time"
        elif p.stop is not None and b.open <= p.stop:
            reason = "gap"
        elif p.take is not None and b.open >= p.take:
            reason = "tp"
        elif dropped:
            reason = "signal"
        if reason is None:
            continue
        proceeds, fill, trade = _close_out(p, session, b.open, reason, p.days_held, rules, reason)
        cash += proceeds
        fills_open.append(fill)
        trades.append(trade)
        del pos[symbol]
        sold_at_open.add(symbol)

    # (3) trims at the open (decision sessions; resize rules or the idle instrument).
    if wanted is not None:
        for symbol in sorted(pos):
            p = pos[symbol]
            t = wanted.get(symbol)
            b = day.get(symbol)
            if t is None or b is None or p.exit_pending or not (rules.resize or symbol == idle):
                continue
            desired = _desired_shares(equity, t.weight, t.last, rules)
            excess = p.shares - desired
            if excess <= 0 or excess * t.last < RESIZE_BAND * equity:
                continue
            if desired <= 0:
                proceeds, fill, trade = _close_out(p, session, b.open, "signal", p.days_held, rules, "trim")
                cash += proceeds
                fills_trim.append(fill)
                trades.append(trade)
                del pos[symbol]
                sold_at_open.add(symbol)
                continue
            price = q(b.open)
            proceeds = _sell_cash(price, excess, rules)
            cash += proceeds
            fills_trim.append(
                Fill(session, symbol, "sell", excess, price, proceeds, _fee(price, excess, rules), "trim")
            )
            pos[symbol] = replace(p, shares=desired, income_usd=p.income_usd + proceeds)

    # (4) buys in rank order, the idle instrument last.
    new_today: set[str] = set()
    if checked is not None:
        ordered = [t for t in checked if t.symbol != idle] + [t for t in checked if t.symbol == idle]
        available = book.cash + planned
        committed = _ZERO
        for t in ordered:
            symbol = t.symbol
            if symbol in sold_at_open:
                continue
            is_idle = symbol == idle
            p = pos.get(symbol)
            if p is not None:
                if p.exit_pending or not (rules.resize or is_idle):
                    continue
                if rules.entry == "limit" and t.limit is None:
                    continue
                desired = _desired_shares(equity, t.weight, t.last, rules)
                gap = desired - p.shares
                if gap <= 0 or gap * t.last < RESIZE_BAND * equity:
                    continue
                price = _sizing_price(t, rules)
                shares = min(gap, _shares_for(available - committed, price, rules))
                if shares <= 0:
                    rejected.append((symbol, "too_small"))
                    continue
                fill_reason: FillReason = "add"
            else:
                if not is_idle and rules.max_positions is not None and slots_used >= rules.max_positions:
                    rejected.append((symbol, "no_slot"))
                    continue
                price = _sizing_price(t, rules)
                budget = min(q(equity * t.weight), available - committed)
                shares = _shares_for(budget, price, rules)
                if shares <= 0:
                    rejected.append((symbol, "too_small"))
                    continue
                if not is_idle:
                    slots_used += 1
                fill_reason = "entry"
            committed += _buy_cash(price, shares, rules)

            b = day.get(symbol)
            if b is None:
                rejected.append((symbol, "no_bar"))
                continue
            if rules.entry == "open":
                fill_price = q(b.open)
            elif b.low < price:
                fill_price = q(b.open if b.open < price else price)
            else:
                rejected.append((symbol, "unfilled"))
                continue
            cost = _buy_cash(fill_price, shares, rules)
            if cost > cash:
                shares = _shares_for(cash, fill_price, rules)
                if shares <= 0:
                    rejected.append((symbol, "cash"))
                    continue
                cost = _buy_cash(fill_price, shares, rules)
            cash -= cost
            fills_buy.append(
                Fill(session, symbol, "buy", shares, fill_price, -cost, _fee(fill_price, shares, rules), fill_reason)
            )
            if p is not None:
                pos[symbol] = replace(p, shares=p.shares + shares, cost_usd=p.cost_usd + cost)
            else:
                pos[symbol] = Position(
                    symbol=symbol,
                    shares=shares,
                    mark=b.close,
                    entry_date=session,
                    entry_price=fill_price,
                    days_held=1,
                    cost_usd=cost,
                    income_usd=_ZERO,
                    stop=t.stop,
                    take=t.take,
                )
                new_today.add(symbol)

    # (5) intraday exits of positions held before S (SL before TP).
    for symbol in sorted(pos):
        if symbol in new_today:
            continue
        p = pos[symbol]
        b = day.get(symbol)
        if b is None:
            continue
        if p.stop is not None and b.low <= p.stop:
            hit: tuple[Decimal, ExitReason] | None = (p.stop, "sl")
        elif p.take is not None and b.high > p.take:
            hit = (p.take, "tp")
        else:
            hit = None
        if hit is None:
            continue
        proceeds, fill, trade = _close_out(p, session, hit[0], hit[1], p.days_held + 1, rules, hit[1])
        cash += proceeds
        fills_intraday.append(fill)
        trades.append(trade)
        del pos[symbol]

    # (6) survivors age one session and are marked at the close.
    for symbol in sorted(pos):
        if symbol in new_today:
            continue
        p = pos[symbol]
        b = day.get(symbol)
        pos[symbol] = replace(p, days_held=p.days_held + 1, mark=b.close if b is not None else p.mark)

    # (7) snapshot.
    positions = tuple(pos[s] for s in sorted(pos))
    equity_now, invested = _valuation(cash, positions, idle)
    return BookStep(
        book=Book(cash=cash, equity=equity_now, positions=positions, last_session=session),
        fills=tuple(fills_open + fills_trim + fills_buy + fills_intraday),
        trades=tuple(trades),
        dividends=tuple(credited),
        rejected=tuple(rejected),
        snapshot=BookSnapshot(date=session, cash_usd=cash, equity_usd=equity_now, invested_usd=invested),
    )


def close_book_unpriced(
    book: Book, symbols: Iterable[str], rules: TradeRules
) -> tuple[Book, tuple[Fill, ...], tuple[Trade, ...]]:
    """Force-close positions that will never get another bar (mirrors ``sim.close_unpriced``).

    Each named position is sold at its mark, reason "forced", ``exit_date =
    book.last_session``, ``days_held`` unchanged, in symbol order. ``equity`` is recomputed for
    what stays open. Every symbol must be held; ValueError before any session was stepped.
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
    if isinstance(symbols, str):
        raise TypeError("symbols must be an iterable of symbols, not a single str")
    wanted: set[str] = set()
    for s in symbols:
        if not isinstance(s, str):
            raise TypeError(f"symbol must be a str, got {type(s).__name__}")
        wanted.add(s)
    if not wanted:
        return book, (), ()
    held = book.held()
    for s in sorted(wanted):
        if s not in held:
            raise ValueError(f"{s} is not an open position")
    when = book.last_session
    if when is None:
        raise ValueError("cannot close a position before any session was stepped")
    cash = book.cash
    keep: list[Position] = []
    fills: list[Fill] = []
    trades: list[Trade] = []
    for p in book.positions:
        if p.symbol not in wanted:
            keep.append(p)
            continue
        proceeds, fill, trade = _close_out(p, when, p.mark, "forced", p.days_held, rules, "forced")
        cash += proceeds
        fills.append(fill)
        trades.append(trade)
    positions = tuple(keep)
    equity, _ = _valuation(cash, positions, rules.idle_symbol)
    return Book(cash=cash, equity=equity, positions=positions, last_session=when), tuple(fills), tuple(trades)


# --------------------------------------------------------------------------- splits

_SHARE_QUANTA_PER_UNIT = Fraction(1) / Fraction(SHARE_QUANTUM)  # 10_000


def _split_position_shares(shares: Decimal, ratio: Fraction, fractional: bool) -> tuple[Decimal, Fraction]:
    """``shares × ratio`` floored to whole shares (or to ``SHARE_QUANTUM`` when ``fractional``),
    and the exact remainder in post-split shares."""
    total = Fraction(shares) * ratio
    if fractional:
        scaled = total * _SHARE_QUANTA_PER_UNIT
        kept = Decimal(scaled.numerator // scaled.denominator) * SHARE_QUANTUM
    else:
        kept = Decimal(total.numerator // total.denominator)
    return kept, total - Fraction(kept)


def _rescale_optional(price: Decimal | None, ratio: Fraction) -> Decimal | None:
    return None if price is None else _rescale_price(price, ratio)


def _rescale_target(t: Target, ratio: Fraction) -> Target:
    """``t`` in post-split units, weight unchanged. ValueError (from ``Target``) when 4 dp cannot
    hold a rescaled price or the rescaled stop/take no longer bracket the reference price."""
    return Target(
        symbol=t.symbol,
        weight=t.weight,
        last=_rescale_price(t.last, ratio),
        limit=_rescale_optional(t.limit, ratio),
        stop=_rescale_optional(t.stop, ratio),
        take=_rescale_optional(t.take, ratio),
    )


def apply_book_split(
    book: Book,
    symbol: str,
    factor: Decimal,
    session: date,
    rules: TradeRules,
    targets: tuple[Target, ...] | None = None,
) -> BookSplit:
    """Rewrite ``symbol``'s position (and its targets) in post-split units for a split executing
    on ``session`` (mirrors ``sim.apply_split`` for the book engine).

    ``factor`` is ``split_to / split_from`` (``seer_engine.splits.Split.factor``), read as an
    exact fraction ``r``. The position's shares become ``floor(shares × r)`` (whole shares, or
    multiples of ``SHARE_QUANTUM`` under ``rules.fractional``); mark, entry price, stop and take
    become ``q(p / r)``; the remainder is paid as cash in lieu ``q(remainder × new mark)``, with
    no cost, into ``cash`` and the position's ``income_usd``. A position that floors to 0 shares
    is closed: a "forced" ``Trade`` and sell ``Fill`` dated ``session`` at the old mark, whose
    income includes the in-lieu cash (fill ``cash_usd`` = the in-lieu cash, ``cost_usd`` 0). The
    book's equity is recomputed; ``last_session`` is unchanged. Each target for ``symbol`` gets
    last, limit, stop and take rescaled, weight unchanged; other targets are kept as they are.
    Nothing references ``symbol``: the book and targets come back as the same objects.

    Call it after ``last_session``'s step and before stepping ``session``, once per applied split.
    TypeError on a wrong type (a float factor included); ValueError when ``factor`` is not a split
    ratio, ``rules.engine`` is not "book", ``session`` is not an NYSE session after
    ``book.last_session``, or a rescaled price cannot be held at 4 dp.
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    if not isinstance(symbol, str):
        raise TypeError(f"symbol must be a str, got {type(symbol).__name__}")
    if not symbol:
        raise ValueError("empty symbol")
    ratio = _split_ratio(factor)
    _date("session", session)
    if not dates.is_session(session):
        raise ValueError(f"{session} is not an NYSE session")
    if book.last_session is not None and session <= book.last_session:
        raise ValueError(f"split session {session} must be after the last session stepped ({book.last_session})")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"apply_book_split runs engine 'book' rules only, got {rules.engine!r} ({rules.id})")
    if targets is not None:
        if not isinstance(targets, tuple):
            raise TypeError(f"targets must be a tuple or None, got {type(targets).__name__}")
        for t in targets:
            if not isinstance(t, Target):
                raise TypeError(f"targets must hold Target values, got {type(t).__name__}")

    new_targets = targets
    if targets is not None and any(t.symbol == symbol for t in targets):
        new_targets = tuple(_rescale_target(t, ratio) if t.symbol == symbol else t for t in targets)

    p = book.position(symbol)
    if p is None:
        return BookSplit(book=book, targets=new_targets, in_lieu=_ZERO, trade=None, fills=())

    mark = _rescale_price(p.mark, ratio)
    if mark <= 0:
        raise ValueError(f"{symbol}: a split of ratio {ratio} leaves a mark ({p.mark} -> {mark}) that 4 dp cannot hold")
    shares, remainder = _split_position_shares(p.shares, ratio, rules.fractional)
    in_lieu = _q_exact(remainder * Fraction(mark))
    cash = book.cash + in_lieu
    income = p.income_usd + in_lieu

    trade: Trade | None = None
    fills: tuple[Fill, ...] = ()
    if shares <= 0:
        exit_price = p.mark
        fills = (
            Fill(
                session_date=session,
                symbol=symbol,
                side="sell",
                shares=p.shares,
                price=exit_price,
                cash_usd=in_lieu,
                cost_usd=_ZERO,
                reason="forced",
            ),
        )
        trade = Trade(
            symbol=symbol,
            entry_date=p.entry_date,
            exit_date=session,
            entry_price=p.entry_price,
            exit_price=exit_price,
            days_held=p.days_held,
            cost_usd=p.cost_usd,
            income_usd=income,
            pnl_usd=income - p.cost_usd,
            exit_reason="forced",
            idle=symbol == rules.idle_symbol,
        )
        positions = tuple(x for x in book.positions if x.symbol != symbol)
    else:
        entry_price = _rescale_price(p.entry_price, ratio)
        stop = _rescale_optional(p.stop, ratio)
        take = _rescale_optional(p.take, ratio)
        if (
            entry_price <= 0
            or (stop is not None and stop <= 0)
            or (take is not None and take <= 0)
            or (stop is not None and take is not None and stop >= take)
        ):
            raise ValueError(
                f"{symbol}: a split of ratio {ratio} leaves prices that 4 dp cannot hold "
                f"(mark {mark}, entry {entry_price}, stop {stop}, take {take})"
            )
        adjusted = replace(
            p,
            shares=shares,
            mark=mark,
            entry_price=entry_price,
            stop=stop,
            take=take,
            income_usd=income,
        )
        positions = tuple(adjusted if x.symbol == symbol else x for x in book.positions)
    equity, _ = _valuation(cash, positions, rules.idle_symbol)
    return BookSplit(
        book=Book(cash=cash, equity=equity, positions=positions, last_session=book.last_session),
        targets=new_targets,
        in_lieu=in_lieu,
        trade=trade,
        fills=fills,
    )
