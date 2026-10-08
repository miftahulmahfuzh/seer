"""One paper night of the SPY buy-and-hold benchmark: ``backtest.benchmark.buy_and_hold``'s loop
body, stepped one session at a time over persisted state.

Pure: no database, network, clock or randomness. Rules, identical to ``buy_and_hold`` (total
return, dividends reinvested):

- :func:`start_benchmark` holds ``cash0 = q(initial cash)`` and nothing else; its
  :meth:`BenchmarkState.snapshot` is ``Snapshot(prev_session(start), cash0, cash0)``, the
  curve's first point.
- On ``start`` (the first paper session), buy ``_fractional_shares(cash, open)`` shares (multiples
  of ``SHARE_QUANTUM``: Gotrade sells SPY in fractions, and since 2026-10-07 a 10,000,000 IDR book
  cannot afford one whole share) at the open, paying ``fractional_buy_cost``; the remainder sits idle. A dividend with ex-date ``start`` is
  not credited (bought at the open, not a holder at the previous close).
- On every later session with a SPY dividend whose ex-date is that session, credit
  ``q(shares × amount)`` and buy ``_fractional_shares(cash, close)`` more at that close.
- Every session is marked at its close: ``equity = q(cash + shares × close)``. Nothing is sold.

``cost_model`` ("flat", the default, or "gotrade") says what a buy pays and rides in
:class:`BenchmarkState`, so it survives between nights. "flat" is 0.1% of the notional, every
rule above unchanged. "gotrade" is Gotrade's measured schedule (``sim.costs``, fitted to the
owner's receipts): the share count is the most whose rounded cash fits
(``sim.costs.gotrade_shares_for``) and the cash paid is ``q(price x n)`` plus the printed fee,
exactly as ``backtest.benchmark.buy_and_hold(..., cost_model="gotrade")`` prices it. A method
measured against this benchmark and the benchmark itself then pay alike -- without it SPY pays
0.1% while the methods pay Gotrade, and "beats SPY TR" is an asymmetric gate.

The holding is a ``sim.book.Position`` (symbol ``SPY``, shares as a Decimal, no stop or
take), so the store persists it as one ``book_positions`` row; ``cost_usd`` is every buy's cash,
``income_usd`` every dividend credited (plus any split cash in lieu). Each buy is a
``sim.book.Fill``: ``entry`` (the first buy) or ``add`` (a reinvestment), for ``book_fills``.

Splits: ``buy_and_hold`` never sees one (its bars are pre-adjusted), and SPY has never split. A
split executing on a session that ``nightly`` applied to the stored bars is still handled, by
:func:`split_benchmark` (also reachable as ``step_benchmark(..., split=factor)``), with
the book engine's fractional rule: shares become ``shares × ratio`` floored to ``SHARE_QUANTUM``,
the remainder is paid as cash in lieu ``q(remainder × new mark)``
(added to cash and to the position's ``income_usd``), mark and entry price become
``q(price / ratio)`` exactly; a holding that floors to 0 shares is paid out entirely in lieu.
Raising instead would fail the whole paper night (every roster strategy is stepped in one
transaction) for an event that is fully determined and cheap to define.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction

from seer_engine import dates
from seer_engine.backtest.benchmark import _fractional_shares, fractional_buy_cost
from seer_engine.prices import Bar
from seer_engine.sim import COST_RATE, Fill, Position, Snapshot, q
from seer_engine.sim.book import _split_position_shares
from seer_engine.sim.costs import COST_MODELS, CostModel, gotrade_cash
from seer_engine.sim.rules import SHARE_QUANTUM
from seer_engine.sim.split_adjust import _q_exact, _rescale_price, _split_ratio

SPY = "SPY"
_ZERO = Decimal("0.0000")


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _money(name: str, x: object) -> Decimal:
    if not isinstance(x, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(x).__name__}")
    if not x.is_finite():
        raise ValueError(f"{name} must be finite, got {x!r}")
    return x


@dataclass(frozen=True, slots=True)
class BenchmarkState:
    """The SPY benchmark between nights.

    - ``start``: the first paper session (``strategies.paper_start``); the open of ``start`` buys.
    - ``cash``: idle cash, 4 dp, never negative.
    - ``equity``: equity at ``last_session``'s close (``cash0`` before the first session).
    - ``position``: the SPY holding, or None (before ``start``, or when cash never bought a share).
    - ``last_session``: the last session stepped; ``prev_session(start)`` before the first.
    - ``cost_model``: what a buy pays -- "flat" (0.1%) or "gotrade" (``sim.costs``). It is part of
      the state because the benchmark is stepped one night at a time: an entry that pays Gotrade
      must still be paying Gotrade on its thousandth night.

    Persisted as ``paper_state`` (``last_session``, ``cash_usd``, ``equity_usd``) plus one
    ``book_positions`` row from ``position``; ``start`` comes back from ``paper_start``, and
    ``cost_model`` from the entry's frozen spec (``paper.roster.spec``'s ``params``).
    """

    start: date
    cash: Decimal
    equity: Decimal
    position: Position | None
    last_session: date
    cost_model: CostModel = "flat"

    def __post_init__(self) -> None:
        _session("start", self.start)
        if self.cost_model not in COST_MODELS:
            raise ValueError(f"unknown cost_model {self.cost_model!r}; expected one of {COST_MODELS}")
        if _money("cash", self.cash) < 0:
            raise ValueError(f"cash must be >= 0, got {self.cash}")
        _money("equity", self.equity)
        _session("last_session", self.last_session)
        day0 = dates.prev_session(self.start)
        if self.last_session < day0:
            raise ValueError(f"last_session {self.last_session} is before {day0}, the day before start")
        p = self.position
        if p is not None:
            if not isinstance(p, Position):
                raise TypeError(f"position must be a Position, got {type(p).__name__}")
            if p.symbol != SPY:
                raise ValueError(f"the benchmark holds {SPY}, got {p.symbol}")
            if p.shares <= 0 or p.shares.quantize(SHARE_QUANTUM) != p.shares:
                raise ValueError(f"the benchmark holds a positive multiple of {SHARE_QUANTUM} shares, got {p.shares}")
            if p.stop is not None or p.take is not None or p.exit_pending:
                raise ValueError("the benchmark position has no stop, take or pending exit")
            if not self.start <= p.entry_date <= self.last_session:
                raise ValueError(
                    f"position entry {p.entry_date} is outside [{self.start}, {self.last_session}]"
                )
        if self.last_session == day0 and (p is not None or self.cash != self.equity):
            raise ValueError("before the first session the benchmark holds cash only")

    @property
    def shares(self) -> Decimal:
        """SPY shares held (0 without a position)."""
        return Decimal(0) if self.position is None else self.position.shares

    @property
    def income_usd(self) -> Decimal:
        """Cash dividends credited to the current holding (plus split cash in lieu, if any)."""
        return _ZERO if self.position is None else self.position.income_usd

    def snapshot(self) -> Snapshot:
        """``Snapshot(last_session, cash, equity)``: day 0 right after :func:`start_benchmark`."""
        return Snapshot(date=self.last_session, cash_usd=self.cash, equity_usd=self.equity)


def start_benchmark(cash0: Decimal, start: date, *, cost_model: CostModel = "flat") -> BenchmarkState:
    """The benchmark the night before ``start``: ``q(cash0)`` in cash, nothing held, paying
    ``cost_model`` ("flat", 0.1%, or "gotrade", ``sim.costs``) on every buy from then on.

    Raises TypeError when ``cash0`` is not a Decimal and ValueError when it is not > 0,
    ``start`` is not an NYSE session (``buy_and_hold``'s checks), or ``cost_model`` is neither
    "flat" nor "gotrade".
    """
    cash = q(_money("cash0", cash0))
    if cash <= 0:
        raise ValueError(f"cash0 must be > 0, got {cash0}")
    _session("start", start)
    return BenchmarkState(
        start=start,
        cash=cash,
        equity=cash,
        position=None,
        last_session=dates.prev_session(start),
        cost_model=cost_model,
    )


def _check_bar(bar: object, session: date) -> Bar:
    if not isinstance(bar, Bar):
        raise TypeError(f"the SPY bar on {session} must be a Bar, got {type(bar).__name__}")
    if bar.symbol != SPY:
        raise ValueError(f"expected a {SPY} bar, got {bar.symbol}")
    if bar.date != session:
        raise ValueError(f"the SPY bar for {session} is dated {bar.date}")
    for name in ("open", "high", "low", "close"):
        value = getattr(bar, name)
        if not isinstance(value, Decimal):
            raise TypeError(f"SPY {name} must be a Decimal, got {type(value).__name__}")
        if not value.is_finite() or value <= 0:
            raise ValueError(f"SPY {name} on {session} must be a finite price > 0, got {value}")
    return bar


def _buy(price: Decimal, shares: Decimal, cost_model: CostModel) -> tuple[Decimal, Decimal]:
    """``(cash out, fee)`` of one benchmark buy of ``shares`` at ``price``, both priced by
    ``cost_model`` on the same unrounded ``price``, so the recorded fee is the fee inside the
    cash that moved. The fee rule is ``sim.book._fee``'s: ``q(price x n x 0.001)`` under
    "flat", Gotrade's printed fee under "gotrade"."""
    cost = fractional_buy_cost(price, shares, cost_model)
    if cost_model == "gotrade":
        return cost, gotrade_cash("buy", price, shares)[1]
    return cost, q(price * shares * COST_RATE)


def _buy_fill(
    session: date, price: Decimal, shares: Decimal, cost: Decimal, fee: Decimal, reason: str
) -> Fill:
    return Fill(
        session_date=session,
        symbol=SPY,
        side="buy",
        shares=shares,
        price=price,
        cash_usd=-cost,
        cost_usd=fee,
        reason=reason,  # type: ignore[arg-type]
    )


def split_benchmark(state: BenchmarkState, factor: Decimal, session: date) -> tuple[BenchmarkState, Decimal]:
    """Rewrite the SPY holding in post-split units for a split executing on ``session``
    (``factor = split_to / split_from``), before ``session`` is stepped.

    Returns the new state and the cash paid in lieu (``0.0000`` when nothing is held or the
    split leaves no fraction). ``equity`` and ``last_session`` are untouched, as in
    ``sim.apply_split``. Raises ValueError when ``factor`` is not a split ratio, ``session`` is
    not a session after ``state.last_session``, or the rescaled prices cannot be held at 4 dp.
    """
    if not isinstance(state, BenchmarkState):
        raise TypeError(f"state must be a BenchmarkState, got {type(state).__name__}")
    ratio = _split_ratio(factor)
    _session("session", session)
    if session <= state.last_session:
        raise ValueError(f"split session {session} must be after the last stepped session {state.last_session}")
    p = state.position
    if p is None:
        return state, _ZERO
    whole, fraction = _split_position_shares(p.shares, ratio, True)
    new_mark = _rescale_price(p.mark, ratio)
    new_entry = _rescale_price(p.entry_price, ratio)
    if new_mark <= 0 or new_entry <= 0:
        raise ValueError(f"{SPY}: a split of ratio {ratio} leaves prices that 4 dp cannot hold")
    in_lieu = _q_exact(fraction * Fraction(new_mark))
    cash = state.cash + in_lieu
    if whole == 0:
        return replace(state, cash=cash, position=None), in_lieu
    position = replace(
        p,
        shares=whole,
        mark=new_mark,
        entry_price=new_entry,
        income_usd=p.income_usd + in_lieu,
    )
    return replace(state, cash=cash, position=position), in_lieu


def step_benchmark(
    state: BenchmarkState,
    session: date,
    bar: Bar,
    dividend: Decimal | None,
    *,
    split: Decimal | None = None,
    deposit: Decimal = _ZERO,
) -> tuple[BenchmarkState, Snapshot, tuple[Fill, ...]]:
    """Step the benchmark through ``session`` (which must be ``next_session(state.last_session)``:
    the benchmark is stepped on every session, like ``buy_and_hold``).

    ``bar`` is SPY's bar on ``session``; ``dividend`` the SPY cash dividend per share with
    ex-date ``session`` (None when there is none; ignored on ``start``). ``split`` is the factor
    of a SPY split executing on ``session`` that was applied to the stored bars (None when there
    is none); it is applied first (:func:`split_benchmark`).

    ``deposit`` is the owner's contribution landing on ``session`` (017; zero, the default, on
    every session that receives none, and the whole history before the funding plan existed). It
    is **spent at this session's close, through the same buy the dividend path uses**, because
    that is what ``backtest.benchmark.buy_and_hold`` does with it and this stepper exists to
    track that curve session by session: a yardstick that banked the owner's deposits as idle
    cash would drift below the dollar-cost-averaged SPY it is supposed to be, and ``paper check``
    would report a mismatch on every session after the first deposit.

    Returns the new state, the session's snapshot and the buys made (``entry`` at ``start``'s
    open, ``add`` for a reinvestment at the close, or ``entry`` when a reinvestment opens the
    holding).
    """
    if not isinstance(state, BenchmarkState):
        raise TypeError(f"state must be a BenchmarkState, got {type(state).__name__}")
    _session("session", session)
    expected = dates.next_session(state.last_session)
    if session != expected:
        raise ValueError(f"the benchmark steps every session: expected {expected}, got {session}")
    b = _check_bar(bar, session)
    if dividend is not None:
        if _money("dividend", dividend) <= 0:
            raise ValueError(f"dividend must be > 0, got {dividend}")
    if _money("deposit", deposit) < 0:
        raise ValueError(f"deposit must be >= 0, got {deposit}")
    if split is not None:
        state, _ = split_benchmark(state, split, session)

    model = state.cost_model
    cash = state.cash
    pos = state.position
    fills: list[Fill] = []
    if session == state.start:
        shares = _fractional_shares(cash, b.open, model)
        cost, fee = _buy(b.open, shares, model)
        cash -= cost
        if shares > 0:
            price = q(b.open)
            pos = Position(
                symbol=SPY,
                shares=shares,
                mark=b.close,
                entry_date=session,
                entry_price=price,
                days_held=1,
                cost_usd=cost,
                income_usd=_ZERO,
                stop=None,
                take=None,
            )
            fills.append(_buy_fill(session, price, shares, cost, fee, "entry"))
    else:
        if pos is not None:
            pos = replace(pos, days_held=pos.days_held + 1)
        if dividend is not None or deposit > 0:
            held = Decimal(0) if pos is None else pos.shares
            # A dividend is income the holding earned; a deposit is the owner's own money. Both
            # land as cash at this close and are spent through the one buy below, which is how
            # buy_and_hold prices them -- but only the dividend is recorded as income.
            income = _ZERO if dividend is None else q(held * dividend)
            cash += income + deposit
            if pos is not None and income > 0:
                pos = replace(pos, income_usd=pos.income_usd + income)
            more = _fractional_shares(cash, b.close, model)
            if more > 0:
                cost, fee = _buy(b.close, more, model)
                cash -= cost
                price = q(b.close)
                if pos is None:
                    pos = Position(
                        symbol=SPY,
                        shares=more,
                        mark=b.close,
                        entry_date=session,
                        entry_price=price,
                        days_held=1,
                        cost_usd=cost,
                        income_usd=_ZERO,
                        stop=None,
                        take=None,
                    )
                    fills.append(_buy_fill(session, price, more, cost, fee, "entry"))
                else:
                    pos = replace(pos, shares=pos.shares + more, cost_usd=pos.cost_usd + cost)
                    fills.append(_buy_fill(session, price, more, cost, fee, "add"))

    if pos is not None:
        pos = replace(pos, mark=b.close)
    held = Decimal(0) if pos is None else pos.shares
    equity = q(cash + held * b.close)
    new = BenchmarkState(
        start=state.start,
        cash=cash,
        equity=equity,
        position=pos,
        last_session=session,
        cost_model=model,
    )
    return new, Snapshot(date=session, cash_usd=cash, equity_usd=equity), tuple(fills)
