# Plan: the fold verdict on every run, and a model that learns the fall

**Slug:** fold-verdict-and-fall-label
**Date:** 2026-10-13 08:21:01 +07
**Analysis:** `docs/analyzer/20261013-082101-K09L_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/fold-verdict-and-fall-label`
**Branch:** `feature/fold-verdict-and-fall-label` (base: `origin/main` @ `a737aff`)
**Phases:** 5
**Status:** phases 1, 2 and 3 of 5 complete
**Coordinator:** `orch-fold-verdict-and-fall-label` (swarm; landing is the coordinator's)

---

## Why

The user's request, verbatim:

> docs/plans/HANDOVER_20261013-measure-the-constraint.md
>
> Read that handover first — it is committed on main at a737aff and holds the decided direction,
> the measured numbers behind it, and the four leftover tasks in its section 2.
>
> Produce a plan set for those leftovers, in dependency order. Task 1 (walk-forward as part of
> every lab run verdict) is the highest-value item and must land before another test-window look
> is spent; task 2 (relabel the tree ranker on the forward fall rather than the forward return
> rank) builds on the plumbing already in engine/src/seer_engine/lab/tree_rank.py; tasks 3 and 4
> are cheap and independent.
>
> Binding rules are in section 3 of the handover and in CLAUDE.md: closed records are frozen, lab
> methods are pre-registered by commit before lab run, lab.sqlite migrates on connect so read it
> read-only, never peek at the test window, and mirror any engine constant into web/.

And the handover's own section 2, which is the specification those four tasks come from:

> 1. **Make walk-forward part of every `lab run` verdict.** [...] Methods are still judged on one
>    20-year dev average and then handed a single out-of-sample observation, spent *after* the
>    promote decision. The fold record would have flagged M0022 and M0002 before they burned test
>    looks. Decide explicitly whether a lost fold majority makes a method ineligible or only
>    annotates it; closed trial rows are frozen, so this is a new column/report path, never an
>    edit of recorded rows.
> 2. **Learn the fall, not the pick.** The constraint that binds is drawdown [...] label on
>    forward downside (drawdown over the next quarter, or realised downside vol) rather than
>    forward return rank, and let the output size the book. [...] only the label and the head
>    change. Pre-register as a new method id from `lab next-id`. Every hyperparameter setting
>    tried counts toward N.
> 3. **Price the short-horizon chart model instead of building it.** [...] compute the turnover
>    such a model would need and run that turnover through the fee schedule the simulator already
>    prices (`sim/costs.py`). That is a number that either kills the idea or does not, for about
>    an hour of work.
> 4. **Append a correcting insight to the lab journal.** Insight 217 (M0130) ends "Learning tools
>    do not fix this lab's real problem, the 2008-sized fall, and here they did not even pick
>    better stocks." The second clause is supported; the first is an overreach from one
>    configuration. Insights are append-only — add a newer one narrowing the claim to what M0130
>    tested, in the owner's plain language, no ids or digests.

The measured facts behind all of it: 65% of dev trials beat SPY TR but only 23% keep the fall at
or under 20%; all four spent test looks failed on return, not on drawdown; and the breaches are
worst in 2008 for 103 trials but in 2011 for 51 and 2015 for 50, so no 2008-shaped rule gates them
away.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Make walk-forward part of every `lab run` verdict — a new recorded column plus a report path, never an edit of recorded rows; decide explicitly whether a lost fold majority gates or annotates | 1 |
| R2 | Learn the fall, not the pick: label the tree model on forward downside **as a level** instead of forward return rank, give it market-level inputs to read, let the output size the book by **exposure** rather than selection, and pre-register it as a new method id | 2 (the label, the market columns, the head, and the exposure gate on the real store), 5 (the pre-registration, the run, the journal entry and the write-up) |
| R3 | Price the short-horizon chart model's turnover through `sim/costs.py` instead of building it | 4 |
| R4 | Append a correcting insight narrowing insight 217's first clause to what M0130 actually tested | 3 |

## Scope

**In scope:**

- A new append-only `method_folds` side table in `lab/lab.sqlite` (schema v6 → v7), written by
  `lab run` on both the ordinary and the `--amend` path, read back by `lab show`.
- A lenient, structured `hardgate.fold_verdict(...)` beside the strict `fold_record` — it records
  the *reason* when a record cannot be computed instead of refusing the run.
- A forward-fall label — **a raw level, never a per-date rank** (Decision D13) — and a book-sizing
  head whose cut reads a **market-level** quantity, added to `lab/tree_rank.py` **as new types**,
  with every existing public name in that module left byte-identical. The fall model's feature
  matrix is the ranker's seven rank-normalised columns **plus three un-normalised market-level
  columns**, appended by a new section builder that *composes* `build_section`.
- One new pre-registered lab method (the id `lab next-id` prints; **M0132** today) running the
  fall-labelled, exposure-sizing model on the dev window, recorded, staged and written up.
- A pure `lab/turnover.py` plus a report-only `lab turnover` subcommand that prices a stated
  turnover against `sim.costs.GOTRADE` on the owner's real funding plan, and a write-up.
- One new `insights` row correcting insight 217.
- `lab stage` after every lab change, and `lab/lab.sqlite` + `web/data/lab.json` committed together.

**Out of scope, and why:**

- **The promote gate does not change.** `hardgate.check` already refuses a lost fold majority, and
  `lab test` already refuses any method that is not `promoted`. R1 adds visibility and a record,
  not a second gate (Decision D1).
- **`web/` is not touched, and `store.SNAPSHOT_VERSION` stays at 5.** No engine constant moves, so
  the `test_sean_mirrors.py` mirror rule is not engaged, and publishing the fold verdict to
  `/sera` is work the handover did not ask for (Decision D3).
- **`TreeRankParams`, `TreeRankAllocator`, `TREE_RANK`, `TREE_RANK_FUND`, `build_section`,
  `Section`, `rank_columns`, `PRICE_FEATURES` and `feature_names` are not edited**, and neither is
  any other existing name in `tree_rank.py`. M0130's recorded `config_digest`s depend on them
  (Decision D4). Phase 2 *measured* the exposure: inserting one compare field into `TreeRankParams`
  moves **five** of M0130's six recorded digests (the sixth, `M0130-DV20`, never names that class),
  so this plan's earlier "all six" is five and the conclusion is unchanged.
- **The test window is never read.** No `lab test`, no `lab promote`, and `engine/.research-test`
  is never named in any command, plan, test or document in this set.
- **No new data purchase**, and the §1 real-money bar does not move.
- **No fundamentals variant in the new method, and no fundamentals allocator either.** The EDGAR
  panel starts in 2009; a panel-gated method is all-cash for 13 of the dev window's 20 years and
  the method id burns (Decision D8). Because no method may ever use it, phase 2 exports **no**
  `FALL_SIZE_FUND` and the allocator id `FALLF` is left unclaimed (Decision D14).
- Closed records — past trials, registry pins, past backtest reports, existing lab rows — are
  never edited or reformatted.

## Invariants

Every phase must hold all of these. They are checkable, not aspirational.

1. **The tree builds and the suite is green at the end of each phase.** Run it as
   `cd <worktree>/engine && PYTHONPATH=<worktree>/engine/src
   PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
   /home/miftah/seer/engine/.venv/bin/python -m pytest -q` and quote the **skip count beside the
   pass count**. Without `PG_TEST_URL` 385 tests skip silently and CI fails the run; without
   `PYTHONPATH` pytest imports the main checkout and tests the wrong code. `docker start seer-pg`
   if the container is down. Lint with `/home/miftah/seer/engine/.venv/bin/ruff check engine`
   (CI is bugs only: E9 and F, minus F401).
2. **No recorded row is edited.** `trials`, `trial_moments`, `trial_funding`, `trial_provenance`,
   `method_amendments`, `insights` and the closed registry pins are append-only. A phase that
   needs a new fact adds a row or a table, never an `UPDATE`.
3. **No existing `config_digest` moves.**
   `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`
   is the tripwire and must stay green. `registry._canon` writes every `compare` field of a params
   dataclass into `config_text`, so adding a field to a params class that a recorded trial names
   is a silent record edit.
4. **The test window is never read.** No `lab test`, no `lab promote`, no `--store` pointing at
   `engine/.research-test`, and no phase prints or reasons about a test-window number that is not
   already in the handover.
5. **A lab method is pre-registered by the commit that adds its file**, before `lab run`.
   `runner.preflight` → `registry_problem` refuses an uncommitted or dirty method file. Commit
   style: `lab: M00NN pre-registered — …`, `lab: M00NN rejected (plain reason)`.
6. **`lab.sqlite` migrates on connect, even for a read.** To inspect it without dirtying it, use
   `sqlite3 'file:lab/lab.sqlite?mode=ro' ...` or `store.connect_readonly`. A phase that does dirty
   it must `lab stage` and commit the database rather than leave it modified.
7. **The lab database is committed with `lab stage && git commit` and NO pathspec.** A pathspec
   commit re-reads the working tree and can pick up a newer `lab.sqlite` beside an older
   `lab.json`; the index after `lab stage` is self-consistent by construction. Check
   `git status --short` first so a bare commit sweeps nothing else.
8. **Every other commit is by explicit pathspec, with `-m` BEFORE `--`.** This worktree is shared
   by every phase session and so is its git index. `git add -- <newfile>` first for a file this
   phase creates, then `git commit -m "..." -- <each path>`, then verify with
   `git show --stat HEAD` that the file list equals the allowlist and `git log -1` carries your
   own message. **`git reset --hard`, `git clean`, `git checkout .` and every bare-path form are
   banned**, including in any subagent you dispatch — say so verbatim in the subagent's prompt.
   If you dispatch `pusher`, write the `Co-Authored-By` trailer out verbatim and tell it not to
   substitute its own model name.
9. **`engine/.research/` does not exist in this worktree.** Any `lab run` must pass
   `--store /home/miftah/seer/engine/.research`. Do not rebuild a store; it costs ~30 minutes plus
   a yfinance crawl for nothing.
10. **Owner-facing text is plain.** Journal entries, verdicts and `/sera` prose carry no method
    ids, digests, code identifiers or statistics jargon.
11. **`argparse` `help=` strings are %-interpolated**: a literal `%` must be written `%%`.
    `description=` is not interpolated and must stay single.
12. **Modules carry prose docstrings explaining *why* the code is shaped as it is.** Match the
    surrounding style — this repo's modules argue for themselves, and a new module that does not
    is out of place.
13. **No engine constant is mirrored into `web/` by this set**, because none moves. If a phase
    finds it must move one, it stops and reports rather than editing one side.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | ✅ The fold verdict on every `lab run` | R1 | `engine/lab`, `engine/commands` | 9 | — | HARD | `.workflows/plan/fold-verdict-and-fall-label/phase-1.md` | P1-ENG-W7QD | — |
| 2 | ✅ The forward-fall **level** label and the market-level sizing head | R2 | `engine/lab` | 2 | — | HARD | `.workflows/plan/fold-verdict-and-fall-label/phase-2.md` | P1-ENG-4KJE | — |
| 3 | ✅ The correcting journal entry | R4 | `lab/` | 2 | 1 | EASY | `.workflows/plan/fold-verdict-and-fall-label/phase-3.md` | P1-ENG-RN2P | — |
| 4 | ✅ Price the chart model's turnover | R3 | `engine/lab`, `engine/commands`, `docs` | 5 | 1 | NORMAL | `.workflows/plan/fold-verdict-and-fall-label/phase-4.md` | P1-ENG-H8TC | — |
| 5 | Pre-register, run and record the fall-labelled method | R2 | `engine/lab/methods`, `lab/`, `docs` | 4 | 1, 2, 3 | HARD | `.workflows/plan/fold-verdict-and-fall-label/phase-5.md` | P1-ENG-5VBX | — |

Waves the `Depends on` column yields: **{1, 2}**, then **{3, 4}**, then **{5}**.

**Why 3, 4 and 5 all depend on 1 — the one-way schema door.** Once the committed `lab/lab.sqlite`
is at schema v7, any checkout running v6 code raises `LabError` on connect (`store._migrate`
refuses a version it does not know). Phase 3 appends an insight, phase 4 reads the lab, phase 5
runs a method — every one of them opens that file, so every one of them must be running phase 1's
code when it does. Phase 2 touches no database and is the only true peer of phase 1.

**File ownership is exclusive.** `commands/lab.py` is edited by phases 1 and 4 in disjoint regions
and **phase 1 lands first**; phase 4 quotes that file as it looks *after* phase 1 and anchors every
edit on quoted text rather than on pre-phase-1 line numbers (Decision D16). `lab/lab.sqlite` +
`web/data/lab.json` are committed by phases 1, 3 and 5 **sequentially**, in that order, each with
`lab stage` and a bare commit. `lab/tree_rank.py` is phase 2's alone; `lab/methods/*` is phase 5's
alone; `lab/turnover.py` is phase 4's alone.

### Phase 1 — The fold verdict on every `lab run`
**Satisfies:** R1
**Owns:**
- `engine/src/seer_engine/lab/store.py` — a new append-only `method_folds` table with its frozen
  dataclass, `<X>_COLUMNS`, `CREATE TABLE`, append-only triggers, `insert_folds`, a reader, a
  `_v6_to_v7` step on the migration ladder, and `SCHEMA_VERSION = "7"`. Copy the shape of
  `_AMENDMENTS_TABLE` / `_AMENDMENTS_TRIGGERS` / `insert_amendment` / `amendments_of` exactly.
- `engine/src/seer_engine/lab/hardgate.py` — one new **lenient, structured** `fold_verdict(...)`
  beside the strict `fold_record` and the display-only `summary`: it returns the record's numbers
  **or** the reason it could not be computed, catching `store.LabError` the way `summary` does.
- `engine/src/seer_engine/lab/runner.py` — `run_method` computes the fold verdict **after**
  `insert_trials` and **inside the same `with conn:` transaction** (the connection sees its own
  uncommitted rows, so the just-recorded curves are in the record), writes one `method_folds` row,
  and returns it to the caller.
- `engine/src/seer_engine/commands/lab.py` — `_run` prints the fold verdict as part of the run's
  verdict, with one plain sentence saying what it means for promotion; `_show` prints the recorded
  verdict for a method that has one.
- `engine/tests/` — new tests, and `lab/lab.sqlite` + `web/data/lab.json` migrated and staged.

**Does not touch:** `hardgate.check` or any promote/test rule; `store.snapshot`,
`SNAPSHOT_VERSION` or anything under `web/`; `trial_rows`, `TrialRow.eligible`, `TrialRow.failed`
or `store.verdict`/`published_verdict`; `lab/tree_rank.py`; any method file; `sim/`.

**Exit criteria:**
- `store.SCHEMA_VERSION == "7"`, the ladder runs v1→v7 in one open, and a v7 database opened by
  this code does not migrate again.
- `lab run` on a method records exactly one `method_folds` row, in the same transaction as its
  trials — a rolled-back run leaves neither.
- A lab with **no** `REF-SPY-HOLD` benchmark, or with fewer than `hardgate.MIN_FOLDS` folds, still
  completes the run and records the reason rather than raising. There is a test for this.
- The `--amend` path records a row too.
- `lab show MNNNN` prints the recorded verdict; `lab run`'s stdout carries it.
- `store.snapshot_json` is **byte-identical** before and after the migration on the committed
  database — proved, not asserted, and the proof quoted in the commit body.
- `lab stage` has run; `lab/lab.sqlite` and `web/data/lab.json` are committed together with no
  pathspec; CI's row-for-row check passes.
- The suite is green, with the skip count quoted beside the pass count.

### Phase 2 — The forward-fall **level** label and the market-level sizing head
**Satisfies:** R2
**Owns:**
- `engine/src/seer_engine/lab/tree_rank.py` — **additions only**:
  - a forward-downside measure beside `forward_returns` — the worst peak-to-trough fall over the
    label window, and/or the realised downside volatility over it — reading only bars dated on or
    before the label end, NaN where unmeasurable, written in the same style as `forward_returns`;
  - a label path on `TreeRankPrepared` that returns that measure **as a raw level, with `rank01`
    never applied** (Decision D13), cached the way `labels`/`forward_returns` are and keyed in its
    own dict so it can never collide with the return-rank cache;
  - a **new section builder that composes `build_section`** and appends three **un-normalised,
    market-level** columns — SPY's distance below its trailing 252-session high, SPY's realised
    volatility over the last 60 sessions, and the cross-sectional dispersion of the date's own
    momentum. Each is a per-date scalar broadcast down the rows, so none can change which names
    the model prefers, only how far the whole date's forecast moves;
  - a **new** params dataclass for the fall model, and a **new** allocator whose head turns the
    predicted fall into *exposure* — how much of the book is held — rather than into a pick order,
    by locating the date's **cross-sectional mean** predicted fall in the model's own training
    distribution of date-level means and holding whole slots accordingly;
  - a from-scratch sibling of `targets_with_inputs` for the new allocator, so the prepared path can
    be proved equal to it bit for bit.
- `engine/tests/test_tree_fall.py` (a new sibling module; `test_tree_rank.py` stays byte-identical)
  — the no-look-ahead probes, the prepared-equals-from-scratch identity, the label's correctness on
  a hand-built history, the market columns' shape and movement, the ladder's monotonicity, and the
  determinism of the fit.

**Does not touch:** `TreeRankParams`, `TreeRankAllocator`, `TREE_RANK`, `TREE_RANK_FUND`,
`forward_returns`, `TreeRankPrepared.labels`, `targets_on`, `fit_model`, `TreeModel`,
`FEATURE_LOOKBACK`, `build_section`, `Section`, `rank_columns`, `PRICE_FEATURES`, `feature_names`
or any other existing public name in that module — **not even a reformat**. No method file, no
database, no CLI, no `web/`.

**Exit criteria:**
- `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`
  is green, and the phase's write-up states that M0130's recorded digests were checked and did not
  move. `git diff` on `tree_rank.py` removes **zero** lines.
- **The label is a level (D13):** `fall_labels(...)` is array-equal to `forward_fall(...)`, no
  `rank_columns`/`rank01` is applied to a fall measure anywhere, and two decision dates' mean
  labels differ — which is impossible under a per-date rank label and is therefore the tripwire.
- **The feature matrix carries three un-normalised market-level columns:** the fall section is 10
  columns wide against the ranker's 7, its first 7 are byte-identical to `build_section`'s, each
  appended column is one value repeated down the rows, and each takes at least five distinct values
  across the decision dates.
- The new allocator satisfies the `Allocator`/`MarketAware` protocol contracts the lab enforces,
  and its history-only path targets nothing. **There is no `FALL_SIZE_FUND`** and the allocator id
  `FALLF` is claimed by nothing (Decision D14).
- `prepared == from-scratch` holds bit for bit on a small market, as `tests/test_tree_rank.py`
  already proves for the return-rank path.
- Nothing dated after the decision date is read: the no-look-ahead probes fire, the market columns
  are unchanged by truncating the history at the decision date, and
  `FALL_SIZE.lookback(...) == FALL_FEATURE_LOOKBACK == max(401, 252, 61) == 401 ≤ 473` — **proved
  by the constant's own arithmetic, not asserted** (Decision D18).
- The sizing head moves exposure in steps coarse enough to clear the measuring tape's
  `TARGET_RESIZE_BAND` (20% of a name's **own** target value) — a sizing effect the resize rule
  swallows is a method that never trades. Phase 2 measured the step: a whole slot is **5×** the
  band at every book size, while a weight nudge under 20% of a slot never trades. The head moves in
  whole slots at a fixed `equal_weight(slots)`, never renormalised, and `size=False` is the
  ready-made always-full control.
- **The exposure gate, on the REAL research store** (`--store /home/miftah/seer/engine/.research`,
  which exists only in the main checkout and must **never** be rebuilt): the model's realised
  exposure on each January decision date 2000-2015 takes **at least three distinct values** and
  **2008 is below 2005**, with the `size=False` control flat at `1.000`. **If it does not, phase 2
  reports that and phase 5 does not spend the method id.** Phase 5 keeps its own pre-commit
  re-check; the two are deliberately redundant because the id is irreversible (Decision D13.5).
- The module is pure: no clock, randomness, files, network or printing. `ruff` clean, suite green
  with the skip count quoted.

### Phase 3 — The correcting journal entry
**Satisfies:** R4
**Owns:**
- One new `insights` row, appended with
  `lab insight --kind observation --title "..." --file <body>`, narrowing insight 217's first
  clause — "Learning tools do not fix this lab's real problem, the 2008-sized fall" — to what
  M0130 actually tested: one model family, one label (the next month's return rank), one universe
  (the twenty most-traded big companies), long-only, after Gotrade's real fees, on signals the lab
  already had. The second clause ("here they did not even pick better stocks") is supported and
  stays supported; the entry says so.
- `lab stage`, then `lab/lab.sqlite` + `web/data/lab.json` committed together.

**Does not touch:** insight 217 or any other existing row — insights are append-only, and the
correction is a *newer* entry, never an edit. No engine source, no test, no method file, no
`web/` source.

**Exit criteria:**
- Exactly one new `insights` row exists; `SELECT count(*) FROM insights` is one higher and
  insight 217's `body` is byte-identical to what it was.
- The body is the owner's plain language: no method ids, no digests, no code identifiers, no
  "DSR", no "walk-forward". It names what was tried and what that licenses, in sentences the owner
  reads on `/sera` without a glossary.
- The claim it makes is the handover's own honest sentence: *gradient-boosted recombination of the
  lab's existing signals, in large caps, long-only, after Gotrade fees, adds no picking skill* —
  not "machine learning does not work".
- `lab stage` has run and the two files are committed together with no pathspec; CI's row-for-row
  check passes.
- `store.test_looks(conn)` is unchanged at 4 and `store.dev_trial_count(conn)` is unchanged; both
  quoted in the commit body.

### Phase 4 — Price the chart model's turnover
**Satisfies:** R3
**Owns:**
- `engine/src/seer_engine/lab/turnover.py` (new) — a pure module that takes a book shape (number
  of names, how often it is re-picked, what fraction of it turns over each time) and an equity
  path, and returns what Gotrade's schedule charges for it: fees as a share of equity per year,
  the share of orders that pay the `$0.10` trading-fee floor rather than the rate, and the annual
  return a strategy must add just to break even. Prices every order through
  `sim.costs.fee_parts`; no backtest, no research store, no database, no clock.
- `engine/src/seer_engine/commands/lab.py` — a `turnover` subparser and its **`_HANDLERS`** row
  (`commands/lab.py:2637`; the table is **not** named `COMMANDS` — Decision D15), report-only in
  the shape of `lab names`: it writes no trial, no moments, no funding, no status and no journal
  row, and says so in its output. `%` doubled in every `help=`. **Phase 1 edits `_run` and `_show`
  in this same file and lands first**, so every edit here is anchored on quoted text, never on a
  pre-phase-1 line number (Decision D16).
- `engine/tests/test_lab_turnover.py` (new) — the arithmetic against hand-computed `fee_parts`
  calls, the floor-binding boundary, and a guard that the command records nothing.
- `docs/backtests/2026-10-13-chart-model-turnover.md` — the write-up carrying the number and the
  verdict it implies for a CNN/LSTM short-horizon model.
- `docs/backtests/2026-10-13-chart-model-turnover-grid.csv` — the grid at full precision, written
  by `lab turnover --csv`.

**Does not touch:** `sim/costs.py` or any fee constant; the lab database beyond a read; any
method file; `lab/tree_rank.py`; `web/`.

**Exit criteria:**
- The grid is swept over the horizons a chart model would plausibly trade at (daily, weekly, and
  the monthly cadence the lab already pays for as the control) and the book sizes the lab actually
  uses, on the owner's real funding plan (`sim.contributions.OWNER_MONTHLY`: 10,000,000 IDR to
  start, +5,000,000 IDR on the 25th), at `sim.costs.GOTRADE`'s current regime.
- Every number in the write-up is reproducible by re-running the command, and the write-up names
  the command line that produced it.
- The write-up states plainly whether the fee burden kills a short-horizon chart model or does
  not, and quotes the annual return such a model would have to add before it is level with doing
  nothing — the number the handover asked for.
- `lab turnover` writes nothing: `store.dev_trial_count` and `store.test_looks` are printed before
  and after and are equal, and `git status --short lab/ web/data/` is empty after a run.
- `ruff` clean, suite green with the skip count quoted.

### Phase 5 — Pre-register, run and record the fall-labelled method
**Satisfies:** R2
**Owns:**
- `engine/src/seer_engine/lab/methods/m<NNNN>_<slug>.py` (new) — the method file, where `<NNNN>` is
  whatever `lab next-id` prints at the time (**M0132** as of 2026-10-13; `M0131` is already taken
  by an unrelated idea in the same family). Built on phase 2's **`FALL_SIZE`** allocator and
  **`FallSizeParams`** (the book-size field is `slots`, not `top_n`), modelled on
  `m0130_tree_ranker.py`: a `hypothesis` and an `expected_failure` written **before** any result is
  seen, **five** variants that are the only hyperparameter settings this idea will ever try (three
  model arms and two controls on the same twenty dollar-volume names), and `seen_keys`.
  The `hypothesis` must describe the method **as phase 2 actually builds it** — a raw **level**
  label, three un-normalised market-level feature columns, and a head that reads the date's
  cross-sectional mean against the model's own training distribution. It pre-registers **no
  exposure ladder of its own**: there is none to choose (Decision D13).
- The pre-registration commit — the method file committed on its own, message
  `lab: M<NNNN> pre-registered — …`, **before** any run.
- The run: `lab run M<NNNN> --store /home/miftah/seer/engine/.research`, then `lab stage`, then
  `lab/lab.sqlite` + `web/data/lab.json` committed with no pathspec.
- One plain-language journal entry for the result, and
  `docs/backtests/2026-10-13-learn-the-fall.md` — the write-up, stating the result against the
  pre-registered hypothesis and expected failure both ways round.

**Does not touch:** any engine source outside `lab/methods/` — a bug this run exposes is
**reported, never patched from here**; the test window; `hardgate.check`; `docs/plans/`; another
phase's files.

**Exit criteria:**
- The method id came from `lab next-id` at run time, not from this plan's guess, and the file's
  module number matches its `METHOD.id`.
- The method file was **committed before** `lab run`, in its own commit, and `lab run` did not
  have to be re-run because of an uncommitted-file refusal.
- Phase 2's exposure gate passed before this phase started, and this phase's own pre-commit
  re-check agrees with it. Both outputs are quoted in the write-up. **If either is flat, or 2008 is
  not below 2005, the method id is not spent** (Decision D13.5).
- The variants rank on **price and dividend features only** — no fundamentals variant (the EDGAR
  panel starts in 2009 and would leave the book all-cash for 13 of the dev window's 20 years), and
  there is no fundamentals allocator to name (Decision D14).
- The insight this phase appends is **strictly newer** than phase 3's correction, and neither phase
  asserts an absolute `insights` id or count — only "exactly one higher than my own baseline".
- `lab run` recorded one trial per variant with its `trial_provenance`, `trial_moments` and
  `trial_funding` rows, plus the `method_folds` row phase 1 added, and the printed fold verdict is
  quoted in the write-up.
- The lab's N moved by exactly one method, not by one per hyperparameter setting beyond this
  method's own id: `store.gate(conn)` and `npolicy.dev_method_count` are read and recorded on both
  sides of the run.
- `store.test_looks(conn)` is unchanged at 4, and `git status --short docs/lab/` is empty.
- Trial `n` is contiguous; `lab stage` has run; CI's row-for-row check passes.
- The write-up and the journal entry are in plain language and state the verdict honestly whichever
  way it fell. If the method is rejected, the commit says so: `lab: M<NNNN> rejected (plain reason)`.
- The suite is green with the skip count quoted.

## Reconciliation Log

The five phase planners ran in parallel and could not see one another's work. One round of
reconciliation; the plan files were edited in place.

| # | Class | Conflict | Resolution |
|---|---|---|---|
| C1 | Contract drift / gap | **Phase 2's fall label was `rank_columns(forward_fall(...))`** — a per-date rank. Phase 5's planner flagged (in its own *Requires (3)*) that `tree_rank` already rank-normalises every **feature** per date, so a per-date rank label leaves the prediction distribution near-stationary and the head can only ever select a count that moves with composition noise. The method would have been a selection test wearing a sizing head. | **D13.** Phase 2's `fall_labels` now returns the **raw level**; `rank01` is removed from the fall path entirely, not merely outranked. Every assertion that depended on the label's range being `[0, 1]` was rewritten, and a new tripwire test (`test_two_dates_labels_live_on_a_shared_scale`) goes red if anyone re-adds the ranking. |
| C2 | Gap (consequence of C1) | A level label is worthless if every **feature** is still a per-date rank — the model could not tell 2008 from 2005 and would predict the unconditional mean. No phase owned this. | **D13.** Phase 2 gains `build_fall_section`, which **composes** `build_section` and appends three **un-normalised** market-level columns (SPY's distance below its 252-session high, SPY's 60-session realised volatility, the date's momentum dispersion). `build_section`, `Section`, `rank_columns`, `PRICE_FEATURES` and `feature_names` stay byte-identical, so D4 is untouched. New constant `FALL_FEATURE_LOOKBACK = max(401, 252, 61) = 401 ≤ 473`, written as arithmetic so the "no extra reach" claim is checkable. |
| C3 | Contract drift (consequence of C1) | Phase 2's head compared each **name's** prediction against a row-quantile cut at `slots / (rows / months)` — a per-name test, which cannot express "the whole market is about to fall". | **D13.** The head now reads a market-level quantity: the date's cross-sectional **mean** predicted fall is located in the model's own training distribution of date-level means (`FallModel.levels`, sorted; `cut` is their median) and the book holds `slots - floor(danger * slots)` whole slots. `fall_training_set` gained a `groups` return and `fit_fall_model` a `groups` parameter so the distribution is over **dates**, not rows. Phase 2's D7 mechanics (whole slots at a fixed `equal_weight(slots)`, never renormalised; `size=False` as the always-full control; the cut derived in-sample, never hand-chosen) are kept whole. |
| C4 | Duplicate work / contract drift | `slots` was in `FallSizeParams.model_key()` because the old cut depended on it. Under C3 it no longer does. | Phase 2's **D2c2**: `model_key()` now excludes both `slots` and `size`, exactly as `TreeRankParams.model_key()` excludes `top_n`. One annual refit ladder now serves every book size. The old D2c and its test were rewritten. |
| C5 | Stale measurement | Phase 2's **M5** (exposure histograms, annual cuts) was measured on the prototype C1–C3 replaced. Carrying it forward would have been a plan asserting numbers its own code can no longer produce. | M5 is marked **SUPERSEDED**, the numbers fenced and labelled, and the implementer is told to re-measure before writing any count into a test. The parts C1–C3 do not touch (determinism, prepared-equals-from-scratch, the look-ahead futures) are called out as still carrying. |
| C6 | Unowned risk in the irreversible phase | The exposure measurement that decides whether the head works at all lived **only** in phase 5 (its Step 3) — the one phase that cannot be rolled back, because the method id is spent. | **D13.5.** The measurement is **moved earlier** into phase 2 as exit criterion **M5b**, run on the real store (`/home/miftah/seer/engine/.research`, never rebuilt): exposure on each January decision date 2000-2015 must take ≥ 3 distinct values and 2008 must be below 2005, with the `size=False` control flat at 1.000. A flat head now fails the cheap, revertible phase. Phase 5 **keeps** its own pre-commit re-check and the redundancy is stated as deliberate. |
| C7 | Duplicate work / dead export | Phase 2 created both `FALL_SIZE` (`FALL`) and `FALL_SIZE_FUND` (`FALLF`), but D8 bars phase 5 from pre-registering any fundamentals variant — so `FALL_SIZE_FUND` was an exported allocator no method could ever use, permanently claiming an id. | **D14.** `FALL_SIZE_FUND` is **removed**, along with its id test. Checked first that nothing needs it: `test_allocator_contract` and `test_allocator_ids_are_unique_across_methods` iterate `backtest.registry.REGISTRY` and the candidates of **discovered method files**, and no method file names it. The `"price+fund"` branch stays reachable and is tested by constructing a `FallSizeAllocator("price+fund")` locally; `FALLF` is left free and a test asserts it. |
| C8 | Unmet assumption / name drift | Phase 5 was written before phase 2's plan existed and guessed `FallParams` with a `top_n` field, carrying a "name reconciliation table" of question marks and an instruction to invent an exposure ladder in the method file if phase 2 did not supply one. | Names **settled** from phase 2's Interface Contract and written into phase 5: `FallSizeParams`, `FALL_SIZE`, `QUARTER`, `FALL_FEATURE_LOOKBACK`; the book-size field is **`slots`**. Step 2b became a confirmation step with a filled table and a "stop and report on disagreement" rule. The invent-a-ladder instruction is **deleted** — there is no ladder to choose. `BASE`, `REG`, `FallBookParams`, `SizedVolumeBook.lookback` and the probe script were all updated. |
| C9 | Contract drift in a pre-registration | Phase 5's `hypothesis` and `expected_failure` described the **rank**-label method — i.e. a method that will not exist. A pre-registration that does not describe what was built is worse than none. | Both rewritten: the hypothesis now states the level label, the three un-normalised market columns, and the market-level head; the expected failure's second mode changed from "flat exposure from per-date normalisation" (removed by D13, and now measured before the commit) to "the ladder may be too **coarse** to matter", which is the real residual risk. The module docstring, `seen_keys`, the write-up skeleton and the `Lookback` note follow. A new exit criterion (3a) pins it. |
| C10 | Requirement creep (considered, refused) | D13 permits a per-date-rank arm to survive as a named control variant in phase 5 "if the variant budget has room" (5 of 6 used). | **Refused, and recorded** (phase 2's **D2f**). Keeping it would mean phase 2 shipping a `label` mode it is supposed to have deleted. Rung 2: phase 5's own variant rule says every setting tried counts and "a sixth would only add a hyperparameter"; rung 4: the index's scope says *a* forward-fall label, singular. The prediction stays in `expected_failure`, where a prediction belongs. |
| C11 | Wrong symbol name | The index and the analysis both called `commands/lab.py`'s dispatch table `COMMANDS`; it is **`_HANDLERS`** (`commands/lab.py:2637`). Phase 4 had already verified this and used the right name; phase 1 repeated the wrong one once, in prose about a non-conflict. | **D15.** Fixed in the index's phase 4 section and in phase 1's Handoffs. Phase 4 needed no change — it names `_HANDLERS` at every edit site and flags the index's error twice. |
| C12 | File collision | Phases 1 and 4 both edit `engine/src/seer_engine/commands/lab.py`. | **D16.** Verified phase 4 already handles it correctly: it declares phase 1 a hard precondition, says its line numbers are pre-phase-1, predicts the `_HANDLERS` table drifting downward, and anchors all four edits (docstring, subparser, handler, dispatch row) on quoted text. The regions are disjoint — phase 1 is in `_show` (~:1399) and `_run` (~:1440-1500); phase 4 is at :70, :351, :2039 and :2646. No edit needed. |
| C13 | Signature change / deleted-then-used | Phase 1 changes `runner.run_method`'s return from `list[Ran]` to `runner.Run`. | **D17.** Verified all four call sites are fixed by phase 1 itself: `commands/lab.py:1489` in its Step 7 (`done = ...; ran = done.ran`), and `tests/test_lab_runner.py:73`, `:283`, `:297` in its Step 9 (each takes `.ran`). Confirmed no other phase reads that return value — phases 2, 3 and 5 never call it, and phase 4 has **zero** occurrences of `run_method` or `runner.Run`. No edit needed. |
| C14 | Ordering / dependency agreement | Each phase's own `Depends on` preamble had to match the index and the one-way schema door. | Verified: phase 1 "none", phase 2 "none", phase 3 "Phase 1", phase 4 "Phase 1", phase 5 "Phase 1, 2, 3" — all agree with the index. The index now states the schema-door reason explicitly in the Phases section. |
| C15 | File collision (sequential) | Phases 1, 3 and 5 all commit `lab/lab.sqlite` + `web/data/lab.json`. | Confirmed sequential by the dependency graph (1 → 3 → 5) and that each uses `lab stage` + a **bare** commit. Phase 5 expects phase 3's insight already present (its Step 1 looks for it as the newest row) and asserts **no** `insights` count — only `dev_trial_count` 394 → 399 and `test_looks` 4. A near-side `insights` read was added to phase 5's Step 6 and a note to Step 9a so its only claim is "exactly one higher than my own baseline". |
| C16 | Contract drift (within phase 3) | Phase 3 said "do not hardcode the insight id, read it from stdout", then hardcoded **219** in its verification table and three commands. | Fixed in place: the table now reads "the Step 1 baseline → baseline + 1", the commands use `<ID>` or `ORDER BY id DESC LIMIT 1`, and the commit-body line reads `<baseline> -> <baseline + 1>`. |
| C17 | Measurement vs. index | The index's phase 2 exit criterion said "aim for about 315 of actual reach". Phase 2 **measured** that this is unreachable without editing the frozen feature set (`FEATURE_LOOKBACK` is 401 and the ranker's features are untouched), and that the look-ahead probes that matter fire in its own test module on a 1510-session synthetic market with 1109 sessions of room. | **D18.** The index's criterion is replaced by "`FALL_FEATURE_LOOKBACK == max(401, 252, 61) == 401 ≤ 473`, proved by the constant's own arithmetic". The measured phase beats the estimated index (rung 2). |
| C18 | Stale count | The index's scope said M0130's **six** recorded `config_digest`s depend on `TreeRankParams`. Phase 2 measured **five** (M0130-DV20's `ControlParams` never names that class). | Index corrected to five, with the sixth named and the conclusion noted as unchanged — the tripwire fires either way. |
| C19 | Stale file counts | The index's phase table said phase 1 touches 6 files and phase 4 touches 4. | Counted from the phases' own Files tables: phase 1 is **9** (4 source + 3 test + `lab.sqlite` + `lab.json`), phase 4 is **5** (`turnover.py`, `commands/lab.py`, the test module, the write-up, the grid CSV). Corrected. |

**No requirement lost coverage.** R1 → 1, R2 → 2 and 5, R3 → 4, R4 → 3, unchanged from the draft.
No step moved between phases except the exposure measurement (C6), which moved **into** phase 2
without leaving phase 5 — so no `Satisfies` line changed.

## Decisions

Rungs: **1** stated invariant · **2** phase exit criteria / a phase's own measurement · **3** the
plan's code blocks · **4** the index's Why and Requirements · **5** the user's raw input · **6** the
surrounding code's convention.

| # | Fork | Choice | Rung |
|---|---|---|---|
| **D13** | The fall label: a per-date cross-sectional **rank** of the forward fall (phase 2 as drafted) vs. the **raw level** (phase 5's objection). | **The level.** `rank01` is removed from the fall path entirely. With rank features *and* a rank label the prediction distribution is near-stationary across dates by construction: a fixed cut would select a count varying only through composition noise, and in October 2008 the per-date ranks are still uniform, so the label cannot encode "all of them" even in principle — a selection test wearing a sizing head, which is the exact mistake the handover is correcting M0130 for. | **5** — the user's raw input and `docs/plans/HANDOVER_20261013-measure-the-constraint.md` §2.2: *"Re-point the model at **exposure** instead of **selection**: label on forward downside … and let the output size the book."* A per-date rank label cannot satisfy that sentence. |
| **D13.1** | Having chosen a level label, does the feature matrix stay all-ranks? | **No.** `build_fall_section` **composes** `build_section` and appends three un-normalised market-level columns (SPY's distance below its 252-session high; SPY's 60-session realised volatility; the date's momentum dispersion), each a per-date scalar broadcast down the rows. Without them the model has no level to read and the level label buys nothing. `build_section`, `Section`, `rank_columns`, `PRICE_FEATURES`, `feature_names` stay byte-identical, so D4 is unchanged and still binding. | **5**, then **1** — the same handover sentence, bounded by the invariant that no recorded `config_digest` may move. |
| **D13.2** | The head's test: a per-name cut vs. a market-level quantity. | **Market-level.** The date's cross-sectional **mean** predicted fall is located in the model's own training distribution of date-level means; the book holds `slots - floor(danger * slots)` whole slots. Monotone, both ends reachable, and **no number in it was chosen** — it is the model's own in-sample empirical CDF, so nothing was read off the dev window. Phase 2's other mechanics are kept whole: whole slots at a fixed `equal_weight(slots)` never renormalised (its D7 measurement: an entry or exit is exactly 5× `TARGET_RESIZE_BAND` at every book size, while a weight nudge under 20% of the slot never trades), and `size=False` as the ready-made always-full control. | **2** — phase 2's own D7 measurement settles the step size; the level requirement comes from D13. |
| **D13.3** | `slots` in `model_key()` or not, once the cut no longer depends on it. | **Out**, together with `size` — exactly as `TreeRankParams.model_key()` leaves `top_n` out. The fall params no longer differ from the ranker's in this respect, and one refit ladder serves every book size. | **6** — the surrounding module's own convention. |
| **D13.4** | A per-date-rank label kept as a named control variant in phase 5 (D13 permits it "if the budget has room") vs. dropped outright. | **Dropped.** Keeping it would mean phase 2 shipping a `label` mode it is supposed to have deleted, and phase 5's own rule is that every setting tried counts and "a sixth would only add a hyperparameter". The prediction that a rank label gives flat exposure stays in `expected_failure`, which is where a prediction belongs when the design that would produce it is not being built. | **2**, supported by **4** — phase 5's variant rule, and the index's scope saying *a* forward-fall label, singular. |
| **D13.5** | Where the "does the head actually move exposure" measurement lives: phase 5 (as drafted) or phase 2. | **Phase 2, as exit criterion M5b**, on the real store (`/home/miftah/seer/engine/.research`, never rebuilt): exposure on each January decision date 2000-2015 must take ≥ 3 distinct values **and** fall in 2008, with the `size=False` control flat at 1.000. A flat head must fail the cheap, revertible phase rather than the one that spends an irreversible method id. **Phase 5 keeps its own pre-commit re-check and the redundancy is deliberate.** | **1** — the lab's append-only invariant: `trials`, `methods` and `insights` are append-only by trigger and the method id is spent the moment `lab run` exits 0. A check that can only fail after that is not a check. |
| **D14** | Export `FALL_SIZE_FUND` (id `FALLF`) or not. | **Not.** D8 bars phase 5 from pre-registering any fundamentals variant (the EDGAR panel starts in 2009; a panel-gated method is all-cash for 13 of the dev window's 20 years and the id burns), so it would be an exported allocator no method can use, claiming an id for ever. Verified nothing needs it first: the lab's protocol tests iterate the registry and **discovered method files**, and no method file names it. The `"price+fund"` branch stays reachable and tested by local construction; `FALLF` is left free, asserted by a test. | **4** — the index's own scope bullet (D8) makes the export unusable by construction. |
| **D15** | Is `commands/lab.py`'s dispatch table `COMMANDS` or `_HANDLERS`? | **`_HANDLERS`** (`commands/lab.py:2637`). Phase 4 verified it against the source. The index and the analysis were wrong; both the index and phase 1's one prose mention are corrected. | **6** — the source is the authority on its own names. |
| **D16** | Phases 1 and 4 both edit `commands/lab.py`. Who owns it, and how does the later one avoid quoting stale code? | **Phase 1 lands first**; phase 4 treats it as a hard precondition, re-reads the file after phase 1, and anchors every edit on quoted text rather than on pre-phase-1 line numbers. The regions are disjoint (phase 1: `_show` ~:1399 and `_run` ~:1440-1500; phase 4: :70, :351, :2039, :2646). Verified phase 4 already does all of this; no edit was needed. | **2** — phase 4's own *Before you start* section already states and justifies it. |
| **D17** | `run_method`'s return type moves from `list[Ran]` to `runner.Run`. Does any other phase assume the old one? | **No.** All four call sites are fixed inside phase 1 (`commands/lab.py:1489` in its Step 7; `tests/test_lab_runner.py:73`, `:283`, `:297` in its Step 9). Phases 2, 3 and 5 never call it; phase 4 has zero occurrences of `run_method` or `runner.Run`. No edit was needed. | **3** — the plans' own code blocks. |
| **D18** | Phase 2's lookback target: the index's "aim for ~315 of actual reach" vs. phase 2's measured 401. | **401, proved as arithmetic.** `FALL_FEATURE_LOOKBACK = max(FEATURE_LOOKBACK, MARKET_HIGH_N, MARKET_VOL_N + 1) = max(401, 252, 61) = 401 ≤ 473`. 315 is unreachable without editing the frozen feature set, and the look-ahead probes that matter fire in phase 2's own test module on a 1510-session synthetic market with 1109 sessions of room. | **2** — a phase measurement beats an index estimate. |
| **D19** | Phase 3's insight id: hardcode 219, or read it back? | **Read it back.** Phase 3 said both; the hardcoded half is removed from its verification table and commands. Phase 5 likewise asserts only "exactly one higher than my own baseline", never an absolute, because phases 3 and 5 both append and a peer session may too. | **2** — phase 3's own stated invariant ("exactly one higher at the end, not 219") against its own table. |

## Open Questions

**None.** Every fork was decided above, and no branch of any of them was irreversible — the one
irreversible act in the set (phase 5 spending a method id) is now gated by a measurement that runs
two phases earlier, in a phase that reverts cleanly (D13.5). Every `R` in the Requirements table is
served by at least one phase.

## Rollback

- **Per phase:** each phase is one or more commits bounded by an explicit pathspec, so
  `git revert <sha>` backs it out. **Never** `git reset --hard` in this worktree — peers' work in
  progress lives in the same tree.
- **Phase 1 is the one with a one-way edge.** Once the committed `lab/lab.sqlite` is at schema v7,
  older code refuses to open it (`store._migrate` rejects an unknown version). Reverting phase 1's
  source without also reverting the database commit leaves the lab unopenable. Back the two out
  **together**, oldest last, and confirm `store.schema_version` reads `"6"` afterwards.
- **Phase 5 cannot be rolled back.** `trials`, `methods` and `insights` are append-only by trigger
  and the method id is spent. That is the lab's design, not a defect: an idea that ran is counted.
  The mitigation is in front of it, not behind — the pre-registration commit, the fixed variant
  list, and the no-fundamentals rule.
- **Phases 3 and 4** revert cleanly: phase 3's insight row can be superseded by another append
  (never deleted), and phase 4 adds only new files plus one subparser.
- **The whole set:** the branch is `feature/fold-verdict-and-fall-label` off `a737aff`. Deleting
  it discards every source change; the lab database commits would have to be reverted on `main`
  separately if they had already been landed there.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/FOLD_VERDICT_AND_FALL_LABEL_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/FOLD_VERDICT_AND_FALL_LABEL_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/FOLD_VERDICT_AND_FALL_LABEL_PLAN.md
