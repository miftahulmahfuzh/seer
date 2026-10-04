# Phase 6: Paper store (load and save state)

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R1, the engine paper step. This phase is the impure half that loads each roster strategy's state before a night and persists it afterwards.
**Depends on:** Phase 1 (migration 003, `paper/__init__.py`, purity glob), Phase 3 (`paper/benchmark.BenchmarkState`), Phase 4 (`BookNight` field semantics; nothing imported)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/paper` (plus one keyword in `engine/src/seer_engine/backtest/io.py`)

---

## Goal

After this phase, every engine's paper state can be loaded from Postgres and saved back exactly. The engines are the bracket `Portfolio`, the book `Book` with its pending targets, and the SPY `BenchmarkState`. "Exactly" covers Decimal money, fractional shares, dates and row order. The nightly inputs can also be read: the roster rows, the frozen spec and its digest, dividends by ex-date, splits applied on a session, and a `Market` built from only the bars since a date. `backtest.io.read_bars_frame` gains a keyword-only `since` whose default keeps every existing call byte-identical. Nothing here commits, so phase 7 can run a whole night in one transaction.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.

**Creates:** `seer_engine.paper.store` (`engine/src/seer_engine/paper/store.py`).

Module-level values and errors:
- Constants: `BENCHMARK_ID = "SPY"`, `MARKET_WINDOW_DAYS = 550`, `PRICE_QUANTUM`, `DIVIDEND_QUANTUM`.
- `StoreError(RuntimeError)` and its subclass `SpecMismatch(StoreError)`.

Roster rows:
- `StrategyRow` (frozen dataclass): `id`, `name`, `engine`, `rules_id`, `is_champion`, `is_benchmark`, `sort`, `paper_start`, `params`.
- `read_strategies(conn) -> tuple[StrategyRow, ...]`
- `read_strategy(conn, strategy_id) -> StrategyRow | None`
- `freeze_spec(conn, strategy_id, *, spec, digest, backtest_gate, paper_start) -> None`
- `check_digest(row, digest) -> None`, which raises `SpecMismatch`.

`paper_state` and snapshots:
- `PaperState` (frozen dataclass): `strategy_id`, `last_session`, `cash_usd`, `equity_usd`, `initial_cash_usd`, `usd_idr`, `pending_session`, `pending_decision`.
- `read_paper_state(conn, sid) -> PaperState | None`
- `init_paper_state(conn, sid, *, paper_start, cash0, usd_idr) -> PaperState`. This is the day-0 init. It writes `paper_state` and the snapshot at `prev_session(paper_start)`.
- `write_paper_state(conn, sid, *, cash, equity, last_session) -> None`. It also clears the pending decision.
- `write_pending(conn, sid, session, *, decision) -> None`. `session` must be `next_session(last_session)`.
- `upsert_snapshot(conn, sid, snapshot: Snapshot | BookSnapshot) -> None`
- `read_snapshots(conn, sid) -> tuple[Snapshot, ...]`

Bracket:
- `load_portfolio(conn, sid) -> Portfolio`
- `insert_pending_orders(conn, sid, placed, companies=None) -> int`
- `save_bracket_night(conn, sid, portfolio, events, snapshot) -> None`
- `read_orders(conn, sid) -> tuple[tuple[Order, Decimal | None], ...]`, each order with its mark.

Book:
- `LoadedBook` (frozen dataclass): `book`, `pending_session`, `targets`, `idle_added`.
- `load_book(conn, sid, *, idle_symbol=None) -> LoadedBook`
- `save_book_night(conn, sid, book, fills, trades, snapshot, *, executed_targets=None) -> None`
- `save_book_decision(conn, sid, session, targets: Sequence[Target] | None) -> None`
- `read_book_positions(conn, sid) -> tuple[Position, ...]`
- `read_book_targets(conn, sid, session) -> tuple[Target, ...]`
- `read_book_fills(conn, sid) -> tuple[Fill, ...]`
- `read_book_trades(conn, sid) -> tuple[Trade, ...]`

Benchmark:
- `load_benchmark(conn, sid="SPY") -> BenchmarkState`
- `save_benchmark_night(conn, sid, state, snapshot, fills) -> None`

Dividends and splits:
- `dividends_on(conn, session, symbols) -> dict[str, dict[date, Decimal]]`, in the `book_runner.DividendMap` shape.
- `dividends_between(conn, start, end) -> dict[str, dict[date, Decimal]]`, also a DividendMap. Both ends are inclusive.
- `applied_splits_on(conn, session) -> tuple[tuple[str, Decimal], ...]`, as `(symbol, factor)`.
- `applied_splits_between(conn, start, end) -> tuple[tuple[str, date, Decimal], ...]`, as `(symbol, execution_date, factor)`.

Market window:
- `market_window_since(data_date) -> date`
- `load_market_window(conn, since) -> Market`

Also created:
- `seer_engine.backtest.io.BARS_COPY_SINCE_SQL` (`engine/src/seer_engine/backtest/io.py`).
- Test file `engine/tests/test_paper_store.py`.

**Signature changes:**
- `backtest.io.read_bars_frame(conn)` becomes `read_bars_frame(conn, *, since: date | None = None)`.
- With `since=None` the function issues exactly `cur.copy(BARS_COPY_SQL)` as before. This is pinned by the existing `test_bars_are_loaded_with_one_streamed_copy`, which still passes, and by a new test.

**Requires (from earlier phases):**
- Phase 1:
  - `db/migrations/003_paper.sql` exactly as contract C1 specifies. The tests rely on these column names: `strategies.engine/rules_id/paper_start`, `orders.mark`, `paper_state.*`, `book_positions.*`, `book_targets.*`, `book_fills.*`, `book_trades.*`, `dividends.*`.
  - The four roster rows `SPY`, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M`, with sort 1..4 and `params = {}`.
  - B and C deleted on a fresh schema.
  - `engine/src/seer_engine/paper/__init__.py` exists.
  - The purity test skips `paper/store.py` by name. `store.py` imports psycopg, so it must be skipped.
- Phase 3: `seer_engine.paper.benchmark.BenchmarkState`, a frozen dataclass with fields `start: date`, `cash: Decimal`, `equity: Decimal`, `position: sim.Position | None`, `last_session: date`, as written in `.workflows/plan/paper-trading-ship/phase-3.md`. Its `__post_init__` validates the state. The store builds it with keywords from `strategies.paper_start` plus `paper_state` plus at most one `book_positions` row.
- Phase 4 (semantics only; the store does not import `paper.book`):
  - `BookNight.fills` order is the `book_fills.seq` order.
  - `BookNight.targets` holds the executed targets in post-split units. The store rewrites the stored decision with them through `save_book_night(..., executed_targets=night.targets)`.

**Leaves alone (owned by others):**
- `commands/*` (phases 7–9), `runs.py` (phase 7) and `.github/workflows/*` (phases 7 and 13).
- `paper/roster.py` and `paper/__init__.py` (phase 1).
- `paper/bracket.py` and `paper/benchmark.py` (phase 3), `paper/book.py` (phase 4) and `paper/replay.py` (phase 8).
- `sim/*` (phase 2), `dividends.py`, `universe.py` and `nightly.py` (phase 5).
- The closed records: `backtest/runner.py`, `book_runner.py`, `benchmark.py` and `registry.py`.
- `db/migrations/*`, `web/*` and docs.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/io.py` | modify (after line 56; replace lines 117–151) | add `BARS_COPY_SINCE_SQL`; `read_bars_frame` gains keyword-only `since` (default path unchanged) |
| `engine/src/seer_engine/paper/store.py` | create (line 1) | the impure store (contract C4), full code below |
| `engine/tests/test_paper_store.py` | create (line 1) | 26 PG tests: round trips, day-0 init, orders by key, targets (empty, None, idle, executed rewrite), benchmark, dividends, splits, windowed market, `read_bars_frame(since=)` |

## Design notes (decisions made in this phase)

- **The API takes pieces, not the night objects.** Bracket and book saves take `(portfolio, events, snapshot)` and `(book, fills, trades, snapshot, executed_targets=)`. Phase 7 unpacks `BracketNight` and `BookNight` into these arguments. The store therefore depends only on `sim` types and on `BenchmarkState`, and the tests drive it with real `sim.step`, `sim.apply_split`, `sim.close_unpriced` and `sim.step_book` output.
- **Settle and decide are separate writes.**
  - Bracket: `save_bracket_night` for session S, then `insert_pending_orders` and `write_pending(S+1, decision=False)`.
  - Book: `save_book_night` for S, then `save_book_decision(S+1, targets | None)`.
  - Settle saves clear `pending_session` and `pending_decision`; the decision write sets them again. The day-0 init night is `init_paper_state` followed by the decision write only.
- **Day-0 `last_session` is `prev_session(paper_start)`, not None.** `paper_state.last_session` is NOT NULL (C1). Phase 3's handoff confirms that `settle_bracket` and `decide_bracket` accept either value. Phase 4's handoff states the same for books, and `BenchmarkState` requires it.
- **Exactness guard.** Every value is checked before it is written: money and prices against 4 dp, shares against `SHARE_QUANTUM` (4 dp), weights against `WEIGHT_QUANTUM` (6 dp). A value the column would round raises `ValueError`. That makes save followed by load provably exact; Postgres numeric rounding never runs silently.
- **Python ordering, not database collation.**
  - Positions are sorted by symbol in Python, because `Book` and `Portfolio.marks` require codepoint order (`"BRK.B" < "BRKB"`), which a locale collation may not give.
  - Orders are sorted by slot, targets by rank, fills by `(session_date, seq)`, and trades by `(exit_date, id)`, which is insertion order and therefore exit order.
- **Bracket order rows are updated by key `(strategy_id, order.session_date, symbol)`.**
  - Each event's order is written in event order: splits, then step exits, fills and expiries, then forced closes.
  - Then every live order of the final portfolio is written again with its mark, because `days_held` and marks move without an event.
  - A key that hits no row is a `StoreError`.
  - Terminal orders get `mark = NULL`. `explanation` and `company` are never touched by an update.
- **`orders.company` is NOT NULL and the engine has no company names.** `insert_pending_orders` takes an optional `companies` mapping and falls back to the symbol. Phase 7 decides whether to pass names (Handoffs).
- **Fills `seq`.** Fills are numbered 1.. per session date, in the order passed. A second save of the same session therefore hits `UNIQUE (strategy_id, session_date, seq)` and fails loudly. Idempotency is phase 7's job; the store guards against a double write.
- **Executed targets.** `save_book_night(..., executed_targets=night.targets)` updates the stored rows for `book.last_session` in place, by `(strategy, session, symbol)`. Weight and the four prices change; rank and `explanation` are kept. The executed symbols in rank order must equal the stored ones, or a `StoreError` is raised. Phase 4's handoff asks for this.
- **Dividends are returned as a `DividendMap`.** `dividends_on` returns `{symbol: {session: amount}}`, which plugs straight into `paper.book.settle_book` (phase 4's argument type). The benchmark's value is `dividends_on(conn, S, ["SPY"]).get("SPY", {}).get(S)`.
- **Split factor.** The factor is `Decimal(split_to) / Decimal(split_from)` in the default 28-digit context, the same number as `splits.Split.factor`. `sim.apply_split` and `apply_book_split` read it as an exact fraction.
- **Windowed market.**
  - Bars come from `read_bars_frame(conn, since=...)`, a COPY with `WHERE date >= %s`; psycopg 3.3 binds COPY parameters client-side, verified against PG 16.
  - Membership comes from `read_intervals`, which merges intervals the same way `load_market` does.
  - All fx rows are read, about 18k rows.
  - Everything is read inside the caller's transaction, with no cache, no `SET TRANSACTION` and no rollback. `read_bars_frame` issues `SET LOCAL datestyle` inside that transaction, which is harmless.
  - `market_window_since(d) = d - 550 days`, per the plan Decisions entry "history at night".
- **Prototype-verified.** This exact `store.py`, the `io.py` change and the test file were run against PG 16, with C1 applied by hand and phase 3's `BenchmarkState` shape stubbed: 26 new tests plus the 15 existing `test_backtest_io.py` tests passed.

## Implementation Steps

### Step 1: `read_bars_frame` gains `since`
**File:** `engine/src/seer_engine/backtest/io.py:53-56` (constant) and `engine/src/seer_engine/backtest/io.py:117-151` (function)
**Change:**
- Insert the new constant immediately after `BARS_COPY_SQL`, which ends at line 56, so it lands before `CACHE_GLOB = "bars-*.pkl"`.
- Replace the whole `read_bars_frame` function, lines 117–151, with the version below.
- No import changes are needed: `date` and `datetime` are already imported at line 20.

**Code (insert after line 56):**
```python
BARS_COPY_SINCE_SQL = (
    "COPY (SELECT symbol, date, open, high, low, close, volume FROM bars "
    "WHERE date >= %s ORDER BY symbol, date) TO STDOUT"
)
```
**Code (replaces lines 117–151):**
```python
def read_bars_frame(conn: psycopg.Connection, *, since: date | None = None) -> pd.DataFrame:
    """Every bar (or, with ``since``, every bar dated on or after it), ordered by (symbol, date),
    via one streamed COPY ... TO STDOUT.

    Columns: symbol (str), date (datetime64), open/high/low/close (float64, correctly
    rounded from the numeric text), volume (int64). ``since`` None (the default) runs
    ``BARS_COPY_SQL`` exactly as before; a date runs ``BARS_COPY_SINCE_SQL`` with it bound.
    """
    if since is not None and (isinstance(since, datetime) or not isinstance(since, date)):
        raise TypeError(f"since must be a date or None, got {type(since).__name__}")
    buf = BytesIO()
    with conn.cursor() as cur:
        cur.execute("SET LOCAL datestyle TO 'ISO, YMD'")
        copy_cm = cur.copy(BARS_COPY_SQL) if since is None else cur.copy(BARS_COPY_SINCE_SQL, (since,))
        with copy_cm as copy:
            for chunk in copy:
                buf.write(chunk)
    if buf.tell() == 0:
        raise LoadError("COPY of bars returned no rows")
    buf.seek(0)
    frame = pd.read_csv(
        buf,
        sep="\t",
        header=None,
        names=list(BAR_COLUMNS),
        dtype={
            "symbol": str,
            "date": str,
            "open": np.float64,
            "high": np.float64,
            "low": np.float64,
            "close": np.float64,
            "volume": np.int64,
        },
        na_filter=False,
        float_precision="round_trip",
        engine="c",
    )
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    return frame
```
**Impact:**
- With `since=None` the call is byte-identical to today: `cur.copy(BARS_COPY_SQL)` with no extra argument. `load_market` and `_bars_frame` call `read_bars_frame(conn)`, so the cache and the existing tests are unaffected.
- A non-date `since` is a `TypeError`.
- A window with no bars raises the existing `LoadError`.

### Step 2: Create the store
**File:** `engine/src/seer_engine/paper/store.py:1` (new file)
**Change:** The whole module below.
**Code:**
```python
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
```
**Impact:** New module only. It imports psycopg, so it must stay out of phase 1's purity glob, which names `store.py` as the exclusion. It imports `seer_engine.paper.benchmark` from phase 3 and `seer_engine.backtest.io`.

### Step 3: Tests on Postgres
**File:** `engine/tests/test_paper_store.py:1` (new file)
**Change:** 26 tests on the `pg` fixture, which applies every migration including 003. They cover:
- the roster rows and the frozen spec;
- the day-0 init, a duplicate init, column-precision refusals and the no-commit guarantee;
- the bracket round trip over five sessions with real `sim` output: placement, fill and expiries, a no-event mark move, a 2-for-1 split on an open order that keeps its key, and a forced close with a replaced snapshot;
- a foreign snapshot, a missing row and a missing mark;
- book decision, night and no-decision states; the empty decision kept apart from no decision; a re-decision and idle derivation;
- the executed-targets rewrite, which keeps `explanation`, and the mismatch refusal;
- fractional shares, fills `seq` across two sessions, trade order, and a duplicate-session save;
- the benchmark round trip, including a session with no fills, and the missing `paper_start` case;
- `dividends_on` and `dividends_between`, and applied-only splits;
- the windowed market equal to `load_market` cut at `since`, and `read_bars_frame`'s exact COPY statements.

**Code:**
```python
"""paper.store on Postgres: exact save -> load round trips for every engine's state, the day-0
init, orders updated by key, book targets (empty decision included), dividends and applied
splits, and the windowed market (plan phase 6, contract C4)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import psycopg
import pytest

from seer_engine import bars, dates, db, fx
from seer_engine.backtest import io as bio
from seer_engine.paper import store
from seer_engine.paper.benchmark import BenchmarkState
from seer_engine.prices import Bar
from seer_engine.sim import (
    MONTHLY_HOLD,
    Book,
    Pick,
    Position,
    Snapshot,
    Target,
    apply_split,
    close_unpriced,
    size_picks,
    step,
    step_book,
)
from seer_engine.sim.book import BookSnapshot, Fill, Trade

D = Decimal
S0, S1, S2, S3, S4, S5 = (
    date(2026, 9, 28),
    date(2026, 9, 29),
    date(2026, 9, 30),
    date(2026, 10, 1),
    date(2026, 10, 2),
    date(2026, 10, 5),
)
CASH0 = D("1250.0000")
RATE = D("16000.0000")
BOOK_ID = "F4-MOM12-N20-TREND"
TIMING_ID = "F1-SPY-SMA200-M"


def bar(symbol: str, d: date, o: str, h: str, low: str, c: str) -> Bar:
    return Bar(symbol, d, D(o), D(h), D(low), D(c), 1_000)


# --------------------------------------------------------------------------- roster rows


def test_read_strategies_returns_the_roster_rows_in_sort_order(pg):
    rows = store.read_strategies(pg)
    assert [r.id for r in rows] == ["SPY", "A", BOOK_ID, TIMING_ID]
    spy = rows[0]
    assert (spy.engine, spy.rules_id, spy.is_champion, spy.is_benchmark) == ("benchmark", None, True, True)
    assert rows[1].engine == "bracket" and rows[1].rules_id == "design-v0"
    assert all(r.paper_start is None and r.params == {} for r in rows)
    assert store.read_strategy(pg, "nope") is None


def test_freeze_spec_writes_params_and_start_once_and_check_digest_compares(pg):
    spec = {"engine": "book", "object": "FACTOR", "params": {"rank": "momentum", "top": "20"}}
    gate = {"passed": False, "note": "dev window only"}
    store.freeze_spec(pg, BOOK_ID, spec=spec, digest="abc123", backtest_gate=gate, paper_start=S1)
    row = store.read_strategy(pg, BOOK_ID)
    assert row.paper_start == S1
    assert row.params == {"spec": spec, "digest": "abc123", "backtest_gate": gate}
    store.check_digest(row, "abc123")
    with pytest.raises(store.SpecMismatch):
        store.check_digest(row, "other")
    store.check_digest(store.read_strategy(pg, "A"), "anything")  # not frozen yet: nothing to compare
    with pytest.raises(store.StoreError, match="already frozen"):
        store.freeze_spec(pg, BOOK_ID, spec=spec, digest="x", backtest_gate=gate, paper_start=S2)
    with pytest.raises(store.StoreError, match="no strategies row"):
        store.freeze_spec(pg, "nope", spec=spec, digest="x", backtest_gate=gate, paper_start=S2)
    with pytest.raises(ValueError, match="not an NYSE session"):
        store.freeze_spec(pg, "A", spec=spec, digest="x", backtest_gate=gate, paper_start=date(2026, 10, 3))


# --------------------------------------------------------------------------- day 0 and paper_state


def test_init_paper_state_writes_day0_state_and_snapshot(pg):
    state = store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    assert state == store.read_paper_state(pg, "A")
    assert state == store.PaperState("A", S0, CASH0, CASH0, CASH0, RATE, None, False)
    assert store.read_snapshots(pg, "A") == (Snapshot(S0, CASH0, CASH0),)
    with pytest.raises(psycopg.errors.UniqueViolation):
        store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)


def test_init_refuses_values_the_columns_cannot_hold(pg):
    with pytest.raises(ValueError, match="more decimals"):
        store.init_paper_state(pg, "A", paper_start=S1, cash0=D("1250.00001"), usd_idr=RATE)
    with pytest.raises(TypeError):
        store.init_paper_state(pg, "A", paper_start=S1, cash0=1250.0, usd_idr=RATE)
    assert store.read_paper_state(pg, "A") is None


def test_load_without_state_is_a_store_error(pg):
    with pytest.raises(store.StoreError, match="no paper_state"):
        store.load_portfolio(pg, "A")
    with pytest.raises(store.StoreError, match="no paper_state"):
        store.load_book(pg, BOOK_ID)
    with pytest.raises(store.StoreError, match="no paper_state"):
        store.load_benchmark(pg)
    with pytest.raises(store.StoreError, match="no paper_state"):
        store.write_pending(pg, "A", S1, decision=False)


def test_write_pending_only_accepts_the_next_session(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    with pytest.raises(ValueError, match="next session"):
        store.write_pending(pg, "A", S2, decision=False)
    store.write_pending(pg, "A", S1, decision=False)
    assert store.read_paper_state(pg, "A").pending_session == S1


def test_upsert_snapshot_replaces_the_row_for_a_date(pg):
    store.upsert_snapshot(pg, "A", Snapshot(S1, D("1"), D("2")))
    store.upsert_snapshot(pg, "A", BookSnapshot(S1, D("3.5"), D("4.25"), D("0")))
    store.upsert_snapshot(pg, "A", Snapshot(S0, D("9"), D("9")))
    assert store.read_snapshots(pg, "A") == (Snapshot(S0, D("9"), D("9")), Snapshot(S1, D("3.5"), D("4.25")))


def test_nothing_is_committed(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    pg.rollback()
    assert store.read_paper_state(pg, "A") is None
    assert store.read_snapshots(pg, "A") == ()


# --------------------------------------------------------------------------- bracket


PICKS = (
    Pick("AAA", D("10"), D("10"), D("11"), D("9.5")),
    Pick("BBB", D("20"), D("20"), D("22"), D("19")),
    Pick("CCC", D("30"), D("30"), D("33"), D("28.5")),
)


def _bracket_day0(conn):
    store.init_paper_state(conn, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    pf = store.load_portfolio(conn, "A")
    sized = size_picks(pf, PICKS, S1)
    assert store.insert_pending_orders(conn, "A", sized.placed, {"AAA": "Triple A Inc"}) == 3
    store.write_pending(conn, "A", S1, decision=False)
    return sized


def test_pending_orders_round_trip_with_company_fallback(pg):
    sized = _bracket_day0(pg)
    assert store.load_portfolio(pg, "A") == sized.portfolio
    companies = dict(pg.execute("SELECT symbol, company FROM orders WHERE strategy_id = 'A'").fetchall())
    assert companies == {"AAA": "Triple A Inc", "BBB": "BBB", "CCC": "CCC"}
    assert store.read_paper_state(pg, "A").pending_session == S1


def test_bracket_nights_update_orders_by_key_with_marks(pg):
    sized = _bracket_day0(pg)
    # S1: AAA fills (low < limit), BBB has no bar, CCC's low never goes below the limit.
    r1 = step(
        sized.portfolio,
        S1,
        {"AAA": bar("AAA", S1, "9.9", "10.4", "9.8", "10.2"), "CCC": bar("CCC", S1, "31", "32", "30", "31")},
    )
    store.save_bracket_night(pg, "A", r1.portfolio, r1.events, r1.snapshot)
    assert store.load_portfolio(pg, "A") == r1.portfolio
    st = store.read_paper_state(pg, "A")
    assert (st.last_session, st.cash_usd, st.equity_usd, st.pending_session) == (
        S1, r1.portfolio.cash, r1.portfolio.equity, None
    )
    by_symbol = {o.symbol: (o, mark) for o, mark in store.read_orders(pg, "A")}
    assert by_symbol["AAA"][0].status == "open" and by_symbol["AAA"][1] == D("10.2")
    assert by_symbol["BBB"][0].status == "expired" and by_symbol["BBB"][1] is None
    assert by_symbol["CCC"][0].status == "expired"

    # S2: no event for AAA, but days_held and the mark still move.
    r2 = step(r1.portfolio, S2, {"AAA": bar("AAA", S2, "10.2", "10.5", "10.0", "10.4")})
    assert r2.events == ()
    store.save_bracket_night(pg, "A", r2.portfolio, r2.events, r2.snapshot)
    assert store.load_portfolio(pg, "A") == r2.portfolio
    aaa, mark = next((o, m) for o, m in store.read_orders(pg, "A") if o.symbol == "AAA")
    assert (aaa.days_held, mark) == (2, D("10.4"))

    # S3: a 2-for-1 split executes, then the session steps; the row keeps its key (S1, AAA).
    split_pf, split_events = apply_split(r2.portfolio, "AAA", D(2), S3)
    r3 = step(split_pf, S3, {"AAA": bar("AAA", S3, "5.2", "5.3", "5.1", "5.25")})
    store.save_bracket_night(pg, "A", r3.portfolio, split_events + r3.events, r3.snapshot)
    assert store.load_portfolio(pg, "A") == r3.portfolio
    aaa, mark = next((o, m) for o, m in store.read_orders(pg, "A") if o.symbol == "AAA")
    assert aaa.session_date == S1 and aaa.shares == 2 * sized.placed[0].shares
    assert aaa.fill_price == D("4.9500") and mark == D("5.25")

    # S4: AAA has no bar and never will: forced close at its mark, snapshot replaced.
    r4 = step(r3.portfolio, S4, {})
    forced_pf, forced = close_unpriced(r4.portfolio, ["AAA"])
    snap = Snapshot(S4, forced_pf.cash, forced_pf.equity)
    store.save_bracket_night(pg, "A", forced_pf, r4.events + forced, snap)
    assert store.load_portfolio(pg, "A") == forced_pf
    aaa, mark = next((o, m) for o, m in store.read_orders(pg, "A") if o.symbol == "AAA")
    assert aaa == forced[0].order and mark is None
    assert store.read_snapshots(pg, "A")[-1] == snap
    assert [s.date for s in store.read_snapshots(pg, "A")] == [S0, S1, S2, S3, S4]


def test_save_bracket_night_refuses_a_foreign_snapshot_or_a_missing_row(pg):
    sized = _bracket_day0(pg)
    r1 = step(sized.portfolio, S1, {"AAA": bar("AAA", S1, "9.9", "10.4", "9.8", "10.2")})
    with pytest.raises(ValueError, match="not the state's"):
        store.save_bracket_night(pg, "A", r1.portfolio, r1.events, Snapshot(S1, CASH0, CASH0))
    pg.execute("DELETE FROM orders WHERE symbol = 'BBB'")
    with pytest.raises(store.StoreError, match="expected to change 1 row"):
        store.save_bracket_night(pg, "A", r1.portfolio, r1.events, r1.snapshot)


def test_open_order_without_mark_is_a_store_error(pg):
    sized = _bracket_day0(pg)
    r1 = step(sized.portfolio, S1, {"AAA": bar("AAA", S1, "9.9", "10.4", "9.8", "10.2")})
    store.save_bracket_night(pg, "A", r1.portfolio, r1.events, r1.snapshot)
    pg.execute("UPDATE orders SET mark = NULL WHERE symbol = 'AAA'")
    with pytest.raises(store.StoreError, match="has no mark"):
        store.load_portfolio(pg, "A")


# --------------------------------------------------------------------------- book


TARGETS = (
    Target("AAA", D("0.500000"), D("10")),
    Target("BBB", D("0.250000"), D("20"), limit=D("20.4"), stop=D("18"), take=D("24")),
)


def test_book_decision_and_night_round_trip(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, BOOK_ID, S3, TARGETS)
    loaded = store.load_book(pg, BOOK_ID)
    assert loaded.targets == TARGETS and loaded.pending_session == S3 and not loaded.idle_added
    assert loaded.book.cash == CASH0 and loaded.book.positions == () and loaded.book.last_session == S2

    stepped = step_book(
        loaded.book,
        S3,
        {"AAA": bar("AAA", S3, "10", "10.5", "9.9", "10.3"), "BBB": bar("BBB", S3, "20", "20.5", "19.9", "20.2")},
        loaded.targets,
        MONTHLY_HOLD,
    )
    assert len(stepped.fills) == 2
    store.save_book_night(
        pg, BOOK_ID, stepped.book, stepped.fills, stepped.trades, stepped.snapshot, executed_targets=loaded.targets
    )
    after = store.load_book(pg, BOOK_ID)
    assert after.book == stepped.book
    assert after.targets is None and after.pending_session is None
    assert store.read_book_fills(pg, BOOK_ID) == stepped.fills
    assert store.read_book_targets(pg, BOOK_ID, S3) == TARGETS  # kept as the decision record

    store.save_book_decision(pg, BOOK_ID, S4, None)  # not a decision session
    st = store.read_paper_state(pg, BOOK_ID)
    assert (st.pending_session, st.pending_decision) == (S4, False)
    assert store.load_book(pg, BOOK_ID).targets is None


def test_empty_decision_is_kept_apart_from_no_decision(pg):
    store.init_paper_state(pg, TIMING_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, TIMING_ID, S3, ())
    loaded = store.load_book(pg, TIMING_ID)
    assert loaded.targets == () and loaded.pending_session == S3
    assert store.read_paper_state(pg, TIMING_ID).pending_decision is True


def test_redeciding_a_session_replaces_its_targets_and_idle_is_derived(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, BOOK_ID, S3, TARGETS)
    with_idle = TARGETS[:1] + (Target("BIL", D("0.500000"), D("91.5")),)
    store.save_book_decision(pg, BOOK_ID, S3, with_idle)
    assert store.load_book(pg, BOOK_ID).targets == with_idle
    assert store.load_book(pg, BOOK_ID, idle_symbol="BIL").idle_added is True
    assert store.load_book(pg, BOOK_ID, idle_symbol=None).idle_added is False
    ranks = pg.execute("SELECT rank, symbol FROM book_targets ORDER BY rank").fetchall()
    assert ranks == [(1, "AAA"), (2, "BIL")]


def test_executed_targets_rewrite_the_stored_decision_in_place(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, BOOK_ID, S3, TARGETS)
    pg.execute("UPDATE book_targets SET explanation = 'why' WHERE symbol = 'BBB'")
    # A 2-for-1 split on BBB executed on S3 halved its prices before the step.
    executed = (
        TARGETS[0],
        Target("BBB", D("0.250000"), D("10"), limit=D("10.2"), stop=D("9"), take=D("12")),
    )
    book = Book(cash=CASH0, equity=CASH0, positions=(), last_session=S3)
    store.save_book_night(pg, BOOK_ID, book, (), (), Snapshot(S3, CASH0, CASH0), executed_targets=executed)
    assert store.read_book_targets(pg, BOOK_ID, S3) == executed
    rows = pg.execute(
        "SELECT rank, symbol, explanation FROM book_targets WHERE strategy_id = %s ORDER BY rank", (BOOK_ID,)
    ).fetchall()
    assert rows == [(1, "AAA", None), (2, "BBB", "why")]


def test_executed_targets_must_match_the_stored_decision(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, BOOK_ID, S3, TARGETS)
    book = Book(cash=CASH0, equity=CASH0, positions=(), last_session=S3)
    with pytest.raises(store.StoreError, match="not the stored decision"):
        store.save_book_night(
            pg, BOOK_ID, book, (), (), Snapshot(S3, CASH0, CASH0), executed_targets=TARGETS[::-1]
        )


def test_fractional_book_fills_and_trades_round_trip_in_order(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    positions = (
        Position("BRK.B", D("1.2345"), D("452.2500"), S3, D("450.1000"), 2, D("556.2183"), D("0"), None, None),
        Position("BRKB", D("0.0001"), D("1.0000"), S3, D("1.0000"), 1, D("0.0001"), D("0.1234"), D("0.9"), D("1.5"), True),
    )
    cash = D("700.0001")
    equity = D("1258.2843")
    book = Book(cash=cash, equity=equity, positions=positions, last_session=S3)
    fills = (
        Fill(S3, "ZZZ", "sell", D("3.5"), D("10.0000"), D("34.9650"), D("0.0350"), "signal"),
        Fill(S3, "BRK.B", "buy", D("1.2345"), D("450.1000"), D("-556.2183"), D("0.5556"), "entry"),
        Fill(S3, "BRKB", "buy", D("0.0001"), D("1.0000"), D("-0.0001"), D("0.0000"), "entry"),
    )
    trades = (
        Trade("ZZZ", S1, S3, D("9.0000"), D("10.0000"), 3, D("31.5315"), D("34.9650"), D("3.4335"), "signal", False),
        Trade("BIL", S1, S3, D("91.0000"), D("91.5000"), 3, D("91.0910"), D("91.4085"), D("0.3175"), "signal", True),
    )
    snap = BookSnapshot(S3, cash, equity, D("558.2843"))
    store.save_book_night(pg, BOOK_ID, book, fills, trades, snap)
    assert store.load_book(pg, BOOK_ID).book == book
    assert store.read_book_positions(pg, BOOK_ID) == positions  # Python order: "BRK.B" < "BRKB"
    assert store.read_book_fills(pg, BOOK_ID) == fills
    assert store.read_book_trades(pg, BOOK_ID) == trades
    assert pg.execute("SELECT seq, symbol FROM book_fills ORDER BY seq").fetchall() == [
        (1, "ZZZ"), (2, "BRK.B"), (3, "BRKB")
    ]
    assert store.read_snapshots(pg, BOOK_ID)[-1] == Snapshot(S3, cash, equity)

    # Next session: positions replaced, seq restarts at 1 for the new date.
    book2 = Book(cash=D("1258.2843"), equity=D("1258.2843"), positions=(), last_session=S4)
    fills2 = (Fill(S4, "BRK.B", "sell", D("1.2345"), D("452.2500"), D("557.7008"), D("0.5583"), "forced"),)
    store.save_book_night(pg, BOOK_ID, book2, fills2, (), Snapshot(S4, book2.cash, book2.equity))
    assert store.read_book_positions(pg, BOOK_ID) == ()
    assert store.read_book_fills(pg, BOOK_ID) == fills + fills2
    assert pg.execute("SELECT seq FROM book_fills WHERE session_date = %s", (S4,)).fetchall() == [(1,)]
    with pytest.raises(psycopg.errors.UniqueViolation):  # a session is saved once
        store.save_book_night(pg, BOOK_ID, book2, fills2, (), Snapshot(S4, book2.cash, book2.equity))


def test_book_values_the_columns_cannot_hold_are_refused(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    p = Position("AAA", D("1.23456"), D("10"), S3, D("10"), 1, D("12.3456"), D("0"), None, None)
    book = Book(cash=D("1"), equity=D("13.3456"), positions=(p,), last_session=S3)
    with pytest.raises(ValueError, match="more decimals"):
        store.save_book_night(pg, BOOK_ID, book, (), (), Snapshot(S3, D("1"), D("13.3456")))


# --------------------------------------------------------------------------- benchmark


def _freeze(conn, strategy_id, paper_start):
    store.freeze_spec(
        conn, strategy_id, spec={"engine": "x"}, digest="d", backtest_gate={"passed": False}, paper_start=paper_start
    )


def test_benchmark_round_trip(pg):
    _freeze(pg, "SPY", S1)
    store.init_paper_state(pg, "SPY", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    day0 = store.load_benchmark(pg)
    assert day0 == BenchmarkState(start=S1, cash=CASH0, equity=CASH0, position=None, last_session=S0)
    holding = Position("SPY", D("2"), D("601.5000"), S1, D("600.0000"), 1, D("1201.2000"), D("0"), None, None)
    state = BenchmarkState(start=S1, cash=D("48.8000"), equity=D("1251.8000"), position=holding, last_session=S1)
    fills = (Fill(S1, "SPY", "buy", D("2"), D("600.0000"), D("-1201.2000"), D("1.2000"), "entry"),)
    store.save_benchmark_night(pg, "SPY", state, Snapshot(S1, state.cash, state.equity), fills)
    assert store.load_benchmark(pg) == state
    assert store.read_book_fills(pg, "SPY") == fills
    assert store.read_snapshots(pg, "SPY") == (Snapshot(S0, CASH0, CASH0), Snapshot(S1, state.cash, state.equity))

    # A session that sells nothing and buys nothing: the holding row is rewritten, no fills.
    marked = BenchmarkState(
        start=S1, cash=D("48.8000"), equity=D("1253.8000"),
        position=Position("SPY", D("2"), D("602.5000"), S1, D("600.0000"), 2, D("1201.2000"), D("0"), None, None),
        last_session=S2,
    )
    store.save_benchmark_night(pg, "SPY", marked, Snapshot(S2, marked.cash, marked.equity), ())
    assert store.load_benchmark(pg) == marked
    assert store.read_book_fills(pg, "SPY") == fills


def test_benchmark_needs_paper_start(pg):
    store.init_paper_state(pg, "SPY", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    with pytest.raises(store.StoreError, match="no paper_start"):
        store.load_benchmark(pg)


# --------------------------------------------------------------------------- dividends and splits


def test_dividends_on_and_between(pg):
    pg.execute(
        "INSERT INTO dividends (symbol, ex_date, amount) VALUES "
        "('SPY', %s, 1.888834), ('AAA', %s, 0.25), ('BBB', %s, 0.1), ('SPY', %s, 1.5)",
        (S3, S3, S3, S5),
    )
    assert store.dividends_on(pg, S3, ["SPY", "AAA", "ZZZ"]) == {"AAA": {S3: D("0.25")}, "SPY": {S3: D("1.888834")}}
    assert list(store.dividends_on(pg, S3, ["SPY", "AAA"])) == ["AAA", "SPY"]
    assert store.dividends_on(pg, S3, ["SPY"]).get("SPY", {}).get(S3) == D("1.888834")
    assert store.dividends_on(pg, S3, []) == {}
    assert store.dividends_on(pg, S4, ["SPY"]) == {}
    assert store.dividends_between(pg, S3, S5) == {
        "AAA": {S3: D("0.25")},
        "BBB": {S3: D("0.1")},
        "SPY": {S3: D("1.888834"), S5: D("1.5")},
    }
    assert store.dividends_between(pg, S4, S4) == {}


def test_applied_splits_only(pg):
    pg.execute(
        "INSERT INTO split_adjustments (symbol, execution_date, split_from, split_to, applied) VALUES "
        "('NVDA', %s, 1, 10, true), ('AAA', %s, 32, 1, true), ('BBB', %s, 1, 2, false), ('CCC', %s, 2, 3, true)",
        (S3, S3, S3, S5),
    )
    assert store.applied_splits_on(pg, S3) == (("AAA", D(1) / D(32)), ("NVDA", D(10)))
    assert store.applied_splits_on(pg, S4) == ()
    assert store.applied_splits_between(pg, S3, S5) == (
        ("AAA", S3, D(1) / D(32)),
        ("CCC", S5, D(3) / D(2)),
        ("NVDA", S3, D(10)),
    )


# --------------------------------------------------------------------------- windowed market


def _seed_market(conn) -> date:
    days = dates.sessions(date(2026, 6, 1), date(2026, 10, 2))
    rows = []
    for i, d in enumerate(days):
        px = D(100) + D(i) / D(4)
        rows.append(bars.make_bar("SPY", d, px, px + 1, px - 1, px + D("0.5"), 1_000_000 + i))
        rows.append(bars.make_bar("AAA", d, px / 2, px / 2 + 1, px / 2 - 1, px / 2, 5_000 + i))
        if d >= date(2026, 9, 1):
            rows.append(bars.make_bar("NEW", d, "50.1234", "51", "49", "50.5", 7))
        if d < date(2026, 7, 1):
            rows.append(bars.make_bar("OLD", d, "5", "6", "4", "5.5", 9))
    with db.transaction(conn, False):
        bars.upsert_bars(conn, rows)
        conn.execute(
            "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) VALUES "
            "('AAA', 'SP500', '2020-01-02', NULL, 'AAA'), ('AAA', 'NDX', '2021-01-04', NULL, 'AAA'), "
            "('OLD', 'SP500', '2020-01-02', '2026-07-01', 'OLD')"
        )
        fx.upsert_fx(conn, [(date(2026, 6, 1), D("16000")), (date(2026, 9, 30), D("16300.5"))])
    return date(2026, 8, 3)


def test_market_window_equals_the_full_load_cut_at_since(pg, tmp_path):
    since = _seed_market(pg)
    full, _ = bio.load_market(pg, cache_dir=tmp_path)
    window = store.load_market_window(pg, since)
    pg.rollback()
    assert list(window.history) == ["AAA", "NEW", "SPY"]  # OLD has no bar on or after since
    cut = np.datetime64(since, "D")
    for symbol, h in window.history.items():
        f = full.history[symbol]
        keep = f.dates >= cut
        assert h.dates.tolist() == f.dates[keep].tolist()
        for col in ("open", "high", "low", "close", "volume"):
            assert getattr(h, col).tolist() == getattr(f, col)[keep].tolist()
        assert window.last_bar_date(symbol) == full.last_bar_date(symbol)
    for d in dates.sessions(since, date(2026, 10, 2)):
        assert window.bars_on(d, ["AAA", "NEW", "SPY"]) == full.bars_on(d, ["AAA", "NEW", "SPY"])
    assert window.membership.intervals == full.membership.intervals
    assert window.fx == full.fx


def test_market_window_since_is_550_calendar_days_back():
    assert store.market_window_since(date(2026, 10, 2)) == date(2026, 10, 2) - timedelta(days=550)


def test_read_bars_frame_default_statement_is_unchanged_and_since_filters(pg, monkeypatch):
    _seed_market(pg)
    statements = []
    real_copy = psycopg.Cursor.copy

    def spy_copy(self, statement, *args, **kwargs):
        statements.append((str(statement), args))
        return real_copy(self, statement, *args, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "copy", spy_copy)
    whole = bio.read_bars_frame(pg)
    part = bio.read_bars_frame(pg, since=date(2026, 9, 1))
    pg.rollback()
    assert statements == [(bio.BARS_COPY_SQL, ()), (bio.BARS_COPY_SINCE_SQL, ((date(2026, 9, 1),),))]
    assert len(part) == int((whole["date"] >= "2026-09-01").sum())
    assert part.reset_index(drop=True).equals(
        whole[whole["date"] >= "2026-09-01"].reset_index(drop=True)
    )
    with pytest.raises(TypeError):
        bio.read_bars_frame(pg, since="2026-09-01")
    pg.rollback()
    with pytest.raises(bio.LoadError):
        bio.read_bars_frame(pg, since=date(2027, 1, 4))
```
**Impact:** Adds about 3 s of PG tests. The tests need phase 1's 003 rows: `read_strategies` expects exactly `SPY, A, F4-MOM12-N20-TREND, F1-SPY-SMA200-M`. If phase 1 changes the roster ids or the sort order, update `test_read_strategies_returns_the_roster_rows_in_sort_order` and the `BOOK_ID`/`TIMING_ID` constants.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/paper-trading-ship && engine/.venv/bin/python -c "import seer_engine.paper.store as s, seer_engine.backtest.io as io; print(s.load_market_window, io.BARS_COPY_SINCE_SQL)"`

**Tests:**
- Focused: `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_paper_store.py engine/tests/test_backtest_io.py -q`
- Purity, with phase 1's glob skipping `store.py`: `engine/.venv/bin/pytest engine/tests/test_sim_purity.py engine/tests/test_strategy_purity.py -q`, plus phase 1's paper purity test file.
- Full suite, invariant 1: `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`. It must pass with **0 skipped**.
- `cd web && npx vitest run` is unaffected; run it anyway for the invariant.

**Manual check:**
- `git diff engine/src/seer_engine/backtest/io.py` shows only the new constant and the `read_bars_frame` body.
- `BARS_COPY_SQL` is unchanged.
- `git diff --stat` touches exactly three files.

**Exit criteria:**
- `test_paper_store.py` is green: save followed by load is exact for the bracket `Portfolio` (incl. marks), the book `Book` (incl. fractional shares and Python symbol order), pending targets (None, empty, idle), fills (`seq` order), trades (exit order), the benchmark state and snapshots.
- The day-0 init writes `prev_session(paper_start)`.
- Orders are updated by key.
- The windowed market equals `load_market` cut at `since`.
- `test_backtest_io.py` is unchanged and green.
- The full engine suite is green with 0 skipped.

## Handoffs

- **Phase 7 (`commands/paper.py`): call order per strategy, inside one `db.transaction`:**
  - Init night for a strategy whose `paper_start` is NULL:
    1. `freeze_spec(conn, sid, spec=..., digest=..., backtest_gate=..., paper_start=rd.session_date)`.
    2. `init_paper_state(conn, sid, paper_start=..., cash0=initial_cash_usd(INITIAL_IDR, usd_idr), usd_idr=...)`.
    3. The decision write: `insert_pending_orders` plus `write_pending(..., decision=False)` for A, `save_book_decision` for a book, `write_pending(..., decision=False)` for SPY (reconciled: every engine keeps `pending_session = next_session(last_session)` between nights, which phase 7's `plan_night` checks and phase 10's seed writes).
  - Every new session S:
    - Bracket: `load_portfolio`, `settle_bracket`, `save_bracket_night(conn, sid, night.portfolio, night.events, night.snapshot)`, `decide_bracket`, `insert_pending_orders(conn, sid, sized.placed)`, `write_pending(conn, sid, next, decision=False)`.
    - Book: `load_book(conn, sid, idle_symbol=rules.idle_symbol)`, `settle_book(...)` with `loaded.targets` and `loaded.idle_added`, `dividends_on(conn, S, held)` and `applied_splits_on(conn, S)`, `save_book_night(conn, sid, night.book, night.fills, night.trades, night.snapshot, executed_targets=night.targets)`, `decide_book`, `save_book_decision(conn, sid, next, targets)`.
    - SPY: `load_benchmark`, `step_benchmark(state, S, bar, dividends_on(conn, S, ["SPY"]).get("SPY", {}).get(S), split=dict(applied_splits_on(conn, S)).get("SPY"))`, `save_benchmark_night(conn, "SPY", state, snapshot, fills)`, `write_pending(conn, "SPY", next, decision=False)`.
    - (Phase 7 as reconciled reads the window's dividends once with `dividends_between` and slices them per session; `dividends_on` stays available.)
  - `market_window_since(data_date)` gives the first bar date to load, and `load_market_window(conn, since)` loads the market.
  - `orders.company`: pass a `companies` mapping if phase 7 has names; otherwise the symbol is stored.
  - Phase 7 decides whether the replay or "new session" detection compares `read_paper_state(...).last_session` with the sessions to step.
- **Phase 7, decision-session guard:** `write_pending` and `save_book_decision` refuse any session other than `next_session(paper_state.last_session)`. The command must therefore settle S before it decides S+1, which matches the runner order.
- **Phase 7, idempotency:** a second `save_*_night` for the same session raises, through the fills `seq` uniqueness or a key-update mismatch. The command must skip sessions `<= paper_state.last_session`.
- **Phase 8 (`paper/replay.py`, `paper_check`):** the persisted side can be read with `read_snapshots`, `read_orders`, `read_book_fills`, `read_book_trades`, `read_book_positions`, `read_paper_state` (`initial_cash_usd` and `usd_idr` for the replay's explicit `usd_idr`) and `read_strategy(...).paper_start`. Window inputs come from `dividends_between` (a DividendMap for `run_rules`) and `applied_splits_between` (the split-affected check), plus `load_market_window`. For `buy_and_hold`, convert `dividends_between(...)["SPY"]` to `backtest.benchmark.Dividend` values in phase 8.
- **Phase 8, cash reconciliation (from phase 2's note):** a floor-to-zero split `Fill` has `cash_usd` equal to the cash in lieu and `cost_usd` 0. A surviving position's cash in lieu shows up only in `income_usd`. The store persists both as given and does not reconcile them.
- **Phase 1 (reconciler):** this plan depends on C1 exactly, including `book_targets.explanation` and `book_fills.seq`. If phase 1 renames a column, `store.py`'s SQL strings are the only place to change.
- **Phase 13 (docs):** describe `paper/store.py` (C4) and `read_bars_frame(since=)` in `engine/package_readme.md`.

## Rollback

`git revert` the phase commit. It removes `paper/store.py` and `tests/test_paper_store.py` and restores `read_bars_frame` without `since`. Nothing else imports the store until phase 7 lands, so phase 7 must be reverted first if it has landed. No migration or data change belongs to this phase.
