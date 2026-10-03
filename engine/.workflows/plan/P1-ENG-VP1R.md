> Adopted from `ENGINE_DATA_PIPELINE_PLAN.md` phase 1. Source: `.workflows/plan/engine-data-pipeline/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Engine foundation: package, migration 002, dates, DB helpers, demo purge

**Plan set:** `ENGINE_DATA_PIPELINE_PLAN.md`
**Analysis:** `20261003-121931-K7P2_code_analyzer.md`
**Spec:** `docs/handover/2026-10-03-data-pipeline.md` (§3 decisions, §6 acceptance)
**Satisfies:** R2 (the `universe` table), R4 (idempotent write helpers), R5 (demo purge), R6 (test infrastructure, date tests, dry-run plumbing). These are the user-facing properties every later writer inherits from this phase.
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/` (Python package `seer_engine`), `db/migrations/`

---

## Goal

After this phase `engine/` is an installable Python 3.11 package (`seer_engine`, src layout) with a command-discovering CLI, a `migrate` command that is the exact twin of `web/scripts/migrate.mjs`, and migration `002_engine.sql` (universe, split_adjustments, backfill_log, one-real-run-per-session index). Every shared helper that phases 2–4 build on exists, as in the index's shared interface contract: NYSE date logic, the transaction/dry-run helper, idempotent `bars`/`fx_rates` upserts, the `runs` lifecycle, the demo purge, and universe queries. All of it is covered by tests that run against a real Postgres 16 in Docker.

**Prototype status.** Every file below was written and run in a scratch copy of the repo before this plan was written (Python 3.11.0, psycopg 3.3.6, pandas 3.0.6, pandas_market_calendars 5.4.0, yfinance 1.7.0, pytest 9.1.1, postgres:16 on port 55432): **101 passed in 10s, 0 skipped**. With `PG_TEST_URL` unset, 66 pass and 35 DB tests skip with the documented reason. The code blocks are those exact files.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Everything listed in the index's "Shared interface contract" is implemented **with the same names, signatures and semantics**. Additions are marked *(add)*. They are optional for consumers, and none of them changes a contract signature.

**Deletes:** nothing.
**Renames:** nothing.

**Creates:**

| Module | Symbols |
|---|---|
| `engine/pyproject.toml` | dist `seer-engine` 0.1.0, `requires-python >=3.11`, deps exactly as the contract (`psycopg[binary]>=3.2, pandas>=2.2, pandas_market_calendars>=5.0, yfinance>=1.0, requests>=2.32, python-dotenv>=1.0`), extra `dev = [pytest>=8]`, console script `seer-engine` *(add)*, `[tool.pytest.ini_options] testpaths=["tests"]` |
| `seer_engine/__init__.py` | `__version__ = "0.1.0"` |
| `seer_engine/__main__.py` | `python -m seer_engine` → `raise SystemExit(cli.main())` |
| `seer_engine/cli.py` | `main(argv=None) -> int`, `discover() -> dict[str, ModuleType]` *(add)*, `build_parser(modules=None)` *(add)*, `setup_logging(verbose: int)` *(add)*. Global flags `--dry-run` and `-v/--verbose` (count) are accepted **before or after** the command name. Exit codes: `run()`'s return value; uncaught exception → 1; `config.ConfigError` → 2; Ctrl-C → 130 |
| command module protocol | `HELP: str`, `add_arguments(p: argparse.ArgumentParser) -> None` (optional), `run(args: argparse.Namespace) -> int`. `args.dry_run: bool` and `args.verbose: int` are always present. Modules whose names start with `_` are ignored |
| `seer_engine/config.py` | `load_env() -> Path\|None`, `get(name) -> str\|None` (empty counts as unset; lazily calls `load_env()` once), `require(name) -> str`, `class ConfigError(RuntimeError)`, `REPO_ROOT: Path` *(add)*, `env_file() -> Path` *(add)*. Env file: `$SEER_ENV_FILE`, otherwise `<repo>/.env.local`. It never overrides variables that are already set |
| `seer_engine/db.py` | `connect(url: str\|None = None) -> psycopg.Connection` (default `DATABASE_URL_UNPOOLED`, `autocommit=False`, `connect_timeout=15`), `transaction(conn, dry_run: bool)` context manager (commits; rolls back on exception; with `dry_run`, rolls back after running the block in full), `CONNECT_TIMEOUT_S = 15` *(add)* |
| `seer_engine/http.py` | `get_json(url, params=None, *, retries=3, backoff=5.0, timeout=30) -> dict`: retries connection errors, timeouts, 429 and 5xx with exponential backoff (`backoff·2^n`; a longer numeric `Retry-After` wins); any other non-200 raises at once. `redact(url) -> str`: masks `apiKey=`, `api_key=`, `key=`, `token=`, `access_token=`. `class HttpError(RuntimeError)` with `.status: int\|None` *(add)*. Test seams *(add)*: module attributes `_session` (has `.get`) and `_sleep` |
| `seer_engine/dates.py` | `sessions(start, end) -> list[date]` (inclusive), `is_session(d)`, `next_session(d)` (strictly after), `prev_session(d)` (strictly before), `session_close_utc(d) -> datetime` (UTC; raises `ValueError` on a non-session), `last_completed_session(now_utc, settle=timedelta(hours=1)) -> date` (raises `ValueError` for naive datetimes), `@dataclass(frozen=True, slots=True) RunDates(data_date, session_date)`, `run_dates(now_utc=None, settle=DEFAULT_SETTLE) -> RunDates` (with `None`, uses the current time *(add)*), `DEFAULT_SETTLE` *(add)*. All functions raise `TypeError` when a `datetime` is passed where a `date` is expected |
| `seer_engine/demo.py` | `purge_demo(conn) -> bool`, `purge_demo_if_needed(conn, dry_run) -> bool` (in its own transaction; under dry-run it returns True for "would purge" and logs a warning), `has_demo(conn) -> bool` *(add)*, `DEMO_TABLES` *(add)* |
| `seer_engine/universe.py` | `BENCHMARK = "SPY"`, `members_on(conn, d) -> set[str]`, `symbols_for_bars(conn, d, grace_days=30) -> set[str]` (∪ SPY), `all_symbols(conn, since) -> list[str]` (∪ SPY, sorted). The SQL predicates are exactly the ones in the phase scope |
| `seer_engine/bars.py` | `@dataclass(frozen=True, slots=True) Bar(symbol, date, open, high, low, close, volume)`, `make_bar(symbol, d, o, h, l, c, v) -> Bar` (rounds half-up to 4 dp; floats go through their shortest repr; `int` volume; rejects NaN/inf, negative volume, and a datetime passed as `d`), `upsert_bars(conn, bars) -> int`, `latest_bar_date(conn, symbol) -> date\|None`, `delete_bars_on(conn, d) -> int`, `to_decimal(x) -> Decimal` *(add)*, `to_volume(v) -> int` *(add)*, `PRICE_QUANTUM` *(add)* |
| `seer_engine/fx.py` | `fetch_latest() -> tuple[date, Decimal]`, `fetch_range(start, end) -> list[tuple[date, Decimal]]` (one request per calendar year, sorted, deduplicated), `upsert_fx(conn, rows) -> int` (accepts Decimal/float/str rates, rounds to 4 dp), `FRANKFURTER = "https://api.frankfurter.dev/v1"` *(add)* |
| `seer_engine/runs.py` | `start_run(conn, rd) -> int\|None`, `finish_run(conn, run_id)`, `fail_run(conn, run_id, error)`, `MAX_ERROR_CHARS = 2000` *(add)* |
| `seer_engine/commands/migrate.py` | command `migrate [--dir PATH]`; `apply_migrations(conn, migrations_dir=MIGRATIONS_DIR, dry_run=False) -> list[str]`, `migration_files(dir) -> list[Path]`, `MIGRATIONS_DIR = REPO_ROOT/"db"/"migrations"` |
| `db/migrations/002_engine.sql` | tables `universe`, `split_adjustments`, `backfill_log`; indexes `universe_symbol_idx`, `runs_real_session_uidx` (columns and checks in Step 2) |
| `engine/tests/conftest.py` | fixtures `pg_url`, `pg_schema` → `PgSchema(conn, name, url)`, `pg_empty`, `pg`, `utc`; autouse `_isolated_env` (sets `SEER_ENV_FILE` to a missing file and `DATABASE_URL_UNPOOLED` to an unroutable `.invalid` host, so no test can reach Neon); autouse `_drop_cli_log_handler`; constant `MIGRATIONS_DIR` |

**Exact semantics that consumers depend on:**
- `upsert_bars` / `upsert_fx`: each COPYs into a session temp table (`_seer_bars_in` / `_seer_fx_in`, `ON COMMIT DELETE ROWS`) and then runs `INSERT … ON CONFLICT DO UPDATE … WHERE (stored) IS DISTINCT FROM (EXCLUDED)`. The return value counts rows inserted plus rows changed. An identical re-run returns 0 and creates **no new tuple versions** (the tests check `xmin`). Either can be called any number of times in one transaction. Neither commits. `upsert_bars` raises `ValueError` when a batch contains the same `(symbol, date)` twice. `upsert_fx` raises when one batch has two *different* rates for the same date.
- `start_run`: a single statement, `INSERT … ON CONFLICT (session_date) WHERE NOT is_demo DO UPDATE SET status='running', started_at=now(), finished_at=NULL, error=NULL, data_date=EXCLUDED.data_date WHERE runs.status <> 'success' RETURNING id`. If no row comes back, the session already succeeded and the function returns `None`. This is the "success → None, else upsert" rule from the phase scope folded into one atomic statement. Demo rows never conflict.
- `finish_run` / `fail_run`: set `finished_at = clock_timestamp()` rather than `now()`, so the time is real even when `start_run` ran in the same transaction. They touch only `NOT is_demo` rows and raise `LookupError` when the id does not exist. `fail_run` stores `http.redact(error)[:2000]`.
- `runs`, `bars`, `fx`, `universe` and `demo.purge_demo` **never commit**. Only `db.transaction`, `demo.purge_demo_if_needed` and `commands.migrate` commit.

**Requires (from earlier phases):** none (first phase).

**Leaves alone (owned by others):**
- The *contents* of `universe`, plus `engine/data/*`, `membership.py` and `commands/universe.py` (Phase 2).
- `yahoo.py` and `commands/backfill.py`, plus all writes to `backfill_log` (Phase 3).
- `massive.py`, `splits.py` and `commands/nightly.py`, plus all writes to `split_adjustments` (Phase 4).
- `.github/`, `web/scripts/seed-demo.mjs`, `docs/runbooks/`, `docs/ROADMAP.md` (Phase 5).
- `web/` in general, and `db/migrations/001_init.sql` (unchanged).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/pyproject.toml` | create (line 1) | package metadata, deps, pytest config |
| `engine/.gitignore` | create (line 1) | ignore `*.egg-info/`, `build/`, `dist/` (root `.gitignore` already covers `.venv/`, `__pycache__/`, `.pytest_cache/`) |
| `db/migrations/002_engine.sql` | create (line 1) | universe, split_adjustments, backfill_log, runs partial unique index |
| `engine/src/seer_engine/__init__.py` | create (line 1) | version |
| `engine/src/seer_engine/__main__.py` | create (line 1) | `python -m seer_engine` |
| `engine/src/seer_engine/config.py` | create (line 1) | dotenv loading and env access |
| `engine/src/seer_engine/db.py` | create (line 1) | connect and transaction/dry-run |
| `engine/src/seer_engine/http.py` | create (line 1) | `get_json` with retries, `redact` |
| `engine/src/seer_engine/dates.py` | create (line 1) | NYSE session logic, `RunDates` |
| `engine/src/seer_engine/bars.py` | create (line 1) | `Bar`, `make_bar`, idempotent upsert |
| `engine/src/seer_engine/fx.py` | create (line 1) | Frankfurter fetch, idempotent upsert |
| `engine/src/seer_engine/universe.py` | create (line 1) | point-in-time queries |
| `engine/src/seer_engine/demo.py` | create (line 1) | demo purge |
| `engine/src/seer_engine/runs.py` | create (line 1) | runs lifecycle |
| `engine/src/seer_engine/cli.py` | create (line 1) | discovery, flags, logging, exit codes |
| `engine/src/seer_engine/commands/__init__.py` | create (line 1) | package docstring (the command protocol) |
| `engine/src/seer_engine/commands/migrate.py` | create (line 1) | Python twin of `migrate.mjs` |
| `engine/tests/conftest.py` | create (line 1) | DB fixtures, env isolation, fixed clock |
| `engine/tests/test_dates.py` | create (line 1) | §6.4 date cases, DST, half day, Good Friday, year end |
| `engine/tests/test_cli.py` | create (line 1) | discovery, flags, exit codes, UTC logs, config |
| `engine/tests/test_migrate.py` | create (line 1) | idempotent apply, dry-run, interop with Node rows, per-file rollback, CLI |
| `engine/tests/test_bars.py` | create (line 1) | rounding, upsert idempotency (0 rows, unchanged xmin), changes count 1 |
| `engine/tests/test_fx.py` | create (line 1) | Frankfurter parsing and chunking (fake HTTP), upsert idempotency |
| `engine/tests/test_runs.py` | create (line 1) | lifecycle, success no-op, failed-row reuse, redaction, index |
| `engine/tests/test_demo.py` | create (line 1) | purge empties 6 tables and keeps strategies; no-op without a demo run; dry-run; atomicity |
| `engine/tests/test_universe_queries.py` | create (line 1) | interval semantics, grace, SPY, checks |
| `engine/tests/test_http.py` | create (line 1) | retry policy, Retry-After, 4xx not retried, redaction |

Deviation from the index's file list, recorded for the reconciler: pytest configuration lives in `[tool.pytest.ini_options]` in `pyproject.toml`, which the index allows, rather than in a separate `pytest.ini`. `test_http.py` is added. Config tests live in `test_cli.py`.

## Implementation Steps

All paths are relative to the worktree root `/home/miftah/.worktrees/seer/engine-data-pipeline`. The shell is zsh. Never `source .env.local`.

### Step 1: Package metadata, ignore file, venv
**File:** `engine/pyproject.toml:1` (new), `engine/.gitignore:1` (new)
**Change:** Create both files, then build the venv:
```zsh
cd /home/miftah/.worktrees/seer/engine-data-pipeline
python3.11 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'
```
**Code (`engine/pyproject.toml`):**
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "seer-engine"
version = "0.1.0"
description = "Seer data pipeline: point-in-time universe, daily bars, FX, nightly runs."
requires-python = ">=3.11"
dependencies = [
  "psycopg[binary]>=3.2",
  "pandas>=2.2",
  "pandas_market_calendars>=5.0",
  "yfinance>=1.0",
  "requests>=2.32",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
seer-engine = "seer_engine.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```
**Code (`engine/.gitignore`):**
```gitignore
# setuptools build output from `pip install -e engine`
*.egg-info/
build/
dist/
```
**Impact:** None on the existing tree. `pip install -e` writes `engine/src/seer_engine.egg-info/`, which the new ignore file covers.

### Step 2: Migration 002
**File:** `db/migrations/002_engine.sql:1` (new)
**Change:** Additive DDL, idempotent (`IF NOT EXISTS`), with a comment header in the style of 001. `universe.end_date` is **exclusive**; NULL means still a member. `split_from`/`split_to > 0` guards the division in Phase 4's re-adjustment. `backfill_log.rows` stays nullable, as the scope specifies (the name `rows` is legal in Postgres 16; verified).
**Code:**
```sql
-- Seer schema v2: engine bookkeeping. Written by engine/ (Python); web/ does not read these.
-- Additive only: three new tables and one partial unique index on runs.

-- Point-in-time index membership, one row per uninterrupted membership interval.
-- A symbol is a member of index_id on date D when start_date <= D AND (end_date IS NULL OR end_date > D).
CREATE TABLE IF NOT EXISTS universe (
  symbol         text NOT NULL,                 -- canonical dot form, same string as bars.symbol ('BRK.B')
  index_id       text NOT NULL CHECK (index_id IN ('SP500', 'NDX')),
  start_date     date NOT NULL,                 -- first day as a member (inclusive)
  end_date       date,                          -- first day no longer a member (EXCLUSIVE); NULL = still a member
  source_symbol  text NOT NULL,                 -- ticker(s) as written in the source dataset (before aliasing); when one
                                                -- interval spans a rename: every source ticker, oldest first, '/'-joined ('FB/META')
  PRIMARY KEY (index_id, symbol, start_date),
  CHECK (end_date IS NULL OR end_date > start_date)
);
CREATE INDEX IF NOT EXISTS universe_symbol_idx ON universe (symbol);

-- Splits seen by the nightly job. applied = history in bars was re-adjusted for this split.
-- Pre-split price / (split_to / split_from); pre-split volume * (split_to / split_from).
CREATE TABLE IF NOT EXISTS split_adjustments (
  symbol          text NOT NULL,
  execution_date  date NOT NULL,
  split_from      numeric NOT NULL CHECK (split_from > 0),
  split_to        numeric NOT NULL CHECK (split_to > 0),
  applied         boolean NOT NULL,
  recorded_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, execution_date)
);

-- One row per symbol the history backfill attempted; lets the backfill resume and
-- records which ever-members could not be fetched.
CREATE TABLE IF NOT EXISTS backfill_log (
  symbol      text PRIMARY KEY,
  status      text NOT NULL CHECK (status IN ('ok', 'empty', 'failed')),
  first_date  date,
  last_date   date,
  rows        int,
  error       text,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- At most one real (non-demo) run per target session: a re-run reuses the row.
CREATE UNIQUE INDEX IF NOT EXISTS runs_real_session_uidx ON runs (session_date) WHERE NOT is_demo;
```
**Impact:** Live Neon already holds one `is_demo` run. The partial index excludes demo rows, so it builds cleanly there. Phase 5 applies it to Neon.

### Step 3: Package root and config
**File:** `engine/src/seer_engine/__init__.py:1`, `engine/src/seer_engine/__main__.py:1`, `engine/src/seer_engine/config.py:1` (all new)
**Code (`__init__.py`):**
```python
"""Seer engine: data pipeline that writes Neon tables the web app reads."""

__version__ = "0.1.0"
```
**Code (`__main__.py`):**
```python
"""Entry point for ``python -m seer_engine``."""

from seer_engine.cli import main

raise SystemExit(main())
```
**Code (`config.py`):**
```python
"""Environment configuration.

Values come from the process environment. Locally they are also read from the repo-root
``.env.local`` (or the file named by ``SEER_ENV_FILE``) with python-dotenv, which never
overrides a variable that is already set. The file is parsed, never ``source``d: it holds
an unquoted ``&`` that a shell would misread.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# engine/src/seer_engine/config.py -> parents: seer_engine, src, engine, <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]

_loaded = False


class ConfigError(RuntimeError):
    """A required setting is missing."""


def env_file() -> Path:
    """The dotenv file load_env() reads: $SEER_ENV_FILE, else <repo root>/.env.local."""
    override = os.environ.get("SEER_ENV_FILE")
    return Path(override) if override else REPO_ROOT / ".env.local"


def load_env() -> Path | None:
    """Load the dotenv file into os.environ without overriding existing variables.

    Returns the path that was loaded, or None when the file does not exist (CI).
    Safe to call more than once.
    """
    global _loaded
    _loaded = True
    path = env_file()
    if not path.is_file():
        return None
    load_dotenv(path, override=False)
    return path


def get(name: str) -> str | None:
    """The value of ``name``, or None when unset or empty."""
    if not _loaded:
        load_env()
    value = os.environ.get(name)
    return value if value else None


def require(name: str) -> str:
    """The value of ``name``; raises ConfigError when unset or empty."""
    value = get(name)
    if value is None:
        raise ConfigError(f"{name} is not set (checked the environment and {env_file()})")
    return value
```
**Impact:** `REPO_ROOT` is `parents[3]` of the source file. This holds for an editable install (where `__file__` is the source path) and for CI runs from a checkout.

### Step 4: DB connection and transaction helper
**File:** `engine/src/seer_engine/db.py:1` (new)
**Code:**
```python
"""Postgres connection and the one transaction helper every write goes through."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from seer_engine import config

log = logging.getLogger(__name__)

CONNECT_TIMEOUT_S = 15


def connect(url: str | None = None) -> psycopg.Connection:
    """Open a connection with autocommit off.

    ``url`` defaults to DATABASE_URL_UNPOOLED (Neon's direct endpoint; the pooled one does
    not support session state such as temp tables). Tests pass their own URL.
    """
    dsn = url or config.require("DATABASE_URL_UNPOOLED")
    return psycopg.connect(dsn, autocommit=False, connect_timeout=CONNECT_TIMEOUT_S)


@contextmanager
def transaction(conn: psycopg.Connection, dry_run: bool) -> Iterator[psycopg.Connection]:
    """Run the block in one transaction: commit on success, roll back on error.

    With ``dry_run`` the block runs in full (every read and every write statement) and is
    then rolled back, so nothing persists.
    """
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    if dry_run:
        conn.rollback()
        log.info("dry-run: transaction rolled back")
    else:
        conn.commit()
```
**Impact:** Every later write goes through `transaction(conn, dry_run)` (invariant 5). Callers must hold the connection with `contextlib.closing(db.connect())`, **not** `with db.connect() as conn`: psycopg's own context manager commits on exit, which would defeat a dry-run that left a statement outside `transaction()`.

### Step 5: HTTP helper
**File:** `engine/src/seer_engine/http.py:1` (new)
**Code:**
```python
"""JSON-over-HTTP with retries, and URL redaction for logs and errors."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests

from seer_engine import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"seer-engine/{__version__}"

_SECRET_PARAM = re.compile(r"(?i)\b((?:api_?key|apikey|access_token|token|key)=)[^&#\s]+")

# Module-level so tests can replace them.
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_sleep = time.sleep


class HttpError(RuntimeError):
    """A request failed after all retries, or returned a non-retryable status."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def redact(url: str) -> str:
    """``url`` with the value of any key/token query parameter replaced by REDACTED."""
    return _SECRET_PARAM.sub(r"\1REDACTED", url)


def _retry_after(resp: requests.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    retries: int = 3,
    backoff: float = 5.0,
    timeout: float = 30,
) -> dict:
    """GET ``url`` and return the decoded JSON object.

    Connection errors, timeouts, HTTP 429 and 5xx are retried up to ``retries`` times with
    exponential backoff (``backoff``, 2x, 4x ... seconds; a numeric Retry-After header wins
    when it is longer). Any other non-200 status raises HttpError at once. Every URL that
    reaches a log line or an exception message is redacted.
    """
    attempt = 0
    while True:
        attempt += 1
        retry_after: float | None = None
        status: int | None = None
        try:
            resp = _session.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            message = redact(f"{type(exc).__name__}: {exc}")
            retryable = True
        else:
            status = resp.status_code
            if status == 200:
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise HttpError(f"non-JSON response from {redact(resp.url)}", status) from exc
                if not isinstance(data, dict):
                    raise HttpError(f"expected a JSON object from {redact(resp.url)}", status)
                return data
            message = redact(f"HTTP {status} from {resp.url}: {resp.text[:300]}")
            retryable = status == 429 or status >= 500
            retry_after = _retry_after(resp)
        if not retryable or attempt > retries:
            raise HttpError(message, status)
        delay = backoff * (2 ** (attempt - 1))
        if retry_after is not None:
            delay = max(delay, retry_after)
        log.warning("%s; retry %d/%d in %.1fs", message, attempt, retries, delay)
        _sleep(delay)
```
**Impact:** Phase 4's Massive client should call `get_json(..., params={"apiKey": key, ...})`. Every URL in errors and logs is then redacted (invariant 8). The module is named `http` as the contract requires. It does not shadow the stdlib because the package directory is never on `sys.path` itself.

### Step 6: NYSE dates
**File:** `engine/src/seer_engine/dates.py:1` (new)
**Change:** Schedules are cached per calendar year (`lru_cache` on `_year(year)`), and range queries assemble the year blocks they span. `market_close` from pandas_market_calendars 5.x is tz-aware UTC, which covers half days (2026-11-27 closes 18:00 UTC) and DST.
**Code:**
```python
"""NYSE session arithmetic.

Dates are ``datetime.date`` values (the ET calendar date of a session). The only
timezone-aware datetimes here are UTC "now" and session closes from the NYSE calendar,
whose ``market_close`` already accounts for half days and daylight saving time.

- ``data_date``: the last completed session, i.e. the latest session whose close plus a
  settle margin is not after now.
- ``session_date``: the session after ``data_date``, which the next picks are for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import pandas_market_calendars as mcal

CALENDAR = "NYSE"
DEFAULT_SETTLE = timedelta(hours=1)

# How many calendar years next_session/prev_session will scan before giving up.
_MAX_YEAR_SCAN = 3


@dataclass(frozen=True, slots=True)
class RunDates:
    data_date: date
    session_date: date


@lru_cache(maxsize=1)
def _calendar() -> mcal.MarketCalendar:
    return mcal.get_calendar(CALENDAR)


@lru_cache(maxsize=None)
def _year(year: int) -> tuple[tuple[date, datetime], ...]:
    """(session date, market close in UTC) for every NYSE session in ``year``, ascending."""
    sched = _calendar().schedule(start_date=f"{year}-01-01", end_date=f"{year}-12-31")
    out: list[tuple[date, datetime]] = []
    for idx, close in zip(sched.index, sched["market_close"]):
        out.append((idx.date(), close.to_pydatetime().astimezone(timezone.utc)))
    return tuple(out)


@lru_cache(maxsize=None)
def _closes(year: int) -> dict[date, datetime]:
    return dict(_year(year))


def _as_date(d: date) -> date:
    if isinstance(d, datetime):
        raise TypeError(f"expected a date, got a datetime: {d!r}")
    if not isinstance(d, date):
        raise TypeError(f"expected a date, got {type(d).__name__}")
    return d


def _as_utc(now_utc: datetime) -> datetime:
    if not isinstance(now_utc, datetime):
        raise TypeError(f"expected a datetime, got {type(now_utc).__name__}")
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    return now_utc.astimezone(timezone.utc)


def sessions(start: date, end: date) -> list[date]:
    """Every NYSE session from ``start`` to ``end``, both inclusive, ascending."""
    start, end = _as_date(start), _as_date(end)
    if end < start:
        return []
    out: list[date] = []
    for year in range(start.year, end.year + 1):
        out.extend(d for d, _ in _year(year) if start <= d <= end)
    return out


def is_session(d: date) -> bool:
    """True when ``d`` is an NYSE trading day (half days included)."""
    d = _as_date(d)
    return d in _closes(d.year)


def next_session(d: date) -> date:
    """The first NYSE session strictly after ``d``."""
    d = _as_date(d)
    for year in range(d.year, d.year + _MAX_YEAR_SCAN):
        for s, _ in _year(year):
            if s > d:
                return s
    raise ValueError(f"no NYSE session after {d} within {_MAX_YEAR_SCAN} years")


def prev_session(d: date) -> date:
    """The last NYSE session strictly before ``d``."""
    d = _as_date(d)
    for year in range(d.year, d.year - _MAX_YEAR_SCAN, -1):
        for s, _ in reversed(_year(year)):
            if s < d:
                return s
    raise ValueError(f"no NYSE session before {d} within {_MAX_YEAR_SCAN} years")


def session_close_utc(d: date) -> datetime:
    """The scheduled close of session ``d`` in UTC (18:00 UTC on a winter half day)."""
    d = _as_date(d)
    try:
        return _closes(d.year)[d]
    except KeyError:
        raise ValueError(f"{d} is not an NYSE session") from None


def last_completed_session(now_utc: datetime, settle: timedelta = DEFAULT_SETTLE) -> date:
    """The latest session whose close + ``settle`` is at or before ``now_utc``."""
    now = _as_utc(now_utc)
    cutoff = now - settle
    # A session's close falls on its own UTC calendar date, so nothing after now's UTC date
    # can have closed yet.
    today = now.date()
    s = today if is_session(today) else prev_session(today)
    while session_close_utc(s) > cutoff:
        s = prev_session(s)
    return s


def run_dates(now_utc: datetime | None = None, settle: timedelta = DEFAULT_SETTLE) -> RunDates:
    """The dates a run started at ``now_utc`` (default: the current time) works with."""
    now = datetime.now(timezone.utc) if now_utc is None else now_utc
    data_date = last_completed_session(now, settle)
    return RunDates(data_date=data_date, session_date=next_session(data_date))
```
**Impact:** `run_dates()` is the single source of `data_date` and `session_date` for Phase 4. Phase 3 uses `last_completed_session(now)` as its default end date.

### Step 7: Bars
**File:** `engine/src/seer_engine/bars.py:1` (new)
**Code:**
```python
"""Daily bars: the value type and idempotent writes to ``bars``.

Prices are split-adjusted only (no dividend adjustment), stored as numeric(12,4);
volume is an integer. Symbols are in canonical dot form ('BRK.B').
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import psycopg

PRICE_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def to_decimal(x: Decimal | float | int | str) -> Decimal:
    """``x`` as a Decimal rounded half-up to 4 decimals (Postgres numeric rounding).

    Floats go through their shortest repr, so 0.1 becomes Decimal('0.1000'), not the
    binary expansion.
    """
    if isinstance(x, bool):
        raise TypeError("bool is not a price")
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError(f"non-finite value: {x!r}")
        d = Decimal(repr(x))
    else:
        d = Decimal(x)
    if not d.is_finite():
        raise ValueError(f"non-finite value: {x!r}")
    return d.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)


def to_volume(v: Decimal | float | int | str) -> int:
    """``v`` rounded half-up to a non-negative int (Massive reports volume as a float)."""
    if isinstance(v, bool):
        raise TypeError("bool is not a volume")
    if isinstance(v, int):
        n = v
    else:
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"non-finite volume: {v!r}")
        n = int(Decimal(repr(v) if isinstance(v, float) else v).to_integral_value(ROUND_HALF_UP))
    if n < 0:
        raise ValueError(f"negative volume: {v!r}")
    return n


def make_bar(
    symbol: str,
    d: date,
    o: Decimal | float | int | str,
    h: Decimal | float | int | str,
    l: Decimal | float | int | str,  # noqa: E741
    c: Decimal | float | int | str,
    v: Decimal | float | int | str,
) -> Bar:
    """A Bar with prices rounded to 4 decimals and an int volume."""
    if not symbol:
        raise ValueError("empty symbol")
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"expected a date, got {d!r}")
    return Bar(symbol, d, to_decimal(o), to_decimal(h), to_decimal(l), to_decimal(c), to_volume(v))


def upsert_bars(conn: psycopg.Connection, bars: Iterable[Bar]) -> int:
    """Insert new bars and update changed ones; return how many rows were inserted or changed.

    Bars identical to the stored row are skipped by the ``IS DISTINCT FROM`` guard, so they
    are not counted and create no new row versions: an identical re-run returns 0.
    Raises ValueError when the batch holds the same (symbol, date) twice. Does not commit.
    """
    rows = list(bars)
    if not rows:
        return 0
    seen: set[tuple[str, date]] = set()
    for b in rows:
        key = (b.symbol, b.date)
        if key in seen:
            raise ValueError(f"duplicate bar in batch: {b.symbol} {b.date.isoformat()}")
        seen.add(key)
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE IF NOT EXISTS _seer_bars_in "
            "(LIKE bars INCLUDING DEFAULTS) ON COMMIT DELETE ROWS"
        )
        cur.execute("TRUNCATE _seer_bars_in")
        with cur.copy(
            "COPY _seer_bars_in (symbol, date, open, high, low, close, volume) FROM STDIN"
        ) as copy:
            for b in rows:
                copy.write_row((b.symbol, b.date, b.open, b.high, b.low, b.close, b.volume))
        cur.execute(
            """
            INSERT INTO bars AS b (symbol, date, open, high, low, close, volume)
            SELECT symbol, date, open, high, low, close, volume FROM _seer_bars_in
            ON CONFLICT (symbol, date) DO UPDATE
            SET open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
            WHERE (b.open, b.high, b.low, b.close, b.volume)
                  IS DISTINCT FROM
                  (EXCLUDED.open, EXCLUDED.high, EXCLUDED.low, EXCLUDED.close, EXCLUDED.volume)
            """
        )
        changed = cur.rowcount
        cur.execute("TRUNCATE _seer_bars_in")
    return changed


def latest_bar_date(conn: psycopg.Connection, symbol: str) -> date | None:
    """The newest stored bar date for ``symbol``, or None when it has no bars."""
    row = conn.execute("SELECT max(date) FROM bars WHERE symbol = %s", (symbol,)).fetchone()
    return row[0]


def delete_bars_on(conn: psycopg.Connection, d: date) -> int:
    """Delete every bar dated ``d``; return the number deleted. Does not commit."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM bars WHERE date = %s", (d,))
        return cur.rowcount
```
**Impact:** Phases 3 and 4 build bars only through `make_bar` and write only through `upsert_bars` (invariant 4 rounding happens in one place). The temp table is session state, so this needs the unpooled URL. `DATABASE_URL_UNPOOLED` is the default.

### Step 8: FX
**File:** `engine/src/seer_engine/fx.py:1` (new)
**Code:**
```python
"""USD/IDR from Frankfurter (ECB reference rates; no API key) and writes to ``fx_rates``."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import psycopg

from seer_engine import http
from seer_engine.bars import to_decimal

FRANKFURTER = "https://api.frankfurter.dev/v1"
PARAMS = {"base": "USD", "symbols": "IDR"}


def _idr(rates: dict, where: str) -> Decimal:
    try:
        return to_decimal(rates["IDR"])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Frankfurter response has no IDR rate ({where})") from exc


def fetch_latest() -> tuple[date, Decimal]:
    """The newest published USD/IDR rate and the date Frankfurter says it is for."""
    data = http.get_json(f"{FRANKFURTER}/latest", params=PARAMS)
    return date.fromisoformat(data["date"]), _idr(data.get("rates") or {}, "latest")


def fetch_range(start: date, end: date) -> list[tuple[date, Decimal]]:
    """Every published USD/IDR rate from ``start`` to ``end`` inclusive, ascending.

    One request per calendar year keeps each response small.
    """
    if end < start:
        return []
    out: dict[date, Decimal] = {}
    for year in range(start.year, end.year + 1):
        a = max(start, date(year, 1, 1))
        b = min(end, date(year, 12, 31))
        data = http.get_json(f"{FRANKFURTER}/{a.isoformat()}..{b.isoformat()}", params=PARAMS)
        for key, rates in (data.get("rates") or {}).items():
            d = date.fromisoformat(key)
            if a <= d <= b:
                out[d] = _idr(rates, key)
    return sorted(out.items())


def upsert_fx(conn: psycopg.Connection, rows: Iterable[tuple[date, Decimal | float | str]]) -> int:
    """Insert new rates and update changed ones (rounded to 4 decimals); return how many
    rows were inserted or changed. An identical re-run returns 0. Does not commit."""
    items: dict[date, Decimal] = {}
    for d, rate in rows:
        value = to_decimal(rate)
        if d in items and items[d] != value:
            raise ValueError(f"conflicting rates for {d.isoformat()} in one batch")
        items[d] = value
    if not items:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE IF NOT EXISTS _seer_fx_in "
            "(LIKE fx_rates INCLUDING DEFAULTS) ON COMMIT DELETE ROWS"
        )
        cur.execute("TRUNCATE _seer_fx_in")
        with cur.copy("COPY _seer_fx_in (date, usd_idr) FROM STDIN") as copy:
            for d, value in sorted(items.items()):
                copy.write_row((d, value))
        cur.execute(
            """
            INSERT INTO fx_rates AS f (date, usd_idr)
            SELECT date, usd_idr FROM _seer_fx_in
            ON CONFLICT (date) DO UPDATE
            SET usd_idr = EXCLUDED.usd_idr
            WHERE f.usd_idr IS DISTINCT FROM EXCLUDED.usd_idr
            """
        )
        changed = cur.rowcount
        cur.execute("TRUNCATE _seer_fx_in")
    return changed
```
**Impact:** Frankfurter is the only network source this phase touches, and its tests fake it. `fetch_latest()` returns Frankfurter's own date (the ECB publication day), which can be earlier than `data_date`. Phase 4 stores it under that date, as returned.

### Step 9: Universe queries
**File:** `engine/src/seer_engine/universe.py:1` (new)
**Code:**
```python
"""Read-side queries on the point-in-time ``universe`` table.

Membership intervals are [start_date, end_date): end_date is exclusive, NULL = still a
member. Phase 2's ``universe refresh`` writes the table; these functions only read it.
"""

from __future__ import annotations

from datetime import date, timedelta

import psycopg

BENCHMARK = "SPY"


def members_on(conn: psycopg.Connection, d: date) -> set[str]:
    """Symbols in either index on ``d``."""
    rows = conn.execute(
        """
        SELECT DISTINCT symbol FROM universe
        WHERE start_date <= %(d)s AND (end_date IS NULL OR end_date > %(d)s)
        """,
        {"d": d},
    ).fetchall()
    return {r[0] for r in rows}


def symbols_for_bars(conn: psycopg.Connection, d: date, grace_days: int = 30) -> set[str]:
    """Symbols whose bars are stored for ``d``: members on ``d``, members that left in the
    last ``grace_days`` days (so open positions keep a price), and the benchmark."""
    rows = conn.execute(
        """
        SELECT DISTINCT symbol FROM universe
        WHERE start_date <= %(d)s AND (end_date IS NULL OR end_date > %(cut)s)
        """,
        {"d": d, "cut": d - timedelta(days=grace_days)},
    ).fetchall()
    return {r[0] for r in rows} | {BENCHMARK}


def all_symbols(conn: psycopg.Connection, since: date) -> list[str]:
    """Every symbol that was a member at any time after ``since``, plus the benchmark,
    sorted. Members that joined after ``since`` are included."""
    rows = conn.execute(
        "SELECT DISTINCT symbol FROM universe WHERE end_date IS NULL OR end_date > %(since)s",
        {"since": since},
    ).fetchall()
    return sorted({r[0] for r in rows} | {BENCHMARK})
```
**Impact:** Read-only. Phase 2 writes the table with exactly these interval semantics.

### Step 10: Demo purge
**File:** `engine/src/seer_engine/demo.py:1` (new)
**Change:** `TRUNCATE action_dismissals, orders, equity_snapshots, bars, fx_rates, runs RESTART IDENTITY`, with no `CASCADE`. The only foreign key into this set is `action_dismissals → orders`, and both tables are in the list. `orders → strategies` and `equity_snapshots → strategies` point *out* of the set, which TRUNCATE allows. `strategies` survives.
**Code:**
```python
"""Removal of the demo rows seeded by web/scripts/seed-demo.mjs.

Demo bars and FX rows are indistinguishable from real ones, so the trigger is the
existence of a demo run: while one exists, every row in the demo-owned tables is demo
data. ``strategies`` is kept because orders reference it and later phases reuse it.
"""

from __future__ import annotations

import logging

import psycopg

from seer_engine import db

log = logging.getLogger(__name__)

DEMO_TABLES = ("action_dismissals", "orders", "equity_snapshots", "bars", "fx_rates", "runs")


def has_demo(conn: psycopg.Connection) -> bool:
    """True when any ``runs`` row is a demo run."""
    row = conn.execute("SELECT EXISTS (SELECT 1 FROM runs WHERE is_demo)").fetchone()
    return bool(row[0])


def purge_demo(conn: psycopg.Connection) -> bool:
    """Empty every demo-owned table when a demo run exists. Returns True when it purged.

    Does not commit: the caller's transaction makes it atomic.
    """
    if not has_demo(conn):
        return False
    conn.execute(f"TRUNCATE {', '.join(DEMO_TABLES)} RESTART IDENTITY")
    log.warning("demo data found: truncated %s", ", ".join(DEMO_TABLES))
    return True


def purge_demo_if_needed(conn: psycopg.Connection, dry_run: bool) -> bool:
    """purge_demo() in its own transaction, before a command's first real write.

    Under ``dry_run`` the purge runs and is rolled back; the return value still says
    whether it would have purged.
    """
    with db.transaction(conn, dry_run):
        purged = purge_demo(conn)
    if purged and dry_run:
        log.warning("dry-run: would purge demo data (%s)", ", ".join(DEMO_TABLES))
    return purged
```
**Impact:** Implements spec §3 "Demo data" and §6.6 (R5). Every write command in phases 2–4 calls `purge_demo_if_needed(conn, args.dry_run)` before its first write (invariant 6).

### Step 11: Runs lifecycle
**File:** `engine/src/seer_engine/runs.py:1` (new)
**Code:**
```python
"""The ``runs`` row lifecycle: one real row per target session.

None of these functions commit; the caller's db.transaction() decides.
"""

from __future__ import annotations

import psycopg

from seer_engine.dates import RunDates
from seer_engine.http import redact

MAX_ERROR_CHARS = 2000


def start_run(conn: psycopg.Connection, rd: RunDates) -> int | None:
    """Claim the real run row for ``rd.session_date`` and mark it running.

    Returns its id, or None when that session already has a successful real run (the
    caller then does nothing). A failed or interrupted row is reused: same id, status
    back to running, error and finished_at cleared, data_date refreshed.
    """
    row = conn.execute(
        """
        INSERT INTO runs (status, data_date, session_date, is_demo)
        VALUES ('running', %(data_date)s, %(session_date)s, false)
        ON CONFLICT (session_date) WHERE NOT is_demo DO UPDATE
        SET status = 'running',
            started_at = now(),
            finished_at = NULL,
            error = NULL,
            data_date = EXCLUDED.data_date
        WHERE runs.status <> 'success'
        RETURNING id
        """,
        {"data_date": rd.data_date, "session_date": rd.session_date},
    ).fetchone()
    return None if row is None else int(row[0])


def _set_final(conn: psycopg.Connection, run_id: int, status: str, error: str | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE runs
            SET status = %(status)s, error = %(error)s, finished_at = clock_timestamp()
            WHERE id = %(id)s AND NOT is_demo
            """,
            {"status": status, "error": error, "id": run_id},
        )
        if cur.rowcount != 1:
            raise LookupError(f"no real run with id {run_id}")


def finish_run(conn: psycopg.Connection, run_id: int) -> None:
    """Mark the run successful."""
    _set_final(conn, run_id, "success", None)


def fail_run(conn: psycopg.Connection, run_id: int, error: str) -> None:
    """Mark the run failed with ``error`` (secrets redacted, cut to 2000 characters)."""
    _set_final(conn, run_id, "failed", redact(error)[:MAX_ERROR_CHARS])
```
**Impact:** Requires `runs_real_session_uidx` (Step 2). The `ON CONFLICT … WHERE NOT is_demo` inference only matches that partial index.

### Step 12: CLI and command package
**File:** `engine/src/seer_engine/cli.py:1`, `engine/src/seer_engine/commands/__init__.py:1` (new)
**Change:** Commands are found with `pkgutil.iter_modules(commands.__path__)`. On subparsers the global flags use `default=argparse.SUPPRESS`, so `--dry-run` works on either side of the command name. Logs go to stderr with `%Y-%m-%dT%H:%M:%SZ` UTC timestamps (`converter = time.gmtime`). The handler is tagged so that repeated `main()` calls, as in tests, replace it rather than stack copies, and pytest's `caplog` is left alone (no `basicConfig(force=True)`).
**Code (`cli.py`):**
```python
"""``python -m seer_engine [--dry-run] [-v] <command> ...``

Commands are the modules in ``seer_engine/commands/`` (names not starting with ``_``).
Each one exposes::

    HELP: str
    def add_arguments(p: argparse.ArgumentParser) -> None
    def run(args: argparse.Namespace) -> int     # args.dry_run and args.verbose are set

Adding a command means adding a module; this file never changes. ``run``'s return value
is the process exit code.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import pkgutil
import sys
import time
from collections.abc import Sequence
from types import ModuleType

from seer_engine import __version__, commands, config

log = logging.getLogger("seer_engine")

_HANDLER_FLAG = "_seer_engine_handler"


def discover() -> dict[str, ModuleType]:
    """Command name -> module, for every public module in seer_engine.commands, sorted."""
    found: dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(commands.__path__):
        if info.name.startswith("_") or info.ispkg:
            continue
        module = importlib.import_module(f"{commands.__name__}.{info.name}")
        if not callable(getattr(module, "run", None)):
            raise TypeError(f"command module {module.__name__} has no run(args)")
        found[info.name] = module
    return dict(sorted(found.items()))


def _add_global_flags(p: argparse.ArgumentParser, *, suppress: bool) -> None:
    """--dry-run and -v. On subcommands the defaults are suppressed so the flags work on
    either side of the command name without one position resetting the other."""
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS if suppress else False,
        help="do every read and compute every write, then roll back; nothing persists",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=argparse.SUPPRESS if suppress else 0,
        help="debug logging",
    )


def build_parser(modules: dict[str, ModuleType] | None = None) -> argparse.ArgumentParser:
    modules = discover() if modules is None else modules
    parser = argparse.ArgumentParser(
        prog="seer_engine", description="Seer data pipeline (bars, universe, FX, runs)."
    )
    parser.add_argument("--version", action="version", version=f"seer_engine {__version__}")
    _add_global_flags(parser, suppress=False)
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)
    for name, module in modules.items():
        help_text = getattr(module, "HELP", "")
        p = sub.add_parser(name, help=help_text, description=help_text)
        _add_global_flags(p, suppress=True)
        add_arguments = getattr(module, "add_arguments", None)
        if add_arguments is not None:
            add_arguments(p)
        p.set_defaults(_run=module.run)
    return parser


class _UtcFormatter(logging.Formatter):
    converter = time.gmtime


def setup_logging(verbose: int) -> None:
    """Log to stderr with UTC timestamps. Replaces only the handler this function added."""
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, _HANDLER_FLAG, False):
            root.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        _UtcFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%SZ")
    )
    setattr(handler, _HANDLER_FLAG, True)
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for noisy in ("urllib3", "yfinance", "peewee"):
        logging.getLogger(noisy).setLevel(logging.DEBUG if verbose > 1 else logging.WARNING)


def main(argv: Sequence[str] | None = None) -> int:
    config.load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    if args.dry_run:
        log.info("dry-run: every transaction will be rolled back")
    try:
        code = args._run(args)
    except config.ConfigError as exc:
        log.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        log.error("interrupted")
        return 130
    except Exception:
        log.exception("command %r failed", args.command)
        return 1
    return int(code or 0)
```
**Code (`commands/__init__.py`):**
```python
"""Subcommands of ``python -m seer_engine``; one module per command, discovered by cli.py.

A command module exposes ``HELP: str``, ``add_arguments(p)`` and ``run(args) -> int``.
"""
```
**Impact:** Phases 2–4 add `commands/universe.py`, `commands/backfill.py` and `commands/nightly.py` without touching `cli.py` (invariant 7).

### Step 13: `migrate` command
**File:** `engine/src/seer_engine/commands/migrate.py:1` (new)
**Change:** Same table DDL, same key (the file name) and same name order as `web/scripts/migrate.mjs:12-33`, with one transaction per file. Under `--dry-run`, all pending files are applied in **one** transaction that is then rolled back. 002 depends on 001's `runs`, so per-file rollbacks would make a dry run on a fresh database fail spuriously.
**Code:**
```python
"""Apply db/migrations/*.sql in name order, each once.

The Python twin of web/scripts/migrate.mjs: same ``schema_migrations`` table, same key
(the file name), one transaction per file, so either runner can apply any migration and
neither re-applies the other's work. Under --dry-run every pending file is applied inside
a single transaction (later files may depend on earlier ones) that is then rolled back.
"""

from __future__ import annotations

import argparse
import logging
from contextlib import closing
from pathlib import Path

import psycopg

from seer_engine import config, db

HELP = "apply pending db/migrations/*.sql (shares schema_migrations with web's db:migrate)"

MIGRATIONS_DIR = config.REPO_ROOT / "db" / "migrations"

log = logging.getLogger(__name__)

_CREATE_TABLE = """CREATE TABLE IF NOT EXISTS schema_migrations (
  name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"""


def migration_files(migrations_dir: Path) -> list[Path]:
    """``*.sql`` files in ``migrations_dir`` sorted by file name."""
    return sorted(
        (p for p in migrations_dir.iterdir() if p.is_file() and p.suffix == ".sql"),
        key=lambda p: p.name,
    )


def _applied(conn: psycopg.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM schema_migrations").fetchall()}


def _apply_one(conn: psycopg.Connection, path: Path) -> None:
    conn.execute(path.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))


def apply_migrations(
    conn: psycopg.Connection, migrations_dir: Path = MIGRATIONS_DIR, dry_run: bool = False
) -> list[str]:
    """Apply every pending migration; return the file names applied (or, under dry_run,
    the names that would be applied)."""
    files = migration_files(migrations_dir)
    done: list[str] = []
    if dry_run:
        try:
            conn.execute(_CREATE_TABLE)
            applied = _applied(conn)
            for path in files:
                if path.name in applied:
                    log.info("skip  %s", path.name)
                    continue
                _apply_one(conn, path)
                done.append(path.name)
                log.info("would apply %s", path.name)
        finally:
            conn.rollback()
        return done

    with db.transaction(conn, dry_run=False):
        conn.execute(_CREATE_TABLE)
    with db.transaction(conn, dry_run=False):
        applied = _applied(conn)
    for path in files:
        if path.name in applied:
            log.info("skip  %s", path.name)
            continue
        with db.transaction(conn, dry_run=False):
            _apply_one(conn, path)
        done.append(path.name)
        log.info("apply %s", path.name)
    return done


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--dir",
        type=Path,
        default=MIGRATIONS_DIR,
        help=f"migrations directory (default: {MIGRATIONS_DIR})",
    )


def run(args: argparse.Namespace) -> int:
    # closing(), not the connection's own context manager: that one commits on exit.
    with closing(db.connect()) as conn:
        names = apply_migrations(conn, args.dir, dry_run=args.dry_run)
    if not names:
        log.info("nothing to apply")
    return 0
```
**Impact:** Phase 5 can run `python -m seer_engine migrate` on Neon from WSL. The Node runner needs `node --env-file` relative to `web/`; this one reads the repo-root `.env.local` directly. Either runner skips what the other applied (tested).

### Step 14: Test fixtures
**File:** `engine/tests/conftest.py:1` (new)
**Change:** `pg_schema` creates `t_<12 hex>`, sets `search_path` to it **and commits**, because a `SET` inside a rolled-back transaction is undone. It drops the schema afterwards over a separate autocommit connection. `pg` applies `db/migrations/*.sql` by plain execution, independent of the migrate code under test. `PgSchema.url` is a conninfo with `options=-c search_path=<schema>`, for code that opens its own connection (`cli.main`, a second connection to prove a commit).
**Code:**
```python
"""Shared fixtures.

DB tests need a real Postgres at PG_TEST_URL. Locally::

    docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
    export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres

Each DB test gets its own throwaway schema (``t_<hex>``), dropped afterwards, so tests
never see each other's rows and never touch ``public``.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from seer_engine import config

MIGRATIONS_DIR = config.REPO_ROOT / "db" / "migrations"

_PG_TEST_URL = os.environ.get("PG_TEST_URL")
_SKIP_REASON = (
    "PG_TEST_URL is not set; start Postgres with "
    "`docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16` and "
    "export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres"
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Keep every test away from the real .env.local and the real Neon database."""
    missing = tmp_path_factory.getbasetemp() / "no-such.env"
    monkeypatch.setenv("SEER_ENV_FILE", str(missing))
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", "postgresql://tests-must-not-use-this.invalid/none")
    monkeypatch.setattr(config, "_loaded", False)


@pytest.fixture(autouse=True)
def _drop_cli_log_handler() -> Iterator[None]:
    """cli.main() installs a stderr handler bound to the current (captured) stream;
    remove it after each test so later tests never log to a closed stream."""
    yield
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_seer_engine_handler", False):
            root.removeHandler(h)


@dataclass(frozen=True)
class PgSchema:
    conn: psycopg.Connection
    name: str
    url: str  # conninfo that lands in this schema; for code that opens its own connection


@pytest.fixture
def pg_url() -> str:
    if not _PG_TEST_URL:
        pytest.skip(_SKIP_REASON)
    return _PG_TEST_URL


@pytest.fixture
def pg_schema(pg_url: str) -> Iterator[PgSchema]:
    """A connection whose search_path is a fresh, empty schema (no migrations applied)."""
    name = f"t_{uuid.uuid4().hex[:12]}"
    conn = psycopg.connect(pg_url, autocommit=False, connect_timeout=15)
    conn.execute(f'CREATE SCHEMA "{name}"')
    conn.execute(f'SET search_path TO "{name}"')
    conn.commit()  # a SET inside a rolled-back transaction would be undone
    try:
        yield PgSchema(conn, name, make_conninfo(pg_url, options=f"-c search_path={name}"))
    finally:
        conn.close()
        with psycopg.connect(pg_url, autocommit=True, connect_timeout=15) as admin:
            admin.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')


@pytest.fixture
def pg_empty(pg_schema: PgSchema) -> psycopg.Connection:
    """Connection to an empty throwaway schema."""
    return pg_schema.conn


@pytest.fixture
def pg(pg_schema: PgSchema) -> psycopg.Connection:
    """Connection to a throwaway schema with every db/migrations/*.sql applied, committed."""
    conn = pg_schema.conn
    for path in sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name):
        conn.execute(path.read_text(encoding="utf-8"))
    conn.commit()
    return conn


@pytest.fixture
def utc() -> Callable[..., datetime]:
    """Fixed-clock factory: utc(2026, 10, 2, 23) -> 2026-10-02T23:00:00+00:00."""

    def make(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
        return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)

    return make
```
**Impact:** The autouse env isolation applies to the test files of phases 2–4 as well. Their tests can never read `.env.local` or reach Neon. A test that needs `MASSIVE_API_KEY` must set it with `monkeypatch.setenv`.

### Step 15: Date tests
**File:** `engine/tests/test_dates.py:1` (new)
**Code:**
```python
"""NYSE date logic under fixed UTC clocks (handover §6.4). No database needed."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from seer_engine import dates
from seer_engine.dates import RunDates, run_dates


def D(s: str) -> date:
    return date.fromisoformat(s)


@pytest.mark.parametrize(
    ("now", "data_date", "session_date"),
    [
        # Friday night run -> Monday.
        ((2026, 10, 2, 23), "2026-10-02", "2026-10-05"),
        # Friday before Labor Day (Mon 2026-09-07) -> Tuesday.
        ((2026, 9, 4, 23), "2026-09-04", "2026-09-08"),
        # Friday before Memorial Day (Mon 2026-05-25) -> Tuesday.
        ((2026, 5, 22, 23), "2026-05-22", "2026-05-26"),
        # Run on the holiday Monday itself: same answer as Friday's run.
        ((2026, 9, 7, 23), "2026-09-04", "2026-09-08"),
        ((2026, 5, 25, 23), "2026-05-22", "2026-05-26"),
        # Saturday and Sunday runs also target Monday.
        ((2026, 10, 3, 23), "2026-10-02", "2026-10-05"),
        ((2026, 10, 4, 23), "2026-10-02", "2026-10-05"),
        # Ordinary weeknight.
        ((2026, 10, 6, 23), "2026-10-06", "2026-10-07"),
        # Before the close on a weekday: data is the previous session, picks are for today.
        ((2026, 10, 7, 15), "2026-10-06", "2026-10-07"),
        # Early-morning UTC run (06:00 WIB is 23:00 UTC the day before; 01:00 UTC retry slot).
        ((2026, 10, 6, 1), "2026-10-05", "2026-10-06"),
        # Thanksgiving week: Wed run skips Thanksgiving (Thu 2026-11-26) to the half day.
        ((2026, 11, 25, 23), "2026-11-25", "2026-11-27"),
        ((2026, 11, 26, 23), "2026-11-25", "2026-11-27"),
        # Half day Fri 2026-11-27 closes 13:00 ET = 18:00 UTC; settled at 19:00 UTC.
        ((2026, 11, 27, 18, 30), "2026-11-25", "2026-11-27"),
        ((2026, 11, 27, 19), "2026-11-27", "2026-11-30"),
        ((2026, 11, 27, 23), "2026-11-27", "2026-11-30"),
        # Good Friday 2026-04-03 is a full NYSE holiday.
        ((2026, 4, 2, 23), "2026-04-02", "2026-04-06"),
        ((2026, 4, 3, 23), "2026-04-02", "2026-04-06"),
        # Year end: Thu 2026-12-31 -> Mon 2027-01-04 (New Year's Day is Friday).
        ((2026, 12, 31, 23), "2026-12-31", "2027-01-04"),
        ((2027, 1, 1, 23), "2026-12-31", "2027-01-04"),
    ],
)
def test_run_dates(utc, now, data_date, session_date):
    assert run_dates(utc(*now)) == RunDates(D(data_date), D(session_date))


@pytest.mark.parametrize(
    ("now", "data_date"),
    [
        # EDT (before 2026-11-01): close 20:00 UTC, settled from 21:00 UTC.
        ((2026, 10, 30, 20, 59), "2026-10-29"),
        ((2026, 10, 30, 21, 0), "2026-10-30"),
        # EST (after 2026-11-01): close 21:00 UTC, settled from 22:00 UTC.
        ((2026, 11, 2, 21, 30), "2026-10-30"),
        ((2026, 11, 2, 22, 0), "2026-11-02"),
        # EST before 2026-03-08: Fri 2026-03-06 settles at 22:00 UTC.
        ((2026, 3, 6, 21, 30), "2026-03-05"),
        ((2026, 3, 6, 22, 0), "2026-03-06"),
        # EDT after 2026-03-08: Mon 2026-03-09 settles at 21:00 UTC.
        ((2026, 3, 9, 20, 59), "2026-03-06"),
        ((2026, 3, 9, 21, 0), "2026-03-09"),
    ],
)
def test_last_completed_session_across_dst(utc, now, data_date):
    assert dates.last_completed_session(utc(*now)) == D(data_date)


def test_settle_margin_is_configurable(utc):
    # 20:30 UTC on an EDT day: closed but not settled with the default 1h margin.
    now = utc(2026, 10, 6, 20, 30)
    assert dates.last_completed_session(now) == D("2026-10-05")
    assert dates.last_completed_session(now, settle=timedelta(0)) == D("2026-10-06")


def test_non_utc_aware_now_is_converted():
    wib = timezone(timedelta(hours=7))
    # 06:00 WIB Saturday == 23:00 UTC Friday.
    assert run_dates(datetime(2026, 10, 3, 6, 0, tzinfo=wib)) == RunDates(
        D("2026-10-02"), D("2026-10-05")
    )


def test_naive_now_is_rejected():
    with pytest.raises(ValueError):
        dates.last_completed_session(datetime(2026, 10, 2, 23))


def test_datetime_is_not_a_date():
    with pytest.raises(TypeError):
        dates.is_session(datetime(2026, 10, 2, tzinfo=timezone.utc))


def test_sessions_inclusive_and_skip_holidays():
    assert dates.sessions(D("2026-04-01"), D("2026-04-07")) == [
        D("2026-04-01"),
        D("2026-04-02"),
        D("2026-04-06"),
        D("2026-04-07"),
    ]
    assert dates.sessions(D("2026-04-03"), D("2026-04-03")) == []
    assert dates.sessions(D("2026-04-07"), D("2026-04-01")) == []


def test_sessions_span_year_boundary():
    assert dates.sessions(D("2026-12-30"), D("2027-01-05")) == [
        D("2026-12-30"),
        D("2026-12-31"),
        D("2027-01-04"),
        D("2027-01-05"),
    ]


def test_is_session():
    assert dates.is_session(D("2026-11-27"))  # half day is a session
    assert not dates.is_session(D("2026-11-26"))  # Thanksgiving
    assert not dates.is_session(D("2026-04-03"))  # Good Friday
    assert not dates.is_session(D("2026-10-03"))  # Saturday


def test_next_and_prev_session():
    assert dates.next_session(D("2026-10-02")) == D("2026-10-05")
    assert dates.next_session(D("2026-10-03")) == D("2026-10-05")
    assert dates.prev_session(D("2026-10-05")) == D("2026-10-02")
    assert dates.prev_session(D("2026-09-08")) == D("2026-09-04")
    assert dates.prev_session(D("2027-01-04")) == D("2026-12-31")


def test_session_close_utc():
    assert dates.session_close_utc(D("2026-11-27")) == datetime(2026, 11, 27, 18, tzinfo=timezone.utc)
    assert dates.session_close_utc(D("2026-10-02")) == datetime(2026, 10, 2, 20, tzinfo=timezone.utc)
    assert dates.session_close_utc(D("2026-12-01")) == datetime(2026, 12, 1, 21, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        dates.session_close_utc(D("2026-11-26"))


def test_run_dates_defaults_to_now():
    rd = run_dates()
    assert rd.session_date > rd.data_date
    assert dates.is_session(rd.data_date) and dates.is_session(rd.session_date)
```

### Step 16: CLI and config tests
**File:** `engine/tests/test_cli.py:1` (new)
**Code:**
```python
"""Command discovery, global flags and exit codes. No database needed."""

from __future__ import annotations

import re
import sys
import textwrap

import pytest

from seer_engine import cli, commands, config


def test_discovers_migrate():
    assert "migrate" in cli.discover()


def test_help_lists_migrate(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "migrate" in capsys.readouterr().out


@pytest.fixture
def fake_command(tmp_path, monkeypatch):
    """Drop a new module into the commands package path, as a later phase would."""
    (tmp_path / "zz_fake.py").write_text(
        textwrap.dedent(
            '''
            HELP = "fake command for tests"
            CALLS = []

            def add_arguments(p):
                p.add_argument("--code", type=int, default=0)
                p.add_argument("--boom", choices=["none", "error", "config"], default="none")

            def run(args):
                CALLS.append(args)
                if args.boom == "error":
                    raise RuntimeError("boom")
                if args.boom == "config":
                    from seer_engine.config import ConfigError
                    raise ConfigError("MISSING is not set")
                return args.code
            '''
        )
    )
    monkeypatch.setattr(commands, "__path__", [*commands.__path__, str(tmp_path)])
    yield "zz_fake"
    sys.modules.pop("seer_engine.commands.zz_fake", None)


def test_new_module_becomes_a_command_without_editing_cli(fake_command):
    assert fake_command in cli.discover()
    assert cli.main([fake_command]) == 0
    module = sys.modules["seer_engine.commands.zz_fake"]
    args = module.CALLS[-1]
    assert args.dry_run is False and args.verbose == 0


def test_return_value_is_exit_code(fake_command):
    assert cli.main([fake_command, "--code", "3"]) == 3


@pytest.mark.parametrize(
    "argv",
    [["--dry-run", "zz_fake"], ["zz_fake", "--dry-run"], ["-v", "zz_fake", "--dry-run"]],
)
def test_dry_run_flag_either_side_of_command(fake_command, argv):
    assert cli.main(argv) == 0
    args = sys.modules["seer_engine.commands.zz_fake"].CALLS[-1]
    assert args.dry_run is True


def test_verbose_flag(fake_command):
    cli.main(["-v", fake_command])
    assert sys.modules["seer_engine.commands.zz_fake"].CALLS[-1].verbose == 1


def test_exception_exits_1(fake_command, capsys):
    assert cli.main([fake_command, "--boom", "error"]) == 1
    assert "boom" in capsys.readouterr().err


def test_config_error_exits_2(fake_command, capsys):
    assert cli.main([fake_command, "--boom", "config"]) == 2
    assert "MISSING is not set" in capsys.readouterr().err


def test_logs_go_to_stderr_with_utc_timestamps(fake_command, capsys):
    cli.main(["--dry-run", fake_command])
    out, err = capsys.readouterr()
    assert out == ""
    assert re.search(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ INFO ", err, re.M)


def test_config_load_env_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / "x.env"
    env.write_text("SEER_T_A=from-file\nSEER_T_B=a&b\n")
    monkeypatch.setenv("SEER_ENV_FILE", str(env))
    monkeypatch.setenv("SEER_T_A", "from-env")
    monkeypatch.setenv("SEER_T_B", "placeholder")
    monkeypatch.delenv("SEER_T_B")  # absent now, and removed again on teardown
    assert config.load_env() == env
    assert config.get("SEER_T_A") == "from-env"
    assert config.get("SEER_T_B") == "a&b"


def test_config_require_raises(monkeypatch):
    monkeypatch.delenv("SEER_T_MISSING", raising=False)
    with pytest.raises(config.ConfigError):
        config.require("SEER_T_MISSING")
```

### Step 17: Migrate tests
**File:** `engine/tests/test_migrate.py:1` (new)
**Code:**
```python
"""The Python migration runner (shares schema_migrations with web/scripts/migrate.mjs)."""

from __future__ import annotations

import pytest

from seer_engine import cli
from seer_engine.commands.migrate import MIGRATIONS_DIR, apply_migrations, migration_files

ALL = [p.name for p in migration_files(MIGRATIONS_DIR)]


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
    ).fetchall()
    return {r[0] for r in rows}


def test_repo_has_001_and_002():
    assert ALL[:2] == ["001_init.sql", "002_engine.sql"]


def test_applies_all_then_nothing(pg_empty):
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == ALL
    assert {"runs", "bars", "universe", "split_adjustments", "backfill_log"} <= _tables(pg_empty)
    names = [r[0] for r in pg_empty.execute("SELECT name FROM schema_migrations ORDER BY name")]
    assert names == ALL
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == []


def test_respects_rows_written_by_the_node_runner(pg_empty):
    pg_empty.execute(
        "CREATE TABLE schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    pg_empty.execute((MIGRATIONS_DIR / "001_init.sql").read_text())
    pg_empty.execute("INSERT INTO schema_migrations (name) VALUES ('001_init.sql')")
    pg_empty.commit()
    assert apply_migrations(pg_empty, MIGRATIONS_DIR) == [n for n in ALL if n != "001_init.sql"]


def test_dry_run_writes_nothing(pg_empty):
    assert apply_migrations(pg_empty, MIGRATIONS_DIR, dry_run=True) == ALL
    assert _tables(pg_empty) == set()


def test_dry_run_after_apply_reports_nothing(pg_empty):
    apply_migrations(pg_empty, MIGRATIONS_DIR)
    assert apply_migrations(pg_empty, MIGRATIONS_DIR, dry_run=True) == []
    count = pg_empty.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == len(ALL)


def test_failed_file_rolls_back_only_itself(pg_empty, tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE ok_t (x int);")
    (tmp_path / "002_bad.sql").write_text("CREATE TABLE bad_t (x int); SELECT no_such_column FROM ok_t;")
    with pytest.raises(Exception):
        apply_migrations(pg_empty, tmp_path)
    assert "ok_t" in _tables(pg_empty)
    assert "bad_t" not in _tables(pg_empty)
    names = [r[0] for r in pg_empty.execute("SELECT name FROM schema_migrations")]
    assert names == ["001_ok.sql"]


def test_cli_dry_run_against_test_db(pg_schema, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", pg_schema.url)
    assert cli.main(["--dry-run", "migrate"]) == 0
    assert _tables(pg_schema.conn) == set()
    assert cli.main(["migrate"]) == 0
    pg_schema.conn.rollback()  # see the other connection's committed work
    count = pg_schema.conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == len(ALL)
```

### Step 18: Bars tests
**File:** `engine/tests/test_bars.py:1` (new)
**Code:**
```python
"""Bar construction and idempotent upserts into ``bars``."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from seer_engine.bars import Bar, delete_bars_on, latest_bar_date, make_bar, upsert_bars

D1 = date(2026, 10, 1)
D2 = date(2026, 10, 2)


def _bars() -> list[Bar]:
    return [
        make_bar("SPY", D1, 764.36, 765.65, 758.7901, 763.99, 47708058.813089),
        make_bar("BRK.B", D1, "480.1", "482", "478.25", "481.5", 3_000_000),
        make_bar("SPY", D2, 764.0, 766.0, 760.0, 765.12345, 40_000_000),
    ]


def _xmins(conn) -> dict[tuple[str, date], str]:
    rows = conn.execute("SELECT symbol, date, xmin::text FROM bars").fetchall()
    return {(r[0], r[1]): r[2] for r in rows}


def test_make_bar_rounds_to_4dp_and_int_volume():
    b = make_bar("SPY", D1, 764.36, 765.65, 758.79005, 0.1, 47708058.813089)
    assert b.open == Decimal("764.3600")
    assert b.low == Decimal("758.7901")  # half-up
    assert b.close == Decimal("0.1000")  # float via shortest repr, not binary expansion
    assert b.volume == 47708059 and isinstance(b.volume, int)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_make_bar_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        make_bar("SPY", D1, bad, 1, 1, 1, 1)


def test_make_bar_rejects_negative_volume_and_datetime():
    from datetime import datetime

    with pytest.raises(ValueError):
        make_bar("SPY", D1, 1, 1, 1, 1, -1)
    with pytest.raises(TypeError):
        make_bar("SPY", datetime(2026, 10, 1), 1, 1, 1, 1, 1)


def test_bar_is_frozen():
    b = _bars()[0]
    with pytest.raises(AttributeError):
        b.close = Decimal("1")  # type: ignore[misc]


def test_upsert_inserts_then_identical_rerun_changes_nothing(pg):
    assert upsert_bars(pg, _bars()) == 3
    pg.commit()
    before = _xmins(pg)
    assert upsert_bars(pg, _bars()) == 0
    pg.commit()
    assert _xmins(pg) == before  # no new row versions either


def test_upsert_counts_only_changed_rows(pg):
    upsert_bars(pg, _bars())
    changed = _bars()
    changed[0] = make_bar("SPY", D1, 764.36, 765.65, 758.7901, 770.0, 47708058.813089)
    assert upsert_bars(pg, changed) == 1
    close = pg.execute("SELECT close FROM bars WHERE symbol='SPY' AND date=%s", (D1,)).fetchone()[0]
    assert close == Decimal("770.0000")


def test_upsert_volume_change_counts(pg):
    upsert_bars(pg, _bars())
    b = _bars()[1]
    assert upsert_bars(pg, [make_bar(b.symbol, b.date, b.open, b.high, b.low, b.close, 1)]) == 1


def test_upsert_twice_in_one_transaction(pg):
    assert upsert_bars(pg, _bars()[:1]) == 1
    assert upsert_bars(pg, _bars()[1:]) == 2
    assert pg.execute("SELECT count(*) FROM bars").fetchone()[0] == 3


def test_upsert_rejects_duplicate_keys_in_batch(pg):
    b = _bars()[0]
    with pytest.raises(ValueError, match="duplicate"):
        upsert_bars(pg, [b, b])


def test_upsert_empty_is_zero(pg):
    assert upsert_bars(pg, []) == 0


def test_latest_bar_date_and_delete(pg):
    assert latest_bar_date(pg, "SPY") is None
    upsert_bars(pg, _bars())
    assert latest_bar_date(pg, "SPY") == D2
    assert latest_bar_date(pg, "BRK.B") == D1
    assert delete_bars_on(pg, D1) == 2
    assert latest_bar_date(pg, "BRK.B") is None
    assert delete_bars_on(pg, D1) == 0
```

### Step 19: FX tests
**File:** `engine/tests/test_fx.py:1` (new)
**Code:**
```python
"""Frankfurter parsing (fake HTTP) and idempotent ``fx_rates`` upserts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from seer_engine import fx


@pytest.fixture
def fake_get_json(monkeypatch):
    calls: list[tuple[str, dict | None]] = []
    responses: dict[str, dict] = {}

    def get_json(url, params=None, **_kw):
        calls.append((url, params))
        return responses[url]

    monkeypatch.setattr(fx.http, "get_json", get_json)
    return calls, responses


def test_fetch_latest(fake_get_json):
    calls, responses = fake_get_json
    responses[f"{fx.FRANKFURTER}/latest"] = {
        "amount": 1.0,
        "base": "USD",
        "date": "2026-10-02",
        "rates": {"IDR": 17950.0},
    }
    assert fx.fetch_latest() == (date(2026, 10, 2), Decimal("17950.0000"))
    assert calls == [(f"{fx.FRANKFURTER}/latest", {"base": "USD", "symbols": "IDR"})]


def test_fetch_latest_without_idr_raises(fake_get_json):
    _, responses = fake_get_json
    responses[f"{fx.FRANKFURTER}/latest"] = {"date": "2026-10-02", "rates": {}}
    with pytest.raises(ValueError):
        fx.fetch_latest()


def test_fetch_range_chunks_per_calendar_year(fake_get_json):
    calls, responses = fake_get_json
    responses[f"{fx.FRANKFURTER}/2024-12-30..2024-12-31"] = {
        "rates": {
            "2024-12-27": {"IDR": 16200.5},  # outside the chunk: ignored
            "2024-12-30": {"IDR": 16100.12345},
            "2024-12-31": {"IDR": 16150},
        }
    }
    responses[f"{fx.FRANKFURTER}/2025-01-01..2025-12-31"] = {
        "rates": {"2025-01-02": {"IDR": 16200}}
    }
    responses[f"{fx.FRANKFURTER}/2026-01-01..2026-01-05"] = {
        "rates": {"2026-01-05": {"IDR": 16700}}
    }
    out = fx.fetch_range(date(2024, 12, 30), date(2026, 1, 5))
    assert [u for u, _ in calls] == [
        f"{fx.FRANKFURTER}/2024-12-30..2024-12-31",
        f"{fx.FRANKFURTER}/2025-01-01..2025-12-31",
        f"{fx.FRANKFURTER}/2026-01-01..2026-01-05",
    ]
    assert out == [
        (date(2024, 12, 30), Decimal("16100.1235")),
        (date(2024, 12, 31), Decimal("16150.0000")),
        (date(2025, 1, 2), Decimal("16200.0000")),
        (date(2026, 1, 5), Decimal("16700.0000")),
    ]


def test_fetch_range_empty_when_reversed(fake_get_json):
    calls, _ = fake_get_json
    assert fx.fetch_range(date(2026, 1, 2), date(2026, 1, 1)) == []
    assert calls == []


def test_upsert_fx_idempotent(pg):
    rows = [(date(2026, 10, 1), Decimal("17900")), (date(2026, 10, 2), 17950.0)]
    assert fx.upsert_fx(pg, rows) == 2
    pg.commit()
    assert fx.upsert_fx(pg, rows) == 0
    assert fx.upsert_fx(pg, [(date(2026, 10, 2), "17950.00001")]) == 0  # rounds to the same
    assert fx.upsert_fx(pg, [(date(2026, 10, 2), "17960")]) == 1
    rate = pg.execute("SELECT usd_idr FROM fx_rates WHERE date='2026-10-02'").fetchone()[0]
    assert rate == Decimal("17960.0000")


def test_upsert_fx_rejects_conflicting_duplicates(pg):
    with pytest.raises(ValueError):
        fx.upsert_fx(pg, [(date(2026, 10, 2), 1), (date(2026, 10, 2), 2)])


def test_upsert_fx_empty(pg):
    assert fx.upsert_fx(pg, []) == 0
```

### Step 20: Runs tests
**File:** `engine/tests/test_runs.py:1` (new)
**Code:**
```python
"""The runs lifecycle: one real row per session, success is final, failures are reused."""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

from seer_engine.dates import RunDates
from seer_engine.runs import MAX_ERROR_CHARS, fail_run, finish_run, start_run

RD = RunDates(data_date=date(2026, 10, 2), session_date=date(2026, 10, 5))


def _row(conn, run_id):
    return conn.execute(
        "SELECT status, data_date, session_date, is_demo, error, finished_at FROM runs WHERE id = %s",
        (run_id,),
    ).fetchone()


def test_start_then_finish(pg):
    run_id = start_run(pg, RD)
    assert isinstance(run_id, int)
    status, data_date, session_date, is_demo, error, finished_at = _row(pg, run_id)
    assert (status, data_date, session_date, is_demo, error, finished_at) == (
        "running", RD.data_date, RD.session_date, False, None, None
    )
    finish_run(pg, run_id)
    status, *_rest, error, finished_at = _row(pg, run_id)
    assert status == "success" and error is None and finished_at is not None


def test_rerun_after_success_is_a_no_op(pg):
    run_id = start_run(pg, RD)
    finish_run(pg, run_id)
    pg.commit()
    before = pg.execute("SELECT *, xmin::text FROM runs").fetchall()
    assert start_run(pg, RD) is None
    pg.commit()
    assert pg.execute("SELECT *, xmin::text FROM runs").fetchall() == before


def test_failed_row_is_reused(pg):
    run_id = start_run(pg, RD)
    fail_run(pg, run_id, "Massive returned HTTP 500")
    assert _row(pg, run_id)[0] == "failed"
    later = RunDates(data_date=date(2026, 10, 2), session_date=RD.session_date)
    assert start_run(pg, later) == run_id
    status, *_rest, error, finished_at = _row(pg, run_id)
    assert (status, error, finished_at) == ("running", None, None)
    assert pg.execute("SELECT count(*) FROM runs").fetchone()[0] == 1


def test_interrupted_running_row_is_reused(pg):
    run_id = start_run(pg, RD)
    assert start_run(pg, RD) == run_id


def test_fail_run_truncates_and_redacts(pg):
    run_id = start_run(pg, RD)
    fail_run(pg, run_id, "GET https://api.massive.com/x?apiKey=SECRET123 failed " + "x" * 5000)
    error = _row(pg, run_id)[4]
    assert len(error) == MAX_ERROR_CHARS
    assert "SECRET123" not in error and "apiKey=REDACTED" in error


def test_demo_run_on_same_session_does_not_conflict(pg):
    pg.execute(
        "INSERT INTO runs (status, data_date, session_date, is_demo) VALUES ('success', %s, %s, true)",
        (RD.data_date, RD.session_date),
    )
    run_id = start_run(pg, RD)
    assert run_id is not None
    assert pg.execute("SELECT count(*) FROM runs").fetchone()[0] == 2


def test_unique_index_rejects_second_real_row(pg):
    start_run(pg, RD)
    with pytest.raises(psycopg.errors.UniqueViolation):
        pg.execute(
            "INSERT INTO runs (status, data_date, session_date) VALUES ('running', %s, %s)",
            (RD.data_date, RD.session_date),
        )


def test_finish_unknown_run_raises(pg):
    with pytest.raises(LookupError):
        finish_run(pg, 999_999)
    with pytest.raises(LookupError):
        fail_run(pg, 999_999, "x")
```

### Step 21: Demo purge tests
**File:** `engine/tests/test_demo.py:1` (new)
**Code:**
```python
"""Demo purge: all-or-nothing, keyed on the existence of a demo run, strategies kept."""

from __future__ import annotations

from datetime import date

import psycopg

from seer_engine.demo import DEMO_TABLES, has_demo, purge_demo, purge_demo_if_needed

D = date(2026, 10, 2)
S = date(2026, 10, 5)


def _seed(conn, *, demo: bool) -> None:
    """A slice of what web/scripts/seed-demo.mjs writes."""
    conn.execute(
        "INSERT INTO strategies (id, name, sub, icon, sort) VALUES "
        "('A', 'A · Quant', 'Mean Reversion', 'sigma', 1), ('SPY', 'SPY', 'Benchmark', 'flag', 9)"
    )
    conn.execute(
        "INSERT INTO runs (status, data_date, session_date, is_demo, finished_at) "
        "VALUES ('success', %s, %s, %s, now())",
        (D, S, demo),
    )
    conn.execute("INSERT INTO fx_rates (date, usd_idr) VALUES (%s, 16530)", (D,))
    conn.execute("INSERT INTO bars VALUES ('NVDA', %s, 180, 180, 180, 180, 1000000)", (D,))
    order_id = conn.execute(
        "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, "
        "limit_price, tp_price, sl_price, shares, status) "
        "VALUES ('A', %s, 1, 'NVDA', 'NVIDIA', 180, 178, 185, 172, 10, 'pending') RETURNING id",
        (S,),
    ).fetchone()[0]
    conn.execute("INSERT INTO action_dismissals (order_id) VALUES (%s)", (order_id,))
    conn.execute(
        "INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ('A', %s, 1000, 1000)",
        (D,),
    )
    conn.commit()


def _counts(conn) -> dict[str, int]:
    return {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in (*DEMO_TABLES, "strategies")
    }


def test_purge_empties_demo_tables_and_keeps_strategies(pg):
    _seed(pg, demo=True)
    assert has_demo(pg)
    assert purge_demo(pg) is True
    pg.commit()
    counts = _counts(pg)
    assert all(counts[t] == 0 for t in DEMO_TABLES)
    assert counts["strategies"] == 2


def test_purge_restarts_identity(pg):
    _seed(pg, demo=True)
    purge_demo(pg)
    new_id = pg.execute(
        "INSERT INTO runs (status, is_demo) VALUES ('running', false) RETURNING id"
    ).fetchone()[0]
    assert new_id == 1


def test_no_demo_run_is_a_no_op(pg):
    _seed(pg, demo=False)
    before = _counts(pg)
    assert purge_demo(pg) is False
    assert _counts(pg) == before


def test_purge_if_needed_commits_in_its_own_transaction(pg, pg_schema):
    _seed(pg, demo=True)
    assert purge_demo_if_needed(pg, dry_run=False) is True
    with psycopg.connect(pg_schema.url) as other:
        assert other.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert other.execute("SELECT count(*) FROM strategies").fetchone()[0] == 2
    assert purge_demo_if_needed(pg, dry_run=False) is False


def test_purge_if_needed_dry_run_keeps_everything(pg):
    _seed(pg, demo=True)
    before = _counts(pg)
    assert purge_demo_if_needed(pg, dry_run=True) is True
    assert _counts(pg) == before


def test_purge_is_atomic_with_the_callers_transaction(pg):
    _seed(pg, demo=True)
    before = _counts(pg)
    purge_demo(pg)
    pg.rollback()
    assert _counts(pg) == before
```

### Step 22: Universe query tests
**File:** `engine/tests/test_universe_queries.py:1` (new)
**Code:**
```python
"""Point-in-time queries on ``universe`` (end_date exclusive, NULL = current)."""

from __future__ import annotations

from datetime import date

from seer_engine.universe import BENCHMARK, all_symbols, members_on, symbols_for_bars

ROWS = [
    # symbol, index_id, start, end (exclusive), source_symbol
    ("AAPL", "SP500", "2015-01-02", None, "AAPL"),
    ("AAPL", "NDX", "2015-01-02", None, "AAPL"),
    ("META", "SP500", "2015-01-02", None, "FB"),
    ("OLD", "SP500", "2015-01-02", "2020-06-01", "OLD"),
    ("LEFT", "NDX", "2018-01-02", "2026-09-21", "LEFT"),
    ("NEW", "SP500", "2026-09-21", None, "NEW"),
    # Left and came back: two intervals.
    ("BACK", "SP500", "2016-01-04", "2018-01-02", "BACK"),
    ("BACK", "SP500", "2020-01-02", None, "BACK"),
]


def _load(conn) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
            "VALUES (%s, %s, %s, %s, %s)",
            ROWS,
        )


def test_members_on(pg):
    _load(pg)
    assert members_on(pg, date(2026, 9, 18)) == {"AAPL", "META", "LEFT", "BACK"}
    # end_date is exclusive, start_date inclusive.
    assert members_on(pg, date(2026, 9, 21)) == {"AAPL", "META", "BACK", "NEW"}
    assert members_on(pg, date(2019, 1, 2)) == {"AAPL", "META", "OLD", "LEFT"}
    assert BENCHMARK not in members_on(pg, date(2026, 9, 21))


def test_symbols_for_bars_keeps_recent_leavers_and_spy(pg):
    _load(pg)
    d = date(2026, 10, 2)  # LEFT left 11 days ago
    assert symbols_for_bars(pg, d) == {"AAPL", "META", "BACK", "NEW", "LEFT", "SPY"}
    assert symbols_for_bars(pg, d, grace_days=5) == {"AAPL", "META", "BACK", "NEW", "SPY"}
    assert "NEW" not in symbols_for_bars(pg, date(2026, 9, 18))


def test_all_symbols_since(pg):
    _load(pg)
    assert all_symbols(pg, date(2015, 1, 2)) == [
        "AAPL", "BACK", "LEFT", "META", "NEW", "OLD", "SPY"
    ]
    assert all_symbols(pg, date(2021, 1, 4)) == ["AAPL", "BACK", "LEFT", "META", "NEW", "SPY"]


def test_empty_universe_still_has_benchmark(pg):
    assert symbols_for_bars(pg, date(2026, 10, 2)) == {"SPY"}
    assert all_symbols(pg, date(2015, 1, 2)) == ["SPY"]
    assert members_on(pg, date(2026, 10, 2)) == set()


def test_check_constraints(pg):
    import psycopg
    import pytest

    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute(
            "INSERT INTO universe VALUES ('X', 'SP500', '2020-01-02', '2020-01-02', 'X')"
        )
    pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("INSERT INTO universe VALUES ('X', 'DJI', '2020-01-02', NULL, 'X')")
```

### Step 23: HTTP tests
**File:** `engine/tests/test_http.py:1` (new)
**Code:**
```python
"""Retry policy and redaction of the shared HTTP helper (no network)."""

from __future__ import annotations

import pytest
import requests

from seer_engine import http


class _Resp:
    def __init__(self, status: int, body=None, headers=None, url="https://x.test/a?apiKey=SECRET"):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.url = url
        self.text = "" if body is None else str(body)

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


@pytest.fixture
def fake(monkeypatch):
    queue: list = []
    sleeps: list[float] = []

    class _Session:
        def get(self, url, params=None, timeout=None):
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    monkeypatch.setattr(http, "_session", _Session())
    monkeypatch.setattr(http, "_sleep", sleeps.append)
    return queue, sleeps


def test_redact():
    assert http.redact("https://api.massive.com/v2/x?adjusted=true&apiKey=abc123") == (
        "https://api.massive.com/v2/x?adjusted=true&apiKey=REDACTED"
    )
    assert http.redact("https://h/x?api_key=a&token=b") == "https://h/x?api_key=REDACTED&token=REDACTED"
    assert http.redact("https://api.frankfurter.dev/v1/latest?base=USD") == (
        "https://api.frankfurter.dev/v1/latest?base=USD"
    )


def test_returns_json(fake):
    queue, sleeps = fake
    queue.append(_Resp(200, {"ok": True}))
    assert http.get_json("https://x.test/a") == {"ok": True}
    assert sleeps == []


def test_retries_429_5xx_and_connection_errors(fake):
    queue, sleeps = fake
    queue.extend([_Resp(429), requests.ConnectionError("down"), _Resp(503), _Resp(200, {"ok": 1})])
    assert http.get_json("https://x.test/a", backoff=1.0) == {"ok": 1}
    assert sleeps == [1.0, 2.0, 4.0]


def test_retry_after_header_wins_when_longer(fake):
    queue, sleeps = fake
    queue.extend([_Resp(429, headers={"Retry-After": "61"}), _Resp(200, {"ok": 1})])
    http.get_json("https://x.test/a", backoff=5.0)
    assert sleeps == [61.0]


def test_gives_up_after_retries_and_redacts(fake):
    queue, _ = fake
    queue.extend([_Resp(500)] * 4)
    with pytest.raises(http.HttpError) as exc:
        http.get_json("https://x.test/a", retries=3, backoff=0)
    assert exc.value.status == 500
    assert "SECRET" not in str(exc.value)


def test_4xx_is_not_retried(fake):
    queue, sleeps = fake
    queue.append(_Resp(403, {"status": "NOT_AUTHORIZED"}))
    with pytest.raises(http.HttpError):
        http.get_json("https://x.test/a")
    assert sleeps == []
```

## Verification

Run these from the worktree root in zsh. The DB tests **must run, not skip**. The container may already exist from planning (`seer-pg` was started on port 55432 while this plan was prototyped), so `docker start` comes first.

```zsh
cd /home/miftah/.worktrees/seer/engine-data-pipeline

# 1. venv + install (Step 1)
python3.11 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'

# 2. local Postgres 16 for DB tests
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
docker exec seer-pg pg_isready -U postgres -t 60
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres

# 3. full suite, skips reported; expect "101 passed" and no "SKIPPED" lines
engine/.venv/bin/pytest engine/tests -q -rs

# 4. CLI lists migrate
engine/.venv/bin/python -m seer_engine --help | grep -w migrate

# 5. migrate --dry-run against the test DB writes nothing (never against Neon here)
DATABASE_URL_UNPOOLED=$PG_TEST_URL SEER_ENV_FILE=/nonexistent \
  engine/.venv/bin/python -m seer_engine --dry-run migrate
docker exec seer-pg psql -U postgres -tAc "select coalesce(to_regclass('public.schema_migrations')::text, 'absent')"
```

**Build:** `engine/.venv/bin/pip install -e 'engine[dev]'` succeeds.
**Tests:** `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs` → `101 passed`, 0 skipped. Without `PG_TEST_URL`: `66 passed, 35 skipped`, and every skip reason quotes the docker command.
**Manual check:** Step 5 logs `would apply 001_init.sql` and `would apply 002_engine.sql` with `…Z INFO` UTC timestamps on stderr, exits 0, and `psql` then prints `absent`. `cd web && npx vitest run` is unaffected, since this phase touches nothing in `web/`.
**Exit criteria:** `python -m seer_engine --help` lists `migrate`. `python -m seer_engine --dry-run migrate` against `PG_TEST_URL` exits 0 and leaves no `schema_migrations`. All 101 tests pass against Postgres 16, including the handover §6.4 date cases. `test_upsert_inserts_then_identical_rerun_changes_nothing` and `test_upsert_fx_idempotent` prove that a second identical upsert returns 0 and leaves `xmin` unchanged.

## Handoffs

- **Phase 2 (R2 content):** fills `universe` with `index_id IN ('SP500','NDX')`, symbols in dot form, and `end_date` **exclusive** (the first day *not* a member). `CHECK (end_date > start_date)` rejects zero-length intervals, so drop them before insert. `universe refresh` should run `demo.purge_demo_if_needed` first (invariant 6) and replace the table inside `db.transaction(conn, args.dry_run)`.
- **Phase 3 (R1):** dedupe `(symbol, date)` before `upsert_bars`, which raises on duplicates within a batch. Write `backfill_log` (Phase 1 only creates it). Hold the connection with `contextlib.closing(db.connect())`.
- **Phase 4 (R3):** the `runs` helpers do not commit. A row created by `start_run` inside a transaction that later rolls back disappears, and `fail_run` then raises `LookupError`. The nightly flow must therefore commit `start_run` in its own transaction **before** fetching (status `running` is visible to nobody: the web reads only `success`), do bars, splits, FX and `finish_run` in a second transaction, and on error call `fail_run` in a third. Pass the Massive key as `params={"apiKey": …}` so `http` redacts it. `finished_at` uses `clock_timestamp()`. Writes to `split_adjustments` belong to Phase 4.
- **Phase 5 (R1/R3/R5 operations):** the CI workflow needs a `postgres:16` service and `PG_TEST_URL` set, or the 35 DB tests skip silently. Consider failing CI on skips, for example by asserting the absence of `SKIPPED` in `-rs` output. Neon migration: `python -m seer_engine migrate` (or `npm run db:migrate`). The seed-script guard and the runbook are also Phase 5's.
- **Resolved by the reconciler:** the root `.gitignore` does not ignore `*.egg-info/`; Phase 1's `engine/.gitignore` (Step 1) covers it, so no phase edits the root file. The root `*.log` rule already covers Phase 5's `.workflows/live/*.log`.
- **Reconciler note (Phase 2):** the `universe.source_symbol` comment in Step 2 documents Phase 2's `/`-joined form (`FB/META`, oldest first). `http.USER_AGENT` (`seer-engine/0.1.0`) is load-bearing: Wikipedia returns 403 to the default `python-requests` agent, and Phase 2's `universe check` depends on it.
- **Command style (all phases):** global flags are accepted on either side of the command, but every documented command in the plan set places them **before** it: `python -m seer_engine --dry-run -v <command> ...`.

## Rollback

`git revert` the phase commit. This removes `engine/` (except the untracked `engine/.venv`, which can be deleted by hand) and `db/migrations/002_engine.sql`. Phase 1 applies nothing to Neon. If 002 was applied somewhere by hand: `DROP INDEX IF EXISTS runs_real_session_uidx; DROP TABLE IF EXISTS universe, split_adjustments, backfill_log; DELETE FROM schema_migrations WHERE name = '002_engine.sql';`. Local test database: `docker rm -f seer-pg`.
