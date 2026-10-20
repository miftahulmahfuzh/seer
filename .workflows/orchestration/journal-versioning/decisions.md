# Coordinator decisions — journal-versioning

Forks settled by `orch-journal-versioning` without asking, so every phase and any resume
inherits them. Each carries the rung of the precedence ladder that decided it
(invariant → exit criteria → plan code blocks → index Why/Requirements → task text → convention).

## Before spawning

**Open Questions:** empty. `/analyze` resolved every fork into the `## Decisions` table of the
plan index; nothing was left open, so nothing needed deciding here.

## During the run

| # | Fork | Chosen | Rung |
|---|------|--------|------|
| C1 | Phase 1's lab commit: the swarm skill says `git commit -- <pathspec>` is the only safe form in a shared worktree; plan invariant 6 says `git commit -m …` after `lab stage` and never `git commit -- <paths>` | **Invariant 6 wins for the commit carrying `lab.sqlite` + `lab.json`; the pathspec form for every source-only commit** | 1: a stated plan invariant outranks a general convention. A pathspec commit re-reads the working tree and defeats `lab stage`'s staging, which is the thing CI's pairing check depends on. Safe here because phase 1 is alone in the worktree — wave 1 does not spawn until it lands. |

## Measured by the coordinator, not taken on report

| What | Value | When |
|---|---|---|
| Content digest, `(id, kind, title, body, method_id, added)` over 500 rows by id | `04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed` | base `15a9a9a`, re-measured read-only before spawning phase 1 |
| `SEER_LAB_DB` | unset — so each worktree uses its own `lab/lab.sqlite` | before spawning phase 1 |
| Live peer on v7 code in `/home/miftah/seer` | `analyze-fold-selector`, busy | before spawning phase 1 |

| C2 | Phase 4 also commits `lab.sqlite` + `lab.json`, but unlike phase 1 it runs **beside concurrent peers** (2 and 3), so C1's justification does not carry | **Phase 4 commits by pathspec**, naming `lab/lab.sqlite` and `web/data/lab.json` explicitly alongside its own source files | 6: C1 chose the index form only because phase 1 was alone in the tree. With peers staging into the same index, an index-based commit sweeps their work in — MEASURED twice on `gotrade-fee-rebuild`. Invariant 6's purpose survives a pathspec commit here, because a pathspec commit reads those two paths from the working tree, which is exactly what `lab stage` just wrote there. If `git diff --cached` shows them staged with content differing from the working tree, `lab stage` targeted another checkout — stop and tell the coordinator. |
| C3 | Spawn wave 1 ([2, 3, 4]) concurrently, or one at a time as phase 1 advised on the back of the "a lab swarm wave crashes this laptop" measurement? | **Concurrently** | 4: the plan index's own "Working in this worktree" section settles it — *"The DAG below allows [2, 3, 4] in parallel, which is fine — they are unit-test phases. Phase 6 writes the database and must run alone."* Phase 1 over-generalised a measurement that was about five concurrent **lab** phases. Phase 6 still runs alone. |

## Verified by the coordinator after phase 1 (not taken on report)

- Content digest re-measured read-only with the plan's own recipe: `04af4687…1673ed`, **unchanged** across the v7→v8 rebuild. Invariant 2 holds on all 500 real rows.
- `web/data/lab.json` is byte-for-byte the export of the migrated `lab.sqlite` — CI's pairing check passes. `summary.insights = 500`, `testLooks = 4`, `SCHEMA_VERSION = 8`, `SNAPSHOT_VERSION = 5`.
- Commit file lists checked against the ownership table: the branch touches `store.py`, `test_lab_insights_trigger.py`, `test_lab_snapshot.py`, `lab/lab.sqlite` and bookkeeping only. No CLI, no writer, no web source. `hardgate.py` untouched (0 lines), as invariant 9 requires.
- The trigger itself exercised at raw SQL on a scratch copy: UPDATE of body/title/kind/method_id/added/doc_key and DELETE all ABORT; `supersedes` NULL→value succeeds exactly once; value→other and value→NULL ABORT; and the owner's named trap, `SET supersedes=?, body='z'`, ABORTs leaving `supersedes` still NULL.
- Phase 1 could not reproduce the plan's literal digest because the plan index does not publish its hashing recipe. The recipe **is** published, in `phase-6.md` lines 235-252. The coordinator used it; both sides match. No content moved.
