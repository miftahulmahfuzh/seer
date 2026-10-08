# Plan: Lab realistic gate — correct N, fund the runner, redo a method honestly

**Slug:** lab-realistic-gate
**Date:** 2026-10-08 13:50:44
**Analysis:** `20261008-135044-N7K3_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/lab-realistic-gate`
**Branch:** `feature/lab-realistic-gate` (base: `origin/main` @ `2b493ee`)
**Phases:** 3
**Status:** planned — reconciled, 6 conflicts resolved
**Coordinator:** —

---

## Why

The owner asked whether a `sera-the-explorer` run today explores methods that consider Gotrade's
fees and his continuous +5,000,000 IDR monthly top-up. Fees: yes, enforced. Funding: no, absent.
He then proposed a skill to purge and redo a method realistically:

> "i just hate it that these old experiments have their own results that do not exactly represent
> how i trade in real life using gotrade. so i am thinking , why not create a skill so i
> specifically target some existing good methods (for example, methods that are included in the
> seer's roster) and cleanly redo it using the realistic approach?"

and, on the luck gate:

> "i fucking hate this DSR bullshit man. redoing the method now will change how their "luck" look
> like. but i dont know anything about statistics or trading, so i will just follow your ideas"

**That objection is correct, and phase 1 removes its cause.** Re-running a method perturbs every
other method's verdict only because `DSR_POLICY = "all-trials"` counts trial rows as independent
looks. The lab's own estimator measures the participation ratio at 2.338 — every method holds US
large-cap equity, so 126 rows are about 2.3 independent bets. Under `methods` a new twin adds 1 to
N instead of ~16, and the owner's objection dissolves rather than being worked around.

The purge he proposed is the one part that cannot be built: `trials_no_delete`, `trials_no_update`
and `methods_no_delete` forbid it at the schema level, and deleting trials would LOWER N and
retroactively inflate every other method's DSR — the exact self-deception the gate exists to
prevent. Phase 3 therefore mints a variation twin, which `real_costs.py` already names as the only
legitimate route and which `sera-the-explorer` already mandates ("Promote the twin, never the
original").

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Correct the luck gate's N so re-running a method stops perturbing every other method's verdict, and publish verdicts that reflect the bars in force now | 1 |
| R2 | Make the lab's own search measure the owner's real funding (+5,000,000 IDR monthly on a 10,000,000 IDR start), not a book that never grows | 2 |
| R3 | A `/redo-sera-experiments <methods>` skill that cleanly redoes one or SEVERAL named existing methods under the realistic configuration, e.g. `/redo-sera-experiments M0022,M0020,M0019` | 3 |

## Scope

**In scope:** `store.DSR_POLICY` and `npolicy.DEFAULT_POLICY`; the six test modules pinning
`"all-trials"`, N=110 and the recorded verdict digest; a `lab reevaluate` sweep and the `lab stage`
republish of `web/data/lab.json`; the two `run_registry` calls in `lab/runner.py` and the
`trial_funding` write beside them; a new `.claude/skills/redo-sera-experiments/`.

**Out of scope:**
- **Any edit to a recorded row.** `trials` and `methods` are append-only; the 128 recorded trials
  must be byte-identical at the end of every phase.
- **Spending a test-window look.** No phase runs `lab test`. Looks used must stay at 2.
- **`lab remeasure`.** `dsr_at` route 2 inverts the recorded DSR exactly, so the policy flip needs
  no moments backfill. Not needed, not in scope.
- **Changing `DSR_MIN` (0.90) or any `tuning.*` bar.** Only N moves.
- **The paper roster's composition.** Phase 1 changes what the lab *says* about the roster's
  methods, never what the roster trades.
- **Promoting anything.** No phase runs `lab promote`.

## Invariants

Every phase must hold all of these. Several are machine-specific facts about this repo that have
cost previous sessions a night:

1. **The tree builds and both suites pass at the end of each phase.**
2. **Recorded rows are never rewritten.** `SELECT count(*) FROM trials` stays 128 and every
   recorded `dsr`, `eligible`, `failed` and `n_trials_at_run` is untouched. The append-only
   triggers are the enforcement; do not work around them.
3. **Only `lab stage` commits `lab/lab.sqlite`**, and **every such commit also includes
   `web/data/lab.json`** — CI fails a database commit without it.
4. **Every lab command migrates `lab.sqlite` on connect, so even a read dirties the file.** Hash
   it before read-only work and restore it by path afterwards; commit only what the phase meant to
   change.
5. **Commit by pathspec. Never `git add -A`, never `git reset --hard`** — this worktree may be
   shared with concurrent phase sessions and the index is shared.
6. **Tests in a worktree need `PYTHONPATH`** pointing at the worktree's `engine/src`, or pytest
   silently tests the main checkout instead of the branch. Use the main checkout's venv.
7. **The research store is not in the worktree.** Point `--store` at `/home/miftah/seer/engine/.research/`;
   rebuilding it is ~30 minutes for nothing.
8. **`web/node_modules` must be hardlinked, not symlinked**, if any phase runs `next build` — a
   symlink passes vitest and tsc and then fails the build with a misleading "filesystem root" error.
9. **No phase spends a test-window look.**
10. **A deposit is not a return.** Any metric that feeds a gate condition — the Sharpe behind the
    DSR, and max drawdown — must be computed net of external cashflows. `total_return` and `cagr`
    are the documented exceptions: `metrics.strategy_metrics` contaminates them deliberately because
    the 128 recorded trials depend on their shape.
11. **Unfunded runs stay byte-identical.** Every cashflow correction must reduce to today's
    expression when the cashflow list is empty.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Count the looks the data supports, and publish today's verdict | R1 | `engine.lab`, `engine.commands`, `web/data` | ~15 | — | HARD | `.workflows/plan/lab-realistic-gate/phase-1.md` | — | — |
| 2 | The lab's search is funded like the owner's account | R2 | `engine.lab`, `engine.backtest` | ~9 | 1 | HARD | `.workflows/plan/lab-realistic-gate/phase-2.md` | — | — |
| 3 | `/redo-sera-experiments` — honest twins of named methods, in a batch | R3 | `.claude/skills` | ~1 | 1, 2 | NORMAL | `.workflows/plan/lab-realistic-gate/phase-3.md` | — | — |

### Phase 1 — Count the looks the data supports, and publish today's verdict
**Satisfies:** R1
**Owns:** `store.DSR_POLICY` -> `"methods"`; `npolicy.DEFAULT_POLICY` moved with it; every test and
prose line pinning `"all-trials"`, N=110 or the recorded verdict digest
(`test_lab_gate_policy.py:622,709`, `test_lab_snapshot.py:373`, `test_lab_prereg.py:439`,
`test_lab_gate_wording.py:188`, `test_lab_luck.py:158`, `test_lab_npolicy.py:99`); the
`lab reevaluate` sweep; the `lab stage` republish of `lab/lab.sqlite` + `web/data/lab.json`.
**Also owns a live bug on main:** `lab --help` raises `ValueError: unsupported format character ','`
because of a bare percent in an argparse help string at `commands/lab.py:236` (`the flat 0.1%,`).
One-character fix (`0.1%%`), plus a sweep of every other argparse help/epilog string in
`engine/src/seer_engine/commands/` for unescaped `%`, plus a regression test that exercises help
formatting for the top-level parser and every subparser. `commands/lab.py` is unowned elsewhere in
this set, so there is no collision with phase 2.
**Does not touch:** `lab/runner.py` (phase 2's), `DSR_MIN`, any `tuning.*` bar, any recorded row,
the paper roster's composition.
**Exit criteria:** `store.gate(conn).policy == "methods"` and `.n == 28` on the committed database;
**SIX methods move `rejected -> dev-eligible` — M0002, M0007, M0011, M0019, M0024, M0030 — taking
dev-eligible from 2 to 8** (measured; the brief predicted two and was wrong). `M0008` stays
rejected and `M0022` was already dev-eligible, both as predicted. The FULL engine suite is green on
phase 1's files alone — phase 1 owns every one of the 8 test modules its change breaks (41
failures), because each phase repairs what it itself breaks. `remeasure.batches_of`'s guard is
widened at the source. `lab --help` no longer raises. `web/data/lab.json`
agrees with `store.gate` and no longer publishes a method as `rejected` whose dev trials clear;
trials count still 128; test looks still 2; both suites green.

### Phase 2 — The lab's search is funded like the owner's account
**Satisfies:** R2
**Owns:** `lab/runner.py:310` (`lab run`) and `:612` (`lab test`) pass
`contributions=OWNER_MONTHLY`; the `FundingRow` construction and `store.insert_funding` call inside
`run_method`'s existing `BEGIN IMMEDIATE`, stamped with the trial number `insert_trials` assigned;
the now-false docstring claim at `backtest/dev.py:594`.
**Does not touch:** `sim/contributions.py`, `backtest/dev.py`'s behaviour (only its docstring),
`store.py`'s funding API (it is already built and tested), any recorded row, phase 1's constant.
**Exit criteria:** a newly run method records one `trial_funding` row per trial with a non-null
`deposits_usd`/`deposits_n` and an `mwr`; `funding_of` still returns None for all 128 pre-existing
trials; the gate's money-weighted branch at `store.py:1428` is reachable and exercised by a test;
`SELECT count(*) FROM trials` unchanged by the phase itself; both suites green.

### Phase 3 — `/redo-sera-experiments` — honest twins of named methods, in a batch
**Satisfies:** R3
**Owns:** `.claude/skills/redo-sera-experiments/SKILL.md`.
The skill takes a COMMA-SEPARATED LIST of methods — `/redo-sera-experiments M0022,M0020,M0019` —
each item a bare `MNNNN`, a `seertrade.site/sera/methods/MNNNN` URL, or a mix; a single method is
the one-element case, not a separate path. For each it resolves the parent, reserves a variation
twin (`lab idea --parent <original>`, `source_kind='variation'`), writes the twin's method file at
fractional + `cost_model="gotrade"` (which `real_cost_problem` enforces for M0031+ anyway) on the
funding phase 2 provides, commits the file as its pre-registration, runs `lab run`, and reports
every twin beside its parent in one batch table.
**Per-item isolation is the key property:** one method's failure or refusal never aborts the batch
— it is journaled and the run continues, mirroring sera-the-explorer's "a child's failure never
pauses the other slots". Refusals are per-item: a parent already fractional+Gotrade has no honest
twin (funding is not in `config_digest`, so the twin would collide — M0029 is the live case), and a
pre-M0031 parent whose edge `lab costs` shows the real fees erase is skipped rather than twinned.
Runs SERIAL in the main checkout, deliberately not sera-the-explorer's 4-way worktree fan-out: the
research store is not in worktrees, `lab stage` takes the write lock, and `registry_problem` runs
git status in the method file's own directory.
The skill takes a `seertrade.site/sera/methods/MNNNN` URL or a bare id, resolves it to the lab
method, reserves a variation twin (`lab idea` with `source_kind='variation'`, `parent_id=<original>`),
writes the twin's method file at fractional + `cost_model="gotrade"` (which `real_cost_problem`
enforces anyway for M0031+) and the funding phase 2 provides, commits the file as its
pre-registration, runs `lab run`, and reports the twin beside its parent.
**Does not touch:** any engine source; `sera-the-explorer/SKILL.md` and
`explore-and-experiment-new-method/SKILL.md` (read them for shape, do not edit them); the lab
database beyond what `lab idea` / `lab run` / `lab stage` legitimately write.
**Exit criteria:** the skill file exists and documents the refusal to purge in plain, non-technical
language, with the twin presented as the thing the owner actually gets; it names the variation route
and the "promote the twin, never the original" rule; it parses a comma-separated batch, dedupes
repeats, and skips a bad or un-twinnable item without discarding the rest; it states how an
interrupted batch resumes without duplicating; every CLI command and flag it names is verified
against the live CLI (`lab idea`'s flag is `--parent`, NOT `--parent-id`); the batch report is
written in everyday words with no column names or backticks in the prose.

## Reconciliation Log

Reconciled by the analyzing session, which held all three plans and the analysis at once.
Each planner measured its own change in a throwaway copy; no conflict below is theoretical.

| Conflict | Phases | Resolution |
|---|---|---|
| `test_lab_runner.py` / `test_lab_remeasure.py` assert `N == 56`, break under phase 1, and are edited by phase 2 | 1, 2 | First assigned to phase 2 to preserve concurrency; **withdrawn** once conflict 2 removed the concurrency. Phase 1 takes them, literal-free (`store.pending_gate`, the recorded `n_trials_at_run`). Phase 2 edits them only for funding behaviour, quoting them as phase 1 leaves them |
| `remeasure.batches_of` breaks at the SOURCE under `methods`, not only in tests | 1, 2 | Phase 1 widens the guard (a production fix phase 2 cannot route around). **Phase 2 now depends on phase 1**; the set is strictly sequential 1 -> 2 -> 3 |
| Phase 1 as first scoped left 23 tests red across five modules it did not own | 1 | Phase 1 takes all 8 modules its change breaks (41 failures). Governing rule for the set: each phase repairs what it itself breaks. Phase 1's exit criterion is now the FULL suite green on its files alone — measured: 3079 passed, 0 failed |
| Funding inflates two GATE conditions — the Sharpe behind the DSR (`book_runner.py:536`) and max drawdown (`metrics.py:261`) — and `book_runner.py` was in no phase's file list | 2, 3 | Phase 3 found it; **phase 2 takes the fix**. Measured 10.1x Sharpe inflation and an understated drawdown. Unfixed, phase 1 corrects the gate for being too strict while phase 2 makes it far too lenient — worse than shipping neither. Unfunded paths take the original code verbatim |
| A twin's headline number is not comparable to its unfunded parent's (`total_return` 10.78 vs `mwr` 0.076 on one run) | 2, 3 | Phase 3's batch report never puts them in one column; each twin is headlined against a SPY fed the same deposits. Enforced in the skill by a Never-table row and a manual check |
| `commands/lab.py` — the live `lab --help` crash — was in no phase's file list | 1 | Assigned to phase 1, which most needs a working CLI for its `reevaluate` / `stage` steps. One-char fix plus an AST sweep (exactly one bad string) plus a regression test over every subparser |

**Superseded by measurement:** the index originally predicted two methods would move to
`dev-eligible`. Phase 1 measured **six** (M0002, M0007, M0011, M0019, M0024, M0030); `dev-eligible`
goes 2 -> 8 and `rejected` 27 -> 21. The exit criteria carry the measured list.

**Corrected during reconciliation:** the `paper[]` block of `web/data/lab.json` does **not** change
and must not — `labStatus` there is frozen promotion provenance (`store.py:666`, `:2176`), the
lab's verdict at the moment each entry was promoted, not a live read. All four roster entries stay
`rejected` / `owner-override`. Also: no method is fractional + `cost_model="gotrade"` today, so
phase 3's digest-collision refusal is unreachable until the skill has run at least once.

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| The owner asked to **purge** M0007's data and redo it; the schema forbids deletion and the statistics forbid lowering N | **Mint a variation twin instead.** The deliverable the owner named — a result that represents how he really trades — is produced either way, and only this way survives the append-only triggers and leaves N honest | 5: the user's raw input, read for the deliverable ("results that represent how i trade") rather than for the mechanism ("purge") |
| Which N policy: `methods` (28) or `effective` (2) | **`methods`.** `effective` is the honest count of independent return *streams*, but the lab genuinely did look 126 times and searching buys luck. `methods` counts distinct ideas and is floored at the measured participation ratio, so it can never claim fewer independent looks than the data shows | 6: surrounding convention — `npolicy.py`'s own docstring makes exactly this argument for `methods` |
| Phase 1 flips the constant; must the republish be its own phase? | **One phase.** `test_lab_snapshot.py:373` asserts `gate["dsrPolicy"] == store.DSR_POLICY`, so flipping the constant without regenerating `lab.json` leaves the tree red — the two cannot be separated without violating invariant 1 | 1: stated invariant (the tree builds and tests pass at the end of each phase) |
| Does the policy flip need a `lab remeasure` backfill first (only 16 of 126 trials have moments)? | **No.** `dsr_at` route 2 inverts the recorded `dsr` at its `n_trials_at_run` and re-evaluates at the new N — exact arithmetic on recorded data, no backtest re-run. Keeping `remeasure` out of scope keeps phase 1 reviewable | 3: the plan's code blocks — `store.dsr_at`'s docstring, routes 1 and 2 |
| May phase 2 backfill funding onto the 128 recorded trials? | **No.** `GOTRADE_FEE_REBUILD_PLAN.md` D18 froze the lab to keep recorded trials reproducible, and `funding_of` returning None already means something definite ("this run was not fed"). Funding applies to new runs only | 1: stated invariant 2 (recorded rows are never rewritten) |

| `test_lab_runner.py` and `test_lab_remeasure.py` assert `N == 56`, break under phase 1's policy, and are edited by phase 2 — which phase owns them? | **Phase 2 owns both outright**, and re-expresses their N assertions in terms of `store.gate(conn).n` / `store.dev_trial_count` rather than any literal. The dependency between the phases then disappears and they stay concurrent. A test OF THE POLICY keeps a literal and is phase 1's; a test of something else that merely trips over N is re-expressed and is phase 2's | 1: stated invariant (no phase leaves the tree broken) + the index's own Depends-on column, which must stay edge-free for these two to run concurrently |
| A twin's headline number vs its parent's: both go in one column? | **No.** Phase 2 measured the same run reporting `total_return` +1078% and `mwr` 7.6% — a funded book's total return is mostly the owner's own deposits. Parent and twin are judged by different measures, so the batch report labels them separately and headlines each twin against a SPY fed the same deposits | 1: stated invariant 2 of the lab's own iron rules (never fool ourselves), applied to the report |
| `run_test`'s funding insert sits inside the existing `BEGIN IMMEDIATE` | **Keep it there.** A raise then rolls the look back rather than spending it, and a spent test-window look is unrecoverable. Marked in phase 2 as a property the implementer must not "clean up" | 1: stated invariant 9 (no phase spends a test-window look) |

| Funding the runner inflates two GATE CONDITIONS: the Sharpe feeding the DSR (`book_runner.py:536`, `cur/prev-1` with no cashflow term) and max drawdown (`metrics.py:261-265`, raw equity) | **Phase 2 fixes both.** Measured on the owner's plan: a book with a true Sharpe of 0.476 reads 1.395 — 2.67x inflated — and the first deposit day reads +51.6% instead of +0.3%. Unfixed, phase 1 corrects the gate for being too strict while phase 2 makes it far too lenient, which is worse than shipping neither. Unfunded runs must stay byte-identical | 1: stated invariant — the lab's own "never fool ourselves", and invariant 2 (recorded rows unchanged) |
| Is the twin's digest-collision refusal reachable today? | **No — correction to an earlier reading.** Measured across all 72 candidates: NO method is fractional + `cost_model="gotrade"` today. M0029 and M0030 are fractional at the FLAT cost, so their twins are legitimate. The refusal becomes reachable only once this skill has run, i.e. pasting a twin's own id into a later batch | 3: the plan's code blocks — phase 3's measured sweep over the candidate set |

| Phase 1 as first scoped left 23 tests red in five modules it did not own — invariant 1 violated phase-locally | **Phase 1 takes every module its change breaks (all 8).** Governing principle for the set: each phase repairs what it itself breaks. A phase that leaves tests red is not a phase, and the orchestrator must be able to land each one independently | 1: stated invariant 1 |
| `remeasure.batches_of` breaks at the SOURCE under `methods`, not merely in tests | **Phase 1 widens the guard**, and **phase 2 therefore depends on phase 1.** This removed the concurrency between 1 and 2, which in turn removed the only reason phase 2 held the two contested test modules — so that earlier assignment was withdrawn and the set is strictly sequential 1 -> 2 -> 3 | 3: the plan's code blocks — phase 1's measured production `LabError` |

## Open Questions

<none — every fork above was decided at Step 8 against the ladder>

## Rollback

- **Phase 1:** revert the two constants and re-run `lab stage`. The `rejected -> dev-eligible`
  transitions it took are recorded in `transitions` and in each method's append-only `analysis`;
  the status move itself is forward-only by trigger, so a true rollback of the *data* means
  restoring `lab/lab.sqlite` from the pre-phase commit. Capture that sha in the phase plan before
  the sweep.
- **Phase 2:** revert `lab/runner.py`. No recorded row changes, so nothing to restore.
- **Phase 3:** delete the skill directory. Nothing else is touched.
- **Whole set:** `git branch -D feature/lab-realistic-gate` and remove the worktree; `main` is
  untouched until the set lands.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f LAB_REALISTIC_GATE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f LAB_REALISTIC_GATE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan LAB_REALISTIC_GATE_PLAN.md
