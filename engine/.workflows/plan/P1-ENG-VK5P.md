> Adopted from `STRATEGY_B_RANKER_PLAN.md` phase 5. Source: `.workflows/plan/strategy-b-ranker/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: B report rendering

**Plan set:** `STRATEGY_B_RANKER_PLAN.md`
**Analysis:** `20261003-180843-B6R1_code_analyzer.md`
**Satisfies:** R5 (byte-stable rendering, determinism switch reported), R6 (purity of the new module), R7 (every section handover §6.7 lists) — the committed P6a report is readable, complete and reproducible byte for byte
**Depends on:** Phase 4 (and, through it, phases 1, 2 and 3)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest`

---

## Goal

After this phase, `seer_engine.backtest.b_report` turns a `BReport` value into the three report
files' text: Markdown with the 15 sections the plan index lists, a wide equity CSV
(`date,b,b_linear,a2,spy_price,spy_tr`), and one self-contained SVG (B, B-linear, A2, SPY price,
SPY TR). It is pure, so it renders the same bytes every time. `_validate` refuses an inconsistent
report: a verdict that is not `gate_p6a` of the gated curve, misaligned curves, a run whose
schedule does not match its `fold_models`, or a gated model that contradicts the determinism
probe. Nothing writes files yet. That is phase 6.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates** (all in `engine/src/seer_engine/backtest/b_report.py`, new):
- `GATE_KEY = "p6a-gate"`, `GATED_KEY = "gated-model"`, `LAST_FOLD_KEY = "last-fold-model"`,
  `FROZEN_KEY = "frozen-model"`;
- `EQUITY_CSV_HEADER = "date,b,b_linear,a2,spy_price,spy_tr"`;
- `@dataclass(frozen=True) class BReport`. Its fields are exactly the index contract's, in that
  order. It adds two helper methods: `curves() -> (b, b_linear)` and `gated_curve() -> BWalkForward`;
- `report_stem(data_end: date) -> str`, which returns `f"{data_end.isoformat()}-strategy-b-walkforward"`;
- `top_features(importance: Sequence[float]) -> tuple[tuple[str, float], ...]`. This one is
  public, though the index contract does not list it. It returns up to `TOP_FEATURES`
  `(FEATURE_NAMES[j], share)` pairs, sorted by `(-share, j)`, and leaves out shares ≤ 0. It
  raises ValueError unless there are `len(FEATURE_NAMES)` shares;
- `machine_lines(r: BReport) -> list[str]`. It returns 4 lines, in the order gate, gated model,
  last-fold model, frozen model:
  - `last-fold-model: {"kind": …, "digest": …, "train_end": "YYYY-MM-DD", "rows": <int>, "label_sum": "<repr(float)>"}`.
    The keys come in this order, and **`label_sum` is a JSON string holding `repr(float)`**, so
    the value round-trips exactly with `float(...)`;
  - `frozen-model: null`, or `{"report", "artifact", "train_end", "sha256"}` in that order, with
    `train_end` in ISO form;
- `parse_machine_line(markdown: str, key: str) -> str`. It delegates to
  `wf_report.parse_machine_line`, so the semantics are identical;
- `render_markdown(r) -> str`, `equity_csv(r) -> str` and `equity_svg(r) -> str`. Each one calls
  `_validate` first;
- private helpers: `_validate`, the `_*_section` functions, `_spct`, `_signed`, `_py`,
  `_report_path`, and so on.

**Signature changes:** none.

**Requires (from earlier phases):**
- **Phase 4** (`backtest/b_walkforward.py`):
  - the constants `B == "B"`, `B_LINEAR == "B-linear"`, `DECILES == 10` and `TOP_FEATURES == 5`;
  - `FoldModel(fold, model, rows, label_mean, label_sum, pred_mean, r2, positive_share, importance)`;
  - `BWalkForward(name, folds, fold_models, run)`;
  - `CalibrationRow(decile, rows, pred_min, pred_max, pred_mean, label_mean)`;
  - `model_schedule(folds, fold_models) -> ParamsSchedule`;
  - `calibration(pred, label) -> tuple[CalibrationRow, ...]`. It drops NaN (unresolved) labels
    itself and raises ValueError when fewer than `DECILES` labels are resolved, so every call
    that returns gives exactly `DECILES` non-empty rows, deciles 1..10 (phase 4 contract item 4);
  - `gate_p6a(wf, spy_tr, start, end, gated) -> Verdict`. When `gated == B_LINEAR`, only the
    sentence's subject changes, to "Strategy B (as B-linear, by the pre-registered determinism
    switch)", so it contains "by the pre-registered determinism switch" (phase 4 contract item 5);
  - `passed_nights`'s traded count equals `len(run.snapshots) - 1` (phase 4 contract item 8).
- **Phase 1** (`strategies/b_model.py`):
  - `TREE == "tree"` and `RIDGE == "ridge"`;
  - `TREE_PARAMS`, a dict in the contract's insertion order;
  - `RIDGE_ALPHA == 1.0`;
  - `BModel.kind`, `.digest` and `.as_dict() -> {"kind", "digest"}`;
  - `fit(kind, X, y) -> BModel`. The test uses it.
- **Phase 2** (`strategies/b.py`):
  - `FEATURE_NAMES`, `SYMBOL_FEATURES` and `SPY_FEATURES`, in the contract's order;
  - `LOOKBACK == 200`, `SPY_SYMBOL == "SPY"` and `MIN_DOLLAR_VOLUME == 20_000_000.0`;
  - `FrozenModel(report, artifact, train_end, sha256)`, a frozen slots dataclass.
- **Phase 3** (`backtest/labels.py`): `COST == 0.001`.

**Leaves alone (owned by others):**
- `backtest/io.py` (phase 6 adds `write_b_report`);
- `commands/backtest_b.py` (phase 6 builds `BReport`);
- `strategies/b.py`'s `STRATEGY_B_FROZEN` value (phase 7);
- `backtest/b_walkforward.py` (phase 4);
- the following, which are read-only by law and are imported, never edited: `wf_report.py`,
  `report.py`, `walkforward.py`, `metrics.py`, `runner.py`, `tuning.py` and `benchmark.py`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/b_report.py` | create (line 1, whole file) | `BReport`, keys, `report_stem`, `top_features`, `machine_lines`, `parse_machine_line`, `_validate`, 15 Markdown sections, `equity_csv`, `equity_svg` |
| `engine/tests/test_backtest_b_report.py` | create (line 1, whole file) | **27 tests** on a small synthetic report built from phase 4's types, phase 1's `fit`, and `gate_p6a`, `model_schedule` and `calibration` |

No existing file is edited. `tests/test_strategy_purity.py` already globs `backtest/*.py`, so it
covers the new module without a change.

## Implementation Steps

### Step 1: Create `backtest/b_report.py`
**File:** `engine/src/seer_engine/backtest/b_report.py:1` (new)
**Change:** the whole module, given in full below.

Design notes, so that the implementer does not have to re-derive them:
- **Determinism.**
  - Every number goes through `metrics.to_fixed` (via `fmt_*`, `_spct` or `_signed`),
    `str(int)`, `f"{int:,}"`, `format(Decimal)`, or `repr(float)` (the machine line only).
  - Iteration follows tuple order, `FEATURE_NAMES` order, or `sorted`.
  - Nothing reads the clock.
- **NaN and None safety.** `_spct` and `_signed` print `—` for None and for non-finite floats. A
  calibration decile with 0 rows prints `—` in every value cell. So `nan` never reaches the
  Markdown.
- **The SVG** reuses `wf_report._chart` and its `_STYLE`. Each curve gets a fixed class:

  | Curve | Class |
  |---|---|
  | B | `s1` |
  | B-linear | `v2` |
  | A2 | `v0` |
  | SPY price | `s2` |
  | SPY TR | `s3` |

  The 5 legend entries end at about x = 890 < 960, the same width as A2's 5-series variants
  chart.
- **The private helpers** are imported read-only from `report.py` and `wf_report.py`, which
  plan-index Decision D1 and the "Out of scope" note allow.
- **"Frozen matches"** means `frozen.report == "docs/backtests/<stem>.md"` and
  `frozen.train_end == the gated curve's last fold tune_end`. The SHA-256 cannot be checked
  here, because the renderer never sees the artifact bytes. Phase 7's
  `test_strategy_b_frozen.py` ties the SHA-256 to the artifact.

**Code:**
```python
"""Strategy B walk-forward (P6a) report rendering: Markdown, one wide CSV and one self-contained SVG.

Pure: takes a ``BReport`` value and returns text. Phase 6's ``io.write_b_report`` writes the files
``<stem>.md``, ``<stem>-equity.csv`` and ``<stem>-equity.svg``. Everything is deterministic
(invariant 5):
- numbers go through ``metrics.to_fixed`` (via ``fmt_*``, ``_spct`` and ``_signed``), ``str(int)``,
  ``format`` of a ``Decimal``, or ``repr`` of a float (the ``last-fold-model`` line only);
- SVG coordinates come from ``wf_report._chart``, ``f"{x:.1f}"`` of floats computed the same way
  every time;
- iteration is in tuple order, ``FEATURE_NAMES`` order or sorted order.

The Markdown ends with four machine-readable lines inside one ``text`` fence, each exactly once:
``p6a-gate: passed|failed``, ``gated-model: B|B-linear``, ``last-fold-model: <json>`` and
``frozen-model: null|<json>``. Phase 7's ``test_strategy_b_frozen.py`` reads them with
:func:`parse_machine_line`.

The per-fold summaries, diagnostics, calibration tables and the "seen before" slice explain the
result. Nothing here feeds any fit or selection. ``report.py``, ``wf_report.py`` and
``walkforward.py`` are reused read-only for their helpers and are never edited.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from seer_engine import dates
from seer_engine.backtest.b_walkforward import (
    B,
    B_LINEAR,
    DECILES,
    TOP_FEATURES,
    BWalkForward,
    CalibrationRow,
    FoldModel,
    gate_p6a,
    model_schedule,
)
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.labels import COST
from seer_engine.backtest.metrics import (
    DASH,
    EXIT_REASONS,
    MINUS,
    checklist,
    curve_metrics,
    fmt_num,
    fmt_pct,
    fmt_pf,
    fmt_signed_pct,
    forced_closes,
    run_metrics,
    to_fixed,
)
from seer_engine.backtest.report import (
    _CHECK_NOTES,
    _EXIT_LABELS,
    FENCE,
    _check_aligned,
    _order_row,
    _pass,
    _sessions,
    _span,
    _table,
    _usd,
)
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, YearGap
from seer_engine.backtest.tuning import Verdict
from seer_engine.backtest.walkforward import (
    COMBINED,
    SEEN_BEFORE_START,
    Diagnostics,
    Fold,
    WalkForward,
    curve_window_metrics,
    diagnostics,
    schedule,
    window_metrics,
)
from seer_engine.backtest.wf_report import (
    _chart,
    _dates,
    _gate_cell,
    _segment_return,
    _signed_usd,
    _slice_sessions,
    _subtitle,
)
from seer_engine.backtest.wf_report import parse_machine_line as _wf_parse_machine_line
from seer_engine.strategies.a import ATR_N, DESIGN_PARAMS
from seer_engine.strategies.b import (
    FEATURE_NAMES,
    LOOKBACK,
    MIN_DOLLAR_VOLUME,
    SPY_FEATURES,
    SPY_SYMBOL,
    SYMBOL_FEATURES,
    FrozenModel,
)
from seer_engine.strategies.b_model import RIDGE, RIDGE_ALPHA, TREE, TREE_PARAMS

GATE_KEY = "p6a-gate"
GATED_KEY = "gated-model"
LAST_FOLD_KEY = "last-fold-model"
FROZEN_KEY = "frozen-model"
EQUITY_CSV_HEADER = "date,b,b_linear,a2,spy_price,spy_tr"

_REPORT_DIR = "docs/backtests"
_A2_LABEL = "A2 walk-forward"
_KINDS = {B: TREE, B_LINEAR: RIDGE}
_MODEL_HEADINGS = {B: "B (gradient-boosted trees)", B_LINEAR: "B-linear (ridge regression)"}
_IMPORTANCE_RULE = {B: "split-gain share", B_LINEAR: "|coefficient| × feature std share"}


# --------------------------------------------------------------------------- values


@dataclass(frozen=True)
class BReport:
    data_end: date
    bars_rows: int
    symbols_with_bars: int
    never_fetched_members: int
    survivorship: tuple[YearGap, ...]  # runner.survivorship(market, is_start, data_end)
    is_start: date
    folds: tuple[Fold, ...]
    candidate_rows: int
    labelled_rows: int  # rows with a valid bracket and a resolved label
    determinism_ok: bool  # probe_determinism on the last fold
    gated: str  # B if determinism_ok else B_LINEAR
    b: BWalkForward
    b_linear: BWalkForward
    a2: WalkForward  # A2's combined walk-forward, recomputed (information)
    passed: tuple[tuple[str, int, int], ...]  # (curve name, passed sessions, traded sessions): B, B-linear
    calibration: tuple[tuple[str, tuple[CalibrationRow, ...]], ...]  # (B, rows), (B-linear, rows)
    spy_price: BenchmarkCurve
    spy_tr: BenchmarkCurve
    verdict: Verdict  # gate_p6a on the gated curve
    frozen: FrozenModel | None  # STRATEGY_B_FROZEN at run time

    def curves(self) -> tuple[BWalkForward, BWalkForward]:
        return (self.b, self.b_linear)

    def gated_curve(self) -> BWalkForward:
        return self.b if self.gated == B else self.b_linear


def report_stem(data_end: date) -> str:
    """File stem for one data end date: ``<data_end>-strategy-b-walkforward``."""
    return f"{data_end.isoformat()}-strategy-b-walkforward"


def _report_path(data_end: date) -> str:
    return f"{_REPORT_DIR}/{report_stem(data_end)}.md"


def top_features(importance: Sequence[float]) -> tuple[tuple[str, float], ...]:
    """The top ``TOP_FEATURES`` ``(feature name, share)`` pairs: share descending, then
    ``FEATURE_NAMES`` order. Shares ≤ 0 are left out."""
    shares = tuple(float(v) for v in importance)
    if len(shares) != len(FEATURE_NAMES):
        raise ValueError(f"{len(shares)} importance shares for {len(FEATURE_NAMES)} features")
    order = sorted(range(len(shares)), key=lambda j: (-shares[j], j))
    return tuple((FEATURE_NAMES[j], shares[j]) for j in order[:TOP_FEATURES] if shares[j] > 0.0)


# --------------------------------------------------------------------------- machine lines


def _last_fold_json(r: BReport) -> str:
    fm = r.gated_curve().fold_models[-1]
    ident = fm.model.as_dict()
    return json.dumps(
        {
            "kind": ident["kind"],
            "digest": ident["digest"],
            "train_end": fm.fold.tune_end.isoformat(),
            "rows": int(fm.rows),
            "label_sum": repr(float(fm.label_sum)),
        }
    )


def _frozen_json(f: FrozenModel) -> str:
    return json.dumps(
        {"report": f.report, "artifact": f.artifact, "train_end": f.train_end.isoformat(), "sha256": f.sha256}
    )


def machine_lines(r: BReport) -> list[str]:
    """The four machine-readable lines: gate, gated model, last fold's model, frozen model."""
    frozen = "null" if r.frozen is None else _frozen_json(r.frozen)
    return [
        f"{GATE_KEY}: {'passed' if r.verdict.passed else 'failed'}",
        f"{GATED_KEY}: {r.gated}",
        f"{LAST_FOLD_KEY}: {_last_fold_json(r)}",
        f"{FROZEN_KEY}: {frozen}",
    ]


def parse_machine_line(markdown: str, key: str) -> str:
    """The raw value of the single ``<key>: <value>`` line; ValueError unless exactly one exists."""
    return _wf_parse_machine_line(markdown, key)


# --------------------------------------------------------------------------- validation


def _check_span(name: str, run: RunResult, folds: tuple[Fold, ...]) -> None:
    if run.start != folds[0].trade_start or run.end != folds[-1].trade_end:
        raise ValueError(
            f"{name}: run {_span(run)} is not "
            f"{folds[0].trade_start.isoformat()} → {folds[-1].trade_end.isoformat()}"
        )


def _check_b_curve(r: BReport, wf: object, name: str) -> None:
    if not isinstance(wf, BWalkForward):
        raise TypeError(f"the {name} curve must be a BWalkForward, got {type(wf).__name__}")
    if wf.name != name:
        raise ValueError(f"the {name} curve is named {wf.name!r}")
    if wf.folds != r.folds:
        raise ValueError(f"{name}: folds differ from the report's folds")
    if len(wf.fold_models) != len(r.folds):
        raise ValueError(f"{name}: {len(wf.fold_models)} fold models for {len(r.folds)} folds")
    kind = _KINDS[name]
    for f, fm in zip(r.folds, wf.fold_models):
        if not isinstance(fm, FoldModel):
            raise TypeError(f"{name}: fold models must be FoldModel values, got {type(fm).__name__}")
        if fm.fold != f:
            raise ValueError(f"{name}: fold model for {fm.fold.year} sits at fold {f.year}")
        if fm.model.kind != kind:
            raise ValueError(f"{name}: fold {f.year} model is {fm.model.kind!r}, not {kind!r}")
        if len(fm.importance) != len(FEATURE_NAMES):
            raise ValueError(
                f"{name}: fold {f.year} has {len(fm.importance)} importance shares for {len(FEATURE_NAMES)} features"
            )
    if wf.run.params != model_schedule(r.folds, wf.fold_models):
        raise ValueError(f"{name}: the run did not use its fold models' schedule")
    _check_span(name, wf.run, r.folds)


def _validate(r: BReport) -> None:
    if not r.folds:
        raise ValueError("the report has no folds")
    if r.is_start != r.folds[0].tune_start:
        raise ValueError(f"is_start {r.is_start} is not the first fold's tune_start {r.folds[0].tune_start}")
    _check_b_curve(r, r.b, B)
    _check_b_curve(r, r.b_linear, B_LINEAR)
    if not isinstance(r.a2, WalkForward):
        raise TypeError(f"a2 must be a WalkForward, got {type(r.a2).__name__}")
    if r.a2.name != COMBINED:
        raise ValueError(f"A2: the curve is named {r.a2.name!r}, not {COMBINED!r}")
    if r.a2.folds != r.folds:
        raise ValueError("A2: folds differ from the report's folds")
    if len(r.a2.selections) != len(r.folds):
        raise ValueError(f"A2: {len(r.a2.selections)} selections for {len(r.folds)} folds")
    if r.a2.run.params != schedule(r.folds, r.a2.selections):
        raise ValueError("A2: the run did not use its fold selections' schedule")
    _check_span("A2", r.a2.run, r.folds)
    if r.b.run.end > r.data_end:
        raise ValueError(f"the runs end {r.b.run.end}, after the data end {r.data_end}")
    _check_aligned(
        "walk-forward curves",
        [r.b.run.snapshots, r.b_linear.run.snapshots, r.a2.run.snapshots, r.spy_price.snapshots, r.spy_tr.snapshots],
    )
    if not isinstance(r.determinism_ok, bool):
        raise TypeError(f"determinism_ok must be a bool, got {type(r.determinism_ok).__name__}")
    expected_gated = B if r.determinism_ok else B_LINEAR
    if r.gated != expected_gated:
        raise ValueError(
            f"the gated model is {r.gated!r}, but the determinism probe "
            f"{'passed' if r.determinism_ok else 'failed'}, so it must be {expected_gated!r}"
        )
    if tuple(p[0] for p in r.passed) != (B, B_LINEAR):
        raise ValueError(f"passed nights are for {[p[0] for p in r.passed]}, not {[B, B_LINEAR]}")
    for (name, passed, traded), wf in zip(r.passed, r.curves()):
        if traded != _sessions(wf.run) or not 0 <= passed <= traded:
            raise ValueError(
                f"{name}: {passed} passed of {traded} traded sessions, but the run has {_sessions(wf.run)} sessions"
            )
    if tuple(c[0] for c in r.calibration) != (B, B_LINEAR):
        raise ValueError(f"calibration tables are for {[c[0] for c in r.calibration]}, not {[B, B_LINEAR]}")
    for name, rows in r.calibration:
        if tuple(c.decile for c in rows) != tuple(range(1, DECILES + 1)):
            raise ValueError(f"{name}: calibration deciles are not 1..{DECILES}")
    if not 0 <= r.labelled_rows <= r.candidate_rows:
        raise ValueError(f"{r.labelled_rows} labelled rows for {r.candidate_rows} candidate rows")
    if r.frozen is not None and not isinstance(r.frozen, FrozenModel):
        raise TypeError(f"frozen must be a FrozenModel or None, got {type(r.frozen).__name__}")
    g = r.gated_curve()
    expected = gate_p6a(run_metrics(g.run), curve_metrics(r.spy_tr), g.run.start, g.run.end, r.gated)
    if r.verdict != expected:
        raise ValueError("the verdict is not gate_p6a of the gated curve and total-return SPY")


# --------------------------------------------------------------------------- small helpers


def _spct(v: float | None, digits: int = 3) -> str:
    """``+0.123%`` / ``−0.123%`` (v × 100); the dash for None or a non-finite value."""
    if v is None or not math.isfinite(v):
        return DASH
    return ("+" if v >= 0 else MINUS) + to_fixed(abs(v * 100), digits) + "%"


def _signed(v: float | None, digits: int) -> str:
    """``+0.0123`` / ``−0.0123``; the dash for None or a non-finite value."""
    if v is None or not math.isfinite(v):
        return DASH
    return ("+" if v >= 0 else MINUS) + to_fixed(abs(v), digits)


def _py(v: object) -> str:
    """A hyperparameter value as Python source: strings double-quoted, everything else ``repr``."""
    return json.dumps(v) if isinstance(v, str) else repr(v)


def _col(r: BReport, name: str) -> str:
    return f"{name} (gated)" if name == r.gated else name


def _seen_covered(r: BReport) -> bool:
    return r.b.run.start <= SEEN_BEFORE_START <= r.b.run.end


def _rejected(run: RunResult) -> str:
    return ", ".join(f"{reason} {count:,}" for reason, count in run.rejections) or "none"


def _strategy_runs(r: BReport) -> list[tuple[str, RunResult]]:
    return [(_col(r, B), r.b.run), (_col(r, B_LINEAR), r.b_linear.run), (_A2_LABEL, r.a2.run)]


# --------------------------------------------------------------------------- sections


def _data_section(r: BReport) -> list[str]:
    run = r.b.run
    tune_end = r.folds[-1].tune_end
    rows = [
        [
            "Training data (anchored, longest window)",
            _dates(r.is_start, tune_end),
            f"{len(dates.sessions(r.is_start, tune_end)):,}",
            DASH,
            DASH,
        ],
        [
            "Walk-forward (traded)",
            _span(run),
            f"{_sessions(run):,}",
            format(run.usd_idr, ",.4f"),
            _usd(run.initial_cash),
        ],
    ]
    if _seen_covered(r):
        rows.append(
            [
                "Seen before (a slice of the walk-forward)",
                _dates(SEEN_BEFORE_START, run.end),
                f"{_slice_sessions(run):,}",
                DASH,
                DASH,
            ]
        )
    first_dd = dates.prev_session(r.is_start)
    last_dd = dates.prev_session(r.folds[-1].trade_end)
    share = f" ({fmt_pct(r.labelled_rows / r.candidate_rows)})" if r.candidate_rows else ""
    return [
        "## Data",
        "",
        f"- Data end (last bar loaded): {r.data_end.isoformat()}",
        f"- Bar rows loaded: {r.bars_rows:,}",
        f"- Symbols with bars: {r.symbols_with_bars:,}",
        f"- Index members in the window with no bars at all: {r.never_fetched_members:,}",
        f"- Candidate rows (every candidate on every data date {_dates(first_dd, last_dd)}): {r.candidate_rows:,}",
        f"- Labelled rows (a valid bracket and a label resolved by the data end): {r.labelled_rows:,}{share}",
        "",
        *_table(
            ["Window", "Dates", "Sessions", "USD/IDR at start", "Starting cash (USD)"],
            ["l", "l", "r", "r", "r"],
            rows,
        ),
        "",
    ]


def _method_section(r: BReport) -> list[str]:
    a = DESIGN_PARAMS.as_dict()
    years = ", ".join(str(f.year) for f in r.folds)
    first = r.folds[0].trade_start.isoformat()
    tree = ", ".join(f"{k}={_py(v)}" for k, v in TREE_PARAMS.items())
    sym = ", ".join(f"`{n}`" for n in SYMBOL_FEATURES)
    spy = ", ".join(f"`{n}`" for n in SPY_FEATURES)
    tm = curve_metrics(r.spy_tr)
    if r.determinism_ok:
        linear = (
            f"- **B-linear (information only).** Ridge regression (alpha = {RIDGE_ALPHA!r}, closed form, "
            "unpenalized intercept) on the same features, labels and folds, traded through the same "
            "walk-forward. It shows whether any edge comes from non-linearity or from the features "
            "alone. It is reported next to B, never gated, and never promotable on this data."
        )
        probe = (
            "- **Determinism probe.** The last fold's tree was fit twice on the same rows, once on one "
            "thread and once on the default thread count, and the two model digests are identical. So "
            "the pre-registered switch did not fire, and B (the tree model) is the gated model."
        )
    else:
        linear = (
            f"- **B-linear (gated by the switch).** Ridge regression (alpha = {RIDGE_ALPHA!r}, closed "
            "form, unpenalized intercept) on the same features, labels and folds, traded through the "
            "same walk-forward. It is gated here only because the determinism probe below failed. "
            "The tree model is reported next to it as information."
        )
        probe = (
            "- **Determinism probe.** The last fold's tree was fit twice on the same rows, once on one "
            "thread and once on the default thread count, and the two model digests differ. So the "
            "pre-registered switch fired: B-linear is the gated model, and the tree model is "
            "information only. Nobody chose this after seeing a result."
        )
    return [
        "## Method",
        "",
        "- **Strategy B** is a learned cross-sectional ranker (design §4). Each night it predicts "
        "the net return of A's design bracket for every candidate, and keeps the candidates with a "
        "positive prediction. Everything below was fixed before any B result was seen.",
        f"- **Candidates.** On each data date, every point-in-time S&P 500 ∪ Nasdaq-100 member with "
        f"a bar dated that day, at least {LOOKBACK} bars through it, 20-session mean close × volume "
        f"> ${MIN_DOLLAR_VOLUME:,.0f} (A's liquidity floor), and all {len(SYMBOL_FEATURES)} "
        f"per-symbol features defined. {SPY_SYMBOL} is never a candidate, and a date where "
        f"{SPY_SYMBOL}'s features are undefined has no candidates.",
        f"- **Features ({len(FEATURE_NAMES)}).** Per symbol, from its last {LOOKBACK} bars: {sym}. "
        "Each is turned into a cross-sectional rank in [0, 1] among that date's candidates, with "
        f"ties averaged. Plus {SPY_SYMBOL}'s {spy}, raw and the same for every candidate on a date. "
        "Returns are over k bars. The 20-session stdev of daily returns uses ddof 0. RSI and ATR are "
        "Wilder's. The dollar-volume rank equals the rank of its log.",
        f"- **Bracket.** A's design bracket, fixed: limit = close − {a['limit_atr']} × ATR({ATR_N}), "
        f"TP = limit + {a['tp_atr']} × ATR({ATR_N}), SL = limit − {a['sl_atr']} × ATR({ATR_N}), each "
        "to 4 dp. A candidate whose bracket is invalid is never picked and never trained on.",
        "- **Label.** The net return per dollar committed of that one bracket order, simulated alone "
        "under design §5 on NYSE sessions. It fills only if the order session's low is below the "
        "limit, at min(open, limit). TP and SL are checked from the session after the fill, with SL "
        "first when both are in range. Gaps exit at the open. The time stop exits at the open once "
        f"5 sessions are held. Costs are {fmt_pct(COST)} per side. An unfilled order labels 0. The "
        "labeler mirrors `seer_engine.sim`, and a test checks it against the simulator.",
        "- **Label purge.** A label is resolved on its exit session, or on its order session if "
        "unfilled. Fold Y trains only on rows whose label resolved on or before the last session of "
        "Y − 1. A trade still open then is left out, so no fold learns from its own traded year.",
        f"- **B.** Gradient-boosted regression trees, `HistGradientBoostingRegressor({tree})`. There "
        "is no hyperparameter search. The model is retrained once per fold on that fold's purged "
        "rows.",
        linear,
        "- **Picks.** Candidates are ranked by predicted label, descending, with the symbol breaking "
        "ties. Only predictions > 0 are kept, so the model may pass on a night. Every survivor gets "
        "A's bracket, and the simulator fills the free slots in that order.",
        f"- **Anchored yearly walk-forward (P3b's folds).** For each trade year Y, the fold trains on "
        f"{r.is_start.isoformat()} → the last session of Y − 1, then trades from the first session "
        f"of Y to the last session of Y (or the data end). Folds: {years}. The traded years form one "
        f"continuous portfolio from {first}. The model switches at each year boundary, and an order "
        "already placed keeps the bracket it was placed with.",
        "- **Strategy A2 (information).** A2's combined walk-forward over the same folds, "
        "recomputed through the P3b pipeline, so that B, A2 and SPY sit on one chart. It is never "
        "gated here.",
        f"- **No look-ahead.** Picks for session S use bars through the previous session only, "
        f"{SPY_SYMBOL}'s included. The universe is S&P 500 ∪ Nasdaq-100 members on that data date "
        "(point in time).",
        "- **One simulator.** Every size, fill, exit and cost (0.1% per side, whole shares, 4 slots) "
        f"comes from `seer_engine.sim`, unchanged. The walk-forward is one fresh portfolio of "
        f"{INITIAL_IDR:,} IDR, converted at the USD/IDR rate of its first session. A held symbol "
        "whose bars end for good is closed at its last close (a forced `time` exit).",
        "- **SPY benchmarks.** They start with the same cash on the session before the first traded "
        "session. They buy whole shares at the first session's open after the 0.1% cost, hold, "
        "and mark at each close. Price-only ignores dividends. Total-return reinvests each dividend "
        "at the ex-date close (whole shares, with cost). At the end, open positions and the SPY "
        "holding are both marked at the last close and never sold.",
        "- **Metrics** follow `web/lib/metrics.ts`:",
        "  - Total return = last / first equity − 1. Every curve starts at the starting cash on "
        "the session before its window.",
        "  - A win is P/L > 0 and a loss is P/L ≤ 0. Profit factor = gross win / gross loss "
        "(∞ with no loss).",
        "  - Max drawdown is measured on per-session equity. Months = calendar days / 30.44.",
        "  - CAGR = (last / first)^(1 / years) − 1, with years = calendar days between the first "
        "and last snapshot / 365.25 (Actual/365.25).",
        "  - Avg days held is the mean of the simulator's `days_held` over closed trades.",
        "- **Diagnostics** explain the result and never feed any fit. They are P/L by exit reason and "
        "by exit year (net of costs), the trades with fewer than 3 shares, cost drag = Σ costs ÷ "
        "Σ gross P/L (both 0.1% sides), the share of nights the model passed, and a calibration "
        "table of mean prediction against mean realized label by prediction decile.",
        "- **Gate (P6a).** Strategy B passes only if the gated curve beats total-return SPY over the "
        "same span, with profit factor ≥ 1.3 and max drawdown ≤ 15%. Nothing else decides it. The "
        f"bar is high: total-return SPY made {fmt_signed_pct(tm.total_return)} over this span, with "
        f"a {fmt_pct(tm.max_drawdown)} max drawdown of its own, and the gate asks for more return "
        "than that with at most a 15% drawdown.",
        probe,
        f"- **Seen before.** P3 already judged Strategy A v1 on the window from "
        f"{SEEN_BEFORE_START.isoformat()} on, so that window is not out-of-sample any more. It is "
        "shown below only as a slice of the continuous curves, for information.",
        "- **One round only.** Strategy B runs once on this data. If it fails the gate, B is not "
        "reworked on this data, and neither B-linear nor A2 can stand in for it.",
        "",
    ]


def _training_table(name: str, wf: BWalkForward) -> list[str]:
    rows: list[list[str]] = []
    for fm in wf.fold_models:
        top = ", ".join(f"`{n}` {fmt_pct(s)}" for n, s in top_features(fm.importance)) or DASH
        rows.append(
            [
                str(fm.fold.year),
                fm.fold.tune_end.isoformat(),
                f"{int(fm.rows):,}",
                _spct(fm.label_mean),
                _spct(fm.pred_mean),
                _signed(fm.r2, 4),
                fmt_pct(fm.positive_share),
                top,
                f"`{fm.model.digest[:12]}`",
            ]
        )
    return [
        f"### {_MODEL_HEADINGS[name]}",
        "",
        f"Top features by {_IMPORTANCE_RULE[name]}.",
        "",
        *_table(
            [
                "Year",
                "Labels resolved through",
                "Rows",
                "Label mean",
                "Pred mean",
                "In-fold R²",
                "Positive share",
                f"Top {TOP_FEATURES} features",
                "Model digest",
            ],
            ["l", "l", "r", "r", "r", "r", "r", "l", "l"],
            rows,
        ),
        "",
    ]


def _training_section(r: BReport) -> list[str]:
    return [
        "## Training per fold",
        "",
        "Each fold trains once, on the rows whose label resolved by the last session before its "
        "traded year. These numbers are in-fold. They explain the model and select nothing. Label "
        "mean and prediction mean are net returns per dollar committed. In-fold R² is information "
        "only (\"—\" when the labels are constant). Positive share is the share of training rows "
        "with a prediction > 0. Feature shares sum to 100% over all "
        f"{len(FEATURE_NAMES)} features.",
        "",
        *_training_table(B, r.b),
        *_training_table(B_LINEAR, r.b_linear),
    ]


def _results_section(r: BReport) -> list[str]:
    runs = _strategy_runs(r)
    ms = [run_metrics(run) for _, run in runs]
    pm = curve_metrics(r.spy_price)
    tm = curve_metrics(r.spy_tr)
    run = r.b.run
    rows: list[list[str]] = [
        [
            "Ending equity (USD)",
            *(_usd(x.snapshots[-1].equity_usd) for _, x in runs),
            _usd(r.spy_price.snapshots[-1].equity_usd),
            _usd(r.spy_tr.snapshots[-1].equity_usd),
        ],
        ["Total return", *(fmt_signed_pct(m.total_return) for m in ms), fmt_signed_pct(pm.total_return), fmt_signed_pct(tm.total_return)],
        ["CAGR", *(fmt_signed_pct(m.cagr) for m in ms), fmt_signed_pct(pm.cagr), fmt_signed_pct(tm.cagr)],
        ["Win rate", *(fmt_pct(m.win_rate) for m in ms), DASH, DASH],
        ["Profit factor", *(fmt_pf(m.profit_factor) for m in ms), DASH, DASH],
        ["Max drawdown", *(fmt_pct(m.max_drawdown) for m in ms), fmt_pct(pm.max_drawdown), fmt_pct(tm.max_drawdown)],
        ["Trades (closed)", *(str(m.trades) for m in ms), DASH, DASH],
        ["Avg days held", *(fmt_num(m.avg_days_held) for m in ms), DASH, DASH],
    ]
    reason_maps = [dict(m.exit_reasons) for m in ms]
    for reason in EXIT_REASONS:
        rows.append([_EXIT_LABELS[reason], *(str(mp.get(reason, 0)) for mp in reason_maps), DASH, DASH])
    rows += [
        ["Forced closes (bars ended; inside time stop)", *(str(forced_closes(x)) for _, x in runs), DASH, DASH],
        ["Open at end", *(str(len(x.open_at_end)) for _, x in runs), DASH, DASH],
        ["Months", *(fmt_num(m.months, 1) for m in ms), fmt_num(pm.months, 1), fmt_num(tm.months, 1)],
        ["SPY shares at end", DASH, DASH, DASH, str(r.spy_price.shares), str(r.spy_tr.shares)],
        ["SPY dividends credited (USD)", DASH, DASH, DASH, DASH, _usd(r.spy_tr.dividends_usd)],
        ["Meets the gate's rules", *(_gate_cell(m, tm.total_return) for m in ms), DASH, DASH],
    ]
    return [
        "## Walk-forward results",
        "",
        "One continuous portfolio over every traded year, per curve. Each year traded the model its "
        "fold trained, and no year's numbers fed any fit. The gated column is the evidence the gate "
        "reads. The other curves are information.",
        "",
        f"### Walk-forward vs SPY ({_span(run)}, {_sessions(run):,} sessions)",
        "",
        *_table(
            ["Metric", *(label for label, _ in runs), "SPY price-only", "SPY total-return"],
            ["l", "r", "r", "r", "r", "r"],
            rows,
        ),
        "",
        "Picks the simulator rejected:",
        "",
        *(f"- {label}: {_rejected(x)}." for label, x in runs),
        "",
    ]


def _years_section(r: BReport) -> list[str]:
    curves = [r.b.run.snapshots, r.b_linear.run.snapshots, r.a2.run.snapshots, r.spy_price.snapshots, r.spy_tr.snapshots]
    rows: list[list[str]] = []
    for f in r.folds:
        rows.append(
            [
                str(f.year),
                _dates(f.trade_start, f.trade_end),
                *(fmt_signed_pct(_segment_return(snaps, f)) for snaps in curves),
            ]
        )
    return [
        "## Year by year",
        "",
        "Each traded year's return, from the close before its first session to its last close.",
        "",
        *_table(
            ["Year", "Traded", _col(r, B), _col(r, B_LINEAR), _A2_LABEL, "SPY price-only", "SPY total-return"],
            ["l", "l", "r", "r", "r", "r", "r"],
            rows,
        ),
        "",
    ]


def _calibration_table(rows: Sequence[CalibrationRow]) -> list[str]:
    out: list[list[str]] = []
    for c in rows:
        if c.rows == 0:
            out.append([str(c.decile), "0", DASH, DASH, DASH])
            continue
        out.append(
            [
                str(c.decile),
                f"{int(c.rows):,}",
                f"{_spct(c.pred_min)} to {_spct(c.pred_max)}",
                _spct(c.pred_mean),
                _spct(c.label_mean),
            ]
        )
    return _table(
        ["Decile", "Rows", "Prediction range", "Mean prediction", "Mean realized label"],
        ["r", "r", "l", "r", "r"],
        out,
    )


def _diagnostics_section(r: BReport) -> list[str]:
    curves = r.curves()
    diags: list[Diagnostics] = [diagnostics(wf.run) for wf in curves]
    names = [_col(r, wf.name) for wf in curves]
    align = ["l"] + ["r"] * len(curves)
    nights = {name: (p, t) for name, p, t in r.passed}

    def night_cell(name: str) -> str:
        p, t = nights[name]
        return f"{p:,} of {t:,} ({fmt_pct(p / t)})" if t else "0"

    summary: list[list[str]] = [
        ["Trades (closed)", *(str(d.trades) for d in diags)],
        [
            "Trades with < 3 shares",
            *(f"{d.small_trades} ({fmt_pct(d.small_trades / d.trades)})" if d.trades else "0" for d in diags),
        ],
        ["Gross P/L (USD)", *(_signed_usd(d.gross_pnl_usd) for d in diags)],
        ["Costs (USD)", *(_usd(d.costs_usd) for d in diags)],
        ["Net P/L (USD)", *(_signed_usd(d.gross_pnl_usd - d.costs_usd) for d in diags)],
        ["Cost drag (costs ÷ gross P/L)", *(fmt_pct(d.cost_drag) for d in diags)],
        ["Nights passed (no pick)", *(night_cell(wf.name) for wf in curves)],
    ]

    by_reason: list[list[str]] = []
    reason_maps = [{reason: (n, pnl) for reason, n, pnl in d.pnl_by_reason} for d in diags]
    for reason in EXIT_REASONS:
        cells: list[str] = []
        for mp in reason_maps:
            n, pnl = mp.get(reason, (0, Decimal("0")))
            cells.append(f"{n} · {_signed_usd(pnl)}")
        by_reason.append([_EXIT_LABELS[reason], *cells])

    year_maps = [{year: (n, pnl) for year, n, pnl in d.pnl_by_year} for d in diags]
    years = sorted({year for mp in year_maps for year in mp})
    by_year: list[list[str]] = []
    for year in years:
        cells = []
        for mp in year_maps:
            item = mp.get(year)
            cells.append(DASH if item is None else f"{item[0]} · {_signed_usd(item[1])}")
        by_year.append([str(year), *cells])

    out = [
        "## Diagnostics",
        "",
        "These numbers explain the result. They never feed a fit. P/L is net of both 0.1% costs. "
        "Gross P/L is (exit − fill) × shares. Cost drag is \"—\" when gross P/L is zero or negative. "
        "A night is passed when the model kept no candidate: none had a valid bracket and a "
        "prediction > 0. Zero picks is allowed (design §5).",
        "",
        *_table(["Measure", *names], align, summary),
        "",
        "### P/L by exit reason (trades · USD)",
        "",
        *_table(["Exit", *names], align, by_reason),
        "",
        "### P/L by exit year (trades · USD)",
        "",
        *(_table(["Year", *names], align, by_year) if by_year else ["No closed trades."]),
        "",
    ]
    for name, rows in r.calibration:
        out += [
            f"### Calibration: {name}",
            "",
            "Every candidate with a valid bracket on a traded session's data date, predicted out of "
            "sample by that year's fold model, with its label resolved by the data end. Sorted by "
            f"prediction and split into {DECILES} groups of (almost) equal size. Mean prediction "
            "against mean realized label shows whether the ranking carries information. It explains "
            "and never selects.",
            "",
            *_calibration_table(rows),
            "",
        ]
    return out


def _seen_before_section(r: BReport) -> list[str]:
    out = ["## Seen before (information only, not out-of-sample)", ""]
    if not _seen_covered(r):
        out += [
            f"The walk-forward window does not include {SEEN_BEFORE_START.isoformat()}, so there "
            "is no slice to show.",
            "",
        ]
        return out
    rows: list[list[str]] = []
    for label, run in _strategy_runs(r):
        m = window_metrics(run, SEEN_BEFORE_START)
        rows.append(
            [
                label,
                fmt_signed_pct(m.total_return),
                fmt_signed_pct(m.cagr),
                fmt_pct(m.win_rate),
                fmt_pf(m.profit_factor),
                fmt_pct(m.max_drawdown),
                str(m.trades),
            ]
        )
    for label, c in (("SPY price-only", r.spy_price), ("SPY total-return", r.spy_tr)):
        m = curve_window_metrics(c, SEEN_BEFORE_START)
        rows.append([label, fmt_signed_pct(m.total_return), fmt_signed_pct(m.cagr), DASH, DASH, fmt_pct(m.max_drawdown), DASH])
    out += [
        f"P3 judged Strategy A v1 on the window from {SEEN_BEFORE_START.isoformat()} on. Because that "
        "window has been looked at, it is not out-of-sample any more. These rows are a slice of the "
        f"same continuous curves ({_dates(SEEN_BEFORE_START, r.b.run.end)}, "
        f"{_slice_sessions(r.b.run):,} sessions, measured from the close before), not a fresh "
        "portfolio. They are information only and never feed the gate.",
        "",
        *_table(
            ["Curve", "Total return", "CAGR", "Win rate", "Profit factor", "Max drawdown", "Trades"],
            ["l", "r", "r", "r", "r", "r", "r"],
            rows,
        ),
        "",
    ]
    return out


def _checklist_section(r: BReport) -> list[str]:
    g = r.gated_curve()
    wf_items = checklist(run_metrics(g.run), curve_metrics(r.spy_tr).total_return)
    seen_items = None
    if _seen_covered(r):
        seen_items = checklist(
            window_metrics(g.run, SEEN_BEFORE_START),
            curve_window_metrics(r.spy_tr, SEEN_BEFORE_START).total_return,
        )
    rows: list[list[str]] = []
    for k, note in enumerate(_CHECK_NOTES):
        rows.append(
            [
                wf_items[k].label,
                note,
                f"{_pass(wf_items[k].ok)}: {wf_items[k].val}",
                DASH if seen_items is None else f"{_pass(seen_items[k].ok)}: {seen_items[k].val}",
            ]
        )
    rows.append(
        [
            "Passed a 10-year backtest under identical rules",
            "#5, decided by the P6a gate",
            f"{_pass(r.verdict.passed)}: P6a gate verdict",
            DASH,
        ]
    )
    return [
        "## Go-live checklist (what a backtest can evaluate)",
        "",
        "These are design §1's fixed rules, computed exactly as the web computes them, on the gated "
        "curve. The \"months forward\" and \"100 trades\" items need forward paper trading, so here "
        "they are information only. \"Beats SPY\" compares with total-return SPY. Only the "
        "walk-forward column is evidence; the seen-before column is information.",
        "",
        *_table(
            ["Item", "Design §1", f"Walk-forward, {r.gated} ({_span(g.run)})", "Seen before (information)"],
            ["l", "l", "l", "l"],
            rows,
        ),
        "",
    ]


def _survivorship_section(r: BReport) -> list[str]:
    rows: list[list[str]] = []
    tot_member = tot_missing = tot_never = tot_other = 0
    for g in r.survivorship:
        rows.append(
            [
                str(g.year),
                f"{g.member_sessions:,}",
                f"{g.missing:,}",
                f"{g.missing_never_fetched:,}",
                f"{g.missing_other:,}",
                fmt_pct(g.missing / g.member_sessions, 2) if g.member_sessions else DASH,
            ]
        )
        tot_member += g.member_sessions
        tot_missing += g.missing
        tot_never += g.missing_never_fetched
        tot_other += g.missing_other
    rows.append(
        [
            "All",
            f"{tot_member:,}",
            f"{tot_missing:,}",
            f"{tot_never:,}",
            f"{tot_other:,}",
            fmt_pct(tot_missing / tot_member, 2) if tot_member else DASH,
        ]
    )
    return [
        "## Survivorship bias",
        "",
        "This walk-forward can only train on and trade stocks that still have price data. "
        f"{r.never_fetched_members:,} stocks were in the S&P 500 or the Nasdaq-100 at some point "
        f"from {r.is_start.isoformat()} to {r.data_end.isoformat()}, but they have no price data at "
        "all. They were delisted or bought out, and the free data source no longer serves them.",
        "",
        "On the days they were index members, Strategy B could not see them, in training or in "
        "trading. **A learned model is more exposed to this than a rule.** Its training labels come "
        "only from survivors, so the losers it never saw are exactly the ones it would have needed "
        "to learn to avoid, and it can absorb the bias into what it learns. **These results are "
        "therefore probably better than reality**, by an amount this data cannot measure.",
        "",
        "The table counts, per year, the (member, session) pairs with no bar:",
        "",
        "- \"Never fetched\" are members with no bars at all.",
        "- \"Other\" are members that have bars elsewhere but none on that session, such as "
        "halts or the days before a listing.",
        "",
        *_table(
            ["Year", "Member-sessions", "Missing", "Never fetched", "Other", "Missing share"],
            ["l", "r", "r", "r", "r", "r"],
            rows,
        ),
        "",
    ]


def _open_positions_section(r: BReport) -> list[str]:
    out = [
        "## Open positions at end",
        "",
        "Positions still live after the last session are marked at that close and never sold, the "
        "same treatment as the SPY holding.",
        "",
    ]
    for label, run in ((B, r.b.run), (B_LINEAR, r.b_linear.run), (_A2_LABEL, r.a2.run)):
        out += [f"### {label}", ""]
        if not run.open_at_end:
            out += ["None.", ""]
            continue
        out += _table(
            ["Symbol", "Status", "Slot", "Session", "Filled", "Fill price", "Shares", "Limit", "TP", "SL", "Days held"],
            ["l", "l", "r", "l", "l", "r", "r", "r", "r", "r", "r"],
            [_order_row(o) for o in run.open_at_end],
        )
        out.append("")
    return out


def _curves_section(r: BReport) -> list[str]:
    stem = report_stem(r.data_end)
    return [
        "## Equity curves",
        "",
        f"![Strategy B and B-linear walk-forward vs Strategy A2, SPY price-only and SPY total-return]({stem}-equity.svg)",
        "",
        f"The daily values of every curve are in [`{stem}-equity.csv`]({stem}-equity.csv). Per-date "
        "predictions are not published: there are about a million of them, and the calibration "
        "tables above summarize them.",
        "",
    ]


def _verdict_section(r: BReport) -> list[str]:
    out = ["## Gate verdict", "", r.verdict.sentence, ""]
    for c in r.verdict.checks:
        out.append(f"- {c.label}: {_pass(c.ok)} ({c.val})")
    out.append("")
    return out


def _next_section(r: BReport) -> list[str]:
    """Only on a failed gate: what was tried, and the owner's options (b), (c), (d) from handover §8."""
    if r.verdict.passed:
        return []
    return [
        "## If the gate failed: what the owner decides next",
        "",
        "Strategy B had one round on this data, and it failed. B is not reworked on this data, and "
        "P4 stays blocked. What was tried, all of it fixed before any result: one gradient-boosted "
        "tree model with fixed hyperparameters and no search, retrained per fold on purged, "
        f"net-of-cost labels over {len(FEATURE_NAMES)} generic features, with A's design bracket and "
        "a positive-prediction threshold; ridge regression (B-linear) beside it as information; and "
        "a pre-registered determinism switch between them. What happens next is the owner's "
        "decision, not this report's. The remaining options are:",
        "",
        "- **(b)** Accept SPY buy-and-hold as the honest champion for now. Seer can still "
        "paper-trade research strategies (P4 without real-money picks), and the home screen "
        "recommends no buys.",
        "- **(c)** Revisit a design §5 trade rule, for example the 5-day time stop, the 4 slots, or "
        "a longer holding horizon. That is a design change, so it needs the owner's explicit "
        "decision and a new handover. It is never done inside a strategy phase.",
        "- **(d)** Strategy C (news + LLM veto) is forward-paper only by design §4, so it cannot "
        "pass a backtest gate. It does not unblock P4 under the current ROADMAP wording, and "
        "changing that wording is the owner's call.",
        "",
    ]


def _frozen_note(r: BReport) -> str:
    f = r.frozen
    last = r.gated_curve().fold_models[-1]
    name = "Frozen in code (`STRATEGY_B_FROZEN`)"
    if f is None and not r.verdict.passed:
        return f"{name}: none. The gate failed, so nothing is deployed and no model artifact is written."
    if f is None:
        return (
            f"{name}: none yet. The gate passed, so `backtest_b` wrote the last fold's model as an "
            "artifact. Set the constant to this report, the artifact, the training cut-off and the "
            "artifact's SHA-256, commit the artifact, and re-run."
        )
    if not r.verdict.passed:
        return f"{name}: set, but the gate failed. Set it back to None and remove the artifact."
    if f.report == _report_path(r.data_end) and f.train_end == last.fold.tune_end:
        return (
            f"{name}: names this report and the last fold's training cut-off. "
            "`tests/test_strategy_b_frozen.py` ties it to the artifact's SHA-256 and the model digest."
        )
    return (
        f"{name}: names a different report or training cut-off. Set it to this report and the last "
        "fold's model, and re-run."
    )


def _machine_section(r: BReport) -> list[str]:
    fm = r.gated_curve().fold_models[-1]
    return [
        "## Machine-readable lines",
        "",
        f"The last fold ({fm.fold.year}) trained the gated model ({r.gated}) on {int(fm.rows):,} rows "
        f"with labels resolved through {fm.fold.tune_end.isoformat()}. Its digest is "
        f"`{fm.model.digest}`. If the gate passes, that model is the one to freeze. The "
        f"`{LAST_FOLD_KEY}` line is its retrain recipe (training cut-off, row count and label sum): "
        "a re-fit from the same rows on the pinned scikit-learn reproduces it bit for bit.",
        "",
        _frozen_note(r),
        "",
        "`tests/test_strategy_b_frozen.py` reads these four lines.",
        "",
        FENCE + "text",
        *machine_lines(r),
        FENCE,
        "",
    ]


def render_markdown(report: BReport) -> str:
    """The full report as Markdown, ending in exactly one newline."""
    _validate(report)
    out: list[str] = [
        f"# Strategy B walk-forward (P6a), data through {report.data_end.isoformat()}",
        "",
        f"**P6a gate verdict:** {report.verdict.sentence}",
        "",
    ]
    out += _data_section(report)
    out += _method_section(report)
    out += _training_section(report)
    out += _results_section(report)
    out += _years_section(report)
    out += _diagnostics_section(report)
    out += _seen_before_section(report)
    out += _checklist_section(report)
    out += _survivorship_section(report)
    out += _open_positions_section(report)
    out += _curves_section(report)
    out += _verdict_section(report)
    out += _next_section(report)
    out += _machine_section(report)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- CSV


def equity_csv(report: BReport) -> str:
    """Wide daily CSV of every curve (USD, 4 dp), header ``EQUITY_CSV_HEADER``."""
    _validate(report)
    curves = [
        report.b.run.snapshots,
        report.b_linear.run.snapshots,
        report.a2.run.snapshots,
        report.spy_price.snapshots,
        report.spy_tr.snapshots,
    ]
    lines = [EQUITY_CSV_HEADER]
    for snaps in zip(*curves):
        lines.append(",".join([snaps[0].date.isoformat(), *(f"{s.equity_usd:f}" for s in snaps)]))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- SVG


def equity_svg(report: BReport) -> str:
    """B (s1), B-linear (v2), A2 (v0), SPY price-only (s2) and SPY total-return (s3)."""
    _validate(report)
    run = report.b.run
    series = (
        ("s1", B, report.b.run.snapshots, run_metrics(report.b.run).total_return),
        ("v2", B_LINEAR, report.b_linear.run.snapshots, run_metrics(report.b_linear.run).total_return),
        ("v0", _A2_LABEL, report.a2.run.snapshots, run_metrics(report.a2.run).total_return),
        ("s2", "SPY price-only", report.spy_price.snapshots, curve_metrics(report.spy_price).total_return),
        ("s3", "SPY total-return", report.spy_tr.snapshots, curve_metrics(report.spy_tr).total_return),
    )
    return _chart(
        f"Strategy B walk-forward vs B-linear, A2 and SPY, {_span(run)}",
        _subtitle(run),
        "Line chart of daily equity in USD for Strategy B, B-linear, the Strategy A2 walk-forward, "
        "SPY price-only and SPY total-return. The values are in the CSV next to this file.",
        series,
    )
```

Notes on the code:
- **Imports the purity test cares about.** The module imports `b_walkforward`, which imports
  `b_model`, which imports scikit-learn. The index's invariant 2 allows that. The source uses no
  `time`, `random`, `logging`, `.now`, `open()` or `print()`. The word "time" appears only inside
  string literals, which the AST check ignores.
- **`gated` in headers.** `_col` appends " (gated)" to the gated curve's column in the results,
  year-by-year and diagnostics tables. The SVG legend keeps plain names, so the chart does not
  change when the switch fires.

**Impact:** a new module only. Nothing imports it until phase 6.

### Step 2: Create `tests/test_backtest_b_report.py` (27 tests)
**File:** `engine/tests/test_backtest_b_report.py:1` (new)
**Change:** a synthetic report, built from:
- phase 4's types and `model_schedule`, `gate_p6a` and `calibration`;
- real models from phase 1's `fit` (a tree and a ridge on 600 × 18 seeded rows, two per kind,
  fitted once at import);
- hand-built `RunResult`s on the same two-fold window as `test_backtest_wf_report.py`
  (2020-01-02 anchored, folds 2021 and 2022, data end 2022-01-31).

A full synthetic-market `execute` run is phase 6's test. Here the inputs are hand-set, so every
rendered number can be asserted exactly.

Facts the fixture produces, checked by running main's identical metrics code:

| Fact | Value |
|---|---|
| Traded sessions (`TRADED`) | 272 |
| 2021 sessions | 252 |
| 40 / 272 | `14.7%` |
| 12 / 272 | `4.4%` |
| B, calibration decile 1 | `−0.500% to −0.410%`, mean `−0.450%`, label `−0.320%` |
| B return, pass branch (delta 2.0) | +38.9% |
| SPY TR return (delta 0.5) | +9.7% |
| A2 return (delta 0.1) | +1.9% |

So A2 fails "Beats SPY" only. Its profit factor is 2.28 and its drawdown is 0.

**Code:**
```python
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
    assert "20,000,000 IDR" in md and "Actual/365.25" in md


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
```

Notes on the tests:
- **The "sits at fold" case.** It reverses the fold models while keeping the run's original
  schedule. `_check_b_curve` checks `fm.fold != f` before it compares schedules, so the per-fold
  error fires first.
- **The "not 'tree'" case.** The B curve gets ridge models and the matching schedule, so the kind
  check fires.
- **`test_calibration_renders_phase_4_output`** assumes phase 4's `calibration` always returns
  `DECILES` rows (via `np.array_split`) and drops NaN labels, as the contract says. If phase 4
  builds the fields from numpy, then `rows` may be a numpy int. The renderer and the test both
  wrap it in `int()`.
- **The "+0.050%" cell.** `to_fixed(0.0005 * 100, 3)` gives `0.050`. The same cell for 2022 is
  `−0.025%` (`0.025` rounds exactly), and the R² cell is `+0.0123`. All were checked with main's
  `to_fixed`.

**Impact:** the suite grows by **27 tests**.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.backtest.b_report"`. Use the worktree's
own venv, after `pip install -e 'engine[dev]'`, because phase 1 added scikit-learn.

**Tests:**
```bash
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_backtest_b_report.py engine/tests/test_strategy_purity.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```
The full-suite count is the count after phase 4 (914) + **27** = **941 passed**, with 0 skipped
(the index's count table).

**Manual check:**
- Write `render_markdown(build_report(passed=False))` from the test fixture to a scratch file and
  read it once for tone against `docs/backtests/2026-10-02-strategy-a2-walkforward.md`.
- Open `equity_svg(...)` in a browser in light and dark mode. The 5 legend entries must not
  overlap or clip.

**Exit criteria:**
- `test_backtest_b_report.py` passes (27 tests), the purity glob still passes, and the full suite
  is green with 0 skipped.
- Every out-of-scope file is unchanged: `git diff --stat 0e91d8a -- engine/src/seer_engine/backtest/{wf_report,report,walkforward,metrics,runner,tuning,benchmark}.py` is empty.

## Assumptions

These come from parallel phases. The reconciler confirmed every one against the other phases'
code blocks (Reconciliation Log).

**Phase 4:**
- `FoldModel` and `BWalkForward` are dataclasses that take the keyword arguments the index
  contract lists, with no `__post_init__` that rejects the hand-set values (`r2=None`, Python
  floats).
- `model_schedule` returns a `ParamsSchedule` that compares equal for the same models.
- `gate_p6a` takes the gated curve name as its 5th positional argument.

**Phase 1:**
- `fit(kind, X, y)` dispatches.
- `BModel.as_dict()` returns `{"kind", "digest"}`.
- `TREE_PARAMS` iterates in the contract order. The test asserts the rendered constructor string
  verbatim.

**Phase 2:**
- `FrozenModel` is a dataclass, so `dataclasses.replace` works on it.
- `FEATURE_NAMES` has the contract's 18 names in the contract's order. The top-feature
  assertions depend on it.

**Phase 3:** `labels.COST == 0.001`, so `fmt_pct(COST) == "0.1%"`.

## Handoffs

**Phase 6** (`backtest_b.execute` / `io.write_b_report`):
- Build `BReport` with:
  - `passed == ((B, p, traded), (B_LINEAR, p, traded))`, straight from phase 4's
    `passed_nights`, whose `traded` is the run's session count (`len(run.snapshots) - 1`).
    `_validate` enforces this;
  - `calibration == ((B, rows), (B_LINEAR, rows))`, each from phase 4's `calibration`;
  - `gated = B if determinism_ok else B_LINEAR`;
  - `verdict = gate_p6a(run_metrics(gated.run), curve_metrics(spy_tr), start, end, gated)`;
  - `frozen = strategies.b.STRATEGY_B_FROZEN`.
- `write_b_report` should render all three texts (`render_markdown`, `equity_csv`, `equity_svg`)
  before writing any file, under the stem `report_stem(data_end)`.
- The artifact that `write_model_artifact` writes is `report.gated_curve().fold_models[-1].model`.

**Phase 7:**
- `FrozenModel.report` must be exactly `"docs/backtests/<stem>.md"` and `train_end` the gated
  last fold's `tune_end`. Otherwise the report's note says "names a different report".
- In the `last-fold-model` JSON, `label_sum` is a **string** (`repr(float)`, read back with
  `float(...)`), `rows` is an int, and `train_end` is an ISO date string (Decision D23).
- `test_strategy_b_frozen.py` should import `GATE_KEY`, `GATED_KEY`, `LAST_FOLD_KEY`,
  `FROZEN_KEY` and `parse_machine_line` from `seer_engine.backtest.b_report`.
- The README module graph gains `b_report → b_walkforward, wf_report, report, walkforward`.

**Not done here (out of scope):** the A2 report's fail section names option (a) Strategy B. That
committed file is frozen by law, so it is not touched.

## Rollback

Delete `engine/src/seer_engine/backtest/b_report.py` and `engine/tests/test_backtest_b_report.py`,
or revert this phase's commit. No other file changes, and nothing imports the module until
phase 6.
