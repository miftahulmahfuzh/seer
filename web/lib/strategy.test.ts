import { describe, expect, it } from 'vitest';
import { checksNews, engineOf, parseGate, shortLabel } from './strategy';

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
      .toEqual({ passed: false, applicable: true, note: 'P7a dev window only; failed max DD <= 15% (22.2%)' });
    expect(parseGate({ passed: true, note: '' })).toEqual({ passed: true, applicable: true, note: null });
  });
  it('never assumes a pass', () => {
    expect(parseGate(null)).toEqual({ passed: false, applicable: true, note: null });
    expect(parseGate(undefined)).toEqual({ passed: false, applicable: true, note: null });
    expect(parseGate({ passed: 'true' })).toEqual({ passed: false, applicable: true, note: null });
    expect(parseGate([true])).toEqual({ passed: false, applicable: true, note: null });
  });
  it('reads a not-applicable gate (C, design §1 item 5)', () => {
    const note = 'Backtest gate: not applicable (LLM strategy, design §1 item 5)';
    expect(parseGate({ passed: false, applicable: false, note })).toEqual({ passed: false, applicable: false, note });
  });
  it('only an explicit false makes the gate not applicable, and not applicable is never a pass', () => {
    expect(parseGate({ passed: false, applicable: 'false' }).applicable).toBe(true);
    expect(parseGate({ passed: false, applicable: null }).applicable).toBe(true);
    expect(parseGate({ passed: true, applicable: false })).toEqual({ passed: false, applicable: false, note: null });
  });
});

describe('shortLabel', () => {
  it('takes the part before the middle dot', () => {
    expect(shortLabel('F4 · Momentum', 'F4-MOM12-N20-TREND')).toBe('F4');
    expect(shortLabel('A · Quant', 'A')).toBe('A');
    expect(shortLabel('C · News veto', 'C')).toBe('C');
    expect(shortLabel('SPY', 'SPY')).toBe('SPY');
    expect(shortLabel(' · Nameless', 'X1')).toBe('X1');
  });
});

describe('checksNews', () => {
  it('is true for the C object or the C roster id', () => {
    expect(checksNews('C', 'STRATEGY_C')).toBe(true);
    expect(checksNews('C', null)).toBe(true);
    expect(checksNews('C2-news', 'STRATEGY_C')).toBe(true);
  });
  it('is false for every other strategy', () => {
    expect(checksNews('A', 'STRATEGY_A')).toBe(false);
    expect(checksNews('SPY', null)).toBe(false);
    expect(checksNews('F4-MOM12-N20-TREND', 'FACTOR')).toBe(false);
  });
});
