"""Point-in-time queries on ``universe`` (end_date exclusive, NULL = current)."""

from __future__ import annotations

from datetime import date

from seer_engine.universe import BENCHMARK, all_symbols, members_on, paper_symbols, symbols_for_bars

ROWS = [
    # symbol, index_id, start, end (exclusive), source_symbol
    ("AAPL", "SP500", "2015-01-02", None, "AAPL"),
    ("AAPL", "NDX", "2015-01-02", None, "AAPL"),
    ("META", "SP500", "2015-01-02", None, "FB"),
    ("OLD", "SP500", "2015-01-02", "2020-06-01", "OLD"),
    ("LEFT", "NDX", "2018-01-02", "2026-09-21", "LEFT"),
    ("NEW", "SP500", "2026-09-21", None, "NEW"),
    # Left and came back: two intervals.
    ("BACK", "SP500", "2016-01-04", "2018-01-02", "BACK"),
    ("BACK", "SP500", "2020-01-02", None, "BACK"),
]


def _load(conn) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
            "VALUES (%s, %s, %s, %s, %s)",
            ROWS,
        )


def test_members_on(pg):
    _load(pg)
    assert members_on(pg, date(2026, 9, 18)) == {"AAPL", "META", "LEFT", "BACK"}
    # end_date is exclusive, start_date inclusive.
    assert members_on(pg, date(2026, 9, 21)) == {"AAPL", "META", "BACK", "NEW"}
    assert members_on(pg, date(2019, 1, 2)) == {"AAPL", "META", "OLD", "LEFT"}
    assert BENCHMARK not in members_on(pg, date(2026, 9, 21))


def test_symbols_for_bars_keeps_recent_leavers_and_spy(pg):
    _load(pg)
    d = date(2026, 10, 2)  # LEFT left 11 days ago
    assert symbols_for_bars(pg, d) == {"AAPL", "META", "BACK", "NEW", "LEFT", "SPY"}
    assert symbols_for_bars(pg, d, grace_days=5) == {"AAPL", "META", "BACK", "NEW", "SPY"}
    assert "NEW" not in symbols_for_bars(pg, date(2026, 9, 18))


def test_all_symbols_since(pg):
    _load(pg)
    assert all_symbols(pg, date(2015, 1, 2)) == [
        "AAPL", "BACK", "LEFT", "META", "NEW", "OLD", "SPY"
    ]
    assert all_symbols(pg, date(2021, 1, 4)) == ["AAPL", "BACK", "LEFT", "META", "NEW", "SPY"]


def test_empty_universe_still_has_benchmark(pg):
    assert symbols_for_bars(pg, date(2026, 10, 2)) == {"SPY"}
    assert all_symbols(pg, date(2015, 1, 2)) == ["SPY"]
    assert members_on(pg, date(2026, 10, 2)) == set()


def test_check_constraints(pg):
    import psycopg
    import pytest

    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute(
            "INSERT INTO universe VALUES ('X', 'SP500', '2020-01-02', '2020-01-02', 'X')"
        )
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("INSERT INTO universe VALUES ('X', 'DJI', '2020-01-02', NULL, 'X')")


def _paper_state(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO strategies (id, name, sub, icon) VALUES ('T1', 'T1', '', 'sigma') ON CONFLICT (id) DO NOTHING"
        )
        cur.executemany(
            "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, "
            "tp_price, sl_price, shares, status) VALUES ('T1', %s, %s, %s, %s, 10, 10, 11, 9, 1, %s)",
            [
                (date(2026, 9, 28), 1, "PEND", "Pending Co", "pending"),
                (date(2026, 9, 21), 2, "OPEN", "Open Co", "open"),
                (date(2026, 9, 14), 3, "DONE", "Closed Co", "closed"),
                (date(2026, 9, 14), 4, "EXP", "Expired Co", "expired"),
            ],
        )
        cur.execute(
            "INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, days_held, "
            "cost_usd, income_usd) VALUES ('T1', 'HELD', 3, 50, '2026-09-01', 48, 20, 0.5, 0)"
        )
        cur.executemany(
            "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price) "
            "VALUES ('T1', %s, %s, %s, 0.5, 20)",
            [
                (date(2026, 9, 1), 1, "PAST"),
                (date(2026, 10, 2), 1, "TODAY"),
                (date(2026, 10, 5), 1, "NEXT"),
            ],
        )


def test_paper_symbols_open_orders_positions_and_current_targets(pg):
    _paper_state(pg)
    assert paper_symbols(pg, date(2026, 10, 2)) == {"PEND", "OPEN", "HELD", "TODAY", "NEXT"}
    assert paper_symbols(pg, date(2026, 10, 5)) == {"PEND", "OPEN", "HELD", "NEXT"}
    pg.rollback()


def test_paper_symbols_empty_without_paper_state(pg):
    assert paper_symbols(pg, date(2026, 10, 2)) == set()
    pg.rollback()
