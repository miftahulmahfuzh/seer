"""SPY benchmark paper nights (plan phase 3, contract C3): ``start_benchmark`` + ``step_benchmark``
looped over a window equal ``buy_and_hold`` with dividends exactly; the persisted shape
(``Position``, ``Fill``); the split rule.

Arithmetic: ``buy_cost(p, n) = q(p × n × 1.001)``; whole shares ``floor(cash / (price × 1.001))``
(``backtest.benchmark._whole_shares``); dividend credit ``q(shares × amount)``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from simkit import D, P, bar

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend, buy_and_hold
from seer_engine.paper.benchmark import (
    SPY,
    BenchmarkState,
    split_benchmark,
    start_benchmark,
    step_benchmark,
)
from seer_engine.prices import Bar
from seer_engine.sim import Fill, Position, Snapshot

# --------------------------------------------------------------------------- synthetic SPY

SESSIONS = dates.sessions(D("2024-01-02"), D("2025-06-30"))
START, END = SESSIONS[0], SESSIONS[-1]
CASH0 = P("1250")


def _spy() -> dict[date, Bar]:
    """A wavy SPY around 100: +0.3 % a session with a -4 % session every 13, so idle cash plus a
    dividend sometimes buys a share and sometimes does not."""
    out: dict[date, Bar] = {}
    prev = 100.0
    for t, d in enumerate(SESSIONS):
        c = prev * 0.96 if t % 13 == 12 else prev * 1.003
        o = prev * (0.998 if t % 2 else 1.002)
        hi = max(o, c) * 1.004
        lo = min(o, c) * 0.996
        out[d] = bar(SPY, d, f"{o:.4f}", f"{hi:.4f}", f"{lo:.4f}", f"{c:.4f}", 50_000_000)
        prev = float(f"{c:.4f}")
    return out


SPY_BARS = _spy()
# Quarterly ex-dates on sessions, one of them on START itself (never credited), amounts large
# enough that the idle cash plus a dividend buys a share at some ex-date closes.
DIVIDENDS = tuple(
    Dividend(d, Decimal(a))
    for d, a in (
        (START, "1.5"),
        (D("2024-03-15"), "1.6"),
        (D("2024-06-21"), "1.75"),
        (D("2024-09-20"), "1.7"),
        (D("2024-12-20"), "1.9"),
        (D("2025-03-21"), "1.7"),
        (D("2025-06-20"), "1.75"),
    )
)
PAID = {d.ex_date: d.amount for d in DIVIDENDS}


def run_nights(spy: dict[date, Bar], start: date, end: date, cash0: Decimal, paid: dict[date, Decimal]):
    state = start_benchmark(cash0, start)
    snaps = [state.snapshot()]
    fills: list[Fill] = []
    states = [state]
    for d in dates.sessions(start, end):
        state, snap, night_fills = step_benchmark(state, d, spy[d], paid.get(d))
        snaps.append(snap)
        fills.extend(night_fills)
        states.append(state)
    return state, tuple(snaps), fills, states


# --------------------------------------------------------------------------- equality with buy_and_hold


def test_window_has_at_least_300_sessions_and_all_ex_dates_are_sessions():
    assert len(SESSIONS) >= 300
    assert all(dates.is_session(d.ex_date) for d in DIVIDENDS)


def test_nights_equal_buy_and_hold_total_return():
    curve = buy_and_hold(SPY_BARS, START, END, CASH0, dividends=DIVIDENDS, name="spy_tr")
    state, snaps, fills, _ = run_nights(SPY_BARS, START, END, CASH0, PAID)
    assert snaps == curve.snapshots
    assert state.shares == curve.shares
    assert state.cash == curve.cash
    assert state.income_usd == curve.dividends_usd
    assert state.equity == curve.snapshots[-1].equity_usd
    # Not vacuous: the start-day dividend is skipped, and reinvestment bought shares.
    assert curve.dividends_usd > 0
    assert [f.reason for f in fills][0] == "entry"
    assert any(f.reason == "add" for f in fills)


def test_every_prefix_equals_buy_and_hold_on_that_prefix():
    _, _, _, states = run_nights(SPY_BARS, START, END, CASH0, PAID)
    for i in range(1, len(states), 37):
        end = states[i].last_session
        curve = buy_and_hold(SPY_BARS, START, end, CASH0, dividends=DIVIDENDS, name="spy_tr")
        assert (states[i].shares, states[i].cash, states[i].equity) == (
            curve.shares, curve.cash, curve.snapshots[-1].equity_usd,
        )


def test_nights_equal_buy_and_hold_price_only():
    curve = buy_and_hold(SPY_BARS, START, END, CASH0, name="spy_price")
    state, snaps, fills, _ = run_nights(SPY_BARS, START, END, CASH0, {})
    assert snaps == curve.snapshots
    assert (state.shares, state.cash) == (curve.shares, curve.cash)
    assert len(fills) == 1


# --------------------------------------------------------------------------- persisted shape, by hand

WEEK = [  # (date, open, close), the week of tests/test_benchmark.py
    ("2026-03-02", "100", "101"),
    ("2026-03-03", "101", "102"),
    ("2026-03-04", "100", "98"),
    ("2026-03-05", "98", "99"),
    ("2026-03-06", "99", "100.5"),
]
WEEK_BARS = {
    D(d): bar(SPY, d, o, str(max(Decimal(o), Decimal(c)) + 1), str(min(Decimal(o), Decimal(c)) - 1), c)
    for d, o, c in WEEK
}
MON, TUE, WED, THU, FRI = (D(d) for d, _, _ in WEEK)


def test_start_state_is_day_zero_cash_only():
    s = start_benchmark(P("1000"), MON)
    assert s == BenchmarkState(start=MON, cash=P("1000"), equity=P("1000"), position=None, last_session=D("2026-02-27"))
    assert s.snapshot() == Snapshot(D("2026-02-27"), P("1000"), P("1000"))
    assert (s.shares, s.income_usd) == (0, P("0"))


def test_position_and_fills_by_hand():
    # MON open 100: floor(1000 / 100.1) = 9 sh, cost q(900.9) = 900.9000, fee q(0.9) = 0.9;
    #   cash 99.1, equity 99.1 + 9 × 101 = 1008.1.
    # WED dividend 2.5: cash + q(22.5) = 121.6; floor(121.6 / 98.098) = 1 sh at close 98,
    #   cost 98.0980 (fee 0.098 -> 0.0980): cash 23.502, 10 sh, equity 23.502 + 980 = 1003.502.
    s = start_benchmark(P("1000"), MON)
    s, snap, fills = step_benchmark(s, MON, WEEK_BARS[MON], None)
    assert snap == Snapshot(MON, P("99.1"), P("1008.1"))
    assert fills == (Fill(MON, SPY, "buy", Decimal(9), P("100"), P("-900.9"), P("0.9"), "entry"),)
    assert s.position == Position(SPY, Decimal(9), P("101"), MON, P("100"), 1, P("900.9"), P("0"), None, None)
    s, snap, fills = step_benchmark(s, TUE, WEEK_BARS[TUE], None)
    assert fills == () and s.position.days_held == 2 and s.position.mark == P("102")
    s, snap, fills = step_benchmark(s, WED, WEEK_BARS[WED], Decimal("2.5"))
    assert snap == Snapshot(WED, P("23.502"), P("1003.502"))
    assert fills == (Fill(WED, SPY, "buy", Decimal(1), P("98"), P("-98.098"), P("0.098"), "add"),)
    assert s.position == Position(SPY, Decimal(10), P("98"), MON, P("100"), 3, P("998.998"), P("22.5"), None, None)
    assert s.income_usd == P("22.5")


def test_dividend_on_start_is_not_credited():
    s = start_benchmark(P("1000"), MON)
    with_div, snap_a, _ = step_benchmark(s, MON, WEEK_BARS[MON], Decimal("2.5"))
    plain, snap_b, _ = step_benchmark(s, MON, WEEK_BARS[MON], None)
    assert (with_div, snap_a) == (plain, snap_b)


def test_reinvestment_can_open_the_holding():
    # 100 USD buys no share at MON's open (100.1 each). WED dividend credits q(0 × 2.5) = 0, but
    # the 100 idle buys floor(100 / 98.098) = 1 sh at the close 98: cost 98.098, cash 1.902.
    curve = buy_and_hold(WEEK_BARS, MON, FRI, P("100"), dividends=[Dividend(WED, Decimal("2.5"))], name="x")
    state, snaps, fills, _ = run_nights(WEEK_BARS, MON, FRI, P("100"), {WED: Decimal("2.5")})
    assert snaps == curve.snapshots
    assert (state.shares, state.cash) == (curve.shares, curve.cash) == (1, P("1.902"))
    assert [f.reason for f in fills] == ["entry"]
    assert state.position.entry_date == WED and state.position.days_held == 3


def test_state_round_trips_through_its_fields():
    # The store rebuilds the state from paper_state + one book_positions row + paper_start.
    s = start_benchmark(P("1000"), MON)
    for d in (MON, TUE, WED):
        s, _, _ = step_benchmark(s, d, WEEK_BARS[d], Decimal("2.5") if d == WED else None)
    p = s.position
    loaded = BenchmarkState(
        start=MON,
        cash=Decimal("23.5020"),
        equity=Decimal("1003.5020"),
        position=Position(p.symbol, Decimal("10.0000"), Decimal("98.0000"), p.entry_date, Decimal("100.0000"),
                          p.days_held, Decimal("998.9980"), Decimal("22.5000"), None, None),
        last_session=WED,
    )
    assert loaded == s
    a = step_benchmark(loaded, THU, WEEK_BARS[THU], None)
    b = step_benchmark(s, THU, WEEK_BARS[THU], None)
    assert a == b


def test_state_validation():
    with pytest.raises(ValueError, match="cash only"):
        BenchmarkState(start=MON, cash=P("1"), equity=P("2"), position=None, last_session=D("2026-02-27"))
    with pytest.raises(ValueError, match="whole shares"):
        BenchmarkState(start=MON, cash=P("1"), equity=P("2"),
                       position=Position(SPY, Decimal("1.5"), P("1"), MON, P("1"), 1, P("1"), P("0"), None, None),
                       last_session=MON)
    with pytest.raises(ValueError, match="holds SPY"):
        BenchmarkState(start=MON, cash=P("1"), equity=P("2"),
                       position=Position("QQQ", Decimal(1), P("1"), MON, P("1"), 1, P("1"), P("0"), None, None),
                       last_session=MON)
    with pytest.raises(ValueError, match="before"):
        BenchmarkState(start=MON, cash=P("1"), equity=P("1"), position=None, last_session=D("2026-02-26"))
    with pytest.raises(ValueError, match="> 0"):
        start_benchmark(P("0"), MON)
    with pytest.raises(TypeError):
        start_benchmark(1000.0, MON)
    with pytest.raises(ValueError, match="not an NYSE session"):
        start_benchmark(P("1000"), D("2026-03-07"))


def test_step_validation():
    s = start_benchmark(P("1000"), MON)
    with pytest.raises(ValueError, match="every session"):
        step_benchmark(s, TUE, WEEK_BARS[TUE], None)
    with pytest.raises(ValueError, match="dated"):
        step_benchmark(s, MON, WEEK_BARS[TUE], None)
    with pytest.raises(ValueError, match="SPY bar"):
        step_benchmark(s, MON, bar("QQQ", MON, "1", "2", "0.5", "1"), None)
    with pytest.raises(ValueError, match="> 0"):
        step_benchmark(s, MON, WEEK_BARS[MON], Decimal("0"))
    with pytest.raises(TypeError):
        step_benchmark(s, MON, WEEK_BARS[MON], 2.5)


# --------------------------------------------------------------------------- splits


def _held_after_tue(cash: str = "1000") -> BenchmarkState:
    s = start_benchmark(P(cash), MON)
    s, _, _ = step_benchmark(s, MON, WEEK_BARS[MON], None)
    s, _, _ = step_benchmark(s, TUE, WEEK_BARS[TUE], None)
    return s


def test_forward_split_rescales_exactly():
    # 9 sh, mark 102, entry 100 -> 2-for-1: 18 sh, mark 51, entry 50, no cash in lieu.
    s = _held_after_tue()
    out, in_lieu = split_benchmark(s, Decimal(2), WED)
    assert in_lieu == P("0")
    assert (out.shares, out.position.mark, out.position.entry_price, out.cash) == (18, P("51"), P("50"), s.cash)
    assert (out.equity, out.last_session) == (s.equity, s.last_session)


def test_reverse_split_pays_the_fraction_in_lieu():
    # 9 sh, 1-for-2 (factor 0.5): floor(4.5) = 4 sh, mark 204; 0.5 sh in lieu q(0.5 × 204) = 102
    # -> cash 99.1 + 102 = 201.1, income 102. Then WED (bar in post-split units, close 196):
    # equity 201.1 + 4 × 196 = 985.1.
    s = _held_after_tue()
    out, in_lieu = split_benchmark(s, Decimal("0.5"), WED)
    assert in_lieu == P("102")
    assert (out.shares, out.position.mark, out.position.entry_price, out.cash, out.income_usd) == (
        4, P("204"), P("200"), P("201.1"), P("102"),
    )
    wed = bar(SPY, WED, "200", "205", "195", "196")
    stepped, snap, fills = step_benchmark(s, WED, wed, None, split=Decimal("0.5"))
    assert fills == ()
    assert snap == Snapshot(WED, P("201.1"), P("985.1"))
    assert stepped.position.mark == P("196") and stepped.position.days_held == 3


def test_split_that_floors_to_zero_pays_everything_in_lieu():
    # 1500 buys floor(1500 / 100.1) = 14 sh at MON's open; 1-for-20: floor(0.7) = 0 sh, all 0.7 sh
    # in lieu at the new mark 102 × 20 = 2040: q(0.7 × 2040) = 1428.
    s = _held_after_tue("1500")
    assert s.shares == 14
    out, in_lieu = split_benchmark(s, Decimal("0.05"), WED)
    assert in_lieu == P("1428")
    assert out.position is None and out.cash == s.cash + P("1428")


def test_split_without_a_holding_and_bad_splits():
    s = start_benchmark(P("1000"), MON)
    assert split_benchmark(s, Decimal(2), MON) == (s, P("0"))
    held = _held_after_tue()
    with pytest.raises(ValueError, match="after the last stepped session"):
        split_benchmark(held, Decimal(2), TUE)
    with pytest.raises(ValueError, match="not a split"):
        split_benchmark(held, Decimal(1), WED)
    with pytest.raises(TypeError):
        split_benchmark(held, 2.0, WED)
