"""`backtest_wf`: Strategy A2 under an anchored yearly walk-forward (roadmap P3b), compared
with SPY, and the report files. Read-only on the database.

Flow:
  1. load the market (bars via the local cache in --cache-dir, universe, fx_rates) on one
     connection, closed before any computation; read the SPY dividends file; validate the
     arguments against the data
  2. prepare Strategy A2 once (param- and variant-independent, causal features)
  3. the tuning pass: one run per combination (4 variants x 81 grid = 324) over
     [is_start, last fold's tune_end], sliced per fold; wall time logged per run and in total
  4. per fold, select on that fold's tuning window only: once over all 324 rows (the combined
     walk-forward) and once per variant (the per-variant curves)
  5. each schedule traded as one continuous portfolio from the first fold's first session to
     --end; SPY price-only and total-return curves over the same window; survivorship;
     the P3b gate on the combined curve
  6. write <stem>.md, -equity.csv, -equity.svg, -variants.svg, -grid.csv to --out; log the
     verdict and whether STRATEGY_A2_PARAMS equals the last fold's selection

Exit 0 whether the gate passes or fails (a losing verdict is a result); 2 when the data or
the arguments cannot back a run; 1 on any other error (cli.main).
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from seer_engine import config, dates, db
from seer_engine.backtest import io as backtest_io
from seer_engine.backtest import walkforward
from seer_engine.backtest.benchmark import Dividend, spy_curves
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import curve_metrics, run_metrics
from seer_engine.backtest.runner import survivorship
from seer_engine.backtest.tuning import IS_START, GridRow
from seer_engine.backtest.walkforward import FIRST_TRADE_YEAR, Fold, WalkForward
from seer_engine.backtest.wf_report import WalkForwardReport
from seer_engine.commands.backtest import never_fetched_members
from seer_engine.strategies import a2 as strategy_a2
from seer_engine.universe import BENCHMARK

log = logging.getLogger(__name__)

HELP = (
    "Backtest Strategy A2 under an anchored yearly walk-forward vs SPY (P3b gate), "
    "write the report (read-only)"
)

DEFAULT_OUT = config.REPO_ROOT / "docs" / "backtests"


class BacktestWfError(RuntimeError):
    """The data or the arguments cannot back a walk-forward run (exit 2)."""


@dataclass(frozen=True)
class WfWindows:
    is_start: date
    first_year: int
    end: date


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from e


def _year(value: str) -> int:
    try:
        year = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected a year YYYY, got {value!r}") from e
    if not 1900 <= year <= 9999:
        raise argparse.ArgumentTypeError(f"expected a year YYYY, got {value!r}")
    return year


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        metavar="DIR",
        help="directory for the report files (default: docs/backtests)",
    )
    p.add_argument(
        "--cache-dir",
        type=Path,
        default=backtest_io.CACHE_DIR,
        metavar="DIR",
        help="where the bars pickle is cached (default: engine/.cache)",
    )
    p.add_argument(
        "--refresh-cache",
        action="store_true",
        help="re-download bars even when the cache matches the table",
    )
    p.add_argument(
        "--is-start",
        type=_iso_date,
        default=IS_START,
        metavar="YYYY-MM-DD",
        help=f"first session of every (anchored) tuning window (default: {IS_START.isoformat()})",
    )
    p.add_argument(
        "--first-year",
        type=_year,
        default=FIRST_TRADE_YEAR,
        metavar="YYYY",
        help=f"first traded year; fold Y tunes on [is-start, last session of Y-1] (default: {FIRST_TRADE_YEAR})",
    )
    p.add_argument(
        "--end",
        type=_iso_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="last traded session (default: the last SPY bar)",
    )
    p.add_argument(
        "--dividends",
        type=Path,
        default=backtest_io.DIVIDENDS_CSV,
        metavar="PATH",
        help="SPY dividends CSV, ex_date,amount_usd (default: engine/data/spy_dividends.csv)",
    )


def run(args: argparse.Namespace) -> int:
    if getattr(args, "dry_run", False):
        log.info("dry-run: backtest_wf never writes to the database; report files are written as usual")
    try:
        with contextlib.closing(db.connect()) as conn:
            market, bars_rows = backtest_io.load_market(
                conn, cache_dir=args.cache_dir, refresh=args.refresh_cache
            )
        dividends = backtest_io.read_dividends(args.dividends)
        w = resolve(market, args.is_start, args.first_year, args.end)
    except FileNotFoundError as e:
        log.error("dividends file not found: %s", e.filename)
        return 2
    except (backtest_io.LoadError, BacktestWfError) as e:
        log.error("%s", e)
        return 2

    report = execute(market, bars_rows, dividends, w.is_start, w.first_year, w.end)
    paths = backtest_io.write_wf_report(args.out, report)
    for path in paths:
        log.info("wrote %s", path)
    return 0


def resolve(market: Market, is_start: date, first_year: int, end: date | None) -> WfWindows:
    """Validate the arguments against the loaded data; raise BacktestWfError if they cannot
    back a run. ``end`` None means the last SPY bar."""
    spy_last = market.last_bar_date(BENCHMARK)
    if spy_last is None:
        raise BacktestWfError(f"no {BENCHMARK} bars loaded; the regime filter and the benchmark curves need them")
    end = spy_last if end is None else end
    for flag, d in (("--is-start", is_start), ("--end", end)):
        if not dates.is_session(d):
            raise BacktestWfError(f"{flag} {d.isoformat()} is not an NYSE session")
    if end > spy_last:
        raise BacktestWfError(
            f"--end {end.isoformat()} is after the last {BENCHMARK} bar {spy_last.isoformat()}"
        )
    try:
        walkforward.folds(is_start, first_year, end)
    except ValueError as e:
        raise BacktestWfError(
            f"no walk-forward folds for --is-start {is_start.isoformat()}, --first-year {first_year}, "
            f"--end {end.isoformat()}: {e}"
        ) from e
    try:
        market.usd_idr_on(is_start)
    except ValueError as e:
        raise BacktestWfError(f"no fx_rates row on or before {is_start.isoformat()}") from e
    return WfWindows(is_start=is_start, first_year=first_year, end=end)


def execute(
    market: Market,
    bars_rows: int,
    dividends: Sequence[Dividend],
    is_start: date,
    first_year: int,
    end: date,
) -> WalkForwardReport:
    """Everything between loading and writing. Pure except for logging and wall-time reads."""
    strategy = strategy_a2.STRATEGY_A2
    folds = walkforward.folds(is_start, first_year, end)
    log.info(
        "%d fold(s), %d..%d: tuning anchored at %s, trading %s..%s",
        len(folds),
        folds[0].year,
        folds[-1].year,
        is_start.isoformat(),
        folds[0].trade_start.isoformat(),
        folds[-1].trade_end.isoformat(),
    )

    t0 = time.perf_counter()
    prepared = strategy.prepare(market.history)
    log.info(
        "prepared Strategy A2 features for %d symbols in %.1fs",
        len(market.history),
        time.perf_counter() - t0,
    )

    combos = walkforward.combinations()
    fold_rows = tune_all(market, strategy, prepared, combos, folds)

    combined = run_walk_forward(market, strategy, prepared, folds, fold_rows, None)
    variants = tuple(
        run_walk_forward(market, strategy, prepared, folds, fold_rows, v)
        for v in strategy_a2.VARIANTS
    )

    # Exactly what wf_report._validate recomputes (phase 4): SPY curves over
    # folds[0].trade_start -> folds[-1].trade_end, and the gate over the combined run's own span.
    trade_start, trade_end = folds[0].trade_start, folds[-1].trade_end
    spy_price, spy_tr = spy_curves(market.spy(), trade_start, trade_end, combined.run.initial_cash, dividends)
    wf_m = run_metrics(combined.run)
    tr_m = curve_metrics(spy_tr)
    log.info(
        "%s %s..%s: return %s vs SPY total return %s, SPY price-only %s",
        combined.name,
        trade_start.isoformat(),
        trade_end.isoformat(),
        _pct(wf_m.total_return),
        _pct(tr_m.total_return),
        _pct(curve_metrics(spy_price).total_return),
    )

    gaps = survivorship(market, is_start, end)
    never_fetched = never_fetched_members(market, is_start, end)
    log.info(
        "survivorship: %d (member, session) pairs without a bar over %d year(s); "
        "%d member(s) in the window never had bars",
        sum(g.missing for g in gaps),
        len(gaps),
        never_fetched,
    )

    verdict = walkforward.gate_p3b(wf_m, tr_m, combined.run.start, combined.run.end)
    log.info("gate %s: %s", "PASSED" if verdict.passed else "FAILED", verdict.sentence)
    frozen = strategy_a2.STRATEGY_A2_PARAMS
    _log_frozen(frozen, combined.selections[-1].params, verdict.passed)

    return WalkForwardReport(
        data_end=end,
        bars_rows=bars_rows,
        symbols_with_bars=len(market.history),
        never_fetched_members=never_fetched,
        survivorship=gaps,
        is_start=is_start,
        folds=folds,
        fold_rows=fold_rows,
        combined=combined,
        variants=variants,
        spy_price=spy_price,
        spy_tr=spy_tr,
        verdict=verdict,
        frozen_params=frozen,
    )


def tune_all(
    market: Market,
    strategy: Any,
    prepared: Any,
    combos: Sequence[Any],
    folds: Sequence[Fold],
) -> tuple[tuple[GridRow, ...], ...]:
    """``walkforward.tune(market, strategy, prepared, combos, folds)``, one combination at a
    time so each run is timed and logged. Sequential, in ``combos`` order, so the result is
    ``==`` the single call: result[k] is fold k's rows in ``combos`` order."""
    total = len(combos)
    per_fold: list[list[GridRow]] = [[] for _ in folds]
    t_all = time.perf_counter()
    for i, combo in enumerate(combos, 1):
        t0 = time.perf_counter()
        one = walkforward.tune(market, strategy, prepared, (combo,), folds)
        if len(one) != len(folds) or any(len(rows) != 1 for rows in one):
            raise RuntimeError(
                f"walkforward.tune returned {[len(rows) for rows in one]} rows for 1 combination "
                f"and {len(folds)} fold(s)"
            )
        for k, rows in enumerate(one):
            per_fold[k].append(rows[0])
        m = one[-1][0].metrics
        log.info(
            "tune %d/%d %s: through %s return %s, PF %s, max DD %s, trades %d (%.2fs)",
            i,
            total,
            _params(combo),
            folds[-1].tune_end.isoformat(),
            _pct(m.total_return),
            _num(m.profit_factor),
            _pct(m.max_drawdown),
            m.trades,
            time.perf_counter() - t0,
        )
    elapsed = time.perf_counter() - t_all
    log.info(
        "tune: %d runs on %s..%s sliced into %d fold(s) in %.1fs (%.2fs/run)",
        total,
        folds[0].tune_start.isoformat(),
        folds[-1].tune_end.isoformat(),
        len(folds),
        elapsed,
        elapsed / total if total else 0.0,
    )
    return tuple(tuple(rows) for rows in per_fold)


def run_walk_forward(
    market: Market,
    strategy: Any,
    prepared: Any,
    folds: Sequence[Fold],
    fold_rows: Sequence[Sequence[GridRow]],
    variant: str | None,
) -> WalkForward:
    """One walk-forward curve (``variant`` None: the combined one), its per-fold selections
    and its result, logged."""
    t0 = time.perf_counter()
    wf = walkforward.walk_forward(market, strategy, prepared, folds, fold_rows, variant)
    m = run_metrics(wf.run)
    log.info(
        "%s %s..%s: return %s, PF %s, max DD %s, trades %d (%.2fs)",
        wf.name,
        wf.run.start.isoformat(),
        wf.run.end.isoformat(),
        _pct(m.total_return),
        _num(m.profit_factor),
        _pct(m.max_drawdown),
        m.trades,
        time.perf_counter() - t0,
    )
    for f, s in zip(wf.folds, wf.selections):
        log.info(
            "%s fold %d (tune %s..%s, trade %s..%s): %s -- %s%s",
            wf.name,
            f.year,
            f.tune_start.isoformat(),
            f.tune_end.isoformat(),
            f.trade_start.isoformat(),
            f.trade_end.isoformat(),
            _params(s.params),
            s.reason,
            "" if s.qualified else " (fallback)",
        )
    return wf


def _log_frozen(frozen: Any, last_fold: Any, passed: bool) -> None:
    """Whether STRATEGY_A2_PARAMS matches what the run says it should be (Decision D14)."""
    if frozen is None:
        if passed:
            log.warning(
                "STRATEGY_A2_PARAMS is None but the gate passed; freeze the last fold's selection "
                "(%s) in strategies/a2.py and re-run so the report records it",
                _params(last_fold),
            )
        else:
            log.info("STRATEGY_A2_PARAMS is None, as it stays after a failed gate")
        return
    if not passed:
        log.warning(
            "STRATEGY_A2_PARAMS is set (%s) but the gate failed; it must stay None",
            _params(frozen),
        )
    elif frozen == last_fold:
        log.info("STRATEGY_A2_PARAMS equals the last fold's selection (%s)", _params(frozen))
    else:
        log.warning(
            "STRATEGY_A2_PARAMS (%s) differs from the last fold's selection (%s); freeze the "
            "selection in strategies/a2.py and re-run so the report records it",
            _params(frozen),
            _params(last_fold),
        )


def _params(p: Any) -> str:
    return " ".join(f"{k}={v}" for k, v in p.as_dict().items())


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:+.2%}"


def _num(x: float | None) -> str:
    if x is None:
        return "n/a"
    if math.isinf(x):
        return "inf"
    return f"{x:.2f}"
