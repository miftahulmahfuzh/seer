/** The lab snapshot contract: `web/data/lab.json`, written by `python -m seer_engine lab export-json`. */

export type LabSnapshot = {
  /**
   * 2 added the derived verdict to every trial (`failedNow` / `eligibleNow` / `dsrNow`);
   * 3 added `paper`, which names the lab method behind each roster entry;
   * 4 added `luckGated`, which says whether the luck hurdle applies to a trial at all;
   * 5 added `mwr` / `spyTrMwr`, what a funded trial's money actually earned.
   */
  version: 5;
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
   * **What the money actually earned**, on a trial that was fed deposits after it started: the
   * rate a savings account would have had to pay to turn the same deposits, paid in on the same
   * days, into the same final balance (`lab.store.FundingRow.mwr`).
   *
   * `null` for a trial that received no deposits — all 128 recorded ones — and that null is a
   * definite answer, "this run was not fed", not a missing value. For such a row `cagr` already
   * *is* the money-weighted return, and `totalReturn` is already a return.
   *
   * On a funded row neither of those is true any more, and the gap is not a rounding difference:
   * one measured funded run reports a `totalReturn` of 10.7821 (+1078%) beside an `mwr` of 0.0764
   * (7.6%), the rest being the owner's own deposits piling up. So **never put this number in a
   * column with an unfunded row's `totalReturn` or `cagr`** — they answer different questions and
   * differ by two orders of magnitude.
   */
  mwr: number | null;
  /**
   * The same measure for the **dollar-cost-averaged** SPY total-return curve: the identical money,
   * paid in on the identical days, put into SPY instead. The only like-for-like comparison a
   * funded trial has, and the pair `beats SPY TR` is decided on for such a row.
   *
   * Always null exactly when `mwr` is null, and read as a pair: the engine's `dev.beats_spy_tr`
   * falls back to the total-return comparison the moment either is missing, so a page showing one
   * alone would contradict the tick printed beside it. `derive.moneyWeighted` is that branch, and
   * is the only thing that should decide whether a row reads money-weighted.
   */
  spyTrMwr: number | null;
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
   * cannot be — the 54 P7a seed rows have no recorded DSR. On a `luckGated` row, null is a
   * **missed** luck check, not an excused one: the engine puts the luck label in `failedNow` for
   * exactly those rows. On a row that is not `luckGated` this is a measurement with no hurdle
   * attached, and must never be compared against `gate.dsrMin`.
   */
  dsrNow: number | null;
  /**
   * **Does the luck hurdle apply to this trial at all?** True for a development row, false for a
   * test-window look (`lab.store.luck_gated`). The web reads this; it must never re-derive it.
   *
   * A test look is one pre-registered confirmatory run, so there is no selection among results to
   * deflate and the engine applies the four owner thresholds and nothing else. `failedNow`
   * therefore has no luck label on such a row — which, read without this marker, is
   * indistinguishable from a cleared hurdle. That is how `M0021-B70-RAW` came to render a green
   * tick on a score of 0.513 against a published bar of 0.90.
   *
   * Three states, and the page must show three: `luckGated && conditionOk === true` (cleared),
   * `luckGated && conditionOk === false` (missed, possibly because `dsrNow` is null and nothing
   * could be scored), and `!luckGated` (does not apply).
   */
  luckGated: boolean;
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
