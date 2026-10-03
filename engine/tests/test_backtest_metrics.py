"""Backtest metrics: parity with web/lib/metrics.ts (handover §6 item 6) plus CAGR, days held
and exit reasons. Every expected string was produced by node 20 from metrics.ts's own code."""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest

from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import (
    DASH,
    INFINITY,
    MINUS,
    Metrics,
    avg_days_held,
    cagr_between,
    checklist,
    curve_metrics,
    exit_reason_counts,
    fmt_pct,
    fmt_pf,
    fmt_signed_pct,
    forced_closes,
    run_metrics,
    strategy_metrics,
    to_fixed,
)
from seer_engine.backtest.runner import RunResult
from seer_engine.sim import Event, Order, Snapshot

D = date.fromisoformat


def snaps(vals):
    """metrics.test.ts ``snaps``: equity i dated 2026-07-01 + i (UTC)."""
    return [(date(2026, 7, 1) + timedelta(days=i), float(v)) for i, v in enumerate(vals)]


# --------------------------------------------------------------------------- parity: strategyMetrics


def test_parity_computes_return_win_rate_profit_factor_drawdown_and_trades():
    m = strategy_metrics(snaps([1000, 1100, 990, 1050]), [30, -10, 20, -10])
    assert m.total_return == pytest.approx(0.05, abs=0.005)
    assert m.win_rate == pytest.approx(0.5, abs=0.005)
    assert m.profit_factor == pytest.approx(2.5, abs=0.005)
    assert m.max_drawdown == pytest.approx(0.1, abs=0.005)  # 1100 -> 990
    assert m.trades == 4
    # bit-exact with JS (node: 1050/1000-1, (1100-990)/1100, 50/20)
    assert m.total_return == 0.050000000000000044
    assert m.max_drawdown == 0.1
    assert m.profit_factor == 2.5
    assert m.win_rate == 0.5


def test_parity_returns_nulls_with_no_data():
    m = strategy_metrics([], [])
    assert m.total_return is None
    assert m.win_rate is None
    assert m.profit_factor is None
    assert m.max_drawdown is None
    assert m.trades == 0
    assert m.months == 0
    assert m.cagr is None


def test_parity_infinite_profit_factor_when_nothing_lost():
    assert strategy_metrics(snaps([1, 2]), [5]).profit_factor == math.inf


def test_parity_measures_months_of_forward_testing():
    m = strategy_metrics([(D("2026-07-06"), 1.0), (D("2026-10-05"), 1.0)], [])
    assert m.months == pytest.approx(3.0, abs=0.05)
    assert m.months == 2.9894875164257555  # node: (Date.parse(b)-Date.parse(a))/86400000/30.44


def test_zero_pnl_is_a_loss_like_the_web():
    m = strategy_metrics(snaps([1, 1]), [0.0])
    assert m.win_rate == 0.0
    assert m.profit_factor == math.inf  # grossLoss is -0, and -0 === 0


def test_sums_run_left_to_right_like_reduce():
    m = strategy_metrics(snaps([1, 1]), [0.1, 0.2, 0.3, -0.3])
    assert m.profit_factor == ((0.0 + 0.1 + 0.2) + 0.3) / 0.3
    assert m.profit_factor == 2.0000000000000004  # math.fsum would give exactly 2.0


# --------------------------------------------------------------------------- parity: checklist


BASE = Metrics(total_return=0.068, win_rate=0.58, profit_factor=1.42, max_drawdown=0.079, trades=84, months=3.0)


def test_parity_checklist_passes_only_when_every_rule_holds():
    items = checklist(BASE, 0.046)
    assert [i.ok for i in items] == [True, False, True, True, True]
    assert items[1].val == "84 / 100"
    assert all(i.ok for i in checklist(Metrics(**{**BASE.__dict__, "trades": 120}), 0.046))
    assert checklist(Metrics(**{**BASE.__dict__, "max_drawdown": 0.16, "trades": 120}), 0.046)[4].ok is False


def test_parity_checklist_labels_and_values_match_the_web_strings():
    items = checklist(BASE, 0.046)
    assert [(i.label, i.val) for i in items] == [
        ("≥ 3 months forward", "3.0 mo"),
        ("≥ 100 trades", "84 / 100"),
        ("Beats SPY", "+6.8 vs +4.6"),
        ("Profit factor ≥ 1.3", "1.42"),
        ("Max drawdown ≤ 15%", "7.9%"),
    ]


def test_checklist_edge_strings():
    m = Metrics(total_return=-0.0123, win_rate=None, profit_factor=None, max_drawdown=None, trades=0, months=91 / 30.44)
    items = checklist(m, None)
    assert items[0].val == "2.9 mo" and items[0].ok is False  # floor to 0.1, like the web
    assert items[2].val == DASH and items[2].ok is False
    assert items[3].val == DASH and items[3].ok is False
    assert items[4].val == DASH and items[4].ok is False
    assert checklist(m, 0.0)[2].val == f"{MINUS}1.2 vs +0.0"
    inf = Metrics(total_return=0.2, win_rate=1.0, profit_factor=math.inf, max_drawdown=0.15, trades=1, months=1.0)
    items = checklist(inf, 0.2)
    assert items[3].val == INFINITY and items[3].ok is True
    assert items[4].val == "15.0%" and items[4].ok is True  # ≤ is inclusive
    assert items[2].ok is False  # beats SPY is strict
    assert checklist(Metrics(**{**inf.__dict__, "profit_factor": 1.3}), 0.1)[3].ok is True


def test_checklist_total_return_none_counts_as_zero_in_the_value_but_never_beats():
    m = Metrics(total_return=None, win_rate=None, profit_factor=None, max_drawdown=None, trades=0, months=0.0)
    item = checklist(m, -0.5)[2]
    assert item.val == f"+0.0 vs {MINUS}50.0"
    assert item.ok is False


# --------------------------------------------------------------------------- toFixed port


@pytest.mark.parametrize(
    ("x", "digits", "js"),
    [  # every right-hand side printed by node 20
        (0.125, 2, "0.13"),
        (2.5, 0, "3"),
        (1.005, 2, "1.00"),
        (-0.04, 1, "-0.0"),
        (-0.0, 1, "0.0"),
        (8.345, 2, "8.35"),
        (1.45, 1, "1.4"),
        (0.079 * 100, 1, "7.9"),
        (abs(0.068 * 100), 1, "6.8"),
        (0.16 * 100, 1, "16.0"),
        (0, 2, "0.00"),
    ],
)
def test_to_fixed_matches_javascript(x, digits, js):
    assert to_fixed(x, digits) == js


def test_to_fixed_refuses_what_js_would_not_print_plainly():
    for bad in (math.inf, math.nan, 1e21):
        with pytest.raises(ValueError):
            to_fixed(bad, 1)
    with pytest.raises(TypeError):
        to_fixed(Decimal("1.5"), 1)  # type: ignore[arg-type]


def test_formatters():
    assert fmt_signed_pct(0.068) == "+6.8%"
    assert fmt_signed_pct(-0.0123) == f"{MINUS}1.2%"
    assert fmt_signed_pct(None) == DASH
    assert fmt_pct(0.079) == "7.9%"
    assert fmt_pct(0.012, 2) == "1.20%"
    assert fmt_pf(math.inf) == INFINITY
    assert fmt_pf(None) == DASH
    assert fmt_pf(1.425) == "1.43"  # node: (1.425).toFixed(2)


# --------------------------------------------------------------------------- CAGR


def test_cagr_is_actual_365_25():
    first, last = (D("2020-01-01"), 100.0), (D("2021-01-01"), 121.0)  # 366 days
    assert cagr_between(first, last) == (121.0 / 100.0) ** (1.0 / (366 / 365.25)) - 1.0
    two_years = cagr_between((D("2019-01-01"), 1.0), (D("2021-01-01"), 4.0))  # 731 days
    assert two_years == pytest.approx(1.0, abs=0.002)


def test_cagr_undefined_cases():
    assert cagr_between((D("2020-01-01"), 1.0), (D("2020-01-01"), 2.0)) is None
    assert cagr_between((D("2020-01-01"), 0.0), (D("2021-01-01"), 2.0)) is None
    assert cagr_between((D("2020-01-01"), 1.0), (D("2021-01-01"), -1.0)) is None
    assert cagr_between((D("2020-01-01"), 1.0), (D("2021-01-01"), 0.0)) == -1.0
    assert strategy_metrics(snaps([1000]), []).cagr is None  # a single snapshot spans 0 days


def test_strategy_metrics_fills_cagr_from_the_same_snapshots():
    m = strategy_metrics([(D("2020-01-01"), 100.0), (D("2020-07-01"), 90.0), (D("2021-01-01"), 121.0)], [])
    assert m.cagr == cagr_between((D("2020-01-01"), 100.0), (D("2021-01-01"), 121.0))


# --------------------------------------------------------------------------- run / curve metrics


def _closed(symbol, slot, reason, pnl, days):
    return Order(
        session_date=D("2026-07-01"),
        slot=slot,
        symbol=symbol,
        last_price=Decimal("10.0000"),
        limit_price=Decimal("9.5000"),
        tp_price=Decimal("10.5000"),
        sl_price=Decimal("8.7500"),
        shares=10,
        status="closed",
        fill_date=D("2026-07-01"),
        fill_price=Decimal("9.5000"),
        days_held=days,
        exit_date=D("2026-07-03"),
        exit_price=Decimal("10.5000"),
        exit_reason=reason,
        pnl_usd=Decimal(pnl),
    )


def _run(closed, events=()):
    s = [Snapshot(d, Decimal(e), Decimal(e)) for d, e in [
        (D("2026-07-01"), "1000.0000"),
        (D("2026-07-02"), "1100.0000"),
        (D("2026-07-03"), "990.0000"),
        (D("2026-07-04"), "1050.0000"),
    ]]
    return RunResult(
        strategy_id="A",
        params=None,
        start=D("2026-07-02"),
        end=D("2026-07-04"),
        usd_idr=Decimal("16000.0000"),
        initial_cash=Decimal("1000.0000"),
        snapshots=tuple(s),
        events=tuple(events),
        closed=tuple(closed),
        open_at_end=(),
        rejections=(),
    )


def test_run_metrics_matches_strategy_metrics_and_adds_days_and_reasons():
    closed = [
        _closed("AAA", 1, "tp", "30.0000", 2),
        _closed("BBB", 2, "sl", "-10.0000", 3),
        _closed("CCC", 3, "time", "20.0000", 5),
        _closed("DDD", 4, "tp", "-10.0000", 1),
    ]
    forced = Event(D("2026-07-03"), "exit", closed[2], forced=True, cash_usd=Decimal("104.8950"))
    normal = Event(D("2026-07-03"), "exit", closed[0], forced=False, cash_usd=Decimal("104.8950"))
    r = _run(closed, events=(normal, forced))
    m = run_metrics(r)
    web = strategy_metrics(snaps([1000, 1100, 990, 1050]), [30, -10, 20, -10])
    assert (m.total_return, m.win_rate, m.profit_factor, m.max_drawdown, m.trades, m.months) == (
        web.total_return, web.win_rate, web.profit_factor, web.max_drawdown, web.trades, web.months,
    )
    assert m.avg_days_held == 2.75
    assert m.exit_reasons == (("tp", 2), ("sl", 1), ("time", 1), ("gap", 0))
    assert forced_closes(r) == 1


def test_run_metrics_with_no_trades():
    m = run_metrics(_run([]))
    assert m.trades == 0 and m.win_rate is None and m.profit_factor is None
    assert m.avg_days_held is None
    assert m.exit_reasons == (("tp", 0), ("sl", 0), ("time", 0), ("gap", 0))
    assert avg_days_held([]) is None
    assert exit_reason_counts([]) == (("tp", 0), ("sl", 0), ("time", 0), ("gap", 0))


def test_curve_metrics_has_no_trades():
    c = BenchmarkCurve(
        name="spy_tr",
        snapshots=(
            Snapshot(D("2026-07-01"), Decimal("1000.0000"), Decimal("1000.0000")),
            Snapshot(D("2026-07-02"), Decimal("1.0000"), Decimal("1020.0000")),
            Snapshot(D("2026-07-03"), Decimal("1.0000"), Decimal("1010.0000")),
        ),
        shares=2,
        cash=Decimal("1.0000"),
        dividends_usd=Decimal("0.0000"),
    )
    m = curve_metrics(c)
    assert m.total_return == 1010.0 / 1000.0 - 1
    assert m.max_drawdown == (1020.0 - 1010.0) / 1020.0
    assert m.trades == 0 and m.profit_factor is None and m.win_rate is None
    assert m.exit_reasons == () and m.avg_days_held is None
