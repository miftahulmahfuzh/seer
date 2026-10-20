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
