# Phase 6 results — the R1 verdict, the sentences, and the close-out

**Date:** 2026-10-20
**Verdict:** **DONE.** The set closes with a rule on each axis, six journalled findings, and **no
promotion**. `phase-6` wrote **no `lab note` at all** — the three sentences this set moved were
already corrected by phases 3 and 5, and a three-pass sweep over all 276 methods found no fourth.
**The document:** `docs/plans/HANDOVER_20261020-control-draw-remedies.md` (653 lines).
**Plan set:** `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md`, phase 6 of 6 (`P1-ROOT-A8RK`).
**Environment:** `main`, main checkout, no worktree, `engine/.venv` (Python 3.11). No research
store was opened; this phase ran no backtest and no `lab run`.

---

## What was swept, and what it found

**276 verdicts and 276 analyses**, in three passes — the figures this set moved, the vocabulary of
a control comparison, and bound-or-floor language near that vocabulary.

- **Sentences moved: 3, all already corrected when this phase swept.** M0208 (VERDICT **and**
  ANALYSIS, by phase 3), M0221 (ANALYSIS, by phase 5), M0225 (ANALYSIS, by phase 5 — its first
  honest margin sentence; no wrong one existed to correct and none was invented).
- **Sentences found by the sweep that the phases missed: NONE.** The previous close-out's six
  phases missed four, three of them in the verdict string. The difference is that phases 3 and 5
  each swept the whole `methods` table themselves before writing.
- **Sentences that stand:** M0202 (3.6–3.8 pts, arms 0.96/0.87 and 0.97/0.89), M0215 (2 pts, arm
  0.99/0.98), M0047, M0227, M0243 (all band-clean), M0201 (2.4 pts — holds against the band-clean
  control too, at 2.475), and M0221's and M0225's **verdicts**, which rest on no control.
- **Still unmeasured: nothing**, for the first time in this family of sets.
- **The bound-language pass** found exactly one owner-facing string calling a control-shape caveat
  a floor — M0208's, already withdrawn. The other "at least" hits (M0130, M0113, M0136, M0216) are
  **pre-registered success bars**, which are promises made before a run, not margin estimates.

**One decision recorded rather than acted on:** M0201's published 2.4-point lead is a subtraction
across two store fingerprints (book on `b683da41…`, both controls on `640fc25e…`) and this set never
re-measured its *money* in one sweep. The boundary cost **0.22 points on M0221** and **exactly zero
on M0208**, so on this chassis it is unknown. **No caveat was written into the owner's text on a
guess** — that is the rule this set itself established — and it is carried as leftover 17 with the
arithmetic attached.

## Insights journalled

Six rows, **479–484**, one command each, no pipe, exit code echoed on its own line and read with
`cat`; every one exited **0** and printed its id. All six were rehearsed on a `SEER_LAB_DB` copy
first and the live hash was confirmed unmoved by the rehearsal. `count(*) = count(DISTINCT title)`
reads **6 | 6**. Bodies and the exact form are committed at
`.workflows/plan/control-draw-remedies/insights/`.

| id | kind | title |
|---|---|---|
| 479 | synthesis | A control matched on trades and turnover is still not return-neutral: it re-balances monthly and the book it controls never trims |
| 480 | synthesis | A fair opponent needs two rules on two axes, and the weight one was never buildable as a single shared rule |
| 481 | observation | An under-shaped control's margin is an estimate of unknown sign, never a floor |
| 482 | observation | A shape ratio across two research-store vintages is not a comparison until it is re-measured in one sweep |
| 483 | observation | A blind opponent's churn must be read off a replayed held set, not a freshly-taken one, and the market switch is the bigger half |
| 484 | risk | Three checks that carry no information: a digest test that passes under the edit it guards, a trade count that agrees by construction, and a refusal the gate never prints |

## The gate

**Refuses all nine**, re-read live through `store.connect_readonly` by calling `hardgate.check`
itself. **No promotion was made or implied.**

Three of the four D17 refusals this set started with — M0201's, M0221's and M0225's — were **inert
all along**: `hardgate.check` raises on the walk-forward fold majority *before* D17. M0208 was the
only method whose operative clause was D17, and the **kin rule** (`failed_kin → ('M0002',)`, a
method that has already read test-failed) stands immediately behind it. After this set only
**M0201's** D17 refusal is still live, and it is one of the inert ones. **What changed is messages
and sentences, not answers.**

## Invariants

| | before | after |
|---|---|---|
| `git hash-object lab/lab.sqlite` | `5a4011f1950871364a77cd3744849b0769865cd0` | **`fe8978fb4f735ac445af549a6e9c9e5020b81a0c`** (the six insights) |
| test-window looks | **4** | **4** |
| trials | 862, ids 1…862 contiguous | **862, unchanged** — this phase recorded none |
| methods | 276 | **276, unchanged** |
| insights | 478 | **484** |
| N (policy: methods) | 165 | **165, unchanged** |

- **I1** — no test-window look. `lab test` and `lab promote` were never invoked;
  `SEER_RESEARCH_TEST_STORE` was unset throughout. Looks **4 → 4**, asserted before and after.
- **I2** — nothing recorded or frozen was touched. No trial, no amendment, no candidate row.
- **I3 / I4** — this phase edited no file under `engine/src`. Every `lab` command was redirected to
  a capture and its exit code echoed on its own line; nothing was piped and nothing was retried.
- **I5** — the only `lab` command that could have migrated the file was `lab control`, and the hash
  was identical either side of it. Every count came from `sqlite3 "file:…?mode=ro"` or
  `store.connect_readonly`.
- **I6** — `lab stage` ran in the checkout that owns the database and its commit took **no
  pathspec**.
- **I11** — the suite was run **after** the final `lab stage`, never between a write and its stage.
- **I12** — no owner-facing string was written at all, so the tripwire had nothing to catch.

## One bookkeeping correction

`phase-3-results.md` records the luck-gate N moving **164 → 165** across its own run. That cannot be
right: `npolicy.dev_method_count` counts distinct `method_id` values holding a dev trial, M0208
already held several, and an amendment creates no method — so no run in this set could move N. The
plan index measured 165 at `e3aeeff` before the set and this phase measures 165 after it. The
database is right; that one line of phase 3's file is a slip, and nothing downstream used it.

## Left for the coordinator

Leftovers **14–19** in the handover are new and each carries its number: the membership convention
(0.067 on M0208, not 0.202; and the quoted "0.034 on M0047" is that chassis's 1996-2002 era —
whole-window it is 0.012); M0201/M0202's borderline 0.920 **with the required sentence** that the
verdict would flip on a different window, and their 2009-2015 reading of **0.827**; `control_shape`
gaining a cross-store check and `entry_w`; M0201's unverified cross-vintage 2.4; a second seed for
the twins; and the duplicated `SMOKE_BARS`. **Numbers 16 and 17 are a separate plan set — this one
was not grown to absorb them.**
