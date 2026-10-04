> Adopted from `SERA_LAB_SITE_PLAN.md` phase 5. Source: `.workflows/plan/sera-lab-site/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: Methods list + method detail

**Plan set:** `SERA_LAB_SITE_PLAN.md`
**Analysis:** `20261004-211729-H54F_code_analyzer.md`
**Satisfies:** R1, R3, R4, R5, R7. Every method and every trial can be reached on a desktop page, with its charts and a plain-language analysis and opinion. R7 (cross-cutting): every method gets a page, and every trial's full technical record is on it.
**Depends on:** Phase 2 (data layer), Phase 3 (shell + chart kit). Phase 1 is reached through phase 2: `web/data/lab.json` must exist.
**Difficulty:** HARD
**Package:** `web/app/sera/methods`

---

## Goal

After this phase, `/sera/methods` lists every method in the lab snapshot: lab `M*` first, newest id first, then historical `H-*`. Each row shows status, family, source, the best variant's numbers against SPY, how many of the six hurdles it cleared (as six dots), and the verdict. An icon-only segmented filter switches between all, lab, historical and alive. `/sera/methods/[id]` gives every method a page with:

- the idea and what could go wrong
- a plain "did it work?" checklist
- a variants table with ✓/✗ for each condition
- four charts: growth of 1, drawdowns, year by year, and against the hurdles
- Sera's markdown analysis
- related insights
- the full technical record of each trial

Methods with no trials (idea, blocked, registered) render the idea and a plain note instead of charts.

## Assumed interfaces

### Phase 2: `web/lib/sera/*`, aligned to `phase-2.md` (read 21:30)

This plan uses these exact phase-2 names:

```ts
// types.ts
export type LabSnapshot; LabMethod; LabTrial; LabInsight; Gate (= LabSnapshot['gate']); Point (= [string, number]);
// lab.ts (relative import of ../../data/lab.json)
export const lab: LabSnapshot;
export const methodById: (id: string) => LabMethod | undefined;
export const trialsOf: (methodId: string) => LabTrial[];       // ordered by n
export const insightsOf: (methodId: string) => LabInsight[];
export const childrenOf: (methodId: string) => LabMethod[];
// derive.ts (relative imports only: '../format', './types')
export const CONDITION_KEYS: readonly ['spy','drawdown','pf','trades','owner','dsr']; export type ConditionKey;
export const CONDITION_LABEL: Record<ConditionKey, string>;    // 'Beats SPY', 'Max drawdown', 'Profit factor', 'Trade count', 'Owner inputs', 'Luck check'
export function conditionOk(t: LabTrial, key: ConditionKey): boolean | null;  // from t.failed; null = not measured
export function conditionsPassed(t: LabTrial): number;
export function misses(t: LabTrial): ConditionKey[];
export function excessCagr(t: LabTrial): number | null;
export function bestVariant(trials: LabTrial[]): LabTrial | null;   // dev trials first; null when none
export function trialsByMethod(trials: LabTrial[]): Map<string, LabTrial[]>;
export function spyForWindow(trial: LabTrial, benchmark: LabSnapshot['benchmark']): Point[];  // rebased 1.0, on the trial's curve dates
export function drawdownSeries(curve: Point[]): Point[];       // value / peak - 1 (≤ 0)
export function yearlyReturns(curve: Point[]): { year: number; ret: number }[];
// glossary.ts
export type GlossaryKey;   // keys used here: 'cagr','maxDrawdown','profitFactor','trades','dsr','mar','sharpe','return'
export const GLOSSARY: Record<GlossaryKey, { term: string; plain: string }>;   // fed to Term via the local T wrapper
export const STATUS_LABEL: Record<LabStatus, { label: string; meaning: string; tone: 'good'|'bad'|'wait'|'neutral' }>;
export const INSIGHT_KIND_LABEL: Record<InsightKind, { label: string; heading: string }>;
export const SOURCE_KIND_LABEL: Record<SourceKind, string>;
// markdown.ts
export function renderMarkdown(src: string): string;   // escape-first; # -> h3, ## -> h4, ### -> h5
```

`view.ts` imports `derive.ts` and `types.ts` by **relative** path, because vitest has no `@/` alias. Phase 2 already does the same.

### Phase 3: `web/components/sera/*` and `web/lib/sera/gate.ts`, aligned to `phase-3.md` (reconciled)

Phase 3 is the verified source of truth (its kit was compiled, tested and built). This plan uses exactly:

```ts
import { PageHeader } from '@/components/sera/PageHeader';   // { eyebrow: string; title: string; lede?: ReactNode; asOf?: string; aside?: ReactNode }
import { Section } from '@/components/sera/Section';         // { eyebrow?; title?; caption?: ReactNode; bg?; aside?; id?; className?; children? }
import { Term } from '@/components/sera/Term';               // { term: string; definition: string; children?: ReactNode }
import { LineChart, type LineSeries } from '@/components/sera/charts/LineChart';
//   series: { id; label; points: readonly [x: ISO date | number, y: number | null, tip?][]; color?; width?; dash?; area?; areaOpacity?; step?; dots?; tip?; endLabel? }[]
//   + ariaLabel, yFormat, refLines: { value; label?; color?; dash?; tip? }[], includeZero, height, legend: ReactNode
import { ScatterChart, type ScatterPoint } from '@/components/sera/charts/ScatterChart';
//   points: { id; x; y; color?; r?; ring?; tip?; href?; label? }[], regions: { x0?; x1?; y0?; y1?; label?; color? }[],
//   refX / refY: RefLine[], includeZeroX, xFormat, yFormat, xLabel, yLabel, height, legend
import { BarChart, type BarGroup } from '@/components/sera/charts/BarChart';
//   groups: { id; label; items: { key; value: number | null; color?; tip?; valueText? }[]; href?; tip? }[], format, height, legend
import { Legend, legendFromSeries } from '@/components/sera/charts/Legend';  // items: { label; color; shape?: 'line'|'dash'|'dot'|'ring'|'zone'; tip? }[]
import { fmtPct, fmtSignedPct } from '@/components/sera/charts/scale';    // tick-formatter factories
import { requireSera } from '@/lib/sera/gate';               // requireSera(next): redirect / notFound, as the layout does
```

- Charts are server components; formatter props are plain functions passed from these server pages.
- `Term` does not import the glossary. Each page defines a 3-line local `T({ k: GlossaryKey })` wrapper that passes `GLOSSARY[k].term` and `GLOSSARY[k].plain`.
- Time charts take ISO-dated points directly (date mode, year ticks). `view.ts` keeps `Point[]` and no longer converts dates to numbers.
- Both pages call `await requireSera(<own path>)` first (Phase 3 handoff 1: a layout does not re-run on client navigation).
- The layout's metadata template is `'%s · Sera'`, so pages set bare titles (`'Methods'`, `` `${m.id} · ${m.name}` ``).

Phase 3 also owns `app/sera/layout.tsx`, which supplies the gate, the rail and the content column; this phase's pages render inside that column. Phase 3 also owns `app/sera/not-found.tsx`, which `notFound()` renders.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `web/app/sera/methods/page.tsx`: default `Methods`, `metadata`.
- `web/app/sera/methods/methods.module.css`
- `web/app/sera/methods/[id]/page.tsx`: default `MethodPage`, `generateStaticParams`, `generateMetadata`.
- `web/app/sera/methods/[id]/method.module.css`
- `web/app/sera/methods/view.ts` exports:
  - filtering: `SHOWS`, `Show`, `parseShow`, `showHref`, `ALIVE_STATUSES`, `isAlive`, `sortMethods`, `MethodRow`, `methodRows`, `matchesShow`, `filterRows`, `showCounts`
  - sources: `sourceHref`, `SOURCE_ICON`
  - formatting: `pct1`, `signed1`, `fixed`, `pfText`, `count`, `longDate`, `windowText`
  - hurdles: `Mark`, `marks`, `conditionTip`, `markLabel`, `conditionSentence`, `Worked`, `workedSummary`
  - charts: `growthFmt`, `CurveLine` (ISO-dated `Point[]`, structurally a Phase 3 `LineSeries`), `BEST_COLOR`, `SPY_COLOR`, `SPY_DASH`, `LINE_COLORS`, `growthLines`, `YearRet`, `yearPairs`, `HurdlePoint`, `hurdlePoints`
  - text: `untestedNote`, `techRows`
- `web/app/sera/methods/view.test.ts`

**Signature changes:** none

**Requires (from earlier phases):**
- Phase 2 (`web/lib/sera/*`): the names listed under **Assumed interfaces → Phase 2**.
- Phase 3 (`web/components/sera/*`, `web/lib/sera/gate.ts`): `PageHeader`, `Section`, `Term`, `charts/{LineChart,ScatterChart,BarChart,Legend,scale}` with the exact props under **Assumed interfaces → Phase 3**; `requireSera`; the `/sera` layout; `app/sera/not-found.tsx`.
- Phase 1: `web/data/lab.json` committed.
- Global CSS (unchanged): `.seg`, `.icon-btn`, `.chip`, `.sheet`, `.num`, `.pos`, `.neg`, `.bg-butter`.

**Leaves alone (owned by others):**
- `web/app/sera/layout.tsx`, `sera.module.css`, `not-found.tsx` and `web/components/sera/**` (Phase 3)
- `web/lib/sera/*` (Phases 2, 3)
- `web/app/sera/page.tsx` and `overview*` (Phase 4)
- `web/app/sera/{journal,ideas,how}/**` (Phase 6)
- `web/app/globals.css`, `web/components/Nav.tsx`
- docs (Phase 7)

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/methods/view.ts` | create (line 1) | pure helpers: filter, sort, rows, source links, formatting, hurdle sentences, chart shaping, tech rows |
| `web/app/sera/methods/view.test.ts` | create (line 1) | vitest for every exported helper |
| `web/app/sera/methods/page.tsx` | create (line 1) | the list page |
| `web/app/sera/methods/methods.module.css` | create (line 1) | list styles |
| `web/app/sera/methods/[id]/page.tsx` | create (line 1) | the detail page |
| `web/app/sera/methods/[id]/method.module.css` | create (line 1) | detail styles, including the `.prose` markdown container and the styled `<summary>` |

## Implementation Steps

### Step 1: Page helpers
**File:** `web/app/sera/methods/view.ts:1` (new)

**Change:** pure, tested helpers. Relative imports only.

- **Pass/miss:** each mark comes from `derive.conditionOk`, which reads the engine's `failed`. `null` means "not measured".
- **Thresholds:** every threshold comes from `snapshot.gate`. Nothing here re-judges a trial (invariant 5).

**Code:**
```ts
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
```
**Impact:** new file. Its import of `lucide-react` (already a dependency) is fine in vitest's node environment.

### Step 2: Helper tests
**File:** `web/app/sera/methods/view.test.ts:1` (new)

**Change:** fixture-based tests. Each builder is full and local, so every expected string is visible here. They import `GATE` from phase 2's `lib/sera/fixture.ts`.

**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { GATE } from '../../../lib/sera/fixture';
import type { LabMethod, LabTrial } from '../../../lib/sera/types';
import {
  BEST_COLOR, conditionSentence, count, filterRows, fixed, growthFmt, growthLines, hurdlePoints, isAlive, longDate,
  markLabel, marks, methodRows, parseShow, pct1, pfText, showCounts, showHref, signed1, sortMethods, sourceHref,
  SPY_COLOR, SPY_DASH, techRows, untestedNote, windowText, workedSummary, yearPairs,
} from './view';

const method = (over: Partial<LabMethod> = {}): LabMethod => ({
  id: 'M0001', name: 'Momentum scaled by its own volatility', family: 'stock-momentum-risk-managed', parentId: null,
  sourceKind: 'paper', sourceRef: 'Barroso & Santa-Clara (2015)', hypothesis: 'Scaling cuts crashes.',
  expectedFailure: 'The target cuts CAGR below SPY.', status: 'rejected', analysis: '', verdict: 'Fixed DD, lost return.',
  blockedOn: '', created: '2026-10-04T10:00:00+07:00', updated: '2026-10-04T12:00:00+07:00', historical: false,
  ...over,
});

const trial = (over: Partial<LabTrial> = {}): LabTrial => ({
  n: 58, methodId: 'M0001', candidateId: 'M0001-TV12', rulesId: 'monthly-hold', allocatorId: 'M0001',
  configText: 'rules=TradeRules(...)', window: 'dev', start: '1996-01-03', end: '2015-10-16', gitSha: 'abc1234',
  runAt: '2026-10-04T12:00:00+07:00', totalReturn: 3.276, cagr: 0.076, maxDrawdown: 0.129, profitFactor: 2.27,
  pfInfinite: false, trades: 1130, sharpe: 0.71, exposure: 0.48, turnover: 3.1, worstYear: 2015,
  worstYearReturn: -0.023, spyTrReturn: 3.514, spyTrCagr: 0.079, mar: 0.59,
  failed: ['beats SPY TR', 'DSR >= 0.95'], eligible: false, dsr: 0.899, nTrialsAtRun: 58,
  curve: [['1996-01-31', 1], ['1996-02-29', 1.02], ['1997-01-31', 1.1]],
  ...over,
});

describe('parseShow / showHref', () => {
  it('accepts the four filters', () => {
    expect(parseShow('lab')).toBe('lab');
    expect(parseShow('historical')).toBe('historical');
    expect(parseShow('alive')).toBe('alive');
    expect(parseShow('all')).toBe('all');
  });
  it('falls back to all', () => {
    expect(parseShow(undefined)).toBe('all');
    expect(parseShow('nope')).toBe('all');
    expect(parseShow(['alive', 'lab'])).toBe('alive');
  });
  it('drops the query for all', () => {
    expect(showHref('all')).toBe('/sera/methods');
    expect(showHref('alive')).toBe('/sera/methods?show=alive');
  });
});

describe('sortMethods', () => {
  it('puts lab methods first by id desc, then historical by id', () => {
    const ms = ['H-P7A-F1', 'M0001', 'H-A', 'M0003', 'M0002'].map(id => method({ id, historical: id.startsWith('H-') }));
    expect(sortMethods(ms).map(m => m.id)).toEqual(['M0003', 'M0002', 'M0001', 'H-A', 'H-P7A-F1']);
  });
});

describe('isAlive / methodRows', () => {
  it('counts live statuses as alive with no trials', () => {
    expect(isAlive(method({ status: 'paper' }), null)).toBe(true);
    expect(isAlive(method({ status: 'dev-eligible' }), null)).toBe(true);
    expect(isAlive(method({ status: 'idea' }), null)).toBe(false);
  });
  it('counts one miss as alive, two as not', () => {
    expect(isAlive(method(), trial({ failed: ['beats SPY TR'] }))).toBe(true);
    expect(isAlive(method(), trial())).toBe(false);
  });
  it('builds a row per method with best variant and passed count', () => {
    const rows = methodRows(
      [method(), method({ id: 'M0002', status: 'idea', parentId: 'M0001' })],
      [trial()],
    );
    expect(rows.map(r => r.method.id)).toEqual(['M0002', 'M0001']);
    expect(rows[0]).toMatchObject({ best: null, tries: 0, passed: null, alive: false });
    expect(rows[1].best?.n).toBe(58);
    expect(rows[1]).toMatchObject({ tries: 1, passed: 4, alive: false });
  });
});

describe('filterRows / showCounts', () => {
  const rows = methodRows(
    [method(), method({ id: 'H-A', historical: true }), method({ id: 'M0002', status: 'paper' })],
    [trial()],
  );
  it('filters lab, historical and alive', () => {
    expect(filterRows(rows, 'lab').map(r => r.method.id)).toEqual(['M0002', 'M0001']);
    expect(filterRows(rows, 'historical').map(r => r.method.id)).toEqual(['H-A']);
    expect(filterRows(rows, 'alive').map(r => r.method.id)).toEqual(['M0002']);
    expect(filterRows(rows, 'all')).toHaveLength(3);
  });
  it('counts every filter', () => {
    expect(showCounts(rows)).toEqual({ all: 3, lab: 2, historical: 1, alive: 1 });
  });
});

describe('sourceHref', () => {
  it('finds a URL and trims trailing punctuation', () => {
    expect(sourceHref('See https://example.com/paper.pdf.')).toBe('https://example.com/paper.pdf');
  });
  it('turns a DOI into a doi.org link', () => {
    expect(sourceHref('Barroso & Santa-Clara (2015), JFE, doi:10.1016/j.jfineco.2014.11.010'))
      .toBe('https://doi.org/10.1016/j.jfineco.2014.11.010');
  });
  it('returns null for a plain citation or a repo path', () => {
    expect(sourceHref('Daniel & Moskowitz (2016), Momentum crashes, JFE 122(2)')).toBeNull();
    expect(sourceHref('docs/backtests/2026-10-04-p7a-dev-exploration.md')).toBeNull();
    expect(sourceHref('')).toBeNull();
  });
});

describe('formatting', () => {
  it('formats percents, numbers and dates', () => {
    expect(pct1(0.076)).toBe('7.6%');
    expect(pct1(-0.123)).toBe('−12.3%');
    expect(pct1(null)).toBe('—');
    expect(signed1(0.076)).toBe('+7.6%');
    expect(signed1(-0.003)).toBe('−0.3%');
    expect(fixed(2.271)).toBe('2.27');
    expect(fixed(null)).toBe('—');
    expect(count(1130)).toBe('1,130');
    expect(longDate('2026-10-04T21:17:00+07:00')).toBe('Oct 4, 2026');
    expect(longDate('2015-10-16')).toBe('Oct 16, 2015');
    expect(windowText(trial())).toBe('1996–2015');
  });
  it('shows ∞ for a variant that never lost', () => {
    expect(pfText(trial({ pfInfinite: true, profitFactor: null }))).toBe('∞');
    expect(pfText(trial())).toBe('2.27');
  });
});

describe('marks / workedSummary', () => {
  it('marks the failed hurdles from the engine list', () => {
    const m = Object.fromEntries(marks(trial()).map(x => [x.key, x.ok]));
    expect(m).toEqual({ spy: false, drawdown: true, pf: true, trades: true, owner: true, dsr: false });
    expect(markLabel(marks(trial())[0])).toBe('Beats SPY: missed');
  });
  it('treats a missing luck score as not measured', () => {
    const dsr = marks(trial({ dsr: null, failed: ['beats SPY TR'] })).find(x => x.key === 'dsr')!;
    expect(dsr.ok).toBeNull();
    expect(markLabel(dsr)).toBe('Luck check: not measured');
    expect(conditionSentence('dsr', null, trial({ dsr: null }), GATE)).toBe('Luck check: not measured.');
  });
  it('writes the plain summary from the gate thresholds', () => {
    const w = workedSummary(trial(), GATE);
    expect(w.headline).toBe('Not yet. Its best variant, M0001-TV12, cleared 4 of 6 hurdles on 1996–2015 data.');
    expect(w.sentence).toBe(
      'Beats SPY: no (7.6% vs 7.9% a year). Max drawdown: yes (12.9% ≤ 15%). ' +
      'Profit factor: yes (2.27 ≥ 1.3). Trade count: yes (1,130 ≥ 100). ' +
      'Owner inputs: yes (none needed). ' +
      'Luck check: no (0.90 < 0.95, after 58 tries).',
    );
  });
  it('says yes when every hurdle clears', () => {
    const t = trial({ failed: [], eligible: true, cagr: 0.09, dsr: 0.97 });
    expect(workedSummary(t, GATE).headline).toBe('Yes. Its best variant, M0001-TV12, cleared all six hurdles on 1996–2015 data.');
  });
  it('flips the comparison sign on a miss', () => {
    const t = trial({ maxDrawdown: 0.18, failed: ['beats SPY TR', 'max DD <= 15%', 'DSR >= 0.95'] });
    expect(conditionSentence('drawdown', false, t, GATE)).toBe('Max drawdown: no (18.0% > 15%).');
  });
});

describe('chart shaping', () => {
  it('formats growth of 1', () => {
    expect(growthFmt(1.5)).toBe('1.5×');
    expect(growthFmt(12.3)).toBe('12×');
  });
  it('draws the best variant last in coral and SPY dotted after it, on ISO dates', () => {
    const a = trial({ n: 55, candidateId: 'M0001-TV10' });
    const b = trial();
    const spy: [string, number][] = [['1996-01-31', 1], ['1997-01-31', 1.2]];
    const lines = growthLines([b, a], b, spy);
    expect(lines.map(l => l.id)).toEqual(['M0001-TV10', 'M0001-TV12', 'SPY']);
    expect(lines[0].dash).toBeUndefined();
    expect(lines[1]).toMatchObject({ color: BEST_COLOR, width: 2.5, label: 'M0001-TV12 (best)' });
    expect(lines[1].points).toEqual(b.curve);
    expect(lines[2]).toMatchObject({ color: SPY_COLOR, dash: SPY_DASH, points: spy });
  });
  it('omits SPY when there is no benchmark series', () => {
    expect(growthLines([trial()], trial(), []).map(l => l.id)).toEqual(['M0001-TV12']);
  });
  it('pairs only the years both series have', () => {
    expect(yearPairs([{ year: 1997, ret: 0.1 }, { year: 1996, ret: 0.05 }, { year: 2016, ret: 0.2 }],
      [{ year: 1996, ret: 0.2 }, { year: 1997, ret: 0.3 }]))
      .toEqual([{ year: 1996, method: 0.05, spy: 0.2 }, { year: 1997, method: 0.1, spy: 0.3 }]);
  });
  it('places own dev trials last and skips test or incomplete ones', () => {
    const pts = hurdlePoints([
      trial(),
      trial({ n: 3, methodId: 'H-P7A-F4', candidateId: 'F4-MOM12', cagr: 0.162, maxDrawdown: 0.222 }),
      trial({ n: 59, window: 'test' }),
      trial({ n: 4, methodId: 'H-A', maxDrawdown: null }),
    ], 'M0001');
    expect(pts.map(p => [p.id, p.own])).toEqual([['3', false], ['58', true]]);
    expect(pts[0].href).toBe('/sera/methods/H-P7A-F4');
    expect(pts[1].x).toBeCloseTo(0.129);
    expect(pts[1].y).toBeCloseTo(-0.003);
    expect(pts[1].tip).toBe('M0001-TV12: −0.3% a year vs SPY, worst fall 12.9%');
  });
});

describe('text', () => {
  it('explains untested methods by status', () => {
    expect(untestedNote(method({ status: 'idea' }))).toMatch(/^Not tested yet\./);
    expect(untestedNote(method({ status: 'blocked-data', blockedOn: 'point-in-time fundamentals' })))
      .toBe('Not tested: it needs data the lab does not have yet (point-in-time fundamentals).');
    expect(untestedNote(method({ status: 'registered' }))).toBe('Registered with its exact rules, not run yet.');
  });
  it('lists the technical record', () => {
    const rows = Object.fromEntries(techRows(trial()));
    expect(rows['Trial number']).toBe('#58');
    expect(rows['Code version (git)']).toBe('abc1234');
    expect(rows['Tries counted when run (N)']).toBe('58');
    expect(rows['Worst year']).toBe('2015 (−2.3%)');
    expect(rows['Failed']).toBe('beats SPY TR; DSR >= 0.95');
    expect(Object.fromEntries(techRows(trial({ failed: [] })))['Failed']).toBe('nothing: eligible');
  });
});
```
**Impact:** new tests. They rely on phase 2's semantics as written in `phase-2.md`:
- `conditionOk` reads `failed`, with null for a missing DSR.
- `misses` returns `ConditionKey[]`.
- `conditionsPassed` counts only `true` results.
- `CONDITION_LABEL` reads 'Beats SPY', 'Max drawdown', 'Profit factor', 'Trade count', 'Owner inputs', 'Luck check'.

If phase 2 changes those labels, update the expected strings in the `marks / workedSummary` block.

### Step 3: List page
**File:** `web/app/sera/methods/page.tsx:1` (new)

**Change:** a server component; `searchParams` is a Promise (Next 16, as in `app/(app)/leaderboard/page.tsx`).

- **Layout:** `PageHeader`, then a single `Section` sheet. The sheet has a toolbar (filter seg + count chips) and a semantic `<table>`.
- **Row link:** the whole row links to the detail page through a stretched link. The method name `<Link>` carries an `::after` that covers the `<tr>`. The source link sits above it with `z-index: 1`, so the two anchors are never nested.
- **Controls:** the four filter buttons are the only controls. They are icon-only `<Link>`s in `.seg`, each with `aria-label`, `data-tip` and `aria-current`.

**Code:**
```tsx
import { Archive, ChevronRight, ExternalLink, FlaskConical, HeartPulse, LayoutList, type LucideIcon } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Term } from '@/components/sera/Term';
import { excessCagr } from '@/lib/sera/derive';
import { requireSera } from '@/lib/sera/gate';
import { GLOSSARY, type GlossaryKey, SOURCE_KIND_LABEL, STATUS_LABEL } from '@/lib/sera/glossary';
import { lab } from '@/lib/sera/lab';
import type { LabTrial } from '@/lib/sera/types';
import {
  count, filterRows, fixed, markLabel, marks, methodRows, parseShow, pct1, pfText, showCounts, showHref, SOURCE_ICON,
  sourceHref, type MethodRow, type Show,
} from './view';
import s from './methods.module.css';

// The layout's title template renders this as "Methods · Sera".
export const metadata: Metadata = { title: 'Methods' };

/** A glossary term: the definition comes from lib/sera/glossary (Term itself takes plain strings). */
function T({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  return <Term term={GLOSSARY[k].term} definition={GLOSSARY[k].plain}>{children}</Term>;
}

const FILTERS: [Show, LucideIcon, string][] = [
  ['all', LayoutList, 'All methods'],
  ['lab', FlaskConical, 'Lab methods only'],
  ['historical', Archive, 'Historical methods, from before the lab'],
  ['alive', HeartPulse, 'Still alive: passed, or one hurdle away'],
];

const EMPTY: Record<Show, string> = {
  all: 'The lab has no methods yet.',
  lab: 'No lab methods yet.',
  historical: 'No historical methods.',
  alive: 'Nothing is alive yet: no method has passed, and none is one hurdle away.',
};

type Search = { show?: string | string[] };

export default async function Methods({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const show = parseShow(q.show);
  await requireSera(showHref(show));
  const rows = methodRows(lab.methods, lab.trials);
  const counts = showCounts(rows);
  const shown = filterRows(rows, show);

  return (
    <>
      <PageHeader
        eyebrow="Methods"
        title="Every method tried"
        lede="Each row is one idea Sera tested on 1993–2015 data, judged by its best variant. Open a row for the full story."
        asOf={lab.asOf}
      />
      <Section
        title="The methods"
        caption="The six dots on each row are the six hurdles a method must clear before it may trade. A filled dot means cleared."
        className={s.sheet}
      >
        <div className={s.toolbar}>
          <div className="seg" role="group" aria-label="Filter methods">
            {FILTERS.map(([v, Icon, tip]) => (
              <Link key={v} href={showHref(v)} replace scroll={false} className="icon-btn"
                data-tip={tip} aria-label={tip} aria-current={show === v ? 'true' : undefined}>
                <Icon size={19} strokeWidth={show === v ? 2 : 1.5} />
              </Link>
            ))}
          </div>
          <div className={s.counts}>
            <span className="chip"><span className="num">{counts.all}</span> methods</span>
            <span className="chip"><span className="num">{counts.lab}</span> lab</span>
            <span className="chip"><span className="num">{counts.historical}</span> historical</span>
            <span className="chip"><span className="num">{counts.alive}</span> alive</span>
            <span className="chip"><span className="num">{count(lab.summary.devTrials)}</span> tries</span>
          </div>
        </div>

        {shown.length === 0 ? (
          <p className={s.empty}>{EMPTY[show]}</p>
        ) : (
          <div className={s.tableWrap}>
            <table className={s.table}>
              <thead>
                <tr>
                  <th className={s.cStatus} scope="col">Status</th>
                  <th className={s.cMethod} scope="col">Method</th>
                  <th className={s.cSource} scope="col">Source</th>
                  <th className={`${s.cCagr} ${s.r}`} scope="col"><T k="cagr">Growth a year</T> vs SPY</th>
                  <th className={`${s.cNum} ${s.r}`} scope="col"><T k="maxDrawdown">Max DD</T></th>
                  <th className={`${s.cNum} ${s.r}`} scope="col"><T k="profitFactor">PF</T></th>
                  <th className={`${s.cNum} ${s.r}`} scope="col"><T k="trades">Trades</T></th>
                  <th className={`${s.cNum} ${s.r}`} scope="col"><T k="dsr">DSR</T></th>
                  <th className={s.cDots} scope="col">Hurdles</th>
                  <th className={s.cVerdict} scope="col">Verdict</th>
                  <th className={s.cGo} aria-hidden="true" />
                </tr>
              </thead>
              <tbody>
                {shown.map(r => <Row key={r.method.id} r={r} />)}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </>
  );
}

function Row({ r }: { r: MethodRow }) {
  const m = r.method;
  const b = r.best;
  const href = sourceHref(m.sourceRef);
  const SrcIcon = SOURCE_ICON[m.sourceKind];
  const srcLabel = SOURCE_KIND_LABEL[m.sourceKind];
  const st = STATUS_LABEL[m.status];
  const excess = b ? excessCagr(b) : null;
  return (
    <tr className={s.row}>
      <td>
        <span className={`chip ${s.status}`} data-tone={st.tone} data-tip={st.meaning}>{st.label}</span>
      </td>
      <td>
        <Link href={`/sera/methods/${m.id}`} className={s.nameLink}>
          <span className={s.id}>{m.id}</span>
          <span className={s.name}>{m.name}</span>
        </Link>
        <span className={s.family}>{m.family}</span>
      </td>
      <td>
        {href ? (
          <a href={href} target="_blank" rel="noreferrer" className={s.sourceLink}
            data-tip={m.sourceRef} aria-label={`${srcLabel}: ${m.sourceRef}`}>
            <SrcIcon size={15} aria-hidden="true" />
            <span className={s.sourceText}>{srcLabel}</span>
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        ) : (
          <span className={s.source} data-tip={m.sourceRef || undefined}>
            <SrcIcon size={15} aria-hidden="true" />
            <span className={s.sourceText}>{srcLabel}</span>
          </span>
        )}
      </td>
      {b ? (
        <>
          <td className={s.r}>
            <span className={`num ${excess === null ? '' : excess >= 0 ? 'pos' : 'neg'}`}>{pct1(b.cagr)}</span>
            <span className={s.vs}> vs {pct1(b.spyTrCagr)}</span>
          </td>
          <td className={`num ${s.r}`}>{pct1(b.maxDrawdown)}</td>
          <td className={`num ${s.r}`}>{pfText(b)}</td>
          <td className={`num ${s.r}`}>{count(b.trades)}</td>
          <td className={`num ${s.r}`}>{fixed(b.dsr, 2)}</td>
          <td><Dots best={b} passed={r.passed ?? 0} /></td>
        </>
      ) : (
        <td colSpan={6} className={s.untested}>Not tested yet</td>
      )}
      <td><span className={s.verdict}>{m.verdict || '—'}</span></td>
      <td className={s.go} aria-hidden="true"><ChevronRight size={18} /></td>
    </tr>
  );
}

function Dots({ best, passed }: { best: LabTrial; passed: number }) {
  const ms = marks(best);
  const missed = ms.filter(x => x.ok !== true).map(markLabel);
  const tip = missed.length ? missed.join(' · ') : 'Cleared every hurdle';
  return (
    <span className={s.dots} role="img" aria-label={`Cleared ${passed} of 6 hurdles. ${tip}`} data-tip={tip}>
      {ms.map(x => (
        <span key={x.key} className={x.ok === true ? s.dotOn : x.ok === null ? s.dotNa : s.dotOff} />
      ))}
      <span className={`num ${s.dotsN}`}>{passed}/6</span>
    </span>
  );
}
```
**Impact:** new route `/sera/methods`. It is dynamic, because it reads `searchParams` and the phase-3 layout reads the session.

### Step 4: List styles
**File:** `web/app/sera/methods/methods.module.css:1` (new)

**Code:**
```css
/* /sera/methods: a wide, table-like sheet. Seer v2 tokens only. Desktop is the designed layout;
   below 1024px the table scrolls sideways inside its sheet. */
.sheet { gap: 20px; }

.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.counts { display: flex; flex-wrap: wrap; gap: 8px; color: var(--ink-2); }
.counts .num { color: var(--ink); font-weight: 500; }

.empty { padding: 12px 0; font-size: 16px; color: var(--ink-2); }

.tableWrap { overflow-x: auto; margin: 0 -8px; }
.table { width: 100%; min-width: 1200px; border-collapse: collapse; table-layout: fixed; font-size: 15px; }
.table th, .table td {
  padding: 13px 8px; text-align: left; font-weight: 400; vertical-align: middle;
  border-bottom: 1px solid var(--hair);
}
.table thead th {
  padding-top: 0; padding-bottom: 10px; font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--ink-2); vertical-align: bottom;
}
.table tbody tr:last-child td { border-bottom: 0; }
.r { text-align: right !important; }

.cStatus { width: 150px; }
.cMethod { width: 24%; }
.cSource { width: 150px; }
.cCagr { width: 142px; }
.cNum { width: 74px; }
.cDots { width: 112px; }
.cVerdict { width: auto; }
.cGo { width: 34px; }

/* Whole row is a link: the name link's ::after covers the row; the source link sits above it. */
.row { position: relative; transition: background 0.12s; }
.row:hover { background: var(--stone); }
.row:focus-within { outline: 2px solid var(--coral); outline-offset: -2px; }
.row td:first-child { border-radius: 18px 0 0 18px; }
.row td:last-child { border-radius: 0 18px 18px 0; }

.nameLink { display: flex; flex-direction: column; gap: 1px; color: var(--ink); outline: none; }
.nameLink::after { content: ''; position: absolute; inset: 0; }
.id { font-size: 12px; letter-spacing: 0.06em; color: var(--ink-3); }
.name { font-size: 16px; font-weight: 500; line-height: 1.25; letter-spacing: -0.01em; }
.family { display: block; margin-top: 2px; font-size: 13px; color: var(--ink-2); }

.source, .sourceLink { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; font-size: 14px; color: var(--ink-2); }
.sourceText { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sourceLink { position: relative; z-index: 1; color: var(--ink); text-decoration: underline; text-decoration-color: var(--outline); text-underline-offset: 3px; }
.sourceLink:hover { text-decoration-color: var(--ink); }
.sourceLink:focus-visible { outline: 2px solid var(--coral); outline-offset: 2px; border-radius: 6px; }

.vs { font-size: 13px; color: var(--ink-2); white-space: nowrap; }
.untested { color: var(--ink-3); font-size: 14px; }

/* Status chip by STATUS_LABEL tone. */
.status { height: 28px; padding: 0 11px; font-size: 13px; background: var(--stone); color: var(--ink-2); }
.status[data-tone='bad'] { background: var(--stone); color: var(--ink-2); }
.status[data-tone='wait'] { background: transparent; border: 1.5px dashed var(--outline); color: var(--ink-2); }
.status[data-tone='neutral'] { background: var(--butter); color: var(--ink); }
.status[data-tone='good'] { background: var(--ink); color: var(--sheet); }

.dots { display: inline-flex; align-items: center; gap: 4px; }
.dotOn, .dotOff, .dotNa { width: 9px; height: 9px; border-radius: 999px; flex: none; }
.dotOn { background: var(--ink); }
.dotOff { border: 1.5px solid var(--outline); }
.dotNa { border: 1.5px dashed var(--ink-3); }
.dotsN { margin-left: 6px; font-size: 13px; color: var(--ink-2); }

.verdict {
  display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden;
  font-size: 14px; line-height: 1.35; color: var(--ink-2);
}
.go { color: var(--ink-3); text-align: right; }
.row:hover .go { color: var(--ink); }

@media (min-width: 1024px) {
  .sheet { padding: 28px 30px 30px; border-radius: 40px; }
}
```

### Step 5: Detail page
**File:** `web/app/sera/methods/[id]/page.tsx:1` (new)

**Change:** builds every method at build time from `lab.methods` (`generateStaticParams`). An unknown id calls `notFound()`, which renders the phase-3 `app/sera/not-found.tsx`. `params` is a Promise.

- **Untested methods:** with no trial at all (idea, blocked, registered), the page renders the idea, the expected failure, a plain note (and `blockedOn`), the analysis and the insights. It skips the charts, the variants table and the technical detail.
- **SPY baseline:** SPY is rebased to the best variant's window with `spyForWindow(best, lab.benchmark)`.
- **Captions:** every chart caption says what the chart shows and how to read it (invariant 6).

**Code:**
```tsx
import { CalendarClock, CalendarPlus, Check, ChevronRight, CircleDashed, ExternalLink, GitFork, Hash, X } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { ReactNode } from 'react';
import { BarChart, type BarGroup } from '@/components/sera/charts/BarChart';
import { Legend, legendFromSeries } from '@/components/sera/charts/Legend';
import { LineChart, type LineSeries } from '@/components/sera/charts/LineChart';
import { fmtPct, fmtSignedPct } from '@/components/sera/charts/scale';
import { ScatterChart, type ScatterPoint } from '@/components/sera/charts/ScatterChart';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Term } from '@/components/sera/Term';
import { bestVariant, CONDITION_KEYS, CONDITION_LABEL, drawdownSeries, spyForWindow, yearlyReturns } from '@/lib/sera/derive';
import { requireSera } from '@/lib/sera/gate';
import { GLOSSARY, type GlossaryKey, INSIGHT_KIND_LABEL, SOURCE_KIND_LABEL, STATUS_LABEL } from '@/lib/sera/glossary';
import { childrenOf, insightsOf, lab, methodById, trialsOf } from '@/lib/sera/lab';
import { renderMarkdown } from '@/lib/sera/markdown';
import type { LabMethod, LabTrial } from '@/lib/sera/types';
import {
  BEST_COLOR, conditionTip, count, fixed, growthFmt, growthLines, hurdlePoints, longDate, markLabel, marks, pct1,
  pfText, signed1, SOURCE_ICON, sourceHref, SPY_COLOR, SPY_DASH, techRows, untestedNote, windowText, workedSummary,
  yearPairs, type Mark,
} from '../view';
import s from './method.module.css';

type Params = { id: string };

export function generateStaticParams(): Params[] {
  return lab.methods.map(m => ({ id: m.id }));
}

// The layout's title template appends " · Sera".
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { id } = await params;
  const m = methodById(id);
  return { title: m ? `${m.id} · ${m.name}` : 'Method' };
}

/** A glossary term: the definition comes from lib/sera/glossary (Term itself takes plain strings). */
function T({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  return <Term term={GLOSSARY[k].term} definition={GLOSSARY[k].plain}>{children}</Term>;
}

export default async function MethodPage({ params }: { params: Promise<Params> }) {
  const { id } = await params;
  await requireSera(`/sera/methods/${encodeURIComponent(id)}`);
  const m = methodById(id);
  if (!m) notFound();

  const trials = trialsOf(m.id);
  const best = bestVariant(trials);
  const parent = m.parentId ? methodById(m.parentId) : undefined;
  const children = childrenOf(m.id);
  const insights = insightsOf(m.id);
  const nAtRun = trials.length ? Math.max(...trials.map(t => t.nTrialsAtRun)) : null;
  const srcHref = sourceHref(m.sourceRef);
  const SrcIcon = SOURCE_ICON[m.sourceKind];
  const srcLabel = SOURCE_KIND_LABEL[m.sourceKind];
  const st = STATUS_LABEL[m.status];

  return (
    <>
      <PageHeader
        eyebrow={`${st.label} · ${m.family}`}
        title={`${m.id} · ${m.name}`}
        lede={m.verdict || untestedNote(m)}
        asOf={lab.asOf}
      />

      <div className={s.meta}>
        <span className={`chip ${s.statusChip}`} data-tone={st.tone} data-tip={st.meaning}>{st.label}</span>
        {srcHref ? (
          <a className={`chip ${s.metaLink}`} href={srcHref} target="_blank" rel="noreferrer"
            data-tip={m.sourceRef} aria-label={`${srcLabel}: ${m.sourceRef}`}>
            <SrcIcon size={15} aria-hidden="true" />{srcLabel}<ExternalLink size={12} aria-hidden="true" />
          </a>
        ) : (
          <span className="chip" data-tip={m.sourceRef || undefined}>
            <SrcIcon size={15} aria-hidden="true" />{srcLabel}
          </span>
        )}
        {parent && (
          <Link className={`chip ${s.metaLink}`} href={`/sera/methods/${parent.id}`}
            data-tip={`A variation of ${parent.name}`} aria-label={`Parent method ${parent.id}: ${parent.name}`}>
            <GitFork size={15} aria-hidden="true" />from {parent.id}
          </Link>
        )}
        {children.map(c => (
          <Link key={c.id} className={`chip ${s.metaLink}`} href={`/sera/methods/${c.id}`}
            data-tip={c.name} aria-label={`Follow-up method ${c.id}: ${c.name}`}>
            <ChevronRight size={15} aria-hidden="true" />led to {c.id}
          </Link>
        ))}
        <span className="chip" data-tip="Written down"><CalendarPlus size={15} aria-hidden="true" />{longDate(m.created)}</span>
        <span className="chip" data-tip="Last updated"><CalendarClock size={15} aria-hidden="true" />{longDate(m.updated)}</span>
        {nAtRun !== null && (
          <span className="chip" data-tip="How many tries the lab had counted when this ran. The more tries, the higher the bar for luck.">
            <Hash size={15} aria-hidden="true" />N = {count(nAtRun)}
          </span>
        )}
      </div>

      <div className={s.twoUp}>
        <Section eyebrow="Hypothesis" title="The idea" caption="What Sera expected before running anything." className={s.textSheet}>
          <p className={s.body}>{m.hypothesis || 'No hypothesis was recorded.'}</p>
          {m.sourceRef && <p className={s.cite}>Source: {m.sourceRef}</p>}
        </Section>
        <Section eyebrow="Written down first" title="What could go wrong" caption="The likely failure, written down before the test so the result cannot be explained away afterwards." className={s.textSheet}>
          <p className={s.body}>
            {m.expectedFailure ?? (m.historical
              ? 'This method predates the lab, and the lab only started writing down the expected failure before each test later. None was recorded.'
              : 'No expected failure was written down.')}
          </p>
        </Section>
      </div>

      {best ? (
        <Tested m={m} trials={trials} best={best} />
      ) : (
        <Section eyebrow="Status" title="Not tested yet" caption="There are no charts until a test has run." className={`${s.textSheet} bg-butter`}>
          <p className={s.body}>{untestedNote(m)}</p>
          {m.blockedOn && m.status !== 'blocked-data' && <p className={s.body}>Waiting on: {m.blockedOn}</p>}
        </Section>
      )}

      <Section eyebrow="Analysis" title="Sera's analysis and opinion" caption="Sera's own reading of the result: what happened, why, and what to try next." className={s.proseSheet}>
        {m.analysis.trim() ? (
          // Escape-first rendering (lib/sera/markdown): all text is HTML-escaped before markup is added.
          <div className={s.prose} dangerouslySetInnerHTML={{ __html: renderMarkdown(m.analysis) }} />
        ) : (
          <p className={s.muted}>
            {m.historical
              ? `This method came from before the lab, and its write-up lives in ${m.sourceRef || 'the project docs'}. The verdict above is the summary.`
              : 'Sera has not written an analysis for this method yet.'}
          </p>
        )}
      </Section>

      <Section eyebrow="Journal" title="Insights from this method" caption="Lessons, wishes and risks Sera noted while working on this method." className={s.textSheet}>
        {insights.length ? (
          <ul className={s.insights}>
            {insights.map(i => (
              <li key={i.id} className={s.insight}>
                <div className={s.insightHead}>
                  <span className={`chip ${s.kindChip}`}>{INSIGHT_KIND_LABEL[i.kind].label}</span>
                  <span className={s.insightTitle}>{i.title}</span>
                  <span className={s.insightDate}>{longDate(i.added)}</span>
                </div>
                <div className={s.prose} dangerouslySetInnerHTML={{ __html: renderMarkdown(i.body) }} />
              </li>
            ))}
          </ul>
        ) : (
          <p className={s.muted}>No insights are linked to this method yet.</p>
        )}
      </Section>

      {trials.length > 0 && (
        <Section eyebrow="For the record" title="Technical detail" caption="Everything needed to rerun each variant exactly: its config, rules, code version and window." className={s.textSheet}>
          <div className={s.techList}>
            {trials.map(t => <Tech key={t.n} t={t} />)}
          </div>
        </Section>
      )}
    </>
  );
}

function MarkIcon({ mark, size }: { mark: Mark; size: number }) {
  const label = markLabel(mark);
  const cls = mark.ok === true ? s.ok : mark.ok === null ? s.na : s.no;
  return (
    <span className={cls} role="img" aria-label={label} data-tip={label}>
      {mark.ok === true ? <Check size={size} /> : mark.ok === null ? <CircleDashed size={size} /> : <X size={size} />}
    </span>
  );
}

function Tested({ m, trials, best }: { m: LabMethod; trials: LabTrial[]; best: LabTrial }) {
  const gate = lab.gate;
  const worked = workedSummary(best, gate);
  const variants = trials.filter(t => t.window === best.window);
  const spy = spyForWindow(best, lab.benchmark);
  const growth = growthLines(variants, best, spy);
  const ddBest = drawdownSeries(best.curve);
  const ddSpy = drawdownSeries(spy);
  const years = yearPairs(yearlyReturns(best.curve), yearlyReturns(spy));
  const points = hurdlePoints(lab.trials, m.id);

  // Phase 3 chart-kit shapes. Dated points go in as ISO strings (date mode, year ticks).
  const ddSeries: LineSeries[] = [
    { id: best.candidateId, label: best.candidateId, points: ddBest, color: BEST_COLOR, width: 2, area: true },
    { id: 'SPY', label: 'SPY with dividends', points: ddSpy, color: SPY_COLOR, width: 1.5, dash: SPY_DASH, area: true, areaOpacity: 0.08 },
  ];
  const yearGroups: BarGroup[] = years.map(y => ({
    id: String(y.year),
    label: String(y.year),
    items: [
      { key: 'method', value: y.method, color: BEST_COLOR, tip: `${y.year} ${best.candidateId}: ${signed1(y.method)}` },
      { key: 'spy', value: y.spy, color: SPY_COLOR, tip: `${y.year} SPY: ${signed1(y.spy)}` },
    ],
  }));
  const scatter: ScatterPoint[] = points.map(p => ({
    id: p.id, x: p.x, y: p.y, tip: p.tip, href: p.own ? undefined : p.href,
    color: p.own ? BEST_COLOR : SPY_COLOR, r: p.own ? 7 : 4, ring: !p.own,
  }));

  return (
    <>
      <Section eyebrow="Verdict" title="Did it work?" caption={worked.headline} className={`${s.textSheet} bg-butter`}>
        <ul className={s.worked}>
          {worked.lines.map(l => (
            <li key={l.key} className={s.workedItem}>
              <MarkIcon mark={{ key: l.key, label: CONDITION_LABEL[l.key], ok: l.ok }} size={16} />
              <span>{l.text}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section eyebrow="Growth" title="Growth of 1"
        caption={`Each line shows what 1 dollar grew to in one variant over ${windowText(best)}. The dotted line is SPY with dividends over the same years. Higher at the right edge is better.`}
        className={s.chartSheet}>
        <LineChart
          ariaLabel={`Growth of 1 dollar for each ${m.id} variant against SPY with dividends`}
          series={growth}
          yFormat={growthFmt}
          refLines={[{ value: 1, label: 'Start' }]}
          height={360}
          legend={<Legend items={legendFromSeries(growth)} />}
        />
      </Section>

      <div className={s.twoUp}>
        <Section eyebrow="Pain" title="Drawdowns"
          caption={`How far the best variant sat below its last peak at each point, with SPY dotted. The line marks the ${pct1(gate.maxDrawdown)} limit; anything below it fails.`}
          className={s.chartSheet}>
          <LineChart
            ariaLabel={`Drawdowns of ${best.candidateId} and SPY`}
            series={ddSeries}
            refLines={[{ value: -gate.maxDrawdown, label: `Limit −${pct1(gate.maxDrawdown)}`, color: 'var(--neg)' }]}
            includeZero
            yFormat={fmtPct(0)}
            height={300}
            legend={<Legend items={legendFromSeries(ddSeries)} />}
          />
        </Section>

        <Section eyebrow="Calendar" title="Year by year"
          caption="Each pair of bars is one calendar year: the best variant, then SPY. The first and last years may be partial."
          className={s.chartSheet}>
          <BarChart
            ariaLabel={`Calendar-year returns of ${best.candidateId} and SPY`}
            groups={yearGroups}
            format={fmtSignedPct(0)}
            height={300}
            legend={<Legend items={[
              { label: best.candidateId, color: BEST_COLOR, shape: 'zone' },
              { label: 'SPY with dividends', color: SPY_COLOR, shape: 'zone' },
            ]} />}
          />
        </Section>
      </div>

      <Section eyebrow="Hurdles" title="Against the hurdles"
        caption={`Each dot is one development try by the lab. Across is its worst fall; up is how much faster it grew than SPY. This method's variants are the solid coral dots. A method must land in the shaded corner: a fall of ${pct1(gate.maxDrawdown)} or less, and growth above SPY.`}
        className={s.chartSheet}>
        <ScatterChart
          ariaLabel={`Where ${m.id}'s variants landed among all development tries`}
          points={scatter}
          regions={[{ x1: gate.maxDrawdown, y0: 0, label: 'Pass zone' }]}
          refY={[{ value: 0, label: 'SPY' }]}
          includeZeroX
          xFormat={fmtPct(0)}
          yFormat={fmtSignedPct(0)}
          xLabel="Worst fall from a peak"
          yLabel="Growth a year minus SPY's"
          height={400}
          legend={<Legend items={[
            { label: `${m.id} variants`, color: BEST_COLOR, shape: 'dot' },
            { label: 'All other tries', color: SPY_COLOR, shape: 'ring' },
            { label: 'Pass zone', color: 'var(--sky)', shape: 'zone' },
          ]} />}
        />
      </Section>

      <Section eyebrow="Variants" title="Every variant"
        caption="One row per test run. A tick means the hurdle was cleared. The best variant is highlighted."
        className={s.chartSheet}>
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead>
              <tr>
                <th scope="col">Variant</th>
                <th scope="col">Window</th>
                <th scope="col" className={s.r}><T k="cagr">Growth a year</T> vs SPY</th>
                <th scope="col" className={s.r}><T k="return">Return</T></th>
                <th scope="col" className={s.r}><T k="maxDrawdown">Max DD</T></th>
                <th scope="col" className={s.r}><T k="profitFactor">PF</T></th>
                <th scope="col" className={s.r}><T k="trades">Trades</T></th>
                <th scope="col" className={s.r}><T k="sharpe">Sharpe</T></th>
                <th scope="col" className={s.r}><T k="mar">MAR</T></th>
                <th scope="col" className={s.r}><T k="dsr">DSR</T></th>
                {CONDITION_KEYS.map(k => (
                  <th key={k} scope="col" className={s.c}>
                    <span data-tip={conditionTip(k, gate)}>{CONDITION_LABEL[k]}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trials.map(t => (
                <tr key={t.n} className={t.n === best.n ? s.bestRow : undefined}>
                  <th scope="row" className={s.variant}>{t.candidateId}</th>
                  <td><span className={s.window} data-window={t.window}>{t.window === 'dev' ? 'Dev' : 'Test'}</span> {windowText(t)}</td>
                  <td className={s.r}>
                    <span className="num">{pct1(t.cagr)}</span>
                    <span className={s.vs}> vs {pct1(t.spyTrCagr)}</span>
                  </td>
                  <td className={`num ${s.r}`}>{signed1(t.totalReturn)}</td>
                  <td className={`num ${s.r}`}>{pct1(t.maxDrawdown)}</td>
                  <td className={`num ${s.r}`}>{pfText(t)}</td>
                  <td className={`num ${s.r}`}>{count(t.trades)}</td>
                  <td className={`num ${s.r}`}>{fixed(t.sharpe, 2)}</td>
                  <td className={`num ${s.r}`}>{fixed(t.mar, 2)}</td>
                  <td className={`num ${s.r}`}>{fixed(t.dsr, 2)}</td>
                  {marks(t).map(x => (
                    <td key={x.key} className={s.c}><MarkIcon mark={x} size={14} /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}

function Tech({ t }: { t: LabTrial }) {
  return (
    <details className={s.tech}>
      <summary className={s.techSummary} data-tip="Show the technical record">
        <span className={s.techChevron} aria-hidden="true"><ChevronRight size={16} /></span>
        <span className={s.techName}>{t.candidateId}</span>
        <span className={s.techSub}>#{t.n} · {t.window === 'dev' ? 'development' : 'test'} {windowText(t)} · {t.failed.length ? `missed ${t.failed.length}` : 'eligible'}</span>
      </summary>
      <div className={s.techBody}>
        <dl className={s.techGrid}>
          {techRows(t).map(([k, v]) => (
            <div key={k} className={s.techRow}>
              <dt>{k}</dt>
              <dd className="num">{v}</dd>
            </div>
          ))}
        </dl>
        <pre className={s.config}>{t.configText}</pre>
      </div>
    </details>
  );
}
```
**Impact:** new route `/sera/methods/[id]`.

- **Text links:** the parent and children chips and the source chip are text links to content, not controls.
- **The one non-link control:** the `<summary>` disclosure. It keeps a Lucide chevron and a `data-tip`, and its text is the variant id that heads the block.
- **Rendering:** the phase-3 layout reads the session, so the route renders dynamically. `generateStaticParams` still lists every id for the build check.

### Step 6: Detail styles
**File:** `web/app/sera/methods/[id]/method.module.css:1` (new)

**Code:**
```css
/* /sera/methods/[id]. Seer v2 tokens only. Desktop is the designed layout; below 1024px the
   two-up grids stack and wide tables scroll inside their sheet. */
.meta { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 12px; }
.metaLink { color: var(--ink); background: var(--chip-solid); transition: background 0.12s, color 0.12s; }
.metaLink:hover { background: var(--ink); color: var(--sheet); }
.metaLink:focus-visible { outline: 2px solid var(--coral); outline-offset: 2px; }
.statusChip { background: var(--stone); color: var(--ink-2); }
.statusChip[data-tone='wait'] { background: transparent; border: 1.5px dashed var(--outline); }
.statusChip[data-tone='neutral'] { background: var(--butter); color: var(--ink); }
.statusChip[data-tone='good'] { background: var(--ink); color: var(--sheet); }

.twoUp { display: grid; grid-template-columns: 1fr; gap: 12px; margin-bottom: 12px; }
.textSheet, .chartSheet, .proseSheet { margin-bottom: 12px; gap: 14px; }
.twoUp > * { margin-bottom: 0; }

.body { font-size: 17px; line-height: 1.55; max-width: 72ch; }
.cite { font-size: 14px; line-height: 1.4; color: var(--ink-2); }
.muted { font-size: 16px; color: var(--ink-2); }

/* Did it work? and condition marks */
.worked { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.workedItem { display: flex; align-items: center; gap: 12px; font-size: 16px; line-height: 1.35; }
.ok, .no, .na {
  flex: none; width: 26px; height: 26px; border-radius: 999px;
  display: inline-flex; align-items: center; justify-content: center;
}
.ok { background: var(--ink); color: var(--sheet); }
.no { border: 1.5px solid var(--ink); color: var(--ink); }
.na { color: var(--ink-3); }

/* Variants table */
.tableWrap { overflow-x: auto; margin: 0 -6px; }
.table { width: 100%; min-width: 1240px; border-collapse: collapse; font-size: 14px; }
.table th, .table td {
  padding: 10px 6px; text-align: left; font-weight: 400; white-space: nowrap; vertical-align: middle;
  border-bottom: 1px solid var(--hair);
}
.table thead th {
  padding-top: 0; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-2);
  white-space: normal; vertical-align: bottom;
}
.table tbody tr:last-child th, .table tbody tr:last-child td { border-bottom: 0; }
.r { text-align: right !important; }
.c { text-align: center !important; width: 72px; }
.c .ok, .c .no, .c .na { width: 22px; height: 22px; }
.variant { font-weight: 500; }
.vs { font-size: 12px; color: var(--ink-2); }
.bestRow { background: var(--butter); }
.bestRow th:first-child { border-radius: 14px 0 0 14px; }
.bestRow td:last-child { border-radius: 0 14px 14px 0; }
.window {
  display: inline-flex; align-items: center; height: 22px; padding: 0 8px; border-radius: 999px;
  font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; background: var(--stone); color: var(--ink-2);
}
.window[data-window='test'] { background: var(--ink); color: var(--sheet); }

/* Markdown prose (escape-first HTML from lib/sera/markdown; headings arrive as h3/h4/h5) */
.proseSheet { gap: 16px; }
.prose { font-size: 16px; line-height: 1.6; color: var(--ink); max-width: 78ch; }
.prose > * + * { margin-top: 0.85em; }
.prose h3, .prose h4, .prose h5 { margin: 1.4em 0 0.4em; font-weight: 500; letter-spacing: -0.01em; line-height: 1.25; }
.prose h3 { font-size: 21px; }
.prose h4 { font-size: 18px; }
.prose h5 { font-size: 16px; }
.prose > :first-child { margin-top: 0; }
.prose p { margin: 0; }
.prose strong { font-weight: 600; }
.prose em { font-style: italic; }
.prose a { text-decoration: underline; text-decoration-color: var(--outline); text-underline-offset: 3px; }
.prose a:hover { text-decoration-color: var(--ink); }
.prose code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88em;
  padding: 1px 6px; border-radius: 6px; background: var(--stone);
}
.prose ul, .prose ol { margin: 0; padding-left: 1.3em; }
.prose li + li { margin-top: 0.3em; }
.prose table {
  display: block; overflow-x: auto; max-width: 100%; border-collapse: collapse;
  font-size: 14px; font-variant-numeric: tabular-nums;
}
.prose th, .prose td { padding: 7px 10px; border-bottom: 1px solid var(--hair); text-align: left; white-space: nowrap; }
.prose thead th { font-size: 12px; color: var(--ink-2); font-weight: 400; }
.prose td[align='right'], .prose th[align='right'],
.prose td[style*='right'], .prose th[style*='right'] { text-align: right; }

/* Insights */
.insights { list-style: none; margin: 0; padding: 0; display: grid; gap: 16px; }
.insight { padding-bottom: 16px; border-bottom: 1px solid var(--hair); display: grid; gap: 8px; }
.insight:last-child { padding-bottom: 0; border-bottom: 0; }
.insightHead { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.kindChip { height: 28px; padding: 0 11px; font-size: 13px; background: var(--stone); }
.insightTitle { flex: 1; min-width: 0; font-size: 17px; font-weight: 500; }
.insightDate { font-size: 13px; color: var(--ink-2); }

/* Technical detail: styled details/summary disclosure */
.techList { display: grid; gap: 8px; }
.tech { border-radius: 22px; background: var(--stone); }
.techSummary {
  list-style: none; display: flex; align-items: center; gap: 12px; padding: 10px 16px 10px 10px;
  cursor: pointer; border-radius: 22px; user-select: none;
}
.techSummary::-webkit-details-marker { display: none; }
.techSummary::marker { content: ''; }
.techSummary:hover { background: var(--hair); }
.techSummary:focus-visible { outline: 2px solid var(--coral); outline-offset: 2px; }
.techChevron {
  flex: none; width: 34px; height: 34px; border-radius: 999px; background: var(--sheet);
  display: inline-flex; align-items: center; justify-content: center; transition: transform 0.15s;
}
.tech[open] .techChevron { transform: rotate(90deg); }
.techName { font-size: 15px; font-weight: 500; }
.techSub { font-size: 13px; color: var(--ink-2); }
.techBody { padding: 4px 18px 18px; display: grid; gap: 14px; }
.techGrid { margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px 24px; }
.techRow { display: grid; gap: 2px; }
.techRow dt { font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-2); }
.techRow dd { margin: 0; font-size: 14px; overflow-wrap: anywhere; }
.config {
  margin: 0; padding: 14px 16px; border-radius: 16px; background: var(--sheet); color: var(--ink);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; line-height: 1.5;
  white-space: pre-wrap; overflow-wrap: anywhere; max-height: 360px; overflow: auto;
}

@media (min-width: 1024px) {
  .twoUp { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .textSheet, .chartSheet, .proseSheet { padding: 28px 30px 30px; border-radius: 40px; }
}
```

## Verification

**Build:**
```
cd /home/miftah/.worktrees/seer/sera-lab-site/web && npm ci && npx tsc --noEmit
```
Run `npm ci` first because the worktree has no `node_modules` (never symlink main's: Turbopack rejects a symlinked `node_modules`; the lockfile is identical to main's). Then run `NEXT_TELEMETRY_DISABLED=1 npx next build` to confirm that `/sera/methods` and `/sera/methods/[id]` compile; the build needs no env (Phase 3, verified).

**Reconciler check:** `view.ts`, `view.test.ts` and both `page.tsx` files, as written here, were type-checked (`tsc --noEmit` clean) and tested (26 tests green) on top of Phases 2–3's code and a real snapshot in a scratch tree.

**Tests:**
```
cd /home/miftah/.worktrees/seer/sera-lab-site/web && npx vitest run
```
`app/sera/methods/view.test.ts` and all existing tests should pass.

**Manual check:** run `npm run dev` and sign in as mahfuzh74@gmail.com.
- **`/sera/methods`:** 17 rows, with M0003, M0002 and M0001 first.
  - M0003 and M0002 show "Not tested yet".
  - M0001 shows 4 filled dots out of 6, with a "Beats SPY: missed · Luck check: missed" tooltip.
  - The filter buttons change `?show=`. "Alive" is empty on today's data, and the empty-state text shows.
- **`/sera/methods/M0001`:** four variants and four charts.
  - The SPY line is dotted.
  - The analysis markdown table renders.
  - Every `<details>` opens.
- **`/sera/methods/M0002`:** the idea and the "from M0001" chip; no charts. M0001's page shows "led to M0002".
- **`/sera/methods/H-P7A-F1`:** 14 variant lines, with the historical "What could go wrong" note.
- **`/sera/methods/NOPE`:** the Sera not-found page.

**Exit criteria:**
- `tsc --noEmit` and `vitest run` are green.
- Every id in `lab.methods` resolves to a page, and an unknown id gives `notFound()`.
- The list filters through icon-only, labelled, tooltipped `.seg` buttons.
- Phase-5 code hard-codes no gate threshold. Thresholds come only from `lab.gate`, and pass/miss comes only from `derive.conditionOk`.

## Handoffs

- **Phase 3 (resolved by the reconciler):** every call site now uses Phase 3's exported props (see **Assumed interfaces → Phase 3**): `LineChart` `area`/`dash`/`refLines: RefLine[]`, `ScatterChart` `regions`/`refY`/`ring` with point `id`s, `BarChart` `groups` of `items`, `Legend` `shape`, `Term` `term`+`definition`, string `PageHeader.title`, and `requireSera` on both pages.
- **Phase 2:** this plan relies on the `CONDITION_LABEL` strings as test expectations ('Beats SPY', 'Max drawdown', 'Profit factor', 'Trade count', 'Owner inputs', 'Luck check'). If phase 2 renames one, update `view.test.ts` to match.
- **Phase 7 (docs, not an R owned here):** document the `/sera/methods?show=` values (all, lab, historical, alive) in the Sera section of `web/package_readme.md`.
- **Unowned follow-up (outside this phase's spec):** a `sourceRef` that is a repo path (`docs/backtests/…md`, `docs/ROADMAP.md`) could link to `github.com/miftahulmahfuzh/seer/blob/main/<path>`, since the repo is public. The spec says to link only a URL or DOI, so this is left out.
- **Phase 4:** its overview has a similar return-vs-drawdown scatter of all dev trials. `hurdlePoints` is local to this phase. A shared builder could come later; there is no conflict now.

## Rollback

Delete `web/app/sera/methods/` (all six files). Nothing else imports from it. The phase-3 rail link to `/sera/methods` would then land on the Sera not-found page, which is harmless.
