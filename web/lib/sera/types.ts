/** The lab snapshot contract: `web/data/lab.json`, written by `python -m seer_engine lab export-json`. */

export type LabSnapshot = {
  /**
   * 2 added the derived verdict to every trial (`failedNow` / `eligibleNow` / `dsrNow`);
   * 3 added `paper`, which names the lab method behind each roster entry.
   */
  version: 3;
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
  /** Where each paper roster entry came from in the lab (`paper.roster.LAB_PROVENANCE`). */
  paper: LabPaper[];
};

/**
 * One roster entry's lab provenance, as the engine records it. A fact about the night the entry
 * was admitted, not a live read: `labStatus` is the method's status at that moment and never
 * tracks the method's current one. Only entries that came from the lab appear — C and SPY have
 * no row here, and must not be linked to a method page.
 */
export type LabPaper = {
  /** `strategies.id` on the leaderboard: 'RAW-FR', 'RMW-FR', … */
  strategyId: string;
  methodId: string;
  /** The exact variant behind the entry: 'M0007-N20-RAW'. */
  candidateId: string;
  /** The method's status when the roster took it. */
  labStatus: string;
  /** 'test-passed' (the lab's own route) or 'owner-override' (the roster's). */
  basis: string;
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
  /**
   * **The record, not the verdict.** The hurdles this trial missed *on the day it ran*, by the
   * bars of that day: `trials` is append-only, so 110 committed rows still say `DSR >= 0.95` and
   * `max DD <= 15%` even though the owner moved both bars on 2026-10-07.
   *
   * Display this only in the technical record, where it is labelled as history. Anything that
   * decides a tick, a count or a colour must read `failedNow` — judging a row by `failed` while
   * printing a target out of `gate` is what put `0.912 < 0.90` on the method page.
   */
  failed: string[];
  /** The record: eligible as judged on the run date. For today's answer, `eligibleNow`. */
  eligible: boolean;
  /** The record: the deflated Sharpe as scored at `nTrialsAtRun`. For today's, `dsrNow`. */
  dsr: number | null;
  /** The record: how many tries the lab had counted when this one ran. */
  nTrialsAtRun: number;
  /**
   * **The verdict: the hurdles this trial misses now**, by the bars in `gate`, at `gate.dsrN`.
   * Written by the engine's `store.published_verdict` at export time — the web never re-judges a
   * trial, and must not try: the luck test is not a comparison of `dsr` against `gate.dsrMin`.
   * `dsr` is scored at the N of its own run date, and re-scoring it at today's N is arithmetic
   * only the engine holds (`M0007-N20-RAW` reads 0.9138 at N = 85 and 0.8985 at N = 110 — a pass
   * and a fail, from the same recorded number).
   */
  failedNow: string[];
  /** The verdict: `failedNow` is empty. The eligibility every page should count. */
  eligibleNow: boolean;
  /**
   * The verdict: this trial's deflated Sharpe re-evaluated at `gate.dsrN`, or null when it
   * cannot be — the 54 P7a seed rows have no recorded DSR. Null is a **missed** luck check, not
   * an excused one: the engine puts the luck label in `failedNow` for exactly those rows.
   */
  dsrNow: number | null;
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
