import { describe, expect, it } from 'vitest';
import { GATE, method, trial } from '../../../lib/sera/fixture';
import type { LabSnapshot } from '../../../lib/sera/types';
import {
  BEARS, dataFacts, honestyRules, hurdles, pctLabel, pipelineLabel, pipelineStages, stageCounts, windowsModel,
  type HowInput,
} from './view';

const DATA: LabSnapshot['data'] = {
  storeStart: '1993-01-29',
  membershipStart: '1996-01-02',
  fxStart: '1999-01-04',
  fingerprints: ['p7a-abc'],
  barRows: 1234567,
  symbolsRequested: 700,
  symbolsServed: 650,
  dividendRows: 45000,
};

const snap = (over: Partial<HowInput> = {}): HowInput => ({
  asOf: '2026-10-04T14:12:24+00:00',
  gate: GATE,
  data: DATA,
  summary: { devTrials: 58, testLooks: 0 },
  methods: [
    method({ id: 'H-P7A-F1', status: 'rejected', historical: true }),
    method({ id: 'M0001', status: 'rejected' }),
    method({ id: 'M0002', status: 'idea' }),
    method({ id: 'M0003', status: 'idea' }),
    method({ id: 'M0004', status: 'blocked-data' }),
    method({ id: 'M0005', status: 'paper', updated: '2026-09-01T08:00:00+00:00' }),
  ],
  trials: [trial({ eligible: true }), trial({ eligible: false }), trial({ window: 'test', eligible: true })],
  ...over,
});

describe('pctLabel', () => {
  it('drops trailing zeros', () => {
    expect(pctLabel(0.15)).toBe('15%');
    expect(pctLabel(0.125)).toBe('12.5%');
  });
});

describe('stageCounts', () => {
  it('counts each stage from statuses and dev trials', () => {
    expect(stageCounts(snap())).toEqual({ ideas: 2, registered: 2, devTrials: 58, eligible: 1, testLooks: 0, paper: 1 });
  });
});

describe('pipelineStages', () => {
  const st = pipelineStages(snap());
  it('has the seven stages in order, with fail branches on the four tests', () => {
    expect(st.map(x => x.key)).toEqual(['idea', 'registered', 'dev', 'hurdles', 'test', 'paper', 'real']);
    expect(st.map(x => x.fails)).toEqual([false, false, true, true, true, true, false]);
    expect(st[6].final).toBe(true);
  });
  it('reads the windows and thresholds from the gate', () => {
    expect(st[2].title).toEqual(['Tested on', '1993–2015']);
    expect(st[4].title).toEqual(['One look at', '2015–today']);
    expect(st[3].detail.join(' | ')).toBe(
      'Beat SPY + dividends | Worst fall ≤ 15% | PF ≥ 1.3 · 100+ trades | No owner inputs | Luck check ≥ 0.95',
    );
    const loose = pipelineStages(snap({ gate: { ...GATE, maxDrawdown: 0.2, dsrMin: 0.9 } }));
    expect(loose[3].detail).toContain('Worst fall ≤ 20%');
    expect(loose[3].detail).toContain('Luck check ≥ 0.9');
  });
  it('shows current counts', () => {
    expect(st.map(x => x.count)).toEqual(['2 waiting', '2 methods', '58 tries', '1 pass', '0 looks used', '1 on paper', 'None yet']);
  });
  it('keeps every line short enough for its box', () => {
    for (const x of st) {
      const max = x.weight && x.weight > 1 ? 26 : 18;
      for (const l of x.title) expect(l.length).toBeLessThanOrEqual(14);
      for (const l of x.detail) expect(l.length).toBeLessThanOrEqual(max);
    }
  });
  it('summarises the path for screen readers', () => {
    expect(pipelineLabel(st)).toContain('Idea (2 waiting), then Written down before testing (2 methods)');
  });
});

describe('windowsModel', () => {
  it('uses the as-of date as today and notes an untouched test window', () => {
    const w = windowsModel(snap());
    expect(w.today).toBe('2026-10-04');
    expect(w.start).toBe('1993-01-29');
    expect(w.testNote).toBe('untouched, no look used yet');
    expect(w.paperSince).toBe('2026-09-01');
    expect(w.bears).toBe(BEARS);
  });
  it('counts looks used and handles nothing on paper', () => {
    const w = windowsModel(snap({ summary: { devTrials: 58, testLooks: 2 }, methods: [] }));
    expect(w.testNote).toBe('2 looks used');
    expect(w.paperSince).toBeNull();
    expect(w.label).toContain('no lab method on paper yet');
  });
  it('survives an empty lab, whose asOf is empty', () => {
    expect(windowsModel(snap({ asOf: '' })).today).toBe('2015-10-19');
  });
});

describe('hurdles', () => {
  it('lists the six conditions in gate order with thresholds from the gate', () => {
    const h = hurdles(GATE, 58);
    expect(h.map(x => x.key)).toEqual(['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr']);
    expect(h.map(x => x.target)).toEqual([
      'More than SPY total return', 'Max drawdown ≤ 15%', 'Profit factor ≥ 1.3', 'At least 100 trades',
      'Nothing left for the owner to decide', 'Luck check ≥ 0.95',
    ]);
    expect(h.map(x => x.term)).toEqual(['spyTr', 'maxDrawdown', 'profitFactor', 'trades', 'ownerInputs', 'dsr']);
    expect(h[5].plain).toContain('N = 58');
  });
});

describe('honestyRules', () => {
  it('quotes the live tries and looks', () => {
    const r = honestyRules(snap({ summary: { devTrials: 1, testLooks: 3 } }));
    expect(r.map(x => x.key)).toEqual(['counted', 'first', 'reroll', 'append', 'look', 'bar']);
    expect(r[0].body.startsWith('1 try so far')).toBe(true);
    expect(r[4].body).toContain('Looks used so far: 3');
  });
});

describe('dataFacts', () => {
  it('formats what the lab has and lists what it lacks', () => {
    const f = dataFacts(DATA, GATE);
    expect(f.has.map(x => x.key)).toEqual(['prices', 'dividends', 'membership', 'fx', 'versions']);
    expect(f.has[0].title).toBe('Daily prices since Jan 1993');
    expect(f.has[0].body).toContain('1,234,567 daily price rows for 650 of the 700');
    expect(f.has[4].title).toBe('One frozen copy of the data');
    expect(f.lacks.map(x => x.key)).toEqual(['fundamentals', 'delisted', 'intraday', 'options', 'sentiment']);
  });
});
