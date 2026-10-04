"""Paper trading's impure edge: load and save every roster strategy's state (plan contract C4).

The pure night cores (``paper.bracket``, ``paper.book``, ``paper.benchmark``) step one session
over values; this module turns those values into rows of the migration-003 tables and back.

- Roster rows: ``strategies`` read; the frozen spec (C2) and ``paper_start`` written once;
  the stored digest checked against the code's.
- ``paper_state``: one row per paper strategy, the state between nights.
- Bracket (strategy A): a ``sim.Portfolio`` is ``paper_state`` plus the strategy's live
  ``orders`` rows (pending and open, by slot); open orders' marks live in ``orders.mark``, in
  the order's own units, and are never rebuilt from ``bars`` (a split would rescale them twice).
- Book (F4, F1): a ``sim.book.Book`` is ``paper_state`` plus ``book_positions``; the pending
  decision is ``book_targets`` for ``paper_state.pending_session`` when ``pending_decision``.
- Benchmark (SPY): ``paper_state`` plus one ``book_positions`` row, stepped by
  ``paper.benchmark``.
- Every engine writes ``equity_snapshots``.
- Strategy C's news check (migration 004): ``news_vetoes`` rows, written once per session by
  ``veto`` and read by ``paper`` / ``paper_check`` as the verdicts C decides and replays from.
- Inputs read at night: dividends by ex-date, splits applied on a session, and the windowed
  ``Market`` (bars since a date, membership, fx).

Every money value, price and share count is written only when the column holds it exactly
(4 dp; weights 6 dp), so a save followed by a load gives back equal values. Rows are returned
in a fixed order: orders by slot, positions by symbol (Python order, not the database
collation), targets by rank, fills by (session, seq), trades by (exit date, insertion).

None of these functions commit or roll back; the caller's ``db.transaction`` decides (the
``paper`` command runs a whole night in one transaction).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from seer_engine import dates
from seer_engine.backtest import io as bio
from seer_engine.backtest.market import Market, Membership
from seer_engine.paper.benchmark import BenchmarkState
from seer_engine.sim.book import WEIGHT_QUANTUM, Book, BookSnapshot, Fill, Position, Target, Trade
from seer_engine.sim.model import Event, Order, Portfolio, Snapshot
from seer_engine.sim.rules import SHARE_QUANTUM
from seer_engine.strategies.c import VERDICTS, allowed_map

BENCHMARK_ID = "SPY"
MARKET_WINDOW_DAYS = 550  # calendar days of bars loaded per night (plan Decisions: "history at night")

PRICE_QUANTUM = Decimal("0.0001")  # numeric(12,4) / numeric(14,4)
DIVIDEND_QUANTUM = Decimal("0.000001")  # dividends.amount numeric(14,6)


class StoreError(RuntimeError):
    """The stored paper state is missing or inconsistent, or a write hit no row."""


class SpecMismatch(StoreError):
    """A frozen strategy's stored digest differs from the code's (a changed strategy needs a new id)."""


# --------------------------------------------------------------------------- validation


def _date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _session(name: str, d: object) -> date:
    _date(name, d)
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _exact(name: str, x: object, quantum: Decimal = PRICE_QUANTUM) -> Decimal:
    """``x`` unchanged when it is a finite Decimal the column holds exactly; else Type/ValueError."""
    if not isinstance(x, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(x).__name__}")
    if not x.is_finite():
        raise ValueError(f"{name} must be finite, got {x!r}")
    if x.quantize(quantum) != x:
        raise ValueError(f"{name} {x} has more decimals than the column holds ({quantum})")
    return x


def _exact_or_none(name: str, x: object, quantum: Decimal = PRICE_QUANTUM) -> Decimal | None:
    return None if x is None else _exact(name, x, quantum)


def _one_row(cur: psycopg.Cursor, what: str) -> None:
    if cur.rowcount != 1:
        raise StoreError(f"{what}: expected to change 1 row, changed {cur.rowcount}")


# --------------------------------------------------------------------------- roster rows


@dataclass(frozen=True)
class StrategyRow:
    """One ``strategies`` row as the paper command needs it."""

    id: str
    name: str
    engine: str | None
    rules_id: str | None
    is_champion: bool
    is_benchmark: bool
    sort: int
    paper_start: date | None
    params: Mapping[str, Any]


_STRATEGY_SQL = (
    "SELECT id, name, engine, rules_id, is_champion, is_benchmark, sort, paper_start, params "
    "FROM strategies"
)


def _strategy(row: tuple) -> StrategyRow:
    sid, name, engine, rules_id, champion, benchmark, sort, paper_start, params = row
    return StrategyRow(
        id=sid,
        name=name,
        engine=engine,
        rules_id=rules_id,
        is_champion=bool(champion),
        is_benchmark=bool(benchmark),
        sort=int(sort),
        paper_start=paper_start,
        params=params if isinstance(params, dict) else {},
    )


def read_strategies(conn: psycopg.Connection) -> tuple[StrategyRow, ...]:
    """Every ``strategies`` row, by (sort, id)."""
    rows = conn.execute(_STRATEGY_SQL + " ORDER BY sort, id").fetchall()
    return tuple(_strategy(r) for r in rows)


def read_strategy(conn: psycopg.Connection, strategy_id: str) -> StrategyRow | None:
    """The ``strategies`` row ``strategy_id``, or None."""
    row = conn.execute(_STRATEGY_SQL + " WHERE id = %s", (strategy_id,)).fetchone()
    return None if row is None else _strategy(row)


def freeze_spec(
    conn: psycopg.Connection,
    strategy_id: str,
    *,
    spec: Mapping[str, Any],
    digest: str,
    backtest_gate: Mapping[str, Any],
    paper_start: date,
) -> None:
    """Write the frozen spec (C2: ``params = {spec, digest, backtest_gate}``) and ``paper_start``.

    Only a row that is not frozen yet (``paper_start IS NULL``) is written; a missing row or an
    already-frozen one is a StoreError (a strategy's spec and start are written exactly once).
    """
    _session("paper_start", paper_start)
    if not isinstance(digest, str) or not digest:
        raise ValueError("digest must be a non-empty str")
    params = {"spec": dict(spec), "digest": digest, "backtest_gate": dict(backtest_gate)}
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE strategies SET params = %s, paper_start = %s WHERE id = %s AND paper_start IS NULL",
            (Jsonb(params), paper_start, strategy_id),
        )
        if cur.rowcount == 1:
            return
    row = read_strategy(conn, strategy_id)
    if row is None:
        raise StoreError(f"no strategies row {strategy_id!r}")
    raise StoreError(
        f"{strategy_id} is already frozen (paper_start {row.paper_start}); a changed strategy needs a new id"
    )


def check_digest(row: StrategyRow, digest: str) -> None:
    """SpecMismatch when ``row`` is frozen (``paper_start`` set) and its stored digest is not ``digest``.

    A row that is not frozen yet passes (there is nothing to compare).
    """
    if row.paper_start is None:
        return
    stored = row.params.get("digest")
    if stored != digest:
        raise SpecMismatch(
            f"{row.id}: stored spec digest {stored!r} differs from the code's {digest!r}; "
            f"a changed strategy needs a new id"
        )


# --------------------------------------------------------------------------- paper_state


@dataclass(frozen=True)
class PaperState:
    """One ``paper_state`` row."""

    strategy_id: str
    last_session: date
    cash_usd: Decimal
    equity_usd: Decimal
    initial_cash_usd: Decimal
    usd_idr: Decimal
    pending_session: date | None
    pending_decision: bool


def read_paper_state(conn: psycopg.Connection, strategy_id: str) -> PaperState | None:
    """The ``paper_state`` row of ``strategy_id``, or None before its day-0 init."""
    row = conn.execute(
        "SELECT strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, "
        "pending_session, pending_decision FROM paper_state WHERE strategy_id = %s",
        (strategy_id,),
    ).fetchone()
    if row is None:
        return None
    return PaperState(
        strategy_id=row[0],
        last_session=row[1],
        cash_usd=row[2],
        equity_usd=row[3],
        initial_cash_usd=row[4],
        usd_idr=row[5],
        pending_session=row[6],
        pending_decision=bool(row[7]),
    )


def _require_state(conn: psycopg.Connection, strategy_id: str) -> PaperState:
    state = read_paper_state(conn, strategy_id)
    if state is None:
        raise StoreError(f"{strategy_id} has no paper_state row; run its day-0 init first")
    return state


def init_paper_state(
    conn: psycopg.Connection,
    strategy_id: str,
    *,
    paper_start: date,
    cash0: Decimal,
    usd_idr: Decimal,
) -> PaperState:
    """Day 0: insert ``paper_state`` (``last_session = prev_session(paper_start)``, cash = equity =
    initial cash = ``cash0``, no pending decision) and the snapshot ``(prev_session(paper_start),
    cash0, cash0)``, exactly the runners' ``snapshots[0]``.

    A second init of the same strategy is a database error (primary key): the caller inits once.
    """
    _session("paper_start", paper_start)
    _exact("cash0", cash0)
    _exact("usd_idr", usd_idr)
    if cash0 <= 0:
        raise ValueError(f"cash0 must be > 0, got {cash0}")
    if usd_idr <= 0:
        raise ValueError(f"usd_idr must be > 0, got {usd_idr}")
    day0 = dates.prev_session(paper_start)
    conn.execute(
        "INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (strategy_id, day0, cash0, cash0, cash0, usd_idr),
    )
    upsert_snapshot(conn, strategy_id, Snapshot(date=day0, cash_usd=cash0, equity_usd=cash0))
    return PaperState(
        strategy_id=strategy_id,
        last_session=day0,
        cash_usd=cash0,
        equity_usd=cash0,
        initial_cash_usd=cash0,
        usd_idr=usd_idr,
        pending_session=None,
        pending_decision=False,
    )


def write_paper_state(
    conn: psycopg.Connection,
    strategy_id: str,
    *,
    cash: Decimal,
    equity: Decimal,
    last_session: date,
) -> None:
    """Record a stepped session: cash, equity and ``last_session``; the pending decision it
    consumed is cleared (``pending_session`` NULL, ``pending_decision`` false)."""
    _exact("cash", cash)
    _exact("equity", equity)
    _session("last_session", last_session)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE paper_state SET cash_usd = %s, equity_usd = %s, last_session = %s, "
            "pending_session = NULL, pending_decision = false, updated_at = now() "
            "WHERE strategy_id = %s",
            (cash, equity, last_session, strategy_id),
        )
        _one_row(cur, f"paper_state {strategy_id}")


def write_pending(conn: psycopg.Connection, strategy_id: str, session: date, *, decision: bool) -> None:
    """Record the decision made tonight for ``session``, which must be
    ``next_session(paper_state.last_session)``. ``decision``: a book strategy's ``session`` is a
    decision session (its targets are in ``book_targets``, possibly none)."""
    _session("session", session)
    state = _require_state(conn, strategy_id)
    expected = dates.next_session(state.last_session)
    if session != expected:
        raise ValueError(
            f"{strategy_id}: a decision for {session}, but the next session after "
            f"{state.last_session} is {expected}"
        )
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE paper_state SET pending_session = %s, pending_decision = %s, updated_at = now() "
            "WHERE strategy_id = %s",
            (session, bool(decision), strategy_id),
        )
        _one_row(cur, f"paper_state {strategy_id}")


# --------------------------------------------------------------------------- equity snapshots


def upsert_snapshot(conn: psycopg.Connection, strategy_id: str, snapshot: Snapshot | BookSnapshot) -> None:
    """Insert or replace the ``equity_snapshots`` row (strategy, ``snapshot.date``)."""
    _date("snapshot.date", snapshot.date)
    conn.execute(
        "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (strategy_id, date) DO UPDATE "
        "SET cash_usd = EXCLUDED.cash_usd, equity_usd = EXCLUDED.equity_usd",
        (
            strategy_id,
            snapshot.date,
            _exact("snapshot.cash_usd", snapshot.cash_usd),
            _exact("snapshot.equity_usd", snapshot.equity_usd),
        ),
    )


def read_snapshots(conn: psycopg.Connection, strategy_id: str) -> tuple[Snapshot, ...]:
    """Every snapshot of ``strategy_id``, by date (day 0 first)."""
    rows = conn.execute(
        "SELECT date, cash_usd, equity_usd FROM equity_snapshots WHERE strategy_id = %s ORDER BY date",
        (strategy_id,),
    ).fetchall()
    return tuple(Snapshot(date=r[0], cash_usd=r[1], equity_usd=r[2]) for r in rows)


def _check_snapshot(snapshot: Snapshot | BookSnapshot, cash: Decimal, equity: Decimal, last: date | None) -> None:
    """The snapshot saved with a state must be that state's own (paper_state.equity is the
    equity at last_session's snapshot)."""
    if last is None:
        raise ValueError("cannot save a state that has not stepped a session")
    if snapshot.date != last or snapshot.cash_usd != cash or snapshot.equity_usd != equity:
        raise ValueError(
            f"snapshot ({snapshot.date}, {snapshot.cash_usd}, {snapshot.equity_usd}) is not the state's "
            f"({last}, {cash}, {equity})"
        )


# --------------------------------------------------------------------------- bracket orders

_ORDER_COLUMNS = (
    "session_date, slot, symbol, last_price, limit_price, tp_price, sl_price, shares, status, "
    "fill_date, fill_price, days_held, exit_date, exit_price, exit_reason, pnl_usd"
)


def _order(row: Sequence[Any]) -> Order:
    return Order(
        session_date=row[0],
        slot=int(row[1]),
        symbol=row[2],
        last_price=row[3],
        limit_price=row[4],
        tp_price=row[5],
        sl_price=row[6],
        shares=int(row[7]),
        status=row[8],
        fill_date=row[9],
        fill_price=row[10],
        days_held=int(row[11]),
        exit_date=row[12],
        exit_price=row[13],
        exit_reason=row[14],
        pnl_usd=row[15],
    )


def _order_params(strategy_id: str, o: Order, mark: Decimal | None) -> dict[str, Any]:
    if not isinstance(o, Order):
        raise TypeError(f"expected an Order, got {type(o).__name__}")
    return {
        "strategy_id": strategy_id,
        "session_date": o.session_date,
        "slot": o.slot,
        "symbol": o.symbol,
        "last_price": _exact("last_price", o.last_price),
        "limit_price": _exact("limit_price", o.limit_price),
        "tp_price": _exact("tp_price", o.tp_price),
        "sl_price": _exact("sl_price", o.sl_price),
        "shares": o.shares,
        "status": o.status,
        "fill_date": o.fill_date,
        "fill_price": _exact_or_none("fill_price", o.fill_price),
        "days_held": o.days_held,
        "exit_date": o.exit_date,
        "exit_price": _exact_or_none("exit_price", o.exit_price),
        "exit_reason": o.exit_reason,
        "pnl_usd": _exact_or_none("pnl_usd", o.pnl_usd),
        "mark": _exact_or_none("mark", mark),
    }


_UPDATE_ORDER_SQL = """
UPDATE orders SET
  slot = %(slot)s, last_price = %(last_price)s, limit_price = %(limit_price)s,
  tp_price = %(tp_price)s, sl_price = %(sl_price)s, shares = %(shares)s, status = %(status)s,
  fill_date = %(fill_date)s, fill_price = %(fill_price)s, days_held = %(days_held)s,
  exit_date = %(exit_date)s, exit_price = %(exit_price)s, exit_reason = %(exit_reason)s,
  pnl_usd = %(pnl_usd)s, mark = %(mark)s
WHERE strategy_id = %(strategy_id)s AND session_date = %(session_date)s AND symbol = %(symbol)s
"""


def _update_order(cur: psycopg.Cursor, strategy_id: str, o: Order, mark: Decimal | None) -> None:
    cur.execute(_UPDATE_ORDER_SQL, _order_params(strategy_id, o, mark))
    _one_row(cur, f"orders ({strategy_id}, {o.session_date}, {o.symbol})")


def load_portfolio(conn: psycopg.Connection, strategy_id: str) -> Portfolio:
    """The bracket ``Portfolio``: ``paper_state`` cash, equity and ``last_session``; the live
    (pending and open) ``orders`` by slot; marks from ``orders.mark`` of the open ones.

    StoreError when there is no ``paper_state`` row or an open order has no mark. Right after
    the day-0 init ``last_session`` is ``prev_session(paper_start)``, not None.
    """
    state = _require_state(conn, strategy_id)
    rows = conn.execute(
        f"SELECT {_ORDER_COLUMNS}, mark FROM orders "
        "WHERE strategy_id = %s AND status IN ('pending', 'open') ORDER BY slot",
        (strategy_id,),
    ).fetchall()
    orders: list[Order] = []
    marks: list[tuple[str, Decimal]] = []
    for row in rows:
        o = _order(row)
        orders.append(o)
        if o.status == "open":
            mark = row[16]
            if mark is None:
                raise StoreError(f"{strategy_id}: open order {o.symbol} ({o.session_date}) has no mark")
            marks.append((o.symbol, mark))
    return Portfolio(
        cash=state.cash_usd,
        equity=state.equity_usd,
        orders=tuple(orders),
        marks=tuple(sorted(marks)),
        last_session=state.last_session,
    )


def insert_pending_orders(
    conn: psycopg.Connection,
    strategy_id: str,
    placed: Iterable[Order],
    companies: Mapping[str, str] | None = None,
) -> int:
    """Insert ``SizingResult.placed`` as pending ``orders`` rows; returns how many.

    ``company`` is ``companies[symbol]`` when given, else the symbol (``orders.company`` is NOT
    NULL and the engine has no company names). ``explanation`` stays NULL (``explain`` fills it).
    Only pending orders are accepted. A row that already exists for (strategy, session, symbol)
    is a database error: the caller decides each session once.
    """
    rows: list[dict[str, Any]] = []
    for o in placed:
        if not isinstance(o, Order):
            raise TypeError(f"placed must hold Order values, got {type(o).__name__}")
        if o.status != "pending":
            raise ValueError(f"only pending orders are inserted, got {o.status} {o.symbol}")
        params = _order_params(strategy_id, o, None)
        params["company"] = (companies or {}).get(o.symbol, o.symbol)
        rows.append(params)
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, "
            "limit_price, tp_price, sl_price, shares, status) VALUES (%(strategy_id)s, "
            "%(session_date)s, %(slot)s, %(symbol)s, %(company)s, %(last_price)s, %(limit_price)s, "
            "%(tp_price)s, %(sl_price)s, %(shares)s, 'pending')",
            rows,
        )
    return len(rows)


def save_bracket_night(
    conn: psycopg.Connection,
    strategy_id: str,
    portfolio: Portfolio,
    events: Sequence[Event],
    snapshot: Snapshot,
) -> None:
    """Persist one settled bracket session (``BracketNight``'s portfolio, events and snapshot).

    1. every event's order (split, fill, expire, exit, forced exit, in the given order) updates
       its ``orders`` row, keyed (strategy, ``order.session_date``, symbol), with ``mark`` NULL;
    2. every live order of ``portfolio`` then updates its row again with its final state and,
       when open, its mark (so ``days_held`` and marks move even without an event);
    3. ``snapshot`` is upserted and ``paper_state`` takes cash, equity and ``last_session``
       (the pending decision it consumed is cleared).

    ``snapshot`` must be the portfolio's own (same date as ``last_session``, same cash and
    equity). An event or live order with no row is a StoreError.
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    _check_snapshot(snapshot, portfolio.cash, portfolio.equity, portfolio.last_session)
    marks = dict(portfolio.marks)
    with conn.cursor() as cur:
        for e in events:
            if not isinstance(e, Event):
                raise TypeError(f"events must hold Event values, got {type(e).__name__}")
            _update_order(cur, strategy_id, e.order, None)
        for o in portfolio.orders:
            _update_order(cur, strategy_id, o, marks.get(o.symbol) if o.status == "open" else None)
    upsert_snapshot(conn, strategy_id, snapshot)
    write_paper_state(
        conn, strategy_id, cash=portfolio.cash, equity=portfolio.equity, last_session=portfolio.last_session
    )


def read_orders(conn: psycopg.Connection, strategy_id: str) -> tuple[tuple[Order, Decimal | None], ...]:
    """Every ``orders`` row of ``strategy_id`` as (Order, mark), by (session_date, slot)."""
    rows = conn.execute(
        f"SELECT {_ORDER_COLUMNS}, mark FROM orders WHERE strategy_id = %s ORDER BY session_date, slot",
        (strategy_id,),
    ).fetchall()
    return tuple((_order(r), r[16]) for r in rows)


# --------------------------------------------------------------------------- book state

_POSITION_COLUMNS = (
    "symbol, shares, mark, entry_date, entry_price, days_held, cost_usd, income_usd, "
    "stop_price, take_price, exit_pending"
)


@dataclass(frozen=True)
class LoadedBook:
    """A book strategy's state between nights.

    ``targets``: the stored decision for ``pending_session`` when it is a decision session (a
    tuple, possibly empty), None when it is not (or nothing was decided). ``idle_added``: the
    targets end with the rules' idle instrument (the runner's residual, ``_with_idle``).
    """

    book: Book
    pending_session: date | None
    targets: tuple[Target, ...] | None
    idle_added: bool


def read_book_positions(conn: psycopg.Connection, strategy_id: str) -> tuple[Position, ...]:
    """The open ``book_positions`` of ``strategy_id``, sorted by symbol (Python order)."""
    rows = conn.execute(
        f"SELECT {_POSITION_COLUMNS} FROM book_positions WHERE strategy_id = %s", (strategy_id,)
    ).fetchall()
    positions = [
        Position(
            symbol=r[0],
            shares=r[1],
            mark=r[2],
            entry_date=r[3],
            entry_price=r[4],
            days_held=int(r[5]),
            cost_usd=r[6],
            income_usd=r[7],
            stop=r[8],
            take=r[9],
            exit_pending=bool(r[10]),
        )
        for r in rows
    ]
    return tuple(sorted(positions, key=lambda p: p.symbol))


def read_book_targets(conn: psycopg.Connection, strategy_id: str, session: date) -> tuple[Target, ...]:
    """The decision stored for ``session``, in rank order (empty when none is stored)."""
    rows = conn.execute(
        "SELECT symbol, weight, last_price, limit_price, stop_price, take_price FROM book_targets "
        "WHERE strategy_id = %s AND session_date = %s ORDER BY rank",
        (strategy_id, session),
    ).fetchall()
    return tuple(
        Target(symbol=r[0], weight=r[1], last=r[2], limit=r[3], stop=r[4], take=r[5]) for r in rows
    )


def load_book(conn: psycopg.Connection, strategy_id: str, *, idle_symbol: str | None = None) -> LoadedBook:
    """The ``Book`` (``paper_state`` + ``book_positions``) and the pending decision.

    ``idle_symbol`` is the rules' ``idle_symbol`` (None for ``MONTHLY_HOLD``); ``idle_added`` is
    True when the stored targets hold it (only ``_with_idle`` can put it there). StoreError when
    there is no ``paper_state`` row, or ``pending_decision`` is set without a ``pending_session``.
    """
    state = _require_state(conn, strategy_id)
    book = Book(
        cash=state.cash_usd,
        equity=state.equity_usd,
        positions=read_book_positions(conn, strategy_id),
        last_session=state.last_session,
    )
    targets: tuple[Target, ...] | None = None
    if state.pending_decision:
        if state.pending_session is None:
            raise StoreError(f"{strategy_id}: pending_decision is set without a pending_session")
        targets = read_book_targets(conn, strategy_id, state.pending_session)
    idle_added = idle_symbol is not None and targets is not None and any(t.symbol == idle_symbol for t in targets)
    return LoadedBook(book=book, pending_session=state.pending_session, targets=targets, idle_added=idle_added)


def _position_params(strategy_id: str, p: Position) -> tuple[Any, ...]:
    if not isinstance(p, Position):
        raise TypeError(f"positions must hold Position values, got {type(p).__name__}")
    return (
        strategy_id,
        p.symbol,
        _exact("shares", p.shares, SHARE_QUANTUM),
        _exact("mark", p.mark),
        p.entry_date,
        _exact("entry_price", p.entry_price),
        p.days_held,
        _exact("cost_usd", p.cost_usd),
        _exact("income_usd", p.income_usd),
        _exact_or_none("stop", p.stop),
        _exact_or_none("take", p.take),
        p.exit_pending,
    )


def _replace_positions(cur: psycopg.Cursor, strategy_id: str, positions: Sequence[Position]) -> None:
    cur.execute("DELETE FROM book_positions WHERE strategy_id = %s", (strategy_id,))
    rows = [_position_params(strategy_id, p) for p in positions]
    if rows:
        cur.executemany(
            f"INSERT INTO book_positions (strategy_id, {_POSITION_COLUMNS}) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )


def _insert_fills(cur: psycopg.Cursor, strategy_id: str, fills: Sequence[Fill]) -> None:
    """Fills in the given (sim) order; ``seq`` counts from 1 within each session date."""
    seq: dict[date, int] = {}
    rows: list[tuple[Any, ...]] = []
    for f in fills:
        if not isinstance(f, Fill):
            raise TypeError(f"fills must hold Fill values, got {type(f).__name__}")
        _date("fill.session_date", f.session_date)
        n = seq.get(f.session_date, 0) + 1
        seq[f.session_date] = n
        rows.append(
            (
                strategy_id,
                f.session_date,
                n,
                f.symbol,
                f.side,
                _exact("fill.shares", f.shares, SHARE_QUANTUM),
                _exact("fill.price", f.price),
                _exact("fill.cash_usd", f.cash_usd),
                _exact("fill.cost_usd", f.cost_usd),
                f.reason,
            )
        )
    if rows:
        cur.executemany(
            "INSERT INTO book_fills (strategy_id, session_date, seq, symbol, side, shares, price, "
            "cash_usd, cost_usd, reason) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )


def _insert_trades(cur: psycopg.Cursor, strategy_id: str, trades: Sequence[Trade]) -> None:
    rows: list[tuple[Any, ...]] = []
    for t in trades:
        if not isinstance(t, Trade):
            raise TypeError(f"trades must hold Trade values, got {type(t).__name__}")
        rows.append(
            (
                strategy_id,
                t.symbol,
                t.entry_date,
                t.exit_date,
                _exact("trade.entry_price", t.entry_price),
                _exact("trade.exit_price", t.exit_price),
                t.days_held,
                _exact("trade.cost_usd", t.cost_usd),
                _exact("trade.income_usd", t.income_usd),
                _exact("trade.pnl_usd", t.pnl_usd),
                t.exit_reason,
                t.idle,
            )
        )
    if rows:
        cur.executemany(
            "INSERT INTO book_trades (strategy_id, symbol, entry_date, exit_date, entry_price, "
            "exit_price, days_held, cost_usd, income_usd, pnl_usd, exit_reason, idle) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )


def _save_holdings_night(
    conn: psycopg.Connection,
    strategy_id: str,
    book: Book,
    fills: Sequence[Fill],
    trades: Sequence[Trade],
    snapshot: Snapshot | BookSnapshot,
) -> None:
    _check_snapshot(snapshot, book.cash, book.equity, book.last_session)
    with conn.cursor() as cur:
        _replace_positions(cur, strategy_id, book.positions)
        _insert_fills(cur, strategy_id, fills)
        _insert_trades(cur, strategy_id, trades)
    upsert_snapshot(conn, strategy_id, snapshot)
    write_paper_state(conn, strategy_id, cash=book.cash, equity=book.equity, last_session=book.last_session)


def _rewrite_executed_targets(
    cur: psycopg.Cursor, strategy_id: str, session: date, targets: Sequence[Target]
) -> None:
    """Rewrite the stored decision for ``session`` with the targets as executed (post-split
    units, ``BookNight.targets``): same symbols in the same rank order, so only weight and
    prices change; ``rank`` and ``explanation`` are kept."""
    stored = [
        r[0]
        for r in cur.execute(
            "SELECT symbol FROM book_targets WHERE strategy_id = %s AND session_date = %s ORDER BY rank",
            (strategy_id, session),
        ).fetchall()
    ]
    executed = [t.symbol for t in targets]
    if executed != stored:
        raise StoreError(
            f"{strategy_id} {session}: executed targets {executed} are not the stored decision {stored}"
        )
    for t in targets:
        if not isinstance(t, Target):
            raise TypeError(f"targets must hold Target values, got {type(t).__name__}")
        cur.execute(
            "UPDATE book_targets SET weight = %s, last_price = %s, limit_price = %s, stop_price = %s, "
            "take_price = %s WHERE strategy_id = %s AND session_date = %s AND symbol = %s",
            (
                _exact("weight", t.weight, WEIGHT_QUANTUM),
                _exact("last", t.last),
                _exact_or_none("limit", t.limit),
                _exact_or_none("stop", t.stop),
                _exact_or_none("take", t.take),
                strategy_id,
                session,
                t.symbol,
            ),
        )
        _one_row(cur, f"book_targets ({strategy_id}, {session}, {t.symbol})")


def save_book_night(
    conn: psycopg.Connection,
    strategy_id: str,
    book: Book,
    fills: Sequence[Fill],
    trades: Sequence[Trade],
    snapshot: BookSnapshot,
    *,
    executed_targets: Sequence[Target] | None = None,
) -> None:
    """Persist one settled book session (``BookNight``'s book, fills, trades, snapshot and
    targets).

    ``book_positions`` is replaced by ``book.positions``; ``fills`` are inserted with ``seq``
    1.. per session date in the given order (a second save of the same session is a database
    error); ``trades`` are inserted; ``snapshot`` is upserted; ``paper_state`` takes cash,
    equity and ``last_session`` and the consumed decision is cleared. ``snapshot`` must be the
    book's own. ``executed_targets`` (``BookNight.targets``; None on a non-decision session)
    rewrites the stored decision for ``book.last_session`` in the units it executed in (a split
    on a targeted symbol rescaled its prices).
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    if executed_targets is not None:
        _check_snapshot(snapshot, book.cash, book.equity, book.last_session)
        with conn.cursor() as cur:
            _rewrite_executed_targets(cur, strategy_id, book.last_session, executed_targets)
    _save_holdings_night(conn, strategy_id, book, fills, trades, snapshot)


def save_book_decision(
    conn: psycopg.Connection,
    strategy_id: str,
    session: date,
    targets: Sequence[Target] | None,
) -> None:
    """Record tonight's decision for ``session`` (``next_session(paper_state.last_session)``).

    ``targets`` None: ``session`` is not a decision session (no rows, ``pending_decision``
    false). A sequence (possibly empty, idle target included last when ``_with_idle`` added one):
    the rows for (strategy, ``session``) are replaced by these, ranked 1.. in order, and
    ``pending_decision`` is true. Earlier sessions' rows are kept as the decision record.
    """
    write_pending(conn, strategy_id, session, decision=targets is not None)
    if targets is None:
        return
    rows: list[tuple[Any, ...]] = []
    for rank, t in enumerate(targets, start=1):
        if not isinstance(t, Target):
            raise TypeError(f"targets must hold Target values, got {type(t).__name__}")
        rows.append(
            (
                strategy_id,
                session,
                rank,
                t.symbol,
                _exact("weight", t.weight, WEIGHT_QUANTUM),
                _exact("last", t.last),
                _exact_or_none("limit", t.limit),
                _exact_or_none("stop", t.stop),
                _exact_or_none("take", t.take),
            )
        )
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM book_targets WHERE strategy_id = %s AND session_date = %s", (strategy_id, session)
        )
        if rows:
            cur.executemany(
                "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price, "
                "limit_price, stop_price, take_price) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )


def read_book_fills(conn: psycopg.Connection, strategy_id: str) -> tuple[Fill, ...]:
    """Every ``book_fills`` row of ``strategy_id``, by (session_date, seq): execution order."""
    rows = conn.execute(
        "SELECT session_date, symbol, side, shares, price, cash_usd, cost_usd, reason FROM book_fills "
        "WHERE strategy_id = %s ORDER BY session_date, seq",
        (strategy_id,),
    ).fetchall()
    return tuple(
        Fill(
            session_date=r[0],
            symbol=r[1],
            side=r[2],
            shares=r[3],
            price=r[4],
            cash_usd=r[5],
            cost_usd=r[6],
            reason=r[7],
        )
        for r in rows
    )


def read_book_trades(conn: psycopg.Connection, strategy_id: str) -> tuple[Trade, ...]:
    """Every ``book_trades`` row of ``strategy_id``, by (exit_date, insertion): exit order."""
    rows = conn.execute(
        "SELECT symbol, entry_date, exit_date, entry_price, exit_price, days_held, cost_usd, income_usd, "
        "pnl_usd, exit_reason, idle FROM book_trades WHERE strategy_id = %s ORDER BY exit_date, id",
        (strategy_id,),
    ).fetchall()
    return tuple(
        Trade(
            symbol=r[0],
            entry_date=r[1],
            exit_date=r[2],
            entry_price=r[3],
            exit_price=r[4],
            days_held=int(r[5]),
            cost_usd=r[6],
            income_usd=r[7],
            pnl_usd=r[8],
            exit_reason=r[9],
            idle=bool(r[10]),
        )
        for r in rows
    )


# --------------------------------------------------------------------------- SPY benchmark
#
# paper.benchmark.BenchmarkState (phase 3: start, cash, equity, position, last_session) is
# persisted like a one-position book: paper_state (cash, equity, last_session; no pending
# decision) + at most one book_positions row (``position``, a sim.Position) + book_fills.
# ``start`` is strategies.paper_start.


def load_benchmark(conn: psycopg.Connection, strategy_id: str = BENCHMARK_ID) -> BenchmarkState:
    """The benchmark's state: ``paper_state`` + its ``book_positions`` row (none before the
    first session's buy), ``start`` from ``strategies.paper_start``. StoreError when there is
    no ``paper_state`` row, no ``paper_start`` or more than one position;
    ``BenchmarkState.__post_init__`` validates the rest."""
    state = _require_state(conn, strategy_id)
    row = read_strategy(conn, strategy_id)
    if row is None or row.paper_start is None:
        raise StoreError(f"{strategy_id} has no paper_start; freeze its spec before loading it")
    positions = read_book_positions(conn, strategy_id)
    if len(positions) > 1:
        raise StoreError(f"the benchmark holds one position, found {[p.symbol for p in positions]}")
    return BenchmarkState(
        start=row.paper_start,
        cash=state.cash_usd,
        equity=state.equity_usd,
        position=positions[0] if positions else None,
        last_session=state.last_session,
    )


def save_benchmark_night(
    conn: psycopg.Connection,
    strategy_id: str,
    state: BenchmarkState,
    snapshot: Snapshot,
    fills: Sequence[Fill],
) -> None:
    """Persist one benchmark session (``step_benchmark``'s state, snapshot and fills): the
    holding row replaced (deleted when ``state.position`` is None), fills inserted with ``seq``,
    snapshot upserted, ``paper_state`` updated. ``snapshot`` must be the state's own."""
    if not isinstance(state, BenchmarkState):
        raise TypeError(f"state must be a BenchmarkState, got {type(state).__name__}")
    positions = () if state.position is None else (state.position,)
    book = Book(cash=state.cash, equity=state.equity, positions=positions, last_session=state.last_session)
    _save_holdings_night(conn, strategy_id, book, fills, (), snapshot)


# --------------------------------------------------------------------------- dividends and splits


def dividends_on(
    conn: psycopg.Connection, session: date, symbols: Iterable[str]
) -> dict[str, dict[date, Decimal]]:
    """The dividends of ``symbols`` with ex-date ``session``, as ``book_runner.DividendMap``
    (``{symbol: {session: cash per share}}``, symbols ascending): the ``dividends`` argument
    of ``paper.book.settle_book``. The benchmark's is ``.get("SPY", {}).get(session)``."""
    _date("session", session)
    wanted = sorted(set(symbols))
    if not wanted:
        return {}
    rows = conn.execute(
        "SELECT symbol, amount FROM dividends WHERE ex_date = %s AND symbol = ANY(%s)",
        (session, wanted),
    ).fetchall()
    return {symbol: {session: amount} for symbol, amount in sorted(rows)}


def dividends_between(conn: psycopg.Connection, start: date, end: date) -> dict[str, dict[date, Decimal]]:
    """Every dividend with ``start <= ex_date <= end`` as ``book_runner.DividendMap``
    (``{symbol: {ex_date: amount}}``), symbols and dates ascending."""
    _date("start", start)
    _date("end", end)
    rows = conn.execute(
        "SELECT symbol, ex_date, amount FROM dividends WHERE ex_date BETWEEN %s AND %s",
        (start, end),
    ).fetchall()
    out: dict[str, dict[date, Decimal]] = {}
    for symbol, ex_date, amount in sorted(rows):
        out.setdefault(symbol, {})[ex_date] = amount
    return out


def _factor(split_from: Decimal, split_to: Decimal) -> Decimal:
    """``split_to / split_from``: the same number as ``splits.Split.factor``."""
    return Decimal(split_to) / Decimal(split_from)


def applied_splits_on(conn: psycopg.Connection, session: date) -> tuple[tuple[str, Decimal], ...]:
    """``(symbol, factor)`` for every split executing on ``session`` whose history was rewritten
    (``split_adjustments.applied``), by symbol. Only these move paper state (plan Decisions)."""
    _date("session", session)
    rows = conn.execute(
        "SELECT symbol, split_from, split_to FROM split_adjustments WHERE execution_date = %s AND applied",
        (session,),
    ).fetchall()
    return tuple(sorted((s, _factor(f, t)) for s, f, t in rows))


def applied_splits_between(
    conn: psycopg.Connection, start: date, end: date
) -> tuple[tuple[str, date, Decimal], ...]:
    """``(symbol, execution_date, factor)`` for every applied split with ``start <= execution_date
    <= end``, by (symbol, date): the replay check's "split-affected" input."""
    _date("start", start)
    _date("end", end)
    rows = conn.execute(
        "SELECT symbol, execution_date, split_from, split_to FROM split_adjustments "
        "WHERE execution_date BETWEEN %s AND %s AND applied",
        (start, end),
    ).fetchall()
    return tuple(sorted((s, d, _factor(f, t)) for s, d, f, t in rows))


# --------------------------------------------------------------------------- market window


def market_window_since(data_date: date) -> date:
    """The first bar date the night loads: ``data_date - MARKET_WINDOW_DAYS`` calendar days
    (>= 253-bar lookbacks with margin)."""
    return _date("data_date", data_date) - timedelta(days=MARKET_WINDOW_DAYS)


def load_market_window(conn: psycopg.Connection, since: date) -> Market:
    """A ``Market`` of every bar dated on or after ``since``, every membership interval (both
    indices merged, as ``io.load_market``) and every fx row, read inside the caller's
    transaction (no cache, no commit, no rollback).

    For a symbol whose bars cover the whole window, its ``History`` equals ``io.load_market``'s
    cut to dates ``>= since``. ``backtest.io.LoadError`` when no bar is dated on or after ``since``.
    """
    _date("since", since)
    frame = bio.read_bars_frame(conn, since=since)
    history = bio.histories_from_frame(frame)
    return Market(history=history, membership=Membership(intervals=bio.read_intervals(conn)), fx=bio.read_fx(conn))


# --------------------------------------------------------------------------- news vetoes (strategy C)


@dataclass(frozen=True, slots=True)
class NewsVerdict:
    """One ``news_vetoes`` row: the news check of one candidate for one session (migration 004).

    ``headlines`` are the lean items the LLM saw, newest first: ``{"id": int, "datetime":
    "YYYY-MM-DDTHH:MM:SSZ", "source": str, "headline": str}`` (no summaries). ``decided_at`` is
    the ``veto`` run's start, tz-aware: the news cutoff.
    """

    rank: int
    symbol: str
    verdict: str  # one of strategies.c.VERDICTS
    reason: str
    model: str | None
    prompt_version: str
    headlines: tuple[Mapping[str, Any], ...]
    earnings_date: date | None
    decided_at: datetime


_VETO_COLUMNS = "rank, symbol, verdict, reason, model, prompt_version, headlines, earnings_date, decided_at"


def _check_verdicts(verdicts: Sequence[NewsVerdict]) -> None:
    """TypeError/ValueError unless ``verdicts`` is a complete, well-formed night for one session."""
    for v in verdicts:
        if not isinstance(v, NewsVerdict):
            raise TypeError(f"verdicts must be NewsVerdict, got {type(v).__name__}")
        if isinstance(v.rank, bool) or not isinstance(v.rank, int):
            raise TypeError(f"rank must be an int, got {type(v.rank).__name__}")
        if not isinstance(v.symbol, str) or not v.symbol:
            raise ValueError(f"rank {v.rank}: symbol must be a non-empty str")
        if v.verdict not in VERDICTS:
            raise ValueError(f"{v.symbol}: verdict {v.verdict!r} is not one of {VERDICTS}")
        if not isinstance(v.reason, str):
            raise TypeError(f"{v.symbol}: reason must be a str, got {type(v.reason).__name__}")
        if v.model is not None and not isinstance(v.model, str):
            raise TypeError(f"{v.symbol}: model must be a str or None, got {type(v.model).__name__}")
        if not isinstance(v.prompt_version, str) or not v.prompt_version:
            raise ValueError(f"{v.symbol}: prompt_version must be a non-empty str")
        if not all(isinstance(h, Mapping) for h in v.headlines):
            raise TypeError(f"{v.symbol}: every headline must be a mapping")
        if v.earnings_date is not None:
            _date(f"{v.symbol}: earnings_date", v.earnings_date)
        if not isinstance(v.decided_at, datetime) or v.decided_at.utcoffset() is None:
            raise ValueError(f"{v.symbol}: decided_at must be a tz-aware datetime")
    ranks = sorted(v.rank for v in verdicts)
    if ranks != list(range(1, len(verdicts) + 1)):
        raise ValueError(f"ranks must be 1..{len(verdicts)} with no gap or repeat, got {ranks}")
    symbols = [v.symbol for v in verdicts]
    if len(set(symbols)) != len(symbols):
        raise ValueError(f"symbols must be unique, got {symbols}")


def has_vetoes(conn: psycopg.Connection, strategy_id: str, session: date) -> bool:
    """True when ``news_vetoes`` holds any row for (``strategy_id``, ``session``): the news
    check for that session already ran."""
    _date("session", session)
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM news_vetoes WHERE strategy_id = %s AND session_date = %s)",
        (strategy_id, session),
    ).fetchone()
    return bool(row[0])


def write_vetoes(
    conn: psycopg.Connection, strategy_id: str, session: date, verdicts: Sequence[NewsVerdict]
) -> int:
    """Insert one ``news_vetoes`` row per verdict for ``session``; returns the rows written.

    Plain INSERTs: a row already stored for (strategy, session, symbol) or (strategy, session,
    rank) is a database error, so the caller checks :func:`has_vetoes` first in the same
    transaction. Validates first and writes nothing on a bad input: ranks 1..n without gaps or
    repeats, unique symbols, ``verdict`` in ``strategies.c.VERDICTS``, tz-aware ``decided_at``.
    An empty ``verdicts`` writes nothing and returns 0.
    """
    _session("session", session)
    verdicts = tuple(verdicts)
    _check_verdicts(verdicts)
    if not verdicts:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO news_vetoes (strategy_id, session_date, {_VETO_COLUMNS}) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    strategy_id,
                    session,
                    v.rank,
                    v.symbol,
                    v.verdict,
                    v.reason,
                    v.model,
                    v.prompt_version,
                    Jsonb([dict(h) for h in v.headlines]),
                    v.earnings_date,
                    v.decided_at,
                )
                for v in sorted(verdicts, key=lambda v: v.rank)
            ],
        )
    return len(verdicts)


def read_vetoes(conn: psycopg.Connection, strategy_id: str, session: date) -> tuple[NewsVerdict, ...]:
    """Every stored verdict of (``strategy_id``, ``session``), by rank; empty when none."""
    _date("session", session)
    rows = conn.execute(
        f"SELECT {_VETO_COLUMNS} FROM news_vetoes WHERE strategy_id = %s AND session_date = %s ORDER BY rank",
        (strategy_id, session),
    ).fetchall()
    return tuple(
        NewsVerdict(
            rank=int(rank),
            symbol=symbol,
            verdict=verdict,
            reason=reason,
            model=model,
            prompt_version=prompt_version,
            headlines=tuple(dict(h) for h in (headlines or [])),
            earnings_date=earnings_date,
            decided_at=decided_at,
        )
        for rank, symbol, verdict, reason, model, prompt_version, headlines, earnings_date, decided_at in rows
    )


def allowed_between(conn: psycopg.Connection, strategy_id: str, start: date, end: date) -> dict[date, frozenset[str]]:
    """``{session: symbols whose stored verdict is "allow"}`` for sessions ``start..end``
    inclusive, via ``strategies.c.allowed_map``. A session with no allowed symbol (all vetoed,
    all failed, or no rows: C sits it out) may be absent, so callers look up with
    ``.get(session, frozenset())``. Empty when ``start > end``."""
    _date("start", start)
    _date("end", end)
    rows = conn.execute(
        "SELECT session_date, symbol, verdict FROM news_vetoes "
        "WHERE strategy_id = %s AND session_date BETWEEN %s AND %s ORDER BY session_date, rank",
        (strategy_id, start, end),
    ).fetchall()
    return allowed_map((d, s, v) for d, s, v in rows)
