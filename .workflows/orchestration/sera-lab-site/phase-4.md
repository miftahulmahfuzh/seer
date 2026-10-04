# Phase 4: Overview page

**Plan set:** `SERA_LAB_SITE_PLAN.md`
**Analysis:** `20261004-211729-H54F_code_analyzer.md`
**Satisfies:** R1, R4, R5, R7. The `/sera` landing page shows the state of the search on desktop: seven charted sections, each with a plain caption. R7 (cross-cutting): every dev trial is plotted, and every headline number is shown.
**Depends on:** Phase 2 (data layer), Phase 3 (shell, gate, chart kit). Phase 1 is implied through Phase 2: `web/data/lab.json` exists.
**Difficulty:** HARD
**Package:** `web/app/sera`

---

## Goal

`/sera` renders a desktop-first Overview. It is a 12-column grid of Seer v2 sheets at 1024 px and wider, and a single column below that. The page says where the search stands, where every try landed against the gate, which hurdles are hardest, whether results are improving, how the luck bar rises with N, which families have been explored, and which lab methods were touched most recently. Before this phase, `/sera` has the layout and gate from Phase 3 but no `page.tsx`, so it returns a 404. All shaping is pure and unit-tested in `overview.ts`. The page only lays out components.

## Interfaces used (reconciled)

The draft of this plan coded against assumed Phase 2 and Phase 3 signatures. The reconciler rewrote every call site to the real exports: Phase 2's `phase-2.md` and Phase 3's `phase-3.md` (Phase 3's kit was compiled, tested and built, so it is the source of truth). The code below was type-checked (`tsc --noEmit` clean) and its tests run (18 green) on top of both phases' code and a real snapshot in a scratch tree.

### Phase 2 (`web/lib/sera/`)

```ts
// types.ts
export type LabSnapshot, LabMethod, LabTrial, LabInsight;
// lab.ts (page only, via '@/lib/sera/lab'; it imports '../../data/lab.json' relatively)
export const lab: LabSnapshot;
// derive.ts (imported RELATIVELY by overview.ts: vitest has no '@/' alias). No gate argument anywhere:
// pass/fail is read from the engine's trial.failed (invariant 5).
export const CONDITION_LABEL: Record<ConditionKey, string>;              // 'Beats SPY', …, 'Luck check'
export function excessCagr(t: LabTrial): number | null;
export function conditionsPassed(t: LabTrial): number;                  // 0..6; an unmeasured luck check is not a pass
export function misses(t: LabTrial): ConditionKey[];                    // overview.ts maps keys to CONDITION_LABEL
export function closest(trials: LabTrial[], k: number): LabTrial[];     // overview.ts takes closest(dev, 1)[0]
export function funnel(trials: LabTrial[]): { key; label; passing; measured; total }[];
export function progress(trials: LabTrial[]): { n; passed; bestPassed; mar; bestMar }[];
export function families(methods: LabMethod[], trials: LabTrial[]): { family; methodIds; trials; bestMar; bestPassed; historical }[];
// glossary.ts (page only)
export type GlossaryKey;                                                 // keys used: tries, testWindow, mar, maxDrawdown, cagr, spyTr, profitFactor, dsr
export const GLOSSARY: Record<GlossaryKey, { term: string; plain: string }>;
export const STATUS_LABEL: Record<LabStatus, { label: string; meaning: string; tone }>;
// markdown.ts (page only)
export function renderMarkdown(src: string): string;
```

### Phase 3 (`web/components/sera/`, `web/lib/sera/gate.ts`)

```ts
PageHeader({ eyebrow: string; title: string; lede?: ReactNode; asOf?: string; aside?: ReactNode })
Section({ eyebrow?; title?; caption?: ReactNode; bg?; aside?; id?; className?; children? })
Stat({ value: string; label: ReactNode; tone?: 'pos'|'neg'; tip?; sub?: ReactNode; size? })
Term({ term: string; definition: string; children?: ReactNode })      // the page's local T({ k }) feeds GLOSSARY[k]
ScatterChart({ points: ScatterPoint[]; ariaLabel; regions?: ScatterRegion[]; refY?: RefLine[]; yDomain?; yTicks?;
               includeZeroX?; xFormat?; yFormat?; xLabel?; yLabel?; height?; legend? })
LineChart({ series: LineSeries[]; ariaLabel; x?: 'number'; xFormat?; yFormat?; yDomain?; yTicks?; includeZero?; xLabel?; height? })
BarChart({ groups: BarGroup[]; ariaLabel; orientation?: 'horizontal'; domain?; format?; width? })
Legend({ items: { label; color; shape?: 'dot'|'zone'|… }[] })
fmtNumber, fmtPct, fmtSignedPct, niceDomain, type Domain, type RefLine, type Tick   // charts/scale.ts
requireSera(next): Promise<User>                                        // lib/sera/gate.ts
```

`overview.ts` imports only **types** from the chart `.tsx` files (`BarGroup`, `LineSeries`, `ScatterPoint`, `ScatterRegion`; erased at runtime) and `niceDomain` plus types from the pure `charts/scale.ts`, all by relative path. Colours are Phase 3's conventions as CSS strings: lab `var(--coral)`, historical `var(--ink-3)`, eligible `var(--pos)`, pass zone `var(--sky)`, extra series `var(--line-b)`.

### Phase 3 layout and the page gate

`web/app/sera/layout.tsx` calls `requireSera()`. This page also calls `await requireSera('/sera')` first (Phase 3 handoff 1: a layout is not re-run on client-side navigation). Both read cookies, so the route is dynamic; the page does not export `dynamic`. The data is bundled from `web/data/lab.json`, so the page does no I/O of its own. The layout's metadata template is `'%s · Sera'`, so the page title is the bare `'Overview'`.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `web/app/sera/page.tsx`: `default async function SeraOverview()` and `export const metadata` (`title: 'Overview'`)
- `web/app/sera/overview.module.css`
- `web/app/sera/overview.ts` with these exports:
  - constants: `HURDLES`, `LAB_COLOR`, `HISTORICAL_COLOR`, `ELIGIBLE_COLOR`, `ABOVE_COLOR`, `HURDLE_COLOR`, `FAMILY_COLOR`, `MAR_COLOR`, `ZONE_COLOR`
  - formatting and paths: `methodHref`, `devTrials`, `pctText`, `signedPp`, `ratioText`, `dayText`, `countTicks`, `missedLabels`, `trialTip`
  - one shaper per section: `state`, `landing`, `hurdles`, `closer`, `luck`, `familyBars`, `latestMethods`
  - `overview`
  - types `Story`, `Closest`, `BestBeat`, `State`, `Landing`, `Hurdles`, `Closer`, `Luck`, `Families`, `MethodCard`, `Overview`
- `web/app/sera/overview.test.ts`

**Signature changes:** none
**Requires (from earlier phases):**
- Phase 2: `lab`, `CONDITION_LABEL`, `excessCagr`, `conditionsPassed`, `misses`, `closest`, `funnel`, `progress`, `families`, `GLOSSARY`, `GlossaryKey`, `STATUS_LABEL`, `renderMarkdown`, types `LabSnapshot`, `LabMethod`, `LabTrial`, `LabInsight` (signatures above). `web/lib/sera/derive.ts` imports nothing through `@/` (Phase 2 deviation 1), so `overview.test.ts` can import it relatively under vitest.
- Phase 3: `PageHeader`, `Section`, `Stat`, `Term`, `ScatterChart`, `LineChart`, `BarChart`, `Legend`, `charts/scale.ts` (`fmtNumber`, `fmtPct`, `fmtSignedPct`, `niceDomain`, types), `requireSera`; the `/sera` layout; the global `TooltipLayer` in `app/layout.tsx` (exists).
- Phase 1: `web/data/lab.json` exists and `insights[].kind` may be `'synthesis'`; `asOf` may be `''` for an empty lab (`PageHeader` then hides the pill).

**Leaves alone (owned by others):** `web/app/sera/layout.tsx`, `sera.module.css` and `not-found.tsx` (Phase 3); `web/components/sera/**` (Phase 3 and, for `diagrams/`, Phase 6); `web/lib/sera/**` (Phases 2 and 3); `web/app/sera/methods/**` (Phase 5); `web/app/sera/{journal,ideas,how}/**` (Phase 6); `web/data/lab.json` (Phase 1).

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/overview.ts` | create (line 1) | pure shaping from `LabSnapshot` into chart and tile props |
| `web/app/sera/overview.test.ts` | create (line 1) | vitest on an inline fixture snapshot |
| `web/app/sera/page.tsx` | create (line 1) | the Overview page (server component) |
| `web/app/sera/overview.module.css` | create (line 1) | desktop 12-column grid, story prose, method cards, status chips |

## Implementation Steps

### Step 1: Page-specific shaping
**File:** `web/app/sera/overview.ts:1` (new)
**Change:** Pure functions that turn the snapshot into the exact Phase 3 chart-kit props (`ScatterPoint[]`, `ScatterRegion[]`, `RefLine[]`, `LineSeries[]`, `BarGroup[]`, `Tick[]`, `Domain`) and tile values. Imports are relative, so vitest resolves them; imports from the chart `.tsx` files are type-only. Gate thresholds always come from `snap.gate`, per invariant 5; pass/fail comes from Phase 2 (the engine's `failed`). `HURDLES = 6` is the number of conditions in the contract's failure-label list, not a threshold.
**Code:**
```ts
import type { BarGroup } from '../../components/sera/charts/BarChart';
import type { LineSeries } from '../../components/sera/charts/LineChart';
import type { ScatterPoint, ScatterRegion } from '../../components/sera/charts/ScatterChart';
import { type Domain, type RefLine, type Tick, niceDomain } from '../../components/sera/charts/scale';
import {
  CONDITION_LABEL,
  closest,
  conditionsPassed,
  excessCagr,
  families,
  funnel,
  misses,
  progress,
} from '../../lib/sera/derive';
import type { LabInsight, LabMethod, LabSnapshot, LabTrial } from '../../lib/sera/types';

/** The six conditions every dev try is judged on (the contract's failure labels). A count, not a threshold. */
export const HURDLES = 6;

const MINUS = '−';

// ---- Colours (Phase 3 conventions: Seer v2 tokens as CSS strings) ---------------------------------

export const LAB_COLOR = 'var(--coral)';
export const HISTORICAL_COLOR = 'var(--ink-3)';
export const ELIGIBLE_COLOR = 'var(--pos)';
export const ABOVE_COLOR = 'var(--ink)';
export const HURDLE_COLOR = 'var(--ink)';
export const FAMILY_COLOR = 'var(--line-b)';
export const MAR_COLOR = 'var(--line-b)';
export const ZONE_COLOR = 'var(--sky)';

// ---- Formatting ---------------------------------------------------------------------------------

export const methodHref = (id: string): string => `/sera/methods/${encodeURIComponent(id)}`;

export const devTrials = (snap: LabSnapshot): LabTrial[] => snap.trials.filter(t => t.window === 'dev');

/** 0.1234 -> '12.3%', -0.05 -> '−5.0%', null -> '—'. */
export const pctText = (v: number | null, digits = 1): string =>
  v === null ? '—' : (v < 0 ? MINUS : '') + (Math.abs(v) * 100).toFixed(digits) + '%';

/** A return difference in percentage points: 0.012 -> '+1.2 pp', -0.03 -> '−3.0 pp'. */
export const signedPp = (v: number, digits = 1): string =>
  (v < 0 ? MINUS : '+') + (Math.abs(v) * 100).toFixed(digits) + ' pp';

/** A plain ratio (MAR, DSR, PF): 0.5557 -> '0.56', null -> '—'. */
export const ratioText = (v: number | null, digits = 2): string =>
  v === null ? '—' : (v < 0 ? MINUS : '') + Math.abs(v).toFixed(digits);

const DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' });

/** '2026-10-04T14:12:19+00:00' -> 'Oct 4, 2026'. */
export const dayText = (iso: string): string => DAY.format(new Date(iso));

/** Integer ticks 0..max, for the 'hurdles cleared' axis. */
export const countTicks = (max: number): Tick[] =>
  Array.from({ length: max + 1 }, (_, i) => ({ value: i, label: String(i) }));

// ---- Shared -------------------------------------------------------------------------------------

const historicalIds = (snap: LabSnapshot): Set<string> =>
  new Set(snap.methods.filter(m => m.historical).map(m => m.id));

/** Plain names of the hurdles a try missed, in display order. */
export const missedLabels = (t: LabTrial): string[] => misses(t).map(k => CONDITION_LABEL[k]);

/** '<candidate>: CAGR x vs SPY y, max DD z, misses: …' */
export function trialTip(t: LabTrial): string {
  const m = missedLabels(t);
  return (
    `${t.candidateId}: CAGR ${pctText(t.cagr)} vs SPY ${pctText(t.spyTrCagr)}, ` +
    `max DD ${pctText(t.maxDrawdown)}, misses: ${m.length ? m.join(', ') : 'none'}`
  );
}

const newest = (xs: LabInsight[]): LabInsight | undefined =>
  [...xs].sort((a, b) => b.added.localeCompare(a.added) || b.id - a.id)[0];

const listText = (xs: string[]): string =>
  xs.length <= 1 ? (xs[0] ?? '') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`;

// ---- (1) State of the search --------------------------------------------------------------------

export type Story = {
  title: string;
  body: string; // markdown
  added: string | null;
  source: 'synthesis' | 'insight' | 'computed';
};
export type Closest = { trial: LabTrial; passed: number; misses: string[] };
export type BestBeat = { trial: LabTrial; excess: number };
export type State = {
  story: Story;
  tried: { total: number; lab: number; historical: number };
  tries: number;
  looks: number;
  eligible: number;
  closest: Closest | null;
  bestBeat: BestBeat | null;
};

export function state(snap: LabSnapshot): State {
  const gate = snap.gate;
  const dev = devTrials(snap);
  const hist = historicalIds(snap);

  const triedIds = new Set(dev.map(t => t.methodId));
  const historical = [...triedIds].filter(id => hist.has(id)).length;
  const tried = { total: triedIds.size, lab: triedIds.size - historical, historical };

  const near = closest(dev, 1)[0];
  const closestRow: Closest | null = near
    ? { trial: near, passed: conditionsPassed(near), misses: missedLabels(near) }
    : null;

  let bestBeat: BestBeat | null = null;
  for (const t of dev) {
    const ex = excessCagr(t);
    if (ex === null || ex <= 0 || t.maxDrawdown === null || t.maxDrawdown > gate.maxDrawdown) continue;
    if (!bestBeat || ex > bestBeat.excess) bestBeat = { trial: t, excess: ex };
  }

  const eligible = dev.filter(t => t.eligible).length;

  const synth = newest(snap.insights.filter(i => i.kind === 'synthesis'));
  const note = newest(snap.insights);
  const story: Story = synth
    ? { title: synth.title, body: synth.body, added: synth.added, source: 'synthesis' }
    : note
      ? { title: note.title, body: note.body, added: note.added, source: 'insight' }
      : computedStory(dev.length, tried.total, eligible, closestRow);

  return { story, tried, tries: dev.length, looks: snap.summary.testLooks, eligible, closest: closestRow, bestBeat };
}

function computedStory(tries: number, methods: number, eligible: number, near: Closest | null): Story {
  const parts = [`${tries} ${tries === 1 ? 'try' : 'tries'} across ${methods} ${methods === 1 ? 'method' : 'methods'} so far.`];
  parts.push(
    eligible > 0
      ? `${eligible} cleared every hurdle and ${eligible === 1 ? 'waits' : 'wait'} for the one look at fresh data.`
      : 'None has cleared every hurdle yet.',
  );
  if (near && near.misses.length) parts.push(`Closest: ${near.trial.candidateId}, which missed ${listText(near.misses)}.`);
  return { title: 'Where the search stands', body: parts.join(' '), added: null, source: 'computed' };
}

// ---- (2) Where every try landed -----------------------------------------------------------------

export type Landing = {
  points: ScatterPoint[];
  regions: ScatterRegion[];
  refY: RefLine[];
  /** Always reaches a little above SPY, so the pass zone shows even when nothing beats SPY yet. */
  yDomain: Domain;
  total: number;
  inZone: number;
};

export function landing(snap: LabSnapshot): Landing {
  const gate = snap.gate;
  const hist = historicalIds(snap);
  const rows = devTrials(snap).flatMap(t => {
    const ex = excessCagr(t);
    return t.maxDrawdown === null || ex === null ? [] : [{ t, dd: t.maxDrawdown, ex }];
  });

  const color = (t: LabTrial) => (t.eligible ? ELIGIBLE_COLOR : hist.has(t.methodId) ? HISTORICAL_COLOR : LAB_COLOR);
  const rank = (t: LabTrial) => (t.eligible ? 2 : hist.has(t.methodId) ? 0 : 1);
  const points: ScatterPoint[] = [...rows]
    // Draw order: historical under lab, eligible on top.
    .sort((a, b) => rank(a.t) - rank(b.t) || a.t.n - b.t.n)
    .map(({ t, dd, ex }) => ({
      id: `t${t.n}`,
      x: dd,
      y: ex,
      color: color(t),
      r: t.eligible ? 8 : 6,
      tip: trialTip(t),
      href: methodHref(t.methodId),
    }));

  const ys = rows.map(r => r.ex);
  return {
    points,
    regions: [
      {
        x1: gate.maxDrawdown,
        y0: 0,
        label: 'Pass zone',
        color: ZONE_COLOR,
        tip: `A worst fall of at most ${pctText(gate.maxDrawdown, 0)}, and growth above SPY`,
      },
    ],
    refY: [{ value: 0, label: 'SPY' }],
    yDomain: niceDomain(Math.min(0, ...ys), Math.max(0.01, ...ys)),
    total: rows.length,
    inZone: rows.filter(r => r.dd <= gate.maxDrawdown && r.ex > 0).length,
  };
}

// ---- (3) Which hurdles are hardest --------------------------------------------------------------

export type Hurdles = { groups: BarGroup[]; domain: Domain; total: number; hardest: string | null };

export function hurdles(snap: LabSnapshot): Hurdles {
  const dev = devTrials(snap);
  const rows = funnel(dev);
  const groups: BarGroup[] = rows.map(r => ({
    id: r.key,
    label: r.label,
    items: [
      {
        key: r.key,
        value: r.passing,
        color: HURDLE_COLOR,
        valueText: `${r.passing} of ${r.measured}`,
        tip:
          r.measured < r.total
            ? `${r.passing} of the ${r.measured} tries it was checked on pass “${r.label}” (${r.total - r.measured} older tries predate it)`
            : `${r.passing} of ${r.total} tries pass “${r.label}”`,
      },
    ],
  }));
  const measured = rows.filter(r => r.measured > 0);
  const hardestRow = measured.length
    ? measured.reduce((a, b) => (b.passing / b.measured < a.passing / a.measured ? b : a))
    : null;
  return { groups, domain: [0, Math.max(dev.length, 1)], total: dev.length, hardest: hardestRow ? hardestRow.label : null };
}

// ---- (4) Are we getting closer? ----------------------------------------------------------------

export type Closer = {
  passed: LineSeries[];
  passedTicks: Tick[];
  mar: LineSeries[] | null;
  latestPassed: number;
  latestMar: number | null;
};

export function closer(snap: LabSnapshot): Closer {
  const rows = progress(devTrials(snap));

  const passed: LineSeries = {
    id: 'passed',
    label: 'Most hurdles cleared so far',
    color: LAB_COLOR,
    step: true,
    points: rows.map(r => [r.n, r.bestPassed, `After try #${r.n}: best clears ${r.bestPassed} of ${HURDLES}`]),
  };

  const marRows = rows.filter((r): r is typeof r & { bestMar: number } => r.bestMar !== null);
  const mar: LineSeries[] | null = marRows.length
    ? [
        {
          id: 'mar',
          label: 'Best MAR so far',
          color: MAR_COLOR,
          step: true,
          points: marRows.map(r => [r.n, r.bestMar, `After try #${r.n}: best MAR ${ratioText(r.bestMar)}`]),
        },
      ]
    : null;

  const last = rows[rows.length - 1];
  return {
    passed: [passed],
    passedTicks: countTicks(HURDLES),
    mar,
    latestPassed: last ? last.bestPassed : 0,
    latestMar: last ? last.bestMar : null,
  };
}

// ---- (5) The luck bar ---------------------------------------------------------------------------

export type Luck = { points: ScatterPoint[]; refY: RefLine[]; yTicks: Tick[]; above: number; total: number };

export function luck(snap: LabSnapshot): Luck | null {
  const gate = snap.gate;
  const rows = devTrials(snap).filter((t): t is LabTrial & { dsr: number } => t.dsr !== null);
  if (rows.length === 0) return null;
  const points: ScatterPoint[] = rows.map(t => ({
    id: `t${t.n}`,
    x: t.nTrialsAtRun,
    y: t.dsr,
    color: t.eligible ? ELIGIBLE_COLOR : t.dsr >= gate.dsrMin ? ABOVE_COLOR : LAB_COLOR,
    r: t.eligible ? 8 : 6,
    tip: `${t.candidateId}: DSR ${ratioText(t.dsr)} at N = ${t.nTrialsAtRun}`,
    href: methodHref(t.methodId),
  }));
  return {
    points,
    refY: [{ value: gate.dsrMin, label: `Luck bar ${ratioText(gate.dsrMin)}`, color: 'var(--neg)' }],
    yTicks: [0, 0.25, 0.5, 0.75, 1].map(v => ({ value: v, label: v.toFixed(2) })),
    above: rows.filter(t => t.dsr >= gate.dsrMin).length,
    total: rows.length,
  };
}

// ---- (6) Families explored ----------------------------------------------------------------------

export type Families = { groups: BarGroup[]; domain: Domain; count: number };

export function familyBars(snap: LabSnapshot): Families {
  const rows = families(snap.methods, devTrials(snap))
    .filter(f => f.trials > 0)
    .sort((a, b) => b.trials - a.trials || a.family.localeCompare(b.family));
  const groups: BarGroup[] = rows.map(f => {
    const n = f.methodIds.length;
    return {
      id: f.family,
      label: f.family,
      items: [
        {
          key: f.family,
          value: f.trials,
          color: FAMILY_COLOR,
          valueText: String(f.trials),
          tip:
            `${f.family}: ${f.trials} ${f.trials === 1 ? 'try' : 'tries'} across ${n} ` +
            `${n === 1 ? 'method' : 'methods'}, best MAR ${ratioText(f.bestMar)}`,
        },
      ],
    };
  });
  return { groups, domain: [0, Math.max(1, ...rows.map(f => f.trials))], count: rows.length };
}

// ---- (7) Latest methods -------------------------------------------------------------------------

export type MethodCard = {
  id: string;
  name: string;
  status: LabMethod['status'];
  family: string;
  blurb: string;
  blurbIsVerdict: boolean;
  updated: string;
  href: string;
  tries: number;
  bestPassed: number | null;
};

/** Up to the first sentence of `text`, capped at `max` characters. */
const firstSentence = (text: string, max = 220): string => {
  const flat = text.replace(/\s+/g, ' ').trim();
  const end = flat.search(/[.!?](\s|$)/);
  const s = end === -1 ? flat : flat.slice(0, end + 1);
  return s.length > max ? s.slice(0, max - 1).trimEnd() + '…' : s;
};

export function latestMethods(snap: LabSnapshot, k = 6): MethodCard[] {
  const dev = devTrials(snap);
  return snap.methods
    .filter(m => !m.historical)
    .sort((a, b) => b.updated.localeCompare(a.updated) || b.id.localeCompare(a.id))
    .slice(0, k)
    .map(m => {
      const own = dev.filter(t => t.methodId === m.id);
      const verdict = m.verdict.trim();
      return {
        id: m.id,
        name: m.name,
        status: m.status,
        family: m.family,
        blurb: verdict || firstSentence(m.hypothesis),
        blurbIsVerdict: verdict !== '',
        updated: m.updated,
        href: methodHref(m.id),
        tries: own.length,
        bestPassed: own.length ? Math.max(...own.map(t => conditionsPassed(t))) : null,
      };
    });
}

// ---- All of it ----------------------------------------------------------------------------------

export type Overview = {
  state: State;
  landing: Landing;
  hurdles: Hurdles;
  closer: Closer;
  luck: Luck | null;
  families: Families;
  latest: MethodCard[];
};

export function overview(snap: LabSnapshot): Overview {
  return {
    state: state(snap),
    landing: landing(snap),
    hurdles: hurdles(snap),
    closer: closer(snap),
    luck: luck(snap),
    families: familyBars(snap),
    latest: latestMethods(snap),
  };
}
```
**Impact:** New file only. Uses Phase 2 derivations unchanged. The luck-check row of the funnel counts only the tries it was measured on (`measured`), so historical tries are not shown as misses.

### Step 2: Unit tests
**File:** `web/app/sera/overview.test.ts:1` (new)
**Change:** An inline fixture snapshot. Its values follow Phase 2's semantics: a try with `failed: []` and a DSR above the bar passes all six conditions, and a historical try (`dsr: null`) is "not measured" on the luck check. Assertions target this file's own shaping: filtering, colours, fallbacks, domains, ticks and ordering.
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import type { LabInsight, LabMethod, LabSnapshot, LabTrial } from '../../lib/sera/types';
import {
  closer,
  countTicks,
  ELIGIBLE_COLOR,
  familyBars,
  HISTORICAL_COLOR,
  hurdles,
  LAB_COLOR,
  landing,
  latestMethods,
  luck,
  pctText,
  signedPp,
  state,
  trialTip,
} from './overview';

const method = (id: string, over: Partial<LabMethod> = {}): LabMethod => ({
  id,
  name: `Method ${id}`,
  family: id.startsWith('H-') ? 'old-family' : 'new-family',
  parentId: null,
  sourceKind: id.startsWith('H-') ? 'seed' : 'knowledge',
  sourceRef: '',
  hypothesis: `Idea for ${id}. More detail here.`,
  expectedFailure: null,
  status: 'rejected',
  analysis: '',
  verdict: '',
  blockedOn: '',
  created: '2026-10-01T00:00:00+00:00',
  updated: '2026-10-01T00:00:00+00:00',
  historical: id.startsWith('H-'),
  ...over,
});

const trial = (n: number, methodId: string, over: Partial<LabTrial> = {}): LabTrial => ({
  n,
  methodId,
  candidateId: `${methodId}-C${n}`,
  rulesId: 'r',
  allocatorId: 'a',
  configText: '{}',
  window: 'dev',
  start: '1993-01-29',
  end: '2015-10-16',
  gitSha: 'abc',
  runAt: '2026-10-04T00:00:00+00:00',
  totalReturn: 1,
  cagr: 0.06,
  maxDrawdown: 0.3,
  profitFactor: 1.5,
  pfInfinite: false,
  trades: 200,
  sharpe: 0.5,
  exposure: 0.9,
  turnover: 1,
  worstYear: 2008,
  worstYearReturn: -0.3,
  spyTrReturn: 2,
  spyTrCagr: 0.08,
  mar: 0.2,
  failed: ['beats SPY TR', 'max DD <= 15%'],
  eligible: false,
  dsr: null,
  nTrialsAtRun: n,
  curve: [],
  ...over,
});

const insight = (id: number, kind: LabInsight['kind'], added: string): LabInsight => ({
  id,
  kind,
  title: `${kind} ${id}`,
  body: `Body of ${id}`,
  methodId: null,
  added,
});

const snap = (over: Partial<LabSnapshot> = {}): LabSnapshot => ({
  version: 1,
  asOf: '2026-10-04T14:12:24+00:00',
  gate: {
    maxDrawdown: 0.15,
    minProfitFactor: 1.3,
    minTrades: 100,
    dsrMin: 0.95,
    devStart: '1993-01-29',
    devEnd: '2015-10-16',
    testStart: '2015-10-19',
  },
  data: {
    storeStart: '1993-01-29',
    membershipStart: '1996-01-02',
    fxStart: '1999-01-04',
    fingerprints: [],
    barRows: 0,
    symbolsRequested: 0,
    symbolsServed: 0,
    dividendRows: 0,
  },
  summary: { devTrials: 4, testLooks: 0, methods: 4, labMethods: 2, historicalMethods: 2, insights: 0, byStatus: {} },
  benchmark: { spyTr: [], spyPrice: [] },
  methods: [
    method('H-A'),
    method('H-B'),
    method('M0001', { updated: '2026-10-04T14:00:35+00:00', verdict: 'Fixed drawdown, lost return.' }),
    method('M0002', { status: 'idea', updated: '2026-10-04T14:00:36+00:00' }),
  ],
  trials: [
    trial(1, 'H-A', { maxDrawdown: 0.55, cagr: 0.089, spyTrCagr: 0.089, failed: ['beats SPY TR', 'max DD <= 15%', 'PF >= 1.3', '>= 100 trades'] }),
    trial(2, 'H-B', { maxDrawdown: 0.19, cagr: 0.098, spyTrCagr: 0.089, mar: 0.52, failed: ['max DD <= 15%', '>= 100 trades'] }),
    trial(3, 'M0001', { maxDrawdown: 0.11, cagr: 0.061, spyTrCagr: 0.079, mar: 0.56, dsr: 0.9, nTrialsAtRun: 4, failed: ['beats SPY TR', 'DSR >= 0.95'] }),
    trial(4, 'M0001', { maxDrawdown: 0.12, cagr: 0.09, spyTrCagr: 0.079, mar: 0.75, dsr: 0.97, nTrialsAtRun: 4, failed: [], eligible: true }),
    trial(5, 'M0001', { window: 'test', maxDrawdown: 0.01, cagr: 0.5 }),
  ],
  insights: [],
  ideasSeen: [],
  ...over,
});


describe('formatting', () => {
  it('formats percentages and percentage points with a real minus', () => {
    expect(pctText(0.1234)).toBe('12.3%');
    expect(pctText(-0.05)).toBe('−5.0%');
    expect(pctText(null)).toBe('—');
    expect(signedPp(0.012)).toBe('+1.2 pp');
    expect(signedPp(-0.03, 0)).toBe('−3 pp');
  });
  it('lists integer ticks for the hurdle axis', () => {
    expect(countTicks(2)).toEqual([{ value: 0, label: '0' }, { value: 1, label: '1' }, { value: 2, label: '2' }]);
  });
});

describe('landing', () => {
  it('plots only dev tries and colours them by origin', () => {
    const l = landing(snap());
    expect(l.points).toHaveLength(4);
    const byTip = (c: string) => l.points.find(p => p.tip!.startsWith(c))!;
    expect(byTip('H-A-C1').color).toBe(HISTORICAL_COLOR);
    expect(byTip('M0001-C3').color).toBe(LAB_COLOR);
    expect(byTip('M0001-C4').color).toBe(ELIGIBLE_COLOR);
    expect(byTip('M0001-C4').r).toBe(8);
    expect(byTip('M0001-C3').href).toBe('/sera/methods/M0001');
    expect(new Set(l.points.map(p => p.id)).size).toBe(4);
  });
  it('draws eligible tries last', () => {
    const l = landing(snap());
    expect(l.points[l.points.length - 1].color).toBe(ELIGIBLE_COLOR);
    expect(l.points[0].color).toBe(HISTORICAL_COLOR);
  });
  it('shades the pass zone from the gate and keeps it visible', () => {
    const l = landing(snap());
    expect(l.regions[0]).toMatchObject({ x1: 0.15, y0: 0, label: 'Pass zone' });
    expect(l.refY[0].value).toBe(0);
    expect(l.yDomain[1]).toBeGreaterThan(0);
    expect(l.inZone).toBe(1);
    const base = snap();
    const none = landing({ ...base, trials: base.trials.filter(t => t.n === 1) });
    expect(none.yDomain[1]).toBeGreaterThan(0);
  });
  it('writes the tip the page promises, with plain hurdle names', () => {
    expect(trialTip(snap().trials[2])).toBe('M0001-C3: CAGR 6.1% vs SPY 7.9%, max DD 11.0%, misses: Beats SPY, Luck check');
  });
});

describe('state', () => {
  it('counts tried methods, tries and looks', () => {
    const s = state(snap());
    expect(s.tried).toEqual({ total: 3, lab: 1, historical: 2 });
    expect(s.tries).toBe(4);
    expect(s.looks).toBe(0);
    expect(s.eligible).toBe(1);
  });
  it('finds the best beat within the drawdown gate', () => {
    const s = state(snap());
    expect(s.bestBeat?.trial.n).toBe(4);
    expect(s.bestBeat?.excess).toBeCloseTo(0.011, 6);
  });
  it('reports no best beat when nothing beats SPY inside the gate', () => {
    const base = snap();
    const s = state({ ...base, trials: base.trials.filter(t => t.n !== 4) });
    expect(s.bestBeat).toBeNull();
  });
  it('prefers the newest synthesis over newer insights of other kinds', () => {
    const s = state(snap({
      insights: [
        insight(1, 'synthesis', '2026-10-04T10:00:00+00:00'),
        insight(2, 'synthesis', '2026-10-04T11:00:00+00:00'),
        insight(3, 'observation', '2026-10-04T12:00:00+00:00'),
      ],
    }));
    expect(s.story.source).toBe('synthesis');
    expect(s.story.title).toBe('synthesis 2');
  });
  it('falls back to the newest insight, then to a computed sentence', () => {
    const one = state(snap({ insights: [insight(1, 'risk', '2026-10-04T10:00:00+00:00'), insight(2, 'observation', '2026-10-04T12:00:00+00:00')] }));
    expect(one.story.source).toBe('insight');
    expect(one.story.title).toBe('observation 2');
    const none = state(snap());
    expect(none.story.source).toBe('computed');
    expect(none.story.body).toContain('4 tries across 3 methods');
  });
});


describe('hurdles', () => {
  it('has one bar per condition, scaled to the dev try count', () => {
    const h = hurdles(snap());
    expect(h.groups.map(g => g.id)).toEqual(['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr']);
    expect(h.domain).toEqual([0, 4]);
    expect(h.total).toBe(4);
    expect(h.groups[4].items[0]).toMatchObject({ value: 4, valueText: '4 of 4' });
    // The luck check was measured on the two lab tries only.
    expect(h.groups[5].items[0]).toMatchObject({ value: 1, valueText: '1 of 2' });
    expect(h.groups[5].items[0].tip).toContain('older tries predate it');
    expect(h.hardest).toBe('Beats SPY');
  });
});

describe('closer', () => {
  it('runs over dev try numbers on a 0–6 scale', () => {
    const c = closer(snap());
    expect(c.passedTicks).toHaveLength(7);
    expect(c.passed[0].points.map(p => p[0])).toEqual([1, 2, 3, 4]);
    expect(c.passed[0].step).toBe(true);
    expect(c.latestPassed).toBe(6);
    expect(c.mar).not.toBeNull();
  });
});

describe('luck', () => {
  it('plots only tries with a DSR against the gate line', () => {
    const l = luck(snap())!;
    expect(l.points).toHaveLength(2);
    expect(l.refY[0].value).toBe(0.95);
    expect(l.above).toBe(1);
    expect(l.points.map(p => p.x)).toEqual([4, 4]);
    expect(l.yTicks.map(t => t.label)).toEqual(['0.00', '0.25', '0.50', '0.75', '1.00']);
  });
  it('is null when no try has a DSR', () => {
    const base = snap();
    expect(luck({ ...base, trials: base.trials.map(t => ({ ...t, dsr: null })) })).toBeNull();
  });
});

describe('families', () => {
  it('bars families by dev tries, largest first', () => {
    const f = familyBars(snap());
    expect(f.groups.map(g => g.id)).toEqual(['new-family', 'old-family']);
    expect(f.groups[0].items[0].value).toBe(2);
    expect(f.domain).toEqual([0, 2]);
    expect(f.groups[0].items[0].tip).toContain('best MAR');
  });
});

describe('latest methods', () => {
  it('lists lab methods newest first with a verdict or the idea', () => {
    const l = latestMethods(snap());
    expect(l.map(m => m.id)).toEqual(['M0002', 'M0001']);
    expect(l[0].blurbIsVerdict).toBe(false);
    expect(l[0].blurb).toBe('Idea for M0002.');
    expect(l[0].tries).toBe(0);
    expect(l[0].bestPassed).toBeNull();
    expect(l[1].blurb).toBe('Fixed drawdown, lost return.');
    expect(l[1].tries).toBe(2);
    expect(l[1].href).toBe('/sera/methods/M0001');
  });
  it('caps at k', () => {
    const many = Array.from({ length: 9 }, (_, i) => method(`M00${10 + i}`, { updated: `2026-10-0${1 + (i % 4)}T00:00:00+00:00` }));
    expect(latestMethods(snap({ methods: many }))).toHaveLength(6);
  });
});
```
**Impact:** New test file (18 tests).

### Step 3: The page
**File:** `web/app/sera/page.tsx:1` (new)
**Change:** A server component. It calls `await requireSera('/sera')`, reads the bundled `lab`, calls `overview(lab)`, and lays out seven `Section` sheets on the desktop grid. Each section's caption is one plain sentence. Jargon is wrapped in the local `T` (Phase 3's `Term` fed from `GLOSSARY`) on its first appearance on the page:
- `tries`, `testWindow`, `mar` in section 1
- `maxDrawdown`, `cagr`, `spyTr` in section 2
- `profitFactor`, `dsr` in section 3

The only controls are the icon-only `ArrowUpRight` links on the method cards. Each has `aria-label` and `data-tip`. Gate numbers come from `lab.gate`.
**Code:**
```tsx
import { ArrowUpRight } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { BarChart } from '@/components/sera/charts/BarChart';
import { Legend } from '@/components/sera/charts/Legend';
import { LineChart } from '@/components/sera/charts/LineChart';
import { fmtNumber, fmtPct, fmtSignedPct } from '@/components/sera/charts/scale';
import { ScatterChart } from '@/components/sera/charts/ScatterChart';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Stat } from '@/components/sera/Stat';
import { Term } from '@/components/sera/Term';
import { requireSera } from '@/lib/sera/gate';
import { GLOSSARY, type GlossaryKey, STATUS_LABEL } from '@/lib/sera/glossary';
import { lab } from '@/lib/sera/lab';
import { renderMarkdown } from '@/lib/sera/markdown';
import {
  ABOVE_COLOR,
  dayText,
  ELIGIBLE_COLOR,
  HISTORICAL_COLOR,
  HURDLES,
  LAB_COLOR,
  overview,
  pctText,
  ratioText,
  signedPp,
  ZONE_COLOR,
} from './overview';
import s from './overview.module.css';

export const metadata: Metadata = { title: 'Overview' };

const year = (ymd: string) => ymd.slice(0, 4);
const tryNumber = (v: number) => `#${v}`;

/** A glossary term: the definition comes from lib/sera/glossary (Term itself takes plain strings). */
function T({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  return (
    <Term term={GLOSSARY[k].term} definition={GLOSSARY[k].plain}>
      {children}
    </Term>
  );
}

export default async function SeraOverview() {
  await requireSera('/sera');
  const v = overview(lab);
  const g = lab.gate;
  const dd = pctText(g.maxDrawdown, 0);
  const dev = `${year(g.devStart)}–${year(g.devEnd)}`;
  const test = `${year(g.testStart)}–today`;
  const { state: st, landing: ld, hurdles: hu, closer: cl, luck: lk, families: fa, latest } = v;

  const storyFrom =
    st.story.source === 'synthesis'
      ? 'Latest batch summary'
      : st.story.source === 'insight'
        ? 'Latest note in the journal'
        : 'Summary from the numbers';

  return (
    <>
      <PageHeader
        eyebrow="Sera · the method lab"
        title="Overview"
        lede={`Where the search for a strategy that beats SPY with a shallow fall stands, and how every try on ${dev} has gone.`}
        asOf={lab.asOf}
      />

      <div className={s.grid}>
        {/* (1) State of the search */}
        <Section
          className={s.state}
          eyebrow="State of the search"
          title={st.story.title}
          caption={`The latest read on the search, then the numbers behind it. A try is one version of a method run once on ${dev}.`}
        >
          <div className={s.stateBody}>
            <article className={s.story}>
              <p className={s.storyMeta}>
                {storyFrom}
                {st.story.added ? ` · ${dayText(st.story.added)}` : ''}
              </p>
              <div className={s.prose} dangerouslySetInnerHTML={{ __html: renderMarkdown(st.story.body) }} />
            </article>

            <div className={s.stats}>
              <Stat
                label="Methods tried"
                value={String(st.tried.total)}
                sub={`${st.tried.lab} from the lab · ${st.tried.historical} from before it`}
              />
              <Stat
                label={
                  <>
                    Tries (<T k="tries">N</T>)
                  </>
                }
                value={String(st.tries)}
                sub="Every try raises the bar for luck"
              />
              <Stat
                label={
                  <>
                    <T k="testWindow">Test-window</T> looks used
                  </>
                }
                value={String(st.looks)}
                sub={st.looks === 0 ? `The ${test} data is still untouched` : `Each look at ${test} is spent for good`}
              />
              <Stat
                label="Closest result"
                value={st.closest ? `${st.closest.passed} of ${HURDLES}` : '—'}
                sub={
                  st.closest ? (
                    <>
                      {st.closest.trial.candidateId}, <T k="mar">MAR</T> {ratioText(st.closest.trial.mar)}
                      {st.closest.misses.length ? ` · missed ${st.closest.misses.join(', ')}` : ' · missed nothing'}
                    </>
                  ) : (
                    'No tries yet'
                  )
                }
              />
              <Stat
                label={`Best beat with a fall ≤ ${dd}`}
                value={st.bestBeat ? signedPp(st.bestBeat.excess) : 'none yet'}
                tone={st.bestBeat ? 'pos' : undefined}
                sub={
                  st.bestBeat
                    ? `${st.bestBeat.trial.candidateId} · per year above SPY, max fall ${pctText(st.bestBeat.trial.maxDrawdown)}`
                    : `Nothing has beaten SPY while keeping its worst fall under ${dd}`
                }
              />
            </div>
          </div>
        </Section>

        {/* (2) Where every try landed */}
        <Section
          className={s.landing}
          eyebrow="Where every try landed"
          title={`${ld.inZone} of ${ld.total} in the pass zone`}
          caption={
            <>
              Each dot is one try: further right means a deeper worst fall (<T k="maxDrawdown">max drawdown</T>),
              higher means it grew faster per year (<T k="cagr">CAGR</T>) than{' '}
              <T k="spyTr">SPY with dividends</T>. Only the shaded corner, a fall of at most {dd} and above SPY, can
              pass.
            </>
          }
        >
          <ScatterChart
            ariaLabel={`Scatter of ${ld.total} tries: max drawdown against growth above SPY, with the pass zone shaded`}
            points={ld.points}
            regions={ld.regions}
            refY={ld.refY}
            yDomain={ld.yDomain}
            includeZeroX
            xFormat={fmtPct(0)}
            yFormat={fmtSignedPct(0)}
            xLabel="Worst fall from a peak"
            yLabel="Growth a year minus SPY"
            height={400}
            legend={
              <Legend
                items={[
                  { label: 'Lab tries', color: LAB_COLOR, shape: 'dot' },
                  { label: 'Tries from before the lab', color: HISTORICAL_COLOR, shape: 'dot' },
                  { label: 'Cleared every hurdle', color: ELIGIBLE_COLOR, shape: 'dot' },
                  { label: 'Pass zone', color: ZONE_COLOR, shape: 'zone' },
                ]}
              />
            }
          />
        </Section>

        {/* (3) Which hurdles are hardest */}
        <Section
          className={s.hurdles}
          eyebrow="Which hurdles are hardest"
          title={hu.hardest ? `Hardest: ${hu.hardest}` : 'No tries yet'}
          caption={
            <>
              Each bar counts how many of the {hu.total} tries cleared that one hurdle, among them the{' '}
              <T k="profitFactor">profit factor</T> and the <T k="dsr">luck check</T>. The shortest bar is the wall.
            </>
          }
        >
          <BarChart
            ariaLabel={`Tries passing each of the ${HURDLES} hurdles`}
            groups={hu.groups}
            orientation="horizontal"
            domain={hu.domain}
            format={fmtNumber(0)}
            width={560}
          />
        </Section>

        {/* (4) Are we getting closer? */}
        <Section
          className={s.closer}
          eyebrow="Are we getting closer?"
          title={`Best so far: ${cl.latestPassed} of ${HURDLES} hurdles`}
          caption="Each line only rises: it shows the best result found up to that try, so a flat stretch means no new ground."
        >
          <div className={s.twin}>
            <div className={s.mini}>
              <p className={s.miniLabel}>Most hurdles cleared so far</p>
              <LineChart
                ariaLabel="Most hurdles cleared by any try so far, by try number"
                series={cl.passed}
                x="number"
                xFormat={tryNumber}
                yDomain={[0, HURDLES]}
                yTicks={cl.passedTicks}
                xLabel="Try number"
                height={220}
              />
            </div>
            <div className={s.mini}>
              <p className={s.miniLabel}>Best MAR so far (growth per unit of worst fall)</p>
              {cl.mar ? (
                <LineChart
                  ariaLabel="Best MAR of any try so far, by try number"
                  series={cl.mar}
                  x="number"
                  xFormat={tryNumber}
                  yFormat={fmtNumber(1)}
                  includeZero
                  xLabel="Try number"
                  height={220}
                />
              ) : (
                <p className={s.empty}>No try has a MAR yet.</p>
              )}
            </div>
          </div>
        </Section>

        {/* (5) The luck bar */}
        <Section
          className={s.luck}
          eyebrow="The luck bar"
          title={lk ? `${lk.above} of ${lk.total} cleared the luck bar` : 'No luck scores yet'}
          caption={`The more tries we run, the likelier one looks good by chance, so each try's luck score is judged against everything tried before it and must reach ${ratioText(g.dsrMin)}.`}
        >
          {lk ? (
            <ScatterChart
              ariaLabel={`Luck score of ${lk.total} tries against the number of tries counted, with the ${ratioText(g.dsrMin)} line`}
              points={lk.points}
              refY={lk.refY}
              yDomain={[0, 1]}
              yTicks={lk.yTicks}
              includeZeroX
              xFormat={fmtNumber(0)}
              xLabel="Tries counted when it ran (N)"
              yLabel="Luck score (DSR)"
              height={300}
              legend={
                <Legend
                  items={[
                    { label: 'Below the bar', color: LAB_COLOR, shape: 'dot' },
                    { label: 'Above the bar', color: ABOVE_COLOR, shape: 'dot' },
                    { label: 'Cleared every hurdle', color: ELIGIBLE_COLOR, shape: 'dot' },
                  ]}
                />
              }
            />
          ) : (
            <p className={s.empty}>Luck scores start with the lab&apos;s own tries; the older ones were run before it existed.</p>
          )}
        </Section>

        {/* (6) Families explored */}
        <Section
          className={s.families}
          eyebrow="Families explored"
          title={`${fa.count} ${fa.count === 1 ? 'family' : 'families'}`}
          caption="Tries per family of ideas; hover a bar for its best MAR. A long bar with a weak best means the family has been squeezed hard."
        >
          <BarChart
            ariaLabel="Tries per method family"
            groups={fa.groups}
            orientation="horizontal"
            domain={fa.domain}
            format={fmtNumber(0)}
            width={640}
          />
        </Section>

        {/* (7) Latest methods */}
        <Section
          className={s.latest}
          eyebrow="Latest methods"
          title="What the lab touched last"
          caption="The six lab methods changed most recently, with the lab's one-line verdict, or the idea itself if it has not run yet."
        >
          {latest.length ? (
            <ul className={s.cards}>
              {latest.map(m => (
                <li key={m.id} className={s.card}>
                  <div className={s.cardHead}>
                    <span className={`chip ${s.status}`} data-status={m.status} data-tip={STATUS_LABEL[m.status].meaning}>
                      {STATUS_LABEL[m.status].label}
                    </span>
                    <span className={s.cardId}>{m.id}</span>
                    <Link
                      href={m.href}
                      className={`icon-btn sm soft ${s.cardLink}`}
                      aria-label={`Open ${m.name}`}
                      data-tip={`Open ${m.id}`}
                    >
                      <ArrowUpRight size={20} strokeWidth={1.75} />
                    </Link>
                  </div>
                  <p className={s.cardName}>{m.name}</p>
                  <p className={m.blurbIsVerdict ? s.cardVerdict : s.cardIdea}>{m.blurb}</p>
                  <p className={s.cardMeta}>
                    {m.family} · {m.tries} {m.tries === 1 ? 'try' : 'tries'}
                    {m.bestPassed !== null ? ` · best ${m.bestPassed} of ${HURDLES}` : ''} · {dayText(m.updated)}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className={s.empty}>No lab methods yet.</p>
          )}
        </Section>
      </div>
    </>
  );
}
```
**Impact:** `/sera` now renders. It sits under the Phase 3 layout (shell and gate) and also gates itself with `requireSera`.

### Step 4: Page styles
**File:** `web/app/sera/overview.module.css:1` (new)
**Change:** A 12-column desktop grid at 1024 px and wider, and a single column below it (R1, out of scope for design). Story prose, stat grid, method cards and status chips use Seer v2 tokens only.
**Code:**
```css
/* Overview: one column below 1024px (readable, not designed); a 12-column sheet grid on desktop. */
.grid { display: flex; flex-direction: column; gap: 12px; }

.state, .landing, .hurdles, .closer, .luck, .families, .latest { min-width: 0; }

.stateBody { display: flex; flex-direction: column; gap: 24px; }

.story { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.storyMeta { font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-3); }

.prose { font-size: 17px; line-height: 1.5; color: var(--ink); }
.prose p { margin: 0 0 10px; }
.prose p:last-child { margin-bottom: 0; }
.prose h1, .prose h2, .prose h3, .prose h4 { margin: 14px 0 6px; font-size: 18px; font-weight: 500; letter-spacing: -0.01em; }
.prose ul, .prose ol { margin: 0 0 10px; padding-left: 20px; }
.prose li { margin: 2px 0; }
.prose strong { font-weight: 500; }
.prose code { font-size: 15px; padding: 1px 6px; border-radius: 8px; background: var(--stone); }
.prose a { text-decoration: underline; text-decoration-color: var(--outline); text-underline-offset: 3px; }
.prose table { width: 100%; border-collapse: collapse; font-size: 15px; margin: 6px 0 10px; }
.prose th, .prose td { padding: 6px 8px 6px 0; text-align: left; border-bottom: 1px solid var(--hair); font-weight: 400; }
.prose th { color: var(--ink-2); font-size: 13px; }

.stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px 24px; align-content: start; }

.twin { display: flex; flex-direction: column; gap: 18px; }
.mini { margin: 0; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.miniLabel { font-size: 15px; color: var(--ink-2); }

.empty { padding: 8px 0; font-size: 16px; line-height: 1.4; color: var(--ink-2); }

.cards { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; }
.card {
  min-width: 0;
  border-radius: 28px;
  padding: 18px 18px 20px 22px;
  background: var(--stone);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.cardHead { display: flex; align-items: center; gap: 10px; }
.cardId { flex: 1; min-width: 0; font-size: 14px; color: var(--ink-3); font-variant-numeric: tabular-nums; }
.cardLink { flex: none; }
.cardName { font-size: 20px; font-weight: 500; letter-spacing: -0.02em; line-height: 1.2; }
.cardVerdict { font-size: 15px; line-height: 1.4; color: var(--ink); }
.cardIdea { font-size: 15px; line-height: 1.4; color: var(--ink-2); font-style: italic; }
.cardMeta { margin-top: auto; padding-top: 4px; font-size: 13px; color: var(--ink-3); }

/* Status chips: one quiet fill per stage of the pipeline. */
.status { height: 30px; padding: 0 12px; font-size: 14px; background: var(--chip-solid); }
.status[data-status='idea'], .status[data-status='registered'] { background: var(--lav); }
.status[data-status='rejected'], .status[data-status='test-failed'] { background: var(--sheet); color: var(--ink-2); }
.status[data-status='blocked-data'] { background: var(--sky); }
.status[data-status='dev-eligible'], .status[data-status='promoted'] { background: var(--butter); }
.status[data-status='test-passed'], .status[data-status='paper'] { background: var(--coral); color: var(--on-coral); }

@media (min-width: 1024px) {
  .grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 12px; align-items: stretch; }

  .state { grid-column: span 12; }
  .landing { grid-column: span 8; }
  .hurdles { grid-column: span 4; }
  .closer { grid-column: span 6; }
  .luck { grid-column: span 6; }
  .families { grid-column: span 5; }
  .latest { grid-column: span 7; }

  .stateBody { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: 36px; align-items: start; }
  .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (min-width: 1360px) {
  .prose { font-size: 18px; }
}
```
**Impact:** Styles are scoped to the page. No global CSS changes.

## Verification

**Setup:** `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npm ci` (the worktree has no `node_modules`; never symlink main's, because Turbopack rejects a symlinked `node_modules` in `next build`; the lockfile is identical to main's).
**Build:** `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npx tsc --noEmit && NEXT_TELEMETRY_DISABLED=1 npx next build`. `next build` must list `/sera` as a dynamic route (ƒ). It needs no env (Phase 3, verified).
**Tests:** `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npx vitest run app/sera/overview.test.ts && npx vitest run`
**Manual check:** `npm run dev`, sign in as mahfuzh74@gmail.com, then open `/sera` at a width of 1280 px or more and check that:
- the 12-column grid lays out as: state full width; landing (8) beside hurdles (4); closer (6) beside luck (6); families (5) beside latest (7)
- the scatter's shaded pass zone sits at x ≤ 15%, y > 0
- hovering a dot shows `<candidate>: CAGR … vs SPY …, max DD …, misses: …` with plain hurdle names, and clicking it opens `/sera/methods/<id>`
- each glossary term shows its definition on hover
- each card's ArrowUpRight link shows its tooltip
- dark mode keeps every surface on tokens

With today's DB, expect:
- 58 points: 54 grey, 4 coral, none green
- luck bar: 4 points at N = 58, all below 0.95; the funnel's luck-check bar reads "0 of 4" (54 older tries predate it)
- story: "Weekly risk checks with monthly re-ranking". No synthesis exists yet, so the story falls back to the newest insight by `added`, which is this feature-wish
**Exit criteria:** `tsc` and `vitest` pass, and `next build` compiles `/sera`. The page renders all seven sections from `web/data/lab.json` with no hard-coded gate numbers, and calls `requireSera('/sera')`.

## Handoffs

- **Phase 2 / Phase 3 (resolved by the reconciler):** the draft's assumed `Axis`/`Tone`/`zones`/`lines`/`bars`+`max`/`Term k` props and the gate-taking derivations were replaced by the real exports listed under **Interfaces used**. Nothing is owed by either phase.
- **Shared prose style:** this page scopes its own `.prose` in `overview.module.css`. Phases 5 and 6 scope theirs in their own modules. No shared file is needed, and no two phases write the same CSS file.
- **Phase 2 (R5), optional:** plain family display names. Families render raw (`p7a-f1`, `stock-momentum-risk-managed`). A `familyLabel()` in `glossary.ts` would serve R5; if one is added later, map it in `familyBars` (label only).
- **Phase 7:** document the Overview's sections in the `web/package_readme.md` Sera section.

## Rollback

Delete the four new files: `web/app/sera/{page.tsx,overview.ts,overview.test.ts,overview.module.css}`. Nothing else references them, and `/sera` goes back to a 404 under the Phase 3 layout. Or revert the phase's single commit.
