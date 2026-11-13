/** Small builders for the sera unit tests. Never imported by app code. */
import type { Gate, LabMethod, LabTrial, LabYardstick } from './types';

export const GATE: Gate = {
  maxDrawdown: 0.25,
  minProfitFactor: 1.3,
  minTrades: 100,
  dsrMin: 0.9,
  dsrPolicy: 'all-trials',
  dsrN: 110,
  dsrNBasis: '110 dev trials, every variant run counted as one independent look',
  yardstickMin: 0.9,
  yardstickDraws: 200,
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
    // Unfunded, like all 128 recorded trials. A test about a funded run sets both together —
    // `derive.moneyWeighted` only reads a row money-weighted when neither is null.
    mwr: null as number | null,
    spyTrMwr: null as number | null,
    failed: ['beats SPY TR'],
    eligible: false,
    dsr: 0.97,
    nTrialsAtRun: 55,
    luckGated: true,
    // No role and no random-twin reading: the state of every arm the lab held when the check
    // began. A test about either sets it.
    role: null,
    yardstick: null as LabYardstick | null,
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
 *
 * `luckGated` follows the window unless the test sets it, which is `store.luck_gated` exactly: a
 * `{ window: 'test' }` trial comes back ungated and carries no luck label, so a test does not
 * have to remember to say both things.
 */
export function withVerdict(t: LabTrial, over: Partial<LabTrial>): LabTrial {
  const luckGated = over.luckGated ?? t.window === 'dev';
  const dsrNow = 'dsrNow' in over ? (over.dsrNow as number | null) : t.dsr;
  const unscored = luckGated && dsrNow === null && !t.failed.some((f) => f.startsWith('DSR >= '));
  const failedNow = over.failedNow ?? (unscored ? [...t.failed, 'DSR >= 0.90'] : t.failed);
  return { ...t, luckGated, failedNow, eligibleNow: over.eligibleNow ?? failedNow.length === 0, dsrNow };
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

/** The engine's random-twin miss and control labels, as `failedNow` carries them. */
export const TWINS_MISS = 'beats 90% of random twins';
export const CONTROL = 'not a control arm';

/** A measured random-twin reading: beat 187 of 200 look-alikes. */
export function reading(over: Partial<LabYardstick> = {}): LabYardstick {
  return {
    status: 'measured',
    percentile: 0.935,
    draws: 200,
    beaten: 187,
    armRate: 0.112,
    medianRate: 0.081,
    tradeRatio: 1.04,
    ...over,
  };
}

/**
 * One dev arm in each state the method page has to draw for the random-twin check, otherwise
 * clean (it clears the six classic hurdles), so a test isolates the seventh.
 *
 * Built here rather than in each test because the committed snapshot cannot supply them: the
 * committed lab has no role and no reading recorded yet, so on the real data every arm is
 * `notMeasured`. These are the only way the other six states are exercised before the backfill.
 */
export function armStates() {
  const clean = { failed: [] as string[], dsr: 0.97, dsrNow: 0.97 };
  return {
    measuredPass: trial({ ...clean, n: 101, candidateId: 'M0001-PASS', role: 'treatment', yardstick: reading(), failedNow: [] }),
    measuredFail: trial({
      ...clean, n: 102, candidateId: 'M0001-FAIL', role: 'treatment',
      yardstick: reading({ percentile: 0.75, beaten: 150, armRate: 0.07 }), failedNow: [TWINS_MISS],
    }),
    unmatched: trial({
      ...clean, n: 103, candidateId: 'M0001-ODD', role: 'treatment',
      yardstick: reading({ status: 'unmatched', percentile: 0.96, beaten: 192, tradeRatio: 2.6 }), failedNow: [TWINS_MISS],
    }),
    notApplicable: trial({
      ...clean, n: 104, candidateId: 'M0001-FUNDS', role: 'treatment',
      yardstick: reading({ status: 'not-applicable', percentile: null, draws: 0, beaten: null, medianRate: null, tradeRatio: null }),
      failedNow: [],
    }),
    notMeasured: trial({ ...clean, n: 105, candidateId: 'M0001-OLD', failedNow: [] }),
    recentUnmeasured: trial({ ...clean, n: 106, candidateId: 'M0001-NEW', role: 'treatment', failedNow: [TWINS_MISS] }),
    control: trial({ ...clean, n: 107, candidateId: 'M0001-RAND', role: 'control', failed: [CONTROL], failedNow: [CONTROL] }),
  };
}
