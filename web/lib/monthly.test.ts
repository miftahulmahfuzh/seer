import { describe, expect, it } from 'vitest';
import { strategyMetrics } from './metrics';
import { monthlyTable, monthOf } from './monthly';

const series = (rows: [string, number][]) => rows.map(([date, equity]) => ({ date, equity }));

// Hand-checked fixture. Day 0 is Mon 2026-10-05 (paper start Tue 2026-10-06), so October is a
// partial first month. The next session is 2026-12-03, so December is the partial current month.
// November has no closed trades.
const STRAT = series([
  ['2026-10-05', 1000], // day 0: initial cash
  ['2026-10-06', 1010],
  ['2026-10-30', 990], // October's last session
  ['2026-11-02', 1020],
  ['2026-11-16', 960],
  ['2026-11-30', 1000], // November's last session
  ['2026-12-01', 1050],
  ['2026-12-02', 1029],
]);
const SPY = series([
  ['2026-10-05', 500],
  ['2026-10-06', 505],
  ['2026-10-30', 510],
  ['2026-11-02', 500],
  ['2026-11-16', 495],
  ['2026-11-30', 520],
  ['2026-12-01', 520],
  ['2026-12-02', 546],
]);
const EXITS = ['2026-10-30', '2026-12-01', '2026-12-02'];

describe('monthlyTable: hand-checked fixture', () => {
  const t = monthlyTable({ snaps: STRAT, spy: SPY, exitDates: EXITS, sessionDate: '2026-12-03' });

  it('splits on calendar-month boundaries, oldest first', () => {
    expect(t.months.map(m => [m.month, m.from, m.to])).toEqual([
      ['2026-10', '2026-10-05', '2026-10-30'], // base = day 0
      ['2026-11', '2026-10-30', '2026-11-30'], // base = October's last snapshot
      ['2026-12', '2026-11-30', '2026-12-02'], // base = November's last snapshot
    ]);
  });

  it('computes each month from its base', () => {
    const [oct, nov, dec] = t.months;
    expect(oct.return).toBeCloseTo(990 / 1000 - 1, 12); // -1.00%
    expect(nov.return).toBeCloseTo(1000 / 990 - 1, 12); // +1.01%
    expect(dec.return).toBeCloseTo(1029 / 1000 - 1, 12); // +2.90%
  });

  it('puts SPY over the same dates', () => {
    const [oct, nov, dec] = t.months;
    expect(oct.spyReturn).toBeCloseTo(510 / 500 - 1, 12); // +2.00%
    expect(nov.spyReturn).toBeCloseTo(520 / 510 - 1, 12); // +1.96%
    expect(dec.spyReturn).toBeCloseTo(546 / 520 - 1, 12); // +5.00%
  });

  it('counts trades by exit month, zero for a month with none', () => {
    expect(t.months.map(m => m.trades)).toEqual([1, 0, 2]);
  });

  it('measures the worst drop within each month', () => {
    const [oct, nov, dec] = t.months;
    expect(oct.worstDrop).toBeCloseTo((1010 - 990) / 1010, 12); // 1.98%
    expect(nov.worstDrop).toBeCloseTo((1020 - 960) / 1020, 12); // 5.88%
    expect(dec.worstDrop).toBeCloseTo((1050 - 1029) / 1050, 12); // 2.00%
  });

  it('marks the first and the current month partial, not the full month between', () => {
    expect(t.months.map(m => m.partial)).toEqual([true, false, true]);
  });

  it('adds a since-start row with the metrics.ts definitions', () => {
    expect(t.sinceStart).not.toBeNull();
    const ss = t.sinceStart!;
    expect([ss.from, ss.to]).toEqual(['2026-10-05', '2026-12-02']);
    expect(ss.return).toBeCloseTo(0.029, 12);
    expect(ss.spyReturn).toBeCloseTo(546 / 500 - 1, 12); // +9.20%
    expect(ss.trades).toBe(3);
    expect(ss.worstDrop).toBeCloseTo((1020 - 960) / 1020, 12);
    const m = strategyMetrics(STRAT, []);
    expect(ss.return).toBe(m.totalReturn);
    expect(ss.worstDrop).toBe(m.maxDrawdown);
  });

  it('chains: compounding the months gives the since-start return', () => {
    const chained = t.months.reduce((a, m) => a * (1 + m.return), 1) - 1;
    expect(chained).toBeCloseTo(t.sinceStart!.return, 12);
  });
});

describe('monthlyTable: edges', () => {
  it('seeds the running peak at the base, so a month that opens lower shows its drop', () => {
    const t = monthlyTable({
      snaps: series([['2026-10-30', 1000], ['2026-11-02', 950], ['2026-11-03', 980]]),
      spy: null, exitDates: [], sessionDate: '2026-11-04',
    });
    expect(t.months).toHaveLength(1);
    expect(t.months[0].worstDrop).toBeCloseTo(0.05, 12);
    expect(t.months[0].return).toBeCloseTo(-0.02, 12);
    expect(t.months[0].spyReturn).toBeNull();
  });

  it('has a full first month when day 0 falls in the month before', () => {
    const t = monthlyTable({
      snaps: series([['2026-10-30', 1000], ['2026-11-02', 1010], ['2026-11-30', 1020]]),
      spy: null, exitDates: [], sessionDate: '2026-12-01',
    });
    expect(t.months.map(m => [m.month, m.partial])).toEqual([['2026-11', false]]); // no October row: day 0 only
  });

  it('treats the latest month as partial when the next session is unknown', () => {
    const t = monthlyTable({
      snaps: series([['2026-10-30', 1000], ['2026-11-30', 1020]]), spy: null, exitDates: [], sessionDate: null,
    });
    expect(t.months[0].partial).toBe(true);
  });

  it('shows nothing before the first paper session', () => {
    expect(monthlyTable({ snaps: series([['2026-10-05', 1000]]), spy: null, exitDates: [], sessionDate: '2026-10-06' }))
      .toEqual({ months: [], sinceStart: null });
    expect(monthlyTable({ snaps: [], spy: null, exitDates: [], sessionDate: null })).toEqual({ months: [], sinceStart: null });
  });

  it('sorts its input and leaves SPY empty where SPY has no snapshot on a base or end date', () => {
    const snaps = series([['2026-11-02', 1010], ['2026-10-30', 1000], ['2026-12-01', 1030], ['2026-11-30', 1020]]);
    const spy = series([['2026-10-30', 500], ['2026-11-30', 510]]); // no 2026-12-01
    const t = monthlyTable({ snaps, spy, exitDates: [], sessionDate: '2026-12-02' });
    expect(t.months.map(m => m.month)).toEqual(['2026-11', '2026-12']);
    expect(t.months[0].spyReturn).toBeCloseTo(0.02, 12);
    expect(t.months[1].spyReturn).toBeNull();
    expect(t.sinceStart!.spyReturn).toBeNull();
  });

  it('reads the month from a date string', () => {
    expect(monthOf('2026-10-05')).toBe('2026-10');
  });
});
