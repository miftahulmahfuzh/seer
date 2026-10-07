> Adopted from `JOURNAL_UNSEEN_BADGES_PLAN.md` phase 1. Source: `.workflows/plan/journal-unseen-badges/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Seen-state storage, server read/write, and the POST endpoint

**Plan set:** `JOURNAL_UNSEEN_BADGES_PLAN.md`
**Analysis:** `20261007-103957-J4N8_code_analyzer.md`
**Satisfies:** R2 — a working definition and mechanism for "seen". This phase builds the half of
R2 that persists and accepts the marking; phase 4 builds the half that decides *when* to mark.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `db/migrations`, `web/lib/sera`, `web/app/api/sera`

---

## Goal

After this phase Seer can remember which `LabInsight.id`s the reader has already looked at, and a
browser can tell it about new ones. Three new files exist and nothing in the app calls any of
them yet: a `journal_seen` table in Neon, a server-only read/write module over it, and a `POST`
endpoint gated exactly the way `/sera` is gated but answering in status codes instead of
redirects. Phases 3, 4 and 5 consume the contract fixed here.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none
**Renames:** none

**Creates — database:**
- table `journal_seen` (`db/migrations/012_journal_seen.sql`), columns
  `insight_id bigint PRIMARY KEY`, `seen_at timestamptz NOT NULL DEFAULT now()`,
  `via text NOT NULL DEFAULT 'view' CHECK (via IN ('view','click'))`. No foreign key. No user
  column. Insert-only.
- migration file name `012_journal_seen.sql` — claims the `012` slot in `db/migrations/`.

**Creates — `web/lib/sera/seen.ts` (new, server only; imports `@/lib/db`):**

```ts
export type SeenVia = 'view' | 'click';
export const MAX_SEEN_BATCH = 500;
export async function seenInsightIds(): Promise<Set<number>>;
export async function unseenCount(insightIds: Iterable<number>): Promise<number | null>;
export function normalizeSeenIds(raw: unknown): number[] | null;
export function parseSeenVia(raw: unknown): SeenVia | null;
export async function markInsightsSeen(ids: number[], via: SeenVia): Promise<number>;
```

Behaviour the other phases may rely on:

- `seenInsightIds()` **never throws**. An unreachable database and an empty table both give
  `new Set()`, i.e. "nothing seen yet" (invariant 9). It logs with `console.error` on failure.
  This is the function **phase 3** awaits in `page.tsx`.
- `unseenCount(ids)` returns how many of `ids` are *not* in the table, or `null` when the read
  failed. **This is phase 5's call, and it is the only one phase 5 makes:** the Sera layout does
  `await unseenCount(lab.insights.map(i => i.id))` and renders no badge when the result is `null`
  or `0`. It deliberately does **not** import `lib/sera/lab` itself, so the API route's bundle
  stays free of the 0.89 MB snapshot; the caller supplies the ids.

  > **The two readers are not duplicates — keep both.** `seenInsightIds()` answers *which*
  > entries are seen, as a whole set, which is what `/sera/journal` needs to partition the lists
  > and tally per kind (phase 3). `unseenCount(ids)` answers *how many of these are unseen, and
  > did the read work* — one number plus a `null`, which is what the Sera rail needs (phase 5).
  > The `null` is the load-bearing difference: invariant 9 asks a failed read to degrade, and
  > phase 5's exit criterion is **no badge** on failure, which an empty `Set` cannot express —
  > it is indistinguishable from a clean read of an empty table. A third function,
  > `unseenCounts(insights, seen)`, lives in phase 2's pure `view.ts` and touches no database at
  > all; it is the per-kind tally over a set the caller already holds. Three questions, three
  > functions, no redundancy.
- `markInsightsSeen` is idempotent and additive: one `INSERT … ON CONFLICT (insight_id) DO
  NOTHING`, so a repeat marking leaves the original `seen_at`/`via` untouched and nothing is ever
  un-seen (invariant 6). It **throws** when the write fails; the route turns that into `500`.
- `normalizeSeenIds` / `parseSeenVia` are the shared input guard; the route holds no validation
  of its own.

**Creates — `web/app/api/sera/journal/seen/route.ts` (new). The wire contract phase 4 codes against:**

| | |
|---|---|
| Method / path | `POST /api/sera/journal/seen` |
| Request body | `{"ids": number[], "via"?: "view" \| "click"}` — JSON text. **Content-Type is ignored**: the handler reads `await req.text()` and `JSON.parse`s it, so a `navigator.sendBeacon` `Blob` of type `text/plain;charset=UTF-8` is accepted exactly like `application/json`. `text/plain` is the type phase 4 should use for the beacon — it is the one every browser allows without a preflight. |
| `ids` | non-empty, at most **500** entries, every entry a positive safe integer. Duplicates are tolerated and collapsed server-side. |
| `via` | optional; omitted means `"view"`. Any other value is a `400`. |
| `204 No Content`, empty body | success. The only success code. |
| `400 Bad Request`, empty body | body is not JSON, is not an object, or `ids`/`via` fail the guard. |
| `404 Not Found`, empty body | caller fails the `/sera` gate (signed out, outside `ALLOWED_EMAIL`, or not `SERA_EMAIL`). Nothing in the response reveals that the section exists (invariant 7). |
| `500`, empty body | the Neon write failed. |
| Response body | **never** carries anything. Phase 4 must not read it — `sendBeacon` cannot see a response at all. |
| Other methods | not exported; Next answers `405`. |

**Requires (from earlier phases):** nothing. This phase has no dependencies.

**Leaves alone (owned by others):**
- `web/app/sera/journal/*` — `view.ts`, `view.test.ts` (Phase 2); `page.tsx`,
  `journal.module.css` (Phase 3); `JournalSeen.tsx`, `seen-client.ts`, `seen-client.test.ts`
  (Phase 4).
- `web/app/sera/layout.tsx`, `web/components/sera/SeraNav.tsx`, `SeraNav.module.css`,
  `web/package_readme.md` (Phase 5).
- `web/lib/data.ts`, `web/lib/sera/lab.ts`, `web/lib/sera/gate.ts`, `web/data/lab.json`,
  `engine/**` — untouched by this phase.

## Files

| File | Action | What changes |
|---|---|---|
| `db/migrations/012_journal_seen.sql` | create (new, line 1) | the `journal_seen` table; next free number after `011_rmw.sql` |
| `web/lib/sera/seen.ts` | create (new, line 1) | server-only read/write over `journal_seen` plus the shared input guard |
| `web/app/api/sera/journal/seen/route.ts` | create (new, line 1) | the gated `POST` handler the client island beacons to |

No existing file is modified. Verified against the tree: `db/migrations/` holds `001`–`011`
(`011_rmw.sql` highest), `web/lib/sera/` has no `seen.ts`, and `web/app/api/` holds only
`auth/[...nextauth]/route.ts`.

## Implementation Steps

### Step 1: The migration

**File:** `db/migrations/012_journal_seen.sql` (new file, whole contents)

**Change:** add the table. Header-comment style copied from `008_book_kickoff.sql` and
`009_evidence.sql` — a short "Seer schema vN:" line, then the reasoning. `CREATE TABLE IF NOT
EXISTS`, like every other table in `db/migrations`, so `engine/tests/test_migrate.py`'s
apply-twice assertions hold.

**Code:**

```sql
-- Seer schema v12: which Journal entries the reader has already seen (/sera/journal badges).
--
-- The seven badges on /sera/journal counted how many entries of each kind EXIST -- a number that
-- only ever grows, because the lab is append-only. They now count how many are NEW to the reader,
-- which needs somewhere to remember what has already been looked at.
--
-- insight_id is `insights.id` from the engine's SQLite lab store
-- (engine/src/seer_engine/lab/store.py), carried verbatim into web/data/lab.json. That table is
-- append-only by construction: the insights_no_update and insights_no_delete triggers RAISE(ABORT)
-- on any UPDATE or DELETE, so an id, once issued, names the same insight forever and is never
-- reused. There is therefore NO foreign key here -- the insights themselves do not live in
-- Postgres, and there is nothing to cascade from. An id with no matching insight (a snapshot
-- rolled back by hand, say) is simply ignored by the reader.
--
-- No user column, for the same reason action_dismissals (001_init.sql) has none: Seer is private
-- to one Google account (web/lib/allow.ts) and /sera to one narrower still (web/lib/sera/access.ts).
--
-- via records HOW the entry was marked: 'click' when the reader opened the method behind the
-- card's redirect arrow, 'view' when the card simply dwelled on screen in a visible tab.
-- Diagnostics only -- nothing reads it to decide seen-ness. A row existing is what "seen" means.
--
-- Rows are only ever inserted, never updated or deleted: the first marking wins and a repeat is an
-- ON CONFLICT DO NOTHING no-op (web/lib/sera/seen.ts markInsightsSeen). Nothing in this plan set
-- marks an entry unseen.
CREATE TABLE IF NOT EXISTS journal_seen (
  insight_id  bigint PRIMARY KEY,
  seen_at     timestamptz NOT NULL DEFAULT now(),
  via         text NOT NULL DEFAULT 'view' CHECK (via IN ('view', 'click'))
);
```

**Impact:** `web/scripts/migrate.mjs` applies it once inside a transaction on the next
`npm run db:migrate`; the engine's `python -m seer_engine migrate` applies it from the same
`schema_migrations` table. `engine/tests/test_migrate.py` needs **no edit**: its `ALL` constant is
derived at import time (`test_migrate.py:16`, `[p.name for p in migration_files(MIGRATIONS_DIR)]`),
`test_repo_has_001_to_004` only pins the first four names, and every `_tables(...)` assertion is a
subset check (`<=`) or an unrelated equality — verified by reading the file.

### Step 2: The server read/write module

**File:** `web/lib/sera/seen.ts` (new file, whole contents)

**Change:** two Neon calls and the input guard they share. Tagged-template style and the
`ON CONFLICT DO NOTHING` idempotence are lifted from `dismissAction` (`web/lib/data.ts:479`). Kept
in `lib/sera/` rather than `lib/data.ts` because `data.ts` is the `(app)` read model and Sera has
its own namespace.

Two implementation notes worth keeping when you type it:

- **The multi-row insert goes through `jsonb`, not a Postgres array parameter.** Nothing in this
  repo passes an array to `sql` today (checked `lib/data.ts` and `scripts/`), so there is no
  precedent proving how `@neondatabase/serverless` serialises one over its HTTP protocol. A single
  JSON **string** parameter with an explicit `::jsonb` cast is unambiguous for any driver.
- **`bigint` comes back from the driver as a string.** `Number(r.insight_id)` is required, and is
  the same `n = (v: unknown) => Number(v)` habit `lib/data.ts:14` already uses.

**Code:**

```ts
/**
 * Reader state for /sera/journal: which lab insights have already been seen.
 *
 * Server only -- it opens the Neon connection from lib/db. Never import it from a client
 * component, and never from app/sera/journal/view.ts: that module stays pure and takes the seen
 * set as a plain `ReadonlySet<number>` parameter (plan invariant 3).
 *
 * Lab FACTS still come only from the committed snapshot (lib/sera/lab.ts). Which entries the
 * reader has seen is the one Sera thing that lives in Postgres, because it is state about the
 * reader, not about the lab.
 */
import { sql } from '@/lib/db';

/** How an entry came to be marked seen. Mirrors journal_seen.via's CHECK (012_journal_seen.sql). */
export type SeenVia = 'view' | 'click';

/**
 * The most ids one POST may carry. The whole Journal is 26 entries today and a reader cannot
 * dwell on more than a screenful at a time, so this is a guard against a malformed or hostile
 * body, not a working limit.
 *
 * PAIRED WITH MAX_BATCH in app/sera/journal/seen-client.ts (50), which is the client's own,
 * smaller cap on one flush. The invariant between them is MAX_BATCH <= MAX_SEEN_BATCH; 50 <= 500
 * holds with room to spare. They cannot share a constant -- this module is server-only and builds
 * the Neon client at module scope, so the island cannot import it -- so if either number changes,
 * check the other. A client cap above this one turns every full flush into a silent 400: the
 * route returns no body and the island swallows failures, so nothing would surface it.
 */
export const MAX_SEEN_BATCH = 500;

/** Every seen id. Throws when Postgres is unreachable; the exported readers below catch. */
async function fetchSeenIds(): Promise<Set<number>> {
  // insight_id is bigint, which the driver returns as a string: Number() it, like lib/data.ts.
  const rows = await sql`SELECT insight_id FROM journal_seen`;
  return new Set<number>(rows.map(r => Number(r.insight_id)));
}

/**
 * Every insight id marked seen, as a set the view layer can probe.
 *
 * Never throws (plan invariant 9). An empty table and an unreachable database both read as
 * "nothing seen yet", so the Journal renders with every entry unseen rather than 500ing because
 * Neon is down.
 */
export async function seenInsightIds(): Promise<Set<number>> {
  try {
    return await fetchSeenIds();
  } catch (e) {
    console.error('journal_seen read failed; treating every entry as unseen', e);
    return new Set<number>();
  }
}

/**
 * How many of `insightIds` are NOT yet seen, or `null` when the read failed.
 *
 * The caller passes the ids rather than this module reaching for the snapshot, so that importing
 * it from the API route does not drag web/data/lab.json (0.89 MB) into that route's bundle.
 * `null` lets the Sera rail show no badge at all rather than a number it cannot stand behind.
 */
export async function unseenCount(insightIds: Iterable<number>): Promise<number | null> {
  let seen: Set<number>;
  try {
    seen = await fetchSeenIds();
  } catch (e) {
    console.error('journal_seen read failed; no unseen count', e);
    return null;
  }
  let n = 0;
  for (const id of insightIds) if (!seen.has(id)) n += 1;
  return n;
}

/**
 * The `ids` of a POST body, cleaned: positive safe integers only, deduplicated, order preserved.
 * Returns null when the input is not an array, is empty, holds anything that is not an id, or is
 * longer than MAX_SEEN_BATCH -- all of which the route answers with 400.
 *
 * Safe integers only because insight_id is a bigint column read back through JS numbers; an id
 * past 2^53-1 could not survive the round trip, and the lab is at id 26.
 */
export function normalizeSeenIds(raw: unknown): number[] | null {
  if (!Array.isArray(raw) || raw.length === 0 || raw.length > MAX_SEEN_BATCH) return null;
  const out: number[] = [];
  const got = new Set<number>();
  for (const v of raw) {
    if (typeof v !== 'number' || !Number.isSafeInteger(v) || v <= 0) return null;
    if (got.has(v)) continue;
    got.add(v);
    out.push(v);
  }
  return out.length === 0 ? null : out;
}

/**
 * The `via` of a POST body. Absent (or null) means 'view', the ordinary case; anything that is
 * not one of the two the CHECK constraint allows returns null, which the route answers with 400.
 */
export function parseSeenVia(raw: unknown): SeenVia | null {
  if (raw === undefined || raw === null) return 'view';
  return raw === 'view' || raw === 'click' ? raw : null;
}

/**
 * Marks `ids` seen, idempotently: a row that already exists is left exactly as it was, so the
 * first marking's seen_at and via win and nothing is ever un-seen (plan invariant 6). Returns how
 * many rows were new.
 *
 * `ids` must already have been through normalizeSeenIds. Throws when the write fails -- the route
 * turns that into a 500 and the client island simply keeps the ids queued for its next flush.
 *
 * The ids travel as one JSON string parameter rather than a Postgres array: nothing else in this
 * app passes an array to the Neon driver, and a string with an explicit ::jsonb cast needs no
 * assumption about how the HTTP protocol serialises one.
 */
export async function markInsightsSeen(ids: number[], via: SeenVia): Promise<number> {
  if (ids.length === 0) return 0;
  const rows = await sql`
    INSERT INTO journal_seen (insight_id, via)
    SELECT value::bigint, ${via}
      FROM jsonb_array_elements_text(${JSON.stringify(ids)}::jsonb) AS t(value)
    ON CONFLICT (insight_id) DO NOTHING
    RETURNING insight_id
  `;
  return rows.length;
}
```

**Impact:** nothing imports this module yet, so nothing changes at runtime. It adds one `@/lib/db`
importer; `DATABASE_URL` is already required by the whole `(app)` section, so no new environment
variable. It is not unit-tested — see **Handoffs**.

### Step 3: The POST route

**File:** `web/app/api/sera/journal/seen/route.ts` (new file, whole contents; creates the
directories `web/app/api/sera/`, `journal/` and `seen/`)

**Change:** the endpoint. It reproduces `requireSera`'s rule from the same two predicates
(`isAllowed` + `isSeraUser`) rather than re-deriving it, but cannot call `requireSera` itself:
`redirect()` and `notFound()` throw Next navigation signals, which produce a `307` and an HTML
404 page — wrong answers for a beacon, and the `307` to `/signin` would leak that the section is
there. A bare `404` with no body is the right reply to everything that fails the gate.

**Code:**

```ts
import { auth } from '@/auth';
import { isAllowed } from '@/lib/allow';
import { isSeraUser } from '@/lib/sera/access';
import { markInsightsSeen, normalizeSeenIds, parseSeenVia } from '@/lib/sera/seen';

// Reads cookies and writes a row: never cached, never prerendered. Matches the convention the
// app/(app) pages follow once they touch Neon.
export const dynamic = 'force-dynamic';

/** Every answer this route gives is a status code and nothing else. */
const empty = (status: number) => new Response(null, { status });

/**
 * The /sera gate, in status-code form. Exactly the rule lib/sera/gate.ts's requireSera applies --
 * signed in, inside ALLOWED_EMAIL, and SERA_EMAIL -- read from the same two predicates so the two
 * cannot drift. requireSera itself is unusable here: its redirect()/notFound() are navigation
 * responses, and a 307 to /signin would tell a stranger the section exists (plan invariant 7).
 */
async function isSeraCaller(): Promise<boolean> {
  const session = await auth();
  const email = session?.user?.email;
  return isAllowed(email, process.env.ALLOWED_EMAIL) && isSeraUser(email);
}

/**
 * POST /api/sera/journal/seen -- mark Journal entries seen.
 *
 * Body: {"ids": number[], "via"?: "view" | "click"}, at most 500 ids, each a positive integer.
 * "via" defaults to "view". Answers 204 on success, 400 on a malformed body, 404 to anyone the
 * /sera gate rejects, 500 when the write fails. The response never carries a body: the client
 * flushes this with navigator.sendBeacon, which cannot read one.
 *
 * The body is read as text and parsed by hand rather than with req.json(): sendBeacon sends a
 * Blob, so the Content-Type on the wire is whatever that Blob was built with (text/plain is the
 * type every browser permits without a preflight). Content-Type is therefore ignored entirely,
 * and one try/catch covers every way the payload can fail to be JSON.
 */
export async function POST(req: Request) {
  if (!(await isSeraCaller())) return empty(404);

  let body: unknown;
  try {
    body = JSON.parse(await req.text());
  } catch {
    return empty(400);
  }
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return empty(400);

  const ids = normalizeSeenIds((body as { ids?: unknown }).ids);
  const via = parseSeenVia((body as { via?: unknown }).via);
  if (!ids || !via) return empty(400);

  try {
    await markInsightsSeen(ids, via);
  } catch (e) {
    // Marking seen is soft state. Log it and let the client requeue; never make the reader care.
    console.error('journal_seen write failed', e);
    return empty(500);
  }
  return empty(204);
}
```

**Impact:** adds one route to the build. No other method is exported, so `GET`/`DELETE` on the path
get Next's automatic `405`. Nothing calls it until phase 4.

## Verification

Run everything from the worktree, `/home/miftah/.worktrees/seer/journal-unseen-badges`.

`web/node_modules` here is already a symlink to `/home/miftah/seer/web/node_modules`
(`package.json` and `package-lock.json` are byte-identical to the base commit), and
`npx tsc --noEmit` is confirmed clean on the base tree. **Do not run `npm ci` or `npm install`.**

**Build / typecheck:**

```
cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npx tsc --noEmit
```

**Tests (web):**

```
cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npx vitest run
```

This phase adds no vitest file; the existing suite must stay green and untouched. (The repo has
no `vitest.config.*` anywhere and every existing test imports by **relative** path — `@/` does not
resolve under vitest — so a test over `seen.ts`, which imports `@/lib/db`, could not run even if
written. See **Handoffs**.)

**Tests (migrations, needs Postgres):**

```
cd /home/miftah/.worktrees/seer/journal-unseen-badges && \
  PYTHONPATH=/home/miftah/.worktrees/seer/journal-unseen-badges/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_migrate.py -q
```

(The shared swarm worktree has no `engine/.venv`; the main checkout's venv plus `PYTHONPATH`
shadows the editable install.) `test_applies_all_then_nothing` must list `012_journal_seen.sql`
last in `schema_migrations` and report nothing on a second pass.

**Manual check:**

1. `cd web && npm run db:migrate` — prints `apply 012_journal_seen.sql`; run it a second time and
   it prints `skip 012_journal_seen.sql`.
2. `\d journal_seen` in psql shows the three columns, the primary key, and the `via` check.
3. `npm run dev`, then signed in as the Sera account:
   `curl -i -X POST localhost:3000/api/sera/journal/seen -H 'content-type: text/plain' --data '{"ids":[1,2],"via":"view"}' -b "<session cookie>"`
   → `204`; repeat it → still `204`, and `SELECT count(*) FROM journal_seen` stays at 2.
4. The same `curl` with no cookie → `404` and an empty body.
5. `--data '{"ids":[]}'`, `--data '{"ids":[0]}'`, `--data '{"ids":["1"]}'`, `--data 'nonsense'`,
   `--data '{"ids":[1],"via":"peeked"}'` → `400` each.
6. `/sera/journal` renders exactly as it does today — nothing reads the table yet.

**Exit criteria:**

- `012_journal_seen.sql` applies cleanly on top of `011_rmw.sql` and is a no-op on a second apply.
- `seenInsightIds()` gives an empty `Set` against an empty table and against an unreachable
  database, and never throws.
- `markInsightsSeen` is idempotent: the same ids twice leave one row each, with the first
  `seen_at`/`via`.
- `POST /api/sera/journal/seen` answers `204` for the Sera user, `404` for everyone else, `400`
  for a body that is not `{ids: number[]}`, and never returns a body.
- Nothing in the app calls any of it; `npx tsc --noEmit && npx vitest run` are both clean.

**Commit path allowlist** (the swarm shares one worktree — stage these three paths explicitly,
never `git add -A`, and check the commit's file list equals exactly this):

```
db/migrations/012_journal_seen.sql
web/lib/sera/seen.ts
web/app/api/sera/journal/seen/route.ts
```

## Handoffs

- **Phase 3** calls `await seenInsightIds()` in `page.tsx` and hands the resulting
  `Set<number>` to phase 2's `journalGroups`/unseen-count helpers as a `ReadonlySet<number>`.
  It also needs `export const dynamic = 'force-dynamic'` on `page.tsx` — that is phase 3's edit,
  not mine; I do not touch any file under `web/app/sera/journal/`. **No double-add:** this phase
  declares its own `force-dynamic` only inside `web/app/api/sera/journal/seen/route.ts`, a file
  phase 3 never opens, and phase 3 declares one only in `page.tsx`, a file this phase never
  opens. Two files, one declaration each.
- **Phase 4** is the only caller of the route. The wire contract above is fixed and complete:
  `POST /api/sera/journal/seen`, `{"ids": number[], "via"?: "view" | "click"}`, ≤ 500 ids,
  `text/plain;charset=UTF-8` Blob for `sendBeacon`, `204` on success, no response body ever. Its
  batch cap in `seen-client.ts` is `MAX_BATCH = 50`, which must stay ≤ this module's
  `MAX_SEEN_BATCH = 500`. It cannot `import { MAX_SEEN_BATCH }` — this module is server-only and
  pulls in the Neon client — so the number is restated there, and **both sides carry a comment
  naming the other**. Checked by the reconciler: 50 ≤ 500, with room to spare; phase 4's
  verification re-greps the pair.
- **Phase 5** uses `unseenCount(lab.insights.map(i => i.id))` in `web/app/sera/layout.tsx` and
  renders no rail badge when it returns `null` (read failed) or `0`. That is this phase's answer to
  the question "should `seen.ts` export an unseen total" — yes, as a function taking the ids, so
  the API route's bundle never pulls `web/data/lab.json`. The layout does not import `lab` today;
  phase 5 adds that import. **Phase 5 does not call `seenInsightIds`** — reconciled: only
  `unseenCount`'s `null` can distinguish a failed read from a clean zero, which is what
  invariant 9 and phase 5's "no badge on failure" criterion require.
- **No unit test for `seen.ts`.** The repo has no `vitest.config.*` and every existing suite
  imports by relative path, so `@/lib/db` does not resolve under vitest; `seen.ts` also builds the
  Neon client at module scope. `normalizeSeenIds` and `parseSeenVia` are pure and would be worth
  covering, but doing so needs a vitest `resolve.alias` for `@/` — a repo-wide change that belongs
  to no phase in this set. Leaving it to a follow-up card; the manual `curl` matrix in
  **Verification** covers the same ground for now.
- **`journal_seen` is deliberately *not* added to `DEMO_TABLES`** (`engine/src/seer_engine/demo.py:34`).
  That list is for tables the demo seed writes, and the demo seed never touches reader state; a
  purge must not wipe what the owner has read. No phase in this set should add it.
- **No `server-only` import guard.** The `server-only` package is not in `web/package.json`;
  adding a dependency is out of scope for this phase. The module header comment carries the rule
  instead, the way `lib/sera/lab.ts:1-4` already does.
- **R3 (badge counts) and R1 (ordering) are not served here.** `unseenCount` exists only because
  phase 5 needs one number from this module; the counting and partitioning that R1/R3 require
  belong to phase 2's pure view layer.

## Rollback

`git revert` this phase's single commit. That removes the three new files; nothing else in the
tree referenced them, so the build and the test suite return to their pre-phase state untouched.

The out-of-tree artefact is the table. To remove it too:

```sql
DROP TABLE IF EXISTS journal_seen;
DELETE FROM schema_migrations WHERE name = '012_journal_seen.sql';
```

Nothing else in the schema references `journal_seen`, so the drop is safe in any order. Leaving
the table in place after a revert costs nothing and makes a re-land cheap — the migration runner
will skip the file if the `schema_migrations` row is left behind, so delete that row whenever the
table is dropped.
