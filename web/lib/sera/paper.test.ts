import { describe, expect, it } from 'vitest';
import { lab, methodById } from './lab';
import { methodHref, paperOf } from './paper';

describe('paper provenance (lab.json `paper`)', () => {
  it('turns a lab-derived roster entry into its method page', () => {
    // The four lab-derived entries on the live roster. They are the -GT successors since the
    // 2026-10-08 Gotrade rebuild, and since 2026-10-14 the unbraked book is the 35-name one:
    // migration 021 moved the roster's width and retired RAW-FR-GT. The snapshot publishes ACTIVE
    // entries only, so the predecessors are no longer here to be looked up.
    expect(methodHref('RAW35-FR-GT')).toBe('/sera/methods/M0139');
    // 2026-10-17: migration 022 put the coskewness book (COSK-FR-GT) in RMW-FR-GT's seat.
    expect(methodHref('COSK-FR-GT')).toBe('/sera/methods/M0179');
    expect(methodHref('MOM-FR-GT')).toBe('/sera/methods/M0002');
    expect(methodHref('MVW-FR-GT')).toBe('/sera/methods/M0008');
  });

  it('has no answer for a retired entry, even one the lab did produce', () => {
    // The purged predecessors, and RAW-FR-GT, retired by 021 when the roster went to 35 names.
    // `LAB_PROVENANCE` still names all of them -- lineage belongs on the roster -- but the
    // snapshot withholds a retired entry, so the site cannot say it is "on paper".
    expect(methodHref('RAW-FR')).toBeNull();
    expect(paperOf('RMW-FR')).toBeNull();
    expect(methodHref('RAW-FR-GT')).toBeNull();
    expect(paperOf('RAW-FR-GT')).toBeNull();
    // RMW-FR-GT, retired by 022 to make room for COSK-FR-GT.
    expect(methodHref('RMW-FR-GT')).toBeNull();
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
    // RAW35-FR-GT is the owner-override the roster documents at length: the owner moved the book
    // from twenty names to thirty-five on evidence from the price history that keeps the companies
    // that failed, and the variant has still never had a test-window look -- which is the thing
    // being overridden. It is the first roster entry admitted at 'dev-eligible' rather than
    // 'rejected': M0139-N35-EBAND fails nothing on the dev window.
    expect(paperOf('RAW35-FR-GT')).toEqual({
      strategyId: 'RAW35-FR-GT',
      methodId: 'M0139',
      candidateId: 'M0139-N35-EBAND',
      labStatus: 'dev-eligible',
      basis: 'owner-override',
    });
  });
});
