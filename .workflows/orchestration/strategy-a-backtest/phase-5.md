# Phase 5: Neon loader with cache + `backtest` command

**Plan set:** `STRATEGY_A_BACKTEST_PLAN.md`
**Analysis:** `20261003-144506-Q8N4_code_analyzer.md`
**Satisfies:** R5, R6 — the command that turns Neon data into the committed report files (the real run itself is phase 6)
**Depends on:** Phase 4 (and through it phases 1, 2, 3)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/backtest` (`io.py`), `engine/src/seer_engine/commands` (`backtest.py`)

---

## Goal

After this phase, `python -m seer_engine backtest` loads `bars` (one streamed `COPY ... TO STDOUT`,
cached as a pickle under `engine/.cache/` keyed by `count(*)` and `max(date)`), `universe` and
`fx_rates` from the database in one read-only transaction, runs the 81-run in-sample grid with wall
time logged per run and in total, selects, runs the selection once on in-sample, out-of-sample and
the full window, builds both SPY curves per window, the survivorship table and the gate, and writes
`<stem>.md`, `<stem>-equity.csv`, `<stem>-equity.svg`. It exits 0 whatever the verdict. It is tested
end to end against a synthetic Postgres schema in seconds; the real Neon run is phase 6.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.backtest.io` (`engine/src/seer_engine/backtest/io.py`, new; the only impure backtest module):
  - constants `CACHE_DIR = config.REPO_ROOT / "engine" / ".cache"`, `DIVIDENDS_CSV = config.REPO_ROOT / "engine" / "data" / "spy_dividends.csv"`, `BAR_COLUMNS`, `BARS_COPY_SQL`, `CACHE_GLOB = "bars-*.pkl"`
  - `class LoadError(RuntimeError)` — the database cannot back a backtest (no bars, inconsistent COPY)
  - `def load_market(conn, *, cache_dir: Path = CACHE_DIR, refresh: bool = False) -> tuple[Market, int]` (as in the index contract)
  - `def read_dividends(path: Path = DIVIDENDS_CSV) -> tuple[Dividend, ...]` (as in the index contract)
  - `def write_report(out_dir: Path, report: BacktestReport) -> list[Path]` (as in the index contract)
  - helpers, public so tests can reach them: `bars_fingerprint(conn) -> tuple[int, date | None]`, `cache_path(cache_dir, rows, max_date) -> Path`, `read_bars_frame(conn) -> pd.DataFrame`, `histories_from_frame(frame) -> dict[str, History]`, `read_intervals(conn) -> tuple[tuple[str, date, date | None], ...]`, `merge_intervals(rows) -> tuple[...]`, `read_fx(conn) -> tuple[tuple[date, Decimal], ...]`
- `seer_engine.commands.backtest` (`engine/src/seer_engine/commands/backtest.py`, new): `HELP`, `add_arguments`, `run` (command contract), plus `DEFAULT_OUT`, `WINDOW_NAMES = ("In-sample", "Out-of-sample", "Full window")` (the display labels phase 4 renders; this module is their one owner), `class BacktestError(RuntimeError)`, `@dataclass Windows`, `resolve_windows(...)`, `run_grid(...)`, `run_window(...)`, `never_fetched_members(...)`, `execute(...) -> BacktestReport`.
- CLI: `python -m seer_engine backtest [--out DIR] [--cache-dir DIR] [--refresh-cache] [--is-start D] [--oos-start D] [--end D] [--dividends PATH]`. **`--cache-dir` is an addition to the index's CLI line** (default `io.CACHE_DIR`); tests need it to keep the cache out of the repo, and it is harmless for phase 6.
- `.gitignore`: `engine/.cache/`.

**Signature changes:** none.

**Requires (from earlier phases), exactly as in the index's shared interface contract:**
- Phase 1: `seer_engine.strategies.base.History` constructible as `History(symbol=..., dates=..., open=..., high=..., low=..., close=..., volume=...)` with `dates` `datetime64[D]` and the rest `float64` arrays; `history_from_bars`; `seer_engine.strategies.a.STRATEGY_A` (with `prepare(history)` and the `Strategy` protocol), `STRATEGY_A_PARAMS`, `AParams.as_dict()`; `backtest/__init__.py` exists (docstring only); `test_strategy_purity.py` excludes `backtest/io.py` by name.
- Phase 2: `seer_engine.backtest.benchmark.Dividend`, `parse_dividends(text)`, `spy_curves(spy, start, end, initial_cash, dividends) -> (price, tr)`, `BenchmarkCurve.snapshots` / `.dividends_usd`.
- Phase 3: `seer_engine.backtest.market.Market(history=..., membership=..., fx=...)` and `Membership(intervals=...)` constructible by keyword; `Market.last_bar_date`, `Market.usd_idr_on` (raises `ValueError` when no fx row is on or before the date), `Market.spy()`, `Market.bar`; `Membership.members_on`; `seer_engine.backtest.runner.run_backtest(market, strategy, params, start, end, *, prepared=...)`, `RunResult` (fields `params`, `start`, `end`, `initial_cash`, `snapshots`), `survivorship(market, start, end)`.
- Phase 4: `seer_engine.backtest.metrics.run_metrics`, `curve_metrics`, `Metrics` (fields `total_return`, `profit_factor`, `max_drawdown`, `trades`); `seer_engine.backtest.tuning.grid`, `GridRow(params=, metrics=)`, `select`, `Selection` (`params`, `qualified`, `reason`), `gate(oos, spy_tr_oos)`, `Verdict` (`passed`, `sentence`), `IS_START`, `OOS_START`; `seer_engine.backtest.report.BacktestReport` (keyword-constructible with the index's fields), `WindowResult(name=, run=, spy_price=, spy_tr=)`, `render_markdown`, `equity_csv`, `equity_svg`, `report_stem(data_end) == f"{data_end.isoformat()}-strategy-a"`.

**Assumptions on phases 3 and 4 (checked by the reconciler, all hold; scratch-verified with phases 1–5 applied):**
- `Membership(intervals=...)` accepts raw per-index rows and merged intervals alike (phase 3 counts overlapping intervals per symbol, so a symbol is never duplicated). This phase merges the two indices' overlapping or touching intervals before constructing it, sorted by `(symbol, start)`; `members_on` and `survivorship` give the same answer either way, and the merge makes `market.membership.intervals` one row per membership spell (index Decisions "Membership input").
- `WindowResult.name` values: **settled by the reconciler** (index Decisions "Window names"): this phase passes `"In-sample"`, `"Out-of-sample"`, `"Full window"`, the labels phase 4 renders in headings and tables and asserts in `test_backtest_report.py`. `commands/backtest.WINDOW_NAMES` is the only place they are defined for real runs.
- `BacktestReport.never_fetched_members` = the number of symbols that are members at some point of the full window (`start <= end_window` and `end is None or end > start_window`) and have no bars at all. **This is its one definition** (`commands/backtest.never_fetched_members`); phase 3's `Membership.symbols()` is only a listing helper and is not used for the count (index Decisions "Never-fetched count").
- `BacktestReport.data_end` = the windows' end date (`--end`, default the last SPY bar), so the stem names the data the report used.

**Leaves alone (owned by others):** `strategies/*` (phase 1; phase 6 owns `STRATEGY_A_PARAMS`), `backtest/benchmark.py` + `engine/data/spy_dividends.csv` (phase 2), `backtest/market.py`, `backtest/runner.py` (phase 3), `backtest/metrics.py`, `tuning.py`, `report.py` (phase 4), `engine/package_readme.md`, `docs/ROADMAP.md`, `docs/backtests/*` (phase 6), `sim/*`, `cli.py`, every DB writer and migration.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/io.py` | create | read-only Neon loader (COPY + pickle cache), dividends reader, report writer |
| `engine/src/seer_engine/commands/backtest.py` | create | the `backtest` command (discovered by `cli.py`, which does not change) |
| `.gitignore` | modify (after line 15, `.pytest_cache/`) | add `engine/.cache/` |
| `engine/tests/test_backtest_io.py` | create | loader, cache, read-only, dividends, writer tests |
| `engine/tests/test_backtest_command.py` | create | discovery/defaults, preconditions, end-to-end on a synthetic schema, re-run determinism |

## Implementation Steps

### Step 0: The worktree's own venv
**File:** `engine/.venv` (not committed)
**Change:** The worktree has no venv (`ls engine/.venv` fails today). Never test with
`/home/miftah/seer/engine/.venv` — it is an editable install of main's tree. From the worktree root:
```bash
cd /home/miftah/.worktrees/seer/strategy-a-backtest
test -x engine/.venv/bin/python || python3 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'
docker start seer-pg
```
**Impact:** none on the tree.

### Step 1: Ignore the cache directory
**File:** `.gitignore:15` (insert after `.pytest_cache/`, before the blank line and `# misc`)
**Change:** add a commented line pair:
```gitignore

# backtest bars cache (seer_engine.backtest.io)
engine/.cache/
```
So the section reads:
```gitignore
# python
__pycache__/
*.pyc
.venv/
.pytest_cache/

# backtest bars cache (seer_engine.backtest.io)
engine/.cache/

# misc
.DS_Store
*.log
```
**Impact:** the ~180 MB pickle never shows in `git status`.

### Step 2: `backtest/io.py`
**File:** `engine/src/seer_engine/backtest/io.py:1` (new)
**Change:** the impure edge. Notes on choices:
- One transaction, `REPEATABLE READ, READ ONLY`, set as its first statement: the fingerprint, the
  COPY, `universe` and `fx_rates` all see one snapshot (a nightly run committing mid-load cannot make
  `count(*)` and the COPY disagree), and Postgres itself refuses any write (invariant 4). It always
  ends in `rollback()`.
- `pd.read_csv(..., float_precision="round_trip")`: the default "high" parser is not guaranteed
  correctly rounded; `round_trip` gives exactly `float("123.4567")`, which is what
  `history_from_bars` (P4's path, `float(Decimal)`) produces. That keeps backtest and nightly floats
  bit-identical (Decisions, "P4 identity").
- `na_filter=False`: a ticker spelled `NA` or `NAN` must stay a string.
- `SET LOCAL datestyle TO 'ISO, YMD'`: COPY's text format uses the session DateStyle; this pins ISO.
- The cache is the parsed frame (pickle, no pyarrow). Written to `*.tmp` then `os.replace`d, so a
  killed run never leaves a truncated `bars-*.pkl`; stale `bars-*.pkl` files are removed after a
  successful write. A cache that fails to load or has the wrong shape is re-downloaded, never fatal.
  The pickle is local and produced by this code only; it is never read from anywhere else.
- `histories_from_frame` returns a dict sorted by symbol (Python code-point order, not the database
  collation), so any iteration over `Market.history` is deterministic (invariant 5).

**Code:**
```python
"""Impure edge of the backtest: read the database once, read the vendored SPY dividends,
write the report files.

The only module in ``seer_engine.backtest`` that touches the database or the filesystem;
``test_strategy_purity.py`` skips it by name. Read-only: ``load_market`` runs one
``REPEATABLE READ, READ ONLY`` transaction and always ends it with a rollback.

Bars are loaded with one streamed ``COPY (SELECT ... ORDER BY symbol, date) TO STDOUT``
into a pandas frame, which is cached as a pickle under ``cache_dir`` named
``bars-<max(date)>-<count(*)>.pkl``. A cheap ``count(*), max(date)`` query decides whether
the cache is still valid, so a grid of runs never re-downloads the ~180 MB table.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from psycopg.pq import TransactionStatus

from seer_engine import config
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

log = logging.getLogger(__name__)

CACHE_DIR = config.REPO_ROOT / "engine" / ".cache"
DIVIDENDS_CSV = config.REPO_ROOT / "engine" / "data" / "spy_dividends.csv"

BAR_COLUMNS = ("symbol", "date", "open", "high", "low", "close", "volume")
FLOAT_COLUMNS = ("open", "high", "low", "close", "volume")
BARS_COPY_SQL = (
    "COPY (SELECT symbol, date, open, high, low, close, volume FROM bars "
    "ORDER BY symbol, date) TO STDOUT"
)
CACHE_GLOB = "bars-*.pkl"

Interval = tuple[str, date, date | None]


class LoadError(RuntimeError):
    """The database cannot back a backtest (no bars, or an inconsistent load)."""


# ---- database ------------------------------------------------------------------------------


def load_market(
    conn: psycopg.Connection,
    *,
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
) -> tuple[Market, int]:
    """(Market, number of bar rows) from ``bars``, ``universe`` and ``fx_rates``.

    ``conn`` must have autocommit off and no transaction in progress. Bars come from the
    cache in ``cache_dir`` when its name matches the table's ``count(*)`` and ``max(date)``
    (``refresh`` forces a re-download); universe and fx are always read fresh (small).
    Raises LoadError when ``bars`` is empty.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("load_market needs a connection with no transaction in progress")
    try:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        rows, max_date = bars_fingerprint(conn)
        if rows == 0 or max_date is None:
            raise LoadError("the bars table is empty; run `backfill` first")
        frame = _bars_frame(conn, Path(cache_dir), rows, max_date, refresh)
        intervals = read_intervals(conn)
        fx_rows = read_fx(conn)
    finally:
        conn.rollback()
    history = histories_from_frame(frame)
    market = Market(history=history, membership=Membership(intervals=intervals), fx=fx_rows)
    log.info(
        "market: %d bar rows through %s, %d symbols with bars, %d membership intervals, %d fx rows",
        rows,
        max_date,
        len(history),
        len(intervals),
        len(fx_rows),
    )
    return market, rows


def bars_fingerprint(conn: psycopg.Connection) -> tuple[int, date | None]:
    """(count(*), max(date)) of ``bars``: the cache key."""
    row = conn.execute("SELECT count(*), max(date) FROM bars").fetchone()
    return int(row[0]), row[1]


def cache_path(cache_dir: Path, rows: int, max_date: date) -> Path:
    return Path(cache_dir) / f"bars-{max_date.isoformat()}-{rows}.pkl"


def read_bars_frame(conn: psycopg.Connection) -> pd.DataFrame:
    """Every bar, ordered by (symbol, date), via one streamed COPY ... TO STDOUT.

    Columns: symbol (str), date (datetime64), open/high/low/close (float64, correctly
    rounded from the numeric text), volume (int64).
    """
    buf = BytesIO()
    with conn.cursor() as cur:
        cur.execute("SET LOCAL datestyle TO 'ISO, YMD'")
        with cur.copy(BARS_COPY_SQL) as copy:
            for chunk in copy:
                buf.write(chunk)
    if buf.tell() == 0:
        raise LoadError("COPY of bars returned no rows")
    buf.seek(0)
    frame = pd.read_csv(
        buf,
        sep="\t",
        header=None,
        names=list(BAR_COLUMNS),
        dtype={
            "symbol": str,
            "date": str,
            "open": np.float64,
            "high": np.float64,
            "low": np.float64,
            "close": np.float64,
            "volume": np.int64,
        },
        na_filter=False,
        float_precision="round_trip",
        engine="c",
    )
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    return frame


def read_intervals(conn: psycopg.Connection) -> tuple[Interval, ...]:
    """Membership intervals [start, end) per symbol, both indices merged."""
    rows = conn.execute(
        "SELECT symbol, start_date, end_date FROM universe ORDER BY symbol, start_date"
    ).fetchall()
    return merge_intervals((r[0], r[1], r[2]) for r in rows)


def merge_intervals(rows: Iterable[Interval]) -> tuple[Interval, ...]:
    """Union of overlapping or touching [start, end) intervals per symbol (end None = open),
    sorted by (symbol, start). Membership in either index counts once."""
    out: list[Interval] = []
    for symbol, start, end in sorted(rows, key=lambda r: (r[0], r[1])):
        if out and out[-1][0] == symbol:
            _, cur_start, cur_end = out[-1]
            if cur_end is None or start <= cur_end:
                merged_end = None if cur_end is None or end is None else max(cur_end, end)
                out[-1] = (symbol, cur_start, merged_end)
                continue
        out.append((symbol, start, end))
    return tuple(out)


def read_fx(conn: psycopg.Connection) -> tuple[tuple[date, Decimal], ...]:
    """Every (date, usd_idr) row, ascending, as 4-dp Decimals."""
    rows = conn.execute("SELECT date, usd_idr FROM fx_rates ORDER BY date").fetchall()
    return tuple((r[0], to_decimal(r[1])) for r in rows)


# ---- cache ---------------------------------------------------------------------------------


def _bars_frame(
    conn: psycopg.Connection, cache_dir: Path, rows: int, max_date: date, refresh: bool
) -> pd.DataFrame:
    path = cache_path(cache_dir, rows, max_date)
    if not refresh and path.is_file():
        cached = _read_cache(path, rows)
        if cached is not None:
            log.info("bars cache hit: %s", path)
            return cached
    log.info(
        "bars cache %s: streaming %d rows from the database",
        "refresh" if refresh else "miss",
        rows,
    )
    frame = read_bars_frame(conn)
    if len(frame) != rows:
        raise LoadError(f"COPY returned {len(frame)} bar rows but count(*) said {rows}")
    _write_cache(path, frame)
    return frame


def _read_cache(path: Path, rows: int) -> pd.DataFrame | None:
    try:
        frame = pd.read_pickle(path, compression=None)
    except Exception as e:  # noqa: BLE001 - a broken cache is re-downloaded, never fatal
        log.warning("bars cache %s unreadable (%s: %s); re-downloading", path, type(e).__name__, e)
        return None
    if (
        not isinstance(frame, pd.DataFrame)
        or len(frame) != rows
        or tuple(frame.columns) != BAR_COLUMNS
    ):
        log.warning("bars cache %s has the wrong shape; re-downloading", path)
        return None
    return frame


def _write_cache(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    frame.to_pickle(tmp, compression=None)
    os.replace(tmp, path)
    log.info("bars cache written: %s", path)
    for old in sorted(path.parent.glob(CACHE_GLOB)):
        if old != path:
            old.unlink(missing_ok=True)
            log.info("removed stale bars cache %s", old.name)


# ---- frame -> histories --------------------------------------------------------------------


def histories_from_frame(frame: pd.DataFrame) -> dict[str, History]:
    """One History per symbol (float64 arrays, datetime64[D] dates), sorted by symbol.

    ``frame`` must be ordered by (symbol, date) as the COPY returns it. Raises LoadError
    when a symbol's rows are not contiguous or its dates are not strictly ascending.
    """
    if len(frame) == 0:
        return {}
    symbols = frame["symbol"].to_numpy(dtype=object)
    days = frame["date"].to_numpy().astype("datetime64[D]")
    cols = {c: np.ascontiguousarray(frame[c].to_numpy(dtype=np.float64)) for c in FLOAT_COLUMNS}
    starts = np.concatenate(([0], np.flatnonzero(symbols[1:] != symbols[:-1]) + 1))
    ends = np.append(starts[1:], len(symbols))
    out: dict[str, History] = {}
    for s, e in zip(starts.tolist(), ends.tolist()):
        symbol = str(symbols[s])
        if symbol in out:
            raise LoadError(f"bars for {symbol} are not contiguous; expected ORDER BY symbol, date")
        d = days[s:e]
        if len(d) > 1 and not bool(np.all(d[1:] > d[:-1])):
            raise LoadError(f"bars for {symbol} are not strictly ascending by date")
        out[symbol] = History(
            symbol=symbol,
            dates=d,
            open=cols["open"][s:e],
            high=cols["high"][s:e],
            low=cols["low"][s:e],
            close=cols["close"][s:e],
            volume=cols["volume"][s:e],
        )
    return dict(sorted(out.items()))


# ---- files ---------------------------------------------------------------------------------


def read_dividends(path: Path = DIVIDENDS_CSV) -> tuple[Dividend, ...]:
    """The vendored SPY dividends (``ex_date,amount_usd``), parsed by benchmark.parse_dividends."""
    return parse_dividends(Path(path).read_text(encoding="utf-8"))


def write_report(out_dir: Path, report: BacktestReport) -> list[Path]:
    """Write <stem>.md, <stem>-equity.csv, <stem>-equity.svg into ``out_dir`` (created if
    needed) with LF line endings; return the paths in that order. All three are rendered
    before any is written, so a render error leaves no partial set."""
    out_dir = Path(out_dir)
    stem = report_stem(report.data_end)
    files = (
        (f"{stem}.md", render_markdown(report)),
        (f"{stem}-equity.csv", equity_csv(report)),
        (f"{stem}-equity.svg", equity_svg(report)),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, text in files:
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths
```
**Impact:** new module; imports psycopg, so it must stay out of the purity glob (phase 1's test
excludes `io.py` by name). Nothing imports it except the command and its tests.

### Step 3: `commands/backtest.py`
**File:** `engine/src/seer_engine/commands/backtest.py:1` (new)
**Change:** the command. Notes:
- One `contextlib.closing(db.connect())` used only for `load_market`, then closed before any
  computation (the grid runs for minutes; no idle Neon connection held). No `db.transaction`.
- Preconditions (exit 2, via `BacktestError` / `io.LoadError` / missing dividends file): empty
  `bars`, no SPY bars, `--is-start`/`--oos-start`/`--end` not NYSE sessions, not
  `is_start < oos_start <= end`, `--end` after the last SPY bar, no `fx_rates` row on or before
  `--is-start`. Anything else raised propagates to `cli.main` (exit 1).
- `--dry-run` changes nothing (the command never writes to the database); it is logged.
- Wall time uses `time.perf_counter()` — allowed here, this module is impure; nothing time-derived
  reaches the report.
- `strategy_a.STRATEGY_A_PARAMS` is read at run time through the module so the value phase 6 freezes
  is what the report records.

**Code:**
```python
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
```
**Impact:** `cli.discover()` now finds `backtest` (no edit to `cli.py`). `discover()` imports every
command module, so a broken import in any backtest module now fails `python -m seer_engine` for all
commands — the e2e test catches that.

### Step 4: `engine/tests/test_backtest_io.py`
**File:** `engine/tests/test_backtest_io.py:1` (new)
**Change:** loader, cache, read-only, dividends and writer tests. DB tests use `pg`.
**Code:**
```python
"""backtest.io: the read-only Neon loader (one COPY + pickle cache), dividends, report writer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pandas as pd
import psycopg
import pytest
from psycopg.pq import TransactionStatus

from seer_engine import bars, db, fx
from seer_engine.backtest import io as bio
from seer_engine.backtest.benchmark import Dividend
from seer_engine.prices import Bar

D1, D2, D3, D4 = date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)
Y2020, Y2021 = date(2020, 1, 2), date(2021, 1, 4)

BARS = [
    ("AAPL", D1, "100.1", "101.2345", "99.5", "100.9999", 1_000_000),
    ("AAPL", D2, "101", "102", "100", "1234.5678", 1_100_000),
    ("AAPL", D3, "102", "103", "101", "102.0001", 1_200_000),
    ("BRK.B", D2, "450", "455", "449", "452.25", 3_000_000),
    ("NA", D1, "10", "11", "9", "10.5", 500),  # 'NA' would be NaN under pandas' default NA parsing
    ("SPY", D1, "500", "505", "499", "501.1", 50_000_000),
    ("SPY", D2, "501", "506", "500", "502.2", 51_000_000),
    ("SPY", D3, "502", "507", "501", "503.3", 52_000_000),
]
UNIVERSE = [  # (symbol, index_id, start, end-exclusive | None)
    ("AAPL", "SP500", Y2020, None),
    ("AAPL", "NDX", Y2021, None),
    ("BRK.B", "SP500", Y2020, D2),
    ("MSFT", "SP500", Y2020, None),  # a member with no bars
    ("MSFT", "NDX", Y2020, D1),
]
FX = [(D1, "16000"), (D3, "16100.5")]


def seed_bars(conn, rows):
    with db.transaction(conn, False):
        bars.upsert_bars(conn, [bars.make_bar(*r) for r in rows])


def seed_universe(conn, rows):
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, %s, %s)",
                [(s, i, a, b, s) for s, i, a, b in rows],
            )


def seed_fx(conn, rows):
    with db.transaction(conn, False):
        fx.upsert_fx(conn, rows)


@pytest.fixture
def seeded(pg):
    seed_bars(pg, BARS)
    seed_universe(pg, UNIVERSE)
    seed_fx(pg, FX)
    return pg


def test_load_market_builds_histories_membership_and_fx(seeded, tmp_path):
    market, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == len(BARS)
    assert list(market.history) == ["AAPL", "BRK.B", "NA", "SPY"]

    h = market.history["AAPL"]
    assert h.symbol == "AAPL"
    assert h.dates.dtype == np.dtype("datetime64[D]")
    assert h.dates.tolist() == [D1, D2, D3]
    assert h.close.dtype == np.float64 and h.volume.dtype == np.float64
    assert h.close.tolist() == [float("100.9999"), float("1234.5678"), float("102.0001")]
    assert h.high.tolist()[0] == float("101.2345")
    assert h.volume.tolist() == [1_000_000.0, 1_100_000.0, 1_200_000.0]
    assert market.history["NA"].close.tolist() == [10.5]
    assert market.bar("AAPL", D2) == Bar(
        "AAPL", D2, Decimal("101.0000"), Decimal("102.0000"), Decimal("100.0000"),
        Decimal("1234.5678"), 1_100_000,
    )

    assert market.membership.intervals == (
        ("AAPL", Y2020, None),
        ("BRK.B", Y2020, D2),
        ("MSFT", Y2020, None),
    )
    assert market.membership.members_on(D1) == frozenset({"AAPL", "BRK.B", "MSFT"})
    assert market.membership.members_on(D2) == frozenset({"AAPL", "MSFT"})  # end is exclusive

    assert market.fx == ((D1, Decimal("16000.0000")), (D3, Decimal("16100.5000")))
    assert market.last_bar_date("SPY") == D3
    assert seeded.info.transaction_status == TransactionStatus.IDLE


def test_bars_are_loaded_with_one_streamed_copy(seeded, tmp_path, monkeypatch):
    statements = []
    real_copy = psycopg.Cursor.copy

    def spy_copy(self, statement, *args, **kwargs):
        statements.append(str(statement))
        return real_copy(self, statement, *args, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "copy", spy_copy)
    bio.load_market(seeded, cache_dir=tmp_path)
    assert statements == [bio.BARS_COPY_SQL]


def test_load_market_transaction_is_read_only(seeded, tmp_path, monkeypatch):
    def writing_read_fx(conn):
        conn.execute("INSERT INTO fx_rates (date, usd_idr) VALUES ('2026-10-01', 1)")
        return ()

    monkeypatch.setattr(bio, "read_fx", writing_read_fx)
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        bio.load_market(seeded, cache_dir=tmp_path)
    assert seeded.info.transaction_status == TransactionStatus.IDLE
    assert seeded.execute("SELECT count(*) FROM fx_rates").fetchone()[0] == len(FX)
    seeded.rollback()


def test_load_market_refuses_a_connection_mid_transaction(seeded, tmp_path):
    seeded.execute("SELECT 1")
    with pytest.raises(ValueError, match="no transaction in progress"):
        bio.load_market(seeded, cache_dir=tmp_path)
    seeded.rollback()


def test_cache_is_written_then_reused_without_a_copy(seeded, tmp_path, monkeypatch):
    first, _ = bio.load_market(seeded, cache_dir=tmp_path)
    expected = tmp_path / f"bars-{D3.isoformat()}-{len(BARS)}.pkl"
    assert sorted(tmp_path.iterdir()) == [expected]

    def no_copy(conn):
        raise AssertionError("the cache should have been used")

    monkeypatch.setattr(bio, "read_bars_frame", no_copy)
    second, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == len(BARS)
    assert list(second.history) == list(first.history)
    for symbol, h in first.history.items():
        g = second.history[symbol]
        for field in ("dates", "open", "high", "low", "close", "volume"):
            assert np.array_equal(getattr(h, field), getattr(g, field)), (symbol, field)


def test_changed_fingerprint_invalidates_the_cache(seeded, tmp_path):
    bio.load_market(seeded, cache_dir=tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == [f"bars-{D3.isoformat()}-8.pkl"]

    seed_bars(seeded, [("MSFT", D1, "400", "401", "399", "400.5", 9)])  # same max(date), +1 row
    market, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == 9 and "MSFT" in market.history
    assert [p.name for p in tmp_path.iterdir()] == [f"bars-{D3.isoformat()}-9.pkl"]

    seed_bars(seeded, [("AAPL", D4, "103", "104", "102", "103.5", 7)])  # new max(date)
    market, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == 10 and market.history["AAPL"].dates.tolist() == [D1, D2, D3, D4]
    assert [p.name for p in tmp_path.iterdir()] == [f"bars-{D4.isoformat()}-10.pkl"]


def test_refresh_rereads_a_valid_cache(seeded, tmp_path, monkeypatch):
    bio.load_market(seeded, cache_dir=tmp_path)
    calls = []
    real = bio.read_bars_frame

    def counting(conn):
        calls.append(1)
        return real(conn)

    monkeypatch.setattr(bio, "read_bars_frame", counting)
    bio.load_market(seeded, cache_dir=tmp_path)
    assert calls == []
    bio.load_market(seeded, cache_dir=tmp_path, refresh=True)
    assert calls == [1]


def test_corrupt_cache_is_replaced(seeded, tmp_path):
    path = tmp_path / f"bars-{D3.isoformat()}-{len(BARS)}.pkl"
    path.write_bytes(b"not a pickle")
    market, _ = bio.load_market(seeded, cache_dir=tmp_path)
    assert "AAPL" in market.history
    assert len(pd.read_pickle(path, compression=None)) == len(BARS)


def test_empty_bars_is_a_load_error(pg, tmp_path):
    with pytest.raises(bio.LoadError, match="bars table is empty"):
        bio.load_market(pg, cache_dir=tmp_path)
    assert pg.info.transaction_status == TransactionStatus.IDLE
    assert list(tmp_path.iterdir()) == []


def test_merge_intervals_unions_indices_per_symbol():
    a, b, c, d = date(2016, 1, 4), date(2017, 1, 3), date(2018, 1, 2), date(2019, 1, 2)
    rows = [
        ("X", b, d),
        ("X", a, c),  # overlaps the first
        ("Y", a, b),
        ("Y", b, c),  # touches: one interval
        ("Y", d, None),  # gap, then open-ended
        ("Z", a, None),
        ("Z", b, c),  # inside an open interval
    ]
    assert bio.merge_intervals(rows) == (
        ("X", a, d),
        ("Y", a, c),
        ("Y", d, None),
        ("Z", a, None),
    )


def test_histories_from_frame_rejects_unsorted_dates():
    frame = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "date": pd.to_datetime(["2026-09-29", "2026-09-28"], format="%Y-%m-%d"),
            "open": [1.0, 1.0],
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
            "volume": [1, 1],
        }
    )
    with pytest.raises(bio.LoadError, match="strictly ascending"):
        bio.histories_from_frame(frame)


def test_histories_from_frame_rejects_non_contiguous_symbols():
    frame = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "AAA"],
            "date": pd.to_datetime(["2026-09-28", "2026-09-28", "2026-09-29"], format="%Y-%m-%d"),
            "open": [1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0],
            "volume": [1, 1, 1],
        }
    )
    with pytest.raises(bio.LoadError, match="not contiguous"):
        bio.histories_from_frame(frame)


def test_read_dividends(tmp_path):
    path = tmp_path / "div.csv"
    path.write_text("ex_date,amount_usd\n2026-03-20,1.7\n2026-06-20,1.75\n", encoding="utf-8")
    assert bio.read_dividends(path) == (
        Dividend(date(2026, 3, 20), Decimal("1.7")),
        Dividend(date(2026, 6, 20), Decimal("1.75")),
    )


def test_write_report_writes_three_files_with_lf(tmp_path, monkeypatch):
    monkeypatch.setattr(bio, "render_markdown", lambda r: "# report\nline\n")
    monkeypatch.setattr(bio, "equity_csv", lambda r: "date,strategy\n2026-10-02,1\n")
    monkeypatch.setattr(bio, "equity_svg", lambda r: "<svg/>\n")
    report = SimpleNamespace(data_end=date(2026, 10, 2))
    out = tmp_path / "nested" / "backtests"
    paths = bio.write_report(out, report)
    assert paths == [
        out / "2026-10-02-strategy-a.md",
        out / "2026-10-02-strategy-a-equity.csv",
        out / "2026-10-02-strategy-a-equity.svg",
    ]
    assert paths[0].read_bytes() == b"# report\nline\n"
    assert paths[1].read_bytes() == b"date,strategy\n2026-10-02,1\n"
    assert paths[2].read_bytes() == b"<svg/>\n"


def test_write_report_renders_everything_before_writing(tmp_path, monkeypatch):
    def boom(report):
        raise RuntimeError("svg failed")

    monkeypatch.setattr(bio, "render_markdown", lambda r: "md")
    monkeypatch.setattr(bio, "equity_csv", lambda r: "csv")
    monkeypatch.setattr(bio, "equity_svg", boom)
    with pytest.raises(RuntimeError, match="svg failed"):
        bio.write_report(tmp_path / "out", SimpleNamespace(data_end=date(2026, 10, 2)))
    assert not (tmp_path / "out").exists()
```
**Impact:** new tests only.

### Step 5: `engine/tests/test_backtest_command.py`
**File:** `engine/tests/test_backtest_command.py:1` (new)
**Change:** discovery and defaults (no DB), preconditions (exit 2), and one end-to-end test that runs
the command twice on a synthetic schema: 6 traded members + SPY + `OLD` (member whose bars end
mid-OOS) + `GONE` (member with no bars), 250 sessions from 2024-01-02 (200 warm-up, 25 IS, 25 OOS),
one SPY dividend in OOS. The second run must hit the cache (the COPY is patched to fail) and write
byte-identical files. The command is pointed at the test schema with
`DATABASE_URL_UNPOOLED = pg_schema.url`, as `test_migrate.py::test_cli_dry_run_against_test_db` does.
Prices follow a rising sawtooth (two −4 % days every 12 sessions) so RSI(2) setups occur above the
SMA200 with dollar volume ≈ 10⁸; the test asserts structure, not a trade count.
**Code:**
```python
"""`backtest` command: discovery, preconditions, and an end-to-end run on a synthetic schema."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, cli, config, dates, db, fx
from seer_engine.backtest import io as bio
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.tuning import IS_START, OOS_START, grid
from seer_engine.commands import backtest as cmd
from seer_engine.strategies import a as strategy_a
from seer_engine.strategies.base import history_from_bars

SESSIONS = dates.sessions(date(2024, 1, 2), date(2025, 3, 31))[:250]
IS_S = SESSIONS[200]  # data_date SESSIONS[199] is the 200th bar
OOS_S = SESSIONS[225]
END = SESSIONS[249]
OLD_LAST = SESSIONS[230]  # OLD's bars end mid-OOS (delisted while a member)
DIVIDEND_DAY = SESSIONS[235]
TRADED = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")
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


def synthetic_bars() -> list:
    rows = []
    for k, symbol in enumerate(TRADED):
        rows += [bars.make_bar(symbol, d, *v) for d, v in zip(SESSIONS, ohlcv(k, len(SESSIONS)))]
    rows += [bars.make_bar("SPY", d, *v) for d, v in zip(SESSIONS, ohlcv(6, len(SESSIONS)))]
    old_sessions = [d for d in SESSIONS if d <= OLD_LAST]
    rows += [bars.make_bar("OLD", d, *v) for d, v in zip(old_sessions, ohlcv(7, len(old_sessions)))]
    return rows


EXPECTED_ROWS = 7 * len(SESSIONS) + len([d for d in SESSIONS if d <= OLD_LAST])


def seed(conn, *, with_bars=True, fx_rows=((SESSIONS[0], "16000"), (SESSIONS[210], "16250.5"))):
    with db.transaction(conn, False):
        if with_bars:
            bars.upsert_bars(conn, synthetic_bars())
        with conn.cursor() as cur:
            members = [(s, "SP500") for s in (*TRADED, "OLD", "GONE")] + [("AAA", "NDX")]
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, NULL, %s)",
                [(s, i, LONG_AGO, s) for s, i in members],
            )
        fx.upsert_fx(conn, list(fx_rows))


def write_dividends(tmp_path):
    path = tmp_path / "spy_dividends.csv"
    path.write_text(f"ex_date,amount_usd\n{DIVIDEND_DAY.isoformat()},0.75\n", encoding="utf-8")
    return path


def argv(tmp_path, out_name="out", *extra):
    return [
        "backtest",
        "--out", str(tmp_path / out_name),
        "--cache-dir", str(tmp_path / "cache"),
        "--is-start", IS_S.isoformat(),
        "--oos-start", OOS_S.isoformat(),
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


# ---- no database -----------------------------------------------------------------------------


def test_discovered_with_defaults():
    assert "backtest" in cli.discover()
    args = cli.build_parser().parse_args(["backtest"])
    assert args._run is cmd.run
    assert args.out == config.REPO_ROOT / "docs" / "backtests"
    assert args.cache_dir == bio.CACHE_DIR == config.REPO_ROOT / "engine" / ".cache"
    assert args.dividends == bio.DIVIDENDS_CSV == config.REPO_ROOT / "engine" / "data" / "spy_dividends.csv"
    assert (args.is_start, args.oos_start, args.end) == (IS_START, OOS_START, None)
    assert args.refresh_cache is False
    assert cmd.HELP


def test_bad_date_argument_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["backtest", "--end", "2026-13-01"])
    assert exc.value.code == 2


def test_never_fetched_members_counts_window_members_without_bars():
    aaa = history_from_bars("AAA", [bars.make_bar("AAA", date(2024, 1, 2), 1, 1, 1, 1, 1)])
    market = Market(
        history={"AAA": aaa},
        membership=Membership(
            intervals=(
                ("AAA", date(2015, 1, 2), None),  # has bars
                ("GONE", date(2015, 1, 2), date(2020, 1, 2)),  # left before the window
                ("LATE", date(2025, 1, 2), None),  # joined after the window
                ("MISS", date(2019, 1, 2), date(2024, 6, 3)),  # overlaps, no bars
            )
        ),
        fx=(),
    )
    assert cmd.never_fetched_members(market, date(2021, 1, 4), date(2024, 12, 31)) == 1


# ---- preconditions (exit 2, nothing written) -----------------------------------------------


def test_empty_bars_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, with_bars=False)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "extra",
    [
        ["--end", dates.next_session(END).isoformat()],  # after the last SPY bar
        ["--oos-start", date(2024, 12, 7).isoformat()],  # a Saturday
        ["--oos-start", IS_S.isoformat()],  # is_start == oos_start
    ],
)
def test_bad_windows_exit_2(pg, point_cli_at, tmp_path, extra):
    seed(pg)
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path, "out", *extra)) == 2
    assert not (tmp_path / "out").exists()


def test_no_fx_before_is_start_exits_2(pg, point_cli_at, tmp_path):
    seed(pg, fx_rows=((SESSIONS[210], "16250.5"),))
    write_dividends(tmp_path)
    assert cli.main(argv(tmp_path)) == 2


def test_missing_dividends_file_exits_2(pg, point_cli_at, tmp_path):
    seed(pg)
    assert cli.main(argv(tmp_path)) == 2  # no spy_dividends.csv written


# ---- end to end ------------------------------------------------------------------------------


def test_end_to_end_report_verdict_read_only_and_byte_identical_rerun(
    pg, point_cli_at, tmp_path, monkeypatch, caplog
):
    seed(pg)
    write_dividends(tmp_path)
    caplog.set_level(logging.INFO)
    captured = []
    real_write = bio.write_report

    def capturing_write(out_dir, report):
        captured.append(report)
        return real_write(out_dir, report)

    monkeypatch.setattr(bio, "write_report", capturing_write)
    before = checksums(pg)

    assert cli.main(argv(tmp_path, "out1")) == 0

    assert checksums(pg) == before  # read-only
    stem = f"{END.isoformat()}-strategy-a"
    names = [f"{stem}.md", f"{stem}-equity.csv", f"{stem}-equity.svg"]
    assert sorted(p.name for p in (tmp_path / "out1").iterdir()) == sorted(names)
    assert [p.name for p in (tmp_path / "cache").iterdir()] == [
        f"bars-{END.isoformat()}-{EXPECTED_ROWS}.pkl"
    ]

    [report] = captured
    assert report.data_end == END
    assert report.bars_rows == EXPECTED_ROWS
    assert report.symbols_with_bars == len(TRADED) + 2  # + SPY + OLD
    assert [r.params for r in report.grid_rows] == list(grid())
    assert report.selection.params in [r.params for r in report.grid_rows]
    assert report.frozen_params == strategy_a.STRATEGY_A_PARAMS
    assert report.never_fetched_members == 1  # GONE
    windows = (report.in_sample, report.out_of_sample, report.full)
    assert [w.name for w in windows] == ["In-sample", "Out-of-sample", "Full window"] == list(cmd.WINDOW_NAMES)
    assert [(w.run.start, w.run.end) for w in windows] == [
        (IS_S, dates.prev_session(OOS_S)),
        (OOS_S, END),
        (IS_S, END),
    ]
    for w in windows:
        assert w.run.params == report.selection.params
        assert w.spy_price.snapshots[0].date == w.spy_tr.snapshots[0].date == w.run.snapshots[0].date
        assert w.spy_price.snapshots[-1].date == w.spy_tr.snapshots[-1].date == w.run.end
    assert report.in_sample.spy_tr.dividends_usd == Decimal("0")
    assert report.out_of_sample.spy_tr.dividends_usd > 0
    assert report.verdict.sentence in (tmp_path / "out1" / f"{stem}.md").read_text(encoding="utf-8")

    messages = [r.getMessage() for r in caplog.records]
    assert sum(1 for m in messages if m.startswith("grid ") and f"/{len(grid())} " in m) == len(grid())
    assert any(m.startswith(f"grid: {len(grid())} runs on ") for m in messages)
    assert any(m.startswith("gate ") and report.verdict.sentence in m for m in messages)
    assert any("STRATEGY_A_PARAMS" in m for m in messages)

    # Second run: the cache must be used (no COPY) and every file byte-identical.
    def no_copy(conn):
        raise AssertionError("the bars cache should have been used")

    monkeypatch.setattr(bio, "read_bars_frame", no_copy)
    caplog.clear()
    assert cli.main(argv(tmp_path, "out2")) == 0
    assert any(r.getMessage().startswith("bars cache hit") for r in caplog.records)
    for name in names:
        assert (tmp_path / "out2" / name).read_bytes() == (tmp_path / "out1" / name).read_bytes(), name
    assert captured[1].selection == captured[0].selection
    assert checksums(pg) == before
```
**Impact:** new tests only. Runtime: the two full runs are 2 × (81 + 3) backtests over ≤ 50
sessions and 7 symbols, plus one `prepare`; expected well under 10 s. If it is slower, shorten IS/OOS
to 15 sessions each (keep `SESSIONS[200]` as the IS start).

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/strategy-a-backtest && engine/.venv/bin/python -c "import seer_engine.commands.backtest, seer_engine.backtest.io"`
**Tests:**
```bash
cd /home/miftah/.worktrees/seer/strategy-a-backtest
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_backtest_io.py engine/tests/test_backtest_command.py -q   # 25 passed (15 + 10)
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs   # full suite: 595 passed, 0 skipped
engine/.venv/bin/python -m seer_engine --help | grep backtest
git status --short   # engine/.cache/ must not appear
```
**Manual check:** `engine/.venv/bin/python -m seer_engine backtest --help` lists every flag with its
default. Do **not** run it against Neon here; that is phase 6.
**Exit criteria:** `load_market` on a seeded schema returns the right `Market` from one streamed
COPY inside a read-only transaction; the cache is written to and reused from `cache_dir` keyed by
`count(*)` and `max(date)`, and a changed fingerprint or `--refresh-cache` re-downloads; the command,
pointed at a synthetic schema with short windows, writes the three report files, logs 81 timed grid
runs plus the total, logs the gate verdict and the `STRATEGY_A_PARAMS` comparison, exits 0, writes
nothing to the database, and a re-run from the cache is byte-identical; `backtest` is in
`cli.discover()`; full suite green: **595 passed** (570 after phase 4 + 25), 0 skipped; `engine/.cache/` ignored.

## Handoffs

- **Phase 6 (R4, R6):** run `SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine backtest`
  from the worktree (defaults write to `docs/backtests/`); read the grid's total wall time from the log
  against the 60-minute threshold in **Decisions → Grid runtime** (above it, phase 6 records
  the time and leaves a parallelization follow-up; it does not parallelize `run_grid` itself); freeze `STRATEGY_A_PARAMS` when the log
  warns that it differs, then re-run (the cache makes the re-run cheap) and confirm byte-identical files.
  Document the command, `--cache-dir`, the cache file naming and `engine/.cache/` in
  `engine/package_readme.md`.
- **Phase 3 (R2):** reconciled. `Membership` accepts the merged intervals `io.read_intervals` returns;
  phase 3 exposes no never-fetched counter (only `Membership.symbols()`), so
  `commands/backtest.never_fetched_members` stays the single definition.
- **Phase 4 (R5):** `WindowResult.name` values are `"In-sample"`, `"Out-of-sample"`, `"Full window"`
  (`commands/backtest.WINDOW_NAMES`), exactly the labels phase 4's renderer and tests use (reconciled).
- Not done here, deliberately: no readme or ROADMAP text, no `docs/backtests/*` files, no change to any
  pure module. If the end-to-end test exposes a bug in a pure module, fix it in that module and name the
  bug in this phase's commit message.

## Rollback

`git revert` this phase's commit: it only adds `backtest/io.py`, `commands/backtest.py`, two test
files and two `.gitignore` lines; no database state is created. Delete `engine/.cache/` locally if
wanted.
