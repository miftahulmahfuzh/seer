import { describe, expect, it } from 'vitest';
import { childrenOf, insightsOf, lab, methodById, trialsOf } from './lab';
import { INSIGHT_KINDS, METHOD_STATUSES, SOURCE_KINDS } from './types';

describe('lab snapshot (web/data/lab.json)', () => {
  it('has exactly the contract keys', () => {
    expect(lab.version).toBe(1);
    expect(Object.keys(lab).sort()).toEqual(
      ['asOf', 'benchmark', 'data', 'gate', 'ideasSeen', 'insights', 'methods', 'summary', 'trials', 'version'].sort(),
    );
    expect(typeof lab.asOf).toBe('string');
    for (const k of ['maxDrawdown', 'minProfitFactor', 'minTrades', 'dsrMin'] as const) {
      expect(Number.isFinite(lab.gate[k])).toBe(true);
    }
    expect(lab.gate.devStart).toBe('1993-01-29');
  });

  it('starts the SPY benchmark at 1.0 on 1993-01-29', () => {
    expect(lab.benchmark.spyTr[0]).toEqual(['1993-01-29', 1]);
    expect(lab.benchmark.spyTr.length).toBeGreaterThan(100);
  });

  it('agrees with its own summary', () => {
    expect(lab.summary.methods).toBe(lab.methods.length);
    expect(lab.summary.devTrials).toBe(lab.trials.filter((t) => t.window === 'dev').length);
    expect(lab.summary.insights).toBe(lab.insights.length);
  });

  it('uses only known statuses, kinds and sources', () => {
    for (const m of lab.methods) {
      expect(METHOD_STATUSES).toContain(m.status);
      expect(SOURCE_KINDS).toContain(m.sourceKind);
      expect(m.historical).toBe(m.id.startsWith('H-'));
    }
    for (const i of lab.insights) expect(INSIGHT_KINDS).toContain(i.kind);
  });

  it('links every trial to a method and parses curves as [date, value] pairs', () => {
    for (const t of lab.trials) {
      expect(methodById(t.methodId)).toBeDefined();
      expect(Array.isArray(t.failed)).toBe(true);
      for (const [d, v] of t.curve) {
        expect(d).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(typeof v).toBe('number');
      }
    }
  });

  it('serves accessors consistent with the raw lists', () => {
    for (const m of lab.methods) {
      expect(methodById(m.id)).toBe(m);
      const ts = trialsOf(m.id);
      expect(ts.every((t) => t.methodId === m.id)).toBe(true);
      expect(ts.map((t) => t.n)).toEqual([...ts.map((t) => t.n)].sort((a, b) => a - b));
      expect(insightsOf(m.id).every((i) => i.methodId === m.id)).toBe(true);
      expect(childrenOf(m.id).every((c) => c.parentId === m.id)).toBe(true);
    }
    expect(trialsOf('NOPE')).toEqual([]);
    expect(methodById('NOPE')).toBeUndefined();
  });
});
