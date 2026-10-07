"""``sean calibrate`` (Sean phase 7): Gotrade's fee schedule replayed over the owner's receipts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import psycopg
import pytest

from seer_engine import cli, db
from seer_engine.sean import calibrate
from seer_engine.sim import costs

FIXTURE = Path(__file__).parent / "fixtures" / "gotrade_fees.json"
CENT = Decimal("0.01")
SINCE = date(2026, 6, 16)
WIB = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class F:
    trading: Decimal
    regulatory: Decimal
    ppn: Decimal


def stand_in(side, amount, on=None):
    """A stand-in schedule: 0.2% with a $0.10 floor, $0.02 regulatory, 11% PPN, to the cent."""
    trading = max(Decimal("0.10"), (amount * Decimal("0.002")).quantize(CENT, ROUND_HALF_UP))
    regulatory = Decimal("0.02")
    ppn = ((trading + regulatory) * Decimal("0.11")).quantize(CENT, ROUND_HALF_UP)
    return F(trading, regulatory, ppn)


def paid(on, *, amount="27.90", trading="0.10", reg="0.02", ppn="0.01", side="buy",
         ref="order 1", symbol="MU"):
    return calibrate.PaidFees(
        ref=ref, on=on, side=side, symbol=symbol, amount=Decimal(amount),
        trading=Decimal(trading), regulatory=Decimal(reg), ppn=Decimal(ppn),
    )


# ---- the check, against a stand-in schedule ----------------------------------------------------


def test_an_order_that_matches_the_schedule_passes():
    cal = calibrate.check([paid(date(2026, 10, 7))], since=SINCE, fee=stand_in)
    assert cal.passed
    assert len(cal.current) == 1
    assert cal.residuals[0].gap == 0
    assert cal.residuals[0].expected_total == Decimal("0.13")


def test_a_cent_is_tolerated_and_two_cents_are_not():
    one = paid(date(2026, 10, 7), ppn="0.02")
    two = paid(date(2026, 10, 7), trading="0.12", ref="order 2")
    cal = calibrate.check([one, two], since=SINCE, fee=stand_in)
    assert cal.residuals[0].ok and cal.residuals[0].gap == CENT
    assert not cal.residuals[1].ok
    assert cal.misses == (cal.residuals[1],)
    assert not cal.passed


def test_an_older_regime_is_reported_but_never_fails():
    old = paid(date(2025, 6, 10), amount="1429.00", trading="0.00", reg="4.29", ppn="0.00")
    cal = calibrate.check([old], since=SINCE, fee=stand_in)
    r = cal.residuals[0]
    assert not r.ok and not r.current
    assert cal.passed
    assert "older schedule" in calibrate.format_report(cal)


def test_each_order_is_priced_on_its_own_date():
    seen = []

    def spy(side, amount, on=None):
        seen.append((side, amount, on))
        return stand_in(side, amount, on)

    calibrate.check([paid(date(2025, 7, 22), side="sell", amount="72.51")], since=SINCE, fee=spy)
    assert seen == [("sell", Decimal("72.51"), date(2025, 7, 22))]


def test_the_report_says_refit_when_a_current_order_is_off():
    cal = calibrate.check([paid(date(2026, 10, 7), trading="0.15")], since=SINCE, fee=stand_in)
    text = calibrate.format_report(cal)
    assert "OFF by up to $0.05" in text
    assert "refit the schedule" in text and "sim/costs.py" in text


def test_the_report_says_so_when_everything_matches():
    text = calibrate.format_report(calibrate.check([paid(date(2026, 10, 7))], since=SINCE, fee=stand_in))
    assert "All 1 order(s) since 2026-06-16 match the schedule" in text


def test_no_orders_is_a_pass():
    cal = calibrate.check([], since=SINCE, fee=stand_in)
    assert cal.passed
    assert "nothing to check" in calibrate.format_report(cal)


def test_a_receipt_time_is_read_as_a_wib_date():
    assert calibrate.wib_date(datetime(2026, 10, 7, 17, 30, tzinfo=timezone.utc)) == date(2026, 10, 8)
    assert calibrate.wib_date(datetime(2026, 10, 7, 21, 55, tzinfo=WIB)) == date(2026, 10, 7)
    with pytest.raises(ValueError, match="timezone-aware"):
        calibrate.wib_date(datetime(2026, 10, 7, 21, 55))


def test_paid_fees_refuse_signed_floats_and_unknown_sides():
    with pytest.raises(ValueError, match="non-negative"):
        paid(date(2026, 10, 7), trading="-0.10")
    with pytest.raises(ValueError, match="side"):
        paid(date(2026, 10, 7), side="short")
    with pytest.raises(TypeError, match="Decimal"):
        calibrate.PaidFees(ref="x", on=date(2026, 10, 7), side="buy", symbol="", amount=27.9,
                           trading=Decimal("0.10"), regulatory=Decimal("0.02"), ppn=Decimal("0.01"))


# ---- the real schedule, against Phase 6's fee fixture -------------------------------------------


def _fixture_rows(path: Path) -> list[calibrate.PaidFees]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["rows"] if isinstance(data, dict) else data
    return [
        calibrate.PaidFees(
            ref=f"row {i}", on=date.fromisoformat(str(r["date"])), side=str(r["side"]),
            symbol=str(r.get("symbol") or ""), amount=Decimal(str(r["amount"])).copy_abs(),
            trading=Decimal(str(r["trading"])).copy_abs(),
            regulatory=Decimal(str(r["regulatory"])).copy_abs(),
            ppn=Decimal(str(r["ppn"])).copy_abs(),
        )
        for i, r in enumerate(items, start=1)
    ]


def test_the_schedule_reproduces_every_current_receipt_in_the_fixture():
    cal = calibrate.check(_fixture_rows(FIXTURE), since=calibrate.current_since())
    assert cal.current, "the fee fixture holds receipts from the current regime"
    assert cal.passed, calibrate.format_report(cal)


def test_current_since_is_a_date_no_later_than_the_newest_receipt():
    since = calibrate.current_since()
    assert isinstance(since, date)
    assert since <= max(r.on for r in _fixture_rows(FIXTURE))


# ---- the command, with a stub connection --------------------------------------------------------


class StubConn:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False
        self.rolled_back = False

    def execute(self, sql, params=None):
        assert "FROM sean_orders" in sql
        return self

    def fetchall(self):
        return self.rows

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _row(oid, at, amount, *, nudge=Decimal("0")):
    e = costs.fee_parts("buy", amount, on=calibrate.wib_date(at))
    return (oid, "buy", f"S{oid}", at, amount, e.trading + nudge, e.regulatory, e.ppn)


def _at(day):
    return datetime(day.year, day.month, day.day, 21, 55, tzinfo=WIB)


def test_cli_exits_0_when_every_current_order_matches(monkeypatch, capsys):
    day = calibrate.current_since()
    stub = StubConn([_row(1, _at(day), Decimal("27.90")), _row(2, _at(day), Decimal("1673.14"))])
    monkeypatch.setattr(db, "connect", lambda url=None: stub)
    assert cli.main(["sean", "calibrate"]) == 0
    assert "match the schedule" in capsys.readouterr().out
    assert stub.closed and stub.rolled_back


def test_cli_exits_1_when_a_current_order_drifted(monkeypatch, capsys):
    day = calibrate.current_since()
    stub = StubConn([_row(1, _at(day), Decimal("27.90"), nudge=Decimal("0.05"))])
    monkeypatch.setattr(db, "connect", lambda url=None: stub)
    assert cli.main(["sean", "calibrate"]) == 1
    out = capsys.readouterr().out
    assert "OFF by up to $0.05" in out and "refit" in out


def test_cli_parses_calibrate():
    args = cli.build_parser().parse_args(["sean", "calibrate"])
    assert args.sean_command == "calibrate"


# ---- end to end on Postgres ----------------------------------------------------------------------


def _insert(conn, symbol, at, amount, fees):
    total = amount + fees.trading + fees.regulatory + fees.ppn
    conn.execute(
        """
        INSERT INTO sean_orders (side, order_type, status, symbol, executed_at, price, shares,
                                 amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd)
        VALUES ('buy', 'Market Buy', 'Filled', %s, %s, %s, 1, %s, %s, %s, %s, %s)
        """,
        (symbol, at, amount, amount, fees.trading, fees.regulatory, fees.ppn, total),
    )
    conn.commit()


def test_calibrate_reads_sean_orders(pg, pg_schema, monkeypatch, capsys):
    day = calibrate.current_since()
    at = _at(day)
    amount = Decimal("27.90")
    _insert(pg, "MU", at, amount, costs.fee_parts("buy", amount, on=day))
    monkeypatch.setattr(db, "connect", lambda url=None: psycopg.connect(pg_schema.url, autocommit=False))
    assert cli.main(["sean", "calibrate"]) == 0
    assert "1 since the current fee schedule" in capsys.readouterr().out

    e = costs.fee_parts("buy", amount, on=day)
    _insert(pg, "CNC", at, amount, F(e.trading + Decimal("0.05"), e.regulatory, e.ppn))
    assert cli.main(["sean", "calibrate"]) == 1
    assert "1 of 2 order(s)" in capsys.readouterr().out
