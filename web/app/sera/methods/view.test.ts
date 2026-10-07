import { describe, expect, it } from 'vitest';
import { GATE } from '../../../lib/sera/fixture';
import type { LabMethod, LabTrial } from '../../../lib/sera/types';
import {
  BEST_COLOR, conditionSentence, count, filterRows, fixed, growthFmt, growthLines, hurdlePoints, isAlive, longDate,
  markLabel, marks, methodRows, parseShow, pct1, pfText, showCounts, showHref, signed1, sortMethods, sourceHref,
  SPY_COLOR, SPY_DASH, techRows, untestedNote, windowText, workedSummary, yearPairs,
} from './view';

const method = (over: Partial<LabMethod> = {}): LabMethod => ({
  id: 'M0001', name: 'Momentum scaled by its own volatility', family: 'stock-momentum-risk-managed', parentId: null,
  sourceKind: 'paper', sourceRef: 'Barroso & Santa-Clara (2015)', hypothesis: 'Scaling cuts crashes.',
  expectedFailure: 'The target cuts CAGR below SPY.', status: 'rejected', analysis: '', verdict: 'Fixed DD, lost return.',
  blockedOn: '', created: '2026-10-04T10:00:00+07:00', updated: '2026-10-04T12:00:00+07:00', historical: false,
  ...over,
});

const trial = (over: Partial<LabTrial> = {}): LabTrial => ({
  n: 58, methodId: 'M0001', candidateId: 'M0001-TV12', rulesId: 'monthly-hold', allocatorId: 'M0001',
  configText: 'rules=TradeRules(...)', window: 'dev', start: '1996-01-03', end: '2015-10-16', gitSha: 'abc1234',
  runAt: '2026-10-04T12:00:00+07:00', totalReturn: 3.276, cagr: 0.076, maxDrawdown: 0.129, profitFactor: 2.27,
  pfInfinite: false, trades: 1130, sharpe: 0.71, exposure: 0.48, turnover: 3.1, worstYear: 2015,
  worstYearReturn: -0.023, spyTrReturn: 3.514, spyTrCagr: 0.079, mar: 0.59,
  failed: ['beats SPY TR', 'DSR >= 0.95'], eligible: false, dsr: 0.899, nTrialsAtRun: 58,
  curve: [['1996-01-31', 1], ['1996-02-29', 1.02], ['1997-01-31', 1.1]],
  ...over,
});

describe('parseShow / showHref', () => {
  it('accepts the four filters', () => {
    expect(parseShow('lab')).toBe('lab');
    expect(parseShow('historical')).toBe('historical');
    expect(parseShow('alive')).toBe('alive');
    expect(parseShow('all')).toBe('all');
  });
  it('falls back to all', () => {
    expect(parseShow(undefined)).toBe('all');
    expect(parseShow('nope')).toBe('all');
    expect(parseShow(['alive', 'lab'])).toBe('alive');
  });
  it('drops the query for all', () => {
    expect(showHref('all')).toBe('/sera/methods');
    expect(showHref('alive')).toBe('/sera/methods?show=alive');
  });
});

describe('sortMethods', () => {
  it('puts lab methods first by id desc, then historical by id', () => {
    const ms = ['H-P7A-F1', 'M0001', 'H-A', 'M0003', 'M0002'].map(id => method({ id, historical: id.startsWith('H-') }));
    expect(sortMethods(ms).map(m => m.id)).toEqual(['M0003', 'M0002', 'M0001', 'H-A', 'H-P7A-F1']);
  });
});

describe('isAlive / methodRows', () => {
  it('counts live statuses as alive with no trials', () => {
    expect(isAlive(method({ status: 'paper' }), null)).toBe(true);
    expect(isAlive(method({ status: 'dev-eligible' }), null)).toBe(true);
    expect(isAlive(method({ status: 'idea' }), null)).toBe(false);
  });
  it('counts one miss as alive, two as not', () => {
    expect(isAlive(method(), trial({ failed: ['beats SPY TR'] }))).toBe(true);
    expect(isAlive(method(), trial())).toBe(false);
  });
  it('builds a row per method with best variant and passed count', () => {
    const rows = methodRows(
      [method(), method({ id: 'M0002', status: 'idea', parentId: 'M0001' })],
      [trial()],
    );
    expect(rows.map(r => r.method.id)).toEqual(['M0002', 'M0001']);
    expect(rows[0]).toMatchObject({ best: null, tries: 0, passed: null, alive: false });
    expect(rows[1].best?.n).toBe(58);
    expect(rows[1]).toMatchObject({ tries: 1, passed: 4, alive: false });
  });
});

describe('filterRows / showCounts', () => {
  const rows = methodRows(
    [method(), method({ id: 'H-A', historical: true }), method({ id: 'M0002', status: 'paper' })],
    [trial()],
  );
  it('filters lab, historical and alive', () => {
    expect(filterRows(rows, 'lab').map(r => r.method.id)).toEqual(['M0002', 'M0001']);
    expect(filterRows(rows, 'historical').map(r => r.method.id)).toEqual(['H-A']);
    expect(filterRows(rows, 'alive').map(r => r.method.id)).toEqual(['M0002']);
    expect(filterRows(rows, 'all')).toHaveLength(3);
  });
  it('counts every filter', () => {
    expect(showCounts(rows)).toEqual({ all: 3, lab: 2, historical: 1, alive: 1 });
  });
});

describe('sourceHref', () => {
  it('finds a URL and trims trailing punctuation', () => {
    expect(sourceHref('See https://example.com/paper.pdf.')).toBe('https://example.com/paper.pdf');
  });
  it('turns a DOI into a doi.org link', () => {
    expect(sourceHref('Barroso & Santa-Clara (2015), JFE, doi:10.1016/j.jfineco.2014.11.010'))
      .toBe('https://doi.org/10.1016/j.jfineco.2014.11.010');
  });
  it('returns null for a plain citation or a repo path', () => {
    expect(sourceHref('Daniel & Moskowitz (2016), Momentum crashes, JFE 122(2)')).toBeNull();
    expect(sourceHref('docs/backtests/2026-10-04-p7a-dev-exploration.md')).toBeNull();
    expect(sourceHref('')).toBeNull();
  });
});

describe('formatting', () => {
  it('formats percents, numbers and dates', () => {
    expect(pct1(0.076)).toBe('7.6%');
    expect(pct1(-0.123)).toBe('−12.3%');
    expect(pct1(null)).toBe('—');
    expect(signed1(0.076)).toBe('+7.6%');
    expect(signed1(-0.003)).toBe('−0.3%');
    expect(fixed(2.271)).toBe('2.27');
    expect(fixed(null)).toBe('—');
    expect(count(1130)).toBe('1,130');
    expect(longDate('2026-10-04T21:17:00+07:00')).toBe('Oct 4, 2026');
    expect(longDate('2015-10-16')).toBe('Oct 16, 2015');
    expect(windowText(trial())).toBe('1996–2015');
  });
  it('shows ∞ for a variant that never lost', () => {
    expect(pfText(trial({ pfInfinite: true, profitFactor: null }))).toBe('∞');
    expect(pfText(trial())).toBe('2.27');
  });
});

describe('marks / workedSummary', () => {
  it('marks the failed hurdles from the engine list', () => {
    const m = Object.fromEntries(marks(trial()).map(x => [x.key, x.ok]));
    expect(m).toEqual({ spy: false, drawdown: true, pf: true, trades: true, owner: true, dsr: false });
    expect(markLabel(marks(trial())[0])).toBe('Beats SPY: missed');
  });
  it('treats a missing luck score as not measured', () => {
    const dsr = marks(trial({ dsr: null, failed: ['beats SPY TR'] })).find(x => x.key === 'dsr')!;
    expect(dsr.ok).toBeNull();
    expect(markLabel(dsr)).toBe('Luck check: not measured');
    expect(conditionSentence('dsr', null, trial({ dsr: null }), GATE)).toBe('Luck check: not measured.');
  });
  it('writes the plain summary from the gate thresholds', () => {
    const w = workedSummary(trial(), GATE);
    expect(w.headline).toBe('Not yet. Its best variant, M0001-TV12, cleared 4 of 6 hurdles on 1996–2015 data.');
    expect(w.sentence).toBe(
      'Beats SPY: no (7.6% vs 7.9% a year). Max drawdown: yes (12.9% ≤ 20%). ' +
      'Profit factor: yes (2.27 ≥ 1.3). Trade count: yes (1,130 ≥ 100). ' +
      'Owner inputs: yes (none needed). ' +
      'Luck check: no (0.899 < 0.90, scored at N = 58).',
    );
  });
  it('says yes when every hurdle clears', () => {
    const t = trial({ failed: [], eligible: true, cagr: 0.09, dsr: 0.97 });
    expect(workedSummary(t, GATE).headline).toBe('Yes. Its best variant, M0001-TV12, cleared all six hurdles on 1996–2015 data.');
  });
  it('flips the comparison sign on a miss', () => {
    // 0.23 rather than 0.18: the sentence says "> 20%", so the value must actually exceed 20%
    // or the rendered sentence contradicts itself.
    const t = trial({ maxDrawdown: 0.23, failed: ['beats SPY TR', 'max DD <= 15%', 'DSR >= 0.95'] });
    expect(conditionSentence('drawdown', false, t, GATE)).toBe('Max drawdown: no (23.0% > 20%).');
  });
});

describe('chart shaping', () => {
  it('formats growth of 1', () => {
    expect(growthFmt(1.5)).toBe('1.5×');
    expect(growthFmt(12.3)).toBe('12×');
  });
  it('draws the best variant last in coral and SPY dotted after it, on ISO dates', () => {
    const a = trial({ n: 55, candidateId: 'M0001-TV10' });
    const b = trial();
    const spy: [string, number][] = [['1996-01-31', 1], ['1997-01-31', 1.2]];
    const lines = growthLines([b, a], b, spy);
    expect(lines.map(l => l.id)).toEqual(['M0001-TV10', 'M0001-TV12', 'SPY']);
    expect(lines[0].dash).toBeUndefined();
    expect(lines[1]).toMatchObject({ color: BEST_COLOR, width: 2.5, label: 'M0001-TV12 (best)' });
    expect(lines[1].points).toEqual(b.curve);
    expect(lines[2]).toMatchObject({ color: SPY_COLOR, dash: SPY_DASH, points: spy });
  });
  it('omits SPY when there is no benchmark series', () => {
    expect(growthLines([trial()], trial(), []).map(l => l.id)).toEqual(['M0001-TV12']);
  });
  it('pairs only the years both series have', () => {
    expect(yearPairs([{ year: 1997, ret: 0.1 }, { year: 1996, ret: 0.05 }, { year: 2016, ret: 0.2 }],
      [{ year: 1996, ret: 0.2 }, { year: 1997, ret: 0.3 }]))
      .toEqual([{ year: 1996, method: 0.05, spy: 0.2 }, { year: 1997, method: 0.1, spy: 0.3 }]);
  });
  it('places own dev trials last and skips test or incomplete ones', () => {
    const pts = hurdlePoints([
      trial(),
      trial({ n: 3, methodId: 'H-P7A-F4', candidateId: 'F4-MOM12', cagr: 0.162, maxDrawdown: 0.222 }),
      trial({ n: 59, window: 'test' }),
      trial({ n: 4, methodId: 'H-A', maxDrawdown: null }),
    ], 'M0001');
    expect(pts.map(p => [p.id, p.own])).toEqual([['3', false], ['58', true]]);
    expect(pts[0].href).toBe('/sera/methods/H-P7A-F4');
    expect(pts[1].x).toBeCloseTo(0.129);
    expect(pts[1].y).toBeCloseTo(-0.003);
    expect(pts[1].tip).toBe('M0001-TV12: −0.3% a year vs SPY, worst fall 12.9%');
  });
});

describe('text', () => {
  it('explains untested methods by status', () => {
    expect(untestedNote(method({ status: 'idea' }))).toMatch(/^Not tested yet\./);
    expect(untestedNote(method({ status: 'blocked-data', blockedOn: 'point-in-time fundamentals' })))
      .toBe('Not tested: it needs data the lab does not have yet (point-in-time fundamentals).');
    expect(untestedNote(method({ status: 'registered' }))).toBe('Registered with its exact rules, not run yet.');
  });
  it('lists the technical record', () => {
    const rows = Object.fromEntries(techRows(trial()));
    expect(rows['Trial number']).toBe('#58');
    expect(rows['Code version (git)']).toBe('abc1234');
    expect(rows['Tries counted when run (N)']).toBe('58');
    expect(rows['Worst year']).toBe('2015 (−2.3%)');
    expect(rows['Failed']).toBe('beats SPY TR; DSR >= 0.95');
    expect(Object.fromEntries(techRows(trial({ failed: [] })))['Failed']).toBe('nothing: eligible');
  });
});
