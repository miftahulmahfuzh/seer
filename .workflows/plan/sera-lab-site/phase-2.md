# Phase 2: Web data layer for the snapshot

**Plan set:** `SERA_LAB_SITE_PLAN.md`
**Analysis:** `20261004-211729-H54F_code_analyzer.md`
**Satisfies:** R3, R5, R7. Every experiment in the snapshot becomes readable from typed, tested helpers (R3). Plain-language labels, the glossary and the safe markdown renderer serve "explain everything non-technically, with analysis and opinion" (R5). R7 (cross-cutting): every derivation the pages need (gate checks, funnel, progress, families, SPY rebase, drawdown, calendar years) is provided and tested.
**Depends on:** Phase 1 (`web/data/lab.json` must exist and follow the index's Interface Contract)
**Difficulty:** NORMAL
**Package:** `web/lib/sera`

---

## Goal

After this phase, `web/lib/sera/` turns the committed snapshot `web/data/lab.json` into everything the pages need. That means typed data with accessors, pure derivations (gate checks, funnel, progress, families, best variant, closest tries, SPY rebased to a trial's window, drawdown and calendar-year series), a plain-language glossary with status and kind labels, and a markdown-to-HTML renderer that escapes first. No page or component changes. Every helper is unit-tested on a small fixture, and `lab.ts` type-checks and loads against the real snapshot.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Phases 4–6 import these exact names.

**Deletes:** none
**Renames:** none
**Creates:**
- `web/lib/sera/types.ts`:
  - types: `LabSnapshot`, `LabMethod`, `LabTrial`, `LabInsight`, `LabSeen` (verbatim from the index), plus aliases `LabStatus = LabMethod['status']`, `InsightKind = LabInsight['kind']`, `SourceKind = LabMethod['sourceKind']`, `Gate = LabSnapshot['gate']`, `Benchmark = LabSnapshot['benchmark']`, `Point = [string, number]`
  - consts: `METHOD_STATUSES`, `INSIGHT_KINDS`, `SOURCE_KINDS` (readonly tuples, in contract order)
- `web/lib/sera/lab.ts`: `lab: LabSnapshot`, `methodById(id): LabMethod | undefined`, `trialsOf(methodId): LabTrial[]` (ordered by `n`), `insightsOf(methodId): LabInsight[]` (ordered by `id`), `childrenOf(methodId): LabMethod[]` (ordered by `id`).
- `web/lib/sera/derive.ts`, all pure, none reads `lab`:
  - condition keys and labels:
    - `CONDITION_KEYS = ['spy','drawdown','pf','trades','owner','dsr']`
    - `type ConditionKey`
    - `FAILURE_LABEL: Record<ConditionKey,string>` (the engine's strings in `trial.failed`)
    - `CONDITION_LABEL: Record<ConditionKey,string>` (plain labels: Beats SPY, Max drawdown, Profit factor, Trade count, Owner inputs, Luck check)
  - result types:
    - `type GateCheck = { key; label; value; target; ok: boolean | null }`
    - `type FunnelRow = { key; label; passing; measured; total }`
    - `type ProgressPoint = { n; passed; bestPassed; mar; bestMar }`
    - `type FamilyRow = { family; methodIds; trials; bestMar; bestPassed; historical }`
    - `type YearReturn = { year; ret }`
  - per-trial checks:
    - `devTrials(trials)`
    - `conditionOk(trial, key): boolean | null`
    - `gateChecks(trial, gate): GateCheck[]` (6, in order)
    - `conditionsPassed(trial): number`
    - `misses(trial): ConditionKey[]`
    - `excessCagr(trial): number | null`
  - aggregates:
    - `closest(trials, k): LabTrial[]`
    - `bestVariant(trials): LabTrial | null`
    - `funnel(trials): FunnelRow[]`
    - `progress(trials): ProgressPoint[]`
    - `families(methods, trials): FamilyRow[]`
    - `trialsByMethod(trials): Map<string, LabTrial[]>`
  - series:
    - `spyForWindow(trial, benchmark): Point[]`
    - `drawdownSeries(curve): Point[]`
    - `yearlyReturns(curve): YearReturn[]`
- `web/lib/sera/glossary.ts`:
  - glossary: `type GlossaryKey` (16 keys), `type GlossaryEntry = { term; plain }`, `GLOSSARY: Record<GlossaryKey, GlossaryEntry>`, `GLOSSARY_ORDER: GlossaryKey[]`
  - condition terms: `CONDITION_TERM: Record<ConditionKey, GlossaryKey>`
  - status, kind and source labels:
    - `type Tone = 'good'|'bad'|'wait'|'neutral'`
    - `STATUS_LABEL: Record<LabStatus, { label; meaning; tone }>`
    - `INSIGHT_KIND_LABEL: Record<InsightKind, { label; heading }>`
    - `SOURCE_KIND_LABEL: Record<SourceKind, string>`
- `web/lib/sera/markdown.ts`: `escapeHtml(s)`, `renderInline(s)`, `renderMarkdown(src)`. Each returns an HTML string for `dangerouslySetInnerHTML`. Heading levels are shifted down two: `#` renders as `<h3>`, `##` as `<h4>`, `###` as `<h5>`.
- `web/lib/sera/fixture.ts`: test-only builders `GATE`, `trial(over)`, `method(over)`.

**Signature changes:** none (all new)

**Deviations from the phase_scope text (deliberate):**
1. `lab.ts` imports `'../../data/lab.json'` (relative), not `'@/data/lab.json'`. `web/` has no vitest config, so vitest cannot resolve the `@/` alias, and `lab.test.ts` would fail. Every existing tested `lib/*.ts` uses relative imports for the same reason. For the same reason, `derive.ts` imports `'../format'`. Pages still import `@/lib/sera/lab`, because Next resolves the alias.
2. `GateCheck.ok` is `boolean | null`, not `boolean`. The 54 historical `H-*` trials have `dsr: null`, and their `failed` lacks `DSR >= 0.95` (they predate the luck check). `null` means "not measured" and counts as neither a pass nor a miss.
3. The derivations that only need pass/fail take no `gate` argument (`closest`, `bestVariant`, `funnel`, `progress`, `families`, `conditionsPassed`, `misses`). Pass/fail is read from the engine's `trial.failed` (invariant 5: the web never re-judges a trial). `gate` is used only for the display `target` strings in `gateChecks`.

**Requires (from earlier phases):** `web/data/lab.json` exists, with every key of the index's `LabSnapshot` contract (Phase 1). The `failed` strings are exactly the six labels listed in the index.
**Leaves alone (owned by others):** `web/lib/sera/access.ts` (+ test) (Phase 3); `web/components/**`, `web/app/**` (Phases 3–6); `engine/**`, `web/data/lab.json` (Phase 1); `web/lib/format.ts` (read-only reuse).

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/sera/types.ts:1` | create | contract types verbatim + aliases + status/kind/source tuples |
| `web/lib/sera/lab.ts:1` | create | loads `web/data/lab.json`, casts once, accessors |
| `web/lib/sera/derive.ts:1` | create | pure derivations |
| `web/lib/sera/glossary.ts:1` | create | glossary, status/kind/source labels |
| `web/lib/sera/markdown.ts:1` | create | escape-first markdown renderer |
| `web/lib/sera/fixture.ts:1` | create | test fixture builders |
| `web/lib/sera/derive.test.ts:1` | create | derivation tests |
| `web/lib/sera/glossary.test.ts:1` | create | coverage tests |
| `web/lib/sera/markdown.test.ts:1` | create | escaping, blocks, inline, tables |
| `web/lib/sera/lab.test.ts:1` | create | real snapshot loads and has contract keys |
| `web/lib/format.ts:13-14` | read only | `pct`, `signedPct` reused |

## Implementation Steps

### Step 0: Worktree setup
The worktree has no `web/node_modules`. `web/package-lock.json` is byte-identical to the main checkout's. Every web phase uses the same setup (reconciled; Phase 3 found that `next build` refuses a symlinked `node_modules`, so never symlink main's):
```sh
cd /home/miftah/.worktrees/seer/sera-lab-site/web && npm ci
```
Confirm that Phase 1 landed: `test -f /home/miftah/.worktrees/seer/sera-lab-site/web/data/lab.json`.

### Step 1: Contract types
**File:** `web/lib/sera/types.ts:1` (new)
**Code:**
```ts
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
```
**Impact:** none; new file.

### Step 2: Test fixture builders
**File:** `web/lib/sera/fixture.ts:1` (new)
**Code:**
```ts
/** Small builders for the sera unit tests. Never imported by app code. */
import type { Gate, LabMethod, LabTrial } from './types';

export const GATE: Gate = {
  maxDrawdown: 0.15,
  minProfitFactor: 1.3,
  minTrades: 100,
  dsrMin: 0.95,
  devStart: '1993-01-29',
  devEnd: '2015-10-16',
  testStart: '2015-10-19',
};

export function trial(over: Partial<LabTrial> = {}): LabTrial {
  return {
    n: 1,
    methodId: 'M0001',
    candidateId: 'M0001-V1',
    rulesId: 'rules-v1',
    allocatorId: 'alloc-v1',
    configText: '{}',
    window: 'dev',
    start: '1996-01-03',
    end: '2015-10-16',
    gitSha: 'abc1234',
    runAt: '2026-10-04T10:00:00+07:00',
    totalReturn: 3.2,
    cagr: 0.076,
    maxDrawdown: 0.12,
    profitFactor: 1.5,
    pfInfinite: false,
    trades: 240,
    sharpe: 0.8,
    exposure: 0.9,
    turnover: 2.1,
    worstYear: 2008,
    worstYearReturn: -0.11,
    spyTrReturn: 4.0,
    spyTrCagr: 0.079,
    mar: 0.63,
    failed: ['beats SPY TR'],
    eligible: false,
    dsr: 0.97,
    nTrialsAtRun: 55,
    curve: [['1996-01-31', 1]],
    ...over,
  };
}

export function method(over: Partial<LabMethod> = {}): LabMethod {
  return {
    id: 'M0001',
    name: 'Momentum, risk managed',
    family: 'stock-momentum-risk-managed',
    parentId: null,
    sourceKind: 'paper',
    sourceRef: 'https://example.com/paper',
    hypothesis: 'Scaling momentum by its own volatility cuts the crashes.',
    expectedFailure: null,
    status: 'rejected',
    analysis: '',
    verdict: '',
    blockedOn: '',
    created: '2026-10-04',
    updated: '2026-10-04',
    historical: false,
    ...over,
  };
}
```
**Impact:** none. `tsc` compiles it, and vitest never runs it directly.

### Step 3: Derivations
**File:** `web/lib/sera/derive.ts:1` (new)
**Code:**
```ts
/**
 * Pure reshaping of the lab snapshot for the /sera pages.
 *
 * Pass/fail always comes from the engine's `trial.failed` (invariant 5: the web never
 * re-judges a trial). The gate is used only to print targets.
 */
import { pct, signedPct } from '../format';
import type { Benchmark, Gate, LabMethod, LabTrial, Point } from './types';

export const CONDITION_KEYS = ['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr'] as const;
export type ConditionKey = (typeof CONDITION_KEYS)[number];

/** The engine's label for each condition, exactly as it appears in `trial.failed`. */
export const FAILURE_LABEL: Record<ConditionKey, string> = {
  spy: 'beats SPY TR',
  drawdown: 'max DD <= 15%',
  pf: 'PF >= 1.3',
  trades: '>= 100 trades',
  owner: 'owner inputs',
  dsr: 'DSR >= 0.95',
};

/** Plain-language name of each condition. */
export const CONDITION_LABEL: Record<ConditionKey, string> = {
  spy: 'Beats SPY',
  drawdown: 'Max drawdown',
  pf: 'Profit factor',
  trades: 'Trade count',
  owner: 'Owner inputs',
  dsr: 'Luck check',
};

/** `ok` is null when the condition was never measured (historical trials have no luck check). */
export type GateCheck = { key: ConditionKey; label: string; value: string; target: string; ok: boolean | null };
export type FunnelRow = { key: ConditionKey; label: string; passing: number; measured: number; total: number };
export type ProgressPoint = { n: number; passed: number; bestPassed: number; mar: number | null; bestMar: number | null };
export type FamilyRow = {
  family: string;
  methodIds: string[];
  trials: number;
  bestMar: number | null;
  bestPassed: number;
  historical: boolean;
};
export type YearReturn = { year: number; ret: number };

const DASH = '—';

const perYear = (v: number | null) => (v === null ? DASH : `${signedPct(v, 1)} a year`);
const num = (v: number) => String(Number(v.toFixed(4)));

export const devTrials = (trials: LabTrial[]): LabTrial[] => trials.filter((t) => t.window === 'dev');

const byN = (a: LabTrial, b: LabTrial) => a.n - b.n;

/** Higher MAR first; a missing MAR sorts last. */
function marDesc(a: LabTrial, b: LabTrial): number {
  if (a.mar === b.mar) return 0;
  if (a.mar === null) return 1;
  if (b.mar === null) return -1;
  return b.mar - a.mar;
}

/** true = passed, false = missed, null = not measured. */
export function conditionOk(trial: LabTrial, key: ConditionKey): boolean | null {
  if (trial.failed.includes(FAILURE_LABEL[key])) return false;
  if (key === 'dsr' && trial.dsr === null) return null;
  return true;
}

/** The six hurdles for one trial, in display order, with plain labels and display strings. */
export function gateChecks(trial: LabTrial, gate: Gate): GateCheck[] {
  const pf = trial.pfInfinite
    ? '∞ (no losing trades)'
    : trial.profitFactor === null
      ? DASH
      : trial.profitFactor.toFixed(2);
  const ownerMissed = conditionOk(trial, 'owner') === false;
  return [
    {
      key: 'spy',
      label: CONDITION_LABEL.spy,
      value: perYear(trial.cagr),
      target: trial.spyTrCagr === null ? 'more than SPY' : `more than ${perYear(trial.spyTrCagr)}`,
      ok: conditionOk(trial, 'spy'),
    },
    {
      key: 'drawdown',
      label: CONDITION_LABEL.drawdown,
      value: trial.maxDrawdown === null ? DASH : `${pct(trial.maxDrawdown, 1)} at worst`,
      target: `${pct(gate.maxDrawdown, 0)} or less`,
      ok: conditionOk(trial, 'drawdown'),
    },
    {
      key: 'pf',
      label: CONDITION_LABEL.pf,
      value: pf,
      target: `${num(gate.minProfitFactor)} or more`,
      ok: conditionOk(trial, 'pf'),
    },
    {
      key: 'trades',
      label: CONDITION_LABEL.trades,
      value: String(trial.trades),
      target: `${gate.minTrades} or more`,
      ok: conditionOk(trial, 'trades'),
    },
    {
      key: 'owner',
      label: CONDITION_LABEL.owner,
      value: ownerMissed ? 'needs owner input' : 'none needed',
      target: 'none needed',
      ok: conditionOk(trial, 'owner'),
    },
    {
      key: 'dsr',
      label: CONDITION_LABEL.dsr,
      value: trial.dsr === null ? 'not measured' : trial.dsr.toFixed(2),
      target: `${num(gate.dsrMin)} or more`,
      ok: conditionOk(trial, 'dsr'),
    },
  ];
}

/** How many of the six hurdles the trial cleared (not-measured counts as not cleared). */
export function conditionsPassed(trial: LabTrial): number {
  return CONDITION_KEYS.filter((k) => conditionOk(trial, k) === true).length;
}

/** The hurdles the trial missed, in display order. */
export function misses(trial: LabTrial): ConditionKey[] {
  return CONDITION_KEYS.filter((k) => conditionOk(trial, k) === false);
}

/** CAGR minus SPY total-return CAGR over the same window. */
export function excessCagr(trial: LabTrial): number | null {
  if (trial.cagr === null || trial.spyTrCagr === null) return null;
  return trial.cagr - trial.spyTrCagr;
}

/** The k dev trials nearest to eligible: most hurdles cleared, then best MAR, then earliest. */
export function closest(trials: LabTrial[], k: number): LabTrial[] {
  return devTrials(trials)
    .sort((a, b) => conditionsPassed(b) - conditionsPassed(a) || marDesc(a, b) || byN(a, b))
    .slice(0, k);
}

/** A method's best variant: fewest missed hurdles, then best MAR, then earliest. Dev trials first. */
export function bestVariant(trials: LabTrial[]): LabTrial | null {
  const dev = devTrials(trials);
  const pool = dev.length > 0 ? dev : [...trials];
  if (pool.length === 0) return null;
  return pool.sort((a, b) => misses(a).length - misses(b).length || marDesc(a, b) || byN(a, b))[0];
}

/** Per hurdle, how many dev trials cleared it. */
export function funnel(trials: LabTrial[]): FunnelRow[] {
  const dev = devTrials(trials);
  return CONDITION_KEYS.map((key) => {
    const oks = dev.map((t) => conditionOk(t, key));
    return {
      key,
      label: CONDITION_LABEL[key],
      passing: oks.filter((o) => o === true).length,
      measured: oks.filter((o) => o !== null).length,
      total: dev.length,
    };
  });
}

/** Over trial number: each dev trial's own score plus the best seen so far. */
export function progress(trials: LabTrial[]): ProgressPoint[] {
  const out: ProgressPoint[] = [];
  let bestPassed = 0;
  let bestMar: number | null = null;
  for (const t of devTrials(trials).sort(byN)) {
    const passed = conditionsPassed(t);
    bestPassed = Math.max(bestPassed, passed);
    if (t.mar !== null && (bestMar === null || t.mar > bestMar)) bestMar = t.mar;
    out.push({ n: t.n, passed, bestPassed, mar: t.mar, bestMar });
  }
  return out;
}

/** Methods and dev trials grouped by family; most-tried family first. */
export function families(methods: LabMethod[], trials: LabTrial[]): FamilyRow[] {
  const familyOf = new Map(methods.map((m) => [m.id, m.family]));
  const rows = new Map<string, FamilyRow>();
  for (const m of methods) {
    const row = rows.get(m.family);
    if (row) {
      row.methodIds.push(m.id);
      row.historical = row.historical && m.historical;
    } else {
      rows.set(m.family, {
        family: m.family,
        methodIds: [m.id],
        trials: 0,
        bestMar: null,
        bestPassed: 0,
        historical: m.historical,
      });
    }
  }
  for (const t of devTrials(trials)) {
    const family = familyOf.get(t.methodId);
    const row = family === undefined ? undefined : rows.get(family);
    if (!row) continue;
    row.trials += 1;
    row.bestPassed = Math.max(row.bestPassed, conditionsPassed(t));
    if (t.mar !== null && (row.bestMar === null || t.mar > row.bestMar)) row.bestMar = t.mar;
  }
  return [...rows.values()].sort((a, b) => b.trials - a.trials || a.family.localeCompare(b.family));
}

/** Trials grouped by method id, each list ordered by n. */
export function trialsByMethod(trials: LabTrial[]): Map<string, LabTrial[]> {
  const out = new Map<string, LabTrial[]>();
  for (const t of [...trials].sort(byN)) {
    const list = out.get(t.methodId);
    if (list) list.push(t);
    else out.set(t.methodId, [t]);
  }
  return out;
}

/** Value of the last point dated on or before `date`, or null when every point is later. */
function valueAtOrBefore(series: Point[], date: string): number | null {
  let lo = 0;
  let hi = series.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (series[mid][0] <= date) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found === -1 ? null : series[found][1];
}

/**
 * SPY total return over the trial's own window, rebased so the trial's start = 1.0, on the
 * trial's curve dates. Base = the last benchmark point dated on or before `trial.start`, or
 * the first point. Curve dates past the benchmark's end are dropped.
 */
export function spyForWindow(trial: LabTrial, benchmark: Benchmark): Point[] {
  const spy = benchmark.spyTr;
  if (spy.length === 0 || trial.curve.length === 0) return [];
  const base = valueAtOrBefore(spy, trial.start) ?? spy[0][1];
  const last = spy[spy.length - 1][0];
  const out: Point[] = [];
  for (const [d] of trial.curve) {
    if (d > last) break;
    const v = valueAtOrBefore(spy, d);
    if (v === null) continue;
    out.push([d, v / base]);
  }
  return out;
}

/** Underwater series: value / running peak − 1 (≤ 0). The peak starts at the base 1.0. */
export function drawdownSeries(curve: Point[]): Point[] {
  let peak = 1;
  return curve.map(([d, v]) => {
    peak = Math.max(peak, v);
    return [d, v / peak - 1];
  });
}

/** Calendar-year returns. The first year runs from the curve's base 1.0; the last may be partial. */
export function yearlyReturns(curve: Point[]): YearReturn[] {
  const out: YearReturn[] = [];
  let prev = 1;
  let year: number | null = null;
  let lastValue = 1;
  for (const [d, v] of curve) {
    const y = Number(d.slice(0, 4));
    if (year !== null && y !== year) {
      out.push({ year, ret: lastValue / prev - 1 });
      prev = lastValue;
    }
    year = y;
    lastValue = v;
  }
  if (year !== null) out.push({ year, ret: lastValue / prev - 1 });
  return out;
}
```
**Impact:** none; new file. `FAILURE_LABEL` hard-codes the engine's label strings, which are identifiers (index: "Failure labels inside `failed` are exactly …"), not thresholds. Displayed thresholds come from `gate`.

### Step 4: Glossary and labels
**File:** `web/lib/sera/glossary.ts:1` (new)
**Code:**
```ts
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
    plain: 'The chance a result is real skill rather than the luckiest of many tries, after counting every try the lab has made.',
  },
  tries: {
    term: 'N (tries)',
    plain: 'Every test the lab has ever run, counted so the luck check can discount a winner found by trying many things.',
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
```
**Impact:** none. `Record<…>` makes a missing status, kind or source a compile error. The test also checks at runtime.

### Step 5: Markdown renderer
**File:** `web/lib/sera/markdown.ts:1` (new)
**Code:**
```ts
/**
 * Escape-first markdown -> HTML for lab analysis text.
 *
 * Supported: # / ## / ### headings (rendered h3 / h4 / h5 so the page keeps h1–h2), paragraphs,
 * **bold**, *italic*, `code`, "- " and "1. " lists, pipe tables with a header separator, and
 * [text](http(s) url) links. Nothing else. All source text is HTML-escaped before any markup is
 * added, so raw HTML in the source always renders as text.
 */

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

const LINK = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
const HEADING = /^(#{1,3})\s+(.+)$/;
const UL = /^\s*-\s+(.*)$/;
const OL = /^\s*\d+\.\s+(.*)$/;
const TABLE_SEP = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

type Align = 'left' | 'center' | 'right' | null;
type List = { tag: 'ul' | 'ol'; items: string[] };

/** Bold and italic on already-escaped text. */
function emphasis(s: string): string {
  return s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*([^*\s][^*]*?)\*/g, '<em>$1</em>');
}

/** Links (http/https only) with emphasis inside and around them, on already-escaped text. */
function linksAndEmphasis(s: string): string {
  let out = '';
  let last = 0;
  for (const m of s.matchAll(LINK)) {
    const at = m.index ?? 0;
    out += emphasis(s.slice(last, at));
    out += `<a href="${m[2]}" rel="noopener noreferrer" target="_blank">${emphasis(m[1])}</a>`;
    last = at + m[0].length;
  }
  return out + emphasis(s.slice(last));
}

/** One line of inline markdown -> HTML. Code spans are left untouched inside. */
export function renderInline(text: string): string {
  return escapeHtml(text)
    .split(/`([^`]+)`/)
    .map((part, i) => (i % 2 === 1 ? `<code>${part}</code>` : linksAndEmphasis(part)))
    .join('');
}

function cells(row: string): string[] {
  let r = row.trim();
  if (r.startsWith('|')) r = r.slice(1);
  if (r.endsWith('|')) r = r.slice(0, -1);
  return r.split('|').map((c) => c.trim());
}

function aligns(separator: string): Align[] {
  return cells(separator).map((c) => {
    const left = c.startsWith(':');
    const right = c.endsWith(':');
    if (left && right) return 'center';
    if (right) return 'right';
    if (left) return 'left';
    return null;
  });
}

function cell(tag: 'th' | 'td', text: string, align: Align): string {
  const style = align ? ` style="text-align:${align}"` : '';
  return `<${tag}${style}>${renderInline(text)}</${tag}>`;
}

class Blocks {
  out: string[] = [];
  para: string[] = [];
  list: List | null = null;

  flushPara(): void {
    if (this.para.length > 0) {
      this.out.push(`<p>${renderInline(this.para.join(' '))}</p>`);
      this.para = [];
    }
  }

  flushList(): void {
    if (this.list) {
      const items = this.list.items.map((it) => `<li>${renderInline(it)}</li>`).join('');
      this.out.push(`<${this.list.tag}>${items}</${this.list.tag}>`);
      this.list = null;
    }
  }

  flush(): void {
    this.flushPara();
    this.flushList();
  }
}

/** Markdown source -> HTML string, safe for dangerouslySetInnerHTML. */
export function renderMarkdown(src: string): string {
  const lines = src.replace(/\r\n?/g, '\n').split('\n');
  const b = new Blocks();
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim() === '') {
      b.flush();
      continue;
    }
    const h = HEADING.exec(line);
    if (h) {
      b.flush();
      const level = h[1].length + 2;
      b.out.push(`<h${level}>${renderInline(h[2].trim())}</h${level}>`);
      continue;
    }
    const next = lines[i + 1];
    if (line.includes('|') && next !== undefined && next.includes('|') && TABLE_SEP.test(next)) {
      b.flush();
      const head = cells(line);
      const al = aligns(next);
      const body: string[][] = [];
      let j = i + 2;
      while (j < lines.length && lines[j].trim() !== '' && lines[j].includes('|')) {
        body.push(cells(lines[j]));
        j++;
      }
      i = j - 1;
      const row = (r: string[], tag: 'th' | 'td') =>
        `<tr>${head.map((_, c) => cell(tag, r[c] ?? '', al[c] ?? null)).join('')}</tr>`;
      b.out.push(`<table><thead>${row(head, 'th')}</thead><tbody>${body.map((r) => row(r, 'td')).join('')}</tbody></table>`);
      continue;
    }
    const ul = UL.exec(line);
    const ol = ul ? null : OL.exec(line);
    const item = ul ?? ol;
    if (item) {
      b.flushPara();
      const tag = ul ? 'ul' : 'ol';
      if (b.list && b.list.tag !== tag) b.flushList();
      if (!b.list) b.list = { tag, items: [] };
      b.list.items.push(item[1]);
      continue;
    }
    if (b.list && /^\s{2,}\S/.test(line)) {
      b.list.items[b.list.items.length - 1] += ' ' + line.trim();
      continue;
    }
    b.flushList();
    b.para.push(line.trim());
  }
  b.flush();
  return b.out.join('\n');
}
```
**Impact:** none; new file. No new dependency (invariant 7).

### Step 6: Snapshot loader and accessors
**File:** `web/lib/sera/lab.ts:1` (new)
**Code:**
```ts
/**
 * The method-lab snapshot, bundled at build time. Regenerated by `lab stage` on every lab commit.
 * Import only from server components: the JSON is large and must not ship to the browser.
 */
import raw from '../../data/lab.json';
import { trialsByMethod } from './derive';
import type { LabInsight, LabMethod, LabSnapshot, LabTrial } from './types';

export const lab = raw as unknown as LabSnapshot;

const methodsById = new Map(lab.methods.map((m) => [m.id, m]));
const trialsById = trialsByMethod(lab.trials);

export const methodById = (id: string): LabMethod | undefined => methodsById.get(id);

/** A method's trials, ordered by n. */
export const trialsOf = (methodId: string): LabTrial[] => trialsById.get(methodId) ?? [];

/** Insights tied to a method, ordered by id. */
export const insightsOf = (methodId: string): LabInsight[] =>
  lab.insights.filter((i) => i.methodId === methodId).sort((a, b) => a.id - b.id);

/** Methods whose parent is `methodId`, ordered by id. */
export const childrenOf = (methodId: string): LabMethod[] =>
  lab.methods.filter((m) => m.parentId === methodId).sort((a, b) => a.id.localeCompare(b.id));
```
**Impact:** this adds the build-time dependency on `web/data/lab.json`. It must exist (Phase 1), or `tsc` fails with "Cannot find module".

### Step 7: Tests: derive
**File:** `web/lib/sera/derive.test.ts:1` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import {
  bestVariant,
  closest,
  conditionsPassed,
  drawdownSeries,
  excessCagr,
  families,
  funnel,
  gateChecks,
  misses,
  progress,
  spyForWindow,
  trialsByMethod,
  yearlyReturns,
} from './derive';
import { GATE, method, trial } from './fixture';
import type { Benchmark } from './types';

describe('gateChecks', () => {
  it('lists six hurdles in order with plain labels, values and targets from the gate', () => {
    const checks = gateChecks(trial(), GATE);
    expect(checks.map((c) => c.key)).toEqual(['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr']);
    expect(checks.map((c) => c.label)).toEqual([
      'Beats SPY',
      'Max drawdown',
      'Profit factor',
      'Trade count',
      'Owner inputs',
      'Luck check',
    ]);
    expect(checks[0]).toEqual({
      key: 'spy',
      label: 'Beats SPY',
      value: '+7.6% a year',
      target: 'more than +7.9% a year',
      ok: false,
    });
    expect(checks[1]).toMatchObject({ value: '12.0% at worst', target: '15% or less', ok: true });
    expect(checks[2]).toMatchObject({ value: '1.50', target: '1.3 or more', ok: true });
    expect(checks[3]).toMatchObject({ value: '240', target: '100 or more', ok: true });
    expect(checks[4]).toMatchObject({ value: 'none needed', target: 'none needed', ok: true });
    expect(checks[5]).toMatchObject({ value: '0.97', target: '0.95 or more', ok: true });
  });

  it('reads targets from the gate, not constants', () => {
    const checks = gateChecks(trial(), { ...GATE, maxDrawdown: 0.2, minProfitFactor: 1.5, minTrades: 50 });
    expect(checks[1].target).toBe('20% or less');
    expect(checks[2].target).toBe('1.5 or more');
    expect(checks[3].target).toBe('50 or more');
  });

  it('shows an infinite profit factor and owner-input misses plainly', () => {
    const checks = gateChecks(
      trial({ profitFactor: null, pfInfinite: true, failed: ['owner inputs'] }),
      GATE,
    );
    expect(checks[2].value).toBe('∞ (no losing trades)');
    expect(checks[4]).toMatchObject({ value: 'needs owner input', ok: false });
  });

  it('marks an unmeasured luck check as null, and a failed one as false', () => {
    const historical = trial({ dsr: null, failed: ['beats SPY TR'] });
    expect(gateChecks(historical, GATE)[5]).toMatchObject({ value: 'not measured', ok: null });
    const unlucky = trial({ dsr: 0.4, failed: ['DSR >= 0.95'] });
    expect(gateChecks(unlucky, GATE)[5]).toMatchObject({ value: '0.40', ok: false });
  });
});

describe('conditionsPassed / misses / excessCagr', () => {
  it('counts only cleared hurdles and lists misses in order', () => {
    const t = trial({ dsr: null, failed: ['beats SPY TR', 'PF >= 1.3'] });
    expect(conditionsPassed(t)).toBe(3);
    expect(misses(t)).toEqual(['spy', 'pf']);
    expect(conditionsPassed(trial({ failed: [] }))).toBe(6);
  });

  it('subtracts SPY CAGR', () => {
    expect(excessCagr(trial())).toBeCloseTo(-0.003, 10);
    expect(excessCagr(trial({ cagr: null }))).toBeNull();
  });
});

describe('closest / bestVariant', () => {
  const a = trial({ n: 1, failed: ['beats SPY TR'], mar: 0.63 });
  const b = trial({ n: 2, failed: [], mar: 0.2 });
  const c = trial({ n: 3, failed: ['beats SPY TR'], mar: 0.9 });
  const t = trial({ n: 4, window: 'test', failed: [], mar: 5 });

  it('ranks dev trials by hurdles cleared, then MAR', () => {
    expect(closest([a, b, c, t], 2).map((x) => x.n)).toEqual([2, 3]);
    expect(closest([a, b, c, t], 10).map((x) => x.n)).toEqual([2, 3, 1]);
  });

  it('picks fewest misses first, then MAR, then earliest', () => {
    const worse = trial({ n: 5, failed: ['beats SPY TR', 'PF >= 1.3'], mar: 2 });
    expect(bestVariant([worse, a])?.n).toBe(1);
    expect(bestVariant([a, c])?.n).toBe(3);
    expect(bestVariant([trial({ n: 7, mar: null }), trial({ n: 6, mar: null })])?.n).toBe(6);
    expect(bestVariant([])).toBeNull();
  });

  it('prefers dev trials over test trials', () => {
    expect(bestVariant([a, t])?.n).toBe(1);
    expect(bestVariant([t])?.n).toBe(4);
  });
});

describe('funnel', () => {
  it('counts dev trials clearing each hurdle', () => {
    const rows = funnel([
      trial({ n: 1, failed: ['beats SPY TR'], dsr: 0.97 }),
      trial({ n: 2, failed: ['max DD <= 15%', 'DSR >= 0.95'], dsr: 0.5 }),
      trial({ n: 3, failed: ['beats SPY TR'], dsr: null }),
      trial({ n: 4, window: 'test', failed: [] }),
    ]);
    expect(rows.map((r) => [r.key, r.passing, r.measured, r.total])).toEqual([
      ['spy', 1, 3, 3],
      ['drawdown', 2, 3, 3],
      ['pf', 3, 3, 3],
      ['trades', 3, 3, 3],
      ['owner', 3, 3, 3],
      ['dsr', 1, 2, 3],
    ]);
    expect(rows[5].label).toBe('Luck check');
  });
});

describe('progress', () => {
  it('tracks the best so far over trial number', () => {
    const t1 = trial({ n: 1, failed: ['beats SPY TR', 'PF >= 1.3'], mar: 0.5 });
    const t2 = trial({ n: 2, failed: ['beats SPY TR'], mar: 0.3 });
    const t3 = trial({ n: 3, failed: ['beats SPY TR', 'PF >= 1.3', '>= 100 trades'], mar: null });
    expect(progress([t3, t1, t2])).toEqual([
      { n: 1, passed: 4, bestPassed: 4, mar: 0.5, bestMar: 0.5 },
      { n: 2, passed: 5, bestPassed: 5, mar: 0.3, bestMar: 0.5 },
      { n: 3, passed: 3, bestPassed: 5, mar: null, bestMar: 0.5 },
    ]);
    expect(progress([])).toEqual([]);
  });
});

describe('families', () => {
  it('groups methods and dev trials by family, most tried first', () => {
    const methods = [
      method({ id: 'H-A', family: 'bracket-swing', historical: true }),
      method({ id: 'H-A2', family: 'bracket-swing', historical: true }),
      method({ id: 'M0001', family: 'momentum', historical: false }),
      method({ id: 'M0002', family: 'value', historical: false }),
    ];
    const rows = families(methods, [
      trial({ n: 1, methodId: 'H-A', mar: 0.2, failed: ['beats SPY TR', 'PF >= 1.3'] }),
      trial({ n: 2, methodId: 'H-A2', mar: 0.4, failed: ['beats SPY TR', 'PF >= 1.3'] }),
      trial({ n: 3, methodId: 'M0001', mar: 0.6, failed: ['beats SPY TR'] }),
      trial({ n: 4, methodId: 'M0001', mar: null, failed: ['beats SPY TR'] }),
      trial({ n: 5, methodId: 'GONE', mar: 9 }),
    ]);
    expect(rows).toEqual([
      { family: 'bracket-swing', methodIds: ['H-A', 'H-A2'], trials: 2, bestMar: 0.4, bestPassed: 4, historical: true },
      { family: 'momentum', methodIds: ['M0001'], trials: 2, bestMar: 0.6, bestPassed: 5, historical: false },
      { family: 'value', methodIds: ['M0002'], trials: 0, bestMar: null, bestPassed: 0, historical: false },
    ]);
  });
});

describe('trialsByMethod', () => {
  it('groups by method id ordered by n', () => {
    const m = trialsByMethod([trial({ n: 3 }), trial({ n: 1 }), trial({ n: 2, methodId: 'H-B' })]);
    expect(m.get('M0001')?.map((t) => t.n)).toEqual([1, 3]);
    expect(m.get('H-B')?.map((t) => t.n)).toEqual([2]);
  });
});

describe('spyForWindow', () => {
  const benchmark: Benchmark = {
    spyTr: [
      ['1993-01-29', 1],
      ['1995-12-29', 2],
      ['1996-01-31', 2.2],
      ['1996-02-29', 2.1],
    ],
    spyPrice: [],
  };

  it('rebases SPY to the last point on or before the trial start, on the trial dates', () => {
    const t = trial({
      start: '1996-01-03',
      curve: [
        ['1996-01-31', 0.99],
        ['1996-02-15', 1.0],
        ['1996-02-29', 1.01],
        ['1996-03-29', 1.02],
      ],
    });
    const out = spyForWindow(t, benchmark);
    expect(out.map(([d]) => d)).toEqual(['1996-01-31', '1996-02-15', '1996-02-29']);
    expect(out[0][1]).toBeCloseTo(1.1, 10);
    expect(out[1][1]).toBeCloseTo(1.1, 10);
    expect(out[2][1]).toBeCloseTo(1.05, 10);
  });

  it('uses the first point when the trial starts before the benchmark', () => {
    const t = trial({ start: '1990-01-01', curve: [['1993-01-29', 1], ['1995-12-29', 1.5]] });
    expect(spyForWindow(t, benchmark)).toEqual([
      ['1993-01-29', 1],
      ['1995-12-29', 2],
    ]);
  });

  it('returns nothing for an empty curve', () => {
    expect(spyForWindow(trial({ curve: [] }), benchmark)).toEqual([]);
  });
});

describe('drawdownSeries', () => {
  it('measures each point against the running peak, starting from 1.0', () => {
    const out = drawdownSeries([
      ['a', 1.1],
      ['b', 0.99],
      ['c', 1.21],
    ]);
    expect(out[0]).toEqual(['a', 0]);
    expect(out[1][1]).toBeCloseTo(-0.1, 10);
    expect(out[2]).toEqual(['c', 0]);
    expect(drawdownSeries([['a', 0.9]])[0][1]).toBeCloseTo(-0.1, 10);
  });
});

describe('yearlyReturns', () => {
  it('chains calendar years from the base 1.0', () => {
    const out = yearlyReturns([
      ['1996-06-28', 1.1],
      ['1996-12-31', 1.2],
      ['1997-06-30', 1.5],
      ['1997-12-31', 1.8],
      ['1998-03-31', 1.62],
    ]);
    expect(out.map((y) => y.year)).toEqual([1996, 1997, 1998]);
    expect(out[0].ret).toBeCloseTo(0.2, 10);
    expect(out[1].ret).toBeCloseTo(0.5, 10);
    expect(out[2].ret).toBeCloseTo(-0.1, 10);
    expect(yearlyReturns([])).toEqual([]);
  });
});
```
**Impact:** none.

Arithmetic checks for the expectations:
- `closest`: a has 5 passed at MAR 0.63, b has 6 at 0.2, c has 5 at 0.9. Order: b, c, a.
- `bestVariant([a, c])`: both miss 1, and c has the higher MAR.
- `families`, momentum: n=3 misses spy only, with dsr 0.97 → 5 passed.
- `families`, bracket-swing: misses spy and pf → 4 passed.
- `families`: the `GONE` method is ignored.

### Step 8: Tests: glossary
**File:** `web/lib/sera/glossary.test.ts:1` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { CONDITION_KEYS } from './derive';
import {
  CONDITION_TERM,
  GLOSSARY,
  GLOSSARY_ORDER,
  INSIGHT_KIND_LABEL,
  SOURCE_KIND_LABEL,
  STATUS_LABEL,
} from './glossary';
import { INSIGHT_KINDS, METHOD_STATUSES, SOURCE_KINDS } from './types';

const sentences = (s: string) => s.trim().split(/[.!?](?=\s|$)/).filter((x) => x.trim() !== '');

describe('glossary', () => {
  it('defines every required term in exactly one plain sentence', () => {
    const keys = Object.keys(GLOSSARY).sort();
    expect(keys).toEqual(
      [
        'return',
        'cagr',
        'maxDrawdown',
        'profitFactor',
        'trades',
        'sharpe',
        'mar',
        'dsr',
        'tries',
        'exposure',
        'turnover',
        'devWindow',
        'testWindow',
        'paperTrading',
        'spyTr',
        'ownerInputs',
      ].sort(),
    );
    for (const entry of Object.values(GLOSSARY)) {
      expect(entry.term.length).toBeGreaterThan(0);
      expect(entry.plain.endsWith('.')).toBe(true);
      expect(sentences(entry.plain)).toHaveLength(1);
      expect(entry.plain).not.toMatch(/\d+(\.\d+)?%/);
    }
  });

  it('orders every term exactly once', () => {
    expect([...GLOSSARY_ORDER].sort()).toEqual(Object.keys(GLOSSARY).sort());
  });

  it('explains every gate condition', () => {
    for (const k of CONDITION_KEYS) expect(GLOSSARY[CONDITION_TERM[k]]).toBeDefined();
  });
});

describe('labels', () => {
  it('covers every method status', () => {
    expect(Object.keys(STATUS_LABEL).sort()).toEqual([...METHOD_STATUSES].sort());
    for (const s of METHOD_STATUSES) {
      expect(STATUS_LABEL[s].label.length).toBeGreaterThan(0);
      expect(STATUS_LABEL[s].meaning.endsWith('.')).toBe(true);
      expect(['good', 'bad', 'wait', 'neutral']).toContain(STATUS_LABEL[s].tone);
    }
  });

  it('covers every insight kind, synthesis included', () => {
    expect(Object.keys(INSIGHT_KIND_LABEL).sort()).toEqual([...INSIGHT_KINDS].sort());
    expect(INSIGHT_KIND_LABEL.synthesis.heading).toBe('Batch summaries');
  });

  it('covers every source kind', () => {
    expect(Object.keys(SOURCE_KIND_LABEL).sort()).toEqual([...SOURCE_KINDS].sort());
  });
});
```

### Step 9: Tests: markdown
**File:** `web/lib/sera/markdown.test.ts:1` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { escapeHtml, renderInline, renderMarkdown } from './markdown';

describe('escaping', () => {
  it('never passes raw HTML through', () => {
    expect(renderMarkdown('<script>alert(1)</script>')).toBe('<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>');
    expect(renderMarkdown('**<b>x</b>**')).toBe('<p><strong>&lt;b&gt;x&lt;/b&gt;</strong></p>');
    expect(renderMarkdown('# <img src=x onerror=alert(1)>')).toBe('<h3>&lt;img src=x onerror=alert(1)&gt;</h3>');
    expect(escapeHtml(`&<>"'`)).toBe('&amp;&lt;&gt;&quot;&#39;');
  });

  it('links http(s) only, escaped, opening in a new tab', () => {
    expect(renderInline('[SSRN](https://papers.ssrn.com/a?b=1&c=2)')).toBe(
      '<a href="https://papers.ssrn.com/a?b=1&amp;c=2" rel="noopener noreferrer" target="_blank">SSRN</a>',
    );
    expect(renderInline('[x](javascript:alert(1))')).toBe('[x](javascript:alert(1))');
    expect(renderInline('[x](data:text/html,hi)')).toBe('[x](data:text/html,hi)');
    const sneaky = renderInline('[x](https://a.com/"onmouseover=alert(1))');
    expect(sneaky).toContain('&quot;onmouseover');
    expect(sneaky).not.toMatch(/href="[^"]*"onmouseover/);
  });
});

describe('inline', () => {
  it('renders bold, italic and code, leaving code contents alone', () => {
    expect(renderInline('**bold** and *it*')).toBe('<strong>bold</strong> and <em>it</em>');
    expect(renderInline('use `a*b*c` here')).toBe('use <code>a*b*c</code> here');
    expect(renderInline('2 * 3 * 4')).toBe('2 * 3 * 4');
  });
});

describe('blocks', () => {
  it('shifts headings down two levels and only knows three', () => {
    expect(renderMarkdown('# A\n## B\n### 2026-10-04\nText')).toBe(
      '<h3>A</h3>\n<h4>B</h4>\n<h5>2026-10-04</h5>\n<p>Text</p>',
    );
    expect(renderMarkdown('#### x')).toBe('<p>#### x</p>');
  });

  it('joins paragraph lines and splits on blank lines', () => {
    expect(renderMarkdown('a\nb\n\nc')).toBe('<p>a b</p>\n<p>c</p>');
    expect(renderMarkdown('a\r\nb')).toBe('<p>a b</p>');
  });

  it('renders bullet and numbered lists, with indented continuations', () => {
    expect(renderMarkdown('- a\n- b\n\n1. x\n2. y')).toBe('<ul><li>a</li><li>b</li></ul>\n<ol><li>x</li><li>y</li></ol>');
    expect(renderMarkdown('- a\n  more\n- b\nafter')).toBe('<ul><li>a more</li><li>b</li></ul>\n<p>after</p>');
  });

  it('renders pipe tables with alignment and inline markup', () => {
    const md = '| Variant | CAGR |\n|---|---:|\n| V1 | 7.6% |\n| V2 | **8%** |';
    expect(renderMarkdown(md)).toBe(
      '<table><thead><tr><th>Variant</th><th style="text-align:right">CAGR</th></tr></thead>' +
        '<tbody><tr><td>V1</td><td style="text-align:right">7.6%</td></tr>' +
        '<tr><td>V2</td><td style="text-align:right"><strong>8%</strong></td></tr></tbody></table>',
    );
  });

  it('pads short rows, ends a table at a blank line, and leaves a lone pipe as text', () => {
    expect(renderMarkdown('| a | b |\n| --- | --- |\n| 1 |\n\nnext')).toBe(
      '<table><thead><tr><th>a</th><th>b</th></tr></thead><tbody><tr><td>1</td><td></td></tr></tbody></table>\n<p>next</p>',
    );
    expect(renderMarkdown('a | b')).toBe('<p>a | b</p>');
  });

  it('escapes table cells', () => {
    expect(renderMarkdown('| <i>x</i> |\n|---|\n| y |')).toContain('<th>&lt;i&gt;x&lt;/i&gt;</th>');
  });
});
```

### Step 10: Tests: real snapshot
**File:** `web/lib/sera/lab.test.ts:1` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { childrenOf, insightsOf, lab, methodById, trialsOf } from './lab';
import { INSIGHT_KINDS, METHOD_STATUSES, SOURCE_KINDS } from './types';

describe('lab snapshot (web/data/lab.json)', () => {
  it('has exactly the contract keys', () => {
    expect(lab.version).toBe(1);
    expect(Object.keys(lab).sort()).toEqual(
      ['asOf', 'benchmark', 'data', 'gate', 'ideasSeen', 'insights', 'methods', 'summary', 'trials', 'version'].sort(),
    );
    expect(typeof lab.asOf).toBe('string');
    for (const k of ['maxDrawdown', 'minProfitFactor', 'minTrades', 'dsrMin'] as const) {
      expect(Number.isFinite(lab.gate[k])).toBe(true);
    }
    expect(lab.gate.devStart).toBe('1993-01-29');
  });

  it('starts the SPY benchmark at 1.0 on 1993-01-29', () => {
    expect(lab.benchmark.spyTr[0]).toEqual(['1993-01-29', 1]);
    expect(lab.benchmark.spyTr.length).toBeGreaterThan(100);
  });

  it('agrees with its own summary', () => {
    expect(lab.summary.methods).toBe(lab.methods.length);
    expect(lab.summary.devTrials).toBe(lab.trials.filter((t) => t.window === 'dev').length);
    expect(lab.summary.insights).toBe(lab.insights.length);
  });

  it('uses only known statuses, kinds and sources', () => {
    for (const m of lab.methods) {
      expect(METHOD_STATUSES).toContain(m.status);
      expect(SOURCE_KINDS).toContain(m.sourceKind);
      expect(m.historical).toBe(m.id.startsWith('H-'));
    }
    for (const i of lab.insights) expect(INSIGHT_KINDS).toContain(i.kind);
  });

  it('links every trial to a method and parses curves as [date, value] pairs', () => {
    for (const t of lab.trials) {
      expect(methodById(t.methodId)).toBeDefined();
      expect(Array.isArray(t.failed)).toBe(true);
      for (const [d, v] of t.curve) {
        expect(d).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(typeof v).toBe('number');
      }
    }
  });

  it('serves accessors consistent with the raw lists', () => {
    for (const m of lab.methods) {
      expect(methodById(m.id)).toBe(m);
      const ts = trialsOf(m.id);
      expect(ts.every((t) => t.methodId === m.id)).toBe(true);
      expect(ts.map((t) => t.n)).toEqual([...ts.map((t) => t.n)].sort((a, b) => a - b));
      expect(insightsOf(m.id).every((i) => i.methodId === m.id)).toBe(true);
      expect(childrenOf(m.id).every((c) => c.parentId === m.id)).toBe(true);
    }
    expect(trialsOf('NOPE')).toEqual([]);
    expect(methodById('NOPE')).toBeUndefined();
  });
});
```
**Impact:** this pins the Phase 1 contract on the web side. If Phase 1 changes a key name, this test fails.

## Verification

**Setup:** Step 0. Run `npm ci` in the worktree's `web/` (the lockfile is identical to main's; never symlink main's `node_modules`).
**Build:** `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npx vitest run` (all existing tests plus the four new `lib/sera/*.test.ts`)
**Manual check:** none (no UI). Optionally run `npx vitest run lib/sera` to see only this phase.
**Exit criteria:**
- tsc is clean, and vitest is green, including `lab.test.ts` against the real `web/data/lab.json`.
- `web/lib/sera/` contains exactly `types.ts`, `lab.ts`, `derive.ts`, `glossary.ts`, `markdown.ts`, `fixture.ts` and the four tests. Phase 3 adds `access.ts` alongside.
- Nothing outside `web/lib/sera/` changed.

## Handoffs

- **Phases 4–6 (consumers):**
  - Import `lab` and its accessors only from server components (`@/lib/sera/lab`). The JSON is large.
  - Render markdown as `<div className={…} dangerouslySetInnerHTML={{ __html: renderMarkdown(m.analysis) }} />`. Style `h3`/`h4`/`h5`, `table`, `code` and `a` inside that div in the page's CSS module.
  - `GateCheck.ok === null` means "not measured" (historical trials, luck check). Show it as neutral, not as a miss.
  - Glossary text for `data-tip` comes from `GLOSSARY[key].plain`. Hurdle tips come via `CONDITION_TERM`.
- **Phase 3 (reconciled):**
  - Phase 3's `Term` takes plain `term` + `definition` strings and never imports `glossary.ts`. Pages feed it `GLOSSARY[k].term` / `GLOSSARY[k].plain` through a small local `T({ k: GlossaryKey })` wrapper (Phases 4–6). Nothing changes here.
  - Status chips can use `STATUS_LABEL[status].tone` (`good|bad|wait|neutral`) for colours.
- **Phase 1 (reconciled, agrees):**
  - `lab.test.ts` asserts that `summary.methods`, `summary.devTrials` and `summary.insights` equal the list lengths, and that `benchmark.spyTr[0]` equals `['1993-01-29', 1]` exactly. Phase 1's `snapshot()` counts every method (historical included), every dev trial and every insight, and its own test asserts `spy_tr[0] == ["1993-01-29", 1.0]`. Checked against a snapshot built with Phase 1's code from the committed `lab/lab.sqlite`: all six `lab.test.ts` tests pass.
  - `summary.byStatus` holds all nine statuses with zeros (Phase 1); `Record<string, number>` covers it. `asOf` is `""` for an empty lab, never `null`; `string` covers it. Points are `[string, number]` tuples, as typed.
- **Out of scope (R7, any later phase):** a `vitest.config.ts` with the `@/` alias would let `lib/sera` use `@/` imports. That is a cross-cutting tooling change and is not done here.

## Rollback

Delete `web/lib/sera/{types,lab,derive,glossary,markdown,fixture}.ts` and the four `*.test.ts` files, or `git revert` the phase commit. Nothing else references them until Phases 4–6 land, and those must be reverted first.
