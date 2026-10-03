# Code Analysis: Strategy A rework under walk-forward validation (roadmap P3b)

**Type:** Feature Implementation
**Date:** 2026-10-03 16:08 WIB
**Session ID:** 20261003-160830-R4W9
**Plan:** `STRATEGY_A_REWORK_PLAN.md` (6 phases)
**Worktree:** `/home/miftah/.worktrees/seer/strategy-a-rework`, branch `feature/strategy-a-rework` (base `HEAD` = `origin/main` @ `e14de0c`)

---

## User Input

### Original User Request

```
/analyze docs/handover/2026-10-03-strategy-a-rework.md
```

The handover file is the specification. It was committed at `e14de0c` and is not copied here; the
plan index quotes its decisions and acceptance criteria. Its §3 "Law" table and "Decided in this
handover" table are binding. §6 is the acceptance list. §7's open questions are settled under
**Decisions** in the plan index.

### User-Provided Context
- P3 landed on `main` @ `2e6994f` with a **failed** gate: OOS −15.0% against +71.9% for
  total-return SPY, PF 0.92, max DD 33.3%. ROADMAP P3: rework before P4.
- This rework runs **once**. If it fails, Strategy A is not reworked again on this data.

### User-Provided Files
- `docs/handover/2026-10-03-strategy-a-rework.md`

### Requirement IDs

These are the handover's §6 acceptance criteria, in its order.

| ID | What the user asked for |
|---|---|
| R1 | Variants V0–V3 (`control`, `regime`, `regime_calm`, `regime_calm_floor`) with tests of each added rule on synthetic data. Regime off at SPY close ≤ SMA(200), including equality. ATR% ranking and its tie order. The $10 floor at exactly 10.0000. V0 picks `==` Strategy A v1 picks. |
| R2 | P4 identity (`picks_prepared(prepare(H)) == picks(upto(d))`) and no look-ahead for every variant, including SPY's own bars dated ≥ S |
| R3 | Anchored yearly walk-forward. Folds exactly as defined. Each fold's selection sees only its tuning window. Segments chain into one portfolio. Brackets survive the year boundary. The none-qualifies fallback is used. |
| R4 | Determinism: `==` results and byte-identical report files. A parallel run, if any, gathers results in a fixed order. |
| R5 | The new modules pass the globbing purity test |
| R6 | One real walk-forward run on Neon, with a committed report holding fold selections and tuning tables, per-variant curves, WF vs both SPY curves, diagnostics, the old OOS window labelled "seen before", the survivorship note, and a one-sentence P3b verdict |
| R7 | Freeze or stop. On a pass: frozen A2 params in code with a comment naming the report, plus a test that ties code to report. On a fail: ROADMAP says the one rework failed and P4 stays blocked, and the report lists what was tried. |
| R8 | The v1 `backtest` report is byte-identical when re-run on the same data. `engine/package_readme.md` documents the variants, walk-forward and the new command. The suite is green with 0 skipped, and CI is green. |

---

## Detailed Requirements Understanding

**Problem statement.** Strategy A v1 has a thin per-trade edge, no market-regime filter, and
oversubscribed slots ranked by deepest RSI(2). A single in-sample/out-of-sample split has been used
up: the 2022→2026 window has been seen once. The rework adds three pre-registered variants and
validates the *procedure* "tune on everything before year Y, trade Y" over 2018→data end, as one
continuous portfolio. The variant choice itself is part of what gets tuned. The result gates P4.

**Success criteria.**
- A new pure strategy, `A2`, exposes the variant as a parameter. V0 reproduces v1 exactly.
- A new pure walk-forward module drives one portfolio whose params change at year boundaries.
- A new read-only command writes a deterministic report, a grid CSV, an equity CSV and SVGs.
- One real run is committed. Either A2 is frozen with a test tying it to the report, or ROADMAP
  records that the single rework failed.
- v1's files and behaviour do not move.

**Key considerations.**
- *No look-ahead across folds.* Picks for the first session of year Y use `data_date` = the last
  session of Y−1. Y's params were tuned through that same session, so it is consistent with "bars
  through `prev_session(S)`".
- *Prefix property of `run_backtest`.* The loop is causal: nothing in it reads `end` except the
  session range, and the "gone" check reads `market.last_bar_date`, not the window. A run on
  `[s, e2]` therefore has exactly the snapshots and closed orders of a run on `[s, e1]` up to `e1`,
  for any `e1 ≤ e2`. Fold tuning exploits this: one run per combination over the longest tuning
  window, sliced per fold (see Decisions D3).
- *SPY is not a member.* The `universe` table holds only index constituents. `universe.BENCHMARK`
  is added only to the bar-fetch symbol sets (`universe.py:38,48`). `Market.history` contains SPY,
  but `Membership` never lists it.
- *Survivorship.* 115 members in the window have no bars at all. That still holds and is still
  reported.
- *Small account.* `lt_one_share` rejections and positions of 1–3 shares are reported as
  diagnostics. They never feed selection.

**Assumptions** (each is recorded as a Decision in the plan index):
- CLI command name `backtest_wf`: command names are module names (`cli.py:36`), and a module name
  cannot contain a hyphen.
- No parallelism is needed. The prefix sharing brings tuning to 324 runs over ≈8.2 years each, about
  4 min. The >60 min trigger in the handover will not fire, but the phase still measures it and logs
  the time.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/handover/2026-10-03-strategy-a-rework.md`
- `docs/backtests/2026-10-02-strategy-a.md`, `docs/handover/2026-10-03-strategy-a-backtest.md`,
  `docs/plans/2026-10-03-seer-design.md`, `engine/package_readme.md`, `docs/ROADMAP.md`

### Discovered Related Files
- `engine/src/seer_engine/strategies/{base,indicators,a,__init__}.py`: the strategy protocol, the
  bit-identical window functions, and Strategy A
- `engine/src/seer_engine/backtest/{runner,market,tuning,metrics,benchmark,report,io,__init__}.py`
- `engine/src/seer_engine/commands/backtest.py`, plus `cli.py` (command discovery by module name)
- `engine/src/seer_engine/sim/{model,sizing,lifecycle}.py`: `Order`, `Pick`, `size_picks`, `step`,
  `close_unpriced`. Read only, never changed.
- `engine/src/seer_engine/universe.py`: `BENCHMARK = "SPY"`. It imports psycopg, so strategies must
  not import it.
- Tests: `stratkit.py`, `test_strategy_a.py`, `test_strategy_purity.py`,
  `test_strategy_a_frozen.py`, `test_backtest_{runner,tuning,metrics,report,command,io}.py`,
  `conftest.py`

---

## Current Dataflow

### Entry Point: `python -m seer_engine backtest`

**Location:** `commands/backtest.py:run` (line ≈118)
**Trigger:** CLI. `cli.discover()` imports every public module in `seer_engine.commands`, and the
command name is `info.name`.
**Next step:** `backtest_io.load_market(conn, cache_dir, refresh)` returns `(Market, rows)`. The
connection is then closed. Next, `read_dividends`, then `resolve_windows`.

### Processing Chain (v1)

1. **`execute(market, bars_rows, dividends, w)`** (`commands/backtest.py:≈175`)
   - `prepared = STRATEGY_A.prepare(market.history)`: a columnar `APrepared` (close, sma, rsi, atr,
     dv) for every symbol with ≥ 200 bars, **SPY included**, ordered by (date, symbol).
   - `run_grid` runs `grid()` (81 `AParams`). For each set it calls
     `run_backtest(market, STRATEGY_A, p, is_start, is_end, prepared=prepared)` and then
     `run_metrics`, and returns `GridRow(params, metrics)`.
   - `select(rows)` takes the highest total return among `qualifies` (DD ≤ 0.15, PF ≥ 1.3). Ties go
     to lower DD, then index. If nothing qualifies, it falls back to `DESIGN_PARAMS`
     (`tuning.py:84`).
   - `run_window` runs three times (IS, OOS, full): `run_backtest` + `spy_curves(spy, start, end,
     result.initial_cash, dividends)`.
   - `survivorship`, `never_fetched_members`, then `gate(oos_metrics, spy_tr_metrics)`.
2. **`run_backtest(market, strategy, params, start, end, *, prepared, initial_idr)`** (`runner.py:88`)
   - `cash0 = initial_cash_usd(initial_idr, market.usd_idr_on(start))`, with snapshot 0 at
     `prev_session(start)`.
   - Per session S: `members = membership.members_on(data_date)`, then
     `picks = strategy.picks_prepared(prepared, members, data_date, params)` (or `picks` on cut
     histories), then `size_picks`, then `step(pf, S, market.bars_on(S, held))`. Symbols whose last
     bar is before S are closed with `close_unpriced`. Finally `data_date = S`.
   - The result is a `RunResult` holding `params`, snapshots, events, closed, open_at_end and
     rejections.
   - **`params` is read in exactly one place**: the `picks`/`picks_prepared` call. That is the hook
     for a schedule.
3. **`StrategyA.picks_prepared`** → `picks_prepared_a` (`a.py:276`)
   - `prepared._rows(d)` gives a slice. A vectorized mask applies close > sma, rsi < rsi_max and
     dv > min_dv. Each survivor is checked for membership and turned into `Features` via
     `picks_from_features`.
   - `picks_from_features` checks the `isinstance(params, AParams)` guard, then `_setup` and
     `_bracket`, then ranks by `(rsi, symbol)`.
   - `_setup(f, params)` and `_bracket(f, params)` (`a.py:≈178,182`) read `params.rsi_max`,
     `min_dollar_volume`, `limit_atr`, `tp_atr` and `sl_atr`. They are module-private but importable.
4. **`StrategyA.picks`** filters history to members, then calls `features_at`, which stacks the last
   200 bars and calls the window functions.

### Metrics, report, files
- `run_metrics(r)` (`metrics.py:≈150`) takes snapshots → `(date, float(equity))` and closed →
  `float(pnl_usd)`, calls `strategy_metrics`, then sets `avg_days_held` and `exit_reasons`.
- `report.render_markdown`, `equity_csv` and `equity_svg` read the `BacktestReport`. `_validate`
  requires every window's `run.params == selection.params`.
- `io.write_report(out_dir, report)` writes `<data_end>-strategy-a.md`, `-equity.csv` and
  `-equity.svg`. Each file is rendered fully before any write.

### Data Persistence
- **None to the DB.** `load_market` runs in one `REPEATABLE READ, READ ONLY` transaction and always
  rolls back.
- Cache: `engine/.cache/bars-<max date>-<rows>.pkl`, which is gitignored.
- Files: `docs/backtests/*`.

### Exit Points
- Exit 0 whether the gate passes or fails, 2 on a precondition, 1 on any other error.

---

## Key Data Structures

### `AParams` (`strategies/a.py:≈48`)
A frozen, slotted dataclass. `rsi_max: float`, `limit_atr`/`tp_atr`/`sl_atr: Decimal`,
`min_dollar_volume: float`. `as_dict()` returns normalized strings in a fixed key order.

### `APrepared` (`strategies/a.py:≈200`)
`symbols`, `dates`, `sym`, `close`, `sma`, `rsi`, `atr`, `dollar_volume`. `_rows(d)` and
`features_on(d)`. It covers **every** symbol in the history it was given, SPY included.

### `RunResult` (`backtest/runner.py:47`)
`strategy_id`, `params`, `start`, `end`, `usd_idr`, `initial_cash`, `snapshots`, `events`, `closed`,
`open_at_end`, `rejections`.

### `Order` (`sim/model.py:101`)
Bracket fields, `shares`, `fill_price`, `exit_date`, `exit_price`, `exit_reason`, and `pnl_usd`
(= `sell_proceeds − buy_cost`, net of both 0.1% costs). Gross P/L is `(exit − fill) × shares`, so
costs = gross − pnl.

### `GridRow`, `Selection`, `Verdict` (`backtest/tuning.py`)
`GridRow(params, metrics)`, `Selection(params, qualified, reason)`,
`Verdict(passed, checks, sentence)`.

---

## Dependencies

- **Configuration:** `SEER_ENV_FILE` for a real run from a worktree, and `PG_TEST_URL` for tests.
- **External:** Neon (read-only). `engine/data/spy_dividends.csv` is vendored.
- **Python:** numpy and pandas are already declared. There are no new dependencies.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `run_backtest` | `backtest/runner.py:88` | def (gains a schedule-aware params path) | backtest |
| `run_backtest` | `commands/backtest.py:run_grid,run_window` | call (v1, unchanged) | commands |
| `run_backtest` | `tests/test_backtest_runner.py` (many) | test | tests |
| `RunResult.params` | `backtest/report.py:_validate` | read (v1, unchanged) | backtest |
| `select` | `backtest/tuning.py:84` | def (gains `fallback=`) | backtest |
| `select` | `commands/backtest.py:execute`, `tests/test_backtest_tuning.py` | call / test | — |
| `DESIGN_PARAMS` | `strategies/a.py`, `tuning.py`, `report.py` | def / read | — |
| `run_metrics` | `backtest/metrics.py:≈150` | def (a sibling `metrics_through` is added) | backtest |
| `_setup`, `_bracket`, `prepare_a`, `APrepared`, `Features` | `strategies/a.py` | reused by `a2.py` (read only) | strategies |
| `sma_window` | `strategies/indicators.py` | reused for SPY's SMA(200) | strategies |
| `_table`, `_usd`, `_nice_ticks`, `_tick_label`, `_esc`, `_SVG_*` | `backtest/report.py` | reused by the WF report (read only) | backtest |
| `checklist`, `fmt_*`, `to_fixed`, `strategy_metrics` | `backtest/metrics.py` | reused | backtest |
| `spy_curves` | `backtest/benchmark.py` | reused for the WF window | backtest |
| `load_market`, `read_dividends` | `backtest/io.py` | reused by the new command | backtest |
| `resolve_windows`, `never_fetched_members` | `commands/backtest.py` | reused or mirrored by the new command | commands |
| `IMPURE` glob | `tests/test_strategy_purity.py:24` | test (covers new modules automatically) | tests |
| `BENCHMARK` | `universe.py:13` | `REGIME_SYMBOL` must equal it | engine |
| `## strategies`, `## backtest`, `### backtest (P3)`, `## Performance`, Usage | `engine/package_readme.md:136,336,401,536,658` | doc | docs |
| P3 verdict line | `docs/ROADMAP.md:27-33` | doc | docs |

---

## Impact Points

1. `strategies/a2.py` (new), `strategies/__init__.py` (exports), `tests/test_strategy_a2.py` (new): phase 1
2. `backtest/runner.py` (`ParamsSchedule`, schedule-aware picks), `backtest/metrics.py`
   (`metrics_through`), `backtest/tuning.py` (`select(..., fallback=)`), and the tests for each: phase 2
3. `backtest/walkforward.py` (new), `tests/test_backtest_walkforward.py` (new): phase 3
4. `backtest/wf_report.py` (new), `tests/test_backtest_wf_report.py` (new): phase 4
5. `backtest/io.py` (`write_wf_report`), `commands/backtest_wf.py` (new),
   `tests/test_backtest_wf_command.py` (new): phase 5
6. `docs/backtests/<end>-strategy-a2-walkforward*` (new), `strategies/a2.py` (the frozen constant on
   a pass), `tests/test_strategy_a2_frozen.py` (new), `docs/ROADMAP.md`,
   `engine/package_readme.md`: phase 6

**This document describes. The plan files prescribe.**
