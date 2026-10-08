"""Bracket paper nights (plan phase 3, contract C3): ``decide_bracket`` + ``settle_bracket`` looped
over a window equal ``run_backtest`` exactly; splits on a pending and an open order; the forced
close; no look-ahead.

Simulator arithmetic in the hand-checked comments: ``buy_cost(p, n) = q(p × n × 1.001)``,
``sell_proceeds(p, n) = q(p × n × 0.999)``; fill when ``low < limit`` at ``min(open, limit)``;
``sim.apply_split`` divides prices by the ratio and floors shares, paying the fraction of an open
position as cash in lieu at the new mark.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal

import pytest
from simkit import D, P, bar, opened, pending, portfolio
from stratkit import mutate_from

from seer_engine import dates
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import RunResult, run_backtest
from seer_engine.paper.bracket import BracketNight, decide_bracket, settle_bracket
from seer_engine.prices import Bar
from seer_engine.sim import DESIGN_V0, Event, Snapshot, TradeRules, initial_cash_usd, new_portfolio
from seer_engine.sim.rules import DESIGN_V0_GOTRADE
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.base import history_from_bars

# --------------------------------------------------------------------------- synthetic market

SESSIONS = dates.sessions(D("2023-01-03"), D("2025-06-30"))
# (symbol, phase, first price). UPA and UPE dip on the same sessions; BIG is too dear for one
# share of a slot budget (``lt_one_share`` rejections).
SYMBOLS = (("UPA", 0, 100.0), ("UPB", 7, 100.0), ("UPC", 13, 100.0), ("UPD", 3, 100.0), ("UPE", 0, 100.0), ("BIG", 7, 5000.0))


def _bars(symbol: str, phase: int, first: float) -> list[Bar]:
    """An uptrend (+0.6 % a session) with two -3 % sessions every 20 (shifted by ``phase``) and a
    deep intraday low the session after, so Strategy A's setup (close > SMA200, RSI(2) < 10,
    dollar volume ~1e8 > 2e7) fires and its limit fills. Every 100 sessions the dips end
    differently: a gap through the stop (m = 20), no fill (39), an intraday drop through the stop
    (60), a take-profit (80) and five flat sessions that run into the time stop (0-5). Prices are
    rounded to 4 dp first, so the float64 History holds exactly what ``bars`` would."""
    out = []
    prev = first + phase
    for t, d in enumerate(SESSIONS):
        k = (t + phase) % 20
        m = (t + phase) % 100
        c = prev * 0.97 if k in (17, 18) else prev * 1.006
        o = prev
        lo = min(o, c) * (0.97 if k == 19 else 0.995)
        hi = max(o, c) * 1.005
        if m == 20:
            o = prev * 0.93
            c = o * 1.004
            lo = o * 0.995
            hi = c * 1.005
        elif m == 39:
            lo = min(o, c) * 0.999
        elif m == 60:
            o, c, lo, hi = prev, prev, prev * 0.95, prev * 1.001
        elif m < 6:
            o = prev
            c = prev * 1.0005
            lo = prev * 0.999
            hi = c * 1.001
        out.append(bar(symbol, d, f"{o:.4f}", f"{hi:.4f}", f"{lo:.4f}", f"{c:.4f}", 1_000_000))
        prev = float(f"{c:.4f}")
    return out


def market(cut: date | None = None) -> Market:
    """The synthetic market; with ``cut``, UPC's bars stop at ``cut`` (delisted after it)."""
    history = {}
    for symbol, phase, first in SYMBOLS:
        rows = _bars(symbol, phase, first)
        if symbol == "UPC" and cut is not None:
            rows = [b for b in rows if b.date <= cut]
        history[symbol] = history_from_bars(symbol, rows)
    return Market(
        history=history,
        membership=Membership(tuple((s, D("2020-01-02"), None) for s in sorted(history))),
        fx=((D("2022-12-30"), Decimal("16000")),),
    )


START, END = SESSIONS[200], SESSIONS[-1]  # data_date SESSIONS[199] has exactly 200 bars


# This fixture's price ladder is calibrated to a 1250 USD book, so it pins its own 20,000,000 IDR
# rather than following backtest.runner.INITIAL_IDR, which plan phase 5 moved to the owner's real
# 10,000,000. Measured at 10,000,000: the slot halves, lt_one_share rejections go 26 -> 123, and
# Gotrade's $0.10 per-order floor then rejects five names the flat rate still affords (128 vs 123),
# so the two runs stop being identical in shape and the test below has nothing left to compare.
# At 20,000,000 both runs place 215 events with the same shape and the assertion keeps its full
# strength -- which is the point: this test is about the fee model, not about the lab's capital.
BRACKET_IDR = Decimal("20000000")


def run_nights(
    m: Market, start: date, end: date, *, rules: TradeRules = DESIGN_V0
) -> tuple[RunResult, list[BracketNight]]:
    """The paper loop over ``[start, end]``, shaped as a ``RunResult`` for comparison.

    ``rules`` defaults to ``DESIGN_V0``, so every existing caller is byte-for-byte unchanged.
    """
    usd_idr = m.usd_idr_on(start)
    cash0 = initial_cash_usd(BRACKET_IDR, usd_idr)
    pf = new_portfolio(cash0)
    data_date = dates.prev_session(start)
    snapshots = [Snapshot(data_date, pf.cash, pf.equity)]
    events: list[Event] = []
    rejections: Counter[str] = Counter()
    nights: list[BracketNight] = []
    for session in dates.sessions(start, end):
        sized = decide_bracket(
            pf, STRATEGY_A, STRATEGY_A_PARAMS, m.history, m.membership.members_on(data_date), data_date, rules=rules
        )
        for r in sized.rejected:
            rejections[r.reason] += 1
        pf = sized.portfolio
        night = settle_bracket(pf, session, m.bars_on(session, pf.held_symbols()), (), m.last_bar_date, rules=rules)
        nights.append(night)
        pf = night.portfolio
        events.extend(night.events)
        snapshots.append(night.snapshot)
        data_date = session
    result = RunResult(
        strategy_id=STRATEGY_A.id,
        params=STRATEGY_A_PARAMS,
        start=start,
        end=end,
        usd_idr=usd_idr,
        initial_cash=cash0,
        snapshots=tuple(snapshots),
        events=tuple(events),
        closed=tuple(e.order for e in events if e.kind == "exit"),
        open_at_end=pf.open_orders(),
        rejections=tuple(sorted(rejections.items())),
    )
    return result, nights


def _cut_while_held() -> date:
    """A session on whose close UPC is open in the uncut run (so cutting its bars there forces a
    close on the next session)."""
    full = run_backtest(market(), STRATEGY_A, STRATEGY_A_PARAMS, START, END, initial_idr=BRACKET_IDR)
    for e in full.events:
        o = e.order
        if e.kind == "fill" and o.symbol == "UPC":
            after = [x for x in full.events if x.kind == "exit" and x.order.symbol == "UPC" and x.order.fill_date == o.fill_date]
            if not after or after[0].order.exit_date > o.fill_date:
                return o.fill_date
    raise AssertionError("UPC never stays open past its fill session")


# --------------------------------------------------------------------------- equality with run_backtest


def test_window_has_at_least_300_sessions():
    assert len(dates.sessions(START, END)) >= 300


def test_nights_equal_run_backtest():
    m = market()
    expected = run_backtest(m, STRATEGY_A, STRATEGY_A_PARAMS, START, END, initial_idr=BRACKET_IDR)
    got, nights = run_nights(m, START, END)
    assert got.snapshots == expected.snapshots
    assert got.events == expected.events
    assert got.closed == expected.closed
    assert got.open_at_end == expected.open_at_end
    assert got.rejections == expected.rejections
    assert got == expected
    # Not vacuous: every exit reason, expiries and rejections happen in the window.
    assert {o.exit_reason for o in expected.closed} == {"tp", "sl", "gap", "time"}
    assert any(e.kind == "expire" for e in expected.events)
    assert dict(expected.rejections).get("lt_one_share", 0) > 0
    assert sum(len(n.closed) for n in nights) == len(expected.closed)
    assert all(n.snapshot == s for n, s in zip(nights, expected.snapshots[1:]))


def test_nights_equal_run_backtest_with_a_forced_close():
    cut = _cut_while_held()
    m = market(cut)
    expected = run_backtest(m, STRATEGY_A, STRATEGY_A_PARAMS, START, END, initial_idr=BRACKET_IDR)
    forced = [e for e in expected.events if e.forced]
    assert len(forced) == 1
    assert forced[0].order.symbol == "UPC"
    assert forced[0].session_date == dates.next_session(cut)
    got, nights = run_nights(m, START, END)
    assert got == expected
    night = next(n for n in nights if n.session == dates.next_session(cut))
    assert night.events[-1] == forced[0]
    assert night.snapshot == Snapshot(night.session, night.portfolio.cash, night.portfolio.equity)


# --------------------------------------------------------------------------- one settled night by hand

MON, TUE, WED = D("2025-03-10"), D("2025-03-11"), D("2025-03-12")


def test_split_on_a_pending_and_on_an_open_order():
    # Before WED: cash 1000; OPN open 3 sh filled MON at 100 (tp 110, sl 90), mark 102, days 2,
    # slot 1; PND pending for WED, 5 sh, limit 50 (tp 55, sl 45), slot 2. last_session TUE.
    opn = opened("OPN", MON, "100", "110", "90", shares=3, days_held=2, slot=1)
    pnd = pending("PND", WED, "50", "55", "45", shares=5, slot=2)
    pf = portfolio("1000", opn, pnd, marks={"OPN": "102"}, last_session=TUE)
    # Splits executing on WED (given out of order; applied by symbol):
    #   PND 2-for-1 (factor 2): 10 sh, limit 25, tp 27.5, sl 22.5.
    #   OPN 1-for-2 (factor 0.5): floor(3 × 1/2) = 1 sh, remainder 1/2 sh paid in lieu at the
    #     new mark 204: q(0.5 × 204) = 102 -> cash 1102. fill 200, tp 220, sl 180.
    # WED bars (post-split units): OPN o 205 h 210 l 200 c 206 -> no exit, days 3, mark 206.
    #   PND o 25.5 h 26 l 24.5 c 25: 24.5 < 25 fills at min(25.5, 25) = 25, cost q(250 × 1.001)
    #   = 250.25 -> cash 851.75; equity 851.75 + 1 × 206 + 10 × 25 = 1307.75.
    bars = {
        "OPN": bar("OPN", WED, "205", "210", "200", "206"),
        "PND": bar("PND", WED, "25.5", "26", "24.5", "25"),
    }
    night = settle_bracket(pf, WED, bars, [("PND", Decimal(2)), ("OPN", Decimal("0.5"))], lambda s: WED)
    kinds = [(e.kind, e.order.symbol) for e in night.events]
    assert kinds == [("split", "OPN"), ("split", "PND"), ("fill", "PND")]
    assert night.events[0].cash_usd == P("102")
    assert night.events[1].cash_usd is None
    o, p = night.portfolio.orders
    assert (o.symbol, o.shares, o.fill_price, o.tp_price, o.sl_price, o.days_held) == (
        "OPN", 1, P("200"), P("220"), P("180"), 3,
    )
    assert (p.symbol, p.status, p.shares, p.limit_price, p.fill_price) == ("PND", "open", 10, P("25"), P("25"))
    assert night.portfolio.marks == (("OPN", P("206")), ("PND", P("25")))
    assert night.snapshot == Snapshot(WED, P("851.75"), P("1307.75"))
    assert night.portfolio.last_session == WED
    assert night.closed == () and night.expired == ()


def test_split_on_a_symbol_not_held_changes_nothing():
    pnd = pending("PND", WED, "50", "55", "45", shares=5)
    pf = portfolio("1000", pnd, last_session=TUE)
    bars = {"PND": bar("PND", WED, "51", "52", "50.5", "51")}  # low 50.5 not < 50: expires
    plain = settle_bracket(pf, WED, bars, (), lambda s: WED)
    with_split = settle_bracket(pf, WED, bars, [("ZZZ", Decimal(4))], lambda s: WED)
    assert with_split == plain
    assert plain.expired == (plain.events[0].order,)
    assert plain.snapshot == Snapshot(WED, P("1000"), P("1000"))


def test_forced_close_of_a_symbol_without_bars():
    # GONE: open 10 sh filled TUE at 20 (tp 25, sl 15), mark 21, days 1. cash 500.
    # WED: no bar -> days 2, mark 21, step equity 500 + 210 = 710. last bar TUE < WED -> forced
    # close at 21: proceeds q(210 × 0.999) = 209.79, pnl 209.79 - q(200 × 1.001) = 9.59.
    # cash 709.79 = equity; the snapshot is replaced.
    gone = opened("GONE", TUE, "20", "25", "15", shares=10, days_held=1)
    pf = portfolio("500", gone, marks={"GONE": "21"}, last_session=TUE)
    night = settle_bracket(pf, WED, {}, (), lambda s: TUE)
    (e,) = night.events
    assert (e.kind, e.forced, e.session_date, e.cash_usd) == ("exit", True, WED, P("209.79"))
    assert (e.order.exit_reason, e.order.exit_price, e.order.days_held, e.order.pnl_usd) == ("time", P("21"), 2, P("9.59"))
    assert night.portfolio.orders == ()
    assert night.snapshot == Snapshot(WED, P("709.79"), P("709.79"))
    assert night.closed == (e.order,)


@pytest.mark.parametrize(
    ("last", "closed"),
    [(None, True), (TUE, True), (WED, False), (D("2025-03-20"), False)],
)
def test_force_close_rule_follows_last_bar_date(last, closed):
    # No bar on WED in every case; only a last bar before WED (or none) closes the position.
    gone = opened("GONE", TUE, "20", "25", "15", shares=10, days_held=1)
    pf = portfolio("500", gone, marks={"GONE": "21"}, last_session=TUE)
    night = settle_bracket(pf, WED, {}, (), lambda s: last)
    assert (night.portfolio.orders == ()) is closed
    assert night.snapshot.equity_usd == (P("709.79") if closed else P("710"))


def test_settle_rejects_bad_input():
    pf = portfolio("1000", last_session=TUE)
    with pytest.raises(ValueError, match="not an NYSE session"):
        settle_bracket(pf, D("2025-03-15"), {}, (), lambda s: None)
    with pytest.raises(ValueError, match="not after"):
        settle_bracket(pf, TUE, {}, (), lambda s: None)
    with pytest.raises(ValueError, match="two splits"):
        settle_bracket(pf, WED, {}, [("X", Decimal(2)), ("X", Decimal(3))], lambda s: None)
    with pytest.raises(TypeError, match="Decimal"):
        settle_bracket(pf, WED, {}, [("X", 2.0)], lambda s: None)
    with pytest.raises(TypeError, match="callable"):
        settle_bracket(pf, WED, {}, (), None)
    with pytest.raises(ValueError, match="pending order"):
        settle_bracket(portfolio("1000", pending("P", D("2025-03-13"), "5", "6", "4", 1), last_session=TUE),
                       WED, {}, (), lambda s: None)


# --------------------------------------------------------------------------- decide


def test_decide_cuts_history_at_data_date_no_look_ahead():
    """Changing every bar dated on or after S leaves the decision for S unchanged."""
    m = market()
    cash0 = initial_cash_usd(BRACKET_IDR, m.usd_idr_on(START))
    seen_picks = 0
    for data_date in SESSIONS[199::7]:
        s = dates.next_session(data_date)
        members = m.membership.members_on(data_date)
        pf = new_portfolio(cash0)
        before = decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, m.history, members, data_date)
        mutated = {sym: mutate_from(h, s) for sym, h in m.history.items()}
        after = decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, mutated, members, data_date)
        assert after == before
        assert all(o.session_date == s for o in before.placed)
        seen_picks += len(before.placed)
    assert seen_picks > 0  # not vacuous


def test_decide_sizes_for_the_next_session_and_checks_the_portfolio():
    m = market()
    data_date = SESSIONS[250]
    pf = new_portfolio(P("1250"))
    sized = decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, m.history, m.membership.members_on(data_date), data_date)
    assert all(o.session_date == dates.next_session(data_date) for o in sized.portfolio.pending_orders())
    stepped = portfolio("1250", last_session=SESSIONS[249])
    with pytest.raises(ValueError, match="last settled session"):
        decide_bracket(stepped, STRATEGY_A, STRATEGY_A_PARAMS, m.history, frozenset(), data_date)
    with pytest.raises(ValueError, match="not an NYSE session"):
        decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, m.history, frozenset(), D("2025-03-15"))


# --------------------------------------------------------------------------- the cost model lever


def test_a_gotrade_night_keeps_the_shape_and_pays_strictly_more():
    """Phase 4: the same window under ``DESIGN_V0_GOTRADE``.

    The signature change moves nothing structural -- same sessions, same fills, same symbols and
    slots -- it only charges Gotrade's measured schedule, so the book ends strictly poorer. That
    is the counterfactual strategy C exists to produce, not a defect.
    """
    m = market()
    flat, _ = run_nights(m, START, END)
    gt, _ = run_nights(m, START, END, rules=DESIGN_V0_GOTRADE)

    def shape(r):
        return [(e.session_date, e.kind, e.order.symbol, e.order.slot) for e in r.events]

    # (i) identical in shape: every event, on the same session, same symbol, same slot.
    assert shape(gt) == shape(flat)
    assert [s.date for s in gt.snapshots] == [s.date for s in flat.snapshots]
    assert gt.rejections == flat.rejections
    assert gt.initial_cash == flat.initial_cash
    # Not vacuous: the window really does fill, reject and exit every way.
    assert sum(1 for e in flat.events if e.kind == "fill") == 85
    assert {o.exit_reason for o in gt.closed} == {"tp", "sl", "gap", "time"}

    # (ii) and strictly poorer, because the fees are strictly higher. Measured on this fixture.
    assert flat.snapshots[-1].equity_usd == Decimal("978.5054")
    assert gt.snapshots[-1].equity_usd == Decimal("912.3158")
    assert gt.snapshots[-1].equity_usd < flat.snapshots[-1].equity_usd


def test_the_default_rules_are_design_v0_so_the_parity_test_is_the_proof():
    """``rules`` is keyword-only with ``DESIGN_V0`` as its default at both entry points, which is
    what lets phase 12 wire ``commands/paper.py`` later without this phase changing any number."""
    import inspect

    for fn in (settle_bracket, decide_bracket):
        p = inspect.signature(fn).parameters["rules"]
        assert p.kind is inspect.Parameter.KEYWORD_ONLY, fn.__name__
        assert p.default is DESIGN_V0, fn.__name__
