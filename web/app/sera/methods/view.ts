// Pure helpers for /sera/methods and /sera/methods/[id]. No data access: the pages feed them.
// Relative imports only, because vitest runs without the @/ alias.
// Pass/miss comes from derive.conditionOk (the engine's `failed` list), and thresholds come from
// snapshot.gate. Nothing here re-judges a trial (invariant 5).
import {
  Archive, Brain, Code, GitFork, GraduationCap, Newspaper, type LucideIcon,
} from 'lucide-react';
import { pct } from '../../../lib/format';
import {
  bestVariant, CONDITION_KEYS, CONDITION_LABEL, conditionOk, conditionsPassed, excessCagr, misses, trialsByMethod,
  type ConditionKey,
} from '../../../lib/sera/derive';
import type { Gate, LabMethod, LabTrial, Point } from '../../../lib/sera/types';

/* ---- List filter --------------------------------------------------------------------------- */

export const SHOWS = ['all', 'lab', 'historical', 'alive'] as const;
export type Show = (typeof SHOWS)[number];

/** `?show=` value -> a known filter; anything else is 'all'. */
export function parseShow(v: string | string[] | undefined): Show {
  const s = Array.isArray(v) ? v[0] : v;
  return (SHOWS as readonly string[]).includes(s ?? '') ? (s as Show) : 'all';
}

export const showHref = (v: Show): string => (v === 'all' ? '/sera/methods' : `/sera/methods?show=${v}`);

/** Statuses that mean a method is still in the running. */
export const ALIVE_STATUSES: readonly LabMethod['status'][] = ['dev-eligible', 'promoted', 'test-passed', 'paper'];

/** Alive: still in the running, or its best variant misses at most one hurdle. */
export function isAlive(m: LabMethod, best: LabTrial | null): boolean {
  return ALIVE_STATUSES.includes(m.status) || (best !== null && misses(best).length <= 1);
}

const byIdAsc = (a: LabMethod, b: LabMethod) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);

/** Lab methods first, newest id first (ids are zero-padded, M0001…), then historical H-* by id. */
export function sortMethods(methods: LabMethod[]): LabMethod[] {
  const labOnes = methods.filter(m => !m.historical).sort((a, b) => byIdAsc(b, a));
  const hist = methods.filter(m => m.historical).sort(byIdAsc);
  return [...labOnes, ...hist];
}

export type MethodRow = {
  method: LabMethod;
  best: LabTrial | null;
  /** Number of trials recorded for this method (all windows). */
  tries: number;
  /** Hurdles the best variant cleared (0..6), or null when it was never run. */
  passed: number | null;
  alive: boolean;
};

export function methodRows(methods: LabMethod[], trials: LabTrial[]): MethodRow[] {
  const by = trialsByMethod(trials);
  return sortMethods(methods).map(method => {
    const own = by.get(method.id) ?? [];
    const best = bestVariant(own);
    return {
      method,
      best,
      tries: own.length,
      passed: best ? conditionsPassed(best) : null,
      alive: isAlive(method, best),
    };
  });
}

export function matchesShow(r: MethodRow, show: Show): boolean {
  switch (show) {
    case 'all': return true;
    case 'lab': return !r.method.historical;
    case 'historical': return r.method.historical;
    case 'alive': return r.alive;
  }
}

export const filterRows = (rows: MethodRow[], show: Show): MethodRow[] => rows.filter(r => matchesShow(r, show));

export function showCounts(rows: MethodRow[]): Record<Show, number> {
  return {
    all: rows.length,
    lab: rows.filter(r => matchesShow(r, 'lab')).length,
    historical: rows.filter(r => matchesShow(r, 'historical')).length,
    alive: rows.filter(r => matchesShow(r, 'alive')).length,
  };
}

/* ---- Sources ------------------------------------------------------------------------------- */

const URL_RE = /https?:\/\/[^\s<>"')]+/;
const DOI_RE = /\b(10\.\d{4,9}\/[^\s<>"',;)]+)/;
const trimEnd = (s: string) => s.replace(/[.,;:]+$/, '');

/** A link for a method's source when its reference holds a URL or a DOI; otherwise null. */
export function sourceHref(ref: string): string | null {
  const url = ref.match(URL_RE);
  if (url) return trimEnd(url[0]);
  const doi = ref.match(DOI_RE);
  if (doi) return `https://doi.org/${trimEnd(doi[1])}`;
  return null;
}

export const SOURCE_ICON: Record<LabMethod['sourceKind'], LucideIcon> = {
  paper: GraduationCap,
  blog: Newspaper,
  github: Code,
  knowledge: Brain,
  variation: GitFork,
  seed: Archive,
};

/* ---- Formatting ---------------------------------------------------------------------------- */

const MINUS = '−';
const INT = new Intl.NumberFormat('en-US');
const LONG = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', year: 'numeric', month: 'short', day: 'numeric' });

/** 0.076 -> '7.6%', -0.02 -> '−2.0%', null -> '—'. */
export const pct1 = (v: number | null): string => (v === null ? '—' : (v < 0 ? MINUS : '') + pct(v, 1));
/** 0.076 -> '+7.6%', -0.02 -> '−2.0%', null -> '—'. */
export const signed1 = (v: number | null): string => (v === null ? '—' : (v < 0 ? MINUS : '+') + pct(v, 1));
/** 2.271 -> '2.27', null -> '—'. */
export const fixed = (v: number | null, digits = 2): string =>
  v === null ? '—' : (v < 0 ? MINUS : '') + Math.abs(v).toFixed(digits);
/** Profit factor; '∞' when the variant never lost. */
export const pfText = (t: LabTrial): string => (t.pfInfinite ? '∞' : fixed(t.profitFactor, 2));
export const count = (v: number): string => INT.format(v);
/** Any ISO date or timestamp -> 'Oct 4, 2026' (the date as written, no timezone shift). */
export const longDate = (iso: string): string => {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : LONG.format(d);
};
/** '1996-01-03'..'2015-10-16' -> '1996–2015'. */
export const windowText = (t: LabTrial): string => `${t.start.slice(0, 4)}–${t.end.slice(0, 4)}`;

/* ---- The six hurdles ----------------------------------------------------------------------- */

/** true = cleared, false = missed, null = not measured (derive.conditionOk). */
export type Mark = { key: ConditionKey; label: string; ok: boolean | null };

/** The six hurdles of one trial, in display order. */
export const marks = (t: LabTrial): Mark[] =>
  CONDITION_KEYS.map(key => ({ key, label: CONDITION_LABEL[key], ok: conditionOk(t, key) }));

/** 'Beats SPY: cleared' / 'missed' / 'not measured'. */
export const markLabel = (m: Mark): string =>
  `${m.label}: ${m.ok === null ? 'not measured' : m.ok ? 'cleared' : 'missed'}`;

/** One plain sentence per hurdle, with its threshold read from the gate. */
export function conditionTip(key: ConditionKey, gate: Gate): string {
  switch (key) {
    case 'spy': return 'Grew faster a year than holding SPY with dividends reinvested';
    case 'drawdown': return `Never fell more than ${pct(gate.maxDrawdown, 0)} from a peak`;
    case 'pf': return `Money won on winners is at least ${gate.minProfitFactor}× the money lost on losers`;
    case 'trades': return `At least ${count(gate.minTrades)} trades, so the result is not a handful of lucky bets`;
    case 'owner': return 'Needs no setting that only the owner can decide';
    case 'dsr': return `A luck-adjusted score of at least ${gate.dsrMin}, counting every try the lab has made`;
  }
}

/** 'Beats SPY: no (7.6% vs 7.9% a year).' and so on, one per hurdle. */
export function conditionSentence(key: ConditionKey, ok: boolean | null, t: LabTrial, gate: Gate): string {
  const label = CONDITION_LABEL[key];
  if (ok === null) return `${label}: not measured.`;
  const yn = ok ? 'yes' : 'no';
  switch (key) {
    case 'spy':
      return `${label}: ${yn} (${pct1(t.cagr)} vs ${pct1(t.spyTrCagr)} a year).`;
    case 'drawdown':
      return `${label}: ${yn} (${pct1(t.maxDrawdown)} ${ok ? '≤' : '>'} ${pct(gate.maxDrawdown, 0)}).`;
    case 'pf':
      return `${label}: ${yn} (${pfText(t)} ${ok ? '≥' : '<'} ${gate.minProfitFactor}).`;
    case 'trades':
      return `${label}: ${yn} (${count(t.trades)} ${ok ? '≥' : '<'} ${count(gate.minTrades)}).`;
    case 'owner':
      return ok ? `${label}: yes (none needed).` : `${label}: no (needs a setting only the owner can decide).`;
    case 'dsr':
      return `${label}: ${yn} (${fixed(t.dsr, 2)} ${ok ? '≥' : '<'} ${gate.dsrMin}, after ${count(t.nTrialsAtRun)} tries).`;
  }
}

export type Worked = {
  headline: string;
  lines: { key: ConditionKey; ok: boolean | null; text: string }[];
  /** Every line joined: the one-paragraph summary. */
  sentence: string;
};

/** The plain 'Did it work?' answer for a method's best variant. */
export function workedSummary(best: LabTrial, gate: Gate): Worked {
  const lines = marks(best).map(m => ({ key: m.key, ok: m.ok, text: conditionSentence(m.key, m.ok, best, gate) }));
  const passed = conditionsPassed(best);
  const span = windowText(best);
  const headline = passed === CONDITION_KEYS.length
    ? `Yes. Its best variant, ${best.candidateId}, cleared all six hurdles on ${span} data.`
    : `Not yet. Its best variant, ${best.candidateId}, cleared ${passed} of 6 hurdles on ${span} data.`;
  return { headline, lines, sentence: lines.map(l => l.text).join(' ') };
}

/* ---- Chart shaping ------------------------------------------------------------------------- */
// Time charts pass ISO-dated points straight to Phase 3's LineChart (date mode, year ticks), so
// no date-to-number conversion lives here.

/** The y-axis label for growth of 1: 1.5 -> '1.5×', 12 -> '12×'. */
export const growthFmt = (v: number): string => `${v < 10 ? v.toFixed(1) : v.toFixed(0)}×`;

export const BEST_COLOR = 'var(--coral)';
export const SPY_COLOR = 'var(--ink-3)';
/** SPY is dotted, as on the Leaderboard (Phase 3 colour conventions). */
export const SPY_DASH = '1 5';
export const LINE_COLORS = ['var(--line-b)', 'var(--line-c)', 'var(--ink-2)', 'var(--pos)', 'var(--ink)'] as const;

/** One growth-of-1 line; structurally a Phase 3 `LineSeries` (ISO-dated points). */
export type CurveLine = { id: string; label: string; points: Point[]; color: string; width: number; dash?: string };

/**
 * One line per variant, the best one last (drawn on top) in coral, then SPY with dividends,
 * dotted. `spy` is derive.spyForWindow(best, lab.benchmark).
 */
export function growthLines(variants: LabTrial[], best: LabTrial | null, spy: Point[]): CurveLine[] {
  const rest = variants.filter(t => !best || t.n !== best.n);
  const lines: CurveLine[] = rest.map((t, i) => ({
    id: t.candidateId, label: t.candidateId, points: t.curve,
    color: LINE_COLORS[i % LINE_COLORS.length], width: 1.5,
  }));
  if (best) {
    lines.push({
      id: best.candidateId, label: `${best.candidateId} (best)`, points: best.curve,
      color: BEST_COLOR, width: 2.5,
    });
  }
  if (spy.length) {
    lines.push({ id: 'SPY', label: 'SPY with dividends', points: spy, color: SPY_COLOR, width: 1.75, dash: SPY_DASH });
  }
  return lines;
}

export type YearRet = { year: number; ret: number };

/** Calendar years present in both series, oldest first. */
export function yearPairs(method: YearRet[], spy: YearRet[]): { year: number; method: number; spy: number }[] {
  const s = new Map(spy.map(r => [r.year, r.ret]));
  return method
    .filter(r => s.has(r.year))
    .map(r => ({ year: r.year, method: r.ret, spy: s.get(r.year) as number }))
    .sort((a, b) => a.year - b.year);
}

export type HurdlePoint = { id: string; x: number; y: number; own: boolean; href: string; tip: string };

/**
 * Every dev trial as (max drawdown, CAGR minus SPY's). This method's variants come last so
 * they draw on top. Trials missing either number are left out.
 */
export function hurdlePoints(all: LabTrial[], methodId: string): HurdlePoint[] {
  const pts: HurdlePoint[] = [];
  for (const t of all) {
    if (t.window !== 'dev' || t.maxDrawdown === null) continue;
    const y = excessCagr(t);
    if (y === null) continue;
    pts.push({
      id: `${t.n}`,
      x: t.maxDrawdown,
      y,
      own: t.methodId === methodId,
      href: `/sera/methods/${t.methodId}`,
      tip: `${t.candidateId}: ${signed1(y)} a year vs SPY, worst fall ${pct1(t.maxDrawdown)}`,
    });
  }
  return [...pts.filter(p => !p.own), ...pts.filter(p => p.own)];
}

/* ---- Text ---------------------------------------------------------------------------------- */

/** What to say instead of charts for a method with no trials. */
export function untestedNote(m: LabMethod): string {
  switch (m.status) {
    case 'idea':
      return 'Not tested yet. Sera wrote the idea and its likely failure down first; it runs when its turn in the queue comes.';
    case 'registered':
      return 'Registered with its exact rules, not run yet.';
    case 'blocked-data':
      return m.blockedOn
        ? `Not tested: it needs data the lab does not have yet (${m.blockedOn}).`
        : 'Not tested: it needs data the lab does not have yet.';
    default:
      return 'There are no recorded test runs for this method.';
  }
}

/** The full technical record of one trial, as label/value rows. */
export function techRows(t: LabTrial): [string, string][] {
  return [
    ['Trial number', `#${t.n}`],
    ['Window', `${t.window === 'dev' ? 'Development' : 'Test'}, ${t.start} → ${t.end}`],
    ['Trading rules', t.rulesId],
    ['Allocator', t.allocatorId],
    ['Code version (git)', t.gitSha || '—'],
    ['Run at', t.runAt],
    ['Tries counted when run (N)', count(t.nTrialsAtRun)],
    ['Time in the market', pct1(t.exposure)],
    ['Turnover', fixed(t.turnover, 2)],
    ['Worst year', t.worstYear === null ? '—' : `${t.worstYear} (${signed1(t.worstYearReturn)})`],
    ['Failed', t.failed.length ? t.failed.join('; ') : 'nothing: eligible'],
  ];
}
