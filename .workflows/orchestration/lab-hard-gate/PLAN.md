# Plan: the hard gate — `lab promote` refuses a method the folds and its kin have already judged

**Slug:** lab-hard-gate
**Date:** 2026-10-09
**Analysis:** `docs/analyzer/20261009-161956-K3QD_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/lab-hard-gate`
**Branch:** `feature/lab-hard-gate` (base: `origin/main` @ `7708350`)
**Phases:** 3
**Status:** reconciled
**Coordinator:** —

---

## Why

The user's request, verbatim:

> Phase 4 of docs/plans/WALK_FORWARD_EVALUATION_PLAN.md — the hard gate. Read the 'Phase 4 — the
> hard gate' section of that plan first; it is the brief and it carries the owner's decision, the
> four open questions you must answer rather than assume, and the context you will not guess. Make
> lab promote refuse a method unless it wins a majority of walk-forward folds
> (lab/walkforward.py Record.majority) and no other method in its family reads test-failed.

And the brief it names, `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md` § **Phase 4 — the hard gate**,
whose load-bearing sentences are the specification for what may and may not be built:

> **Decided 2026-10-09 by the owner**, after seeing what it costs. [...] **It blocks every
> promotion in the lab as of today.** [...] That is the intended effect, not a side effect. Five
> out-of-sample results, five failures; and the surviving ideas are all cousins of the methods that
> produced them. A lab that keeps promoting cousins of disproven families is not learning. **If
> this proves too strict in practice the answer is a recorded, argued change to the rule — not an
> override path, which is precisely the mechanism that produced the 0-for-5 roster in the first
> place.**

> **Why at promote and not at test.** `lab promote` is where the lab commits [...] Refusing at
> `lab test` would leave a method stranded in a state it can never leave. Refuse before the
> commitment, not after it.

> **What the pre-registration must record.** [...] Add the folds won and scored, whether the pick
> was stable across folds, and the family's state at promotion.

> - a method winning a majority with a clean family **promotes** (the existing promote tests must
>   still pass unchanged);
> - [...] the refusal happens **before** the pre-registration file is written and before any status
>   moves -- a refused promote must leave the repository and database byte-identical.

> **A funded curve must be de-funded before it is measured** (`regime.defunded`). Every trial from
> M0032 on is funded. Getting this wrong reads the owner's deposits as edge -- it did, by seventy
> to eighty points a year, until it was fixed (insight 72, 75).

> `backtest/walkforward.py` is a **different module** -- P3b's anchored walk-forward for Strategy
> A2 on the bracket engine. The lab one is `lab/walkforward.py`. **Do not edit the wrong file.**

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | `lab promote` refuses unless the method wins a majority of its walk-forward folds (`Record.majority`) **and** no other method in its family reads `test-failed`; the refusal lands before the pre-registration is written and before any status moves | 1 |
| R2 | Open question 1 — fail closed on thin evidence: decide the minimum scoreable folds and say why in the code | 1 |
| R3 | Open question 2 — is (K) evaluated at promote only? Decide whether `lab test` re-checks it, and say which was chosen | 1, 2 |
| R3a | *(R3's second half, assigned in reconciliation)* the printed `lab test` note that Decision D3 promises — one line, no new refusal, in `lab/runner.py:preflight_test` | 2 |
| R4 | Open question 3 — does (K) walk `parent_id` as well as `family`? | 1 |
| R5 | Open question 4 — is there any path back? Do not invent one; note whether it will be needed | 1 |
| R6 | The pre-registration records the folds won and scored, pick stability, and the family's state at promotion | 2 |
| R7 | `lab status` shows the fold record beside the dev-eligible list | 3 |
| R8 | `explore-and-experiment-new-method` Promotion step 0b says the gate **refuses**, not advises | 3 |
| R9 | `sera-the-explorer`'s promotion path and Never table say the same | 3 |

## Scope

**In scope**

- a new `engine/src/seer_engine/lab/hardgate.py` holding the rule, the kin walk, and the refusal
- `lab promote` calling it before `prereg.promote_method`
- `_trial_deposits` moving out of `commands/lab.py` into `hardgate` so the gate, `lab regime` and
  `lab walkforward` share one de-funding path
- two new `prereg` fields recording the fold record and family state at promotion
- `lab status`, the two skills, `package_readme.md`, `docs/lab/prereg/README.md`'s Format table,
  and marking phase 4 done in the walk-forward plan

**Out of scope, and why**

- **`engine/src/seer_engine/backtest/walkforward.py`** — P3b's anchored walk-forward for Strategy
  A2. The brief names it explicitly as the wrong file. Nothing in this plan touches it.
- **`engine/src/seer_engine/lab/walkforward.py` and `commands/lab.py:_walkforward`'s buy signal.**
  The buy signal's family check is narrower than the gate's kin walk, and stays that way
  (Decision D9). It is a separate, owner-decided rule about when to buy data; phase 3 states the
  asymmetry in prose and no phase changes the rule.
- **An override path.** The brief forbids one in the sentence that decides the rule. No `--force`,
  no environment variable, no "promote anyway". A rule that proves too strict is changed by a
  commit, argued, in git.
- **Loosening `lab test`.** `preflight_test` keeps the five refusals it has; this plan adds a
  printed note to it and no new refusal (Decision D3). **Phase 2 owns that note**, with
  `engine/src/seer_engine/lab/runner.py` and its two tests.
- **Rewriting the four committed pre-registrations.** `docs/lab/prereg/{M0002,M0021,M0022,M0029}.md`
  are records of what was claimed before a look and are never edited (Decision D5).
- **A re-evaluation path for a blocked family.** Open question 4 says do not invent one here
  (Decision D6).
- **Any contact with `lab/lab.sqlite`.** Every test builds its own temp database, the way
  `test_lab_prereg.py` already does. No `lab stage`, no snapshot regeneration, no `lab.json`.

## Invariants

Every phase must hold all of these, and each phase's exit criteria restate the ones it can break.

1. **The tree builds and the lab tests pass at the end of each phase.**
   `cd engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q tests/test_lab_*.py`
   (the worktree has no `.venv` of its own; `PYTHONPATH` is what makes pytest read the worktree's
   `src` rather than the main checkout's — without it the suite silently tests main).
2. **No existing test body is edited, in any file; fixture helpers may be extended; and every
   pre-existing test still passes.** This is the brief's "the existing promote tests must still
   pass unchanged", preserved exactly and not weakened: all **31** tests in
   `engine/tests/test_lab_prereg.py` pass, and not one of their bodies moves. What phase 1 *does*
   edit in that file is three **fixture helpers** — `_real_method`, plus new `_months`, `_curve`
   and `_benchmark` — so the fixture lab becomes a lab that could actually promote something,
   which is what the brief's own sentence "a method winning a majority with a clean family
   **promotes**" requires of a fixture. Measured after that patch: **31 passed**. The same rule
   holds for `engine/tests/test_lab_test_window.py` (17) and `engine/tests/test_lab_status.py`
   (12): additions only, no body edited.

   The counts, measured at `7708350` in this worktree, because the draft of this plan had them
   wrong: `test_lab_prereg.py` holds **31** tests, not 29. The baseline for
   `test_lab_prereg.py` + `test_lab_walkforward.py` + `test_lab_status.py` is **68 passed** —
   quote the count, never the seconds (8.99s for the analyst, 11.35s for phase 1, the same 68
   tests). The analysis file's Reference List still says "29 tests"; it is the stale number and
   this invariant is the correction.
3. **A refused `lab promote` leaves the repository and the database byte-identical.** No file
   written, no row updated, no insight added, no analysis appended.
4. **The gate opens no research store, runs no backtest and spends no look.** It is SQL plus
   arithmetic on `trials.curve_json`, and must stay under a second.
5. **Every curve is de-funded before it is measured.** Any new read of a trial curve goes through
   the same deposit reconstruction `lab regime` and `lab walkforward` already use.
6. **No override path is added**, in any phase, in any form.
7. **`engine/src/seer_engine/backtest/walkforward.py` is not modified.**
8. **`lab/lab.sqlite` is not modified.** Not by a test, not by a verification run. Verify against a
   copy in the scratchpad if a real-data check is wanted.
9. **The refusal is a `store.LabError`**, so `commands/lab.py:run` turns it into exit 2 with no new
   `except` clause anywhere.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | The rule, and the refusal at `lab promote` | R1, R2, R3, R4, R5 | `engine/lab`, `engine/commands` | 4 | — | HARD | `.workflows/plan/lab-hard-gate/phase-1.md` | — | — |
| 2 | The pre-registration records what it cleared, and `lab test` says what changed | R3, R3a, R6 | `engine/lab`, `engine/commands`, docs | 6 | 1 | NORMAL | `.workflows/plan/lab-hard-gate/phase-2.md` | — | — |
| 3 | Make the gate visible before it bites | R7, R8, R9 | `engine/commands`, skills, docs | 6 | 1, 2 | NORMAL | `.workflows/plan/lab-hard-gate/phase-3.md` | — | — |

**On the dependency edges, and on quoting the file.** Phases 2 and 3 are logically independent of
each other, and the DAG would run them concurrently. They are chained `1 -> 2 -> 3` on purpose:
all three edit `engine/src/seer_engine/commands/lab.py`, phases 1 and 2 both edit
`engine/tests/test_lab_prereg.py`, and Seer's swarm shares one worktree and one git index — so two
sessions editing those files at once is a conflict, not parallelism.

Because the chain is sequential, **each later phase quotes the files as the earlier ones leave
them**, and reconciliation rewrote the three places where a plan still quoted `origin/main`:

- Phase 2's two `_promote` prints anchor on the labelled print block **inside phase 1's replaced
  handler** (phase 1 rewrites `_promote` whole: the hard-gate docstring, the `hardgate` import,
  and `hardgate.check` before `prereg.promote_method`). The `gate` line is the anchor; the line
  numbers have moved.
- Phase 2's additions to `test_lab_prereg.py` **reuse phase 1's new `_months`, `_curve` and
  `_benchmark` helpers rather than redefining them** — a second `_curve` in that module would
  shadow phase 1's and silently change what the file's other tests build.
- Phase 3's `_promotable_now`, `_empty_reason`, `_promotion_path` and `_PROMOTION_STATUSES` edits
  sit alongside phase 1's `hardgate` import and phase 2's two print lines, all in the same file.
  Every line number in phase 3's plan is read at `7708350`; the anchors are the function names,
  which neither earlier phase renames.

The edit regions themselves are disjoint — phase 1 holds `_promote`, `_regime`, `_walkforward`,
`_trial_deposits` and the module help block; phase 2 holds two prints inside `_promote`'s block;
phase 3 holds the status-path functions — so a later reader could split them. This plan does not.

### Phase 1 — The rule, and the refusal at `lab promote`

**Satisfies:** R1, R2, R3, R4, R5
**Owns:**
- new `engine/src/seer_engine/lab/hardgate.py`: the fold record for one method, the kin walk, the
  two conditions, the refusal, and a one-line summary string other callers print
- `_trial_deposits` moves from `commands/lab.py` into `hardgate` (public name), with `_regime` and
  `_walkforward` updated to call it there — one de-funding path, not three
- `commands/lab.py:_promote` calls the gate **before** `prereg.promote_method`
- the `lab promote` line in the module help block says it refuses
- new `engine/tests/test_lab_hardgate.py`

**Does not touch:** `lab/prereg.py` (phase 2), `lab/walkforward.py` (it is already correct and
tested — this phase *reads* `Record.majority`, it does not change it), `lab/runner.py` (phase 2
owns the `lab test` note), `commands/lab.py:_walkforward`'s inline kin query and `wf.BUY_CONDITIONS`
(Decision D9), `lab status` (phase 3), the skills, `package_readme.md`,
`docs/lab/prereg/README.md` (phase 2), and any existing **test body**.

**Exit criteria:**
- `lab promote` on a method that loses the folds exits 2, names the record (`"2 of 4 folds"`), and
  leaves `docs/lab/prereg/` and the database untouched
- `lab promote` on a method whose kin reads `test-failed` exits 2 and names the member by id
- `lab promote` on a method with fewer than `MIN_FOLDS` scoreable folds exits 2 and says so
- `lab promote` on a method with a majority and clean kin behaves exactly as before
- all **31** tests in `test_lab_prereg.py` pass with every **test body** byte-identical — the only
  edits in that file are the three fixture helpers; `test_lab_walkforward.py` and
  `test_lab_status.py` pass unchanged
- `grep -n "_trial_deposits" engine/src/seer_engine/commands/lab.py` returns nothing
- the four open questions are answered in `hardgate.py`'s own prose, each with its reason

### Phase 2 — The pre-registration records what it cleared, and `lab test` says what changed

**Satisfies:** R3, R3a, R6
**Owns:**
- `lab/prereg.py`: two new `FIELDS` — `folds` and `family_state` — written by `render`, tolerated as
  absent by `parse` for files that predate the gate (Decision D5), and populated by
  `promote_method` from `hardgate`
- `render`'s prose states what the fold record means and that it is the bar *this* method cleared
- `commands/lab.py:_promote` prints the two new lines, appended to the block **phase 1 leaves
  behind**
- `lab/runner.py`: `kin_note`, and one `print` in `preflight_test` before it returns — **Decision
  D3's promised line**, assigned here in reconciliation. No new refusal, no exit code change, no
  transition change; `preflight_test`'s five existing refusals are untouched
- `docs/lab/prereg/README.md`: two rows in the Format table, for `folds` and `family_state`, so the
  directory's documentation and the parser do not disagree
- additions to `engine/tests/test_lab_prereg.py` (eleven, reusing phase 1's `_months` / `_curve` /
  `_benchmark`), including one test that the four committed pre-registrations still parse, and two
  additions to `engine/tests/test_lab_test_window.py` for the note

**Does not touch:** `hardgate.py`'s rule (it reads it), `lab/walkforward.py`, `lab status`, the
skills, `package_readme.md`, `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md`, any existing **test
body** in `test_lab_prereg.py` or `test_lab_test_window.py`, phase 1's three fixture helpers (it
reuses them), and the four committed `docs/lab/prereg/{M0002,M0021,M0022,M0029}.md` files.

**Exit criteria:**
- a promotion that passes writes a pre-registration carrying `folds:` and `family_state:`
- `parse(render(p, name)) == p` still holds exactly, including the new fields
- `prereg.parse` reads all four committed files and reports the new fields as not recorded
- `promote_method` still refuses to rewrite an existing file, and a re-run still does not move the
  date line
- `lab test` on a promoted method whose kin has since failed prints one line naming **every**
  failed relative, and still runs: same exit code, same transition, no new refusal; with clean kin
  it prints nothing extra
- `docs/lab/prereg/README.md`'s Format table lists all seventeen keys, with no DSR threshold and no
  percentage typed as a literal (`test_lab_gate_wording.py` scans it)
- `test_lab_prereg.py` reads 42 and `test_lab_test_window.py` reads 19, with every pre-existing
  test body unmodified

### Phase 3 — Make the gate visible before it bites

**Satisfies:** R7, R8, R9
**Owns:**
- `commands/lab.py:_promotable_now`: each listed method carries its fold record and kin state, so
  "why can nothing be promoted" is answerable from `lab status` alone
- `.claude/skills/explore-and-experiment-new-method/SKILL.md` step 0b: the gate **refuses**
- `.claude/skills/sera-the-explorer/SKILL.md`: promotion path and Never table
- `engine/package_readme.md`: the lab package map (including `lab/walkforward.py`, missing from it
  entirely) and the new `hardgate` API block
- `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md`: phase 4 marked done, and its stale cost paragraph
  corrected against this plan's measurement
- `engine/tests/test_lab_status.py` additions

**Does not touch:** the rule itself, `prereg.py`, `lab/runner.py` and `docs/lab/prereg/README.md`
(phase 2), `lab/walkforward.py` and `commands/lab.py:_walkforward` (Decision D9 — it states the
asymmetry in prose and changes neither), `backtest/walkforward.py`, and any existing test body.

**Exit criteria:**
- `lab status` prints each dev-eligible method's fold record and, when blocked, the failed kin, and
  lists no method under "Promotable now" that `lab promote` would refuse
- the empty `Promoted` section blames the gate rather than an unrun command
- `lab status` exits 0 on a lab with no `REF-SPY-HOLD` dev trial and empty curves
- the explore skill and the Sera skill both say the gate refuses, neither tells a child to expect
  an override, both count the buy signal's conditions at four, and the explore skill states the
  buy-signal / hard-gate asymmetry (Decision D9)
- `package_readme.md` describes `hardgate`, `lab/walkforward.py` and the two new pre-registration
  fields, checked against the modules as phases 1 and 2 actually built them
- the walk-forward plan's phase 4 reads done, with the measured seven-method table, not the stale
  four-method list

## Reconciliation Log

One row per conflict found across the three plans, with how it was resolved. The three planners ran
concurrently and could not see each other's work; everything below was resolved by editing the plan
files, not by reporting it.

| # | Conflict | Kind | Phases | Resolution |
|---|---|---|---|---|
| 1 | **D1 was wrong.** It claimed the gate could live in `commands/lab.py:_promote` with every existing promote test passing untouched. `test_lab_promote_command_writes_the_file_and_names_the_next_step` (`tests/test_lab_prereg.py:490`) drives the CLI `_promote` — exactly where the gate lands — on a fixture lab with `curve_json="[]"` and no `REF-SPY-HOLD`, so it gets exit 2 and asserts 0 | Contract drift | 1 | **D1 rewritten in place** (below), stating the location *and* the consequence, and keeping the reason the gate still cannot live inside `prereg.promote_method`. Phase 1 resolves it by editing three *fixture helpers* and no test body; re-measured **31 passed** |
| 2 | `test_lab_prereg.py` holds **31** tests, not the 29 the draft index and the analysis's Reference List both state | Stale measurement | all | Corrected in Invariant 2, in phase 1's "READ THIS FIRST" table, and in phase 2's Impact and exit criteria. The analysis file is left as written and is the stale copy |
| 3 | The baseline was quoted with two different wall times (8.99s by the analyst, 11.35s by phase 1) for the same run | Stale measurement | 1, 2, 3 | Every quote now reads **68 passed** and says explicitly: quote the count, never the seconds |
| 4 | Invariant 2 said the 29 tests "stay byte-identical", which phase 1 legitimately breaks by editing three fixture helpers in that file | Contract drift | 1, 2 | Invariant 2 restated: no existing **test body** is edited in any file; fixture helpers may be extended; every pre-existing test still passes. The brief's "the existing promote tests must still pass unchanged" is preserved exactly, not weakened |
| 5 | **The `lab test` printed note (D3) was owned by nobody.** Phase 1's scope forbids it `runner.py` and hands it to phase 2; phase 3 hands it to phase 1; the index assigned it to neither | Gap | 1, 2, 3 | **Assigned to phase 2**, which already carries R3 and the "a pre-registration is a promise" prose. `engine/src/seer_engine/lab/runner.py` added to its owned files, with `kin_note` + one `print` in `preflight_test` and two tests in `test_lab_test_window.py`. No exit code, no transition, no new refusal. Phases 1 and 3 updated to point at phase 2 |
| 6 | **`docs/lab/prereg/README.md` was owned by nobody.** Its Format table lists every front-matter key and goes stale the moment phase 2 adds `folds` and `family_state`; phase 2 drafted the rows and recommended phase 3, which does not own it | Gap | 2, 3 | **Assigned to phase 2** (Step 8), where the fields are written, so table and `FIELDS` move in one commit. Phase 3's "Leaves alone" updated |
| 7 | Phase 2 flagged a risk that `failed_kin` might return `str \| None` like `commands/lab.py:1872` does today, losing one of M0030's two failed kin | Unmet assumption (unfounded) | 1, 2 | **Verified: both plans agree on `failed_kin(conn, method_id) -> tuple[str, ...]`.** Every message naming kin `", ".join(...)`s all of them — `hardgate.family_state`, `hardgate.check`, `prereg.family_text`, `runner.kin_note`. Phase 2's risk note deleted, along with its dangling "see Risks" pointer to a section that did not exist |
| 8 | Phase 3's `_promotable_now` printed `f"{head}  {record}, kin clean"`, where `record` is `hardgate.summary` — which **already ends in `; kin clean`**. The line would have read `4 of 4 folds; kin clean, kin clean` | Contract drift | 1, 3 | Phase 3 now prints `record` whole and appends nothing; its Requires block states `summary`'s exact shape, `"<fold record>; kin <state>"`. Its test still asserts both substrings, and both appear once |
| 9 | Phase 3 asked whether phase 1's `check` exempts `promoted` (its Requires item 6), and whether `summary`/`check` can raise a bare `ValueError` (item 4), offering to widen its `except` to `Exception` | Unmet assumption | 1, 3 | **Both settled from phase 1's module code.** `check` is silent for every status but `dev-eligible` (pinned by `test_the_gate_is_silent_for_every_status_but_dev_eligible`), so the `(already pre-registered)` line is exactly true. `_dev_curves` filters empty curves before `evaluate` can `min()` them, and `summary` is lenient — so **only** `store.LabError` escapes and the narrow catch stands. The `except Exception` fallback is not taken |
| 10 | Phase 3 did not cut the fold geometry once, though phase 1's handoff asks for it: `_hard_gate_states` called `hardgate.summary(conn, mid)` per method, re-cutting the benchmark's folds seven times | Contract drift | 1, 3 | `_hard_gate_states` now calls `hardgate.geometry(conn)` once inside a `try`, passes `geo` to every `summary`, and leaves `geo = None` on a lab with no benchmark — the shape phase 1 specified |
| 11 | **Three phases edit `commands/lab.py`; phases 1 and 2 both edit `test_lab_prereg.py`.** Phase 2 quoted `_promote`'s print block and `test_lab_prereg.py`'s append point at `origin/main`, before phase 1 rewrites the handler and inserts three helpers; phase 3's line numbers are all pre-phase-1 | File collision | 1, 2, 3 | Phase 2 now anchors on the post-phase-1 `_promote` (the `gate` line, not a line number) and **reuses `_months` / `_curve` / `_benchmark` rather than redefining them**. Phase 3 carries a stated rule: every line number is read at `7708350`, anchor on the function names. The index's dependency-edges section records all three |
| 12 | Phase 2 said "ten tests" and "29 tests to 39"; the appended block holds **eleven** test functions | Stale measurement | 2 | Corrected to eleven, and to `31 -> 42` |
| 13 | `lab walkforward`'s inline kin query and `wf.BUY_CONDITIONS` are family-only, while the promote gate walks family ∪ ancestors (D4), so `lab walkforward` reports M0030's family clean while `lab promote` refuses it on ancestry | Behavioural fork | 1, 3 | **Deliberately left** — recorded as new **Decision D9**. The buy signal is a separate, owner-decided rule about when to buy data and changing it is beyond this brief. Phase 3 states the asymmetry in the explore skill's step 0b, and is explicitly forbidden from editing `lab/walkforward.py` or `_walkforward` to do it |
| 14 | `walkforward.buy_signal`'s success string says "cleared all three" for four conditions (`lab/walkforward.py:296`) | Gap (out of scope) | 3 | Same do-not-edit file. Recorded as a **follow-up under D9**, not a change. Phase 3 fixes the count in the two skills only |
| 15 | Phase 3's "Leaves alone" still named `_trial_deposits (:1656)`, which phase 1 deletes | Deleted-then-used | 1, 3 | Phase 3's list updated to say so and to forbid reintroducing a reference to it |
| 16 | Phase 2's Satisfies, Files and Owns did not reflect the two items moved into it | Requirement follows the work | 2 | R3's second half broken out as **R3a** in the Requirements table and mapped to phase 2; phase 2's Satisfies line, Files table (3 → 6), Owns and exit criteria all updated to match. No phase's `Satisfies` was widened to legalise creep |

**Requirement ids after every move:** R1 → 1; R2 → 1; R3 → 1, 2; R3a → 2; R4 → 1; R5 → 1; R6 → 2;
R7 → 3; R8 → 3; R9 → 3. Every id is owned; nothing was dropped.

**Invariants re-verified across the edited set.** No override path appears in any phase, in any
form — phase 1 pins it with `test_there_is_no_override`, phase 2 adds a note and no refusal, phase 3
tells both skills there is none. `engine/src/seer_engine/backtest/walkforward.py` appears in all
three plans only on a do-not-touch list. No phase writes to `lab/lab.sqlite`: every test builds its
own temp database, and both manual checks run against a scratchpad copy. Dependencies point
backward only (`1 -> 2 -> 3`), no symbol is deleted before its last use (`_trial_deposits` is
deleted and re-called in phase 1's own commit), and each phase builds green on its own.

**Round 2 — the verification pass.** Round 1 reported `contract_changed: true`, so the set was read
again against phase 1's final contract and against the real modules in this worktree. Three
findings, all edited in place; nothing that round 1 settled was re-opened.

| # | Conflict | Kind | Phases | Resolution |
|---|---|---|---|---|
| 17 | Phase 1's Interface Contract labelled `fold_summary` and `family_state` "phase 2's", and its Handoff told phase 2 to **call** them — but phase 2 calls `fold_record`, `failed_kin` and `MIN_FOLDS` and composes its own line, because `Record.summary()` says ", pick changed" only when the pick moved and R6 asks the file to name stability as a word rather than by absence | Contract drift | 1, 2 | Phase 1's two contract labels, its Signatures table and its Phase-2 handoff bullet now state phase 2's actual call surface and the reason for it; `fold_summary` / `family_state` are re-described as the module's own display helpers (`summary` is built from them, `test_lab_hardgate.py` pins them). **No symbol moved**: phase 1 still creates all of them with the same signatures, so this is not a contract change |
| 18 | Phase 2's `test_lab_test_prints_a_note_when_the_kin_failed_after_the_promise` docstring claimed "a sibling in the same family **and an ancestor** both read `test-failed`", while its fixture adds one method and its assertion reads the singular `"has read test-failed since"` — adding the second kin `kin_note` would say `have`, and the test would fail | Contract drift (asserted string) | 2 | Docstring rewritten to the one sibling the fixture builds, with the verb trap stated; the "names **every** failed relative" claim re-pointed at the tests that actually cover the `", ".join` (phase 1's M0030 case, and `prereg.family_text`'s own test) |
| 19 | Phase 3's Creates list and Files table said "three fixture helpers" where Step 5 defines four (`_lab_with_a_benchmark` was uncounted), and exit criterion 4 asked for "the first 317 lines byte-identical" of a file that is 317 lines long and into which it inserts at `:302` | Stale measurement | 3 | Corrected to four helpers in all three places, with a note that none shadows the module's existing `_trial` / `_method`; exit criterion 4 restated as *every one of the 317 existing lines byte-identical, the only additions being two import lines and the block inserted between the old `:301` and the old `:304`* |

**Verified in round 2 and deliberately not changed.** `hardgate.check` takes no `geo`, so
`_hard_gate_states` cuts the geometry once for the seven `summary` calls and each `check` then cuts
it again — a cost, not an inconsistency, and well inside invariant 4's one second for SQL and
arithmetic on seven recorded curves. Widening `check`'s signature would move phase 1's contract in
round 2 and force a third round for no behavioural gain, so it stands as phase 1 specified it.

**Everything else checked in round 2 held.** Every name phases 2 and 3 require is created by phase
1 with a matching signature, and `geo=None` is present on every function phase 3 passes `geo` to
(`summary`; `check` is called without it). Every asserted literal was quote-matched against the
code block that emits it, against the real `walkforward.Record.summary()` (`"N of M folds"`,
`", pick changed"` only when unstable) and the real `Slice` / `FoldPick` / `Fold` field orders, the
real `prereg.PreregError` message (`"the pre-registration is missing …"`) and the real
`promote_method(..., check_method_file=…)` signature — no second double-render was found. The two
reassigned items are complete in phase 2, not merely mentioned: `lab/runner.py` is in its Files
table with `kin_note`, the one `print` before `preflight_test`'s `return pre` (which prints nothing
today, so phase 2's "prints nothing extra" assertion holds) and two tests, and
`docs/lab/prereg/README.md`'s two rows are written out; phase 3 claims neither. `test_lab_prereg.py`
is sequenced correctly — phase 2 reuses `_months` / `_curve` / `_benchmark` and no phase redefines a
helper an earlier phase added (phase 3's four helpers are new names in a different module). Phase 1
is one commit, which is what keeps steps 2-6 from leaving the tree red between step 3's deletion and
step 5's last call site. And the invariants hold: no override path, `backtest/walkforward.py` on
every do-not-touch list, both manual checks against a scratchpad copy (phase 3's `SEER_LAB_DB`
override is real — `store.DB_PATH` reads it), the refusal always a `store.LabError`, every curve
de-funded through the one `trial_deposits`, and R1-R9 plus R3a each owned.

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Where the gate lives: inside `prereg.promote_method`, or in `commands/lab.py:_promote` before it | **`lab/hardgate.py`, called from `_promote` before `promote_method`** — and the fixture lab in `test_lab_prereg.py` is made promotable, by editing three fixture helpers and no test body (D1, corrected) | 5: the brief's own test list — "a method winning a majority with a clean family **promotes** (the existing promote tests must still pass unchanged)" |
| Open question 1 — the minimum scoreable folds | **every fold the geometry yields, and at least 4** | 5: the brief ("fail closed on thin evidence... decide the minimum and say why") + measurement |
| Open question 2 — does `lab test` re-check (K)? | **No. The pre-registration is honoured as written; `lab test` prints a note when the family has since failed, and refuses nothing new** | 5: the brief ("the design's instinct is that a pre-registration is a promise and is not re-opened") |
| Open question 3 — does (K) walk `parent_id`? | **Yes: `family` ∪ transitive ancestors. Not the full connected component** | 5: the brief ("a method whose *parent* failed is as disproven as one whose sibling did") + measurement |
| Open question 4 — is there a path back? | **None is built. The need is recorded, in code and in the walk-forward plan** | 5: the brief ("Do not invent one in this phase; note whether it will be needed") |
| Two new `prereg` fields: required, or tolerated-absent on read? | **Tolerated absent, with a stated legacy value; the four committed files are never edited** | 1: invariant 3 and `prereg.py`'s own "written once and never rewritten" |
| The benchmark is missing from the database | **Refuse (fail closed), naming `REF-SPY-HOLD`** | 5: the brief ("must be **refused**, never waved through") |
| Phases 2 and 3 run concurrently (no shared edge) or sequentially | **Sequentially: `1 -> 2 -> 3`** | 6: surrounding convention — Seer's swarm shares one worktree and index, and all three edit `commands/lab.py`; phases 1 and 2 also share `test_lab_prereg.py` |
| Who owns Decision D3's printed `lab test` note — phase 1 (which owns the gate), phase 2 (which owns the promise's record), or nobody | **Phase 2**, with `lab/runner.py` and two tests | 2: the phases' own exit criteria — phase 1's scope forbids it `runner.py` and phase 3 claims none of `lab test`; phase 2 already carries R3 |
| Who owns `docs/lab/prereg/README.md`'s Format table — phase 2 (which adds the keys) or phase 3 (which owns the other docs) | **Phase 2**, so the table and `FIELDS` move in one commit | 3: the plans' own code blocks — phase 2 had already drafted the two rows |
| `lab walkforward`'s family-only buy signal vs. the gate's family ∪ ancestors kin walk | **Left asymmetric; stated in prose, changed nowhere** (D9) | 4: the index's Why and Requirements table — no `R` asks for the buy signal to move, and the brief scopes this phase to `lab promote` |
| Phase 3's `_promotable_now` line: append `", kin clean"`, or print `hardgate.summary` whole | **Print it whole** — `summary` already ends in the kin state | 3: the plans' own code blocks — phase 1's `summary` returns `f"{folds}; kin {kin}"` |

**D1 — the gate lives in `lab/hardgate.py`, called from `commands/lab.py:_promote`; and the promote
fixture becomes a lab that could actually promote.** *(Corrected in reconciliation. The draft of
this decision claimed every existing promote test would pass untouched. That half was wrong, and
the correction is the second paragraph — it is here rather than dropped, because a phase session
that reads only the first half will write the wrong commit.)*

**Where it lives, and why not in `prereg.promote_method`.** The brief's test list requires that
"the existing promote tests must still pass unchanged". `test_lab_prereg.py`'s fixtures insert dev
trials with `curve_json="[]"` (`tests/test_lab_prereg.py:82`) and never insert a `REF-SPY-HOLD`
row. `prereg.promote_method` is the one function every one of those tests calls, so a gate inside
it would refuse a *fixture database* rather than a method — in fact `walkforward.evaluate` raises
`ValueError` on `min()` of an empty curve before it even reaches the missing benchmark. So the gate
cannot live there, and the brief settles it. `prereg.promote_method` has exactly **one** production
caller, `commands/lab.py:1161`, so a check in `_promote` before that call is not a hole in
practice; `hardgate.py`'s docstring says so, and says that a second caller must call the gate too.
Putting the rule in its own module rather than inline in the handler keeps it unit-testable without
an argparse namespace, which is how `lab/prereg.py`, `lab/npolicy.py` and `lab/walkforward.py` are
already shaped.

**The consequence the draft missed: one existing test drives `_promote` too, and it is phase 1's to
resolve.** `test_lab_promote_command_writes_the_file_and_names_the_next_step`
(`tests/test_lab_prereg.py:490`) calls the CLI — `lab_cmd.run(argparse.Namespace(..., "promote",
...))`, asserting `== 0` — and `run` dispatches to `_promote`, which is exactly where the gate
lands. Its lab comes from `_real_method` (`:135`), which inserts `curve_json="[]"` and no
benchmark. **Measured** against a prototype of `hardgate.fold_record` on a database shaped like
`_real_method`'s: `store.LabError: no REF-SPY-HOLD dev trial` → `commands/lab.py:367` → `return 2`,
against an assertion of 0. **It fails.**

Phase 1 resolves it without an override, without weakening D7, and **without editing a test body**:
it edits three *fixture helpers* — `_real_method`, plus new module-level `_months`, `_curve` and
`_benchmark` — so the fixture lab carries a `REF-SPY-HOLD` benchmark and a real twenty-year curve,
and the method wins all four folds. That is what the brief's own sentence asks a fixture to be able
to represent: "a method winning a majority with a clean family **promotes**". A fixture that cannot
represent a promotable lab is a fixture that is behind the gate — the same move `_ballast` already
made one gate earlier, for the same reason. **Measured** on a scratchpad copy with exactly that
patch: **31 passed**, unchanged from baseline, with no DSR, N-policy or eligibility side effect,
and the gate then reports `4 of 4 folds, majority True` on that same lab. Phase 1's Steps 2 and 6
must therefore land in **one commit**: between them the tree is red.

**D2 — the minimum is every fold the geometry yields, and at least 4.**
Measured on the committed lab: the fold geometry is cut from the **benchmark** curve
(`REF-SPY-HOLD`, 1993-02-01..2015-10-16), so it is global and yields **4 folds**. Every `M*` method
in the lab has a dev curve spanning 1996-01-03..2015-10-16 and is scoreable on all four, so this
minimum costs a real method nothing. `H-P7A-F10`, whose curve starts 2007-04-10, scores only 2 —
proof the thin case exists.

Why not "3 or more". Under a coin-flip null (a bound, not a p-value — the brief forbids treating
overlapping folds as independent):

| scoreable folds | P(strict majority \| coin flip) |
|---|---|
| 1 | 0.5000 |
| 2 | 0.2500 |
| **3** | **0.5000** |
| **4** | **0.3125** |
| 5 | 0.5000 |

A strict majority of an **odd** count is a coin flip at every odd count. A "minimum of 3" would
therefore admit evidence strictly weaker than 4 and no stronger than 1. The rule is stated as the
conjunction *"scoreable on every fold, and at least `MIN_FOLDS = 4`"*: the first clause refuses a
method whose curve does not cover the window, the second is a tripwire that fires if
`MIN_TRAIN_YEARS`, `EVAL_YEARS` or the dev window ever changes the geometry — so a changed setting
cannot silently lower the bar. Both numbers and this table go in `hardgate.py`'s prose.

**D3 — (K) is checked at promote only; `lab test` honours the pre-registration.**
The brief states the design's instinct and asks for a choice. Chosen: the pre-registration is a
promise. Three reasons, in the order they matter: `promoted` has only two exits and both are final,
so a refusal at `lab test` strands a method forever — the exact failure the brief's "Why at promote
and not at test" rejects; a pre-registration whose meaning depends on events after it was written
is not a pre-registration; and the family state **is** recorded in the file by phase 2, so a reader
can see the promise's basis without the code re-deriving it.

What is added instead is **one printed line**, not a refusal: when `lab test` runs on a method whose
kin has failed since promotion, it says so above the look. That is information the owner should
have before spending the one look, and it changes no exit code and no transition. It is a sentence,
not a gate — the same shape as `_ratchet_warning`.

**D4 — (K) is `family` ∪ transitive ancestors via `parent_id`.**
The brief asks the question and gives the reason for yes: "M0032 is M0007's realistic twin by
`parent_id`, not by family string. A method whose *parent* failed is as disproven as one whose
sibling did." Measured on the committed lab (63 methods, 4 `test-failed`):

| rule | blocks | note |
|---|---|---|
| `family` only | 26 of 63 | the literal rule; **misses M0030**, whose family is clean but whose parent M0029 and grandparent M0021 both read `test-failed` |
| ancestors only | 10 of 63 | misses M0007, M0019, M0020, M0033, all caught by family |
| **`family` ∪ ancestors** | **29 of 63** | catches all seven dev-eligible methods |
| full connected component | 36 of 63 | one **26-method blob**; would refuse M0019 on account of M0021, a multi-factor blend four hops away in an unrelated family |

The component rule is rejected on that last line: "cousin of a disproven family" stretched to four
hops through unrelated families stops being a statement about the evidence. Descendants are left to
the `family` string, which by construction holds a variation twin (`lab idea --source-kind
variation --parent …` keeps the family), and the measurement shows family already catches every
failed-descendant case in the lab today.

**D5 — the two new pre-registration fields are tolerated-absent on read.**
`docs/lab/prereg/` holds four committed files — M0002, M0021, M0022, M0029 — written before this
gate existed, and `prereg.parse` refuses a file missing any key in `FIELDS`. Making `folds` and
`family_state` required would invalidate four records whose entire value is that they were
committed before a number existed, and `prereg.py`'s central rule forbids migrating them ("a
pre-registration is written once and never rewritten"). So `parse` keeps its strictness for the
original fifteen fields and fills these two with a stated legacy value when absent. `render` always
writes them, so `parse(render(p, name)) == p` still holds exactly for every file written from here
on, and for a legacy file read back.

**D6 — no path back is built, and the need is recorded.**
The brief: "Do not invent one in this phase; note whether it will be needed." It will. `reevaluate`
exists for `rejected -> dev-eligible` when the bars move; nothing equivalent exists for a method
whose kin is blocked. Two shapes will eventually be wanted and neither is built here: a family whose
failure is later attributed to something other than the idea (a cost model, a fill assumption), and
a method whose `parent_id` links it to a failure it does not inherit. Both are *arguments*, and the
brief's own sentence says an argued change to the rule is the mechanism — a commit, not a flag.
`hardgate.py` records this where the next reader will find it, and phase 3 records it in the
walk-forward plan.

**D7 — a missing benchmark refuses.**
If no `REF-SPY-HOLD` dev trial is in the database, no fold can be scored. The brief's open question
1 says a method with no scoreable folds "must be **refused**, never waved through", and the same
answer applies when the benchmark rather than the method is missing. The message names
`REF-SPY-HOLD` so the reader knows it is the lab's fixture that is wrong, not their method.

**D8 — the brief's cost paragraph is stale; the conclusion is not.**
The brief says "Every dev-eligible method -- M0007, M0019, M0020, M0033 -- is in a family that has
already failed the test window, so every one fails (K)." Measured today, the lab has **seven**
dev-eligible methods, and two of them — M0024 (`stock-seasonality`) and M0030
(`stock-core-satellite`) — pass (K) on family alone:

| method | folds won | (F) | (K) family | (K) family ∪ ancestors |
|---|---|---|---|---|
| M0007 | 3 of 4 | pass | fail (M0022) | fail (M0022) |
| M0011 | 2 of 4 | **fail** | fail (M0022) | fail (M0022) |
| M0019 | 3 of 4 | pass | fail (M0002) | fail (M0002) |
| M0020 | 3 of 4 | pass | fail (M0002) | fail (M0002) |
| M0024 | 2 of 4 | **fail** | pass | pass |
| M0030 | 2 of 4 | **fail** | **pass** | **fail (M0021, M0029)** |
| M0033 | 3 of 4 | pass | fail (M0022) | fail (M0022) |

The conjunction still refuses all seven, so "it blocks every promotion in the lab as of today"
holds — but only the conjunction gets there, and M0030 is the live case that decides D4. Phase 3
corrects the paragraph in the walk-forward plan rather than leaving a measurement that was true for
four hours. Methods clean under D4's rule do exist — M0034 and M0035 both win 3 of 4 and their
parent M0032 reads `rejected`, not `test-failed` — so the gate is not a permanent stop.

**D9 — `lab walkforward`'s buy signal stays family-only, and the asymmetry is stated rather than
removed.** *(Added in reconciliation.)*
`commands/lab.py:1863-1866` queries kin as `family = ? AND status = 'test-failed' ... LIMIT 1` — one
family, one row — and `walkforward.BUY_CONDITIONS` says the same. The promote gate walks `family` ∪
transitive ancestors (D4). So **`lab walkforward` will report M0030's family as clean while `lab
promote` refuses it on ancestry**, and the `LIMIT 1` cannot name both M0021 and M0029 even where it
does fire.

That is a real, user-visible inconsistency and it is **deliberately left**. The buy signal is a
separate rule, decided by the owner, about when survivorship-free price history is worth buying —
not about when a method may be promoted. Widening it would change what `lab walkforward` prints and
what the two skills tell a child to report, which no requirement in this plan set asks for, and
`lab/walkforward.py` is on this plan's do-not-edit list. The rungs that settle it: the index's own
Requirements table, which has no `R` for the buy signal, and the brief, which scopes this work to
`lab promote`.

What is done instead: **phase 3 states the asymmetry where a reader meets it** — the explore
skill's Promotion step 0b, in prose, naming M0030 as the live case. Phase 3 must not edit
`lab/walkforward.py` or `_walkforward` to do it.

**Follow-up, recorded and not done:** `walkforward.buy_signal`'s success string says "cleared all
three" while `BUY_CONDITIONS` above it lists four (`lab/walkforward.py:296`). Same do-not-edit
file, so phase 3 fixes the count in the two skills and leaves the module to whoever next opens it.
A one-word fix and one test assertion, for a separate commit.

## Open Questions

**None.** Every fork in this plan set is reversible and every one is settled above, with the rung
that decided it, in **Decisions**. The brief's four open questions were questions *for the
implementer* and all four are answered — D2 (minimum folds), D3 (`lab test` re-check), D4
(ancestry), D6 (path back) — and reconciliation settled five more, recorded as the last five rows
of the Decisions table and as D9. Every requirement id R1-R9 (and R3a) is owned by at least one
phase, so nothing lands here as an unowned requirement either. The set is ready to launch
unattended.

## Rollback

**Per phase.** Each phase is one commit on `feature/lab-hard-gate`; `git revert` it.

- **Phase 1** — reverting restores `lab promote`'s pre-gate behaviour exactly. `_trial_deposits`
  moves back into `commands/lab.py`; nothing persisted depends on the gate.
- **Phase 2** — reverting removes the two `prereg` fields, the `lab test` kin note (leaving
  `preflight_test`'s five refusals exactly as phase 1 left them) and the two README rows. Any
  pre-registration written while it was live keeps its two extra lines; after the revert `parse`
  refuses them as unknown keys. **If phase 2 is reverted after a real promotion, deleting that
  promotion's file is not an option** (it is a committed record), so revert phase 2 only before any
  method is promoted under it. Nothing in the lab is promotable today (D8), so this window is
  currently unbounded. The note and the README rows are inert on their own and can be hand-reverted
  without the fields.
- **Phase 3** — documentation and one `lab status` block; reverting is free.

**As a whole.** `git branch -D feature/lab-hard-gate` and remove the worktree. Nothing in this plan
writes to `lab/lab.sqlite`, `web/data/lab.json`, Neon, Vercel or the research store, so there is no
state outside git to undo.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/LAB_HARD_GATE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/LAB_HARD_GATE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/LAB_HARD_GATE_PLAN.md
