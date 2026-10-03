"""`backtest`: tune Strategy A on the in-sample window, validate it once out of sample,
compare with SPY, and write the report files. Read-only on the database.

Flow:
  1. load the market (bars via the local cache in --cache-dir, universe, fx_rates) on one
     connection, closed before any computation; read the SPY dividends file
  2. prepare Strategy A once (param-independent features)
  3. the 81-run grid on the in-sample window; wall time logged per run and in total
  4. select on in-sample metrics only
  5. the selection once on in-sample, once on out-of-sample, once on the full window
  6. SPY price-only and total-return curves per window, survivorship, the gate (OOS only)
  7. write <stem>.md, <stem>-equity.csv, <stem>-equity.svg to --out; log the verdict and
     whether STRATEGY_A_PARAMS equals the selection

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
from seer_engine.backtest.benchmark import Dividend, spy_curves
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import curve_metrics, run_metrics
from seer_engine.backtest.report import BacktestReport, WindowResult
from seer_engine.backtest.runner import run_backtest, survivorship
from seer_engine.backtest.tuning import IS_START, OOS_START, GridRow, gate, grid, select
from seer_engine.prices import Bar
from seer_engine.strategies import a as strategy_a
from seer_engine.universe import BENCHMARK

log = logging.getLogger(__name__)

HELP = "Backtest Strategy A: in-sample grid, out-of-sample check vs SPY, write the report (read-only)"

DEFAULT_OUT = config.REPO_ROOT / "docs" / "backtests"
WINDOW_NAMES = ("In-sample", "Out-of-sample", "Full window")  # rendered by backtest.report


class BacktestError(RuntimeError):
    """The data or the arguments cannot back a run (exit 2)."""


@dataclass(frozen=True)
class Windows:
    is_start: date
    is_end: date
    oos_start: date
    end: date


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from e


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
        help=f"first in-sample session (default: {IS_START.isoformat()})",
    )
    p.add_argument(
        "--oos-start",
        type=_iso_date,
        default=OOS_START,
        metavar="YYYY-MM-DD",
        help=f"first out-of-sample session; in-sample ends the session before (default: {OOS_START.isoformat()})",
    )
    p.add_argument(
        "--end",
        type=_iso_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="last session of the out-of-sample and full windows (default: the last SPY bar)",
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
        log.info("dry-run: backtest never writes to the database; report files are written as usual")
    try:
        with contextlib.closing(db.connect()) as conn:
            market, bars_rows = backtest_io.load_market(
                conn, cache_dir=args.cache_dir, refresh=args.refresh_cache
            )
        dividends = backtest_io.read_dividends(args.dividends)
        windows = resolve_windows(market, args.is_start, args.oos_start, args.end)
    except FileNotFoundError as e:
        log.error("dividends file not found: %s", e.filename)
        return 2
    except (backtest_io.LoadError, BacktestError) as e:
        log.error("%s", e)
        return 2

    report = execute(market, bars_rows, dividends, windows)
    paths = backtest_io.write_report(args.out, report)
    for path in paths:
        log.info("wrote %s", path)

    verdict = report.verdict
    log.info("gate %s: %s", "PASSED" if verdict.passed else "FAILED", verdict.sentence)
    frozen = strategy_a.STRATEGY_A_PARAMS
    if frozen == report.selection.params:
        log.info("STRATEGY_A_PARAMS equals the selection (%s)", _params(frozen))
    else:
        log.warning(
            "STRATEGY_A_PARAMS (%s) differs from the selection (%s); freeze the selection in "
            "strategies/a.py and re-run so the report records it",
            _params(frozen),
            _params(report.selection.params),
        )
    return 0


def resolve_windows(market: Market, is_start: date, oos_start: date, end: date | None) -> Windows:
    """Validate the window arguments against the loaded data; raise BacktestError if they
    cannot back a run. ``end`` None means the last SPY bar."""
    spy_last = market.last_bar_date(BENCHMARK)
    if spy_last is None:
        raise BacktestError(f"no {BENCHMARK} bars loaded; the benchmark curve needs them")
    end = spy_last if end is None else end
    for flag, d in (("--is-start", is_start), ("--oos-start", oos_start), ("--end", end)):
        if not dates.is_session(d):
            raise BacktestError(f"{flag} {d.isoformat()} is not an NYSE session")
    if not is_start < oos_start <= end:
        raise BacktestError(
            f"need is_start < oos_start <= end, got {is_start.isoformat()}, "
            f"{oos_start.isoformat()}, {end.isoformat()}"
        )
    if end > spy_last:
        raise BacktestError(
            f"--end {end.isoformat()} is after the last {BENCHMARK} bar {spy_last.isoformat()}"
        )
    try:
        market.usd_idr_on(is_start)
    except ValueError as e:
        raise BacktestError(f"no fx_rates row on or before {is_start.isoformat()}") from e
    return Windows(is_start=is_start, is_end=dates.prev_session(oos_start), oos_start=oos_start, end=end)


def execute(
    market: Market,
    bars_rows: int,
    dividends: Sequence[Dividend],
    w: Windows,
) -> BacktestReport:
    """Everything between loading and writing. Pure except for logging and wall-time reads."""
    strategy = strategy_a.STRATEGY_A
    t0 = time.perf_counter()
    prepared = strategy.prepare(market.history)
    log.info(
        "prepared Strategy A features for %d symbols in %.1fs",
        len(market.history),
        time.perf_counter() - t0,
    )

    rows = run_grid(market, prepared, w.is_start, w.is_end)
    selection = select(rows)
    log.info(
        "selection: %s -- %s%s",
        _params(selection.params),
        selection.reason,
        "" if selection.qualified else " (no grid row qualified)",
    )

    spy = market.spy()
    in_sample = run_window(
        WINDOW_NAMES[0], market, spy, selection.params, prepared, w.is_start, w.is_end, dividends
    )
    out_of_sample = run_window(
        WINDOW_NAMES[1], market, spy, selection.params, prepared, w.oos_start, w.end, dividends
    )
    full = run_window(
        WINDOW_NAMES[2], market, spy, selection.params, prepared, w.is_start, w.end, dividends
    )

    gaps = survivorship(market, w.is_start, w.end)
    never_fetched = never_fetched_members(market, w.is_start, w.end)
    log.info(
        "survivorship: %d (member, session) pairs without a bar over %d year(s); "
        "%d member(s) in the window never had bars",
        sum(g.missing for g in gaps),
        len(gaps),
        never_fetched,
    )

    verdict = gate(run_metrics(out_of_sample.run), curve_metrics(out_of_sample.spy_tr))
    return BacktestReport(
        data_end=w.end,
        bars_rows=bars_rows,
        symbols_with_bars=len(market.history),
        grid_rows=rows,
        selection=selection,
        frozen_params=strategy_a.STRATEGY_A_PARAMS,
        in_sample=in_sample,
        out_of_sample=out_of_sample,
        full=full,
        survivorship=gaps,
        never_fetched_members=never_fetched,
        verdict=verdict,
    )


def run_grid(market: Market, prepared: Any, start: date, end: date) -> tuple[GridRow, ...]:
    """Every grid point on [start, end] (in-sample only), in grid order, each timed."""
    points = grid()
    total = len(points)
    rows: list[GridRow] = []
    t_all = time.perf_counter()
    for i, params in enumerate(points, 1):
        t0 = time.perf_counter()
        result = run_backtest(market, strategy_a.STRATEGY_A, params, start, end, prepared=prepared)
        m = run_metrics(result)
        rows.append(GridRow(params=params, metrics=m))
        log.info(
            "grid %d/%d %s: IS return %s, PF %s, max DD %s, trades %d (%.2fs)",
            i,
            total,
            _params(params),
            _pct(m.total_return),
            _num(m.profit_factor),
            _pct(m.max_drawdown),
            m.trades,
            time.perf_counter() - t0,
        )
    elapsed = time.perf_counter() - t_all
    log.info(
        "grid: %d runs on %s..%s in %.1fs (%.2fs/run)",
        total,
        start.isoformat(),
        end.isoformat(),
        elapsed,
        elapsed / total,
    )
    return tuple(rows)


def run_window(
    name: str,
    market: Market,
    spy: dict[date, Bar],
    params: Any,
    prepared: Any,
    start: date,
    end: date,
    dividends: Sequence[Dividend],
) -> WindowResult:
    """One run of ``params`` on [start, end] plus both SPY curves from the same starting cash."""
    t0 = time.perf_counter()
    result = run_backtest(market, strategy_a.STRATEGY_A, params, start, end, prepared=prepared)
    spy_price, spy_tr = spy_curves(spy, start, end, result.initial_cash, dividends)
    m = run_metrics(result)
    tr = curve_metrics(spy_tr)
    log.info(
        "%s %s..%s: return %s vs SPY total return %s, PF %s, max DD %s, trades %d (%.2fs)",
        name,
        start.isoformat(),
        end.isoformat(),
        _pct(m.total_return),
        _pct(tr.total_return),
        _num(m.profit_factor),
        _pct(m.max_drawdown),
        m.trades,
        time.perf_counter() - t0,
    )
    return WindowResult(name=name, run=result, spy_price=spy_price, spy_tr=spy_tr)


def never_fetched_members(market: Market, start: date, end: date) -> int:
    """Symbols that are index members at some point of [start, end] but have no bars at all."""
    return len(
        {
            symbol
            for symbol, iv_start, iv_end in market.membership.intervals
            if symbol not in market.history
            and iv_start <= end
            and (iv_end is None or iv_end > start)
        }
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
