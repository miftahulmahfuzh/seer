# Plan: one journal document per topic, with versions

**Slug:** `journal-versioning`
**Date:** 2026-10-20 16:20:50 UTC
**Analysis:** `docs/analyzer/20261020-162050-J7K2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/journal-versioning`
**Branch:** `feature/journal-versioning` (base: `origin/main` @ `15a9a9a`)
**Phases:** 6
**Status:** phase 1/6 complete
**Coordinator:** —

> This file supersedes the design note of the same name written earlier today. The design is
> carried forward intact; what is new is the **measured** state of the journal, one correction to
> the design that the measurement forced (§Design correction), and the phase plans.

---

## Why

The owner, 2026-10-20:

> *"I hate this journal append-only rule. It will add to an infinite number of trash and outdated
> logs one day. Can we change it so each document can have some kind of versioning instead? So
> instead of showing 4 documents talking about one thing in Sera, we can just show 1 document, but
> we will say this is the fourth version."*

And the spine that does not move:

- **Append-only protects the audit.** Nobody — the owner, Sera, a child session — can quietly
  rewrite what a method predicted *after* seeing how it turned out. That is why
  `insights_no_update` / `insights_no_delete` exist.
- **Nothing about that guarantee requires a bad reader.** Showing the owner four entries on one
  topic is not integrity, it is an unrendered chain.

**So: keep the store immutable, add a `supersedes` link, render chains as versioned documents.**
Superseding *adds* a row; it never mutates one.

Owner decision, 2026-10-20, relayed through `sera-20261020-1417`: **option (a)** — narrow
`insights_no_update` to protect content while letting `supersedes` go `NULL`→value exactly once.
(b) is recorded history, not a live branch. Phase 6 (backfill) is therefore in scope.

---

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Render a chain of rows as **one document labelled with its version**, history behind a disclosure | 4, 5 |
| R2 | Stop the pile-up growing: auto-journalling links a re-run instead of appending a sibling | 3 |
| R3 | Thread the duplicates that already exist, starting 500→499 | 6 |
| R4 | Narrow `insights_no_update` to protect content, and test it harder than the trigger it replaces | 1 |
| R5 | Counts and filters count **documents, not rows**; a new version reads as *revised*, not *new* | 5 |
| R6 | An honest verdict on whether the cheap alternative is enough on its own | — answered in §Verdict below; it is an analysis deliverable, not build work |

---

## Verdict: is the cheap alternative enough?

The brief asked for a real hearing of *"just teach the auto-journalling commands not to duplicate
in the first place"* — 90% of the complaint for 10% of the work. It got one, and the measurement
came back with an answer nobody expected.

### The cheap alternative, as anyone would build it, is not cheap — it is unsafe

The obvious key is `(method_id, title)`: if a command is about to write a note that matches one it
already wrote for this method, don't. That key would have caught 12 of the 500 rows. **Seven of
those twelve are not duplicates.** They are different *variants* of the same method, reported under
one generated title because `real_costs` titles on `cmp.method_name` and never on its
`cmp.candidate_id` — which it has, at `real_costs.py:226`, and does not use.

Matched against the recorded `trials` rows:

| insight | reported max DD / PF | is actually |
|---|---|---|
| 466 | 23.8% / 1.98 | `M0260-M-NATIVE` |
| 467 | 25.6% / 1.62 | `M0260-M-G12` |
| 468 | 33.6% / 1.60 | `M0260-M-G3` |

Written 25 and 30 seconds apart, identical titles, same method. They look exactly like an
accidental triple-write. They are three separate measurements.

A title-keyed dedupe would have **silently discarded** `M0260-M-G12`, `M0260-M-G3` and
`M0008-N30-C07`. And the plan's own §3 auto-link rule — *"looks for its own most recent head for
that `method_id` and supersedes it"* — is the same bug wearing the feature's clothes: it would have
buried the 23.8%-drawdown arm underneath the 33.6% one and shown the owner only the last. **A
measurement disappearing off the rendered page is the exact failure append-only exists to
prevent.** Building it would be this change doing, by accident, the thing it was written to avoid.

So the cheap alternative is rejected on its own terms — not for being too small, but for being
wrong. The same finding forces a correction to the full design (§Design correction).

### The narrow version of the cheap fix is safe, and it is genuinely cheap

Refuse to write a row that is **byte-identical in `title` and `body`** to an existing row for the
same `method_id`. A row identical to its predecessor carries zero information by construction, so
no judgment call about document identity is needed. That rule catches **5 of the 12**, including
`499→500`, `320→499` and `493→498` — the rows that prompted the complaint.

That is roughly one afternoon, no schema change, no migration, no one-way door.

### But it does not give the owner what he asked for

He asked for two things in one sentence and they have different answers:

| The complaint | Does the narrow cheap fix solve it? |
|---|---|
| *"it will add to an infinite number of trash"* | **Yes, mostly.** 5 of 12 today, and it is the half that will keep recurring, because a retried command is the mechanism (see the known trap: a piped `lab` command's exit code is owned by the pipe, so a retry double-appends). |
| *"show 1 document and say this is the fourth version"* | **No. Not at all.** It never merges anything. M0007 keeps its 7 cards. Nothing is ever labelled "version 4". |

And the versioning half is demonstrably wanted, not speculative. Insight **126** already supersedes
**125** — in prose, in the body text:

> *(This replaces the entry just before it, which miscounted the pairs as 20 and claimed too much
> about the walk-forward periods.)*

The relation exists in this journal today. It is hand-written into the text because the schema has
nowhere to put it.

### The honest size of the prize

The peer message asked to be told plainly if phases 4–6 are gold-plating. They are not — but the
reason to build them is not the one in the plan's opening paragraph, and the owner should hear the
correction:

- **The duplicate rows are 2.4% of the journal** (12 of 500), and the truly worthless ones are 1%.
  "The journal is drowning in trash" is a forecast, not a description of today.
- What *is* true today is that `/sera/journal` renders **331 observations as 331 cards**, with
  M0007 appearing 7 times under five near-identical generated titles. **Superseding does not
  collapse those and must not** — they say different things.
- So the phase that most changes what the owner sees is **phase 5, the reader** — version chips,
  heads-only, document counts, history behind a disclosure. Phases 1–4 are the plumbing that makes
  phase 5 truthful rather than a lie about what the database holds.

### Recommendation

**Build it, in this order, and stop after any phase that turns out to be enough.** The phases are
cut so that each one is independently worth shipping:

1. **Phases 1–3 are the floor.** They stop the pile-up growing *correctly* — keyed on what a row is
   actually about, not on a colliding title. Phase 3 alone delivers R2.
2. **Phases 4–5 are the owner's actual request.** Without them nothing is ever labelled a version
   and the complaint is answered only in the half he cared about least.
3. **Phase 6 is small and high-symbolism** — 5 pairs, one of them the 499/500 that started this.

If the owner wants to spend less: **phases 1, 3 and 6 with a deliberately dumb reader** still
leaves the journal honest and stops the growth, and the version chips can wait. What must not be
cut is phase 1's test suite — see Invariants.

---

## Design correction forced by the measurement

The plan as written adds one column, `supersedes`. **That is not sufficient**, and §3's auto-link
rule is unimplementable as specified: it says a writer *"looks for **its own** most recent head for
that `method_id`"*, but `insights` has **no column recording what produced a row**, and no column
recording which variant it is about. Title is the only available key and the measurement proves
title is not a document identity.

**This plan therefore adds two columns, not one:**

```sql
ALTER TABLE insights ADD COLUMN supersedes INTEGER REFERENCES insights(id);
ALTER TABLE insights ADD COLUMN doc_key    TEXT;
```

`doc_key` is the writer-computed stable identity of the **document** a row is a version of —
`real-costs:M0260-M-G3`, `survivorship:M0007-N20-RAW`, `prereg:M0022`. Rows written by hand carry
`NULL` and are linked explicitly with `--supersedes`.

With it the auto-link is exact instead of heuristic:

- same `doc_key` → supersede the current head. A genuine re-run.
- different `doc_key` → append a sibling. A different arm. **466/467/468 stay three documents.**

Everything else in the original design stands unchanged.

---

## Scope

**In scope:** schema version 8 (`supersedes`, `doc_key`, the narrowed trigger, the one-successor
index); the store API; `lab insight --supersedes` and a `lab link` for the backfill; `doc_key` and
auto-linking in the five auto-journalling writers; the snapshot export and its TS mirror; the
`/sera/journal` reader; threading the 5 byte-identical pairs.

**Out of scope:** deleting anything; editing any existing `body`; `methods.analysis` and
`methods.verdict` and their append-only trigger — **those chains stay visible by default**, because
"you said X before the run and Y after" is load-bearing there and M0261's withdrawn 3.21 is only
legible beside its correction; feature-wish 492 (the opinion-value report); `lab/hardgate.py`
(`analyze-fold-selector` is in that file); `lab test`, promotion, any new method id; the
test-window budget, which reads 4 and must still read 4 when this branch lands.

---

## Invariants

Every phase holds all of these.

1. **The tree builds and `pytest engine/tests` passes at the end of every phase.**
2. **No existing content is ever rewritten.** Not one `body`, `title`, `kind`, `method_id` or
   `added` of any of the 500 rows changes, is reformatted, or is re-worded. The only column this
   change ever writes on an existing row is `supersedes`, and only `NULL`→value, once.
3. **The narrowed trigger is a whitelist, not a blacklist.** `supersedes` is the *only* column
   permitted to change, and only from `NULL`. Every other column — including `id`, including
   `doc_key`, including any column added later — aborts. This is what makes the owner's
   "multi-column UPDATE smuggles `body` through" case impossible by construction rather than by
   enumeration.
4. **Tests before the trigger.** Phase 1 writes the full abort suite first and watches it fail
   against the old trigger for the right reason, then narrows the trigger.
5. **`lab stage` THEN test.** `test_lab_snapshot.py` is red by design until `web/data/lab.json` is
   regenerated. Never the reverse.
6. **Commit the lab by index.** `git commit -m …` after `lab stage`; never
   `git commit -- <paths>`, which re-reads the working tree and defeats the staging.
7. **Every commit that moves `lab.sqlite` also carries `web/data/lab.json`.** CI fails a database
   commit without it.
8. **Engine and web constants move together.** `LabInsight` in `web/lib/sera/types.ts` mirrors the
   exported row; a test asserts the mirror.
9. **Do not touch `engine/src/seer_engine/lab/hardgate.py`.** Another session owns it.
10. **Schema 8 is a one-way door.** A v8 database is refused by v7 code on connect. The migration
    and the migrated committed database land in the same commit.

---

## Working in this worktree — already set up, do not redo

Both of this repo's worktree traps were cleared when this plan was written. Use these exact
invocations; neither needs a per-worktree `engine/.venv`.

```bash
# Engine. PYTHONPATH is NOT optional: without it pytest silently tests the MAIN checkout,
# not this branch, and every assertion passes against the wrong tree.
cd /home/miftah/.worktrees/seer/journal-versioning
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine <command>
```

Verified at plan time: that invocation resolves `seer_engine` to
`<worktree>/engine/src/seer_engine/__init__.py` and reports `SCHEMA_VERSION = 7`.

`web/node_modules` is already **hardlinked** (`cp -al`) from the main checkout, 568 MB. Do not
replace it with a symlink: a symlink passes `vitest` and `tsc` and then kills `next build` with a
misleading "filesystem root" error.

Two more, both measured on this machine:

- **`lab stage` targets the checkout that owns the database.** From this worktree it regenerates
  and stages `/home/miftah/seer`'s files. Pass `PYTHONPATH=engine/src`.
- **Do not run concurrent lab phases.** Five at once took WSL down twice on 15 GB. The DAG below
  allows `[2, 3, 4]` in parallel, which is fine — they are unit-test phases. Phase 6 writes the
  database and must run alone.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Schema 8: the narrowed trigger, `supersedes`, `doc_key` | R4 | `engine/lab` | 4 | — | HARD | `.workflows/plan/journal-versioning/phase-1.md` | P1-ENG-JV1K (done 2026-10-20) | — |
| 2 | Writer CLI: `lab insight --supersedes`, `lab link` | R3 | `engine/commands` | 2 | 1 | NORMAL | `.workflows/plan/journal-versioning/phase-2.md` | P1-ENG-H4ZQ | — |
| 3 | Auto-link the five journalling writers on `doc_key` | R2 | `engine/lab` | 7 | 1 | NORMAL | `.workflows/plan/journal-versioning/phase-3.md` | P1-ENG-T2MD | — |
| 4 | Export: snapshot emits the chain; TS mirror; document counts | R1 | `engine/lab` + `web/lib` | 4 | 1 | NORMAL | `.workflows/plan/journal-versioning/phase-4.md` | P1-ENG-Q9XB | — |
| 5 | Reader: heads-only, version chip, history disclosure, "Revised" | R1, R5 | `web/app/sera` | 8 | 4, 6 | HARD | `.workflows/plan/journal-versioning/phase-5.md` | P1-WEB-K6DR | — |
| 6 | Backfill the 5 byte-identical pairs, 500→499 first | R3 | `lab/` data | 2 | 2, 4 | NORMAL | `.workflows/plan/journal-versioning/phase-6.md` | P1-ROOT-N7FS | — |

Waves the DAG allows: **[1] → [2, 3, 4] → [6] → [5]**.

**The `4 → 6` edge was added during planning, not guessed.** Phase 6's planner measured that
`store.snapshot` enumerates insight fields explicitly (`store.py:3002-3006`), so phase 1's new
columns never reach `lab.json` until phase 4 publishes them. Run phase 6 before phase 4 and the
backfill is invisible in the snapshot: the stage diff carries `lab/lab.sqlite` alone, the five
links render nowhere, and the commit *looks* like it breached invariant 7. Ordering 4 ahead of 6
keeps every lab commit carrying both files for the reason the invariant exists. It costs no
wall-clock — 4 is already in wave 2 and 6 in wave 3.

**Content digest, measured at base `15a9a9a`** over `(id, kind, title, body, method_id, added)`
across all 500 rows:

```
04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed
```

This digest **must be unchanged** after phase 6 and after every other phase. It is the strongest
available proof on real data that the narrowed trigger does its job — invariant 2 made checkable
rather than asserted. Any phase that moves it has rewritten content and must be reverted.

### Phase 1 — Schema 8: the narrowed trigger, `supersedes`, `doc_key`
**Satisfies:** R4
**Owns:** `SCHEMA_VERSION = "8"`; `_INSIGHTS_TABLE` gaining `supersedes INTEGER REFERENCES
insights(id)` and `doc_key TEXT`; the rewritten `insights_no_update`; the partial unique index
`insights_one_successor`; `_v7_to_v8` following `_v1_to_v2`'s rebuild recipe exactly (rename aside,
recreate, copy every row with its id, carry `sqlite_sequence`, drop, **then** create the triggers —
they come last or `CREATE TRIGGER IF NOT EXISTS` silently skips them); `store.add_insight` gaining
`doc_key=` and `supersedes=`; a new `store.set_supersedes` that validates and writes the one
permitted UPDATE; the migration test in `test_lab_snapshot.py`; and a new dedicated test module for
the trigger. Also: run the migration once, `lab stage`, and commit the migrated `lab.sqlite` with
`web/data/lab.json`.
**Does not touch:** any CLI, any writer, any web file, `hardgate.py`.
**Exit criteria:** the full abort suite passes; a v7 fixture migrates to v8 with all 500 rows
byte-identical; `lab.sqlite` is committed at v8 alongside a regenerated `lab.json`;
`pytest engine/tests` green.

The trigger, which is the deliverable:

```sql
CREATE TRIGGER IF NOT EXISTS insights_no_update BEFORE UPDATE ON insights
BEGIN
  SELECT RAISE(ABORT, 'insights are append-only: add a newer one instead')
  WHERE OLD.id         IS NOT NEW.id
     OR OLD.kind       IS NOT NEW.kind
     OR OLD.title      IS NOT NEW.title
     OR OLD.body       IS NOT NEW.body
     OR OLD.method_id  IS NOT NEW.method_id
     OR OLD.added      IS NOT NEW.added
     OR OLD.doc_key    IS NOT NEW.doc_key
     OR OLD.supersedes IS NOT NULL;
END;
```

`IS NOT` is SQLite's null-safe distinct operator, so a NULL column compares correctly. The last
clause refuses value→different-value and value→NULL in one line: once set, the link is frozen.
Every other column is named, so a multi-column UPDATE that changes `supersedes` *and* `body` trips
the `body` clause and aborts — the allowed column cannot smuggle a forbidden one through.
**Verified on SQLite 3.45.3 during planning:** `UPDATE … SET supersedes=9, body='z'` aborts *and*
leaves `supersedes` still NULL.

Two things the implementation must carry beyond the SQL above:

- **The index lives in `_INSIGHTS_INDEXES`, not `_SCHEMA`.** See the Reconciliation Log — putting
  it in `_SCHEMA` makes the committed v7 database unopenable.
- **`CHECK (supersedes IS NULL OR supersedes < id)` on the table**, so self-reference and cycles
  are impossible in SQL and not only in Python. The `LabError` stays the friendly path.

**One accepted behaviour change, named rather than discovered later:** under the old blanket
trigger *every* UPDATE aborted, including `UPDATE insights SET body = body`. Under the whitelist
that no-op succeeds, because nothing is distinct so nothing raises. No content moves either way,
and the content digest below is the check that proves it. Recorded because it is a genuine, if
harmless, loosening of the old rule.

**The abort suite (write it first).** Each case is its own test, each asserts
`sqlite3.IntegrityError`/abort and then re-reads the row to prove it is unchanged:

| Case | Expected |
|---|---|
| UPDATE `body` | **ABORT** — the single most important test in this change |
| UPDATE `kind` | ABORT |
| UPDATE `title` | ABORT |
| UPDATE `method_id` | ABORT |
| UPDATE `added` | ABORT |
| UPDATE `id` | ABORT |
| UPDATE `doc_key` | ABORT |
| UPDATE `supersedes` NULL→value | **SUCCEEDS**, exactly once |
| UPDATE `supersedes` value→different value | ABORT |
| UPDATE `supersedes` value→NULL | ABORT |
| UPDATE `supersedes` *and* `body` in one statement | ABORT, and `supersedes` is still NULL afterwards |
| UPDATE `supersedes` *and* `title` in one statement | ABORT |
| `DELETE` | ABORT, unchanged from today |
| two rows superseding the same predecessor | refused by `insights_one_successor` |
| `supersedes` pointing at a higher id, or at itself, or at a missing id | refused by `store.set_supersedes` |
| `supersedes` crossing `method_id` | refused by `store.set_supersedes` |

### Phase 2 — Writer CLI
**Satisfies:** R3
**Owns:** `lab insight --supersedes ID` (link a new row at birth) and `lab link ID --supersedes ID`
(set the link on an existing row — the backfill tool phase 6 runs). Both validate through
`store.set_supersedes` and exit **2** on a rules refusal, never 1. Help strings escape `%` as `%%`.
Update the `lab insight` usage line at `commands/lab.py:130`.
**Does not touch:** `store.py` (phase 1 owns the validation), any writer module, any web file.
**Exit criteria:** both commands covered by tests, including the exit-2 path for every invariant;
`pytest engine/tests` green.

### Phase 3 — Auto-link the five journalling writers
**Satisfies:** R2
**Owns:** a `doc_key` for each auto-journalling writer, and auto-linking through it.
`real_costs` → `f"real-costs:{cmp.candidate_id}"`; `survivorship_check`, `gate_probe` and
`exposure` → the same shape over whatever identifies the arm they measured (**the candidate, not
the method** — this is the whole point of the phase); `prereg` → `f"prereg:{method_id}"`. On write,
if a head already exists with this `doc_key`, supersede it; otherwise append. A `--no-supersede`
escape on each command.
**Does not touch:** `store.py`, `commands/lab.py`'s `_insight`/`_link`, any web file, `hardgate.py`.
**Exit criteria:** a regression test replaying M0260's three arms produces **three documents, not
one** — the measured failure this phase exists to prevent; a test that re-running the *same* arm
produces one document at version 2; `pytest engine/tests` green.

### Phase 4 — Export and TS mirror
**Satisfies:** R1
**Owns:** `store.snapshot` emitting `supersedes`, `docKey`, and the derived `version` and
`supersededBy` per insight, so `view.ts` stays a pure helper with no graph-walking in a component;
`summary.insights` counting **documents** (heads), with the row count kept beside it if the status
block needs it; `LabInsight` in `web/lib/sera/types.ts` gaining the same fields; the snapshot
contract test. Regenerate `web/data/lab.json` with `lab stage` **before** running the suite.
**Does not touch:** the journal page or its helpers (phase 5 owns those), any writer.
**Exit criteria:** `lab.json` is the export of `lab.sqlite`; `npx tsc --noEmit` clean;
`pytest engine/tests` green.

### Gap found during planning, assigned to phase 5

`web/app/sera/overview.ts:130` picks the lab's headline story with

```ts
const synth = newest(snap.insights.filter(i => i.kind === 'synthesis'));
```

where `newest` (`overview.ts:77`) sorts by `added` descending. Phase 4's planner flagged this as
"will pick a superseded row once chains exist". Checked: **in the ordinary case it will not.**
`supersedes < id`, ids are `AUTOINCREMENT`, and `added` is stamped at insert, so a successor always
sorts newer than its predecessor and `newest` lands on the head by construction.

The hole is the case this design deliberately permits: **`kind` may change along a chain** — a
`hypothesis` that becomes an `observation` is the normal life of a lab idea. So a `synthesis` at
row 400 superseded by an `observation` at row 450 leaves 400 as the newest *synthesis*, and the
overview would publish a story the lab has already replaced. Narrow, real, and exactly the failure
this whole change exists to prevent, one page over from the one being fixed.

**Phase 5 owns the fix**, as one line — filter to heads before taking the newest:

```ts
const synth = newest(snap.insights.filter(i => i.kind === 'synthesis' && i.supersededBy === null));
```

plus a case in `overview.test.ts` for a superseded synthesis whose successor changed kind. It is
assigned to phase 5 rather than phase 4 because it consumes the published field rather than
producing it, and because "render heads, not rows" is phase 5's rule.

### Phase 5 — Reader
**Satisfies:** R1, R5
**Owns:** `/sera/journal` rendering **heads only**, each labelled with its version, earlier
versions behind an icon-only disclosure (Lucide, `aria-label`, tooltip — Seer v2, no generic
styling); `kindCounts`, `unseenCounts`, `journalGroups`, `badgeTip` and the "N entries in all" line
counting **documents, not rows**; `page.tsx`'s `unseenByKind` likewise; and the seen-state
interaction made deliberate — a revised document correctly reappears as unseen because its head id
changed, and the marker reads **"Revised"** with its own `aria-label`, not "New". `view.test.ts`
covers chain grouping, version numbering, document counts, and the revised-vs-new marker.
**Also owns, outside `journal/` — three one-line row-vs-document fixes assigned at reconciliation:**
`web/app/sera/layout.tsx:28` (the rail badge, whose own docstring promises it agrees with the
journal's seven badges), `web/app/sera/how/page.tsx:39` (the data-wish count), and
`web/app/sera/overview.ts:130` (the head filter described in the Gap section above), each with a
test.

**Does not touch:** `store.py`, any engine file, `web/lib/sera/types.ts` (phase 4),
`web/lib/sera/lab.test.ts` (phase 4), `seen-client.ts` / `seen-client.test.ts`, the seen API route
or its table, and `/sera/methods` — whose `insightsOf()` stays row-level **by design**, because
that is where "said X before the run, Y after" lives.

**The one that will bite:** `JournalSeen.tsx:219` selects its observation targets with
`querySelectorAll('[data-insight-id]')`. History entries behind the disclosure **must not carry
that attribute**, or expanding a document marks its superseded rows seen and desynchronises every
badge. This is exactly why `JournalSeen.tsx` itself needs no edit.

**Exit criteria:** `npx tsc --noEmit && npm test` green; screenshots at phone (390) and desktop
width in both themes via the `run-the-web-app` skill, showing a version chip and an expanded
history — against the **real chains phase 6 committed**, not a hand-edited snapshot.

### Phase 6 — Backfill
**Satisfies:** R3
**Owns:** running `lab link` over exactly these five pairs, in id order, **500→499 last so the
chain 320→499→500 builds in the right direction**:

| predecessor → successor | method |
|---|---|
| 227 → 230 | M0131 |
| 289 → 290 | M0024 |
| 493 → 498 | M0127 |
| 320 → 499 | M0179 |
| 499 → 500 | M0179 |

Only these. Every one is byte-identical in `title` **and** `body` to its predecessor, which is why
threading it needs no judgment about document identity. The seven rows whose bodies differ are
**different variants** and are deliberately left as siblings. Then `lab stage` and one commit
carrying `lab.sqlite` and `web/data/lab.json` together.
**Does not touch:** any source file. Data only.
**Exit criteria:** the journal renders 495 documents from 500 rows; M0179's note reads version 3;
the test-window look count still reads **4**; `pytest engine/tests` green after `lab stage`.

---

## Reconciliation Log

| Conflict | Phases | Resolution |
|---|---|---|
| `doc_key` grammar: the brief specified `prefix:candidate_id` for all five writers | 3 | **Brief was wrong; phase 3 corrected it.** Only `real_costs` reports a single arm. `survivorship_check`, `gate_probe` and `exposure` each emit one observation per method covering `rows: tuple[VariantRow, ...]`, and `lab survivorship` has no `--only` flag at all. Grammar is `prefix:method_id:scope`, scope = `all` or the sorted `+`-joined arm ids. **Validated against all 12 duplicate rows** — see below. |
| Refusal mechanism: `LabError` vs the unique index | 1, 2, 6 | **`store.set_supersedes` must raise `LabError` for every refusal, including the already-has-a-successor case.** `commands/lab.py:778-786` catches only `LabError` → exit 2; a raw `sqlite3.IntegrityError` escaping `insights_one_successor` exits **1**, which phase 6's backfill would read as a broken tool rather than a refused request. The index stays as a backstop, never as the contract. |
| `web/lib/sera/lab.test.ts:136` asserts `summary.insights === insights.length` | 4, 5 | Goes red the moment counts become documents. **Phase 4 owns it** — it is the phase that changes the meaning. |
| `view.test.ts`'s `ins()` factory needs the four new required fields | 4, 5 | Phase 4 edits the four default lines; additive and trivial. Phase 5 owns the file otherwise. |
| `SNAPSHOT_VERSION` assertion inside phase 1's migration test | 1, 4 | Phase 4 changes only the trailing `assert store.SNAPSHOT_VERSION == 5` line. |
| `web/app/sera/layout.tsx:28` rail badge counts rows | 5 | **Scope extension accepted.** That file's own docstring promises the rail "must agree with the seven badges /sera/journal renders for itself"; left alone, the rail and the page disagree over one snapshot. One line, last step, revertible alone. |
| `web/app/sera/how/page.tsx:39` counts data-wish **rows** | 5 | **Assigned to phase 5.** Same row-vs-document rule, one line. Unowned otherwise. |
| `web/app/sera/overview.ts:130` can publish a superseded synthesis | 4, 5 | **Assigned to phase 5** — see the Gap section above. The reported mechanism was wrong; the real hole is the permitted `kind` change along a chain. |
| Phase 5's screenshots need chains phase 6 has not created | 5, 6 | **Added the `6 → 5` edge** rather than accept phase 5's temporary hand-edit of `web/data/lab.json` followed by a mandatory `git checkout --` before pytest. Hand-editing a generated file in a worktree shared by concurrent phases, with a revert that must not be forgotten, is not a step to run unattended. Costs one wave; phase 5's unit tests use fixtures and never needed it. |
| **The unique index cannot live in `_SCHEMA`** — the index spec in this plan's own Phase 1 section was wrong and would have bricked the committed lab | 1 | **Phase 1 caught it; verified independently before accepting.** `connect` runs `executescript(_SCHEMA)` (`store.py:655`) *before* `_migrate` (`:661`). On a v7 database `CREATE TABLE IF NOT EXISTS insights` is a no-op, but `CREATE UNIQUE INDEX … ON insights(supersedes)` is not — it resolves against the v7 table and raises `OperationalError: no such column: supersedes`, taking `connect` down **before** the migration that adds the column can run. The committed lab would have been unopenable by its own code. Reproduced on SQLite 3.45.3. Fix: a new `_INSIGHTS_INDEXES` constant, created inside `_v7_to_v8` and again in `connect` *after* `_migrate` (the only path a fresh database takes). |

### The `doc_key` grammar, validated against all 12 duplicate rows

Measured by attributing every duplicate-title pair to its writer and checking whether the body moved:

| writer | pairs | body | under the phase-3 grammar |
|---|---|---|---|
| `real_costs` | 50→52, 51→53, 48→54, 466→467, 467→468 | **DIFFERS** | keyed per-arm (`candidate_id`) → **stay siblings** ✓ |
| `real_costs` | 289→290 | IDENTICAL | same arm re-run → **folds** ✓ |
| `survivorship` | 493→498, 320→499, 499→500 | IDENTICAL | keyed `method_id:scope` → **folds** ✓ |
| `exposure` | 227→230 | IDENTICAL | keyed `method_id:scope` → **folds** ✓ |
| manual | 125→126, 390→391 | DIFFERS | no `doc_key` → **stay siblings**, linkable by hand ✓ |

Every one of the twelve lands where it should. The five dangerous ones — different arms wearing one
generated title — are all `real_costs`, which is the one writer keyed per-arm.

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| `supersedes` alone vs `supersedes` + `doc_key` | add **both** columns in one migration | 5: the user's raw input asks the auto-linker to find "its own" previous note, which is unimplementable without a writer-computed identity; the measurement proves title collides across variants |
| trigger as blacklist (enumerate forbidden) vs whitelist (`supersedes` only may change) | **whitelist** | 5: the owner's own message names the "multi-column UPDATE smuggles `body` through" trap; a whitelist makes it impossible by construction and also protects columns added later |
| is `doc_key` in the protected set? | **yes — it aborts like content** | 5: the owner permitted exactly one column to change, `supersedes`; a new column is not a new permission |
| dedupe-on-write (skip the row) vs supersede (append linked) | **supersede** | 2: phase 3's exit criteria require M0260's three arms to survive; skipping discards a measurement, which invariant 2 forbids |
| backfill all 12 title-collisions vs only the 5 byte-identical | **only the 5** | 1: invariant 2 — threading a row whose body differs hides a measurement, and the 7 are different variants |
| one migration adding two columns vs two migrations | **one (v8)** | 6: `_migrate`'s ladder is documented as one step per version and schema 8 is already a one-way door; two doors cost twice for nothing |
| `ALTER TABLE ADD COLUMN` vs rebuild the table | **rebuild, following `_v1_to_v2`** | 6: that function is the repo's proven recipe for this exact table, carries `sqlite_sequence`, and is the only way to land the new CHECKs and the recreated trigger together |

## Open Questions

*(empty — every fork above was decided from the ladder. The one decision the design deliberately
left open, the trigger, was settled by the owner on 2026-10-20 in favour of (a).)*

## Rollback

**Per phase:** every phase is one commit on `feature/journal-versioning`; `git revert` it.

**As a whole:** the branch is never merged, or is reverted entire. The one asymmetry is
**schema 8**: once a `lab.sqlite` at v8 is committed to `main`, v7 code refuses it on connect
(`store.py:838-852`). Backing out after that point means reverting the committed database to its
v7 blob in the same commit as the code — so if this is going to be abandoned, abandon it **before
phase 1 lands on `main`**. Phases 2–6 are freely revertible; phase 6 only ever wrote `supersedes`
on five rows, and a revert of the database blob undoes it with no content touched.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/JOURNAL_VERSIONING_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/JOURNAL_VERSIONING_PLAN.md
