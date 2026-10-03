# Todos: engine

**Package Path**: `engine`
**Package Code**: ENG
**Last Updated**: 2026-10-03 17:25:05
**Total Active Tasks**: 3

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 1
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 2
- Completed: 17

---

## Active Tasks

### [P0] Critical

### [P1] High

- [ ] **P1-ENG-BVN5** Phase 4: Walk-forward report rendering
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `backtest/wf_report.py` (new: `WalkForwardReport`, `report_stem`, machine lines, `parse_machine_line`, `render_markdown`, `equity_csv`, `grid_csv`, `equity_svg`, `variants_svg`) and `tests/test_backtest_wf_report.py` (new, from a small synthetic walk-forward). 16 report sections in order (title, verdict, Data, Method listing everything tried, Folds with top-10, WF vs both SPY curves, per-variant tables/selections, Diagnostics, "Seen before" from 2022-01-03, go-live checklist, survivorship, open positions, equity curves, gate verdict, fail-only owner options (a)-(c), machine lines per D14). Imports `report.py` helpers read-only, defines its own `_STYLE`. Does not touch `report.py`. Exit: suite green, 0 skipped (740); two renders byte-equal (invariant 5, D16).
  - **Status**: open
  - **Plan Set**: `STRATEGY_A_REWORK_PLAN.md` (phase 4 of 6)
  - **Satisfies**: R5 — The new modules pass the globbing purity test; R6 — One real walk-forward run on Neon, with a committed report holding fold selections and tables, per-variant curves, WF vs both SPY curves, diagnostics, the "seen before" window, the survivorship note and the P3b verdict sentence
  - **Depends on**: P1-ENG-ODYP
  - **Plan**: `.workflows/plan/P1-ENG-BVN5.md`

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

- [ ] **P1-ENG-U4G0** Phase 5: `backtest_wf` command + `write_wf_report`
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `io.write_wf_report` and `commands/backtest_wf.py` (args, `resolve` preconditions mirroring v1 exit-2 cases, `tune_all` per-combination timing via `walkforward.tune` (D17), `run_walk_forward`, `execute` building SPY curves + verdict as `wf_report._validate` recomputes; logs prepare time, per-combo/total tuning time, per-fold selections, verdict, `STRATEGY_A2_PARAMS` match) plus `tests/test_backtest_wf_command.py` (discovery/defaults, exit-2 cases, end-to-end on synthetic PG schema spanning >= 2 trade years: read-only, five file names, cache hit, byte-identical re-run). Does not touch `commands/backtest.py`, `report.py`, `walkforward.py`, `wf_report.py` (except logged defect fixes). Exit: suite green, 0 skipped (757); `python -m seer_engine backtest_wf --help` works; `tune_all == tune` on a subset tested.
  - **Status**: blocked
  - **Plan Set**: `STRATEGY_A_REWORK_PLAN.md` (phase 5 of 6)
  - **Satisfies**: R4 — Determinism: `==` results and byte-identical files; a parallel gather, if any, comes back in a fixed order; R6 — One real walk-forward run on Neon, with a committed report holding fold selections and tables, per-variant curves, WF vs both SPY curves, diagnostics, the "seen before" window, the survivorship note and the P3b verdict sentence
  - **Depends on**: P1-ENG-BVN5
  - **Plan**: `.workflows/plan/P1-ENG-U4G0.md`

- [ ] **P1-ENG-RTWR** Phase 6: Real run on Neon, freeze or stop, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns one real `backtest_wf` run with committed `docs/backtests/<end>-strategy-a2-walkforward{.md,-equity.csv,-equity.svg,-variants.svg,-grid.csv}`; on pass replace the placeholder with an `A2Params(...)` literal of the last fold selection + comment naming the report and re-run, on fail leave `None`; `tests/test_strategy_a2_frozen.py` asserts the branch taken; v1 byte-identity check vs committed `2026-10-02-strategy-a.*` (D9); `docs/ROADMAP.md` P3b line with verdict (fail: one rework failed, P4 stays blocked); `engine/package_readme.md` (strategies A2/variants, backtest schedule/`metrics_through`/walkforward/wf_report, `backtest_wf` section, `## Performance`, Usage). Does not touch pure-module logic except tested, logged defect fixes. Exit: report committed; frozen test green; v1 identity verified; suite green, 0 skipped (761); CI green on push.
  - **Status**: blocked
  - **Plan Set**: `STRATEGY_A_REWORK_PLAN.md` (phase 6 of 6)
  - **Satisfies**: R6 — One real walk-forward run on Neon, with a committed report holding fold selections and tables, per-variant curves, WF vs both SPY curves, diagnostics, the "seen before" window, the survivorship note and the P3b verdict sentence; R7 — Freeze or stop: on a pass, frozen A2 params with a comment naming the report and a code↔report test; on a fail, ROADMAP records that the one rework failed and P4 stays blocked, and the report lists what was tried; R8 — The v1 `backtest` report is byte-identical when re-run on the same data; `engine/package_readme.md` documents the variants, walk-forward and the new command; the suite is green with 0 skipped; CI is green
  - **Depends on**: P1-ENG-U4G0
  - **Plan**: `.workflows/plan/P1-ENG-RTWR.md`

---

## Completed Tasks
- [x] **P1-ENG-ODYP** Phase 3: Walk-forward engine
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `backtest/walkforward.py` (new: `folds`, `combinations`, `tune`, `select_fold`, `schedule`, `walk_forward`, `diagnostics`, `window_metrics`, `curve_window_metrics`, `gate_p3b`) and `tests/test_backtest_walkforward.py` (new, synthetic: folds as defined incl. real calendar 2018…2026 vs end 2026-10-02 and edge cases; 324 combinations in order; `tune` rows `==` direct per-fold runs; mutating a bar inside a traded year leaves that fold unchanged; one portfolio with year-start param switches, bracket survives 31 Dec; fallback used when nothing qualifies; diagnostics hand-computed; gate sentences; determinism). Does not touch `runner.py`, `metrics.py`, `tuning.py`, `strategies/`, existing tests. Exit: suite green, 0 skipped (712); purity glob covers the module.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_REWORK_PLAN.md` (phase 3 of 6)
  - **Satisfies**: R3 — Anchored yearly walk-forward: folds as defined, each fold's selection sees only its tuning window, segments chain into one portfolio, brackets survive the year boundary, the fallback is used when nothing qualifies; R4 — Determinism: `==` results and byte-identical files; a parallel gather, if any, comes back in a fixed order; R5 — The new modules pass the globbing purity test
  - **Depends on**: P1-ENG-WCIA, P1-ENG-3PA3
  - **Plan**: `.workflows/plan/P1-ENG-ODYP.md`
  - **Completed**: 2026-10-03 17:25
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/walkforward.py, engine/tests/test_backtest_walkforward.py
- [x] **P1-ENG-3PA3** Phase 2: Runner params schedule, `metrics_through`, `select` fallback
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `ParamsSchedule` + the schedule branch in `run_backtest`, `metrics_through` in `metrics.py`, keyword-only `fallback=` (default `DESIGN_PARAMS`, D19) on `tuning.select`; tests in `test_backtest_runner.py` / `test_backtest_metrics.py` / `test_backtest_tuning.py` (mid-run param switch keeps open bracket; one-segment schedule `==` plain run except `RunResult.params`; prefix property on scenario + Strategy A smoke markets incl. forced closes; `select` with/without fallback; helpers `ParamPicks`, `TABLE_B`, `SWITCH`, `smoke_market(cut=None)` appended, existing helpers untouched). Only changed assertion: `select` signature guard widened to `["rows", "fallback"]`. Does not touch `strategies/`, `report.py`, `commands/`. Exit: suite green, 0 skipped (611 alone, 673 with phase 1); every existing runner/tuning/metrics test unchanged and passing except the widened guard.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_REWORK_PLAN.md` (phase 2 of 6)
  - **Satisfies**: R3 — Anchored yearly walk-forward: folds as defined, each fold's selection sees only its tuning window, segments chain into one portfolio, brackets survive the year boundary, the fallback is used when nothing qualifies; R8 — The v1 `backtest` report is byte-identical when re-run on the same data; `engine/package_readme.md` documents the variants, walk-forward and the new command; the suite is green with 0 skipped; CI is green
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-3PA3.md`
  - **Completed**: 2026-10-03 17:22
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/runner.py, engine/src/seer_engine/backtest/metrics.py, engine/src/seer_engine/backtest/tuning.py, engine/tests/test_backtest_runner.py, engine/tests/test_backtest_metrics.py, engine/tests/test_backtest_tuning.py
  - **Drift**: None. Every anchor the plan quotes matched e14de0c exactly, and the code blocks were applied verbatim.
  - **Decided**: Worktree venv: p1 and p2 both ran the install concurrently in the shared worktree, and p1 re-ran pip install afterwards. seer_engine imports from the worktree. (rung 6: invariant 1 venv rule)
- [x] **P1-ENG-WCIA** Phase 1: Strategy A2: variants V0–V3
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `strategies/a2.py` (new, exactly the shared contract; `STRATEGY_A2_PARAMS = None` under a two-line placeholder comment, `Decimal` imported), `strategies/__init__.py` exports, `tests/test_strategy_a2.py` (new: every R1 rule; V0 `==` v1 over a contract set for several params; P4 identity for all four variants; no look-ahead with SPY mutated/truncated from S; SPY never picked; `REGIME_SYMBOL == universe.BENCHMARK`), reusing `tests/stratkit.py` unedited. Does not touch `a.py`, `base.py`, `indicators.py`, `stratkit.py`, `test_strategy_purity.py`, `backtest/`. Exit: suite green, 0 skipped (660 alone, 673 with phase 2); purity glob covers `a2.py`; `a.py`, `base.py`, `indicators.py` byte-identical to `e14de0c`.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_REWORK_PLAN.md` (phase 1 of 6)
  - **Satisfies**: R1 — Variants V0–V3 with tests of each added rule: regime off at SPY close ≤ SMA(200), including equality; the ATR% ranking and its tie order; the $10 floor at exactly 10.0000; V0 picks `==` v1 picks; R2 — P4 identity and no look-ahead for every variant, including SPY's own bars dated ≥ S; R5 — The new modules pass the globbing purity test
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-WCIA.md`
  - **Completed**: 2026-10-03 17:20
  - **Method**: /do
  - **Files**: engine/src/seer_engine/strategies/a2.py, engine/src/seer_engine/strategies/__init__.py, engine/tests/test_strategy_a2.py
- [x] **P1-ENG-KG5T** Phase 6: Real 10-year run, freeze params, committed report, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/strategies/a.py` (`STRATEGY_A_PARAMS` only, written in the grid constants' spelling), `docs/backtests/<end>-strategy-a.md`, `<end>-strategy-a-equity.csv`, `<end>-strategy-a-equity.svg` (new, produced by the command), `engine/tests/test_strategy_a_frozen.py` (new: the frozen params equal the ones recorded in the committed report), `engine/package_readme.md` (strategy interface, indicators, Strategy A, backtest modules, command, report), `docs/ROADMAP.md` (P3 status + verdict). Does not touch any other source module. If the real run exposes a bug, fix it in the owning module and record it in the commit message; never change a rule to move the result. Exit: one real run on Neon (`SEER_ENV_FILE=/home/miftah/seer/.env.local`, read-only), report committed, `STRATEGY_A_PARAMS` equals the selection with a comment naming the report, a re-run reproduces byte-identical report files, the verdict sentence is in the report and in ROADMAP P3. If the gate fails, ROADMAP says so and that P4 must not start. readme documents everything above, `--cache-dir` included. 3 new tests (`test_strategy_a_frozen.py`, via `report.parse_params_line`); suite **598**, 0 skipped.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_BACKTEST_PLAN.md` (phase 6 of 6)
  - **Satisfies**: R4 — Tune on in-sample with the fixed 81-run grid, validate once on out-of-sample, freeze params in code; R5 — Backtest report (curves vs SPY, return, CAGR, win rate, PF, max DD, trades, exit reasons, go-live criteria, IS/OOS separately, survivorship note, gate verdict), metrics identical to `web/lib/metrics.ts`; R6 — One real 10-year run on Neon, report committed, gate verdict stated, API documented in `engine/package_readme.md`, suite green with 0 skipped, CI green
  - **Depends on**: P1-ENG-5LGI
  - **Plan**: `.workflows/plan/P1-ENG-KG5T.md`
  - **Completed**: 2026-10-03 15:54
  - **Method**: /do
  - **Files**: engine/src/seer_engine/strategies/a.py, engine/tests/test_strategy_a_frozen.py, docs/backtests/2026-10-02-strategy-a.md, docs/backtests/2026-10-02-strategy-a-equity.csv, docs/backtests/2026-10-02-strategy-a-equity.svg, engine/package_readme.md, docs/ROADMAP.md
  - **Drift**:
    - package_readme.md anchors were shifted by +2 lines (phase 1 added two placeholder layout lines for strategies/ and backtest/); those placeholders were replaced by the full layout entries. Edits applied by text anchor.
    - Module-graph bullet corrected against the code: commands.backtest also imports prices; backtest.io also imports numpy; pure backtest modules import numpy.
    - Cold-load time taken from run-log timestamps (~25 s streaming COPY) rather than run1-run3 wall difference.
  - **Decided**:
    - Plan Rule 3 'never push' vs /implement pusher + swarm coordinator instruction -> push to feature/strategy-a-backtest (not main). Rung: coordinator owns landing; phases 1-5 were pushed to the same branch.
    - Survivorship readme examples (SIVB, FRC, CHK, ATVI, CELG) dropped - not verified against the never-fetched list. Rung 6.
  - **Result**:
    - Real run on Neon, data through 2026-10-02 (1,817,429 bar rows, 663 symbols). 0 of 81 in-sample grid runs qualified (max DD <= 15% and PF >= 1.3) -> design fallback frozen as explicit AParams literal {"rsi_max": "10", "limit_atr": "0.5", "tp_atr": "1", "sl_atr": "1.5", "min_dollar_volume": "20000000"}.
    - Gate FAILED: out of sample -15.0% vs +71.9% total-return SPY, PF 0.92, max DD 33.3%. P4 must not start until Strategy A is reworked.
    - Runs #1/#2/#3 byte-identical; Neon fingerprint unchanged; grid 37.7-39.0 s total. Suite: 598 passed, 0 skipped.
- [x] **P1-ENG-5LGI** Phase 5: Neon loader with cache + `backtest` command
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/backtest/io.py`, `engine/src/seer_engine/commands/backtest.py` (new), `.gitignore` (add `engine/.cache/`), `engine/tests/test_backtest_io.py`, `engine/tests/test_backtest_command.py` (new; DB tests on the `pg` fixture). Does not touch the pure modules (except a bug fix found by the end-to-end test, recorded in the commit), readme, ROADMAP, `strategies/a.py`'s params. Exit: `load_market` on a seeded test schema returns the right `Market` (bars via one streamed `COPY ... TO STDOUT`, universe, fx); the cache is written to and reused from `cache_dir` keyed by `(max(date), count(*))`, and a changed fingerprint invalidates it; the command, pointed at a synthetic test DB with short windows, writes the three report files, logs the gate verdict, exits 0, and writes nothing to the DB; the command module passes `discover()`; the grid's wall time is logged per run and in total; window names are `WINDOW_NAMES`; `--cache-dir` keeps the test cache out of the repo. 25 new tests; suite **595**, 0 skipped.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_BACKTEST_PLAN.md` (phase 5 of 6)
  - **Satisfies**: R5 — Backtest report (curves vs SPY, return, CAGR, win rate, PF, max DD, trades, exit reasons, go-live criteria, IS/OOS separately, survivorship note, gate verdict), metrics identical to `web/lib/metrics.ts`; R6 — One real 10-year run on Neon, report committed, gate verdict stated, API documented in `engine/package_readme.md`, suite green with 0 skipped, CI green
  - **Depends on**: P1-ENG-VTZ5
  - **Plan**: `.workflows/plan/P1-ENG-5LGI.md`
  - **Completed**: 2026-10-03 15:40
  - **Method**: /do
  - **Files**: .gitignore, engine/src/seer_engine/backtest/io.py, engine/src/seer_engine/commands/backtest.py, engine/tests/test_backtest_io.py, engine/tests/test_backtest_command.py
- [x] **P1-ENG-VTZ5** Phase 4: Metrics (web parity), grid + selection + gate, report rendering
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/backtest/{metrics,tuning,report}.py` (new), `engine/tests/test_backtest_metrics.py`, `engine/tests/test_backtest_tuning.py`, `engine/tests/test_backtest_report.py` (new). Does not touch `market.py`, `runner.py`, `benchmark.py`, `strategies/*`. Exit: handover §6 item 6: `strategy_metrics`/`checklist` reproduce every case of `web/lib/metrics.test.ts` with the same inputs; CAGR, avg days held and exit-reason counts tested; `grid()` is the exact 81 in the stated order; `select` picks the highest IS return among `max_dd ≤ 0.15 and PF ≥ 1.3` with the stated tie-break, and falls back to `DESIGN_PARAMS` when none qualifies; `gate` passes only when OOS return > OOS total-return SPY, PF ≥ 1.3 and max DD ≤ 0.15; `render_markdown`/`equity_csv`/`equity_svg` are deterministic and contain every required section (built from a small synthetic `BacktestReport`); the `frozen-params:`/`selected-params:` lines round-trip through `parse_params_line`. 67 new tests; suite **570**, 0 skipped.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_BACKTEST_PLAN.md` (phase 4 of 6)
  - **Satisfies**: R4 — Tune on in-sample with the fixed 81-run grid, validate once on out-of-sample, freeze params in code; R5 — Backtest report (curves vs SPY, return, CAGR, win rate, PF, max DD, trades, exit reasons, go-live criteria, IS/OOS separately, survivorship note, gate verdict), metrics identical to `web/lib/metrics.ts`
  - **Depends on**: P1-ENG-3WDD, P1-ENG-HCER
  - **Plan**: `.workflows/plan/P1-ENG-VTZ5.md`
  - **Completed**: 2026-10-03 15:37
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/metrics.py, engine/src/seer_engine/backtest/tuning.py, engine/src/seer_engine/backtest/report.py, engine/tests/test_backtest_metrics.py, engine/tests/test_backtest_tuning.py, engine/tests/test_backtest_report.py
  - **Drift**: none — all six files are the plan's code blocks applied verbatim
    manual SVG light/dark visual check skipped: no SVG rasterizer (rsvg-convert/cairosvg) on this machine; synthetic SVG determinism/no-nan/no-inf tests pass; the real SVG is reviewed in phase 6
- [x] **P1-ENG-HCER** Phase 3: Point-in-time market + backtest runner + survivorship
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/backtest/market.py`, `engine/src/seer_engine/backtest/runner.py` (new), `engine/tests/test_backtest_market.py`, `engine/tests/test_backtest_runner.py` (new). Does not touch `benchmark.py`, `strategies/*` (consumes them), `stratkit.py` (may import its builders; add local helpers in its own test files). Exit: handover §6 items 4 and 7 (runner side): `Membership.members_on` honours `[start, end)` and unions both indices; `Market.bar` returns exact 4-dp Decimals from floats; a synthetic multi-symbol backtest through `size_picks` → `step` → `close_unpriced` with hand-checked final cash, equity and trade list, including a held symbol whose bars end (forced `close_unpriced` exactly once, at the first session after its last bar) and a session with 0 picks; a 3-session halt (bars resume) does not force-close; members are evaluated on `data_date`; the run with `prepared=` equals the run without it; two runs are `==`; non-session windows raise; `survivorship` counts per year are hand-checked. 23 new tests; suite **471** (or **503** after phase 2), 0 skipped.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_BACKTEST_PLAN.md` (phase 3 of 6)
  - **Satisfies**: R2 — Backtest runner over the point-in-time universe, every NYSE session, `size_picks` → `step` → `close_unpriced`, delisting handled
  - **Depends on**: P1-ENG-WHQG
  - **Plan**: `.workflows/plan/P1-ENG-HCER.md`
  - **Completed**: 2026-10-03 15:34
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/market.py, engine/src/seer_engine/backtest/runner.py, engine/tests/test_backtest_market.py, engine/tests/test_backtest_runner.py
  - **Drift**: none — the plan's four code blocks applied verbatim
  - **Decided**: readme-updater on engine/package_readme.md this phase? → skipped (rung 1: index Scope + phase 3 'Leaves alone' assign the readme to phase 6)
- [x] **P1-ENG-3WDD** Phase 2: SPY buy-and-hold benchmark + vendored dividends
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/backtest/benchmark.py` (new), `engine/data/spy_dividends.csv` (new, fetched once with yfinance `Ticker("SPY").dividends`, 2015-01-01 → today), `engine/data/SOURCES.md` (add its entry), `engine/tests/test_benchmark.py` (new). Does not touch `market.py`, `runner.py`, anything in `strategies/`. Exit: handover §6 item 5: price-only and total-return curves on synthetic bars plus a dividend, including whole-share purchase at the first session's open after the 0.1% cost, an idle cash remainder, a dividend on the ex-date reinvested at that close (whole shares, with cost), a dividend dated on the start session not credited, a missing SPY bar raising, an in-window ex-date that is not a session raising, and the vendored CSV parsing cleanly (ascending, unique, positive, every ex-date a session, covers 2015–2026). 32 new tests; suite **480** (or **503** after phase 3), 0 skipped.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_BACKTEST_PLAN.md` (phase 2 of 6)
  - **Satisfies**: R3 — SPY buy-and-hold curves (price-only and total-return), same 0.1% costs and whole-share rule
  - **Depends on**: P1-ENG-WHQG
  - **Plan**: `.workflows/plan/P1-ENG-3WDD.md`
  - **Completed**: 2026-10-03 15:33
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/benchmark.py, engine/data/spy_dividends.csv, engine/data/SOURCES.md, engine/tests/test_benchmark.py
  - **Drift**: none — plan code blocks applied verbatim; yfinance 1.7.0 fetch on 2026-10-03 reproduced the probe exactly (47 rows 2015-03-20..2026-09-18, sha256 3251a8525bfcb6e1e3fe7b74db88326122826c808be5a6005eba767fbb5b598a)
- [x] **P1-ENG-WHQG** Phase 1: Strategy interface, indicators, Strategy A
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/pyproject.toml` (declare `numpy>=2`), `engine/src/seer_engine/strategies/{__init__,base,indicators,a}.py` (new), `engine/src/seer_engine/backtest/__init__.py` (new, docstring only), `engine/tests/stratkit.py` (new synthetic `History` builders), `engine/tests/test_indicators.py`, `engine/tests/test_strategy_a.py`, `engine/tests/test_strategy_purity.py` (new; globs `strategies/*.py` and `backtest/*.py` minus `io.py`). Does not touch `sim/*`, `test_sim_purity.py`, any other `backtest/` module, readme. Exit: handover §6 items 1, 2, 3 and 8 (for the strategy modules): each indicator matches hand-computed values on short synthetic windows including the warm-up boundary (NaN before enough bars); `rolling(...)[t]` is bit-identical (`==`, not approx) to the window function on the last W bars ending at t; changing any bar dated ≥ S leaves the picks for session S (data_date = prev_session(S)) unchanged; `picks_prepared(prepare(H), …) == picks(upto(d), …)` on every date of a multi-symbol synthetic set; setup filter tests for each condition alone; limit/TP/SL to 4 dp; RSI ranking with symbol tie-break; invalid prices dropped; non-members excluded, including a symbol joining and one leaving mid-window. 74 new tests; suite **448 passed**, 0 skipped.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_BACKTEST_PLAN.md` (phase 1 of 6)
  - **Satisfies**: R1 — Strategy A signals from data through `data_date` only → ranked `sim.Pick`s, behind a small pure strategy interface shared with P4/P6
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-WHQG.md`
  - **Completed**: 2026-10-03 15:28
  - **Method**: /do
  - **Files**: engine/pyproject.toml, engine/src/seer_engine/strategies/__init__.py, engine/src/seer_engine/strategies/base.py, engine/src/seer_engine/strategies/indicators.py, engine/src/seer_engine/strategies/a.py, engine/src/seer_engine/backtest/__init__.py, engine/tests/stratkit.py, engine/tests/test_indicators.py, engine/tests/test_strategy_a.py, engine/tests/test_strategy_purity.py
  - **Drift**: None — every code block applied verbatim from the plan.
  - **Decided**: `-f` path `.workflows/orchestration/strategy-a-backtest/PLAN.md` does not exist in the worktree → used `STRATEGY_A_BACKTEST_PLAN.md` at worktree root (same slug; confirmed by coordinator orch-strategy-a-backtest)

- [x] **P1-ENG-SEZ7** Phase 4: Public API, scenario, determinism, benchmark, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sim/__init__.py` (add the sizing and split exports), `engine/tests/test_sim_scenario.py` (new), `engine/package_readme.md` (`sim` + `prices` sections, layout, performance, P3/P4 usage loop), `docs/ROADMAP.md` (P2 status line). Exit: a ≥10-session, 4-slot, mixed-outcome scenario with hand-checked final cash, every snapshot's equity, and every closed trade's `pnl_usd` (12 sessions; final cash 985.0996, final equity 1340.5996, Σ pnl 84.6604). Running the scenario twice gives identical outputs. A benchmark of 2,950 sessions × 4 slots finishes under a generous bound, and the measured time is written in the readme. The readme documents the API for P3 and P4. Suite green with 0 skipped.
  - **Status**: completed
  - **Plan Set**: `ENGINE_FILL_SIMULATOR_PLAN.md` (phase 4 of 4)
  - **Satisfies**: R4 — Small pure deterministic API for P3/P4, import-purity test, ≥10-session hand-checked scenario, documented in `engine/package_readme.md`
  - **Depends on**: P1-ENG-2PWS, P1-ENG-56QL (both done 2026-10-03)
  - **Plan**: `.workflows/plan/P1-ENG-SEZ7.md`
  - **Completed**: 2026-10-03 14:30
  - **Method**: /do
  - **Files**: engine/src/seer_engine/sim/__init__.py, engine/tests/test_sim_scenario.py, engine/package_readme.md, docs/ROADMAP.md
  - **Drift**: Phase 1 had already added prices.py to the readme Layout, the prices note in the bars section and the bars->prices line in the module graph. Phase 4 Step 3 was applied by intent: the bars section's prices bullets were collapsed into the plan's single re-export bullet, the new ### prices section was added, and the existing module-graph line was reworded instead of duplicated. The 'sim/ ... in progress' layout line was replaced with the full sim/ subtree.
  - **Verified**: export check ok (24 names); test_sim_scenario 11 passed, benchmark 2950 sessions x 4 slots in ~0.20 s; full suite 374 passed, 0 skipped

- [x] **P1-ENG-2PWS** Phase 2: Whole-share sizing of picks into slots
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sim/sizing.py` (new), `engine/tests/test_sim_sizing.py` (new). Exit: tests for whole-share sizing, equity ÷ 4 from the last snapshot, the cash cap with earlier placements that night, `lt_one_share`, `held` (no adding, including a symbol already pending and a duplicate pick), `no_slot`, 0 picks, the lowest free slot first in pick order, slot reuse after an exit or expiry on the same session (driven through `step`), and validation errors. Suite green.
  - **Status**: completed
  - **Plan Set**: `ENGINE_FILL_SIMULATOR_PLAN.md` (phase 2 of 4)
  - **Satisfies**: R2 — Whole-share sizing, 4 slots, equity ÷ 4 recomputed daily, cash cap, ineligible < 1 share, no adding, 0 picks valid
  - **Depends on**: P1-ENG-DQFG
  - **Plan**: `.workflows/plan/P1-ENG-2PWS.md`
  - **Completed**: 2026-10-03 14:27
  - **Method**: /do
  - **Files**: engine/src/seer_engine/sim/sizing.py, engine/tests/test_sim_sizing.py

- [x] **P1-ENG-56QL** Phase 3: Split recompute for live orders
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sim/split_adjust.py` (new), `engine/tests/test_sim_split.py` (new). Exit: tests for a forward split (10:1, 3:2) and a reverse split (1:32, 1:3 with a fractional remainder → cash in lieu) on an open position and on a pending order, a pending order flooring to 0 → `expire` event, an open position flooring to 0 → forced `exit` paid in lieu, prices that 4 dp cannot hold → `ValueError` with the input untouched, symbols not affected, `marks` rescaled, and a split followed by `step` on adjusted bars giving the same economic P/L. Suite green.
  - **Status**: completed
  - **Plan Set**: `ENGINE_FILL_SIMULATOR_PLAN.md` (phase 3 of 4)
  - **Satisfies**: R5 — Pure split-recompute function for live orders (forward and reverse)
  - **Depends on**: P1-ENG-DQFG
  - **Plan**: `.workflows/plan/P1-ENG-56QL.md`
  - **Completed**: 2026-10-03 14:26
  - **Method**: /do
  - **Files**: engine/src/seer_engine/sim/split_adjust.py, engine/tests/test_sim_split.py

- [x] **P1-ENG-DQFG** Phase 1: Pure price types, sim model and session lifecycle
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/prices.py` (new), `engine/src/seer_engine/bars.py` (move `Bar`/`PRICE_QUANTUM`/`to_decimal` out, re-export), `engine/src/seer_engine/sim/__init__.py`, `sim/model.py`, `sim/lifecycle.py`, `engine/tests/simkit.py`, `engine/tests/test_sim_lifecycle.py`, `engine/tests/test_sim_purity.py`. Exit: `step` and `close_unpriced` implement every lifecycle rule and decision. A test exists for each lifecycle edge case in handover §6.1: touch vs penetrate for entry/TP/SL, open < limit, gap SL → `gap`, gap TP → `tp`, same-bar SL first, no check on the fill session, time stop at the day-6 open across a holiday and a half day, expiry, costs and `pnl_usd` to the cent, slot freed after an exit, a missing bar for a held symbol, a missing bar for a pending order, and `close_unpriced`. The purity subprocess test passes. The full suite is green with 0 skipped.
  - **Status**: completed
  - **Plan Set**: `ENGINE_FILL_SIMULATOR_PLAN.md` (phase 1 of 4)
  - **Satisfies**: R1 — Order lifecycle `pending → open → closed` / `pending → expired` exactly as design §5 + handover §3; R3 — Cash/equity per portfolio, 0.1% cost per side, `pnl_usd`, per-session equity snapshot; R4 — Small pure deterministic API for P3/P4, import-purity test, ≥10-session hand-checked scenario, documented in `engine/package_readme.md`
  - **Plan**: `.workflows/plan/P1-ENG-DQFG.md`
  - **Completed**: 2026-10-03 14:23
  - **Method**: /do
  - **Files**: engine/src/seer_engine/prices.py, engine/src/seer_engine/bars.py, engine/src/seer_engine/sim/__init__.py, engine/src/seer_engine/sim/model.py, engine/src/seer_engine/sim/lifecycle.py, engine/tests/simkit.py, engine/tests/test_sim_lifecycle.py, engine/tests/test_sim_purity.py

- [x] **P1-ENG-VP1R** Phase 1: Engine foundation: package, migration 002, dates, DB helpers, demo purge
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/pyproject.toml` (incl. pytest config), `engine/.gitignore`, `engine/src/seer_engine/{__init__,__main__,cli,config,db,http,dates,demo,universe,bars,fx,runs}.py`, `commands/{__init__,migrate}.py`, `db/migrations/002_engine.sql`, and `engine/tests/{conftest,test_dates,test_cli,test_migrate,test_bars,test_fx,test_runs,test_demo,test_universe_queries,test_http}.py`. Does not touch membership loading, non-Frankfurter sources, `.github/`, `web/`, root `.gitignore`, Neon. Exit: `python -m seer_engine --help` lists `migrate`; `--dry-run migrate` against `PG_TEST_URL` exits 0 and leaves no `schema_migrations`; 101 tests pass against Postgres 16 (container `seer-pg`, port 55432) with 0 skipped, incl. handover §6.4 date cases; a second identical `upsert_bars`/`upsert_fx` returns 0 and leaves `xmin` unchanged.
  - **Status**: done
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 1 of 5)
  - **Satisfies**: R2 — Point-in-time S&P 500 ∪ Nasdaq-100 membership in a new table (migration 002); R4 — Every step idempotent for the same date; R5 — First real engine write deletes all demo data atomically; R6 — Unit tests (dates, adjustment, idempotent upserts) and a dry-run mode that writes nothing
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-VP1R.md`
  - **Completed**: 2026-10-03 12:51
  - **Method**: /do
  - **Files**: engine/pyproject.toml, engine/.gitignore, db/migrations/002_engine.sql, engine/src/seer_engine/{__init__,__main__,cli,config,db,http,dates,demo,universe,bars,fx,runs}.py, engine/src/seer_engine/commands/{__init__,migrate}.py, engine/tests/{conftest,test_dates,test_cli,test_migrate,test_bars,test_fx,test_runs,test_demo,test_universe_queries,test_http}.py

- [x] **P1-ENG-GF8Y** Phase 4: Nightly command: Massive bars, splits, FX, runs
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/massive.py`, `splits.py`, `commands/nightly.py`, `engine/tests/{test_massive,test_splits,test_nightly}.py`. Does not touch backfill, membership, `.github/`, Neon. Exit: `nightly` computes `RunDates`, no-ops when that session already succeeded, else fetches every missing session up to `data_date` via grouped daily (≤ 30, calls ≥ 12.5 s apart), applies every split in the gap once (`split_adjustments`; guard "stored bar on/after execution date → already adjusted", then ratio heuristic for `|ln f| ≥ ln 1.25`) before upserting fetched bars, upserts FX, finishes the run — all bars/splits/FX/run-success in one transaction; failures mark the run failed (exit 1) with no bars written; missing key exits 2; dry-run writes nothing; checksum test proves a same-`now` re-run leaves `bars`, `fx_rates`, `runs`, `split_adjustments` identical.
  - **Status**: done
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 4 of 5)
  - **Satisfies**: R3 — Nightly Actions job: Massive bars + Frankfurter FX + `runs` row with correct dates; failed fetch → `failed` run, no partial bars; R4 — Every step idempotent for the same date; R6 — Unit tests (dates, adjustment, idempotent upserts) and a dry-run mode that writes nothing
  - **Depends on**: P1-ENG-VP1R
  - **Plan**: `.workflows/plan/P1-ENG-GF8Y.md`
  - **Completed**: 2026-10-03 12:56
  - **Method**: /do
  - **Files**: engine/src/seer_engine/splits.py, engine/src/seer_engine/massive.py, engine/src/seer_engine/commands/nightly.py, engine/tests/test_massive.py, engine/tests/test_splits.py, engine/tests/test_nightly.py
  - **Decided**: readme-updater/pusher chain vs coordinator 'do not push' → commit locally only, skip readme-updater and push (rung 5: coordinator -note; plan scope already excludes git push)

- [x] **P1-ENG-L73U** Phase 3: yfinance + FX history backfill
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/yahoo.py`, `commands/backfill.py`, `engine/tests/test_backfill.py`. Does not touch Massive, `runs`, `split_adjustments`, `universe` contents, membership loading. Exit: `backfill` (default start 2015-01-02, end = `last_completed_session(now)`, overridable with `--end`) loads `all_symbols(since=start)` in throttled batches of 40, records every symbol in `backfill_log` (`ok` / `empty` = no Yahoo data / `failed` = rate limit or error), skips every already-logged symbol by default (`--retry-failed` re-attempts `failed`+`empty`, `--symbols` ignores the log), loads Frankfurter history into `fx_rates`; exit 0 unless a symbol is `failed` or FX failed (1) or the universe is empty (2); re-run changes nothing; 32 tests with an injected fake downloader pass against `PG_TEST_URL`.
  - **Status**: done
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 3 of 5)
  - **Satisfies**: R1 — Backfill 10+ years of split-adjusted daily bars for every ever-member (yfinance), logging unfetchable symbols; R4 — Every step idempotent for the same date; R6 — Unit tests (dates, adjustment, idempotent upserts) and a dry-run mode that writes nothing
  - **Depends on**: P1-ENG-VP1R
  - **Plan**: `.workflows/plan/P1-ENG-L73U.md`
  - **Completed**: 2026-10-03 13:05
  - **Method**: /do
  - **Files**: engine/src/seer_engine/yahoo.py, engine/src/seer_engine/commands/backfill.py, engine/tests/test_backfill.py

- [x] **P1-ENG-853Z** Phase 2: Point-in-time universe membership
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/data/{sp500_history.csv, ndx_history.csv, ticker_aliases.csv, membership_overrides.csv, SOURCES.md}`, `engine/src/seer_engine/membership.py`, `commands/universe.py` (`universe refresh`, `universe check`), `engine/tests/test_membership.py`. Does not touch `universe.py` queries or other phase-1 files, `bars`, `.vercelignore`. Exit: `universe refresh` replaces the `universe` table in one transaction and prints `unchanged, nothing written` on re-run; `--dry-run universe refresh` leaves the table untouched; `universe check` exits 0 on live Wikipedia pages and 1 on any diff (tested); 29 tests in `test_membership.py` cover interval building, overrides and aliases; full suite green.
  - **Status**: done
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 2 of 5)
  - **Satisfies**: R2 — Point-in-time S&P 500 ∪ Nasdaq-100 membership in a new table (migration 002); R4 — Every step idempotent for the same date; R6 — Unit tests (dates, adjustment, idempotent upserts) and a dry-run mode that writes nothing
  - **Depends on**: P1-ENG-VP1R
  - **Plan**: `.workflows/plan/P1-ENG-853Z.md`
  - **Completed**: 2026-10-03 13:10
  - **Method**: /implement
  - **Commit**: 4ea9360
  - **Files**: engine/data/{sp500_history.csv, ndx_history.csv, ticker_aliases.csv, membership_overrides.csv, SOURCES.md}, engine/src/seer_engine/membership.py, engine/src/seer_engine/commands/universe.py, engine/tests/test_membership.py
  - **Verified**: test_membership 29/29, suite 216 passed (seer-pg); local refresh 1544 rows then "unchanged, nothing written"; universe check identical SP500 503 / NDX 101

---

## Archive
