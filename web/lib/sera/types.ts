/** The lab snapshot contract: `web/data/lab.json`, written by `python -m seer_engine lab export-json`. */

export type LabSnapshot = {
  version: 1;
  asOf: string;
  gate: {
    maxDrawdown: number;
    minProfitFactor: number;
    minTrades: number;
    dsrMin: number;
    devStart: '1993-01-29';
    devEnd: '2015-10-16';
    testStart: '2015-10-19';
  };
  data: {
    storeStart: '1993-01-29';
    membershipStart: '1996-01-02';
    fxStart: '1999-01-04';
    fingerprints: string[];
    barRows: number;
    symbolsRequested: number;
    symbolsServed: number;
    dividendRows: number;
  };
  summary: {
    devTrials: number;
    testLooks: number;
    methods: number;
    labMethods: number;
    historicalMethods: number;
    insights: number;
    byStatus: Record<string, number>;
  };
  benchmark: { spyTr: [string, number][]; spyPrice: [string, number][] };
  methods: LabMethod[];
  trials: LabTrial[];
  insights: LabInsight[];
  ideasSeen: LabSeen[];
};

export type LabMethod = {
  id: string;
  name: string;
  family: string;
  parentId: string | null;
  sourceKind: 'paper' | 'blog' | 'github' | 'knowledge' | 'variation' | 'seed';
  sourceRef: string;
  hypothesis: string;
  expectedFailure: string | null;
  status:
    | 'idea'
    | 'registered'
    | 'rejected'
    | 'dev-eligible'
    | 'promoted'
    | 'test-passed'
    | 'test-failed'
    | 'paper'
    | 'blocked-data';
  analysis: string;
  verdict: string;
  blockedOn: string;
  created: string;
  updated: string;
  historical: boolean;
};

export type LabTrial = {
  n: number;
  methodId: string;
  candidateId: string;
  rulesId: string;
  allocatorId: string;
  configText: string;
  window: 'dev' | 'test';
  start: string;
  end: string;
  gitSha: string;
  runAt: string;
  totalReturn: number | null;
  cagr: number | null;
  maxDrawdown: number | null;
  profitFactor: number | null;
  pfInfinite: boolean;
  trades: number;
  sharpe: number | null;
  exposure: number | null;
  turnover: number | null;
  worstYear: number | null;
  worstYearReturn: number | null;
  spyTrReturn: number | null;
  spyTrCagr: number | null;
  mar: number | null;
  failed: string[];
  eligible: boolean;
  dsr: number | null;
  nTrialsAtRun: number;
  curve: [string, number][];
};

export type LabInsight = {
  id: number;
  kind: 'observation' | 'hypothesis' | 'data-wish' | 'feature-wish' | 'risk' | 'synthesis';
  title: string;
  body: string;
  methodId: string | null;
  added: string;
};

export type LabSeen = { key: string; methodId: string | null; note: string; added: string };

export type LabStatus = LabMethod['status'];
export type InsightKind = LabInsight['kind'];
export type SourceKind = LabMethod['sourceKind'];
export type Gate = LabSnapshot['gate'];
export type Benchmark = LabSnapshot['benchmark'];
/** A dated value: [ISO date, value]. */
export type Point = [string, number];

export const METHOD_STATUSES = [
  'idea',
  'registered',
  'rejected',
  'dev-eligible',
  'promoted',
  'test-passed',
  'test-failed',
  'paper',
  'blocked-data',
] as const satisfies readonly LabStatus[];

export const INSIGHT_KINDS = [
  'synthesis',
  'observation',
  'hypothesis',
  'data-wish',
  'feature-wish',
  'risk',
] as const satisfies readonly InsightKind[];

export const SOURCE_KINDS = [
  'paper',
  'blog',
  'github',
  'knowledge',
  'variation',
  'seed',
] as const satisfies readonly SourceKind[];
