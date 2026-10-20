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

## A correction the coordinator relayed and phase 3 caught

Phase 2 reported 5 failing modules in the shared worktree (`test_lab_costs`,
`test_lab_survivorship`, three in `test_lab_snapshot`) and attributed them to phases 3 and 4
being mid-edit. The coordinator relayed that to phase 3 **without re-measuring it**, along with
the guidance "do not judge your own phase green from the shared tree".

Phase 3 re-ran the three modules against the tree at `b0a48d5` instead of quoting the number
back, and got **71 passed, 2 skipped, 0 failed**. The coordinator confirmed this independently:
same three modules, same result, 13.0s. `lab/lab.sqlite` is byte-identical to HEAD on both sides
(`98b1216d…`), so phase 3 moved no content.

The five were real when phase 2 measured them and stale by the time they were relayed — taken in
the window between phase 3's writers changing return type and its call-site update, and phase 4's
`SNAPSHOT_VERSION` edit. Both had closed.

**The lesson is the coordinator's, not phase 2's:** a mid-wave test result in a shared worktree
has a shelf life of minutes, and relaying one as a standing fact turns a peer's honest snapshot
into guidance that outlives its evidence. Re-measure before relaying, the same way every other
number in this file was re-measured. The general guidance ("verify in a clean copy") remains
right for attributing a failure; it was the specific claim that had expired.

## C5 landed, in someone else's commit — and C4 is now proven in both directions

The heads-only `_status` SELECT is on the branch and correct, but it is **inside phase 3's
`5b5d16d`**, not phase 2's `79341e4`. Phase 2 wrote the edit, and while it was rebuilding its
isolated-index tree (HEAD moved twice underneath it) phase 3 committed `commands/lab.py` by
pathspec — which re-reads the working tree — and carried phase 2's uncommitted edit away under
*"feat(lab): auto-link the five journalling writers on a doc_key"*.

Phase 2 did not re-implement it. Correct: the workflow is explicit that re-implementing work
already on the branch is how a cosmetic mis-attribution becomes a real conflict, and nobody
rewrites pushed history on a branch three sessions are pushing to. Its `79341e4` carries the two
tests the code half was missing, so the behaviour is pinned by something other than the diff that
happened to carry it, and its commit message names `5b5d16d` so a reader finding either is pointed
at the other.

Verified by the coordinator: the block at HEAD is the heads-only `NOT EXISTS` form with its
comment intact, `engine/tests/test_lab_status.py` is 23 passing tests, and the working tree is
clean for that path.

**This is the stronger argument for C4 than the one that produced it.** Pathspec on a shared file
fails in BOTH directions — it ships a peer's work under your name (what phase 2 avoided in the
morning) and it ships your work under theirs (what happened to phase 2 four hours later). Same
file, same mechanism, opposite victims. Phase 4 reported the same thing from the other side: its
`todos.md`, `package_readme.md` and plan-index edits also rode out inside `5b5d16d`.

**A guard to relay with the isolated-index recipe, found by phase 2 the hard way:** its first
rebuild used a `lab.py` snapshot from the previous HEAD, and committing it would have DELETED 60
lines of phase 3's freshly landed work. A `deletions <= 2` sanity check in the retry loop refused
it. The recipe rebuilds a file from a base commit, so a base that goes stale mid-build silently
reverts whoever landed in between — **re-read HEAD inside the retry loop, never outside it.**

## Follow-up after the set lands — named so it is not lost

`_status`'s heads-only SELECT uses an inline `NOT EXISTS`, while phase 4 landed
`store.INSIGHT_DOCUMENTS_SQL` / `store.insight_document_count()` for the same concept. Phase 2
could not reference the helper: it existed only in phase 4's uncommitted copy at the time, so
referencing it would have left phase 2's commit red on the branch. Both definitions are correct
and tested, so this is redundancy rather than a defect.

**Not folded into phase 6** (rung 6): phase 6's own scope line is *"Does not touch: any source
file. Data only."*, and it is the one phase that writes the committed database and must run alone.
Trading that risk for a cosmetic consolidation is a bad deal. Phase 5 cannot take it either — its
"Does not touch" bars every engine file. It is a clean, small follow-up for after the merge.

## Phase 6 — the proof, and one test it was right to rewrite

**The number the whole branch exists to produce**, measured by the coordinator after the five
writes, read-only, with the plan's own recipe:

```
rows=500 digest=04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed
```

Identical to base, to post-phase-1, and to post-wave-1. Five `UPDATE`s ran against the narrowed
trigger and not one byte of `kind`, `title`, `body`, `method_id` or `added` moved on any of the
500 rows. Invariant 2 is no longer an assertion; it is a measurement on real data.

Links confirmed exactly as specified — `(230,227) (290,289) (498,493) (499,320) (500,499)` —
495 heads of 500 rows, `doc_key` written on 0 existing rows, `lab.json` still the exact export,
`testLooks` still 4, main checkout never written. Full suite 6405 passed / 4 skipped / 0 failed,
ruff clean.

| # | Fork | Chosen | Rung |
|---|------|--------|------|
| C6 | Phase 6's own scope says *"Does not touch: any source file. Data only."* — but the moment the backfill landed, phase 1's `test_the_v7_to_v8_migration_moves_not_one_byte_of_the_web_snapshot` went red on its third assertion, `count(*) WHERE supersedes IS NOT NULL OR doc_key IS NOT NULL == 0` | **Rewrite the assertion, in a separate commit** (data commit `33ac3ad`, test commit `08e4b68`) | 1: plan invariant 1 — the suite is green at the end of every phase — outranks a phase plan's scope prose, and phase 6's own exit criteria demand pytest green. Decided by phase 6 without asking; **the coordinator checked the replacement rather than accepting the reasoning.** |

**Why the rewrite is sound, verified line by line rather than taken on the phase's word:**

- The old assertion pinned the committed database's *contents on the day phase 1 wrote it*, not a
  rule. It reads "nobody has used the feature yet" and goes red for the reason the feature works.
- The replacement compares the whole `(id, supersedes, doc_key)` map before and after `connect`.
  That is **strictly stronger**: it catches a connect that invents a link *and* one that destroys
  one, and it keeps saying so at 5 links or 500. The old form caught only invention, and only
  while the journal happened to be empty of chains.
- The guarantee that a v7→v8 migration threads nothing *by itself* was not lost. It is a claim
  about a genuine v7 database and it is still pinned where it belongs — `test_lab_snapshot.py:736`,
  on the synthetic V7 fixture: `count(*) WHERE supersedes IS NULL AND doc_key IS NULL ==
  len(V7_INSIGHTS)`. Confirmed present and passing.
- Separate commits so the data commit stays data-only and revertible alone, which that phase's
  Rollback section depends on. Correct.

## What phase 5 will render, measured

Four chains, maximum depth 3 — so the history disclosure never hides more than two versions:

| head | version | method | note |
|---|---|---|---|
| 230 | 2 | M0131 | a slower target for the learned ranker |
| 290 | 2 | M0024 | same-month seasonality |
| 498 | 2 | M0127 | rebalance on the slot, not the account |
| 500 | 3 | M0179 | companies that crash with the market — the 320→499→500 chain |

The "N entries in all" line must read **495**.

## Carried forward, owned by nobody — named so they are not lost

1. **Entry 126 says in its own prose that it replaces 125**, but the two are not byte-identical,
   so threading them is a judgment call about document identity. Phase 6 correctly did not make
   it. This is the one case in the journal where the relation is known and unrecorded.
2. **`real_costs.py:226` titles on `cmp.method_name` when it has `cmp.candidate_id` to hand** —
   the original cause of M0260's three colliding titles. Phase 3 fixed the *linking*, not the
   titles, so those three cards still read alike. If the owner asks why M0260 shows three
   near-identical cards, the answer is that they are `-M-NATIVE`, `-M-G12` and `-M-G3`: three
   different measurements at 23.8%, 25.6% and 33.6% max drawdown, correctly kept apart.
3. **Fold `_status`'s inline `NOT EXISTS` onto `store.INSIGHT_DOCUMENTS_SQL`** (see above).

---

# LANDING: the `lab.sqlite` conflict, and the resolution REHEARSED AND PROVEN

**Found before the merge, not during it.** While this set was being built, the peer session
`analyze-fold-selector` committed `4799701` straight to `main`, touching **the same two files
this branch touches**: `lab/lab.sqlite` and `web/data/lab.json`. `lab.sqlite` is a binary; git
cannot merge it, and the conflict is guaranteed.

| | insights | schema | |
|---|---|---|---|
| base `15a9a9a` | 500 | 7 | where the branch was cut |
| `origin/main` | **501** | 7 | peer added insight 501, a `risk` note, `added` 2026-10-20T09:49:05+00:00, body 2587 chars |
| `feature/journal-versioning` | 500 | **8** | migrated, plus the five links |

**Neither side may simply win.** Taking main's `lab.sqlite` discards schema 8, both new columns
and all five links — the entire branch. Taking ours destroys insight 501, a real measurement
another session wrote, which is precisely what invariant 2 forbids and what this whole change
exists to prevent. Resolving a binary conflict by picking a side is the one move that silently
loses a journal entry.

## The resolution — rehearsed on scratch copies, every number verified

Take **our** v8 database, then re-insert main's row 501 into it preserving id and every byte.
`INSERT` is permitted — only `UPDATE` and `DELETE` are blocked by the triggers — so this needs no
exception to the append-only rule and writes nothing to any existing row.

```python
# read main's row exactly as it is
src = sqlite3.connect(f"{main_db.as_uri()}?mode=ro", uri=True); src.row_factory = sqlite3.Row
row = dict(src.execute("SELECT * FROM insights WHERE id = 501").fetchone())
# insert into our v8 copy; supersedes and doc_key stay NULL on it
shared = [c for c in row if c in our_columns]          # id, kind, title, body, method_id, added
dst.execute(f"INSERT INTO insights ({','.join(shared)}) VALUES ({','.join('?'*len(shared))})",
            [row[c] for c in shared])
dst.execute("UPDATE sqlite_sequence SET seq = (SELECT max(id) FROM insights) WHERE name='insights'")
```

`sqlite_sequence` must be bumped or the next journal entry re-uses id 501.

Then **regenerate** `web/data/lab.json` with `lab stage` — never hand-merge it, it is a generated
file and its conflict is an artifact of the binary one underneath.

## Measured results of the rehearsal — all three hold at once

| check | result |
|---|---|
| digest over rows 1-500 | `04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed` — **unchanged**, the branch's work intact |
| digest over all 501 rows | `2d3fb90fac51a5651e6155008910dab56863ba303ae2b83b21a5aebb709c5fd7` — **identical to main's own**, so row 501 survives byte for byte |
| v8 code opens the merged file | yes: **496 documents from 501 rows**, `testLooks` 4 |
| the five links | `(230,227) (290,289) (498,493) (499,320) (500,499)` all present |

496 = 495 heads + the peer's new entry. Correct.

## Re-measure at merge time before executing

`analyze-fold-selector` has exited, so `main` should still be at 501 — but its own 3-phase plan
set is on `main` and may be resumed by someone. **Re-read `origin/main`'s `lab.sqlite` and redo
this comparison before resolving**; if it carries more than row 501, insert every row above 500,
in id order, and re-check both digests.

**If a resume picks this set up on another machine: do not merge `lab.sqlite` by choosing a
side.** Follow the recipe above.

---

# LANDED

`main` @ **`db48956`** — merge of 6 phases, pushed first attempt, `4110b98..db48956`.

| Conflict | Resolved | Rung |
|---|---|---|
| `lab/lab.sqlite` (binary, unmergeable) | branch's v8 database, then `main`'s row 501 re-INSERTed with id and every byte preserved, `sqlite_sequence` bumped to 501 | the rehearsed recipe above. **`--ours` was a trap**: `land --step merge` cuts the land worktree from `origin/main`, so "ours" is main's v7 side. Took `origin/feature/journal-versioning:lab/lab.sqlite` explicitly instead of trusting ours/theirs. |
| `web/data/lab.json` (generated) | regenerated with `store.write_snapshot`, the writer `lab stage` itself calls | 6: never hand-merge a generated file. `lab stage` has no `--db` and targets the main checkout, so the writer was called directly, scoped to the land worktree. Validated first by a control: regenerating from the branch's own database reproduced the branch's committed `lab.json` byte for byte. |
| `docs/plans/JOURNAL_VERSIONING_PLAN.md` | branch's version entire | 3: the file's own first line says it supersedes the design note of the same name, and `main`'s two commits (`984dbea`, `7cbb301`) corrected that earlier *note*. The substance of the correction — that titles collide across variants, with the 466/467/468 table — is carried forward and expanded in the plan's §Verdict and §Design correction. |

**Verified on the committed merge object, not the working tree:**

- rows 1-500 digest `04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed` — unchanged from base. The branch's work is intact and no content moved, through a migration, five links and a merge.
- all 501 rows digest `2d3fb90fac51a5651e6155008910dab56863ba303ae2b83b21a5aebb709c5fd7` — **identical to `origin/main`'s own**, so the peer's insight 501 survived byte for byte. No journal entry was lost to the merge.
- engine 6405 passed / 4 skipped / 0 failed against the merged 501-row database, with Postgres up.
- web 725 passed / 50 files, `tsc --noEmit` exit 0, run against the merged `lab.json` (`node_modules` hardlinked in, never symlinked, and removed before the commit).
- `main` now serves **496 documents from 501 rows**, four chains — 230 v2, 290 v2, 498 v2, 500 v3 — and `testLooks` still reads 4.

**Migrations: none.** The branch adds no file under `db/migrations/`; both sides carry the same 22. The only schema change is `lab.sqlite`'s internal version 8, which travels as a committed binary rather than a Neon migration. Nothing was applied to production, and nothing needed to be.

**Cleanup:** land worktree and `land-journal-versioning` removed; the set's worktree removed; `feature/journal-versioning` deleted local and remote.
