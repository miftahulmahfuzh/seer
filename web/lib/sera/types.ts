/** The lab snapshot contract: `web/data/lab.json`, written by `python -m seer_engine lab export-json`. */

export type LabSnapshot = {
  version: 1;
  asOf: string;
  gate: {
    maxDrawdown: number;
    minProfitFactor: number;
    minTrades: number;
    /** The luck bar (`lab.store.DSR_MIN`): 0.90 since 2026-10-07, the owner's risk appetite. */
    dsrMin: number;
    /** Which multiple-testing policy sets the luck check's N (`lab.store.DSR_POLICY`, design §7.2). */
    dsrPolicy: DsrPolicy;
    /** The N that policy resolves to on this snapshot's data. Resolved at export time, not stored. */
    dsrN: number;
    /** One line of evidence for that N, written by the engine. Display as given; never parse it. */
    dsrNBasis: string;
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

/**
 * The named multiple-testing policies the luck gate can deflate by (`lab/npolicy.py`).
 * `all-trials` is in force and was left there deliberately (design §7.2); the other two are
 * measured, tested and one constant away, which is why the site names the one in use.
 */
export type DsrPolicy = 'all-trials' | 'methods' | 'effective';
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

export const DSR_POLICIES = [
  'all-trials',
  'methods',
  'effective',
] as const satisfies readonly DsrPolicy[];

/** What each policy counts, in the site's own plain words. Never show the identifier alone. */
export const DSR_POLICY_LABEL: Record<DsrPolicy, string> = {
  'all-trials': 'one look per variant run',
  methods: 'one look per distinct idea',
  effective: 'one look per independent return stream',
};
