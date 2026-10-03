"""Fill simulator: money helpers, model invariants and the one-session lifecycle.

Every rule in design §5 and fill-simulator handover §3 / §6.1 that phase 1 owns has a test
here, on synthetic bars. Real NYSE dates (via seer_engine.dates) are used throughout:
2026-10-05 is a Monday; Thanksgiving 2026-11-26 is a holiday and 2026-11-27 a half day.
No database needed.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim import (
    COST_RATE,
    SLOTS,
    TIME_STOP_DAYS,
    Event,
    Order,
    Portfolio,
    Snapshot,
    buy_cost,
    close_unpriced,
    initial_cash_usd,
    new_portfolio,
    q,
    sell_proceeds,
    step,
)
from simkit import D, P, bar, day, opened, pending, portfolio

MON = "2026-10-05"
TUE = "2026-10-06"
WED = "2026-10-07"
THU = "2026-10-08"
FRI = "2026-10-09"
MON2 = "2026-10-12"
TUE2 = "2026-10-13"


def _only(events: tuple[Event, ...]) -> Event:
    assert len(events) == 1, events
    return events[0]


# ============================================================== money helpers and model


def test_constants():
    assert SLOTS == 4
    assert TIME_STOP_DAYS == 5
    assert COST_RATE == Decimal("0.001")


def test_q_rounds_half_up_to_4dp():
    assert q(Decimal("1.00005")) == Decimal("1.0001")
    assert q(Decimal("1.00004999")) == Decimal("1.0000")
    assert q(Decimal("-1.00005")) == Decimal("-1.0001")  # half-up = away from zero
    assert str(q(Decimal("7"))) == "7.0000"


def test_buy_cost_and_sell_proceeds():
    # 100 × 50 = 5000; × 1.001 = 5005; × 0.999 = 4995
    assert buy_cost(P("50"), 100) == Decimal("5005.0000")
    assert sell_proceeds(P("50"), 100) == Decimal("4995.0000")
    # 7 × 12.3457 = 86.4199; × 1.001 = 86.5063199 -> 86.5063
    assert buy_cost(P("12.3457"), 7) == Decimal("86.5063")
    # 7 × 11.1111 = 77.7777; × 0.999 = 77.6999223 -> 77.6999
    assert sell_proceeds(P("11.1111"), 7) == Decimal("77.6999")


def test_initial_cash_usd():
    # 20,000,000 / 16,250 = 1230.769230... -> 1230.7692
    assert initial_cash_usd(Decimal("20000000"), Decimal("16250")) == Decimal("1230.7692")


@pytest.mark.parametrize(
    "call",
    [
        lambda: q(1.5),
        lambda: buy_cost(50.0, 1),
        lambda: sell_proceeds(Decimal("50"), 1.0),
        lambda: buy_cost(Decimal("50"), True),
        lambda: initial_cash_usd(20_000_000.0, Decimal("16250")),
        lambda: new_portfolio(1000.0),
    ],
)
def test_floats_are_refused(call):
    with pytest.raises(TypeError):
        call()


def test_new_portfolio():
    p = new_portfolio(Decimal("1230.76923"))
    assert p.cash == p.equity == Decimal("1230.7692")
    assert p.orders == () and p.marks == () and p.last_session is None
    assert p.free_slots() == (1, 2, 3, 4)


def test_portfolio_helpers():
    a = opened("AAA", MON, "10", "11", "9", 10, days_held=2, slot=3)
    b = pending("BBB", TUE, "20", "22", "18", 5, slot=1)
    p = portfolio("1000", a, b, marks={"AAA": "10.5"})
    assert [o.slot for o in p.orders] == [1, 3]
    assert p.open_orders() == (a,)
    assert p.pending_orders() == (b,)
    assert p.free_slots() == (2, 4)
    assert p.held_symbols() == ("AAA", "BBB")
    assert p.mark("AAA") == Decimal("10.5000")
    assert p.mark("BBB") is None
    assert p.equity == Decimal("1105.0000")  # 1000 + 10 × 10.5


@pytest.mark.parametrize(
    "build",
    [
        # two orders in one slot
        lambda: Portfolio(
            P("1"), P("1"), (pending("A", MON, "10", "11", "9", 1), pending("B", MON, "10", "11", "9", 1))
        ),
        # not sorted by slot
        lambda: Portfolio(
            P("1"),
            P("1"),
            (pending("A", MON, "10", "11", "9", 1, slot=2), pending("B", MON, "10", "11", "9", 1, slot=1)),
        ),
        # one symbol twice
        lambda: Portfolio(
            P("1"),
            P("1"),
            (pending("A", MON, "10", "11", "9", 1, slot=1), pending("A", MON, "10", "11", "9", 1, slot=2)),
        ),
        # a terminal order
        lambda: Portfolio(P("1"), P("1"), (replace(pending("A", MON, "10", "11", "9", 1), status="expired"),)),
        # an open order without a mark
        lambda: Portfolio(P("1"), P("1"), (opened("A", MON, "10", "11", "9", 1, 1),)),
        # a mark without an open order
        lambda: Portfolio(P("1"), P("1"), (), (("A", P("10")),)),
    ],
)
def test_portfolio_rejects_broken_state(build):
    with pytest.raises(ValueError):
        build()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"slot": 0},
        {"slot": 5},
        {"shares": 0},
        {"sl_price": P("11"), "tp_price": P("11")},
        {"limit_price": P("0")},
        {"status": "open"},  # open without fill fields
        {"days_held": 1},  # pending with days held
    ],
)
def test_order_rejects_bad_fields(kwargs):
    base = pending("AAA", MON, "10", "11", "9", 10)
    with pytest.raises(ValueError):
        replace(base, **kwargs)


def test_order_refuses_float_prices():
    base = pending("AAA", MON, "10", "11", "9", 10)
    with pytest.raises(TypeError):
        replace(base, limit_price=10.0)
    with pytest.raises(TypeError):
        replace(base, shares=10.0)


# ============================================================== entry (fill)


def test_entry_touch_does_not_fill_and_expires():
    # low == limit: a touch is not a fill (strict low < limit).
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10, slot=2))
    r = step(p, D(MON), day(bar("AAA", MON, "10.20", "10.50", "10", "10.30")))
    ev = _only(r.events)
    assert ev.kind == "expire" and ev.cash_usd is None
    assert ev.order.status == "expired" and ev.order.fill_price is None
    assert r.portfolio.orders == ()
    assert r.portfolio.free_slots() == (1, 2, 3, 4)  # slot freed
    assert r.portfolio.cash == Decimal("1000.0000")
    assert r.snapshot == Snapshot(D(MON), Decimal("1000.0000"), Decimal("1000.0000"))


def test_entry_penetrate_fills_at_limit():
    # low one tick below the limit fills; open above the limit -> fill at the limit.
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("AAA", MON, "10.20", "10.50", "9.9999", "10.30")))
    ev = _only(r.events)
    assert ev.kind == "fill"
    o = ev.order
    assert (o.status, o.fill_date, o.fill_price, o.days_held) == ("open", D(MON), Decimal("10.0000"), 1)
    # cost = 10 × 10 × 1.001 = 100.1000
    assert ev.cash_usd == Decimal("-100.1000")
    assert r.portfolio.cash == Decimal("899.9000")
    # equity = 899.9000 + 10 × 10.30 (close) = 1002.9000
    assert r.snapshot.equity_usd == Decimal("1002.9000")
    assert r.portfolio.equity == Decimal("1002.9000")
    assert r.portfolio.marks == (("AAA", Decimal("10.3000")),)
    assert r.portfolio.last_session == D(MON)


def test_entry_open_below_limit_fills_at_open():
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("AAA", MON, "9.80", "10.40", "9.70", "10.10")))
    ev = _only(r.events)
    assert ev.order.fill_price == Decimal("9.8000")
    # cost = 10 × 9.80 × 1.001 = 98.0980
    assert ev.cash_usd == Decimal("-98.0980")
    assert r.portfolio.cash == Decimal("901.9020")


def test_entry_open_equal_to_limit_fills_at_limit():
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("AAA", MON, "10", "10.40", "9.70", "10.10")))
    assert _only(r.events).order.fill_price == Decimal("10.0000")


def test_missing_bar_for_pending_order_expires():
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("ZZZ", MON, "1", "1", "1", "1")))
    ev = _only(r.events)
    assert ev.kind == "expire" and ev.order.status == "expired"
    assert r.portfolio.orders == ()


def test_no_tp_sl_check_on_the_fill_session():
    # The fill bar spans both SL (9) and TP (11): the position is filled and stays open.
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("AAA", MON, "10.50", "11.50", "8.50", "10.20")))
    ev = _only(r.events)
    assert ev.kind == "fill"
    (o,) = r.portfolio.orders
    assert o.status == "open" and o.days_held == 1


# ============================================================== TP and SL


def _held(days_held: int = 1, shares: int = 10) -> Portfolio:
    # Bought 10 AAA at 10 on MON: cost 100.1000, cash left 899.9000.
    return portfolio("899.9", opened("AAA", MON, "10", "11", "9", shares, days_held), last_session=MON)


def test_tp_touch_does_not_exit():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "10.50", "11", "10.20", "10.80")))
    assert r.events == ()
    (o,) = r.portfolio.orders
    assert o.days_held == 2
    assert r.portfolio.mark("AAA") == Decimal("10.8000")
    # equity = 899.9000 + 10 × 10.80 = 1007.9000
    assert r.snapshot.equity_usd == Decimal("1007.9000")


def test_tp_penetrate_exits_at_tp():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "10.50", "11.0001", "10.20", "10.80")))
    ev = _only(r.events)
    o = ev.order
    assert ev.kind == "exit" and not ev.forced
    assert (o.status, o.exit_reason, o.exit_price, o.exit_date) == ("closed", "tp", Decimal("11.0000"), D(TUE))
    assert o.days_held == 2  # intraday exit on day 2 counts day 2
    # proceeds = 10 × 11 × 0.999 = 109.8900; pnl = 109.8900 − 100.1000 = 9.7900
    # handover formula: (11 − 10) × 10 − 0.001 × (11 + 10) × 10 = 10 − 0.21 = 9.79
    assert ev.cash_usd == Decimal("109.8900")
    assert o.pnl_usd == Decimal("9.7900")
    assert r.portfolio.cash == Decimal("1009.7900")
    assert r.snapshot.equity_usd == Decimal("1009.7900")
    assert r.portfolio.orders == () and r.portfolio.marks == ()


def test_sl_touch_exits_at_sl():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "9.80", "10.10", "9", "9.50")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.days_held) == ("sl", Decimal("9.0000"), 2)
    # proceeds = 10 × 9 × 0.999 = 89.9100; pnl = 89.9100 − 100.1000 = −10.1900
    # formula: (9 − 10) × 10 − 0.001 × 19 × 10 = −10 − 0.19 = −10.19
    assert o.pnl_usd == Decimal("-10.1900")
    assert r.portfolio.cash == Decimal("989.8100")


def test_sl_and_tp_on_the_same_bar_takes_sl_first():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "10", "11.50", "8.90", "10.60")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price) == ("sl", Decimal("9.0000"))


def test_gap_down_through_sl_exits_at_open_reason_gap():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "8.50", "8.90", "8.00", "8.20")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price) == ("gap", Decimal("8.5000"))
    assert o.days_held == 1  # exit at the open of day 2 records the days before it
    # proceeds = 85 × 0.999 = 84.9150; pnl = 84.9150 − 100.1000 = −15.1850
    # formula: (8.5 − 10) × 10 − 0.001 × 18.5 × 10 = −15 − 0.185 = −15.185
    assert o.pnl_usd == Decimal("-15.1850")


def test_open_exactly_at_sl_is_a_gap_exit():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "9", "9.50", "8.80", "9.20")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price) == ("gap", Decimal("9.0000"))


def test_gap_up_through_tp_exits_at_open_reason_tp():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "11.40", "11.90", "11.20", "11.60")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.days_held) == ("tp", Decimal("11.4000"), 1)
    # proceeds = 114 × 0.999 = 113.8860; pnl = 113.8860 − 100.1000 = 13.7860
    # formula: (11.4 − 10) × 10 − 0.001 × 21.4 × 10 = 14 − 0.214 = 13.786
    assert o.pnl_usd == Decimal("13.7860")


def test_open_exactly_at_tp_exits_at_open_reason_tp():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "11", "11", "10.50", "10.70")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price) == ("tp", Decimal("11.0000"))


def test_pnl_to_the_cent_with_rounding():
    # 7 shares filled at 12.3457, SL hit at 11.1111.
    p = portfolio(
        "913.4937",
        opened("XYZ", MON, "12.3457", "13.5", "11.1111", 7, days_held=1),
        last_session=MON,
    )
    r = step(p, D(TUE), day(bar("XYZ", TUE, "12", "12.10", "11.00", "11.05")))
    o = _only(r.events).order
    # buy_cost = q(86.4199 × 1.001 = 86.5063199) = 86.5063
    # proceeds = q(77.7777 × 0.999 = 77.6999223) = 77.6999
    # pnl = 77.6999 − 86.5063 = −8.8064
    # formula: (11.1111 − 12.3457) × 7 − 0.001 × 23.4568 × 7 = −8.6422 − 0.1641976 = −8.8063976
    assert o.pnl_usd == Decimal("-8.8064")
    assert abs(o.pnl_usd - Decimal("-8.8063976")) <= Decimal("0.0001")
    # cash = 913.4937 + 77.6999 = 991.1936
    assert r.portfolio.cash == Decimal("991.1936")


def test_round_trip_pnl_reconciles_with_cash():
    # Fill then exit via step: cash change equals pnl exactly.
    start = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r1 = step(start, D(MON), day(bar("AAA", MON, "9.95", "10.10", "9.90", "10.05")))
    # fill at open 9.95: cost = 99.5 × 1.001 = 99.5995
    assert r1.portfolio.cash == Decimal("900.4005")
    r2 = step(r1.portfolio, D(TUE), day(bar("AAA", TUE, "10.40", "11.20", "10.30", "11.10")))
    o = _only(r2.events).order
    # proceeds = 110 × 0.999 = 109.8900; pnl = 109.8900 − 99.5995 = 10.2905
    assert o.pnl_usd == Decimal("10.2905")
    assert r2.portfolio.cash - start.cash == o.pnl_usd
    assert r2.portfolio.cash == Decimal("1010.2905")


# ============================================================== time stop


@pytest.mark.parametrize(
    ("session", "days_before"),
    [(TUE, 1), (WED, 2), (THU, 3), (FRI, 4)],
)
def test_days_held_counts_each_session(session, days_before):
    p = portfolio(
        "899.9",
        opened("AAA", MON, "10", "11", "9", 10, days_held=days_before),
        last_session=dates.prev_session(D(session)),
    )
    r = step(p, D(session), day(bar("AAA", session, "10", "10.5", "9.5", "10")))
    assert r.events == ()
    assert r.portfolio.orders[0].days_held == days_before + 1


def test_time_stop_at_the_open_of_day_6():
    # Fill MON (day 1); TUE..FRI are days 2-5; nothing hits. Exit at MON2's open.
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    quiet = ("10", "10.50", "9.50", "10.20")
    p = step(p, D(MON), day(bar("AAA", MON, "10", "10.5", "9.9", "10.2"))).portfolio
    for s in (TUE, WED, THU, FRI):
        r = step(p, D(s), day(bar("AAA", s, *quiet)))
        assert r.events == ()
        p = r.portfolio
    assert p.orders[0].days_held == 5
    r = step(p, D(MON2), day(bar("AAA", MON2, "10.30", "10.90", "10.10", "10.60")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.exit_date, o.days_held) == ("time", Decimal("10.3000"), D(MON2), 5)
    # cost = 100.1000; proceeds = 103 × 0.999 = 102.8970; pnl = 2.7970
    assert o.pnl_usd == Decimal("2.7970")
    assert r.portfolio.cash == Decimal("1002.7970")


def test_time_stop_across_thanksgiving_and_the_half_day():
    # 2026-11-26 (Thu) is a holiday, 2026-11-27 (Fri) a half day.
    assert not dates.is_session(D("2026-11-26"))
    assert dates.is_session(D("2026-11-27"))
    with pytest.raises(ValueError):
        step(new_portfolio(Decimal("1000")), D("2026-11-26"), {})
    # Fill Tue 11-24 = day 1, Wed 11-25 = day 2, (Thu holiday: no day), Fri 11-27 half
    # day = day 3, Mon 11-30 = day 4, Tue 12-01 = day 5 -> exit at Wed 12-02's open.
    p = portfolio("1000", pending("AAA", "2026-11-24", "10", "11", "9", 10))
    p = step(p, D("2026-11-24"), day(bar("AAA", "2026-11-24", "10", "10.5", "9.9", "10.2"))).portfolio
    expected = {"2026-11-25": 2, "2026-11-27": 3, "2026-11-30": 4, "2026-12-01": 5}
    for s in dates.sessions(D("2026-11-25"), D("2026-12-01")):
        r = step(p, s, day(bar("AAA", s, "10", "10.50", "9.50", "10.20")))
        assert r.events == ()
        p = r.portfolio
        assert p.orders[0].days_held == expected[s.isoformat()]
    assert [s.isoformat() for s in dates.sessions(D("2026-11-25"), D("2026-12-01"))] == list(expected)
    r = step(p, D("2026-12-02"), day(bar("AAA", "2026-12-02", "9.70", "10.10", "9.60", "9.90")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.exit_date, o.days_held) == (
        "time",
        Decimal("9.7000"),
        D("2026-12-02"),
        5,
    )
    # proceeds = 97 × 0.999 = 96.9030; pnl = 96.9030 − 100.1000 = −3.1970
    assert o.pnl_usd == Decimal("-3.1970")


def test_time_stop_comes_before_gap_and_tp_checks():
    # Day 6's open is below SL and its high above TP: still a time exit at the open.
    p = _held(days_held=5)
    r = step(p, D(TUE), day(bar("AAA", TUE, "8.80", "11.50", "8.50", "11.20")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.days_held) == ("time", Decimal("8.8000"), 5)


def test_day_5_still_checks_tp_and_sl_intraday():
    r = step(_held(days_held=4), D(TUE), day(bar("AAA", TUE, "10", "10.20", "8.90", "9.10")))
    o = _only(r.events).order
    assert (o.exit_reason, o.days_held) == ("sl", 5)


# ============================================================== missing bars


def test_missing_bar_for_a_held_symbol_counts_the_day_and_keeps_the_mark():
    p = portfolio(
        "899.9",
        opened("AAA", MON, "10", "11", "9", 10, days_held=1),
        marks={"AAA": "10.40"},
        last_session=MON,
    )
    r = step(p, D(TUE), day(bar("BBB", TUE, "5", "5", "5", "5")))
    assert r.events == ()
    (o,) = r.portfolio.orders
    assert o.days_held == 2
    assert r.portfolio.mark("AAA") == Decimal("10.4000")
    # equity = 899.9000 + 10 × 10.40 (last known close) = 1003.9000
    assert r.snapshot == Snapshot(D(TUE), Decimal("899.9000"), Decimal("1003.9000"))


def test_due_time_stop_waits_for_the_next_bar():
    p = _held(days_held=5)
    r = step(p, D(TUE), {})  # no bar on day 6: nothing happens, the day still counts
    assert r.events == ()
    assert r.portfolio.orders[0].days_held == 6
    r = step(r.portfolio, D(WED), day(bar("AAA", WED, "10.10", "10.20", "9.90", "10")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.exit_date, o.days_held) == ("time", Decimal("10.1000"), D(WED), 6)


# ============================================================== slots, ordering, purity


def test_slot_is_freed_after_an_exit():
    p = portfolio(
        "500",
        opened("AAA", MON, "10", "11", "9", 10, days_held=1, slot=1),
        opened("BBB", MON, "20", "22", "18", 5, days_held=1, slot=3),
        last_session=MON,
    )
    r = step(
        p,
        D(TUE),
        day(
            bar("AAA", TUE, "10", "11.50", "9.80", "11"),  # TP
            bar("BBB", TUE, "20", "20.50", "19.50", "20.10"),  # holds
        ),
    )
    assert [e.order.symbol for e in r.events] == ["AAA"]
    assert r.portfolio.free_slots() == (1, 2, 4)
    assert r.portfolio.held_symbols() == ("BBB",)


def test_events_are_exits_then_fills_then_expiries_in_slot_order():
    p = portfolio(
        "2000",
        pending("EEE", TUE, "10", "11", "9", 1, slot=1),  # expires
        pending("FFF", TUE, "10", "11", "9", 1, slot=2),  # fills
        opened("XXX", MON, "10", "11", "9", 1, days_held=1, slot=3),  # exits (SL)
        opened("YYY", MON, "10", "11", "9", 1, days_held=1, slot=4),  # exits (TP)
        last_session=MON,
    )
    bars = day(
        bar("YYY", TUE, "10", "11.5", "9.8", "11"),
        bar("FFF", TUE, "10", "10.2", "9.5", "10"),
        bar("XXX", TUE, "10", "10.2", "8.5", "9"),
        bar("EEE", TUE, "10.5", "10.8", "10.1", "10.6"),
    )
    r = step(p, D(TUE), bars)
    assert [(e.kind, e.order.symbol) for e in r.events] == [
        ("exit", "XXX"),
        ("exit", "YYY"),
        ("fill", "FFF"),
        ("expire", "EEE"),
    ]
    assert [o.symbol for o in r.portfolio.orders] == ["FFF"]
    # Same inputs, same outputs, independent of the mapping's insertion order.
    again = step(p, D(TUE), dict(reversed(list(bars.items()))))
    assert again == r


def test_snapshot_marks_every_open_position_at_the_close():
    p = portfolio(
        "1000",
        pending("NEW", TUE, "50", "55", "45", 2, slot=2),
        opened("OLD", MON, "10", "11", "9", 10, days_held=1, slot=1),
        last_session=MON,
    )
    r = step(
        p,
        D(TUE),
        day(bar("OLD", TUE, "10.1", "10.6", "9.6", "10.5"), bar("NEW", TUE, "49", "51", "48", "50.5")),
    )
    # NEW fills at open 49: cost = 98 × 1.001 = 98.0980 -> cash 901.9020
    # equity = 901.9020 + 10 × 10.50 + 2 × 50.50 = 901.9020 + 105 + 101 = 1107.9020
    assert r.snapshot == Snapshot(D(TUE), Decimal("901.9020"), Decimal("1107.9020"))
    assert r.portfolio.marks == (("NEW", Decimal("50.5000")), ("OLD", Decimal("10.5000")))


def test_empty_portfolio_still_snapshots():
    r = step(new_portfolio(Decimal("1230.7692")), D(MON), {})
    assert r.events == ()
    assert r.snapshot == Snapshot(D(MON), Decimal("1230.7692"), Decimal("1230.7692"))
    assert r.portfolio.last_session == D(MON)


def test_step_does_not_change_its_input():
    p = _held()
    before = repr(p)
    step(p, D(TUE), day(bar("AAA", TUE, "10.50", "11.50", "10.20", "11")))
    assert repr(p) == before


def test_bars_for_unrelated_symbols_are_ignored():
    # A bad bar for a symbol nobody holds is never read.
    r = step(_held(), D(TUE), {"AAA": bar("AAA", TUE, "10", "10.5", "9.5", "10"), "JUNK": object()})
    assert r.events == ()


# ============================================================== validation


def test_step_rejects_a_non_session():
    with pytest.raises(ValueError):
        step(new_portfolio(Decimal("1000")), D("2026-10-03"), {})  # Saturday


def test_step_rejects_a_session_not_after_the_last():
    p = _held()
    with pytest.raises(ValueError):
        step(p, D(MON), {})
    with pytest.raises(ValueError):
        step(p, D("2026-10-02"), {})


def test_step_rejects_a_pending_order_for_another_session():
    p = portfolio("1000", pending("AAA", WED, "10", "11", "9", 10))
    with pytest.raises(ValueError):
        step(p, D(TUE), {})


def test_step_rejects_a_datetime():
    with pytest.raises(TypeError):
        step(new_portfolio(Decimal("1000")), datetime(2026, 10, 5, 14, 30), {})


def test_step_rejects_float_bar_prices():
    bad = Bar("AAA", D(TUE), 10.0, Decimal("10.5"), Decimal("9.5"), Decimal("10"), 1)
    with pytest.raises(TypeError):
        step(_held(), D(TUE), {"AAA": bad})


@pytest.mark.parametrize(
    "bars",
    [
        {"AAA": bar("BBB", TUE, "10", "10.5", "9.5", "10")},  # keyed under the wrong symbol
        {"AAA": bar("AAA", WED, "10", "10.5", "9.5", "10")},  # wrong date
    ],
)
def test_step_rejects_mismatched_bars(bars):
    with pytest.raises(ValueError):
        step(_held(), D(TUE), bars)


# ============================================================== close_unpriced


def test_close_unpriced_exits_at_the_last_known_close():
    p = portfolio(
        "500",
        opened("AAA", MON, "10", "11", "9", 10, days_held=3, slot=2),
        opened("BBB", MON, "20", "22", "18", 5, days_held=3, slot=1),
        marks={"AAA": "9.50", "BBB": "21"},
        last_session=THU,
    )
    p2, events = close_unpriced(p, ["AAA"])
    ev = _only(events)
    o = ev.order
    assert ev.kind == "exit" and ev.forced and ev.session_date == D(THU)
    assert (o.status, o.exit_reason, o.exit_price, o.exit_date, o.days_held) == (
        "closed",
        "time",
        Decimal("9.5000"),
        D(THU),
        3,
    )
    # proceeds = 95 × 0.999 = 94.9050; pnl = 94.9050 − 100.1000 = −5.1950
    assert ev.cash_usd == Decimal("94.9050")
    assert o.pnl_usd == Decimal("-5.1950")
    assert p2.cash == Decimal("594.9050")
    # equity = 594.9050 + 5 × 21 = 699.9050
    assert p2.equity == Decimal("699.9050")
    assert p2.marks == (("BBB", Decimal("21.0000")),)
    assert p2.free_slots() == (2, 3, 4)
    assert p2.last_session == D(THU)


def test_close_unpriced_events_are_in_slot_order():
    p = portfolio(
        "0",
        opened("AAA", MON, "10", "11", "9", 1, days_held=2, slot=4),
        opened("BBB", MON, "10", "11", "9", 1, days_held=2, slot=2),
        last_session=TUE,
    )
    p2, events = close_unpriced(p, ("AAA", "BBB", "AAA"))
    assert [e.order.symbol for e in events] == ["BBB", "AAA"]
    assert p2.orders == ()


def test_close_unpriced_with_nothing_to_close_is_a_no_op():
    p = _held()
    assert close_unpriced(p, []) == (p, ())


@pytest.mark.parametrize(
    ("symbols", "exc"),
    [
        ("AAA", TypeError),  # a bare str
        (["ZZZ"], ValueError),  # not held
        (["PND"], ValueError),  # pending, not open
    ],
)
def test_close_unpriced_rejects_bad_symbols(symbols, exc):
    p = portfolio(
        "899.9",
        opened("AAA", MON, "10", "11", "9", 10, days_held=1, slot=1),
        pending("PND", TUE, "10", "11", "9", 10, slot=2),
        last_session=MON,
    )
    with pytest.raises(exc):
        close_unpriced(p, symbols)


def test_close_unpriced_needs_a_stepped_session():
    p = portfolio("899.9", opened("AAA", MON, "10", "11", "9", 10, days_held=1))
    with pytest.raises(ValueError):
        close_unpriced(p, ["AAA"])
