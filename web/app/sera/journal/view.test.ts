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
