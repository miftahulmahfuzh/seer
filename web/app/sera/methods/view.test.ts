import { describe, expect, it } from 'vitest';
import { GATE, withVerdict } from '../../../lib/sera/fixture';
import type { LabMethod, LabTrial } from '../../../lib/sera/types';
import {
  anyMoneyWeighted, BEST_COLOR, conditionSentence, count, dsrNote, earned, earnedVs, filterRows, fixed, growthFmt,
  growthLines, hurdlePoints, isAlive,
  longDate,
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

/** Mirrors `lib/sera/fixture`: the verdict follows the record unless a test sets it apart. */
const trial = (over: Partial<LabTrial> = {}): LabTrial => {
  const t: LabTrial = {
    n: 58, methodId: 'M0001', candidateId: 'M0001-TV12', rulesId: 'monthly-hold', allocatorId: 'M0001',
    configText: 'rules=TradeRules(...)', window: 'dev', start: '1996-01-03', end: '2015-10-16', gitSha: 'abc1234',
    runAt: '2026-10-04T12:00:00+07:00', totalReturn: 3.276, cagr: 0.076, maxDrawdown: 0.129, profitFactor: 2.27,
    pfInfinite: false, trades: 1130, sharpe: 0.71, exposure: 0.48, turnover: 3.1, worstYear: 2015,
    worstYearReturn: -0.023, spyTrReturn: 3.514, spyTrCagr: 0.079, mar: 0.59, mwr: null, spyTrMwr: null,
    failed: ['beats SPY TR', 'DSR >= 0.95'], eligible: false, dsr: 0.899, nTrialsAtRun: 58,
    luckGated: true, failedNow: [], eligibleNow: false, dsrNow: null,
    curve: [['1996-01-31', 1], ['1996-02-29', 1.02], ['1997-01-31', 1.1]],
    ...over,
  };
  return withVerdict(t, over);
};

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
  it('treats a missing luck score as a miss, and says why', () => {
    // A P7a seed row: no DSR to re-evaluate at any N. The engine puts the luck label in
    // `failedNow` for exactly these, so the hurdle reads as missed rather than as a blank a
    // reader could take for an excused one — and the sentence gives the reason.
    const seed = trial({ dsr: null, dsrNow: null, failedNow: ['beats SPY TR', 'DSR >= 0.90'] });
    const dsr = marks(seed).find(x => x.key === 'dsr')!;
    expect(dsr.ok).toBe(false);
    expect(markLabel(dsr)).toBe('Luck check: missed');
    expect(conditionSentence('dsr', false, seed, GATE)).toBe(
      'Luck check: no (not measured — the luck test cannot be scored for this trial, so it cannot pass it).',
    );
  });
  it('calls a test run\'s luck check not applicable, and never missed', () => {
    // M0021-B70-RAW's shape: a test look scoring 0.513 with no luck label in `failedNow`, because
    // a single pre-registered try has nothing to discount. Rendered without the engine's marker,
    // this was a green tick against a published bar of 0.90.
    const look = trial({
      window: 'test', start: '2015-10-19', end: '2026-10-01',
      dsr: 0.513013, dsrNow: 0.513013, failed: ['beats SPY TR'], failedNow: ['beats SPY TR'],
    });
    const dsr = marks(look).find(x => x.key === 'dsr')!;
    expect(dsr.ok).toBe(null);
    expect(markLabel(dsr)).toBe('Luck check: not applicable');
    expect(conditionSentence('dsr', null, look, GATE)).toBe(
      'Luck check: does not apply. A test run is a single try booked in advance, so there is ' +
      'nothing to discount for luck (it scored 0.513).',
    );
    // The number is still annotated, but not with an N it was never scored at.
    expect(dsrNote(look, GATE)).toBe('not a hurdle on a test run');
    expect(dsrNote(trial({ dsrNow: 0.9122 }), GATE)).toBe('at N 110');
    expect(dsrNote(trial({ dsr: null, dsrNow: null }), GATE)).toBe(null);
    // And it is counted out of five, not scored 5 of 6 for a hurdle it never had.
    expect(workedSummary(look, GATE).headline).toBe(
      'Not yet. Its best variant, M0001-TV12, cleared 4 of 5 hurdles on 2015–2026 data.',
    );
  });

  it('says what a funded run earned instead of quoting a curve the deposits lifted', () => {
    // The whole point of publishing the pair: on a real funded run the engine reports a total
    // return of +1078% beside an earned rate of 7.6%, and the +1078% is mostly the owner's own
    // deposits. The sentence beside the tick must name the number the tick was decided on.
    const funded = trial({ mwr: 0.0764, spyTrMwr: 0.0712, failed: [], failedNow: [] });
    expect(conditionSentence('spy', true, funded, GATE)).toBe(
      'Beats SPY: yes (your money earned 7.6% a year, against 7.1% from putting the same ' +
      'deposits into SPY on the same days).',
    );
    // An unfunded row is untouched, which is all 128 recorded ones.
    expect(conditionSentence('spy', false, trial(), GATE)).toBe('Beats SPY: no (7.6% vs 7.9% a year).');
  });

  it('gives a funded run its own cells, and leaves an unfunded one exactly as it was', () => {
    const funded = trial({ mwr: 0.0764, spyTrMwr: 0.0712 });
    expect(anyMoneyWeighted([trial(), funded])).toBe(true);
    expect(anyMoneyWeighted([trial(), trial({ n: 2 })])).toBe(false);
    expect(earned(funded)).toBe('+7.6%');
    expect(earnedVs(funded)).toBe('vs +7.1%');
    // Not a dash standing in for a number: an unfunded run has no earned rate to show, because
    // its own return already is one.
    expect(earned(trial())).toBe('—');
    expect(earnedVs(trial())).toBeNull();

    const rows = Object.fromEntries(techRows(funded));
    expect(rows['What the money earned']).toBe('+7.6% a year');
    expect(rows['The same deposits in SPY']).toBe('+7.1% a year');
    expect(Object.keys(Object.fromEntries(techRows(trial())))).not.toContain('What the money earned');
  });

  it('records whether the luck bar applied, from the engine and not from the window', () => {
    const rows = Object.fromEntries(techRows(trial()));
    expect(rows['Luck bar applies']).toBe('yes');
    const look = techRows(trial({ window: 'test', failedNow: ['beats SPY TR'] }));
    expect(Object.fromEntries(look)['Luck bar applies']).toBe(
      'no — a test run has nothing to discount for luck',
    );
  });
  it('quotes the luck score at the gate\'s N, not at the N of the run date', () => {
    // The bug this guards: a score from one N printed against a bar belonging to another. The
    // fixture row was scored at N = 58 and reads 0.9122 at today's N = 110, which clears 0.90.
    const reread = trial({
      dsr: 0.93, nTrialsAtRun: 58, failed: ['DSR >= 0.95'], eligible: false,
      failedNow: [], eligibleNow: true, dsrNow: 0.9122,
    });
    expect(conditionSentence('dsr', true, reread, GATE)).toBe(
      'Luck check: yes (0.912 ≥ 0.90, scored at N = 110).',
    );
  });
  it('writes the plain summary from the gate thresholds', () => {
    const w = workedSummary(trial(), GATE);
    expect(w.headline).toBe('Not yet. Its best variant, M0001-TV12, cleared 4 of 6 hurdles on 1996–2015 data.');
    expect(w.sentence).toBe(
      'Beats SPY: no (7.6% vs 7.9% a year). Max drawdown: yes (12.9% ≤ 20%). ' +
      'Profit factor: yes (2.27 ≥ 1.3). Trade count: yes (1,130 ≥ 100). ' +
      'Owner inputs: yes (none needed). ' +
      'Luck check: no (0.899 < 0.90, scored at N = 110).',
    );
  });
  it('says yes when every hurdle clears', () => {
    const t = trial({ failed: [], failedNow: [], eligible: true, cagr: 0.09, dsr: 0.97, dsrNow: 0.97 });
    expect(workedSummary(t, GATE).headline).toBe('Yes. Its best variant, M0001-TV12, cleared all six hurdles on 1996–2015 data.');
  });
  it('flips the comparison sign on a miss', () => {
    // 0.23 rather than 0.18: the sentence says "> 20%", so the value must actually exceed 20%
    // or the rendered sentence contradicts itself.
    const t = trial({ maxDrawdown: 0.23, failedNow: ['beats SPY TR', 'max DD <= 20%', 'DSR >= 0.90'] });
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
    // Set apart on purpose: the record names the 0.95 bar of its run date, the verdict today's.
    const rows = Object.fromEntries(techRows(trial({ failedNow: ['beats SPY TR', 'DSR >= 0.90'] })));
    expect(rows['Trial number']).toBe('#58');
    expect(rows['Code version (git)']).toBe('abc1234');
    expect(rows['Tries counted when run (N)']).toBe('58');
    expect(rows['Worst year']).toBe('2015 (−2.3%)');
    // Both sides, each labelled: the record names the bars of its run date for ever, the verdict
    // names today's. A reader comparing them can see exactly what the owner's change did.
    expect(rows['Luck score when run']).toBe('0.899 at N = 58');
    expect(rows['Missed when run']).toBe('beats SPY TR; DSR >= 0.95');
    expect(rows['Missed by today\u2019s bars']).toBe('beats SPY TR; DSR >= 0.90');
    const clean = Object.fromEntries(techRows(trial({ failed: [], failedNow: [] })));
    expect(clean['Missed when run']).toBe('nothing: eligible');
    expect(clean['Missed by today\u2019s bars']).toBe('nothing: eligible');
  });
});
