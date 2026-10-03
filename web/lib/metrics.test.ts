import { describe, expect, it } from 'vitest';
import { checklist, strategyMetrics } from './metrics';

const snaps = (vals: number[]) =>
  vals.map((equity, i) => ({ date: new Date(Date.UTC(2026, 6, 1 + i)).toISOString().slice(0, 10), equity }));

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
  it('passes only when every go-live rule holds', () => {
    const base = { totalReturn: 0.068, winRate: 0.58, profitFactor: 1.42, maxDrawdown: 0.079, trades: 84, months: 3.0 };
    const items = checklist(base, 0.046);
    expect(items.map(i => i.ok)).toEqual([true, false, true, true, true]);
    expect(items[1].val).toBe('84 / 100');
    expect(checklist({ ...base, trades: 120 }, 0.046).every(i => i.ok)).toBe(true);
    expect(checklist({ ...base, maxDrawdown: 0.16, trades: 120 }, 0.046)[4].ok).toBe(false);
  });
});
