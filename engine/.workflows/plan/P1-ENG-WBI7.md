> Adopted from `PAPER_TRADING_SHIP_PLAN.md` phase 8. Source: `.workflows/plan/paper-trading-ship/phase-8.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 8: `paper_check` replay check

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R3. This is the replay check (D7): the proof that the nightly paper state equals a one-shot backtest replay. It also covers design §8 failure handling, where a broken paper state shows up as a red, readable check.
**Depends on:** Phase 7. Through phase 7 it also depends on phases 1, 3, 4, 5 and 6.
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/paper` (pure `replay.py`) and `engine/src/seer_engine/commands` (`paper_check.py`)

---

## Goal

After this phase, `python -m seer_engine paper_check [--require-sessions N]` replays every roster strategy from its `paper_start` through its last stepped session, using the bars in the database:
- A runs through `run_rules` with `DESIGN_V0`.
- F4 and F1 run through `run_rules` with `MONTHLY_HOLD` and the stored `usd_idr`.
- SPY runs through `buy_and_hold`.

The check then compares the replay with every stored record:
- every `equity_snapshots` row, day 0 included;
- every A `orders` row and open mark;
- the `book_positions`, `book_fills` and `book_trades` rows;
- every `book_targets` decision;
- the SPY holding;
- `paper_state`.

Each strategy gets one result:
- **ok**;
- **mismatch**, with the first differences listed in plain words;
- **split-affected**, when an applied split hit a symbol the strategy held or had pending;
- **not started**.

The command exits 1 on any mismatch, and also when `--require-sessions N` is given and a strategy has stepped fewer than N sessions. It writes nothing.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.

**Creates:**
- `seer_engine.paper.replay` (`engine/src/seer_engine/paper/replay.py`, new, pure):
  - Type aliases:
    - `Engine = Literal["bracket", "book", "benchmark"]`
    - `Status = Literal["ok", "mismatch", "split-affected", "not-started"]`
  - Constants:
    - `ENGINES`, `MAX_SHOWN = 10`, `BENCHMARK_SYMBOL = "SPY"`
    - the field lists `SNAPSHOT_FIELDS`, `ORDER_FIELDS`, `POSITION_FIELDS`, `FILL_FIELDS`, `TRADE_FIELDS`, `TARGET_FIELDS`, `HOLDING_FIELDS`
  - Value types:
    - `Holding(symbol, shares, mark)`: frozen, slots.
    - `PaperHead(strategy_id, engine, paper_start, last_session, usd_idr)`: frozen, slots, validated, with the property `sessions`.
    - `Records(initial_cash, cash, equity, pending_session, pending_decision, snapshots, orders=(), marks=(), positions=(), fills=(), trades=(), targets=(), holdings=())`: frozen.
    - `Difference(where, text)`: frozen, slots. `str()` gives `"where: text"`.
    - `CheckResult(strategy_id, status, sessions, paper_start=None, last_session=None, differences=(), total_differences=0, splits=())`: frozen, slots.
  - Functions:
    - `sessions_stepped(paper_start, last_session) -> int`
    - `last_close(market, symbol, on) -> Decimal`
    - `held_before(fills, session) -> frozenset[str]`
    - `expected_bracket(market, strategy, params, head) -> Records`
    - `expected_book(market, allocator, params, rules, head, dividends) -> Records`
    - `expected_benchmark(market, head, dividends) -> Records`
    - `compare(engine, stored, expected) -> tuple[Difference, ...]`
    - `split_exposure(engine, paper_start, records, splits) -> tuple[tuple[str, date], ...]`
    - `judge(head, stored, expected, splits) -> CheckResult`
    - `not_started(strategy_id) -> CheckResult`
    - `broken(strategy_id, where, message, *, paper_start=None, last_session=None) -> CheckResult`
    - `failures(results, require_sessions) -> tuple[str, ...]`
    - `exit_code(results, require_sessions) -> int`
    - `render(results) -> tuple[str, ...]`
- `seer_engine.commands.paper_check` (`engine/src/seer_engine/commands/paper_check.py`, new). `cli.discover()` finds it as the command `paper_check`:
  - `HELP: str`
  - `add_arguments(p)`: `--require-sessions N`, a non-negative int with default 0.
  - `run(args) -> int`
  - `execute(conn, *, require_sessions: int = 0) -> int`
  - `check(conn) -> tuple[CheckResult, ...]`. It needs an idle connection, and it reads everything in one `REPEATABLE READ, READ ONLY` transaction, which it rolls back.
- Tests:
  - `engine/tests/test_paper_replay.py` (new, pure, 39 collected tests);
  - `engine/tests/test_paper_check.py` (new, PG, 25 collected tests).

**Signature changes:** none to existing code.

**Requires (from earlier phases).** Each name below is quoted from the sibling plan files as they stand.

| Phase | Symbol used here | Shape |
|---|---|---|
| 1 | `seer_engine.paper.roster.ROSTER` | `tuple[RosterEntry, ...]` in sort order (SPY, A, F4, F1) |
| 1 | `RosterEntry.id / .engine / .obj / .params / .rules` | `engine` is one of `"bracket"`, `"book"`, `"benchmark"`. `obj` is `STRATEGY_A`, `FACTOR`, `TIMING`, or `None` for SPY. `rules` is `DESIGN_V0`, `MONTHLY_HOLD`, or `None` |
| 1 | `paper/__init__.py` exists (a docstring only); the purity test globs `paper/*.py` except `store.py` | `paper/replay.py` is covered with no test edit |
| 1 | migration 003 = C1 | `strategies.paper_start`, `paper_state`, `book_*`, `dividends`, `orders.mark` |
| 3 | `paper.bracket.decide_bracket(pf, strategy, params, history, members, data_date) -> SizingResult` | needs `pf.last_session in (None, data_date)` |
| 4 | `paper.book.decide_book(market, allocator, params, rules, data_date, held) -> tuple[tuple[Target, ...] \| None, bool]` | `None` when `next_session(data_date)` is not a decision session |
| 6 | `store.read_strategies(conn) -> tuple[StrategyRow, ...]` | `StrategyRow.id`, `.paper_start` |
| 6 | `store.read_paper_state(conn, sid) -> PaperState \| None` | `.last_session, .cash_usd, .equity_usd, .initial_cash_usd, .usd_idr, .pending_session, .pending_decision` |
| 6 | `store.read_snapshots(conn, sid) -> tuple[Snapshot, ...]` | ordered by date, day 0 first |
| 6 | `store.read_orders(conn, sid) -> tuple[tuple[Order, Decimal \| None], ...]` | every row with its `mark`, ordered by `(session_date, slot)` |
| 6 | `store.read_book_positions(conn, sid) -> tuple[Position, ...]` | sorted by symbol |
| 6 | `store.read_book_fills(conn, sid) -> tuple[Fill, ...]` | ordered by `(session_date, seq)` |
| 6 | `store.read_book_trades(conn, sid) -> tuple[Trade, ...]` | ordered by `(exit_date, id)` |
| 6 | `store.read_book_targets(conn, sid, session) -> tuple[Target, ...]` | in rank order |
| 6 | `store.dividends_between(conn, start, end) -> DividendMap` | both ends inclusive |
| 6 | `store.applied_splits_between(conn, start, end) -> tuple[tuple[str, date, Decimal], ...]` | |
| 6 | `store.load_market_window(conn, since) -> Market` | read inside the caller's transaction; no commit, no rollback |
| 6 | `store.MARKET_WINDOW_DAYS` | `550` |
| 7 | `commands.paper.execute(conn, *, now, dry_run=False) -> int` | used by the PG tests |
| 7 | persisted conventions | listed under "Assumptions on phase 7's writes" below |

Assumptions on phase 7's writes. These are the conventions the comparison relies on, and all of them appear in phases 6 and 7 as written:
- **Snapshots.** Every strategy has an `equity_snapshots` row on `prev_session(paper_start)` (day 0) and one per stepped session.
- **A's orders.** A writes every order it ever sizes into `orders`, including expired ones, the forced closes and the pending ones for `pending_session`. `orders.mark` holds the open orders' marks.
- **Targets.** A book strategy writes its targets for a decision session to `book_targets` with `rank` running 1..n, and keeps them after execution. A decision with no targets writes no row.
- **`pending_decision`.** `paper_state.pending_decision` is meaningful for book strategies only.
- **The SPY benchmark.** It keeps at most one `book_positions` row, with symbol `SPY` and whole shares. Its `paper_state.cash_usd` is the uninvested cash.
- **FX.** `paper_state.usd_idr` is the rate the initial cash was converted at.

**Leaves alone (owned by others):**
- `commands/paper.py` and `runs.py` (phase 7);
- `paper/store.py` and `backtest/io.py` (phase 6);
- `paper/bracket.py` and `paper/benchmark.py` (phase 3);
- `paper/book.py` (phase 4);
- `paper/roster.py`, `paper/__init__.py`, the purity tests and migration 003 (phase 1);
- `sim/*` (phase 2);
- `.github/workflows/*`, the "Paper check" step included (phase 13);
- `docs/*`, `engine/package_readme.md` and the runbook (phase 13);
- `web/*` (phases 10–12);
- the closed records (`backtest/runner.py`, `book_runner.py`, `benchmark.py`, `registry.py`), which this phase only calls.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/replay.py` | create (new file, line 1) | Pure replay and comparison: expected records per engine, field-by-field differences, the split-affected rule, verdicts, exit code and rendering |
| `engine/src/seer_engine/commands/paper_check.py` | create (new file, line 1) | The impure command. It reads the stored records and the market in one read-only transaction, replays every started roster strategy, logs one line per strategy and returns 0 or 1 |
| `engine/tests/test_paper_replay.py` | create (new file, line 1) | Pure unit tests on an in-memory market: equality with `run_backtest`, `run_book` and `buy_and_hold`, day-0 decisions, readable differences, split exposure, verdicts, exit codes and rendering |
| `engine/tests/test_paper_check.py` | create (new file, line 1) | PG tests. They cover: 8 synthetic `paper` nights followed by a passing check; tampered rows giving exit 1 with a readable difference; `--require-sessions`; split-affected; not started; the first night only; a broken `paper_state`; read-only behavior; and CLI wiring |

No existing file changes.

## Implementation Steps

### Step 1: The pure replay module
**File:** `engine/src/seer_engine/paper/replay.py:1` (new file)

**Change:** This step creates the pure half of the check. Design decisions:

- **One record type for both sides.** `Records` holds both what the DB stored and what the replay expects, so a single `compare` diffs them field by field. Tests can also build a stored record from an expected one and then tamper with it.
- **A's FX.** `run_rules(DESIGN_V0)` refuses an explicit `usd_idr` and converts at `market.usd_idr_on(start)`. The A replay therefore runs on a copy of the market whose `fx` is `((paper_start, usd_idr),)`. This addresses phase 7's handoff ("the A replay must call `run_backtest` on a Market whose fx stops at `prev_session(paper_start)`, or an equivalent").
- **Pending orders.** A's pending orders for `pending_session` are recomputed with phase 3's `decide_bracket`, starting from the replay's end portfolio:
  - cash and equity come from the last snapshot;
  - the orders are `open_at_end`;
  - each mark is the open symbol's last close on or before `last_session`. This is the mark `sim.step` leaves.
- **Book decisions.** Every decision session in `[paper_start, pending_session]` is recomputed with phase 4's `decide_book`. The held set before each decision session is rebuilt from the replay's fills. There are no splits inside a replay, so the net shares per symbol equal the position exactly.
- **Ignored fields.** The benchmark has no meaningful `pending_session` or `pending_decision`, and bracket has no meaningful `pending_decision`. Those fields are not compared.
- **Splits.** A split counts only when it is `applied` and executed on or after `paper_start`, and the strategy had live state on the symbol the night before it. Live state means:
  - bracket: a live order;
  - book: a held position or a target for that session;
  - benchmark: the SPY holding.

  When that holds, the verdict is `split-affected` and the differences are still listed for information. There is no upper bound on the split date: a split already applied to history but not yet stepped through (the paper step failed after `nightly`) also changes the replay.

**Code:**
```python
"""Replay check (D7): one strategy's stored paper record against a fresh one-shot replay.

Pure (the paper purity test globs ``seer_engine/paper/*.py`` except ``store.py``): no database,
network, clock, randomness, logging or file access. ``commands/paper_check.py`` reads the stored
records, the windowed market and the dividends, and hands them in.

Expected records, per engine, over ``[paper_start, last_session]``:

- ``bracket`` (A): ``run_rules(market', strategy, params, DESIGN_V0, paper_start, last_session)``
  where ``market'`` is the market with ``fx = ((paper_start, usd_idr),)``. ``run_backtest``
  converts at ``market.usd_idr_on(start)``; paper converted at the stored rate (plan Decisions
  "Initial FX"). Expected orders: the run's closed, expired and open orders, plus the pending
  orders ``paper.bracket.decide_bracket`` sizes for ``pending_session`` from the run's end
  portfolio. Expected marks: each open symbol's last close on or before ``last_session``.
- ``book`` (F4, F1): ``run_rules(market, allocator, params, rules, paper_start, last_session,
  dividends=dividends, usd_idr=usd_idr)``. Expected targets: ``paper.book.decide_book`` on every
  decision session from ``paper_start`` through ``pending_session``, with the held set rebuilt
  from the run's fills; an empty decision is left out (it writes no ``book_targets`` row).
- ``benchmark`` (SPY): ``buy_and_hold(market.spy(), paper_start, last_session, cash0,
  dividends=SPY's)``; the holding is ``(SPY, whole shares, last close)``.

The first night steps no session (``last_session == prev_session(paper_start)``): the expected
record is the day-0 snapshot plus the first decision.

``judge`` gives one ``CheckResult``: ``ok`` when stored == expected; ``mismatch`` with the first
``MAX_SHOWN`` differences; ``split-affected`` when an applied split executed on or after
``paper_start`` on a symbol the strategy held or had pending the night before it, whatever the
differences (plan Decisions "Replay check scope": whole shares sized before a split cannot equal
a replay over the rewritten bars); ``not-started`` without a paper start.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend, buy_and_hold
from seer_engine.backtest.book_runner import BookResult, DividendMap, run_rules
from seer_engine.backtest.market import SPY, Market
from seer_engine.backtest.runner import INITIAL_IDR, RunResult
from seer_engine.paper.book import decide_book
from seer_engine.paper.bracket import decide_bracket
from seer_engine.sim import (
    DESIGN_V0,
    Fill,
    Order,
    Portfolio,
    Position,
    Snapshot,
    Target,
    Trade,
    TradeRules,
    initial_cash_usd,
    is_decision_session,
    new_portfolio,
)
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import Strategy

Engine = Literal["bracket", "book", "benchmark"]
Status = Literal["ok", "mismatch", "split-affected", "not-started"]

ENGINES: tuple[str, ...] = ("bracket", "book", "benchmark")
MAX_SHOWN = 10  # differences listed per strategy; the rest are only counted
BENCHMARK_SYMBOL = SPY

SNAPSHOT_FIELDS: tuple[str, ...] = ("cash_usd", "equity_usd")
ORDER_FIELDS: tuple[str, ...] = (
    "slot",
    "last_price",
    "limit_price",
    "tp_price",
    "sl_price",
    "shares",
    "status",
    "fill_date",
    "fill_price",
    "days_held",
    "exit_date",
    "exit_price",
    "exit_reason",
    "pnl_usd",
)
POSITION_FIELDS: tuple[str, ...] = (
    "shares",
    "mark",
    "entry_date",
    "entry_price",
    "days_held",
    "cost_usd",
    "income_usd",
    "stop",
    "take",
    "exit_pending",
)
FILL_FIELDS: tuple[str, ...] = ("session_date", "symbol", "side", "shares", "price", "cash_usd", "cost_usd", "reason")
TRADE_FIELDS: tuple[str, ...] = (
    "symbol",
    "entry_date",
    "exit_date",
    "entry_price",
    "exit_price",
    "days_held",
    "cost_usd",
    "income_usd",
    "pnl_usd",
    "exit_reason",
    "idle",
)
TARGET_FIELDS: tuple[str, ...] = ("symbol", "weight", "last", "limit", "stop", "take")
HOLDING_FIELDS: tuple[str, ...] = ("shares", "mark")


# --------------------------------------------------------------------------- values


@dataclass(frozen=True, slots=True)
class Holding:
    """The benchmark's holding as ``book_positions`` stores it: whole shares and the last close."""

    symbol: str
    shares: Decimal
    mark: Decimal


@dataclass(frozen=True, slots=True)
class PaperHead:
    """What the replay needs from a started strategy: its engine, window and starting rate.

    ``last_session`` is ``prev_session(paper_start)`` right after the first night, then the last
    session stepped. ``usd_idr`` is ``paper_state.usd_idr``, the rate the initial cash was
    converted at.
    """

    strategy_id: str
    engine: Engine
    paper_start: date
    last_session: date
    usd_idr: Decimal

    def __post_init__(self) -> None:
        if self.engine not in ENGINES:
            raise ValueError(f"{self.strategy_id}: unknown engine {self.engine!r}")
        for name in ("paper_start", "last_session"):
            value = getattr(self, name)
            if isinstance(value, datetime) or not isinstance(value, date):
                raise TypeError(f"{self.strategy_id}: {name} must be a date, got {type(value).__name__}")
            if not dates.is_session(value):
                raise ValueError(f"{self.strategy_id}: {name} {value} is not an NYSE session")
        if self.last_session < dates.prev_session(self.paper_start):
            raise ValueError(
                f"{self.strategy_id}: last session {self.last_session} is before the day-0 session "
                f"{dates.prev_session(self.paper_start)}"
            )
        if not isinstance(self.usd_idr, Decimal):
            raise TypeError(f"{self.strategy_id}: usd_idr must be a Decimal, got {type(self.usd_idr).__name__}")
        if not self.usd_idr.is_finite() or self.usd_idr <= 0:
            raise ValueError(f"{self.strategy_id}: usd_idr must be > 0, got {self.usd_idr}")

    @property
    def sessions(self) -> int:
        """How many sessions have been stepped (0 after the first night)."""
        return sessions_stepped(self.paper_start, self.last_session)


@dataclass(frozen=True)
class Records:
    """One strategy's paper record: as stored in the database, or as the replay expects it.

    ``initial_cash``, ``cash``, ``equity``, ``pending_session`` and ``pending_decision`` are the
    ``paper_state`` columns. ``snapshots`` are every ``equity_snapshots`` row from day 0. Bracket:
    ``orders`` (every ``orders`` row) and ``marks`` (``(symbol, orders.mark)`` of the open
    orders, by symbol). Book: ``positions``, ``fills`` (execution order), ``trades`` (exit
    order) and ``targets`` (``(session, ranked targets)`` for every stored, non-empty decision,
    by session). Benchmark: ``holdings``.
    """

    initial_cash: Decimal | None
    cash: Decimal | None
    equity: Decimal | None
    pending_session: date | None
    pending_decision: bool
    snapshots: tuple[Snapshot, ...]
    orders: tuple[Order, ...] = ()
    marks: tuple[tuple[str, Decimal | None], ...] = ()
    positions: tuple[Position, ...] = ()
    fills: tuple[Fill, ...] = ()
    trades: tuple[Trade, ...] = ()
    targets: tuple[tuple[date, tuple[Target, ...]], ...] = ()
    holdings: tuple[Holding, ...] = ()


@dataclass(frozen=True, slots=True)
class Difference:
    """One stored value that is not the replay's, in words: ``str()`` is ``"where: text"``."""

    where: str
    text: str

    def __str__(self) -> str:
        return f"{self.where}: {self.text}"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """The verdict for one roster strategy.

    ``differences`` holds the first ``MAX_SHOWN`` differences, ``total_differences`` counts all
    of them. ``splits`` are the applied ``(symbol, execution_date)`` splits that made the
    strategy split-affected.
    """

    strategy_id: str
    status: Status
    sessions: int
    paper_start: date | None = None
    last_session: date | None = None
    differences: tuple[Difference, ...] = ()
    total_differences: int = 0
    splits: tuple[tuple[str, date], ...] = ()


# --------------------------------------------------------------------------- helpers


def sessions_stepped(paper_start: date, last_session: date) -> int:
    """NYSE sessions in ``[paper_start, last_session]`` (0 when ``last_session`` is before the start)."""
    return len(dates.sessions(paper_start, last_session))


def last_close(market: Market, symbol: str, on: date) -> Decimal:
    """``symbol``'s close on its last bar dated on or before ``on``: the mark ``sim.step`` leaves."""
    h = market.history.get(symbol)
    last = None if h is None else h.upto(on).last_date()
    if last is None:
        raise ValueError(f"{symbol} has no bar on or before {on}")
    bar = market.bar(symbol, last)
    if bar is None:
        raise ValueError(f"{symbol} has no bar on {last}")
    return bar.close


def held_before(fills: Iterable[Fill], session: date) -> frozenset[str]:
    """Symbols with net shares > 0 from the fills dated before ``session``: the book's held set the
    night before it (a replay has no splits, so bought minus sold is the position exactly)."""
    net: dict[str, Decimal] = {}
    for f in fills:
        if f.session_date >= session:
            continue
        change = f.shares if f.side == "buy" else -f.shares
        net[f.symbol] = net.get(f.symbol, Decimal(0)) + change
    return frozenset(symbol for symbol, shares in net.items() if shares > 0)


def _day0(paper_start: date, cash0: Decimal) -> Snapshot:
    return Snapshot(date=dates.prev_session(paper_start), cash_usd=cash0, equity_usd=cash0)


def _order_key(o: Order) -> tuple[date, int, str]:
    return (o.session_date, o.slot, o.symbol)


# --------------------------------------------------------------------------- expected records


def expected_bracket(market: Market, strategy: Strategy, params: Any, head: PaperHead) -> Records:
    """The bracket record ``run_rules(DESIGN_V0)`` gives over the head's window, plus the next decision."""
    if head.engine != "bracket":
        raise ValueError(f"{head.strategy_id} is a {head.engine} strategy, not bracket")
    start, last = head.paper_start, head.last_session
    cash0 = initial_cash_usd(INITIAL_IDR, head.usd_idr)
    settled: tuple[Order, ...] = ()
    if last < start:
        pf = new_portfolio(cash0)
        snapshots: tuple[Snapshot, ...] = (_day0(start, cash0),)
    else:
        fixed = Market(history=market.history, membership=market.membership, fx=((start, head.usd_idr),))
        run = run_rules(fixed, strategy, params, DESIGN_V0, start, last)
        if not isinstance(run, RunResult):
            raise TypeError(f"DESIGN_V0 replay of {head.strategy_id} returned {type(run).__name__}")
        snapshots = run.snapshots
        expired = tuple(e.order for e in run.events if e.kind == "expire")
        settled = run.closed + expired + run.open_at_end
        marks = tuple(sorted((o.symbol, last_close(market, o.symbol, last)) for o in run.open_at_end))
        pf = Portfolio(
            cash=snapshots[-1].cash_usd,
            equity=snapshots[-1].equity_usd,
            orders=run.open_at_end,
            marks=marks,
            last_session=last,
        )
    sized = decide_bracket(pf, strategy, params, market.history, market.membership.members_on(last), last)
    orders = tuple(sorted(settled + sized.portfolio.pending_orders(), key=_order_key))
    return Records(
        initial_cash=cash0,
        cash=snapshots[-1].cash_usd,
        equity=snapshots[-1].equity_usd,
        pending_session=dates.next_session(last),
        pending_decision=False,
        snapshots=tuple(snapshots),
        orders=orders,
        marks=pf.marks,
    )


def expected_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    head: PaperHead,
    dividends: DividendMap,
) -> Records:
    """The book record ``run_rules(rules)`` gives over the head's window, plus every decision."""
    if head.engine != "book":
        raise ValueError(f"{head.strategy_id} is a {head.engine} strategy, not book")
    if not isinstance(rules, TradeRules) or rules.engine != "book":
        raise ValueError(f"{head.strategy_id}: book replay needs book rules, got {rules!r}")
    start, last = head.paper_start, head.last_session
    cash0 = initial_cash_usd(INITIAL_IDR, head.usd_idr)
    fills: tuple[Fill, ...] = ()
    trades: tuple[Trade, ...] = ()
    positions: tuple[Position, ...] = ()
    if last < start:
        snapshots: tuple[Snapshot, ...] = (_day0(start, cash0),)
    else:
        run = run_rules(market, allocator, params, rules, start, last, dividends=dividends, usd_idr=head.usd_idr)
        if not isinstance(run, BookResult):
            raise TypeError(f"book replay of {head.strategy_id} returned {type(run).__name__}")
        snapshots = tuple(Snapshot(date=s.date, cash_usd=s.cash_usd, equity_usd=s.equity_usd) for s in run.snapshots)
        fills, trades, positions = run.fills, run.trades, run.open_at_end
    pending = dates.next_session(last)
    decisions: list[tuple[date, tuple[Target, ...]]] = []
    pending_decision = False
    for session in dates.sessions(start, pending):
        if not is_decision_session(rules, session):
            continue
        wanted, _ = decide_book(
            market, allocator, params, rules, dates.prev_session(session), held_before(fills, session)
        )
        if session == pending:
            pending_decision = wanted is not None
        if wanted:
            decisions.append((session, tuple(wanted)))
    return Records(
        initial_cash=cash0,
        cash=snapshots[-1].cash_usd,
        equity=snapshots[-1].equity_usd,
        pending_session=pending,
        pending_decision=pending_decision,
        snapshots=snapshots,
        positions=positions,
        fills=fills,
        trades=trades,
        targets=tuple(decisions),
    )


def expected_benchmark(market: Market, head: PaperHead, dividends: DividendMap) -> Records:
    """The SPY buy-and-hold record over the head's window (dividends reinvested at the ex-date close)."""
    if head.engine != "benchmark":
        raise ValueError(f"{head.strategy_id} is a {head.engine} strategy, not benchmark")
    start, last = head.paper_start, head.last_session
    cash0 = initial_cash_usd(INITIAL_IDR, head.usd_idr)
    if last < start:
        snapshots: tuple[Snapshot, ...] = (_day0(start, cash0),)
        cash = cash0
        holdings: tuple[Holding, ...] = ()
    else:
        by_date = dividends.get(BENCHMARK_SYMBOL, {})
        paid = tuple(Dividend(ex_date=d, amount=by_date[d]) for d in sorted(by_date))
        curve = buy_and_hold(market.spy(), start, last, cash0, dividends=paid, name=BENCHMARK_SYMBOL)
        snapshots = curve.snapshots
        cash = curve.cash
        holdings = ()
        if curve.shares > 0:
            holdings = (
                Holding(
                    symbol=BENCHMARK_SYMBOL,
                    shares=Decimal(curve.shares),
                    mark=last_close(market, BENCHMARK_SYMBOL, last),
                ),
            )
    return Records(
        initial_cash=cash0,
        cash=cash,
        equity=snapshots[-1].equity_usd,
        pending_session=dates.next_session(last),
        pending_decision=False,
        snapshots=tuple(snapshots),
        holdings=holdings,
    )


# --------------------------------------------------------------------------- comparison


def _fmt(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _diff_fields(where: str, stored: object, expected: object, names: Sequence[str]) -> list[Difference]:
    out: list[Difference] = []
    for name in names:
        a, b = getattr(stored, name), getattr(expected, name)
        if a != b:
            out.append(Difference(where, f"{name} stored {_fmt(a)}, replay {_fmt(b)}"))
    return out


def _diff_keyed(
    label: str,
    stored: Mapping[Any, Any],
    expected: Mapping[Any, Any],
    names: Sequence[str],
    key_text: Callable[[Any], str],
) -> list[Difference]:
    out: list[Difference] = []
    for key in sorted(set(stored) | set(expected)):
        where = f"{label} {key_text(key)}"
        if key not in stored:
            out.append(Difference(where, "in the replay, missing from the database"))
        elif key not in expected:
            out.append(Difference(where, "in the database, not in the replay"))
        else:
            out.extend(_diff_fields(where, stored[key], expected[key], names))
    return out


def _diff_sequence(
    label: str,
    stored: Sequence[Any],
    expected: Sequence[Any],
    names: Sequence[str],
    describe: Callable[[Any], str],
) -> list[Difference]:
    out: list[Difference] = []
    for i in range(max(len(stored), len(expected))):
        if i >= len(stored):
            out.append(Difference(f"{label} #{i + 1} ({describe(expected[i])})", "in the replay, missing from the database"))
        elif i >= len(expected):
            out.append(Difference(f"{label} #{i + 1} ({describe(stored[i])})", "in the database, not in the replay"))
        else:
            out.extend(_diff_fields(f"{label} #{i + 1} ({describe(expected[i])})", stored[i], expected[i], names))
    return out


def _diff_values(label: str, stored: Mapping[str, Any], expected: Mapping[str, Any]) -> list[Difference]:
    out: list[Difference] = []
    for key in sorted(set(stored) | set(expected)):
        where = f"{label} {key}"
        if key not in stored:
            out.append(Difference(where, "in the replay, missing from the database"))
        elif key not in expected:
            out.append(Difference(where, "in the database, not in the replay"))
        elif stored[key] != expected[key]:
            out.append(Difference(where, f"stored {_fmt(stored[key])}, replay {_fmt(expected[key])}"))
    return out


def _iso(d: date) -> str:
    return d.isoformat()


def _order_text(key: tuple[date, str]) -> str:
    return f"{key[0].isoformat()} {key[1]}"


def _target_text(key: tuple[date, int]) -> str:
    return f"{key[0].isoformat()} rank {key[1]}"


def _fill_text(f: Fill) -> str:
    return f"{f.session_date.isoformat()} {f.side} {f.symbol}"


def _trade_text(t: Trade) -> str:
    return f"{t.symbol} {t.entry_date.isoformat()}..{t.exit_date.isoformat()}"


def _targets_by_key(decisions: Iterable[tuple[date, tuple[Target, ...]]]) -> dict[tuple[date, int], Target]:
    out: dict[tuple[date, int], Target] = {}
    for session, targets in decisions:
        for rank, t in enumerate(targets, start=1):
            out[(session, rank)] = t
    return out


def compare(engine: Engine, stored: Records, expected: Records) -> tuple[Difference, ...]:
    """Every stored value that differs from the replay, snapshots first, ``paper_state`` last."""
    if engine not in ENGINES:
        raise ValueError(f"unknown engine {engine!r}")
    out: list[Difference] = _diff_keyed(
        "snapshot",
        {s.date: s for s in stored.snapshots},
        {s.date: s for s in expected.snapshots},
        SNAPSHOT_FIELDS,
        _iso,
    )
    if engine == "bracket":
        out += _diff_keyed(
            "order",
            {(o.session_date, o.symbol): o for o in stored.orders},
            {(o.session_date, o.symbol): o for o in expected.orders},
            ORDER_FIELDS,
            _order_text,
        )
        out += _diff_values("mark", dict(stored.marks), dict(expected.marks))
        state = ("initial_cash", "cash", "equity", "pending_session")
    elif engine == "book":
        out += _diff_keyed(
            "position",
            {p.symbol: p for p in stored.positions},
            {p.symbol: p for p in expected.positions},
            POSITION_FIELDS,
            str,
        )
        out += _diff_sequence("fill", stored.fills, expected.fills, FILL_FIELDS, _fill_text)
        out += _diff_sequence("trade", stored.trades, expected.trades, TRADE_FIELDS, _trade_text)
        out += _diff_keyed(
            "target", _targets_by_key(stored.targets), _targets_by_key(expected.targets), TARGET_FIELDS, _target_text
        )
        state = ("initial_cash", "cash", "equity", "pending_session", "pending_decision")
    else:
        out += _diff_keyed(
            "holding",
            {h.symbol: h for h in stored.holdings},
            {h.symbol: h for h in expected.holdings},
            HOLDING_FIELDS,
            str,
        )
        state = ("initial_cash", "cash", "equity")
    out += _diff_fields("paper_state", stored, expected, state)
    return tuple(out)


# --------------------------------------------------------------------------- splits


def _exposed(engine: Engine, paper_start: date, r: Records, symbol: str, day: date) -> bool:
    """Whether ``r`` had live state on ``symbol`` the night before the split executing on ``day``."""
    if engine == "bracket":
        for o in r.orders:
            if o.symbol != symbol or o.session_date > day:
                continue
            if o.status == "closed" and o.exit_date is not None and o.exit_date < day:
                continue
            if o.status == "expired" and o.session_date < day:
                continue
            return True
        return False
    if engine == "book":
        for t in r.trades:
            if t.symbol == symbol and t.entry_date < day <= t.exit_date:
                return True
        for p in r.positions:
            if p.symbol == symbol and p.entry_date < day:
                return True
        for session, targets in r.targets:
            if session == day and any(t.symbol == symbol for t in targets):
                return True
        return False
    return symbol == BENCHMARK_SYMBOL and day > paper_start


def split_exposure(
    engine: Engine,
    paper_start: date,
    records: Iterable[Records],
    splits: Iterable[tuple[str, date]],
) -> tuple[tuple[str, date], ...]:
    """The applied ``(symbol, execution_date)`` splits, on or after ``paper_start``, that hit a
    symbol any of ``records`` (stored and replayed) held or had pending the night before; by
    (date, symbol)."""
    if engine not in ENGINES:
        raise ValueError(f"unknown engine {engine!r}")
    pool = tuple(records)
    hit: set[tuple[str, date]] = set()
    for symbol, day in splits:
        if day < paper_start:
            continue
        if any(_exposed(engine, paper_start, r, symbol, day) for r in pool):
            hit.add((symbol, day))
    return tuple(sorted(hit, key=lambda s: (s[1], s[0])))


# --------------------------------------------------------------------------- verdicts


def judge(
    head: PaperHead, stored: Records, expected: Records, splits: Iterable[tuple[str, date]]
) -> CheckResult:
    """The verdict for one started strategy."""
    found = compare(head.engine, stored, expected)
    exposed = split_exposure(head.engine, head.paper_start, (stored, expected), splits)
    if exposed:
        status: Status = "split-affected"
    elif found:
        status = "mismatch"
    else:
        status = "ok"
    return CheckResult(
        strategy_id=head.strategy_id,
        status=status,
        sessions=head.sessions,
        paper_start=head.paper_start,
        last_session=head.last_session,
        differences=found[:MAX_SHOWN],
        total_differences=len(found),
        splits=exposed,
    )


def not_started(strategy_id: str) -> CheckResult:
    """A roster strategy with no paper start and no paper state."""
    return CheckResult(strategy_id=strategy_id, status="not-started", sessions=0)


def broken(
    strategy_id: str,
    where: str,
    message: str,
    *,
    paper_start: date | None = None,
    last_session: date | None = None,
) -> CheckResult:
    """A strategy whose stored state cannot be read or replayed: a mismatch with one difference."""
    sessions = 0
    if paper_start is not None and last_session is not None:
        sessions = sessions_stepped(paper_start, last_session)
    return CheckResult(
        strategy_id=strategy_id,
        status="mismatch",
        sessions=sessions,
        paper_start=paper_start,
        last_session=last_session,
        differences=(Difference(where, message),),
        total_differences=1,
    )


def _count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def failures(results: Sequence[CheckResult], require_sessions: int) -> tuple[str, ...]:
    """Why the check fails, one line per reason (empty: it passes). A mismatch always fails;
    with ``require_sessions > 0`` so does any strategy that stepped fewer sessions (not started
    counts as 0). Split-affected never fails by itself."""
    if require_sessions < 0:
        raise ValueError(f"require_sessions must be >= 0, got {require_sessions}")
    out: list[str] = []
    for r in results:
        if r.status == "mismatch":
            out.append(f"{r.strategy_id}: replay mismatch ({_count(r.total_differences, 'difference')})")
        if require_sessions > 0 and r.sessions < require_sessions:
            out.append(f"{r.strategy_id}: {r.sessions} sessions stepped, {require_sessions} required")
    return tuple(out)


def exit_code(results: Sequence[CheckResult], require_sessions: int) -> int:
    """1 when ``failures`` is non-empty, else 0."""
    return 1 if failures(results, require_sessions) else 0


def render(results: Sequence[CheckResult]) -> tuple[str, ...]:
    """One line per strategy, then its listed differences indented, then a count of the rest."""
    width = max((len(r.strategy_id) for r in results), default=0)
    lines: list[str] = []
    for r in results:
        head = f"{r.strategy_id:<{width}}  {r.status:<14}"
        if r.status == "not-started":
            lines.append(f"{head}  no paper start")
            continue
        if r.sessions == 0 or r.paper_start is None or r.last_session is None:
            start = "-" if r.paper_start is None else r.paper_start.isoformat()
            span = f"0 sessions (starts {start})"
        else:
            span = f"{_count(r.sessions, 'session')} ({r.paper_start.isoformat()}..{r.last_session.isoformat()})"
        if r.status == "ok":
            lines.append(f"{head}  {span}")
        elif r.status == "mismatch":
            lines.append(f"{head}  {span}, {_count(r.total_differences, 'difference')}")
        else:
            hit = ", ".join(f"{symbol} on {day.isoformat()}" for symbol, day in r.splits)
            lines.append(
                f"{head}  {span}, applied split {hit}; "
                f"{_count(r.total_differences, 'difference')} not failed"
            )
        for d in r.differences:
            lines.append(f"    {d}")
        hidden = r.total_differences - len(r.differences)
        if hidden > 0:
            lines.append(f"    ... and {hidden} more")
    return tuple(lines)
```
**Impact:** This is a new pure module. Phase 1's purity glob (`paper/*.py` except `store.py`) checks it with no test edit. Its imports are:
- `seer_engine.dates`;
- the closed backtest modules (called, not edited);
- `seer_engine.paper.bracket` and `seer_engine.paper.book`;
- `seer_engine.sim`;
- `seer_engine.strategies.*`.

It has no logging, I/O or clock.

### Step 2: The `paper_check` command
**File:** `engine/src/seer_engine/commands/paper_check.py:1` (new file)

**Change:** This is the impure edge. It reads everything in one `REPEATABLE READ, READ ONLY` transaction, which gives one consistent snapshot and makes the check provably read-only. The transaction is rolled back in a `finally`. Inside it:
- the stored records come from phase 6's readers;
- the bars window is `store.load_market_window`, which reads inside the caller's transaction (phase 6), starting `store.MARKET_WINDOW_DAYS` before the earliest `paper_start`;
- the dividends are `store.dividends_between` from the earliest `paper_start` to the latest `last_session`;
- the applied splits are `store.applied_splits_between` from the earliest `paper_start` onward.

The only query the command writes itself is the list of sessions that have stored `book_targets`. Phase 6's `read_book_targets` reads one session at a time.

Errors are handled per strategy, so one bad strategy does not hide the others:
- a stored row that fails `sim` validation, or a `paper_start`/`paper_state` disagreement, gives a `broken` mismatch;
- a replay that raises, for example on a missing SPY bar, also gives a `broken` mismatch.

Every result line is logged at INFO, and every failure reason at ERROR.

**Code:**
```python
"""paper_check: the read-only replay check (D7, design §9 "one code path").

``python -m seer_engine paper_check [--require-sessions N]``

For every roster strategy with a paper start, replay it from ``paper_start`` through its last
stepped session on the bars in the database and compare every stored record with the replay
(``paper.replay``): every ``equity_snapshots`` row from day 0; A's every ``orders`` row and open
marks; the book strategies' ``book_positions``, ``book_fills`` (in order), ``book_trades`` (in
order) and every stored ``book_targets`` decision; the benchmark's SPY holding; ``paper_state``.

Read-only: everything is read in one REPEATABLE READ, READ ONLY transaction that is rolled back,
so ``--dry-run`` changes nothing. Exit 0 when every started strategy is ``ok`` or
``split-affected`` (and, with ``--require-sessions N``, every roster strategy has stepped at
least N sessions); exit 1 otherwise. Config errors exit 2 (cli).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from datetime import date, timedelta

import psycopg
from psycopg.pq import TransactionStatus

from seer_engine import db
from seer_engine.backtest.book_runner import DividendMap
from seer_engine.backtest.market import Market
from seer_engine.paper import replay, roster, store
from seer_engine.paper.replay import CheckResult, Holding, PaperHead, Records
from seer_engine.paper.roster import RosterEntry
from seer_engine.paper.store import PaperState

log = logging.getLogger(__name__)

HELP = "Replay every paper strategy from its paper start and compare it with the stored state (read-only)"

_NO_END = date(9999, 12, 31)  # applied splits have no upper bound (see paper.replay)


def _sessions_arg(value: str) -> int:
    try:
        n = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--require-sessions must be a whole number, got {value!r}") from e
    if n < 0:
        raise argparse.ArgumentTypeError(f"--require-sessions must be >= 0, got {n}")
    return n


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--require-sessions",
        type=_sessions_arg,
        default=0,
        metavar="N",
        help="also fail when any roster strategy has stepped fewer than N paper sessions",
    )


def run(args: argparse.Namespace) -> int:
    conn = db.connect()
    try:
        return execute(conn, require_sessions=int(getattr(args, "require_sessions", 0)))
    finally:
        conn.close()


def execute(conn: psycopg.Connection, *, require_sessions: int = 0) -> int:
    """Run the check against ``conn``; log one line per strategy; return 0 (pass) or 1 (fail)."""
    if require_sessions < 0:
        raise ValueError(f"require_sessions must be >= 0, got {require_sessions}")
    results = check(conn)
    for line in replay.render(results):
        log.info("paper_check: %s", line)
    reasons = replay.failures(results, require_sessions)
    for reason in reasons:
        log.error("paper_check failed: %s", reason)
    if reasons:
        return 1
    started = sum(1 for r in results if r.status != "not-started")
    log.info("paper_check: ok (%d of %d roster strategies started)", started, len(results))
    return 0


def check(conn: psycopg.Connection) -> tuple[CheckResult, ...]:
    """One ``CheckResult`` per roster entry, in roster order. Writes nothing.

    ``conn`` must have autocommit off and no transaction in progress; the read-only transaction
    this opens is always rolled back.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("paper_check needs a connection with no transaction in progress")
    try:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return _check(conn, roster.ROSTER)
    finally:
        conn.rollback()


def _check(conn: psycopg.Connection, entries: Sequence[RosterEntry]) -> tuple[CheckResult, ...]:
    starts = {row.id: row.paper_start for row in store.read_strategies(conn)}
    results: dict[str, CheckResult] = {}
    heads: dict[str, PaperHead] = {}
    stored: dict[str, Records] = {}
    for entry in entries:
        paper_start = starts.get(entry.id)
        state = store.read_paper_state(conn, entry.id)
        if paper_start is None and state is None:
            results[entry.id] = replay.not_started(entry.id)
            continue
        last_session = None if state is None else state.last_session
        if paper_start is None or state is None:
            results[entry.id] = replay.broken(
                entry.id,
                "paper_state",
                _disagreement(paper_start, state),
                paper_start=paper_start,
                last_session=last_session,
            )
            continue
        try:
            head = PaperHead(
                strategy_id=entry.id,
                engine=entry.engine,
                paper_start=paper_start,
                last_session=state.last_session,
                usd_idr=state.usd_idr,
            )
            stored[entry.id] = _stored_records(conn, entry.engine, entry.id, state)
        except (TypeError, ValueError) as exc:
            results[entry.id] = replay.broken(
                entry.id,
                "stored rows",
                f"{type(exc).__name__}: {exc}",
                paper_start=paper_start,
                last_session=last_session,
            )
            continue
        heads[entry.id] = head

    if heads:
        first = min(h.paper_start for h in heads.values())
        last = max(h.last_session for h in heads.values())
        splits = tuple((symbol, day) for symbol, day, _ in store.applied_splits_between(conn, first, _NO_END))
        market = store.load_market_window(conn, first - timedelta(days=store.MARKET_WINDOW_DAYS))
        dividends: DividendMap = store.dividends_between(conn, first, last) if last >= first else {}
        log.info(
            "paper_check: replaying %d strategies from %s (bars since %s), %d applied split(s) since",
            len(heads),
            first,
            first - timedelta(days=store.MARKET_WINDOW_DAYS),
            len(splits),
        )
        for entry in entries:
            head = heads.get(entry.id)
            if head is None:
                continue
            try:
                expected = _expected(entry, head, market, dividends)
            except Exception as exc:  # noqa: BLE001 - a replay that cannot run is that strategy's failed check
                results[entry.id] = replay.broken(
                    entry.id,
                    "replay",
                    f"{type(exc).__name__}: {exc}",
                    paper_start=head.paper_start,
                    last_session=head.last_session,
                )
                continue
            results[entry.id] = replay.judge(head, stored[entry.id], expected, splits)
    return tuple(results[e.id] for e in entries)


def _disagreement(paper_start: date | None, state: PaperState | None) -> str:
    if paper_start is None and state is not None:
        return f"paper_state has a row (last session {state.last_session}) but strategies.paper_start is NULL"
    return f"strategies.paper_start is {paper_start} but paper_state has no row"


def _stored_records(conn: psycopg.Connection, engine: str, strategy_id: str, state: PaperState) -> Records:
    common = {
        "initial_cash": state.initial_cash_usd,
        "cash": state.cash_usd,
        "equity": state.equity_usd,
        "pending_session": state.pending_session,
        "pending_decision": bool(state.pending_decision),
        "snapshots": store.read_snapshots(conn, strategy_id),
    }
    if engine == "bracket":
        rows = store.read_orders(conn, strategy_id)
        marks = tuple(sorted((o.symbol, mark) for o, mark in rows if o.status == "open"))
        return Records(**common, orders=tuple(o for o, _ in rows), marks=marks)
    if engine == "book":
        sessions = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT session_date FROM book_targets WHERE strategy_id = %s ORDER BY session_date",
                (strategy_id,),
            ).fetchall()
        ]
        targets = tuple((s, store.read_book_targets(conn, strategy_id, s)) for s in sessions)
        return Records(
            **common,
            positions=store.read_book_positions(conn, strategy_id),
            fills=store.read_book_fills(conn, strategy_id),
            trades=store.read_book_trades(conn, strategy_id),
            targets=targets,
        )
    if engine == "benchmark":
        holdings = tuple(
            Holding(symbol=p.symbol, shares=p.shares, mark=p.mark) for p in store.read_book_positions(conn, strategy_id)
        )
        return Records(**common, holdings=holdings)
    raise ValueError(f"{strategy_id}: unknown engine {engine!r}")


def _expected(entry: RosterEntry, head: PaperHead, market: Market, dividends: DividendMap) -> Records:
    if entry.engine == "bracket":
        return replay.expected_bracket(market, entry.obj, entry.params, head)
    if entry.engine == "book":
        return replay.expected_book(market, entry.obj, entry.params, entry.rules, head, dividends)
    if entry.engine == "benchmark":
        return replay.expected_benchmark(market, head, dividends)
    raise ValueError(f"{entry.id}: unknown engine {entry.engine!r}")
```
**Impact:**
- This is a new command module. `cli.discover()` picks it up, and `cli.py` does not change.
- It writes nothing. The only statements it runs are `SET TRANSACTION`, SELECTs, and the `SET LOCAL datestyle` and `COPY ... TO STDOUT` that `read_bars_frame` issues inside `load_market_window`. All of these are allowed in a READ ONLY transaction.
- Run time on Neon is one windowed bars COPY plus the replays. The analysis measured the COPY at about 2.7 s for 326k rows. Replaying A over a few months with single-window picks takes seconds.

### Step 3: Pure unit tests
**File:** `engine/tests/test_paper_replay.py:1` (new file)

**Change:** The tests use an in-memory market of three symbols (AAA, BBB, SPY, 2025-02-18..2025-03-14), together with:
- `FixedPicks`, a fake `Strategy` that returns a fixed pick table;
- `allocatorkit.FIXED` under `MONTHLY_HOLD`.

The market's own fx is 15000, while the head holds 16000. That proves the bracket replay converts at the stored rate. Each expected record is checked against the runner it wraps (`run_backtest`, `run_book`, `buy_and_hold`).

The scenario was hand-run on the current tree:
- **Bracket.** AAA fills on 03-04 at 10.0000 for 31 shares and is still open on 03-07, with mark 10.4000. BBB's order for 03-06 expires. BBB is pending for 03-10.
- **Book.** It buys 58 AAA and 23 BBB on 03-03. AAA's dividend of 0.25 on 03-05 credits 14.5000.
- **Benchmark.** It holds 2 SPY with cash 249.9980 and 3.0000 in dividends.

Difference text, split exposure, verdicts, the exit code and rendering are asserted exactly.

**Code:**
```python
"""paper.replay: the pure half of the replay check (plan phase 8).

An in-memory market (AAA, BBB, SPY on 2025-02-18..2025-03-14), a fixed-pick fake strategy for
the bracket engine and ``allocatorkit.FIXED`` under ``MONTHLY_HOLD`` for the book engine. The
market's own fx (15000) differs from the stored rate (16000), so a bracket replay that ignored
the stored rate would show. Every expected record is checked against the runner it wraps.
"""

from __future__ import annotations

from collections.abc import Mapping, Set as AbstractSet
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from allocatorkit import FIXED, FixedParams
from simkit import D, P, bar

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend, buy_and_hold
from seer_engine.backtest.book_runner import run_book
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import INITIAL_IDR, run_backtest
from seer_engine.paper import replay
from seer_engine.paper.replay import CheckResult, Difference, Holding, PaperHead, Records
from seer_engine.prices import Bar
from seer_engine.sim import MONTHLY_HOLD, Pick, Portfolio, Snapshot, Trade, initial_cash_usd, size_picks
from seer_engine.strategies.base import History, history_from_bars

FIRST, LAST_BAR = D("2025-02-18"), D("2025-03-14")
USD_IDR = Decimal("16000")
CASH0 = initial_cash_usd(INITIAL_IDR, USD_IDR)  # 1250.0000


def _bars(symbol: str, special: Mapping[str, tuple[str, str, str, str]], default: tuple[str, str, str, str]) -> list[Bar]:
    return [bar(symbol, d, *special.get(d.isoformat(), default)) for d in dates.sessions(FIRST, LAST_BAR)]


AAA = _bars(
    "AAA",
    {
        "2025-03-04": ("10.4", "10.5", "9.8", "10.1"),  # the bracket limit 10 fills (low < limit)
        "2025-03-05": ("10.1", "10.3", "10.0", "10.2"),
        "2025-03-10": ("10.4", "11.2", "10.3", "11.0"),
    },
    ("10.4", "10.6", "10.1", "10.4"),
)
BBB = _bars("BBB", {}, ("21", "21.2", "20.8", "21"))  # a limit of 20 never fills
SPY_BARS = _bars("SPY", {"2025-03-04": ("500", "503", "499", "502")}, ("501", "502", "500", "501"))


def market() -> Market:
    return Market(
        history={
            "AAA": history_from_bars("AAA", AAA),
            "BBB": history_from_bars("BBB", BBB),
            "SPY": history_from_bars("SPY", SPY_BARS),
        },
        membership=Membership((("AAA", D("2020-01-02"), None), ("BBB", D("2020-01-02"), None))),
        fx=((D("2025-01-02"), Decimal("15000")),),
    )


def pick(symbol: str, limit: str, tp: str, sl: str) -> Pick:
    return Pick(symbol, P(limit), P(limit), P(tp), P(sl))


class FixedPicks:
    """A fake ``Strategy``: fixed ranked picks per data_date, members only."""

    id = "FIXED"
    lookback = 1

    def __init__(self, table: Mapping[date, tuple[Pick, ...]]):
        self.table = dict(table)

    def _picks(self, members: AbstractSet[str], data_date: date) -> list[Pick]:
        return [p for p in self.table.get(data_date, ()) if p.symbol in members]

    def picks(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date, params: Any) -> list[Pick]:
        return self._picks(members, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return None

    def picks_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date, params: Any) -> list[Pick]:
        return self._picks(members, data_date)


PICKS = FixedPicks(
    {
        D("2025-03-03"): (pick("AAA", "10", "11", "9"),),  # -> 03-04: fills, open at the end
        D("2025-03-05"): (pick("BBB", "20", "22", "18"),),  # -> 03-06: expires
        D("2025-03-07"): (pick("AAA", "10", "11", "9"), pick("BBB", "20", "22", "18")),  # -> 03-10: AAA held, BBB pending
    }
)
FIXED_PARAMS = FixedParams(weights=(("AAA", Decimal("0.5")), ("BBB", Decimal("0.4"))))
DIVIDENDS = {"AAA": {D("2025-03-05"): Decimal("0.25")}, "SPY": {D("2025-03-05"): Decimal("1.5")}}

BRACKET_HEAD = PaperHead("A", "bracket", D("2025-03-04"), D("2025-03-07"), USD_IDR)
BOOK_HEAD = PaperHead("F", "book", D("2025-02-26"), D("2025-03-05"), USD_IDR)
SPY_HEAD = PaperHead("SPY", "benchmark", D("2025-03-03"), D("2025-03-07"), USD_IDR)


def _bracket(head: PaperHead = BRACKET_HEAD) -> Records:
    return replay.expected_bracket(market(), PICKS, None, head)


def _book(head: PaperHead = BOOK_HEAD) -> Records:
    return replay.expected_book(market(), FIXED, FIXED_PARAMS, MONTHLY_HOLD, head, DIVIDENDS)


def _benchmark(head: PaperHead = SPY_HEAD) -> Records:
    return replay.expected_benchmark(market(), head, DIVIDENDS)


# ---- expected records --------------------------------------------------------------------------


def test_expected_bracket_is_run_backtest_at_the_stored_rate():
    m = market()
    got = _bracket()
    fixed = Market(history=m.history, membership=m.membership, fx=((BRACKET_HEAD.paper_start, USD_IDR),))
    run = run_backtest(fixed, PICKS, None, BRACKET_HEAD.paper_start, BRACKET_HEAD.last_session)
    assert got.snapshots == run.snapshots
    assert got.initial_cash == CASH0 == run.initial_cash
    assert (got.cash, got.equity) == (run.snapshots[-1].cash_usd, run.snapshots[-1].equity_usd)
    assert got.pending_session == D("2025-03-10")
    assert {(o.session_date, o.symbol): o.status for o in got.orders} == {
        (D("2025-03-04"), "AAA"): "open",
        (D("2025-03-06"), "BBB"): "expired",
        (D("2025-03-10"), "BBB"): "pending",
    }
    assert got.marks == (("AAA", P("10.4")),)
    end = Portfolio(
        cash=got.cash, equity=got.equity, orders=run.open_at_end, marks=got.marks, last_session=BRACKET_HEAD.last_session
    )
    direct = size_picks(
        end,
        PICKS.picks({}, m.membership.members_on(BRACKET_HEAD.last_session), BRACKET_HEAD.last_session, None),
        D("2025-03-10"),
    )
    assert tuple(o for o in got.orders if o.status == "pending") == direct.portfolio.pending_orders()


def test_expected_bracket_first_night_is_day0_plus_the_first_decision():
    got = _bracket(replace(BRACKET_HEAD, last_session=D("2025-03-03")))
    assert got.snapshots == (Snapshot(D("2025-03-03"), CASH0, CASH0),)
    assert [(o.session_date, o.symbol, o.status) for o in got.orders] == [(D("2025-03-04"), "AAA", "pending")]
    assert got.marks == ()
    assert (got.cash, got.equity, got.pending_session) == (CASH0, CASH0, D("2025-03-04"))


def test_expected_book_is_run_book_with_every_decision():
    m = market()
    got = _book()
    run = run_book(
        m, FIXED, FIXED_PARAMS, MONTHLY_HOLD, BOOK_HEAD.paper_start, BOOK_HEAD.last_session, dividends=DIVIDENDS, usd_idr=USD_IDR
    )
    assert got.snapshots == tuple(Snapshot(s.date, s.cash_usd, s.equity_usd) for s in run.snapshots)
    assert got.fills == run.fills and len(got.fills) == 2
    assert got.trades == run.trades
    assert got.positions == run.open_at_end
    assert {p.symbol for p in got.positions} == {"AAA", "BBB"}
    assert run.dividends_usd == P("14.5")
    assert [s for s, _ in got.targets] == [D("2025-03-03")]  # the first session of March only
    assert [t.symbol for t in got.targets[0][1]] == ["AAA", "BBB"]
    assert got.pending_session == D("2025-03-06") and got.pending_decision is False
    assert got.initial_cash == CASH0


def test_expected_book_pending_decision_on_the_night_before_a_decision_session():
    got = _book(replace(BOOK_HEAD, last_session=D("2025-02-28")))
    assert got.pending_session == D("2025-03-03")
    assert got.pending_decision is True
    assert [s for s, _ in got.targets] == [D("2025-03-03")]
    assert got.positions == () and got.fills == ()


def test_expected_book_first_night():
    got = _book(replace(BOOK_HEAD, last_session=D("2025-02-25")))
    assert got.snapshots == (Snapshot(D("2025-02-25"), CASH0, CASH0),)
    assert got.targets == () and got.pending_decision is False  # 2025-02-26 is no monthly decision


def test_expected_benchmark_is_buy_and_hold_with_spy_dividends():
    m = market()
    got = _benchmark()
    curve = buy_and_hold(
        m.spy(), SPY_HEAD.paper_start, SPY_HEAD.last_session, CASH0,
        dividends=(Dividend(D("2025-03-05"), Decimal("1.5")),), name="SPY",
    )
    assert curve.dividends_usd == P("3")
    assert got.snapshots == curve.snapshots
    assert got.cash == curve.cash == P("249.998")
    assert got.holdings == (Holding("SPY", Decimal(curve.shares), P("501")),)
    assert curve.shares == 2


def test_expected_benchmark_first_night_holds_cash_only():
    got = _benchmark(replace(SPY_HEAD, last_session=D("2025-02-28")))
    assert got.snapshots == (Snapshot(D("2025-02-28"), CASH0, CASH0),)
    assert got.holdings == () and got.cash == CASH0


def test_held_before_rebuilds_the_held_set_from_fills():
    fills = _book().fills
    assert replay.held_before(fills, D("2025-03-03")) == frozenset()
    assert replay.held_before(fills, D("2025-03-04")) == frozenset({"AAA", "BBB"})


def test_last_close_is_the_latest_bar_on_or_before():
    m = market()
    assert replay.last_close(m, "AAA", D("2025-03-04")) == P("10.1")
    assert replay.last_close(m, "AAA", D("2025-03-08")) == P("10.4")  # Saturday: Friday's close
    with pytest.raises(ValueError, match="no bar"):
        replay.last_close(m, "CCC", D("2025-03-04"))


def test_wrong_engine_is_refused():
    with pytest.raises(ValueError, match="not bracket"):
        replay.expected_bracket(market(), PICKS, None, BOOK_HEAD)
    with pytest.raises(ValueError, match="not book"):
        replay.expected_book(market(), FIXED, FIXED_PARAMS, MONTHLY_HOLD, SPY_HEAD, DIVIDENDS)
    with pytest.raises(ValueError, match="not benchmark"):
        replay.expected_benchmark(market(), BRACKET_HEAD, DIVIDENDS)


# ---- comparison ---------------------------------------------------------------------------------


def test_identical_records_have_no_difference():
    assert replay.compare("bracket", _bracket(), _bracket()) == ()
    assert replay.compare("book", _book(), _book()) == ()
    assert replay.compare("benchmark", _benchmark(), _benchmark()) == ()


def test_snapshot_difference_is_readable():
    exp = _bracket()
    s = exp.snapshots[2]
    snaps = list(exp.snapshots)
    snaps[2] = Snapshot(s.date, s.cash_usd, s.equity_usd + 1)
    diffs = replay.compare("bracket", replace(exp, snapshots=tuple(snaps)), exp)
    assert [str(d) for d in diffs] == [
        f"snapshot {s.date.isoformat()}: equity_usd stored {format(s.equity_usd + 1, 'f')}, replay {format(s.equity_usd, 'f')}"
    ]


def test_missing_and_extra_snapshots():
    exp = _bracket()
    diffs = replay.compare("bracket", replace(exp, snapshots=exp.snapshots[:-1]), exp)
    assert [str(d) for d in diffs] == ["snapshot 2025-03-07: in the replay, missing from the database"]
    extra = exp.snapshots + (Snapshot(D("2025-03-10"), CASH0, CASH0),)
    diffs = replay.compare("bracket", replace(exp, snapshots=extra), exp)
    assert [str(d) for d in diffs] == ["snapshot 2025-03-10: in the database, not in the replay"]


def test_missing_pending_order_and_changed_order_field():
    exp = _bracket()
    assert [str(d) for d in replay.compare("bracket", replace(exp, orders=exp.orders[:-1]), exp)] == [
        "order 2025-03-10 BBB: in the replay, missing from the database"
    ]
    first = exp.orders[0]
    changed = (replace(first, days_held=first.days_held + 1),) + exp.orders[1:]
    assert [str(d) for d in replay.compare("bracket", replace(exp, orders=changed), exp)] == [
        f"order 2025-03-04 AAA: days_held stored {first.days_held + 1}, replay {first.days_held}"
    ]


def test_mark_difference():
    exp = _bracket()
    diffs = replay.compare("bracket", replace(exp, marks=(("AAA", P("10.5")),)), exp)
    assert [str(d) for d in diffs] == ["mark AAA: stored 10.5000, replay 10.4000"]
    diffs = replay.compare("bracket", replace(exp, marks=(("AAA", None),)), exp)
    assert [str(d) for d in diffs] == ["mark AAA: stored none, replay 10.4000"]


def test_book_position_fill_trade_and_target_differences():
    exp = _book()
    pos = exp.positions[0]
    stored = replace(exp, positions=(replace(pos, shares=pos.shares + 1),) + exp.positions[1:])
    assert [str(d) for d in replay.compare("book", stored, exp)] == [
        f"position {pos.symbol}: shares stored {format(pos.shares + 1, 'f')}, replay {format(pos.shares, 'f')}"
    ]
    fill = exp.fills[0]
    stored = replace(exp, fills=(replace(fill, price=fill.price + P("0.01")),) + exp.fills[1:])
    assert [str(d) for d in replay.compare("book", stored, exp)] == [
        f"fill #1 (2025-03-03 buy AAA): price stored {format(fill.price + P('0.01'), 'f')}, replay {format(fill.price, 'f')}"
    ]
    fake = Trade(
        symbol="AAA",
        entry_date=D("2025-03-03"),
        exit_date=D("2025-03-04"),
        entry_price=P("10.4"),
        exit_price=P("10.1"),
        days_held=2,
        cost_usd=P("0.02"),
        income_usd=P("0"),
        pnl_usd=P("-0.32"),
        exit_reason="signal",
        idle=False,
    )
    stored = replace(exp, trades=exp.trades + (fake,))
    assert [str(d) for d in replay.compare("book", stored, exp)] == [
        f"trade #{len(exp.trades) + 1} (AAA 2025-03-03..2025-03-04): in the database, not in the replay"
    ]
    session, targets = exp.targets[0]
    halved = (replace(targets[0], weight=targets[0].weight / 2),) + targets[1:]
    stored = replace(exp, targets=((session, halved),))
    assert [str(d) for d in replay.compare("book", stored, exp)] == [
        f"target 2025-03-03 rank 1: weight stored {format(targets[0].weight / 2, 'f')}, replay {format(targets[0].weight, 'f')}"
    ]


def test_pending_decision_is_compared_for_book_only():
    exp = _book()
    assert [str(d) for d in replay.compare("book", replace(exp, pending_decision=True), exp)] == [
        "paper_state: pending_decision stored true, replay false"
    ]
    br = _bracket()
    assert replay.compare("bracket", replace(br, pending_decision=True), br) == ()
    bm = _benchmark()
    assert replay.compare("benchmark", replace(bm, pending_decision=True, pending_session=None), bm) == ()


def test_benchmark_holding_and_state_differences():
    exp = _benchmark()
    h = exp.holdings[0]
    stored = replace(exp, holdings=(Holding(h.symbol, h.shares + 1, h.mark),), cash=exp.cash - 1)
    assert [str(d) for d in replay.compare("benchmark", stored, exp)] == [
        f"holding SPY: shares stored {format(h.shares + 1, 'f')}, replay {format(h.shares, 'f')}",
        f"paper_state: cash stored {format(exp.cash - 1, 'f')}, replay {format(exp.cash, 'f')}",
    ]


def test_unknown_engine_is_refused():
    with pytest.raises(ValueError, match="unknown engine"):
        replay.compare("other", _bracket(), _bracket())  # type: ignore[arg-type]


# ---- splits -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("symbol", "day", "hit"),
    [
        ("AAA", "2025-03-05", True),  # open since 03-04
        ("BBB", "2025-03-06", True),  # pending for 03-06 the night before (it then expired)
        ("BBB", "2025-03-05", False),  # nothing live on BBB the night before 03-05
        ("BBB", "2025-03-10", True),  # pending for 03-10
        ("AAA", "2025-03-03", False),  # before paper_start
        ("CCC", "2025-03-05", False),
    ],
)
def test_bracket_split_exposure(symbol, day, hit):
    got = replay.split_exposure("bracket", BRACKET_HEAD.paper_start, (_bracket(),), [(symbol, D(day))])
    assert got == (((symbol, D(day)),) if hit else ())


def test_bracket_order_closed_before_the_split_is_not_exposed():
    exp = _bracket()
    first = exp.orders[0]
    closed = replace(
        first, status="closed", exit_date=D("2025-03-05"), exit_price=P("11"), exit_reason="tp", pnl_usd=P("1")
    )
    rec = replace(exp, orders=(closed,))
    assert replay.split_exposure("bracket", BRACKET_HEAD.paper_start, (rec,), [("AAA", D("2025-03-06"))]) == ()
    assert replay.split_exposure("bracket", BRACKET_HEAD.paper_start, (rec,), [("AAA", D("2025-03-05"))]) == (
        ("AAA", D("2025-03-05")),
    )


@pytest.mark.parametrize(
    ("symbol", "day", "hit"),
    [
        ("AAA", "2025-03-04", True),  # held since 03-03
        ("AAA", "2025-03-03", True),  # targeted for 03-03
        ("BBB", "2025-02-27", False),
        ("AAA", "2025-02-26", False),
    ],
)
def test_book_split_exposure(symbol, day, hit):
    got = replay.split_exposure("book", BOOK_HEAD.paper_start, (_book(),), [(symbol, D(day))])
    assert got == (((symbol, D(day)),) if hit else ())


def test_book_trade_spanning_the_split_is_exposed():
    exp = _book()
    trade = Trade(
        symbol="CCC",
        entry_date=D("2025-02-27"),
        exit_date=D("2025-03-03"),
        entry_price=P("5"),
        exit_price=P("5"),
        days_held=3,
        cost_usd=P("0.01"),
        income_usd=P("0"),
        pnl_usd=P("-0.02"),
        exit_reason="signal",
        idle=False,
    )
    rec = replace(exp, trades=(trade,))
    assert replay.split_exposure("book", BOOK_HEAD.paper_start, (rec,), [("CCC", D("2025-03-03"))]) == (
        ("CCC", D("2025-03-03")),
    )
    assert replay.split_exposure("book", BOOK_HEAD.paper_start, (rec,), [("CCC", D("2025-02-27"))]) == ()


def test_benchmark_split_exposure_starts_after_the_first_session():
    exp = _benchmark()
    start = SPY_HEAD.paper_start
    assert replay.split_exposure("benchmark", start, (exp,), [("SPY", start)]) == ()
    nxt = dates.next_session(start)
    assert replay.split_exposure("benchmark", start, (exp,), [("SPY", nxt), ("AAA", nxt)]) == (("SPY", nxt),)


# ---- verdicts -----------------------------------------------------------------------------------


def test_judge_ok_mismatch_and_split_affected():
    exp = _bracket()
    ok = replay.judge(BRACKET_HEAD, exp, exp, ())
    assert (ok.status, ok.sessions, ok.differences, ok.total_differences, ok.splits) == ("ok", 4, (), 0, ())
    assert (ok.paper_start, ok.last_session) == (D("2025-03-04"), D("2025-03-07"))
    bad = replay.judge(BRACKET_HEAD, replace(exp, cash=exp.cash + 1), exp, ())
    assert bad.status == "mismatch" and bad.total_differences == 1
    hit = replay.judge(BRACKET_HEAD, replace(exp, cash=exp.cash + 1), exp, [("AAA", D("2025-03-05"))])
    assert hit.status == "split-affected" and hit.splits == (("AAA", D("2025-03-05")),)
    assert hit.total_differences == 1


def test_judge_lists_at_most_max_shown(monkeypatch):
    monkeypatch.setattr(replay, "MAX_SHOWN", 3)
    exp = _bracket()
    snaps = tuple(Snapshot(s.date, s.cash_usd + 1, s.equity_usd + 1) for s in exp.snapshots)
    r = replay.judge(BRACKET_HEAD, replace(exp, snapshots=snaps), exp, ())
    assert len(r.differences) == 3 and r.total_differences == 10
    assert replay.render((r,))[-1] == "    ... and 7 more"


def test_not_started_and_broken():
    r = replay.not_started("F1")
    assert (r.status, r.sessions, r.differences) == ("not-started", 0, ())
    b = replay.broken("A", "replay", "boom", paper_start=D("2025-03-04"), last_session=D("2025-03-07"))
    assert b.status == "mismatch" and b.sessions == 4 and [str(d) for d in b.differences] == ["replay: boom"]
    assert replay.broken("A", "paper_state", "x", paper_start=D("2025-03-04")).sessions == 0


def test_exit_code_and_failures():
    ok = CheckResult("A", "ok", 5)
    split = CheckResult("SPY", "split-affected", 5)
    new = replay.not_started("F1")
    bad = CheckResult("F4", "mismatch", 5, total_differences=2)
    assert replay.exit_code((ok, split, new), 0) == 0
    assert replay.exit_code((ok, split, new), 1) == 1
    assert replay.exit_code((ok, split), 5) == 0
    assert replay.exit_code((ok, split), 6) == 1
    assert replay.exit_code((ok, bad), 0) == 1
    assert replay.failures((ok, bad, new), 1) == (
        "F4: replay mismatch (2 differences)",
        "F1: 0 sessions stepped, 1 required",
    )
    with pytest.raises(ValueError):
        replay.failures((ok,), -1)


def test_render_one_line_per_strategy_then_its_differences():
    exp = _bracket()
    bad = replay.judge(BRACKET_HEAD, replace(exp, cash=exp.cash + 1), exp, ())
    lines = replay.render((bad, replay.not_started("F1-SPY-SMA200-M")))
    assert lines[0].split() == ["A", "mismatch", "4", "sessions", "(2025-03-04..2025-03-07),", "1", "difference"]
    assert lines[1] == f"    paper_state: cash stored {format(exp.cash + 1, 'f')}, replay {format(exp.cash, 'f')}"
    assert lines[2].split() == ["F1-SPY-SMA200-M", "not-started", "no", "paper", "start"]
    split = replay.judge(BRACKET_HEAD, exp, exp, [("AAA", D("2025-03-05"))])
    assert replay.render((split,))[0].endswith("applied split AAA on 2025-03-05; 0 differences not failed")
    first = replay.judge(replace(BRACKET_HEAD, last_session=D("2025-03-03")), exp, exp, ())
    assert "0 sessions (starts 2025-03-04)" in replay.render((first,))[0]


def test_paper_head_validation():
    with pytest.raises(ValueError, match="before the day-0 session"):
        PaperHead("A", "bracket", D("2025-03-04"), D("2025-02-28"), USD_IDR)
    with pytest.raises(ValueError, match="unknown engine"):
        PaperHead("A", "other", D("2025-03-04"), D("2025-03-07"), USD_IDR)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not an NYSE session"):
        PaperHead("A", "bracket", D("2025-03-08"), D("2025-03-10"), USD_IDR)
    with pytest.raises(TypeError, match="usd_idr"):
        PaperHead("A", "bracket", D("2025-03-04"), D("2025-03-07"), 16000)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="usd_idr"):
        PaperHead("A", "bracket", D("2025-03-04"), D("2025-03-07"), Decimal("0"))
    assert PaperHead("A", "bracket", D("2025-03-04"), D("2025-03-03"), USD_IDR).sessions == 0


def test_difference_str():
    assert str(Difference("snapshot 2025-03-04", "missing")) == "snapshot 2025-03-04: missing"
```
**Impact:** These are new tests only. `allocatorkit` and `simkit` are imported unchanged, the same way existing test modules import them.

### Step 4: PG tests against real `paper` nights
**File:** `engine/tests/test_paper_check.py:1` (new file)

**Change:** The tests build a self-contained synthetic world, with the same data on every run. Phase 7's random world is not reused, for three reasons: A must trade, the tampers need specific rows to exist, and the tests should not depend on another phase's test module. The world is:
- **24 members, `S00`..`S23`.** Each follows an 8-session sawtooth of `+0.5 × 5, −0.75 × 3`. Each symbol starts at `10 + k/2`, its phase is offset by `k`, `low = min(o, c) − 1` and volume is 3,000,000.
- **SPY.** It rises by 0.25 each session from 400.
- **Bars.** They run from 2025-05-01 to 2026-11-13, so they extend past the last night and a look-ahead would show.
- **FX.** One row: USD/IDR 16500.
- **Dividend.** One SPY dividend, 1.85 on 2026-10-28.

**Nights.** There are 8 nights: 2026-10-23 (the first night, `paper_start = 2026-10-26`), 10-26, 10-27, 10-28, 10-29, 10-30, 11-02 and 11-03. That steps 7 sessions, and 11-02 is the monthly decision for F4 and F1.

Hand-run on the current tree with `run_rules`, this world gives:
- **A.** Picks every night. 12 orders close at tp, 3 orders are open at the end, and one is pending.
- **F4.** 20 targets and 20 entries on 11-02.
- **F1.** Holds SPY.
- **SPY.** Holds 2 shares and is credited the dividend.

**Code:**
```python
"""`paper_check` on Postgres: real `paper` nights over a synthetic world, then the replay check.

The world: 24 members S00..S23 on an 8-session sawtooth (+0.5 x 5, -0.75 x 3; a 3-day dip puts
RSI(2) under 10 above a rising SMA(200), so A picks every night and its trades close at tp), SPY
rising 0.25 a session, one USD/IDR row, one SPY dividend. Bars run past the last night. Eight
nights: the first (2026-10-23) starts paper on 2026-10-26; the rest step 7 sessions through
2026-11-03, with 2026-11-02 the monthly decision for F4 and F1.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from functools import lru_cache

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, cli, dates, db, fx
from seer_engine.commands import paper, paper_check
from seer_engine.paper import replay
from seer_engine.prices import Bar

UTC = timezone.utc
HIST_START = date(2025, 5, 1)
HIST_END = date(2026, 11, 13)
MEMBERS = tuple(f"S{k:02d}" for k in range(24))
CYCLE = tuple(Decimal(x) for x in ("0.5", "0.5", "0.5", "0.5", "0.5", "-0.75", "-0.75", "-0.75"))
USD_IDR = Decimal("16500.0000")
SPY_EX_DATE = date(2026, 10, 28)
SPY_DIVIDEND = Decimal("1.850000")

NIGHTS = (
    date(2026, 10, 23),  # first night: paper_start = 2026-10-26
    date(2026, 10, 26),
    date(2026, 10, 27),
    date(2026, 10, 28),
    date(2026, 10, 29),
    date(2026, 10, 30),  # decides 2026-11-02, the first session of November (F4, F1)
    date(2026, 11, 2),
    date(2026, 11, 3),
)
PAPER_START = date(2026, 10, 26)
LAST = date(2026, 11, 3)
DAY0 = date(2026, 10, 23)
NOV2 = date(2026, 11, 2)
F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"
ROSTER_IDS = ("SPY", "A", F4, F1)


# ---- the synthetic world -----------------------------------------------------------------------


@lru_cache(maxsize=1)
def synthetic_bars() -> tuple[Bar, ...]:
    days = dates.sessions(HIST_START, HIST_END)
    out: list[Bar] = []
    for k, symbol in enumerate(MEMBERS):
        close = Decimal(10) + Decimal(k) / 2
        for t, d in enumerate(days):
            o = close
            c = o + CYCLE[(t + k) % len(CYCLE)]
            out.append(Bar(symbol, d, o, max(o, c) + Decimal("0.125"), min(o, c) - 1, c, 3_000_000))
            close = c
    spy = Decimal(400)
    for d in days:
        o = spy
        c = o + Decimal("0.25")
        out.append(Bar("SPY", d, o, c + Decimal("0.5"), o - Decimal("0.5"), c, 80_000_000))
        spy = c
    return tuple(out)


@pytest.fixture
def world(pg):
    with db.transaction(pg, False):
        bars.upsert_bars(pg, synthetic_bars())
        fx.upsert_fx(pg, [(HIST_START, USD_IDR)])
        for s in MEMBERS:
            pg.execute(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, 'SP500', '2000-01-03', NULL, %s)",
                (s, s),
            )
        pg.execute(
            "INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, %s)", (SPY_EX_DATE, SPY_DIVIDEND)
        )
    return pg


def night(conn, d: date) -> None:
    """The real runs row a successful bars run writes for the night of ``d``, then ``paper``."""
    now = datetime(d.year, d.month, d.day, 23, tzinfo=UTC)
    rd = dates.run_dates(now)
    with db.transaction(conn, False):
        conn.execute(
            """
            INSERT INTO runs (status, data_date, session_date, is_demo, finished_at)
            VALUES ('success', %s, %s, false, now())
            ON CONFLICT (session_date) WHERE NOT is_demo DO NOTHING
            """,
            (rd.data_date, rd.session_date),
        )
    assert paper.execute(conn, now=now) == 0, f"paper failed on the night of {d}"


@pytest.fixture
def stepped(world):
    for d in NIGHTS:
        night(world, d)
    return world


def q(conn, sql, params=()):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.rollback()
    return rows


def results(conn) -> dict[str, replay.CheckResult]:
    return {r.strategy_id: r for r in paper_check.check(conn)}


def text(found: dict[str, replay.CheckResult]) -> str:
    return "\n".join(replay.render(tuple(found.values())))


def tamper(conn, sql: str, params=()) -> None:
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            assert cur.rowcount >= 1, f"the tamper touched no row: {sql}"


# Whole rows of every table paper state lives in: the check must leave them all unchanged.
TABLES = {
    "paper_state": "strategy_id",
    "book_positions": "strategy_id, symbol",
    "book_targets": "strategy_id, session_date, rank",
    "book_fills": "id",
    "book_trades": "id",
    "orders": "id",
    "equity_snapshots": "strategy_id, date",
    "strategies": "id",
    "runs": "id",
    "bars": "symbol, date",
    "dividends": "symbol, ex_date",
    "split_adjustments": "symbol, execution_date",
}


def everything(conn):
    return {t: q(conn, f"SELECT x::text FROM {t} x ORDER BY {order}") for t, order in TABLES.items()}


# ---- not started and the first night -----------------------------------------------------------


def test_paper_check_is_a_command():
    assert "paper_check" in cli.discover()


def test_fresh_database_reports_every_strategy_not_started(pg):
    found = results(pg)
    assert tuple(found) == ROSTER_IDS
    assert {r.status for r in found.values()} == {"not-started"}
    assert paper_check.execute(pg) == 0
    assert paper_check.execute(pg, require_sessions=1) == 1


def test_first_night_only_is_ok_with_zero_sessions(world):
    night(world, NIGHTS[0])
    found = results(world)
    for sid in ROSTER_IDS:
        r = found[sid]
        assert r.status == "ok", text(found)
        assert (r.sessions, r.paper_start, r.last_session) == (0, PAPER_START, DAY0)
    assert q(world, "SELECT count(*) FROM orders WHERE strategy_id = 'A' AND status = 'pending'") >= [(1,)]
    assert paper_check.execute(world) == 0
    assert paper_check.execute(world, require_sessions=1) == 1


# ---- eight nights ------------------------------------------------------------------------------


def test_eight_nights_equal_the_replay(stepped):
    found = results(stepped)
    for sid in ROSTER_IDS:
        r = found[sid]
        assert r.status == "ok", text(found)
        assert (r.sessions, r.paper_start, r.last_session) == (7, PAPER_START, LAST)
    # The check was not vacuous: every record kind it compares exists.
    assert q(stepped, "SELECT count(*) FROM orders WHERE strategy_id = 'A' AND status = 'closed'")[0][0] >= 1
    assert q(stepped, "SELECT count(*) FROM orders WHERE strategy_id = 'A' AND status = 'open'")[0][0] >= 1
    assert q(stepped, "SELECT count(*) FROM orders WHERE strategy_id = 'A' AND status = 'pending'")[0][0] >= 1
    assert q(stepped, "SELECT count(*) FROM book_positions WHERE strategy_id = %s", (F4,))[0][0] >= 1
    assert q(stepped, "SELECT count(*) FROM book_targets WHERE strategy_id = %s AND session_date = %s", (F4, NOV2))[0][0] >= 1
    assert q(stepped, "SELECT symbol FROM book_positions WHERE strategy_id = %s", (F1,)) == [("SPY",)]
    assert q(stepped, "SELECT symbol FROM book_positions WHERE strategy_id = 'SPY'") == [("SPY",)]
    assert paper_check.execute(stepped, require_sessions=7) == 0
    assert paper_check.execute(stepped, require_sessions=8) == 1


def test_check_writes_nothing(stepped):
    before = everything(stepped)
    assert paper_check.execute(stepped, require_sessions=7) == 0
    assert everything(stepped) == before


def test_execute_logs_a_line_per_strategy_and_each_failure(stepped, caplog):
    caplog.set_level(logging.INFO, logger="seer_engine.commands.paper_check")
    assert paper_check.execute(stepped, require_sessions=8) == 1
    for sid in ROSTER_IDS:
        assert f"paper_check: {sid} " in caplog.text
    assert "paper_check failed: SPY: 7 sessions stepped, 8 required" in caplog.text


TAMPERS = [
    pytest.param(
        "UPDATE equity_snapshots SET equity_usd = equity_usd + 1 WHERE strategy_id = 'A' AND date = DATE '2026-10-28'",
        "A",
        "snapshot 2026-10-28: equity_usd stored",
        id="snapshot",
    ),
    pytest.param(
        "UPDATE equity_snapshots SET cash_usd = cash_usd - 1 WHERE strategy_id = 'SPY' AND date = DATE '2026-10-23'",
        "SPY",
        "snapshot 2026-10-23: cash_usd stored",
        id="day0-snapshot",
    ),
    pytest.param(
        "UPDATE orders SET pnl_usd = pnl_usd + 1 "
        "WHERE id = (SELECT min(id) FROM orders WHERE strategy_id = 'A' AND status = 'closed')",
        "A",
        ": pnl_usd stored",
        id="closed-order",
    ),
    pytest.param(
        "DELETE FROM orders WHERE id = (SELECT max(id) FROM orders WHERE strategy_id = 'A' AND status = 'pending')",
        "A",
        "in the replay, missing from the database",
        id="pending-order",
    ),
    pytest.param(
        "UPDATE orders SET mark = mark + 1 "
        "WHERE id = (SELECT min(id) FROM orders WHERE strategy_id = 'A' AND status = 'open')",
        "A",
        ": stored",
        id="open-mark",
    ),
    pytest.param(
        "UPDATE book_positions SET shares = shares + 1 WHERE strategy_id = 'F1-SPY-SMA200-M' AND symbol = 'SPY'",
        F1,
        "position SPY: shares stored",
        id="position",
    ),
    pytest.param(
        "UPDATE book_targets SET weight = weight / 2 "
        "WHERE strategy_id = 'F4-MOM12-N20-TREND' AND session_date = DATE '2026-11-02' AND rank = 1",
        F4,
        "target 2026-11-02 rank 1: weight stored",
        id="target",
    ),
    pytest.param(
        "UPDATE book_fills SET price = price + 0.01 "
        "WHERE strategy_id = 'F4-MOM12-N20-TREND' AND session_date = DATE '2026-11-02' AND seq = 1",
        F4,
        ": price stored",
        id="fill",
    ),
    pytest.param(
        "INSERT INTO book_trades (strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, days_held, "
        "cost_usd, income_usd, pnl_usd, exit_reason, idle) VALUES ('F4-MOM12-N20-TREND', 'S00', "
        "DATE '2026-10-26', DATE '2026-10-27', 10, 11, 2, 0.02, 0, 0.98, 'signal', false)",
        F4,
        "in the database, not in the replay",
        id="trade",
    ),
    pytest.param(
        "UPDATE paper_state SET pending_decision = NOT pending_decision WHERE strategy_id = 'F1-SPY-SMA200-M'",
        F1,
        "paper_state: pending_decision stored",
        id="pending-decision",
    ),
    pytest.param(
        "UPDATE book_positions SET mark = mark + 1 WHERE strategy_id = 'SPY'",
        "SPY",
        "holding SPY: mark stored",
        id="benchmark-holding",
    ),
]


@pytest.mark.parametrize(("sql", "victim", "fragment"), TAMPERS)
def test_tampered_record_fails_with_a_readable_difference(stepped, sql, victim, fragment):
    tamper(stepped, sql)
    found = results(stepped)
    rendered = text(found)
    assert found[victim].status == "mismatch", rendered
    assert fragment in rendered, rendered
    for sid in ROSTER_IDS:
        if sid != victim:
            assert found[sid].status == "ok", rendered
    assert paper_check.execute(stepped) == 1


# ---- splits and broken state -------------------------------------------------------------------


def test_applied_split_on_a_held_symbol_reports_split_affected(stepped):
    split_day = LAST
    with db.transaction(stepped, False):
        stepped.execute(
            "INSERT INTO split_adjustments (symbol, execution_date, split_from, split_to, applied) "
            "VALUES ('SPY', %s, 1, 2, true)",
            (split_day,),
        )
        # What splits.apply_splits does to history before the execution date.
        stepped.execute(
            "UPDATE bars SET open = round(open / 2, 4), high = round(high / 2, 4), low = round(low / 2, 4), "
            "close = round(close / 2, 4), volume = volume * 2 WHERE symbol = 'SPY' AND date < %s",
            (split_day,),
        )
        stepped.execute(
            "UPDATE dividends SET amount = round(amount / 2, 6) WHERE symbol = 'SPY' AND ex_date < %s", (split_day,)
        )
    found = results(stepped)
    rendered = text(found)
    assert found["SPY"].status == "split-affected", rendered
    assert found["SPY"].splits == (("SPY", split_day),)
    assert found[F1].status == "split-affected", rendered  # held SPY since 2026-11-02
    assert found["A"].status == "ok", rendered  # never touched SPY
    assert found[F4].status == "ok", rendered  # SPY only gates its trend (a ratio)
    assert "applied split SPY on 2026-11-03" in rendered
    assert paper_check.execute(stepped) == 0


def test_unapplied_split_is_ignored(stepped):
    with db.transaction(stepped, False):
        stepped.execute(
            "INSERT INTO split_adjustments (symbol, execution_date, split_from, split_to, applied) "
            "VALUES ('SPY', %s, 1, 2, false)",
            (LAST,),
        )
    assert {r.status for r in results(stepped).values()} == {"ok"}


def test_paper_start_without_state_is_a_mismatch(stepped):
    tamper(stepped, "DELETE FROM paper_state WHERE strategy_id = 'A'")
    found = results(stepped)
    assert found["A"].status == "mismatch"
    assert "paper_state: strategies.paper_start is 2026-10-26 but paper_state has no row" in text(found)
    assert paper_check.execute(stepped) == 1


def test_unreadable_stored_row_is_a_mismatch_not_a_crash(stepped):
    # An open order whose stop is above its target fails sim.Order's own validation.
    tamper(
        stepped,
        "UPDATE orders SET sl_price = tp_price + 1 "
        "WHERE id = (SELECT min(id) FROM orders WHERE strategy_id = 'A' AND status = 'open')",
    )
    found = results(stepped)
    assert found["A"].status == "mismatch"
    assert found["A"].differences[0].where == "stored rows"
    assert {found[s].status for s in ("SPY", F4, F1)} == {"ok"}


def test_check_needs_an_idle_connection(pg):
    pg.execute("SELECT 1")
    with pytest.raises(ValueError, match="no transaction in progress"):
        paper_check.check(pg)
    pg.rollback()


# ---- the command line --------------------------------------------------------------------------


def test_require_sessions_argument():
    p = argparse.ArgumentParser()
    paper_check.add_arguments(p)
    assert p.parse_args([]).require_sessions == 0
    assert p.parse_args(["--require-sessions", "5"]).require_sessions == 5
    with pytest.raises(SystemExit):
        p.parse_args(["--require-sessions", "-1"])
    with pytest.raises(SystemExit):
        p.parse_args(["--require-sessions", "five"])


def test_run_wiring(monkeypatch):
    p = argparse.ArgumentParser()
    paper_check.add_arguments(p)
    args = p.parse_args(["--require-sessions", "5"])
    args.dry_run = False
    args.verbose = 0

    class DummyConn:
        closed = False

        def close(self):
            self.closed = True

    conn = DummyConn()
    seen = {}

    def fake_execute(c, **kw):
        seen.update(kw, conn=c)
        return 1

    monkeypatch.setattr(paper_check.db, "connect", lambda: conn)
    monkeypatch.setattr(paper_check, "execute", fake_execute)
    assert paper_check.run(args) == 1
    assert seen == {"require_sessions": 5, "conn": conn} and conn.closed


def test_execute_refuses_a_negative_requirement(pg):
    with pytest.raises(ValueError):
        paper_check.execute(pg, require_sessions=-1)
```
**Impact:** These are new tests only. Notes on running them:
- The `stepped` fixture runs 8 `paper` nights, about 1 to 2 s on the local PG.
- The parametrized tamper test re-runs those nights for each of its 11 cases, so the module adds about 30 s.
- They need `PG_TEST_URL`, and the suite must stay at 0 skipped with `seer-pg` running (Invariant 1).

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.paper.replay, seer_engine.commands.paper_check"`, then `engine/.venv/bin/python -m seer_engine paper_check --help`.

**Tests:**
```
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_paper_replay.py engine/tests/test_paper_check.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q   # 0 skipped
cd web && npx vitest run   # untouched, must stay green (Invariant 1)
```

**Manual check:** none is required for this phase. After landing, the nightly job starts the paper clock. Once 5 or more paper sessions exist, run `SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v paper_check --require-sessions 5` against Neon. It should print one `ok` line per roster strategy and exit 0. This is acceptance 1 and step 2 of "After landing".

**Exit criteria:**
- `test_paper_replay.py` (39) and `test_paper_check.py` (25) pass.
- The purity test covers `paper/replay.py` and passes.
- The whole engine suite passes with 0 skipped.
- After 8 synthetic `paper` nights, `paper_check` reports `ok` for SPY, A, F4 and F1 and exits 0. It exits 1 with a difference that names the row and field for every tampered snapshot, order, mark, position, target, fill, trade, pending decision and holding.
- An applied SPY split reports SPY and F1 as `split-affected` with exit 0.
- `--require-sessions 8` exits 1 after 7 stepped sessions.

## Handoffs

**Phase 13 (Ship):**
- Add the "Paper check" step to `nightly.yml` (`python -m seer_engine -v paper_check`). It needs no `--require-sessions`, because a fresh clock reports "not started" and the first night "0 sessions", and both pass.
- `--require-sessions 5` is the release check in the runbook.
- Document four things in `engine/package_readme.md` and `docs/runbooks/paper-trading.md`:
  - the four statuses;
  - that split-affected never fails;
  - that a halted symbol that later resumes shows as a mismatch, because the night force-closed it (plan Decisions "Force-close rule live");
  - the exit codes.

**Phase 7 (`paper`):** the comparison assumes the persisted conventions listed under the Interface Contract's "Assumptions on phase 7's writes". If phase 7 drops any of them, the reconciler should update `_stored_records` and `compare` in this plan, not phase 7. Those conventions are: expired orders kept in `orders`, `book_targets` kept after execution with ranks 1..n, day-0 snapshots, and the benchmark's whole-share `book_positions` row.

**Phase 6 (store):** the only SQL this phase writes itself is `SELECT DISTINCT session_date FROM book_targets WHERE strategy_id = %s`, because `read_book_targets` reads one session at a time. If the reconciler prefers it, phase 6 can add `read_book_target_sessions(conn, sid) -> tuple[date, ...]`, and `_stored_records` would then call that instead.

**Benchmark fills:** phase 3 writes SPY's buys to `book_fills` (reasons `entry`/`add`). `buy_and_hold` produces no fills, so the check does not compare them. The SPY snapshots, the cash and the holding already pin every buy. Comparing them would need a fills-producing benchmark replay, which is out of scope here and has no owner.

**Phase 1 (purity):** this plan relies on phase 1's purity test globbing `paper/*.py` except `store.py`. If phase 1 lists modules by name instead, `replay.py` has to be added to that list in phase 1's test, not here.

## Rollback

Delete the four new files:
- `engine/src/seer_engine/paper/replay.py`
- `engine/src/seer_engine/commands/paper_check.py`
- `engine/tests/test_paper_replay.py`
- `engine/tests/test_paper_check.py`

Nothing else references them until phase 13 adds the workflow step. If phase 13 has already landed, also remove its "Paper check" step from `nightly.yml`. The command writes nothing, so there is no data to undo.
