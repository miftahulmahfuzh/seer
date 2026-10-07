"""`sean`: the owner's real Gotrade trades (the Sean section of the site).

    sean marks [--now ISO8601]   fetch daily closes for every symbol the owner has held
                                 (sean_marks) and rewrite the daily profit/loss series
                                 (sean_equity) from the first order to the last completed
                                 NYSE session
    sean calibrate               replay Gotrade's fee schedule (sim/costs.py) over every stored
                                 order and print what each paid against what the schedule says;
                                 exit 1 when an order since the current fee regime is off by more
                                 than a cent (Gotrade changed its fees: refit the schedule)

No orders yet: clears any stale series, fetches nothing, exit 0. A symbol Yahoo cannot price
(delisted, not listed there) is logged and valued at its stored closes or its last order
price; it never fails the run. Exit 0 on success, 1 on any other error.

Each subcommand is one ``sub.add_parser`` call in ``add_arguments`` and one ``_HANDLERS``
entry taking ``(conn, args)``.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

import psycopg

from seer_engine import dates, db
from seer_engine.sean import calibrate as fee_check
from seer_engine.sean import equity, marks

log = logging.getLogger(__name__)

HELP = "Sean, the owner's real Gotrade trades: mark holdings to market, write the daily P&L"


def _parse_now(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--now must be ISO 8601 (e.g. 2026-10-02T23:00:00Z): {value!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def add_arguments(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="sean_command", metavar="<sean command>", required=True)

    s = sub.add_parser(
        "marks",
        help="fetch closes for the owner's symbols and rewrite the daily P&L series",
        description=(
            "Fetch daily closes from Yahoo for every symbol in sean_orders, from its first trade "
            "date to the last completed NYSE session, upsert them into sean_marks, and replace "
            "sean_equity with one row per session from the first order on."
        ),
    )
    s.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        metavar="ISO8601",
        help="pretend the current time is this (UTC if no offset); for tests and replays",
    )

    sub.add_parser(
        "calibrate",
        help="replay Gotrade's fee schedule over every stored order; exit 1 when it needs a refit",
        description=(
            "Read every order in sean_orders, ask sim/costs.py what each should have paid on its "
            "own date (trading fee, regulatory fee, PPN), and print both. Exit 1 when any order "
            "dated on or after the first day of the current fee regime is off by more than a cent "
            "in any part. Reads only; writes nothing."
        ),
    )


def run(args: argparse.Namespace) -> int:
    conn = db.connect()
    try:
        return _HANDLERS[args.sean_command](conn, args)
    finally:
        conn.close()


def execute_marks(
    conn: psycopg.Connection,
    *,
    now_utc: datetime | None = None,
    dry_run: bool = False,
    fetch: marks.CloseFetch = marks.yahoo_closes,
) -> int:
    """Fetch closes, store them, rewrite the series. Prices are fetched outside any write
    transaction; the write re-reads the orders under the lock, so an upload that lands while
    prices download is counted (valued at its order price if it brought a new symbol)."""
    now = now_utc or datetime.now(timezone.utc)
    end = dates.last_completed_session(now)

    with db.transaction(conn, dry_run):
        orders = equity.read_orders(conn)

    if not orders:
        with db.transaction(conn, dry_run):
            equity.lock(conn)
            equity.replace_equity(conn, [])
        log.info("sean marks: no orders yet; nothing to mark")
        return 0

    fetched = marks.fetch_closes(equity.symbol_starts(orders), end, fetch)

    with db.transaction(conn, dry_run):
        equity.lock(conn)
        changed = marks.upsert_marks(conn, fetched.rows())
        orders = equity.read_orders(conn)
        points = equity.series(orders, end, marks.read_marks(conn))
        written = equity.replace_equity(conn, points)

    last = points[-1] if points else None
    log.info(
        "sean marks: %d symbols priced, %d without prices%s; %d closes written; %d sessions through %s%s%s",
        len(fetched.closes),
        len(fetched.missing),
        f" ({', '.join(fetched.missing)})" if fetched.missing else "",
        changed,
        written,
        end.isoformat(),
        f"; profit/loss ${last.pnl_usd}" if last else "",
        " (dry-run: rolled back)" if dry_run else "",
    )
    return 0


def _marks(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    return execute_marks(conn, now_utc=args.now, dry_run=bool(args.dry_run))


def _calibrate(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    """Read-only: every stored order's fees against the schedule. ``run`` owns the connection."""
    paid = fee_check.rows_from_db(conn)
    conn.rollback()  # close the read transaction; nothing was written
    result = fee_check.check(paid, since=fee_check.current_since())
    print(fee_check.format_report(result))
    log.info(
        "sean calibrate: %d order(s), %d in the current regime, %d off by more than a cent",
        len(result.residuals), len(result.current), len(result.misses),
    )
    return 0 if result.passed else 1


_HANDLERS = {
    "marks": _marks,
    "calibrate": _calibrate,
}
