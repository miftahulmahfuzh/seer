/** Plain-language words for the /sera pages. One sentence each, and no thresholds (those come from the snapshot gate). */
import type { ConditionKey } from './derive';
import type { InsightKind, LabStatus, SourceKind } from './types';

export type GlossaryKey =
  | 'return'
  | 'cagr'
  | 'maxDrawdown'
  | 'profitFactor'
  | 'trades'
  | 'sharpe'
  | 'mar'
  | 'dsr'
  | 'tries'
  | 'exposure'
  | 'turnover'
  | 'devWindow'
  | 'testWindow'
  | 'paperTrading'
  | 'spyTr'
  | 'ownerInputs';

export type GlossaryEntry = { term: string; plain: string };

export const GLOSSARY: Record<GlossaryKey, GlossaryEntry> = {
  return: {
    term: 'Return',
    plain: 'How much the money grew or shrank over the whole test, as a share of what it started with.',
  },
  cagr: {
    term: 'CAGR',
    plain: 'The steady yearly growth rate that turns the starting money into the ending money, the "per year" return.',
  },
  maxDrawdown: {
    term: 'Max drawdown',
    plain: 'The deepest fall from a high point to a later low, the worst loss you would have had to sit through.',
  },
  profitFactor: {
    term: 'Profit factor',
    plain: 'Money made on winning trades divided by money lost on losing trades, so above 1 means the winners paid for the losers.',
  },
  trades: {
    term: 'Trades',
    plain: 'How many round trips (a buy and its later sell) the method made, where more trades make a fluke less likely.',
  },
  sharpe: {
    term: 'Sharpe',
    plain: 'Return per unit of bumpiness, where higher means the growth came with smaller swings along the way.',
  },
  mar: {
    term: 'MAR',
    plain: 'Yearly growth divided by the worst fall, one number for how much return you got for the pain you sat through.',
  },
  dsr: {
    term: 'Luck check (DSR)',
    plain:
      'The chance a result is real skill rather than the luckiest of many tries, after discounting ' +
      'for how many tries have been counted, against a bar that is the owner’s call on how much ' +
      'doubt is acceptable.',
  },
  tries: {
    term: 'N (tries)',
    plain:
      'Every test the lab has ever run, all kept on the record and all counted so the luck check ' +
      'can discount a winner found by trying many things, which means trying more raises the bar ' +
      'for everyone.',
  },
  exposure: {
    term: 'Exposure',
    plain: 'The share of the time the money was actually invested rather than sitting in cash.',
  },
  turnover: {
    term: 'Turnover',
    plain: 'How much of the portfolio was bought and sold in a typical year, where more turnover means more trading costs.',
  },
  devWindow: {
    term: 'Dev window',
    plain: 'The older stretch of history every idea is tested on while we are still searching and allowed to adjust.',
  },
  testWindow: {
    term: 'Test window',
    plain: 'The newer stretch of history, kept sealed, that a finalist gets exactly one look at to see if it holds up on data it never saw.',
  },
  paperTrading: {
    term: 'Paper trading',
    plain: 'Running the method live with pretend money for months to check it behaves like its backtest before any real money goes in.',
  },
  spyTr: {
    term: 'Total-return SPY',
    plain: 'The S&P 500 fund with its dividends reinvested, the do-nothing benchmark every method has to beat.',
  },
  ownerInputs: {
    term: 'Owner inputs',
    plain: 'Settings only the owner can decide, such as how much to risk, so a method that still needs them cannot go live as it is.',
  },
};

/** Display order for the glossary on the How it works page. */
export const GLOSSARY_ORDER: GlossaryKey[] = [
  'spyTr',
  'return',
  'cagr',
  'maxDrawdown',
  'profitFactor',
  'trades',
  'ownerInputs',
  'dsr',
  'tries',
  'mar',
  'sharpe',
  'exposure',
  'turnover',
  'devWindow',
  'testWindow',
  'paperTrading',
];

/** The glossary entry explaining each gate condition (for `data-tip` on a hurdle). */
export const CONDITION_TERM: Record<ConditionKey, GlossaryKey> = {
  spy: 'spyTr',
  drawdown: 'maxDrawdown',
  pf: 'profitFactor',
  trades: 'trades',
  owner: 'ownerInputs',
  dsr: 'dsr',
};

export type Tone = 'good' | 'bad' | 'wait' | 'neutral';

export const STATUS_LABEL: Record<LabStatus, { label: string; meaning: string; tone: Tone }> = {
  idea: { label: 'Idea', meaning: 'Written down, not tested yet.', tone: 'wait' },
  registered: { label: 'Registered', meaning: 'Its rules are locked in before the test runs.', tone: 'wait' },
  rejected: { label: 'Rejected', meaning: 'Tested on the older history and missed at least one hurdle.', tone: 'bad' },
  'dev-eligible': { label: 'Passed dev', meaning: 'Cleared every hurdle on the older history.', tone: 'good' },
  promoted: { label: 'Promoted', meaning: 'Chosen for its one look at the sealed newer history.', tone: 'good' },
  'test-passed': { label: 'Passed final test', meaning: 'Held up on the sealed newer history.', tone: 'good' },
  'test-failed': { label: 'Failed final test', meaning: 'Did not hold up on the sealed newer history.', tone: 'bad' },
  paper: { label: 'Paper trading', meaning: 'Running live with pretend money.', tone: 'good' },
  'blocked-data': { label: 'Blocked on data', meaning: 'Needs data the lab does not have yet.', tone: 'neutral' },
};

/** `heading` is the Journal section title; `label` names one entry. */
export const INSIGHT_KIND_LABEL: Record<InsightKind, { label: string; heading: string }> = {
  synthesis: { label: 'Batch summary', heading: 'Batch summaries' },
  observation: { label: 'Observation', heading: 'What we learned' },
  hypothesis: { label: 'Idea to test', heading: 'Ideas worth testing' },
  'data-wish': { label: 'Data wish', heading: 'Data we wish we had' },
  'feature-wish': { label: 'Feature wish', heading: 'Features to build' },
  risk: { label: 'Risk', heading: 'Risks we see' },
};

export const SOURCE_KIND_LABEL: Record<SourceKind, string> = {
  paper: 'Research paper',
  blog: 'Blog post',
  github: 'Code on GitHub',
  knowledge: 'Known technique',
  variation: 'Variation of an earlier method',
  seed: 'Earlier Seer research',
};
