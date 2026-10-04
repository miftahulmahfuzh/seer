"""Read-side queries on the point-in-time ``universe`` table.

Membership intervals are [start_date, end_date): end_date is exclusive, NULL = still a
member. Phase 2's ``universe refresh`` writes the table; these functions only read it.
"""

from __future__ import annotations

from datetime import date, timedelta

import psycopg

BENCHMARK = "SPY"


def members_on(conn: psycopg.Connection, d: date) -> set[str]:
    """Symbols in either index on ``d``."""
    rows = conn.execute(
        """
        SELECT DISTINCT symbol FROM universe
        WHERE start_date <= %(d)s AND (end_date IS NULL OR end_date > %(d)s)
        """,
        {"d": d},
    ).fetchall()
    return {r[0] for r in rows}


def symbols_for_bars(conn: psycopg.Connection, d: date, grace_days: int = 30) -> set[str]:
    """Symbols whose bars are stored for ``d``: members on ``d``, members that left in the
    last ``grace_days`` days (so open positions keep a price), and the benchmark."""
    rows = conn.execute(
        """
        SELECT DISTINCT symbol FROM universe
        WHERE start_date <= %(d)s AND (end_date IS NULL OR end_date > %(cut)s)
        """,
        {"d": d, "cut": d - timedelta(days=grace_days)},
    ).fetchall()
    return {r[0] for r in rows} | {BENCHMARK}


def all_symbols(conn: psycopg.Connection, since: date) -> list[str]:
    """Every symbol that was a member at any time after ``since``, plus the benchmark,
    sorted. Members that joined after ``since`` are included."""
    rows = conn.execute(
        "SELECT DISTINCT symbol FROM universe WHERE end_date IS NULL OR end_date > %(since)s",
        {"since": since},
    ).fetchall()
    return sorted({r[0] for r in rows} | {BENCHMARK})


def paper_symbols(conn: psycopg.Connection, d: date) -> set[str]:
    """Symbols paper state still needs a bar for on session ``d`` (tables from migration 003).

    Bracket orders that are pending or open, every open book position (book strategies and the
    SPY benchmark holding), and book targets decided for session ``d`` or later. ``nightly`` adds
    these to the universe set so a held symbol that left the index keeps getting bars.
    """
    rows = conn.execute(
        """
        SELECT symbol FROM orders WHERE status IN ('pending', 'open')
        UNION
        SELECT symbol FROM book_positions
        UNION
        SELECT symbol FROM book_targets WHERE session_date >= %(d)s
        """,
        {"d": d},
    ).fetchall()
    return {r[0] for r in rows}
