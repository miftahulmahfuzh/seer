"""paper.compare and commands.compare (plan roster-promotion-pipeline, phase 3; invariant 6).

The pure module is the reference implementation phase 4 ports to TypeScript, so the ``as_json``
shape, the constants and the selection rule are pinned here by name: a port that diverges makes
the leaderboard and the CLI disagree silently.

Three tests need ``PG_TEST_URL`` (the ``pg`` fixture) and skip without it; the rest are pure.
"""

from __future__ import annotations

import ast
import json
import math
import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import seer_engine.paper.compare as cmp
from seer_engine.backtest.metrics import cagr_between, strategy_metrics
from seer_engine.commands import compare as cli_compare

D = date(2026, 1, 5)

FORBIDDEN_IMPORT_ROOTS = {"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib", "socket"}
FORBIDDEN_ATTRS = {"now", "utcnow", "today", "fromtimestamp"}
FORBIDDEN_CALLS = {"print", "open", "input"}


# --------------------------------------------------------------------------- builders


def curve(start: date, equities: Sequence[float], *, step: int = 1) -> list[tuple[date, float]]:
    """(date, equity) on consecutive calendar days from ``start`` (weekends are irrelevant here:
    the module compares snapshot dates, never trading calendars)."""
    return [(start + timedelta(days=i * step), float(e)) for i, e in enumerate(equities)]


def flat(start: date, n: int, value: float = 100_000.0) -> list[tuple[date, float]]:
    return curve(start, [value] * n)


def drifting(start: date, n: int, per_session: float, value: float = 100_000.0) -> list[tuple[date, float]]:
    """A curve compounding ``per_session`` every session, with a single 1% dip at session n//2 so
    it has non-zero variance and a measurable drawdown."""
    out: list[float] = [value]
    for i in range(1, n):
        out.append(out[-1] * (1.0 + per_session) * (0.99 if i == n // 2 else 1.0))
    return curve(start, out)


def perf(sharpe: float | None, total_return: float, max_drawdown: float) -> cmp.Performance:
    """A ``Performance`` with only the three fields ``_rank_key`` reads set meaningfully."""
    return cmp.Performance(
        start=D,
        end=D + timedelta(days=99),
        sessions=100,
        total_return=total_return,
        cagr=0.1,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
    )


def ranked_row(strategy_id: str, window: cmp.Performance) -> cmp.Row:
    return cmp.Row(
        strategy_id=strategy_id, status="ranked", rank=None, reason=None, window=window, inception=window
    )


# --------------------------------------------------------------------------- 1-13: performance


def test_performance_total_return_and_sessions():
    p = cmp.performance(curve(D, [100.0, 110.0, 121.0]))
    assert p is not None
    assert p.total_return == pytest.approx(0.21)
    assert p.sessions == 3
    assert p.start == D
    assert p.end == D + timedelta(days=2)


def test_cagr_matches_backtest_metrics_cagr_between():
    for n, per in ((40, 0.001), (200, 0.0005), (500, 0.002)):
        c = drifting(D, n, per)
        p = cmp.performance(c)
        assert p is not None
        assert p.cagr == pytest.approx(cagr_between(c[0], c[-1]))


def test_max_drawdown_matches_strategy_metrics():
    c = curve(D, [100.0, 120.0, 90.0, 130.0, 100.0, 140.0])
    p = cmp.performance(c)
    assert p is not None
    assert p.max_drawdown == pytest.approx(strategy_metrics(c, []).max_drawdown)


def test_sharpe_is_annualised_from_session_returns():
    returns = (0.01, -0.005, 0.02, 0.0)
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    expected = mean / math.sqrt(variance) * math.sqrt(252)
    assert cmp._sharpe(returns) == pytest.approx(expected)
    assert cmp.SESSIONS_PER_YEAR == 252


def test_sharpe_is_none_on_a_flat_series():
    p = cmp.performance(flat(D, 10))
    assert p is not None
    assert p.sharpe is None
    assert p.total_return == 0.0
    assert p.max_drawdown == 0.0


def test_sharpe_is_none_with_one_return():
    p = cmp.performance(curve(D, [100.0, 110.0]))
    assert p is not None
    assert p.sharpe is None
    assert p.total_return == pytest.approx(0.1)


def test_performance_is_none_for_a_single_session():
    assert cmp.performance([(D, 1.0)]) is None
    assert cmp.performance([]) is None


def test_cagr_is_none_over_zero_calendar_days():
    # A two-point curve cannot repeat a date (``_points`` refuses it), so this goes through
    # ``_cagr`` directly.
    assert cmp._cagr([(D, 100.0), (D, 110.0)]) is None


def test_points_rejects_out_of_order_dates():
    with pytest.raises(ValueError):
        cmp._points("X", [(D + timedelta(days=1), 100.0), (D, 101.0)])


def test_points_rejects_a_duplicate_date():
    with pytest.raises(ValueError):
        cmp._points("X", [(D, 100.0), (D, 101.0)])


def test_points_rejects_non_positive_equity():
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError):
            cmp._points("X", [(D, 100.0), (D + timedelta(days=1), bad)])


def test_points_rejects_a_datetime():
    with pytest.raises(TypeError):
        cmp._points("X", [(datetime(2026, 1, 5, 12, 0), 100.0)])


def test_points_accepts_decimal_equity():
    pts = cmp._points("X", [(D, Decimal("100000.0000")), (D + timedelta(days=1), Decimal("110000.0000"))])
    assert pts[0][1] == 100_000.0
    assert pts[1][1] == 110_000.0


# --------------------------------------------------------------------------- 14-23: the window


def test_common_window_is_the_intersection_and_is_returned():
    a = drifting(D, 100, 0.001)
    b = drifting(D + timedelta(days=20), 100, 0.001)
    c = cmp.compare({"A": a, "B": b}, min_sessions=10)
    assert c.window is not None
    assert c.window.start == D + timedelta(days=20)
    assert c.window.end == D + timedelta(days=99)
    assert c.window.sessions == 80
    assert {r.strategy_id for r in c.ranked} == {"A", "B"}


def test_a_missed_session_is_dropped_for_everyone():
    a = drifting(D, 100, 0.001)
    missed = a[50][0]
    b = [p for p in drifting(D, 100, 0.0012) if p[0] != missed]
    c = cmp.compare({"A": a, "B": b})
    assert c.window is not None
    assert c.window.sessions == 99
    for row in c.ranked:
        assert row.window is not None
        assert row.window.sessions == 99


def test_a_short_strategy_is_insufficient_and_does_not_shorten_the_window():
    # The FND case: a just-promoted strategy must not collapse the board's window.
    c = cmp.compare(
        {"A": drifting(D, 200, 0.001), "B": drifting(D, 200, 0.0008), "FND": drifting(D, 9, 0.002)}
    )
    assert c.window is not None
    assert c.window.sessions == 200
    assert {r.strategy_id for r in c.ranked} == {"A", "B"}
    (fnd,) = c.insufficient
    assert fnd.strategy_id == "FND"
    assert fnd.rank is None
    assert fnd.window is None
    assert "9 sessions of its own" in fnd.reason


def test_a_retired_strategy_truncates_the_common_window():
    a = drifting(D, 200, 0.001)
    retired = drifting(D, 160, 0.0012)
    c = cmp.compare({"A": a, "R": retired})
    assert c.window is not None
    assert c.window.end == retired[-1][0]
    assert c.window.sessions == 160
    assert {r.strategy_id for r in c.ranked} == {"A", "R"}


def test_a_retired_strategy_that_overlaps_nothing_is_dropped_not_ranked():
    old = drifting(date(2024, 1, 1), 100, 0.001)
    c = cmp.compare({"A": drifting(D, 200, 0.001), "B": drifting(D, 200, 0.0008), "OLD": old})
    assert c.window is not None
    assert c.window.sessions == 200
    assert {r.strategy_id for r in c.ranked} == {"A", "B"}
    (dropped,) = c.insufficient
    assert dropped.strategy_id == "OLD"
    assert "leaves only 0 common sessions" in dropped.reason


def test_two_strategies_with_an_empty_intersection_rank_nothing():
    c = cmp.compare({"A": drifting(D, 100, 0.001), "OLD": drifting(date(2024, 1, 1), 100, 0.001)})
    assert c.window is None
    assert c.ranked == ()
    assert len(c.insufficient) == 2
    for row in c.insufficient:
        assert "fewer than 2 strategies share a window of 63 sessions" == row.reason


def test_no_strategies_yields_an_empty_comparison():
    c = cmp.compare({})
    assert c.window is None
    assert c.rows == ()
    assert c.best is None


def test_one_strategy_is_never_a_ranking():
    c = cmp.compare({"A": drifting(D, 500, 0.001)})
    assert c.ranked == ()
    assert len(c.insufficient) == 1
    assert c.best is None
    assert cmp.MIN_RANKED == 2


def test_selection_is_independent_of_input_order():
    series = {
        "A": drifting(D, 200, 0.001),
        "B": drifting(D, 200, 0.0008),
        "C": drifting(D + timedelta(days=10), 190, 0.0012),
        "FND": drifting(D, 9, 0.002),
    }
    keys = list(series)
    orders = [
        keys,
        keys[::-1],
        [keys[1], keys[0], keys[3], keys[2]],
        [keys[2], keys[3], keys[0], keys[1]],
        [keys[3], keys[2], keys[1], keys[0]],
        [keys[1], keys[3], keys[2], keys[0]],
    ]
    payloads = [cmp.as_json(cmp.compare({k: series[k] for k in order})) for order in orders]
    for payload in payloads[1:]:
        assert payload == payloads[0]


def test_min_sessions_below_two_is_refused():
    with pytest.raises(ValueError):
        cmp.compare({"A": drifting(D, 100, 0.001)}, min_sessions=1)


# --------------------------------------------------------------------------- 24-32: ranking


def test_ranks_by_sharpe_descending():
    # Same dates, same dip shape, different drift: more drift per unit of the same volatility is a
    # higher Sharpe, so the order is known by construction.
    c = cmp.compare(
        {
            "LOW": drifting(D, 150, 0.0002),
            "HIGH": drifting(D, 150, 0.0020),
            "MID": drifting(D, 150, 0.0010),
        }
    )
    assert [r.strategy_id for r in c.ranked] == ["HIGH", "MID", "LOW"]
    assert [r.rank for r in c.ranked] == [1, 2, 3]
    sharpes = [r.window.sharpe for r in c.ranked]
    assert sharpes == sorted(sharpes, reverse=True)


def test_ties_on_sharpe_break_on_total_return_then_drawdown():
    # ``_rank_key`` is the pinned contract; exercising it directly keeps the tie exact instead of
    # depending on two float curves landing on bit-identical Sharpes.
    rows = [
        ranked_row("c-worse-dd", perf(sharpe=1.5, total_return=0.20, max_drawdown=0.12)),
        ranked_row("a-best", perf(sharpe=1.5, total_return=0.30, max_drawdown=0.09)),
        ranked_row("b-better-dd", perf(sharpe=1.5, total_return=0.20, max_drawdown=0.08)),
    ]
    assert [r.strategy_id for r in sorted(rows, key=cmp._rank_key)] == [
        "a-best",
        "b-better-dd",
        "c-worse-dd",
    ]


def test_a_flat_ranked_row_sorts_after_every_finite_sharpe():
    c = cmp.compare({"FLAT": flat(D, 150), "DRIFT": drifting(D, 150, 0.001)})
    assert [r.strategy_id for r in c.ranked] == ["DRIFT", "FLAT"]
    flat_row = c.ranked[1]
    assert flat_row.window is not None
    assert flat_row.window.sharpe is None


def test_best_is_the_rank_one_row():
    c = cmp.compare({"A": drifting(D, 150, 0.001), "B": drifting(D, 150, 0.0005)})
    assert c.best is not None
    assert c.best.strategy_id == c.ranked[0].strategy_id
    assert c.best.rank == 1
    assert cmp.compare({"A": drifting(D, 150, 0.001)}).best is None


def test_insufficient_rows_carry_no_rank_and_no_window():
    c = cmp.compare({"A": drifting(D, 200, 0.001), "B": drifting(D, 200, 0.0008), "Y": drifting(D, 5, 0.001)})
    assert c.insufficient
    for row in c.insufficient:
        assert row.rank is None
        assert row.window is None
        assert isinstance(row.reason, str) and row.reason


def test_every_input_id_appears_exactly_once_in_rows():
    series = {
        "A": drifting(D, 200, 0.001),
        "B": drifting(D, 200, 0.0008),
        "SHORT": drifting(D, 4, 0.001),
        "OLD": drifting(date(2024, 1, 1), 100, 0.001),
    }
    c = cmp.compare(series)
    assert sorted(r.strategy_id for r in c.rows) == sorted(series)


def test_inception_is_the_whole_own_curve_and_differs_from_the_window():
    a = drifting(D, 100, 0.001)
    b = drifting(D + timedelta(days=20), 100, 0.001)
    c = cmp.compare({"A": a, "B": b}, min_sessions=10)
    row = next(r for r in c.ranked if r.strategy_id == "A")
    assert row.inception is not None and row.window is not None
    assert row.inception.sessions == 100
    assert row.inception.sessions > row.window.sessions
    assert row.inception.total_return != row.window.total_return
    assert row.inception.start == D


def test_inception_is_present_for_an_insufficient_row():
    c = cmp.compare(
        {"A": drifting(D, 200, 0.001), "B": drifting(D, 200, 0.0008), "FND": drifting(D, 9, 0.002)}
    )
    (fnd,) = c.insufficient
    assert fnd.inception is not None
    assert fnd.inception.sessions == 9


def test_an_unusable_curve_costs_its_own_row_not_the_table():
    bad = drifting(D, 150, 0.001)
    bad[70] = (bad[70][0], -5.0)
    c = cmp.compare({"A": drifting(D, 150, 0.001), "B": drifting(D, 150, 0.0008), "BAD": bad})
    assert {r.strategy_id for r in c.ranked} == {"A", "B"}
    (broken,) = c.insufficient
    assert broken.strategy_id == "BAD"
    assert "unusable curve" in broken.reason
    assert broken.inception is None


# --------------------------------------------------------------------------- 33-35: output


def test_render_states_the_window_on_its_first_line_and_marks_what_is_not_ranked():
    c = cmp.compare(
        {"A": drifting(D, 200, 0.001), "B": drifting(D, 200, 0.0008), "FND": drifting(D, 9, 0.002)}
    )
    lines = cmp.render(c)
    assert re.match(r"^common window \d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}, \d+ sessions \(minimum 63\)$", lines[0])
    assert any(line.lstrip().startswith("-") and "FND" in line and "not ranked:" in line for line in lines)
    assert sum(1 for line in lines if line.startswith("inception to date")) == 1


def test_render_says_so_when_there_is_no_common_window():
    c = cmp.compare({"A": drifting(D, 100, 0.001), "OLD": drifting(date(2024, 1, 1), 100, 0.001)})
    assert cmp.render(c)[0].startswith("no common window of")


def test_as_json_field_names_units_and_nulls():
    c = cmp.compare(
        {"A": drifting(D, 200, 0.001), "B": drifting(D, 200, 0.0008), "FND": drifting(D, 9, 0.002)}
    )
    payload = cmp.as_json(c)
    assert set(payload) == {"minSessions", "window", "rows"}
    assert payload["minSessions"] == 63
    assert set(payload["window"]) == {"start", "end", "sessions"}
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", payload["window"]["start"])
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", payload["window"]["end"])

    for row in payload["rows"]:
        assert set(row) == {"strategyId", "status", "rank", "reason", "window", "inception"}
        assert row["status"] in {"ranked", "insufficient"}
        for block in (row["window"], row["inception"]):
            if block is None:
                continue
            assert set(block) == {
                "start",
                "end",
                "sessions",
                "totalReturn",
                "cagr",
                "maxDrawdown",
                "sharpe",
            }
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", block["start"])
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", block["end"])

    ranked = [r for r in payload["rows"] if r["status"] == "ranked"]
    assert ranked
    for row in ranked:
        assert 0.0 < row["window"]["totalReturn"] < 1.0  # a fraction, not a percent
        assert row["window"]["start"] == payload["window"]["start"]
        assert row["window"]["end"] == payload["window"]["end"]
        assert row["window"]["sessions"] == payload["window"]["sessions"]

    insufficient = [r for r in payload["rows"] if r["status"] == "insufficient"]
    assert insufficient
    for row in insufficient:
        assert row["rank"] is None
        assert row["window"] is None
        assert isinstance(row["reason"], str)

    assert json.loads(json.dumps(payload)) == payload


# --------------------------------------------------------------------------- P1: purity


def test_compare_module_has_no_clock_randomness_or_io():
    """The executable form of the module docstring's 'Pure' claim (cf. test_sim_purity.py)."""
    path = Path(cmp.__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []
    for node in ast.walk(tree):
        where = f"{path.name}:{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS or alias.name == "seer_engine.bars":
                    problems.append(f"{where} import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in FORBIDDEN_IMPORT_ROOTS or node.module == "seer_engine.bars":
                problems.append(f"{where} from {node.module} import ...")
            if node.module == "seer_engine" and any(a.name == "bars" for a in node.names):
                problems.append(f"{where} from seer_engine import bars")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            problems.append(f"{where} .{node.attr}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            problems.append(f"{where} {node.func.id}()")
    assert problems == []


# --------------------------------------------------------------------------- D1-D3: the CLI edge

SEEDED = ("SPY", "A", "F4-MOM12-N20-TREND")


def _seed(conn, n: int, start: date = D) -> None:
    """``n`` consecutive snapshots for each seeded strategy; equity drifts so Sharpe is defined."""
    for i, strategy_id in enumerate(SEEDED):
        equity = 100_000.0
        for j in range(n):
            equity *= 1.0 + 0.001 * (i + 1) * (-1.0 if j % 7 == 3 else 1.0)
            conn.execute(
                "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd)"
                " VALUES (%s, %s, %s, %s)",
                (strategy_id, start + timedelta(days=j), Decimal("0.0000"), round(Decimal(equity), 4)),
            )
    conn.commit()


def test_execute_reads_equity_snapshots_and_prints_the_window(pg, capsys):
    _seed(pg, 120)
    assert cli_compare.execute(pg, min_sessions=63) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("common window")
    assert "120 sessions (minimum 63)" in out[0]
    from psycopg.pq import TransactionStatus

    assert pg.info.transaction_status == TransactionStatus.IDLE


def test_execute_excludes_ids(pg, capsys):
    _seed(pg, 120)
    assert cli_compare.execute(pg, min_sessions=63, exclude=("SPY",)) == 0
    out = capsys.readouterr().out
    assert "SPY" not in out
    assert "SPY" not in cli_compare.read_series(pg, exclude=("SPY",))
    assert "SPY" in cli_compare.read_series(pg)


def test_require_window_exits_1_without_a_common_window(pg, capsys):
    _seed(pg, 10)
    assert cli_compare.execute(pg, min_sessions=63) == 0
    capsys.readouterr()
    assert cli_compare.execute(pg, min_sessions=63, require_window=True) == 1
    capsys.readouterr()
    assert cli_compare.execute(pg, min_sessions=63, as_json=True) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["window"] is None
    assert all(r["status"] == "insufficient" for r in payload["rows"])


# --------------------------------------------------------------------------- contributions
#
# Money the owner adds is not a return. He deposits 5,000,000 IDR on the 25th of each month on
# top of a 10,000,000 IDR start (his decision, relayed 2026-10-08), and a book that is handed it
# would otherwise report the deposit as performance. Inert today: zero sessions stepped and
# paper_contributions is empty, so every figure below is bit-identical without the argument.


def test_a_deposit_is_not_a_return():
    # 1000 -> 1312.50 on the session a 312.50 deposit lands: the strategy returned 0%, not +31%.
    points = ((date(2026, 9, 28), 1000.0), (date(2026, 9, 29), 1312.50))
    assert cmp._returns(points) == (0.3125,)                                   # today: wrong
    assert cmp._returns(points, {date(2026, 9, 29): 312.50}) == (0.0,)         # with the deposit out
    # And an unfunded curve is untouched, which is every strategy on the roster today.
    assert cmp._returns(points, {}) == cmp._returns(points)


def test_a_deposit_on_the_opening_session_is_the_baseline_not_a_return():
    """``_returns`` starts at the second point, so ``_deposited`` must skip the first too."""
    points = ((date(2026, 9, 28), 1000.0), (date(2026, 9, 29), 1010.0))
    opening = {date(2026, 9, 28): 500.0}
    assert cmp._deposited(points, opening) == 0.0
    assert cmp._returns(points, opening) == cmp._returns(points)
    assert cmp.performance(points, opening).cagr is not None


def test_performance_suppresses_cagr_for_a_window_that_was_fed():
    points = tuple(curve(D, [1000.0, 1312.50, 1325.0, 1330.0]))
    deposits = {points[1][0]: 312.50}

    clean = cmp.performance(points)
    assert clean.deposited == 0.0
    assert clean.cagr is not None

    fed = cmp.performance(points, deposits)
    assert fed.deposited == 312.50
    # Compound growth off the endpoints would count the owner's own money as growth.
    assert fed.cagr is None
    # The session returns -- and so Sharpe -- have it removed; the raw curve figures do not.
    assert fed.sharpe != clean.sharpe
    assert fed.total_return == clean.total_return
    assert fed.max_drawdown == clean.max_drawdown


def test_compare_threads_deposits_per_strategy_and_leaves_the_others_alone():
    series = {"A": curve(D, [100.0 * 1.002 ** i for i in range(80)]),
              "B": curve(D, [100.0 * 1.001 ** i for i in range(80)])}
    fed_day = series["A"][40][0]
    series["A"] = [(d, e + (50.0 if d >= fed_day else 0.0)) for d, e in series["A"]]

    plain = cmp.compare(series)
    with_deposit = cmp.compare(series, deposits={"A": {fed_day: 50.0}})

    rows = {r.strategy_id: r for r in with_deposit.rows}
    assert rows["A"].window.deposited == 50.0
    assert rows["A"].window.cagr is None
    # B received nothing, so every one of its figures is bit-identical to the no-deposit run.
    before = {r.strategy_id: r for r in plain.rows}["B"]
    assert rows["B"].window == before.window
    assert rows["B"].inception == before.inception
    assert rows["B"].window.deposited == 0.0


def test_an_empty_deposits_mapping_changes_nothing_at_all():
    series = {"A": curve(D, [100.0 * 1.002 ** i for i in range(80)]),
              "B": curve(D, [100.0 * 1.001 ** i for i in range(80)])}
    assert cmp.compare(series, deposits={}) == cmp.compare(series)


def test_render_says_when_a_figure_carries_money_the_owner_added():
    series = {"A": curve(D, [100.0 * 1.002 ** i for i in range(80)]),
              "B": curve(D, [100.0 * 1.001 ** i for i in range(80)])}
    fed_day = series["A"][40][0]
    lines = cmp.render(cmp.compare(series, deposits={"A": {fed_day: 50.0}}))
    note = [ln for ln in lines if "money added during the window" in ln]
    assert len(note) == 1 and "A (+50.00 USD)" in note[0]
    assert any("money-weighted return" in ln for ln in lines)
    # Nothing is said when nobody was fed.
    assert not [ln for ln in cmp.render(cmp.compare(series)) if "money added" in ln]


def test_as_json_shape_is_unchanged_by_deposits():
    """The published shape is pinned and ported to TypeScript: ``deposited`` stays Python-side."""
    series = {"A": curve(D, [100.0 * 1.002 ** i for i in range(80)]),
              "B": curve(D, [100.0 * 1.001 ** i for i in range(80)])}
    fed_day = series["A"][40][0]
    payload = cmp.as_json(cmp.compare(series, deposits={"A": {fed_day: 50.0}}))
    for row in payload["rows"]:
        for block in (row["window"], row["inception"]):
            if block is None:
                continue
            assert set(block) == {
                "start", "end", "sessions", "totalReturn", "cagr", "maxDrawdown", "sharpe",
            }


def test_read_deposits_takes_credited_rows_only(pg):
    """An accrued-but-uncredited row has reached no equity snapshot, so it must not be subtracted."""
    from seer_engine.paper import store as paper_store

    due, settled = date(2026, 9, 26), date(2026, 9, 30)
    paper_store.record_contribution(
        pg, "A", due_date=due, amount_idr=Decimal("5000000.00"), usd_idr=Decimal("16000.0000")
    )
    assert cli_compare.read_deposits(pg, ["A"]) == {"A": {}}  # recorded, not yet credited

    paper_store.init_paper_state(
        pg, "A", paper_start=date(2026, 9, 29), cash0=Decimal("1250.0000"), usd_idr=Decimal("16000.0000")
    )
    pg.execute(
        "UPDATE paper_contributions SET applied_at = now() WHERE strategy_id = %s AND due_date = %s",
        ("A", due),
    )
    landed = paper_store.read_contribution(pg, "A", due).session_date
    assert cli_compare.read_deposits(pg, ["A"]) == {"A": {landed: 312.50}}
    assert cli_compare.read_deposits(pg, ["B"]) == {"B": {}}
    assert settled > landed  # the deposit landed before the window this book will report on
