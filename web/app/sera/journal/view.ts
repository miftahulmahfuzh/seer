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
