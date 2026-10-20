# Plan — one document per topic, with versions, instead of N entries saying the same thing

**Owner's ask, 2026-10-20:** *"I hate this journal append-only rule. It will add to an infinite
number of trash and outdated logs one day. Can we change it so each document can have some kind
of versioning instead? So instead of showing 4 documents talking about one thing in Sera, we can
just show 1 document, but we will say this is the fourth version."*

## The distinction this plan rests on

The complaint and the rule are aimed at two different things, and separating them is the whole
design:

- **Append-only protects the audit.** Nobody — the owner, Sera, a child session — can quietly
  rewrite what a method predicted *after* seeing how it turned out. That is the lab's central
  anti-self-deception mechanism (`docs/plans/2026-10-04-method-lab-design.md`), and it is why
  `insights_no_update` / `insights_no_delete` exist.
- **Nothing about that guarantee requires a bad reader.** Showing the owner four entries on one
  topic is not integrity, it is an unrendered chain. Entries **499 and 500 are byte-identical** —
  there is zero audit value in the owner seeing both.

**So: keep the store immutable, add a `supersedes` link, and render chains as versioned
documents.** Superseding *adds* a row; it never mutates one. The guarantee is untouched.

## Current state (measured, not assumed)

- `engine/src/seer_engine/lab/store.py:99` — `SCHEMA_VERSION = "7"`, with the migration chain
  documented inline (`2: synthesis kind; … 7: method_folds`) and `_migrate` at line 838. **This
  plan is version 8.**
- Schema today:
  ```sql
  CREATE TABLE insights (id INTEGER PRIMARY KEY AUTOINCREMENT, kind, title, body, method_id, added);
  CREATE TRIGGER insights_no_update BEFORE UPDATE ON insights
    BEGIN SELECT RAISE(ABORT, 'insights are append-only: add a newer one instead'); END;
  CREATE TRIGGER insights_no_delete BEFORE DELETE ON insights ...
  ```
- `web/data/lab.json` carries `insights: [{id, kind, title, body, …}]` alongside
  `methods`/`trials`; `tests/test_lab_snapshot.py` asserts the JSON **is** the export of the
  database, and CI fails a database commit without it. Both sides move together or neither does.
- Reader: `web/app/sera/journal/` — `view.ts` (175 lines, pure helpers, no data access),
  `page.tsx` (179), `JournalSeen.tsx`, `seen-client.ts`, `journal.module.css`, `view.test.ts`.
- There are **500 insights today**, and the newest is a duplicate of the one before it.

## The design

### 1. Schema (migration to version 8, additive)

Add **two** nullable columns:

```sql
ALTER TABLE insights ADD COLUMN supersedes INTEGER REFERENCES insights(id);
ALTER TABLE insights ADD COLUMN doc_key    TEXT;  -- "real-costs:M0260-M-G3", "prereg:M0022"
```

> **CORRECTED 2026-10-20, before any code was written.** This section originally added
> `supersedes` alone and keyed auto-linking on `method_id`. **That was wrong and would have
> destroyed measurements.** All five auto-journalling writers title on the METHOD, never the
> VARIANT (e.g. `real_costs.py:407` builds its title from `cmp.method_name` while `Comparison`
> carries `candidate_id` at line 226 and never uses it). So insights 466/467/468 — written 25 and
> 30 seconds apart, looking exactly like an accidental triple-write — are in fact three different
> arms of M0260 (`M-NATIVE` dd .238/pf 1.98, `M-G12` .256/1.62, `M-G3` .336/1.60; trials 835, 838,
> 836). Keying on `method_id` would have buried the 23.8%-drawdown arm under the 33.6% one and
> shown the owner only the last. **A measurement vanishing off the rendered page is precisely what
> append-only exists to prevent** — arriving through the front door of the feature built to
> respect it.
>
> `doc_key` is the writer-computed identity of the *document* a row is a version of. Same
> `doc_key` → supersede. Different → sibling. 466/467/468 stay three documents. §3 is
> unimplementable without it: `insights` has no column saying what produced a row or which variant
> it concerns, and `title` is the only other candidate key — which is exactly the key that fails.
> **The same bug kills the cheap alternative if it is keyed on title.**

A chain of rows linked by `supersedes` is one **document**. Its **version** is its depth in the
chain; the **head** is the row nothing supersedes. Rendering shows heads.

Invariants to enforce in `lab/store.py`, not only by convention:

- `supersedes` must reference an **existing, older** insight (`supersedes < id`). This alone makes
  cycles impossible.
- **One successor per row.** A row may be superseded at most once, or "version 4" is ambiguous.
  Enforce with `CREATE UNIQUE INDEX insights_one_successor ON insights(supersedes) WHERE supersedes IS NOT NULL;`
- A successor must share the predecessor's `method_id` (both NULL counts as shared). A chain that
  wanders between methods is not one document.
- `kind` **may** change along a chain — a `hypothesis` that becomes an `observation` is the normal
  life of a lab idea — but the change should be visible in the rendered history, not silent.

### 2. The trigger decision — SETTLED BY THE OWNER, 2026-10-20: **(a)**

> **Owner decision, 2026-10-20: go with (a).** The trigger is narrowed to protect content while
> letting `supersedes` be set once. Phase 6 (backfilling the existing duplicates, starting
> 500→499) is therefore in scope. The analysis below is kept as the record of what was weighed;
> (b) is no longer a live option.
>
> This makes the narrowed trigger the thing standing between this lab and a rewritten prediction,
> so it must be tested harder than the trigger it replaces. **Write the tests before the trigger.**
> Required cases: an UPDATE to `body` aborts; an UPDATE to `kind`/`title`/`method_id`/`added` each
> aborts; `supersedes` NULL→value succeeds exactly once; value→different value aborts; value→NULL
> aborts; **a multi-column UPDATE touching `supersedes` *and* `body` aborts** — a naive "is
> supersedes changing?" check lets the allowed column smuggle a forbidden one through; DELETE
> still aborts, unchanged.
>
> **Implement it as a WHITELIST, not a blacklist.** `supersedes` is the only column permitted to
> change, and only from NULL; every other column is named explicitly, `id` and `doc_key`
> included. This makes the smuggling case impossible *by construction* rather than by
> enumeration, and auto-protects any column added later:
>
> ```sql
> SELECT RAISE(ABORT, 'insights are append-only: add a newer one instead')
> WHERE OLD.id IS NOT NEW.id OR OLD.kind IS NOT NEW.kind OR OLD.title IS NOT NEW.title
>    OR OLD.body IS NOT NEW.body OR OLD.method_id IS NOT NEW.method_id
>    OR OLD.added IS NOT NEW.added OR OLD.doc_key IS NOT NEW.doc_key
>    OR OLD.supersedes IS NOT NULL;
> ```
>
> The last clause refuses value→different-value and value→NULL in one line. A 16-case abort suite
> in a dedicated test module, written **before** the trigger, each case re-reading the row to
> prove it is unchanged.

`insights_no_update` fires on **any** UPDATE. So **the existing 500 rows cannot be threaded
retroactively** without touching it, and 499/500 — the case that prompted this — is exactly a
retroactive thread.

Two options; the plan recommends (a), but this is the owner's call and must be settled before
code is written:

- **(a) Narrow the trigger to protect content, and let the link be set once.** Abort any UPDATE
  that changes `kind`, `title`, `body`, `method_id` or `added`; allow `supersedes` to go from
  `NULL` to a value exactly once, never from a value to another value or back to `NULL`.
  *Content stays immutable — only the thread between rows is added.* This permits backfilling the
  existing duplicates and is the only option that fixes today's mess.
- **(b) Leave the trigger absolutely as-is.** Only newly written rows can carry a link; 499/500
  and every past duplicate stay unthreaded forever. Strictly safer, and it leaves the owner's
  actual complaint half-unaddressed.

If (a): the narrowed trigger is itself a guarantee that must be tested harder than the old one —
a test that an UPDATE to `body` still aborts is the single most important test in this change.

### 3. Writer

- `lab insight --supersedes <id>` on the CLI, validated against every invariant above, exit 2 on
  violation (the lab's "refused by the rules" code), never exit 1.
- **Auto-journalling commands link automatically — by `doc_key`, NEVER by `method_id` or
  `title`.** Each writer computes a `doc_key` that includes the **variant** it is reporting on
  (`"real-costs:M0260-M-G3"`), looks for its own most recent head with that exact key, and
  supersedes it. Rows with different keys stay siblings. **This is the 499/500 fix**, and keyed
  this way it stops the pile-up growing without collapsing distinct arms. Keying it any other way
  is the bug described in §1 — re-read that box before implementing this.
- A `--no-supersede` escape for the case where a genuinely new observation happens to share a
  method.

### 4. Export and reader

- `lab stage` emits `supersedes` plus a derived `version` and `supersededBy` on each insight, so
  `view.ts` stays a pure helper with no graph-walking in the component.
- `/sera/journal` renders **heads only**, labelled *"version 4"*, with earlier versions behind a
  disclosure. Follow the Seer v2 design: icon-only button, `aria-label`, tooltip.
- `kindCounts` and the journal's filters count **documents, not rows** — otherwise the owner's
  counts still inflate with every re-run, which is the complaint restated.

### 5. Seen-state — a real interaction, easy to get wrong

`seen-client.ts` keys on insight **id**. If a document gains a version, its head id changes, so
the document correctly reappears as unseen. That is the behaviour we want (the owner should see
that a conclusion was revised) — **but it must be deliberate and tested**, not an accident, and
the UI should say *"revised"* rather than presenting it as brand new.

### 6. What must NOT be collapsed

Method `analysis` and `verdict` are a different case from journal observations. That is where
"you said X before the run and Y after" lives, and it is load-bearing: today's M0261 correction
is only legible *because* the withdrawn 3.21 sits beside the corrected ~1.1. **Keep version
chains on analysis and verdict visible by default**; collapse journal observations and
auto-written survivorship notes. If this plan grows to cover `analysis`, that distinction is the
first thing to re-argue.

## Phases

| # | What | Depends on |
|---|---|---|
| 1 | ~~Settle the trigger decision.~~ **DONE 2026-10-20: owner chose (a).** | — |
| 2 | Schema 8: column, invariants, unique index, trigger change if (a). Tests first, especially "UPDATE to body still aborts". | 1 |
| 3 | Writer: `--supersedes`, validation, and auto-linking in `lab survivorship`. | 2 |
| 4 | Export: `lab stage` emits `supersedes`/`version`; snapshot test moves with it. | 2 |
| 5 | Reader: heads-only journal with version label and history disclosure; counts by document. | 4 |
| 6 | Backfill **exactly 5 pairs**, not 12. **In scope** under (a). | 2, 3 |

**The backfill list is settled and needs no judgment** — all five are byte-identical in title
*and* body: `227→230` (M0131), `289→290` (M0024), `493→498` (M0127), `320→499` (M0179),
`499→500` (M0179). Twelve rows share a title with an earlier row, but only these five are
true duplicates; the other seven are different arms under one generated title and **stay
siblings**.

**Also: insight 126 already supersedes 125 — in prose, inside its own body** ("*This replaces the
entry just before it, which miscounted the pairs as 20…*"). The relation exists in this journal
today and is hand-written because the schema has nowhere to put it. That is the strongest single
argument that this feature is worth building.

**Still open, and the owner wants a straight answer:** whether the *cheap alternative* — just
teaching auto-journalling commands to supersede their own previous note instead of appending a
sibling — solves enough of the complaint on its own. Choosing (a) does not pre-commit to building
all six phases. If phases 1–3 plus that fix already give one document per topic, and 4–6 are
gold-plating, say so rather than building them by default.

## Traps specific to this repo

- `lab stage` **then** test. `test_lab_snapshot.py` is red by design until the JSON is regenerated.
- Commit the lab **by index** (`git commit -m …`), never by pathspec — a pathspec re-reads the
  working tree and defeats `lab stage`.
- `web/` mirrors some engine constants and a test asserts they match. If this change adds one,
  change both sides.
- **Closed records are frozen.** This plan threads rows together; it must not reformat or re-word
  a single existing `body`.
- Every `lab stage` commit includes `web/data/lab.json`. CI fails a database commit without it,
  and Vercel redeploys `/sera` from each push to `main`.
- Parallel sessions share `lab.sqlite` through `SEER_LAB_DB`; a migration takes the write lock,
  so run it when no child session is mid-write.

## Out of scope

Deleting anything; editing any existing `body`; changing what `methods.analysis`'s append-only
trigger does; and feature-wish 492 (the opinion-value report), which is a separate "make the lab
readable" item that would pair well afterwards.
