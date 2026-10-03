"""The runs lifecycle: one real row per session, success is final, failures are reused."""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

from seer_engine.dates import RunDates
from seer_engine.runs import MAX_ERROR_CHARS, fail_run, finish_run, start_run

RD = RunDates(data_date=date(2026, 10, 2), session_date=date(2026, 10, 5))


def _row(conn, run_id):
    return conn.execute(
        "SELECT status, data_date, session_date, is_demo, error, finished_at FROM runs WHERE id = %s",
        (run_id,),
    ).fetchone()


def test_start_then_finish(pg):
    run_id = start_run(pg, RD)
    assert isinstance(run_id, int)
    status, data_date, session_date, is_demo, error, finished_at = _row(pg, run_id)
    assert (status, data_date, session_date, is_demo, error, finished_at) == (
        "running", RD.data_date, RD.session_date, False, None, None
    )
    finish_run(pg, run_id)
    status, *_rest, error, finished_at = _row(pg, run_id)
    assert status == "success" and error is None and finished_at is not None


def test_rerun_after_success_is_a_no_op(pg):
    run_id = start_run(pg, RD)
    finish_run(pg, run_id)
    pg.commit()
    before = pg.execute("SELECT *, xmin::text FROM runs").fetchall()
    assert start_run(pg, RD) is None
    pg.commit()
    assert pg.execute("SELECT *, xmin::text FROM runs").fetchall() == before


def test_failed_row_is_reused(pg):
    run_id = start_run(pg, RD)
    fail_run(pg, run_id, "Massive returned HTTP 500")
    assert _row(pg, run_id)[0] == "failed"
    later = RunDates(data_date=date(2026, 10, 2), session_date=RD.session_date)
    assert start_run(pg, later) == run_id
    status, *_rest, error, finished_at = _row(pg, run_id)
    assert (status, error, finished_at) == ("running", None, None)
    assert pg.execute("SELECT count(*) FROM runs").fetchone()[0] == 1


def test_interrupted_running_row_is_reused(pg):
    run_id = start_run(pg, RD)
    assert start_run(pg, RD) == run_id


def test_fail_run_truncates_and_redacts(pg):
    run_id = start_run(pg, RD)
    fail_run(pg, run_id, "GET https://api.massive.com/x?apiKey=SECRET123 failed " + "x" * 5000)
    error = _row(pg, run_id)[4]
    assert len(error) == MAX_ERROR_CHARS
    assert "SECRET123" not in error and "apiKey=REDACTED" in error


def test_demo_run_on_same_session_does_not_conflict(pg):
    pg.execute(
        "INSERT INTO runs (status, data_date, session_date, is_demo) VALUES ('success', %s, %s, true)",
        (RD.data_date, RD.session_date),
    )
    run_id = start_run(pg, RD)
    assert run_id is not None
    assert pg.execute("SELECT count(*) FROM runs").fetchone()[0] == 2


def test_unique_index_rejects_second_real_row(pg):
    start_run(pg, RD)
    with pytest.raises(psycopg.errors.UniqueViolation):
        pg.execute(
            "INSERT INTO runs (status, data_date, session_date) VALUES ('running', %s, %s)",
            (RD.data_date, RD.session_date),
        )


def test_finish_unknown_run_raises(pg):
    with pytest.raises(LookupError):
        finish_run(pg, 999_999)
    with pytest.raises(LookupError):
        fail_run(pg, 999_999, "x")
