import { describe, expect, it } from 'vitest';
import { withVerdict } from '../../lib/sera/fixture';
import type { LabInsight, LabMethod, LabSnapshot, LabTrial } from '../../lib/sera/types';
import {
  closer,
  countTicks,
  ELIGIBLE_COLOR,
  familyBars,
  familyLabel,
  HISTORICAL_COLOR,
  hurdles,
  LAB_COLOR,
  landing,
  latestMethods,
  luck,
  pctText,
  signedPp,
  state,
  trialTip,
} from './overview';

const method = (id: string, over: Partial<LabMethod> = {}): LabMethod => ({
  id,
  name: `Method ${id}`,
  family: id.startsWith('H-') ? 'old-family' : 'new-family',
  parentId: null,
  sourceKind: id.startsWith('H-') ? 'seed' : 'knowledge',
  sourceRef: '',
  hypothesis: `Idea for ${id}. More detail here.`,
  expectedFailure: null,
  status: 'rejected',
  analysis: '',
  verdict: '',
  blockedOn: '',
  created: '2026-10-01T00:00:00+00:00',
  updated: '2026-10-01T00:00:00+00:00',
  historical: id.startsWith('H-'),
  ...over,
});

const trial = (n: number, methodId: string, over: Partial<LabTrial> = {}): LabTrial => withVerdict({
  n,
  methodId,
  candidateId: `${methodId}-C${n}`,
  rulesId: 'r',
  allocatorId: 'a',
  configText: '{}',
  window: 'dev',
  start: '1993-01-29',
  end: '2015-10-16',
  gitSha: 'abc',
  runAt: '2026-10-04T00:00:00+00:00',
  totalReturn: 1,
  cagr: 0.06,
  maxDrawdown: 0.3,
  profitFactor: 1.5,
  pfInfinite: false,
  trades: 200,
  sharpe: 0.5,
  exposure: 0.9,
  turnover: 1,
  worstYear: 2008,
  worstYearReturn: -0.3,
  spyTrReturn: 2,
  spyTrCagr: 0.08,
  mar: 0.2,
  failed: ['beats SPY TR', 'max DD <= 15%'],
  eligible: false,
  dsr: null,
  nTrialsAtRun: n,
  luckGated: true,
  failedNow: [],
  eligibleNow: false,
  dsrNow: null,
  curve: [],
  ...over,
}, over);

const insight = (id: number, kind: LabInsight['kind'], added: string): LabInsight => ({
  id,
  kind,
  title: `${kind} ${id}`,
  body: `Body of ${id}`,
  methodId: null,
  added,
});

const snap = (over: Partial<LabSnapshot> = {}): LabSnapshot => ({
  version: 4,
  asOf: '2026-10-04T14:12:24+00:00',
  gate: {
    maxDrawdown: 0.2,
    minProfitFactor: 1.3,
    minTrades: 100,
    dsrMin: 0.9,
    dsrPolicy: 'all-trials',
    dsrN: 4,
    dsrNBasis: '4 dev trials, every variant run counted as one independent look',
    devStart: '1993-01-29',
    devEnd: '2015-10-16',
    testStart: '2015-10-19',
  },
  data: {
    storeStart: '1993-01-29',
    membershipStart: '1996-01-02',
    fxStart: '1999-01-04',
    fingerprints: [],
    barRows: 0,
    symbolsRequested: 0,
    symbolsServed: 0,
    dividendRows: 0,
  },
  summary: { devTrials: 4, testLooks: 0, methods: 4, labMethods: 2, historicalMethods: 2, insights: 0, byStatus: {} },
  benchmark: { spyTr: [], spyPrice: [] },
  methods: [
    method('H-A'),
    method('H-B'),
    method('M0001', { updated: '2026-10-04T14:00:35+00:00', verdict: 'Fixed drawdown, lost return.' }),
    method('M0002', { status: 'idea', updated: '2026-10-04T14:00:36+00:00' }),
  ],
  trials: [
    // `failed` is each row as recorded under the old 15%/0.95 bars; `failedNow` is the same row
    // at this fixture's gate (20%, 0.90, N = 4). They differ on purpose: H-B's 19% fall and
    // M0001-C3's 0.90 score are both misses in the record and passes today, which is the whole
    // behaviour under test. The two historical rows have no DSR, so they miss the luck check.
    trial(1, 'H-A', { maxDrawdown: 0.55, cagr: 0.089, spyTrCagr: 0.089, failed: ['beats SPY TR', 'max DD <= 15%', 'PF >= 1.3', '>= 100 trades'], failedNow: ['beats SPY TR', 'max DD <= 20%', 'PF >= 1.3', '>= 100 trades', 'DSR >= 0.90'] }),
    trial(2, 'H-B', { maxDrawdown: 0.19, cagr: 0.098, spyTrCagr: 0.089, mar: 0.52, failed: ['max DD <= 15%', '>= 100 trades'], failedNow: ['>= 100 trades', 'DSR >= 0.90'] }),
    trial(3, 'M0001', { maxDrawdown: 0.11, cagr: 0.061, spyTrCagr: 0.079, mar: 0.56, dsr: 0.9, nTrialsAtRun: 4, failed: ['beats SPY TR', 'DSR >= 0.95'], failedNow: ['beats SPY TR'] }),
    trial(4, 'M0001', { maxDrawdown: 0.12, cagr: 0.09, spyTrCagr: 0.079, mar: 0.75, dsr: 0.97, nTrialsAtRun: 4, failed: [], eligible: true, failedNow: [] }),
    trial(5, 'M0001', { window: 'test', maxDrawdown: 0.01, cagr: 0.5 }),
  ],
  insights: [],
  ideasSeen: [],
  paper: [],
  ...over,
});


describe('formatting', () => {
  it('formats percentages and percentage points with a real minus', () => {
    expect(pctText(0.1234)).toBe('12.3%');
    expect(pctText(-0.05)).toBe('−5.0%');
    expect(pctText(null)).toBe('—');
    expect(signedPp(0.012)).toBe('+1.2 pp');
    expect(signedPp(-0.03, 0)).toBe('−3 pp');
  });
  it('lists integer ticks for the hurdle axis', () => {
    expect(countTicks(2)).toEqual([{ value: 0, label: '0' }, { value: 1, label: '1' }, { value: 2, label: '2' }]);
  });
});

describe('landing', () => {
  it('plots only dev tries and colours them by origin', () => {
    const l = landing(snap());
    expect(l.points).toHaveLength(4);
    const byTip = (c: string) => l.points.find(p => p.tip!.startsWith(c))!;
    expect(byTip('H-A-C1').color).toBe(HISTORICAL_COLOR);
    expect(byTip('M0001-C3').color).toBe(LAB_COLOR);
    expect(byTip('M0001-C4').color).toBe(ELIGIBLE_COLOR);
    expect(byTip('M0001-C4').r).toBe(8);
    expect(byTip('M0001-C3').href).toBe('/sera/methods/M0001');
    expect(new Set(l.points.map(p => p.id)).size).toBe(4);
  });
  it('draws eligible tries last', () => {
    const l = landing(snap());
    expect(l.points[l.points.length - 1].color).toBe(ELIGIBLE_COLOR);
    expect(l.points[0].color).toBe(HISTORICAL_COLOR);
  });
  it('shades the pass zone from the gate and keeps it visible', () => {
    const l = landing(snap());
    expect(l.regions[0]).toMatchObject({ x1: 0.2, y0: 0, label: 'Pass zone' });
    expect(l.refY[0].value).toBe(0);
    expect(l.yDomain[1]).toBeGreaterThan(0);
    // H-B (fall 19%, +0.9pp a year over SPY) enters the pass zone at the 20% bar; at 15% only
    // M0001-C4 was inside. This is the owner's 2026-10-07 change, seen on the landing chart.
    expect(l.inZone).toBe(2);
    const base = snap();
    const none = landing({ ...base, trials: base.trials.filter(t => t.n === 1) });
    expect(none.yDomain[1]).toBeGreaterThan(0);
  });
  it('writes the tip the page promises, with plain hurdle names', () => {
    // M0001-C3 recorded `DSR >= 0.95` and its 0.90 score clears today's bar, so the only miss
    // the tip names is the one it still has. The tip reads the verdict, like every other mark.
    expect(trialTip(snap().trials[2])).toBe('M0001-C3: CAGR 6.1% vs SPY 7.9%, max DD 11.0%, misses: Beats SPY');
  });
});

describe('state', () => {
  it('counts tried methods, tries and looks', () => {
    const s = state(snap());
    expect(s.tried).toEqual({ total: 3, lab: 1, historical: 2 });
    expect(s.tries).toBe(4);
    expect(s.looks).toBe(0);
    expect(s.eligible).toBe(1);
  });
  it('finds the best beat within the drawdown gate', () => {
    const s = state(snap());
    expect(s.bestBeat?.trial.n).toBe(4);
    expect(s.bestBeat?.excess).toBeCloseTo(0.011, 6);
  });
  it('reports no best beat when nothing beats SPY inside the gate', () => {
    const base = snap();
    const s = state({ ...base, trials: base.trials.filter(t => t.n !== 4 && t.n !== 2) });
    expect(s.bestBeat).toBeNull();
  });
  it('prefers the newest synthesis over newer insights of other kinds', () => {
    const s = state(snap({
      insights: [
        insight(1, 'synthesis', '2026-10-04T10:00:00+00:00'),
        insight(2, 'synthesis', '2026-10-04T11:00:00+00:00'),
        insight(3, 'observation', '2026-10-04T12:00:00+00:00'),
      ],
    }));
    expect(s.story.source).toBe('synthesis');
    expect(s.story.title).toBe('synthesis 2');
  });
  it('never headlines a non-synthesis note: it computes a plain story instead', () => {
    const s = state(snap({ insights: [insight(1, 'risk', '2026-10-04T10:00:00+00:00'), insight(2, 'observation', '2026-10-04T12:00:00+00:00')] }));
    expect(s.story.source).toBe('computed');
    expect(s.story.title).toBe('Where the search stands');
    expect(s.story.body).toContain('4 tries across 3 methods');
    expect(s.story.body).not.toMatch(/`/);
  });
  it('leads the computed story with a promotion, in plain words', () => {
    const base = snap();
    const methods = base.methods.map((m, i) =>
      i === 0 ? { ...m, analysis: `${m.analysis ?? ''}\n\n# Promotion\n\nPromoted to the paper roster as \`FND\`.\n\nFrozen spec digest: \`4a9d\`.` } : m,
    );
    const s = state({ ...base, methods });
    expect(s.story.title).toBe('A strategy has started paper trading');
    expect(s.story.body).toContain(`“${methods[0].name}”`);
    expect(s.story.body).toContain('short name FND');
    expect(s.story.body).not.toMatch(/digest|`/);
  });
});


describe('hurdles', () => {
  it('has one bar per condition, scaled to the dev try count', () => {
    const h = hurdles(snap());
    expect(h.groups.map(g => g.id)).toEqual(['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr']);
    expect(h.domain).toEqual([0, 4]);
    expect(h.total).toBe(4);
    expect(h.groups[4].items[0]).toMatchObject({ value: 4, valueText: '4' });
    // The luck check could only be scored on the two lab tries, and both clear 0.90 — the bar
    // the fixture's gate holds. The two historical tries have no score, so they miss it and are
    // not in the denominator the tip quotes.
    expect(h.groups[5].items[0]).toMatchObject({ value: 2, valueText: '2' });
    expect(h.groups[5].items[0].tip).toContain('older tries predate it');
    expect(h.hardest).toBe('Beats SPY');
  });
});

describe('closer', () => {
  it('runs over dev try numbers on a 0–6 scale', () => {
    const c = closer(snap());
    expect(c.passedTicks).toHaveLength(7);
    expect(c.passed[0].points.map(p => p[0])).toEqual([1, 2, 3, 4]);
    expect(c.passed[0].step).toBe(true);
    expect(c.latestPassed).toBe(6);
    expect(c.mar).not.toBeNull();
  });
});

describe('luck', () => {
  it('plots only tries with a DSR against the gate line', () => {
    const l = luck(snap())!;
    expect(l.points).toHaveLength(2);
    expect(l.refY[0].value).toBe(0.9);
    expect(l.above).toBe(2); // 0.90 and 0.97 both clear a 0.90 bar
    expect(l.points.map(p => p.x)).toEqual([4, 4]);
    expect(l.yTicks.map(t => t.label)).toEqual(['0.00', '0.25', '0.50', '0.75', '1.00']);
  });
  it('marks the N the gate deflates by today, with its evidence', () => {
    const l = luck(snap())!;
    expect(l.refX[0].value).toBe(4);
    expect(l.refX[0].label).toBe('N = 4 today');
    expect(l.refX[0].tip).toBe('4 dev trials, every variant run counted as one independent look');
    expect(l.n).toBe(4);
    expect(l.policy).toBe('all-trials');
  });
  it('is null when no try has a DSR', () => {
    const base = snap();
    expect(luck({ ...base, trials: base.trials.map(t => ({ ...t, dsr: null })) })).toBeNull();
  });
});

describe('families', () => {
  it('bars families by dev tries, largest first', () => {
    const f = familyBars(snap());
    expect(f.groups.map(g => g.id)).toEqual(['new-family', 'old-family']);
    expect(f.groups[0].items[0].value).toBe(2);
    expect(f.domain).toEqual([0, 2]);
    expect(f.groups[0].items[0].tip).toContain('best MAR');
  });

  it('cuts family labels to 7 characters', () => {
    expect(familyLabel('p7a-f10')).toBe('p7a-f10');
    expect(familyLabel('stock-momentum-risk-managed')).toBe('stock..');
  });
});

describe('latest methods', () => {
  it('lists lab methods newest first with a verdict or the idea', () => {
    const l = latestMethods(snap());
    expect(l.map(m => m.id)).toEqual(['M0002', 'M0001']);
    expect(l[0].blurbIsVerdict).toBe(false);
    expect(l[0].blurb).toBe('Idea for M0002.');
    expect(l[0].tries).toBe(0);
    expect(l[0].bestPassed).toBeNull();
    expect(l[1].blurb).toBe('Fixed drawdown, lost return.');
    expect(l[1].tries).toBe(2);
    expect(l[1].href).toBe('/sera/methods/M0001');
  });
  it('caps at k', () => {
    const many = Array.from({ length: 9 }, (_, i) => method(`M00${10 + i}`, { updated: `2026-10-0${1 + (i % 4)}T00:00:00+00:00` }));
    expect(latestMethods(snap({ methods: many }))).toHaveLength(6);
  });
});
