"""The Python migration runner (shares schema_migrations with web/scripts/migrate.mjs)."""

from __future__ import annotations

import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
import pytest

from seer_engine import cli
from seer_engine.commands.migrate import MIGRATIONS_DIR, apply_migrations, migration_files

ALL = [p.name for p in migration_files(MIGRATIONS_DIR)]
PAPER_TABLES = {"paper_state", "book_positions", "book_targets", "book_fills", "book_trades", "dividends"}
ROSTER_IDS = {"SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M"}
C_ROW = ("C", "C · News veto", "A's picks, LLM can veto on news", "gavel", False, False, 5, "bracket", "design-v0")


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


def _upto(tmp_path: Path, last: str) -> Path:
    """A migrations directory holding the repo's files up to and including ``last``: the
    schema as it stood when ``last`` was the newest migration."""
    out = tmp_path / f"upto-{last}"
    out.mkdir()
    for p in migration_files(MIGRATIONS_DIR):
        if p.name <= last:
            shutil.copy(p, out / p.name)
    return out


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


def test_repo_has_001_to_004():
    assert ALL[:4] == ["001_init.sql", "002_engine.sql", "003_paper.sql", "004_news_veto.sql"]


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


def test_003_on_a_fresh_schema_writes_the_roster_with_spy_champion(pg_empty, tmp_path):
    apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql"))
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


def test_003_sql_is_idempotent(pg_empty, tmp_path):
    # On the schema 003 left (before 004): 003's DELETE of an unreferenced C would undo 004's row.
    apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql"))
    pg = pg_empty
    before = (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg))
    pg.execute((MIGRATIONS_DIR / "003_paper.sql").read_text(encoding="utf-8"))
    pg.commit()
    assert (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg)) == before


def test_003_on_neon_flips_the_champion_and_drops_unreferenced_b_and_c(pg_empty, tmp_path):
    _neon_before_003(pg_empty)
    assert apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql")) == ["003_paper.sql"]
    rows = {r[0]: r[1:] for r in pg_empty.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort FROM strategies"
    ).fetchall()}
    assert set(rows) == ROSTER_IDS
    assert rows["SPY"] == ("SPY", "S&P 500, buy and hold", "landmark", True, True, 1)
    assert rows["A"] == ("A · Quant", "Mean reversion, 5-day brackets", "sigma", False, False, 2)
    champions = pg_empty.execute("SELECT id FROM strategies WHERE is_champion").fetchall()
    assert champions == [("SPY",)]


@pytest.mark.parametrize("kept", ["orders", "equity_snapshots"])
def test_003_keeps_a_referenced_b_or_c(pg_empty, tmp_path, kept):
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
    apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql"))
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


# ---- 004_news_veto.sql -----------------------------------------------------------------------

NEWS_VETOES_COLUMNS = [
    ("news_vetoes", "strategy_id", "text", "NO", None),
    ("news_vetoes", "session_date", "date", "NO", None),
    ("news_vetoes", "rank", "integer", "NO", None),
    ("news_vetoes", "symbol", "text", "NO", None),
    ("news_vetoes", "verdict", "text", "NO", None),
    ("news_vetoes", "reason", "text", "NO", None),
    ("news_vetoes", "model", "text", "YES", None),
    ("news_vetoes", "prompt_version", "text", "NO", None),
    ("news_vetoes", "headlines", "jsonb", "NO", "'[]'::jsonb"),
    ("news_vetoes", "earnings_date", "date", "YES", None),
    ("news_vetoes", "decided_at", "timestamp with time zone", "NO", None),
]
DECIDED = datetime(2026, 10, 5, 23, 30, tzinfo=timezone.utc)


def _veto(conn, strategy_id="C", session=date(2026, 10, 6), rank=1, symbol="NVDA", verdict="allow") -> None:
    conn.execute(
        "INSERT INTO news_vetoes (strategy_id, session_date, rank, symbol, verdict, reason, model, "
        "prompt_version, decided_at) VALUES (%s, %s, %s, %s, %s, 'r', 'glm-5.3', 'c-veto-v1', %s)",
        (strategy_id, session, rank, symbol, verdict, DECIDED),
    )


def _started_a(conn) -> None:
    """A's paper clock started, with one pending order and its state (what Neon will hold)."""
    conn.execute(
        "UPDATE strategies SET paper_start = %s, params = '{\"digest\": \"x\"}'::jsonb WHERE id = 'A'",
        (date(2026, 10, 6),),
    )
    conn.execute(
        "INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, "
        "usd_idr, pending_session, pending_decision) VALUES ('A', %s, 1000, 1000, 1000, 16530, %s, false)",
        (date(2026, 10, 5), date(2026, 10, 6)),
    )
    conn.execute(
        "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, "
        "limit_price, tp_price, sl_price, shares, status) "
        "VALUES ('A', %s, 1, 'NVDA', 'NVIDIA', 180, 178, 185, 172, 10, 'pending')",
        (date(2026, 10, 6),),
    )
    conn.commit()


def _paper_rows(conn) -> list:
    return [
        conn.execute(f"SELECT x::text FROM {t} x ORDER BY x::text").fetchall()
        for t in ("paper_state", "orders", "equity_snapshots", "book_positions", "book_targets")
    ]


def test_004_on_a_fresh_schema_adds_c_last_and_the_news_vetoes_table(pg_empty):
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    rows = pg_empty.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, params, paper_start "
        "FROM strategies ORDER BY sort"
    ).fetchall()
    assert [r[0] for r in rows] == ["SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M", "C"]
    assert rows[-1] == (*C_ROW, {}, None)
    assert pg_empty.execute("SELECT id FROM strategies WHERE is_champion").fetchall() == [("SPY",)]
    assert [c for c in _columns(pg_empty) if c[0] == "news_vetoes"] == NEWS_VETOES_COLUMNS
    assert pg_empty.execute("SELECT count(*) FROM news_vetoes").fetchone()[0] == 0


def test_004_on_a_post_003_schema_adds_c_and_leaves_the_roster_rows_alone(pg_empty, tmp_path):
    _neon_before_003(pg_empty)
    assert apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql")) == ["003_paper.sql"]
    _started_a(pg_empty)
    before = (_strategies(pg_empty), _paper_rows(pg_empty))
    assert "news_vetoes" not in _tables(pg_empty)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ["004_news_veto.sql"]
    after = _strategies(pg_empty)
    assert [r for r in after if r[0] != "C"] == before[0]  # SPY, A (started), F4, F1: byte for byte
    assert [r[:9] for r in after if r[0] == "C"] == [C_ROW]
    assert _paper_rows(pg_empty) == before[1]
    assert "news_vetoes" in _tables(pg_empty)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == []


def test_004_restyles_a_c_row_that_003_kept(pg_empty, tmp_path):
    _neon_before_003(pg_empty)
    pg_empty.execute(
        "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ('C', %s, 1, 1)",
        (date(2026, 10, 2),),
    )
    pg_empty.commit()
    apply_migrations(pg_empty, _upto(tmp_path, "003_paper.sql"))
    assert pg_empty.execute("SELECT name FROM strategies WHERE id = 'C'").fetchone() == ("C · LLM",)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ["004_news_veto.sql"]
    row = pg_empty.execute(
        "SELECT id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id FROM strategies WHERE id = 'C'"
    ).fetchone()
    assert row == C_ROW
    assert pg_empty.execute("SELECT count(*) FROM equity_snapshots WHERE strategy_id = 'C'").fetchone()[0] == 1


def test_004_sql_is_idempotent(pg):
    _veto(pg)
    pg.commit()
    before = (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg))
    rows = pg.execute("SELECT x::text FROM news_vetoes x").fetchall()
    pg.execute((MIGRATIONS_DIR / "004_news_veto.sql").read_text(encoding="utf-8"))
    pg.commit()
    assert (_columns(pg), _constraints(pg), _tables(pg), _strategies(pg)) == before
    assert pg.execute("SELECT x::text FROM news_vetoes x").fetchall() == rows


def test_004_news_vetoes_defaults_and_keys(pg):
    _veto(pg)
    headlines, earnings = pg.execute("SELECT headlines, earnings_date FROM news_vetoes").fetchone()
    assert (headlines, earnings) == ([], None)
    pg.commit()
    for dup in (
        {"rank": 2, "symbol": "NVDA"},  # (strategy, session, symbol) is the primary key
        {"rank": 1, "symbol": "AAPL"},  # (strategy, session, rank) is unique
    ):
        with pytest.raises(psycopg.errors.UniqueViolation):
            _veto(pg, **dup)
        pg.rollback()
    _veto(pg, session=date(2026, 10, 7))  # the same symbol and rank on another session is fine
    _veto(pg, strategy_id="A")  # ... and for another strategy
    pg.rollback()


def test_004_checks_reject_unknown_values(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        _veto(pg, verdict="maybe")
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        _veto(pg, rank=0)
    pg.rollback()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _veto(pg, strategy_id="B")
    pg.rollback()
