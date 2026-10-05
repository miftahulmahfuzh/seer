import { describe, expect, it } from 'vitest';
import type { Snapshot } from '../../../lib/metrics';
import type { MonthlyTable } from '../../../lib/monthly';
import {
  CHECKS, compare, LOOK_PERIOD, looks, MIN_COMMON_SESSIONS, MIN_RANKED, monthLabel, monthLines,
  NO_GATE, pickResearch, researchOf, retiredLabel, scoreOf, sinceStartLine, spyOverSpan,
  windowLine, type RankIn, type RosterIn,
} from './view';

const roster: RosterIn[] = [
  { id: 'SPY', isChampion: true, isBenchmark: true },
  { id: 'A', isChampion: false, isBenchmark: false },
  { id: 'F4-MOM12-N20-TREND', isChampion: false, isBenchmark: false },
  { id: 'F1-SPY-SMA200-M', isChampion: false, isBenchmark: false },
  { id: 'C', isChampion: false, isBenchmark: false },
];
const RESEARCH = ['A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M', 'C'];

describe('looks', () => {
  it('gives the benchmark the dotted line on a plain sheet', () => {
    expect(looks(roster).get('SPY')).toEqual({ bg: 'bg-sheet', tint: 'var(--sheet)', line: 'var(--ink-3)', width: 1.75, dash: '1 4' });
  });
  it('assigns research sheets, and lines of the same colour, in roster order', () => {
    const l = looks(roster);
    expect(RESEARCH.map(id => l.get(id)!.bg)).toEqual(['bg-lav', 'bg-sky', 'bg-sage', 'bg-rose']);
    expect(RESEARCH.map(id => l.get(id)!.tint)).toEqual(['var(--lav)', 'var(--sky)', 'var(--sage)', 'var(--rose)']);
    expect(RESEARCH.map(id => l.get(id)!.line)).toEqual(['var(--lav-line)', 'var(--sky-line)', 'var(--sage-line)', 'var(--rose-line)']);
    expect(RESEARCH.map(id => l.get(id)!.width)).toEqual([2, 2, 2, 2]);
    expect(RESEARCH.map(id => l.get(id)!.dash)).toEqual([null, null, null, null]);
  });
  it('never gives C the look of A', () => {
    const l = looks(roster);
    expect(l.get('C')).not.toEqual(l.get('A'));
    expect(l.get('C')).toEqual({ bg: 'bg-rose', tint: 'var(--rose)', line: 'var(--rose-line)', width: 2, dash: null });
  });
  it('follows roster order, not ids', () => {
    const l = looks([roster[3], roster[0], roster[1]]);
    expect(l.get('F1-SPY-SMA200-M')!.bg).toBe('bg-lav');
    expect(l.get('A')!.bg).toBe('bg-sky');
  });
  it('gives six research strategies six different sheets, butter never among them', () => {
    const extra = ['X9', 'X10'].map(id => ({ id, isChampion: false, isBenchmark: false }));
    const l = looks([...roster, ...extra]);
    const bgs = [...RESEARCH, ...extra.map(e => e.id)].map(id => l.get(id)!.bg);
    expect(new Set(bgs).size).toBe(6);
    expect(bgs).not.toContain('bg-butter');
    expect(bgs).not.toContain('bg-sheet');
    expect(l.get('X9')).toEqual({ bg: 'bg-plum', tint: 'var(--plum)', line: 'var(--plum-line)', width: 2, dash: null });
    expect(l.get('X10')).toEqual({ bg: 'bg-stone', tint: 'var(--stone)', line: 'var(--stone-line)', width: 2, dash: null });
  });
  it('dashes the second lap of the palette', () => {
    const many: RosterIn[] = Array.from({ length: 7 }, (_, i) => ({ id: `S${i}`, isChampion: false, isBenchmark: false }));
    const l = looks(many);
    expect(l.get('S6')).toEqual({ bg: 'bg-lav', tint: 'var(--lav)', line: 'var(--lav-line)', width: 2, dash: '7 5' });
  });
  it('never gives two research strategies the same line, up to LOOK_PERIOD', () => {
    expect(LOOK_PERIOD).toBe(12);
    const many: RosterIn[] = Array.from({ length: LOOK_PERIOD }, (_, i) => ({
      id: `S${i}`, isChampion: false, isBenchmark: false,
    }));
    const l = looks(many);
    const seen = many.map(st => `${l.get(st.id)!.line}|${l.get(st.id)!.dash}`);
    expect(new Set(seen).size).toBe(LOOK_PERIOD);
  });
  it('emphasises a non-benchmark champion', () => {
    const l = looks([{ ...roster[0], isChampion: false }, { ...roster[1], isChampion: true }]);
    expect(l.get('A')!.width).toBe(2.75);
  });
});

describe('researchOf', () => {
  it('lists research strategies only', () => {
    expect(researchOf(roster).map(s => s.id)).toEqual(RESEARCH);
  });
});

// --- the common-window comparison (R3, invariant 6) ---------------------------------------------

/** `n` consecutive dates from `start`. compare() reads dates, not a calendar: weekends do not matter. */
function days(start: string, n: number): string[] {
  const t0 = Date.parse(`${start}T00:00:00Z`);
  return Array.from({ length: n }, (_, i) => new Date(t0 + i * 86_400_000).toISOString().slice(0, 10));
}
const curveOf = (start: string, equities: number[]): Snapshot[] =>
  days(start, equities.length).map((date, i) => ({ date, equity: equities[i] }));
/** 100000 on every date but the last, so the window's total return is exactly `ret`. */
const flatThen = (n: number, ret: number) => [...Array(n - 1).fill(100000), 100000 * (1 + ret)];

const st = (id: string, status: 'active' | 'retired' = 'active'): RankIn =>
  ({ id, isChampion: false, isBenchmark: false, status });
const bench: RankIn = { id: 'SPY', isChampion: true, isBenchmark: true, status: 'active' };

// Shared window: 2026-03-02 .. 2026-05-03, 63 sessions — exactly MIN_COMMON_SESSIONS, so every
// fixture here is the smallest board that can be ranked at all.
const SHARED = '2026-03-02';
const N = MIN_COMMON_SESSIONS;        // 63
const A1 = { strategy: st('A1'), curve: curveOf(SHARED, flatThen(N, 0.01)) };
const B1 = { strategy: st('B1'), curve: curveOf(SHARED, flatThen(N, 0.005)) };
// Doubled its money before the window opened; inside it, it made 0.2%. Raw total return would
// crown it; the common window must not.
const OLD = {
  strategy: st('OLD'),
  curve: curveOf('2026-01-31', [...Array(30).fill(50000), ...flatThen(N, 0.002)]),
};
const SPY_ROW = { strategy: bench, curve: curveOf(SHARED, flatThen(N, 0.9)) };

describe('compare', () => {
  it('ranks over the sessions every compared strategy shares, and reports that window', () => {
    const c = compare([SPY_ROW, A1, B1, OLD]);
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
    expect(c.ranked.map(r => r.strategy.id)).toEqual(['A1', 'B1', 'OLD']);
    expect(c.best?.strategy.id).toBe('A1');
    expect(c.best?.totalReturn).toBeCloseTo(0.01, 10);
    expect(c.best?.sessions).toBe(63);

    // Every figure below is `as_json(compare(...))` from seer_engine/paper/compare.py on these
    // very fixtures, not a hand-computed expectation: the port is pinned against the reference
    // implementation, which is the one failure mode a port has that a call does not.
    //   totalReturn, cagr, maxDrawdown, sharpe, inception
    const PY: Record<string, [number, number, number, number, number]> = {
      A1: [0.01, 0.0603708262, 0, 2.0160645150967413, 0.01],
      B1: [0.005, 0.0298181679, 0, 2.0160645150967413, 0.005],
      OLD: [0.002, 0.0118400363, 0, 2.0160645150967413, 1.004],
    };
    for (const r of c.ranked) {
      const [tr, cagr, dd, sharpe, inception] = PY[r.strategy.id];
      expect(r.totalReturn!).toBeCloseTo(tr, 12);
      expect(r.cagr!).toBeCloseTo(cagr, 9);
      expect(r.maxDrawdown!).toBeCloseTo(dd, 12);
      expect(r.sharpe!).toBeCloseTo(sharpe, 12);
      expect(r.inception!).toBeCloseTo(inception, 12);
    }
    // All three curves have the same shape, so Sharpe ties and the rank falls through to total
    // return descending — Python ranks them 1/2/3 in exactly this order for exactly that reason.
    expect(new Set(c.ranked.map(r => r.sharpe)).size).toBe(1);
  });

  it('is the engine module’s minimum, not its own', () => {
    // The one number that must never drift from seer_engine/paper/compare.py.
    expect(MIN_COMMON_SESSIONS).toBe(63);
    expect(MIN_RANKED).toBe(2);
  });

  it('drops the worst-overlapping strategy rather than ranking nothing', () => {
    // compare.py's `_select`: ODD overlaps the others by only 20 sessions, so including it would
    // leave the board below 63. It goes; the other three still rank over their own 63.
    const odd = { strategy: st('ODD'), curve: curveOf('2026-04-14', flatThen(80, 0.4)) };
    const c = compare([A1, B1, OLD, odd]);
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
    expect(c.ranked.map(r => r.strategy.id)).toEqual(['A1', 'B1', 'OLD']);
    expect(c.rows.find(r => r.strategy.id === 'ODD')!.status).toBe('insufficient');
    expect(c.best!.strategy.id).toBe('A1'); // +40% but unranked: it does not win
  });

  it('does not depend on the order the rows arrive in', () => {
    const base = compare([A1, B1, OLD]);
    const shuffled = compare([OLD, B1, A1]);
    expect(shuffled.ranked.map(r => r.strategy.id)).toEqual(base.ranked.map(r => r.strategy.id));
    expect(shuffled.window).toEqual(base.window);
  });

  it('does not crown a return earned outside the window (what bestResearch got wrong)', () => {
    const c = compare([A1, B1, OLD]);
    const old = c.rows.find(r => r.strategy.id === 'OLD')!;
    expect(old.inception).toBeCloseTo(100200 / 50000 - 1, 10); // +100.4% inception to date
    expect(old.totalReturn).toBeCloseTo(0.002, 10);            // +0.2% over the shared window
    expect(c.best!.strategy.id).toBe('A1');                    // raw max would have said OLD
    expect(c.best!.totalReturn!).toBeLessThan(old.inception!);
  });

  it('never compares the benchmark', () => {
    const c = compare([SPY_ROW, A1, B1]);
    expect(c.rows.map(r => r.strategy.id)).toEqual(['A1', 'B1']);
  });

  it('calls a newcomer insufficient without letting it shorten the others’ window', () => {
    const fresh = { strategy: st('NEW'), curve: curveOf('2026-04-20', flatThen(9, 0.05)) };
    const c = compare([A1, B1, OLD, fresh]);
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
    const n = c.rows.find(r => r.strategy.id === 'NEW')!;
    expect(n.status).toBe('insufficient');
    expect(n.sessions).toBe(9);
    expect(c.ranked.map(r => r.strategy.id)).toEqual(['A1', 'B1', 'OLD']);
    expect(c.best!.strategy.id).toBe('A1'); // +5% but unranked: it does not win
  });

  it('keeps a retired strategy’s record, out of the ranking and out of the window', () => {
    const gone = { strategy: st('GONE', 'retired'), curve: curveOf(SHARED, flatThen(N, 0.2)) };
    const c = compare([A1, B1, OLD, gone]);
    const g = c.rows.find(r => r.strategy.id === 'GONE')!;
    expect(g.status).toBe('retired');
    expect(g.inception).toBeCloseTo(0.2, 10);     // the record stands
    expect(g.totalReturn).toBeNull();             // but it is not a ranking
    expect(c.ranked.map(r => r.strategy.id)).not.toContain('GONE');
    expect(c.best!.strategy.id).toBe('A1');       // +20% retired does not win
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
  });

  it('ranks nothing while the common window is short, and still reports how short', () => {
    const short = MIN_COMMON_SESSIONS - 11;   // 52
    const c = compare([
      { strategy: st('A1'), curve: curveOf(SHARED, flatThen(short, 0.01)) },
      { strategy: st('B1'), curve: curveOf(SHARED, flatThen(short, 0.02)) },
    ]);
    expect(c.ranked).toEqual([]);
    expect(c.best).toBeNull();
    // `window` is null whenever nothing ranked — compare.py's own guarantee. How short the board
    // still is lives in `shared`, which is never a ranking.
    expect(c.window).toBeNull();
    expect(c.shared).toBe(short);
    expect(c.rows.map(r => r.status)).toEqual(['insufficient', 'insufficient']);
  });

  it('leaves every windowed figure null on any row it did not rank', () => {
    const gone = { strategy: st('GONE', 'retired'), curve: curveOf(SHARED, flatThen(N, 0.2)) };
    const fresh = { strategy: st('NEW'), curve: curveOf('2026-04-20', flatThen(9, 0.05)) };
    for (const r of compare([A1, B1, gone, fresh]).rows) {
      if (r.status === 'ranked') continue;
      expect([r.totalReturn, r.cagr, r.maxDrawdown, r.sharpe]).toEqual([null, null, null, null]);
    }
  });
});

describe('windowLine', () => {
  it('names the window the ranking used and how many strategies it covered', () => {
    const w = windowLine(compare([A1, B1, OLD]));
    expect(w.label).toBe('Ranked over Mar 2 – May 3');
    expect(w.detail).toBe('63 shared sessions · 3 of 3 active strategies compared');
  });
  it('says how far off a window is rather than showing an unearned ranking', () => {
    const short = MIN_COMMON_SESSIONS - 11;
    const w = windowLine(compare([
      { strategy: st('A1'), curve: curveOf(SHARED, flatThen(short, 0.01)) },
      { strategy: st('B1'), curve: curveOf(SHARED, flatThen(short, 0.02)) },
    ]));
    expect(w.label).toBe('No common window yet');
    expect(w.detail).toBe(`${short} of ${MIN_COMMON_SESSIONS} sessions shared by every strategy`);
  });
});

describe('spyOverSpan', () => {
  it('measures the benchmark over the strategy’s own span, not over its whole record', () => {
    // 30 days at 10, then 63 days rising 100 → 162. The pick spans exactly those 63 days.
    const spy = curveOf('2026-01-31', [...Array(30).fill(10), ...Array(N).fill(0).map((_, i) => 100 + i)]);
    const pick = curveOf(SHARED, flatThen(N, 0.01));
    expect(spyOverSpan(spy, pick)).toBeCloseTo(162 / 100 - 1, 10);
  });
  it('is null when the benchmark has no snapshot on a boundary date', () => {
    expect(spyOverSpan(curveOf('2026-06-01', flatThen(5, 0.1)), curveOf(SHARED, flatThen(N, 0.01)))).toBeNull();
    expect(spyOverSpan(curveOf(SHARED, flatThen(N, 0.01)), [{ date: SHARED, equity: 1 }])).toBeNull();
  });
});

describe('pickResearch', () => {
  const list = [st('GONE', 'retired'), st('A1'), st('B1')];
  it('defaults to the first active strategy, never to a retired one', () => {
    expect(pickResearch(list, undefined)?.id).toBe('A1');
    expect(pickResearch(list, 'nope')?.id).toBe('A1');
  });
  it('honours an explicit request for a retired strategy: the record stays reachable', () => {
    expect(pickResearch(list, 'GONE')?.id).toBe('GONE');
  });
  it('falls back to the first row when every strategy is retired, and is null when there are none', () => {
    expect(pickResearch([st('GONE', 'retired')], undefined)?.id).toBe('GONE');
    expect(pickResearch([], undefined)).toBeNull();
  });
});

describe('retiredLabel', () => {
  it('names the date it stopped, and degrades before paper_end is written', () => {
    expect(retiredLabel('2026-12-02')).toBe('Retired Dec 2');
    expect(retiredLabel(null)).toBe('Retired');
  });
});

describe('scoreOf', () => {
  const items = (oks: boolean[]) => oks.map(ok => ({ ok }));
  const PASSED = { passed: true, applicable: true };
  const FAILED = { passed: false, applicable: true };
  const NOT_APPLICABLE = { passed: false, applicable: false };
  it('scores out of six and says paper only while the gate has not passed', () => {
    const sc = scoreOf(items([true, true, true, true, true, false]), FAILED);
    expect(sc).toEqual({ passed: 5, total: CHECKS, ready: false, lines: ['Paper only.', 'Backtest gate not passed'] });
    expect(scoreOf([], NO_GATE).lines).toEqual(['Paper only.', 'Backtest gate not passed']);
  });
  it('says paper trading until all six pass when only the gate has passed', () => {
    expect(scoreOf(items([false, false, true, true, true, true]), PASSED).lines).toEqual(['Paper trading until', 'all six pass']);
  });
  it('is ready only when all six pass', () => {
    const sc = scoreOf(items([true, true, true, true, true, true]), PASSED);
    expect(sc.ready).toBe(true);
    expect(sc.lines).toEqual(['All six pass.', 'Ready for real money']);
  });
  it('is never ready with fewer than six items', () => {
    expect(scoreOf(items([true, true, true, true, true]), PASSED).ready).toBe(false);
  });
  it('says real money needs an owner decision when the gate is not applicable (C, handover D9)', () => {
    const sc = scoreOf(items([true, true, true, true, true, false]), NOT_APPLICABLE);
    expect(sc).toEqual({
      passed: 5, total: CHECKS, ready: false,
      lines: ['Paper only. No backtest gate.', 'Real money needs an owner decision'],
    });
  });
  it('is never ready when the gate is not applicable, whatever the items say', () => {
    const sc = scoreOf(items([true, true, true, true, true, true]), NOT_APPLICABLE);
    expect(sc.ready).toBe(false);
    expect(sc.lines[1]).toBe('Real money needs an owner decision');
  });
});

describe('month rows', () => {
  // Phase 10's MonthlyTable shape, oldest first as monthly() returns it.
  const t: MonthlyTable = {
    months: [
      { month: '2026-10', from: '2026-10-05', to: '2026-10-30', return: 0.012, spyReturn: 0.008, trades: 3, worstDrop: 0.021, partial: true },
      { month: '2026-11', from: '2026-10-30', to: '2026-11-30', return: -0.004, spyReturn: null, trades: 0, worstDrop: 0, partial: false },
      { month: '2026-12', from: '2026-11-30', to: '2026-12-02', return: 0, spyReturn: 0.01, trades: 0, worstDrop: 0.005, partial: true },
    ],
    sinceStart: { from: '2026-10-05', to: '2026-12-02', return: 0.008, spyReturn: 0.019, trades: 3, worstDrop: 0.03 },
  };
  it('labels months', () => {
    expect(monthLabel('2026-10')).toBe('Oct 2026');
  });
  it('orders newest first and formats every column', () => {
    const rows = monthLines(t);
    expect(rows.map(r => r.key)).toEqual(['2026-12', '2026-11', '2026-10']);
    expect(rows[1]).toEqual({
      key: '2026-11', label: 'Nov 2026', partial: false,
      ret: { text: '−0.4%', tone: 'neg' }, spy: '—', trades: '0', drop: '0.0%',
    });
    expect(rows[2]).toEqual({
      key: '2026-10', label: 'Oct 2026', partial: true,
      ret: { text: '+1.2%', tone: 'pos' }, spy: '+0.8%', trades: '3', drop: '2.1%',
    });
    expect(rows[0].partial).toBe(true);
  });
  it('builds the since-start row from day 0', () => {
    expect(sinceStartLine(t)).toEqual({
      key: 'since-start', label: 'Since Oct 5', partial: false,
      ret: { text: '+0.8%', tone: 'pos' }, spy: '+1.9%', trades: '3', drop: '3.0%',
    });
  });
  it('has no since-start row before the first paper session', () => {
    expect(sinceStartLine({ months: [], sinceStart: null })).toBeNull();
  });
});
