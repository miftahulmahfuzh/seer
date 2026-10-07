"""Grid, in-sample selection and the P3 gate (handover §3 "Tuning" and "Gate verdict")."""

from __future__ import annotations

import itertools
import math
from datetime import date
from decimal import Decimal

from seer_engine import dates
from seer_engine.backtest.metrics import MINUS, Metrics, checklist
from seer_engine.backtest.tuning import (
    GRID_LIMIT,
    GRID_RSI,
    GRID_SL,
    GRID_TP,
    IS_START,
    MAX_DRAWDOWN,
    MIN_PROFIT_FACTOR,
    OOS_START,
    GridRow,
    gate,
    grid,
    qualifies,
    select,
)
from seer_engine.strategies.a import DESIGN_PARAMS, AParams


def M(ret, pf=1.5, dd=0.10, trades=120):
    return Metrics(total_return=ret, win_rate=0.6, profit_factor=pf, max_drawdown=dd, trades=trades, months=70.0)


def rows_with(*metrics):
    g = grid()
    return [GridRow(params=g[i], metrics=m) for i, m in enumerate(metrics)]


# --------------------------------------------------------------------------- constants and grid


def test_windows():
    assert IS_START == date(2015, 10, 19)
    assert OOS_START == date(2022, 1, 3)
    assert dates.prev_session(OOS_START) == date(2021, 12, 31)


def test_grid_is_the_declared_81_in_nested_order():
    g = grid()
    assert len(g) == 81
    assert len(set(g)) == 81
    expected = [
        (r, l, t, s) for r, l, t, s in itertools.product(GRID_RSI, GRID_LIMIT, GRID_TP, GRID_SL)
    ]
    assert [(p.rsi_max, p.limit_atr, p.tp_atr, p.sl_atr) for p in g] == expected
    assert (g[0].rsi_max, g[0].limit_atr, g[0].tp_atr, g[0].sl_atr) == (5.0, Decimal("0.25"), Decimal("0.75"), Decimal("1.0"))
    assert (g[1].sl_atr, g[3].tp_atr, g[9].limit_atr, g[27].rsi_max) == (Decimal("1.5"), Decimal("1.0"), Decimal("0.5"), 10.0)
    assert g[40] == DESIGN_PARAMS
    assert all(p.min_dollar_volume == DESIGN_PARAMS.min_dollar_volume for p in g)
    assert grid() == g  # deterministic


def test_grid_values_are_the_handover_values():
    assert GRID_RSI == (5.0, 10.0, 15.0)
    assert GRID_LIMIT == (Decimal("0.25"), Decimal("0.5"), Decimal("0.75"))
    assert GRID_TP == (Decimal("0.75"), Decimal("1.0"), Decimal("1.5"))
    assert GRID_SL == (Decimal("1.0"), Decimal("1.5"), Decimal("2.0"))


def test_thresholds_equal_the_web_checklist():
    edge = Metrics(total_return=0.1, win_rate=0.5, profit_factor=MIN_PROFIT_FACTOR, max_drawdown=MAX_DRAWDOWN, trades=1, months=1.0)
    items = checklist(edge, 0.0)
    assert items[2].ok and items[3].ok
    below = Metrics(total_return=0.1, win_rate=0.5, profit_factor=math.nextafter(MIN_PROFIT_FACTOR, 0), max_drawdown=math.nextafter(MAX_DRAWDOWN, 1), trades=1, months=1.0)
    items = checklist(below, 0.0)
    assert not items[2].ok and not items[3].ok
    assert qualifies(edge) and not qualifies(below)


# --------------------------------------------------------------------------- selection


def test_select_takes_the_highest_return_among_qualified_runs():
    rows = rows_with(
        M(0.30, dd=0.25),  # higher return, drawdown too deep
        M(0.25, pf=1.29),  # profit factor too low
        M(0.20),
        M(0.22, pf=math.inf),  # no loss: qualifies
        M(0.10),
    )
    s = select(rows)
    assert s.qualified is True
    assert s.params == grid()[3]
    assert s.reason.startswith("Grid run #4 has the highest in-sample total return (+22.0%")
    assert "among the 3 of 5 runs" in s.reason
    assert "tied" not in s.reason


def test_select_boundaries_are_inclusive():
    s = select(rows_with(M(0.05, pf=1.3, dd=MAX_DRAWDOWN)))
    assert s.qualified and s.params == grid()[0]


def test_select_ties_break_by_lower_drawdown_then_grid_order():
    s = select(rows_with(M(0.2, dd=0.12), M(0.2, dd=0.08), M(0.2, dd=0.08)))
    assert s.params == grid()[1]
    assert "3 runs tied on return" in s.reason


def test_select_negative_returns_still_pick_the_least_bad_qualified_run():
    s = select(rows_with(M(-0.05), M(-0.02), M(-0.10)))
    assert s.params == grid()[1]
    assert f"({MINUS}2.0%" in s.reason


def test_select_falls_back_to_design_values_when_nothing_qualifies():
    s = select(rows_with(M(0.5, dd=0.25), M(0.4, pf=1.0), M(0.3, pf=None, trades=0)))
    assert s.qualified is False
    assert s.params == DESIGN_PARAMS
    assert s.reason == (
        "No in-sample grid run had max drawdown ≤ 20% and profit factor ≥ 1.3 (0 of 3), "
        "so the design values are kept."
    )
    assert select([]).params == DESIGN_PARAMS


def test_select_fallback_is_used_only_when_nothing_qualifies():
    nothing = rows_with(M(0.5, dd=0.25), M(0.4, pf=1.0))
    sentinel = object()
    s = select(nothing, fallback=sentinel)
    assert s.params is sentinel
    assert s.qualified is False
    assert s.reason == select(nothing).reason  # same words whatever the fallback
    assert select([], fallback=sentinel).params is sentinel
    # With a qualifying row the fallback is ignored: same Selection as without it.
    some = rows_with(M(0.5, dd=0.25), M(0.1), M(0.2))
    assert select(some, fallback=sentinel) == select(some)
    assert select(some, fallback=sentinel).params == grid()[2]
    # The default is DESIGN_PARAMS, exactly as before.
    assert select(nothing) == select(nothing, fallback=DESIGN_PARAMS)
    assert select(nothing).params is DESIGN_PARAMS


def test_select_is_deterministic():
    rows = rows_with(*(M(0.01 * (i % 7), dd=0.05 + 0.001 * i) for i in range(81)))
    assert select(rows) == select(list(rows))


# --------------------------------------------------------------------------- gate


def spy(ret):
    return Metrics(total_return=ret, win_rate=None, profit_factor=None, max_drawdown=0.25, trades=0, months=57.0)


def test_gate_passes_only_when_all_three_hold():
    v = gate(M(0.40, pf=1.45, dd=0.098), spy(0.35))
    assert v.passed is True
    assert [c.label for c in v.checks] == ["Beats SPY", "Profit factor ≥ 1.3", "Max drawdown ≤ 20%"]
    assert v.sentence == (
        "Strategy A passes the P3 gate: out of sample it returned +40.0% against +35.0% for "
        "total-return SPY, with profit factor 1.45 and max drawdown 9.8%."
    )


def test_gate_fails_on_each_condition_alone():
    assert gate(M(0.30), spy(0.35)).passed is False
    assert gate(M(0.35), spy(0.35)).passed is False  # strict: a tie does not beat SPY
    assert gate(M(0.40, pf=1.29), spy(0.35)).passed is False
    assert gate(M(0.40, dd=math.nextafter(MAX_DRAWDOWN, 1)), spy(0.35)).passed is False
    assert gate(M(0.40, pf=None, trades=0), spy(0.35)).passed is False
    assert gate(M(0.40), spy(None)).passed is False


def test_gate_failure_sentence_names_every_failed_check_and_stops_p4():
    v = gate(M(-0.032, pf=1.10, dd=0.12), spy(0.401))
    assert v.passed is False
    assert v.sentence == (
        f"Strategy A fails the P3 gate: out of sample it returned {MINUS}3.2% against +40.1% for "
        "total-return SPY, with profit factor 1.10 and max drawdown 12.0%, so it fails on "
        "beating total-return SPY and profit factor ≥ 1.3; P4 must not start until Strategy A is reworked."
    )
    v3 = gate(M(-0.1, pf=1.0, dd=0.3), spy(0.1))
    assert "fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 20%;" in v3.sentence


def test_gate_accepts_an_infinite_profit_factor():
    v = gate(M(0.4, pf=math.inf), spy(0.1))
    assert v.passed and v.checks[1].val == "∞"


def test_gate_and_select_see_only_their_own_window():
    # Structural guard for invariant 6: neither takes the other window's data. select's only
    # extra parameter is the keyword-only fallback params object (P3b), never a metrics window.
    import inspect

    params = inspect.signature(select).parameters
    assert list(params) == ["rows", "fallback"]
    assert params["fallback"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["fallback"].default is DESIGN_PARAMS
    assert list(inspect.signature(gate).parameters) == ["oos", "spy_tr_oos"]


def test_aparams_in_grid_construct_with_decimal_offsets():
    for p in grid():
        assert isinstance(p, AParams)
        assert isinstance(p.limit_atr, Decimal) and isinstance(p.tp_atr, Decimal) and isinstance(p.sl_atr, Decimal)
