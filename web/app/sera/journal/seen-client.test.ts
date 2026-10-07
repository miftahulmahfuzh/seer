import { describe, expect, it } from 'vitest';
import { INSIGHT_KINDS, type InsightKind } from '../../../lib/sera/types';
import {
  DWELL_MS, FLUSH_IDLE_MS, MAX_BATCH, OBSERVER_THRESHOLDS, SEEN_ENDPOINT,
  TALL_VIEWPORT_FRACTION, VISIBLE_FRACTION,
  badgeCounts, createSeenQueue, isOnScreen, isUnseenAttr, seenRequestBody,
  type UnseenByKind,
} from './seen-client';

const rect = (height: number) => ({ height });

// Built with a loop rather than Object.fromEntries: fromEntries widens to a string index
// signature, which TS will not assert onto a Record with six required keys.
const unseen = (over: Partial<Record<InsightKind, number[]>> = {}): UnseenByKind => {
  const out = {} as Record<InsightKind, number[]>;
  for (const k of INSIGHT_KINDS) out[k] = over[k] ?? [];
  return out;
};

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
