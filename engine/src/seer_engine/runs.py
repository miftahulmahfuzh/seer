"""The ``runs`` row lifecycle: one real row per target session.

None of these functions commit; the caller's db.transaction() decides.
"""

from __future__ import annotations

import psycopg

from seer_engine.dates import RunDates
from seer_engine.http import redact

MAX_ERROR_CHARS = 2000


def start_run(conn: psycopg.Connection, rd: RunDates) -> int | None:
    """Claim the real run row for ``rd.session_date`` and mark it running.

    Returns its id, or None when that session already has a successful real run (the
    caller then does nothing). A failed or interrupted row is reused: same id, status
    back to running, error and finished_at cleared, data_date refreshed.
    """
    row = conn.execute(
        """
        INSERT INTO runs (status, data_date, session_date, is_demo)
        VALUES ('running', %(data_date)s, %(session_date)s, false)
        ON CONFLICT (session_date) WHERE NOT is_demo DO UPDATE
        SET status = 'running',
            started_at = now(),
            finished_at = NULL,
            error = NULL,
            data_date = EXCLUDED.data_date
        WHERE runs.status <> 'success'
        RETURNING id
        """,
        {"data_date": rd.data_date, "session_date": rd.session_date},
    ).fetchone()
    return None if row is None else int(row[0])


def _set_final(conn: psycopg.Connection, run_id: int, status: str, error: str | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE runs
            SET status = %(status)s, error = %(error)s, finished_at = clock_timestamp()
            WHERE id = %(id)s AND NOT is_demo
            """,
            {"status": status, "error": error, "id": run_id},
        )
        if cur.rowcount != 1:
            raise LookupError(f"no real run with id {run_id}")


def finish_run(conn: psycopg.Connection, run_id: int) -> None:
    """Mark the run successful."""
    _set_final(conn, run_id, "success", None)


def fail_run(conn: psycopg.Connection, run_id: int, error: str) -> None:
    """Mark the run failed with ``error`` (secrets redacted, cut to 2000 characters)."""
    _set_final(conn, run_id, "failed", redact(error)[:MAX_ERROR_CHARS])
