import { describe, expect, it } from 'vitest';
import { companyName, money, pct, rp, shortDate, signedPct, signedRp, signedUsd, usd } from './format';

describe('format', () => {
  it('formats USD like the Gotrade ticket', () => {
    expect(usd(271.4)).toBe('$271.40');
    expect(money(271.4)).toBe('271.40');
    expect(signedUsd(5.2)).toBe('+$5.20');
    expect(signedUsd(-2.1)).toBe('−$2.10');
  });
  it('formats IDR rounded to the thousand with Indonesian grouping', () => {
    expect(rp(2.1, 16530)).toBe('Rp 35.000');
    expect(signedRp(-2.1, 16530)).toBe('−Rp 35.000');
    expect(signedRp(7.5, 16530)).toBe('+Rp 124.000');
  });
  it('formats percentages', () => {
    expect(signedPct(0.0213)).toBe('+2.13%');
    expect(signedPct(-0.0154)).toBe('−1.54%');
    expect(pct(0.068, 1)).toBe('6.8%');
  });
  it('formats ISO dates without timezone drift', () => {
    expect(shortDate('2026-10-08')).toBe('Thu, Oct 8');
  });
  it('hides a company name that only repeats the ticker', () => {
    expect(companyName('JNJ', 'JNJ')).toBeNull();
    expect(companyName('jnj ', 'JNJ')).toBeNull();
    expect(companyName(null, 'JNJ')).toBeNull();
    expect(companyName('Johnson & Johnson', 'JNJ')).toBe('Johnson & Johnson');
  });
});
