import { describe, expect, it } from 'vitest';
import { lab, methodById } from './lab';
import { methodHref, paperOf } from './paper';

describe('paper provenance (lab.json `paper`)', () => {
  it('turns a lab-derived roster entry into its method page', () => {
    // The roster entries on paper since the first night (migration 013).
    expect(methodHref('RAW-FR')).toBe('/sera/methods/M0007');
    expect(methodHref('RMW-FR')).toBe('/sera/methods/M0022');
    expect(methodHref('MOM-FR')).toBe('/sera/methods/M0002');
    expect(methodHref('MVW-FR')).toBe('/sera/methods/M0008');
  });

  it('has no answer for an entry the lab never produced', () => {
    // C is design-v0 and SPY is the benchmark: neither is a lab method, and null here is the
    // ordinary answer, not missing data. The leaderboard renders the plain name for both.
    expect(methodHref('C')).toBeNull();
    expect(methodHref('SPY')).toBeNull();
    expect(paperOf('C')).toBeNull();
    expect(methodHref('not-a-strategy')).toBeNull();
  });

  it('only ever points at a method the snapshot actually has', () => {
    // The href is built from `methodId` alone, so a row naming a method the lab does not hold
    // would be a 404 reached by clicking a strategy's name on the leaderboard.
    expect(lab.paper.length).toBeGreaterThan(0);
    for (const p of lab.paper) {
      expect(methodById(p.methodId), `${p.strategyId} -> ${p.methodId}`).toBeDefined();
      expect(methodHref(p.strategyId)).toBe(`/sera/methods/${p.methodId}`);
    }
  });

  it('carries the variant and the basis the entry was admitted on', () => {
    // RAW-FR is the owner-override the roster documents at length: the lab rejected it on the
    // luck test and the roster took it anyway, as the controlled comparison against RMW-FR.
    expect(paperOf('RAW-FR')).toEqual({
      strategyId: 'RAW-FR',
      methodId: 'M0007',
      candidateId: 'M0007-N20-RAW',
      labStatus: 'rejected',
      basis: 'owner-override',
    });
  });
});
