# Plan: the lab's luck gate and the promotion path

**Slug:** lab-luck-gate
**Date:** 2026-10-07 08:56:06
**Analysis:** `20261007-085606-D3K1_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/lab-luck-gate`
**Branch:** `feature/lab-luck-gate` (base: `origin/main` @ `a95126a`)
**Phases:** 9
**Status:** reconciled
**Coordinator:** —

---

## Why

The user's own statement of the problem, verbatim from the turn this command was invoked on:

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

Three further instructions from the owner, in the same session, redirected the set mid-planning
and are recorded as Decisions **D1**, **D6** and **D7**:

> this 0.95 threshold is too high man. my risk appetite is 0.90

> i am thinking of my risk appetite, and i think let's set the Max drawdown to 20% instead of 15%

> i mean, i much prefer we just rerun those methods with our new lab if it means we can make sure
> we know how they perform on the luck test

The lab exists because "the risk is overfitting, not running out of ideas" (design, preamble).
Nothing in this plan may weaken that. What it corrects is a counter that asserts an independence
the trials measurably do not have — ρ̄ = 0.595 across the 110 dev curves — and in doing so
overstates the hurdle until no candidate can ever clear it; and two thresholds the owner has
re-set on their own authority, which is theirs to do and is recorded as such.

## Requirements

Final after both reconciliation rounds. `create-task` reads this table to shape the board's
cards, so it matches the plans' **Satisfies** lines, not the draft.

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | The gate admits nothing at 110 trials and the bar rises with every exploration regardless of merit — 110 correlated variant rows deflated as 110 independent trials. | 1, 4, 5, 7 |
| R2 | A trial's verdict is frozen at the N of its run date, so verdicts are not comparable across time and a method can never be re-judged. | 2, 3, 4 |
| R3 | The promotion path is unreachable and the test window unspent, and nothing surfaces either. | 5 |
| R4 | The lab verdict and the paper roster have diverged silently — RM and RMW trade while both read `rejected`. | 6 |
| R5 | The owner's drawdown appetite is 20%, not 15%, and the bar must be one number rather than one per language. | 8 |
| R6 | Half the lab's trials have never been luck-tested; they pay into N and get no verdict for it. | 9 |

## Scope

**In scope:** `DSR_MIN` 0.95 → 0.90 and `MAX_DRAWDOWN` 0.15 → 0.20 (the owner's stated risk
appetite, 2026-10-07, on both the lab screen and design §1's go-live bar); the N the luck gate
deflates by, built as an inspectable policy but left at today's default; persisting the DSR's
inputs so a verdict can be recomputed; a derived verdict read under one policy **and at the
current N** at evaluation time; **luck-testing the 54 P7a seed trials by recovering their daily
moments** (measured at ~65 seconds for all 54 — 10.8s to load the store, 51.5s of backtests — not
an hours-long batch, though it is built resumable and chunk-invariant anyway); the narrow status edge that lets a re-judgeable rejection be reconsidered; the
promotable queue and look budget in `lab status`; recorded lab provenance for every paper roster
entry; the docs, the committed pre-registration wording and the sera site's gate display.

**Out of scope, and why:**
- `deflated_sharpe` itself (`backtest/dev.py:548`) — the formula is correct and well-tested; only
  its `n_trials` argument is wrong.
- The N **default**: `DSR_POLICY` ships as `all-trials` (today's N = every dev trial). The policy
  machinery is built, tested and inspectable, but the **third** lever is NOT pulled — see D1.
- The *set* of five P7a D8 conditions and the comparisons that apply them — unchanged. Two of
  their *thresholds* have moved (D1, D6); the conditions themselves have not.
- `DEV_END`, the D9 guard, the P7a registry — frozen by design §4. Phase 9 **runs** registry
  entries; it does not change one.
- The test window — no phase may run a `window='test'` backtest. `test_looks` reads 0 when this
  lands.
- Retiring or re-digesting any started paper roster id — forbidden by the roster's own invariants.

## Invariants

Every phase must hold all of these, and each phase's exit criteria restate the ones it could break:

1. `pytest` passes in `engine/` at the end of each phase; the web build passes at the end of phase 7.
2. **No test-window look is spent.** No phase runs a backtest with `window='test'`;
   `store.test_looks(conn)` reads `0` on the committed database when the set lands.
3. **`trials` stays append-only.** No recorded `dsr`, `eligible`, `failed` or `n_trials_at_run`
   is modified or deleted; the `trials_no_update` and `trials_no_delete` triggers stay in force.
   Everything new goes in a side table or is derived on read.
4. `deflated_sharpe`, `DEV_END`, the D9 guard and the dev store's manifest fingerprint
   (`399d0d25…`) are byte-for-byte unchanged. **This does not cover `tuning.MAX_DRAWDOWN` or
   `tuning.MIN_PROFIT_FACTOR`**, which are the owner's dials: D6 moves the first of them, in
   phase 8, and the formula that reads it is untouched.
5. No started paper roster id changes its `spec_digest`; no entry is retired or re-admitted.
6. The committed `lab/lab.sqlite` is modified by at most one phase (phase 4's migration), and that
   migration is additive and idempotent. `web/data/lab.json` is a *projection* of it and is
   regenerated — never hand-edited — by whichever phase last changed its inputs (see D10).
7. **Luck-testing a recorded trial never changes the lab's N or its trial-Sharpe variance.** The
   54 seed trials are already inside `dev_trial_count`; recovering their moments adds
   `trial_moments` rows, never `trials` rows. `store.dev_trial_count`,
   `npolicy.effective_n(conn, 'all-trials').n`, `store.dev_sharpe_variance` and
   `store.dev_daily_sharpes` must be identical before and after any remeasure batch. This is the
   invariant that keeps D7 honest: if remeasuring raised N, it would re-tighten the gate on
   everyone and the exercise would undo itself.

   **True in the code, not merely asserted in prose** (verified in round 2, and the subtlety D12
   creates): `dev_daily_sharpes` is `SELECT sharpe FROM trials WHERE window='dev' AND sharpe IS
   NOT NULL` (`store.py:562-565`), and the 54 seed rows **already carry a `sharpe`** — so the
   variance the gate deflates by genuinely does not move when their moments arrive. Phase 9's only
   write is `store.insert_moments` into `trial_moments`, which contains no `trials` row and which
   neither `dev_trial_count` nor `dev_daily_sharpes` can observe. Phase 9 asserts all four
   quantities before and after a full 54-row batch.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | The N policy and the effective-N estimator | R1 | `engine/lab` | 2 | — | NORMAL | `.workflows/plan/lab-luck-gate/phase-1.md` | P1-ENG-FNKE (done 2026-10-07) | — |
| 2 | Record the DSR's inputs with every dev trial | R2 | `engine/lab` | 5 | — | NORMAL | `.workflows/plan/lab-luck-gate/phase-2.md` | `P1-ENG-6134` | — |
| 3 | `lab remeasure` — recover the inputs for a recorded method | R2 | `engine/commands` | 3 | 2 | NORMAL | `.workflows/plan/lab-luck-gate/phase-3.md` | P1-ENG-921N | — |
| 4 | The verdict is derived under one policy, at the current N | R1, R2 | `engine/lab` | 7 | 1, 2, 8 | HARD | `.workflows/plan/lab-luck-gate/phase-4.md` | P1-ENG-B6Y5 | — |
| 5 | `lab status` shows the queue and the look budget; `lab luck` | R3, R1 | `engine/commands` | 3 | 4 | NORMAL | `.workflows/plan/lab-luck-gate/phase-5.md` | P1-ENG-QM5I | — |
| 6 | Every roster entry carries its lab provenance | R4 | `engine/paper` | 6 | — | NORMAL | `.workflows/plan/lab-luck-gate/phase-6.md` | P1-ENG-CA69 | — |
| 7 | Docs, the pre-registration wording, and the site's gate | R1 | `docs` + `web` | 25 | 4, 8 | NORMAL | `.workflows/plan/lab-luck-gate/phase-7.md` | P1-ROOT-FWWQ | — |
| 8 | The go-live drawdown bar, 15% → 20% | R5 | `engine/backtest` + `web` | 30 | — | HARD | `.workflows/plan/lab-luck-gate/phase-8.md` | P1-ENG-EH4K (done 2026-10-07) | — |
| 9 | Luck-test the P7a seed | R6 | `engine/lab` | 3 | 2, 3, 4 | NORMAL | `.workflows/plan/lab-luck-gate/phase-9.md` | P1-ENG-ALY2 | — |

### Waves

Final, from the `Depends on` column after both reconciliation rounds:

| Wave | Phases | Why |
|---|---|---|
| **W1** | **1, 2, 6, 8** | no dependencies |
| **W2** | **3, 4** | 3 needs 2; 4 needs 1, 2 and 8 |
| **W3** | **5, 7, 9** | 5 needs 4; 7 needs 4 and 8; **9 needs 2, 3 and 4** |

**Phase 9's `Depends on` moved from `2, 3` to `2, 3, 4`** in round 2, on its own planner's
correction: the eligibility report its brief mandates needs `store.verdict`, `store.gate`,
`store.DSR_MIN` and `store.dev_sharpe_variance`, all four created by phase 4, and
re-implementing that policy inside phase 9 would guarantee the two drift. **The waves do not
change** — phases 3 and 4 are both in W2, so phase 9 was already a W3 member and stays one. What
changes is that inside W3 it now waits on *both* W2 phases rather than on phase 3 alone, so a
coordinator must not release it when phase 3 alone reports done.

All nine plan files exist with complete code blocks, and the set has been reconciled twice. There
is no third round outstanding.

### Phase 1 — The N policy and the effective-N estimator
**Satisfies:** R1
**Owns:** a new pure module `engine/src/seer_engine/lab/npolicy.py`: the named policies
(`all-trials`, `methods`, `effective`), the participation-ratio estimator computed from the
month-end curves already in `trials.curve_json`, `effective_n(conn, policy) -> NCount` carrying
both the number used and the evidence behind it, and `NCount.basis` — the one-line evidence string
phase 7 commits into every pre-registration and into `web/data/lab.json`. Tests.
**Does not touch:** `runner.py`, `store.py`'s reads, any caller. Nothing in the lab calls this yet.
**Exit criteria:** `npolicy.effective_n` returns 110 under `all-trials`, 23 under `methods` and
≈2 under `effective` on the committed database; `all-trials` returns **0** on an empty lab and is
not floored; `DEFAULT_POLICY == "all-trials"`, matching `store.DSR_POLICY`; `NCount.basis` is a
non-empty single line for every policy on every lab; the `methods` policy is floored at the
measured participation ratio so it can never assert fewer looks than the evidence; `pytest` green.

### Phase 2 — Record the DSR's inputs with every dev trial
**Satisfies:** R2
**Owns:** an additive, append-only `trial_moments` side table (`trial_n`, `sr_daily`, `t`, `skew`,
`kurt`, `var_trials`, `n_at_run`, `measured`) in `store.py`'s schema and `_migrate`, its writer,
and `runner.trial_rows` populating it in the same transaction as the trial it describes. **It owns
the whole body of `trial_rows`**; phase 4 applies a two-line delta to it and nothing else.
**Does not touch:** the `trials` table's columns, triggers or contents; the eligibility decision,
which still reads exactly as it does today.
**Exit criteria:** a new `lab run` writes one `trial_moments` row per dev trial; the committed
database migrates in place without touching any `trials` row; `test_looks` still 0; `pytest` green.

### Phase 3 — `lab remeasure` — recover the inputs for a recorded method
**Satisfies:** R2
**Owns:** `lab remeasure <method>` in `commands/lab.py` and the `lab/remeasure.py` module: re-runs
*only* the dev window for a method whose trials predate phase 2, writes `trial_moments` rows and
nothing else, and is idempotent. Refuses any method with a test trial, and refuses the test window
by name.
**Does not touch:** `trials`, `methods.status`, the prereg files, the test-window store.
**Exit criteria:** `lab remeasure M0022` populates three `trial_moments` rows whose recomputed DSR
reproduces each recorded `dsr` to within 1e-6 at the recorded `n_trials_at_run` — the check that
proves the re-run is the same measurement; running it twice changes nothing; `pytest` green.

### Phase 4 — The verdict is derived under one policy, at the current N
**Satisfies:** R1, R2
**Owns:** the gate change. `store.DSR_MIN` 0.95 → 0.90 (the owner's risk appetite, 2026-10-07) —
this phase is its sole owner. `store.DSR_POLICY = "all-trials"` as the single constant that decides
N, shipped at today's N so the N lever does not move. `store.verdict(conn, trial)` deciding **every
condition at evaluation time**: the four threshold owner conditions re-derived from the trial's
recorded columns against the live constants, `owner inputs` carried from the record, and the luck
test decided on the trial's DSR **at the gate's current N** (`store.dsr_at`, exact from
`trial_moments` or recovered by `store.recover_dsr`). `best_dev_eligible` reading it; the
`("rejected", "dev-eligible")` transition, guarded twice; `runner.trial_rows` evaluating new trials
under the same gate; `lab reevaluate`; the additive, idempotent migration of the committed
`lab/lab.sqlite` (invariant 6) and its re-export of `web/data/lab.json`.
**Also owns the shared label and arithmetic helpers** every other phase calls:
`LUCK_LABEL_PREFIX` / `is_luck_label` / `recorded_labels` / `OWNER_INPUTS_LABEL` /
`owner_failures` / `sr_star` / `recover_dsr` / `dev_sharpe_variance` / `dsr_at`.
**`dsr_at` deflates by `dev_sharpe_variance(conn)` — today's lab-wide trial-Sharpe variance — on
BOTH routes (Decision D12).** The variance is read once, above the branch, and
`moments["var_trials"]` is not referenced in the function at all: the column recorded beside a
trial is historical record only and never enters a live verdict.
**Does not touch:** the set of five owner conditions, `deflated_sharpe`, `tuning.MAX_DRAWDOWN`
(read, never written — phase 8 owns it), the N default, any recorded column, `snapshot()`'s gate
dict (phase 7).
**Exit criteria:** at (N = 110, `DSR >= 0.90`, `max DD <= 20%`) exactly **three** trials are
eligible — M0022-W-TV14 (DSR 0.912, MAR 0.86), M0022-W-TV16 (0.916, MAR 0.82) and M0020-W-NOSTOP
(0.913 re-evaluated at N=110, max DD 19.3%, MAR 0.79) — and `best_dev_eligible` returns W-TV14 for
M0022 and W-NOSTOP for M0020; **M0007-N20-RAW is explicitly not eligible** (recorded 0.9138 at its
recorded N = 85, **0.8985** re-evaluated at N = 110); M0011 stays ineligible (recorded 0.8974 at
N = 90, 0.884 at N = 110); a trial whose DSR cannot be evaluated fails the luck test, so
`F9-SPY200M70-MOM30` stays out on the luck test alone and `F3-SEC-TOP3-6M-TREND` stays out on
`owner inputs` independently of its luck test (two tests, two reasons);
`store.dsr_at` uses today's variance on both routes and never the recorded `var_trials`
(`test_dsr_at_deflates_by_todays_variance_not_the_one_recorded_beside_the_trial`);
a recorded `"DSR >= 0.95"` or
`"max DD <= 15%"` is never read as a live condition; `DSR_POLICY="all-trials"`, `DSR_MIN=0.95`
**and** `MAX_DRAWDOWN=0.15` together reproduce `main`'s verdicts exactly; the recorded
`dsr`/`eligible`/`failed`/`n_trials_at_run` columns on all 110 rows are byte-identical before and
after; `test_looks` 0; `pytest` green.

### Phase 5 — `lab status` shows the queue and the look budget; `lab luck`
**Satisfies:** R3, and R1 through D1b
**Owns:** `commands/lab.py`'s `_status`: the promotion path printed **always**, including when it
is empty, with the reason it is empty; "test-window looks used: k" per design §3; a "Promotable
now" section; the D1b ratchet warning; and `lab luck`, printing the leaderboard under each policy
side by side so the gate's sensitivity is inspectable without editing a constant.
**Does not touch:** the gate, the policy default, any write path. `lab luck` is read-only, and
**every rule it applies is phase 4's** — `_owner_misses`, `_dev_var`, `sr_star` and `recover_dsr`
are all aliases or re-exports.
**Exit criteria:** `lab status` on a lab with nothing promotable prints why; after phase 4 it
lists M0022 (with W-TV14) and M0020 (with W-NOSTOP); the ratchet warning names N = 143; `lab luck`
reproduces the analysis document's N-sensitivity table and counts three clearing at N=110 and
seven at N=23; `pytest` green.

### Phase 6 — Every roster entry carries its lab provenance
**Satisfies:** R4
**Owns:** making the divergence explicit and checked rather than silent. A `lab_provenance` field
on the roster entry — the lab method and candidate id, the lab status at admission, and the
admission basis (`test-passed` or `owner-override`, with its reason) — outside the spec digest,
like `gate_note`; `store.record_promotion` writing the same fact onto the method; a test asserting
every roster entry whose id names a lab candidate has provenance that matches `lab.sqlite`.
**Does not touch:** any `spec_digest`, any started paper clock, the roster's admission *policy* —
paper membership still does not require a test pass (D3) — and **no historical gate note or
provenance reason is re-synced to the new bars**: they state what was true on the night.
**Exit criteria:** RM-FR and RMW-FR carry `owner-override` provenance naming M0011/M0022 and the
`rejected` status they were admitted under; the roster digest test still passes unchanged;
`pytest` green.

### Phase 7 — Docs, the pre-registration wording, and the site's gate
**Satisfies:** R1
**Owns:** design §3's definition of dev-eligible amended to both moved thresholds, with the
correlation evidence and the date, and §7's dated revision (7.1 the luck bar, 7.2 the N left
alone, 7.3 the deferred ratchet, 7.4 paper membership, 7.5 pointing at §1's drawdown change, 7.6
the seed re-run); `prereg.py`'s baked N wording and `docs/lab/prereg/README.md`; `SKILL.md`;
`engine/package_readme.md`; the snapshot `gate` block gaining the policy name, its N and its
evidence; the sera site's gate display, **including matching both threshold-bearing failure labels
by prefix** in `derive.ts`.
**Does not touch:** engine behavior, either threshold, the policy default, any recorded trial,
design **§1** (phase 8's) or `web/lib/metrics.ts` (phase 8's).
**Shares with phase 8, which lands first:** `web/lib/sera/fixture.ts`,
`web/app/sera/overview.test.ts`, `web/app/sera/how/view.test.ts`, `web/lib/sera/derive.test.ts`,
`web/app/sera/methods/view.test.ts`, `engine/tests/test_lab_snapshot.py` and `web/data/lab.json`.
Phase 8 moves only the drawdown number in each; phase 7 rewrites the gate objects wholesale and
**quotes the post-phase-8 state** (`maxDrawdown: 0.2` already in place). The two phases' gate
overrides in `how/view.test.ts` are written to identical values (`maxDrawdown: 0.3, dsrMin: 0.8`),
so the overlap merges as a no-op.
**Exit criteria:** no doc states a bar the lab does not apply; `derive.ts` reads both
`DSR >= …` and `max DD <= …` by prefix and both prefixes are pinned to the engine; the sera site
shows the policy and its N next to the luck bar; `npm run build` and `vitest` pass in `web/`;
`pytest` green.

### Phase 8 — The go-live drawdown bar, 15% → 20%
**Satisfies:** R5
**Owns:** `MAX_DRAWDOWN` 0.15 → 0.20 and its single home — the constant is **defined in
`backtest/metrics.py`** with `tuning` re-exporting it (`MAX_DRAWDOWN = _metrics.MAX_DRAWDOWN`),
because `metrics.checklist` compares against a literal `0.15` today (`metrics.py:271`, verified)
and `tuning.gate` / `walkforward.gate_p3b` / `b_walkforward.gate_p6a` all decide drawdown through
`checklist(...)[2:5]`, so the P3/P3b/P6a real-money gates never read `MAX_DRAWDOWN` at all. The
direction is forced: `metrics.py` imports nothing from `tuning.py` (verified), so defining in
`metrics` and re-exporting from `tuning` is the only non-circular arrangement, and every existing
reader of `tuning.MAX_DRAWDOWN` — phase 4's `owner_failures`/`_blocking` and phase 7's snapshot
assertion included — resolves unchanged. Also `dev.FAILURE_LABELS[1]`, which becomes
`f"max DD <= {tuning.MAX_DRAWDOWN:.0%}"` (**Decision D13**; `engine/src/seer_engine/backtest/dev.py`
is modified by no other phase), `tuning._GATE_NAMES`, `web/lib/metrics.ts` (which hardcodes
**both** the label and the comparison — a second implementation of go-live #4 that does not read
the engine), `web/lib/golive.ts` + its engine-pinning test, design **§1 item 4** of
`docs/plans/2026-10-03-seer-design.md` with a new dated §11, and the pinned tests.
**Does not touch:** `docs/plans/2026-10-04-method-lab-design.md` §3 and §7 (phase 7's — a
different document); `store.verdict`, `store.DSR_MIN` or any `lab/` module (phase 4 reads the
constant, never writes it); `lab/lab.sqlite`; the recorded `trials.failed` strings.
**Shares with phase 7, and lands first:** `web/lib/sera/fixture.ts`,
`web/app/sera/overview.test.ts`, `web/app/sera/how/view.test.ts`, `web/lib/sera/derive.test.ts`,
`web/app/sera/methods/view.test.ts`, `engine/tests/test_lab_snapshot.py`, `web/data/lab.json`.
Phase 8 moves only the drawdown number in each; phase 7 then rewrites those gate objects wholesale
and quotes the post-phase-8 state.
**Exit criteria:** one definition of the drawdown bar, read by the lab screen, the go-live
checklist and the web; `dev.FAILURE_LABELS[1] == f"max DD <= {tuning.MAX_DRAWDOWN:.0%}" ==
"max DD <= 20%"` and stays **prefix-stable** (`"max DD <= " + the number`), so the 30 historical
rows reading `"max DD <= 15%"` are still recognised as drawdown misses, and putting the constant
back to 0.15 reproduces the old string byte-for-byte; `FAILURE_LABELS` keeps five entries in
order; every gate-override test still overrides to a value that differs from the default
(`maxDrawdown: 0.3`, `dsrMin: 0.8`, `minProfitFactor: 1.5`, `minTrades: 50`); `lab/lab.sqlite`
byte-identical to `origin/main`; `pytest` green and `npm test` green.

### Phase 9 — Luck-test the P7a seed
**Satisfies:** R6
**Owns:** extending `seer_engine.lab.remeasure` (phase 3's module) with a seed-specific path and a
resumable batch mode over all 54 P7a trials, recovering their daily moments and writing **only**
`trial_moments` rows.
**Does not touch:** `trials` — not one row, by invariant 7 — `methods.status`, the P7a `REGISTRY`,
the test window, or any constant. It changes runtime data, not any phase's logic.
**Exit criteria:** all 54 seed trials have `trial_moments` and therefore a real luck verdict;
`store.dev_trial_count`, `npolicy.effective_n(conn, "all-trials").n`, `store.dev_sharpe_variance`
and `store.dev_daily_sharpes` are **identical before and after** (invariant 7 — true in the code,
not merely in the prose: `dev_daily_sharpes` reads `trials.sharpe`, which these 54 rows already
carry and which this phase never writes, and the phase's only write is `store.insert_moments`);
the batch is resumable and idempotent and is **~65 seconds**, not hours (10.8s store load + 51.5s
for all 54 in one `run_registry`; chunking verified bit-identical to one call);
`test_looks` 0; `pytest` green.
**It makes nothing eligible.** The report names `F9-SPY200M70-MOM30`'s resolved DSR at the gate's
N — **0.856651** under D12's today's-variance rule — prints the as-of-P7a figure (**0.903053**)
beside it in brackets so the closeness of the call stays on the terminal
(`test_the_report_names_both_variances`), and reads `luck: fail` / `not eligible`. The eligible
set is still **three**. F9 is now held out by a luck test it *received* rather than by a data gap,
which is the whole of R6.

## Reconciliation Log

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Phase 1 set `npolicy.DEFAULT_POLICY = "methods"` (written before the owner's instruction) while phase 4 sets `store.DSR_POLICY = "all-trials"`; phase 1's Handoffs told phase 4 to write `DSR_POLICY = npolicy.DEFAULT_POLICY`. | Contract drift + unmet assumption | Phase 1's default changed to `"all-trials"`, so the two cannot disagree; phase 4 keeps its explicit literal. Phase 1's handoff rewritten to say so, and a test pins each side. |
| 2 | Phase 7 reads `NCount.basis`; phase 1's `NCount` had no such attribute (only `evidence()`). Phase 7 would not import. | Unmet assumption → broken build | `basis` added to phase 1 as a property, specified to phase 7's contract (one line, non-empty, no newline, stable). Phase 7's "if phase 1 names it differently" escape hatch replaced with the settled name. |
| 3 | Phase 7's snapshot guard required `dsrN >= 1`; phase 1's `all-trials` returns **0** on an empty lab and `snapshot` runs on empty fixtures. | Unmet assumption → test failure | Phase 7 relaxed to `>= 0` in `requireGate`, the snapshot assertion and the web contract test. Phase 1's design note 1 (`all-trials` is the literal row count, unfloored) wins — its exit criteria and test both assert 0. |
| 4 | Phase 2's `MomentsRow` has eight fields including `measured: str` (no default, `NOT NULL`); phase 3's `Requires` listed seven and `_moments_row` constructed the row without it. | Unmet assumption → `TypeError` | Phase 3's `_moments_row` takes a `measured` argument and `remeasure()` passes `store.now_iso()` — the backfill's own stamp, not the old trial's `run_at`. Phase 3's Requires table updated; phase 2's handoff made binding. |
| 5 | Phases 2 and 4 both rewrote the whole of `runner.trial_rows`, with different bodies; phase 4's called a `_moments_row` helper phase 2 does not define, used `_dsr` where phase 2 inlines `deflated_sharpe`, and bound `metrics` where phase 2 binds `met`. | File collision + contract drift | Phase 2 owns the body. Phase 4's Step 6a rewritten to quote phase 2's post-change code verbatim with only its two-line delta (`pending_gate` / `n_trials = gate.n`) substituted. Stated reciprocally in both files. |
| 6 | Phase 5's Step 9 replaced the whole `_HANDLERS` dict, which would have deleted phase 3's `"remeasure"` and phase 4's `"reevaluate"` keys. Its Step 1 replaced the whole import block. | File collision | Both converted to **insertions**. All three phases now carry a shared-file protocol table naming every anchor, with the rule "insert at your anchor, never rewrite a literal, never `git add -A`". The post-merge dict is quoted in phase 3. |
| 7 | `lab reeval` (phase 5, read-only) and `lab reevaluate` (phase 4, writes) differ by two characters and do opposite things. | Contract drift / trap | **Owner's call (D9):** phase 5's command renamed `reeval` → **`lab luck`**; phase 4 keeps `reevaluate`. Applied across phases 1, 3, 4, 5, 7 and this index — handler, subparser, `_HANDLERS` key, test file name, docstrings and every prose mention. Verified by grep: 0 remaining `reeval` that is not part of `reevaluate`. |
| 8 | Phase 5's `_owner_misses` carried its own luck-label rule (`not f.startswith("DSR ")`) over the recorded `failed` string; phase 4 owns `store.owner_failures`. Both phases also fixed `commands/lab.py:204-206` independently. | Duplicate work + two definitions of one rule | Phase 4 owns both (it lands first and owns the symbol). Phase 5's helper is a one-line delegation **taking the row**, and a test asserts it contains no rule of its own. Phase 5's Step 7a demoted from a fix to a tidy, with phase 4's post-change code quoted. |
| 9 | `M0011-RAW20-TV14-N21` quoted as 0.897 (phase 4, analysis) and 0.884 (index, phase 7) with neither labelled. | Numeric discrepancy | Measured: **0.8974 recorded at its recorded N = 90**; **0.884 re-evaluated at today's N = 110**. Convention fixed as **D8** and applied in phases 4, 5, 6, 7 and this index: the gate always uses re-evaluated-at-current-N; a recorded value is quoted only about the database and is always labelled *recorded*, with its N. Phase 4's "≈0.883" corrected to 0.884 in both places. |
| 10 | `web/data/lab.json` regenerated by phases 4 and 7 (and now 8); invariant 6 named only `lab.sqlite`. Phase 4 used `lab stage`, which also `git add`s, in a shared worktree. | Duplicate work on a generated artifact | **D10:** the file is a projection, regenerated by whichever phase last changed its inputs, never hand-edited, and a conflict in it is resolved by re-running `lab export-json` — never merged. Phase 4 switched from `lab stage` to `export-json` plus an explicit path allowlist, matching phase 7. Invariant 6 extended. |
| 11 | `commands/lab.py` edited by phases 3, 4, 5; `lab/store.py` by 2, 4, 6, 7; `runner.py` by 2, 4; `test_lab_store.py` by 2, 4, 6; `test_lab_snapshot.py` by 2, 7. | File collision | Verified disjoint by anchor and tabulated in each plan. No dependency edges added — the merges are stated as insertions and unions instead, so order does not matter. **All `store.py` line numbers in phases 4, 6 and 7 are pre-phase-2 and will have moved**; every plan now says to anchor on quoted text, not line numbers. |
| 12 | Phase 4's opening note claimed the index's Phase 4 section was stale (`DSR_POLICY` default `methods`, `DSR_MIN` under "does not touch", W-TV16 as best). | Contract drift | The index was already correct on all three. The staleness note and the Handoffs #1 request are removed and marked settled. |
| 13 | Stale file counts: index said 4/4/6/8 where the plans report 2/5/6/25. | Contract drift | Phase table corrected from the planners' returned contracts: 1→2, 2→5, 3→3, 4→7, 5→3, 6→6, 7→25, 8→29. |
| 14 | **Owner change (D6):** `tuning.MAX_DRAWDOWN` 0.15 → 0.20 broke phase 4's core design — `verdict` read the four owner conditions out of the recorded `failed` string, so all 110 rows would keep `"max DD <= 15%"` for ever and `M0020-W-NOSTOP` could never become eligible. | Contract drift forced by a late requirement | Phase 4's `owner_failures` rewritten to take the **trial row** and **re-derive the four threshold conditions from its recorded columns** against the live constants, carrying only `owner inputs` from the string. `is_luck_label` kept for the three display readers. Phase 4 gains a dependency on phase 8. Nine of phase 4's existing tests re-pinned (drawdown fixtures 0.20 → 0.245, which is outside the new bar). |
| 15 | **Owner change (D6), second-order:** `derive.ts` matched `drawdown: 'max DD <= 15%'` by exact equality — after phase 8 the engine writes `max DD <= 20%` and a *missed* drawdown would render as a green tick. Nobody had found this. | Gap | Phase 7's Step 13 extended with `DRAWDOWN_FAILURE_PREFIX`, a second engine-side pin (`test_the_web_mirrors_the_engines_drawdown_label_prefix`) and a second data pin in Step 14. `DSR_FAILURE_PREFIX` aligned to `'DSR >= '` so it mirrors `store.LUCK_LABEL_PREFIX` verbatim. |
| 16 | **Phase 4 / phase 8 disagreement:** phase 8 reported four eligible candidates, this pass measured three. | Behavioural fork | **D11.** Settled on re-evaluation at the current gate N. Exactly one trial disagrees — `M0007-N20-RAW`, recorded 0.9138 at N = 85, **0.8985** at N = 110 — and admitting it would admit a candidate for having been tried *earlier*, which is R2's defect exactly. Phase 4's `verdict` rewritten: the `n_trials_at_run == gate.n` condition is **gone**, replaced by `store.dsr_at` over every trial with a recorded DSR. Count is **three** everywhere. |
| 17 | NULL-`dsr` trials would have become eligible the moment the drawdown bar moved, on a luck test nobody ran. | Gap (exposed by D6) | **D11.** `verdict` applies `runner.trial_rows`'s own rule — `dsr is None` ⇒ the luck label is appended. Two committed rows have this shape: `F9-SPY200M70-MOM30` (passes all five owner conditions at 20%) and `F3-SEC-TOP3-6M-TREND` (which also records `owner inputs`, so it has two independent reasons). Both pinned as named tests, each with its own reason. |
| 18 | `store.dsr_at`'s two routes disagreed by up to **0.098** — eleven times the margin the gate decides by — because route 1 used the `var_trials` recorded beside the trial while route 2 used today's. | Contract drift found while reconciling | **Round 1 fixed the docstring and believed it had fixed the code; it had not.** Phase 9, reading phase 4 after round 1, found route 1 still passing `float(moments["var_trials"])` to `deflated_sharpe`. **Round 2 fixed the code** (D12): the variance is now read **once, above the branch**, and `moments["var_trials"]` is not referenced anywhere in `dsr_at`. Measured agreement: **1.3e-5** across all 56 trials. Phase 4's `_reconstruct_moments` helper already solved `t` against the same variance, so it needed no change. Pinned by `test_dsr_at_deflates_by_todays_variance_not_the_one_recorded_beside_the_trial`. The recorded `var_trials` stays in `trial_moments` as history. |
| 19 | Phases 4 and 5 each defined the deflated Sharpe's inversion (`sr_star` / `recover_dsr`) once phase 4 needed it for `dsr_at`. | Duplicate work | Defined once in `lab/store.py` (phase 4), re-exported by `commands/lab.py` so phase 5's call sites and tests read unchanged. `_dev_var` likewise becomes an alias for `store.dev_sharpe_variance`. Phase 5's own handoff anticipating this move is marked done. |
| 20 | Phase 5's status fixtures used `n_trials_at_run` far from the fixture lab's N, relying on a "falls back to the recorded columns" case in phase 4 that D11 deleted — the ratchet warning would not have fired. | Unmet assumption → test failure | Fixtures re-pinned to `n_trials_at_run=2`, matching their two-trial labs, so `recover_dsr`'s identity makes the re-evaluation a no-op. The reason is written into the file so the next editor does not undo it. Phase 5's `LUCK_ONLY` table grew from five rows to **seven** (the 20% bar admits M0020-W-NOSTOP and M0007-N20-RAW into the luck-only pool) and its D1 counts changed from 2-and-5 to **3-and-7**. |
| 21 | **Owner change (D7):** the Scope line "Re-running the 54 P7a seed trials … They keep their recorded verdicts forever" is overridden. | Scope override | Line deleted from Out-of-scope and moved into In-scope. New phase 9, new R6, new **invariant 7** (remeasuring must not move N). Phase 4's seed-trap tests annotated as describing the pre-remeasure state — one now skips itself once those rows have moments — so phase 9 cannot break them by running. |
| 22 | Decision numbering collided: this pass had used D6–D9 for its own forks before the owner's D6 and D7 arrived. | Bookkeeping | Renumbered throughout phases 4 and 5: quoting convention → **D8**, `lab luck` rename → **D9**, `lab.json` one-writer → **D10**, re-evaluate-at-current-N → **D11**. Phase 6's three references to "Decisions D5" corrected to **D3**, which is the decision they describe. |
| 23 | **Carried forward, unverified:** phase 8 moves `MAX_DRAWDOWN` into `backtest/metrics.py` with `tuning` re-exporting it. | Ordering risk | **Round 2: verified against the files on disk and clean.** `metrics.py:271` really compares against a literal `0.15`; `tuning.py:27` really defines `MAX_DRAWDOWN = 0.15`; `metrics.py` imports nothing from `tuning.py`, so the re-export direction is the only non-circular one. `tuning.MAX_DRAWDOWN` survives as a module name bound to `0.20`, and phase 4's `owner_failures`/`_blocking` and phase 7's snapshot assertion resolve through it unchanged. One anchor correction: phase 8 cited the `tuning.py` import as `:17–:18`; it is `:16–:17`. The quoted replacement block was already correct. |
| 24 | **Carried forward, unverified:** the gate-override tests become no-ops once the defaults become 0.2 / 0.9 — they would pass while proving nothing. | Latent test rot | **Round 2: verified, and the paths in this row were wrong.** The real files are `web/app/sera/how/view.test.ts` and `web/lib/sera/derive.test.ts`; there is no `web/app/sera/how/derive.test.ts`. Phases 7 and 8 both set `how/view.test.ts` to `maxDrawdown: 0.3, dsrMin: 0.8` — **identical values**, so the overlap merges as a no-op. `derive.test.ts`'s override (`maxDrawdown: 0.3, minProfitFactor: 1.5, minTrades: 50`) is **phase 8's alone**; phase 7 does not touch it. Phase 7's handoff corrected to say so. **Whoever merges second still checks the override *values*, not merely that the file merged.** |
| 25 | **Phases 8 and 9 had not been reconciled against phases 1–7.** Their plan files were written concurrently with round 1. | Needed a second round | **Done in round 2.** Every item checked: the design-document region split (row 29), prefix-stability of `dev.FAILURE_LABELS[1]` (row 28), the shared web test files (row 27), invariant 7 (row 32), phase 9's `trial_moments`-only write (row 32), the `MAX_DRAWDOWN` home (row 23), the override trap (row 24), and the `dsr_at` variance (row 18). Rows 26–34 are round 2's own findings. |
| 26 | **Phase 9's `Depends on` was `2, 3`**, but the eligibility report its brief mandates needs `store.verdict`, `store.gate`, `store.DSR_MIN` and `store.dev_sharpe_variance` — all four created by phase 4. | Unmet assumption | Accepted its planner's correction to **`2, 3, 4`**. Waves are **unchanged** (3 and 4 are both W2, so phase 9 was already W3), but a coordinator must no longer release phase 9 when phase 3 alone reports done. Stated explicitly in the Waves table. |
| 27 | **Phase 8 touches four files the index said it does not** — `web/lib/sera/fixture.ts`, `web/app/sera/overview.test.ts`, `web/app/sera/how/view.test.ts`, `engine/tests/test_lab_snapshot.py` — plus `web/lib/sera/derive.test.ts` and `web/app/sera/methods/view.test.ts`, which phase 7 also touches. | File collision | **Phase 8 keeps them** (rule 3: the earlier phase owns the region — phase 8 is W1, phase 7 is W3), confined to the drawdown number. **Phase 7 quotes the post-phase-8 state** (rule 4) — its blocks already carry `maxDrawdown: 0.2`. Both plans gained a shared-files table naming every file and who writes what; the index's "does not touch" claim is deleted. |
| 28 | **Phase 8 refused to move `dev.FAILURE_LABELS[1]`**, on the premise that `derive.ts` matches it by exact equality so a changed label would render 30 committed misses as passes. The index's own phase-8 exit criterion required the opposite ("follows it and stays prefix-stable"). | Contract drift + a behavioural fork | **Decision D13: the label moves**, as `f"max DD <= {tuning.MAX_DRAWDOWN:.0%}"`, owned by phase 8 (new Step 3b; `backtest/dev.py` modified by no other phase). The premise is removed by phase 7, which replaces that matcher with `DRAWDOWN_FAILURE_PREFIX` and pins it with a test asserting **both** texts start with the prefix. Left frozen, phase 4's `owner_failures` would name a 15% bar for a trial judged at 20% — a false reason in an append-only column. Phase 8's Decision 2 rewritten as reversed-with-reasons, its H1a handoff closed, `test_lab_test_window.py:327`'s literal made symbolic, and a new exit criterion and test added. |
| 29 | **Design-document region split**, carried forward unverified. | Ordering risk | **Verified and disjoint, and they are two different documents.** Phase 8 owns `docs/plans/2026-10-03-seer-design.md` §1 item 4 + a new §11; phase 7 owns `docs/plans/2026-10-04-method-lab-design.md` §3 and §7 (7.1–7.6), and §7.5 only *points at* §1 rather than editing it. No overlap. |
| 30 | **The brief told phase 4 to pin `F3-SEC-TOP3-6M-TREND` as an "ineligible-by-NULL seed trap".** Phase 9 measured it and found that false: F3 fails `owner inputs` (nine sector ETFs), which is not a threshold and which no constant re-decides. | Gap / wrong premise propagated | Phase 4's single combined test split into two: `test_f9_the_one_seed_row_held_out_by_the_luck_test_alone` (the NULL-DSR rule, state-dependent, self-skipping once phase 9 has run) and `test_f3_stays_ineligible_on_owner_inputs_whatever_its_luck_test_says` (**unconditional**, takes no view on F3's DSR). Phase 7's design §7.5 rewritten to give the two rows their two different reasons. Phase 9's cross-reference corrected. |
| 31 | **`test_the_report_names_both_variances` was referenced twice in phase 9 and never defined**, and `SeedVerdict.dsr_today_var` would have become a duplicate of `v.dsr` once D12 landed — so the report would have printed one number twice and the fork would have vanished from the terminal. | Gap + contract drift created by D12 | Field renamed `dsr_recorded_var` and computed from `moments["var_trials"]`; `seed_verdicts` and `format_seed_report` relabelled so the **gate's** number leads and the as-of-P7a number follows in brackets. The missing test written (16 tests, not 14), asserting both numbers are the right two, that they differ, and that both appear in the formatted text. |
| 32 | **Invariant 7** (remeasuring never moves N or the trial-Sharpe variance), carried forward unverified. | Ordering risk | **Verified in the code, not just the prose.** `store.dev_daily_sharpes` is `SELECT sharpe FROM trials WHERE window='dev' AND sharpe IS NOT NULL` (`store.py:562-565`), and the 54 seed rows already carry a `sharpe`; phase 9's only write is `store.insert_moments` into `trial_moments`, which holds no `trials` row. So `dev_trial_count`, `effective_n('all-trials').n`, `dev_sharpe_variance` and `dev_daily_sharpes` are all genuinely immovable by this phase. Phase 9 asserts all four. |
| 33 | **Wall-clock wording.** Phase 9 was briefed as a long job needing resumability; it measured **~65s total** (10.8s store load + 51.5s for all 54). | Stale premise | Phase 9 already recorded the true cost. Phase 3's `_remeasure` docstring ("re-running an hour of backtests") corrected with the measured numbers, and the index's phase-9 exit criteria now state them. The chunked/resumable design is kept — it is cheap and verified bit-identical — but no plan or doc describes it as hours-long. |
| 34 | **Phase 3 asserted the `H-*` families can never be re-run** (docstring + `LabError` message), and its exit criterion 3 pinned `lab remeasure H-P7A-F1` as exiting 2 — both false after phase 9. Phase 3 also gave no reason why `SHARPE_TOL` is relative while phase 9's `METRIC_TOL` is absolute. | Contract drift + gap | Ownership left with **phase 9** (it lands after 3 and quotes phase 3's text as its diff's left side — rule 4 in the other direction). Phase 3 gained: forward-pointers in both code sites telling the implementer to write the text as it stands and not to revert phase 9's correction; a "Changed later by phase 9" table in its Interface Contract; exit criterion 3 annotated as deliberately temporary (its unit test `test_a_seed_family_is_refused_by_name` stays green, because phase 9 keeps `resolve_method` refusing `H-*` and dispatches before it); and the relative-vs-absolute rationale written at `SHARPE_TOL` — full-precision engine floats give ulp-scaled error (relative), a CSV rounded to 6 dp gives a 5e-7 magnitude-independent bound (absolute). |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| D1 — the gate admits nothing at 110 trials. Which lever moves: the threshold (0.95), the N (110 trial rows vs 23 methods vs measured 2.4), or both? | **the thresholds, not the N.** `DSR_MIN` 0.95 → 0.90 (phase 4) and, with D6, `MAX_DRAWDOWN` 15% → 20% (phase 8) — a **pair** of owner-set bars, both moved by the owner in this session. `DSR_POLICY` ships defaulted to `all-trials`, so N is unchanged; the policy module, its evidence and `lab luck` are still built, so the third lever is measured and ready but not pulled. | 5: the owner's instruction, given in this session — "this 0.95 threshold is too high man. my risk appetite is 0.90". Measured: at (N=110, 0.90, 20%) exactly **three** candidates become eligible — M0022-W-TV14, M0022-W-TV16 and M0020-W-NOSTOP, the three highest-MAR books in the lab. Pulling the N lever too (N=23) would admit **18 of the 25** trials that miss no owner condition — **corrected 2026-10-07 by the coordinator on phase 5's measurement**; the "seven" this row originally quoted came from the plan's `LUCK_ONLY` tuple, which is a 7-row *sample* and not the pool. Measured on the committed database: 56 dev trials carry a recorded DSR, 25 of those miss no owner condition, and 3 / 12 / 18 of them clear the 0.90 bar at N = 110 / 37 / 23. **The decision is unchanged and strengthened** — the number D1 actually rests on is the exactly **three** eligible at the live N = 110, which is exact and asserted by name. Moving the two levers the owner chose admits the right three; moving the third admits fifteen more the owner never asked for, and would make it impossible to say afterwards which change did the work. |
| D1b — the ratchet R1 named is deferred, not removed: at `DSR_MIN` 0.90, M0022-W-TV16 passes at N=110 (0.916) and fails at N=143 (0.8997), roughly 33 more dev trials | **accept the deferral, and make it visible**: phase 5's `lab status` must warn when the best luck-only candidate is within 0.03 of the bar, naming the N that would sink it | 4: the index's own Why — the complaint is that the bar rises silently with every exploration. A threshold change buys ~33 trials of runway; the warning is what stops the next deadlock being discovered 110 trials late. |
| D2 — `rejected` is terminal, so M0022 can never be re-judged under a corrected rule: add an edge, or require a new method id for every re-evaluation | **add `("rejected", "dev-eligible")`, taken only by `reevaluate_method`, only from `rejected`, and only for a trial that clears all five conditions at the bars in force** | 1: the stated invariant. "Status moves forward only" protects *verdicts from being erased*; the verdict stays in the append-only `trials` table untouched and the re-evaluation is appended to `analysis`. A new method id would instead force a duplicate digest, which `has_trial` refuses outright — so R1 is unsatisfiable without this edge. |
| D3 — does a paper roster entry require a test pass (design §3/§6), or not (`roster.py:62-65`)? | **not** — paper membership keeps its own admission criterion; what changes is that the basis becomes recorded and checked | 5: the user's raw input calls the divergence *silent*, so the complaint is the silence. Reversing the policy would retire RM-FR and RMW-FR mid-clock, which invariant 5 and the roster's own "a changed strategy needs a new id" rule forbid. |
| D4 — recovering DSR inputs for existing lab trials: re-run all of them, or on demand per method | **on demand, `lab remeasure <method>`** (phase 3), with the gate re-evaluating the recorded DSR at the current N meanwhile, so no trial waits on a backtest to be judged | 6: surrounding convention — the lab never silently re-runs what it has recorded, and an unattended night must not depend on a long batch of backtests it did not ask for. (Measured afterwards: a full 54-candidate seed re-run is ~65 seconds, so the cost argument is weaker than it looked; the *convention* argument — don't re-run what is recorded unless asked — is what still carries this decision.) Note D7 then made the *seed* trials a deliberate exception, because for them there is no recorded DSR to re-evaluate at all. |
| D5 — phase 4 changes the committed `lab/lab.sqlite`; which phase owns the migration | **phase 4 alone**, additive and idempotent; phase 2 ships the schema but migrates nothing it does not write | 6: convention — one writer per binary artifact, because `lab.sqlite` cannot be merged and the waves run concurrently. |
| D6 — the owner's 20% drawdown: lab screen only, or design §1's go-live #4 too? | **both — `tuning.MAX_DRAWDOWN` 0.15 → 0.20**, phase 8, with the constant moved to one home that every reader actually reads | 5: the owner's instruction. The scope fork was put to them explicitly with the blast radius named (10 reading modules, the go-live checklist, a separate hardcoded copy in `web/lib/metrics.ts`) and they chose both. Recorded as the owner's call on a real-money safety setting, not an inference. |
| D7 — the 54 P7a seed trials have `dsr IS NULL` and under D11's rule are permanently ineligible by data gap rather than by merit. Leave them, or re-run to recover their moments? | **re-run them** — phase 9, extending `lab remeasure` with a seed path and a batch mode, writing `trial_moments` only | 5: the owner's instruction in this session. Supported by measurement: the 54 are **already** inside `dev_trial_count` = 110, so they pay the full multiple-testing penalty and receive no verdict — luck-testing them raises the bar for nobody (invariant 7 makes that binding). `F9-SPY200M70-MOM30` passes every owner condition at the new 20% bar and its DSR is underdetermined across 0.744–0.979 from recorded data alone, straddling the 0.90 bar; it cannot be resolved without the re-run. All 54 candidates remain in the frozen P7a `REGISTRY` (verified, len 54), so they are runnable without touching that frozen record. |
| D8 — `M0011-RAW20-TV14-N21` is quoted as both 0.897 and 0.884, and the same ambiguity recurs for M0007 and M0020. Which number is "the" DSR? | **both are real and neither stands alone.** The **gate** always uses the value **re-evaluated at the current N**. A **recorded** value is quoted only when the subject is what the database holds, and is then always labelled *recorded*, with its N. | 4: the index's Requirements table, R2 — "verdicts are not comparable across time and the leaderboard mixes bars" is precisely the defect an unlabelled number reproduces. Measured: M0011 is 0.8974 recorded at N = 90 and 0.884 at N = 110 — a gap wider than the margin the gate decides by. |
| D9 — `lab reeval` (read-only) and `lab reevaluate` (writes) differ by two characters and do opposite things | **rename phase 5's to `lab luck`**; phase 4 keeps `lab reevaluate` | 5: the owner's instruction in this session ("rename reeval to something clearer"). "Luck" is already this codebase's word for the DSR — the sera site draws the threshold as the "Luck bar" (`web/app/sera/overview.ts:328`), the lab verdicts read "rejected on luck only" (`dffac31`), the analysis document and this index both call it the luck test, and phase 5's own helpers are named `_best_luck_only` and `_owner_misses` around it. The rename costs no new vocabulary. |
| D10 — `web/data/lab.json` is regenerated by phases 4, 7 and 8. Invariant 6 names only `lab.sqlite`. Who owns it? | **nobody owns it; it is a projection.** Whichever phase last changed its inputs (`lab/lab.sqlite` or an engine constant in the `gate` block) regenerates it with `lab export-json` and stages it explicitly. It is never hand-edited, and a conflict in it is never merged — it is re-derived. | 6: the surrounding convention invariant 6 already encodes for `lab.sqlite` (one writer per unmergeable artifact), applied to a file that *is* mergeable but whose merge is always wrong. `lab stage` is avoided by every phase because it `git add`s, and the swarm shares one worktree. |
| D11 — a recorded DSR was computed at the N in force on its run date. Does the gate read it as recorded, or re-evaluate it at the current N? | **re-evaluate at the current gate N, always. And a DSR that cannot be evaluated fails the luck test.** | 4: the index's Requirements table, R2 — "a trial's verdict is frozen at the N of its run date, so verdicts are not comparable across time and the leaderboard mixes bars". Exactly one trial disagrees between the two readings: `M0007-N20-RAW`, recorded **0.9138 at N = 85**, **0.8985 at N = 110**. Admitting it while judging M0022's variants at N = 110 would admit a candidate for having been tried *earlier* — the self-deception the lab exists to prevent. It is also strictly more conservative and costs nothing: `recover_dsr` is exact arithmetic on recorded data, with no backtest re-run. The NULL half follows the same logic and matches `runner.trial_rows`'s own rule for a new trial. |
| D12 — the per-trial `var_trials` recorded in `trial_moments`, or the lab's trial-Sharpe variance as it stands now? **This one decides a candidate.** | **today's — `store.dev_sharpe_variance(conn)` — on both of `dsr_at`'s routes, read once above the branch. The `var_trials` column recorded beside a trial is historical record only and must never enter a live verdict.** | **4: the index's Requirements table, R2** — *"a trial's verdict is frozen at the N of its run date, so verdicts are not comparable across time and the leaderboard mixes bars."* The hurdle is `SR* = sqrt(var_trials) × E[max over N]`; using each trial's as-of-run variance freezes **half the hurdle** at its run date and reintroduces exactly the incoherence R2 exists to remove. It is the same rung and the same principle on which D11 settled `M0007-N20-RAW` (re-evaluate at the current N, not the recorded one) — **the two decisions must agree or the gate is incoherent.** Measured: the recorded variance put the two routes **0.098** apart — eleven times the gate's deciding margin — against **1.3e-5** when both use today's; and phase 9 verified independently that route 2 with `dev_sharpe_variance` reproduces phase 4's own quoted `M0007-N20-RAW` figure of **0.8985** exactly (the as-of-run variance gives 0.8962), which shows phase 4's numbers were taken under the docstring and the route-1 code was the outlier. **Consequence, and it is the headline of the set:** `F9-SPY200M70-MOM30` — the one of 54 P7a seed trials that passes every owner condition at the new 20% bar, with its real moments now measured (t=4983, sr_daily=0.054990233, skew=-0.398685892, kurt=10.209918596) — reads **0.903053** under the stored as-of-P7a variance (2.006691e-04) and **0.856651** under today's (2.395048e-04). Under this decision it reads **0.8567 and stays ineligible — but on a luck test it finally RECEIVED, rather than on a data gap.** That is R6 satisfied either way, and it is what the owner asked for in saying they would rather re-run than wonder. **The eligible set therefore remains THREE:** M0022-W-TV14, M0022-W-TV16, M0020-W-NOSTOP. Phase 9's report prints both figures side by side so the fork stays visible on the terminal rather than buried in a constant. |
| D13 — `dev.FAILURE_LABELS[1]` reads `"max DD <= 15%"` while the bar it names becomes 20%. Freeze the label (phase 8's first draft) or make it follow the constant (the index's own exit criterion)? | **follow the constant: `f"max DD <= {tuning.MAX_DRAWDOWN:.0%}"`, owned by phase 8.** Five entries, same order, prefix `"max DD <= "` unchanged, and byte-identical to the old string whenever the constant is put back to 0.15. | 2: the phases' exit criteria. The index's phase-8 criterion already said the label *follows* the constant and stays prefix-stable, and phase 7's exit criterion 0 asserts **both** `dev.FAILURE_LABELS[1]` and the historical `"max DD <= 15%"` start with `DRAWDOWN_FAILURE_PREFIX` — an assertion with content only if the two may differ. Phase 8's counter-argument rested on `derive.ts` matching by exact equality, which **phase 7 removes**; rung 3 (the plans' code blocks) therefore agrees rather than conflicts. Left frozen, phase 4's `owner_failures` — which re-derives the condition from the numeric column and reports it *with the live label text* — would tell a trial judged at 20% that it missed `"max DD <= 15%"`: a false reason written into an append-only column for ever. The recorded strings on the 110 committed rows are never rewritten; only what the engine writes next changes. |

## Open Questions

**_None._ This section is empty, and that is the finished state, not an omission.**

Every fork above was decided on a stated rung: four the owner settled in session (**D1, D6, D7,
D9**) and six this reconciliation settled (**D8, D10, D11, D12, D13**, and the ownership splits
recorded in the Reconciliation Log). Every requirement id **R1–R6 is served by at least one
phase**, and the Requirements table maps each to the phases that ended up serving it.

Nothing in this set destroys data, rewrites published history, or performs an unrepeatable
migration — the only three conditions that would justify parking a fork here. Both gate changes
are one constant each and revert by putting the constant back; the new transition edge is
additive; phase 9 writes only a side table and never a `trials` row; `trial_moments` is
append-only but carries no verdict, so a bad row is inert rather than destructive; and every
recorded `dsr`, `eligible`, `failed` and `n_trials_at_run` on all 110 rows is preserved
byte-for-byte and verified by digest.

**Both reconciliation rounds are complete.** Round 1 reconciled phases 1–7 and reported honestly
that it could not finish phases 8 and 9. Round 2 finished them and re-checked the whole set: see
Reconciliation Log rows 18 and 23–34. All nine plan files exist with complete code blocks. There
is no third round outstanding and nothing is waiting on an answer.

## Rollback

**Per phase.** Each phase is one commit on `feature/lab-luck-gate` and reverts cleanly; phases 1,
2, 3, 5, 6 and 9 are purely additive and reverting one leaves the gate exactly as it is on `main`.

**Phase 4 specifically** — the phase that changes a verdict. Setting `store.DSR_MIN` back to 0.95
restores the old luck bar on the next evaluation, with no data change, because every recorded
column is preserved and the verdict is read at call time. The `lab.sqlite` migration is additive:
reverting the code leaves an unread `trial_moments` table. A method moved `rejected → dev-eligible`
can be left where it is or re-rejected by the next `lab run`; the trials that decided it never
changed.

**Phase 8 specifically** — the other phase that changes a verdict, through
`tuning.MAX_DRAWDOWN`. Setting it back to 0.15 restores the old drawdown bar everywhere at once,
which is the whole point of giving it one home. No data changes, on either the lab screen or the
go-live checklist.

**As a whole.** `git branch -D feature/lab-luck-gate` before the merge; after it, revert the merge
commit. The committed `lab.sqlite` needs `git checkout origin/main -- lab/lab.sqlite` as a
separate step, since a binary revert is not a merge; `web/data/lab.json` comes back with it.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f LAB_LUCK_GATE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f LAB_LUCK_GATE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan LAB_LUCK_GATE_PLAN.md
