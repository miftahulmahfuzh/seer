import { describe, expect, it } from 'vitest';
import { DRAWDOWN_FAILURE_PREFIX, DSR_FAILURE_PREFIX, FAILURE_LABEL } from './derive';
import { childrenOf, insightsOf, lab, methodById, trialsOf } from './lab';
import { DSR_POLICIES, INSIGHT_KINDS, METHOD_STATUSES, SOURCE_KINDS } from './types';

describe('lab snapshot (web/data/lab.json)', () => {
  it('has exactly the contract keys', () => {
    expect(lab.version).toBe(1);
    expect(Object.keys(lab).sort()).toEqual(
      ['asOf', 'benchmark', 'data', 'gate', 'ideasSeen', 'insights', 'methods', 'summary', 'trials', 'version'].sort(),
    );
    expect(typeof lab.asOf).toBe('string');
    for (const k of ['maxDrawdown', 'minProfitFactor', 'minTrades', 'dsrMin', 'dsrN'] as const) {
      expect(Number.isFinite(lab.gate[k])).toBe(true);
    }
    // The N the luck bar is deflated by, and the evidence for it (design §7.2).
    expect(DSR_POLICIES).toContain(lab.gate.dsrPolicy);
    expect(Number.isInteger(lab.gate.dsrN) && lab.gate.dsrN >= 0).toBe(true);
    expect(lab.gate.dsrNBasis.length).toBeGreaterThan(0);
    expect(lab.gate.devStart).toBe('1993-01-29');
  });

  it('writes every failure label in a shape conditionOk can read', () => {
    // `trials` is append-only: rows judged before 2026-10-07 carry `DSR >= 0.95`, rows judged
    // after carry `DSR >= 0.90`, and `conditionOk` reads the luck check by prefix for exactly
    // that reason. Checked against the real snapshot rather than a fixture, because the failure
    // this guards against is a label the engine starts writing that the site stops recognising —
    // which renders a missed hurdle as a tick, silently, on the page the owner reads.
    const known = new Set(Object.values(FAILURE_LABEL));
    const unreadable = lab.trials
      .flatMap((t) => t.failed)
      .filter(
        (f) =>
          !known.has(f) &&
          !f.startsWith(DSR_FAILURE_PREFIX) &&
          !f.startsWith(DRAWDOWN_FAILURE_PREFIX),
      );
    expect([...new Set(unreadable)]).toEqual([]);
  });

  it('still reads the two labels the owner moved the bars on', () => {
    // Both prefixes must actually match something in the committed snapshot, or the pin above
    // would pass vacuously after a label change that silenced them.
    const all = lab.trials.flatMap((t) => t.failed);
    expect(all.some((f) => f.startsWith(DSR_FAILURE_PREFIX))).toBe(true);
    expect(all.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX))).toBe(true);
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
