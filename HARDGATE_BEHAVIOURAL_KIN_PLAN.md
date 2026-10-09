# Plan: Hard gate kin follows behaviour (D14)

**Slug:** hardgate-behavioural-kin
**Date:** 2026-10-09 21:55
**Analysis:** `20261009-215504-K7Q2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/hardgate-behavioural-kin`
**Branch:** `feature/hardgate-behavioural-kin` (base: `origin/main` @ `461580a`)
**Phases:** 1
**Status:** planned
**Coordinator:** —

---

## Why

Verbatim from the owner:

> Close a third hole in the hard gate's kin check (K), found by Sera in batch sera-20261009-2125 — read lab insight 92 in full. The kin rule follows family strings, parent_id ancestry, and since D12 blend ingredients. But a plain momentum book filed under a brand-new family name, with a non-momentum parent, is not linked to the momentum families that already read test-failed (stock-residual-momentum, stock-momentum-risk-managed, stock-multi-factor-blend), so the gate would not block it. Queued ideas M0060 (stock-low-volume-momentum) and M0062 (stock-liquidity-tilt) are the live examples. Nobody meant to dodge; the filing lets it happen by accident.
>
> Make kin follow what a method actually is, not what it is called. Measure the candidates before choosing, as D4/D10/D11/D12 in hardgate.py did — state each option, measure what it blocks across the committed lab, pick, and say why: (a) a machine-readable declaration of the main ranking signal on each method […], with kin = same signal; (b) behavioural kin — correlation of de-funded monthly returns (hardgate.trial_deposits / regime.defunded) on the dev window between the method's promoted variant and every test-failed method, kin above a threshold you choose by measurement; (c) both. The rule must catch M0060/M0062-shaped books, must not swallow unrelated ideas the way the full connected component did in D4 (26-method blob), and must say what it does for a method with no curve yet. Write it as a new lettered decision (D14+) in hardgate.py's docstring in its existing voice. Also handle the two queued idea rows: if their family should change, idea-status rows may be updated (methods_hypothesis_frozen and other triggers permitting — check), otherwise record why not. Update the explore skill […] only where it describes the kin check.
>
> Constraints (owner's, non-negotiable): no override of any kind; do not edit walkforward.buy_signal (D13: it follows kin through its caller hardgate.failed_kin — say whether that still holds); trials and test-failed are final and append-only; lab.sqlite committed only through lab stage; commit by pathspec, never git add -A (Sera sessions may commit to main). Run the engine as PYTHONPATH=<tree>/engine/src /home/miftah/seer/engine/.venv/bin/python; experiment only on scratch copies of lab.sqlite. lab status must keep printing Promotable now: (none) unless the measurement says otherwise.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Kin follows what a method is: measure (a)/(b)/(c), pick, catch M0060/M0062-shaped books, no blob, say what happens with no curve; no override; `buy_signal` untouched, say whether D13 holds | 1 |
| R2 | Write it as decision D14 in `hardgate.py`'s docstring, in its voice | 1 |
| R3 | Handle idea rows M0060/M0062 (re-file family if it should change, else record why not), through `lab stage`, pathspec commit | 1 |
| R4 | Update the explore skill only where it describes the kin check | 1 |

## Scope

**In scope:** `lab/hardgate.py` (behavioural kin + D14 + rule summary + refusal text), `tests/test_lab_hardgate.py`, `commands/lab.py` (`lab walkforward` catches a kin `LabError`; comment), kin wording in `lab/prereg.py` and `lab/runner.py`, the explore skill's kin paragraphs, the two idea rows + one insight on the main checkout's `lab/lab.sqlite`.

**Out of scope:** `walkforward.buy_signal` and its docstring and `BUY_CONDITIONS` (owner's); any override; schema changes; method files (frozen); `trials` and test-failed rows; the D11 fold rule; the web app.

## Invariants

1. No override path of any kind — no flag, env var, or parameter that skips behavioural kin.
2. `walkforward.py` is byte-identical.
3. `failed_kin` stays the one definition of kin; every reader keeps calling it.
4. `lab status` on the committed lab prints `Promotable now: (none)`.
5. Full engine suite green: `cd engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q`.
6. `lab/lab.sqlite` is only ever committed after `lab stage`, by pathspec, on the main checkout; experiments run on scratch copies.
7. No `git add -A` / `git add .` anywhere.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Behavioural kin (D14), skill text, idea re-file | R1, R2, R3, R4 | `engine/src/seer_engine/lab` | 6 + db | — | HARD | `.workflows/plan/hardgate-behavioural-kin/phase-1.md` | — | — |

### Phase 1 — Behavioural kin (D14), skill text, idea re-file
**Satisfies:** R1, R2, R3, R4 (one phase: the decision, its code, its tests, its skill text and the two rows it re-files are one argued change; splitting them would ship a skill describing a rule that does not exist yet)
**Owns:** everything in scope above.
**Does not touch:** `walkforward.py`, method files, schema, `trials`.
**Exit criteria:** suite green; `lab status` prints `Promotable now: (none)`; `failed_kin` on the committed lab matches the D14 table; D14 present; skill updated; M0060/M0062 handled and an insight records it; branch merged to main and pushed; db commit on main by pathspec.

## Reconciliation Log

single phase — nothing to reconcile

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| (a) declared signal vs (b) behaviour vs (c) both | **(b) alone.** (a) cannot live in method files: all 4 test-failed methods' files are frozen by `source_sha`, as are all 30 files on disk; it would need a second hand-kept registry for 76 rows, labelled by the same filer whose label slipped. Its one advantage, working before a curve exists, buys nothing at the gate: (F) refuses a method with no dev curve before (K) is read | 5: user's raw input ("follow what a method actually is, not what it is called") + measurement |
| Which correlation | residual: each series' monthly de-funded return regressed (OLS, intercept + slope) on `REF-SPY-HOLD`'s monthly return; Pearson on the common months | measurement: only metric with a gap (non-momentum max 0.8033, momentum min 0.8522); raw and active have none |
| Threshold | `KIN_CORRELATION = 0.85` | measurement: 0.047 above the highest unrelated book (H-P7A-F10, 0.8033); plain-momentum proxy H-P7A-F4 at 0.97 |
| Method side: promoted variant vs every dev variant | every dev variant | D12's reason (kin is about a method; every variant is a candidate in every fold's pick); measured: same dev-eligible refusals (10 of 10, both newly linked already refused by D11) |
| Failed side | each test-failed method's **tested** variant (its `window='test'` trial's candidate), dev curve | it is the variant that read test-failed |
| Failed method with no test trial / zero-variance series / < 36 common months | contributes nothing behaviourally (still kin by D4/D12 if linked) | surrounding convention: fixture test-failed rows have no test trial; constant fixture curves have no variance |
| Price-fingerprint mismatch on either side | `LabError` (fail closed, D10) | stated invariant of D10 |
| `lab walkforward` meets a kin `LabError` | catch in `commands/lab.py`, pass `"kin unknown (...)"` as `family_failed` so the signal cannot fire; `buy_signal` untouched | invariant 2 + D10's "reports warn and print the row" |
| Transitive behaviour (kin of kin) | no — one hop, against test-failed tested variants only | D4/D12's blob argument |
| M0060/M0062 family | re-file both to `p7a-f4` (the lab's family for plain 12-1 momentum: H-P7A-F4, M0010) **only if still `idea`**; parents unchanged; recorded by a `lab insight`. Changes no kin verdict today (p7a-f4 holds no test-failed method); D14 is what links them behaviourally once they run | skill rule "name the family by what it ranks on" (SKILL.md:90) + no trigger guards `family` |

## Open Questions

(none)

## Rollback

Revert the merge commit on main (code) and, separately, the pathspec db commit (re-file + insight row; insights are append-only, so a rollback of the row is a git revert of the db file, not a DELETE).

## Next

    /implement -f HARDGATE_BEHAVIOURAL_KIN_PLAN.md --phase 1

## Planner additions (decided in phase-1.md)

| Fork | Chosen | Rung |
|---|---|---|
| `runner.kin_note` meets a kin `LabError` | catch, return a note — a refusal at `lab test` would break D3 | 1: D3 invariant |
| `behavioural_kin` order | returns `()` before reading the benchmark when nothing is comparable, so existing fixture tests are unchanged | 6: surrounding convention |
| flat fixture curves | std floor `_FLAT = 1e-6` treats them as unmeasured, no NumPy warning | 6: surrounding convention |
| D14 numbers drift if Sera moves the lab | Step 13 re-measures and updates; stops if 0.85 no longer sits in a gap | 3: plan code blocks |
