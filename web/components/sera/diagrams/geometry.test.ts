import { describe, expect, it } from 'vitest';
import { monthYear, rowBoxes, timeScale, yearTicks } from './geometry';

describe('rowBoxes', () => {
  it('fills the width exactly with equal weights', () => {
    const b = rowBoxes([1, 1, 1, 1, 1, 1, 1], 1240, 26, 8, 228);
    expect(b).toHaveLength(7);
    expect(b[0].x).toBe(0);
    expect(b[6].x + b[6].w).toBeCloseTo(1240, 6);
    expect(b[1].x - (b[0].x + b[0].w)).toBeCloseTo(26, 6);
    expect(b.every(x => x.y === 8 && x.h === 228)).toBe(true);
  });
  it('sizes boxes by weight', () => {
    const b = rowBoxes([1, 2, 1], 400, 0, 0, 10);
    expect(b.map(x => x.w)).toEqual([100, 200, 100]);
    expect(b.map(x => x.x)).toEqual([0, 100, 300]);
  });
  it('returns nothing for no stages', () => {
    expect(rowBoxes([], 100, 10, 0, 10)).toEqual([]);
  });
});

describe('timeScale', () => {
  const x = timeScale('2000-01-01', '2010-01-01', 0, 100);
  it('maps the ends and the middle', () => {
    expect(x('2000-01-01')).toBe(0);
    expect(x('2010-01-01')).toBe(100);
    expect(x('2005-01-01')).toBeCloseTo(50, 0);
  });
  it('accepts timestamps and clamps outside dates', () => {
    expect(x('2010-01-01T14:12:19+00:00')).toBe(100);
    expect(x('1990-06-30')).toBe(0);
    expect(x('2030-06-30')).toBe(100);
  });
  it('never divides by zero', () => {
    expect(Number.isFinite(timeScale('2000-01-01', '2000-01-01', 0, 10)('2000-01-01'))).toBe(true);
  });
});

describe('yearTicks', () => {
  it('lists the round years after the start year', () => {
    expect(yearTicks('1993-01-29', '2026-10-04', 5)).toEqual([1995, 2000, 2005, 2010, 2015, 2020, 2025]);
    expect(yearTicks('1995-01-03', '2001-01-01', 5)).toEqual([2000]);
  });
});

describe('monthYear', () => {
  it('formats in UTC', () => {
    expect(monthYear('2015-10-16')).toBe('Oct 2015');
    expect(monthYear('1993-01-29T00:00:00+00:00')).toBe('Jan 1993');
  });
});
