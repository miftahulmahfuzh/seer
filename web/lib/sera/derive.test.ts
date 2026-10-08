import { describe, expect, it } from 'vitest';
import {
  bestVariant,
  closest,
  conditionsPassed,
  drawdownSeries,
  excessCagr,
  families,
  funnel,
  gateChecks,
  misses,
  moneyWeighted,
  progress,
  spyForWindow,
  trialsByMethod,
  yearlyReturns,
} from './derive';
import { GATE, method, trial } from './fixture';
import type { Benchmark } from './types';

describe('moneyWeighted', () => {
  it('is null for a trial that received no deposits, which is every recorded one', () => {
    expect(moneyWeighted(trial())).toBeNull();
  });

  it('is the pair, and only ever the pair', () => {
    expect(moneyWeighted(trial({ mwr: 0.0764, spyTrMwr: 0.0712 }))).toEqual({ mwr: 0.0764, spyTrMwr: 0.0712 });
    // Half a pair is not a funded reading. `dev.beats_spy_tr` falls back to the total-return
    // comparison the moment either number is missing, so a page that showed the surviving half
    // would print a figure the tick beside it was not decided on.
    expect(moneyWeighted(trial({ mwr: 0.0764 }))).toBeNull();
    expect(moneyWeighted(trial({ spyTrMwr: 0.0712 }))).toBeNull();
  });
});

describe('gateChecks', () => {
  it('reads a funded trial on what its money earned, not on its curve', () => {
    // The row's own cagr (7.6%) and spyTrCagr (7.9%) are untouched and would read the old way.
    // Once deposits arrive neither is a return, so the hurdle is printed on the pair the engine
    // actually judged it by.
    const funded = trial({ mwr: 0.0764, spyTrMwr: 0.0712, failedNow: [], failed: [] });
    expect(gateChecks(funded, GATE)[0]).toEqual({
      key: 'spy',
      label: 'Beats SPY',
      value: '+7.6% a year',
      target: 'more than +7.1% a year from the same deposits in SPY',
      ok: true,
    });
  });


  it('lists six hurdles in order with plain labels, values and targets from the gate', () => {
    const checks = gateChecks(trial(), GATE);
    expect(checks.map((c) => c.key)).toEqual(['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr']);
    expect(checks.map((c) => c.label)).toEqual([
      'Beats SPY',
      'Max drawdown',
      'Profit factor',
      'Trade count',
      'Owner inputs',
      'Luck check',
    ]);
    expect(checks[0]).toEqual({
      key: 'spy',
      label: 'Beats SPY',
      value: '+7.6% a year',
      target: 'more than +7.9% a year',
      ok: false,
    });
    expect(checks[1]).toMatchObject({ value: '12.0% at worst', target: '20% or less', ok: true });
    expect(checks[2]).toMatchObject({ value: '1.50', target: '1.3 or more', ok: true });
    expect(checks[3]).toMatchObject({ value: '240', target: '100 or more', ok: true });
    expect(checks[4]).toMatchObject({ value: 'none needed', target: 'none needed', ok: true });
    expect(checks[5]).toMatchObject({ value: '0.97', target: '0.9 or more', ok: true });
  });

  it('reads targets from the gate, not constants', () => {
    // 0.3 rather than 0.2: at 0.2 the override would equal GATE and prove nothing.
    const checks = gateChecks(trial(), { ...GATE, maxDrawdown: 0.3, minProfitFactor: 1.5, minTrades: 50 });
    expect(checks[1].target).toBe('30% or less');
    expect(checks[2].target).toBe('1.5 or more');
    expect(checks[3].target).toBe('50 or more');
  });

  it('shows an infinite profit factor and owner-input misses plainly', () => {
    const checks = gateChecks(
      trial({ profitFactor: null, pfInfinite: true, failed: ['owner inputs'] }),
      GATE,
    );
    expect(checks[2].value).toBe('∞ (no losing trades)');
    expect(checks[4]).toMatchObject({ value: 'needs owner input', ok: false });
  });

  it('marks an unscorable luck check as a miss, and a failed one as a miss under either bar', () => {
    // No DSR to re-evaluate at any N. The engine puts the luck label in `failedNow` for exactly
    // these rows (its D11), so the page shows a cross with "not measured" as the reason — never
    // a blank that a reader could mistake for an excused hurdle.
    const seed = trial({ dsr: null, dsrNow: null, failed: ['beats SPY TR'], failedNow: ['beats SPY TR', 'DSR >= 0.90'] });
    expect(gateChecks(seed, GATE)[5]).toMatchObject({ value: 'not measured', ok: false });
    // The luck label is matched by prefix, so both spellings of the bar read as a miss. Matching
    // one literal would show the other as a tick.
    const old = trial({ dsrNow: 0.4, failedNow: ['DSR >= 0.95'] });
    expect(gateChecks(old, GATE)[5]).toMatchObject({ value: '0.40', ok: false });
    const recent = trial({ dsrNow: 0.4, failedNow: ['DSR >= 0.90'] });
    expect(gateChecks(recent, GATE)[5]).toMatchObject({ value: '0.40', ok: false });
  });

  it('shows a test look as not applicable, never as a cleared hurdle', () => {
    // M0021-B70-RAW exactly: a pre-registered test look scoring 0.513 against a published bar of
    // 0.90, with no luck label in `failedNow` because the gate does not apply to it. Read without
    // `luckGated` this rendered a green tick, which is the whole of R7.
    const look = trial({
      window: 'test', dsr: 0.513013, dsrNow: 0.513013,
      failed: ['beats SPY TR'], failedNow: ['beats SPY TR'],
    });
    expect(look.luckGated).toBe(false);
    expect(gateChecks(look, GATE)[5]).toMatchObject({
      value: '0.51', target: 'does not apply to a test look', ok: null,
    });
    // Not applicable is neither a pass nor a miss: it does not count toward the tally and it does
    // not appear in the misses list.
    expect(conditionsPassed(look)).toBe(4);
    expect(misses(look)).toEqual(['spy']);
    // And the other side of the distinction is untouched: a gated row with no score is a MISS.
    const seed = trial({ dsr: null, dsrNow: null, failed: ['beats SPY TR'], failedNow: ['beats SPY TR', 'DSR >= 0.90'] });
    expect(seed.luckGated).toBe(true);
    expect(gateChecks(seed, GATE)[5]).toMatchObject({ value: 'not measured', ok: false });
  });

  it('judges by the verdict and never by the record, and shows the score at the gate\'s N', () => {
    // M0022-W-TV14 exactly: recorded `DSR >= 0.95` at N = 110 on the day it ran, re-read against
    // today's 0.90 bar and eligible. Judging it by `failed` while printing the target out of
    // `gate` is what rendered `Luck check: no (0.912 < 0.90)` on the live site.
    const reread = trial({
      dsr: 0.91221, nTrialsAtRun: 110, failed: ['DSR >= 0.95'], eligible: false,
      failedNow: [], eligibleNow: true, dsrNow: 0.91221,
    });
    expect(gateChecks(reread, GATE)[5]).toMatchObject({ value: '0.91', target: '0.9 or more', ok: true });
    expect(misses(reread)).toEqual([]);
    expect(conditionsPassed(reread)).toBe(6);

    // And the other direction, which is why the web must not re-threshold `dsr` itself:
    // M0007-N20-RAW scored 0.9138 at N = 85 and reads 0.8985 at today's N = 110.
    const ratcheted = trial({
      dsr: 0.913757, nTrialsAtRun: 85, failed: ['DSR >= 0.95'],
      failedNow: ['DSR >= 0.90'], eligibleNow: false, dsrNow: 0.898468,
    });
    expect(gateChecks(ratcheted, GATE)[5]).toMatchObject({ value: '0.90', ok: false });
    expect(misses(ratcheted)).toEqual(['dsr']);
  });
});

describe('conditionsPassed / misses / excessCagr', () => {
  it('counts only cleared hurdles and lists misses in order', () => {
    const t = trial({ failedNow: ['beats SPY TR', 'PF >= 1.3'] });
    expect(conditionsPassed(t)).toBe(4);
    expect(misses(t)).toEqual(['spy', 'pf']);
    // An unscorable luck check is a miss, so it costs a hurdle rather than being skipped.
    const seed = trial({ dsr: null, dsrNow: null, failedNow: ['beats SPY TR', 'PF >= 1.3', 'DSR >= 0.90'] });
    expect(conditionsPassed(seed)).toBe(3);
    expect(misses(seed)).toEqual(['spy', 'pf', 'dsr']);
    expect(conditionsPassed(trial({ failed: [] }))).toBe(6);
  });

  it('subtracts SPY CAGR', () => {
    expect(excessCagr(trial())).toBeCloseTo(-0.003, 10);
    expect(excessCagr(trial({ cagr: null }))).toBeNull();
  });
});

describe('closest / bestVariant', () => {
  const a = trial({ n: 1, failed: ['beats SPY TR'], mar: 0.63 });
  const b = trial({ n: 2, failed: [], mar: 0.2 });
  const c = trial({ n: 3, failed: ['beats SPY TR'], mar: 0.9 });
  const t = trial({ n: 4, window: 'test', failed: [], mar: 5 });

  it('ranks dev trials by hurdles cleared, then MAR', () => {
    expect(closest([a, b, c, t], 2).map((x) => x.n)).toEqual([2, 3]);
    expect(closest([a, b, c, t], 10).map((x) => x.n)).toEqual([2, 3, 1]);
  });

  it('picks fewest misses first, then MAR, then earliest', () => {
    const worse = trial({ n: 5, failed: ['beats SPY TR', 'PF >= 1.3'], mar: 2 });
    expect(bestVariant([worse, a])?.n).toBe(1);
    expect(bestVariant([a, c])?.n).toBe(3);
    expect(bestVariant([trial({ n: 7, mar: null }), trial({ n: 6, mar: null })])?.n).toBe(6);
    expect(bestVariant([])).toBeNull();
  });

  it('prefers dev trials over test trials', () => {
    expect(bestVariant([a, t])?.n).toBe(1);
    expect(bestVariant([t])?.n).toBe(4);
  });
});

describe('funnel', () => {
  it('counts dev trials clearing each hurdle', () => {
    const rows = funnel([
      trial({ n: 1, failedNow: ['beats SPY TR'], dsrNow: 0.97 }),
      trial({ n: 2, failedNow: ['max DD <= 20%', 'DSR >= 0.90'], dsrNow: 0.5 }),
      // No DSR at any N: it misses the luck check (passing counts it as a miss) but it is not
      // part of the denominator the page quotes, which is what `measured` is for.
      trial({ n: 3, failedNow: ['beats SPY TR', 'DSR >= 0.90'], dsr: null, dsrNow: null }),
      trial({ n: 4, window: 'test', failedNow: [] }),
    ]);
    expect(rows.map((r) => [r.key, r.passing, r.measured, r.total])).toEqual([
      ['spy', 1, 3, 3],
      ['drawdown', 2, 3, 3],
      ['pf', 3, 3, 3],
      ['trades', 3, 3, 3],
      ['owner', 3, 3, 3],
      ['dsr', 1, 2, 3],
    ]);
    expect(rows[5].label).toBe('Luck check');
  });
});

describe('progress', () => {
  it('tracks the best so far over trial number', () => {
    const t1 = trial({ n: 1, failed: ['beats SPY TR', 'PF >= 1.3'], mar: 0.5 });
    const t2 = trial({ n: 2, failed: ['beats SPY TR'], mar: 0.3 });
    const t3 = trial({ n: 3, failed: ['beats SPY TR', 'PF >= 1.3', '>= 100 trades'], mar: null });
    expect(progress([t3, t1, t2])).toEqual([
      { n: 1, passed: 4, bestPassed: 4, mar: 0.5, bestMar: 0.5 },
      { n: 2, passed: 5, bestPassed: 5, mar: 0.3, bestMar: 0.5 },
      { n: 3, passed: 3, bestPassed: 5, mar: null, bestMar: 0.5 },
    ]);
    expect(progress([])).toEqual([]);
  });
});

describe('families', () => {
  it('groups methods and dev trials by family, most tried first', () => {
    const methods = [
      method({ id: 'H-A', family: 'bracket-swing', historical: true }),
      method({ id: 'H-A2', family: 'bracket-swing', historical: true }),
      method({ id: 'M0001', family: 'momentum', historical: false }),
      method({ id: 'M0002', family: 'value', historical: false }),
    ];
    const rows = families(methods, [
      trial({ n: 1, methodId: 'H-A', mar: 0.2, failed: ['beats SPY TR', 'PF >= 1.3'] }),
      trial({ n: 2, methodId: 'H-A2', mar: 0.4, failed: ['beats SPY TR', 'PF >= 1.3'] }),
      trial({ n: 3, methodId: 'M0001', mar: 0.6, failed: ['beats SPY TR'] }),
      trial({ n: 4, methodId: 'M0001', mar: null, failed: ['beats SPY TR'] }),
      trial({ n: 5, methodId: 'GONE', mar: 9 }),
    ]);
    expect(rows).toEqual([
      { family: 'bracket-swing', methodIds: ['H-A', 'H-A2'], trials: 2, bestMar: 0.4, bestPassed: 4, historical: true },
      { family: 'momentum', methodIds: ['M0001'], trials: 2, bestMar: 0.6, bestPassed: 5, historical: false },
      { family: 'value', methodIds: ['M0002'], trials: 0, bestMar: null, bestPassed: 0, historical: false },
    ]);
  });
});

describe('trialsByMethod', () => {
  it('groups by method id ordered by n', () => {
    const m = trialsByMethod([trial({ n: 3 }), trial({ n: 1 }), trial({ n: 2, methodId: 'H-B' })]);
    expect(m.get('M0001')?.map((t) => t.n)).toEqual([1, 3]);
    expect(m.get('H-B')?.map((t) => t.n)).toEqual([2]);
  });
});

describe('spyForWindow', () => {
  const benchmark: Benchmark = {
    spyTr: [
      ['1993-01-29', 1],
      ['1995-12-29', 2],
      ['1996-01-31', 2.2],
      ['1996-02-29', 2.1],
    ],
    spyPrice: [],
  };

  it('rebases SPY to the last point on or before the trial start, on the trial dates', () => {
    const t = trial({
      start: '1996-01-03',
      curve: [
        ['1996-01-31', 0.99],
        ['1996-02-15', 1.0],
        ['1996-02-29', 1.01],
        ['1996-03-29', 1.02],
      ],
    });
    const out = spyForWindow(t, benchmark);
    expect(out.map(([d]) => d)).toEqual(['1996-01-31', '1996-02-15', '1996-02-29']);
    expect(out[0][1]).toBeCloseTo(1.1, 10);
    expect(out[1][1]).toBeCloseTo(1.1, 10);
    expect(out[2][1]).toBeCloseTo(1.05, 10);
  });

  it('uses the first point when the trial starts before the benchmark', () => {
    const t = trial({ start: '1990-01-01', curve: [['1993-01-29', 1], ['1995-12-29', 1.5]] });
    expect(spyForWindow(t, benchmark)).toEqual([
      ['1993-01-29', 1],
      ['1995-12-29', 2],
    ]);
  });

  it('returns nothing for an empty curve', () => {
    expect(spyForWindow(trial({ curve: [] }), benchmark)).toEqual([]);
  });
});

describe('drawdownSeries', () => {
  it('measures each point against the running peak, starting from 1.0', () => {
    const out = drawdownSeries([
      ['a', 1.1],
      ['b', 0.99],
      ['c', 1.21],
    ]);
    expect(out[0]).toEqual(['a', 0]);
    expect(out[1][1]).toBeCloseTo(-0.1, 10);
    expect(out[2]).toEqual(['c', 0]);
    expect(drawdownSeries([['a', 0.9]])[0][1]).toBeCloseTo(-0.1, 10);
  });
});

describe('yearlyReturns', () => {
  it('chains calendar years from the base 1.0', () => {
    const out = yearlyReturns([
      ['1996-06-28', 1.1],
      ['1996-12-31', 1.2],
      ['1997-06-30', 1.5],
      ['1997-12-31', 1.8],
      ['1998-03-31', 1.62],
    ]);
    expect(out.map((y) => y.year)).toEqual([1996, 1997, 1998]);
    expect(out[0].ret).toBeCloseTo(0.2, 10);
    expect(out[1].ret).toBeCloseTo(0.5, 10);
    expect(out[2].ret).toBeCloseTo(-0.1, 10);
    expect(yearlyReturns([])).toEqual([]);
  });
});
