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
