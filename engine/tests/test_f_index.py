"""Families F1/F10/F11 (strategies/f_index.py): index timing and the turn-of-month calendar."""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest
from stratkit import drop_days, hist, mutate_from, session_days, truncate_before

from seer_engine.dates import next_session, prev_session, sessions
from seer_engine.sim import Target
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import (
    CALENDAR,
    MAX_SESSIONS_PER_MONTH,
    TIMING,
    CalendarAllocator,
    CalendarParams,
    IndexPrepared,
    TimingAllocator,
    TimingParams,
    turn_of_month,
)

NONE: frozenset[str] = frozenset()
NO_MEMBERS: frozenset[str] = frozenset()
D0 = date(2019, 1, 2)  # stratkit.START: hist() bars run on consecutive sessions from here


def T(hold: str, signal: str, rule: str, n: int) -> TimingParams:  # noqa: N802 — the plan index's notation
    return TimingParams(hold=hold, signal=signal, rule=rule, n=n)


def full(symbol: str, last: str) -> Target:
    return Target(symbol, Decimal("1"), Decimal(last))


def last_day(h: History) -> date:
    d = h.last_date()
    assert d is not None
    return d


def run(allocator, history, d, params, held=NONE):
    return allocator.targets(history, NO_MEMBERS, d, held, params)


# ---- params --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kw, exc",
    [
        ({"hold": "", "signal": "SPY", "rule": "sma"}, ValueError),
        ({"hold": "spy", "signal": "SPY", "rule": "sma"}, ValueError),
        ({"hold": " SPY", "signal": "SPY", "rule": "sma"}, ValueError),
        ({"hold": 1, "signal": "SPY", "rule": "sma"}, TypeError),
        ({"hold": "SPY", "signal": None, "rule": "sma"}, TypeError),
        ({"hold": "SPY", "signal": "SPY", "rule": "ema"}, ValueError),
        ({"hold": "SPY", "signal": "SPY", "rule": 3}, TypeError),
        ({"hold": "SPY", "signal": "SPY", "rule": "sma", "n": 0}, ValueError),
        ({"hold": "SPY", "signal": "SPY", "rule": "sma", "n": True}, TypeError),
        ({"hold": "SPY", "signal": "SPY", "rule": "sma", "n": 200.0}, TypeError),
    ],
)
def test_timing_params_reject_bad_values(kw, exc):
    with pytest.raises(exc):
        TimingParams(**kw)


@pytest.mark.parametrize(
    "kw, exc",
    [
        ({"hold": ""}, ValueError),
        ({"hold": "SPY", "days_before": -1}, ValueError),
        ({"hold": "SPY", "days_after": 11}, ValueError),
        ({"hold": "SPY", "days_before": 0, "days_after": 0}, ValueError),
        ({"hold": "SPY", "days_before": 1.0}, TypeError),
        ({"hold": "SPY", "days_after": False}, TypeError),
        ({"hold": "SPY", "trend": ["SPY", 200]}, TypeError),
        ({"hold": "SPY", "trend": ("SPY",)}, TypeError),
        ({"hold": "SPY", "trend": ("SPY", 0)}, ValueError),
        ({"hold": "SPY", "trend": ("spy", 200)}, ValueError),
        ({"hold": "SPY", "trend": ("SPY", "200")}, TypeError),
    ],
)
def test_calendar_params_reject_bad_values(kw, exc):
    with pytest.raises(exc):
        CalendarParams(**kw)


def test_params_defaults_and_as_dict_in_fixed_order():
    p = TimingParams(hold="SSO", signal="SPY", rule="month_sma", n=10)
    assert p.as_dict() == {"hold": "SSO", "signal": "SPY", "rule": "month_sma", "n": "10"}
    assert list(p.as_dict()) == ["hold", "signal", "rule", "n"]
    assert TimingParams(hold="SPY", signal="SPY", rule="sma").n == 200
    c = CalendarParams("QQQ")
    assert (c.days_before, c.days_after, c.trend) == (1, 3, None)
    assert c.as_dict() == {"hold": "QQQ", "days_before": "1", "days_after": "3", "trend": "none"}
    assert list(c.as_dict()) == ["hold", "days_before", "days_after", "trend"]
    assert CalendarParams("QQQ", 2, 0, ("QQQ", 200)).as_dict()["trend"] == "QQQ:200"
    assert CalendarParams("SPY", 0, 1).days_before == 0  # one side may be zero


def test_params_are_frozen_and_hashable():
    p = T("SPY", "SPY", "sma", 200)
    with pytest.raises(AttributeError):
        p.n = 100  # type: ignore[misc]
    assert hash(p) == hash(T("SPY", "SPY", "sma", 200))
    assert hash(CalendarParams("SPY", 1, 3, ("SPY", 200))) == hash(CalendarParams("SPY", 1, 3, ("SPY", 200)))


# ---- the protocol surface ------------------------------------------------------------------------


def test_singletons_implement_the_allocator_protocol():
    assert isinstance(TIMING, TimingAllocator) and isinstance(CALENDAR, CalendarAllocator)
    assert isinstance(TIMING, Allocator) and isinstance(CALENDAR, Allocator)
    assert (TIMING.id, CALENDAR.id) == ("F1", "F11")


@pytest.mark.parametrize(
    "allocator, params, lookback, symbols, holds",
    [
        (TIMING, T("SPY", "SPY", "sma", 200), 200, ("SPY",), ("SPY",)),
        (TIMING, T("QQQ", "SPY", "sma", 200), 200, ("QQQ", "SPY"), ("QQQ",)),
        (TIMING, T("SSO", "SPY", "month_sma", 10), MAX_SESSIONS_PER_MONTH * 10, ("SPY", "SSO"), ("SSO",)),
        (TIMING, T("SPY", "SPY", "abs_mom", 252), 253, ("SPY",), ("SPY",)),
        (TIMING, T("SPY", "SPY", "always", 1), 1, ("SPY",), ("SPY",)),
        (TIMING, T("QLD", "QQQ", "always", 200), 1, ("QLD", "QQQ"), ("QLD",)),
        (CALENDAR, CalendarParams("SPY", 1, 3, None), 1, ("SPY",), ("SPY",)),
        (CALENDAR, CalendarParams("SPY", 1, 3, ("SPY", 200)), 200, ("SPY",), ("SPY",)),
        (CALENDAR, CalendarParams("QQQ", 1, 3, ("SPY", 150)), 150, ("QQQ", "SPY"), ("QQQ",)),
    ],
)
def test_lookback_symbols_holds_and_members(allocator, params, lookback, symbols, holds):
    assert allocator.lookback(params) == lookback
    assert allocator.symbols(params) == symbols
    assert allocator.holds(params) == holds
    assert set(allocator.holds(params)) <= set(allocator.symbols(params))
    assert allocator.uses_members(params) is False


def test_month_sma_lookback_always_spans_n_completed_months():
    # 23 × n consecutive sessions end on any day and still contain n completed month ends.
    days = sessions(date(1993, 1, 4), date(2016, 12, 30))
    n = 10
    need = TIMING.lookback(T("SPY", "SPY", "month_sma", n))
    for end in range(need - 1, len(days), 7):
        window = days[end + 1 - need : end + 1]
        d = window[-1]
        completed = {(x.year, x.month) for x in window if (x.year, x.month) != (d.year, d.month)}
        if next_session(d).month != d.month:
            completed.add((d.year, d.month))  # d ends its month
        assert len(completed) >= n, d


def test_wrong_params_or_prepared_types_raise():
    h = {"SPY": hist("SPY", [1.0, 2.0, 3.0])}
    cal = CalendarParams("SPY")
    tim = T("SPY", "SPY", "sma", 3)
    for method in ("lookback", "symbols", "holds", "uses_members"):
        with pytest.raises(TypeError):
            getattr(TIMING, method)(cal)
        with pytest.raises(TypeError):
            getattr(CALENDAR, method)(tim)
    with pytest.raises(TypeError):
        run(TIMING, h, D0, cal)
    with pytest.raises(TypeError):
        run(CALENDAR, h, D0, tim)
    with pytest.raises(TypeError):
        TIMING.targets_prepared(h, NO_MEMBERS, D0, NONE, tim)  # a plain dict is not IndexPrepared
    with pytest.raises(TypeError):
        run(TIMING, h, D0.isoformat(), tim)


def test_prepare_freezes_a_snapshot_of_the_mapping():
    h = {"SPY": hist("SPY", [1.0, 2.0, 3.0])}
    prepared = TIMING.prepare(h)
    assert isinstance(prepared, IndexPrepared) and isinstance(CALENDAR.prepare(h), IndexPrepared)
    h["SPY"] = hist("SPY", [3.0, 2.0, 1.0])  # later edits to the caller's dict do not leak in
    d = date(2019, 1, 4)
    assert TIMING.targets_prepared(prepared, NO_MEMBERS, d, NONE, T("SPY", "SPY", "sma", 3)) == (full("SPY", "3"),)
    assert TIMING.targets_prepared(TIMING.prepare({}), NO_MEMBERS, d, NONE, T("SPY", "SPY", "sma", 3)) == ()


# ---- F1 signals, hand-checked --------------------------------------------------------------------


@pytest.mark.parametrize(
    "closes, on",
    [
        ([1.0, 2.0, 3.0], True),  # SMA3 = 2, close 3
        ([3.0, 2.0, 1.0], False),  # SMA3 = 2, close 1
        ([2.0, 2.0, 2.0], False),  # close == SMA: strict
        ([100.0, 1.0, 2.0, 3.0], True),  # only the last 3 closes are averaged
        ([1.0, 2.0], False),  # fewer than n bars: off
    ],
)
def test_sma_rule_hand_checked(closes, on):
    h = {"SPY": hist("SPY", closes)}
    got = run(TIMING, h, last_day(h["SPY"]), T("SPY", "SPY", "sma", 3))
    assert got == ((full("SPY", f"{closes[-1]:.4f}"),) if on else ())


def test_target_is_full_weight_at_the_data_date_close_with_no_bracket():
    h = {"SPY": hist("SPY", [10.0, 11.0, 123.45675])}  # SMA3 = 48.15…; close rounds half-up
    (t,) = run(TIMING, h, last_day(h["SPY"]), T("SPY", "SPY", "sma", 3))
    assert t == Target("SPY", Decimal("1"), Decimal("123.4568"))
    assert (t.limit, t.stop, t.take) == (None, None, None)
    assert t.weight == Decimal(1) and t.last.as_tuple().exponent == -4


def month_history(values: dict[int, float], last: date) -> History:
    """SPY closes constant within each 2019 month (``values[month]``), every session to ``last``."""
    days = sessions(D0, last)
    return hist("SPY", [values[d.month] for d in days], days=days)


@pytest.mark.parametrize(
    "n, d, on",
    [
        (3, date(2019, 4, 29), True),  # completed Jan–Mar: mean(10, 20, 30) = 20 < 25
        (3, date(2019, 4, 30), False),  # Apr 30 ends April: mean(20, 30, 25) = 25, close 25 (strict)
        (3, date(2019, 5, 15), True),  # mean(20, 30, 25) = 25 < 26
        (2, date(2019, 5, 15), False),  # mean(30, 25) = 27.5 > 26
        (4, date(2019, 5, 15), True),  # mean(10, 20, 30, 25) = 21.25
        (5, date(2019, 5, 15), False),  # only 4 completed months: off
    ],
)
def test_month_sma_rule_hand_checked(n, d, on):
    h = {"SPY": month_history({1: 10.0, 2: 20.0, 3: 30.0, 4: 25.0, 5: 26.0}, date(2019, 5, 31))}
    got = run(TIMING, h, d, T("SPY", "SPY", "month_sma", n))
    close = 26.0 if d.month == 5 else 25.0
    assert got == ((full("SPY", f"{close:.4f}"),) if on else ())


@pytest.mark.parametrize(
    "closes, on",
    [
        ([10.0, 11.0, 12.0, 10.5], True),  # 10.5 / 10 − 1 = 0.05
        ([10.0, 11.0, 12.0, 10.0], False),  # exactly 0: strict
        ([10.0, 11.0, 12.0, 9.9], False),
        ([1.0, 10.0, 11.0, 12.0, 10.5], True),  # the base is n sessions back, not the first bar
        ([11.0, 12.0, 10.5], False),  # fewer than n + 1 bars: off
    ],
)
def test_abs_mom_rule_hand_checked(closes, on):
    h = {"SPY": hist("SPY", closes)}
    got = run(TIMING, h, last_day(h["SPY"]), T("SPY", "SPY", "abs_mom", 3))
    assert got == ((full("SPY", f"{closes[-1]:.4f}"),) if on else ())


def test_always_ignores_the_signal_and_n():
    spy = hist("SPY", [5.0])
    assert run(TIMING, {"SPY": spy}, D0, T("SPY", "SPY", "always", 1)) == (full("SPY", "5"),)
    qqq = hist("QQQ", [7.25, 7.5])
    d = last_day(qqq)
    assert run(TIMING, {"QQQ": qqq}, d, T("QQQ", "SPY", "always", 200)) == (full("QQQ", "7.5"),)


def test_hold_can_differ_from_the_signal():
    qqq = hist("QQQ", [50.0, 50.1, 50.25])
    up = {"SPY": hist("SPY", [1.0, 2.0, 3.0]), "QQQ": qqq}
    down = {"SPY": hist("SPY", [3.0, 2.0, 1.0]), "QQQ": qqq}
    d = last_day(qqq)
    p = T("QQQ", "SPY", "sma", 3)
    assert run(TIMING, up, d, p) == (full("QQQ", "50.25"),)
    assert run(TIMING, down, d, p) == ()
    assert run(TIMING, down, d, p, frozenset({"QQQ"})) == ()  # off: a held hold is signal-exited


# ---- missing bars and the held passthrough -------------------------------------------------------


def test_a_hold_without_a_bar_on_d_is_never_a_new_target():
    days = session_days(3)
    history = {"SPY": hist("SPY", [1.0, 2.0, 3.0], days=days), "QQQ": hist("QQQ", [40.0, 41.0], days=days[:2])}
    p = T("QQQ", "SPY", "sma", 3)
    assert run(TIMING, history, days[2], p) == ()
    # held: kept at its latest close before d, so the engine does not sell on a data gap
    assert run(TIMING, history, days[2], p, frozenset({"QQQ"})) == (full("QQQ", "41"),)
    assert run(TIMING, {"SPY": history["SPY"]}, days[2], p, frozenset({"QQQ"})) == ()  # no history at all


def test_a_signal_without_a_bar_on_d_keeps_only_what_is_held():
    days = session_days(4)
    spy = drop_days(hist("SPY", [1.0, 2.0, 3.0, 4.0], days=days), [days[3]])
    qqq = hist("QQQ", [40.0, 41.0, 42.0, 43.0], days=days)
    p = T("QQQ", "SPY", "sma", 3)
    assert run(TIMING, {"SPY": spy, "QQQ": qqq}, days[3], p) == ()
    assert run(TIMING, {"SPY": spy, "QQQ": qqq}, days[3], p, frozenset({"QQQ"})) == (full("QQQ", "43"),)
    # the signal is the hold and has no bar dated d: a held position is kept at its last close
    same = T("SPY", "SPY", "sma", 3)
    assert run(TIMING, {"SPY": spy}, days[3], same) == ()
    assert run(TIMING, {"SPY": spy}, days[3], same, frozenset({"SPY"})) == (full("SPY", "3"),)
    assert run(TIMING, {"QQQ": qqq}, days[3], p) == ()  # the signal's history is absent: unknown


@pytest.mark.parametrize("held", [NONE, frozenset({"SPY"}), frozenset({"BIL"}), frozenset({"SPY", "BIL"})])
def test_held_does_not_change_a_known_decision(held):
    up = {"SPY": hist("SPY", [1.0, 2.0, 3.0])}
    down = {"SPY": hist("SPY", [3.0, 2.0, 1.0])}
    d = last_day(up["SPY"])
    p = T("SPY", "SPY", "sma", 3)
    assert run(TIMING, up, d, p, held) == (full("SPY", "3"),)
    assert run(TIMING, down, d, p, held) == ()


# ---- F11: the turn-of-month window ---------------------------------------------------------------


@pytest.mark.parametrize(
    "session, before, after, on",
    [
        # March 2018 ends on Maundy Thursday (Good Friday 2018-03-30 closed)
        (date(2018, 3, 28), 1, 3, False),
        (date(2018, 3, 29), 1, 3, True),
        (date(2018, 4, 2), 1, 3, True),
        (date(2018, 4, 4), 1, 3, True),
        (date(2018, 4, 5), 1, 3, False),
        # Good Friday 2021-04-02 inside the first sessions of April: Apr 1, 5, 6
        (date(2021, 3, 30), 1, 3, False),
        (date(2021, 3, 31), 1, 3, True),
        (date(2021, 4, 1), 1, 3, True),
        (date(2021, 4, 5), 1, 3, True),
        (date(2021, 4, 6), 1, 3, True),
        (date(2021, 4, 7), 1, 3, False),
        # New Year: Dec 31 2018, then Jan 2, 3, 4 2019
        (date(2018, 12, 28), 1, 3, False),
        (date(2018, 12, 31), 1, 3, True),
        (date(2019, 1, 2), 1, 3, True),
        (date(2019, 1, 4), 1, 3, True),
        (date(2019, 1, 7), 1, 3, False),
        # a short month (February 2019 ends Thursday the 28th), two sessions before
        (date(2019, 2, 26), 2, 3, False),
        (date(2019, 2, 27), 2, 3, True),
        (date(2019, 2, 28), 2, 3, True),
        (date(2019, 3, 1), 2, 3, True),
        (date(2019, 3, 5), 2, 3, True),
        (date(2019, 3, 6), 2, 3, False),
        # a month ending on a weekend (March 2019 ends Sunday the 31st)
        (date(2019, 3, 28), 1, 3, False),
        (date(2019, 3, 29), 1, 3, True),
        # Independence Day inside the first four sessions of July 2019: Jul 1, 2, 3, 5
        (date(2019, 7, 3), 1, 4, True),
        (date(2019, 7, 5), 1, 4, True),
        (date(2019, 7, 8), 1, 4, False),
        # Hurricane Sandy closed Oct 29–30 2012: the last two sessions of October are Oct 26 and 31
        (date(2012, 10, 25), 2, 3, False),
        (date(2012, 10, 26), 2, 3, True),
        (date(2012, 10, 31), 2, 3, True),
        # one side switched off
        (date(2019, 1, 31), 0, 3, False),
        (date(2019, 1, 2), 1, 0, False),
        (date(2019, 1, 31), 1, 0, True),
    ],
)
def test_turn_of_month_window(session, before, after, on):
    assert turn_of_month(session, before, after) is on


@pytest.mark.parametrize("day", [date(2018, 3, 30), date(2019, 1, 5), date(2019, 1, 1)])
def test_turn_of_month_rejects_a_non_session(day):
    with pytest.raises(ValueError):
        turn_of_month(day, 1, 3)


def test_calendar_trades_the_next_session():
    days = sessions(date(2018, 1, 2), date(2018, 4, 30))
    spy = hist("SPY", [100.0 + 0.25 * t for t in range(len(days))], days=days)
    p = CalendarParams("SPY", 1, 3)
    on = [d for d in sessions(date(2018, 3, 20), date(2018, 4, 10)) if run(CALENDAR, {"SPY": spy}, d, p)]
    # decided on d for S = next_session(d): Mar 28 -> Mar 29 (last of March), Mar 29 -> Apr 2 (over Good
    # Friday), Apr 2 -> Apr 3, Apr 3 -> Apr 4; Apr 4 -> Apr 5 is the 4th session of April
    assert on == [date(2018, 3, 28), date(2018, 3, 29), date(2018, 4, 2), date(2018, 4, 3)]
    d = date(2018, 3, 29)
    (t,) = run(CALENDAR, {"SPY": spy}, d, p)
    assert t == Target("SPY", Decimal("1"), Decimal(f"{float(spy.close[spy.index_of(d)]):.4f}"))


def test_calendar_out_of_window_exits_even_a_held_position():
    days = sessions(date(2018, 1, 2), date(2018, 4, 30))
    spy = hist("SPY", [100.0 + 0.25 * t for t in range(len(days))], days=days)
    assert run(CALENDAR, {"SPY": spy}, date(2018, 4, 4), CalendarParams("SPY"), frozenset({"SPY"})) == ()


def test_calendar_trend_gate():
    days = sessions(date(2018, 1, 2), date(2018, 4, 30))
    up = hist("SPY", [100.0 + 0.25 * t for t in range(len(days))], days=days)
    down = hist("SPY", [200.0 - 0.25 * t for t in range(len(days))], days=days)
    flat = hist("SPY", [150.0] * len(days), days=days)
    qqq = hist("QQQ", [50.0 + 0.1 * t for t in range(len(days))], days=days)
    d = date(2018, 3, 29)  # in the window (S = Apr 2)
    gated = CalendarParams("QQQ", 1, 3, ("SPY", 20))
    q_last = f"{float(qqq.close[qqq.index_of(d)]):.4f}"
    assert run(CALENDAR, {"SPY": up, "QQQ": qqq}, d, gated) == (full("QQQ", q_last),)
    assert run(CALENDAR, {"SPY": down, "QQQ": qqq}, d, gated) == ()
    assert run(CALENDAR, {"SPY": flat, "QQQ": qqq}, d, gated) == ()  # close == SMA: strict
    assert run(CALENDAR, {"SPY": down, "QQQ": qqq}, d, gated, frozenset({"QQQ"})) == ()
    # the trend instrument has no bar dated d: unknown -> keep only what is held
    gap = drop_days(up, [d])
    assert run(CALENDAR, {"SPY": gap, "QQQ": qqq}, d, gated) == ()
    assert run(CALENDAR, {"SPY": gap, "QQQ": qqq}, d, gated, frozenset({"QQQ"})) == (full("QQQ", q_last),)
    # too little trend history: off
    short = CalendarParams("QQQ", 1, 3, ("SPY", len(sessions(date(2018, 1, 2), d)) + 1))
    assert run(CALENDAR, {"SPY": up, "QQQ": qqq}, d, short) == ()


# ---- P4 identity and no look-ahead ---------------------------------------------------------------

CONTRACT_PARAMS = [
    (TIMING, T("SPY", "SPY", "sma", 50)),
    (TIMING, T("QQQ", "SPY", "sma", 20)),
    (TIMING, T("SPY", "SPY", "month_sma", 3)),
    (TIMING, T("QQQ", "QQQ", "abs_mom", 30)),
    (TIMING, T("SPY", "SPY", "always", 1)),
    (CALENDAR, CalendarParams("SPY", 1, 3, None)),
    (CALENDAR, CalendarParams("QQQ", 2, 2, ("SPY", 20))),
]
CONTRACT_IDS = ["sma50", "qqq-on-spy", "month-sma3", "abs-mom30", "always", "tom", "tom-trend"]


def contract_set() -> tuple[list[date], dict[str, History]]:
    """~14 months of waves (the signals flip), QQQ with a gap, BIL flat."""
    days = session_days(300, date(2018, 1, 2))
    spy = [100.0 + 12.0 * math.sin(t / 17.0) + 0.04 * t for t in range(300)]
    qqq = [60.0 + 9.0 * math.sin(t / 11.0 + 1.0) + 0.03 * t for t in range(300)]
    return days, {
        "SPY": hist("SPY", spy, days=days),
        "QQQ": drop_days(hist("QQQ", qqq, days=days), days[150:153] + [days[220]]),
        "BIL": hist("BIL", [91.5] * 300, days=days),
    }


@pytest.mark.parametrize("allocator, params", CONTRACT_PARAMS, ids=CONTRACT_IDS)
def test_p4_identity_and_no_look_ahead(allocator, params):
    """Prepared == single-window == full history; changing or deleting every bar dated >= S changes nothing."""
    days, history = contract_set()
    prepared = allocator.prepare(history)
    hold = allocator.holds(params)[0]
    on = off = 0
    for s in days[60:]:
        d = prev_session(s)
        changed = {k: mutate_from(h, s) for k, h in history.items()}
        cut = {k: truncate_before(h, s) for k, h in history.items()}
        for held in (NONE, frozenset({hold}), frozenset({"BIL"})):
            base = allocator.targets(history, NO_MEMBERS, d, held, params)
            assert allocator.targets({k: h.upto(d) for k, h in history.items()}, NO_MEMBERS, d, held, params) == base
            assert allocator.targets_prepared(prepared, NO_MEMBERS, d, held, params) == base, d
            assert allocator.targets(changed, NO_MEMBERS, d, held, params) == base, d
            assert allocator.targets(cut, NO_MEMBERS, d, held, params) == base, d
            assert allocator.targets_prepared(allocator.prepare(changed), NO_MEMBERS, d, held, params) == base, d
            assert len(base) <= 1 and sum(t.weight for t in base) <= 1
            for t in base:
                h = history[t.symbol]
                i = h.index_of(d)
                if i is not None:
                    assert t.last == Decimal(f"{float(h.close[i]):.4f}")
                else:
                    assert t.symbol in held  # a gap: only a held symbol is kept
        on += bool(allocator.targets(history, NO_MEMBERS, d, NONE, params))
        off += not allocator.targets(history, NO_MEMBERS, d, NONE, params)
    assert on > 0  # not vacuous
    if params != T("SPY", "SPY", "always", 1):
        assert off > 0  # the signal flips inside the window


def test_the_mutation_does_change_a_decision_read_at_s():
    # Guards test_p4_identity_and_no_look_ahead: the same mutation, read at data_date = S, matters.
    days, history = contract_set()
    p = T("SPY", "SPY", "sma", 50)
    differs = 0
    for s in days[60:]:
        changed = {k: mutate_from(h, s) for k, h in history.items()}
        differs += run(TIMING, changed, s, p) != run(TIMING, history, s, p)
    assert differs > 0


def test_allocatorkit_contract():
    """The shared phase-2 checkers agree (tests/allocatorkit.py; plan index D-E)."""
    from allocatorkit import assert_no_lookahead, assert_p4_identity

    days, history = contract_set()
    data_dates = [prev_session(s) for s in days[60:]]
    for allocator, params in CONTRACT_PARAMS:
        held_sets = [NONE, frozenset({allocator.holds(params)[0]})]
        assert assert_p4_identity(allocator, history, lambda d: NO_MEMBERS, data_dates, held_sets, [params]) > 0
        assert assert_no_lookahead(allocator, history, lambda d: NO_MEMBERS, days[60::10], held_sets, [params]) > 0
