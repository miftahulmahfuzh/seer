# Code Analysis: journal versioning (`insights` supersedes chains)

**Type:** Feature Implementation
**Date:** 2026-10-20 16:20:50 UTC
**Session ID:** 20261020-162050-J7K2
**Plan:** `docs/plans/JOURNAL_VERSIONING_PLAN.md` (6 phases)
**Worktree:** `/home/miftah/.worktrees/seer/journal-versioning`, branch `feature/journal-versioning` (base `origin/main` @ `15a9a9a`)

---

## User Input

### Original User Request

> Read that plan in full first. It was written this session from measured state, not guesses, and
> it names one decision it deliberately does NOT settle.
>
> THE GOAL, in the owner own words: "instead of showing 4 documents talking about one thing in
> Sera, we can just show 1 document, but we will say this is the fourth version." He is right that
> the journal accumulates trash — insights 499 and 500 are BYTE-IDENTICAL today.
>
> THE DESIGN SPINE YOU MUST NOT BREAK: append-only exists so nobody can rewrite what a method
> predicted AFTER seeing the result. That is the lab central anti-self-deception mechanism. The
> plan keeps the store immutable and adds a `supersedes` link so a chain of rows RENDERS as one
> versioned document. Superseding ADDS a row, it never mutates one. If your analysis ends up
> proposing that bodies become editable, you have taken a wrong turn — go back.
>
> THE ONE DECISION THE PLAN LEAVES OPEN, and it is the owner call, not yours: `insights_no_update`
> fires on ANY update, so the existing 500 rows cannot be threaded retroactively without narrowing
> it. Option (a) narrows the trigger to protect kind/title/body/method_id/added while letting
> `supersedes` go from NULL to a value exactly once — this is the only option that fixes today
> duplicates. Option (b) leaves the trigger absolutely alone and only new rows can be linked.
> Analyse BOTH, state the risk of each concretely, recommend one with the argument written out,
> but present it as a decision for the owner.
>
> GROUND TRUTH ALREADY ESTABLISHED (do not re-derive, do verify):
> - engine/src/seer_engine/lab/store.py:99 — SCHEMA_VERSION = "7", migration chain documented
>   inline, _migrate at line 838. This change is version 8.
> - web/data/lab.json carries insights[]; tests/test_lab_snapshot.py asserts the JSON IS the export
>   of lab.sqlite, and CI fails a database commit without it. Both sides move together.
> - Reader is web/app/sera/journal/ — view.ts (175 lines, pure helpers, no data access), page.tsx
>   (179), JournalSeen.tsx, seen-client.ts, view.test.ts.
> - 500 insights exist; the newest duplicates the one before it.
>
> PAY PARTICULAR ATTENTION TO:
> 1. The seen-state interaction. seen-client.ts keys on insight id, so a new version changes the
>    head id and the document reappears as unseen. That is desirable but must be DELIBERATE and
>    tested, and the UI should say "revised" not present it as new.
> 2. Counting. kindCounts and the journal filters must count DOCUMENTS, not rows, or the owner
>    counts still inflate on every re-run — which is his complaint restated.
> 3. What must NOT collapse: method analysis and verdict chains stay visible by default. That is
>    where "said X before the run, Y after" lives. M0261 withdrawn 3.21 figure is only legible
>    beside its correction.
>
> REPO TRAPS: `lab stage` THEN test, never the reverse (test_lab_snapshot is red by design until
> the JSON is regenerated). Commit the lab BY INDEX, never by pathspec. web/ mirrors some engine
> constants and a test asserts they match. Closed records are frozen — this change threads rows
> together and must not reformat or re-word a single existing body. Every lab stage commit
> includes web/data/lab.json. A migration takes the write lock, so do not run one while a child
> session is mid-write.
>
> DO NOT: run `lab test`, promote, spend a method id, or touch the test-window budget (reads 4,
> must stay 4). This is an engine + web feature, not a lab experiment.
>
> NOTE: another session, analyze-fold-selector, is running concurrently and is touching
> engine/src/seer_engine/lab/hardgate.py. Stay out of that file.
>
> DELIVERABLE: a phase breakdown with the trigger decision as phase 1 blocking everything else,
> the test strategy for the narrowed trigger if (a) is chosen (the test that an UPDATE to body
> still ABORTS is the most important test in the change), and an honest assessment of whether this
> is worth building versus just teaching the auto-journalling commands not to duplicate in the
> first place — that cheaper alternative deserves a real hearing, because it may solve 90% of the
> complaint for 10% of the work.
>
> Report back to sera-20261020-1417 with the phases, the trigger recommendation, and your verdict
> on whether the cheap alternative is enough.

### Mid-session owner decision (peer message from `sera-20261020-1417`, 2026-10-20)

> OWNER DECISION, 2026-10-20: go with option (a). Phase 1 of the plan is now SETTLED — stop
> analysing (b) as a live option and do not spend effort recommending between them.
>
> (a) means: narrow `insights_no_update` so it protects CONTENT — abort any UPDATE that changes
> kind, title, body, method_id or added — while allowing `supersedes` to go from NULL to a value
> EXACTLY ONCE. Never value→different value, never value→NULL. Everything else in the plan stands.
>
> What this unblocks: phase 6 (backfilling the existing duplicate chains, starting 500→499) is now
> in scope, because the existing 500 rows CAN be threaded retroactively.
>
> What it obliges you to do, and treat this as the highest-priority item in the whole change: the
> narrowed trigger is now the thing standing between this lab and a rewritten prediction. It must
> be tested harder than the trigger it replaces. At minimum —
> - an UPDATE to `body` still ABORTS (the single most important test in this change)
> - an UPDATE to kind / title / method_id / added each ABORTS
> - supersedes NULL→value SUCCEEDS exactly once
> - supersedes value→different value ABORTS
> - supersedes value→NULL ABORTS
> - a multi-column UPDATE that touches supersedes AND body ABORTS (do not let the allowed column
>   smuggle a forbidden one through)
> - DELETE still ABORTS, unchanged
>
> That last one matters: a naive trigger rewrite that checks "is supersedes changing?" can
> accidentally permit a body edit in the same statement. Write the test before the trigger.
>
> Still live and still wanted: your verdict on whether the CHEAP ALTERNATIVE (just teach
> auto-journalling commands to supersede their own previous note rather than append a sibling)
> solves enough of the owner's complaint on its own. The owner picking (a) does not pre-commit him
> to building all six phases — if the cheap fix plus phase 1-3 gets him one document per topic and
> phases 4-6 are gold-plating, say so plainly. He would rather hear that than have it built by
> default.
>
> Unchanged: no `lab test`, no promotion, no method id, test-window budget stays at 4, stay out of
> hardgate.py (analyze-fold-selector is in there).

### User-Provided Files

- `docs/plans/JOURNAL_VERSIONING_PLAN.md` (the design document this analysis plans against)

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Render a chain of `insights` rows on `/sera/journal` as **one document labelled with its version**, earlier versions behind a disclosure — "1 document, this is the fourth version". |
| R2 | Stop the pile-up growing: auto-journalling commands link a re-run to their own previous note instead of appending a sibling. |
| R3 | Thread the duplicates that already exist, starting 500→499 — unblocked by the owner choosing (a). |
| R4 | Narrow `insights_no_update` to protect content (kind/title/body/method_id/added) while letting `supersedes` go NULL→value exactly once, and test the narrowed trigger harder than the one it replaces. |
| R5 | Counts and filters must count **documents, not rows**; seen-state must treat a new version as *revised*, not *new*, deliberately and under test. |
| R6 | An honest verdict on whether the cheap alternative (dedupe on write) solves enough on its own. |

---

## Detailed Requirements Understanding

**Problem statement.** The lab journal is append-only by trigger. Re-running a command that
auto-journals appends a second row saying nearly or exactly the same thing, and `/sera/journal`
renders every row as its own card. The owner reads N cards where one document exists. He asked for
versioning: one document, labelled "version 4".

**Success criteria.**

1. `lab.sqlite` stays immutable in content. No existing `body`, `title`, `kind`, `method_id` or
   `added` is ever rewritten — verified by a test suite that is strictly stronger than today's.
2. A re-run of an auto-journalling command on **the same subject** produces a linked successor,
   not a sibling.
3. A run on a **different subject that happens to generate the same title** still produces a
   sibling. (See the measurement below — this is the failure mode the obvious design walks into.)
4. `/sera/journal` shows heads, labelled with their version, history behind a disclosure.
5. Kind counts, filter badges and the "N entries in all" line count documents.

**Key constraint discovered by measurement, and it changes the design.** See
*Measured state* below: the generated title is **not** a document identity. `insights` carries no
column saying what produced a row, so neither the cheap fix nor the plan's §3 auto-link can
distinguish "a re-run of the same note" from "a different variant whose generated title collides".
The plan needs **one more column than it currently specifies**.

**Assumptions stated.**

- Schema version 8 is this change; the version number is a one-way door for every other checkout
  (documented at `store.py:838-852`), so engine code and the migrated committed database land
  together.
- The owner's decision (a) is final; (b) is recorded history, not a live branch.
- Method `analysis`/`verdict` chains are explicitly out of scope and keep their current append-only
  trigger untouched.

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/plans/JOURNAL_VERSIONING_PLAN.md`

### Discovered Related Files

| File | Why |
|---|---|
| `engine/src/seer_engine/lab/store.py` | the whole schema, triggers, migrations, `add_insight`, the snapshot export |
| `engine/src/seer_engine/commands/lab.py` | `lab insight`, `lab stage`, the subcommand table |
| `engine/src/seer_engine/lab/real_costs.py` | auto-journals (18 rows) |
| `engine/src/seer_engine/lab/survivorship_check.py` | auto-journals (95 rows) |
| `engine/src/seer_engine/lab/exposure.py` | auto-journals (14 rows) |
| `engine/src/seer_engine/lab/gate_probe.py` | auto-journals (5 rows) |
| `engine/src/seer_engine/lab/prereg.py` | auto-journals (4 rows) |
| `engine/tests/test_lab_snapshot.py` | owns every migration test and the committed-snapshot guard |
| `engine/tests/test_lab_store.py` | the append-only trigger tests |
| `web/lib/sera/types.ts` | `LabInsight` — the TS mirror of the exported row |
| `web/app/sera/journal/view.ts` | `kindCounts`, `unseenCounts`, `journalGroups`, `badgeTip` |
| `web/app/sera/journal/page.tsx` | renders the cards, computes `unseenByKind` |
| `web/app/sera/journal/seen-client.ts` | seen policy, keyed on insight id |
| `web/app/sera/journal/JournalSeen.tsx` | the client island that counts badges down |

---

## Current Dataflow

### Entry Point A: an auto-journalling command

**Location:** `commands/lab.py:2270-2304` (`lab real-costs`), and the four siblings.
**Trigger:** CLI subcommand.
**Chain:** `real_costs.resolve_method` → `pick_candidate(conn, method, args.candidate)` →
`measure(...)` → `real_costs.journal(conn, cmp)` → `insight_text(cmp)` builds `(title, body)` →
`store.add_insight(conn, kind="observation", title=…, body=…, method_id=cmp.method_id)`.

**The title each writer generates:**

| Writer | `title` | Rows today |
|---|---|---|
| `real_costs.insight_text` (`real_costs.py:407`) | `f"{cmp.method_name}: what Gotrade's real fees do to it"` | 18 |
| `survivorship_check.insight_text` (`survivorship_check.py:726`) | `f"{rep.method_name}: what the missing companies did to it"` | 95 |
| `gate_probe.insight_text` (`gate_probe.py:1391`) | `f"{rep.method_name}: what its market safety rule was worth"` | 5 |
| `exposure.insight_text` (`exposure.py:1094`) | `f"{rep.method_name}: what its own picks did, apart from the money it parks"` | 14 |
| `prereg` (`prereg.py:731`) | `f"{row['name']} is pre-registered for its one test-window look"` | 4 |

**Every one of those titles is a function of the method, not of the variant.**
`real_costs.Comparison` carries `candidate_id` (`real_costs.py:226`) and does not put it in the
title. This is the crux — see *Measured state*.

### Entry Point B: `lab insight`

**Location:** `commands/lab.py:3156-3164`.
**Input:** `--kind --title (--body | --file) [--method]`. Exactly one of `--body`/`--file`.
**Exit:** prints the new id. 364 of the 500 rows came this way (Sera's own syntheses and
observations).

### Data Persistence

**`store.add_insight`** — `store.py:2626-2639`:

```python
def add_insight(conn, *, kind, title, body, method_id=None) -> int:
    if kind not in INSIGHT_KINDS: raise LabError(...)
    if method_id is not None and get_method(conn, method_id) is None: raise LabError(...)
    cur = conn.execute(
        "INSERT INTO insights (kind, title, body, method_id, added) VALUES (?, ?, ?, ?, ?)",
        (kind, title.strip(), body.strip(), method_id, now_iso()))
    return int(cur.lastrowid)
```

**Table and triggers** — `store.py:234-247`:

```sql
CREATE TABLE IF NOT EXISTS insights (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kind      TEXT NOT NULL CHECK (kind IN (...)),
    title     TEXT NOT NULL CHECK (length(trim(title)) > 0),
    body      TEXT NOT NULL CHECK (length(trim(body)) > 0),
    method_id TEXT REFERENCES methods(id),
    added     TEXT NOT NULL
);
CREATE TRIGGER insights_no_update BEFORE UPDATE ON insights
  BEGIN SELECT RAISE(ABORT, 'insights are append-only: add a newer one instead'); END;
CREATE TRIGGER insights_no_delete BEFORE DELETE ON insights
  BEGIN SELECT RAISE(ABORT, 'insights are append-only'); END;
```

There is **no column recording which command wrote a row**, and none recording the variant it is
about.

### Exit Point: the web snapshot

**`store.snapshot`** — `store.py:3002-3006`:

```python
"insights": [
    {"id": int(i["id"]), "kind": i["kind"], "title": i["title"], "body": i["body"],
     "methodId": i["method_id"], "added": i["added"]}
    for i in _dicts(conn, "SELECT * FROM insights ORDER BY id")
],
```

`snapshot_json` (`store.py:3028`) is the exact bytes of `web/data/lab.json`.
`lab stage` (`commands/lab.py:3166-3190`) writes it and `git add`s both files under
`BEGIN EXCLUSIVE`.

`store.summary_rows` (`store.py:2704`) and `snapshot["summary"]["insights"]`
(`store.py:2988`) both count **rows**: `SELECT count(*) FROM insights`.

### Exit Point: the reader

`page.tsx:42-45` — `kindCounts(lab.insights)`, `unseenCounts(lab.insights, seenIds)`,
`journalGroups(lab.insights, filter, seenIds)`, `total = lab.insights.length`.
`view.ts:74-78` — `kindCounts` counts every row of a kind.
`page.tsx:71-74` — `unseenByKind` filters `lab.insights` directly, deliberately independent of
`view.ts`'s partition shape.
`page.tsx:141-178` — `InsightCard` renders `data-insight-id={insight.id}`; the island at
`JournalSeen.tsx` reads that attribute and posts ids to `/api/sera/journal/seen`.
`view.ts:46-52` — `SEEN_COPY.marker = 'New'`, `markerLabel = 'Not seen yet'`.

---

## Measured state

Every number below was read from `lab/lab.sqlite` read-only during this analysis. They are not
estimates.

### The journal today

| | |
|---|---|
| insights | **500** |
| by kind | observation 331 · risk 57 · synthesis 48 · feature-wish 34 · hypothesis 17 · data-wish 13 |
| written by hand (`lab insight`) | **364** |
| written by a command | **136** (survivorship 95, real_costs 18, exposure 14, gate_probe 5, prereg 4) |
| rows sharing a `title` with an earlier row | **12** (2.4% of the journal) |
| …of which the body is **byte-identical** | **5** |
| …of which the body **differs** | **7** |
| rows involved in duplicate-title groups | 22 across 10 groups |

### The finding that changes the design

Of the 12 rows a `(method_id, title)` key would have caught, **7 carry different numbers** — and
they are not noisy re-runs. They are **different variants of the same method**, matched here
against the recorded `trials` rows:

| insight | reported max DD / PF | matches trial |
|---|---|---|
| 466 (M0260) | 23.8% / 1.98 | `n=835 M0260-M-NATIVE` dd 0.238 pf 1.98 |
| 467 (M0260) | 25.6% / 1.62 | `n=838 M0260-M-G12` dd 0.256 pf 1.62 |
| 468 (M0260) | 33.6% / 1.60 | `n=836 M0260-M-G3` dd 0.336 pf 1.60 |
| 50 (M0008) | 21.7% / 1.82 | `n=70 M0008-C10` dd 0.216 pf 1.96 |
| 52 (M0008) | 19.7% / 1.96 | `n=73 M0008-N30-C07` dd 0.200 pf 2.14 |
| 48 (M0007) | 19.8% / 2.00 | `n=84 M0007-N20-RAW` dd 0.196 pf 2.16 |

466, 467 and 468 were written 25 and 30 seconds apart on 2026-10-19 and look exactly like an
accidental triple-write. They are not. They are three arms of M0260 reported under one generated
title, because `real_costs` titles on `cmp.method_name` and never on `cmp.candidate_id`.

**Consequence, stated plainly:**

- A dedupe-on-write keyed on title would have **silently discarded** `M0260-M-G12`,
  `M0260-M-G3` and `M0008-N30-C07`.
- The plan's §3 auto-link as currently written — *"looks for its own most recent head for that
  `method_id` and supersedes it"* — would have **buried a 23.8%-drawdown arm underneath a
  33.6% one** and shown the owner only the last. That is a measurement disappearing from the
  rendered page: the precise failure the append-only rule exists to prevent, arriving through the
  front door of the feature built to respect it.
- Neither can be fixed by being cleverer about titles, because `insights` has no column that says
  what a row is about. **`supersedes` alone is not sufficient; a document-identity column is
  required.**

### The 5 genuinely-identical pairs

| predecessor → successor | method | gap |
|---|---|---|
| 227 → 230 | M0131 | 94 s |
| 289 → 290 | M0024 | 26 s |
| 493 → 498 | M0127 | 28 min |
| 320 → 499 | M0179 | 3 days |
| 499 → 500 | M0179 | 15 min |

These five are byte-identical in `title` **and** `body`. By construction they carry zero
information beyond their predecessor, so threading them is objectively safe and needs no judgment
call about what a document is. 499→500 is the owner's trigger case; 320→499 is the same note
written a third time.

### Evidence the feature is genuinely wanted

Insight **126** supersedes **125** in prose. Its body ends:

> *(This replaces the entry just before it, which miscounted the pairs as 20 and claimed too much
> about the walk-forward periods.)*

The supersedes relation already exists in this journal. It is hand-written into the text because
the schema has nowhere to put it. That is the strongest argument in favour of building R1.

### What the owner actually sees

The 12 duplicate rows are 2.4% of a 500-card page. The lived experience of "4 documents talking
about one thing" is better explained by **M0007 carrying 7 cards** — of which exactly one pair is a
mechanical duplicate and the other five are genuinely different observations that all begin
*"Residual momentum: …"*. **Superseding does not collapse those, and must not.** Sizing this
honestly matters, and the Verdict section below does it.

---

## Key Data Structures

### `insights` row (engine) → `LabInsight` (web)

**Engine:** `store.py:234-241`. **Web:** `web/lib/sera/types.ts:207-214`:

```ts
export type LabInsight = {
  id: number; kind: 'observation' | ... ; title: string; body: string;
  methodId: string | null; added: string;
};
```

The two move together: `test_lab_snapshot.py` asserts the committed JSON is the export of the
committed database, and CI fails a database commit without it.

### `JournalGroup` / `JournalEntry`

`view.ts:110-139`. `entries`, `items`, `unseen`, `seen`, `unseenCount` — five views of one
partition, all currently over **rows**.

---

## Dependencies

- **Schema version gate.** `store.py:838-852`: a version this code does not know is refused on
  connect. v8 written by this branch is unreadable by every other checkout until they take the
  code. One-way door.
- **`SEER_LAB_DB`.** Parallel sessions share one database (`store.py:97`). The v8 migration takes
  the write lock under `BEGIN IMMEDIATE`.
- **`lab.sqlite` is dirtied by any lab command that connects** once this lands, because `_migrate`
  runs on connect. The phase that ships the migration must stage and commit the migrated database
  in the same change, or every later phase's test run leaves an uncommitted binary diff.
- `test_lab_snapshot.py:673-676` constructs an "unknown version" fixture using `'9'`. At v8 that is
  still unknown, so it keeps working — but it is one step from colliding and should be read when
  the version moves.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `SCHEMA_VERSION = "7"` | `lab/store.py:99` | def | engine |
| `_INSIGHTS_TABLE` | `lab/store.py:234` | def | engine |
| `_INSIGHTS_TRIGGERS` | `lab/store.py:242` | def | engine |
| `_migrate` | `lab/store.py:838` | def | engine |
| `_v1_to_v2` (insights-rebuild precedent) | `lab/store.py:682` | def | engine |
| `add_insight` | `lab/store.py:2626` | def | engine |
| `summary_rows` insights count | `lab/store.py:2704` | call | engine |
| `snapshot["summary"]["insights"]` | `lab/store.py:2988` | call | engine |
| `snapshot["insights"]` | `lab/store.py:3002` | call | engine |
| `snapshot_json` | `lab/store.py:3028` | def | engine |
| `real_costs.journal` | `lab/real_costs.py:436` | call | engine |
| `real_costs.insight_text` title | `lab/real_costs.py:407` | def | engine |
| `Comparison.candidate_id` | `lab/real_costs.py:226` | def | engine |
| `survivorship_check.journal` | `lab/survivorship_check.py:737` | call | engine |
| `gate_probe.journal` | `lab/gate_probe.py:1395` | call | engine |
| `exposure.journal` | `lab/exposure.py:1097` | call | engine |
| `prereg` add_insight | `lab/prereg.py:731` | call | engine |
| `_insight` (CLI) | `commands/lab.py:3156` | def | engine |
| `insight` subparser | `commands/lab.py:761` | config | engine |
| `_stage` | `commands/lab.py:3166` | def | engine |
| `lab insight` help line | `commands/lab.py:130` | doc | engine |
| "Latest insights" status block | `commands/lab.py:843` | call | engine |
| `LabInsight` | `web/lib/sera/types.ts:207` | def | web |
| `kindCounts` | `web/app/sera/journal/view.ts:74` | def | web |
| `unseenCounts` | `web/app/sera/journal/view.ts:87` | def | web |
| `journalGroups` | `web/app/sera/journal/view.ts:146` | def | web |
| `badgeTip` | `web/app/sera/journal/view.ts:105` | def | web |
| `SEEN_COPY` | `web/app/sera/journal/view.ts:46` | def | web |
| `JournalPage` | `web/app/sera/journal/page.tsx:37` | def | web |
| `InsightCard` | `web/app/sera/journal/page.tsx:141` | def | web |
| `unseenByKind` | `web/app/sera/journal/page.tsx:71` | call | web |
| `SEEN_ENDPOINT` / policy | `web/app/sera/journal/seen-client.ts:12` | def | web |
| migration tests | `engine/tests/test_lab_snapshot.py` | test | engine |
| trigger tests | `engine/tests/test_lab_store.py` | test | engine |
| view tests | `web/app/sera/journal/view.test.ts` | test | web |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/lab/store.py` — schema v8, narrowed trigger, `supersedes` + the
   document-identity column, `set_supersedes`, export. Phases 1, 2, 4.
2. `engine/tests/test_lab_snapshot.py` — the v7→v8 migration test and the stripper that builds a
   v7 fixture. Phase 1.
3. `engine/tests/test_lab_insights_trigger.py` *(new)* — the narrowed trigger's own suite. Phase 1.
4. `engine/src/seer_engine/commands/lab.py` — `lab insight --supersedes`, help text. Phase 2.
5. `engine/src/seer_engine/lab/{real_costs,survivorship_check,gate_probe,exposure,prereg}.py` —
   compute a document key, auto-link. Phase 3.
6. `web/lib/sera/types.ts` — `LabInsight` gains the exported fields. Phase 4.
7. `web/app/sera/journal/view.ts` + `view.test.ts` — document-level counts and grouping. Phase 5.
8. `web/app/sera/journal/page.tsx` — heads-only rendering, version label, history disclosure,
   "revised". Phase 5.
9. `web/app/sera/journal/journal.module.css` — the disclosure and version chip. Phase 5.
10. `lab/lab.sqlite` + `web/data/lab.json` — migrated by phase 1, threaded by phase 6.

**This document describes. The plan files prescribe.**
