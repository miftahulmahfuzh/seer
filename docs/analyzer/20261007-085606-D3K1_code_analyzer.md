# Code Analysis: the lab's luck gate and the promotion path

**Type:** Feature Update (the eligibility rule, its N, and the lab→paper linkage)
**Date:** 2026-10-07 08:56:06
**Session ID:** 20261007-085606-D3K1
**Plan:** `LAB_LUCK_GATE_PLAN.md` (7 phases)
**Worktree:** `/home/miftah/.worktrees/seer/lab-luck-gate`, branch `feature/lab-luck-gate` (base `origin/main` @ `a95126a`)

---

## User Input

### Original User Request

```
/analyze these problems
```

`these problems` refers to the findings the preceding turn put to the user, which this
command was invoked to act on. Reproduced here because nothing downstream reads the
conversation:

> The lab is in a deadlock that more exploration actively makes worse.
> dev trials spent: 110 · test-window looks: 0 · methods dev-eligible: 0 · methods promoted: 0.
> `lab promote` requires `dev-eligible` and `lab test` requires `promoted`, so the entire
> promotion path built yesterday is unreachable code.
> DSR is not converging: the ceiling moved from 0.914 (N=85) to 0.916 (N=110) while the
> threshold is 0.95. Every Sera batch raises the bar for every candidate already on the books.
> `n_trials_at_run` = 110 = the number of trial *rows*; there are 37 methods and 110 variant
> rows, so DSR's multiple-testing N counts every variant of every idea as an independent trial.
> Meanwhile the promotions are routing around the gate — `fcad718` and `a95126a` both promote
> to paper with "lab status stays rejected". The formal path is decorative while the real
> decision is made by hand on MAR.

### User-Provided Context

No `@` files, no logs. The evidence is the committed lab database and the engine source, both
read directly during Step 2.

### User-Provided Files

None.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | The DSR gate's N over-counts the search: 110 correlated variant rows are deflated as 110 independent trials, so the bar rises with every exploration regardless of merit, and 110 trials have produced 0 eligible methods. |
| R2 | A trial's verdict is frozen at the N of its run date, so verdicts are not comparable across time and the leaderboard mixes bars — and the append-only table means a method can never be re-judged. |
| R3 | The promotion path is unreachable (0 dev-eligible, 0 promoted) and the test window has never been spent, so the machinery built in `build-promotion-path` has never run and nothing surfaces that. |
| R4 | The lab verdict and the paper roster have diverged silently: RM and RMW trade on paper with lab status `rejected`, contradicting design §3 and §6. |

---

## Detailed Requirements Understanding

**Problem statement.** `lab/store.py:79` sets `DSR_MIN = 0.95` and design §3 defines dev-eligible
as the five P7a D8 conditions **and** `DSR >= 0.95 with N = all lab trials`. `runner.py:160-180`
implements that faithfully: `n_trials = store.dev_trial_count(conn) + len(results)`, and the
deflated Sharpe is computed against the variance of the daily Sharpe across every dev trial ever
recorded. The implementation matches its specification exactly. **The defect is in the rule, not
in the code that applies it**, and it has three distinct consequences the user named separately.

**Success criteria.**

- A candidate that passes the five owner conditions is judged against a luck bar whose N reflects
  the number of *independent* looks actually taken, measured rather than assumed (R1).
- Every trial is judged under one bar at evaluation time, so two identical strategies run six
  weeks apart get the same verdict; history is never rewritten to achieve this (R2).
- `lab status` shows what is promotable under the current rule and how many of the test window's
  looks remain, so an unreachable path is visible as soon as it becomes unreachable (R3).
- A paper roster entry's lab provenance is recorded and checked, so "admitted without a test
  pass" is a stated fact with a reason rather than a silent divergence (R4).

**Key considerations and constraints.**

- `trials` is append-only, enforced by the `trials_no_update` and `trials_no_delete` triggers.
  No fix may rewrite a recorded verdict. Re-evaluation must be a *derived read* or a *side table*.
- `methods.status` moves forward only along `TRANSITIONS` (`store.py:62-73`), enforced by
  `methods_status_forward`. `rejected` is terminal: there is no edge out of it. A method already
  marked `rejected` under the old bar cannot be moved to `dev-eligible` by any amount of
  re-evaluation — this is the single hardest constraint in the whole change.
- The test window must not be touched. Nothing in this plan may run a `window='test'` backtest or
  spend a look; `store.test_looks` must still read 0 when the set lands.
- `DEV_END = date(2015, 10, 16)` and the D9 guard are frozen by design §4's guardrails.
- The P7a seed's 54 trials carry `dsr IS NULL` (`seed.py:136`, "P7a reported it for one row
  only"), so only the 56 lab-method trials have a recomputable DSR.

**Assumption, stated because it decides the plan.** The owner's intent in asking for this analysis
is to resolve the deadlock, not merely to instrument it. A plan that only measured the problem
would leave the lab exactly where it is. The gate therefore changes — see `## Decisions` in the
plan index for the choice and the rung that decided it.

---

## Analysis Scope

### Explicitly Mentioned Files

None. Entry point was `lab/lab.sqlite` and `docs/plans/2026-10-04-method-lab-design.md`.

### Discovered Related Files

- `engine/src/seer_engine/lab/store.py` — schema, statuses, transitions, `DSR_MIN`, the N and
  variance queries, `best_dev_eligible`, the web snapshot's `gate` block
- `engine/src/seer_engine/lab/runner.py` — `_dsr`, `trial_rows`, `run_method`, `run_test`
- `engine/src/seer_engine/backtest/dev.py:548` — `deflated_sharpe`, the Bailey & López de Prado formula
- `engine/src/seer_engine/commands/lab.py` — `status`, `promote`, the near-miss and closest-to-eligible tables
- `engine/src/seer_engine/lab/prereg.py` — the committed pre-registration format, which bakes the N wording into the file
- `engine/src/seer_engine/paper/roster.py` — `RMW_ID`/`RM_ID`, the admission doctrine at lines 62-65
- `engine/src/seer_engine/commands/backtest_dev.py` — `daily_moments`, the (sharpe, skew, kurt) source
- `web/app/sera/overview.ts`, `web/app/sera/methods/[id]/page.tsx`, `web/lib/sera/lab.ts` — the site's gate display

---

## Current Dataflow

### Entry Point: `lab run <method>`

**Location:** `commands/lab.py` → `runner.run_method` (`runner.py:224`)
**Trigger:** the explore skill's step 5, or a human at the CLI
**Validation:** `preflight` refuses an uncommitted method file, a method that already ran, and any
variant whose config digest already has a dev trial.

### Processing Chain — how a verdict is produced

1. **`dev.run_registry`** runs each variant on the dev-window research store and returns a
   `DevRow` per variant, carrying `row.failed` — the five owner conditions already evaluated.
2. **`runner.trial_rows`** (`runner.py:160`) computes the luck test:
   - `prior = store.dev_daily_sharpes(conn)` — every dev trial's annualized Sharpe ÷ √252
   - `n_trials = store.dev_trial_count(conn) + len(results)` — **every dev trial row, this batch included**
   - `var_trials = statistics.variance(prior + new_sharpes)`
   - `dsr = dev.deflated_sharpe(sr, n_trials, var_trials, t, skew, kurt)` per variant
   - `if dsr is None or dsr < store.DSR_MIN: failed.append(store.DSR_LABEL)`
   - `eligible = not failed` — **frozen into the row at this moment**
3. **`store.insert_trials`** appends the rows. `has_trial` refuses a duplicate `(digest, window)`.
4. The method's status moves to `dev-eligible` when any trial is eligible, else `rejected`.

**This is where R1 and R2 both originate, in one function.** `n_trials` and `var_trials` are read
from the database at run time and then discarded; only their *output* (`dsr`, `eligible`,
`n_trials_at_run`) is stored. The inputs needed to re-evaluate the verdict — `t`, `skew`, `kurt`,
and the `var_trials` of that moment — are never persisted.

### Data Persistence

**Database:** `lab/lab.sqlite`, table `trials`, append-only by trigger. 110 dev rows, 0 test rows.
**Status machine:** `methods.status`, forward-only along `TRANSITIONS`. `rejected` has no outgoing edge.
**Web:** `store.snapshot()` → `web/data/lab.json`, whose `gate.dsrMin` the sera site draws as the
"Luck bar" reference line (`web/app/sera/overview.ts:328`).

### Exit Points

`lab promote <method>` (`commands/lab.py:307`) calls `store.best_dev_eligible`, which selects
`WHERE eligible = 1` — so it is gated entirely on the frozen flag — writes `docs/lab/prereg/MNNNN.md`
and moves the method `dev-eligible → promoted`. `lab test` then requires `promoted`.

---

## Measured Evidence

Everything below was computed from the committed database during this analysis. No backtest was
re-run and no test-window look was spent.

### The gate has never been met, and the margin is not closing

| candidate | ann. Sharpe | CAGR | maxDD | MAR | DSR | N at run | other failed conditions |
|---|---|---|---|---|---|---|---|
| M0022-W-TV16 | 0.945 | 11.7% | 14.3% | 0.82 | 0.916 | 110 | **none** |
| M0022-W-TV14 | 0.940 | 10.6% | 12.4% | 0.86 | 0.912 | 110 | **none** |
| M0020-W-NOSTOP | 0.938 | 15.3% | 19.3% | 0.79 | 0.914 | 107 | max DD ≤ 15% |
| M0007-N20-RAW | 0.942 | 15.0% | 19.6% | 0.77 | 0.914 | 85 | max DD ≤ 15% |
| M0011-RAW20-TV14-N21 | 0.926 | 10.8% | 14.1% | 0.76 | 0.897 | 90 | **none** |

Three candidates — M0022's two variants and M0011's — **fail only the luck test**. Every other
owner condition passes.

### The bar rises with N, by construction

`SR*`, the daily hurdle, at the measured trial-Sharpe variance (`var = 2.395e-04`, sd 0.01548):

| N | 10 | 20 | 37 | 54 | 85 | 110 | 135 | 200 | 400 |
|---|---|---|---|---|---|---|---|---|---|
| SR* (daily) | 0.0244 | 0.0294 | 0.0334 | 0.0357 | 0.0383 | 0.0397 | 0.0408 | 0.0428 | 0.0462 |
| SR* (annualized) | 0.387 | 0.467 | 0.530 | 0.566 | 0.608 | 0.630 | 0.647 | 0.679 | 0.733 |

A day of Sera adds ~25 trials. From N=85 to N=110 the hurdle rose 0.022 annualized Sharpe while
the best candidate's DSR rose 0.002. **The search is losing ground to its own counter.**

### The trials are not independent, and this is measurable

Computed from the month-end equity curves already stored in `trials.curve_json` (all 110 rows
have one), over the 102 month-ends common to every trial:

```
mean pairwise correlation (ρ̄)        = 0.595   (median 0.640)
effective N, participation ratio       = 2.4
effective N, 1 + (N−1)ρ̄ adjustment     = 1.7
distinct methods with dev trials       = 23     (11 P7a families + 12 lab methods)
trial rows                             = 110
```

`deflated_sharpe` assumes N **independent** trial Sharpes drawn from a distribution of variance
`var_trials`. Feeding it 110 trials whose mean pairwise correlation is 0.595 asserts an
independence the data does not have. The expected maximum over 110 correlated draws is materially
below the expected maximum over 110 independent ones, so the hurdle is overstated.

The participation ratio of 2.4 is the other extreme and is not a usable N either: it measures how
many independent *return streams* exist, and every strategy in the lab holds US large-cap
equities, so it collapses onto the market factor. It says nothing about how many times the search
looked.

### What each N would do to the recorded verdicts

Recovered by inverting each recorded DSR for its per-trial constant `√(t−1)/√radicand` and
re-evaluating `Φ((SR − SR*(N))·k)`. Exact given the recorded values; no re-run.

| candidate | DSR as recorded | at N=37 | at N=23 | other failed conditions |
|---|---|---|---|---|
| M0022-W-TV16 | 0.916 (N=110) | 0.965 | 0.978 | none |
| M0022-W-TV14 | 0.912 (N=110) | 0.963 | 0.977 | none |
| M0020-W-NOSTOP | 0.914 (N=107) | 0.964 | 0.978 | max DD |
| M0007-N20-RAW | 0.914 (N=85) | 0.953 | 0.970 | max DD |
| M0019-RAW20-S25 | 0.900 (N=104) | 0.956 | 0.972 | max DD |
| M0001-TV10 | 0.903 (N=58) | 0.937 | 0.964 | beats SPY TR |

At N = 23 (distinct methods), M0022's two variants clear 0.95 on the strength of the five
conditions they already pass. **Nothing else changes**: every other candidate still fails on max
drawdown or on beating SPY, which no change to N can rescue.

### The verdicts are not comparable across time

`M0007-N20-RAW` scored DSR 0.914 at N=85. The identical trial recorded today, at N=110, scores
≈0.89. A method's verdict depends on how many unrelated ideas happened to be tried before it.
The `eligible` column therefore mixes bars, and `best_dev_eligible` — which reads
`WHERE eligible = 1` — selects against a column whose meaning drifts.

### The promotion path is unreachable and nothing says so

```
methods by status:  idea 11 · rejected 26 · dev-eligible 0 · promoted 0 · test-passed 0 · paper 0
test-window looks spent: 0
```

`lab promote` refuses anything not `dev-eligible`; `lab test` refuses anything not `promoted`.
With both counts at zero, neither command can be invoked. `lab status` prints the `Dev-eligible`
and `Promoted` sections only when they are non-empty (`commands/lab.py:215-222`), so a lab in this
state prints *nothing at all* about the promotion path — the one condition that most needs saying
is the one condition that is silent.

### The lab and the paper roster disagree, in writing

`paper/roster.py:62-65`:

> ``FND`` is on the roster having failed its gate too (six M0005 dev-window trials, all six
> failed, all six recorded in ``lab/lab.sqlite``): passing a gate has never been this roster's
> admission criterion, and the gates bind the real-money decision, not paper membership.

Against design §3: "Pass → `test-passed`, and the skill stops for the owner: a paper roster entry
(new id, own clock) is the owner's call", and §6: "on a test pass, a paper-roster entry with its
own clock".

Both positions are defensible; what is not defensible is that they are both live. Today RM-FR
(lab M0011) and RMW-FR (lab M0022) trade on the paper roster while both methods read `rejected`
in `lab.sqlite`, and the only record of why is prose in a commit message. `TRANSITIONS` has
exactly one edge into `paper` — from `test-passed` — so the status a roster entry implies is
unreachable for every entry currently on the roster.

---

## Key Data Structures

### `store.TrialRow` — `lab/store.py:517`
Carries `dsr`, `eligible`, `failed`, `n_trials_at_run`, `curve_json`. **Does not carry** `t`,
`skew`, `kurt` or the `var_trials` used — the four inputs a re-evaluation needs.

### `TRANSITIONS` — `lab/store.py:62`
`rejected` is terminal. This is why re-evaluation alone cannot unblock M0022: the method is
already `rejected`, and no edge leads out. The plan adds one, scoped and justified, in phase 4.

### `dev.deflated_sharpe` — `backtest/dev.py:548`
Pure, total, well-tested. **Unchanged by this plan.** Only its `n_trials` argument changes.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `DSR_MIN` | `lab/store.py:79` | def | engine |
| `DSR_LABEL` | `lab/store.py:80` | def | engine |
| `dev_trial_count` | `lab/store.py:554` | def | engine |
| `dev_daily_sharpes` | `lab/store.py:562` | def | engine |
| `best_dev_eligible` | `lab/store.py:572` | def | engine |
| `TRANSITIONS` | `lab/store.py:62` | def | engine |
| `snapshot` gate block | `lab/store.py:829-838` | def | engine |
| `_dsr` | `lab/runner.py:146` | def | engine |
| `trial_rows` | `lab/runner.py:160` | call | engine |
| `run_test` | `lab/runner.py:438-481` | call | engine |
| `deflated_sharpe` | `backtest/dev.py:548` | def | engine |
| `daily_moments` | `commands/backtest_dev.py` | def | engine |
| status / promote | `commands/lab.py:180-230, 307` | call | engine |
| DSR wording in prereg | `lab/prereg.py:152, 166, 204, 416` | def | engine |
| roster admission doctrine | `paper/roster.py:62-65` | doc | engine |
| `RM_ID` / `RMW_ID` | `paper/roster.py:118, 237-241` | def | engine |
| `gate.dsrMin` | `web/app/sera/overview.ts:321-330` | call | web |
| gate keys | `web/lib/sera/lab.ts` | def | web |
| design §3 | `docs/plans/2026-10-04-method-lab-design.md:56` | doc | docs |
| N wording | `docs/lab/prereg/README.md` | doc | docs |
| tests | `engine/tests/test_lab_runner.py`, `test_lab_store.py`, `test_lab_prereg.py`, `test_lab_test_window.py`, `test_lab_snapshot.py`, `test_paper_roster.py` | test | engine |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/lab/npolicy.py` (new) — the N policy and the effective-N estimator — phase 1
2. `engine/src/seer_engine/lab/store.py` — `trial_moments` table, policy-aware reads, the `rejected → dev-eligible` edge, snapshot gate — phases 2, 4
3. `engine/src/seer_engine/lab/runner.py` — record the DSR inputs; evaluate under the policy — phases 2, 4
4. `engine/src/seer_engine/commands/lab.py` — `remeasure`, `reeval`, the status queue and look budget — phases 3, 5
5. `engine/src/seer_engine/lab/prereg.py` — the N wording in the committed format — phase 7
6. `engine/src/seer_engine/paper/roster.py` + `commands/promote.py` — lab provenance — phase 6
7. `docs/plans/2026-10-04-method-lab-design.md` §3, `.claude/skills/explore-and-experiment-new-method/SKILL.md`, `engine/package_readme.md`, `docs/lab/prereg/README.md` — phase 7
8. `web/data/lab.json` shape, `web/app/sera/overview.ts`, `web/lib/sera/lab.ts` — phase 7
9. `engine/tests/test_lab_*.py`, `test_paper_roster.py` — every phase

**This document describes. The plan files prescribe.**
