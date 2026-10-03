# Package: seer_engine

**Location**: `engine` (src layout: `engine/src/seer_engine`)
**Last Updated**: 2026-10-03 (Strategy A + backtest P3, phase 6 of `STRATEGY_A_BACKTEST_PLAN.md`: `strategies`, `backtest`, `backtest` command, committed report)

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
      __init__.py           re-exports the public names of base and a
      base.py               History, history_from_bars(), Strategy protocol
      indicators.py         sma / wilder_rsi / wilder_atr / mean_dollar_volume windows, rolling()
      a.py                  Strategy A: AParams, DESIGN_PARAMS, STRATEGY_A_PARAMS (frozen), StrategyA
      a2.py                 Strategy A2 variants V0–V3 (rework P1; full docs pending phase 6)
    backtest/               10-year backtest (P3); every module but io.py is pure
      __init__.py           docstring only
      market.py             Membership, Market: bars, universe and FX in memory
      runner.py             run_backtest(), RunResult, survivorship()
      benchmark.py          SPY buy-and-hold, price-only and total-return
      metrics.py            Metrics, strategy_metrics(), checklist() (web/lib/metrics.ts parity)
      tuning.py             windows, the 81-run grid, select(), gate()
      walkforward.py        anchored yearly walk-forward for A2: folds, tune, select_fold, gate_p3b (rework P3; full docs pending phase 6)
      report.py             BacktestReport, render_markdown(), equity_csv(), equity_svg()
      wf_report.py          walk-forward (P3b) report: WalkForwardReport, render_markdown(), equity/grid CSVs, equity/variants SVGs, machine lines (rework P4; full docs pending phase 6)
      io.py                 Neon loader + bar cache, dividends CSV, report writers write_report() / write_wf_report() (impure)
    commands/
      __init__.py           command-module contract
      migrate.py            `migrate` command
      backfill.py           `backfill` command (phase 3)
      backtest.py           `backtest` command (P3)
      backtest_wf.py        `backtest_wf` command: A2 anchored yearly walk-forward vs SPY, P3b gate, report (read-only; flags --out --cache-dir --refresh-cache --is-start --first-year --end --dividends; exit 0 pass or fail, 2 bad data/args) (rework P5; full docs pending phase 6)
  tests/                    pytest; DB tests need PG_TEST_URL
  data/spy_dividends.csv    SPY dividends (ex_date, amount_usd), vendored from yfinance (see data/SOURCES.md)
  .cache/                   gitignored; bars-<max date>-<rows>.pkl written by the backtest loader
docs/backtests/             committed backtest reports: <data end>-strategy-a.md, -equity.csv, -equity.svg
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

### Standard library
`argparse`, `importlib`/`pkgutil` (command discovery), `logging`, `contextlib`, `dataclasses`, `decimal`, `functools.lru_cache`, `re`, `time`.

## Reverse Dependencies

- Within `engine/`, the phase 2 to 4 modules consume the API above exactly as written in the plan's "Shared interface contract": `membership.py` and `commands/universe.py` (phase 2), `yahoo.py` and `commands/backfill.py` (phase 3), and `massive.py`, `splits.py` and `commands/nightly.py` (phase 4).
- Phase 5 will add `.github/workflows/{engine-ci,nightly,universe,backfill}.yml`, which invoke the CLI.
- P4 (nightly) will call `strategies.a.STRATEGY_A.picks(...)` with `STRATEGY_A_PARAMS` and write `STRATEGY_A_PARAMS.as_dict()` to `strategies.params`. P6 adds strategies B and C beside `a.py`, implementing the same `Strategy` protocol.
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
