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
