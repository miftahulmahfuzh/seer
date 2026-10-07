> Adopted from `JOURNAL_UNSEEN_BADGES_PLAN.md` phase 2. Source: `.workflows/plan/journal-unseen-badges/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Unseen-aware pure view layer: counts and the unseen/seen partition

**Plan set:** `JOURNAL_UNSEEN_BADGES_PLAN.md`
**Analysis:** `20261007-103957-J4N8_code_analyzer.md`
**Satisfies:** R1 (unseen items sit at the top of every tab, newest-first; seen items pushed down), R3 (the tab badge counts unseen, not inventory) — this phase supplies the pure arithmetic both requirements rest on; phase 3 renders it.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `web/app/sera/journal`

---

## Goal

`view.ts` learns what "seen" means without learning where seen-state lives. It gains
`unseenCounts(insights, seen)` — a zero-filled `Record<KindFilter, number>` whose `all` key is
the unseen total — and `journalGroups` gains an optional third parameter, a
`ReadonlySet<number>` of seen insight ids, which splits each kind's entries into an unseen half
and a seen half, each half newest-first, with the per-entry unseen flag and the boundary index
exposed on `JournalGroup`. Because the parameter is optional and defaults to an empty set, the
untouched `page.tsx` keeps compiling and keeps rendering exactly what it renders today.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing. `KindFilter`, `KindCopy`, `KIND_COPY`, `parseKind`, `journalHref`,
`newestFirst`, `kindCounts`, `dayLabel` keep their current names, signatures and behaviour
byte-for-byte.

**Renames:** none.

**Creates** (all in `web/app/sera/journal/view.ts`):

```ts
/** Copy for the unseen/seen split, kept beside KIND_COPY so every string on this page lives here. */
export const SEEN_COPY: {
  readonly boundary: 'Seen earlier';   // the divider between a group's unseen half and its seen half
  readonly marker: 'New';              // the marker shown on an unseen card
  readonly markerLabel: 'Not seen yet';// aria-label for that marker, which is otherwise a bare word
};

/** One count per tab: the six kinds plus the `all` sentinel. */
export type UnseenCounts = Record<KindFilter, number>;

/** How many entries of each kind the reader has not seen. `all` is the sum of the six kinds. */
export function unseenCounts(
  insights: readonly LabInsight[],
  seen?: ReadonlySet<number>,     // default: empty set — nothing seen
): UnseenCounts;

/** The seven-tab tooltip, naming both numbers so the badge is never ambiguous. */
export function badgeTip(heading: string, unseen: number, total: number): string;

/** One insight plus whether the reader has seen it. */
export type JournalEntry = { insight: LabInsight; unseen: boolean };
```

**Signature changes:**

```ts
// before
export function journalGroups(insights: readonly LabInsight[], filter: KindFilter): JournalGroup[];
// after — third parameter OPTIONAL, defaults to an empty set
export function journalGroups(
  insights: readonly LabInsight[],
  filter: KindFilter,
  seen?: ReadonlySet<number>,
): JournalGroup[];
```

```ts
// before
export type JournalGroup = KindCopy & { kind: InsightKind; heading: string; entries: LabInsight[] };
// after — `entries` keeps its exact type and meaning-of-order; four fields added
export type JournalGroup = KindCopy & {
  kind: InsightKind;
  heading: string;
  /** Render order, flat: the unseen half newest-first, then the seen half newest-first.
   *  Same length and same order as `items`; `entries[n] === items[n].insight`. */
  entries: LabInsight[];
  /** The same list, each entry carrying its own unseen flag. */
  items: JournalEntry[];
  /** The unseen half — identical to `items.slice(0, unseenCount)`. */
  unseen: JournalEntry[];
  /** The seen half — identical to `items.slice(unseenCount)`. */
  seen: JournalEntry[];
  /** How many of `items` are unseen; also the index at which the seen half begins. */
  unseenCount: number;
};
```

**Who consumes what — reconciled, so nothing here ships dead:**

| Export | Consumed by |
|---|---|
| `SEEN_COPY.boundary` | phase 3, the divider between a group's two halves |
| `SEEN_COPY.marker` | phase 3, as `data-tip` on the unseen card's dot |
| `SEEN_COPY.markerLabel` | phase 3, the screen-reader text inside that dot |
| `unseenCounts` | phase 3, for all seven badges (`.all` is the sentinel's number — phase 3 does **not** sum the six) |
| `badgeTip` | phase 3 for the server-rendered tooltip, **and phase 4's client island** for the live rewrite as the badge counts down |
| `journalGroups` + `JournalGroup.unseen` / `.seen` / `.items` / `.unseenCount` | phase 3, rendered **directly** — there is no adapter in `page.tsx` |
| `JournalGroup.entries` | nothing, after phase 3 lands. It stays anyway: this phase's own `view.test.ts` asserts it, and it is what keeps `tsc` green while `page.tsx` is untouched. Phase 3 is told not to remove it. |

> **`view.ts` must stay importable from a `'use client'` module.** Phase 4's `JournalSeen.tsx`
> imports `badgeTip` from here so the seven tooltips have exactly one formatter. That is safe
> today — this module imports only `lib/sera/glossary` and `lib/sera/types`; `types.ts` imports
> nothing and `glossary.ts` imports only types — and it is now a **constraint**, not just a
> property: do not add an import to `view.ts` that pulls `lib/db`, `lib/sera/lab`, `lib/sera/seen`
> or anything `next/*`-server. Invariant 3 already said this; phase 4 now depends on it.

**Contract notes phase 3 must be able to rely on, stated because phase 3 cannot read this plan:**

- `unseenCounts(...)` is keyed by `KindFilter`, so `counts[id]` works for all seven tabs
  including `'all'` — no special case at the `all` sentinel.
- `unseenCounts(insights).all` equals `insights.length` when the seen-set is empty, which is
  exactly `page.tsx`'s current `total`.
- The boundary test is `g.unseenCount > 0 && g.unseenCount < g.items.length`, equivalently
  `g.unseen.length > 0 && g.seen.length > 0`. Both halves non-empty, and only then.
- Rendering a flat list and inserting the boundary at `idx === g.unseenCount` (guarded by
  `g.unseenCount > 0`) gives the same result as rendering `g.unseen`, the boundary, then
  `g.seen` — phase 3 picks whichever suits the CSS grid.
- `entries` is part of the contract and must stay. `view.test.ts` asserts it and it is what keeps
  the tree green while `page.tsx` is untouched. Phase 3 may stop *using* it; it must not remove it.

**Requires (from earlier phases):** nothing. This phase has no dependencies and imports nothing
new.

**Leaves alone (owned by others):**
- `web/app/sera/journal/page.tsx` (phases 3 and 4) — **not edited, not even the import line.**
- `web/app/sera/journal/journal.module.css` (phases 3 and 4).
- `web/lib/sera/seen.ts`, `web/app/api/sera/journal/seen/route.ts`, `db/migrations/012_journal_seen.sql` (phase 1) — **never imported from `view.ts`** (invariant 3).
- `web/app/sera/journal/JournalSeen.tsx`, `seen-client.ts`, `seen-client.test.ts` (phase 4).
- `web/components/sera/SeraNav.tsx`, `web/app/sera/layout.tsx`, `web/package_readme.md` (phase 5).
- `web/lib/sera/types.ts` and `web/lib/sera/glossary.ts` — read-only here; `INSIGHT_KINDS` and
  `INSIGHT_KIND_LABEL` keep their current contents.

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/journal/view.ts` | modify | add `SEEN_COPY` + `NOTHING_SEEN` after `KIND_COPY` (:41); add `UnseenCounts`, `unseenCounts`, `badgeTip` after `kindCounts` (:62); replace `JournalGroup` (:64) and `journalGroups` (:67-76) with the partitioning versions |
| `web/app/sera/journal/view.test.ts` | modify | keep all eight existing cases verbatim; add `unseenCounts`, `badgeTip`, `SEEN_COPY` and partition suites |

Nothing else in the repository is touched.

## Implementation Steps

### Step 1: Rewrite `view.ts`
**File:** `web/app/sera/journal/view.ts` (whole file; the new material lands after `:41`, after
`:62`, and in place of `:64-76`)

**Change:** `KIND_COPY`, `parseKind`, `journalHref`, `newestFirst`, `kindCounts` and `dayLabel`
are reproduced unchanged. Added: `SEEN_COPY`, the shared `NOTHING_SEEN` empty set, `UnseenCounts`
/ `unseenCounts`, `badgeTip`, `JournalEntry`, and a partitioning `journalGroups` with a new
`JournalGroup` shape.

Two details that matter and are easy to get wrong:

1. **Invariant 4.** `insights.filter(i => i.kind === kind)` already copies; the two half-lists
   then `.filter(...)` that copy again before `.sort(...)`. The caller's array is never touched,
   and `view.test.ts`'s "does not reorder the input" keeps passing — now with a non-empty seen
   set too.
2. **`NOTHING_SEEN` is a module-level constant**, not `new Set()` written inline in the default,
   so the common "nothing seen" path allocates nothing per call and the default is referentially
   stable.

**Code:** complete new contents of `web/app/sera/journal/view.ts`:

```ts
// Pure helpers for /sera/journal. No data access; page.tsx feeds lab.insights.
// Seen-state arrives as a plain ReadonlySet<number> of insight ids. This module never reads it
// from Postgres, the DOM or the network — it stays unit-testable with no database and no DOM.
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

/** How many entries of each kind exist in all. The denominator behind the badge. */
export function kindCounts(insights: readonly LabInsight[]): Record<InsightKind, number> {
  const out = Object.fromEntries(INSIGHT_KINDS.map(k => [k, 0])) as Record<InsightKind, number>;
  for (const i of insights) if (i.kind in out) out[i.kind] += 1;
  return out;
}

/** One count per tab: the six kinds plus the 'all' sentinel. */
export type UnseenCounts = Record<KindFilter, number>;

/**
 * How many entries of each kind the reader has not seen, zeroes included.
 * `all` is the sum of the six kinds, so the sentinel tab agrees with the six beside it.
 * An id in `seen` that is not in `insights` is simply never looked at.
 */
export function unseenCounts(
  insights: readonly LabInsight[],
  seen: ReadonlySet<number> = NOTHING_SEEN,
): UnseenCounts {
  const out = Object.fromEntries(
    (['all', ...INSIGHT_KINDS] as readonly KindFilter[]).map(k => [k, 0]),
  ) as UnseenCounts;
  for (const i of insights) {
    if (!(i.kind in out) || seen.has(i.id)) continue;
    out[i.kind] += 1;
    out.all += 1;
  }
  return out;
}

/**
 * The seven-tab tooltip. It names both numbers, so a badge reading 2 next to a kind holding 4
 * entries is never ambiguous: "Risks we see · 2 new of 4".
 */
export function badgeTip(heading: string, unseen: number, total: number): string {
  if (total === 0) return `${heading} · none yet`;
  if (unseen === 0) return `${heading} · ${total} ${total === 1 ? 'entry' : 'entries'}, all seen`;
  return `${heading} · ${unseen} new of ${total}`;
}

/** One insight plus whether the reader has seen it. */
export type JournalEntry = { insight: LabInsight; unseen: boolean };

export type JournalGroup = KindCopy & {
  kind: InsightKind;
  heading: string;
  /**
   * Render order, flat: the unseen half newest-first, then the seen half newest-first.
   * Same length and order as `items` — `entries[n] === items[n].insight`.
   */
  entries: LabInsight[];
  /** The same list, each entry carrying its own unseen flag. */
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
  return INSIGHT_KINDS
    .filter(k => filter === 'all' || k === filter)
    .map(kind => {
      const mine = insights.filter(i => i.kind === kind);
      const fresh = mine.filter(i => !seen.has(i.id)).sort(newestFirst)
        .map((insight): JournalEntry => ({ insight, unseen: true }));
      const old = mine.filter(i => seen.has(i.id)).sort(newestFirst)
        .map((insight): JournalEntry => ({ insight, unseen: false }));
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

**Impact:** `page.tsx` is unaffected — it calls `journalGroups(lab.insights, filter)` with two
arguments and reads `g.entries`, both still valid, and `kindCounts` is untouched. The page keeps
rendering the inventory counts and a flat newest-first list until phase 3 lands. `tsc --noEmit`
stays clean with `page.tsx` never opened.

### Step 2: Rewrite `view.test.ts`
**File:** `web/app/sera/journal/view.test.ts` (whole file; the eight existing cases are at
`:20-46`, `:48-54`, `:56-76`, `:78-83` and are reproduced verbatim)

**Change:** keep every existing case exactly as it is — none of them needs updating, because the
new `journalGroups` parameter is optional and `entries` kept its type. Add five suites:
`unseenCounts`, `badgeTip`, `SEEN_COPY`, the `journalGroups` partition, and the no-reorder
property re-asserted with a non-empty seen set.

The fixture stays the five-insight `ALL` already in the file. Its arithmetic, verified against
the implementation before writing this plan:

| seen-set | `unseenCounts(...)` |
|---|---|
| `{}` | `all 5, synthesis 1, observation 3, hypothesis 0, data-wish 1, feature-wish 0, risk 0` |
| `{1,2,3,4,5}` | every key `0` |
| `{3,4}` | `all 3, synthesis 0, observation 2, hypothesis 0, data-wish 1, feature-wish 0, risk 0` |
| `{99}` | same as `{}` |

and `journalGroups(ALL, 'all', new Set([3, 4]))` gives, in one call, a group with no unseen half
(`synthesis`: entries `[4]`, `unseenCount` 0), a group with both halves (`observation`: entries
`[5, 1, 3]`, `unseenCount` 2), a group with no seen half (`data-wish`: entries `[2]`,
`unseenCount` 1) and three empty groups — all four boundary cases phase 3 has to render.

**Code:** complete new contents of `web/app/sera/journal/view.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import type { LabInsight } from '../../../lib/sera/types';
import {
  badgeTip, dayLabel, journalGroups, journalHref, kindCounts, newestFirst, parseKind,
  SEEN_COPY, unseenCounts,
} from './view';

const ins = (over: Partial<LabInsight> & Pick<LabInsight, 'id' | 'kind'>): LabInsight => ({
  title: `t${over.id}`,
  body: 'b',
  methodId: null,
  added: '2026-10-04T10:00:00+00:00',
  ...over,
});

const ALL: LabInsight[] = [
  ins({ id: 1, kind: 'observation', added: '2026-10-04T14:12:19+00:00', methodId: 'M0001' }),
  ins({ id: 2, kind: 'data-wish', added: '2026-10-04T14:12:20+00:00' }),
  ins({ id: 3, kind: 'observation', added: '2026-10-05T09:00:00+00:00' }),
  ins({ id: 4, kind: 'synthesis', added: '2026-10-05T09:00:00+00:00' }),
  ins({ id: 5, kind: 'observation', added: '2026-10-05T09:00:00+00:00' }),
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

describe('kindCounts', () => {
  it('counts every kind, zero included', () => {
    expect(kindCounts(ALL)).toEqual({
      synthesis: 1, observation: 3, hypothesis: 0, 'data-wish': 1, 'feature-wish': 0, risk: 0,
    });
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
  it('agrees with kindCounts and the snapshot length when nothing is seen', () => {
    const c = unseenCounts(ALL);
    expect(c.all).toBe(ALL.length);
    const totals = kindCounts(ALL);
    for (const k of ['synthesis', 'observation', 'hypothesis', 'data-wish', 'feature-wish', 'risk'] as const) {
      expect(c[k]).toBe(totals[k]);
    }
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
});

describe('SEEN_COPY', () => {
  it('carries non-empty copy for the boundary and the marker', () => {
    expect(SEEN_COPY.boundary.length).toBeGreaterThan(0);
    expect(SEEN_COPY.marker.length).toBeGreaterThan(0);
    expect(SEEN_COPY.markerLabel.length).toBeGreaterThan(0);
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

**Impact:** `npx vitest run app/sera/journal` goes from 8 cases to 29, all pure — no database, no
DOM, no network. `tsc --noEmit` covers this file too (`tsconfig.json` includes `**/*.ts`), so a
contract drift between `view.ts` and the test is a build error, not just a test failure.

## Verification

**Dependencies are already in place.** `web/node_modules` in this worktree is a symlink to
`/home/miftah/seer/web/node_modules`; `package.json` and `package-lock.json` are byte-identical
to the base commit, and `npx tsc --noEmit` is confirmed clean on the base tree. **Do not run
`npm ci` or `npm install`** — the link is there and an install would only cost minutes.
`node_modules` is gitignored, so it never shows up in the phase commit.

**Build:**

    cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npx tsc --noEmit

Must be clean **with `app/sera/journal/page.tsx` untouched** — that is the single most important
check in this phase. If `tsc` complains about the `journalGroups` call at `page.tsx:35` or about
`g.entries` at `page.tsx:78/86`, the optional parameter or the `entries` field has been broken;
fix `view.ts`, never `page.tsx`.

**Tests:**

    cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npx vitest run app/sera/journal
    cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npm test

**Manual check:**

    cd /home/miftah/.worktrees/seer/journal-unseen-badges && git status --porcelain

must list exactly two modified paths, `web/app/sera/journal/view.ts` and
`web/app/sera/journal/view.test.ts`, and nothing else. Also confirm `view.ts` imports only
`../../../lib/sera/glossary` and `../../../lib/sera/types` — no `@/lib/db`, no `lib/sera/seen`,
no `next/*` (invariant 3):

    grep -n "^import" web/app/sera/journal/view.ts

**Exit criteria:**
- `unseenCounts` and the three-argument `journalGroups` are exported with the signatures in the
  Interface Contract, and `JournalGroup` carries `entries`, `items`, `unseen`, `seen` and
  `unseenCount`.
- `npx tsc --noEmit` is clean and `page.tsx` is byte-identical to its state before this phase.
- All 29 cases in `app/sera/journal/view.test.ts` pass with no database and no DOM, the four
  pre-existing `journalGroups` / `kindCounts` cases unchanged among them.
- The Journal page in `npm run dev` looks exactly as it did before this phase — same badges,
  same flat newest-first lists. This phase is invisible until phase 3 passes a real seen-set.

## Handoffs

**To phase 3** (`page.tsx`, `journal.module.css`):
- Swap `kindCounts(lab.insights)` in the `options` array for
  `unseenCounts(lab.insights, await seenInsightIds())`, and read the badge number as
  `unseen[id]` for all seven tabs including `'all'` — no sentinel special case. Keep calling
  `kindCounts` as well: it is the denominator in the tooltip.
- Build the tooltip with the exported `badgeTip(INSIGHT_KIND_LABEL[k].heading, unseen[k], totals[k])`,
  and for the sentinel `badgeTip('Everything', unseen.all, lab.insights.length)`. It exists so
  the copy is tested here rather than written inline in the page — and phase 4 calls the same
  function when it rewrites a tooltip live, so the wording cannot fork between the server render
  and the countdown. **Do not write a tip string in `page.tsx`.**
- Render the boundary with `SEEN_COPY.boundary`, the per-card marker's screen-reader text with
  `SEEN_COPY.markerLabel`, and the marker's `data-tip` with `SEEN_COPY.marker`. The boundary
  condition is `g.unseenCount > 0 && g.unseenCount < g.items.length`.
- Render `g.unseen` and `g.seen` **directly** — they are already partitioned and already sorted.
  No `split()` helper, no adapter; dereference `e.insight` at the call site.
- `g.entries` is deliberately still a `LabInsight[]` in the same render order. Do not delete the
  field — `view.test.ts` (phase 2's file) asserts it.
- `g.entries.length` is still the right eyebrow count for a `Section` (unseen plus seen).

**To phase 4** (`JournalSeen.tsx`, `seen-client.ts`): the live countdown decrements the badge
numbers this phase computes, and it **imports `badgeTip` from this module** to rewrite each
tooltip as a badge falls — see the client-safety constraint in the Interface Contract. Nothing
else here is imported client-side: the island reads the `data-` hooks phase 3 puts on the cards
and recomputes its counts from a prop, so the partition shape never crosses the boundary. The
dwell/visibility constants belong in `seen-client.ts`, not in `view.ts`; this phase deliberately
leaves them out.

**Deliberately not done here (not this phase's R):**
- Reading seen-state from anywhere — that is R2, phases 1 and 4.
- Any CSS for the boundary or the marker — R1's rendering half, phase 3.
- **The rail badge's total.** Settled by the reconciler: phase 5 calls phase 1's
  `unseenCount(lab.insights.map(i => i.id))`, **not** `unseenCounts(...).all`. The two agree on
  every successful read, but only phase 1's can return `null` to say "the read failed", which is
  what invariant 9 and phase 5's "no badge on failure" criterion need — an empty `ReadonlySet`
  handed to this function is indistinguishable from a clean read of an empty table. This
  function is not redundant with it: `unseenCounts` answers *per kind, over a set the caller
  already holds, with no database*, which is the page's question. Both ship.

**Noticed but not touched:** `page.tsx:71`'s "`{total} entries in all`" bar note will read oddly
once the badges mean something different from the inventory. That line lives in phase 3's file;
flagged, not changed.

## Rollback

`git checkout -- web/app/sera/journal/view.ts web/app/sera/journal/view.test.ts`, or revert the
phase commit. Both files return to their base state, `page.tsx` has never been edited, and the
page renders exactly as it does today. Nothing outside `web/app/sera/journal/` is involved, no
migration runs, no data is written, so there is nothing else to undo.
