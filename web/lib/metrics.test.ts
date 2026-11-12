import { describe, expect, it } from 'vitest';
import { checklist, CHECKLIST_RULES, gateItem, strategyMetrics, withoutDeposits } from './metrics';

const snaps = (vals: number[]) =>
  vals.map((equity, i) => ({ date: new Date(Date.UTC(2026, 6, 1 + i)).toISOString().slice(0, 10), equity }));

const FAILED = { passed: false, applicable: true };
const PASSED = { passed: true, applicable: true };
const NOT_APPLICABLE = { passed: false, applicable: false };
const TWIN = { passed: false, applicable: false, twin: true as const };

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

describe('withoutDeposits', () => {
  it("takes a deposit out of the session it landed in, so it is never a return", () => {
    // 1000 -> 990 (-1%), then 275 lands and the book also gains 1%: 990 * 1.01 + 275 = 1274.9.
    const raw = snaps([1000, 990, 1274.9, 1287.649]);
    const clean = withoutDeposits(raw, new Map([[raw[2].date, 275]]));
    expect(clean.map(s => s.date)).toEqual(raw.map(s => s.date));
    expect(clean[0].equity).toBe(1000);
    expect(clean[2].equity).toBeCloseTo(999.9);   // 1000 * 0.99 * 1.01
    expect(clean[3].equity).toBeCloseTo(1009.899); // then +1% more
    expect(strategyMetrics(clean, []).totalReturn).toBeCloseTo(0.009899);
    expect(strategyMetrics(raw, []).totalReturn).toBeCloseTo(0.287649); // what the card used to say
  });
  it('counts a deposit on the opening snapshot as opening money', () => {
    const raw = snaps([1275, 1287.75]);
    expect(withoutDeposits(raw, new Map([[raw[0].date, 275]]))[1].equity).toBeCloseTo(1287.75);
  });
  it('returns the curve unchanged with no deposits', () => {
    const raw = snaps([1, 2, 3]);
    expect(withoutDeposits(raw, new Map())).toBe(raw);
  });
  it('keeps a deposit from hiding a drawdown', () => {
    // -10%, then a deposit lifts the balance past its old peak while the book gains nothing.
    const raw = snaps([1000, 900, 1175]);
    const clean = withoutDeposits(raw, new Map([[raw[2].date, 275]]));
    expect(strategyMetrics(clean, []).maxDrawdown).toBeCloseTo(0.1);
    expect(strategyMetrics(clean, []).totalReturn).toBeCloseTo(-0.1);
  });
});

describe('checklist', () => {
  const base = { totalReturn: 0.068, winRate: 0.58, profitFactor: 1.42, maxDrawdown: 0.079, trades: 84, months: 3.0 };

  // The coupling that did not exist on 2026-10-07. Design §13 shortened this list from six rows to
  // five and nothing in TypeScript failed, so `leaderboard/view.ts`'s `CHECKS = 6` went on scoring
  // five rendered rows out of six with "Ready for real money" unreachable. This is the test that
  // would have caught that: the count and the list it counts can no longer drift apart in silence.
  it('returns exactly CHECKLIST_RULES rows, whatever the gate says', () => {
    expect(checklist(base, 0.046, PASSED)).toHaveLength(CHECKLIST_RULES);
    expect(checklist(base, 0.046, FAILED)).toHaveLength(CHECKLIST_RULES);
    expect(checklist(base, 0.046, NOT_APPLICABLE)).toHaveLength(CHECKLIST_RULES);
  });

  // `base` is 3 months, which no longer passes item 1: design §13 (2026-10-07) raised it to 18
  // and DELETED the trades clause, so `trades` can no longer make or break any row here.
  it('keeps the four forward-test rules unchanged', () => {
    const items = checklist(base, 0.046, PASSED);
    expect(items.slice(0, 4).map(i => i.ok)).toEqual([false, true, true, true]);
    expect(items[0].label).toBe('≥ 18 months forward');
    expect(items[0].val).toBe('3.0 mo');
    // 0.26 and not 0.21: the owner raised the real-money bar 20% -> 25% on 2026-10-14
    // (design §18), so a 21% fall now PASSES go-live condition 4.
    expect(checklist({ ...base, maxDrawdown: 0.26, months: 18 }, 0.046, PASSED)[3].ok).toBe(false);
  });

  it('counts no trades at all, whatever the trade count is', () => {
    const many = checklist({ ...base, months: 18, trades: 5000 }, 0.046, PASSED);
    const few = checklist({ ...base, months: 18, trades: 1 }, 0.046, PASSED);
    expect(many).toEqual(few);
    expect(many.every(i => i.ok)).toBe(true);
    expect(many.some(i => i.label.includes('trades'))).toBe(false);
  });

  it('adds the backtest gate as a fifth rule', () => {
    const items = checklist(base, 0.046, FAILED);
    expect(items).toHaveLength(5);
    expect(items[4]).toEqual({ label: 'Backtest gate passed', val: 'Not passed', ok: false });
    expect(checklist(base, 0.046, PASSED)[4]).toEqual({ label: 'Backtest gate passed', val: 'Passed', ok: true });
  });

  it('reads "Not applicable" for C and never counts it as passed (handover D9)', () => {
    const items = checklist(base, 0.046, NOT_APPLICABLE);
    expect(items).toHaveLength(5);
    expect(items[4]).toEqual({ label: 'Backtest gate', val: 'Not applicable', ok: false });
    // Even every forward metric passing leaves C at four of five.
    const allForward = checklist({ ...base, months: 18 }, 0.046, NOT_APPLICABLE);
    expect(allForward.filter(i => i.ok)).toHaveLength(4);
    expect(allForward.every(i => i.ok)).toBe(false);
  });

  it('builds the fifth rule on its own', () => {
    expect(gateItem({ passed: false, applicable: false })).toEqual({ label: 'Backtest gate', val: 'Not applicable', ok: false });
    expect(gateItem(PASSED)).toEqual({ label: 'Backtest gate passed', val: 'Passed', ok: true });
  });
  it("reads \"Can't be run\" for a Claude twin and never counts it as passed", () => {
    expect(gateItem(TWIN)).toEqual({ label: 'Backtest gate', val: "Can't be run", ok: false });
    const items = checklist({ ...base, months: 18 }, 0.046, TWIN);
    expect(items).toHaveLength(CHECKLIST_RULES);
    expect(items[4]).toEqual({ label: 'Backtest gate', val: "Can't be run", ok: false });
    expect(items.filter(i => i.ok)).toHaveLength(4);
  });
  it('even a twin gate that claims a pass is not a pass', () => {
    expect(gateItem({ passed: true, applicable: true, twin: true }).ok).toBe(false);
  });

  // A checklist item is a verdict and nothing else (owner, 2026-10-07). `gateItem` used to hang the
  // roster's prose off the failing row, which is how it reached the leaderboard sheet at all.
  it('carries no prose on any item: a failed gate explains itself on the Sera method page', () => {
    for (const gate of [PASSED, FAILED, NOT_APPLICABLE, TWIN]) {
      for (const item of checklist({ ...base, months: 18 }, 0.046, gate)) {
        expect(Object.keys(item).sort()).toEqual(['label', 'ok', 'val']);
      }
    }
  });

  it('passes only when all five hold', () => {
    expect(checklist({ ...base, months: 18 }, 0.046, PASSED).every(i => i.ok)).toBe(true);
    // Every forward metric passing does not make a strategy ready while its backtest gate failed.
    const failedGate = checklist({ ...base, months: 18 }, 0.046, FAILED);
    expect(failedGate.filter(i => i.ok)).toHaveLength(4);
    expect(failedGate.every(i => i.ok)).toBe(false);
  });
});
