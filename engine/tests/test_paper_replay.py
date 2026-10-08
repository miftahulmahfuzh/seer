"""paper.replay: the pure half of the replay check (plan phase 8).

An in-memory market (AAA, BBB, SPY on 2025-02-18..2025-03-14), a fixed-pick fake strategy for
the bracket engine and ``allocatorkit.FIXED`` under ``MONTHLY_HOLD`` for the book engine. The
market's own fx (15000) differs from the stored rate (16000), so a bracket replay that ignored
the stored rate would show. Every expected record is checked against the runner it wraps.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from allocatorkit import FIXED, FixedParams
from simkit import D, P, bar
from test_paper_book import BREATHE, SPLIT_END, SPLIT_RULES, split_market, split_paper_run

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend, buy_and_hold
from seer_engine.backtest.book_runner import run_book
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import run_backtest
from seer_engine.paper import replay
from seer_engine.paper.capital import PAPER_INITIAL_IDR
from seer_engine.paper.replay import (
    CheckResult,
    Difference,
    Holding,
    PaperHead,
    Records,
)
from seer_engine.prices import Bar
from seer_engine.sim import (
    MONTHLY_HOLD,
    MONTHLY_RANK_WEEKLY_RESIZE,
    Pick,
    Portfolio,
    Snapshot,
    Trade,
    initial_cash_usd,
    is_resize_session,
    size_picks,
)
from seer_engine.strategies.base import History, history_from_bars

FIRST, LAST_BAR = D("2025-02-18"), D("2025-03-14")
USD_IDR = Decimal("16000")
CASH0 = initial_cash_usd(PAPER_INITIAL_IDR, USD_IDR)  # 625.0000: the paper books start with 10,000,000 IDR


def _bars(symbol: str, special: Mapping[str, tuple[str, str, str, str]], default: tuple[str, str, str, str]) -> list[Bar]:
    return [bar(symbol, d, *special.get(d.isoformat(), default)) for d in dates.sessions(FIRST, LAST_BAR)]


AAA = _bars(
    "AAA",
    {
        "2025-03-04": ("10.4", "10.5", "9.8", "10.1"),  # the bracket limit 10 fills (low < limit)
        "2025-03-05": ("10.1", "10.3", "10.0", "10.2"),
        "2025-03-10": ("10.4", "11.2", "10.3", "11.0"),
    },
    ("10.4", "10.6", "10.1", "10.4"),
)
BBB = _bars("BBB", {}, ("21", "21.2", "20.8", "21"))  # a limit of 20 never fills
SPY_BARS = _bars("SPY", {"2025-03-04": ("500", "503", "499", "502")}, ("501", "502", "500", "501"))


def market() -> Market:
    return Market(
        history={
            "AAA": history_from_bars("AAA", AAA),
            "BBB": history_from_bars("BBB", BBB),
            "SPY": history_from_bars("SPY", SPY_BARS),
        },
        membership=Membership((("AAA", D("2020-01-02"), None), ("BBB", D("2020-01-02"), None))),
        fx=((D("2025-01-02"), Decimal("15000")),),
    )


def pick(symbol: str, limit: str, tp: str, sl: str) -> Pick:
    return Pick(symbol, P(limit), P(limit), P(tp), P(sl))


class FixedPicks:
    """A fake ``Strategy``: fixed ranked picks per data_date, members only."""

    id = "FIXED"
    lookback = 1

    def __init__(self, table: Mapping[date, tuple[Pick, ...]]):
        self.table = dict(table)

    def _picks(self, members: AbstractSet[str], data_date: date) -> list[Pick]:
        return [p for p in self.table.get(data_date, ()) if p.symbol in members]

    def picks(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date, params: Any) -> list[Pick]:
        return self._picks(members, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return None

    def picks_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date, params: Any) -> list[Pick]:
        return self._picks(members, data_date)


PICKS = FixedPicks(
    {
        D("2025-03-03"): (pick("AAA", "10", "11", "9"),),  # -> 03-04: fills, open at the end
        D("2025-03-05"): (pick("BBB", "20", "22", "18"),),  # -> 03-06: expires
        D("2025-03-07"): (pick("AAA", "10", "11", "9"), pick("BBB", "20", "22", "18")),  # -> 03-10: AAA held, BBB pending
    }
)
FIXED_PARAMS = FixedParams(weights=(("AAA", Decimal("0.5")), ("BBB", Decimal("0.4"))))
DIVIDENDS = {"AAA": {D("2025-03-05"): Decimal("0.25")}, "SPY": {D("2025-03-05"): Decimal("1.5")}}

BRACKET_HEAD = PaperHead("A", "bracket", D("2025-03-04"), D("2025-03-07"), USD_IDR)
BOOK_HEAD = PaperHead("F", "book", D("2025-02-26"), D("2025-03-05"), USD_IDR)
SPY_HEAD = PaperHead("SPY", "benchmark", D("2025-03-03"), D("2025-03-07"), USD_IDR)


def _bracket(head: PaperHead = BRACKET_HEAD) -> Records:
    return replay.expected_bracket(market(), PICKS, None, head)


def _book(head: PaperHead = BOOK_HEAD) -> Records:
    return replay.expected_book(market(), FIXED, FIXED_PARAMS, MONTHLY_HOLD, head, DIVIDENDS)


def _benchmark(head: PaperHead = SPY_HEAD, cost_model: str = "flat") -> Records:
    return replay.expected_benchmark(market(), head, DIVIDENDS, cost_model=cost_model)


# ---- expected records --------------------------------------------------------------------------


def test_expected_bracket_is_run_backtest_at_the_stored_rate():
    m = market()
    got = _bracket()
    fixed = Market(history=m.history, membership=m.membership, fx=((BRACKET_HEAD.paper_start, USD_IDR),))
    run = run_backtest(
        fixed, PICKS, None, BRACKET_HEAD.paper_start, BRACKET_HEAD.last_session, initial_idr=PAPER_INITIAL_IDR
    )
    assert got.snapshots == run.snapshots
    assert got.initial_cash == CASH0 == run.initial_cash
    assert (got.cash, got.equity) == (run.snapshots[-1].cash_usd, run.snapshots[-1].equity_usd)
    assert got.pending_session == D("2025-03-10")
    assert {(o.session_date, o.symbol): o.status for o in got.orders} == {
        (D("2025-03-04"), "AAA"): "open",
        (D("2025-03-06"), "BBB"): "expired",
        (D("2025-03-10"), "BBB"): "pending",
    }
    assert got.marks == (("AAA", P("10.4")),)
    end = Portfolio(
        cash=got.cash, equity=got.equity, orders=run.open_at_end, marks=got.marks, last_session=BRACKET_HEAD.last_session
    )
    direct = size_picks(
        end,
        PICKS.picks({}, m.membership.members_on(BRACKET_HEAD.last_session), BRACKET_HEAD.last_session, None),
        D("2025-03-10"),
    )
    assert tuple(o for o in got.orders if o.status == "pending") == direct.portfolio.pending_orders()


def test_expected_bracket_first_night_is_day0_plus_the_first_decision():
    got = _bracket(replace(BRACKET_HEAD, last_session=D("2025-03-03")))
    assert got.snapshots == (Snapshot(D("2025-03-03"), CASH0, CASH0),)
    assert [(o.session_date, o.symbol, o.status) for o in got.orders] == [(D("2025-03-04"), "AAA", "pending")]
    assert got.marks == ()
    assert (got.cash, got.equity, got.pending_session) == (CASH0, CASH0, D("2025-03-04"))


def test_expected_book_is_run_book_with_every_decision():
    m = market()
    got = _book()
    run = run_book(
        m, FIXED, FIXED_PARAMS, MONTHLY_HOLD, BOOK_HEAD.paper_start, BOOK_HEAD.last_session, dividends=DIVIDENDS, usd_idr=USD_IDR,
        initial_idr=PAPER_INITIAL_IDR,
    )
    assert got.snapshots == tuple(Snapshot(s.date, s.cash_usd, s.equity_usd) for s in run.snapshots)
    assert got.fills == run.fills and len(got.fills) == 2
    assert got.trades == run.trades
    assert got.positions == run.open_at_end
    assert {p.symbol for p in got.positions} == {"AAA", "BBB"}
    assert run.dividends_usd == P("7.25")  # half the shares of a 20,000,000 IDR book: 10,000,000 since 2026-10-07
    assert [s for s, _ in got.targets] == [D("2025-03-03")]  # the first session of March only
    assert [t.symbol for t in got.targets[0][1]] == ["AAA", "BBB"]
    assert got.pending_session == D("2025-03-06") and got.pending_decision is False
    assert got.initial_cash == CASH0


def test_expected_book_pending_decision_on_the_night_before_a_decision_session():
    got = _book(replace(BOOK_HEAD, last_session=D("2025-02-28")))
    assert got.pending_session == D("2025-03-03")
    assert got.pending_decision is True
    assert [s for s, _ in got.targets] == [D("2025-03-03")]
    assert got.positions == () and got.fills == ()


def test_expected_book_first_night():
    got = _book(replace(BOOK_HEAD, last_session=D("2025-02-25")))
    assert got.snapshots == (Snapshot(D("2025-02-25"), CASH0, CASH0),)
    assert got.targets == () and got.pending_decision is False  # 2025-02-26 is no monthly decision


def test_expected_benchmark_is_buy_and_hold_with_spy_dividends():
    m = market()
    got = _benchmark()
    curve = buy_and_hold(
        m.spy(), SPY_HEAD.paper_start, SPY_HEAD.last_session, CASH0,
        dividends=(Dividend(D("2025-03-05"), Decimal("1.5")),), name="SPY", fractional=True,
    )
    # A $625 book buys about 1.25 SPY shares (fractional since 2026-10-07): nearly all of it
    # invested, the dividend credited on that holding and reinvested at the ex-date close.
    assert curve.dividends_usd == P("1.8693")
    assert got.snapshots == curve.snapshots
    assert got.cash == curve.cash == P("0.0432")
    assert got.holdings == (Holding("SPY", curve.shares, P("501")),)
    assert curve.shares == P("1.2499")


def test_expected_benchmark_replays_at_the_entrys_own_cost_model():
    """SPY-GT's first night: the live buy paid Gotrade's fee, the replay assumed the flat rate.

    ``expected_benchmark`` defaulted ``cost_model`` away, so a Gotrade benchmark was reconstructed
    at 0.1% and ``paper_check`` reported a mismatch against a correct run (stored 0.7207 shares and
    0.0393 cash, replay 0.7217 and 0.0736). Each model must replay as ``buy_and_hold`` prices it,
    and the two must differ -- without the second assertion this test passes on the bug.
    """
    m = market()
    for model in ("flat", "gotrade"):
        curve = buy_and_hold(
            m.spy(), SPY_HEAD.paper_start, SPY_HEAD.last_session, CASH0,
            dividends=(Dividend(D("2025-03-05"), Decimal("1.5")),), name="SPY", fractional=True,
            cost_model=model,
        )
        got = _benchmark(cost_model=model)
        assert got.cash == curve.cash, model
        assert got.holdings == (Holding("SPY", curve.shares, P("501")),), model
    assert _benchmark(cost_model="flat").cash != _benchmark(cost_model="gotrade").cash


def test_expected_benchmark_first_night_holds_cash_only():
    got = _benchmark(replace(SPY_HEAD, last_session=D("2025-02-28")))
    assert got.snapshots == (Snapshot(D("2025-02-28"), CASH0, CASH0),)
    assert got.holdings == () and got.cash == CASH0


def test_held_before_rebuilds_the_held_set_from_fills():
    fills = _book().fills
    assert replay.held_before(fills, D("2025-03-03")) == frozenset()
    assert replay.held_before(fills, D("2025-03-04")) == frozenset({"AAA", "BBB"})


def test_last_close_is_the_latest_bar_on_or_before():
    m = market()
    assert replay.last_close(m, "AAA", D("2025-03-04")) == P("10.1")
    assert replay.last_close(m, "AAA", D("2025-03-08")) == P("10.4")  # Saturday: Friday's close
    with pytest.raises(ValueError, match="no bar"):
        replay.last_close(m, "CCC", D("2025-03-04"))


def test_wrong_engine_is_refused():
    with pytest.raises(ValueError, match="not bracket"):
        replay.expected_bracket(market(), PICKS, None, BOOK_HEAD)
    with pytest.raises(ValueError, match="not book"):
        replay.expected_book(market(), FIXED, FIXED_PARAMS, MONTHLY_HOLD, SPY_HEAD, DIVIDENDS)
    with pytest.raises(ValueError, match="not benchmark"):
        replay.expected_benchmark(market(), BRACKET_HEAD, DIVIDENDS, cost_model="flat")


# ---- comparison ---------------------------------------------------------------------------------


def test_identical_records_have_no_difference():
    assert replay.compare("bracket", _bracket(), _bracket()) == ()
    assert replay.compare("book", _book(), _book()) == ()
    assert replay.compare("benchmark", _benchmark(), _benchmark()) == ()


def test_snapshot_difference_is_readable():
    exp = _bracket()
    s = exp.snapshots[2]
    snaps = list(exp.snapshots)
    snaps[2] = Snapshot(s.date, s.cash_usd, s.equity_usd + 1)
    diffs = replay.compare("bracket", replace(exp, snapshots=tuple(snaps)), exp)
    assert [str(d) for d in diffs] == [
        f"snapshot {s.date.isoformat()}: equity_usd stored {format(s.equity_usd + 1, 'f')}, replay {format(s.equity_usd, 'f')}"
    ]


def test_missing_and_extra_snapshots():
    exp = _bracket()
    diffs = replay.compare("bracket", replace(exp, snapshots=exp.snapshots[:-1]), exp)
    assert [str(d) for d in diffs] == ["snapshot 2025-03-07: in the replay, missing from the database"]
    extra = exp.snapshots + (Snapshot(D("2025-03-10"), CASH0, CASH0),)
    diffs = replay.compare("bracket", replace(exp, snapshots=extra), exp)
    assert [str(d) for d in diffs] == ["snapshot 2025-03-10: in the database, not in the replay"]


def test_missing_pending_order_and_changed_order_field():
    exp = _bracket()
    assert [str(d) for d in replay.compare("bracket", replace(exp, orders=exp.orders[:-1]), exp)] == [
        "order 2025-03-10 BBB: in the replay, missing from the database"
    ]
    first = exp.orders[0]
    changed = (replace(first, days_held=first.days_held + 1),) + exp.orders[1:]
    assert [str(d) for d in replay.compare("bracket", replace(exp, orders=changed), exp)] == [
        f"order 2025-03-04 AAA: days_held stored {first.days_held + 1}, replay {first.days_held}"
    ]


def test_mark_difference():
    exp = _bracket()
    diffs = replay.compare("bracket", replace(exp, marks=(("AAA", P("10.5")),)), exp)
    assert [str(d) for d in diffs] == ["mark AAA: stored 10.5000, replay 10.4000"]
    diffs = replay.compare("bracket", replace(exp, marks=(("AAA", None),)), exp)
    assert [str(d) for d in diffs] == ["mark AAA: stored none, replay 10.4000"]


def test_book_position_fill_trade_and_target_differences():
    exp = _book()
    pos = exp.positions[0]
    stored = replace(exp, positions=(replace(pos, shares=pos.shares + 1),) + exp.positions[1:])
    assert [str(d) for d in replay.compare("book", stored, exp)] == [
        f"position {pos.symbol}: shares stored {format(pos.shares + 1, 'f')}, replay {format(pos.shares, 'f')}"
    ]
    fill = exp.fills[0]
    stored = replace(exp, fills=(replace(fill, price=fill.price + P("0.01")),) + exp.fills[1:])
    assert [str(d) for d in replay.compare("book", stored, exp)] == [
        f"fill #1 (2025-03-03 buy AAA): price stored {format(fill.price + P('0.01'), 'f')}, replay {format(fill.price, 'f')}"
    ]
    fake = Trade(
        symbol="AAA",
        entry_date=D("2025-03-03"),
        exit_date=D("2025-03-04"),
        entry_price=P("10.4"),
        exit_price=P("10.1"),
        days_held=2,
        cost_usd=P("0.02"),
        income_usd=P("0"),
        pnl_usd=P("-0.32"),
        exit_reason="signal",
        idle=False,
    )
    stored = replace(exp, trades=exp.trades + (fake,))
    assert [str(d) for d in replay.compare("book", stored, exp)] == [
        f"trade #{len(exp.trades) + 1} (AAA 2025-03-03..2025-03-04): in the database, not in the replay"
    ]
    session, targets = exp.targets[0]
    halved = (replace(targets[0], weight=targets[0].weight / 2),) + targets[1:]
    stored = replace(exp, targets=((session, halved),))
    assert [str(d) for d in replay.compare("book", stored, exp)] == [
        f"target 2025-03-03 rank 1: weight stored {format(targets[0].weight / 2, 'f')}, replay {format(targets[0].weight, 'f')}"
    ]


def test_pending_decision_is_compared_for_book_only():
    exp = _book()
    assert [str(d) for d in replay.compare("book", replace(exp, pending_decision=True), exp)] == [
        "paper_state: pending_decision stored true, replay false"
    ]
    br = _bracket()
    assert replay.compare("bracket", replace(br, pending_decision=True), br) == ()
    bm = _benchmark()
    assert replay.compare("benchmark", replace(bm, pending_decision=True, pending_session=None), bm) == ()


def test_benchmark_holding_and_state_differences():
    exp = _benchmark()
    h = exp.holdings[0]
    stored = replace(exp, holdings=(Holding(h.symbol, h.shares + 1, h.mark),), cash=exp.cash - 1)
    assert [str(d) for d in replay.compare("benchmark", stored, exp)] == [
        f"holding SPY: shares stored {format(h.shares + 1, 'f')}, replay {format(h.shares, 'f')}",
        f"paper_state: cash stored {format(exp.cash - 1, 'f')}, replay {format(exp.cash, 'f')}",
    ]


def test_unknown_engine_is_refused():
    with pytest.raises(ValueError, match="unknown engine"):
        replay.compare("other", _bracket(), _bracket())  # type: ignore[arg-type]


# ---- splits -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("symbol", "day", "hit"),
    [
        ("AAA", "2025-03-05", True),  # open since 03-04
        ("BBB", "2025-03-06", True),  # pending for 03-06 the night before (it then expired)
        ("BBB", "2025-03-05", False),  # nothing live on BBB the night before 03-05
        ("BBB", "2025-03-10", True),  # pending for 03-10
        ("AAA", "2025-03-03", False),  # before paper_start
        ("CCC", "2025-03-05", False),
    ],
)
def test_bracket_split_exposure(symbol, day, hit):
    got = replay.split_exposure("bracket", BRACKET_HEAD.paper_start, (_bracket(),), [(symbol, D(day))])
    assert got == (((symbol, D(day)),) if hit else ())


def test_bracket_order_closed_before_the_split_is_not_exposed():
    exp = _bracket()
    first = exp.orders[0]
    closed = replace(
        first, status="closed", exit_date=D("2025-03-05"), exit_price=P("11"), exit_reason="tp", pnl_usd=P("1")
    )
    rec = replace(exp, orders=(closed,))
    assert replay.split_exposure("bracket", BRACKET_HEAD.paper_start, (rec,), [("AAA", D("2025-03-06"))]) == ()
    assert replay.split_exposure("bracket", BRACKET_HEAD.paper_start, (rec,), [("AAA", D("2025-03-05"))]) == (
        ("AAA", D("2025-03-05")),
    )


@pytest.mark.parametrize(
    ("symbol", "day", "hit"),
    [
        ("AAA", "2025-03-04", True),  # held since 03-03
        ("AAA", "2025-03-03", True),  # targeted for 03-03
        ("BBB", "2025-02-27", False),
        ("AAA", "2025-02-26", False),
    ],
)
def test_book_split_exposure(symbol, day, hit):
    got = replay.split_exposure("book", BOOK_HEAD.paper_start, (_book(),), [(symbol, D(day))])
    assert got == (((symbol, D(day)),) if hit else ())


def test_book_trade_spanning_the_split_is_exposed():
    exp = _book()
    trade = Trade(
        symbol="CCC",
        entry_date=D("2025-02-27"),
        exit_date=D("2025-03-03"),
        entry_price=P("5"),
        exit_price=P("5"),
        days_held=3,
        cost_usd=P("0.01"),
        income_usd=P("0"),
        pnl_usd=P("-0.02"),
        exit_reason="signal",
        idle=False,
    )
    rec = replace(exp, trades=(trade,))
    assert replay.split_exposure("book", BOOK_HEAD.paper_start, (rec,), [("CCC", D("2025-03-03"))]) == (
        ("CCC", D("2025-03-03")),
    )
    assert replay.split_exposure("book", BOOK_HEAD.paper_start, (rec,), [("CCC", D("2025-02-27"))]) == ()


def test_benchmark_split_exposure_starts_after_the_first_session():
    exp = _benchmark()
    start = SPY_HEAD.paper_start
    assert replay.split_exposure("benchmark", start, (exp,), [("SPY", start)]) == ()
    nxt = dates.next_session(start)
    assert replay.split_exposure("benchmark", start, (exp,), [("SPY", nxt), ("AAA", nxt)]) == (("SPY", nxt),)


# ---- verdicts -----------------------------------------------------------------------------------


def test_judge_ok_mismatch_and_split_affected():
    exp = _bracket()
    ok = replay.judge(BRACKET_HEAD, exp, exp, ())
    assert (ok.status, ok.sessions, ok.differences, ok.total_differences, ok.splits) == ("ok", 4, (), 0, ())
    assert (ok.paper_start, ok.last_session) == (D("2025-03-04"), D("2025-03-07"))
    bad = replay.judge(BRACKET_HEAD, replace(exp, cash=exp.cash + 1), exp, ())
    assert bad.status == "mismatch" and bad.total_differences == 1
    hit = replay.judge(BRACKET_HEAD, replace(exp, cash=exp.cash + 1), exp, [("AAA", D("2025-03-05"))])
    assert hit.status == "split-affected" and hit.splits == (("AAA", D("2025-03-05")),)
    assert hit.total_differences == 1


def test_judge_lists_at_most_max_shown(monkeypatch):
    monkeypatch.setattr(replay, "MAX_SHOWN", 3)
    exp = _bracket()
    snaps = tuple(Snapshot(s.date, s.cash_usd + 1, s.equity_usd + 1) for s in exp.snapshots)
    r = replay.judge(BRACKET_HEAD, replace(exp, snapshots=snaps), exp, ())
    assert len(r.differences) == 3 and r.total_differences == 10
    assert replay.render((r,))[-1] == "    ... and 7 more"


def test_not_started_and_broken():
    r = replay.not_started("F1")
    assert (r.status, r.sessions, r.differences) == ("not-started", 0, ())
    b = replay.broken("A", "replay", "boom", paper_start=D("2025-03-04"), last_session=D("2025-03-07"))
    assert b.status == "mismatch" and b.sessions == 4 and [str(d) for d in b.differences] == ["replay: boom"]
    assert replay.broken("A", "paper_state", "x", paper_start=D("2025-03-04")).sessions == 0


def test_exit_code_and_failures():
    ok = CheckResult("A", "ok", 5)
    split = CheckResult("SPY", "split-affected", 5)
    new = replay.not_started("F1")
    bad = CheckResult("F4", "mismatch", 5, total_differences=2)
    assert replay.exit_code((ok, split, new), 0) == 0
    assert replay.exit_code((ok, split, new), 1) == 1
    assert replay.exit_code((ok, split), 5) == 0
    assert replay.exit_code((ok, split), 6) == 1
    assert replay.exit_code((ok, bad), 0) == 1
    assert replay.failures((ok, bad, new), 1) == (
        "F4: replay mismatch (2 differences)",
        "F1: 0 sessions stepped, 1 required",
    )
    with pytest.raises(ValueError):
        replay.failures((ok,), -1)


def test_render_one_line_per_strategy_then_its_differences():
    exp = _bracket()
    bad = replay.judge(BRACKET_HEAD, replace(exp, cash=exp.cash + 1), exp, ())
    lines = replay.render((bad, replay.not_started("F1-SPY-SMA200-M")))
    assert lines[0].split() == ["A", "mismatch", "4", "sessions", "(2025-03-04..2025-03-07),", "1", "difference"]
    assert lines[1] == f"    paper_state: cash stored {format(exp.cash + 1, 'f')}, replay {format(exp.cash, 'f')}"
    assert lines[2].split() == ["F1-SPY-SMA200-M", "not-started", "no", "paper", "start"]
    split = replay.judge(BRACKET_HEAD, exp, exp, [("AAA", D("2025-03-05"))])
    assert replay.render((split,))[0].endswith("applied split AAA on 2025-03-05; 0 differences not failed")
    first = replay.judge(replace(BRACKET_HEAD, last_session=D("2025-03-03")), exp, exp, ())
    assert "0 sessions (starts 2025-03-04)" in replay.render((first,))[0]


def test_paper_head_validation():
    with pytest.raises(ValueError, match="before the day-0 session"):
        PaperHead("A", "bracket", D("2025-03-04"), D("2025-02-28"), USD_IDR)
    with pytest.raises(ValueError, match="unknown engine"):
        PaperHead("A", "other", D("2025-03-04"), D("2025-03-07"), USD_IDR)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not an NYSE session"):
        PaperHead("A", "bracket", D("2025-03-08"), D("2025-03-10"), USD_IDR)
    with pytest.raises(TypeError, match="usd_idr"):
        PaperHead("A", "bracket", D("2025-03-04"), D("2025-03-07"), 16000)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="usd_idr"):
        PaperHead("A", "bracket", D("2025-03-04"), D("2025-03-07"), Decimal("0"))
    assert PaperHead("A", "bracket", D("2025-03-04"), D("2025-03-03"), USD_IDR).sessions == 0


def test_difference_str():
    assert str(Difference("snapshot 2025-03-04", "missing")) == "snapshot 2025-03-04: missing"


# ---- split cadence: the replay keeps its own last rank basket ---------------------------------
#
# The split-cadence market and allocator of tests/test_paper_book.py. The replay rebuilds the
# last rank basket from its own rank decisions and the marks from last_close; the paper night
# (split_paper_run there) reads them back from what it stored. Both must decide the same.


@pytest.mark.parametrize("rules", SPLIT_RULES, ids=lambda r: r.id)
@pytest.mark.parametrize("start", [D("2025-02-03"), D("2025-02-10"), D("2025-02-12")],
                         ids=["rank-day", "resize-monday", "mid-month"])
def test_expected_book_of_split_cadence_rules_equals_the_nights(rules, start):
    m = split_market()
    nights = split_paper_run(lambda d: m, BREATHE, None, rules, start, SPLIT_END, initial_idr=PAPER_INITIAL_IDR)
    head = PaperHead("S", "book", start, SPLIT_END, USD_IDR, kickoff=nights.kickoff)
    got = replay.expected_book(m, BREATHE, None, rules, head, {})
    assert got.snapshots == tuple(Snapshot(s.date, s.cash_usd, s.equity_usd) for s in nights.result.snapshots)
    assert got.fills == nights.result.fills and got.trades == nights.result.trades
    assert got.positions == nights.result.open_at_end
    assert got.targets == tuple(sorted(nights.stored.items()))
    assert any(is_resize_session(rules, s) for s, _ in got.targets)
    assert replay.compare("book", got, got) == ()


def test_expected_book_pending_resize_decision():
    m, rules = split_market(), MONTHLY_RANK_WEEKLY_RESIZE
    head = PaperHead("S", "book", D("2025-02-12"), D("2025-03-07"), USD_IDR, kickoff=D("2025-02-12"))
    got = replay.expected_book(m, BREATHE, None, rules, head, {})
    assert got.pending_session == D("2025-03-10") and got.pending_decision is True
    (pending,) = [t for s, t in got.targets if s == D("2025-03-10")]
    assert [(t.symbol, t.weight) for t in pending] == [("DDD", Decimal("0.45")), ("AAA", Decimal("0.45"))]
    # Before any rank (a head with no kickoff, started mid-month) a resize week decides nothing.
    early = replay.expected_book(m, BREATHE, None, rules, replace(head, last_session=D("2025-02-14"), kickoff=None), {})
    assert early.pending_session == D("2025-02-18") and is_resize_session(rules, D("2025-02-18"))
    assert early.pending_decision is False and early.targets == ()
