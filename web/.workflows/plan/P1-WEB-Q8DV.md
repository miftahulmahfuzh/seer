> Adopted from `JOURNAL_UNSEEN_BADGES_PLAN.md` phase 4. Source: `.workflows/plan/journal-unseen-badges/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: The client island: dwell, click, batch, flush, live countdown

**Plan set:** `JOURNAL_UNSEEN_BADGES_PLAN.md`
**Analysis:** `20261007-103957-J4N8_code_analyzer.md`
**Satisfies:** R2 (a working definition and mechanism for "seen" — the click rule *and* the rule for the items with no arrow), R3 (the badge is the true unseen count, and it falls while you read)
**Depends on:** Phase 1 (the POST endpoint), Phase 3 (the DOM hooks and the server-rendered bar)
**Difficulty:** HARD
**Package:** `web/app/sera/journal`

---

## READ THIS FIRST — the two sibling contracts, reconciled

### 1. `page.tsx` is a shared file. Phase 3 rewrites it before you.

**Do not paste a whole `page.tsx`.** Phase 3 lands its edit first and the file you open will not
be the file quoted in the analysis. Read `web/app/sera/journal/page.tsx` **as it stands after
phase 3 has landed** and apply the four surgical edits in [Step 4](#step-4-pagetsx--four-surgical-edits-on-top-of-phase-3s)
to it. Nothing in this phase rewrites phase 3's markup, copy, counts, boundary or card structure.

**The reconciler has read phase 3's plan and rewritten every anchor in Step 4 to phase 3's real
names.** The ones that matter:

| What | Phase 3's actual name / shape |
|---|---|
| the seen-set local in `JournalPage` | **`seenIds`** (a `Set<number>`), not `seen` — phase 3 avoids `seen` on purpose, because a group's seen half is called that |
| the `options` entries | `{ id, heading, total, tip, n, Icon }` — phase 3 already carries `heading` and `total` **for this phase to use**; this phase adds no field to `options` |
| the tooltip copy | built by phase 2's `badgeTip(heading, unseen, total)`; there is **no `data-tip-template`** anywhere in this set |
| `InsightCard` | `({ insight, tone, unseen }: { insight: LabInsight; tone: string; unseen: boolean })` — this phase does not touch it at all |
| the unseen marker | `<span className={s.new} data-tip={SEEN_COPY.marker}>` inside the card title; **phase 3 owns both the element and the CSS that fades it.** This phase adds no attribute to it and touches `journal.module.css` not at all |
| per-card state hooks | `data-insight-id="<id>"` and `data-unseen="true"|"false"` on every `<article>`, `data-seen-click="true"` on each redirect-arrow `<Link>` |

### 2. The endpoint contract, as phase 1 actually fixed it

`POST /api/sera/journal/seen`, body `{"ids": number[], "via"?: "view" | "click"}`, `204` on
success, `400` on a malformed body, `404` to anyone the `/sera` gate rejects, `500` on a failed
write, and **never a response body**. Content-Type is ignored — the handler does
`JSON.parse(await req.text())` — so a `sendBeacon` `Blob` of `text/plain;charset=UTF-8` is
accepted exactly like `application/json`. All of that matches what this plan codes against.

**The batch caps, and the relationship between them.** Phase 1 exports
`MAX_SEEN_BATCH = 500` from `web/lib/sera/seen.ts` and its route rejects a body with more than
500 ids as `400`. This phase's `MAX_BATCH = 50` is the client's own, smaller cap: it is what
`createSeenQueue` splits a flush at, so no single request can ever carry more than 50 ids.

> **The invariant between them: `MAX_BATCH` ≤ `MAX_SEEN_BATCH`.** 50 ≤ 500 holds today with
> room to spare. The island **cannot** `import { MAX_SEEN_BATCH }` — `lib/sera/seen.ts` is
> server-only and builds the Neon client at module scope — so the number is restated here, and
> both sides carry a comment naming the other. If either is ever changed, check the other: a
> `MAX_BATCH` above `MAX_SEEN_BATCH` turns every full flush into a silent `400`, and because the
> route never returns a body and this island swallows failures, nothing would surface it except
> ids that never stop being requeued.

Still open `web/app/api/sera/journal/seen/route.ts` as it stands after phase 1 landed before you
write the fetch. If it disagrees with the above, phase 1 drifted from its own plan — raise it
rather than bending `seen-client.ts` around it. If you do have to adjust `SEEN_ENDPOINT`,
`seenRequestBody()` or `MAX_BATCH`, each is a single line in one file; say so in the commit
message.

---

## Goal

After this phase a Journal entry becomes *seen* by one of two rules the reader never has to think
about: clicking its redirect-arrow, or letting it sit on screen in a foreground tab long enough to
have been read. Newly-seen ids are batched in the browser, posted to phase 1's endpoint, and
flushed on page-hide with `navigator.sendBeacon`, so nothing is lost when the reader leaves. While
they read, the seven badge numbers count down in place — that is the "excitement" the user asked
for — without a single card moving (invariant 5) and without the page ceasing to be a server
component.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing.

**Renames:** nothing.

**Creates — new files:**

- `web/app/sera/journal/seen-client.ts` (new, pure, DOM-free). Exports:
  - constants: `SEEN_ENDPOINT`, `VISIBLE_FRACTION`, `TALL_VIEWPORT_FRACTION`, `DWELL_MS`,
    `FLUSH_IDLE_MS`, `MAX_BATCH`, `OBSERVER_THRESHOLDS`
  - types: `SeenVia`, `SeenBatch`, `BadgeKey`, `UnseenByKind`, `BadgeMeta`, `RectLike`, `SeenQueue`
  - functions: `isUnseenAttr`, `isOnScreen`, `badgeCounts`, `seenRequestBody`, `createSeenQueue`
- `web/app/sera/journal/seen-client.test.ts` (new, vitest, node env — no DOM, no network)
- `web/app/sera/journal/JournalSeen.tsx` (new, `'use client'`). Exports:
  - `JournalSeen` — a React component rendering `null`
  - `JournalSeenProps = { unseenByKind: Record<InsightKind, number[]>; badgeMeta: BadgeMeta; zeroClass: string }`

**Creates — new symbols in `page.tsx` (phase 3's file, second edit):**

- local `const unseenByKind: Record<InsightKind, number[]>` in `JournalPage`
- local `const badgeMeta` in `JournalPage`, derived from phase 3's `options` array

**Nothing is added to the `options` array.** Phase 3 already carries `heading` and `total` on
every entry precisely so this phase can read them; there is no `tipTemplate` field and no
`data-tip-template` attribute.

**Creates — new DOM contract this phase introduces (none of these exist before this phase):**

| Attribute | Rendered on | By | Read by |
|---|---|---|---|
| `data-badge-kind="all" \| <InsightKind>` | the badge `<span>` inside each of the seven tab `<Link>`s | `page.tsx` (this phase) | `JournalSeen` |
| `data-seen-now` | an `InsightCard` `<article>`, set imperatively when the island marks it (alongside `data-unseen="false"`) | `JournalSeen` (this phase) | `journal.module.css` — **phase 3's rule**, not this phase's |

**Creates — no CSS.** `journal.module.css` is phase 3's file and this phase does not open it.
The fade that retires a marker live (`.card[data-seen-now] .new { opacity: 0 }`, plus the
companion rule that keeps the dot's box so the title does not reflow) is written by phase 3, in
the module where the hashed `.new` class is in scope. There is no `data-unseen-marker` attribute
in this plan set. This phase's whole part in it is setting the two attributes.

**Signature changes:** none to any exported symbol anywhere. `view.ts` is not edited.

**Requires (from earlier phases):**

- **Phase 1** — `POST /api/sera/journal/seen` exists, accepts `{"ids": number[], "via": "view" |
  "click"}` with Content-Type ignored, answers `204`/`400`/`404`/`500` with no body, and caps a
  request at `MAX_SEEN_BATCH = 500` ids. This phase's `MAX_BATCH = 50` must stay ≤ that; see the
  pre-flight note above.
- **Phase 2** — `badgeTip(heading, unseen, total): string`, exported from
  `app/sera/journal/view.ts`. **This phase imports it**, which is allowed and checked:
  `view.ts` imports only `lib/sera/glossary` and `lib/sera/types`; `types.ts` imports nothing,
  `glossary.ts` imports only types (`./derive`, `./types`) beyond its own data, and neither
  touches `lib/db`, `lib/sera/lab` or anything `next/*`-server. So the island may import it
  without dragging `lab.json` or the Neon client into the client bundle. It is the single
  formatter for all seven tooltips; this phase does **not** re-implement the string.
- **Phase 3** — every insight card `<article>` carries `data-insight-id="<id>"`.
- **Phase 3** — every insight card `<article>` carries `data-unseen="true"` or
  `data-unseen="false"`, **always present, always a string**. `isUnseenAttr` reads `"true"` as
  unseen and `"false"` as seen, so the two agree: a card rendered `data-unseen="false"` is read
  as **seen**, never as unseen-because-the-attribute-is-there. (`isUnseenAttr` also tolerates
  present-and-empty and `"1"`/`"0"`, which phase 3 never emits; that tolerance is harmless and
  stays, because the island also removes nothing — it writes `"false"` rather than deleting the
  attribute, so the reading never drifts between a fresh render and a live update.)
- **Phase 3** — the redirect-arrow `<Link>` inside `InsightCard` carries `data-seen-click="true"`.
  Select on presence (`[data-seen-click]`), never on the value.
- **Phase 3** — `page.tsx` holds the seen-set in a local named **`seenIds`** (`await
  seenInsightIds()`). Step 4 edit B reads it by that name.
- **Phase 3** — `journal.module.css` exports a `zero` class (it already does today at
  `journal.module.css:13`) and `page.tsx` imports the module as `s`.
- **Phase 3** — the seven-tab bar is still a server-rendered `<nav className="seg">` built from an
  `options` array whose entries carry `id`, `heading`, `total`, `tip`, `n`, `Icon`.
- **Phase 3** — `journal.module.css` carries `.card[data-seen-now] .new { opacity: 0; … }` and the
  companion rule that keeps the dot's box. This phase sets the attribute; phase 3 styles it.

**Leaves alone (owned by others):**

- `web/app/sera/journal/view.ts`, `view.test.ts` (Phase 2) — **not edited.** `badgeTip` is
  imported from it (pure, client-safe; see Requires). Nothing else is: `unseenByKind` is derived
  straight from `lab.insights` and the seen-set in `page.tsx`, on the server, so the island takes
  no dependency on the partition shape.
- `web/lib/sera/seen.ts`, `web/app/api/sera/journal/seen/route.ts` (Phase 1) — consumed over HTTP,
  never edited, never imported (server-only).
- `web/app/sera/journal/journal.module.css` (Phase 3) — **not opened by this phase at all.**
- `web/components/sera/SeraNav.tsx`, `SeraNav.module.css`, `web/app/sera/layout.tsx`,
  `web/package_readme.md` (Phase 5).
- Everything phase 3 wrote in `page.tsx`: the counts, the copy, the boundary, the card structure,
  the `options` fields, the `.badge` / `.zero` styling, the `.cards` grid and its 1023.98px
  breakpoint.

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/journal/seen-client.ts` | create | the policy constants, the dwell threshold arithmetic, the badge countdown arithmetic, the queue — pure, DOM-free |
| `web/app/sera/journal/seen-client.test.ts` | create | vitest over all of the above; runs with no DOM and no connection |
| `web/app/sera/journal/JournalSeen.tsx` | create | `'use client'` glue: one `IntersectionObserver`, dwell timers, a delegated click listener, the flush paths, and the repaint |
| `web/app/sera/journal/page.tsx` | modify (2nd edit, after phase 3) | four surgical edits: import, two derived locals, one attribute on the badge span, mount `<JournalSeen>` |

`journal.module.css` is **not** in this table. Phase 3 owns every rule the marker needs,
including the `[data-seen-now]` fade this phase triggers.

---

## The policy, and why each number is what it is

Every number lives in one exported block at the top of `seen-client.ts`.

| Constant | Value | Why |
|---|---|---|
| `VISIBLE_FRACTION` | `0.6` | How much of a card must be in frame to count as on screen. Past the halfway mark, so a card merely peeking in at the bottom edge of the viewport never starts a dwell, while a card the reader actually scrolled to has its title and most of its body in view. |
| `TALL_VIEWPORT_FRACTION` | `0.75` | The fallback for a card **taller than the viewport**, where `VISIBLE_FRACTION` is unreachable by arithmetic — a card twice the viewport's height can show at most half of itself, which is below 0.6 forever. Such a card counts as on screen once it fills three quarters of the viewport instead: at that point the reader is looking at nothing else. The two rules are a single `||`, with no "is it tall?" branch, so there is no boundary case to get wrong; the tall clause is simply unreachable for a card shorter than `0.75 × viewport`. |
| `DWELL_MS` | `2500` | Continuous, foreground, on-screen time before the card counts as read. Scrolling past at speed leaves a card in frame for a few hundred milliseconds — well under this, so a fast scroll-through marks nothing. Stopping to read even a two-sentence insight takes longer than 2.5s. |
| `FLUSH_IDLE_MS` | `1500` | Quiet time after the last mark before the queue is posted. Reading down a section marks a run of cards in quick succession; 1.5s coalesces that run into one request, and still lands the write long before the reader leaves. |
| `MAX_BATCH` | `50` | Hard cap on one request's `ids`. Comfortably above the whole snapshot today (26 insights), so an entire read-through is a single POST, and it bounds the body no matter what. **Must stay ≤ phase 1's `MAX_SEEN_BATCH` (500)**, which the route enforces with a `400`; 50 ≤ 500 holds with room to spare. The two cannot share a constant — `lib/sera/seen.ts` is server-only — so each carries a comment naming the other. See the pre-flight note at the top of this plan. |
| `OBSERVER_THRESHOLDS` | `[0, 0.05, … 1]` (21 even steps) | `isOnScreen` compares pixel heights, not the observer's own `intersectionRatio`, so the ratio at which the decision flips is not a fixed number — it depends on the card's height against the viewport's. An even 5%-step ladder keeps the callback firing close enough to wherever the crossing actually is, at negligible cost for ~26 observed nodes. |

**`document.visibilityState` is a precondition, not a modifier.** A hidden tab marks nothing:
the observer callback refuses to start a dwell when the document is not visible; a
`visibilitychange` to hidden **cancels** every running dwell timer outright rather than pausing it
(so a tab backgrounded at 2.4s and restored a minute later starts its 2.5s over); and the dwell
timer re-checks `visibilityState` when it fires, closing the race where the tab is hidden between
the timer being set and firing. On returning to visible, the island re-observes its targets — an
`IntersectionObserver` does not re-fire on its own, but `unobserve` + `observe` delivers a fresh
entry with the current geometry, which restarts the dwell for whatever is on screen.

## The live badge countdown: approach (b), and why

> Pick ONE approach and state why: (a) lift just the bar into a small client component fed by
> server-computed props, or (b) have the island update the badge text through `data-` hooks on
> the existing markup.

**This phase takes (b).** Reasons, in order of weight:

1. **JS-disabled correctness is structural, not a promise.** The bar stays exactly the server-
   rendered markup phase 3 wrote. With JavaScript off the numbers are the ones the server computed
   from the seen-set and nothing patches them. Under (a) the bar would be a client component that
   happens to SSR correctly — true, but a property that a later careless `useState` initialiser
   could quietly break.
2. **Nothing of the page ships to the browser but seven numbers' worth of integers.** `lab.json` is
   0.89 MB and `lib/sera/lab.ts` warns in its header that it must not reach the client. Under (b)
   the island's entire payload is `unseenByKind` — one integer per unseen insight, 26 today, a few
   hundred at worst — plus one class-name string. No insight titles, no markdown bodies, no icons,
   no `<Link>` tree.
3. **It is the smaller diff to the shared file.** `page.tsx` is rewritten by phase 3 immediately
   before this phase. (b) adds two attributes, one derived local, one field on `options` and one
   element; (a) would cut the whole 16-line bar out of phase 3's render and move it into a new
   file — a near-guaranteed conflict with whatever phase 3 did to that exact block.
4. **Tooltips survive either way, so they are not a tiebreaker.** `components/tooltip.ts` reads
   `el.getAttribute('data-tip')` at show time, so rewriting the attribute is enough. This phase
   keeps the tooltip truthful by calling **phase 2's `badgeTip(heading, unseen, total)`** again
   with the live count and setting `data-tip` and `aria-label` on the enclosing `<Link>`. The
   heading and the total come from phase 3's `options` array, handed over as the `badgeMeta`
   prop. There is no template string and no `data-tip-template` attribute: one formatter in
   `view.ts`, called by the server render and by the island, so the wording can never fork.

**The arithmetic that makes (b) safe.** Imperatively patching React-owned DOM has one real hazard:
React re-renders the bar on a soft navigation (a tab click is `<Link replace scroll={false}>`) and
writes the server's numbers back over the patched ones. The fix is to make the displayed number a
*pure function of two things that are both correct at any moment*, and to re-apply it after every
commit:

```
displayed(kind) = count of ids in unseenByKind[kind] that are NOT in the session's marked set
displayed('all') = the sum of the six
```

This is `badgeCounts()` in `seen-client.ts`, and it is idempotent under any number of re-applies:

- It never subtracts from a base, so it cannot double-count.
- After a soft navigation the server recomputes `unseenByKind` — ids already flushed simply are
  not in the lists any more, and filtering them by the marked set is then a harmless no-op.
- Ids marked but not yet flushed are still in the server's lists, and the marked set removes them.
  The number is right either way, which is why **no extra flush is needed on a tab switch**.

The repaint runs in a `useEffect` **with no dependency array** — that is the point: it must run
after every commit, because a commit is exactly when React may have overwritten the badge text.
Painting seven `<span>`s and a handful of attributes is free.

---

## Implementation Steps

### Step 1: `seen-client.ts` — the policy, the arithmetic, the queue

**File:** `web/app/sera/journal/seen-client.ts` (new)
**Change:** The whole pure layer. No DOM, no network, no database (invariant 3). Imports only
`lib/sera/types`, which `view.ts` already imports the same relative way (`view.ts:3`).

**Code:**

```ts
/**
 * The Journal's "seen" policy and queue. Pure: no DOM, no network, no database (plan invariant 3).
 * JournalSeen.tsx is the thin glue that reads the DOM and posts; everything decidable without a
 * browser lives here and is covered by seen-client.test.ts.
 */
import { INSIGHT_KINDS, type InsightKind } from '../../../lib/sera/types';

// ---------------------------------------------------------------------------
// Policy. Every number the island's behaviour depends on is here, so it is tuned in one place.
// ---------------------------------------------------------------------------

/** Where a batch of newly-seen ids is posted. Phase 1 owns the route handler. */
export const SEEN_ENDPOINT = '/api/sera/journal/seen';

/**
 * How much of a card must be in frame to count as "on screen". 0.6 is past the halfway mark, so a
 * card merely peeking in at the bottom edge never starts a dwell, while a card the reader actually
 * scrolled to has its title and most of its body in view.
 */
export const VISIBLE_FRACTION = 0.6;

/**
 * The fallback for a card TALLER than the viewport, where VISIBLE_FRACTION is unreachable by
 * arithmetic: a card twice the viewport's height can show at most half of itself. Such a card
 * counts as on screen once it fills this much of the viewport instead — at that point the reader
 * is looking at nothing else. Unreachable for a card shorter than this fraction of the viewport,
 * so the two rules need no "is it tall?" branch between them.
 */
export const TALL_VIEWPORT_FRACTION = 0.75;

/**
 * Continuous, foreground, on-screen time before a card counts as read. Scrolling past at speed
 * leaves a card in frame for a few hundred milliseconds, well under this, so a fast scroll-through
 * marks nothing; stopping to read even a two-sentence insight takes longer.
 */
export const DWELL_MS = 2_500;

/**
 * Quiet time after the last mark before the queue is posted. Reading down a section marks a run of
 * cards in quick succession; this coalesces the run into one request while still landing the write
 * long before the reader leaves the page.
 */
export const FLUSH_IDLE_MS = 1_500;

/**
 * Hard cap on one request's `ids`. 50 is comfortably above the whole snapshot today (26 insights),
 * so an entire read-through is a single POST, and it bounds the body no matter what.
 *
 * MUST STAY <= MAX_SEEN_BATCH (500) in web/lib/sera/seen.ts, which the POST route enforces with a
 * 400. The two cannot share a constant: seen.ts is server-only and builds the Neon client at
 * module scope, so importing it here would drag the database into the browser bundle. If either
 * number changes, check the other -- a MAX_BATCH above the server's cap turns every full flush
 * into a silent 400 (the route returns no body and this island swallows failures).
 */
export const MAX_BATCH = 50;

/**
 * Thresholds for the IntersectionObserver. `isOnScreen` compares pixel heights rather than the
 * observer's own ratio, so the ratio at which the decision flips depends on the card's height
 * against the viewport's and is not a fixed number — an even 5%-step ladder keeps the callback
 * firing close enough to wherever the crossing actually is.
 */
export const OBSERVER_THRESHOLDS: readonly number[] = Array.from({ length: 21 }, (_, i) => i / 20);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** How an entry came to be seen. Mirrors the `via` column phase 1's table constrains. */
export type SeenVia = 'view' | 'click';

/** One request's worth of ids, all marked the same way. */
export type SeenBatch = { ids: number[]; via: SeenVia };

/** The seven tabs: the `all` sentinel first, then the six kinds. */
export type BadgeKey = InsightKind | 'all';

/** The server's view of what is still unseen, per kind, as of this render. */
export type UnseenByKind = Readonly<Record<InsightKind, readonly number[]>>;

/**
 * Per tab, the two arguments view.ts's badgeTip needs beside the live count. page.tsx derives it
 * from its own `options` array, so the heading and the total are the server's, not restated here.
 */
export type BadgeMeta = Readonly<Record<BadgeKey, { heading: string; total: number }>>;

/** A height-bearing rectangle. DOMRect and DOMRectReadOnly both satisfy it structurally. */
export type RectLike = { readonly height: number };

// ---------------------------------------------------------------------------
// Pure decisions
// ---------------------------------------------------------------------------

/**
 * Reads a card's `data-unseen` hook.
 *
 * Phase 3 renders it on EVERY card, always as the string "true" or "false", so the two readings
 * that matter are exactly those: "true" is unseen, "false" is seen. A card rendered
 * data-unseen="false" is seen, never "unseen because the attribute is present".
 *
 * Present-and-empty and "1"/"0" are tolerated too, which phase 3 never emits -- cheap insurance,
 * and it costs nothing because the island never deletes the attribute either: marking a card
 * live writes "false" over it rather than removing it, so the reading is the same before and
 * after. Absent is seen.
 */
export function isUnseenAttr(raw: string | null | undefined): boolean {
  if (raw === null || raw === undefined) return false;
  const v = raw.trim().toLowerCase();
  return v !== 'false' && v !== '0';
}

/**
 * Does this card count as "on screen" right now?
 *
 * `bounds` is the card's own rectangle, `intersection` the part of it inside the viewport (null
 * when it is not intersecting at all), `viewportHeight` the observer root's height.
 *
 * Rule one: at least VISIBLE_FRACTION of the card is in frame.
 * Rule two, for a card too tall for rule one ever to fire: it fills TALL_VIEWPORT_FRACTION of the
 * viewport. Rule two is unreachable for a card shorter than that fraction of the viewport, so the
 * two are a plain `||` with no branch between them.
 */
export function isOnScreen(
  bounds: RectLike,
  intersection: RectLike | null,
  viewportHeight: number,
): boolean {
  const visible = intersection ? intersection.height : 0;
  if (visible <= 0) return false;
  if (bounds.height > 0 && visible >= bounds.height * VISIBLE_FRACTION) return true;
  return viewportHeight > 0 && visible >= viewportHeight * TALL_VIEWPORT_FRACTION;
}

/**
 * The seven badge numbers: what the server still calls unseen, minus what this session has marked.
 *
 * Never subtracts from a running base, so it is idempotent however many times it is re-applied —
 * which is what lets the island repaint React-owned badge text after every commit without ever
 * double-counting. Ids in `marked` that the server has already recorded are simply absent from
 * `unseen`, and filtering them is then a no-op.
 */
export function badgeCounts(unseen: UnseenByKind, marked: ReadonlySet<number>): Record<BadgeKey, number> {
  const out = { all: 0 } as Record<BadgeKey, number>;
  for (const kind of INSIGHT_KINDS) {
    let n = 0;
    for (const id of unseen[kind] ?? []) if (!marked.has(id)) n += 1;
    out[kind] = n;
    out.all += n;
  }
  return out;
}

/** The request body phase 1's route parses, as a string (sendBeacon needs one, fetch takes one). */
export const seenRequestBody = (batch: SeenBatch): string =>
  JSON.stringify({ ids: batch.ids, via: batch.via });

// ---------------------------------------------------------------------------
// The queue
// ---------------------------------------------------------------------------

/**
 * Two sets, deliberately: `marked` is every id this session has decided is seen and never shrinks
 * (it drives the badge countdown and stops an id being posted twice); `pending` is the subset not
 * yet successfully posted. A failed POST returns ids to `pending` but leaves `marked` alone, so the
 * badge stays down and the write simply rides along with the next flush (invariant 6: additive and
 * idempotent — re-posting an id costs one `ON CONFLICT DO NOTHING`).
 */
export type SeenQueue = {
  /** Queue an id. False when it is not a usable id, or was already marked this session. */
  add(id: number, via: SeenVia): boolean;
  /** Has this session already marked this id? */
  has(id: number): boolean;
  /** The live set of ids marked this session. Live, so a repaint always reads the latest. */
  marked(): ReadonlySet<number>;
  /** How many ids are waiting to be posted. */
  pendingCount(): number;
  /** Is the pending set at the batch cap? */
  isFull(): boolean;
  /** Drain `pending` into request-sized batches, grouped by `via`. Leaves `marked` untouched. */
  take(): SeenBatch[];
  /** Put batches back after a failed POST. */
  requeue(batches: readonly SeenBatch[]): void;
};

export function createSeenQueue(maxBatch: number = MAX_BATCH): SeenQueue {
  const cap = Math.max(1, Math.floor(maxBatch));
  const marked = new Set<number>();
  const pending = new Map<number, SeenVia>();

  return {
    add(id, via) {
      if (!Number.isInteger(id) || id <= 0) return false;
      if (marked.has(id)) return false;
      marked.add(id);
      pending.set(id, via);
      return true;
    },
    has: (id) => marked.has(id),
    marked: () => marked,
    pendingCount: () => pending.size,
    isFull: () => pending.size >= cap,
    take() {
      const byVia = new Map<SeenVia, number[]>();
      for (const [id, via] of pending) {
        const list = byVia.get(via);
        if (list) list.push(id);
        else byVia.set(via, [id]);
      }
      pending.clear();
      const out: SeenBatch[] = [];
      for (const [via, ids] of byVia) {
        for (let i = 0; i < ids.length; i += cap) out.push({ ids: ids.slice(i, i + cap), via });
      }
      return out;
    },
    requeue(batches) {
      for (const b of batches) {
        for (const id of b.ids) if (!pending.has(id)) pending.set(id, b.via);
      }
    },
  };
}
```

**Impact:** adds a module nothing imports yet. `npx tsc --noEmit` and `npm test` stay green on
their own. No runtime behaviour changes until Step 3.

---

### Step 2: `seen-client.test.ts` — the suite that runs with no connection

**File:** `web/app/sera/journal/seen-client.test.ts` (new)
**Change:** Vitest over everything in Step 1. `web/package.json` runs `vitest run` with **no
config file**, so the environment is node: there is no `document`, no `window`, no
`IntersectionObserver` — which is exactly the discipline invariant 3 asks for, and why the
threshold arithmetic and the queue were pulled out of the island in the first place.

**Code:**

```ts
import { describe, expect, it } from 'vitest';
import { INSIGHT_KINDS, type InsightKind } from '../../../lib/sera/types';
import {
  DWELL_MS, FLUSH_IDLE_MS, MAX_BATCH, OBSERVER_THRESHOLDS, SEEN_ENDPOINT,
  TALL_VIEWPORT_FRACTION, VISIBLE_FRACTION,
  badgeCounts, createSeenQueue, isOnScreen, isUnseenAttr, seenRequestBody,
  type UnseenByKind,
} from './seen-client';

const rect = (height: number) => ({ height });

const unseen = (over: Partial<Record<InsightKind, number[]>> = {}): UnseenByKind =>
  Object.fromEntries(INSIGHT_KINDS.map(k => [k, over[k] ?? []])) as UnseenByKind;

describe('policy constants', () => {
  it('keeps the fractions inside (0, 1]', () => {
    expect(VISIBLE_FRACTION).toBeGreaterThan(0);
    expect(VISIBLE_FRACTION).toBeLessThanOrEqual(1);
    expect(TALL_VIEWPORT_FRACTION).toBeGreaterThan(0);
    expect(TALL_VIEWPORT_FRACTION).toBeLessThanOrEqual(1);
  });

  it('dwells for longer than a scroll-through and flushes while the reader is still there', () => {
    expect(DWELL_MS).toBeGreaterThanOrEqual(1_000);
    expect(FLUSH_IDLE_MS).toBeGreaterThan(0);
    expect(FLUSH_IDLE_MS).toBeLessThan(DWELL_MS * 4);
  });

  it('caps a batch at a positive whole number', () => {
    expect(Number.isInteger(MAX_BATCH)).toBe(true);
    expect(MAX_BATCH).toBeGreaterThan(0);
  });

  it('posts to the Sera-gated route', () => {
    expect(SEEN_ENDPOINT).toBe('/api/sera/journal/seen');
  });

  it('gives the observer an even ladder from 0 to 1', () => {
    expect(OBSERVER_THRESHOLDS[0]).toBe(0);
    expect(OBSERVER_THRESHOLDS[OBSERVER_THRESHOLDS.length - 1]).toBe(1);
    expect([...OBSERVER_THRESHOLDS].sort((a, b) => a - b)).toEqual([...OBSERVER_THRESHOLDS]);
    expect(OBSERVER_THRESHOLDS.length).toBeGreaterThanOrEqual(10);
  });
});

describe('isUnseenAttr', () => {
  // The two phase 3 actually renders, on every card, always as a string. These two cases are the
  // contract; the rest is tolerated noise.
  it('reads phase 3\'s two spellings', () => {
    expect(isUnseenAttr('true')).toBe(true);
    expect(isUnseenAttr('false')).toBe(false);
  });
  it('also accepts present-and-empty and 1 as unseen', () => {
    expect(isUnseenAttr('')).toBe(true);
    expect(isUnseenAttr('1')).toBe(true);
    expect(isUnseenAttr('TRUE')).toBe(true);
  });
  it('treats an absent attribute, false and 0 as seen', () => {
    expect(isUnseenAttr(null)).toBe(false);
    expect(isUnseenAttr(undefined)).toBe(false);
    expect(isUnseenAttr('FALSE')).toBe(false);
    expect(isUnseenAttr(' 0 ')).toBe(false);
  });
});

describe('isOnScreen', () => {
  const VIEWPORT = 800;

  it('is false when the card is not intersecting at all', () => {
    expect(isOnScreen(rect(300), null, VIEWPORT)).toBe(false);
  });

  it('is false for a zero-height sliver', () => {
    expect(isOnScreen(rect(300), rect(0), VIEWPORT)).toBe(false);
  });

  it('is true for a short card fully in frame', () => {
    expect(isOnScreen(rect(300), rect(300), VIEWPORT)).toBe(true);
  });

  it('is false for a short card only half in frame', () => {
    expect(isOnScreen(rect(300), rect(150), VIEWPORT)).toBe(false);
  });

  it('flips exactly at the visible fraction', () => {
    expect(isOnScreen(rect(300), rect(300 * VISIBLE_FRACTION), VIEWPORT)).toBe(true);
    expect(isOnScreen(rect(300), rect(300 * VISIBLE_FRACTION - 1), VIEWPORT)).toBe(false);
  });

  it('falls back to filling the viewport for a card taller than it', () => {
    // 2400px card in an 800px viewport: 0.6 of the card is 1440px, which can never be in frame.
    expect(isOnScreen(rect(2400), rect(800), VIEWPORT)).toBe(true);
    expect(isOnScreen(rect(2400), rect(VIEWPORT * TALL_VIEWPORT_FRACTION), VIEWPORT)).toBe(true);
  });

  it('still refuses a tall card that is mostly out of frame', () => {
    expect(isOnScreen(rect(2400), rect(400), VIEWPORT)).toBe(false);
  });

  it('refuses rather than throws when the viewport height is unknown', () => {
    expect(isOnScreen(rect(2400), rect(400), 0)).toBe(false);
  });
});

describe('badgeCounts', () => {
  const U = unseen({ observation: [5, 3, 1], risk: [9], synthesis: [4] });

  it('counts every kind and the all total with nothing marked', () => {
    const c = badgeCounts(U, new Set());
    expect(c.observation).toBe(3);
    expect(c.risk).toBe(1);
    expect(c.synthesis).toBe(1);
    expect(c.hypothesis).toBe(0);
    expect(c['data-wish']).toBe(0);
    expect(c['feature-wish']).toBe(0);
    expect(c.all).toBe(5);
  });

  it('drops a marked id from its own kind and from the total', () => {
    const c = badgeCounts(U, new Set([3]));
    expect(c.observation).toBe(2);
    expect(c.all).toBe(4);
    expect(c.risk).toBe(1);
  });

  it('is idempotent: re-running with the same marked set gives the same numbers', () => {
    const marked = new Set([3, 9]);
    expect(badgeCounts(U, marked)).toEqual(badgeCounts(U, marked));
    expect(badgeCounts(U, marked).all).toBe(3);
  });

  it('ignores a marked id the server no longer lists as unseen', () => {
    expect(badgeCounts(U, new Set([999])).all).toBe(5);
  });

  it('reaches zero everywhere when everything is marked', () => {
    const c = badgeCounts(U, new Set([5, 3, 1, 9, 4]));
    expect(c.all).toBe(0);
    for (const k of INSIGHT_KINDS) expect(c[k]).toBe(0);
  });

  it('answers all zeroes for an empty snapshot', () => {
    expect(badgeCounts(unseen(), new Set()).all).toBe(0);
  });
});

describe('seenRequestBody', () => {
  it('builds the body phase 1 parses', () => {
    expect(JSON.parse(seenRequestBody({ ids: [2, 7], via: 'view' })))
      .toEqual({ ids: [2, 7], via: 'view' });
    expect(JSON.parse(seenRequestBody({ ids: [11], via: 'click' })))
      .toEqual({ ids: [11], via: 'click' });
  });
});

describe('createSeenQueue', () => {
  it('queues an id once and refuses the repeat', () => {
    const q = createSeenQueue();
    expect(q.add(7, 'view')).toBe(true);
    expect(q.add(7, 'view')).toBe(false);
    expect(q.add(7, 'click')).toBe(false);
    expect(q.pendingCount()).toBe(1);
    expect(q.has(7)).toBe(true);
    expect(q.has(8)).toBe(false);
  });

  it('refuses anything that is not a positive whole id', () => {
    const q = createSeenQueue();
    expect(q.add(0, 'view')).toBe(false);
    expect(q.add(-3, 'view')).toBe(false);
    expect(q.add(1.5, 'view')).toBe(false);
    expect(q.add(Number.NaN, 'view')).toBe(false);
    expect(q.pendingCount()).toBe(0);
  });

  it('takes the pending ids grouped by how they were marked', () => {
    const q = createSeenQueue();
    q.add(1, 'view');
    q.add(2, 'click');
    q.add(3, 'view');
    const batches = q.take();
    expect(batches).toHaveLength(2);
    expect(batches.find(b => b.via === 'view')?.ids).toEqual([1, 3]);
    expect(batches.find(b => b.via === 'click')?.ids).toEqual([2]);
  });

  it('empties pending on take but never forgets what was marked', () => {
    const q = createSeenQueue();
    q.add(1, 'view');
    q.take();
    expect(q.pendingCount()).toBe(0);
    expect(q.take()).toEqual([]);
    expect(q.has(1)).toBe(true);
    expect([...q.marked()]).toEqual([1]);
    expect(q.add(1, 'view')).toBe(false);
  });

  it('splits a take at the batch cap', () => {
    const q = createSeenQueue(3);
    for (const id of [1, 2, 3, 4, 5, 6, 7]) q.add(id, 'view');
    const batches = q.take();
    expect(batches.map(b => b.ids)).toEqual([[1, 2, 3], [4, 5, 6], [7]]);
    expect(batches.every(b => b.via === 'view')).toBe(true);
  });

  it('reports full at the cap and empty again after a take', () => {
    const q = createSeenQueue(2);
    q.add(1, 'view');
    expect(q.isFull()).toBe(false);
    q.add(2, 'view');
    expect(q.isFull()).toBe(true);
    q.take();
    expect(q.isFull()).toBe(false);
  });

  it('puts a failed batch back, keeping how it was marked, without un-marking it', () => {
    const q = createSeenQueue();
    q.add(1, 'view');
    q.add(2, 'click');
    const batches = q.take();
    q.requeue(batches);
    expect(q.pendingCount()).toBe(2);
    expect(q.has(1)).toBe(true);
    const again = q.take();
    expect(again.find(b => b.via === 'view')?.ids).toEqual([1]);
    expect(again.find(b => b.via === 'click')?.ids).toEqual([2]);
  });

  it('never grows pending past the cap through a requeue of the same ids', () => {
    const q = createSeenQueue();
    q.add(1, 'view');
    const b = q.take();
    q.requeue(b);
    q.requeue(b);
    expect(q.pendingCount()).toBe(1);
  });

  it('floors a nonsense cap to one rather than producing empty batches', () => {
    const q = createSeenQueue(0);
    q.add(1, 'view');
    q.add(2, 'view');
    expect(q.take().map(b => b.ids)).toEqual([[1], [2]]);
  });
});
```

**Impact:** `npx vitest run app/sera/journal` now covers both `view.test.ts` (phase 2) and this
file. No DOM, no connection, no fixtures.

---

### Step 3: `JournalSeen.tsx` — the client island

**File:** `web/app/sera/journal/JournalSeen.tsx` (new)
**Change:** The only `'use client'` file this phase adds. It renders `null`: it exists for its
effects. Two effects, in this order:

1. **paint** — no dependency array, so it runs after every commit and re-applies the countdown
   over whatever React just wrote.
2. **wire** — keyed on a content hash of `unseenByKind`, so it tears down and rebuilds the
   observer, the listeners and the timers exactly when the rendered set of cards changes (first
   load, and a tab switch) and not on every repaint.

**Code:**

```tsx
'use client';

import { useEffect, useRef, useState } from 'react';
import type { InsightKind } from '@/lib/sera/types';
// view.ts is pure — it imports only lib/sera/glossary and lib/sera/types, neither of which
// touches lib/db, lib/sera/lab or anything server-only — so a client island may import it.
// badgeTip is the ONE formatter for the seven tab tooltips: the server render calls it, and so
// does the repaint below, which is why the wording cannot fork as the badge counts down.
import { badgeTip } from './view';
import {
  DWELL_MS, FLUSH_IDLE_MS, MAX_BATCH, OBSERVER_THRESHOLDS, SEEN_ENDPOINT,
  badgeCounts, createSeenQueue, isOnScreen, isUnseenAttr, seenRequestBody,
  type BadgeKey, type BadgeMeta, type SeenBatch, type SeenQueue, type SeenVia,
} from './seen-client';

export type JournalSeenProps = {
  /** The ids the server still calls unseen, per kind, as of this render. Integers only. */
  unseenByKind: Record<InsightKind, number[]>;
  /** Per tab, the heading and the total — badgeTip's other two arguments. From page.tsx's options. */
  badgeMeta: BadgeMeta;
  /** `journal.module.css`'s hashed `zero` class, so the island can mute a badge that hits zero. */
  zeroClass: string;
};

const idOf = (el: Element): number => Number(el.getAttribute('data-insight-id'));
const usable = (id: number): boolean => Number.isInteger(id) && id > 0;

/**
 * Marks Journal entries seen, and counts the seven badges down while the reader reads.
 *
 * Two rules, both of them R2's answer: a click on a card's redirect-arrow (`data-seen-click`), and
 * a continuous DWELL_MS of the card being on screen in a visible tab — the second being the only
 * thing that can ever mark the five entries in the snapshot that carry no methodId and therefore
 * have no arrow.
 *
 * It renders nothing. The page stays a server component; this island only reads the hooks phase 3
 * put in the DOM, posts ids to phase 1's endpoint, and repaints seven numbers. It never moves a
 * card (plan invariant 5) and it never surfaces a failure to the reader.
 */
export function JournalSeen({ unseenByKind, badgeMeta, zeroClass }: JournalSeenProps) {
  // One queue for the life of the island: it survives a tab switch, so an id marked before the
  // switch stays off the badges even though the server has not been told yet.
  const queueRef = useRef<SeenQueue | null>(null);
  if (queueRef.current === null) queueRef.current = createSeenQueue(MAX_BATCH);

  // Latest props, readable from callbacks that are not re-created on every render.
  const unseenRef = useRef(unseenByKind);
  unseenRef.current = unseenByKind;
  const metaRef = useRef(badgeMeta);
  metaRef.current = badgeMeta;
  const zeroRef = useRef(zeroClass);
  zeroRef.current = zeroClass;

  // Bumped whenever an id is marked, purely to make React commit so the paint effect runs again.
  const [, setTick] = useState(0);

  // A content key. The prop object is a fresh identity every render, so an effect depending on it
  // would tear down and rebuild the observer constantly; the string only changes when the server's
  // unseen set actually changes — first load, and a tab switch.
  const unseenKey = JSON.stringify(unseenByKind);

  // --- paint ---------------------------------------------------------------
  // No dependency array on purpose. React re-renders this bar on a soft navigation and writes the
  // server's numbers back over the patched ones, so the countdown has to be re-applied after every
  // commit. badgeCounts() never subtracts from a base, so re-applying can never double-count.
  useEffect(() => {
    const marked = queueRef.current!.marked();
    const counts = badgeCounts(unseenRef.current, marked);
    const meta = metaRef.current;
    const zero = zeroRef.current;

    for (const el of Array.from(document.querySelectorAll<HTMLElement>('[data-badge-kind]'))) {
      const key = el.dataset.badgeKind as BadgeKey | undefined;
      if (!key || !(key in counts)) continue;
      const n = counts[key];
      const text = String(n);
      if (el.textContent !== text) el.textContent = text;
      if (zero) el.classList.toggle(zero, n === 0);

      // Keep the tooltip and the accessible name honest by calling view.ts's badgeTip again —
      // the same function page.tsx used for the server render, so the wording cannot fork. The
      // heading and the total come from the page's own `options`, handed over as badgeMeta.
      // tooltip.ts reads data-tip at show time, so rewriting the attribute is enough.
      const m = meta[key];
      const link = el.closest<HTMLElement>('a[data-tip]');
      if (m && link) {
        const tip = badgeTip(m.heading, n, m.total);
        if (link.getAttribute('data-tip') !== tip) {
          link.setAttribute('data-tip', tip);
          link.setAttribute('aria-label', tip);
        }
      }
    }

    // The per-card marker. The card keeps its slot — only its state changes (invariant 5).
    // Both attributes, deliberately: data-unseen="false" is what isUnseenAttr and phase 3's
    // .card[data-unseen='true'] rule read, and data-seen-now is what keeps phase 3's dot in the
    // layout while it fades to opacity 0, so retiring a marker never reflows the title beside it.
    // Write "false" rather than removing the attribute — the island and the server must agree on
    // one spelling, and an absent attribute is a second one.
    for (const id of marked) {
      const card = document.querySelector<HTMLElement>(`[data-insight-id="${id}"]`);
      if (!card) continue;
      if (card.getAttribute('data-unseen') !== 'false') card.setAttribute('data-unseen', 'false');
      if (!card.hasAttribute('data-seen-now')) card.setAttribute('data-seen-now', '');
    }
  });

  // --- wire ----------------------------------------------------------------
  useEffect(() => {
    const queue = queueRef.current!;
    const dwell = new Map<Element, ReturnType<typeof setTimeout>>();
    let idle: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const clearDwell = (el: Element) => {
      const t = dwell.get(el);
      if (t !== undefined) {
        clearTimeout(t);
        dwell.delete(el);
      }
    };
    const clearAllDwell = () => {
      for (const t of dwell.values()) clearTimeout(t);
      dwell.clear();
    };

    // A failed POST is swallowed. The ids go back on the queue for the next flush and the reader
    // is told nothing: this is soft state and a network error over it would be noise.
    const post = (batch: SeenBatch, unloading: boolean) => {
      const body = seenRequestBody(batch);
      if (unloading && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
        // text/plain because sendBeacon sends a Blob; phase 1's route accepts it for this reason.
        const ok = navigator.sendBeacon(
          SEEN_ENDPOINT,
          new Blob([body], { type: 'text/plain;charset=UTF-8' }),
        );
        if (!ok) queue.requeue([batch]);
        return;
      }
      fetch(SEEN_ENDPOINT, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body,
        keepalive: unloading,
        cache: 'no-store',
      })
        .then(res => {
          if (!res.ok) queue.requeue([batch]);
        })
        .catch(() => queue.requeue([batch]));
    };

    const flush = (unloading: boolean) => {
      if (idle !== undefined) {
        clearTimeout(idle);
        idle = undefined;
      }
      for (const batch of queue.take()) post(batch, unloading);
    };

    const scheduleFlush = () => {
      if (idle !== undefined) clearTimeout(idle);
      idle = setTimeout(() => {
        idle = undefined;
        flush(false);
      }, FLUSH_IDLE_MS);
    };

    const mark = (id: number, via: SeenVia) => {
      const added = usable(id) && queue.add(id, via);
      if (added) setTick(t => t + 1);
      // A click navigates away, so it beacons immediately — even for an id dwell already marked,
      // whose 'view' entry may still be sitting in the queue.
      if (via === 'click') {
        flush(true);
        return;
      }
      if (!added) return;
      if (queue.isFull()) flush(false);
      else scheduleFlush();
    };

    // --- the dwell rule ---
    const observer = new IntersectionObserver(
      entries => {
        if (stopped) return;
        const visible = document.visibilityState === 'visible';
        for (const e of entries) {
          const el = e.target;
          const viewport = e.rootBounds?.height ?? window.innerHeight;
          const on =
            visible &&
            isOnScreen(e.boundingClientRect, e.isIntersecting ? e.intersectionRect : null, viewport);
          if (!on) {
            clearDwell(el);
            continue;
          }
          if (dwell.has(el)) continue;
          const id = idOf(el);
          if (!usable(id) || queue.has(id)) continue;
          dwell.set(
            el,
            setTimeout(() => {
              dwell.delete(el);
              if (stopped) return;
              // Re-checked here as well: the tab can go hidden between setting and firing.
              if (document.visibilityState !== 'visible') return;
              mark(id, 'view');
              observer.unobserve(el);
            }, DWELL_MS),
          );
        }
      },
      // Spread: IntersectionObserverInit wants a mutable `number[]`, and the constant is readonly.
      { threshold: [...OBSERVER_THRESHOLDS] },
    );

    const targets = Array.from(document.querySelectorAll<HTMLElement>('[data-insight-id]')).filter(
      el => usable(idOf(el)) && isUnseenAttr(el.getAttribute('data-unseen')) && !queue.has(idOf(el)),
    );
    for (const el of targets) observer.observe(el);

    // --- the click rule ---
    // Capture phase, so the id is queued and beaconed before Next's Link handler navigates.
    const onClick = (ev: MouseEvent) => {
      const t = ev.target;
      if (!(t instanceof Element)) return;
      const hook = t.closest('[data-seen-click]');
      if (!hook) return;
      const card = hook.closest('[data-insight-id]');
      if (card) mark(idOf(card), 'click');
    };
    document.addEventListener('click', onClick, true);

    // --- visibility ---
    const onVisibility = () => {
      if (stopped) return;
      if (document.visibilityState === 'visible') {
        // An IntersectionObserver does not re-fire on its own; unobserve + observe delivers a fresh
        // entry with the current geometry, which restarts the dwell for whatever is on screen.
        for (const el of targets) {
          observer.unobserve(el);
          if (!queue.has(idOf(el))) observer.observe(el);
        }
        return;
      }
      // Hidden: a background tab marks nothing. Cancel outright, do not pause — a tab backgrounded
      // at 2.4s and restored a minute later starts its dwell over.
      clearAllDwell();
      flush(true);
    };
    document.addEventListener('visibilitychange', onVisibility);

    const onPageHide = () => {
      clearAllDwell();
      flush(true);
    };
    window.addEventListener('pagehide', onPageHide);

    return () => {
      stopped = true;
      observer.disconnect();
      clearAllDwell();
      if (idle !== undefined) {
        clearTimeout(idle);
        idle = undefined;
      }
      document.removeEventListener('click', onClick, true);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pagehide', onPageHide);
      // Whatever is still queued when the island goes away is still the reader's; beacon it.
      flush(true);
    };
  }, [unseenKey]);

  return null;
}
```

**Impact:** still inert — nothing renders it until Step 4. Adding it alone keeps `tsc` and the test
suite green.

**Note on `unseenKey` and the exhaustive-deps lint:** the `wire` effect intentionally depends on
the *content* hash rather than the prop object; `unseenByKind` is read through `unseenRef` inside
the paint effect. There is no ESLint config in `web/` (no `.eslintrc*`, no `eslint` dependency in
`package.json`), so nothing flags it — but keep the comment above the `unseenKey` line, because it
is the reason the line exists.

---

### Step 4: `page.tsx` — four surgical edits on top of phase 3's

**File:** `web/app/sera/journal/page.tsx` — **read it as it stands after phase 3 landed.** These
are additions; the only thing any of them replaces is named explicitly.

#### Edit A — import the island

Add beside the other local imports, immediately above `import s from './journal.module.css';`
(before phase 3's edit that line is `page.tsx:14`):

```tsx
import { JournalSeen } from './JournalSeen';
```

#### Edit B — derive the two props, from phase 3's own locals

Add inside `JournalPage`, **after** phase 3's `const options = [...]` block (it reads `options`,
so it must come after it) and before the `return`. Phase 3 names the seen-set local **`seenIds`**;
use that name.

```tsx
  // The ids the server still calls unseen, per kind. This is all the client island needs to count
  // the badges down, and it is one integer per unseen insight — 26 today — so lab.json's 0.89 MB
  // of titles and markdown bodies still never reaches the browser. Derived straight from the
  // snapshot and the seen-set, so the island takes no dependency on view.ts's partition shape.
  const unseenByKind = Object.fromEntries(
    INSIGHT_KINDS.map(k => [k, lab.insights.filter(i => i.kind === k && !seenIds.has(i.id)).map(i => i.id)]),
  ) as Record<InsightKind, number[]>;

  // The other two arguments badgeTip takes beside the live count, per tab. The island calls
  // badgeTip itself, so the tooltip stays the same words as the server rendered — it just
  // recomputes the number. Seven short strings and seven integers; nothing else crosses.
  const badgeMeta = Object.fromEntries(
    options.map(o => [o.id, { heading: o.heading, total: o.total }]),
  ) as Record<KindFilter, { heading: string; total: number }>;
```

`INSIGHT_KINDS`, `InsightKind`, `KindFilter` and `lab` are all already imported by phase 3.

#### Edit C — one attribute on the bar

In the `options.map(...)` render, put `data-badge-kind` on the badge `<span>`. **That is the whole
edit** — the destructure, the `href`, `replace`, `scroll={false}`, `icon-btn md`, `data-tip`,
`aria-label`, `aria-current`, the icon and the `s.badge`/`s.zero` classes all stay exactly as
phase 3 left them. No `data-tip-template`: the island rebuilds the tooltip from `badgeMeta` and
`badgeTip`, and finds the `<Link>` with `el.closest('a[data-tip]')`.

```tsx
                  <span className={`${s.badge} ${n === 0 ? s.zero : ''}`} data-badge-kind={id} aria-hidden="true">{n}</span>
```

With JavaScript off, `data-badge-kind` is inert and the server's numbers and tooltips stand as
rendered.

#### Edit D — mount the island

Add as the **last child of `<div className={s.page}>`**, after phase 3's `{groups.map(...)}`. It
renders `null`, so its position is cosmetic; last keeps the diff off the markup above it.

```tsx
        <JournalSeen unseenByKind={unseenByKind} badgeMeta={badgeMeta} zeroClass={s.zero} />
```

#### Nothing else — in particular, nothing inside `InsightCard`

An earlier draft of this plan added a `data-unseen-marker` attribute to phase 3's marker element
so a CSS rule in this phase could fade it. **That is gone.** Phase 3 owns the marker *and* the
rule that fades it (`.card[data-seen-now] .new`), written in its own CSS module where the hashed
`.new` class is in scope, so no extra attribute is needed and this phase does not open
`journal.module.css` at all. `InsightCard` is untouched: `data-insight-id`, `data-unseen`,
`data-seen-click`, the marker, the head, the body, the footer and the arrow are all phase 3's.

**Impact of Step 4:** the island becomes live. The page is still a server component —
`JournalSeen` is the only client boundary on it, it renders nothing, and its props are integers
and seven short strings.

---

## Verification

The worktree's `web/node_modules` is already a symlink to `/home/miftah/seer/web/node_modules`
(`package.json` and `package-lock.json` are byte-identical to the base commit), and
`npx tsc --noEmit` is confirmed clean on the base tree. **Do not run `npm ci` or `npm install`.**

**Build:** `cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npx tsc --noEmit`

**Tests:** `cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npm test`
(phase-local: `npx vitest run app/sera/journal` — `view.test.ts` from phase 2 and
`seen-client.test.ts` from this phase, both with no DOM and no connection)

**Manual check** — `npm run dev`, sign in as `SERA_EMAIL`, open `/sera/journal`, DevTools open on
the Network tab filtered to `seen`:

1. **The five arrow-less entries.** Scroll to an insight whose footer has no "About M…" line (there
   are 5 of the 26 today). Hold it on screen for ~3s. Its badge number drops by one, the `all`
   badge drops by one, and its marker fades without the card moving. ~1.5s later one `POST
   /api/sera/journal/seen` → `204` goes out carrying that id and `"via":"view"`. This is the path
   that only exists because of the dwell rule — R2's hard half.
2. **Scroll past at speed.** Flick from the top of the page to the bottom without stopping. No
   badge changes and no POST fires.
3. **The arrow.** Click a card's redirect-arrow. A POST with `"via":"click"` and that single id
   leaves *before* `/sera/methods/<id>` renders (it shows in the Network tab as a `sendBeacon`
   entry). Go back: that card now sits below phase 3's boundary and the badge is one lower.
4. **A background tab.** Open a card at the top of the viewport, switch to another tab within a
   second, wait ten, come back. Nothing was marked while you were away; the dwell starts over on
   return and marks it ~2.5s later.
5. **Reload.** Everything marked during the visit is below the boundary, and each of the seven
   badges is lower by exactly the number of ids of that kind that were marked.
6. **Cards never move.** Watch a section while its cards are marked. The markers fade; nothing
   reorders. (Invariant 5.)
7. **JavaScript disabled.** DevTools → Settings → Debugger → *Disable JavaScript*, reload. The
   seven badges carry the server's unseen counts, the tooltips read correctly, the boundary is in
   place. Nothing is ever marked, which is the honest behaviour with no browser to observe with.
8. **A failing endpoint.** In DevTools, block the request URL (Network → right-click → *Block
   request URL*). Read a few cards: the badges still count down, no error surfaces anywhere on the
   page, and the console shows no uncaught rejection. Unblock, scroll one more card: the next flush
   carries the ids that failed as well.
9. **Tab switch while ids are pending.** Mark a card, and within the 1.5s debounce click another
   tab icon. The badge for the first card's kind stays down across the navigation (the queue
   survives, and `badgeCounts` filters the still-listed id out).
10. **The tooltip follows the badge, in phase 2's words.** Hover a tab before reading: "What we
    learned · 18 new of 18". Read a card of that kind; the badge falls to 17 and the tooltip now
    reads "… · 17 new of 18". Mark every entry of some kind and its tooltip switches to "… · 4
    entries, all seen" — `badgeTip`'s zero phrasing, reached live, because the island calls the
    same function the server did rather than patching a template.
11. **The marker fades, it does not collapse.** Watch a card's title as its 2.5s dwell completes:
    the coral dot fades over ~240ms and the title text does **not** shift left. If it jumps, the
    `[data-seen-now]` rule in phase 3's CSS is missing or the island removed `data-unseen`
    instead of writing `"false"`.
12. **`MAX_BATCH` against the route's cap.** `grep -n 'MAX_SEEN_BATCH' web/lib/sera/seen.ts` and
    `grep -n 'MAX_BATCH =' web/app/sera/journal/seen-client.ts`; confirm the client number is ≤
    the server number (50 ≤ 500 today) and that each comment still names the other.

**Exit criteria:**

- An entry with no redirect-arrow is marked seen by being read, and only by being read: 2.5s of
  continuous ≥60%-visible presence in a foreground tab, with a fast scroll-through marking nothing
  and a backgrounded tab marking nothing.
- Clicking a redirect-arrow marks that entry before the navigation lands.
- The seven badge numbers fall as the reader reads, and are still correct after a tab switch, after
  a reload, and with JavaScript disabled.
- No card moves while the page is open.
- A blocked or failing endpoint changes nothing the reader can see, and the ids survive to the next
  flush.
- Every observer, timer and listener is removed on unmount and on every re-wire.
- `npx tsc --noEmit && npm test` clean, `seen-client.test.ts` included.

## Handoffs

Found while planning, deliberately left alone:

- **The per-card marker is entirely phase 3's** — the element, the attribute hook and the
  `[data-seen-now]` fade rule. This phase sets `data-unseen="false"` and `data-seen-now` on the
  card and nothing more; it does not open `journal.module.css`. (Resolved by the reconciler: the
  CSS rule needs the hashed `.new` class, which is only in scope inside phase 3's own module, so
  owning the attribute without owning the rule would have split one decision across two sessions.)
- **The rail badge does not count down (Phase 5, R3).** `SeraNav`'s Journal badge is server-rendered
  per navigation and the phase-5 scope says it need not be live. This island deliberately does not
  reach outside the Journal page to patch it; it will be correct on the next navigation, which
  re-renders the Sera layout. Not a bug, and not this phase's to change.
- **`via` is recorded but never read back (Phase 1, R2).** Phase 1's table carries a `via` column
  and this island always sends it, but nothing in this plan set displays or filters on it. It is
  there so a later question ("did I click this or just scroll past it?") is answerable without a
  migration. No phase should feel obliged to surface it.
- **A "mark all as read" control.** Explicitly out of scope in the plan index. The island has
  everything it would need (the queue takes any ids), but adding the button is inventing scope.
- **`auxclick` / middle-click on a redirect-arrow** opens the method in a new tab without firing
  `click`, so that entry is not marked by the click rule. It is still marked by the dwell rule if
  the reader was looking at it, which they were. Left as is rather than growing a second listener.
- **`view.ts` could expose `unseenByKind` (Phase 2, R1).** Edit B derives it inline from
  `lab.insights` precisely so the island's props do not depend on phase 2's partition shape. Phase
  2's `journalGroups` carries the same facts per group, so folding edit B into a call on it is a
  clean follow-up — a simplification, not a fix. (`badgeTip` *is* imported from `view.ts`: that
  one is copy, and copy must have a single home.)

## Rollback

This phase alone:

```
git revert <phase-4 commit>
```

That deletes `seen-client.ts`, `seen-client.test.ts` and `JournalSeen.tsx`, and takes `page.tsx`
back to phase 3's version. (`journal.module.css` is phase 3's and this phase never touched it;
phase 3's `[data-seen-now]` rule stays behind and is simply never triggered — inert CSS, not a
break.) Nothing marks entries seen any more, so the
badges freeze at whatever `journal_seen` already holds — the page still renders, still sorts
unseen-first, still counts correctly, and phases 1, 2 and 3 are all still live. No migration to
undo and no rows to delete: rows already written stay valid and simply stop growing.

Partial rollbacks, if the revert is too blunt:

- **Keep the marking, drop the live countdown.** Remove Step 4 edit C (the `data-badge-kind`
  attribute) and the `badgeMeta` half of edit B, and delete the paint effect from
  `JournalSeen.tsx`. Entries are still marked and flushed; the badges simply stop moving until
  the next load.
- **Keep the countdown, drop the dwell rule.** Remove the `IntersectionObserver` block and the
  `targets` list from the wire effect. Only the arrow click marks anything — which is the half of
  R2 that was never in doubt, and leaves the five arrow-less entries permanently unseen.
