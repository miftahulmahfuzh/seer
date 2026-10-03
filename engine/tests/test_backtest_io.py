"""backtest.io: the read-only Neon loader (one COPY + pickle cache), dividends, report writer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pandas as pd
import psycopg
import pytest
from psycopg.pq import TransactionStatus

from seer_engine import bars, db, fx
from seer_engine.backtest import io as bio
from seer_engine.backtest.benchmark import Dividend
from seer_engine.prices import Bar

D1, D2, D3, D4 = date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)
Y2020, Y2021 = date(2020, 1, 2), date(2021, 1, 4)

BARS = [
    ("AAPL", D1, "100.1", "101.2345", "99.5", "100.9999", 1_000_000),
    ("AAPL", D2, "101", "102", "100", "1234.5678", 1_100_000),
    ("AAPL", D3, "102", "103", "101", "102.0001", 1_200_000),
    ("BRK.B", D2, "450", "455", "449", "452.25", 3_000_000),
    ("NA", D1, "10", "11", "9", "10.5", 500),  # 'NA' would be NaN under pandas' default NA parsing
    ("SPY", D1, "500", "505", "499", "501.1", 50_000_000),
    ("SPY", D2, "501", "506", "500", "502.2", 51_000_000),
    ("SPY", D3, "502", "507", "501", "503.3", 52_000_000),
]
UNIVERSE = [  # (symbol, index_id, start, end-exclusive | None)
    ("AAPL", "SP500", Y2020, None),
    ("AAPL", "NDX", Y2021, None),
    ("BRK.B", "SP500", Y2020, D2),
    ("MSFT", "SP500", Y2020, None),  # a member with no bars
    ("MSFT", "NDX", Y2020, D1),
]
FX = [(D1, "16000"), (D3, "16100.5")]


def seed_bars(conn, rows):
    with db.transaction(conn, False):
        bars.upsert_bars(conn, [bars.make_bar(*r) for r in rows])


def seed_universe(conn, rows):
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, %s, %s)",
                [(s, i, a, b, s) for s, i, a, b in rows],
            )


def seed_fx(conn, rows):
    with db.transaction(conn, False):
        fx.upsert_fx(conn, rows)


@pytest.fixture
def seeded(pg):
    seed_bars(pg, BARS)
    seed_universe(pg, UNIVERSE)
    seed_fx(pg, FX)
    return pg


def test_load_market_builds_histories_membership_and_fx(seeded, tmp_path):
    market, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == len(BARS)
    assert list(market.history) == ["AAPL", "BRK.B", "NA", "SPY"]

    h = market.history["AAPL"]
    assert h.symbol == "AAPL"
    assert h.dates.dtype == np.dtype("datetime64[D]")
    assert h.dates.tolist() == [D1, D2, D3]
    assert h.close.dtype == np.float64 and h.volume.dtype == np.float64
    assert h.close.tolist() == [float("100.9999"), float("1234.5678"), float("102.0001")]
    assert h.high.tolist()[0] == float("101.2345")
    assert h.volume.tolist() == [1_000_000.0, 1_100_000.0, 1_200_000.0]
    assert market.history["NA"].close.tolist() == [10.5]
    assert market.bar("AAPL", D2) == Bar(
        "AAPL", D2, Decimal("101.0000"), Decimal("102.0000"), Decimal("100.0000"),
        Decimal("1234.5678"), 1_100_000,
    )

    assert market.membership.intervals == (
        ("AAPL", Y2020, None),
        ("BRK.B", Y2020, D2),
        ("MSFT", Y2020, None),
    )
    assert market.membership.members_on(D1) == frozenset({"AAPL", "BRK.B", "MSFT"})
    assert market.membership.members_on(D2) == frozenset({"AAPL", "MSFT"})  # end is exclusive

    assert market.fx == ((D1, Decimal("16000.0000")), (D3, Decimal("16100.5000")))
    assert market.last_bar_date("SPY") == D3
    assert seeded.info.transaction_status == TransactionStatus.IDLE


def test_bars_are_loaded_with_one_streamed_copy(seeded, tmp_path, monkeypatch):
    statements = []
    real_copy = psycopg.Cursor.copy

    def spy_copy(self, statement, *args, **kwargs):
        statements.append(str(statement))
        return real_copy(self, statement, *args, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "copy", spy_copy)
    bio.load_market(seeded, cache_dir=tmp_path)
    assert statements == [bio.BARS_COPY_SQL]


def test_load_market_transaction_is_read_only(seeded, tmp_path, monkeypatch):
    def writing_read_fx(conn):
        conn.execute("INSERT INTO fx_rates (date, usd_idr) VALUES ('2026-10-01', 1)")
        return ()

    monkeypatch.setattr(bio, "read_fx", writing_read_fx)
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        bio.load_market(seeded, cache_dir=tmp_path)
    assert seeded.info.transaction_status == TransactionStatus.IDLE
    assert seeded.execute("SELECT count(*) FROM fx_rates").fetchone()[0] == len(FX)
    seeded.rollback()


def test_load_market_refuses_a_connection_mid_transaction(seeded, tmp_path):
    seeded.execute("SELECT 1")
    with pytest.raises(ValueError, match="no transaction in progress"):
        bio.load_market(seeded, cache_dir=tmp_path)
    seeded.rollback()


def test_cache_is_written_then_reused_without_a_copy(seeded, tmp_path, monkeypatch):
    first, _ = bio.load_market(seeded, cache_dir=tmp_path)
    expected = tmp_path / f"bars-{D3.isoformat()}-{len(BARS)}.pkl"
    assert sorted(tmp_path.iterdir()) == [expected]

    def no_copy(conn):
        raise AssertionError("the cache should have been used")

    monkeypatch.setattr(bio, "read_bars_frame", no_copy)
    second, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == len(BARS)
    assert list(second.history) == list(first.history)
    for symbol, h in first.history.items():
        g = second.history[symbol]
        for field in ("dates", "open", "high", "low", "close", "volume"):
            assert np.array_equal(getattr(h, field), getattr(g, field)), (symbol, field)


def test_changed_fingerprint_invalidates_the_cache(seeded, tmp_path):
    bio.load_market(seeded, cache_dir=tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == [f"bars-{D3.isoformat()}-8.pkl"]

    seed_bars(seeded, [("MSFT", D1, "400", "401", "399", "400.5", 9)])  # same max(date), +1 row
    market, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == 9 and "MSFT" in market.history
    assert [p.name for p in tmp_path.iterdir()] == [f"bars-{D3.isoformat()}-9.pkl"]

    seed_bars(seeded, [("AAPL", D4, "103", "104", "102", "103.5", 7)])  # new max(date)
    market, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == 10 and market.history["AAPL"].dates.tolist() == [D1, D2, D3, D4]
    assert [p.name for p in tmp_path.iterdir()] == [f"bars-{D4.isoformat()}-10.pkl"]


def test_refresh_rereads_a_valid_cache(seeded, tmp_path, monkeypatch):
    bio.load_market(seeded, cache_dir=tmp_path)
    calls = []
    real = bio.read_bars_frame

    def counting(conn):
        calls.append(1)
        return real(conn)

    monkeypatch.setattr(bio, "read_bars_frame", counting)
    bio.load_market(seeded, cache_dir=tmp_path)
    assert calls == []
    bio.load_market(seeded, cache_dir=tmp_path, refresh=True)
    assert calls == [1]


def test_corrupt_cache_is_replaced(seeded, tmp_path):
    path = tmp_path / f"bars-{D3.isoformat()}-{len(BARS)}.pkl"
    path.write_bytes(b"not a pickle")
    market, _ = bio.load_market(seeded, cache_dir=tmp_path)
    assert "AAPL" in market.history
    assert len(pd.read_pickle(path, compression=None)) == len(BARS)


def test_empty_bars_is_a_load_error(pg, tmp_path):
    with pytest.raises(bio.LoadError, match="bars table is empty"):
        bio.load_market(pg, cache_dir=tmp_path)
    assert pg.info.transaction_status == TransactionStatus.IDLE
    assert list(tmp_path.iterdir()) == []


def test_merge_intervals_unions_indices_per_symbol():
    a, b, c, d = date(2016, 1, 4), date(2017, 1, 3), date(2018, 1, 2), date(2019, 1, 2)
    rows = [
        ("X", b, d),
        ("X", a, c),  # overlaps the first
        ("Y", a, b),
        ("Y", b, c),  # touches: one interval
        ("Y", d, None),  # gap, then open-ended
        ("Z", a, None),
        ("Z", b, c),  # inside an open interval
    ]
    assert bio.merge_intervals(rows) == (
        ("X", a, d),
        ("Y", a, c),
        ("Y", d, None),
        ("Z", a, None),
    )


def test_histories_from_frame_rejects_unsorted_dates():
    frame = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "date": pd.to_datetime(["2026-09-29", "2026-09-28"], format="%Y-%m-%d"),
            "open": [1.0, 1.0],
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
            "volume": [1, 1],
        }
    )
    with pytest.raises(bio.LoadError, match="strictly ascending"):
        bio.histories_from_frame(frame)


def test_histories_from_frame_rejects_non_contiguous_symbols():
    frame = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "AAA"],
            "date": pd.to_datetime(["2026-09-28", "2026-09-28", "2026-09-29"], format="%Y-%m-%d"),
            "open": [1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0],
            "volume": [1, 1, 1],
        }
    )
    with pytest.raises(bio.LoadError, match="not contiguous"):
        bio.histories_from_frame(frame)


def test_read_dividends(tmp_path):
    path = tmp_path / "div.csv"
    path.write_text("ex_date,amount_usd\n2026-03-20,1.7\n2026-06-20,1.75\n", encoding="utf-8")
    assert bio.read_dividends(path) == (
        Dividend(date(2026, 3, 20), Decimal("1.7")),
        Dividend(date(2026, 6, 20), Decimal("1.75")),
    )


def test_write_report_writes_three_files_with_lf(tmp_path, monkeypatch):
    monkeypatch.setattr(bio, "render_markdown", lambda r: "# report\nline\n")
    monkeypatch.setattr(bio, "equity_csv", lambda r: "date,strategy\n2026-10-02,1\n")
    monkeypatch.setattr(bio, "equity_svg", lambda r: "<svg/>\n")
    report = SimpleNamespace(data_end=date(2026, 10, 2))
    out = tmp_path / "nested" / "backtests"
    paths = bio.write_report(out, report)
    assert paths == [
        out / "2026-10-02-strategy-a.md",
        out / "2026-10-02-strategy-a-equity.csv",
        out / "2026-10-02-strategy-a-equity.svg",
    ]
    assert paths[0].read_bytes() == b"# report\nline\n"
    assert paths[1].read_bytes() == b"date,strategy\n2026-10-02,1\n"
    assert paths[2].read_bytes() == b"<svg/>\n"


def test_write_report_renders_everything_before_writing(tmp_path, monkeypatch):
    def boom(report):
        raise RuntimeError("svg failed")

    monkeypatch.setattr(bio, "render_markdown", lambda r: "md")
    monkeypatch.setattr(bio, "equity_csv", lambda r: "csv")
    monkeypatch.setattr(bio, "equity_svg", boom)
    with pytest.raises(RuntimeError, match="svg failed"):
        bio.write_report(tmp_path / "out", SimpleNamespace(data_end=date(2026, 10, 2)))
    assert not (tmp_path / "out").exists()
