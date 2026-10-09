# Code Analysis: Lab realistic gate — N policy, funded runner, redo skill

**Type:** Feature Update (three related items: a shipped-constant correction, a wiring gap, and a new skill)
**Date:** 2026-10-08 13:50:44
**Session ID:** 20261008-135044-N7K3
**Plan:** `LAB_REALISTIC_GATE_PLAN.md` (3 phases)
**Worktree:** `/home/miftah/.worktrees/seer/lab-realistic-gate` — branch `feature/lab-realistic-gate` (base `origin/main` @ `2b493ee`)

---

## User Input

### Original User Request

The owner's question that started this was whether a `sera-the-explorer` run today would explore
methods that consider (1) Gotrade's fees and (2) his continuous +5,000,000 IDR monthly top-up.
Validation found (1) enforced and (2) absent. He then proposed a `/redo-sera-experiment <method-url>`
skill that would **purge** an existing method's experiment data and redo it realistically, in his words:

> "i just hate it that these old experiments have their own results that do not exactly represent how
> i trade in real life using gotrade. so i am thinking , why not create a skill so i specifically
> target some existing good methods (for example, methods that are included in the seer's roster)
> and cleanly redo it using the realistic approach?"

On being shown that the purge is forbidden and that the luck gate's N is miscounted, he said:

> "i fucking hate this DSR bullshit man. redoing the method now will change how their "luck" look
> like. but i dont know anything about statistics or trading, so i will just follow your ideas"

and then, to the proposal below: **"yes. and /analyze them all"**.

The rationale is the specification: the owner's objection — that re-running a method perturbs every
other method's luck verdict — is a true and correct observation about the `all-trials` N policy, and
item 1 exists to remove its cause rather than to work around it.

### User-Provided Context

- `lab luck` (read-only) measures mean pairwise correlation **0.612** and participation ratio
  **2.338** across the 126 recorded dev curves.
- `store.py:125` records that at `all-trials` the best candidate sinks below the bar at N ~ 200,
  about four more Sera nights — the lab rejects everything on a timer.
- Round-trip Gotrade fee measured against book size (20 names, 16,500 IDR/USD): 0.957% at 10M IDR
  (the lab's permanent book), 0.647% at month 3, 0.553% at month 24, 0.515% at month 60.
- All four paper-roster entries publish as `"labStatus":"rejected","basis":"owner-override"`.

### User-Provided Files

None marked with `@`; every file below was discovered by exploration.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Correct the luck gate's N so re-running a method stops perturbing every other method's verdict, and publish verdicts that reflect the bars in force now |
| R2 | Make the lab's own search measure the owner's real funding (+5,000,000 IDR monthly on a 10,000,000 IDR start), not a book that never grows |
| R3 | A `/redo-sera-experiment <method-url>` skill that cleanly redoes a named existing method under the realistic configuration |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement**

Three defects, one theme: the lab's verdicts do not describe the trading the owner actually does.

1. **The luck gate counts wrong.** `store.DSR_POLICY = "all-trials"` deflates the Sharpe by the
   number of trial *rows* (126). `deflated_sharpe` assumes those are independent draws. They are
   not — every method in the lab holds US large-cap equity, and the lab's own estimator puts the
   participation ratio at 2.338 with mean pairwise correlation 0.612. The gate therefore asserts an
   independence its own data contradicts, and the hurdle it sets is overstated.
2. **The published snapshot shows stale lifecycle statuses.** `published_verdict` already re-derives
   every condition at today's bars, but `methods.status` is a stored lifecycle state that only moves
   via `lab reevaluate`. `M0022-W-TV16` clears the live 0.90 bar yet its method publishes as
   `rejected`.
3. **The lab's search is unfunded.** `dev.run_registry` accepts `contributions=` and defaults to
   None; `lab/runner.py:310` and `:612` both omit it. So 0 of 128 trials carry a `trial_funding`
   row, `store.insert_funding` has no production caller, and the gate's money-weighted branch is
   unreachable.

**Success Criteria**

- The gate deflates by `methods` (N = 28 on the committed database), and `npolicy.DEFAULT_POLICY`
  agrees with `store.DSR_POLICY` by construction.
- `lab reevaluate` has moved every method whose recorded dev trials now clear, and
  `web/data/lab.json` republishes the result. Measured expectation: `M0002` and `M0007` move
  `rejected -> dev-eligible`; `M0022` is already `dev-eligible`; `M0008` stays `rejected`.
- `lab run` and `lab test` fund the book with `OWNER_MONTHLY` and write a `trial_funding` row per
  trial; the 128 already-recorded trials are byte-identical afterwards.
- `/redo-sera-experiment <url>` exists, resolves a method URL, mints a variation twin, runs it, and
  reports the twin beside its parent.

**Key Considerations**

- `trials` and `methods` are append-only at the schema level (`trials_no_update`,
  `trials_no_delete`, `methods_no_delete`). Nothing in this plan set may delete or rewrite a
  recorded row. The owner's original "purge" framing is therefore replaced by the variation-twin
  route that `real_costs.py` already names as the only legitimate one.
- `dsr_at` has two exact routes: from `trial_moments` (16 of 126 trials have one) and, failing
  that, by inverting the recorded `dsr` at its `n_trials_at_run` (`recover_dsr`). **Both are exact
  arithmetic**, so the policy flip does NOT require a `lab remeasure` campaign first. The 54 seed
  rows with NULL `dsr` stay unjudgeable, exactly as they are today.
- `GOTRADE_FEE_REBUILD_PLAN.md` D18 deliberately froze the lab ("nothing about the lab moves") to
  keep recorded trials reproducible. R2 honours that: funding applies to new runs only.

---

## Analysis Scope

### Discovered Related Files

| File | Why |
|---|---|
| `engine/src/seer_engine/lab/store.py` | `DSR_POLICY` (:165), `gate` (:951), `verdict` (:1264), `published_verdict` (:1333), `dsr_at` (:1188), `reevaluate` (:1582), `FundingRow`/`insert_funding` (:1690+), `snapshot` (:2070) |
| `engine/src/seer_engine/lab/npolicy.py` | `DEFAULT_POLICY`, the three policies, the participation-ratio estimator |
| `engine/src/seer_engine/lab/runner.py` | `:310` `lab run`, `:612` `lab test` — the two `run_registry` calls missing `contributions=` |
| `engine/src/seer_engine/backtest/dev.py` | `run_registry` (:582) and `_run` (:491), which already thread `contributions` |
| `engine/src/seer_engine/sim/contributions.py` | `OWNER_MONTHLY`, `ContributionSchedule`, `credit_for` |
| `engine/src/seer_engine/backtest/metrics.py` | `mwr`, `money_weighted_return`, `external_cashflows` |
| `engine/src/seer_engine/lab/real_costs.py` | `requires_real_cost`, `real_cost_problem` — the M0031 rule |
| `engine/src/seer_engine/commands/lab.py` | `reevaluate` (:1147), `stage`, `export-json` |
| `.claude/skills/explore-and-experiment-new-method/` | `SKILL.md` + `method_template.py` — the shape a new skill must mirror |
| `.claude/skills/sera-the-explorer/SKILL.md` | the promotion rules and the "promote the twin, never the original" mandate |

---

## Current Dataflow

### `lab run MNNNN` — the search

1. `commands/lab.py` -> `runner.run_method(conn, method, path, data, git_sha)`
2. `runner.preflight` — refuses an uncommitted method file, a method that already ran, a repeated
   configuration, and (M0031+) any variant not at `cost_model="gotrade"` via `real_cost_problem`.
3. `dev.run_registry(market, dividends, spy_dividends, method.candidates, on_result=...)`
   — **`contributions` is not passed, so it defaults to None.** Each candidate runs a lump-sum book
   of `INITIAL_IDR = 10,000,000`, converted once, that never receives another rupiah.
4. `runner.trial_rows` computes the DSR with N from `store.pending_gate`, which reads
   `store.DSR_POLICY`.
5. One `BEGIN IMMEDIATE`: `insert_trials`, `insert_moments`, status set to `dev-eligible` or
   `rejected`. **No `insert_funding` call exists anywhere in production code.**

### Verdict read path

`store.gate(conn)` resolves N through `npolicy.effective_n(policy=DSR_POLICY)`.
`store.verdict(conn, trial, at=gate)` re-derives the four owner thresholds from the row's own
columns against live `tuning.*`, and decides the luck test on `dsr_at(conn, trial, g.n)`.
`published_verdict` applies that to dev rows and thresholds-only to test rows.
`snapshot` -> `snapshot_json` -> `web/data/lab.json` -> seertrade.site/sera.

**The gap:** `published_verdict` is current, but the `paper` block of the snapshot carries
`methods.status`, a stored lifecycle value. `lab reevaluate` is the only thing that moves it, along
the `rejected -> dev-eligible` transition edge.

### State changes

- `lab/lab.sqlite` — the only legitimate writer for a commit is `lab stage`, which takes the write
  lock, regenerates `web/data/lab.json` and stages both.
- **Every lab command migrates the database on connect, so even a read dirties the file.**

---

## Key Data Structures

### `store.Gate`
`n`, `policy`, `derived`, `unjudgeable`, `dev_trials`, `unblocked` — the live multiple-testing count
and what it would admit.

### `store.FundingRow` (`store.py:1693`)
`trial_n`, `mwr`, `spy_tr_mwr`, `deposits_usd`, `deposits_n`, `schedule`, `measured`.
Built but never written in production. **The existence of a row is the funded flag**; `funding_of`
returning None means "this run was not fed", which is true of all 128 recorded trials.

### `sim.contributions.OWNER_MONTHLY`
`ContributionSchedule(amount_idr=Decimal("5000000"), day_of_month=25)`.

---

## Reference List

| Symbol / key | File:line | Kind | Owner phase |
|---|---|---|---|
| `DSR_POLICY = "all-trials"` | `lab/store.py:165` | def | 1 |
| `DEFAULT_POLICY: Policy = "all-trials"` | `lab/npolicy.py` | def | 1 |
| `assert store.DSR_POLICY == "all-trials"` | `tests/test_lab_gate_policy.py:622` | test | 1 |
| `assert store.DSR_POLICY == "all-trials"` | `tests/test_lab_gate_policy.py:709` | test | 1 |
| `RECORDED_VERDICT_DIGEST`, N=110 fixture | `tests/test_lab_gate_policy.py` | test | 1 |
| `gate["dsrPolicy"] == store.DSR_POLICY` | `tests/test_lab_snapshot.py:373` | test | 1 |
| policy name in prereg text | `tests/test_lab_prereg.py:439` | test | 1 |
| `DSR_POLICY` in gate wording | `tests/test_lab_gate_wording.py:188` | test | 1 |
| "which is why `DSR_POLICY` stays at `all-trials`" | `tests/test_lab_luck.py:158` | doc/prose | 1 |
| `npolicy` default-agreement test | `tests/test_lab_npolicy.py:99` | test | 1 |
| `web/data/lab.json` | repo | data | 1 |
| `run_registry(... )` missing `contributions=` | `lab/runner.py:310` | call | 2 |
| `run_registry(... window=window)` missing `contributions=` | `lab/runner.py:612` | call | 2 |
| `insert_funding` (no production caller) | `lab/store.py:1759` | def | 2 |
| `contributions: ... = None` + docstring claim | `backtest/dev.py:582,594` | def/doc | 2 |
| `.claude/skills/redo-sera-experiment/` | new | skill | 3 |

---

## Impact Points

1. `engine/src/seer_engine/lab/store.py` — one constant; phase 1.
2. `engine/src/seer_engine/lab/npolicy.py` — `DEFAULT_POLICY` must move with it; phase 1.
3. Six test modules pinning `"all-trials"`, N=110 and the verdict digest; phase 1.
4. `web/data/lab.json` — regenerated through `lab stage` after `lab reevaluate`; phase 1.
5. `engine/src/seer_engine/lab/runner.py` — two `run_registry` calls plus funding-row construction
   and `insert_funding` inside the existing transaction; phase 2.
6. `engine/src/seer_engine/backtest/dev.py` — the docstring claim "what every caller in the tree
   passes" becomes false; phase 2.
7. `.claude/skills/redo-sera-experiment/SKILL.md` — new; phase 3.

**This document describes. The plan files prescribe.**
