# Package: seer_engine

**Location**: `engine` (src layout: `engine/src/seer_engine`)
**Last Updated**: 2026-10-06 (make the research-store clobber guard checkout-independent, the single phase of `RESEARCH_STORE_CLOBBER_GUARD_PLAN.md`: `research_store`'s build path now refuses a wrong-window store by its manifest, not by its path)

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
- The roster as data (roster-promotion-pipeline, phase 1): a paper portfolio is a `strategies` row, not a Python literal. Migration 006 adds the lifecycle (`status`, `paper_end`, `promoted_from`) and definition (`object_name`, `registry_id`, `gate_note`, `gate_applicable`) columns; `paper/roster.py` gains `RESOLVER` (the one code-side table mapping a stable object name to the live `Strategy` / `Allocator`) and `from_row` / `from_rows`, which build `RosterEntry` values out of rows; `paper/store.py` gains `read_roster_rows`. `ROSTER` is now `from_rows(SEED_ROWS)`, so the compiled roster and a database's roster travel the same builder, and the five pinned spec digests are unchanged. `veto` still reads the compiled `ROSTER`; `paper` and `paper_check` read the stored one (phase 2)
- The roster is read at run time, and retirement is a lifecycle (roster-promotion-pipeline, phase 2): `paper` and `paper_check` build their entries with `roster.from_rows(store.read_roster_rows(conn))` instead of the compiled `ROSTER`, so adding or replacing a horseman is a row change, not a code edit. `paper/store.py` gains `retire` and `set_paper_end`, the only two writers of the lifecycle columns; a `status = 'retired'` entry is a deliberate skip on the night (no orders, no equity snapshot, no `paper_state` step) and keeps every history row it ever wrote, while `paper_check` replays it like any other, so its record stays verifiable after it stops trading
- Promotion: the lab reaches the roster by command (roster-promotion-pipeline, phase 5): `commands/promote.py` turns a lab method's pre-registered `Candidate` into a `strategies` row (`status='active'`, `promoted_from=<method id>`, `registry_id` NULL, the full contract-C2 `params`, and **no** `paper_start` — the next paper night starts the clock the ordinary way, so a promoted strategy's record begins at its promotion). The row is read back and rebuilt through `roster.from_row` inside the same transaction, so a row the night would refuse never commits; `--retire <id>` runs phase 2's `store.retire` in that transaction, making a swap atomic. `lab/store.py` gains `record_promotion` (an append-only, idempotent lab note, moving the method's status only along the existing `('test-passed','paper')` edge) and `PROMOTION_MARKER`. `backtest/registry.py` is deliberately never touched (Decisions D1)
- Honest comparison (roster-promotion-pipeline, phase 3): `paper/compare.py` is the pure, common-window, risk-adjusted comparison of the paper equity curves — every ranked figure is computed over the one window every ranked strategy shares (the intersection of snapshot dates, not `[max(start), min(end)]`), the window travels with the figures, inception-to-date is carried separately and never ranked, and a strategy that cannot join the window is an explicit `insufficient` row with a reason rather than a silent omission. The read-only `compare` command is its one impure edge
- `FND` joins the roster (roster-promotion-pipeline, phase 6): a sixth entry, `FND · Fundamentals` (top 20 by SEC filing factors, monthly; `object_name = 'FUNDAMENTAL'`, `rules_id = 'monthly-hold'`, the book engine, `sort = 6`, `promoted_from = 'M0005'`, `registry_id` NULL), seeded by migration 007 and put on the live board by phase 5's `promote --method M0005 --candidate M0005-ALL --id FND --lab-status-stays` — the first promotion through the new lab → roster path rather than around it. Its `gate_note` says out loud that it **failed** its M0005 dev-window gate: passing a backtest gate has never been this roster's admission criterion (Decisions D5), and the gate binds the real-money decision, not paper membership. It is also the roster's first `MarketAware` object, which is why `paper/book.py` and `paper/replay.py` gained the prepared dispatch below. The five pre-existing spec digests are unchanged and `MAX_LOOKBACK_BARS` is still 253
- Two windows, two stores (build-promotion-path, phase 2): the research window became a parameter on the store half. `build_store` / `load_store` / `refresh_fundamentals` each take a keyword `window=` defaulting to `DEV_WINDOW`, and a store declares its own window in three **optional** manifest keys (`window_name`, `window_start`, `window_end`) that a dev build never writes — **absent means dev**, so `engine/.research`'s manifest stays exactly the nine `MANIFEST_KEYS` it was sealed with and its fingerprint cannot move. `research_store --test-window` builds the P7b test-window store (2015-10-19..data end) into `engine/.research-test` (gitignored); `load_store` refuses a dev store where a test store is expected and the reverse, before it reads a single data file. `MANIFEST_KEYS` is unchanged at nine, no test-window look is spent, and no lab state changes
- Pre-registration, the half a database cannot enforce (build-promotion-path, phase 3): the lab gets **one** look at the test window per configuration, and `UNIQUE(config_digest, window)` on `trials` enforces the *count* but not *which* configuration the look is spent on. `lab/prereg.py` owns the committed file that does — `docs/lab/prereg/MNNNN.md`, a strict `key: value` block then prose — with its writer, its parser (`parse(render(p, name)) == p` exactly) and the gate `lab test` calls before it looks (`require_committed`, `check_digest`). `lab promote <method>` writes that file for the method's best dev-eligible variant by MAR (`lab.store.best_dev_eligible`) and moves the method `dev-eligible -> promoted`; it loads no research store, runs no backtest and inserts no `trials` row, so pre-registering costs no look. A pre-registration is written once and never rewritten: a better variant found later is a new method with its own dev trials, not an edit to the file
- Spending the look (build-promotion-path, phase 4): `lab test <candidate>` is the one counted look at the test window, and the last step before the roster. `lab/runner.py` gains an appended test-window half — `Tested`, `resolve_candidate`, `preflight_test`, `test_trial_row`, `run_test` — and `commands/lab.py` the `test` subcommand (with `--dry-run`, `--store`, `--roster-id`). It refuses, in this order, a method that is not `promoted`, a method file that has changed since its dev trials ran, a missing or uncommitted pre-registration, a pre-registered digest that has drifted, a configuration with no recorded dev trial, and a configuration that has already had its look — the last enforced in the database by `UNIQUE(config_digest, window)`, not only in the command — and it refuses a dev research store *by name* before anything is loaded. A run appends exactly one `trials` row with `window = 'test'`, which **does not move the lab's N** (`dev_trial_count` and `dev_daily_sharpes` stay dev-only, so a test look is a look, not a search); DSR is recorded and never decides the verdict, because a pre-registered look has no selection among results to deflate. The method ends at `test-passed` or `test-failed`, both final, and a pass prints a ready-to-run `seer_engine promote ...` line that hands off to phase 5's existing paper-roster path. `lab status` now lists `Test-passed` and `Test-failed` alongside `Promoted (pre-registered)`; against the real lab `test-window looks used` still reads 0 — this phase builds the mechanism and spends nothing
- The clobber guard knows a store by its content, not by its path (research-store-clobber-guard, the set's single phase): `commands/research_store.py`'s two `_same_dir` guards compare the `--store` path against `research.STORE_DIR` / `research.TEST_STORE_DIR`, which are derived from the **running module's own location** — so a `--test-window` build aimed at another checkout's or worktree's `engine/.research` was not refused, and a build replaces the whole directory. The **build path only** now also asks the target what it is: `_declared_window_or_none` wraps `research.declared_window`, and a declared window that disagrees with `--test-window` exits 2 before a single symbol is downloaded. The answer comes from the target's own `manifest.json`, so it holds for a store anywhere on the machine; `None` means *undecidable*, never *wrong*, so a missing, empty or unparseable target falls through and the first build of all still works. The two path guards are byte-for-byte unchanged and still fire first, and `--verify`, `--coverage` and `--refresh-fundamentals` are untouched — they read a store rather than replace one

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
    research.py             local research store: build_store() / load_store() / refresh_fundamentals(), each with a keyword window=; test_window(), latest_session(), declared_window(); the D9 end-of-window guard (impure; P7a, windowed in build-promotion-path phase 2)
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
      roster.py             the roster builder: RESOLVER, Row / RosterRow, from_row() / from_rows(), SEED_ROWS -> ROSTER (six entries), active(), canonical spec text, digest, backtest_gate
      bracket.py            settle_bracket(), decide_bracket(): run_backtest's loop body for one session
      book.py               settle_book(), decide_book(): run_book's loop body for one session, incl. the MarketAware prepared branch (phase 6)
      benchmark.py          BenchmarkState, start_benchmark(), split_benchmark(), step_benchmark(): buy_and_hold for one session
      replay.py             the pure comparison behind paper_check
      compare.py            common-window, risk-adjusted comparison of the equity curves: Window, Performance, Row, Comparison, compare(), render(), as_json() (phase 3)
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
      window.py             Window(name, start, end), WINDOW_NAMES: the session range a run is bound to (P7a)
      dev.py                DEV_WINDOW / DEV_END guard, Candidate, candidate_window(), run_registry(), D8 finalists(), deflated_sharpe() (P7a)
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
    lab/                    the method lab (docs/plans/2026-10-04-method-lab-design.md); only store.py and prereg.py touch the disk
      __init__.py           docstring only
      method.py             a lab method file: METHOD, Candidate, METHOD_ID, discover(), config_digest(), source_sha()
      store.py              lab/lab.sqlite: committed and append-only; methods, trials, ideas, insights; TRANSITIONS, record_promotion(), best_dev_eligible() (build-promotion-path phase 3)
      runner.py             `lab run`: one committed method's variants on the dev window, into the database; git_head(); and the appended test-window half — Tested, resolve_candidate(), preflight_test(), test_trial_row(), run_test() (build-promotion-path phase 4)
      prereg.py             the docs/lab/prereg/MNNNN.md pre-registration: Prereg, render()/parse(), require_committed(), check_digest(), check_source(), promote_method() (build-promotion-path phase 3)
      seed.py               one-time import of the pre-lab record (P7a's 54 candidates)
      methods/              one file per method, mNNNN_<slug>.py exporting METHOD
    commands/
      __init__.py           command-module contract
      migrate.py            `migrate` command
      backfill.py           `backfill` command (phase 3)
      backtest.py           `backtest` command (P3)
      backtest_wf.py        `backtest_wf` command (P3b)
      backtest_b.py         `backtest_b` command (P6a)
      research_store.py     `research_store` command (P7a)
      backtest_dev.py       `backtest_dev` command (P7a)
      lab.py                `lab` command: the method lab (status / show / run / promote / test / idea / note / insight / stage / export ...)
      nightly.py            `nightly` command (P1; P4 adds dividends and held paper symbols)
      paper.py              `paper` command (P4)
      paper_check.py        `paper_check` command (P4)
      explain.py            `explain` command (P4)
      veto.py               `veto` command (P6): Strategy C's nightly news check
      promote.py            `promote` command (roster-promotion-pipeline phase 5): a lab method's variant -> a `strategies` row
      compare.py            `compare` command (roster-promotion-pipeline phase 3): read-only ranking over the common window
  tests/                    pytest; DB tests need PG_TEST_URL
  data/spy_dividends.csv    SPY dividends (ex_date, amount_usd), vendored from yfinance (see data/SOURCES.md)
  .cache/                   gitignored; bars-<max date>-<rows>.pkl and fundamentals-<max filed>-<rows>.pkl written by the backtest loader
  .research/                gitignored; the P7a research store, dev window: bars.csv, dividends.csv, fx.csv, unserved.csv, manifest.json (research_store), plus the optional fundamentals.csv (--with-fundamentals)
  .research-test/           gitignored; the P7b test-window store, the same files (research_store --test-window), its manifest declaring window_name/window_start/window_end; built on the first promotion and never before (build-promotion-path phase 2)
docs/backtests/             committed reports: <end>-strategy-a{.md,-equity.csv,-equity.svg} (P3); <end>-strategy-a2-walkforward{.md,-equity.csv,-equity.svg,-variants.svg,-grid.csv} (P3b); <end>-strategy-b-walkforward{.md,-equity.csv,-equity.svg} (P6a); <run date>-p7a-dev-exploration{.md,-rows.csv,-curves.csv,-frontier.svg} (P7a)
docs/plans/                 <run date>-p7b-preregistration.md: the P7b finalists (or "none eligible"), written by backtest_dev (P7a)
docs/lab/prereg/            committed pre-registrations, one MNNNN.md per promoted method, written by `lab promote`; README.md documents the format (build-promotion-path phase 3)
db/migrations/002_engine.sql  (outside the package, owned by it)
db/migrations/003_paper.sql   (outside the package; paper state, book tables, dividends, roster rows; P4)
db/migrations/004_news_veto.sql (outside the package; the C roster row and news_vetoes; P6)
db/migrations/006_roster.sql  (outside the package; the strategies lifecycle and definition columns, and the five seeded rows' definition values; roster-promotion-pipeline phase 1)
db/migrations/007_fnd.sql     (outside the package; the FND roster row, so a database brought up from migrations has one; roster-promotion-pipeline phase 6)
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
                                    [--test-window [--window-end YYYY-MM-DD]]
```

This builds the local research store (D5). It covers bars for every S&P 500 member since 1996 and
Nasdaq-100 member since 2007 that yfinance can serve, plus the 21 research ETFs, cash dividends
from the start, and Frankfurter USD/IDR. It **never connects to Neon** and needs no database
setting — `--with-fundamentals` is the single exception, below.

**Two windows, two stores** (build-promotion-path phase 2): the **dev window**
(1993-01-29..2015-10-16) in `engine/.research` is the default — what `lab run` and `backtest_dev`
read, and the store whose fingerprint every recorded lab trial was measured against — and the
**test window** (2015-10-19..data end) lives in `engine/.research-test` behind `--test-window`,
read only by `lab test`. The two are **not** interchangeable: `research.load_store` refuses a store
whose declared window is not the one the caller asked for, and this command refuses (exit 2) to
build one window into the other's directory even when the operator names it explicitly — by **path**
for this checkout's own two directories, and, since research-store-clobber-guard, by **content** as
well: a build reads the target's own `manifest.json` (`research.declared_window`) and refuses when
the store already sitting there declares the other window, which protects a store in **any** checkout
or worktree and not merely the running one. A target holding no readable store declares nothing, so
the first build of all still proceeds.

- **`--store`** defaults to `engine/.research` (gitignored), or `engine/.research-test` with
  `--test-window`, and **`--batch-size`** to 40 symbols per yfinance request.
- **`--test-window`** (build-promotion-path phase 2) acts on the P7b test store. A build covers
  `2015-10-19..`the latest completed NYSE session and records that window in the manifest's three
  optional keys. It still holds the **same deep history from 1993-01-29** as the dev store — a
  candidate first traded on 2015-10-19 needs its `lookback` bars before that date, and the one
  look per configuration is append-only, so a store starting at its own window start would make
  that look permanently wrong. The universe follows the window at both ends, so every company that
  joined the index after October 2015 is in and everything that left before 2015-10-19 is out.
  Build it only when something is being promoted (design S3), never speculatively.
- **`--window-end`** pins the test window's last scored session instead of taking the latest
  completed one, so an interrupted build can be resumed to the *same* end rather than silently
  moving. It must be an NYSE session after `DEV_END`, applies only with `--test-window`, and only
  to a build — `--verify`, `--coverage` and `--refresh-fundamentals` read the window the store
  already declares (exit 2 otherwise).
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
  on failure. Re-sealing **re-declares the window the store already had**, so refreshing a store
  can never change which window it is for, and the mode refuses a store whose declared window
  disagrees with `--test-window`.
- **`--coverage`** (fundamental-panel-coverage) loads the store and prints, for each sampled
  dev-window date, how many symbols the panel can actually rank — a symbol counts only when
  `as_of` returns a snapshot with **non-empty `observations`** whose newest fact was filed within
  `max_stale_days` — plus one fraction over the window. `as_of` never returns `None`, so a
  presence check measures nothing; this is the content check, and it is the same measure
  `lab run` refuses on below `fundamentals.coverage.MIN_DEV_COVERAGE`. No network, no database.
  It reads no bars, so membership, `min_price` and `min_dollar_volume` are not applied and the
  fraction is an **upper bound**: below the floor is conclusive, above it is necessary and not
  sufficient. It is a **dev-window** measure and is refused (exit 2) with `--test-window`.
- **The build** is throttled with backoff and runs all-or-nothing: temp files first, then a rename.
  The same downloads give byte-identical files and the same fingerprint. Nothing dated after the
  window's end is kept — 2015-10-16 on the dev window, the recorded `window_end` on a test store.
- **`--verify`** uses no network. It loads the store, checks every file's sha256 against
  `manifest.json` and that no row is after the store's declared window end, runs three data checks
  (SPY has a bar on every NYSE session from 1993-02-01 through that end; SPY's dividends equal the
  vendored `data/spy_dividends.csv` on the overlap of the two; AAPL's 2012 dividends are on the
  split-adjusted price scale), and prints the window, the fingerprint and the counts. The printed
  window states what is **scored** and `store_start` what is **held**, which differ on a test
  store. It is the check to run before any dev run, and it refuses a store whose declared window
  disagrees with `--test-window`.
- **`--dry-run`** builds into a temporary directory, verifies it, and discards it.
- **Logs:** batches, unserved symbols, counts, and the fingerprint.
- **Exit codes:** 0 when the store is built (or loaded) and all three checks pass; 1 when the build
  fails (nothing is written, any previous store is kept) or a check fails; 2 when the store is
  missing or invalid (a tampered file, or a row after the declared window's end), or when the flags
  refuse — a store/window mismatch, `--test-window` aimed at `engine/.research` or a dev invocation
  aimed at `engine/.research-test`, a **build** whose target directory already holds a store whose
  manifest declares the other window (the content guard, which holds wherever that store lives),
  `--window-end` without `--test-window` or on a read-only mode, or `--coverage` with
  `--test-window`.

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
- **The roster comes from the database** (phase 2): `store.read_roster_rows` through `roster.from_rows`, not the compiled `ROSTER`. A row whose `object_name` or `rules_id` cannot be resolved stops the night by name and writes nothing — never a silently dropped portfolio. An entry on the roster with no `paper_start` starts tonight, exactly as any new entry does.
- **`FND`** (phase 6) is on the roster like any other row and starts on its next night, with no `paper_start` written by migration 007 and no special case in the command. It is the roster's one `MarketAware` object: `paper.book.decide_book` prepares it from the whole `Market` so it ranks on `market.fundamentals`. On a database without `005_fundamentals.sql` applied — or with the table empty — the panel is `EMPTY_PANEL`, no symbol is eligible and FND holds cash: an all-cash FND, never a wrong one.
- **First night**: writes each roster row's frozen spec (`params`) and `paper_start = session_date`, `paper_state` (initial cash 20,000,000 IDR at the latest FX on or before `data_date`), day-0 snapshots at `data_date`, and the first decisions.
- **Every night**: steps every session after `paper_state.last_session` through `data_date` for every strategy, then decides `session_date`. See Usage, "Paper: one night".
- **Retired entries** (`status = 'retired'`) take no decision at all: no orders, no equity snapshot, no `paper_state` step, and no history row is read or written. The only column the night may write for one is `paper_end`, stamped with the last session it actually traded and only when a retirement taken by hand SQL left it NULL. Once every retirement is stamped the night is an ordinary no-op again, so an all-retired roster is cheap rather than a crash. A `status` the night does not understand fails it instead of guessing, and a deliberate skip never shares a code path or a log line with an unresolvable row.
- **Strategy C**: C's strategy object is given the verdicts stored in `news_vetoes` for the sessions being decided (`store.allowed_between`); only `allow` is bought, and a missing verdict counts as `failed`. `paper` makes no network call and never fails because of C's verdicts.
- **Idempotent** per (strategy, session): a re-run for a session already done writes nothing.
- **One transaction** for the whole night plus `runs.paper_status`. A failure rolls back everything and records `paper_status = failed`.
- **Frozen spec**: a started strategy whose stored digest differs from `paper/roster.py` fails the night as `store.SpecMismatch` (rolled back, `paper_status = failed`, exit 1). A `paper_start` with no `paper_state` is refused the same way until the clock is reset.
- **Exit codes**: 0 = stepped and decided, or already done (no-op); 1 = no successful bars run for the session (nothing written), or the night failed (rolled back, `paper_status = failed`, `paper_error` set); 2 = missing setting (`DATABASE_URL_UNPOOLED`).

### `paper_check` (P4)

```
usage: seer_engine paper_check [-h] [--dry-run] [-v] [--require-sessions N]
```

The read-only replay check (D7). See Usage, "Paper: replay check". The roster is read from the `strategies` rows in the same read-only transaction (phase 2), so the replay checks exactly what the night traded; a retired strategy is replayed like any other, keeping its `paper_start`, its `paper_state` and every history row. C is replayed from its stored verdicts, read in the same read-only transaction; the LLM is never asked again. "Not started" (no `paper_start`) is a pass. A strategy touched by an applied split is reported `split-affected`, not failed. `--require-sessions N` is the v0.1.0 release check. Exit codes: 0 = every started strategy `ok` or `split-affected` (or none started); 1 = a mismatch, or `--require-sessions N` unmet (`not-started` counts as 0); 2 = missing setting.

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

### `promote` (roster-promotion-pipeline phase 5, P1-ENG-Z8MR)

```
usage: seer_engine promote [-h] [--dry-run] [-v] --method M0001 [--candidate M0001-A]
                           --id FND --name NAME --sub SUB [--icon ICON] [--sort N]
                           --gate-note NOTE [--gate-not-applicable] [--retire ID]
                           [--lab-db PATH] [--lab-status-stays]
```

The lab → roster bridge (plan Decisions D1, D3, D5, D6): it puts a lab method's pre-registered variant on the paper roster as a `strategies` row. It is the only writer that creates a roster entry, it is run by hand, and the nightly job never calls it.

- **Promotable means two things**, and anything that is not both is refused. (1) The method file exposes the variant as a `Candidate` — a frozen (rules, allocator, params) triple; the roster entry is that triple unchanged, and nothing here invents a parameter. (2) The variant's allocator is a value `paper.roster.RESOLVER` names: `object_name_of(obj)` inverts `RESOLVER`, and raises `NotPromotable` both when no name maps to the object (the message gives the `Binding(...)` line to add) and when more than one does, because the name is part of the frozen spec and an object with two names has two digests.
- **The rules must be the `sim.rules` preset of their own id** (`_check_rules`): a roster row carries only `rules_id`, so a one-off `TradeRules` would be frozen under one rule set and read back under another — a `store.SpecMismatch` on the entry's first paper night instead of a refusal here.
- **`find_candidate`** reads `lab.method.discover()`. No committed method file, a multi-variant method named without `--candidate`, and an unknown `--candidate` are each a named `NotPromotable` that lists what does exist.
- **`check_lookback`** raises at promotion time what `commands/paper.py:_check_window` would raise at 23:00 on the entry's first night, so the roster never holds a row the night cannot feed.
- **One `strategies` INSERT**: the display columns, **every** definition column migration 006 added (`object_name`, `registry_id` **NULL**, `gate_note`, `gate_applicable` — `roster.from_row` refuses a row without them, so leaving one out would fail the next night for the whole board), `status = 'active'`, `promoted_from = <method id>`, the full contract-C2 `params` (spec, digest, backtest_gate), and **no `paper_start`**: the next paper night freezes the spec through `paper.store.freeze_spec` and starts the clock exactly as for any new entry, which is what keeps the record honest — a promoted strategy's track record begins when it was promoted. `is_champion` and `is_benchmark` are always false (a promotion never takes the champion from `SPY`); `--sort` defaults to one past the current maximum.
- **The row is proved before it commits**: `_insert` reads it back with `paper_store.read_strategy` and rebuilds it through `roster.from_row` **inside the same transaction**, then compares the rebuilt digest with the planned one. Any `RosterError`, or a digest that moved, aborts the promotion with the night's own message, so a row the paper night would refuse is never committed. (Phase 1 asked for this hook by name.)
- **`--retire <id>`** calls phase 2's `paper.store.retire` in that same transaction, so a swap is atomic and the board never shows five active horsemen or three. `--retire` equal to `--id` is refused outright.
- **The target id**: `_check_target` raises `AlreadyStarted` when the id already has a `paper_start` (invariant 3, add never mutate: months of track record must not be re-pointed at another algorithm) and `RosterConflict` when the id exists and is not this promotion's own row. An existing unfrozen row with the same `promoted_from` **and** the same digest *is* this promotion's own: the insert is skipped and only the lab side is re-recorded.
- **The lab record** is `lab.store.record_promotion(conn, method_id=, strategy_id=, candidate_id=, object_name=, spec_digest=, retired_id=, move_status=)`, which returns the method's status. The lab is append-only, so the promotion is *added*: `analysis` grows by one dated `# Promotion` section (`methods_analysis_grows` permits only growth) and one `insights` row of kind `observation` is appended. `status` moves to `paper` **only** along the edge `TRANSITIONS` already has, `('test-passed','paper')`; a method already at `paper` is left alone, and any other status raises `LabError` rather than inventing an edge. It is **idempotent**: a method whose `analysis` already carries `PROMOTION_MARKER` followed by the roster id is already recorded, and the call writes nothing. `hypothesis`, `verdict`, `parent_id` and above all `source_sha` are never written, and no `trials` row is inserted — a promotion is not a backtest and must not move the lab's N. The caller holds the transaction, as for every other writer in that module.
- **`--lab-status-stays`** records the promotion and leaves the method's lab status alone. It is required when the method is not at `test-passed` or `paper`, because `TRANSITIONS` has no other edge to `paper`; the roster's admission rule is not the lab's gate (Decisions D5), so taking a method the lab has not passed is allowed but must be said out loud.
- **`backtest/registry.py` is never touched** (Decisions D1). `REGISTRY` is the P7a dev-run candidate set, fixed *before* the run, capped at `dev.MAX_CANDIDATES` and digest-pinned; appending to it would corrupt the multiple-testing count the lab's `trials` table exists to maintain. A promoted method reaches the roster through the roster's own resolver, the way `A` and `C` do. Also never written: `paper_start`, any paper history row, any `trials` row, any lab `source_sha`, and any `TRANSITIONS` edge that is not already there.
- **Two databases, one promotion**: the roster is Neon, the lab is `lab/lab.sqlite`, and they cannot share a transaction. So the lab's rules are checked first and write nothing, the roster transaction commits, then the lab record commits (`lab_store.begin_immediate`, rolled back on any exception). The only possible partial outcome is "roster written, lab note missing", and re-running the identical command repairs it, since the insert is skipped for a row this promotion already owns and `record_promotion` is idempotent. The reverse order was rejected: a lab note for a promotion that did not happen cannot be taken back from an append-only database.
- **`render_plan`** prints every row the promotion will write — the INSERT column by column, the `--retire` UPDATE, the two lab writes, and `backtest.registry.REGISTRY untouched` — on every run, dry or not. `--dry-run` rolls back both transactions and says so.
- **Exit codes**: 0 success; 2 for any `PromoteError` (`NotPromotable`, `AlreadyStarted`, `RosterConflict`), `roster.RosterError`, `lab_store.LabError` or `paper_store.StoreError`; 1 for anything else.
- Tests: `tests/test_promote_command.py` (20) and the `record_promotion` cases in `tests/test_lab_store.py`.

### `compare` (roster-promotion-pipeline phase 3)

```
python -m seer_engine compare [--min-sessions N] [--exclude ID ...] [--json] [--require-window]
```

Ranks the paper strategies over the window they **share**, with that window stated rather than
implied. Read-only, and the one impure edge of the pure `paper/compare.py`: it reads every
`equity_snapshots` row in a single `REPEATABLE READ, READ ONLY` transaction that is always rolled
back, hands them to `paper.compare.compare`, and prints the window, the ranking over it, what could
not be ranked and why, and inception-to-date as a separate block. Nothing else is read — no
`strategies` row, no roster, no clock — so `--dry-run` changes nothing because there is nothing to
change.

- **`--min-sessions N`** (default `paper.compare.MIN_COMMON_SESSIONS`, 63; minimum 2) is the floor on
  how short the common window may be.
- **`--exclude ID`** drops a strategy from the comparison. Because the command does not read
  `strategies`, it does not know which entries are retired, and that is deliberate: a retired
  strategy is not a live competitor, so excluding it is a caller's decision, not this module's
  arithmetic. The leaderboard's TypeScript port makes the same decision from `strategies.status`.
- **`--json`** prints `paper.compare.as_json` instead of the table — the exact shape that port is
  pinned against.
- **Exit codes**: 0 when a comparison was produced; with `--require-window`, 1 when no window of
  `--min-sessions` sessions exists (useful in CI, and the honest answer for a young board); 2 for a
  missing setting.

### `lab promote` (build-promotion-path phase 3)

```
python -m seer_engine lab promote M0007 [--dir PATH]
```

Method lab design §3 in one command: it pre-registers a method's best dev-eligible variant for the
test window and moves the method `dev-eligible -> promoted`. It loads no research store, runs no
backtest and inserts no `trials` row, so `store.test_looks` reads the same after it as before —
pre-registering costs no look.

- **Which variant**: `lab.store.best_dev_eligible(conn, method_id)` — the highest `mar` among that
  method's `window = 'dev'`, `eligible = 1` trials, ties broken on the trial number. "One variant per
  method" is a property of that query, not of the caller. A test trial is never a candidate: letting
  one back in would let a test number decide what gets tested.
- **What it writes**: `docs/lab/prereg/M0007.md` (`--dir` relocates it, for tests), one dated
  `# Pre-registration` section appended to the method's `analysis`, one `insights` row of kind
  `observation`, and the status transition. The file is written **first**, inside the write lock, and
  the status moves second in the same transaction — the file write is not rolled back, and that
  asymmetry is the point. A crash between them leaves a pre-registration for a method still reading
  `dev-eligible`, which a re-run finishes, rather than a `promoted` method with nothing
  pre-registered, which is the one state design §3 forbids.
- **The digest is copied, never recomputed** from the live method file: it comes off the recorded dev
  `trials` row, so the file names what was actually measured. `prereg.check_source` separately proves
  the method file still hashes to the `source_sha` frozen when it ran and that the trial's candidate
  still digests to the trial's `config_digest`.
- **Idempotent, and more than idempotent**: a method already at `promoted` is not moved again (the
  forward-only trigger would refuse it anyway) and its analysis is not appended to twice; a
  pre-registration already on disk is read, checked and left **byte-for-byte alone**, date line
  included — rewriting identical-but-for-the-date bytes would un-commit a file whose whole value is
  that it was committed first. A *missing* file is rewritten, which repairs a half-finished promotion.
- **It refuses to change its mind**: when the file, or the method's analysis, already pre-registers a
  different candidate than the one the database now ranks best, that is a `PreregError`. The first
  choice is the one the look is spent on; a genuinely better variant is a new method with its own dev
  trials, not a new version of this file.
- **`--dry-run` is ignored**, as it is for every `lab` subcommand: there is no roll-back half to show,
  and a dry run that printed a pre-registration without writing it would be exactly the artefact
  design §3 exists to prevent.
- **Output**: whether the file was written or already pre-registered the candidate, the method's
  status, the candidate and its dev trial, the config digest, the dev window with MAR / DSR / N, the
  test window, the gate, the `git add` / `git commit` / `lab test` lines to run next, and the
  test-window look count.
- **Exit codes**: 0 success; 2 for any `PreregError` (a `store.LabError`, so `lab`'s existing handler
  already maps it); 1 for anything else.
- Tests: `tests/test_lab_prereg.py` (25) and the `best_dev_eligible` case in `tests/test_lab_store.py`.

### `lab test` (build-promotion-path phase 4)

```
python -m seer_engine lab test M0007-RESID [--store PATH] [--roster-id ID] [--dry-run]
```

The one counted look at the test window (design §3), and the last step before the paper roster. It
is addressed by **candidate**, not by method: one variant per method is pre-registered, and it is
that variant the look is spent on. `runner.resolve_candidate` reads it out of the committed method
file, so `lab test` runs the file, not a database row.

- **It refuses before it loads anything**, in this order (`runner.preflight_test`, every one a
  `store.LabError`): the method is not `promoted` (only `lab promote` moves it there); the method
  file is uncommitted, or no longer hashes to the `source_sha` its dev trials ran under — a changed
  method is a new variation method, not a second look; there is no committed pre-registration naming
  this method and this candidate (`prereg.require_committed`); the pre-registered configuration
  digest has drifted (`prereg.check_digest`); this configuration has no recorded `dev` trial — the
  test window confirms a dev result, it never discovers one; and this configuration has already had
  its look. That last refusal is the readable, early form of a no the database makes anyway:
  `UNIQUE(config_digest, window)` on `trials` plus the append-only triggers. None of them spends
  anything.
- **The store must be the test store.** `--store` defaults to `research.TEST_STORE_DIR`
  (`engine/.research-test`) or `$SEER_RESEARCH_TEST_STORE`. The command asks
  `research.declared_window(store_dir)` what the store is for and refuses a dev store **by name**
  before a data file is read; `load_store` refuses the mismatch a second time, and `run_test` makes
  the same check a third time on `data.window`. Three independent noes, because a `window = 'test'`
  row measured on dev data can never be corrected. A missing store is reported with the
  `research_store --test-window` line that builds it, and a `MarketAware` candidate against a test
  store with no fundamentals panel is refused rather than measured.
- **What a run records**: exactly one `trials` row with `window = 'test'`, appended with the status
  move in one `BEGIN IMMEDIATE` transaction, with `preflight_test` re-run inside the lock so a
  parallel session cannot win the same look twice. The candidate goes through `dev.run_registry` —
  the same path, the same `prepare_for` dispatch and the same D8 row as `lab run`, with the window
  as the only difference.
- **It does not move the lab's N.** `n_trials_at_run` is `store.dev_trial_count` as it already
  stands: `trials` counts the multiple testing of the *search*, and a pre-registered look at an
  already-counted configuration is not a new search. `dev_trial_count` and `dev_daily_sharpes` stay
  dev-only, so every recorded dev trial stays reproducible and a later dev trial is deflated by
  exactly the N it would have had if this look had never happened.
- **DSR is recorded and is not a condition.** The verdict is the five design §1 go-live conditions
  (`dev.FAILURE_LABELS`), which `dev.make_row` has already applied; `store.DSR_LABEL` never appears
  in a test trial's `failed`. A pre-registered look has no selection among results to deflate.
- **The method ends final**: `test-passed` or `test-failed`, and `TRANSITIONS` gives `promoted` only
  those two exits. `test-failed` is final on every window — the follow-up is a variation method with
  its own dev trials, not a retry.
- **On a pass it prints the next command rather than running it** (`_promote_argv`): a complete
  `python -m seer_engine promote --method ... --candidate ... --id ... --gate-note ...` line, plus
  `lab stage`. `lab test` reads a research store and a SQLite file and stays offline; `promote`
  opens Neon, and the two writes cannot share a transaction. `--roster-id` sets the id proposed in
  that line (default: the method id). The generated `--gate-note` states both windows and says out
  loud what the method still has not got — forward paper time.
- **`--dry-run`** prints what would run (the method, variant, config digest, the committed
  pre-registration and its date, the store, the five conditions, and both outcomes) and stops. It
  loads nothing, runs nothing and records nothing; the look is not spent. This is the one `lab`
  subcommand where `--dry-run` means something.
- **Output**: the refreshed `lab show` for the method, then the verdict with return vs SPY TR, CAGR,
  max DD, PF, trades, MAR and the recorded DSR at N, then either the promote hand-off or the
  `test-failed` note, then `Lab N (dev trials) is still N; test-window looks used: K`.
- **Exit codes**: 0 success (a `test-failed` verdict is a successful run and exits 0); 2 for any
  `store.LabError`, which is every refusal above; 1 for anything else.
- `lab status` lists `Test-passed` and `Test-failed` as their own sections, next to `Dev-eligible`
  and `Promoted (pre-registered)`. Against the real lab, `test-window looks used` reads **0**: this
  phase builds the mechanism and spends nothing.
- Tests: `tests/test_lab_test_window.py`, with the fixtures in `tests/labkit.py`.


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
The store is local and gitignored: `engine/.research/` for the dev window, and since
build-promotion-path phase 2 `engine/.research-test/` for the P7b test window. Every public entry
point takes a keyword `window=` that defaults to `DEV_WINDOW`, so every caller that predates the
parameter builds, loads and refreshes exactly what it did before.

- Constants:
  - `DEV_END = date(2015, 10, 16)`, `DEV_WINDOW`, `MEMBERSHIP_START` and `FX_START`, each equal to
    `backtest.dev`'s (tested);
  - `STORE_START = date(1993, 1, 29)`;
  - `STORE_DIR` (`engine/.research`), and since build-promotion-path phase 2
    `TEST_STORE_DIR` (`engine/.research-test`) and `TEST_WINDOW_START = date(2015, 10, 19)`, the
    first session the test window **trades** — deliberately *not* where the test store's data
    starts, which is `STORE_START` on both windows;
  - `RESEARCH_ETFS`: 21 ETFs (BIL, DIA, EFA, GLD, IEF, IWM, QLD, QQQ, SHY, SPY, SSO, TLT and the 9
    sector SPDRs);
  - `SECTOR_ETFS`, equal to `backtest.registry.SECTOR_ETFS` (tested).
  - `DATA_FILES` (the four required files) and, since edgar-fundamentals,
    `OPTIONAL_DATA_FILES = (FUNDAMENTALS_FILE,)`. `fundamentals.csv` is in the **optional** tuple,
    never a fifth required file: `_read_manifest` requires `DATA_FILES` and *permits* the optional
    ones, and the fingerprint is the sha256 of the sorted `name:sha` lines of the files that were
    actually written. So a store built before this phase keeps loading with a **bit-identical
    fingerprint**, and `--verify` still passes on it.
  - `MANIFEST_KEYS` — still the same **nine** keys — and, since build-promotion-path phase 2,
    `OPTIONAL_MANIFEST_KEYS = {window_name, window_start, window_end}`: the window a non-dev store
    declares, all three or none. They say what the store is **scored** on, never what it holds
    (`store_start` is `1993-01-29` on a test store too), and `dev_end` stays a *code-version pin*
    — the `DEV_END` the building code was compiled against — which a test store carries unchanged.
    **Absent means the dev window.** That is the compatibility hinge, not a convenience:
    `engine/.research` was sealed with exactly `MANIFEST_KEYS`, so a dev build writes none of the
    three and its manifest stays byte-identical. The fingerprint is unaffected either way —
    `fingerprint_of` hashes the `files` map alone — but the manifest's bytes are not, and a shipped
    test reads them. It is the same precedent `OPTIONAL_DATA_FILES` set for a four-file manifest
    from before fundamentals existed.
- The window-bearing helpers — `requested_symbols`, `research_membership`, `unserved_by_year` and
  the private `_overlaps_window` / `_members_start` — each take a keyword `window=` that defaults
  to `DEV_WINDOW`, so every existing caller is unchanged. The membership lower bound stays
  `max(window.start, MEMBERSHIP_START)`: it is a property of the vendored CSVs, not of the window,
  and for the dev window (`start = date.min`) it is `MEMBERSHIP_START` exactly as before.
  `UNSERVED_REASON` is now produced by `unserved_reason(start=STORE_START, end=DEV_END)`; the
  module constant is kept as that function's default call, so `unserved.csv` is byte-identical.
- The window entry points (build-promotion-path phase 2):
  - `test_window(end) -> Window`: `TEST_WINDOW_START` through `end`, equal to
    `DEV_WINDOW.following("test", end)` and asserted equal to it in `tests/test_research_test_store.py`
    so the two spellings cannot drift. `ValueError` when `end` is not after `DEV_END` (that is the
    dev window's territory) or is not an NYSE session. `end` is deliberately **not** a constant: a
    hardcoded end goes stale and would silently change what a recorded test trial meant.
  - `latest_session(now_utc=None) -> date`: an injectable wrapper over
    `dates.last_completed_session` — "data end" at build time, the default end of a
    `--test-window` build.
  - `declared_window(store_dir) -> Window`: what a store says it is for, from its manifest alone.
    It reads no data file and verifies nothing, so a caller can pass the matching `window` to
    `load_store`, which does the verifying. A store with no window keys declares `DEV_WINDOW`. It
    is **not** a way around `load_store`'s refusal — a caller that wants the dev window still
    passes `DEV_WINDOW` and is still refused a test store — and `lab run` and `backtest_dev` never
    call it.
- Files. All are LF text, sorted and deterministic, with prices at 4 dp like `bars`:

| File | Columns | Notes |
|---|---|---|
| `bars.csv` | `symbol,date,open,high,low,close,volume` | split-adjusted, not dividend-adjusted (`auto_adjust=False`), dates ≤ `DEV_END` |
| `dividends.csv` | `symbol,ex_date,amount` | cash dividends from `actions=True`, ≤ 6 dp |
| `fx.csv` | `date,usd_idr` | Frankfurter from 1999-01-04 |
| `unserved.csv` | `symbol,reason` | members overlapping [1996-01-02, `DEV_END`] that yfinance could not serve |
| `fundamentals.csv` | `FACT_COLUMNS`: `symbol,taxonomy,tag,unit,period_start,period_end,val,accn,form,fy,fp,filed` | **optional** (edgar-fundamentals), written only with `--with-fundamentals`; sorted, in `io.FACTS_COPY_SQL`'s encoding |
| `manifest.json` | — | counts, a sha256 per file, and `fingerprint` (the sha256 of the sorted `name:sha` lines); no timestamps |

- `build_store(store_dir, *, downloader=None, fetch_fx=None, sleep=time.sleep, batch_size=40, data_dir=None, facts=None, window=DEV_WINDOW)`:
  - `window` is the window the store is built for and declares. On the default every byte is what
    it was before the parameter existed — same symbols, same range, same `unserved.csv` text, same
    nine manifest keys, same fingerprint. Pass `test_window(latest_session())` for the test store.
  - **the data range follows `window.end` alone**: always `STORE_START..window.end` for bars and
    `FX_START..window.end` for FX, on either window. A test store therefore carries the *same* deep
    history as the dev store plus everything after it.
  - **the universe follows the window at both ends**: `requested_symbols(data_dir, window=window)`
    is every member overlapping `[max(window.start, MEMBERSHIP_START), window.end]` —
    `[1996-01-02, DEV_END]` on the dev window, unchanged. On the test window every post-2015 joiner
    is in and everything that left before 2015-10-19 is out, because no test-window session ever
    ranks, holds or exits one; `members_on(t)` is the same set either way and only the crawl size
    differs. A membership interval closing in 2018 also stays closed instead of reading as open.
  - facts are **not** filtered by `window`: `FundamentalPanel` selects point-in-time on `filed <= t`
    at read time, so a later filing is invisible on an earlier session, and filtering here would
    rewrite `fundamentals.csv` and move the dev store's fingerprint for no gain.
  - `unserved.csv` names the range the **download** covered (`STORE_START..window.end`), which is
    byte-identical to `UNSERVED_REASON` on the dev window;
  - downloads are throttled and batched, with rate-limit backoff like `backfill`;
  - rows after `window.end` are dropped defensively;
  - it writes every file to a temp dir and then renames it, so the build is all-or-nothing
    (`ResearchStoreError` on failure);
  - `facts` (edgar-fundamentals) is the SEC point-in-time panel as a plain sequence of
    `fundamentals.Fact`, rendered by `fundamentals_lines(facts)` into `fundamentals.csv` and added
    to the manifest. `None` — the default, and every caller that predates fundamentals — writes no
    `fundamentals.csv` at all. `research.py` never opens a connection for them: the command passes
    them in (see `--with-fundamentals` below), so the "Never Neon" invariant (D5) is unchanged.
  - it returns the manifest.
- `load_store(store_dir, *, data_dir=None, window=DEV_WINDOW) -> ResearchData(market, dividends, spy_dividends, fingerprint, manifest, unserved, window)`:
  - `window` is the window the **caller** expects, and `ResearchData` now carries the window the
    store declares. The default means every dev path — `lab run`, `backtest_dev`, this module's own
    refresh — gets the dev guarantee without passing anything, and a mis-pointed
    `SEER_RESEARCH_STORE` aimed at the test store fails loudly instead of silently running the dev
    pipeline on test data. A test-window caller must ask for it explicitly, normally by passing
    `declared_window(store_dir)` straight back in.
  - **it refuses a window mismatch before it reads a data file**: a dev store where a test store is
    expected, or the reverse, is a `ValueError` naming both windows. The two are not
    interchangeable — the test store holds the same history *and* every session after `DEV_END`, so
    loading one where the other is expected would run the dev pipeline on unseen data (D9).
  - it verifies every sha256 and rejects any row dated after `window.end` (`ValueError`, also for a
    missing store). That is the data-level guard of D9; on the dev window the refusal message is
    unchanged, word for word.
  - Its `Market` takes membership from `membership.compute_universe()` through
    `io.merge_intervals`, offline. Its `fundamentals` is `_read_fundamentals(fundamentals.csv)`
    when the manifest lists that file and `EMPTY_FUNDAMENTALS` otherwise (edgar-fundamentals), so
    a pre-fundamentals store loads to a market with an empty panel rather than an error.
- `run_checks(data, vendored)`: the three data checks `research_store --verify` prints. Two of
  them now follow `data.window` (build-promotion-path phase 2): `check_spy_sessions` defaults its
  `end` to the store's own window end, and `check_spy_dividends` compares on the overlap
  `[first vendored ex_date, min(window end, last vendored ex_date)]`. The clamp is what stops a
  test store built past the vendored file's last row from reading as a mismatch; on the dev window
  the window end is still the earlier bound, so neither check weakens.
- `refresh_fundamentals(store_dir, facts, *, data_dir=None, window=DEV_WINDOW)`, the
  fundamentals-only refresh (fundamental-panel-coverage): reuses an existing store's four
  required files byte for byte, writes a new `fundamentals.csv`, re-seals and `_swap_in`s. The
  manifest's copied counts (`bar_rows`, `dividend_rows`, `fx_rows`, `symbols_requested`,
  `symbols_served`) are carried over, never re-derived from a download. `window` must be the window
  the store declares (pass `declared_window(store_dir)`); `load_store` refuses a mismatch, so a dev
  refresh can never be aimed at the test store or the reverse, and `_seal` re-declares the same
  window — refreshing a store never changes which window it is for.

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

**That fingerprint cannot move**, and build-promotion-path phase 2 was built around keeping it so:
it is the identity `/sync-research-store` keys on and the one every recorded lab trial was measured
against. The dev store's manifest therefore still carries exactly nine keys — the window keys are
optional and a dev build writes none of them — and the dev store has **no test-window twin inside
it**: the test window is a separate directory, `engine/.research-test`, with no fingerprint on
record until something is actually promoted.

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

- **`backtest.window`**: one frozen value object and nothing else — `Window(name, start, end)`,
  with `name` in `WINDOW_NAMES = ("dev", "test")`, `covers(d)` and
  `following(name, end)` (the window opening on the session after this one). Pure, and the purity
  glob covers it. It holds no date of its own, so it adds no third copy of `DEV_END`: the dev
  window is a constant in each of the two modules that already own one (`dev.DEV_WINDOW` and
  `research.DEV_WINDOW`, pinned equal by `tests/test_backtest_window.py`, as the two `DEV_END`s
  are). `start = date.min` means *no lower bound* — that is the dev window, whose backtests open
  as early as the data allows (SPY's first session, 1993-01-29).
- **`backtest.dev`**:
  - Constants: `DEV_END = 2015-10-16`, `DEV_WINDOW = Window("dev", date.min, DEV_END)`,
    `MEMBERSHIP_START = 1996-01-02`, `FX_START = 1999-01-04` and `MAX_CANDIDATES = 60`.
  - **The window is a value, not a module constant.** Every entry point below takes a `window=`
    argument that **defaults to `DEV_WINDOW`**, so a caller that passes nothing gets the D9 dev
    behaviour it has always had, byte for byte; `DEV_END` itself is unchanged.
  - `check_dev_session(d, window=DEV_WINDOW)` raises `DevWindowError` (a `ValueError`) after
    `window.end` — `DEV_END` on every path that passes no window. Every public entry point calls
    it before anything else.
  - `Candidate(id, family, rules, allocator, params, rationale, added, owner_inputs)`.
    `candidate_owner_inputs(c)` returns `rule_owner_inputs` plus every held ETF outside
    `DEFAULT_ETFS`, plus `leverage` for a held leveraged ETF. An empty tuple means executable under
    the conservative defaults.
  - `candidate_window(market, c, *, window=DEV_WINDOW) -> (start, window.end)`. The start is the
    first session where every instrument the candidate reads, and SPY, has its lookback. A member
    family also starts no earlier than `MEMBERSHIP_START`, and no candidate opens before
    `window.start` — a floor that can never bind on the dev window, whose start is `date.min`.
  - `run_candidate(market, dividends, spy_dividends, c, *, prepared=None, window=DEV_WINDOW)` and
    `run_registry(market, dividends, spy_dividends, registry, *, on_result=None, window=DEV_WINDOW)`
    run sequentially, in registry order, with one prepared value per allocator id — built by
    `strategies.allocator.prepare_for(allocator, market)` (edgar-fundamentals), so a `MarketAware`
    allocator gets the whole `Market` (fundamentals included) and every other one gets exactly the
    `allocator.prepare(market.history)` it got before. The candidate's market copy carries
    `fundamentals` over with `history` and `membership`, so a long window keeps the panel. Starting cash is
    `initial_cash_usd(20,000,000 IDR, usd_idr_on(max(start, FX_START)))`; a window starting before
    `FX_START` runs on a market copy whose `fx` is that single rate (D-C). FX before 1999 affects
    only that conversion, never a decision.
  - `DevRow` holds the stats and both SPY curves on the candidate's own window and cash. SPY's
    dividends come from the store. Its trailing `window` field (defaulted to `DEV_WINDOW`) records
    which window produced the row; `make_row(..., window=DEV_WINDOW)` carries it over.
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

### lab: pre-registration (build-promotion-path phase 3)

`lab/prereg.py` owns the `docs/lab/prereg/MNNNN.md` format — its writer, its parser and the
committed-file gate. Nothing in it loads a research store, runs a backtest or writes a `trials` row.

- **Why a file at all.** The lab gets one look at the test window per configuration, and the database
  already enforces that much: `UNIQUE(config_digest, window)` plus the append-only triggers. What a
  database cannot enforce is *which* configuration the look is spent on, and it cannot stop a
  disappointing answer from retroactively becoming a different question. The committed markdown file
  is that missing half, and the property is a conjunction of three facts: the file's `config_digest`
  is copied out of the recorded dev `trials` row and never recomputed from the live method file; the
  method file still hashes to the `source_sha` frozen when it ran; and the file is in git, unmodified,
  before the look. `docs/lab/prereg/README.md` states the same contract for a human reader.
- `PreregError(store.LabError)`: every refusal in the module. Being a `LabError` means
  `commands/lab.py` already turns it into exit 2 and no caller needs a second `except`.
- `Prereg`: a frozen dataclass of the file's front-matter block — `method`, `candidate`,
  `config_digest`, `rules_id`, `allocator_id`, `dev_trial`, `dev_window`, `test_window`, `gate`,
  `mar`, `dsr`, `n_trials_at_run`, `store_fingerprint`, `git_sha`, `date`. **Every field is a `str`**:
  the file is the record and this value is a reading of it, not a parallel source of truth, so
  `parse(render(p, name)) == p` exactly with no number formatting in the round trip. `FIELDS` is the
  tuple of names, taken from the dataclass.
- `render(p, name) -> str` / `parse(text) -> Prereg`: the exact bytes of the file, and the reading of
  them. `parse` is strict on purpose — the block must be the first thing in the file, must be closed
  by its second `---`, must carry every key in `FIELDS` exactly once and must carry nothing else. An
  unknown key is an error rather than a shrug, so a misspelled `config_digest` can never read as "no
  digest given".
- `require_committed(candidate_id, *, directory=None) -> Prereg`: **the gate `lab test` calls before
  it spends the look**, and the only reason the module exists — a test number must not be reachable
  unless the thing being tested was named, in git, first. It refuses when `candidate_id` is not a
  `MNNNN-SUFFIX` candidate id (a bare method id is an ambiguity to refuse, not a thing to guess at),
  when `docs/lab/prereg/<method>.md` does not exist, when git does not track it or it has staged or
  unstaged changes, when it does not parse, and when it pre-registers a different method or a
  different candidate. It deliberately does **not** look at the database: the method's status and the
  one-look rule are the caller's refusals, so a missing file and a wrong status give different
  messages rather than one vague one.
- `check_digest(p, digest, *, directory=None) -> None`: `require_committed` matched the candidate's
  *id*; this matches what the candidate *does*, which is the match that counts — an id can be reused,
  a digest cannot. The caller passes the digest of the thing it is about to run.
- `check_source(method_id, row, trial) -> Path`: two equalities, both `PreregError` when broken — the
  method file's sha256 is the `source_sha` frozen when the method ran, and the candidate the trial
  names still digests to the trial's `config_digest`. The second is checked even though the first
  mostly implies it, because `config_digest` canonicalizes `TradeRules` and allocator params defined
  in *other* files, so the method file's own bytes do not pin it. No git call: `lab run` already
  refused an uncommitted method file before recording those trials.
- `promote_method(conn, method_id, *, git_sha, today=None, directory=None, check_method_file=True) ->
  Promotion`: what `lab promote` runs; the CLI section above has its ordering, idempotence and
  refusals. `Promotion(prereg, path, trial_n, status, wrote_file, moved_status)` is what it did, for
  the caller to print. `check_method_file=False` skips `check_source` and exists for tests, which
  build `trials` rows with no method file behind them; nothing in the CLI passes it.
- `path_for(method_id, directory=None)`, `method_of(candidate_id)`, `repo_path(path)`,
  `committed_problem(path)`, `PREREG_DIR`, `FENCE`, `MARKER`.
- `gate_text()` is **built** from `backtest.dev.FAILURE_LABELS` and `store.DSR_LABEL` rather than
  retyped, so a file written next year cannot claim a condition the code stopped applying. What it
  states is the **dev** gate the variant passed to become `dev-eligible` (the five P7a D8 conditions
  plus `DSR >= 0.95` at N = every dev trial in the lab). It is *not* the gate the one test-window look
  is judged by: that is the five D8 conditions alone, because a pre-registered look has no selection
  among results to deflate, so DSR is recorded on the test trial and is not a condition. `render`
  says so in the file's prose, so a reader of the pre-registration cannot mistake one for the other.
- `test_window_label()` is `dates.next_session(dev.DEV_END)..data end` — the same start
  `lab.store.snapshot` publishes as `gate.testStart`. The end is deliberately not a date this step
  can know (the test-window store is built on first promotion and reaches the latest session
  available then), so the exact end is pinned afterwards by the `trials` row `lab test` writes.
- `store.best_dev_eligible(conn, method_id) -> sqlite3.Row | None` (a pure addition to `lab/store.py`):
  the method's best eligible dev trial by MAR, ties broken on the trial number, so the answer is
  exactly one row and the same row every time. Only `window = 'dev'`, only `eligible = 1`, and only a
  non-NULL `mar` — an eligible trial always has one, since "beats SPY TR" is among the conditions it
  passed, so a NULL here means a row that cannot be compared rather than a row that compares badly.
  `None` when the method has no eligible dev trial at all. `TRANSITIONS` already carried the
  `('dev-eligible', 'promoted')` edge; no schema or trigger changed.


### paper (P4)

`seer_engine.paper` is nightly paper trading. Every module but `store.py` is pure (no psycopg,
requests, yfinance, clock or randomness), `Decimal`-only for money, and covered by the purity tests.
Each night function steps exactly one session the way a runner's loop body does, and its tests prove
that looping it equals the runner (`run_backtest`, `run_book`, `buy_and_hold`) over hundreds of
synthetic sessions.

- **`paper.roster`**: the roster builder (D1, D4; roster-promotion-pipeline R2, D2, D3). Pure: no database, no clock, no I/O, and it imports nothing from `store`. A roster entry is a `strategies` row plus the live Python object the row names; this module is the only place that turns one into the other.
  - `BENCHMARK_ID = "SPY"`, `F4_ID = "F4-MOM12-N20-TREND"`, `F1_ID = "F1-SPY-SMA200-M"`, `FND_ID = "FND"` (phase 6), `BENCHMARK_OBJECT = "buy_and_hold"`. `Engine = Literal["bracket", "book", "benchmark"]` and `Status = Literal["active", "retired"]`, with `ENGINES` / `STATUSES` as the `CHECK`s in Python.
  - Errors, all `RosterError(LookupError)` and all naming **the strategy id and the offending value**: `UnknownObject` (`object_name` is not a `RESOLVER` key), `UnknownRules` (`rules_id` is not a `sim.rules` preset), `BadRosterRow` (bad engine or status, missing or surplus fields). None is ever swallowed — a row that cannot be built stops the whole build, because skipping it would leave an unfillable hole in that portfolio's equity curve.
  - `RosterEntry` (frozen dataclass), one paper portfolio: `id, name, sub, icon, is_champion, is_benchmark, sort` (the display fields of the row), `engine: Engine`, `rules: TradeRules | None`, `obj: Strategy | Allocator | None`, `object_name`, `params`, `registry_id: str | None`, `lookback: int`, `gate_note: str`, `gate_applicable: bool = True` (P6; false only for `C`), plus the lifecycle fields `status: Status = "active"` and `paper_end: date | None` (migration 006). `rules_id` is a property (`None` for the benchmark).
  - `Binding(obj, params=None, from_registry=False)`: what an `object_name` resolves to — the live object and where its params come from (`from_registry` means the row's `registry_id` names the `backtest.registry` candidate that supplies them, as F4 and F1 have always worked).
  - `RESOLVER: dict[str, Binding]` — **the one code-side table, and the extension point** (D2): `buy_and_hold` → no object, `STRATEGY_A`, `STRATEGY_C`, `FACTOR`, `TIMING` and (phase 6) `FUNDAMENTAL` → `Binding(obj=FUNDAMENTAL, params=FUNDAMENTAL_PARAMS)`. A database cannot hold an `Allocator`, and `eval`-ing an import path out of a row would make `strategies` a code-execution surface, so a row carries a stable *name* instead. Keys are forever: a stored spec names one, so renaming a key would move a live digest. Append only. `resolver_names() -> tuple[str, ...]` (sorted); `resolve(object_name) -> Binding` (`UnknownObject`, never a default and never `None`).
  - `rules_for(rules_id) -> TradeRules | None`: the `sim.rules` preset, the same object (so `is DESIGN_V0` holds); `None` → `None` (the benchmark trades under no rule set); an unknown id raises `UnknownRules`.
  - `Row` (Protocol): what `from_row` reads off a `strategies` row — `id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, object_name, registry_id, gate_note, gate_applicable, status, paper_end`, at the column types, nullables included. `paper.store.StrategyRow` satisfies it structurally, which is how `roster` stays pure. `RosterRow` is the same thing as a plain frozen dataclass, used by the seeds and the tests.
  - `from_row(row) -> RosterEntry`: one row, through `RESOLVER`. Validates engine and status against the `CHECK`s, resolves the object and the rules, requires a non-empty `gate_note`, and enforces the shape rules — a `benchmark` row carries no object, rules or `registry_id`; a `bracket` / `book` row needs a `rules_id` and an object; a `from_registry` object needs a `registry_id` (checked against `REGISTRY` for allocator and rules identity) and any other object must have `registry_id` NULL. `lookback` comes from the object (`obj.lookback` for bracket, `obj.lookback(params)` for book, 1 for the benchmark). There is no path that returns `None` or a half-understood entry.
  - `from_rows(rows) -> tuple[RosterEntry, ...]`: every row as an entry, sorted by `(sort, id)`, raising on the first row it cannot build and refusing duplicate ids. All or nothing — no row is ever dropped.
  - `SEED_ROWS: tuple[RosterRow, ...]`: the six rows `003_paper.sql`, `004_news_veto.sql`, `006_roster.sql` and `007_fnd.sql` write, as data; `tests/test_paper_roster.py` checks it equals a migrated database's `strategies` rows.
  - `ROSTER: tuple[RosterEntry, ...] = from_rows(SEED_ROWS)` (SPY, A, F4, F1, C, FND), `ROSTER_IDS`, `MAX_LOOKBACK_BARS = max(e.lookback for e in ROSTER)` (still 253, FACTOR's `factor_lookback` — FND's lookback is 20, the dollar-volume window, since a filing's availability is its `filed` date and not a bar count, so phase 6 does not widen the night's market window; a property of `SEED_ROWS`, not of whatever a live database holds). The compiled roster and the stored roster therefore travel the *same* builder, so the pinned digests prove the data path and not just a literal. `C` (P6): `C · News veto`, icon `gavel`, sort 5, engine `bracket`, rules `DESIGN_V0`, `obj = STRATEGY_C`, `params = STRATEGY_C_PARAMS`, gate note "Backtest gate: not applicable (LLM strategy, design §1 item 5)". `FND` (phase 6): `FND · Fundamentals`, "Top 20 by SEC filing factors, monthly", icon `book-open`, sort 6, engine `book`, rules `monthly-hold`, `object_name = "FUNDAMENTAL"`, `registry_id` NULL, `promoted_from = "M0005"`, and a `gate_note` that states the gate it **failed** (M0005's dev window only, fundamental coverage 0.3151: beats SPY TR +1.8% vs +351.4%, 15 closed trades against ≥ 100, DSR 0.006 against ≥ 0.95). `gate_applicable` stays true — the gate applies to it and it did not pass; saying so is the point.
  - `FUNDAMENTAL_PARAMS = FundamentalParams(rank="composite", top=20)` (phase 6): FND's parameters, written out in `roster.py` and deliberately **not** imported from `lab.methods.m0005_fundamental_factors`. That module's `source_sha` is frozen in `lab/lab.sqlite`, so editing it for a lab reason would silently re-digest a started paper strategy; the roster says what it runs, in its own file. `composite` is the a-priori equal-weight blend of the four factor families the method's sources name, chosen *before* the numbers — not `M0005-VAL`, which merely had the highest return of six failed dev-window trials and would be a pick made on the multiple-testing noise the lab's `trials` table exists to count. `tests/test_paper_fnd.py` pins it value-equal to the lab module's `COMPOSITE`, because a drift between them would make the promoted row's stored digest and the roster's recomputed digest differ and `store.check_digest` would refuse FND's second night with a `SpecMismatch`.
  - `active(entries=ROSTER) -> tuple[RosterEntry, ...]`: the entries still trading (`status == "active"`), in order. A retired entry keeps every row it ever wrote and its leaderboard place; it only stops trading.
  - `entry(strategy_id) -> RosterEntry`: the seeded roster entry; `KeyError` when it is not on the roster.
  - `rules_dict(rules: TradeRules) -> dict[str, str | None]`: every `TradeRules` field, in field order, as plain strings — minus a lever still at its pre-pin default (`sim.rules.is_pinned_default`), so a roster strategy that does not use a newly added lever keeps the spec digest already written to its live `strategies.params` row.
  - `spec(e) -> dict[str, Any]`: the frozen spec (C2 `params.spec`), JSON-ready, strings and nulls only: `id`, `engine`, `object` (the `RESOLVER` key), `object_id`, `registry_id`, `registry_digest`, `rules_id`, `rules`, `params`, `initial_idr`. `status`, `paper_end`, `gate_note` and `gate_applicable` are deliberately **not** in it: retiring a strategy or correcting a note must not move a live digest.
  - `spec_text(s) -> str`: the canonical text of a spec: JSON with sorted keys, no whitespace, ASCII only.
  - `spec_digest(s) -> str`: sha256 (hex) of `spec_text(s)` in UTF-8. The six digests are pinned in `tests/test_paper_roster.py`; the four P4 digests never change, and phase 6 moved none of the five that existed before `FND`.
  - `backtest_gate(e) -> dict[str, Any]`: C2 `params.backtest_gate`, `passed` false for every entry, with `e.gate_note`; for `C` also `"applicable": false` (the web shows "Not applicable" and counts it as not passed). Not part of the spec, so no digest depends on it.
  - `strategy_params(e) -> dict[str, Any]`: the whole `strategies.params` jsonb (`spec`, `digest`, `backtest_gate`), as `paper` writes it.
- **`paper.bracket`**:
  - `BracketNight(session, portfolio, events, snapshot)`: one settled session of a bracket strategy.
  - `settle_bracket(pf, session, bars, splits, last_bar_date) -> BracketNight`: settle `session` exactly like one `run_backtest` iteration (`apply_split` per applied split, `sim.step`, `close_unpriced` for symbols whose bars ended, snapshot replaced).
  - `decide_bracket(pf, strategy, params, history, members, data_date) -> SizingResult`: the pending orders for `next_session(data_date)`: `strategy.picks` on `history` cut at `data_date`, then `size_picks`.
- **`paper.book`**:
  - `BookNight(session, book, targets, splits, fills, trades, dividends, rejected, forced, snapshot)`: one settled session of a book strategy.
  - `decide_book(market, allocator, params, rules, data_date, held) -> tuple[tuple[Target, ...] | None, bool]`: the targets for `next_session(data_date)` (`None` when it is not a decision session) and whether the idle residual was appended. `backtest.book_runner._with_idle` is reused by import. Split-cadence rules (`rules.resize_cadence`) are a `ValueError`: a resize-only session needs the last rank session's basket and this function is stateless, so paper refuses loudly instead of silently re-ranking on the fast clock. Backtests and replays of split rules go through `run_book`, which carries that state, and are correct.
    - **The `MarketAware` branch** (phase 6): an allocator that satisfies `strategies.allocator.MarketAware` (it defines `prepare_market`) is decided through `targets_prepared(prepare_for(allocator, replace(market, history=history)), …)` — `run_book`'s own prepared dispatch, brought to the nightly decision — instead of `allocator.targets(history, …)`. It must be: such an allocator reads part of the `Market` that the `history` dict cannot carry, so the history-only path is not a worse answer but a fixed empty one (`FUNDAMENTAL` finds every symbol ineligible and returns `()`, forever, while every log line says it decided). The `Market` handed over carries the same `history` cut at `data_date`, so no bar dated after `data_date` is reachable on either path, and the panel needs no cut of its own: `panel.as_of(symbol, d)` answers from facts with `filed <= d` and `filed` **is** the no-look-ahead boundary (`005_fundamentals.sql`). The branch is keyed on the protocol and nothing else, so for every allocator without `prepare_market` the expression is byte-identical to before and the five pre-FND strategies replay bit for bit.
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
  - `expected_book` replays a `MarketAware` allocator through `run_rules(..., prepared=prepare_for(allocator, market))` (phase 6), exactly as `paper.book.decide_book` decided it; `prepared` stays `None` for every other allocator, so the five strategies that already have a paper clock replay byte for byte. The `market` is passed **uncut** here because `run_book` cuts per session itself and `FUNDAMENTAL` indexes its bars by date (`History.index_of`), never by last row — the property `allocatorkit.assert_no_lookahead` pins.
  - `compare(engine, stored, expected) -> tuple[Difference, ...]`: every stored value that differs, snapshots first, `paper_state` last. `split_exposure(engine, paper_start, records, splits)`: the applied splits that hit a held or pending symbol. `judge(head, stored, expected, splits) -> CheckResult`; `not_started(strategy_id)`; `broken(strategy_id, where, message, *, paper_start=None, last_session=None)`.
  - `failures(results, require_sessions) -> tuple[str, ...]`; `exit_code(results, require_sessions) -> int` (1 when `failures` is non-empty); `render(results) -> tuple[str, ...]`.
- **`paper.compare`** (roster-promotion-pipeline phase 3; pure — no database, no clock, no I/O, in `paper/roster.py`'s discipline, with `commands/compare.py` as its one impure edge). Not to be confused with `paper.replay.compare`, which diffs one strategy's stored night against its replay; this module ranks strategies against each other.
  - `MIN_COMMON_SESSIONS = 63` (a quarter of a 252-session year, three full rebalances of a `MONTHLY_HOLD` book), `MIN_RANKED = 2`, `SESSIONS_PER_YEAR = 252`, `YEAR_DAYS = 365.25`, `NA = "n/a"`, `Status = Literal["ranked", "insufficient"]`. `Window`, `Performance`, `Row`, `Comparison` (frozen dataclasses).
  - `compare(series: Mapping[str, Sequence[Any]], *, min_sessions=MIN_COMMON_SESSIONS) -> Comparison`: `series` maps a strategy id to its `(date, equity)` snapshots in date order, the equity anything `float()` accepts, so `equity_snapshots`' `Decimal` rows go straight in. Every id handed in comes back as exactly one `Row` — never dropped. Every ranked figure is computed over **one window shared by every ranked strategy** — the intersection of snapshot dates, not `[max(start), min(end)]`, so every strategy's returns come from the very same consecutive pairs of dates — and that window is returned in `Comparison.window` rather than implied. A strategy whose own curve is shorter than `min_sessions` never joins the intersection; among the rest, while the intersection is still short, the strategy whose removal leaves the longest intersection is dropped (ties: shortest own curve, then id) until it reaches `min_sessions` or fewer than `MIN_RANKED` remain. Everything left out is a `status="insufficient"` row carrying a `reason` — never a ranked row and never a silent omission.
  - The risk-adjusted figure is the **annualised Sharpe** of the session returns at a zero risk-free rate (`mean / stdev(ddof=1) * sqrt(SESSIONS_PER_YEAR)`): defined for any window with two returns and non-zero variance, scale-free so it does not reward merely having run longer, and — because the window is common by construction — estimated from the same number of observations for every ranked strategy. Sortino needs enough losing sessions to estimate a tail; Calmar/MAR divides by max drawdown, which is understated over a short window and exactly `0.0` for a curve that only rises. It is still noisy, so the window and session count travel with every figure.
  - **Inception-to-date is separate** (invariant 6): every row carries an `inception` block over the strategy's own whole curve, with its own start, end and session count. It is never ranked and never mixed into the common-window figures.
  - Fractions, not percents (`total_return`, `cagr`, `max_drawdown` are `0.123` for 12.3%), matching `web/lib/metrics.ts` and `backtest/metrics.py`; CAGR uses Actual/365.25. `render(c) -> tuple[str, ...]` is the table; `as_json(c) -> dict[str, Any]` is the shape the leaderboard's TypeScript port is pinned against.
- **`paper.store`** (impure; nothing commits, `paper` runs a night in one transaction):
  - `BENCHMARK_ID = "SPY"`, `MARKET_WINDOW_DAYS = 550` (the only window constant), `PRICE_QUANTUM`, `DIVIDEND_QUANTUM`. `StoreError(RuntimeError)`; `SpecMismatch(StoreError)`: a frozen strategy's stored digest differs from the code's.
  - Roster rows: `StrategyRow(id, name, sub, icon, engine, rules_id, is_champion, is_benchmark, sort, paper_start, params, status="active", paper_end=None, promoted_from=None, object_name=None, registry_id=None, gate_note=None, gate_applicable=True)` — structurally a `paper.roster.Row`, so `roster.from_rows(read_roster_rows(conn))` is the whole roster-from-data path and neither module imports the other. The migration 006 columns are nullable on rows that are not roster rows; `roster.from_row` validates them with a named error rather than defaulting them.
  - `read_strategies(conn)`, `read_strategy(conn, strategy_id)`; `read_roster_rows(conn)`: every row with `engine IS NOT NULL`, by `(sort, id)`. `engine` is the predicate because it is what the paper night dispatches on and what migration 003 set on exactly the roster's rows. **Retired rows are returned** (only `roster.active` drops them from a night), and a row with an `engine` but an unusable `object_name` is *not* filtered out here — `roster.from_row` raises `UnknownObject` for it, which is the point.
  - Lifecycle (006), the **only two writers** of `status` and `paper_end`: `retire(conn, strategy_id) -> date | None` sets `status = 'retired'` and `paper_end` to `paper_state.last_session` — the last session actually traded, NULL when the strategy never started — and returns it. Re-retiring is a deliberate no-op that returns the stored `paper_end`, so an interrupted swap can simply be re-run; a missing row is a `StoreError`. It reads `paper_state` for the date and nothing else: no `equity_snapshots`, `orders`, `book_*` or `paper_state` row is written or deleted, so a retired strategy keeps its whole track record and its leaderboard place. `set_paper_end(conn, strategy_id, paper_end)` is the repair for a retirement taken by hand SQL: only a retired row whose `paper_end` is still NULL is written, and an active row, a missing row or one already stamped is a `StoreError`. Neither commits — the caller's transaction decides, so a retirement and its replacement's INSERT land together and the board never shows two rosters.
  - `freeze_spec(conn, strategy_id, *, spec, digest, backtest_gate, paper_start)` (writes once); `check_digest(row, digest)` (raises `SpecMismatch`).
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

## Migration 006 (`db/migrations/006_roster.sql`, roster-promotion-pipeline phase 1)

Additive only, to 003's discipline: every new column is nullable or defaulted, nothing is dropped,
no `CHECK` is narrowed, migrations 001–005 are untouched. Written by the engine; web reads `status`
and `paper_end` from the leaderboard.

- Lifecycle: `strategies` gains `status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired'))` (a retired row keeps its history and stops trading), `paper_end date` (the last session actually traded; NULL while active) and `promoted_from text` (the lab `methods.id` the row came from, when it was promoted).
- Definition, read by `paper.roster.from_row`: `object_name text` (a `paper.roster.RESOLVER` key), `registry_id text` (a `backtest.registry` id for book entries, else NULL), `gate_note text` (the display fact the go-live checklist reads) and `gate_applicable boolean NOT NULL DEFAULT true`.
- Data: the five rows 003 and 004 inserted are backfilled with the four definition values, byte-for-byte `paper/roster.py`'s `SEED_ROWS`; `tests/test_paper_roster.py` checks that equality against a migrated database. The five spec digests do not move — none of these columns is in the spec.
- Why a name and not an import path: a row cannot hold an `Allocator`, and `eval`-ing an import path out of the table would make `strategies` a code-execution surface. A name the resolver does not know is a hard error when the roster is built, never a silently dropped portfolio.
- Replacing a horseman is therefore a transaction, not a code edit: INSERT the new row, set the old row's `status` to `retired` and its `paper_end` (`paper/store.py`'s `retire` is the engine-side writer of that transaction). Retirement never deletes `equity_snapshots`, `orders`, `book_*` or `paper_state` rows and never clears `paper_start`, so the leaderboard keeps the whole track record and can say the row is retired rather than hiding it.

## Migration 007 (`db/migrations/007_fnd.sql`, roster-promotion-pipeline phase 6)

Additive only, in `004_news_veto.sql`'s shape: one roster display row, no column added, dropped or
narrowed, and no existing row touched. It requires 006, whose columns it names.

- Data: the `FND` roster row (`FND · Fundamentals`, "Top 20 by SEC filing factors, monthly", icon `book-open`, sort 6, engine `book`, rules `monthly-hold`, `object_name = 'FUNDAMENTAL'`, `registry_id` NULL, `gate_applicable` true, `promoted_from = 'M0005'`, not champion, not benchmark), as an upsert. Every value is byte-for-byte `paper/roster.py`'s `FND` seed row, which is what `tests/test_paper_roster.py`'s migration-equality test compares.
- **Why a migration when phase 5's `promote` writes the same row**: the two write it to different databases. `promote --method M0005 --candidate M0005-ALL --id FND --lab-status-stays` wrote it to the live Neon instance, whose roster is already data; this file writes it to every database brought up *from* migrations — CI's throwaway schema, a fresh local train database, a rebuilt Neon — so `paper`'s `plan_night` finds a `strategies` row for every roster entry.
- **No frozen spec, no `paper_start`, no paper clock** is written here: `paper` writes them on the first night through `store.freeze_spec`, exactly as it did for SPY, A, F4, F1 and C. A row with no `paper_start` is a strategy that starts on the next night — phase 2's path, and FND is its first user.
- **The definition columns are not optional**: `from_row` reads them, and a NULL `object_name` raises `UnknownObject` while a missing `gate_note` raises `BadRosterRow` — either of which stops the whole paper night. So the file writes all four.
- `status` is deliberately **not named**, so the `ON CONFLICT` branch cannot resurrect a strategy someone has since retired (006 defaults it to `active`, which is what FND wants). `promoted_from` is written on INSERT and never on UPDATE, so re-running the file can never clobber what `promote` wrote.

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
- `commands.promote` (phase 5) imports `config`, `dates`, `db`, `lab.store`, `lab.method` (`discover`, inside the function), `paper.roster`, `paper.store`, `sim.rules` (`TradeRules`) and `psycopg.types.json.Jsonb`. It never imports `backtest.registry` (D1), and it is the only module that holds a Neon connection and a lab SQLite connection at the same time — sequentially, never in one transaction.
- `lab.prereg` (build-promotion-path phase 3) imports `config`, `lab.store` and `lab.method` (`METHOD_ID`, `config_digest`, `source_sha`), plus `sqlite3` from the standard library. `backtest.dev` (`FAILURE_LABELS`, `DEV_END`), `dates` (`next_session`), `lab.method.discover` and `commands.backtest_dev.registry_problem` — the same `git status` check `lab run` makes on a method file — are imported *inside* the functions that need them, so importing `lab.prereg` does not drag in `backtest`. `commands.lab`'s `promote` handler imports `lab.prereg` and `lab.runner.git_head` inside the function. It never touches Neon: the pre-registration is a lab-side artefact only.
- `paper.compare` (phase 3) imports nothing from the package at all — only the standard library — which is what keeps it portable to the leaderboard's TypeScript port. `commands.compare` imports `db`, `paper.compare` and `psycopg`, and reads one table.
- `paper.book` and `paper.replay` (phase 6) also import `MarketAware` and `prepare_for` from `strategies.allocator`; `paper.roster` imports `strategies.f_fundamental` (`FUNDAMENTAL`, `FundamentalParams`) and still never imports `lab.methods.*` — the lab must not become an input to a paper spec digest.
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
2. `entries = roster.from_rows(store.read_roster_rows(conn))`: the roster is the database's, not the compiled `ROSTER`, and an unresolvable row stops the night here by name. Then `plan_night(entries, rows, states, rd)` reads every strategy's `store.read_paper_state`, checks each **active** entry's frozen digest (`store.check_digest`) and returns a `NightPlan(start, step, retired)` — the entries that start tonight, the `(entry, state)` pairs that step, and a `Retired(entry, paper_end, stamp)` per `status = 'retired'` row. `NightPlan.empty()` (nothing starts, nothing steps, no retirement left to stamp): exit 0.
3. `runs.start_paper` (its own short transaction). Then, in one transaction (`_night`): first every retirement whose `paper_end` is still NULL is stamped (`store.set_paper_end`), the only write a retired strategy ever gets; then, only when something actually starts or steps, `_trade` loads the windowed market (`store.load_market_window(conn, since)` with `since = store.market_window_since(earliest)`, 550 calendar days before the earliest session to step), the applied splits per session (`store.applied_splits_on`) and the dividends (`store.dividends_between`). Each session S is computed on `night_view(market, S, later_factors(...))`: the market as it stood on S's night, later bars and FX hidden, splits executed after S undone on bars and dividends.
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

`paper_check` re-runs `backtest.book_runner.run_rules` (A, F4, F1 and, since phase 6, FND — the
latter through `run_rules(..., prepared=…)`, the branch `decide_book` took) and the `buy_and_hold` rules
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
engine/.venv/bin/python -m seer_engine research_store --verify   # no network: sha256s, window guard, data checks, fingerprint
engine/.venv/bin/python -m seer_engine backtest_dev              # every REGISTRY candidate, dev window only (~1 min)
```

The test-window store is a separate build, done on the first promotion and never before (design S3):

```
engine/.venv/bin/python -m seer_engine research_store --test-window                          # engine/.research-test, through the latest session
engine/.venv/bin/python -m seer_engine research_store --test-window --window-end 2026-10-02  # resume an interrupted build to the same end
engine/.venv/bin/python -m seer_engine research_store --test-window --verify                 # its own window, its own fingerprint
```

Neither store can be used in the other's place: `--test-window` against `engine/.research` (or a
dev invocation against `engine/.research-test`) exits 2 — as does any build whose target already
holds a store declaring the other window, wherever on the machine that store lives — and
`load_store` refuses the mismatch before it reads a data file.

Spending the one look on that store is `lab test` (build-promotion-path phase 4), after the method
has been pre-registered by `lab promote` and that file committed **and pushed**:

```
engine/.venv/bin/python -m seer_engine lab test M0007-RESID --dry-run  # loads nothing, runs nothing, spends nothing
engine/.venv/bin/python -m seer_engine lab test M0007-RESID            # the one counted look; test-passed or test-failed, both final
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
- **The dev window is law.** Every dev entry point raises `backtest.dev.DevWindowError` for a session after 2015-10-16, and `research.load_store` rejects a store holding a row after the window it was asked for — `DEV_WINDOW` unless the caller says otherwise, and `lab run` and `backtest_dev` never say otherwise. Never add a flag, a default or a store that gets past either guard. P7b runs the pre-registered finalists on the test window under its own handover.
- **A dev store and a test store are never interchangeable** (build-promotion-path phase 2; the build guard is content-based since research-store-clobber-guard). They live in different directories (`engine/.research` vs `engine/.research-test`) and a store declares which it is in its manifest, so `load_store` refuses the wrong one *before* reading any data file, and `research_store` refuses to build or verify one window against the other's directory even when `--store` names it explicitly — the **build** check reads the target's own `manifest.json` (`research.declared_window`), not the `--store` path, so it refuses a wrong-window store in **any** checkout or worktree and not merely this one, and falls through only when the directory holds no readable store at all. Do not "fix" a mismatch by pointing `--store` or `SEER_RESEARCH_STORE` somewhere else: the test store holds the same history **and** every session after `DEV_END`, so running the dev pipeline on it would spend unseen data silently.
- **The dev store's manifest is nine keys, and a dev build must never write a tenth.** `window_name` / `window_start` / `window_end` are `OPTIONAL_MANIFEST_KEYS` and **absent means the dev window** — never a `window_name: "dev"`. `engine/.research` was sealed with exactly `MANIFEST_KEYS`; requiring a window key, or writing one on a dev build, would reject or re-seal the store whose fingerprint `/sync-research-store` keys on and every recorded lab trial was measured against.
- **The test store starts in 1993, not in 2015.** `TEST_WINDOW_START` (2015-10-19) is the first session the test window *trades*; `STORE_START` is where its data begins, the same as the dev store's. A candidate first traded on 2015-10-19 still needs its `lookback` bars before that date, and the lab gets exactly one append-only look per configuration, so a test store opening at its own window start would make that one look permanently and unrecoverably wrong.
- **Build the test store on the first promotion, never before** (design S3), and pin `--window-end` when resuming an interrupted build. Without the pin the window silently moves to whatever the latest completed session is that day, which changes what a recorded test trial meant.
- **The registry is append-only.** `tests/test_registry.py` pins every `(id, digest)`. A new candidate is appended and pinned in its own commit, before its dev run (D6). Editing an entry after its result exists is not allowed, even to fix a "typo": append a new id instead, and it counts as a trial.
- `backtest_dev` refuses a full run (exit 2) while `backtest/registry.py` has uncommitted changes. `--only` skips that check and writes nothing; its numbers are a smoke test, never a result.
- **Paper state stays in the units it was sized in.** Never rebuild a mark or a price of a live paper order or position from `bars`: `nightly` rewrites history backwards on a split, and `apply_split` / `apply_book_split` would then rescale it twice. Marks are stored (`orders.mark`, `book_positions.mark`).
- **A roster entry is frozen.** `paper` fails the night (`store.SpecMismatch`, rolled back, `runs.paper_status = failed`) when a started strategy's stored spec digest differs from `paper/roster.py`'s. Change a strategy by adding a new id (its own `paper_start`), never by editing a started one or deleting its rows.
- **`RESOLVER` keys are forever, and an unknown one stops the build.** A stored spec names its `object_name`, so renaming or removing a key a started strategy still names would move a live digest. Append only. And `roster.from_row` raises `UnknownObject` rather than skipping a row it cannot resolve: a dropped portfolio is a hole in a track record that nothing later can fill, so the whole build fails loudly instead.
- **`promote` never appends to `backtest/registry.py`** (D1). The registry is the P7a dev-run candidate set, fixed before that run and digest-pinned; a promoted method reaches the roster through `paper.roster.RESOLVER` instead, so the lab's multiple-testing count stays honest. Add the `Binding` to `RESOLVER`, never a `REGISTRY` entry.
- **A promotion leaves `paper_start` NULL on purpose.** `promote` writes the row; the next paper night freezes the spec and starts the clock. Never back-date a promoted entry's `paper_start`, and never re-point a started id at another algorithm — `promote` raises `AlreadyStarted` for exactly that. Promote under a new id and `--retire` the old one in the same command, so the swap is one transaction.
- **The roster write and the lab note cannot be one transaction** (Neon and SQLite). The roster commits first; if the lab note is then lost, re-run the identical `promote` command — both halves are idempotent. Never reorder them: the lab is append-only, so a note for a promotion that did not happen cannot be withdrawn.
- **A pre-registration is written once and never rewritten** (design §3). `lab promote` leaves an existing `docs/lab/prereg/MNNNN.md` byte-for-byte alone, date line included, and raises rather than re-pointing it at a better variant found later; if the first choice is genuinely wrong, that is a new method with its own dev trials. And the file must be committed **and pushed before** `lab test`: `prereg.require_committed` refuses on a file git does not track or that has staged or unstaged changes, which is the whole point of putting the record in git.
- **The gate named in a pre-registration is the dev gate, not the test gate.** `prereg.gate_text` states what the variant passed to become `dev-eligible` (the five P7a D8 conditions plus `DSR >= 0.95` at N = every dev trial). The one test-window look is judged by the five D8 conditions alone; DSR is recorded on the test trial and is not a condition, because a pre-registered look has no selection among results to deflate and a look is not a search.
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

The roster-as-data sections (migration 006, `paper.roster`'s `RESOLVER`, `Binding`, `Row` /
`RosterRow`, `from_row` / `from_rows`, `SEED_ROWS`, `active` and the `RosterError` family, and
`paper.store.read_roster_rows` with the widened `StrategyRow`) were added on 2026-10-05 as phase 1
of `ROSTER_PROMOTION_PIPELINE_PLAN.md`. This phase is pure plumbing: `ROSTER` is now
`from_rows(SEED_ROWS)` instead of a hand-written tuple, the five spec digests are byte-identical
and still pinned in `tests/test_paper_roster.py`, and `paper`, `paper_check` and `veto` continued to
read the compiled `ROSTER`.

Phase 2 landed on 2026-10-05 (P1-ENG-J5XD): `paper` and `paper_check` now build their entries from
the stored rows, `commands/paper.py` gains `Retired` and a third `NightPlan` leg (a retired entry is
a deliberate skip, never an error, and never the code path an unresolvable row takes), `_night`
splits into `_night` (which settles retirements, and loads no market window when nothing trades) and
`_trade` (never called with nothing to do), and `paper/store.py` gains `retire` and `set_paper_end`
as the only writers of the lifecycle columns.

Phase 5 landed on 2026-10-05 (P1-ENG-Z8MR): the `promote` command (`commands/promote.py`) and
`lab.store.record_promotion` / `PROMOTION_MARKER`. It is the lab → roster bridge and the only
writer that creates a roster entry: one `strategies` INSERT (`status='active'`, `promoted_from`,
`registry_id` NULL, the full contract-C2 `params`, no `paper_start`), proved by a
`roster.from_row` round trip inside the same transaction, optionally atomic with phase 2's
`store.retire`; and one append-only, idempotent lab note that moves the method's status only along
the existing `('test-passed','paper')` edge. `backtest/registry.py` is untouched by design
(Decisions D1), and the roster's admission rule is deliberately not the lab's gate (Decisions D5),
which is what `--lab-status-stays` makes explicit.

Phase 3 landed on 2026-10-05: `paper/compare.py` (pure) and the read-only `compare` command. It
replaced "rank by whatever each strategy's own span happened to return" with a comparison over the
window every ranked strategy shares, stated rather than implied, with inception-to-date kept
separate and never ranked (invariant 6). Its readme sections were written up with phase 6, because
phase 3 landed while its peers were committing concurrently.

Phase 6 landed on 2026-10-05 (P1-ENG-H3WF), the last of the set: `FND · Fundamentals` joined the
roster as its sixth entry (migration 007, `roster.FND_ID` / `FUNDAMENTAL_PARAMS` / the `FUNDAMENTAL`
`RESOLVER` binding, `tests/test_paper_fnd.py`), put on the live board by phase 5's `promote` — the
first promotion through the new lab → roster path rather than around it. It carries a `gate_note`
that says it **failed** its M0005 dev-window gate, which is the honest statement: a backtest gate has
never been this roster's admission criterion (Decisions D5) and it binds the real-money decision, not
paper membership. Because FND is the roster's first `MarketAware` object, `paper/book.py:decide_book`
and `paper/replay.py:expected_book` now dispatch such an allocator through `prepare_for` +
`targets_prepared`, so it actually reads `market.fundamentals`; before this a `MarketAware` allocator
on the roster would have held cash forever while every log line said it had decided. The branch is
keyed on the protocol alone, so for every allocator that is not `MarketAware` the expression is
byte-identical to before: the five pre-existing spec digests are unchanged, the five strategies with
a paper clock replay bit for bit, and `MAX_LOOKBACK_BARS` is still 253.

Phase 3 of `BUILD_PROMOTION_PATH_PLAN.md` landed on 2026-10-06 (P1-ENG-AZ81): `lab/prereg.py`, the
committed pre-registration format it owns (`docs/lab/prereg/MNNNN.md`, with
`docs/lab/prereg/README.md` stating that format for a human reader), `lab.store.best_dev_eligible`
and the `lab promote` subcommand. It supplies the half of the one-look rule a database cannot
enforce: SQLite counts the looks (`UNIQUE(config_digest, window)` and the append-only triggers), and
the committed file names which configuration each look is spent on, before any test number exists.
All three source edits are pure additions (90 insertions, 0 deletions) and `lab run` is
behaviourally unchanged. Tests: `tests/test_lab_prereg.py` (25) and one case in
`tests/test_lab_store.py`.

Phase 4 of `BUILD_PROMOTION_PATH_PLAN.md` landed on 2026-10-06 (P1-ENG-YJDW), the last of the set:
the `lab test` subcommand and the test-window half of `lab/runner.py` (`Tested`,
`resolve_candidate`, `preflight_test`, `test_trial_row`, `run_test`). `runner.py` is appended to and
nothing above its `lab run` half changed, so `lab run` is behaviourally unchanged. It closes the
path the first three phases built: phase 2's second store supplies the data, phase 3's committed
pre-registration says which configuration the look is spent on, and this phase spends it — one
`window = 'test'` trial row that does not move the lab's N, a verdict of `test-passed` or
`test-failed` (both final), and on a pass the exact `promote` line that hands the method to phase
5's existing roster path. The one-look rule is enforced in two places on purpose: readably in
`preflight_test`, and in the database by `UNIQUE(config_digest, window)` — the second is the one
that holds against a parallel session, which is why `run_test` re-runs the preflight inside its
write lock. The mechanism is built and **nothing has been spent**: `test-window looks used` reads 0
against the real lab. Tests: `tests/test_lab_test_window.py`, with the fixtures in
`tests/labkit.py`.
