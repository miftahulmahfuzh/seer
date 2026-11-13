// Pure helpers for /sera/methods and /sera/methods/[id]. No data access: the pages feed them.
// Relative imports only, because vitest runs without the @/ alias.
// Pass/miss comes from derive.conditionOk (the engine's `failedNow` verdict), and thresholds come
// from snapshot.gate — the two are resolved against each other at export time, so a tick and the
// target printed next to it always describe the same day. Nothing here re-judges a trial
// (invariant 5); `failed`, the run-date record, appears only in techRows, labelled as the record.
import {
  Archive, Brain, Code, GitFork, GraduationCap, Newspaper, type LucideIcon,
} from 'lucide-react';
import { pct } from '../../../lib/format';
import {
  bestVariant, CONDITION_KEYS, CONDITION_LABEL, CONTROL_LABEL, conditionOk, conditionsPassed, excessCagr,
  isComparisonBook, isYardstickLabel, misses, moneyWeighted, shareInWords, trialsByMethod, twinsState,
  twinsValue, type ConditionKey,
} from '../../../lib/sera/derive';
import type { ArmRole, Gate, LabMethod, LabTrial, Point } from '../../../lib/sera/types';

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
  /** Hurdles the best variant cleared (0..7), or null when it was never run. */
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

/** The N the method's MOST RECENT run was scored against, or null when it has never run.
 *
 * Deliberately the newest trial's N and not `Math.max` over them. Those agreed while N only ever
 * grew, and they stopped agreeing on 2026-10-08, when the luck policy moved from counting trial
 * rows to counting methods and N fell from 126 to 74. A book whose trials straddle that change --
 * which an amendment is the first thing able to produce, since it adds trials to a method that has
 * already run -- would otherwise advertise the largest N any of its trials ever faced rather than
 * the one it was last judged against. Measured 2026-10-12: M0030 carries trials at N = 126 (Oct 7)
 * and N = 74 (Oct 12), and `Math.max` showed 126 beside a lab whose hurdle is 74.
 */
export function nAtLastRun(trials: LabTrial[]): number | null {
  if (trials.length === 0) return null;
  return trials.reduce((newest, t) => (t.n > newest.n ? t : newest)).nTrialsAtRun;
}
/** Any ISO date or timestamp -> 'Oct 4, 2026' (the date as written, no timezone shift). */
export const longDate = (iso: string): string => {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : LONG.format(d);
};
/** '1996-01-03'..'2015-10-16' -> '1996–2015'. */
export const windowText = (t: LabTrial): string => `${t.start.slice(0, 4)}–${t.end.slice(0, 4)}`;

/* ---- Funded runs --------------------------------------------------------------------------- */
// A trial the lab fed deposits into is read differently from one it did not, and the difference
// is not cosmetic: on one measured funded run the engine reports a total return of +1078% beside
// an earned rate of 7.6%, almost all of the gap being the owner's own deposits piling up. So the
// earned rate gets a column of its own and never shares one with an unfunded row's return, and
// the two cells the deposits inflate are blanked rather than printed as if they meant something.

/** Does any trial on this page carry a money-weighted pair? Decides whether the column shows. */
export const anyMoneyWeighted = (trials: LabTrial[]): boolean => trials.some(t => moneyWeighted(t) !== null);

/** '+7.6%' for a funded trial's earned rate, '—' for one that received no deposits. */
export const earned = (t: LabTrial): string => {
  const m = moneyWeighted(t);
  return m === null ? '—' : signed1(m.mwr);
};

/** 'vs +7.1%' — the same deposits in SPY — or null when there is nothing to compare. */
export const earnedVs = (t: LabTrial): string | null => {
  const m = moneyWeighted(t);
  return m === null ? null : `vs ${signed1(m.spyTrMwr)}`;
};

/** Why a funded row's return and growth-a-year cells are blank. Everyday words, no jargon. */
export const DEPOSITS_TIP =
  'Money was added to this run every month, so these two count your own deposits as if they were ' +
  'gains. What the money actually earned is in the next column.';

/**
 * The children of a method that were **actually run on deposits**, ordered by id.
 *
 * `/redo-sera-experiments` mints a pre-registered variation twin rather than rewriting its parent:
 * the lab's rows are append-only, and deleting a method's trials to "redo" it would *lower* the
 * multiple-testing N and retroactively flatter every other method in the lab. So the honest redo
 * of a method is always a different method with a page of its own, and this is how the parent's
 * page finds it and brings the result back.
 *
 * The test is `moneyWeighted`, never `sourceKind === 'variation'`. 22 of the lab's 45 methods are
 * already variations and not one of them was fed, so keying off `sourceKind` would claim two dozen
 * redos that never happened.
 */
export function redoneOf(children: LabMethod[], trialsOf: (id: string) => LabTrial[]): Redone[] {
  const out: Redone[] = [];
  for (const method of children) {
    const trial = bestVariant(trialsOf(method.id));
    if (trial && moneyWeighted(trial) !== null) out.push({ method, trial });
  }
  return out.sort((a, b) => a.method.id.localeCompare(b.method.id));
}

/** A child method that is this one redone on real money, with the trial that says so. */
export type Redone = { method: LabMethod; trial: LabTrial };

/* ---- The seven hurdles --------------------------------------------------------------------- */

/**
 * true = cleared, false = missed, null = nothing to score here
 * (derive.conditionOk, which reads the engine's `failedNow`, `luckGated` and `yardstick`).
 *
 * `null` is the luck check on a test-window look, the random-twin check on a test look or on a
 * book that only holds funds, and the random-twin check on an arm nobody has measured yet. The
 * last one says so in `naText` ("not measured yet"), so a dashed mark is never read as an excused
 * hurdle when it is really a pending one. `detail` is the reading behind a random-twin mark
 * ("beat 187 of 200"), printed after the state wherever the mark is spelled out.
 */
export type Mark = { key: ConditionKey; label: string; ok: boolean | null; naText?: string; detail?: string };

/** The seven hurdles of one trial, in display order. */
export const marks = (t: LabTrial): Mark[] =>
  CONDITION_KEYS.map(key => {
    const mark: Mark = { key, label: CONDITION_LABEL[key], ok: conditionOk(t, key) };
    if (key !== 'yardstick') return mark;
    const state = twinsState(t);
    if (state === 'not-measured') return { ...mark, naText: 'not measured yet' };
    if (state === 'cleared' || state === 'missed' || state === 'unmatched') return { ...mark, detail: twinsValue(t) };
    return mark;
  });

/** 'Beats SPY: cleared' / 'missed' / 'not applicable' / 'not measured yet', plus any reading. */
export const markLabel = (m: Mark): string => {
  const state = m.ok === null ? (m.naText ?? 'not applicable') : m.ok ? 'cleared' : 'missed';
  return m.detail ? `${m.label}: ${state} (${m.detail})` : `${m.label}: ${state}`;
};

/** One plain sentence per hurdle, with its threshold read from the gate. */
export function conditionTip(key: ConditionKey, gate: Gate): string {
  switch (key) {
    case 'spy': return 'Grew faster a year than holding SPY with dividends reinvested';
    case 'drawdown': return `Never fell more than ${pct(gate.maxDrawdown, 0)} from a peak`;
    case 'pf': return `Money won on winners is at least ${gate.minProfitFactor}× the money lost on losers`;
    case 'trades': return `At least ${count(gate.minTrades)} trades, so the result is not a handful of lucky bets`;
    case 'owner': return 'Needs no setting that only the owner can decide';
    case 'dsr': return `A luck-adjusted score of at least ${fixed(gate.dsrMin, 2)}, discounted by all ${count(gate.dsrN)} tries counted so far (${gate.dsrNBasis})`;
    case 'yardstick': return `Earned more than at least ${shareInWords(gate.yardstickMin)} of ${count(gate.yardstickDraws)} random look-alike books: the same trading days and amounts, with every picked stock swapped for a random one of similar size`;
  }
}

/**
 * The random-twin sentence. Its own function because it has six things to say, not three, and
 * which one is decided by `twinsState` — the engine's verdict and its reading together — rather
 * than by the tick alone.
 */
export function twinsSentence(t: LabTrial, gate: Gate): string {
  const label = CONDITION_LABEL.yardstick;
  const bar = shareInWords(gate.yardstickMin);
  const y = t.yardstick;
  const beat = y !== null && y.beaten !== null && y.draws !== null
    ? `${count(y.beaten)} of ${count(y.draws)}`
    : null;
  switch (twinsState(t)) {
    case 'cleared':
      return beat === null
        ? `${label}: yes.`
        : `${label}: yes (it earned more than ${beat} random look-alike books, and the bar is ${bar}).`;
    case 'missed':
      return beat === null
        ? `${label}: no (not measured — a variant this recent cannot pass until it has been compared with random look-alike books).`
        : `${label}: no (it earned more than only ${beat} random look-alike books, short of ${bar}).`;
    case 'unmatched':
      return `${label}: no (its random look-alikes ended up trading too differently from it to be a fair comparison, and that never counts as a pass).`;
    case 'not-applicable':
      return `${label}: does not apply. It only holds funds, so there are no picked stocks to swap for random ones.`;
    case 'not-measured':
      return `${label}: not measured yet. It has not been compared with random look-alike books, so this is neither a pass nor a miss.`;
    case 'test-look':
      return `${label}: does not apply to a test run.`;
  }
}

/** 'Beats SPY: no (7.6% vs 7.9% a year).' and so on, one per hurdle. */
export function conditionSentence(key: ConditionKey, ok: boolean | null, t: LabTrial, gate: Gate): string {
  if (key === 'yardstick') return twinsSentence(t, gate);
  const label = CONDITION_LABEL[key];
  if (ok === null) {
    // Only the luck check reaches here, and only on a test look. Say which hurdle it is, say it
    // does not apply, and still show the number — it was measured, it is simply not a bar.
    return key === 'dsr'
      ? `${label}: does not apply. A test run is a single try booked in advance, so there is nothing to discount for luck${t.dsrNow === null ? '' : ` (it scored ${fixed(t.dsrNow, 3)})`}.`
      : `${label}: does not apply.`;
  }
  const yn = ok ? 'yes' : 'no';
  const money = moneyWeighted(t);
  switch (key) {
    case 'spy':
      // A funded run is judged on what its money earned, so that is what this sentence quotes.
      // Its `cagr` is not a yearly return once deposits keep arriving — it is the shape of a
      // curve that the deposits themselves lifted — and quoting it here would name a number the
      // engine did not decide the tick by.
      return money !== null
        ? `${label}: ${yn} (your money earned ${pct1(money.mwr)} a year, against ${pct1(money.spyTrMwr)} from putting the same deposits into SPY on the same days).`
        : `${label}: ${yn} (${pct1(t.cagr)} vs ${pct1(t.spyTrCagr)} a year).`;
    case 'drawdown':
      return `${label}: ${yn} (${pct1(t.maxDrawdown)} ${ok ? '≤' : '>'} ${pct(gate.maxDrawdown, 0)}).`;
    case 'pf':
      return `${label}: ${yn} (${pfText(t)} ${ok ? '≥' : '<'} ${gate.minProfitFactor}).`;
    case 'trades':
      return `${label}: ${yn} (${count(t.trades)} ${ok ? '≥' : '<'} ${count(gate.minTrades)}).`;
    case 'owner':
      return ok ? `${label}: yes (none needed).` : `${label}: no (needs a setting only the owner can decide).`;
    case 'dsr':
      // `dsrNow` at `gate.dsrN`, never the recorded pair: the bar is the bar *at that N*, and
      // quoting a score from one N against a bar from another is how this line once read
      // "no (0.912 < 0.90)". Null means the luck test could not be run, which is a miss.
      return t.dsrNow === null
        ? `${label}: no (not measured — the luck test cannot be scored for this trial, so it cannot pass it).`
        : `${label}: ${yn} (${fixed(t.dsrNow, 3)} ${ok ? '≥' : '<'} ${fixed(gate.dsrMin, 2)}, scored at N = ${count(gate.dsrN)}).`;
  }
}

/**
 * What follows the DSR number in the variants table: the N the score belongs to, or why there is
 * no bar beside it. Null when there is no score to annotate.
 *
 * `at N 126` beside a test look's number is a false statement — that score was never computed at
 * the gate's N and is not read against it — so the two cases carry different words.
 */
export const dsrNote = (t: LabTrial, gate: Gate): string | null =>
  t.dsrNow === null ? null : t.luckGated ? `at N ${count(gate.dsrN)}` : 'not a hurdle on a test run';

export type Worked = {
  headline: string;
  /** One per hurdle: its mark, and the sentence printed beside it. */
  lines: (Mark & { text: string })[];
  /** Every line joined: the one-paragraph summary. */
  sentence: string;
};

const NUMBER_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven'];

/**
 * The plain 'Did it work?' answer for a method's best variant.
 *
 * Hurdles with nothing to score are not hurdles it failed to clear, so they leave the count: a
 * test look is counted out of five, and an arm nobody has compared with its random look-alikes
 * out of six. That second case is a hurdle still ahead of it, not one behind it, so a "Yes" says
 * so in the same sentence rather than reading as "cleared everything".
 */
export function workedSummary(best: LabTrial, gate: Gate): Worked {
  const lines = marks(best).map(m => ({ ...m, text: conditionSentence(m.key, m.ok, best, gate) }));
  const passed = conditionsPassed(best);
  const applicable = lines.filter(l => l.ok !== null).length;
  const span = windowText(best);
  const pending = twinsState(best) === 'not-measured' ? '; it has not been compared with random look-alike books yet' : '';
  const headline = passed === applicable
    ? `Yes. Its best variant, ${best.candidateId}, cleared all ${NUMBER_WORDS[applicable] ?? count(applicable)} hurdles on ${span} data${pending}.`
    : `Not yet. Its best variant, ${best.candidateId}, cleared ${passed} of ${count(applicable)} hurdles on ${span} data.`;
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

const ROLE_TEXT: Record<ArmRole, string> = {
  idea: 'the idea itself',
  treatment: 'the idea itself',
  dose: 'the idea at a stronger or weaker setting',
  control: 'a comparison book, built to be beaten',
};

/** An arm's registered role in words, or 'not recorded'. */
export const roleText = (role: ArmRole | null): string => (role === null ? 'not recorded' : ROLE_TEXT[role]);

/** The random-twin reading for the technical record: the count, the arm's rate and the middle look-alike's. */
export function twinsRecord(t: LabTrial): string {
  const y = t.yardstick;
  switch (twinsState(t)) {
    case 'cleared':
    case 'missed':
      return y === null || y.beaten === null || y.draws === null
        ? 'not measured, and a variant this recent cannot pass without it'
        : `${twinsValue(t)}; it earned ${pct1(y.armRate)} a year, the middle look-alike ${pct1(y.medianRate)}`;
    case 'unmatched':
      return 'not comparable: its look-alikes traded too differently from it';
    case 'not-applicable':
      return 'does not apply: it only holds funds';
    case 'test-look':
      return 'does not apply to a test run';
    case 'not-measured':
      return 'not measured yet';
  }
}

/** The one-line state on a technical-record summary. A comparison book is not a missed idea. */
export const techStatus = (t: LabTrial): string =>
  isComparisonBook(t) ? 'comparison book' : t.failedNow.length ? `missed ${t.failedNow.length}` : 'eligible';

/**
 * One `failedNow` label as the owner reads it in a sentence ("Still misses: …" on the redone panel).
 *
 * Only the two labels this lab grew on 2026-11-14 are translated: the random-twin miss and the
 * control arm's label, which would otherwise print engine text ("beats 90% of random twins",
 * "not a control arm") on a page with no ids or code. Every older label is returned as it was;
 * rewording those is a separate change.
 */
export function missInWords(label: string, gate: Gate): string {
  if (isYardstickLabel(label)) return `beating ${shareInWords(gate.yardstickMin)} random look-alike books`;
  if (label === CONTROL_LABEL) return 'it is a comparison book, built to be beaten';
  return label;
}

/**
 * The full technical record of one trial, as label/value rows.
 *
 * `gate` is here for one row: "Missed by today's bars" goes through `missInWords`, because the
 * record sits on the page the owner reads and the two labels the lab grew on 2026-11-14 are
 * engine text, not words (plan invariant 8, and phase 5's exit criterion that no owner-facing
 * text prints either raw). Every older label prints as it always did.
 */
export function techRows(t: LabTrial, gate: Gate): [string, string][] {
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
    // Both, and labelled. The record names the bars of its own run date and never changes; the
    // verdict is the same row read against the bars in force now, which is what the page's ticks
    // show. They differ for every row recorded before the owner moved a bar on 2026-10-07.
    ['Luck score when run', t.dsr === null ? 'not measured' : `${fixed(t.dsr, 3)} at N = ${count(t.nTrialsAtRun)}`],
    // Published by the engine (`store.luck_gated`), not worked out here: the luck bar applies to
    // a development try, which is one of many results selected among, and not to a test run,
    // which is a single try booked in advance.
    ['Luck bar applies', t.luckGated ? 'yes' : 'no — a test run has nothing to discount for luck'],
    ['Missed when run', t.failed.length ? t.failed.join('; ') : 'nothing: eligible'],
    ['Missed by today’s bars', t.failedNow.length ? t.failedNow.map(f => missInWords(f, gate)).join('; ') : 'nothing: eligible'],
    // Snapshot 8. What the arm was registered as, and how it did against its random look-alikes.
    ['Kind of variant', roleText(t.role)],
    ['Random look-alikes', twinsRecord(t)],
    // Only for a run that was fed. An unfunded trial has nothing to say here and says nothing,
    // which is why these are appended rather than dashed: every recorded trial is unfunded, and a
    // row of em-dashes on all 128 of them would be noise standing in for a definite answer.
    ...(moneyWeighted(t)
      ? ([
        ['What the money earned', `${earned(t)} a year`],
        ['The same deposits in SPY', `${signed1(moneyWeighted(t)!.spyTrMwr)} a year`],
      ] as [string, string][])
      : []),
  ];
}
