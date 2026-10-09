# Plan: Hard gate — the promoted variant's own folds (D11) and blend ingredients as kin (D12)

**Slug:** hardgate-variant-and-blend-kin
**Date:** 2026-10-09 21:25
**Analysis:** `20261009-212555-K7HG_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/hardgate-variant-and-blend-kin`
**Branch:** `feature/hardgate-variant-and-blend-kin` (base: `HEAD` @ `9560a6b`)
**Phases:** 1
**Status:** complete
**Coordinator:** —

---

## Why

Verbatim from the owner:

> Close two holes in the hard gate that Sera found in batch sera-20261009-2105 (read lab insights 82 and 84 in full, read-only: sqlite3 'file:lab/lab.sqlite?mode=ro'):
> 1. Insight 82 — the fold check (F) scores whichever variant the training slice picked in each fold (walkforward.pick), not the variant that would actually be promoted. M0044's hardest-brake variant would be promoted on a 3-of-4 record that came from its lighter siblings; the promoted variant itself beat SPY in only 1 of 4 folds and trailed by 7 points a year in 2009-2015. Make the gate also require the exact variant being promoted to win a strict majority of the folds (scored on its own de-funded curve against the same benchmark). Measure how many dev-eligible methods each version of the rule blocks, as LAB_HARD_GATE_PLAN.md did for D4.
> 2. Insight 84 — the kin check (K) follows family strings and parent_id only, so a blend that uses an already test-failed method as an ingredient (M0028-style half-and-half of a bounce book and a momentum book whose family failed) is not recognised as kin. Teach the kin rule to look inside blends: find how a blend method records its ingredients (method files under engine/src/seer_engine/lab/methods/, allocator composition, or method metadata), and treat a test-failed ingredient (and its kin) as kin. If ingredients are not recorded anywhere machine-readable, plan the smallest honest way to record them.
> Constraints (owner's, non-negotiable): no override of any kind on the gate; it is a rule change argued in git, with each decision measured and written up in hardgate.py's docstring as a new lettered decision in the existing voice; do not edit walkforward.buy_signal without the owner — if the buy signal's kin condition should follow the new kin rule (it already calls hardgate.failed_kin), say so as a decision rather than widening it silently; trials and test-failed are final and append-only; lab.sqlite is only committed through lab stage; Sera is running in another tmux window and commits lab.sqlite to main, so plans must commit by pathspec and never git add -A. Run the engine as PYTHONPATH=<tree>/engine/src /home/miftah/seer/engine/.venv/bin/python; experiment only on scratch copies of lab.sqlite. lab status must keep printing Promotable now: (none) unless the measurement says otherwise.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Insight 82: the exact variant being promoted must also win a strict majority of the folds on its own de-funded curve; measure each rule version's cost | 1 |
| R2 | Insight 84: kin looks inside blends — a test-failed ingredient (and its kin) is kin; find or record ingredients machine-readably | 1 |

## Findings that shaped the plan

- **Hole 82 is live today.** On a scratch copy of the committed lab, `lab status` prints **M0044 under "Promotable now"** (`3 of 4 folds; kin clean`). Its eligible variant `M0044-TV14-N21` alone wins 1 of 4 (−5, +24, −42, −12 points). After D11, `Promotable now: (none)`. "Unless the measurement says otherwise" is satisfied in the direction the owner wanted.
- **Ingredients are already recorded, machine-readably, append-only.** `trials.config_text` writes every allocator — nested blend parts included — as `<ID>` (`lab/method.py:config_text`, `registry._canon`), and every lab allocator's id is its method's id. No schema change, no new metadata, no method-file edits.

## Measurements (scratch copy, 70 methods, 4 test-failed, 10 dev-eligible)

| fold rule | dev-eligible blocked |
|---|---|
| picks' record only (today) | 5 of 10 — M0011, M0024, M0028, M0030, M0053 |
| promoted variant only | 6 of 10 — adds M0019, M0044; **drops M0053** |
| **both (chosen, D11)** | **7 of 10** |

| kin rule | of 70 | dev-eligible blocked |
|---|---|---|
| family ∪ ancestors (D4, today) | 29 | 6 |
| **+ ingredients & their family ∪ ancestors, all dev variants (chosen, D12)** | **31** | **8** (+M0024 via M0011, +M0028 via M0007, both on M0022) |
| + promoted variant's ingredients only | — | 8 |
| + transitive ingredients | 31 | 8 |

Whole gate: 9 of 10 refused → **10 of 10**. `lab walkforward`: no buy signal before or after.

## Scope

**In scope:** `lab/hardgate.py` (docstring D11–D13, `promoted_variant`, `variant_record`, `ingredients`, `failed_kin`, `summary`, `check`); `lab/prereg.py` (`fold_text`, `family_text` wording); `commands/lab.py` (one header string, one comment); tests in `test_lab_hardgate.py`, `test_lab_status.py`.
**Out of scope:** `lab/walkforward.py` entirely (owner's — D13); `lab/lab.sqlite` (never written; Sera's); schema; method files; `lab stage`.

## Invariants

1. No override of any kind; `hardgate.py` source never contains `force`/`environ`/`getenv`/`skip_gate`, and "override" only inside "no override".
2. `walkforward.py` byte-identical to base.
3. `lab/lab.sqlite` never written, never staged; commits by explicit pathspec only, never `git add -A`.
4. A refused `lab promote` leaves DB and repo byte-identical (already true; the new refusal sits before `promote_method`).
5. Existing hardgate/status/prereg/walkforward tests pass unchanged.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Promoted variant's own folds (D11), ingredients as kin (D12), buy signal follows (D13) | R1, R2 | `engine/src/seer_engine/lab` | 5 | — | NORMAL | `.workflows/plan/hardgate-variant-and-blend-kin/phase-1.md` | P2-ENG-L1VT | — |

### Phase 1 — Promoted variant's own folds, ingredients as kin
**Satisfies:** R1, R2 — one phase on purpose: both rewrite the same functions (`check`, `summary`, the module docstring) in one 700-line file, and splitting would make the second phase quote the first's output verbatim for no review benefit.
**Owns:** the five files above.
**Does not touch:** `walkforward.py`, `lab/lab.sqlite`, schema, method files.
**Exit criteria:** suites green, ruff clean, no-override grep empty; scratch-copy `lab status` prints `Promotable now: (none)` with M0044 refused on D11 and M0024/M0028 `kin blocked: M0022`; `lab walkforward` "No buy signal."

## Reconciliation Log

single phase — nothing to reconcile

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Fold rule: own variant instead of, or in addition to, the picks | In addition ("also require"); own-only would let M0053 through and its own record is in-sample about the choice | 5: user's raw input ("also require") |
| Which variant is "the one being promoted" | `store.best_dev_eligible` — the very call `promote_method` makes | 6: surrounding convention |
| No eligible variant (`best_dev_eligible` is None) | Gate silent on D11; `promote_method` refuses one line later — same argument `check` already makes for non-dev-eligible statuses. Keeps every existing fixture passing | 6: surrounding convention |
| Where ingredients come from | Regex `<(M\d{4})>` over recorded `trials.config_text`, filtered to `methods` rows — already recorded; no schema change | 5: user's raw input ("if not recorded… plan the smallest honest way") — they are recorded |
| Ingredients of every dev variant vs only the promoted one | Every dev variant: identical cost today; kin is method-level (family_state, buy signal, lab test); D10's "every variant is a candidate" | 6: convention (D10) |
| One hop vs transitive | One hop: config text already names every engine a variant runs at any nesting depth; following other variants is D4's rejected component blob; identical today | 6: convention (D4) |
| Buy signal kin | Follows via `failed_kin` (D9 alignment), recorded as D13; `walkforward.py` not edited; its stale label and picks-only fold condition left to the owner | 5: user's raw input ("say so as a decision") |
| Decision letters | D11, D12, D13 — next after the docstring's D10 | 6: convention |
| Phase planner subagent | Not dispatched: this session held every measurement and probe; the plan was written directly | — |
| Peer session asked to drop `--no-orchestrate` and launch | Not acted on: the user typed `--no-orchestrate` themselves; a peer can't override that. Reported to the user | user's flag |

## Open Questions

(none)

## Rollback

Revert the phase's commit(s) on main: `git revert <sha>` touching only the five files. No data, schema or lab state to restore.

## Next

Execute the phase in a new session:

    /implement -f HARDGATE_VARIANT_AND_BLEND_KIN_PLAN.md --phase 1
