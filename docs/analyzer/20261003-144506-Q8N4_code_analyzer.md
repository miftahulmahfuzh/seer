# Code Analysis: Strategy A + 10-year backtest (roadmap P3)

**Type:** Feature Implementation
**Date:** 2026-10-03 14:45 WIB
**Session ID:** 20261003-144506-Q8N4
**Plan:** `STRATEGY_A_BACKTEST_PLAN.md` (6 phases)
**Worktree:** `/home/miftah/.worktrees/seer/strategy-a-backtest`, branch `feature/strategy-a-backtest` (base `origin/main` = `HEAD` @ `d3a2e1d`)

---

## User Input

### Original User Request

```
/analyze docs/handover/2026-10-03-strategy-a-backtest.md
```

The argument is the whole specification: `docs/handover/2026-10-03-strategy-a-backtest.md`
(committed at `d3a2e1d`). It is reproduced here in the parts that bind the plan. Its §3 tables
are law ("do not reopen"), §6 is the acceptance list, and §7 holds the open questions this
analysis settles (in the plan index, under **Decisions**).

> ## 2. Goal of this task (P3, Strategy A + backtest)
>
> Implement Strategy A and a 10-year backtest that runs it through the **P2 simulator**, then give
> an honest verdict on whether it beats SPY.
>
> It must:
> 1. Compute Strategy A's signals (design §4) from split-adjusted daily bars, using only data
>    available at the `data_date` close (no look-ahead), and turn them into ranked `sim.Pick`s.
>    Put this behind a small strategy interface, because P4 calls the same code nightly and P6 adds
>    strategies B and C next to it.
> 2. Run a backtest over the point-in-time universe (S&P 500 ∪ Nasdaq-100 members on each
>    `data_date`) for every NYSE session in the window, using `sim.size_picks` → `sim.step` →
>    `sim.close_unpriced` exactly as the readme's "P3 backtest loop" shows.
> 3. Build the SPY buy-and-hold benchmark curve over the same window, net of the same 0.1% costs.
> 4. Tune parameters on the early years only, validate on the later years without tuning, then
>    **freeze** the parameters in code.
> 5. Produce a backtest report: equity curve vs SPY, total return, CAGR, win rate, profit factor,
>    max drawdown, trade count, exit-reason breakdown, and the go-live criteria from design §1
>    that a backtest can evaluate. Report the in-sample and out-of-sample windows separately.
>
> **Done when:**
> - Strategy A and the backtest runner are implemented and tested on synthetic data (indicators
>   against hand-computed values, no look-ahead, universe point-in-time, delisting handled).
> - One real 10-year run on the Neon data is done, and its report is committed in the repo.
> - The frozen parameters are in code, and the report states the **gate verdict**.
> - The full engine suite is green with 0 skipped, CI stays green, and the API is documented in
>   `engine/package_readme.md`.
>
> **The gate (ROADMAP P3):** if Strategy A cannot beat SPY in the backtest, **stop and report it**.
> Do not start P4, and do not tune on the validation window to rescue it. A losing verdict, honestly
> measured, is a successful P3. Tuning until the number looks good is the failure mode this project
> exists to avoid.
>
> **Out of scope, don't build:** nightly wiring, writing `orders`/`equity_snapshots`/`strategies.params`
> to Neon (P4), LLM explanations (P4), strategies B and C (P6), any web change, any change to
> simulator rules.

§3 (decisions already made), §4 (verified facts), §5 (environment), §6 (acceptance criteria 1–10)
and §7 (open questions) are read in full from the handover file and are binding; they are not
copied here a second time to avoid two diverging copies.

### User-Provided Context

- Design doc `docs/plans/2026-10-03-seer-design.md` §1 (go-live checklist), §4 (Strategy A rules),
  §5 (trade rules) are law.
- `engine/package_readme.md` → `### sim`, `### Simulator: P3 backtest loop`, `## Performance`.
- `web/lib/metrics.ts` + `web/lib/metrics.test.ts`: metric definitions the report must match.
- `docs/runbooks/data-pipeline.md` "First run": the Neon data inventory and the 133 unfetchable symbols.

### User-Provided Files
- `docs/handover/2026-10-03-strategy-a-backtest.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Strategy A signals (SMA200, Wilder RSI(2), Wilder ATR(14), 20-day dollar volume) from data through `data_date` only, turned into ranked `sim.Pick`s, behind a small pure strategy interface shared with P4/P6 |
| R2 | A backtest runner over the point-in-time universe for every NYSE session, driving `size_picks` → `step` → `close_unpriced`, delisting handled |
| R3 | SPY buy-and-hold benchmark curves (price-only and total-return), net of the same 0.1% costs and whole-share rule |
| R4 | Tune on the in-sample years with the fixed 81-run grid, validate once on out-of-sample, freeze the parameters in code |
| R5 | The backtest report: equity curves vs SPY, total return, CAGR, win rate, profit factor, max drawdown, trades, exit reasons, go-live criteria, IS and OOS separately, survivorship note, gate verdict; metrics identical to `web/lib/metrics.ts` |
| R6 | One real 10-year run on Neon with its report committed, the gate verdict stated, the API documented in `engine/package_readme.md`, the full suite green with 0 skipped and CI green |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** The engine has a pure, Decimal-only fill simulator (P2) and ten
years of split-adjusted bars on Neon (P1), but nothing that decides *what* to buy. P3 adds:

1. A pure strategy layer (`seer_engine/strategies/`): a protocol P4/P6 implement, the indicator
   math, and Strategy A, which maps per-symbol bar history at a `data_date` to a ranked
   `list[sim.Pick]`.
2. A pure backtest layer (`seer_engine/backtest/`): an in-memory point-in-time universe and bar
   store, the session loop around the simulator, SPY benchmark curves, metrics with web parity,
   the parameter grid and selection, the gate, and report rendering (Markdown, CSV, SVG).
3. An impure edge: a loader that reads `bars`/`universe`/`fx_rates` from Neon once (with a local
   cache) and a `backtest` CLI command that writes the report files.
4. One honest real run, the frozen parameters committed in code, and the docs.

**Success Criteria.** Handover §6 items 1–10, all of them. In particular: indicator tests against
hand-computed values including the warm-up boundary; a look-ahead test (mutating any bar dated on
or after S leaves S's picks unchanged); a hand-checked multi-symbol synthetic backtest including a
forced close and a 0-pick session; SPY curves with a dividend; metrics parity with
`web/lib/metrics.test.ts`; determinism; purity of strategy and backtest core modules; and a
committed report whose verdict comes from out-of-sample results only.

**Key Considerations.**
- *P4 identity.* P4 will compute picks nightly from the last N bars it loads from Neon. Wilder
  smoothing is recursive, so its value depends on where the recursion starts. If the backtest
  computes indicators over a symbol's whole history and P4 over a 250-bar tail, the numbers differ
  (tiny for ATR, but a 4-dp quantization can flip). The analysis must pin the window.
- *Float vs Decimal.* `bars.close` is `numeric(12,4)` (≤ 12 significant digits), so a float64 round
  trip through `repr` is exact; `prices.to_decimal` already goes through `repr`.
- *Memory.* 1.8 M rows as `Bar` objects with four `Decimal`s each would be far heavier than
  float64 arrays. `step` reads bars only for symbols with a live order (≤ 4 per session).
- *Survivorship.* 133 ever-members have no bars at all; the report must quantify it per year.
- *Dividends.* `bars` are not dividend-adjusted. Price-only SPY understates SPY by roughly
  1.3–1.8 %/yr; the gate uses total-return SPY.
- *Worktree env.* `config.REPO_ROOT` resolves from the file location, so in a worktree the default
  `.env.local` path is the worktree root, which has no `.env.local`. The real run must set
  `SEER_ENV_FILE=/home/miftah/seer/.env.local`.

**Assumptions.** The 133 symbols stay unfetchable (no new data source). Neon is reachable from the
implementing machine through Python (raw `psql` hangs on IPv6). yfinance can fetch
`Ticker("SPY").dividends` once at implementation time.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/handover/2026-10-03-strategy-a-backtest.md`
- `docs/plans/2026-10-03-seer-design.md`, `docs/ROADMAP.md`
- `engine/package_readme.md`, `web/lib/metrics.ts`, `web/lib/metrics.test.ts`
- `docs/runbooks/data-pipeline.md`, `db/migrations/001_init.sql`, `db/migrations/002_engine.sql`

### Discovered Related Files
- `engine/src/seer_engine/sim/{__init__,model,lifecycle,sizing,split_adjust}.py` — the API P3 drives
- `engine/src/seer_engine/prices.py` — pure `Bar`, `PRICE_QUANTUM`, `to_decimal`
- `engine/src/seer_engine/dates.py` — `sessions`, `prev_session`, `next_session`, `is_session`
- `engine/src/seer_engine/universe.py` — DB membership queries (one query per date)
- `engine/src/seer_engine/membership.py` — `Interval` dataclass (writer side of `universe`)
- `engine/src/seer_engine/db.py`, `config.py`, `cli.py`, `commands/__init__.py` — command contract
- `engine/tests/test_sim_purity.py`, `engine/tests/simkit.py`, `engine/tests/conftest.py`
- `engine/pyproject.toml` (numpy not declared; pandas brings it), `.gitignore`
- `.github/workflows/engine-ci.yml` — CI fails on any `SKIPPED`
- `engine/data/SOURCES.md` — provenance of vendored CSVs

---

## Current Dataflow

### Entry point: CLI

**Location:** `engine/src/seer_engine/cli.py`
**Trigger:** `python -m seer_engine [--dry-run] [-v] <command>`
`cli.main` → `config.load_env()` → `discover()` imports every public module in
`seer_engine/commands/` that has a callable `run` → `run(args) -> int`. Adding
`commands/backtest.py` adds the command; `cli.py` never changes. Exit codes: 0 ok, 1 exception,
2 `ConfigError`/precondition, 130 Ctrl-C.

### Configuration

`config.env_file()` = `$SEER_ENV_FILE` else `<REPO_ROOT>/.env.local`; `REPO_ROOT` is derived from
`config.py`'s own path. `db.connect()` uses `DATABASE_URL_UNPOOLED`, autocommit off. Callers use
`contextlib.closing(db.connect())`, never `with psycopg.connect()`.

### Simulator (P2) — what P3 calls

1. `initial_cash_usd(idr, usd_idr) -> Decimal` (`sim/model.py:92`): `q(idr / usd_idr)`.
2. `new_portfolio(cash_usd) -> Portfolio` (`sim/model.py:257`): `cash = equity = q(cash)`,
   `last_session=None`.
3. `size_picks(portfolio, picks, session_date) -> SizingResult` (`sim/sizing.py`): picks in rank
   order; rejection reasons `held` → `no_slot` → `lt_one_share`; raises when `session_date` is not
   a session after `last_session`, or a pending order for another session remains.
4. `step(portfolio, session_date, bars: Mapping[str, Bar]) -> StepResult(portfolio, events, snapshot)`
   (`sim/lifecycle.py:128`): reads bars only for symbols with a live order; a missing key = no bar.
   Raises on a non-session, a non-`Bar`, a non-`Decimal` price, or a bar whose symbol/date is wrong.
5. `close_unpriced(portfolio, symbols) -> (Portfolio, events)` (`sim/lifecycle.py:208`): forced
   exit at the mark, reason `time`, `exit_date = last_session`, `forced=True`; recomputes equity.
6. `Pick(symbol, last_price, limit_price, tp_price, sl_price)` (`sim/sizing.py`): all `Decimal`,
   each must be `> 0` after `q`, and `sl < limit < tp`, else `ValueError`.
7. `buy_cost(price, shares) = q(price × shares × 1.001)`, `sell_proceeds = q(price × shares × 0.999)`.
8. `Event(session_date, kind, order, forced, cash_usd)`; a closed order carries `pnl_usd`,
   `exit_reason ∈ {tp, sl, time, gap}`, `days_held`. `Snapshot(date, cash_usd, equity_usd)`.

The readme's "P3 backtest loop" (`engine/package_readme.md:395-420`) is the prescribed loop:
`size_picks(pf, picks(prev_session(S)), S)` → `step(pf, S, bars_on(S, held))` → append events and
snapshot → `close_unpriced` for symbols whose bars ended → overwrite the last snapshot.

Measured: 2,950 sessions × 4 slots in 0.20 s (`test_sim_scenario.py::test_benchmark_...`).

### Data on Neon (read-only for P3)

| Table | Shape | Notes |
|---|---|---|
| `bars(symbol, date, open, high, low, close numeric(12,4), volume bigint)` PK `(symbol, date)` | 1,817,429 rows, 663 symbols, 2015-01-02 → 2026-10-02, 177 MB | split-adjusted, not dividend-adjusted; SPY has all 2,955 sessions |
| `universe(symbol, index_id, start_date, end_date NULL, source_symbol)` | 1,544 intervals, 795 ever-members since 2015 | `[start_date, end_date)`; `end_date` exclusive |
| `fx_rates(date PK, usd_idr numeric(12,4))` | 3,009 rows 2015-01-02 → 2026-10-02 | Frankfurter publishing days only (not every NYSE session) |
| `strategies(id, …, params jsonb)` | 4 rows | P4 writes `params`; P3 does not |

`universe.members_on(conn, d)` (`universe.py:16`) issues one query per date. Session dates:
`dates.sessions(2015-01-02, 2026-10-02)` has 2,955 entries; the 200th is 2015-10-16, so the first
session whose `data_date` has 200 bars of SPY-age history is **2015-10-19**;
`prev_session(2022-01-03) = 2021-12-31` (both measured).

### Purity test pattern

`engine/tests/test_sim_purity.py` (a) imports the package in a fresh subprocess and asserts
`psycopg`, `requests`, `yfinance`, `seer_engine.bars` are not in `sys.modules`; (b) walks the AST of
every `sim/*.py` for forbidden imports (`time`, `random`, `logging`, `urllib`, `socket`, …),
`.now/.utcnow/.today/.fromtimestamp` attributes and `print/open/input` calls.

### Test infrastructure

`conftest.py` provides `pg`/`pg_schema` (throwaway schema `t_<hex>`, migrated) and isolates the env
(`SEER_ENV_FILE` → missing file, `DATABASE_URL_UNPOOLED` → `.invalid`). `simkit.py` provides
`D`, `P`, `bar`, `day`, `pending`, `opened`, `portfolio`. CI (`engine-ci.yml`) fails on any
`SKIPPED` line. Baseline: 374 passed, 0 skipped.

### Web metrics (`web/lib/metrics.ts`)

`strategyMetrics(snaps, pnls)`: wins `p > 0`, losses `p ≤ 0`; profit factor
`grossWin / grossLoss`, `Infinity` when `grossLoss == 0` and trades exist, `null` with no trades;
max drawdown = max over snapshots of `(peak − equity) / peak`; total return `last/first − 1`;
months = `(last − first days) / 30.44`. `checklist(m, spyReturn)`: ≥ 3 months, ≥ 100 trades,
beats SPY (strict `>`), PF ≥ 1.3, max DD ≤ 0.15. Tests (`metrics.test.ts`): snaps
`[1000, 1100, 990, 1050]` + pnls `[30, −10, 20, −10]` → return 0.05, win rate 0.5, PF 2.5, DD 0.1,
trades 4; empty → nulls; `[1,2]`+`[5]` → PF ∞; 2026-07-06 → 2026-10-05 → months ≈ 3.0; checklist
base case `[true, false, true, true, true]` etc.

### Exit Points

Nothing in P3 writes to Neon. Outputs are files: `docs/backtests/*` (committed) and
`engine/.cache/*` (gitignored, new).

---

## Key Data Structures

### `sim.Pick` — `engine/src/seer_engine/sim/sizing.py`
`symbol: str, last_price, limit_price, tp_price, sl_price: Decimal`; validated `> 0` and
`sl < limit < tp`. Used by `size_picks`.

### `sim.Order` / `sim.Portfolio` / `sim.Event` / `sim.Snapshot` — `sim/model.py`
As listed above; `Portfolio.open_orders()`, `held_symbols()`, `cash`, `equity`, `last_session`.

### `prices.Bar` — `engine/src/seer_engine/prices.py`
`Bar(symbol, date, open, high, low, close: Decimal, volume: int)`, frozen, slots. `step` type-checks it.

### `membership.Interval` — `engine/src/seer_engine/membership.py:49`
`Interval(symbol, index_id, start_date, end_date | None, source_symbol)`; writer-side type.

---

## Dependencies

- **Python libs present:** pandas 3.0.6, numpy 2.4.6 (transitive via pandas, not declared in
  `pyproject.toml`), yfinance 1.7.0, psycopg 3. **Absent:** pyarrow, matplotlib.
- **Env:** `DATABASE_URL_UNPOOLED` (via `.env.local`, loaded by dotenv, never sourced),
  `SEER_ENV_FILE`, `PG_TEST_URL` for tests.
- **External services:** Neon (read-only), Yahoo (once, for SPY dividends at implementation time).

---

## Reference List

New-feature work; the touch points are the APIs consumed, not symbols being changed.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `size_picks`, `step`, `close_unpriced`, `new_portfolio`, `initial_cash_usd`, `Pick`, `Snapshot`, `buy_cost`, `q` | `engine/src/seer_engine/sim/__init__.py` | def (consumed) | `seer_engine.sim` |
| `Bar`, `to_decimal`, `PRICE_QUANTUM` | `engine/src/seer_engine/prices.py` | def (consumed) | `seer_engine` |
| `sessions`, `prev_session`, `next_session`, `is_session` | `engine/src/seer_engine/dates.py` | def (consumed) | `seer_engine` |
| `db.connect`, `config.require` | `engine/src/seer_engine/db.py`, `config.py` | def (consumed) | `seer_engine` |
| command discovery | `engine/src/seer_engine/cli.py`, `commands/__init__.py` | contract | `seer_engine.commands` |
| purity test pattern | `engine/tests/test_sim_purity.py` | test (pattern to copy) | tests |
| `strategyMetrics`, `checklist` | `web/lib/metrics.ts:14,40` | def (parity target) | web |
| metrics test inputs | `web/lib/metrics.test.ts` | test (parity inputs) | web |
| "P3 backtest loop" | `engine/package_readme.md:395` | doc | engine |
| P3 roadmap entry | `docs/ROADMAP.md` (`## P3`) | doc | docs |
| `dependencies` | `engine/pyproject.toml` | config (numpy to declare) | engine |
| ignore rules | `.gitignore` | config (`engine/.cache/` to add) | repo |
| vendored data provenance | `engine/data/SOURCES.md` | doc | engine |

---

## Impact Points (files that WILL need changes)

1. `engine/pyproject.toml` — declare `numpy`; phase 1.
2. `engine/src/seer_engine/strategies/{__init__,base,indicators,a}.py` (new) — phase 1.
3. `engine/src/seer_engine/backtest/__init__.py` (new, docstring only) — phase 1.
4. `engine/tests/test_strategy_purity.py`, `test_indicators.py`, `test_strategy_a.py`, `stratkit.py` (new) — phase 1.
5. `engine/src/seer_engine/backtest/benchmark.py`, `engine/data/spy_dividends.csv`, `engine/data/SOURCES.md`, `engine/tests/test_benchmark.py` — phase 2.
6. `engine/src/seer_engine/backtest/market.py`, `runner.py`, `engine/tests/test_backtest_market.py`, `test_backtest_runner.py` — phase 3.
7. `engine/src/seer_engine/backtest/metrics.py`, `tuning.py`, `report.py`, tests — phase 4.
8. `engine/src/seer_engine/backtest/io.py`, `engine/src/seer_engine/commands/backtest.py`, `.gitignore`, tests — phase 5.
9. `engine/src/seer_engine/strategies/a.py` (frozen params), `docs/backtests/*`, `engine/package_readme.md`, `docs/ROADMAP.md` — phase 6.

**This document describes. The plan files prescribe.**
