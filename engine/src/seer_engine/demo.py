"""Removal of the demo rows seeded by web/scripts/seed-demo.mjs.

Demo bars and FX rows are indistinguishable from real ones, so the trigger is the
existence of a demo run: while one exists, every row in the demo-owned tables is demo
data. ``strategies`` is kept because orders reference it and later phases reuse it.
"""

from __future__ import annotations

import logging

import psycopg

from seer_engine import db

log = logging.getLogger(__name__)

DEMO_TABLES = ("action_dismissals", "orders", "equity_snapshots", "bars", "fx_rates", "runs")


def has_demo(conn: psycopg.Connection) -> bool:
    """True when any ``runs`` row is a demo run."""
    row = conn.execute("SELECT EXISTS (SELECT 1 FROM runs WHERE is_demo)").fetchone()
    return bool(row[0])


def purge_demo(conn: psycopg.Connection) -> bool:
    """Empty every demo-owned table when a demo run exists. Returns True when it purged.

    Does not commit: the caller's transaction makes it atomic.
    """
    if not has_demo(conn):
        return False
    conn.execute(f"TRUNCATE {', '.join(DEMO_TABLES)} RESTART IDENTITY")
    log.warning("demo data found: truncated %s", ", ".join(DEMO_TABLES))
    return True


def purge_demo_if_needed(conn: psycopg.Connection, dry_run: bool) -> bool:
    """purge_demo() in its own transaction, before a command's first real write.

    Under ``dry_run`` the purge runs and is rolled back; the return value still says
    whether it would have purged.
    """
    with db.transaction(conn, dry_run):
        purged = purge_demo(conn)
    if purged and dry_run:
        log.warning("dry-run: would purge demo data (%s)", ", ".join(DEMO_TABLES))
    return purged
