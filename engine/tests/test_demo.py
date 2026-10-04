"""Demo purge: all-or-nothing, keyed on the existence of a demo run, strategies and dividends kept."""

from __future__ import annotations

from datetime import date

import psycopg

from seer_engine.demo import DEMO_TABLES, has_demo, purge_demo, purge_demo_if_needed
from seer_engine.paper.roster import ROSTER

D = date(2026, 10, 2)
S = date(2026, 10, 5)
F4 = "F4-MOM12-N20-TREND"
PAPER_TABLES = ("paper_state", "book_positions", "book_targets", "book_fills", "book_trades")


def _seed(conn, *, demo: bool) -> None:
    """A slice of what web/scripts/seed-demo.mjs writes, plus one real dividend.

    The roster's ``strategies`` rows come from migrations 003 and 004 (the ``pg`` fixture
    applies them).
    """
    conn.execute(
        "INSERT INTO runs (status, data_date, session_date, is_demo, finished_at) "
        "VALUES ('success', %s, %s, %s, now())",
        (D, S, demo),
    )
    conn.execute("INSERT INTO fx_rates (date, usd_idr) VALUES (%s, 16530)", (D,))
    conn.execute("INSERT INTO bars VALUES ('NVDA', %s, 180, 180, 180, 180, 1000000)", (D,))
    order_id = conn.execute(
        "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, "
        "limit_price, tp_price, sl_price, shares, status) "
        "VALUES ('A', %s, 1, 'NVDA', 'NVIDIA', 180, 178, 185, 172, 10, 'pending') RETURNING id",
        (S,),
    ).fetchone()[0]
    conn.execute("INSERT INTO action_dismissals (order_id) VALUES (%s)", (order_id,))
    conn.execute(
        "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ('A', %s, 1000, 1000)",
        (D,),
    )
    conn.execute(
        "INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, "
        "usd_idr, pending_session, pending_decision) VALUES (%s, %s, 1000, 1000, 1000, 16530, %s, true)",
        (F4, D, S),
    )
    conn.execute(
        "INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, "
        "days_held, cost_usd, income_usd) VALUES (%s, 'NVDA', 5, 180, %s, 178, 1, 0.89, 0)",
        (F4, D),
    )
    conn.execute(
        "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price) "
        "VALUES (%s, %s, 1, 'NVDA', 0.05, 180)",
        (F4, S),
    )
    conn.execute(
        "INSERT INTO book_fills (strategy_id, session_date, seq, symbol, side, shares, price, "
        "cash_usd, cost_usd, reason) VALUES (%s, %s, 1, 'NVDA', 'buy', 5, 178, 890.89, 0.89, 'entry')",
        (F4, D),
    )
    conn.execute(
        "INSERT INTO book_trades (strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, "
        "days_held, cost_usd, income_usd, pnl_usd, exit_reason) "
        "VALUES (%s, 'AAPL', %s, %s, 200, 210, 20, 0.41, 0, 9.59, 'signal')",
        (F4, date(2026, 9, 1), D),
    )
    conn.execute(
        "INSERT INTO news_vetoes (strategy_id, session_date, rank, symbol, verdict, reason, model, "
        "prompt_version, decided_at) VALUES ('C', %s, 1, 'NVDA', 'veto', 'Earnings inside the window.', "
        "'glm-5.3', 'c-veto-v1', '2026-10-02 23:30+00')",
        (S,),
    )
    conn.execute("INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, 1.888834)", (D,))
    # The demo seed's paper clock on the roster rows (web/scripts/seed-demo.mjs writes both columns).
    conn.execute(
        "UPDATE strategies SET paper_start = %s, params = '{\"demo\": true, \"digest\": null}'::jsonb", (S,)
    )
    conn.commit()


def _clock(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute("SELECT paper_start, params FROM strategies ORDER BY id").fetchall()]


def _counts(conn) -> dict[str, int]:
    return {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in (*DEMO_TABLES, "strategies", "dividends")
    }


def test_demo_tables_cover_the_paper_tables_and_not_dividends():
    assert set(PAPER_TABLES) <= set(DEMO_TABLES)
    assert "news_vetoes" in DEMO_TABLES
    assert "dividends" not in DEMO_TABLES
    assert "strategies" not in DEMO_TABLES
    assert len(set(DEMO_TABLES)) == len(DEMO_TABLES)


def test_purge_empties_demo_tables_and_keeps_strategies_and_dividends(pg):
    _seed(pg, demo=True)
    assert all(_counts(pg)[t] >= 1 for t in DEMO_TABLES)
    assert has_demo(pg)
    assert purge_demo(pg) is True
    pg.commit()
    counts = _counts(pg)
    assert all(counts[t] == 0 for t in DEMO_TABLES)
    assert counts["strategies"] == len(ROSTER)
    assert counts["dividends"] == 1
    assert _clock(pg) == [(None, {})] * len(ROSTER)  # the demo paper clock is reset, the rows stay


def test_purge_restarts_identity(pg):
    _seed(pg, demo=True)
    purge_demo(pg)
    new_id = pg.execute(
        "INSERT INTO runs (status, is_demo) VALUES ('running', false) RETURNING id"
    ).fetchone()[0]
    assert new_id == 1
    fill_id = pg.execute(
        "INSERT INTO book_fills (strategy_id, session_date, seq, symbol, side, shares, price, "
        "cash_usd, cost_usd, reason) VALUES (%s, %s, 1, 'NVDA', 'buy', 1, 178, 178.18, 0.18, 'entry') "
        "RETURNING id",
        (F4, S),
    ).fetchone()[0]
    assert fill_id == 1


def test_no_demo_run_is_a_no_op(pg):
    _seed(pg, demo=False)
    before = (_counts(pg), _clock(pg))
    assert purge_demo(pg) is False
    assert (_counts(pg), _clock(pg)) == before


def test_purge_if_needed_commits_in_its_own_transaction(pg, pg_schema):
    _seed(pg, demo=True)
    assert purge_demo_if_needed(pg, dry_run=False) is True
    with psycopg.connect(pg_schema.url) as other:
        assert other.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert other.execute("SELECT count(*) FROM paper_state").fetchone()[0] == 0
        assert other.execute("SELECT count(*) FROM news_vetoes").fetchone()[0] == 0
        assert other.execute("SELECT count(*) FROM strategies").fetchone()[0] == len(ROSTER)
        assert other.execute("SELECT count(*) FROM dividends").fetchone()[0] == 1
        assert other.execute("SELECT count(*) FROM strategies WHERE paper_start IS NOT NULL").fetchone()[0] == 0
    assert purge_demo_if_needed(pg, dry_run=False) is False


def test_purge_if_needed_dry_run_keeps_everything(pg):
    _seed(pg, demo=True)
    before = (_counts(pg), _clock(pg))
    assert purge_demo_if_needed(pg, dry_run=True) is True
    assert (_counts(pg), _clock(pg)) == before


def test_purge_is_atomic_with_the_callers_transaction(pg):
    _seed(pg, demo=True)
    before = (_counts(pg), _clock(pg))
    purge_demo(pg)
    pg.rollback()
    assert (_counts(pg), _clock(pg)) == before
