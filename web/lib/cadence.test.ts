import { describe, expect, it } from 'vitest';
import {
  cadenceOf, heldUsd, orderSizeChange, picksMonthlySizesWeekly, RESIZE_BAND, resizeBasisOf, sellsWhen,
  sizeChange, sizeLabel, sizeTip, SPLIT_CADENCE_RULES, TARGET_BAND_RULES, TARGET_RESIZE_BAND,
} from './cadence';

describe('picksMonthlySizesWeekly', () => {
  it('knows the four split-cadence rule sets', () => {
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-tbill')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-frac')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-frac-gotrade')).toBe(true);
    expect(SPLIT_CADENCE_RULES).toHaveLength(4);
  });
  it('is false for every other rule set and for none', () => {
    for (const id of ['monthly-hold', 'monthly-hold-frac', 'monthly-hold-frac-gotrade', 'monthly-hold-tbill', 'weekly-hold', 'daily-switch', 'design-v0', '']) {
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

describe('cadenceOf: when a rule set can act at all', () => {
  // Every preset in engine/src/seer_engine/sim/rules.py PRESETS, by its own cadence and
  // resize_cadence. A preset missing here answers 'unknown', which every caller reads as
  // "say nothing specific" -- so a new engine preset degrades, it does not lie.
  it('mirrors the engine presets', () => {
    for (const id of ['design-v0', 'design-v0-gotrade', 'daily-switch', 'daily-switch-tbill',
      'swing-t10', 'swing-t20', 'swing-t20-open']) {
      expect(cadenceOf(id)).toBe('daily');
    }
    expect(cadenceOf('weekly-hold')).toBe('weekly');
    for (const id of ['monthly-hold', 'monthly-hold-tbill', 'monthly-hold-frac', 'monthly-hold-frac-gotrade']) {
      expect(cadenceOf(id)).toBe('monthly');
    }
    for (const id of SPLIT_CADENCE_RULES) expect(cadenceOf(id)).toBe('monthly-weekly');
  });

  it('is unknown for the benchmark and for a preset it has not been taught', () => {
    expect(cadenceOf(null)).toBe('unknown');
    expect(cadenceOf(undefined)).toBe('unknown');
    expect(cadenceOf('')).toBe('unknown');
    expect(cadenceOf('not-a-preset')).toBe('unknown');
  });

  it('agrees with picksMonthlySizesWeekly, which answers the narrower question', () => {
    for (const id of ['monthly-hold', 'design-v0-gotrade', 'weekly-hold', ...SPLIT_CADENCE_RULES]) {
      expect(picksMonthlySizesWeekly(id)).toBe(cadenceOf(id) === 'monthly-weekly');
    }
  });
});

describe('sellsWhen', () => {
  it('never names a date -- the NYSE calendar is the engine\'s, not the web app\'s', () => {
    for (const c of ['daily', 'weekly', 'monthly', 'monthly-weekly'] as const) {
      expect(sellsWhen(c)).not.toMatch(/\d/);
    }
  });
  it('says nothing at all for a cadence it does not know', () => {
    expect(sellsWhen('unknown')).toBeNull();
  });
});

describe('the target-basis band', () => {
  it('mirrors the engine: a fifth of the holding target, for the fixed-tape rule sets only', () => {
    expect(TARGET_RESIZE_BAND).toBe(0.2);
    expect([...TARGET_BAND_RULES]).toEqual([
      'monthly-hold-frac-gotrade-tband',
      'monthly-hold-frac-gotrade-tband-cash',
      'weekly-hold-frac-gotrade-tband-cash',
    ]);
    for (const id of TARGET_BAND_RULES) expect(resizeBasisOf(id)).toBe('target');
    for (const id of ['monthly-hold-frac-gotrade', 'weekly-hold', 'design-v0', '']) {
      expect(resizeBasisOf(id)).toBe('equity');
    }
    expect(resizeBasisOf(null)).toBe('equity');
    expect(resizeBasisOf(undefined)).toBe('equity');
  });
  it('measures the gap against the target, trading at exactly the band and not under it', () => {
    // target 0.1 × 1000 = 100, so the band is 20 (the equity band would be 10)
    expect(sizeChange(0.1, 1000, 80, 'target')).toEqual({ action: 'add', usd: 20 });
    expect(sizeChange(0.1, 1000, 81, 'target')).toEqual({ action: 'none', usd: 0 });
    expect(sizeChange(0.1, 1000, 119, 'target')).toEqual({ action: 'none', usd: 0 });
    expect(sizeChange(0.1, 1000, 120, 'target')).toEqual({ action: 'trim', usd: 20 });
  });
  it('leaves alone a gap the equity band would trade', () => {
    expect(sizeChange(0.1, 1000, 85)).toEqual({ action: 'add', usd: 15 });
    expect(sizeChange(0.1, 1000, 85, 'target')).toEqual({ action: 'none', usd: 0 });
  });
  it('still buys a symbol that is not held, whatever the basis', () => {
    expect(sizeChange(0.005, 500, null, 'target')).toEqual({ action: 'buy', usd: 2.5 });
    expect(orderSizeChange(0.1, 1000, 'AAPL', heldUsd([{ symbol: 'AAPL', value: 85 }]), 'target'))
      .toEqual({ action: 'none', usd: 0 });
  });
  it('says which band in the tooltip', () => {
    expect(sizeTip({ action: 'none', usd: 0 }, 'target')).toContain('20%');
    expect(sizeTip({ action: 'none', usd: 0 }, 'target')).not.toContain('equity');
    expect(sizeTip({ action: 'none', usd: 0 }, 'equity')).toContain('1%');
  });
  it('knows the cadence of the fixed-tape rule sets', () => {
    expect(cadenceOf('monthly-hold-frac-gotrade-tband')).toBe('monthly');
    expect(cadenceOf('monthly-hold-frac-gotrade-tband-cash')).toBe('monthly');
    expect(cadenceOf('weekly-hold-frac-gotrade-tband-cash')).toBe('weekly');
    for (const id of TARGET_BAND_RULES) expect(picksMonthlySizesWeekly(id)).toBe(false);
  });
});
