"""Point-in-time queries on ``universe`` (end_date exclusive, NULL = current)."""

from __future__ import annotations

from datetime import date

from seer_engine.universe import BENCHMARK, all_symbols, members_on, symbols_for_bars

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
