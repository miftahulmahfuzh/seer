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
