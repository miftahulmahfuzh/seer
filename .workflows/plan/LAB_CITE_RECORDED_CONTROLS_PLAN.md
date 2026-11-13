# Plan: lab idea lists recorded controls; children cite them

**Slug:** lab-cite-recorded-controls
**Date:** 2026-11-13 08:07
**Analysis:** `.workflows/analyze/20261113-080701-C7K2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/lab-cite-recorded-controls`
**Branch:** `feature/lab-cite-recorded-controls` (base: `main` @ `5006bbc8`; clean checkout, no origin/main ahead)
**Phases:** 1
**Status:** complete
**Coordinator:** —

---

## Why

Stop the lab re-measuring controls it already holds. Context: Sera batch 20261113-0721 re-ran 8 arms that were byte-identical books of earlier recorded trials (M0545 SMA200/ALWAYS = M0084-MONTHLY/ALWAYS; M0561 D3/D6 = M0558-A3/A6; four M0606 control arms = M0108-DD20, M0232-PLC1, M0313-GDRAW-S2, M0337-DVOL). They were legitimately declared, so lab run accepted them, but each re-run costs run time and extra trial rows and is not new evidence. Goal: at idea-reservation time (lab idea, which already prints neighbours on stderr) also report which standard controls of the new method's frame already exist in the lab (by first-recorded trial id), and update the explore-and-experiment-new-method and sera-the-explorer skills so a child cites a recorded control instead of re-running it and spends its arms on new books. First read lab/runner.py and the lab twins / control code to establish whether recorded control curves can be reused or must be recomputed, and whether reuse is compatible with the append-only lab, N policy, DSR and the hard gate (D19). Do NOT delete or edit existing lab rows (frozen, append-only triggers). Smallest change that works, no new module unless unavoidable; state scope first. Verify with the verify-seer skill, tests green, commit explicit paths only and push to main.

## Requirements

| ID | What the user asked for (verbatim) | Phases |
|---|---|---|
| R1 | First read lab/runner.py and the lab twins / control code to establish whether recorded control curves can be reused or must be recomputed, and whether reuse is compatible with the append-only lab, N policy, DSR and the hard gate (D19). | 1 |
| R2 | at idea-reservation time (lab idea, which already prints neighbours on stderr) also report which standard controls of the new method's frame already exist in the lab (by first-recorded trial id) | 1 |
| R3 | update the explore-and-experiment-new-method and sera-the-explorer skills so a child cites a recorded control instead of re-running it and spends its arms on new books. | 1 |
| R4 | Do NOT delete or edit existing lab rows (frozen, append-only triggers). Smallest change that works, no new module unless unavoidable; state scope first. Verify with the verify-seer skill, tests green, commit explicit paths only and push to main. | 1 |

### Acceptance Criteria

| ID | Pattern | Criterion | Phases | Journeys |
|---|---|---|---|---|
| R1.1 | ubiquitous | THE SYSTEM SHALL state, in the lab's own docs, that a recorded control is cited by trial and never copied into a new method's rows, with the reasons it is safe for append-only, N, DSR and D17/D19. | 1 | P1.J4 |
| R2.1 | event | WHEN `lab idea` reserves an id and a neighbouring method holds a control arm THE SYSTEM SHALL print on stderr that control's first-recorded candidate, trial number, owning method, rules/allocator and whether the book was measured on the current store. | 1 | P1.J1 |
| R2.2 | ubiquitous | THE SYSTEM SHALL keep stdout of `lab idea` the bare id. | 1 | P1.J1 |
| R2.3 | unwanted | IF the control listing cannot be read THEN THE SYSTEM SHALL still exit 0 with the id reserved, and write nothing to the lab. | 1 | P1.J2 |
| R2.4 | unwanted | IF a neighbour's control is a later copy of an earlier recording THEN THE SYSTEM SHALL name the first-recorded candidate, once. | 1 | P1.J1 |
| R3.1 | ubiquitous | THE SYSTEM SHALL tell both skills' readers to cite a recorded control instead of re-running it, when it is configured identically and on the current store, and to re-run (declared) otherwise. | 1 | P1.J4 |
| R4.1 | ubiquitous | THE SYSTEM SHALL leave every existing lab row, the lab.sqlite file and web/data/lab.json unchanged. | 1 | P1.J3 |

## Scope

**In scope:** `_recorded_controls` in `commands/lab.py` plus its call in `_print_idea_neighbours`; tests; a `twins.py` docstring paragraph recording the reuse finding; wording in the two skills, `lab-cli.md` and one `CLAUDE.md` clause.
**Out of scope:** any `lab run` behaviour (the repeat refusal stays the guarantee), `hardgate`, `runner`, a new subcommand, a schema or row change, copying curves into trials, auto-skipping arms at run time, retrofitting M0545/M0561/M0606.

## Invariants

- No lab row, `lab/lab.sqlite` or `web/data/lab.json` changes; nothing is written after the reservation.
- stdout of `lab idea` stays the bare id; the listing is stderr only and never fails the reservation.
- `lab run`, N policy, DSR and the hard gate are unchanged.
- Tests green and ruff clean at the end of the phase.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | idea lists recorded controls; skills say cite | R1, R2, R3, R4 | `engine` + skills | 7 | — | NORMAL | `.workflows/plan/lab-cite-recorded-controls/phase-1.md` | P2-ENG-3UGL | — |

### Phase 1 — idea lists recorded controls; skills say cite
**Satisfies:** R1, R2, R3, R4
**Owns:** everything in Scope.
**Does not touch:** the out-of-scope items.
**Exit criteria:** J1-J4 pass, ruff clean, pytest green, one commit on `main` pushed.

## Reconciliation Log

single phase — nothing to reconcile

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| "Frame" at idea time is only text (no arms yet) | the five word-neighbours `lab idea` already computes stand in for the frame; their control-role arms are listed | 5: user input ("lab idea … already prints neighbours") |
| Reuse a curve vs recompute | cite by trial, never write a row; recorded numbers are what a re-run would reproduce byte for byte | 1: invariant (append-only, D19 twin) |
| Which recorded controls may be cited | exact rules/allocator/params match and book on the current store (newest dev trial's fingerprint, itself or any copy); else re-run as declared control | 2: exit criteria; a stale-store book has not been shown to reproduce |
| Hint vs refusal | hint only on stderr; `lab run`'s refusal unchanged | 5: user input "smallest change" |
| Phase plan written by the planner directly | no `phase-planner` subagent for a one-phase set | 6: convention (the analysis already held everything) |

## Open Questions

(none)

## Rollback

`git revert` the one commit. Nothing is written to the lab or the web data, so there is nothing else to undo.

## Next

    /implement -f /home/miftah/.worktrees/seer/lab-cite-recorded-controls/.workflows/plan/LAB_CITE_RECORDED_CONTROLS_PLAN.md --phase 1
