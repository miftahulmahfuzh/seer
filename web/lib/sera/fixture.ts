/** Small builders for the sera unit tests. Never imported by app code. */
import type { Gate, LabMethod, LabTrial } from './types';

export const GATE: Gate = {
  maxDrawdown: 0.2,
  minProfitFactor: 1.3,
  minTrades: 100,
  dsrMin: 0.9,
  dsrPolicy: 'all-trials',
  dsrN: 110,
  dsrNBasis: '110 dev trials, every variant run counted as one independent look',
  devStart: '1993-01-29',
  devEnd: '2015-10-16',
  testStart: '2015-10-19',
};

/**
 * A trial. `failedNow` / `eligibleNow` / `dsrNow` mirror the record unless the test sets them.
 *
 * Mirroring is the right default because most tests mean "this is the verdict today" and say so
 * through `failed`. Only a test about the record/verdict split — a row recorded against the old
 * 0.95 bar and read against today's 0.90 — sets the two sides apart, and then it must set both,
 * which is exactly the distinction worth making explicit in such a test.
 */
export function trial(over: Partial<LabTrial> = {}): LabTrial {
  const t: LabTrial = {
    n: 1,
    methodId: 'M0001',
    candidateId: 'M0001-V1',
    rulesId: 'rules-v1',
    allocatorId: 'alloc-v1',
    configText: '{}',
    window: 'dev',
    start: '1996-01-03',
    end: '2015-10-16',
    gitSha: 'abc1234',
    runAt: '2026-10-04T10:00:00+07:00',
    totalReturn: 3.2,
    cagr: 0.076,
    maxDrawdown: 0.12,
    profitFactor: 1.5,
    pfInfinite: false,
    trades: 240,
    sharpe: 0.8,
    exposure: 0.9,
    turnover: 2.1,
    worstYear: 2008,
    worstYearReturn: -0.11,
    spyTrReturn: 4.0,
    spyTrCagr: 0.079,
    mar: 0.63,
    failed: ['beats SPY TR'],
    eligible: false,
    dsr: 0.97,
    nTrialsAtRun: 55,
    failedNow: [] as string[],
    eligibleNow: false,
    dsrNow: null as number | null,
    curve: [['1996-01-31', 1]] as [string, number][],
    ...over,
  };
  return withVerdict(t, over);
}

/**
 * Default a trial's verdict fields from its record: `failedNow` mirrors `failed`, `dsrNow`
 * mirrors `dsr`, and a row with no score picks up the luck label — the engine's own rule, that a
 * luck test which cannot be scored was not passed. Shared by the test-local trial builders so
 * all three agree. A test about the record/verdict split passes the fields explicitly instead.
 */
export function withVerdict(t: LabTrial, over: Partial<LabTrial>): LabTrial {
  const dsrNow = 'dsrNow' in over ? (over.dsrNow as number | null) : t.dsr;
  const unscored = dsrNow === null && !t.failed.some((f) => f.startsWith('DSR >= '));
  const failedNow = over.failedNow ?? (unscored ? [...t.failed, 'DSR >= 0.90'] : t.failed);
  return { ...t, failedNow, eligibleNow: over.eligibleNow ?? failedNow.length === 0, dsrNow };
}

export function method(over: Partial<LabMethod> = {}): LabMethod {
  return {
    id: 'M0001',
    name: 'Momentum, risk managed',
    family: 'stock-momentum-risk-managed',
    parentId: null,
    sourceKind: 'paper',
    sourceRef: 'https://example.com/paper',
    hypothesis: 'Scaling momentum by its own volatility cuts the crashes.',
    expectedFailure: null,
    status: 'rejected',
    analysis: '',
    verdict: '',
    blockedOn: '',
    created: '2026-10-04',
    updated: '2026-10-04',
    historical: false,
    ...over,
  };
}
