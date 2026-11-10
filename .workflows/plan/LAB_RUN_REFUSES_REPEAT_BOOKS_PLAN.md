# Plan: `lab run` refuses a book the lab already ran

**Slug:** lab-run-refuses-repeat-books
**Date:** 2026-11-10 09:16
**Analysis:** `.workflows/analyze/20261110-091649-R7QX_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/lab-run-refuses-repeat-books`
**Branch:** `feature/lab-run-refuses-repeat-books` (base: `origin/main` @ `22d1051`)
**Phases:** 1
**Status:** planned
**Coordinator:** —

---

## Why

Owner, verbatim:

> do we need somekind of semantic search algorithm that make sure a new method that sera will explore is unique and has never been explored before?
> just /analyze this shit man. remove human-in-the-loop. make sure we take the robust approach.

> REMEMBER: you don't have to follow my semantic search idea. afterall, i am poor and this is a free tier project. so we just need to be realistic about our requirements

Measured 2026-11-10 on the committed `lab/lab.sqlite`: 213 of 1,952 dev trials are byte-identical
repeats of an earlier book, 144 methods contain at least one, 44 of the last 258 trials are
repeats, and whole treatments repeat (M0538-LOSER = M0028-PLAIN-RESID, trial 159; every arm of
M0447). Because N counts methods **with a dev trial**, a refusal before the trials are recorded
costs no N and needs no extra simulation.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Make sure a new method Sera explores is unique and has never been explored before | 1 |
| R2 | No human in the loop: the guarantee runs and decides without the owner | 1 |
| R3 | The robust approach | 1 |
| R4 | Realistic for a free-tier project: no semantic search, embeddings or paid APIs | 1 |

## Scope

**In scope:**
- Book level (the guarantee): `lab run` / `lab run --amend` refuses, with exit 2 and nothing
  written, an arm that repeats a book another method recorded unless the arm is a declared repeat,
  and refuses a batch where every arm repeats a recorded book. No arm metrics are printed before
  the check.
- Idea level (a hint): `lab idea` prints the five recorded methods whose name, family and
  hypothesis share the most words with the new idea. Stdlib only, never refuses.
- The Sera and explore skills: what an agent does on the refusal and with the neighbour list.
- The verify-seer feature map entry for the lab CLI.

**Out of scope:**
- Semantic search, embeddings, any network call or new dependency (R4).
- A separate pre-commit precheck and a curve cache (the refusal inside `lab run` makes both
  unnecessary: same simulation, no N spent).
- Near-twins (curves that differ by a trade). Byte-identical only, as `lab/twins.py` defines a twin.
- Any change to recorded rows, the schema, `config_digest`, the N policy or hardgate D19.
- Reusing a recorded control's curve instead of re-simulating it.

## Invariants

1. `lab/lab.sqlite` stays append-only; a refused run writes nothing (no method row change, no trial, no journal).
2. N policy unchanged; a refused method stays `idea`/`registered` and does not count.
3. No metric of any arm of a refused batch reaches stdout or the log before the refusal.
4. Existing tests pass; `engine/.venv/bin/ruff check engine` passes.
5. No owner prompt anywhere in the new path (R2).
6. Tests never reach production (autouse fixture untouched).

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Refuse repeat books in `lab run`; neighbours in `lab idea`; skills | R1, R2, R3, R4 | `engine/src/seer_engine/lab`, `commands`, `.claude/skills` | 7 | — | NORMAL | `.workflows/plan/lab-run-refuses-repeat-books/phase-1.md` | — | — |

### Phase 1 — Refuse repeat books in `lab run`; neighbours in `lab idea`; skills
**Satisfies:** R1, R2, R3, R4 (one phase: the four are properties of one mechanism, not separable deliverables)
**Owns:** `lab/twins.py` (lookup by unrecorded curve + the refusal rule), `lab/runner.py` (check before `insert_trials`, log after), `commands/lab.py` (`_idea` neighbours, roles into the run), tests, the two skills, `verify-seer/features/lab-cli.md`.
**Does not touch:** recorded rows, schema, `config_digest`, N policy, hardgate, web/.
**Exit criteria:** a test proves a cross-method treatment repeat is refused with exit-2 semantics and writes nothing; a declared repeat and a same-method twin still record; an all-repeat batch is refused; `lab idea` prints neighbours; full engine suite and ruff green.

## Reconciliation Log

single phase — nothing to reconcile

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Semantic search vs book-level check | Book level is the guarantee; idea level is a stdlib word-overlap hint that never refuses | 5: user's raw input (R4, "be realistic") |
| Pre-commit precheck + curve cache vs refusal inside `lab run` | Refusal inside `lab run`, before `insert_trials` | 5: user's raw input (R3/R4) — same guarantee, no N spent, no second simulation, no cache to invalidate |
| A control arm that repeats another method's book (M0115-CTRL = M0109-EW-ALL-W) | Still simulated and recorded, labelled in the Book twins block; not reused from the record | 2: phase exit criteria + index Scope (reuse is out of scope): the control prices the treatment on the same store in the same run, at about a minute's compute |
| Check placement: before `begin_immediate` vs inside the IMMEDIATE transaction before `insert_trials` | Inside the transaction (phase-1 plan) | 1: invariant 1 — parallel Sera children cannot both record the same book; raising rolls back, nothing written |
| hardgate.py D15/D19 docstrings still say `lab run` only annotates | Left unchanged this phase; wording follow-up queued in Next | 2: index Scope says hardgate is not touched |
| What counts as a declared repeat | `control_shape.role_of(arm) == ROLE_CONTROL`, or the arm's rationale names the earlier twin's method id | 6: convention (Sera already requires the hypothesis to name the recorded host) |

## Open Questions

(none)

## Rollback

Revert the phase's single merge commit. Nothing is written to `lab.sqlite` by this change, so no data rollback exists or is needed.

## Next

Follow-up (docs only, not this phase): hardgate.py D15/D19 docstrings should say `lab run` now refuses an undeclared cross-method repeat.


    /implement -f .workflows/plan/LAB_RUN_REFUSES_REPEAT_BOOKS_PLAN.md --phase 1
