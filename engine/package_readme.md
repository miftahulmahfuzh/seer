# Package: seer_engine

**Location**: `engine` (src layout: `engine/src/seer_engine`)
**Last Updated**: 2026-10-04 (P6 Strategy C, phase 7 of `STRATEGY_C_NEWS_VETO_PLAN.md`: `strategies.c`, `finnhub`, `llm` call options, roster entry `C`, the `news_vetoes` store, migration 004, the `veto` command, `paper` / `paper_check` deciding and replaying C)

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
- Trade rules as a value and a dev-window strategy search (P7a): `sim.rules` (`TradeRules`, with `DESIGN_V0` reproducing design §5 exactly) and a second pure engine, `sim.book` (signal exits, rebalancing, dividends, fractional shares, open entries, idle instruments); the `Allocator` protocol and the families F1–F11 (`strategies/allocator.py`, `f_index.py`, `f_rotation.py`, `f_factor.py`, `f_swing.py`); `backtest/book_runner.py`; a local, gitignored research store of pre-2015 history (`research.py`, `research_store` command); and a pre-registered registry run only on the development window (≤ 2015-10-16) by `backtest/dev.py`, `dev_report.py`, `registry.py` and the `backtest_dev` command, which writes the dev report and the P7b pre-registration
- Nightly paper trading (P4, paper-only by the owner's option (b), 2026-10-04): a frozen roster of four paper portfolios (`SPY` the champion and benchmark, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M`) stepped one session at a time by pure night functions (`paper/bracket.py`, `paper/book.py`, `paper/benchmark.py`) that mirror the backtest runners' loop bodies; persisted in migration 003's tables by `paper/store.py`; driven by the `paper` command after `nightly`; proven equal to a one-shot `run_rules` / `buy_and_hold` replay by `paper_check`; optionally explained by an LLM (`explain`). No real-money path exists, and design §1 is unchanged
- Strategy C on paper (P6): a fifth roster entry `C` whose picks are A's first 10 ranked candidates minus every symbol whose nightly news check did not say `allow`. `strategies.c` holds the pure part (the `NewsVeto` strategy, the frozen prompt `c-veto-v1`, the JSON verdict parser); `finnhub.py` reads company news and earnings dates; the `veto` command asks the LLM once per candidate before `paper` and stores every verdict and the headlines it saw in `news_vetoes` (migration 004); `paper` and `paper_check` read only stored verdicts, so the replay never re-asks the LLM. A failed or missing verdict is no trade (design §8). No backtest gate applies (design §1 item 5)

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
    research.py             local research store: build_store() / load_store(), DEV_END guard (impure; P7a)
    dividends.py            Massive cash dividends (CD + SC) per ex-date, upsert into `dividends` (P4)
    llm.py                  Anthropic-compatible Messages call for `explain` (P4) and `veto` (P6, with temperature/thinking/max_tokens per call)
    finnhub.py              Finnhub company news and earnings calendar, rate-limited, key in a header only (P6)
    sim/                    fill simulator: pure, deterministic, Decimal-only (P2)
      __init__.py           public surface; import everything from seer_engine.sim
      model.py              constants, money helpers, Order, Portfolio, Event, Snapshot, StepResult
      lifecycle.py          step(), close_unpriced()
      sizing.py             Pick, Rejection, SizingResult, size_picks()
      split_adjust.py       apply_split()
      rules.py              TradeRules, DESIGN_V0, V0_BOOK, the presets, the rank/resize cadence split (P7a)
      book.py               the book engine: Target, Book, Position, Fill, Trade, step_book(), close_book_unpriced() (P7a); apply_book_split(), BookSplit (P4)
    paper/                  nightly paper trading (P4); every module but store.py is pure
      __init__.py           docstring only
      roster.py             the frozen roster: five entries (C since P6), canonical spec text, digest, backtest_gate
      bracket.py            settle_bracket(), decide_bracket(): run_backtest's loop body for one session
      book.py               settle_book(), decide_book(): run_book's loop body for one session
      benchmark.py          BenchmarkState, start_benchmark(), split_benchmark(), step_benchmark(): buy_and_hold for one session
      replay.py             the pure comparison behind paper_check
      store.py              load/save paper state, windowed market, splits and dividends queries, news verdicts (impure)
    strategies/             strategy layer: pure; float64 indicators, Decimal picks (P3)
      __init__.py           re-exports the public names of base, a, a2 and b (never b_model, so importing the package does not load scikit-learn)
      base.py               History, history_from_bars(), Strategy protocol
      indicators.py         sma / wilder_rsi / wilder_atr / mean_dollar_volume / mean / stdev_return windows, rolling()
      a.py                  Strategy A: AParams, DESIGN_PARAMS, STRATEGY_A_PARAMS (frozen), StrategyA
      a2.py                 Strategy A2 (P3b): A2Params, VARIANTS V0-V3, regime_on, STRATEGY_A2_PARAMS, StrategyA2
      b_model.py            Strategy B's model (P6a): fit_tree / fit_ridge, BModel (digest identity), importance, dumps / loads
      b.py                  Strategy B (P6a): 18 features, rank01, candidates, BParams, picks > 0, FrozenModel, STRATEGY_B_FROZEN, StrategyB
      c.py                  Strategy C (P6): CParams, STRATEGY_C_PARAMS, the frozen prompt c-veto-v1, candidates(), NewsVeto, parse_verdict()
      allocator.py          Allocator protocol (target weights), target_from_close, month_end_closes, PICKS / BLEND / VOLTARGET (P7a); MarketAware protocol + prepare_for() (edgar-fundamentals)
      f_index.py            F1/F10 TIMING (trend-timed index), F11 CALENDAR (turn of month) (P7a)
      f_rotation.py         F2/F3 ROTATION (dual momentum, sector rotation) (P7a)
      f_factor.py           F4/F5/F6 FACTOR (momentum, low vol, momentum + low vol) on index members (P7a)
      f_swing.py            F7 SWING (longer-horizon RSI(2) mean reversion, signal exits) (P7a)
    backtest/               10-year backtest (P3) and walk-forward (P3b, P6a); every module but io.py is pure
      __init__.py           docstring only
      market.py             Membership, Market: bars, universe, FX and the point-in-time SEC fact panel in memory; EMPTY_FUNDAMENTALS, Market.with_fundamentals() (edgar-fundamentals)
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
      book_runner.py        run_book(), run_rules() (DESIGN_V0 -> run_backtest unchanged), BookResult, RunStats, run_stats() (P7a)
      dev.py                DEV_END guard, Candidate, candidate_window(), run_registry(), D8 finalists(), deflated_sharpe() (P7a)
      dev_report.py         DevReport, Markdown, rows/curves CSVs, frontier SVG, P7b pre-registration (P7a)
      registry.py           REGISTRY: the append-only candidate registry (P7a)
      io.py                 Neon loader + bar cache, dividends CSV, report writers write_report() / write_wf_report() / write_b_report() / write_dev_report(), write_model_artifact() (impure)
                            load_panel() + fact cache, read_facts() -- the tree's one declared impure backtest edge for fundamentals (edgar-fundamentals)
    fundamentals/           raw SEC XBRL facts -> point-in-time panel: pure, like `strategies` (edgar-fundamentals)
      __init__.py           public surface; `sue` stays a module, never re-exported
      ladder.py             LADDER_TAGS, the ingest allowlist the impure ingest command imports; per-metric tag preference order
      panel.py              Fact, Snapshot, FundamentalPanel.as_of(symbol, t) -> Snapshot (the one read surface), EMPTY_PANEL (what Market.fundamentals defaults to), FACT_COLUMNS (the 12-column projection contract)
                            filed <= t only, never period_end; tiebreak (filed desc, rung asc, accn desc) per period; restatements preserved, never overwritten; flow metrics annual, not TTM; gross profit reported -> derived (Revenues - CostOfRevenue, same fiscal period end) -> none, never zero, never partial
      sue.py                standardized unexpected earnings on the seasonal random walk EPS_q - EPS_{q-4}, scaled by the dispersion of prior surprises; MIN_QUARTERS = 9
    commands/
      __init__.py           command-module contract
      migrate.py            `migrate` command
      backfill.py           `backfill` command (phase 3)
      backtest.py           `backtest` command (P3)
      backtest_wf.py        `backtest_wf` command (P3b)
      backtest_b.py         `backtest_b` command (P6a)
      research_store.py     `research_store` command (P7a)
      backtest_dev.py       `backtest_dev` command (P7a)
      nightly.py            `nightly` command (P1; P4 adds dividends and held paper symbols)
      paper.py              `paper` command (P4)
      paper_check.py        `paper_check` command (P4)
      explain.py            `explain` command (P4)
      veto.py               `veto` command (P6): Strategy C's nightly news check
  tests/                    pytest; DB tests need PG_TEST_URL
  data/spy_dividends.csv    SPY dividends (ex_date, amount_usd), vendored from yfinance (see data/SOURCES.md)
  .cache/                   gitignored; bars-<max date>-<rows>.pkl and fundamentals-<max filed>-<rows>.pkl written by the backtest loader
  .research/                gitignored; the P7a research store: bars.csv, dividends.csv, fx.csv, unserved.csv, manifest.json (research_store), plus the optional fundamentals.csv (--with-fundamentals)
docs/backtests/             committed reports: <end>-strategy-a{.md,-equity.csv,-equity.svg} (P3); <end>-strategy-a2-walkforward{.md,-equity.csv,-equity.svg,-variants.svg,-grid.csv} (P3b); <end>-strategy-b-walkforward{.md,-equity.csv,-equity.svg} (P6a); <run date>-p7a-dev-exploration{.md,-rows.csv,-curves.csv,-frontier.svg} (P7a)
docs/plans/                 <run date>-p7b-preregistration.md: the P7b finalists (or "none eligible"), written by backtest_dev (P7a)
db/migrations/002_engine.sql  (outside the package, owned by it)
db/migrations/003_paper.sql   (outside the package; paper state, book tables, dividends, roster rows; P4)
db/migrations/004_news_veto.sql (outside the package; the C roster row and news_vetoes; P6)
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

### `research_store` (P7a)

```
python -m seer_engine research_store [--dry-run] [-v] [--store STORE] [--batch-size BATCH_SIZE] [--verify]
                                    [--with-fundamentals] [--refresh-fundamentals] [--coverage]
```

This builds the local research store (D5). It covers pre-2015 bars for every S&P 500 member since
1996 and Nasdaq-100 member since 2007 that yfinance can serve, plus the 21 research ETFs, cash
dividends from the start, and Frankfurter USD/IDR. It **never connects to Neon** and needs no
database setting — `--with-fundamentals` is the single exception, below.

- **`--store`** defaults to `engine/.research` (gitignored), and **`--batch-size`** to 40 symbols
  per yfinance request.
- **`--with-fundamentals`** (edgar-fundamentals) additionally reads the SEC point-in-time fact
  panel through `backtest.io.read_facts()` (`DATABASE_URL_UNPOOLED`, the one place in this command
  that needs a database) and writes it as the store's **optional** fifth file, `fundamentals.csv`,
  so a later dev/lab run sees a non-empty `Market.fundamentals`. Without the flag the store carries
  no panel and the run ranks on bars alone, silently. The read lives in `backtest/io.py`, not here:
  `test_research_store.py::test_no_neon_and_no_database_url_needed` AST-scans both `research.py`
  and this command and fails either one that names `seer_engine.db` or `psycopg`. Omitting the flag
  leaves the store byte-identical to a pre-fundamentals build, fingerprint included.
- **`--refresh-fundamentals`** (fundamental-panel-coverage) rewrites `fundamentals.csv` **only**:
  `bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` are carried over from the existing
  store byte for byte and every `_COUNT_KEYS` value with them, so the panel changes and the bar
  history does not. It exists because `build_store` always downloads every symbol's bars first,
  and two yfinance crawls on two days give two different fingerprints — which would break
  comparability with the trials already recorded. It needs `DATABASE_URL_UNPOOLED` (set
  `SEER_ENV_FILE` to the train env file) and re-seals and swaps atomically; nothing is written
  on failure.
- **`--coverage`** (fundamental-panel-coverage) loads the store and prints, for each sampled
  dev-window date, how many symbols the panel can actually rank — a symbol counts only when
  `as_of` returns a snapshot with **non-empty `observations`** whose newest fact was filed within
  `max_stale_days` — plus one fraction over the window. `as_of` never returns `None`, so a
  presence check measures nothing; this is the content check, and it is the same measure
  `lab run` refuses on below `fundamentals.coverage.MIN_DEV_COVERAGE`. No network, no database.
  It reads no bars, so membership, `min_price` and `min_dollar_volume` are not applied and the
  fraction is an **upper bound**: below the floor is conclusive, above it is necessary and not
  sufficient.
- **The build** is throttled with backoff and runs all-or-nothing: temp files first, then a rename.
  The same downloads give byte-identical files and the same fingerprint. Nothing dated after
  2015-10-16 is kept.
- **`--verify`** uses no network. It loads the store, checks every file's sha256 against
  `manifest.json` and that no row is after 2015-10-16, runs three data checks (SPY has a bar on
  every NYSE session 1993-02-01 → 2015-10-16; SPY's 2015 dividends equal the vendored
  `data/spy_dividends.csv`; AAPL's 2012 dividends are on the split-adjusted price scale), and
  prints the fingerprint and the counts. It is the check to run before any dev run.
- **`--dry-run`** builds into a temporary directory, verifies it, and discards it.
- **Logs:** batches, unserved symbols, counts, and the fingerprint.
- **Exit codes:** 0 when the store is built (or loaded) and all three checks pass; 1 when the build
  fails (nothing is written, any previous store is kept) or a check fails; 2 when the store is
  missing or invalid (a tampered file, or a row after `DEV_END`).

### `backtest_dev` (P7a)

```
python -m seer_engine backtest_dev [--dry-run] [-v] [--store DIR] [--out DIR] [--plans DIR] [--run-date YYYY-MM-DD] [--only ID [ID ...]]
```

This runs every candidate in `backtest/registry.py` on the **development window only** (each
candidate's own start → 2015-10-16) and writes the P7a report set and the P7b pre-registration. It
reads only the research store. **No Neon, no network.**

- **Defaults are the committed run:** `--store engine/.research`, `--out docs/backtests` and
  `--plans docs/plans`. `--run-date` defaults to today, and it appears in file names only.
- **No `--end` exists.** Every entry point rejects a session after 2015-10-16 (`DevWindowError`),
  and the store holds no later row (D9).
- **Pre-registration guard:** the command exits 2 while `backtest/registry.py` has uncommitted
  changes (or is untracked), so every committed report comes from a committed registry (D6).
  `--only ID ...` skips the guard for smoke runs: it runs those candidates in registry order,
  renders the files in memory, logs an estimate of the full run's time, and **writes nothing**.
- **`--dry-run`** changes nothing: the command never touches the database, and a full run still
  writes its report files.
- **Steps:**
  1. Load and verify the store.
  2. Run every candidate, sequentially, in registry order.
  3. Compute D8 and the deflated Sharpe.
  4. Render all five files, then write them.
- **Output:** `<out>/<run date>-p7a-dev-exploration.md`, `-rows.csv`, `-curves.csv` and
  `-frontier.svg`, plus `<plans>/<run date>-p7b-preregistration.md`. A re-run with the same
  `--run-date` overwrites them byte-identically.
- **Logs:** the store fingerprint, one line per candidate (its result, failed D8 conditions and
  wall time), and the finalist ids or "none eligible". Wall times appear in logs only, never in a
  file.
- **Exit codes:**
  - 0 whether or not any candidate is eligible, because "none eligible" is a result.
  - 1 on an error.
  - 2 on a precondition: a dirty registry, an unknown `--only` id, a missing or invalid store, or
    `research.DEV_END` differing from `backtest.dev.DEV_END`.
- **One run per registry state.** Appending a candidate (D6) means a new commit before its run, and
  every try is reported.

### `paper` (P4)

```
usage: seer_engine paper [-h] [--dry-run] [-v] [--now ISO8601]
```

The nightly paper step for the frozen roster (`docs/runbooks/paper-trading.md`).

- **Precondition**: the real `runs` row for `run_dates(now).session_date` has `status = success`. Otherwise nothing is written and it exits 1 (design §8: a failed bars run means no paper step).
- **First night**: writes each roster row's frozen spec (`params`) and `paper_start = session_date`, `paper_state` (initial cash 20,000,000 IDR at the latest FX on or before `data_date`), day-0 snapshots at `data_date`, and the first decisions.
- **Every night**: steps every session after `paper_state.last_session` through `data_date` for every strategy, then decides `session_date`. See Usage, "Paper: one night".
- **Strategy C**: C's strategy object is given the verdicts stored in `news_vetoes` for the sessions being decided (`store.allowed_between`); only `allow` is bought, and a missing verdict counts as `failed`. `paper` makes no network call and never fails because of C's verdicts.
- **Idempotent** per (strategy, session): a re-run for a session already done writes nothing.
- **One transaction** for the whole night plus `runs.paper_status`. A failure rolls back everything and records `paper_status = failed`.
- **Frozen spec**: a started strategy whose stored digest differs from `paper/roster.py` fails the night as `store.SpecMismatch` (rolled back, `paper_status = failed`, exit 1). A `paper_start` with no `paper_state` is refused the same way until the clock is reset.
- **Exit codes**: 0 = stepped and decided, or already done (no-op); 1 = no successful bars run for the session (nothing written), or the night failed (rolled back, `paper_status = failed`, `paper_error` set); 2 = missing setting (`DATABASE_URL_UNPOOLED`).

### `paper_check` (P4)

```
usage: seer_engine paper_check [-h] [--dry-run] [-v] [--require-sessions N]
```

The read-only replay check (D7). See Usage, "Paper: replay check". C is replayed from its stored verdicts, read in the same read-only transaction; the LLM is never asked again. "Not started" (no `paper_start`) is a pass. A strategy touched by an applied split is reported `split-affected`, not failed. `--require-sessions N` is the v0.1.0 release check. Exit codes: 0 = every started strategy `ok` or `split-affected` (or none started); 1 = a mismatch, or `--require-sessions N` unmet (`not-started` counts as 0); 2 = missing setting.

### `explain` (P4)

```
usage: seer_engine explain [-h] [--dry-run] [-v]
```

Optional LLM explanations (D9) for new paper entries without one: `orders.explanation` for A's new pending orders, `book_targets.explanation` for new entries of the latest decision. Missing or empty `LLM_*` settings, or any LLM error, leave the text NULL and exit 0. Paper correctness never depends on it. Exit 1 only on a database error; 2 when `LLM_*` is set but `DATABASE_URL_UNPOOLED` is missing.

### `veto` (P6, Strategy C)

```
usage: seer_engine veto [-h] [--dry-run] [-v] [--now ISO8601]
```

Strategy C's nightly news check (handover D6; `docs/runbooks/paper-trading.md`, "Strategy C: the news check"). The nightly job runs it after `nightly` and before `paper`, as a `continue-on-error` step with a 10-minute limit. It runs outside `paper`'s transaction, so `paper` stays one network-free transaction.

- **Clock**: `started_at = now` (tz-aware UTC; `--now` for tests) is both the news cutoff and every row's `decided_at`. `rd = dates.run_dates(now)`; the session checked is `rd.session_date`.
- **Precondition**: the real `runs` row for that session has `status = success`. Otherwise exit 1, nothing written, no network call.
- **Nothing to do**: C already has rows for the session (`store.has_vetoes`): "already checked", exit 0, no Finnhub or LLM call. `paper` has already decided the session: "too late", exit 0, nothing written.
- **Candidates**: `strategies.c.candidates` on `store.load_market_window(conn, store.market_window_since(rd.data_date))` at `rd.data_date` (A's ranked picks, the first 10), read and rolled back before any network call. None: exit 0, nothing written.
- **Per candidate**, in rank order: `finnhub.Client.company_news(symbol, *news_dates(started_at, 3))` → `select_headlines(..., cutoff=started_at, cap=20)`; `finnhub.Client.earnings(symbol, *earnings_window(session, 5))`; `llm.Client(cfg, timeout=30.0, retries=1).complete(SYSTEM_PROMPT, user_prompt(...), temperature=float(params.temperature), thinking=params.thinking, max_tokens=params.max_tokens)` (0.0, "disabled", 1024, all from C's frozen `CParams`) → `parse_verdict`.
- **A failure is a verdict, never an exception**: `failed`, with a plain reason redacted and cut to 300 characters, when `FINNHUB_API_KEY` is unset, any `LLM_*` is unset, `LLM_MODEL` is not C's frozen model ("LLM_MODEL <x> is not C's frozen model glm-5.3"), Finnhub or the LLM errors, the reply is unparsable, or `MAX_CONSECUTIVE_FAILURES = 3` network failures in a row stopped the rest ("skipped after 3 consecutive failures").
- **One write**: one transaction re-checks `has_vetoes` (another run may have won) and writes every row with `store.write_vetoes`. `--dry-run` makes the real calls, then rolls back. No secret reaches a row or a log line.
- **Exit codes**: 0 = rows written (whatever the verdicts, all `failed` included), nothing to do, or no candidates; 1 = no successful bars run for the session, or a database error; 2 = missing setting (`DATABASE_URL_UNPOOLED`).

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
- P4: `start_paper(conn, run_id)`, `finish_paper(conn, run_id)`, `fail_paper(conn, run_id, error)` (error redacted, cut to 2000 characters); each raises `LookupError` for an unknown or demo run. `paper` sets `running` in a short transaction of its own, then `success` inside the night's transaction; a failure rolls the night back and sets `failed` with a redacted `paper_error` in its own transaction.

### universe (read side only; phase 2 writes the table)

Membership intervals are `[start_date, end_date)`, where `end_date` is exclusive and NULL means still a member.

- `BENCHMARK = "SPY"`
- `members_on(conn, d) -> set[str]`: symbols in either index (SP500 or NDX) on `d`.
- `symbols_for_bars(conn, d, grace_days=30) -> set[str]`: members on `d`, plus members that left within `grace_days` (so open positions keep a price), plus `BENCHMARK`.
- `all_symbols(conn, since) -> list[str]`: every symbol that was a member at any time after `since`, plus `BENCHMARK`, sorted.

### demo

Demo bars and FX rows look exactly like real ones, so the trigger is that a `runs` row with `is_demo` exists. While one exists, every row in the demo-owned tables is treated as demo data.

- `DEMO_TABLES = ("action_dismissals", "orders", "equity_snapshots", "paper_state", "book_positions", "book_targets", "book_fills", "book_trades", "news_vetoes", "bars", "fx_rates", "runs")`. `strategies` is kept on purpose. A purge also resets `strategies.paper_start` and `params` (the demo seed's paper clock; `RESET_PAPER_CLOCK`), so the first real `paper` run starts cleanly; `dividends` is never purged.
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
`tests/test_strategy_purity.py` globs every module in `strategies/`, `backtest/`,
`fundamentals/` and `paper/` — the two declared impure edges `backtest/io.py` and
`paper/store.py` excepted — and checks this in a subprocess and on the AST. P4 calls this code nightly and P6 adds strategies B and C beside `a.py`.

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

### strategies.c (P6, Strategy C)

Pure like the rest of `strategies/` (the purity tests cover it): no psycopg, requests, clock,
randomness, logging or `fromtimestamp`. The network half lives in `finnhub.py`, `llm.py` and
`commands/veto.py`.

- `PROMPT_VERSION = "c-veto-v1"`, `FROZEN_MODEL = "glm-5.3"`, `STRATEGY_C_ID = "C-news-veto"` (the object id in C's spec; the roster id is `C`). `Verdict = Literal["allow", "veto", "failed"]`, `VERDICTS`.
- `Headline(id, published, source, headline, summary)`: one Finnhub news item as C reads it; `published` is tz-aware UTC.
- `CParams(a=STRATEGY_A_PARAMS, max_candidates=10, news_days=3, max_headlines=20, max_summary_chars=280, earnings_sessions=5, model=FROZEN_MODEL, prompt_version=PROMPT_VERSION, temperature="0", thinking="disabled", max_tokens=1024)`; `as_dict()` gives every key as a plain string: A's params as `a.<key>`, `a_object`, `a_object_id`, the fields above, and the full `system_prompt` and `user_template` texts, so C's digest moves if any of them changes. `STRATEGY_C_PARAMS = CParams()`.
- `SYSTEM_PROMPT`, `USER_TEMPLATE`: the frozen `c-veto-v1` texts (the plan's K1, verbatim). The system prompt lists what is a veto (earnings inside the holding window or in the last 3 days; guidance cut, warning or large miss; accounting problems or fraud; a lawsuit, regulatory action, investigation or recall; M&A, spin-off or tender news; a halt, delisting, bankruptcy or going-concern doubt; a major analyst or credit downgrade; the CEO or CFO leaving) and asks for one JSON object `{"verdict": "allow" | "veto", "reason": "<one sentence>"}`.
- `candidates(history, members, data_date, params)` / `candidates_prepared(prepared, members, data_date, params)`: `STRATEGY_A.picks(...)` / `picks_prepared(...)` with `params.a`, cut to `params.max_candidates`. The one place C's candidates are computed (`veto` and `NewsVeto` both call it).
- `NewsVeto(allowed: Mapping[date, frozenset[str]], id=STRATEGY_C_ID, lookback=STRATEGY_A.lookback)` implements `Strategy`: `picks` keeps the candidates whose symbol is in `allowed[next_session(data_date)]`, in rank order; `prepare` is A's; `picks_prepared` is the same filter on `candidates_prepared`. `with_allowed(allowed)` returns a copy carrying stored verdicts. `STRATEGY_C = NewsVeto(allowed={})` (with no verdicts it never buys).
- `news_dates(started_at, days) -> (from, to)`: ET calendar dates for Finnhub; `to` is `started_at` in New York.
- `earnings_window(session, n) -> (session, the n-th session counting session as 1)`.
- `select_headlines(items, cutoff, cap)`: items published strictly before `cutoff`, newest first (ties: higher id first), at most `cap`.
- `user_prompt(symbol, session, window_end, earnings, cutoff, headlines, params) -> str`: `USER_TEMPLATE` filled; summaries cut to `max_summary_chars` at a word boundary; `No headlines.` when there are none.
- `parse_verdict(text) -> (verdict, reason)`: accepts surrounding whitespace and a fenced JSON block, takes the first `{...}` object; the verdict must be exactly `allow` or `veto` (case-insensitive) and the reason a non-empty string (whitespace collapsed, at most 300 characters). Anything else is `("failed", "unparsable reply: <first 120 chars>")`.
- `allowed_map(rows) -> {session: frozenset of allowed symbols}` from `(session, symbol, verdict)` rows.

### backtest (P3)

Every module except `io.py` is pure (same purity test as `strategies`). Nothing here writes to
the database.

- **`backtest.market`**: `Membership(intervals)` with `members_on(d) -> frozenset[str]` (both
  indices unioned, `[start, end)`), evaluated in memory instead of one query per date.
  `Market(history, membership, fx, fundamentals=EMPTY_FUNDAMENTALS)`: `bar(symbol, d) -> Bar | None`
  builds a 4-dp `Decimal` `Bar` on demand (only for symbols with a live order, and SPY),
  `bars_on(d, symbols)`, `last_bar_date(symbol)`, `usd_idr_on(d)` (latest FX row dated `<= d`,
  `ValueError` when none), `spy()`.
  **`fundamentals`** (edgar-fundamentals) is the point-in-time SEC fact panel
  (`fundamentals.FundamentalPanel`), read through `panel.as_of(symbol, t)`. It defaults to
  `EMPTY_FUNDAMENTALS`, which **is** `fundamentals.EMPTY_PANEL` — one shared instance, so
  `market.fundamentals is EMPTY_PANEL` is a usable identity test — so every existing
  `Market(...)` call site keeps working unchanged. `Market` is frozen, so
  `with_fundamentals(panel) -> Market` is the supported way to attach a panel to a market built
  without one (the research store, a paper replay, a test fixture) without any caller knowing the
  field order. The panel is deliberately **independent of `history`**: a symbol may have facts and
  no bars (a delisted ever-member) or bars and no facts (every ETF), and nothing cross-checks the
  two. `__post_init__` type-checks it like the other fields.
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
- **`backtest.io`, the fundamentals load** (edgar-fundamentals; still the only impure module here):
  `load_market` now also fills `market.fundamentals` via
  `load_panel(conn, *, cache_dir=CACHE_DIR, refresh=False) -> Panel`, inside the same
  `REPEATABLE READ, READ ONLY` transaction it already owns and rolls back.
  - The rows come from `fundamental_facts` JOINed to `ticker_cik`, because the facts are
    **CIK-keyed** and the panel is **symbol-keyed**.
  - It is cached by table fingerprint exactly the way `bars` is:
    `facts_fingerprint(conn) -> (count(*), max(filed))` **over the join** is the cache key,
    `facts_cache_path` names `fundamentals-<max filed>-<rows>.pkl` in `.cache/`, and
    `read_facts_frame` streams one COPY on a miss (or with `refresh`). A broken pickle is a
    warning and a re-download, never fatal.
  - **It degrades instead of failing.** `facts_fingerprint` tests both tables with `to_regclass`
    and returns `(0, None)` when **either** is missing, so `load_panel` returns
    `EMPTY_FUNDAMENTALS` with no error — the state of every database that has not run
    `005_fundamentals.sql`, and of one that has but has not yet run `fundamentals`. `load_market`
    against such a database is unchanged (verified against the live Neon DB, and the backtest and
    `load_market` output are byte-identical to `origin/main`).
  - `read_facts(*, conninfo=None) -> tuple[Fact, ...]` opens its own connection
    (`DATABASE_URL_UNPOOLED`), runs the same fingerprint + COPY + `facts_from_frame` trio
    `load_panel` uses — so the facts equal the panel's by construction — and always rolls back.
    It lives **here, not in `commands/research_store.py`**: `io.py` is the one module in
    `seer_engine.backtest` that touches the database and the one `test_strategy_purity.py` skips
    by name, and `test_research_store.py::test_no_neon_and_no_database_url_needed` AST-scans both
    `research.py` and the `research_store` command and fails either one that names
    `seer_engine.db` or `psycopg`. The "Never Neon" invariant is untouched: `research.py` still
    imports nothing from `seer_engine.db`, and `build_store` still takes a plain sequence of facts.
  - `tests/test_market_fundamentals.py` covers the field, the `EMPTY_PANEL` identity, the
    `with_fundamentals` / `replace` carry-through, the `to_regclass` degradation path and the fact
    cache.

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

### sim: trade rules and the book engine (P7a)

Design §5 is now a value. `sim.model`, `sim.lifecycle`, `sim.sizing` and `sim.split_adjust` are not
edited. `DESIGN_V0` runs go through the unchanged `size_picks` + `step` path, through
`backtest.book_runner.run_rules` → `runner.run_backtest`. So the A, A2 and B reports re-render
byte-identically: re-running `backtest`, `backtest_wf` and `backtest_b` on the unchanged Neon data (1,817,429 bar rows through 2026-10-02): all 11 `docs/backtests/2026-10-02-*` files `cmp`-equal (phase 13, 2026-10-04). Every other rule set runs on a second pure engine, `sim.book`.
Both new modules are pure and `Decimal`-only, and `test_sim_purity.py` covers them. Import everything
from `seer_engine.sim`.

**`sim.rules`:**
- Constants:
  - `OPEN_LIMIT_BAND = Decimal("0.02")`;
  - `RESIZE_BAND = Decimal("0.01")`;
  - `SHARE_QUANTUM = Decimal("0.0001")`;
  - `DEFAULT_ETFS = {"SPY", "QQQ"}`, the owner-input default;
  - `LEVERAGED_ETFS = {"SSO", "QLD", "UPRO", "TQQQ"}`.
- `TradeRules` is a frozen value. `__post_init__` validates types (`TypeError`), ints ≥ 1,
  `cost_rate` in [0, 0.05) and a kebab-case `id` (`ValueError`).

| Field | Default | Meaning |
|---|---|---|
| `id` | — | kebab-case, unique per preset |
| `engine` | — | `"bracket_v0"` only for `DESIGN_V0` (`ValueError` otherwise, both ways); `"book"` for everything else |
| `cadence` | `"daily"` | the RANK cadence — sessions on which the allocator may choose a new basket: every session (`daily`); the first NYSE session of each ISO week (`weekly`); or the first of each calendar month (`monthly`) |
| `resize_cadence` | `None` | a faster RESIZE cadence split off `cadence` (`None` = one cadence, every rule set before the split). Must be strictly faster than `cadence` and needs `resize=True`, else `ValueError`. On a resize-only session the last rank's basket is kept and rescaled to today's exposure; nothing is ranked, entered or signal-exited |
| `entry` | `"limit"` | `limit`: the target's limit price (a new target with no limit price is bought like `open_limit`); `open_limit`: a buy limit at last close × 1.02 (a limit order, so executable by default); `open`: market-on-open (owner input) |
| `max_positions` | `None` | a cap on non-idle positions (4 only for §5 parity) |
| `time_stop` | `None` | sell at the next open once `days_held >= time_stop` |
| `resize` | `False` | on decision sessions, trade held targets back to weight when the change is ≥ `RESIZE_BAND` × equity |
| `fractional` | `False` | shares quantized down to `SHARE_QUANTUM` (owner input) |
| `dividends` | `True` | credit cash dividends on the ex-date (D11) |
| `idle_symbol` | `None` | the residual weight (1 − Σ targets) held in this instrument on decision sessions; 0% while it has no bar (BIL before 2007) |
| `cost_rate` | `0.001` | per side; any other value is an owner input |

- Presets (`PRESETS` holds every row below except `V0_BOOK`; ids are unique):

| Preset | id | Engine | Cadence | Entry | Other |
|---|---|---|---|---|---|
| `DESIGN_V0` | `design-v0` | bracket_v0 | daily | limit | 4 positions, time stop 5, whole shares, no dividends: design §5 exactly (= `SLOTS`, `TIME_STOP_DAYS`, `COST_RATE`, tested) |
| `V0_BOOK` | `v0-book` | book | daily | limit | `DESIGN_V0` replayed by the book engine; parity tests only, never in the registry |
| `MONTHLY_HOLD` | `monthly-hold` | book | monthly | open_limit | resize |
| `MONTHLY_HOLD_TBILL` | `monthly-hold-tbill` | book | monthly | open_limit | resize, idle in BIL |
| `WEEKLY_HOLD` | `weekly-hold` | book | weekly | open_limit | resize |
| `DAILY_SWITCH` | `daily-switch` | book | daily | open_limit | no resize |
| `DAILY_SWITCH_TBILL` | `daily-switch-tbill` | book | daily | open_limit | idle in BIL |
| `SWING_T10` | `swing-t10` | book | daily | limit | time stop 10 |
| `SWING_T20` | `swing-t20` | book | daily | limit | time stop 20 |
| `SWING_T20_OPEN` | `swing-t20-open` | book | daily | open_limit | time stop 20 |
| `MONTHLY_RANK_WEEKLY_RESIZE` | `monthly-rank-weekly-resize` | book | monthly rank, weekly resize | open_limit | resize |
| `MONTHLY_RANK_WEEKLY_RESIZE_TBILL` | `monthly-rank-weekly-resize-tbill` | book | monthly rank, weekly resize | open_limit | resize, idle in BIL |

- `is_rank_session(rules, session) -> bool`, `is_resize_session(rules, session) -> bool` (a resize-ONLY
  session: False without a `resize_cadence`, and False when the session also ranks — ranking supersedes),
  and `is_decision_session(rules, session) -> bool` (either). Without a `resize_cadence`,
  `is_decision_session` is exactly `is_rank_session`, so every call site that predates the split stays
  correct. All three raise `ValueError` for a non-session.
- `LEVERS_SINCE_PINS` / `is_pinned_default(name, value)`: a lever added AFTER the P7a registry, the lab
  trials and the paper roster were pinned, mapped to the value meaning "as before this lever existed"
  (`{"resize_cadence": None}`). Every canonical form pinned before the lever leaves such a field out
  while it holds that value — `backtest.registry._canon` (so no pinned candidate digest moves and no
  closed lab trial re-digests through `lab.method.config_digest`) and `paper.roster.rules_dict` (so no
  live paper spec digest moves). A rule set that uses the lever canonicalizes differently.
- `rule_owner_inputs(rules) -> tuple[str, ...]`. The result is sorted and drawn from
  `market-on-open`, `fractional`, `etf:<idle symbol>` (outside `DEFAULT_ETFS`) and `fee`.
- `describe_rules(rules) -> tuple[str, ...]`: one fixed plain-English line per lever. The reports
  and the pre-registration's §5 text use it.

**`sim.book`** (`WEIGHT_QUANTUM = Decimal("0.000001")`):
- `Target(symbol, weight, last, limit=None, stop=None, take=None)`: one instrument wanted after the
  next open, in rank order.
  - `0 < weight ≤ 1`, a multiple of `WEIGHT_QUANTUM`.
  - The prices are 4 dp, with `stop < limit (or last) < take`.
  - A float anywhere is a `TypeError`.
- `to_weight(x)` quantizes down to `WEIGHT_QUANTUM`. `equal_weight(n)`.
- `Position(symbol, shares, mark, entry_date, entry_price, days_held, cost_usd, income_usd, stop, take, exit_pending=False)`:
  one holding episode. `exit_pending` marks a signal exit decided while the symbol had no bar.
- `Book(cash, equity, positions=(), last_session=None)`, with `held()` and `position(symbol)`.
  `new_book(cash_usd)`.
- `Fill(session_date, symbol, side, shares, price, cash_usd, cost_usd, reason)`. The reason is one
  of `entry`, `add`, `trim`, `signal`, `time`, `gap`, `tp`, `sl` or `forced`.
- `Trade(symbol, entry_date, exit_date, entry_price, exit_price, days_held, cost_usd, income_usd, pnl_usd, exit_reason, idle)`:
  one closed episode (shares 0 → > 0 → 0).
  - Dividends are inside `income_usd`.
  - `pnl_usd = income_usd − cost_usd` reconciles with cash exactly.
  - Trims and adds do not create trades.
  - Idle-instrument episodes (`idle=True`) are excluded from trade statistics.
- `BookSnapshot(date, cash_usd, equity_usd, invested_usd)`: `invested_usd` counts non-idle
  positions only, so exposure = invested ÷ equity.
- `step_book(book, session, bars, targets, rules, dividends={}, idle_symbol_ok=False) -> BookStep(book, fills, trades, dividends, rejected, snapshot)`:
  - `targets=None`: not a decision session.
  - `targets=()`: a decision session wanting nothing, so every non-idle position is signal-exited.
  - Σ weight ≤ 1 is checked only when `rules.max_positions is None` (D-A).
  - Order:
    1. Dividends on the ex-date for positions held before S.
    2. Open exits, in symbol order: time stop, then a gap through the stop or the take, then a
       signal exit (a dropped target or `exit_pending`). A position sold this way does not re-enter
       on S.
    3. Trims (`resize`, or the idle symbol) beyond `RESIZE_BAND`.
    4. Buys in rank order, idle last.
       - `max_positions` → `no_slot`.
       - Sizing price: the target's limit, or last × 1.02 (`open_limit`, `open`, and a
         limit-less new target under `limit`). A held target without a limit is never added to.
       - Budget: `min(equity × weight, cash + planned night sells − committed)`.
       - Whole or fractional shares → `too_small`.
       - Fill: strict `low < limit` at `min(open, limit)`, or at the open for `open`. Otherwise
         `unfilled` or `no_bar`.
       - A fill-time cash guard → `cash`.
    5. Intraday stop then take, for positions held before S.
    6. `days_held + 1` and marks.
    7. The snapshot.
  - Buy cash is `q(p × n × (1 + c))`. Sell proceeds are `q(p × n × (1 − c))`.
- `close_book_unpriced(book, symbols, rules) -> (book, fills, trades)` sells at the mark with reason
  `forced`, mirroring `sim.close_unpriced`.
- **Parity:** `run_book(PICKS(A), V0_BOOK)` reproduces `run_backtest(STRATEGY_A)` exactly: equal
  snapshots and equal closed trades on seeded synthetic markets (`tests/test_book_runner.py`).

### strategies: allocators and the P7a families

The new modules are pure and flat in `strategies/`, so the purity glob covers them.
`strategies/__init__.py` is unchanged: import from the modules.

- **`strategies.allocator`**:
  - The `Allocator` protocol: `id`, `lookback(params)`, `symbols(params)` (fixed symbols it reads),
    `holds(params)` (fixed symbols it may hold), `uses_members(params)`,
    `targets(history, members, data_date, held, params)`, `prepare(history)` and
    `targets_prepared(prepared, members, data_date, held, params)`.
  - **Contract (P4 identity):**
    - `targets_prepared(prepare(H), …) == targets({s: h.upto(d)}, …)` for every date, holding and
      params;
    - it reads only bars dated ≤ `data_date`;
    - targets are in rank order, with unique symbols and Σ weight ≤ 1 (except `PICKS`, whose §5
      picks may weigh more: the engine's `max_positions` cap picks the entrants, and `step_book`
      checks Σ ≤ 1 only when there is no cap);
    - a symbol with no bar on `data_date` is never a new target;
    - `held` lets a family keep a position, and the engine signal-exits any held symbol the family
      drops. The book runner passes `held` without the idle symbol (D-J).

    `tests/allocatorkit.py` checks this contract for every family.
  - `target_from_close(symbol, close, weight, *, limit=None, stop=None, take=None)` and
    `month_end_closes(h, data_date)`.
  - Adapters and overlays:
    - `PICKS` (`PicksParams(strategy, params, slots=4)`): any bracket `Strategy` as an allocator;
      used for the V0 parity.
    - `BLEND` (`BlendParams(parts)`, each `BlendPart(allocator, params, share)`): F9, core plus
      satellite.
    - `VOLTARGET` (`VolTargetParams(inner, inner_params, signal="SPY", target_vol=0.12, n=20)`):
      L11, which scales the inner weights by `min(1, target ÷ realized vol)`.
  - `prepare(history)` takes no params, so one prepared value per allocator id serves every
    candidate (`LazyPrepared` for `PICKS`, `BLEND` and `VOLTARGET`; D-D).
  - **`MarketAware` and `prepare_for`** (edgar-fundamentals): an allocator that needs more than
    bars — the SEC fact panel, FX, membership — implements `prepare_market(market) -> Any` and so
    satisfies the second `runtime_checkable` protocol `MarketAware`, *in addition to* `Allocator`.
    `prepare_for(obj, market)` is the dispatch: `obj.prepare_market(market)` when the attribute is
    present, else `obj.prepare(market.history)` — exactly what every call site did before — so an
    allocator that does not define it sees no change at all. `obj` may be an `Allocator` or a
    bracket `Strategy`; both have `prepare`. A present-but-not-callable `prepare_market` is a
    `TypeError`, because `runtime_checkable` cannot tell a method from a data attribute and a
    silent fallback would hide a typo as a quietly bar-only allocator.
    - **`prepare_market` is deliberately NOT a member of `Allocator`.** `Allocator` is
      `runtime_checkable` and production sites test `isinstance(x, Allocator)`; adding a member —
      even one with a default body — would make every existing structural implementer fail the
      check. `Allocator`'s member set is therefore unchanged by this phase.
    - An implementer still needs `prepare`: it is an `Allocator` member, and `allocatorkit`'s P4
      identity check drives the plain path.
    - The single real dispatch site is `backtest.dev`'s per-allocator-id prepared cache; nothing in
      the first registry implements `MarketAware` yet.
  - `strategies/__init__.py` is still unchanged: import `MarketAware` and `prepare_for` from
    `strategies.allocator`.
- **`strategies.indicators.return_window(close, n, skip=0)`** (additive):
  `c[:, -1-skip] / c[:, -1-n] − 1`. It follows the same bit-identity rule as the existing windows.
- **Families.** Each family is one singleton plus a frozen params dataclass with
  `as_dict() -> dict[str, str]` in a fixed key order. `Candidate.family` carries the catalogue
  label.

| Module | Singleton (allocator id) | Params | Catalogue | Idea |
|---|---|---|---|---|
| `f_index` | `TIMING` (`F1`) | `TimingParams(hold, signal, rule, n=200)`; rule `sma` / `month_sma` / `abs_mom` / `always` | F1, F10 | hold an index ETF (or a 2× ETF, owner input) only while its signal is above trend |
| `f_index` | `CALENDAR` (`F11`) | `CalendarParams(hold, days_before=1, days_after=3, trend=None)` | F11 | turn of the month, optionally only above trend |
| `f_rotation` | `ROTATION` (`ROT`) | `RotationParams(universe, lookback, top, absolute=True, fallback=None, trend=None)` | F2, F3 | dual momentum and sector rotation, with an absolute filter and an optional bond fallback |
| `f_factor` | `FACTOR` (`FAC`) | `FactorParams(rank, top=10, mom_n=252, mom_skip=21, vol_n=60, pool=50, sizing="equal", min_dollar_volume=2e7, min_price=5, trend=("SPY", 200))` | F4, F5, F6 | 12-1 momentum, low volatility, or momentum among calmer names, on point-in-time index members (SPY excluded) |
| `f_swing` | `SWING` (`F7`) | `SwingParams(slots=4, rsi_n=2, rsi_max=10, sma_n=200, entry="dip", limit_atr=0.5, stop_atr=2.5, take_atr=None, exit_sma=5, exit_rsi=None, min_dollar_volume=2e7, market_trend=None)` | F7 | A's oversold-in-an-uptrend idea with a longer horizon, signal exits and no TP (D12: a new candidate, never A re-run) |
| `allocator` | `BLEND` | `BlendParams` | F9 | a timed SPY core plus a momentum or swing satellite |

F8 (a learned ranker at a longer horizon) and F12 (earnings drift) are not in the first registry
(index Decisions). Either may be appended under D6.

### research store (P7a)

`seer_engine.research` is an **impure** edge: yfinance, Frankfurter and files. It is never Neon (D5).
The store is local and gitignored, in `engine/.research/`.

- Constants:
  - `DEV_END = date(2015, 10, 16)`, `MEMBERSHIP_START` and `FX_START`, each equal to
    `backtest.dev`'s (tested);
  - `STORE_START = date(1993, 1, 29)`;
  - `STORE_DIR`;
  - `RESEARCH_ETFS`: 21 ETFs (BIL, DIA, EFA, GLD, IEF, IWM, QLD, QQQ, SHY, SPY, SSO, TLT and the 9
    sector SPDRs);
  - `SECTOR_ETFS`, equal to `backtest.registry.SECTOR_ETFS` (tested).
  - `DATA_FILES` (the four required files) and, since edgar-fundamentals,
    `OPTIONAL_DATA_FILES = (FUNDAMENTALS_FILE,)`. `fundamentals.csv` is in the **optional** tuple,
    never a fifth required file: `_read_manifest` requires `DATA_FILES` and *permits* the optional
    ones, and the fingerprint is the sha256 of the sorted `name:sha` lines of the files that were
    actually written. So a store built before this phase keeps loading with a **bit-identical
    fingerprint**, and `--verify` still passes on it.
- Files. All are LF text, sorted and deterministic, with prices at 4 dp like `bars`:

| File | Columns | Notes |
|---|---|---|
| `bars.csv` | `symbol,date,open,high,low,close,volume` | split-adjusted, not dividend-adjusted (`auto_adjust=False`), dates ≤ `DEV_END` |
| `dividends.csv` | `symbol,ex_date,amount` | cash dividends from `actions=True`, ≤ 6 dp |
| `fx.csv` | `date,usd_idr` | Frankfurter from 1999-01-04 |
| `unserved.csv` | `symbol,reason` | members overlapping [1996-01-02, `DEV_END`] that yfinance could not serve |
| `fundamentals.csv` | `FACT_COLUMNS`: `symbol,taxonomy,tag,unit,period_start,period_end,val,accn,form,fy,fp,filed` | **optional** (edgar-fundamentals), written only with `--with-fundamentals`; sorted, in `io.FACTS_COPY_SQL`'s encoding |
| `manifest.json` | — | counts, a sha256 per file, and `fingerprint` (the sha256 of the sorted `name:sha` lines); no timestamps |

- `build_store(store_dir, *, downloader=None, fetch_fx=None, sleep=time.sleep, batch_size=40, data_dir=None, facts=None)`:
  - the symbols are `RESEARCH_ETFS` plus every `compute_universe()` member overlapping
    [1996-01-02, `DEV_END`];
  - downloads are throttled and batched, with rate-limit backoff like `backfill`;
  - rows after `DEV_END` are dropped defensively;
  - it writes every file to a temp dir and then renames it, so the build is all-or-nothing
    (`ResearchStoreError` on failure);
  - `facts` (edgar-fundamentals) is the SEC point-in-time panel as a plain sequence of
    `fundamentals.Fact`, rendered by `fundamentals_lines(facts)` into `fundamentals.csv` and added
    to the manifest. `None` — the default, and every caller that predates fundamentals — writes no
    `fundamentals.csv` at all. `research.py` never opens a connection for them: the command passes
    them in (see `--with-fundamentals` below), so the "Never Neon" invariant (D5) is unchanged.
  - it returns the manifest.
- `load_store(store_dir, *, data_dir=None) -> ResearchData(market, dividends, spy_dividends, fingerprint, manifest, unserved)`:
  - it verifies every sha256 and rejects any row dated after `DEV_END` (`ValueError`, also for a
    missing store). That is the data-level guard of D9.
  - Its `Market` takes membership from `membership.compute_universe()` through
    `io.merge_intervals`, offline. Its `fundamentals` is `_read_fundamentals(fundamentals.csv)`
    when the manifest lists that file and `EMPTY_FUNDAMENTALS` otherwise (edgar-fundamentals), so
    a pre-fundamentals store loads to a market with an empty panel rather than an error.
- `run_checks(data, vendored)`: the three data checks `research_store --verify` prints.
- the fundamentals-only refresh (fundamental-panel-coverage): reuses an existing store's four
  required files byte for byte, writes a new `fundamentals.csv`, re-seals and `_swap_in`s. The
  manifest's copied counts (`bar_rows`, `dividend_rows`, `fx_rows`, `symbols_requested`,
  `symbols_served`) are carried over, never re-derived from a download.

**The committed store** (built in phase 4, verified in phase 13): fingerprint `5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a`.
- 2,490,793 bar rows; 539 of 1,061 symbols served, and 522 members unserved.
- 28,206 dividend rows and 4,300 FX rows.

**The current train/eval store** (fundamental-panel-coverage, 2026-10-05): fingerprint
`399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8`, superseding
`e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3`.
Same bars — the refresh copied them byte for byte — with a panel rebuilt from facts filed since
2009-01-01 against the re-vendored `ticker_cik.csv`: 1,213,303 facts over 869 symbols. Dev-window
coverage **0.3151** (`research_store --coverage`, 75 of 238 monthly samples); it was **0.0378**
before. That is better data and not a valid test: the dev window opens in 1996 and XBRL starts
around 2009, so a fundamentals method still cannot reach the lab's `>= 100 trades` gate on it.
The store syncs between machines with `/sync-research-store` (`push`/`pull`, content-addressed on
this fingerprint, Vercel Blob); push it with `--keep 0`, because a plain `push` prunes to the
newest three versions.

Both coverage figures above are **upper bounds** — the measure reads no bars, so membership,
`min_price` and `min_dollar_volume` are not applied.

yfinance has no delisted tickers, so the dev window's survivorship gap is far larger than the 115
members since 2015, and single-stock dev results are optimistic (D4). The report counts the gap year
by year (41.4% of member-sessions over 1996–2015 have no bar). ETF-only candidates have no such bias.

### backtest book runner (P7a)

`backtest/book_runner.py` is pure (covered by `tests/test_strategy_purity.py`); tests in
`tests/test_book_runner.py`.

- **`run_book(market, allocator, params, rules, start, end, *, prepared=None, dividends=..., initial_idr=INITIAL_IDR, usd_idr=None) -> BookResult`**:
  drives an `Allocator` under book `TradeRules` (`rules.engine == "book"`) through `sim.book.step_book`
  over every NYSE session in `[start, end]`, in `run_backtest`'s shape. On a rank session
  (`sim.rules.is_rank_session`) the allocator maps history through `data_date = prev_session(S)`
  to target weights (via `targets_prepared` when `prepared` is given, else `targets`); other sessions
  pass `None`. On a resize-only session (`is_resize_session`, only with `rules.resize_cadence`) the
  allocator is called the same way but its answer is used for its TOTAL weight alone: `_rescaled`
  keeps the last rank session's basket, restricted to what is still held, with every weight × `k =
  Σ(fresh) / Σ(last rank)` and `last` refreshed to today's close (falling back to the book's mark),
  dropping `limit`/`stop`/`take`. So Σ matches what the allocator wants today while the names are
  frozen, and the freed weight goes to `idle_symbol` or cash. `k` is exact for an overlay that scales
  a fixed-width basket (vol targeting); for an allocator whose basket WIDTH varies it conflates
  "fewer names" with "less exposure". A resize session before the window's first rank has no basket
  and is not a decision session at all (the allocator is not called). With `rules.idle_symbol` the residual `1 - sum(weights)` goes to that instrument.
  Held-symbol dividends with ex-date S are passed only when `rules.dividends`. Positions with no bar
  on S or later are force-closed (`close_book_unpriced`). `usd_idr` defaults to
  `market.usd_idr_on(start)`. `DESIGN_V0` rules are a ValueError here.
  `BookResult` carries snapshots, fills, trades, `open_at_end`, `dividends_usd`, `costs_usd` and
  `rejections` (by reason).
- **`run_rules(market, strategy_or_allocator, params, rules, start, end, *, prepared=None, dividends=..., usd_idr=None) -> RunResult | BookResult`**:
  the single P7a dispatch. `DESIGN_V0` (`"bracket_v0"`) with a `Strategy` goes to the unchanged
  `run_backtest` (so A, A2 and B stay byte-identical by construction; dividends ignored; `usd_idr`
  must be None or equal `market.usd_idr_on(start)`); book rules with an `Allocator` go to
  `run_book`; any other pairing is a TypeError.
- **`run_stats(RunResult | BookResult) -> RunStats`**: what the dev report needs from either
  result: `metrics` (non-idle trades for a book run, plus `avg_days_held` and `exit_reasons`),
  `exposure`, annualized `turnover`, `costs_usd`, `gross_pnl_usd`, `cost_drag`, `dividends_usd`,
  `daily_returns`, `sharpe` (population stdev, x sqrt(252)), `year_returns` and `worst_year`.
  Floats exist only here, summed left to right as in `backtest.metrics`.

### backtest: dev runner, report and registry (P7a)

These add to P3, P3b and P6a without changing them, on top of the book runner above. Every module
here is pure, and the purity glob covers it; the one writer is `backtest.io.write_dev_report`.

- **`backtest.dev`**:
  - Constants: `DEV_END = 2015-10-16`, `MEMBERSHIP_START = 1996-01-02`, `FX_START = 1999-01-04`
    and `MAX_CANDIDATES = 60`.
  - `check_dev_session(d)` raises `DevWindowError` (a `ValueError`) after `DEV_END`. Every public
    entry point calls it before anything else.
  - `Candidate(id, family, rules, allocator, params, rationale, added, owner_inputs)`.
    `candidate_owner_inputs(c)` returns `rule_owner_inputs` plus every held ETF outside
    `DEFAULT_ETFS`, plus `leverage` for a held leveraged ETF. An empty tuple means executable under
    the conservative defaults.
  - `candidate_window(market, c) -> (start, DEV_END)`. The start is the first session where every
    instrument the candidate reads, and SPY, has its lookback. A member family also starts no
    earlier than `MEMBERSHIP_START`.
  - `run_candidate(market, dividends, spy_dividends, c, *, prepared=None)` and
    `run_registry(market, dividends, spy_dividends, registry, *, on_result=None)` run sequentially,
    in registry order, with one prepared value per allocator id — built by
    `strategies.allocator.prepare_for(allocator, market)` (edgar-fundamentals), so a `MarketAware`
    allocator gets the whole `Market` (fundamentals included) and every other one gets exactly the
    `allocator.prepare(market.history)` it got before. The candidate's market copy carries
    `fundamentals` over with `history` and `membership`, so a long window keeps the panel. Starting cash is
    `initial_cash_usd(20,000,000 IDR, usd_idr_on(max(start, FX_START)))`; a window starting before
    `FX_START` runs on a market copy whose `fx` is that single rate (D-C). FX before 1999 affects
    only that conversion, never a decision.
  - `DevRow` holds the stats and both SPY curves on the candidate's own window and cash. SPY's
    dividends come from the store.
  - `finalists(rows)` is D8:
    - **eligible** means beating SPY TR, max DD ≤ 15%, PF ≥ 1.3, ≥ 100 closed trades, and no owner
      input;
    - the eligible rows are ranked by MAR (CAGR ÷ max DD), ties by id;
    - the top 3 are kept, at most one per family.
  - `deflated_sharpe(sharpe_daily, n_trials, var_trials, t, skew, kurt)` follows Bailey & López de
    Prado (2014).
- **`backtest.dev_report`**:
  - `DevReport` and `report_stem(run_date)` (`<run date>-p7a-dev-exploration`);
  - `preregistration_name(run_date)` (`<run date>-p7b-preregistration.md`);
  - `render_markdown`, `rows_csv`, `curves_csv`, `frontier_svg` and `render_preregistration`.
  - The run date appears in file names only, so a re-run is byte-identical. Two renders are
    byte-equal.
- **`backtest.registry`**:
  - `REGISTRY` holds 54 candidates across 11 families. 11 of them carry owner inputs and cannot be
    finalists until the owner confirms.
  - `candidate_digest(c)`.
  - `tests/test_registry.py` pins every `(id, digest)`, so the tuple only grows (D6).
- **`backtest.io.write_dev_report(out_dir, plans_dir, report) -> list[Path]`** renders all five
  files (`dev_report_files`) before writing any.

**Committed result** (research store `5451195fd552`, dev window ≤ 2015-10-16, registry at
`b2ec090`): 54 candidates tried, 0 eligible under D8.

None eligible: of 54 candidates, 35 beat total-return SPY on their own windows, 0 kept max DD ≤ 15%,
40 reached PF ≥ 1.3, 33 made ≥ 100 closed trades and 43 needed no owner input; none met all five.
The best MAR was `F4-MOM12-N20-TREND` (F4): CAGR +16.2% against +7.9% for total-return SPY, max DD
22.2%, PF 2.27, 1,154 trades, MAR 0.73; it failed on max DD ≤ 15%. See
`docs/backtests/2026-10-04-p7a-dev-exploration.md` and its frontier chart. P7b does not run; the
pre-registration file records "none eligible".

### paper (P4)

`seer_engine.paper` is nightly paper trading. Every module but `store.py` is pure (no psycopg,
requests, yfinance, clock or randomness), `Decimal`-only for money, and covered by the purity tests.
Each night function steps exactly one session the way a runner's loop body does, and its tests prove
that looping it equals the runner (`run_backtest`, `run_book`, `buy_and_hold`) over hundreds of
synthetic sessions.

- **`paper.roster`**: the frozen roster (D1, D4).
  - `BENCHMARK_ID = "SPY"`, `F4_ID = "F4-MOM12-N20-TREND"`, `F1_ID = "F1-SPY-SMA200-M"`.
  - `RosterEntry` (frozen dataclass), one paper portfolio: `id, name, sub, icon, is_champion, is_benchmark, sort` (equal to the rows migrations 003 and 004 insert), `engine: Engine`, `rules: TradeRules | None`, `obj: Strategy | Allocator | None`, `object_name`, `params`, `registry_id: str | None`, `lookback: int`, `gate_note: str`, `gate_applicable: bool = True` (P6; false only for `C`).
  - `ROSTER: tuple[RosterEntry, ...]` (SPY, A, F4, F1, C), `ROSTER_IDS`, `MAX_LOOKBACK_BARS = max(e.lookback for e in ROSTER)`. `C` (P6): `C · News veto`, icon `gavel`, sort 5, engine `bracket`, rules `DESIGN_V0`, `obj = STRATEGY_C`, `params = STRATEGY_C_PARAMS`, gate note "Backtest gate: not applicable (LLM strategy, design §1 item 5)".
  - `entry(strategy_id) -> RosterEntry`: the roster entry; `KeyError` when it is not on the roster.
  - `rules_dict(rules: TradeRules) -> dict[str, str | None]`: every `TradeRules` field, in field order, as plain strings — minus a lever still at its pre-pin default (`sim.rules.is_pinned_default`), so a roster strategy that does not use a newly added lever keeps the spec digest already written to its live `strategies.params` row.
  - `spec(e) -> dict[str, Any]`: the frozen spec (C2 `params.spec`), JSON-ready, strings and nulls only.
  - `spec_text(s) -> str`: the canonical text of a spec: JSON with sorted keys, no whitespace, ASCII only.
  - `spec_digest(s) -> str`: sha256 (hex) of `spec_text(s)` in UTF-8. The five digests are pinned in `tests/test_paper_roster.py`; the four P4 digests never change.
  - `backtest_gate(e) -> dict[str, Any]`: C2 `params.backtest_gate`, `passed` false for every entry, with `e.gate_note`; for `C` also `"applicable": false` (the web shows "Not applicable" and counts it as not passed). Not part of the spec, so no digest depends on it.
  - `strategy_params(e) -> dict[str, Any]`: the whole `strategies.params` jsonb (`spec`, `digest`, `backtest_gate`), as `paper` writes it.
- **`paper.bracket`**:
  - `BracketNight(session, portfolio, events, snapshot)`: one settled session of a bracket strategy.
  - `settle_bracket(pf, session, bars, splits, last_bar_date) -> BracketNight`: settle `session` exactly like one `run_backtest` iteration (`apply_split` per applied split, `sim.step`, `close_unpriced` for symbols whose bars ended, snapshot replaced).
  - `decide_bracket(pf, strategy, params, history, members, data_date) -> SizingResult`: the pending orders for `next_session(data_date)`: `strategy.picks` on `history` cut at `data_date`, then `size_picks`.
- **`paper.book`**:
  - `BookNight(session, book, targets, splits, fills, trades, dividends, rejected, forced, snapshot)`: one settled session of a book strategy.
  - `decide_book(market, allocator, params, rules, data_date, held) -> tuple[tuple[Target, ...] | None, bool]`: the targets for `next_session(data_date)` (`None` when it is not a decision session) and whether the idle residual was appended. `backtest.book_runner._with_idle` is reused by import. Split-cadence rules (`rules.resize_cadence`) are a `ValueError`: a resize-only session needs the last rank session's basket and this function is stateless, so paper refuses loudly instead of silently re-ranking on the fast clock. Backtests and replays of split rules go through `run_book`, which carries that state, and are correct.
  - `settle_book(book, session, bars, targets, idle_added, rules, dividends, splits, last_bar_date) -> BookNight`: `sim.apply_book_split` per applied split (targets rescaled too), `sim.step_book`, `close_book_unpriced` for gone positions, snapshot replaced.
- **`paper.benchmark`**: `buy_and_hold` one session at a time. Whole shares at the first session's open; dividends with an ex-date after the start credited on the ex-date and reinvested at that close; marked at every close.
  - `SPY = "SPY"`; `BenchmarkState(start, cash, equity, position: Position | None, last_session)`.
  - `start_benchmark(cash0, start) -> BenchmarkState`: the benchmark the night before `start`: `q(cash0)` in cash, nothing held.
  - `split_benchmark(state, factor, session) -> tuple[BenchmarkState, Decimal]`: rewrite the SPY holding in post-split units (floor shares, cash in lieu returned, prices ÷ the exact factor).
  - `step_benchmark(state, session, bar, dividend, *, split=None) -> tuple[BenchmarkState, Snapshot, tuple[Fill, ...]]`: step through `session` (which must be `next_session(state.last_session)`); a `split` runs `split_benchmark` first.
- **`paper.replay`**: the pure comparison behind `paper_check`.
  - `Engine`, `Status = "ok" | "mismatch" | "split-affected" | "not-started"`; field tuples `SNAPSHOT_FIELDS`, `ORDER_FIELDS`, `POSITION_FIELDS`, `FILL_FIELDS`, `TRADE_FIELDS`, `TARGET_FIELDS`, `HOLDING_FIELDS`; `MAX_SHOWN = 10`.
  - `Holding(symbol, shares, mark)`: the benchmark's holding as `book_positions` stores it. `PaperHead(strategy_id, engine, paper_start, last_session, usd_idr)`: what the replay needs from a started strategy. `Records(...)`: one strategy's paper record, stored or expected (cash, equity, pending, snapshots, orders and marks, positions, fills, trades, targets, holdings). `Difference(where, text)`. `CheckResult(strategy_id, status, sessions, paper_start, last_session, differences, total_differences, splits)`.
  - `sessions_stepped(paper_start, last_session) -> int`; `last_close(market, symbol, on) -> Decimal`; `held_before(fills, session) -> frozenset[str]`.
  - `expected_bracket(market, strategy, params, head) -> Records` (`run_rules(DESIGN_V0)` plus the next decision); `expected_book(market, allocator, params, rules, head, dividends) -> Records` (`run_rules(rules)` plus every decision); `expected_benchmark(market, head, dividends) -> Records`.
  - `compare(engine, stored, expected) -> tuple[Difference, ...]`: every stored value that differs, snapshots first, `paper_state` last. `split_exposure(engine, paper_start, records, splits)`: the applied splits that hit a held or pending symbol. `judge(head, stored, expected, splits) -> CheckResult`; `not_started(strategy_id)`; `broken(strategy_id, where, message, *, paper_start=None, last_session=None)`.
  - `failures(results, require_sessions) -> tuple[str, ...]`; `exit_code(results, require_sessions) -> int` (1 when `failures` is non-empty); `render(results) -> tuple[str, ...]`.
- **`paper.store`** (impure; nothing commits, `paper` runs a night in one transaction):
  - `BENCHMARK_ID = "SPY"`, `MARKET_WINDOW_DAYS = 550` (the only window constant), `PRICE_QUANTUM`, `DIVIDEND_QUANTUM`. `StoreError(RuntimeError)`; `SpecMismatch(StoreError)`: a frozen strategy's stored digest differs from the code's.
  - Roster rows: `StrategyRow(id, name, engine, rules_id, is_champion, is_benchmark, sort, paper_start, params)`; `read_strategies(conn)`, `read_strategy(conn, strategy_id)`; `freeze_spec(conn, strategy_id, *, spec, digest, backtest_gate, paper_start)` (writes once); `check_digest(row, digest)` (raises `SpecMismatch`).
  - State: `PaperState(strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, pending_decision)`; `read_paper_state(conn, strategy_id)`; `init_paper_state(conn, strategy_id, *, paper_start, cash0, usd_idr) -> PaperState` (day 0: `last_session = prev_session(paper_start)` plus the day-0 snapshot); `write_paper_state(conn, strategy_id, *, cash, equity, last_session)`; `write_pending(conn, strategy_id, session, *, decision)`; `upsert_snapshot(conn, strategy_id, snapshot)`; `read_snapshots(conn, strategy_id)`.
  - Bracket: `load_portfolio(conn, strategy_id) -> Portfolio`; `insert_pending_orders(conn, strategy_id, placed, companies=None) -> int`; `save_bracket_night(conn, strategy_id, portfolio, events, snapshot)`; `read_orders(conn, strategy_id) -> tuple[tuple[Order, Decimal | None], ...]`.
  - Book: `LoadedBook(book, pending_session, targets, idle_added)`; `load_book(conn, strategy_id, *, idle_symbol=None) -> LoadedBook`; `save_book_night(conn, strategy_id, book, fills, trades, snapshot, *, executed_targets=None)`; `save_book_decision(conn, strategy_id, session, targets)` (an empty decision writes no row); `read_book_positions`, `read_book_targets(conn, strategy_id, session)`, `read_book_fills`, `read_book_trades`.
  - Benchmark: `load_benchmark(conn, strategy_id="SPY") -> BenchmarkState`; `save_benchmark_night(conn, strategy_id, state, snapshot, fills)`.
  - Market: `dividends_on(conn, session, symbols)`, `dividends_between(conn, start, end)` (`book_runner.DividendMap` shape); `applied_splits_on(conn, session) -> tuple[tuple[str, Decimal], ...]`, `applied_splits_between(conn, start, end)`; `market_window_since(data_date) -> date`; `load_market_window(conn, since) -> Market` (bars via `backtest.io.read_bars_frame(conn, since=...)`, every membership interval, FX).
  - News verdicts (P6): `NewsVerdict(rank, symbol, verdict, reason, model, prompt_version, headlines, earnings_date, decided_at)`; `has_vetoes(conn, strategy_id, session) -> bool`; `write_vetoes(conn, strategy_id, session, verdicts) -> int` (plain INSERTs after validating ranks 1..n, unique symbols, a known verdict and a tz-aware `decided_at`; a duplicate is a database error, so callers check `has_vetoes` first in the same transaction); `read_vetoes(conn, strategy_id, session)` (by rank); `allowed_between(conn, strategy_id, start, end) -> dict[date, frozenset[str]]` (only `allow`, sessions `start..end` inclusive).

### dividends (P4)

- `AMOUNT_QUANTUM = Decimal("0.000001")`, `CASH_TYPES = frozenset({"CD", "SC"})`, `CURRENCY = "USD"`.
- `Dividend(symbol, ex_date, amount)`.
- `quantize_amount(value) -> Decimal`: rounded half-up to 6 decimals (`numeric(14,6)`).
- `parse_massive(raw) -> Dividend | None`: one Massive `/v3/reference/dividends` row, or None for a valid row Seer does not credit (other types or currencies).
- `totals(items) -> list[Dividend]`: one per (symbol, ex_date), the exact sum quantized half-up to 6 dp.
- `adjust_for_splits(items, split_items) -> list[Dividend]`: put freshly fetched dividends into the units of the bars fetched with them.
- `upsert_dividends(conn, items) -> int`: insert new dividends and update changed ones; returns how many rows changed.

### llm (P4)

- `ANTHROPIC_VERSION = "2023-06-01"`, `DEFAULT_TIMEOUT_S = 20.0`, `DEFAULT_RETRIES = 1`, `DEFAULT_BACKOFF_S = 2.0`, `DEFAULT_MAX_TOKENS = 400`, `MAX_ERROR_BODY = 200`.
- `LlmError(RuntimeError)`: a request failed after retries, or the reply held no text.
- `LlmConfig(base_url, api_key, model)` (`api_key` excluded from `repr`); `load_config() -> LlmConfig | None`: None when any of `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` is unset or empty.
- `messages_url(base_url) -> str`: the Messages endpoint for `base_url`. `scrub(text, secret) -> str`: key/token query parameters and every occurrence of `secret` redacted.
- `Client(cfg, *, transport=None, timeout=20.0, retries=1, backoff=2.0, max_tokens=400, sleep=time.sleep)`; `Client.complete(system, prompt, *, temperature=None, thinking=None, max_tokens=None) -> str`. The key goes out as both `x-api-key` and `Authorization: Bearer` (z.ai compatibility). `explain` calls it with no keywords, and its request body is byte-identical to P4's; `veto` (P6) passes `temperature=0.0`, `thinking="disabled"` (sent as `{"type": "disabled"}`) and `max_tokens=1024`, because `glm-5.3` with a small budget spends it on reasoning and returns no text. `explain` and `veto` catch every `LlmError`, so neither raises past it.

### finnhub (P6)

- `BASE_URL = "https://finnhub.io/api/v1"`, `MIN_INTERVAL = 1.0` (s between calls: the free tier's 60 a minute), `DEFAULT_TIMEOUT_S = 15.0`.
- `FinnhubError(message, status)`: a request failed after its retry. The text never holds the key.
- `load_key() -> str | None`: `config.get("FINNHUB_API_KEY")`.
- `Client(key, *, transport=None, base_url=BASE_URL, min_interval=MIN_INTERVAL, timeout=DEFAULT_TIMEOUT_S, retries=1, backoff=2.0, clock=time.monotonic, sleep=time.sleep)`; the key travels only in the `X-Finnhub-Token` header. One retry on a connection error, a timeout, 429 or 5xx (honouring a longer numeric `Retry-After`, capped at 60 s); anything else raises `FinnhubError`. Calls are spaced from the end of the previous attempt, retries included.
  - `company_news(symbol, start, end) -> list[Headline]` (`GET /company-news`; symbols in the dot form `bars` stores, e.g. `BRK.B`); items with a missing or non-integer `id` or `datetime`, or an empty headline, are dropped. No cutoff here: `veto` applies `select_headlines`.
  - `earnings(symbol, start, end) -> date | None` (`GET /calendar/earnings`): the earliest date in `[start, end]`, else None. For `BRK.B` the free tier returns the `BRK.A` row.

### P4 additions to existing modules

- `massive.Client.dividends(d)` (and the `MassiveSource` protocol): one call per fetched session, `/v3/reference/dividends?ex_dividend_date=D` (the free tier served 513 rows for 2026-09-18 in one page); USD cash dividends of types CD and SC, following `next_url`.
- `splits.apply_splits` also rewrites `dividends` before the execution date: `round(amount * split_from / split_to, 6)`.
- `commands/nightly.py`: fetches and stores dividends for every missing session in its one transaction, and adds paper-held symbols (`universe.paper_symbols(conn, d)`) to each session's wanted set, so a position keeps its bars after its symbol leaves the index.
- `universe.paper_symbols(conn, d) -> set[str]`: symbols paper state still needs a bar for on session `d`: pending or open `orders`, every `book_positions` row (the SPY benchmark holding included), and `book_targets` decided for `d` or later.
- `runs`: `start_paper(conn, run_id)`, `finish_paper(conn, run_id)` and `fail_paper(conn, run_id, error)` set `paper_status`, `paper_error` (redacted, cut like `error`) and `paper_finished_at` on the real run row.
- `sim.apply_book_split(book, symbol, factor, session, rules, targets=None) -> BookSplit` (`sim/book.py`, exported from `seer_engine.sim`): the book engine's split rule. Shares × factor (floored for whole-share rules); cash in lieu credited to cash and the position's `income_usd`; stop, take, mark and entry price ÷ the exact factor; floor-to-zero closes as `forced` at the old mark; pending targets for the symbol rescaled. `BookSplit(book, targets, in_lieu, trade, fills)`. Called only for splits recorded with `applied = true`.
- `backtest.io.read_bars_frame(conn, *, since=None)`: `since` limits the `COPY` to `date >= since`. The default is unchanged, so every existing caller and `load_market` are byte-identical.

## Migration 002 (`db/migrations/002_engine.sql`)

This migration is additive only. It is written by the engine, and web does not read these tables.

- `universe(symbol, index_id IN ('SP500','NDX'), start_date, end_date NULL, source_symbol)`, with PK `(index_id, symbol, start_date)`, `CHECK end_date > start_date` and an index on `symbol`. When an interval spans a rename, `source_symbol` joins the source tickers with `/`, oldest first (`FB/META`).
- `split_adjustments(symbol, execution_date, split_from > 0, split_to > 0, applied, recorded_at)`, with PK `(symbol, execution_date)`.
- `backfill_log(symbol PK, status IN ('ok','empty','failed'), first_date, last_date, rows, error, updated_at)`.
- `runs_real_session_uidx`: a unique index on `runs(session_date) WHERE NOT is_demo`, which allows at most one real run per session.

## Migration 003 (`db/migrations/003_paper.sql`, P4)

Additive only: new columns are nullable or defaulted, `orders` keeps every type and constraint.

- `strategies` gains `engine` (`bracket` | `book` | `benchmark`), `rules_id` (`design-v0`, `monthly-hold`, NULL for SPY) and `paper_start` (the first paper session; NULL until `paper` starts it). `params` holds the frozen spec, its digest and `backtest_gate`.
- `orders` gains `mark` (an open order's last close, in the order's own pre-split units).
- `runs` gains `paper_status` (`running` | `success` | `failed`), `paper_error` and `paper_finished_at`.
- `paper_state(strategy_id PK, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, pending_decision, updated_at)`: one row per paper strategy.
- `book_positions(strategy_id, symbol)` PK: `sim.book.Position` (fractional-capable `shares`, `mark`, entry date and price, `days_held`, episode `cost_usd` / `income_usd`, stop, take, `exit_pending`). The SPY benchmark's holding is a row here too.
- `book_targets(strategy_id, session_date, symbol)` PK, unique rank: a book strategy's ranked decision for one session, kept after execution, with `explanation`.
- `book_fills` (`seq` within a session, side, reason `entry`…`forced`) and `book_trades` (closed holding episodes, `idle` flag, exit reasons `signal`, `time`, `gap`, `tp`, `sl`, `forced`; index on `(strategy_id, exit_date)`).
- `dividends(symbol, ex_date)` PK, `amount` > 0: Massive cash dividends (CD + SC summed), in bars' units; `splits.apply_splits` rewrites them with the bars.
- Data: the four roster display rows (upsert; `SPY` is the only champion and the benchmark), and `B`/`C` deleted only when no `orders` or `equity_snapshots` row references them.
- Applied to Neon on 2026-10-04 (runbook ship check).

## Migration 004 (`db/migrations/004_news_veto.sql`, P6)

Additive only.

- Data: the `C` roster row (`C · News veto`, "A's picks, LLM can veto on news", icon `gavel`, sort 5, engine `bracket`, rules `design-v0`, not champion, not benchmark), as an upsert: 003 had deleted the old unreferenced `C` row.
- `news_vetoes(strategy_id → strategies, session_date, rank ≥ 1, symbol, verdict IN ('allow','veto','failed'), reason, model NULL when unset, prompt_version, headlines jsonb [{id, datetime, source, headline}] newest first, earnings_date, decided_at timestamptz)`, PK `(strategy_id, session_date, symbol)`, unique `(strategy_id, session_date, rank)`. One row per candidate checked; `paper` and `paper_check` read it, the LLM is never re-asked. About 0.55 MB a month.
- Demo-owned: `demo.DEMO_TABLES` includes `news_vetoes`. `paper`'s orphaned-rows guard does not count it (verdicts exist before C starts).
- Applied to Neon by the nightly `Migrate` step on the first scheduled run after the merge; that night also starts C's clock.

## Data Flow

Phase 1 provides the building blocks. Write commands in later phases use them in this order:

1. `cli.main` calls `config.load_env()`, builds the parser from `discover()`, sets up logging and calls the command's `run(args)`.
2. `run` opens `closing(db.connect())`. It does not use `with connect()`, because psycopg's connection context manager commits on exit.
3. `demo.purge_demo_if_needed(conn, args.dry_run)` runs in its own transaction before any other write.
4. Reads (`dates.run_dates`, `universe.*`, `http.get_json` / `fx.fetch_*`) are followed by writes (`bars.upsert_bars`, `fx.upsert_fx`, `runs.*`) inside `with db.transaction(conn, args.dry_run):`.
5. The transaction commits, or rolls back and re-raises. `main` maps exceptions to exit codes.

`veto` (P6) is the one write command that calls the network after reading the database: it reads the
candidates in a transaction it rolls back, makes every Finnhub and LLM call with no transaction open,
then writes all its rows in one short transaction. A network failure becomes a `failed` row, never an
exception. The real night is `migrate` → `nightly` → `veto` → `paper` → `paper_check` → `explain`.

## Dependencies

### External
- `psycopg[binary]>=3.2`: the Postgres driver, used for COPY into temp tables in the upserts.
- `pandas>=2.2`, `pandas_market_calendars>=5.0`: the NYSE schedule, including closes, half days and DST.
- `numpy>=2`: indicator math and the float64 arrays in `strategies.base.History` (declared in P3; it was already installed through pandas).
- `requests>=2.32`: HTTP, through one module-level `Session` in `http.py`.
- `python-dotenv>=1.0`: parses `.env.local`. The file is parsed, never `source`d, because it contains an unquoted `&`.
- `yfinance>=1.0`: used only by `yahoo.py` (phase 3 backfill, and P7a's research store through its dividends-aware download with `actions=True`), imported lazily.
- Finnhub REST (P6, no new package: `requests`): `company-news` and `calendar/earnings` on the free tier, 60 calls a minute.
- `scikit-learn>=1.9,<1.10` (P6a): Strategy B's `HistGradientBoostingRegressor`, used only by `strategies.b_model`. The minor version is pinned, because a frozen model is a pickle of its estimator, and `b_model`'s digest reads the fitted trees' private node arrays. It brings `threadpoolctl` (used to cap the threads in the determinism probe), `joblib` and `scipy`. `cli.discover` imports every command, so `backtest_b` makes every command load scikit-learn at startup (about 0.5–1 s); `import seer_engine.strategies` alone does not.
- dev: `pytest>=8`, `ruff>=0.16,<0.17` (lint config in `[tool.ruff]`: `py311`, selects `E9` and `F`, ignores `F401`).

### Internal module graph
- `cli` imports `config` and `commands`. `commands.migrate` imports `config` and `db`.
- `db` imports `config`. `demo` imports `db`.
- `prices` imports only the standard library; `bars` imports `prices` and re-exports it. `fx` imports `http` and `bars.to_decimal`. `runs` imports `dates.RunDates` and `http.redact`.
- `http` imports `__version__` for `USER_AGENT`.
- `yahoo` imports `bars` and pandas. `commands.backfill` imports `bars`, `dates`, `db`, `demo`, `fx`, `universe` and `yahoo`.
- `sim.model` imports `prices`. `sim.lifecycle` and `sim.split_adjust` import `dates`, `prices` and `sim.model`. `sim.sizing` imports `dates` and `sim.model`. Nothing in `sim` imports `bars`, `db` or `http`.
- `strategies.*` import numpy, `prices`, `sim` (for `Pick` and `q`) and each other. `backtest.market`, `runner`, `benchmark`, `metrics`, `tuning` and `report` import numpy, `dates`, `prices`, `sim`, `strategies` and each other; `backtest.market` also imports `seer_engine.fundamentals` (`EMPTY_PANEL`, `FundamentalPanel`), which is pure. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` imports `config`, psycopg, pandas, numpy and the pure backtest modules. `commands.backtest` imports `config`, `db`, `dates`, `prices`, `universe` (for `BENCHMARK`), `backtest.*` and `strategies.a`.
- `strategies.a2` imports numpy, `sim`, `strategies.a`, `strategies.base` and `strategies.indicators`; never `universe` (psycopg), so `REGIME_SYMBOL` repeats `universe.BENCHMARK` and a test asserts they are equal. `backtest.walkforward` imports `dates`, `strategies.a2`, `strategies.base` and `backtest.runner`, `metrics`, `tuning`, `market` and `benchmark`. `backtest.wf_report` imports `backtest.report`'s helpers (read-only), `dates`, `sim`, `strategies.a` (`ATR_N`, `SMA_N`), `strategies.a2`, and `backtest.metrics`, `runner`, `tuning`, `benchmark` and `walkforward`. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` also imports `wf_report` (for `write_wf_report`). `commands.backtest_wf` imports `config`, `db`, `dates`, `universe` (for `BENCHMARK`), `backtest.io`, `walkforward`, `benchmark`, `market`, `metrics`, `runner`, `tuning`, `wf_report`, `commands.backtest` (for `never_fetched_members`) and `strategies.a2`.
- `strategies.b_model` imports numpy, scikit-learn (`HistGradientBoostingRegressor`), `threadpoolctl`, `pickle` and `hashlib`, and nothing from the engine. scikit-learn loads none of psycopg, requests or yfinance, so the module stays pure. `strategies.b` imports numpy, `sim` (`Pick`), `strategies.a` (`_bracket`, `Features`, `DESIGN_PARAMS`), `strategies.base` and `strategies.indicators`. It never imports `b_model`, so `import seer_engine.strategies` does not load scikit-learn, and never `universe` (psycopg), so `SPY_SYMBOL` repeats `universe.BENCHMARK` and a test asserts they are equal.
- `backtest.labels` imports numpy, `dates`, `sim.model` (`TIME_STOP_DAYS`) and `strategies.base`; its `COST` repeats `sim.COST_RATE` as a float, and a test pins them equal. `backtest.b_walkforward` imports numpy, `dates`, `strategies.b`, `strategies.b_model`, `backtest.labels`, `runner`, `metrics`, `market`, `tuning` (`Verdict`) and `walkforward` (`Fold` and the private `_check_folds`, `_day`, `_session`, `_join`, `_GATE_NAMES`, read-only). `backtest.b_report` imports `backtest.report`'s and `wf_report`'s helpers (read-only), `dates`, `strategies.a`, `strategies.b`, `strategies.b_model` (constants), and `backtest.b_walkforward`, `labels`, `metrics`, `runner`, `tuning`, `benchmark` and `walkforward`. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` also imports `b_report` and `strategies.b_model` (for `write_b_report` and `write_model_artifact`). `commands.backtest_b` imports `config`, `db`, numpy, `backtest.io`, `b_walkforward`, `b_report`, `walkforward`, `benchmark`, `market`, `metrics`, `runner`, `commands.backtest_wf` (`resolve`, `tune_all`, `run_walk_forward`, `BacktestWfError`), `commands.backtest` (`never_fetched_members`), `strategies.a2`, `strategies.b` and `strategies.b_model`.
- `sim.rules` imports `dates` only (its agreement with `sim.model`'s constants is a test). `sim.book` imports `dates`, `prices` (`Bar`), `sim.model` (`q`) and `sim.rules`. Neither imports `sim.lifecycle` or `sim.sizing`, and nothing in `sim` imports `bars`, `db` or `http`.
- `strategies.allocator` imports numpy, `dates`, `prices`, `sim` (`Pick`, `q`), `sim.book`, `strategies.base` and `strategies.indicators`. It names `backtest.market.Market` under `TYPE_CHECKING` only (for `MarketAware` / `prepare_for`), so there is no runtime `strategies` -> `backtest` import and no cycle. `strategies.f_index`, `f_rotation`, `f_factor` and `f_swing` import numpy, `strategies.allocator` (`target_from_close`, and `month_end_closes` in `f_index`), `strategies.base`, `strategies.indicators` and `sim` / `sim.book`, plus `dates` (`f_index`) or `prices` (`f_rotation`, `f_swing`); none imports another family or `universe`.
- `backtest.book_runner` imports `dates`, `market`, `metrics`, `runner` (`run_backtest`, `RunResult`, `INITIAL_IDR`, read-only), `sim.book`, `sim.model`, `sim.rules`, `strategies.allocator` and `strategies.base`. `backtest.dev` imports `dates`, `tuning`, `benchmark`, `book_runner`, `market`, `metrics`, `runner` (`RunResult`), `sim.rules`, `strategies.allocator` and `strategies.base`. `backtest.dev_report` imports `benchmark`, `dev`, `metrics`, `report`'s helpers (read-only), `runner` (`INITIAL_IDR`, `YearGap`), `tuning` (thresholds), `sim.rules` and `strategies.allocator`. `backtest.registry` imports `dev`, `sim.rules`, `strategies.a` (`STRATEGY_A`, for `REF-A-V0`), `strategies.allocator`, `strategies.base` and every family module. None of them imports `bars`, `db`, `http` or `config`.
- `research` (impure) imports `config`, `dates`, `fx`, `membership`, `yahoo` (the dividends-aware download), `prices`, `backtest.benchmark`, `backtest.io` (`histories_from_frame`, `merge_intervals`) and `backtest.market`; it never imports `db`. `commands.research_store` imports `research`, `backtest.io` (the vendored SPY dividends for `--verify`, and `read_facts` for `--with-fundamentals`) and `seer_engine.fundamentals` (`Fact`, a type only); it still names neither `seer_engine.db` nor `psycopg`. `research` also imports `seer_engine.fundamentals` (`FACT_COLUMNS`, `Fact`, `FundamentalPanel`). `backtest.io` imports `seer_engine.fundamentals` and `seer_engine.db` (for `read_facts`). `backtest.io` also imports `dev_report` (for `dev_report_files` and `write_dev_report`). `commands.backtest_dev` imports `config`, `research`, `backtest.dev`, `dev_report`, `registry`, `backtest.io`, `benchmark`, `market`, `metrics`, `runner` and `sim`, and `subprocess` for the `git status` registry check.
- `strategies.c` imports `dates`, `sim` (`Pick`), `strategies.a` (`STRATEGY_A`, `STRATEGY_A_PARAMS`, `AParams`) and `strategies.base`; never `finnhub`, `llm`, `db` or `universe`. `finnhub` imports `config`, `http` (`redact`), `requests` and `strategies.c` (`Headline`). `commands.veto` imports `db`, `dates`, `demo`, `runs`, `finnhub`, `llm`, `commands.nightly` (`_parse_now`), `paper.roster`, `paper.store`, `sim.sizing` (`Pick`) and `strategies.c`.
### Standard library
`argparse`, `importlib`/`pkgutil` (command discovery), `logging`, `contextlib`, `dataclasses`, `decimal`, `functools.lru_cache`, `re`, `time`.

## Reverse Dependencies

- Within `engine/`, the phase 2 to 4 modules consume the API above exactly as written in the plan's "Shared interface contract": `membership.py` and `commands/universe.py` (phase 2), `yahoo.py` and `commands/backfill.py` (phase 3), and `massive.py`, `splits.py` and `commands/nightly.py` (phase 4).
- Phase 5 will add `.github/workflows/{engine-ci,nightly,universe,backfill}.yml`, which invoke the CLI.
- P4 (nightly) will call `strategies.a.STRATEGY_A.picks(...)` with `STRATEGY_A_PARAMS` and write `STRATEGY_A_PARAMS.as_dict()` to `strategies.params`. P6 adds strategies B and C beside `a.py`, implementing the same `Strategy` protocol.
- P4 is blocked: the P3b gate failed, and `STRATEGY_A2_PARAMS` is `None`. Nothing may deploy Strategy A or A2. P6's Strategy B can reuse `backtest.walkforward` (handover §8 option (a)), if the owner chooses it.
- P4 stays blocked: the P6a gate failed, `STRATEGY_B_FROZEN` is `None`, and no model artifact is committed. Nothing may deploy Strategy A, A2 or B. B's one round has failed on this data. The owner chooses among the report's options (b), (c) and (d).
- P4 stays blocked through P7a: no registry candidate was eligible on the dev window, so P7b does not run, and nothing in `strategies/` or `backtest/registry.py` may be deployed. The owner decides next with the dev frontier.
- Nothing in `web/` imports the engine. The two share only the database schema and `schema_migrations`.
- P4 runs **paper-only** (owner option (b), 2026-10-04): `commands/paper.py` steps the frozen roster (`paper/roster.py`: `SPY`, `A` with `STRATEGY_A_PARAMS`, `F4-MOM12-N20-TREND` and `F1-SPY-SMA200-M` from `backtest/registry.py`, read-only) through the same `sim` and strategy/allocator code the backtests ran. Nothing is a real-money recommendation: SPY is the champion, and `strategies.params.backtest_gate.passed` is false for every entry.
- `web/lib/data.ts` reads `paper_state`, `book_positions`, `book_targets`, `book_trades`, `orders`, `equity_snapshots`, `news_vetoes` (P6, Positions' "Vetoed tonight"), `runs.paper_*` and `strategies.params`/`paper_start` (read-only; `params.backtest_gate.applicable`). The web never imports the engine; the schema in migrations 003 and 004 is the contract.
- `.github/workflows/nightly.yml` runs `migrate` → `nightly` → `veto` (P6, `continue-on-error`, 10 minutes) → `paper` → `paper_check` → `explain`; `.github/workflows/engine-ci.yml` runs `ruff check engine` (rules in `pyproject.toml`) before pytest.

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
- Dev search (P7a), measured on the research store `5451195fd552` (2,490,793 bar rows, 539 symbols, through 2015-10-16; 130 MB on disk), WSL2, Python 3.11:
  - `research_store --verify` (sha256 of every file, the `DEV_END` scan and the three data checks, no network): 4.3 s.
  - `backtest_dev`: store load 2.11 s; 54 candidates, sequentially, from 0.07 s to 5.26 s each, each allocator's one-time feature preparation included in its first candidate (median 0.43 s; slowest `F9-SPY200D50-SWING50`); 45.2 s for all 54 including the survivorship table and SPY curves; rendering and writing the five files under 1 s (not logged separately; read from the log timestamps).
  - Whole command: 0:51 for the committed run, 0:49 for the identical re-run; peak RSS 847 MB. Well under D13's 60-minute threshold, so there is no process pool.
- Paper (P4), measured on Neon on 2026-10-04 from WSL2, Python 3.11, with the real data (bars through
  2026-10-02), as a rolled-back first night (`--dry-run -v paper`, four strategies started, 0 sessions stepped):
  - Windowed bars load: 247,310 bars since 2025-03-31 in 1.69 s (`store.load_market_window`, timed separately; inside the command the window, splits and dividends took about 5 s). The plan's probe: `COPY … WHERE date >= '2025-06-01'`
    219,575 rows in 2.34 s; `>= '2024-10-01'` 326,410 rows in 2.73 s. There is no pickle cache.
  - Whole command: 6.94 s wall, peak RSS 238 MB. That is well inside the nightly job's 45-minute timeout.
  - `paper_check` before any session: 1.38 s wall. Its cost grows with the paper window, one
    `run_rules` per strategy over `[paper_start, last_session]`.
  - Migration 003 left the database at 186 MB (186 MB before; bars are 177 MB of it). The paper tables
    grow by kilobytes per month.
- Veto (P6), measured on 2026-10-04 from WSL2 with a local smoke (10 liquid symbols, no database): Finnhub `company-news` median 0.29 s (its 1 s spacing already passed during the previous LLM call) and `calendar/earnings` median 1.26 s (including the spacing), LLM verdict (`glm-5.3`, thinking disabled) median 3.05 s (max 4.97 s), 45.1 s for all 10. A night is at most 10 candidates, about 1 minute; the workflow step's 10-minute limit bounds the worst case. Details: the runbook's "Strategy C: the news check".
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

### Paper: one night (P4)

The night as `commands/paper.py` runs it, after `nightly` has succeeded for `rd.session_date`.
Every arrow below is a call into code the backtests also run.

1. `rd = dates.run_dates(now)`; refuse (exit 1, nothing written) unless the real `runs` row for `rd.session_date` is `success`.
2. `plan_night(roster.ROSTER, rows, states, rd)` reads the roster rows (`store.read_strategies`) and every strategy's `store.read_paper_state`, checks each frozen digest (`store.check_digest`) and decides which entries start and which step. Nothing to do: exit 0.
3. `runs.start_paper` (its own short transaction). Then, in one transaction: the windowed market (`store.load_market_window(conn, since)` with `since = store.market_window_since(earliest)`, 550 calendar days before the earliest session to step), the applied splits per session (`store.applied_splits_on`) and the dividends (`store.dividends_between`). Each session S is computed on `night_view(market, S, later_factors(...))`: the market as it stood on S's night, later bars and FX hidden, splits executed after S undone on bars and dividends.
4. First night only (`_start`): `store.freeze_spec` writes each frozen spec (`roster.strategy_params(e)`) and `paper_start = rd.session_date`; `store.init_paper_state` writes `paper_state` (initial cash `initial_cash_usd(INITIAL_IDR, the latest fx_rates rate ≤ rd.data_date)`) and the day-0 snapshot at `rd.data_date`; then the decision for `paper_start`.
5. For every session S after `paper_state.last_session` through `rd.data_date`, per strategy:
   - A: `paper.bracket.settle_bracket(pf, S, bars, splits, last_bar_date)`, which is `apply_split` per applied split, then `sim.step`, then `close_unpriced`, with the snapshot replaced; `store.save_bracket_night`; then `decide_bracket(pf, e.obj, e.params, history, members, S)` → `store.insert_pending_orders`, `store.write_pending`;
   - C: exactly as A, with `e.obj.with_allowed(store.allowed_between(conn, "C", first, last))` as the strategy, so its picks are A's first 10 minus every symbol without a stored `allow`;
   - F4, F1: `paper.book.settle_book(book, S, bars, targets, idle_added, rules, dividends, splits, last_bar_date)`, which is `sim.apply_book_split` per applied split, then `sim.step_book`, then `close_book_unpriced`; `store.save_book_night(..., executed_targets=)`; then `decide_book(view, e.obj, e.params, rules, S, held)` → `store.save_book_decision` (targets, or `None` when the next session is not a month's first);
   - SPY: `paper.benchmark.step_benchmark(state, S, bar, dividend, split=<applied SPY split on S or None>)`, the `buy_and_hold` rules; `store.save_benchmark_night`, `store.write_pending`.
6. `runs.finish_paper` sets `runs.paper_status = success` inside the same transaction, so a failure rolls back everything; `runs.fail_paper` then records `paper_status = failed` and the redacted error in its own transaction (exit 1).

Run it:

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v paper   # rolled back
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v paper_check
```

The real night runs only in `nightly.yml` (Veto → Paper → Paper check → Explain).

### Paper: replay check (P4)

`paper_check` re-runs `backtest.book_runner.run_rules` (A, F4, F1) and the `buy_and_hold` rules
(SPY) over `[paper_start, last_session]` on the same windowed market, with `paper_state.usd_idr`, and
compares them with the stored state through `paper.replay` (pure: `expected_bracket`,
`expected_book`, `expected_benchmark`, `compare`, `judge`): every snapshot, order, fill, closed trade,
stored decision and open position. `--require-sessions N` also demands ≥ N stepped sessions per
strategy. That is the v0.1.0 release check.

### Strategy C: the news check (P6)

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v veto   # real calls, rolled back
```

`veto` needs `FINNHUB_API_KEY` and `LLM_*` (with `LLM_MODEL=glm-5.3`); without them every verdict is
`failed`. Only the nightly job runs it for real. Then `paper` decides C from the stored verdicts and
`paper_check` replays it from the same rows.

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

### Research store and the dev search (P7a)

```
cd <repo or worktree root>
engine/.venv/bin/python -m seer_engine research_store            # build engine/.research (network; 30-60 min)
engine/.venv/bin/python -m seer_engine research_store --verify   # no network: sha256s, DEV_END guard, data checks, fingerprint
engine/.venv/bin/python -m seer_engine backtest_dev              # every REGISTRY candidate, dev window only (~1 min)
```

Neither command needs `SEER_ENV_FILE`: neither reads Neon. Then read
`docs/backtests/<run date>-p7a-dev-exploration.md` and `docs/plans/<run date>-p7b-preregistration.md`.
The report's store fingerprint must equal `research_store --verify`'s, and its registry digest must
equal `sha256sum engine/src/seer_engine/backtest/registry.py` at the committed registry.

To add a candidate (D6): append it to `REGISTRY`, pin its `(id, digest)` in `tests/test_registry.py`,
and commit both **before** running it. A smoke run of one candidate is `backtest_dev --only <ID>`,
which writes nothing. A committed report always comes from a full run over a clean registry.

### Gotchas
- Do not use `with psycopg.connect(...) as conn`, because it commits on exit and defeats `--dry-run`. Use `contextlib.closing` instead.
- Every write must be inside `db.transaction(conn, dry_run)`. The helpers never commit, so a write outside it is lost or left open.
- `demo.purge_demo_if_needed` must run before the first write. Any demo `runs` row means `bars` and `fx_rates` will be TRUNCATEd.
- Never build a local-midnight datetime from a date. Pass `date` objects, and give `last_completed_session`/`run_dates` an aware UTC datetime.
- Convert symbols to Yahoo's dash form (`BRK-B`) only inside the Yahoo adapter (phase 3). Tables always store `BRK.B`.
- `universe.end_date` is exclusive.
- Under `--dry-run`, `migrate` reports the files it would apply, but leaves no `schema_migrations` table behind.
- **The dev window is law.** Every dev entry point raises `backtest.dev.DevWindowError` for a session after 2015-10-16, and `research.load_store` rejects a store holding a later row. Never add a flag, a default or a store that gets past either guard. P7b runs the pre-registered finalists on the test window under its own handover.
- **The registry is append-only.** `tests/test_registry.py` pins every `(id, digest)`. A new candidate is appended and pinned in its own commit, before its dev run (D6). Editing an entry after its result exists is not allowed, even to fix a "typo": append a new id instead, and it counts as a trial.
- `backtest_dev` refuses a full run (exit 2) while `backtest/registry.py` has uncommitted changes. `--only` skips that check and writes nothing; its numbers are a smoke test, never a result.
- **Paper state stays in the units it was sized in.** Never rebuild a mark or a price of a live paper order or position from `bars`: `nightly` rewrites history backwards on a split, and `apply_split` / `apply_book_split` would then rescale it twice. Marks are stored (`orders.mark`, `book_positions.mark`).
- **A roster entry is frozen.** `paper` fails the night (`store.SpecMismatch`, rolled back, `runs.paper_status = failed`) when a started strategy's stored spec digest differs from `paper/roster.py`'s. Change a strategy by adding a new id (its own `paper_start`), never by editing a started one or deleting its rows.
- `paper` runs only after a successful bars run for the same session, and only in the `seer-db-writer` concurrency group. Never run a real (non-`--dry-run`) `paper` locally against Neon while the scheduled job may run, and never before the code is on `main` (D11: no back-dated paper days).
- `paper_check` reports a strategy `split-affected` (not failed) once an applied split touched a symbol it held or had pending: whole-share rounding before and after a split cannot match a replay over adjusted bars.
- `explain` must never decide anything: it writes text only, and a failure leaves NULL.
- **C's verdicts are decided once.** `paper_check` replays C from `news_vetoes` and never re-asks the LLM. Never edit, delete or re-run verdicts for a session Paper already decided: the replay would no longer match what Paper did. `veto` refuses on its own once the session is checked or decided.
- **C's model is part of its spec.** `LLM_MODEL` must be `glm-5.3`; another value makes every C verdict `failed`. Editing `strategies.c.FROZEN_MODEL`, the prompt or any `CParams` field changes C's digest and fails the whole night with `SpecMismatch`. A different model or prompt is a new roster id.
- **No look-ahead in news.** `select_headlines` keeps only items published before the `veto` run started (`decided_at`); the earnings window is the schedule as known then.
- **Rebuild a `Market` with `dataclasses.replace`, never `Market(history=..., membership=..., fx=...)`.** Every windowing site that re-listed the fields by hand (`paper.replay.expected_bracket`, `commands.paper.night_view`, `backtest.dev`'s FX-window copy) now uses `replace`, so a new field such as `fundamentals` is carried over instead of being silently dropped back to the empty panel. Use `market.with_fundamentals(panel)` to attach one.
- **`prepare_market` must not be added to the `Allocator` protocol.** `Allocator` is `runtime_checkable` and several production sites test `isinstance(x, Allocator)`; adding a member — even one with a default body — makes every structural implementer fail the check. Implement `strategies.allocator.MarketAware` alongside it and let `prepare_for(obj, market)` dispatch.
- **Fundamentals are optional everywhere they are read.** A database with no `fundamental_facts` / `ticker_cik` (or no rows) loads to `EMPTY_FUNDAMENTALS`, and a research store built before the panel existed loads with a bit-identical fingerprint. Never make either an error: the backtest must stay runnable on a database that has not applied `005_fundamentals.sql`.

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

The P7a sections (`sim.rules`, `sim.book`, the allocators and families F1–F11, the book runner, the
research store, the dev runner, report and registry, the `research_store` and `backtest_dev`
commands, and the committed dev report and P7b pre-registration) were added on 2026-10-04. Their
design, invariants and decisions are in `TRADE_RULES_DEV_SEARCH_PLAN.md` and
`docs/handover/2026-10-03-trade-rules-revision.md`.

The P4 sections (`paper/*`, the `paper`, `paper_check` and `explain` commands, `dividends`, `llm`,
the book split rule, migration 003, the P4 additions to `massive`, `splits`, `nightly`, `universe`,
`runs`, `demo` and `backtest.io`, and the real nightly flow under Usage) were added on 2026-10-04.
P4 runs paper-only by the owner's option (b) of 2026-10-04: no real-money recommendations, design §1
unchanged. Design, invariants and decisions: `PAPER_TRADING_SHIP_PLAN.md` and
`docs/handover/2026-10-04-paper-trading-ship.md`; operations: `docs/runbooks/paper-trading.md`.

The P6 Strategy C sections (`strategies.c`, `finnhub`, the `llm` call options, roster entry `C`,
the `news_vetoes` store, migration 004, the `veto` command, and C in `paper`, `paper_check` and the
nightly flow) were added on 2026-10-04. C runs on paper only: no backtest gate applies to an LLM
strategy (design §1 item 5), and real money for C would need an explicit owner decision. Design,
invariants and decisions: `STRATEGY_C_NEWS_VETO_PLAN.md` and
`docs/handover/2026-10-04-strategy-c-news-veto.md`; operations: `docs/runbooks/paper-trading.md`.
