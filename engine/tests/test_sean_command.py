"""`sean marks`: closes in, daily P&L series out, against a real Postgres."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from seer_engine import cli, dates
from seer_engine.commands import sean as sean_cmd

NOW = datetime(2026, 6, 23, 0, 0, tzinfo=timezone.utc)  # last completed session: Mon 2026-06-22
MU_CLOSES = {
    date(2026, 6, 16): Decimal("121"),
    date(2026, 6, 17): Decimal("125"),
    date(2026, 6, 18): Decimal("128"),
    date(2026, 6, 22): Decimal("130"),
}


def add_order(conn, symbol, side, at, price, shares, amount, total):
    conn.execute(
        """
        INSERT INTO sean_orders (side, order_type, status, symbol, executed_at, price, shares,
                                 amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd)
        VALUES (%s, %s, 'Filled', %s, %s, %s, %s, %s, 0.10, 0.02, 0.01, %s)
        """,
        (side, "Market Buy" if side == "buy" else "Market Sell", symbol, datetime.fromisoformat(at),
         Decimal(price), Decimal(shares), Decimal(amount), Decimal(total)),
    )
    conn.commit()


def seed(conn):
    add_order(conn, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.00", "30.13")
    add_order(conn, "XYZ", "buy", "2026-06-17T22:00:00+07:00", "10.00", "2", "20.00", "20.13")
    add_order(conn, "MU", "sell", "2026-06-18T03:10:00+07:00", "130.00", "0.1", "13.00", "12.87")


class FakeYahoo:
    def __init__(self):
        self.calls = []

    def __call__(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        if symbol == "XYZ":
            raise RuntimeError("delisted")
        return [(d, c) for d, c in sorted(MU_CLOSES.items()) if start <= d <= end]


def equity_rows(conn):
    return conn.execute(
        "SELECT date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd "
        "FROM sean_equity ORDER BY date"
    ).fetchall()


def test_no_orders_is_a_no_op_that_clears_a_stale_series(pg):
    pg.execute(
        "INSERT INTO sean_equity (date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd) "
        "VALUES ('2026-06-16', 1, 1, 0, 0, 0, 0)"
    )
    pg.commit()

    def fetch(symbol, start, end):
        raise AssertionError("no orders: nothing to fetch")

    assert sean_cmd.execute_marks(pg, now_utc=NOW, fetch=fetch) == 0
    assert equity_rows(pg) == []


def test_marks_and_series(pg):
    seed(pg)
    fake = FakeYahoo()
    assert sean_cmd.execute_marks(pg, now_utc=NOW, fetch=fake) == 0

    assert fake.calls == [("MU", date(2026, 6, 16), date(2026, 6, 22)), ("XYZ", date(2026, 6, 17), date(2026, 6, 22))]
    assert pg.execute("SELECT count(*) FROM sean_marks WHERE symbol = 'MU'").fetchone()[0] == 4
    assert pg.execute("SELECT count(*) FROM sean_marks WHERE symbol = 'XYZ'").fetchone()[0] == 0

    rows = equity_rows(pg)
    assert [r[0] for r in rows] == dates.sessions(date(2026, 6, 16), date(2026, 6, 22))
    assert [r[0] for r in rows] == [date(2026, 6, 16), date(2026, 6, 17), date(2026, 6, 18), date(2026, 6, 22)]
    D = Decimal
    assert rows[0][1:] == (D("30.25"), D("30.13"), D("0.00"), D("0.12"), D("0.12"), D("0.13"))
    # the 03:10 WIB sell is the 17th's session; XYZ has no close, so its order price stands
    assert rows[1][1:] == (D("38.75"), D("38.21"), D("0.82"), D("0.54"), D("1.36"), D("0.39"))
    assert rows[2][1:] == (D("39.20"), D("38.21"), D("0.82"), D("0.99"), D("1.81"), D("0.39"))
    assert rows[3][1:] == (D("39.50"), D("38.21"), D("0.82"), D("1.29"), D("2.11"), D("0.39"))


def test_a_rerun_replaces_the_series_and_keeps_stored_closes_when_yahoo_fails(pg):
    seed(pg)
    assert sean_cmd.execute_marks(pg, now_utc=NOW, fetch=FakeYahoo()) == 0
    before = equity_rows(pg)

    def down(symbol, start, end):
        raise RuntimeError("yahoo is down")

    assert sean_cmd.execute_marks(pg, now_utc=NOW, fetch=down) == 0
    assert equity_rows(pg) == before


def test_dry_run_writes_nothing(pg):
    seed(pg)
    assert sean_cmd.execute_marks(pg, now_utc=NOW, dry_run=True, fetch=FakeYahoo()) == 0
    assert equity_rows(pg) == []
    assert pg.execute("SELECT count(*) FROM sean_marks").fetchone()[0] == 0


def test_cli_parses_the_marks_subcommand():
    args = cli.build_parser().parse_args(["sean", "marks", "--now", "2026-06-23T00:00:00Z"])
    assert args.sean_command == "marks"
    assert args.now == NOW
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["sean"])


def test_cli_end_to_end_on_an_empty_database(pg_schema, pg, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", pg_schema.url)
    assert cli.main(["sean", "marks", "--now", "2026-06-23T00:00:00Z"]) == 0
    assert cli.main(["--dry-run", "sean", "marks", "--now", "2026-06-23T00:00:00Z"]) == 0
    assert equity_rows(pg) == []
