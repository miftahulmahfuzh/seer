"""The backtest loop and the survivorship count (handover §6.4 and §6.7, plan phase 3).

The hand-checked scenario uses ``FixedPicks``, a fake strategy that returns a fixed, ranked
list of picks per ``data_date`` (filtered to the members it is given), so every number below
depends only on the simulator rules and the runner's wiring, not on Strategy A's indicators.
A separate smoke test runs the real ``STRATEGY_A`` through the runner on synthetic bars.

Simulator arithmetic used in the comments (``seer_engine.sim``):

- ``buy_cost(p, n) = q(p * n * 1.001)``, ``sell_proceeds(p, n) = q(p * n * 0.999)``, ``q`` = 4 dp half-up;
  ``pnl = sell_proceeds(exit) - buy_cost(fill)``.
- sizing: ``budget = min(q(equity / 4), cash - Σ buy_cost(limit, shares) of pending)``,
  ``shares = floor(budget / (limit * 1.001))``, lowest free slot, picks in rank order.
- fill when ``low < limit`` at ``min(open, limit)``; intraday SL before TP; ``high > tp`` exits at tp.
- equity = cash + Σ shares × last close.
"""

from __future__ import annotations

from collections.abc import Mapping, Set as AbstractSet
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from simkit import D, P, bar

from seer_engine import dates
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, YearGap, run_backtest, survivorship
from seer_engine.prices import Bar
from seer_engine.sim import Pick, Snapshot
from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A
from seer_engine.strategies.base import History, history_from_bars


def pick(symbol: str, limit: str, tp: str, sl: str) -> Pick:
    return Pick(symbol, P(limit), P(limit), P(tp), P(sl))


class FixedPicks:
    """A fake ``Strategy``: fixed ranked picks per data_date, keeping members only.

    Records every call as ``(entry, data_date, members, latest bar date seen)`` so tests can
    check what the runner passed in.
    """

    id = "FIXED"
    lookback = 1

    def __init__(self, table: Mapping[date, tuple[Pick, ...]]):
        self.table = dict(table)
        self.calls: list[tuple[str, date, frozenset[str], date | None]] = []

    def _picks(self, members: AbstractSet[str], data_date: date) -> list[Pick]:
        return [p for p in self.table.get(data_date, ()) if p.symbol in members]

    def picks(self, history: Mapping[str, History], members: AbstractSet[str],
              data_date: date, params: Any) -> list[Pick]:
        seen = [h.last_date() for h in history.values() if len(h)]
        self.calls.append(("picks", data_date, frozenset(members), max(seen) if seen else None))
        return self._picks(members, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return tuple(sorted(history))

    def picks_prepared(self, prepared: Any, members: AbstractSet[str],
                       data_date: date, params: Any) -> list[Pick]:
        self.calls.append(("prepared", data_date, frozenset(members), None))
        return self._picks(members, data_date)


# --------------------------------------------------------------------------- the scenario
#
# Sessions (March 2025, no holidays): 03-03 (data_date of the first session), then the window
# 03-04, 03-05, 03-06, 03-07, 03-10, 03-11, 03-12, 03-13, 03-14.
# USD/IDR on 03-04 = the 03-03 row, 16000 -> cash0 = q(20,000,000 / 16,000) = 1250.0000.

START, END = D("2025-03-04"), D("2025-03-14")

BARS = {
    "AAA": [
        bar("AAA", "2025-03-03", "10.5", "10.6", "10.1", "10.4"),
        bar("AAA", "2025-03-04", "10.2", "10.5", "9.8", "10.1"),
        bar("AAA", "2025-03-05", "10.3", "11.2", "10.2", "11.0"),
        bar("AAA", "2025-03-06", "11.0", "11.1", "10.9", "11.0"),
    ],
    # BBB's bars end on 03-05: it is gone from 03-06 on (delisted while held).
    "BBB": [
        bar("BBB", "2025-03-03", "20.5", "20.6", "20.1", "20.4"),
        bar("BBB", "2025-03-04", "19.5", "20.5", "19.0", "20.0"),
        bar("BBB", "2025-03-05", "20.0", "20.4", "19.8", "20.2"),
    ],
    "CCC": [
        bar("CCC", "2025-03-05", "51.0", "51.5", "50.5", "51.0"),
        bar("CCC", "2025-03-06", "49.8", "50.5", "49.5", "50.2"),
        bar("CCC", "2025-03-07", "50.5", "51.0", "50.0", "50.8"),
        bar("CCC", "2025-03-10", "50.0", "50.5", "44.0", "46.0"),
        bar("CCC", "2025-03-11", "46.0", "47.0", "45.5", "46.5"),
    ],
    # DDD: no bar on 03-11, 03-12, 03-13 (a three-session halt), bars resume 03-14.
    "DDD": [
        bar("DDD", "2025-03-06", "5.2", "5.3", "5.1", "5.2"),
        bar("DDD", "2025-03-07", "5.1", "5.2", "5.05", "5.15"),
        bar("DDD", "2025-03-10", "5.0", "5.1", "4.9", "4.95"),
        bar("DDD", "2025-03-14", "5.2", "5.5", "5.1", "5.4"),
        bar("DDD", "2025-03-17", "5.4", "5.6", "5.3", "5.5"),
    ],
}

INTERVALS = (
    ("AAA", D("2020-01-02"), None),
    ("AAA", D("2024-06-03"), None),  # also in the other index: unioned
    ("BBB", D("2020-01-02"), D("2025-03-06")),
    ("CCC", D("2020-01-02"), D("2025-03-07")),  # leaves the index while held
    ("DDD", D("2025-03-06"), None),  # joins on 03-06: a member for data_date 03-06, not 03-05
    ("EEE", D("2020-01-02"), None),  # never has bars
)

FX = (
    (D("2025-02-27"), Decimal("15000")),
    (D("2025-03-03"), Decimal("16000")),
    (D("2025-03-05"), Decimal("17000")),  # after the start: never used
)

TABLE = {
    # data_date 03-03 -> session 03-04
    D("2025-03-03"): (pick("AAA", "10", "11", "9"), pick("BBB", "20", "22", "18")),
    # data_date 03-04 -> session 03-05: no picks
    # data_date 03-05 -> session 03-06: BBB is held (rejected), DDD is not a member on 03-05
    D("2025-03-05"): (pick("BBB", "20", "22", "18"), pick("CCC", "50", "55", "45"), pick("DDD", "5", "6", "4")),
    # data_date 03-06 -> session 03-07: DDD (expires), EEE too dear for one share
    D("2025-03-06"): (pick("DDD", "5", "6", "4"), pick("EEE", "400", "450", "350")),
    # data_date 03-07 -> session 03-10: DDD again (fills)
    D("2025-03-07"): (pick("DDD", "5", "6", "4"),),
}


def scenario_market() -> Market:
    return Market(
        history={s: history_from_bars(s, b) for s, b in sorted(BARS.items())},
        membership=Membership(INTERVALS),
        fx=FX,
    )


def run_scenario(prepared: bool = False) -> tuple[RunResult, FixedPicks]:
    market = scenario_market()
    strategy = FixedPicks(TABLE)
    prep = strategy.prepare(market.history) if prepared else None
    return run_backtest(market, strategy, None, START, END, prepared=prep), strategy


def test_scenario_final_cash_equity_and_trades():
    r, _ = run_scenario()
    assert r.strategy_id == "FIXED"
    assert (r.start, r.end) == (START, END)
    assert r.usd_idr == Decimal("16000")
    assert r.initial_cash == Decimal("1250.0000")

    # 03-04: slot budget q(1250/4) = 312.5.
    #   AAA: floor(312.5 / 10.01) = 31 sh; committed buy_cost(10, 31) = 310.31.
    #   BBB: min(312.5, 1250 - 310.31) = 312.5 -> floor(312.5 / 20.02) = 15 sh.
    #   AAA low 9.8 < 10 fills at min(10.2, 10) = 10: cost q(310 * 1.001) = 310.3100.
    #   BBB low 19 < 20 fills at min(19.5, 20) = 19.5: cost q(292.5 * 1.001) = 292.7925.
    #   cash 1250 - 310.31 - 292.7925 = 646.8975; equity + 31*10.1 + 15*20 = 1259.9975.
    # 03-05: no picks. AAA high 11.2 > tp 11 -> exit at 11 (days 2): q(341 * 0.999) = 340.6590,
    #   pnl 340.659 - 310.31 = 30.3490. BBB stays (sl 18, tp 22), mark 20.2.
    #   cash 987.5565; equity + 15*20.2 = 1290.5565.
    # 03-06: slot budget q(1290.5565/4) = 322.6391. BBB held -> rejected 'held'; CCC:
    #   floor(322.6391 / 50.05) = 6 sh in slot 1; DDD not a member on 03-05 -> never offered.
    #   BBB has no bar (days 3). CCC low 49.5 < 50 fills at 49.8: cost q(298.8 * 1.001) = 299.0988.
    #   cash 688.4577. BBB's last bar (03-05) < 03-06 -> close_unpriced at mark 20.2:
    #   q(303 * 0.999) = 302.6970, pnl 302.697 - 292.7925 = 9.9045, reason time, forced.
    #   cash 991.1547; equity + 6*50.2 = 1292.3547 (the replaced snapshot).
    # 03-07: slot budget q(1292.3547/4) = 323.0887. DDD: floor(323.0887 / 5.005) = 64 sh, slot 2;
    #   EEE: floor(323.0887 / 400.4) = 0 -> 'lt_one_share'. DDD low 5.05 is not < 5 -> expires.
    #   CCC stays (days 2), mark 50.8. cash 991.1547; equity + 6*50.8 = 1295.9547.
    # 03-10: slot budget q(1295.9547/4) = 323.9887 -> DDD floor(323.9887 / 5.005) = 64 sh, slot 2.
    #   CCC low 44 <= sl 45 -> exit at 45 (days 3): q(270 * 0.999) = 269.7300,
    #   pnl 269.73 - 299.0988 = -29.3688. DDD low 4.9 < 5 fills at min(5.0, 5) = 5: cost 320.3200.
    #   cash 991.1547 + 269.73 - 320.32 = 940.5647; equity + 64*4.95 = 1257.3647.
    # 03-11, 03-12, 03-13: DDD has no bar (halt): no event, no forced close (it has a later bar),
    #   days 2, 3, 4, mark 4.95. equity 1257.3647.
    # 03-14: DDD bar back, days_held 4 < 5, o 5.2 h 5.5 l 5.1: no exit; days 5, mark 5.4.
    #   cash 940.5647; equity + 64*5.4 = 1286.1647. Open at the end, never liquidated.
    assert r.snapshots == (
        Snapshot(D("2025-03-03"), P("1250"), P("1250")),
        Snapshot(D("2025-03-04"), P("646.8975"), P("1259.9975")),
        Snapshot(D("2025-03-05"), P("987.5565"), P("1290.5565")),
        Snapshot(D("2025-03-06"), P("991.1547"), P("1292.3547")),
        Snapshot(D("2025-03-07"), P("991.1547"), P("1295.9547")),
        Snapshot(D("2025-03-10"), P("940.5647"), P("1257.3647")),
        Snapshot(D("2025-03-11"), P("940.5647"), P("1257.3647")),
        Snapshot(D("2025-03-12"), P("940.5647"), P("1257.3647")),
        Snapshot(D("2025-03-13"), P("940.5647"), P("1257.3647")),
        Snapshot(D("2025-03-14"), P("940.5647"), P("1286.1647")),
    )

    trades = [
        (o.symbol, o.shares, o.fill_date, o.fill_price, o.exit_date, o.exit_price, o.exit_reason,
         o.days_held, o.pnl_usd)
        for o in r.closed
    ]
    assert trades == [
        ("AAA", 31, D("2025-03-04"), P("10"), D("2025-03-05"), P("11"), "tp", 2, P("30.349")),
        ("BBB", 15, D("2025-03-04"), P("19.5"), D("2025-03-06"), P("20.2"), "time", 3, P("9.9045")),
        ("CCC", 6, D("2025-03-06"), P("49.8"), D("2025-03-10"), P("45"), "sl", 3, P("-29.3688")),
    ]
    # Cash reconciles: cash0 + Σ pnl - buy cost of what is still open.
    assert r.snapshots[-1].cash_usd == r.initial_cash + sum(o.pnl_usd for o in r.closed) - P("320.32")

    assert [(o.symbol, o.shares, o.slot, o.fill_price, o.days_held) for o in r.open_at_end] == [
        ("DDD", 64, 2, P("5"), 5)
    ]
    assert r.rejections == (("held", 1), ("lt_one_share", 1))

    kinds = [(e.session_date, e.kind, e.order.symbol, e.forced) for e in r.events]
    assert kinds == [
        (D("2025-03-04"), "fill", "AAA", False),
        (D("2025-03-04"), "fill", "BBB", False),
        (D("2025-03-05"), "exit", "AAA", False),
        (D("2025-03-06"), "fill", "CCC", False),
        (D("2025-03-06"), "exit", "BBB", True),
        (D("2025-03-07"), "expire", "DDD", False),
        (D("2025-03-10"), "exit", "CCC", False),
        (D("2025-03-10"), "fill", "DDD", False),
    ]


def test_gone_symbol_is_force_closed_exactly_once_at_the_first_session_after_its_last_bar():
    r, _ = run_scenario()
    forced = [e for e in r.events if e.forced]
    assert len(forced) == 1
    assert forced[0].order.symbol == "BBB"
    assert forced[0].session_date == D("2025-03-06")  # next_session(03-05), BBB's last bar
    assert forced[0].order.exit_reason == "time"
    # The halted DDD (no bars 03-11..03-13, back on 03-14) is never force-closed.
    assert not [e for e in r.events if e.order.symbol == "DDD" and e.kind == "exit"]


def test_members_are_taken_on_data_date_and_history_is_cut_at_data_date():
    _, strategy = run_scenario()
    sessions = dates.sessions(START, END)
    data_dates = [dates.prev_session(START)] + sessions[:-1]
    assert [c[1] for c in strategy.calls] == data_dates
    assert all(c[0] == "picks" for c in strategy.calls)
    members = {c[1]: c[2] for c in strategy.calls}
    assert members[D("2025-03-05")] == frozenset({"AAA", "BBB", "CCC", "EEE"})  # DDD joins 03-06
    assert members[D("2025-03-06")] == frozenset({"AAA", "CCC", "DDD", "EEE"})  # BBB left 03-06
    assert members[D("2025-03-07")] == frozenset({"AAA", "DDD", "EEE"})  # CCC left 03-07
    # No look-ahead: no history handed to the strategy reaches past data_date.
    for _, data_date, _, latest in strategy.calls:
        assert latest is not None and latest <= data_date


def test_prepared_run_equals_unprepared_and_runs_repeat_identically():
    plain, _ = run_scenario()
    prepped, strategy = run_scenario(prepared=True)
    assert all(c[0] == "prepared" for c in strategy.calls)
    assert prepped == plain
    again, _ = run_scenario()
    assert again == plain


def test_initial_idr_and_a_window_of_one_session():
    market = scenario_market()
    r = run_backtest(market, FixedPicks(TABLE), None, START, START, initial_idr=Decimal("16000000"))
    # 16,000,000 / 16,000 = 1000; AAA floor(250 / 10.01) = 24, BBB floor(250 / 20.02) = 12.
    # AAA fills at 10: q(240 * 1.001) = 240.24; BBB at 19.5: q(234 * 1.001) = 234.234.
    # cash 1000 - 240.24 - 234.234 = 525.526; equity + 24*10.1 + 12*20 = 1007.926.
    assert r.initial_cash == P("1000")
    assert r.snapshots == (
        Snapshot(D("2025-03-03"), P("1000"), P("1000")),
        Snapshot(D("2025-03-04"), P("525.526"), P("1007.926")),
    )
    assert r.closed == ()
    assert [o.symbol for o in r.open_at_end] == ["AAA", "BBB"]


def test_run_rejects_bad_windows_and_missing_fx():
    market = scenario_market()
    with pytest.raises(ValueError):
        run_backtest(market, FixedPicks(TABLE), None, D("2025-03-08"), END)  # a Saturday
    with pytest.raises(ValueError):
        run_backtest(market, FixedPicks(TABLE), None, START, D("2025-03-09"))  # a Sunday
    with pytest.raises(ValueError):
        run_backtest(market, FixedPicks(TABLE), None, END, START)
    no_fx = Market(history=market.history, membership=market.membership, fx=((D("2025-03-05"), Decimal("1")),))
    with pytest.raises(ValueError):
        run_backtest(no_fx, FixedPicks(TABLE), None, START, END)


def test_initial_idr_default():
    assert INITIAL_IDR == Decimal("20000000")


# --------------------------------------------------------------------------- survivorship


def test_survivorship_counts_member_sessions_without_a_bar_per_year():
    # Sessions 2024-12-30, 2024-12-31, 2025-01-02, 2025-01-03 (01-01 is a holiday).
    bars = {
        "AAA": [bar("AAA", d, 1, 1, 1, 1) for d in ("2024-12-30", "2024-12-31", "2025-01-02", "2025-01-03")],
        "GAP": [bar("GAP", d, 1, 1, 1, 1) for d in ("2024-12-30", "2025-01-03")],
        "LFT": [bar("LFT", "2024-12-30", 1, 1, 1, 1)],
        "SPY": [bar("SPY", "2024-12-30", 1, 1, 1, 1)],  # bars, never a member: ignored
    }
    intervals = (
        ("AAA", D("2020-01-02"), None),
        ("AAA", D("2024-01-02"), None),  # both indices: counted once per session
        ("GAP", D("2020-01-02"), None),
        ("GON", D("2024-12-31"), D("2025-01-03")),  # never fetched; member 12-31 and 01-02
        ("LFT", D("2024-12-01"), D("2024-12-31")),  # member on 12-30 only, has that bar
        ("OLD", D("2010-01-04"), D("2015-01-02")),  # never fetched, but not a member in the window
    )
    market = Market(
        history={s: history_from_bars(s, b) for s, b in sorted(bars.items())},
        membership=Membership(intervals),
        fx=(),
    )
    # 2024: pairs AAA 2 + GAP 2 + GON 1 + LFT 1 = 6; missing GON 12-31 (never), GAP 12-31 (other).
    # 2025: pairs AAA 2 + GAP 2 + GON 1 (01-03 is its end, exclusive) = 5;
    #       missing GON 01-02 (never), GAP 01-02 (other).
    assert survivorship(market, D("2024-12-30"), D("2025-01-03")) == (
        YearGap(year=2024, member_sessions=6, missing=2, missing_never_fetched=1, missing_other=1),
        YearGap(year=2025, member_sessions=5, missing=2, missing_never_fetched=1, missing_other=1),
    )
    assert survivorship(market, D("2025-01-04"), D("2025-01-05")) == ()  # a weekend


# --------------------------------------------------------------------------- Strategy A smoke


def _smoke_bars(symbol: str, sessions: list[date], phase: int) -> list[Bar]:
    """An uptrend (+0.4 % a session) with two -3 % sessions every 20 (shifted by ``phase``), and a
    deep intraday low the session after, so Strategy A's setup (close > SMA200, RSI(2) < 10,
    dollar volume ~1e8 > 2e7) fires and its limit fills. Prices are rounded to 4 dp first, so the
    float64 History holds exactly what ``bars`` would."""
    out = []
    prev = 100.0 + phase
    for t, d in enumerate(sessions):
        k = (t + phase) % 20
        c = prev * 0.97 if k in (17, 18) else prev * 1.004
        o = prev
        lo = min(o, c) * (0.97 if k == 19 else 0.995)
        hi = max(o, c) * 1.005
        out.append(bar(symbol, d, f"{o:.4f}", f"{hi:.4f}", f"{lo:.4f}", f"{c:.4f}", 1_000_000))
        prev = float(f"{c:.4f}")
    return out


def test_strategy_a_smoke_prepared_equals_plain():
    sessions = dates.sessions(D("2024-01-02"), D("2025-03-31"))
    history = {
        s: history_from_bars(s, _smoke_bars(s, sessions, phase))
        for s, phase in (("UPA", 0), ("UPB", 7), ("UPC", 13))
    }
    market = Market(
        history=history,
        membership=Membership(tuple((s, D("2020-01-02"), None) for s in sorted(history))),
        fx=((D("2023-12-29"), Decimal("16000")),),
    )
    start, end = sessions[200], sessions[-1]  # data_date sessions[199] has exactly 200 bars
    plain = run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end)
    prepped = run_backtest(
        market, STRATEGY_A, DESIGN_PARAMS, start, end, prepared=STRATEGY_A.prepare(market.history)
    )
    assert prepped == plain
    assert run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end) == plain
    assert plain.strategy_id == "A"
    assert len(plain.snapshots) == len(dates.sessions(start, end)) + 1
    assert any(e.kind == "fill" for e in plain.events)
    assert {o.symbol for o in plain.closed} <= {"UPA", "UPB", "UPC"}
