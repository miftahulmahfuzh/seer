import { BookOpen, Gauge, Gavel, Landmark, Shield, Sigma } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import { selectStrategy, sharesLabel, strategyIcon } from './roster';

const roster = [
  { id: 'SPY', name: 'SPY', isChampion: true, isBenchmark: true },
  { id: 'A', name: 'A · Quant', isChampion: false, isBenchmark: false },
  { id: 'F4-MOM12-N20-TREND', name: 'F4 · Momentum', isChampion: false, isBenchmark: false },
  { id: 'F1-SPY-SMA200-M', name: 'F1 · Trend', isChampion: false, isBenchmark: false },
  { id: 'C', name: 'C · News veto', isChampion: false, isBenchmark: false },
];

describe('selectStrategy', () => {
  it('returns the requested strategy when it is on the roster', () => {
    expect(selectStrategy(roster, 'F1-SPY-SMA200-M')?.id).toBe('F1-SPY-SMA200-M');
    expect(selectStrategy(roster, 'SPY')?.id).toBe('SPY');
    expect(selectStrategy(roster, 'C')?.id).toBe('C');
  });
  it('defaults to the first research strategy', () => {
    expect(selectStrategy(roster, undefined)?.id).toBe('A');
    expect(selectStrategy(roster, 'B')?.id).toBe('A');
  });
  it('falls back to the first row, then null', () => {
    expect(selectStrategy([roster[0]], undefined)?.id).toBe('SPY');
    expect(selectStrategy([], undefined)).toBeNull();
  });
});

describe('strategyIcon', () => {
  it('maps the roster icons and falls back to Sigma', () => {
    expect(strategyIcon('landmark')).toBe(Landmark);
    expect(strategyIcon('trending-up')).toBe(Gauge);
    expect(strategyIcon('shield')).toBe(Shield);
    expect(strategyIcon('gavel')).toBe(Gavel);
    expect(strategyIcon('sigma')).toBe(Sigma);
    expect(strategyIcon('book-open')).toBe(BookOpen);
    expect(strategyIcon('nope')).toBe(Sigma);
  });
});

describe('sharesLabel', () => {
  it('formats whole and fractional shares', () => {
    expect(sharesLabel(1)).toBe('1 share');
    expect(sharesLabel(3)).toBe('3 shares');
    expect(sharesLabel(2.5)).toBe('2.5 shares');
    expect(sharesLabel(0.123456)).toBe('0.1235 shares');
  });
});
