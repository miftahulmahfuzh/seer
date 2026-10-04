import { describe, expect, it } from 'vitest';
import {
  areaPath, clamp, colorAt, dateNum, extent, fmtMultiple, fmtNumber, fmtPct, fmtSignedPct, isNum, linePath,
  linear, niceDomain, niceStep, niceTicks, resolveAxis, spread, stepPoints, textWidth, ticksWithin, truncate,
  yearTicks,
} from './scale';

describe('linear', () => {
  it('maps the domain onto the range, inverted ranges included', () => {
    const f = linear([0, 10], [100, 0]);
    expect(f(0)).toBe(100);
    expect(f(5)).toBe(50);
    expect(f(10)).toBe(0);
  });
  it('maps a zero-width domain to the middle of the range', () => {
    expect(linear([3, 3], [0, 100])(3)).toBe(50);
  });
});

describe('clamp and isNum', () => {
  it('clamps whichever order the bounds come in', () => {
    expect(clamp(5, 0, 3)).toBe(3);
    expect(clamp(5, 3, 0)).toBe(3);
    expect(clamp(-1, 0, 3)).toBe(0);
  });
  it('accepts finite numbers only', () => {
    expect(isNum(0)).toBe(true);
    expect(isNum(null)).toBe(false);
    expect(isNum(undefined)).toBe(false);
    expect(isNum(NaN)).toBe(false);
    expect(isNum(Infinity)).toBe(false);
  });
});

describe('extent', () => {
  it('ignores null and non-finite values and honours include', () => {
    expect(extent([3, null, -1, NaN, Infinity, 2])).toEqual([-1, 3]);
    expect(extent([0.1, 0.2], [0])).toEqual([0, 0.2]);
  });
  it('pads a single value and defaults an empty set', () => {
    expect(extent([5])).toEqual([4.5, 5.5]);
    expect(extent([0])).toEqual([-1, 1]);
    expect(extent([])).toEqual([0, 1]);
  });
});

describe('nice ticks', () => {
  it('picks 1, 2, 2.5 or 5 steps', () => {
    expect(niceStep(1, 5)).toBeCloseTo(0.2);
    expect(niceStep(23, 5)).toBe(5);
    expect(niceStep(0.49, 5)).toBeCloseTo(0.1);
    expect(niceStep(0, 5)).toBe(1);
  });
  it('covers the range with clean values', () => {
    expect(niceTicks(0, 1, 5)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1]);
    expect(niceTicks(-0.37, 0.12, 5)).toEqual([-0.4, -0.3, -0.2, -0.1, 0, 0.1, 0.2]);
    expect(niceTicks(5, 5)).toEqual([5]);
    expect(niceTicks(NaN, 1)).toEqual([]);
  });
  it('keeps a given domain or widens to the ticks', () => {
    expect(ticksWithin([0.05, 0.95], 5)).toEqual([0.2, 0.4, 0.6, 0.8]);
    expect(niceDomain(0.03, 0.97)).toEqual([0, 1]);
  });
});

describe('resolveAxis', () => {
  const pct = fmtPct(0);
  it('widens the raw extent to nice ticks and labels them', () => {
    const a = resolveAxis([0.03, 0.97], { format: pct, count: 5 });
    expect(a.domain).toEqual([0, 1]);
    expect(a.ticks.map(t => t.label)).toEqual(['0%', '20%', '40%', '60%', '80%', '100%']);
  });
  it('keeps a given domain', () => {
    const a = resolveAxis([0, 1], { domain: [0.05, 0.95], format: pct, count: 5 });
    expect(a.domain).toEqual([0.05, 0.95]);
    expect(a.ticks.map(t => t.value)).toEqual([0.2, 0.4, 0.6, 0.8]);
  });
  it('takes explicit ticks as they are', () => {
    const a = resolveAxis([0.1, 0.9], { ticks: [{ value: 0, label: 'none' }, { value: 1, label: 'all' }], format: pct, count: 5 });
    expect(a.domain).toEqual([0, 1]);
    expect(a.ticks.map(t => t.label)).toEqual(['none', 'all']);
  });
});

describe('dates', () => {
  it('reads ISO dates as UTC', () => {
    expect(dateNum('2000-01-01')).toBe(Date.UTC(2000, 0, 1));
  });
  it('marks years every 2 across the dev window', () => {
    const t = yearTicks(dateNum('1993-01-29'), dateNum('2015-10-16'));
    expect(t.length).toBe(11);
    expect(t[0]).toEqual({ value: Date.UTC(1994, 0, 1), label: '1994' });
    expect(t[t.length - 1].label).toBe('2014');
  });
  it('marks every year when they fit', () => {
    expect(yearTicks(dateNum('2015-10-19'), dateNum('2026-10-02')).map(t => t.label)).toEqual(
      ['2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026'],
    );
  });
  it('labels the two ends of a short window', () => {
    expect(yearTicks(dateNum('2015-10-19'), dateNum('2016-03-31')).map(t => t.label)).toEqual(['Oct 2015', 'Mar 2016']);
    expect(yearTicks(5, 5)).toEqual([]);
  });
});

describe('paths', () => {
  it('rounds to 0.1 and lifts the pen at nulls', () => {
    expect(linePath([[0, 0], [10.04, 5.26]])).toBe('M0 0L10 5.3');
    expect(linePath([[0, 0], null, [5, 5], [6, 6]])).toBe('M0 0M5 5L6 6');
    expect(linePath([])).toBe('');
  });
  it('closes areas down to the baseline per unbroken run', () => {
    expect(areaPath([[0, 5], [10, 2]], 10)).toBe('M0 10L0 5L10 2L10 10Z');
    expect(areaPath([[0, 5]], 10)).toBe('');
    expect(areaPath([[0, 5], [1, 4], null, [3, 3], [4, 2]], 10)).toBe('M0 10L0 5L1 4L1 10ZM3 10L3 3L4 2L4 10Z');
  });
  it('holds values flat until the next x for step lines', () => {
    expect(stepPoints([[0, 1], [2, 3]])).toEqual([[0, 1], [2, 1], [2, 3]]);
    expect(stepPoints([[0, 1], null, [2, 3]])).toEqual([[0, 1], null, [2, 3]]);
  });
});

describe('label layout', () => {
  it('spreads close labels apart, keeping input order', () => {
    expect(spread([10, 12, 50], 8)).toEqual([10, 18, 50]);
    expect(spread([100, 98], 8, 0, 100)).toEqual([100, 92]);
  });
  it('estimates width and truncates', () => {
    expect(textWidth('abcd', 10)).toBeCloseTo(22.4);
    expect(truncate('abcdef', 4)).toBe('abc…');
    expect(truncate('abc', 4)).toBe('abc');
  });
  it('cycles the series colours', () => {
    expect(colorAt(0)).toBe('var(--ink)');
    expect(colorAt(6)).toBe('var(--ink)');
    expect(colorAt(1)).toBe('var(--line-b)');
  });
});

describe('formatters', () => {
  it('formats percents with a true minus and no negative zero', () => {
    expect(fmtPct(0)(-0.153)).toBe('−15%');
    expect(fmtPct(0)(-0.001)).toBe('0%');
    expect(fmtSignedPct(1)(0.0123)).toBe('+1.2%');
    expect(fmtSignedPct(1)(0)).toBe('0.0%');
  });
  it('formats numbers and multiples', () => {
    expect(fmtNumber(0)(-3)).toBe('−3');
    expect(fmtNumber(2)(1.234)).toBe('1.23');
    expect(fmtMultiple(1)(2.5)).toBe('2.5×');
  });
});
