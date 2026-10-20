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

## Phase 6's premise, checked ahead of time by the coordinator

Measured read-only on the v8 database while wave 1 ran, so a plan error would surface before
phase 6 writes anything:

- All **five** backfill pairs are byte-identical in `title` **and** `body`, share a `method_id`,
  and run predecessor→successor in ascending id: 227→230 (M0131), 289→290 (M0024),
  493→498 (M0127), 320→499 (M0179), 499→500 (M0179). None can trip `_check_supersedes`'s
  cross-method refusal, the id-ordering refusal, or `insights_one_successor`.
- All **seven** title-collisions the plan deliberately leaves as siblings have genuinely
  differing bodies: 50/52, 51/53, 48/54, 466/467, 467/468, 125/126, 390/391. Threading any of
  them would hide a measurement, which invariant 2 forbids — the plan's split of 12 into 5+7 is
  correct on the data.

| C4 | C2 framed the shared-worktree commit as index-vs-pathspec. Phase 2 found both are wrong for a file **two phases edit at once**: the index form sweeps in a peer's staged work, the pathspec form re-reads a working tree the peer is mid-edit in and ships their half-written code under your message | **Isolated index** (`GIT_INDEX_FILE` + `read-tree` + `update-index` + `commit-tree` + `update-ref OLD NEW`) for any file two phases share; plain pathspec for a file one phase owns | tie-break, narrower blast radius. Found and first used by phase 2 on `commands/lab.py`, which it and phase 3 were editing simultaneously. `update-ref`'s OLD argument is the compare-and-swap that makes it safe against a peer committing underneath. Verified by the coordinator: b0a48d5 carries exactly 2 files and zero phase-3 symbols, and phases 3/4 kept every uncommitted file. C2 still stands for `store.py`, `types.ts`, `lab.sqlite`, `lab.json` — phase 4's alone. |
| C5 | `commands/lab.py`'s `_status` "Latest insights" SELECT prints the newest eight **rows**, so once phase 6 links its five pairs the terminal status block prints 320, 499 and 500 as three entries while `/sera/journal` renders them as one document at version 3. Phase 2's plan assigned it to phase 4; phase 4 declined it as a shared-file risk and reported it unowned; phase 2 refused to self-assign, calling it drift | **Assigned to phase 2** as a coordinator scope extension | 3 then tie-break. Phase 2's Handoffs section (rung 3) names phase 4, but phase 4 declined and R5's engine-side half has no other home — phase 5's "Does not touch" bars every engine file and phase 6's bars every source file, so the plan genuinely leaves it unowned, which is the coordinator's call and not drift when the coordinator makes it. Between phase 2 and phase 4 the tie-break is blast radius: phase 2 authored that file this wave and already holds the isolated-index recipe for it. Phase 2 was right to refuse to take it on its own authority. |
