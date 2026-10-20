# Phase 5: Reader: heads-only, version chip, history disclosure, "Revised"

**Plan set:** `JOURNAL_VERSIONING_PLAN.md`
**Analysis:** `docs/analyzer/20261020-162050-J7K2_code_analyzer.md`
**Satisfies:** R1 (one document labelled with its version, history behind a disclosure), R5 (counts are documents, not rows; a new version reads *revised*, not *new*)
**Depends on:** Phase 4 — the snapshot must already carry `supersedes`, `docKey`, `version`, `supersededBy` on every `LabInsight`
**Difficulty:** HARD
**Package:** `web/app/sera/journal`

---

## Goal

`/sera/journal` renders **one card per document**, not one per row. A head at version N carries a
plain-language line — *"Version 3 · two earlier versions"* — and its earlier bodies sit behind a
disclosure that costs nothing on the ~495 cards that are a lone version 1. Every number on the page
— the seven tab badges, their tooltips, each Section's eyebrow, and the "N entries in all" line —
counts documents. A revised document still reappears as unseen (its head id changed, which is
correct and wanted), but it now says **"Revised"** rather than pretending to be new.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Creates (all in `web/app/sera/journal/view.ts`):**

- `isHead(i: LabInsight): boolean` — `i.supersededBy === null`
- `documentCount(insights): number`
- `historyByHead(insights): Map<number, LabInsight[]>` — per head, its earlier versions newest-first
- `countWord(n: number): string` — `0..10` as words, digits above
- `versionLabel(version: number, earlier: number): string` — `''` when `version <= 1`
- `historyTip(earlier: number): string`
- `pastVersionLabel(version: number): string`
- `JournalEntry.history: LabInsight[]` — new field on an existing exported type
- `SEEN_COPY.revised` and `SEEN_COPY.revisedLabel` — new keys on an existing exported const
- `markerCopy(insight: LabInsight): { marker: string; label: string }`

**Signature changes:**

- `InsightCard` (`page.tsx`, local, not exported): `({ insight, tone, unseen })` -> `({ entry, tone })`
  where `entry: JournalEntry`.
- `JournalEntry` gains `history`. `kindCounts`, `unseenCounts`, `journalGroups` keep their exact
  signatures; only their **meaning** narrows to heads. This is deliberate: it makes every present
  and future caller document-counting by construction rather than by remembering to filter.

**Deletes:** nothing.
**Renames:** nothing.

**Requires (from Phase 4), and this is the whole data interface:** every `LabInsight` in
`lab.insights` carries, in addition to today's `{id, kind, title, body, methodId, added}`:

| field | type | meaning |
|---|---|---|
| `supersedes` | `number \| null` | the id this row supersedes |
| `docKey` | `string \| null` | document identity — **never rendered to the owner** |
| `version` | `number` | depth in the chain, `1` when it supersedes nothing |
| `supersededBy` | `number \| null` | `null` means **this row is a head** |

> **Assumption, stated because I could not verify it.**
> `.workflows/plan/journal-versioning/phase-4.md` did not exist when this plan was written. The
> four field names and types above are taken verbatim from this phase's brief. If phase 4 lands
> different spellings, the only places to change are `isHead` / `historyByHead` / `markerCopy` /
> `versionLabel` in `view.ts` and the `ins()` factory in `view.test.ts` — nothing else in this
> phase reads those fields directly.

**Also assumed from Phase 4, and NOT fixed here:** `web/lib/sera/lab.test.ts:136` asserts
`lab.summary.insights === lab.insights.length`. Phase 4 changes `summary.insights` to count
documents, so phase 4 owns that assertion. If it is still row-shaped when this phase runs,
`npm test` is red for a reason that is not mine — see Handoffs.

**Leaves alone (owned by others):**

- `web/app/sera/journal/seen-client.ts` and `seen-client.test.ts` — the id-keyed policy is correct
  and load-bearing. Untouched, and `seen-client.test.ts` must still pass with zero edits.
- `web/app/sera/journal/JournalSeen.tsx` — **read carefully and deliberately left unchanged.** Its
  observer targets `document.querySelectorAll('[data-insight-id]')` (`JournalSeen.tsx:219`). This
  phase therefore renders **no `data-insight-id` on any history entry**, so an expanded disclosure
  can never mark an earlier version seen or move a badge. That is the single most important
  integration detail in this phase and it is why the file needs no edit.
- `/api/sera/journal/seen` and `web/lib/sera/seen.ts` (Phase 1 of the earlier seen-state set).
- `web/lib/sera/types.ts` — Phase 4.
- `/sera/methods/*` — method `analysis` and `verdict` chains stay visible by default, explicitly
  out of scope (plan §Scope).
- `lab/lab.sqlite`, `web/data/lab.json` — Phases 1, 4 and 6. See **Step 7** for the one temporary,
  reverted local edit the screenshots need.
- all of `engine/`.

**Scope note for the reconciler — one file outside the stated directory.**
Step 6 changes **one line** of `web/app/sera/layout.tsx:28`. That line feeds the Sera rail's Journal
badge from `lab.insights.map(i => i.id)` — raw rows. Left alone, the rail says *30* while the page's
own `all` badge says *27*, and its own docstring (`layout.tsx:16-18`) states the rule it would then
break: *"the rail must agree with the seven badges /sera/journal renders for itself"*. It serves
R5, which is mine, and no other phase in this set lists the file. It is the last step and revertible
on its own. If the reconciler prefers it elsewhere, move Step 6 whole — nothing else depends on it.

---

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/journal/view.ts` | modify | heads-only counting and grouping; `history` on each entry; version + marker copy. Stays pure — no data access, no DOM, no network |
| `web/app/sera/journal/page.tsx` | modify | `InsightCard` takes a `JournalEntry`; version line + `<details>` history; document totals; `unseenByKind` filtered to heads |
| `web/app/sera/journal/journal.module.css` | modify | the version line, the disclosure, the past-version blocks, the hollow "Revised" dot |
| `web/app/sera/journal/view.test.ts` | modify | the `ins()` factory gains the four fields; new suites for heads, history, document counts, version copy and the Revised rule |
| `web/app/sera/layout.tsx` | modify | one line: rail badge counts heads (see scope note) |
| `web/app/sera/journal/JournalSeen.tsx` | **read, unchanged** | listed because the brief names it as owned; the correct action is no edit — see the contract above |

---

## Implementation Steps

### Step 1: `view.ts` — heads, history, and document counting

**File:** `web/app/sera/journal/view.ts:1-175` (whole file replaced)
**Change:** add `isHead`, `documentCount`, `historyByHead`; narrow `kindCounts`, `unseenCounts` and
`journalGroups` to heads; add `history` to `JournalEntry`; add the version and marker copy.

`historyByHead` walks `supersedes` backwards from each head using an id map. That is not the
graph-walking phase 4 moved into Python — phase 4 computes `version` and `supersededBy`, which is
the expensive, order-dependent part; collecting the earlier *rows* for the disclosure is a bounded
pointer chase the reader has to do anyway because only the reader knows which heads it is about to
render. It is guarded against a cycle and against a predecessor missing from the snapshot.

**Code:** complete replacement for `web/app/sera/journal/view.ts`:

```ts
// Pure helpers for /sera/journal. No data access; page.tsx feeds lab.insights.
// Seen-state arrives as a plain ReadonlySet<number> of insight ids. This module never reads it
// from Postgres, the DOM or the network — it stays unit-testable with no database and no DOM.
//
// DOCUMENTS, NOT ROWS. A chain of `insights` rows linked by `supersedes` is ONE document with
// several versions; the row with no successor (`supersededBy === null`) is its head. Every count
// and every group in this file is over heads, so the owner's "4 documents talking about one thing"
// is 1 card reading "Version 4" and the badges above it never inflate on a re-run. The chain is
// walked in Python (lab/store.py's snapshot) precisely so `version` and `supersededBy` arrive as
// plain fields; all this file does with them is filter, and collect the earlier rows a card shows
// behind its disclosure.
import { INSIGHT_KIND_LABEL } from '../../../lib/sera/glossary';
import { INSIGHT_KINDS, type InsightKind, type LabInsight } from '../../../lib/sera/types';

export type KindFilter = InsightKind | 'all';

/** What the Journal says around each kind; the heading itself is INSIGHT_KIND_LABEL[kind].heading. */
export type KindCopy = { caption: string; empty: string; tone: string };

export const KIND_COPY: Record<InsightKind, KindCopy> = {
  synthesis: {
    caption: 'What a whole batch of tries added up to, written when the batch ended.',
    empty: 'No batch summary yet. Sera writes one each time it finishes a batch of tries.',
    tone: 'bg-lav',
  },
  observation: {
    caption: 'Facts the tests showed, whether or not the method passed.',
    empty: 'Nothing learned is written down yet.',
    tone: 'bg-sky',
  },
  hypothesis: {
    caption: 'Hunches the results suggest. Any of them can become the next method.',
    empty: 'No untested hunch is written down yet.',
    tone: 'bg-butter',
  },
  'data-wish': {
    caption: 'Data the lab does not have that would open up new kinds of methods.',
    empty: 'No data wish yet.',
    tone: 'bg-stone',
  },
  'feature-wish': {
    caption: 'Tools that would let the lab test things it cannot test today.',
    empty: 'No feature wish yet.',
    tone: 'bg-lav',
  },
  risk: {
    caption: 'Ways the lab could fool itself, or a good test could still fail with real money.',
    empty: 'No risk is written down yet.',
    tone: 'bg-butter',
  },
};

/** Copy for the unseen/seen split, kept beside KIND_COPY so every string on this page lives here. */
export const SEEN_COPY = {
  /** The divider between a group's unseen half and its seen half. Only when both halves exist. */
  boundary: 'Seen earlier',
  /** The marker on a card the reader has not seen yet. */
  marker: 'New',
  /** aria-label for that marker, which on its own is a bare word. */
  markerLabel: 'Not seen yet',
  /**
   * The marker on an unseen card that is version 2 or later.
   *
   * Seen-state keys on the insight id, and a revised document HAS a new head id, so it correctly
   * comes back unseen — the owner should be told when a conclusion was rewritten. But calling a
   * rewrite "New" is a small lie about a page whose whole job is honesty, so it says what actually
   * happened instead.
   */
  revised: 'Revised',
  /** aria-label for the revised marker. */
  revisedLabel: 'Revised and not seen yet',
} as const;

/** The "nothing has been seen" set. Shared, so the default argument allocates nothing per call. */
const NOTHING_SEEN: ReadonlySet<number> = new Set<number>();

/** `?kind=` value -> a known kind, else 'all'. */
export function parseKind(raw: string | string[] | undefined): KindFilter {
  const v = Array.isArray(raw) ? raw[0] : raw;
  return (INSIGHT_KINDS as readonly string[]).includes(v ?? '') ? (v as InsightKind) : 'all';
}

export const journalHref = (kind: KindFilter) =>
  kind === 'all' ? '/sera/journal' : `/sera/journal?kind=${encodeURIComponent(kind)}`;

/** Newest first by `added`; ties by higher id first. */
export function newestFirst(a: LabInsight, b: LabInsight): number {
  if (a.added !== b.added) return a.added < b.added ? 1 : -1;
  return b.id - a.id;
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

/**
 * Is this row the current version of its document?
 *
 * `supersededBy === null` means nothing supersedes it. A row that never joined a chain is its own
 * head at version 1 — which is ~495 of the 500 rows, so this is the overwhelmingly common case and
 * the page must cost nothing extra for it.
 */
export const isHead = (i: LabInsight): boolean => i.supersededBy === null;

/** How many documents a snapshot holds. The "N entries in all" number. */
export const documentCount = (insights: readonly LabInsight[]): number =>
  insights.reduce((n, i) => n + (isHead(i) ? 1 : 0), 0);

/**
 * Per head id, its earlier versions newest-first (the head itself excluded).
 *
 * Walks `supersedes` backwards through an id index, so a chain of k costs k lookups and a head
 * with no chain costs one. Two guards, both reachable in real data rather than theoretical:
 *
 * - a predecessor that is not in this snapshot stops the walk (the chain is simply shown short
 *   rather than the card throwing — the snapshot is a build-time bundle and a row could in
 *   principle be filtered out upstream);
 * - a cycle, or a chain longer than the snapshot, stops the walk. `supersedes` can only point at a
 *   lower id and only one successor is permitted, so the store makes a cycle impossible; this
 *   costs one Set and removes "the Journal hangs" from the list of things a bad row can do.
 */
export function historyByHead(insights: readonly LabInsight[]): Map<number, LabInsight[]> {
  const byId = new Map<number, LabInsight>();
  for (const i of insights) byId.set(i.id, i);

  const out = new Map<number, LabInsight[]>();
  for (const head of insights) {
    if (!isHead(head)) continue;
    const past: LabInsight[] = [];
    const walked = new Set<number>([head.id]);
    let at: number | null = head.supersedes;
    while (at !== null && at !== undefined && !walked.has(at) && past.length < insights.length) {
      walked.add(at);
      const row = byId.get(at);
      if (!row) break;
      past.push(row);
      at = row.supersedes;
    }
    out.set(head.id, past);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Version copy. Plain language, and never an id, a digest or a doc_key: the owner reads
// "Version 3 · two earlier versions", never "insight #499 supersedes #320".
// ---------------------------------------------------------------------------

const COUNT_WORDS = [
  'no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
] as const;

/** 0..10 as a word, anything else as digits. Small counts read better written out. */
export const countWord = (n: number): string =>
  Number.isInteger(n) && n >= 0 && n < COUNT_WORDS.length ? COUNT_WORDS[n] : String(n);

/**
 * The line on a card that has been revised. Empty string at version 1 — and that is the point:
 * almost every card is a lone version 1, so the version chip must be invisible noise there rather
 * than 495 cards all shouting "Version 1".
 *
 * `earlier` is how many previous versions this snapshot actually holds, which is normally
 * `version - 1`. When a predecessor is missing the label drops the count rather than claiming a
 * history the card cannot show.
 */
export function versionLabel(version: number, earlier: number): string {
  if (!Number.isFinite(version) || version <= 1) return '';
  if (earlier <= 0) return `Version ${version}`;
  return `Version ${version} · ${countWord(earlier)} earlier ${earlier === 1 ? 'version' : 'versions'}`;
}

/** The disclosure's tooltip and accessible name. */
export const historyTip = (earlier: number): string =>
  earlier === 1
    ? 'Read the earlier version'
    : `Read the ${countWord(earlier)} earlier versions`;

/** The heading above one earlier body inside the disclosure. */
export const pastVersionLabel = (version: number): string => `Version ${version}`;

/**
 * Which marker an unseen card wears. Version 1 is genuinely new; anything later is a rewrite of
 * something the reader may already have read, so it says so.
 */
export function markerCopy(insight: LabInsight): { marker: string; label: string } {
  return insight.version > 1
    ? { marker: SEEN_COPY.revised, label: SEEN_COPY.revisedLabel }
    : { marker: SEEN_COPY.marker, label: SEEN_COPY.markerLabel };
}

// ---------------------------------------------------------------------------
// Counts
// ---------------------------------------------------------------------------

/**
 * How many DOCUMENTS of each kind exist in all. The denominator behind the badge.
 * Superseded rows are not counted: a re-run must never move this number, which is the owner's
 * complaint restated as an invariant.
 */
export function kindCounts(insights: readonly LabInsight[]): Record<InsightKind, number> {
  const out = Object.fromEntries(INSIGHT_KINDS.map(k => [k, 0])) as Record<InsightKind, number>;
  for (const i of insights) if (isHead(i) && i.kind in out) out[i.kind] += 1;
  return out;
}

/** One count per tab: the six kinds plus the 'all' sentinel. */
export type UnseenCounts = Record<KindFilter, number>;

/**
 * How many DOCUMENTS of each kind the reader has not seen, zeroes included.
 * `all` is the sum of the six kinds, so the sentinel tab agrees with the six beside it.
 * An id in `seen` that is not in `insights` is simply never looked at — and so is a superseded
 * row's id, which is why marking version 1 seen does not quieten version 2.
 */
export function unseenCounts(
  insights: readonly LabInsight[],
  seen: ReadonlySet<number> = NOTHING_SEEN,
): UnseenCounts {
  const out = Object.fromEntries(
    (['all', ...INSIGHT_KINDS] as readonly KindFilter[]).map(k => [k, 0]),
  ) as UnseenCounts;
  for (const i of insights) {
    if (!isHead(i) || !(i.kind in out) || seen.has(i.id)) continue;
    out[i.kind] += 1;
    out.all += 1;
  }
  return out;
}

/**
 * The seven-tab tooltip. It names both numbers, so a badge reading 2 next to a kind holding 4
 * documents is never ambiguous: "Risks we see · 2 new of 4". Both arguments are document counts —
 * `kindCounts` and `unseenCounts` are the only things that ever feed it.
 */
export function badgeTip(heading: string, unseen: number, total: number): string {
  if (total === 0) return `${heading} · none yet`;
  if (unseen === 0) return `${heading} · ${total} ${total === 1 ? 'entry' : 'entries'}, all seen`;
  return `${heading} · ${unseen} new of ${total}`;
}

// ---------------------------------------------------------------------------
// Groups
// ---------------------------------------------------------------------------

/** One document plus whether the reader has seen its current version. */
export type JournalEntry = {
  /** The head: the current version, and the only row that carries a card of its own. */
  insight: LabInsight;
  unseen: boolean;
  /**
   * Earlier versions, newest-first, head excluded. Empty for a lone version-1 document, which is
   * almost all of them. page.tsx renders these behind a disclosure and gives them NO
   * `data-insight-id`, so JournalSeen's observer can never mark a superseded row seen.
   */
  history: LabInsight[];
};

export type JournalGroup = KindCopy & {
  kind: InsightKind;
  heading: string;
  /**
   * Render order, flat: the unseen half newest-first, then the seen half newest-first.
   * Heads only. Same length and order as `items` — `entries[n] === items[n].insight`.
   */
  entries: LabInsight[];
  /** The same list, each entry carrying its own unseen flag and its own history. */
  items: JournalEntry[];
  /** The unseen half — identical to `items.slice(0, unseenCount)`. */
  unseen: JournalEntry[];
  /** The seen half — identical to `items.slice(unseenCount)`. */
  seen: JournalEntry[];
  /**
   * How many of `items` are unseen; also the index at which the seen half begins.
   * A boundary belongs between the halves only when `0 < unseenCount < items.length`.
   */
  unseenCount: number;
};

/**
 * One group per kind in Journal order (every kind when filter is 'all').
 * Heads only: a superseded row never gets a card, it hangs off its head's history instead.
 * Within a group: unseen entries newest-first, then seen entries newest-first.
 * `seen` defaults to empty, which puts every entry in the unseen half and reduces the order to
 * the plain newest-first list this function returned before seen-state existed.
 * Never sorts the caller's array: every sort runs on a copy.
 */
export function journalGroups(
  insights: readonly LabInsight[],
  filter: KindFilter,
  seen: ReadonlySet<number> = NOTHING_SEEN,
): JournalGroup[] {
  const history = historyByHead(insights);
  const entry = (insight: LabInsight, unseen: boolean): JournalEntry => ({
    insight,
    unseen,
    history: history.get(insight.id) ?? [],
  });

  return INSIGHT_KINDS
    .filter(k => filter === 'all' || k === filter)
    .map(kind => {
      const mine = insights.filter(i => isHead(i) && i.kind === kind);
      const fresh = mine.filter(i => !seen.has(i.id)).sort(newestFirst)
        .map(i => entry(i, true));
      const old = mine.filter(i => seen.has(i.id)).sort(newestFirst)
        .map(i => entry(i, false));
      const items = [...fresh, ...old];
      return {
        kind,
        heading: INSIGHT_KIND_LABEL[kind].heading,
        ...KIND_COPY[kind],
        entries: items.map(e => e.insight),
        items,
        unseen: fresh,
        seen: old,
        unseenCount: fresh.length,
      };
    });
}

const DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' });

/** '2026-10-04T14:12:19+00:00' or '2026-10-04' -> 'Oct 4, 2026' (UTC). */
export const dayLabel = (iso: string) =>
  DAY.format(new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso));
```

**Impact:** `kindCounts`, `unseenCounts` and `journalGroups` now ignore superseded rows. Before
phase 6 lands there are zero chains, so on today's data every number is unchanged and the page
renders exactly as it does now — which is what makes this phase independently shippable.

---

### Step 2: `page.tsx` — heads-only cards, the version line, the history disclosure

**File:** `web/app/sera/journal/page.tsx:1-179` (whole file replaced)
**Change:**

- `total` becomes `documentCount(lab.insights)` — the bar note and the `all` tab's denominator
  (`page.tsx:46`, `:55`, `:107`).
- `unseenByKind` filters to heads (`page.tsx:73-75`). It deliberately does not go through `view.ts`
  — that independence is in its docstring — so it learns the rule itself, via the one exported
  predicate, rather than restating it.
- `InsightCard` takes a `JournalEntry`, so it has the card's history and its unseen flag in one
  object instead of three props.
- The marker's copy comes from `markerCopy`, and the card gains `data-revised` so CSS can draw a
  hollow dot for a rewrite without a second React branch.
- Below the body, a head at version 2+ renders either a `<details>` holding its earlier bodies, or
  — when the predecessors are not in this snapshot — the bare version line, so a revised card never
  silently loses its version.
- The disclosure follows the repo's existing server-side pattern (`/sera/methods/[id]`'s `Tech`,
  `page.tsx:594-612`): a `<details>` whose `<summary>` is a Lucide chevron that rotates on `[open]`,
  carrying both `aria-label` and `data-tip`. No JavaScript, so the page stays a server component.
- **No `data-insight-id` on a history entry.** `JournalSeen.tsx:219` observes every element with
  that attribute; putting it on an earlier version would let an expanded disclosure mark a
  superseded row seen and move a badge that is not counting it.

**Code:** complete replacement for `web/app/sera/journal/page.tsx`:

```tsx
import {
  ArrowUpRight, ChevronRight, Database, FlaskRound, Layers, ListFilter, Sparkles, TriangleAlert,
  Wrench, type LucideIcon,
} from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSera } from '@/lib/sera/gate';
import { INSIGHT_KIND_LABEL } from '@/lib/sera/glossary';
import { lab, methodById } from '@/lib/sera/lab';
import { renderMarkdown } from '@/lib/sera/markdown';
import { seenInsightIds } from '@/lib/sera/seen';
import { INSIGHT_KINDS, type InsightKind } from '@/lib/sera/types';
import {
  SEEN_COPY, badgeTip, dayLabel, documentCount, historyTip, isHead, journalGroups, journalHref,
  kindCounts, markerCopy, parseKind, pastVersionLabel, unseenCounts, versionLabel,
  type JournalEntry, type KindFilter,
} from './view';
import { JournalSeen } from './JournalSeen';
import s from './journal.module.css';

// The layout's title template renders this as "Journal · Sera".
export const metadata: Metadata = { title: 'Journal' };

// The page reads journal_seen from Neon, so it is never cached — the (app) convention.
export const dynamic = 'force-dynamic';

const KIND_ICON: Record<InsightKind, LucideIcon> = {
  synthesis: Layers,
  observation: Sparkles,
  hypothesis: FlaskRound,
  'data-wish': Database,
  'feature-wish': Wrench,
  risk: TriangleAlert,
};

type Search = { kind?: string | string[] };

export default async function JournalPage({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const filter = parseKind(q.kind);
  await requireSera(journalHref(filter));
  const seenIds = await seenInsightIds();
  const counts = kindCounts(lab.insights);
  const fresh = unseenCounts(lab.insights, seenIds);
  const groups = journalGroups(lab.insights, filter, seenIds);

  // DOCUMENTS, not rows. A chain of superseding rows is one entry on this page, so re-running a
  // command and writing the same note again must not move this number — which is the whole point
  // of the change. `documentCount` counts heads; `lab.insights.length` would count versions.
  const total = documentCount(lab.insights);

  // heading + total ride along on every option: they are badgeTip's other two arguments, and the
  // client island (phase 4) reads them off this array to keep the tooltip honest as `n` falls.
  const options: { id: KindFilter; heading: string; total: number; tip: string; n: number; Icon: LucideIcon }[] = [
    {
      id: 'all',
      heading: 'Everything',
      total,
      tip: badgeTip('Everything', fresh.all, total),
      n: fresh.all,
      Icon: ListFilter,
    },
    ...INSIGHT_KINDS.map(k => ({
      id: k as KindFilter,
      heading: INSIGHT_KIND_LABEL[k].heading,
      total: counts[k],
      tip: badgeTip(INSIGHT_KIND_LABEL[k].heading, fresh[k], counts[k]),
      n: fresh[k],
      Icon: KIND_ICON[k],
    })),
  ];

  // The ids the server still calls unseen, per kind. This is all the client island needs to count
  // the badges down, and it is one integer per unseen document — so lab.json's 0.89 MB of titles
  // and markdown bodies still never reaches the browser. Derived straight from the snapshot and
  // the seen-set, so the island takes no dependency on view.ts's partition shape.
  //
  // `isHead` is the one thing it DOES borrow, and it has to: the island subtracts these ids from
  // badgeMeta's totals, which are kindCounts' document counts. A superseded row's id in here would
  // be an id the denominator never counted, and the badge would under-run.
  const unseenByKind = Object.fromEntries(
    INSIGHT_KINDS.map(k => [
      k,
      lab.insights.filter(i => isHead(i) && i.kind === k && !seenIds.has(i.id)).map(i => i.id),
    ]),
  ) as Record<InsightKind, number[]>;

  // The other two arguments badgeTip takes beside the live count, per tab. The island calls
  // badgeTip itself, so the tooltip stays the same words as the server rendered — it just
  // recomputes the number. Seven short strings and seven integers; nothing else crosses.
  const badgeMeta = Object.fromEntries(
    options.map(o => [o.id, { heading: o.heading, total: o.total }]),
  ) as Record<KindFilter, { heading: string; total: number }>;

  return (
    <>
      <PageHeader
        eyebrow="Journal"
        title="What the lab is thinking"
        lede="Everything the lab noticed along the way: lessons, hunches, the data and tools it wishes it had, and the risks it sees. Food for thought, newest first."
        asOf={lab.asOf}
      />
      <div className={s.page}>
        <div className={s.bar}>
          <nav className="seg" aria-label="Show one kind of entry">
            {options.map(({ id, tip, n, Icon }) => {
              const on = id === filter;
              return (
                <Link key={id} href={journalHref(id)} replace scroll={false} className={`icon-btn md ${s.segBtn}`}
                  data-tip={tip} aria-label={tip} aria-current={on ? 'true' : undefined}>
                  <Icon size={19} strokeWidth={on ? 2 : 1.5} />
                  <span className={`${s.badge} ${n === 0 ? s.zero : ''}`} data-badge-kind={id} aria-hidden="true">{n}</span>
                </Link>
              );
            })}
          </nav>
          <p className={s.barNote}>
            {total} {total === 1 ? 'entry' : 'entries'} in all. Every lab run adds to this page.
          </p>
        </div>

        {groups.map(g => {
          const n = g.items.length;
          return (
            <Section
              key={g.kind}
              eyebrow={`${n} ${n === 1 ? 'entry' : 'entries'}`}
              title={g.heading}
              caption={g.caption}
            >
              {n === 0 ? (
                <p className={s.empty}>{g.empty}</p>
              ) : (
                <div className={s.cards}>
                  {g.unseen.map(e => (
                    <InsightCard key={e.insight.id} entry={e} tone={g.tone} />
                  ))}
                  {g.unseenCount > 0 && g.unseenCount < n && (
                    <p className={s.boundary}>{SEEN_COPY.boundary}</p>
                  )}
                  {g.seen.map(e => (
                    <InsightCard key={e.insight.id} entry={e} tone={g.tone} />
                  ))}
                </div>
              )}
            </Section>
          );
        })}

        <JournalSeen unseenByKind={unseenByKind} badgeMeta={badgeMeta} zeroClass={s.zero} />
      </div>
    </>
  );
}

/**
 * One document: its current version as the card, and every earlier version behind a disclosure.
 *
 * Version 1 — ~495 of the ~500 documents — renders exactly what it rendered before this change:
 * no line, no disclosure, nothing extra in the DOM. A version chip on every card would be noise,
 * not information.
 */
function InsightCard({ entry, tone }: { entry: JournalEntry; tone: string }) {
  const { insight, unseen, history } = entry;
  const method = insight.methodId ? methodById(insight.methodId) : undefined;
  const marker = markerCopy(insight);
  const label = versionLabel(insight.version, history.length);
  const revised = insight.version > 1;
  return (
    <article
      className={`${s.card} ${tone}`}
      data-insight-id={insight.id}
      data-unseen={unseen ? 'true' : 'false'}
      data-revised={revised ? 'true' : 'false'}
    >
      <header className={s.cardHead}>
        <h3 className={s.cardTitle}>
          <span className={s.new} data-tip={marker.marker}>
            <span className={s.sr}>{marker.label}: </span>
          </span>
          {insight.title}
        </h3>
        <time className={s.date} dateTime={insight.added}>{dayLabel(insight.added)}</time>
      </header>

      <div className={s.body} dangerouslySetInnerHTML={{ __html: renderMarkdown(insight.body) }} />

      {label && history.length > 0 && (
        <details className={s.history}>
          <summary className={s.historySummary} aria-label={historyTip(history.length)} data-tip={historyTip(history.length)}>
            <span className={s.historyChevron} aria-hidden="true"><ChevronRight size={16} /></span>
            <span className={s.historyLabel}>{label}</span>
          </summary>
          <div className={s.historyBody}>
            {/* No data-insight-id on these: JournalSeen observes that attribute, and an earlier
                version is not a card the reader can be said to have "seen". */}
            {history.map(old => (
              <section key={old.id} className={s.past}>
                <header className={s.pastHead}>
                  <span className={s.pastVersion}>{pastVersionLabel(old.version)}</span>
                  <time className={s.date} dateTime={old.added}>{dayLabel(old.added)}</time>
                </header>
                <div className={s.body} dangerouslySetInnerHTML={{ __html: renderMarkdown(old.body) }} />
              </section>
            ))}
          </div>
        </details>
      )}

      {/* A revised head whose earlier rows are not in this snapshot: the line without a
          disclosure, so the version is never silently dropped. */}
      {label && history.length === 0 && <p className={s.versionOnly}>{label}</p>}

      {insight.methodId && (
        <footer className={s.cardFoot}>
          <span className={s.about}>
            About {insight.methodId}{method ? ` · ${method.name}` : ''}
          </span>
          {method && (
            <Link href={`/sera/methods/${encodeURIComponent(method.id)}`} className="icon-btn sm"
              data-seen-click="true"
              aria-label={`Open ${method.id}, ${method.name}`} data-tip={`Open ${method.id}`}>
              <ArrowUpRight size={18} strokeWidth={1.5} />
            </Link>
          )}
        </footer>
      )}
    </article>
  );
}
```

**Impact:** the page renders one card per document. `LabInsight` is no longer imported by `page.tsx`
(the card takes a `JournalEntry` instead), which `tsc --noEmit` would flag as unused under
`noUnusedLocals` — it is dropped from the import above. Nothing outside this file imports
`InsightCard`.

---

### Step 3: `journal.module.css` — the disclosure, the version line, the Revised dot

**File:** `web/app/sera/journal/journal.module.css:49` (insert after the `.new::before` rule, before
the `.boundary` comment at `:51`) and `:43-49` (the `.new` block gains one rule)
**Change:** add the version/disclosure rules, and give a revised card's dot a hollow ring so "New"
and "Revised" are distinguishable at a glance as well as in words.

**Code:** replace the block currently at `journal.module.css:38-49` with:

```css
/* An unseen card's marker: a coral dot before the title, the same colour as the badge it counts
   toward. Shown by the data-unseen attribute rather than by React, so the client island can
   retire one card's marker by flipping attributes (plan invariant 5: it never moves a card).
   [data-seen-now] is set by phase 4's island on a card marked during this visit: the dot KEEPS
   its box and fades, so retiring it never reflows the title beside it.
   [data-revised] draws the same dot hollow. A revised document comes back unseen because its head
   id changed, which is correct and wanted — the ring is what stops it reading as brand new at a
   glance, the way SEEN_COPY.revised stops it in words. */
.new { display: none; margin-right: 9px; }
.card[data-unseen='true'] .new, .card[data-seen-now] .new { display: inline-block; }
.card[data-seen-now] .new { opacity: 0; transition: opacity 240ms ease; }
.new::before {
  content: ''; display: inline-block; width: 8px; height: 8px;
  border-radius: 999px; background: var(--coral); vertical-align: 0.12em;
}
.card[data-revised='true'] .new::before {
  background: transparent; box-shadow: inset 0 0 0 2px var(--coral);
}

/* ---- Versions ---------------------------------------------------------------------------
   A document that has been revised carries one plain line — "Version 3 · two earlier versions" —
   and its earlier bodies behind it. <details> is the repo's own server-side disclosure (the Tech
   block on /sera/methods/[id]): no JavaScript, so this page stays a server component, and the
   chevron is the only moving part.

   Almost every card is a lone version 1 and renders NONE of this, so it must stay cheap: these
   rules only ever match inside a card that actually has a history. */
.history { border-radius: 22px; background: var(--chip); }
.historySummary {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 16px; border-radius: 22px;
  list-style: none; cursor: pointer;
  font-size: 14px; color: var(--ink-2);
}
.historySummary::-webkit-details-marker { display: none; }
.historySummary::marker { content: ''; }
.historySummary:hover { background: var(--chip-solid); }
.historySummary:focus-visible { outline: 2px solid var(--coral); outline-offset: 2px; }
.historyChevron { display: inline-flex; flex: none; transition: transform 0.12s; }
.history[open] .historyChevron { transform: rotate(90deg); }
.historyLabel { overflow-wrap: anywhere; }

.historyBody { padding: 2px 16px 16px; display: grid; gap: 14px; }
.historyBody .body { font-size: 14.5px; color: var(--ink-2); }
.past { display: grid; gap: 6px; padding-top: 12px; border-top: 1px solid var(--hair); }
.past:first-child { padding-top: 2px; border-top: 0; }
.pastHead { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.pastVersion {
  font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-2);
}

/* The same line when this snapshot does not hold the earlier rows: the label alone, no control,
   so a revised card never silently loses its version. */
.versionOnly { font-size: 14px; color: var(--ink-2); }
```

**Impact:** no existing rule's specificity changes; `.card[data-revised='false']` matches nothing
new. The two-column `.cards` grid at `:15` is untouched and the disclosure sits inside a card, so
nothing about the phone breakpoint at `:65-68` needs changing.

---

### Step 4: `view.test.ts` — the `ins()` factory, and the new suites

**File:** `web/app/sera/journal/view.test.ts:1-232` (whole file replaced)
**Change:** the factory gains the four phase-4 fields with head/version-1 defaults, so every
existing assertion keeps its exact numbers. Then the new suites: `isHead`, `documentCount`,
`historyByHead` (including the two guards), document-level `kindCounts`/`unseenCounts`/`badgeTip`,
heads-only `journalGroups` with history attached, and the Revised-vs-New marker rule.

**Code:** complete replacement for `web/app/sera/journal/view.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import type { LabInsight } from '../../../lib/sera/types';
import {
  badgeTip, countWord, dayLabel, documentCount, historyByHead, historyTip, isHead, journalGroups,
  journalHref, kindCounts, markerCopy, newestFirst, parseKind, pastVersionLabel, SEEN_COPY,
  unseenCounts, versionLabel,
} from './view';

/** A head at version 1 unless the case says otherwise — which is ~495 of the 500 real rows. */
const ins = (over: Partial<LabInsight> & Pick<LabInsight, 'id' | 'kind'>): LabInsight => ({
  title: `t${over.id}`,
  body: 'b',
  methodId: null,
  added: '2026-10-04T10:00:00+00:00',
  supersedes: null,
  docKey: null,
  version: 1,
  supersededBy: null,
  ...over,
});

const ALL: LabInsight[] = [
  ins({ id: 1, kind: 'observation', added: '2026-10-04T14:12:19+00:00', methodId: 'M0001' }),
  ins({ id: 2, kind: 'data-wish', added: '2026-10-04T14:12:20+00:00' }),
  ins({ id: 3, kind: 'observation', added: '2026-10-05T09:00:00+00:00' }),
  ins({ id: 4, kind: 'synthesis', added: '2026-10-05T09:00:00+00:00' }),
  ins({ id: 5, kind: 'observation', added: '2026-10-05T09:00:00+00:00' }),
];

/**
 * M0179's real shape: one note written three times, 320 -> 499 -> 500, plus two lone documents.
 * Five rows, three documents.
 */
const CHAIN: LabInsight[] = [
  ins({
    id: 10, kind: 'observation', title: 'Residual momentum', body: 'v1',
    added: '2026-10-01T09:00:00+00:00', docKey: 'real-costs:M0179-N20',
    version: 1, supersedes: null, supersededBy: 11,
  }),
  ins({
    id: 11, kind: 'observation', title: 'Residual momentum', body: 'v2',
    added: '2026-10-02T09:00:00+00:00', docKey: 'real-costs:M0179-N20',
    version: 2, supersedes: 10, supersededBy: 12,
  }),
  ins({
    id: 12, kind: 'observation', title: 'Residual momentum', body: 'v3',
    added: '2026-10-03T09:00:00+00:00', docKey: 'real-costs:M0179-N20',
    version: 3, supersedes: 11, supersededBy: null,
  }),
  ins({ id: 13, kind: 'observation', added: '2026-10-04T09:00:00+00:00' }),
  ins({ id: 20, kind: 'risk', added: '2026-10-02T10:00:00+00:00' }),
];

/** The group for one kind, out of a filter-'all' call. */
const of = (groups: ReturnType<typeof journalGroups>, kind: string) =>
  groups.find(g => g.kind === kind)!;

describe('parseKind', () => {
  it('accepts every known kind', () => {
    for (const k of ['synthesis', 'observation', 'hypothesis', 'data-wish', 'feature-wish', 'risk']) {
      expect(parseKind(k)).toBe(k);
    }
  });
  it('falls back to all', () => {
    expect(parseKind(undefined)).toBe('all');
    expect(parseKind('nope')).toBe('all');
    expect(parseKind('')).toBe('all');
    expect(parseKind(['risk', 'observation'])).toBe('risk');
  });
});

describe('journalHref', () => {
  it('drops the param for all', () => {
    expect(journalHref('all')).toBe('/sera/journal');
    expect(journalHref('data-wish')).toBe('/sera/journal?kind=data-wish');
  });
});

describe('newestFirst', () => {
  it('orders by date, then by id', () => {
    expect([...ALL].sort(newestFirst).map(i => i.id)).toEqual([5, 4, 3, 2, 1]);
  });
});

describe('isHead', () => {
  it('is true only for a row nothing supersedes', () => {
    expect(CHAIN.filter(isHead).map(i => i.id)).toEqual([12, 13, 20]);
    expect(ALL.every(isHead)).toBe(true);
  });
});

describe('documentCount', () => {
  it('counts documents, not rows', () => {
    expect(documentCount(CHAIN)).toBe(3);
    expect(CHAIN.length).toBe(5);
  });
  it('equals the row count when nothing is chained', () => {
    expect(documentCount(ALL)).toBe(ALL.length);
  });
  it('counts nothing out of an empty snapshot', () => {
    expect(documentCount([])).toBe(0);
  });
});

describe('historyByHead', () => {
  it('gives every head its earlier versions, newest first', () => {
    const h = historyByHead(CHAIN);
    expect(h.get(12)!.map(i => i.id)).toEqual([11, 10]);
  });
  it('gives a lone document an empty history', () => {
    const h = historyByHead(CHAIN);
    expect(h.get(13)).toEqual([]);
    expect(h.get(20)).toEqual([]);
  });
  it('has no entry for a superseded row', () => {
    const h = historyByHead(CHAIN);
    expect(h.has(10)).toBe(false);
    expect(h.has(11)).toBe(false);
  });
  it('stops short when a predecessor is not in the snapshot', () => {
    const partial = CHAIN.filter(i => i.id !== 10);
    expect(historyByHead(partial).get(12)!.map(i => i.id)).toEqual([11]);
  });
  it('does not hang on a cycle', () => {
    const cyclic: LabInsight[] = [
      ins({ id: 30, kind: 'risk', version: 2, supersedes: 31, supersededBy: null }),
      ins({ id: 31, kind: 'risk', version: 1, supersedes: 30, supersededBy: 30 }),
    ];
    expect(historyByHead(cyclic).get(30)!.map(i => i.id)).toEqual([31]);
  });
  it('is empty for an empty snapshot', () => {
    expect(historyByHead([]).size).toBe(0);
  });
});

describe('kindCounts', () => {
  it('counts every kind, zero included', () => {
    expect(kindCounts(ALL)).toEqual({
      synthesis: 1, observation: 3, hypothesis: 0, 'data-wish': 1, 'feature-wish': 0, risk: 0,
    });
  });
  it('counts documents, not rows — a re-run never moves the number', () => {
    expect(kindCounts(CHAIN)).toEqual({
      synthesis: 0, observation: 2, hypothesis: 0, 'data-wish': 0, 'feature-wish': 0, risk: 1,
    });
  });
  it('agrees with documentCount across the six kinds', () => {
    const c = kindCounts(CHAIN);
    const six = c.synthesis + c.observation + c.hypothesis + c['data-wish'] + c['feature-wish'] + c.risk;
    expect(six).toBe(documentCount(CHAIN));
  });
});

describe('unseenCounts', () => {
  it('counts everything as unseen when nothing has been seen', () => {
    expect(unseenCounts(ALL, new Set())).toEqual({
      all: 5, synthesis: 1, observation: 3, hypothesis: 0, 'data-wish': 1, 'feature-wish': 0, risk: 0,
    });
  });
  it('defaults to an empty seen-set', () => {
    expect(unseenCounts(ALL)).toEqual(unseenCounts(ALL, new Set()));
  });
  it('is all zeroes when every entry has been seen', () => {
    expect(unseenCounts(ALL, new Set([1, 2, 3, 4, 5]))).toEqual({
      all: 0, synthesis: 0, observation: 0, hypothesis: 0, 'data-wish': 0, 'feature-wish': 0, risk: 0,
    });
  });
  it('subtracts only the seen ids', () => {
    expect(unseenCounts(ALL, new Set([3, 4]))).toEqual({
      all: 3, synthesis: 0, observation: 2, hypothesis: 0, 'data-wish': 1, 'feature-wish': 0, risk: 0,
    });
  });
  it('ignores a seen id that is not in the snapshot', () => {
    expect(unseenCounts(ALL, new Set([99, 100]))).toEqual(unseenCounts(ALL, new Set()));
  });
  it('makes all the sum of the six kinds, for any seen-set', () => {
    for (const seen of [new Set<number>(), new Set([3, 4]), new Set([1, 2, 3, 4, 5]), new Set([99])]) {
      const c = unseenCounts(ALL, seen);
      const six = c.synthesis + c.observation + c.hypothesis + c['data-wish'] + c['feature-wish'] + c.risk;
      expect(c.all).toBe(six);
    }
  });
  it('agrees with kindCounts and the document count when nothing is seen', () => {
    const c = unseenCounts(ALL);
    expect(c.all).toBe(documentCount(ALL));
    const totals = kindCounts(ALL);
    for (const k of ['synthesis', 'observation', 'hypothesis', 'data-wish', 'feature-wish', 'risk'] as const) {
      expect(c[k]).toBe(totals[k]);
    }
  });
  it('counts documents, not rows', () => {
    expect(unseenCounts(CHAIN, new Set()).all).toBe(3);
  });
  it('is unmoved by a superseded row being in the seen-set', () => {
    expect(unseenCounts(CHAIN, new Set([10, 11]))).toEqual(unseenCounts(CHAIN, new Set()));
  });
  it('quietens a document only when its CURRENT version is seen', () => {
    const c = unseenCounts(CHAIN, new Set([12]));
    expect(c.observation).toBe(1);
    expect(c.all).toBe(2);
  });
  it('counts nothing out of an empty snapshot', () => {
    expect(unseenCounts([], new Set([1]))).toEqual({
      all: 0, synthesis: 0, observation: 0, hypothesis: 0, 'data-wish': 0, 'feature-wish': 0, risk: 0,
    });
  });
});

describe('badgeTip', () => {
  it('names both numbers when something is new', () => {
    expect(badgeTip('Risks we see', 2, 4)).toBe('Risks we see · 2 new of 4');
  });
  it('says so when everything has been seen', () => {
    expect(badgeTip('Risks we see', 0, 4)).toBe('Risks we see · 4 entries, all seen');
    expect(badgeTip('Risks we see', 0, 1)).toBe('Risks we see · 1 entry, all seen');
  });
  it('says so when the kind is empty', () => {
    expect(badgeTip('Ideas worth testing', 0, 0)).toBe('Ideas worth testing · none yet');
  });
  it('quotes document counts when fed from kindCounts and unseenCounts', () => {
    const totals = kindCounts(CHAIN);
    const fresh = unseenCounts(CHAIN, new Set());
    expect(badgeTip('What we learned', fresh.observation, totals.observation))
      .toBe('What we learned · 2 new of 2');
  });
});

describe('SEEN_COPY', () => {
  it('carries non-empty copy for the boundary and both markers', () => {
    expect(SEEN_COPY.boundary.length).toBeGreaterThan(0);
    expect(SEEN_COPY.marker.length).toBeGreaterThan(0);
    expect(SEEN_COPY.markerLabel.length).toBeGreaterThan(0);
    expect(SEEN_COPY.revised.length).toBeGreaterThan(0);
    expect(SEEN_COPY.revisedLabel.length).toBeGreaterThan(0);
  });
  it('does not say the same thing twice', () => {
    expect(SEEN_COPY.revised).not.toBe(SEEN_COPY.marker);
    expect(SEEN_COPY.revisedLabel).not.toBe(SEEN_COPY.markerLabel);
  });
});

describe('markerCopy', () => {
  it('reads New on a document that has only ever had one version', () => {
    expect(markerCopy(ins({ id: 1, kind: 'risk' }))).toEqual({
      marker: SEEN_COPY.marker, label: SEEN_COPY.markerLabel,
    });
  });
  it('reads Revised on any later version', () => {
    for (const v of [2, 3, 4, 9]) {
      expect(markerCopy(ins({ id: 1, kind: 'risk', version: v }))).toEqual({
        marker: SEEN_COPY.revised, label: SEEN_COPY.revisedLabel,
      });
    }
  });
  it('calls the head of the real three-version chain Revised', () => {
    expect(markerCopy(CHAIN[2]).marker).toBe(SEEN_COPY.revised);
    expect(markerCopy(CHAIN[3]).marker).toBe(SEEN_COPY.marker);
  });
});

describe('countWord', () => {
  it('writes out small counts', () => {
    expect([0, 1, 2, 3, 10].map(countWord)).toEqual(['no', 'one', 'two', 'three', 'ten']);
  });
  it('falls back to digits above ten', () => {
    expect(countWord(11)).toBe('11');
    expect(countWord(42)).toBe('42');
  });
});

describe('versionLabel', () => {
  it('says nothing at all at version 1', () => {
    expect(versionLabel(1, 0)).toBe('');
    expect(versionLabel(0, 0)).toBe('');
  });
  it('names the version and the history in plain words', () => {
    expect(versionLabel(2, 1)).toBe('Version 2 · one earlier version');
    expect(versionLabel(3, 2)).toBe('Version 3 · two earlier versions');
    expect(versionLabel(4, 3)).toBe('Version 4 · three earlier versions');
  });
  it('drops the count when this snapshot has no earlier rows', () => {
    expect(versionLabel(3, 0)).toBe('Version 3');
  });
  it('never shows an id, a digest or a doc key', () => {
    for (const text of [versionLabel(3, 2), versionLabel(2, 1), historyTip(2), pastVersionLabel(1)]) {
      expect(text).not.toMatch(/#|supersed|insight|M\d{4}|:/i);
    }
  });
});

describe('historyTip', () => {
  it('is plain language, singular and plural', () => {
    expect(historyTip(1)).toBe('Read the earlier version');
    expect(historyTip(2)).toBe('Read the two earlier versions');
  });
});

describe('pastVersionLabel', () => {
  it('names a past version by its number', () => {
    expect(pastVersionLabel(1)).toBe('Version 1');
    expect(pastVersionLabel(2)).toBe('Version 2');
  });
});

describe('journalGroups', () => {
  it('lists all six kinds in the Journal order with plain headings', () => {
    const g = journalGroups(ALL, 'all');
    expect(g.map(x => x.kind)).toEqual(['synthesis', 'observation', 'hypothesis', 'data-wish', 'feature-wish', 'risk']);
    expect(g.map(x => x.heading)).toEqual([
      'Batch summaries', 'What we learned', 'Ideas worth testing', 'Data we wish we had', 'Features to build', 'Risks we see',
    ]);
    expect(g[1].entries.map(i => i.id)).toEqual([5, 3, 1]);
    expect(g[2].entries).toEqual([]);
    expect(g[2].empty.length).toBeGreaterThan(0);
  });
  it('keeps only the filtered kind', () => {
    const g = journalGroups(ALL, 'data-wish');
    expect(g).toHaveLength(1);
    expect(g[0].entries.map(i => i.id)).toEqual([2]);
  });
  it('does not reorder the input', () => {
    const copy = [...ALL];
    journalGroups(copy, 'all');
    expect(copy.map(i => i.id)).toEqual([1, 2, 3, 4, 5]);
  });
  it('does not reorder the input with a seen-set either', () => {
    const copy = [...ALL];
    journalGroups(copy, 'all', new Set([3, 4]));
    expect(copy.map(i => i.id)).toEqual([1, 2, 3, 4, 5]);
  });

  it('renders heads only — a superseded row never gets a card', () => {
    const obs = of(journalGroups(CHAIN, 'all'), 'observation');
    expect(obs.entries.map(i => i.id)).toEqual([13, 12]);
    expect(obs.items).toHaveLength(2);
    expect(obs.entries.some(i => i.id === 10 || i.id === 11)).toBe(false);
  });
  it('hangs the earlier versions off their head, newest first', () => {
    const obs = of(journalGroups(CHAIN, 'all'), 'observation');
    const head = obs.items.find(e => e.insight.id === 12)!;
    expect(head.history.map(i => i.id)).toEqual([11, 10]);
    expect(head.history.map(i => i.body)).toEqual(['v2', 'v1']);
  });
  it('gives a lone document an empty history', () => {
    for (const g of journalGroups(ALL, 'all')) {
      expect(g.items.every(e => e.history.length === 0)).toBe(true);
    }
    const obs = of(journalGroups(CHAIN, 'all'), 'observation');
    expect(obs.items.find(e => e.insight.id === 13)!.history).toEqual([]);
  });
  it('ignores a seen-set entry naming a superseded row', () => {
    const a = journalGroups(CHAIN, 'all', new Set([10, 11]));
    const b = journalGroups(CHAIN, 'all', new Set());
    expect(a.map(g => g.entries.map(i => i.id))).toEqual(b.map(g => g.entries.map(i => i.id)));
    expect(a.every(g => g.seen.length === 0)).toBe(true);
  });
  it('moves a revised document to the seen half only when its head id is seen', () => {
    const obs = of(journalGroups(CHAIN, 'all', new Set([12])), 'observation');
    expect(obs.unseen.map(e => e.insight.id)).toEqual([13]);
    expect(obs.seen.map(e => e.insight.id)).toEqual([12]);
    expect(obs.unseenCount).toBe(1);
  });

  it('treats everything as unseen when the seen-set is empty', () => {
    const obs = of(journalGroups(ALL, 'all', new Set()), 'observation');
    expect(obs.entries.map(i => i.id)).toEqual([5, 3, 1]);
    expect(obs.unseen.map(e => e.insight.id)).toEqual([5, 3, 1]);
    expect(obs.seen).toEqual([]);
    expect(obs.unseenCount).toBe(3);
    expect(obs.items.every(e => e.unseen)).toBe(true);
  });
  it('defaults the seen-set to empty, which is the pre-seen-state order', () => {
    const withDefault = journalGroups(ALL, 'all');
    const withEmpty = journalGroups(ALL, 'all', new Set());
    expect(withDefault.map(g => g.entries.map(i => i.id)))
      .toEqual(withEmpty.map(g => g.entries.map(i => i.id)));
    expect(withDefault.every(g => g.seen.length === 0)).toBe(true);
  });
  it('treats everything as seen when every id is in the set', () => {
    const obs = of(journalGroups(ALL, 'all', new Set([1, 2, 3, 4, 5])), 'observation');
    expect(obs.unseen).toEqual([]);
    expect(obs.unseenCount).toBe(0);
    expect(obs.seen.map(e => e.insight.id)).toEqual([5, 3, 1]);
    expect(obs.entries.map(i => i.id)).toEqual([5, 3, 1]);
    expect(obs.items.some(e => e.unseen)).toBe(false);
  });
  it('puts the unseen half first, each half newest-first', () => {
    const obs = of(journalGroups(ALL, 'all', new Set([3])), 'observation');
    expect(obs.unseen.map(e => e.insight.id)).toEqual([5, 1]);
    expect(obs.seen.map(e => e.insight.id)).toEqual([3]);
    expect(obs.entries.map(i => i.id)).toEqual([5, 1, 3]);
    expect(obs.unseenCount).toBe(2);
    expect(obs.items.map(e => e.unseen)).toEqual([true, true, false]);
  });
  it('ignores a seen id that is not in the snapshot', () => {
    const a = journalGroups(ALL, 'all', new Set([99]));
    const b = journalGroups(ALL, 'all', new Set());
    expect(a.map(g => g.entries.map(i => i.id))).toEqual(b.map(g => g.entries.map(i => i.id)));
    expect(a.every(g => g.seen.length === 0)).toBe(true);
  });
  it('keeps entries, items and the two halves consistent', () => {
    for (const g of journalGroups(ALL, 'all', new Set([3, 4]))) {
      expect(g.entries).toEqual(g.items.map(e => e.insight));
      expect(g.unseen).toEqual(g.items.slice(0, g.unseenCount));
      expect(g.seen).toEqual(g.items.slice(g.unseenCount));
      expect(g.unseenCount).toBe(g.unseen.length);
      expect(g.unseen.every(e => e.unseen)).toBe(true);
      expect(g.seen.some(e => e.unseen)).toBe(false);
    }
  });
  it('agrees with kindCounts on how many cards each kind renders', () => {
    const totals = kindCounts(CHAIN);
    for (const g of journalGroups(CHAIN, 'all')) expect(g.items.length).toBe(totals[g.kind]);
  });
  it('gives phase 3 all four boundary cases from one seen-set', () => {
    const g = journalGroups(ALL, 'all', new Set([3, 4]));
    const needsBoundary = (x: { unseenCount: number; items: unknown[] }) =>
      x.unseenCount > 0 && x.unseenCount < x.items.length;
    // every entry seen -> no boundary
    expect(of(g, 'synthesis').unseenCount).toBe(0);
    expect(needsBoundary(of(g, 'synthesis'))).toBe(false);
    // both halves -> boundary
    expect(needsBoundary(of(g, 'observation'))).toBe(true);
    // every entry unseen -> no boundary
    expect(of(g, 'data-wish').seen).toEqual([]);
    expect(needsBoundary(of(g, 'data-wish'))).toBe(false);
    // no entries at all -> no boundary
    expect(of(g, 'hypothesis').items).toEqual([]);
    expect(needsBoundary(of(g, 'hypothesis'))).toBe(false);
  });
  it('filters to one kind and still partitions it', () => {
    const g = journalGroups(ALL, 'observation', new Set([5]));
    expect(g).toHaveLength(1);
    expect(g[0].entries.map(i => i.id)).toEqual([3, 1, 5]);
    expect(g[0].unseenCount).toBe(2);
    expect(g[0].seen.map(e => e.insight.id)).toEqual([5]);
  });
});

describe('dayLabel', () => {
  it('formats timestamps and dates in UTC', () => {
    expect(dayLabel('2026-10-04T14:12:19+00:00')).toBe('Oct 4, 2026');
    expect(dayLabel('2015-10-16')).toBe('Oct 16, 2015');
  });
});
```

**Impact:** every pre-existing assertion keeps its exact expected value, because `ALL` is five
unchained heads. The new suites are the ones that would go red if a later change reverted
document-counting.

---

### Step 5: check `seen-client.test.ts` is still green with zero edits

**File:** `web/app/sera/journal/seen-client.test.ts` (no change)
**Change:** none. This is a verification step, written down because the brief makes it a
requirement: `seen-client.ts` keeps its id-keyed behaviour and its tests must pass untouched.
If `npm test` reports a failure in that file, something in Step 1–4 reached into the seen policy
and must be backed out.

**Impact:** none.

---

### Step 6: the Sera rail's Journal badge counts documents

> **Scope note.** One line outside `web/app/sera/journal/`. See the Interface Contract: it serves
> R5, no other phase owns the file, and leaving it breaks the agreement the file's own docstring
> promises. Revertible on its own.

**File:** `web/app/sera/layout.tsx:26-32`
**Change:** hand `unseenCount` the head ids, not every row id.

**Code:** replace `journalUnseen` and the comment above it:

```tsx
/**
 * Entries in the bundled snapshot the reader has not seen — the number on the rail's Journal
 * tab. 0 renders no badge at all, and so does a failed read.
 *
 * The ids come from `lab.insights`, never from journal_seen's row count and never as
 * `insights.length - seen.size`: a row may name an id that is not in this build's snapshot (the
 * table lives in Neon, the snapshot is bundled at build time), and the rail must agree with the
 * seven badges /sera/journal renders for itself. unseenCount only looks at the ids it is given,
 * so handing it lab.insights' ids is the derivation rule, enforced.
 *
 * HEADS ONLY, for exactly that agreement. A chain of superseding rows is one entry on the Journal
 * and its badges count documents; sending every row id here would make the rail say 30 while the
 * page says 27, over the same snapshot. `isHead` is the one predicate both sides share.
 *
 * unseenCount returns null when the read failed, which is why it is the function this layout
 * calls rather than seenInsightIds: an empty Set cannot say whether nothing is unseen or Neon is
 * down, and invariant 9 asks for no badge in the second case rather than a confident 26. The
 * try/catch is belt-and-braces -- unseenCount already swallows its own query failure -- because
 * this layout wraps every /sera page and a throw here takes the whole section down over a badge.
 */
async function journalUnseen(): Promise<number> {
  try {
    return (await unseenCount(lab.insights.filter(isHead).map(i => i.id))) ?? 0;
  } catch {
    return 0;
  }
}
```

and add the import beside the existing ones at `layout.tsx:1-6`:

```tsx
import { isHead } from './journal/view';
```

**Impact:** the rail agrees with the page. `view.ts` is pure (it imports only
`lib/sera/glossary` and `lib/sera/types`), so a server layout importing it drags nothing extra in —
the same property that already lets the client island import it.

---

### Step 7: see it — screenshots at both widths in both themes

**File:** none (verification)
**Change:** none in the tree. This is required, not optional, for a user-visible web change.

**The problem to solve first:** phase 5 depends on phase 4, not phase 6, so `web/data/lab.json`
holds **no chains** when this phase runs. Every card is a lone version 1 and a screenshot proves
only that nothing regressed. To photograph a version line and an expanded history, make a
**temporary, local, reverted** edit to `web/data/lab.json`: thread M0179's real trio by hand, the
same three rows phase 6 will thread for real —

| row | set |
|---|---|
| 320 | `"supersededBy": 499` |
| 499 | `"supersedes": 320, "version": 2, "supersededBy": 500` |
| 500 | `"supersedes": 499, "version": 3` |

leaving every `title` and `body` byte-identical. Then:

```bash
cd /home/miftah/.worktrees/seer/journal-versioning/web
# A dev server locks per DIRECTORY, not per port: if a peer phase already has one up in this
# worktree, reuse its port instead of starting a second.
npm run dev:env                                  # localhost:3111

npm run shoot -- --out .shots/p5 --width 390  --theme both /sera/journal
npm run shoot -- --out .shots/p5 --width 1280 --theme both /sera/journal
npm run shoot -- --out .shots/p5 --width 1280 --theme both --full '/sera/journal?kind=observation'
```

`shoot` signs itself in headlessly and renews its own session — never ask the owner to sign in.
`/sera/journal` reads `journal_seen` from Neon, so if production renders an empty or all-seen page,
seed a throwaway demo database (`npm run db:seed-demo`) and point `.env.local` at it, then drop it.
In this worktree pass `SEER_ENV_FILE`.

A `<details>` is closed on load, so the expanded-history shot needs the disclosure opened. Either
add `open` to the `<details>` in `page.tsx` for one shot and remove it, or click it in a
`npm run film` run — whichever is quicker; the deliverable is a PNG showing an opened history.

**Then revert the data edit before anything else:**

```bash
git checkout -- web/data/lab.json
git status --short web/data/lab.json       # must print nothing
```

`engine/tests/test_lab_snapshot.py` asserts the committed JSON is the export of the committed
database, so it is red for as long as that hand edit exists. Revert first, then run the suites.

**Impact:** none on the tree. The PNGs are in `.shots/`, which is git-ignored.

**What the screenshots must show:**

1. phone 390, light and dark: the filter bar, the per-Section eyebrow, and cards that are version 1
   carrying **no** version line — the chip is invisible noise at version 1 and that must be visible
   in the picture;
2. desktop 1280, light and dark: the M0179 card reading **"Version 3 · two earlier versions"**;
3. one shot with that disclosure **open**, showing Version 2 and Version 1 bodies stacked under it,
   each with its own date;
4. the two-column grid intact at 1280 and one column at 390, with no horizontal scroll.

---

## Verification

**Types:** `cd /home/miftah/.worktrees/seer/journal-versioning/web && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/journal-versioning/web && npm test`
**Lint/build sanity:** `cd /home/miftah/.worktrees/seer/journal-versioning/web && npm run build`
(this worktree's `web/node_modules` is a real directory, which `next build` requires — a symlink
passes vitest and tsc and then fails the build with a misleading "filesystem root" error)
**Engine, unchanged but asserted:**
`cd /home/miftah/.worktrees/seer/journal-versioning && PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests`
— this phase touches no engine file; run it to prove the branch is still green, and only after
`web/data/lab.json` is back to its committed bytes.
**Manual check:** the four screenshots listed in Step 7.

**Exit criteria:**

1. `npx tsc --noEmit` clean and `npm test` green, including `seen-client.test.ts` with zero edits.
2. On a snapshot containing the M0179 trio, `/sera/journal` renders **one** card for it, headed
   "Version 3 · two earlier versions", with Version 2 and Version 1 behind the disclosure.
3. On that same snapshot the `all` badge's denominator, the observation Section's eyebrow, the
   "N entries in all" line and the Sera rail's Journal badge all fall by **2** relative to the row
   count — the same 2, consistently, in all four places.
4. An unseen head at version 2+ renders the marker "Revised" with the aria-label
   "Revised and not seen yet"; an unseen version-1 head still renders "New" / "Not seen yet".
5. No `data-insight-id`, no insight id, no digest and no `doc_key` appears anywhere inside a
   history disclosure's markup or copy.
6. `git status --short web/data/lab.json lab/lab.sqlite` prints nothing.

---

## Handoffs

- **Phase 4 owns `web/lib/sera/lab.test.ts:136`** — `expect(lab.summary.insights).toBe(lab.insights.length)`.
  Phase 4 changes `summary.insights` to count documents, which makes that assertion false the
  moment a chain exists. It is phase 4's file and phase 4's requirement (R1, the export); this
  phase does not touch it. If it is still row-shaped when phase 6's chains land, `npm test` goes
  red there and the fix is `documentCount`-shaped, not mine.
- **`/sera/methods/[id]` deliberately left alone.** `insightsOf(methodId)` (`web/lib/sera/lab.ts:49`)
  still lists every row, superseded ones included, on a method's page. That is correct and is plan
  §Scope: *"said X before the run, Y after"* is load-bearing there, and M0261's withdrawn 3.21 is
  only legible beside its correction. If a later change ever wants heads-only there too, it needs
  the owner's say-so, not a drive-by.
- **`web/app/sera/how/page.tsx:39`** counts `data-wish` rows (`lab.insights.filter(...).length`).
  It is one number on a different page, serves no requirement in this set, and no phase owns it.
  Left alone on purpose; worth a one-line follow-up card if the owner ever threads a data-wish.
- **`web/app/sera/overview.ts:130`** picks the newest synthesis for the Sera overview. Newest by
  date already resolves to the head of a chain, so it needs nothing — recorded here so the next
  reader does not have to re-derive it.
- **An "earlier version" is never marked seen.** By design: the disclosure's entries carry no
  `data-insight-id`, so they are invisible to `JournalSeen`. If the owner later wants reading a
  history to count, that is a change to `seen-client.ts`'s policy and belongs in its own phase.

---

## Rollback

Four files, one commit, no data and no schema:

```bash
cd /home/miftah/.worktrees/seer/journal-versioning
git revert <phase-5-commit>
```

Nothing in this phase writes to `lab/lab.sqlite`, `web/data/lab.json` or Neon, so a revert is total:
the page returns to one card per row with no version line. Phases 1–4 and 6 are unaffected — the
chains stay in the database, simply unrendered, which is exactly the state the journal is in today.

Step 6 (`web/app/sera/layout.tsx`) can be reverted on its own with
`git checkout <phase-5-commit>~1 -- web/app/sera/layout.tsx` if the reconciler moves it to another
phase; nothing else in this phase depends on it.
