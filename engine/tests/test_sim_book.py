"""The book engine (P7a phase 1): one synthetic-bar test (or more) per lever, plus a
session-by-session replay of §5 (``size_picks`` + ``step``) under ``V0_BOOK``.

Real NYSE dates: 2026-10-05 is a Monday. Every hand-checked number is in the comments.
No database needed.
"""

from __future__ import annotations

import random
from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal

import pytest

from seer_engine import dates, sim
from seer_engine.prices import Bar
from seer_engine.sim import (
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    DESIGN_V0,
    SWING_T10,
    SWING_T20,
    V0_BOOK,
    Book,
    BookStep,
    Pick,
    Position,
    Target,
    TradeRules,
    close_book_unpriced,
    equal_weight,
    new_book,
    new_portfolio,
    size_picks,
    step,
    step_book,
    to_weight,
)
from seer_engine.sim.book import WEIGHT_QUANTUM
from simkit import D, P, bar, day

MON = "2026-10-05"
TUE = "2026-10-06"
WED = "2026-10-07"
THU = "2026-10-08"
FRI = "2026-10-09"

W = Decimal

RESIZE = TradeRules(id="resize", engine="book", entry="open_limit", resize=True)
OPEN = TradeRules(id="open", engine="book", entry="open")
FRACTIONAL = TradeRules(id="fractional", engine="book", entry="open_limit", fractional=True)


def T(symbol: str, weight: str, last: str, limit: str | None = None, stop: str | None = None, take: str | None = None) -> Target:
    return Target(
        symbol=symbol,
        weight=W(weight),
        last=P(last),
        limit=None if limit is None else P(limit),
        stop=None if stop is None else P(stop),
        take=None if take is None else P(take),
    )


def pos(
    symbol: str,
    shares: int | str,
    mark: str,
    *,
    entry_date: str = "2026-10-01",
    entry_price: str | None = None,
    days_held: int = 3,
    cost: str | None = None,
    income: str = "0",
    stop: str | None = None,
    take: str | None = None,
    exit_pending: bool = False,
) -> Position:
    """A held position; ``cost`` defaults to q(entry × shares × 1.001)."""
    n = W(shares)
    entry = P(mark if entry_price is None else entry_price)
    return Position(
        symbol=symbol,
        shares=n,
        mark=P(mark),
        entry_date=D(entry_date),
        entry_price=entry,
        days_held=days_held,
        cost_usd=sim.q(entry * n * W("1.001")) if cost is None else P(cost),
        income_usd=P(income),
        stop=None if stop is None else P(stop),
        take=None if take is None else P(take),
        exit_pending=exit_pending,
    )


def book(cash: str, *positions: Position, last: str = MON) -> Book:
    ps = tuple(sorted(positions, key=lambda p: p.symbol))
    equity = sim.q(P(cash) + sum((p.shares * p.mark for p in ps), W(0)))
    return Book(cash=P(cash), equity=equity, positions=ps, last_session=D(last))


def go(b: Book, session: str, bars: dict[str, Bar], targets, rules: TradeRules, **kw) -> BookStep:
    return step_book(b, D(session), bars, targets, rules, **kw)


# ============================================================== weights and values


def test_to_weight_quantizes_down():
    assert to_weight(W("0.3333339")) == W("0.333333")
    assert to_weight(0.1) == W("0.100000")  # float via repr, not its binary expansion
    assert to_weight(1) == W("1")
    assert to_weight(W("0.0000019")) == WEIGHT_QUANTUM
    for bad in (W("0.0000009"), W(0), W("-0.5"), float("nan"), W("Infinity")):
        with pytest.raises(ValueError):
            to_weight(bad)
    for bad in (True, "0.5", None):
        with pytest.raises(TypeError):
            to_weight(bad)  # type: ignore[arg-type]


def test_equal_weight():
    assert equal_weight(1) == W(1)
    assert equal_weight(3) == W("0.333333")
    assert equal_weight(4) == W("0.25")
    assert equal_weight(8) == W("0.125")
    with pytest.raises(ValueError):
        equal_weight(0)
    with pytest.raises(TypeError):
        equal_weight(2.0)  # type: ignore[arg-type]


def test_target_validation():
    t = Target("SPY", W("0.5"), W("100.00004"), limit=W("99.5"), stop=W("95"), take=W("110"))
    assert t.last == W("100.0000")
    with pytest.raises(TypeError):
        Target("SPY", W("0.5"), 100.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Target("SPY", 0.5, W(100))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Target("SPY", W("0.5"), W(100), limit=99.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="multiple"):
        Target("SPY", W("0.1234567"), W(100))
    for bad in (W(0), W("1.000001"), W("-0.1")):
        with pytest.raises(ValueError, match=r"\(0, 1\]"):
            Target("SPY", bad, W(100))
    with pytest.raises(ValueError, match="> 0"):
        Target("SPY", W("0.5"), W("0.00001"))
    with pytest.raises(ValueError, match="below"):
        Target("SPY", W("0.5"), W(100), limit=W(99), stop=W(99))
    with pytest.raises(ValueError, match="above"):
        Target("SPY", W("0.5"), W(100), take=W(100))
    with pytest.raises(ValueError):
        Target("", W("0.5"), W(100))
    with pytest.raises(FrozenInstanceError):
        t.weight = W(1)  # type: ignore[misc]


def test_book_validation_and_accessors():
    b = book("100", pos("BBB", 1, "10"), pos("AAA", 2, "5"))
    assert b.held() == frozenset({"AAA", "BBB"})
    assert b.position("AAA").shares == W(2)
    assert b.position("ZZZ") is None
    with pytest.raises(ValueError, match="sorted"):
        Book(cash=W(1), equity=W(1), positions=(pos("BBB", 1, "10"), pos("AAA", 1, "10")))
    with pytest.raises(TypeError):
        Book(cash=1.0, equity=W(1))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        pos("AAA", 0, "10")
    with pytest.raises(TypeError):
        Position("AAA", 1, W(1), D(MON), W(1), 1, W(1), W(0), None, None)  # type: ignore[arg-type]


def test_new_book():
    b = new_book(W("1234.56789"))
    assert (b.cash, b.equity, b.positions, b.last_session) == (W("1234.5679"), W("1234.5679"), (), None)
    with pytest.raises(ValueError):
        new_book(W(0))
    with pytest.raises(TypeError):
        new_book(1000.0)  # type: ignore[arg-type]


def test_book_values_are_exported_from_sim():
    assert sim.step_book is step_book
    assert sim.Target is Target
    assert sim.to_weight is to_weight
    assert sim.close_book_unpriced is close_book_unpriced
    for name in ("Book", "Position", "Fill", "Trade", "BookSnapshot", "BookStep", "new_book", "equal_weight"):
        assert hasattr(sim, name), name


# ============================================================== step_book argument checks


def test_step_book_rejects_the_bracket_engine_and_bad_sessions():
    b = new_book(W(1000))
    with pytest.raises(ValueError, match="engine 'book'"):
        go(b, TUE, {}, None, DESIGN_V0)
    with pytest.raises(ValueError, match="not an NYSE session"):
        go(b, "2026-10-04", {}, None, DAILY_SWITCH)
    later = go(b, TUE, {}, None, DAILY_SWITCH).book
    with pytest.raises(ValueError, match="not after"):
        go(later, TUE, {}, None, DAILY_SWITCH)
    with pytest.raises(TypeError):
        go(b, TUE, {}, [T("SPY", "1", "100")], DAILY_SWITCH)  # a list, not a tuple


def test_step_book_rejects_bad_targets():
    b = new_book(W(1000))
    with pytest.raises(ValueError, match="twice"):
        go(b, TUE, {}, (T("SPY", "0.5", "100"), T("SPY", "0.5", "100")), DAILY_SWITCH)
    with pytest.raises(ValueError, match="sum to"):
        go(b, TUE, {}, (T("SPY", "0.6", "100"), T("QQQ", "0.5", "100")), DAILY_SWITCH)
    with pytest.raises(TypeError):
        go(b, TUE, {}, ("SPY",), DAILY_SWITCH)


def test_step_book_rejects_float_prices_in_bars():
    b = new_book(W(1000))
    bad = Bar("SPY", D(TUE), 100.0, W(101), W(99), W(100), 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        go(b, TUE, {"SPY": bad}, (T("SPY", "0.5", "100"),), DAILY_SWITCH)


def test_max_positions_lets_ranked_targets_weigh_more_than_one():
    # §5 ranks more picks than slots on purpose; with max_positions set the extra ones are no_slot.
    r = replace(DAILY_SWITCH, id="capped", max_positions=2)
    out = go(new_book(W(1000)), TUE, {}, (T("A", "0.5", "10"), T("B", "0.5", "10"), T("C", "0.5", "10")), r)
    assert out.rejected == (("A", "no_bar"), ("B", "no_bar"), ("C", "no_slot"))


# ============================================================== signal exits


def test_signal_exit_sells_a_dropped_position_at_the_next_open():
    b = book("1000", pos("AAA", 10, "100", cost="1001"))
    out = go(b, TUE, day(bar("AAA", TUE, "105", "106", "104", "105.5")), (), DAILY_SWITCH)
    # q(105 × 10 × 0.999) = 1048.95; fee q(105 × 10 × 0.001) = 1.05
    (f,) = out.fills
    assert (f.side, f.shares, f.price, f.cash_usd, f.cost_usd, f.reason) == ("sell", W(10), P("105"), P("1048.95"), P("1.05"), "signal")
    (t,) = out.trades
    assert (t.exit_reason, t.days_held, t.exit_price, t.pnl_usd, t.idle) == ("signal", 3, P("105"), P("47.95"), False)
    assert out.book.positions == ()
    assert (out.snapshot.cash_usd, out.snapshot.equity_usd, out.snapshot.invested_usd) == (P("2048.95"), P("2048.95"), P(0))


def test_no_decision_means_no_signal_exit():
    b = book("1000", pos("AAA", 10, "100"))
    out = go(b, TUE, day(bar("AAA", TUE, "105", "106", "104", "105.5")), None, DAILY_SWITCH)
    assert out.fills == () and out.trades == ()
    p = out.book.position("AAA")
    assert (p.days_held, p.mark) == (4, P("105.5"))
    assert out.snapshot.equity_usd == P("2055")


def test_a_kept_target_is_not_sold():
    b = book("1000", pos("AAA", 10, "100"))
    out = go(b, TUE, day(bar("AAA", TUE, "105", "106", "104", "105.5")), (T("AAA", "0.5", "100"),), DAILY_SWITCH)
    assert out.fills == () and out.book.position("AAA").shares == W(10)


def test_signal_exit_without_a_bar_waits_for_the_next_bar():
    b = book("1000", pos("AAA", 10, "100", cost="1001"))
    out = go(b, TUE, {}, (), DAILY_SWITCH)
    p = out.book.position("AAA")
    assert (p.exit_pending, p.days_held, p.mark) == (True, 4, P("100"))
    assert out.fills == ()
    # WED is not a decision session (targets None), yet the pending exit is sold at its open.
    out2 = go(out.book, WED, day(bar("AAA", WED, "99", "101", "98", "100")), None, DAILY_SWITCH)
    (t,) = out2.trades
    # q(99 × 10 × 0.999) = 989.01; pnl = 989.01 − 1001 = −11.99; days_held stays 4 at the open
    assert (t.exit_reason, t.exit_price, t.days_held, t.pnl_usd) == ("signal", P("99"), 4, P("-11.99"))
    assert out2.book.positions == ()
    assert out2.snapshot.cash_usd == P("1989.01")


def test_no_reentry_on_the_session_of_an_exit_at_the_open():
    b = book("0", pos("AAA", 10, "100", days_held=10))
    bars = day(bar("AAA", TUE, "100", "101", "99", "100"))
    out = go(b, TUE, bars, (T("AAA", "1", "100"),), replace(SWING_T10, entry="open_limit", id="t10-open"))
    assert [f.reason for f in out.fills] == ["time"]
    assert out.book.positions == ()
    assert out.rejected == ()


# ============================================================== rebalance (trims and adds)


def _two_held() -> Book:
    return book("0", pos("AAA", 60, "100"), pos("BBB", 40, "100"))  # equity 10,000


def test_rebalance_trims_and_adds_at_the_open():
    b = _two_held()
    bars = day(
        bar("AAA", TUE, "101", "102", "100", "101"),
        bar("BBB", TUE, "99", "100", "98.5", "99.5"),
    )
    out = go(b, TUE, bars, (T("AAA", "0.5", "100"), T("BBB", "0.5", "100")), RESIZE)
    # desired = floor(q(10000 × 0.5) / (100 × 1.001)) = 49 for both.
    # AAA: excess 11 × 100 = 1100 >= 1% × 10000 -> trim 11 at the open 101: q(1111 × 0.999) = 1109.889.
    # BBB: gap 9 × 100 = 900 >= 100 -> add; limit q(100 × 1.02) = 102, cash at night = 0 + planned
    #      trim q(100 × 11 × 0.999) = 1098.9 -> min(9, floor(1098.9 / 102.102) = 10) = 9;
    #      fill at min(99, 102) = 99: q(99 × 9 × 1.001) = 891.891.
    assert [(f.symbol, f.side, f.shares, f.price, f.cash_usd, f.reason) for f in out.fills] == [
        ("AAA", "sell", W(11), P("101"), P("1109.889"), "trim"),
        ("BBB", "buy", W(9), P("99"), P("-891.891"), "add"),
    ]
    assert out.trades == ()
    a, bb = out.book.position("AAA"), out.book.position("BBB")
    assert (a.shares, a.income_usd, a.days_held, a.mark) == (W(49), P("1109.889"), 4, P("101"))
    assert (bb.shares, bb.cost_usd, bb.days_held, bb.entry_price) == (W(49), b.position("BBB").cost_usd + P("891.891"), 4, P("100"))
    # cash 217.998; equity = 217.998 + 49 × 101 + 49 × 99.5
    assert out.snapshot.cash_usd == P("217.998")
    assert out.snapshot.equity_usd == P("10042.498")


def test_rebalance_inside_the_band_does_nothing():
    # equity 10,000: desired = floor(5000 / 99.099) = 50; AAA is 1 share × 99 = 99 < 100 over.
    b = book("100", pos("AAA", 51, "99"), pos("BBB", 49, "99"))
    bars = day(bar("AAA", TUE, "99", "99", "99", "99"), bar("BBB", TUE, "99", "99", "98", "99"))
    out = go(b, TUE, bars, (T("AAA", "0.5", "99"), T("BBB", "0.5", "99")), RESIZE)
    assert out.fills == () and out.rejected == ()


def test_without_resize_held_targets_keep_their_shares():
    b = _two_held()
    bars = day(bar("AAA", TUE, "101", "102", "100", "101"), bar("BBB", TUE, "99", "100", "98.5", "99.5"))
    out = go(b, TUE, bars, (T("AAA", "0.5", "100"), T("BBB", "0.5", "100")), DAILY_SWITCH)
    assert out.fills == ()
    assert [p.shares for p in out.book.positions] == [W(60), W(40)]


def test_a_trim_to_zero_closes_the_episode():
    b = book("0", pos("AAA", 1, "100"), pos("BBB", 99, "100"))  # equity 10,000
    bars = day(bar("AAA", TUE, "100", "100", "100", "100"), bar("BBB", TUE, "100", "100", "100", "100"))
    # AAA weight 0.000001 -> q(0.01) buys 0 shares at 100.1 -> desired 0; excess 1 × 100 >= 100.
    out = go(b, TUE, bars, (T("AAA", "0.000001", "100"), T("BBB", "0.9", "100")), RESIZE)
    assert [(f.symbol, f.reason) for f in out.fills][0] == ("AAA", "trim")
    (t,) = out.trades
    assert (t.symbol, t.exit_reason) == ("AAA", "signal")
    assert out.book.position("AAA") is None


# ============================================================== dividends


def test_dividends_are_credited_on_the_ex_date():
    b = book("500", pos("AAA", 10, "50"))
    out = go(b, TUE, day(bar("AAA", TUE, "50", "51", "49", "50")), None, DAILY_SWITCH, dividends={"AAA": W("0.4567"), "ZZZ": W(1)})
    # q(10 × 0.4567) = 4.567 (ZZZ is not held)
    assert out.dividends == (("AAA", P("4.567")),)
    assert out.snapshot.cash_usd == P("504.567")
    assert out.book.position("AAA").income_usd == P("4.567")
    assert out.snapshot.equity_usd == P("1004.567")


def test_dividends_off_credits_nothing():
    b = book("500", pos("AAA", 10, "50"))
    r = replace(DAILY_SWITCH, id="no-divs", dividends=False)
    out = go(b, TUE, day(bar("AAA", TUE, "50", "51", "49", "50")), None, r, dividends={"AAA": W("0.4567")})
    assert out.dividends == () and out.snapshot.cash_usd == P("500")


def test_a_position_sold_on_the_ex_date_still_gets_the_dividend():
    b = book("500", pos("AAA", 10, "50", cost="500.5"))
    out = go(b, TUE, day(bar("AAA", TUE, "51", "52", "50", "51")), (), DAILY_SWITCH, dividends={"AAA": W("0.4567")})
    (t,) = out.trades
    # income = 4.567 + q(510 × 0.999) = 4.567 + 509.49; pnl = 514.057 − 500.5
    assert (t.income_usd, t.pnl_usd) == (P("514.057"), P("13.557"))
    assert out.snapshot.cash_usd == P("1014.057")


def test_a_position_bought_on_the_ex_date_gets_no_dividend():
    out = go(new_book(W(1000)), TUE, day(bar("AAA", TUE, "50", "51", "49", "50")), (T("AAA", "0.5", "50"),), DAILY_SWITCH, dividends={"AAA": W(1)})
    assert out.dividends == ()
    assert out.book.position("AAA").income_usd == 0


def test_dividend_amounts_are_decimals():
    b = book("500", pos("AAA", 10, "50"))
    with pytest.raises(TypeError):
        go(b, TUE, {}, None, DAILY_SWITCH, dividends={"AAA": 0.5})
    with pytest.raises(ValueError):
        go(b, TUE, {}, None, DAILY_SWITCH, dividends={"AAA": W(0)})


# ============================================================== fractional shares


def test_fractional_shares_round_down_to_the_share_quantum():
    bars = day(bar("XYZ", TUE, "301", "305", "299", "304"))
    out = go(new_book(W(1000)), TUE, bars, (T("XYZ", "1", "300"),), FRACTIONAL)
    # limit q(300 × 1.02) = 306; 1000 / (306 × 1.001) = 3.26470... -> 3.2647
    (f,) = out.fills
    assert (f.shares, f.price) == (W("3.2647"), P("301"))
    # q(301 × 3.2647 × 1.001) = q(983.6573747) = 983.6574
    assert f.cash_usd == P("-983.6574")
    assert out.snapshot.cash_usd == P("16.3426")
    assert out.snapshot.equity_usd == sim.q(P("16.3426") + W("3.2647") * P("304"))


def test_whole_shares_by_default():
    bars = day(bar("XYZ", TUE, "301", "305", "299", "304"))
    out = go(new_book(W(1000)), TUE, bars, (T("XYZ", "1", "300"),), DAILY_SWITCH)
    (f,) = out.fills
    assert f.shares == W(3)
    assert f.cash_usd == P("-903.903")  # q(301 × 3 × 1.001)
    assert out.book.position("XYZ").shares == W(3)


# ============================================================== entry types


def test_open_limit_entry_fills_below_the_band():
    bars = day(bar("SPY", TUE, "101", "103", "100.5", "102"))
    out = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), DAILY_SWITCH)
    # limit q(100 × 1.02) = 102; floor(5000 / 102.102) = 48; fill at min(101, 102) = 101
    (f,) = out.fills
    assert (f.shares, f.price, f.cash_usd, f.reason) == (W(48), P("101"), P("-4852.848"), "entry")
    p = out.book.position("SPY")
    assert (p.days_held, p.entry_date, p.entry_price, p.mark, p.cost_usd) == (1, D(TUE), P("101"), P("102"), P("4852.848"))


def test_open_limit_entry_gapping_above_the_band_goes_unfilled():
    bars = day(bar("SPY", TUE, "103", "104", "102.5", "103.5"))
    out = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), DAILY_SWITCH)
    assert out.fills == () and out.rejected == (("SPY", "unfilled"),)
    # the low must trade strictly below the limit
    bars = day(bar("SPY", TUE, "103", "104", "102", "103.5"))
    assert go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), DAILY_SWITCH).rejected == (("SPY", "unfilled"),)
    # a gap above the band that trades back through it fills at the limit
    bars = day(bar("SPY", TUE, "103", "104", "101.9999", "103.5"))
    (f,) = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), DAILY_SWITCH).fills
    assert f.price == P("102")


def test_open_entry_fills_at_the_open_whatever_the_gap():
    bars = day(bar("SPY", TUE, "103", "104", "102.5", "103.5"))
    out = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), OPEN)
    # sized at q(100 × 1.02) = 102 -> 48 shares; filled at the open 103: q(103 × 48 × 1.001) = 4948.944
    (f,) = out.fills
    assert (f.shares, f.price, f.cash_usd) == (W(48), P("103"), P("-4948.944"))


def test_limit_entry_uses_the_target_limit_and_brackets():
    bars = day(bar("AAA", TUE, "100", "101", "98.9", "100.5"))
    out = go(new_book(W(10000)), TUE, bars, (T("AAA", "0.25", "100", limit="99", stop="95", take="104"),), SWING_T20)
    # floor(2500 / (99 × 1.001)) = 25; fill at min(100, 99) = 99
    (f,) = out.fills
    assert (f.shares, f.price) == (W(25), P("99"))
    p = out.book.position("AAA")
    assert (p.stop, p.take) == (P("95"), P("104"))


def test_limit_entry_without_a_limit_buys_like_open_limit():
    # SWING_T20 (entry "limit"): an unheld target with no limit price is bought at q(last × 1.02).
    bars = day(bar("SPY", TUE, "101", "103", "100.5", "102"))
    out = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), SWING_T20)
    # limit q(100 × 1.02) = 102; floor(5000 / 102.102) = 48; fill at min(101, 102) = 101
    (f,) = out.fills
    assert (f.shares, f.price, f.reason) == (W(48), P("101"), "entry")
    assert out.book.position("SPY").stop is None and out.book.position("SPY").take is None
    # gapping above the band: unfilled, exactly as open_limit
    gap = day(bar("SPY", TUE, "103", "104", "102.5", "103.5"))
    assert go(new_book(W(10000)), TUE, gap, (T("SPY", "0.5", "100"),), SWING_T20).rejected == (("SPY", "unfilled"),)
    # a HELD target without a limit price is kept and never added to
    held = book("10000", pos("SPY", 10, "100"))
    kept = go(held, TUE, bars, (T("SPY", "1", "100"),), SWING_T20)
    assert kept.fills == () and kept.book.position("SPY").shares == W(10)


def test_a_new_position_is_not_stopped_on_its_fill_session():
    bars = day(bar("AAA", TUE, "100", "110", "90", "100"))  # through both stop and take
    out = go(new_book(W(10000)), TUE, bars, (T("AAA", "0.25", "100", limit="99", stop="95", take="104"),), SWING_T20)
    assert out.trades == () and out.book.position("AAA") is not None


def test_no_bar_on_the_session_rejects_the_entry():
    out = go(new_book(W(10000)), TUE, {}, (T("AAA", "0.25", "100"),), DAILY_SWITCH)
    assert out.rejected == (("AAA", "no_bar"),)


def test_too_small_rejects_and_ranks_on():
    bars = day(bar("BIG", TUE, "3000", "3000", "2990", "3000"), bar("SMALL", TUE, "10", "10", "9.9", "10"))
    out = go(new_book(W(1000)), TUE, bars, (T("BIG", "0.5", "3000"), T("SMALL", "0.5", "10")), DAILY_SWITCH)
    assert out.rejected == (("BIG", "too_small"),)
    assert [f.symbol for f in out.fills] == ["SMALL"]


# ============================================================== max_positions


def test_max_positions_two():
    r = replace(DAILY_SWITCH, id="two", max_positions=2)
    bars = day(*(bar(s, TUE, "10", "10", "9.9", "10") for s in ("A", "B", "C")))
    out = go(new_book(W(10000)), TUE, bars, (T("A", "0.25", "10"), T("B", "0.25", "10"), T("C", "0.25", "10")), r)
    assert [f.symbol for f in out.fills] == ["A", "B"]
    assert out.rejected == (("C", "no_slot"),)


def test_an_exit_by_rule_at_the_open_does_not_free_a_slot():
    r = TradeRules(id="one", engine="book", entry="open_limit", max_positions=1, time_stop=2)
    b = book("1000", pos("A", 10, "10", days_held=2))
    bars = day(bar("A", TUE, "10", "10", "9.9", "10"), bar("B", TUE, "10", "10", "9.9", "10"))
    out = go(b, TUE, bars, (T("A", "0.5", "10"), T("B", "0.5", "10")), r)
    assert [(f.symbol, f.reason) for f in out.fills] == [("A", "time")]
    assert out.rejected == (("B", "no_slot"),)


def test_a_signal_exit_frees_its_slot_and_funds_the_entry():
    r = TradeRules(id="one", engine="book", entry="open_limit", max_positions=1)
    b = book("0", pos("A", 100, "10"))
    bars = day(bar("A", TUE, "10", "10", "9.9", "10"), bar("B", TUE, "10.1", "10.2", "10", "10.1"))
    out = go(b, TUE, bars, (T("B", "1", "10"),), r)
    # night: planned q(10 × 100 × 0.999) = 999; budget min(1000, 999) at 10.2 -> floor(999 / 10.2102) = 97
    assert [(f.symbol, f.side, f.shares, f.reason) for f in out.fills] == [
        ("A", "sell", W(100), "signal"),
        ("B", "buy", W(97), "entry"),
    ]
    # 999 − q(10.1 × 97 × 1.001) = 999 − 980.6797
    assert out.snapshot.cash_usd == P("18.3203")


# ============================================================== time stop


@pytest.mark.parametrize("rules,limit", [(SWING_T10, 10), (SWING_T20, 20)])
def test_time_stop_sells_at_the_open_once_held_long_enough(rules, limit):
    b = book("0", pos("AAA", 10, "100", days_held=limit - 1))
    out = go(b, TUE, day(bar("AAA", TUE, "100", "101", "99", "100")), None, rules)
    assert out.fills == () and out.book.position("AAA").days_held == limit
    out2 = go(out.book, WED, day(bar("AAA", WED, "102", "103", "101", "102")), None, rules)
    (t,) = out2.trades
    assert (t.exit_reason, t.days_held, t.exit_price) == ("time", limit, P("102"))


def test_no_time_stop_holds_indefinitely():
    b = book("0", pos("AAA", 10, "100", days_held=500))
    out = go(b, TUE, day(bar("AAA", TUE, "100", "101", "99", "100")), None, DAILY_SWITCH)
    assert out.fills == () and out.book.position("AAA").days_held == 501


# ============================================================== stops and take-profits


def test_gap_and_intraday_exits_follow_sim_semantics():
    held = (pos("GAP", 10, "100", stop="95", take="110"), pos("SL", 10, "100", stop="95"), pos("TP", 10, "100", take="104"))
    b = book("0", *held)
    bars = day(
        bar("GAP", TUE, "94", "96", "93", "95"),  # open <= stop -> at the open, days unchanged
        bar("SL", TUE, "97", "98", "95", "96"),  # low <= stop -> at the stop, days + 1
        bar("TP", TUE, "103", "104.01", "102", "104"),  # high > take -> at the take, days + 1
    )
    out = go(b, TUE, bars, None, DAILY_SWITCH)
    got = {t.symbol: (t.exit_reason, t.exit_price, t.days_held) for t in out.trades}
    assert got == {"GAP": ("gap", P("94"), 3), "SL": ("sl", P("95"), 4), "TP": ("tp", P("104"), 4)}
    # fills: open sells first (symbol order), then the intraday sells (symbol order)
    assert [f.symbol for f in out.fills] == ["GAP", "SL", "TP"]


def test_take_at_the_open_and_high_equal_to_take():
    b = book("0", pos("A", 10, "100", take="104"), pos("B", 10, "100", take="104"))
    bars = day(bar("A", TUE, "104", "105", "103", "104"), bar("B", TUE, "103", "104", "102", "103"))
    out = go(b, TUE, bars, None, DAILY_SWITCH)
    assert [(t.symbol, t.exit_reason, t.exit_price) for t in out.trades] == [("A", "tp", P("104"))]


# ============================================================== vol-scaled (unequal) weights


def test_unequal_weights_are_sized_by_their_own_weight():
    bars = day(
        bar("A", TUE, "50", "51", "49", "50"),
        bar("B", TUE, "20", "20.5", "19.8", "20"),
        bar("C", TUE, "1000", "1000", "999", "1000"),
    )
    out = go(new_book(W(10000)), TUE, bars, (T("A", "0.6", "50"), T("B", "0.3", "20"), T("C", "0.1", "1000")), DAILY_SWITCH)
    # A: floor(6000 / (51 × 1.001)) = 117; B: floor(3000 / (20.4 × 1.001)) = 146; C: 1000 < 1020 × 1.001
    assert [(f.symbol, f.shares) for f in out.fills] == [("A", W(117)), ("B", W(146))]
    assert out.rejected == (("C", "too_small"),)


# ============================================================== the idle instrument


def test_idle_target_takes_the_residual_weight_and_is_not_invested():
    bars = day(bar("SPY", TUE, "100", "101", "99", "101"), bar("BIL", TUE, "50", "50.02", "49.99", "50.01"))
    targets = (T("SPY", "0.6", "100"), T("BIL", "0.4", "50"))
    out = go(new_book(W(10000)), TUE, bars, targets, DAILY_SWITCH_TBILL, idle_symbol_ok=True)
    # SPY floor(6000 / 102.102) = 58 at 100; BIL floor(4000 / 51.051) = 78 at 50
    assert [(f.symbol, f.shares, f.price) for f in out.fills] == [("SPY", W(58), P("100")), ("BIL", W(78), P("50"))]
    # cash 10000 − 5805.8 − 3903.9 = 290.3; invested = 58 × 101 only
    assert out.snapshot.cash_usd == P("290.3")
    assert out.snapshot.invested_usd == P("5858")
    assert out.snapshot.equity_usd == P("10049.08")


def test_idle_target_is_ranked_last_and_needs_no_slot():
    r = replace(DAILY_SWITCH_TBILL, id="tbill-one", max_positions=1)
    bars = day(bar("SPY", TUE, "100", "101", "99", "101"), bar("BIL", TUE, "50", "50.02", "49.99", "50.01"))
    out = go(new_book(W(10000)), TUE, bars, (T("BIL", "0.4", "50"), T("SPY", "0.6", "100")), r, idle_symbol_ok=True)
    assert [f.symbol for f in out.fills] == ["SPY", "BIL"]
    assert out.rejected == ()


def test_targeting_the_idle_instrument_needs_the_caller_flag():
    with pytest.raises(ValueError, match="idle instrument"):
        go(new_book(W(10000)), TUE, {}, (T("BIL", "0.4", "50"),), DAILY_SWITCH_TBILL)


def test_idle_position_is_trimmed_even_without_resize():
    b = book("0", pos("SPY", 50, "100"), pos("BIL", 100, "50"))  # equity 10,000
    bars = day(bar("SPY", TUE, "100", "101", "99", "100"), bar("BIL", TUE, "50", "50", "50", "50"))
    out = go(b, TUE, bars, (T("SPY", "0.8", "100"), T("BIL", "0.2", "50")), DAILY_SWITCH_TBILL, idle_symbol_ok=True)
    # BIL desired floor(2000 / 50.05) = 39 -> trim 61; SPY (resize False) is not added to
    assert [(f.symbol, f.side, f.shares, f.reason) for f in out.fills] == [("BIL", "sell", W(61), "trim")]


def test_idle_episode_is_flagged_idle():
    b = book("0", pos("SPY", 50, "100"), pos("BIL", 100, "50"))
    bars = day(bar("SPY", TUE, "100", "101", "99", "100"), bar("BIL", TUE, "50", "50", "50", "50"))
    out = go(b, TUE, bars, (T("SPY", "1", "100"),), DAILY_SWITCH_TBILL)
    (t,) = out.trades
    assert (t.symbol, t.exit_reason, t.idle) == ("BIL", "signal", True)


# ============================================================== cash guard


def test_cash_guard_shrinks_a_buy_cash_cannot_cover():
    # A planned sell (A, no bar on TUE) does not happen, so B's fill finds only 500 in cash.
    b = book("500", pos("A", 50, "10"))
    bars = day(bar("B", TUE, "10.1", "10.2", "10", "10.1"))
    out = go(b, TUE, bars, (T("B", "1", "10"),), DAILY_SWITCH)
    # sized: min(1000, 500 + 499.5) / 10.2102 -> 97; at fill q(10.1 × 97 × 1.001) = 980.6797 > 500
    # -> floor(500 / (10.1 × 1.001)) = 49: q(495.3949)
    (f,) = out.fills
    assert (f.symbol, f.shares, f.cash_usd) == ("B", W(49), P("-495.3949"))
    assert out.snapshot.cash_usd == P("4.6051")
    assert out.book.position("A").exit_pending is True


def test_cash_guard_rejects_when_nothing_fits():
    b = book("0", pos("A", 100, "10"))
    bars = day(bar("B", TUE, "10.1", "10.2", "10", "10.1"))
    out = go(b, TUE, bars, (T("B", "1", "10"),), DAILY_SWITCH)
    assert out.fills == () and out.rejected == (("B", "cash"),)


# ============================================================== close_book_unpriced


def test_close_book_unpriced_sells_at_the_mark():
    b = book("100", pos("A", 10, "20", entry_price="20", days_held=3), pos("B", 5, "40"), last=TUE)
    nb, fills, trades = close_book_unpriced(b, ["A"], DAILY_SWITCH)
    # q(20 × 10 × 0.999) = 199.8; cost q(20 × 10 × 1.001) = 200.2
    (f,) = fills
    assert (f.reason, f.price, f.cash_usd, f.session_date) == ("forced", P("20"), P("199.8"), D(TUE))
    (t,) = trades
    assert (t.exit_reason, t.exit_date, t.days_held, t.pnl_usd) == ("forced", D(TUE), 3, P("-0.4"))
    assert nb.held() == frozenset({"B"})
    assert (nb.cash, nb.equity, nb.last_session) == (P("299.8"), P("499.8"), D(TUE))


def test_close_book_unpriced_checks():
    b = book("100", pos("A", 10, "20"), last=TUE)
    assert close_book_unpriced(b, [], DAILY_SWITCH) == (b, (), ())
    with pytest.raises(ValueError, match="not an open position"):
        close_book_unpriced(b, ["Z"], DAILY_SWITCH)
    with pytest.raises(TypeError):
        close_book_unpriced(b, "A", DAILY_SWITCH)
    with pytest.raises(ValueError, match="before any session"):
        close_book_unpriced(replace(b, last_session=None), ["A"], DAILY_SWITCH)


# ============================================================== P&L reconciles with cash


def test_episode_pnl_reconciles_with_cash_exactly():
    r = TradeRules(id="pnl", engine="book", entry="open_limit", resize=True)
    cash0 = W(10000)
    steps = []
    s = go(
        new_book(cash0),
        MON,
        day(bar("A", MON, "100", "101", "99", "100.5"), bar("B", MON, "40", "40.5", "39.5", "40.2")),
        (T("A", "0.5", "100", stop="90"), T("B", "0.3", "40", take="48")),
        r,
    )
    steps.append(s)
    s = go(
        s.book,
        TUE,
        day(bar("A", TUE, "101", "102", "100", "101"), bar("B", TUE, "40", "41", "39.9", "40.5")),
        (T("A", "0.3", "100.5", stop="90"), T("B", "0.5", "40.2", take="48")),
        r,
        dividends={"A": W("0.37"), "B": W("0.11")},
    )
    steps.append(s)
    s = go(s.book, WED, day(bar("A", WED, "101", "101", "100", "100.5"), bar("B", WED, "45", "48.5", "44", "47")), None, r)
    steps.append(s)
    s = go(s.book, THU, day(bar("A", THU, "99.5", "100", "99", "99.8")), (), r)
    steps.append(s)

    fills = [f for st in steps for f in st.fills]
    trades = [t for st in steps for t in st.trades]
    credited = [amount for st in steps for _, amount in st.dividends]
    assert [f.reason for f in fills] == ["entry", "entry", "trim", "add", "tp", "signal"]
    assert [t.exit_reason for t in trades] == ["tp", "signal"]
    assert len(credited) == 2
    assert s.book.positions == ()
    # Every cash movement belongs to exactly one episode: Σ pnl == Σ fill cash + Σ dividends == Δcash.
    assert sum((t.pnl_usd for t in trades), W(0)) == s.book.cash - cash0
    assert sum((f.cash_usd for f in fills), W(0)) + sum(credited, W(0)) == s.book.cash - cash0
    assert s.snapshot.equity_usd == s.book.cash


# ============================================================== §5 replay: V0_BOOK == size_picks + step


def _tick(x: float | Decimal) -> Decimal:
    """``x`` on a 0.25 price grid, so exact ties (low == limit, low == stop, open == take) occur."""
    d = W(repr(x)) if isinstance(x, float) else x
    return sim.q((d * 4).to_integral_value() / 4)


def _market(seed: int, symbols: dict[str, float], sessions: list[date]) -> dict[date, dict[str, Bar]]:
    rng = random.Random(seed)
    closes = dict(symbols)
    out: dict[date, dict[str, Bar]] = {}
    for i, s in enumerate(sessions):
        bars: dict[str, Bar] = {}
        for sym in sorted(symbols):
            prev = closes[sym]
            o = prev * (1 + rng.gauss(0, 0.012))
            c = prev * (1 + rng.gauss(0.0005, 0.018))
            h = max(o, c) * (1 + abs(rng.gauss(0, 0.008)))
            lo = min(o, c) * (1 - abs(rng.gauss(0, 0.008)))
            closes[sym] = c
            if i > 0 and rng.random() < 0.05:
                continue  # a missing bar
            bars[sym] = Bar(sym, s, _tick(o), _tick(h), _tick(lo), _tick(c), 1_000_000)
        out[s] = bars
    return out


def _picks(bars: dict[str, Bar], order: list[str]) -> list[Pick]:
    out = []
    for sym in order:
        b = bars.get(sym)
        if b is None:
            continue
        c = b.close
        limit, tp, sl = _tick(c * W("0.995")), _tick(c * W("1.015")), _tick(c * W("0.97"))
        if sl < limit < tp:
            out.append(Pick(sym, c, limit, tp, sl))
    return out


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_v0_book_replays_size_picks_and_step(seed):
    sessions = dates.sessions(D("2026-06-01"), D("2026-09-30"))
    symbols = {"AAA": 50.0, "BBB": 120.0, "CCC": 20.0, "DDD": 300.0, "EEE": 75.0, "XPN": 3000.0}
    market = _market(seed, symbols, sessions)
    rng = random.Random(seed + 100)
    cash0 = W("10000")
    pf = new_portfolio(cash0)
    bk = new_book(cash0)
    w = equal_weight(4)
    sim_closed = []
    book_closed = []
    data = market[sessions[0]]
    for s in sessions[1:]:
        order = sorted(symbols)
        rng.shuffle(order)
        picks = _picks(data, order)

        sized = size_picks(pf, picks, s)
        res = step(sized.portfolio, s, market[s])
        pf = res.portfolio
        sim_closed += [
            (e.order.symbol, e.order.fill_date, e.order.fill_price, e.order.exit_date, e.order.exit_price, e.order.exit_reason, e.order.days_held, e.order.pnl_usd)
            for e in res.events
            if e.kind == "exit"
        ]

        held = bk.held()
        targets = tuple(Target(p.symbol, w, p.mark) for p in bk.positions) + tuple(
            Target(p.symbol, w, p.last_price, limit=p.limit_price, stop=p.sl_price, take=p.tp_price)
            for p in picks
            if p.symbol not in held
        )
        out = step_book(bk, s, market[s], targets, V0_BOOK)
        bk = out.book
        book_closed += [
            (t.symbol, t.entry_date, t.entry_price, t.exit_date, t.exit_price, t.exit_reason, t.days_held, t.pnl_usd)
            for t in out.trades
        ]

        assert (out.snapshot.cash_usd, out.snapshot.equity_usd) == (res.snapshot.cash_usd, res.snapshot.equity_usd), s
        assert sorted(o.symbol for o in pf.open_orders()) == sorted(bk.held()), s
        data = market[s]

    assert sorted(book_closed) == sorted(sim_closed)
    assert len(sim_closed) >= 20
    assert {r[5] for r in sim_closed} == {"gap", "sl", "time", "tp"}
