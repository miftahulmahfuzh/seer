"""The ``runs`` row lifecycle: one real row per target session.

None of these functions commit; the caller's db.transaction() decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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


@dataclass(frozen=True, slots=True)
class RealRun:
    """The real (non-demo) ``runs`` row of one session, as the paper step reads it."""

    id: int
    status: str
    data_date: date | None
    session_date: date
    paper_status: str | None


def real_run(conn: psycopg.Connection, session_date: date) -> RealRun | None:
    """The real run row for ``session_date``, or None when there is none (demo rows never count)."""
    row = conn.execute(
        """
        SELECT id, status, data_date, session_date, paper_status
        FROM runs
        WHERE session_date = %(session_date)s AND NOT is_demo
        """,
        {"session_date": session_date},
    ).fetchone()
    if row is None:
        return None
    return RealRun(
        id=int(row[0]),
        status=str(row[1]),
        data_date=row[2],
        session_date=row[3],
        paper_status=None if row[4] is None else str(row[4]),
    )


_PAPER_RUNNING_SQL = """
    UPDATE runs
    SET paper_status = 'running', paper_error = NULL, paper_finished_at = NULL
    WHERE id = %(id)s AND NOT is_demo
"""

_PAPER_FINAL_SQL = """
    UPDATE runs
    SET paper_status = %(status)s, paper_error = %(error)s, paper_finished_at = clock_timestamp()
    WHERE id = %(id)s AND NOT is_demo
"""


def _set_paper(conn: psycopg.Connection, sql: str, params: dict[str, object]) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.rowcount != 1:
            raise LookupError(f"no real run with id {params['id']}")


def start_paper(conn: psycopg.Connection, run_id: int) -> None:
    """Mark the run's paper step running (error and finished_at cleared)."""
    _set_paper(conn, _PAPER_RUNNING_SQL, {"id": run_id})


def finish_paper(conn: psycopg.Connection, run_id: int) -> None:
    """Mark the run's paper step successful."""
    _set_paper(conn, _PAPER_FINAL_SQL, {"id": run_id, "status": "success", "error": None})


def fail_paper(conn: psycopg.Connection, run_id: int, error: str) -> None:
    """Mark the run's paper step failed with ``error`` (secrets redacted, cut to 2000 characters)."""
    _set_paper(
        conn,
        _PAPER_FINAL_SQL,
        {"id": run_id, "status": "failed", "error": redact(error)[:MAX_ERROR_CHARS]},
    )
