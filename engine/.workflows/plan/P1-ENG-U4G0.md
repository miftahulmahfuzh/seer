> Adopted from `STRATEGY_A_REWORK_PLAN.md` phase 5. Source: `.workflows/plan/strategy-a-rework/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: `backtest_wf` command + `write_wf_report`

**Plan set:** `STRATEGY_A_REWORK_PLAN.md`
**Analysis:** `20261003-160830-R4W9_code_analyzer.md`
**Satisfies:** R6 (the runnable, read-only command that produces the five-file walk-forward report), R4 (byte-identical files on re-run; the sequential tuning pass returns rows in `combinations()` order)
**Depends on:** Phase 4 (and through it phases 1, 2, 3)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/commands` (+ one additive function in `engine/src/seer_engine/backtest/io.py`)

---

## Goal

After this phase `python -m seer_engine backtest_wf` loads the market read-only (via the bars
cache), validates its arguments against the data (exit 2 on any precondition), runs the whole
walk-forward (prepare A2 once, a sequential 324-combination tuning pass with per-combination
timing, the combined and four per-variant walk-forward curves, both SPY curves, survivorship, the
P3b gate), and writes `<end>-strategy-a2-walkforward{.md,-equity.csv,-equity.svg,-variants.svg,-grid.csv}`.
A synthetic-PG end-to-end test proves the run is read-only, uses the cache on re-run, and writes
byte-identical files. Phase 6 runs this command against Neon.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.backtest.io.write_wf_report(out_dir: Path, report: wf_report.WalkForwardReport) -> list[Path]` (`backtest/io.py`, appended after `write_report`)
- module `seer_engine.commands.backtest_wf` (`commands/backtest_wf.py`), discovered by `cli.discover()` as command `backtest_wf`:
  - `HELP: str`, `DEFAULT_OUT: Path`
  - `class BacktestWfError(RuntimeError)`
  - `@dataclass(frozen=True) class WfWindows(is_start: date, first_year: int, end: date)`
  - `def add_arguments(p: argparse.ArgumentParser) -> None`
  - `def run(args: argparse.Namespace) -> int`
  - `def resolve(market: Market, is_start: date, first_year: int, end: date | None) -> WfWindows`
  - `def execute(market: Market, bars_rows: int, dividends: Sequence[Dividend], is_start: date, first_year: int, end: date) -> WalkForwardReport`
  - `def tune_all(market, strategy, prepared, combos, folds) -> tuple[tuple[GridRow, ...], ...]` (per-combination loop over `walkforward.tune`; `==` one `walkforward.tune(..., combos, folds)` call)
  - `def run_walk_forward(market, strategy, prepared, folds, fold_rows, variant: str | None) -> WalkForward`
- test module `engine/tests/test_backtest_wf_command.py`
**Signature changes:** none.
**Requires (from earlier phases):**
- Phase 1: `seer_engine.strategies.a2` with `STRATEGY_A2` (`.prepare(history)`), `STRATEGY_A2_PARAMS: A2Params | None` (read as a **module attribute at call time**, so phase 6's freeze is picked up), `VARIANTS`, `A2Params.as_dict()` (variant first), frozen-dataclass `==`.
- Phase 2: nothing directly (used through phase 3).
- Phase 3: `seer_engine.backtest.walkforward` with `FIRST_TRADE_YEAR`, `COMBINED`, `Fold` (fields `year, tune_start, tune_end, trade_start, trade_end`), `folds(is_start, first_year, end)` raising `ValueError` on non-session dates / no fold / `folds[0].tune_end < is_start`, `combinations()` (324, `A2Params`), `tune(market, strategy, prepared, combos, folds)` returning `result[k]` = fold k's `GridRow`s in `combos` order, `walk_forward(market, strategy, prepared, folds, fold_rows, variant=None)` returning a `WalkForward(name, folds, selections, run)`, `gate_p3b(wf: Metrics, spy_tr: Metrics, start, end) -> Verdict`.
- Phase 4: `seer_engine.backtest.wf_report` with `WalkForwardReport` (keyword constructor with exactly the fields in the index contract: `data_end, bars_rows, symbols_with_bars, never_fetched_members, survivorship, is_start, folds, fold_rows, combined, variants, spy_price, spy_tr, verdict, frozen_params`), `report_stem`, `render_markdown`, `equity_csv`, `equity_svg`, `variants_svg`, `grid_csv`, `parse_machine_line`, `GATE_KEY`, `FROZEN_KEY`, `LAST_FOLD_KEY`. The machine-line values follow Decision D14: `p3b-gate: passed|failed`, `frozen-params: null|{json}`, `last-fold-params: {json}` (a JSON object).
- v1 (unchanged, imported read-only): `commands.backtest.never_fetched_members`, `backtest.io.load_market` / `read_dividends` / `LoadError` / `CACHE_DIR` / `DIVIDENDS_CSV`, `benchmark.spy_curves`, `metrics.run_metrics` / `curve_metrics`, `runner.survivorship`, `tuning.IS_START`, `universe.BENCHMARK`.
**Leaves alone (owned by others):** `commands/backtest.py` (v1; imported, never edited), `backtest/report.py`, `cli.py`, `backtest/walkforward.py` (phase 3), `backtest/wf_report.py` (phase 4), `strategies/*` (phase 1 / phase 6), `backtest/runner.py`, `metrics.py`, `tuning.py` (phase 2), `docs/*`, `engine/package_readme.md` (phase 6).

### Decision taken here: per-combination tuning timing

`walkforward.tune`'s contract is **not** changed (no progress callback). The command owns
`tune_all`, which loops over `combos` itself and calls
`walkforward.tune(market, strategy, prepared, (combo,), folds)` once per combination, appending
`one[k][0]` to fold k's list. Because `tune` does exactly one independent `run_backtest` per combo
and returns per-fold rows in `combos` order, the stitched result is `==` a single
`tune(..., combos, folds)` call; a no-DB test asserts that on a 6-combination subset spanning all
four variants. The cost is identical (one `run_backtest` per combo either way); the loop is
sequential, so the order is `combinations()` order (Decision D3, invariant 5).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/io.py` | modify | import `wf_report` (after line 38); append `write_wf_report` after `write_report` (after line 292) |
| `engine/src/seer_engine/commands/backtest_wf.py` | create | the command: args, `resolve` (exit-2 preconditions), `execute`, `tune_all`, `run_walk_forward` |
| `engine/tests/test_backtest_wf_command.py` | create | discovery/defaults, usage errors, `write_wf_report` unit tests, `tune_all == tune`, exit-2 cases, end-to-end on synthetic PG |

## Implementation Steps

### Step 1: Import `wf_report` in `io.py`
**File:** `engine/src/seer_engine/backtest/io.py:32-38`
**Change:** add a module import directly after the existing `from seer_engine.backtest.report import (...)` block (ends line 38). A module import (not names) because `wf_report` exports `render_markdown`, `equity_csv`, `equity_svg` and `report_stem`, which would shadow v1's names already imported from `report`.
**Code:** (lines 29-40 after the edit)
```python
from seer_engine import config
from seer_engine.backtest import wf_report
from seer_engine.backtest.benchmark import Dividend, parse_dividends
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.report import (
    BacktestReport,
    equity_csv,
    equity_svg,
    render_markdown,
    report_stem,
)
from seer_engine.prices import to_decimal
from seer_engine.strategies.base import History
```
**Impact:** `io.py` (and so v1's `commands/backtest.py`, which imports it) now imports `wf_report`, which imports `walkforward` and `a2`. All are pure; no cycle (none of them imports `io`). v1 behaviour and output are unchanged.

### Step 2: `write_wf_report`
**File:** `engine/src/seer_engine/backtest/io.py:293` (append after `write_report`, end of file)
**Change:** new function, mirroring `write_report`: render all five texts first, then create the directory and write with LF endings. Order of the returned paths is the contract order.
**Code:**
```python


def write_wf_report(out_dir: Path, report: wf_report.WalkForwardReport) -> list[Path]:
    """Write the walk-forward report set into ``out_dir`` (created if needed) with LF line
    endings and return the paths in this order: <stem>.md, <stem>-equity.csv,
    <stem>-equity.svg, <stem>-variants.svg, <stem>-grid.csv. All five are rendered before any
    is written, so a render error leaves no partial set."""
    out_dir = Path(out_dir)
    stem = wf_report.report_stem(report.data_end)
    files = (
        (f"{stem}.md", wf_report.render_markdown(report)),
        (f"{stem}-equity.csv", wf_report.equity_csv(report)),
        (f"{stem}-equity.svg", wf_report.equity_svg(report)),
        (f"{stem}-variants.svg", wf_report.variants_svg(report)),
        (f"{stem}-grid.csv", wf_report.grid_csv(report)),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, text in files:
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths
```
Also update the module docstring's first line (line 1-2) to stay accurate:
```python
"""Impure edge of the backtest: read the database once, read the vendored SPY dividends,
write the report files (v1's ``write_report`` and the walk-forward ``write_wf_report``).
```
(lines 3-12 of the docstring unchanged.)
**Impact:** additive. The functions are looked up as `wf_report.<name>` at call time, which lets the unit tests monkeypatch them.

### Step 3: The command module
**File:** `engine/src/seer_engine/commands/backtest_wf.py` (new)
**Change:** whole module. Mirrors `commands/backtest.py` (same load/close/read-dividends/resolve/execute/write flow, same exit codes, same log style). `never_fetched_members` is imported from v1's command module (unchanged there) so both reports count identically.
**Code:**
```python
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
```
**Impact:** new command `backtest_wf` appears in `python -m seer_engine --help`. No existing behaviour changes. `execute` calls `walkforward.folds` again after `resolve` validated it (pure and cheap) so its signature matches the index contract.

Notes for the implementer:
- `resolve` checks `--is-start`/`--end` are sessions before calling `folds` so the two most common mistakes get v1's exact message; `folds`' own `ValueError` (no fold whose first session is ≤ end, or `folds[0].tune_end < is_start`, i.e. an empty tuning window) is mapped to `BacktestWfError` (exit 2).
- The fx check is on `is_start` only: it is the earliest session any run starts on (tuning starts there; the walk-forward starts later at `folds[0].trade_start`, which therefore also has a rate).
- `spy_curves` runs to `folds[-1].trade_end` and `gate_p3b` takes `(combined.run.start, combined.run.end)`, which is literally what `wf_report._validate` recomputes (phase 4; plan index contract). By phase 3's fold rule `folds[-1].trade_end == end` (the last fold is `end.year`, `trade_end = min(last session of the year, end)`), so the values are the same as using `end`; spelling them the contract's way means `_validate` can never disagree. The e2e test asserts the curves and the run end on `END`.

### Step 4: Tests
**File:** `engine/tests/test_backtest_wf_command.py` (new)
**Change:** whole module. Synthetic data: 625 NYSE sessions 2022-01-03 .. 2024-06-28; `IS_S = SESSIONS[200]` = 2022-10-19 (its data_date is the 200th bar, so A2's features and SPY's SMA(200) exist from the first tuning session); `--first-year 2023` gives folds 2023 (tune 2022-10-19..2022-12-30) and 2024 (tune ..2023-12-29, trade 2024-01-02..2024-06-28). Four traded symbols + SPY (never a member) + `OLD` (bars end mid-2024 while a member) + `GONE` (a member with no bars). The sawtooth from v1's test makes the `rsi_max=15` third of the grid trade (≈100 closed orders over the tuning window, measured on v1's runner), so the selection, schedules and files are non-trivial.

Speed (measured with v1's runner on this market: one 301-session run ≈ 9-10 ms, 81 runs ≈ 0.85 s): one `backtest_wf` run is ≈ 324 × ~12 ms ≈ 4 s of tuning plus five ~375-session walk-forward runs; the e2e test runs it twice, ≈ 10 s total. The exit-2 tests stop before `execute`. Keep the symbol count at this size.

**Code:**
```python
"""`backtest_wf` command: discovery, write_wf_report, the tuning loop, preconditions, and an
end-to-end run on a synthetic schema."""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, cli, config, dates, db, fx
from seer_engine.backtest import io as bio
from seer_engine.backtest import walkforward, wf_report
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.tuning import IS_START
from seer_engine.commands import backtest_wf as cmd
from seer_engine.strategies import a2 as strategy_a2
from seer_engine.strategies.base import history_from_bars

SESSIONS = dates.sessions(date(2022, 1, 3), date(2024, 6, 28))
IS_S = SESSIONS[200]  # 2022-10-19; data_date SESSIONS[199] is the 200th bar
FIRST_YEAR = 2023  # folds 2023 and 2024
END = SESSIONS[-1]  # 2024-06-28
OLD_LAST = SESSIONS[560]  # OLD's bars end in 2024 (delisted while a member)
DIVIDEND_DAY = SESSIONS[600]  # inside the traded window
FX_LATE = SESSIONS[400]
TRADED = ("AAA", "BBB", "CCC", "DDD")
LONG_AGO = date(2015, 1, 2)


def ohlcv(k: int, n: int) -> list[tuple[float, float, float, float, int]]:
    """Rising sawtooth: +0.6 %/session, two -4 % sessions then +6 % every 12; phase shifted by k."""
    price = 40.0 + 7.0 * k
    out = []
    for i in range(n):
        phase = (i + 3 * k) % 12
        if phase in (9, 10):
            price *= 0.96
        elif phase == 11:
            price *= 1.06
        else:
            price *= 1.006
        c = round(price, 4)
        out.append((round(c * 0.999, 4), round(c * 1.02, 4), round(c * 0.97, 4), c, 2_000_000 + 1_000 * k))
    return out


def synthetic_bars(*, with_spy: bool = True) -> list:
    rows = []
    for k, symbol in enumerate(TRADED):
        rows += [bars.make_bar(symbol, d, *v) for d, v in zip(SESSIONS, ohlcv(k, len(SESSIONS)))]
    if with_spy:
        rows += [bars.make_bar("SPY", d, *v) for d, v in zip(SESSIONS, ohlcv(6, len(SESSIONS)))]
    old_sessions = [d for d in SESSIONS if d <= OLD_LAST]
    rows += [bars.make_bar("OLD", d, *v) for d, v in zip(old_sessions, ohlcv(7, len(old_sessions)))]
    return rows


EXPECTED_ROWS = (len(TRADED) + 1) * len(SESSIONS) + len([d for d in SESSIONS if d <= OLD_LAST])


def seed(conn, *, with_bars=True, with_spy=True, fx_rows=((SESSIONS[0], "16000"), (FX_LATE, "16250.5"))):
    with db.transaction(conn, False):
        if with_bars:
            bars.upsert_bars(conn, synthetic_bars(with_spy=with_spy))
        with conn.cursor() as cur:
            members = [(s, "SP500") for s in (*TRADED, "OLD", "GONE")] + [("AAA", "NDX")]
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, NULL, %s)",
                [(s, i, LONG_AGO, s) for s, i in members],
            )
        fx.upsert_fx(conn, list(fx_rows))


def in_memory_market() -> Market:
    """The same data as seed(), without a database (SPY not a member, GONE has no bars)."""
    by_symbol: dict[str, list] = {}
    for b in synthetic_bars():
        by_symbol.setdefault(b.symbol, []).append(b)
    history = {s: history_from_bars(s, rows) for s, rows in sorted(by_symbol.items())}
    intervals = tuple(sorted((s, LONG_AGO, None) for s in (*TRADED, "OLD", "GONE")))
    return Market(
        history=history,
        membership=Membership(intervals=intervals),
        fx=((SESSIONS[0], Decimal("16000")), (FX_LATE, Decimal("16250.5"))),
    )


def write_dividends(tmp_path):
    path = tmp_path / "spy_dividends.csv"
    path.write_text(f"ex_date,amount_usd\n{DIVIDEND_DAY.isoformat()},0.75\n", encoding="utf-8")
    return path


def argv(tmp_path, out_name="out", *extra):
    return [
        "backtest_wf",
        "--out", str(tmp_path / out_name),
        "--cache-dir", str(tmp_path / "cache"),
        "--is-start", IS_S.isoformat(),
        "--first-year", str(FIRST_YEAR),
        "--end", END.isoformat(),
        "--dividends", str(tmp_path / "spy_dividends.csv"),
        *extra,
    ]


def file_names(stem: str) -> list[str]:
    return [
        f"{stem}.md",
        f"{stem}-equity.csv",
        f"{stem}-equity.svg",
        f"{stem}-variants.svg",
        f"{stem}-grid.csv",
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


# ---- no database -----------------------------------------------------------------------------


def test_discovered_with_defaults():
    assert "backtest_wf" in cli.discover()
    args = cli.build_parser().parse_args(["backtest_wf"])
    assert args._run is cmd.run
    assert args.out == cmd.DEFAULT_OUT == config.REPO_ROOT / "docs" / "backtests"
    assert args.cache_dir == bio.CACHE_DIR == config.REPO_ROOT / "engine" / ".cache"
    assert args.dividends == bio.DIVIDENDS_CSV == config.REPO_ROOT / "engine" / "data" / "spy_dividends.csv"
    assert (args.is_start, args.first_year, args.end) == (IS_START, walkforward.FIRST_TRADE_YEAR, None)
    assert args.refresh_cache is False
    assert cmd.HELP


@pytest.mark.parametrize(
    "extra",
    [
        ["--end", "2026-13-01"],
        ["--is-start", "yesterday"],
        ["--first-year", "twenty"],
    ],
)
def test_bad_argument_is_a_usage_error(extra):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["backtest_wf", *extra])
    assert exc.value.code == 2


def test_write_wf_report_writes_five_files_in_order_with_lf(tmp_path, monkeypatch):
    texts = {
        "render_markdown": "# md\nline\n",
        "equity_csv": "date,walk_forward\n",
        "equity_svg": "<svg>equity</svg>\n",
        "variants_svg": "<svg>variants</svg>\n",
        "grid_csv": "fold,combo\n",
    }
    for name, text in texts.items():
        monkeypatch.setattr(wf_report, name, lambda report, _t=text: _t)
    report = SimpleNamespace(data_end=date(2024, 6, 28))
    paths = bio.write_wf_report(tmp_path / "nested" / "out", report)
    stem = wf_report.report_stem(date(2024, 6, 28))
    assert stem == "2024-06-28-strategy-a2-walkforward"
    assert [p.name for p in paths] == file_names(stem)
    assert [p.read_bytes() for p in paths] == [t.encode("utf-8") for t in texts.values()]


def test_write_wf_report_renders_everything_before_writing(tmp_path, monkeypatch):
    for name in ("render_markdown", "equity_csv", "equity_svg", "variants_svg"):
        monkeypatch.setattr(wf_report, name, lambda report: "ok\n")

    def boom(report):
        raise RuntimeError("grid render failed")

    monkeypatch.setattr(wf_report, "grid_csv", boom)
    with pytest.raises(RuntimeError, match="grid render failed"):
        bio.write_wf_report(tmp_path / "out", SimpleNamespace(data_end=date(2024, 6, 28)))
    assert not (tmp_path / "out").exists()


def test_tune_all_equals_one_tune_call_and_logs_each_run(caplog):
    market = in_memory_market()
    strategy = strategy_a2.STRATEGY_A2
    prepared = strategy.prepare(market.history)
    folds = walkforward.folds(IS_S, FIRST_YEAR, END)
    combos = walkforward.combinations()[::54]  # 6 combinations, every variant represented
    assert {c.variant for c in combos} == set(strategy_a2.VARIANTS)
    caplog.set_level(logging.INFO)

    stitched = cmd.tune_all(market, strategy, prepared, combos, folds)

    assert stitched == walkforward.tune(market, strategy, prepared, combos, folds)
    assert len(stitched) == len(folds) == 2
    assert all([r.params for r in rows] == list(combos) for rows in stitched)
    messages = [r.getMessage() for r in caplog.records]
    assert [m.split(" ", 2)[1] for m in messages if m.startswith("tune ")] == [
        f"{i}/{len(combos)}" for i in range(1, len(combos) + 1)
    ]
    assert sum(1 for m in messages if m.startswith(f"tune: {len(combos)} runs on ")) == 1


# ---- preconditions (exit 2, nothing written) -----------------------------------------------


def test_empty_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_bars=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert not (tmp_path / "out").exists()


def test_no_spy_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_spy=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "extra",
    [
        ["--end", dates.next_session(END).isoformat()],  # after the last SPY bar
        ["--end", date(2023, 6, 10).isoformat()],  # a Saturday
        ["--is-start", date(2022, 10, 22).isoformat()],  # a Saturday
        ["--first-year", "2022"],  # fold 2022 would tune on nothing before is_start
        ["--first-year", "2025"],  # no fold: 2025's first session is after --end
    ],
)
def test_bad_windows_exit_2(pg, point_cli_at, tmp_path, extra):
    seed(pg)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path, "out", *extra)) == 2
    assert not (tmp_path / "out").exists()


def test_no_fx_before_is_start_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, fx_rows=((FX_LATE, "16250.5"),))
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert not (tmp_path / "out").exists()


def test_missing_dividends_file_exits_2(pg, point_cli_at, tmp_path):
    seed(pg)
    assert cli.main(argv(tmp_path)) == 2  # no spy_dividends.csv written
    assert not (tmp_path / "out").exists()


# ---- end to end ------------------------------------------------------------------------------


def test_end_to_end_report_read_only_cache_hit_and_byte_identical_rerun(
    pg, point_cli_at, tmp_path, monkeypatch, caplog
):
    seed(pg)
    write_dividends(tmp_path)
    caplog.set_level(logging.INFO)
    captured = []
    real_write = bio.write_wf_report

    def capturing_write(out_dir, report):
        captured.append(report)
        return real_write(out_dir, report)

    monkeypatch.setattr(bio, "write_wf_report", capturing_write)
    before = checksums(pg)

    assert cli.main(argv(tmp_path, "out1")) == 0

    assert checksums(pg) == before  # read-only
    stem = f"{END.isoformat()}-strategy-a2-walkforward"
    assert wf_report.report_stem(END) == stem
    names = file_names(stem)
    assert sorted(p.name for p in (tmp_path / "out1").iterdir()) == sorted(names)
    assert [p.name for p in (tmp_path / "cache").iterdir()] == [
        f"bars-{END.isoformat()}-{EXPECTED_ROWS}.pkl"
    ]

    [report] = captured
    combos = walkforward.combinations()
    folds = walkforward.folds(IS_S, FIRST_YEAR, END)
    assert report.data_end == END
    assert report.bars_rows == EXPECTED_ROWS
    assert report.symbols_with_bars == len(TRADED) + 2  # + SPY + OLD
    assert report.never_fetched_members == 1  # GONE
    assert report.is_start == IS_S
    assert report.folds == folds
    assert [f.year for f in report.folds] == [2023, 2024]
    assert len(report.fold_rows) == 2
    for rows in report.fold_rows:
        assert [r.params for r in rows] == list(combos)
    assert report.combined.name == walkforward.COMBINED
    assert [v.name for v in report.variants] == list(strategy_a2.VARIANTS)
    for wf in (report.combined, *report.variants):
        assert wf.folds == folds
        assert len(wf.selections) == len(folds)
        assert (wf.run.start, wf.run.end) == (folds[0].trade_start, END)
    for v, wf in zip(strategy_a2.VARIANTS, report.variants):
        assert all(s.params.variant == v for s in wf.selections)
    for curve in (report.spy_price, report.spy_tr):
        assert curve.snapshots[0].date == report.combined.run.snapshots[0].date
        assert curve.snapshots[-1].date == END
    assert report.spy_tr.dividends_usd > 0
    assert [g.year for g in report.survivorship] == [2022, 2023, 2024]
    assert report.frozen_params == strategy_a2.STRATEGY_A2_PARAMS

    md = (tmp_path / "out1" / f"{stem}.md").read_text(encoding="utf-8")
    assert report.verdict.sentence in md
    assert wf_report.parse_machine_line(md, wf_report.GATE_KEY) == (
        "passed" if report.verdict.passed else "failed"
    )
    frozen_line = json.loads(wf_report.parse_machine_line(md, wf_report.FROZEN_KEY))
    if report.frozen_params is None:
        assert frozen_line is None
    else:
        assert isinstance(frozen_line, dict)
    last_fold = json.loads(wf_report.parse_machine_line(md, wf_report.LAST_FOLD_KEY))
    assert isinstance(last_fold, dict)
    assert last_fold["variant"] == report.combined.selections[-1].params.variant

    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("prepared Strategy A2 features for ") for m in messages)
    assert sum(1 for m in messages if m.startswith("tune ") and f"/{len(combos)} " in m) == len(combos)
    assert sum(1 for m in messages if m.startswith(f"tune: {len(combos)} runs on ")) == 1
    for name in (walkforward.COMBINED, *strategy_a2.VARIANTS):
        assert sum(1 for m in messages if m.startswith(f"{name} fold ")) == len(folds)
    assert any(m.startswith("gate ") and report.verdict.sentence in m for m in messages)
    assert any("STRATEGY_A2_PARAMS" in m for m in messages)
    assert sum(1 for m in messages if m.startswith("wrote ")) == len(names)

    # Second run: the cache must be used (no COPY) and every file byte-identical.
    def no_copy(conn):
        raise AssertionError("the bars cache should have been used")

    monkeypatch.setattr(bio, "read_bars_frame", no_copy)
    caplog.clear()
    assert cli.main(argv(tmp_path, "out2")) == 0
    assert any(r.getMessage().startswith("bars cache hit") for r in caplog.records)
    for name in names:
        assert (tmp_path / "out2" / name).read_bytes() == (tmp_path / "out1" / name).read_bytes(), name
    assert captured[1].fold_rows == captured[0].fold_rows
    assert captured[1].combined.selections == captured[0].combined.selections
    assert [v.selections for v in captured[1].variants] == [v.selections for v in captured[0].variants]
    assert captured[1].verdict == captured[0].verdict
    assert checksums(pg) == before
```
**Impact:** +17 tests (see Verification). One e2e test runs the full 324-combination pass twice (~10 s).

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/strategy-a-rework && engine/.venv/bin/python -m seer_engine backtest_wf --help` (worktree venv; never main's)
**Tests:**
```
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_backtest_wf_command.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```
**Expected test count delta:** **+17** over the suite after phase 4:
- no DB (7): `test_discovered_with_defaults` 1, `test_bad_argument_is_a_usage_error` 3, `test_write_wf_report_writes_five_files_in_order_with_lf` 1, `test_write_wf_report_renders_everything_before_writing` 1, `test_tune_all_equals_one_tune_call_and_logs_each_run` 1
- PG (10): `test_empty_bars_exits_2` 1, `test_no_spy_bars_exits_2` 1, `test_bad_windows_exit_2` 5, `test_no_fx_before_is_start_exits_2` 1, `test_missing_dividends_file_exits_2` 1, end-to-end 1

Total 7 + 10 = 17, 0 skipped. Full suite after this phase: **757 passed** (740 after phase 4 + 17; plan index invariant 1).
**Manual check:** `python -m seer_engine --help` lists `backtest_wf`; `test_backtest_wf_command.py` wall time stays under ~30 s (`pytest --durations=5`). If the e2e test exceeds ~30 s, record the measurement in the phase log; do not shrink the grid (it is fixed) - shrink the synthetic market instead (fewer traded symbols).
**Exit criteria:** suite green with 0 skipped; `python -m seer_engine backtest_wf --help` works; the e2e test proves read-only access, the five file names, a cache hit on re-run, byte-identical files, and `stitched == tune(combos)`.

## Assumptions (on other phases)

- Phase 3's `walkforward.tune` accepts any `Sequence` of combos (a 1-tuple included) and returns exactly `len(folds)` tuples of `len(combos)` rows; its runs are independent per combo, so per-combo calls stitched in order `==` one call. `tune_all` raises `RuntimeError` if the shape is ever different.
- Phase 3's `folds(...)` validates as the index contract says (ValueError for non-session dates, no fold, empty first tuning window). For `--first-year 2022` with `is_start = 2022-10-19` it raises (fold 2022's `tune_end` 2021-12-31 < is_start); for `--first-year 2025` with `end = 2024-06-28` it raises (no fold).
- Phase 3's `walk_forward(...)` returns a `WalkForward` whose `run` ends at `folds[-1].trade_end` (= `end`) and whose `name` is `COMBINED` for `variant=None`, else the variant string. Per-variant selections all carry that variant (Decision D7 fallback included).
- Phase 4's `WalkForwardReport` takes exactly the 14 keyword fields listed in the index contract, and `parse_machine_line` returns raw values where `GATE_KEY` is `passed|failed`, `FROZEN_KEY` is JSON `null` or a JSON object, `LAST_FOLD_KEY` is a JSON object containing `"variant"` (Decision D14). If phase 4 validates the report (like v1's `_validate`), the values `execute` passes satisfy the contract by construction.
- Phase 1's `A2Params.as_dict()` exists (used for log strings), `STRATEGY_A2.prepare(history)` handles SPY in `history` and a symbol (`OLD`) whose bars end early.

## Handoffs

- **Phase 6:** run `python -m seer_engine backtest_wf` on Neon (with `SEER_ENV_FILE` pointing at main's `.env.local`), commit the five files, and record in `engine/package_readme.md` (`## Performance`) the logged prepare time, the per-run tune average and the total from the `tune: 324 runs ...` line. Document the command section and Usage there too (R8; not this phase's requirement).
- **Phase 6:** after freezing on a pass, the re-run logs `STRATEGY_A2_PARAMS equals the last fold's selection (...)`; on a fail it logs `STRATEGY_A2_PARAMS is None, as it stays after a failed gate`. Use those lines as evidence in the phase log.
- **Phase 6 / R8:** `io.py` now imports `wf_report`; v1's `backtest` command still renders through `report.py` only, so the v1 byte-identity check (Decision D9) is unaffected, but phase 6's check is what proves it.
- Any defect found here in `walkforward.py` or `wf_report.py` is fixed in the owning module with a test and recorded in the phase log (index phase 5 "Does not touch" clause); none is planned.

## Rollback

`git revert` this phase's commit: it deletes `commands/backtest_wf.py` and
`tests/test_backtest_wf_command.py` and removes `write_wf_report` plus the `wf_report` import from
`backtest/io.py`. Nothing else references them until phase 6, and no DB state or committed report
is produced by this phase.
