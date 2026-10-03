"""Demo purge: all-or-nothing, keyed on the existence of a demo run, strategies kept."""

from __future__ import annotations

from datetime import date

import psycopg

from seer_engine.demo import DEMO_TABLES, has_demo, purge_demo, purge_demo_if_needed

D = date(2026, 10, 2)
S = date(2026, 10, 5)


def _seed(conn, *, demo: bool) -> None:
    """A slice of what web/scripts/seed-demo.mjs writes."""
    conn.execute(
        "INSERT INTO strategies (id, name, sub, icon, sort) VALUES "
        "('A', 'A · Quant', 'Mean Reversion', 'sigma', 1), ('SPY', 'SPY', 'Benchmark', 'flag', 9)"
    )
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
    conn.commit()


def _counts(conn) -> dict[str, int]:
    return {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in (*DEMO_TABLES, "strategies")
    }


def test_purge_empties_demo_tables_and_keeps_strategies(pg):
    _seed(pg, demo=True)
    assert has_demo(pg)
    assert purge_demo(pg) is True
    pg.commit()
    counts = _counts(pg)
    assert all(counts[t] == 0 for t in DEMO_TABLES)
    assert counts["strategies"] == 2


def test_purge_restarts_identity(pg):
    _seed(pg, demo=True)
    purge_demo(pg)
    new_id = pg.execute(
        "INSERT INTO runs (status, is_demo) VALUES ('running', false) RETURNING id"
    ).fetchone()[0]
    assert new_id == 1


def test_no_demo_run_is_a_no_op(pg):
    _seed(pg, demo=False)
    before = _counts(pg)
    assert purge_demo(pg) is False
    assert _counts(pg) == before


def test_purge_if_needed_commits_in_its_own_transaction(pg, pg_schema):
    _seed(pg, demo=True)
    assert purge_demo_if_needed(pg, dry_run=False) is True
    with psycopg.connect(pg_schema.url) as other:
        assert other.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert other.execute("SELECT count(*) FROM strategies").fetchone()[0] == 2
    assert purge_demo_if_needed(pg, dry_run=False) is False


def test_purge_if_needed_dry_run_keeps_everything(pg):
    _seed(pg, demo=True)
    before = _counts(pg)
    assert purge_demo_if_needed(pg, dry_run=True) is True
    assert _counts(pg) == before


def test_purge_is_atomic_with_the_callers_transaction(pg):
    _seed(pg, demo=True)
    before = _counts(pg)
    purge_demo(pg)
    pg.rollback()
    assert _counts(pg) == before
