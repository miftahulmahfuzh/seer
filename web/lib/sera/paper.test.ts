import { describe, expect, it } from 'vitest';
import { lab, methodById } from './lab';
import { methodHref, paperOf } from './paper';

describe('paper provenance (lab.json `paper`)', () => {
  it('turns a lab-derived roster entry into its method page', () => {
    // The four lab-derived entries on the live roster. They are the -GT successors since the
    // 2026-10-08 Gotrade rebuild: the snapshot publishes ACTIVE entries only, so the predecessors
    // these replaced (RAW-FR, RMW-FR, MOM-FR, MVW-FR) are no longer here to be looked up. Same
    // methods, same hrefs -- a rebuild changes which entry trades them, not which method they are.
    expect(methodHref('RAW-FR-GT')).toBe('/sera/methods/M0007');
    expect(methodHref('RMW-FR-GT')).toBe('/sera/methods/M0022');
    expect(methodHref('MOM-FR-GT')).toBe('/sera/methods/M0002');
    expect(methodHref('MVW-FR-GT')).toBe('/sera/methods/M0008');
  });

  it('has no answer for a retired entry, even one the lab did produce', () => {
    // The purged predecessors. `LAB_PROVENANCE` still names them -- lineage belongs on the roster
    // -- but the snapshot withholds them, so the site cannot say a deleted entry is "on paper".
    expect(methodHref('RAW-FR')).toBeNull();
    expect(paperOf('RMW-FR')).toBeNull();
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
    // RAW-FR-GT is the owner-override the roster documents at length: the lab rejected the method
    // on the luck test and the roster took it anyway, as the controlled comparison against
    // RMW-FR-GT. The basis survived the Gotrade rebuild because the successor admits the same
    // method on the same grounds -- only the fee schedule it pays changed.
    expect(paperOf('RAW-FR-GT')).toEqual({
      strategyId: 'RAW-FR-GT',
      methodId: 'M0007',
      candidateId: 'M0007-N20-RAW',
      labStatus: 'rejected',
      basis: 'owner-override',
    });
  });
});
