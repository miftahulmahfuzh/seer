"""Report rendering (handover §6 items 6, 7, 9): deterministic, every section, the machine lines,
CSV and SVG, all from a small synthetic BacktestReport."""

from __future__ import annotations

import dataclasses
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

import pytest

from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import Metrics, curve_metrics, run_metrics
from seer_engine.backtest.report import (
    FROZEN_KEY,
    SELECTED_KEY,
    BacktestReport,
    WindowResult,
    equity_csv,
    equity_svg,
    params_line,
    parse_params_line,
    render_markdown,
    report_stem,
)
from seer_engine.backtest.runner import RunResult, YearGap
from seer_engine.backtest.tuning import GridRow, gate, grid, select
from seer_engine.sim import Event, Order, Snapshot
from seer_engine.strategies.a import DESIGN_PARAMS

D = date.fromisoformat
CASH0 = "1250.0000"
FULL_DATES = ["2021-12-29", "2021-12-30", "2021-12-31", "2022-01-03", "2022-01-04", "2022-01-05"]
STRAT = [CASH0, "1262.5000", "1240.0000", "1255.0000", "1270.0000", "1280.0000"]
SPY_P = [CASH0, "1251.0000", "1249.0000", "1253.0000", "1252.0000", "1256.0000"]
SPY_T = [CASH0, "1251.0000", "1249.5000", "1254.0000", "1253.5000", "1258.0000"]


def _snaps(ds, vals):
    return tuple(Snapshot(D(d), Decimal(v), Decimal(v)) for d, v in zip(ds, vals))


def _order(symbol, slot, status, reason=None, pnl=None, days=0):
    filled = status in ("open", "closed")
    return Order(
        session_date=D("2021-12-30"),
        slot=slot,
        symbol=symbol,
        last_price=Decimal("10.0000"),
        limit_price=Decimal("9.5000"),
        tp_price=Decimal("10.5000"),
        sl_price=Decimal("8.7500"),
        shares=10,
        status=status,
        fill_date=D("2021-12-30") if filled else None,
        fill_price=Decimal("9.5000") if filled else None,
        days_held=days if filled else 0,
        exit_date=D("2022-01-03") if status == "closed" else None,
        exit_price=Decimal("10.5000") if status == "closed" else None,
        exit_reason=reason,
        pnl_usd=Decimal(pnl) if pnl is not None else None,
    )


def _run(ds, vals, params, closed=(), events=(), open_at_end=(), rejections=()):
    return RunResult(
        strategy_id="A",
        params=params,
        start=D(ds[1]),
        end=D(ds[-1]),
        usd_idr=Decimal("16000.0000"),
        initial_cash=Decimal(CASH0),
        snapshots=_snaps(ds, vals),
        events=tuple(events),
        closed=tuple(closed),
        open_at_end=tuple(open_at_end),
        rejections=tuple(rejections),
    )


def _curve(name, ds, vals, dividends="0.0000"):
    return BenchmarkCurve(
        name=name,
        snapshots=_snaps(ds, vals),
        shares=2,
        cash=Decimal("12.3400"),
        dividends_usd=Decimal(dividends),
    )


def _window(name, lo, hi, params, **run_kw):
    ds, s, p, t = FULL_DATES[lo:hi], STRAT[lo:hi], SPY_P[lo:hi], SPY_T[lo:hi]
    s = [CASH0] + s[1:]
    p = [CASH0] + p[1:]
    t = [CASH0] + t[1:]
    return WindowResult(
        name=name,
        run=_run(ds, s, params, **run_kw),
        spy_price=_curve("spy_price", ds, p),
        spy_tr=_curve("spy_tr", ds, t, dividends="1.5000"),
    )


def _grid_rows():
    return tuple(
        GridRow(
            params=p,
            metrics=Metrics(
                total_return=0.01 * i - 0.2,
                win_rate=0.5,
                profit_factor=1.0 + 0.01 * i,
                max_drawdown=0.10 + (0.1 if i % 2 else 0.0),
                trades=100 + i,
                months=74.0,
                cagr=0.001 * i,
                avg_days_held=2.5,
                exit_reasons=(("tp", 1), ("sl", 1), ("time", 0), ("gap", 0)),
            ),
        )
        for i, p in enumerate(grid())
    )


def build_report(frozen=None):
    rows = _grid_rows()
    selection = select(rows)
    params = selection.params
    closed = (
        _order("AAA", 1, "closed", "tp", "30.0000", 2),
        _order("CCC", 2, "closed", "time", "-10.0000", 3),
    )
    forced = Event(D("2022-01-03"), "exit", closed[1], forced=True, cash_usd=Decimal("94.8950"))
    full = _window(
        "Full window", 0, 6, params,
        closed=closed, events=(forced,),
        open_at_end=(_order("BBB", 3, "open", days=2),),
        rejections=(("held", 1), ("no_slot", 2)),
    )
    ins = _window("In-sample", 0, 3, params)
    oos = _window("Out-of-sample", 2, 6, params, closed=closed[:1])
    verdict = gate(run_metrics(oos.run), curve_metrics(oos.spy_tr))
    return BacktestReport(
        data_end=D("2026-10-02"),
        bars_rows=1_817_429,
        symbols_with_bars=663,
        grid_rows=rows,
        selection=selection,
        frozen_params=DESIGN_PARAMS if frozen is None else frozen,
        in_sample=ins,
        out_of_sample=oos,
        full=full,
        survivorship=(
            YearGap(year=2021, member_sessions=1000, missing=12, missing_never_fetched=10, missing_other=2),
            YearGap(year=2022, member_sessions=500, missing=0, missing_never_fetched=0, missing_other=0),
        ),
        never_fetched_members=133,
        verdict=verdict,
    )


def _section(md: str, heading: str) -> str:
    start = md.index(heading)
    nxt = md.find("\n## ", start + 1)
    return md[start: nxt if nxt != -1 else len(md)]


# --------------------------------------------------------------------------- basics


def test_report_stem():
    assert report_stem(D("2026-10-02")) == "2026-10-02-strategy-a"


def test_selection_in_fixture_is_the_last_qualifying_row():
    r = build_report()
    assert r.selection.qualified and r.selection.params == grid()[80]


def test_outputs_are_deterministic():
    a, b = build_report(), build_report()
    assert render_markdown(a) == render_markdown(b)
    assert equity_csv(a) == equity_csv(b)
    assert equity_svg(a) == equity_svg(b)
    assert render_markdown(a) == render_markdown(a)


# --------------------------------------------------------------------------- markdown


def test_markdown_contains_every_required_section_in_order():
    md = render_markdown(build_report())
    headings = [
        "# Strategy A backtest, data through 2026-10-02",
        "**Gate verdict:** ",
        "## Data",
        "## Method",
        "## In-sample grid (81 runs, 2021-12-30 → 2021-12-31)",
        "## Selection",
        "## Results",
        "### In-sample (2021-12-30 → 2021-12-31, 2 sessions)",
        "### Out-of-sample (2022-01-03 → 2022-01-05, 3 sessions)",
        "### Full window (2021-12-30 → 2022-01-05, 5 sessions)",
        "## Go-live checklist (what a backtest can evaluate)",
        "## Survivorship bias",
        "## Open positions at end",
        "## Equity curves",
        "## Gate verdict",
    ]
    positions = [md.index(h) for h in headings]
    assert positions == sorted(positions)
    assert md.endswith("\n") and not md.endswith("\n\n")
    assert "nan" not in md.lower().replace("financ", "")


def test_markdown_data_provenance():
    md = _section(render_markdown(build_report()), "## Data")
    assert "- Data end (last bar loaded): 2026-10-02" in md
    assert "- Bar rows loaded: 1,817,429" in md
    assert "- Symbols with bars: 663" in md
    assert "| Full window | 2021-12-30 → 2022-01-05 | 5 | 16,000.0000 | 1,250.00 |" in md


def test_markdown_method_states_cagr_convention_and_grid():
    md = _section(render_markdown(build_report()), "## Method")
    assert "Actual/365.25" in md
    assert "RSI {5, 10, 15} × limit {0.25, 0.5, 0.75} × TP {0.75, 1.0, 1.5} × SL {1.0, 1.5, 2.0} ATR" in md
    assert "20,000,000 IDR" in md


def test_markdown_lists_all_81_grid_rows_in_order():
    sec = _section(render_markdown(build_report()), "## In-sample grid")
    rows = [line for line in sec.splitlines() if line[:3].strip("| ").isdigit()]
    assert [int(line.split("|")[1]) for line in rows] == list(range(1, 82))
    assert rows[80].endswith("| yes | selected |")
    assert rows[1].endswith("| no |  |")  # odd rows have drawdown 0.20
    assert sum(1 for line in rows if line.endswith("| selected |")) == 1


def test_markdown_grid_marks_the_fallback():
    r = build_report()
    rows = tuple(GridRow(params=g.params, metrics=dataclasses.replace(g.metrics, max_drawdown=0.5)) for g in r.grid_rows)
    sel = select(rows)
    assert sel.params == DESIGN_PARAMS and not sel.qualified
    windows = {
        k: dataclasses.replace(w, run=dataclasses.replace(w.run, params=DESIGN_PARAMS))
        for k, w in (("in_sample", r.in_sample), ("out_of_sample", r.out_of_sample), ("full", r.full))
    }
    md = render_markdown(dataclasses.replace(r, grid_rows=rows, selection=sel, **windows))
    assert "| kept (fallback) |" in _section(md, "## In-sample grid")
    assert sel.reason in md


def test_machine_lines_round_trip():
    r = build_report()
    md = render_markdown(r)
    assert parse_params_line(md, FROZEN_KEY) == DESIGN_PARAMS.as_dict()
    assert parse_params_line(md, SELECTED_KEY) == r.selection.params.as_dict()
    assert list(parse_params_line(md, SELECTED_KEY)) == list(r.selection.params.as_dict())  # key order kept
    assert md.count("\nfrozen-params: ") == 1 and md.count("\nselected-params: ") == 1
    assert params_line(FROZEN_KEY, DESIGN_PARAMS) in md.splitlines()
    assert "differs from the selection" in md


def test_frozen_params_change_only_their_own_lines():
    a = render_markdown(build_report()).splitlines()
    r = build_report()
    b = render_markdown(build_report(frozen=r.selection.params)).splitlines()
    changed = [(x, y) for x, y in zip(a, b) if x != y]
    assert len(a) == len(b)
    assert all(
        x.startswith("frozen-params: ") or x.startswith("Frozen in code") or x.startswith("| ")
        for x, _ in changed
    )
    assert len(changed) == 2 + sum(
        1 for k in DESIGN_PARAMS.as_dict() if DESIGN_PARAMS.as_dict()[k] != r.selection.params.as_dict()[k]
    )
    assert "matches the selection" in "\n".join(b)


def test_parse_params_line_needs_exactly_one():
    with pytest.raises(ValueError):
        parse_params_line("nothing here\n", FROZEN_KEY)
    line = params_line(FROZEN_KEY, DESIGN_PARAMS)
    with pytest.raises(ValueError):
        parse_params_line(f"{line}\n{line}\n", FROZEN_KEY)


def test_markdown_window_tables():
    md = _section(render_markdown(build_report()), "## Results")
    assert md.count("| Metric | Strategy A | SPY price-only | SPY total-return |") == 3
    full = md[md.index("### Full window"):]
    assert "| Ending equity (USD) | 1,280.00 | 1,256.00 | 1,258.00 |" in full
    assert "| Total return | +2.4% | +0.5% | +0.6% |" in full
    assert "| Trades (closed) | 2 | — | — |" in full
    assert "| Avg days held | 2.50 | — | — |" in full
    assert "| Exits: take profit | 1 | — | — |" in full
    assert "| Exits: time stop | 1 | — | — |" in full
    assert "| Exits: gap at the open | 0 | — | — |" in full
    assert "| Forced closes (bars ended; inside time stop) | 1 | — | — |" in full
    assert "| Open at end | 1 | — | — |" in full
    assert "| SPY dividends credited (USD) | — | — | 1.50 |" in full
    assert "Picks the simulator rejected: held 1, no_slot 2." in full
    for row in ("| CAGR |", "| Win rate |", "| Profit factor |", "| Max drawdown |"):
        assert row in full


def test_markdown_checklist_has_the_backtest_items():
    md = _section(render_markdown(build_report()), "## Go-live checklist")
    for label in ("≥ 3 months forward", "≥ 100 trades", "Beats SPY", "Profit factor ≥ 1.3", "Max drawdown ≤ 15%"):
        assert f"| {label} |" in md
    assert "| Passed a 10-year backtest under identical rules | #5, decided by the gate |" in md
    assert "forward-only: information" in md


def test_markdown_survivorship_in_plain_words_with_per_year_gaps():
    md = _section(render_markdown(build_report()), "## Survivorship bias")
    assert "133 stocks were in the S&P 500 or the Nasdaq-100" in md
    assert "probably better than reality" in md
    assert "| 2021 | 1,000 | 12 | 10 | 2 | 1.20% |" in md
    assert "| 2022 | 500 | 0 | 0 | 0 | 0.00% |" in md
    assert "| All | 1,500 | 12 | 10 | 2 | 0.80% |" in md


def test_markdown_open_positions():
    md = _section(render_markdown(build_report()), "## Open positions at end")
    assert "| BBB | open | 3 | 2021-12-30 | 2021-12-30 | 9.5000 | 10 | 9.5000 | 10.5000 | 8.7500 | 2 |" in md
    assert md.count("None.") == 2  # in-sample and out-of-sample hold nothing


def test_markdown_verdict_sentence_twice_and_checks():
    r = build_report()
    md = render_markdown(r)
    assert md.count(r.verdict.sentence) == 2
    assert md.startswith(f"# Strategy A backtest, data through 2026-10-02\n\n**Gate verdict:** {r.verdict.sentence}\n")
    v = _section(md, "## Gate verdict")
    assert "- Beats SPY: " in v and "- Profit factor ≥ 1.3: " in v and "- Max drawdown ≤ 15%: " in v


def test_markdown_links_the_curve_files():
    md = render_markdown(build_report())
    assert "](2026-10-02-strategy-a-equity.svg)" in md
    assert "(2026-10-02-strategy-a-equity.csv)" in md


def test_render_refuses_runs_not_on_the_selection():
    r = build_report()
    bad = dataclasses.replace(r.out_of_sample, run=dataclasses.replace(r.out_of_sample.run, params=grid()[0]))
    with pytest.raises(ValueError, match="Out-of-sample"):
        render_markdown(dataclasses.replace(r, out_of_sample=bad))


def test_render_refuses_misaligned_curves():
    r = build_report()
    short = dataclasses.replace(r.full.spy_tr, snapshots=r.full.spy_tr.snapshots[:-1])
    bad = dataclasses.replace(r, full=dataclasses.replace(r.full, spy_tr=short))
    for fn in (render_markdown, equity_csv, equity_svg):
        with pytest.raises(ValueError, match="Full window"):
            fn(bad)


# --------------------------------------------------------------------------- CSV


def test_equity_csv_is_the_full_window_wide():
    assert equity_csv(build_report()) == (
        "date,strategy_a,spy_price,spy_tr\n"
        "2021-12-29,1250.0000,1250.0000,1250.0000\n"
        "2021-12-30,1262.5000,1251.0000,1251.0000\n"
        "2021-12-31,1240.0000,1249.0000,1249.5000\n"
        "2022-01-03,1255.0000,1253.0000,1254.0000\n"
        "2022-01-04,1270.0000,1252.0000,1253.5000\n"
        "2022-01-05,1280.0000,1256.0000,1258.0000\n"
    )


# --------------------------------------------------------------------------- SVG


def test_equity_svg_is_self_contained_and_themed():
    svg = equity_svg(build_report())
    root = ET.fromstring(svg.encode("utf-8"))
    ns = "{http://www.w3.org/2000/svg}"
    assert root.tag == f"{ns}svg"
    assert root.get("viewBox") == "0 0 960 460"
    lines = root.findall(f"{ns}polyline")
    assert [pl.get("class") for pl in lines] == ["line s1", "line s2", "line s3"]
    assert all(len(pl.get("points").split()) == 6 for pl in lines)
    style = root.find(f"{ns}style").text
    assert "@media (prefers-color-scheme: dark)" in style
    assert root.find(f"{ns}rect").get("class") == "bg"
    assert "<script" not in svg and "href" not in svg
    assert "nan" not in svg.lower() and "inf" not in svg.lower()
    texts = [t.text for t in root.iter(f"{ns}text")]
    assert "2022" in texts  # one year tick inside the window
    assert any(t and t.startswith("Strategy A +2.4%") for t in texts)
    assert any(t and t.startswith("SPY price-only") for t in texts)
    assert any(t and t.startswith("SPY total-return") for t in texts)


def test_equity_svg_needs_two_dates():
    r = build_report()
    one = lambda c: dataclasses.replace(c, snapshots=c.snapshots[:1])  # noqa: E731
    full = dataclasses.replace(
        r.full,
        run=dataclasses.replace(r.full.run, snapshots=r.full.run.snapshots[:1]),
        spy_price=one(r.full.spy_price),
        spy_tr=one(r.full.spy_tr),
    )
    with pytest.raises(ValueError):
        equity_svg(dataclasses.replace(r, full=full))
