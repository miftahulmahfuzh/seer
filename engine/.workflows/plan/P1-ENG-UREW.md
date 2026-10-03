> Adopted from `STRATEGY_B_RANKER_PLAN.md` phase 6. Source: `.workflows/plan/strategy-b-ranker/phase-6.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 6: `backtest_b` command + io writers

**Plan set:** `STRATEGY_B_RANKER_PLAN.md`
**Analysis:** `20261003-180843-B6R1_code_analyzer.md`
**Satisfies:** R5 (the same inputs give `==` reports and byte-identical files, wall times only in logs), R7 (the command that produces the one real report, run by phase 7)
**Depends on:** Phase 5 (and so, transitively, phases 1–4)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/commands` (primary), `engine/src/seer_engine/backtest` (additive `io.py`)

---

## Goal

`python -m seer_engine backtest_b` exists. It loads the market read-only. It validates the
arguments through `backtest_wf.resolve`, then runs Strategy B and B-linear through phase 4's
walk-forward API. It recomputes A2's combined walk-forward with `backtest_wf`'s own
`tune_all` and `run_walk_forward`, assembles a phase-5 `BReport` and writes the three report
files. When the P6a gate passes, it also writes the gated curve's last-fold model as
`<model-dir>/<data end>-strategy-b.pkl` and logs its SHA-256 and the exact `FrozenModel(...)`
that phase 7 freezes. Every step is timed, and the times appear only in logs. Two `execute`
calls on the same market give `==` reports and byte-identical files.

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- In `seer_engine/backtest/io.py`, additive:
  - `MODELS_DIR` (`config.REPO_ROOT / "engine" / "data" / "models"`);
  - `write_b_report(out_dir: Path, report: b_report.BReport) -> list[Path]`;
  - `write_model_artifact(model_dir: Path, data_end: date, model: b_model.BModel) -> tuple[Path, str]`.
- `seer_engine/commands/backtest_b.py` (new):
  - `HELP`, `DEFAULT_OUT` (`is backtest_wf.DEFAULT_OUT`);
  - `add_arguments(p)`: calls `backtest_wf.add_arguments(p)`, then adds `--model-dir`;
  - `run(args) -> int`;
  - `execute(market, bars_rows, dividends, is_start, first_year, end) -> BReport`;
  - `recompute_a2(market, folds) -> walkforward.WalkForward`. **This one is not in the index
    contract.** It is a public helper so the A2 step is one named, timed unit;
  - private helpers `_train`, `_walk_forward`, `_calibration`, `_labelled_rows`, `_gated_curve`,
    `_freeze`, `_log_not_frozen`, `_frozen_literal`, `_repo_path`, `_since`, `_r2`.
- `engine/tests/test_backtest_b_command.py` (new). It adds **23 tests**.

**Signature changes:** none. The existing `io.py` functions are untouched. Only the module
docstring and the import block grow.

**Requires (from earlier phases), exactly as the index contract states them:**
- Phase 1, `strategies/b_model.py`:
  - `TREE`, `RIDGE`, `TREE_PARAMS`;
  - `BModel` with value `__eq__` on `(kind, n_features, digest)`;
  - `fit_ridge(X, y)`, `dumps(model) -> bytes`, `loads(bytes) -> BModel`, `sha256(bytes) -> str` (hex).
- Phase 2, `strategies/b.py`:
  - `prepare_b(history) -> BPrepared`, with `.raw` (rows, 18) and `.symbols`;
  - `FrozenModel(report: str, artifact: str, train_end: date, sha256: str)`, a frozen dataclass
    with value equality;
  - the module attribute `STRATEGY_B_FROZEN`. It is read through the module at call time, so a
    `monkeypatch` or phase 7's edit is seen.
- Phase 4, `backtest/b_walkforward.py`:
  - `B`, `B_LINEAR`;
  - `candidate_table(market, prepared, is_start, end) -> CandidateTable`, with `.data_dates`,
    `.limit` and `.labels.label` / `.labels.resolved`;
  - `train_folds(table, folds, kind) -> tuple[FoldModel, ...]`;
  - `FoldModel` with `.fold`, `.model`, `.rows`, `.label_mean`, `.pred_mean`, `.r2` and
    `.positive_share`;
  - `probe_determinism(table, fold) -> bool`;
  - `walk_forward_b(market, prepared, folds, fold_models, name) -> BWalkForward`, with `.name`,
    `.fold_models` and `.run`;
  - `oos_predictions(table, folds, fold_models) -> (row indices, predictions)`;
  - `calibration(pred, label) -> tuple[CalibrationRow, ...]`. **It filters unresolved (NaN)
    labels itself**: this phase passes `table.labels.label[rows]` unfiltered. It raises
    ValueError when fewer than `DECILES` (10) labels are resolved; the synthetic market here
    resolves hundreds of out-of-sample rows, and P3b's real windows over a million;
  - `passed_nights(table, folds, fold_models) -> (passed, traded)`, where `traded` is
    `len(dates.sessions(folds[0].trade_start, folds[-1].trade_end))` == `len(run.snapshots) - 1`
    (phase 4 contract item 8);
  - `gate_p6a(wf, spy_tr, start, end, gated) -> Verdict`.
- Phase 5, `backtest/b_report.py`:
  - `BReport`, with exactly the contract's 21 fields, in keyword form;
  - `report_stem(data_end)`, `render_markdown`, `equity_csv`, `equity_svg`;
  - `parse_machine_line`, `GATE_KEY`, `GATED_KEY`, `EQUITY_CSV_HEADER`;
  - `b_report` must **not** import `backtest.io`, or the imports go circular.
- **Value equality across two `execute` calls (R5).** `BReport.__eq__` must hold field by field.
  That needs `BWalkForward`, `FoldModel`, `CalibrationRow` and `BReport` to compare by value.
  Phase 4's `FoldModel` is `@dataclass(frozen=True)` (value equality), and the reconciled index
  contract now says so (Decision D20). `CandidateTable` stays `eq=False`, because it is not a
  `BReport` field.

**Leaves alone (owned by others):**
- `commands/backtest_wf.py`, `commands/backtest.py`, `cli.py`. They are imported only.
  `backtest_wf.add_arguments`, `resolve`, `BacktestWfError`, `tune_all`, `run_walk_forward`,
  `DEFAULT_OUT`, `_pct` and `_num` are reused, never copied.
- `backtest/walkforward.py`, `wf_report.py`, `runner.py`, `benchmark.py`, `metrics.py`.
- Every existing function in `backtest/io.py`.
- `strategies/*`: phases 1 and 2, and phase 7 for `STRATEGY_B_FROZEN`.
- `backtest/b_walkforward.py` (phase 4) and `backtest/b_report.py` (phase 5).
- Every existing test file.
- `docs/`, `engine/package_readme.md` and `engine/data/models/`. Phase 7 owns them.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/io.py` | modify (additive) | docstring lines 1–2; imports at lines 19, 30 and after 40 (`datetime`, `b_report`, `b_model`); `MODELS_DIR` after line 46; `write_b_report` and `write_model_artifact` appended after line 316 |
| `engine/src/seer_engine/commands/backtest_b.py` | create | the command |
| `engine/tests/test_backtest_b_command.py` | create | 23 tests: discovery, help, both writers, `execute` determinism, fields, logs, wall times, A2 equality, `run` pass/fail/frozen, exit-2 preconditions, and the end-to-end CLI run |

Three files. `cli.py` discovers the module by its name, and `strategies/__init__.py` is
phase 2's (the reconciled index table says 3).

## Implementation Steps

### Step 1: `io.py`, the docstring and imports
**File:** `engine/src/seer_engine/backtest/io.py:1-2` and `:16-41`
**Change:**
- The first two docstring lines name the new writers.
- Add `datetime` to the `datetime` import.
- Import `b_report` alongside `wf_report`.
- Import `b_model`.

Nothing else in the header changes.

**Code.** Replace lines 1–2:
```python
"""Impure edge of the backtest: read the database once, read the vendored SPY dividends,
write the report files (v1's ``write_report``, the walk-forward ``write_wf_report``, Strategy B's
``write_b_report``) and Strategy B's model artifact (``write_model_artifact``).
```
The rest of the docstring, from `The only module in ``seer_engine.backtest`` that touches…`,
is unchanged.

Replace line 19 (`from datetime import date`):
```python
from datetime import date, datetime
```
Replace line 30 (`from seer_engine.backtest import wf_report`):
```python
from seer_engine.backtest import b_report, wf_report
```
Insert after line 40 (`from seer_engine.prices import to_decimal`):
```python
from seer_engine.strategies import b_model
```
**Impact:** importing `backtest.io` now loads `b_report` → `b_walkforward` → `b_model` →
scikit-learn. That changes nothing functionally, because `cli.discover` already imports every
command module and so `backtest_b` (Risk K1). `io.py` is the purity test's one exempt module.

### Step 2: `io.py`, `MODELS_DIR`
**File:** `engine/src/seer_engine/backtest/io.py:46` (insert after `DIVIDENDS_CSV = ...`)
**Code:**
```python
MODELS_DIR = config.REPO_ROOT / "engine" / "data" / "models"
```
**Impact:** none. It is a new constant.

### Step 3: `io.py`, `write_b_report` and `write_model_artifact`
**File:** `engine/src/seer_engine/backtest/io.py:316` (append after `write_wf_report`, at the end
of the file)
**Code:**
```python


def write_b_report(out_dir: Path, report: b_report.BReport) -> list[Path]:
    """Write Strategy B's walk-forward report set into ``out_dir`` (created if needed) with LF
    line endings and return the paths in this order: <stem>.md, <stem>-equity.csv,
    <stem>-equity.svg. All three are rendered before any is written, so a render error leaves
    no partial set."""
    out_dir = Path(out_dir)
    stem = b_report.report_stem(report.data_end)
    files = (
        (f"{stem}.md", b_report.render_markdown(report)),
        (f"{stem}-equity.csv", b_report.equity_csv(report)),
        (f"{stem}-equity.svg", b_report.equity_svg(report)),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, text in files:
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def write_model_artifact(model_dir: Path, data_end: date, model: b_model.BModel) -> tuple[Path, str]:
    """Write ``b_model.dumps(model)`` to ``<model_dir>/<data_end>-strategy-b.pkl`` (the directory
    is created if needed) and return ``(path, sha256 hex of the written bytes)``.

    The bytes are serialized first and land through a temporary file plus ``os.replace``, so a
    failure never leaves a truncated artifact. Re-writing the same model gives the same bytes.
    """
    if isinstance(data_end, datetime) or not isinstance(data_end, date):
        raise TypeError(f"data_end must be a date, got {type(data_end).__name__}")
    if not isinstance(model, b_model.BModel):
        raise TypeError(f"model must be a b_model.BModel, got {type(model).__name__}")
    data = b_model.dumps(model)
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    path = model_dir / f"{data_end.isoformat()}-strategy-b.pkl"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return path, b_model.sha256(data)
```
**Impact:**
- Additive only.
- `os` is already imported (line 17).
- `b_report` is reached through the module attribute, so tests can monkeypatch its renderers,
  as `test_backtest_wf_command.py` does for `wf_report`.

### Step 4: the command module
**File:** `engine/src/seer_engine/commands/backtest_b.py` (new)
**Code:**
```python
"""`backtest_b`: Strategy B (the learned cross-sectional ranker) and B-linear under P3b's
anchored yearly walk-forward (roadmap P6a), against A2's walk-forward and SPY, and the report
files. Read-only on the database.

Flow:
  1. load the market (bars via the local cache in --cache-dir, universe, fx_rates) on one
     connection, closed before any computation; read the SPY dividends file; validate the
     arguments with backtest_wf.resolve (the same folds and preconditions as P3b)
  2. prepare Strategy B's raw features once; build the candidate table: every candidate row
     with its bracket and its net-of-cost label
  3. per fold, fit the tree (B) and the ridge (B-linear) on that fold's purged rows; refit the
     last fold's tree at 1 thread and at the default thread count and compare the digests: the
     pre-registered determinism switch (Decision D13) gates B-linear when they differ
  4. trade each curve's fold models as one continuous portfolio; recompute A2's combined
     walk-forward through backtest_wf's own tune_all and run_walk_forward (information only)
  5. SPY price-only and total-return curves, survivorship, passed nights, the out-of-sample
     calibration table, the P6a gate on the gated curve; STRATEGY_B_FROZEN read at call time
  6. write <stem>.md, -equity.csv, -equity.svg to --out; when the gate passed, also write the
     gated curve's last-fold model to --model-dir and log its SHA-256 and the exact
     STRATEGY_B_FROZEN value that freezes it (phase 7 commits both)

Every step is timed; wall times go to the log only, never into a report file.

Exit 0 whether the gate passes or fails (a losing verdict is a result); 2 when the data or
the arguments cannot back a run; 1 on any other error (cli.main).
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import time
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from seer_engine import config, db
from seer_engine.backtest import b_walkforward as bw
from seer_engine.backtest import io as backtest_io
from seer_engine.backtest import walkforward
from seer_engine.backtest.b_report import BReport
from seer_engine.backtest.benchmark import Dividend, spy_curves
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import curve_metrics, run_metrics
from seer_engine.backtest.runner import survivorship
from seer_engine.backtest.walkforward import Fold, WalkForward
from seer_engine.commands import backtest_wf
from seer_engine.commands.backtest import never_fetched_members
from seer_engine.strategies import a2 as strategy_a2
from seer_engine.strategies import b as strategy_b
from seer_engine.strategies import b_model

log = logging.getLogger(__name__)

HELP = (
    "Backtest Strategy B (learned ranker) and B-linear under the anchored yearly walk-forward "
    "vs A2 and SPY (P6a gate), write the report and, on a pass, the model artifact (read-only)"
)

DEFAULT_OUT = backtest_wf.DEFAULT_OUT


def add_arguments(p: argparse.ArgumentParser) -> None:
    """backtest_wf's flags (same names, defaults and parsers), plus --model-dir."""
    backtest_wf.add_arguments(p)
    p.add_argument(
        "--model-dir",
        type=Path,
        default=backtest_io.MODELS_DIR,
        metavar="DIR",
        help="where a passing run writes the gated last-fold model (default: engine/data/models)",
    )


def run(args: argparse.Namespace) -> int:
    if getattr(args, "dry_run", False):
        log.info(
            "dry-run: backtest_b never writes to the database; the report files and a passing "
            "run's model artifact are written as usual"
        )
    try:
        with contextlib.closing(db.connect()) as conn:
            market, bars_rows = backtest_io.load_market(
                conn, cache_dir=args.cache_dir, refresh=args.refresh_cache
            )
        dividends = backtest_io.read_dividends(args.dividends)
        w = backtest_wf.resolve(market, args.is_start, args.first_year, args.end)
    except FileNotFoundError as e:
        log.error("dividends file not found: %s", e.filename)
        return 2
    except (backtest_io.LoadError, backtest_wf.BacktestWfError) as e:
        log.error("%s", e)
        return 2

    report = execute(market, bars_rows, dividends, w.is_start, w.first_year, w.end)
    paths = backtest_io.write_b_report(args.out, report)
    for path in paths:
        log.info("wrote %s", path)
    if report.verdict.passed:
        _freeze(report, paths[0], args.model_dir)
    else:
        _log_not_frozen(report.frozen)
    return 0


def execute(
    market: Market,
    bars_rows: int,
    dividends: Sequence[Dividend],
    is_start: date,
    first_year: int,
    end: date,
) -> BReport:
    """Everything between loading and writing. Pure except for logging and wall-time reads,
    so two calls on the same inputs return ``==`` reports."""
    t_all = time.perf_counter()
    folds = walkforward.folds(is_start, first_year, end)
    log.info(
        "%d fold(s), %d..%d: training anchored at %s, trading %s..%s",
        len(folds),
        folds[0].year,
        folds[-1].year,
        is_start.isoformat(),
        folds[0].trade_start.isoformat(),
        folds[-1].trade_end.isoformat(),
    )

    t0 = time.perf_counter()
    prepared = strategy_b.prepare_b(market.history)
    log.info(
        "prepared Strategy B features: %d (symbol, date) rows over %d symbols (%.2fs)",
        int(prepared.raw.shape[0]),
        len(prepared.symbols),
        _since(t0),
    )

    t0 = time.perf_counter()
    table = bw.candidate_table(market, prepared, is_start, end)
    candidate_rows = int(table.data_dates.shape[0])
    labelled_rows = _labelled_rows(table)
    log.info(
        "candidate table: %d rows on %d data dates, %d with a valid bracket and a resolved label (%.2fs)",
        candidate_rows,
        int(np.unique(table.data_dates).shape[0]),
        labelled_rows,
        _since(t0),
    )

    tree_models = _train(table, folds, b_model.TREE, bw.B)
    ridge_models = _train(table, folds, b_model.RIDGE, bw.B_LINEAR)

    t0 = time.perf_counter()
    determinism_ok = bw.probe_determinism(table, folds[-1])
    gated = bw.B if determinism_ok else bw.B_LINEAR
    if determinism_ok:
        log.info(
            "determinism probe on fold %d: the tree refit at 1 thread equals the default-thread "
            "refit, so %s is gated (%.2fs)",
            folds[-1].year,
            gated,
            _since(t0),
        )
    else:
        log.warning(
            "determinism probe on fold %d: the tree refit at 1 thread differs from the "
            "default-thread refit, so the pre-registered switch gates %s and %s is information "
            "only (%.2fs)",
            folds[-1].year,
            bw.B_LINEAR,
            bw.B,
            _since(t0),
        )

    b_wf = _walk_forward(market, prepared, folds, tree_models, bw.B)
    b_linear_wf = _walk_forward(market, prepared, folds, ridge_models, bw.B_LINEAR)

    a2 = recompute_a2(market, folds)

    # Exactly what b_report._validate recomputes: SPY curves over folds[0].trade_start ->
    # folds[-1].trade_end with the B run's starting cash, and the gate over the gated run's span.
    t0 = time.perf_counter()
    trade_start, trade_end = folds[0].trade_start, folds[-1].trade_end
    spy_price, spy_tr = spy_curves(market.spy(), trade_start, trade_end, b_wf.run.initial_cash, dividends)
    tr_m = curve_metrics(spy_tr)
    log.info(
        "SPY %s..%s: total return %s, price-only %s (%.2fs)",
        trade_start.isoformat(),
        trade_end.isoformat(),
        backtest_wf._pct(tr_m.total_return),
        backtest_wf._pct(curve_metrics(spy_price).total_return),
        _since(t0),
    )

    t0 = time.perf_counter()
    gaps = survivorship(market, is_start, end)
    never_fetched = never_fetched_members(market, is_start, end)
    log.info(
        "survivorship: %d (member, session) pairs without a bar over %d year(s); "
        "%d member(s) in the window never had bars (%.2fs)",
        sum(g.missing for g in gaps),
        len(gaps),
        never_fetched,
        _since(t0),
    )

    passed_rows: list[tuple[str, int, int]] = []
    for wf in (b_wf, b_linear_wf):
        t0 = time.perf_counter()
        passed, traded = bw.passed_nights(table, folds, wf.fold_models)
        log.info(
            "%s passed nights: %d of %d traded sessions (%.1f%%) (%.2fs)",
            wf.name,
            passed,
            traded,
            100.0 * passed / traded if traded else 0.0,
            _since(t0),
        )
        passed_rows.append((wf.name, int(passed), int(traded)))

    calibration_rows: list[tuple[str, tuple[bw.CalibrationRow, ...]]] = []
    for wf in (b_wf, b_linear_wf):
        t0 = time.perf_counter()
        rows = _calibration(table, folds, wf.fold_models)
        log.info(
            "%s calibration: %d decile(s) over %d out-of-sample labelled rows (%.2fs)",
            wf.name,
            len(rows),
            sum(r.rows for r in rows),
            _since(t0),
        )
        calibration_rows.append((wf.name, rows))

    t0 = time.perf_counter()
    gated_wf = b_wf if gated == bw.B else b_linear_wf
    verdict = bw.gate_p6a(run_metrics(gated_wf.run), tr_m, gated_wf.run.start, gated_wf.run.end, gated)
    log.info("gate %s: %s (%.2fs)", "PASSED" if verdict.passed else "FAILED", verdict.sentence, _since(t0))

    frozen = strategy_b.STRATEGY_B_FROZEN
    log.info(
        "STRATEGY_B_FROZEN at run time: %s",
        "None" if frozen is None else _frozen_literal(frozen),
    )

    report = BReport(
        data_end=end,
        bars_rows=bars_rows,
        symbols_with_bars=len(market.history),
        never_fetched_members=never_fetched,
        survivorship=gaps,
        is_start=is_start,
        folds=folds,
        candidate_rows=candidate_rows,
        labelled_rows=labelled_rows,
        determinism_ok=determinism_ok,
        gated=gated,
        b=b_wf,
        b_linear=b_linear_wf,
        a2=a2,
        passed=tuple(passed_rows),
        calibration=tuple(calibration_rows),
        spy_price=spy_price,
        spy_tr=spy_tr,
        verdict=verdict,
        frozen=frozen,
    )
    log.info("execute: done (%.2fs)", _since(t_all))
    return report


def recompute_a2(market: Market, folds: Sequence[Fold]) -> WalkForward:
    """A2's combined walk-forward over ``folds``, computed exactly as ``backtest_wf.execute``
    computes its ``combined`` curve: ``STRATEGY_A2.prepare``, ``backtest_wf.tune_all`` over
    ``walkforward.combinations()``, then ``backtest_wf.run_walk_forward(..., None)``. Both of
    those log every run with its wall time. Information only: never gated (Decision D12)."""
    t_a2 = time.perf_counter()
    strategy = strategy_a2.STRATEGY_A2
    t0 = time.perf_counter()
    prepared = strategy.prepare(market.history)
    log.info(
        "A2 recompute: prepared Strategy A2 features for %d symbols (%.2fs)",
        len(market.history),
        _since(t0),
    )
    fold_rows = backtest_wf.tune_all(market, strategy, prepared, walkforward.combinations(), folds)
    combined = backtest_wf.run_walk_forward(market, strategy, prepared, folds, fold_rows, None)
    log.info("A2 recompute: done (%.2fs)", _since(t_a2))
    return combined


# --------------------------------------------------------------------------- steps


def _train(table: bw.CandidateTable, folds: Sequence[Fold], kind: str, name: str) -> tuple[bw.FoldModel, ...]:
    """``bw.train_folds`` for one model kind, with one log line per fold and the total time."""
    t0 = time.perf_counter()
    models = bw.train_folds(table, folds, kind)
    elapsed = _since(t0)
    for fm in models:
        log.info(
            "%s fold %d (trained through %s): %d rows, label mean %+.5f, in-fold R² %s, "
            "pred mean %+.5f, positive share %.1f%%, digest %s",
            name,
            fm.fold.year,
            fm.fold.tune_end.isoformat(),
            fm.rows,
            fm.label_mean,
            _r2(fm.r2),
            fm.pred_mean,
            100.0 * fm.positive_share,
            fm.model.digest[:12],
        )
    log.info("%s: %d fold model(s) fitted (%.2fs)", name, len(models), elapsed)
    return models


def _walk_forward(
    market: Market,
    prepared: Any,
    folds: Sequence[Fold],
    fold_models: Sequence[bw.FoldModel],
    name: str,
) -> bw.BWalkForward:
    """One B curve traded as one continuous portfolio, logged with its headline metrics."""
    t0 = time.perf_counter()
    wf = bw.walk_forward_b(market, prepared, folds, fold_models, name)
    m = run_metrics(wf.run)
    log.info(
        "%s %s..%s: return %s, PF %s, max DD %s, trades %d (%.2fs)",
        wf.name,
        wf.run.start.isoformat(),
        wf.run.end.isoformat(),
        backtest_wf._pct(m.total_return),
        backtest_wf._num(m.profit_factor),
        backtest_wf._pct(m.max_drawdown),
        m.trades,
        _since(t0),
    )
    return wf


def _calibration(
    table: bw.CandidateTable, folds: Sequence[Fold], fold_models: Sequence[bw.FoldModel]
) -> tuple[bw.CalibrationRow, ...]:
    """The out-of-sample calibration table: each traded row's prediction by its own fold's
    model against its label (unresolved labels are dropped by ``bw.calibration``)."""
    rows, pred = bw.oos_predictions(table, folds, fold_models)
    return bw.calibration(pred, table.labels.label[rows])


def _labelled_rows(table: bw.CandidateTable) -> int:
    """Candidate rows with a valid bracket (finite limit) and a resolved label."""
    valid = ~np.isnan(table.limit)
    resolved = ~np.isnat(table.labels.resolved)
    return int(np.count_nonzero(valid & resolved))


# --------------------------------------------------------------------------- freeze


def _gated_curve(report: Any) -> bw.BWalkForward:
    return report.b if report.gated == bw.B else report.b_linear


def _freeze(report: Any, report_path: Path, model_dir: Path) -> None:
    """The gate passed: write the gated curve's last-fold model, and say what to freeze."""
    fm = _gated_curve(report).fold_models[-1]
    path, digest = backtest_io.write_model_artifact(model_dir, report.data_end, fm.model)
    log.info(
        "wrote %s (%s model of fold %d, trained through %s, sha256 %s)",
        path,
        report.gated,
        fm.fold.year,
        fm.fold.tune_end.isoformat(),
        digest,
    )
    expected = strategy_b.FrozenModel(
        report=_repo_path(report_path),
        artifact=_repo_path(path),
        train_end=fm.fold.tune_end,
        sha256=digest,
    )
    if report.frozen == expected:
        log.info("STRATEGY_B_FROZEN matches this run's artifact (sha256 %s)", digest)
        return
    log.warning(
        "the P6a gate passed: freeze the model by setting STRATEGY_B_FROZEN = %s in "
        "strategies/b.py (it is %s now), commit %s, and re-run so the report records it",
        _frozen_literal(expected),
        "None" if report.frozen is None else _frozen_literal(report.frozen),
        _repo_path(path),
    )


def _log_not_frozen(frozen: Any) -> None:
    """The gate failed: no artifact is written, and STRATEGY_B_FROZEN must stay None."""
    if frozen is None:
        log.info("STRATEGY_B_FROZEN is None, as it stays after a failed gate; no model artifact written")
    else:
        log.warning(
            "STRATEGY_B_FROZEN is set (%s) but the gate failed; it must stay None",
            _frozen_literal(frozen),
        )


def _frozen_literal(f: Any) -> str:
    """The Python source of a FrozenModel, ready to paste into strategies/b.py."""
    d = f.train_end
    return (
        f"FrozenModel(report={f.report!r}, artifact={f.artifact!r}, "
        f"train_end=date({d.year}, {d.month}, {d.day}), sha256={f.sha256!r})"
    )


def _repo_path(path: Path) -> str:
    """``path`` relative to the repository root in POSIX form, or absolute when outside it."""
    p = Path(path).resolve()
    try:
        return p.relative_to(config.REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


# --------------------------------------------------------------------------- formatting


def _since(t0: float) -> float:
    return time.perf_counter() - t0


def _r2(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.4f}"
```
**Impact:**
- `cli.discover()` picks the module up by its name (`backtest_b`), and `cli.py` is not edited.
- `run`, `execute` and `backtest_io.write_b_report` are looked up through module globals or
  attributes, so tests can monkeypatch them.
- `time` is a module global, so a test can swap in a fake clock and prove that wall times never
  reach the report.

Design notes, binding for the implementer:
- **Reuse, not copies.**
  - `add_arguments` delegates to `backtest_wf.add_arguments`, so the flags are guaranteed
    identical to `backtest_wf`'s.
  - Preconditions are `backtest_wf.resolve`. `BacktestWfError` exits 2.
  - The A2 curve is `backtest_wf.tune_all` + `backtest_wf.run_walk_forward(..., None)` over
    `walkforward.combinations()`.
  - `_pct` and `_num` come from `backtest_wf`.
- **The artifact model** is `_gated_curve(report).fold_models[-1].model`: the tree if `gated == B`,
  the ridge if the determinism switch fired.
- **Paths in `FrozenModel` are repo-relative** (for example `docs/backtests/<stem>.md` and
  `engine/data/models/<end>-strategy-b.pkl`), which is the form the contract's `FrozenModel`
  comment shows.
- **The order of steps follows the contract**, and every fit and run is sequential (D18).
- **No wall-clock value enters `BReport`.** Its fields carry none.

### Step 5: tests
**File:** `engine/tests/test_backtest_b_command.py` (new)

The synthetic market is 16 traded symbols plus SPY over 2022-01-03 → 2023-06-30 (375 sessions):
- `IS_S = SESSIONS[200]`, which is 2022-10-19;
- `FIRST_YEAR = 2023`, so there is **one fold**.

Why one fold: A2's tuning span is `[is_start, last fold's tune_end]`.
- One fold keeps it to about 50 sessions. 324 combinations then took **1.27 s**, measured on
  `0e91d8a` with main's venv; `walkforward` and `backtest_wf` are unchanged there.
- Two folds would make the span about 300 sessions, at **7.2 s** per tuning, and this file tunes
  A2 four times.

Fold 2023 trains on about 50 data dates × 16 symbols ≈ 800 rows. That is above
`2 × min_samples_leaf = 400`, so the trees really split. The test asserts the bound.

`execute` runs twice in a module-scoped fixture, and the second run uses fake clocks. One more
run comes from `backtest_wf.execute`, for the A2 comparison, and another from the end-to-end
CLI run. The expected added wall time is about 15–25 s.

**Code:**
```python
"""`backtest_b` command: discovery, the two io writers, execute's determinism and contents,
wall times in logs only, A2's curve against backtest_wf's, the artifact on a pass only,
preconditions (exit 2), and an end-to-end run on a synthetic schema.

The synthetic market has one fold (2023) so that A2's 324-combination tuning pass covers about
50 sessions. Fold 2023 still trains on more than 2 x min_samples_leaf rows, so the trees split.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, cli, config, dates, db, fx
from seer_engine.backtest import b_report
from seer_engine.backtest import b_walkforward as bw
from seer_engine.backtest import io as bio
from seer_engine.backtest import walkforward
from seer_engine.backtest.benchmark import parse_dividends
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.metrics import curve_metrics, run_metrics
from seer_engine.backtest.tuning import IS_START
from seer_engine.commands import backtest_b as cmd
from seer_engine.commands import backtest_wf as cmd_wf
from seer_engine.strategies import b as strategy_b
from seer_engine.strategies import b_model
from seer_engine.strategies.base import history_from_bars

SESSIONS = dates.sessions(date(2022, 1, 3), date(2023, 6, 30))
IS_S = SESSIONS[200]  # 2022-10-19: data_date SESSIONS[199] is the 200th bar
FIRST_YEAR = 2023  # one fold: train through 2022-12-30, trade 2023-01-03..END
END = SESSIONS[-1]  # 2023-06-30
FX_LATE = SESSIONS[300]
DIVIDEND_DAY = SESSIONS[320]  # inside the traded window
TRADED = tuple(f"S{k:02d}" for k in range(16))
SPY_K = 20
LONG_AGO = date(2015, 1, 2)
STEM = f"{END.isoformat()}-strategy-b-walkforward"
FILE_NAMES = [f"{STEM}.md", f"{STEM}-equity.csv", f"{STEM}-equity.svg"]
ARTIFACT_NAME = f"{END.isoformat()}-strategy-b.pkl"
DIVIDENDS_TEXT = f"ex_date,amount_usd\n{DIVIDEND_DAY.isoformat()},0.75\n"
DIVIDENDS = parse_dividends(DIVIDENDS_TEXT)
EXPECTED_ROWS = (len(TRADED) + 1) * len(SESSIONS)
DURATION = re.compile(r"\((\d+\.\d{2})s\)")

# Messages execute must log, each with its wall time "(N.NNs)".
TIMED_PREFIXES = (
    "prepared Strategy B features: ",
    "candidate table: ",
    f"{bw.B}: 1 fold model(s) fitted ",
    f"{bw.B_LINEAR}: 1 fold model(s) fitted ",
    "determinism probe on fold 2023: ",
    "A2 recompute: prepared Strategy A2 features ",
    "A2 recompute: done ",
    "SPY ",
    "survivorship: ",
    f"{bw.B} passed nights: ",
    f"{bw.B_LINEAR} passed nights: ",
    f"{bw.B} calibration: ",
    f"{bw.B_LINEAR} calibration: ",
    "gate ",
    "execute: done ",
)


def ohlcv(k: int, n: int) -> list[tuple[float, float, float, float, int]]:
    """A rising sawtooth whose cycle length, drift, phase and volume depend on k, so features
    and labels vary across symbols and dates. Close >= ~30 and volume >= 2M keep every symbol
    above the $20M liquidity floor."""
    price = 30.0 + 2.5 * k
    cycle = 9 + k % 5
    drift = 1.004 + 0.0005 * (k % 4)
    out = []
    for i in range(n):
        phase = (i + 2 * k) % cycle
        if phase in (cycle - 3, cycle - 2):
            price *= 0.965
        elif phase == cycle - 1:
            price *= 1.05
        else:
            price *= drift
        c = round(price, 4)
        o = round(c * (0.995 + 0.001 * (phase % 3)), 4)
        out.append((o, round(c * 1.018, 4), round(c * 0.972, 4), c, 2_000_000 + 25_000 * k + 40_000 * phase))
    return out


def synthetic_bars(*, with_spy: bool = True) -> list:
    rows = []
    for k, symbol in enumerate(TRADED):
        rows += [bars.make_bar(symbol, d, *v) for d, v in zip(SESSIONS, ohlcv(k, len(SESSIONS)))]
    if with_spy:
        rows += [bars.make_bar("SPY", d, *v) for d, v in zip(SESSIONS, ohlcv(SPY_K, len(SESSIONS)))]
    return rows


def in_memory_market() -> Market:
    """The same data as seed(), without a database (SPY not a member, GONE has no bars)."""
    by_symbol: dict[str, list] = {}
    for b in synthetic_bars():
        by_symbol.setdefault(b.symbol, []).append(b)
    history = {s: history_from_bars(s, rows) for s, rows in sorted(by_symbol.items())}
    intervals = tuple(sorted((s, LONG_AGO, None) for s in (*TRADED, "GONE")))
    return Market(
        history=history,
        membership=Membership(intervals=intervals),
        fx=((SESSIONS[0], Decimal("16000")), (FX_LATE, Decimal("16250.5"))),
    )


def seed(conn, *, with_bars=True, with_spy=True, fx_rows=((SESSIONS[0], "16000"), (FX_LATE, "16250.5"))):
    with db.transaction(conn, False):
        if with_bars:
            bars.upsert_bars(conn, synthetic_bars(with_spy=with_spy))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, NULL, %s)",
                [(s, "SP500", LONG_AGO, s) for s in (*TRADED, "GONE")],
            )
        fx.upsert_fx(conn, list(fx_rows))


def write_dividends(tmp_path):
    path = tmp_path / "spy_dividends.csv"
    path.write_text(DIVIDENDS_TEXT, encoding="utf-8")
    return path


def argv(tmp_path, *extra):
    return [
        "backtest_b",
        "--out", str(tmp_path / "out"),
        "--cache-dir", str(tmp_path / "cache"),
        "--model-dir", str(tmp_path / "models"),
        "--is-start", IS_S.isoformat(),
        "--first-year", str(FIRST_YEAR),
        "--end", END.isoformat(),
        "--dividends", str(tmp_path / "spy_dividends.csv"),
        *extra,
    ]


def checksums(conn):
    out = {}
    for table, order in {
        "bars": "x.symbol, x.date",
        "universe": "x.index_id, x.symbol, x.start_date",
        "fx_rates": "x.date",
        "strategies": "x.id",
        "runs": "x.id",
        "orders": "x.id",
        "equity_snapshots": "x.strategy_id, x.date",
    }.items():
        with conn.cursor(row_factory=tuple_row) as cur:
            cur.execute(
                f"SELECT count(*), coalesce(md5(string_agg(x::text, '|' ORDER BY {order})), '') "
                f"FROM {table} x"
            )
            out[table] = cur.fetchone()
    conn.rollback()
    return out


@pytest.fixture
def point_cli_at(pg_schema, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", pg_schema.url)


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _fake_clock(step: float = 1000.0) -> SimpleNamespace:
    """A perf_counter that advances ``step`` seconds per call: every logged duration >= step."""
    state = {"t": 0.0}

    def perf_counter() -> float:
        state["t"] += step
        return state["t"]

    return SimpleNamespace(perf_counter=perf_counter)


def _execute_logged() -> tuple[object, list[str]]:
    handler = _ListHandler()
    logger = logging.getLogger("seer_engine")
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        report = cmd.execute(in_memory_market(), EXPECTED_ROWS, DIVIDENDS, IS_S, FIRST_YEAR, END)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    return report, handler.messages


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """execute twice on fresh copies of the same market: once on the real clock, once on fake
    clocks in backtest_b and backtest_wf (1000 s per reading). Both report sets are written."""
    first, first_logs = _execute_logged()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cmd, "time", _fake_clock())
        mp.setattr(cmd_wf, "time", _fake_clock())
        second, second_logs = _execute_logged()
    paths1 = bio.write_b_report(tmp_path_factory.mktemp("b-out1"), first)
    paths2 = bio.write_b_report(tmp_path_factory.mktemp("b-out2"), second)
    return SimpleNamespace(
        first=first,
        second=second,
        first_logs=first_logs,
        second_logs=second_logs,
        paths1=paths1,
        paths2=paths2,
    )


def _stand_in(base, *, passed: bool, gated: str, frozen=None) -> SimpleNamespace:
    """What run() reads from a report, with the verdict and gated curve chosen by the test and
    the real fold models of ``base``. A stand-in, so no BReport invariant is bypassed."""
    return SimpleNamespace(
        data_end=END,
        verdict=SimpleNamespace(passed=passed, sentence="stand-in verdict"),
        gated=gated,
        b=base.b,
        b_linear=base.b_linear,
        frozen=frozen,
    )


def _patch_run(monkeypatch, report) -> tuple[list, list]:
    seen: list = []
    calls: list = []

    def fake_execute(market, bars_rows, dividends, is_start, first_year, end):
        seen.append((bars_rows, dividends, is_start, first_year, end))
        return report

    def fake_write(out_dir, rep):
        calls.append((Path(out_dir), rep))
        return [Path(out_dir) / name for name in FILE_NAMES]

    monkeypatch.setattr(cmd, "execute", fake_execute)
    monkeypatch.setattr(bio, "write_b_report", fake_write)
    return seen, calls


# ---- no database -----------------------------------------------------------------------------


def test_discovered_with_defaults():
    assert "backtest_b" in cli.discover()
    args = cli.build_parser().parse_args(["backtest_b"])
    assert args._run is cmd.run
    assert args.out == cmd.DEFAULT_OUT == cmd_wf.DEFAULT_OUT == config.REPO_ROOT / "docs" / "backtests"
    assert args.model_dir == bio.MODELS_DIR == config.REPO_ROOT / "engine" / "data" / "models"
    assert args.cache_dir == bio.CACHE_DIR
    assert args.dividends == bio.DIVIDENDS_CSV
    assert (args.is_start, args.first_year, args.end) == (IS_START, walkforward.FIRST_TRADE_YEAR, None)
    assert args.refresh_cache is False
    assert cmd.HELP


def test_help_lists_every_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["backtest_b", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in (
        "--out", "--cache-dir", "--refresh-cache", "--is-start",
        "--first-year", "--end", "--dividends", "--model-dir",
    ):
        assert flag in out, flag


def test_write_b_report_writes_three_files_in_order_with_lf(tmp_path, monkeypatch):
    texts = {
        "render_markdown": "# md\nline\n",
        "equity_csv": b_report.EQUITY_CSV_HEADER + "\n",
        "equity_svg": "<svg>equity</svg>\n",
    }
    for name, text in texts.items():
        monkeypatch.setattr(b_report, name, lambda report, _t=text: _t)
    paths = bio.write_b_report(tmp_path / "nested" / "out", SimpleNamespace(data_end=END))
    assert b_report.report_stem(END) == STEM
    assert [p.name for p in paths] == FILE_NAMES
    assert [p.read_bytes() for p in paths] == [t.encode("utf-8") for t in texts.values()]


def test_write_b_report_renders_everything_before_writing(tmp_path, monkeypatch):
    for name in ("render_markdown", "equity_csv"):
        monkeypatch.setattr(b_report, name, lambda report: "ok\n")

    def boom(report):
        raise RuntimeError("svg render failed")

    monkeypatch.setattr(b_report, "equity_svg", boom)
    with pytest.raises(RuntimeError, match="svg render failed"):
        bio.write_b_report(tmp_path / "out", SimpleNamespace(data_end=END))
    assert not (tmp_path / "out").exists()


def test_write_model_artifact_writes_dumps_and_returns_its_sha256(tmp_path):
    X = np.array([[0.0, 1.0], [1.0, 0.0], [2.0, 1.0], [3.0, 3.0], [4.0, 2.0]], dtype=np.float64)
    y = np.array([0.01, -0.02, 0.03, 0.05, 0.02], dtype=np.float64)
    model = b_model.fit_ridge(X, y)
    model_dir = tmp_path / "models" / "deep"

    path, digest = bio.write_model_artifact(model_dir, END, model)

    assert path == model_dir / ARTIFACT_NAME
    data = path.read_bytes()
    assert data == b_model.dumps(model)
    assert digest == hashlib.sha256(data).hexdigest() == b_model.sha256(data)
    assert b_model.loads(data) == model
    assert [p.name for p in model_dir.iterdir()] == [ARTIFACT_NAME]  # no temp file left behind
    assert bio.write_model_artifact(model_dir, END, model) == (path, digest)
    assert path.read_bytes() == data
    with pytest.raises(TypeError):
        bio.write_model_artifact(model_dir, END, "not a model")


def test_execute_twice_is_equal_and_byte_identical(runs):
    assert runs.first == runs.second
    assert [p.name for p in runs.paths1] == FILE_NAMES
    assert [p.name for p in runs.paths2] == FILE_NAMES
    for p1, p2 in zip(runs.paths1, runs.paths2):
        assert p1.read_bytes() == p2.read_bytes(), p1.name
    md = runs.paths1[0].read_text(encoding="utf-8")
    assert runs.first.verdict.sentence in md
    assert b_report.parse_machine_line(md, b_report.GATE_KEY) == (
        "passed" if runs.first.verdict.passed else "failed"
    )
    assert b_report.parse_machine_line(md, b_report.GATED_KEY) == runs.first.gated


def test_execute_report_fields(runs):
    r = runs.first
    folds = walkforward.folds(IS_S, FIRST_YEAR, END)
    assert r.data_end == END
    assert r.bars_rows == EXPECTED_ROWS
    assert r.symbols_with_bars == len(TRADED) + 1  # + SPY
    assert r.never_fetched_members == 1  # GONE
    assert [g.year for g in r.survivorship] == [2022, 2023]
    assert r.is_start == IS_S
    assert r.folds == folds
    assert 0 < r.labelled_rows <= r.candidate_rows
    assert r.gated == (bw.B if r.determinism_ok else bw.B_LINEAR)
    assert (r.b.name, r.b_linear.name) == (bw.B, bw.B_LINEAR)
    min_rows = 2 * b_model.TREE_PARAMS["min_samples_leaf"]
    for wf, kind in ((r.b, b_model.TREE), (r.b_linear, b_model.RIDGE)):
        assert wf.folds == folds
        assert [fm.fold for fm in wf.fold_models] == list(folds)
        assert all(fm.model.kind == kind for fm in wf.fold_models)
        assert all(fm.rows >= min_rows for fm in wf.fold_models)  # the trees really split
        assert (wf.run.start, wf.run.end) == (folds[0].trade_start, END)
    assert r.a2.name == walkforward.COMBINED
    assert (r.a2.run.start, r.a2.run.end) == (folds[0].trade_start, END)
    traded = len(dates.sessions(folds[0].trade_start, folds[-1].trade_end))
    assert [p[0] for p in r.passed] == [bw.B, bw.B_LINEAR]
    assert all(0 <= p[1] <= p[2] == traded for p in r.passed)
    assert [c[0] for c in r.calibration] == [bw.B, bw.B_LINEAR]
    assert all(sum(row.rows for row in c[1]) <= r.labelled_rows for c in r.calibration)
    for curve in (r.spy_price, r.spy_tr):
        assert curve.snapshots[0].date == r.b.run.snapshots[0].date
        assert curve.snapshots[-1].date == END
    assert r.spy_tr.dividends_usd > 0
    gated_wf = r.b if r.gated == bw.B else r.b_linear
    assert r.verdict == bw.gate_p6a(
        run_metrics(gated_wf.run), curve_metrics(r.spy_tr), gated_wf.run.start, gated_wf.run.end, r.gated
    )
    assert r.frozen == strategy_b.STRATEGY_B_FROZEN


def test_execute_logs_every_step_with_its_wall_time(runs):
    logs = runs.first_logs
    for prefix in TIMED_PREFIXES:
        hits = [m for m in logs if m.startswith(prefix)]
        assert hits, prefix
        assert all(DURATION.search(m) for m in hits), prefix
    start = walkforward.folds(IS_S, FIRST_YEAR, END)[0].trade_start.isoformat()
    for prefix in (
        "1 fold(s), 2023..2023: ",
        f"{bw.B} fold 2023 ",
        f"{bw.B_LINEAR} fold 2023 ",
        f"{bw.B} {start}..{END.isoformat()}: return ",
        f"{bw.B_LINEAR} {start}..{END.isoformat()}: return ",
        f"{walkforward.COMBINED} {start}..{END.isoformat()}: return ",
        "STRATEGY_B_FROZEN at run time: ",
    ):
        assert sum(1 for m in logs if m.startswith(prefix)) == 1, prefix
    n = len(walkforward.combinations())
    assert sum(1 for m in logs if m.startswith("tune ") and f"/{n} " in m) == n
    assert sum(1 for m in logs if m.startswith(f"tune: {n} runs on ")) == 1
    assert any(m.startswith("gate ") and runs.first.verdict.sentence in m for m in logs)


def test_wall_times_reach_logs_only(runs):
    real = [float(x) for m in runs.first_logs for x in DURATION.findall(m)]
    fake = [float(x) for m in runs.second_logs for x in DURATION.findall(m)]
    assert real and len(real) == len(fake)
    assert all(x < 1000.0 for x in real)
    assert all(x >= 1000.0 for x in fake)  # the fake clocks really drove the second run's logs
    assert runs.first == runs.second
    for p1, p2 in zip(runs.paths1, runs.paths2):
        assert p1.read_bytes() == p2.read_bytes(), p1.name
        assert not DURATION.search(p1.read_text(encoding="utf-8")), p1.name


def test_a2_curve_equals_backtest_wf_combined_on_the_same_market(runs):
    wf = cmd_wf.execute(in_memory_market(), EXPECTED_ROWS, DIVIDENDS, IS_S, FIRST_YEAR, END)
    assert runs.first.a2 == wf.combined
    assert runs.first.a2.selections == wf.combined.selections
    assert runs.first.a2.run.snapshots == wf.combined.run.snapshots


# ---- run(): the artifact on a pass only ---------------------------------------------------------


@pytest.mark.parametrize("gated", [bw.B, bw.B_LINEAR])
def test_run_pass_writes_the_gated_curves_last_fold_model(
    pg, point_cli_at, tmp_path, monkeypatch, caplog, runs, gated
):
    seed(pg)
    write_dividends(tmp_path)
    report = _stand_in(runs.first, passed=True, gated=gated)
    seen, calls = _patch_run(monkeypatch, report)
    caplog.set_level(logging.INFO)

    assert cli.main(argv(tmp_path)) == 0

    assert seen == [(EXPECTED_ROWS, DIVIDENDS, IS_S, FIRST_YEAR, END)]
    assert len(calls) == 1 and calls[0][0] == tmp_path / "out" and calls[0][1] is report
    curve = runs.first.b if gated == bw.B else runs.first.b_linear
    other = runs.first.b_linear if gated == bw.B else runs.first.b
    path = tmp_path / "models" / ARTIFACT_NAME
    assert [p.name for p in (tmp_path / "models").iterdir()] == [ARTIFACT_NAME]
    data = path.read_bytes()
    assert data == b_model.dumps(curve.fold_models[-1].model)
    assert data != b_model.dumps(other.fold_models[-1].model)
    digest = hashlib.sha256(data).hexdigest()
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith(f"wrote {path} ") and digest in m for m in messages)
    freeze = [m for m in messages if "STRATEGY_B_FROZEN = FrozenModel(" in m]
    assert len(freeze) == 1
    assert digest in freeze[0]
    tune_end = curve.fold_models[-1].fold.tune_end
    assert f"train_end=date({tune_end.year}, {tune_end.month}, {tune_end.day})" in freeze[0]


def test_run_fail_writes_the_report_but_no_artifact(pg, point_cli_at, tmp_path, monkeypatch, caplog, runs):
    seed(pg)
    write_dividends(tmp_path)
    report = _stand_in(runs.first, passed=False, gated=bw.B)
    _, calls = _patch_run(monkeypatch, report)
    caplog.set_level(logging.INFO)

    assert cli.main(argv(tmp_path)) == 0

    assert len(calls) == 1
    assert not (tmp_path / "models").exists()
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("STRATEGY_B_FROZEN is None, as it stays after a failed gate") for m in messages)


def test_run_pass_with_matching_frozen_constant_logs_the_match(
    pg, point_cli_at, tmp_path, monkeypatch, caplog, runs
):
    seed(pg)
    write_dividends(tmp_path)
    fm = runs.first.b.fold_models[-1]
    artifact = tmp_path / "models" / ARTIFACT_NAME
    frozen = strategy_b.FrozenModel(
        report=cmd._repo_path(tmp_path / "out" / FILE_NAMES[0]),
        artifact=cmd._repo_path(artifact),
        train_end=fm.fold.tune_end,
        sha256=hashlib.sha256(b_model.dumps(fm.model)).hexdigest(),
    )
    report = _stand_in(runs.first, passed=True, gated=bw.B, frozen=frozen)
    _patch_run(monkeypatch, report)
    caplog.set_level(logging.INFO)

    assert cli.main(argv(tmp_path)) == 0

    assert artifact.is_file()
    assert any(r.getMessage().startswith("STRATEGY_B_FROZEN matches this run's artifact") for r in caplog.records)
    assert not any(
        r.levelno >= logging.WARNING and "STRATEGY_B_FROZEN" in r.getMessage() for r in caplog.records
    )


# ---- preconditions (exit 2, nothing written) -----------------------------------------------


def _nothing_written(tmp_path) -> bool:
    return not (tmp_path / "out").exists() and not (tmp_path / "models").exists()


def test_empty_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_bars=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert _nothing_written(tmp_path)


def test_no_spy_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_spy=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert _nothing_written(tmp_path)


@pytest.mark.parametrize(
    "extra",
    [
        ["--end", dates.next_session(END).isoformat()],  # after the last SPY bar
        ["--end", date(2023, 6, 10).isoformat()],  # a Saturday
        ["--first-year", "2022"],  # fold 2022 would train on nothing before is_start
        ["--first-year", "2024"],  # no fold: 2024's first session is after --end
    ],
)
def test_bad_windows_exit_2(pg, point_cli_at, tmp_path, extra):
    seed(pg)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path, *extra)) == 2
    assert _nothing_written(tmp_path)


def test_no_fx_before_is_start_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, fx_rows=((FX_LATE, "16250.5"),))
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert _nothing_written(tmp_path)


def test_missing_dividends_file_exits_2(pg, point_cli_at, tmp_path):
    seed(pg)
    assert cli.main(argv(tmp_path)) == 2  # no spy_dividends.csv written
    assert _nothing_written(tmp_path)


# ---- end to end ------------------------------------------------------------------------------


def test_end_to_end_cli_run_is_read_only_and_writes_the_report_set(pg, point_cli_at, tmp_path, caplog):
    seed(pg)
    write_dividends(tmp_path)
    caplog.set_level(logging.INFO)
    before = checksums(pg)

    assert cli.main(argv(tmp_path)) == 0

    assert checksums(pg) == before  # read-only
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(FILE_NAMES)
    assert [p.name for p in (tmp_path / "cache").iterdir()] == [f"bars-{END.isoformat()}-{EXPECTED_ROWS}.pkl"]
    md = (tmp_path / "out" / FILE_NAMES[0]).read_text(encoding="utf-8")
    gate = b_report.parse_machine_line(md, b_report.GATE_KEY)
    assert gate in ("passed", "failed")
    artifact = tmp_path / "models" / ARTIFACT_NAME
    assert artifact.is_file() == (gate == "passed")
    assert (tmp_path / "models").exists() == (gate == "passed")
    messages = [r.getMessage() for r in caplog.records]
    assert sum(1 for m in messages if m.startswith("wrote ")) == len(FILE_NAMES) + (1 if gate == "passed" else 0)
    assert any(m.startswith("execute: done ") for m in messages)
```
**Impact:**
- Adds **23 tests**:
  - discovery 1, help 1;
  - `write_b_report` 2, `write_model_artifact` 1;
  - `execute` determinism 1, fields 1, logs 1, wall times 1;
  - A2 equality 1;
  - `run` on a pass 2 (parametrized), on a fail 1, with a matching frozen constant 1;
  - exit 2: empty bars 1, no SPY 1, bad windows 4 (parametrized), no fx 1, missing dividends 1;
  - end to end 1.
- Every DB test uses the `pg` fixture. With `PG_TEST_URL` set, none skips.
- The helper code is written fresh in this file and does not import from
  `test_backtest_wf_command.py`. No existing test file is edited.

## Verification

**Build:**
```
cd /home/miftah/.worktrees/seer/strategy-b-ranker
engine/.venv/bin/pip install -e 'engine[dev]'          # the worktree's own venv; idempotent
engine/.venv/bin/python -m seer_engine backtest_b --help
```
**Tests:**
```
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_backtest_b_command.py -q --durations=10
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```
**Manual checks:**
- `git diff --stat 0e91d8a -- engine/src/seer_engine/commands/backtest_wf.py engine/src/seer_engine/cli.py engine/src/seer_engine/backtest/wf_report.py engine/src/seer_engine/backtest/walkforward.py engine/tests/test_backtest_wf_command.py`
  is empty.
- `git diff 0e91d8a -- engine/src/seer_engine/backtest/io.py` shows only additions, plus the 2
  replaced docstring lines and 2 replaced import lines.
- `--durations` shows the new file adds no more than about 30 s. If `runs` exceeds that, the fix is
  fewer symbols. It is **not** fewer A2 combinations, because the A2 step must run the real
  `walkforward.combinations()`.

**Exit criteria:**
- The full suite passes with 0 skipped: the count after phase 5 (941), plus exactly 23 =
  **964 passed**.
- `python -m seer_engine backtest_b --help` lists `--model-dir`.
- Two `execute` calls give `==` `BReport`s and byte-identical files, under different clocks.
- An artifact is written only when `verdict.passed`, and it is the gated curve's last-fold model.

## Handoffs

- **H1 → Phase 4 (contract conflict, R5). Resolved by the reconciler (D20): phase 4 already
  declares `@dataclass(frozen=True)`, and the index contract was amended.** The draft index declared
  `@dataclass(frozen=True, eq=False) class FoldModel`.
  - With `eq=False`, `BWalkForward.__eq__` compares `fold_models` by identity, so two `execute`
    calls can never give `==` `BReport`s, and phase 4's own "two identical calls give `==`
    results" fails the same way.
  - `FoldModel` must use the default `eq=True`. Every field is value-comparable: `Fold`, `BModel`
    (digest equality), ints, finite floats, `float | None` and a tuple of floats.
  - The reconciler should amend the contract. `CandidateTable` and `Labels` can stay `eq=False`,
    because no `BReport` field holds them.
- **H2 → Phase 4. Confirmed by the reconciler (D21).** `calibration(pred, label)` must drop rows
  whose label is NaN (unresolved) itself. This phase passes `table.labels.label[rows]` straight from `oos_predictions`' row
  indices.
- **H3 → Phase 4. Confirmed by the reconciler.** `passed_nights(...)[1]` ("traded sessions") is
  asserted to equal `len(dates.sessions(folds[0].trade_start, folds[-1].trade_end))`, which is
  phase 4's own definition and equals `len(run.snapshots) - 1`.
- **H4 → Phase 5.** `b_report` must not import `backtest.io`, which now imports `b_report`.
  If `BReport` validates in `__post_init__`, that is fine. This phase builds `BReport` only from
  real values, and its `run` tests use a `SimpleNamespace` stand-in rather than
  `dataclasses.replace`.
  `_validate`, wherever it runs, must accept the SPY curves built with `b.run.initial_cash` over
  `folds[0].trade_start..folds[-1].trade_end`, and the verdict
  `gate_p6a(run_metrics(gated.run), curve_metrics(spy_tr), gated.run.start, gated.run.end, gated)`.
  Those are the exact recomputations `execute` uses.
- **H5 → Phase 5.** `labelled_rows` is computed here as "finite `limit` and non-NaT `resolved`".
  If `_validate` recomputes it, it must use the same rule.
- **H6 → Phase 7.**
  - Run with the default `--model-dir` (`engine/data/models`) and the default `--out`.
  - On a pass, the WARNING line `... set STRATEGY_B_FROZEN = FrozenModel(report='docs/backtests/<stem>.md', artifact='engine/data/models/<end>-strategy-b.pkl', train_end=date(Y, M, D), sha256='…') ...`
    is the literal to paste into `strategies/b.py`.
  - A re-run then logs `STRATEGY_B_FROZEN matches this run's artifact` and rewrites the artifact
    byte-identically.
  - The `.pkl` is not gitignored. Commit it on a pass only.
- **H7 → Phase 7 (readme, R9).** `engine/package_readme.md` should document:
  - `backtest_b`'s flags (as `backtest_wf`'s, plus `--model-dir`);
  - its exit codes;
  - the measured wall time per step, read from the logs of the real run.
- **H8 → Phase 2.** `FrozenModel` must be a value-equal dataclass (the contract's
  `frozen=True, slots=True` gives that). `STRATEGY_B_FROZEN` must stay a module attribute that
  `backtest_b` reads as `strategy_b.STRATEGY_B_FROZEN` at call time.

## Risks

- **K1.** `cli.discover()` imports every command module, so after this phase every CLI command,
  the nightly job included, imports scikit-learn through `backtest_b` → `b_walkforward` →
  `b_model`. That costs about 0.5–1 s of startup and changes nothing functionally.
  Lazy-importing inside `execute` would avoid it, but it would hide the import graph. That is
  deliberately not done here (Decision D19: eager imports, scikit-learn is a core dependency);
  record it for the readme (phase 7).
- **K2.** If a fold has no purged training rows (a very short `--is-start..tune_end`), phase 4's
  `train_folds` → `b_model.check_xy` raises `ValueError`. `cli.main` then exits 1, not 2. P3b's
  real windows always have rows. Adding a precondition would mean a B-specific `resolve`, which
  is out of scope.
- **K3.** The synthetic market has one fold, so "last fold" is also the only fold in these tests.
  Phase 4's tests own multi-fold chaining and the year boundary.

## Rollback

Revert this phase's commit. Doing so:
- deletes `commands/backtest_b.py` and `tests/test_backtest_b_command.py`;
- restores `backtest/io.py` to its phase-5 state, removing the 2 docstring lines, the 2 import
  edits, `MODELS_DIR` and the two appended functions.

No other module references these symbols until phase 7, so the tree stays green.
