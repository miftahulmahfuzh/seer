"""Sean's ledger (plan contract B): unit cases, then the fixture shared with the web ledger."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

import pytest

from seer_engine import config
from seer_engine.sean import ledger
from seer_engine.sean.ledger import Order

FIXTURE = config.REPO_ROOT / "web" / "lib" / "sean" / "fixtures" / "ledger.json"
_POINT_FIELDS = ("value_usd", "cost_usd", "realized_usd", "unrealized_usd", "pnl_usd", "fees_usd")


def order(
    id: int,
    symbol: str,
    side: str,
    at: str,
    price: str,
    shares: str,
    total: str,
    fees: tuple[str, str, str] = ("0.10", "0.02", "0.01"),
) -> Order:
    return Order(
        id=id,
        symbol=symbol,
        side=side,
        executed_at=datetime.fromisoformat(at),
        price=Decimal(price),
        shares=Decimal(shares),
        total_usd=Decimal(total),
        trading_fee_usd=Decimal(fees[0]),
        regulatory_fee_usd=Decimal(fees[1]),
        ppn_usd=Decimal(fees[2]),
    )


def test_buy_puts_fees_in_the_cost_basis():
    led = ledger.build_ledger([order(1, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.13")])
    assert led.holdings == (ledger.Holding("MU", Decimal("0.250000000"), Decimal("30.13")),)
    assert led.realized_usd == Decimal("0.00")
    assert led.fees_usd == Decimal("0.13")


def test_sell_realizes_against_the_average_cost_with_fees():
    led = ledger.build_ledger([
        order(1, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.13"),
        order(2, "MU", "sell", "2026-06-18T03:10:00+07:00", "130.00", "0.1", "12.87"),
    ])
    # avg = 30.13 / 0.25 = 120.52; basis sold = 12.052; realized = 12.87 - 12.052 = 0.818
    assert led.realized_usd == Decimal("0.82")
    assert led.holdings == (ledger.Holding("MU", Decimal("0.150000000"), Decimal("18.08")),)
    assert led.fees_usd == Decimal("0.26")


def test_a_sell_of_more_than_held_counts_only_the_held_shares_and_their_money():
    led = ledger.build_ledger([
        order(1, "AAA", "buy", "2026-06-16T21:40:00+07:00", "10.00", "1", "10.13"),
        order(2, "AAA", "sell", "2026-06-17T21:40:00+07:00", "6.00", "2", "11.87"),
    ])
    assert led.holdings == ()
    # 1 of the 2 shares sold was known: proceeds 11.87 * 1 / 2 = 5.935; realized 5.935 - 10.13
    # = -4.195, half away from zero -> -4.20
    assert led.realized_usd == Decimal("-4.20")
    assert led.fees_usd == Decimal("0.26")


def test_a_sell_with_nothing_held_adds_only_its_fees():
    led = ledger.build_ledger([order(1, "AAA", "sell", "2026-06-17T21:40:00+07:00", "6.00", "1", "5.87")])
    assert led.holdings == ()
    assert led.realized_usd == Decimal("0.00")
    assert led.fees_usd == Decimal("0.13")


def test_selling_everything_then_buying_again_starts_a_fresh_basis():
    led = ledger.build_ledger([
        order(1, "AAA", "buy", "2026-06-16T21:40:00+07:00", "10.00", "1", "10.13"),
        order(2, "AAA", "sell", "2026-06-17T21:40:00+07:00", "11.00", "1", "10.87"),
        order(3, "AAA", "buy", "2026-06-18T21:40:00+07:00", "12.00", "2", "24.13"),
    ])
    assert led.holdings == (ledger.Holding("AAA", Decimal("2.000000000"), Decimal("24.13")),)
    assert led.realized_usd == Decimal("0.74")


def test_orders_apply_by_time_then_id_whatever_order_they_arrive_in():
    a = order(2, "AAA", "sell", "2026-06-17T21:40:00+07:00", "11.00", "1", "10.87")
    b = order(1, "AAA", "buy", "2026-06-17T21:40:00+07:00", "10.00", "1", "10.13")
    c = order(3, "AAA", "buy", "2026-06-16T21:40:00+07:00", "9.00", "1", "9.13")
    assert [o.id for o in ledger.sort_orders([a, b, c])] == [3, 1, 2]
    assert ledger.build_ledger([a, b, c]) == ledger.build_ledger([c, b, a])


def test_trade_date_is_the_new_york_date():
    late = order(1, "MU", "sell", "2026-06-18T03:10:00+07:00", "130.00", "0.1", "12.87")
    assert late.trade_date == date(2026, 6, 17)
    evening = order(2, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.13")
    assert evening.trade_date == date(2026, 6, 16)


def test_value_uses_the_last_close_on_or_before_the_date_else_the_last_order_price():
    orders = [
        order(1, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "1", "120.13"),
        order(2, "XYZ", "buy", "2026-06-16T22:00:00+07:00", "10.00", "2", "20.13"),
    ]
    closes = {"MU": [(date(2026, 6, 16), Decimal("121")), (date(2026, 6, 18), Decimal("125"))]}
    p = ledger.pnl_at(orders, date(2026, 6, 17), closes)
    assert p.value_usd == Decimal("141.00")  # MU at the 16th's close, XYZ at its order price
    assert p.cost_usd == Decimal("140.26")
    assert p.unrealized_usd == Decimal("0.74")
    assert p.pnl_usd == Decimal("0.74")
    assert p.fees_usd == Decimal("0.26")


def test_series_counts_only_orders_traded_on_or_before_each_date():
    orders = [
        order(1, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.13"),
        order(2, "XYZ", "buy", "2026-06-17T22:00:00+07:00", "10.00", "2", "20.13"),
        order(3, "MU", "sell", "2026-06-18T03:10:00+07:00", "130.00", "0.1", "12.87"),
    ]
    closes = {"MU": [(date(2026, 6, 16), Decimal("121")), (date(2026, 6, 17), Decimal("125"))]}
    p16, p17 = ledger.pnl_series(orders, [date(2026, 6, 16), date(2026, 6, 17)], closes)
    assert (p16.value_usd, p16.cost_usd, p16.pnl_usd, p16.fees_usd) == (
        Decimal("30.25"), Decimal("30.13"), Decimal("0.12"), Decimal("0.13"),
    )
    assert (p17.value_usd, p17.cost_usd, p17.realized_usd, p17.unrealized_usd, p17.pnl_usd, p17.fees_usd) == (
        Decimal("38.75"), Decimal("38.21"), Decimal("0.82"), Decimal("0.54"), Decimal("1.36"), Decimal("0.39"),
    )


def test_series_refuses_unsorted_dates():
    with pytest.raises(ValueError):
        ledger.pnl_series([], [date(2026, 6, 17), date(2026, 6, 16)], {})


def test_money_rounds_half_away_from_zero():
    assert ledger.money(Decimal("0.005")) == Decimal("0.01")
    assert ledger.money(Decimal("-0.005")) == Decimal("-0.01")
    assert ledger.money(Decimal("0.0049")) == Decimal("0.00")


def test_order_refuses_floats_bad_sides_and_naive_times():
    with pytest.raises(TypeError):
        ledger.order_from_mapping({
            "id": 1, "symbol": "MU", "side": "buy", "executed_at": "2026-06-16T21:40:00+07:00",
            "price": 120.0, "shares": "1", "total_usd": "120.13",
            "trading_fee_usd": "0.10", "regulatory_fee_usd": "0.02", "ppn_usd": "0.01",
        })
    with pytest.raises(ValueError):
        order(1, "MU", "hold", "2026-06-16T21:40:00+07:00", "1", "1", "1")
    with pytest.raises(ValueError):
        order(1, "MU", "buy", "2026-06-16T21:40:00", "1", "1", "1")


def test_shared_fixture_matches_the_web_ledger():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"), parse_float=Decimal)
    orders = [ledger.order_from_mapping(m) for m in data["orders"]]
    closes = ledger.closes_from_mapping(data["closes"])
    expected = data["expected"]

    led = ledger.build_ledger(orders)
    assert [(h.symbol, h.shares, h.cost_usd) for h in led.holdings] == [
        (p["symbol"], Decimal(str(p["shares"])), Decimal(str(p["cost_usd"]))) for p in expected["positions"]
    ]
    assert led.realized_usd == Decimal(str(expected["realized_usd"]))
    assert led.fees_usd == Decimal(str(expected["fees_usd"]))

    assert expected["points"], "the fixture must check at least one date"
    for want in expected["points"]:
        got = ledger.pnl_at(orders, date.fromisoformat(want["date"]), closes)
        for field in _POINT_FIELDS:
            assert getattr(got, field) == Decimal(str(want[field])), (want["date"], field)
