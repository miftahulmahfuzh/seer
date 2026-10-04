/** Small builders for the sera unit tests. Never imported by app code. */
import type { Gate, LabMethod, LabTrial } from './types';

export const GATE: Gate = {
  maxDrawdown: 0.15,
  minProfitFactor: 1.3,
  minTrades: 100,
  dsrMin: 0.95,
  devStart: '1993-01-29',
  devEnd: '2015-10-16',
  testStart: '2015-10-19',
};

export function trial(over: Partial<LabTrial> = {}): LabTrial {
  return {
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
    curve: [['1996-01-31', 1]],
    ...over,
  };
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
