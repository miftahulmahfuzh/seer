import { describe, expect, it } from 'vitest';
import { asText, cents, fixed, parseReceiptDate, parseShares, parseUsd, parseUsdParts, roundHalfUp } from './money';

describe('roundHalfUp', () => {
  it('rounds ties away from zero, like Python ROUND_HALF_UP', () => {
    expect(roundHalfUp(26.125, 2)).toBe(26.13);
    expect(roundHalfUp(-26.125, 2)).toBe(-26.13);
    expect(roundHalfUp(0.005, 2)).toBe(0.01);
    expect(roundHalfUp(1.0049, 2)).toBe(1);
  });
  it('ignores binary noise that would turn a tie into a round-down', () => {
    expect(Math.round(1.005 * 100) / 100).toBe(1); // the naive way rounds this tie down
    expect(cents(1.005)).toBe(1.01);
    expect(cents(24.13 + 1.995)).toBe(26.13);
  });
  it('never returns negative zero', () => {
    expect(Object.is(roundHalfUp(-0.0001, 2), 0)).toBe(true);
  });
  it('keeps nine decimals for shares', () => {
    expect(roundHalfUp(0.0262246144, 9)).toBe(0.026224614);
    expect(roundHalfUp(0.0262246145, 9)).toBe(0.026224615);
  });
  it('prints fixed decimals', () => {
    expect(fixed(26.125, 2)).toBe('26.13');
    expect(fixed(1.5, 9)).toBe('1.500000000');
    expect(fixed(0, 2)).toBe('0.00');
  });
});

describe('asText', () => {
  it('trims, collapses spaces, and accepts finite numbers', () => {
    expect(asText('  Market   Buy ')).toBe('Market Buy');
    expect(asText(5.38)).toBe('5.38');
    expect(asText('')).toBeNull();
    expect(asText(Number.NaN)).toBeNull();
    expect(asText(null)).toBeNull();
    expect(asText({})).toBeNull();
  });
});

describe('parseUsd', () => {
  it('reads every money format the receipts print', () => {
    expect(parseUsd('$1,063.886')).toBe(1063.886);
    expect(parseUsd('$1,832.90')).toBe(1832.9);
    expect(parseUsd('$27.90')).toBe(27.9);
    expect(parseUsd('+$0.10')).toBe(0.1);
    expect(parseUsd('-$0.15')).toBe(-0.15);
    expect(parseUsd('−$0.15')).toBe(-0.15);
    expect(parseUsd('$-0.15')).toBe(-0.15);
    expect(parseUsd('+$0.00')).toBe(0);
    expect(parseUsd('$ 72.27')).toBe(72.27);
    expect(parseUsd('US$5')).toBe(5);
    expect(parseUsd('72.27')).toBe(72.27);
    expect(parseUsd(72.27)).toBe(72.27);
  });
  it('keeps the printed sign apart from the size', () => {
    expect(parseUsdParts('+$0.10')).toEqual({ sign: '+', magnitude: 0.1 });
    expect(parseUsdParts('-$0.15')).toEqual({ sign: '-', magnitude: 0.15 });
    expect(parseUsdParts('$22.31')).toEqual({ sign: null, magnitude: 22.31 });
  });
  it('refuses what is not money', () => {
    for (const bad of ['', 'Filled', '$', '$1,06.88', '+-$1', '-$-1', '1.2.3', '$12a', 'Rp 10.000']) {
      expect(parseUsd(bad), bad).toBeNull();
    }
    expect(parseUsd(null)).toBeNull();
    expect(parseUsd(undefined)).toBeNull();
  });
});

describe('parseShares', () => {
  it('reads share counts with up to nine decimals', () => {
    expect(parseShares('0.026224614')).toBe(0.026224614);
    expect(parseShares('7.084773035')).toBe(7.084773035);
    expect(parseShares('3')).toBe(3);
    expect(parseShares('1,000.5')).toBe(1000.5);
    expect(parseShares(5.38)).toBe(5.38);
  });
  it('reads a partial-fill line as printed', () => {
    expect(parseShares('· 0.38 shares')).toBe(0.38);
    expect(parseShares('5 shares')).toBe(5);
    expect(parseShares('1 share')).toBe(1);
  });
  it('refuses a tenth decimal, signs and words', () => {
    for (const bad of ['0.0262246141', '-1', '+1', 'five', '', '1e-7', '$5']) {
      expect(parseShares(bad), bad).toBeNull();
    }
  });
});

describe('parseReceiptDate', () => {
  it('turns the printed date and WIB time into one ISO timestamp', () => {
    expect(parseReceiptDate('October 07, 2026', '21:55 WIB')).toBe('2026-10-07T21:55:00+07:00');
    expect(parseReceiptDate('June 10, 2025', '21:34 WIB')).toBe('2025-06-10T21:34:00+07:00');
  });
  it('accepts abbreviated months, a missing comma or WIB, and dotted times', () => {
    expect(parseReceiptDate('Oct 7 2026', '21:55')).toBe('2026-10-07T21:55:00+07:00');
    expect(parseReceiptDate('Sept 1, 2026', '09.05 WIB')).toBe('2026-09-01T09:05:00+07:00');
  });
  it('converts a 12-hour time', () => {
    expect(parseReceiptDate('March 25, 2026', '8:30 PM')).toBe('2026-03-25T20:30:00+07:00');
    expect(parseReceiptDate('March 25, 2026', '12:15 AM')).toBe('2026-03-25T00:15:00+07:00');
    expect(parseReceiptDate('March 25, 2026', '12:15 PM')).toBe('2026-03-25T12:15:00+07:00');
  });
  it('refuses impossible dates, other time zones and junk', () => {
    expect(parseReceiptDate('February 30, 2026', '21:55 WIB')).toBeNull();
    expect(parseReceiptDate('October 07, 2026', '25:00 WIB')).toBeNull();
    expect(parseReceiptDate('October 07, 2026', '21:55 ET')).toBeNull();
    expect(parseReceiptDate('October 07, 2026', '21:55 PM')).toBeNull();
    expect(parseReceiptDate('Oc 07, 2026', '21:55 WIB')).toBeNull();
    expect(parseReceiptDate('2026-10-07', '21:55 WIB')).toBeNull();
    expect(parseReceiptDate(null, '21:55 WIB')).toBeNull();
    expect(parseReceiptDate('October 07, 2026', null)).toBeNull();
  });
});
