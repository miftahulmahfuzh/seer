"""The Python migration runner (shares schema_migrations with web/scripts/migrate.mjs)."""

from __future__ import annotations

import pytest

from seer_engine import cli
from seer_engine.commands.migrate import MIGRATIONS_DIR, apply_migrations, migration_files

ALL = [p.name for p in migration_files(MIGRATIONS_DIR)]


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
    ).fetchall()
    return {r[0] for r in rows}


def test_repo_has_001_and_002():
    assert ALL[:2] == ["001_init.sql", "002_engine.sql"]


def test_applies_all_then_nothing(pg_empty):
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ALL
    assert {"runs", "bars", "universe", "split_adjustments", "backfill_log"} <= _tables(pg_empty)
    names = [r[0] for r in pg_empty.execute("SELECT name FROM schema_migrations ORDER BY name")]
    assert names == ALL
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == []


def test_respects_rows_written_by_the_node_runner(pg_empty):
    pg_empty.execute(
        "CREATE TABLE schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    pg_empty.execute((MIGRATIONS_DIR / "001_init.sql").read_text())
    pg_empty.execute("INSERT INTO schema_migrations (name) VALUES ('001_init.sql')")
    pg_empty.commit()
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == [n for n in ALL if n != "001_init.sql"]


def test_dry_run_writes_nothing(pg_empty):
    assert apply_migrations(pg_empty, MIGRATIONS_DIR, dry_run=True) == ALL
    assert _tables(pg_empty) == set()


def test_dry_run_after_apply_reports_nothing(pg_empty):
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR, dry_run=True) == []
    count = pg_empty.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == len(ALL)


def test_failed_file_rolls_back_only_itself(pg_empty, tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE ok_t (x int);")
    (tmp_path / "002_bad.sql").write_text("CREATE TABLE bad_t (x int); SELECT no_such_column FROM ok_t;")
    with pytest.raises(Exception):
        apply_migrations(pg_empty, tmp_path)
    assert "ok_t" in _tables(pg_empty)
    assert "bad_t" not in _tables(pg_empty)
    names = [r[0] for r in pg_empty.execute("SELECT name FROM schema_migrations")]
    assert names == ["001_ok.sql"]


def test_cli_dry_run_against_test_db(pg_schema, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", pg_schema.url)
    assert cli.main(["--dry-run", "migrate"]) == 0
    assert _tables(pg_schema.conn) == set()
    assert cli.main(["migrate"]) == 0
    pg_schema.conn.rollback()  # see the other connection's committed work
    count = pg_schema.conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == len(ALL)
