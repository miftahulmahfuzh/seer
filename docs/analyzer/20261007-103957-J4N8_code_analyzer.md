# Code Analysis: Sera Journal unseen-item notifications

**Type:** Feature Update
**Date:** 2026-10-07 10:39:57 +07
**Session ID:** 20261007-103957-J4N8
**Plan:** `JOURNAL_UNSEEN_BADGES_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/seer/journal-unseen-badges` — branch `feature/journal-unseen-badges` (base `origin/main` @ `46c04b4`)

---

## User Input

### Original User Request

> we need to update how https://seertrade.site/sera/journal works.
> we show seven icons tab, with notification-like numbers at the top corner of each icons.
> i like this. but , we need to fix how these notification actually works.
>
> requirement:
> i imagine the system to work like this:
> - we will keep trying new methods, and Journal will keep finding new information, new things to share with me. so,
> - for every tab content, we put the "seen" items down. so only unseen items being put at the top, and sort this unseen items based on the most recent ones to the oldest.
> - we need to think of a way to determine , which items is considered "seen" . for example, some items can be clicked (there is a redirect-arrow button). so if the items has been clicked , then it means it has been seen. but we need to think / determine a way for items that can't be clicked. maybe if we have a way to know that user has opened this tab and show this item on the screen?
>
> > [!IMPORTANT]
> > bottom line is, i hope this notification can work correctly, it really shows the unseen items count per tab, so user can have some kind of "excitement" if they see a new notification number on a tab icon.

### User-Provided Context

No error messages or logs. The page named is `https://seertrade.site/sera/journal`, which is
`web/app/sera/journal/page.tsx` in this repo.

### User-Provided Files

None marked with `@`. The target was identified from the URL.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Within every tab's content, unseen items sit at the top sorted newest-to-oldest, and seen items are pushed down below them |
| R2 | A working definition and mechanism for "seen": a click on an item's redirect-arrow marks it seen, and items with no arrow are marked seen some other way — e.g. the user opened that tab and the item was shown on screen |
| R3 | The notification number on each of the seven tab icons is the true count of *unseen* items for that tab, so a new number on a tab is a real signal worth getting excited about |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement**

`/sera/journal` renders a seven-icon segmented bar (`all` + the six `InsightKind`s). Each icon
carries a badge. Today that badge is `kindCounts(lab.insights)[kind]` — the *total* number of
insights of that kind in the bundled snapshot, and `total` for the `all` icon. It never changes
in response to anything the user does, so it is a static inventory count dressed as a
notification. Below the bar, each kind's `Section` lists its entries sorted strictly
`newestFirst` with no notion of read state.

The lab is append-only and keeps growing (`engine/src/seer_engine/lab/store.py` puts
`insights_no_update` and `insights_no_delete` triggers on the table), so the number on a tab
only ever grows. The user wants it to mean "how many of these have you not looked at yet",
which requires (a) somewhere to persist per-item read state, (b) a rule for when an item becomes
read, and (c) a sort and a count derived from that state.

**Success Criteria**

- Each of the seven badges shows the number of unseen entries for that tab; the `all` badge is
  the total unseen across all six kinds.
- A badge that reaches zero renders in the existing muted `.badge.zero` style.
- Within each kind's section, unseen entries come first (newest `added` first, ties by higher
  `id`), then seen entries (same ordering), with a visible boundary between the two groups.
- Clicking an entry's redirect-arrow marks that entry seen.
- An entry that has no arrow becomes seen by being displayed on screen, in an open and visible
  tab, for long enough to have been read past rather than merely scrolled through.
- Read state survives a reload and is the same on every device (it is one account).
- The ordering shown on a page does **not** reshuffle under the reader while they are reading it.

**Key Considerations**

- *One account.* `lib/allow.ts` locks Seer to a single Google address and `lib/sera/access.ts`
  narrows `/sera` further to `SERA_EMAIL`. There is exactly one reader, so seen-state needs no
  user column — the same decision `action_dismissals` already made (`db/migrations/001_init.sql:81`).
- *Stable keys.* `LabInsight.id` is a SQLite `AUTOINCREMENT` primary key on an append-only table,
  carried verbatim into `data/lab.json`. It never changes and never gets reused, so it is a safe
  key for seen-state held in a different database.
- *Sera reads JSON, not Neon.* `web/package_readme.md` states Sera is a read model over the
  committed `data/lab.json`, "not from Neon". Seen-state is **reader** state, not lab data, so
  storing it in Neon does not put lab facts in two places; the statement in the readme needs a
  sentence added rather than a correction.
- *Nothing marks state on the server for free.* The page is a React Server Component. Marking
  "this was on screen" is inherently a browser event, so the page needs a client island and an
  endpoint it can POST to.
- *Freeze the order per page view.* The partition must be computed once, at render, from the
  seen-set as it stood when the page loaded. If an item re-sorted the moment it was marked seen,
  cards would jump out from under the cursor.
- *First run shows everything unseen.* With an empty `journal_seen` table all 26 current
  insights are unseen, so the first load after deploy shows 26 on `all`. That is the correct
  reading of the model, not a bug.
- *Caching.* Sera pages carry no `export const dynamic`; they are already dynamic because
  `requireSera()` reads cookies via `auth()`. The `(app)` pages that read Neon all declare
  `export const dynamic = 'force-dynamic'` explicitly, so the journal page should match that
  convention once it reads a table.

---

## Analysis Scope

### Explicitly Mentioned Files

None (the target was given as a URL).

### Discovered Related Files

- `web/app/sera/journal/page.tsx` — the page; renders the seven-icon bar and the per-kind sections
- `web/app/sera/journal/view.ts` — pure helpers: `parseKind`, `journalHref`, `newestFirst`, `kindCounts`, `journalGroups`, `dayLabel`
- `web/app/sera/journal/view.test.ts` — the vitest suite over those helpers
- `web/app/sera/journal/journal.module.css` — `.bar`, `.segBtn`, `.badge`, `.badge.zero`, `.cards`, `.card`, `.cardFoot`
- `web/lib/sera/types.ts` — `LabInsight`, `InsightKind`, `INSIGHT_KINDS`, `LabSnapshot`
- `web/lib/sera/lab.ts` — `lab` (the bundled snapshot), `methodById`
- `web/lib/sera/glossary.ts` — `INSIGHT_KIND_LABEL`
- `web/lib/sera/gate.ts` — `requireSera(next)`
- `web/lib/sera/access.ts` — `SERA_EMAIL`, `isSeraUser`
- `web/lib/allow.ts` — `isAllowed` (one account)
- `web/lib/db.ts` — `sql = neon(DATABASE_URL)`
- `web/lib/data.ts:479` — `dismissAction(orderId)`, the only existing web→Neon write
- `web/app/(app)/actions.ts` — `dismiss(formData)`, the server-action precedent
- `web/app/sera/layout.tsx` — the Sera shell; renders `SeraNav`
- `web/components/sera/SeraNav.tsx` — the client rail with the Journal tab
- `web/components/sera/SeraNav.module.css` — rail styles
- `web/components/sera/Section.tsx` — the per-kind sheet
- `web/components/TooltipLayer.tsx`, `web/components/tooltip.ts` — a delegated `data-tip` layer, so client/server split does not affect tooltips
- `web/app/globals.css:147-184` — `.icon-btn`, `.seg`
- `db/migrations/001_init.sql:81` — `action_dismissals`, the shape to copy
- `db/migrations/011_rmw.sql` — the highest existing migration; the next is `012_`
- `web/scripts/migrate.mjs` — applies `db/migrations/*.sql` once each
- `engine/src/seer_engine/lab/store.py:91-105` — the append-only `insights` table and its triggers
- `engine/src/seer_engine/demo.py:14-26` — `DEMO_TABLES`, the demo purge list
- `engine/tests/test_migrate.py` — asserts every `db/migrations/*.sql` applies cleanly in order

---

## Current Dataflow

### Entry Point: `GET /sera/journal`

**Location:** `web/app/sera/journal/page.tsx:29` (`JournalPage`)
**Trigger:** HTTP GET, Next.js App Router server component
**Input Schema:** `searchParams: Promise<{ kind?: string | string[] }>`
**Validation:** `parseKind(q.kind)` (`view.ts:43`) — any value not in `INSIGHT_KINDS` becomes `'all'`
**Gate:** `await requireSera(journalHref(filter))` (`lib/sera/gate.ts:11`) — signed out redirects
to `/signin?next=…`; signed in as anyone but `SERA_EMAIL` within `ALLOWED_EMAIL` gets `notFound()`

**Next Step:** reads the module-level `lab` snapshot and shapes it with two pure calls.

### Processing Chain

1. **`kindCounts(lab.insights)`**
   - **Location:** `web/app/sera/journal/view.ts:60`
   - **Input:** the full `LabInsight[]`
   - **Transform:** a bare tally — one counter per `InsightKind`, zeroes included
   - **Output:** `Record<InsightKind, number>`
   - **Consumed by:** the `options` array at `page.tsx:38`, which becomes the badge numbers.
     This is the function the user is calling wrong: it answers "how many exist", and the badge
     is asking "how many are new".

2. **`journalGroups(lab.insights, filter)`**
   - **Location:** `web/app/sera/journal/view.ts:71`
   - **Input:** the full `LabInsight[]` and the active `KindFilter`
   - **Transform:** `INSIGHT_KINDS.filter(k => filter === 'all' || k === filter)`, then for each
     surviving kind `insights.filter(i => i.kind === kind).sort(newestFirst)` plus the static
     copy from `KIND_COPY` and the heading from `INSIGHT_KIND_LABEL`
   - **Output:** `JournalGroup[]` — `{ kind, heading, caption, empty, tone, entries }`
   - **Note:** `.filter()` copies before `.sort()`, so the snapshot array is never reordered
     (asserted by `view.test.ts` "does not reorder the input"). Any new sort must keep that.

3. **`newestFirst(a, b)`**
   - **Location:** `web/app/sera/journal/view.ts:53`
   - **Transform:** descending by `added`, ties broken by higher `id` first
   - **Output:** a comparator; the only ordering rule in the page today

4. **Render — the seven-icon bar**
   - **Location:** `web/app/sera/journal/page.tsx:56-71`
   - `options` = `{ id: 'all', n: total, Icon: ListFilter }` followed by one entry per kind with
     `n: counts[k]`. Each is a `<Link href={journalHref(id)} replace scroll={false}>` carrying
     `className="icon-btn md"`, `data-tip`, `aria-label` and `aria-current`, with a
     `<span className={s.badge}>{n}</span>` absolutely positioned at its top-right corner.
   - `s.badge.zero` already exists in `journal.module.css:11` and renders a muted badge — it is
     reachable today only for a kind with no entries at all.

5. **Render — one `Section` per kind**
   - **Location:** `web/app/sera/journal/page.tsx:78-93`
   - Eyebrow is the entry count, title the heading, caption the `KIND_COPY` caption; the body is
     either `g.empty` or a two-column `.cards` grid of `InsightCard`s.

6. **Render — `InsightCard`**
   - **Location:** `web/app/sera/journal/page.tsx:99`
   - Head: `h3` title + `<time>` with `dayLabel(insight.added)`
   - Body: `dangerouslySetInnerHTML` from `renderMarkdown(insight.body)` (escape-first, `lib/sera/markdown.ts`)
   - Foot — **only when `insight.methodId` is set**: an "About M0022 · name" line and, **only
     when `methodById(insight.methodId)` resolves**, the redirect-arrow
     `<Link href={/sera/methods/<id>} className="icon-btn sm"><ArrowUpRight/></Link>`.
     This is the arrow the user refers to. In today's snapshot 21 of 26 insights carry a
     `methodId`; 5 carry none and therefore have **no arrow at all** — those are precisely the
     items R2 says need a non-click rule.

### Data Persistence

**Lab snapshot:** `web/data/lab.json`, 0.89 MB, imported at module scope by `lib/sera/lab.ts`
and bundled at build time. Regenerated by `python -m seer_engine lab stage` / `lab export-json`
and committed; never edited by hand. Read-only from the web app.

**Neon (Postgres):** reached through `sql` from `web/lib/db.ts` (`@neondatabase/serverless`,
HTTP). Every existing read lives in `web/lib/data.ts`; the single existing write is
`dismissAction` at `web/lib/data.ts:479`:
```ts
await sql`INSERT INTO action_dismissals (order_id) VALUES (${orderId}) ON CONFLICT DO NOTHING`;
```
backed by `db/migrations/001_init.sql:81`:
```sql
CREATE TABLE IF NOT EXISTS action_dismissals (
  order_id      bigint PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
  dismissed_at  timestamptz NOT NULL DEFAULT now()
);
```
Note it carries no user column — the app is single-account — and the write is idempotent via
`ON CONFLICT DO NOTHING`. Both properties carry over to seen-state.

**Migrations:** `db/migrations/NNN_name.sql`, applied once each by `web/scripts/migrate.mjs`
(and by the engine's Python runner, sharing `schema_migrations`). Highest today is
`011_rmw.sql`; the next free number is `012`.

**Cache:** none in Sera. `/sera/*` has no `export const dynamic` or `revalidate`; the pages are
dynamic because `requireSera()` reads cookies. `app/(app)/{page,history,positions,leaderboard}`
each declare `export const dynamic = 'force-dynamic'` — the convention for a page that reads Neon.

### Exit Points

- HTML for `/sera/journal`
- `redirect('/signin?next=…')` when signed out; `notFound()` when signed in as anyone else
- Client-side navigation to `/sera/journal?kind=<k>` on a tab click (`replace`, `scroll={false}`)
- Client-side navigation to `/sera/methods/<id>` on a redirect-arrow click
- No writes of any kind today

### State Changes

None. `/sera/journal` is read-only end to end.

---

## Key Data Structures

### Type: `LabInsight`
**Location:** `web/lib/sera/types.ts:103`
```ts
export type LabInsight = {
  id: number;
  kind: 'observation' | 'hypothesis' | 'data-wish' | 'feature-wish' | 'risk' | 'synthesis';
  title: string;
  body: string;
  methodId: string | null;
  added: string;
};
```
**Used In:** `journalGroups`, `kindCounts`, `newestFirst` (`app/sera/journal/view.ts`),
`InsightCard` (`page.tsx:99`), `insightsOf` (`lib/sera/lab.ts:21`),
`app/sera/methods/[id]/page.tsx`, `app/sera/page.tsx` (the latest synthesis on Overview).

**`id` is stable and monotonic.** `engine/src/seer_engine/lab/store.py:93` declares
`insights` with an autoincrementing id, and lines 102-105 add
`insights_no_update` / `insights_no_delete` triggers that `RAISE(ABORT)` on any UPDATE or
DELETE. The table is append-only by construction, so an id, once issued, names the same insight
forever. Seen-state keyed on `id` can live in another database without a foreign key and still
never drift.

### Type: `KindFilter` / `KindCopy` / `JournalGroup`
**Location:** `web/app/sera/journal/view.ts:5,9,67`
```ts
export type KindFilter = InsightKind | 'all';
export type KindCopy = { caption: string; empty: string; tone: string };
export type JournalGroup = KindCopy & { kind: InsightKind; heading: string; entries: LabInsight[] };
```
`JournalGroup.entries` is the single flat list the page renders. R1 splits it in two; the shape
either grows a second list or grows a per-entry flag.

### Constant: `INSIGHT_KINDS`
**Location:** `web/lib/sera/types.ts:131`
`['synthesis','observation','hypothesis','data-wish','feature-wish','risk']` — the Journal's
display order and the source of six of the seven tabs. The seventh is the `all` sentinel,
constructed inline at `page.tsx:39`.

### Snapshot shape today
26 insights, ids 1-26, `added` from `2026-10-04T14:12:19+00:00` to `2026-10-06T19:08:18+00:00`.
By kind: observation 18, risk 4, synthesis 2, data-wish 1, feature-wish 1, hypothesis 0.
21 carry a `methodId`, 5 do not.

---

## Dependencies

### Configuration / Environment

- `DATABASE_URL` — Neon connection for `lib/db.ts` (already set wherever the app runs; the
  `(app)` section depends on it)
- `DATABASE_URL_UNPOOLED` — used by `scripts/migrate.mjs` only
- `ALLOWED_EMAIL` — the single allowed Google account (`lib/allow.ts`)
- `SERA_EMAIL` — narrows `/sera` further (`lib/sera/access.ts`)
- `AUTH_*` — NextAuth/Google (`auth.ts`)

### External Services

- Neon serverless Postgres over HTTP (`@neondatabase/serverless` ^1.2.0)
- Google OAuth via `next-auth` ^5.0.0-beta.32
- Vercel, region `sin1` (`web/vercel.json`)

### Build-time inputs

- `web/data/lab.json`, produced by `python -m seer_engine lab stage`

---

## Reference List

Every site that touches the badge counts, the entry ordering, or the storage the change needs.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `JournalPage` | `web/app/sera/journal/page.tsx:29` | def | web |
| `options` (the seven tabs) | `web/app/sera/journal/page.tsx:38-46` | call | web |
| badge `<span className={s.badge}>` | `web/app/sera/journal/page.tsx:68` | render | web |
| `InsightCard` | `web/app/sera/journal/page.tsx:99` | def | web |
| redirect-arrow `<Link>` | `web/app/sera/journal/page.tsx:114-118` | render | web |
| `kindCounts` | `web/app/sera/journal/view.ts:60` | def | web |
| `kindCounts` | `web/app/sera/journal/page.tsx:34` | call | web |
| `kindCounts` | `web/app/sera/journal/view.test.ts:54` | test | web |
| `journalGroups` | `web/app/sera/journal/view.ts:71` | def | web |
| `journalGroups` | `web/app/sera/journal/page.tsx:35` | call | web |
| `journalGroups` | `web/app/sera/journal/view.test.ts:62-84` | test | web |
| `newestFirst` | `web/app/sera/journal/view.ts:53` | def | web |
| `newestFirst` | `web/app/sera/journal/view.test.ts:46` | test | web |
| `parseKind` / `journalHref` | `web/app/sera/journal/view.ts:43,50` | def | web |
| `KIND_COPY` / `JournalGroup` | `web/app/sera/journal/view.ts:12,67` | def | web |
| `.badge`, `.badge.zero`, `.segBtn` | `web/app/sera/journal/journal.module.css:7-13` | css | web |
| `.cards`, `.card`, `.cardFoot` | `web/app/sera/journal/journal.module.css:15-33` | css | web |
| `LabInsight`, `InsightKind`, `INSIGHT_KINDS` | `web/lib/sera/types.ts:103,126,131` | def | web |
| `lab`, `methodById` | `web/lib/sera/lab.ts:9,15` | def | web |
| `insightsOf` | `web/lib/sera/lab.ts:21` | def | web |
| `INSIGHT_KIND_LABEL` | `web/lib/sera/glossary.ts` | def | web |
| `requireSera` | `web/lib/sera/gate.ts:11` | def | web |
| `requireSera` | `web/app/sera/journal/page.tsx:33`, `app/sera/layout.tsx:11` | call | web |
| `sql` | `web/lib/db.ts:3` | def | web |
| `dismissAction` | `web/lib/data.ts:479` | def (write precedent) | web |
| `dismiss` server action | `web/app/(app)/actions.ts:7` | def (action precedent) | web |
| `export const dynamic = 'force-dynamic'` | `web/app/(app)/{page,history/page,positions/page,leaderboard/page}.tsx:16-18` | convention | web |
| `SeraNav`, `TABS` | `web/components/sera/SeraNav.tsx:7,16` | def | web |
| `SeraLayout` | `web/app/sera/layout.tsx:9` | def | web |
| `Section` | `web/components/sera/Section.tsx` | def | web |
| `TooltipLayer` / `installTooltips` | `web/components/TooltipLayer.tsx`, `web/components/tooltip.ts` | def | web |
| `.icon-btn`, `.seg` | `web/app/globals.css:147,176` | css | web |
| `action_dismissals` | `db/migrations/001_init.sql:81` | schema precedent | db |
| highest migration | `db/migrations/011_rmw.sql` | schema | db |
| migration runner | `web/scripts/migrate.mjs:9` | tool | web |
| `insights` table + append-only triggers | `engine/src/seer_engine/lab/store.py:93,102-105` | schema | engine |
| `DEMO_TABLES` | `engine/src/seer_engine/demo.py:14` | config | engine |
| migrations-apply test | `engine/tests/test_migrate.py:90` | test | engine |
| Sera "not from Neon" sentence | `web/package_readme.md` (Overview) | doc | web |
| Journal line in the layout tree | `web/package_readme.md` (Layout) | doc | web |

---

## Impact Points (files that WILL need changes)

1. `db/migrations/012_journal_seen.sql` — **new.** The table that remembers which insight ids
   have been seen. Owned by phase 1.
2. `web/lib/sera/seen.ts` — **new.** Server-only Neon read/write for that table
   (`seenInsightIds()`, `markInsightsSeen(ids)`). Kept out of `lib/data.ts` because that module
   is the `(app)` read model and Sera has its own `lib/sera/` namespace. Owned by phase 1.
3. `web/app/api/sera/journal/seen/route.ts` — **new.** The `POST` endpoint the client island
   beacons ids to. A route handler rather than a server action because the flush on
   page-hide needs `navigator.sendBeacon`, which can only target a URL. Owned by phase 1.
4. `web/app/sera/journal/view.ts` — `kindCounts` gains an unseen-aware sibling; `journalGroups`
   gains the seen-set parameter and the unseen/seen partition. Owned by phase 2.
5. `web/app/sera/journal/view.test.ts` — the existing suite asserts the current signatures
   (`kindCounts(ALL)`, `journalGroups(ALL, 'all')`, "does not reorder the input"); it must grow
   partition and unseen-count cases. Owned by phase 2.
6. `web/app/sera/journal/page.tsx` — reads the seen-set, feeds it to the view helpers, renders
   unseen counts in the badges, renders the unseen/seen boundary, tags each card with its id and
   its seen state, mounts the client island, and declares `force-dynamic`. Owned by phase 3;
   phase 4 edits it again to mount the island and hand the bar its live counts.
7. `web/app/sera/journal/journal.module.css` — styles for the unseen marker on a card and the
   "already seen" divider. Owned by phase 3; phase 4 adds nothing to it.
8. `web/app/sera/journal/JournalSeen.tsx` — **new, client.** `IntersectionObserver` dwell
   detection, arrow-click marking, batched POST, page-hide flush, and the live badge countdown.
   Owned by phase 4.
9. `web/app/sera/journal/seen-client.ts` — **new, pure.** The dwell/batch policy constants and
   the queue logic, extracted so it can be unit-tested without a DOM. Owned by phase 4.
10. `web/components/sera/SeraNav.tsx` — the Journal rail tab gains an optional badge prop.
    Owned by phase 5.
11. `web/components/sera/SeraNav.module.css` — the rail badge style. Owned by phase 5.
12. `web/app/sera/layout.tsx` — reads the unseen total and passes it to `SeraNav`. Owned by phase 5.
13. `web/package_readme.md` — the Overview sentence "not from Neon" needs the seen-state
    exception, and the Layout tree needs the new files. Owned by phase 5 (the last phase to land).

**This document describes. The plan files prescribe.**
