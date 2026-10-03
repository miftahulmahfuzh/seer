# Todos: engine

**Package Path**: `engine`
**Package Code**: ENG
**Last Updated**: 2026-10-03 18:48:27
**Total Active Tasks**: 6

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 6
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 4
- Completed: 21

---

## Active Tasks

### [P0] Critical

### [P1] High
- [ ] **P1-ENG-1OMN** Phase 2: B features, ranks, candidates, `StrategyB`
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns additive `mean_window` and `stdev_return_window` in `strategies/indicators.py` (tests in new `tests/test_indicators_b.py`), new `strategies/b.py` exactly as the index contract, `strategies/__init__.py` exports from `b.py` only (never imports `b_model`), and new `tests/test_strategy_b.py` (every feature hand-computed; `prepare_b` vs `design_at` bit-identity; `rank01` ties and n=0/1; ranks from members on d only; SPY features through d, no candidates when SPY missing/short; `picks_from_design` positive-only, symbol tie-break order, invalid-bracket drop; P4 identity over several dates and fake models; no look-ahead incl. SPY bars from S on; SPY never picked; `SPY_SYMBOL == universe.BENCHMARK`; `MIN_DOLLAR_VOLUME == a.DESIGN_PARAMS.min_dollar_volume`). Does not touch `a.py`, `a2.py`, `base.py`, existing indicators, `b_model.py`, `backtest/`. Exit: suite green, 0 skipped (+59: 11 + 48); purity glob covers `b.py`; `import seer_engine.strategies` loads no `sklearn`; `STRATEGY_B_FROZEN` not re-exported (D24).
  - **Status**: in_progress
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 2 of 7)
  - **Satisfies**: R2 — Features. Each is hand-computed. The rolling and single-window paths are bit-identical. Ranks use that date's candidates only, ties averaged. SPY features read SPY's bars through `data_date` only; R3 — P4 identity and no look-ahead, for B and B-linear, with a fixed model. SPY bars dated ≥ S are included; R6 — Purity. The new modules pass the globbing purity test
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-1OMN.md`
- [x] **P1-ENG-DKWU** Phase 3: Vectorized bracket labeler
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `backtest/labels.py` exactly as the index contract and new `tests/test_backtest_labels.py`: synthetic bars for every path (no fill: no bar / low >= limit; fill at limit; fill at open when open < limit; TP and SL intraday; both in range -> SL first; gap through SL / TP at the open; day-5 time stop; time stop delayed by a missing bar; forced close after the last bar; unresolved at the end), every label net of 0.1% per side, sim parity on a seeded synthetic market for a few thousand rows vs `run_backtest` with a one-pick fake strategy (same exit reason, `forced` ~ sim `time` with `forced=True`, same exit date or expiry, return within 1e-6; RNG allowed in the test only), and mutating bars after a row's resolved date leaves its label unchanged. Does not touch `sim/`, `runner.py`, `strategies/`. Exit: suite green, 0 skipped (+30); purity glob covers the module.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 3 of 7)
  - **Satisfies**: R1 — Labels. Synthetic tests cover every label path. The vectorized labeler agrees with a one-order `sim` run on a seeded sample. Changing a bar after `tune_end(Y)` leaves fold Y's training set unchanged; R6 — Purity. The new modules pass the globbing purity test
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-DKWU.md`
  - **Completed**: 2026-10-03 18:48
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/labels.py, engine/tests/test_backtest_labels.py
  - **Decided**:
    - Step 3 task creation in a concurrent swarm -> left to phase 1's session, which created all 7 tasks (P1-ENG-DKWU is phase 3) (tie-break: narrower blast radius, avoid racing peers on todos.md)
    - readme-updater -> skipped for this phase; engine/package_readme.md is owned by phase 7 per the plan index Scope/phase 7 Owns (rung 4: index scope)
- [ ] **P1-ENG-U5JJ** Phase 4: B walk-forward: candidate table, purge, per-fold fits, runs, diagnostics, gate
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `backtest/b_walkforward.py` exactly as the index contract (`FoldModel` value equality D20, `calibration` drops NaN labels itself D21, `gate_p6a` changes only the subject for B-linear D22, `passed_nights` traded == `len(run.snapshots) - 1`, five private `walkforward.py` helpers imported read-only D26) and new `tests/test_backtest_b_walkforward.py` (35 tests on synthetic markets: `CandidateTable` rows equal `design_on`; purge -- mutating bars after `tune_end(Y)` leaves fold Y's mask, X, labels and model digest unchanged; folds equal `walkforward.folds`; `train_folds` for both kinds; schedule switches at year starts and a 31 Dec open order keeps its bracket; P4 identity with real tree and ridge `BParams`; `oos_predictions` uses the right fold's model; hand-checked calibration deciles; passed nights equal empty-pick sessions; `gate_p6a` sentences in both kinds and outcomes; two identical calls give `==`; `probe_determinism` True on synthetic data). Does not touch `walkforward.py` or any out-of-scope file. Exit: suite green, 0 skipped (914); purity glob covers the module.
  - **Status**: blocked
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 4 of 7)
  - **Satisfies**: R1 — Labels. Synthetic tests cover every label path. The vectorized labeler agrees with a one-order `sim` run on a seeded sample. Changing a bar after `tune_end(Y)` leaves fold Y's training set unchanged; R3 — P4 identity and no look-ahead, for B and B-linear, with a fixed model. SPY bars dated ≥ S are included; R4 — Walk-forward. The folds are exactly P3b's. Training uses purged labels only. One chained portfolio, whose brackets survive the year boundary. `backtest_wf`'s A2 report stays byte-identical; R5 — Determinism. `==` results and byte-identical files. The gated model is bit-identical across runs and thread counts, or the pre-registered switch to B-linear takes effect; R6 — Purity. The new modules pass the globbing purity test
  - **Depends on**: P1-ENG-CW71, P1-ENG-1OMN, P1-ENG-DKWU
  - **Plan**: `.workflows/plan/P1-ENG-U5JJ.md`
- [ ] **P1-ENG-VK5P** Phase 5: B report rendering
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `backtest/b_report.py` (`BReport` with `curves()`/`gated_curve()`, `_validate`, `top_features`, machine lines with `label_sum` as a JSON string of `repr(float)` D23, `render_markdown`, `equity_csv`, `equity_svg`; Markdown sections in order: title, data, method, per-fold training summary for B and B-linear, results vs both SPY curves, year by year, diagnostics incl. passed nights and calibration, seen before, go-live checklist, survivorship with learned-model caveat, open positions, curves SVG link, verdict sentence, owner's options (b)/(c)/(d) on a fail, machine fence) and new `tests/test_backtest_b_report.py` (27 tests from a small synthetic run via phase 4's API). Does not touch `wf_report.py` or `report.py` (helpers imported only). Exit: suite green, 0 skipped (941); rendering twice is byte-identical; `_validate` rejects a mismatched verdict, a misaligned curve and a schedule not matching `fold_models`.
  - **Status**: blocked
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 5 of 7)
  - **Satisfies**: R5 — Determinism. `==` results and byte-identical files. The gated model is bit-identical across runs and thread counts, or the pre-registered switch to B-linear takes effect; R6 — Purity. The new modules pass the globbing purity test; R7 — One real run on Neon, with the committed report holding every section §6.7 lists
  - **Depends on**: P1-ENG-U5JJ
  - **Plan**: `.workflows/plan/P1-ENG-VK5P.md`
- [ ] **P1-ENG-UREW** Phase 6: `backtest_b` command + io writers
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns additive `backtest/io.py` (`MODELS_DIR`, `write_b_report`, `write_model_artifact`; the only phase editing `io.py`), new `commands/backtest_b.py` incl. public `recompute_a2(market, folds)` with eager imports (every CLI command now loads scikit-learn via `cli.discover`, D19), and new `tests/test_backtest_b_command.py` (23 tests: `execute` twice on a synthetic market gives `==` reports and byte-identical files; gate pass writes the artifact, fail does not; exit 2 on a precondition; A2 curve equals `backtest_wf`'s combined curve; wall times in logs only; synthetic-market helpers live in the test file). Does not touch `backtest_wf.py` (imported only) or `cli.py`. Exit: suite green, 0 skipped (964); `python -m seer_engine backtest_b --help` works.
  - **Status**: blocked
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 6 of 7)
  - **Satisfies**: R5 — Determinism. `==` results and byte-identical files. The gated model is bit-identical across runs and thread counts, or the pre-registered switch to B-linear takes effect; R7 — One real run on Neon, with the committed report holding every section §6.7 lists
  - **Depends on**: P1-ENG-VK5P
  - **Plan**: `.workflows/plan/P1-ENG-UREW.md`
- [ ] **P1-ENG-M99E** Phase 7: Real run on Neon, A2 byte-identity check, freeze or stop, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns the real `backtest_b` run on Neon from the worktree (`SEER_ENV_FILE`; record data end, wall time, peak RSS); re-run `backtest_wf --end 2026-10-02 --out <scratch>` and `cmp` all 5 files against committed `docs/backtests/2026-10-02-strategy-a2-walkforward*` (a difference stops the phase); commit the B report set. On a pass: set `STRATEGY_B_FROZEN` in `b.py` (report, artifact, `train_end`, sha256; only that line and its two comment lines), commit the artifact, re-run so the report records `frozen-model`, and `tests/test_strategy_b_frozen.py` (6 tests) asserts constant == machine line, sha256 of artifact bytes, and `loads(artifact).digest` == last-fold digest (D23-D25). On a fail: constant stays None and the test asserts `failed`, `frozen-model: null` and no artifact under `engine/data/models/`. Docs: `engine/package_readme.md` (B, labeler, features, model, `backtest_b`, performance, module graph) and `docs/ROADMAP.md` (P6a verdict; on a fail, B's one round failed, P4 stays blocked, owner's options). Exit: suite green, 0 skipped (970 plus any Bug-protocol regression tests), CI green, report committed.
  - **Status**: blocked
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 7 of 7)
  - **Satisfies**: R4 — Walk-forward. The folds are exactly P3b's. Training uses purged labels only. One chained portfolio, whose brackets survive the year boundary. `backtest_wf`'s A2 report stays byte-identical; R7 — One real run on Neon, with the committed report holding every section §6.7 lists; R8 — Freeze or stop. **Pass:** artifact + constant + tie test. **Fail:** ROADMAP records the failure, P4 stays blocked, and the report lists the owner's options; R9 — The readme documents B. The suite is green with 0 skipped. CI is green with scikit-learn
  - **Depends on**: P1-ENG-UREW
  - **Plan**: `.workflows/plan/P1-ENG-M99E.md`

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

---

## Completed Tasks
- [x] **P1-ENG-CW71** Phase 1: B model interface + scikit-learn dependency
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/pyproject.toml` (scikit-learn pin `>=1.9,<1.10`), new `strategies/b_model.py` exactly as the index contract, and new `tests/test_b_model.py` (synthetic fit/predict; ridge vs a hand-solved case; per-row batch independence for both kinds; two fits give `==` models with equal digests; thread-count determinism via subprocesses at `OMP_NUM_THREADS` 1 and 4 on ~50k x 18 rows; `dumps`/`loads` round trip keeps predictions and digest; importance shares sum to 1; `r2`; input validation; purity glob covers the module). Does not touch `b.py`, `strategies/__init__.py` or `backtest/`. Exit: suite green, 0 skipped (790 alone); `pip install -e 'engine[dev]'` pulls scikit-learn 1.9.x; artifact identity is sha256 of file bytes and `loads(b).digest`, never re-pickled bytes (D25).
  - **Status**: completed
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 1 of 7)
  - **Satisfies**: R5 — Determinism. `==` results and byte-identical files. The gated model is bit-identical across runs and thread counts, or the pre-registered switch to B-linear takes effect; R6 — Purity. The new modules pass the globbing purity test; R9 — The readme documents B. The suite is green with 0 skipped. CI is green with scikit-learn
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-CW71.md`
  - **Completed**: 2026-10-03 18:48
  - **Method**: /do
  - **Files**: engine/pyproject.toml, engine/src/seer_engine/strategies/b_model.py, engine/tests/test_b_model.py
- [x] **P1-ENG-RTWR** Phase 6: Real run on Neon, freeze or stop, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns one real `backtest_wf` run with committed `docs/backtests/<end>-strategy-a2-walkforward{.md,-equity.csv,-equity.svg,-variants.svg,-grid.csv}`; on pass replace the placeholder with an `A2Params(...)` literal of the last fold selection + comment naming the report and re-run, on fail leave `None`; `tests/test_strategy_a2_frozen.py` asserts the branch taken; v1 byte-identity check vs committed `2026-10-02-strategy-a.*` (D9); `docs/ROADMAP.md` P3b line with verdict (fail: one rework failed, P4 stays blocked); `engine/package_readme.md` (strategies A2/variants, backtest schedule/`metrics_through`/walkforward/wf_report, `backtest_wf` section, `## Performance`, Usage). Does not touch pure-module logic except tested, logged defect fixes. Exit: report committed; frozen test green; v1 identity verified; suite green, 0 skipped (761); CI green on push.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_REWORK_PLAN.md` (phase 6 of 6)
  - **Satisfies**: R6 — One real walk-forward run on Neon, with a committed report holding fold selections and tables, per-variant curves, WF vs both SPY curves, diagnostics, the "seen before" window, the survivorship note and the P3b verdict sentence; R7 — Freeze or stop: on a pass, frozen A2 params with a comment naming the report and a code↔report test; on a fail, ROADMAP records that the one rework failed and P4 stays blocked, and the report lists what was tried; R8 — The v1 `backtest` report is byte-identical when re-run on the same data; `engine/package_readme.md` documents the variants, walk-forward and the new command; the suite is green with 0 skipped; CI is green
  - **Depends on**: P1-ENG-U4G0
  - **Plan**: `.workflows/plan/P1-ENG-RTWR.md`
  - **Completed**: 2026-10-03 17:55
  - **Method**: /do
  - **Files**: docs/backtests/2026-10-02-strategy-a2-walkforward.md, docs/backtests/2026-10-02-strategy-a2-walkforward-equity.csv, docs/backtests/2026-10-02-strategy-a2-walkforward-equity.svg, docs/backtests/2026-10-02-strategy-a2-walkforward-variants.svg, docs/backtests/2026-10-02-strategy-a2-walkforward-grid.csv, engine/tests/test_strategy_a2_frozen.py, engine/package_readme.md, docs/ROADMAP.md
  - **Outcome**: P3b gate FAILED — walk-forward 2018-01-02..2026-10-02 +9.1% vs SPY total-return +187.6%, PF 1.02, max DD 29.1%. `STRATEGY_A2_PARAMS` stays `None`; Strategy A's one rework failed; P4 stays blocked. Re-run byte-identical; v1 report byte-identical on unchanged Neon data; suite 761 passed, 0 skipped.
  - **Drift**: engine/package_readme.md had 'full docs pending phase 6' layout stubs added by phases 1-5's readme updates, so plan Step 9's line numbers were stale; edits were applied by anchor text and the stub lines replaced with the plan's final wording. Synopsis also lists --dry-run/-v, which the command has.
  - **Decided**: readme edits anchored by text instead of plan line numbers → anchor (rung 6: plan line numbers drifted; content as plan's code blocks, rung 3)
- [x] **P1-ENG-U4G0** Phase 5: `backtest_wf` command + `write_wf_report`
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `io.write_wf_report` and `commands/backtest_wf.py` (args, `resolve` preconditions mirroring v1 exit-2 cases, `tune_all` per-combination timing via `walkforward.tune` (D17), `run_walk_forward`, `execute` building SPY curves + verdict as `wf_report._validate` recomputes; logs prepare time, per-combo/total tuning time, per-fold selections, verdict, `STRATEGY_A2_PARAMS` match) plus `tests/test_backtest_wf_command.py` (discovery/defaults, exit-2 cases, end-to-end on synthetic PG schema spanning >= 2 trade years: read-only, five file names, cache hit, byte-identical re-run). Does not touch `commands/backtest.py`, `report.py`, `walkforward.py`, `wf_report.py` (except logged defect fixes). Exit: suite green, 0 skipped (757); `python -m seer_engine backtest_wf --help` works; `tune_all == tune` on a subset tested.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_REWORK_PLAN.md` (phase 5 of 6)
  - **Satisfies**: R4 — Determinism: `==` results and byte-identical files; a parallel gather, if any, comes back in a fixed order; R6 — One real walk-forward run on Neon, with a committed report holding fold selections and tables, per-variant curves, WF vs both SPY curves, diagnostics, the "seen before" window, the survivorship note and the P3b verdict sentence
  - **Depends on**: P1-ENG-BVN5
  - **Plan**: `.workflows/plan/P1-ENG-U4G0.md`
  - **Completed**: 2026-10-03 17:33
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/io.py, engine/src/seer_engine/commands/backtest_wf.py, engine/tests/test_backtest_wf_command.py
- [x] **P1-ENG-BVN5** Phase 4: Walk-forward report rendering
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `backtest/wf_report.py` (new: `WalkForwardReport`, `report_stem`, machine lines, `parse_machine_line`, `render_markdown`, `equity_csv`, `grid_csv`, `equity_svg`, `variants_svg`) and `tests/test_backtest_wf_report.py` (new, from a small synthetic walk-forward). 16 report sections in order (title, verdict, Data, Method listing everything tried, Folds with top-10, WF vs both SPY curves, per-variant tables/selections, Diagnostics, "Seen before" from 2022-01-03, go-live checklist, survivorship, open positions, equity curves, gate verdict, fail-only owner options (a)-(c), machine lines per D14). Imports `report.py` helpers read-only, defines its own `_STYLE`. Does not touch `report.py`. Exit: suite green, 0 skipped (740); two renders byte-equal (invariant 5, D16).
  - **Status**: completed
  - **Plan Set**: `STRATEGY_A_REWORK_PLAN.md` (phase 4 of 6)
  - **Satisfies**: R5 — The new modules pass the globbing purity test; R6 — One real walk-forward run on Neon, with a committed report holding fold selections and tables, per-variant curves, WF vs both SPY curves, diagnostics, the "seen before" window, the survivorship note and the P3b verdict sentence
  - **Depends on**: P1-ENG-ODYP
  - **Plan**: `.workflows/plan/P1-ENG-BVN5.md`
  - **Completed**: 2026-10-03 17:28
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/wf_report.py, engine/tests/test_backtest_wf_report.py
  - **Drift**: ruff is not installed in engine/.venv and not configured in the project, so the plan's lint step was skipped; imports kept in the plan's order.
  - **Decided**: test_grid_csv_has_every_run_and_one_mark_per_fold counted the header line (which ends in ',selected') → count body rows only via lines[1:] (rung 3: the plan's exact GRID_CSV_HEADER code block wins over the test's miscount; assertion intent unchanged: exactly one selected and one fallback row)
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
