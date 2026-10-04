import { describe, expect, it } from 'vitest';
import type { MonthlyTable } from '../../../lib/monthly';
import {
  bestResearch, CHECKS, looks, monthLabel, monthLines, monthsBg, NO_GATE, researchOf, scoreOf, sinceStartLine,
  type RosterIn,
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
    expect(looks(roster).get('SPY')).toEqual({ bg: 'bg-sheet', line: 'var(--ink-3)', width: 1.75, dotted: true });
  });
  it('assigns research sheets and lines in roster order', () => {
    const l = looks(roster);
    expect(RESEARCH.map(id => l.get(id)!.bg)).toEqual(['bg-lav', 'bg-sky', 'bg-stone', 'bg-butter']);
    expect(RESEARCH.map(id => l.get(id)!.line)).toEqual(['var(--ink)', 'var(--line-b)', 'var(--line-c)', 'var(--coral)']);
    expect(RESEARCH.map(id => l.get(id)!.width)).toEqual([2, 2, 2, 2]);
  });
  it('never gives C the look of A', () => {
    const l = looks(roster);
    expect(l.get('C')).not.toEqual(l.get('A'));
    expect(l.get('C')).toEqual({ bg: 'bg-butter', line: 'var(--coral)', width: 2, dotted: false });
  });
  it('follows roster order, not ids', () => {
    const l = looks([roster[3], roster[0], roster[1]]);
    expect(l.get('F1-SPY-SMA200-M')).toEqual({ bg: 'bg-lav', line: 'var(--ink)', width: 2, dotted: false });
    expect(l.get('A')).toEqual({ bg: 'bg-sky', line: 'var(--line-b)', width: 2, dotted: false });
  });
  it('cycles sheets and uses the spare line for a fifth research strategy', () => {
    const l = looks([...roster, { id: 'X9', isChampion: false, isBenchmark: false }]);
    expect(l.get('X9')).toEqual({ bg: 'bg-lav', line: 'var(--ink-2)', width: 2, dotted: false });
  });
  it('emphasises a non-benchmark champion', () => {
    const l = looks([{ ...roster[0], isChampion: false }, { ...roster[1], isChampion: true }]);
    expect(l.get('A')!.width).toBe(2.75);
  });
});

describe('monthsBg', () => {
  it('keeps the card sheet, except butter, which would merge into the butter checklist above it', () => {
    const l = looks(roster);
    expect(monthsBg(l.get('A')!)).toBe('bg-lav');
    expect(monthsBg(l.get('F4-MOM12-N20-TREND')!)).toBe('bg-sky');
    expect(monthsBg(l.get('C')!)).toBe('bg-stone');
  });
});

describe('researchOf', () => {
  it('lists research strategies only', () => {
    expect(researchOf(roster).map(s => s.id)).toEqual(RESEARCH);
  });
});

describe('bestResearch', () => {
  const row = (i: number, totalReturn: number | null) => ({ strategy: roster[i], metrics: { totalReturn } });
  it('ignores the benchmark and strategies without a return', () => {
    const b = bestResearch([row(0, 0.05), row(1, -0.01), row(2, 0.02), row(3, null), row(4, 0.01)]);
    expect(b?.strategy.id).toBe('F4-MOM12-N20-TREND');
    expect(b?.ret).toBeCloseTo(0.02);
  });
  it('is null before any paper result', () => {
    expect(bestResearch([row(0, 0.01), row(1, null)])).toBeNull();
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
