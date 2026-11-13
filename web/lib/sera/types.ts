/** The lab snapshot contract: `web/data/lab.json`, written by `python -m seer_engine lab export-json`. */

export type LabSnapshot = {
  /**
   * 2 added the derived verdict to every trial (`failedNow` / `eligibleNow` / `dsrNow`);
   * 3 added `paper`, which names the lab method behind each roster entry;
   * 4 added `luckGated`, which says whether the luck hurdle applies to a trial at all;
   * 5 added `mwr` / `spyTrMwr`, what a funded trial's money actually earned;
   * 6 added the journal's version chain (`supersedes` / `docKey` / `version` / `supersededBy`)
   *   and split the journal count: `summary.insights` now counts documents, not rows;
   * 7 added `books` and `summary.testBooks` — the buy signal and the spent looks collapsed from
   *   method ids to distinct strategies, because a method id is not a strategy;
   * 8 added each trial's `role` and `yardstick` (its random-twin reading) and the gate's
   *   `yardstickMin` / `yardstickDraws` — the seventh condition, and which arms are comparison books;
   * 9 added `panel` — stage one of the lab: every signal measured on the stock-by-month panel,
   *   with its verdict worked out at export time.
   */
  version: 9;
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
    /** The random-twin bar (`lab.store.YARDSTICK_MIN_PERCENTILE`): the share of look-alikes a dev arm must out-earn. */
    yardstickMin: number;
    /** How many random look-alike books each arm is measured against (`lab.yardstick.DRAWS`). */
    yardstickDraws: number;
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
    /**
     * Journal **documents**: insight rows that nothing supersedes. A re-run that supersedes its
     * own previous note leaves this number where it was. Counted rows until snapshot 5.
     */
    insights: number;
    /** Journal rows, every version of every document. `insights` is the one to show a reader. */
    insightRows: number;
    /**
     * How many **distinct books** those `testLooks` bought — never how many looks were spent.
     * Four are spent and they bought two: M0021, M0022 and M0029 are one strategy under three
     * names, so the lab's out-of-sample record is 0-for-2 and three of the four looks bought
     * nearly the same information. `books.testLooks` is the same fact with the names in it.
     */
    testBooks: number;
    byStatus: Record<string, number>;
  };
  benchmark: { spyTr: [string, number][]; spyPrice: [string, number][] };
  methods: LabMethod[];
  trials: LabTrial[];
  insights: LabInsight[];
  ideasSeen: LabSeen[];
  /** Where each paper roster entry came from in the lab (`paper.roster.LAB_PROVENANCE`). */
  paper: LabPaper[];
  /**
   * One entry per distinct strategy, for the two places a method id has been standing in for one:
   * `firing` is what the buy signal says is worth paying for survivorship-free price history, and
   * `testLooks` is what the spent looks actually bought. Written by `lab/firings.py`, which reads
   * the declared parent of each method and confirms it against the recorded curves.
   */
  books: { firing: LabBook[]; testLooks: LabBook[] };
  /**
   * Stage one of the lab (snapshot 9): every stock-picking idea measured on the stock-by-month
   * panel, best controlled slope first, each with its verdict. Empty until a panel is recorded.
   */
  panel: LabPanel;
};

/**
 * One strategy, and every method id that turned out to be it.
 *
 * `lead` is the method the row is shown under — the one the others were derived from. `others`
 * are the same book under another name. `why` says of each how that is known, as a sentence with
 * `{lead}` still in it: substitute the **lead method's name**, never its id, because this text is
 * read by the owner. `bookText` in `derive.ts` is the one place that substitution happens.
 */
export type LabBook = { lead: string; others: string[]; why: Record<string, string> };

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
  /**
   * The arm's registered role (`lab.store.role_of_trial`), or null when none is recorded — every
   * arm the committed lab held when snapshot 8 shipped. `control` is a comparison book: built to be
   * beaten, never a candidate. Read it through `derive.isComparisonBook`, which also honours the
   * engine's own label for a control.
   */
  role: ArmRole | null;
  /**
   * The arm's latest random-twin reading (`lab.store.yardstick_of`), or null when it has none.
   * A reading is a measurement, not a verdict: whether the arm clears is the engine's call, made in
   * `failedNow`, and `derive.twinsState` is the one place the two are combined. Null is "not
   * measured", never a pass.
   */
  yardstick: LabYardstick | null;
  curve: [string, number][];
};

/**
 * One journal row. Rows are linked into **documents** by `supersedes`: a re-run of the command
 * that wrote a note appends a new row pointing at the old one rather than a sibling, and
 * `/sera/journal` renders the chain as one document labelled with its version.
 *
 * The store is append-only and stays that way — superseding *adds* a row, it never rewrites one.
 * `version` and `supersededBy` are derived by the engine at export time (`store._insight_chains`)
 * so that nothing here has to walk a linked list: show rows with `supersededBy === null`, and
 * reach the history through `supersedes`.
 */
export type LabInsight = {
  id: number;
  kind: 'observation' | 'hypothesis' | 'data-wish' | 'feature-wish' | 'risk' | 'synthesis';
  title: string;
  body: string;
  methodId: string | null;
  added: string;
  /** The row this one replaces, or null when it starts a document. Always a lower `id`. */
  supersedes: number | null;
  /**
   * The writer-computed identity of the document this row is a version of
   * (`real-costs:M0260-M-G3`, `prereg:M0022`). Null on rows written by hand and on every row
   * written before snapshot 6. Never a display string — it is a key.
   */
  docKey: string | null;
  /** Depth in the chain: 1 for a row that supersedes nothing, 2 for the row that replaced it. */
  version: number;
  /** The row that replaced this one, or null when this row is the head — the current version. */
  supersededBy: number | null;
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

/** An arm's registered role (`lab.control_shape.ROLES`). `control` is a comparison book. */
export type ArmRole = 'control' | 'dose' | 'idea' | 'treatment';

/** How a random-twin measurement came out (`lab.yardstick.STATUS_*`). */
export type YardstickStatus = 'measured' | 'not-applicable' | 'unmatched';

/** One random-twin reading as the engine publishes it (`store._snapshot_yardstick`). */
export type LabYardstick = {
  status: YardstickStatus;
  /** Share of the look-alikes the arm out-earned (ties count against it); null when none were drawn. */
  percentile: number | null;
  /** How many look-alikes were drawn: 0 or null for a book that only holds funds. */
  draws: number | null;
  /** How many of them the arm out-earned. */
  beaten: number | null;
  /** The arm's own rate: what the money earned on a funded run, yearly growth otherwise. */
  armRate: number | null;
  /** The middle look-alike's rate, on the same measure. */
  medianRate: number | null;
  /** The look-alikes' median trade count over the arm's own. */
  tradeRatio: number | null;
};

/** Mirrors `lab.control_shape.ROLES`; `engine/tests/test_lab_gate_wording.py` pins the two. */
export const ARM_ROLES = ['control', 'dose', 'idea', 'treatment'] as const satisfies readonly ArmRole[];

/** Mirrors `lab.yardstick.STATUS_*`; pinned by the same engine test. */
export const YARDSTICK_STATUSES = ['measured', 'not-applicable', 'unmatched'] as const satisfies readonly YardstickStatus[];

/** What a panel row is (`lab.store.PANEL_KINDS`): a registered signal, or a replay of an arm the lab already ran. */
export type PanelKind = 'signal' | 'replay';

/** Mirrors `lab.store.PANEL_KINDS`; pinned by `engine/tests/test_lab_gate_wording.py`. */
export const PANEL_KINDS = ['signal', 'replay'] as const satisfies readonly PanelKind[];

/**
 * One era of one panel reading (`store._snapshot_panel_era`). Every rate is a fraction, not a
 * percentage. `ic` / `icT` are null for a replay: an arm's picks are a set with no score to rank.
 */
export type LabPanelEra = {
  /** Months measured. */
  months: number;
  /** Mean monthly rank correlation between the score and next month's return. */
  ic: number | null;
  icT: number | null;
  /** The top bucket's return over the whole pool's, annualised. */
  spread: number;
  spreadT: number;
  /**
   * Next month's return per 1 sd of score (or per pick, for a replay) once momentum, beta, size and
   * volatility are allowed for. MONTHLY, unlike `spread`: a yearly figure is `slope * 12`, and the
   * two are never shown as one unit.
   */
  slope: number;
  slopeT: number;
  /** Mean share of the top bucket replaced each month. */
  turnover: number;
};

/** One store's readings by era; an era with no months is null. `recent` is 2009 to 2015. */
export type LabPanelStore = {
  all: LabPanelEra | null;
  pre2009: LabPanelEra | null;
  recent: LabPanelEra | null;
};

/** One recorded panel and its verdict (`store._snapshot_panel`, `lab.panel_verdict.published`). */
export type LabPanelSignal = {
  /** `S0001` for a signal; the arm's own id for a replay. Never shown to the owner. */
  id: string;
  kind: PanelKind;
  /** What it ranks on, in plain words. */
  name: string;
  family: string;
  /** The method a replay re-reads; null for a signal. */
  methodId: string | null;
  /** Whether it clears stage one. Never true for a twin. */
  clears: boolean;
  /** Its false-discovery q-value across every distinct pick set; null when not measured on the current history. */
  q: number | null;
  /** Each condition it missed, as a plain sentence written by the engine; empty exactly when it clears. */
  reasons: string[];
  /** The earlier panel that picks exactly the same stocks every month, or null. */
  twinOf: string | null;
  /** On the current dev price history; null when not measured there. */
  dev: LabPanelStore | null;
  /** With the companies that later disappeared put back; null when not measured that way. */
  survivorship: LabPanelStore | null;
};

/** The panel block: the rule, the false-discovery rate it is judged at, and every recorded panel. */
export type LabPanel = { rule: string; fdr: number; signals: LabPanelSignal[] };
