"""The Python migration runner (shares schema_migrations with web/scripts/migrate.mjs)."""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

from seer_engine import cli
from seer_engine.commands.migrate import MIGRATIONS_DIR, apply_migrations, migration_files

ALL = [p.name for p in migration_files(MIGRATIONS_DIR)]
PAPER_TABLES = {"paper_state", "book_positions", "book_targets", "book_fills", "book_trades", "dividends"}
ROSTER_IDS = {"SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M"}


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
    ).fetchall()
    return {r[0] for r in rows}


def _columns(conn) -> list[tuple]:
    return conn.execute(
        "SELECT table_name, column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_schema = current_schema() "
        "ORDER BY table_name, ordinal_position"
    ).fetchall()


def _constraints(conn) -> list[tuple]:
    return conn.execute(
        "SELECT conrelid::regclass::text, conname FROM pg_constraint c "
        "JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = current_schema() "
        "ORDER BY 1, 2"
    ).fetchall()


def _strategies(conn) -> list[tuple]:
    return conn.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, params, paper_start "
        "FROM strategies ORDER BY id"
    ).fetchall()


def _neon_before_003(conn) -> None:
    """001 + 002 applied and recorded, with the strategies rows Neon had before 003."""
    conn.execute(
        "CREATE TABLE schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    for name in ("001_init.sql", "002_engine.sql"):
        conn.execute((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
    conn.execute(
        "INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort) VALUES "
        "('A', 'A · Quant', 'Mean Reversion', 'sigma', true, false, 1), "
        "('B', 'B · ML', 'Gradient boosting', 'brain', false, false, 2), "
        "('C', 'C · LLM', 'Language model', 'sparkles', false, false, 3), "
        "('SPY', 'SPY', 'Benchmark', 'flag', false, true, 9)"
    )
    conn.commit()


def test_repo_has_001_to_003():
    assert ALL[:3] == ["001_init.sql", "002_engine.sql", "003_paper.sql"]


def test_applies_all_then_nothing(pg_empty):
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ALL
    assert {"runs", "bars", "universe", "split_adjustments", "backfill_log"} | PAPER_TABLES <= _tables(pg_empty)
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


# ---- 003_paper.sql ---------------------------------------------------------------------------


def test_003_on_a_fresh_schema_writes_the_roster_with_spy_champion(pg_empty):
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    rows = pg_empty.execute(
        "SELECT id, is_champion, is_benchmark, engine, rules_id, params, paper_start FROM strategies ORDER BY sort"
    ).fetchall()
    assert rows == [
        ("SPY", True, True, "benchmark", None, {}, None),
        ("A", False, False, "bracket", "design-v0", {}, None),
        ("F4-MOM12-N20-TREND", False, False, "book", "monthly-hold", {}, None),
        ("F1-SPY-SMA200-M", False, False, "book", "monthly-hold", {}, None),
    ]


def test_003_adds_the_columns(pg):
    cols = {(t, c) for t, c, *_ in _columns(pg)}
    assert {
        ("strategies", "engine"),
        ("strategies", "rules_id"),
        ("strategies", "paper_start"),
        ("orders", "mark"),
        ("runs", "paper_status"),
        ("runs", "paper_error"),
        ("runs", "paper_finished_at"),
    } <= cols


def test_003_sql_is_idempotent(pg):
    before = (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg))
    pg.execute((MIGRATIONS_DIR / "003_paper.sql").read_text(encoding="utf-8"))
    pg.commit()
    assert (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg)) == before


def test_003_on_neon_flips_the_champion_and_drops_unreferenced_b_and_c(pg_empty):
    _neon_before_003(pg_empty)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ["003_paper.sql"]
    rows = {r[0]: r[1:] for r in pg_empty.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort FROM strategies"
    ).fetchall()}
    assert set(rows) == ROSTER_IDS
    assert rows["SPY"] == ("SPY", "S&P 500, buy and hold", "landmark", True, True, 1)
    assert rows["A"] == ("A · Quant", "Mean reversion, 5-day brackets", "sigma", False, False, 2)
    champions = pg_empty.execute("SELECT id FROM strategies WHERE is_champion").fetchall()
    assert champions == [("SPY",)]


@pytest.mark.parametrize("kept", ["orders", "equity_snapshots"])
def test_003_keeps_a_referenced_b_or_c(pg_empty, kept):
    _neon_before_003(pg_empty)
    if kept == "orders":
        pg_empty.execute(
            "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, "
            "limit_price, tp_price, sl_price, shares, status) "
            "VALUES ('B', %s, 1, 'NVDA', 'NVIDIA', 180, 178, 185, 172, 10, 'pending')",
            (date(2026, 10, 5),),
        )
    else:
        pg_empty.execute(
            "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ('C', %s, 1, 1)",
            (date(2026, 10, 2),),
        )
    pg_empty.commit()
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    ids = {r[0] for r in pg_empty.execute("SELECT id FROM strategies").fetchall()}
    survivor = "B" if kept == "orders" else "C"
    gone = "C" if kept == "orders" else "B"
    assert survivor in ids
    assert gone not in ids
    assert ROSTER_IDS <= ids


def test_003_checks_reject_unknown_values(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("UPDATE strategies SET engine = 'other' WHERE id = 'A'")
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("INSERT INTO runs (status, paper_status) VALUES ('running', 'done')")
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute(
            "INSERT INTO book_trades (strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, "
            "days_held, cost_usd, income_usd, pnl_usd, exit_reason) "
            "VALUES ('A', 'X', '2026-10-01', '2026-10-02', 1, 1, 1, 0, 0, 0, 'tp-hit')"
        )
    pg.rollback()
