# Code Analysis: the four leftovers of HANDOVER_20261013-measure-the-constraint

**Type:** Feature Implementation (three features + one journal append)
**Date:** 2026-10-13 08:21:01 +07
**Session ID:** 20261013-082101-K09L
**Plan:** `docs/plans/FOLD_VERDICT_AND_FALL_LABEL_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/seer/fold-verdict-and-fall-label`, branch `feature/fold-verdict-and-fall-label` (base `origin/main` @ `a737aff`)

---

## User Input

### Original User Request

```
docs/plans/HANDOVER_20261013-measure-the-constraint.md

Read that handover first — it is committed on main at a737aff and holds the decided direction,
the measured numbers behind it, and the four leftover tasks in its section 2.

Produce a plan set for those leftovers, in dependency order. Task 1 (walk-forward as part of
every lab run verdict) is the highest-value item and must land before another test-window look
is spent; task 2 (relabel the tree ranker on the forward fall rather than the forward return
rank) builds on the plumbing already in engine/src/seer_engine/lab/tree_rank.py; tasks 3 and 4
are cheap and independent.

Binding rules are in section 3 of the handover and in CLAUDE.md: closed records are frozen, lab
methods are pre-registered by commit before lab run, lab.sqlite migrates on connect so read it
read-only, never peek at the test window, and mirror any engine constant into web/.
```

### User-Provided Context

The handover `docs/plans/HANDOVER_20261013-measure-the-constraint.md` (committed at `a737aff`) is
the specification. Its section 2 carries the four tasks verbatim; its section 3 carries the rules.
The measured facts it supplies, which the plan is built on:

- 394 dev trials with a recorded return. 256 (65%) beat SPY TR; only 92 (23%) keep the fall at or
  under 20%; 69 clear both; 22 are fully eligible across 11 methods. **The fall is the binding
  constraint, not the pick.**
- All four spent test-window looks failed on `beats SPY TR`, and not narrowly. M0022-W-TV14 went
  DSR 0.912 on dev to 0.136 on test; M0002-REL-85 went 0.854 to 0.204.
- Of the 302 dev trials breaching 20%, the worst year is 2008 for 103, but **2011 for 51 and 2015
  for 50** — so the drawdown problem cannot be gated away by a 2008-shaped rule.
- M0130 (the tree ranker) licenses only this sentence: *gradient-boosted recombination of the
  lab's existing signals, in large caps, long-only, after Gotrade fees, adds no picking skill.*

### User-Provided Files

None marked with `@`. The handover named `engine/src/seer_engine/lab/tree_rank.py`,
`engine/src/seer_engine/lab/walkforward.py` and `engine/src/seer_engine/sim/costs.py`.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Make walk-forward part of every `lab run` verdict. Decide explicitly whether a lost fold majority makes a method ineligible or only annotates it. A new column/report path, never an edit of recorded rows. Must land before another test-window look is spent. |
| R2 | Learn the fall, not the pick: re-point the tree model at *exposure* instead of *selection* — label on forward downside rather than forward return rank, and let the output size the book. Pre-register as a new method id from `lab next-id`. |
| R3 | Price the short-horizon chart model instead of building it: compute the turnover such a model would need and run that turnover through the fee schedule the simulator already prices (`sim/costs.py`). |
| R4 | Append a correcting insight to the lab journal narrowing insight 217's first clause to what M0130 actually tested, in the owner's plain language. |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** The lab judges a method on one twenty-year dev average and
then spends a single out-of-sample look on it, *after* the promote decision. `lab/walkforward.py`
already exists and already gates `lab promote` through `hardgate.check`, but a researcher running
`lab run MNNNN` never sees a fold record — it appears only when they later try to promote. R1
closes that gap by computing and recording the fold verdict at run time. R2 changes what the tree
model is asked to predict: the next quarter's *fall*, not the next month's return rank, with the
prediction sizing the book instead of picking its names. R3 replaces a CNN/LSTM build with an hour
of fee arithmetic that either kills the idea or does not. R4 corrects an overreaching sentence in
the published journal.

**Success Criteria.**

- R1: every `lab run` (ordinary and `--amend`) ends by computing the method's walk-forward record
  against the lab's shared geometry, recording it in an append-only side table, and printing it
  in the run's verdict. `lab show MNNNN` prints the recorded record. A run on a lab with no
  benchmark, thin geometry or a price mismatch records the *reason* and still succeeds. No
  recorded `trials` row is edited; `trials.eligible` keeps its present meaning.
- R2: `lab/tree_rank.py` grows a forward-fall label and a sizing head **beside** its existing
  types, with `TreeRankParams`, `TreeRankAllocator`, `TREE_RANK` and `TREE_RANK_FUND` untouched,
  so M0130's six recorded `config_digest`s still reproduce. A new method file, committed as its
  pre-registration, runs on the dev window and is recorded, staged and written up.
- R3: a pure module plus a report-only `lab` subcommand that prices a stated turnover against
  `sim/costs.GOTRADE` on the owner's real funding plan, and a write-up carrying the number.
- R4: one new `insights` row, append-only, plain language, no ids or digests; `lab stage` run and
  `lab.sqlite` + `web/data/lab.json` committed together.

**Key Considerations.**

- **The schema bump is a one-way door for peers.** `store._migrate` refuses a version it does not
  know, so once R1 moves the committed `lab/lab.sqlite` from v6 to v7, every lab command on older
  code raises `LabError`. Code and migrated database must land in one commit, and every later
  phase that touches the lab must run on the new code.
- **`registry._canon` puts every compare field of a params dataclass into `config_text`.** Adding
  one field to `TreeRankParams` would move M0130's six recorded digests and fail
  `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`.
  This is "closed records are frozen" in mechanical form.
- **The fold record is a method-level, time-varying property.** It is computed from every recorded
  curve of the method plus the benchmark, so an amendment recorded tomorrow changes it. A per-trial
  `eligible` column that depended on it would stop being reproducible, which is exactly what
  `store.verdict`'s "comparable across time" promise forbids.
- **The lab must still bootstrap.** `hardgate.pin_dev_store` is explicit: *"a fresh lab has to be
  able to run before it has a benchmark"*. A fold verdict that refused a run without geometry would
  break that.
- **The research store is not in worktrees.** `engine/.research/` exists only in
  `/home/miftah/seer`; any `lab run` from the worktree must pass
  `--store /home/miftah/seer/engine/.research`.
- **The worktree shares one git index with every peer phase.** Commit by pathspec with `-m` before
  `--`, `git add --` a new file first, and never `reset --hard`, `git clean` or `git checkout .`.
  The one exception is the lab database commit, which must be `lab stage && git commit` with **no**
  pathspec so the staged `lab.json` is the export of the staged `lab.sqlite`.
- **Tests in a worktree need `PYTHONPATH` and `PG_TEST_URL`**, or they silently test the main
  checkout and silently skip 385 tests.

**Assumptions stated.**

- The next free method id is whatever `lab next-id` prints at run time. It is **M0132** today:
  `M0131` is already registered as an `idea` in the same `stock-ml-ranker` family ("A slower target
  for the learned ranker"), and it is a different question from R2's.
- R2's method ranks on price and dividend features only. The EDGAR panel starts in 2009, so a
  panel-gated variant is all-cash for 13 of the dev window's 20 years and the method id burns.
- No `lab test`, no `lab promote`, and `engine/.research-test` is never named anywhere in this set.

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/plans/HANDOVER_20261013-measure-the-constraint.md` — the specification
- `engine/src/seer_engine/lab/tree_rank.py` (832 lines) — R2's plumbing
- `engine/src/seer_engine/lab/walkforward.py` (311 lines) — R1's evaluator
- `engine/src/seer_engine/sim/costs.py` — R3's fee schedule

### Discovered Related Files

- `engine/src/seer_engine/lab/runner.py` (1128) — `run_method` at :586, `trial_rows` at :451
- `engine/src/seer_engine/lab/hardgate.py` (1297) — `geometry` :595, `fold_record` :792,
  `variant_record` :840, `summary` :1180, `check` :1216, `trial_deposits` :520
- `engine/src/seer_engine/lab/store.py` (2712) — schema, migrations, snapshot
- `engine/src/seer_engine/commands/lab.py` (2662) — `_run` :1440, `_show` :1399,
  `_walkforward` :2178, `_names` :1991, `_insight` :2572, `_stage` :2582, `_next_id` :2607
- `engine/src/seer_engine/lab/method.py` (235) — `config_text` :43, `config_digest` :51,
  `Amendment`, `Method`, `discover`, `source_sha`
- `engine/src/seer_engine/backtest/registry.py` — `_canon` :302, `candidate_digest` :350
- `engine/src/seer_engine/commands/backtest_dev.py` — `registry_problem` :486
- `engine/src/seer_engine/lab/name_count.py` (524) — the shape every report-only lab module copies
- `engine/src/seer_engine/lab/methods/m0130_tree_ranker.py` — the method-file template for R2
- `engine/src/seer_engine/sim/rules.py` — `RESIZE_BAND` :58, `TARGET_RESIZE_BAND` :62,
  `MONTHLY_HOLD_FRAC_GOTRADE_TBAND`
- `engine/src/seer_engine/sim/book.py` — `equal_weight` :196, `Target` :206
- `engine/tests/test_lab_methods.py`, `test_lab_hardgate.py`, `test_lab_walkforward.py`,
  `test_tree_rank.py`, `test_lab_runner.py`, `test_lab_snapshot.py`, `test_sim_costs.py`
- `engine/tests/test_sean_mirrors.py` — the engine↔web mirror guard, and its stated preference
  order: **publish, don't mirror**

---

## Current Dataflow

### Entry Point: `lab run MNNNN`

**Location:** `engine/src/seer_engine/commands/lab.py:1440` (`_run`)
**Trigger:** CLI subcommand, dispatched from the `COMMANDS` table at :2637
**Input:** `args.method`, `args.store`, `args.amend`, `args.allow_coverage`

Sequence as it stands today:

1. `research.declared_purpose(args.store)` — a survivorship-check store is refused before anything
   is discovered or loaded.
2. `method.discover()` → `(METHOD, path)`.
3. `runner.preflight(conn, method, path, amend=...)` (`runner.py:226`) — refuses an uncommitted
   file (`registry_problem`, which runs `git status --porcelain` and `git ls-files` on the file's
   own directory, so a feature-branch commit satisfies it), a variant not priced at Gotrade's real
   fees, a method that has already run without `--amend`, a missing parent, and any candidate whose
   `config_digest` already has a dev trial.
4. `research.load_store(...)`.
5. `hardgate.pin_dev_store(conn, data.price_fingerprint)` (`hardgate.py:745`) — refuses a store
   whose prices are not the benchmark's (D10). Silent when the lab has no benchmark trial at all.
6. `runner.preflight_data(...)` — the fundamentals coverage floor.
7. `runner.run_method(...)` (`runner.py:586`).
8. `_show(conn, Namespace(method=...))` then a line naming `store.dev_trial_count` and
   `store.test_looks`.

**There is no walk-forward anywhere in this path.** `grep -n "walkforward" commands/lab.py` finds
it only in `_walkforward` (the report) and in two help strings.

### Processing chain: `runner.run_method`

**Location:** `engine/src/seer_engine/lab/runner.py:586`

1. `refuse_survivorship_store(data, ...)`, then `preflight` again.
2. `dev.run_registry(...)` with `contributions=OWNER_MONTHLY, initial_idr=INITIAL_IDR`; each result
   appends `(DevRow, month_end_curve(snapshots))` and `metrics.external_cashflows(result)`.
3. `store.begin_immediate(conn)`, then one `with conn:` transaction:
   - `preflight` re-checked (amendment race).
   - `trial_rows(...)` (`runner.py:451`) builds the `TrialRow`/`MomentsRow`/`FundingRow` triples.
     The luck N is `store.pending_gate(conn, method.id, len(results)).n`; the variance is the
     sample variance of daily Sharpes over every recorded dev trial plus this batch;
     `failed` gains `store.DSR_LABEL` when `dsr < store.DSR_MIN`; `eligible = not failed`.
   - `store.add_method` / `store.update_method` as needed.
   - `store.insert_trials` → the assigned `n`s.
   - `store.insert_moments`, `store.insert_funding`, `store.insert_provenance`, each stamped with
     those `n`s **in the same transaction**.
   - `store.update_method(..., source_sha=..., status=...)` on the ordinary path, or
     `store.insert_amendment(...)` on the `--amend` path (status untouched).
   - `store.mark_seen(...)` per `method.seen_keys`.
4. Returns `list[Ran]`.

`status` is `"dev-eligible"` when **any** trial is eligible, else `"rejected"`.

### The walk-forward evaluator (pure)

**Location:** `engine/src/seer_engine/lab/walkforward.py`

- `MIN_TRAIN_YEARS = 10`, `EVAL_YEARS = 3`, `MIN_EVAL_MONTHS = 12`.
- `folds(months)` → expanding-train / fixed-evaluate `Fold`s.
- `measure(curve, start, end, deposits)` → `Slice(months, total_return, cagr, max_drawdown, mar)`,
  **de-funded before the cut** via `backtest.regime.defunded`.
- `pick(curves, fold, first, deposits)` → the candidate the training slice ranks best by MAR.
- `evaluate(curves, bench, folds, deposits)` → one `FoldPick` per fold.
- `Record(method, picks)` with `.scored`, `.won`, `.majority`, `.stable`, `.summary()`.
- `buy_signal(dev_eligible, record, high_coverage_edge, family_failed)` → the four-condition
  survivorship-data purchase signal.

No I/O, no database, no clock. It re-runs nothing — every fold is a date slice of
`trials.curve_json` rows already in the database.

### Where the fold record is already enforced

**Location:** `engine/src/seer_engine/lab/hardgate.py:1216` (`check`), called by `_promote`
**before** `prereg.promote_method`.

- `geometry(conn)` (`:595`) reads the first `REF-SPY-HOLD` dev trial carrying a curve, cuts
  `wf.folds` from it, and **raises** when there is none or when fewer than `MIN_FOLDS = 4` folds
  come out.
- `fold_record(conn, method_id, geo)` (`:792`) — every dev curve of the method (`_dev_curves`),
  de-funded by `trial_deposits`, scored by `wf.evaluate`. Raises on no curve and on a price
  fingerprint mismatch (D10).
- `check` then refuses: fewer scoreable folds than the geometry yields; fewer than `MIN_FOLDS`;
  `not record.majority`; the same two for the *promoted variant alone* (`variant_record`, D11);
  and finally `failed_kin` (D4/D12/D14).
- `summary(conn, method_id, geo)` (`:1180`) is the **lenient** sibling — it catches `store.LabError`
  and returns the reason as display text. `lab status` uses it.

So the fold majority already stands between a method and a test-window look: `lab test`
(`runner.preflight_test`) refuses any method that is not `promoted`, and the only edge into
`promoted` runs through `hardgate.check`. What is missing is **visibility and a record at run
time**, which is what R1 adds.

### Data persistence: the lab database

**Location:** `engine/src/seer_engine/lab/store.py`

- `DB_PATH = $SEER_LAB_DB or <repo>/lab/lab.sqlite`; `SCHEMA_VERSION = "6"`.
- `connect(path)` migrates on connect; `connect_readonly(path)` never does.
- `_migrate` (`:733`) is a ladder, v1→v6, under `BEGIN IMMEDIATE`, re-reading the version after
  the lock so only the first of several parallel sessions migrates. **A version it does not know
  is refused**, so a v7 database read by v6 code raises `LabError`.
- Side tables, each append-only by trigger and each the template for a new one:
  `trial_moments` (v3), `trial_funding` (v4), `trial_provenance` (v5), `method_amendments` (v6).
  Each has a `<X>_COLUMNS` tuple derived from its dataclass `fields(...)`, an `insert_<x>` and a
  `<x>_of` reader.
- `trials` is append-only; `insert_trials` returns the assigned `n`s.
- `snapshot(conn)` builds `web/data/lab.json` (`SNAPSHOT_VERSION = 5`). It reads `methods`,
  `trials`, `insights`, `ideas_seen` and resolves the gate block from the live constants at export
  time — the "publish, don't mirror" pattern `test_sean_mirrors.py` names as the preferred one.
  **A new side table changes none of those bytes.**

### The tree ranker

**Location:** `engine/src/seer_engine/lab/tree_rank.py`

- `TreeRankParams` (`:209`) — `top_n, feature_set, learning_rate, max_iter, max_leaf_nodes,
  min_samples_leaf, l2, train_start, min_train_months, horizon, seed`; `model_key()`, `as_dict()`.
- Calendar: `month_ends`, `label_end(t, horizon)` (the 21st NYSE session after `t`),
  `year_end`, `anchor_for(d)` (annual refit at the last session of the year).
- `TreeInputs` (`:330`), `Section` (`:383`), `rank_columns` (`:398`), `build_section` (`:457`).
- **`forward_returns(history, section, end)` (`:501`)** — each symbol's return from
  `section.day`'s close to its last close on or before `end`. Reads only bars dated ≤ `end`.
- `TreeModel` (`:528`), `fit_model(X, y, params)` (`:555`) — `HistGradientBoostingRegressor`,
  `early_stopping=False`, under `threadpool_limits(1)`; an all-blank column is fitted as a constant.
- `TreeRankPrepared` (`:587`) — caches sections by `(date, universe)`, label dates by
  `(date, horizon)`, forward returns by `(date, label_date)`, models by
  `(anchor, params.model_key())`.
  - **`labels(t, horizon)` (`:651`)** = `rank_columns(forward_returns(...).reshape(-1,1))[:,0]`.
    **This is the single line R2 re-points.**
  - `training_dates`, `training_set`, `model`, `model_on`.
  - **`targets_on(members, data_date, params)` (`:695`)** — predict, sort descending, take the
    `top_n` finite predictions at `equal_weight(top_n)`. **This is the head R2 replaces.**
- `TreeRankAllocator` (`:733`); `TREE_RANK = TreeRankAllocator("price")`,
  `TREE_RANK_FUND = TreeRankAllocator("price+fund")`.
- `targets_with_inputs(...)` (`:815`) — the from-scratch path the prepared path must equal bit for
  bit (`tests/test_tree_rank.py`).
- `FEATURE_LOOKBACK = 401` — under the smoke fixture's 473-bar cap, so a new allocator reusing it
  still passes `test_lab_methods.py::test_candidate_runs_a_smoke_window`.

### The fee schedule

**Location:** `engine/src/seer_engine/sim/costs.py`

- `GotradeSchedule` / `FeeRegime` / `FeeParts`; `GOTRADE` (`:199`) holds the fitted regimes.
- `fee_parts(side, amount, on=None)` (`:241`) — one order's trading + regulatory + PPN, to the
  cent, in `Decimal`. `on=None` means the current regime, which is what every backtest uses.
- `gotrade_cash(side, price, shares)` (`:248`), `gotrade_shares_for(budget, price, quantum)` (`:260`).
- Current regime: trading 0.2% half-up with a **$0.10 minimum**, regulatory 0.054% rounded up
  capped at $0.11, a sell adds an uncapped 0.04%, PPN 11% of the two, rounded half-down.

**Corrected after phase 4 measured it.** This section originally read "the `$0.10` floor is the
whole of R3's answer". It is not. The floor is a *transient*: it binds months 0–1 at 20 names and
months 0–3 at 30, never at 10, with an exact boundary at a slot of `$47.49` (binds) versus
`$47.50` (`0.2% × $47.50 = $0.095`, half-up to exactly `$0.10`, tying the minimum). The owner's
equity grows under `OWNER_MONTHLY`, so the floor's bite shrinks away.

What actually kills a short-horizon model is the plain rate afterwards — **0.503% per round trip**
— multiplied by the cadence. Measured through `fee_parts` at `GOTRADE`'s current regime: the
cheapest conceivable daily book (one name of twenty swapped per session) must add **7.03%/yr**
just to break even, about what the market itself returns; a full daily re-pick of 20 names must
add **290.45%/yr**; weekly at full churn **32.49%/yr**; against the monthly control at 25% churn,
**1.63%/yr**. The floor still deserves its own column in the report because it dominates the first
months and would otherwise be mistaken for the steady state.

### Exit points

- `lab run` → trials + side rows in `lab.sqlite`, the method's status, stdout.
- `lab stage` (`commands/lab.py:2582`) → `web/data/lab.json` written under `BEGIN EXCLUSIVE` and
  `git add`ed beside the database, both in the database's own checkout
  (`store.snapshot_path` resolves from the DB path, not from this code's).
- `web/data/lab.json` → `/sera` (read-only). CI checks the two agree row for row.

---

## Key Data Structures

### `store.TrialRow` — `store.py:~950`, `TRIAL_COLUMNS` at `:1027`
Append-only. `failed` is a `"; "`-joined label string; `eligible = not failed`;
`dsr` and `n_trials_at_run` are frozen at the run date. **Never edited.**

### `store.MomentsRow` / `FundingRow` / `ProvenanceRow` / `AmendmentRow`
The four existing side-table dataclasses. Each: a frozen dataclass, a `<X>_COLUMNS` tuple built
from `fields(...)`, a `CREATE TABLE IF NOT EXISTS` string, an append-only trigger pair, an
`insert_<x>(conn, rows)` and an `<x>_of(conn, key)`. **The template R1's new table copies.**

### `walkforward.Record` — `walkforward.py:~196`
`method: str`, `picks: tuple[FoldPick, ...]`; `.scored`, `.won`, `.majority`, `.stable`,
`.summary()` → `"3 of 4 folds"` or `"3 of 4 folds, pick changed"`.

### `hardgate.Geometry` — `hardgate.py:573`
`bench: tuple[(date, float), ...]`, `folds: tuple[wf.Fold, ...]`, `bench_n: int`. Global on
purpose — the folds come from `REF-SPY-HOLD`, never from the method under test.

### `tree_rank.TreeRankParams` — `tree_rank.py:209`
**Frozen by consequence.** `method.config_text` writes `params={_canon(c.params)}`, and
`registry._canon` emits `TreeRankParams(top_n=20,feature_set='price',...)` over every `compare`
field. M0130's six recorded `config_digest`s are pinned by
`test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`.

### `sim.costs.FeeParts` — `costs.py:72`
`trading`, `regulatory`, `ppn`, `total`, all `Decimal` to the cent, with `total` checked against
the sum in `__post_init__`.

---

## Dependencies

### Configuration / Environment

- `SEER_LAB_DB` — the lab database a session writes. Parallel sessions share state through it.
- `SEER_RESEARCH_STORE` — the dev store. **Not present in a worktree**; point `--store` at
  `/home/miftah/seer/engine/.research` (fingerprint `399d0d254c7a` as of 2026-10-08).
- `PG_TEST_URL` — without it 385 tests skip silently and CI fails the run.
- `PYTHONPATH=<worktree>/engine/src` — without it pytest imports the **main checkout's** modules.
- `engine/.venv` lives only in the main checkout; the worktree has none.

### External services

None in this work. No network, no Neon, no yfinance. `lab run` reads the local research store;
every other command here is arithmetic over the committed database.

---

## Reference List

Every site that touches what these four tasks change.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `_run` | `commands/lab.py:1440` | def · the run path R1 extends | commands |
| `_show` | `commands/lab.py:1399` | def · prints a method's trials; R1 adds the fold line | commands |
| `_walkforward` | `commands/lab.py:2178` | def · the existing report, unchanged by R1 | commands |
| `_names` | `commands/lab.py:1991` | def · the report-only shape R3 copies | commands |
| `_insight` | `commands/lab.py:2572` | def · R4's writer | commands |
| `_stage` | `commands/lab.py:2582` | def · R1/R2/R4 all end here | commands |
| `_next_id` | `commands/lab.py:2607` | def · R2's id | commands |
| `_HANDLERS` dispatch table | `commands/lab.py:2637` | table · R3 adds a row | commands |
| subparser block | `commands/lab.py:~290-560` | argparse · R3 adds a parser; `%` must be `%%` in `help=` | commands |
| `run_method` | `lab/runner.py:586` | def · R1 records the fold verdict here | lab |
| `trial_rows` | `lab/runner.py:451` | def · untouched by R1 | lab |
| `preflight` | `lab/runner.py:226` | def · the pre-registration refusals | lab |
| `preflight_test` | `lab/runner.py:840` | def · test-window; never reached in this set | lab |
| `wf.folds` / `wf.evaluate` / `wf.Record` | `lab/walkforward.py:92,170,196` | def · R1 reuses, never edits | lab |
| `wf.buy_signal` | `lab/walkforward.py:~270` | def · unchanged | lab |
| `hardgate.geometry` | `lab/hardgate.py:595` | def · R1 reuses; raises without a benchmark | lab |
| `hardgate.fold_record` | `lab/hardgate.py:792` | def · R1 reuses (strict) | lab |
| `hardgate.variant_record` | `lab/hardgate.py:840` | def · D11's per-variant record | lab |
| `hardgate.summary` | `lab/hardgate.py:1180` | def · the lenient display sibling R1 models on | lab |
| `hardgate.check` | `lab/hardgate.py:1216` | def · the promote gate — **R1 does not change it** | lab |
| `hardgate.trial_deposits` | `lab/hardgate.py:520` | def · de-funding, shared by gate and report | lab |
| `hardgate.MIN_FOLDS` | `lab/hardgate.py:~468` | const = 4 | lab |
| `store.SCHEMA_VERSION` | `lab/store.py:86` | const "6" → R1 moves it to "7" | lab |
| `store._migrate` | `lab/store.py:733` | def · R1 appends `_v6_to_v7` | lab |
| `store._AMENDMENTS_TABLE` / `_TRIGGERS` | `lab/store.py:359,371` | sql · the template R1 copies | lab |
| `store.insert_amendment` / `amendments_of` | `lab/store.py:2225,2184` | def · the reader/writer template | lab |
| `store.snapshot` / `SNAPSHOT_VERSION` | `lab/store.py:2580,2414` | def/const · **unchanged** (D3) | lab |
| `store.connect_readonly` | `lab/store.py:588` | def · never migrates — how to read the DB safely | lab |
| `store.add_insight` / `INSIGHT_KINDS` | `lab/store.py:2295,123` | def/const · R4 | lab |
| `tree_rank.forward_returns` | `lab/tree_rank.py:501` | def · R2's sibling is added beside it | lab |
| `TreeRankPrepared.labels` | `lab/tree_rank.py:651` | def · the line R2 re-points | lab |
| `TreeRankPrepared.targets_on` | `lab/tree_rank.py:695` | def · the head R2 replaces | lab |
| `TreeRankParams` | `lab/tree_rank.py:209` | dataclass · **frozen by digest** | lab |
| `TreeRankAllocator`, `TREE_RANK`, `TREE_RANK_FUND` | `lab/tree_rank.py:733,811,812` | class/objects · **not edited** | lab |
| `fit_model` / `TreeModel` | `lab/tree_rank.py:555,528` | def/class · R2 reuses unchanged | lab |
| `FEATURE_LOOKBACK` = 401 | `lab/tree_rank.py:158` | const · under the 473-bar smoke cap | lab |
| `targets_with_inputs` | `lab/tree_rank.py:815` | def · R2 needs a sibling for its own identity test | lab |
| `method.config_text` / `config_digest` | `lab/method.py:43,51` | def · why `TreeRankParams` is frozen | lab |
| `registry._canon` | `backtest/registry.py:302` | def · serialises every compare field | backtest |
| `registry_problem` | `commands/backtest_dev.py:486` | def · the pre-registration commit check | commands |
| `m0130_tree_ranker.METHOD` | `lab/methods/m0130_tree_ranker.py` | method file · R2's template | lab/methods |
| `costs.fee_parts` / `GOTRADE` | `sim/costs.py:241,199` | def/const · R3's whole engine | sim |
| `rules.MONTHLY_HOLD_FRAC_GOTRADE_TBAND` | `sim/rules.py:~273` | const · the fixed measuring tape | sim |
| `rules.TARGET_RESIZE_BAND` = 0.20 | `sim/rules.py:62` | const · 20% of a name's **own** target | sim |
| `book.equal_weight` | `sim/book.py:196` | def · how a slot weight is spelled | sim |
| `contributions.OWNER_MONTHLY` | `sim/contributions.py` | const · 10M IDR + 5M on the 25th | sim |
| `test_every_recorded_configuration_still_digests_to_its_recorded_digest` | `tests/test_lab_methods.py:187` | test · the tripwire on `TreeRankParams` | tests |
| `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` | `tests/test_lab_methods.py:134` | test · the `source_sha` freeze | tests |
| `test_candidate_runs_a_smoke_window` | `tests/test_lab_methods.py:79` | test · the 473-bar lookback cap | tests |
| `test_the_committed_snapshot_is_the_export_of_the_committed_database` | `tests/test_lab_snapshot.py` | test · reads the **working tree** DB, red mid-batch | tests |
| `test_sean_mirrors.py` | `tests/test_sean_mirrors.py` | test · engine↔web mirrors; no constant moves here | tests |
| `web/data/lab.json` | `web/data/lab.json` | data · staged with `lab.sqlite`, CI checks row for row | web |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/lab/store.py` — a new append-only `method_folds` table, its dataclass,
   `COLUMNS`, triggers, `insert_folds`, `folds_of`/`latest_folds`, `_v6_to_v7`,
   `SCHEMA_VERSION = "7"`. **Phase 1.**
2. `engine/src/seer_engine/lab/hardgate.py` — one lenient, structured `fold_verdict(...)` beside
   the strict `fold_record` and the display-only `summary`, so the runner records a *reason* rather
   than crashing on a lab with no geometry. **Phase 1.**
3. `engine/src/seer_engine/lab/runner.py` — `run_method` computes and records the fold verdict in
   the same transaction as the trials, and returns it. **Phase 1.**
4. `engine/src/seer_engine/commands/lab.py` — `_run` prints the fold verdict as part of the run's
   verdict; `_show` prints the recorded one. **Phase 1.** A new `turnover` subparser and
   `COMMANDS` row. **Phase 4.**
5. `engine/tests/` — new tests for the recorded fold verdict (phase 1), the fall label and the
   sizing head (phase 2), the turnover pricing (phase 4).
6. `engine/src/seer_engine/lab/tree_rank.py` — a `forward_drawdown`/downside measure beside
   `forward_returns`, a fall-label path on `TreeRankPrepared`, a new params dataclass and a new
   sizing allocator, and a from-scratch sibling of `targets_with_inputs`. Nothing existing edited.
   **Phase 2.**
7. `engine/src/seer_engine/lab/turnover.py` (new) — the pure turnover-to-fees module. **Phase 4.**
8. `engine/src/seer_engine/lab/methods/m0132_<slug>.py` (new) — R2's pre-registered method file.
   **Phase 5.**
9. `lab/lab.sqlite` + `web/data/lab.json` — migrated to v7 and staged (phase 1); one new insight
   (phase 3); M0132's method row, trials and side rows (phase 5). Always via
   `lab stage && git commit` with no pathspec.
10. `docs/backtests/2026-10-13-*.md` — the turnover write-up (phase 4) and M0132's result write-up
    (phase 5).
11. `.workflows/todos.md` — one task per phase, minted by each phase for itself only.

**Not changed, deliberately:** `hardgate.check` (the promote gate keeps its present rules),
`store.snapshot`/`SNAPSHOT_VERSION`, `web/` (no engine constant moves), any closed trial row,
any past backtest report, `backtest/registry.py`'s pins, and the §1 real-money bar.

**This document describes. The plan files prescribe.**
