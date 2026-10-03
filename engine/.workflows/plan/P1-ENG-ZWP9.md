> Adopted from `TRADE_RULES_DEV_SEARCH_PLAN.md` phase 12. Source: `.workflows/plan/trade-rules-dev-search/phase-12.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 12: `backtest_dev` command, io writer, runtime on the real store

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R4 (the test that `research.DEV_END`, `MEMBERSHIP_START` and `FX_START` equal `backtest.dev`'s, assigned here by plan index D-I because this is the first phase that depends on both), R6 (the pipeline that produces the committed dev report set), R8 (determinism: `==` rows and byte-identical files on a re-run)
**Depends on:** Phase 4 (research store), Phase 10 (dev report renderers), Phase 11 (registry). Through them, phases 1, 2, 3, 5, 6, 7, 8 and 9 have also landed.
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/commands` (primary), `engine/src/seer_engine/backtest` (additive `io.py`)

---

## Goal

`python -m seer_engine backtest_dev` loads the local research store, runs the committed candidate
registry in registry order on the dev window (never past `DEV_END`), builds the `DevReport`, and
writes the dev report set plus the pre-registration file. The same inputs give byte-identical
files. A full run is refused while `backtest/registry.py` has uncommitted changes. `--only` runs a
subset as a smoke test, writes nothing, and logs an estimate of how long the full run takes. The
phase ends with a timed `--only` smoke on the real store and the D13 decision recorded: parallelize
or not.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.commands.backtest_dev` (`commands/backtest_dev.py`, new), discovered by `cli.discover()`. Its public surface:
  - `HELP: str`, `add_arguments(p)`, `run(args) -> int` (the command convention);
  - `DEFAULT_OUT = config.REPO_ROOT / "docs" / "backtests"`, `DEFAULT_PLANS = config.REPO_ROOT / "docs" / "plans"`;
  - `REGISTRY_PATH: Path` (the imported `backtest/registry.py` file, resolved), `TOP_YEARS = 5`, `STORE_COUNT_KEYS`, `UNSERVED_FILE = "unserved.csv"`;
  - `class BacktestDevError(RuntimeError)`;
  - `@dataclass(frozen=True) class Timing(candidate_id, estimate_class, seconds: float)`: the wall time from the previous candidate's end to this one's, so it includes the allocator's `prepare` when this candidate was the first to use it;
  - `load_registry() -> tuple[Candidate, ...]`. Tests monkeypatch it with a fake registry;
  - `registry_problem(path) -> str | None`, `registry_digest(path) -> str`;
  - `select(registry, only) -> tuple[Candidate, ...]`;
  - `read_unserved(store_dir) -> tuple[str, ...]` (the same list as phase 4's `ResearchData.unserved`), `store_counts(manifest) -> dict[str, int]`;
  - `estimate_class(c) -> tuple[str, str, str]`;
  - `month_end_curve(snapshots) -> tuple[tuple[date, float], ...]`;
  - `top_years(rows, finals, k=TOP_YEARS)`, `daily_moments(returns)`, `deflated_sharpes(rows, finals)`;
  - `run_candidates(market, dividends, spy_dividends, candidates) -> (rows, curves, timings)`: **through `dev.run_registry(..., on_result=...)`** (plan index D-D: one prepare per `allocator.id`, the one keying rule);
  - `execute(data, candidates, *, unserved, registry_digest, run_date) -> (DevReport, timings)`;
  - `estimate_full_run(registry, timings) -> float`.
- `seer_engine.backtest.io.dev_report_files(out_dir, plans_dir, report) -> tuple[tuple[Path, str], ...]` (`backtest/io.py`, additive). It renders every file of the set without writing.
- `seer_engine.backtest.io.write_dev_report(out_dir, plans_dir, report) -> list[Path]` (`backtest/io.py`, additive; the signature is exactly the index contract).
- `engine/tests/test_backtest_dev_command.py` (new, 28 tests).

**Signature changes:** none.

**Requires (from earlier phases):**
- Phase 4 (`seer_engine.research`):
  - `DEV_END`, `STORE_START`, `STORE_DIR`.
  - `load_store(store_dir: Path, *, data_dir=None) -> ResearchData` with `.market`, `.dividends`, `.spy_dividends`, `.fingerprint`, `.manifest` and `.unserved`. It raises `ValueError` for a missing store (no `manifest.json`), a sha mismatch or a row after `DEV_END`; the command also maps a `FileNotFoundError` (a data file deleted after the manifest was read) to exit 2.
  - `build_store(store_dir, *, downloader, fetch_fx, sleep, batch_size=40, data_dir=None)`:
    - `downloader` has the `yahoo.Downloader` shape `(yahoo_tickers: list[str], start: date, end_exclusive: date) -> pd.DataFrame | None`, returning the yfinance `group_by="ticker"` frame plus the `Dividends` and `Stock Splits` columns that `actions=True` adds;
    - `fetch_fx` has the `fx.fetch_range` shape `(start: date, end: date) -> list[tuple[date, Decimal]]`;
    - **every `RESEARCH_ETFS` symbol must be served**, or the build raises `ResearchStoreError` (phase 4 interface note 5), so the test fixture serves all 21.
  - The store holds `unserved.csv` with a header row whose first column is `symbol`.
  - The manifest has the keys `bar_rows`, `dividend_rows`, `fx_rows`, `symbols_requested` and `symbols_served`, each an int.
  - `MEMBERSHIP_START`, `FX_START`, `SECTOR_ETFS` and `RESEARCH_ETFS` (the D-I equality tests).
- Phase 9 (`seer_engine.backtest.dev`):
  - the constants `DEV_END`, `MEMBERSHIP_START` and `FX_START`;
  - `Candidate`, with keyword fields `id`, `family`, `rules`, `allocator`, `params`, `rationale`, `added` and `owner_inputs`;
  - `DevRow`, with `candidate`, `start`, `end`, `stats`, `spy_tr`, `mar`, `eligible` and `failed`;
  - `run_candidate(market, dividends, spy_dividends, c, *, prepared=None) -> (RunResult | BookResult, DevRow)` (Step 8's pool only);
  - `run_registry(market, dividends, spy_dividends, registry, *, on_result=None) -> tuple[DevRow, ...]`, where `on_result(index, result, row)` is called after each candidate in registry order (phase 9 interface note 1);
  - `finalists(rows)`;
  - `deflated_sharpe(sharpe_daily, n_trials, var_trials, t, skew, kurt) -> float | None`.

  `DevRow` must survive `dataclasses.replace` and, only if Step 8 runs, pickling.
- Phase 3: `RunStats.metrics`, `.sharpe` (annualized), `.daily_returns` and `.year_returns`. `BookResult.snapshots` and `RunResult.snapshots` both carry `.date` and `.equity_usd`.
- Phase 10 (`seer_engine.backtest.dev_report`):
  - `DevReport`, with the exact contract fields `run_date`, `store_fingerprint`, `store_counts`, `unserved`, `survivorship`, `registry_digest`, `rows`, `finalists`, `spy_window`, `spy_price`, `spy_tr`, `top_years`, `curves` and `dsr`;
  - `report_stem`, `preregistration_name`, `render_markdown`, `rows_csv`, `curves_csv`, `frontier_svg` and `render_preregistration`.

  The renderers must accept a report whose `rows` is a registry-order **subset** of `REGISTRY` (the `--only` path renders in memory).
- Phase 11: `backtest.registry.REGISTRY` exists, is committed, and every id is unique.
- Phases 2 and 5–8: every allocator's `prepare(history)` (and `Strategy.prepare`) depends only on `history`, never on params (plan index D-D). So one prepared value per allocator id is valid for every candidate that uses that allocator; `dev.run_registry` keys it so, and this command uses `run_registry`.
- Phase 11: `backtest.registry.SECTOR_ETFS` and `REGISTRY` (the D-I symbol test).
- Phases 5 and 6: `strategies.f_index.TIMING`, `TimingParams`, `strategies.f_rotation.ROTATION` and `RotationParams`. The test's fake registry uses them.
- Phase 1: `sim.rules.DAILY_SWITCH` and `MONTHLY_HOLD`.

**Leaves alone (owned by others):**
- `seer_engine/research.py` and `commands/research_store.py` (Phase 4);
- `backtest/dev.py` (Phase 9), `backtest/dev_report.py` (Phase 10) and `backtest/registry.py` (Phase 11);
- every family module (Phases 5–8);
- every file in the plan index's frozen set;
- every existing test file;
- `docs/` (Phase 13 writes the real report and pre-registration);
- `engine/package_readme.md` and `docs/ROADMAP.md` (Phase 13).

The edit to `backtest/io.py` is additive: one name in an import line, one docstring sentence, and two appended functions.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/io.py:1-3` | modify | docstring: also names `write_dev_report` |
| `engine/src/seer_engine/backtest/io.py:31` | modify | `from seer_engine.backtest import b_report, dev_report, wf_report` |
| `engine/src/seer_engine/backtest/io.py:362` (append after `write_model_artifact`, the file's last line 361) | modify | new `dev_report_files` and `write_dev_report` |
| `engine/src/seer_engine/commands/backtest_dev.py` | create | the command |
| `engine/tests/test_backtest_dev_command.py` | create | 28 tests: synthetic store via `research.build_store`, fake registry, end-to-end and unit checks, the D-I constant and symbol agreement |
| (conditional, Step 8 only) the same two files | modify | `--workers N` and a fixed-order process pool, only if the Step 7 estimate exceeds 60 min |

## Implementation Steps

### Step 1: `io.dev_report_files` and `io.write_dev_report`
**File:** `engine/src/seer_engine/backtest/io.py:1-3`, `:31`, append at `:362`

**Change:**
- Docstring lines 1–3 become:

  ```python
  """Impure edge of the backtest: read the database once, read the vendored SPY dividends,
  write the report files (v1's ``write_report``, the walk-forward ``write_wf_report``, Strategy B's
  ``write_b_report``, P7a's ``write_dev_report``) and Strategy B's model artifact (``write_model_artifact``).
  ```

  The rest of the docstring is unchanged.
- Line 31 becomes:

  ```python
  from seer_engine.backtest import b_report, dev_report, wf_report
  ```

  There is no import cycle. `dev_report` → `dev` → `book_runner`/`runner`/`strategies` never imports `io` (they are pure), and `research` → `io` → `dev_report` is acyclic because `dev` must not import `research` (phase 9 is pure).
- Append after line 361:

**Code:**
```python


def dev_report_files(
    out_dir: Path, plans_dir: Path, report: dev_report.DevReport
) -> tuple[tuple[Path, str], ...]:
    """Every file of the P7a dev report set, rendered, as ``(path, text)`` in write order:
    <stem>.md, <stem>-rows.csv, <stem>-curves.csv, <stem>-frontier.svg in ``out_dir``, then the
    P7b pre-registration in ``plans_dir``. Nothing is written; ``backtest_dev --only`` renders
    through this to exercise the renderers without touching ``docs/``."""
    out_dir = Path(out_dir)
    plans_dir = Path(plans_dir)
    stem = dev_report.report_stem(report.run_date)
    return (
        (out_dir / f"{stem}.md", dev_report.render_markdown(report)),
        (out_dir / f"{stem}-rows.csv", dev_report.rows_csv(report)),
        (out_dir / f"{stem}-curves.csv", dev_report.curves_csv(report)),
        (out_dir / f"{stem}-frontier.svg", dev_report.frontier_svg(report)),
        (plans_dir / dev_report.preregistration_name(report.run_date), dev_report.render_preregistration(report)),
    )


def write_dev_report(out_dir: Path, plans_dir: Path, report: dev_report.DevReport) -> list[Path]:
    """Write the P7a dev report set into ``out_dir`` and the pre-registration into ``plans_dir``
    (both created if needed) with LF line endings; return the paths in ``dev_report_files``
    order. All five are rendered before any directory is created or file written, so a render
    error leaves no partial set."""
    files = dev_report_files(out_dir, plans_dir, report)
    for directory in sorted({path.parent for path, _ in files}):
        directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for path, text in files:
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths
```
**Impact:**
- Purely additive. `test_strategy_purity.py` already skips `backtest/io.py` by name.
- Every module that imports `backtest.io` now also imports the P7a chain (`dev_report` → `dev` → families). Today those modules are `commands/backtest.py`, `backtest_wf.py`, `backtest_b.py` and phase 4's `research.py`. Their behaviour does not change.

### Step 2: The command module
**File:** `engine/src/seer_engine/commands/backtest_dev.py` (new)

**Change:** the full module. The design choices it encodes:
- **It runs the candidates through `dev.run_registry(..., on_result=...)`** (plan index D-D). The callback hands back each `(index, result, row)`, so the command takes each result's snapshots for the month-end curves and times each candidate from the previous callback, without re-implementing the loop.
  - The prepared-feature cache is therefore `run_registry`'s own: one `prepare(history)` per allocator id, refused when two different objects share an id, dropped after its last use. There is one keying rule in the plan set.
  - A candidate's time includes its allocator's `prepare` when it is the first to use it. The D13 estimate is a class mean over these times, so it errs high (toward the pool), never low.
- **Wall times stay out of the report.** They go to the log and into the separate `Timing` tuple only, never into `DevReport` (invariant 6).
- **`top_years` lists the finalists first.** Finalists come first in finalist order, then the highest-MAR rows (by `(−mar, id)`) until 5. That way every finalist's year-by-year is in the report even when an ineligible row has a higher MAR.
- **`dsr` covers the finalists, or the best row when there are none.** It holds one entry per finalist. With no finalist, it holds one entry for the row with the highest annualized `RunStats.sharpe` (ties by id). The inputs to `dev.deflated_sharpe` are:
  - the row's daily Sharpe, computed from the population moments of `stats.daily_returns`, with skew `m3/m2^1.5` and plain (non-excess) kurtosis `m4/m2²`;
  - `n_trials = len(rows)`;
  - `var_trials`, the **sample** variance (`statistics.variance`) of the daily Sharpe over every row that has one;
  - `t = len(daily_returns)`.

  The value is `None` when it is undefined (fewer than 2 trials or 2 defined Sharpes, or zero variance in the returns).
- **`run_date` defaults to `date.today()`.** It is the owner's local date, the same date convention as committed doc names. It only ever reaches file names.
- **The registry check runs `git status --porcelain -- registry.py`** in that file's directory. Any output counts as dirty: modified, staged or untracked. A file git does not track (`ls-files --error-unmatch` fails), a missing git, or a failing git all count as a refusal too. `--only` skips the check (a smoke that writes nothing).
- **`--only` dedupes its ids and keeps registry order.** An unknown id exits 2. It renders the report in memory through `io.dev_report_files`, writes nothing, and logs the full-run estimate.
- **There is no `--end`.** argparse rejects it as an unknown option (exit 2).

**Code:**
```python
"""`backtest_dev`: run every candidate of the committed P7a registry on the development window
(each candidate's own start .. 2015-10-16) from the local research store, and write the dev
report set and the P7b pre-registration file. Never touches the database.

Flow:
  1. full run only: refuse (exit 2) unless backtest/registry.py is committed, because D6 commits
     every registry append before its dev run; the registry digest is the sha256 of that file
  2. load the research store (research.load_store verifies every file's sha256 and that no row
     is dated after DEV_END); read the unserved members
  3. run the candidates in registry order through dev.run_registry (one prepare per allocator
     id); every candidate is timed in the log through run_registry's on_result callback
  4. build the DevReport: survivorship over MEMBERSHIP_START..DEV_END, SPY price-only and
     total-return curves on the earliest candidate window, the D8 finalists, the top candidates
     year by year, month-end curves, deflated Sharpe
  5. full run: write <stem>.md, -rows.csv, -curves.csv, -frontier.svg to --out and the
     pre-registration to --plans. --only: render everything in memory, write nothing, and log
     an estimate of the full run's wall time (D13: parallelize only above 60 min)

There is no --end: the window always ends at DEV_END (D9). Wall times go to the log only, never
into a report file; the run date appears in file names only.

Exit 0 on success, whatever the finalists; 2 when the registry is uncommitted, the store is
missing or rejected, or an --only id is unknown; 1 on any other error (cli.main).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import math
import statistics
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from seer_engine import config, research
from seer_engine.backtest import dev
from seer_engine.backtest import io as backtest_io
from seer_engine.backtest import registry as registry_module
from seer_engine.backtest.benchmark import Dividend, spy_curves
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.dev_report import DevReport
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.backtest.runner import INITIAL_IDR, survivorship
from seer_engine.sim import initial_cash_usd

log = logging.getLogger(__name__)

HELP = (
    "Run every committed P7a registry candidate on the development window (through 2015-10-16) "
    "from the local research store; write the dev report and the P7b pre-registration (read-only)"
)

DEFAULT_OUT = config.REPO_ROOT / "docs" / "backtests"
DEFAULT_PLANS = config.REPO_ROOT / "docs" / "plans"
REGISTRY_PATH = Path(registry_module.__file__).resolve()
TOP_YEARS = 5
STORE_COUNT_KEYS: tuple[str, ...] = (
    "bar_rows",
    "dividend_rows",
    "fx_rows",
    "symbols_requested",
    "symbols_served",
)
UNSERVED_FILE = "unserved.csv"

Curve = tuple[tuple[date, float], ...]


class BacktestDevError(RuntimeError):
    """The arguments cannot back a dev run (exit 2)."""


@dataclass(frozen=True)
class Timing:
    """Wall time of one candidate, from the previous candidate's end to this one's: it includes
    the allocator's ``prepare`` when this candidate was the first to use it. Log and estimate
    only, never in a report file."""

    candidate_id: str
    estimate_class: tuple[str, str, str]
    seconds: float


# --------------------------------------------------------------------------- arguments


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from e


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--store",
        type=Path,
        default=research.STORE_DIR,
        metavar="DIR",
        help="the research store built by `research_store` (default: engine/.research)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        metavar="DIR",
        help="directory for the dev report files (default: docs/backtests)",
    )
    p.add_argument(
        "--plans",
        type=Path,
        default=DEFAULT_PLANS,
        metavar="DIR",
        help="directory for the P7b pre-registration file (default: docs/plans)",
    )
    p.add_argument(
        "--run-date",
        type=_iso_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="the date in the output file names (default: today); never inside a file",
    )
    p.add_argument(
        "--only",
        nargs="+",
        default=None,
        metavar="ID",
        help="smoke run: only these candidate ids, in registry order; writes nothing and "
        "skips the committed-registry check",
    )


# --------------------------------------------------------------------------- run


def run(args: argparse.Namespace) -> int:
    if getattr(args, "dry_run", False):
        log.info("dry-run: backtest_dev never touches the database; report files are written as usual")
    if research.DEV_END != dev.DEV_END:
        log.error(
            "research.DEV_END %s differs from dev.DEV_END %s; refusing to run",
            research.DEV_END.isoformat(),
            dev.DEV_END.isoformat(),
        )
        return 2
    full = args.only is None
    run_date = args.run_date if args.run_date is not None else date.today()

    if full:
        problem = registry_problem(REGISTRY_PATH)
        if problem is not None:
            log.error(
                "refusing a full dev run: %s. Commit the registry first (D6: every append is "
                "committed before its dev run), or pass --only for a smoke run that writes nothing",
                problem,
            )
            return 2

    registry = load_registry()
    try:
        candidates = select(registry, args.only)
    except BacktestDevError as e:
        log.error("%s", e)
        return 2
    digest = registry_digest(REGISTRY_PATH)
    log.info(
        "registry %s: %d candidate(s), sha256 %s; running %d%s",
        _repo_path(REGISTRY_PATH),
        len(registry),
        digest,
        len(candidates),
        "" if full else " (--only smoke run: nothing is written)",
    )

    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
        unserved = read_unserved(Path(args.store))
    except FileNotFoundError as e:
        log.error(
            "research store %s is missing %s; build it with `python -m seer_engine research_store`",
            args.store,
            e.filename or e,
        )
        return 2
    except ValueError as e:
        log.error("research store %s rejected: %s", args.store, e)
        return 2
    counts = store_counts(data.manifest)
    log.info(
        "research store %s: fingerprint %s, %d bar rows, %d of %d symbols served, %d dividend "
        "rows, %d fx rows, %d unserved (%.2fs)",
        args.store,
        data.fingerprint,
        counts["bar_rows"],
        counts["symbols_served"],
        counts["symbols_requested"],
        counts["dividend_rows"],
        counts["fx_rows"],
        len(unserved),
        _since(t0),
    )

    report, timings = execute(data, candidates, unserved=unserved, registry_digest=digest, run_date=run_date)

    if full:
        for path in backtest_io.write_dev_report(args.out, args.plans, report):
            log.info("wrote %s", path)
        return 0

    t0 = time.perf_counter()
    files = backtest_io.dev_report_files(args.out, args.plans, report)
    log.info(
        "--only: rendered %d file(s) in memory (%d characters); nothing written (%.2fs)",
        len(files),
        sum(len(text) for _, text in files),
        _since(t0),
    )
    estimate = estimate_full_run(registry, timings)
    log.info(
        "estimated full run: %.1f min for %d candidates from %d timed (D13: parallelize only above 60 min)",
        estimate / 60.0,
        len(registry),
        len(timings),
    )
    return 0


def load_registry() -> tuple[Candidate, ...]:
    """The committed registry. A function so tests can inject a fake one."""
    return tuple(registry_module.REGISTRY)


def execute(
    data: research.ResearchData,
    candidates: Sequence[Candidate],
    *,
    unserved: tuple[str, ...],
    registry_digest: str,
    run_date: date,
) -> tuple[DevReport, tuple[Timing, ...]]:
    """Everything between loading and writing. Pure except for logging and wall-time reads,
    so two calls on the same inputs return ``==`` reports; the timings are returned apart."""
    if not candidates:
        raise BacktestDevError("no candidates to run")
    t_all = time.perf_counter()
    market = data.market
    rows, curves, timings = run_candidates(market, data.dividends, data.spy_dividends, candidates)

    t0 = time.perf_counter()
    gaps = survivorship(market, dev.MEMBERSHIP_START, dev.DEV_END)
    log.info(
        "survivorship %s..%s: %d (member, session) pairs without a bar over %d year(s), %d never "
        "fetched (%.2fs)",
        dev.MEMBERSHIP_START.isoformat(),
        dev.DEV_END.isoformat(),
        sum(g.missing for g in gaps),
        len(gaps),
        sum(g.missing_never_fetched for g in gaps),
        _since(t0),
    )

    t0 = time.perf_counter()
    spy_start = min(r.start for r in rows)
    cash0 = initial_cash_usd(INITIAL_IDR, market.usd_idr_on(max(spy_start, dev.FX_START)))
    spy_price, spy_tr = spy_curves(market.spy(), spy_start, dev.DEV_END, cash0, data.spy_dividends)
    log.info(
        "SPY %s..%s from %s USD: price-only and total-return curves, %d sessions (%.2fs)",
        spy_start.isoformat(),
        dev.DEV_END.isoformat(),
        cash0,
        len(spy_tr.snapshots) - 1,
        _since(t0),
    )

    finals = dev.finalists(rows)
    if finals:
        for k, r in enumerate(finals, start=1):
            log.info("finalist %d: %s (%s), MAR %s", k, r.candidate.id, r.candidate.family, fmt_num(r.mar))
    else:
        log.info("finalists: none eligible under D8")

    report = DevReport(
        run_date=run_date,
        store_fingerprint=data.fingerprint,
        store_counts=store_counts(data.manifest),
        unserved=unserved,
        survivorship=gaps,
        registry_digest=registry_digest,
        rows=rows,
        finalists=finals,
        spy_window=(spy_start, dev.DEV_END),
        spy_price=spy_price,
        spy_tr=spy_tr,
        top_years=top_years(rows, finals),
        curves=curves,
        dsr=deflated_sharpes(rows, finals),
    )
    log.info("execute: %d candidate(s) done (%.2fs)", len(rows), _since(t_all))
    return report, timings


# --------------------------------------------------------------------------- candidates


def estimate_class(c: Candidate) -> tuple[str, str, str]:
    """Candidates expected to cost about the same per run: same allocator id, cadence, engine."""
    return (str(c.allocator.id), str(c.rules.cadence), str(c.rules.engine))


def run_candidates(
    market: Market,
    dividends: Mapping[str, Mapping[date, Decimal]],
    spy_dividends: Sequence[Dividend],
    candidates: Sequence[Candidate],
) -> tuple[tuple[DevRow, ...], tuple[tuple[str, Curve], ...], tuple[Timing, ...]]:
    """Run ``candidates`` through ``dev.run_registry`` (sequential, in the given registry order,
    one ``prepare`` per allocator id, every D9 check), collecting each result's month-end curve
    and wall time through its ``on_result`` callback. Returns the rows, the curves and the
    wall times."""
    selected = tuple(candidates)
    curves: list[tuple[str, Curve]] = []
    timings: list[Timing] = []
    n = len(selected)
    clock = [time.perf_counter()]

    def on_result(i: int, result: Any, row: DevRow) -> None:
        now = time.perf_counter()
        seconds = now - clock[0]
        clock[0] = now
        c = selected[i]
        curves.append((c.id, month_end_curve(result.snapshots)))
        timings.append(Timing(c.id, estimate_class(c), seconds))
        _log_row(i + 1, n, row, seconds)

    rows = dev.run_registry(market, dividends, spy_dividends, selected, on_result=on_result)
    return rows, tuple(curves), tuple(timings)


def _log_row(k: int, n: int, row: DevRow, seconds: float) -> None:
    m = row.stats.metrics
    log.info(
        "[%d/%d] %s (%s, %s) %s..%s: return %s vs SPY TR %s, CAGR %s, max DD %s, PF %s, "
        "trades %d, MAR %s, %s (%.2fs)",
        k,
        n,
        row.candidate.id,
        row.candidate.family,
        row.candidate.rules.id,
        row.start.isoformat(),
        row.end.isoformat(),
        fmt_signed_pct(m.total_return),
        fmt_signed_pct(row.spy_tr.total_return),
        fmt_signed_pct(m.cagr),
        fmt_pct(m.max_drawdown),
        fmt_pf(m.profit_factor),
        m.trades,
        fmt_num(row.mar),
        "eligible" if row.eligible else "failed: " + "; ".join(row.failed),
        seconds,
    )


def select(registry: Sequence[Candidate], only: Sequence[str] | None) -> tuple[Candidate, ...]:
    """The whole registry, or the ``only`` ids in registry order (duplicates collapse).
    BacktestDevError names every unknown id."""
    if only is None:
        return tuple(registry)
    wanted = set(only)
    unknown = sorted(wanted - {c.id for c in registry})
    if unknown:
        raise BacktestDevError(f"unknown candidate id(s) for --only: {', '.join(unknown)}")
    return tuple(c for c in registry if c.id in wanted)


# --------------------------------------------------------------------------- report pieces


def month_end_curve(snapshots: Sequence[Any]) -> Curve:
    """Equity normalized to the first snapshot (the starting cash), at the last snapshot of
    every calendar month, ascending. The first snapshot (prev_session(start)) closes its own
    month at 1.0 unless a later snapshot shares that month."""
    if not snapshots:
        raise ValueError("a curve needs at least one snapshot")
    base = snapshots[0].equity_usd
    if base <= 0:
        raise ValueError(f"the first snapshot's equity must be > 0, got {base}")
    last: dict[tuple[int, int], Any] = {}
    for s in snapshots:
        last[(s.date.year, s.date.month)] = s
    return tuple((s.date, float(s.equity_usd / base)) for _, s in sorted(last.items()))


def top_years(rows: Sequence[DevRow], finals: Sequence[DevRow], k: int = TOP_YEARS) -> tuple[
    tuple[str, tuple[tuple[int, float], ...]], ...
]:
    """Year-by-year returns for up to ``k`` candidates: the finalists first (in finalist order),
    then the remaining rows with a MAR, by (-MAR, id)."""
    chosen = [r.candidate.id for r in finals][:k]
    ranked = sorted((r for r in rows if r.mar is not None), key=lambda r: (-r.mar, r.candidate.id))
    for r in ranked:
        if len(chosen) >= k:
            break
        if r.candidate.id not in chosen:
            chosen.append(r.candidate.id)
    by_id = {r.candidate.id: r for r in rows}
    return tuple((cid, tuple(by_id[cid].stats.year_returns)) for cid in chosen)


def daily_moments(returns: Sequence[float]) -> tuple[float, float, float] | None:
    """(daily Sharpe = mean / pstdev, skewness m3 / m2^1.5, kurtosis m4 / m2^2 (not excess))
    over population moments; None with fewer than 2 returns or zero variance."""
    n = len(returns)
    if n < 2:
        return None
    mean = math.fsum(returns) / n
    dev_ = [x - mean for x in returns]
    m2 = math.fsum(d * d for d in dev_) / n
    if not m2 > 0.0:
        return None
    m3 = math.fsum(d * d * d for d in dev_) / n
    m4 = math.fsum(d * d * d * d for d in dev_) / n
    sd = math.sqrt(m2)
    return mean / sd, m3 / (m2 * sd), m4 / (m2 * m2)


def deflated_sharpes(rows: Sequence[DevRow], finals: Sequence[DevRow]) -> tuple[tuple[str, float | None], ...]:
    """The deflated Sharpe ratio per finalist, or for the best annualized-Sharpe row (ties by
    id) when there is none; () when no row has a Sharpe. Trials = every row run; the variance
    across trials is the sample variance of the daily Sharpe over the rows that have one."""
    moments = {r.candidate.id: daily_moments(r.stats.daily_returns) for r in rows}
    sharpes = [m[0] for m in moments.values() if m is not None]
    var_trials = statistics.variance(sharpes) if len(sharpes) >= 2 else None
    if finals:
        targets = list(finals)
    else:
        with_sharpe = [r for r in rows if r.stats.sharpe is not None]
        if not with_sharpe:
            return ()
        targets = [min(with_sharpe, key=lambda r: (-r.stats.sharpe, r.candidate.id))]
    out: list[tuple[str, float | None]] = []
    for r in targets:
        m = moments[r.candidate.id]
        if m is None or var_trials is None or len(rows) < 2:
            out.append((r.candidate.id, None))
            continue
        sr, skew, kurt = m
        value = dev.deflated_sharpe(sr, len(rows), var_trials, len(r.stats.daily_returns), skew, kurt)
        out.append((r.candidate.id, value))
    return tuple(out)


def store_counts(manifest: Mapping[str, Any]) -> dict[str, int]:
    """The manifest's counts in STORE_COUNT_KEYS order; a list value counts its items."""
    out: dict[str, int] = {}
    for key in STORE_COUNT_KEYS:
        if key not in manifest:
            raise ValueError(f"the store manifest has no {key!r}")
        value = manifest[key]
        out[key] = len(value) if isinstance(value, (list, tuple)) else int(value)
    return out


def read_unserved(store_dir: Path) -> tuple[str, ...]:
    """The member symbols yfinance served nothing for (``unserved.csv``), sorted, unique."""
    text = (Path(store_dir) / UNSERVED_FILE).read_text(encoding="utf-8")
    reader = csv.reader(text.splitlines())
    header = next(reader, None)
    if header is None or header[:1] != ["symbol"]:
        raise ValueError(f"{UNSERVED_FILE}: expected a header starting with 'symbol', got {header!r}")
    return tuple(sorted({row[0] for row in reader if row and row[0]}))


# --------------------------------------------------------------------------- registry state


def registry_problem(path: Path) -> str | None:
    """None when ``path`` is tracked by git with no uncommitted change (modified, staged or
    untracked); otherwise why a full dev run must not use it."""
    path = Path(path).resolve()
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", path.name],
            cwd=path.parent,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "git is not installed, so the registry's commit state cannot be checked"
    except NotADirectoryError:
        return f"{path.parent} is not a directory"
    if status.returncode != 0:
        return f"git status failed for {path} ({status.stderr.strip() or status.returncode})"
    if status.stdout.strip():
        return f"{path.name} has uncommitted changes ({status.stdout.strip()})"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", path.name],
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0:
        return f"{path} is not tracked by git"
    return None


def registry_digest(path: Path) -> str:
    """sha256 hex of the registry source file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------- runtime estimate


def estimate_full_run(registry: Sequence[Candidate], timings: Sequence[Timing]) -> float:
    """Seconds a full run should take, from a smoke run's timings: each registry candidate
    costs the mean time of the timed candidates in its estimate_class, else the mean of every
    timed candidate. A timed candidate's time includes its allocator's prepare when it was the
    first to use it, so the estimate errs high (D13 then errs toward the pool)."""
    if not timings:
        return 0.0
    by_class: dict[tuple[str, str, str], list[float]] = {}
    for t in timings:
        by_class.setdefault(t.estimate_class, []).append(t.seconds)
    mean_all = math.fsum(t.seconds for t in timings) / len(timings)
    total = 0.0
    for c in registry:
        runs = by_class.get(estimate_class(c))
        total += math.fsum(runs) / len(runs) if runs else mean_all
    return total


# --------------------------------------------------------------------------- helpers


def _repo_path(path: Path) -> str:
    """``path`` relative to the repository root in POSIX form, or absolute when outside it."""
    p = Path(path).resolve()
    try:
        return p.relative_to(config.REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _since(t0: float) -> float:
    return time.perf_counter() - t0
```
**Impact:**
- `cli.discover()` picks it up. `cli.py` is frozen and needs no change.
- Commands are outside the purity glob, so `time`, `subprocess` and `logging` are allowed here.

### Step 3: The test kit inside the test file (synthetic store and fake registry)
**File:** `engine/tests/test_backtest_dev_command.py` (new). This step is its header and fixtures; Step 4 is its tests. Both blocks together make up the file.

**Change:**
- The synthetic store is built by the real `research.build_store` with a fake downloader and a fake FX fetcher.
- SPY (from 1993-01-29) and QQQ (from 1999-03-10) have long histories; the other 19 `RESEARCH_ETFS` have bars from 2010-01-04, because phase 4 aborts a build that leaves any research ETF unserved. Every member of the vendored membership gets nothing, so it lands in `unserved.csv`.
- Prices are a deterministic seeded walk per symbol, rounded to 2 dp. Dividends are paid quarterly.
- FX is a flat 9000 IDR per USD from 1999-01-04.

The fake registry has 3 candidates:
- two share the `TIMING` allocator, so the prepare cache is reused (one "prepared F1" line in the log);
- the third uses `ROTATION`, and its window starts after QQQ's launch.

**Code:**
```python
"""`backtest_dev` command: discovery and flags (no --end), the io writer, the committed-registry
check, the pure report pieces, and end-to-end runs on a synthetic research store written by
research.build_store with a fake downloader and a tiny fake registry: rows equal
dev.run_registry, byte-identical files across two runs, the dirty-registry refusal, --only
writes nothing, and store errors exit 2.

The store has long bars for SPY (from 1993-01-29) and QQQ (from 1999-03-10), short bars (from
2010-01-04) for every other research ETF (research.build_store refuses a store missing one), and
nothing for the index members, which are listed in unserved.csv.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import math
import re
import shutil
import statistics
import subprocess
import zlib
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from seer_engine import cli, config, dates, research, yahoo
from seer_engine.backtest import dev, dev_report
from seer_engine.backtest import io as bio
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.registry import REGISTRY, SECTOR_ETFS
from seer_engine.backtest.runner import survivorship
from seer_engine.commands import backtest_dev as cmd
from seer_engine.sim.model import Snapshot
from seer_engine.sim.rules import DAILY_SWITCH, DESIGN_V0, MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams
from seer_engine.strategies.f_rotation import ROTATION, RotationParams

# Every research ETF must be served (phase 4 aborts otherwise); only SPY and QQQ need history.
LAUNCH = {
    **{s: date(2010, 1, 4) for s in research.RESEARCH_ETFS},
    "SPY": date(1993, 1, 29),
    "QQQ": date(1999, 3, 10),
}
ALL_SESSIONS = tuple(dates.sessions(research.STORE_START, research.DEV_END))
FX_FIRST = date(1999, 1, 4)
RUN_DATE = date(2031, 1, 2)
DURATION = re.compile(r"\((\d+\.\d{2})s\)")
ADDED = date(2026, 10, 3)

FAKE_REGISTRY = (
    Candidate(
        id="T-REF-SPY-HOLD",
        family="REF",
        rules=MONTHLY_HOLD,
        allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="always", n=1),
        rationale="test: SPY held monthly",
        added=ADDED,
        owner_inputs=(),
    ),
    Candidate(
        id="T-F1-SPY-SMA20-D",
        family="F1",
        rules=DAILY_SWITCH,
        allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=20),
        rationale="test: SPY above its 20-day SMA, checked nightly",
        added=ADDED,
        owner_inputs=(),
    ),
    Candidate(
        id="T-F2-SPYQQQ-3M",
        family="F2",
        rules=MONTHLY_HOLD,
        allocator=ROTATION,
        params=RotationParams(universe=("QQQ", "SPY"), lookback=63, top=1, absolute=True, fallback=None, trend=None),
        rationale="test: 3-month dual momentum over QQQ and SPY",
        added=ADDED,
        owner_inputs=(),
    ),
)
FAKE_IDS = tuple(c.id for c in FAKE_REGISTRY)


@functools.cache
def _series(symbol: str) -> pd.DataFrame:
    """One symbol's full synthetic yfinance frame (actions=True columns), launch..DEV_END."""
    sess = [d for d in ALL_SESSIONS if d >= LAUNCH[symbol]]
    n = len(sess)
    rng = np.random.default_rng(zlib.crc32(symbol.encode()))
    close = np.round(50.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.011, n))), 2)
    prev = np.concatenate(([close[0]], close[:-1]))
    open_ = np.round(prev * (1.0 + rng.normal(0.0, 0.003, n)), 2)
    high = np.round(np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, 0.004, n))), 2)
    low = np.round(np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, 0.004, n))), 2)
    divs = np.zeros(n)
    paid: set[tuple[int, int]] = set()
    for i, d in enumerate(sess):
        if d.month in (3, 6, 9, 12) and d.day >= 15 and (d.year, d.month) not in paid:
            paid.add((d.year, d.month))
            divs[i] = 0.5 if symbol == "SPY" else 0.1
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Adj Close": close,
            "Volume": np.full(n, 1.0e7),
            "Dividends": divs,
            "Stock Splits": np.zeros(n),
        },
        index=pd.DatetimeIndex([pd.Timestamp(d) for d in sess]),
    )


def fake_download(tickers: list[str], start: date, end_exclusive: date) -> pd.DataFrame:
    """yfinance group_by='ticker' shape: MultiIndex (Ticker, Price), outer-joined dates."""
    parts: dict[str, pd.DataFrame] = {}
    for t in tickers:
        symbol = yahoo.from_yahoo(t)
        if symbol in LAUNCH:
            f = _series(symbol)
            mask = (f.index >= pd.Timestamp(start)) & (f.index < pd.Timestamp(end_exclusive))
            parts[t] = f[mask]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, axis=1)


def fake_fx(start: date, end: date) -> list[tuple[date, Decimal]]:
    a = max(start, FX_FIRST)
    if end < a:
        return []
    return [(d, Decimal("9000")) for d in dates.sessions(a, end)]


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=seer-test", "-c", "user.email=seer-test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def committed_file(root: Path, name: str = "registry.py", text: str = "REGISTRY = ()\n") -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    path = repo / name
    path.write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", "registry")
    return path


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("research") / "store"
    research.build_store(path, downloader=fake_download, fetch_fx=fake_fx, sleep=lambda _s: None)
    return path


@pytest.fixture(scope="module")
def data(store: Path) -> research.ResearchData:
    return research.load_store(store)


@pytest.fixture(scope="module")
def executed(store: Path, data: research.ResearchData):
    return cmd.execute(
        data,
        FAKE_REGISTRY,
        unserved=cmd.read_unserved(store),
        registry_digest="0" * 64,
        run_date=RUN_DATE,
    )


@pytest.fixture
def fake_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = committed_file(tmp_path)
    monkeypatch.setattr(cmd, "load_registry", lambda: FAKE_REGISTRY)
    monkeypatch.setattr(cmd, "REGISTRY_PATH", path)
    return path


def argv(store: Path, tmp_path: Path, tag: str, *extra: str) -> list[str]:
    return [
        "backtest_dev",
        "--store", str(store),
        "--out", str(tmp_path / f"out-{tag}"),
        "--plans", str(tmp_path / f"plans-{tag}"),
        "--run-date", RUN_DATE.isoformat(),
        *extra,
    ]


def expected_names() -> tuple[list[str], str]:
    stem = dev_report.report_stem(RUN_DATE)
    return [f"{stem}.md", f"{stem}-rows.csv", f"{stem}-curves.csv", f"{stem}-frontier.svg"], dev_report.preregistration_name(RUN_DATE)
```
**Impact:** the module-scoped `store` fixture costs one `build_store` call over the real vendored membership (no `data_dir`): about 27 fake batches plus one individual retry per unserved member (about 1,040, each an empty frame; `sleep` is a no-op), all in memory.

### Step 4: The tests
**File:** `engine/tests/test_backtest_dev_command.py` (continued from Step 3)

**Code:**
```python
# ------------------------------------------------------------------ contract and flags


def test_research_and_dev_constants_agree():
    # Plan index D-I: phase 9's pure dev.py cannot import research, so the duplicates are pinned here.
    assert research.DEV_END == dev.DEV_END == date(2015, 10, 16)
    assert research.MEMBERSHIP_START == dev.MEMBERSHIP_START
    assert research.FX_START == dev.FX_START


def test_registry_reads_only_research_etfs():
    # Plan index D-I: phase 11's pure registry.py cannot import research either.
    assert SECTOR_ETFS == research.SECTOR_ETFS
    needed: set[str] = set()
    for c in REGISTRY:
        if c.rules is DESIGN_V0:
            continue
        needed |= set(c.allocator.symbols(c.params)) | set(c.allocator.holds(c.params))
        if c.rules.idle_symbol is not None:
            needed.add(c.rules.idle_symbol)
    assert needed <= set(research.RESEARCH_ETFS), sorted(needed - set(research.RESEARCH_ETFS))


def test_discovered_with_defaults():
    assert "backtest_dev" in cli.discover()
    args = cli.build_parser().parse_args(["backtest_dev"])
    assert args._run is cmd.run
    assert args.store == research.STORE_DIR
    assert args.out == cmd.DEFAULT_OUT == config.REPO_ROOT / "docs" / "backtests"
    assert args.plans == cmd.DEFAULT_PLANS == config.REPO_ROOT / "docs" / "plans"
    assert (args.run_date, args.only) == (None, None)
    assert cmd.REGISTRY_PATH.name == "registry.py"
    assert cmd.REGISTRY_PATH.parent.name == "backtest"
    assert cmd.HELP


def test_help_lists_every_flag_and_no_end(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["backtest_dev", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--store", "--out", "--plans", "--run-date", "--only"):
        assert flag in out, flag
    assert "--end" not in out


@pytest.mark.parametrize("extra", [["--end", "2016-01-04"], ["--run-date", "someday"], ["--only"]])
def test_bad_argument_is_a_usage_error(extra):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["backtest_dev", *extra])
    assert exc.value.code == 2


# ------------------------------------------------------------------ io writer


def test_write_dev_report_writes_five_files_in_order_with_lf(tmp_path, monkeypatch):
    texts = {
        "render_markdown": "# md\nline\n",
        "rows_csv": "id,family\n",
        "curves_csv": "date,spy_tr\n",
        "frontier_svg": "<svg>frontier</svg>\n",
        "render_preregistration": "# pre-registration\n",
    }
    for name, text in texts.items():
        monkeypatch.setattr(dev_report, name, lambda report, _t=text: _t)
    report = SimpleNamespace(run_date=RUN_DATE)
    paths = bio.write_dev_report(tmp_path / "nested" / "out", tmp_path / "nested" / "plans", report)
    names, prereg = expected_names()
    assert [p.name for p in paths] == [*names, prereg]
    assert [p.parent.name for p in paths] == ["out"] * 4 + ["plans"]
    assert [p.read_bytes() for p in paths] == [t.encode("utf-8") for t in texts.values()]


def test_write_dev_report_renders_everything_before_writing(tmp_path, monkeypatch):
    for name in ("render_markdown", "rows_csv", "curves_csv", "frontier_svg"):
        monkeypatch.setattr(dev_report, name, lambda report: "ok\n")

    def boom(report):
        raise RuntimeError("pre-registration render failed")

    monkeypatch.setattr(dev_report, "render_preregistration", boom)
    with pytest.raises(RuntimeError, match="pre-registration render failed"):
        bio.write_dev_report(tmp_path / "out", tmp_path / "plans", SimpleNamespace(run_date=RUN_DATE))
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "plans").exists()


# ------------------------------------------------------------------ registry state


def test_registry_problem_tracks_every_uncommitted_state(tmp_path):
    path = committed_file(tmp_path)
    assert cmd.registry_problem(path) is None
    path.write_text("REGISTRY = (1,)\n", encoding="utf-8")
    assert "uncommitted" in cmd.registry_problem(path)
    git(path.parent, "add", path.name)
    assert "uncommitted" in cmd.registry_problem(path)  # staged, not committed
    git(path.parent, "commit", "-q", "-m", "append")
    assert cmd.registry_problem(path) is None
    untracked = path.parent / "other.py"
    untracked.write_text("x = 1\n", encoding="utf-8")
    assert "uncommitted" in cmd.registry_problem(untracked)
    outside = tmp_path / "loose"
    outside.mkdir()
    (outside / "registry.py").write_text("REGISTRY = ()\n", encoding="utf-8")
    assert cmd.registry_problem(outside / "registry.py") is not None  # not a git repository


def test_registry_digest_is_the_sha256_of_the_file_bytes(tmp_path):
    path = tmp_path / "registry.py"
    path.write_bytes(b"REGISTRY = ()\n")
    assert cmd.registry_digest(path) == hashlib.sha256(b"REGISTRY = ()\n").hexdigest()


# ------------------------------------------------------------------ pure pieces


def test_select_keeps_registry_order_dedupes_and_rejects_unknown():
    assert cmd.select(FAKE_REGISTRY, None) == FAKE_REGISTRY
    picked = cmd.select(FAKE_REGISTRY, ["T-F2-SPYQQQ-3M", "T-REF-SPY-HOLD", "T-F2-SPYQQQ-3M"])
    assert [c.id for c in picked] == ["T-REF-SPY-HOLD", "T-F2-SPYQQQ-3M"]
    with pytest.raises(cmd.BacktestDevError, match="NOPE-1, NOPE-2"):
        cmd.select(FAKE_REGISTRY, ["NOPE-2", "T-REF-SPY-HOLD", "NOPE-1"])


def test_month_end_curve_normalizes_and_keeps_each_months_last_snapshot():
    snaps = [
        Snapshot(date(2015, 1, 30), Decimal("100"), Decimal("100")),
        Snapshot(date(2015, 2, 2), Decimal("0"), Decimal("110")),
        Snapshot(date(2015, 2, 27), Decimal("0"), Decimal("120")),
        Snapshot(date(2015, 3, 2), Decimal("0"), Decimal("90")),
    ]
    assert cmd.month_end_curve(snaps) == (
        (date(2015, 1, 30), 1.0),
        (date(2015, 2, 27), 1.2),
        (date(2015, 3, 2), 0.9),
    )
    with pytest.raises(ValueError):
        cmd.month_end_curve([])


def _row(cid: str, mar, years=(), returns=(), sharpe=None):
    return SimpleNamespace(
        candidate=SimpleNamespace(id=cid),
        mar=mar,
        stats=SimpleNamespace(year_returns=tuple(years), daily_returns=tuple(returns), sharpe=sharpe),
    )


def test_top_years_lists_finalists_first_then_by_mar():
    rows = [_row(f"C{k}", mar, years=((2000, k / 100),)) for k, mar in enumerate([0.5, None, 2.0, 1.0, 2.0, 0.1, 0.3])]
    finals = [rows[3]]  # C3, MAR 1.0, ranked below C2 and C4
    got = cmd.top_years(rows, finals)
    assert [cid for cid, _ in got] == ["C3", "C2", "C4", "C0", "C6"]
    assert got[0][1] == ((2000, 0.03),)
    assert [cid for cid, _ in cmd.top_years(rows, [])] == ["C2", "C4", "C3", "C0", "C6"]


def test_daily_moments_hand_checked():
    r = [0.01, -0.01, 0.02, 0.0, 0.03]
    mean = sum(r) / 5
    d = [x - mean for x in r]
    m2 = sum(x * x for x in d) / 5
    m3 = sum(x ** 3 for x in d) / 5
    m4 = sum(x ** 4 for x in d) / 5
    sr, skew, kurt = cmd.daily_moments(r)
    assert sr == pytest.approx(mean / math.sqrt(m2), rel=1e-12)
    assert skew == pytest.approx(m3 / m2 ** 1.5, rel=1e-12)
    assert kurt == pytest.approx(m4 / m2 ** 2, rel=1e-12)
    assert cmd.daily_moments([0.01]) is None
    assert cmd.daily_moments([0.01, 0.01, 0.01]) is None


def test_deflated_sharpes_use_every_trial_and_fall_back_to_the_best_sharpe():
    a = _row("A", 1.0, returns=[0.01, -0.005, 0.02, 0.0, 0.004], sharpe=1.5)
    b = _row("B", 0.5, returns=[0.002, -0.01, 0.005, 0.001, -0.002], sharpe=0.2)
    c = _row("C", None, returns=[], sharpe=None)
    sr_a, skew_a, kurt_a = cmd.daily_moments(a.stats.daily_returns)
    sr_b = cmd.daily_moments(b.stats.daily_returns)[0]
    var = statistics.variance([sr_a, sr_b])
    expected = dev.deflated_sharpe(sr_a, 3, var, 5, skew_a, kurt_a)
    assert cmd.deflated_sharpes([a, b, c], []) == (("A", expected),)
    assert cmd.deflated_sharpes([a, b, c], [b, a])[1] == ("A", expected)
    assert cmd.deflated_sharpes([c], []) == ()
    assert cmd.deflated_sharpes([a], [a]) == (("A", None),)  # one trial: undefined


def test_estimate_full_run_by_class():
    t = (
        cmd.Timing("T-REF-SPY-HOLD", cmd.estimate_class(FAKE_REGISTRY[0]), 12.0),
        cmd.Timing("T-F2-SPYQQQ-3M", cmd.estimate_class(FAKE_REGISTRY[2]), 23.0),
    )
    # REF (12) + F1 daily: no timed class -> mean of all, 17.5 + ROT (23).
    assert cmd.estimate_full_run(FAKE_REGISTRY, t) == pytest.approx(12.0 + 17.5 + 23.0)
    assert cmd.estimate_full_run(FAKE_REGISTRY, ()) == 0.0


def test_store_counts_and_unserved(store, data):
    counts = cmd.store_counts(data.manifest)
    assert tuple(counts) == cmd.STORE_COUNT_KEYS
    assert all(isinstance(v, int) and v >= 0 for v in counts.values())
    unserved = cmd.read_unserved(store)
    assert unserved == tuple(sorted(set(unserved)))
    assert "SPY" not in unserved and "QQQ" not in unserved
    assert unserved  # every vendored member is served nothing by the fake downloader
    with pytest.raises(ValueError, match="no 'bar_rows'"):
        cmd.store_counts({})


# ------------------------------------------------------------------ execute


def test_execute_rows_equal_run_registry_and_fields(store, data, executed):
    report, timings = executed
    assert report.rows == dev.run_registry(data.market, data.dividends, data.spy_dividends, FAKE_REGISTRY)
    assert tuple(r.candidate.id for r in report.rows) == FAKE_IDS
    assert report.finalists == dev.finalists(report.rows)
    assert report.survivorship == survivorship(data.market, dev.MEMBERSHIP_START, dev.DEV_END)
    assert report.spy_window == (min(r.start for r in report.rows), dev.DEV_END)
    assert report.store_fingerprint == data.fingerprint
    assert report.store_counts == cmd.store_counts(data.manifest)
    assert report.unserved == cmd.read_unserved(store)
    assert report.run_date == RUN_DATE
    assert tuple(cid for cid, _ in report.curves) == FAKE_IDS
    for _, curve in report.curves:
        assert curve[0][1] == 1.0
        assert curve[-1][0] == dev.DEV_END
    assert all(r.end == dev.DEV_END for r in report.rows)
    assert report.rows[2].start > LAUNCH["QQQ"]  # the rotation waits for QQQ's lookback
    assert report.top_years == cmd.top_years(report.rows, report.finalists)
    assert report.dsr == cmd.deflated_sharpes(report.rows, report.finalists)
    assert [t.candidate_id for t in timings] == list(FAKE_IDS)


def test_execute_twice_is_equal(store, data, executed):
    again = cmd.execute(
        data, FAKE_REGISTRY, unserved=cmd.read_unserved(store), registry_digest="0" * 64, run_date=RUN_DATE
    )
    assert again[0] == executed[0]


def test_run_candidates_logs_every_candidate_and_prepares_once(data, caplog, monkeypatch):
    calls: list[str] = []
    for allocator in (TIMING, ROTATION):
        real = allocator.prepare
        monkeypatch.setattr(
            allocator, "prepare", lambda history, _real=real, _id=allocator.id: (calls.append(_id), _real(history))[1]
        )
    caplog.set_level(logging.INFO, logger=cmd.__name__)
    rows, curves, timings = cmd.run_candidates(data.market, data.dividends, data.spy_dividends, FAKE_REGISTRY)
    messages = [r.getMessage() for r in caplog.records if r.name == cmd.__name__]
    for k, cid in enumerate(FAKE_IDS, start=1):
        line = [m for m in messages if m.startswith(f"[{k}/3] {cid} ")]
        assert len(line) == 1, cid
        assert DURATION.search(line[0])
    assert calls == ["F1", "ROT"]  # dev.run_registry: TIMING once for two candidates, ROTATION once
    assert [t.candidate_id for t in timings] == list(FAKE_IDS)
    assert all(t.seconds >= 0.0 for t in timings)
    assert tuple(cid for cid, _ in curves) == FAKE_IDS


# ------------------------------------------------------------------ end to end


def test_full_run_writes_byte_identical_files(store, tmp_path, fake_registry):
    assert cli.main(argv(store, tmp_path, "1")) == 0
    assert cli.main(argv(store, tmp_path, "2")) == 0
    names, prereg = expected_names()
    for tag in ("1", "2"):
        assert sorted(p.name for p in (tmp_path / f"out-{tag}").iterdir()) == sorted(names)
        assert [p.name for p in (tmp_path / f"plans-{tag}").iterdir()] == [prereg]
    pairs = [(tmp_path / "out-1" / n, tmp_path / "out-2" / n) for n in names]
    pairs.append((tmp_path / "plans-1" / prereg, tmp_path / "plans-2" / prereg))
    for a, b in pairs:
        assert a.read_bytes() == b.read_bytes(), a.name
        text = a.read_text(encoding="utf-8")
        assert RUN_DATE.isoformat() not in text, a.name  # the run date is in file names only
        assert "\r" not in text, a.name


@pytest.mark.parametrize("state", ["modified", "untracked"])
def test_full_run_refuses_an_uncommitted_registry(store, tmp_path, monkeypatch, state):
    if state == "modified":
        path = committed_file(tmp_path)
        path.write_text("REGISTRY = (1,)\n", encoding="utf-8")
    else:
        path = committed_file(tmp_path, name="other.py")
        path = path.parent / "registry.py"
        path.write_text("REGISTRY = ()\n", encoding="utf-8")
    monkeypatch.setattr(cmd, "REGISTRY_PATH", path)
    monkeypatch.setattr(cmd, "load_registry", lambda: FAKE_REGISTRY)

    def no_store(*_a, **_k):
        raise AssertionError("the store must not be loaded after a refusal")

    monkeypatch.setattr(research, "load_store", no_store)
    assert cli.main(argv(store, tmp_path, "x")) == 2
    assert not (tmp_path / "out-x").exists()
    assert not (tmp_path / "plans-x").exists()


def test_only_writes_nothing_even_with_a_dirty_registry(store, tmp_path, monkeypatch, caplog):
    path = committed_file(tmp_path)
    path.write_text("REGISTRY = (1,)\n", encoding="utf-8")
    monkeypatch.setattr(cmd, "REGISTRY_PATH", path)
    monkeypatch.setattr(cmd, "load_registry", lambda: FAKE_REGISTRY)
    assert cli.main(argv(store, tmp_path, "o", "--only", "T-F2-SPYQQQ-3M", "T-REF-SPY-HOLD")) == 0
    assert not (tmp_path / "out-o").exists()
    assert not (tmp_path / "plans-o").exists()
    messages = [r.getMessage() for r in caplog.records if r.name == cmd.__name__]
    assert any(m.startswith("[1/2] T-REF-SPY-HOLD ") for m in messages)
    assert any(m.startswith("[2/2] T-F2-SPYQQQ-3M ") for m in messages)
    assert any(m.startswith("estimated full run: ") for m in messages)


def test_only_unknown_id_exits_2(store, tmp_path, fake_registry):
    assert cli.main(argv(store, tmp_path, "u", "--only", "NOPE")) == 2
    assert not (tmp_path / "out-u").exists()


def test_missing_store_exits_2(tmp_path, fake_registry):
    assert cli.main(argv(tmp_path / "no-store", tmp_path, "m")) == 2
    assert not (tmp_path / "out-m").exists()


def test_tampered_store_exits_2(store, tmp_path, fake_registry):
    copy = tmp_path / "store"
    shutil.copytree(store, copy)
    bars_csv = copy / "bars.csv"
    raw = bars_csv.read_bytes()
    bars_csv.write_bytes(raw[:-2] + (b"9" if raw[-2:-1] != b"9" else b"8") + raw[-1:])
    assert cli.main(argv(copy, tmp_path, "t")) == 2
    assert not (tmp_path / "out-t").exists()
```
**Count:** 28 collected tests:
- 1 research/dev constants, 1 registry symbols (both D-I), 1 discovery, 1 help;
- 3 bad-argument cases (`--end`, a bad `--run-date`, a bare `--only`);
- 2 io;
- 2 registry;
- 7 pure-piece tests: select, month_end, top_years, moments, dsr, estimate, store counts;
- 3 for execute and run_candidates: the rows/fields test, the equality test and the log test;
- 1 byte-identical run;
- 2 refusal cases;
- 1 `--only`, 1 unknown id, 1 missing store, 1 tampered store.

The suite count rises by **28** over the count after phase 11 (1694 with every earlier phase landed; see the index's count table). None of these tests need Postgres.

**Impact:** `git` must be on PATH, as it is in GitHub Actions and locally. Nothing is skipped.

### Step 5: Run the suite
Run from the worktree root (`/home/miftah/.worktrees/seer/trade-rules-dev-search`), with the worktree's own venv:

```bash
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_backtest_dev_command.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
git diff --stat 2546a92 -- engine/src/seer_engine/sim/model.py engine/src/seer_engine/sim/lifecycle.py \
  engine/src/seer_engine/sim/sizing.py engine/src/seer_engine/sim/split_adjust.py \
  engine/src/seer_engine/backtest/runner.py engine/src/seer_engine/backtest/market.py \
  engine/src/seer_engine/backtest/benchmark.py engine/src/seer_engine/backtest/metrics.py \
  engine/src/seer_engine/backtest/walkforward.py engine/src/seer_engine/backtest/wf_report.py \
  engine/src/seer_engine/backtest/report.py engine/src/seer_engine/backtest/tuning.py \
  engine/src/seer_engine/backtest/labels.py engine/src/seer_engine/backtest/b_walkforward.py \
  engine/src/seer_engine/backtest/b_report.py engine/src/seer_engine/strategies/base.py \
  engine/src/seer_engine/strategies/a.py engine/src/seer_engine/strategies/a2.py \
  engine/src/seer_engine/strategies/b.py engine/src/seer_engine/strategies/b_model.py \
  engine/src/seer_engine/commands/backtest.py engine/src/seer_engine/commands/backtest_wf.py \
  engine/src/seer_engine/commands/backtest_b.py engine/src/seer_engine/cli.py \
  engine/src/seer_engine/membership.py engine/src/seer_engine/fx.py
```
The suite must pass with 0 skipped, at (count after phase 11) + 28 = 1694. The `git diff` must print nothing. Log the passed count in the phase log.

### Step 6: Commit the code before the smoke
Commit Steps 1–4. The commit must not include `engine/.research/`, which is gitignored by phase 4. `git status --porcelain -- engine/src/seer_engine/backtest/registry.py` must print nothing. Phase 11 committed it, and this phase never edits it.

### Step 7: The timed `--only` smoke on the real store (D13 measurement)
**Precondition:** `engine/.research/` holds phase 4's real build. Check it with `engine/.venv/bin/python -m seer_engine research_store --verify` and log the fingerprint. If it differs from phase 4's logged value, log both and continue (a smoke run writes nothing). If the store is missing, run `engine/.venv/bin/python -m seer_engine research_store` (a 30–60 min background build), log the new fingerprint, and continue.

**Command** (worktree root; nothing is written to `docs/`; the log goes to the scratchpad):
```bash
cd /home/miftah/.worktrees/seer/trade-rules-dev-search/engine && /usr/bin/time -v .venv/bin/python -m seer_engine backtest_dev --only \
  REF-SPY-HOLD REF-A-V0 \
  F1-SPY-SMA200-D F1-SPY-10MSMA-M F1-SPY-VT12-W \
  F10-SSO-SMA200-D \
  F11-SPY-TOM-TREND \
  F2-GEM-SPYEFA-IEF \
  F3-SEC-TOP3-6M \
  F4-MOM12-N10-TREND F4-MOM12-N10-TREND-W \
  F5-LV60-N20 \
  F6-ML-P50-N10-VT12 \
  F7-RSI2-T20-DIP \
  F9-SPY200M70-MOM30 F9-SPY200D50-SWING50 \
  2>&1 | tee "$SCRATCH/p7a-smoke.log"
```
`$SCRATCH` is the session scratchpad.

The 16 candidates cover:
- every family: REF, F1, F2, F3, F4, F5, F6, F7, F9, F10 and F11;
- every allocator id: `F1`, `F11`, `ROT`, `FAC`, `F7`, `BLEND`, `VOLTARGET`, plus the `DESIGN_V0` Strategy path;
- every cadence: daily, weekly and monthly;
- both engines.

**Record in the phase log:**
- every `[k/16] …` line with its seconds (a candidate's seconds include its allocator's prepare when it is the first to use it);
- the `estimated full run: N min` line;
- the peak RSS (`Maximum resident set size` from `/usr/bin/time -v`);
- the exit code (must be 0);
- confirmation that `git status --porcelain docs/` prints nothing.

**Decision rule (D13):**
- **Estimate ≤ 60 min:** no pool. Step 8 is **not** implemented. Write "D13: sequential, estimated N min, no pool" in the phase log, and the phase is done.
- **Estimate > 60 min:** first look for an obvious vectorization miss in the slowest class's log (a single-window path where a prepared one was expected). Record it as a handoff to the owning family phase in the phase log. Then implement Step 8, which speeds things up without changing a byte.
- **REF-A-V0** starts before 1999-01-04. Phase 9 runs it on a market copy whose FX is the single row `(start, rate on 1999-01-04)` (plan index D-C), so it must run with exit 0. A `no usd_idr rate` error here is a phase-9 bug: write a failing regression test in `tests/test_backtest_dev.py`, fix `dev.py`, and re-run the smoke.

### Step 8 (CONDITIONAL — only if Step 7's estimate exceeds 60 min): a fixed-order process pool
**Files:** `engine/src/seer_engine/commands/backtest_dev.py` and `engine/tests/test_backtest_dev_command.py`

**Change:**
- Add `--workers N` (default 1).
- With N > 1, `execute` calls `run_candidates_pool`. It forks after the market is loaded, so workers share it copy-on-write. There is one task per candidate. `Executor.map` returns results in submission order, which is registry order.
- Each worker prepares an allocator's features once, the first time it needs them, keyed by `allocator.id` exactly as `dev.run_registry` keys them (plan index D-D). `test_pool_rows_equal_sequential` pins that the pool's rows and curves equal the sequential (`run_registry`) ones.
- Each `DevRow` comes back pickled. Its `candidate` is replaced by the parent's original object, so rows `==` the sequential rows. Allocator singletons compare by identity, so a pickled copy alone would not be equal.
- Results are gathered and logged in registry order.

**Code (additions to `backtest_dev.py`):**

At the imports, add:
```python
import dataclasses
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
```
In `add_arguments`, append:
```python
    p.add_argument(
        "--workers",
        type=_positive_int,
        default=1,
        metavar="N",
        help="processes for the candidate runs (default 1: sequential); results are gathered "
        "in registry order, so the files are identical for any N",
    )
```
New helpers and the pool:
```python
def _positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}") from e
    if n < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}")
    return n


_POOL: dict[str, Any] = {}


def _pool_run(i: int) -> tuple[int, DevRow, Curve, Timing]:
    """One candidate in a forked worker; inputs come from _POOL, set before the fork. The
    prepared value is keyed by allocator id, as dev.run_registry keys it."""
    market = _POOL["market"]
    c = _POOL["candidates"][i]
    cache: dict[str, Any] = _POOL.setdefault("cache", {})
    t0 = time.perf_counter()
    key = str(c.allocator.id)
    if key not in cache:
        cache[key] = c.allocator.prepare(market.history)
    result, row = dev.run_candidate(market, _POOL["dividends"], _POOL["spy_dividends"], c, prepared=cache[key])
    return i, row, month_end_curve(result.snapshots), Timing(c.id, estimate_class(c), _since(t0))


def run_candidates_pool(
    market: Market,
    dividends: Mapping[str, Mapping[date, Decimal]],
    spy_dividends: Sequence[Dividend],
    candidates: Sequence[Candidate],
    workers: int,
) -> tuple[tuple[DevRow, ...], tuple[tuple[str, Curve], ...], tuple[Timing, ...]]:
    """run_candidates across ``workers`` forked processes, gathered in the given order; equal
    to the sequential result."""
    _POOL.clear()
    _POOL.update(market=market, dividends=dividends, spy_dividends=spy_dividends, candidates=tuple(candidates))
    rows: list[DevRow] = []
    curves: list[tuple[str, Curve]] = []
    timings: list[Timing] = []
    n = len(candidates)
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork")) as ex:
            for i, row, curve, timing in ex.map(_pool_run, range(n), chunksize=1):
                original = candidates[i]
                rows.append(dataclasses.replace(row, candidate=original))
                curves.append((original.id, curve))
                timings.append(timing)
                _log_row(i + 1, n, rows[-1], timing.seconds)
    finally:
        _POOL.clear()
    return tuple(rows), tuple(curves), tuple(timings)
```
**Wiring:**
- `execute` gains a keyword `workers: int = 1`. Its first line after the empty-check becomes:

  ```python
      if workers > 1:
          rows, curves, timings = run_candidates_pool(market, data.dividends, data.spy_dividends, candidates, workers)
      else:
          rows, curves, timings = run_candidates(market, data.dividends, data.spy_dividends, candidates)
  ```

- `run` passes `workers=args.workers` to `execute`.
- `estimate_full_run` stays a sequential estimate. Log the wall time of `execute` too.

**Tests (append; +2 tests, so 30 in all):**
```python
def test_pool_rows_equal_sequential(data, executed):
    rows, curves, _ = cmd.run_candidates_pool(data.market, data.dividends, data.spy_dividends, FAKE_REGISTRY, 2)
    report, _ = executed
    assert rows == report.rows
    assert curves == report.curves


def test_workers_flag_defaults_to_one_and_rejects_zero():
    assert cli.build_parser().parse_args(["backtest_dev"]).workers == 1
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["backtest_dev", "--workers", "0"])
```
After Step 8, re-run Step 7 with `--workers 4`. Record the new wall time. Also record whether `prepare`-heavy classes (FAC) now dominate. The suite is then 1696 (+2).

**Impact:** a speed-up only. The rows, the files and the registry order are unchanged, which `test_pool_rows_equal_sequential` checks.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.commands.backtest_dev, seer_engine.backtest.io"` (from the worktree root).

**Tests:**
- `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`;
- the count must equal the phase-11 count + 28 = 1694 (+30 = 1696 if Step 8 ran), with 0 skipped;
- the frozen-set `git diff --stat 2546a92` from Step 5 must print nothing.

**Manual check:**
- `engine/.venv/bin/python -m seer_engine backtest_dev --help` lists `--store`, `--out`, `--plans`, `--run-date` and `--only` (plus `--workers` after Step 8), and no `--end`.
- The Step 7 smoke log shows one timed line per candidate and the estimate line.
- After the smoke, `git status --porcelain docs/` prints nothing.

**Exit criteria:**
- The suite is green with 0 skipped.
- `backtest_dev` is discovered.
- `io.write_dev_report` writes the five files, with everything rendered first.
- These are tested on a store built by `research.build_store`:
  - the dirty and untracked registry refusals (exit 2, nothing written, the store never loaded);
  - `--only` writes nothing;
  - two full runs write byte-identical files;
  - `rows == dev.run_registry(...)`;
  - `research.DEV_END`, `MEMBERSHIP_START` and `FX_START` equal `dev`'s; `registry.SECTOR_ETFS == research.SECTOR_ETFS`; every registry fixed symbol is in `research.RESEARCH_ETFS` (D-I).
- The real-store smoke ran with exit 0. Its per-candidate times and the full-run estimate are in the phase log, along with the D13 decision (sequential, or the pool with its measured time).

## Handoffs

- **Phase 13 (real run):**
  - Run `python -m seer_engine backtest_dev --run-date <YYYY-MM-DD>`, with `--workers N` if Step 8 landed. Pass `--run-date` explicitly so that the re-run for the `cmp` lands on the same file names even across midnight.
  - The command refuses unless `backtest/registry.py` is committed. Any D6 append must be committed before its run.
  - The smoke's estimate tells phase 13 how long to expect.
- **Phase 9 (`dev.py`) — FX before 1999 for `DESIGN_V0` (settled, plan index D-C):** REF-A-V0's natural start (`MEMBERSHIP_START` 1996-01-02 plus A's lookback) is before `FX_START`. Phase 9 runs such a window on a market copy whose `fx` is the single row `(start, usd_idr_on(FX_START))`; windows are not clamped. This command's SPY cash uses the same rate (`usd_idr_on(max(spy_start, FX_START))`). The smoke still includes REF-A-V0, as the real-data check of that path.
- **Phase 9 (`dev.py`) — the shared prepare key (settled, plan index D-D):** `run_candidates` calls `dev.run_registry(…, on_result=…)`, so there is one keying rule (`allocator.id`); only the conditional Step 8 pool keeps its own per-worker cache, keyed the same way and pinned equal by a test.
- **Phase 9 (`dev.py`) — `deflated_sharpe` inputs:** it receives `n_trials >= 2` and `var_trials` defined; this command guards both. For any remaining undefined case (a non-positive denominator) it should return `None`, not raise.
- **Phase 10 (`dev_report.py`) — subsets:** `DevReport` and every renderer must accept a registry-order subset of rows (the `--only` path), an empty `finalists`, and `dsr == ()`.
- **Phase 10 (`dev_report.py`) — what this phase fills in:** the field semantics phase 10 should document in the markdown:
  - `top_years` holds the finalists first, then the rest by MAR, up to 5;
  - each `curves` entry is a month-end equity series normalized to 1.0 at `prev_session(start)`;
  - `dsr` holds the finalists, or the single best-Sharpe row, and `None` means undefined;
  - `store_counts` is ordered by `STORE_COUNT_KEYS`.
- **Phase 4 (`research.py`):** these hold as phase 4 plans them: the fake `downloader` and `fetch_fx` shapes, the `unserved.csv` header, the manifest count keys, `ValueError` for a missing or tampered store, and the requirement that every research ETF be served (the fixture serves all 21).
- **Phase 2 (allocators):** `BlendAllocator.prepare(history)` and `VolTargetAllocator.prepare(history)` return a param-independent `LazyPrepared` (phase 2 Decision 1, tested there by `test_blend_prepares_each_part_once` and `test_voltarget_prepares_the_inner_allocator_once`), so one prepared value per allocator id is correct for both F9 rows.
- **Phase 13 (docs, R9):** document `backtest_dev`'s flags and its refusal in `engine/package_readme.md`.

## Rollback

- Run `git revert` on this phase's commit(s). That removes `commands/backtest_dev.py` and the test file, and restores `backtest/io.py`'s import line, docstring and tail.
- Nothing else depends on them until phase 13.
- The smoke run writes no files, so there is nothing to clean up.
