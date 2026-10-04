import { describe, expect, it } from 'vitest';
import { engineOf, parseGate, shortLabel } from './strategy';

describe('engineOf', () => {
  it('keeps a known engine', () => {
    expect(engineOf('book', false)).toBe('book');
    expect(engineOf('bracket', false)).toBe('bracket');
    expect(engineOf('benchmark', true)).toBe('benchmark');
  });
  it('falls back for rows written before migration 003', () => {
    expect(engineOf(null, true)).toBe('benchmark');
    expect(engineOf(null, false)).toBe('bracket');
    expect(engineOf('ml', false)).toBe('bracket');
  });
});

describe('parseGate', () => {
  it('reads the backtest gate from params', () => {
    expect(parseGate({ passed: false, note: 'P7a dev window only; failed max DD <= 15% (22.2%)' }))
      .toEqual({ passed: false, note: 'P7a dev window only; failed max DD <= 15% (22.2%)' });
    expect(parseGate({ passed: true, note: '' })).toEqual({ passed: true, note: null });
  });
  it('never assumes a pass', () => {
    expect(parseGate(null)).toEqual({ passed: false, note: null });
    expect(parseGate(undefined)).toEqual({ passed: false, note: null });
    expect(parseGate({ passed: 'true' })).toEqual({ passed: false, note: null });
    expect(parseGate([true])).toEqual({ passed: false, note: null });
  });
});

describe('shortLabel', () => {
  it('takes the part before the middle dot', () => {
    expect(shortLabel('F4 · Momentum', 'F4-MOM12-N20-TREND')).toBe('F4');
    expect(shortLabel('A · Quant', 'A')).toBe('A');
    expect(shortLabel('SPY', 'SPY')).toBe('SPY');
    expect(shortLabel(' · Nameless', 'X1')).toBe('X1');
  });
});
