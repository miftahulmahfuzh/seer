"""apply_split: live orders rewritten in post-split units (design §8, plan Decisions).

Every expected number below is worked by hand in the comment next to it. Sessions: Mon 2026-10-05
is the last stepped session, Tue 2026-10-06 is the split's execution session.
"""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from seer_engine.prices import Bar
from seer_engine.sim.lifecycle import step
from seer_engine.sim.charges import buy_cash
from seer_engine.sim.model import Event, Order, Portfolio
from seer_engine.sim.rules import DESIGN_V0_GOTRADE
from seer_engine.sim.split_adjust import apply_split
from seer_engine.splits import Split
from simkit import D, P

MON = D("2026-10-05")
TUE = D("2026-10-06")
SAT = D("2026-10-10")

TEN_FOR_ONE = Decimal(10)
THREE_FOR_TWO = Decimal(3) / Decimal(2)  # 1.5
ONE_FOR_32 = Decimal(1) / Decimal(32)  # 0.03125, exact
ONE_FOR_3 = Split("ABC", TUE, split_from=Decimal(3), split_to=Decimal(1)).factor  # 0.3333…3 (28 digits)


def _open(symbol, *, slot, last, limit, fill, tp, sl, shares, days_held=1):
    return Order(
        session_date=MON,
        slot=slot,
        symbol=symbol,
        last_price=P(last),
        limit_price=P(limit),
        tp_price=P(tp),
        sl_price=P(sl),
        shares=shares,
        status="open",
        fill_date=MON,
        fill_price=P(fill),
        days_held=days_held,
    )


def _pending(symbol, *, slot, last, limit, tp, sl, shares):
    return Order(
        session_date=TUE,
        slot=slot,
        symbol=symbol,
        last_price=P(last),
        limit_price=P(limit),
        tp_price=P(tp),
        sl_price=P(sl),
        shares=shares,
    )


def _pf(cash, *orders, marks=(), equity=None, last_session=MON):
    return Portfolio(
        cash=P(cash),
        equity=P(equity if equity is not None else cash),
        orders=tuple(sorted(orders, key=lambda o: o.slot)),
        marks=tuple(sorted((s, P(m)) for s, m in marks)),
        last_session=last_session,
    )


def _bar(symbol, d, o, h, l, c):  # noqa: E741
    return Bar(symbol, d, P(o), P(h), P(l), P(c), 1_000_000)


# ---- forward splits ----

def test_forward_10_for_1_on_open_position():
    abc = _open("ABC", slot=2, last="125", limit="121.0005", fill="120", tp="132", sl="114", shares=3)
    pf = _pf("640", abc, marks=[("ABC", "125.5")], equity="1016.5")

    out, events = apply_split(pf, "ABC", TEN_FOR_ONE, TUE)

    adjusted = replace(
        abc,
        shares=30,  # 3 x 10
        last_price=P("12.5"),  # 125 / 10
        limit_price=P("12.1001"),  # 121.0005 / 10 = 12.10005 -> half-up 12.1001
        fill_price=P("12"),  # 120 / 10
        tp_price=P("13.2"),  # 132 / 10
        sl_price=P("11.4"),  # 114 / 10
    )
    assert out.orders == (adjusted,)
    assert out.marks == (("ABC", P("12.55")),)  # 125.5 / 10
    assert out.cash == P("640")  # 30 is whole: no cash in lieu
    assert out.equity == P("1016.5")  # untouched
    assert out.last_session == MON  # untouched
    assert events == (
        Event(session_date=TUE, kind="split", order=adjusted, cash_usd=Decimal("0.0000")),
    )
    # fill date, days held and status survive the split
    assert (adjusted.status, adjusted.fill_date, adjusted.days_held) == ("open", MON, 1)


def test_forward_3_for_2_on_open_position_pays_cash_in_lieu():
    abc = _open("ABC", slot=1, last="102", limit="101", fill="100", tp="110", sl="95", shares=5)
    pf = _pf("500", abc, marks=[("ABC", "104")])

    out, events = apply_split(pf, "ABC", THREE_FOR_TWO, TUE)

    adjusted = replace(
        abc,
        shares=7,  # 5 x 1.5 = 7.5 -> floor 7, remainder 0.5 share
        last_price=P("68"),  # 102 x 2/3
        limit_price=P("67.3333"),  # 101 x 2/3 = 67.3333…
        fill_price=P("66.6667"),  # 100 x 2/3 = 66.6666… -> 66.6667
        tp_price=P("73.3333"),  # 110 x 2/3
        sl_price=P("63.3333"),  # 95 x 2/3
    )
    assert out.orders == (adjusted,)
    assert out.marks == (("ABC", P("69.3333")),)  # 104 x 2/3
    # cash in lieu = q(0.5 x 69.3333) = q(34.66665) = 34.6667, no cost
    assert events == (
        Event(session_date=TUE, kind="split", order=adjusted, cash_usd=P("34.6667")),
    )
    assert out.cash == P("534.6667")  # 500 + 34.6667


def test_forward_3_for_2_on_pending_order():
    xyz = _pending("XYZ", slot=3, last="51", limit="50", tp="55", sl="47.5", shares=5)
    pf = _pf("1000", xyz)

    out, events = apply_split(pf, "XYZ", THREE_FOR_TWO, TUE)

    adjusted = replace(
        xyz,
        shares=7,  # 5 x 1.5 = 7.5 -> 7; a pending order holds nothing, so no cash in lieu
        last_price=P("34"),  # 51 x 2/3
        limit_price=P("33.3333"),  # 50 x 2/3
        tp_price=P("36.6667"),  # 55 x 2/3 = 36.6666…
        sl_price=P("31.6667"),  # 47.5 x 2/3 = 31.6666…
    )
    assert out.orders == (adjusted,)
    assert adjusted.status == "pending" and adjusted.fill_price is None
    assert events == (Event(session_date=TUE, kind="split", order=adjusted),)
    assert events[0].cash_usd is None
    assert out.cash == P("1000")
    assert out.marks == ()  # a pending order has no mark, and none is invented


# ---- reverse splits ----

def test_reverse_1_for_32_on_open_position_with_remainder():
    abc = _open("ABC", slot=1, last="0.52", limit="0.51", fill="0.5", tp="0.55", sl="0.475", shares=70)
    pf = _pf("100", abc, marks=[("ABC", "0.53")])

    out, events = apply_split(pf, "ABC", ONE_FOR_32, TUE)

    adjusted = replace(
        abc,
        shares=2,  # 70 / 32 = 2.1875 -> 2, remainder 0.1875 share
        last_price=P("16.64"),  # 0.52 x 32
        limit_price=P("16.32"),  # 0.51 x 32
        fill_price=P("16"),  # 0.50 x 32
        tp_price=P("17.6"),  # 0.55 x 32
        sl_price=P("15.2"),  # 0.475 x 32
    )
    assert out.orders == (adjusted,)
    assert out.marks == (("ABC", P("16.96")),)  # 0.53 x 32
    # cash in lieu = q(0.1875 x 16.96) = 3.18
    assert events == (Event(session_date=TUE, kind="split", order=adjusted, cash_usd=P("3.18")),)
    assert out.cash == P("103.18")


def test_reverse_1_for_3_with_split_factor_on_open_and_pending():
    # ONE_FOR_3 is Split.factor, the 28-digit Decimal 0.333…; naive Decimal math floors 300 x it to 99
    assert int(Decimal(300) * ONE_FOR_3) == 99
    abc = _open("ABC", slot=1, last="3.1", limit="3.05", fill="3", tp="3.3", sl="2.8", shares=10)
    xyz = _pending("XYZ", slot=2, last="2", limit="1.9", tp="2.1", sl="1.8", shares=300)
    pf = _pf("969.97", abc, xyz, marks=[("ABC", "3.1")])

    out, events = apply_split(pf, "ABC", ONE_FOR_3, TUE)
    adjusted = replace(
        abc,
        shares=3,  # 10 / 3 = 3.333… -> 3, remainder 1/3 share
        last_price=P("9.3"),
        limit_price=P("9.15"),
        fill_price=P("9"),
        tp_price=P("9.9"),
        sl_price=P("8.4"),
    )
    assert out.orders == (adjusted, xyz)
    assert out.marks == (("ABC", P("9.3")),)
    # cash in lieu = q(1/3 x 9.3) = 3.1 (exactly the one pre-split share at its 3.10 close)
    assert events == (Event(session_date=TUE, kind="split", order=adjusted, cash_usd=P("3.1")),)
    assert out.cash == P("973.07")

    # the same factor on the 300-share pending order gives exactly 100, not 99
    out2, events2 = apply_split(pf, "XYZ", ONE_FOR_3, TUE)
    assert out2.orders[1].shares == 100
    assert out2.orders[1].limit_price == P("5.7")  # 1.9 x 3
    assert events2[0].kind == "split" and events2[0].cash_usd is None


def test_reverse_1_for_3_on_pending_order_floors_without_cash():
    xyz = _pending("XYZ", slot=1, last="2", limit="1.9", tp="2.1", sl="1.8", shares=10)
    out, events = apply_split(_pf("1000", xyz), "XYZ", ONE_FOR_3, TUE)
    assert out.orders[0].shares == 3  # 10 / 3 -> 3; the remainder is simply not ordered
    assert out.cash == P("1000")
    assert events[0].cash_usd is None


def test_reverse_split_flooring_pending_order_to_zero_expires_it():
    xyz = _pending("XYZ", slot=2, last="0.52", limit="0.5", tp="0.55", sl="0.475", shares=20)
    def_ = _open("DEF", slot=4, last="40", limit="40", fill="39.5", tp="44", sl="37", shares=7)
    pf = _pf("200", xyz, def_, marks=[("DEF", "40.25")])

    out, events = apply_split(pf, "XYZ", ONE_FOR_32, TUE)  # 20 / 32 = 0.625 -> 0

    assert events == (
        Event(session_date=TUE, kind="expire", order=replace(xyz, status="expired")),
    )
    assert out.orders == (def_,)
    assert 2 in out.free_slots()
    assert out.cash == P("200")
    assert out.marks == (("DEF", P("40.25")),)


def test_reverse_split_flooring_open_position_to_zero_pays_it_all_in_lieu():
    abc = _open("ABC", slot=3, last="0.52", limit="0.51", fill="0.5", tp="0.55", sl="0.475", shares=20)
    pf = _pf("100", abc, marks=[("ABC", "0.53")])

    out, events = apply_split(pf, "ABC", ONE_FOR_32, TUE)

    # 20 / 32 = 0.625 share -> 0 whole; in lieu = q(0.625 x 16.96) = 10.6
    # pnl_usd = 10.6 - buy_cost(0.50, 20) = 10.6 - q(10 x 1.001) = 10.6 - 10.01 = 0.59
    closed = replace(
        abc,
        status="closed",
        exit_date=TUE,
        exit_price=P("0.53"),
        exit_reason="time",
        pnl_usd=P("0.59"),
    )
    assert events == (
        Event(session_date=TUE, kind="exit", order=closed, forced=True, cash_usd=P("10.6")),
    )
    assert out.orders == ()
    assert out.marks == ()
    assert out.cash == P("110.6")


# ---- scope: only the split symbol moves ----

def test_unaffected_symbols_and_order_are_untouched():
    abc = _open("ABC", slot=1, last="125", limit="121", fill="120", tp="132", sl="114", shares=3)
    xyz = _pending("XYZ", slot=2, last="51", limit="50", tp="55", sl="47.5", shares=5)
    def_ = _open("DEF", slot=3, last="40", limit="40", fill="39.5", tp="44", sl="37", shares=7)
    pf = _pf("100", abc, xyz, def_, marks=[("ABC", "125.5"), ("DEF", "40.25")])

    out, events = apply_split(pf, "ABC", TEN_FOR_ONE, TUE)

    assert [o.slot for o in out.orders] == [1, 2, 3]
    assert out.orders[1] is xyz
    assert out.orders[2] is def_
    assert out.marks == (("ABC", P("12.55")), ("DEF", P("40.25")))
    assert [e.order.symbol for e in events] == ["ABC"]


def test_symbol_not_held_returns_the_same_portfolio():
    def_ = _open("DEF", slot=1, last="40", limit="40", fill="39.5", tp="44", sl="37", shares=7)
    pf = _pf("100", def_, marks=[("DEF", "40.25")])
    out, events = apply_split(pf, "NVDA", TEN_FOR_ONE, TUE)
    assert out is pf
    assert events == ()


def test_apply_split_is_deterministic_and_leaves_input_alone():
    abc = _open("ABC", slot=1, last="102", limit="101", fill="100", tp="110", sl="95", shares=5)
    pf = _pf("500", abc, marks=[("ABC", "104")])
    before = replace(pf)
    assert apply_split(pf, "ABC", THREE_FOR_TWO, TUE) == apply_split(pf, "ABC", THREE_FOR_TWO, TUE)
    assert pf == before


# ---- validation ----

@pytest.mark.parametrize("factor", [10, 1.5, "10", True, None])
def test_non_decimal_factor_is_a_type_error(factor):
    with pytest.raises(TypeError):
        apply_split(_pf("100"), "ABC", factor, TUE)


@pytest.mark.parametrize(
    "factor",
    [
        Decimal(0),
        Decimal(-2),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal(1),
        Decimal("1.0000"),
        Decimal("1.00000000001"),  # not a ratio of small integers
    ],
)
def test_bad_factor_is_a_value_error(factor):
    with pytest.raises(ValueError):
        apply_split(_pf("100"), "ABC", factor, TUE)


def test_split_that_leaves_prices_unrepresentable_at_4dp_is_a_value_error():
    # 10-for-1 on a sub-cent bracket: sl 0.0009 -> 0.00009 -> 0.0001 and tp 0.0011 -> 0.00011
    # -> 0.0001, so sl == tp. Order validation would reject it; apply_split says why, up front.
    xyz = _pending("XYZ", slot=1, last="0.001", limit="0.001", tp="0.0011", sl="0.0009", shares=1000)
    pf = _pf("100", xyz)
    with pytest.raises(ValueError, match="4 dp"):
        apply_split(pf, "XYZ", TEN_FOR_ONE, TUE)
    # An open position whose mark rounds to 0: 0.0004 / 10 = 0.00004 -> 0.0000.
    abc = _open("ABC", slot=1, last="0.0004", limit="0.0004", fill="0.0004", tp="0.0005", sl="0.0003", shares=1000)
    pf2 = _pf("100", abc, marks=[("ABC", "0.0004")])
    before = replace(pf2)
    with pytest.raises(ValueError, match="4 dp"):
        apply_split(pf2, "ABC", TEN_FOR_ONE, TUE)
    assert pf2 == before  # nothing was half-applied


def test_session_must_follow_last_session():
    with pytest.raises(ValueError):
        apply_split(_pf("100", last_session=TUE), "ABC", TEN_FOR_ONE, TUE)
    with pytest.raises(ValueError):
        apply_split(_pf("100", last_session=TUE), "ABC", TEN_FOR_ONE, MON)


def test_session_must_be_an_nyse_session():
    with pytest.raises(ValueError):
        apply_split(_pf("100"), "ABC", TEN_FOR_ONE, SAT)


def test_session_date_must_be_a_date():
    with pytest.raises(TypeError):
        apply_split(_pf("100"), "ABC", TEN_FOR_ONE, datetime(2026, 10, 6, 9, 30))


def test_no_last_session_accepts_any_session():
    out, events = apply_split(_pf("100", last_session=None), "ABC", TEN_FOR_ONE, TUE)
    assert events == ()


@pytest.mark.parametrize("symbol, exc", [("", ValueError), (None, TypeError), (7, TypeError)])
def test_bad_symbol(symbol, exc):
    with pytest.raises(exc):
        apply_split(_pf("100"), symbol, TEN_FOR_ONE, TUE)


def test_bad_portfolio_is_a_type_error():
    with pytest.raises(TypeError):
        apply_split(None, "ABC", TEN_FOR_ONE, TUE)


# ---- end to end: split, then step on adjusted bars ----

def test_10_for_1_then_step_gives_the_same_trade_as_no_split():
    # Filled Mon: 2 x 120.00, buy_cost = q(240 x 1.001) = 240.24; cash 1000 - 240.24 = 759.76
    abc = _open("ABC", slot=1, last="121", limit="121", fill="120", tp="132", sl="114", shares=2)
    pf = _pf("759.76", abc, marks=[("ABC", "125")], equity="1009.76")

    # No split: Tue bar o 126 h 133 l 121 c 130. No gap; low 121 > SL 114; high 133 > TP 132 -> TP at 132.
    # proceeds = q(264 x 0.999) = 263.736; pnl = 263.736 - 240.24 = 23.496; cash 1023.496
    plain = step(pf, TUE, {"ABC": _bar("ABC", TUE, "126", "133", "121", "130")})

    # Split 10:1 executes Tue; the same session in post-split units: o 12.6 h 13.3 l 12.1 c 13.0.
    # 20 x 12.00 (buy_cost(12, 20) = 240.24); high 13.3 > TP 13.2 -> exit 20 x 13.2:
    # proceeds q(264 x 0.999) = 263.736; pnl 23.496
    split_pf, split_events = apply_split(pf, "ABC", TEN_FOR_ONE, TUE)
    assert split_events[0].cash_usd == Decimal("0.0000")
    split = step(split_pf, TUE, {"ABC": _bar("ABC", TUE, "12.6", "13.3", "12.1", "13")})

    (plain_exit,) = plain.events
    (split_exit,) = split.events
    assert plain_exit.kind == split_exit.kind == "exit"
    assert plain_exit.order.exit_reason == split_exit.order.exit_reason == "tp"
    assert plain_exit.order.exit_price == P("132")
    assert split_exit.order.exit_price == P("13.2")
    assert split_exit.order.shares == 20
    assert plain_exit.order.pnl_usd == split_exit.order.pnl_usd == P("23.496")
    assert plain.portfolio.cash == split.portfolio.cash == P("1023.496")
    assert plain.snapshot.equity_usd == split.snapshot.equity_usd == P("1023.496")


def test_1_for_3_then_step_reconciles_cash_with_pnl_and_cash_in_lieu():
    # Filled Mon: 10 x 3.00, buy_cost = q(30 x 1.001) = 30.03; cash 1000 - 30.03 = 969.97
    abc = _open("ABC", slot=1, last="3.1", limit="3.05", fill="3", tp="3.3", sl="2.8", shares=10)
    pf = _pf("969.97", abc, marks=[("ABC", "3.1")], equity="1000.97")

    # 1-for-3 on Tue: 3 shares at fill 9.00, TP 9.90, SL 8.40; 1/3 share paid as q(9.3 / 3) = 3.10
    split_pf, split_events = apply_split(pf, "ABC", ONE_FOR_3, TUE)
    assert split_events[0].cash_usd == P("3.1")
    assert split_pf.cash == P("973.07")

    # Tue bar (post-split units) o 9.2 h 9.95 l 9.0 c 9.8: no gap, low 9.0 > SL 8.4, high 9.95 > TP 9.9
    # exit 3 x 9.90: proceeds = q(29.7 x 0.999) = 29.6703; pnl = 29.6703 - buy_cost(9, 3) = 29.6703 - 27.027 = 2.6433
    result = step(split_pf, TUE, {"ABC": _bar("ABC", TUE, "9.2", "9.95", "9", "9.8")})
    (exit_,) = result.events
    assert exit_.order.exit_reason == "tp"
    assert exit_.order.exit_price == P("9.9")
    assert exit_.order.pnl_usd == P("2.6433")
    assert result.portfolio.cash == P("1002.7403")  # 973.07 + 29.6703

    # Economic P/L over the trade = final cash - starting cash = 2.7403. It splits exactly into
    # pnl_usd (3 post-split shares) + cash in lieu - the cost basis of the share paid in lieu,
    # which is buy_cost(3.00, 10) - buy_cost(9.00, 3) = 30.03 - 27.027 = 3.003.
    economic = result.portfolio.cash - P("1000")
    basis_in_lieu = P("30.03") - P("27.027")
    assert economic == P("2.7403")
    assert economic == exit_.order.pnl_usd + split_events[0].cash_usd - basis_in_lieu


def test_pending_order_adjusted_by_split_fills_at_the_adjusted_limit():
    xyz = _pending("XYZ", slot=1, last="51", limit="50", tp="55", sl="47.5", shares=5)
    split_pf, _ = apply_split(_pf("1000", xyz), "XYZ", THREE_FOR_TWO, TUE)

    # Tue bar o 34 h 35 l 33 c 34.5: low 33 < limit 33.3333 and open 34 >= limit -> fill at limit
    # buy_cost = q(33.3333 x 7 x 1.001) = q(233.5664331) = 233.5664
    result = step(split_pf, TUE, {"XYZ": _bar("XYZ", TUE, "34", "35", "33", "34.5")})
    (fill,) = result.events
    assert fill.kind == "fill"
    assert fill.order.fill_price == P("33.3333")
    assert fill.order.shares == 7
    assert result.portfolio.cash == P("766.4336")  # 1000 - 233.5664


# ---- the cost model lever (phase 4) ----


def test_a_liquidating_reverse_split_reconciles_pnl_against_the_rule_sets_buy_cash():
    """Cash in lieu is identical under both models (a split pays no brokerage); only the pnl's
    cost basis moves, because Gotrade charged more than 0.1% at the fill."""
    abc = _open("ABC", slot=3, last="0.52", limit="0.51", fill="0.5", tp="0.55", sl="0.475", shares=20)
    pf = _pf("100", abc, marks=[("ABC", "0.53")])

    flat_out, flat_events = apply_split(pf, "ABC", ONE_FOR_32, TUE)
    gt_out, gt_events = apply_split(pf, "ABC", ONE_FOR_32, TUE, rules=DESIGN_V0_GOTRADE)

    (flat_ev,) = flat_events
    (gt_ev,) = gt_events
    in_lieu = P("10.6")
    # The split pays no brokerage: the cash in lieu, and so the cash, is the same either way.
    assert flat_ev.cash_usd == gt_ev.cash_usd == in_lieu
    assert flat_out.cash == gt_out.cash == P("110.6")
    # Only the cost basis differs: a $10 order pays $0.12 at Gotrade (plan fee table) against
    # the flat model's $0.01.
    assert gt_ev.order.pnl_usd == in_lieu - buy_cash(P("0.5"), 20, DESIGN_V0_GOTRADE)
    assert buy_cash(P("0.5"), 20, DESIGN_V0_GOTRADE) == P("10.12")
    assert flat_ev.order.pnl_usd == P("0.59")  # 10.6 - 10.01, unchanged
    assert gt_ev.order.pnl_usd == P("0.48")  # 10.6 - 10.12
    assert gt_ev.order.pnl_usd < flat_ev.order.pnl_usd
