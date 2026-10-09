# Code Analysis: recorded-trial reproducibility and cross-store comparison (handover §5.1)

**Type:** Bug Investigation (with a policy decision attached)
**Date:** 2026-10-09T12:38Z
**Session ID:** 20261009-192826-T7RQ
**Plan:** `TRIAL_REPRODUCIBILITY_PLAN.md` (4 phases)
**Worktree:** `/home/miftah/.worktrees/seer/trial-reproducibility` on `feature/trial-reproducibility` (base `origin/main` @ `e5eda52`)

---

## User Input

### Original User Request

```
/analyze docs/plans/HANDOVER_20261009.md
```

The handover names its own primary target: "`/analyze` this file. The primary target is **§5.1**".
§5.1, verbatim, is the specification:

### 5.1 PRIMARY TARGET — recorded trials are not reproducible, and the lab compares across stores

**The evidence, all measured today:**

- `lab costs M0011` re-ran `M0011-RAW20-TV14-N21` at the flat cost and got **+545.3%** where trial
  #90 records **+660.2%**. The command prints its own warning: *"compare the two re-runs with each
  other, not with the recorded trial."*
- The lab's 152 trials were recorded under **three different store fingerprints**:

  | fingerprint | dev trials | recorded |
  |---|---|---|
  | `399d0d254c7a` (current) | 84 | Oct 6-9 |
  | `5451195fd552` | 58 | Oct 4 |
  | `e597367bb680` | 6 | Oct 5 |

- **`REF-SPY-HOLD`, the benchmark every walk-forward fold is scored against, lives in
  `5451195fd552`** — not the current store. Rebuilt from the current store the same curve ends
  **+1.83%** higher, with a worst monthly gap of 1.90%.

**Why it is not a fire today, and why it will be.** Measured: of **130** scoreable fold verdicts
across the lab, only **3** sit inside that 1.9% drift — M0030 fold 1 (−0.32 pts), M0021 fold 1
(−0.36), H-P7A-F1 fold 4 (−0.91) — and every one of the three is blocked by another condition
anyway, so **no gate outcome changes**. Today's verdicts stand. But the hard gate now makes real
promotion decisions out of cross-store arithmetic, and the margin only has to be thin once.

The root cause is known and documented in the repo already: yfinance answers differently from one
day to the next, so a rebuild is never bit-identical, which is exactly why
`.claude/skills/sync-research-store/` exists — *copying* a store keeps one fingerprint and
rebuilding does not.

**Questions to answer with measurement, not assumption** (the lab-hard-gate set did this well on
2026-10-09; copy its approach — state the options, measure what each costs, pick, and say why):

1. **What is the policy?** Candidates, not a menu to pick blind: (a) pin the dev store forever and
   make a rebuild an explicit, versioned event; (b) re-run the benchmark under the current store so
   at least the yardstick matches the majority; (c) make the gate refuse a comparison whose two
   sides carry different `store_fingerprint`, failing closed; (d) record enough per trial to
   re-derive. Measure how many trials and verdicts each would strand.
2. **Is `trials.store_fingerprint` enough to detect it?** It is already recorded on every row.
   Should `lab walkforward`, `lab regime` and `hardgate` warn — or refuse — on a mismatch?
3. **How far does the drift reach?** 1.83% was measured on SPY buy-and-hold only. Quantify it for
   a method curve, not just the benchmark, before deciding (a)-(d).
4. **Does the 58-trial `5451195fd552` cohort need re-running, or marking?** `trials` is
   append-only by trigger, so "fixing" old rows is not available; only adding or annotating is.

**Hard constraints.** `trials` is append-only — triggers refuse UPDATE and DELETE. `test-failed`
and `test-passed` are final; `TRANSITIONS` has no edge out of either. Do not invent one.


And the handover's §6, which binds every phase:

## 6. What NOT to do

- **Do not re-propose the breadth-regime diagnosis or walk-forward as a complete answer.** Both
  were tried today and both are written up with the measurement that limits them (§2).
- **Do not add an override to the hard gate.** The owner decided there is none. The override path
  is exactly what produced the 0-for-5 roster. If the rule is wrong, change the rule in git and
  argue for it in the commit.
- **Do not edit `lab/walkforward.py:buy_signal` without the owner.** It is his rule about his
  money. The lab-hard-gate implementers correctly escalated rather than widen it.
- **Do not "fix" old trials.** `trials` is append-only by trigger. Add or annotate; never rewrite.
- **Do not spend a test-window look casually.** Four are spent, all four failed. `test-failed` is
  final.

### User-Provided Context

- The handover was written on the other laptop. This analysis ran on the **GPD** (`hostname` →
  `GPD`), whose `engine/.research-test/` is an *older* test store (`56e83810e82e`, window end
  2026-10-06, 4,407,549 bar rows) than the `bbe7abfb4a12` the handover describes. The dev store
  here is `399d0d254c7a`, the current one.
- No `sera-*` / `orch-*` tmux window was open at analysis time.

### User-Provided Files
- `docs/plans/HANDOVER_20261009.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Choose the reproducibility/comparability **policy** — candidates (a) pin the store and make a rebuild an explicit versioned event, (b) re-run the benchmark under the current store, (c) gate refuses a comparison across different `store_fingerprint`, failing closed, (d) record enough per trial to re-derive — measured by how many trials and verdicts each strands, and say why |
| R2 | Decide whether `trials.store_fingerprint` is enough to detect the problem, and whether `lab walkforward`, `lab regime` and `hardgate` should warn or refuse on a mismatch |
| R3 | Quantify how far the drift reaches on a **method** curve, not just the SPY benchmark, before deciding R1 |
| R4 | Decide whether the 58-trial `5451195fd552` cohort needs re-running or marking — append-only, so only adding or annotating |

Hard constraints carried from §5.1 and §6: `trials` is append-only by trigger; `test-failed` /
`test-passed` are final; no override on the hard gate; no edit to `walkforward.buy_signal`; no
casual test-window look.

---

## Measurements taken in this session (2026-10-09, GPD)

Every number below was produced by a command run in this session against **copies** of
`lab/lab.sqlite` in the scratchpad (`lab remeasure` writes `trial_moments`; the real database was
opened read-only throughout and is unchanged).

### M1 — The three dev fingerprints carry byte-identical price data

`research.fingerprint_of` over the current store's manifest **with `fundamentals.csv` left out**
(i.e. over `bars.csv`, `dividends.csv`, `fx.csv`, `unserved.csv` only) returns
`5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a` — **exactly the P7a store's
fingerprint**. So:

| fingerprint | what differs from `5451195…` | price files |
|---|---|---|
| `5451195fd552` (P7a, Oct 4) | — (four files, no panel) | the reference |
| `e597367bb680` (Oct 5) | adds `fundamentals.csv` (2015-only panel) | identical (runbook: the 399d0d refresh "copied them byte for byte" from e597367) |
| `399d0d254c7a` (Oct 5, current) | `fundamentals.csv` rebuilt from 2009 | **identical — proven above** |

`fingerprint_of` hashes the whole `files` map, so adding or refreshing the fundamentals panel moves
the fingerprint without moving one bar. **The dev store's prices have never changed.**
`trials.store_fingerprint` therefore over-reports drift for every price-only method and is the
wrong key for a comparability rule.

### M2 — Same store, different numbers: the engine's starting capital moved

`lab remeasure M0011` and `lab remeasure M0007` (both recorded on `399d0d…`, today's store) do
**not** reproduce on today's code: Sharpe deltas 9.5e-4 .. 5.2e-2 against a 1e-9 tolerance.
Cause, found by inspection and then proven:

- `d79fc83` (2026-10-08T11:32:48+07:00, "feat(sim): a contribution schedule, and the lab's real
  capital") changed `backtest/runner.py:INITIAL_IDR` from `Decimal("20000000")` to
  `Decimal("10000000")`.
- `INITIAL_IDR` is not part of `config_digest`, not a `trials` column, and a recorded curve is
  normalised to opening cash, so nothing in the database says which capital a trial ran on. Whole-
  share lot rounding makes capital a result-moving input.
- **Proof:** in a throwaway worktree of HEAD with only `INITIAL_IDR = Decimal("20000000")`
  restored, `lab remeasure M0011` and `lab remeasure M0007` reproduce **every** variant with
  Sharpe delta **0.000e+00** and DSR delta **0.000e+00**.

The same accounts for `lab costs M0011` reading +545.3% where trial #90 records +660.2%: the flat
re-run ran at 10M, the trial at 20M.

### M3 — The capital of every recorded trial is determined exactly

Cross-checked by `git merge-base --is-ancestor d79fc83 <trial.git_sha>` over all 26 distinct
`git_sha` values in `trials`:

| | git_sha before `d79fc83` | git_sha after |
|---|---|---|
| no `trial_funding` row (lump sum) | **20** shas — trials #1..#128 | 0 |
| has a `trial_funding` row | 0 | **6** shas — trials #129..#152 |

Rule, exact on today's database: **lump-sum trial → 20,000,000 IDR; funded trial →
10,000,000 IDR.** Test trials follow it too (#123, #125 lump at 20M; #130, #131 funded at 10M).

### M4 — The P7a seed cohort reproduces on today's store (R3, R4)

`lab remeasure H-P7A` against today's store:

- at today's code (10M): **54 of 54 diverge** — e.g. `REF-SPY-HOLD` total return 5.945958
  recorded vs 5.874617 re-run; `F9-SPY200M70-MOM30` 8.786433 vs 8.031926, 17 fewer trades.
- at 20M (the throwaway worktree): **54 of 54 reproduce** all six recorded metrics within
  `METRIC_TOL = 1e-6` absolute, exact on trades; exit 0.

So the method-curve drift across the cohort boundary (R3) is **nil** once capital is honoured, and
the REF-SPY-HOLD benchmark reproduces on today's store bit-for-bit within the 6-dp rounding of the
CSV it was imported from. The handover's "+1.83% higher, worst monthly gap 1.90%" was produced by
a rebuild that cannot have used the recorded capital (at 10M the re-run ends ~1.0% *lower*, not
higher; the construction behind 1.83% is not recorded anywhere in the repo). Either way it was not
store drift.

### M5 — What the four policies would strand (R1)

| policy | trials stranded today | verdicts changed today | note |
|---|---|---|---|
| (a) pin the dev store, rebuild = versioned event | 0 | 0 | the store has never moved its prices (M1) |
| (b) re-run REF-SPY-HOLD under the current store | 0 | 0 | unnecessary: it already reproduces at its capital (M4) |
| (c) refuse a comparison across **`store_fingerprint`** | **every** promotion: the benchmark is `5451195…`, every M-method trial is `399d0d…` or `e597367…` | all promotion paths closed | wrong key (M1) |
| (c′) refuse across **price fingerprint** | 0 | 0 | all 148 dev trials share price fingerprint `5451195…` |
| (d) record enough per trial to re-derive | 0 | 0 | the missing input is **capital** (M2); with it recorded, M0007, M0011 and the 54 seed trials reproduce exactly |

### M6 — Side effect measured, deliberately not taken

Writing the recovered moments changes the lab's reading, though no status: with the 54 seed
`trial_moments` rows present, `lab status` newly lists `H-P7A-F9 F9-SPY200M70-MOM30 status
'rejected': lab reevaluate H-P7A-F9 re-judges it and moves it to dev-eligible`. With M0007 / M0011
moments present, `M0007-N20-RAW` reads DSR 0.978 (from 0.952) and `M0011-RAW20-TV14-N21` 0.973
(from 0.943). `trial_moments` is append-only by trigger. This is a verdict-level change outside
§5.1 and is left to the explore loop, which owns the lab's judgements; this plan only makes
`lab remeasure` *able* to reproduce them.

---

## Detailed Requirements Understanding

**Problem statement.** The lab compares numbers that were produced under different conditions and
cannot tell. The handover attributes it to the research store (three fingerprints). Measured, the
store's prices never moved (M1); the condition that did move is the engine's starting capital
(M2), which no trial records, so `lab remeasure`, `lab costs` and anything that re-runs a recorded
trial reproduces the wrong measurement — and `hardgate.trial_deposits` divides by the live
`INITIAL_IDR` to de-fund a curve, so the next change to that constant would silently mis-de-fund
every funded trial the gate reads.

**What must change.**

1. Record, per trial, the two inputs that make a re-run the same measurement and that no existing
   column carries: **starting capital** and **price fingerprint** (fingerprint of the four price
   files, fundamentals excluded). Backfill both for all 152 existing trials as an annotation in a
   new append-only table — never an UPDATE of `trials`.
2. Every path that re-runs a recorded trial (`lab remeasure` dev + seed, `lab costs`) runs it at
   the recorded capital; every path that de-funds a recorded curve divides by the recorded capital.
3. Comparability: the hard gate **refuses** (fails closed) when a method's curve and the
   benchmark's carry different or unknown price fingerprints; `lab walkforward` and `lab regime`
   (report-only) **warn** on the same condition; `lab run` refuses a dev store whose price
   fingerprint differs from the benchmark trial's, so a rebuild cannot slip into the record
   unannounced (policy (a) made mechanical).
4. Record the findings: lab insight, runbook, package readme, and correct the now-false claim in
   `remeasure.py`'s METRIC_TOL comment and the handover §5.1.

**Success criteria.**

- On a copy of the committed database, `lab remeasure M0011`, `lab remeasure M0007` and
  `lab remeasure H-P7A` reproduce (exit 0) on today's store **with today's `INITIAL_IDR` (10M)
  unchanged**.
- `lab costs M0011`'s flat column, on a copy, reads trial #90's recorded total return.
- `lab status` still prints `Promotable now: (none)`; the hard gate's verdict on every
  dev-eligible method is unchanged (0 stranded, per M5).
- The full engine suite passes; the `test_lab_snapshot` staging reminder is satisfied by
  `lab stage`.

**Assumptions.**

- The handover's 1.83% figure is not reproduced and not relied on; M4 supersedes it.
- `bbe7abfb4a12` (test store on the other laptop) has an unknown file map here; its price
  fingerprint is recorded as unknown (NULL), which affects nothing — no comparison reads test
  trials against the dev benchmark.
- Funded trials always start at `INITIAL_IDR`, never at another sum (true of the code path
  `run_method` / `run_test` today).

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/plans/HANDOVER_20261009.md`

### Discovered Related Files
- `engine/src/seer_engine/lab/store.py` — schema (`trials`, `trial_moments`, `trial_funding`,
  triggers), `SCHEMA_VERSION = "4"`, `_migrate`, `funding_of`, `insert_funding`, snapshot
  `fingerprints`
- `engine/src/seer_engine/lab/runner.py` — `recorded_contributions`, `trial_rows`, `run_method`,
  `test_trial_row`, `run_test`
- `engine/src/seer_engine/lab/hardgate.py` — `trial_deposits` (divides by `INITIAL_IDR`),
  `geometry`, `fold_record`, `check`, `summary`
- `engine/src/seer_engine/lab/walkforward.py` — pure; untouched (buy signal is the owner's)
- `engine/src/seer_engine/lab/remeasure.py` — `measure`, `run_chunk`, `METRIC_TOL` comment
- `engine/src/seer_engine/lab/real_costs.py` — `measure`
- `engine/src/seer_engine/lab/name_count.py` — runs at live capital by design (not a re-run)
- `engine/src/seer_engine/backtest/dev.py` — `_run`, `run_candidate`, `run_registry`
- `engine/src/seer_engine/backtest/book_runner.py:420` — `run_rules(..., initial_idr=INITIAL_IDR, ...)`
- `engine/src/seer_engine/backtest/runner.py:58` — `INITIAL_IDR`
- `engine/src/seer_engine/research.py` — `fingerprint_of`, `DATA_FILES`, `OPTIONAL_DATA_FILES`,
  `ResearchData`, `load_store`
- `engine/src/seer_engine/commands/lab.py` — `_run`, `_remeasure`, `_remeasure_seed`, `_costs`,
  `_regime`, `_walkforward`, `_status`
- `engine/src/seer_engine/backtest/regime.py` — `BENCH_CANDIDATE`, `defunded`, `split`
- `engine/src/seer_engine/lab/seed.py` — `P7A_FINGERPRINT`
- `docs/runbooks/data-pipeline.md`, `engine/package_readme.md`

---

## Current Dataflow

### Entry: `lab run MNNNN` → `commands/lab.py:_run` (1248)

1. `research.load_store(--store)` → `ResearchData` (`fingerprint`, `manifest` with `files`).
   No check against anything the lab has recorded.
2. `runner.run_method` (`lab/runner.py:359`) → `dev.run_registry(..., contributions=OWNER_MONTHLY)`
   — no `initial_idr` keyword exists on `run_registry`; `dev._run` calls `run_rules` without it, so
   `run_rules` uses its default `INITIAL_IDR` (10M since `d79fc83`).
3. `trial_rows` builds `store.TrialRow(store_fingerprint=data.fingerprint, git_sha=…, curve_json=…)`
   plus `MomentsRow` and `FundingRow`; `run_method` inserts all three in one `BEGIN IMMEDIATE`
   transaction (`insert_trials`, `insert_moments`, `insert_funding`).
4. Capital is never recorded. The curve is normalised to opening cash, erasing it.

### Entry: `lab test` → `runner.run_test` (696)
Same path on the test store; `test_trial_row(fingerprint=data.fingerprint)`; funding row written.

### Entry: re-runs of a recorded trial
- `lab remeasure M…` → `remeasure.measure` (372) → `dev.run_registry(..., contributions=recorded_contributions(...))` at live capital → compares Sharpe at 1e-9 relative → writes `trial_moments` or refuses all.
- `lab remeasure H-P7A` → `remeasure.run_chunk` (1026) → `dev.run_registry` at live capital → compares six metrics at 1e-6 → writes moments for the reproduced, reports the rest (exit 1).
- `lab costs M…` → `real_costs.measure` (247) → `dev.run_registry` twice (flat, gotrade) at live capital → journals an insight.

### Entry: comparisons on recorded curves (no store)
- `hardgate.geometry` (`lab/hardgate.py`) reads the first `REF-SPY-HOLD` dev trial → folds.
- `hardgate.fold_record` reads every dev trial of the method, de-funds with
  `trial_deposits` — `unit = amount_idr / INITIAL_IDR` **at the live constant** — and calls
  `walkforward.evaluate`. No fingerprint is consulted anywhere.
- `commands/lab.py:_walkforward` (1903) and `_regime` (1812) use the same benchmark and
  `hardgate.trial_deposits`; `_regime` also loads a store for breadth and prints its fingerprint.
- `hardgate.check` is called by `_promote` before `prereg.promote_method`; `hardgate.summary`
  by `_status`.

### Data persistence
`lab/lab.sqlite` (committed). Triggers: `trials_no_update`, `trials_no_delete`,
`trial_moments_no_update/no_delete`, `trial_funding_no_update/no_delete`, and others. `connect()`
migrates to `SCHEMA_VERSION` on open; `connect_readonly` does not. `lab stage` writes
`web/data/lab.json` and git-adds both.

---

## Key Data Structures

- `store.TrialRow` (`lab/store.py:~755`) — 33 fields incl. `store_fingerprint`, `git_sha`, `curve_json`; `TRIAL_COLUMNS`.
- `store.FundingRow` / table `trial_funding` (`lab/store.py:263`) — the precedent for a per-trial side table: `trial_n` PK FK, NOT NULL columns, `measured`, no-update/no-delete triggers, added by migration v4.
- `research.ResearchData` (`research.py:~185`) — `fingerprint`, `manifest`, `window`.
- `hardgate.Geometry` — `bench` curve + `folds`.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `INITIAL_IDR` | `backtest/runner.py:58` | def | backtest |
| `INITIAL_IDR` default | `backtest/runner.py:156`, `book_runner.py:256,432` | def (param default) | backtest |
| `run_rules` | `backtest/book_runner.py:420` | def, takes `initial_idr` | backtest |
| `_run` / `run_candidate` / `run_registry` | `backtest/dev.py:482,557,586` | def — no `initial_idr` | backtest |
| `INITIAL_IDR` | `lab/hardgate.py:203,210` | call (de-fund unit) | lab |
| `recorded_contributions` | `lab/runner.py:112` | def | lab |
| `recorded_contributions` | `lab/remeasure.py`, `lab/real_costs.py:258`, `lab/hardgate.py:205` | call | lab |
| `dev.run_registry` | `lab/runner.py:386,748`, `lab/remeasure.py:414,1052`, `lab/real_costs.py:280`, `lab/name_count.py:353` | call | lab |
| `store_fingerprint` | `lab/store.py:319,766,2167`, `lab/runner.py:324,672`, `lab/seed.py:118`, `lab/prereg.py:114,279,670` | column / write / read | lab |
| `SCHEMA_VERSION` / `_migrate` | `lab/store.py:70,504` | def | lab |
| `fingerprint_of` / `DATA_FILES` | `research.py:372`, `research.py` top | def | research |
| `BENCH_CANDIDATE` | `backtest/regime.py:42` | def | backtest |
| METRIC_TOL "measured … today's dev store" comment | `lab/remeasure.py:~666` | doc (now false) | lab |
| tests | `tests/test_lab_store.py`, `test_lab_runner.py`, `test_lab_hardgate.py`, `test_lab_walkforward.py`, `test_lab_remeasure.py`, `test_lab_remeasure_seed.py`, `test_backtest_dev.py`, `test_lab_snapshot.py` | test | engine/tests |
| docs | `docs/runbooks/data-pipeline.md`, `engine/package_readme.md`, `docs/plans/HANDOVER_20261009.md` §5.1 | doc | docs |

---

## Impact Points

1. `backtest/dev.py` — `initial_idr` keyword through `_run` / `run_candidate` / `run_registry` → `run_rules`. **Phase 1.**
2. `research.py` — `PRICE_FILES`, `price_fingerprint_of`, `ResearchData.price_fingerprint`. **Phase 2.**
3. `lab/store.py` — schema v5 `trial_provenance`, triggers, migration backfill, `ProvenanceRow`, `insert_provenance`, `provenance_of`. **Phase 2.**
4. `lab/runner.py` — `recorded_capital`; provenance rows written by `run_method` / `run_test`. **Phase 2.**
5. `lab/remeasure.py`, `lab/real_costs.py` — re-run at recorded capital; fix the METRIC_TOL comment. **Phase 2.**
6. `lab/hardgate.py` — `trial_deposits` divides by recorded capital (**Phase 2**); price-fingerprint comparability refusal (**Phase 3**).
7. `commands/lab.py` — `lab run` store pin (**Phase 3**); `_walkforward` / `_regime` warnings (**Phase 3**).
8. Docs, lab insight, `lab stage` of the migrated database. **Phase 4.**

**This document describes. The plan files prescribe.**
