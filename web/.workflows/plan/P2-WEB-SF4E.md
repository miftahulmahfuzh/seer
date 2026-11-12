> Adopted from `.workflows/plan/LEADERBOARD_LEGEND_TOGGLES_PLAN.md` phase 1. Source: `.workflows/plan/leaderboard-legend-toggles/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: ChartPanel: left legend row, toggle highlight, pick seeds it

**Plan set:** `LEADERBOARD_LEGEND_TOGGLES_PLAN.md`
**Analysis:** `.workflows/analyze/20261112-094511-L7G2_code_analyzer.md`
**Satisfies:** R1, R2, R3 — the leaderboard chart's legend moves to a left-aligned row of its own and becomes a set of toggles that highlight lines, which a card pick also feeds
**Criteria:** R1.1, R1.2, R2.1, R2.2, R2.3, R2.4, R3.1, R3.2, R3.3
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `web/app/(app)/leaderboard`

---

## Goal

Today the legend is a static `<span>` list a server component (`Legend`, `page.tsx:361`) renders
twice: on desktop pushed to the right of the headline figures, on mobile under the axis. After
this phase the chart sheet is a client component, `ChartPanel`, that owns a set of highlighted
strategy ids. Its legend is a row of `<button aria-pressed>` toggles on its own row under the
headline figures, the first swatch on the champion label's left edge. A pressed toggle draws its
line 1px thicker and on top, and every other line fades to 20%. A card pick (`?s=X`, a soft
navigation that keeps `ChartPanel` mounted) adds X to the set. Nothing is stored in the URL or
in browser storage.

## Interface Contract

**Deletes:** `Legend` (server function, `web/app/(app)/leaderboard/page.tsx:361-382`); CSS rules `.headline > .legend`, `.headline > .legend .legendItem`, `.headline > .legend .swatch, .headline > .legend .swatchDash`, `.headline > .legend .legendLabel` and the desktop `.headline { flex-wrap: wrap; row-gap: 14px; }` (`leaderboard.module.css:236-246`)
**Renames:** none
**Creates:** `ChartPanel` (client component), `type ChartLine`, `type LegendEntry` (`web/app/(app)/leaderboard/ChartPanel.tsx`); `legendEntry()` (module function, `page.tsx`, where `Legend` was); CSS classes `.legendDesk`, custom properties `--pill-x` (on `.legend`) and `--pill` (inline on each legend button); DOM attributes `data-id` on legend buttons, `data-line` / `data-on` on chart paths, `data-focus` on the svg and on each legend group; step file `.claude/skills/verify-seer/features/steps/leaderboard-legend.mjs`; test file `ChartPanel.test.tsx`
**Signature changes:** none (the `chartSheet` constant in `Leaderboard` changes body, not type)
**Requires (from earlier phases):** none
**Leaves alone (owned by others):** `view.ts` (all logic, `looks()`, `pickResearch`, `BENCHMARK_DASH` values), `buildChart` maths (`page.tsx:384-418`), `card()` and its `<Link href scroll={false}>`, `checklistSheet`, `monthsSheet`, `StrategySwitch`, `RetiredShelf`, `components/sera/charts/*`, `engine/`. The existing step `leaderboard-spread.mjs` is not edited: its legend check (`[class*="legendItem"]` visible, six, one top) must still pass as-is.

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/(app)/leaderboard/ChartPanel.tsx` | create | client component: highlight set, svg paths, desktop and mobile legends of toggle buttons |
| `web/app/(app)/leaderboard/ChartPanel.test.tsx` | create | `renderToStaticMarkup` tests: nothing-pressed = today's strokes; pick seeds the set; toggles are named buttons |
| `web/app/(app)/leaderboard/page.tsx` | modify | L16-21 imports; L110-155 `chartSheet` uses `ChartPanel`; L355-382 `Legend` replaced by `legendEntry()` |
| `web/app/(app)/leaderboard/leaderboard.module.css` | modify | L19-26 legend/toggle/swatch/highlight rules; L236-246 desktop legend block |
| `.claude/skills/verify-seer/features/leaderboard.md` | modify | L5 new sub-feature bullet; L37 new drive commands; L60 gotcha lines |
| `.claude/skills/verify-seer/features/steps/leaderboard-legend.mjs` | create | Playwright step proving R1.1–R3.3 |

## Implementation Steps

Before anything: the worktree has no `web/node_modules`. Hard-link it (a symlink passes tsc/vitest
and then breaks `next build` and the verify snapshot):

```sh
cd /home/miftah/.worktrees/seer/leaderboard-legend-toggles
[ -d web/node_modules ] || cp -al /home/miftah/seer/web/node_modules web/node_modules
```

Next.js 16 note (read from `web/node_modules/next/dist/docs/01-app/02-guides/server-and-client-boundary.md`
and `next/dist/client/components/layout-router.js:549`): props into a client component must be
serializable, and rendered React elements are (that is how `head` and `axis` cross). Importing a
non-type value from a `'use client'` module into a server component gives a client reference, not
the value, so `W`/`H` stay in `page.tsx` and go in as props. The layout router keys a page's state
by `__PAGE__` *without* its search params, so a `<Link href="/leaderboard?s=X">` soft navigation
keeps `ChartPanel` mounted with its state, and only `pickId` changes. `cacheComponents` is not
enabled in `web/next.config.ts`, so no `<Activity>` behaviour applies.

### Step 1: Create the client component
**File:** `web/app/(app)/leaderboard/ChartPanel.tsx` (new)
**Change:** The chart sheet as a client component. It imports nothing from `view.ts` (that module
pulls `lib/metrics`, `lib/strategy`, `lib/monthly` into the client bundle); the page hands it
ready-made legend entries.
**Code:**
```tsx
'use client';

import { useState, type CSSProperties, type ReactNode } from 'react';
import s from './leaderboard.module.css';

/** One equity curve as `buildChart` (page.tsx) draws it: an svg path in the chart's own units. */
export type ChartLine = { id: string; d: string; color: string; width: number; dash: string | null };

/**
 * One legend toggle. The page builds it (`legendEntry`) from the strategy and its look, so this
 * module needs nothing from `view.ts`.
 */
export type LegendEntry = {
  id: string;
  /** The short code the item shows. */
  code: string;
  /** The full name (a retired one says when it stopped): the tooltip and the accessible name. */
  tip: string;
  retired: boolean;
  /** The line's colour, for the swatch. */
  line: string;
  /** The swatch's stroke: solid, SPY's dotted benchmark, or a lap or twin dash. */
  stroke: 'solid' | 'dotted' | 'dashed';
  /** The pill's background while the item is pressed: the strategy's sheet tint. */
  pill: string;
};

/**
 * The leaderboard's chart sheet (owner, 2026-11-12). It is a client component because its legend
 * is a row of toggles: pressing one highlights that strategy's line, so the owner can press two
 * and compare them. Highlighted lines keep their own colour, are 1px thicker and are drawn above
 * the rest; every other line fades to 20% (the stylesheet, from `data-focus` / `data-on`). With
 * nothing pressed the chart is exactly what it was before the legend could be pressed. Any number
 * can be pressed, SPY included.
 *
 * The picked card is pressed too. `pickId` comes from the URL (`?s=`), and a card is a `<Link>`
 * soft navigation, which keeps this component mounted with its state: a new pick is ADDED to what
 * is already pressed (the owner's answer, "Add."), never replaces it, and pressing the picked
 * strategy's item again un-highlights its line while the card stays picked. The set lives in this
 * component's memory only ("memory only for now"): a reload starts again from the pick alone.
 *
 * The figures above the chart and the axis labels under it are rendered on the server and handed
 * in as `head` and `axis`; only the lines and the two legends (desktop, under the headline; phone,
 * under the axis) read the state, and they share it.
 */
export function ChartPanel({ pickId, entries, lines, grid, zero, w, h, head, axis }: {
  /** The picked strategy's id, or null when there is no research strategy to pick. */
  pickId: string | null;
  /** One per strategy on the chart, in board order. */
  entries: LegendEntry[];
  /** Champion last, as `buildChart` orders them. */
  lines: ChartLine[];
  grid: number[];
  zero: number;
  /** The svg's viewBox width and height. */
  w: number;
  h: number;
  head: ReactNode;
  axis: ReactNode;
}) {
  const [active, setActive] = useState<ReadonlySet<string>>(() => new Set(pickId === null ? [] : [pickId]));
  // A new pick arrives as a prop on a soft navigation. React's "adjust state when a prop changes"
  // pattern: compare with the pick last seen during render and add the new one, no Effect.
  const [seenPick, setSeenPick] = useState(pickId);
  if (pickId !== seenPick) {
    setSeenPick(pickId);
    if (pickId !== null && !active.has(pickId)) setActive(new Set(active).add(pickId));
  }

  // Only ids on the chart count: a retired pick left in the set after the owner picks a live card
  // has no line and no legend item, and must not fade everything else.
  const lit: ReadonlySet<string> = new Set(entries.filter(e => active.has(e.id)).map(e => e.id));
  const focus = lit.size > 0 ? 'true' : undefined;
  // Highlighted lines last, so they draw on top; each group keeps `buildChart`'s order.
  const drawn = focus ? [...lines.filter(l => !lit.has(l.id)), ...lines.filter(l => lit.has(l.id))] : lines;
  const toggle = (id: string) => setActive(prev => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  return (
    <section className={`sheet bg-sheet ${s.chartSheet}`}>
      {head}
      <div className={`${s.pad} desk-only`}>
        <Legend entries={entries} lit={lit} focus={focus} onToggle={toggle} className={`${s.legend} ${s.legendDesk}`} />
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={s.chart} role="img"
        aria-label="Equity curves of each strategy against SPY" data-focus={focus}>
        {grid.map((y, i) => <line key={i} x1="0" x2={w} y1={y} y2={y} vectorEffect="non-scaling-stroke" stroke="var(--hair)" />)}
        <line x1="0" x2={w} y1={zero} y2={zero} vectorEffect="non-scaling-stroke" stroke="var(--outline)" strokeDasharray="3 3" />
        {drawn.map(l => {
          const on = lit.has(l.id);
          return (
            <path key={l.id} data-line={l.id} data-on={on ? 'true' : undefined} d={l.d}
              vectorEffect="non-scaling-stroke" fill="none" stroke={l.color} strokeWidth={on ? l.width + 1 : l.width}
              strokeDasharray={l.dash ?? undefined} strokeLinecap="round" strokeLinejoin="round" />
          );
        })}
      </svg>
      {axis}
      <div className={`${s.pad} mobile-only`}>
        <Legend entries={entries} lit={lit} focus={focus} onToggle={toggle} className={`${s.legend} ${s.legendRow}`} />
      </div>
    </section>
  );
}

/**
 * One toggle per strategy: its swatch and code, its full name as the tooltip and accessible name.
 * The toggles carry text, an exception to the icon-only rule the owner accepted: the code is how
 * the lines are told apart. On desktop it is one row (`.legendDesk`); on the phone it wraps.
 */
function Legend({ entries, lit, focus, onToggle, className }: {
  entries: LegendEntry[];
  lit: ReadonlySet<string>;
  focus: string | undefined;
  onToggle: (id: string) => void;
  className: string;
}) {
  return (
    <div role="group" aria-label="Highlight lines" className={className} data-focus={focus}>
      {entries.map(e => (
        <button key={e.id} type="button" data-id={e.id} aria-pressed={lit.has(e.id)}
          data-tip={e.tip} aria-label={e.tip}
          className={e.retired ? `${s.legendItem} ${s.legendRetired}` : s.legendItem}
          style={{ '--pill': e.pill } as CSSProperties} onClick={() => onToggle(e.id)}>
          {e.stroke === 'solid'
            ? <span className={s.swatch} style={{ background: e.line }} />
            : <span className={s.swatchDash} style={{ borderTopColor: e.line, borderTopStyle: e.stroke }} />}
          <span className={s.legendLabel}>{e.code}</span>
        </button>
      ))}
    </div>
  );
}
```
**Impact:** new module, nothing imports it until Step 3.

### Step 2: Tests for the component
**File:** `web/app/(app)/leaderboard/ChartPanel.test.tsx` (new)
**Change:** static-markup tests in the `RetiredShelf.test.tsx` style. They assert what the
browser receives (attributes on paths and buttons, order), not internals. CSS module class names
are not asserted (vitest does not process CSS modules).
**Code:**
```tsx
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ChartPanel, type ChartLine, type LegendEntry } from './ChartPanel';

// As buildChart hands them over: board order with the champion (SPY here) last.
const LINES: ChartLine[] = [
  { id: 'A', d: 'M0 100 L340 60', color: 'var(--lav-line)', width: 2, dash: null },
  { id: 'C', d: 'M0 100 L340 120', color: 'var(--rose-line)', width: 2, dash: '6 3' },
  { id: 'SPY', d: 'M0 100 L340 80', color: 'var(--ink-3)', width: 1.75, dash: '1 4' },
];

const ENTRIES: LegendEntry[] = [
  { id: 'SPY', code: 'SPY', tip: 'SPY', retired: false, line: 'var(--ink-3)', stroke: 'dotted', pill: 'var(--chip-plain)' },
  { id: 'A', code: 'A', tip: 'A · Quant', retired: false, line: 'var(--lav-line)', stroke: 'solid', pill: 'var(--lav)' },
  { id: 'C', code: 'C', tip: 'C · Dip buyer · retired oct 30', retired: true, line: 'var(--rose-line)', stroke: 'dashed', pill: 'var(--rose)' },
];

const render = (pickId: string | null) => renderToStaticMarkup(
  <ChartPanel pickId={pickId} entries={ENTRIES} lines={LINES} grid={[14, 87]} zero={120} w={340} h={170}
    head={<p>HEAD</p>} axis={<p>AXIS</p>} />,
);

const paths = (html: string) => (html.match(/<path [^>]*>/g) ?? []).map(tag => ({
  tag,
  id: /data-line="([^"]+)"/.exec(tag)?.[1],
  width: /stroke-width="([^"]+)"/.exec(tag)?.[1],
}));
const buttons = (html: string): string[] => html.match(/<button [^>]*>/g) ?? [];
const pressed = (html: string) => buttons(html)
  .filter(t => t.includes('aria-pressed="true"'))
  .map(t => /data-id="([^"]+)"/.exec(t)?.[1]);

describe('ChartPanel', () => {
  it('with nothing pressed, draws every line exactly as given: own colour, width and dash, in order, unfaded', () => {
    const html = render(null);
    const ps = paths(html);
    expect(ps.map(p => p.id)).toEqual(['A', 'C', 'SPY']);
    LINES.forEach((l, i) => {
      expect(ps[i].tag).toContain(`stroke="${l.color}"`);
      expect(ps[i].width).toBe(String(l.width));
      if (l.dash) expect(ps[i].tag).toContain(`stroke-dasharray="${l.dash}"`);
      else expect(ps[i].tag).not.toContain('stroke-dasharray');
      expect(ps[i].tag).not.toContain('data-on');
      expect(ps[i].tag).not.toContain('opacity');
    });
    expect(html).not.toContain('data-focus');
    expect(pressed(html)).toEqual([]);
  });

  it('starts with only the pick pressed, in both legends: its line 1px thicker and drawn last', () => {
    const html = render('A');
    expect(pressed(html)).toEqual(['A', 'A']);
    const ps = paths(html);
    expect(ps.map(p => p.id)).toEqual(['C', 'SPY', 'A']);
    expect(ps[2].width).toBe('3');
    expect(ps[2].tag).toContain('data-on="true"');
    expect(ps[2].tag).toContain('stroke="var(--lav-line)"');
    expect(ps[0].width).toBe('2');
    expect(ps[1].width).toBe('1.75');
    expect(html).toMatch(/<svg [^>]*data-focus="true"/);
  });

  it('lets SPY be pressed like any strategy', () => {
    const ps = paths(render('SPY'));
    expect(ps.map(p => p.id)).toEqual(['A', 'C', 'SPY']);
    expect(ps[2].width).toBe('2.75');
    expect(ps[2].tag).toContain('stroke-dasharray="1 4"');
  });

  it('lights nothing for a pick that is not on the chart', () => {
    const html = render('GONE');
    expect(html).not.toContain('data-focus');
    expect(pressed(html)).toEqual([]);
  });

  it('makes every legend item a named toggle with its full name as the tooltip, in both legends', () => {
    const html = render(null);
    const bs = buttons(html);
    expect(bs).toHaveLength(ENTRIES.length * 2);
    for (const b of bs) {
      expect(b).toContain('type="button"');
      expect(b).toContain('aria-pressed="false"');
      const tip = /data-tip="([^"]+)"/.exec(b)?.[1];
      expect(tip).toBeTruthy();
      expect(b).toContain(`aria-label="${tip}"`);
    }
    expect(html).toContain('data-tip="C · Dip buyer · retired oct 30"');
    // SPY's swatch is the dotted benchmark stroke, and its pressed pill takes the page ground.
    expect(html).toContain('border-top-style:dotted');
    expect(html).toContain('--pill:var(--chip-plain)');
    expect(html).toContain('border-top-style:dashed');
  });

  it('puts the desktop legend under the figures and the phone legend under the axis', () => {
    const html = render(null);
    const at = (needle: string) => html.indexOf(needle);
    const firstButton = at('<button ');
    const lastButton = html.lastIndexOf('<button ');
    expect(at('HEAD')).toBeLessThan(firstButton);
    expect(firstButton).toBeLessThan(at('<svg '));
    expect(at('<svg ')).toBeLessThan(at('AXIS'));
    expect(at('AXIS')).toBeLessThan(lastButton);
  });
});
```
**Impact:** `npm test` gains six tests. Check: `cd web && npx vitest run 'app/(app)/leaderboard/ChartPanel.test.tsx'` passes.

### Step 3: Wire the page and drop the server `Legend`
**File:** `web/app/(app)/leaderboard/page.tsx`

**3a — imports, L14-21.** Add the `ChartPanel` import after `PickName` (keep `BENCHMARK_DASH`
and `retiredLabel`: `legendEntry` uses them).
Replace:
```tsx
import { PickName } from './PickName';
import { RetiredShelf } from './RetiredShelf';
```
with:
```tsx
import { ChartPanel, type LegendEntry } from './ChartPanel';
import { PickName } from './PickName';
import { RetiredShelf } from './RetiredShelf';
```

**3b — `chartSheet`, L110-155.** Replace the whole `const chartSheet = ( ... );` block with:
```tsx
  // The chart sheet is a client component (`ChartPanel`): its legend toggles which lines are
  // highlighted, and the pick seeds that. The figures above the chart and the axis under it are
  // rendered here and handed in. The legend is no longer in the headline: it is a row of its own
  // under the window line, left-aligned on the champion label (owner, 2026-11-12).
  const chartSheet = (
    <ChartPanel pickId={pick?.id ?? null} lines={chart.lines} grid={chart.grid} zero={chart.zero} w={W} h={H}
      entries={shown.map(r => legendEntry(r.strategy, lookOf(r.strategy.id)))}
      head={
        <>
          <div className={`${s.between} ${s.pad} mobile-only`}>
            <span className="eyebrow">Forward test</span>
            <span className="pill-outline">{period}</span>
          </div>
          <div className={`${s.headline} ${s.pad}`}>
            <div className={s.stats}>
              <div className={s.stat}>
                <span className={`num ${s.big} ${tone(champRet)}`}>{ret(champRet)}</span>
                <span className={s.statLabel}>
                  <Crown size={14} />
                  <span>{champ?.strategy.name ?? 'No champion'}<span className="desk-only">, champion</span></span>
                </span>
              </div>
              <div className={s.stat}>
                <span className={`num ${s.mid}`}>{second.value}</span>
                <span className={s.statLabel}>
                  <span className="mobile-only">{second.mobile}</span>
                  <span className="desk-only">{second.desk}</span>
                </span>
              </div>
              <div className={`${s.stat} mobile-only`}>
                <span className={`num ${s.mid}`}>{champ?.curve.length ?? 0}</span>
                <span className={s.statLabel}>Sessions</span>
              </div>
            </div>
          </div>
          <div className={`${s.window} ${s.pad}`}>
            <span className={s.windowLabel}>{wline.label}</span>
            <span className={s.windowDetail}>{wline.detail}</span>
          </div>
        </>
      }
      axis={<div className={`${s.axis} ${s.pad}`}>{chart.labels.map((l, i) => <span key={i}>{l}</span>)}</div>} />
  );
```
Decision recorded: the desktop legend sits after the window line, directly above the chart, not
between the figures and the window line. It is still "on its own row below the headline figures"
(R1.1), the window line stays attached to the "best over the common window" figure it qualifies,
and the legend is next to the lines it keys.

**3c — `Legend`, L355-382.** Delete the doc comment and the `Legend` function (L355-382) and put
this in their place (before `buildChart`):
```tsx
/**
 * One legend toggle per strategy on the chart (`ChartPanel`): its code, its full name as the
 * tooltip (a retired one says when it stopped), its line's colour and stroke for the swatch, and
 * the tint its pill takes while its line is highlighted. SPY's sheet is the chart's own white, so
 * its pill takes the page ground instead, as SPY's card icon does (`.card:global(.bg-sheet) .icon`).
 */
function legendEntry(st: Board['rows'][number]['strategy'], look: Look): LegendEntry {
  const retired = st.status === 'retired';
  return {
    id: st.id,
    code: st.short,
    tip: retired ? `${st.name} · ${retiredLabel(st.paperEnd).toLowerCase()}` : st.name,
    retired,
    line: look.line,
    stroke: look.dash === null ? 'solid' : look.dash === BENCHMARK_DASH ? 'dotted' : 'dashed',
    pill: look.bg === 'bg-sheet' ? 'var(--chip-plain)' : look.tint,
  };
}
```
**Impact:** `buildChart`'s return (`lines: {id,d,color,width,dash}[]`) matches `ChartLine[]`
structurally; no change to it. The comment on `shown` (L67-68, "The chart, the legend and the
switch show...") stays true. Run `cd web && npx tsc --noEmit` — must be clean.

### Step 4: Styles
**File:** `web/app/(app)/leaderboard/leaderboard.module.css`

**4a — L19-23.** Replace:
```css
.legend { display: flex; flex-wrap: wrap; gap: 8px 18px; font-size: 14px; }
.legendItem { display: flex; align-items: center; gap: 7px; white-space: nowrap; }
/* Mobile: spread under the axis labels, wrapping onto a second line rather than off the edge: six
   live codes plus a picked retired one do not fit 390px on one line. */
.legendRow { flex-wrap: wrap; justify-content: flex-start; gap: 6px 14px; }
```
with:
```css
/* The chart legend: one toggle per line (owner, 2026-11-12). Every item is always a pill, padded
   `--pill-x` each side whether or not it is pressed, and the row is pulled out by the same amount
   into the `.pad` around it, so the first swatch sits exactly on the sheet's text edge (where the
   champion label starts) and pressing an item moves nothing. The two paddings are the spacing
   between items (14px, as before). The pull stays inside the `.pad` padding, so nothing reaches
   past the sheet. */
.legend {
  --pill-x: 7px;
  display: flex; flex-wrap: wrap; gap: 0; font-size: 14px;
  margin-inline: calc(var(--pill-x) * -1);
}
.legendItem {
  display: flex; align-items: center; gap: 7px; white-space: nowrap;
  margin: 0; border: 0; padding: 3px var(--pill-x); border-radius: 999px;
  background: transparent; cursor: pointer; -webkit-tap-highlight-color: transparent;
  transition: background-color 0.15s ease, opacity 0.15s ease;
}
/* Pressed: the strategy's own sheet tint (`--pill`, from the page; SPY's is the page ground). */
.legendItem[aria-pressed='true'] { background: var(--pill); }
.legendItem:focus-visible { outline: 2px solid var(--coral); outline-offset: 1px; }
@media (hover: hover) {
  .legendItem[aria-pressed='false']:hover { background: var(--chip-plain); }
}
/* While anything is highlighted, the items that are not step back with their lines. */
.legend[data-focus] .legendItem[aria-pressed='false'] { opacity: 0.45; }
.legend[data-focus] .legendRetired[aria-pressed='false'] { opacity: 0.3; }
/* Mobile: under the axis labels, wrapping onto a second line rather than off the edge: six live
   codes plus a picked retired one do not fit 390px on one line. */
.legendRow { flex-wrap: wrap; justify-content: flex-start; }
```

**4b — after L26** (`.swatchDash { ... }`), insert:
```css

/* Highlighted lines (`ChartPanel`): with anything pressed, every other line fades to 20%. The
   pressed lines' extra pixel and their place on top are set on the paths themselves. With nothing
   pressed no rule here matches and the lines are exactly as `buildChart` drew them. */
.chart path[data-line] { transition: opacity 0.15s ease; }
.chart[data-focus] path[data-line]:not([data-on]) { opacity: 0.2; }
/* The fades are motion; with reduced motion they snap. */
@media (prefers-reduced-motion: reduce) {
  .chart path[data-line], .legendItem { transition: none; }
}
```

**4c — L236-246** (inside the third `@media (min-width: 1024px)` block, which continues with the
card rules — keep the `@media` line and everything after L246). Replace:
```css
  /* The legend is one row. It sits beside the headline figures when it fits and drops under them,
     still one row, when it does not. Only past a dozen strategies do its codes ellipsise (each
     keeps its full name as its tooltip), never a second row. */
  .headline { flex-wrap: wrap; row-gap: 14px; }
  .headline > .legend {
    flex: 0 1 auto; min-width: 0; margin-left: auto;
    flex-wrap: nowrap; gap: 6px 14px; font-size: 13px;
  }
  .headline > .legend .legendItem { min-width: 0; gap: 6px; }
  .headline > .legend .swatch, .headline > .legend .swatchDash { flex: none; }
  .headline > .legend .legendLabel { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
```
with:
```css
  /* The legend is one row of its own, under the headline figures and the window line, starting on
     the sheet's text edge (owner, 2026-11-12). Only past a dozen strategies do its codes ellipsise
     (each keeps its full name as its tooltip), never a second row. */
  .legendDesk { flex-wrap: nowrap; font-size: 13px; }
  .legendDesk .legendItem { min-width: 0; gap: 6px; }
  .legendDesk .swatch, .legendDesk .swatchDash { flex: none; }
  .legendDesk .legendLabel { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
```
**Impact:** `.headline` keeps its base rule (L7); its desktop wrap existed only for the legend and
goes. `.legendRetired { opacity: 0.6; }` (L95) is unchanged and still applies when nothing is
pressed.

### Step 5: The Playwright step
**File:** `.claude/skills/verify-seer/features/steps/leaderboard-legend.mjs` (new)
**Code:**
```js
// Chart legend toggles (leaderboard-legend-toggles phase 1). The legend is its own row under the
// headline figures, its first swatch on the champion label's left edge, one row on desktop. Every
// item is a toggle (aria-pressed): pressed lines keep their colour, are 1px thicker and drawn last,
// every other line fades to 20%; nothing pressed is the chart as before. A card pick adds to the
// pressed set; un-pressing the pick keeps the card picked; a reload starts from the pick alone.
// Run on `up` demo data:
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 1440 --theme light
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 1024
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 390
// Demo roster in board order: SPY (champion, dotted, 1.75px), A, F4, F4's twin, F1, C (2px each,
// from view.ts looks()). With no ?s= the pick is A.
const F4 = 'F4-MOM12-N20-TREND';
const TWIN = 'F4-MOM12-N20-TREND-CX';
const F1 = 'F1-SPY-SMA200-M';
const IDS = ['SPY', 'A', F4, TWIN, F1, 'C'];
// buildChart's order: board order, champion (SPY) last.
const DRAW_ORDER = ['A', F4, TWIN, F1, 'C', 'SPY'];
const BASE = { SPY: 1.75, A: 2, [F4]: 2, [TWIN]: 2, [F1]: 2, C: 2 };
const CHART = 'svg[aria-label="Equity curves of each strategy against SPY"]';
const card = id => `a[href="/leaderboard?s=${encodeURIComponent(id)}"][data-status]`;

export default async ({ page, base, shot, log }) => {
  const width = page.viewportSize()?.width ?? 0;
  const near = (a, b, tol) => Math.abs(a - b) <= tol;
  const same = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());

  // Settled opacities without waiting on the 0.15s fade; the fade itself is checked at the end.
  await page.emulateMedia({ reducedMotion: 'reduce' });

  const read = () => page.evaluate(sel => {
    const shown = el => el.getClientRects().length > 0;
    const svg = document.querySelector(sel);
    const sb = svg.getBoundingClientRect();
    const buttons = [...document.querySelectorAll('button[data-id][aria-pressed]')].filter(shown).map(b => {
      const r = b.getBoundingClientRect();
      return {
        id: b.dataset.id, pressed: b.getAttribute('aria-pressed') === 'true',
        top: Math.round(r.top), bottom: r.bottom,
        swatchLeft: b.firstElementChild.getBoundingClientRect().left,
        inHeadline: b.closest('[class*="headline"]') !== null,
        opacity: parseFloat(getComputedStyle(b).opacity),
      };
    });
    const paths = [...svg.querySelectorAll('path[data-line]')].map(p => ({
      id: p.dataset.line, on: p.hasAttribute('data-on'), stroke: p.getAttribute('stroke'),
      dash: p.getAttribute('stroke-dasharray'), width: parseFloat(p.getAttribute('stroke-width')),
      opacity: parseFloat(getComputedStyle(p).opacity),
    }));
    return { buttons, paths, focus: svg.hasAttribute('data-focus'), svgTop: sb.top, svgBottom: sb.bottom };
  }, CHART);
  const pressedIds = st => st.buttons.filter(b => b.pressed).map(b => b.id);
  const press = async id => {
    await page.locator(`button[data-id="${id}"]:visible`).click();
    await page.mouse.move(0, 0); // no hover tint, no tooltip
  };
  const expectPressed = (st, want, what) => {
    if (!same(pressedIds(st), want)) throw new Error(`${what}: pressed ${JSON.stringify(pressedIds(st))}, want ${JSON.stringify(want)}`);
  };
  let strokes = null; // each line's colour and dash as the server drew it, recorded on first read
  const checkLines = (st, litIds, what) => {
    const lit = new Set(litIds);
    if (st.paths.length !== IDS.length) throw new Error(`${what}: ${st.paths.length} lines, want ${IDS.length}`);
    for (const p of st.paths) {
      const b = BASE[p.id];
      if (strokes && (p.stroke !== strokes[p.id].stroke || p.dash !== strokes[p.id].dash))
        throw new Error(`${what}: ${p.id} changed colour or dash: ${p.stroke} ${p.dash}`);
      if (lit.has(p.id)) {
        if (!p.on || !near(p.width, b + 1, 0.001) || !near(p.opacity, 1, 0.01))
          throw new Error(`${what}: highlighted ${p.id} is width ${p.width} (want ${b + 1}), opacity ${p.opacity}, data-on ${p.on}`);
      } else if (lit.size) {
        if (p.on || !near(p.width, b, 0.001) || !near(p.opacity, 0.2, 0.02))
          throw new Error(`${what}: faded ${p.id} is width ${p.width} (want ${b}), opacity ${p.opacity} (want 0.2)`);
      } else if (p.on || p.width !== b || p.opacity !== 1) {
        throw new Error(`${what}: ${p.id} is width ${p.width} (want ${b}), opacity ${p.opacity} (want 1), data-on ${p.on}`);
      }
    }
    if (lit.size) {
      const tail = st.paths.slice(-lit.size).map(p => p.id);
      if (!same(tail, litIds)) throw new Error(`${what}: drawn last ${tail.join(', ')}, want the highlighted ${litIds.join(', ')}`);
    } else if (JSON.stringify(st.paths.map(p => p.id)) !== JSON.stringify(DRAW_ORDER)) {
      throw new Error(`${what}: draw order ${st.paths.map(p => p.id).join(', ')}, want ${DRAW_ORDER.join(', ')}`);
    }
    if (st.focus !== lit.size > 0) throw new Error(`${what}: svg data-focus ${st.focus} with ${lit.size} highlighted`);
  };
  const open = async path => {
    await page.goto(base + path, { waitUntil: 'networkidle' });
    await page.mouse.move(0, 0);
  };

  if (width < 1024) {
    // J9 (R2.1): on the phone the legend is the row under the axis, and its items are the same toggles.
    await open('/leaderboard');
    const st0 = await read();
    if (JSON.stringify(st0.buttons.map(b => b.id)) !== JSON.stringify(IDS)) throw new Error(`phone legend: ${st0.buttons.map(b => b.id).join(', ')}`);
    if (st0.buttons.some(b => b.top < st0.svgBottom)) throw new Error('the phone legend is not under the chart');
    expectPressed(st0, ['A'], 'phone, landed');
    await press(F1);
    const st1 = await read();
    expectPressed(st1, ['A', F1], 'phone, F1 pressed');
    checkLines(st1, ['A', F1], 'phone, F1 pressed');
    await shot('phone-two-lit');
    await press(F1);
    expectPressed(await read(), ['A'], 'phone, F1 released');
    log('J9 phone: the legend is the row under the axis; pressing F1 sets aria-pressed true and lights its line beside A; pressing again sets it false');
    return;
  }

  // J1 (R1.1, R1.2): the legend is its own row under the figures, on the champion label's edge, one row.
  await open('/leaderboard');
  const anchor = await page.evaluate(() => {
    const label = [...document.querySelectorAll('[class*="statLabel"]')]
      .find(e => e.getClientRects().length > 0 && e.textContent.includes('champion'));
    const stats = label.closest('[class*="stats"]');
    return { left: label.getBoundingClientRect().left, statsBottom: stats.getBoundingClientRect().bottom, text: label.textContent };
  });
  const st0 = await read();
  strokes = Object.fromEntries(st0.paths.map(p => [p.id, { stroke: p.stroke, dash: p.dash }]));
  if (JSON.stringify(st0.buttons.map(b => b.id)) !== JSON.stringify(IDS)) throw new Error(`legend: ${st0.buttons.map(b => b.id).join(', ')}`);
  const first = st0.buttons[0];
  if (!near(first.swatchLeft, anchor.left, 1)) throw new Error(`first swatch at x ${first.swatchLeft}, "${anchor.text}" at x ${anchor.left}`);
  if (st0.buttons.some(b => b.inHeadline)) throw new Error('the legend is still inside the headline');
  if (first.top < anchor.statsBottom || first.bottom > st0.svgTop) throw new Error(`legend row at ${first.top}, figures end ${anchor.statsBottom}, chart starts ${st0.svgTop}`);
  const tops = new Set(st0.buttons.map(b => b.top));
  if (tops.size !== 1) throw new Error(`legend wraps: tops ${JSON.stringify([...tops])}`);
  log(`J1 row at ${width}px: ${IDS.length} toggles in one row at y ${first.top}, under the figures (end ${anchor.statsBottom.toFixed(1)}) ` +
    `and above the chart; first swatch x ${first.swatchLeft.toFixed(2)}, "${anchor.text.trim()}" x ${anchor.left.toFixed(2)}`);

  // Landing: only the pick (A) is pressed.
  expectPressed(st0, ['A'], 'landed');
  checkLines(st0, ['A'], 'landed');
  await shot('landed');

  // J2 (R2.1): a click flips aria-pressed, both ways.
  await press(F1);
  const st2 = await read();
  if (!st2.buttons.find(b => b.id === F1).pressed) throw new Error('F1 did not turn pressed');
  await press(F1);
  const st2b = await read();
  if (st2b.buttons.find(b => b.id === F1).pressed) throw new Error('F1 did not turn back');
  log('J2 toggle: F1 aria-pressed false -> true -> false');

  // J3 (R2.2): two pressed (A, F4): both 1px thicker, own colour, drawn last; the rest at 20%.
  await press(F4);
  const st3 = await read();
  expectPressed(st3, ['A', F4], 'A and F4');
  checkLines(st3, ['A', F4], 'A and F4');
  const dim = st3.buttons.filter(b => !b.pressed);
  if (dim.some(b => b.opacity > 0.5)) throw new Error(`unpressed legend items not faded: ${dim.map(b => `${b.id} ${b.opacity}`).join(', ')}`);
  log(`J3 compare two: A and F4 at ${BASE.A + 1}px, full opacity, drawn last; SPY, ${TWIN}, ${F1}, C at their own width and opacity 0.2; unpressed items faded`);
  await shot('two-lit');

  // J4 (R2.4): every item pressed at once, SPY included.
  for (const id of IDS) if (!(await read()).buttons.find(b => b.id === id).pressed) await press(id);
  const st4 = await read();
  expectPressed(st4, IDS, 'all');
  checkLines(st4, IDS, 'all');
  log('J4 all six pressed, SPY included: every line 1px thicker at full opacity');
  await shot('all-lit');

  // J5 (R2.3): nothing pressed is today's chart: own colour and dash, SPY 1.75px, the rest 2px, full opacity, champion last.
  for (const id of IDS) await press(id);
  const st5 = await read();
  expectPressed(st5, [], 'none');
  checkLines(st5, [], 'none');
  if (st5.buttons.some(b => b.opacity !== 1 && b.id !== 'C')) throw new Error('legend items still faded with nothing pressed');
  log(`J5 none pressed: ${st5.paths.map(p => `${p.id} ${p.width}px`).join(', ')}, all opacity 1, no data-focus`);
  await shot('none-lit');

  // J6 (R3.1): picking a card adds it. Fresh load (A), press F1, then pick C by its card.
  await open('/leaderboard');
  await press(F1);
  expectPressed(await read(), ['A', F1], 'before the pick');
  const c = page.locator(card('C')).first();
  await c.scrollIntoViewIfNeeded();
  const cb = await c.boundingBox();
  await c.click({ position: { x: cb.width * 0.7, y: cb.height / 2 } }); // its right 60% is on top
  await page.waitForURL(u => u.searchParams.get('s') === 'C');
  await page.getByText(/Go-live checklist · C/).first().waitFor();
  await page.waitForFunction(() => document.querySelector('button[data-id="C"]')?.getAttribute('aria-pressed') === 'true');
  await page.mouse.move(0, 0);
  const st6 = await read();
  expectPressed(st6, ['A', F1, 'C'], 'after picking C');
  checkLines(st6, ['A', F1, 'C'], 'after picking C');
  if ((await c.getAttribute('aria-current')) !== 'true') throw new Error('C is not the picked card');
  log('J6 pick adds: A and F1 pressed, card C clicked -> ?s=C, C pressed and lit, A and F1 still pressed');
  await shot('pick-added');

  // J7 (R3.2): un-pressing the pick's item un-highlights its line; the card stays picked.
  const eyebrow = () => page.evaluate(() =>
    [...document.querySelectorAll('.eyebrow')].map(e => e.textContent).find(t => t.startsWith('Go-live checklist')));
  const before = await eyebrow();
  await press('C');
  const st7 = await read();
  expectPressed(st7, ['A', F1], 'C released');
  checkLines(st7, ['A', F1], 'C released');
  if (new URL(page.url()).searchParams.get('s') !== 'C') throw new Error(`URL moved: ${page.url()}`);
  if ((await c.getAttribute('aria-current')) !== 'true') throw new Error('C lost aria-current');
  if ((await eyebrow()) !== before) throw new Error(`checklist changed: "${before}" -> "${await eyebrow()}"`);
  log(`J7 C released: its line at 0.2 with the others, card C still aria-current, checklist still "${before}", URL still ?s=C`);

  // J8 (R3.3): a reload starts from the pick alone; nothing went to the URL or to storage.
  const url = new URL(page.url());
  if (url.pathname !== '/leaderboard' || url.search !== '?s=C') throw new Error(`state leaked into the URL: ${url.search}`);
  const stored = await page.evaluate(() =>
    JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)]));
  if (stored.includes(F1)) throw new Error(`a highlight leaked into browser storage: ${stored}`);
  await page.reload({ waitUntil: 'networkidle' });
  await page.mouse.move(0, 0);
  const st8 = await read();
  expectPressed(st8, ['C'], 'reloaded');
  checkLines(st8, ['C'], 'reloaded');
  log('J8 reload on ?s=C: only C pressed (A and F1 forgotten); URL carried only ?s=C, storage held no highlight');
  await shot('reloaded');

  // Motion: the fade animates, and snaps under reduced motion.
  const duration = () => page.locator(`${CHART} path[data-line]`).first().evaluate(p => getComputedStyle(p).transitionDuration);
  if (parseFloat(await duration()) !== 0) throw new Error('lines animate under prefers-reduced-motion');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  if (!(parseFloat(await duration()) > 0)) throw new Error('no fade on the chart lines');
  log('motion: line fades take 0.15s, none under prefers-reduced-motion');
};
```
**Impact:** new file under the feature map's `steps/`; nothing else reads it.

### Step 6: Feature map entry
**File:** `.claude/skills/verify-seer/features/leaderboard.md`

**6a — after L5** (the "Equity curves..." bullet) insert:
```markdown
- Chart legend toggles (owner, 2026-11-12): the legend is a row of its own under the headline figures and the window line, left-aligned so its first swatch starts exactly where the champion label ("SPY, champion") starts; on desktop it is one row, on a phone it wraps under the axis. Every item is a toggle button (`aria-pressed`, the full name as its tooltip). While one or more are pressed, each pressed strategy's line keeps its colour, is 1px thicker and is drawn above the rest, every other line fades to 20%, the pressed items wear their sheet tint as a pill (SPY: the page ground) and the others fade. Nothing pressed is the chart exactly as before. Any number can be pressed, SPY included. Picking a card adds it to the pressed set and never clears the others; pressing the pick's item again un-highlights its line while the card stays picked. Highlights live in page memory only: a reload starts from the pick alone.
```
**6b — after L38** (the `leaderboard-spread.mjs --width 390` comment line) insert:
```sh
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 1440 --theme light
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 1024
                                # J1 one row, first swatch on "SPY, champion"; J2-J5 toggles, highlight, all, none;
                                # J6 card C adds to A+F1; J7 un-press C, card stays picked; J8 reload -> C only; result: PASS
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 390
                                # phone: the wrapping row under the axis, same toggles; result: PASS
```
**6c — after L60** (the twin swatch gotcha) insert:
```markdown
- With no `?s=` the demo pick is A, so `/leaderboard` opens with A's line highlighted and every other line at 20%. That is the pick seeding the legend, not a bug.
- Both legends are in the DOM (desktop row and phone row, one hidden by `desk-only` / `mobile-only`). Query the visible one (`button[data-id]:visible`); `data-id` is the strategy id, the accessible name is its full name.
```
The spread bullet (L10) keeps "the chart legend is one row" as is.

## Principles applied

- Subtract before you add: the server `Legend` and the `.headline > .legend` / desktop `.headline` wrap rules are deleted outright rather than kept beside the new legend; their only job (legend in the headline row) is gone.
- Laziness protocol: one client component holds state, svg and both legends; no context provider, no store, no hook module. `buildChart`, `card()` and the `Link` are untouched, and the pick reaches the state through a plain `pickId` prop, not a URL reader in the client.
- Make illegal states unrepresentable: "highlighted" is derived during render as `active ∩ entries` (`lit`), so a stale id (a retired pick that left the chart) can never fade every line with nothing lit; `data-focus` is computed from `lit`, never stored beside it.
- Boundary discipline: the client module takes plain, ready-made `LegendEntry` values (stroke kind and pill colour decided once in `legendEntry` on the server) and imports nothing from `view.ts`.
- Prove it works / test behaviour: proof is a Playwright drive of the real page measuring swatch position, `aria-pressed`, path width, opacity and order; the unit tests assert rendered markup, not internals or class names.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/leaderboard-legend-toggles/web && ([ -d node_modules ] || cp -al /home/miftah/seer/web/node_modules node_modules) && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/leaderboard-legend-toggles/web && npm test` (all green, including the six new `ChartPanel` tests and the existing `RetiredShelf`, `PickName`, `view` tests)
**Proof:** the real leaderboard page, driven signed in on a throwaway run with demo data.
- Harness: `.claude/skills/verify-seer` — from the worktree root: `V=.claude/skills/verify-seer/scripts/verify.sh; $V up` (prints `RUN=`), then the journeys, then `$V down RUN`. `up` snapshots `web/`, so run it after the code lands (or `down`/`up` again after any web edit). Each `ui` run prints numbered `J…` log lines and ends `result: PASS` or `result: FAIL`.
- Feature-map entries: `.claude/skills/verify-seer/features/leaderboard.md`
- Journeys:
  - **J1** · traces R1.1, R1.2 — `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 1440 --theme light` and again with `--width 1024` → passes when each run's log has the `J1 row` line (six toggles at one y, below the figures' bottom and above the chart's top, first swatch x within 1px of the "SPY, champion" label x) and ends `result: PASS`
  - **J2** · traces R2.1 — same 1440 run → passes when the log has `J2 toggle: F1 aria-pressed false -> true -> false`
  - **J3** · traces R2.2 — same 1440 run → passes when the log has the `J3 compare two` line: A and F4 at stroke-width 3, opacity 1, the last two paths in the svg, every other path at its own width (SPY 1.75, others 2) and computed opacity 0.2±0.02, colours and dashes unchanged; screenshot `two-lit` shows two bold lines over faded ones
  - **J4** · traces R2.4 — same 1440 run → passes when the log has `J4 all six pressed, SPY included` (six `aria-pressed="true"`, six paths at width+1, opacity 1)
  - **J5** · traces R2.3 — same 1440 run → passes when the log has `J5 none pressed` listing `A 2px … C 2px, SPY 1.75px` in that draw order (champion last), all opacity 1, no `data-focus`; plus `npx vitest run 'app/(app)/leaderboard/ChartPanel.test.tsx'` passes its "with nothing pressed, draws every line exactly as given" test
  - **J6** · traces R3.1 — same 1440 run → passes when the log has `J6 pick adds`: after pressing F1 on `/leaderboard` (A picked) and clicking card C, the URL is `?s=C` and the pressed set is exactly {A, F1, C}, with C's path lit and C's card `aria-current="true"`
  - **J7** · traces R3.2 — same 1440 run → passes when the log has `J7 C released`: pressed set {A, F1}, C's path at opacity 0.2, card C still `aria-current="true"`, the checklist eyebrow text identical before and after, URL still `?s=C`
  - **J8** · traces R3.3 — same 1440 run → passes when the log has `J8 reload on ?s=C`: after `page.reload()` the pressed set is exactly {C}; before the reload the URL search was exactly `?s=C` and local/session storage held no highlighted id
  - **J9** · traces R2.1 — `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 390` → passes when the log has `J9 phone` (the six toggles sit below the chart; F1 flips to pressed, lights beside A, flips back) and ends `result: PASS` with no horizontal-scroll failure
  - Screenshots (read the PNGs, not just the exit code): `$V shoot RUN --theme both --width 1440 --width 390 /leaderboard '/leaderboard?s=C'` → passes when every PNG renders (no 4xx, no console error, no horizontal scroll) and, read by eye, the legend sits left under the figures in both themes, SPY's pressed pill is visible in light mode, and A's line stands out with the others faded
- Neighbor check: the card spread and twin colours read the same chart and legend — `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1440 --theme light` and `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs` → both end `result: PASS` (the spread step's own "legend is one row" check counts six visible `[class*="legendItem"]` at one top; the twin step finds one solid `var(--sky-line)` path and one `var(--teal-line)` path dashed `3 3`)
- Cost: none (offline run, no LLM, no `--net`)
**Exit criteria:** tsc and vitest green in `web/`; `leaderboard-legend.mjs` ends `result: PASS` at 1440 (light), 1024 and 390; `leaderboard-spread.mjs` and `leaderboard-twin.mjs` still PASS; screenshots at 1440 and 390 in light and dark read correctly.

## Handoffs

- None to another phase (single-phase set).
- Left alone deliberately (drive-by, not this request): `leaderboard-spread.mjs`'s legend check comment says "the earlier revamp's promise"; it still holds and is not edited. `.headline`'s base `justify-content: space-between` (L7) is now a one-child flex row and harmless; not touched.

## Rollback

Revert the phase commit: it restores `Legend` and the old CSS in `page.tsx` / `leaderboard.module.css`, deletes `ChartPanel.tsx`, its test and `leaderboard-legend.mjs`, and restores `features/leaderboard.md`. No data, schema, URL or storage is involved.
