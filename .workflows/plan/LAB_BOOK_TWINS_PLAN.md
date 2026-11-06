# Plan: Lab book twins — name a book the lab already recorded, everywhere it is reported

**Slug:** lab-book-twins
**Date:** 2026-11-06 15:10 WIB
**Analysis:** `.workflows/analyze/20261106-151026-T7WN_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/lab-book-twins`
**Branch:** `feature/lab-book-twins` (base: `origin/main` @ `3b87070`)
**Phases:** 3
**Status:** phases 1/3 and 3/3 complete (phase 2 running)
**Coordinator:** —

---

## Why

From `docs/plans/2026-11-06-handover-repeated-control-arms.md` (verbatim excerpts):

> The batch's calculate-assets run on M0488 reported its never-aside control at Rp 2,146.7M
> (2018-04-01 to 2026-10-08). The owner's top-4 note already holds that exact book as DEEPTAPE
> (M0447-DVC10-NEVER). [...] Why the digests differ: each method file wraps M0125's host
> `WeightParams` in its own params dataclass [...]. The digest covers the wrapper, so the same book
> gets a new identity in every follow-up method. The runner's "already-run digest" refusal never
> fires.

> **Constraints:** the protocol requires controls to run beside the treatment, so a reused control
> must stay attached to the new method. N policy counts methods, not arms. Closed records and
> existing digests are frozen: never rewrite trials 1536/1674/1734.

> Follow CLAUDE.md: smallest change that fixes it, prove it with the `verify-seer` skill, keep
> `lab.sqlite` append-only, and use explicit pathspecs when committing.

Measured by the coordinator at `3b87070`: 80 byte-identical-curve groups, 260 rows, 180 duplicate
rows under the twin definition (any store); 74 groups / 195 rows / 121 duplicates within one store
fingerprint;
the handover's book has four recordings (M0125-DV-C10 too); M0447 and M0488 are dev-eligible on
an arm whose curve is `M0442-DVC10-FIXED730`'s.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Detect that a candidate is behaviourally a book the lab already recorded, and decide what happens on a match, without touching frozen records | 1 |
| R2 | Stop reporting surfaces (promote, calculate-assets, `lab status`, the Sera relay) presenting a control or an already-recorded book as a new candidate | 1, 2, 3 |
| R3 | Decide whether Sera's slate selection (skill or `lab idea`) warns about arms that re-measure a recorded book | 3 |
| R4 | Re-run COSK to 2026-10-06 and say whether calculate-assets output changed for a fixed end date | — (measured in the analysis: no change; Rp 1,783,094,603 reproduced exactly) |

## Scope

**In scope:** a derived, read-only twin reader over `trials.curve_json`; `lab run` twin
annotation; `lab twins` subcommand; role/twin tags on `lab status` near-miss and
closest-to-eligible rows; a `lab promote` refusal (hardgate D19) when the arm to pre-register is a
twin of an earlier method's trial or of a same-method control; calculate-assets role + twin line
(stdout and `--out` JSON); Sera skill text.

**Out of scope:** any schema change or new table (twin-ness is derived on read); any pre-run
refusal or digest change (would move every recorded digest — memory
`seer-shared-params-cannot-gain-a-field`); editing frozen method files; the web `/sera` pages and
`lab.json`; `lab idea` (an idea row has no candidates to compare); correcting note J-60F
(owner's note).

## Invariants

1. No row of `lab/lab.sqlite` is written, updated or deleted by any new code path; no migration.
2. No `config_digest`, `config_text`, method file or `best_dev_eligible` ranking changes.
3. Every new annotation in `lab run` is a forwarder in try/except that cannot fail a recorded run (D15).
4. calculate-assets never opens the lab DB through `lab.store`; only `sqlite3.connect("file:...?mode=ro", uri=True)`, and a missing/unreadable DB degrades to "twin not checked", never an error.
5. Twin = same `window`, same `trades`, byte-identical `curve_json`; "first recorded" = lowest `n`. Store fingerprints of both are reported; a cross-fingerprint twin is still a twin.
6. Engine tests (`pytest engine/tests`) and `ruff check engine` pass at the end of every phase.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Twin reader and lab CLI surfaces (run, twins, status, promote D19) | R1, R2 | `engine/lab`, `engine/commands` | 6 | — | HARD | `.workflows/plan/lab-book-twins/phase-1.md` | P1-ENG-K7QD (done 2026-11-06) | — |
| 2 | calculate-assets names controls and twins | R2 | `.claude/skills/calculate-assets` | 2 | 1 | NORMAL | `.workflows/plan/lab-book-twins/phase-2.md` | P2-ROOT-M3ZV | — |
| 3 | Sera skills read the twin line | R2, R3 | `.claude/skills` | 2 | 1 | EASY | `.workflows/plan/lab-book-twins/phase-3.md` | P2-ROOT-R9XA (done 2026-11-06) | — |

### Phase 1 — Twin reader and lab CLI surfaces
**Satisfies:** R1, R2
**Owns:** new `engine/src/seer_engine/lab/twins.py` (pure reader, rows read by position: `Twin` frozen dataclass with properties `earlier`, `same_method`, `same_store` and `provenance()`; `fingerprint(curve_json)`; `twins_of(conn, candidate_id, window='dev') -> tuple[Twin, ...]`; `first_recorded(conn, candidate_id, window='dev') -> Twin | None`, the earliest OTHER trial of the book; `for_method(conn, method_id, window='dev')`; `report_lines(found, roles, *, limit=3)`); `hardgate.book_twin_refusal(conn, method_id, candidate_id)`; new `engine/tests/test_lab_twins.py`; `commands/lab.py` (`lab run` block headed `Book twins:` after mirror pairs, always printed, `Book twins: none.` when clean; `lab twins ID [ID ...] [--window dev|test]` subcommand; `_roles`/`_roles_by_candidate`/`_twin_lines`/`_book_tags`, `_arm_roles` delegating with unchanged output; `[role; = X]` tags on `lab status` near-miss and closest-to-eligible rows); `lab/hardgate.py` D19 in `check` beside D18; D19 tests in `engine/tests/test_lab_hardgate.py`; `.claude/skills/verify-seer/features/lab-cli.md`.
**Does not touch:** `store.best_dev_eligible`, `method.config_digest`, `runner.preflight`, `walkforward.buy_signal`, `firings.py`, `control_shape.role_of`, schema/migrations, method files, `web/`, any skill other than the verify-seer feature entry.
**Exit criteria:** `lab twins M0488` prints `M0488-DVC10-NEVER (control) = M0125-DV-C10, first recorded (trial 519, ...)` and `M0488-DVC10-FIXED730 ... = M0442-DVC10-FIXED730`; `lab status` refuses M0258 with `(D19)` naming `M0072-Z2-RAWRANK`; `book_twin_refusal(conn, "M0488", "M0488-DVC10-FIXED730")` names M0442 and returns None for M0442's own arm; journey J6 re-measures every figure in the D19 docstring; ruff and the full engine suite green with 0 skips; `lab/lab.sqlite` hash unchanged.

### Phase 2 — calculate-assets names controls and twins
**Satisfies:** R2
**Owns:** `.claude/skills/calculate-assets/calculate_assets.py` (role via `control_shape.role_of` on the named arm; twin via a `mode=ro` `sqlite3` connection + `twins.first_recorded` on the arm that ran: `TwinCheck` with status `twin` only when `Twin.earlier`, `first` when the arm is itself the first recording, `none`, or `not checked`; one stdout block before the money and `role`/`twin_of` JSON keys), `SKILL.md` (rule 4 allows the one read-only read; a fifth rule: say "control" and name the first-recorded twin when relaying; `lab twins MNNNN`).
**Does not touch:** the money model, `build_page.py`, `build_audit.py`, the engine.
**Exit criteria:** running on `M0488-DVC10-NEVER` prints that it is a control arm of M0488 and `Same book as M0125-DV-C10 (M0125), first recorded 2026-10-16`; on `M0179-N20` prints no twin and `Rp 1,783,094,603` with a money section byte-identical to the base commit's script; `check_twin('M0125-DV-C10')` reads `first`; `lab/lab.sqlite` sha256 unchanged.

### Phase 3 — Sera skills read the twin line
**Satisfies:** R2, R3
**Owns:** `.claude/skills/sera-the-explorer/SKILL.md` (S1 slate rule, S2 relay check, S3 report table, S4 two Never rows), `.claude/skills/explore-and-experiment-new-method/SKILL.md` (E1 design note, E2 read the `Book twins` block, E3 gate trap, E4 D19 at promote, E5 quick reference). New prose says "book twin", never bare "twin".
**Does not touch:** engine code, `lab idea`, `.claude/skills/calculate-assets/*`, any other skill.
**Exit criteria:** both skills name `lab twins` and state that a control's or a book twin's money is never a new book; the explore skill names "the treatment never acted", "the dial never moved" and D19; `lab twins M0488` / `M0447` on a verify-seer copy show the cases the text quotes.

## Reconciliation Log

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Index draft listed phase 1's reader as `twins_of(conn, n)` / `first_recorded(conn, n)` / `fingerprint(curve_json, trades)`; phase 1 ships candidate-id signatures and `fingerprint(curve_json)` | Contract drift (index vs plan) | Index Phase 1 **Owns** rewritten to phase 1's Interface Contract |
| 2 | Phase 2 read `first_recorded` as possibly returning the candidate's own trial and treated "not the same id" as an earlier twin; phase 1 returns the earliest OTHER trial and marks precedence with `Twin.earlier`. A first recording (e.g. `M0125-DV-C10`) would have printed "Same book as M0442-DVC10-NEVER, first recorded" | Unmet assumption | Phase 2 `check_twin` now maps `None`->`none`, `earlier`->`twin`, not `earlier`->new `first` status ("the first recording of this book; recorded again later as X"); JSON `{"status":"first","later_copy",...}`; SKILL.md `--out` text, Interface Contract and journey 3 (adds `M0125-DV-C10` -> `first`) updated |
| 3 | Phase 3 quotes `Book twins:` heading, `Book twins: none.`, `lab twins MNNNN`, `the treatment never acted`, `(D19)` | Contract check | Verified against phase 1 Steps 1, 5, 7b, 7d and its tests: all emitted verbatim. Phase 3 caveats replaced with the confirmation; E2 now mentions `Book twins: none.`; journey 3 expectation for the DEEP ladder made concrete (`DEEP15 ... is the first recording`, later rungs `= M0488-DVC10-DEEP15, an earlier arm of this method`) |
| 4 | Phase 2 SKILL.md rule 5 names `python -m seer_engine lab twins MNNNN` with a "reconciler should update if different" caveat | Contract check | Matches phase 1's `sub.add_parser("twins")` with positional `ids nargs="+"`; caveat replaced with the confirmation |
| 5 | Phases 1 and 3 called 74/195/121 vs 80/260/180 a disagreement; phase 1 asked the reconciler to arbitrate | Stale figure | Both are correct cuts (one store vs any store), both measured by the coordinator. Phase 1 measured block and handoff, phase 3 facts/handoff/risks, and the index Why rewritten. D19 docstring quotes the any-store figure and J6 re-measures it; no test pins a count |
| 6 | Phase 1 handoff left `walkforward.buy_signal` vs D19 as an "owner decision"; phase 2 handoff left `role_of` on `M0488-DVC10-FIXED730` to "phase 1 or a follow-up" | Unresolved fork | Settled in Decisions (leave unchanged, follow-up); both handoffs now cite the decision |
| 7 | File ownership across phases | File collision check | Phase 1: `engine/**` + `verify-seer/features/lab-cli.md`; phase 2: `calculate-assets/{calculate_assets.py,SKILL.md}`; phase 3: `sera-the-explorer/SKILL.md`, `explore-and-experiment-new-method/SKILL.md`. Disjoint; 2 and 3 depend only on 1, so they can run in one wave |
| 8 | Requirement coverage | Unowned requirement check | R1 -> 1; R2 -> 1, 2, 3; R3 -> 3; R4 answered by measurement in the analysis (Decisions row). No creep: each phase's steps serve only its Satisfies ids |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Detect by effective-config digest, result fingerprint, or pre-run probe | Result fingerprint (curve bytes + trades), derived on read, no stored column | 1: invariant 1-2 (a digest change moves frozen digests; wrappers' frozen files cannot gain a hook); handover R1 "same targets on every decision date" is what an identical curve proves |
| On a match: reuse the recorded trial or run and mark | Run anyway (as today), annotate with provenance; no refusal at run | 5: user input "controls run beside the treatment, a reused control must stay attached to the new method"; N counts methods so a twin costs compute only |
| Promote when the arm is a twin | Refuse (hardgate D19): twin of an earlier method's trial → promote that method instead; twin of a same-method control → the treatment never acted | 5: user input R2 "surfaces that present ... a book already recorded as a new candidate"; mirrors D18's existing shape |
| `lab idea` warning (R3) | No: an idea row has no candidates; warning lives in the skills and in `lab run` | 6: surrounding convention (annotations at `lab run`, D15) |
| R4 phase | None: measured in the analysis | 5: user asked to "say whether", which the measurement answers |
| D19 also refuses M0173, M0258, M0284 at promote (arms are byte-copies of M0038-DIV-WATCH / M0072-Z2-RAWRANK) | Accept: a look at a copy is the original's look under another name; promotable-now drops 9→6, measured at 3b87070 | 5: user input R2 "a book already recorded ... presented as a new candidate" |
| walkforward.buy_signal ignores D19 (still fires on M0258/M0284) | Leave unchanged this set; queued as follow-up | 6: smallest change (CLAUDE.md) — buy signal is not among the handover's named surfaces |
| control_shape.role_of reads 'Clock control: ...' rationale (M0488-DVC10-FIXED730) as treatment | Leave unchanged; D19's cross-method clause catches that arm anyway; follow-up | 6: smallest change |
| `first_recorded` returns the candidate's own trial vs the earliest OTHER trial (phase 2 tolerated both) | Earliest OTHER trial, precedence via `Twin.earlier`; calculate-assets says "first recorded as X" only when `earlier`, else "first recording; recorded again later as X" | 3: phase 1's code block (`twins_of` excludes `n <> ?`; `first_recorded` docstring) |
| Duplicate count to quote: 80/260/180 or 74/195/121 | Quote 80/260/180 (any store) where a count is quoted (D19 docstring, re-measured by J6); 74/195/121 is the one-store cut, also correct | 1: invariant 5 (a cross-fingerprint twin is still a twin) |

## Open Questions

(none)

## Rollback

Each phase is one commit; revert it. Nothing is written to `lab.sqlite`, so no data rollback exists or is needed.

## Next

    /implement -f .workflows/plan/LAB_BOOK_TWINS_PLAN.md --phase 1

    /analyze-orchestrator -f .workflows/plan/LAB_BOOK_TWINS_PLAN.md
