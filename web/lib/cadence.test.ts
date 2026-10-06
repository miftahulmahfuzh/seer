import { describe, expect, it } from 'vitest';
import {
  heldUsd, orderSizeChange, picksMonthlySizesWeekly, RESIZE_BAND, sizeChange, sizeLabel, sizeTip, SPLIT_CADENCE_RULES,
} from './cadence';

describe('picksMonthlySizesWeekly', () => {
  it('knows the three split-cadence rule sets', () => {
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-tbill')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-frac')).toBe(true);
    expect(SPLIT_CADENCE_RULES).toHaveLength(3);
  });
  it('is false for every other rule set and for none', () => {
    for (const id of ['monthly-hold', 'monthly-hold-frac', 'monthly-hold-tbill', 'weekly-hold', 'daily-switch', 'design-v0', '']) {
      expect(picksMonthlySizesWeekly(id)).toBe(false);
    }
    expect(picksMonthlySizesWeekly(null)).toBe(false);
    expect(picksMonthlySizesWeekly(undefined)).toBe(false);
  });
});

describe('sizeChange', () => {
  it('mirrors the engine band of 1% of equity', () => {
    expect(RESIZE_BAND).toBe(0.01);
  });
  it('reads a symbol not held as a buy of the full amount', () => {
    expect(sizeChange(0.2, 500, null)).toEqual({ action: 'buy', usd: 100 });
    // The band gates resizes only: a small new buy is still a buy.
    expect(sizeChange(0.005, 500, null)).toEqual({ action: 'buy', usd: 2.5 });
  });
  it('adds when the holding is below its target by at least the band', () => {
    expect(sizeChange(0.1, 1000, 80)).toEqual({ action: 'add', usd: 20 });
  });
  it('trims when the holding is above its target by at least the band', () => {
    expect(sizeChange(0.1, 1000, 130)).toEqual({ action: 'trim', usd: 30 });
  });
  it('trades at exactly the band and not under it (the engine skips only a strictly smaller gap)', () => {
    expect(sizeChange(0.1, 1000, 90)).toEqual({ action: 'add', usd: 10 });
    expect(sizeChange(0.1, 1000, 91)).toEqual({ action: 'none', usd: 0 });
    expect(sizeChange(0.1, 1000, 109)).toEqual({ action: 'none', usd: 0 });
    expect(sizeChange(0.1, 1000, 110)).toEqual({ action: 'trim', usd: 10 });
  });
  it('treats the idle instrument like any other symbol', () => {
    const held = heldUsd([{ symbol: 'BIL', value: 300 }]);
    expect(orderSizeChange(0.5, 1000, 'BIL', held)).toEqual({ action: 'add', usd: 200 });
  });
});

describe('heldUsd and orderSizeChange', () => {
  it('maps each symbol to its dollar value held now', () => {
    const held = heldUsd([{ symbol: 'AAPL', value: 120.5 }, { symbol: 'MSFT', value: 80 }, { symbol: 'AAPL', value: 0.5 }]);
    expect(held.get('AAPL')).toBe(121);
    expect(held.get('MSFT')).toBe(80);
    expect(held.has('NVDA')).toBe(false);
  });
  it('is null when the weight or the equity is unknown', () => {
    const held = heldUsd([]);
    expect(orderSizeChange(null, 1000, 'AAPL', held)).toBeNull();
    expect(orderSizeChange(0.1, null, 'AAPL', held)).toBeNull();
  });
  it('buys a symbol that is not held', () => {
    expect(orderSizeChange(0.25, 558, 'NVDA', heldUsd([{ symbol: 'AAPL', value: 100 }]))).toEqual({ action: 'buy', usd: 139.5 });
  });
});

describe('sizeLabel and sizeTip', () => {
  it('says it in plain words with dollars to the cent', () => {
    expect(sizeLabel({ action: 'buy', usd: 40 })).toBe('Buy about $40.00');
    expect(sizeLabel({ action: 'add', usd: 6.123 })).toBe('Add about $6.12');
    expect(sizeLabel({ action: 'trim', usd: 9.8 })).toBe('Trim about $9.80');
    expect(sizeLabel({ action: 'none', usd: 0 })).toBe('No change');
  });
  it('has a tooltip for every action', () => {
    for (const action of ['buy', 'add', 'trim', 'none'] as const) {
      expect(sizeTip({ action, usd: 1 }).length).toBeGreaterThan(0);
    }
    expect(sizeTip({ action: 'none', usd: 0 })).toContain('1%');
  });
});
