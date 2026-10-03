# Package: seer_engine

**Location**: `engine` (src layout: `engine/src/seer_engine`)
**Last Updated**: 2026-10-03 (Strategy B P6a, phase 7 of `STRATEGY_B_RANKER_PLAN.md`: `strategies.b`, `b_model`, labeler, B walk-forward, `backtest_b` command, committed P6a report)

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
- The pure fill simulator (`sim/`): order lifecycle, whole-share sizing, cash/equity and split recompute, shared by the backtest (P3) and nightly paper trading (P4)
- The pure strategy layer (`strategies/`): the `Strategy` protocol, numpy indicator windows and Strategy A with its frozen parameters, shared by the backtest (P3) and nightly picks (P4)
- The 10-year backtest (`backtest/`, `backtest` command): point-in-time market, the session loop around the simulator, SPY benchmarks, metrics identical to the web's, the in-sample grid, the out-of-sample gate and the committed report
- The Strategy A rework (P3b): `strategies.a2` (Strategy A's pre-registered variants V0–V3), an anchored yearly walk-forward (`backtest/walkforward.py`) that drives one portfolio whose params change by year, its report (`backtest/wf_report.py`) and the `backtest_wf` command
- Strategy B (P6a): `strategies.b` (an ML cross-sectional ranker on 15 ranked features and 3 SPY features, keeping A's bracket and passing on nights with no positive prediction), `strategies.b_model` (fixed-hyperparameter gradient-boosted trees, plus a ridge for information), a vectorized net-of-cost bracket labeler (`backtest/labels.py`), the B walk-forward over P3b's folds with a label purge (`backtest/b_walkforward.py`), its report (`backtest/b_report.py`), and the `backtest_b` command

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
    prices.py               pure Bar, PRICE_QUANTUM, to_decimal (no psycopg)
    bars.py                 re-exports prices; to_volume, make_bar, upsert_bars()
    fx.py                   Frankfurter USD/IDR fetch, upsert_fx()
    yahoo.py                yfinance download + frame parsing, BRK.B <-> BRK-B (phase 3)
    runs.py                 start_run / finish_run / fail_run
    sim/                    fill simulator: pure, deterministic, Decimal-only (P2)
      __init__.py           public surface; import everything from seer_engine.sim
      model.py              constants, money helpers, Order, Portfolio, Event, Snapshot, StepResult
      lifecycle.py          step(), close_unpriced()
      sizing.py             Pick, Rejection, SizingResult, size_picks()
      split_adjust.py       apply_split()
    strategies/             strategy layer: pure; float64 indicators, Decimal picks (P3)
      __init__.py           re-exports the public names of base, a, a2 and b (never b_model, so importing the package does not load scikit-learn)
      base.py               History, history_from_bars(), Strategy protocol
      indicators.py         sma / wilder_rsi / wilder_atr / mean_dollar_volume / mean / stdev_return windows, rolling()
      a.py                  Strategy A: AParams, DESIGN_PARAMS, STRATEGY_A_PARAMS (frozen), StrategyA
      a2.py                 Strategy A2 (P3b): A2Params, VARIANTS V0-V3, regime_on, STRATEGY_A2_PARAMS, StrategyA2
      b_model.py            Strategy B's model (P6a): fit_tree / fit_ridge, BModel (digest identity), importance, dumps / loads
      b.py                  Strategy B (P6a): 18 features, rank01, candidates, BParams, picks > 0, FrozenModel, STRATEGY_B_FROZEN, StrategyB
    backtest/               10-year backtest (P3) and walk-forward (P3b, P6a); every module but io.py is pure
      __init__.py           docstring only
      market.py             Membership, Market: bars, universe and FX in memory
      runner.py             run_backtest(), RunResult, survivorship(), ParamsSchedule (P3b)
      benchmark.py          SPY buy-and-hold, price-only and total-return
      metrics.py            Metrics, strategy_metrics(), checklist() (web/lib/metrics.ts parity), metrics_through() (P3b)
      tuning.py             windows, the 81-run grid, select(fallback=), gate()
      walkforward.py        folds, 324 combinations, tune(), select_fold(), walk_forward(), diagnostics(), gate_p3b() (P3b)
      report.py             BacktestReport, render_markdown(), equity_csv(), equity_svg()
      wf_report.py          WalkForwardReport, machine lines, Markdown, equity/grid CSVs, two SVGs (P3b)
      labels.py             vectorized bracket labeler: net-of-cost label and resolution date per order (P6a)
      b_walkforward.py      candidate table, purge, per-fold fits, probe, B / B-linear runs, calibration, gate_p6a() (P6a)
      b_report.py           BReport, machine lines, Markdown, equity CSV, SVG (P6a)
      io.py                 Neon loader + bar cache, dividends CSV, report writers write_report() / write_wf_report() / write_b_report(), write_model_artifact() (impure)
    commands/
      __init__.py           command-module contract
      migrate.py            `migrate` command
      backfill.py           `backfill` command (phase 3)
      backtest.py           `backtest` command (P3)
      backtest_wf.py        `backtest_wf` command (P3b)
      backtest_b.py         `backtest_b` command (P6a)
  tests/                    pytest; DB tests need PG_TEST_URL
  data/spy_dividends.csv    SPY dividends (ex_date, amount_usd), vendored from yfinance (see data/SOURCES.md)
  .cache/                   gitignored; bars-<max date>-<rows>.pkl written by the backtest loader
docs/backtests/             committed reports: <end>-strategy-a{.md,-equity.csv,-equity.svg} (P3); <end>-strategy-a2-walkforward{.md,-equity.csv,-equity.svg,-variants.svg,-grid.csv} (P3b); <end>-strategy-b-walkforward{.md,-equity.csv,-equity.svg} (P6a)
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

### `backfill` (phase 3, P1-ENG-L73U)

```
python -m seer_engine [--dry-run] backfill [--start YYYY-MM-DD] [--end YYYY-MM-DD]
    [--symbols AAPL,BRK.B] [--retry-failed] [--skip-fx | --fx-only] [--batch-size N]
```

A one-off, resumable history load: daily bars from yfinance plus USD/IDR history from Frankfurter.

- **Range**: `--start` defaults to `2015-01-02` (`DEFAULT_START`). `--end` defaults to `dates.last_completed_session(now UTC)`. Both bounds are inclusive. `--start` after `--end` is exit 2.
- **Symbols**: every symbol returned by `universe.all_symbols(conn, since=start)`, which includes SPY. An empty universe (nothing but SPY) is exit 2 with a hint to run `universe refresh` first. `--symbols` takes a comma list in place of the universe and ignores `backfill_log`. Yahoo dash spellings are converted to the dot form.
- **Resume**: by default, symbols already in `backfill_log` with any status (`ok`, `empty` or `failed`) are skipped and counted as "skipped". `--retry-failed` skips only `ok` and re-attempts `failed` and `empty`.
- **Batches**: `--batch-size` symbols per `yf.download` call (default 40, `DEFAULT_BATCH_SIZE`), with a 3 s pause between batches (`BATCH_PAUSE_S`). A rate-limited call is retried after 60, 120 and 240 s (`RATE_LIMIT_BACKOFF_S`). After that, or on any other download exception, the whole batch is logged `failed` and the run continues. A symbol that comes back with no bars in range gets one individual retry, then is logged `empty`.
- **Writes**: each batch's `bars.upsert_bars` and its `backfill_log` upserts run in one `db.transaction`, so a crash loses at most one batch. `backfill_log` stores `status`, `first_date`, `last_date`, `rows` and `error` (cut to 500 characters). The log upsert never downgrades an `ok` row to `failed`, and it skips identical rows.
- **FX**: unless `--skip-fx`, `fx.fetch_range(start, end)` then `fx.upsert_fx` into `fx_rates`, in its own transaction after the bars. An FX fetch failure is reported, and the bars already committed are kept. `--fx-only` skips the bars entirely.
- **Order**: symbol selection (a read), then `demo.purge_demo_if_needed`, then the bars, then FX. No `runs` row is written, and no splits are recorded, because yfinance history is already adjusted for every split up to the moment the backfill runs. Later splits are applied by the nightly command.
- **Idempotent**: every write is an upsert. Re-running with the same arguments changes 0 `bars` and `fx_rates` rows.
- **Output**: a summary on stdout with ok, empty, failed and skipped counts, bar rows fetched and changed, the failed and empty symbol lists, FX rows changed, and the `bars` table size from `pg_total_relation_size`.
- **Exit codes**: 0 when everything succeeded (empty symbols are not a failure); 1 when any symbol failed or the FX fetch failed; 2 for a bad range or an empty universe (`BackfillError`).
- **Testing seams**: `backfill(conn, opts, *, downloader=None, sleep=time.sleep, fetch_fx=None) -> Summary` takes injectable network and sleep callables. `fetch_batch`, `select_symbols`, `options_from_args` and `format_summary` are also public.

### `backtest` (P3)

```
SEER_ENV_FILE=/path/to/.env.local python -m seer_engine backtest [--out DIR] [--cache-dir DIR]
    [--refresh-cache] [--is-start YYYY-MM-DD] [--oos-start YYYY-MM-DD] [--end YYYY-MM-DD] [--dividends PATH]
```

Runs Strategy A's 10-year backtest against Neon and writes the report. **Read-only**: it reads
`bars`, `universe` and `fx_rates` and writes nothing to any table; `--dry-run` changes nothing.

- **Defaults are the committed run.** `--out` defaults to `<repo>/docs/backtests`, the windows to
  `tuning.IS_START` / `tuning.OOS_START` / the last SPY bar, `--dividends` to
  `engine/data/spy_dividends.csv`. The window flags exist for synthetic tests; passing them for a
  real run is how out-of-sample tuning starts, so don't.
- **Steps:** load the market (cached), `STRATEGY_A.prepare` once, the 81 in-sample grid runs,
  `select` on in-sample metrics only, then one out-of-sample run and one full-window run with the
  selection, both SPY curves per window, the survivorship count, the gate, and the three files.
- **Cache:** bars are read with one streamed `COPY ... TO STDOUT` and pickled to
  `<cache dir>/bars-<max date>-<rows>.pkl`; `--cache-dir` defaults to `engine/.cache` (gitignored)
  and exists so tests keep the cache out of the repo. Each run first asks Neon for
  `max(date), count(*)` from `bars`; a different fingerprint reloads. `--refresh-cache` forces a
  reload. `universe` and `fx_rates` are small and read every time.
- **Output:** `<out>/<data end>-strategy-a.md`, `-equity.csv`, `-equity.svg`. The stem uses the
  data end date, so a re-run on the same data overwrites the same files byte-identically.
- **Logs:** cache hit or miss, wall time per grid run and in total, the selection, the gate verdict.
- **Exit codes:** 0 whether the gate passes or fails (a losing verdict is a result); 1 on an error;
  2 on a precondition (no bars, no SPY bars, a window date that is not an NYSE session or is after
  the last SPY bar, `is_start < oos_start <= end` violated, no FX row on or before `--is-start`, a
  missing dividends file).
- **Worktrees:** `config.REPO_ROOT` is the worktree, which has no `.env.local`, so set
  `SEER_ENV_FILE` to the main checkout's file. Never `source` it.

### `backtest_wf` (P3b)

```
SEER_ENV_FILE=/path/to/.env.local python -m seer_engine backtest_wf [--dry-run] [-v] [--out DIR] [--cache-dir DIR]
    [--refresh-cache] [--is-start YYYY-MM-DD] [--first-year YYYY] [--end YYYY-MM-DD] [--dividends PATH]
```

This runs Strategy A2's anchored yearly walk-forward against Neon and writes the P3b report.
Command names are module names, and a hyphen is not legal in one, hence the underscore.
**Read-only**, like `backtest`: it reads `bars`, `universe` and `fx_rates` and writes nothing to
any table, `strategies.params` included. `--dry-run` changes nothing (there are no DB writes to roll
back); the report files are still written.

- **Defaults are the committed run.**
  - `--out` defaults to `<repo>/docs/backtests`, `--is-start` to `tuning.IS_START` (2015-10-19),
    `--first-year` to `walkforward.FIRST_TRADE_YEAR` (2018), `--end` to the last SPY bar, and
    `--dividends` to `engine/data/spy_dividends.csv`.
  - The window flags exist for synthetic tests. Passing them for a real run is how tuning on traded
    data starts, so don't.
- **Steps:**
  1. Load the market (the same bar cache as `backtest`).
  2. `STRATEGY_A2.prepare` once, then the folds.
  3. Tuning: one run per each of the 324 (variant × grid) combinations over 2015-10-19 → the last
     fold's tune end, sliced per fold with `metrics_through`.
  4. The combined selection per fold, and each variant's own.
  5. Five walk-forward runs (combined + 4 variants), each one continuous portfolio from 2018-01-02.
  6. Both SPY curves from the same starting cash, survivorship, `gate_p3b`, and the five files.
- **Output:** `<out>/<data end>-strategy-a2-walkforward.md`, `-equity.csv`, `-equity.svg`,
  `-variants.svg`, `-grid.csv`. A re-run on the same data overwrites them byte-identically.
- **Logs:**
  - cache hit or miss;
  - the prepare time;
  - wall time per combination and in total;
  - every fold's selection;
  - the gate verdict;
  - whether `STRATEGY_A2_PARAMS` equals the last fold's selection.
- **Exit codes:**
  - 0 whether the gate passes or fails, because a losing verdict is a result.
  - 1 on an error.
  - 2 on a precondition, as for `backtest`: no bars, no SPY bars, a window date that is not an NYSE
    session or is after the last SPY bar, no fold to trade, no FX row on or before `--is-start`, or
    a missing dividends file.
- **Worktrees:** as for `backtest`, set `SEER_ENV_FILE` to the main checkout's `.env.local`. Never
  `source` it.
- **One round.** The committed run is P3b's single rework of Strategy A. Re-running it on newer data
  re-measures the same pre-registered procedure. Adding a variant or a grid value after seeing
  results is not allowed.

### `backtest_b` (P6a)

```
SEER_ENV_FILE=/path/to/.env.local python -m seer_engine backtest_b [--dry-run] [-v] [--out DIR] [--cache-dir DIR]
    [--refresh-cache] [--is-start YYYY-MM-DD] [--first-year YYYY] [--end YYYY-MM-DD] [--dividends PATH]
    [--model-dir DIR]
```

This runs Strategy B's anchored yearly walk-forward against Neon and writes the P6a report.
**Read-only**, like `backtest_wf`: it reads `bars`, `universe` and `fx_rates`, and writes nothing to
any table, `strategies.params` included. `--dry-run` changes nothing: the report files (and a
passing run's artifact) are written as usual.

- **Defaults are the committed run.**
  - `--out` defaults to `<repo>/docs/backtests`, `--cache-dir` to `engine/.cache` (shared with
    `backtest` and `backtest_wf`) and `--model-dir` to `<repo>/engine/data/models`.
  - The window flags have `backtest_wf`'s defaults (2015-10-19, 2018, the last SPY bar, and
    `engine/data/spy_dividends.csv`). They exist for synthetic tests. Passing them for a real run
    is how training on traded data starts, so don't.
- **Steps:**
  1. Load the market, from the same bar cache as `backtest`.
  2. The folds; `prepare_b` once; the candidate table with its labels.
  3. Per fold, a tree fit and a ridge fit on the purged rows, sequential, in fold order. Then the
     determinism probe on the last fold, which decides the gated curve.
  4. The B and B-linear walk-forward runs, each one continuous portfolio from 2018-01-02.
  5. A2's combined walk-forward, recomputed through `backtest_wf`'s `tune_all` + `run_walk_forward`
     as information.
  6. Both SPY curves, survivorship, passed nights, calibration, `gate_p6a`, and the three files.
  7. On a pass, the gated curve's last-fold model goes to `<model-dir>/<data end>-strategy-b.pkl`,
     and its sha256 is logged with the instruction to freeze it.
- **Output:** `<out>/<data end>-strategy-b-walkforward.md`, `-equity.csv` and `-equity.svg`, plus
  the artifact on a pass. A re-run on the same data overwrites them byte-identically. Only the
  `frozen-model:` line, and what renders from it, follows `STRATEGY_B_FROZEN`.
- **Logs:** cache hit or miss, the wall time of every step, every fold's training summary, the
  probe result, the gate verdict, and the artifact path and sha256 on a pass. Wall times appear in
  logs only, never in a file.
- **Exit codes:**
  - 0 whether the gate passes or fails, because a losing verdict is a result.
  - 1 on an error.
  - 2 on a precondition, the same ones as `backtest_wf` (`backtest_wf.resolve`: no bars, no SPY
    bars, a window date that is not an NYSE session or is after the last SPY bar, no fold to trade,
    no FX row on or before `--is-start`), or a missing dividends file.
- **Worktrees:** as for `backtest`, set `SEER_ENV_FILE` to the main checkout's `.env.local`. Never
  `source` it.
- **One round.** The committed run is B's single round on this data. Re-running it on newer data
  re-measures the same pre-registered procedure. Changing a feature, the label, a hyperparameter or
  the pick rule after seeing results is not allowed.

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

### prices

Pure value types for prices, with no database import, so the simulator can use `Bar` without loading `psycopg`. `bars` re-exports all three names, so `from seer_engine.bars import Bar, PRICE_QUANTUM, to_decimal` keeps working.

- `PRICE_QUANTUM = Decimal("0.0001")`
- `@dataclass(frozen, slots) Bar(symbol, date, open, high, low, close: Decimal, volume: int)`
- `to_decimal(x) -> Decimal`: rounds half-up to 4 dp. Floats go through `repr`, so `0.1` becomes `0.1000`. Raises on bool and non-finite values.

### bars

Prices are split-adjusted only (no dividend adjustment) and stored as `numeric(12,4)`. Volume is an `int`. Symbols use the canonical dot form (`BRK.B`).

- `PRICE_QUANTUM`, `Bar`, `to_decimal`: defined in `prices` and re-exported here unchanged.
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

### yahoo (phase 3)

This is the only module that knows Yahoo's ticker spelling. Prices come from yfinance's `Open/High/Low/Close/Volume` with `auto_adjust=False`, so they are split-adjusted but not dividend-adjusted. `Adj Close` is ignored on purpose.

- `Downloader = Callable[[list[str], date, date], DataFrame | None]`: `(yahoo_tickers, start, end_exclusive)`. Tests inject a fake and never touch Yahoo.
- `class RateLimited(Exception)`
- `to_yahoo(symbol)` / `from_yahoo(ticker) -> str`: `BRK.B` and `BRK-B`, upper-cased and stripped.
- `yf_download(tickers, start, end_exclusive)`: the real downloader. One `yf.download` call (`interval="1d"`, `group_by="ticker"`, `threads=False`, `repair=False`). `yf.download` swallows per-ticker errors and only logs them, so a temporary handler on the `yfinance` logger captures ERROR records. A rate-limit message there, or a raised `YFRateLimitError`, raises `RateLimited`.
- `download(symbols, start, end_exclusive, *, downloader=None) -> dict[str, list[Bar]]`: one entry (possibly empty) per requested canonical symbol, with bars sorted by date. The caller filters to its inclusive range, because Yahoo can return a partial current-day bar.
- `parse_frame(frame, tickers)`: accepts `(Ticker, Price)` or `(Price, Ticker)` MultiIndex columns, and flat columns when exactly one ticker was requested.
- `frame_to_bars(symbol, sub) -> list[Bar]`: drops rows with missing or non-finite OHLC and rows with a non-positive price. A missing volume becomes 0. A tz-aware index is made naive without conversion, so the exchange-local date is kept.

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

### sim (fill simulator, P2)

Pure and deterministic: no database, no network, no clock, no randomness, no logging. It imports only `seer_engine.dates` and `seer_engine.prices`, never `bars`, and `tests/test_sim_purity.py` checks in a subprocess that `psycopg`, `requests` and `yfinance` stay out of `sys.modules`. Every value is a frozen dataclass, and every function returns new values. All money and prices are `Decimal`, quantized to 4 dp half-up (`q`). Shares are `int`. A float or any other non-`Decimal` price raises `TypeError`. Import everything from `seer_engine.sim`.

**Rules** (design §5 + handover §3, all tested on synthetic bars):

| Topic | Rule |
|---|---|
| Fill | session `low < limit` (strict; a touch does not fill). Fill at the **open** if `open < limit`, else at the limit. Fill session = day 1 |
| Unfilled | the pending order expires at the end of its session; the slot is free for that night's picks |
| Session order | (1) time stop at the open, (2) gap at the open (`open <= SL` → `gap`, then `open >= TP` → `tp`), (3) intraday `low <= SL` → `sl` at SL, then `high > TP` → `tp` at TP (SL first), (4) fills, (5) expiries, (6) mark to close. A position filled today is not checked against TP/SL today |
| Time stop | `days_held >= 5` and a bar → exit at that bar's open, reason `time`, before any gap/TP/SL check |
| `days_held` | fill session = 1; +1 for every later session survived, bar or not. Intraday exit on day k records k; an exit at the open of day k (time, gap, gap-TP) records k − 1, so a time exit records 5 |
| Costs | `buy_cost = q(price × shares × 1.001)`, `sell_proceeds = q(price × shares × 0.999)`. Fill: `cash -= buy_cost`; exit: `cash += sell_proceeds` |
| `pnl_usd` | `sell_proceeds − buy_cost`, so Σ `pnl_usd` reconciles with cash exactly. Within 0.0001 of handover §3's `(exit − fill) × sh − 0.001 × (exit + fill) × sh` |
| Equity | `q(cash + Σ shares × last known close)` at each session's close. Pending orders reserve nothing in equity |
| Sizing | picks in rank order; each placed pick takes the lowest free slot. `budget = min(q(equity / 4), cash − Σ buy_cost(limit, shares) of pending orders)`, with `equity` the last snapshot. `shares = floor(budget / (limit × 1.001))`. Rejections: `held` (symbol has a live order, or a duplicate pick), then `no_slot`, then `lt_one_share`. A rejection never uses a slot. 0 picks is valid |
| Missing bar | an open position without a bar: no event, the day still counts, marked at the last close. A due time stop waits for the next bar's open. A pending order without a bar expires |
| Holidays | the caller steps NYSE sessions only (`dates.sessions`). `step` raises on a non-session |
| Splits | `apply_split` rewrites live orders in post-split units (see below) |

**Constants and helpers** (`sim.model`):
- `SLOTS = 4`, `TIME_STOP_DAYS = 5`, `COST_RATE = Decimal("0.001")`
- `OrderStatus = Literal["pending", "open", "closed", "expired"]`, `ExitReason = Literal["tp", "sl", "time", "gap"]`, `EventKind = Literal["fill", "expire", "exit", "split"]`
- `q(x) -> Decimal`: quantize to `PRICE_QUANTUM`, half-up.
- `buy_cost(price, shares)`, `sell_proceeds(price, shares) -> Decimal`: as in the table.
- `initial_cash_usd(idr, usd_idr) -> Decimal`: `q(idr / usd_idr)`, with `usd_idr` the IDR price of 1 USD on the start date.

**Values:**
- `Order(session_date, slot, symbol, last_price, limit_price, tp_price, sl_price, shares, status="pending", fill_date=None, fill_price=None, days_held=0, exit_date=None, exit_price=None, exit_reason=None, pnl_usd=None)`: mirrors the `orders` columns except `strategy_id`, `company`, `explanation`, `id` and `created_at`. It validates itself: `slot` is 1–4, `shares >= 1`, `sl < tp`, the fill fields exactly when `open`/`closed`, and the exit fields exactly when `closed`.
- `Portfolio(cash, equity, orders=(), marks=(), last_session=None)`: one strategy's state between sessions.
  - `orders` holds **live** orders only (pending + open), sorted by slot, at most one per slot and one per symbol.
  - `marks` is `(symbol, last close)` for exactly the open symbols, sorted.
  - `equity` is the last snapshot's (or the initial cash).
  - Methods: `open_orders()`, `pending_orders()`, `free_slots()` (ascending), `held_symbols()` (all live, sorted), `mark(symbol)`.
- `new_portfolio(cash_usd) -> Portfolio`: `cash = equity = q(cash_usd)`.
- `Event(session_date, kind, order, forced=False, cash_usd=None)`:
  - `order` is the order state after the event. A terminal order (closed or expired) leaves the portfolio and appears only here, which is where P4 writes it.
  - `cash_usd` is the cash moved: `-buy_cost` on a fill, `+proceeds` on an exit, cash in lieu on a split, and `None` on an expire.
  - `forced=True` marks an exit made without a bar (`close_unpriced`, or a split that floors an open position to 0 shares).
- `Snapshot(date, cash_usd, equity_usd)`: one `equity_snapshots` row.
- `StepResult(portfolio, events, snapshot)`.

**Functions:**
- `step(portfolio, session_date, bars: Mapping[str, Bar]) -> StepResult` (`sim.lifecycle`): advances through one session.
  - `bars` holds split-adjusted bars keyed by symbol. Only bars for symbols with a live order are read and validated; the rest are ignored. A symbol absent from `bars` has no bar this session.
  - **Event order:** all exits in slot order, then all fills in slot order, then all expiries in slot order.
  - Raises `ValueError` when `session_date` is not an NYSE session, is not after `last_session`, or differs from a pending order's `session_date`, or when a bar has the wrong symbol or date. Raises `TypeError` on a non-`Bar` or a non-`Decimal` price.
- `close_unpriced(portfolio, symbols) -> (Portfolio, events)` (`sim.lifecycle`): force-closes open positions that will never get another bar (delisted, halted for good). Each exits at its mark, reason `time`, `exit_date = last_session`, with `forced=True`. It recomputes `equity`, so persist the snapshot after it. The caller decides that no bar will come; a pure step cannot know.
- `Pick(symbol, last_price, limit_price, tp_price, sl_price)` (`sim.sizing`): one ranked pick before sizing. It requires `sl < limit < tp`.
- `size_picks(portfolio, picks, session_date) -> SizingResult(portfolio, placed, rejected)` (`sim.sizing`): sizes the picks for the next session.
  - `placed: tuple[Order, ...]` and `rejected: tuple[Rejection(symbol, reason), ...]` are in pick order. `RejectReason = Literal["no_slot", "held", "lt_one_share"]`.
  - Cash does not change; a pending order pays at its fill.
  - Raises `ValueError` when `session_date` is not a session after `last_session`, or when a pending order for another session is still in the portfolio (step that session first).
- `apply_split(portfolio, symbol, factor, session_date) -> (Portfolio, events)` (`sim.split_adjust`):
  - `factor = split_to / split_from`, the same number as `splits.Split.factor`. 10 is a 10-for-1; `Decimal(1) / 32` is a 1-for-32 reverse split.
  - Call it once per split, after session S−1's `step` and before stepping the execution session S, with `session_date = S`.
  - Prices become `q(p / factor)`, and `shares = floor(shares × factor)`. The open position's fractional remainder is paid as cash in lieu at the adjusted mark, with no cost and outside `pnl_usd`; the amount is on the `split` event's `cash_usd`.
  - A pending order that floors to 0 shares emits `expire`. An open position that floors to 0 is paid out in lieu, emitting a forced `exit` (reason `time`, `pnl_usd = in lieu − buy_cost`).
  - Events are in slot order. `equity` stays at the last snapshot until the next `step` (unlike `close_unpriced`, which recomputes it). The caller applies each split exactly once (`split_adjustments` guarantees this).
  - Raises `ValueError` when a rescaled price or mark rounds to 0 at 4 dp, or SL rounds up to TP, and leaves the input untouched. Real listed stocks never get there.
  - P3 does not need it: backfilled history is already adjusted backwards.

**Determinism:** the same inputs give `==` and `repr`-identical events and snapshots. The insertion order of `bars` does not matter. `tests/test_sim_scenario.py` checks this, and also holds the 12-session hand-checked scenario.

### strategies (P3)

Pure, like `sim`: no database, network, clock, randomness or logging, and never `bars`.
`tests/test_strategy_purity.py` globs every module in `strategies/` and `backtest/` (except
`backtest/io.py`) and checks this in a subprocess and on the AST. P4 calls this code nightly and
P6 adds strategies B and C beside `a.py`.

**`strategies.base`**
- `@dataclass(frozen, slots) History(symbol, dates, open, high, low, close, volume)`: one symbol's
  daily bars, ascending, one row per bar it has (gaps allowed). `dates` is `datetime64[D]`; the
  rest are float64 arrays of the same length. `len(h)`, `h.upto(d)` (bars dated `<= d`, a view),
  `h.last_date()`, `h.index_of(d)` (row of the bar dated `d`, else `None`).
- `history_from_bars(symbol, bars: Sequence[Bar]) -> History`: `float(Decimal)` per field.
- `Strategy` protocol: `id: str`, `lookback: int` (bars per symbol `picks` needs), and
  - `picks(history, members, data_date, params) -> list[Pick]`: the nightly entry point. `history`
    maps symbol → `History` through `data_date`; longer histories are fine, only the last
    `lookback` bars dated `<= data_date` are read.
  - `prepare(history) -> Any` and `picks_prepared(prepared, members, data_date, params)`: the
    backtest's fast path, computing parameter-independent features once for every date.
  - **Contract:** `picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d)}, M, d, p)` for
    every `d`. A test proves it on a multi-symbol synthetic set.

**`strategies.indicators`** — window functions take 2-D float64 arrays shaped `(rows, W)`, oldest
column first, and return one float64 per row, `NaN` when `W` is too short. They use only
elementwise numpy and an explicit loop over columns (never a reduction along time), so a row's
result is bit-identical whatever the number of rows.
- `sma_window(close, n)`: the last `n` closes summed left to right, `/ n`.
- `wilder_rsi_window(close, n)`: changes `d_i = c_i − c_{i−1}`; seed = mean of the first `n` gains
  and losses; then `avg = (avg·(n−1) + x) / n`; `100` when the average loss is 0, else
  `100 − 100 / (1 + avgG/avgL)`.
- `wilder_atr_window(high, low, close, n)`: `TR = max(h − l, |h − c_prev|, |l − c_prev|)` from the
  window's second bar; seed = mean of the first `n` TRs; Wilder after.
- `mean_dollar_volume_window(close, volume, n)`: mean of `close × volume` over the last `n` bars.
- `mean_window(x, n)`: mean of the last `n` columns of any series, summed left to right, `/ n` (Strategy B: volume).
- `stdev_return_window(close, n)`: population (ddof 0) stdev of the last `n` one-bar returns `c_i / c_{i−1} − 1`; `NaN` when `W < n + 1`.
- `rolling(fn, *series, window, **kw)`: a length-T series → length-T result via
  `sliding_window_view`, `NaN` for `t < window − 1`.

**`strategies.a`** (design §4)
- `LOOKBACK = 200`, `SMA_N = 200`, `RSI_N = 2`, `ATR_N = 14`, `DV_N = 20`.
- `@dataclass(frozen, slots) AParams(rsi_max=10.0, limit_atr=Decimal("0.5"), tp_atr=Decimal("1.0"), sl_atr=Decimal("1.5"), min_dollar_volume=20_000_000.0)`;
  `as_dict() -> dict[str, str]` in a stable key order (what P4 writes to `strategies.params`).
- `DESIGN_PARAMS = AParams()`: design §4's starting values, the selection fallback.
- `STRATEGY_A_PARAMS`: **the frozen parameters**: `{"rsi_max": "10", "limit_atr": "0.5", "tp_atr": "1", "sl_atr": "1.5", "min_dollar_volume": "20000000"}`,
  selected on the in-sample window only by the committed report `docs/backtests/2026-10-02-strategy-a.md`
  (no grid run qualified, so these are the design values, written as an explicit literal).
  `tests/test_strategy_a_frozen.py` fails if code and report disagree. Changing a value means
  re-running the backtest and committing its report, and it resets the forward clock.
- `features_at(history, data_date) -> list[Features]` (sorted by symbol) and
  `picks_from_features(features, members, params) -> list[Pick]`; `StrategyA` implements
  `Strategy` with `id = "A"`, `lookback = LOOKBACK`; `STRATEGY_A = StrategyA()`.

| Rule | Strategy A |
|---|---|
| Timing | Picks for session S use bars through `data_date = prev_session(S)` only; `last_price` = that close. Every indicator is a function of the symbol's last 200 bars ending at `data_date`, Wilder recursions seeded inside that window, so the backtest and the nightly job compute bit-identical floats |
| Eligible | member on `data_date` (point-in-time), a bar dated `data_date`, ≥ 200 bars through it |
| Setup | `close > SMA200` and `RSI(2) < rsi_max` and 20-day mean `close × volume > min_dollar_volume`, all strict |
| Prices | `last = to_decimal(close)`, `atr = to_decimal(ATR14)`, `limit = q(last − limit_atr·atr)`, `tp = q(limit + tp_atr·atr)`, `sl = q(limit − sl_atr·atr)` |
| Dropped | after `q`: `last ≤ 0`, `limit ≤ 0`, `sl ≤ 0`, `sl ≥ limit` or `tp ≤ limit` (`Pick` would raise); dropped silently, never raised |
| Ranking | `(rsi, symbol)` ascending; every qualifying candidate is returned. Held symbols are not filtered: `size_picks` rejects them as `held` without using a slot |

**Float vs Decimal.** Indicators and the setup comparisons are float64; everything handed to the
simulator is a 4-dp `Decimal`. `bars.close` is `numeric(12,4)` (at most 12 significant digits), so
`to_decimal(float(close))` round-trips exactly through `repr`. A float could flip a strict
threshold only within about 1e-12 of it (RSI exactly 10.0 is excluded by `<`), and because the
window math is bit-identical, it flips the same way in the backtest and nightly.

**`strategies.a2`** (P3b: the Strategy A rework, `docs/handover/2026-10-03-strategy-a-rework.md`)

Strategy A2 is Strategy A plus four pre-registered variants, fixed before any result was seen. It
reuses `a.py`'s features, setup and bracket helpers unchanged. `a.py` and `STRATEGY_A_PARAMS` are
v1's record and do not move.

- `REGIME_SYMBOL = "SPY"`. It equals `universe.BENCHMARK`, which a test asserts. `a2` cannot
  import `universe`, because that imports psycopg.
- `FLOOR_PRICE = 10.0`.
- `VARIANTS = ("control", "regime", "regime_calm", "regime_calm_floor")`, which is V0–V3, in this
  order everywhere.
- `@dataclass(frozen, slots) A2Params(variant="control", rsi_max=10.0, limit_atr=Decimal("0.5"), tp_atr=Decimal("1.0"), sl_atr=Decimal("1.5"), min_dollar_volume=20_000_000.0)`:
  - A's five fields, validated and coerced exactly as `AParams`; an unknown variant is a
    `ValueError`.
  - `a_params()` gives the `AParams` of the same five values.
  - `as_dict()` puts `variant` first, then `AParams.as_dict()`. This is what P4 would write to
    `strategies.params`.
  - `A2Params.from_a(variant, p)`.
- `A2_DESIGN_PARAMS = A2Params()`: V0 with the design values, the walk-forward fallback.
- `STRATEGY_A2_PARAMS = None`.
  - The P3b gate failed (`docs/backtests/2026-10-02-strategy-a2-walkforward.md`), so nothing is frozen
    and A2 may not be deployed.
  - `tests/test_strategy_a2_frozen.py` fails if a value appears without a passing report.
- `regime_on(spy, data_date) -> bool`, `picks_from_features_a2(features, members, params, regime)`.
- `A2Prepared` / `prepare_a2(history)`: `prepare_a`'s columns plus SPY's regime column, computed
  once.
- `picks_prepared_a2(...)`.
- `StrategyA2` implements `Strategy` with `id = "A2"`, `lookback = LOOKBACK`; `STRATEGY_A2 = StrategyA2()`.

| Variant | Rule on top of Strategy A |
|---|---|
| V0 `control` | none: its picks `==` `STRATEGY_A.picks` for the same five params (tested) |
| V1 `regime` | no new picks on a `data_date` where SPY's close ≤ SPY's SMA(200). The rule is strict `>`, so equality means off. It is also off when SPY has no bar on `data_date` or fewer than 200 bars through it. The SMA is `sma_window` over SPY's last 200 closes ending at `data_date`, bit-identical between `picks` and `prepare` |
| V2 `regime_calm` | V1, ranked by `(ATR(14) / close, RSI(2), symbol)` ascending instead of `(RSI(2), symbol)` |
| V3 `regime_calm_floor` | V2, plus `close ≥ 10.00` (inclusive; fixed, never tuned) |

SPY is read from the same `history` mapping as the members, never from `members`. It can never be a
pick: it is excluded explicitly, and the universe never lists it. The P4 identity
(`picks_prepared(prepare(H)) == picks(upto(d))`) and no look-ahead hold for every variant,
including SPY's own bars dated ≥ S.

**`strategies.b_model`** (P6a: `docs/handover/2026-10-03-strategy-b-ranker.md`)

This is the one place scikit-learn is used. It is pure: no I/O, no clock and no global randomness,
because seeds are passed as `random_state=0`.

- `TREE = "tree"` and `RIDGE = "ridge"`. `TREE_PARAMS` is the pre-registered
  `HistGradientBoostingRegressor(loss="squared_error", learning_rate=0.05, max_iter=300, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0, early_stopping=False, random_state=0)`.
  There is no hyperparameter search. `RIDGE_ALPHA = 1.0`.
- `BModel(kind, n_features, digest, estimator)`. Equality and hash are `(kind, n_features, digest)`.
  `digest` is the sha256 of the tree's baseline and node arrays, or of the ridge coefficients and
  intercept. `predict(X)` is bit-identical per row, whatever the batch size.
- `fit_tree(X, y, *, threads=None)` and `fit_ridge(X, y, alpha=RIDGE_ALPHA)`. The ridge is closed
  form with an unpenalized intercept, accumulated in fixed `BLOCK_ROWS` blocks, so it never depends
  on BLAS threads. `fit(kind, X, y)` dispatches between them.
- `importance(model, X)`: shares that sum to 1. Trees use split gain; ridge uses |coef| × the
  feature's std. `r2(y, pred)`.
- `dumps(model) -> bytes` (a protocol-5 pickle of `(kind, n_features, estimator)`),
  `loads(data) -> BModel` (it recomputes the digest) and `sha256(data) -> str`. An artifact's
  identity is `sha256(file bytes)` and `loads(bytes).digest`; never re-pickle a loaded tree to
  compare bytes, since the pickle framing can differ.

**`strategies.b`** (P6a: Strategy B, the ML cross-sectional ranker)

Strategy B ranks the same eligible set as A by a learned prediction of each order's net return, and
keeps A's fixed bracket. `a.py` and `a2.py` are not changed.

- `LOOKBACK = 200`, `SPY_SYMBOL = "SPY"` (equal to `universe.BENCHMARK`, which a test asserts), and
  `MIN_DOLLAR_VOLUME = 20_000_000.0` (A's floor, strict `>`).
- `FEATURE_NAMES`: the 15 `SYMBOL_FEATURES` (returns over 1/5/20/60/120 bars, close ÷ SMA(50) − 1,
  close ÷ SMA(200) − 1, RSI(2), RSI(14), ATR(14) ÷ close, the 20-bar stdev of returns, 20-day mean
  dollar volume, 5- ÷ 20-day mean volume, gap and range position), then the 3 `SPY_FEATURES` (SPY's
  5- and 20-bar returns and close ÷ SMA(200) − 1).
  - Each symbol feature is turned into a cross-sectional rank in [0, 1] among that date's
    candidates only (`rank01`: ties averaged, 0.5 for a single candidate). The SPY features stay
    raw.
  - Ranking dollar volume itself equals ranking its log (D6).
- **Candidates on `d`:** a member other than SPY, with a bar dated `d`, at least 200 bars through
  `d`, a 20-day mean dollar volume above $20M and all 15 raw features finite. SPY's features must
  also be defined on `d`; if they are not, there are no candidates. Bracket validity is not a
  candidate rule: it applies to picks and to training rows.
- `Design(data_date, symbols, X, close, atr)`, `BPrepared` / `prepare_b(history)` (raw window
  features once per (symbol, date)), `BPrepared.design_on(members, d)`, and `design_at(history, members, d)`
  (the single-window path, bit-identical to `prepare_b`).
- `BParams(model)`. Any `Predictor` with `predict(X) -> float64` fits, and `b_model.BModel` is the
  real one. `bracket(symbol, close, atr)` is `a._bracket` at the design values.
  `picks_from_design(design, params)` keeps predictions > 0.0, ordered by (−prediction, symbol).
- `FrozenModel(report, artifact, train_end, sha256)`.
- `STRATEGY_B_FROZEN = None`.
  - The P6a gate failed (`docs/backtests/2026-10-02-strategy-b-walkforward.md`), so nothing is frozen, no artifact is committed, and B may not be deployed.
  - `tests/test_strategy_b_frozen.py` fails if a value or an artifact appears without a passing report. It reads the constant as `seer_engine.strategies.b.STRATEGY_B_FROZEN` at call time; the package does not re-export it.
- `StrategyB` implements `Strategy` with `id = "B"` and `lookback = LOOKBACK`; `STRATEGY_B =
  StrategyB()`. Its contract is `picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d)}, M, d,
  p)` for every model, and no look-ahead, SPY's bars included. B-linear is the same `STRATEGY_B`
  with a ridge `BParams`.

### backtest (P3)

Every module except `io.py` is pure (same purity test as `strategies`). Nothing here writes to
the database.

- **`backtest.market`**: `Membership(intervals)` with `members_on(d) -> frozenset[str]` (both
  indices unioned, `[start, end)`), evaluated in memory instead of one query per date.
  `Market(history, membership, fx)`: `bar(symbol, d) -> Bar | None` builds a 4-dp `Decimal` `Bar`
  on demand (only for symbols with a live order, and SPY), `bars_on(d, symbols)`,
  `last_bar_date(symbol)`, `usd_idr_on(d)` (latest FX row dated `<= d`, `ValueError` when none),
  `spy()`.
- **`backtest.runner`**: `INITIAL_IDR = Decimal("20000000")`.
  `run_backtest(market, strategy, params, start, end, *, prepared=None, initial_idr=INITIAL_IDR) -> RunResult`
  is the "P3 backtest loop" below: each session `size_picks(picks(prev_session(S)))` → `step` →
  `close_unpriced` for held symbols whose bars ended for good (`last_bar_date < S`; a halt whose
  bars resume is left to the simulator's missing-bar rule). `RunResult` holds `snapshots`
  (`[0] = Snapshot(prev_session(start), cash0, cash0)`, then one per session), `events`, `closed`,
  `open_at_end` (marked at the last close, never liquidated) and rejection counts.
  `survivorship(market, start, end) -> tuple[YearGap, ...]`: per year, the (member, session) pairs
  with no bar, split into never-fetched symbols and other gaps.
- **`backtest.benchmark`**: `parse_dividends(text)`, `buy_and_hold(spy, start, end, initial_cash, *, dividends=(), name)`
  and `spy_curves(...) -> (price, total_return)`. Whole shares at the first session's open after
  the 0.1% cost, idle remainder, marked at each close, never sold. Total-return reinvests a
  dividend when `start < ex_date ≤ end`: cash `+= q(shares × amount)`, then whole shares at that
  close with `buy_cost`.
- **`backtest.metrics`**: `strategy_metrics(snaps, pnls) -> Metrics` and `checklist(m, spy_return)`,
  identical to `web/lib/metrics.ts` (a loss is `pnl ≤ 0`; PF = gross win / gross loss, `inf` with
  no loss; max drawdown on per-session equity; total return = last / first − 1;
  months = days / 30.44). Adds CAGR, average `days_held` and the exit-reason breakdown.
  `run_metrics(RunResult)`, `curve_metrics(BenchmarkCurve)`. `tests/test_backtest_metrics.py`
  replays every case in `web/lib/metrics.test.ts`.
- **`backtest.tuning`**: `IS_START = 2015-10-19` (the first session with 200 bars of history behind
  its `data_date`), `OOS_START = 2022-01-03` (in-sample ends 2021-12-31). `grid()`: the 81 params
  fixed before any result was seen — RSI `{5, 10, 15}` × limit `{0.25, 0.5, 0.75}` × TP
  `{0.75, 1.0, 1.5}` × SL `{1.0, 1.5, 2.0}` ATR. `select(rows)`: highest in-sample total return
  among runs with max DD ≤ 15% and PF ≥ 1.3; ties → lower max DD → earlier grid index;
  `DESIGN_PARAMS` when none qualifies. `gate(oos, spy_tr_oos) -> Verdict`: passes only when, on
  **out-of-sample**, total return > total-return SPY, PF ≥ 1.3 and max DD ≤ 15%.
- **`backtest.report`**: `BacktestReport`, `render_markdown`, `equity_csv`, `equity_svg`,
  `report_stem(data_end)`. Deterministic: the same inputs give byte-identical files. The Markdown
  carries two machine-readable lines, `frozen-params:` (the code's `STRATEGY_A_PARAMS` at run
  time) and `selected-params:` (the in-sample selection), which `test_strategy_a_frozen.py` reads
  with `parse_params_line`.
- **`backtest.io`** (impure): `load_market(conn, *, cache_dir=CACHE_DIR, refresh=False) -> (Market, bars_rows)`,
  `read_dividends(path=DIVIDENDS_CSV)`, `write_report(out_dir, report) -> list[Path]`,
  `write_wf_report(out_dir, report: WalkForwardReport) -> list[Path]` (renders all five files,
  `<stem>.md`, `-equity.csv`, `-equity.svg`, `-variants.svg`, `-grid.csv`, before writing any, LF
  endings; returns the paths in that order).

**Windows.** In-sample 2015-10-19 → 2021-12-31 (tuning); out-of-sample 2022-01-03 → the last SPY
bar (validation, run once); full 2015-10-19 → the last SPY bar (one continuous portfolio). Each
window starts its own 20,000,000 IDR portfolio at the FX rate on or before its first session, and
its own two SPY curves on the same session.

**The report** (`docs/backtests/<data end>-strategy-a.md`): data inventory; the in-sample grid,
all 81 rows; the selection and why; in-sample, out-of-sample and full-window results each against
price-only and total-return SPY (total return, CAGR, win rate, PF, max DD, trades, average days
held, exit reasons, go-live checklist); the survivorship note with per-year missing
(member, session) counts; the gate verdict in one sentence. `-equity.csv` is wide (`date` + one
column per curve) and `-equity.svg` is a hand-written chart, no plotting dependency.

**Committed result** (2026-10-02 data): gate **FAILED**. Strategy A fails the P3 gate: out of sample it returned −15.0% against +71.9% for total-return SPY, with profit factor 0.92 and max drawdown 33.3%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; P4 must not start until Strategy A is reworked.
See `docs/backtests/2026-10-02-strategy-a.md`.

**Survivorship.** 115 index members in the full window have no bars at all (delisted or
acquired; Yahoo no longer serves them), so the backtest cannot trade them (115 is the report's
"Index members in the window with no bars at all"). A dip-buying strategy is exactly what those
collapses would have hurt, so the result is biased in Strategy A's favour; the report counts the
gap per year.

### backtest walk-forward (P3b)

This adds to P3 without changing it. Every v1 call takes its unchanged code path, and the
committed v1 report re-renders byte-identically on its own data (checked by re-running `backtest` on the unchanged Neon data (2026-10-02, 1,817,429 bar rows)). Like
the rest of `backtest/`, every module here except `io.py` is pure, and the purity glob covers it.

- **`backtest.runner.ParamsSchedule(segments)`**: `segments` is `((first_session, params), ...)`,
  NYSE sessions, strictly ascending, at least one. `at(session)` gives the params of the last
  segment starting on or before `session`, and raises `ValueError` before the first.
  `run_backtest(..., params=<ParamsSchedule>, ...)` picks for session S with `params.at(S)` (S is
  the session traded, not `data_date`), and raises `ValueError` if `start` is before the first
  segment. Orders keep the bracket they were placed with across a switch. With any other `params`,
  `run_backtest` behaves exactly as in P3.
- **`backtest.metrics.metrics_through(r, end)`**: `run_metrics` of `r` cut at session `end`, using
  snapshots dated `<= end` and exits on or before `end`. **Prefix property:** it equals
  `run_metrics` of the same run with `end=end`, which tests prove on the scenario market and a
  Strategy A market.
- **`backtest.tuning.select(rows, *, fallback=DESIGN_PARAMS)`**: P3's rule, tie-breaks and reason
  strings, with the none-qualifies params as an argument. Without it, it behaves exactly as in P3.
- **`backtest.walkforward`**:
  - `FIRST_TRADE_YEAR = 2018`, `SEEN_BEFORE_START = tuning.OOS_START` (2022-01-03, the burned P3
    out-of-sample start), `COMBINED = "walk-forward"`.
  - `Fold(year, tune_start, tune_end, trade_start, trade_end)` and
    `folds(is_start, first_year, end)`.
  - `combinations()`: 324 `A2Params`, variant outer, grid inner.
  - `tune(market, strategy, prepared, combos, folds)`: one run per combination, and per fold a
    `GridRow` via `metrics_through(run, fold.tune_end)`. Sequential, in combination order.
  - `select_fold(rows, variant=None)`. The combined selection falls back to `A2_DESIGN_PARAMS`; a
    variant's own falls back to `A2Params(variant=v)`.
  - `schedule(folds, selections)`, then `walk_forward(...) -> WalkForward(name, folds, selections,
    run)`: one continuous portfolio from the first trade session to the data end.
  - `diagnostics(run) -> Diagnostics`: P/L by exit reason and by exit year, trades with < 3 shares,
    gross P/L, costs, and cost drag = costs ÷ gross ("—" when gross ≤ 0). Diagnostics **explain**
    the result and never reach `select`.
  - `window_metrics(run, start)` and `curve_window_metrics(curve, start)`: the "seen before" slice
    of the continuous curves.
  - `gate_p3b(wf, spy_tr, start, end) -> Verdict`.
- **`backtest.wf_report`**:
  - `WalkForwardReport`, `report_stem(data_end)` (`<data end>-strategy-a2-walkforward`),
    `render_markdown`, `equity_csv`, `grid_csv`, `equity_svg`, `variants_svg`. Deterministic: two
    renders are byte-equal.
  - Machine lines `p3b-gate:` (`GATE_KEY`), `last-fold-params:` (`LAST_FOLD_KEY`) and
    `frozen-params:` (`FROZEN_KEY`, `null` when nothing is frozen), read with
    `parse_machine_line(markdown, key) -> str`.
- **`backtest.io.write_wf_report(out_dir, report) -> list[Path]`**: the five files, all rendered
  before any is written.

**Folds** (anchored, yearly). For each trade year Y from 2018 to the data end's year:

- **Tune** on 2015-10-19 → the last session of Y−1.
- **Trade** the first session of Y → the last session of Y, or the data end.

The traded segments form **one** portfolio: 20,000,000 IDR at `prev_session(2018-01-02)`'s FX, with
params switching at each year's first session. Picks for that session use `data_date` = the last
session of Y−1 = `tune_end(Y)`. Each fold selects among all 324 (variant × grid) combinations with
P3's rule (highest tuning-window total return among max DD ≤ 15% and PF ≥ 1.3; ties → lower DD →
combination order), else V0 with the design values. Each variant also gets its own walk-forward,
with the variant fixed and the grid tuned per fold.

**Gate (P3b).** A2 passes only if the combined walk-forward curve (2018-01-02 → data end) beats
total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 15%, measured with P3's `metrics`
(web parity). The 2022-01-03 → data end window has been seen before. The report shows it only as a
labelled slice of the continuous curves, and it never feeds the gate.

**The report** (`docs/backtests/<data end>-strategy-a2-walkforward.md`) contains, in order:

1. the verdict;
2. data;
3. method, which lists everything tried;
4. every fold's windows, selection, reason and top-10 tuning rows (all 324 per fold are in
   `-grid.csv`);
5. the walk-forward vs both SPY curves;
6. the per-variant curves and selections;
7. the diagnostics;
8. "seen before";
9. the go-live checklist;
10. survivorship;
11. positions open at the end;
12. both charts and links to both CSVs (`-equity.svg`: walk-forward vs SPY; `-variants.svg`: the
    four variants + total-return SPY);
13. the gate verdict;
14. on a fail, the owner's options (handover §8);
15. the machine lines.

**Committed result** (2026-10-02 data, walk-forward 2018-01-02 → 2026-10-02): gate **FAILED**. Strategy A2 fails the P3b gate: walk-forward from 2018-01-02 to 2026-10-02 it returned +9.1% against +187.6% for total-return SPY, with profit factor 1.02 and max drawdown 29.1%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; Strategy A's one rework has failed, and P4 stays blocked.
See `docs/backtests/2026-10-02-strategy-a2-walkforward.md`.
Strategy A's one rework has failed. Strategy A is not reworked again on this data, and P4 stays blocked until the owner chooses among the report's options.

**Survivorship.** This is the same gap as P3: 115 index members in the window from
2015-10-19 have no bars at all. It biases every variant in its favour, and the report counts the gap
per year.

### backtest Strategy B walk-forward (P6a)

This adds to P3 and P3b without changing them. `walkforward.py`, `wf_report.py` and `backtest_wf.py`
are not edited, so A2's P3b report re-renders byte-identically on its own data (checked by
re-running `backtest_wf --end 2026-10-02` on the unchanged Neon data (1,817,429 bar rows): all five files `cmp`-equal). Like the rest of `backtest/`, every module here except `io.py`
is pure, and the purity glob covers it.

- **`backtest.labels`**:
  - `REASONS = ("expire", "tp", "sl", "gap", "time", "forced")`, with `code = index` and -1 for
    unresolved. `COST = 0.001`, which equals `float(sim.COST_RATE)` (tested).
  - `Labels(label, resolved, reason, fill, exit)`: arrays per row.
  - `label_orders(history, symbols, data_dates, limit, tp, sl, end) -> Labels` puts one bracket order
    per row, alone, under design §5 exactly as `sim.step` and the runner apply it, on NYSE sessions,
    reading bars dated ≤ `end` only:
    - The order session is `next_session(data_date)`. With no bar there, or low ≥ limit, the result
      is `expire`, label 0.0.
    - Otherwise it fills at min(open, limit), with no exit check on the fill session.
    - On each later session, in order: the day-5 time stop at the open; a gap through SL or TP at
      the open; SL intraday (first on a both-in-range bar); TP intraday. A session without a bar
      still counts toward the time stop.
    - A symbol whose bars end exits at its last close (`forced`).
    - Anything not resolved by `end` is unresolved (NaN / NaT / -1).
  - `label = exit × (1 − 0.001) ÷ (fill × (1 + 0.001)) − 1`, per share, so it does not depend on
    the share count. `resolved` is the exit session, or the expiry session when unfilled.
  - It is vectorized: session-aligned float matrices, one numpy pass per session offset over the
    still-open rows. A test proves it agrees with a one-order `run_backtest` on a seeded sample:
    the same reason, the same exit date, and the return within 1e-6.
- **`backtest.b_walkforward`**:
  - `B = "B"` and `B_LINEAR = "B-linear"` (curve names), `DECILES = 10`, `TOP_FEATURES = 5`.
  - `candidate_table(market, prepared, is_start, end) -> CandidateTable`: every candidate row from
    `prev_session(is_start)` through `prev_session(end)`, ordered by `(data_date, symbol)`. Its `X`
    equals that date's `Design` rows bit for bit. It carries the `b.bracket` prices (NaN when
    invalid) and `labels` from `label_orders(..., end=end)`.
  - `training_mask(table, fold)` is **the purge**. It keeps rows with a valid bracket whose label
    resolved on or before `fold.tune_end`, with `data_date ≥ prev_session(fold.tune_start)`. A trade
    still open at `tune_end` is excluded.
  - `train_folds(table, folds, kind) -> tuple[FoldModel, ...]`, sequential and in fold order.
    `FoldModel(fold, model, rows, label_mean, label_sum, pred_mean, r2, positive_share, importance)`:
    the in-fold values are information only.
  - `probe_determinism(table, fold) -> bool`: the fold's tree fit at 1 thread and at the default
    give equal digests.
  - `model_schedule(folds, fold_models)` gives a `ParamsSchedule` of `BParams` that switches at each
    year's first session. `walk_forward_b(market, prepared, folds, fold_models, name) -> BWalkForward`
    is one continuous portfolio from the first trade session to the data end.
  - `oos_predictions`, `calibration(pred, label) -> tuple[CalibrationRow, ...]` (10 deciles of the
    out-of-fold prediction, with mean predicted vs realized label) and
    `passed_nights(table, folds, fold_models) -> (passed, traded)`. These **explain** the result and
    never select anything.
  - `gate_p6a(wf, spy_tr, start, end, gated) -> Verdict`.
- **`backtest.b_report`**:
  - `BReport`, `report_stem(data_end)` (`<data end>-strategy-b-walkforward`), `render_markdown`,
    `equity_csv` (`date,b,b_linear,a2,spy_price,spy_tr`) and `equity_svg` (B, B-linear, A2 and both
    SPY curves). It is deterministic: two renders are byte-equal.
  - The machine lines are `p6a-gate:` (`GATE_KEY`), `gated-model:` (`GATED_KEY`),
    `last-fold-model:` (`LAST_FOLD_KEY`: kind, digest, `train_end`, rows and `label_sum` as a JSON
    string holding `repr(float)`, the retrain recipe) and `frozen-model:` (`FROZEN_KEY`, `null` when
    nothing is frozen). Read them with `parse_machine_line(markdown, key) -> str`.
- **`backtest.io`**:
  - `write_b_report(out_dir, report) -> list[Path]` renders the three files before writing any.
  - `MODELS_DIR` (`engine/data/models`).
  - `write_model_artifact(model_dir, data_end, model) -> (path, sha256)` writes
    `b_model.dumps(model)` to `<data end>-strategy-b.pkl`.

**Folds, training and trading.**
- The folds are exactly P3b's (`walkforward.folds`): fold Y trains on 2015-10-19 → the last session
  of Y−1 and trades Y, for 2018 → the data end. No fold selects anything: each one just fits B and
  B-linear on its purged rows.
- The traded segments form **one** portfolio: 20,000,000 IDR at `prev_session(2018-01-02)`'s FX,
  with the model switching at each year's first session. Orders keep the bracket they were placed
  with across a switch.
- Each night's picks are the candidates with a predicted net return > 0.0, ranked descending, ties
  broken by symbol, each with A's design bracket. The simulator fills the free slots in order, and
  a night with no positive prediction trades nothing.

**Gate (P6a).** The gated curve passes only if its walk-forward (2018-01-02 → data end) beats
total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 15%, measured with P3's `metrics`
(web parity). The gated curve is B, unless the last fold's determinism probe fails. Then the
pre-registered switch gates B-linear, and the verdict sentence says so. B-linear is otherwise
information only and never promotable on this data. A2's walk-forward is on the chart and in the
tables as information.

**The report** (`docs/backtests/<data end>-strategy-b-walkforward.md`) contains, in order:

1. the title;
2. data;
3. method, which lists everything that was fixed in advance;
4. every fold's training summary for B and B-linear (rows, label mean, in-fold R², pred mean,
   positive share, top 5 features by split gain, or by |coef| × std for B-linear);
5. B, B-linear and A2 vs both SPY curves;
6. year by year;
7. the diagnostics: P/L by exit reason and by year, < 3 shares, cost drag, passed nights and the
   calibration table;
8. "seen before" (2022-01-03 →);
9. the go-live checklist;
10. survivorship, with the learned-model caveat;
11. positions open at the end;
12. the chart;
13. the gate verdict;
14. on a fail, the owner's options (b), (c) and (d) (handover §8);
15. the machine lines.

**Committed result** (2026-10-02 data, walk-forward 2018-01-02 → 2026-10-02): gate **FAILED**. Determinism probe: bit-identical at 1 thread and at the default, so B is gated. Strategy B fails the P6a gate: walk-forward from 2018-01-02 to 2026-10-02 it returned +13.3% against +187.6% for total-return SPY, with profit factor 1.03 and max drawdown 57.6%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; Strategy B's one round has failed on this data, and P4 stays blocked.
See `docs/backtests/2026-10-02-strategy-b-walkforward.md`. B made +13.3% (PF 1.03, max DD 57.6%)
and B-linear +20.6% (PF 1.05, max DD 32.4%), against +187.6% for total-return SPY; A2's
walk-forward on the same chart made +9.1%.
B's one round has failed on this data. B is not reworked on it, no model is frozen, and P4 stays blocked until the owner chooses among the report's options.

**Survivorship.** The gap is the same as P3's: 115 index members in the window from
2015-10-19 have no bars at all. A learned model can absorb that bias more than a rule can, because
the losers it never saw are exactly the ones it would have needed to learn to avoid. The report says
so.

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
- `numpy>=2`: indicator math and the float64 arrays in `strategies.base.History` (declared in P3; it was already installed through pandas).
- `requests>=2.32`: HTTP, through one module-level `Session` in `http.py`.
- `python-dotenv>=1.0`: parses `.env.local`. The file is parsed, never `source`d, because it contains an unquoted `&`.
- `yfinance>=1.0`: used only by `yahoo.py` (phase 3 backfill), imported lazily inside `yf_download`.
- `scikit-learn>=1.9,<1.10` (P6a): Strategy B's `HistGradientBoostingRegressor`, used only by `strategies.b_model`. The minor version is pinned, because a frozen model is a pickle of its estimator, and `b_model`'s digest reads the fitted trees' private node arrays. It brings `threadpoolctl` (used to cap the threads in the determinism probe), `joblib` and `scipy`. `cli.discover` imports every command, so `backtest_b` makes every command load scikit-learn at startup (about 0.5–1 s); `import seer_engine.strategies` alone does not.
- dev: `pytest>=8`.

### Internal module graph
- `cli` imports `config` and `commands`. `commands.migrate` imports `config` and `db`.
- `db` imports `config`. `demo` imports `db`.
- `prices` imports only the standard library; `bars` imports `prices` and re-exports it. `fx` imports `http` and `bars.to_decimal`. `runs` imports `dates.RunDates` and `http.redact`.
- `http` imports `__version__` for `USER_AGENT`.
- `yahoo` imports `bars` and pandas. `commands.backfill` imports `bars`, `dates`, `db`, `demo`, `fx`, `universe` and `yahoo`.
- `sim.model` imports `prices`. `sim.lifecycle` and `sim.split_adjust` import `dates`, `prices` and `sim.model`. `sim.sizing` imports `dates` and `sim.model`. Nothing in `sim` imports `bars`, `db` or `http`.
- `strategies.*` import numpy, `prices`, `sim` (for `Pick` and `q`) and each other. `backtest.market`, `runner`, `benchmark`, `metrics`, `tuning` and `report` import numpy, `dates`, `prices`, `sim`, `strategies` and each other. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` imports `config`, psycopg, pandas, numpy and the pure backtest modules. `commands.backtest` imports `config`, `db`, `dates`, `prices`, `universe` (for `BENCHMARK`), `backtest.*` and `strategies.a`.
- `strategies.a2` imports numpy, `sim`, `strategies.a`, `strategies.base` and `strategies.indicators`; never `universe` (psycopg), so `REGIME_SYMBOL` repeats `universe.BENCHMARK` and a test asserts they are equal. `backtest.walkforward` imports `dates`, `strategies.a2`, `strategies.base` and `backtest.runner`, `metrics`, `tuning`, `market` and `benchmark`. `backtest.wf_report` imports `backtest.report`'s helpers (read-only), `dates`, `sim`, `strategies.a` (`ATR_N`, `SMA_N`), `strategies.a2`, and `backtest.metrics`, `runner`, `tuning`, `benchmark` and `walkforward`. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` also imports `wf_report` (for `write_wf_report`). `commands.backtest_wf` imports `config`, `db`, `dates`, `universe` (for `BENCHMARK`), `backtest.io`, `walkforward`, `benchmark`, `market`, `metrics`, `runner`, `tuning`, `wf_report`, `commands.backtest` (for `never_fetched_members`) and `strategies.a2`.
- `strategies.b_model` imports numpy, scikit-learn (`HistGradientBoostingRegressor`), `threadpoolctl`, `pickle` and `hashlib`, and nothing from the engine. scikit-learn loads none of psycopg, requests or yfinance, so the module stays pure. `strategies.b` imports numpy, `sim` (`Pick`), `strategies.a` (`_bracket`, `Features`, `DESIGN_PARAMS`), `strategies.base` and `strategies.indicators`. It never imports `b_model`, so `import seer_engine.strategies` does not load scikit-learn, and never `universe` (psycopg), so `SPY_SYMBOL` repeats `universe.BENCHMARK` and a test asserts they are equal.
- `backtest.labels` imports numpy, `dates`, `sim.model` (`TIME_STOP_DAYS`) and `strategies.base`; its `COST` repeats `sim.COST_RATE` as a float, and a test pins them equal. `backtest.b_walkforward` imports numpy, `dates`, `strategies.b`, `strategies.b_model`, `backtest.labels`, `runner`, `metrics`, `market`, `tuning` (`Verdict`) and `walkforward` (`Fold` and the private `_check_folds`, `_day`, `_session`, `_join`, `_GATE_NAMES`, read-only). `backtest.b_report` imports `backtest.report`'s and `wf_report`'s helpers (read-only), `dates`, `strategies.a`, `strategies.b`, `strategies.b_model` (constants), and `backtest.b_walkforward`, `labels`, `metrics`, `runner`, `tuning`, `benchmark` and `walkforward`. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` also imports `b_report` and `strategies.b_model` (for `write_b_report` and `write_model_artifact`). `commands.backtest_b` imports `config`, `db`, numpy, `backtest.io`, `b_walkforward`, `b_report`, `walkforward`, `benchmark`, `market`, `metrics`, `runner`, `commands.backtest_wf` (`resolve`, `tune_all`, `run_walk_forward`, `BacktestWfError`), `commands.backtest` (`never_fetched_members`), `strategies.a2`, `strategies.b` and `strategies.b_model`.
### Standard library
`argparse`, `importlib`/`pkgutil` (command discovery), `logging`, `contextlib`, `dataclasses`, `decimal`, `functools.lru_cache`, `re`, `time`.

## Reverse Dependencies

- Within `engine/`, the phase 2 to 4 modules consume the API above exactly as written in the plan's "Shared interface contract": `membership.py` and `commands/universe.py` (phase 2), `yahoo.py` and `commands/backfill.py` (phase 3), and `massive.py`, `splits.py` and `commands/nightly.py` (phase 4).
- Phase 5 will add `.github/workflows/{engine-ci,nightly,universe,backfill}.yml`, which invoke the CLI.
- P4 (nightly) will call `strategies.a.STRATEGY_A.picks(...)` with `STRATEGY_A_PARAMS` and write `STRATEGY_A_PARAMS.as_dict()` to `strategies.params`. P6 adds strategies B and C beside `a.py`, implementing the same `Strategy` protocol.
- P4 is blocked: the P3b gate failed, and `STRATEGY_A2_PARAMS` is `None`. Nothing may deploy Strategy A or A2. P6's Strategy B can reuse `backtest.walkforward` (handover §8 option (a)), if the owner chooses it.
- P4 stays blocked: the P6a gate failed, `STRATEGY_B_FROZEN` is `None`, and no model artifact is committed. Nothing may deploy Strategy A, A2 or B. B's one round has failed on this data. The owner chooses among the report's options (b), (c) and (d).
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
- Simulator: `tests/test_sim_scenario.py::test_benchmark_2950_sessions_x_4_slots` runs 2,950 NYSE sessions (2015-01-02 onward) × 4 slots with `size_picks` + `step` every session on synthetic bars, using `Decimal` throughout. Measured: **0.20 s** on WSL2, Python 3.11 (bound in the test: 20 s). A 10-year backtest is therefore dominated by loading bars and computing signals, not by the simulator. Floats are not needed.
- Backtest (P3), measured on the 2026-10-02 data (1,817,429 bar rows, 663 symbols), WSL2, Python 3.11:
  - Load: about 25 s from Neon on a cache miss (one streamed `COPY`, timed from the run log), 0.7 s from the 90 MB pickle cache (including the fingerprint query).
  - `STRATEGY_A.prepare` over all symbols and dates: 2.8 s, once per command.
  - Grid: 81 in-sample runs in 37.7–39.0 s, about 0.5 s each.
  - Whole command: 1:09 cold, 0:46–0:53 with the cache; peak RSS 420 MB.
  - Bars live as float64 arrays; `Decimal` `Bar`s are built only for symbols with a live order and for SPY, so the simulator's share of the time stays small.
- Walk-forward (P3b), measured on the 2026-10-02 data (1,817,429 bar rows, 663 symbols), WSL2, Python 3.11:
  - Load: 0.6 s from the 90 MB pickle cache (about 37 s from Neon on a miss). `STRATEGY_A2.prepare` (Strategy A's columns plus SPY's regime column): 2.8 s, once per command.
  - Tuning: 324 combinations, sequential, in 236.9 s, about 0.7 s each. Each combination is **one** run over 2015-10-19 → 2025-12-31, sliced into the 9 folds' tuning windows with `metrics_through`. That is exact by the runner's prefix property, and about 9× less work than re-simulating every fold.
  - The five walk-forward runs (combined + 4 variants, 2018-01-02 → 2026-10-02) and their SPY curves: about 4 s.
  - Whole command: 4:13 for the first run, 4:14 for the re-run; peak RSS 430 MB.
- Strategy B walk-forward (P6a), measured on the 2026-10-02 data (1,817,429 bar rows, 663 symbols), WSL2, Python 3.11, scikit-learn 1.9.1:
  - Load: 0.7 s from the 90 MB pickle cache (about 18 s streaming from Neon on a miss). `STRATEGY_B.prepare` (the 18 raw window columns for every (symbol, date) with 200 bars, plus SPY's 3; 1,684,380 rows over 662 symbols): 4.6–4.8 s, once per command.
  - Candidate table and labels: 1,304,876 candidate rows ranked per date and labelled by the vectorized bracket labeler (1,304,243 with a valid bracket and a resolved label) in 12.4 s. It is one numpy pass per session offset over the still-open rows, not one `sim.step` per row.
  - Fits: 9 tree fits in 30.5 s and 9 ridge fits in 2.1 s, sequential, in fold order (up to 1,207,705 rows × 18 features in the last fold). The determinism probe (the last fold's tree refit at 1 thread and at the default) took 13.1 s.
  - The B and B-linear walk-forward runs (2018-01-02 → 2026-10-02): 17.1 s and 4.7 s; the SPY curves 0.02 s. The A2 information curve, recomputed through `backtest_wf`'s pipeline (D12): 242.6 s, about 73% of the command. Survivorship, passed nights and both calibrations: 3.5 s.
  - Whole command: 5:47 for the first run, 5:53 for the re-run (cache hits both); peak RSS 1,548 MB (the candidate table and the per-fold training matrices).
- There is no benchmark coverage for the DB writers.

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

### Simulator: P3 backtest loop

History is already split-adjusted backwards, so the backtest never calls `apply_split`.

`backtest.runner.run_backtest` implements this loop; the sketch below is the shape.

```python
from decimal import Decimal
from seer_engine import dates
from seer_engine.sim import (
    Snapshot, close_unpriced, initial_cash_usd, new_portfolio, size_picks, step,
)

pf = new_portfolio(initial_cash_usd(Decimal("20000000"), usd_idr_on(start)))
events, snapshots = [], []
for session in dates.sessions(start, end):
    picks = strategy.picks(data_date=dates.prev_session(session))  # ranked Picks, made after that close
    pf = size_picks(pf, picks, session).portfolio
    result = step(pf, session, bars_on(session, pf.held_symbols()))  # {symbol: Bar}; missing = no bar
    pf = result.portfolio
    events += result.events
    snapshots.append(result.snapshot)
    gone = delisted_after(session, pf.open_orders())  # P3 knows from data when a symbol's bars end
    if gone:
        pf, forced = close_unpriced(pf, gone)
        events += forced
        snapshots[-1] = Snapshot(session, pf.cash, pf.equity)
```

### Simulator: P4 nightly

One strategy, one night: `rd = dates.run_dates()`. The session to settle is `rd.data_date`, and the picks are for `rd.session_date`.

```python
pf = load_portfolio(conn, strategy_id)
# Portfolio(cash, equity) from the last equity_snapshots row; orders = rows with status
# pending/open, sorted by slot; marks = last close per open symbol; last_session = last snapshot date.
# The marks must be in the same (pre-split) units as the orders: take them from closes as they were
# before splits.apply rescaled history, or apply_split would rescale an already-adjusted mark.
for split in splits_executing_on(conn, rd.data_date):        # recorded by splits.apply this run
    pf, split_events = apply_split(pf, split.symbol, split.factor, rd.data_date)
    persist_events(conn, strategy_id, split_events)            # UPDATE orders prices/shares; cash in lieu
result = step(pf, rd.data_date, bars_on(conn, rd.data_date, pf.held_symbols()))
persist_events(conn, strategy_id, result.events)              # fill/exit/expire -> UPDATE orders
persist_snapshot(conn, strategy_id, result.snapshot)          # equity_snapshots (strategy_id, date)
sized = size_picks(result.portfolio, ranked_picks, rd.session_date)
insert_orders(conn, strategy_id, sized.placed)                # status 'pending', slot 1..4
```

`Event.order` maps 1:1 onto `orders` columns. Its row key is `(strategy_id, order.session_date, order.symbol)`. Everything runs inside one `db.transaction`, so a failed night leaves nothing half-written.

### Strategy: P4 nightly picks

```python
from seer_engine import dates
from seer_engine.sim import size_picks
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.base import history_from_bars

rd = dates.run_dates()
# At least STRATEGY_A.lookback (200) bars per symbol, ending at rd.data_date; more is fine.
history = {s: history_from_bars(s, bars) for s, bars in last_bars_by_symbol(conn, rd.data_date).items()}
members = universe.members_on(conn, rd.data_date)
picks = STRATEGY_A.picks(history, members, rd.data_date, STRATEGY_A_PARAMS)  # ranked, deepest RSI first
sized = size_picks(result.portfolio, picks, rd.session_date)                  # after settling data_date
```

These are the same functions and parameters the committed backtest ran, so a night's picks are the
backtest's picks for that date given the same bars.

### Backtest: run and read the report

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine backtest
```

Then read `docs/backtests/<data end>-strategy-a.md`. If `STRATEGY_A_PARAMS` differs from the new
report's `selected-params:` line, `test_strategy_a_frozen.py` fails until the constant is updated
(with its comment) or the report is not committed.

### Backtest: walk-forward (P3b)

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine backtest_wf
```

Then read `docs/backtests/<data end>-strategy-a2-walkforward.md`. Its `p3b-gate:`,
`last-fold-params:` and `frozen-params:` lines are what `test_strategy_a2_frozen.py` reads:

- On a passing report, `STRATEGY_A2_PARAMS` must equal `last-fold-params:`, and the comment above
  it must name the report.
- On a failing report, it must be `None`.

A newer report with a different outcome or selection fails the test until the constant follows it.
Committing a newer report is a re-measurement on new data, not a new rework.

### Backtest: Strategy B walk-forward (P6a)

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine backtest_b
```

Then read `docs/backtests/<data end>-strategy-b-walkforward.md`. Its `p6a-gate:`, `gated-model:`,
`last-fold-model:` and `frozen-model:` lines are what `test_strategy_b_frozen.py` reads:

- On a passing report, `backtest_b` also writes `engine/data/models/<data end>-strategy-b.pkl` and
  logs its sha256. `STRATEGY_B_FROZEN` must name the report, that artifact, its sha256 and the last
  fold's `train_end`. The artifact must load (`b_model.loads`) to the `last-fold-model:` digest, and
  the comment above the constant must name the report. Re-run after freezing, so the report records
  `frozen-model:`.
- On a failing report, the constant must be `None`, and no `*-strategy-b.pkl` may be committed.

A newer report with a different outcome or model fails the test until the constant and the artifact
follow it. Committing a newer report is a re-measurement on new data, not a new round.

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

The P3 sections (`strategies`, `backtest`, the `backtest` command and the committed report) were
added on 2026-10-03; their design, invariants and decisions are in `STRATEGY_A_BACKTEST_PLAN.md`
and `docs/handover/2026-10-03-strategy-a-backtest.md`.

The P3b sections (`strategies.a2`, the walk-forward modules, the `backtest_wf` command and the
committed walk-forward report) were added on 2026-10-03. Their design, invariants and decisions are
in `STRATEGY_A_REWORK_PLAN.md` and `docs/handover/2026-10-03-strategy-a-rework.md`.

The P6a sections (`strategies.b_model`, `strategies.b`, the labeler, the B walk-forward and report
modules, the `backtest_b` command and the committed P6a report) were added on 2026-10-03. Their
design, invariants and decisions are in `STRATEGY_B_RANKER_PLAN.md` and
`docs/handover/2026-10-03-strategy-b-ranker.md`.
