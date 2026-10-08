"""Strategy B report rendering (P6a, plan phase 5): section order, machine lines, the determinism
switch, the fail-only section, the CSV, the SVG, validation and determinism, from a small synthetic
report built with phase 4's types (real tree and ridge models from phase 1's ``fit``) on a two-fold
window."""

from __future__ import annotations

import dataclasses
import json
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

import numpy as np
import pytest

from seer_engine import dates
from seer_engine.backtest.b_report import (
    EQUITY_CSV_HEADER,
    FROZEN_KEY,
    GATE_KEY,
    GATED_KEY,
    LAST_FOLD_KEY,
    BReport,
    equity_csv,
    equity_svg,
    machine_lines,
    parse_machine_line,
    render_markdown,
    report_stem,
    top_features,
)
from seer_engine.backtest.b_walkforward import (
    B,
    B_LINEAR,
    DECILES,
    BWalkForward,
    CalibrationRow,
    FoldModel,
    calibration,
    gate_p6a,
    model_schedule,
)
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import curve_metrics, fmt_pct, fmt_signed_pct, run_metrics
from seer_engine.backtest.runner import RunResult, YearGap
from seer_engine.backtest.tuning import Selection
from seer_engine.backtest.walkforward import (
    COMBINED,
    SEEN_BEFORE_START,
    WalkForward,
    folds,
    schedule,
    window_metrics,
)
from seer_engine.backtest.wf_report import parse_machine_line as wf_parse_machine_line
from seer_engine.sim import Event, Order, Snapshot
from seer_engine.strategies.a2 import A2_DESIGN_PARAMS
from seer_engine.strategies.b import FEATURE_NAMES, FrozenModel
from seer_engine.strategies.b_model import RIDGE, TREE, fit

D = date.fromisoformat
CASH0 = "1400.0000"
IS_START = D("2020-01-02")
END = D("2022-01-31")
FOLDS = folds(IS_START, 2021, END)
SESS = [dates.prev_session(FOLDS[0].trade_start)] + dates.sessions(FOLDS[0].trade_start, FOLDS[-1].trade_end)
TRADED = len(SESS) - 1
RENDERERS = (render_markdown, equity_csv, equity_svg)


# --------------------------------------------------------------------------- models (fitted once)


def _xy(shift: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(7 + shift)  # tests may draw random numbers; the modules may not
    X = rng.random((600, len(FEATURE_NAMES)))
    y = 0.01 * (X[:, 0] - 0.5) + 0.001 * shift
    return X, y


_DATA = (_xy(0), _xy(1))
TREES = tuple(fit(TREE, X, y) for X, y in _DATA)
RIDGES = tuple(fit(RIDGE, X, y) for X, y in _DATA)


def _imp(shares: dict[str, float]) -> tuple[float, ...]:
    out = [0.0] * len(FEATURE_NAMES)
    for name, share in shares.items():
        out[FEATURE_NAMES.index(name)] = share
    return tuple(out)


IMP_B = _imp(
    {"ret_1": 0.30, "spy_ret_5": 0.25, "ret_20": 0.10, "ret_60": 0.10, "rsi_2": 0.10, "atr_pct": 0.10, "dollar_volume_20": 0.05}
)
IMP_LIN = _imp({"gap": 0.6, "range_pos": 0.4})


def _fold_models(models) -> tuple[FoldModel, ...]:
    return (
        FoldModel(
            fold=FOLDS[0],
            model=models[0],
            rows=1200,
            label_mean=0.0005,
            label_sum=0.6,
            pred_mean=0.0004,
            r2=None,
            positive_share=0.375,
            importance=IMP_B if models[0].kind == TREE else IMP_LIN,
        ),
        FoldModel(
            fold=FOLDS[1],
            model=models[1],
            rows=2400,
            label_mean=-0.00025,
            label_sum=-0.6,
            pred_mean=-0.0001,
            r2=0.0123,
            positive_share=0.25,
            importance=IMP_B if models[1].kind == TREE else IMP_LIN,
        ),
    )


# --------------------------------------------------------------------------- runs and curves


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


def _run(strategy_id: str, params, delta: str, open_at_end=()) -> RunResult:
    return RunResult(
        strategy_id=strategy_id,
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


def _bwf(name: str, models, delta: str, open_at_end=()) -> BWalkForward:
    fms = _fold_models(models)
    return BWalkForward(
        name=name, folds=FOLDS, fold_models=fms, run=_run("B", model_schedule(FOLDS, fms), delta, open_at_end)
    )


def _a2() -> WalkForward:
    sels = tuple(
        Selection(params=A2_DESIGN_PARAMS, qualified=False, reason="No in-sample run qualified.") for _ in FOLDS
    )
    return WalkForward(name=COMBINED, folds=FOLDS, selections=sels, run=_run("A2", schedule(FOLDS, sels), "0.1000"))


def _curve(name: str, delta: str, dividends: str) -> BenchmarkCurve:
    return BenchmarkCurve(name=name, snapshots=_snaps(delta), shares=3, cash=Decimal("12.3400"), dividends_usd=Decimal(dividends))


def _cal(nan_top: bool) -> tuple[CalibrationRow, ...]:
    rows = []
    for k in range(1, DECILES + 1):
        if nan_top and k == DECILES:
            rows.append(
                CalibrationRow(decile=k, rows=0, pred_min=float("nan"), pred_max=float("nan"), pred_mean=float("nan"), label_mean=float("nan"))
            )
            continue
        pmin = (k - 6) * 0.001
        rows.append(
            CalibrationRow(
                decile=k, rows=30, pred_min=pmin, pred_max=pmin + 0.0009, pred_mean=pmin + 0.0005, label_mean=(k - 5) * 0.0008
            )
        )
    return tuple(rows)


def build_report(*, passed=True, determinism_ok=True, frozen=None, open_symbol="DDD") -> BReport:
    b = _bwf(B, TREES, "2.0000" if passed else "-0.2000", open_at_end=(_open(open_symbol),))
    b_linear = _bwf(B_LINEAR, RIDGES, "1.5000" if passed else "-0.3000")
    spy_price = _curve("spy_price", "0.4000", "0.0000")
    spy_tr = _curve("spy_tr", "0.5000", "4.5600")
    gated = B if determinism_ok else B_LINEAR
    g = b if determinism_ok else b_linear
    verdict = gate_p6a(run_metrics(g.run), curve_metrics(spy_tr), g.run.start, g.run.end, gated)
    return BReport(
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
        candidate_rows=50_000,
        labelled_rows=40_000,
        determinism_ok=determinism_ok,
        gated=gated,
        b=b,
        b_linear=b_linear,
        a2=_a2(),
        passed=((B, 40, TRADED), (B_LINEAR, 12, TRADED)),
        calibration=((B, _cal(False)), (B_LINEAR, _cal(True))),
        spy_price=spy_price,
        spy_tr=spy_tr,
        verdict=verdict,
        frozen=frozen,
    )


def _frozen(**changes) -> FrozenModel:
    f = FrozenModel(
        report=f"docs/backtests/{report_stem(END)}.md",
        artifact=f"engine/data/models/{END.isoformat()}-strategy-b.pkl",
        train_end=FOLDS[-1].tune_end,
        sha256="ab" * 32,
    )
    return dataclasses.replace(f, **changes)


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
    "# Strategy B walk-forward (P6a), data through 2022-01-31",
    "**P6a gate verdict:** ",
    "## Data",
    "## Method",
    "## Training per fold",
    "### B (gradient-boosted trees)",
    "### B-linear (ridge regression)",
    "## Walk-forward results",
    "## Year by year",
    "## Diagnostics",
    "### Calibration: B\n",
    "### Calibration: B-linear",
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


def test_fixture_takes_all_branches():
    r = build_report()
    assert r.verdict.passed and not build_report(passed=False).verdict.passed
    assert r.gated == B and r.gated_curve() is r.b
    switched = build_report(determinism_ok=False)
    assert switched.gated == B_LINEAR and switched.gated_curve() is switched.b_linear
    assert switched.verdict.passed and not build_report(passed=False, determinism_ok=False).verdict.passed
    assert [fm.model.kind for fm in r.b.fold_models] == [TREE, TREE]
    assert [fm.model.kind for fm in r.b_linear.fold_models] == [RIDGE, RIDGE]


def test_report_stem_and_keys():
    assert report_stem(D("2026-10-02")) == "2026-10-02-strategy-b-walkforward"
    assert (GATE_KEY, GATED_KEY, LAST_FOLD_KEY, FROZEN_KEY) == (
        "p6a-gate",
        "gated-model",
        "last-fold-model",
        "frozen-model",
    )


def test_every_output_is_deterministic():
    for passed in (True, False):
        for ok in (True, False):
            a = build_report(passed=passed, determinism_ok=ok)
            b = build_report(passed=passed, determinism_ok=ok)
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
    for option in ("**(b)**", "**(c)**", "**(d)**"):
        assert option in sec
    assert "**(a)**" not in sec
    assert "one round" in sec and "P4 stays blocked" in sec
    assert "buy-and-hold" in sec and "time stop" in sec and "Strategy C" in sec
    assert "nan" not in md.lower().replace("financ", "")


def test_verdict_sentence_at_top_and_in_its_section():
    r = build_report(passed=False)
    md = render_markdown(r)
    assert md.startswith(
        f"# Strategy B walk-forward (P6a), data through 2022-01-31\n\n**P6a gate verdict:** {r.verdict.sentence}\n"
    )
    assert md.count(r.verdict.sentence) == 2
    assert "- Beats SPY: fail" in _section(md, "## Gate verdict")


# --------------------------------------------------------------------------- machine lines


def test_machine_lines_on_a_pass():
    r = build_report()
    md = render_markdown(r)
    assert parse_machine_line(md, GATE_KEY) == "passed"
    assert parse_machine_line(md, GATED_KEY) == B
    raw = parse_machine_line(md, LAST_FOLD_KEY)
    last = json.loads(raw)
    fm = r.b.fold_models[-1]
    assert list(last) == ["kind", "digest", "train_end", "rows", "label_sum"]
    assert last == {
        "kind": TREE,
        "digest": fm.model.digest,
        "train_end": "2021-12-31",
        "rows": 2400,
        "label_sum": repr(-0.6),
    }
    assert float(last["label_sum"]) == fm.label_sum
    assert parse_machine_line(md, FROZEN_KEY) == "null"
    assert "none yet. The gate passed" in md
    assert machine_lines(r) == [
        "p6a-gate: passed",
        "gated-model: B",
        f"last-fold-model: {raw}",
        "frozen-model: null",
    ]


def test_machine_lines_on_a_fail():
    md = render_markdown(build_report(passed=False))
    assert parse_machine_line(md, GATE_KEY) == "failed"
    assert parse_machine_line(md, FROZEN_KEY) == "null"
    assert "none. The gate failed, so nothing is deployed" in md


def test_frozen_model_line_and_notes():
    f = _frozen()
    md = render_markdown(build_report(frozen=f))
    raw = parse_machine_line(md, FROZEN_KEY)
    assert list(json.loads(raw)) == ["report", "artifact", "train_end", "sha256"]
    assert json.loads(raw) == {
        "report": "docs/backtests/2022-01-31-strategy-b-walkforward.md",
        "artifact": "engine/data/models/2022-01-31-strategy-b.pkl",
        "train_end": "2021-12-31",
        "sha256": "ab" * 32,
    }
    assert "names this report and the last fold's training cut-off" in md
    other = render_markdown(build_report(frozen=_frozen(train_end=FOLDS[0].tune_end)))
    assert "names a different report or training cut-off" in other
    on_fail = render_markdown(build_report(passed=False, frozen=f))
    assert "set, but the gate failed" in on_fail


def test_machine_lines_sit_together_in_one_text_fence():
    lines = render_markdown(build_report()).splitlines()
    i = lines.index("```text")
    assert lines[i + 1].startswith(f"{GATE_KEY}: ")
    assert lines[i + 2].startswith(f"{GATED_KEY}: ")
    assert lines[i + 3].startswith(f"{LAST_FOLD_KEY}: ")
    assert lines[i + 4].startswith(f"{FROZEN_KEY}: ")
    assert lines[i + 5] == "```"
    assert lines.count("```text") == 1


def test_parse_machine_line_needs_exactly_one():
    with pytest.raises(ValueError):
        parse_machine_line("nothing here\n", GATE_KEY)
    with pytest.raises(ValueError):
        parse_machine_line("p6a-gate: passed\np6a-gate: failed\n", GATE_KEY)
    text = "x\np6a-gate: passed\ny\n"
    assert parse_machine_line(text, GATE_KEY) == wf_parse_machine_line(text, GATE_KEY) == "passed"


# --------------------------------------------------------------------------- method, switch, training


def test_method_states_the_preregistered_design():
    md = _section(render_markdown(build_report()), "## Method")
    for name in FEATURE_NAMES:
        assert f"`{name}`" in md
    assert (
        'HistGradientBoostingRegressor(loss="squared_error", learning_rate=0.05, max_iter=300, '
        "max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0, early_stopping=False, "
        "random_state=0)" in md
    )
    assert "alpha = 1.0" in md and "never gated, and never promotable on this data" in md
    assert "limit = close − 0.5 × ATR(14), TP = limit + 1 × ATR(14), SL = limit − 1.5 × ATR(14)" in md
    assert "$20,000,000" in md and "Costs are 0.1% per side" in md
    assert "resolved on or before the last session of Y − 1" in md
    assert "Only predictions > 0 are kept" in md
    assert "Folds: 2021, 2022" in md
    assert "the two model digests are identical" in md
    assert "One round only" in md
    assert "10,000,000 IDR" in md and "Actual/365.25" in md


def test_determinism_switch_gates_b_linear():
    r = build_report(determinism_ok=False)
    md = render_markdown(r)
    assert parse_machine_line(md, GATED_KEY) == B_LINEAR
    last = json.loads(parse_machine_line(md, LAST_FOLD_KEY))
    assert last["kind"] == RIDGE and last["digest"] == r.b_linear.fold_models[-1].model.digest
    method = _section(md, "## Method")
    assert "the two model digests differ" in method and "B-linear is the gated model" in method
    assert "| Metric | B | B-linear (gated) | A2 walk-forward |" in _section(md, "## Walk-forward results")
    assert "Walk-forward, B-linear (" in _section(md, "## Go-live checklist")
    assert "by the pre-registered determinism switch" in r.verdict.sentence
    assert r.verdict.sentence in md


def test_top_features_orders_by_share_then_feature_order():
    assert top_features(IMP_B) == (
        ("ret_1", 0.30),
        ("spy_ret_5", 0.25),
        ("ret_20", 0.10),
        ("ret_60", 0.10),
        ("rsi_2", 0.10),
    )
    assert top_features(IMP_LIN) == (("gap", 0.6), ("range_pos", 0.4))
    assert top_features((0.0,) * len(FEATURE_NAMES)) == ()
    with pytest.raises(ValueError):
        top_features((1.0,))


def test_training_tables_per_fold():
    r = build_report()
    sec = _section(render_markdown(r), "## Training per fold")
    tree = _table_rows(sec[sec.index("### B (gradient-boosted trees)"): sec.index("### B-linear (ridge regression)")])
    assert [c[0] for c in tree] == ["2021", "2022"]
    assert tree[0][:7] == ["2021", "2020-12-31", "1,200", "+0.050%", "+0.040%", "—", "37.5%"]
    assert tree[1][:7] == ["2022", "2021-12-31", "2,400", "−0.025%", "−0.010%", "+0.0123", "25.0%"]
    assert tree[0][7] == "`ret_1` 30.0%, `spy_ret_5` 25.0%, `ret_20` 10.0%, `ret_60` 10.0%, `rsi_2` 10.0%"
    assert tree[0][8] == f"`{r.b.fold_models[0].model.digest[:12]}`"
    linear = _table_rows(sec[sec.index("### B-linear (ridge regression)"):])
    assert linear[1][7] == "`gap` 60.0%, `range_pos` 40.0%"
    assert "split-gain share" in sec and "|coefficient| × feature std share" in sec


# --------------------------------------------------------------------------- results, years, diagnostics


def test_results_table_has_every_curve():
    sec = _section(render_markdown(build_report()), "## Walk-forward results")
    assert "| Metric | B (gated) | B-linear | A2 walk-forward | SPY price-only | SPY total-return |" in sec
    end_b = Decimal(CASH0) + Decimal("2.0000") * TRADED
    end_lin = Decimal(CASH0) + Decimal("1.5000") * TRADED
    assert f"| Ending equity (USD) | {format(end_b, ',.2f')} | {format(end_lin, ',.2f')} |" in sec
    assert "| SPY dividends credited (USD) | — | — | — | — | 4.56 |" in sec
    assert "| Meets the gate's rules | yes | yes | no: Beats SPY | — | — |" in sec
    assert "- B (gated): held 3, no_slot 7." in sec and "- A2 walk-forward: held 3, no_slot 7." in sec


def test_year_by_year():
    sec = _section(render_markdown(build_report()), "## Year by year")
    rows = _table_rows(sec)
    assert [c[0] for c in rows] == ["2021", "2022"]
    n2021 = len(dates.sessions(FOLDS[0].trade_start, FOLDS[0].trade_end))
    assert rows[0][1] == "2021-01-04 → 2021-12-31"
    assert rows[0][2] == fmt_signed_pct((1400 + 2 * n2021) / 1400 - 1)
    assert rows[0][4] == fmt_signed_pct((1400 + 0.1 * n2021) / 1400 - 1)
    assert len(rows[0]) == 7


def test_diagnostics_passed_nights_and_calibration():
    sec = _section(render_markdown(build_report()), "## Diagnostics")
    assert "| Measure | B (gated) | B-linear |" in sec
    assert f"| Nights passed (no pick) | 40 of {TRADED} ({fmt_pct(40 / TRADED)}) | 12 of {TRADED} ({fmt_pct(12 / TRADED)}) |" in sec
    assert "| Trades with < 3 shares | 2 (66.7%) | 2 (66.7%) |" in sec
    assert "| Exits: take profit | 1 · +1.96 | 1 · +1.96 |" in sec
    cal_b = _table_rows(sec[sec.index("### Calibration: B\n"): sec.index("### Calibration: B-linear")])
    assert [c[0] for c in cal_b] == [str(k) for k in range(1, DECILES + 1)]
    assert cal_b[0] == ["1", "30", "−0.500% to −0.410%", "−0.450%", "−0.320%"]
    cal_lin = _table_rows(sec[sec.index("### Calibration: B-linear"):])
    assert cal_lin[-1] == ["10", "0", "—", "—", "—"]


def test_calibration_renders_phase_4_output():
    pred = np.linspace(-0.01, 0.01, 25)
    label = pred * 0.5
    label[3] = np.nan  # an unresolved label is left out
    rows = calibration(pred, label)
    assert len(rows) == DECILES
    r = dataclasses.replace(build_report(), calibration=((B, rows), (B_LINEAR, rows)))
    md = render_markdown(r)
    sec = _section(md, "## Diagnostics")
    parsed = _table_rows(sec[sec.index("### Calibration: B\n"): sec.index("### Calibration: B-linear")])
    assert [int(c[1].replace(",", "")) for c in parsed] == [c.rows for c in rows]
    assert sum(c.rows for c in rows) == 24
    assert "nan" not in md.lower().replace("financ", "")


def test_seen_before_and_checklist():
    r = build_report()
    md = render_markdown(r)
    sec = _section(md, "## Seen before (information only, not out-of-sample)")
    assert "not out-of-sample any more" in sec and "never feed the gate" in sec
    assert f"({SEEN_BEFORE_START.isoformat()} → 2022-01-31," in sec
    m = window_metrics(r.b.run, SEEN_BEFORE_START)
    assert f"| B (gated) | {fmt_signed_pct(m.total_return)} |" in sec
    for name in ("| B-linear |", "| A2 walk-forward |", "| SPY price-only |", "| SPY total-return |"):
        assert name in sec
    chk = _section(md, "## Go-live checklist")
    assert "Walk-forward, B (" in chk
    assert (
        "| Passed a 10-year backtest under identical rules | #5, decided by the P6a gate | pass: P6a gate verdict | — |"
        in chk
    )


def test_survivorship_note_has_the_learned_model_caveat():
    md = _section(render_markdown(build_report()), "## Survivorship bias")
    assert "7 stocks were in the S&P 500 or the Nasdaq-100" in md
    assert "from 2020-01-02 to 2022-01-31" in md
    assert "A learned model is more exposed to this than a rule" in md
    assert "the losers it never saw" in md
    assert "probably better than reality" in md
    assert "| All | 2,200 | 20 | 16 | 4 | 0.91% |" in md


def test_open_positions_per_curve():
    md = _section(render_markdown(build_report(open_symbol="A|B")), "## Open positions at end")
    assert "### B\n" in md and "### B-linear\n" in md and "### A2 walk-forward\n" in md
    assert "| A\\|B | open | 4 | 2022-01-28 | 2022-01-28 | 29.5000 | 3 | 29.5000 | 31.0000 | 28.0000 | 2 |" in md
    assert md.count("None.") == 2


def test_curves_section_links_svg_and_csv():
    md = render_markdown(build_report())
    stem = report_stem(END)
    assert f"({stem}-equity.svg)" in md and f"({stem}-equity.csv)" in md
    assert "-grid.csv" not in md and "-variants.svg" not in md


# --------------------------------------------------------------------------- CSV and SVG


def test_equity_csv_is_wide_and_aligned():
    text = equity_csv(build_report())
    lines = text.splitlines()
    assert lines[0] == EQUITY_CSV_HEADER == "date,b,b_linear,a2,spy_price,spy_tr"
    assert len(lines) == len(SESS) + 1
    assert lines[1] == f"{SESS[0].isoformat()}," + ",".join([CASH0] * 5)
    assert lines[2].split(",")[1:] == ["1402.0000", "1401.5000", "1400.1000", "1400.4000", "1400.5000"]
    assert text.endswith("\n") and not text.endswith("\n\n")


NS = "{http://www.w3.org/2000/svg}"


def test_equity_svg_has_five_series_in_contract_classes():
    svg = equity_svg(build_report())
    root = ET.fromstring(svg.encode("utf-8"))
    assert root.tag == f"{NS}svg" and root.get("viewBox") == "0 0 960 460"
    lines = root.findall(f"{NS}polyline")
    assert [pl.get("class") for pl in lines] == ["line s1", "line v2", "line v0", "line s2", "line s3"]
    assert all(len(pl.get("points").split()) == len(SESS) for pl in lines)
    assert "@media (prefers-color-scheme: dark)" in root.find(f"{NS}style").text
    assert root.find(f"{NS}rect").get("class") == "bg"
    assert "<script" not in svg and "href" not in svg
    assert "nan" not in svg.lower() and "inf" not in svg.lower()
    texts = [t.text or "" for t in root.iter(f"{NS}text")]
    for label in ("B", "B-linear", "A2 walk-forward", "SPY price-only", "SPY total-return"):
        assert label in texts
        assert any(t.startswith(f"{label} +") for t in texts)
    assert "2022" in texts


# --------------------------------------------------------------------------- validation


def test_renderers_refuse_misaligned_curves():
    r = build_report()
    bad_run = dataclasses.replace(r.b_linear.run, snapshots=r.b_linear.run.snapshots[:-1])
    bad = dataclasses.replace(r, b_linear=dataclasses.replace(r.b_linear, run=bad_run))
    for fn in RENDERERS:
        with pytest.raises(ValueError, match="walk-forward curves"):
            fn(bad)


def test_renderers_refuse_inconsistent_inputs():
    r = build_report()
    lin_fms = r.b_linear.fold_models
    cases = (
        (dataclasses.replace(r, verdict=dataclasses.replace(r.verdict, passed=False)), "verdict"),
        (
            dataclasses.replace(
                r, b=dataclasses.replace(r.b, run=dataclasses.replace(r.b.run, params=model_schedule(FOLDS, lin_fms)))
            ),
            "fold models' schedule",
        ),
        (dataclasses.replace(r, b=dataclasses.replace(r.b, fold_models=r.b.fold_models[::-1])), "sits at fold"),
        (
            dataclasses.replace(
                r,
                b=dataclasses.replace(
                    r.b, fold_models=lin_fms, run=dataclasses.replace(r.b.run, params=model_schedule(FOLDS, lin_fms))
                ),
            ),
            "not 'tree'",
        ),
        (dataclasses.replace(r, gated=B_LINEAR), "gated"),
        (dataclasses.replace(r, passed=((B, 40, TRADED - 1), (B_LINEAR, 12, TRADED))), "traded sessions"),
        (dataclasses.replace(r, calibration=r.calibration[::-1]), "calibration"),
        (dataclasses.replace(r, labelled_rows=r.candidate_rows + 1), "labelled rows"),
        (
            dataclasses.replace(r, a2=dataclasses.replace(r.a2, run=dataclasses.replace(r.a2.run, params=A2_DESIGN_PARAMS))),
            "A2",
        ),
    )
    for bad, match in cases:
        for fn in RENDERERS:
            with pytest.raises(ValueError, match=match):
                fn(bad)
