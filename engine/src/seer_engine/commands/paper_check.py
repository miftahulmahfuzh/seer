"""paper_check: the read-only replay check (D7, design §9 "one code path").

``python -m seer_engine paper_check [--require-sessions N]``

For every strategy on the database roster -- retired ones included -- with a paper start, replay
it from ``paper_start`` through its last
stepped session on the bars in the database and compare every stored record with the replay
(``paper.replay``): every ``equity_snapshots`` row from day 0; A's and C's every ``orders`` row and
open marks; the book strategies' ``book_positions``, ``book_fills`` (in order), ``book_trades`` (in
order) and every stored ``book_targets`` decision; the benchmark's SPY holding; ``paper_state``.

C is replayed from the verdicts ``veto`` stored (``news_vetoes``), read in the same transaction;
the LLM is never asked again (handover D8): only ``allow`` verdicts can be bought, a ``veto``,
``failed`` or missing verdict is no trade, exactly as ``paper`` decided it.

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

from seer_engine import dates, db
from seer_engine.backtest.book_runner import DividendMap
from seer_engine.backtest.market import Market
from seer_engine.commands.paper import _bracket_strategy
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

    The roster is read from the ``strategies`` rows in this same read-only transaction, so the
    replay checks exactly what the night traded. A retired strategy is replayed like any other:
    it keeps its ``paper_start``, its ``paper_state`` and every history row, so its record stays
    verifiable after it stops trading (plan invariant 4).

    ``conn`` must have autocommit off and no transaction in progress; the read-only transaction
    this opens is always rolled back.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("paper_check needs a connection with no transaction in progress")
    try:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return _check(conn, roster.from_rows(store.read_roster_rows(conn)))
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
                kickoff=state.kickoff_session,
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
                expected = _expected(conn, entry, head, market, dividends)
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


def _expected(
    conn: psycopg.Connection, entry: RosterEntry, head: PaperHead, market: Market, dividends: DividendMap
) -> Records:
    if entry.engine == "bracket":
        # The replay decides paper_start .. next_session(last_session): C carries the verdicts
        # stored for exactly those sessions (read in this read-only transaction).
        strategy = _bracket_strategy(conn, entry, head.paper_start, dates.next_session(head.last_session))
        return replay.expected_bracket(market, strategy, entry.params, head)
    if entry.engine == "book":
        return replay.expected_book(market, entry.obj, entry.params, entry.rules, head, dividends)
    if entry.engine == "benchmark":
        return replay.expected_benchmark(market, head, dividends)
    raise ValueError(f"{entry.id}: unknown engine {entry.engine!r}")
