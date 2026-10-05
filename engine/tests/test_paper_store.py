"""paper.store on Postgres: exact save -> load round trips for every engine's state, the day-0
init, orders updated by key, book targets (empty decision included), dividends and applied
splits, and the windowed market (plan phase 6, contract C4)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import psycopg
import pytest

from seer_engine import bars, dates, db, fx
from seer_engine.backtest import io as bio
from seer_engine.fundamentals import EMPTY_PANEL
from seer_engine.paper import store
from seer_engine.paper.benchmark import BenchmarkState
from seer_engine.prices import Bar
from seer_engine.sim import (
    MONTHLY_HOLD,
    Book,
    Pick,
    Position,
    Snapshot,
    Target,
    apply_split,
    close_unpriced,
    size_picks,
    step,
    step_book,
)
from seer_engine.sim.book import BookSnapshot, Fill, Trade

D = Decimal
S0, S1, S2, S3, S4, S5 = (
    date(2026, 9, 28),
    date(2026, 9, 29),
    date(2026, 9, 30),
    date(2026, 10, 1),
    date(2026, 10, 2),
    date(2026, 10, 5),
)
CASH0 = D("1250.0000")
RATE = D("16000.0000")
BOOK_ID = "F4-MOM12-N20-TREND"
TIMING_ID = "F1-SPY-SMA200-M"


def bar(symbol: str, d: date, o: str, h: str, low: str, c: str) -> Bar:
    return Bar(symbol, d, D(o), D(h), D(low), D(c), 1_000)


# --------------------------------------------------------------------------- roster rows


def test_read_strategies_returns_the_roster_rows_in_sort_order(pg):
    rows = store.read_strategies(pg)
    assert [r.id for r in rows] == ["SPY", "A", BOOK_ID, TIMING_ID, "C"]
    spy = rows[0]
    assert (spy.engine, spy.rules_id, spy.is_champion, spy.is_benchmark) == ("benchmark", None, True, True)
    assert rows[1].engine == "bracket" and rows[1].rules_id == "design-v0"
    assert all(r.paper_start is None and r.params == {} for r in rows)
    assert store.read_strategy(pg, "nope") is None


def test_freeze_spec_writes_params_and_start_once_and_check_digest_compares(pg):
    spec = {"engine": "book", "object": "FACTOR", "params": {"rank": "momentum", "top": "20"}}
    gate = {"passed": False, "note": "dev window only"}
    store.freeze_spec(pg, BOOK_ID, spec=spec, digest="abc123", backtest_gate=gate, paper_start=S1)
    row = store.read_strategy(pg, BOOK_ID)
    assert row.paper_start == S1
    assert row.params == {"spec": spec, "digest": "abc123", "backtest_gate": gate}
    store.check_digest(row, "abc123")
    with pytest.raises(store.SpecMismatch):
        store.check_digest(row, "other")
    store.check_digest(store.read_strategy(pg, "A"), "anything")  # not frozen yet: nothing to compare
    with pytest.raises(store.StoreError, match="already frozen"):
        store.freeze_spec(pg, BOOK_ID, spec=spec, digest="x", backtest_gate=gate, paper_start=S2)
    with pytest.raises(store.StoreError, match="no strategies row"):
        store.freeze_spec(pg, "nope", spec=spec, digest="x", backtest_gate=gate, paper_start=S2)
    with pytest.raises(ValueError, match="not an NYSE session"):
        store.freeze_spec(pg, "A", spec=spec, digest="x", backtest_gate=gate, paper_start=date(2026, 10, 3))


# --------------------------------------------------------------------------- day 0 and paper_state


def test_init_paper_state_writes_day0_state_and_snapshot(pg):
    state = store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    assert state == store.read_paper_state(pg, "A")
    assert state == store.PaperState("A", S0, CASH0, CASH0, CASH0, RATE, None, False)
    assert store.read_snapshots(pg, "A") == (Snapshot(S0, CASH0, CASH0),)
    with pytest.raises(psycopg.errors.UniqueViolation):
        store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)


def test_init_refuses_values_the_columns_cannot_hold(pg):
    with pytest.raises(ValueError, match="more decimals"):
        store.init_paper_state(pg, "A", paper_start=S1, cash0=D("1250.00001"), usd_idr=RATE)
    with pytest.raises(TypeError):
        store.init_paper_state(pg, "A", paper_start=S1, cash0=1250.0, usd_idr=RATE)
    assert store.read_paper_state(pg, "A") is None


def test_load_without_state_is_a_store_error(pg):
    with pytest.raises(store.StoreError, match="no paper_state"):
        store.load_portfolio(pg, "A")
    with pytest.raises(store.StoreError, match="no paper_state"):
        store.load_book(pg, BOOK_ID)
    with pytest.raises(store.StoreError, match="no paper_state"):
        store.load_benchmark(pg)
    with pytest.raises(store.StoreError, match="no paper_state"):
        store.write_pending(pg, "A", S1, decision=False)


def test_write_pending_only_accepts_the_next_session(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    with pytest.raises(ValueError, match="next session"):
        store.write_pending(pg, "A", S2, decision=False)
    store.write_pending(pg, "A", S1, decision=False)
    assert store.read_paper_state(pg, "A").pending_session == S1


def test_upsert_snapshot_replaces_the_row_for_a_date(pg):
    store.upsert_snapshot(pg, "A", Snapshot(S1, D("1"), D("2")))
    store.upsert_snapshot(pg, "A", BookSnapshot(S1, D("3.5"), D("4.25"), D("0")))
    store.upsert_snapshot(pg, "A", Snapshot(S0, D("9"), D("9")))
    assert store.read_snapshots(pg, "A") == (Snapshot(S0, D("9"), D("9")), Snapshot(S1, D("3.5"), D("4.25")))


def test_nothing_is_committed(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    pg.rollback()
    assert store.read_paper_state(pg, "A") is None
    assert store.read_snapshots(pg, "A") == ()


# --------------------------------------------------------------------------- bracket


PICKS = (
    Pick("AAA", D("10"), D("10"), D("11"), D("9.5")),
    Pick("BBB", D("20"), D("20"), D("22"), D("19")),
    Pick("CCC", D("30"), D("30"), D("33"), D("28.5")),
)


def _bracket_day0(conn):
    store.init_paper_state(conn, "A", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    pf = store.load_portfolio(conn, "A")
    sized = size_picks(pf, PICKS, S1)
    assert store.insert_pending_orders(conn, "A", sized.placed, {"AAA": "Triple A Inc"}) == 3
    store.write_pending(conn, "A", S1, decision=False)
    return sized


def test_pending_orders_round_trip_with_company_fallback(pg):
    sized = _bracket_day0(pg)
    assert store.load_portfolio(pg, "A") == sized.portfolio
    companies = dict(pg.execute("SELECT symbol, company FROM orders WHERE strategy_id = 'A'").fetchall())
    assert companies == {"AAA": "Triple A Inc", "BBB": "BBB", "CCC": "CCC"}
    assert store.read_paper_state(pg, "A").pending_session == S1


def test_bracket_nights_update_orders_by_key_with_marks(pg):
    sized = _bracket_day0(pg)
    # S1: AAA fills (low < limit), BBB has no bar, CCC's low never goes below the limit.
    r1 = step(
        sized.portfolio,
        S1,
        {"AAA": bar("AAA", S1, "9.9", "10.4", "9.8", "10.2"), "CCC": bar("CCC", S1, "31", "32", "30", "31")},
    )
    store.save_bracket_night(pg, "A", r1.portfolio, r1.events, r1.snapshot)
    assert store.load_portfolio(pg, "A") == r1.portfolio
    st = store.read_paper_state(pg, "A")
    assert (st.last_session, st.cash_usd, st.equity_usd, st.pending_session) == (
        S1, r1.portfolio.cash, r1.portfolio.equity, None
    )
    by_symbol = {o.symbol: (o, mark) for o, mark in store.read_orders(pg, "A")}
    assert by_symbol["AAA"][0].status == "open" and by_symbol["AAA"][1] == D("10.2")
    assert by_symbol["BBB"][0].status == "expired" and by_symbol["BBB"][1] is None
    assert by_symbol["CCC"][0].status == "expired"

    # S2: no event for AAA, but days_held and the mark still move.
    r2 = step(r1.portfolio, S2, {"AAA": bar("AAA", S2, "10.2", "10.5", "10.0", "10.4")})
    assert r2.events == ()
    store.save_bracket_night(pg, "A", r2.portfolio, r2.events, r2.snapshot)
    assert store.load_portfolio(pg, "A") == r2.portfolio
    aaa, mark = next((o, m) for o, m in store.read_orders(pg, "A") if o.symbol == "AAA")
    assert (aaa.days_held, mark) == (2, D("10.4"))

    # S3: a 2-for-1 split executes, then the session steps; the row keeps its key (S1, AAA).
    split_pf, split_events = apply_split(r2.portfolio, "AAA", D(2), S3)
    r3 = step(split_pf, S3, {"AAA": bar("AAA", S3, "5.2", "5.3", "5.1", "5.25")})
    store.save_bracket_night(pg, "A", r3.portfolio, split_events + r3.events, r3.snapshot)
    assert store.load_portfolio(pg, "A") == r3.portfolio
    aaa, mark = next((o, m) for o, m in store.read_orders(pg, "A") if o.symbol == "AAA")
    assert aaa.session_date == S1 and aaa.shares == 2 * sized.placed[0].shares
    assert aaa.fill_price == D("4.9500") and mark == D("5.25")

    # S4: AAA has no bar and never will: forced close at its mark, snapshot replaced.
    r4 = step(r3.portfolio, S4, {})
    forced_pf, forced = close_unpriced(r4.portfolio, ["AAA"])
    snap = Snapshot(S4, forced_pf.cash, forced_pf.equity)
    store.save_bracket_night(pg, "A", forced_pf, r4.events + forced, snap)
    assert store.load_portfolio(pg, "A") == forced_pf
    aaa, mark = next((o, m) for o, m in store.read_orders(pg, "A") if o.symbol == "AAA")
    assert aaa == forced[0].order and mark is None
    assert store.read_snapshots(pg, "A")[-1] == snap
    assert [s.date for s in store.read_snapshots(pg, "A")] == [S0, S1, S2, S3, S4]


def test_save_bracket_night_refuses_a_foreign_snapshot_or_a_missing_row(pg):
    sized = _bracket_day0(pg)
    r1 = step(sized.portfolio, S1, {"AAA": bar("AAA", S1, "9.9", "10.4", "9.8", "10.2")})
    with pytest.raises(ValueError, match="not the state's"):
        store.save_bracket_night(pg, "A", r1.portfolio, r1.events, Snapshot(S1, CASH0, CASH0))
    pg.execute("DELETE FROM orders WHERE symbol = 'BBB'")
    with pytest.raises(store.StoreError, match="expected to change 1 row"):
        store.save_bracket_night(pg, "A", r1.portfolio, r1.events, r1.snapshot)


def test_open_order_without_mark_is_a_store_error(pg):
    sized = _bracket_day0(pg)
    r1 = step(sized.portfolio, S1, {"AAA": bar("AAA", S1, "9.9", "10.4", "9.8", "10.2")})
    store.save_bracket_night(pg, "A", r1.portfolio, r1.events, r1.snapshot)
    pg.execute("UPDATE orders SET mark = NULL WHERE symbol = 'AAA'")
    with pytest.raises(store.StoreError, match="has no mark"):
        store.load_portfolio(pg, "A")


# --------------------------------------------------------------------------- book


TARGETS = (
    Target("AAA", D("0.500000"), D("10")),
    Target("BBB", D("0.250000"), D("20"), limit=D("20.4"), stop=D("18"), take=D("24")),
)


def test_book_decision_and_night_round_trip(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, BOOK_ID, S3, TARGETS)
    loaded = store.load_book(pg, BOOK_ID)
    assert loaded.targets == TARGETS and loaded.pending_session == S3 and not loaded.idle_added
    assert loaded.book.cash == CASH0 and loaded.book.positions == () and loaded.book.last_session == S2

    stepped = step_book(
        loaded.book,
        S3,
        {"AAA": bar("AAA", S3, "10", "10.5", "9.9", "10.3"), "BBB": bar("BBB", S3, "20", "20.5", "19.9", "20.2")},
        loaded.targets,
        MONTHLY_HOLD,
    )
    assert len(stepped.fills) == 2
    store.save_book_night(
        pg, BOOK_ID, stepped.book, stepped.fills, stepped.trades, stepped.snapshot, executed_targets=loaded.targets
    )
    after = store.load_book(pg, BOOK_ID)
    assert after.book == stepped.book
    assert after.targets is None and after.pending_session is None
    assert store.read_book_fills(pg, BOOK_ID) == stepped.fills
    assert store.read_book_targets(pg, BOOK_ID, S3) == TARGETS  # kept as the decision record

    store.save_book_decision(pg, BOOK_ID, S4, None)  # not a decision session
    st = store.read_paper_state(pg, BOOK_ID)
    assert (st.pending_session, st.pending_decision) == (S4, False)
    assert store.load_book(pg, BOOK_ID).targets is None


def test_empty_decision_is_kept_apart_from_no_decision(pg):
    store.init_paper_state(pg, TIMING_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, TIMING_ID, S3, ())
    loaded = store.load_book(pg, TIMING_ID)
    assert loaded.targets == () and loaded.pending_session == S3
    assert store.read_paper_state(pg, TIMING_ID).pending_decision is True


def test_redeciding_a_session_replaces_its_targets_and_idle_is_derived(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, BOOK_ID, S3, TARGETS)
    with_idle = TARGETS[:1] + (Target("BIL", D("0.500000"), D("91.5")),)
    store.save_book_decision(pg, BOOK_ID, S3, with_idle)
    assert store.load_book(pg, BOOK_ID).targets == with_idle
    assert store.load_book(pg, BOOK_ID, idle_symbol="BIL").idle_added is True
    assert store.load_book(pg, BOOK_ID, idle_symbol=None).idle_added is False
    ranks = pg.execute("SELECT rank, symbol FROM book_targets ORDER BY rank").fetchall()
    assert ranks == [(1, "AAA"), (2, "BIL")]


def test_executed_targets_rewrite_the_stored_decision_in_place(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, BOOK_ID, S3, TARGETS)
    pg.execute("UPDATE book_targets SET explanation = 'why' WHERE symbol = 'BBB'")
    # A 2-for-1 split on BBB executed on S3 halved its prices before the step.
    executed = (
        TARGETS[0],
        Target("BBB", D("0.250000"), D("10"), limit=D("10.2"), stop=D("9"), take=D("12")),
    )
    book = Book(cash=CASH0, equity=CASH0, positions=(), last_session=S3)
    store.save_book_night(pg, BOOK_ID, book, (), (), Snapshot(S3, CASH0, CASH0), executed_targets=executed)
    assert store.read_book_targets(pg, BOOK_ID, S3) == executed
    rows = pg.execute(
        "SELECT rank, symbol, explanation FROM book_targets WHERE strategy_id = %s ORDER BY rank", (BOOK_ID,)
    ).fetchall()
    assert rows == [(1, "AAA", None), (2, "BBB", "why")]


def test_executed_targets_must_match_the_stored_decision(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    store.save_book_decision(pg, BOOK_ID, S3, TARGETS)
    book = Book(cash=CASH0, equity=CASH0, positions=(), last_session=S3)
    with pytest.raises(store.StoreError, match="not the stored decision"):
        store.save_book_night(
            pg, BOOK_ID, book, (), (), Snapshot(S3, CASH0, CASH0), executed_targets=TARGETS[::-1]
        )


def test_fractional_book_fills_and_trades_round_trip_in_order(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    positions = (
        Position("BRK.B", D("1.2345"), D("452.2500"), S3, D("450.1000"), 2, D("556.2183"), D("0"), None, None),
        Position("BRKB", D("0.0001"), D("1.0000"), S3, D("1.0000"), 1, D("0.0001"), D("0.1234"), D("0.9"), D("1.5"), True),
    )
    cash = D("700.0001")
    equity = D("1258.2843")
    book = Book(cash=cash, equity=equity, positions=positions, last_session=S3)
    fills = (
        Fill(S3, "ZZZ", "sell", D("3.5"), D("10.0000"), D("34.9650"), D("0.0350"), "signal"),
        Fill(S3, "BRK.B", "buy", D("1.2345"), D("450.1000"), D("-556.2183"), D("0.5556"), "entry"),
        Fill(S3, "BRKB", "buy", D("0.0001"), D("1.0000"), D("-0.0001"), D("0.0000"), "entry"),
    )
    trades = (
        Trade("ZZZ", S1, S3, D("9.0000"), D("10.0000"), 3, D("31.5315"), D("34.9650"), D("3.4335"), "signal", False),
        Trade("BIL", S1, S3, D("91.0000"), D("91.5000"), 3, D("91.0910"), D("91.4085"), D("0.3175"), "signal", True),
    )
    snap = BookSnapshot(S3, cash, equity, D("558.2843"))
    store.save_book_night(pg, BOOK_ID, book, fills, trades, snap)
    assert store.load_book(pg, BOOK_ID).book == book
    assert store.read_book_positions(pg, BOOK_ID) == positions  # Python order: "BRK.B" < "BRKB"
    assert store.read_book_fills(pg, BOOK_ID) == fills
    assert store.read_book_trades(pg, BOOK_ID) == trades
    assert pg.execute("SELECT seq, symbol FROM book_fills ORDER BY seq").fetchall() == [
        (1, "ZZZ"), (2, "BRK.B"), (3, "BRKB")
    ]
    assert store.read_snapshots(pg, BOOK_ID)[-1] == Snapshot(S3, cash, equity)

    # Next session: positions replaced, seq restarts at 1 for the new date.
    book2 = Book(cash=D("1258.2843"), equity=D("1258.2843"), positions=(), last_session=S4)
    fills2 = (Fill(S4, "BRK.B", "sell", D("1.2345"), D("452.2500"), D("557.7008"), D("0.5583"), "forced"),)
    store.save_book_night(pg, BOOK_ID, book2, fills2, (), Snapshot(S4, book2.cash, book2.equity))
    assert store.read_book_positions(pg, BOOK_ID) == ()
    assert store.read_book_fills(pg, BOOK_ID) == fills + fills2
    assert pg.execute("SELECT seq FROM book_fills WHERE session_date = %s", (S4,)).fetchall() == [(1,)]
    with pytest.raises(psycopg.errors.UniqueViolation):  # a session is saved once
        store.save_book_night(pg, BOOK_ID, book2, fills2, (), Snapshot(S4, book2.cash, book2.equity))


def test_book_values_the_columns_cannot_hold_are_refused(pg):
    store.init_paper_state(pg, BOOK_ID, paper_start=S3, cash0=CASH0, usd_idr=RATE)
    p = Position("AAA", D("1.23456"), D("10"), S3, D("10"), 1, D("12.3456"), D("0"), None, None)
    book = Book(cash=D("1"), equity=D("13.3456"), positions=(p,), last_session=S3)
    with pytest.raises(ValueError, match="more decimals"):
        store.save_book_night(pg, BOOK_ID, book, (), (), Snapshot(S3, D("1"), D("13.3456")))


# --------------------------------------------------------------------------- benchmark


def _freeze(conn, strategy_id, paper_start):
    store.freeze_spec(
        conn, strategy_id, spec={"engine": "x"}, digest="d", backtest_gate={"passed": False}, paper_start=paper_start
    )


def test_benchmark_round_trip(pg):
    _freeze(pg, "SPY", S1)
    store.init_paper_state(pg, "SPY", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    day0 = store.load_benchmark(pg)
    assert day0 == BenchmarkState(start=S1, cash=CASH0, equity=CASH0, position=None, last_session=S0)
    holding = Position("SPY", D("2"), D("601.5000"), S1, D("600.0000"), 1, D("1201.2000"), D("0"), None, None)
    state = BenchmarkState(start=S1, cash=D("48.8000"), equity=D("1251.8000"), position=holding, last_session=S1)
    fills = (Fill(S1, "SPY", "buy", D("2"), D("600.0000"), D("-1201.2000"), D("1.2000"), "entry"),)
    store.save_benchmark_night(pg, "SPY", state, Snapshot(S1, state.cash, state.equity), fills)
    assert store.load_benchmark(pg) == state
    assert store.read_book_fills(pg, "SPY") == fills
    assert store.read_snapshots(pg, "SPY") == (Snapshot(S0, CASH0, CASH0), Snapshot(S1, state.cash, state.equity))

    # A session that sells nothing and buys nothing: the holding row is rewritten, no fills.
    marked = BenchmarkState(
        start=S1, cash=D("48.8000"), equity=D("1253.8000"),
        position=Position("SPY", D("2"), D("602.5000"), S1, D("600.0000"), 2, D("1201.2000"), D("0"), None, None),
        last_session=S2,
    )
    store.save_benchmark_night(pg, "SPY", marked, Snapshot(S2, marked.cash, marked.equity), ())
    assert store.load_benchmark(pg) == marked
    assert store.read_book_fills(pg, "SPY") == fills


def test_benchmark_needs_paper_start(pg):
    store.init_paper_state(pg, "SPY", paper_start=S1, cash0=CASH0, usd_idr=RATE)
    with pytest.raises(store.StoreError, match="no paper_start"):
        store.load_benchmark(pg)


# --------------------------------------------------------------------------- dividends and splits


def test_dividends_on_and_between(pg):
    pg.execute(
        "INSERT INTO dividends (symbol, ex_date, amount) VALUES "
        "('SPY', %s, 1.888834), ('AAA', %s, 0.25), ('BBB', %s, 0.1), ('SPY', %s, 1.5)",
        (S3, S3, S3, S5),
    )
    assert store.dividends_on(pg, S3, ["SPY", "AAA", "ZZZ"]) == {"AAA": {S3: D("0.25")}, "SPY": {S3: D("1.888834")}}
    assert list(store.dividends_on(pg, S3, ["SPY", "AAA"])) == ["AAA", "SPY"]
    assert store.dividends_on(pg, S3, ["SPY"]).get("SPY", {}).get(S3) == D("1.888834")
    assert store.dividends_on(pg, S3, []) == {}
    assert store.dividends_on(pg, S4, ["SPY"]) == {}
    assert store.dividends_between(pg, S3, S5) == {
        "AAA": {S3: D("0.25")},
        "BBB": {S3: D("0.1")},
        "SPY": {S3: D("1.888834"), S5: D("1.5")},
    }
    assert store.dividends_between(pg, S4, S4) == {}


def test_applied_splits_only(pg):
    pg.execute(
        "INSERT INTO split_adjustments (symbol, execution_date, split_from, split_to, applied) VALUES "
        "('NVDA', %s, 1, 10, true), ('AAA', %s, 32, 1, true), ('BBB', %s, 1, 2, false), ('CCC', %s, 2, 3, true)",
        (S3, S3, S3, S5),
    )
    assert store.applied_splits_on(pg, S3) == (("AAA", D(1) / D(32)), ("NVDA", D(10)))
    assert store.applied_splits_on(pg, S4) == ()
    assert store.applied_splits_between(pg, S3, S5) == (
        ("AAA", S3, D(1) / D(32)),
        ("CCC", S5, D(3) / D(2)),
        ("NVDA", S3, D(10)),
    )


# --------------------------------------------------------------------------- windowed market


def _seed_market(conn) -> date:
    days = dates.sessions(date(2026, 6, 1), date(2026, 10, 2))
    rows = []
    for i, d in enumerate(days):
        px = D(100) + D(i) / D(4)
        rows.append(bars.make_bar("SPY", d, px, px + 1, px - 1, px + D("0.5"), 1_000_000 + i))
        rows.append(bars.make_bar("AAA", d, px / 2, px / 2 + 1, px / 2 - 1, px / 2, 5_000 + i))
        if d >= date(2026, 9, 1):
            rows.append(bars.make_bar("NEW", d, "50.1234", "51", "49", "50.5", 7))
        if d < date(2026, 7, 1):
            rows.append(bars.make_bar("OLD", d, "5", "6", "4", "5.5", 9))
    with db.transaction(conn, False):
        bars.upsert_bars(conn, rows)
        conn.execute(
            "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) VALUES "
            "('AAA', 'SP500', '2020-01-02', NULL, 'AAA'), ('AAA', 'NDX', '2021-01-04', NULL, 'AAA'), "
            "('OLD', 'SP500', '2020-01-02', '2026-07-01', 'OLD')"
        )
        fx.upsert_fx(conn, [(date(2026, 6, 1), D("16000")), (date(2026, 9, 30), D("16300.5"))])
    return date(2026, 8, 3)


def test_market_window_equals_the_full_load_cut_at_since(pg, tmp_path):
    since = _seed_market(pg)
    full, _ = bio.load_market(pg, cache_dir=tmp_path)
    window = store.load_market_window(pg, since)
    pg.rollback()
    assert list(window.history) == ["AAA", "NEW", "SPY"]  # OLD has no bar on or after since
    cut = np.datetime64(since, "D")
    for symbol, h in window.history.items():
        f = full.history[symbol]
        keep = f.dates >= cut
        assert h.dates.tolist() == f.dates[keep].tolist()
        for col in ("open", "high", "low", "close", "volume"):
            assert getattr(h, col).tolist() == getattr(f, col)[keep].tolist()
        assert window.last_bar_date(symbol) == full.last_bar_date(symbol)
    for d in dates.sessions(since, date(2026, 10, 2)):
        assert window.bars_on(d, ["AAA", "NEW", "SPY"]) == full.bars_on(d, ["AAA", "NEW", "SPY"])
    assert window.membership.intervals == full.membership.intervals
    assert window.fx == full.fx


def test_market_window_since_is_550_calendar_days_back():
    assert store.market_window_since(date(2026, 10, 2)) == date(2026, 10, 2) - timedelta(days=550)


def test_read_bars_frame_default_statement_is_unchanged_and_since_filters(pg, monkeypatch):
    _seed_market(pg)
    statements = []
    real_copy = psycopg.Cursor.copy

    def spy_copy(self, statement, *args, **kwargs):
        statements.append((str(statement), args))
        return real_copy(self, statement, *args, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "copy", spy_copy)
    whole = bio.read_bars_frame(pg)
    part = bio.read_bars_frame(pg, since=date(2026, 9, 1))
    pg.rollback()
    assert statements == [(bio.BARS_COPY_SQL, ()), (bio.BARS_COPY_SINCE_SQL, ((date(2026, 9, 1),),))]
    assert len(part) == int((whole["date"] >= "2026-09-01").sum())
    assert part.reset_index(drop=True).equals(
        whole[whole["date"] >= "2026-09-01"].reset_index(drop=True)
    )
    with pytest.raises(TypeError):
        bio.read_bars_frame(pg, since="2026-09-01")
    pg.rollback()
    with pytest.raises(bio.LoadError):
        bio.read_bars_frame(pg, since=date(2027, 1, 4))


_CIK_AAA = 1000000001


def _seed_facts_for_aaa(conn):
    """One filer behind ``AAA`` and two annual facts for it, so the panel is NON-EMPTY.

    This matters more than it looks. An earlier version of the test below compared the
    window's panel against ``io.load_market``'s without seeding anything, so both sides were
    ``EMPTY_PANEL`` and the assertion was ``0 == 0`` -- it passed with the fix reverted. The
    panel's symbols come from ``ticker_cik``, not from ``bars``, so the map row is the half
    that makes the panel non-empty.
    """
    # Committed via db.transaction, as test_market_fundamentals.py's seed helpers do: an open
    # transaction makes load_market refuse the connection (io.py:143 wants IDLE).
    with db.transaction(conn, False), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ticker_cik (symbol, cik, start_date, end_date, company, source, note) "
            "VALUES ('AAA', %s, '2020-01-02', NULL, 'Triple A Inc.', 'manual', NULL)",
            (_CIK_AAA,),
        )
        cur.executemany(
            "INSERT INTO fundamental_facts "
            "(cik, taxonomy, tag, unit, period_start, period_end, val, accn, fy, fp, form, filed) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                # Assets is a balance-sheet STOCK, so it is tagged instantaneous:
                # period_start == period_end, which is how 005_fundamentals.sql encodes it.
                # Seeding it as a duration makes the ladder refuse it and Snapshot.assets NaN.
                (_CIK_AAA, "us-gaap", "Assets", "USD", date(2025, 12, 31), date(2025, 12, 31),
                 1000.0, "acc-1", 2025, "FY", "10-K", date(2026, 2, 20)),
                (_CIK_AAA, "us-gaap", "StockholdersEquity", "USD", date(2025, 12, 31),
                 date(2025, 12, 31), 400.0, "acc-1", 2025, "FY", "10-K", date(2026, 2, 20)),
            ],
        )


def test_market_window_carries_the_fundamental_panel_not_an_empty_one(pg, tmp_path):
    """The paper night's ``Market`` must carry the panel, not default to ``EMPTY_PANEL``.

    ``load_market_window`` built ``Market(history=..., membership=..., fx=...)`` with no
    ``fundamentals`` argument, so every paper night silently got ``EMPTY_PANEL`` from the
    dataclass default and a ``MarketAware`` allocator would have ranked nobody and reported
    no error. Latent only because ``FND`` is not in ``paper/roster.py``.
    """
    since = _seed_market(pg)
    _seed_facts_for_aaa(pg)
    window = store.load_market_window(pg, since, cache_dir=tmp_path)
    assert window.fundamentals is not EMPTY_PANEL, "the night got the shared empty panel"
    assert "AAA" in window.fundamentals.symbols
    snap = window.fundamentals.as_of("AAA", date(2026, 6, 1))
    assert snap is not None and snap.observations, "the panel carries no usable observations"
    assert snap.assets == 1000.0 and snap.equity == 400.0
    pg.rollback()


def test_market_window_panel_equals_the_full_loads_panel(pg, tmp_path):
    """Windowing the bars must not window the facts: SUE reads quarters behind ``t``."""
    since = _seed_market(pg)
    _seed_facts_for_aaa(pg)
    full, _ = bio.load_market(pg, cache_dir=tmp_path)
    window = store.load_market_window(pg, since, cache_dir=tmp_path)
    assert sorted(window.fundamentals.symbols) == sorted(full.fundamentals.symbols)
    assert window.fundamentals.as_of("AAA", date(2026, 6, 1)).observations == \
        full.fundamentals.as_of("AAA", date(2026, 6, 1)).observations
    pg.rollback()


def test_market_window_panel_is_empty_when_no_facts_are_stored(pg, tmp_path):
    """Production's state: 005 applied, ``fundamental_facts`` deliberately truncated because
    train/eval reads a local Postgres instead. The night must still load.
    """
    since = _seed_market(pg)
    window = store.load_market_window(pg, since, cache_dir=tmp_path)
    assert window.fundamentals is EMPTY_PANEL
    assert list(window.history) == ["AAA", "NEW", "SPY"]
    pg.rollback()
