# Code Analysis: Strategy B, the ML cross-sectional ranker under walk-forward (roadmap P6a)

**Type:** Feature Implementation
**Date:** 2026-10-03 18:08 WIB
**Session ID:** 20261003-180843-B6R1
**Plan:** `STRATEGY_B_RANKER_PLAN.md` (7 phases)
**Worktree:** `/home/miftah/.worktrees/seer/strategy-b-ranker`, branch `feature/strategy-b-ranker` (base `origin/main` @ `0e91d8a`)

---

## User Input

### Original User Request

```
/analyze docs/handover/2026-10-03-strategy-b-ranker.md
```

The whole specification is the handover file, committed at `0e91d8a`. It is copied into this
worktree unchanged, so it is not repeated here. Read all of it. Its §3 tables ("Law" and "Decided
in this handover") are binding. §6 is the acceptance list. §7 holds the open questions, which the
plan index settles under **Decisions**.

### User-Provided Context

These parts of the handover are quoted verbatim because they decide scope:

> **This handover takes (a)** [Strategy B] … It is research-only and read-only, and it touches no
> trade rule.

> **B must be trained on a net-of-cost target and must be allowed to pass on a night.** Zero picks
> is valid (design §5).

> | One round only | B runs **once** on this data. If it fails, B is not reworked on this data either. The report and ROADMAP say so |

> These are recommendations, and each can be overturned with a one-line change before planning. They
> are fixed **now, before anyone sees a B result**, which is the point.

### User-Provided Files
- `docs/handover/2026-10-03-strategy-b-ranker.md`

### Requirement IDs

These come from the handover's §6 acceptance list, in its order.

| ID | What the user asked for |
|---|---|
| R1 | Labels. Synthetic-bar tests cover every label path, net of 0.1% per side. The vectorized labeler agrees with a one-order `sim` run on a seeded sample. The label purge holds: changing a bar after `tune_end(Y)` leaves fold Y's training set unchanged |
| R2 | Features. Each feature is hand-computed on a synthetic series. The rolling and single-window paths are bit-identical. Ranks use that date's candidates only, with ties averaged. SPY features read SPY's bars through `data_date` only |
| R3 | P4 identity and no look-ahead, for B and B-linear, with a fixed model. That includes SPY bars dated ≥ S |
| R4 | Walk-forward. The folds are exactly P3b's. Each fold trains only on labels resolved by its `tune_end`. The segments chain into one portfolio, and brackets survive the year boundary. `backtest_wf`'s A2 report re-renders byte-identically |
| R5 | Determinism. The same inputs give `==` results and byte-identical files. The gated model's predictions are bit-identical across runs and thread counts, or the pre-registered switch to B-linear takes effect and the report says so |
| R6 | Purity. The new modules pass the globbing purity test |
| R7 | One real walk-forward run on Neon, with the report committed. It holds the fold summaries, the B and B-linear curves against A2 and both SPY curves, a year-by-year table, the diagnostics (passed-night share and calibration included), "seen before", the survivorship note and a one-sentence P6a verdict |
| R8 | Freeze or stop. **On a pass:** the last fold's model becomes a committed artifact, a code constant names the report, the cutoff and the SHA-256, and a test ties the three together. **On a fail:** ROADMAP records that B's one round failed and P4 stays blocked, and the report lists the owner's options |
| R9 | `engine/package_readme.md` documents B, the labeler, the features, the command and its performance. The suite is green with 0 skipped, and CI is green with scikit-learn installed |

---

## Detailed Requirements Understanding

**Problem.** Seer needs a second strategy. It must pass the fixed go-live gate (design §1) over the
same anchored yearly walk-forward that A2 failed (2018-01-02 → data end). Strategy B is a learned
ranker:
- **Candidates:** A's eligible set (A's liquidity floor, A's bracket).
- **Features:** 15 generic per-symbol features, each a cross-sectional rank, plus 3 raw SPY
  features.
- **Target:** the realized **net** return per dollar of that one bracket order, simulated alone.
- **Model:** a fixed-hyperparameter gradient-boosted tree regressor, retrained once per fold on
  purged labels.
- **Picks:** every candidate with a positive predicted net return, best first. On some nights there
  are none.

Ridge regression (B-linear) runs alongside as information.

**Success criteria.** All of R1–R9. The verdict is a result either way: a failed gate is a valid
outcome of this work, not a defect.

**Key considerations.**
- **Nothing A2 uses may change:**
  - `strategies/a.py` and `a2.py`;
  - `backtest/walkforward.py`, `wf_report.py`, `runner.py`, `metrics.py`, `tuning.py`;
  - `commands/backtest_wf.py`;
  - `sim/*`.

  B reuses their public functions. Then `backtest_wf`'s output stays byte-identical by
  construction, and the real-run phase checks it with `cmp`.
- **Labels are training targets, not money.** They are floats, computed on float bar arrays. The
  brackets are still the exact 4-dp Decimal brackets `sim` would get, converted to float before
  the labeler sees them.
- **The labeler must follow `sim`'s rules exactly.** The rules are set by NYSE sessions, not by
  bars:
  - the fill happens only on the order session (`next_session(data_date)`), and only when that
    session has a bar with `low < limit`;
  - `days_held` grows on sessions without a bar;
  - the time stop exits at the first bar open once `days_held ≥ 5`;
  - when a symbol has no later bar at all, the runner force-closes it at the last close.
- **Bit-identity.**
  - New window functions follow `indicators.py`'s rule: elementwise operations plus an explicit
    column loop.
  - The ridge fit uses a fixed-block `einsum(optimize=False)` accumulation, and its prediction is
    an explicit loop over the feature columns. Results then never depend on BLAS threading or on
    batch size.
  - The tree model's predictions are per-row sums over its trees in a fixed order, so they do not
    depend on batch size either.
- **Purity.** `test_strategy_purity.py` globs `strategies/*.py` and `backtest/*.py`:
  - sources must not use `logging`, `time`, `random`, `.random` or `open()`;
  - a fresh import must not load psycopg, requests, yfinance or `seer_engine.bars`.

  Verified on 2026-10-03: importing scikit-learn 1.9.1 loads `logging` and `urllib.parse`
  indirectly, which is allowed, and none of the four forbidden modules. Permutation importance
  would need `np.random`, which the AST check forbids. So feature importance uses the trees'
  split gain.
- **Tree determinism, verified 2026-10-03** (scratch venv: sklearn 1.9.1, numpy 2.4.6, 24-core
  WSL2):
  - `HistGradientBoostingRegressor` with the handover's fixed hyperparameters, on 1.2M × 18
    synthetic rows, gave **bit-identical predictions** under `OMP_NUM_THREADS` = 1, 7 and 24
    (sha256 `5bfc3d92…`). The 300k-row run matched across 1, 2 and the default thread count.
  - Fit time at 1.2M rows: 9.7 s on one thread, 3.4 s on the default 24.
  - `pickle.dumps(model, protocol=5)` is byte-identical across two fits of the same data.
  - Predicting one row at a time gives the same floats as predicting a batch.

**Assumptions** (each one is recorded as a Decision in the plan index):
- Labels for rows that are still open at the data end are unresolved and excluded.
- The ridge intercept is not penalized.
- The stdev of returns uses ddof 0.
- "Returns over k sessions" means k bars back within the window.
- A candidate needs all 15 raw features finite.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/handover/2026-10-03-strategy-b-ranker.md`
- `docs/backtests/2026-10-02-strategy-a2-walkforward.md` (and its `-equity.csv`)
- `docs/handover/2026-10-03-strategy-a-rework.md`
- `docs/plans/2026-10-03-seer-design.md` (§1, §4, §5)
- `engine/package_readme.md`
- `docs/ROADMAP.md`

### Discovered Related Files
- `engine/src/seer_engine/strategies/{base,indicators,a,a2,__init__}.py`
- `engine/src/seer_engine/backtest/{runner,walkforward,wf_report,metrics,tuning,market,benchmark,report,io}.py`
- `engine/src/seer_engine/commands/{backtest_wf,backtest}.py`, `cli.py` (finds commands by module name)
- `engine/src/seer_engine/sim/{lifecycle,model,sizing}.py`
- `engine/tests/{stratkit,simkit}.py`, `test_strategy_purity.py`, `test_strategy_a2_frozen.py`, `test_backtest_walkforward.py`, `test_backtest_runner.py`
- `engine/pyproject.toml`, `.github/workflows/engine-ci.yml` (installs `engine[dev]`)

---

## Current Dataflow

### Entry point: `python -m seer_engine backtest_wf` (`commands/backtest_wf.py`)

1. `run(args)`:
   - opens the DB;
   - `backtest_io.load_market(conn, cache_dir, refresh)` returns `(Market, bars_rows)`. Bars come
     from a pickle cache keyed by `bars-<max date>-<rows>.pkl`;
   - `read_dividends`;
   - `resolve(market, is_start, first_year, end)`. Its `end` defaults to the last SPY bar, and it
     raises `BacktestWfError`, which exits 2.
2. `execute(market, bars_rows, dividends, is_start, first_year, end)`:
   - `folds = walkforward.folds(is_start, first_year, end)` (`walkforward.py:155`). It gives one
     `Fold(year, tune_start=is_start, tune_end=prev_session(trade_start), trade_start, trade_end)`
     per year from 2018;
   - `prepared = STRATEGY_A2.prepare(market.history)`;
   - `tune_all(...)` runs one `run_backtest` per combination (324), sliced per fold by
     `metrics_through`;
   - `run_walk_forward(... variant)` calls `walkforward.walk_forward`, which runs `select_fold`
     per fold and builds `schedule(folds, selections)`. That is a `ParamsSchedule` of
     `(trade_start, params)`, traded by one `run_backtest` over `[folds[0].trade_start,
     folds[-1].trade_end]`;
   - `spy_curves(market.spy(), trade_start, trade_end, combined.run.initial_cash, dividends)`;
   - `survivorship`, `never_fetched_members`, `gate_p3b`, and the result is a `WalkForwardReport`.
3. `backtest_io.write_wf_report(out, report)` writes 5 files, all rendered before any is written.

### Processing chain inside `run_backtest` (`backtest/runner.py:131`)

For each NYSE session S in `[start, end]`:
1. `members = market.membership.members_on(data_date)`, where `data_date = prev_session(S)`.
2. `session_params = schedule.at(S)`.
3. Picks:
   - with `prepared`: `picks_prepared(prepared, members, data_date, params)`;
   - without it: `picks({s: h.upto(data_date)}, members, data_date, params)`.
4. `size_picks(pf, picks, S)`. Each pick gets `equity ÷ 4` as its budget, in whole shares, and
   any rejection is counted.
5. `step(pf, S, market.bars_on(S, held))`.
6. Every open order whose symbol's `last_bar_date < S` is closed by
   `close_unpriced(pf, gone)`: exit at the mark (the last close), reason `time`, `forced=True`,
   exit date S.

The result is a `RunResult(strategy_id, params, start, end, usd_idr, initial_cash, snapshots, events, closed, open_at_end, rejections)`.

### Fill and exit rules (`sim/lifecycle.py:step`)

**Exits.** For an open order on a session with a bar, the checks run in this order:
1. `days_held ≥ 5`: exit at the open, reason `time`.
2. `open ≤ sl`: exit at the open, reason `gap`.
3. `open ≥ tp`: exit at the open, reason `tp`.
4. `low ≤ sl`: exit at sl, reason `sl`, with `days_held + 1`.
5. `high > tp`: exit at tp, reason `tp`.
6. Otherwise `days_held + 1` and the order is marked at the close.

An open order on a session with no bar gets `days_held + 1` and no event.

**Pending orders.** A pending order fills only on its own session, and only if that session has a
bar with `low < limit`. The fill price is `q(min(open, limit))`, `days_held = 1`, and the order is
not checked for exits on its fill day. Otherwise it expires.

**Money.**
- `buy_cost = q(price × shares × 1.001)`.
- `sell_proceeds = q(price × shares × 0.999)`.
- `pnl = proceeds − buy_cost`.

So with a fill on session S1 and bars on every session, the time stop exits at the open of S6.

### Strategy A's eligibility and bracket (`strategies/a.py`)

- **Eligible:** a bar dated `data_date` and `LOOKBACK = 200` bars through it. Every indicator
  reads only the last 200 bars.
- **Liquidity:** `dollar_volume` is `mean_dollar_volume_window(close, volume, 20)`, and the
  candidate needs it `> 20_000_000.0` (strict).
- **Bracket:** `_bracket(f: Features, params: AParams) -> Pick | None` (`a.py:178`):
  - `last = to_decimal(f.close)`, `atr = to_decimal(f.atr)`;
  - `limit = q(last − limit_atr·atr)`, `tp = q(limit + tp_atr·atr)`, `sl = q(limit − sl_atr·atr)`;
  - it returns None when `last ≤ 0`, `limit ≤ 0`, `sl ≤ 0`, `sl ≥ limit` or `tp ≤ limit`.
- **Design values:** `DESIGN_PARAMS` (`a.py:94`) is limit 0.5, TP 1.0, SL 1.5.
- **`prepare_a`** builds columnar rows ordered by (date, symbol): `symbols`, `dates`, `sym`,
  `close`, `sma`, `rsi`, `atr`, `dollar_volume`. Each column comes from
  `indicators.rolling(fn, ..., window=200)`, which is bit-identical to the single-window call.

### Exit Points
- Report files go under `docs/backtests/`. Logs go to stderr. Nothing writes to the DB.

---

## Key Data Structures

### `History` (`strategies/base.py:31`)
`symbol`, `dates` (datetime64[D]), `open/high/low/close/volume` (float64). It provides
`upto(d)`, `index_of(d)` and `last_date()`.

### `Market` (`backtest/market.py:94`)
- Fields: `history: Mapping[str, History]` (SPY included), `membership: Membership`, and
  `fx`.
- Methods: `bar(s, d)` returns a Decimal `Bar`. Also `bars_on`, `last_bar_date`, `usd_idr_on` and
  `spy()`.

### `ParamsSchedule` (`backtest/runner.py:74`)
`segments: tuple[(first_session, params), ...]`. Its params may be any object except another
schedule. `at(S)` bisects. `RunResult.params` is the schedule, so params equality is what
`wf_report._validate` relies on.

### `Fold`, `WalkForward`, `Diagnostics` (`backtest/walkforward.py:68–100`)
`Fold(year, tune_start, tune_end, trade_start, trade_end)`.

`diagnostics(run)` returns P/L by exit reason and by exit year, small trades (< 3 shares), gross
P/L, costs and cost drag.

`window_metrics(run, start)` and `curve_window_metrics(curve, start)` are for "seen before".

### `Selection`, `Verdict`, `GridRow` (`backtest/tuning.py`)
`Verdict(passed, checks: tuple[CheckItem, ...], sentence)`.

`metrics.checklist(m, spy_return)[2:5]` holds the three gate items: beats SPY, PF ≥ 1.3, DD ≤ 15%.

### `Pick` (`sim/sizing.py`)
`Pick(symbol, last, limit, tp, sl)`, every price a 4-dp `Decimal`.

---

## Dependencies

- **Runtime:** numpy ≥ 2, pandas, psycopg (io only), pandas_market_calendars (`dates`).
  **New:** scikit-learn, pinned `>=1.9,<1.10`. It brings threadpoolctl, joblib and scipy.
- **Environment:**
  - `SEER_ENV_FILE` points at the main checkout's `.env.local` for a real run from the worktree.
  - `PG_TEST_URL` is needed for a test run with 0 skipped.
- **Data:** the `bars` table has 1,817,429 rows, 663 symbols, 2015-01-02 → 2026-10-02. The
  nightly job may add sessions from 2026-10-05.
- **CI:** `.github/workflows/engine-ci.yml` runs `pip install -e 'engine[dev]'`, so a new
  `dependencies` entry reaches CI without editing the workflow.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `walkforward.folds` | `backtest/walkforward.py:155` | def (reused) | backtest |
| `walkforward.diagnostics` | `backtest/walkforward.py:284` | def (reused) | backtest |
| `walkforward.window_metrics`, `curve_window_metrics` | `backtest/walkforward.py:325,341` | def (reused) | backtest |
| `walkforward.gate_p3b` (A2 sentence) | `backtest/walkforward.py:362` | def (pattern for `gate_p6a`, not edited) | backtest |
| `walkforward.walk_forward`, `tune`, `select_fold`, `combinations` | `backtest/walkforward.py` | A2-specific; reused **only** to recompute A2's curve | backtest |
| `runner.ParamsSchedule`, `run_backtest`, `survivorship` | `backtest/runner.py:74,131,240` | def (reused) | backtest |
| `metrics.run_metrics`, `curve_metrics`, `checklist`, `fmt_*`, `to_fixed`, `strategy_metrics` | `backtest/metrics.py` | def (reused) | backtest |
| `tuning.IS_START`, `Verdict` | `backtest/tuning.py:17,64` | const/def (reused) | backtest |
| `wf_report._chart`, `_STYLE`, `_validate` pattern; `report._table`, `_usd`, `_span`, `_check_aligned`, `_CHECK_NOTES`, `_EXIT_LABELS` | `backtest/wf_report.py:1120`, `backtest/report.py` | helpers (imported read-only) | backtest |
| `io.write_wf_report` | `backtest/io.py:296` | pattern for `write_b_report` | backtest |
| `backtest_wf.tune_all`, `run_walk_forward`, `resolve`, `_pct`, `_num` | `commands/backtest_wf.py` | reused by `backtest_b` to recompute A2 | commands |
| `backtest.never_fetched_members` | `commands/backtest.py` | reused | commands |
| `a._bracket`, `a.DESIGN_PARAMS`, `a.LOOKBACK`, `a.DV_N`, `a.ATR_N` | `strategies/a.py:178,94,37` | reused | strategies |
| `indicators.sma_window`, `wilder_rsi_window`, `wilder_atr_window`, `mean_dollar_volume_window`, `rolling`, `_column_mean` | `strategies/indicators.py` | reused; `mean_window` and `stdev_return_window` are **added** | strategies |
| `a2.REGIME_SYMBOL` / `market.SPY` / `universe.BENCHMARK` | — | "SPY" | — |
| `sim.step`, `size_picks`, `new_portfolio`, `close_unpriced`, `COST_RATE`, `TIME_STOP_DAYS` | `sim/` | labeler parity (the test only) | sim |
| `test_strategy_purity.py` globs | `tests/test_strategy_purity.py:28` | test (covers new modules automatically) | tests |
| `test_strategy_a2_frozen.py` | `tests/` | pattern for `test_strategy_b_frozen.py` | tests |
| `stratkit.hist`, `mutate_from`, `truncate_before`, `uptrend`, `session_days` | `tests/stratkit.py` | test helpers (reused) | tests |
| `simkit.bar`, `P`, `D` | `tests/simkit.py` | test helpers | tests |
| `dependencies` | `engine/pyproject.toml:9` | config (+ scikit-learn) | engine |
| ROADMAP P6 | `docs/ROADMAP.md:58` | doc | docs |
| readme `backtest_wf`, `backtest walk-forward (P3b)`, `## Performance` | `engine/package_readme.md:173,565,727` | doc | engine |

---

## Impact Points (files that WILL need changes)

1. `engine/pyproject.toml`: add `scikit-learn>=1.9,<1.10`. Phase 1.
2. `strategies/b_model.py` (new): fitting, prediction, identity and serialization for the tree
   and ridge models. Phase 1.
3. `strategies/indicators.py` (additive): `mean_window` and `stdev_return_window`. Phase 2.
4. `strategies/b.py` (new): features, ranks, candidates, `BParams`, `BPrepared`, `StrategyB`.
   Phase 2.
5. `strategies/__init__.py`: exports. Phase 2.
6. `backtest/labels.py` (new): the vectorized labeler and the resolution dates. Phase 3.
7. `backtest/b_walkforward.py` (new): the training set, the purge, per-fold fits, the runs, the
   extra diagnostics and `gate_p6a`. Phase 4.
8. `backtest/b_report.py` (new): the Markdown, CSV and SVG renderers. Phase 5.
9. `backtest/io.py` (additive): `write_b_report` and `write_model_artifact`. Phase 6.
10. `commands/backtest_b.py` (new). Phase 6.
11. The `docs/backtests/<end>-strategy-b-walkforward*` files. Also, on a pass,
    `engine/data/models/…` and the `STRATEGY_B_FROZEN` constant. Plus
    `tests/test_strategy_b_frozen.py`, `engine/package_readme.md` and `docs/ROADMAP.md`. Phase 7.

**This document describes. The plan files prescribe.**
