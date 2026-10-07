# Plan: Journal notifications count what you have not seen yet

**Slug:** journal-unseen-badges
**Date:** 2026-10-07 10:39:57 +07
**Analysis:** `20261007-103957-J4N8_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/journal-unseen-badges`
**Branch:** `feature/journal-unseen-badges` (base: `origin/main` @ `46c04b4`)
**Phases:** 5
**Status:** 4/5 phases complete (1, 2, 3, 4); landing owned by the swarm coordinator
**Reconciled:** 2026-10-07 — 9 conflicts found, 9 resolved, 0 open questions
**Coordinator:** `orch-journal-unseen-badges`

---

## Why

The user's words, verbatim:

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

The badge on each of the seven tabs is `kindCounts(lab.insights)[kind]` today — the total
inventory of that kind, a number that only ever grows and never responds to the reader. The
user likes the affordance and wants the number behind it to mean something: how many entries
are new to them.

## Requirements

Final after reconciliation — this is the mapping the phase plans actually implement.

| ID | What the user asked for | Phases | Where it lands |
|---|---|---|---|
| R1 | Within every tab's content, unseen items sit at the top sorted newest-to-oldest, and seen items are pushed down below them | 2, 3 | 2 partitions (`journalGroups`' seen-set parameter, `JournalGroup.unseen`/`.seen`); 3 renders the two halves and the divider between them |
| R2 | A working definition and mechanism for "seen": a click on an item's redirect-arrow marks it seen, and items with no arrow are marked seen some other way — e.g. the user opened that tab and the item was shown on screen | 1, 4 | 1 persists it (`journal_seen`, `markInsightsSeen`, the POST route); 4 decides *when* (arrow click, and the dwell rule that is the only thing reaching the 5 arrow-less entries) |
| R3 | The notification number on each of the seven tab icons is the true count of *unseen* items for that tab, so a new number on a tab is a real signal worth getting excited about | 2, 3, 4, 5 | 2 counts (`unseenCounts`, `badgeTip`); 3 renders the seven badges; 4 counts them down live; 5 carries the total to the Sera rail |

No requirement id is unowned, and no phase's steps serve an `R` outside its own **Satisfies**
line — checked after every move below.

## Scope

**In scope**

- A Neon table that remembers which `LabInsight.id`s have been seen, and the server read/write
  over it (`db/migrations/012_journal_seen.sql`, `web/lib/sera/seen.ts`).
- A `POST` endpoint the browser can beacon newly-seen ids to
  (`web/app/api/sera/journal/seen/route.ts`).
- Unseen-aware shaping in the Journal's pure view layer: per-kind unseen counts and an
  unseen-then-seen partition inside each group (`web/app/sera/journal/view.ts`).
- The page rendering unseen counts in the seven badges, an unseen/seen boundary inside each
  section, and a per-card unseen marker (`web/app/sera/journal/page.tsx`, `journal.module.css`).
- A client island that marks an entry seen when its redirect-arrow is clicked, or when the entry
  has dwelled on screen in a visible tab (`JournalSeen.tsx`, `seen-client.ts`), batching the ids
  and flushing them on page-hide.
- Badges that count down live as entries are marked seen during the visit.
- A badge on the Journal tab of the Sera rail carrying the unseen total, so the number is
  visible from the other Sera pages (`SeraNav.tsx`, `app/sera/layout.tsx`).

**Out of scope**

- Any change to `web/data/lab.json`, to the engine's `insights` table, or to how insights are
  written. The lab stays append-only and the snapshot stays the single source of lab facts.
- A "mark all as read" / "mark unread" control. The user asked for the count to be correct, not
  for manual control of it; adding buttons now would be inventing scope.
- Per-user seen-state. Seer is locked to one Google account (`lib/allow.ts`,
  `lib/sera/access.ts`); the existing `action_dismissals` table carries no user column for the
  same reason, and so does this one.
- Badges anywhere outside the Journal's seven tabs and the Sera rail's Journal tab — the Methods
  and Ideas pages keep the counts they have.
- Notifications outside the app (email, push, service worker).

## Invariants

Every phase must leave all of these true.

1. **The tree builds and `npm test` passes at the end of each phase.** `cd web && npx tsc --noEmit && npm test`.
2. **The lab snapshot is read-only.** No phase writes to `web/data/lab.json`, and no phase makes
   the Journal's lab facts depend on Neon. Only *reader* state lives in Postgres.
3. **Pure view logic stays pure and tested.** Everything in `web/app/sera/journal/view.ts` and
   `web/app/sera/journal/seen-client.ts` takes plain data, touches no DOM, no network and no
   database, and is covered by a vitest suite that runs with no connection — the discipline every
   other `lib/*.ts` and `view.ts` in this app already follows.
4. **The snapshot array is never reordered in place.** `journalGroups` copies before it sorts;
   `view.test.ts`'s "does not reorder the input" case must keep passing.
5. **The rendered order is frozen for the page view.** The unseen/seen partition is computed once
   on the server from the seen-set as it stood when the page was requested. Marking an entry seen
   during a visit changes the badges and the per-card marker, never the position of a card.
6. **Marking seen is idempotent and additive.** Posting an id that is already seen is a no-op;
   nothing in this plan ever deletes a `journal_seen` row or marks an entry unseen.
7. **The `/sera` gate holds everywhere, the new endpoint included.** The POST route rejects any
   caller `requireSera` would reject, and reveals nothing about the section to anyone else.
8. **The seven tabs stay exactly seven, in the order they have now** — the `all` sentinel first,
   then `INSIGHT_KINDS` in its declared order — and keep their current icons, tooltips,
   `aria-label`, `aria-current` and `.icon-btn md` styling. Only the number inside the badge
   changes meaning.
9. **An empty `journal_seen` table reads as "nothing seen yet"**, and a failed seen-state read
   degrades to the same thing: every entry unseen, the page still renders. The Journal never 500s
   because Postgres is unreachable.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 ✅ | Seen-state storage, server read/write, and the POST endpoint | R2 | `db/migrations`, `web/lib/sera`, `web/app/api` | 3 | — | NORMAL | `.workflows/plan/journal-unseen-badges/phase-1.md` | P1-WEB-K3QM (done 2026-10-07) | — |
| 2 ✅ | Unseen-aware pure view layer: counts and the unseen/seen partition | R1, R3 | `web/app/sera/journal` | 2 | — | NORMAL | `.workflows/plan/journal-unseen-badges/phase-2.md` | P1-WEB-SSGU | — |
| 3 ✅ | The page renders unseen counts, the boundary, and per-card state | R1, R3 | `web/app/sera/journal` | 2 | 1, 2 | NORMAL | `.workflows/plan/journal-unseen-badges/phase-3.md` | P1-WEB-M2WF | — |
| 4 ✅ | The client island: dwell, click, batch, flush, live countdown | R2, R3 | `web/app/sera/journal` | 4 | 1, 2, 3 | HARD | `.workflows/plan/journal-unseen-badges/phase-4.md` | P1-WEB-Q8DV (done 2026-10-07) | — |
| 5 | The rail badge and the package readme | R3 | `web/components/sera`, `web/app/sera`, docs | 4 | 1, 2, 3, 4 | EASY | `.workflows/plan/journal-unseen-badges/phase-5.md` | P1-WEB-Z5LP | — |

**Waves**, given those dependencies: phases **1 and 2** run concurrently (neither depends on
anything and they share no file); then **3**; then **4**; then **5**.

Phase 5's code needs only phase 1 (`lib/sera/seen.ts`), but three of its readme edits (4d, 4g,
4h) describe files phases 2, 3 and 4 create, and its own plan tells the session to read those
files before writing their one-line descriptions. Running it early would mean documenting files
that do not exist yet. The draft's `Depends on: 1` was therefore widened to `1, 2, 3, 4` — the
truthful constraint, and the one that keeps the readme describing the set as it actually landed.

### Phase 1 — Seen-state storage, server read/write, and the POST endpoint

**Satisfies:** R2

**Owns:**
- `db/migrations/012_journal_seen.sql` — **new.** `journal_seen`, modelled on `action_dismissals`
  (`db/migrations/001_init.sql:81`): `insight_id bigint PRIMARY KEY`,
  `seen_at timestamptz NOT NULL DEFAULT now()`, and a `via text` column recording how it was
  marked, constrained to `'view'` or `'click'`. **No foreign key** — insights live in the
  engine's SQLite lab store, not in Postgres, and the analysis establishes that ids there are
  append-only and never reused, so there is nothing to cascade from. No user column: one account.
  `CREATE TABLE IF NOT EXISTS`, like every other table in `db/migrations`.
- `web/lib/sera/seen.ts` — **new, server only.** Over `sql` from `@/lib/db`:
  - `seenInsightIds(): Promise<Set<number>>` — every `insight_id` in the table. Wrapped so that
    a failed query resolves to an empty set and logs, never throws (invariant 9). **Phase 3's**
    reader: the page needs the whole set, to partition and to tally per kind.
  - `unseenCount(ids: Iterable<number>): Promise<number | null>` — how many of `ids` are not in
    the table, or `null` when the read failed. **Phase 5's** reader: the rail needs one number
    *and* the ability to say "I don't know", because invariant 9 wants **no badge** on a failed
    read and an empty `Set` cannot express that. The two are not duplicates; they answer
    different questions, and phase 2's pure `unseenCounts` answers a third. Takes the ids rather
    than importing the snapshot, so the API route's bundle never pulls `data/lab.json`.
  - `markInsightsSeen(ids: number[], via: 'view' | 'click'): Promise<number>` — a single
    multi-row `INSERT … ON CONFLICT DO NOTHING`, returning how many rows were new.
  - `normalizeSeenIds` / `parseSeenVia` — the shared input guard; the route holds none of its
    own. `MAX_SEEN_BATCH = 500` is the per-request id cap, and phase 4's client-side
    `MAX_BATCH = 50` must stay ≤ it (they cannot share a constant: this module is server-only).
  - Keep it in `lib/sera/`, not `lib/data.ts`: `data.ts` is the `(app)` read model and Sera has
    its own namespace. Mirror `dismissAction`'s tagged-template style and its idempotence.
- `web/app/api/sera/journal/seen/route.ts` — **new.** `POST` handler. Gates the caller the way
  `requireSera` does — signed in, `isAllowed(email, ALLOWED_EMAIL)` **and** `isSeraUser(email)` —
  but answers with status codes rather than `redirect`/`notFound`, since this is an XHR/beacon
  target, not a navigation: anything that fails the gate gets `404` with an empty body, so the
  section is not revealed (invariant 7). Accepts `{"ids": number[], "via"?: "view" | "click"}`,
  also accepting a `text/plain` body because `navigator.sendBeacon` sends a `Blob`; rejects a
  malformed body with `400`; answers `204` on success. Factor the gate check so it reads from the
  same `isAllowed`/`isSeraUser` pair `lib/sera/gate.ts` uses rather than re-deriving the rule.

**Does not touch:** `web/app/sera/journal/*` (phases 2-4 own every file there), `SeraNav`, the
Sera layout, `lib/data.ts`, `lib/sera/lab.ts`, `web/data/lab.json`.

**Exit criteria:**
- `db/migrations/012_journal_seen.sql` applies cleanly on top of `011_rmw.sql` and is idempotent
  on a second apply (`engine/tests/test_migrate.py` applies every file in order).
- `seenInsightIds()` returns an empty `Set` against an empty table and against an unreachable
  database, and never throws.
- `unseenCount(ids)` returns a number against a reachable database and `null` against an
  unreachable one, and never throws.
- `markInsightsSeen` is idempotent: the same ids posted twice leave one row each.
- `POST /api/sera/journal/seen` returns `204` for the Sera user, `404` for everyone else, and
  `400` for a body that is not `{ids: number[]}`.
- Nothing in the app calls any of it yet; the tree builds and `npm test` passes.
- `journal_seen` is **not** in `engine/src/seer_engine/demo.py`'s `DEMO_TABLES`, and no phase in
  this set adds it: a demo purge must not wipe what the owner has read.

### Phase 2 — Unseen-aware pure view layer: counts and the unseen/seen partition

**Satisfies:** R1, R3

**Owns:**
- `web/app/sera/journal/view.ts` — the pure shaping. **Settled shape, as reconciled:**
  - `unseenCounts(insights, seen?): Record<KindFilter, number>` — keyed by all seven tabs, so
    `.all` is the unseen total and the sentinel needs no special case. Keep `kindCounts` itself:
    it is the denominator in the tooltip.
  - `badgeTip(heading, unseen, total): string` — the **single** formatter for the seven tab
    tooltips. Phase 3 calls it for the server render and phase 4's client island calls it for
    the live rewrite, so the wording cannot fork. No tip string is written inline anywhere.
  - `SEEN_COPY = { boundary, marker, markerLabel }` — the divider label, the unseen card's
    marker tooltip, and the marker's screen-reader text. Beside `KIND_COPY`, because every
    other string on this page lives in `view.ts` or `glossary.ts`.
  - `journalGroups(insights, filter, seen?)` — the seen-set is a trailing **optional**
    `ReadonlySet<number>`. Each `JournalGroup` carries `items: JournalEntry[]` (where
    `JournalEntry = { insight, unseen }`), the two halves `unseen` / `seen`, `unseenCount`, and
    the flat `entries: LabInsight[]` it already had. Phase 3 renders `unseen` and `seen`
    **directly** — no adapter. `entries` stays because `view.test.ts` asserts it and it keeps
    the tree green while `page.tsx` is untouched; phase 3 stops using it and must not remove it.
  - The boundary test, used verbatim downstream: `g.unseenCount > 0 && g.unseenCount < g.items.length`.
  - **Must stay importable from a `'use client'` module** — phase 4 imports `badgeTip`. Verified
    client-safe: `view.ts` imports only `lib/sera/glossary` and `lib/sera/types`, neither of
    which touches `lib/db`, `lib/sera/lab` or anything server-only. This is now a constraint,
    not just a property.
  - Invariant 4 holds: copy before sorting, never sort the snapshot array.
- `web/app/sera/journal/view.test.ts` — extend the existing suite. The present cases
  (`parseKind`, `journalHref`, `newestFirst`, `kindCounts`, `journalGroups` x3, `dayLabel`) must
  keep passing in spirit; update the `journalGroups` calls for the new signature and add:
  an empty seen-set means everything unseen; a full seen-set means zero unseen everywhere; a
  mixed set partitions correctly with each side newest-first; a seen id that is not in the
  snapshot is ignored; the `all` total is the sum of the six kinds; and the input array is still
  not reordered.

**Does not touch:** `page.tsx`, `journal.module.css`, anything outside `web/app/sera/journal/`.
It must not import `lib/sera/seen.ts`, `lib/db.ts`, or anything server-only — it takes a
`ReadonlySet<number>` as a parameter (invariant 3).

**Exit criteria:**
- `npx vitest run app/sera/journal` passes with no database and no DOM.
- `journalGroups`, `unseenCounts`, `badgeTip` and `SEEN_COPY` are exported with the signatures
  above, which phase 3 consumes without guessing.
- `npx tsc --noEmit` is clean **with `page.tsx` byte-identical to its pre-phase state.** This is
  the load-bearing check: the seen-set parameter is **optional**, defaulting to an empty set, so
  the untouched `page.tsx` keeps compiling and keeps rendering exactly today's output. Phase 3
  does not assume otherwise — it passes three arguments. If `tsc` complains at `page.tsx:35` or
  about `g.entries`, fix `view.ts`, never `page.tsx`.
- `view.ts` imports nothing beyond `lib/sera/glossary` and `lib/sera/types` (`grep -n "^import"`),
  so phase 4's client island can import `badgeTip` from it.

### Phase 3 — The page renders unseen counts, the boundary, and per-card state

**Satisfies:** R1, R3

**Owns:**
- `web/app/sera/journal/page.tsx` — the server render:
  - `export const dynamic = 'force-dynamic'`, matching `app/(app)/*` now that the page reads Neon.
    This is the only place in the set that adds it to `page.tsx`; phase 1's is in its own
    `route.ts`. No double-add.
  - `await seenInsightIds()` from phase 1 into a local named **`seenIds`** (not `seen` — that
    name is taken by a group's seen half, and the shadowing would be a trap). Phase 4 reads it
    by that name.
  - The seven `options` carry **unseen** counts (`fresh.all` for the sentinel, `fresh[k]` per
    kind) and two new fields, `heading` and `total`, which are `badgeTip`'s other two arguments.
    The `tip` string comes from `badgeTip` — this page writes no tooltip copy of its own, and
    phase 4 reads `heading`/`total` off this same array rather than adding a field to it. The
    `.badge.zero` style now means "nothing new here", which is its real job.
  - Each `Section`'s body renders `g.unseen`, then — only when
    `g.unseenCount > 0 && g.unseenCount < g.items.length` — the boundary element, then `g.seen`.
    No adapter and no `split()` helper: phase 2's halves are rendered directly. A section whose
    entries are all unseen, or all seen, or absent, shows no boundary.
  - `InsightCard` takes the entry's unseen flag, carries `data-insight-id={insight.id}` and
    `data-unseen="true"|"false"` (**always present, always a string** — the hooks phase 4's
    observer reads), and shows a small marker on an unseen card. The redirect-arrow `<Link>`
    gains `data-seen-click="true"`, so phase 4 can bind the click without restructuring the card.
  - Everything stays a server component; no `'use client'` in this phase.
- `web/app/sera/journal/journal.module.css` — the unseen marker on a card and the boundary
  style. Reuse the existing palette tokens (`--coral`, `--on-coral`, `--ink-2`, `--hair`,
  `--outline`) the badge and the cards already use; the boundary should read as a quiet divider,
  not as another section header. Keep the two-column `.cards` grid and its 1023.98px single-column
  breakpoint intact.
  **This phase owns every marker rule, including the one phase 4 triggers**:
  `.card[data-seen-now] .new` keeps the dot in the layout at `opacity: 0` with a 240ms
  transition, so retiring a marker live fades it instead of collapsing its box and reflowing the
  title. The rule needs the hashed `.new` class, which is only in scope in this module — which
  is why there is **no `data-unseen-marker` attribute** anywhere in this set and why phase 4
  does not open this file.

**Does not touch:** `view.ts` / `view.test.ts` (phase 2 owns them — in particular, **do not remove
`JournalGroup.entries`**, which this page stops using but `view.test.ts` still asserts),
`lib/sera/seen.ts` and the API route (phase 1 owns them), `SeraNav` and the Sera layout (phase 5).

**Note on the shared file:** phase 4 edits `page.tsx` after this phase, to mount the client
island and give the badge span one attribute. Phase 4's plan quotes the file as it looks *after*
phase 3 — its anchors were rewritten by the reconciler to this phase's real names (`seenIds`,
the six-field `options` entries, `badgeTip`'s copy, `InsightCard({ insight, tone, unseen })`).

**Exit criteria:**
- With an empty `journal_seen` table the page is visually equivalent to today's except that every
  badge shows the same number it shows now and every card carries the unseen marker — because
  nothing has been seen yet.
- With some ids seen, those cards appear below the boundary inside their section and the badges
  drop by exactly that many.
- A section with no seen entries and a section with no unseen entries both render without a
  stray boundary.
- The seven tabs are unchanged in order, icons, `aria-current` behaviour and styling; their
  tooltips are `badgeTip`'s strings, not hand-written ones.
- Setting `data-unseen="false"` plus `data-seen-now` on a card by hand fades its dot without the
  title shifting — the contract phase 4 relies on.
- `npx tsc --noEmit && npm test` clean.

### Phase 4 — The client island: dwell, click, batch, flush, live countdown

**Satisfies:** R2, R3

**Owns:**
- `web/app/sera/journal/seen-client.ts` — **new, pure.** The policy and the queue, DOM-free and
  unit-testable (invariant 3):
  - The constants, in one place with a comment each: the visibility fraction that counts as "on
    screen", the fallback pixel height for a card taller than the viewport, the dwell in
    milliseconds, the idle debounce before a flush, and the maximum batch size. `MAX_BATCH = 50`
    **must stay ≤ phase 1's `MAX_SEEN_BATCH = 500`**, which the route enforces with a `400`. They
    cannot share a constant (`lib/sera/seen.ts` is server-only), so each side carries a comment
    naming the other and phase 4's verification greps the pair.
  - A queue object: add an id, ask what is pending, take the pending batch for a flush, and know
    which ids are already marked so an id is never posted twice in a session.
  - A function deciding whether an `IntersectionObserver` entry counts as "on screen" from its
    intersection and bounding rectangles plus the viewport height — this is the piece worth
    testing, and it is pure arithmetic.
- `web/app/sera/journal/seen-client.test.ts` — **new.** Vitest over those two: the threshold
  decision for a short card, a card taller than the viewport, a card half out of frame; the
  queue's dedupe, its batch cap, and that taking a batch empties the pending set.
- `web/app/sera/journal/JournalSeen.tsx` — **new, `'use client'`.** The island:
  - Finds the cards by the `data-insight-id` hook phase 3 put on them, observes them with one
    `IntersectionObserver`, and starts a dwell timer when a card counts as on screen —
    cancelling it if the card leaves, or if `document.visibilityState` turns `hidden`, so a
    background tab never marks anything seen. On dwell completion the id joins the queue.
  - Binds the redirect-arrow click (`data-seen-click`) to mark that card's id immediately with
    `via: 'click'`, and flushes right away, because the click is a navigation away from the page.
  - Flushes the queue to `POST /api/sera/journal/seen` after the idle debounce or at the batch
    cap, and on `visibilitychange → hidden` and `pagehide` via `navigator.sendBeacon` — with a
    `fetch(..., { keepalive: true })` fallback where `sendBeacon` is absent.
  - Decrements the live badge counts as ids are marked, so the number on the tab falls while the
    reader reads, and rewrites each tooltip by calling **phase 2's `badgeTip`** with the live
    count. It must **not** move any card (invariant 5): it sets `data-unseen="false"` and
    `data-seen-now` on a marked card, which phase 3's CSS turns into a fade in place.
  - Cleans up every observer, timer and listener on unmount.
  - A failed POST is swallowed: the ids stay queued for the next flush and the page carries on.
    Never surface a network error to the reader over something this soft.
- `web/app/sera/journal/page.tsx` — a second edit, on top of phase 3, in **four surgical edits**:
  import the island, derive `unseenByKind` and `badgeMeta`, put `data-badge-kind` on the badge
  `<span>`, mount `<JournalSeen>`. **Settled: the badges update through `data-` hooks on phase
  3's server-rendered markup, not by lifting the bar into a client component.** The bar stays
  exactly what the server rendered, so JS-disabled correctness is structural rather than a
  promise; and lifting it would have meant passing `Icon: LucideIcon` — a function — across the
  client boundary, which a server component cannot do. Nothing is added to the `options` array:
  phase 3 already carries `heading` and `total` for this.

**Does not touch:** `view.ts` / `view.test.ts` (it *imports* `badgeTip` from `view.ts` — allowed,
that module is pure and client-safe — but edits neither), `journal.module.css` (phase 3 owns
every rule, the `[data-seen-now]` fade included), `lib/sera/seen.ts`, the API route's contract
(phase 1 fixed it), `SeraNav`, the Sera layout.

**Exit criteria:**
- Opening a tab and reading down it marks the entries that were actually on screen, and only
  those; entries further down the page that were never scrolled to stay unseen on the next load.
- A background tab marks nothing.
- Clicking a redirect-arrow marks that entry before the navigation lands.
- Reloading shows the newly-seen entries below the boundary and the badges lower by exactly that
  many.
- Cards do not move while the page is open, and a retired marker fades rather than collapsing —
  the title beside it does not shift.
- A tooltip tracks its badge as the count falls, in `badgeTip`'s words (including its "all seen"
  phrasing at zero), because the island calls the same function the server did.
- `npx tsc --noEmit && npm test` clean, `seen-client.test.ts` included.

### Phase 5 — The rail badge and the package readme

**Satisfies:** R3

**Owns:**
- `web/app/sera/layout.tsx` — calls **`unseenCount(lab.insights.map(i => i.id))`** from phase 1's
  module and passes the result to `SeraNav`. Renders **no badge** on `null` (the read failed) or
  `0` — invariant 9, fully reached, because `unseenCount`'s `null` is the one thing that can tell
  a failed read from a clean zero. It must **not** use `seenInsightIds`: that resolves to an empty
  `Set` on failure, which would make a Neon outage show the full inventory and call it a
  notification. The ids come from `lab.insights`, never from `count(*)` and never from
  `insights.length - seen.size`, so the rail always agrees with the page's `all` badge.
- `web/components/sera/SeraNav.tsx` — the Journal tab accepts an optional unseen count and
  renders a badge in its corner when it is above zero. The rail is already `'use client'`; the
  count arrives as a prop from the server layout. The other four tabs are unchanged.
- `web/components/sera/SeraNav.module.css` — the rail badge, visually a sibling of
  `journal.module.css`'s `.badge` (same `--coral` / `--on-coral`, same pill), sized for the rail
  and correct in the below-1024px top-bar layout too.
- `web/package_readme.md` — the Overview sentence that says Sera reads "from a committed JSON
  snapshot … not from Neon" needs its exception written in: lab *facts* still come only from the
  snapshot; which entries the reader has seen is the one thing Sera stores in Postgres. Add the
  new files to the Layout tree (`lib/sera/seen.ts`, `app/api/sera/journal/seen/`,
  `app/sera/journal/JournalSeen.tsx`, `seen-client.ts`) and note `db/migrations/012_journal_seen.sql`.

**Does not touch:** anything under `web/app/sera/journal/` except as a mention in the readme —
phases 2-4 own those files. Does not touch the `(app)` section or its nav.

**Why it is last:** the readme must describe the set as it finally landed, and the rail badge is
the one piece a reader could drop without losing R1 or R2. This is why its `Depends on` is
`1, 2, 3, 4` rather than the draft's `1` — three of its readme edits document files phases 2–4
create, and its own plan tells the session to read those files first.

**Exit criteria:**
- The Journal tab in the rail shows the unseen total on every `/sera/*` page and no badge at
  zero.
- A failed seen-state read shows **no badge**, not the full inventory.
- With the read succeeding, the rail's number equals the `all` badge on `/sera/journal`,
  including when `journal_seen` holds an id outside the snapshot.
- The rail renders correctly in both the ≥1024px rail layout and the below-1024px top bar.
- `web/package_readme.md` no longer claims Sera never reads Neon, and lists every file this set
  added.
- `npx tsc --noEmit && npm test` clean.

## Reconciliation Log

The five phase planners ran concurrently and could not see each other's plans. Nine conflicts
were found and all nine were resolved **by editing the plan files**, so no phase session meets a
fork at runtime. Five further cross-phase claims were checked and found already consistent; they
are recorded below so nobody re-opens them.

### Conflicts resolved

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| C1 | Phase 2 exports `SEEN_COPY = { boundary, marker, markerLabel }` from `view.ts`; phase 3 guessed the name `SEEN_DIVIDER` and shipped a table of alternatives | Contract drift | 2, 3 | Phase 2 owns `view.ts`, so its name wins. Every occurrence in phase-3.md now reads `SEEN_COPY.boundary` / `.marker` / `.markerLabel`; the "three names in this plan are guesses" banner is replaced with phase 2's real contract table. `.markerLabel` is the marker's screen-reader text and `.marker` its `data-tip`, so none of the three ships dead. |
| C2 | Phase 3 wrote a module-private `split(g)` adapter against a guessed partition shape, with two ready-made alternatives | Duplicate work / contract drift | 2, 3 | Phase 2's `g.unseen` / `g.seen` are already the two sorted halves. **`split()` is deleted outright** — a pass-through would be a layer that explains nothing — along with both alternatives. Phase 3 maps `g.unseen` / `g.seen` directly, uses `g.items.length` as the entry count, and takes phase 2's boundary condition verbatim: `g.unseenCount > 0 && g.unseenCount < g.items.length`. |
| C3 | Three designs for one tooltip: phase 2's `badgeTip`, phase 3's inline template literals, phase 4's `tipTemplate` field + `data-tip-template` attribute | Duplicate work | 2, 3, 4 | **`badgeTip` is the single formatter, end to end.** Verified that `view.ts` is client-safe (it imports only `lib/sera/glossary` and `lib/sera/types`; `types.ts` imports nothing, `glossary.ts` imports only types), so phase 4's `'use client'` island imports `badgeTip` and calls it rather than re-implementing the string. `tipTemplate` and `data-tip-template` are deleted from phase-4.md; phase 3's inline strings and its "uniform format at zero" argument are deleted from phase-3.md. Phase 3's `options` grow `heading` and `total` instead, which phase 4 reads off the same array as `badgeMeta`. |
| C4 | Two unseen-total implementations: phase 1's `unseenCount(ids): Promise<number \| null>` and phase 2's `unseenCounts(...).all`; phase 5 assumed a third thing (`seenInsightIds` + a local reduce) | Duplicate work / unmet assumption | 1, 2, 5 | Settled by **invariant 9**: a failed read must degrade, and phase 5's exit criterion is *no badge*. Only `unseenCount`'s `null` distinguishes "read failed" from "nothing unseen" — an empty `Set` cannot. Phase 5 now calls `unseenCount(lab.insights.map(i => i.id))` and renders no badge on `null` or `0`; its substitution table and its "invariant 9 is only partly reachable" paragraph are deleted (with `unseenCount` it *is* reachable). **Both functions are kept** and all three plans now say why: `seenInsightIds` answers *which*, `unseenCount` answers *how many, and did it work*, `unseenCounts` answers *per kind, purely*. |
| C5 | Phase 4 added `data-unseen-marker` to phase 3's marker via a `page.tsx` edit (its "edit F") and a CSS rule in phase 3's stylesheet; its own handoff said phase 3 might prefer to own it | Duplicate work / file collision | 3, 4 | **Assigned wholly to phase 3 — the attribute is deleted, not moved.** Phase 3's rule can select its own hashed `.new` class, which is in scope only inside its module, so no hook attribute is needed at all. Phase 4's edit F and its Step 4 (the CSS) are deleted; phase 4 no longer opens `journal.module.css` and its edits drop from six to four. |
| C6 | Phase 4's `page.tsx` edits quoted guessed anchors: the seen-set local, the `options` shape, the tooltip copy, the `InsightCard` signature | File collision | 3, 4 | Every anchor rewritten to phase 3's real names (`seenIds`, `{ id, heading, total, tip, n, Icon }`, `badgeTip`, `InsightCard({ insight, tone, unseen })`) and all "adapt at implement time" hedging deleted. Phase 3 is explicitly told **not** to remove `JournalGroup.entries`, which phase 2's `view.test.ts` asserts. |
| C7 | Phase 4's island did `card.removeAttribute('data-unseen')` while phase 3's `.new` is `display:none` unless `[data-unseen='true']` — so the dot would collapse its box instantly and the fade phase 4 designed could never run | Contract drift (found during reconciliation) | 3, 4 | Phase 3 gains `.card[data-unseen='true'] .new, .card[data-seen-now] .new { display: inline-block }` plus `.card[data-seen-now] .new { opacity: 0; transition: … }`. Phase 4's island writes `data-unseen="false"` (never removes it) **and** sets `data-seen-now`, so the dot keeps its box and fades. Invariant 5 holds to the pixel, and `isUnseenAttr` reads the same spelling before and after a live mark. |
| C8 | Phase 3 argued for a deliberately uniform tooltip at zero ("Risks we see · 0 new of 4"); phase 2's `badgeTip` special-cases zero ("… · 4 entries, all seen") and empty ("… · none yet"), with tests asserting it | Contract drift | 2, 3 | Phase 2 owns the copy and its wording is tested, so `badgeTip` wins; phase 3's paragraph is deleted and its manual checks now quote `badgeTip`'s actual strings. The zero phrasing is now reachable live, which C3's resolution handles for free. |
| C9 | Phase 3's handoff told phase 5 to compute the rail total "the same way from phase 2's exported function" — contradicting C4's resolution | Ordering / contract drift | 3, 5 | Phase 3's handoff rewritten: phase 5 takes phase 1's `unseenCount`, and the handoff states why (the `null`) and that the two agree on every successful read. |

### Checked and already consistent — do not re-open

| Check | Finding |
|---|---|
| Phase 4's `MAX_BATCH = 50` vs phase 1's `MAX_SEEN_BATCH = 500` and its 500-id route cap | Compatible (50 ≤ 500). They **cannot** share a constant — `lib/sera/seen.ts` is server-only — so the relationship is now stated explicitly in both files' plans, each comment names the other, and phase 4's verification greps the pair. A client cap above the server's would turn every full flush into a silent `400`, since the route returns no body and the island swallows failures. |
| Phase 4's `isUnseenAttr` vs phase 3's `data-unseen="true"\|"false"` | They agree. `isUnseenAttr('false') === false`, so a card rendered `data-unseen="false"` is read as **seen**, not as unseen-because-present. Its tolerance for present-and-empty / `"1"` / `"0"` is unreachable from phase 3's render and harmless; it is kept and the test now names the two real spellings first. Strengthened by C7: the island writes `"false"` rather than deleting the attribute, so there is one spelling, always. |
| `export const dynamic = 'force-dynamic'` — phase 1 said phase 3 adds it to `page.tsx`, and phase 3's contract does create it | No double-add. Two files, one declaration each: phase 1's is in `web/app/api/sera/journal/seen/route.ts` (which phase 3 never opens), phase 3's is in `page.tsx` (which phase 1 never opens). Stated in both plans. |
| `journal_seen` and `engine/src/seer_engine/demo.py`'s `DEMO_TABLES` | No phase adds it, and phase 1 says so explicitly. Confirmed by grep across all five plan files: `demo.py` appears once, in phase 1's handoff, as a prohibition. Recorded as a decision below so a later session does not "fix" the omission. |
| Phase 2's green-ness — the seen-set parameter staying **optional** while `page.tsx` is byte-identical | Holds. Phase 2's plan still makes it optional with a `NOTHING_SEEN` default, keeps `JournalGroup.entries`, and its exit criteria make "`tsc` clean with `page.tsx` untouched" the load-bearing check. Phase 3 does not assume otherwise — it passes three arguments. No phase leaves the tree uncompilable at its own boundary. |
| Every **Impact Point** in the analysis owned by exactly one phase | 1–3 → phase 1; 4–5 → phase 2; 6 → phase 3 then phase 4 (sequenced, anchors reconciled); 7 → phase 3 **alone** after C5; 8–9 → phase 4; 10–12 → phase 5; 13 → phase 5. No gaps, no shared ownership. |

### Environment note carried into every phase

`web/node_modules` in this worktree is already a symlink to `/home/miftah/seer/web/node_modules`
(`package.json` and `package-lock.json` are byte-identical to the base commit), and
`cd web && npx tsc --noEmit` is confirmed clean on the base tree. Phase 2's plan opened its
verification with "run `npm ci` or symlink first"; that is replaced, in every plan, with a note
that the link exists and an instruction **not** to install. Verification commands are
`cd web && npx tsc --noEmit` and `cd web && npm test`.

## Decisions

Every behavioural fork settled during reconciliation, with the rung of the precedence ladder that
settled it. **An executor should read this instead of re-litigating any of it.**

| # | The fork | Chosen | Ladder rung |
|---|---|---|---|
| D1 | The rail's unseen total: phase 1's `unseenCount` (`null` on failure) vs phase 2's `unseenCounts(...).all` (empty set on failure) | `unseenCount`, with no badge on `null` or `0` | **Stated invariant** — invariant 9, "a failed seen-state read degrades … the page still renders", read together with phase 5's exit criterion "no badge". An empty `Set` cannot express failure, so only one branch satisfies the invariant. |
| D2 | How the two surfaces degrade when Neon is down: the page shows everything unseen, the rail shows nothing | Keep both, deliberately divergent | **Stated invariant**, then **the index's Why**. The page is rendering the entries anyway and "all new to you" is the safe reading for a list; the rail is a bare number, and R3's "a new number is a real signal" makes silence the right failure mode for it. Documented in phase 5's readme edits so it reads as a decision, not a bug. |
| D3 | Tooltip copy: one `badgeTip` formatter vs a `data-tip-template` the island interpolates | `badgeTip`, called by both the server render and the client island | **Phase exit criteria** — phase 2's exit criteria make `badgeTip`'s wording a tested contract; a template would have put the same words in two places with only one of them tested. Enabled by verifying `view.ts` is client-safe. |
| D4 | Tooltip at zero: uniform "0 new of 4" (phase 3's argument) vs `badgeTip`'s "4 entries, all seen" | `badgeTip`'s phrasing | **Phase exit criteria**, then **the plans' code blocks** — phase 2's `view.test.ts` asserts the three strings; phase 3 offered prose, not a tested contract. |
| D5 | The partition's shape and whether phase 3 adapts it | Phase 2's `unseen` / `seen` / `items` / `unseenCount`, rendered directly; no adapter | **The plans' code blocks** — phase 2's `view.ts` is written out in full and phase 3's `split()` was explicitly a guess against it. One owner per file region: `view.ts` is phase 2's. |
| D6 | Who owns the unseen marker's live retirement — the `data-unseen-marker` attribute and its CSS | Phase 3 owns the element, the attribute hook and the rule; phase 4 only sets `data-unseen="false"` + `data-seen-now` | **Surrounding code's convention** — a CSS Module rule needs the hashed class, which exists only inside the module that declares it, so splitting the rule from the stylesheet would have been the odd choice. Reinforced by the analysis's impact point 7 ("owned by phase 3; phase 4 adds nothing to it"). |
| D7 | Retiring a marker: collapse the dot (`display:none`) vs fade it in place (`opacity: 0`) | Fade in place, with the box kept by `[data-seen-now]` | **Stated invariant** — invariant 5, "marking an entry seen during a visit changes the badges and the per-card marker, never the position of a card". A collapsing box reflows the title beside it. |
| D8 | The live bar: lift it into a client component vs patch the server markup through `data-` hooks | `data-` hooks on phase 3's markup | **The plans' code blocks** — `options` carries `Icon: LucideIcon`, a function, which a server component cannot pass across the client boundary; the lift would also have cut phase 3's bar out from under it one phase later. Phase 4 already argued and chose this; the reconciler only removed the "planner picks one" language from the index. |
| D9 | `journal_seen` in `engine/src/seer_engine/demo.py`'s `DEMO_TABLES` | **Not added**, by any phase | **The index's Why and Scope** — seen-state is *reader* state, and the demo purge exists to reset demo *data*. Wiping what the owner has read would reset every badge to the full inventory, which is the exact failure this set was written to remove. Recorded here so a later session reading `DEMO_TABLES` does not "complete" the list. |
| D10 | Phase 5's `Depends on`: the draft's `1` (what its code needs) vs `1, 2, 3, 4` (what its readme needs) | `1, 2, 3, 4` | **Phase exit criteria** — phase 5's own plan instructs the session to read phases 2–4's files before writing three of its readme edits, and its exit criterion is a readme that "lists every file this set added". Running it early would document files that do not exist. |

## Open Questions

**None.** Every fork above was decidable on the ladder, and no branch of any of them was
irreversible — nothing in this set destroys data, rewrites published history, or performs an
unrepeatable migration. Every requirement id (R1, R2, R3) is owned by at least one phase, and
every impact point in the analysis is owned by exactly one. The set is ready to launch
unattended.

## Rollback

**Per phase**

- Phase 5: revert the commit. The rail loses its badge; the Journal's own seven badges are
  untouched.
- Phase 4: revert the commit. Nothing marks entries seen any more, so the badges freeze at
  whatever the table holds; the page still renders, still sorts unseen-first, still counts
  correctly.
- Phase 3: revert the commit. The page returns to total counts and a flat newest-first list;
  phases 1 and 2 are dead code that still builds and still tests green.
- Phase 2: revert the commit. `view.ts` returns to its current signatures.
- Phase 1: revert the commit, then `DROP TABLE journal_seen` and delete the
  `012_journal_seen.sql` row from `schema_migrations`. Nothing else in the schema references it.

**As a whole**

`git revert` the merge, or delete `feature/journal-unseen-badges` before it lands. The only
out-of-tree artefact is the `journal_seen` table, which nothing else reads; leaving it in place
costs nothing and makes a re-land cheap.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f JOURNAL_UNSEEN_BADGES_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f JOURNAL_UNSEEN_BADGES_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan JOURNAL_UNSEEN_BADGES_PLAN.md
