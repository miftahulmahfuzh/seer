"""Walk-forward report rendering (P3b, plan phase 4): section order, machine lines, the fail-only
section, both CSVs, both SVGs, validation and determinism, from a small synthetic report built
with phase 3's API and a reduced combination list (the renderer never assumes 324)."""

from __future__ import annotations

import dataclasses
import json
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

import pytest

from seer_engine import dates
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import Metrics, curve_metrics, fmt_signed_pct, run_metrics
from seer_engine.backtest.runner import RunResult, YearGap
from seer_engine.backtest.tuning import GridRow, grid
from seer_engine.backtest.walkforward import (
    COMBINED,
    SEEN_BEFORE_START,
    WalkForward,
    diagnostics,
    folds,
    gate_p3b,
    schedule,
    select_fold,
    window_metrics,
)
from seer_engine.backtest.wf_report import (
    EQUITY_CSV_HEADER,
    FROZEN_KEY,
    GATE_KEY,
    GRID_CSV_HEADER,
    LAST_FOLD_KEY,
    WalkForwardReport,
    equity_csv,
    grid_csv,
    parse_machine_line,
    render_markdown,
    report_stem,
    top_rows,
    variants_svg,
    equity_svg,
)
from seer_engine.sim import Event, Order, Snapshot
from seer_engine.strategies.a2 import A2_DESIGN_PARAMS, VARIANTS, A2Params

D = date.fromisoformat
CASH0 = "1400.0000"
IS_START = D("2020-01-02")
END = D("2022-01-31")
FOLDS = folds(IS_START, 2021, END)
SESS = [dates.prev_session(FOLDS[0].trade_start)] + dates.sessions(FOLDS[0].trade_start, FOLDS[-1].trade_end)
COMBOS = tuple(A2Params.from_a(v, p) for v in VARIANTS for p in grid()[39:42])  # 12; grid()[40] is the design set
VARIANT_DELTAS = ("0.1000", "0.3000", "-0.1000", "0.2000")
RENDERERS = (render_markdown, equity_csv, grid_csv, equity_svg, variants_svg)


def _snaps(delta: str) -> tuple[Snapshot, ...]:
    base, step = Decimal(CASH0), Decimal(delta)
    return tuple(Snapshot(d, base + step * k, base + step * k) for k, d in enumerate(SESS))


def _closed(symbol, slot, shares, fill, exit_, pnl, fill_date, exit_date, reason, tp, sl):
    return Order(
        session_date=D(fill_date),
        slot=slot,
        symbol=symbol,
        last_price=Decimal(fill),
        limit_price=Decimal(fill),
        tp_price=Decimal(tp),
        sl_price=Decimal(sl),
        shares=shares,
        status="closed",
        fill_date=D(fill_date),
        fill_price=Decimal(fill),
        days_held=2,
        exit_date=D(exit_date),
        exit_price=Decimal(exit_),
        exit_reason=reason,
        pnl_usd=Decimal(pnl),
    )


CLOSED = (
    _closed("AAA", 1, 2, "10.0000", "11.0000", "1.9580", "2021-06-01", "2021-06-03", "tp", "11.0000", "9.0000"),
    _closed("BBB", 2, 5, "20.0000", "19.0000", "-5.1950", "2022-01-10", "2022-01-12", "sl", "21.0000", "19.0000"),
    _closed("CCC", 3, 1, "50.0000", "60.0000", "9.8900", "2022-01-18", "2022-01-20", "time", "60.0000", "45.0000"),
)


def _open(symbol: str) -> Order:
    return Order(
        session_date=D("2022-01-28"),
        slot=4,
        symbol=symbol,
        last_price=Decimal("30.0000"),
        limit_price=Decimal("29.5000"),
        tp_price=Decimal("31.0000"),
        sl_price=Decimal("28.0000"),
        shares=3,
        status="open",
        fill_date=D("2022-01-28"),
        fill_price=Decimal("29.5000"),
        days_held=2,
    )


def _run(params, delta, open_at_end=()) -> RunResult:
    return RunResult(
        strategy_id="A2",
        params=params,
        start=FOLDS[0].trade_start,
        end=FOLDS[-1].trade_end,
        usd_idr=Decimal("15000.0000"),
        initial_cash=Decimal(CASH0),
        snapshots=_snaps(delta),
        events=tuple(Event(o.exit_date, "exit", o) for o in CLOSED),
        closed=CLOSED,
        open_at_end=tuple(open_at_end),
        rejections=(("held", 3), ("no_slot", 7)),
    )


def _curve(name: str, delta: str, dividends: str) -> BenchmarkCurve:
    return BenchmarkCurve(name=name, snapshots=_snaps(delta), shares=3, cash=Decimal("12.3400"), dividends_usd=Decimal(dividends))


def _fold_rows(combos):
    out = []
    for k, _ in enumerate(FOLDS):
        rows = []
        for i, p in enumerate(combos):
            ok = k == 0 and p.variant in ("regime_calm", "regime_calm_floor")
            rows.append(
                GridRow(
                    params=p,
                    metrics=Metrics(
                        total_return=0.01 * (i + 1) - 0.02 * k,
                        win_rate=0.55,
                        profit_factor=1.5 if ok else 1.0,
                        max_drawdown=0.10 if ok else 0.30,
                        trades=100 + i,
                        months=12.0 * (k + 1),
                        cagr=0.005 * (i + 1),
                        avg_days_held=3.0,
                        exit_reasons=(("tp", 1), ("sl", 1), ("time", 0), ("gap", 0)),
                    ),
                )
            )
        out.append(tuple(rows))
    return tuple(out)


def _wf(name, sels, delta, open_at_end=()) -> WalkForward:
    return WalkForward(name=name, folds=FOLDS, selections=sels, run=_run(schedule(FOLDS, sels), delta, open_at_end))


def build_report(*, passed=True, frozen=None, combos=COMBOS, open_symbol="DDD") -> WalkForwardReport:
    rows = _fold_rows(combos)
    combined = _wf(
        COMBINED,
        tuple(select_fold(r) for r in rows),
        "2.0000" if passed else "-0.2000",
        open_at_end=(_open(open_symbol),),
    )
    variants = tuple(
        _wf(v, tuple(select_fold(r, v) for r in rows), d) for v, d in zip(VARIANTS, VARIANT_DELTAS)
    )
    spy_price = _curve("spy_price", "0.4000", "0.0000")
    spy_tr = _curve("spy_tr", "0.5000", "4.5600")
    verdict = gate_p3b(run_metrics(combined.run), curve_metrics(spy_tr), combined.run.start, combined.run.end)
    return WalkForwardReport(
        data_end=END,
        bars_rows=123_456,
        symbols_with_bars=42,
        never_fetched_members=7,
        survivorship=(
            YearGap(year=2020, member_sessions=1000, missing=12, missing_never_fetched=10, missing_other=2),
            YearGap(year=2021, member_sessions=1000, missing=8, missing_never_fetched=6, missing_other=2),
            YearGap(year=2022, member_sessions=200, missing=0, missing_never_fetched=0, missing_other=0),
        ),
        is_start=IS_START,
        folds=FOLDS,
        fold_rows=rows,
        combined=combined,
        variants=variants,
        spy_price=spy_price,
        spy_tr=spy_tr,
        verdict=verdict,
        frozen_params=frozen,
    )


def _section(md: str, heading: str) -> str:
    start = md.index(heading)
    nxt = md.find("\n## ", start + 1)
    return md[start: nxt if nxt != -1 else len(md)]


def _table_rows(text: str) -> list[list[str]]:
    """Body rows of every Markdown table in ``text`` whose first cell is a number."""
    out = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| ") and cells and cells[0].isdigit():
            out.append(cells)
    return out


HEADINGS = [
    "# Strategy A2 walk-forward (P3b), data through 2022-01-31",
    "**P3b gate verdict:** ",
    "## Data",
    "## Method",
    "## Folds",
    "### 2021",
    "### 2022",
    "## Walk-forward results",
    "## Per-variant walk-forward",
    "## Diagnostics",
    "## Seen before (information only, not out-of-sample)",
    "## Go-live checklist (what a backtest can evaluate)",
    "## Survivorship bias",
    "## Open positions at end",
    "## Equity curves",
    "## Gate verdict",
    "## Machine-readable lines",
]
FAIL_HEADING = "## If the gate failed: what the owner decides next"


# --------------------------------------------------------------------------- basics


def test_fixture_takes_both_branches():
    r = build_report()
    assert r.verdict.passed and not build_report(passed=False).verdict.passed
    assert r.combined.selections[0].qualified and r.combined.selections[0].params == COMBOS[11]
    assert not r.combined.selections[1].qualified and r.combined.selections[1].params == A2_DESIGN_PARAMS


def test_report_stem():
    assert report_stem(D("2026-10-02")) == "2026-10-02-strategy-a2-walkforward"


def test_every_output_is_deterministic():
    for passed in (True, False):
        a, b = build_report(passed=passed), build_report(passed=passed)
        for fn in RENDERERS:
            assert fn(a) == fn(b)


# --------------------------------------------------------------------------- markdown structure


def test_sections_in_order_on_a_pass():
    md = render_markdown(build_report())
    positions = [md.index(h) for h in HEADINGS]
    assert positions == sorted(positions)
    assert FAIL_HEADING not in md
    assert md.endswith("\n") and not md.endswith("\n\n")
    assert "nan" not in md.lower().replace("financ", "")


def test_fail_section_only_on_a_fail_and_before_the_machine_lines():
    md = render_markdown(build_report(passed=False))
    sec = _section(md, FAIL_HEADING)
    assert md.index("## Gate verdict") < md.index(FAIL_HEADING) < md.index("## Machine-readable lines")
    for option in ("**(a)**", "**(b)**", "**(c)**"):
        assert option in sec
    assert "Strategy B" in sec and "buy-and-hold" in sec and "time stop" in sec
    assert "P4 stays blocked" in sec


def test_verdict_sentence_at_top_and_in_its_section():
    r = build_report(passed=False)
    md = render_markdown(r)
    assert md.startswith(
        f"# Strategy A2 walk-forward (P3b), data through 2022-01-31\n\n**P3b gate verdict:** {r.verdict.sentence}\n"
    )
    assert md.count(r.verdict.sentence) == 2
    v = _section(md, "## Gate verdict")
    assert "- Beats SPY: fail" in v


# --------------------------------------------------------------------------- machine lines


def test_machine_lines_on_a_pass():
    r = build_report()
    md = render_markdown(r)
    assert parse_machine_line(md, GATE_KEY) == "passed"
    last = parse_machine_line(md, LAST_FOLD_KEY)
    assert last == json.dumps(r.combined.selections[-1].params.as_dict())
    assert list(json.loads(last))[0] == "variant"
    assert parse_machine_line(md, FROZEN_KEY) == "null"
    assert "none yet. The gate passed" in md


def test_machine_lines_on_a_fail():
    md = render_markdown(build_report(passed=False))
    assert parse_machine_line(md, GATE_KEY) == "failed"
    assert parse_machine_line(md, FROZEN_KEY) == "null"
    assert "none. The gate failed, so nothing is deployed." in md


def test_frozen_params_line_and_note():
    last = build_report().combined.selections[-1].params
    md = render_markdown(build_report(frozen=last))
    assert json.loads(parse_machine_line(md, FROZEN_KEY)) == last.as_dict()
    assert "matches the last fold's selection" in md
    other = render_markdown(build_report(frozen=COMBOS[0]))
    assert "differs from the last fold's selection" in other


def test_machine_lines_sit_together_in_one_text_fence():
    lines = render_markdown(build_report()).splitlines()
    i = lines.index("```text")
    assert lines[i + 1].startswith(f"{GATE_KEY}: ")
    assert lines[i + 2].startswith(f"{LAST_FOLD_KEY}: ")
    assert lines[i + 3].startswith(f"{FROZEN_KEY}: ")
    assert lines[i + 4] == "```"
    assert lines.count("```text") == 1


def test_parse_machine_line_needs_exactly_one():
    with pytest.raises(ValueError):
        parse_machine_line("nothing here\n", GATE_KEY)
    with pytest.raises(ValueError):
        parse_machine_line("p3b-gate: passed\np3b-gate: failed\n", GATE_KEY)
    assert parse_machine_line("x\np3b-gate: passed\ny\n", GATE_KEY) == "passed"


# --------------------------------------------------------------------------- method and folds


def test_method_lists_everything_tried():
    md = _section(render_markdown(build_report()), "## Method")
    for v in VARIANTS:
        assert f"`{v}`" in md
    assert "SMA(200)" in md and "strictly above" in md
    assert "ATR(14) / close ascending" in md
    assert "≥ $10.00" in md
    assert "RSI {5, 10, 15} × limit {0.25, 0.5, 0.75} × TP {0.75, 1.0, 1.5} × SL {1.0, 1.5, 2.0} ATR (81 sets)" in md
    assert "the same 12 combinations" in md
    assert "Folds: 2021, 2022" in md
    assert "trades `control` with the design values" in md
    assert "max drawdown ≤ 15% and profit factor ≥ 1.3" in md
    assert "20,000,000 IDR" in md and "Actual/365.25" in md
    assert "One round only" in md


def test_top_rows_put_qualifying_runs_first():
    rows = build_report().fold_rows
    assert [i + 1 for i in top_rows(rows[0])] == [12, 11, 10, 9, 8, 7, 6, 5, 4, 3]
    assert [i + 1 for i in top_rows(rows[1])] == [12, 11, 10, 9, 8, 7, 6, 5, 4, 3]


def test_fold_sections_have_top_ten_selection_and_reason():
    r = build_report()
    md = render_markdown(r)
    f2021 = md[md.index("### 2021"): md.index("### 2022")]
    top = _table_rows(f2021)
    assert [int(c[1]) for c in top] == [12, 11, 10, 9, 8, 7, 6, 5, 4, 3]
    assert top[0][-1] == "selected" and top[0][2] == "`regime_calm_floor`"
    assert r.combined.selections[0].reason in f2021
    f2022 = _section(md, "### 2022")
    assert r.combined.selections[1].reason in f2022
    assert "The selected combination (#2) is outside the top 10" in f2022  # the fallback is combo #2
    summary = _section(md, "## Folds")
    assert "| 2021 | 2020-01-02 → 2020-12-31 | 2021-01-04 → 2021-12-31 | 6 of 12 |" in summary
    assert "| 0 of 12 | `control` | 10 | 0.5 | 1 | 1.5 | fallback |" in summary


def test_top_table_shrinks_with_fewer_combinations():
    combos = tuple(A2Params.from_a(v, grid()[40]) for v in VARIANTS)
    md = render_markdown(build_report(combos=combos))
    assert "Top 4 of 4 combinations" in md
    assert len(_table_rows(md[md.index("### 2021"): md.index("### 2022")])) == 4


# --------------------------------------------------------------------------- results, variants, diagnostics


def test_results_table_and_year_by_year():
    r = build_report()
    sec = _section(render_markdown(r), "## Walk-forward results")
    assert "| Metric | Strategy A2 walk-forward | SPY price-only | SPY total-return |" in sec
    end = Decimal(CASH0) + Decimal("2.0000") * (len(SESS) - 1)
    assert f"| Ending equity (USD) | {format(end, ',.2f')} |" in sec
    assert "Picks the simulator rejected: held 3, no_slot 7." in sec
    assert "| SPY dividends credited (USD) | — | — | 4.56 |" in sec
    years = _table_rows(sec[sec.index("### Year by year"):])
    assert [c[0] for c in years] == ["2021", "2022"]
    assert years[1][2] == "`control`, RSI 10, limit 0.5, TP 1, SL 1.5 (fallback)"


def test_per_variant_table_and_fold_selections():
    md = _section(render_markdown(build_report()), "## Per-variant walk-forward")
    for name in ("Walk-forward", *(f"`{v}`" for v in VARIANTS), "SPY price-only", "SPY total-return"):
        assert f"| {name} | " in md
    sels = md[md.index("### Fold selections per curve"):]
    assert "| Year | Walk-forward | `control` | `regime` | `regime_calm` | `regime_calm_floor` |" in sels
    rows = _table_rows(sels)
    assert [c[0] for c in rows] == ["2021", "2022"]
    assert rows[0][2].endswith("(fallback)") and not rows[0][3 + 1].endswith("(fallback)")
    assert all(c.endswith("(fallback)") for c in rows[1][1:])


def test_diagnostics_section_uses_phase_3_diagnostics():
    r = build_report()
    sec = _section(render_markdown(r), "## Diagnostics")
    d = diagnostics(r.combined.run)
    assert d.trades == 3 and d.small_trades == 2  # AAA (2 shares) and CCC (1 share)
    lines = sec.splitlines()
    assert any(line.startswith("| Trades with < 3 shares | 2 (66.7%) |") for line in lines)
    assert any(line.startswith("| Trades (closed) | 3 |") for line in lines)
    assert "### P/L by exit reason (trades · USD)" in sec
    assert "| Exits: take profit | 1 · +1.96 |" in sec
    assert "| Exits: stop loss | 1 · −5.20 |" in sec
    assert "| Exits: gap at the open | 0 · 0.00 |" in sec
    years = _table_rows(sec[sec.index("### P/L by exit year"):])
    assert [c[0] for c in years] == ["2021", "2022"]


def test_seen_before_is_a_labelled_slice():
    r = build_report()
    sec = _section(render_markdown(r), "## Seen before (information only, not out-of-sample)")
    assert "not out-of-sample any more" in sec and "never feed the gate" in sec
    assert f"({SEEN_BEFORE_START.isoformat()} → 2022-01-31," in sec
    m = window_metrics(r.combined.run, SEEN_BEFORE_START)
    assert f"| Walk-forward | {fmt_signed_pct(m.total_return)} |" in sec
    checklist_sec = _section(render_markdown(r), "## Go-live checklist")
    assert "| Passed a 10-year backtest under identical rules | #5, decided by the P3b gate | pass: P3b gate verdict | — |" in checklist_sec


def test_survivorship_note():
    md = _section(render_markdown(build_report()), "## Survivorship bias")
    assert "7 stocks were in the S&P 500 or the Nasdaq-100" in md
    assert "from 2020-01-02 to 2022-01-31" in md
    assert "probably better than reality" in md
    assert "| All | 2,200 | 20 | 16 | 4 | 0.91% |" in md


def test_open_positions_escape_pipes():
    md = _section(render_markdown(build_report(open_symbol="A|B")), "## Open positions at end")
    assert "| A\\|B | open | 4 | 2022-01-28 | 2022-01-28 | 29.5000 | 3 | 29.5000 | 31.0000 | 28.0000 | 2 |" in md
    assert md.count("None.") == len(VARIANTS)


def test_curves_section_links_all_four_files():
    md = render_markdown(build_report())
    stem = report_stem(END)
    for suffix in ("-equity.svg)", "-variants.svg)", "-equity.csv)", "-grid.csv)"):
        assert f"({stem}{suffix}" in md


# --------------------------------------------------------------------------- CSV


def test_equity_csv_is_wide_and_aligned():
    text = equity_csv(build_report())
    lines = text.splitlines()
    assert lines[0] == EQUITY_CSV_HEADER == "date,walk_forward,control,regime,regime_calm,regime_calm_floor,spy_price,spy_tr"
    assert len(lines) == len(SESS) + 1
    assert lines[1] == f"{SESS[0].isoformat()}," + ",".join([CASH0] * 7)
    assert lines[2].split(",")[1] == "1402.0000"
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_grid_csv_has_every_run_and_one_mark_per_fold():
    r = build_report()
    lines = grid_csv(r).splitlines()
    assert lines[0] == ",".join(GRID_CSV_HEADER)
    assert lines[0].startswith("fold,tune_start,tune_end,combo,variant,rsi_max,")
    assert len(lines) == 1 + len(FOLDS) * len(COMBOS)
    assert sum(1 for line in lines[1:] if line.endswith(",selected")) == 1  # the header also ends in ",selected"
    assert sum(1 for line in lines[1:] if line.endswith(",fallback")) == 1
    first = lines[1].split(",")
    assert first[:5] == ["2021", "2020-01-02", "2020-12-31", "1", "control"]
    assert first[-2:] == ["no", ""]
    assert lines[12].split(",")[3:5] == ["12", "regime_calm_floor"] and lines[12].endswith(",yes,selected")
    assert lines[14].split(",")[:5] == ["2022", "2020-01-02", "2021-12-31", "2", "control"]
    assert lines[14].endswith(",no,fallback")


# --------------------------------------------------------------------------- SVG


NS = "{http://www.w3.org/2000/svg}"


def _check_svg(svg: str, classes: list[str]) -> ET.Element:
    root = ET.fromstring(svg.encode("utf-8"))
    assert root.tag == f"{NS}svg" and root.get("viewBox") == "0 0 960 460"
    lines = root.findall(f"{NS}polyline")
    assert [pl.get("class") for pl in lines] == classes
    assert all(len(pl.get("points").split()) == len(SESS) for pl in lines)
    style = root.find(f"{NS}style").text
    assert "@media (prefers-color-scheme: dark)" in style
    assert root.find(f"{NS}rect").get("class") == "bg"
    assert "<script" not in svg and "href" not in svg
    assert "nan" not in svg.lower() and "inf" not in svg.lower()
    return root


def test_equity_svg_is_self_contained_and_themed():
    root = _check_svg(equity_svg(build_report()), ["line s1", "line s2", "line s3"])
    texts = [t.text or "" for t in root.iter(f"{NS}text")]
    assert "2022" in texts
    assert any(t.startswith("A2 walk-forward +") for t in texts)


def test_variants_svg_has_four_variants_and_spy():
    root = _check_svg(variants_svg(build_report()), ["line v0", "line v1", "line v2", "line v3", "line s3"])
    texts = [t.text or "" for t in root.iter(f"{NS}text")]
    for v in VARIANTS:
        assert any(t.startswith(f"{v} ") for t in texts)


# --------------------------------------------------------------------------- validation


def test_renderers_refuse_misaligned_curves():
    r = build_report()
    bad_run = dataclasses.replace(r.variants[2].run, snapshots=r.variants[2].run.snapshots[:-1])
    bad = dataclasses.replace(
        r, variants=r.variants[:2] + (dataclasses.replace(r.variants[2], run=bad_run),) + r.variants[3:]
    )
    for fn in RENDERERS:
        with pytest.raises(ValueError, match="walk-forward curves"):
            fn(bad)


def test_renderers_refuse_inconsistent_inputs():
    r = build_report()
    uneven = dataclasses.replace(r, fold_rows=(r.fold_rows[0], r.fold_rows[1][:-1]))
    off_schedule = dataclasses.replace(
        r,
        variants=(dataclasses.replace(r.variants[0], run=dataclasses.replace(r.variants[0].run, params=A2_DESIGN_PARAMS)),)
        + r.variants[1:],
    )
    wrong_verdict = dataclasses.replace(r, verdict=dataclasses.replace(r.verdict, passed=False))
    for bad, match in ((uneven, "fold 2022"), (off_schedule, "control"), (wrong_verdict, "verdict")):
        for fn in RENDERERS:
            with pytest.raises(ValueError, match=match):
                fn(bad)
