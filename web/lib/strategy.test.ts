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
    expect(parseGate({ passed: false })).toEqual({ passed: false, applicable: true });
    expect(parseGate({ passed: true })).toEqual({ passed: true, applicable: true });
  });
  it('never assumes a pass', () => {
    expect(parseGate(null)).toEqual({ passed: false, applicable: true });
    expect(parseGate(undefined)).toEqual({ passed: false, applicable: true });
    expect(parseGate({ passed: 'true' })).toEqual({ passed: false, applicable: true });
    expect(parseGate([true])).toEqual({ passed: false, applicable: true });
  });
  it('reads a not-applicable gate (C, design §1 item 5)', () => {
    expect(parseGate({ passed: false, applicable: false })).toEqual({ passed: false, applicable: false });
  });
  it('only an explicit false makes the gate not applicable, and not applicable is never a pass', () => {
    expect(parseGate({ passed: false, applicable: 'false' }).applicable).toBe(true);
    expect(parseGate({ passed: false, applicable: null }).applicable).toBe(true);
    expect(parseGate({ passed: true, applicable: false })).toEqual({ passed: false, applicable: false });
  });

  // The gate note is purged (owner, 2026-10-07): the checklist states the verdict, and the
  // reasoning lives on the method's Sera page. Rows frozen before that date still carry a note in
  // `params.backtest_gate`, so the guarantee has to hold against the stored shape, not just the
  // new one — this is the boundary where the prose stops, and nothing past it can leak it.
  it('drops a stored note instead of carrying it into the app', () => {
    const stored = { passed: false, note: 'Lab M0022 dev window only; failed only DSR >= 0.95 (0.916 at N=110)' };
    expect(parseGate(stored)).toEqual({ passed: false, applicable: true });
    expect('note' in parseGate(stored)).toBe(false);
    expect(JSON.stringify(parseGate(stored))).not.toContain('M0022');
    expect('note' in parseGate({ passed: false, applicable: false, note: 'Not applicable (LLM strategy)' })).toBe(false);
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
