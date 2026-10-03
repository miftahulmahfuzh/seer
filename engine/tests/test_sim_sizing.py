"""Whole-share sizing of picks into slots (design §5, handover §3 sizing row). No database."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from simkit import D, P, bar, opened, pending, portfolio

from seer_engine.sim.lifecycle import step
from seer_engine.sim.model import buy_cost, new_portfolio, sell_proceeds
from seer_engine.sim.sizing import Pick, Rejection, size_picks

PREV = D("2026-10-02")  # Friday, last stepped session (data_date)
SESSION = D("2026-10-05")  # Monday, the session the picks are placed for
NEXT = D("2026-10-06")


def pick(symbol: str, limit: str, tp: str | None = None, sl: str | None = None) -> Pick:
    lim = P(limit)
    return Pick(
        symbol=symbol,
        last_price=lim,
        limit_price=lim,
        tp_price=P(tp) if tp is not None else lim * Decimal("1.1"),
        sl_price=P(sl) if sl is not None else lim * Decimal("0.9"),
    )


def flat(cash: str = "10000") -> object:
    """A portfolio with no live orders, equity == cash, last stepped on PREV."""
    return portfolio(P(cash), equity=P(cash), last_session=PREV)


# --- zero picks -------------------------------------------------------------------------------


def test_zero_picks_returns_portfolio_unchanged() -> None:
    pf = flat()
    res = size_picks(pf, [], SESSION)
    assert res.portfolio is pf
    assert res.placed == ()
    assert res.rejected == ()


def test_zero_picks_on_full_portfolio_is_fine() -> None:
    pf = portfolio(
        P("1000"),
        opened("AAA", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=1),
        opened("BBB", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=2),
        opened("CCC", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=3),
        opened("DDD", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=4),
        equity=P("1400"),
        last_session=PREV,
    )
    assert size_picks(pf, (), SESSION).portfolio is pf


# --- whole shares, equity ÷ 4 ---------------------------------------------------------------


def test_whole_shares_floor_of_equity_quarter_over_limit_with_cost() -> None:
    pf = flat("10000")
    res = size_picks(pf, [pick("AAA", "33", tp="36", sl="31")], SESSION)
    # slot budget = 10000 / 4 = 2500; 2500 / (33 × 1.001) = 2500 / 33.033 = 75.68 → 75 (floor, not 76)
    (o,) = res.placed
    assert o.symbol == "AAA"
    assert o.shares == 75
    assert o.slot == 1
    assert o.session_date == SESSION
    assert o.status == "pending"
    assert (o.limit_price, o.tp_price, o.sl_price, o.last_price) == (P("33"), P("36"), P("31"), P("33"))
    assert o.fill_date is None and o.days_held == 0
    # The buy cost fits the budget: 75 × 33 × 1.001 = 2477.4750 <= 2500.
    assert buy_cost(o.limit_price, o.shares) == P("2477.4750")
    assert res.rejected == ()
    # Sizing reserves nothing in cash or equity; it only adds the pending order.
    assert res.portfolio.cash == P("10000")
    assert res.portfolio.equity == P("10000")
    assert res.portfolio.last_session == PREV
    assert res.portfolio.marks == pf.marks
    assert res.portfolio.orders == (o,)


def test_cost_buffer_drops_a_share() -> None:
    # equity 4000 → slot 1000. Without the 0.1 % buffer 1000 / 10 = 100 shares would cost 1001.00.
    # With it: 1000 / 10.01 = 99.90 → 99; 99 × 10 × 1.001 = 990.9900.
    res = size_picks(flat("4000"), [pick("AAA", "10")], SESSION)
    assert res.placed[0].shares == 99
    assert buy_cost(P("10"), 99) == P("990.9900")


def test_fresh_portfolio_without_last_session() -> None:
    pf = new_portfolio(P("8000"))
    res = size_picks(pf, [pick("AAA", "10")], SESSION)
    # 8000 / 4 = 2000; 2000 / 10.01 = 199.80 → 199
    assert res.placed[0].shares == 199
    assert res.placed[0].slot == 1


# --- slots ------------------------------------------------------------------------------------


def test_picks_take_lowest_free_slots_in_pick_order_then_no_slot() -> None:
    picks = [pick("AAA", "10"), pick("BBB", "20"), pick("CCC", "50"), pick("DDD", "100"), pick("EEE", "5")]
    res = size_picks(flat("10000"), picks, SESSION)
    # Slot budget 2500 each, and cash never binds:
    #   AAA 2500 / 10.01  = 249.75 → 249, cost 2492.49, committed 2492.49
    #   BBB 2500 / 20.02  = 124.88 → 124, cost 2482.48, committed 4974.97
    #   CCC 2500 / 50.05  =  49.95 →  49, cost 2452.45, committed 7427.42 (cash left 2572.58 > 2500)
    #   DDD 2500 / 100.10 =  24.98 →  24, cost 2402.40
    #   EEE no free slot
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [
        ("AAA", 1, 249),
        ("BBB", 2, 124),
        ("CCC", 3, 49),
        ("DDD", 4, 24),
    ]
    assert res.rejected == (Rejection("EEE", "no_slot"),)
    assert res.portfolio.free_slots() == ()
    assert [o.slot for o in res.portfolio.orders] == [1, 2, 3, 4]


def test_lowest_free_slot_skips_occupied_slots() -> None:
    pf = portfolio(
        P("10000"),
        opened("XOM", D("2026-10-01"), P("100"), P("110"), P("95"), 10, 2, slot=1),
        opened("CVX", D("2026-10-01"), P("150"), P("165"), P("140"), 10, 2, slot=3),
        equity=P("12500"),
        last_session=PREV,
    )
    res = size_picks(pf, [pick("AAA", "10"), pick("BBB", "20"), pick("CCC", "30")], SESSION)
    # slot budget 12500 / 4 = 3125
    #   AAA 3125 / 10.01 = 312.19 → 312, cost 3123.12, cash left 6876.88 > 3125
    #   BBB 3125 / 20.02 = 156.09 → 156
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 2, 312), ("BBB", 4, 156)]
    assert res.rejected == (Rejection("CCC", "no_slot"),)
    assert [(o.slot, o.symbol) for o in res.portfolio.orders] == [(1, "XOM"), (2, "AAA"), (3, "CVX"), (4, "BBB")]


def test_pick_order_decides_who_gets_the_lower_slot() -> None:
    res = size_picks(flat(), [pick("BBB", "20"), pick("AAA", "10")], SESSION)
    assert [(o.symbol, o.slot) for o in res.placed] == [("BBB", 1), ("AAA", 2)]


# --- the cash cap -----------------------------------------------------------------------------


def _appreciated() -> object:
    # XOM: 90 shares bought at 100, now marked near 133.33. Equity 15000 = 3000 cash + 12000 stock,
    # so equity / 4 = 3750 is more than the 3000 cash actually free.
    return portfolio(
        P("3000"),
        opened("XOM", D("2026-09-30"), P("100"), P("130"), P("90"), 90, 3, slot=1),
        equity=P("15000"),
        last_session=PREV,
    )


def test_cash_cap_when_appreciated_holding_lifts_equity_quarter_above_cash() -> None:
    picks = [pick("AAA", "50", tp="55", sl="45"), pick("BBB", "40", tp="44", sl="36"), pick("CCC", "20")]
    res = size_picks(_appreciated(), picks, SESSION)
    #   AAA budget = min(3750, 3000)          = 3000;  3000 / 50.05 = 59.94 → 59 (uncapped: 74)
    #       cost 59 × 50 × 1.001 = 2952.95;  committed 2952.95
    #   BBB budget = min(3750, 3000 − 2952.95) = 47.05; 47.05 / 40.04 = 1.18 → 1
    #       cost 40.04;                    committed 2992.99
    #   CCC budget = min(3750, 3000 − 2992.99) = 7.01;  7.01 / 20.02 = 0.35 → ineligible
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 2, 59), ("BBB", 3, 1)]
    assert res.rejected == (Rejection("CCC", "lt_one_share"),)
    assert res.portfolio.free_slots() == (4,)
    committed = sum(buy_cost(o.limit_price, o.shares) for o in res.placed)
    assert committed == P("2992.9900")
    assert committed <= res.portfolio.cash == P("3000")


def test_cash_cap_counts_pending_orders_placed_by_an_earlier_call() -> None:
    first = size_picks(_appreciated(), [pick("AAA", "50", tp="55", sl="45")], SESSION)
    assert first.placed[0].shares == 59
    # Second call the same night: the pending AAA (cost 2952.95) is already committed.
    second = size_picks(first.portfolio, [pick("BBB", "40", tp="44", sl="36")], SESSION)
    assert [(o.symbol, o.slot, o.shares) for o in second.placed] == [("BBB", 3, 1)]
    assert [o.symbol for o in second.portfolio.pending_orders()] == ["AAA", "BBB"]


def test_no_cash_left_rejects_lt_one_share() -> None:
    pf = portfolio(
        P("0"),
        opened("XOM", D("2026-10-01"), P("100"), P("110"), P("95"), 100, 2, slot=1),
        equity=P("10000"),
        last_session=PREV,
    )
    res = size_picks(pf, [pick("AAA", "10")], SESSION)
    assert res.placed == ()
    assert res.rejected == (Rejection("AAA", "lt_one_share"),)
    assert res.portfolio is pf


# --- ineligible -------------------------------------------------------------------------------


def test_ineligible_pick_does_not_consume_a_slot() -> None:
    picks = [pick("BRK.A", "700000", tp="770000", sl="630000"), pick("AAA", "10")]
    res = size_picks(flat("10000"), picks, SESSION)
    # 2500 / 700700 = 0.0036 → 0 shares; AAA still gets slot 1 with 2500 / 10.01 = 249.75 → 249
    assert res.rejected == (Rejection("BRK.A", "lt_one_share"),)
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 1, 249)]


# --- no adding, duplicates --------------------------------------------------------------------


def test_no_adding_to_open_or_pending_holding() -> None:
    pf = portfolio(
        P("10000"),
        opened("XOM", D("2026-10-01"), P("100"), P("110"), P("95"), 10, 2, slot=1),
        pending("CVX", SESSION, P("150"), P("165"), P("140"), 10, slot=2),
        equity=P("10000"),
        last_session=PREV,
    )
    res = size_picks(pf, [pick("XOM", "105"), pick("CVX", "151"), pick("AAA", "10")], SESSION)
    # Pending CVX commits 150 × 10 × 1.001 = 1501.50; cash left 8498.50 > 2500, so AAA gets 249.
    assert res.rejected == (Rejection("XOM", "held"), Rejection("CVX", "held"))
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 3, 249)]
    assert buy_cost(P("150"), 10) == P("1501.5000")


def test_duplicate_pick_is_rejected_held() -> None:
    res = size_picks(flat("10000"), [pick("AAA", "10"), pick("AAA", "12"), pick("BBB", "20")], SESSION)
    # AAA 249 (cost 2492.49); cash left 7507.51 > 2500, so BBB: 2500 / 20.02 = 124.88 → 124
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 1, 249), ("BBB", 2, 124)]
    assert res.rejected == (Rejection("AAA", "held"),)


def test_duplicate_of_an_ineligible_pick_is_still_held() -> None:
    picks = [pick("BRK.A", "700000", tp="770000", sl="630000"), pick("BRK.A", "700000", tp="770000", sl="630000")]
    res = size_picks(flat(), picks, SESSION)
    assert res.rejected == (Rejection("BRK.A", "lt_one_share"), Rejection("BRK.A", "held"))


def test_held_is_reported_before_no_slot() -> None:
    pf = portfolio(
        P("1000"),
        opened("XOM", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=1),
        opened("CVX", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=2),
        opened("KO", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=3),
        opened("PEP", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=4),
        equity=P("1400"),
        last_session=PREV,
    )
    res = size_picks(pf, [pick("XOM", "10"), pick("AAA", "10")], SESSION)
    assert res.rejected == (Rejection("XOM", "held"), Rejection("AAA", "no_slot"))
    assert res.portfolio is pf


# --- slot reuse after an exit and an expiry, through step --------------------------------------


def test_slots_freed_by_exit_and_expiry_are_reused_next_night() -> None:
    pf = portfolio(
        P("5000"),
        opened("AAA", D("2026-10-01"), P("50"), P("55"), P("47"), 40, 2, slot=1),
        pending("BBB", SESSION, P("30"), P("33"), P("28"), 80, slot=2),
        opened("CCC", D("2026-10-01"), P("20"), P("22"), P("19"), 100, 2, slot=3),
        opened("DDD", D("2026-10-02"), P("10"), P("11"), P("9.5"), 200, 1, slot=4),
        equity=P("10000"),
        last_session=PREV,
    )
    bars = {
        # AAA: open 49 is above SL 47 and below TP 55; low 46.5 <= 47 → SL exit at 47.
        "AAA": bar("AAA", SESSION, P("49"), P("49.5"), P("46.5"), P("47.5")),
        # BBB: low 30 is not < limit 30 → not filled → expires; slot 2 freed.
        "BBB": bar("BBB", SESSION, P("30.5"), P("31"), P("30"), P("30.8")),
        "CCC": bar("CCC", SESSION, P("20.5"), P("21"), P("20.2"), P("20.8")),
        "DDD": bar("DDD", SESSION, P("10.2"), P("10.5"), P("10.0"), P("10.4")),
    }
    stepped = step(pf, SESSION, bars)
    # cash 5000 + sell_proceeds(47, 40) = 5000 + 1878.12 = 6878.12
    # equity 6878.12 + 100 × 20.8 + 200 × 10.4 = 6878.12 + 2080 + 2080 = 11038.12
    assert sell_proceeds(P("47"), 40) == P("1878.1200")
    assert stepped.portfolio.cash == P("6878.1200")
    assert stepped.portfolio.equity == P("11038.1200")
    assert stepped.portfolio.free_slots() == (1, 2)

    picks = [pick("CCC", "21"), pick("EEE", "25", tp="27.5", sl="23"), pick("FFF", "40", tp="44", sl="37"), pick("GGG", "15")]
    res = size_picks(stepped.portfolio, picks, NEXT)
    # equity ÷ 4 recomputed from the new snapshot: 11038.12 / 4 = 2759.53
    #   CCC still open → held
    #   EEE min(2759.53, 6878.12)          → 2759.53 / 25.025 = 110.27 → 110, cost 2752.75
    #   FFF min(2759.53, 6878.12 − 2752.75 = 4125.37) → 2759.53 / 40.04 = 68.92 → 68, cost 2722.72
    #   GGG no free slot
    assert [(o.symbol, o.slot, o.shares, o.session_date) for o in res.placed] == [
        ("EEE", 1, 110, NEXT),
        ("FFF", 2, 68, NEXT),
    ]
    assert res.rejected == (Rejection("CCC", "held"), Rejection("GGG", "no_slot"))
    assert buy_cost(P("25"), 110) == P("2752.7500")
    assert buy_cost(P("40"), 68) == P("2722.7200")
    assert [(o.slot, o.symbol) for o in res.portfolio.orders] == [(1, "EEE"), (2, "FFF"), (3, "CCC"), (4, "DDD")]
    assert res.portfolio.cash == P("6878.1200")


# --- determinism ------------------------------------------------------------------------------


def test_same_inputs_give_identical_results() -> None:
    picks = [pick("AAA", "50", tp="55", sl="45"), pick("BBB", "40", tp="44", sl="36"), pick("CCC", "20")]
    assert size_picks(_appreciated(), picks, SESSION) == size_picks(_appreciated(), picks, SESSION)


# --- Pick validation --------------------------------------------------------------------------


def test_pick_quantizes_prices_to_4dp() -> None:
    p = Pick("AAA", Decimal("10.00005"), Decimal("10.00005"), Decimal("11"), Decimal("9"))
    assert p.limit_price == Decimal("10.0001")
    assert p.last_price == Decimal("10.0001")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"last_price": 10.0},
        {"limit_price": 10},
        {"tp_price": "11"},
        {"sl_price": None},
    ],
)
def test_pick_rejects_non_decimal_prices(kwargs: dict[str, object]) -> None:
    base: dict[str, object] = {
        "symbol": "AAA",
        "last_price": P("10"),
        "limit_price": P("10"),
        "tp_price": P("11"),
        "sl_price": P("9"),
    }
    with pytest.raises(TypeError):
        Pick(**{**base, **kwargs})


@pytest.mark.parametrize(
    ("limit", "tp", "sl"),
    [
        ("10", "11", "10"),  # sl == limit
        ("10", "11", "10.5"),  # sl > limit
        ("10", "10", "9"),  # tp == limit
        ("10", "9.5", "9"),  # tp < limit
        ("10", "11", "0"),  # sl not positive
    ],
)
def test_pick_requires_sl_below_limit_below_tp(limit: str, tp: str, sl: str) -> None:
    with pytest.raises(ValueError):
        Pick("AAA", P(limit), P(limit), P(tp), P(sl))


def test_pick_rejects_non_finite_and_empty_symbol() -> None:
    with pytest.raises(ValueError):
        Pick("AAA", P("10"), Decimal("NaN"), P("11"), P("9"))
    with pytest.raises(ValueError):
        Pick("", P("10"), P("10"), P("11"), P("9"))
    with pytest.raises(TypeError):
        Pick(None, P("10"), P("10"), P("11"), P("9"))  # type: ignore[arg-type]


# --- size_picks validation --------------------------------------------------------------------


@pytest.mark.parametrize(
    "session_date",
    [
        D("2026-10-03"),  # Saturday
        D("2026-11-26"),  # Thanksgiving
    ],
)
def test_session_date_must_be_an_nyse_session(session_date) -> None:
    with pytest.raises(ValueError):
        size_picks(flat(), [pick("AAA", "10")], session_date)


@pytest.mark.parametrize("session_date", [PREV, D("2026-10-01")])
def test_session_date_must_be_after_last_session(session_date) -> None:
    with pytest.raises(ValueError):
        size_picks(flat(), [], session_date)


def test_session_date_must_be_a_date_not_datetime() -> None:
    with pytest.raises(TypeError):
        size_picks(flat(), [], datetime(2026, 10, 5, 13, 30))


def test_picks_must_be_pick_values() -> None:
    with pytest.raises(TypeError):
        size_picks(flat(), [("AAA", P("10"))], SESSION)  # type: ignore[list-item]


def test_stale_pending_order_for_another_session_is_an_error() -> None:
    pf = portfolio(
        P("10000"),
        pending("CVX", PREV, P("150"), P("165"), P("140"), 10, slot=1),
        equity=P("10000"),
        last_session=D("2026-10-01"),
    )
    with pytest.raises(ValueError):
        size_picks(pf, [pick("AAA", "10")], SESSION)
