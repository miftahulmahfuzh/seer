// Pure helpers for /sera/how. No data access; page.tsx feeds the snapshot (structurally narrowed).
import { monthYear, type Era, type PipelineStage } from '../../../components/sera/diagrams/geometry';
import { CONDITION_KEYS, type ConditionKey } from '../../../lib/sera/derive';
import { CONDITION_TERM, type GlossaryKey } from '../../../lib/sera/glossary';
import type { Gate, LabMethod, LabSnapshot, LabTrial } from '../../../lib/sera/types';

/** The parts of the snapshot this page reads; LabSnapshot satisfies it. */
export type HowInput = {
  asOf: string;
  gate: Gate;
  data: LabSnapshot['data'];
  summary: Pick<LabSnapshot['summary'], 'devTrials' | 'testLooks'>;
  methods: readonly Pick<LabMethod, 'status' | 'historical' | 'updated'>[];
  trials: readonly Pick<LabTrial, 'window' | 'eligible'>[];
};

/**
 * Design §1's paper bar before real money: at least 3 months and 100 trades on paper.
 * Not in snapshot.gate (the lab never reaches paper by itself). See the Phase 6 handoff to Phase 1.
 */
export const PAPER_MONTHS = 3;
export const PAPER_TRADES = 100;

/** The two bear markets inside the dev window (S&P 500 peak to trough). */
export const BEARS: Era[] = [
  { start: '2000-03-24', end: '2002-10-09', label: 'Dot-com crash', years: '2000–02, about −49%' },
  { start: '2007-10-09', end: '2009-03-09', label: 'Financial crisis', years: '2008–09, about −57%' },
];

const year = (iso: string) => iso.slice(0, 4);
const INT = new Intl.NumberFormat('en-US');
export const count = (n: number) => INT.format(n);
const plural = (n: number, one: string, many: string) => `${count(n)} ${n === 1 ? one : many}`;
const num = (v: number) => String(Number(v.toFixed(4)));

/** 0.15 -> '15%', 0.125 -> '12.5%' */
export const pctLabel = (v: number) => `${Number((v * 100).toFixed(1))}%`;

export type StageCounts = {
  ideas: number;
  registered: number;
  devTrials: number;
  eligible: number;
  testLooks: number;
  paper: number;
};

const NOT_REGISTERED = new Set<LabMethod['status']>(['idea', 'blocked-data']);

export function stageCounts(snap: HowInput): StageCounts {
  return {
    ideas: snap.methods.filter(m => m.status === 'idea').length,
    registered: snap.methods.filter(m => !m.historical && !NOT_REGISTERED.has(m.status)).length,
    devTrials: snap.summary.devTrials,
    eligible: snap.trials.filter(t => t.window === 'dev' && t.eligible).length,
    testLooks: snap.summary.testLooks,
    paper: snap.methods.filter(m => m.status === 'paper').length,
  };
}

export function pipelineStages(snap: HowInput): PipelineStage[] {
  const g = snap.gate;
  const c = stageCounts(snap);
  return [
    {
      key: 'idea',
      title: ['Idea'],
      detail: ['A paper, a blog,', 'GitHub, a known', 'effect or a tweak'],
      count: `${count(c.ideas)} waiting`,
      countTip: 'Methods written down but not run yet',
      fails: false,
    },
    {
      key: 'registered',
      title: ['Written down', 'before testing'],
      detail: ['Committed to git', 'before any result', 'exists'],
      count: plural(c.registered, 'method', 'methods'),
      countTip: 'Lab methods whose plan was committed before their first run',
      fails: false,
    },
    {
      key: 'dev',
      title: ['Tested on', `${year(g.devStart)}–${year(g.devEnd)}`],
      detail: ['Practice years.', 'Every variant run', 'is counted'],
      count: plural(c.devTrials, 'try', 'tries'),
      countTip: `N = ${count(c.devTrials)}: every try on the practice years, the early Seer research included`,
      fails: true,
    },
    {
      key: 'hurdles',
      title: ['Five hurdles', '+ luck check'],
      detail: [
        'Beat SPY + dividends',
        `Worst fall ≤ ${pctLabel(g.maxDrawdown)}`,
        `PF ≥ ${num(g.minProfitFactor)} · ${count(g.minTrades)}+ trades`,
        'No owner inputs',
        `Luck check ≥ ${num(g.dsrMin)}`,
      ],
      count: `${count(c.eligible)} pass`,
      countTip: `${count(c.eligible)} of ${count(c.devTrials)} tries cleared all six at once`,
      fails: true,
      weight: 1.35,
    },
    {
      key: 'test',
      title: ['One look at', `${year(g.testStart)}–today`],
      detail: ['Years never used', 'to build anything.', 'One look, final'],
      count: `${plural(c.testLooks, 'look', 'looks')} used`,
      countTip: c.testLooks === 0 ? 'The exam years are untouched' : `${count(c.testLooks)} one-time looks used so far`,
      fails: true,
    },
    {
      key: 'paper',
      title: ['Paper trading'],
      detail: [`At least ${PAPER_MONTHS} months`, `and ${PAPER_TRADES} trades,`, 'no real money'],
      count: `${count(c.paper)} on paper`,
      countTip: 'Lab methods trading with pretend money now',
      fails: true,
    },
    {
      key: 'real',
      title: ['Real money'],
      detail: ['Only when every', 'design §1 rule is', 'met and the owner', 'says yes'],
      count: 'None yet',
      countTip: 'Seer is paper-only: nothing trades real money',
      fails: false,
      final: true,
    },
  ];
}

export function pipelineLabel(stages: PipelineStage[]): string {
  const path = stages.map(st => `${st.title.join(' ')} (${st.count})`).join(', then ');
  return `The path a method takes: ${path}. A fail at any test is written in the journal and the lab moves to the next idea.`;
}

export type WindowsModel = {
  start: string;
  devEnd: string;
  testStart: string;
  today: string;
  testNote: string;
  paperSince: string | null;
  bears: Era[];
  label: string;
};

export function windowsModel(snap: HowInput): WindowsModel {
  const g = snap.gate;
  const looks = snap.summary.testLooks;
  const testNote = looks === 0 ? 'untouched, no look used yet' : `${plural(looks, 'look', 'looks')} used`;
  const onPaper = snap.methods.filter(m => m.status === 'paper').map(m => m.updated.slice(0, 10)).sort();
  const paperSince = onPaper[0] ?? null;
  const paperText = paperSince ? `paper trading since ${monthYear(paperSince)}` : 'no lab method on paper yet';
  return {
    start: g.devStart,
    devEnd: g.devEnd,
    testStart: g.testStart,
    // asOf is '' for an empty lab (Phase 1); fall back to the test window's first day.
    today: (snap.asOf || g.testStart).slice(0, 10),
    testNote,
    paperSince,
    bears: BEARS,
    label:
      `Timeline from ${year(g.devStart)} to today. Practice years ${monthYear(g.devStart)} to ${monthYear(g.devEnd)}; ` +
      `exam years ${monthYear(g.testStart)} to today, ${testNote}; ${paperText}. ` +
      'Shaded: the 2000–02 and 2008–09 bear markets, both inside the practice years.',
  };
}

export type Hurdle = { key: ConditionKey; title: string; target: string; plain: string; term: GlossaryKey };

export function hurdles(gate: Gate, tries: number): Hurdle[] {
  const text: Record<ConditionKey, { title: string; target: string; plain: string }> = {
    spy: {
      title: 'Beat SPY with dividends',
      target: 'More than SPY total return',
      plain: 'Over the practice years it must end with more money than simply holding the S&P 500 fund with dividends reinvested. If it cannot beat doing nothing, it is not worth the effort.',
    },
    drawdown: {
      title: 'A small worst fall',
      target: `Max drawdown ≤ ${pctLabel(gate.maxDrawdown)}`,
      plain: `The deepest drop from a high point to a later low must stay within ${pctLabel(gate.maxDrawdown)}. Bigger falls are when people abandon a plan, usually at the worst moment.`,
    },
    pf: {
      title: 'Winners outweigh losers',
      target: `Profit factor ≥ ${num(gate.minProfitFactor)}`,
      plain: `Money made on winning trades must be at least ${num(gate.minProfitFactor)} times the money lost on losing ones, so there is room for costs and bad luck.`,
    },
    trades: {
      title: 'Enough trades',
      target: `At least ${count(gate.minTrades)} trades`,
      plain: `With fewer than ${count(gate.minTrades)} trades a result could rest on a handful of lucky bets.`,
    },
    owner: {
      title: 'No owner inputs',
      target: 'Nothing left for the owner to decide',
      plain: 'It may not lean on choices only the owner can make, such as using borrowed money or buying funds outside the approved list.',
    },
    dsr: {
      title: 'Not just luck',
      target: `Luck check ≥ ${num(gate.dsrMin)}`,
      plain: `Try enough ideas and one will look great by chance. The luck check discounts a result for every try ever made (N = ${count(tries)} so far), so the bar rises as the lab keeps searching.`,
    },
  };
  return CONDITION_KEYS.map(key => ({ key, term: CONDITION_TERM[key], ...text[key] }));
}

export type Rule = { key: 'counted' | 'first' | 'reroll' | 'append' | 'look' | 'bar'; title: string; body: string };

export function honestyRules(snap: Pick<HowInput, 'gate' | 'summary'>): Rule[] {
  const { devTrials, testLooks } = snap.summary;
  const g = snap.gate;
  return [
    {
      key: 'counted',
      title: 'Every try is counted',
      body: `${plural(devTrials, 'try', 'tries')} so far, failures included. The luck check uses all of them, so trying more never makes a winner easier to find.`,
    },
    {
      key: 'first',
      title: 'Written down before results',
      body: 'Each method’s idea, its variants and what could go wrong are committed to git before the first run. The lab refuses to run anything not committed.',
    },
    {
      key: 'reroll',
      title: 'No re-rolls',
      body: 'The exact same setup runs only once. Tweaking it and running again is a new try, and it is counted.',
    },
    {
      key: 'append',
      title: 'Nothing is ever erased',
      body: 'Results are never edited or deleted; the database itself blocks it. Analyses only grow, with a dated note each time.',
    },
    {
      key: 'look',
      title: 'One look at the exam years',
      body: `The ${year(g.testStart)}–today years are opened once per finalist, and a fail is final. Looks used so far: ${count(testLooks)}.`,
    },
    {
      key: 'bar',
      title: 'The bar never moves',
      body: 'The rules for real money (design §1) are fixed. The lab never lowers a hurdle to let a method through.',
    },
  ];
}

export type Fact = { key: string; title: string; body: string };

export function dataFacts(data: LabSnapshot['data'], gate: Gate): { has: Fact[]; lacks: Fact[] } {
  const versions = data.fingerprints.length;
  return {
    has: [
      {
        key: 'prices',
        title: `Daily prices since ${monthYear(data.storeStart)}`,
        body: `${count(data.barRows)} daily price rows for ${count(data.symbolsServed)} of the ${count(data.symbolsRequested)} stocks and funds asked for. The years after ${monthYear(gate.devEnd)} stay locked until a method earns its one look.`,
      },
      {
        key: 'dividends',
        title: 'Dividends',
        body: `${count(data.dividendRows)} dividend payments, so every return here includes dividends, and so does SPY’s.`,
      },
      {
        key: 'membership',
        title: `S&P 500 membership since ${monthYear(data.membershipStart)}`,
        body: 'Which companies were in the index on each day, so a test only picks from stocks it could have known about at the time.',
      },
      {
        key: 'fx',
        title: `Currency rates since ${monthYear(data.fxStart)}`,
        body: 'Daily exchange rates for converting results between currencies.',
      },
      {
        key: 'versions',
        title: versions === 1 ? 'One frozen copy of the data' : `${count(versions)} frozen data versions`,
        body: 'Every try records the exact data version it ran on, so any result can be repeated later.',
      },
    ],
    lacks: [
      {
        key: 'fundamentals',
        title: 'Company fundamentals',
        body: 'Earnings, sales, debt, book value. Without them the lab cannot test value or quality ideas.',
      },
      {
        key: 'delisted',
        title: 'Delisted stocks',
        body: 'Companies that went bust or were bought out. Without them the past looks rosier than it was.',
      },
      {
        key: 'intraday',
        title: 'Prices within the day',
        body: 'Only one price row per day, so ideas that trade on minutes or hours cannot be tested.',
      },
      {
        key: 'options',
        title: 'Options',
        body: 'No option prices, so nothing built on hedging or on what option traders expect.',
      },
      {
        key: 'sentiment',
        title: 'News and sentiment',
        body: 'No news, social media or analyst mood, so ideas about crowd behaviour have to wait.',
      },
    ],
  };
}
