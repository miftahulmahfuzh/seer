"""apply_book_split: live book positions and targets rewritten in post-split units (paper-trading-ship
phase 2; plan index Decisions "§6 book split rule").

Every expected number is worked by hand in the comment next to it. Sessions: Mon 2026-10-05 is the
last stepped session, Tue 2026-10-06 is the split's execution session. No database needed.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime
from decimal import Decimal

import pytest

from seer_engine import sim
from seer_engine.sim import (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    Book,
    BookSplit,
    Fill,
    Position,
    Target,
    Trade,
    TradeRules,
    apply_book_split,
    step_book,
)
from seer_engine.splits import Split
from simkit import D, P, bar, day

MON = D("2026-10-05")
TUE = D("2026-10-06")
SAT = D("2026-10-10")

W = Decimal

TEN_FOR_ONE = W(10)
THREE_FOR_TWO = W(3) / W(2)  # 1.5
ONE_FOR_32 = W(1) / W(32)  # 0.03125, exact
ONE_FOR_10 = W("0.1")
ONE_FOR_3 = Split("ABC", TUE, split_from=W(3), split_to=W(1)).factor  # 0.3333…3 (28 digits)

WHOLE = MONTHLY_HOLD  # fractional=False
FRACTIONAL = TradeRules(id="fractional", engine="book", entry="open_limit", resize=True, fractional=True)


def pos(
    symbol: str,
    shares: str,
    mark: str,
    *,
    entry_price: str | None = None,
    days_held: int = 3,
    cost: str | None = None,
    income: str = "0",
    stop: str | None = None,
    take: str | None = None,
    exit_pending: bool = False,
) -> Position:
    """A held position entered 2026-10-01; ``cost`` defaults to q(entry × shares × 1.001)."""
    n = W(shares)
    entry = P(mark if entry_price is None else entry_price)
    return Position(
        symbol=symbol,
        shares=n,
        mark=P(mark),
        entry_date=D("2026-10-01"),
        entry_price=entry,
        days_held=days_held,
        cost_usd=sim.q(entry * n * W("1.001")) if cost is None else P(cost),
        income_usd=P(income),
        stop=None if stop is None else P(stop),
        take=None if take is None else P(take),
        exit_pending=exit_pending,
    )


def book(cash: str, *positions: Position, last=MON) -> Book:
    ps = tuple(sorted(positions, key=lambda p: p.symbol))
    equity = sim.q(P(cash) + sum((p.shares * p.mark for p in ps), W(0)))
    return Book(cash=P(cash), equity=equity, positions=ps, last_session=last)


def T(symbol: str, weight: str, last: str, limit: str | None = None, stop: str | None = None, take: str | None = None) -> Target:
    return Target(
        symbol=symbol,
        weight=W(weight),
        last=P(last),
        limit=None if limit is None else P(limit),
        stop=None if stop is None else P(stop),
        take=None if take is None else P(take),
    )


# ============================================================== forward splits


def test_forward_10_for_1_whole_shares_no_remainder():
    abc = pos("ABC", "3", "125.5", entry_price="120", stop="114", take="132")  # cost q(360.36)
    b = book("640", abc)  # equity 640 + 3 × 125.5 = 1016.5

    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE)

    assert isinstance(out, BookSplit)
    (p,) = out.book.positions
    assert p.shares == W(30)  # 3 × 10
    assert p.mark == P("12.55")  # 125.5 / 10
    assert p.entry_price == P("12")  # 120 / 10
    assert p.stop == P("11.4") and p.take == P("13.2")  # 114 / 10, 132 / 10
    assert p.cost_usd == P("360.36") and p.income_usd == P("0")  # cost unchanged, no in lieu
    assert p.entry_date == D("2026-10-01") and p.days_held == 3
    assert out.in_lieu == P("0")
    assert out.book.cash == P("640")
    assert out.book.equity == P("1016.5")  # 640 + 30 × 12.55 = 640 + 376.5
    assert out.book.last_session == MON  # the split does not step a session
    assert out.trade is None and out.fills == ()
    assert out.targets is None


def test_forward_3_for_2_whole_shares_pays_the_half_share_in_lieu():
    abc = pos("ABC", "5", "101", entry_price="99", stop="96", take="108", income="2")
    b = book("100", abc)  # equity 100 + 505 = 605

    out = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, WHOLE)

    (p,) = out.book.positions
    assert p.shares == W(7)  # floor(5 × 1.5 = 7.5)
    assert p.mark == P("67.3333")  # 101 / 1.5 = 67.3333…
    assert p.entry_price == P("66")  # 99 / 1.5
    assert p.stop == P("64") and p.take == P("72")  # 96 / 1.5, 108 / 1.5
    assert out.in_lieu == P("33.6667")  # q(0.5 × 67.3333 = 33.66665), half-up
    assert p.income_usd == P("35.6667")  # 2 + 33.6667
    assert out.book.cash == P("133.6667")  # 100 + 33.6667
    # Recomputed: 133.6667 + 7 × 67.3333 = 133.6667 + 471.3331 = 604.9998 (605 before; the
    # 0.0002 is the rounding of the rescaled mark, not lost cash).
    assert out.book.equity == P("604.9998")
    assert out.trade is None and out.fills == ()


# ============================================================== reverse splits


def test_reverse_1_for_32_keeps_three_shares_and_pays_an_eighth_in_lieu():
    abc = pos("ABC", "100", "2.5", entry_price="2.4", stop="2.2", take="3")
    b = book("0", abc)  # equity 250

    out = apply_book_split(b, "ABC", ONE_FOR_32, TUE, WHOLE)

    (p,) = out.book.positions
    assert p.shares == W(3)  # floor(100 / 32 = 3.125)
    assert p.mark == P("80")  # 2.5 × 32
    assert p.entry_price == P("76.8")  # 2.4 × 32
    assert p.stop == P("70.4") and p.take == P("96")  # 2.2 × 32, 3 × 32
    assert out.in_lieu == P("10")  # 0.125 × 80
    assert p.income_usd == P("10")
    assert out.book.cash == P("10")
    assert out.book.equity == P("250")  # 10 + 3 × 80


def test_one_for_3_is_read_as_an_exact_third():
    # 300 × 0.3333…3 (the 28-digit Decimal) is 99.99…, which would floor to 99.
    b = book("0", pos("ABC", "300", "10"))
    out = apply_book_split(b, "ABC", ONE_FOR_3, TUE, WHOLE)
    (p,) = out.book.positions
    assert p.shares == W(100)  # 300 / 3 exactly
    assert p.mark == P("30")  # 10 × 3
    assert out.in_lieu == P("0")

    b = book("0", pos("ABC", "301", "10"))
    out = apply_book_split(b, "ABC", ONE_FOR_3, TUE, WHOLE)
    (p,) = out.book.positions
    assert p.shares == W(100)  # floor(301 / 3 = 100.333…)
    assert out.in_lieu == P("10")  # 1/3 × 30
    assert out.book.cash == P("10")
    assert out.book.equity == P("3010")  # 10 + 100 × 30


# ============================================================== whole vs fractional shares


def test_whole_and_fractional_rules_floor_to_their_own_quantum():
    abc = pos("ABC", "2.5001", "90")  # a fractional book's position
    b = book("0", abc)  # equity q(2.5001 × 90 = 225.009)

    whole = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, WHOLE)
    (p,) = whole.book.positions
    assert p.shares == W(3)  # floor(2.5001 × 1.5 = 3.75015)
    assert p.mark == P("60")  # 90 / 1.5
    assert whole.in_lieu == P("45.009")  # 0.75015 × 60

    frac = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, FRACTIONAL)
    (p,) = frac.book.positions
    assert p.shares == W("3.7501")  # 3.75015 floored to 0.0001
    assert frac.in_lieu == P("0.003")  # 0.00005 × 60
    assert p.income_usd == P("0.003")
    assert frac.book.equity == P("225.009")  # 0.003 + 3.7501 × 60 = 0.003 + 225.006


def test_fractional_one_for_3_floors_a_third_to_the_share_quantum():
    b = book("0", pos("ABC", "1", "30"))
    out = apply_book_split(b, "ABC", ONE_FOR_3, TUE, FRACTIONAL)
    (p,) = out.book.positions
    assert p.shares == W("0.3333")  # 1/3 floored to 0.0001
    assert p.mark == P("90")  # 30 × 3
    assert out.in_lieu == P("0.003")  # (1/3 − 0.3333 = 1/30000) × 90 = 0.003


# ============================================================== floor to zero


def test_floor_to_zero_closes_the_position_as_a_forced_trade_at_the_old_mark():
    abc = pos("ABC", "7", "4", entry_price="3.5", income="1.2")  # cost q(3.5 × 7 × 1.001 = 24.5245)
    xyz = pos("XYZ", "2", "50")
    b = book("100", abc, xyz)  # equity 100 + 28 + 100 = 228

    out = apply_book_split(b, "ABC", ONE_FOR_10, TUE, WHOLE)

    assert out.book.positions == (xyz,)  # other positions untouched
    assert out.in_lieu == P("28")  # 7 / 10 = 0.7 share × (4 × 10 = 40)
    assert out.book.cash == P("128")
    assert out.book.equity == P("228")  # 128 + 2 × 50
    assert out.book.last_session == MON
    assert out.trade == Trade(
        symbol="ABC",
        entry_date=D("2026-10-01"),
        exit_date=TUE,
        entry_price=P("3.5"),
        exit_price=P("4"),  # the old (pre-split) mark
        days_held=3,
        cost_usd=P("24.5245"),
        income_usd=P("29.2"),  # 1.2 + 28 in lieu
        pnl_usd=P("4.6755"),  # 29.2 − 24.5245
        exit_reason="forced",
        idle=False,
    )
    assert out.fills == (
        Fill(
            session_date=TUE,
            symbol="ABC",
            side="sell",
            shares=W(7),  # pre-split shares
            price=P("4"),
            cash_usd=P("28"),
            cost_usd=P("0"),  # cash in lieu has no cost
            reason="forced",
        ),
    )


def test_floor_to_zero_of_the_idle_instrument_is_an_idle_trade():
    b = book("0", pos("BIL", "3", "91"))
    out = apply_book_split(b, "BIL", ONE_FOR_10, TUE, MONTHLY_HOLD_TBILL)
    assert out.book.positions == ()
    assert out.trade is not None and out.trade.idle is True
    assert out.in_lieu == P("273")  # 0.3 × 910
    assert out.book.equity == P("273")


def test_floor_to_zero_does_not_check_stop_and_take_it_drops():
    # stop 0.4 / 10000 would round to 0; the position is closed, so that does not matter.
    b = book("0", pos("ABC", "1", "1", stop="0.4", take="2"))
    out = apply_book_split(b, "ABC", W("0.5"), TUE, WHOLE)  # 1-for-2: floor(0.5) = 0
    assert out.book.positions == ()
    assert out.in_lieu == P("1")  # 0.5 × 2


# ============================================================== targets


def test_targets_for_the_symbol_are_rescaled_and_others_kept():
    abc_t = T("ABC", "0.5", "125", limit="124", stop="114", take="132")
    xyz_t = T("XYZ", "0.25", "50")
    targets = (abc_t, xyz_t)
    b = book("1000")  # nothing held

    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, targets)

    assert out.book is b  # no position in ABC: the book is returned as is
    assert out.in_lieu == P("0") and out.trade is None and out.fills == ()
    assert out.targets == (
        Target(symbol="ABC", weight=W("0.5"), last=P("12.5"), limit=P("12.4"), stop=P("11.4"), take=P("13.2")),
        xyz_t,
    )
    assert out.targets[1] is xyz_t  # untouched targets are the same objects, in the same order


def test_reverse_split_rescales_targets_and_the_position_together():
    targets = (T("ABC", "1", "2.5", stop="2.2", take="3"),)
    b = book("0", pos("ABC", "64", "2.5"))
    out = apply_book_split(b, "ABC", ONE_FOR_32, TUE, WHOLE, targets)
    assert out.targets == (Target(symbol="ABC", weight=W("1"), last=P("80"), stop=P("70.4"), take=P("96")),)
    (p,) = out.book.positions
    assert p.shares == W(2)  # 64 / 32
    assert out.in_lieu == P("0")


def test_empty_targets_stay_empty():
    b = book("10", pos("ABC", "3", "10"))
    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, ())
    assert out.targets == ()


# ============================================================== no-op, sequencing


def test_nothing_references_the_symbol_is_a_no_op():
    xyz = pos("XYZ", "2", "50")
    b = book("100", xyz)
    targets = (T("XYZ", "0.5", "50"),)
    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, targets)
    assert out == BookSplit(book=b, targets=targets, in_lieu=P("0"), trade=None, fills=())
    assert out.book is b and out.targets is targets


def test_a_split_book_steps_the_split_session_in_post_split_units():
    b = book("640", pos("ABC", "3", "125.5", entry_price="120", stop="114", take="132"))
    split = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE)
    stepped = step_book(split.book, TUE, day(bar("ABC", TUE, "12.6", "12.9", "12.5", "12.8")), None, WHOLE)
    (p,) = stepped.book.positions
    assert p.shares == W(30) and p.mark == P("12.8") and p.days_held == 4
    assert stepped.trades == ()  # 12.5 > stop 11.4, 12.9 < take 13.2
    assert stepped.snapshot.equity_usd == P("1024")  # 640 + 30 × 12.8


def test_exit_pending_survives_the_split():
    b = book("0", pos("ABC", "3", "10", exit_pending=True))
    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE)
    assert out.book.positions[0].exit_pending is True


# ============================================================== errors


def test_type_errors():
    b = book("10", pos("ABC", "3", "10"))
    with pytest.raises(TypeError):
        apply_book_split("book", "ABC", TEN_FOR_ONE, TUE, WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, b"ABC", TEN_FOR_ONE, TUE, WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", 10.0, TUE, WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", 10, TUE, WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, datetime(2026, 10, 6), WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, "2026-10-06", WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, "monthly-hold")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, [T("ABC", "1", "10")])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, ("ABC",))  # type: ignore[arg-type]


def test_value_errors():
    b = book("10", pos("ABC", "3", "10"))
    with pytest.raises(ValueError):
        apply_book_split(b, "", TEN_FOR_ONE, TUE, WHOLE)
    for bad in (W(1), W(0), W(-2), W("NaN"), W("Infinity"), W("3.14159265358979")):
        with pytest.raises(ValueError):
            apply_book_split(b, "ABC", bad, TUE, WHOLE)
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, SAT, WHOLE)  # not a session
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, MON, WHOLE)  # not after last_session
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, DESIGN_V0)  # a bracket rule set
    # The checks run before the no-op shortcut, like sim.apply_split.
    with pytest.raises(ValueError):
        apply_book_split(b, "XYZ", TEN_FOR_ONE, SAT, WHOLE)


def test_prices_4dp_cannot_hold_are_refused():
    # 10000-for-1: stop 0.4 -> 0.00004 rounds to 0 on a surviving position.
    b = book("0", pos("ABC", "1", "1", stop="0.4", take="2"))
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", W(10000), TUE, WHOLE)
    # A mark that rounds to 0 is refused even when the position would close.
    b = book("0", pos("ABC", "1", "0.0004"))
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", W(10), TUE, WHOLE)
    # A target whose rescaled limit rounds to 0.
    with pytest.raises(ValueError):
        apply_book_split(book("0"), "ABC", W(10000), TUE, WHOLE, (T("ABC", "1", "1", limit="0.4"),))


# ============================================================== purity


def test_inputs_untouched_and_result_deterministic():
    abc = pos("ABC", "5", "101", entry_price="99", stop="96", take="108")
    b = book("100", abc, pos("XYZ", "2", "50"))
    targets = (T("ABC", "0.5", "101", stop="96", take="108"), T("XYZ", "0.5", "50"))
    before = (b, targets)
    first = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, WHOLE, targets)
    second = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, WHOLE, targets)
    assert first == second
    assert (b, targets) == before
    assert b.positions[0] is abc and abc.shares == W(5)
    with pytest.raises(FrozenInstanceError):
        first.in_lieu = W(0)  # type: ignore[misc]


def test_exported_from_sim():
    from seer_engine.sim import book as book_module

    assert sim.apply_book_split is book_module.apply_book_split
    assert sim.BookSplit is book_module.BookSplit
    assert "apply_book_split" in sim.__all__ and "BookSplit" in sim.__all__
