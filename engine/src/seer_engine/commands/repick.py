"""repick: re-take every waiting paper decision that holds a stock the broker does not offer.

``python -m seer_engine [--dry-run] [-v] repick``

The owner lists stocks Gotrade does not offer on the website (``unavailable_symbols``, migration
014). A decision already taken but not yet traded may hold one; this re-takes it at once, on the
same bars, with the listed stocks out of the universe, so the method's next-best stock takes the
slot (``commands.paper.repick``). The paper night runs the same step before it settles anything,
so a listing made after this command still reaches the decision; this command only makes it
reach the website before the US open. Explanations of the new picks are written by ``explain``.

Retired entries are never touched. Nothing waiting holds a listed stock: no-op, exit 0.
"""

from __future__ import annotations

import argparse
import logging

import psycopg

from seer_engine import db
from seer_engine.commands.paper import repick
from seer_engine.paper import roster, store

log = logging.getLogger(__name__)

HELP = "Re-pick waiting paper decisions that hold a stock the broker does not offer"


def add_arguments(p: argparse.ArgumentParser) -> None:  # noqa: ARG001 - no options
    return None


def execute(conn: psycopg.Connection, *, dry_run: bool = False) -> int:
    with db.transaction(conn, dry_run):
        rows = store.read_roster_rows(conn)
        entries = roster.active(roster.from_rows(rows))
        starts = {row.id: row.paper_start for row in rows}
        done = repick(conn, entries, starts)
    if done:
        log.info("re-picked %s%s", ", ".join(done), " (dry-run: rolled back)" if dry_run else "")
    else:
        log.info("no waiting decision holds a stock on the not-offered list")
    return 0


def run(args: argparse.Namespace) -> int:
    conn = db.connect()
    try:
        return execute(conn, dry_run=bool(args.dry_run))
    finally:
        conn.close()
