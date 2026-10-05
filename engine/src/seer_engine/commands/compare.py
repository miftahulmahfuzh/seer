"""compare: rank the paper strategies over the window they share (read-only).

``python -m seer_engine compare [--min-sessions N] [--exclude ID ...] [--json] [--require-window]``

Reads every ``equity_snapshots`` row and hands them to ``paper.compare``, which is pure. Prints
the common window, the ranking over it, what could not be ranked and why, and inception-to-date
as a separate block. ``--json`` prints ``paper.compare.as_json`` instead -- the exact shape the
leaderboard's TypeScript port is pinned against.

Reads one table and nothing else: no ``strategies`` row, no roster, no clock. Everything happens
in one REPEATABLE READ, READ ONLY transaction that is always rolled back, so ``--dry-run``
changes nothing because there is nothing to change.

Because it does not read ``strategies``, it does not know which strategies are retired, and that
is deliberate: a retired strategy is not a live competitor, so excluding it is the caller's
decision, not this module's arithmetic. ``--exclude <id>`` is how a human makes it; the
leaderboard's TypeScript port makes it from ``strategies.status``.

Exit 0 when the comparison was produced; with ``--require-window``, exit 1 when no window of
``--min-sessions`` sessions exists (useful in CI, and the honest answer for a young board).
Config errors exit 2 (cli).
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import psycopg
from psycopg.pq import TransactionStatus

from seer_engine import db
from seer_engine.paper import compare as compare_

log = logging.getLogger(__name__)

HELP = "Rank the paper strategies over the window they share, with the window stated (read-only)"


def _sessions_arg(value: str) -> int:
    try:
        n = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--min-sessions must be a whole number, got {value!r}") from e
    if n < 2:
        raise argparse.ArgumentTypeError(f"--min-sessions must be at least 2, got {n}")
    return n


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--min-sessions",
        type=_sessions_arg,
        default=compare_.MIN_COMMON_SESSIONS,
        metavar="N",
        help=(
            f"sessions a strategy needs in the common window to be ranked "
            f"(default {compare_.MIN_COMMON_SESSIONS}, one quarter of a trading year)"
        ),
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="ID",
        help="leave this strategy out of the comparison entirely (repeatable, e.g. --exclude SPY). "
             "A retired strategy is not a live competitor: exclude it to rank the living",
    )
    p.add_argument("--json", action="store_true", help="print the comparison as JSON instead of a table")
    p.add_argument(
        "--require-window",
        action="store_true",
        help="exit 1 when no common window of --min-sessions sessions exists",
    )


def run(args: argparse.Namespace) -> int:
    conn = db.connect()
    try:
        return execute(
            conn,
            min_sessions=int(args.min_sessions),
            exclude=tuple(args.exclude),
            as_json=bool(args.json),
            require_window=bool(args.require_window),
        )
    finally:
        conn.close()


def read_series(
    conn: psycopg.Connection, *, exclude: Sequence[str] = ()
) -> dict[str, list[tuple[date, Decimal]]]:
    """Every strategy's ``equity_snapshots`` rows as ``(date, equity_usd)`` in date order.

    Reads only ``equity_snapshots``; a strategy with no snapshot simply has no key.
    """
    skip = {s.strip() for s in exclude if s.strip()}
    rows = conn.execute(
        "SELECT strategy_id, date, equity_usd FROM equity_snapshots ORDER BY strategy_id, date"
    ).fetchall()
    series: dict[str, list[tuple[date, Decimal]]] = {}
    for strategy_id, day, equity in rows:
        if strategy_id in skip:
            continue
        series.setdefault(strategy_id, []).append((day, equity))
    return series


def execute(
    conn: psycopg.Connection,
    *,
    min_sessions: int = compare_.MIN_COMMON_SESSIONS,
    exclude: Sequence[str] = (),
    as_json: bool = False,
    require_window: bool = False,
) -> int:
    """Read, compare, print; return the exit code. Writes nothing.

    ``conn`` must have autocommit off and no transaction in progress; the read-only transaction
    this opens is always rolled back.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("compare needs a connection with no transaction in progress")
    try:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        series = read_series(conn, exclude=exclude)
    finally:
        conn.rollback()

    result = compare_.compare(series, min_sessions=min_sessions)
    if as_json:
        print(json.dumps(compare_.as_json(result), indent=2, sort_keys=True))
    else:
        for line in compare_.render(result):
            print(line)
    if result.window is None:
        log.warning(
            "compare: no common window of %d sessions; nothing was ranked (invariant 6: a "
            "cross-window comparison is not a ranking)",
            min_sessions,
        )
        if require_window:
            return 1
    return 0
