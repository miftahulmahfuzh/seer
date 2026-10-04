"""Removal of the demo rows seeded by web/scripts/seed-demo.mjs.

Demo bars and FX rows are indistinguishable from real ones, so the trigger is the
existence of a demo run: while one exists, every row in the demo-owned tables is demo
data. ``strategies`` is kept because orders reference it and later phases reuse it.

The paper tables of migration 003 (``paper_state`` and the ``book_*`` tables) are
demo-owned too: the demo seed writes paper state, and real paper state never coexists with
a demo run (``paper`` runs only after ``nightly``, which purges first). The seed also sets
the roster rows' paper clock (``strategies.paper_start`` and ``params``); the purge keeps
the rows but resets those two columns, so the first real ``paper`` run starts cleanly.

``dividends`` is **not** demo-owned. Its rows are Massive facts keyed by (symbol,
ex-date), fetched only for the sessions ``nightly`` is missing, so a purge would lose
ex-dates for good and the replay check (D7) could no longer reproduce a dividend credit.
The demo seed never writes it, and ``splits.apply_splits`` rewrites it in step with the
bars, so a kept row never disagrees with them.
"""

from __future__ import annotations

import logging

import psycopg

from seer_engine import db

log = logging.getLogger(__name__)

DEMO_TABLES = (
    "action_dismissals",
    "orders",
    "equity_snapshots",
    "paper_state",
    "book_positions",
    "book_targets",
    "book_fills",
    "book_trades",
    "bars",
    "fx_rates",
    "runs",
)

# The demo seed sets the roster rows' paper clock; a purge resets it (the rows themselves stay).
RESET_PAPER_CLOCK = "paper_start = NULL, params = '{}'::jsonb"


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
    conn.execute(f"UPDATE strategies SET {RESET_PAPER_CLOCK}")
    log.warning("demo data found: truncated %s; reset strategies.paper_start/params", ", ".join(DEMO_TABLES))
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
