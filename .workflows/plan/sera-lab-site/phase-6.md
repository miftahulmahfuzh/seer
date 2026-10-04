# Phase 6: Journal, Ideas, How it works

**Plan set:** `SERA_LAB_SITE_PLAN.md`
**Analysis:** `20261004-211729-H54F_code_analyzer.md`
**Satisfies:** R1, R4, R5, R6, R7. Three desktop pages: the insights journal and the food-for-thought ideas list (R6); the pipeline and time-window diagrams (R4); every rule and hurdle explained in plain words (R5). R7 (cross-cutting): every insight, idea and seen key is listed, plus every rule and glossary term.
**Depends on:** Phase 2 (`web/lib/sera/*`), Phase 3 (`/sera` layout and gate, `web/components/sera/{PageHeader,Section,Term}`). Phase 1 is needed only transitively, through Phase 2's `lab.ts`.
**Difficulty:** HARD
**Package:** `web/app/sera/{journal,ideas,how}`, `web/components/sera/diagrams`

---

## Goal

After this phase, `/sera/journal`, `/sera/ideas` and `/sera/how` render from the bundled snapshot.
- **Journal:** every insight, grouped under six plain headings, filterable by kind.
- **Ideas:** the backlog, the data wishlist (methods blocked on data), and the full reading list.
- **How it works:** two hand-built SVG diagrams (the pipeline from idea to real money, and the 1993-to-today time windows), the six hurdles with thresholds taken from `lab.gate`, the honesty rules, the data the lab has and lacks, and the glossary.

Nothing here computes a trading result. Every number on these pages is a count or a threshold read from the snapshot.

## Assumed interfaces

This plan codes against the exact exports of `phase-2.md` and `phase-3.md` (Phase 3 aligned by the reconciler). The reconciler type-checked the code below (`tsc --noEmit` clean) and ran its tests on top of both phases' code and a real snapshot in a scratch tree.

### Phase 2: as planned, used verbatim

| Import | Names used here |
|---|---|
| `@/lib/sera/lab` (pages only) | `lab: LabSnapshot`, `methodById(id): LabMethod \| undefined` |
| `@/lib/sera/markdown` (pages only) | `renderMarkdown(src: string): string` (escape-first HTML) |
| `@/lib/sera/types` / `../../../lib/sera/types` | types `LabSnapshot`, `LabMethod`, `LabTrial`, `LabInsight`, `LabSeen`, `InsightKind`, `Gate`; const `INSIGHT_KINDS` (order `synthesis, observation, hypothesis, data-wish, feature-wish, risk`, the Journal order) |
| `../../../lib/sera/glossary` | `GLOSSARY: Record<GlossaryKey, {term, plain}>`, `GLOSSARY_ORDER`, `type GlossaryKey`, `CONDITION_TERM`, `INSIGHT_KIND_LABEL` (`.heading` is the Journal heading), `SOURCE_KIND_LABEL` |
| `../../../lib/sera/derive` | `CONDITION_KEYS`, `type ConditionKey` |
| `../../../lib/sera/fixture` (tests only) | `GATE`, `method(over)`, `trial(over)` |

The `view.ts` files and their tests import `lib/sera/*` by relative path. `web/` has no vitest config, so the `@/` alias does not resolve under vitest (Phase 2, deviation 1). Pages import through `@/`.

Glossary keys used through the local `T k=` wrapper: `spyTr`, `maxDrawdown`, `profitFactor`, `trades`, `ownerInputs`, `dsr` (all through `CONDITION_TERM`), plus `tries`, `devWindow`, `testWindow`, `paperTrading`.

### Phase 3: aligned to `phase-3.md` (reconciled)

Phase 3 is the verified source of truth (its kit was compiled, tested and built). These pages use exactly:

```ts
import { PageHeader } from '@/components/sera/PageHeader'; // { eyebrow: string; title: string; lede?: ReactNode; asOf?: string; aside?: ReactNode }
import { Section } from '@/components/sera/Section';       // { eyebrow?; title?; caption?: ReactNode; bg?; aside?; id?; className?; children? }
import { Term } from '@/components/sera/Term';             // { term: string; definition: string; children?: ReactNode }
import { requireSera } from '@/lib/sera/gate';             // requireSera(next = '/sera'): redirect / notFound, as the layout does
```

- `Term` does not import the glossary. `how/page.tsx` defines a 3-line local `T({ k: GlossaryKey })` that passes `GLOSSARY[k].term` and `GLOSSARY[k].plain`.
- Each page calls `await requireSera('<its own path>')` first (Phase 3 handoff 1: a layout is not re-run on client-side navigation). The `/sera` layout gates too, and renders `children` inside the 1360 px content column.
- The layout's metadata template is `'%s · Sera'`, so pages set bare titles (`'Journal'`, `'Ideas'`, `'How it works'`).
- `Section` does take an `id`, but the in-page anchors (`#backlog`, `#blocked`, `#reading`) stay on wrapping `<div>`s this phase owns; both work, and the wrappers keep the anchors independent of Section's markup.
- `web/components/sera/diagrams/` is owned by this phase; Phase 3 creates nothing there.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- Routes `/sera/journal`, `/sera/ideas`, `/sera/how`. The links into them use `?kind=<InsightKind>` on the journal and the anchors `#backlog`, `#blocked`, `#reading` on ideas.
- `web/app/sera/journal/view.ts`:
  - types `KindFilter`, `KindCopy`, `JournalGroup`
  - `KIND_COPY`, `parseKind`, `journalHref`, `newestFirst`, `kindCounts`, `journalGroups`, `dayLabel`
- `web/app/sera/ideas/view.ts`:
  - types `ReadingLink`, `Concept`, `ConceptGroup`, `ReadingList`
  - `methodsWithStatus`, `needs`, `sourceLabel`, `sourceLink`, `urlParts`, `readingList`
- `web/app/sera/how/view.ts`:
  - types `HowInput`, `StageCounts`, `Hurdle`, `Rule`, `Fact`, `WindowsModel`
  - `PAPER_MONTHS`, `PAPER_TRADES`, `BEARS`
  - `pctLabel`, `count`, `stageCounts`, `pipelineStages`, `pipelineLabel`, `windowsModel`, `hurdles`, `honestyRules`, `dataFacts`
- `web/components/sera/diagrams/geometry.ts`: types `Box`, `PipelineStage`, `Era`; `rowBoxes`, `timeScale`, `yearTicks`, `monthYear`
- `web/components/sera/diagrams/Pipeline.tsx`: `Pipeline({ stages, failLabel, label })`
- `web/components/sera/diagrams/Windows.tsx`: `Windows({ start, devEnd, testStart, today, testNote, paperSince, bears, label })`
- `web/components/sera/diagrams/diagrams.module.css`
- Tests: `journal/view.test.ts`, `ideas/view.test.ts`, `how/view.test.ts`, `diagrams/geometry.test.ts`

**Signature changes:** none
**Requires (from earlier phases):**
- Phase 2: every name in the Phase 2 table above, as planned.
- Phase 3: `PageHeader`, `Section`, `Term`, `requireSera` (props above). Also the `/sera` layout with the gate, and the method detail route `/sera/methods/[id]`, which Phase 5 owns. The links here go to `/sera/methods/<id>` for every method id, including `idea` ones, because Phase 5 generates static params for all methods.
- Phase 1: `web/data/lab.json` exists. Insight `kind` may be `synthesis`.

**Leaves alone (owned by others):**
- `web/app/sera/layout.tsx`, `sera.module.css` and `not-found.tsx` (Phase 3)
- `web/components/sera/*` outside `diagrams/`, including `charts/` (Phase 3)
- `web/lib/sera/**` (Phases 2 and 3)
- `web/app/sera/page.tsx` (Phase 4)
- `web/app/sera/methods/**` (Phase 5)
- `web/data/lab.json` and `engine/**` (Phase 1)
- docs (Phase 7)

## Files

| File | Action | What changes |
|---|---|---|
| `web/components/sera/diagrams/geometry.ts` | create | pure layout math and the diagram data types |
| `web/components/sera/diagrams/geometry.test.ts` | create | tests for the layout math |
| `web/components/sera/diagrams/diagrams.module.css` | create | SVG fills and strokes from Seer v2 tokens |
| `web/components/sera/diagrams/Pipeline.tsx` | create | pipeline diagram (SVG) |
| `web/components/sera/diagrams/Windows.tsx` | create | time-windows diagram (SVG) |
| `web/app/sera/journal/view.ts` | create | journal grouping, filtering and copy |
| `web/app/sera/journal/view.test.ts` | create | tests |
| `web/app/sera/journal/journal.module.css` | create | journal layout, cards, markdown body |
| `web/app/sera/journal/page.tsx` | create | Journal route |
| `web/app/sera/ideas/view.ts` | create | backlog, wishlist and reading-list shaping |
| `web/app/sera/ideas/view.test.ts` | create | tests |
| `web/app/sera/ideas/ideas.module.css` | create | ideas layout |
| `web/app/sera/ideas/page.tsx` | create | Ideas route |
| `web/app/sera/how/view.ts` | create | pipeline counts, hurdles, rules, data facts |
| `web/app/sera/how/view.test.ts` | create | tests |
| `web/app/sera/how/how.module.css` | create | How-it-works layout |
| `web/app/sera/how/page.tsx` | create | How it works route |

17 files, all new. No existing file is modified.

## Implementation Steps

### Step 0: Worktree setup
The worktree has no `web/node_modules`. Run this before anything else:
```sh
cd /home/miftah/.worktrees/seer/sera-lab-site/web && npm ci
```
Confirm Phases 1–3 landed:
```sh
test -f /home/miftah/.worktrees/seer/sera-lab-site/web/data/lab.json
test -f /home/miftah/.worktrees/seer/sera-lab-site/web/lib/sera/glossary.ts
test -f /home/miftah/.worktrees/seer/sera-lab-site/web/components/sera/Section.tsx
```

### Step 1: Diagram geometry
**File:** `web/components/sera/diagrams/geometry.ts:1` (new)
**Change:** Pure layout math for the two diagrams, plus the data types they take. It has no React and no snapshot import, so `how/view.ts` can import it at runtime under vitest.
**Code:**
```ts
// Pure layout math for the hand-built SVG diagrams on /sera/how. No React, no snapshot.

export type Box = { x: number; y: number; w: number; h: number };

/** One box of the pipeline diagram. Lines are pre-broken: SVG text does not wrap. */
export type PipelineStage = {
  key: string;
  /** 1–2 short lines (≤ 14 characters each). */
  title: string[];
  /** 1–5 short lines (≤ 18 characters, ≤ 26 on a weight-1.35 box). */
  detail: string[];
  /** The pill at the bottom, e.g. '58 tries'. */
  count: string;
  /** Tooltip on the pill. */
  countTip: string;
  /** Draws a dashed "fails" arrow from this box down to the journal lane. */
  fails: boolean;
  /** Relative width; 1 when omitted. */
  weight?: number;
  /** The last stage (real money) gets the accent fill. */
  final?: boolean;
};

/** A dated stretch of history, e.g. a bear market. Dates are ISO yyyy-mm-dd. */
export type Era = { start: string; end: string; label: string; years: string };

/** Boxes left to right across `width`, sized by `weights`, separated by `gap`. */
export function rowBoxes(weights: number[], width: number, gap: number, y: number, h: number): Box[] {
  if (weights.length === 0) return [];
  const total = weights.reduce((a, w) => a + w, 0);
  const unit = (width - gap * (weights.length - 1)) / total;
  const out: Box[] = [];
  let x = 0;
  for (const w of weights) {
    out.push({ x, y, w: w * unit, h });
    x += w * unit + gap;
  }
  return out;
}

const toTime = (iso: string) => Date.parse(`${iso.slice(0, 10)}T00:00:00Z`);

/** Linear date -> x over [start, end] onto [x0, x1], clamped to the range. */
export function timeScale(start: string, end: string, x0: number, x1: number): (iso: string) => number {
  const t0 = toTime(start);
  const span = toTime(end) - t0 || 1;
  return (iso: string) => {
    const f = Math.min(1, Math.max(0, (toTime(iso) - t0) / span));
    return x0 + f * (x1 - x0);
  };
}

/** Years divisible by `step` after start's year, up to end's year. */
export function yearTicks(start: string, end: string, step: number): number[] {
  const y0 = Number(start.slice(0, 4));
  const y1 = Number(end.slice(0, 4));
  const out: number[] = [];
  for (let y = Math.ceil((y0 + 1) / step) * step; y <= y1; y += step) out.push(y);
  return out;
}

const MONTH_YEAR = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', year: 'numeric' });

/** '2015-10-16' -> 'Oct 2015' */
export const monthYear = (iso: string) => MONTH_YEAR.format(new Date(`${iso.slice(0, 10)}T12:00:00Z`));
```
**Impact:** none; new file.

### Step 2: Geometry tests
**File:** `web/components/sera/diagrams/geometry.test.ts:1` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { monthYear, rowBoxes, timeScale, yearTicks } from './geometry';

describe('rowBoxes', () => {
  it('fills the width exactly with equal weights', () => {
    const b = rowBoxes([1, 1, 1, 1, 1, 1, 1], 1240, 26, 8, 228);
    expect(b).toHaveLength(7);
    expect(b[0].x).toBe(0);
    expect(b[6].x + b[6].w).toBeCloseTo(1240, 6);
    expect(b[1].x - (b[0].x + b[0].w)).toBeCloseTo(26, 6);
    expect(b.every(x => x.y === 8 && x.h === 228)).toBe(true);
  });
  it('sizes boxes by weight', () => {
    const b = rowBoxes([1, 2, 1], 400, 0, 0, 10);
    expect(b.map(x => x.w)).toEqual([100, 200, 100]);
    expect(b.map(x => x.x)).toEqual([0, 100, 300]);
  });
  it('returns nothing for no stages', () => {
    expect(rowBoxes([], 100, 10, 0, 10)).toEqual([]);
  });
});

describe('timeScale', () => {
  const x = timeScale('2000-01-01', '2010-01-01', 0, 100);
  it('maps the ends and the middle', () => {
    expect(x('2000-01-01')).toBe(0);
    expect(x('2010-01-01')).toBe(100);
    expect(x('2005-01-01')).toBeCloseTo(50, 0);
  });
  it('accepts timestamps and clamps outside dates', () => {
    expect(x('2010-01-01T14:12:19+00:00')).toBe(100);
    expect(x('1990-06-30')).toBe(0);
    expect(x('2030-06-30')).toBe(100);
  });
  it('never divides by zero', () => {
    expect(Number.isFinite(timeScale('2000-01-01', '2000-01-01', 0, 10)('2000-01-01'))).toBe(true);
  });
});

describe('yearTicks', () => {
  it('lists the round years after the start year', () => {
    expect(yearTicks('1993-01-29', '2026-10-04', 5)).toEqual([1995, 2000, 2005, 2010, 2015, 2020, 2025]);
    expect(yearTicks('1995-01-03', '2001-01-01', 5)).toEqual([2000]);
  });
});

describe('monthYear', () => {
  it('formats in UTC', () => {
    expect(monthYear('2015-10-16')).toBe('Oct 2015');
    expect(monthYear('1993-01-29T00:00:00+00:00')).toBe('Jan 1993');
  });
});
```

### Step 3: Diagram styles
**File:** `web/components/sera/diagrams/diagrams.module.css:1` (new)
**Change:** All fills and strokes come from CSS classes on `var(--…)` tokens, not from presentation attributes. Light and dark mode follow `globals.css`.
**Code:**
```css
/* Hand-built SVG diagrams for /sera/how. Seer v2 tokens only; text inherits Outfit from body. */
.svg { display: block; width: 100%; height: auto; overflow: visible; font-family: inherit; }

/* Pipeline */
.box { fill: var(--stone); }
.boxFinal { fill: var(--butter); }
.step { fill: var(--ink-3); font-size: 12px; letter-spacing: 0.12em; }
.title { fill: var(--ink); font-size: 15px; font-weight: 500; }
.detail { fill: var(--ink-2); font-size: 12px; }
.count { fill: var(--sheet); }
.countText { fill: var(--ink); font-size: 13px; font-variant-numeric: tabular-nums; }
.arrow { stroke: var(--ink-2); stroke-width: 1.5; fill: none; }
.arrowHead { fill: var(--ink-2); }
.failArrow { stroke: var(--neg); stroke-width: 1.5; stroke-dasharray: 4 4; fill: none; }
.failHead { fill: var(--neg); }
.lane { fill: none; stroke: var(--neg); stroke-width: 1.5; stroke-dasharray: 4 4; }
.laneText { fill: var(--neg); font-size: 14px; }

/* Windows */
.devBand { fill: var(--lav); }
.testBand { fill: var(--butter); }
.paperBand { fill: var(--sky); }
.bandTitle { fill: var(--ink); font-size: 15px; font-weight: 500; }
.bandText { fill: var(--ink-2); font-size: 12.5px; }
.muted { fill: var(--ink-3); font-size: 13px; }
.bear { fill: var(--neg); opacity: 0.12; }
.bearTitle { fill: var(--neg); font-size: 12.5px; font-weight: 500; }
.bearText { fill: var(--neg); font-size: 12px; }
.split { stroke: var(--ink); stroke-width: 1.25; stroke-dasharray: 3 4; }
.splitText { fill: var(--ink); font-size: 12.5px; }
.axis { stroke: var(--outline); stroke-width: 1; }
.tick { stroke: var(--outline); stroke-width: 1; }
.tickText { fill: var(--ink-2); font-size: 12px; font-variant-numeric: tabular-nums; }
.today { stroke: var(--ink-2); stroke-width: 1.25; }
```

### Step 4: Pipeline diagram
**File:** `web/components/sera/diagrams/Pipeline.tsx:1` (new)
**Change:** A server component that draws the stages left to right with forward arrows. Each stage with `fails` sends a red dashed arrow down to a "fails" lane, and the lane sends an arrow back up into the first stage (the idea), which closes the loop. Each count pill carries a `data-tip`. The viewBox is 1240 wide, so at desktop width the text renders at about its nominal px size.
**Code:**
```tsx
import { rowBoxes, type PipelineStage } from './geometry';
import s from './diagrams.module.css';

type Props = {
  stages: PipelineStage[];
  /** Text inside the fails lane. */
  failLabel: string;
  /** Accessible summary of the whole diagram. */
  label: string;
};

const W = 1240;
const GAP = 26;
const TOP = 8;
const BOX_H = 228;
const LANE_Y = 286;
const LANE_H = 44;
const H = LANE_Y + LANE_H + 8;
const PAD = 16;
const ARROW = 'sera-pipeline-arrow';
const FAIL = 'sera-pipeline-fail';

/** The path from idea to real money; one per page (marker ids are fixed). */
export function Pipeline({ stages, failLabel, label }: Props) {
  const boxes = rowBoxes(stages.map(st => st.weight ?? 1), W, GAP, TOP, BOX_H);
  const bottom = TOP + BOX_H;
  const arrowY = TOP + 46;
  const failIdx = stages.flatMap((st, i) => (st.fails ? [i] : []));
  const first = boxes[0];
  const lastFail = failIdx.length ? boxes[failIdx[failIdx.length - 1]] : undefined;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={s.svg} role="img" aria-label={label}>
      <defs>
        <marker id={ARROW} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" className={s.arrowHead} />
        </marker>
        <marker id={FAIL} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" className={s.failHead} />
        </marker>
      </defs>

      {boxes.slice(0, -1).map((b, i) => (
        <line key={`fwd-${stages[i].key}`} x1={b.x + b.w + 3} x2={boxes[i + 1].x - 3} y1={arrowY} y2={arrowY}
          className={s.arrow} markerEnd={`url(#${ARROW})`} />
      ))}

      {stages.map((st, i) => {
        const b = boxes[i];
        const detailY = b.y + 56 + st.title.length * 20 + 10;
        return (
          <g key={st.key}>
            <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={24} className={st.final ? s.boxFinal : s.box} />
            <text x={b.x + PAD} y={b.y + 28} className={s.step}>{String(i + 1).padStart(2, '0')}</text>
            {st.title.map((line, j) => (
              <text key={`t${j}`} x={b.x + PAD} y={b.y + 56 + j * 20} className={s.title}>{line}</text>
            ))}
            {st.detail.map((line, j) => (
              <text key={`d${j}`} x={b.x + PAD} y={detailY + j * 17} className={s.detail}>{line}</text>
            ))}
            <g data-tip={st.countTip}>
              <rect x={b.x + 12} y={b.y + b.h - 44} width={b.w - 24} height={32} rx={16} className={s.count} />
              <text x={b.x + b.w / 2} y={b.y + b.h - 23} textAnchor="middle" className={s.countText}>{st.count}</text>
            </g>
          </g>
        );
      })}

      {first && lastFail && (
        <g>
          {failIdx.map(i => {
            const cx = boxes[i].x + boxes[i].w / 2;
            return (
              <line key={`fail-${stages[i].key}`} x1={cx} x2={cx} y1={bottom + 3} y2={LANE_Y - 3}
                className={s.failArrow} markerEnd={`url(#${FAIL})`} />
            );
          })}
          <line x1={first.x + first.w / 2} x2={first.x + first.w / 2} y1={LANE_Y - 3} y2={bottom + 3}
            className={s.failArrow} markerEnd={`url(#${FAIL})`} />
          <rect x={first.x} y={LANE_Y} width={lastFail.x + lastFail.w - first.x} height={LANE_H} rx={LANE_H / 2}
            className={s.lane} />
          <text x={(first.x + lastFail.x + lastFail.w) / 2} y={LANE_Y + LANE_H / 2 + 5} textAnchor="middle"
            className={s.laneText}>{failLabel}</text>
        </g>
      )}
    </svg>
  );
}
```
**Impact:** none. The SVG is `role="img"` with a full `aria-label`, and the count pills' `data-tip` work through the existing `TooltipLayer`, because `closest('[data-tip]')` works on SVG elements.

### Step 5: Windows diagram
**File:** `web/components/sera/diagrams/Windows.tsx:1` (new)
**Change:** A timeline from the first data day to "today" (the snapshot's `asOf`, so builds are deterministic). It shows:
- a dev band and a test band, with a dashed split line between them
- a paper band, or a muted note when nothing is on paper
- the bear markets as red tint over everything, with labels at the top
- five-year ticks, which drop out within 50 px of either end so they never collide with the "1993" and "Today" labels
**Code:**
```tsx
import { monthYear, timeScale, yearTicks, type Era } from './geometry';
import s from './diagrams.module.css';

type Props = {
  /** First day of the dev window (= first data day). */
  start: string;
  devEnd: string;
  testStart: string;
  /** The snapshot's as-of date: the right edge. */
  today: string;
  /** e.g. 'untouched, no look used yet' or '2 looks used'. */
  testNote: string;
  /** First day any lab method went on paper, or null. */
  paperSince: string | null;
  bears: Era[];
  /** Accessible summary of the whole diagram. */
  label: string;
};

const W = 1240;
const X0 = 24;
const X1 = 1216;
const BAND_Y = 58;
const BAND_H = 64;
const PAPER_Y = 136;
const PAPER_H = 44;
const AXIS_Y = 232;
const H = 262;

export function Windows({ start, devEnd, testStart, today, testNote, paperSince, bears, label }: Props) {
  const x = timeScale(start, today, X0, X1);
  const devX1 = x(devEnd);
  const testX0 = x(testStart) + 3;
  const todayX = x(today);
  const ticks = yearTicks(start, today, 5).filter(y => {
    const tx = x(`${y}-01-01`);
    return tx > X0 + 50 && tx < X1 - 50;
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={s.svg} role="img" aria-label={label}>
      <rect x={X0} y={BAND_Y} width={Math.max(0, devX1 - X0)} height={BAND_H} rx={18} className={s.devBand} />
      <text x={X0 + 18} y={BAND_Y + 27} className={s.bandTitle}>Practice years · dev window</text>
      <text x={X0 + 18} y={BAND_Y + 47} className={s.bandText}>
        {monthYear(start)} – {monthYear(devEnd)} · every idea is built and tested here
      </text>

      <rect x={testX0} y={BAND_Y} width={Math.max(0, todayX - testX0)} height={BAND_H} rx={18} className={s.testBand} />
      <text x={testX0 + 18} y={BAND_Y + 27} className={s.bandTitle}>Exam years · test window</text>
      <text x={testX0 + 18} y={BAND_Y + 47} className={s.bandText}>
        {monthYear(testStart)} – today · {testNote}
      </text>

      {paperSince ? (
        <>
          <rect x={x(paperSince)} y={PAPER_Y} width={Math.max(4, todayX - x(paperSince))} height={PAPER_H} rx={16}
            className={s.paperBand} />
          <text x={todayX - 14} y={PAPER_Y + 27} textAnchor="end" className={s.bandTitle}>
            On paper since {monthYear(paperSince)}
          </text>
        </>
      ) : (
        <text x={todayX} y={PAPER_Y + 27} textAnchor="end" className={s.muted}>Paper trading: no lab method yet</text>
      )}

      <line x1={devX1 + 1.5} x2={devX1 + 1.5} y1={BAND_Y - 14} y2={AXIS_Y} className={s.split} />
      <text x={devX1 + 1.5} y={BAND_Y - 20} textAnchor="middle" className={s.splitText}>
        The split · {monthYear(devEnd)}
      </text>

      {bears.map(b => (
        <g key={b.start}>
          <rect x={x(b.start)} y={10} width={Math.max(2, x(b.end) - x(b.start))} height={AXIS_Y - 10} className={s.bear} />
          <text x={x(b.start) + 6} y={24} className={s.bearTitle}>{b.label}</text>
          <text x={x(b.start) + 6} y={40} className={s.bearText}>{b.years}</text>
        </g>
      ))}

      <line x1={X0} x2={X1} y1={AXIS_Y} y2={AXIS_Y} className={s.axis} />
      <line x1={todayX} x2={todayX} y1={BAND_Y} y2={AXIS_Y + 6} className={s.today} />
      {ticks.map(y => {
        const tx = x(`${y}-01-01`);
        return (
          <g key={y}>
            <line x1={tx} x2={tx} y1={AXIS_Y} y2={AXIS_Y + 6} className={s.tick} />
            <text x={tx} y={AXIS_Y + 22} textAnchor="middle" className={s.tickText}>{y}</text>
          </g>
        );
      })}
      <text x={X0} y={AXIS_Y + 22} className={s.tickText}>{start.slice(0, 4)}</text>
      <text x={X1} y={AXIS_Y + 22} textAnchor="end" className={s.tickText}>Today</text>
    </svg>
  );
}
```
**Impact:** none.

### Step 6: Journal view helpers
**File:** `web/app/sera/journal/view.ts:1` (new)
**Change:** The order and the headings come from Phase 2 (`INSIGHT_KINDS`, `INSIGHT_KIND_LABEL`). This file adds the per-kind caption, the empty-state sentence and the card tone, then groups and filters the insights.
**Code:**
```ts
// Pure helpers for /sera/journal. No data access; page.tsx feeds lab.insights.
import { INSIGHT_KIND_LABEL } from '../../../lib/sera/glossary';
import { INSIGHT_KINDS, type InsightKind, type LabInsight } from '../../../lib/sera/types';

export type KindFilter = InsightKind | 'all';

/** What the Journal says around each kind; the heading itself is INSIGHT_KIND_LABEL[kind].heading. */
export type KindCopy = { caption: string; empty: string; tone: string };

export const KIND_COPY: Record<InsightKind, KindCopy> = {
  synthesis: {
    caption: 'What a whole batch of tries added up to, written when the batch ended.',
    empty: 'No batch summary yet. Sera writes one each time it finishes a batch of tries.',
    tone: 'bg-lav',
  },
  observation: {
    caption: 'Facts the tests showed, whether or not the method passed.',
    empty: 'Nothing learned is written down yet.',
    tone: 'bg-sky',
  },
  hypothesis: {
    caption: 'Hunches the results suggest. Any of them can become the next method.',
    empty: 'No untested hunch is written down yet.',
    tone: 'bg-butter',
  },
  'data-wish': {
    caption: 'Data the lab does not have that would open up new kinds of methods.',
    empty: 'No data wish yet.',
    tone: 'bg-stone',
  },
  'feature-wish': {
    caption: 'Tools that would let the lab test things it cannot test today.',
    empty: 'No feature wish yet.',
    tone: 'bg-lav',
  },
  risk: {
    caption: 'Ways the lab could fool itself, or a good test could still fail with real money.',
    empty: 'No risk is written down yet.',
    tone: 'bg-butter',
  },
};

/** `?kind=` value -> a known kind, else 'all'. */
export function parseKind(raw: string | string[] | undefined): KindFilter {
  const v = Array.isArray(raw) ? raw[0] : raw;
  return (INSIGHT_KINDS as readonly string[]).includes(v ?? '') ? (v as InsightKind) : 'all';
}

export const journalHref = (kind: KindFilter) =>
  kind === 'all' ? '/sera/journal' : `/sera/journal?kind=${encodeURIComponent(kind)}`;

/** Newest first by `added`; ties by higher id first. */
export function newestFirst(a: LabInsight, b: LabInsight): number {
  if (a.added !== b.added) return a.added < b.added ? 1 : -1;
  return b.id - a.id;
}

export function kindCounts(insights: readonly LabInsight[]): Record<InsightKind, number> {
  const out = Object.fromEntries(INSIGHT_KINDS.map(k => [k, 0])) as Record<InsightKind, number>;
  for (const i of insights) if (i.kind in out) out[i.kind] += 1;
  return out;
}

export type JournalGroup = KindCopy & { kind: InsightKind; heading: string; entries: LabInsight[] };

/** One group per kind in Journal order (every kind when filter is 'all'), entries newest first. */
export function journalGroups(insights: readonly LabInsight[], filter: KindFilter): JournalGroup[] {
  return INSIGHT_KINDS
    .filter(k => filter === 'all' || k === filter)
    .map(kind => ({
      kind,
      heading: INSIGHT_KIND_LABEL[kind].heading,
      ...KIND_COPY[kind],
      entries: insights.filter(i => i.kind === kind).sort(newestFirst),
    }));
}

const DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' });

/** '2026-10-04T14:12:19+00:00' or '2026-10-04' -> 'Oct 4, 2026' (UTC). */
export const dayLabel = (iso: string) =>
  DAY.format(new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso));
```
**Impact:** none.

### Step 7: Journal view tests
**File:** `web/app/sera/journal/view.test.ts:1` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import type { LabInsight } from '../../../lib/sera/types';
import { dayLabel, journalGroups, journalHref, kindCounts, newestFirst, parseKind } from './view';

const ins = (over: Partial<LabInsight> & Pick<LabInsight, 'id' | 'kind'>): LabInsight => ({
  title: `t${over.id}`,
  body: 'b',
  methodId: null,
  added: '2026-10-04T10:00:00+00:00',
  ...over,
});

const ALL: LabInsight[] = [
  ins({ id: 1, kind: 'observation', added: '2026-10-04T14:12:19+00:00', methodId: 'M0001' }),
  ins({ id: 2, kind: 'data-wish', added: '2026-10-04T14:12:20+00:00' }),
  ins({ id: 3, kind: 'observation', added: '2026-10-05T09:00:00+00:00' }),
  ins({ id: 4, kind: 'synthesis', added: '2026-10-05T09:00:00+00:00' }),
  ins({ id: 5, kind: 'observation', added: '2026-10-05T09:00:00+00:00' }),
];

describe('parseKind', () => {
  it('accepts every known kind', () => {
    for (const k of ['synthesis', 'observation', 'hypothesis', 'data-wish', 'feature-wish', 'risk']) {
      expect(parseKind(k)).toBe(k);
    }
  });
  it('falls back to all', () => {
    expect(parseKind(undefined)).toBe('all');
    expect(parseKind('nope')).toBe('all');
    expect(parseKind('')).toBe('all');
    expect(parseKind(['risk', 'observation'])).toBe('risk');
  });
});

describe('journalHref', () => {
  it('drops the param for all', () => {
    expect(journalHref('all')).toBe('/sera/journal');
    expect(journalHref('data-wish')).toBe('/sera/journal?kind=data-wish');
  });
});

describe('newestFirst', () => {
  it('orders by date, then by id', () => {
    expect([...ALL].sort(newestFirst).map(i => i.id)).toEqual([5, 4, 3, 2, 1]);
  });
});

describe('kindCounts', () => {
  it('counts every kind, zero included', () => {
    expect(kindCounts(ALL)).toEqual({
      synthesis: 1, observation: 3, hypothesis: 0, 'data-wish': 1, 'feature-wish': 0, risk: 0,
    });
  });
});

describe('journalGroups', () => {
  it('lists all six kinds in the Journal order with plain headings', () => {
    const g = journalGroups(ALL, 'all');
    expect(g.map(x => x.kind)).toEqual(['synthesis', 'observation', 'hypothesis', 'data-wish', 'feature-wish', 'risk']);
    expect(g.map(x => x.heading)).toEqual([
      'Batch summaries', 'What we learned', 'Ideas worth testing', 'Data we wish we had', 'Features to build', 'Risks we see',
    ]);
    expect(g[1].entries.map(i => i.id)).toEqual([5, 3, 1]);
    expect(g[2].entries).toEqual([]);
    expect(g[2].empty.length).toBeGreaterThan(0);
  });
  it('keeps only the filtered kind', () => {
    const g = journalGroups(ALL, 'data-wish');
    expect(g).toHaveLength(1);
    expect(g[0].entries.map(i => i.id)).toEqual([2]);
  });
  it('does not reorder the input', () => {
    const copy = [...ALL];
    journalGroups(copy, 'all');
    expect(copy.map(i => i.id)).toEqual([1, 2, 3, 4, 5]);
  });
});

describe('dayLabel', () => {
  it('formats timestamps and dates in UTC', () => {
    expect(dayLabel('2026-10-04T14:12:19+00:00')).toBe('Oct 4, 2026');
    expect(dayLabel('2015-10-16')).toBe('Oct 16, 2015');
  });
});
```

### Step 8: Journal styles
**File:** `web/app/sera/journal/journal.module.css:1` (new)
**Code:**
```css
/* Journal: a filter bar, then one sheet per kind holding two columns of insight cards. */
.page { display: flex; flex-direction: column; gap: 12px; }

.bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 4px 0 2px; }
.barNote { font-size: 15px; color: var(--ink-2); }
.segBtn { position: relative; }
.badge {
  position: absolute; top: -4px; right: -4px; min-width: 20px; height: 20px; padding: 0 6px;
  border-radius: 999px; background: var(--coral); color: var(--on-coral);
  font-size: 11.5px; line-height: 20px; text-align: center; font-variant-numeric: tabular-nums;
  pointer-events: none;
}
.badge.zero { background: var(--outline); color: var(--ink-2); }

.cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.card { border-radius: 28px; padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 12px; }
.cardHead { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.cardTitle { margin: 0; font-size: 20px; font-weight: 500; letter-spacing: -0.01em; line-height: 1.25; }
.date { flex: none; font-size: 13px; color: var(--ink-2); white-space: nowrap; }

.body { font-size: 15.5px; line-height: 1.5; overflow-wrap: anywhere; }
.body :global(p) { margin: 0 0 10px; }
.body :global(p:last-child) { margin-bottom: 0; }
.body :global(ul), .body :global(ol) { margin: 0 0 10px; padding-left: 20px; }
.body :global(li) { margin: 2px 0; }
.body :global(strong) { font-weight: 600; }
.body :global(code) { font-size: 0.92em; padding: 1px 6px; border-radius: 6px; background: var(--chip); }
.body :global(a) { text-decoration: underline; text-underline-offset: 3px; }
.body :global(h3), .body :global(h4), .body :global(h5) { margin: 12px 0 6px; font-size: 16px; font-weight: 500; }
.body :global(table) { border-collapse: collapse; font-size: 14px; margin: 0 0 10px; }
.body :global(th), .body :global(td) { padding: 6px 12px 6px 0; border-bottom: 1px solid var(--hair); text-align: left; font-weight: 400; }

.cardFoot { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 4px; }
.about { font-size: 14px; color: var(--ink-2); }
.empty { font-size: 16px; color: var(--ink-2); }

@media (max-width: 1023.98px) {
  .cards { grid-template-columns: 1fr; }
  .bar { flex-direction: column; align-items: flex-start; }
}
```

### Step 9: Journal page
**File:** `web/app/sera/journal/page.tsx:1` (new)
**Change:** A server component. The page lays out:
- a segmented filter, one icon-only `Link` per kind plus "All". Each `Link` has an `aria-label`, a `data-tip` naming the heading and its count, and a count badge.
- one `Section` per shown kind, with its count in the eyebrow and a plain caption.
- cards with the title, the date, the markdown body, and an icon-only link to the method when `methodId` is set.
**Code:**
```tsx
import {
  ArrowUpRight, Database, FlaskRound, Layers, ListFilter, Sparkles, TriangleAlert, Wrench, type LucideIcon,
} from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSera } from '@/lib/sera/gate';
import { INSIGHT_KIND_LABEL } from '@/lib/sera/glossary';
import { lab, methodById } from '@/lib/sera/lab';
import { renderMarkdown } from '@/lib/sera/markdown';
import { INSIGHT_KINDS, type InsightKind, type LabInsight } from '@/lib/sera/types';
import { dayLabel, journalGroups, journalHref, kindCounts, parseKind, type KindFilter } from './view';
import s from './journal.module.css';

// The layout's title template renders this as "Journal · Sera".
export const metadata: Metadata = { title: 'Journal' };

const KIND_ICON: Record<InsightKind, LucideIcon> = {
  synthesis: Layers,
  observation: Sparkles,
  hypothesis: FlaskRound,
  'data-wish': Database,
  'feature-wish': Wrench,
  risk: TriangleAlert,
};

type Search = { kind?: string | string[] };

export default async function JournalPage({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const filter = parseKind(q.kind);
  await requireSera(journalHref(filter));
  const counts = kindCounts(lab.insights);
  const groups = journalGroups(lab.insights, filter);
  const total = lab.insights.length;

  const options: { id: KindFilter; tip: string; n: number; Icon: LucideIcon }[] = [
    { id: 'all', tip: `Everything · ${total}`, n: total, Icon: ListFilter },
    ...INSIGHT_KINDS.map(k => ({
      id: k as KindFilter,
      tip: `${INSIGHT_KIND_LABEL[k].heading} · ${counts[k]}`,
      n: counts[k],
      Icon: KIND_ICON[k],
    })),
  ];

  return (
    <>
      <PageHeader
        eyebrow="Journal"
        title="What the lab is thinking"
        lede="Everything the lab noticed along the way: lessons, hunches, the data and tools it wishes it had, and the risks it sees. Food for thought, newest first."
        asOf={lab.asOf}
      />
      <div className={s.page}>
        <div className={s.bar}>
          <nav className="seg" aria-label="Show one kind of entry">
            {options.map(({ id, tip, n, Icon }) => {
              const on = id === filter;
              return (
                <Link key={id} href={journalHref(id)} replace scroll={false} className={`icon-btn md ${s.segBtn}`}
                  data-tip={tip} aria-label={tip} aria-current={on ? 'true' : undefined}>
                  <Icon size={19} strokeWidth={on ? 2 : 1.5} />
                  <span className={`${s.badge} ${n === 0 ? s.zero : ''}`} aria-hidden="true">{n}</span>
                </Link>
              );
            })}
          </nav>
          <p className={s.barNote}>
            {total} {total === 1 ? 'entry' : 'entries'} in all. Every lab run adds to this page.
          </p>
        </div>

        {groups.map(g => (
          <Section
            key={g.kind}
            eyebrow={`${g.entries.length} ${g.entries.length === 1 ? 'entry' : 'entries'}`}
            title={g.heading}
            caption={g.caption}
          >
            {g.entries.length === 0 ? (
              <p className={s.empty}>{g.empty}</p>
            ) : (
              <div className={s.cards}>
                {g.entries.map(i => <InsightCard key={i.id} insight={i} tone={g.tone} />)}
              </div>
            )}
          </Section>
        ))}
      </div>
    </>
  );
}

function InsightCard({ insight, tone }: { insight: LabInsight; tone: string }) {
  const method = insight.methodId ? methodById(insight.methodId) : undefined;
  return (
    <article className={`${s.card} ${tone}`}>
      <header className={s.cardHead}>
        <h3 className={s.cardTitle}>{insight.title}</h3>
        <time className={s.date} dateTime={insight.added}>{dayLabel(insight.added)}</time>
      </header>
      <div className={s.body} dangerouslySetInnerHTML={{ __html: renderMarkdown(insight.body) }} />
      {insight.methodId && (
        <footer className={s.cardFoot}>
          <span className={s.about}>
            About {insight.methodId}{method ? ` · ${method.name}` : ''}
          </span>
          {method && (
            <Link href={`/sera/methods/${encodeURIComponent(method.id)}`} className="icon-btn sm"
              aria-label={`Open ${method.id}, ${method.name}`} data-tip={`Open ${method.id}`}>
              <ArrowUpRight size={18} strokeWidth={1.5} />
            </Link>
          )}
        </footer>
      )}
    </article>
  );
}
```
**Impact:** new route. It is dynamic because the Phase 3 layout reads the session and the page reads `searchParams`.

### Step 10: Ideas view helpers
**File:** `web/app/sera/ideas/view.ts:1` (new)
**Code:**
```ts
// Pure helpers for /sera/ideas. No data access; page.tsx feeds lab.methods and lab.ideasSeen.
import { SOURCE_KIND_LABEL } from '../../../lib/sera/glossary';
import type { LabMethod, LabSeen } from '../../../lib/sera/types';

/** Methods with one status, ordered by id (numeric-aware: M0002 before M0010). */
export function methodsWithStatus(methods: readonly LabMethod[], status: LabMethod['status']): LabMethod[] {
  return methods
    .filter(m => m.status === status)
    .sort((a, b) => a.id.localeCompare(b.id, 'en', { numeric: true }));
}

/** The data wishlist line for a blocked method. */
export function needs(blockedOn: string): string {
  const t = blockedOn.trim();
  return t ? `needs: ${t}` : 'needs: not written down yet';
}

export const sourceLabel = (kind: string): string =>
  (SOURCE_KIND_LABEL as Record<string, string>)[kind] ?? kind;

/** The source ref when it is an http(s) URL, else null. */
export function sourceLink(ref: string): string | null {
  const t = ref.trim();
  return /^https?:\/\//i.test(t) && urlParts(t).safe ? t : null;
}

/** Safe-to-link check plus short display text for a URL. */
export function urlParts(url: string): { safe: boolean; host: string; display: string } {
  try {
    const u = new URL(url);
    const safe = u.protocol === 'https:' || u.protocol === 'http:';
    const full = (u.host + u.pathname + u.search).replace(/\/$/, '');
    return { safe, host: u.host || url, display: full.length > 72 ? `${full.slice(0, 71)}…` : full };
  } catch {
    return { safe: false, host: url, display: url };
  }
}

export type ReadingLink = {
  key: string;
  url: string;
  safe: boolean;
  host: string;
  display: string;
  note: string;
  methodId: string | null;
  added: string;
};
export type Concept = { key: string; label: string; note: string };
export type ConceptGroup = { methodId: string | null; concepts: Concept[] };
export type ReadingList = { links: ReadingLink[]; groups: ConceptGroup[]; conceptCount: number };

/**
 * `url:` keys become links (newest first); every other key is a concept (the `concept:` prefix
 * is dropped), grouped by the method it led to (ids in numeric order, untied concepts last).
 */
export function readingList(seen: readonly LabSeen[]): ReadingList {
  const links: ReadingLink[] = [];
  const byMethod = new Map<string | null, Concept[]>();
  for (const it of seen) {
    if (it.key.startsWith('url:')) {
      const url = it.key.slice(4).trim();
      links.push({ key: it.key, url, ...urlParts(url), note: it.note, methodId: it.methodId, added: it.added });
      continue;
    }
    const label = it.key.startsWith('concept:') ? it.key.slice(8) : it.key;
    const list = byMethod.get(it.methodId) ?? [];
    list.push({ key: it.key, label, note: it.note });
    byMethod.set(it.methodId, list);
  }
  links.sort((a, b) => (a.added === b.added ? a.key.localeCompare(b.key) : a.added < b.added ? 1 : -1));
  const groups = [...byMethod.entries()]
    .map(([methodId, concepts]) => ({ methodId, concepts }))
    .sort((a, b) => {
      if (a.methodId === b.methodId) return 0;
      if (a.methodId === null) return 1;
      if (b.methodId === null) return -1;
      return a.methodId.localeCompare(b.methodId, 'en', { numeric: true });
    });
  return { links, groups, conceptCount: seen.length - links.length };
}
```

### Step 11: Ideas view tests
**File:** `web/app/sera/ideas/view.test.ts:1` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { method } from '../../../lib/sera/fixture';
import type { LabSeen } from '../../../lib/sera/types';
import { methodsWithStatus, needs, readingList, sourceLabel, sourceLink, urlParts } from './view';

const seen = (key: string, methodId: string | null, note = '', added = '2026-10-04T13:54:48+00:00'): LabSeen =>
  ({ key, methodId, note, added });

describe('methodsWithStatus', () => {
  it('filters by status in numeric id order', () => {
    const ms = [
      method({ id: 'M0010', status: 'idea' }),
      method({ id: 'M0002', status: 'idea' }),
      method({ id: 'M0001', status: 'rejected' }),
      method({ id: 'M0003', status: 'blocked-data' }),
    ];
    expect(methodsWithStatus(ms, 'idea').map(m => m.id)).toEqual(['M0002', 'M0010']);
    expect(methodsWithStatus(ms, 'blocked-data').map(m => m.id)).toEqual(['M0003']);
    expect(methodsWithStatus(ms, 'paper')).toEqual([]);
  });
});

describe('needs', () => {
  it('frames what is missing', () => {
    expect(needs('  quarterly fundamentals ')).toBe('needs: quarterly fundamentals');
    expect(needs('')).toBe('needs: not written down yet');
  });
});

describe('sourceLabel', () => {
  it('uses the glossary label and falls back to the raw kind', () => {
    expect(sourceLabel('paper')).toBe('Research paper');
    expect(sourceLabel('backlog')).toBe('backlog');
  });
});

describe('urlParts / sourceLink', () => {
  it('shortens a URL for display', () => {
    expect(urlParts('https://doi.org/10.1016/j.jfineco.2014.11.010')).toEqual({
      safe: true, host: 'doi.org', display: 'doi.org/10.1016/j.jfineco.2014.11.010',
    });
    expect(urlParts('https://example.com/').display).toBe('example.com');
  });
  it('never links a non-http scheme or garbage', () => {
    expect(urlParts('javascript:alert(1)').safe).toBe(false);
    expect(urlParts('not a url').safe).toBe(false);
    expect(sourceLink('javascript:alert(1)')).toBeNull();
    expect(sourceLink('Barroso & Santa-Clara (2015)')).toBeNull();
    expect(sourceLink(' https://arxiv.org/abs/1 ')).toBe('https://arxiv.org/abs/1');
  });
  it('truncates long URLs', () => {
    const d = urlParts(`https://example.com/${'a'.repeat(100)}`).display;
    expect(d.length).toBe(72);
    expect(d.endsWith('…')).toBe(true);
  });
});

describe('readingList', () => {
  const list = readingList([
    seen('concept:f1-spy-sma200-d', 'H-P7A-F1', 'The classic drawdown cutter'),
    seen('concept:f10-sso-sma200-d', 'H-P7A-F10', '2x S&P only above trend'),
    seen('concept:f2-spyqqq-12m', 'H-P7A-F2'),
    seen('concept:loose', null, 'no method yet'),
    seen('concept:momentum-own-vol-scaling', 'M0001', '', '2026-10-04T13:59:59+00:00'),
    seen('odd-key', 'M0001'),
    seen('url:https://doi.org/10.1016/j.jfineco.2014.11.010', 'M0001', '', '2026-10-04T13:59:59+00:00'),
    seen('url:https://a.example/older', null, 'older', '2026-10-01T00:00:00+00:00'),
  ]);
  it('splits links from concepts', () => {
    expect(list.links.map(l => l.host)).toEqual(['doi.org', 'a.example']);
    expect(list.conceptCount).toBe(6);
  });
  it('groups concepts by method, numeric order, untied last', () => {
    expect(list.groups.map(g => g.methodId)).toEqual(['H-P7A-F1', 'H-P7A-F2', 'H-P7A-F10', 'M0001', null]);
    expect(list.groups[3].concepts.map(c => c.label)).toEqual(['momentum-own-vol-scaling', 'odd-key']);
    expect(list.groups[0].concepts[0]).toEqual({
      key: 'concept:f1-spy-sma200-d', label: 'f1-spy-sma200-d', note: 'The classic drawdown cutter',
    });
  });
});
```

### Step 12: Ideas styles
**File:** `web/app/sera/ideas/ideas.module.css:1` (new)
**Code:**
```css
/* Ideas: tally chips, then backlog cards, the data wishlist, and the reading list. */
.page { display: flex; flex-direction: column; gap: 12px; }
.tally { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 0 2px; }
.tally :global(.chip) { background: var(--sheet); }

.cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.card { border-radius: 28px; padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 12px; }
.cardHead { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.cardTitles { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.cardId { font-size: 13px; letter-spacing: 0.12em; color: var(--ink-2); }
.cardTitle { margin: 0; font-size: 21px; font-weight: 500; letter-spacing: -0.01em; line-height: 1.25; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chips :global(.chip) { background: var(--sheet); font-size: 14px; height: 30px; }
.text { font-size: 15.5px; line-height: 1.5; white-space: pre-line; overflow-wrap: anywhere; }
.risk { font-size: 15px; line-height: 1.45; color: var(--ink-2); white-space: pre-line; }
.label { display: block; font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 2px; }
.cardFoot { display: flex; flex-direction: column; gap: 8px; padding-top: 4px; }
.ref { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.refText { font-size: 14px; color: var(--ink-2); min-width: 0; overflow-wrap: anywhere; }

.wishes { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.wish { display: flex; align-items: flex-start; gap: 16px; padding: 18px 22px; border-radius: 24px; background: var(--stone); }
.wishMain { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.wishHead { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.wishName { font-size: 18px; font-weight: 500; }
.needs { background: var(--butter); color: var(--ink); height: 30px; font-size: 14px; white-space: normal; }

.more { display: flex; align-items: center; justify-content: flex-end; gap: 12px; font-size: 14px; color: var(--ink-2); }

.subhead { margin: 6px 0 0; font-size: 13px; font-weight: 400; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-2); }
.links { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.link { display: flex; align-items: center; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--hair); }
.link:last-child { border-bottom: 0; }
.linkMain { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.linkText { font-size: 16px; overflow-wrap: anywhere; }
.linkNote { font-size: 14px; color: var(--ink-2); }

.groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.group { display: flex; flex-direction: column; gap: 10px; padding: 16px 18px; border-radius: 24px; background: var(--stone); }
.groupHead { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 15px; font-weight: 500; }
.tags { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
.tag { background: var(--sheet); height: 30px; font-size: 13.5px; cursor: default; }
.sr {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}

.empty { font-size: 16px; color: var(--ink-2); }

@media (max-width: 1023.98px) {
  .cards, .groups { grid-template-columns: 1fr; }
}
```

### Step 13: Ideas page
**File:** `web/app/sera/ideas/page.tsx:1` (new)
**Code:**
```tsx
import { ArrowUpRight, Database, ExternalLink, GitBranch } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSera } from '@/lib/sera/gate';
import { lab, methodById } from '@/lib/sera/lab';
import type { LabMethod } from '@/lib/sera/types';
import { methodsWithStatus, needs, readingList, sourceLabel, sourceLink, urlParts, type ReadingLink } from './view';
import s from './ideas.module.css';

export const metadata: Metadata = { title: 'Ideas' };

const methodHref = (id: string) => `/sera/methods/${encodeURIComponent(id)}`;

export default async function IdeasPage() {
  await requireSera('/sera/ideas');
  const backlog = methodsWithStatus(lab.methods, 'idea');
  const blocked = methodsWithStatus(lab.methods, 'blocked-data');
  const reading = readingList(lab.ideasSeen);
  const read = reading.links.length + reading.conceptCount;

  return (
    <>
      <PageHeader
        eyebrow="Ideas"
        title="What comes next"
        lede="What the lab plans to try next, what it cannot try until it has more data, and everything it has already looked at so it never tries the same thing twice."
        asOf={lab.asOf}
      />
      <div className={s.page}>
        <div className={s.tally}>
          <span className="chip num">{backlog.length} waiting</span>
          <span className="chip num">{blocked.length} blocked on data</span>
          <span className="chip num">{reading.links.length} links read</span>
          <span className="chip num">{reading.conceptCount} concepts tried</span>
        </div>

        <div id="backlog">
          <Section
            eyebrow={`Backlog · ${backlog.length}`}
            title="Waiting to be tried"
            caption="Methods written down but not run yet. Each one states its idea and what could go wrong before any result exists."
          >
            {backlog.length === 0 ? (
              <p className={s.empty}>The backlog is empty. The next exploration run will add to it.</p>
            ) : (
              <div className={s.cards}>{backlog.map(m => <IdeaCard key={m.id} method={m} />)}</div>
            )}
          </Section>
        </div>

        <div id="blocked">
          <Section
            eyebrow={`Blocked on data · ${blocked.length}`}
            title="Data wishlist"
            caption="Ideas the lab cannot test with the data it has. Each one says what it needs, so getting that data would unlock it."
          >
            {blocked.length === 0 ? (
              <p className={s.empty}>No idea is waiting on data yet. When one is, it shows here with what it needs.</p>
            ) : (
              <ul className={s.wishes}>{blocked.map(m => <WishRow key={m.id} method={m} />)}</ul>
            )}
            <div className={s.more}>
              <span>More data wishes are in the journal.</span>
              <Link href="/sera/journal?kind=data-wish" className="icon-btn sm"
                aria-label="Open the data wishes in the journal" data-tip="Data wishes in the journal">
                <Database size={18} strokeWidth={1.5} />
              </Link>
            </div>
          </Section>
        </div>

        <div id="reading">
          <Section
            eyebrow={`Reading list · ${read}`}
            title="Everything already looked at"
            caption="Every paper, post and concept the lab has considered, and the method it led to. Hover a tag to read its note."
          >
            <h3 className={s.subhead}>Links · {reading.links.length}</h3>
            {reading.links.length === 0 ? (
              <p className={s.empty}>No link has been read yet.</p>
            ) : (
              <ul className={s.links}>{reading.links.map(l => <LinkRow key={l.key} link={l} />)}</ul>
            )}

            <h3 className={s.subhead}>Concepts · {reading.conceptCount}</h3>
            {reading.groups.length === 0 ? (
              <p className={s.empty}>No concept has been tried yet.</p>
            ) : (
              <div className={s.groups}>
                {reading.groups.map(g => {
                  const m = g.methodId ? methodById(g.methodId) : undefined;
                  return (
                    <div key={g.methodId ?? 'none'} className={s.group}>
                      <div className={s.groupHead}>
                        <span>{g.methodId ? `${g.methodId}${m ? ` · ${m.name}` : ''}` : 'Not tied to a method'}</span>
                        {m && (
                          <Link href={methodHref(m.id)} className="icon-btn sm"
                            aria-label={`Open ${m.id}, ${m.name}`} data-tip={`Open ${m.id}`}>
                            <ArrowUpRight size={18} strokeWidth={1.5} />
                          </Link>
                        )}
                      </div>
                      <ul className={s.tags}>
                        {g.concepts.map(c => (
                          <li key={c.key} className={`chip ${s.tag}`} data-tip={c.note || 'No note'}>
                            {c.label}
                            {c.note && <span className={s.sr}>: {c.note}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            )}
          </Section>
        </div>
      </div>
    </>
  );
}

function IdeaCard({ method: m }: { method: LabMethod }) {
  const parent = m.parentId ? methodById(m.parentId) : undefined;
  const link = sourceLink(m.sourceRef);
  return (
    <article className={`${s.card} bg-butter`}>
      <header className={s.cardHead}>
        <div className={s.cardTitles}>
          <span className={s.cardId}>{m.id}</span>
          <h3 className={s.cardTitle}>{m.name}</h3>
        </div>
        <Link href={methodHref(m.id)} className="icon-btn sm" aria-label={`Open ${m.id}, ${m.name}`} data-tip={`Open ${m.id}`}>
          <ArrowUpRight size={18} strokeWidth={1.5} />
        </Link>
      </header>
      <div className={s.chips}>
        <span className="chip">{m.family}</span>
        <span className="chip">{sourceLabel(m.sourceKind)}</span>
      </div>
      <p className={s.text}>{m.hypothesis}</p>
      {m.expectedFailure && (
        <p className={s.risk}><span className={s.label}>What could go wrong</span>{m.expectedFailure}</p>
      )}
      {(m.sourceRef.trim() || m.parentId) && (
        <footer className={s.cardFoot}>
          {m.sourceRef.trim() && (
            <div className={s.ref}>
              <span className={s.refText}>{link ? urlParts(link).display : m.sourceRef}</span>
              {link && (
                <a href={link} target="_blank" rel="noopener noreferrer" className="icon-btn sm"
                  aria-label="Open the source in a new tab" data-tip="Open the source">
                  <ExternalLink size={17} strokeWidth={1.5} />
                </a>
              )}
            </div>
          )}
          {m.parentId && (
            <div className={s.ref}>
              <span className={s.refText}>Builds on {m.parentId}{parent ? ` · ${parent.name}` : ''}</span>
              {parent && (
                <Link href={methodHref(parent.id)} className="icon-btn sm"
                  aria-label={`Open the parent method ${parent.id}, ${parent.name}`} data-tip={`Parent: ${parent.id}`}>
                  <GitBranch size={17} strokeWidth={1.5} />
                </Link>
              )}
            </div>
          )}
        </footer>
      )}
    </article>
  );
}

function WishRow({ method: m }: { method: LabMethod }) {
  return (
    <li className={s.wish}>
      <div className={s.wishMain}>
        <div className={s.wishHead}>
          <span className={s.cardId}>{m.id}</span>
          <span className={s.wishName}>{m.name}</span>
          <span className={`chip ${s.needs}`}>{needs(m.blockedOn)}</span>
        </div>
        <p className={s.text}>{m.hypothesis}</p>
      </div>
      <Link href={methodHref(m.id)} className="icon-btn sm" aria-label={`Open ${m.id}, ${m.name}`} data-tip={`Open ${m.id}`}>
        <ArrowUpRight size={18} strokeWidth={1.5} />
      </Link>
    </li>
  );
}

function LinkRow({ link: l }: { link: ReadingLink }) {
  const m = l.methodId ? methodById(l.methodId) : undefined;
  return (
    <li className={s.link}>
      <div className={s.linkMain}>
        <span className={s.linkText}>{l.display}</span>
        {l.note && <span className={s.linkNote}>{l.note}</span>}
        {l.methodId && <span className={s.linkNote}>Led to {l.methodId}{m ? ` · ${m.name}` : ''}</span>}
      </div>
      {m && (
        <Link href={methodHref(m.id)} className="icon-btn sm" aria-label={`Open ${m.id}, ${m.name}`} data-tip={`Open ${m.id}`}>
          <ArrowUpRight size={18} strokeWidth={1.5} />
        </Link>
      )}
      {l.safe && (
        <a href={l.url} target="_blank" rel="noopener noreferrer" className="icon-btn sm"
          aria-label={`Open ${l.host} in a new tab`} data-tip={`Open ${l.host}`}>
          <ExternalLink size={17} strokeWidth={1.5} />
        </a>
      )}
    </li>
  );
}
```
**Impact:** new route. URLs and source refs show as plain text, each with an icon-only external link (invariant 4). Only `http(s)` URLs are ever linked.

### Step 14: How-it-works view helpers
**File:** `web/app/sera/how/view.ts:1` (new)
**Change:** All copy and counts for `/sera/how`. Gate thresholds always come from `gate` (invariant 5). The paper bar (3 months, 100 trades) is not part of `snapshot.gate`. It is design §1's bar for real money, kept as two named constants (see Handoffs).
**Code:**
```ts
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
```
**Impact:** none.

### Step 15: How-it-works view tests
**File:** `web/app/sera/how/view.test.ts:1` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { GATE, method, trial } from '../../../lib/sera/fixture';
import type { LabSnapshot } from '../../../lib/sera/types';
import {
  BEARS, dataFacts, honestyRules, hurdles, pctLabel, pipelineLabel, pipelineStages, stageCounts, windowsModel,
  type HowInput,
} from './view';

const DATA: LabSnapshot['data'] = {
  storeStart: '1993-01-29',
  membershipStart: '1996-01-02',
  fxStart: '1999-01-04',
  fingerprints: ['p7a-abc'],
  barRows: 1234567,
  symbolsRequested: 700,
  symbolsServed: 650,
  dividendRows: 45000,
};

const snap = (over: Partial<HowInput> = {}): HowInput => ({
  asOf: '2026-10-04T14:12:24+00:00',
  gate: GATE,
  data: DATA,
  summary: { devTrials: 58, testLooks: 0 },
  methods: [
    method({ id: 'H-P7A-F1', status: 'rejected', historical: true }),
    method({ id: 'M0001', status: 'rejected' }),
    method({ id: 'M0002', status: 'idea' }),
    method({ id: 'M0003', status: 'idea' }),
    method({ id: 'M0004', status: 'blocked-data' }),
    method({ id: 'M0005', status: 'paper', updated: '2026-09-01T08:00:00+00:00' }),
  ],
  trials: [trial({ eligible: true }), trial({ eligible: false }), trial({ window: 'test', eligible: true })],
  ...over,
});

describe('pctLabel', () => {
  it('drops trailing zeros', () => {
    expect(pctLabel(0.15)).toBe('15%');
    expect(pctLabel(0.125)).toBe('12.5%');
  });
});

describe('stageCounts', () => {
  it('counts each stage from statuses and dev trials', () => {
    expect(stageCounts(snap())).toEqual({ ideas: 2, registered: 2, devTrials: 58, eligible: 1, testLooks: 0, paper: 1 });
  });
});

describe('pipelineStages', () => {
  const st = pipelineStages(snap());
  it('has the seven stages in order, with fail branches on the four tests', () => {
    expect(st.map(x => x.key)).toEqual(['idea', 'registered', 'dev', 'hurdles', 'test', 'paper', 'real']);
    expect(st.map(x => x.fails)).toEqual([false, false, true, true, true, true, false]);
    expect(st[6].final).toBe(true);
  });
  it('reads the windows and thresholds from the gate', () => {
    expect(st[2].title).toEqual(['Tested on', '1993–2015']);
    expect(st[4].title).toEqual(['One look at', '2015–today']);
    expect(st[3].detail.join(' | ')).toBe(
      'Beat SPY + dividends | Worst fall ≤ 15% | PF ≥ 1.3 · 100+ trades | No owner inputs | Luck check ≥ 0.95',
    );
    const loose = pipelineStages(snap({ gate: { ...GATE, maxDrawdown: 0.2, dsrMin: 0.9 } }));
    expect(loose[3].detail).toContain('Worst fall ≤ 20%');
    expect(loose[3].detail).toContain('Luck check ≥ 0.9');
  });
  it('shows current counts', () => {
    expect(st.map(x => x.count)).toEqual(['2 waiting', '2 methods', '58 tries', '1 pass', '0 looks used', '1 on paper', 'None yet']);
  });
  it('keeps every line short enough for its box', () => {
    for (const x of st) {
      const max = x.weight && x.weight > 1 ? 26 : 18;
      for (const l of x.title) expect(l.length).toBeLessThanOrEqual(14);
      for (const l of x.detail) expect(l.length).toBeLessThanOrEqual(max);
    }
  });
  it('summarises the path for screen readers', () => {
    expect(pipelineLabel(st)).toContain('Idea (2 waiting), then Written down before testing (2 methods)');
  });
});

describe('windowsModel', () => {
  it('uses the as-of date as today and notes an untouched test window', () => {
    const w = windowsModel(snap());
    expect(w.today).toBe('2026-10-04');
    expect(w.start).toBe('1993-01-29');
    expect(w.testNote).toBe('untouched, no look used yet');
    expect(w.paperSince).toBe('2026-09-01');
    expect(w.bears).toBe(BEARS);
  });
  it('counts looks used and handles nothing on paper', () => {
    const w = windowsModel(snap({ summary: { devTrials: 58, testLooks: 2 }, methods: [] }));
    expect(w.testNote).toBe('2 looks used');
    expect(w.paperSince).toBeNull();
    expect(w.label).toContain('no lab method on paper yet');
  });
  it('survives an empty lab, whose asOf is empty', () => {
    expect(windowsModel(snap({ asOf: '' })).today).toBe('2015-10-19');
  });
});

describe('hurdles', () => {
  it('lists the six conditions in gate order with thresholds from the gate', () => {
    const h = hurdles(GATE, 58);
    expect(h.map(x => x.key)).toEqual(['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr']);
    expect(h.map(x => x.target)).toEqual([
      'More than SPY total return', 'Max drawdown ≤ 15%', 'Profit factor ≥ 1.3', 'At least 100 trades',
      'Nothing left for the owner to decide', 'Luck check ≥ 0.95',
    ]);
    expect(h.map(x => x.term)).toEqual(['spyTr', 'maxDrawdown', 'profitFactor', 'trades', 'ownerInputs', 'dsr']);
    expect(h[5].plain).toContain('N = 58');
  });
});

describe('honestyRules', () => {
  it('quotes the live tries and looks', () => {
    const r = honestyRules(snap({ summary: { devTrials: 1, testLooks: 3 } }));
    expect(r.map(x => x.key)).toEqual(['counted', 'first', 'reroll', 'append', 'look', 'bar']);
    expect(r[0].body.startsWith('1 try so far')).toBe(true);
    expect(r[4].body).toContain('Looks used so far: 3');
  });
});

describe('dataFacts', () => {
  it('formats what the lab has and lists what it lacks', () => {
    const f = dataFacts(DATA, GATE);
    expect(f.has.map(x => x.key)).toEqual(['prices', 'dividends', 'membership', 'fx', 'versions']);
    expect(f.has[0].title).toBe('Daily prices since Jan 1993');
    expect(f.has[0].body).toContain('1,234,567 daily price rows for 650 of the 700');
    expect(f.has[4].title).toBe('One frozen copy of the data');
    expect(f.lacks.map(x => x.key)).toEqual(['fundamentals', 'delisted', 'intraday', 'options', 'sentiment']);
  });
});
```

### Step 16: How-it-works styles
**File:** `web/app/sera/how/how.module.css:1` (new)
**Code:**
```css
/* How it works: two full-width diagram sheets, then hurdle cards, rules, data columns, glossary. */
.page { display: flex; flex-direction: column; gap: 12px; }
.diagram { width: 100%; padding: 6px 0 2px; }

.grid3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.card { background: var(--stone); border-radius: 28px; padding: 22px 24px; display: flex; flex-direction: column; gap: 10px; }
.cardHead { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.idx { font-size: 13px; letter-spacing: 0.12em; color: var(--ink-3); }
.cardTitle { margin: 0; font-size: 19px; font-weight: 500; letter-spacing: -0.01em; line-height: 1.25; }
.target { align-self: flex-start; background: var(--sheet); font-size: 14px; height: 30px; }
.plain { font-size: 15px; line-height: 1.45; color: var(--ink-2); }

.rules { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.rule { display: flex; gap: 14px; align-items: flex-start; background: var(--stone); border-radius: 28px; padding: 20px 22px; }
.ruleIcon {
  flex: none; width: 44px; height: 44px; border-radius: 999px; background: var(--ink); color: var(--sheet);
  display: flex; align-items: center; justify-content: center;
}
.ruleText { display: flex; flex-direction: column; gap: 4px; }
.ruleTitle { margin: 0; font-size: 17px; font-weight: 500; }

.cols { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.col { border-radius: 28px; padding: 22px 24px; display: flex; flex-direction: column; gap: 14px; }
.colHead { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.colTitle { margin: 0; font-size: 20px; font-weight: 500; }
.links { display: flex; gap: 8px; }
.facts { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }
.fact { display: flex; flex-direction: column; gap: 3px; }
.factTitle { font-size: 16px; font-weight: 500; }
.factBody { font-size: 15px; line-height: 1.45; color: var(--ink-2); }

.glossary { margin: 0; display: grid; grid-template-columns: 240px minmax(0, 1fr); column-gap: 28px; }
.glossary dt { padding: 12px 0; font-size: 16px; font-weight: 500; border-bottom: 1px solid var(--hair); }
.glossary dd { margin: 0; padding: 12px 0; font-size: 15.5px; line-height: 1.45; color: var(--ink-2); border-bottom: 1px solid var(--hair); }

@media (max-width: 1023.98px) {
  .grid3, .rules, .cols { grid-template-columns: 1fr; }
  .glossary { grid-template-columns: 1fr; }
  .glossary dt { border-bottom: 0; padding-bottom: 0; }
  /* The diagrams are drawn for desktop; below 1024px they scroll sideways instead of shrinking text. */
  .diagram { overflow-x: auto; }
  .diagram > svg { min-width: 960px; }
}
```

### Step 17: How-it-works page
**File:** `web/app/sera/how/page.tsx:1` (new)
**Change:** A server component with six `Section`s, each with an eyebrow, a title and a one-sentence plain caption:
1. the pipeline
2. the windows
3. the hurdles
4. the honesty rules
5. the data
6. the glossary

Jargon is wrapped in the local `T` (Phase 3's `Term`, fed from `GLOSSARY`) on first use: dev window, test window and paper trading in captions 1–2, each hurdle's term on its title, and N (tries) in the rules caption.
**Code:**
```tsx
import { Anchor, ArrowUpRight, Ban, Database, Eye, Hash, Lock, PenLine, type LucideIcon } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { Pipeline } from '@/components/sera/diagrams/Pipeline';
import { Windows } from '@/components/sera/diagrams/Windows';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Term } from '@/components/sera/Term';
import { requireSera } from '@/lib/sera/gate';
import { GLOSSARY, GLOSSARY_ORDER, type GlossaryKey } from '@/lib/sera/glossary';
import { lab } from '@/lib/sera/lab';
import { dataFacts, honestyRules, hurdles, pipelineLabel, pipelineStages, windowsModel, type Rule } from './view';
import s from './how.module.css';

export const metadata: Metadata = { title: 'How it works' };

const RULE_ICON: Record<Rule['key'], LucideIcon> = {
  counted: Hash,
  first: PenLine,
  reroll: Ban,
  append: Lock,
  look: Eye,
  bar: Anchor,
};

/** A glossary term: the definition comes from lib/sera/glossary (Term itself takes plain strings). */
function T({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  return <Term term={GLOSSARY[k].term} definition={GLOSSARY[k].plain}>{children}</Term>;
}

export default async function HowPage() {
  await requireSera('/sera/how');
  const stages = pipelineStages(lab);
  const win = windowsModel(lab);
  const hs = hurdles(lab.gate, lab.summary.devTrials);
  const rules = honestyRules(lab);
  const facts = dataFacts(lab.data, lab.gate);
  const wishes = lab.insights.filter(i => i.kind === 'data-wish').length;
  const blocked = lab.methods.filter(m => m.status === 'blocked-data').length;

  return (
    <>
      <PageHeader
        eyebrow="How it works"
        title="How the lab decides"
        lede="How an idea becomes a method, how it is tested, and the rules that stop the lab from fooling itself."
        asOf={lab.asOf}
      />
      <div className={s.page}>
        <Section
          eyebrow="The path"
          title="From idea to real money"
          caption={
            <>
              Each box is a stage, and its pill shows how many methods or tries are there now. Red dashed arrows are
              fails: the lesson goes in the journal and the lab moves to the next idea. Testing starts on
              the <T k="devWindow">dev window</T> and ends with <T k="paperTrading">paper trading</T>.
            </>
          }
        >
          <div className={s.diagram}>
            <Pipeline stages={stages} failLabel="fails → written in the journal, then the next idea"
              label={pipelineLabel(stages)} />
          </div>
        </Section>

        <Section
          eyebrow="The calendar"
          title="Which years are used for what"
          caption={
            <>
              Every idea is built and tested on the practice years. The <T k="testWindow">exam years</T> stay
              sealed for one final look. Red shading marks the two big crashes the practice years include.
            </>
          }
        >
          <div className={s.diagram}>
            <Windows {...win} />
          </div>
        </Section>

        <Section
          eyebrow="The hurdles"
          title="Six things every method must clear"
          caption="A method passes the practice stage only if one of its variants clears all six at once. The numbers come from the lab’s own settings."
        >
          <div className={s.grid3}>
            {hs.map((h, i) => (
              <article key={h.key} className={s.card}>
                <div className={s.cardHead}>
                  <span className={s.idx}>{String(i + 1).padStart(2, '0')}</span>
                </div>
                <h3 className={s.cardTitle}><T k={h.term}>{h.title}</T></h3>
                <span className={`chip num ${s.target}`}>{h.target}</span>
                <p className={s.plain}>{h.plain}</p>
              </article>
            ))}
          </div>
        </Section>

        <Section
          eyebrow="The honesty rules"
          title="Why a pass here means something"
          caption={
            <>
              Test enough ideas on the same past and one will look brilliant by luck. These rules, and counting
              every try (<T k="tries">N</T>), stop the lab from fooling itself.
            </>
          }
        >
          <ul className={s.rules}>
            {rules.map(r => {
              const Icon = RULE_ICON[r.key];
              return (
                <li key={r.key} className={s.rule}>
                  <span className={s.ruleIcon} aria-hidden="true"><Icon size={20} strokeWidth={1.6} /></span>
                  <div className={s.ruleText}>
                    <h3 className={s.ruleTitle}>{r.title}</h3>
                    <p className={s.plain}>{r.body}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </Section>

        <Section
          eyebrow="The data"
          title="What the lab can see, and what it cannot"
          caption="Every method is limited to the data on the left. Ideas that need something on the right wait as data wishes."
        >
          <div className={s.cols}>
            <div className={`${s.col} bg-sky`}>
              <div className={s.colHead}><h3 className={s.colTitle}>What it has</h3></div>
              <ul className={s.facts}>
                {facts.has.map(f => (
                  <li key={f.key} className={s.fact}>
                    <span className={s.factTitle}>{f.title}</span>
                    <span className={s.factBody}>{f.body}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className={`${s.col} bg-butter`}>
              <div className={s.colHead}>
                <h3 className={s.colTitle}>What it lacks</h3>
                <div className={s.links}>
                  <Link href="/sera/journal?kind=data-wish" className="icon-btn sm"
                    aria-label={`Open the ${wishes} data wishes in the journal`} data-tip={`Data wishes · ${wishes}`}>
                    <Database size={18} strokeWidth={1.5} />
                  </Link>
                  <Link href="/sera/ideas#blocked" className="icon-btn sm"
                    aria-label={`Open the ${blocked} ideas blocked on data`} data-tip={`Blocked on data · ${blocked}`}>
                    <ArrowUpRight size={18} strokeWidth={1.5} />
                  </Link>
                </div>
              </div>
              <ul className={s.facts}>
                {facts.lacks.map(f => (
                  <li key={f.key} className={s.fact}>
                    <span className={s.factTitle}>{f.title}</span>
                    <span className={s.factBody}>{f.body}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Section>

        <Section
          eyebrow="The words"
          title="Glossary"
          caption="The plain meaning of every term used across Sera. Hover an underlined word anywhere for the same text."
        >
          <dl className={s.glossary}>
            {GLOSSARY_ORDER.map(k => (
              <div key={k} style={{ display: 'contents' }}>
                <dt>{GLOSSARY[k].term}</dt>
                <dd>{GLOSSARY[k].plain}</dd>
              </div>
            ))}
          </dl>
        </Section>
      </div>
    </>
  );
}
```
**Impact:** new route. `pipelineStages(lab)`, `windowsModel(lab)` and `honestyRules(lab)` accept the full `LabSnapshot` structurally (`HowInput` is a narrowing of it). If Phase 2 types `gate.devStart` etc. as literal strings, the `HowInput.gate: Gate` alias keeps them identical.

## Verification

**Setup:** Step 0 (`npm ci` in the worktree's `web/`).
**Build:** `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npx vitest run` (all existing tests plus the 4 new suites: `app/sera/{journal,ideas,how}/view.test.ts`, `components/sera/diagrams/geometry.test.ts`)
**Route compile:** `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npx next build`. Skip it if it fails only on missing auth env vars, which is unrelated to this phase. If it runs, the output must list `/sera/journal`, `/sera/ideas` and `/sera/how`.
**Manual check:** with `npm run dev`, signed in as mahfuzh74@gmail.com, at 1440 px width, check:
- the Journal seg filter switches groups, and every button shows its tooltip and badge.
- `?kind=data-wish` shows only that group.
- Ideas shows M0002 and M0003 in the backlog, M0002's parent link goes to M0001, the doi.org link opens in a new tab, and concept tags show their notes on hover.
- How: the pipeline has 7 boxes with no text overflowing a box, and the fail lane loops back to Idea.
- Windows: the two bears are shaded, the split sits at Oct 2015, and the test band reads "untouched".
- Dark mode (`prefers-color-scheme: dark`) keeps every diagram legible.

**Exit criteria:**
- tsc is clean, and vitest is green.
- The three routes compile.
- No file outside the 17 listed is touched.
- No text button exists on the three pages. Every `Link` and `a` that is a control is an icon-only `.icon-btn` with `aria-label` and `data-tip`.

## Handoffs

- **Phase 1 (snapshot contract), optional:** the paper bar (3 months, 100 trades) is design §1's, and it is hard-coded as `PAPER_MONTHS` / `PAPER_TRADES` in `how/view.ts`. If the reconciler wants invariant 5 to cover it, Phase 1 adds `gate.paperMonths` and `gate.paperTrades` to the snapshot, and this phase reads them. Serves R5.
- **Phase 1, optional:** the data-store end date for prices (`data.storeEnd`) is not in the contract. The "has" copy therefore avoids naming an end date and says that the years after `gate.devEnd` stay locked.
- **Phase 3:** if `Section` gains an `id` prop, the `<div id=…>` wrappers in `ideas/page.tsx` can fold into it. If Phase 3 ships a shared `.md` (markdown body) style, `journal.module.css`'s `.body :global(...)` rules can be replaced by it. Phase 5 likely needs the same rules for the analysis text. Cosmetic, no requirement.
- **Phase 2:** `KIND_COPY` (the caption, empty sentence and tone per insight kind) lives in `journal/view.ts`. If Phase 2 prefers all insight-kind copy in `glossary.ts`, it can move there. The headings already come from `INSIGHT_KIND_LABEL`.
- **Phase 7 (docs, R6):** the `web/package_readme.md` Sera section should mention:
  - `/sera/journal?kind=…`
  - `/sera/ideas#backlog|#blocked|#reading`
  - `/sera/how`
  - `web/components/sera/diagrams/` (Pipeline, Windows)

## Rollback

Every file in this phase is new. To undo it, delete `web/app/sera/journal/`, `web/app/sera/ideas/`, `web/app/sera/how/` and `web/components/sera/diagrams/`, or revert this phase's commit. No other phase imports anything from these paths. The Phase 3 rail tabs that point to the three routes would then 404 into `web/app/sera/not-found.tsx`, which is harmless.
