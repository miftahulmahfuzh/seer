import { describe, expect, it } from 'vitest';
import { lab } from '../../../lib/sera/lab';
import type { LabSnapshot } from '../../../lib/sera/types';
import {
  EMPTY_TEXT, FINDING_TEXT, PAGE_SIZE, controlled, displayNames, pageHref, parsePage, rankSignals, readings,
  signalMap, type PanelSignal, type SignalMap,
} from './view';

type Panel = LabSnapshot['panel'];
type Era = NonNullable<NonNullable<PanelSignal['dev']>['all']>;

/** Text that must never reach the owner: a method or signal id, a digest, or code punctuation. */
const NOT_PLAIN = /\b[MS]\d{4}\b|\b[0-9a-f]{12,}\b|[_`{}<>]|=>/;

const era = (over: Partial<Era> = {}): Era => ({
  months: 120, ic: 0.01, icT: 1.2, spread: 0.02, spreadT: 1.5, slope: 0.001, slopeT: 1.1, turnover: 0.3, ...over,
});

function sig(over: Partial<PanelSignal> = {}): PanelSignal {
  return {
    id: 'S0001',
    kind: 'signal',
    name: 'Twelve-month winners, skipping the last month',
    family: 'stock-momentum',
    methodId: null,
    clears: false,
    q: 0.4,
    reasons: ['Its lead could be luck, given how many ideas were tried'],
    twinOf: null,
    dev: { all: era({ spread: 0.021 }), pre2009: era(), recent: era({ spread: 0.004 }) },
    survivorship: { all: era({ spread: 0.018 }), pre2009: era(), recent: era() },
    ...over,
  };
}

const panel = (signals: PanelSignal[]): Panel => ({ rule: 'panel-v1', fdr: 0.1, signals });

/** Every string signalMap hands the page. */
function ownerText(map: SignalMap): string[] {
  return [
    map.lede,
    ...(map.finding ? [map.finding] : []),
    ...map.rows.flatMap(r => [r.name, r.verdict, ...r.why, r.readings, r.controlled ?? '', r.origin, r.twin ?? '']),
  ];
}

describe('signalMap on an empty panel (R6.3)', () => {
  const map = signalMap(panel([]), undefined);
  it('says nothing has been measured, with no rows and no finding', () => {
    expect(map.total).toBe(0);
    expect(map.rows).toEqual([]);
    expect(map.finding).toBeNull();
    expect(map.pages).toBe(1);
    expect(map.page).toBe(1);
    expect(map.lede.endsWith('No idea has been measured yet.')).toBe(true);
  });
  it('has an empty-state sentence that names no id', () => {
    expect(EMPTY_TEXT).not.toMatch(NOT_PLAIN);
  });
});

describe('signalMap headline', () => {
  it('counts ideas and passes, and reads "none" when nothing passed', () => {
    const map = signalMap(panel([sig(), sig({ id: 'S0002', name: 'Cheap on earnings' })]), undefined);
    expect(map.lede.endsWith('2 ideas measured; none passed.')).toBe(true);
    expect(map.finding).toBe(FINDING_TEXT);
  });
  it('drops the finding once one idea passes', () => {
    const map = signalMap(panel([sig({ clears: true, reasons: [] }), sig({ id: 'S0002', name: 'Cheap' })]), undefined);
    expect(map.lede.endsWith('2 ideas measured; 1 passed.')).toBe(true);
    expect(map.finding).toBeNull();
    expect(map.cleared).toBe(1);
  });
  it('formats large counts with separators', () => {
    const many = Array.from({ length: 1500 }, (_, i) => sig({ id: `S${String(i + 1).padStart(4, '0')}`, name: `Idea ${i}` }));
    expect(signalMap(panel(many), undefined).lede.endsWith('1,500 ideas measured; none passed.')).toBe(true);
  });
});

describe('rankSignals', () => {
  it('orders by the controlled slope, best first, with no slope last and ties by name', () => {
    const ranked = rankSignals([
      sig({ id: 'S0001', name: 'B', dev: { all: era({ slope: 0.001 }), pre2009: era(), recent: era() } }),
      sig({ id: 'S0002', name: 'A', dev: { all: era({ slope: 0.003 }), pre2009: era(), recent: era() } }),
      sig({ id: 'S0003', name: 'C', dev: { all: era({ slope: Number.NaN }), pre2009: era(), recent: era() } }),
      sig({ id: 'S0004', name: 'A2', dev: { all: era({ slope: 0.001 }), pre2009: era(), recent: era() } }),
    ]);
    expect(ranked.map(s => s.id)).toEqual(['S0002', 'S0004', 'S0001', 'S0003']);
  });
});

describe('row wording (R6.2)', () => {
  it('says the three readings in words, with their meaning', () => {
    expect(readings(sig())).toBe(
      'Its top picks beat the average stock it could have picked by 2.1% a year; since 2009 they beat it by 0.4%; ' +
        'with the companies that later failed put back, they beat it by 1.8%.',
    );
  });
  it('says trailed for a negative spread and matched for a zero one', () => {
    const s = sig({
      dev: { all: era({ spread: -0.012 }), pre2009: era(), recent: era({ spread: 0.0001 }) },
      survivorship: null,
    });
    expect(readings(s)).toBe(
      'Its top picks trailed the average stock it could have picked by 1.2% a year; since 2009 they matched it; ' +
        'with the companies that later failed put back, it has not been measured yet.',
    );
  });
  it('says "not enough months to say" for an era left out of a measured store', () => {
    const s = sig({
      dev: { all: era({ spread: 0.021 }), pre2009: era(), recent: null },
      survivorship: { all: null, pre2009: null, recent: null },
    });
    expect(readings(s)).toBe(
      'Its top picks beat the average stock it could have picked by 2.1% a year; since 2009 there are not enough months to say; ' +
        'with the companies that later failed put back, there are not enough months to say.',
    );
  });
  it('says the controlled slope by its sign only', () => {
    expect(controlled(sig({ dev: { all: era({ slope: 0.002 }), pre2009: era(), recent: era() } }))).toMatch(/still did better\.$/);
    expect(controlled(sig({ dev: { all: era({ slope: -0.002 }), pre2009: era(), recent: era() } }))).toMatch(/did no better\.$/);
  });
  it('gives the verdict in words, with the engine reasons only when it did not pass', () => {
    const [pass, miss] = signalMap(
      panel([
        sig({ id: 'S0001', clears: true, reasons: [], dev: { all: era({ slope: 0.01 }), pre2009: era(), recent: era() } }),
        sig({ id: 'S0002', name: 'Cheap on earnings', reasons: ['It stopped working after 2009'] }),
      ]),
      undefined,
    ).rows;
    expect([pass.verdict, pass.why]).toEqual(['Passed the screen', []]);
    expect([miss.verdict, miss.why]).toEqual(['Did not pass', ['It stopped working after 2009']]);
  });
  it('tells replays from new signals in words', () => {
    const rows = signalMap(
      panel([sig(), sig({ id: 'M0614-V1', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high' })]),
      undefined,
    ).rows;
    expect(rows.map(r => r.origin).sort()).toEqual(['From a strategy already tested', 'Tested as a signal first']);
  });
  it('names a twin by the name of the row it repeats, never its id', () => {
    const rows = signalMap(
      panel([
        sig({ id: 'M0614-V1', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high' }),
        sig({ id: 'M0614-V2', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high', twinOf: 'M0614-V1' }),
        sig({ id: 'S0009', name: 'Orphan', twinOf: 'S9999' }),
      ]),
      undefined,
    ).rows;
    const byName = new Map(rows.map(r => [r.name, r]));
    expect(byName.get('Quiet stocks near their high (variant 2 of 2)')?.twin).toBe(
      'The same picks as Quiet stocks near their high (variant 1 of 2)',
    );
    expect(byName.get('Quiet stocks near their high (variant 1 of 2)')?.twin).toBeNull();
    expect(byName.get('Orphan')?.twin).toBe('The same picks as an earlier idea');
  });
  it('suffixes only names that collide', () => {
    const names = displayNames([sig({ id: 'S0001', name: 'A' }), sig({ id: 'S0002', name: 'B' })]);
    expect([...names.values()]).toEqual(['A', 'B']);
  });
  it('never puts an id, a digest or code in front of the owner', () => {
    const map = signalMap(
      panel([
        sig({ id: 'S0001', clears: true, reasons: [] }),
        sig({ id: 'M0614-V1', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high', survivorship: null }),
        sig({ id: 'M0614-V2', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high', twinOf: 'M0614-V1' }),
        sig({ id: 'S0003', name: 'Orphan', twinOf: 'S9999' }),
      ]),
      undefined,
    );
    for (const text of ownerText(map)) expect(text).not.toMatch(NOT_PLAIN);
  });
});

describe('pagination', () => {
  const many = Array.from({ length: 120 }, (_, i) =>
    sig({
      id: `S${String(i + 1).padStart(4, '0')}`,
      name: `Idea ${String(i + 1).padStart(3, '0')}`,
      dev: { all: era({ slope: 1 - i / 1000 }), pre2009: era(), recent: era() },
    }),
  );
  it('serves PAGE_SIZE rows a page, ranked across the whole list', () => {
    const p1 = signalMap(panel(many), undefined);
    const p3 = signalMap(panel(many), '3');
    expect(PAGE_SIZE).toBe(50);
    expect([p1.pages, p1.rows.length, p1.rows[0].rank, p1.rows[0].name]).toEqual([3, 50, 1, 'Idea 001']);
    expect([p3.page, p3.rows.length, p3.rows[0].rank, p3.rows[19].rank]).toEqual([3, 20, 101, 120]);
  });
  it('reads garbage as page 1 and a page past the end as the last page', () => {
    expect(parsePage(undefined, 3)).toBe(1);
    expect(parsePage('abc', 3)).toBe(1);
    expect(parsePage('0', 3)).toBe(1);
    expect(parsePage('2.5', 3)).toBe(1);
    expect(parsePage(['2', '3'], 3)).toBe(2);
    expect(parsePage('99', 3)).toBe(3);
    expect(parsePage('5', 1)).toBe(1);
  });
  it('links page 1 without a query', () => {
    expect([pageHref(1), pageHref(2)]).toEqual(['/sera/signals', '/sera/signals?page=2']);
  });
});

describe('the committed snapshot', () => {
  // Reasons only (Decisions): a replay's name is its method's own name, owner-facing already on
  // /sera/methods, and a method name may legitimately mention another method. The fixture tests
  // above still hold every name, verdict and line the page prints to the no-ids rule.
  it('publishes owner-readable reasons for every panel row', () => {
    for (const s of lab.panel.signals) {
      for (const text of s.reasons) {
        expect([s.id, text, NOT_PLAIN.test(text)]).toEqual([s.id, text, false]);
      }
    }
  });
  it('renders without throwing on whatever it holds', () => {
    const map = signalMap(lab.panel, undefined);
    expect(map.total).toBe(lab.panel.signals.length);
    expect(map.rows.length).toBe(Math.min(PAGE_SIZE, map.total));
  });
});
