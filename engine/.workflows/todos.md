# Todos: engine

**Package Path**: `engine`
**Package Code**: ENG
**Last Updated**: 2026-10-08
**Total Active Tasks**: 0

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 0
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 0
- Completed: 100

---

## Active Tasks

### [P0] Critical

### [P1] High
- [x] **P1-ENG-F6QN** Phase 4: The bracket path can express and charge Gotrade's fees
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sim/rules.py`, `model.py`, `sizing.py`, `lifecycle.py`, `split_adjust.py`, `__init__.py`, the **new** `sim/charges.py`, `engine/src/seer_engine/paper/bracket.py` and the matching tests — 13 files. Does not touch `sim/book.py`, `sim/costs.py`, `paper/benchmark.py` (phase 3), `paper/roster.py` (phase 12), any file under `commands/`, or `backtest/runner.py` (phase 5 owns its `rules` keyword, D10). It adds **no** roster entry — it makes one expressible; every parameter it adds is keyword-only with `DESIGN_V0` as the default, which is what keeps the tree green with the wiring absent. Exit: `TradeRules(id="design-v0-gotrade", engine="bracket", cost_model="gotrade", …)` constructs, is `PRESETS[13]`, and `paper.roster.rules_for("design-v0-gotrade")` returns it; `size_picks` / `step` / `close_unpriced` / `apply_split` / `decide_bracket` / `settle_bracket` each take a `rules` keyword and charge Gotrade's measured schedule including the $0.10 per-order floor — both owner receipts reproduced to the cent (buy $27.90 → 28.0300, sell $72.51 → 72.2700) and a $28 slot rejecting a $27.90 pick; `DESIGN_V0` still constructs, is still `engine="bracket_v0"`, and `roster.rules_dict(DESIGN_V0)` is byte-identical to today, so C's frozen spec digest has not moved; `git diff --stat` shows no `commands/` file at all and `backtest/runner.py` unmodified; the engine suite's failing-node set is identical to the pre-edit one (`main` is RED for two known reasons phases 1 and 2 own); `PAPER_PAUSED` is still `'true'` and no roster entry was added, edited or retired. This is **resume condition 2** of three.
  - **Status**: completed
  - **Plan Set**: `GOTRADE_FEE_REBUILD_PLAN.md` (phase 4 of 12)
  - **Satisfies**: R4 — Make the bracket path pay Gotrade's fees so the daily control C is honest. C stays permanently
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-F6QN.md`
  - **Completed**: 2026-10-08 10:52
  - **Method**: /implement
  - **Commit**: `836d1a5` — all thirteen phase 4 files are inside it. That commit's own message
    names phase 3 only: twelve sessions share one worktree and therefore one git index, and a
    peer's `git commit` drained the index between this session's `git add` and its `git commit`,
    taking phase 4's staged files with it. The code is correct and complete on the branch; only
    the attribution is scrambled, and `836d1a5` is pushed, so it was not rewritten. The safe
    pattern is `git commit -- <paths>` (stage and commit as one atomic step), not `git add` by
    explicit path followed by a separate `git commit`, which the allowlist does not protect.
  - **Files**: engine/src/seer_engine/sim/charges.py, engine/src/seer_engine/sim/rules.py, engine/src/seer_engine/sim/sizing.py, engine/src/seer_engine/sim/lifecycle.py, engine/src/seer_engine/sim/split_adjust.py, engine/src/seer_engine/sim/__init__.py, engine/src/seer_engine/paper/bracket.py, engine/tests/test_sim_rules.py, engine/tests/test_sim_sizing.py, engine/tests/test_sim_lifecycle.py, engine/tests/test_sim_split.py, engine/tests/test_paper_bracket.py, engine/tests/test_cost_model_pins.py, engine/.workflows/todos.md, engine/.workflows/plan/P1-ENG-F6QN.md
  - **Verified**: `ruff check engine/src engine/tests` -> All checks passed! Full engine suite from the worktree root with `PYTHONPATH=engine/src` and `PG_TEST_URL` -> 3388 passed, 1 skipped, 0 failed (111s); pre-edit baseline on this branch 3362 passed, 2 skipped, 0 failed, failing-node set identical (empty). `import seer_engine.commands.paper, seer_engine.commands.promote, seer_engine.paper.replay` -> ok, so the unwired callers still import and the capability is complete and INERT until phase 12 wires it (D10). All seven exit criteria verified: `git diff` shows no change under `commands/`, nor to `backtest/runner.py`, `paper/replay.py`, `sim/costs.py` (invariant 5), `sim/model.py`, `sim/book.py` or `paper/roster.py`; `PAPER_PAUSED` is still `'true'` (invariant 2); no roster entry added, edited or retired (invariants 3 and 4); every added `rules` parameter is KEYWORD_ONLY with `DESIGN_V0` as its default; `roster.rules_dict(DESIGN_V0)` is byte-identical to before, so live strategy C's frozen spec digest has not moved. Measured and reproduced: the owner's two real receipts to the cent (a 1-share buy at $27.90 costs $28.03; a 1-share sell at $72.51 returns $72.27); at a $28 slot a $27.90 pick sizes to 1 share flat and 0 under Gotrade; the flat branch of `charges.py` is bit-identical to `sim.model`'s old arithmetic over 40,000 random cases (0 mismatches).
  - **Drift**:
    - `test_sim_rules.py`'s `test_unknown_literal_values` parametrized `('engine', 'bracket')` as an UNKNOWN engine -- the exact value Step 1 makes valid. The plan's Files table did not foresee it. Repointed that case to `'brackets'`, which the plan's own 12c test already asserts raises "unknown engine". The guard is repointed, not relaxed.
    - `sizing.py`'s `from decimal import ROUND_FLOOR, Decimal` left `ROUND_FLOOR` unused once `_whole_shares` moved to `charges.py`; dropped it from the import. The plan's import block did not mention it.
    - Pre-edit baseline measured 3362 passed / 2 skipped / 0 FAILED -- the plan's exit criterion 6 anticipated "two known main failures", but this branch is already green (phases 1 and 2 own those, and one surfaced as a skip). Held the stronger bar of zero failures instead.
    - simkit helper signatures differ from the plan's illustrative 12e snippets (`portfolio` takes `marks=` as a Mapping; `opened` takes `days_held` positionally). Adapted as the plan's own note sanctions; every asserted money figure is unchanged and measured.
    - My hand-worked literal in the new 12f split test was wrong (I guessed a $0.10 Gotrade fee on a $10 order); measured it is $0.12, matching the plan's own fee table. Corrected the two pins to the measured 10.12 / 0.48.
  - **Decided**:
    - Step 3 says create every phase's task, but six wave-1 sessions share this worktree -> created phase 4's task only (tie-break: narrower blast radius; twelve concurrent writers on one todos.md is a guaranteed race).
    - `test_unknown_literal_values` pins `'bracket'` as unknown, which Step 1 makes known -> repointed the case to `'brackets'` (rung 3: the phase plan's own 12c code block uses exactly that spelling for a still-invalid engine).
    - `ruff format --check` fails on 237 pre-existing files repo-wide and `engine/pyproject.toml` deliberately selects only E9+F because "closed records must not be reformatted" -> treated `ruff check` as the real lint gate (it passes) and reverted an accidental `ruff-format` pass over `test_paper_bracket.py` (rung 6: the surrounding code's existing convention).
    - Completion: the `[x]` block is left in place under `### [P1] High` rather than moved into `## Completed Tasks`, and Quick Stats are recounted from the file rather than blind-decremented (rung 6: the recorded precedent in this same file from P1-ENG-D7XQ, T4KD and 7V3C). Five peer sessions are appending to this file concurrently; a cross-section block move is the one edit that silently loses a peer's append, and a decrement compounds the race where a recount is idempotent. A peer landed P1-ENG-KQRW in this file between my first and second read of it, which is the race in question, observed.

- [x] **P1-ENG-D7XQ** Phase 1: The delisting stress harness
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns a new tested module `engine/src/seer_engine/delisting.py` (the hazard estimator and the `Market` perturbation), a new driver `engine/scripts/delisting_stress.py` (the Monte Carlo and the break-even solver) and a new `engine/tests/test_delisting.py`; it adds files and changes none, touching no `backtest/`, `sim/`, `lab/`, `paper/`, `web/`, document or `engine/.research`. Exit: `delisting_stress.py --help` runs and a smoke run over one candidate, two assumed delisting returns and 2 seeds prints a hazard block reproducing M2 (5.091%, 4.002%, 10,096 member-years); `ruff check --no-cache src tests scripts` passes; a test asserts the module imports neither `lab.store` nor `lab.runner`; the full suite passes with `PG_TEST_URL` and `PYTHONPATH` at 0 failed and 0 skipped; the commit lists exactly the three new paths. This phase owns the CLI spellings and the `--csv` column names, order and units that phase 2 consumes.
  - **Status**: completed
  - **Plan Set**: `DELISTING_STRESS_ROSTER_RULES_PLAN.md` (phase 1 of 5)
  - **Satisfies**: R1 — Q1 — settle where the delisting stress test lives and what it needs, build it, run it, and report the break-even delisting return with a judgement on whether that number is plausible
  - **Plan**: `.workflows/plan/P1-ENG-D7XQ.md`
  - **Completed**: 2026-10-07 18:16
  - **Method**: /do
  - **Files**: engine/src/seer_engine/delisting.py, engine/scripts/delisting_stress.py, engine/tests/test_delisting.py
  - **Verified**: Import check — `seer_engine.delisting` resolves to the worktree file and prints `1996-01-02 2015-10-16 12`. `ruff check --no-cache src tests scripts` -> All checks passed! `pytest tests/test_delisting.py` -> 28 passed, 0 skipped, 3.19s. Full engine suite with `PG_TEST_URL` + worktree `PYTHONPATH` and no `-o addopts` -> 3229 passed, 0 failed, 0 skipped, 61.85s (branch baseline 3197; the surplus is this phase's 28 plus peers' concurrent additions — the invariant is `0 failed, 0 skipped` at a count no lower than 3197, never a specific total, because four peer phases add tests to this shared worktree). `delisting_stress.py --help` runs and lists every CLI flag the Interface Contract names. Smoke run against the main checkout's store reproduces the plan's recorded output exactly: hazard block `ever-members 1041 / priced 519 / unpriced 522`, `5.091%` all-exit and `4.002%` unpriced-exit over `10096` member-years (analysis M2); unstressed `M0022-W-TV16` CAGR `+11.68%/yr`, worst fall `14.31%`, `1589` trades (M1/M3); `break-even delisting return: NONE on this grid` with the mean edge still `+0.32 pts/yr` at r = -100%. Nothing moved: `engine/.research/manifest.json` and `lab/lab.sqlite` sha256 byte-identical before and after; `lab status` still reports N = 110 dev trials, 0 test-window looks, 37 methods, 32 insights.
  - **Drift**: none.
  - **Decided**:
    - `PG_TEST_URL` was not exported in the implementing session's environment and the plan's verification commands guard it with `${PG_TEST_URL:?...}`, which would have halted the run -> exported the URL that `engine/tests/conftest.py:6` documents (the local seer-pg docker container, confirmed running on port 55432) rather than stopping. Rung 1 (invariant 1 requires `PG_TEST_URL` in every suite run) plus rung 6 (the repo's own stated convention). No file changed as a result; this was a shell-environment decision only.
    - Completion: the `[x]` block is left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the recorded precedent in this same file from P1-ENG-T4KD and P1-ENG-7V3C). A cross-file-section block move is the one edit that silently loses a peer's concurrent append, and four peers are appending to this file right now.
    - Completion: the plan index's `**Status:**` left at `reconciled` rather than set to `phase 1/5 complete` (rung 6, same precedent). With five phases running concurrently a single scalar cannot represent out-of-order completion — phases 3 and 4 are already done — and `.workflows/orchestration/delisting-stress-roster-rules/ledger.json` is the per-phase status of record for a swarm-tracked set. The phase row in the index's table was ticked `**done**` instead, matching how phase 4 was ticked.
    - Quick Stats recounted from the file rather than blind-decremented (recount is idempotent under concurrency; a decrement compounds the race).
    - Completion: `readme-updater` ran in **advisory mode** and wrote nothing (rung 1: invariant 8). `engine/package_readme.md` is outside this phase's three-path allowlist; an edit there could not be committed by this phase and would dangle in a tree four peers are committing from. **But the debt is real and is left for the set's coordinator at land time**, because no phase in the index owns `package_readme.md`: (1) the Layout tree enumerates every flat module under `src/seer_engine/` and does not know `delisting.py` — now the 21st — exists; (2) `## Exported API` carries an H3 per pure module with a public `__all__`, and `delisting.py`'s eight-name `__all__` has no section; (3) `### Internal module graph` needs one bullet pinning that `delisting` imports only numpy, `backtest.dev`, `backtest.market` and `strategies.base`, and in particular neither `lab.store` nor `lab.runner`. The `scripts/` driver is a weaker claim — `engine/scripts/` is 0% documented today (neither `build_ticker_cik.py` nor `survivorship_coverage.py` is named anywhere), so that hole predates this phase; fold `delisting_stress.py` into the module's own section rather than opening a `scripts/` node, unless the coordinator wants to close the pre-existing gap too. Two further coordinator notes: `package_readme.md:4` (`**Last Updated**`) is a single-line contention point all five phases would rewrite — whoever lands last should own it; and `package_readme.md:1957` ("yfinance has no delisted tickers, so ... single-stock dev results are optimistic (D4)") is the line this plan set exists to settle, but it must be revised by whichever phase **records a break-even number** (phase 2, P1-ROOT-T8MK), not by phase 1, which ships the instrument and commits no measurement.
- [x] **P1-ENG-T4KD** Phase 4: A test that pins the dev gate's trades bar
  - **Difficulty**: EASY
  - **Type**: Update
  - **Context**: Owns exactly one new file, `engine/tests/test_dev_trades_bar.py` — three tests pinning `dev._MIN_TRADES == 100` with failure prose explaining why it differs from design §1 item 1, and re-deriving §13's measurement from the committed lab database on every CI run. Test-only: writes no documentation. Exit: the three tests pass with 0 skipped; moving `_MIN_TRADES` in memory produces actionable prose naming design §13; the third test re-derives `F1-SPY-SMA200-M` (11 trades) and `F1-SPY-10MSMA-M` (13 trades), both with `dsr IS NULL`, from the database; `backtest/dev.py` and every seer-fc-claimed file show no diff; the commit lists exactly one path; full suite 0 failed, 0 skipped.
  - **Status**: completed
  - **Plan Set**: `DELISTING_STRESS_ROSTER_RULES_PLAN.md` (phase 4 of 5)
  - **Satisfies**: R2 — Q2, settle whether go-live item 1 is calibrated and tell the owner; the residue owned here is the executable guard on the dev-gate asymmetry
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-T4KD.md`
  - **Completed**: 2026-10-07 18:12
  - **Method**: /do
  - **Files**: engine/tests/test_dev_trades_bar.py
  - **Verified**: `ruff check --no-cache src tests` -> All checks passed. `pytest -q -rs tests/test_dev_trades_bar.py` with `PYTHONPATH` + `PG_TEST_URL` -> 3 passed, 0 skipped, 2.44s. Full engine suite with both env vars -> 3201 passed, 0 failed, 0 skipped in 114s (baseline 3197; the invariant is `0 failed, 0 skipped` at a count >= 3197, never a specific total, because peer phases add tests to this shared worktree). Manual guard check: setting `dev._MIN_TRADES = 0` in memory renders the full explanatory failure message naming design §13 — confirmed, and `git diff -- engine/src/seer_engine/backtest/dev.py` is empty, so nothing was mutated on disk. `lab status` -> dev trials 110, test-window looks 0, methods 37, insights 32 — the pre-set reading invariant 2 requires; `git status --porcelain lab/lab.sqlite` prints nothing.
  - **Drift**: none.
  - **Decided**:
    - Step 3 task bookkeeping: create only phase 4's task, not all five -> only P1-ENG-T4KD minted (tie-break: narrower blast radius; phases 1 and 3 are spawned concurrently in this shared worktree and phase 1 shares the engine package counter, so three sessions each minting five TaskIDs would collide). Validated in flight — phase 1's session independently minted P1-ENG-D7XQ and phase 3's P1-ROOT-K3VD.
    - Commit stages exactly one path, excluding `engine/.workflows/todos.md` -> the shared todos file is left for a peer or coordinator sweep (rung 3: phase 4's Step 3 code block stages only the test file and asserts HEAD lists exactly that one path; rung 2 agrees via exit criterion 4; invariant 8 forbids committing a peer's work under this phase's name, and that file currently also carries phase 1's task line).
    - The handover note `docs/handover/2026-10-07-dev-gate-trades-bar.md` is **cancelled, not deferred** -> written by nobody (rung 2: the plan index's Reconciliation Log rows 9 and 10 and its Decisions table, which record the cancellation and resolve Impact Point 7 as deliberately unowned). `seer-fc`'s design §13 already carries the prose in full; a duplicate record goes stale first and then misleads.
    - Completion: the `[x]` block is left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the recorded precedent in this same file from the ROSTER_PROMOTION_PIPELINE swarm). A cross-file-section block move is the one edit that silently loses a peer's concurrent append, and four peers are appending to this file right now.
    - Completion: `readme-updater` ran in **advisory mode** and wrote nothing (rung 1: invariant 8). `engine/package_readme.md` is outside this phase's one-path allowlist; an edit there could not be committed by this phase and would be left dangling in a tree four peers are committing from. It nonetheless returned **edit-warranted**, and that recommendation is recorded here rather than dropped — the readme documents `dev._MIN_TRADES` as a plain threshold at lines 2055 and 2218-2224 and mentions `tuning.MIN_PAPER_MONTHS` and design §13 **zero** times, so a reader who consults it before touching the constant finds no warning that deleting it silently re-judges all 110 recorded dev trials. **Unowned deliverable for the coordinator to fold in at land time**: one bullet in `### Gotchas` (heading line 2811), inserted after the pre-registration-gate bullet at line 2833:
      > - **`dev._MIN_TRADES` is an owner dial, not a leftover.** Design §1 item 1 dropped its "≥ 100 closed trades" clause on 2026-10-07 for "≥ 18 months of forward paper trading" (`tuning.MIN_PAPER_MONTHS`; `docs/plans/2026-10-03-seer-design.md` §13), and the dev-window gate kept its trades condition **on purpose**: item 1 asks how much forward evidence a strategy has accumulated making real decisions, which is a question about time, and the dev gate asks whether a 20-year backtest closed enough trades for its PF and drawdown to mean anything, which is a question about sample size. Making the two "agree" by deleting the constant is not a tidy-up — `store.owner_failures` and `store.verdict` re-derive every verdict from it **at read time** and `trials` is append-only, so moving it silently re-judges all 110 recorded dev trials while the rows stay byte for byte. `tests/test_dev_trades_bar.py` is the guard: it pins the bar at 100, pins `MIN_PAPER_MONTHS` at 18 as a separate dial with no arithmetic tying the two together, and re-derives §13's measurement — the two trials the bar alone holds out, `F1-SPY-10MSMA-M` (13 trades) and `F1-SPY-SMA200-M` (11), both `dsr IS NULL` and so failing the luck test regardless — read-only from the committed lab database on every run. Moving the bar is an owner decision with a dated design revision behind it.

      Two conditions on folding it in: (a) if the phase that landed §13 adds its own Gotcha covering item 1 / `MIN_PAPER_MONTHS`, append only the second half (from "`tests/test_dev_trades_bar.py` is the guard") to **that** bullet — two bullets restating one asymmetry is worse than none; (b) separately and out of this phase's scope, `package_readme.md` line 2067 still records "max DD ≤ 15%" and "33 made ≥ 100 closed trades" as a 2026-10-04 run, nine lines below line 2055's live "≤ 20%", unlabelled as history. Worth its own pass; **not** fixed here.
- [x] **P1-ENG-7V3C** Phase 3: Common-window, risk-adjusted comparison over `equity_snapshots`
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns a new pure `engine/src/seer_engine/paper/compare.py`, a new read-only CLI edge `engine/src/seer_engine/commands/compare.py`, and a new `engine/tests/test_paper_compare.py`; it does not touch the roster, the paper night, `web/` or any schema, and never reads the `strategies` table — which is what keeps it a wave-1 phase with no dependency on phase 1. Exit: a pure function takes equity series per strategy and returns total return, CAGR, max drawdown and a risk-adjusted figure for a stated window, plus the window it used and its session count; the common window is the explicit intersection of the compared strategies' live sessions (invariant 6), inception-to-date is available separately and never mixed into the same ranking, a strategy with fewer than `MIN_COMMON_SESSIONS = 63` common sessions is `insufficient` rather than ranked and does not shorten anyone else's window, `MIN_COMMON_SESSIONS = 63` / `MIN_RANKED = 2` / annualised Sharpe as the only risk-adjusted figure / `_select`'s drop-the-worst-overlap rule are the pinned contract phase 4 ports, `as_json` emits exactly that phase's Interface Contract keys, and purity (no database, no clock, no I/O) is proved mechanically by an `ast`-based test.
  - **Status**: completed
  - **Plan Set**: `ROSTER_PROMOTION_PIPELINE_PLAN.md` (phase 3 of 6)
  - **Satisfies**: R3 — A robust pipeline to compare and "re-sort" the horsemen, so a better method can be recognised as better
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-7V3C.md`
  - **Completed**: 2026-10-05 18:00
  - **Method**: /implement
  - **Files**: engine/src/seer_engine/paper/compare.py, engine/src/seer_engine/commands/compare.py, engine/tests/test_paper_compare.py
  - **Verified**: build ok (`import seer_engine.paper.compare, seer_engine.commands.compare`); `ruff check` passed on all three new files; phase tests 39 passed with `PG_TEST_URL`, 36 passed / 3 skipped without. Full engine suite with `PG_TEST_URL`: 2648 passed, 0 failed, 0 skipped (245s) — that total also contains phase 1's concurrent in-flight work in the shared tree; phase 3's own contribution is exactly +39 passed, since it modifies no existing file. Manual: `python -m seer_engine --help` lists `compare`; `compare --min-sessions 10` against the local-train DB prints the honest `no common window of 10 sessions among 0 strategies` (that DB holds no paper history); `--json` emits `{"minSessions":10,"rows":[],"window":null}`; `--require-window` exits 1.
  - **Drift**: none. Every anchor the plan quotes was verified present: the `cli.discover()` contract (`cli.py:9,29`), `backtest.metrics.cagr_between` / `strategy_metrics`, the conftest pg fixture, `paper_check.py`'s REPEATABLE READ READ ONLY pattern, the `equity_snapshots` DDL (`001_init.sql:67`), `test_sim_purity.py`'s forbidden-import constants, and `test_cli.py` pinning no command list (only `"migrate" in cli.discover()`).
  - **Decided**:
    - Create tasks for all 6 phases, or only phase 3's? -> only phase 3's (tie-break: narrower blast radius). Five peer sessions run Step 3 against this same file concurrently; minting all six TaskIDs from here would race them into duplicates.
    - The plan's test table enumerates 39 tests (35 numbered + P1 purity + D1–D3 database) but its summary line says "32 pure + 3 database = 35". -> Wrote all 39 and report the MEASURED delta (rung 3, the plan's code blocks). The enumerated table is the specification; the summary arithmetic over it is the stale half. Invariant 1's real guard — no existing test changes result — holds either way, structurally: this phase creates three new files and modifies zero existing ones.
    - Test 25 (ties on Sharpe break on total return then drawdown) was specified as "two curves with identical Sharpe (one a scaled copy)". -> Exercise `_rank_key` directly on hand-built `Performance` objects (rung 3). Two float equity curves cannot be relied on to land on bit-identical Sharpes, so a curve-based tie test would be testing floating point rather than the pinned rank key.
    - Completion: `readme-updater` skipped (rung 6, the recorded precedent in this file from the FUNDAMENTAL_PANEL_COVERAGE swarm, plus the session's explicit pathspec constraint). `engine/package_readme.md` is outside this phase's commit pathspec; writing it would leave an uncommitted edit in a worktree five peers are committing from. The new `compare` command still wants a readme line — flagged to the set's coordinator to fold in at land time, since no phase in the index owns `package_readme.md`.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: all five phases of the previous swarm were left the same way in this file). A cross-file block move is the one edit that loses a peer's concurrent append.
    - Completion: the plan index's `**Status:**` left at `reconciled` rather than set to `phase 3/6 complete`. With six phases running concurrently a single scalar cannot represent out-of-order completion, and `.workflows/orchestration/roster-promotion-pipeline/ledger.json` is the per-phase status of record for a swarm-tracked set. No peer phase's task was unblocked or altered.
- [x] **P1-ENG-TJ4M** Phase 1: The coverage gate: a pure measure, a CLI surface, a `lab run` refusal
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns a new pure `engine/src/seer_engine/fundamentals/coverage.py` (no database, network, clock or randomness — `tests/test_strategy_purity.py` territory) exporting the measure and its constants, its export from `fundamentals/__init__.py`, a `--coverage` mode on `commands/research_store.py` that loads the store and prints the per-year table plus one fraction, a post-load refusal in `lab/runner.py` wired into `commands/lab.py:_run` between `load_store` and `run_method` with an `--allow-coverage FLOAT` escape, and tests in a new `engine/tests/test_fundamentals_coverage.py` plus additions to `engine/tests/test_lab_runner.py`. Does not touch `cik.py`, `build_ticker_cik.py`, `ticker_cik.csv`, `commands/fundamentals.py`, `research.py`'s build or seal path, any `docs/` file or any database; it must work against the current 2.5%-coverage store and its tests must not depend on a store on disk. The measure answers "on how many sampled dev-window dates can the panel rank at least `top` symbols?", counting a symbol only when `panel.as_of(sym, t)` has non-empty `observations` and its newest `filed` is within `max_stale_days` of `t`; `lab run` refuses below `MIN_DEV_COVERAGE = 0.80` when the method has a `MarketAware` allocator, and a price-only method is never refused. Exit: `python -m seer_engine research_store --coverage --store "$SEER_STORE"` prints, for the 2026-10-05 store, a table whose 1996–2014 rows are 0 and whose 2015 row is non-zero and a fraction of `0.0378` — under this set's one definition (monthly sample of 1996-01-02 .. 2015-10-16, 238 dates, `top = 20`, `max_stale_days = 400`, content checked through `Snapshot.observations`) and reported as an upper bound because the measure reads no bars; a unit test asserts 0.0 for a panel whose facts all postdate the window, 1.0 for one that covers it, and that an empty-`observations` `Snapshot` counts as not rankable; a `lab run` test asserts the refusal fires for a `MarketAware` method on a thin panel, does not fire for a price-only method, and is lifted by `--allow-coverage`. Suite green at +27.
  - **Status**: completed
  - **Plan Set**: `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` (phase 1 of 5)
  - **Satisfies**: R3 — The coverage gate (§6.2): the check moves out of the runbook and into the engine, so no future method runs against a panel that cannot rank
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-TJ4M.md`
  - **Completed**: 2026-10-05 14:35
  - **Method**: /implement
  - **Commit**: df6e0ab
  - **Files**: engine/src/seer_engine/fundamentals/coverage.py, engine/src/seer_engine/fundamentals/__init__.py, engine/src/seer_engine/commands/research_store.py, engine/src/seer_engine/commands/lab.py, engine/src/seer_engine/lab/runner.py, engine/tests/test_fundamentals_coverage.py, engine/tests/test_lab_runner.py
  - **Measured**: 0.0378 on the 2026-10-05 store (fingerprint e597367b…), monthly / top=20 / max_stale_days=400 / 1996-01-02..2015-10-02, 238 samples; 1996–2014 all 0/12, 2015 covers 9 of 10 with 519 rankable at best. An UPPER BOUND — the measure reads no bars, so membership, min_price and min_dollar_volume are unapplied. The 4% (doc §4 span estimate) and 2.5% (semiannual) figures are retired by name.
  - **Decided**:
    - Step 3 task creation in a concurrent swarm -> this session (phase 1) created all five tasks; peers skip it (rung 6: the recorded precedent in this file from the STRATEGY_B_RANKER swarm). A peer minted a rival ID set (JUE0/WQI8/6U02/RLMS/27JI) a minute earlier; those plan copies are orphaned — no todos entry, no index row — and were left on disk for their session to clean up (tie-break: reversible option)
    - Committed by explicit pathspec from the main context, not via pusher (rung 6: the shared-worktree ruling recorded in this file); `git add -A` would have swept phase 2's in-flight CSV work
    - readme-updater skipped: `engine/package_readme.md` is phase 5's (rung 4: the index Scope and phase 1's "Leaves alone")
    - Phases 2–5 left for their own sessions to claim rather than pre-flipped (rung 6: phase 2's session claimed its own entry the same way)
  - **Notes**: `lab run` was NOT executed, by design. The 6 `test_cik.py` failures present in the shared worktree at commit time are phase 2's in-flight edits — its own new tests asserting a `ticker_cik.csv` it has not regenerated yet — and phase 1 touches no file phase 2 touches. Phase 1's delta is +27 (20 new in `test_fundamentals_coverage.py`, 7 added to `test_lab_runner.py`); full suite 2242 passed / 332 skipped, 2574 passed / 0 skipped with `PG_TEST_URL`.
- [x] **P1-ENG-QD7X** Phase 2: Fix A: re-vendor `ticker_cik.csv` back to real 2009 membership, with the `EARLY` start screen
  - **Difficulty**: HARD
  - **Type**: Update
  - **Context**: Owns `engine/src/seer_engine/cik.py` (`SINCE` → `date(2009, 1, 1)` and the docstring that explains it), `engine/scripts/build_ticker_cik.py` (the `MANUAL` start sentinel, the new audits, `SCREEN_EXEMPT` additions, the second `EARLY` screen — `periodic_dates`, `EARLY_WINDOW_DAYS` and `EARLY_EXEMPT` — and the measured counts in its module docstring), the regenerated `engine/data/ticker_cik.csv`, `engine/data/SOURCES.md`, and `engine/tests/test_cik.py` (one assertion widened, five tests added). Does not touch `commands/fundamentals.py` (phase 3 owns both ingest floors), `fundamentals/` (phase 1), `research.py` (phase 4), any `docs/` file outside `engine/data`, or the `ticker_cik` table and `005_fundamentals.sql`. `spans()` already derives every start from `max(iv.start_date, SINCE)`, so lowering `SINCE` fixes tiers 1–4 for free; what it does not fix is `MANUAL`, whose ~60 literal `"2015-01-02"` starts become an empty-cell sentinel meaning "the symbol's membership start from `spans()`" while genuinely later starts stay literal and every `end` stays literal and unchanged. 118 symbols enter scope, most delisted before 2015 and resolved by hand against `https://data.sec.gov/submissions/CIK<cik>.json`, with new pre-2015 recycling split into two dated rows rather than merged. Exit: the CSV loads through `cik.load_index()` with 913 symbols; `cik.coverage_gaps(index, compute_universe())` is empty; zero rows carry `source=fuzzy`; zero rows start at 2015-01-02; `NDOI` is still the only `NONE` and still alone; the generator exits 0 with `UNRESOLVED`, `SCREEN` and `EARLY` all empty and every exemption carrying a reason naming what was checked; `RECYCLED`, `SPOT_CHECKS`, `SHARE_CLASSES`, the WestRock and Alphabet tests all pass with their existing expected values; `SOURCES.md`'s row and tier counts match the file. Suite green at +5.
  - **Status**: completed
  - **Plan Set**: `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` (phase 2 of 5)
  - **Satisfies**: R1 — Fix A (§2): re-vendor `ticker_cik.csv` with real first-membership intervals, every §2 invariant still enforced by tests
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-QD7X.md`
  - **Completed**: 2026-10-05 — commit `85f6bfd`
  - **Result**: `ticker_cik.csv` 798 rows/795 symbols -> 944/913. 0 rows at the retired
    2015-01-02 clamp (525 removed), 540 at the 2009 floor, 0 before it, 0 `fuzzy`, `NDOI`
    still the only `NONE` and alone, `coverage_gaps` empty, `K` -> 0000055067. The new
    `EARLY` screen (450 days from the span's start) flagged 56 rows `SCREEN` cannot see,
    including pre-existing errors: `DIS` and `XRX` were mapped to their 2019 holdcos and
    `SNDK` to the 2025 spinoff. 69 symbols hand-audited in all; `MANUAL` 70 -> 152 symbols /
    183 rows, every CIK read off data.sec.gov/submissions. Generator exits 0 and a re-run is
    byte-identical. Suite 2261 passed / 332 skipped (delta +5); 2593 passed with
    `PG_TEST_URL`. All 11 `SCREEN_EXEMPT` reasons intact; no `end_date` pushed forward; no
    database or network write.
  - **Decisions**: five tests not four (inv 1/C9); successor handovers split at the
    successor's first periodic filing, measured (inv 2+10); membership-gap symbols split at
    real membership boundaries, hole left uncovered (the plan's own `Q` block); hull opening
    before the ticker existed -> `EARLY_EXEMPT`, not a `membership_overrides.csv` fix (C7i) —
    `CCEP`, `DXC`, `LMCK`, `PSKY`, `VTRS`; `CCE` single row -> split, its old
    "NOT 0000804055" note held only at the 2015 floor (inv 2); two `coverage_gaps` unit tests
    re-anchored from a literal 2015-01-02 to `c.SINCE`, assertions unchanged and both still
    pass (inv 1); `BNI`'s fuzzy match hand-read and promoted to `manual` (inv 3).
  - **Note**: C7i predicted `DXC` passes both screens; it does not — `EARLY` flags it. Kept
    out of scope as C7i directs and exempted with the reason.
- [x] **P1-ENG-F2BN** Phase 3: Fix B: re-ingest at `--since-filed 2009-01-01` via `--symbols`, and measure 2009–2012
  - **Difficulty**: NORMAL
  - **Type**: Update
  - **Context**: Owns `engine/src/seer_engine/commands/fundamentals.py` (`DEFAULT_SINCE` and `DEFAULT_SINCE_FILED` → `date(2009, 1, 1)`, the module docstring's "since 2015-01-02", the two `--since*` help strings, the storage paragraph's arithmetic), `engine/tests/test_fundamentals_command.py`, and the ingest run itself against `.env.local-train`. Does not touch `cik.py` or `ticker_cik.csv` (phase 2), `fundamentals/` (phase 1), `research.py` or `engine/.research/` (phases 4 and 5), Neon, or the `005` migration. The local train database holds 0 `universe` and 0 `bars` rows, so `universe refresh` (no network) must run before the ingest even under `--symbols`, which bypasses `select_symbols` but not `plan_jobs`'s per-symbol `windows`. The decision doc §3's `--retry-failed` does not work — it narrows `done` to `{ok}` and skips all 773 `ok` filers — so the run is `fundamentals --since 2009-01-01 --since-filed 2009-01-01 --symbols <912 symbols>`, which makes `plan_jobs` set `logged = {}` and fetch every resolved CIK without deleting a row anywhere; `--since` moves too, or the member set stays at 795. Budget ~30 minutes for roughly 890 companyfacts calls. The measurement is as much the deliverable as the rows: facts by `filed` year for 2009–2012 against the 2013–2026 baseline, expected partial and size-biased because XBRL phased in by filer size. Exit: `fundamentals_log` holds no unexplained `failed` row and no log row was deleted to get there; a per-year `filed` count for 2009–2026 is recorded in the phase's summary; `fundamental_facts` row count and `pg_total_relation_size` are recorded; the resolved DSN named `localhost:55432` before anything was written. Suite green at +0 (four existing tests edited in place, none added or removed).
  - **Status**: completed
  - **Plan Set**: `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` (phase 3 of 5)
  - **Satisfies**: R2 — Fix B (§3): re-ingest at `--since-filed 2009-01-01`, and measure how much 2009–2012 XBRL actually exists
  - **Depends on**: P1-ENG-QD7X
  - **Plan**: `.workflows/plan/P1-ENG-F2BN.md`
  - **Completed**: 2026-10-05 16:05
  - **Method**: /do
  - **Files**: engine/src/seer_engine/commands/fundamentals.py, engine/tests/test_fundamentals_command.py
  - **Drift**: None. The plan's quoted line numbers and code blocks matched the tree exactly; all
    four regions (module docstring, the `DEFAULT_SINCE`/`DEFAULT_SINCE_FILED` block,
    `add_arguments`, four test edits) applied verbatim.
  - **Decided**:
    - The Verification section's grep expects no `2015-01-02` anywhere in
      `commands/fundamentals.py`, but `resolve_cik`'s docstring uses it as a recycled-ticker
      illustration (`CA on 2015-01-02 is CA Inc. and not the Xtrackers ETF`) -> kept it
      unchanged (rung 3: the phase plan's code blocks and its Files table enumerate exactly
      four changing regions and `resolve_cik` is not among them; the grep is prose shorthand
      for "no floor still says 2015/2013")
    - `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` left untouched, `**Status:** reconciled` not
      advanced (rung 6 + rung 4: `swarm.py find` returns `swarm: true` with coordinator
      `orch-fundamental-panel-coverage`, so the set's tracker is its ledger at
      `/home/miftah/seer/.workflows/orchestration/fundamental-panel-coverage/ledger.json` and
      the coordinator writes it; phases 1 and 4 made the same call, and a linear "phase 3/5"
      would misreport a set that landed 4 before 3)
    - Completed block left in place under `### [P1] High` rather than moved to
      `## Completed Tasks` (rung 6: TJ4M, QD7X and K8RV — every landed phase of this set —
      sit there checked; moving only F2BN would be the inconsistent edit)
    - `engine/package_readme.md` not written — readme-updater dispatched read-only, to report
      staleness rather than fix it (rung 2/3: phase 5's `Owns` list names that file, and phase 4
      of this set took the same ruling an hour ago; any finding is handed to phase 5)
    - `P1-ENG-M3HE` flipped `blocked` -> `open` (rung 4: its `Depends on` names TJ4M, QD7X,
      F2BN and K8RV, and with this phase landed all four are complete — it is now genuinely
      runnable, which phase 4 correctly refused to claim an hour ago)
    - No `**Commit**` field (rung 2: this phase is one commit carrying code and bookkeeping
      together, so the sha cannot name itself; phase 1's field came from /implement's separate
      `chore(todos)` commit)
  - **Handoff to P1-ENG-M3HE (phase 5, which owns `engine/package_readme.md`)**: readme-updater
    reviewed it read-only and found **nothing stale from this change** — the readme names
    neither the 2015-01-02 member floor nor the 2013 filed floor nor any fundamentals
    row-count figure, and every `2015` in it is a different constant (`:181` is `backfill`'s
    `DEFAULT_START`, bars; `:29/:328/:345-349/:1353` are `DEV_END = 2015-10-16`;
    `:239/:247/:289/:838/:885-886/:955/:1062/:1302/:1397` are `tuning.IS_START = 2015-10-19`).
    It did flag four **pre-existing** gaps, caused by nothing in this phase, that phase 5 may
    want to fill while it is in the file: (a) the `commands/` tree at `:113-126` has no
    `fundamentals.py` row though `:109` already cites "the impure ingest command";
    (b) the Commands table at `:166-171` lists only `migrate`, so `--since`, `--since-filed`,
    `--retry-failed` and the `--symbols`-ignores-the-log resume semantics are undocumented;
    (c) the migrations list at `:133-136` stops at `004_news_veto.sql` though `:869` and
    `:1890` both name `005_fundamentals.sql`; (d) `:8` ("writes the Neon (Postgres) tables")
    and `:855-870` are now *incomplete* rather than wrong, since `:859`'s "rows come from
    `fundamental_facts` JOINed to `ticker_cik`" now implies a different database than the
    overview's Neon framing.
  - **Measured**: suite 2261 passed / 332 skipped, delta **+0** — exactly the inherited count,
    four tests edited in place, none added or removed; 2593 passed / 0 skipped / 0 failed with
    `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`. The run went to
    `.env.local-train` / `localhost:55432`; **Neon was untouched throughout**. Route was
    `--symbols` over the whole 912-symbol member set (Decisions row C6): 927 symbols ok,
    17 empty, 0 failed, 0 skipped; 915 companyfacts calls (up from 776), 915 `fundamentals_log`
    rows written, **0 log rows deleted** — `fundamentals_log_pre_fixb` is a read-only 776-row
    snapshot never restored from. `fundamental_facts` 385 MB -> 471.2 MB,
    1,228,822 -> 1,589,093 rows over 899 CIKs; 1,589,093 facts kept, 360,271 inserted or changed.
    M4: 67 facts stored over 36 CIKs carry EDGAR's `filed < period_end` (48 joined, was 28/18) —
    a filer-side typo class `facts_from_frame` drops and counts, not an error.
    M5: `fundamentals_log` 899 ok / 16 empty / **0 failed**.
    M6: `ticker_cik` 943 rows / 912 symbols; `universe` 1544 rows / 1265 symbols (was 0).
    Full output at `/tmp/seer-fixb/measurement.txt`, ingest log at `/tmp/seer-fixb/ingest-*.log`.
  - **M1 — facts by `filed` year (stored), vs the `2dad9ff` baseline**:
    2009 22,219/403 filers (new) · 2010 60,550/670 (new) · 2011 90,505/729 (new) ·
    2012 99,641/738 (new) · 2013 101,736/739 (base 89,913, +11,823) ·
    2014 101,580/738 (base 91,578, +10,002) · 2015 101,002/747 (base 91,921, +9,081) ·
    2016 100,390/730 (base 91,655, +8,735) · 2017 97,841/723 (base 90,595, +7,246) ·
    2018 99,305/725 (base 92,259, +7,046) · 2019 104,978/720 (base 98,506, +6,472) ·
    2020 104,064/710 (base 98,431, +5,633) · 2021 96,535/708 (base 91,870, +4,665) ·
    2022 88,211/701 (base 84,183, +4,028) · 2023 87,068/691 (base 83,277, +3,791) ·
    2024 87,504/690 (base 83,970, +3,534) · 2025 86,733/685 (base 83,504, +3,229) ·
    2026 59,231/675 (base 57,160, +2,071). Total **1,589,093** (baseline 1,228,822).
  - **M3 — what the PANEL sees (the dated `ticker_cik` join), by `filed` year**: baseline was
    831,725 rows / 780 symbols with **2013 and 2014 absent entirely**. Now
    2009 21,179/382 · 2010 51,395/525 · 2011 70,642/541 · 2012 73,365/537 · 2013 74,248/539 ·
    2014 74,339/538 · 2015 73,927/551 · 2016 74,342/554 · 2017 73,607/550 · 2018 74,763/547 ·
    2019 79,342/538 · 2020 80,135/548 · 2021 75,063/544 · 2022 68,604/542 · 2023 67,726/532 ·
    2024 67,394/532 · 2025 67,126/532 · 2026 46,154/531. Joined total **1,213,351 rows /
    869 symbols** (was 831,725 / 780) — **+381,626 rows, +89 symbols**.
  - **Finding**: **the real floor is roughly 2011, not 2009.** 2009 holds 22,219 facts from 403
    filers against a 2013 baseline of 89,913 from 773 — about **25%** of a full year; 2010 holds
    60,550 from 670, about **67%**. 2011 (90,505/729) is the first year to reach the 2013
    baseline and 2012 (99,641/738) exceeds it. This is the expected shape, not an ingest
    failure: XBRL phased in by filer size — large accelerated filers from roughly FY2009, all
    filers by FY2011 — so 2009–2010 are thin **and** large-cap-skewed.
    **Fix A and Fix B worked together**, and the number that proves it is M3's 2013 and 2014
    rows: 74,248 and 74,339, both previously **zero**. 181,491 facts that were stored and
    invisible now reach the panel.
    **This is not panel coverage.** "Facts by filed year" is not "dates on which the panel can
    rank 20 symbols" — conflating them is the M0005 bug (invariant 9). Panel coverage is phase
    1's `--coverage`, measured by phase 5 after phase 4's store refresh. This phase writes no
    docs file; phase 5 (`P1-ENG-M3HE`) writes this finding into
    `docs/runbooks/data-pipeline.md` and §4 of
    `docs/plans/2026-10-05-fundamental-panel-coverage.md`.
- [x] **P1-ENG-K8RV** Phase 4: Refresh the store's panel without re-downloading bars
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/research.py` (a refresh that reuses an existing store's `bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` byte for byte, writes a new `fundamentals.csv`, re-seals and swaps), the `--refresh-fundamentals` flag, its two handlers and one additional branch in `run()` on `engine/src/seer_engine/commands/research_store.py`, and `engine/tests/test_research_store.py`. Does not touch `build_store`'s existing download path, `load_store`, `MANIFEST_KEYS`, `_COUNT_KEYS`, the fingerprint algorithm, `fundamentals/` (phase 1), phase 1's `--coverage` flag, its `_coverage` handler and its branch in `run()` — all three must survive this edit unmodified — or `engine/.research/` itself, which phase 5 runs. The branch order in `run()` is guards → `--coverage` → `--verify` → `--refresh-fundamentals` → build, quoted verbatim from phase 1's landed body; neither phase converts `--verify` into a mutually-exclusive argparse group and `--verify` with `--coverage` still resolves to `--coverage`. The phase exists because `build_store` always fetches FX and downloads every symbol's bars, so rebuilding to pick up the new panel would replace all 2,490,793 bar rows and break comparability with the 64 recorded trials; the manifest's counts for copied files are carried over or recomputed from the copied files, never re-derived from a download. Exit: a test builds a store with facts A, refreshes it with facts B, and asserts `bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` are byte-identical before and after, that `fundamentals.csv` changed, that the fingerprint changed, that every `_COUNT_KEYS` value is unchanged and that `load_store` accepts the result; a second test asserts the refresh refuses rather than half-writing when the source store is missing or fails verification; the `.tmp`/`.old` swap discipline and the "nothing is written on failure" guarantee hold; phase 1's `--coverage` branch is still reachable and still wins over `--verify`. Suite green at +13.
  - **Status**: completed
  - **Plan Set**: `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` (phase 4 of 5)
  - **Satisfies**: R4 — Honest reporting (§8.3): the resulting coverage is measured across the whole dev window and written down as it is
  - **Depends on**: P1-ENG-TJ4M
  - **Plan**: `.workflows/plan/P1-ENG-K8RV.md`
  - **Completed**: 2026-10-05 14:50
  - **Method**: /do
  - **Files**: engine/src/seer_engine/research.py, engine/src/seer_engine/commands/research_store.py, engine/tests/test_research_store.py
  - **Decided**:
    - Staging in a worktree shared with phase 2's in-flight edits -> commit by explicit pathspec only, never `git add -A` / `git commit -a` (rung 6: surrounding convention, phase 1 held the same discipline; plus the "narrower blast radius" tie-break)
    - May readme-updater write `engine/package_readme.md`? -> No, skipped (rung 2/3: phase 4's plan lists it under "Leaves alone (owned by others) — phase 5", and phase 5's `Owns` claims it)
    - Completed block left in place under `### [P1] High` rather than moved to `## Completed Tasks` (rung 6: phase 1 of this set did the same an hour ago, and TJ4M/AHLW/DKWU all sit there checked; a 10-line move 1000 lines down this file is the largest avoidable conflict surface against the live phase 2 session)
    - `P1-ENG-M3HE` left `blocked`, not flipped to `open` (rung 4: its `Depends on` names four phases and only TJ4M and K8RV have landed — phase 2 is in_progress, phase 3 blocked. Marking it open would claim it is runnable when it is not)
    - `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` left untouched (rung 6 + rung 4: the swarm ledger at `.workflows/orchestration/fundamental-panel-coverage/ledger.json` is this set's phase tracker and the coordinator writes it; phase 1 likewise left `**Status:** reconciled` alone, and a linear "phase N/5 complete" would misreport a set completing out of order)
    - No `**Commit**` field (rung 2: this phase is one commit carrying both code and bookkeeping, so the sha cannot name itself; phase 1's field came from /implement's separate `chore(todos)` commit)
  - **Notes**: Verified under the set's Runtime preamble (`PYTHONPATH` over main's venv, resolving to the worktree). Full suite 6 failed / 2255 passed / 332 skipped against an inherited baseline of 6 failed / 2242 passed / 332 skipped — **+13**, the planned delta, with the identical 6 pre-existing `test_cik.py` failures (phase 2's in-flight work, not touched by this phase) and no existing test changing its result. With `PG_TEST_URL`: 6 failed / 2587 passed, same 6. `test_research_store.py` collected 34 → 47 = +13 (10 functions, one parametrized ×4). `git diff` shows 0 deletions in both `research.py` and `research_store.py`, so phase 1's `--coverage` flag, `_coverage` handler and `run()` branch are intact. No store on disk, database or network was touched — phase 5 runs the refresh against the real `engine/.research/`.
- [x] **P1-ENG-M3HE** Phase 5: Measure, report honestly, and retire the runbook snippet
  - **Difficulty**: NORMAL
  - **Type**: Update
  - **Context**: Owns running phase 4's refresh against the real store with phase 3's facts and phase 1's `--coverage` against the result; `docs/runbooks/data-pipeline.md` — the whole file's fundamental-panel surface, `:188-256` (the snippet replaced by the command, the measured numbers replacing the 2026-10-05 ones) and, assigned by reconciliation, `:151-175` and the stale scope lines at `:12,:15,:44,:51`; `docs/plans/2026-10-05-fundamental-panel-coverage.md` §4 (the `~14%` / `~30%` estimates replaced by measurements, the rest untouched); `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py`'s "READ THIS BEFORE RUNNING" preamble (pointing at the gate instead of a `python -c` one-liner, and saying M0005 is spent); `engine/package_readme.md`; and pushing the refreshed store with `/sync-research-store push`. Does not touch any `engine/src` file outside the one method docstring, `ticker_cik.csv`, the database, or any other `docs/plans/*.md`; it does not run `lab run`, does not mint a variation method and does not touch the test window. R5 is verified rather than re-implemented: `2dad9ff` already made `load_market_window` pass `fundamentals=` and added three tests at `engine/tests/test_paper_store.py:554`, `:573` and `:585`, and this phase confirms all three pass with `PG_TEST_URL` set, that `engine/src` has exactly three `Market(` construction sites all passing `fundamentals=`, and records §6.1 closed. The honesty clause is the deliverable: whatever the number is, the runbook and §4 state it, state that the dev window still opens 13 years before any XBRL exists, and state that the test-window decision remains unmade and out of scope. Exit: the `--coverage` output is pasted into the runbook with its date and the store's new fingerprint and described as an upper bound wherever quoted; §4's table has measured values in the `+ Fix A` and `+ Fix B` rows or the explicit words "not separately measured" and why; the runbook's two copy-paste Python blocks are gone and commands stand in their place; the duplicated re-vendoring recipe is a pointer to `SOURCES.md` and no longer claims "98 of 133"; `grep '2015-01-02' docs/runbooks/data-pipeline.md` returns only lines whose subject is bars; `grep -c '<<'` over the four edited documents returns 0; the store is pushed with `--keep 0`, `e597367b…` is still listed remotely and the push's content hash is recorded; `git status` shows no stray file; suite green at +0 with and without `PG_TEST_URL`.
  - **Status**: completed
  - **Plan Set**: `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` (phase 5 of 5)
  - **Satisfies**: R4 — Honest reporting (§8.3): the resulting coverage is measured across the whole dev window and written down as it is; R5 — §6.1: `paper/store.py` must not silently build a `Market` with `EMPTY_PANEL`
  - **Depends on**: P1-ENG-TJ4M, P1-ENG-QD7X, P1-ENG-F2BN, P1-ENG-K8RV
  - **Plan**: `.workflows/plan/P1-ENG-M3HE.md`
  - **Completed**: 2026-10-05 16:24
  - **Method**: /do
  - **Files**: docs/runbooks/data-pipeline.md, docs/plans/2026-10-05-fundamental-panel-coverage.md, engine/package_readme.md
  - **Measured** (every figure below was produced by a command in this session; none estimated):
    - **THE HEADLINE — dev-window panel coverage 0.3151 (75 of 238 monthly samples), an UPPER
      BOUND**, by `research_store --coverage` on the refreshed store. Up from **0.0378**
      (9 of 238) on the pre-fix store `e597367b…` under the identical measure. 869 panel
      symbols (was 780). First sampled date able to rank 20 names: **2009-08-02**. Still far
      below the `MIN_DEV_COVERAGE = 0.80` floor — phase 1's gate would refuse a `MarketAware`
      method on this store, and that refusal is correct.
    - **Fix A alone: 0.1387** (33 of 238), from re-running the same pure measure over the
      refreshed panel with facts filtered to `filed >= 2013-01-01`. So Fix A buys 2013–2014 and
      Fix B buys 2009–2012; §4's `~14%` and `~30%` estimates are both replaced by measurements.
    - It is an **upper bound every time it is quoted** (Decisions C8): the measure reads no bars,
      so index membership on the date, `min_price`, twenty sessions of history and
      `min_dollar_volume` are all unapplied and can only remove symbols. Below the floor is
      conclusive; above it would be necessary, not sufficient.
    - **Store refresh** (phase 4's `--refresh-fundamentals`, against the real `engine/.research/`
      in the main checkout): fingerprint `e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3`
      -> **`399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8`**. 1,213,303 facts
      written; 2,490,793 bar rows carried over unchanged; `sha256sum -c` confirmed `bars.csv`,
      `dividends.csv`, `fx.csv` and `unserved.csv` all byte-identical; `--verify` passes all three
      data checks.
    - **Blob push**: `sync_store.py push --keep 0` -> `seer/research-store/399d0d25….tar.gz`,
      45.2 MB, `"pruned": []`. `e597367b…` confirmed **still listed** remotely afterwards
      (`current: false`). Local backup kept at `/home/miftah/.seer-store-backup-e597367b`.
    - **Suite: 2261 passed / 332 skipped, delta +0** off the inherited 2261/332 — exactly the
      planned delta; no test added, no existing test changing its result. With
      `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`: **2593 passed, 0 failed,
      0 skipped**. Run under the set's Runtime preamble (`PYTHONPATH=$SEER_WT/engine/src` over
      main's venv, resolving to the worktree; no worktree venv built).
    - **R5 / §6.1 CLOSED by verification, no code written.** Exactly three `Market(` construction
      sites in `engine/src`, all passing `fundamentals=`: `backtest/io.py:156`,
      `paper/store.py:1058`, `research.py:682`. The three tests at
      `engine/tests/test_paper_store.py:554`, `:573`, `:585` all pass with `PG_TEST_URL` set
      (3 passed, 26 deselected).
    - **Siblings' findings carried into the docs** (phases 2 and 3 asked for these): the real
      floor is ~2011, not 2009 — 2009 holds 22,219 facts / 403 filers (~25% of a full year),
      2010 60,550 / 670 (~67%), 2011 90,505 / 729 (first year at baseline), 2012 99,641 / 738 —
      and 2009–2010 are large-cap-skewed because XBRL phased in by filer size, which matters more
      for a *ranking* method than the raw shortfall. Fix A unblocked facts already stored: 2013
      and 2014 had **zero** panel rows before and now have 74,248 and 74,339; the panel went
      831,725 rows / 780 symbols to 1,213,351 / 869. And the clamp was hiding **wrong** answers,
      not merely missing ones — `MFE`->MCAFEE COM CORP, `JNS`->a non-filer, `AKS`->a non-filing
      subsidiary, `WFT`->Weatherford Enterra, and `DIS`/`XRX`/`SNDK`->2019 holdcos and a 2025
      spinoff (phase 2 asked specifically that the `SNDK` case be named; it is).
    - **The honest reading, written into both documents**: this is better data, not a valid test.
      The dev window opens 1996-01-03 and XBRL does not exist before roughly 2009, so ~13 of its
      19 years are permanently uncoverable from EDGAR at any price. The `>= 100 trades` gate stays
      unreachable for a fundamentals method on this dev window. The test-window decision remains
      **unmade and out of scope**. No `lab run` was invoked, no method id or variation was minted,
      the post-2015 test window was not touched, and Neon was never contacted (the DSN proved
      `localhost:55432` before the one write).
  - **Drift**:
    - The phase plan's Runtime preamble has a corrupt line `export SEER_PY=/home/miftah/seer/"$SEER_PY"`. The plan index's own Runtime preamble has the correct `/home/miftah/seer/engine/.venv/bin/python`; used that (rung 1, the index is the reconciled copy).
    - `research.py`'s `Market(` construction site is at `:682`, not `:583` as the plan's Step 7 quoted — phase 4 inserted code above it. Still exactly three sites in `engine/src`, all passing `fundamentals=`.
    - `engine/package_readme.md`'s `--with-fundamentals` bullet ends at `:342`, not `:339` as Step 11b quoted. Insertion anchored on text, not line number.
  - **Decided**:
    - Step 10 (rewrite the M0005 docstring preamble) applied, then **REVERTED** -> the file is frozen. Rung 1 (invariant 1: no existing test may change its result). `engine/tests/test_lab_methods.py::test_a_method_that_ran_is_frozen` compares `source_sha(path)` against the committed lab database and a docstring edit moves it; the edit was made, the test failed (dd9344c7… -> 1422f4b7…), the edit was reverted and the suite returned to 2261 passed. Step 10's own contingency anticipated this ("If a test pins this file's `source_sha`, stop … and leave the file alone"). The information was instead written into `docs/runbooks/data-pipeline.md`, which now states that the M0005 docstring still prints the retired manifest one-liner, that it cannot be corrected without minting a variation method, and that the runbook section is the current instruction. **One exit-criterion clause ("the manifest one-liner is gone from the M0005 docstring") is therefore NOT met, and is reported as not achievable rather than as done.**
    - `readme-updater` **not** dispatched. Rung 2/3: phase 5's exit criteria and its Step 11 make `engine/package_readme.md` this phase's own deliverable carrying figures this phase measured; a second writer could restate a figure it did not run (invariant 10).
    - Runbook `:12` and `:45` left at 2015-01-02. Rung 3: Step 8b-i states explicitly that those lines' subject is BARS (`backfill`'s `DEFAULT_START`), a different constant phase 2 deliberately did not move. Only `:15` and `:51`, whose subject is the fundamentals scope, were changed to 2009-01-01 / 913 symbols.
    - Local store backup `/home/miftah/.seer-store-backup-e597367b` (227 MB) **KEPT** rather than deleted. Tie-break "take the reversible option" — Step 12 makes deletion optional and keeping it buys a network-free rollback.
    - Completed block left in place under `### [P1] High` rather than moved to `## Completed Tasks` (rung 6: TJ4M, QD7X, K8RV — every landed phase of this set — plus AHLW and DKWU all sit checked under that heading; moving only phase 5 would scatter one set across two sections).
    - `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` left untouched (rung 6 + rung 4: the swarm ledger at `.workflows/orchestration/fundamental-panel-coverage/ledger.json` is this set's tracker and the coordinator writes it; phases 1, 3 and 4 all made the same call).
    - **The set was NOT landed.** `swarm.py find --plan FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` returns `{"swarm": true, "coordinator": "orch-fundamental-panel-coverage"}`; per `analyze-orchestrator.md` Step 5 the merge belongs to that coordinator. No merge to main, no push to main, no branch or worktree deletion.
  - **Handoff left open**: `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py`'s docstring still points operators at the retired `python -c` manifest gate and cannot be corrected while the method is frozen. Anyone minting the `source_kind='variation'`, `parent_id='M0005'` re-test should write the corrected preamble into the new file. The runbook now says so explicitly.
- [x] **P1-ENG-AHLW** Phase 7: Fundamental factor allocator, lab method, runbook
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `seer_engine/strategies/f_fundamental.py`, a lab method `seer_engine/lab/methods/m0005_<slug>.py`, the `fundamentals` rows in `docs/runbooks/data-pipeline.md`, `engine/tests/test_f_fundamental.py`, and the one branch added to `engine/tests/test_lab_methods.py:85–93` — no other phase touches that file. Does not touch `f_factor.py`, `seer_engine/fundamentals/*`, `backtest/*`, `strategies/allocator.py`, or `seer_engine/research.py` (phase 6 owns the research store). Exit: the allocator ranks on value, quality, profitability and SUE with eligibility rules in the style of `f_factor`, reading phase 5's annual flows through one `panel.as_of(symbol, t)` call per symbol; it implements phase 6's `MarketAware` by defining `prepare_market` and does not widen `Allocator`; its id (`FND`) is unique across lab methods; the method declares 6 fixed variants, and the SUE-free ones pass a hermetic end-to-end dev-window test over a real `FundamentalPanel` while the SUE-ranking ones (including both composites, since `rank="composite"` reads every factor) are held to the criterion a synthetic annual panel can meet: they rank nobody and raise nothing, because `Snapshot.sue` is NaN without a quarterly EPS series. `lab run M0005` is NOT executed by this phase — `runner.preflight` refuses a second run of any method, so one premature run against a store without fundamentals would record all-cash trials and burn the method id permanently; the warning goes in the method docstring and the runbook, which documents the command, its exit codes and how to re-vendor `ticker_cik.csv`.
  - **Status**: completed
  - **Plan Set**: `EDGAR_FUNDAMENTALS_PLAN.md` (phase 7 of 7)
  - **Satisfies**: R6 — Factor exposure to the lab: value, quality, profitability, SUE; consensus surprise out of scope
  - **Depends on**: P1-ENG-9U93, P1-ENG-0LUS
  - **Plan**: `.workflows/plan/P1-ENG-AHLW.md`
  - **Completed**: 2026-10-05 11:20
  - **Method**: /implement
  - **Commit**: 81d2256
  - **Decisions**: quality ranking expectation CCC,DDD,AAA,BBB -> CCC,AAA,DDD,BBB (rung 3, `_row` + `rank_rows`); SUE-ranking test's `fundamental_rows` call corrected to the 5-arg form with a real history (rung 3, Step 1's signature); `NO_FLOOR` min_price 0.0 -> 0.01 (rung 3, `__post_init__` rejects < 0.01 and `test_params_reject_bad_values` pins it); dev-window test 400 -> 460 sessions filtered to <= DEV_END (rung 2, the exit criterion requires the run to end on DEV_END); bookkeeping committed from the main context rather than via pusher (rung 5, the coordinator's shared-worktree ruling after this set's measured sweep incident).
  - **Notes**: `lab run M0005` was NOT executed, by design — `runner.preflight` refuses a second run of any method. Also fixed `engine/package_readme.md`'s purity-glob sentence (four packages, two impure edges), a stale line two phases flagged and neither owned.
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

- [x] **P1-ENG-7KQ2** Phase 1: The roster becomes data: `status`, `paper_end`, and a name→object resolver
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `db/migrations/006_roster.sql`, `engine/src/seer_engine/paper/roster.py`, the read side of `engine/src/seer_engine/paper/store.py`, and `engine/tests/test_paper_roster.py`. Does not touch `commands/paper.py`'s night logic (phase 2), the comparison math (phase 3), anything under `web/` (phase 4), or `backtest/registry.py` (never). 006 adds **seven** columns to `strategies`, additively — `status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired'))`, `paper_end date`, `promoted_from text`, `object_name text`, `registry_id text`, `gate_note text`, `gate_applicable boolean NOT NULL DEFAULT true` — and backfills the four definition columns on the five rows 003/004 inserted. `roster.RESOLVER: dict[str, Binding]` maps a stable object name to the live Python object; `roster.from_row`/`from_rows` build `RosterEntry` values from database rows through it; and `ROSTER` becomes `from_rows(SEED_ROWS)`, so the compiled roster travels the *same* builder as the stored one and the pins prove the data path rather than sitting beside it. Exit: `store.read_roster_rows(conn)` returns the `engine IS NOT NULL` rows by `(sort, id)` and `roster.from_rows(store.read_roster_rows(conn)) == roster.ROSTER` against a migrated database; the five existing entries resolve to byte-identical `spec_digest` values and `test_paper_roster.py`'s pinned digests pass unchanged; an unresolvable `object_name` raises `UnknownObject` naming the strategy id *and* the object name and poisons the whole build rather than dropping one entry (invariant 9), covered by a test; `ROSTER`/`ROSTER_IDS`/`MAX_LOOKBACK_BARS`/`entry` keep working for callers that have not moved, and `MAX_LOOKBACK_BARS` stays 253 and is this phase's alone (D12).
  - **Status**: completed
  - **Plan Set**: `ROSTER_PROMOTION_PIPELINE_PLAN.md` (phase 1 of 6)
  - **Satisfies**: R2 — Replace the four horsemen easily — swapping an approach must not require editing engine code
  - **Plan**: `.workflows/plan/P1-ENG-7KQ2.md`
  - **Completed**: 2026-10-05 18:03
  - **Method**: /implement
  - **Files**: db/migrations/006_roster.sql, engine/src/seer_engine/paper/roster.py, engine/src/seer_engine/paper/store.py, engine/tests/test_paper_roster.py
  - **Verified**: `pytest engine/tests/test_paper_roster.py -q` with `PG_TEST_URL` -> 36 passed (20 existing + 16 new); the five pinned `spec_digest` values in `PINS` pass unchanged. Invariant 2 proved by byte-identity: `spec_text`, `spec_digest`, `strategy_params` and `lookback` captured before the rewrite and compared after -> identical for all five entries; the identity assertions (`is STRATEGY_A`, `is STRATEGY_A_PARAMS`, `is DESIGN_V0`, `is STRATEGY_C`, `is STRATEGY_C_PARAMS`, `is FACTOR`, `is TIMING`, `is MONTHLY_HOLD`) all hold; `MAX_LOOKBACK_BARS` still 253 (D12). `ruff check engine/src engine/tests` -> all checks passed. `pytest engine/tests/test_strategy_purity.py -q` -> 3 passed (`roster.py` stays pure). Full suite WITHOUT `PG_TEST_URL`: 2273 passed, 336 skipped — delta +12 passed, +4 skipped off the plan's 2261/332 baseline, measured before the peer's test file existed, so it is a clean measure of phase 1 alone. Full suite WITH `PG_TEST_URL`: 2648 passed, 0 failed, 0 skipped = baseline 2593 + 16 (phase 1) + 39 (the concurrent phase 3) — phase 1's own delta is +16 passed. Migration applied twice into a scratch schema: idempotent (`ADD COLUMN IF NOT EXISTS` skips), seven columns present with `status`/`gate_applicable` NOT NULL + defaults and the rest nullable, all five rows backfilled, and the `status` CHECK live (`'zombie'` raises CheckViolation); scratch schema dropped.
  - **Drift**:
    - No code drift: `store.py:104-152` and `roster.py` matched the plan's quotes byte for byte.
    - The plan's prose says "+15 tests (12 pure, 3 pg-gated)" but its own code block contains 16 (12 pure, 4 pg-gated). Implemented all 16 per the code block; the prose arithmetic was simply off by one. The index's test-delta table (`| 1 | +15 passed | +12 passed, +3 skipped |`) therefore reads one low against the measured +16 / +12+4; the measurement above is the honest number.
    - A concurrent peer session implemented phase 3 in this same worktree and left `engine/src/seer_engine/paper/compare.py`, `engine/src/seer_engine/commands/compare.py` and `engine/tests/test_paper_compare.py` in the tree (and in the shared index). They are NOT phase 1's and were deliberately kept out of this commit's pathspec.
  - **Decided**:
    - Task package for phases 1, 2, 3, 5, 6 -> `engine`, phase 4 -> `web` (`db/` has no `.workflows/`) (rung 6: surrounding code convention).
    - The plan prose's "+15 tests" vs its code block's 16 -> implemented the code block's 16 (rung 3: the phase plan's code blocks outrank the prose around them).
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded two blocks above by phase 3 of this same set, and by all five phases of the previous swarm in this same file). Five peer sessions hold this one file open in one shared working tree; a cross-file block move is the single edit most likely to clobber a peer's concurrent append.
    - Completion: no `**Commit**` field (rung 6: phase 3's entry in this file, immediately above, has none either). `engine/.workflows/todos.md` is committed *inside* the phase's own commit, so a field naming that commit's sha cannot exist in it, and the alternatives — `--amend` after a push, or a second commit — either need a force-push or add a rewrite to a branch five peers are committing onto. The sha is reported to the set's coordinator and is one `git log` away.
    - Completion: the plan index's `**Status:**` left at `reconciled` and no per-phase tick added (rung 6: phase 3's recorded decision in this file). The phase table has no status column, and adding one would mean rewriting all six rows of a file five peer sessions hold open — the maximal conflict surface. `.workflows/orchestration/roster-promotion-pipeline/ledger.json` is the per-phase status of record for a swarm-tracked set, and a single scalar cannot represent out-of-order concurrent completion. Phase 2's `P1-ENG-J5XD` was unblocked (`blocked` -> `open`) because its stated dependency genuinely landed; no other peer phase's task was touched.
- [x] **P1-ENG-J5XD** Phase 2: Retire and activate: the paper night honours roster lifecycle
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/commands/paper.py`, the write side of `engine/src/seer_engine/paper/store.py`, `engine/src/seer_engine/commands/paper_check.py` if the replay needs it, and `engine/tests/test_paper*.py`. Does not touch `roster.py`'s resolver (phase 1 owns it), the migration (phase 1), or `web/`. Exit: `commands/paper.py` and `commands/paper_check.py` source their entries from `roster.from_rows(store.read_roster_rows(conn))` — **not** from `roster.ROSTER`, and not from `read_strategies`, which returns legacy rows `from_rows` correctly refuses; `paper` skips `status='retired'` entries with no orders, no equity snapshot and no `paper_state` step; retiring sets `paper_end` to the last session actually traded, at retirement time through `store.retire` or on the next night through `store.set_paper_end` for a retirement taken by hand, and never deletes a row; a strategy added as `active` with no `paper_start` starts on the next night exactly as a new entry does today (`store.freeze_spec`); `store.check_digest`'s `SpecMismatch` refusal is still reachable on every active started strategy and `test_changed_frozen_spec_is_refused` still passes untouched; an unresolvable roster entry fails the night with a named error, writes nothing, and its message contains neither "retired" nor "skip" so the two skips are never confusable (invariant 9); `store.retire` is the only writer phase 5 may use for a retirement and re-retiring is a no-op returning the stored `paper_end`, so an interrupted swap can be re-run; and `paper_check` replay passes over a window containing a retirement.
  - **Status**: completed
  - **Plan Set**: `ROSTER_PROMOTION_PIPELINE_PLAN.md` (phase 2 of 6)
  - **Satisfies**: R2 — Replace the four horsemen easily — swapping an approach must not require editing engine code
  - **Depends on**: P1-ENG-7KQ2
  - **Plan**: `.workflows/plan/P1-ENG-J5XD.md`
  - **Completed**: 2026-10-05 18:44
  - **Method**: /do
  - **Files**: engine/src/seer_engine/commands/paper.py, engine/src/seer_engine/commands/paper_check.py, engine/src/seer_engine/paper/store.py, engine/tests/test_paper_command.py, engine/tests/test_paper_store.py, engine/tests/test_paper_check.py, engine/tests/test_paper_c.py
  - **Verified**: `ruff check engine` all passed; `compileall` clean on the three sources. Phase surface (test_paper_command/store/check/roster) 114 passed. Full engine suite WITH `PG_TEST_URL`: 2659 passed, 0 failed; WITHOUT: 2309 passed, 350 skipped. Inherited baseline MEASURED in a throwaway detached worktree at HEAD (7f2241d): 2648 passed with PG, 2309 passed / 339 skipped without. **Delta +11 passed / +0 skipped with PG, +0 passed / +11 skipped without — exactly the plan index's stated phase-2 delta. No existing test changed its result.** Manual dry-night check could not reach the roster (the local train DB has no bars run for session 2026-10-06, so `paper` exits at flow step 2); the log line it was meant to eyeball is asserted directly by `test_retiring_by_hand_stamps_paper_end_on_the_next_night` via caplog.
  - **Drift**:
    - Line numbers in the plan's Files table were a few lines off after phase 1 landed; every anchor matched by exact text, no semantic drift.
    - `test_paper_c.py` was not in the plan's Files table but is inside the phase's Owns (`engine/tests/test_paper*.py`). Its two tests that simulate "before C landed" by monkeypatching `roster.ROSTER` stopped working once `paper`/`paper_check` source entries from the database: one failed outright, the other passed vacuously. Translated `four_only()` to the data layer with new `hide_c`/`land_c` helpers (clear and restore `strategies.engine`, which is exactly what `read_roster_rows` filters on). Both tests pass and now test what they claim again.
  - **Decided**:
    - `test_an_unresolvable_roster_entry_stops_the_night_and_is_not_a_skip` asserted `everything()` unchanged, but a deliberately failed night DOES write its `runs` row (`paper_status=failed` + `paper_error`), which Step 4 of the plan requires -> switched the assertion to `content()`, the existing precedent in `test_changed_frozen_spec_is_refused`. (Rung 2/3: exit criterion 5 "writes nothing" means writes no paper data, and the plan's own Step 4 code block states the failure writes `runs.paper_error`.)
    - `test_paper_c.py`'s `roster.ROSTER` monkeypatch no longer hides a strategy from a night -> translated it to the data layer rather than leaving it inert. (Rung 1: invariant 1, no existing test may change its result; rung 6: the test's own `four_only()` docstring, "the roster as it was before C landed".)
    - `ruff format --check` reports 254 files would be reformatted across `engine/` -> not treated as a gate. (Rung 6: verified identical at HEAD for the same files; the repo has never been `ruff format` clean, only `ruff check` is enforced, and it passes.)
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded by phases 1 and 3 of this same set in the two blocks above, and by all five phases of the previous swarm in this same file). A cross-file block move is the single edit most likely to clobber a peer's concurrent append in a shared worktree.
    - Completion: no `**Commit**` field (rung 6: phases 1 and 3 above have none either). This file is committed *inside* the phase's own commit, so a field naming that commit's sha cannot exist in it; the sha is reported to the set's coordinator and is one `git log` away.
    - Completion: the plan index's phase-2 row ticked and its `**Status:**` advanced to `phases 1, 2, 3, 4 of 6 complete`. This REVERSES phase 1's recorded decision to leave both alone, because the premise of that decision no longer holds: the index as it stands already carries ✅ on rows 1, 3 and 4 and already names the completed phases on its Status line, so leaving row 2 blank would now misreport the set rather than avoid a conflict (rung 6: the file's own current state outranks a decision its later edits superseded). Edit confined to one table row and one line.
    - Completion: `P1-ENG-Z8MR` (phase 5) unblocked `blocked` -> `open` — both its stated dependencies, `P1-ENG-7KQ2` and `P1-ENG-J5XD`, have now landed. `P1-ENG-H3WF` (phase 6) left `blocked`; it depends on phase 5, which has not.
    - Completion: landing NOT attempted. `swarm.py find --plan ROSTER_PROMOTION_PIPELINE_PLAN.md` returns `swarm: true` with coordinator `orch-roster-promotion-pipeline`, and this is phase 2 of 6 in any case — the merge belongs to the set's coordinator.
- [x] **P1-ENG-Z8MR** Phase 5: `promote`: the lab → roster bridge
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `engine/src/seer_engine/commands/promote.py`, `engine/src/seer_engine/lab/store.py` (recording the promotion) and its tests. Does not touch `backtest/registry.py` (D1), the paper night (phase 2 owns it), or `web/`. Exit: `promote --method M --candidate M-X --id <roster-id> [--retire <id>]` inserts a `strategies` row with `status='active'`, `promoted_from='<method id>'`, **the definition columns (`object_name`, `registry_id` NULL, `gate_note`, `gate_applicable`)**, full contract-C2 `params` and no `paper_start`, so the next paper night starts its clock the ordinary way; the row it just wrote is read back and rebuilt through `roster.from_row` **inside the same transaction**, so a row the paper night would refuse never commits; it refuses — each with a named error — to reuse an id that already has a `paper_start` (invariant 3), an allocator the resolver does not name (naming the one `Binding(...)` line to add), a method whose variant is ambiguous, and a candidate whose rules are not a `sim.rules` preset; `--retire <id>` calls `store.retire` (phase 2's, never its own SQL) in the same transaction as the insert, so a swap is atomic and the board never shows five active horsemen or three; the lab database records the promotion against the method — `analysis` grown, one `insights` row — at **any** status, and moves `status` to `paper` only along the `('test-passed','paper')` edge `TRANSITIONS` already has, with `--lab-status-stays` recording without moving (the shape a `rejected` method needs) and `source_sha`, `hypothesis` and `verdict` untouched and no `TRANSITIONS` edge added; a dry-run mode prints every row it would write in both databases and writes nothing; and `backtest/registry.py` is byte-identical to `origin/main` (D1), pinned by a test.
  - **Status**: completed
  - **Plan Set**: `ROSTER_PROMOTION_PIPELINE_PLAN.md` (phase 5 of 6)
  - **Satisfies**: R4 — Promote a method found in a `/sera-the-explorer` session onto the main app's leaderboard
  - **Depends on**: P1-ENG-7KQ2, P1-ENG-J5XD
  - **Plan**: `.workflows/plan/P1-ENG-Z8MR.md`
  - **Completed**: 2026-10-05 19:09
  - **Method**: /do
  - **Files**: engine/src/seer_engine/commands/promote.py, engine/src/seer_engine/lab/store.py, engine/tests/test_promote_command.py, engine/tests/test_lab_store.py
  - **Verified**: `python -c 'import seer_engine.commands.promote as m; print(m.HELP)'` ok; `"promote" in cli.discover()` ok; `python -m seer_engine promote --help` ok. Targeted set (test_promote_command, test_lab_store, test_paper_roster, test_registry, test_lab_snapshot, test_cli): 170 passed. Full engine suite WITH `PG_TEST_URL`: **2683 passed, 0 skipped** (inherited 2659 -> delta **+24 passed, +0 skipped**). WITHOUT `PG_TEST_URL`: **2323 passed, 360 skipped** (delta **+14 passed, +10 skipped**). Both deltas are exactly the plan index's declared phase-5 delta, and 2683 total either way — the plan's consistency check holds. `ruff check` passed on all four files. D1 pinned: `git diff origin/main -- engine/src/seer_engine/backtest/registry.py` is EMPTY (byte-identical). Manual dry-run against a local migrated throwaway schema exits 2 with the designed "the roster resolver has no name for <FND> ... Add one entry to RESOLVER" refusal — the correct outcome at the end of THIS phase (phase 6 commits that line); `git status --porcelain lab/lab.sqlite web/data/lab.json` empty afterwards. No existing test changed its result; `test_paper_roster.py`'s five pinned spec digests pass unchanged.
  - **Drift**:
    - `lab/store.py` line numbers in the plan were ~13 lines ahead of the tree (`append_analysis` at :376, not :388; file 783 lines, not 796). Anchors were unambiguous; inserted by anchor, not by line number.
    - The plan's db tests patched `pg.close` to a no-op to keep the fixture connection usable. That DEADLOCKS the suite: the autouse `resolver_entry(monkeypatch)` fixture pulls monkeypatch into the closure first, so monkeypatch's undo runs LAST — after conftest's `pg_schema` teardown has already called the still-patched `close`. The connection survives holding its locks and the schema's `DROP ... CASCADE` blocks forever. Confirmed with `--setup-show` and `pg_stat_activity`. Replaced with a `_Borrowed` connection proxy whose `close()` only rolls back, so the fixture's own `close` is never patched. Every assertion the plan's tests make is preserved.
  - **Decided**:
    - `_check_target`'s second raw `SELECT promoted_from` -> read `row.promoted_from` off the `StrategyRow` the same block already fetched (rung 3, the phase plan's code blocks: phase 2's `StrategyRow` carries `promoted_from`, so the extra query is the same value plus a row-factory assumption).
    - Test named `test_promote_inserts_an_active_row_with_no_paper_start` renamed to `test_a_lab_without_the_method_refuses_before_writing`, which is what it asserts (exit 2 on a fresh lab), plus an added assertion that the roster stayed empty (rung 2, exit criteria: exit criterion 1 is proved by `test_promote_writes_the_row_the_night_expects`; the old name labelled a different test).
    - The plan's db tests patched `pg.close`, which deadlocked the suite -> `_Borrowed` connection proxy instead (rung 2, exit criteria: criterion 3 and the whole db half are unreachable while the suite hangs).
    - The plan's manual dry-run check reaches its designed refusal only after a `SELECT max(sort)`, so as written it opens production Neon. Ran it against a freshly migrated local throwaway schema instead (rung 1, invariant 8: no Neon write; the refusal does not depend on which Postgres answers).
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded by phases 1, 2 and 3 of this same set in the blocks above, and by all five phases of the previous swarm in this same file). A cross-file block move is the single edit most likely to clobber a peer's concurrent append in a shared worktree.
    - Completion: no `**Commit**` field (rung 6: phases 1, 2 and 3 above have none either). This file is committed *inside* the phase's own commit, so a field naming that commit's sha cannot exist in it; the sha is reported to the set's coordinator and is one `git log` away.
    - Completion: the plan index's phase-5 row ticked and its `**Status:**` advanced to `phases 1, 2, 3, 4, 5 of 6 complete`, following phase 2's recorded reversal rather than phase 1's and phase 3's original decision — the index already carries ✅ on rows 1–4 and already names the completed phases on its Status line, so leaving row 5 blank would now misreport the set. Edit confined to one table row and one line.
    - Completion: `P1-ENG-H3WF` (phase 6) unblocked `blocked` -> `open` — its sole stated dependency, `P1-ENG-Z8MR`, has now landed.
    - Completion: landing NOT attempted. `swarm.py find --plan ROSTER_PROMOTION_PIPELINE_PLAN.md` returns `swarm: true` with coordinator `orch-roster-promotion-pipeline`; per analyze-orchestrator Step 5 the merge belongs to the set's coordinator, and phase 6 has not run in any case.
- [x] **P1-ENG-H3WF** Phase 6: `FND` onto the roster — the first promotion through the new path
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns the `FND` `RESOLVER` entry and `SEED_ROWS` row in `paper/roster.py`, new `db/migrations/007_fnd.sql`, **`paper/book.py` and `paper/replay.py`'s `MarketAware` dispatch**, new `engine/tests/test_paper_fnd.py` plus the widened literals in `test_paper_book.py`, `test_paper_roster.py`, `test_migrate.py` and `test_paper_check.py`, and the "FND joined the roster" section of `docs/runbooks/paper.md`. Does not touch `f_fundamental.py`'s own logic, M0005's lab status/`source_sha`/`trials`, `REGISTRY`, `commands/promote.py` or `web/`. Exit: `FND` is on the roster as `active`, `sort=6`, `engine='book'`, `rules_id='monthly-hold'`, `object_name='FUNDAMENTAL'`, `registry_id IS NULL`, carrying an honest `gate_note` in the style of its neighbours — it has **not** passed a gate and must not claim to; it is added through phase 5's `promote --method M0005 --candidate M0005-ALL --id FND --lab-status-stays`, which also records the promotion in the lab, proving the pipeline rather than bypassing it (D7, D11), with the documented-equivalent SQL as the escape hatch only; `paper.book.decide_book` and `paper.replay.expected_book` dispatch a `MarketAware` allocator through `prepare_for` + `targets_prepared` so `FND` reaches `market.fundamentals` — without which it would hold cash forever while every log line said it decided — and for every allocator that is not `MarketAware` the expression is byte-identical to today's, so the five existing strategies replay bit for bit; the paper night produces orders or an explicit empty decision for `FND` against a `Market` carrying the fundamental panel and `paper_check` replays it as `ok`, never `mismatch`; a `Market` with no panel yields no trades, not wrong trades, asserted by a test at the roster level; `roster.FUNDAMENTAL_PARAMS` equals M0005's `COMPOSITE` by value, pinned by a test, because `roster.py` must never import a lab method and only that equality keeps the promoted row's frozen digest and the roster's recomputed digest the same; the five pre-existing `spec_digest` values are byte-identical and `MAX_LOOKBACK_BARS` is still 253 (`FND`'s lookback is 20); and nothing claims `FND` passed a backtest gate, with the go-live checklist's arithmetic still reading honestly with a fifth research strategy present (`CHECKS = 6` is per strategy; checked).
  - **Status**: completed
  - **Plan Set**: `ROSTER_PROMOTION_PIPELINE_PLAN.md` (phase 6 of 6)
  - **Satisfies**: R1 — Include the fundamentals-driven strategy in paper trading — the stated justification for excluding it does not hold, because paper is not real money and the gates bind only the real-money decision
  - **Depends on**: P1-ENG-Z8MR
  - **Plan**: `.workflows/plan/P1-ENG-H3WF.md`
  - **Completed**: 2026-10-05 19:51
  - **Method**: /do
  - **Files**: db/migrations/007_fnd.sql, docs/runbooks/paper-trading.md, engine/src/seer_engine/paper/book.py, engine/src/seer_engine/paper/replay.py, engine/src/seer_engine/paper/roster.py, engine/tests/test_paper_fnd.py, engine/tests/test_paper_book.py, engine/tests/test_paper_roster.py, engine/tests/test_migrate.py, engine/tests/test_paper_check.py, engine/tests/test_paper_store.py, engine/tests/test_paper_c.py, lab/lab.sqlite, web/data/lab.json
  - **Verified**: `ruff check engine/src engine/tests` passed. Full engine suite WITH `PG_TEST_URL`: **2700 passed, 0 skipped** (phase 5 inherited 2683 -> delta **+17 passed, +0 skipped**); WITHOUT `PG_TEST_URL`: **2340 passed, 360 skipped** (inherited 2323/360 -> same **+17/+0** delta, because `test_paper_fnd.py` touches no database). The plan declared +16; the 17th is the deliberate night-vs-replay agreement test recorded under Decided. Invariant 2 holds — the five pre-existing `spec_digest`s are byte-identical (SPY `ca309ea7…`, A `37cd89be…`, F4 `6c55c13a…`, F1 `e7fbb32d…`, C `6cea6cb8…`); `FND`'s is `4a9dacc37478bf4d17b3ba35cbebd9e0c3f8759f122c4596f7cd9d076d8ef530`, exactly the plan's pin, and its `spec_text` matches the plan byte for byte. D12 holds: `MAX_LOOKBACK_BARS` is still 253 (`FND`'s lookback is 20). D1 holds: `git diff origin/main -- engine/src/seer_engine/backtest/registry.py` is EMPTY.
  - **Promotion**: Step 6 ran dry-run then real `promote --method M0005 --candidate M0005-ALL --id FND --name 'FND · Fundamentals' --sub 'Top 20 by SEC filing factors, monthly' --icon book-open --sort 6 --lab-status-stays --gate-note '<the M0005 note>'` against a local schema migrated to 006. Wrote `id=FND`, `status=active`, `sort=6`, `engine=book`, `rules_id=monthly-hold`, `object_name=FUNDAMENTAL`, `registry_id=NULL`, `gate_applicable=t`, `paper_start=NULL`, `promoted_from=M0005`, and `params.digest 4a9dacc3…` — i.e. the frozen digest `promote` computes equals the digest the roster recomputes. Schema dropped afterwards. Lab record: `lab stage` wrote `lab/lab.sqlite` and `web/data/lab.json`; M0005 is still `status='rejected'` with its 64-char `source_sha` and 6 trials untouched; `methods.analysis` grew one `# Promotion` section and `insights` grew one observation row.
  - **Drift**:
    - `docs/runbooks/paper.md` does not exist; the runbook is `docs/runbooks/paper-trading.md`. Appended the "FND joined the roster" section there (small drift, plan intent followed).
    - The plan's `test_paper_fnd.py` fixtures used constructor spellings that have drifted: `Membership` intervals are 3-tuples `(symbol, start, end)` not 4; `stratkit.hist` is `hist(symbol, closes, days=..., volumes=...)` not `hist(symbol, days, closes, volume=...)`; `session_days` is `(n, start)` not `(start, end)`. Adapted per the plan's own implementer note ("the assertions are the contract; the fixture spelling is not").
    - `rank='composite'` reads all four factors and `fundamental_rows` drops a row whose SUE is NaN, so the panel fixture needed 10 quarters of diluted EPS (`sue.MIN_QUARTERS=9`), not the plan's single annual filing. Also the plan's $100+ closes made every whole-share order `too_small` against a $1,250 book at 1/20 weights; closes lowered to single digits (still over `min_price=5`, dollar volume ~$30–70M, over the $20M floor).
    - Four more existing tests needed the same literal widening the plan prescribed for three others, and the plan did not list them: `test_paper_roster.py` (the 5-way unpack in `test_each_entry_is_the_named_object_params_and_rules`, two `active(...)` lists, and the `promoted_from`-is-NULL assertion, which `FND`'s row legitimately breaks), `test_migrate.py` (`rows[-1]` is no longer C), `test_paper_store.py` and `test_paper_c.py` (`ROSTER[-1].id == C`). All widened minimally; no assertion weakened.
  - **Decided**:
    - Step 6's promotion ran against a freshly migrated LOCAL throwaway schema, not live Neon (rung 1, invariant 9 + the tree): `origin/main`'s `db/migrations` stops at 005, so live Neon has no `object_name`/`status`/`promoted_from` columns for `promote` to write, and main's `RESOLVER` has no `FUNDAMENTAL` key — a live `FND` row would make `roster.from_row` raise `UnknownObject` and stop the WHOLE paper night for all five existing strategies until the set merges. The live write is a post-merge owner step. The lab half (`lab/lab.sqlite`, `web/data/lab.json`) was written for real and is committed.
    - The plan's exit criteria say "+14 passed" while its delta table says +16; the table is right (13 new tests in `test_paper_fnd.py` + 3 in `test_paper_book.py`) and +14 was stale (rung 3, the plan's own code blocks enumerate the tests).
    - Added a 14th test, `test_the_night_and_the_replay_decide_fnd_the_same_way`, beyond the plan's set (rung 2, exit criteria: "`paper_check` replays either outcome as `ok`"). With an EMPTY panel both dispatch branches return `()`, so every empty-panel test is vacuous for Step1/Step2 agreement — nothing in the plan's set would have caught a `prepared=` left off `replay.py`. The new test drives `replay.expected_book` directly against a real panel; verified by sabotage (setting `prepared=None` in `replay.py` makes it fail, restoring makes it pass).
    - `replay.py`'s `MarketAware`/`prepare_for` import merged into the existing `from seer_engine.strategies.allocator import Allocator` line instead of the plan's separate import after `decide_bracket` (rung 6, surrounding code: the module already imports from that path).
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded by phases 1, 2, 3 and 5 of this same set in the blocks above, and by all five phases of the previous swarm in this same file). Keeping the set's six phase blocks contiguous is what a reader of this set wants; splitting the last one off alone would scatter it.
    - Completion: no `**Commit**` field (rung 6: phases 1, 2, 3 and 5 above have none either). This file is committed *inside* the phase's own commit, so a field naming that commit's sha cannot exist in it; the sha is reported to the set's coordinator and is one `git log` away.
    - Completion: landing NOT attempted, and `next_command` is empty. `swarm.py find --plan ROSTER_PROMOTION_PIPELINE_PLAN.md` returns `swarm: true` with coordinator `orch-roster-promotion-pipeline`; per `analyze-orchestrator` Step 5 the merge of the whole set belongs to that coordinator, and landing it here too is the double-merge that rule exists to prevent. This is the set's last phase, so there is no successor task either.

- [x] **P1-ENG-5X3M** Phase 1: Make the backtest window a parameter, keeping D9 absolute
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns a new `backtest/window.py`, the window threading through `backtest/dev.py` (guards, `candidate_window`, `run_candidate`, `run_registry`, `DevRow.window` and the relaxation of `DevRow.__post_init__` to `check_dev_session(self.end, self.window)`), and `research.py`'s window-bearing helpers (`_members_start`, `_overlaps_window`, `requested_symbols`, `research_membership`, `unserved_by_year`, `unserved_reason`); sole editor of `engine/tests/test_research_store.py`. Leaves store build/load on disk, all of `lab/`, every CLI and `dev_report.py` alone. Exit: `DEV_END` unchanged in both modules and its equality test passes untouched; no manifest key added (`test_research_store.py:235`'s `set(manifest) == MANIFEST_KEYS` holds); `unserved_reason()` byte-identical to the retired `UNSERVED_REASON`, so the dev fingerprint `399d0d25…` cannot move; every existing caller compiles with no argument changes; a post-`DEV_END` bar is still refused under the dev window and accepted only when a test window is passed; the membership clamp is against the passed window's end and the universe is `[max(window.start, MEMBERSHIP_START), window.end]`; `lab run`'s digests byte-identical.
  - **Status**: completed
  - **Plan Set**: `BUILD_PROMOTION_PATH_PLAN.md` (phase 1 of 4)
  - **Satisfies**: R1 — A test-window research store (2015-10-19 → latest session), built like the dev store, with the same files, manifest and checks; R2 — `lab test <candidate>`: refuses without a committed pre-registration, runs once, records a `test` trial, sets `test-passed`/`test-failed`
  - **Plan**: `.workflows/plan/P1-ENG-5X3M.md`
  - **Completed**: 2026-10-06 12:54
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/window.py (new), engine/src/seer_engine/backtest/dev.py, engine/src/seer_engine/research.py, engine/tests/test_backtest_window.py (new), engine/tests/test_backtest_dev.py, engine/tests/test_research_store.py
  - **Verified**: `ruff check src tests` clean; full engine suite 2392 passed / 360 skipped in 160.91s (every skip `PG_TEST_URL`-gated and pre-existing). No venv on PATH in this worktree, so the suite ran under the main checkout's interpreter (`/home/miftah/seer/engine/.venv/bin/python`) with `PYTHONPATH` pointed at this worktree's `src`. The plan's three manual checks all confirmed: (1) `git diff -U0` over `dev.py` and `research.py` filtered on `DEV_END = ` printed nothing — the literal `date(2015, 10, 16)` is unchanged in both; (2) `test_fundamentals_coverage.py` (which pins `coverage.WINDOW_END == dev.DEV_END == research.DEV_END`) has a zero-line diff, and both `test_backtest_dev.py` (+93) and `test_research_store.py` (+54) are pure insertions with zero deletions, so no existing test function was edited; (3) `DEV_WINDOW.start == date.min`, which makes `candidate_window`'s new floor provably dead code on the dev window, so no recorded dev trial's start/end can shift. Also confirmed at runtime: `MANIFEST_KEYS` still holds exactly 9 keys (dev store fingerprint `399d0d25…` cannot move), `unserved_reason()` is byte-identical to the retired `UNSERVED_REASON`, and `dev.DEV_WINDOW == research.DEV_WINDOW`. Plan invariants 1-7 all hold; nothing wrote to `lab/lab.sqlite` or `web/data/lab.json` and no test-window look was spent.
  - **Drift**: none. Every code block in the phase plan applied against the tree exactly as quoted. A concurrent session is implementing phase 3 (which shares no dependency with phase 1) in this same worktree; its files are excluded from this phase's commit by the decision below.
  - **Decided**:
    - Which index to tick: `-f` named `.workflows/orchestration/build-promotion-path/PLAN.md`, but the committed index carrying the TaskID column is `BUILD_PROMOTION_PATH_PLAN.md` at the repo root -> tick the root index (rung 5: the plan's own Next block prints `-f BUILD_PROMOTION_PATH_PLAN.md`, and Step 3 wrote the TaskIDs there).
    - Shared worktree with a live phase-3 session -> commit only phase 1's six files plus the set-wide bookkeeping, leaving `lab/`, `commands/lab.py`, `docs/lab/` and `tests/test_lab_*` to phase 3 (rung 6: the index's File-ownership table makes `lab/` phase 3's region). Committed by explicit pathspec; no `git add -A`.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the precedent recorded repeatedly in this same file by the ROSTER_PROMOTION_PIPELINE and FUNDAMENTAL_PANEL_COVERAGE swarms). A cross-file block move is the one edit that reliably loses a peer's concurrent append, and a peer is appending to this file right now.
    - Completion: no `**Commit**` field (rung 6: the same precedent). This file is committed inside the phase's own commit, so a field naming that sha cannot exist in it; the sha is reported to the caller instead.
- [x] **P1-ENG-8OLO** Phase 2: Build and load the test-window store
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `research.build_store` / `load_store` / `refresh_fundamentals` window plumbing, `ResearchData.window`, the manifest's optional window identity (`window_name`, `window_start`, `window_end`) and `declared_window`, `TEST_STORE_DIR` / `TEST_WINDOW_START` / `test_window` / `latest_session`, the swap of `research._after_dev_end` for `_after_window_end`, `commands/research_store.py`'s `--test-window` and `--window-end`, and the `.gitignore` / ruff excludes for `engine/.research-test`. Leaves `backtest/` (phase 1), `commands/lab.py` and `lab/` (phases 3–4) and `test_research_store.py` alone, adding `engine/tests/test_research_test_store.py` instead. Exit: a test store builds into `engine/.research-test` via `research_store --test-window`; `load_store` verifies by fingerprint and refuses a dev store where a test store is expected and vice versa before any data file is read; membership clamps against the test window's end; the universe is the test window's members at both ends; the store's data still runs from `STORE_START` (1993-01-29) so the lookback run-up is present; `MANIFEST_KEYS` unchanged and a dev build writes no window key, so the dev store loads bit-identically (`399d0d25…`) and `test_research_store.py:235` passes unedited.
  - **Status**: completed
  - **Plan Set**: `BUILD_PROMOTION_PATH_PLAN.md` (phase 2 of 4)
  - **Satisfies**: R1 — A test-window research store (2015-10-19 → latest session), built like the dev store, with the same files, manifest and checks
  - **Depends on**: P1-ENG-5X3M
  - **Plan**: `.workflows/plan/P1-ENG-8OLO.md`
  - **Completed**: 2026-10-06 13:24
  - **Method**: /do
  - **Files**: engine/src/seer_engine/research.py, engine/src/seer_engine/commands/research_store.py, engine/tests/test_research_test_store.py (new), .gitignore, engine/pyproject.toml
  - **Verified**: new suite `tests/test_research_test_store.py` **28 passed**; `tests/test_research_store.py tests/test_fundamentals_coverage.py` **72 passed** with `git diff` on both files **empty** (untouched, as the plan requires); whole engine suite over phase 2 + the landed phase 3 **2452 passed / 360 skipped**, exit 0 (every skip a pre-existing `PG_TEST_URL` one); `ruff check src tests` clean. Against the **real 2.49M-row dev store**: `research_store --verify` exits 0, fingerprint still `399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8`, manifest still exactly 9 keys, all three checks ok, spy-dividends overlap still 2015-03-20..2015-10-16; `sync_store.py status` verifies the same fingerprint. All five command refusals exit 2 before any I/O: `--test-window` at the dev store dir; the test-store dir without `--test-window`; `--coverage --test-window`; `--window-end` without `--test-window`; a `--window-end` that is not an NYSE session. No test-window look spent and no lab state changed.
  - **Drift**:
    - Phase 1 kept the module constant `UNSERVED_REASON = unserved_reason()` rather than retiring it (`test_research_store.py` references it). Phase 2 followed the plan's `build_store` code — `unserved_reason(STORE_START, window.end)` — and left the constant in place. The dev store's `unserved.csv` text is byte-identical either way.
    - The plan's test file imported `yahoo` and `Path` without using them, and used `pd.Timedelta(days=1).to_pytimedelta()`; dropped the unused imports and used plain `timedelta(days=1)` (the plan's own note endorses this) so ruff stays green. The two inline monkeypatch blocks were factored into one `patched_build` helper — same behaviour.
    - `check_spy_dividends`' docstring says the vendored file "runs well past `DEV_END`" rather than the plan's hardcoded "2026-09-18", which is a date that moves as the file grows. Prose only.
  - **Decided**:
    - The plan's test asserted `members_on(2016-01-05) == {AAA, CCC}` but its own membership fixture (sp500 snapshot 2016-01-04 = AAA,CCC,NEW; ndx 2007-02-01 = AAA,DDD, never closed) yields `{AAA, CCC, NEW, DDD}` -> corrected the literal, not the code (rung 2: phase 2's exit criterion 4 "every company that joined the index after October 2015 is in it" and the sibling test's `assert "NEW" in test` both require NEW to be a member, so the literal was the stale half).
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded by phases 1 and 3 of this same set, and by every ROSTER_PROMOTION_PIPELINE and FUNDAMENTAL_PANEL_COVERAGE swarm in this file). A cross-file block move is the one edit that reliably loses a peer's concurrent append, and peers are appending to this file.
    - Completion: no `**Commit**` field (rung 6: the same precedent). This file is committed inside the phase's own commit, so a field naming that sha cannot exist in it; the sha is reported to the caller instead.
    - Landing and dispatch: not attempted, `next_command` empty. `swarm.py find --plan BUILD_PROMOTION_PATH_PLAN.md` returns `swarm: true` with coordinator `orch-build-promotion-path`, so per `analyze-orchestrator` Step 5 both the merge and the dispatch of phase 4 belong to that coordinator.
    - Phase 4 (`P1-ENG-YJDW`) flipped `blocked` -> `open`: it depends on phases 2 and 3, and with this phase landed both are complete.
- [x] **P1-ENG-AZ81** Phase 3: Pre-registration: `lab promote` and `docs/lab/prereg/`
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `lab/prereg.py` — the `docs/lab/prereg/MNNNN.md` format, its writer, its parser and the committed-file gate (`require_committed(candidate_id, *, directory=None) -> Prereg`, `check_digest(p, digest, *, directory=None)`, `PreregError(store.LabError)`) — plus `store.best_dev_eligible`, a `lab promote <method>` subcommand that writes the prereg file and moves `dev-eligible → promoted`, and `docs/lab/prereg/README.md`. Lands before phase 4 in `commands/lab.py` and is the earlier owner of that file's three insertion regions. Leaves `backtest/`, `research.py`, the test store and runner, `record_promotion`, `commands/promote.py` and every skill file alone. Exit: `lab promote` refuses a method that is not `dev-eligible`; writes exactly one prereg file carrying `method`, `candidate`, `config_digest`, `gate`, `test_window` and `date` (all `str`); is idempotent and never rewrites a committed file, not even its `date`; refuses to change which variant is pre-registered; a test proves the prereg digest is copied from the recorded dev trial's digest; the prose states the test look is judged by the five go-live conditions alone with DSR recorded and not applied, so the `gate` field cannot be read as the test gate; `store.test_looks` stays 0 and no `trials` row is written.
  - **Status**: completed
  - **Plan Set**: `BUILD_PROMOTION_PATH_PLAN.md` (phase 3 of 4)
  - **Satisfies**: R3 — Pre-registration of the best dev-eligible variant by MAR in `docs/lab/prereg/MNNNN.md`, committed before any test number exists
  - **Plan**: `.workflows/plan/P1-ENG-AZ81.md`
  - **Completed**: 2026-10-06 12:59
  - **Method**: /do
  - **Files**: engine/src/seer_engine/lab/prereg.py (new), engine/src/seer_engine/lab/store.py, engine/src/seer_engine/commands/lab.py, docs/lab/prereg/README.md (new), engine/tests/test_lab_prereg.py (new), engine/tests/test_lab_store.py
  - **Verified**: `import seer_engine.lab.prereg, seer_engine.commands.lab` ok; `ruff check src tests` clean; full engine suite **2407 passed / 360 skipped** with phase 3 alone on base `353d744` in a throwaway worktree, and **2424 passed / 360 skipped** in the shared tree that also carried phase 1's work (every skip `PG_TEST_URL`-gated and pre-existing). `python -m seer_engine lab promote --help` lists the subcommand; `lab promote M0007` exits 2 with "M0007 is 'rejected', and only a dev-eligible method is pre-registered". Against the real database `store.test_looks()` is **0** and `git status` shows no `lab/lab.sqlite` and no `web/data/lab.json` — no look was spent and no `trials` row written. All seven exit criteria met. Plan invariants 1–7 hold: `DEV_END` is untouched because this phase edits none of `backtest/dev.py`, `research.py` or `fundamentals/coverage.py`, and all three source edits are pure additions (90 insertions, 0 deletions), so `lab run` is behaviourally unchanged.
  - **Drift**:
    - None. Every anchor the plan quotes matched the tree exactly: `store.py` `trials_of` at `:568-569` with the `ideas_seen` divider at `:572`; `commands/lab.py` docstring `:9`, the `--allow-coverage` block ending `:78`, `_run` ending `:262`, `_HANDLERS` at `:375`; and `registry_problem`, `git_head`, `FAILURE_LABELS`, `DSR_LABEL`, `dates.next_session`, `config.REPO_ROOT`, `TRANSITIONS` and the `test_lab_store.py` `_method`/`_trial` fixtures all as described.
    - This worktree has no `engine/.venv`, so verification ran on the main checkout's interpreter (`/home/miftah/seer/engine/.venv/bin/python`) with `PYTHONPATH=<worktree>/engine/src`, verified to shadow the editable install (`seer_engine` resolves to the worktree).
  - **Decided**:
    - Where to verify, given a live peer session editing this same worktree -> ran the suite a second time in a throwaway worktree holding ONLY phase 3's six files on top of base `353d744` (rung 1: invariant 1 is per-phase, and the Rollback section makes each phase one revertible commit). Phase 3 alone: 2407 passed. The shared tree including the peer's work also passed: 2424 passed.
    - Whether phase 4 is unblocked -> NO (rung 4: the index's phase table). Phase 4 (`P1-ENG-YJDW`) depends on phases 2 **and** 3; phase 2 (`P1-ENG-8OLO`) has not landed, so phase 4 stays `blocked`. Only this task flips to completed.
    - Which paths this phase's commit may contain -> phase 3's six files plus the shared plan-set bookkeeping only; the peer's work-in-progress is explicitly excluded (rung 1: the Rollback section's "each phase is one commit on `feature/build-promotion-path`; `git revert` it"). Committed by explicit pathspec; no `git add -A`.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded by phase 1 of this same set three blocks above, and by all of the ROSTER_PROMOTION_PIPELINE and FUNDAMENTAL_PANEL_COVERAGE swarms in this same file). A cross-file block move is the one edit that reliably loses a peer's concurrent append, and peers are appending to this file.
    - Completion: no `**Commit**` field (rung 6: the same precedent). This file is committed inside the phase's own commit, so a field naming that sha cannot exist in it; the sha is reported to the caller instead.
    - Landing: not attempted, and `next_command` is empty. `swarm.py find --plan BUILD_PROMOTION_PATH_PLAN.md` returns `swarm: true` with coordinator `orch-build-promotion-path`, so per `analyze-orchestrator` Step 5 both the merge and the dispatch of the next phase belong to that coordinator.
- [x] **P1-ENG-YJDW** Phase 4: `lab test`: one counted look, recorded and final
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns the test-window runner appended to `lab/runner.py` (`Tested`, `resolve_candidate`, `preflight_test`, `test_trial_row`, `run_test` — nothing above `:253` changes), the `lab test <candidate>` subcommand, the `promoted → test-passed|test-failed` transition, the printed hand-off to `commands/promote.py` on a pass, `tests/labkit.py`'s test-window fixtures, and the whole `## Promotion` section of `.claude/skills/explore-and-experiment-new-method/SKILL.md` (which must document `lab promote` as well as `lab test`). Leaves `backtest/dev.py` (phase 1), `research.py` and `commands/research_store.py` (phase 2), `lab/prereg.py` and the `promote` subcommand (phase 3), `lab/store.py`, `record_promotion`, the eligibility gate, `lab/lab.sqlite` and `web/data/lab.json` alone. Exit: `lab test` refuses a candidate with no committed prereg, a drifted digest, a method that is not `promoted`, no dev trial, and a second look (proven against the database with raw SQL); refuses a dev store by name before anything runs; records one `trials` row with `window='test'` that does not increment the lab's dev N (`dev_trial_count` and `dev_daily_sharpes` byte-identical); DSR recorded and never in `failed`; sets final `test-passed`/`test-failed`; on a pass prints a ready-to-run `promote` command; `SKILL.md` names both subcommands; `lab status` and the web snapshot report `test-window looks used: 1` after a simulated look in a temp database and 0 in the real one.
  - **Status**: completed
  - **Plan Set**: `BUILD_PROMOTION_PATH_PLAN.md` (phase 4 of 4)
  - **Satisfies**: R2 — `lab test <candidate>`: refuses without a committed pre-registration, runs once, records a `test` trial, sets `test-passed`/`test-failed`
  - **Depends on**: P1-ENG-8OLO, P1-ENG-AZ81
  - **Plan**: `.workflows/plan/P1-ENG-YJDW.md`
  - **Completed**: 2026-10-06 13:41
  - **Method**: /do
  - **Files**: engine/src/seer_engine/lab/runner.py, engine/src/seer_engine/commands/lab.py, engine/tests/labkit.py, engine/tests/test_lab_test_window.py (new), .claude/skills/explore-and-experiment-new-method/SKILL.md
  - **Verified**: `ruff check src/seer_engine tests` clean; `import seer_engine.lab.runner, seer_engine.commands.lab` ok. `pytest tests/test_lab_test_window.py -q` **17 passed** (the plan's ~16 plus an added refusal-5 test). Neighbour suites `test_lab_runner.py test_lab_store.py test_lab_snapshot.py test_lab_methods.py test_backtest_dev.py test_research_store.py test_fundamentals_coverage.py test_lab_prereg.py` — **271 passed**. Whole engine suite with `PG_TEST_URL` set: **2829 passed**, 0 failed, 0 skipped, 291s. Manual: `lab status` prints `test-window looks used: 0` against the real lab (no look spent); `git status --porcelain lab/lab.sqlite web/data/lab.json engine/.research-test` prints nothing; `lab test --help` lists the subcommand and `lab test M0007-N20 --dry-run` exits 2 with "M0007 is 'rejected'; only a 'promoted' method reaches the test window". `git diff --stat` is **empty** for `engine/tests/test_fundamentals_coverage.py`, `engine/tests/test_research_store.py`, `fundamentals/coverage.py`, `backtest/dev.py`, `research.py`, `lab/prereg.py` and `lab/store.py` — the three `DEV_END` pins pass unedited and no other phase's file was touched. Plan invariants 1-7 all hold; the phase is purely additive.
  - **Drift**:
    - This worktree has no `engine/.venv`, so verification ran on the main checkout's interpreter (`/home/miftah/seer/engine/.venv/bin/python`) with `PYTHONPATH=<worktree>/engine/src`, verified to shadow the editable install (`seer_engine` resolves into the worktree). Same workaround phases 2 and 3 recorded.
    - The plan's Verification example `lab test M0007-RESID --dry-run` uses an illustrative variant id M0007 does not have, so it exits 2 via `resolve_candidate`'s "no variant" refusal rather than the status refusal the plan names. Re-run with a real variant, `lab test M0007-N20 --dry-run`, which exits 2 with "M0007 is 'rejected'; only a 'promoted' method reaches the test window" — the live proof the plan wanted.
  - **Decided**:
    - Where to run verification, given no `engine/.venv` in this worktree -> the main checkout's interpreter with `PYTHONPATH` into the worktree's `src` (rung 6: the direct precedent recorded by phases 2 and 3 of this same set).
    - The plan's `pre: "prereg.Prereg | None"` string annotations with a function-local `prereg` import tripped ruff F821 -> added a `TYPE_CHECKING` guard importing `seer_engine.lab.prereg` for typing only, keeping the runtime import function-local exactly as the plan wrote it (rung 2: the phase's exit criteria require a ruff-green tree, and the plan's own rationale keeps `prereg` out of module scope to avoid pulling git and the docs tree into `import runner`). The codebase already uses this idiom at `strategies/allocator.py:49`.
    - `test_a_second_look_is_refused_after_a_real_run` as the plan wrote it asserted "already had its look" after a real run, but `run_test` moves the method to `test-failed` first, so `preflight_test`'s refusal 1 (status) fires before refusal 5 (second look) — the plan's own documented order. Fixed the TEST, not the refusal order (rung 3: both the status move and the 1..5 ordering are the plan's quoted code; the assertion is one line written against an ordering that code contradicts). The test now asserts the status refusal after a real run, and a NEW test `test_a_recorded_look_is_refused_even_while_the_method_is_still_promoted` reaches refusal 5 on its own by recording a test trial against a method still at `promoted`. No check was relaxed; the raw-SQL database proof of the second-look refusal passes unchanged.
    - Landing: not attempted, and `next_command` is empty. `swarm.py find --plan BUILD_PROMOTION_PATH_PLAN.md --task P1-ENG-YJDW` returns `swarm: true` with coordinator `orch-build-promotion-path`, so per `analyze-orchestrator` Step 5 the merge of `feature/build-promotion-path` into `main` belongs to that coordinator, not to this session.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded by phases 1 and 3 of this same set, and by the ROSTER_PROMOTION_PIPELINE and FUNDAMENTAL_PANEL_COVERAGE swarms in this same file). A cross-file block move is the one edit that reliably loses a peer's concurrent append.
    - Completion: no `**Commit**` field (rung 6: the same precedent). This file is committed inside the phase's own commit, so a field naming that sha cannot exist in it; the sha is reported to the caller for the swarm ledger instead.
- [x] **P1-ENG-FNKE** Phase 1: The N policy and the effective-N estimator
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns a new pure module `engine/src/seer_engine/lab/npolicy.py`: the named policies (`all-trials`, `methods`, `effective`), the participation-ratio estimator computed from the month-end curves already in `trials.curve_json`, `effective_n(conn, policy) -> NCount` carrying both the number used and the evidence behind it, and `NCount.basis` — the one-line evidence string phase 7 commits into every pre-registration and into `web/data/lab.json`. Tests. Exit: `npolicy.effective_n` returns 110 under `all-trials`, 23 under `methods` and ~2 under `effective` on the committed database; `all-trials` returns 0 on an empty lab and is not floored; `DEFAULT_POLICY == "all-trials"`; `NCount.basis` is a non-empty single line for every policy on every lab; the `methods` policy is floored at the measured participation ratio; pytest green.
  - **Status**: completed
  - **Plan Set**: `LAB_LUCK_GATE_PLAN.md` (phase 1 of 9)
  - **Satisfies**: R1 — The gate admits nothing at 110 trials and the bar rises with every exploration regardless of merit — 110 correlated variant rows deflated as 110 independent trials.
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-FNKE.md`
  - **Completed**: 2026-10-07 10:53
  - **Method**: /do
  - **Files**: engine/src/seer_engine/lab/npolicy.py, engine/tests/test_lab_npolicy.py, engine/.workflows/plan/P1-ENG-FNKE.md
  - **Verified**: `pytest tests/test_lab_npolicy.py` -> 13 passed (serial, `-o addopts="-ra"`); full engine suite in an isolated HEAD worktree carrying only this phase's two new files -> 2675 passed / 382 skipped / 0 failed; `ruff check --select E9,F --ignore F401` -> All checks passed. Manual check against the committed `lab/lab.sqlite` reproduced the plan's expected output byte-for-byte: N = 110 (`all-trials`) / 23 (`methods`) / 2 (`effective`), participation ratio 2.44, mean pairwise correlation 0.595 over 102 common month-ends. Invariant 2 held: `store.test_looks()` = 0. `lab/lab.sqlite`, `engine/pyproject.toml` and `web/data/lab.json` untouched. `grep -rn npolicy engine/src engine/tests` finds no caller outside the module and its own test -- by design; phase 4 wires the gate.
  - **Drift**:
    - Plan cites `engine/pyproject.toml:10` for the `numpy>=2` dependency; it is actually line 13. Verify-only step, no edit made, content as the plan quotes it.
    - The plan's Verification prose says `Expected: 14 passed`; its Step 2 code block defines 13 test functions. The code block is authoritative (rung 3) -- 13 passed, no skips.
    - `pytest-xdist` is not installed in `/home/miftah/seer/engine/.venv`, but `engine/pyproject.toml` sets `addopts = "-ra -n auto"`, so the plan's verification command errors with `unrecognized arguments: -n`. Ran with `-o addopts="-ra"` (serial) instead of installing into the venv three peer sessions are using. Every test still ran.
    - The full suite cannot be run in the shared worktree right now: phase 8's in-flight `dev.FAILURE_LABELS[1]` change (D13) makes `tests/test_backtest_dev_report.py` fail collection on the literal `max DD <= 15%`. That is phase 8's work mid-flight, not phase 1's. Invariant 1 was verified instead in a throwaway worktree cut from HEAD carrying only phase 1's two new files: 2675 passed, 382 skipped, 0 failed. That worktree has been removed.
    - `engine/.workflows/todos.md` is modified by three concurrent sessions (phases 1, 2 and 6 each appended a task entry). Deliberately left out of the commit allowlist.
  - **Decided**:
    - Step 3 says create every phase's task; created only phase 1's (P1-ENG-FNKE) (tie-break: narrower blast radius -- phases 1, 2, 6 and 8 are spawned concurrently and all land in `engine/.workflows/todos.md`).
    - `pytest-xdist` missing: ran serially with `-o addopts="-ra"` rather than pip-installing into the shared venv (tie-break: narrower blast radius / reversible option).
    - Full-suite verification done in an isolated HEAD worktree rather than the shared one, because peers' in-flight edits break collection (rung 1: invariant 1 requires pytest green for THIS phase's change; a peer's half-written file is not phase 1's failure).
    - Commit allowlist excludes `engine/.workflows/todos.md`; the adopted plan copy `P1-ENG-FNKE.md` replaces the plan's already-committed, unmodified `.workflows/plan/lab-luck-gate/phase-1.md` (rung 3: the phase plan's commit-allowlist block).
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded by the BUILD_PROMOTION_PATH, ROSTER_PROMOTION_PIPELINE and FUNDAMENTAL_PANEL_COVERAGE swarms in this same file). A cross-file block move is the one edit that reliably loses a peer's concurrent append.
    - Completion: no `**Commit**` field (rung 6: the same precedent). This file is committed by whichever session commits it later, not by this phase, so a field naming this phase's sha cannot be consistent; the sha is reported to the caller for the swarm ledger instead.
    - Quick Stats recounted from the file rather than blind-decremented (the header read `P1 High: 1 / Completed: 81` against 8 open P1 blocks and 83 `[x]` blocks -- three concurrent sessions had already lost each other's increments). A recount is idempotent and converges under concurrency; a decrement compounds the race.
- [x] **P1-ENG-CA69** Phase 6: Every roster entry carries its lab provenance
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns making the lab/roster divergence explicit and checked rather than silent — a `lab_provenance` field on the roster entry (lab method and candidate id, lab status at admission, admission basis `test-passed`/`owner-override` with its reason), outside the spec digest like `gate_note`; `store.record_promotion` writing the same fact onto the method; a test asserting every roster entry whose id names a lab candidate has provenance matching `lab.sqlite`. Exit: RM-FR and RMW-FR carry `owner-override` provenance naming M0011/M0022 and the `rejected` status they were admitted under; the roster digest test still passes unchanged; pytest green.
  - **Status**: completed
  - **Plan Set**: `LAB_LUCK_GATE_PLAN.md` (phase 6 of 9)
  - **Satisfies**: R4 — The lab verdict and the paper roster have diverged silently — RM and RMW trade while both read `rejected`.
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-CA69.md`
  - **Completed**: 2026-10-07 11:01
  - **Method**: /do
  - **Files**: engine/src/seer_engine/paper/roster.py, engine/src/seer_engine/lab/store.py, engine/src/seer_engine/commands/promote.py, engine/tests/test_paper_roster.py, engine/tests/test_lab_store.py, engine/tests/test_promote_command.py, engine/tests/test_paper_split_cadence.py, engine/.workflows/todos.md, engine/.workflows/plan/P1-ENG-CA69.md
  - **Drift**:
    - test_paper_split_cadence.py is a THIRD `promote` call site the plan did not know about -- its Step 8 Impact note names "exactly one production caller and two test call sites". It landed in 06d12ea (the paper-split-cadence set) after the analysis was taken, hand-builds an argparse.Namespace with no `lab_override_reason`, and promotes a `rejected` M0022, so the new refusal fired and the test failed. Fixed exactly as Steps 11/12 fix the two known call sites. Seventh file; the plan said six.
    - The `lab` fixture in test_promote_command.py ends at status `rejected`, not `idea` as Step 12's prose claims (it calls update_method to `rejected` right after add_method). Still an owner-override either way, so the refusal test is unaffected; the printed-provenance assertion was written as lab_status='rejected' to match the fixture that actually exists.
    - Every store.py line number in the phase plan was pre-phase-2 and had already moved (phase 2 is live in this worktree). Anchored on quoted text throughout, as the shared-file protocol's rule 2 requires -- the PROMOTION_MARKER block and record_promotion were the anchors.
    - The repo's pytest addopts is `-ra -n auto` but pytest-xdist is not installed in the only venv on this machine (/home/miftah/seer/engine/.venv). Pre-existing environment gap, unrelated to this phase; ran the identical tests serially with `-o addopts=-ra`.
    - Four tests fail in the shared worktree and belong to peers still running, not to this phase: test_backtest_tuning.py::test_select_fallback_is_used_only_when_nothing_qualifies and test_backtest_walkforward.py::test_select_fold_falls_back_when_nothing_qualifies (phase 8's MAX_DRAWDOWN 0.15->0.20 changing which grid row qualifies), and both test_lab_snapshot.py failures (phase 2's trial_moments migration / snapshot export). None touch any file in this phase's allowlist.
  - **Decided**:
    - Step 3 said create tasks for all 9 phases; created only phase 6's -> rung 6 (surrounding convention) plus the narrower-blast-radius tie-break: phases 1, 2 and 8 run concurrently in this shared worktree and each would otherwise write all nine entries into the same todos.md and the same TaskID column -- four writers, 36 duplicate rows.
    - Plan Step 12 asserts lab_status='idea' in the printed LAB_PROVENANCE line; wrote 'rejected' -> rung 3 (the code block's intent is that the printed provenance names the fixture's actual lab status), read against the fixture on disk, which ends at 'rejected'.
    - test_paper_split_cadence.py's promote Namespace gained lab_override_reason -> rung 2 (the phase's exit criterion "pytest green in engine/") and rung 3 (Steps 11 and 12 do exactly this at every other call site). Weakening the new refusal was ruled out: a failing verification is never settled by relaxing the check.
    - Ran pytest serially by overriding addopts, since pytest-xdist is absent -> not a relaxation; the identical tests run, only not in parallel.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded by phase 1 of this same set, and by the BUILD_PROMOTION_PATH / ROSTER_PROMOTION_PIPELINE / FUNDAMENTAL_PANEL_COVERAGE swarms in this file). A cross-file block move is the one edit that reliably loses a peer's concurrent append.
    - Completion: no `**Commit**` field, and `LAB_LUCK_GATE_PLAN.md` left untouched (rung 6: phase 1's precedent; rung 3: the set is a swarm whose coordinator `orch-lab-luck-gate` owns the ledger at .workflows/orchestration/lab-luck-gate/ledger.json). The index's phase table has no tick column and eight peers hold it open; the sha goes to the coordinator instead.
    - Quick Stats recounted from the file rather than blind-decremented (recount is idempotent under concurrency; a decrement compounds the race).
- [x] **P1-ENG-6134** Phase 2: Record the DSR's inputs with every dev trial
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns an additive, append-only `trial_moments` side table (`trial_n`, `sr_daily`, `t`, `skew`, `kurt`, `var_trials`, `n_at_run`, `measured`) in `store.py`'s schema and `_migrate`, its writer, and `runner.trial_rows` populating it in the same transaction as the trial it describes — it owns the whole body of `trial_rows`, with phase 4 applying a two-line delta to it and nothing else; it does not touch the `trials` table's columns, triggers or contents, nor the eligibility decision, which still reads exactly as it does today. Exit: a new `lab run` writes one `trial_moments` row per dev trial; the committed database migrates in place without touching any `trials` row; `test_looks` still 0; `pytest` green.
  - **Status**: completed
  - **Plan Set**: `LAB_LUCK_GATE_PLAN.md` (phase 2 of 9)
  - **Satisfies**: R2 — A trial's verdict is frozen at the N of its run date, so verdicts are not comparable across time and a method can never be re-judged.
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-6134.md`
  - **Completed**: 2026-10-07 11:11
  - **Method**: /do
  - **Files**: engine/src/seer_engine/lab/runner.py, engine/tests/test_lab_runner.py, engine/tests/test_lab_snapshot.py, engine/.workflows/plan/P1-ENG-6134.md (store.py and test_lab_store.py landed with phase 6's `11b802a` under the reconciled shared-file protocol rule 3)
  - **Verified**: build ok — `store.SCHEMA_VERSION` = 3 and `store.MOMENTS_COLUMNS` = `('trial_n','sr_daily','t','skew','kurt','var_trials','n_at_run','measured')`, exactly the plan's contract. Targeted lab suites (test_lab_store, test_lab_snapshot, test_lab_runner, test_lab_prereg, test_lab_test_window, test_lab_methods) with `PG_TEST_URL`: 224 passed, 0 failed. Full engine suite with `PG_TEST_URL`: **3076 passed, 0 failed, 0 skipped** (413s) — the shared tree is green carrying phases 1 and 6 landed plus 8 in flight. Phase 2 in isolation (throwaway copy of HEAD carrying only phase 2's files): 2670 passed, its single failure a harness artefact because the shared `test_lab_snapshot.py` carries phase 8's `maxDrawdown: 0.20` expectation into a tree with HEAD's 0.15 source. Migration run on a COPY of the committed `lab/lab.sqlite` (never the committed binary): 110 trials, sha256 `6bfc3a9e952987d72842e07b489b72563e017905b579966855ce9a56062f7507` **identical before and after**; `schema_version` 2 → 3; `trial_moments` empty; `test_looks` 0; table plus `trial_moments_no_update` and `trial_moments_no_delete` present; `PRAGMA foreign_key_check` clean. `git status --porcelain lab/lab.sqlite` EMPTY — invariant 6 held, phase 4 keeps the single commit that writes the migrated binary.
  - **Drift**: No code drift — every anchor `phase-2.md` quotes was present verbatim in `store.py` and `runner.py`, and `runner._dsr` was exactly the computation the plan hoists, so the verdict is provably unchanged.
    - Environment: the main venv has no `pytest-xdist` but `engine/pyproject.toml` sets `addopts='-ra -n auto'`, so a bare `pytest` cannot start. Ran every suite with `-o addopts="-ra"`. Pre-existing repo condition, confirmed independently by the coordinator; nothing installed into the shared venv.
    - Plan defect found and repaired in Step 8e: the new v2→v3 migration test asserted the append-only triggers fire on the EMPTY `trial_moments` table, but SQLite BEFORE UPDATE/DELETE triggers are row-level and never fire with zero rows, so the assertion could not pass. The test now inserts one moments row into the migrated table first, then asserts both triggers abort — strengthening the check rather than relaxing it, since it now proves a table arriving by MIGRATION is as append-only as one created by `_SCHEMA`.
  - **Decided**:
    - Step 3 said create tasks for all 9 phases → created phase 2's task only (rung 6, surrounding convention plus the narrower blast radius): W1 phases 1/2/6/8 run Step 3 concurrently in one shared worktree, so each creating all nine would write duplicate cards. Peers independently did the same (P1-ENG-FNKE, P1-ENG-CA69).
    - Verification runner could not start → override `addopts` to `-ra`, serial (rung 6): `-n auto` is a parallelism flag, not an assertion, so the identical test set runs.
    - Plan's Step 8e trigger assertions were vacuous on an empty table → give the migrated table a row before asserting (rung 2, exit criterion 1 "a fresh database has `trial_moments` with both append-only triggers", plus the never-relax-a-check rule). Strengthens the test.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the recorded precedent of phases 1 and 6 of this same set, and of the BUILD_PROMOTION_PATH / ROSTER_PROMOTION_PIPELINE / FUNDAMENTAL_PANEL_COVERAGE swarms in this file). A cross-file block move is the one edit that reliably loses a peer's concurrent append.
    - Completion: no `**Commit**` field, and `LAB_LUCK_GATE_PLAN.md` left untouched (rung 6: phases 1 and 6's precedent; rung 3: the set is a swarm whose coordinator `orch-lab-luck-gate` owns the ledger at `.workflows/orchestration/lab-luck-gate/ledger.json`). The index's phase table has no tick column and seven peers hold it open; the sha goes to the coordinator instead. No peer phase's task was unblocked or altered — phase 3 (`P1-ENG-921N`) stays `blocked`; the coordinator releases it.
    - Quick Stats recounted from the file rather than blind-decremented (recount is idempotent under concurrency; a decrement compounds the race).
- [x] **P1-ENG-921N** Phase 3: `lab remeasure` — recover the inputs for a recorded method
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `lab remeasure <method>` in `commands/lab.py` and the new `lab/remeasure.py` module: re-runs *only* the dev window for a method whose trials predate phase 2, writes `trial_moments` rows and nothing else, and is idempotent; refuses any method with a test trial and refuses the test window by name. Does not touch `trials`, `methods.status`, the prereg files or the test-window store. Exit: `lab remeasure M0022` populates three `trial_moments` rows whose recomputed DSR reproduces each recorded `dsr` to within 1e-6 at the recorded `n_trials_at_run`; running it twice changes nothing; `pytest` green.
  - **Status**: completed
  - **Plan Set**: `LAB_LUCK_GATE_PLAN.md` (phase 3 of 9)
  - **Satisfies**: R2 — A trial's verdict is frozen at the N of its run date, so verdicts are not comparable across time and a method can never be re-judged.
  - **Depends on**: P1-ENG-6134
  - **Plan**: `.workflows/plan/P1-ENG-921N.md`
  - **Completed**: 2026-10-07 11:36
  - **Method**: /do
  - **Files**: engine/src/seer_engine/lab/remeasure.py, engine/src/seer_engine/commands/lab.py, engine/tests/test_lab_remeasure.py, engine/.workflows/plan/P1-ENG-921N.md, engine/.workflows/todos.md
  - **Verified**: all five exit criteria measured, not estimated. (1) `lab remeasure M0022` against a COPY of the committed database (`SEER_LAB_DB`, per D5 — the committed `lab/lab.sqlite` was never opened for writing) and the real 270MB dev research store wrote exactly three `trial_moments` rows — #108 M0022-W-TV14, #109 M0022-W-TV16, #110 M0022-W-TV14-SW — each reproducing its recorded DSR (0.912210222337 / 0.915623353658 / 0.764668011634) at the recorded N=110 with the reconstructed `var_trials` = 2.395048e-04; **every delta exactly 0.000e+00**, bit-identical rather than merely inside the mandated 1e-6, and the recorded annualized Sharpes reproduced bit-identically too. (2) A second run loaded no research store, wrote nothing and named the three trials it skipped — idempotent. (3) `lab remeasure H-P7A-F1` and `lab remeasure M9999` both exit 2; the test-trial and no-dev-trial refusals are covered by unit tests. (4) Invariants hold on the remeasured copy: the `trials` digest over (n, method_id, candidate_id, window, sharpe, dsr, eligible, failed, n_trials_at_run) identical before and after across all 110 rows (`dcd884b7c6f08a2f`), the `methods` digest identical across all 37 rows (`581de1c38996cff3`), `test_looks` = 0, `dev_trial_count` = 110, M0022 still `rejected`. (5) Full engine suite green: **3089 passed, 0 failed** (`pytest -q -o addopts="-ra"` with `PG_TEST_URL` set). Targeted group `test_lab_remeasure.py test_lab_runner.py test_lab_store.py test_lab_test_window.py`: 68 passed; the new file contributes 13 tests.
  - **Drift**:
    - No drift. Every symbol phase 2 was contracted to provide exists with the assumed shape (`store.MomentsRow` with its 8th no-default `measured: str` field — reconciliation conflict 4 — `store.insert_moments` called by attribute in `runner.py` so the test fixture can monkeypatch it, `store.moments_of`). All four `commands/lab.py` anchors matched the plan's quoted text exactly and all four edits were pure insertions, per the shared-file protocol (conflict 6/11).
    - Verification environment: `pytest-xdist` is absent from the shared venv while `engine/pyproject.toml` sets `addopts = "-ra -n auto"`, so every suite ran with `-o addopts="-ra"` (serial). Pre-existing repo condition recorded independently by phases 1, 2 and 6; nothing was installed into the shared venv. `PG_TEST_URL` was set, which takes ~21 tests out of skip.
    - Because phase 4's unfinished work is sitting uncommitted in this shared tree, the whole suite was re-run a second time against a pristine `git archive HEAD` extraction carrying ONLY this phase's three files, to prove the green is this phase's and not a peer's WIP propping it up: 3088 passed with a single failure, `test_lab_prereg.py::test_lab_promote_command_exits_2_when_the_lab_refuses`, which shells out to `git rev-parse HEAD` and therefore cannot pass inside a non-git /tmp extraction. It reproduces identically on bare HEAD with zero phase-3 files present — an artifact of the isolation harness, not a defect and not this phase's.
  - **Decided**:
    - The plan's code blocks embed two `NOTE TO THE IMPLEMENTER` paragraphs inside shipped docstrings (`remeasure.resolve_method` and `remeasure._moments_row`) → stripped them from the delivered code (rung 3, the plan set's code blocks): phase 9 quotes both docstrings as the left side of its diff WITHOUT those paragraphs, so shipping them verbatim would break the dependent phase's diff. Every other line of both code blocks is verbatim.
    - Reconstructing a historical run's `var_trials`, which was never recorded: `trials.n` is a monotone AUTOINCREMENT and `run_method` writes a whole batch inside one `BEGIN IMMEDIATE`, so a batch's trial numbers are contiguous and "every dev trial that existed then" is exactly "every dev row with a lower n" — rebuilt from the append-only `sharpe` column and cross-checked against the recorded `n_trials_at_run` before anything is reconstructed. The cross-check refuses rather than guesses if the two disagree.
    - Landing: not attempted, and `next_command` is empty. `swarm.py find --plan LAB_LUCK_GATE_PLAN.md --task P1-ENG-921N` returns `swarm: true` with coordinator `orch-lab-luck-gate`, so per `analyze-orchestrator` Step 5 the merge of `feature/lab-luck-gate` into `main` belongs to that coordinator, not to this session. Nothing merged, pushed to main, or deleted.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks` (rung 6: the direct precedent recorded by phases 1, 2 and 6 of this same set, and by the BUILD_PROMOTION_PATH / ROSTER_PROMOTION_PIPELINE / FUNDAMENTAL_PANEL_COVERAGE swarms in this same file). A cross-file block move is the one edit that reliably loses a peer's concurrent append.
    - Completion: no `**Commit**` field, and `LAB_LUCK_GATE_PLAN.md` left untouched (rung 6: phases 1, 2 and 6's precedent; rung 3: the set is a swarm whose coordinator owns the ledger at `.workflows/orchestration/lab-luck-gate/ledger.json`). The index's phase table has no tick column — its TaskID and Card columns are `—` for all nine rows — and six peers hold it open; the sha goes to the coordinator instead.
    - No peer phase's task was unblocked or altered: phase 9 (`P1-ENG-ALY2`) stays `blocked` and the coordinator releases it; phase 4 (`P1-ENG-B6Y5`) is in flight in a peer session. `next_task_id` was deliberately empty.
    - Quick Stats recounted from the file rather than blind-decremented (recount is idempotent under concurrency; a decrement compounds the race).
- [x] **P1-ENG-B6Y5** Phase 4: The verdict is derived under one policy, at the current N
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns the gate change: `store.DSR_MIN` 0.95 → 0.90 (sole owner), `store.DSR_POLICY = "all-trials"` as the single constant deciding N, and `store.verdict(conn, trial)` deciding every condition at evaluation time — the four threshold owner conditions re-derived from the trial's recorded columns against the live constants, `owner inputs` carried from the record, and the luck test decided on the trial's DSR at the gate's current N (`store.dsr_at`, exact from `trial_moments` or recovered by `store.recover_dsr`). Also owns the shared label/arithmetic helpers (`LUCK_LABEL_PREFIX`, `is_luck_label`, `recorded_labels`, `OWNER_INPUTS_LABEL`, `owner_failures`, `sr_star`, `recover_dsr`, `dev_sharpe_variance`, `dsr_at`), `best_dev_eligible`, the twice-guarded `("rejected", "dev-eligible")` transition, `runner.trial_rows`'s two-line delta, `lab reevaluate`, and the additive idempotent migration of the committed `lab/lab.sqlite` plus its re-export of `web/data/lab.json`. `dsr_at` deflates by today's `dev_sharpe_variance` on BOTH routes (D12). Exit: at (N=110, DSR >= 0.90, max DD <= 20%) exactly three trials are eligible — M0022-W-TV14, M0022-W-TV16, M0020-W-NOSTOP — with M0007-N20-RAW explicitly not eligible (0.8985 at N=110) and M0011 still out; a trial whose DSR cannot be evaluated fails the luck test; `DSR_POLICY="all-trials"`, `DSR_MIN=0.95` and `MAX_DRAWDOWN=0.15` together reproduce `main`'s verdicts exactly; all 110 recorded `dsr`/`eligible`/`failed`/`n_trials_at_run` columns byte-identical before and after; `test_looks` 0; `pytest` green.
  - **Status**: completed
  - **Plan Set**: `LAB_LUCK_GATE_PLAN.md` (phase 4 of 9)
  - **Satisfies**: R1 — The gate admits nothing at 110 trials and the bar rises with every exploration regardless of merit — 110 correlated variant rows deflated as 110 independent trials; R2 — A trial's verdict is frozen at the N of its run date, so verdicts are not comparable across time and a method can never be re-judged.
  - **Depends on**: P1-ENG-FNKE, P1-ENG-6134, P1-ENG-EH4K
  - **Plan**: `.workflows/plan/P1-ENG-B6Y5.md`
  - **Completed**: 2026-10-07 13:42
  - **Method**: /do
  - **Files**: engine/src/seer_engine/lab/store.py, engine/src/seer_engine/lab/runner.py, engine/src/seer_engine/commands/lab.py, engine/tests/test_lab_store.py, engine/tests/test_lab_gate_policy.py, engine/tests/test_lab_prereg.py, engine/tests/test_lab_snapshot.py, engine/.workflows/plan/P1-ENG-B6Y5.md, lab/lab.sqlite, web/data/lab.json, engine/.workflows/todos.md
  - **Verified**: full engine suite with `PYTHONPATH=src`, `PG_TEST_URL` set and `-o addopts="-ra"` (serial; `pytest-xdist` absent from the shared venv) -> **3122 passed, 0 failed**, 153 warnings in 327s. Gate moved and still discriminates: import check prints `0.9 DSR >= 0.90 all-trials True`. Committed `lab/lab.sqlite` after migration: `schema_version` 3, 110 trials, `trial_moments` 0, test-window looks 0, M0020 and M0022 both `dev-eligible`. Recorded-column digest over all 110 trials `166ae36bdc4425cebd7380b0187f9c21dc7726d502fe999bd7746e60bc974016` -- byte-identical to the plan's constant, so no recorded `dsr`/`eligible`/`failed`/`n_trials_at_run` changed. Migration idempotent: two consecutive `lab reevaluate` runs give identical `sqlite3 .dump` sha256. `web/data/lab.json` regenerated with `lab export-json` (not `lab stage`, which would `git add` in a shared worktree): `gate.dsrMin` 0.90, `gate.maxDrawdown` 0.20, `summary.byStatus` rejected 24 / dev-eligible 2. No reader compares the luck label by equality (`grep -rn 'DSR_LABEL' engine/src | grep -E '==|!=|\bin \b' | grep -v is_luck_label` returns only comments and f-string writes). `lab status` renders; M0022-W-TV14 and M0022-W-TV16 both show `misses 0`. `lab promote M0022` on a copy pre-registers M0022-W-TV14, MAR 0.856651, DSR 0.912210 at N = 110 -- **the promotion path is reachable for the first time** -- with `git status docs/lab/prereg/` clean.
  - **Drift**:
    - The plan's Step 8 claimed no other existing test breaks; the full suite showed 18 failures. 15 in `test_lab_prereg.py` and 1 in `test_lab_store.py` were fixture decay from the derived verdict (a fixture lab whose dev trials share one Sharpe has zero trial-Sharpe variance, so under D12 no DSR is evaluable and nothing is eligible; and rows meant to be ineligible relied on a recorded `failed` string that phase 4 deliberately stops reading). Repaired by moving the fixtures clear of the bar -- distinct Sharpes, a `_ballast` second dev trial, and ineligible rows made ineligible in their NUMBERS (`max_drawdown` 0.245, `profit_factor` 1.1). No assertion was weakened and no production code was changed to accommodate a fixture. `test_lab_prereg.py` and `test_lab_snapshot.py` were therefore added to the phase's file list (the plan listed 7 files; this is 7 + 2 test files + the adopted plan copy).
    - `test_lab_snapshot.py`'s gate dict needed `dsrMin` 0.95 -> 0.90 (its `maxDrawdown` already read 0.20 from phase 8), as the coordinator's brief predicted.
    - The plan's manual check 2 (`lab promote M0022`) run against the committed database MOVES M0022 to `promoted`, which is forward-only and irreversible. It was run as written, caught, and undone: `lab/lab.sqlite` was restored from HEAD (md5 `bd038a7005dc6ebb231cec2496c76cd2`, the coordinator's baseline), the migration redone, and the promote smoke re-run against a copy via `SEER_LAB_DB`. The committed database holds M0020 and M0022 at `dev-eligible`, not `promoted`.
    - `commands/lab.py`: phase 3 landed `998e67f` (its four `remeasure` insertions) mid-phase, so this commit's diff of that file carries only phase 4's five hunks. Verified: zero `remeasure` additions in the diff.
  - **Decided**:
    - The phase plan's `test_m0011_stays_rejected_so_rm_and_rmw_diverge_on_purpose` asserted `v.derived is False` and `v.n == 90` -> replaced with `derived is True`, `v.n == 110`, `dsr ~= 0.884` (rung 1 and 3: those assertions were the superseded "return the row verbatim at another N" draft, contradicting the same plan's Step 3 code block, Decision D11 and the index's R2; the invariant and the code blocks win over stale prose). The test now pins the re-evaluated figure the index itself quotes.
    - 18 existing tests broke on fixture decay from `DSR_MIN` 0.95->0.90 plus the derived verdict -> fixtures moved clear of the bar, never an assertion relaxed (rung 3, plus the plan's own rule that a failing verification is never settled by relaxing the check). A one-dev-trial fixture lab has no evaluable DSR by design -- `runner.trial_rows` has always recorded `dsr=None` for a lab's first trial -- so a fixture wanting a promotable method must look like a lab that could have one.
    - `test_the_two_moved_bars_unblock_exactly_m0022_and_m0020` asserted a `rejected`->`dev-eligible` move against the very database this phase migrates (Decision D5, Step 10), so it could only pass once -> the move assertion is now relative to the starting status while the three-eligible-trials assertion stays unconditional (rung 2: the phase's exit criteria are about which trials are eligible, which is where R1 and R5 live).
    - Landing: not attempted, and `next_command` is empty. `swarm.py find --plan LAB_LUCK_GATE_PLAN.md --task P1-ENG-B6Y5` returns `swarm: true` with coordinator `orch-lab-luck-gate`, so per `analyze-orchestrator` Step 5 the merge of `feature/lab-luck-gate` into `main` belongs to that coordinator, not to this session. Nothing merged, pushed to main, or deleted.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks`, no `**Commit**` field, and `LAB_LUCK_GATE_PLAN.md` left untouched (rung 6: the direct precedent recorded by phases 1, 2, 3, 6 and 8 of this same set in this same file). A cross-file block move is the one edit that reliably loses a peer's concurrent append, and the index's phase table has no tick column -- its TaskID and Card columns are `--` for all nine rows -- with six peers holding it open. The sha goes to the coordinator instead.
    - Phase 5 (`P1-ENG-QM5I`, which depends on this phase) left at `blocked` and `next_command` left empty rather than dispatched: in a swarm the coordinator releases the dependent phase off its ledger (`impl-lab-luck-gate-p5` is already a named peer), so printing `/do P1-ENG-QM5I` for a human would start a duplicate session on the same branch. Same for phase 9 (`P1-ENG-ALY2`).
- [x] **P1-ENG-QM5I** Phase 5: `lab status` shows the queue and the look budget; `lab luck`
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `commands/lab.py`'s `_status` — the promotion path printed always, including when it is empty and with the reason it is empty; "test-window looks used: k" per design §3; a "Promotable now" section; the D1b ratchet warning — and the new read-only `lab luck`, printing the leaderboard under each policy side by side so the gate's sensitivity is inspectable without editing a constant. Does not touch the gate, the policy default or any write path; every rule it applies is phase 4's (`_owner_misses`, `_dev_var`, `sr_star`, `recover_dsr` are aliases or re-exports). Exit: `lab status` on a lab with nothing promotable prints why; after phase 4 it lists M0022 (with W-TV14) and M0020 (with W-NOSTOP); the ratchet warning names N = 143; `lab luck` reproduces the analysis document's N-sensitivity table, counting three clearing at N=110 and seven at N=23; `pytest` green.
  - **Status**: completed
  - **Plan Set**: `LAB_LUCK_GATE_PLAN.md` (phase 5 of 9)
  - **Satisfies**: R3 — The promotion path is unreachable and the test window unspent, and nothing surfaces either; R1 — The gate admits nothing at 110 trials and the bar rises with every exploration regardless of merit — 110 correlated variant rows deflated as 110 independent trials.
  - **Depends on**: P1-ENG-B6Y5
  - **Plan**: `.workflows/plan/P1-ENG-QM5I.md`
  - **Completed**: 2026-10-07 14:18
  - **Method**: /do
  - **Files**: engine/src/seer_engine/commands/lab.py, engine/tests/test_lab_luck.py, engine/tests/test_lab_status.py, engine/package_readme.md, engine/.workflows/plan/P1-ENG-QM5I.md, engine/.workflows/todos.md
  - **Verified**: full engine suite with `PYTHONPATH=src`, `PG_TEST_URL` set and `-o addopts="-ra"` (serial) -> **3186 passed, 0 failed**, 153 warnings in 495.70s; `ruff check` clean on all three files. CLI wiring: `lab._HANDLERS` carries `luck` -> `_luck`, and `sr_star(110, 2.395048e-04)` = 0.0397, the analysis document's hurdle exactly. `lab status` on the committed database prints the promotion path with every section present: the D1b ratchet warning fires on M0022-W-TV16 reading "DSR is 0.916 against a 0.9 bar -- 0.016 of margin at N = 110" and "falls below the bar at N = 143: 33 more dev trials" -- D1b's measured numbers to the digit; "Promotable now" lists M0020/M0020-W-NOSTOP and M0022/M0022-W-TV14 (MAR ranking, as the plan predicted, not W-TV16); "Dev-eligible (2)"; "Test-window looks used: 0"; the Closest-to-eligible table shows M0022-W-TV14, M0022-W-TV16 and M0020-W-NOSTOP all at `misses 0`. `lab luck --at 37 --at 23` reproduces the analysis document's N-sensitivity table to the last printed digit (M0022-W-TV16 0.965/0.978, M0022-W-TV14 0.963/0.977, M0020-W-NOSTOP 0.964/0.978, M0007-N20-RAW 0.953/0.970, M0019-RAW20-S25 0.956/0.972), variance 2.395048e-04, mean pairwise correlation 0.595, and exactly 3 clearing at the live N = 110, named M0020-W-NOSTOP, M0022-W-TV14 and M0022-W-TV16. Read-only proved by measurement: `lab/lab.sqlite` md5 `5b94f444d69e7af262b1c815e84346c9` before and after both commands, `git status --porcelain lab/lab.sqlite` empty, and `store.test_looks` reads 0.
  - **Drift**:
    - The plan's line numbers were `main`'s; phases 3 and 4 had moved them. All eight edits were applied on quoted-text anchors instead, as the plan's shared-file protocol requires. No content drift.
    - Step 7a was already half-landed: phase 4 had left the `misses()` closure delegating to `store.owner_failures`, exactly as the plan predicted. Only the tidy -- collapsing it into the module-level `_owner_misses` -- was left to do.
    - `tests/test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database` failed once mid-run and then passed: a peer (phase 7) was regenerating `web/data/lab.json` concurrently under D10. Not this phase's file; `lab/lab.sqlite` stayed byte-identical (md5 `5b94f444d69e7af262b1c815e84346c9`) across the whole phase.
    - `engine/src/seer_engine/commands/lab.py` in the WORKING TREE also carries phase 9's uncommitted `lab remeasure H-P7A` hunks (`rm.is_seed_id`, `rm.seed_preflight`, `rm.remeasure_seed`, `rm.format_seed_report`, `rm.seed_verdicts`, all backed by uncommitted edits to `lab/remeasure.py`). They are excluded from this commit: a phase-5-only build of the file was staged through the index, leaving the working tree untouched so phase 9 loses nothing.
  - **Decided**:
    - Plan exit criterion 6 said `lab luck` counts seven candidates clearing at N = 23; measured 18 -> kept the recomputing code and corrected the plan's stale comment instead (rung 1: the phase plan's own repeated invariant that nothing is a constant lifted from the analysis document -- `_eligible_at` recomputes rather than quotes). The plan's LUCK_ONLY tuple is a 7-row SAMPLE, not the pool: measured on the committed database there are 56 dev trials with a recorded DSR, 25 missing no owner condition, of which 3 clear at N = 110, 12 at N = 37 and 18 at N = 23. The number D1 actually rests on -- exactly THREE at the live N = 110, and which three -- is exact and is asserted by name.
    - `test_a_candidate_that_misses_an_owner_condition_is_named_as_unrescuable` was self-contradictory as drafted: `max_drawdown=0.11` passes the live 20% bar, so the row missed nothing, yet the test asserted a "max DD" miss -> set `max_drawdown=0.31` so it genuinely misses, and asserted the prefix `max DD <= ` rather than the frozen `15%` (rung 3, plus Decision D13: the label follows the constant and is prefix-stable).
    - Fixture decay, as the coordinator warned: several fixtures' second dev trial shared the default `sharpe=0.9`, giving zero trial-Sharpe variance, so no DSR is evaluable and nothing is eligible -> gave them distinct Sharpes and, where needed, a genuine owner-condition miss in the NUMBERS (phase 4's precedent). No assertion was weakened and no production code was changed to suit a fixture.
    - `test_lab_luck_recorded_column_reproduces_the_database` scanned every output line beginning with a candidate id, which also matched the one-field "candidates clearing the bar" line in the per-policy block -> scoped the scan to the leaderboard table (rung 3: the `_luck` code block is complete by construction and its `recorded` column does reproduce the database exactly; the test's scan predated that line). The assertion still requires every recorded trial to be seen.
    - `commands/lab.py` staged from the WORKING TREE, not from the purpose-built phase-5-only blob handed over at implementation time (rung: measurement over the handover). By staging time phase 9 had landed as `a17df19`, putting its `rm.*` call sites in HEAD, so the working-tree file was already phase-5-only against HEAD. Applying the pre-built blob as handed over would have REVERTED phase 9's 101 committed lines, because it was cut from the phase-4 HEAD `1cb2dc2`. Proved rather than assumed: the blob was rebuilt by replaying the phase-5 patch from that true base onto the new HEAD and came out BYTE-IDENTICAL to the working-tree file, and the staged diff carries zero `seed_preflight`/`is_seed_id`/`remeasure_seed` hits -- the handover's own gate check, run before committing.
    - Staging deferred rather than forced: at bookkeeping time the SHARED index already held phase 9's complete ready-to-commit set (its plan, `lab/remeasure.py`, `tests/test_lab_remeasure_seed.py`, `todos.md` and its own hunk-level blob of `commands/lab.py`). `git update-index` on that path would have destroyed phase 9's staged blob, and whichever session committed first would have absorbed the other's work wholesale -- `git commit` writes the entire index, not only the paths its author staged. Phase 5 waited for phase 9's commit to land and then staged into a clean index (rung 6: the shared-worktree discipline this whole set is run under; the alternative, a private `GIT_INDEX_FILE`, avoids the collision in one direction but leaves phase 9's stale index able to revert phase 5's paths on its next commit).
    - Landing: not attempted, and `next_command` is empty. This set is a swarm with coordinator `orch-lab-luck-gate`, so per `analyze-orchestrator` Step 5 the merge of `feature/lab-luck-gate` into `main` belongs to that coordinator, not to this session. Nothing merged to main, nothing deleted, `lab promote` not run.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks`, no `**Commit**` field, and `LAB_LUCK_GATE_PLAN.md` left untouched (rung 6: the direct precedent recorded by phases 1, 2, 3, 4, 6, 8 and 9 of this same set in this same file -- a cross-file block move is the one edit that reliably loses a peer's concurrent append, six peers hold the index open, and its TaskID/Card columns read `--` for all nine rows. The sha goes to the coordinator instead).
    - `readme-updater` dispatched, but only after phase 7 landed (`d2ee303`) and left `engine/package_readme.md` clean at HEAD. While that file was dirty with a peer's uncommitted work the correct move was phase 8's and phase 9's -- skip it -- since editing and staging it would commit that peer's work under phase 5's name; once it was clean, a brand-new CLI command warranted the entry. It added an Overview bullet, named `luck` in the `commands/lab.py` Layout line, and added two CLI sections. It corrected the brief on one point worth keeping: `lab luck` does not print the mean pairwise correlation as a column of its own -- `_evidence` reads an `npolicy.NCount`'s fields generically, so the participation ratio and the correlation surface on each policy's `evidence:` line without the CLI naming either.
    - Quick Stats recounted from the file rather than blind-decremented (rung 6: same precedent -- a recount is idempotent under concurrency, a decrement compounds the race).
- [x] **P1-ENG-EH4K** Phase 8: The go-live drawdown bar, 15% → 20%
  - **Difficulty**: HARD
  - **Type**: Update
  - **Context**: Owns `MAX_DRAWDOWN` 0.15 → 0.20 and its single home — the constant moves into `backtest/metrics.py` with `tuning` re-exporting it (`MAX_DRAWDOWN = _metrics.MAX_DRAWDOWN`), because `metrics.checklist` compares against a literal `0.15` today and `tuning.gate` / `walkforward.gate_p3b` / `b_walkforward.gate_p6a` all decide drawdown through `checklist(...)[2:5]`, so the P3/P3b/P6a real-money gates never read `MAX_DRAWDOWN` at all; `metrics.py` imports nothing from `tuning.py`, so this is the only non-circular arrangement and every existing reader of `tuning.MAX_DRAWDOWN` resolves unchanged. Also `dev.FAILURE_LABELS[1]` becoming `f"max DD <= {tuning.MAX_DRAWDOWN:.0%}"` (D13), `tuning._GATE_NAMES`, `web/lib/metrics.ts` (a second hardcoded implementation of go-live #4), `web/lib/golive.ts` + its engine-pinning test, design §1 item 4 of `docs/plans/2026-10-03-seer-design.md` with a new dated §11, and the pinned tests. Shares six files with phase 7 and lands first, moving only the drawdown number in each. Exit: one definition of the drawdown bar read by the lab screen, the go-live checklist and the web; `dev.FAILURE_LABELS[1] == "max DD <= 20%"` and prefix-stable so the 30 historical `"max DD <= 15%"` rows are still recognised as drawdown misses; `FAILURE_LABELS` keeps five entries in order; every gate-override test still overrides to a differing value; `lab/lab.sqlite` byte-identical to `origin/main`; `pytest` green and `npm test` green.
  - **Status**: completed
  - **Plan Set**: `LAB_LUCK_GATE_PLAN.md` (phase 8 of 9)
  - **Satisfies**: R5 — The owner's drawdown appetite is 20%, not 15%, and the bar must be one number rather than one per language.
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-EH4K.md`
  - **Completed**: 2026-10-07 11:16
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/metrics.py, engine/src/seer_engine/backtest/tuning.py, engine/src/seer_engine/backtest/dev.py, engine/src/seer_engine/backtest/walkforward.py, engine/src/seer_engine/backtest/b_walkforward.py, engine/src/seer_engine/backtest/dev_report.py, engine/src/seer_engine/backtest/report.py, engine/src/seer_engine/backtest/wf_report.py, engine/src/seer_engine/backtest/b_report.py, engine/tests/test_backtest_metrics.py, engine/tests/test_backtest_tuning.py, engine/tests/test_backtest_dev.py, engine/tests/test_backtest_walkforward.py, engine/tests/test_backtest_b_walkforward.py, engine/tests/test_backtest_report.py, engine/tests/test_backtest_wf_report.py, engine/tests/test_backtest_dev_report.py, engine/tests/test_lab_test_window.py, web/lib/golive.ts, web/lib/golive.test.ts, web/lib/metrics.ts, web/lib/metrics.test.ts, web/data/lab.json, web/lib/sera/fixture.ts, web/app/sera/overview.test.ts, web/app/sera/how/view.test.ts, web/lib/sera/derive.test.ts, web/app/sera/methods/view.test.ts, docs/plans/2026-10-03-seer-design.md, engine/.workflows/plan/P1-ENG-EH4K.md, engine/.workflows/todos.md
  - **Verified**: `pytest` in `engine/` with `PG_TEST_URL` set, `-o addopts=-ra` (serial) -> **3076 passed, 0 failed, 0 skipped**; `ruff check src tests` clean; `npx vitest run` in `web/` -> **292 passed (27 files)**; `npm run build` in `web/` succeeded. One definition proved: `tuning.MAX_DRAWDOWN` and `metrics.MAX_DRAWDOWN` both `0.2`, `metrics.MAX_DRAWDOWN_LABEL` = `Max drawdown <= 20%`, and `web/data/lab.json`'s gate reads `maxDrawdown: 0.2`. The bar actually moved and still discriminates: `M0020-W-NOSTOP` dd=0.1927 passes=True; `M0019-RAW20-S25` dd=0.2066 passes=False. Invariants held: `lab/lab.sqlite` byte-identical to `origin/main`; `store.test_looks` = 0.
  - **Drift**:
    - The plan's Step 9/10 file table under-listed the engine tests. Eight further drawdown assertions moved because the bar widened: `test_backtest_metrics.py` (the 0.16 "fails" case -> 0.21; the "inclusive" boundary 0.15 -> 0.20), `test_backtest_tuning.py` (three "does not qualify" grid fixtures at dd=0.16/0.2 -> 0.25, the inclusive case -> `MAX_DRAWDOWN`, and the `select()` fallback reason string), `test_backtest_walkforward.py` (the `select_fold` fallback reason string), `test_backtest_dev.py` (the `FAILURE_LABELS` pin at :206), `test_backtest_dev_report.py` (the `SPECS` fixture's failed tuple and its CSV assertion). Each fixture was moved clear of the new bar so it still proves what it names; no assertion was weakened.
    - Unlisted second copy of the drawdown label: `dev_report.py:60` `FAIL_ORDER` hardcoded `('beats SPY TR', 'max DD <= 15%', ...)`. It orders the failure histogram by exact string, so it would have dropped the drawdown bucket out of its slot once the label became `max DD <= 20%`. Now `FAIL_ORDER = dev.FAILURE_LABELS`.
    - `DevRow.__post_init__` validates `failed` against the live `FAILURE_LABELS`, so constructed test fixtures could not keep the literal `max DD <= 15%` (it broke collection of `test_backtest_dev_report.py`). Those fixtures now reference `FAILURE_LABELS[1]` symbolically. Recorded `trials.failed` strings in the database are untouched -- they are never validated through `DevRow`.
    - `engine/tests/test_lab_snapshot.py` is DELIBERATELY NOT in the files list. Step 11's one-line edit (gate `maxDrawdown` 0.15 -> 0.20, now at :277) IS applied on disk and the suite is green with it, but phase 2 has ~114 uncommitted lines of `trial_moments` schema-v3 work in that same file. Staging it would commit a peer's in-flight work under phase 8's name. The line rides with phase 2's commit instead; phase 2 has been told.
    - `readme-updater` deliberately skipped: `engine/package_readme.md`'s drawdown lines are phase 7's per phase-8 handoff H2, and the file is currently dirty with a peer's uncommitted work.
    - `web/node_modules` was missing `lucide-react` and `react-dom` (both declared in `package.json`); `npm install` repaired it. `node_modules` is gitignored; no tracked file changed.
  - **Decided**:
    - Plan's engine-test list incomplete -> moved each extra drawdown fixture clear of the new bar rather than relaxing any assertion (rung 3: the plan's code blocks, plus "a failing verification is never settled by relaxing the check").
    - `dev_report.FAIL_ORDER` was a second hardcoded label copy -> derived it from `dev.FAILURE_LABELS` (rung 3: Step 3b's rule that every reader follows the constant).
    - `test_lab_snapshot.py` excluded from the commit allowlist -> the edit lands with phase 2, which owns that file's uncommitted body (rung: /implement Step 4, "a file wrongly in it is a peer's work committed under your name").
    - `readme-updater` skipped -> `engine/package_readme.md` is phase 7's per H2 (rung 3: the phase plan's "Leaves alone (owned by others)").
    - `pytest` run with `-o addopts=-ra` rather than pip-installing `pytest-xdist` -> four sessions share that venv (rung 6: don't mutate shared ground mid-swarm; also the coordinator's broadcast decision on phase 1).
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks`, and no `**Commit**` field (rung 6: the direct precedent recorded by phases 1, 2 and 6 of this same swarm in this same file -- a cross-file block move is the one edit that reliably loses a peer's concurrent append, and this file is committed by whichever session commits it, so a sha field cannot stay consistent).
    - Quick Stats recounted from the file rather than blind-decremented (rung 6: same precedent -- a recount is idempotent under concurrency, a decrement compounds the race).
    - Plan index: ticked phase 8's TaskID cell `(done 2026-10-07)` and left `**Status:** reconciled` alone (rung 6: phases 1 and 6 ticked exactly that way and touched neither; in a swarm the phases finish out of order, so a `phase N/9 complete` line would assert an order that does not exist).
- [x] **P1-ENG-ALY2** Phase 9: Luck-test the P7a seed
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns extending `seer_engine.lab.remeasure` (phase 3's module) with a seed-specific path and a resumable batch mode over all 54 P7a trials, recovering their daily moments and writing only `trial_moments` rows. Does not touch `trials` — not one row, by invariant 7 — `methods.status`, the P7a `REGISTRY`, the test window or any constant; it changes runtime data, not any phase's logic. Exit: all 54 seed trials have `trial_moments` and therefore a real luck verdict; `store.dev_trial_count`, `npolicy.effective_n(conn, "all-trials").n`, `store.dev_sharpe_variance` and `store.dev_daily_sharpes` identical before and after; the batch is resumable, idempotent and ~65 seconds (10.8s store load + 51.5s of backtests), chunk-invariant; `test_looks` 0; `pytest` green. It makes nothing eligible — the report names `F9-SPY200M70-MOM30`'s resolved DSR at the gate's N (0.856651 under D12's today's-variance rule) with the as-of-P7a figure (0.903053) beside it in brackets, and reads `luck: fail` / `not eligible`; the eligible set stays three, but F9 is now held out by a luck test it received rather than by a data gap.
  - **Status**: completed
  - **Plan Set**: `LAB_LUCK_GATE_PLAN.md` (phase 9 of 9)
  - **Satisfies**: R6 — Half the lab's trials have never been luck-tested; they pay into N and get no verdict for it.
  - **Depends on**: P1-ENG-6134, P1-ENG-921N, P1-ENG-B6Y5
  - **Plan**: `.workflows/plan/P1-ENG-ALY2.md`
  - **Completed**: 2026-10-07 14:17
  - **Method**: /do
  - **Files**: engine/src/seer_engine/lab/remeasure.py, engine/src/seer_engine/commands/lab.py, engine/tests/test_lab_remeasure_seed.py, engine/.workflows/plan/P1-ENG-ALY2.md, engine/.workflows/todos.md
  - **Verified**: full engine suite with `PYTHONPATH=.../engine/src`, `PG_TEST_URL` set, `-o addopts="-ra"` (serial, main checkout's venv) -> **3186 passed, 0 failed**, 153 warnings in 419s. New `tests/test_lab_remeasure_seed.py`: 16 passed; targeted group (seed + remeasure + store + runner + test_window + registry) 158 passed. Real 54-trial batch against a COPY of the committed database (`SEER_LAB_DB` pointed at a scratch copy; the committed file never opened for write): exit 0, 54 `trial_moments` rows written, **zero blocked**. Invariant 7 proved by measurement, committed file vs fully-remeasured copy, all four quantities identical: `dev_trial_count` 110/110, `npolicy.effective_n(conn,'all-trials').n` 110/110, `dev_sharpe_variance` 0.00023950479947117267 on both, `dev_daily_sharpes` len 110 and sum 4.5469122331089125 on both. Invariant 3: sha256 over every column of every row -- `trials` IDENTICAL (`6bfc3a9e952987d7`), `methods` IDENTICAL (`2826262fe63b6d46`) before vs after the batch; `trials.dsr` still NULL on all 54 seed rows and every H-P7A method status still `rejected`. Invariant 2: `test_looks` reads 0 after the batch. D12 headline exactly as the plan predicted: `#53 F9-SPY200M70-MOM30 DSR @ N=110 = 0.85665110202 luck: fail (bar 0.9) [with the recorded as-of-P7a variance: 0.903053194698]`, `owner conditions: all pass MAR 0.635164 -> not eligible`. The eligible set is unchanged at THREE on both the committed file and the remeasured copy (M0020-W-NOSTOP, M0022-W-TV14, M0022-W-TV16) -- this phase makes nothing eligible, which is the intended outcome. Idempotent: the second run prints "every seed trial already has its moments; nothing to do", loads no research store, writes nothing, exit 0. Committed `lab/lab.sqlite` byte-untouched (md5 `5b94f444d69e7af262b1c815e84346c9`, unchanged) -- phase 4 owns that binary per D5/invariant 6. The staged-only build of `commands/lab.py` (without phase 5's in-flight work) was verified to import, parse and wire the CLI standalone: `lab remeasure --help` renders the widened positional plus `--only`/`--chunk`.
  - **Drift**:
    - The plan's Step 5 prose says "14 tests" while its Interface Contract and its own code block say 16. The code block is the artifact; the file has 16 and all 16 pass.
    - The plan's test code block referenced `research.TEST_WINDOW`, which does not exist in the module. Four further defects were test-side only; the implementation code blocks (Steps 1-4) applied verbatim with no changes.
    - Both phase-3 contract diffs (`resolve_method`'s docstring + message, `_moments_row`'s annotation) applied exactly as written, as phase 3 promised.
    - `readme-updater` deliberately skipped: `engine/package_readme.md` is already dirty with phase 7's in-flight edits, so editing and staging it would commit a peer's work under this phase's name.
  - **Decided**:
    - `research.TEST_WINDOW` does not exist -> used `research.test_window(research.TEST_WINDOW_START)`, the module's real API (rung 6: the surrounding code's convention; the guard reads `w.name`/`w.start`/`w.end`, so a genuine test `Window` is what the assertion needs).
    - The registry-drift test did `UPDATE trials SET config_digest` -> moved the mismatch to the REGISTRY side by monkeypatching `remeasure.config_digest` (rung 1: invariant 3, `trials` is append-only and the `trials_no_update` trigger refuses the write outright; the guard's intent, a digest mismatch, is preserved).
    - The D12 variance-contrast test asserted the two variances differ on a seed-only fixture where they are computed over the same 54 rows by construction -> the fixture now appends two non-seed dev trials carrying a `dsr`, reproducing the committed lab's 2.0067e-04 vs 2.3950e-04 contrast (rung 2: the phase's exit criteria -- D12's contrast is the thing under test, and a fixture where the two numbers coincide proves nothing).
    - The report assertion `f'{v.dsr:.6f}'[:6] in text` rounds at the 4th decimal while `format_seed_report` prints `_g(v.dsr)` at 12 significant digits; F6-ML-P50-N20-TREND is 0.840199760046 and sits exactly on that boundary -> assert against the report's own formatter (rung 3: the plan's code blocks are the reconciled artifact; the assertion was commentary on it).
    - `test_no_window_can_be_selected_anywhere_in_the_seed_path` called `remeasure.run_chunk` after monkeypatching it away, so it captured zero calls -> the real function is captured before the seam is substituted (rung 3).
    - The shared `engine/src/seer_engine/commands/lab.py` is staged at HUNK level, not wholesale, because phase 5's uncommitted +631-line `_status`/`_luck` rewrite is interleaved in the same file (rung: /implement Step 4's own rule that a peer's work must never be committed under my name; tie-break: the narrower blast radius). The working tree was not modified, so phase 5 loses nothing.
    - Landing: not attempted, and `next_command` is empty. `swarm.py find --plan LAB_LUCK_GATE_PLAN.md --task P1-ENG-ALY2` returns `swarm: true` with coordinator `orch-lab-luck-gate`, so per `analyze-orchestrator` Step 5 the merge of `feature/lab-luck-gate` into `main` belongs to that coordinator, not to this session -- even though this is phase 9 of 9. Nothing merged, pushed to main, or deleted; the branch itself was pushed.
    - Completion: the `[x]` block left in place under `### [P1] High` rather than moved into `## Completed Tasks`, and no `**Commit**` field (rung 6: the direct precedent recorded by phases 1, 2, 3, 4, 6 and 8 of this same set in this same file -- a cross-file block move is the one edit that reliably loses a peer's concurrent append, and the file is committed by whichever session commits it, so a sha field cannot stay consistent).
    - `LAB_LUCK_GATE_PLAN.md` left untouched, including phase 9's row (rung 6 + measurement: the index's TaskID and Card columns read `--` for all nine rows and `git log -- LAB_LUCK_GATE_PLAN.md` shows exactly one commit, the plan's own creation -- so phase 8's recorded "ticked phase 8's TaskID cell" never survived, which is direct evidence that a cross-file tick in this shared worktree is lost. The set is a swarm whose coordinator owns the ledger at `.workflows/orchestration/lab-luck-gate/ledger.json`; the sha goes there instead).
    - No peer phase was unblocked or altered: phase 5 (`P1-ENG-QM5I`) stays `blocked` and in flight in a peer session; `next_task_id` was empty and phase 9 is the last phase, so there is no successor to release.
    - Quick Stats recounted from the file rather than blind-decremented (recount is idempotent under concurrency; a decrement compounds the race).


### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

---

## Completed Tasks
- [x] **P1-ENG-MWRQ** Phase 7: Money-weighted return, and a SPY fed the same money
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/backtest/metrics.py`; `backtest/benchmark.py` (the schedule reaches `buy_and_hold` / `spy_curves`); `backtest/dev.py` (the gate restated); `engine/src/seer_engine/lab/store.py` (the trial schema and `owner_failures`); `engine/tests/test_backtest_metrics.py`, `test_backtest_benchmark.py`. Also owns `dev.run_registry` / `dev._run`'s `contributions` keyword and `dev.py`'s `is_bracket` dispatch, plus `engine/tests/test_lab_snapshot.py`'s six `SCHEMA_VERSION` string pins and the new v3->v4 migration test. Exit criteria: a contribution-fed book reports a money-weighted return beside its CAGR, and every gate phrased in CAGR terms is restated in it; SPY is dollar-cost-averaged on the identical schedule, so "beats SPY TR" compares two books holding the same money at the same times.
  - **Status**: completed
  - **Plan Set**: `GOTRADE_FEE_REBUILD_PLAN.md` (phase 7 of 12)
  - **Satisfies**: R3 — Measure what the owner will actually do: 10,000,000 IDR start, +5,000,000 IDR on the 25th of each month — contributions in backtest and paper, a money-weighted return, a dollar-cost-averaged SPY, every CAGR-phrased gate restated
  - **Depends on**: phase 2 (P1-ENG-KQRW), phase 5
  - **Plan**: `.workflows/plan/P1-ENG-MWRQ.md`
  - **Completed**: 2026-10-08 11:58
  - **Method**: /do
  - **Commit**: `35e33e5` — all nine phase 7 files are inside it and nothing else is; verified
    with `git show --stat --format="" 35e33e5` against the allowlist before the push. Committed
    as `git add -- <the two new files>` then `git commit -F <msgfile> -- <nine paths>`, the
    pathspec form phases 4 and 6 record as the only one the allowlist actually protects in this
    shared index. This sha is recorded by a second, todos-only commit, since a commit cannot
    name itself.
  - **Files**: engine/src/seer_engine/backtest/metrics.py, engine/src/seer_engine/backtest/benchmark.py, engine/src/seer_engine/backtest/dev.py, engine/src/seer_engine/lab/store.py, engine/tests/test_backtest_metrics.py, engine/tests/test_lab_snapshot.py, engine/tests/test_backtest_benchmark.py (new), engine/.workflows/plan/P1-ENG-MWRQ.md (new), engine/.workflows/todos.md
  - **Verified**: engine suite `PYTHONPATH=engine/src PG_TEST_URL=... python -m pytest engine/tests -q -n auto` -> **3456 passed, 1 skipped, 0 failed**, re-run on top of phase 6's `ca75a96`. Web `npx vitest run` -> 625 passed / 48 files / 0 failed; `npx tsc --noEmit` -> exit 0. `python -m ruff check engine` -> all checks passed. Import build clears the metrics <-> book_runner cycle. Exit criterion 9: `grep -n 'bracket_v0' engine/src/seer_engine/backtest/dev.py` returns nothing. `git diff --stat` shows no change to `backtest/runner.py`, `backtest/book_runner.py`, `sim/`, `paper/`, `web/` or `lab/lab.sqlite`.
  - **Drift**:
    - `engine/.workflows/todos.md` already carried this phase's task row: it was swept into phase 6's commit `27a9a17`, which documented doing so. The row was on the branch before this phase committed; flipping it to completed is the new edit, and that is the only reason todos.md is in this phase's allowlist.
    - The plan's manual check expected `money-weighted +0.00%`; the code prints `-0.00%`. The value is zero to 13 decimal places (bisection lands a hair under zero) and the pinned test asserts `abs(mwr) < 1e-9` and passes. Formatting artefact, not a behaviour difference.
  - **Decided**:
    - Step 10's code block feeds `external_cashflows(result)` (floats, per its own Step 4 definition) into `spy_curves`, but Step 6 requires Decimal amounts — the two code blocks contradict, and the registry run raised TypeError. -> Pass `result.cashflows` straight through. Rung 2 (the phase's exit criteria): criterion 3 says `spy_curves` is fed `result.cashflows`, which is already Decimal. Phase 5's own handoff independently says the benchmark takes the dated Decimal half. Keeping Decimal also avoids rounding real money through binary floats, so the benchmark pays the same sum as the book it benchmarks.
    - A funded BOOK run reported `mwr=None`, because `book_runner._book_metrics` calls `strategy_metrics` without cashflows — so `make_row` ranked a deposit-fed book on its inflated CAGR (measured: MAR 113.8 on a book whose money actually lost 64.7%). That is the +600.9% lie this phase exists to end, surviving on the engine four of the roster's six entries run. The one-keyword fix belongs to `book_runner.py`, which is phase 5's file and which this phase's Interface Contract says to leave alone. -> Computed it in `dev._funded_stats`, inside this phase's own Owns. Tie-break: take the narrower blast radius — a change inside the phase's Owns beats an equivalent change outside it, even when the outside one is tidier. Handed off below.
    - `GOTRADE_FEE_REBUILD_PLAN.md` left untouched — no phase-7 row tick, no `**Status:**` change. This set is a coordinated swarm whose ledger owns set-level progress; phases 1, 2, 3, 5 and 6 all recorded the same decision, and the repo-root index is outside this phase's commit allowlist.
    - No Step 5a landing, no merge to `main`, no branch or worktree deletion: the coordinator lands the set (analyze-orchestrator Step 5). Landing here too is the double-merge that rule exists to prevent.
    - `engine/.workflows/plan/P1-ENG-KQRW.md` (phase 2's untracked leftover in this shared worktree) deliberately left alone — not added, not committed, not deleted.
    - `engine/package_readme.md` NOT updated, and `readme-updater` not dispatched. Phase 7's Owns does not name it (phase 5's did, and phase 5 updated it), and this phase's commit allowlist is fixed at its eight files plus this one. In a worktree three peers are writing concurrently, a readme edit that cannot be committed is worse than no readme edit: it leaves a dirty shared file for a peer's stage to sweep up. Same call phase 6 recorded.
  - **Handoffs**:
    - **`book_runner._book_metrics` should take the cashflows (phase 5's file).** It calls `strategy_metrics(snaps, pnls)` with no cashflows, so a `BookResult` carries no `mwr` of its own and `dev._funded_stats` fills it in. The tidier fix is one keyword there; whoever next owns `book_runner.py` should make it and delete `_funded_stats`'s fallback branch. Harmless until then: `dev` is the only caller that passes a schedule, so every other `run_stats` caller runs unfunded.
    - **Phase 8 writes the first funded trials.** `store.insert_funding` exists for the writer; `trial_funding` is correctly empty today because nothing in the lab has ever been fed. Stamp it with the trial's own `run_at` and the schedule's own words.
    - **Phase 8 — `config_digest`.** `trials` carries `UNIQUE(config_digest, window)`. If the schedule does not reach `lab/runner.config_digest`, a funded and an unfunded run of the same method collide and the second insert is refused. Flagged, not decided here; `lab/runner.py` is not phase 7's file.
    - **`lab/lab.sqlite` is v3 and is NOT touched here.** It migrates itself to v4 on its next `lab` write (an empty table, two triggers, no recorded value changes). Whoever first runs a `lab` command that writes should commit the migrated file in that commit.
    - **The web has nothing to publish yet.** `_snapshot_trial` / `TRIAL_KEYS` are untouched by design (the side table is why). Once funded trials exist, `/sera` will want `mwr` / `spyTrMwr` beside `cagr` / `spyTrCagr` with the plain gloss.
- [x] **P1-ENG-R7MD** Phase 6: Paper accepts a deposit
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `db/migrations/016_contributions.sql` (**this number, not another**), `engine/src/seer_engine/paper/store.py` (a deposit path beside the write-once `initial_cash_usd`), `paper/book.py`, `engine/tests/test_paper_store.py`, `test_paper_book.py`, and — reconciler decision **D12** — `paper/compare.py` plus its impure edge `commands/compare.py`, so a deposit is not read as a return. Does not touch `paper/roster.py` or `db/migrations/017_*` (phase 12), `paper/benchmark.py` (phase 3), `paper/bracket.py` (phase 4), or `store.py:1127-1145` (`load_benchmark`), which is phase 12's single hunk in this phase's file (D10 + D13) — the two regions are line-disjoint and phase 6 lands first. Exit: paper can record money arriving and apply it on its session, where today `initial_cash_usd` is written once at `store.py:417` and the only later UPDATE (`:449`) writes `cash_usd`, `equity_usd` and `last_session`; deposits reach every engine — the four quant books, C and SPY — because the gap is below all of them, not per-method; a deposit landing between sessions raises cash on its session and is **not** counted as a return; **a credit raises CASH AND EQUITY by the same amount, asserted not assumed**, since both engines size from the last snapshot's equity (`sim/sizing.py:137`, `sim/book.py:536`) and crediting cash alone would leave every deposit permanently under-deployed — `paper.book.deposit_book` does both; and `paper.compare._returns` removes the session's deposit before taking the ratio, so a book that earns nothing and is handed $312.50 reports 0%, not +31% (D12).
  - **Status**: completed
  - **Plan Set**: `GOTRADE_FEE_REBUILD_PLAN.md` (phase 6 of 12)
  - **Satisfies**: R3 — Measure what the owner will actually do: 10,000,000 IDR start, +5,000,000 IDR on the 25th of each month — contributions in backtest and paper, a money-weighted return, a dollar-cost-averaged SPY, every CAGR-phrased gate restated
  - **Depends on**: P1-ENG-HPOI
  - **Plan**: `.workflows/plan/P1-ENG-R7MD.md`
  - **Completed**: 2026-10-08 11:52
  - **Method**: /do
  - **Commit**: `ca75a96` — all ten phase 6 files are inside it and nothing else is; verified
    with `git show --stat --format="" ca75a96` against the allowlist before the push. Committed
    as `git commit -F <msgfile> -- <ten paths>`, the atomic stage-and-commit form phase 4 above
    records as the only one the allowlist actually protects in this shared index. This sha is
    recorded by a second, todos-only commit, since a commit cannot name itself.
  - **Files**: db/migrations/016_contributions.sql, engine/src/seer_engine/paper/store.py, engine/src/seer_engine/paper/book.py, engine/src/seer_engine/paper/compare.py, engine/src/seer_engine/commands/compare.py, engine/tests/test_paper_store.py, engine/tests/test_paper_book.py, engine/tests/test_paper_compare.py, engine/.workflows/plan/P1-ENG-R7MD.md, engine/.workflows/todos.md
  - **Verified**: engine suite `PYTHONPATH=engine/src PG_TEST_URL=... python -m pytest engine/tests -q -n auto` -> **3454 passed, 1 skipped, 0 failed**. `ruff` clean on all seven changed source and test files.
  - **Drift**:
    - No code drift: every anchor the plan quotes (store.py:39/:55 imports, `write_kickoff`/`save_book_preview`, book.py:50, `rank_basket`/`settle_book`, the test import blocks) matched the tree exactly.
    - The plan's test snippet for `test_paper_compare.py` used `D("2026-09-28")` as a date helper, but in that file `D` is a date CONSTANT (`date(2026, 1, 5)`). Adapted to `date(...)` and the file's own `curve()` builder.
  - **Decided**:
    - Plan prose says "four of the twelve 25ths are not sessions"; its own measured table and the live NYSE calendar both say five -> corrected to five in all four places (migration comment, `store.contribution_session` docstring, two test comments, and the assertion). Rung 1: invariant 6, every number measured with its command recoverable.
    - `Performance` gains a `deposited` field but `_performance_json` keeps its exact seven keys -> `as_json` shape unchanged. Rung 2: this phase's exit criterion "with no deposits every ranked figure is bit-identical", plus narrower blast radius — the shape is pinned by `test_as_json_field_names_units_and_nulls` and ported to TypeScript by a different plan set.
    - `engine/package_readme.md` NOT updated, and `readme-updater` not dispatched. Rung 3: phase 6's Files table names exactly seven files and the readme is not among them, while phase 5's plan explicitly did list its readme lines. Never widen scope.
    - `engine/.workflows/todos.md` also carries phase 7's task row P1-ENG-MWRQ, minted by that concurrent session in this shared worktree; a single file cannot be committed line-by-line, so that row is swept into this phase's commit. It is a correct task record, not code. Noted so phase 7's handler sees its row already committed.
    - `GOTRADE_FEE_REBUILD_PLAN.md` left untouched — no phase-6 row tick, no `**Status:**` change — and `.workflows/orchestration/gotrade-fee-rebuild/ledger.json` left untouched too. This set is a coordinated swarm whose ledger owns set-level progress; phases 1-5 all deliberately left the index alone, the repo-root index is outside this phase's commit allowlist, and `**Status:**` is one field eleven concurrent sessions would each overwrite.
    - No Step 5a landing, no merge to `main`, no branch or worktree deletion: the coordinator lands the set (analyze-orchestrator Step 5). Landing here too is the double-merge that rule exists to prevent.
    - The `[x]` block moved into `## Completed Tasks` and Quick Stats recounted from the file rather than blind-decremented (recount is idempotent under concurrency; a decrement compounds the race).
- [x] **P1-ENG-HPOI** Phase 5: A contribution schedule, and the lab's real capital
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sim/contributions.py` (new: ContributionSchedule, OWNER_MONTHLY, dates_in, due, usd_at, credit_usd, MAX_DAY_OF_MONTH, the alias Contributions and credit_for), `backtest/runner.py` (INITIAL_IDR, session loop, and its `rules` keyword — phase 4's H1), `backtest/book_runner.py` (and its is_bracket dispatch + order_fee — phase 4's H1/H2), new `engine/tests/test_sim_contributions.py`, plus test_backtest_runner.py, test_book_runner.py, test_backtest_report.py, test_backtest_b_report.py, test_backtest_wf_report.py, test_backtest_labels.py, and engine/package_readme.md. Exit: +5,000,000 IDR on the 25th of each month is expressible as a value object and honoured by both backtest runners; INITIAL_IDR is the real 10,000,000 IDR; the schedule deposits on a calendar date and lets the NYSE calendar produce the lag; run_backtest(..., rules=DESIGN_V0_GOTRADE) ends with strictly less equity than at DESIGN_V0; run_rules sends a "bracket" rule set to run_backtest rather than step_book.
  - **Status**: completed
  - **Plan Set**: `GOTRADE_FEE_REBUILD_PLAN.md` (phase 5 of 12)
  - **Satisfies**: R3 — Measure what the owner will actually do: 10,000,000 IDR start, +5,000,000 IDR on the 25th of each month — contributions in backtest and paper, a money-weighted return, a dollar-cost-averaged SPY, every CAGR-phrased gate restated
  - **Depends on**: P1-ENG-F6QN
  - **Plan**: `.workflows/plan/P1-ENG-HPOI.md`
  - **Completed**: 2026-10-08 11:28
  - **Method**: /do
  - **Files**: engine/src/seer_engine/sim/contributions.py, engine/src/seer_engine/backtest/runner.py, engine/src/seer_engine/backtest/book_runner.py, engine/tests/test_sim_contributions.py, engine/tests/test_backtest_runner.py, engine/tests/test_book_runner.py, engine/tests/test_backtest_labels.py, engine/tests/test_backtest_report.py, engine/tests/test_backtest_b_report.py, engine/tests/test_backtest_wf_report.py, engine/tests/test_paper_bracket.py, engine/package_readme.md, engine/.workflows/todos.md, engine/.workflows/plan/P1-ENG-HPOI.md
  - **Verified**: `cd engine && python -m ruff check src tests` -> All checks passed!. `PYTHONPATH=engine/src PG_TEST_URL=... python -m pytest engine/tests -q -n auto` -> **3413 passed, 1 skipped, 0 failed** against a coordinator-measured baseline of 3388 passed / 1 skipped / 0 failed taken minutes earlier with nothing else writing: +25 tests, zero new failures. `cd web && npx tsc --noEmit` exit 0; `npx vitest run` 47 files / 606 tests passed. All six exit criteria verified, including criterion 5 (ending equity 1273.4568 flat vs 1249.5128 gotrade -- strictly less; `run_rules` returns a RunResult for a `"bracket"` rule set) and criterion 6 (D18 round trip: re-feeding a run its own `cashflows` reproduces snapshots, events and cashflows exactly).
  - **Drift**:
    - Phase 5's "moving INITIAL_IDR breaks 10 tests in 5 files, and nothing else" was measured at 485d416, BEFORE phase 4 landed. Phase 4 added `engine/tests/test_paper_bracket.py`, whose fixture funds from INITIAL_IDR and whose price ladder is calibrated to a 1250 USD book, so halving the capital broke `test_a_gotrade_night_keeps_the_shape_and_pays_strictly_more`. Fixed with this phase's own documented remedy, already applied three times in Steps 5/6/7: pin the fixture at its own `Decimal('20000000')` (BRACKET_IDR) and pass it at the four funding/comparison sites. Measured and written into the comment: at 20M both runs place 215 events with identical shape; at 10M the slot halves, `lt_one_share` rejections go 26 -> 123, and Gotrade's $0.10 floor rejects five more names than flat (128 vs 123). No assertion was relaxed.
    - Step 2b's H2 one-liner `cost = order_fee(side, price, shares, rules)` was written against line numbers pointing at `book_runner.py`'s private `_fee` helper, and names `cost`/`side`/`rules` that exist at no call site there. Implemented as described under Decided.
    - Step 4's test block predates the reconciler's D18 and imports no `credit_for`, but exit criterion 6 requires the record form to be asserted. Added `credit_for` to the import plus 3 tests for it (14 tests in the file, not the plan's 11), and one round-trip test in `test_backtest_runner.py`.
  - **Decided**:
    - Step 2b's `order_fee` site needs a rule set `RunResult` does not carry -> threaded `rules: TradeRules = DESIGN_V0` as a keyword-with-default through `run_stats` / `_run_result_stats` / `_fee`, rather than adding a third field to `RunResult` (rung 3: the plan's Interface Contract lists RunResult's new fields exhaustively as two, and phases 6/7/8/12 quote it; keyword-with-default is D10's own pattern). Measured bit-identical under the default; costs 14.6854 flat vs 42.43 gotrade on the seeded fixture.
    - Phase 4's `test_paper_bracket.py` broke on the INITIAL_IDR move -> pinned its fixture at its own 20,000,000 IDR (rung 3: the plan's own "pin the fixture rather than loosen the tolerance"). See Drift above.
    - The plan's Verification prescribes `git stash && pytest && git stash pop` for the before/after failure sets -> skipped; used the coordinator's measured baseline instead (engine 3388 passed / 1 skipped / 0 failed, taken minutes before this phase started with nothing else writing). Rung 1: bare `git stash` is a tree-wide git command, banned in this shared worktree.
    - `GOTRADE_FEE_REBUILD_PLAN.md` left untouched, phase 5's row not ticked (rung 1 + the direct precedent of phases 1, 2, 3, 9 and 11 of this same set): the set is a coordinated swarm whose `ledger.json` owns set-level progress, the index is outside this phase's commit allowlist, and a cross-file tick races eleven peers.
    - The `[x]` block moved into `## Completed Tasks` and Quick Stats recounted from the file rather than blind-decremented (recount is idempotent under concurrency; a decrement compounds the race).
- [x] **P1-ENG-KQRW** Phase 2: A test-window look is not luck-gated, and says so
  - **Difficulty**: HARD
  - **Type**: Bug
  - **Context**: Owns `engine/src/seer_engine/lab/store.py` (`luck_gated()` after `published_verdict`, `SNAPSHOT_VERSION` 3→4, the `"luckGated"` key in `_snapshot_trial` — and nothing else in that file); `web/lib/sera/{types,derive,fixture,lab.test,derive.test}.ts`; `web/app/sera/methods/{view.ts,view.test.ts,[id]/page.tsx,page.tsx}`; `web/app/sera/overview.test.ts`; `web/data/lab.json` (regenerated); `engine/tests/test_lab_snapshot.py` (the `TRIAL_KEYS` set, the int `s["version"]` pin at :280, and two new tests only). Exit criteria: `cd web && npx vitest run` reports 0 failed (today 1 failed | 9 passed in lib/sera/lab.test.ts); `npx tsc --noEmit` clean; the engine suite reports 0 failed for test_lab_snapshot.py; `web/data/lab.json` has `"version":4` and exactly 2 trials with `"luckGated":false`, both `window: "test"`, both still carrying `dsrNow`; a test-window row renders "not applicable" rather than a green tick and prints no `at N 126`; `lab.test.ts` decides the luck branch by reading `t.luckGated`; `lab/lab.sqlite` is byte-identical.
  - **Status**: completed
  - **Plan Set**: `GOTRADE_FEE_REBUILD_PLAN.md` (phase 2 of 12)
  - **Satisfies**: R7 — Settle how a test-window look relates to the luck gate; make snapshot, pages and test agree
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-KQRW.md`
  - **Completed**: 2026-10-08 10:51
  - **Method**: /do
  - **Files**: engine/src/seer_engine/lab/store.py, engine/tests/test_lab_snapshot.py, web/data/lab.json, web/lib/sera/types.ts, web/lib/sera/derive.ts, web/lib/sera/fixture.ts, web/lib/sera/lab.test.ts, web/lib/sera/derive.test.ts, web/app/sera/methods/view.ts, web/app/sera/methods/view.test.ts, web/app/sera/methods/[id]/page.tsx, web/app/sera/methods/page.tsx, web/app/sera/overview.test.ts, engine/.workflows/todos.md, engine/.workflows/plan/P1-ENG-KQRW.md
  - **Drift**: web/app/sera/overview.test.ts pinned `version: 3` in a LabSnapshot fixture literal at :89 that the plan's Files table did not list (it listed only the trial() literal at :41-76). The LabSnapshot.version type change from Step 5 forces it. Moved to 4; same forced-by-the-type-change class as the luckGated literals, in a file the phase already owns.
  - **Drift**: `luck_gated()` landed at store.py:1273 rather than the plan's quoted :1272 — it is immediately after `published_verdict`'s closing paren and before the REEVALUATION_MARKER block, exactly as specified. A one-line offset in the plan's quote, not a code difference.
  - **Decided**: Step 3 says create tasks for all 12 phases, but five peer /implement sessions are running against this same plan and worktree concurrently and would each do the same -> duplicate rows and a 6-way concurrent write to one todos.md. Created phase 2's task only. (Rung 1: invariant 1, the tree builds and both suites pass at the end of each phase.)
  - **Decided**: Phase 2's task was filed in the `engine` package rather than `web`, though 10 of its 13 files are under web/. (Rung 6, the surrounding convention: the plan index's Package column and the phase plan's own header both name `engine.lab` first, and the published marker originates in the engine.)
  - **Decided**: web/app/sera/overview.test.ts version pin 3 -> 4, not listed in the plan's Files table. (Rung 2: phase 2's exit criterion 2, `npx tsc --noEmit` is clean.)
  - **Decided**: `GOTRADE_FEE_REBUILD_PLAN.md` left untouched — no phase-2 row tick, no `**Status:**` change. This set is a swarm (`swarm.py find` -> coordinator `orch-gotrade-fee-rebuild`), so the ledger at `.workflows/orchestration/gotrade-fee-rebuild/ledger.json` owns progress, not the index. Same call phases 1 and 3 of this set recorded minutes earlier: the repo-root index is outside this phase's commit allowlist, `**Status:**` is one field six concurrent wave-1 sessions would each overwrite, and engine/.workflows/todos.md already records a measured case of such a cross-file tick being lost in this shared worktree.
  - **Decided**: engine/.workflows/todos.md is in the commit allowlist even though it currently also carries peer phases 1, 3 and 4's uncommitted rows — excluding it would mean this task's record never lands, and the swept-in rows are correct task records, not code (tie-break: take the reversible option). Noted so the peers' handlers see their rows already committed.
  - **Verified**: `PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres python -m pytest engine/tests -q -n auto` -> 3385 passed, 1 skipped, 0 failed (the skip is the deliberate SEER_LAB_COSTS_LIVE live-store gate).
  - **Verified**: `cd web && npx vitest run` -> 47 files, 606 tests passed, 0 failed (was `1 failed | 9 passed` in lib/sera/lab.test.ts; that file is now 11 passing).
  - **Verified**: `cd web && npx tsc --noEmit` -> clean.
  - **Verified**: `lab export-json` re-run is idempotent; `lab/lab.sqlite` byte-identical (git status clean for it). web/data/lab.json: version 4, 126 gated, 2 ungated, both window=test, both still carrying dsrNow.
  - **Verified**: Rendered against the real committed snapshot through the real render functions: M0021-B70-RAW -> `Luck check: not applicable`, mark ok=null (dashed), DSR cell `0.51 not a hurdle on a test run`; M0029-B70-RAW-FRAC -> same at 0.39; dev control M0001-TV10 unchanged at `Luck check: missed` / `at N 126`.
- [x] **P1-ENG-H2VK** Phase 3: The live SPY benchmark pays what the methods pay
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/paper/benchmark.py` and `engine/tests/test_paper_benchmark.py`. Does not touch `backtest/benchmark.py` (it already carries the cost_model lever), anything in `sim/`, `commands/paper.py` or `paper/store.py` (phase 12's wiring under D10). Exit: all three flat sites take the cost model — the recorded `Fill.cost_usd` at :170, the entry buy at :249-250 and the reinvestment buy at :276-279 — and the recorded fee equals the cash actually moved; `BenchmarkState` carries the model so it survives between nights; the default stays "flat" and the 16 pre-existing tests pass bit-identically. This is resume condition 1 of three.
  - **Status**: completed
  - **Plan Set**: `GOTRADE_FEE_REBUILD_PLAN.md` (phase 3 of 12)
  - **Satisfies**: R1 (Q1) — Rebuild the roster so every entry pays Gotrade's measured fees, SPY included — as new entries with fresh paper clocks
  - **Plan**: `.workflows/plan/P1-ENG-H2VK.md`
  - **Completed**: 2026-10-08 10:49
  - **Method**: /implement
  - **Files**: engine/src/seer_engine/paper/benchmark.py, engine/tests/test_paper_benchmark.py, engine/.workflows/todos.md, engine/.workflows/plan/P1-ENG-H2VK.md
  - **Drift**: No code drift: engine/src/seer_engine/paper/benchmark.py matched every line the plan quoted, at the quoted line numbers.
  - **Drift**: Plan prose nit, no code impact: the Manual check snippet's expected output says 'flat fee 0.9990, ratio 2.34' for the $1,000-at-$100 case; the actual is 'flat fee 0.9977, ratio 2.35'. Both are correct about different things — the plan's Goal table's $0.9990 is the FLAT model buying its own 9.99 shares, while the snippet prices the flat fee on gotrade's 9.9766-share count. The first line printed exactly as the plan says (0.9352 sh, gotrade fee 1.45, flat fee 0.5985, ratio 2.42). The authoritative figures ($3.67 vs $1.3840 of fees; $1,248.2768 vs $1,250.5694 ending equity) are asserted by test_gotrade_nights_equal_buy_and_hold_at_the_same_cost_model, which passes.
  - **Drift**: Shared-worktree noise: the full engine suite in this worktree reports 140 failed / 43 errors, every one of them from peer phases 1, 2 and 4's in-flight edits to sim/rules.py, sim/sizing.py, sim/lifecycle.py, sim/split_adjust.py, sim/__init__.py, lab/npolicy.py and lab/store.py. None is phase 3's. Proven by isolation, see Verified below.
  - **Decided**: Step 3 says create all 12 phases' tasks, but 5 peer sessions run that same step concurrently in this shared worktree -> created only phase 3's task (P1-ENG-H2VK). Rung 6, the surrounding convention: engine/.workflows/todos.md:60 and :993 record exactly this call made in two earlier swarms, and a shared package counter is a lost-update race.
  - **Decided**: The plan's full-suite verification command is unusable in a shared worktree mid-wave (140 peer-caused failures) -> ran it against a pristine `git archive HEAD` copy carrying ONLY phase 3's two files instead of relaxing or skipping the check. Result 3367 passed / 1 failed, the single failure being the isolation harness itself (`git rev-parse HEAD` exits 128 because the scratch copy is not a git repo), not code. Rung 1, invariant 1 (both suites pass at the end of each phase) read together with the tie-break that a failing verification is never settled by relaxing the check.
  - **Decided**: The `[x]` block is moved into `## Completed Tasks` and Quick Stats recounted from the file rather than blind-decremented — following phase 1 (P1-ENG-R4XB) of this same set, which moved its block minutes earlier; a recount is idempotent under concurrency where a decrement compounds the race.
  - **Decided**: `GOTRADE_FEE_REBUILD_PLAN.md` left untouched — no phase-3 row tick, no `**Status:**` change -> the swarm ledger owns progress, not the index. Three reasons: the commit allowlist for this phase is four paths and excludes the repo-root index, so the edit could never land and would sit dirty in a worktree five peers are staging from; `**Status:**` is a single field six concurrent wave-1 sessions would each overwrite with a different `phase N/12`; and `engine/.workflows/todos.md:776` records the measurement that a cross-file index tick in this shared worktree was already lost once (`git log -- LAB_LUCK_GATE_PLAN.md` showed only the plan's creation commit).
  - **Verified**: `python -m ruff check engine` -> All checks passed!
  - **Verified**: `PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres python -m pytest engine/tests/test_paper_benchmark.py -q -n auto` -> 22 passed (16 pre-existing, bit-identical at the "flat" default, plus the 6 new ones).
  - **Verified**: The three paper files the plan names: `test_paper_benchmark.py test_paper_store.py test_paper_command.py` -> 76 passed.
  - **Verified**: Full engine suite, isolated from peers (pristine `git archive HEAD` copy + only phase 3's two files, PYTHONPATH at that copy's engine/src) -> 3367 passed, 1 failed, 2 skipped in 274.56s; the 1 failure is `test_lab_prereg.py::test_lab_promote_command_exits_2_when_the_lab_refuses`, failing on `git rev-parse HEAD` exit 128 because the scratch tree is not a git repo — a harness artifact, not a code failure.
  - **Verified**: Manual check reproduced: `0.9352 sh, gotrade fee 1.45, flat fee 0.5985, ratio 2.42`.
  - **Verified**: Exit criterion 5 fences all hold: `git diff --name-only` shows NO change to `sim/costs.py` (invariant 5), `.github/workflows/nightly.yml` (`PAPER_PAUSED` still `'true'` at :70, invariant 2), `paper/roster.py`, `commands/paper.py`, `paper/store.py` or `backtest/benchmark.py`. No roster entry added, edited or retired (invariants 3, 4, 8). Phase 3's own diff is exactly 2 files, +178/-23.
- [x] **P1-ENG-R4XB** Phase 1: The CI guard catches what it was written for
  - **Difficulty**: NORMAL
  - **Type**: Bug
  - **Context**: Narrow `.github/workflows/engine-ci.yml`'s `^SKIPPED` guard to conftest's `pg_url` skip reason only, so deliberate skipifs stop turning the build red with a false "PG_TEST_URL did not reach pytest" message; and replace `engine/tests/test_lab_npolicy.py`'s four aged `COMMITTED_*` constants with a recomputation from the committed lab database so the pinned-evidence test asserts instead of skipping. Plus three comment-only number fixes in `lab/npolicy.py` (D11). Exit: guard fires only on the real misconfiguration, `test_lab_npolicy.py` reports 0 skipped, engine suite 0 failed, `ruff check engine` passes.
  - **Status**: completed
  - **Plan Set**: `GOTRADE_FEE_REBUILD_PLAN.md` (phase 1 of 12)
  - **Satisfies**: R6 — Narrow the CI skip-guard; put `COMMITTED_DEV_TRIALS` in a form that cannot age again
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-R4XB.md`
  - **Completed**: 2026-10-08 10:48
  - **Method**: /do
  - **Files**: .github/workflows/engine-ci.yml, engine/tests/test_lab_npolicy.py, engine/src/seer_engine/lab/npolicy.py, engine/.workflows/todos.md, engine/.workflows/plan/P1-ENG-R4XB.md
  - **Drift**: No code drift: all three files matched the plan's quotes byte-for-byte at 485d416/12d563e.
  - **Drift**: The plan's exit criterion 4 predicted `3362 passed, 1 skipped`; measured `3363 passed, 1 skipped, 0 failed`. The old pinned test counted as a skip and the new one passes, so passes rise by one. The invariants the criterion named (0 failed, 1 skipped) hold.
  - **Drift**: The shared worktree's full suite reports 5 failures, ALL in peer territory (phase 4's gotrade presets and `bracket` engine in sim/rules.py + sim/charges.py; phase 2's web/data/lab.json export vs lab/store.py). Verified by re-running the whole engine suite in a throwaway worktree cut from HEAD with ONLY this phase's three files applied: 3363 passed, 1 skipped, 0 failed, ruff clean.
  - **Drift**: The plan's 'eight skip sites' is nine (the phase plan's own Handoff 2 records this); it changes no code because the narrowed guard keys on one reason string.
  - **Decided**: Step 3 says create every phase's task, but six wave-1 sessions share this worktree and would each write all 12 into the same todos.md -> created phase 1's task only (tie-break: narrower blast radius; in a swarm the ledger, not todos.md, unblocks phases).
  - **Decided**: The plan's exit criterion 3 requires `grep -c 'COMMITTED_DEV_TRIALS\|COMMITTED_METHODS\|COMMITTED_PR\|COMMITTED_RHO'` to return 0, but its own Step 3 code block puts `COMMITTED_PR = 2.442` inside the new docstring -> the exit criterion wins and the docstring was reworded to 'a participation ratio pinned at 2.442, and friends' (rung 2, the phase's exit criteria, outranks rung 3, the code blocks). The history is kept, only the identifier goes; the check is satisfied, not loosened.
  - **Decided**: engine/.workflows/todos.md carries peers' task entries as well as mine -> included in the allowlist anyway, because completion-handler must write the completion into it and excluding it would mean the task record never lands (tie-break: take the reversible option).
- [x] **P1-ENG-GX63** Phase 2: Nightly wiring and end-to-end tests (paper night, paper_check, promote)
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `commands/paper.py` only among sources: private `_resize_only` and `_split_inputs`; `_start`/`_step_book` pass, for split rules only, `last_rank` = `rank_basket(store.read_book_targets(... last_rank_session(...)))` and `marks` from the settled book; evidence None on a resize-only decision; rules without `resize_cadence` call `decide_book` exactly as today. New `engine/tests/test_paper_split_cadence.py`: a scripted `monthly-rank-weekly-resize-frac` entry over 20 Postgres nights (mid-month kickoff, resize weeks, catch-up across a rank, a 2:1 split on a resize Monday, a stopped-out position never re-bought) equal to `run_rules`, `paper_check` ok/split-affected never mismatch; and `promote --fractional` of `M0022-W-TV14` (RESOLVER/EVIDENCE via monkeypatch only) then 25 nights to a green `paper_check`. Does not touch `paper/book.py`, `paper/replay.py`, `paper/store.py`, `commands/promote.py`, existing tests, web, roster or `PAPER_PAUSED`. Exit: split-cadence entry paper-trades end to end equal to `run_rules`/`run_book`; resize-only decisions carry no evidence; promote writes `rules_id = 'monthly-rank-weekly-resize-frac'` and trades to a green `paper_check`; every existing test unedited and green.
  - **Status**: completed
  - **Plan Set**: `PAPER_SPLIT_CADENCE_PLAN.md` (phase 2 of 3)
  - **Satisfies**: R1, R2, R3, R7 — split-cadence decisions wired into the paper night with the last rank basket read back from `book_targets` (no migration); replay agrees over many nights; promote accepts only what paper runs and paper runs all it accepts
  - **Depends on**: P1-ENG-Q47S
  - **Plan**: `.workflows/plan/P1-ENG-GX63.md`
  - **Completed**: 2026-10-07 01:58
  - **Method**: /do
  - **Files**: engine/src/seer_engine/commands/paper.py, engine/tests/test_paper_split_cadence.py
- [x] **P1-ENG-Q47S** Phase 1: Pure split-cadence decision, replay and fractional preset
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `sim/rules.py` + `sim/__init__.py` (new `MONTHLY_RANK_WEEKLY_RESIZE_FRAC`, appended last to `PRESETS`, exported); `paper/book.py` (`decide_book(..., *, force=False, last_rank=None, marks=None)`, refusal removed, `needs_kickoff` on `is_rank_session`, pure helpers `last_rank_session` and `rank_basket`); `paper/replay.py` (`expected_book` tracks the expected last rank basket and marks); unit tests in `test_paper_book.py`, `test_paper_kickoff.py`, `test_sim_rules.py`, `test_promote_command.py`, `test_paper_replay.py`. Does not touch `commands/paper.py`, `paper/store.py`, web. Exit: a night-by-night `decide_book`/`settle_book` loop over a split-cadence rule set reproduces `run_book` field for field (resize weeks, mid-month kickoff, stopped-out position not re-bought, idle instrument); `expected_book` decisions equal that loop; `fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE)` is the new preset; full engine suite green; rule sets without `resize_cadence` byte for byte unchanged.
  - **Status**: completed
  - **Plan Set**: `PAPER_SPLIT_CADENCE_PLAN.md` (phase 1 of 3)
  - **Satisfies**: R1, R3, R5 — `decide_book` accepts split-cadence rules (resize-only session returns `run_book`'s `_with_idle(_rescaled(...))`, stays pure); replay agrees; `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` appended to `PRESETS` and `promote --fractional` maps to it
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-Q47S.md`
  - **Completed**: 2026-10-07 01:51
  - **Method**: /do
  - **Files**: engine/src/seer_engine/sim/rules.py, engine/src/seer_engine/sim/__init__.py, engine/src/seer_engine/paper/book.py, engine/src/seer_engine/paper/replay.py, engine/tests/test_paper_book.py, engine/tests/test_paper_kickoff.py, engine/tests/test_paper_replay.py, engine/tests/test_sim_rules.py, engine/tests/test_promote_command.py
- [x] **P1-ENG-Q0OH** Phase 3: Explain from evidence, with checks
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `commands/explain.py` (K3: prompt from facts + strategy plain name, `thinking="disabled"`, temperature 0, `EXPLAIN_MAX_TOKENS`, `accept()` checks), `tests/test_explain.py`, `tests/test_paper_c.py:490` (one assertion), `llm.py` docstrings, `docs/runbooks/paper-trading.md` (Explain section, Paper evidence and Explain lines) and `engine/package_readme.md` (pipeline overview, migration 009, promote's third condition). Exit: prompt built from evidence only; accept() rejects invented numbers, cut-off text, >2 sentences, banned phrases, duplicates; no "…"; entries without evidence skipped; always exit 0; phase 1's exact fact shapes pass `vet`.
  - **Status**: completed
  - **Plan Set**: `WHY_THIS_PICK_PIPELINE_PLAN.md` (phase 3 of 5)
  - **Satisfies**: R2, R3, R4, R8 — Explain passes those facts to the LLM → 1–2 plain sentences per pick, distinct per stock; Facts only, no predictions, no buy advice; every number checked against the facts; failing text discarded; never fails the night; Fix today's bugs: boilerplate, NULL, truncated texts; Plain words for a non-trader; no ids/codes on the site
  - **Depends on**: P1-ENG-H5LC
  - **Plan**: `.workflows/plan/P1-ENG-Q0OH.md`
  - **Completed**: 2026-10-06 22:31
  - **Method**: /implement
  - **Files**: engine/src/seer_engine/commands/explain.py, engine/tests/test_explain.py, engine/tests/test_paper_c.py, engine/src/seer_engine/llm.py, docs/runbooks/paper-trading.md, engine/package_readme.md
  - **Drift**: Plan's test seed inserted the KO order at slot 5; orders.slot has CHECK (slot BETWEEN 1 AND 4). KO is on a different session (LAST), so it now uses slot 1 — same intent, valid row.
- [x] **P1-ENG-BZYN** Phase 4: Promote requires evidence
  - **Difficulty**: EASY
  - **Type**: Feature
  - **Context**: Owns the `commands/promote.py` gate (K4: exit 2 `NotPromotable` when `not evidence.has_evidence(name)`, one-line reason), `tests/test_promote_command.py`, and the explore skill's promotion rule (a promotable allocator needs an `EVIDENCE` entry and a `RESOLVER` entry); does not touch the evidence module contents, roster, lab methods or `engine/package_readme.md`. Exit: promoting a candidate whose object has no evidence exits 2 with a one-line reason; existing promote tests green.
  - **Status**: completed
  - **Plan Set**: `WHY_THIS_PICK_PIPELINE_PLAN.md` (phase 4 of 5)
  - **Satisfies**: R7 — Evidence is required before a lab method is promoted to the site
  - **Depends on**: P1-ENG-A1SZ
  - **Plan**: `.workflows/plan/P1-ENG-BZYN.md`
  - **Completed**: 2026-10-06 22:20
  - **Method**: /do
  - **Files**: engine/src/seer_engine/commands/promote.py, engine/tests/test_promote_command.py, .claude/skills/explore-and-experiment-new-method/SKILL.md
- [x] **P1-ENG-H5LC** Phase 2: Store evidence with every paper entry
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `db/migrations/009_evidence.sql` (nullable `evidence jsonb` on orders, book_targets, book_previews), keyword-only `evidence=None` params in `paper/store.py`, the catch-all evidence helper and calls in `commands/paper.py` (`_start`/`_step_bracket`, `_start`/`_step_book`), and `engine/tests/test_paper_evidence.py`; decisions, replay, explain, web, docs untouched. Exit: after a paper night every pending A and C order and every non-idle target/preview row has evidence (idle symbol NULL; TIMING-off night explains nothing); a raising evidence function leaves NULL and the night succeeds; `paper_check` green; existing paper tests unchanged and green.
  - **Status**: completed
  - **Plan Set**: `WHY_THIS_PICK_PIPELINE_PLAN.md` (phase 2 of 5)
  - **Satisfies**: R1, R6 — Every method that recommends stocks exposes per-pick evidence: the numbers its formula used; "Would pick now" rows get reasons too, if cheap
  - **Depends on**: P1-ENG-A1SZ
  - **Plan**: `.workflows/plan/P1-ENG-H5LC.md`
  - **Completed**: 2026-10-06 23:30
  - **Method**: /do
  - **Files**: db/migrations/009_evidence.sql, engine/src/seer_engine/paper/store.py, engine/src/seer_engine/commands/paper.py, engine/tests/test_paper_evidence.py
- [x] **P1-ENG-A1SZ** Phase 1: Pure evidence module
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new pure `engine/src/seer_engine/strategies/evidence.py` (K1: `Facts`, `EvidenceFn`, `EVIDENCE` keyed by RESOLVER names minus the benchmark, `evidence_for`, `has_evidence`, both reading `EVIDENCE` at call time) and `engine/tests/test_evidence.py`; touches no existing strategy, params, roster, paper, explain or web file. Exit: every non-benchmark RESOLVER object has an evidence function; tests show distinct facts per symbol on synthetic markets, plain wording (no "RSI", "SMA", ids, no Explain `BANNED` word; market filter says "hold", never "buy"), no look-ahead (facts identical when later bars are added), purity test green.
  - **Status**: completed
  - **Plan Set**: `WHY_THIS_PICK_PIPELINE_PLAN.md` (phase 1 of 5)
  - **Satisfies**: R1, R8 — Every method that recommends stocks exposes per-pick evidence: the numbers its formula used; Plain words for a non-trader; no ids/codes on the site
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-A1SZ.md`
  - **Completed**: 2026-10-06 22:05
  - **Method**: /do
  - **Files**: engine/src/seer_engine/strategies/evidence.py (new), engine/tests/test_evidence.py (new)
- [x] **P1-ENG-G4TQ** Phase 1: Content-based clobber guard on the build path
  - **Difficulty**: NORMAL
  - **Type**: Bug
  - **Context**: Owns `engine/src/seer_engine/commands/research_store.py` (content-based window check on the build path, additive to the two existing `_same_dir` name checks, plus the module docstring's two-stores paragraph), `engine/tests/test_research_test_store.py` (R1 cross-checkout refusal both directions, four fall-through shapes, R2 sibling-path regression tests), `engine/package_readme.md:2372`. Exit: cross-checkout wrong-window build exits 2 both directions; missing/empty/unparseable/same-window paths fall through; `test_research_test_store.py:449-452` passes unedited; sibling-path regression tests pass against unchanged sibling code; `pytest -q` in `engine/` green at 2480 passed, 360 skipped, 0 failed.
  - **Status**: completed
  - **Plan Set**: `RESEARCH_STORE_CLOBBER_GUARD_PLAN.md` (phase 1 of 1)
  - **Satisfies**: R1 — a `--test-window` build must refuse a dev store belonging to any checkout or worktree, and symmetrically for a dev build aimed at another checkout's test store; R2 — do it without weakening the guard that already works, with the sibling paths shown covered by regression test
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ENG-G4TQ.md`
  - **Completed**: 2026-10-06 14:53
  - **Method**: /implement
  - **Files**: engine/src/seer_engine/commands/research_store.py, engine/tests/test_research_test_store.py, engine/package_readme.md, engine/.workflows/todos.md, engine/.workflows/plan/P1-ENG-G4TQ.md, RESEARCH_STORE_CLOBBER_GUARD_PLAN.md
  - **Verified**: full engine suite 2480 passed, 360 skipped, 0 failed in 167s (baseline 2469/360; +11 is exactly this phase's new tests) — exit criterion 6, invariant 7. `test_research_test_store.py` alone 39 passed; `test_command_refuses_the_test_window_on_the_dev_store` passes UNEDITED in this worktree where `research.STORE_DIR` does not exist (invariant 3 / exit criterion 4); `test_research_store.py` + `test_fundamentals_coverage.py` + `test_lab_test_window.py` 89 passed, none edited; `ruff check engine/src engine/tests` clean. Invariant 1: main checkout's `engine/.research/manifest.json` still fingerprint `399d0d25…b07cf8` with 9 keys. Invariant 4: `lab/lab.sqlite` reads `dev|85`, no `test` row — no counted test-window look spent. Invariant 5: `engine/.research` not created in the worktree, `engine/.research-test` still absent on main.
  - **Drift**:
    - No code drift: every block the phase plan quoted matched the tree byte-for-byte and was applied as written.
    - The plan's manual check `git diff research_store.py | grep -c '^-'` expected ~7 and reads 3 (with the `---` header excluded). That is the plan's own grep arithmetic, not a behaviour difference: git coalesces the 4 unchanged leading lines of the rewritten docstring paragraph, so only its last 3 prose lines are deletions. Verified by inspection — the 3 deleted lines are all docstring text, and no code line is deleted anywhere in the diff.
  - **Decided**:
    - The executor reported no decisions; the plan's three forks were all settled at /analyze time and recorded in the plan index's Decisions table.
    - Completion: the `[x]` block MOVED into `## Completed Tasks` rather than left in place. The in-place precedent recorded by the ROSTER_PROMOTION_PIPELINE / FUNDAMENTAL_PANEL_COVERAGE / BUILD_PROMOTION_PATH phases exists to protect concurrent peers appending to this same file in a shared worktree; this set has one phase and no peers, so the reason for the exception is absent and the default applies.
    - Completion: `**Method**: /implement`, not `/do` — the set was executed via `/implement -f RESEARCH_STORE_CLOBBER_GUARD_PLAN.md --phase 1`, which is what the plan index's Next block prescribes and what every other plan-set phase in this file records.
- [x] **P1-ENG-22VQ** Phase 4: `fundamentals` command — resumable ingest
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `seer_engine/commands/fundamentals.py` and `engine/tests/test_fundamentals_command.py`, including `sync_ticker_cik` — the one writer of the `ticker_cik` table from phase 1's CSV. Does not touch `cli.py` (discovery is automatic), the backtest, `engine/data/*`, `db/migrations/*`, the runbook; it imports the ingest tag allowlist as `fundamentals.ladder.LADDER_TAGS` from phase 5's pure package and derives nothing itself. Exit: `python -m seer_engine fundamentals` loads facts for every ever-member the scope predicate selects (795 on 2026-10-05, SPY excluded), resolved through phase 1's map by date, writing facts and `fundamentals_log` rows in one transaction per batch. The unit of work is the CIK, not the symbol: `plan_jobs` resolves every in-scope symbol, groups by CIK, and skips CIKs already logged, so a share-class pair (GOOG/GOOGL) is one `companyfacts` call, one log row and one `rows` count — but both symbols still appear in the summary via `CikResult.per_symbol()`. `batch_size` counts CIKs; `--symbols` dedupes to CIKs but ignores the log outright; `--retry-failed` re-attempts `failed` and `empty` CIKs; `--dry-run` rolls everything back. `Summary.exit_code` is unchanged from `backfill`'s: 0 when nothing failed, 1 on any failure, 2 on a missing setting or an empty universe — an `empty` filer is not an error. A symbol with no CIK gets no log row at all and is re-evaluated every run; a symbol missing from the map is `failed` by design, so an incomplete CSV exits 1, while a symbol the map marks `NONE` is `empty` and exits 0.
  - **Status**: completed
  - **Plan Set**: `EDGAR_FUNDAMENTALS_PLAN.md` (phase 4 of 7)
  - **Satisfies**: R1 — ticker → CIK bridge, vendored as `engine/data/ticker_cik.csv`, keyed so a recycled ticker can never resolve to the wrong company; R2 — Bulk ingest of SEC XBRL facts, `filed` as the no-look-ahead boundary, restatements kept queryable; R5 — New resumable `seer_engine` command respecting SEC fair access (User-Agent, 10 req/s)
  - **Depends on**: P1-ENG-R7TL, P1-ENG-FPIL, P1-ENG-0351, P1-ENG-9U93
  - **Plan**: `.workflows/plan/P1-ENG-22VQ.md`
  - **Completed**: 2026-10-05 11:00
  - **Method**: /implement
  - **Commit**: 886c7ad
  - **Files**: engine/src/seer_engine/commands/fundamentals.py, engine/tests/test_fundamentals_command.py
  - **Drift**:
    - No drift in any cross-phase contract. C1-C8 were each re-verified against the landed code before the first edit: `cik.CikRow` exposes `.symbol`/`.company_name`, `sec.Fact` carries `period_start`/`frame`, `sec.CompanyFacts` wraps `.facts`, `ladder.LADDER_TAGS` is a 19-pair frozenset, `005_fundamentals.sql` has no `frame` column and keys `fundamentals_log` by `cik`. The module and tests came out of the plan's code blocks essentially verbatim.
    - One plan bug, test-only: Step 11's `seed_universe` calls `conn.executemany`, which psycopg3 `Connection` does not have (only `Cursor` does). Fixed to `with conn.cursor() as cur: cur.executemany(...)`, the shape `test_backtest_io.py:51` already uses.
    - Live `python -m seer_engine fundamentals` against data.sec.gov was not exercised: this host has no `.env`, so neither `SEC_CONTACT_EMAIL` nor `DATABASE_URL_UNPOOLED` is set, and the coordinator ruled the exit criteria are not gated on a live run. The missing-setting path was verified instead (exit 2). Exit criteria 1-4 and 6 are the operator's first real run, once phases 1 and 4 are both on the branch (C8).
  - **Decided**:
    - `run()` reads the contact through `sec.require_contact()` inside `try/except config.ConfigError -> return 2`, not Step 4's bare `config.require("SEC_CONTACT_EMAIL")` (rung 3: C4, a reconciled contract in the same plan, names `sec.require_contact()` as the accessor; rung 6: `commands/nightly.py:76-80` is the identical shape for `MASSIVE_API_KEY`). Behaviour is unchanged either way -- `cli.main` maps `ConfigError` to 2 -- but the error now names the setting before a connection is opened.
    - Kept Step 7's `except sec.SecNotFound -> STATUS_EMPTY` branch, against the Impact paragraph two lines below it which says SecNotFound "is not special cased here" (rung 3: the step's own code block has the branch, and C4 states 404 -> `empty`). The prose is the stale half.
    - Committed the two files by literal path from the main context instead of delegating `git add` to a `pusher` subagent (rung 6 / narrower blast radius, on the coordinator's shared-worktree ruling: phase 7's `f_fundamental.py`, `m0005_fundamental_factors.py` and a modified `test_lab_methods.py` were uncommitted in this tree while this phase committed). `git show --stat 886c7ad` confirms exactly 2 files.
    - `readme-updater` skipped, same precedent as P1-ENG-R7TL and P1-ENG-DKWU: `engine/package_readme.md` is a shared file and phase 7 is live in this worktree, and phase 7 already owns the `fundamentals` rows in `docs/runbooks/data-pipeline.md` (H5), which is where this command's contract is documented.
- [x] **P1-ENG-R7TL** Phase 1: Vendored ticker→CIK map and loader
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/data/ticker_cik.csv` (generated once and committed), its documentation block in `engine/data/SOURCES.md`, a new `seer_engine/cik.py` loader validating it in the style of `membership.load_aliases`, `engine/scripts/build_ticker_cik.py` (the committed one-off generator, a new directory linted by `ruff check engine`), and `engine/tests/test_cik.py`. Does not touch the database or the `ticker_cik` table (phase 2 declares it, phase 4 writes it), the SEC client, any command, `.env.example`. Exit: the CSV covers every ever-member the scope predicate selects (795 on 2026-10-05; tests derive the set from `membership.symbols_since(...)` and never assert a literal count) with explicit validity intervals; the loader rejects a bad header, an overlapping interval for one ticker, and a CIK that is not 10 digits; a test asserts each of CA, MON, PLL, ALTR, LLL and DTV resolves to the company that held the ticker during its S&P/NDX membership and not to the current holder; Kellanova resolves to `0000055067`, with a test pinning that `0000039899` (TEGNA) is not it.
  - **Status**: completed
  - **Plan Set**: `EDGAR_FUNDAMENTALS_PLAN.md` (phase 1 of 7)
  - **Satisfies**: R1 — ticker → CIK bridge, vendored as `engine/data/ticker_cik.csv`, keyed so a recycled ticker can never resolve to the wrong company
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-R7TL.md`
  - **Completed**: 2026-10-05 11:12
  - **Method**: /implement
  - **Files**: engine/data/ticker_cik.csv, engine/data/SOURCES.md, engine/src/seer_engine/cik.py, engine/tests/test_cik.py, engine/scripts/build_ticker_cik.py
  - **Drift**:
    - No drift from the plan. Every API it quotes (`membership.Interval`/`normalize_ticker`/`symbols_since`, `http.get_json`'s retries+backoff kwargs, `SOURCES.md` lines 3-5 and its 139-line tail) matched the tree exactly. `cik.py` and `test_cik.py` were extracted verbatim from the plan's code blocks.
    - Generator needed 3 passes, as the plan predicted. Tiers resolved more than measured: 33 unresolved (plan predicted 93), then the periodic-filing screen caught 37 more.
  - **Decided**:
    - `SEC_CONTACT_EMAIL` for the generator -> mahfuzh74@gmail.com (rung 6, surrounding convention: SEC fair access requires a real contact in the User-Agent; the repo's own git config user.email is the in-tree answer). Passed via the environment only, never committed; phase 3 owns the `config.py` setting.
    - Generator's filing screen now skips `NO_FILER` rows (rung 2: exit criteria require the CSV to cover every ever-member, and the index's Decisions table defines `NONE` as the answer for a symbol with no EDGAR filer; the plan's code block would have crashed fetching `CIKNONE.json`, so it never encoded the path its own Step 3 prose requires).
    - Added `SCREEN_EXEMPT` to the generator: 11 symbols whose absence of a periodic filing was hand-verified and explained in code (rung 2 + the plan's own "a net, not a gate"). Without it a CORRECT file could never make the generator exit 0. Three recurring reasons: a bank rather than a bank holding company files periodic reports with the FDIC under Exchange Act s12(i), never EDGAR (FRC, SBNY); a short span ends before the next 10-K falls due (SWY 25 days, PETM 10 weeks, FCPT 7 days, VSNT 4 days); a current member's span opened weeks ago (BE, NBIS, P, RDDT, VMRK).
    - 70 hand-audited `MANUAL` rows, each verified against `data.sec.gov/submissions` with its evidence in the CSV's note column: 9 seeded + 33 that reached no automated tier + 27 the screen caught + HAR.
    - HAR: the single fuzzy-tier row was WRONG and the screen passed it — `difflib` matched Massive's "Harman International Industries" to "AMERICAN INTERNATIONAL INDUSTRIES" (`0001073146`), an unrelated company that filed 4 periodic reports inside the span. Corrected to `0000800459`. The file now has ZERO fuzzy rows.
    - Hand-audit recorded in `SOURCES.md` as method + categories + counts, pointing at the CSV's mandatory note column for per-row evidence, rather than duplicating 70 rows into prose (tie-break: one owner per concept — a second copy can only drift).
    - readme-updater -> skipped for this phase; `engine/package_readme.md` holds phase 6's uncommitted edits and phase 1 ships a vendored data file plus a pure loader, both documented in `engine/data/SOURCES.md`, which phase 1 owns (same precedent as P1-ENG-DKWU).
- [x] **P1-ENG-0LUS** Phase 6: `Market.fundamentals` + the `MarketAware` hook
  - **Difficulty**: HARD
  - **Type**: Update
  - **Context**: Owns the new `fundamentals` field on `Market`, the panel load in `backtest/io.py` (cached by table fingerprint like `bars`, reading `fundamental_facts` joined to `ticker_cik` because facts are CIK-keyed and the panel is symbol-keyed), the `MarketAware` protocol + `prepare_for` helper, the single real call site `dev.py:455`, the two docstrings at `runner.py:143` and `walkforward.py:200`, every other place a `Market` is constructed and would silently drop the new field (`dev.py:367`, `research.py:472`, `paper/replay.py:281`, `commands/paper.py:254`) — including the research store's optional `fundamentals.csv` artifact (`research.py`, `commands/research_store.py` + a new `--with-fundamentals` flag), without which the lab sees an empty panel — and `engine/tests/test_market_fundamentals.py`. Does not touch the existing allocators' behaviour, `Allocator`'s member set (which must not gain `prepare_market`), `test_strategy_purity.py`, `test_lab_methods.py`, `research.DATA_FILES` or `engine/tests/test_research_store.py` — the new store file is optional, carried in `OPTIONAL_DATA_FILES`. Exit: `Market` stays frozen and pure; `load_market` returns a panel and still works against a database with neither `fundamental_facts` nor `ticker_cik`; `isinstance(x, Allocator)` is still True for all eleven existing implementers; `test_strategy_purity.py` is byte-identical to what phase 5 left and so is `test_research_store.py`; a store rebuilt with `--with-fundamentals` carries a panel equal to `io.load_panel(conn)`'s, and a store built before this phase still loads with the same fingerprint `origin/main` computes for it; every existing backtest produces byte-identical output to `origin/main` for one pinned candidate.
  - **Status**: completed
  - **Plan Set**: `EDGAR_FUNDAMENTALS_PLAN.md` (phase 6 of 7)
  - **Satisfies**: R6 — Factor exposure to the lab: value, quality, profitability, SUE; consensus surprise out of scope
  - **Depends on**: P1-ENG-FPIL, P1-ENG-9U93
  - **Plan**: `.workflows/plan/P1-ENG-0LUS.md`
  - **Completed**: 2026-10-05 10:37
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/market.py, engine/src/seer_engine/backtest/io.py, engine/src/seer_engine/strategies/allocator.py, engine/src/seer_engine/backtest/dev.py, engine/src/seer_engine/backtest/runner.py, engine/src/seer_engine/backtest/walkforward.py, engine/src/seer_engine/research.py, engine/src/seer_engine/commands/research_store.py, engine/src/seer_engine/paper/replay.py, engine/src/seer_engine/commands/paper.py, engine/tests/test_market_fundamentals.py
  - **Drift**:
    - `seer_engine.fundamentals.FundamentalPanel` is `@dataclass(frozen=True, eq=False)` by phase 5, so `panel_a == panel_b` is identity, not value equality. The plan's test block asserted panel equality twice. Phase 5 owns that type and this phase must not edit it, so the tests compare the per-symbol `Fact` tuples through a local `panel_facts()` helper instead (`Fact` is a plain frozen dataclass with value equality).
    - `engine/tests/test_research_store.py::test_no_neon_and_no_database_url_needed` AST-scans BOTH `research.py` AND `commands/research_store.py` and fails either one that names `seer_engine.db` or `psycopg`. The plan's Step 7 item 8 put `db.connect()` inside `commands/research_store.py`, which turned that test RED. That file is byte-identical shipped code with no owner in this plan set, and phase 6's own exit criterion 6 requires it stay untouched and green.
    - The plan's test block had two self-inconsistent assertions, both corrected: (a) `facts_fingerprint()` leaves an implicit transaction open, so the `load_market()` call right after it raised "needs a connection with no transaction in progress"; (b) the stale-pickle test seeded a new fact filed 2016-04-27, EARLIER than the already-seeded max filed of 2017-03-01, so `max(filed)` never moved and the asserted pickle name was unreachable.
    - No pre-existing research store exists anywhere on this machine, so the plan's "load `/home/miftah/seer/engine/.research`" check was run instead as a cross-checkout equivalent: a four-file store built by the `origin/main` checkout, then loaded by both checkouts.
    - The plan's pinned-candidate diff reads a research store that does not exist and whose real build needs hours of yfinance downloads. It was run instead over a deterministic synthetic market generated identically in both checkouts — a real ~19-year `F4-MOM12-N10-TREND` backtest through `dev.run_registry`, i.e. through the exact line this phase changed.
  - **Decided**:
    - `FundamentalPanel` is `eq=False` and phase 5 owns it -> compare per-symbol `Fact` tuples rather than panels, and do not add `__eq__` to phase 5's type (rung 2: exit criterion 7's "facts equal to `io.load_panel(conn)`'s … a round-trip assertion" means value equality of the facts, which `Fact` already has)
    - Where the `--with-fundamentals` database connection lives: the plan said `commands/research_store.py`, but that makes the unowned, byte-identical `test_research_store.py` fail -> moved into `backtest/io.py` as `io.read_facts()`, the tree's declared impure backtest edge that `test_strategy_purity.py` skips by name (rung 2: phase 6's exit criterion 6, "`test_research_store.py` byte-identical and green", outranks rung 3's placement of the call). `research.py` still imports nothing from `seer_engine.db`, so the "Never Neon" invariant the Decisions table protects is intact, and `build_store` still takes a plain facts sequence.
    - The stale-pickle test's new fact re-dated 2016-04-27 -> 2017-04-27 so that `max(filed)` actually advances (rung 2: the exit criterion is that a NEW fingerprint sweeps the stale pickle; the fix preserves and strengthens the check rather than relaxing it)
    - `fundamentals.csv` is NOT clipped at `DEV_END` the way bars/dividends/fx are (rung 2: exit criterion 7 requires the store panel equal the database panel; look-ahead is already prevented downstream by phase 5's `as_of(symbol, t)`, which exposes only `filed <= t`)
- [x] **P1-ENG-9U93** Phase 5: Pure derivation: concept ladder, PIT selection, SUE
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `seer_engine/fundamentals/` (`__init__.py`, `ladder.py`, `panel.py`, `sue.py`), `engine/tests/test_fundamentals_derive.py`, and the additive extension of `engine/tests/test_strategy_purity.py`'s glob to cover the new package — it is the sole owner of that shared test file, which phase 6 must leave byte-identical. It also owns `ladder.LADDER_TAGS`, which phase 4 imports as the ingest allowlist, so a rung added here later costs a full re-ingest and `ladder.py`'s docstring must say so. Does not touch the database, the network, `Market`, any allocator. Exit: the concept ladder reproduces the measured coverage over the 8 sampled filers (revenue 2 variants; net income, assets, equity, OCF, diluted EPS, shares outstanding 1 each; operating income missing for SIVB and PXD; gross profit present only for CELG and WRK, derived as `Revenues − CostOfRevenue` elsewhere with the fallback documented in the module docstring); point-in-time selection returns the latest fact with `filed <= t`, proven by a test on a real restatement; SUE is the seasonal random walk `EPS_q − EPS_{q−4}` scaled by the dispersion of recent surprises, with the minimum history it needs stated and enforced.
  - **Status**: completed
  - **Plan Set**: `EDGAR_FUNDAMENTALS_PLAN.md` (phase 5 of 7)
  - **Satisfies**: R3 — Concept ladder over the measured tag variants, gross profit derived with a documented fallback
  - **Depends on**: P1-ENG-FPIL
  - **Plan**: `.workflows/plan/P1-ENG-9U93.md`
  - **Completed**: 2026-10-05 10:04
  - **Method**: /do
  - **Files**: engine/src/seer_engine/fundamentals/__init__.py, engine/src/seer_engine/fundamentals/ladder.py, engine/src/seer_engine/fundamentals/panel.py, engine/src/seer_engine/fundamentals/sue.py, engine/tests/test_fundamentals_derive.py, engine/tests/test_strategy_purity.py
  - **Drift**:
    - None. `test_strategy_purity.py` matched the plan exactly at lines 1-6, 34 and 60-72; the glob extension was the three additive edits the plan specified.
    - The 31 errors in the full-suite run are all `engine/tests/test_cik.py` (FileNotFoundError on the vendored CSV phase 1 has not finished generating). Zero failures, zero non-cik errors; the swarm coordinator ruled in advance that these belong to phase 1.
  - **Decided**:
    - `ladder.py`'s docstring said "revising it needs no re-ingest", while the plan's reconciled input contract and the plan index's Phase 5 Owns both require it to state that adding a rung costs a full re-ingest. The docstring now carries both precisely: reordering or dropping rungs among already-ingested tags is free; adding a NEW tag rung is not, because `LADDER_TAGS` is also phase 4's ingest allowlist — and the re-ingest recipe is spelled out. (Rung 4: the plan index's Phase 5 Owns outranks the stale prose inside the code block.)
- [x] **P1-ENG-FPIL** Phase 2: Schema: `ticker_cik`, `fundamental_facts`, `fundamentals_log`
  - **Difficulty**: EASY
  - **Type**: Feature
  - **Context**: Owns `db/migrations/005_fundamentals.sql` and the two `test_migrate.py` assertions that assume 004 is the last migration (`:300` and `:318`, repointed at `_upto(tmp_path, "004_news_veto.sql")`) plus the new 005 block; no other phase touches `engine/tests/test_migrate.py`. Does not touch any `engine/src` Python or `docs/runbooks/data-pipeline.md` (phase 7 owns it entirely). Exit: `migrate` applies it cleanly and is idempotent; `fundamental_facts`'s primary key is `(cik, taxonomy, tag, unit, period_start, period_end, accn)` — `accn` so a restatement inserts rather than overwrites, `period_start` so a 10-K's Q4 figure cannot collide with its full-year figure; `period_start` is `NOT NULL` with `period_start = period_end` meaning instantaneous; `fundamentals_log` mirrors `backfill_log`'s shape but is keyed by `cik` (invariant 4); `ticker_cik.source`'s CHECK matches phase 1's tier labels; every table is additive (`CREATE TABLE IF NOT EXISTS`) in the style of `002_engine.sql`; `test_migrate.py` is green.
  - **Status**: completed
  - **Plan Set**: `EDGAR_FUNDAMENTALS_PLAN.md` (phase 2 of 7)
  - **Satisfies**: R4 — Postgres schema + migration consistent with `bars`/`universe`/`dividends`/`split_adjustments`
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-FPIL.md`
  - **Completed**: 2026-10-05 09:40
  - **Method**: /do
  - **Files**: db/migrations/005_fundamentals.sql, engine/tests/test_migrate.py
  - **Drift**:
    - Plan Step 2's code block calls `_upto(tmp_path, '004_news_veto.sql')` twice in one test; `_upto` does a bare `mkdir()` so the second call raised FileExistsError. The plan's prose claimed the two calls get different directories — that was wrong, the directory name is keyed only on `last`. Bound the directory to a local and reused it.
    - The worktree had no `engine/.venv`; created one (python 3.12.7, `pip install -e 'engine[dev]'`) rather than using the main checkout's editable install.
    - No `seer-pg` test container existed; started one per `docs/runbooks/data-pipeline.md:238` (postgres:16 on 55432).
    - The plan's manual check against the real database was not run — no `.env` / `DATABASE_URL_UNPOOLED` is reachable from this worktree.
  - **Decided**:
    - Plan Step 2's duplicate `_upto` call -> bind the directory to a local and reuse it, rather than making the shared `_upto` helper idempotent (rung 3: the phase plan's code block is the authority on intent; the plan also says nothing else in the file moves)
    - Manual `migrate` against the real Neon DB -> skipped; exit criterion 1 is proven by `test_005_is_applied_last_and_only_once` and `test_005_sql_is_idempotent` against a real Postgres 16 (rung 2: the exit criteria name the tests)
    - Verification interpreter -> the worktree's own `engine/.venv`, created here (rung 6: surrounding convention, which states never to test a worktree with `/home/miftah/seer/engine/.venv`)
- [x] **P1-ENG-0351** Phase 3: SEC client (`sec.py`) and `SEC_CONTACT_EMAIL`
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `seer_engine/sec.py`, the `SEC_CONTACT_EMAIL` key in `.env.example` (the only phase that edits that file), and `engine/tests/test_sec.py`; `config.py` is not edited — it exposes no named accessors, so `sec.require_contact()` is the local accessor exactly as `finnhub.load_key` is. Does not touch `http.py`'s module-level session (Massive and Finnhub must not inherit the contact User-Agent), the database, the command module. Exit: the client fetches `companyfacts/CIK##########.json`, enforces ≤ 10 req/s from the end of the previous call, sends a `User-Agent` carrying `SEC_CONTACT_EMAIL`, retries 429/5xx with backoff honouring `Retry-After`, raises a typed error otherwise, and takes an injectable transport/clock/sleep so tests never touch the network.
  - **Status**: completed
  - **Plan Set**: `EDGAR_FUNDAMENTALS_PLAN.md` (phase 3 of 7)
  - **Satisfies**: R2 — Bulk ingest of SEC XBRL facts, `filed` as the no-look-ahead boundary, restatements kept queryable; R5 — New resumable `seer_engine` command respecting SEC fair access (User-Agent, 10 req/s)
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-0351.md`
  - **Completed**: 2026-10-05 09:40
  - **Method**: /do
  - **Files**: engine/src/seer_engine/sec.py, engine/tests/test_sec.py, .env.example
  - **Drift**: none — the tree matched every line the plan quoted: `.env.example` ended at line 21 on `FINNHUB_API_KEY=`, `http.py` had `redact`/`_session`/`USER_AGENT`/`HttpError(message, status)`, `config.py` had `require`/`ConfigError`/`_loaded`, `__version__ == 0.1.0`
  - **Decided**:
    - `test_first_call_does_not_wait_and_calls_are_spaced_by_min_interval` asserted `clock.sleeps == [0.11, 0.11]`, but a wait is computed as `last + MIN_INTERVAL - now` and lands at 0.10999999999999943 -> both expected values wrapped in `pytest.approx` (rung 3, the plan's own code blocks: the sibling test two functions below already uses `pytest.approx(sec.MIN_INTERVAL - 0.04)` for the identical arithmetic). What is asserted — two waits, each one MIN_INTERVAL — is unchanged
    - Step 3 created a task for phase 3 only, not all seven (rung 6 / narrower blast radius: phases 1 and 2 are live in this same worktree and six of seven phases map to this file, so three sessions minting from one counter would be a lost-update race). A sibling had already booked all seven; deferred to its published P1-ENG-0351
    - readme-updater not dispatched: `engine/package_readme.md` is shared with two live sibling phases, and phase 3's Files table names exactly three files. Phase 7 owns the runbook line for `SEC_CONTACT_EMAIL` per this plan's Handoffs
- [x] **P1-ENG-6QQA** Phase 1: Lab snapshot export + synthesis kind
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/lab/store.py` (schema v2: `synthesis` insight kind via a `connect()`-time migration rebuilding `insights` with the new CHECK, copying rows, recreating triggers, `schema_version='2'`; plus `snapshot(conn)` / `snapshot_json(conn)` per the index's `web/data/lab.json` Interface Contract), `lab/seed.py` (store-fact constants + benchmark curve reader), `commands/lab.py` (`lab export-json [--out web/data/lab.json]`; `lab stage` also writes the snapshot under the same exclusive lock and `git add`s both files), new `tests/test_lab_snapshot.py` (migration, determinism, contract shape, CLI, sync guard), and the generated `web/data/lab.json` + migrated `lab/lab.sqlite`. Does not touch `web/` code, skills, CI. Exit: `python -m seer_engine lab export-json` reproduces the committed `web/data/lab.json` byte for byte; `lab insight --kind synthesis` works; all engine tests green.
  - **Status**: completed
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 1 of 7)
  - **Satisfies**: R3 — Show every experiment, as detailed as possible, kept current with no human step; R6 — Insights from every exploration; food for thought on features and data sources; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-6QQA.md`
  - **Completed**: 2026-10-04 22:20
  - **Method**: /do
  - **Files**: engine/src/seer_engine/lab/store.py, engine/src/seer_engine/lab/seed.py, engine/src/seer_engine/commands/lab.py, engine/tests/test_lab_snapshot.py, lab/lab.sqlite, web/data/lab.json
  - **Decided**:
    - Step 3 task creation in a concurrent swarm -> phase 1's session created all 7 tasks (repo precedent; phase 3 runs concurrently in the same worktree)
    - readme-updater -> skip: engine/package_readme.md does not document the lab CLI (plan reconciliation row 16); lab docs (web/package_readme.md, ROADMAP) are owned by phase 7 (rung 4: index scope)
- [x] **P1-ENG-QRXI** Phase 4: `veto` command
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/commands/veto.py` (K6, incl. the H1 guard) + `engine/tests/test_veto_command.py` (27 tests; PG + fake Finnhub/LLM injected through `execute(conn, *, now, dry_run, finnhub=..., llm=...)` factories). Does not touch: `paper.py`, `paper_check.py`, store (calls K3 only), `test_paper_command.py` (imports its helpers), workflow, docs. Exit: tests for each acceptance-3 failure (no LLM config, timeout/HTTP error, unparsable, Finnhub error, no Finnhub key, model mismatch, consecutive-failure stop); look-ahead (news at/after start never in the prompt or stored; bars dated ≥ session never change candidates); idempotent re-run makes zero client calls and writes nothing; **after Paper decided the session (late-verdict retry) no client call, no row, and C's `paper_check` stays ok; Paper deciding during the checks → the write transaction writes nothing**; failed/missing bars run → exit 1, nothing written; `--dry-run` writes nothing; no secret in rows or logs; LLM options are `float(params.temperature)`, `params.thinking`, `params.max_tokens`.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_C_NEWS_VETO_PLAN.md` (phase 4 of 7)
  - **Satisfies**: R2 — Engine, impure: Finnhub client, `veto` command (D6), migration `004` (D7), verdict store, `paper` deciding C, `paper_check` replaying C (D8), `explain` covering C
  - **Depends on**: P1-ENG-4I4B, P1-ENG-2548
  - **Plan**: `.workflows/plan/P1-ENG-QRXI.md`
  - **Completed**: 2026-10-04 18:21
  - **Method**: /do
  - **Files**: engine/src/seer_engine/commands/veto.py, engine/tests/test_veto_command.py
  - **Drift**: none — both files created verbatim from the phase plan's code blocks
  - **Decided**:
    - readme-updater -> skipped; engine/package_readme.md is owned by phase 7 (rung 1: plan invariant 9, file ownership). Same decision phase 3 recorded
    - commit scope -> only this phase's files + bookkeeping; the shared worktree holds uncommitted peer edits from phases 5 and 6 (rung 1: invariant 9)
    - plan index orchestration/strategy-c-news-veto/PLAN.md edited in place on the main checkout (Status line), not committed from this worktree (completion-handler)
  - **Verified**: test_veto_command.py 27 passed; full engine suite 2159 passed, 0 skipped; ruff clean; web vitest 83 passed + tsc clean
  - **Next**: P1-ROOT-ZEOM (phase 7) stays blocked: phase 5 is complete but P1-WEB-8YO3 (phase 6) is still in progress (completion-handler)

- [x] **P1-ENG-IIZE** Phase 5: `paper`, `paper_check`, `explain` decide and replay C
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `commands/paper.py` (K7: `_bracket_strategy`, `_start`, `_step_bracket`), `commands/paper_check.py` (K7: `_expected(conn, ...)`); new `engine/tests/test_paper_c.py` (14 tests, verdict rows via `store.write_vetoes`). Does not touch: `paper/*` cores, `replay.py`, store, `veto.py`, `explain.py`, `test_paper_command.py`, `test_paper_check.py` / `test_paper_store.py` (phase 2's edits stand), web. Exit: C starts on its first night with its own `paper_start` while the other four keep theirs; ≥ 5 synthetic nights → `paper_check` ok for all five; the replay really reads stored verdicts (flipping one → C mismatch); all-allow C orders == A orders; veto/failed/missing → no C order for that symbol and `paper` exit 0; catch-up night with verdicts only for the newest session; re-run writes nothing; the four existing strategies' rows identical with and without C; explain fills C's pending orders.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_C_NEWS_VETO_PLAN.md` (phase 5 of 7)
  - **Satisfies**: R2 — Engine, impure: Finnhub client, `veto` command (D6), migration `004` (D7), verdict store, `paper` deciding C, `paper_check` replaying C (D8), `explain` covering C
  - **Depends on**: P1-ENG-4I4B
  - **Plan**: `.workflows/plan/P1-ENG-IIZE.md`
  - **Completed**: 2026-10-04 18:19
  - **Method**: /do
  - **Files**: engine/src/seer_engine/commands/paper.py, engine/src/seer_engine/commands/paper_check.py, engine/tests/test_paper_c.py
  - **Drift**: none — plan applied verbatim; code matched the quoted lines
  - **Decided**:
    - readme-updater for phase 5 -> skipped; engine/package_readme.md is owned by phase 7 only (rung 1: invariant 9) (completion-handler)
    - plan index not ticked here; PLAN.md lives on main and is updated by swarm coordinator orch-strategy-c-news-veto when it records the phase (completion-handler)
  - **Verified**: full engine suite 2132 passed, 0 skipped; ruff clean; web vitest 83 passed + tsc clean
  - **Next**: P1-ROOT-ZEOM (phase 7) stays blocked: it still depends on P1-ENG-QRXI (phase 4) and P1-WEB-8YO3 (phase 6), both still in progress (completion-handler)

- [x] **P1-ENG-2548** Phase 3: Finnhub client and LLM call options
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/finnhub.py` (K5) + `engine/tests/test_finnhub.py` (fake transport/clock); `llm.py` keyword options (K5) + `test_llm.py` additions (body byte-identical without keywords; with them `temperature`, `thinking`, `max_tokens` present). Does not touch: commands (`explain` keeps calling `complete(system, prompt)`), store, web. Exit: spacing ≥ 1.0 s between any two requests, retries included; key only in a header and scrubbed from errors, logs and repr; one retry on connection error/timeout/429/5xx (Retry-After capped at 60 s), none on other 4xx; earnings earliest-in-window; tests green.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_C_NEWS_VETO_PLAN.md` (phase 3 of 7)
  - **Satisfies**: R2 — Engine, impure: Finnhub client, `veto` command (D6), migration `004` (D7), verdict store, `paper` deciding C, `paper_check` replaying C (D8), `explain` covering C
  - **Depends on**: P1-ENG-KIBJ
  - **Plan**: `.workflows/plan/P1-ENG-2548.md`
  - **Completed**: 2026-10-04 18:10
  - **Method**: /do
  - **Files**: engine/src/seer_engine/finnhub.py, engine/src/seer_engine/llm.py, engine/tests/test_finnhub.py, engine/tests/test_llm.py
  - **Decided**:
    - readme-updater for phase 3 -> skipped; engine/package_readme.md is owned by phase 7 only (rung 1: invariant 9) (completion-handler)
  - **Verified**: targeted test_finnhub/test_llm/test_strategy_purity/test_massive/test_http 85 passed (matches plan); full engine suite on HEAD + these 4 files 2079 passed, 0 skipped; ruff clean; web vitest 65 passed + tsc clean
  - **Next**: P1-ENG-QRXI (phase 4) unblocked: both its dependencies (P1-ENG-4I4B, P1-ENG-2548) are complete (completion-handler)

- [x] **P1-ENG-4I4B** Phase 2: Migration 004, roster entry C, verdict store
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `db/migrations/004_news_veto.sql` (K2, byte for byte); `paper/roster.py` (K4); `paper/store.py` (K3); `demo.py` (`news_vetoes` in `DEMO_TABLES`); tests `test_migrate.py` (003 tests pinned to a schema at 003; 004 fresh, post-003, restyle, idempotent, keys), `test_paper_roster.py` (C pin `6cea6cb8…b762`, display fields equal 004's row, the four pins unchanged, C's gate dict), `test_demo.py`, new `test_paper_store_vetoes.py`, and the one-line `"C"` edits in `test_paper_store.py:58` and `test_paper_check.py:51` (owned here so the phase is green alone). Does not touch: commands, workflows, web, docs. Exit: full engine suite green with 0 skipped; the four existing digests and gate dicts unchanged; `004` applies on a schema at 003 and is a no-op twice; C's pin passes (if it fails for C only, re-pin from the printed digest: C has never been frozen).
  - **Status**: completed
  - **Plan Set**: `STRATEGY_C_NEWS_VETO_PLAN.md` (phase 2 of 7)
  - **Satisfies**: R1 — Engine, pure: C strategy object, roster entry `C` with frozen spec (D5), prompt + JSON verdict parser; R2 — Engine, impure: Finnhub client, `veto` command (D6), migration `004` (D7), verdict store, `paper` deciding C, `paper_check` replaying C (D8), `explain` covering C
  - **Depends on**: P1-ENG-KIBJ
  - **Plan**: `.workflows/plan/P1-ENG-4I4B.md`
  - **Completed**: 2026-10-04 18:07
  - **Method**: /do
  - **Files**: db/migrations/004_news_veto.sql, engine/src/seer_engine/paper/roster.py, engine/src/seer_engine/paper/store.py, engine/src/seer_engine/demo.py, engine/tests/test_migrate.py, engine/tests/test_paper_roster.py, engine/tests/test_demo.py, engine/tests/test_paper_store_vetoes.py, engine/tests/test_paper_store.py, engine/tests/test_paper_check.py
  - **Decided**:
    - readme-updater for phase 2 -> skipped; engine/package_readme.md is owned by phase 7 only (rung 1: invariant 9) (completion-handler)
  - **Verified**: ruff clean; full engine suite 2118 passed, 0 skipped (319 s); web vitest 65 passed + tsc clean; 004 byte-identical to K2; C digest 6cea6cb8...b762 matches pin, four existing digests unchanged
  - **Next**: P1-ENG-IIZE (phase 5) and P1-WEB-8YO3 (phase 6) unblocked: both depend only on phase 2. P1-ENG-QRXI (phase 4) still waits on P1-ENG-2548 (phase 3) (completion-handler)

- [x] **P1-ENG-KIBJ** Phase 1: Pure C: strategy object, prompt, parser
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/strategies/c.py` (K1, entire); `engine/tests/test_strategy_c.py`. Does not touch: `strategies/a.py`, `strategies/__init__.py` (no re-export), roster, store, any command, web. Exit: with every candidate allowed, `NewsVeto.picks == candidates == STRATEGY_A.picks[:10]`; vetoed/failed/missing symbols removed, order kept; ranks > 10 never returned; `picks_prepared(prepare(H)) == picks(H cut)`; `run_rules(DESIGN_V0)` over a synthetic market with an all-allow map equals A's run where A never needs rank > 10; `select_headlines` drops items at/after the cutoff; `parse_verdict` table of cases; `user_prompt` golden text; purity green; prompt texts have no trailing newline and `as_dict` has exactly the 19 keys K1 lists (C's pin depends on them).
  - **Status**: completed
  - **Plan Set**: `STRATEGY_C_NEWS_VETO_PLAN.md` (phase 1 of 7)
  - **Satisfies**: R1 — Engine, pure: C strategy object, roster entry `C` with frozen spec (D5), prompt + JSON verdict parser
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-KIBJ.md`
  - **Completed**: 2026-10-04 17:57
  - **Method**: /implement
  - **Files**: engine/src/seer_engine/strategies/c.py, engine/tests/test_strategy_c.py
  - **Decided**:
    - readme-updater for phase 1 -> skipped; engine/package_readme.md is owned by phase 7 only (rung 1: invariant 9)
    - package for phases 1-5 tasks -> engine (ENG), phase 6 -> web, phase 7 -> root (rung 6: precedent of earlier plan sets)
    - web/node_modules missing in worktree -> ran npm ci (no tracked file changed) so invariant 1's vitest/tsc could run
  - **Verified**: test_strategy_c + test_strategy_purity 62 passed; full engine suite 2031 passed, 0 skipped; ruff clean; web vitest 65 passed, tsc clean
  - **Next**: P1-ENG-4I4B (phase 2) and P1-ENG-2548 (phase 3) unblocked: both depend only on phase 1 (completion-handler)

- [x] **P1-ENG-WBI7** Phase 8: `paper_check` replay check
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `paper/replay.py` (pure comparison), `commands/paper_check.py`; tests: after ≥ 5 nights of `paper` on synthetic data the check passes; a tampered snapshot/trade/position fails; a split on a held symbol reports "split-affected" without failing; `--require-sessions`. Does not touch: `commands/paper.py`, workflows (phase 13 adds the step), web. Exit: tests green.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 8 of 13)
  - **Satisfies**: R3 — Replay check (D7) + design §8 failure handling
  - **Depends on**: P1-ENG-0ZLD
  - **Plan**: `.workflows/plan/P1-ENG-WBI7.md`
  - **Completed**: 2026-10-04 10:13
  - **Method**: /do
  - **Files**: engine/src/seer_engine/paper/replay.py, engine/src/seer_engine/commands/paper_check.py, engine/tests/test_paper_replay.py, engine/tests/test_paper_check.py
  - **Decided**:
    - readme-updater -> skipped; engine/package_readme.md is owned by phase 13 only (plan invariant 8)
  - **Verified**: paper_check --help ok; focused 64 passed (39 + 25); full engine suite 1972 passed, 0 skipped; web vitest 65 passed
  - **Next**: P1-ROOT-FOK3 (phase 13) unblocked: phases 1-12 all complete (completion-handler)

- [x] **P1-ENG-0ZLD** Phase 7: `paper` command and workflow step
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `commands/paper.py` (calls only phase 1's roster API and phase 6's store API; the window is `store.market_window_since`; catch-up uses `night_view` for bars/FX and undoes later splits on dividends too; passes an applied SPY split to `step_benchmark(split=)`); `runs.py` paper status helpers; `.github/workflows/nightly.yml` "Paper" step after "Nightly"; PG integration tests with synthetic bars: init (paper_start = session_date, day-0 snapshot), ≥ 5 consecutive nights, idempotent re-run writes nothing, a failure leaves no partial state and marks `paper_status = failed`, failed/missing bars run → no paper step, no look-ahead (changing bars dated ≥ S leaves S's decisions unchanged), frozen-spec mismatch refused (`SpecMismatch`). Does not touch: `nightly.py`, `paper/*` cores and store (only calls them), `demo.py`, the job's `timeout-minutes`, web, docs. Exit: tests green; `--dry-run` writes nothing.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 7 of 13)
  - **Satisfies**: R1 — Engine paper step: pure core + impure command, per roster strategy per new session (state, splits, settle, dividends, force-close, decide, persist, SPY benchmark); R3 — Replay check (D7) + design §8 failure handling
  - **Depends on**: P1-ENG-X99Y, P1-ENG-AYRQ
  - **Plan**: `.workflows/plan/P1-ENG-0ZLD.md`
  - **Completed**: 2026-10-04 10:06
  - **Method**: /do
  - **Files**: engine/src/seer_engine/commands/paper.py, engine/src/seer_engine/runs.py, engine/tests/test_paper_command.py, engine/tests/test_runs.py, .github/workflows/nightly.yml
  - **Verified**: focused 25 passed; full engine suite 1908 passed, 0 skipped; web vitest 65 passed; nightly.yml parses with Paper step after Nightly
  - **Next**: P1-ENG-WBI7 (phase 8) unblocked (completion-handler)

- [x] **P1-ENG-AYRQ** Phase 6: Paper store (load and save state)
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `paper/store.py` (C4, the API listed there; `MARKET_WINDOW_DAYS = 550` is the only window constant in the set); `backtest/io.read_bars_frame(conn, *, since=None)` (default unchanged); PG round-trip tests for every engine's state, targets, fills, trades, snapshots, splits and dividends queries; windowed market load. Does not touch: commands, workflows, web, runners. Exit: save→load round trips are exact (Decimal, dates, ordering); `load_market` unchanged.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 6 of 13)
  - **Satisfies**: R1 — Engine paper step: pure core + impure command, per roster strategy per new session (state, splits, settle, dividends, force-close, decide, persist, SPY benchmark)
  - **Depends on**: P1-ENG-N6UC, P1-ENG-79OL, P1-ENG-1BVI
  - **Plan**: `.workflows/plan/P1-ENG-AYRQ.md`
  - **Completed**: 2026-10-04 09:58
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/io.py, engine/src/seer_engine/paper/store.py, engine/tests/test_paper_store.py
  - **Verified**: focused 41 passed; full engine suite 1891 passed, 0 skipped; web vitest 49 passed
  - **Next**: P1-ENG-0ZLD (phase 7) unblocked: P1-ENG-X99Y and P1-ENG-AYRQ both complete (completion-handler)

- [x] **P1-ENG-1BVI** Phase 4: Book night core
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `paper/book.py` (C3); tests proving `decide_book`+`settle_book` looped equal `run_book` for `MONTHLY_HOLD` with FACTOR and TIMING on synthetic markets (incl. dividends and a forced close), split on a held position and on pending targets, no look-ahead. Does not touch: `sim/*` (uses phase 2's `apply_book_split`), runners, DB. Exit: equality tests green; purity green.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 4 of 13)
  - **Satisfies**: R1 — Engine paper step: pure core + impure command, per roster strategy per new session (state, splits, settle, dividends, force-close, decide, persist, SPY benchmark)
  - **Depends on**: P1-ENG-N6UC, P1-ENG-HCYN
  - **Plan**: `.workflows/plan/P1-ENG-1BVI.md`
  - **Completed**: 2026-10-04 10:05
  - **Method**: /do
  - **Files**: engine/src/seer_engine/paper/book.py, engine/tests/test_paper_book.py
  - **Decided**:
    - Step 3 task creation -> skipped; phase 1's session already minted all 13 TaskIDs (phase 4 = P1-ENG-1BVI) (re-run detection per /implement Step 3)
    - readme-updater -> skip; engine/package_readme.md is owned by phase 13 only (rung 1: plan invariant 8)
  - **Verified**: focused 29 passed; purity 9 passed; full engine suite 1865 passed, 0 skipped; web vitest 44 passed
  - **Next**: P1-ENG-AYRQ (phase 6) unblocked: P1-ENG-N6UC, P1-ENG-79OL and P1-ENG-1BVI all complete (completion-handler)

- [x] **P1-ENG-79OL** Phase 3: Bracket and benchmark night cores
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `paper/bracket.py`, `paper/benchmark.py` (C3, incl. `split_benchmark` and `step_benchmark(..., split=)`); tests proving `settle_bracket`+`decide_bracket` looped over ≥ 300 synthetic sessions equal `run_backtest` (snapshots, events, closed, open), `step_benchmark` looped equals `buy_and_hold` with dividends; split on a pending and on an open bracket order; no look-ahead. Does not touch: `sim/*`, runners, `paper/book.py`, DB. Exit: equality tests green; purity green.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 3 of 13)
  - **Satisfies**: R1 — Engine paper step: pure core + impure command, per roster strategy per new session (state, splits, settle, dividends, force-close, decide, persist, SPY benchmark)
  - **Depends on**: P1-ENG-N6UC
  - **Plan**: `.workflows/plan/P1-ENG-79OL.md`
  - **Completed**: 2026-10-04 09:55
  - **Method**: /do
  - **Files**: engine/src/seer_engine/paper/bracket.py, engine/src/seer_engine/paper/benchmark.py, engine/tests/test_paper_bracket.py, engine/tests/test_paper_benchmark.py
  - **Verified**: focused 31 passed; full engine suite 1792 passed, 0 skipped; web vitest 44 passed
  - **Next**: P1-ENG-AYRQ (phase 6) left blocked: also depends on P1-ENG-1BVI (phase 4), still open (completion-handler)

- [x] **P1-ENG-X99Y** Phase 5: Dividends and held-symbol bars in `nightly`
  - **Difficulty**: NORMAL
  - **Type**: Update
  - **Context**: Owns `massive.Client.dividends(d)` (+ `MassiveSource` protocol); new `dividends.py` (parse CD+SC, sum per symbol/ex-date, upsert into `dividends`); `splits.apply_splits` also rewrites `dividends` before the execution date (`round(amount * from / to, 6)`); `nightly` fetches dividends per missing session in the same transaction and adds paper-held symbols (`universe.paper_symbols(conn, d)`: open/pending `orders`, `book_positions`, `book_targets` for sessions ≥ the session) to each session's wanted set; tests (`test_massive`, `test_nightly`, `test_splits`, new `test_dividends`). Does not touch: `paper/*`, workflows, web. Exit: fake-client tests for dividends, split rewrite of dividends, held symbol outside the universe still fetched; nightly stays one transaction.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 5 of 13)
  - **Satisfies**: R1 — Engine paper step: pure core + impure command, per roster strategy per new session (state, splits, settle, dividends, force-close, decide, persist, SPY benchmark)
  - **Depends on**: P1-ENG-N6UC
  - **Plan**: `.workflows/plan/P1-ENG-X99Y.md`
  - **Completed**: 2026-10-04 09:50
  - **Method**: /do
  - **Files**: engine/src/seer_engine/dividends.py, engine/src/seer_engine/massive.py, engine/src/seer_engine/splits.py, engine/src/seer_engine/universe.py, engine/src/seer_engine/commands/nightly.py, engine/tests/test_dividends.py, engine/tests/test_massive.py, engine/tests/test_splits.py, engine/tests/test_universe_queries.py, engine/tests/test_nightly.py
  - **Drift**:
    - test_universe_queries.py was 73 lines (plan said append after l.60); paper_symbols tests appended at end of file. No other drift.
  - **Verified**: focused 103 passed; full engine suite 1836 passed, 0 skipped; web vitest 44 passed
  - **Next**: P1-ENG-AYRQ (phase 6) left blocked: also depends on P1-ENG-79OL (phase 3) and P1-ENG-1BVI (phase 4), both still open (completion-handler)

- [x] **P1-ENG-YEW4** Phase 9: `explain`: optional LLM explanations
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `llm.py` (Anthropic-compatible Messages call over `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`; the key is sent as both `x-api-key` and `Authorization: Bearer` for z.ai compatibility; timeouts, redaction), `commands/explain.py` (fills `orders.explanation` for new pending A orders and `book_targets.explanation` for new entries of the latest decision; missing config or any LLM failure → leaves NULL, exit 0, logs); tests with a fake transport. Does not touch: `paper` command, workflows (phase 13), web. Exit: tests green; never raises on LLM failure.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 9 of 13)
  - **Satisfies**: R5 — Optional LLM explanations (D9)
  - **Depends on**: P1-ENG-N6UC
  - **Plan**: `.workflows/plan/P1-ENG-YEW4.md`
  - **Completed**: 2026-10-04 09:49
  - **Method**: /do
  - **Files**: engine/src/seer_engine/llm.py, engine/src/seer_engine/commands/explain.py, engine/tests/test_llm.py, engine/tests/test_explain.py
  - **Decided**:
    - readme-updater -> skipped for this phase; engine/package_readme.md is owned by phase 13 per the plan index invariant 8

- [x] **P1-ENG-N6UC** Phase 1: Migration 003 and the frozen roster
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `db/migrations/003_paper.sql` (C1); `engine/src/seer_engine/paper/__init__.py` (docstring only, no re-exports); `engine/src/seer_engine/paper/roster.py` (pure: `RosterEntry` with display fields, engine, `obj`, `params`, `rules`, `lookback`, `gate_note`; `ROSTER`, `ROSTER_IDS`, `MAX_LOOKBACK_BARS` = 253, `entry`, `spec`, `spec_text`, `spec_digest`, `backtest_gate`, `strategy_params`); purity-test coverage for `paper/*.py` except `store.py`; `demo.DEMO_TABLES` gains the five paper state tables and `purge_demo` also resets `strategies.paper_start`/`params` (the demo seed's paper clock); tests (`test_migrate`, new `test_paper_roster.py`, `test_demo`). Does not touch: any other engine module, the web, workflows, docs. Exit: `migrate` applies 003 on a fresh schema and is a no-op twice; roster display fields equal the migration's INSERT; digests pinned in a test; a demo purge empties the paper tables, keeps `dividends`, and resets the roster rows' `paper_start`/`params`.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 1 of 13)
  - **Satisfies**: R2 — Migration `003` (D6) + roster `strategies` rows with `paper_start` and frozen spec (D4); demo seed in the new shape
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-N6UC.md`
  - **Completed**: 2026-10-04 09:36
  - **Method**: /do
  - **Files**: db/migrations/003_paper.sql, engine/src/seer_engine/paper/__init__.py, engine/src/seer_engine/paper/roster.py, engine/src/seer_engine/demo.py, engine/tests/test_strategy_purity.py, engine/tests/test_demo.py, engine/tests/test_migrate.py, engine/tests/test_paper_roster.py
  - **Decided**:
    - Package mapping for TaskIDs: db/engine/* → engine (ENG), web/* → web (WEB, todos initialized), repo → root (ROOT) (rung 6: existing convention)
    - readme-updater -> skipped for this phase; engine/package_readme.md is owned by phase 13 per the plan index invariant 8

- [x] **P1-ENG-HCYN** Phase 2: Book-engine split rule
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `sim/book.py` `apply_book_split` + `BookSplit`; export in `sim/__init__.py`; tests in a new `tests/test_sim_book_split.py`. Does not touch: `step_book` behavior, `sim/split_adjust.py`, anything outside `sim`. Exit: whole-share and fractional rules, cash in lieu (credited to cash and `income_usd`), floor-to-zero → `forced` Trade, prices/targets rescaled by the exact fraction, reverse splits, purity.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 2 of 13)
  - **Satisfies**: R1 — Engine paper step: pure core + impure command, per roster strategy per new session (state, splits, settle, dividends, force-close, decide, persist, SPY benchmark)
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-HCYN.md`
  - **Completed**: 2026-10-04 09:35
  - **Method**: /implement
  - **Files**: engine/src/seer_engine/sim/book.py, engine/src/seer_engine/sim/__init__.py, engine/tests/test_sim_book_split.py
  - **Decided**:
    - Step 3 task creation in a concurrent swarm -> left to phase 1's session, which minted all 13 TaskIDs (phase 2 = P1-ENG-HCYN) (tie-break: narrower blast radius, avoid racing a peer on todos.md; same precedent as STRATEGY_B_RANKER set)
    - readme-updater -> skipped; engine/package_readme.md is owned by phase 13 only (rung 1: invariant 8)

- [x] **P1-ENG-904W** Phase 13: The real dev run, report, pre-registration, V0 `cmp`, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns the committed report set and pre-registration file, an identical re-run (`cmp`), the real-data `cmp` of `docs/backtests/2026-10-02-*` (per Decisions), `engine/package_readme.md`, `docs/ROADMAP.md` (P7a entry with the result, and the P7b entry), and one appended Decisions row in the index (the R1 outcome). Never stops to ask (D-H): a missing store is rebuilt, a differing fingerprint is recorded and the run proceeds, a defect fixable only in `registry.py` or a frozen file ends the phase with the run uncommitted and a note in the phase log and completion summary. Exit: every handover §7 item checked off in the phase log; suite green with 0 skipped (1694 plus only Bug-protocol tests); CI green.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 13 of 13)
  - **Satisfies**: R1 — `TradeRules`: `DESIGN_V0` reproduces §5, and A, A2 and B re-render byte-identically (synthetic test plus a real-data `cmp`). Each new lever has its own synthetic-bar tests; R6 — One dev run over every candidate, with the committed report holding every §7.6 section; R7 — The pre-registration file (≤ 3 finalists exactly specified, or "none eligible"), with the proposed §5 revision; R9 — Docs (package readme, ROADMAP P7a and P7b). The suite is green with 0 skipped, and CI is green
  - **Depends on**: P1-ENG-ZWP9
  - **Plan**: `.workflows/plan/P1-ENG-904W.md`
  - **Completed**: 2026-10-04 07:37
  - **Method**: /do
  - **Files**: docs/backtests/2026-10-04-p7a-dev-exploration.md, docs/backtests/2026-10-04-p7a-dev-exploration-rows.csv, docs/backtests/2026-10-04-p7a-dev-exploration-curves.csv, docs/backtests/2026-10-04-p7a-dev-exploration-frontier.svg, docs/plans/2026-10-04-p7b-preregistration.md, engine/package_readme.md, docs/ROADMAP.md, TRADE_RULES_DEV_SEARCH_PLAN.md
  - **Drift**:
    - package_readme.md line numbers (as of 2546a92) had moved: phase 3's readme-updater had added a book_runner layout line and a 'backtest book runner (P7a)' section. Blocks were placed by content anchor; phase 3's section kept, not duplicated.
    - Readme text follows landed code where the plan draft differed: V0_BOOK is not in PRESETS; backtest_dev --only writes nothing (not 'send to scratch'); extra exit-2 cases (unknown --only id, DEV_END mismatch); --dry-run/-v flags on both commands; close_book_unpriced returns (book, fills, trades).
    - Step 1c's test-diff guard showed engine/tests/conftest.py modified since 2546a92 (commit 992f2eb, thread caps, additive, no test changed); proceeded.
  - **Decided**:
    - conftest.py diff in Step 1c's no-test-modified guard -> proceed (rung 1: invariant 3's frozen set is empty-diff; conftest holds no test and the change is additive infra the coordinator committed)
    - Readme anchors drifted -> place by content, keep phase 3's book-runner section (small drift rule; narrower blast radius)
    - readme-updater -> skipped; engine/package_readme.md was this phase's own deliverable, already written and committed in e273531 (completion-handler, per coordinator instruction)
    - Landing -> not done here; swarm coordinator orch-trade-rules-dev-search owns the merge (analyze-orchestrator Step 5) (completion-handler)
  - **Outcome**:
    - Commits: 7a24b84 (dev run), e273531 (docs); CI green https://github.com/miftahulmahfuzh/seer/actions/runs/37165273861
    - Store fingerprint 5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a (equals phase 4's); registry 54 candidates / 11 families / 11 owner-input, committed at b2ec090 before the run
    - D8: none eligible (35 beat SPY TR, 0 max DD<=15%, 40 PF>=1.3, 33 >=100 trades, 43 no owner input). Best MAR F4-MOM12-N20-TREND (CAGR +16.2% vs +7.9%, DD 22.2%, PF 2.27, 1154 trades, MAR 0.73), failed only on DD. P7b does not run
    - Re-run cmp: same=5, byte-identical; R1 real-data cmp: Neon fingerprint unchanged, all 11 docs/backtests/2026-10-02-* cmp-equal
    - Suite: 1694 passed, 0 skipped (before and after); dev run 0:51, re-run 0:49, peak RSS 847 MB, sequential
    - Sanity: REF-SPY-HOLD +594.6% vs SPY TR +594.7%; date scan FAILURES 0

- [x] **P1-ENG-ZWP9** Phase 12: `backtest_dev` command, io writer, runtime on the real store
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `commands/backtest_dev.py` running the registry through `dev.run_registry(on_result=...)` (D-D), additive `backtest/io.py` (`dev_report_files`, `write_dev_report`), new `tests/test_backtest_dev_command.py` (28) incl. the D-I tests (`research.DEV_END`, `MEMBERSHIP_START`, `FX_START` equal `dev`'s; `registry.SECTOR_ETFS == research.SECTOR_ETFS`; registry fixed symbols subset of `research.RESEARCH_ETFS`) on a synthetic store; also a timed `--only` smoke run on the real store with no docs written, adding a fixed-order process pool (D13; +2 tests) if the estimated whole run exceeds 60 min. Exit: suite green at 1694 (1696 with the pool); the command's dirty-registry refusal is tested.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 12 of 13)
  - **Satisfies**: R4 — The dev window is enforced in code (no session after 2015-10-16), and a test proves it; R6 — One dev run over every candidate, with the committed report holding every §7.6 section; R8 — Determinism and purity: `==` results, byte-identical files, and the purity globs pass
  - **Depends on**: P1-ENG-CQ5M, P1-ENG-PLRV, P1-ENG-078U
  - **Plan**: `.workflows/plan/P1-ENG-ZWP9.md`
  - **Completed**: 2026-10-04 07:05
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/io.py, engine/src/seer_engine/commands/backtest_dev.py, engine/tests/test_backtest_dev_command.py
  - **Drift**:
    - none: every API the plan quotes (io.py lines, dev.run_registry on_result, research constants/load_store, DevReport fields, registry ids) matched the tree
  - **Decided**:
    - test_full_run_writes_byte_identical_files asserted the run date never appears in rendered text, but dev_report's markdown links its sibling files by name (which carry the run date) -> the test strips the five sibling file names before asserting no run date remains (rung 1 / Decisions row 'Report file names': the run date appears in file names only, and so in the links between the sibling files); renderer unchanged
    - Step 6 commit-before-smoke folded into the single phase commit: --only skips the registry check and registry.py is untouched (git status clean), so ordering does not matter (rung 6; /implement: main context performs no git ops)
    - D13: sequential, estimated 1.1 min for 54 candidates from 16 timed, no pool; Step 8 not implemented (plan Step 7 decision rule)
    - readme-updater -> skipped; engine/package_readme.md is owned by phase 13 per the plan index (rung 4: index scope; same call phases 9-11 made)
    - Phase 13 (P1-ENG-904W) unblocked: its only dep, phase 12, is complete (completion-handler)
  - **Outcome**:
    - Suite: `PG_TEST_URL=... engine/.venv/bin/pytest engine/tests -q` -> 1694 passed, 0 skipped (2 pandas deprecation warnings from the test's fake downloader concat)
    - Frozen set: `git diff --stat 2546a92 -- <frozen set>` printed nothing
    - Research store verify: exit 0; fingerprint 5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a (equals phase 4's logged value); 539 symbols with bars, 2,490,793 bar rows, 28,206 dividends, 4,300 fx rows, 522 unserved
    - Smoke: `backtest_dev --only` (16 candidates) on the real store: exit 0, wall 0:28.79, peak RSS 866,764 KB; `git status --porcelain docs/` empty
    - Smoke timings: [1/16] REF-SPY-HOLD 0.76s; [2/16] REF-A-V0 4.26s (pre-1999 FX path ran fine, D-C); [3/16] F1-SPY-SMA200-D 0.71s; [4/16] F1-SPY-10MSMA-M 0.15s; [5/16] F1-SPY-VT12-W 0.33s; [6/16] F10-SSO-SMA200-D 0.25s; [7/16] F11-SPY-TOM-TREND 0.33s; [8/16] F2-GEM-SPYEFA-IEF 0.09s; [9/16] F3-SEC-TOP3-6M 0.22s; [10/16] F4-MOM12-N10-TREND 1.01s; [11/16] F4-MOM12-N10-TREND-W 0.99s; [12/16] F5-LV60-N20 1.38s; [13/16] F6-ML-P50-N10-VT12 1.55s; [14/16] F7-RSI2-T20-DIP 4.19s; [15/16] F9-SPY200M70-MOM30 1.07s; [16/16] F9-SPY200D50-SWING50 4.88s
    - Estimated full run: 1.1 min for 54 candidates. D13: sequential, no pool

- [x] **P1-ENG-PLRV** Phase 10: Dev report and pre-registration renderers
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `backtest/dev_report.py` and `tests/test_backtest_dev_report.py` (32) using structural checks and byte-stability. Exit: suite green; two renders are byte-identical; rendered content contains no run date outside sibling-file names; `top_years` lists the finalists first (D-G).
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 10 of 13)
  - **Satisfies**: R6 — One dev run over every candidate, with the committed report holding every §7.6 section; R7 — The pre-registration file (≤ 3 finalists exactly specified, or "none eligible"), with the proposed §5 revision; R8 — Determinism and purity: `==` results, byte-identical files, and the purity globs pass
  - **Depends on**: P1-ENG-2E01
  - **Plan**: `.workflows/plan/P1-ENG-PLRV.md`
  - **Completed**: 2026-10-04 06:35
  - **Method**: /implement
  - **Files**: engine/src/seer_engine/backtest/dev_report.py, engine/tests/test_backtest_dev_report.py
  - **Drift**:
    - Phase 9's DevRow.__post_init__ already calls check_dev_session(end) and checks beats_spy agrees with failed; the plan's fixture predated that. Fixed in the test fixture only (per the plan's prototype note: fix the fixture, never the other phase): the 'after-dev-end' bad report now forces end past construction with object.__setattr__ so the renderer's own third D9 guard is what is exercised; beats_spy is derived as '"beats SPY TR" not in failed' so the all_fail fixture builds a consistent DevRow.
    - Verification: test_backtest_dev_report.py 32 passed; test_strategy_purity green (glob covers dev_report.py); full suite 1666 passed, 0 skipped (1560 through phase 9 + 32 phase 10 + 74 phase 11); frozen-set git diff vs 2546a92 empty.
  - **Decided**:
    - Plan fixture vs landed DevRow validation -> adapt the test fixture, module unchanged (rung 3: the plan's Verification note that a contract mismatch is fixed in the fixture or this module, never the other phase)
    - readme-updater -> skip; engine/package_readme.md is owned by phase 13 per the plan index (rung 4: index scope; same as phases 4 and 5)
    - Completion bookkeeping waited for phase 11's concurrent commit (b2ec090) before editing todos.md and the index, so neither commit carries the other phase's edits (tie-break: narrower blast radius)
    - Phase 12 (P1-ENG-ZWP9) unblocked: its deps 4, 10 and 11 are all complete (completion-handler)


- [x] **P1-ENG-078U** Phase 11: The candidate registry (54 entries, append-only test)
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `backtest/registry.py` and `tests/test_registry.py` (74): ids unique and the first 54 are the index table in order (row 54 under `SWING_T20`); <= 60 entries; (id, digest) pins append-only; declared owner inputs equal `candidate_owner_inputs`; every rules preset valid for its allocator; every candidate runs one short smoke window on a synthetic market (every fixed symbol, BIL and the leveraged ETFs) through `run_candidate`. Exit: suite green and the registry committed before any real dev run (agreement with `research` is phase 12's test).
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 11 of 13)
  - **Satisfies**: R5 — The candidate registry is committed before the dev run: ≤ 60 entries, append-only, each with a family, rules, fixed params, a rationale and an owner-verification flag
  - **Depends on**: P1-ENG-ZNTC, P1-ENG-76SL, P1-ENG-SB1Q, P1-ENG-5U7B, P1-ENG-2E01
  - **Plan**: `.workflows/plan/P1-ENG-078U.md`
  - **Completed**: 2026-10-04 06:29
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/registry.py, engine/tests/test_registry.py
  - **Drift**:
    - None in the plan's code. Plan index Status line was stale (it omitted phases 7 and 9, which are complete in todos.md and git); dependencies 5-9 were verified complete.
    - Full suite: 1663 passed, 3 failed, 0 skipped. All 3 failures are in engine/tests/test_backtest_dev_report.py, phase 10's untracked work in progress written concurrently in this worktree by session impl-trade-rules-dev-search-p10; not part of this phase. Excluding phase 10's 32 tests: 1560 (through phase 9) + 74 (phase 11) = 1634, all passed.
    - test_registry.py: 74 passed (20 + 54 smoke cases); smoke wall time ~10 s (well under 60 s, nothing to note for phase 12's D13). test_strategy_purity covers registry.py. grep -c UNPINNED = 0. Frozen-set git diff vs 2546a92 is empty.
  - **Decided**:
    - FIRST_APPEND date -> date(2026, 10, 4) (also the '# ---- 2026-10-04' registry comment), because the commit is made 2026-10-04 (rung 3: the phase plan's Step 1 says to set it to the commit date). The digest excludes `added`, so the pins are unaffected.
    - P1-ENG-ZWP9 left blocked: its other dep P1-ENG-PLRV (phase 10) is not complete (completion-handler)
    - readme-updater -> skipped for this phase; engine/package_readme.md is owned by phase 13 per the plan index phase table (rung 4: index scope; same call phase 3 made)

- [x] **P1-ENG-2E01** Phase 9: Dev runner: window guard, candidate windows, D8, deflated Sharpe
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `backtest/dev.py` and `tests/test_backtest_dev.py` (50): `DevWindowError` on any end, session, bar, FX row or dividend after 2015-10-16 from every public entry point; `candidate_window` across ETF launches and the membership start; a window starting before 1999-01-04 converting at the `FX_START` rate (D-C); D8 selection incl. one-per-family, ties and `mar is None` ranked last; deflated Sharpe vs hand-computed cases; `run_registry` order, determinism, one prepare per allocator id and the `on_result` callback. Exit: suite green.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 9 of 13)
  - **Satisfies**: R4 — The dev window is enforced in code (no session after 2015-10-16), and a test proves it; R5 — The candidate registry is committed before the dev run: ≤ 60 entries, append-only, each with a family, rules, fixed params, a rationale and an owner-verification flag; R8 — Determinism and purity: `==` results, byte-identical files, and the purity globs pass
  - **Depends on**: P1-ENG-CPHN
  - **Plan**: `.workflows/plan/P1-ENG-2E01.md`
  - **Completed**: 2026-10-04 06:22
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/dev.py, engine/tests/test_backtest_dev.py
  - **Decided**:
    - readme-updater -> skipped; engine/package_readme.md is owned by phase 13 per the plan index (rung 4: index scope)

- [x] **P1-ENG-76SL** Phase 6: Families F2/F3: ETF rotation
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `strategies/f_rotation.py` and `tests/test_f_rotation.py` (39): momentum ranking with ties, absolute filter, fallback, trend filter, missing or short ETFs, P4 identity and no look-ahead (locally and through the kit). Exit: suite green.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 6 of 13)
  - **Satisfies**: R3 — No look-ahead and P4 identity for every new family; the prepared and single-window paths agree
  - **Depends on**: P1-ENG-XORE
  - **Plan**: `.workflows/plan/P1-ENG-76SL.md`
  - **Completed**: 2026-10-04 06:16
  - **Method**: /do
  - **Files**: engine/src/seer_engine/strategies/f_rotation.py, engine/tests/test_f_rotation.py
  - **Drift**:
    - None: both files written verbatim from the phase-6 plan's code blocks.
  - **Decided**:
    - Full-suite wall-clock flake under swarm load (test_backtest_b_command.py::test_wall_times_reach_logs_only; 8h31m run at load avg ~41; passes alone in 9.6s) -> accepted on an isolated re-pass, no check relaxed (tie-break: never relax a check; the test itself passes unchanged)
    - readme-updater -> skipped; engine/package_readme.md is owned by phase 13 per the plan index (rung 4: index scope)

- [x] **P1-ENG-SB1Q** Phase 7: Families F4/F5/F6: stock factors
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `strategies/f_factor.py` (vectorized, param-independent `prepare` like `prepare_a`) and `tests/test_f_factor.py` (78): hand-computed 12-1 momentum, vol and dollar-volume eligibility; mom_lowvol pool selection; inverse-vol weights summing to <= 1; trend filter; members only with SPY excluded; P4 identity with bit-identity between prepared and single-window features; no look-ahead (locally and through the kit). Exit: suite green.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 7 of 13)
  - **Satisfies**: R3 — No look-ahead and P4 identity for every new family; the prepared and single-window paths agree
  - **Depends on**: P1-ENG-XORE
  - **Plan**: `.workflows/plan/P1-ENG-SB1Q.md`
  - **Completed**: 2026-10-04 06:15
  - **Method**: /do
  - **Files**: engine/src/seer_engine/strategies/f_factor.py, engine/tests/test_f_factor.py
  - **Drift**:
    - none: plan code blocks applied verbatim
  - **Decided**:
    - full suite 1 failed / 1509 passed (8h31m, load avg ~41 from concurrent phase sessions sharing this worktree): test_backtest_b_command.py::test_wall_times_reach_logs_only asserts real wall times < 1000 s -> treated as a load-induced flake, not relaxed (frozen test file, outside phase scope); passes in isolation in 7 s (tie-break: never relax a check)
    - ruff not installed in engine/.venv -> lint step skipped; pytest + purity glob are the plan's verification
    - readme-updater -> skipped; engine/package_readme.md is owned by phase 13 per the plan index (rung 4: index scope; same as phases 4 and 5)
    - Phase 11 (P1-ENG-078U) left blocked: its dep 9 (P1-ENG-2E01) is not complete


- [x] **P1-ENG-5U7B** Phase 8: Family F7: longer-horizon mean reversion
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `strategies/f_swing.py` and `tests/test_f_swing.py` (87): setup and dip/close limits; stop and take from ATR; signal exits (SMA and RSI); self-capped slots with keep-first ordering; held symbols that left the index; market-trend gate for new entries only; P4 identity and no look-ahead (locally and through the kit). Exit: suite green.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 8 of 13)
  - **Satisfies**: R3 — No look-ahead and P4 identity for every new family; the prepared and single-window paths agree
  - **Depends on**: P1-ENG-XORE
  - **Plan**: `.workflows/plan/P1-ENG-5U7B.md`
  - **Completed**: 2026-10-04 06:15
  - **Method**: /do
  - **Files**: engine/src/seer_engine/strategies/f_swing.py, engine/tests/test_f_swing.py
  - **Decided**:
    - Full suite: 1 failed / 1509 passed / 0 skipped in 8h29m under load avg ~40 (several phase sessions sharing the machine); the failure was test_backtest_b_command.py::test_wall_times_reach_logs_only (wall-time < 1000s assertion), unrelated to F7; re-run alone: 23/23 passed in 19.5s -> treated as load-induced, not a phase-8 regression (no check relaxed)
    - No task unblocked: phase 11 (P1-ENG-078U) still waits on phases 4-7 and 9 (index phase table Depends on)
    - readme-updater -> skipped for this phase; engine/package_readme.md is owned by phase 13 per the plan index (index scope)

- [x] **P1-ENG-CPHN** Phase 3: Book runner, `run_rules` dispatch, run stats, V0 parity
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `backtest/book_runner.py` and `tests/test_book_runner.py` (47). Does not touch `runner.py`, `metrics.py`, `benchmark.py` (imported read-only). Exit: suite green, and on seeded synthetic markets: `run_rules(..., DESIGN_V0) == run_backtest(...)` for A, A2 and B (fake predictor); `run_book(PICKS(A), V0_BOOK)` matches `run_backtest` snapshots, trades, fills and open positions exactly (seeds 39 and 4 plus the hand-checked FixedPicks scenario); the allocator never sees the idle position in `held` (D-J); `run_stats` hand-checked on small books.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 3 of 13)
  - **Satisfies**: R1 — `TradeRules`: `DESIGN_V0` reproduces §5, and A, A2 and B re-render byte-identically (synthetic test plus a real-data `cmp`). Each new lever has its own synthetic-bar tests; R8 — Determinism and purity: `==` results, byte-identical files, and the purity globs pass
  - **Depends on**: P1-ENG-OY9Z, P1-ENG-XORE
  - **Plan**: `.workflows/plan/P1-ENG-CPHN.md`
  - **Completed**: 2026-10-04 06:15
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/book_runner.py, engine/tests/test_book_runner.py
  - **Decided**:
    - full-suite failure test_backtest_b_command.py::test_wall_times_reach_logs_only -> treated as a load flake, not a phase-3 defect (the full run took 8h30m at load avg ~61 with 4 concurrent suites, so a real step exceeded the test's 1000 s wall-time bound; rerun alone: 23/23 passed in 16 s; phase 3 touches no file that test imports)
    - Unblocked phase 9 (P1-ENG-2E01) -> open; its only dependency is phase 3 (index phase table Depends on)

- [x] **P1-ENG-ZNTC** Phase 5: Families F1/F10/F11: index timing and calendar
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `strategies/f_index.py` and `tests/test_f_index.py` (109): hand-checked signals (SMA, month-end SMA, absolute momentum, always, turn-of-month calendar around month ends and holidays), P4 identity and no look-ahead, locally and through the phase-2 kit (D-E). Exit: suite green; purity glob covers the module.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 5 of 13)
  - **Satisfies**: R3 — No look-ahead and P4 identity for every new family; the prepared and single-window paths agree
  - **Depends on**: P1-ENG-XORE
  - **Plan**: `.workflows/plan/P1-ENG-ZNTC.md`
  - **Completed**: 2026-10-04 04:54
  - **Method**: /do
  - **Files**: engine/src/seer_engine/strategies/f_index.py, engine/tests/test_f_index.py
  - **Drift**:
    - none: both files written verbatim from the phase-5 plan code blocks
  - **Decided**:
    - full suite 1 failed / 1509 passed (7h01m, machine load avg ~62 from concurrent swarm sessions): test_backtest_b_command.py::test_wall_times_reach_logs_only asserts real wall times < 1000s; under this load the real run exceeds it (isolated rerun could not finish in 900s). Nothing imports f_index except test_f_index.py, so environmental, not this phase -> proceeded without touching the test (tie-break: never relax a check; not a phase-5 regression)
    - ruff not installed in engine/.venv -> lint not run (not part of the plan's verification)
    - readme-updater -> skip; engine/package_readme.md is owned by phase 13 per the plan index (rung 4: index scope; same as phase 4)
    - Phase 11 (P1-ENG-078U) left blocked: its other deps, phases 6, 7, 8 and 9, are not complete

- [x] **P1-ENG-CQ5M** Phase 4: Research store: build, load, verify, command, real build
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `seer_engine/research.py`, new `commands/research_store.py`, additive dividends-aware download/parse in `yahoo.py`, `.gitignore` entries (`engine/.research/`, `.research.tmp/`, `.research.old/`), new `tests/test_research_store.py` (34, fake downloader + fake FX fetcher); also does the real build into the worktree's `engine/.research/` (30-60 min background), logging counts and fingerprint, verifying SPY has a bar on every NYSE session 1993-02-01..`DEV_END`, yfinance SPY dividends equal `engine/data/spy_dividends.csv` on 2015-03-20..2015-10-16, and AAPL 2012 split-adjusted dividend consistency. Does not touch `membership.py`, `fx.py`, `backfill.py`, Neon (constant equality with `backtest.dev` tested in phase 12, D-I). Exit: suite green; re-running `build_store` on the same fake downloads gives byte-identical files and the same fingerprint; `load_store` rejects a tampered file and a row after `DEV_END`; `research_store --verify` exits 0 on the real store.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 4 of 13)
  - **Satisfies**: R2 — A research store command: pre-2015 member bars, the L9 ETFs, dividends from the start, unserved members per year, no Neon writes, deterministic, with a fingerprint; R4 — The dev window is enforced in code (no session after 2015-10-16), and a test proves it
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-CQ5M.md`
  - **Completed**: 2026-10-03 22:00
  - **Method**: /implement
  - **Files**: .gitignore, engine/src/seer_engine/yahoo.py, engine/src/seer_engine/research.py, engine/src/seer_engine/commands/research_store.py, engine/tests/test_research_store.py
  - **Drift**:
    - none: the code matched the plan's quotes; code blocks applied verbatim
    - real build had 522 of 1061 requested symbols unserved (plan estimated ~400); all are index members (ETFs all served); recorded per year for the D4 survivorship caveat, not a check failure
  - **Decided**:
    - Step 3 task creation in a concurrent swarm -> left to phase 1's session, which created all 13 tasks (tie-break: narrower blast radius, avoid racing peers on todos.md; same as strategy-b-ranker precedent)
    - readme-updater -> skip; engine/package_readme.md is owned by phase 13 per the plan index (rung 4: index scope)
    - Phase 12 (P1-ENG-ZWP9) left blocked: its other deps, phases 10 and 11, are not complete
  - **Phase log**:
    - fingerprint: 5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a
    - symbols: 539 served of 1061 requested, 522 unserved
    - rows: 2,490,793 bars, 28,206 dividends, 4,300 fx
    - unserved members by year (unserved of members): 1996 267/506, 1997 258/516, 1998 260/526, 1999 260/533, 2000 267/546, 2001 243/522, 2002 231/517, 2003 214/503, 2004 219/513, 2005 209/511, 2006 216/529, 2007 240/593, 2008 219/586, 2009 202/569, 2010 182/549, 2011 175/553, 2012 164/552, 2013 154/550, 2014 142/540, 2015 137/548
    - check spy-sessions: ok: 5721 NYSE sessions 1993-02-01..2015-10-16, 0 without a SPY bar
    - check spy-dividends: ok: 2015-03-20..2015-10-16: store 2015-03-20=0.931, 2015-06-19=1.03, 2015-09-18=1.033 | vendored 2015-03-20=0.931, 2015-06-19=1.03, 2015-09-18=1.033
    - check dividend-scale-AAPL-2012: ok: 2012-08-09: 0.094643 / close 22.1379 = 0.4275%; 2012-11-07: 0.094643 / close 20.8161 = 0.4547%
    - build wall time 34:45; store size 130M (engine/.research/, gitignored, never committed)

- [x] **P1-ENG-XORE** Phase 2: Allocator protocol, adapters, overlays, `return_window`
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `strategies/allocator.py` (`Allocator`, `target_from_close`, `month_end_closes`, `last_close`, `scale_weight`, `vol_scale`, `LazyPrepared`, `PicksAllocator`, `BlendAllocator`, `VolTargetAllocator`), additive `return_window` in `strategies/indicators.py`, new `tests/test_allocator.py` (55) and the reusable P4-identity/no-look-ahead kit `tests/allocatorkit.py` (contract API, D-E) that phases 5-8 import. Does not touch existing indicator functions, `base.py`, `a.py`, `a2.py`, `b.py`, `strategies/__init__.py`. Exit: suite green; purity glob covers `allocator.py`; P4 identity of `PicksAllocator`/`BlendAllocator`/`VolTargetAllocator` tested with fake inner allocators; the kit rejects a look-ahead fake, a broken prepared path and a too-short lookback.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 2 of 13)
  - **Satisfies**: R3 — No look-ahead and P4 identity for every new family; the prepared and single-window paths agree; R8 — Determinism and purity: `==` results, byte-identical files, and the purity globs pass
  - **Depends on**: P1-ENG-OY9Z
  - **Plan**: `.workflows/plan/P1-ENG-XORE.md`
  - **Completed**: 2026-10-03 21:40
  - **Method**: /do
  - **Files**: engine/src/seer_engine/strategies/allocator.py, engine/src/seer_engine/strategies/indicators.py, engine/tests/allocatorkit.py, engine/tests/test_allocator.py
  - **Decided**:
    - readme-updater -> skipped for this phase; engine/package_readme.md is owned by phase 13 (rung 4: index Scope / phase 13 Owns; same call as phase 1)
    - Unblocked phases 3, 5, 6, 7, 8 (P1-ENG-CPHN, ZNTC, 76SL, SB1Q, 5U7B) -> open; every dependency (phases 1, 2) is complete (rung 4: index phase table Depends on)


- [x] **P1-ENG-OY9Z** Phase 1: `TradeRules` + the book engine
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `sim/rules.py` and `sim/book.py` (exactly as contracted), additive exports in `sim/__init__.py`, new `tests/test_sim_rules.py` (35) and `tests/test_sim_book.py` (56) with at least one synthetic-bar test per lever: signal exit at next open incl. missing bar (`exit_pending`); rebalance trims/adds under `RESIZE_BAND`; dividends on ex-date; fractional shares; `open`/`open_limit` entries (gap above band unfilled); `limit` entry and its D-B fallback; `max_positions` != 4 and sum weight > 1 only under a slot cap (D-A); time stop 10/20/None; vol-scaled weights; idle T-bill target; cash guard; `close_book_unpriced`; episode P&L reconciling with cash exactly; session-by-session replay of `size_picks` + `step` under `V0_BOOK`. Does not touch `sim/model.py`, `lifecycle.py`, `sizing.py`, `split_adjust.py` or anything outside `sim/`. Exit: suite green, 0 skipped (+91); `test_sim_purity.py` covers both new modules; `DESIGN_V0` agrees with the `model` constants (tested); V0 replay passes for 3 seeds.
  - **Status**: completed
  - **Plan Set**: `TRADE_RULES_DEV_SEARCH_PLAN.md` (phase 1 of 13)
  - **Satisfies**: R1 — `TradeRules`: `DESIGN_V0` reproduces §5, and A, A2 and B re-render byte-identically (synthetic test plus a real-data `cmp`). Each new lever has its own synthetic-bar tests; R8 — Determinism and purity: `==` results, byte-identical files, and the purity globs pass
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-OY9Z.md`
  - **Completed**: 2026-10-03 21:03
  - **Method**: /do
  - **Files**: engine/src/seer_engine/sim/rules.py, engine/src/seer_engine/sim/book.py, engine/src/seer_engine/sim/__init__.py, engine/tests/test_sim_rules.py, engine/tests/test_sim_book.py
  - **Decided**:
    - Step 3 task creation in a concurrent swarm -> phase 1 session created all 13 tasks (P1-ENG-OY9Z..904W) (convention from strategy-b-ranker set; avoid peers racing on todos.md)
    - Phase 4 task (P1-ENG-CQ5M) status -> in_progress, not blocked (it has no dependencies and its session is running) (rung 4: index phase table Depends on '—')
    - readme-updater -> skip for this phase; engine/package_readme.md is owned by phase 13 (rung 4: index Scope / phase 13 Owns; phase 1 Handoffs: 'this phase writes no docs')


- [x] **P1-ENG-M99E** Phase 7: Real run on Neon, A2 byte-identity check, freeze or stop, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns the real `backtest_b` run on Neon from the worktree (`SEER_ENV_FILE`; record data end, wall time, peak RSS); re-run `backtest_wf --end 2026-10-02 --out <scratch>` and `cmp` all 5 files against committed `docs/backtests/2026-10-02-strategy-a2-walkforward*` (a difference stops the phase); commit the B report set. On a pass: set `STRATEGY_B_FROZEN` in `b.py` (report, artifact, `train_end`, sha256; only that line and its two comment lines), commit the artifact, re-run so the report records `frozen-model`, and `tests/test_strategy_b_frozen.py` (6 tests) asserts constant == machine line, sha256 of artifact bytes, and `loads(artifact).digest` == last-fold digest (D23-D25). On a fail: constant stays None and the test asserts `failed`, `frozen-model: null` and no artifact under `engine/data/models/`. Docs: `engine/package_readme.md` (B, labeler, features, model, `backtest_b`, performance, module graph) and `docs/ROADMAP.md` (P6a verdict; on a fail, B's one round failed, P4 stays blocked, owner's options). Exit: suite green, 0 skipped (970 plus any Bug-protocol regression tests), CI green, report committed.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 7 of 7)
  - **Satisfies**: R4 — Walk-forward. The folds are exactly P3b's. Training uses purged labels only. One chained portfolio, whose brackets survive the year boundary. `backtest_wf`'s A2 report stays byte-identical; R7 — One real run on Neon, with the committed report holding every section §6.7 lists; R8 — Freeze or stop. **Pass:** artifact + constant + tie test. **Fail:** ROADMAP records the failure, P4 stays blocked, and the report lists the owner's options; R9 — The readme documents B. The suite is green with 0 skipped. CI is green with scikit-learn
  - **Depends on**: P1-ENG-UREW
  - **Plan**: `.workflows/plan/P1-ENG-M99E.md`
  - **Completed**: 2026-10-03 19:33
  - **Method**: /do
  - **Files**: docs/backtests/2026-10-02-strategy-b-walkforward.md, docs/backtests/2026-10-02-strategy-b-walkforward-equity.csv, docs/backtests/2026-10-02-strategy-b-walkforward-equity.svg, engine/tests/test_strategy_b_frozen.py, engine/package_readme.md, docs/ROADMAP.md
  - **Outcome**: P6a gate FAILED (fail branch). B +13.3% vs +187.6% total-return SPY, PF 1.03, max DD 57.6%; B-linear +20.6%, PF 1.05, DD 32.4%; A2 +9.1%. Determinism probe bit-identical, gated model B. STRATEGY_B_FROZEN stays None, no artifact under engine/data/models. A2 5 files cmp-identical on re-run (R4). Run #2 byte-identical to run #1. Neon fingerprint (2026-10-02, 1817429) unchanged across the phase. Suite 970 passed, 0 skipped. Whole command 5:47 / 5:53, peak RSS 1548 MB. CI run 37123034970 green on e71c059.
  - **Drift**:
    - engine/package_readme.md line numbers had shifted (phases 2 and 4 added 'in progress' lines); edits were anchored by content, and the in-progress placeholders (layout b.py / b_walkforward.py lines, the '### backtest Strategy B walk-forward (P6a, in progress…)' section) were replaced by the final text.
  - **Decided**:
    - Readme module-graph and imports text -> written from the actual imports (labels imports sim.model TIME_STOP_DAYS not COST_RATE; b_walkforward does not import benchmark; command imports numpy/b_model, not dates/universe) (plan Step 9: 'where the code differs from this text, the code wins')
    - Plan 9g's indicators paragraph -> not added; phase 2 already documented mean_window / stdev_return_window as bullets in the indicators list (rung 6, avoid duplicating existing doc)
    - Commits of run + docs and the branch push -> done by main context per the phase plan's Steps 8/10/11 (rung 3: the phase plan's code blocks), since CI green on the pushed head is an exit criterion
- [x] **P1-ENG-UREW** Phase 6: `backtest_b` command + io writers
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns additive `backtest/io.py` (`MODELS_DIR`, `write_b_report`, `write_model_artifact`; the only phase editing `io.py`), new `commands/backtest_b.py` incl. public `recompute_a2(market, folds)` with eager imports (every CLI command now loads scikit-learn via `cli.discover`, D19), and new `tests/test_backtest_b_command.py` (23 tests: `execute` twice on a synthetic market gives `==` reports and byte-identical files; gate pass writes the artifact, fail does not; exit 2 on a precondition; A2 curve equals `backtest_wf`'s combined curve; wall times in logs only; synthetic-market helpers live in the test file). Does not touch `backtest_wf.py` (imported only) or `cli.py`. Exit: suite green, 0 skipped (964); `python -m seer_engine backtest_b --help` works.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 6 of 7)
  - **Satisfies**: R5 — Determinism. `==` results and byte-identical files. The gated model is bit-identical across runs and thread counts, or the pre-registered switch to B-linear takes effect; R7 — One real run on Neon, with the committed report holding every section §6.7 lists
  - **Depends on**: P1-ENG-VK5P
  - **Plan**: `.workflows/plan/P1-ENG-UREW.md`
  - **Completed**: 2026-10-03 19:05
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/io.py, engine/src/seer_engine/commands/backtest_b.py, engine/tests/test_backtest_b_command.py
  - **Decided**:
    - readme-updater -> skip for this phase; engine/package_readme.md is owned by phase 7 per the plan index Scope / phase 7 Owns (rung 4: index scope) -- same decision phases 3-5 recorded
- [x] **P1-ENG-VK5P** Phase 5: B report rendering
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `backtest/b_report.py` (`BReport` with `curves()`/`gated_curve()`, `_validate`, `top_features`, machine lines with `label_sum` as a JSON string of `repr(float)` D23, `render_markdown`, `equity_csv`, `equity_svg`; Markdown sections in order: title, data, method, per-fold training summary for B and B-linear, results vs both SPY curves, year by year, diagnostics incl. passed nights and calibration, seen before, go-live checklist, survivorship with learned-model caveat, open positions, curves SVG link, verdict sentence, owner's options (b)/(c)/(d) on a fail, machine fence) and new `tests/test_backtest_b_report.py` (27 tests from a small synthetic run via phase 4's API). Does not touch `wf_report.py` or `report.py` (helpers imported only). Exit: suite green, 0 skipped (941); rendering twice is byte-identical; `_validate` rejects a mismatched verdict, a misaligned curve and a schedule not matching `fold_models`.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 5 of 7)
  - **Satisfies**: R5 — Determinism. `==` results and byte-identical files. The gated model is bit-identical across runs and thread counts, or the pre-registered switch to B-linear takes effect; R6 — Purity. The new modules pass the globbing purity test; R7 — One real run on Neon, with the committed report holding every section §6.7 lists
  - **Depends on**: P1-ENG-U5JJ
  - **Plan**: `.workflows/plan/P1-ENG-VK5P.md`
  - **Completed**: 2026-10-03 19:30
  - **Method**: /implement
  - **Files**: engine/src/seer_engine/backtest/b_report.py, engine/tests/test_backtest_b_report.py
  - **Decided**:
    - readme-updater -> skipped for this phase; engine/package_readme.md is owned by phase 7 per the plan index Scope/phase 7 Owns (rung 4: index scope) -- same decision phases 1-4 recorded
- [x] **P1-ENG-U5JJ** Phase 4: B walk-forward: candidate table, purge, per-fold fits, runs, diagnostics, gate
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new `backtest/b_walkforward.py` exactly as the index contract (`FoldModel` value equality D20, `calibration` drops NaN labels itself D21, `gate_p6a` changes only the subject for B-linear D22, `passed_nights` traded == `len(run.snapshots) - 1`, five private `walkforward.py` helpers imported read-only D26) and new `tests/test_backtest_b_walkforward.py` (35 tests on synthetic markets: `CandidateTable` rows equal `design_on`; purge -- mutating bars after `tune_end(Y)` leaves fold Y's mask, X, labels and model digest unchanged; folds equal `walkforward.folds`; `train_folds` for both kinds; schedule switches at year starts and a 31 Dec open order keeps its bracket; P4 identity with real tree and ridge `BParams`; `oos_predictions` uses the right fold's model; hand-checked calibration deciles; passed nights equal empty-pick sessions; `gate_p6a` sentences in both kinds and outcomes; two identical calls give `==`; `probe_determinism` True on synthetic data). Does not touch `walkforward.py` or any out-of-scope file. Exit: suite green, 0 skipped (914); purity glob covers the module.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 4 of 7)
  - **Satisfies**: R1 — Labels. Synthetic tests cover every label path. The vectorized labeler agrees with a one-order `sim` run on a seeded sample. Changing a bar after `tune_end(Y)` leaves fold Y's training set unchanged; R3 — P4 identity and no look-ahead, for B and B-linear, with a fixed model. SPY bars dated ≥ S are included; R4 — Walk-forward. The folds are exactly P3b's. Training uses purged labels only. One chained portfolio, whose brackets survive the year boundary. `backtest_wf`'s A2 report stays byte-identical; R5 — Determinism. `==` results and byte-identical files. The gated model is bit-identical across runs and thread counts, or the pre-registered switch to B-linear takes effect; R6 — Purity. The new modules pass the globbing purity test
  - **Depends on**: P1-ENG-CW71, P1-ENG-1OMN, P1-ENG-DKWU
  - **Plan**: `.workflows/plan/P1-ENG-U5JJ.md`
  - **Completed**: 2026-10-03 18:54
  - **Method**: /do
  - **Files**: engine/src/seer_engine/backtest/b_walkforward.py, engine/tests/test_backtest_b_walkforward.py
  - **Decided**:
    - Manual purity grep matches the docstring word 'logging' (b_walkforward.py:3) -> kept the code block verbatim (rung 3: reconciled code block; the AST-based test_strategy_purity.py passes, and walkforward.py:3 has the identical line)
- [x] **P1-ENG-1OMN** Phase 2: B features, ranks, candidates, `StrategyB`
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns additive `mean_window` and `stdev_return_window` in `strategies/indicators.py` (tests in new `tests/test_indicators_b.py`), new `strategies/b.py` exactly as the index contract, `strategies/__init__.py` exports from `b.py` only (never imports `b_model`), and new `tests/test_strategy_b.py` (every feature hand-computed; `prepare_b` vs `design_at` bit-identity; `rank01` ties and n=0/1; ranks from members on d only; SPY features through d, no candidates when SPY missing/short; `picks_from_design` positive-only, symbol tie-break order, invalid-bracket drop; P4 identity over several dates and fake models; no look-ahead incl. SPY bars from S on; SPY never picked; `SPY_SYMBOL == universe.BENCHMARK`; `MIN_DOLLAR_VOLUME == a.DESIGN_PARAMS.min_dollar_volume`). Does not touch `a.py`, `a2.py`, `base.py`, existing indicators, `b_model.py`, `backtest/`. Exit: suite green, 0 skipped (+59: 11 + 48); purity glob covers `b.py`; `import seer_engine.strategies` loads no `sklearn`; `STRATEGY_B_FROZEN` not re-exported (D24).
  - **Status**: completed
  - **Plan Set**: `STRATEGY_B_RANKER_PLAN.md` (phase 2 of 7)
  - **Satisfies**: R2 — Features. Each is hand-computed. The rolling and single-window paths are bit-identical. Ranks use that date's candidates only, ties averaged. SPY features read SPY's bars through `data_date` only; R3 — P4 identity and no look-ahead, for B and B-linear, with a fixed model. SPY bars dated ≥ S are included; R6 — Purity. The new modules pass the globbing purity test
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-ENG-1OMN.md`
  - **Completed**: 2026-10-03 18:49
  - **Method**: /do
  - **Files**: engine/src/seer_engine/strategies/indicators.py, engine/src/seer_engine/strategies/b.py, engine/src/seer_engine/strategies/__init__.py, engine/tests/test_indicators_b.py, engine/tests/test_strategy_b.py
  - **Decided**:
    - Step 3 task creation skipped: peer session impl-strategy-b-ranker-p1 created all 7 tasks (p2 = P1-ENG-1OMN) in the shared worktree, to avoid duplicate tasks from concurrent sessions (tie-break: narrower blast radius)
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
