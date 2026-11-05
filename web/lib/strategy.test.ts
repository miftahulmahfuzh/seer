import { describe, expect, it } from 'vitest';
import { attachedOriginal, checksNews, engineOf, gateOf, orderTwins, parseGate, shortLabel, TWIN_GATE, twinOfRow, type TwinIn } from './strategy';

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
  it('is never true for a Claude twin, whatever its spec names', () => {
    expect(checksNews('C-CX', 'STRATEGY_C', 'C')).toBe(false);
    expect(checksNews('A-GT-CX', 'STRATEGY_A', 'A-GT')).toBe(false);
    expect(checksNews('C', 'STRATEGY_C', null)).toBe(true);
  });
});

describe('twinOfRow', () => {
  it('reads the original id of a Claude twin', () => {
    expect(twinOfRow('RAW35-FR-GT')).toBe('RAW35-FR-GT');
  });
  it('reads anything else as not a twin, including a DB without migration 027', () => {
    expect(twinOfRow(null)).toBeNull();
    expect(twinOfRow(undefined)).toBeNull();
    expect(twinOfRow('')).toBeNull();
    expect(twinOfRow(42)).toBeNull();
  });
});

describe('gateOf', () => {
  it("gives a twin the twin gate, even when params say it passed or params are still '{}'", () => {
    expect(gateOf({ passed: true }, 'A-GT')).toEqual({ passed: false, applicable: false, twin: true });
    expect(gateOf(null, 'A-GT')).toBe(TWIN_GATE);
  });
  it('reads every other row exactly as parseGate does', () => {
    expect(gateOf({ passed: true }, null)).toEqual(parseGate({ passed: true }));
    expect(gateOf({ passed: false, applicable: false }, null)).toEqual({ passed: false, applicable: false });
    expect('twin' in gateOf({ passed: false }, null)).toBe(false);
  });
  it('cannot be edited by a caller', () => {
    expect(Object.isFrozen(TWIN_GATE)).toBe(true);
  });
});

describe('orderTwins', () => {
  const row = (id: string, twinOf: string | null = null) => ({ id, twinOf });

  it('puts each twin directly after its original, wherever the twin started', () => {
    const rows = [row('SPY'), row('A-GT-CX', 'A-GT'), row('A-GT'), row('RAW35'), row('C'), row('RAW35-CX', 'RAW35')];
    expect(orderTwins(rows).map(r => r.id)).toEqual(['SPY', 'A-GT', 'A-GT-CX', 'RAW35', 'RAW35-CX', 'C']);
  });
  it('leaves a list without twins exactly as it was', () => {
    const rows = [row('SPY'), row('A'), row('F4'), row('C')];
    expect(orderTwins(rows)).toEqual(rows);
  });
  it('keeps a twin whose original is not on the list where it was', () => {
    const rows = [row('SPY'), row('X-CX', 'X'), row('C')];
    expect(orderTwins(rows).map(r => r.id)).toEqual(['SPY', 'X-CX', 'C']);
  });
  it('never drops or duplicates a row, even for a twin of a twin', () => {
    const rows = [row('B-CX-CX', 'B-CX'), row('B'), row('B-CX', 'B')];
    const out = orderTwins(rows).map(r => r.id);
    expect(out).toHaveLength(3);
    expect(new Set(out)).toEqual(new Set(['B', 'B-CX', 'B-CX-CX']));
    expect(out.indexOf('B-CX')).toBe(out.indexOf('B') + 1);
  });
});

describe('attachedOriginal', () => {
  it('finds the original on the list, and nothing for a plain row', () => {
    const a: TwinIn = { id: 'A', twinOf: null }, t: TwinIn = { id: 'A-CX', twinOf: 'A' };
    const byId = new Map([[a.id, a], [t.id, t]]);
    expect(attachedOriginal(t, byId)).toBe(a);
    expect(attachedOriginal(a, byId)).toBeNull();
  });
});
