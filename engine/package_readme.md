# Package: seer_engine

**Location**: `engine` (src layout: `engine/src/seer_engine`)
**Last Updated**: 2026-10-03 (P1-ENG-VP1R, phase 1 of `ENGINE_DATA_PIPELINE_PLAN.md`)

## Overview

`seer_engine` is Seer's Python data pipeline. It writes the Neon (Postgres) tables the web
app reads: daily bars, USD/IDR FX and nightly `runs`, plus the engine's own bookkeeping tables
(point-in-time `universe`, `split_adjustments`, `backfill_log`). Phase 1 is the foundation:
the package, a plug-in CLI, migration 002, NYSE date arithmetic, idempotent DB write helpers
and removal of the web app's seeded demo data. Later phases add commands on top of it
(`universe`, `backfill`, `nightly`).

**Key Responsibilities:**
- One CLI (`python -m seer_engine` / `seer-engine`) whose subcommands are discovered from `seer_engine/commands/`
- Config from the environment, with the repo-root `.env.local` as a local fallback
- One transaction helper that every write goes through, with a whole-run `--dry-run`
- NYSE session arithmetic: which session's data is complete (`data_date`) and which session the next picks are for (`session_date`)
- Idempotent upserts for `bars` and `fx_rates`, where an identical re-run changes 0 rows
- The `runs` row lifecycle: one real row per target session
- Purging demo rows before the first real write
- Applying `db/migrations/*.sql`, sharing `schema_migrations` with web's `db:migrate`

## Layout

```
engine/
  pyproject.toml            package seer-engine 0.1.0, python >=3.11, script seer-engine
  .gitignore                *.egg-info/, build/, dist/
  src/seer_engine/
    __init__.py             __version__ = "0.1.0"
    __main__.py             python -m seer_engine -> cli.main()
    cli.py                  parser, command discovery, logging, exit codes
    config.py               env + dotenv loading
    db.py                   connect(), transaction()
    http.py                 get_json() with retries, redact()
    dates.py                NYSE sessions, RunDates
    demo.py                 demo-data purge
    universe.py             read-only point-in-time membership queries
    bars.py                 Bar value type, rounding, upsert_bars()
    fx.py                   Frankfurter USD/IDR fetch, upsert_fx()
    runs.py                 start_run / finish_run / fail_run
    commands/
      __init__.py           command-module contract
      migrate.py            `migrate` command
  tests/                    pytest; DB tests need PG_TEST_URL
db/migrations/002_engine.sql  (outside the package, owned by it)
```

## CLI

```
python -m seer_engine [--version] [--dry-run] [-v|-vv] <command> [command args]
```

- `--dry-run`: runs every read and every write statement, then rolls back every transaction, so nothing persists.
- `-v`: debug logging. `-vv` also enables debug logging for the `urllib3`, `yfinance` and `peewee` loggers.
- The global flags work on either side of the command name. Documented usage puts them before it.
- Logs go to stderr with UTC ISO timestamps.

**Exit codes** (`cli.main`): 0 success or no-op; 1 an uncaught exception or a failed run; 2
`config.ConfigError` (missing setting) or an unmet precondition returned by a command; 130
Ctrl-C. Otherwise the code is whatever the command's `run()` returns.

### Command contract

Every public module in `seer_engine/commands/` (a name not starting with `_`) is a command:

```python
HELP: str
def add_arguments(p: argparse.ArgumentParser) -> None   # optional
def run(args: argparse.Namespace) -> int               # args.dry_run, args.verbose always set
```

To add a command, add a module. `cli.py` never changes. `discover()` raises `TypeError` if a
module has no callable `run`.

### Commands (phase 1)

| Command | Args | What it does |
|---|---|---|
| `migrate` | `--dir PATH` (default `<repo>/db/migrations`) | Applies pending `*.sql` files in file-name order, one transaction per file, and records each in `schema_migrations(name, applied_at)`. It is the twin of `web/scripts/migrate.mjs` and uses the same table and key, so either runner can apply any file. Under `--dry-run`, all pending files are applied in one transaction (later files may depend on earlier ones), which is then rolled back, so not even `schema_migrations` is created. |

## Exported API

### config

- `REPO_ROOT: Path`: the repository root, derived from the file's location.
- `class ConfigError(RuntimeError)`: raised when a required setting is missing. The CLI maps it to exit code 2.
- `env_file() -> Path`: `$SEER_ENV_FILE`, else `<repo>/.env.local`.
- `load_env() -> Path | None`: loads the dotenv file without overriding variables that are already set. Returns `None` when the file is absent (CI). Safe to call more than once.
- `get(name) -> str | None`: the value of `name`. Empty counts as unset. Calls `load_env()` on first use.
- `require(name) -> str`: like `get`, but raises `ConfigError` with the variable name and the dotenv path it checked.

### db

- `CONNECT_TIMEOUT_S = 15`
- `connect(url=None) -> psycopg.Connection`: opens a connection with autocommit off. Defaults to `DATABASE_URL_UNPOOLED` (Neon's direct endpoint, because the pooled one drops session state such as temp tables).
- `transaction(conn, dry_run: bool)`: a context manager. Commits on success. On any exception, including `BaseException`, it rolls back and re-raises. With `dry_run` it rolls back after the block completes.

### http

- `USER_AGENT = "seer-engine/0.1.0"`: set on the shared session. Wikipedia returns 403 to the default python-requests agent.
- `class HttpError(RuntimeError)`: has a `.status` attribute (`int | None`).
- `redact(url) -> str`: replaces the value of any `api_key`/`apikey`/`access_token`/`token`/`key` query parameter with `REDACTED`.
- `get_json(url, params=None, *, retries=3, backoff=5.0, timeout=30) -> dict`: GETs a JSON object. Connection errors, timeouts, 429 and 5xx responses are retried with exponential backoff (`backoff * 2**(n-1)`). A numeric `Retry-After` header wins when it is longer. Any other non-200 status, non-JSON body or non-object JSON raises `HttpError` at once. Every URL in logs and exception messages is redacted.

### dates

All dates are `datetime.date`. The only timezone-aware datetimes are the UTC "now" and NYSE closes.

- `CALENDAR = "NYSE"`, `DEFAULT_SETTLE = timedelta(hours=1)`
- `@dataclass(frozen) RunDates(data_date: date, session_date: date)`
- `sessions(start, end) -> list[date]`: inclusive, ascending. Returns `[]` when `end < start`.
- `is_session(d) -> bool`: half days count as sessions.
- `next_session(d)` / `prev_session(d) -> date`: strictly after or before `d`. Scans up to 3 years, then raises `ValueError`.
- `session_close_utc(d) -> datetime`: the scheduled close in UTC, accounting for half days and DST. Raises `ValueError` when `d` is not a session.
- `last_completed_session(now_utc, settle=DEFAULT_SETTLE) -> date`: the latest session whose close plus `settle` is at or before `now_utc`. Requires an aware datetime (`ValueError` otherwise).
- `run_dates(now_utc=None, settle=DEFAULT_SETTLE) -> RunDates`: `data_date = last_completed_session(now)` and `session_date = next_session(data_date)`.

Passing a `datetime` where a `date` is expected raises `TypeError`, because `datetime` is a `date` subclass and would otherwise slip through.

### bars

Prices are split-adjusted only (no dividend adjustment) and stored as `numeric(12,4)`. Volume is an `int`. Symbols use the canonical dot form (`BRK.B`).

- `PRICE_QUANTUM = Decimal("0.0001")`
- `@dataclass(frozen) Bar(symbol, date, open, high, low, close: Decimal, volume: int)`
- `to_decimal(x) -> Decimal`: rounds half-up to 4 dp. Floats go through `repr`, so `0.1` becomes `0.1000`. Raises on bool and non-finite values.
- `to_volume(v) -> int`: rounds half-up. Raises on bool, non-finite and negative values. Massive reports volume as a float.
- `make_bar(symbol, d, o, h, l, c, v) -> Bar`: validates and rounds. Raises `ValueError` for an empty symbol and `TypeError` for a non-date or datetime `d`.
- `upsert_bars(conn, bars) -> int`: COPYs into the temp table `_seer_bars_in`, then runs `INSERT ... ON CONFLICT (symbol, date) DO UPDATE ... WHERE ... IS DISTINCT FROM`. Returns the number of rows inserted or changed. An identical re-run returns 0 and creates no new row versions (`xmin` is unchanged). Raises `ValueError` when a batch holds the same `(symbol, date)` twice.
- `latest_bar_date(conn, symbol) -> date | None`
- `delete_bars_on(conn, d) -> int`

### fx

- `FRANKFURTER = "https://api.frankfurter.dev/v1"`, `PARAMS = {"base": "USD", "symbols": "IDR"}`. These are ECB reference rates and need no API key.
- `fetch_latest() -> (date, Decimal)`: the newest rate and the date Frankfurter assigns to it.
- `fetch_range(start, end) -> list[(date, Decimal)]`: inclusive and ascending, with one request per calendar year.
- `upsert_fx(conn, rows) -> int`: has the same temp-table and `IS DISTINCT FROM` shape as `upsert_bars` (`_seer_fx_in`). An identical re-run returns 0. Raises `ValueError` on conflicting rates for one date in a batch. A missing IDR rate in a response raises `ValueError`.

### runs

- `MAX_ERROR_CHARS = 2000`
- `start_run(conn, rd: RunDates) -> int | None`: claims the real run row for `rd.session_date` and sets `status='running'`. Returns `None` when that session already has a successful real run, in which case the caller does nothing. A failed or stale running row is reused with the same id: error and `finished_at` are cleared and `data_date` is refreshed. This relies on the `runs_real_session_uidx` partial unique index.
- `finish_run(conn, run_id)`: sets `success` and `finished_at = clock_timestamp()`.
- `fail_run(conn, run_id, error)`: sets `failed` with a redacted error cut to 2000 characters.
- Both final setters raise `LookupError` when `run_id` is not a real (non-demo) run.

### universe (read side only; phase 2 writes the table)

Membership intervals are `[start_date, end_date)`, where `end_date` is exclusive and NULL means still a member.

- `BENCHMARK = "SPY"`
- `members_on(conn, d) -> set[str]`: symbols in either index (SP500 or NDX) on `d`.
- `symbols_for_bars(conn, d, grace_days=30) -> set[str]`: members on `d`, plus members that left within `grace_days` (so open positions keep a price), plus `BENCHMARK`.
- `all_symbols(conn, since) -> list[str]`: every symbol that was a member at any time after `since`, plus `BENCHMARK`, sorted.

### demo

Demo bars and FX rows look exactly like real ones, so the trigger is that a `runs` row with `is_demo` exists. While one exists, every row in the demo-owned tables is treated as demo data.

- `DEMO_TABLES = ("action_dismissals", "orders", "equity_snapshots", "bars", "fx_rates", "runs")`. `strategies` is kept on purpose.
- `has_demo(conn) -> bool`
- `purge_demo(conn) -> bool`: `TRUNCATE <DEMO_TABLES> RESTART IDENTITY` when demo data exists. Does not commit.
- `purge_demo_if_needed(conn, dry_run) -> bool`: runs `purge_demo` in its own `db.transaction`. Under `dry_run` the purge runs, is rolled back and logs "would purge". The return value still says whether it purged or would have.

## Migration 002 (`db/migrations/002_engine.sql`)

This migration is additive only. It is written by the engine, and web does not read these tables.

- `universe(symbol, index_id IN ('SP500','NDX'), start_date, end_date NULL, source_symbol)`, with PK `(index_id, symbol, start_date)`, `CHECK end_date > start_date` and an index on `symbol`. When an interval spans a rename, `source_symbol` joins the source tickers with `/`, oldest first (`FB/META`).
- `split_adjustments(symbol, execution_date, split_from > 0, split_to > 0, applied, recorded_at)`, with PK `(symbol, execution_date)`.
- `backfill_log(symbol PK, status IN ('ok','empty','failed'), first_date, last_date, rows, error, updated_at)`.
- `runs_real_session_uidx`: a unique index on `runs(session_date) WHERE NOT is_demo`, which allows at most one real run per session.

## Data Flow

Phase 1 provides the building blocks. Write commands in later phases use them in this order:

1. `cli.main` calls `config.load_env()`, builds the parser from `discover()`, sets up logging and calls the command's `run(args)`.
2. `run` opens `closing(db.connect())`. It does not use `with connect()`, because psycopg's connection context manager commits on exit.
3. `demo.purge_demo_if_needed(conn, args.dry_run)` runs in its own transaction before any other write.
4. Reads (`dates.run_dates`, `universe.*`, `http.get_json` / `fx.fetch_*`) are followed by writes (`bars.upsert_bars`, `fx.upsert_fx`, `runs.*`) inside `with db.transaction(conn, args.dry_run):`.
5. The transaction commits, or rolls back and re-raises. `main` maps exceptions to exit codes.

## Dependencies

### External
- `psycopg[binary]>=3.2`: the Postgres driver, used for COPY into temp tables in the upserts.
- `pandas>=2.2`, `pandas_market_calendars>=5.0`: the NYSE schedule, including closes, half days and DST.
- `requests>=2.32`: HTTP, through one module-level `Session` in `http.py`.
- `python-dotenv>=1.0`: parses `.env.local`. The file is parsed, never `source`d, because it contains an unquoted `&`.
- `yfinance>=1.0`: declared for phase 3 (backfill). Phase 1 does not use it.
- dev: `pytest>=8`.

### Internal module graph
- `cli` imports `config` and `commands`. `commands.migrate` imports `config` and `db`.
- `db` imports `config`. `demo` imports `db`.
- `fx` imports `http` and `bars.to_decimal`. `runs` imports `dates.RunDates` and `http.redact`.
- `http` imports `__version__` for `USER_AGENT`.

### Standard library
`argparse`, `importlib`/`pkgutil` (command discovery), `logging`, `contextlib`, `dataclasses`, `decimal`, `functools.lru_cache`, `re`, `time`.

## Reverse Dependencies

- Within `engine/`, the phase 2 to 4 modules consume the API above exactly as written in the plan's "Shared interface contract": `membership.py` and `commands/universe.py` (phase 2), `yahoo.py` and `commands/backfill.py` (phase 3), and `massive.py`, `splits.py` and `commands/nightly.py` (phase 4).
- Phase 5 will add `.github/workflows/{engine-ci,nightly,universe,backfill}.yml`, which invoke the CLI.
- Nothing in `web/` imports the engine. The two share only the database schema and `schema_migrations`.

## Concurrency

This package is not designed for concurrent use. It is single-threaded and uses one connection per command. Some state is held per process:
- `http._session` is a module-level `requests.Session`.
- `config._loaded` is a module-level flag.
- `dates._calendar`, `_year` and `_closes` are `lru_cache`d per process.

The temp tables `_seer_bars_in` and `_seer_fx_in` are scoped to a session (`ON COMMIT DELETE ROWS`), so concurrent processes do not collide.

## Error Handling

- Custom exceptions: `config.ConfigError` (exit 2) and `http.HttpError(.status)`.
- Validation errors are `ValueError` or `TypeError` with a message naming the bad value or date.
- `runs` raises `LookupError` for an unknown or demo run id.
- `db.transaction` always re-raises after rolling back. Data helpers never commit.
- Secrets are redacted from every logged or raised URL and from `runs.error`.
- Nothing in the package panics or exits outside `cli.main`.

## Performance

- Bulk writes use COPY into a temp table and then one set-based `INSERT ... ON CONFLICT`. Writes that change nothing are skipped by the `IS DISTINCT FROM` guard, so re-runs cause no table bloat.
- The NYSE schedule is computed once per year and cached for the life of the process.
- Network calls are the expensive part. `get_json` waits 5 s, then 10 s, then 20 s between retries by default. `fx.fetch_range` makes one request per year.
- There is no benchmark coverage.

## Usage

### Setup and tests

```
python3.11 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'
docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests
```

DB tests skip without `PG_TEST_URL`, and CI should treat skips as failures. Each DB test gets
a throwaway schema `t_<hex>`. The fixtures are `pg` (migrated), `pg_empty`, `pg_schema`,
`pg_url` and `utc(y, m, d, h=0, mi=0)`. An autouse `_isolated_env` fixture points
`SEER_ENV_FILE` at a missing file and `DATABASE_URL_UNPOOLED` at a `.invalid` host, so no test
can reach `.env.local` or Neon.

### Settings
- `DATABASE_URL_UNPOOLED`: required by `db.connect()`.
- `SEER_ENV_FILE`: optional override for the dotenv path.

### Typical write command

```python
def run(args):
    with closing(db.connect()) as conn:
        demo.purge_demo_if_needed(conn, args.dry_run)
        rd = dates.run_dates()
        with db.transaction(conn, args.dry_run):
            run_id = runs.start_run(conn, rd)
            if run_id is None:
                return 0
            bars.upsert_bars(conn, fetched)
            runs.finish_run(conn, run_id)
    return 0
```

### Gotchas
- Do not use `with psycopg.connect(...) as conn`, because it commits on exit and defeats `--dry-run`. Use `contextlib.closing` instead.
- Every write must be inside `db.transaction(conn, dry_run)`. The helpers never commit, so a write outside it is lost or left open.
- `demo.purge_demo_if_needed` must run before the first write. Any demo `runs` row means `bars` and `fx_rates` will be TRUNCATEd.
- Never build a local-midnight datetime from a date. Pass `date` objects, and give `last_completed_session`/`run_dates` an aware UTC datetime.
- Convert symbols to Yahoo's dash form (`BRK-B`) only inside the Yahoo adapter (phase 3). Tables always store `BRK.B`.
- `universe.end_date` is exclusive.
- Under `--dry-run`, `migrate` reports the files it would apply, but leaves no `schema_migrations` table behind.

## Notes

Documentation created on 2026-10-03 for P1-ENG-VP1R (phase 1). Phases 2 to 4 (P1-ENG-853Z,
P1-ENG-L73U, P1-ENG-GF8Y) will add the `universe`, `backfill` and `nightly` commands, and this
document should gain their sections when they land. The full design, invariants and
reconciliation log are in `ENGINE_DATA_PIPELINE_PLAN.md`.
