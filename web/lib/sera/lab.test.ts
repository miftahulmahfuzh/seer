import { describe, expect, it } from 'vitest';
import { DRAWDOWN_FAILURE_PREFIX, DSR_FAILURE_PREFIX, FAILURE_LABEL } from './derive';
import { childrenOf, insightsOf, lab, methodById, trialsOf } from './lab';
import { DSR_POLICIES, INSIGHT_KINDS, METHOD_STATUSES, SOURCE_KINDS } from './types';

describe('lab snapshot (web/data/lab.json)', () => {
  it('has exactly the contract keys', () => {
    expect(lab.version).toBe(5);
    expect(Object.keys(lab).sort()).toEqual(
      ['asOf', 'benchmark', 'data', 'gate', 'ideasSeen', 'insights', 'methods', 'paper', 'summary',
        'trials', 'version'].sort(),
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
      .flatMap((t) => [...t.failed, ...t.failedNow])
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

  it('publishes a verdict that agrees with the gate published beside it', () => {
    // The regression this file exists to catch. `/sera/methods/M0022` once rendered
    // "Luck check: no (0.912 < 0.90)": the cross came from the trial's recorded `DSR >= 0.95`
    // and the number from the live gate. Both halves of every hurdle must now come from the
    // same day, so a scored trial misses the luck check exactly when its score is under the bar.
    //
    // Which rows that applies to is the engine's answer, read here and not re-derived: a
    // pre-registered test look has no selection to deflate, so `published_verdict` applies the
    // owner thresholds and nothing else and `luckGated` is false. Before the marker existed this
    // branch had to be either a failure (it was) or an exception that also excused the live page.
    for (const t of lab.trials) {
      const missedLuck = t.failedNow.some((f) => f.startsWith(DSR_FAILURE_PREFIX));
      if (!t.luckGated) {
        // No hurdle, whatever the score. M0021-B70-RAW: 0.513013, and correctly not a failure.
        expect([t.candidateId, missedLuck]).toEqual([t.candidateId, false]);
      } else if (t.dsrNow !== null) {
        expect([t.candidateId, missedLuck]).toEqual([t.candidateId, t.dsrNow < lab.gate.dsrMin]);
      } else {
        // A trial with no score cannot pass a luck test it never had.
        expect([t.candidateId, missedLuck]).toEqual([t.candidateId, true]);
      }

      // The drawdown condition can no longer be re-derived from the published gate, and that is
      // a deliberate change rather than a gap. On 2026-10-14 the owner split the lab's dev SCREEN
      // (50%: is this worth another hour of study) off his real-money BAR (25%: would he fund it)
      // -- design §18. `failedNow` is judged against the screen; `gate.maxDrawdown` publishes the
      // bar. So `maxDrawdown > gate.maxDrawdown` stopped implying a recorded drawdown miss, and
      // the old equality here would now fail on every trial that falls between the two numbers.
      //
      // What still holds is the one-way implication, and it is the half worth pinning: the screen
      // is looser than the bar, so a trial inside the BAR is necessarily inside the screen and can
      // never record a drawdown miss. A trial outside the bar may go either way -- that is exactly
      // the band the split created.
      const missedDd = t.failedNow.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX));
      if (t.maxDrawdown !== null && t.maxDrawdown <= lab.gate.maxDrawdown) {
        expect([t.candidateId, missedDd]).toEqual([t.candidateId, false]);
      }
      expect(t.eligibleNow).toBe(t.failedNow.length === 0);
    }

    // ...and the band is not empty, or the assertion above would be vacuous and the split would
    // be invisible here: at least one published trial falls further than the owner would fund and
    // is still, correctly, carrying no drawdown miss because the lab thinks it worth studying.
    const studiedButUnfundable = lab.trials.filter(
      (t) => t.maxDrawdown !== null
        && t.maxDrawdown > lab.gate.maxDrawdown
        && !t.failedNow.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX)),
    );
    expect(studiedButUnfundable.length).toBeGreaterThan(0);
  });

  it('says per trial whether the luck gate applies, and the ungated branch is not empty', () => {
    // The marker's contract, pinned on the real snapshot: it is window-shaped, it agrees with
    // `summary.testLooks`, and there is at least one row where it actually changes the answer —
    // a scored row, under the bar, that is correctly not a failure. Without that last pin the
    // branch above could pass vacuously the day the lab's test looks are rewritten.
    expect(lab.trials.every((t) => t.luckGated === (t.window === 'dev'))).toBe(true);
    const ungated = lab.trials.filter((t) => !t.luckGated);
    expect(ungated.length).toBe(lab.summary.testLooks);
    expect(ungated.length).toBeGreaterThan(0);
    const underTheBarAnyway = ungated.filter(
      (t) => t.dsrNow !== null && t.dsrNow < lab.gate.dsrMin,
    );
    expect(underTheBarAnyway.length).toBeGreaterThan(0);
    for (const t of underTheBarAnyway) {
      expect(t.failedNow.some((f) => f.startsWith(DSR_FAILURE_PREFIX))).toBe(false);
    }
  });

  it('carries a record that differs from the verdict, so neither pin is vacuous', () => {
    // 110 committed rows were judged against the old 0.95 and 15% bars and still say so. If the
    // two lists ever became identical everywhere, the test above would stop proving anything.
    const split = lab.trials.filter((t) => t.failed.join('; ') !== t.failedNow.join('; '));
    expect(split.length).toBeGreaterThan(0);
    // And the split actually moves an outcome: some row is eligible today that was not when run.
    expect(lab.trials.some((t) => t.eligibleNow && !t.eligible)).toBe(true);
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
    // Scanned rather than asserted point by point: the curves hold millions of samples between
    // them, and one `expect` per sample spent most of a five-second budget on matcher overhead
    // alone -- the test timed out on roughly two runs in three, and every new trial made it
    // worse. Collecting the first offender keeps the same meaning, reports a better message
    // (which trial, which point) and runs in milliseconds.
    const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
    const orphans: string[] = [];
    const unlabelled: string[] = [];
    const badPoints: string[] = [];
    for (const t of lab.trials) {
      if (methodById(t.methodId) === undefined) orphans.push(`n=${t.n} -> ${t.methodId}`);
      if (!Array.isArray(t.failed)) unlabelled.push(`n=${t.n}`);
      for (let i = 0; i < t.curve.length; i++) {
        const [d, v] = t.curve[i];
        if (typeof d !== 'string' || !ISO_DAY.test(d) || typeof v !== 'number') {
          badPoints.push(`n=${t.n}[${i}] = ${JSON.stringify(t.curve[i])}`);
          break; // one example per trial is enough to name the offender
        }
      }
    }
    expect(orphans).toEqual([]);
    expect(unlabelled).toEqual([]);
    expect(badPoints).toEqual([]);
    // The scan is only meaningful if it actually walked something.
    expect(lab.trials.length).toBeGreaterThan(0);
    expect(lab.trials.some((t) => t.curve.length > 0)).toBe(true);
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
