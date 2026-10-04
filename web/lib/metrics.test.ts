import { describe, expect, it } from 'vitest';
import { checklist, gateItem, strategyMetrics } from './metrics';

const snaps = (vals: number[]) =>
  vals.map((equity, i) => ({ date: new Date(Date.UTC(2026, 6, 1 + i)).toISOString().slice(0, 10), equity }));

const FAILED = { passed: false, applicable: true, note: 'P7a dev window only; failed max DD <= 15% (22.2%)' };
const PASSED = { passed: true, applicable: true, note: null };
const NOT_APPLICABLE = { passed: false, applicable: false, note: 'Backtest gate: not applicable (LLM strategy, design §1 item 5)' };

describe('strategyMetrics', () => {
  it('computes return, win rate, profit factor, drawdown and trade count', () => {
    const m = strategyMetrics(snaps([1000, 1100, 990, 1050]), [30, -10, 20, -10]);
    expect(m.totalReturn).toBeCloseTo(0.05);
    expect(m.winRate).toBeCloseTo(0.5);
    expect(m.profitFactor).toBeCloseTo(2.5);
    expect(m.maxDrawdown).toBeCloseTo(0.1); // 1100 -> 990
    expect(m.trades).toBe(4);
  });
  it('returns nulls with no data', () => {
    const m = strategyMetrics([], []);
    expect(m.totalReturn).toBeNull();
    expect(m.winRate).toBeNull();
    expect(m.profitFactor).toBeNull();
    expect(m.maxDrawdown).toBeNull();
    expect(m.trades).toBe(0);
  });
  it('gives an infinite profit factor when nothing lost', () => {
    expect(strategyMetrics(snaps([1, 2]), [5]).profitFactor).toBe(Infinity);
  });
  it('measures months of forward testing', () => {
    const m = strategyMetrics([{ date: '2026-07-06', equity: 1 }, { date: '2026-10-05', equity: 1 }], []);
    expect(m.months).toBeCloseTo(3.0, 1);
  });
});

describe('checklist', () => {
  const base = { totalReturn: 0.068, winRate: 0.58, profitFactor: 1.42, maxDrawdown: 0.079, trades: 84, months: 3.0 };

  it('keeps the five forward-test rules unchanged', () => {
    const items = checklist(base, 0.046, PASSED);
    expect(items.slice(0, 5).map(i => i.ok)).toEqual([true, false, true, true, true]);
    expect(items[1].val).toBe('84 / 100');
    expect(checklist({ ...base, maxDrawdown: 0.16, trades: 120 }, 0.046, PASSED)[4].ok).toBe(false);
  });

  it('adds the backtest gate as a sixth rule', () => {
    const items = checklist(base, 0.046, FAILED);
    expect(items).toHaveLength(6);
    expect(items[5]).toEqual({ label: 'Backtest gate passed', val: 'Not passed', ok: false, note: FAILED.note });
    expect(checklist(base, 0.046, PASSED)[5]).toEqual({ label: 'Backtest gate passed', val: 'Passed', ok: true });
  });

  it('reads "Not applicable" for C and never counts it as passed (handover D9)', () => {
    const items = checklist(base, 0.046, NOT_APPLICABLE);
    expect(items).toHaveLength(6);
    expect(items[5]).toEqual({ label: 'Backtest gate', val: 'Not applicable', ok: false, note: NOT_APPLICABLE.note });
    // Even every forward metric passing leaves C at five of six.
    const allForward = checklist({ ...base, trades: 120 }, 0.046, NOT_APPLICABLE);
    expect(allForward.filter(i => i.ok)).toHaveLength(5);
    expect(allForward.every(i => i.ok)).toBe(false);
  });

  it('builds the sixth rule on its own', () => {
    expect(gateItem({ passed: false, applicable: false, note: null })).toEqual({ label: 'Backtest gate', val: 'Not applicable', ok: false });
    expect(gateItem(PASSED)).toEqual({ label: 'Backtest gate passed', val: 'Passed', ok: true });
  });

  it('passes only when all six hold', () => {
    expect(checklist({ ...base, trades: 120 }, 0.046, PASSED).every(i => i.ok)).toBe(true);
    // Every forward metric passing does not make a strategy ready while its backtest gate failed.
    const failedGate = checklist({ ...base, trades: 120 }, 0.046, FAILED);
    expect(failedGate.filter(i => i.ok)).toHaveLength(5);
    expect(failedGate.every(i => i.ok)).toBe(false);
  });
});
