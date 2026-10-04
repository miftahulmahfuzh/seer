> Adopted from `SERA_LAB_SITE_PLAN.md` phase 3. Source: `.workflows/plan/sera-lab-site/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Sera shell, access gate, chart kit

**Plan set:** `SERA_LAB_SITE_PLAN.md`
**Analysis:** `20261004-211729-H54F_code_analyzer.md`
**Satisfies:** R1, R2, R4, R7. R1: the desktop shell. R2: `/sera`, visible only to mahfuzh74@gmail.com. R4: the chart kit every page draws with. R7 (cross-cutting): the chart kit covers lines, areas, steps, scatter with zones, grouped and signed bars, and legends.
**Depends on:** none
**Difficulty:** HARD
**Package:** `web/app/sera`, `web/components/sera`

---

## Goal

Before this phase, nothing lives at `/sera`. After it, `/sera/**` is a gated section: a signed-out visitor goes to `/signin?next=%2Fsera` and comes back after Google sign-in, and any other account gets a 404. The section has its own desktop shell: a rail with the wordmark "Sera.", five icon-only tabs and a way back to Seer, plus a 1360 px content column. Phases 4–6 get a complete, tested component kit: `PageHeader`, `Section` (+ `SectionGrid`), `Stat`, `Term`, and the server-rendered SVG charts `LineChart`, `ScatterChart`, `BarChart` and `Legend`, built on a pure `scale.ts`. Seer's own desktop rail gains a Sera link for the Sera account.

All code in this plan was compiled and run in a scratch copy of `web/` at `c138b08`:
- `npx tsc --noEmit` exits 0.
- `npx vitest run` passes 13 files and 123 tests (85 existing, 38 new).
- `next build` compiles, including a throwaway `/sera/page.tsx` that used every component. It reported `ƒ /sera`.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none
**Renames:** none
**Creates:**
- `web/lib/sera/access.ts`: `SERA_EMAIL = 'mahfuzh74@gmail.com'`, `isSeraUser(email: string | null | undefined): boolean`
- `web/lib/sera/gate.ts`: `requireSera(next = '/sera'): Promise<User>`, server-only, imports `@/auth`
- `web/lib/allow.ts`: `safeNext(next: string | string[] | undefined, fallback = '/'): string` (new export in an existing file)
- `web/app/sera/layout.tsx` (default `SeraLayout`, `metadata` with `title.template: '%s · Sera'`), `web/app/sera/sera.module.css`, `web/app/sera/not-found.tsx`
- `web/components/sera/SeraNav.tsx` (`SeraNav`, a client component)
- `web/components/sera/PageHeader.tsx` (`PageHeader`, `PageHeaderProps`)
- `web/components/sera/Section.tsx` (`Section`, `SectionGrid`, `SectionProps`, `SectionBg`)
- `web/components/sera/Stat.tsx` (`Stat`, `StatProps`)
- `web/components/sera/Term.tsx` (`Term`, `TermProps`)
- one CSS module each: `SeraNav`, `PageHeader`, `Section`, `Stat`, `Term`
- `web/components/sera/charts/scale.ts`. Types: `Domain`, `Pt`, `Tick`, `RefLine`, `TickSpec`, `Format`. Constants and functions: `CHART_COLORS`, `colorAt`, `isNum`, `clamp`, `linear`, `extent`, `niceStep`, `niceTicks`, `ticksWithin`, `niceDomain`, `resolveAxis`, `dateNum`, `yearTicks`, `linePath`, `areaPath`, `stepPoints`, `spread`, `textWidth`, `truncate`. Formatters: `fmtPct`, `fmtSignedPct`, `fmtNumber`, `fmtMultiple`.
- `web/components/sera/charts/LineChart.tsx`: `LineChart`, `LineSeries`, `LinePoint`, `XValue`, `LineChartProps`
- `web/components/sera/charts/ScatterChart.tsx`: `ScatterChart`, `ScatterPoint`, `ScatterRegion`, `ScatterChartProps`
- `web/components/sera/charts/BarChart.tsx`: `BarChart`, `barGroups`, `BarItem`, `BarGroup`, `SimpleBar`, `BarChartProps`
- `web/components/sera/charts/Legend.tsx`: `Legend`, `legendFromSeries`, `LegendItem`, `LegendShape`
- `web/components/sera/charts/parts.tsx` (internal: `HRef`, `VRef`), `charts.module.css`
- tests: `web/lib/sera/access.test.ts`, `web/components/sera/charts/scale.test.ts`, `web/components/sera/charts/charts.test.tsx`

**Signature changes:**
- `Nav()` -> `Nav({ showSera = false }: { showSera?: boolean })` (`web/components/Nav.tsx`)
- `SignIn` searchParams type gains `next?: string | string[]` (`web/app/signin/page.tsx`)

**Behaviour changes in shared files:**
- `components/tooltip.ts` `showTip`: tips longer than 48 characters wrap, up to 340 px wide. A `\n` in a `data-tip` forces a line break (`white-space: pre-line`). Short tips look exactly as before.
- `app/(app)/layout.tsx` passes `showSera={isSeraUser(user.email)}` to `Nav`.
- `/signin` honours `?next=`. It accepts internal paths only, both for the sign-in `redirectTo` and for the already-signed-in redirect.

**Requires (from earlier phases):** none

**Leaves alone (owned by others):**
- `web/lib/sera/{types,lab,derive,glossary,markdown,fixture}.ts` and their tests (Phase 2). Nothing in this phase imports them.
- `web/app/sera/page.tsx` and `overview.*` (Phase 4)
- `web/app/sera/methods/**` (Phase 5)
- `web/app/sera/{journal,ideas,how}/**` and `web/components/sera/diagrams/**` (Phase 6)
- `web/data/lab.json` and `engine/**` (Phase 1)
- CI, skills, docs (Phase 7)

### Component API: what Phases 4–6 code against

The rules:
- Every component below is a **server component** with no `'use client'`, except `SeraNav`.
- Charts take plain props and never import the snapshot or `web/lib/sera/*`.
- Formatter props (`yFormat`, `format`, …) are functions. That is fine from a server page. Any page that would rather pass only serializable props can give explicit `Tick[]` lists (`TickSpec`) instead of formatters.
- Colours are CSS strings, normally Seer v2 tokens (`'var(--coral)'`).
- Sizes are viewBox units. The SVG scales to the column width with `preserveAspectRatio="xMidYMid meet"`, so its text keeps its proportions.

Import paths:
```ts
import { PageHeader } from '@/components/sera/PageHeader';
import { Section, SectionGrid } from '@/components/sera/Section';
import { Stat } from '@/components/sera/Stat';
import { Term } from '@/components/sera/Term';
import { LineChart, type LineSeries } from '@/components/sera/charts/LineChart';
import { ScatterChart, type ScatterPoint, type ScatterRegion } from '@/components/sera/charts/ScatterChart';
import { BarChart, barGroups, type BarGroup } from '@/components/sera/charts/BarChart';
import { Legend, legendFromSeries, type LegendItem } from '@/components/sera/charts/Legend';
import { fmtPct, fmtSignedPct, fmtNumber, fmtMultiple, type RefLine, type Tick } from '@/components/sera/charts/scale';
import { requireSera } from '@/lib/sera/gate';
```

Prop shapes (full definitions are in Steps 5–9):
```ts
PageHeader({ eyebrow: string; title: string; lede?: ReactNode; asOf?: string; aside?: ReactNode })
Section({ eyebrow?: string; title?: string; caption?: ReactNode; bg?: 'sheet'|'lav'|'butter'|'sky'|'stone'|'coral';
          aside?: ReactNode; id?: string; className?: string; children?: ReactNode })
SectionGrid({ columns?: string /* grid-template-columns, default 2 equal */; className?: string; children: ReactNode })
Stat({ value: string; label: ReactNode; tone?: 'pos'|'neg'; tip?: string; sub?: ReactNode; size?: 'lg'|'md' })
Term({ term: string; definition: string; children?: ReactNode })     // pages pass glossary text in

type RefLine = { value: number; label?: string; color?: string; dash?: string; tip?: string };
type Tick = { value: number; label: string };
type TickSpec = number | readonly Tick[];                            // target count, or explicit ticks

LineChart({ series: LineSeries[]; ariaLabel: string; x?: 'date'|'number'; xDomain?; yDomain?; includeZero?;
            xFormat?; yFormat?; xTicks?: TickSpec; yTicks?: TickSpec; refLines?: RefLine[]; xLabel?; yLabel?;
            legend?: ReactNode; width? = 960; height? = 360; preserveAspectRatio?; className? })
  LineSeries = { id; label; points: [x: string(ISO date)|number, y: number|null, tip?: string][];
                 color?; width?; dash?; opacity?; area?; areaOpacity?; step?; dots?; tip?; endLabel? }
ScatterChart({ points: ScatterPoint[]; ariaLabel; regions?: ScatterRegion[]; refX?: RefLine[]; refY?: RefLine[];
               xDomain?; yDomain?; includeZeroX?; includeZeroY?; xFormat?; yFormat?; xTicks?; yTicks?;
               xLabel?; yLabel?; legend?; width? = 960; height? = 440; preserveAspectRatio?; className? })
  ScatterPoint = { id; x: number|null; y: number|null; color?; r?; ring?; tip?; href?; label? }
  ScatterRegion = { x0?; x1?; y0?; y1? /* null|undefined = plot edge */; label?; color? = 'var(--sky)'; opacity?; tip? }
BarChart({ groups: BarGroup[]; ariaLabel; orientation?: 'vertical'|'horizontal'; signed?; color?; domain?;
           format?; ticks?: TickSpec; values?: boolean; refLines?: RefLine[]; axisLabel?; legend?;
           width? = 960; height?; rowHeight?; maxLabelChars? = 28; preserveAspectRatio?; className? })
  BarGroup = { id; label; items: BarItem[]; href?; tip? };  BarItem = { key; value: number|null; color?; tip?; valueText? }
  barGroups(SimpleBar[]) -> BarGroup[];  SimpleBar = { id; label; value; color?; tip?; href?; valueText? }
Legend({ items: LegendItem[]; className? });  LegendItem = { label; color; shape?: 'line'|'dash'|'dot'|'ring'|'zone'; tip? }
legendFromSeries(LineSeries[]) -> LegendItem[]
requireSera(next?: string) -> Promise<User>   // redirect / notFound as the layout does
```

Conventions the pages inherit:
- **Page layout.** Under the layout, a page returns `<PageHeader/>` followed by `Section`s (or `SectionGrid`s of them). They stack in the 1360 px column with a 16 px gap. Any other row layout belongs in the page's own CSS module, collapsing to one column below 1024 px.
- **Titles.** A page sets `export const metadata = { title: 'Methods' }`, and the layout's template renders it as "Methods · Sera".
- **Tooltips.** Use `data-tip` on any element, SVG included. The global `TooltipLayer` in `app/layout.tsx` shows it. A `\n` in the text breaks the line.
- **Colours.** Use these meanings:
  - `var(--coral)`: lab methods and the accent
  - `var(--ink-3)` dotted (`dash: '1 5'`): SPY, as on the Leaderboard
  - `var(--pos)` and `var(--neg)`: signs
  - `var(--sky)`: the pass zone
  - `var(--line-b)` and `var(--line-c)`: extra series
- **Charts on tinted sheets.** A chart inside `Section bg="lav"` and the like rings its labels and points in that background, through `--chart-halo`.

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/sera/access.ts:1` | create | `SERA_EMAIL`, `isSeraUser` |
| `web/lib/sera/access.test.ts:1` | create | gate predicate tests |
| `web/lib/sera/gate.ts:1` | create | `requireSera()`: `auth()` → redirect / `notFound()` |
| `web/lib/allow.ts:6` | modify | append `safeNext` after `isAllowed` (ends line 5) |
| `web/lib/allow.test.ts:1` | modify | whole file: existing `isAllowed` tests kept, `safeNext` tests added |
| `web/components/tooltip.ts:16` | modify | `showTip` style block (lines 16–23): wrap long tips, honour `\n` |
| `web/components/sera/charts/scale.ts:1` | create | pure scales, ticks, paths, layout, formatters |
| `web/components/sera/charts/scale.test.ts:1` | create | 24 tests |
| `web/components/sera/charts/charts.module.css:1` | create | chart + legend styles |
| `web/components/sera/charts/parts.tsx:1` | create | `HRef`, `VRef` reference lines |
| `web/components/sera/charts/LineChart.tsx:1` | create | multi-series line chart |
| `web/components/sera/charts/ScatterChart.tsx:1` | create | scatter with regions and links |
| `web/components/sera/charts/BarChart.tsx:1` | create | vertical/horizontal, grouped, signed bars |
| `web/components/sera/charts/Legend.tsx:1` | create | legend + `legendFromSeries` |
| `web/components/sera/charts/charts.test.tsx:1` | create | 10 render tests (`renderToStaticMarkup`) |
| `web/components/sera/Term.tsx:1` + `Term.module.css:1` | create | dotted-underline term with `data-tip` |
| `web/components/sera/Stat.tsx:1` + `Stat.module.css:1` | create | KPI tile |
| `web/components/sera/Section.tsx:1` + `Section.module.css:1` | create | sheet + grid |
| `web/components/sera/PageHeader.tsx:1` + `PageHeader.module.css:1` | create | header with as-of pill and sign-out |
| `web/components/sera/SeraNav.tsx:1` + `SeraNav.module.css:1` | create | Sera rail |
| `web/app/sera/layout.tsx:1` | create | gate + shell |
| `web/app/sera/sera.module.css:1` | create | shell, column, fallback |
| `web/app/sera/not-found.tsx:1` | create | Sera-styled 404 inside the shell |
| `web/components/Nav.tsx:3,16,20-23` | modify | `showSera` prop; Telescope link at the foot of the desktop rail |
| `web/components/Nav.module.css:68` | modify | append `.sera { margin-top: auto; }` after `.wordmark` (ends line 67) |
| `web/app/(app)/layout.tsx:1-14` | modify | compute `isSeraUser(user.email)`, pass to `Nav` |
| `web/app/signin/page.tsx:3,8-10,33` | modify | `next` search param → `safeNext` → both redirects |

32 files: 25 new, 7 modified (each `.tsx` + `.module.css` pair above counts as two files).

## Implementation Steps

### Step 0: Give the worktree its node_modules
**File:** `web/node_modules` (gitignored)
**Change:** `cd /home/miftah/.worktrees/seer/sera-lab-site/web && npm ci` (the lockfile is byte-identical to main's). Every web phase uses this same setup. Never symlink main's `node_modules`: Turbopack refuses it in `next build` with "Symlink [project]/node_modules is invalid, it points out of the filesystem root". This was verified.

**Impact:** none on the tree.

### Step 1: The Sera account check
**File:** `web/lib/sera/access.ts:1` (create)
**Change:** A pure predicate, separate from `gate.ts` so that vitest never imports `next-auth`.
**Code:**
```ts
/** The one account that may see Sera (/sera). Sign-in itself is still limited by ALLOWED_EMAIL. */
export const SERA_EMAIL = 'mahfuzh74@gmail.com';

/** True only for SERA_EMAIL, compared trimmed and case-insensitively. */
export function isSeraUser(email: string | null | undefined): boolean {
  if (!email) return false;
  return email.trim().toLowerCase() === SERA_EMAIL;
}
```

**File:** `web/lib/sera/access.test.ts:1` (create)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { isSeraUser, SERA_EMAIL } from './access';

describe('isSeraUser', () => {
  it('is pinned to the owner address', () => {
    expect(SERA_EMAIL).toBe('mahfuzh74@gmail.com');
  });
  it('accepts the owner, trimmed and case-insensitively', () => {
    expect(isSeraUser('mahfuzh74@gmail.com')).toBe(true);
    expect(isSeraUser('  Mahfuzh74@Gmail.COM ')).toBe(true);
  });
  it('refuses everyone else and missing emails', () => {
    expect(isSeraUser('someone.else@gmail.com')).toBe(false);
    expect(isSeraUser('mahfuzh74@gmail.com.evil.io')).toBe(false);
    expect(isSeraUser('')).toBe(false);
    expect(isSeraUser(null)).toBe(false);
    expect(isSeraUser(undefined)).toBe(false);
  });
});
```
**Impact:** none (new).

### Step 2: Safe `next` paths
**File:** `web/lib/allow.ts:6` (append after `isAllowed`, which ends at line 5)
**Change:** Add `safeNext`. The resulting whole file:
**Code:**
```ts
/** Seer is private to exactly one Google account. */
export function isAllowed(email: string | null | undefined, allowed: string | undefined): boolean {
  if (!email || !allowed) return false;
  return email.trim().toLowerCase() === allowed.trim().toLowerCase();
}

/**
 * A post-sign-in destination taken from `?next=`: only an internal path such as '/sera'.
 * Never '//host', '/\host', a backslash or a control character (open-redirect tricks). Anything else: `fallback`.
 */
export function safeNext(next: string | string[] | undefined, fallback = '/'): string {
  const v = Array.isArray(next) ? next[0] : next;
  if (!v || !v.startsWith('/') || v.startsWith('//') || v.startsWith('/\\')) return fallback;
  if (/[\u0000-\u001f\u007f\\]/.test(v)) return fallback;
  return v;
}
```

**File:** `web/lib/allow.test.ts:1` (replace the whole file; the existing `isAllowed` block is unchanged)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { isAllowed, safeNext } from './allow';

describe('isAllowed', () => {
  it('accepts only the configured email, case-insensitively', () => {
    expect(isAllowed('mahfuzh74@gmail.com', 'mahfuzh74@gmail.com')).toBe(true);
    expect(isAllowed('Mahfuzh74@Gmail.com', 'mahfuzh74@gmail.com')).toBe(true);
    expect(isAllowed('someone.else@gmail.com', 'mahfuzh74@gmail.com')).toBe(false);
  });
  it('rejects everyone when unconfigured or email missing', () => {
    expect(isAllowed('mahfuzh74@gmail.com', undefined)).toBe(false);
    expect(isAllowed('mahfuzh74@gmail.com', '')).toBe(false);
    expect(isAllowed(null, 'mahfuzh74@gmail.com')).toBe(false);
  });
});

describe('safeNext', () => {
  it('keeps internal paths, query included', () => {
    expect(safeNext('/sera')).toBe('/sera');
    expect(safeNext('/sera/methods/M0001?show=all')).toBe('/sera/methods/M0001?show=all');
    expect(safeNext(['/sera/journal', '/x'])).toBe('/sera/journal');
  });
  it('falls back on anything that could leave the site', () => {
    expect(safeNext(undefined)).toBe('/');
    expect(safeNext('')).toBe('/');
    expect(safeNext('sera')).toBe('/');
    expect(safeNext('https://evil.example')).toBe('/');
    expect(safeNext('//evil.example')).toBe('/');
    expect(safeNext('/\\evil.example')).toBe('/');
    expect(safeNext('/sera\\..\\x')).toBe('/');
    expect(safeNext('/sera\nSet-Cookie: x')).toBe('/');
  });
  it('uses the given fallback', () => {
    expect(safeNext('https://evil.example', '/sera')).toBe('/sera');
  });
});
```
**Impact:** only a new export. `isAllowed` is untouched.

### Step 3: The gate
**File:** `web/lib/sera/gate.ts:1` (create)
**Change:** This implements invariant 3. With no session, it calls `redirect('/signin?next=' + encodeURIComponent(next))`, which for the layout is `/signin?next=%2Fsera`. A session whose email fails `isAllowed(…, ALLOWED_EMAIL)` or `isSeraUser` gets `notFound()`.

`notFound()` thrown from the `/sera` layout is caught by the **root** not-found boundary, which is Next's default 404. It is not caught by `app/sera/not-found.tsx`, because a segment's own not-found does not wrap its layout. So a stranger sees nothing Sera-branded. In practice the branch is unreachable today, because `ALLOWED_EMAIL` already equals `SERA_EMAIL` and `auth.ts` refuses every other account at sign-in.
**Code:**
```ts
import { notFound, redirect } from 'next/navigation';
import { auth } from '@/auth';
import { isAllowed } from '@/lib/allow';
import { isSeraUser } from './access';

/**
 * The /sera gate (plan invariant 3). Signed out: sign-in, which returns to `next` afterwards.
 * Signed in as anyone but SERA_EMAIL (or outside ALLOWED_EMAIL): 404, so the section is not revealed.
 * Returns the signed-in Sera user.
 */
export async function requireSera(next = '/sera') {
  const session = await auth();
  const user = session?.user;
  if (!user) redirect(`/signin?next=${encodeURIComponent(next)}`);
  if (!isAllowed(user.email, process.env.ALLOWED_EMAIL) || !isSeraUser(user.email)) notFound();
  return user;
}
```
**Impact:** None until something calls it. It reads cookies, so every `/sera` route is dynamic (`ƒ /sera` in `next build`).

### Step 4: Tooltips that can hold a sentence
**File:** `web/components/tooltip.ts:16` (replace lines 16–23, the `const cs` line through the end of `Object.assign(...)`)
**Change:** Glossary definitions (Term) and multi-fact point tips are longer than the one-line pills built for icon buttons. Tips over 48 characters now wrap in a 340 px rounded box, and `\n` forces a break. Short tips keep the exact old style. The whole function after the change:
**Code:**
```ts
export function showTip(el: Element, text?: string) {
  const t = text ?? el.getAttribute('data-tip');
  if (!t) return;
  if (!tip) {
    tip = document.createElement('div');
    tip.setAttribute('role', 'tooltip');
    document.body.appendChild(tip);
  }
  clearTimeout(hideTimer);
  const cs = getComputedStyle(el);
  // Short captions stay one-line pills. Longer ones (Sera's glossary terms, chart points) wrap in a
  // rounded box; a '\n' in the text forces a line break.
  const multi = t.includes('\n');
  const long = multi || t.length > 48;
  Object.assign(tip.style, {
    position: 'fixed', zIndex: '9999', pointerEvents: 'none', left: '0px', top: '0px',
    background: cs.getPropertyValue('--ink').trim() || '#1d1c1a',
    color: cs.getPropertyValue('--sheet').trim() || '#ffffff',
    font: `500 13px/${long ? '1.4' : '1.2'} var(--font-outfit), system-ui, sans-serif`, letterSpacing: '0.01em',
    padding: long ? '10px 14px' : '9px 14px', borderRadius: long ? '16px' : '999px',
    whiteSpace: multi ? 'pre-line' : long ? 'normal' : 'nowrap', maxWidth: long ? '340px' : 'none',
    opacity: '1', transition: 'opacity .12s',
  });
  tip.textContent = t;
  // Inside a [data-tip-anchor] (the mobile tab bar) the caption clears the whole container, not just the tab.
  const box = el.closest('[data-tip-anchor]');
  const r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
  const x = Math.max(6, Math.min(innerWidth - w - 6, r.left + r.width / 2 - w / 2));
  let y = box ? box.getBoundingClientRect().top - h - 10 : r.top - h - 8;
  if (y < 6) y = r.bottom + 8;
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}
```
**Impact:** Every existing tip in Seer is a short label (at most 48 characters, no `\n`), so they render exactly as before. The demo-data tip in `AppHeader.tsx:20` ("Sample data until the engine runs. Do not trade it.", 51 characters) now wraps into a box instead of one long pill. That is intended.

### Step 5: Chart geometry (pure)
**File:** `web/components/sera/charts/scale.ts:1` (create)
**Change:** Scales, nice ticks, year ticks, path builders (line, area, step), label de-overlap, width estimate, truncation and tick formatters. No React, no DOM.
**Code:**
```ts
// Pure geometry for Sera's hand-built SVG charts: scales, ticks, path builders, label layout and
// tick formatters. No React, no DOM, no snapshot import, so it is unit-tested under plain vitest.

export type Domain = readonly [number, number];
export type Pt = readonly [number, number];
export type Tick = { value: number; label: string };
/** A line across the plot at one value: a gate threshold, zero, SPY. */
export type RefLine = { value: number; label?: string; color?: string; dash?: string; tip?: string };
/** A target tick count, or an explicit list of ticks (then no formatter is needed). */
export type TickSpec = number | readonly Tick[];
export type Format = (v: number) => string;

/** Colour cycle for series that do not set their own. Seer v2 tokens only. */
export const CHART_COLORS = ['var(--ink)', 'var(--line-b)', 'var(--line-c)', 'var(--coral)', 'var(--pos)', 'var(--ink-3)'] as const;

export function colorAt(i: number): string {
  const n = CHART_COLORS.length;
  return CHART_COLORS[((i % n) + n) % n];
}

export const isNum = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v);

/** `v` held inside [a, b], whichever order a and b come in. */
export function clamp(v: number, a: number, b: number): number {
  const lo = Math.min(a, b);
  const hi = Math.max(a, b);
  return Math.min(hi, Math.max(lo, v));
}

/** Linear map from `domain` onto `range`. A zero-width domain maps everything to the middle of the range. */
export function linear(domain: Domain, range: Domain): (v: number) => number {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  if (d1 === d0) {
    const mid = (r0 + r1) / 2;
    return () => mid;
  }
  const k = (r1 - r0) / (d1 - d0);
  return v => r0 + (v - d0) * k;
}

/** [min, max] of the finite values plus `include`. Empty: [0, 1]. A single value is padded by 10% (or 1 at zero). */
export function extent(values: Iterable<number | null | undefined>, include: readonly number[] = []): Domain {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (!isNum(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  for (const v of include) {
    if (!isNum(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (lo === Infinity) return [0, 1];
  if (lo === hi) {
    const pad = lo === 0 ? 1 : Math.abs(lo) * 0.1;
    return [lo - pad, hi + pad];
  }
  return [lo, hi];
}

/** A 1, 2, 2.5 or 5 × 10^k step that cuts `span` into about `count` intervals. */
export function niceStep(span: number, count: number): number {
  if (!(span > 0) || !Number.isFinite(span)) return 1;
  const raw = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
  return nice * mag;
}

function tidy(v: number, step: number): number {
  const digits = Math.min(12, Math.max(0, 2 - Math.floor(Math.log10(step))));
  return Number(v.toFixed(digits)) || 0;
}

/** Ticks on a nice step; the first is <= min and the last is >= max. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (!isNum(min) || !isNum(max)) return [];
  if (min === max) return [min];
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  const step = niceStep(hi - lo, count);
  const first = Math.floor(lo / step + 1e-9);
  const last = Math.ceil(hi / step - 1e-9);
  const out: number[] = [];
  for (let i = first; i <= last; i++) out.push(tidy(i * step, step));
  return out;
}

/** Nice ticks that fall inside `domain` (the domain itself is kept as given). */
export function ticksWithin(domain: Domain, count = 5): number[] {
  const lo = Math.min(domain[0], domain[1]);
  const hi = Math.max(domain[0], domain[1]);
  const eps = (hi - lo) * 1e-9;
  return niceTicks(lo, hi, count).filter(t => t >= lo - eps && t <= hi + eps);
}

/** [min, max] widened out to the nice ticks around it. */
export function niceDomain(min: number, max: number, count = 5): Domain {
  const t = niceTicks(min, max, count);
  return t.length >= 2 ? [t[0], t[t.length - 1]] : extent([min, max]);
}

/**
 * One value axis. Explicit ticks win (the domain then covers them and `raw`). Otherwise nice ticks:
 * inside `domain` when one is given, or over `raw` with the domain widened to the outer ticks.
 */
export function resolveAxis(
  raw: Domain,
  opts: { domain?: Domain; ticks?: TickSpec; format: Format; count: number },
): { domain: Domain; ticks: Tick[] } {
  const spec = opts.ticks;
  if (spec !== undefined && typeof spec !== 'number') {
    const ticks = [...spec];
    return { domain: opts.domain ?? extent(ticks.map(t => t.value), [raw[0], raw[1]]), ticks };
  }
  const count = spec ?? opts.count;
  if (opts.domain) {
    return { domain: opts.domain, ticks: ticksWithin(opts.domain, count).map(v => ({ value: v, label: opts.format(v) })) };
  }
  const vals = niceTicks(raw[0], raw[1], count);
  const domain: Domain = vals.length >= 2 ? [vals[0], vals[vals.length - 1]] : raw;
  return { domain, ticks: vals.map(v => ({ value: v, label: opts.format(v) })) };
}

/** '1993-01-29' (UTC midnight) or a full ISO timestamp -> epoch ms. */
export function dateNum(iso: string): number {
  return Date.parse(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
}

const MONTH_YEAR = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', year: 'numeric' });

/**
 * Jan-1 ticks every 1, 2, 5, 10… years so there are at most `maxTicks`, inside [min, max] (epoch ms).
 * A window too short for two year marks gets its two ends instead ('Oct 2015', 'Mar 2016').
 */
export function yearTicks(min: number, max: number, maxTicks = 12): Tick[] {
  if (!isNum(min) || !isNum(max) || max <= min) return [];
  const y0 = new Date(min).getUTCFullYear();
  const y1 = new Date(max).getUTCFullYear();
  const years = y1 - y0 + 1;
  const step = [1, 2, 5, 10, 20, 50, 100].find(st => Math.ceil(years / st) <= maxTicks) ?? 100;
  const out: Tick[] = [];
  for (let y = Math.ceil(y0 / step) * step; y <= y1; y += step) {
    const v = Date.UTC(y, 0, 1);
    if (v >= min && v <= max) out.push({ value: v, label: String(y) });
  }
  if (out.length >= 2) return out;
  return [
    { value: min, label: MONTH_YEAR.format(new Date(min)) },
    { value: max, label: MONTH_YEAR.format(new Date(max)) },
  ];
}

const r1 = (v: number) => Math.round(v * 10) / 10 || 0;

/** SVG path through the points; a null (or non-finite) point lifts the pen. Coordinates to 0.1. */
export function linePath(points: ReadonlyArray<Pt | null>): string {
  let d = '';
  let pen = false;
  for (const p of points) {
    if (!p || !isNum(p[0]) || !isNum(p[1])) {
      pen = false;
      continue;
    }
    d += `${pen ? 'L' : 'M'}${r1(p[0])} ${r1(p[1])}`;
    pen = true;
  }
  return d;
}

/** Closed area between each unbroken run of points and the horizontal line y = baseY. */
export function areaPath(points: ReadonlyArray<Pt | null>, baseY: number): string {
  let d = '';
  let run: Pt[] = [];
  const flush = () => {
    if (run.length > 1) {
      d += `M${r1(run[0][0])} ${r1(baseY)}`;
      for (const p of run) d += `L${r1(p[0])} ${r1(p[1])}`;
      d += `L${r1(run[run.length - 1][0])} ${r1(baseY)}Z`;
    }
    run = [];
  };
  for (const p of points) {
    if (p && isNum(p[0]) && isNum(p[1])) run.push(p);
    else flush();
  }
  flush();
  return d;
}

/** Step-after: holds each value flat until the next x (for "best so far" lines). Nulls still break the line. */
export function stepPoints(points: ReadonlyArray<Pt | null>): Array<Pt | null> {
  const out: Array<Pt | null> = [];
  let prev: Pt | null = null;
  for (const p of points) {
    if (p && prev) out.push([p[0], prev[1]]);
    out.push(p);
    prev = p;
  }
  return out;
}

/** Moves label positions apart to at least `gap`, inside [lo, hi], keeping their order. Returned in input order. */
export function spread(values: readonly number[], gap: number, lo = -Infinity, hi = Infinity): number[] {
  const order = values.map((_, i) => i).sort((a, b) => values[a] - values[b]);
  const pos = order.map(i => values[i]);
  for (let k = 0; k < pos.length; k++) pos[k] = Math.max(pos[k], lo, k ? pos[k - 1] + gap : -Infinity);
  for (let k = pos.length - 1; k >= 0; k--) pos[k] = Math.min(pos[k], hi, k < pos.length - 1 ? pos[k + 1] - gap : Infinity);
  const out = new Array<number>(values.length);
  order.forEach((i, k) => {
    out[i] = pos[k];
  });
  return out;
}

/** Rough rendered width of `text` in Outfit at `size` user units (for margins, not layout-critical). */
export const textWidth = (text: string, size = 13) => text.length * size * 0.56;

/** `text` cut to at most `max` characters with an ellipsis. */
export function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, Math.max(1, max - 1)).trimEnd()}…`;
}

// ---- Tick formatters (factories, so a page writes yFormat={fmtPct(0)}) -------------------------

const MINUS = '−';
const signFor = (v: number, shown: string, plus: boolean) => (Number(shown) === 0 ? '' : v < 0 ? MINUS : plus ? '+' : '');

/** 0.153 -> '15%', -0.153 -> '−15%'. */
export const fmtPct = (digits = 0): Format => v => {
  const shown = (Math.abs(v) * 100).toFixed(digits);
  return `${signFor(v, shown, false)}${shown}%`;
};
/** 0.0123 -> '+1.2%' with digits 1. */
export const fmtSignedPct = (digits = 0): Format => v => {
  const shown = (Math.abs(v) * 100).toFixed(digits);
  return `${signFor(v, shown, true)}${shown}%`;
};
/** -3 -> '−3'. */
export const fmtNumber = (digits = 0): Format => v => {
  const shown = Math.abs(v).toFixed(digits);
  return `${signFor(v, shown, false)}${shown}`;
};
/** 2.5 -> '2.5×' (growth of 1). */
export const fmtMultiple = (digits = 1): Format => v => `${v.toFixed(digits)}×`;
```

**File:** `web/components/sera/charts/scale.test.ts:1` (create)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import {
  areaPath, clamp, colorAt, dateNum, extent, fmtMultiple, fmtNumber, fmtPct, fmtSignedPct, isNum, linePath,
  linear, niceDomain, niceStep, niceTicks, resolveAxis, spread, stepPoints, textWidth, ticksWithin, truncate,
  yearTicks,
} from './scale';

describe('linear', () => {
  it('maps the domain onto the range, inverted ranges included', () => {
    const f = linear([0, 10], [100, 0]);
    expect(f(0)).toBe(100);
    expect(f(5)).toBe(50);
    expect(f(10)).toBe(0);
  });
  it('maps a zero-width domain to the middle of the range', () => {
    expect(linear([3, 3], [0, 100])(3)).toBe(50);
  });
});

describe('clamp and isNum', () => {
  it('clamps whichever order the bounds come in', () => {
    expect(clamp(5, 0, 3)).toBe(3);
    expect(clamp(5, 3, 0)).toBe(3);
    expect(clamp(-1, 0, 3)).toBe(0);
  });
  it('accepts finite numbers only', () => {
    expect(isNum(0)).toBe(true);
    expect(isNum(null)).toBe(false);
    expect(isNum(undefined)).toBe(false);
    expect(isNum(NaN)).toBe(false);
    expect(isNum(Infinity)).toBe(false);
  });
});

describe('extent', () => {
  it('ignores null and non-finite values and honours include', () => {
    expect(extent([3, null, -1, NaN, Infinity, 2])).toEqual([-1, 3]);
    expect(extent([0.1, 0.2], [0])).toEqual([0, 0.2]);
  });
  it('pads a single value and defaults an empty set', () => {
    expect(extent([5])).toEqual([4.5, 5.5]);
    expect(extent([0])).toEqual([-1, 1]);
    expect(extent([])).toEqual([0, 1]);
  });
});

describe('nice ticks', () => {
  it('picks 1, 2, 2.5 or 5 steps', () => {
    expect(niceStep(1, 5)).toBeCloseTo(0.2);
    expect(niceStep(23, 5)).toBe(5);
    expect(niceStep(0.49, 5)).toBeCloseTo(0.1);
    expect(niceStep(0, 5)).toBe(1);
  });
  it('covers the range with clean values', () => {
    expect(niceTicks(0, 1, 5)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1]);
    expect(niceTicks(-0.37, 0.12, 5)).toEqual([-0.4, -0.3, -0.2, -0.1, 0, 0.1, 0.2]);
    expect(niceTicks(5, 5)).toEqual([5]);
    expect(niceTicks(NaN, 1)).toEqual([]);
  });
  it('keeps a given domain or widens to the ticks', () => {
    expect(ticksWithin([0.05, 0.95], 5)).toEqual([0.2, 0.4, 0.6, 0.8]);
    expect(niceDomain(0.03, 0.97)).toEqual([0, 1]);
  });
});

describe('resolveAxis', () => {
  const pct = fmtPct(0);
  it('widens the raw extent to nice ticks and labels them', () => {
    const a = resolveAxis([0.03, 0.97], { format: pct, count: 5 });
    expect(a.domain).toEqual([0, 1]);
    expect(a.ticks.map(t => t.label)).toEqual(['0%', '20%', '40%', '60%', '80%', '100%']);
  });
  it('keeps a given domain', () => {
    const a = resolveAxis([0, 1], { domain: [0.05, 0.95], format: pct, count: 5 });
    expect(a.domain).toEqual([0.05, 0.95]);
    expect(a.ticks.map(t => t.value)).toEqual([0.2, 0.4, 0.6, 0.8]);
  });
  it('takes explicit ticks as they are', () => {
    const a = resolveAxis([0.1, 0.9], { ticks: [{ value: 0, label: 'none' }, { value: 1, label: 'all' }], format: pct, count: 5 });
    expect(a.domain).toEqual([0, 1]);
    expect(a.ticks.map(t => t.label)).toEqual(['none', 'all']);
  });
});

describe('dates', () => {
  it('reads ISO dates as UTC', () => {
    expect(dateNum('2000-01-01')).toBe(Date.UTC(2000, 0, 1));
  });
  it('marks years every 2 across the dev window', () => {
    const t = yearTicks(dateNum('1993-01-29'), dateNum('2015-10-16'));
    expect(t.length).toBe(11);
    expect(t[0]).toEqual({ value: Date.UTC(1994, 0, 1), label: '1994' });
    expect(t[t.length - 1].label).toBe('2014');
  });
  it('marks every year when they fit', () => {
    expect(yearTicks(dateNum('2015-10-19'), dateNum('2026-10-02')).map(t => t.label)).toEqual(
      ['2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026'],
    );
  });
  it('labels the two ends of a short window', () => {
    expect(yearTicks(dateNum('2015-10-19'), dateNum('2016-03-31')).map(t => t.label)).toEqual(['Oct 2015', 'Mar 2016']);
    expect(yearTicks(5, 5)).toEqual([]);
  });
});

describe('paths', () => {
  it('rounds to 0.1 and lifts the pen at nulls', () => {
    expect(linePath([[0, 0], [10.04, 5.26]])).toBe('M0 0L10 5.3');
    expect(linePath([[0, 0], null, [5, 5], [6, 6]])).toBe('M0 0M5 5L6 6');
    expect(linePath([])).toBe('');
  });
  it('closes areas down to the baseline per unbroken run', () => {
    expect(areaPath([[0, 5], [10, 2]], 10)).toBe('M0 10L0 5L10 2L10 10Z');
    expect(areaPath([[0, 5]], 10)).toBe('');
    expect(areaPath([[0, 5], [1, 4], null, [3, 3], [4, 2]], 10)).toBe('M0 10L0 5L1 4L1 10ZM3 10L3 3L4 2L4 10Z');
  });
  it('holds values flat until the next x for step lines', () => {
    expect(stepPoints([[0, 1], [2, 3]])).toEqual([[0, 1], [2, 1], [2, 3]]);
    expect(stepPoints([[0, 1], null, [2, 3]])).toEqual([[0, 1], null, [2, 3]]);
  });
});

describe('label layout', () => {
  it('spreads close labels apart, keeping input order', () => {
    expect(spread([10, 12, 50], 8)).toEqual([10, 18, 50]);
    expect(spread([100, 98], 8, 0, 100)).toEqual([100, 92]);
  });
  it('estimates width and truncates', () => {
    expect(textWidth('abcd', 10)).toBeCloseTo(22.4);
    expect(truncate('abcdef', 4)).toBe('abc…');
    expect(truncate('abc', 4)).toBe('abc');
  });
  it('cycles the series colours', () => {
    expect(colorAt(0)).toBe('var(--ink)');
    expect(colorAt(6)).toBe('var(--ink)');
    expect(colorAt(1)).toBe('var(--line-b)');
  });
});

describe('formatters', () => {
  it('formats percents with a true minus and no negative zero', () => {
    expect(fmtPct(0)(-0.153)).toBe('−15%');
    expect(fmtPct(0)(-0.001)).toBe('0%');
    expect(fmtSignedPct(1)(0.0123)).toBe('+1.2%');
    expect(fmtSignedPct(1)(0)).toBe('0.0%');
  });
  it('formats numbers and multiples', () => {
    expect(fmtNumber(0)(-3)).toBe('−3');
    expect(fmtNumber(2)(1.234)).toBe('1.23');
    expect(fmtMultiple(1)(2.5)).toBe('2.5×');
  });
});
```
**Impact:** none (new).

### Step 6: Chart styles and reference lines
**File:** `web/components/sera/charts/charts.module.css:1` (create)
**Code:**
```css
/* Sera chart kit. Colours are Seer v2 tokens. --chart-halo (set by Section to its background) rings
   labels and points so they stay legible where they cross lines. */
.figure { margin: 0; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.legendSlot { display: flex; justify-content: flex-end; }
.svg { display: block; width: 100%; height: auto; overflow: visible; font-family: inherit; }

.grid { stroke: var(--hair); stroke-width: 1; }
.axisLine { stroke: var(--outline); stroke-width: 1.25; }
.tick { fill: var(--ink-2); font-size: 13px; font-variant-numeric: tabular-nums; }
.axisTitle { fill: var(--ink-3); font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; }
.empty { fill: var(--ink-3); font-size: 16px; }

.refLabel, .endLabel, .pointLabel, .valueLabel, .regionLabel {
  paint-order: stroke;
  stroke: var(--chart-halo, var(--sheet));
  stroke-width: 4px;
  stroke-linejoin: round;
}
.refLabel { font-size: 12.5px; font-weight: 500; }
.endLabel { font-size: 13px; font-weight: 500; }
.pointLabel { fill: var(--ink); font-size: 12.5px; font-weight: 500; }
.valueLabel { fill: var(--ink); font-size: 13px; font-variant-numeric: tabular-nums; }
.regionLabel { fill: var(--ink-2); font-size: 13px; font-weight: 500; letter-spacing: 0.02em; }
.barLabel { fill: var(--ink); font-size: 14px; }

/* Invisible wide strokes that carry a line's data-tip. */
.hit { fill: none; stroke: transparent; stroke-width: 14px; pointer-events: stroke; }
.hitLine { stroke: transparent; stroke-width: 12px; pointer-events: stroke; }

.dot { stroke: var(--chart-halo, var(--sheet)); stroke-width: 1.5px; }
.point { transition: stroke-width 0.12s; }
.point:hover, .link:focus-visible .point { stroke: var(--ink) !important; stroke-width: 2.5px !important; }
.bar { transition: opacity 0.12s; }
.bar:hover, .link:focus-visible .bar { opacity: 0.78; }
.link { cursor: pointer; }
.link:focus-visible { outline: none; }

.legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  font-size: 14px;
  color: var(--ink);
}
.legendItem { display: inline-flex; align-items: center; gap: 8px; white-space: nowrap; }
.legendItem[data-tip] { cursor: help; }
.swatch { flex: none; display: inline-block; }
.sw_line { width: 18px; height: 3px; border-radius: 9px; }
.sw_dash { width: 18px; height: 0; border-top: 2.5px dashed; }
.sw_dot { width: 10px; height: 10px; border-radius: 999px; }
.sw_ring { width: 11px; height: 11px; border-radius: 999px; border: 2px solid; }
.sw_zone { width: 16px; height: 12px; border-radius: 4px; }
```

**File:** `web/components/sera/charts/parts.tsx:1` (create)
**Code:**
```tsx
import s from './charts.module.css';
import { type RefLine, textWidth } from './scale';

/** A horizontal reference line across the plot, label at its right end. */
export function HRef({ r, y, x1, x2 }: { r: RefLine; y: number; x1: number; x2: number }) {
  const color = r.color ?? 'var(--ink-2)';
  return (
    <g>
      <line x1={x1} x2={x2} y1={y} y2={y} style={{ stroke: color }} strokeWidth={1.25} strokeDasharray={r.dash ?? '6 5'} />
      <line x1={x1} x2={x2} y1={y} y2={y} className={s.hitLine} data-tip={r.tip ?? r.label} />
      {r.label ? (
        <text x={x2 - 4} y={y - 7} textAnchor="end" className={s.refLabel} style={{ fill: color }}>
          {r.label}
        </text>
      ) : null}
    </g>
  );
}

/** A vertical reference line, label at its top; the label flips left when it would cross `right`. */
export function VRef({ r, x, y1, y2, right }: { r: RefLine; x: number; y1: number; y2: number; right: number }) {
  const color = r.color ?? 'var(--ink-2)';
  const flip = r.label ? x + 7 + textWidth(r.label, 12.5) > right : false;
  return (
    <g>
      <line x1={x} x2={x} y1={y1} y2={y2} style={{ stroke: color }} strokeWidth={1.25} strokeDasharray={r.dash ?? '6 5'} />
      <line x1={x} x2={x} y1={y1} y2={y2} className={s.hitLine} data-tip={r.tip ?? r.label} />
      {r.label ? (
        <text x={flip ? x - 7 : x + 7} y={y1 + 14} textAnchor={flip ? 'end' : 'start'} className={s.refLabel} style={{ fill: color }}>
          {r.label}
        </text>
      ) : null}
    </g>
  );
}
```
**Impact:** none (new).

### Step 7: LineChart
**File:** `web/components/sera/charts/LineChart.tsx:1` (create)
**Change:** The chart takes several series:
- x is ISO dates (year ticks) or numbers.
- Each series can set its colour, width and dash, fill an area to zero (underwater), draw as a step line ("best so far"), show dots with per-point tips, and print an end label (collisions are spread apart).
- Horizontal reference lines carry labels, and there is a legend slot.
- An empty input renders "No data yet".

For the method page (Phase 5), the uses are:
- **Growth of 1:** each variant's `curve` plus the rebased SPY, `{ dash: '1 5', color: 'var(--ink-3)' }`, with `yFormat={fmtMultiple(1)}` and `refLines={[{ value: 1, label: 'Start' }]}`.
- **Drawdown:** `{ area: true, color: 'var(--neg)' }` with `yFormat={fmtPct(0)}` and `includeZero`.
**Code:**
```tsx
import type { ReactNode } from 'react';
import s from './charts.module.css';
import { HRef } from './parts';
import {
  type Domain, type Format, type Pt, type RefLine, type Tick, type TickSpec,
  areaPath, clamp, colorAt, dateNum, extent, fmtNumber, isNum, linePath, linear, resolveAxis, spread, stepPoints,
  textWidth, yearTicks,
} from './scale';

export type XValue = string | number;
/** [x, y, tip?]. x is an ISO date ('1993-01-29') or a number (a trial number). A null y breaks the line. */
export type LinePoint = readonly [x: XValue, y: number | null, tip?: string];

export type LineSeries = {
  id: string;
  label: string;
  points: readonly LinePoint[];
  /** CSS colour, normally a token: 'var(--coral)'. Default: CHART_COLORS by series index. */
  color?: string;
  /** Stroke width in viewBox units. Default 2.25. */
  width?: number;
  /** stroke-dasharray, e.g. '1 5' dotted (SPY, as on the Leaderboard) or '6 4' dashed. */
  dash?: string;
  opacity?: number;
  /** Fill between the line and y = 0 (drawdown / underwater charts). */
  area?: boolean;
  /** Default 0.16. */
  areaOpacity?: number;
  /** Step-after line: each value holds flat until the next x ("best so far"). */
  step?: boolean;
  /** Draw a dot at every point; each dot's data-tip is the point's tip, else the series tip, else its label. */
  dots?: boolean;
  /** Tooltip on the line. Default: label. */
  tip?: string;
  /** Print the label at the right end of the line (collisions are spread apart). */
  endLabel?: boolean;
};

export type LineChartProps = {
  series: readonly LineSeries[];
  /** Required: the chart is role="img". */
  ariaLabel: string;
  /** Default: 'date' when the first x is a string, else 'number'. */
  x?: 'date' | 'number';
  /** Epoch ms in date mode. Default: the data's extent. */
  xDomain?: Domain;
  /** Default: the data's extent (plus 0 when includeZero, plus refLines), widened to nice ticks. */
  yDomain?: Domain;
  includeZero?: boolean;
  /** Number-mode x labels. Default fmtNumber(0). */
  xFormat?: Format;
  /** Default fmtNumber(0). Use fmtPct(0), fmtMultiple(1)… from ./scale. */
  yFormat?: Format;
  /** Date mode: a number is the max year ticks (default 12). Number mode: target count (default 8). Or explicit ticks. */
  xTicks?: TickSpec;
  /** Target count (default 5) or explicit ticks. */
  yTicks?: TickSpec;
  refLines?: readonly RefLine[];
  xLabel?: string;
  yLabel?: string;
  /** Rendered above the plot, right-aligned (usually <Legend items={legendFromSeries(series)} />). */
  legend?: ReactNode;
  /** viewBox size. Default 960 × 360. */
  width?: number;
  height?: number;
  /** Default 'xMidYMid meet' (text keeps its proportions). */
  preserveAspectRatio?: string;
  className?: string;
};

/** Multi-series line chart: hand-built SVG, server-rendered, year ticks on date axes. */
export function LineChart(props: LineChartProps) {
  const { series, ariaLabel, refLines = [], legend, className } = props;
  const W = props.width ?? 960;
  const H = props.height ?? 360;
  const firstX = series.find(se => se.points.length > 0)?.points[0][0];
  const mode = props.x ?? (typeof firstX === 'string' ? 'date' : 'number');
  const toX = (v: XValue) => (typeof v === 'string' ? dateNum(v) : v);
  const raw = series.map(se => se.points.map(p => [toX(p[0]), p[1]] as const));
  const xsAll = raw.flatMap(r => r.filter(q => isNum(q[1])).map(q => q[0]));
  const ysAll = raw.flatMap(r => r.map(q => q[1]));
  const empty = !raw.some(r => r.some(q => isNum(q[0]) && isNum(q[1])));

  const y = resolveAxis(extent(ysAll, [...(props.includeZero ? [0] : []), ...refLines.map(r => r.value)]), {
    domain: props.yDomain,
    ticks: props.yTicks,
    format: props.yFormat ?? fmtNumber(0),
    count: 5,
  });
  const xDom: Domain = props.xDomain ?? extent(xsAll);
  let xTicks: Tick[];
  if (props.xTicks !== undefined && typeof props.xTicks !== 'number') xTicks = [...props.xTicks];
  else if (mode === 'date') xTicks = yearTicks(xDom[0], xDom[1], props.xTicks ?? 12);
  else xTicks = resolveAxis(xDom, { domain: xDom, ticks: props.xTicks, format: props.xFormat ?? fmtNumber(0), count: 8 }).ticks;

  const ends = series.flatMap((se, i) => (se.endLabel ? [i] : []));
  const m = {
    top: 18,
    right: 20 + (ends.length ? Math.max(...ends.map(i => textWidth(series[i].label))) + 14 : 0),
    bottom: 34 + (props.xLabel ? 24 : 0),
    left: 14 + Math.max(16, ...y.ticks.map(t => textWidth(t.label))) + (props.yLabel ? 26 : 0),
  };
  const sx = linear(xDom, [m.left, W - m.right]);
  const sy = linear(y.domain, [H - m.bottom, m.top]);
  const baseY = sy(clamp(0, y.domain[0], y.domain[1]));

  const drawn = series.map((se, i) => {
    const xy: Array<Pt | null> = raw[i].map(([xv, yv]) => (isNum(xv) && isNum(yv) ? ([sx(xv), sy(yv)] as const) : null));
    const path = se.step ? stepPoints(xy) : xy;
    let last: Pt | null = null;
    for (const q of xy) if (q) last = q;
    return { se, xy, last, color: se.color ?? colorAt(i), d: linePath(path), area: se.area ? areaPath(path, baseY) : '' };
  });
  const endY = spread(ends.map(i => drawn[i].last?.[1] ?? baseY), 16, m.top, H - m.bottom);
  const inX = (v: number) => v >= Math.min(...xDom) && v <= Math.max(...xDom);

  return (
    <figure className={`${s.figure} ${className ?? ''}`}>
      {legend ? <div className={s.legendSlot}>{legend}</div> : null}
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio={props.preserveAspectRatio ?? 'xMidYMid meet'}
        className={s.svg} role="img" aria-label={ariaLabel}>
        {y.ticks.map(t => (
          <g key={`y${t.value}`}>
            <line x1={m.left} x2={W - m.right} y1={sy(t.value)} y2={sy(t.value)} className={s.grid} />
            <text x={m.left - 10} y={sy(t.value)} dy="0.35em" textAnchor="end" className={s.tick}>{t.label}</text>
          </g>
        ))}
        {xTicks.filter(t => inX(t.value)).map(t => (
          <text key={`x${t.value}`} x={sx(t.value)} y={H - m.bottom + 22} textAnchor="middle" className={s.tick}>{t.label}</text>
        ))}
        <line x1={m.left} x2={W - m.right} y1={H - m.bottom} y2={H - m.bottom} className={s.axisLine} />
        {drawn.map(({ se, color, area }) =>
          area ? <path key={`a${se.id}`} d={area} style={{ fill: color, opacity: se.areaOpacity ?? 0.16 }} /> : null,
        )}
        {refLines.map((r, i) => <HRef key={`r${i}`} r={r} y={sy(r.value)} x1={m.left} x2={W - m.right} />)}
        {drawn.map(({ se, color, d }) =>
          d ? (
            <g key={`l${se.id}`}>
              <path d={d} fill="none" style={{ stroke: color, opacity: se.opacity }} strokeWidth={se.width ?? 2.25}
                strokeDasharray={se.dash} strokeLinecap="round" strokeLinejoin="round" />
              <path d={d} className={s.hit} data-tip={se.tip ?? se.label} />
            </g>
          ) : null,
        )}
        {drawn.map(({ se, xy, color }) =>
          se.dots
            ? xy.map((q, j) =>
                q ? (
                  <circle key={`d${se.id}-${j}`} cx={q[0]} cy={q[1]} r={3.5} className={s.dot} style={{ fill: color }}
                    data-tip={se.points[j][2] ?? se.tip ?? se.label} />
                ) : null,
              )
            : null,
        )}
        {ends.map((i, k) =>
          drawn[i].last ? (
            <text key={`e${series[i].id}`} x={W - m.right + 10} y={endY[k]} dy="0.35em" className={s.endLabel}
              style={{ fill: drawn[i].color }}>
              {series[i].label}
            </text>
          ) : null,
        )}
        {props.xLabel ? (
          <text x={(m.left + W - m.right) / 2} y={H - 6} textAnchor="middle" className={s.axisTitle}>{props.xLabel}</text>
        ) : null}
        {props.yLabel ? (
          <text transform={`translate(14 ${(m.top + H - m.bottom) / 2}) rotate(-90)`} textAnchor="middle" className={s.axisTitle}>
            {props.yLabel}
          </text>
        ) : null}
        {empty ? <text x={W / 2} y={H / 2} textAnchor="middle" className={s.empty}>No data yet</text> : null}
      </svg>
    </figure>
  );
}
```
**Impact:** none (new).

### Step 8: ScatterChart
**File:** `web/components/sera/charts/ScatterChart.tsx:1` (create)
**Change:** The chart draws:
- points with colour, radius, a hollow `ring` option, a `data-tip`, an optional `href` (an SVG `<a>`, so a full navigation) and an optional label
- shaded rectangular regions with labels; a missing bound runs to the plot edge
- vertical and horizontal reference lines
- axis titles and formatters

Points with a null coordinate are skipped.

For the Overview's pass zone, use `regions={[{ x1: gate.maxDrawdown, y0: 0, label: 'Pass zone' }]}` with x = max drawdown and y = CAGR minus SPY's. The threshold comes from `snapshot.gate` (invariant 5), not from a literal.
**Code:**
```tsx
import type { ReactNode } from 'react';
import s from './charts.module.css';
import { HRef, VRef } from './parts';
import { type Domain, type Format, type RefLine, type TickSpec, clamp, extent, fmtNumber, isNum, linear, resolveAxis, textWidth } from './scale';

export type ScatterPoint = {
  /** Unique within the chart (React key). */
  id: string;
  /** A null coordinate skips the point. */
  x: number | null;
  y: number | null;
  /** Default 'var(--ink)'. */
  color?: string;
  /** Radius in viewBox units. Default 6. */
  r?: number;
  /** Hollow point (outline only). */
  ring?: boolean;
  /** Tooltip; '\n' breaks lines. */
  tip?: string;
  /** Makes the point a link (e.g. '/sera/methods/M0001'). */
  href?: string;
  /** Text printed beside the point. */
  label?: string;
};

/** A shaded rectangle in data units. A null or missing bound runs to the plot edge. */
export type ScatterRegion = {
  x0?: number | null;
  x1?: number | null;
  y0?: number | null;
  y1?: number | null;
  /** Printed in the region's top-left corner (e.g. 'Pass zone'). */
  label?: string;
  /** Default 'var(--sky)'. */
  color?: string;
  /** Default 1 (the pale tokens are already soft). */
  opacity?: number;
  tip?: string;
};

export type ScatterChartProps = {
  points: readonly ScatterPoint[];
  ariaLabel: string;
  regions?: readonly ScatterRegion[];
  /** Vertical lines at x values. */
  refX?: readonly RefLine[];
  /** Horizontal lines at y values. */
  refY?: readonly RefLine[];
  /** Default: points + finite region bounds + ref lines, widened to nice ticks. */
  xDomain?: Domain;
  yDomain?: Domain;
  includeZeroX?: boolean;
  includeZeroY?: boolean;
  /** Default fmtNumber(1). */
  xFormat?: Format;
  yFormat?: Format;
  /** Target count (x default 8, y default 6) or explicit ticks. */
  xTicks?: TickSpec;
  yTicks?: TickSpec;
  xLabel?: string;
  yLabel?: string;
  legend?: ReactNode;
  /** viewBox size. Default 960 × 440. */
  width?: number;
  height?: number;
  preserveAspectRatio?: string;
  className?: string;
};

/** Scatter plot with shaded regions (the pass zone), reference lines, tooltips and link-able points. */
export function ScatterChart(props: ScatterChartProps) {
  const { points, ariaLabel, regions = [], refX = [], refY = [], legend, className } = props;
  const W = props.width ?? 960;
  const H = props.height ?? 440;
  const live = points.filter((p): p is ScatterPoint & { x: number; y: number } => isNum(p.x) && isNum(p.y));
  const finite = (vs: ReadonlyArray<number | null | undefined>) => vs.filter(isNum);

  const xAxis = resolveAxis(
    extent(live.map(p => p.x), [...(props.includeZeroX ? [0] : []), ...refX.map(r => r.value), ...finite(regions.flatMap(r => [r.x0, r.x1]))]),
    { domain: props.xDomain, ticks: props.xTicks, format: props.xFormat ?? fmtNumber(1), count: 8 },
  );
  const yAxis = resolveAxis(
    extent(live.map(p => p.y), [...(props.includeZeroY ? [0] : []), ...refY.map(r => r.value), ...finite(regions.flatMap(r => [r.y0, r.y1]))]),
    { domain: props.yDomain, ticks: props.yTicks, format: props.yFormat ?? fmtNumber(1), count: 6 },
  );
  const m = {
    top: 16,
    right: 24,
    bottom: 36 + (props.xLabel ? 24 : 0),
    left: 14 + Math.max(16, ...yAxis.ticks.map(t => textWidth(t.label))) + (props.yLabel ? 26 : 0),
  };
  const sx = linear(xAxis.domain, [m.left, W - m.right]);
  const sy = linear(yAxis.domain, [H - m.bottom, m.top]);
  const ex = (v: number | null | undefined, edge: number) => (isNum(v) ? sx(clamp(v, xAxis.domain[0], xAxis.domain[1])) : edge);
  const ey = (v: number | null | undefined, edge: number) => (isNum(v) ? sy(clamp(v, yAxis.domain[0], yAxis.domain[1])) : edge);
  const inX = (v: number) => v >= Math.min(...xAxis.domain) && v <= Math.max(...xAxis.domain);
  const inY = (v: number) => v >= Math.min(...yAxis.domain) && v <= Math.max(...yAxis.domain);

  return (
    <figure className={`${s.figure} ${className ?? ''}`}>
      {legend ? <div className={s.legendSlot}>{legend}</div> : null}
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio={props.preserveAspectRatio ?? 'xMidYMid meet'}
        className={s.svg} role="img" aria-label={ariaLabel}>
        {regions.map((r, i) => {
          const a = ex(r.x0, m.left);
          const b = ex(r.x1, W - m.right);
          const c = ey(r.y0, H - m.bottom);
          const d = ey(r.y1, m.top);
          const x = Math.min(a, b);
          const y = Math.min(c, d);
          return (
            <g key={`z${i}`}>
              <rect x={x} y={y} width={Math.abs(b - a)} height={Math.abs(d - c)} rx={10}
                style={{ fill: r.color ?? 'var(--sky)', opacity: r.opacity ?? 1 }} data-tip={r.tip} />
              {r.label ? <text x={x + 12} y={y + 22} className={s.regionLabel}>{r.label}</text> : null}
            </g>
          );
        })}
        {yAxis.ticks.filter(t => inY(t.value)).map(t => (
          <g key={`y${t.value}`}>
            <line x1={m.left} x2={W - m.right} y1={sy(t.value)} y2={sy(t.value)} className={s.grid} />
            <text x={m.left - 10} y={sy(t.value)} dy="0.35em" textAnchor="end" className={s.tick}>{t.label}</text>
          </g>
        ))}
        {xAxis.ticks.filter(t => inX(t.value)).map(t => (
          <g key={`x${t.value}`}>
            <line x1={sx(t.value)} x2={sx(t.value)} y1={m.top} y2={H - m.bottom} className={s.grid} />
            <text x={sx(t.value)} y={H - m.bottom + 22} textAnchor="middle" className={s.tick}>{t.label}</text>
          </g>
        ))}
        <line x1={m.left} x2={W - m.right} y1={H - m.bottom} y2={H - m.bottom} className={s.axisLine} />
        <line x1={m.left} x2={m.left} y1={m.top} y2={H - m.bottom} className={s.axisLine} />
        {refY.map((r, i) => <HRef key={`ry${i}`} r={r} y={sy(r.value)} x1={m.left} x2={W - m.right} />)}
        {refX.map((r, i) => <VRef key={`rx${i}`} r={r} x={sx(r.value)} y1={m.top} y2={H - m.bottom} right={W - m.right} />)}
        {live.map(p => {
          const color = p.color ?? 'var(--ink)';
          const cx = sx(p.x);
          const cy = sy(p.y);
          const radius = p.r ?? 6;
          const dot = (
            <circle cx={cx} cy={cy} r={radius} className={s.point} data-tip={p.tip}
              style={p.ring
                ? { fill: 'var(--chart-halo, var(--sheet))', stroke: color, strokeWidth: 2 }
                : { fill: color, stroke: 'var(--chart-halo, var(--sheet))', strokeWidth: 1.5 }} />
          );
          const label = p.label ? (
            <text x={cx + radius + 6} y={cy} dy="0.35em" className={s.pointLabel}>{p.label}</text>
          ) : null;
          return p.href ? (
            <a key={p.id} href={p.href} className={s.link} aria-label={p.tip ?? p.label ?? p.id}>{dot}{label}</a>
          ) : (
            <g key={p.id}>{dot}{label}</g>
          );
        })}
        {props.xLabel ? (
          <text x={(m.left + W - m.right) / 2} y={H - 6} textAnchor="middle" className={s.axisTitle}>{props.xLabel}</text>
        ) : null}
        {props.yLabel ? (
          <text transform={`translate(14 ${(m.top + H - m.bottom) / 2}) rotate(-90)`} textAnchor="middle" className={s.axisTitle}>
            {props.yLabel}
          </text>
        ) : null}
        {live.length === 0 ? <text x={W / 2} y={H / 2} textAnchor="middle" className={s.empty}>No data yet</text> : null}
      </svg>
    </figure>
  );
}
```
**Impact:** none (new).

### Step 9: BarChart and Legend
**File:** `web/components/sera/charts/BarChart.tsx:1` (create)
**Change:** The chart takes `groups`, each holding one or more `items`:
- Single bars come from `barGroups(...)`. The year-by-year chart uses two items per year (the method and SPY).
- Orientation is vertical or horizontal.
- `signed` colours by sign.
- Value labels default on for at most 16 single-bar groups.
- Reference value lines are supported.
- Each bar has its own `data-tip`, and a group can carry an `href`.
- In horizontal charts, category labels are truncated, with the full label in the tip, and the height fits the rows.
**Code:**
```tsx
import type { ReactNode } from 'react';
import s from './charts.module.css';
import { HRef, VRef } from './parts';
import { type Domain, type Format, type RefLine, type TickSpec, clamp, extent, fmtNumber, isNum, linear, resolveAxis, textWidth, truncate } from './scale';

/** One bar inside a group. */
export type BarItem = {
  /** Unique within its group (React key), e.g. 'method' / 'spy'. */
  key: string;
  /** null draws no bar ('—' when values are shown). */
  value: number | null;
  /** Overrides the signed / default colour. */
  color?: string;
  tip?: string;
  /** Printed value. Default: format(value). */
  valueText?: string;
};

/** One category: a year, a hurdle, a family. Several items side by side make a grouped bar. */
export type BarGroup = {
  id: string;
  label: string;
  items: readonly BarItem[];
  /** Makes the whole group a link. */
  href?: string;
  /** Tooltip on the category label (horizontal: defaults to the full label when it was truncated). */
  tip?: string;
};

/** The one-bar-per-category shape; turn it into groups with barGroups(). */
export type SimpleBar = {
  id: string;
  label: string;
  value: number | null;
  color?: string;
  tip?: string;
  href?: string;
  valueText?: string;
};

export function barGroups(bars: readonly SimpleBar[]): BarGroup[] {
  return bars.map(b => ({
    id: b.id,
    label: b.label,
    href: b.href,
    items: [{ key: b.id, value: b.value, color: b.color, tip: b.tip, valueText: b.valueText }],
  }));
}

export type BarChartProps = {
  groups: readonly BarGroup[];
  ariaLabel: string;
  /** 'vertical' (default): categories along x. 'horizontal': categories down the left. */
  orientation?: 'vertical' | 'horizontal';
  /** Colour bars by sign: --pos at or above zero, --neg below (unless an item sets color). */
  signed?: boolean;
  /** Colour when not signed. Default 'var(--ink)'. */
  color?: string;
  /** Value axis. Default: the values plus 0 plus refLines, widened to nice ticks. */
  domain?: Domain;
  /** Value and tick format. Default fmtNumber(0). */
  format?: Format;
  /** Target count (default 5) or explicit ticks. */
  ticks?: TickSpec;
  /** Print each bar's value. Default: true for one bar per group and at most 16 groups. */
  values?: boolean;
  /** Lines across the bars at a value (a target, SPY's figure). */
  refLines?: readonly RefLine[];
  /** Title of the value axis. */
  axisLabel?: string;
  legend?: ReactNode;
  /** viewBox width. Default 960. */
  width?: number;
  /** viewBox height. Vertical default 360. Horizontal default: fits the rows. */
  height?: number;
  /** Horizontal row height. Default 34 (one item) or 16 per item + 14. */
  rowHeight?: number;
  /** Horizontal category labels are cut to this many characters. Default 28. */
  maxLabelChars?: number;
  preserveAspectRatio?: string;
  className?: string;
};

/** Vertical or horizontal bars, single or grouped, optionally coloured by sign. */
export function BarChart(props: BarChartProps) {
  const { groups, ariaLabel, legend, className, refLines = [] } = props;
  const horizontal = props.orientation === 'horizontal';
  const W = props.width ?? 960;
  const fmt = props.format ?? fmtNumber(0);
  const n = groups.length;
  const k = Math.max(1, ...groups.map(g => g.items.length));
  const values = groups.flatMap(g => g.items.map(it => it.value)).filter(isNum);
  const axis = resolveAxis(extent(values, [0, ...refLines.map(r => r.value)]), {
    domain: props.domain,
    ticks: props.ticks,
    format: fmt,
    count: 5,
  });
  const dom = axis.domain;
  const lo = Math.min(...dom);
  const hi = Math.max(...dom);
  const ticks = axis.ticks.filter(t => t.value >= lo && t.value <= hi);
  const showValues = props.values ?? (k === 1 && n <= 16);
  const colorOf = (it: BarItem, v: number) =>
    it.color ?? (props.signed ? (v < 0 ? 'var(--neg)' : 'var(--pos)') : (props.color ?? 'var(--ink)'));
  const textOf = (it: BarItem) => it.valueText ?? (isNum(it.value) ? fmt(it.value) : '—');
  const wrap = (g: BarGroup, body: ReactNode) =>
    g.href ? (
      <a key={g.id} href={g.href} className={s.link} aria-label={g.tip ?? g.label}>{body}</a>
    ) : (
      <g key={g.id}>{body}</g>
    );

  let H: number;
  let body: ReactNode;

  if (!horizontal) {
    H = props.height ?? 360;
    const m = {
      top: showValues ? 28 : 16,
      right: 20,
      bottom: 36,
      left: 14 + Math.max(16, ...ticks.map(t => textWidth(t.label))) + (props.axisLabel ? 26 : 0),
    };
    const sv = linear(dom, [H - m.bottom, m.top]);
    const zero = sv(clamp(0, lo, hi));
    const band = (W - m.left - m.right) / Math.max(1, n);
    const inner = band * 0.72;
    const bw = inner / k;
    const every = Math.max(1, Math.ceil((Math.max(0, ...groups.map(g => textWidth(g.label))) + 10) / band));
    body = (
      <>
        {ticks.map(t => (
          <g key={`t${t.value}`}>
            <line x1={m.left} x2={W - m.right} y1={sv(t.value)} y2={sv(t.value)} className={s.grid} />
            <text x={m.left - 10} y={sv(t.value)} dy="0.35em" textAnchor="end" className={s.tick}>{t.label}</text>
          </g>
        ))}
        {groups.map((g, i) => {
          const gx = m.left + i * band + (band - inner) / 2;
          return wrap(
            g,
            <>
              {g.items.map((it, j) => {
                const x = gx + j * bw;
                if (!isNum(it.value)) {
                  return showValues ? (
                    <text key={it.key} x={x + bw / 2} y={zero - 7} textAnchor="middle" className={s.valueLabel}>—</text>
                  ) : null;
                }
                const yv = sv(clamp(it.value, lo, hi));
                const top = Math.min(yv, zero);
                const h = Math.max(1, Math.abs(yv - zero));
                return (
                  <g key={it.key}>
                    <rect x={x + 1} y={top} width={Math.max(1, bw - 2)} height={h} rx={Math.min(3, bw / 4)}
                      className={s.bar} style={{ fill: colorOf(it, it.value) }} data-tip={it.tip} />
                    {showValues ? (
                      <text x={x + bw / 2} y={it.value < 0 ? top + h + 15 : top - 7} textAnchor="middle" className={s.valueLabel}>
                        {textOf(it)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
              {i % every === 0 ? (
                <text x={m.left + i * band + band / 2} y={H - m.bottom + 22} textAnchor="middle" className={s.tick} data-tip={g.tip}>
                  {g.label}
                </text>
              ) : null}
            </>,
          );
        })}
        <line x1={m.left} x2={W - m.right} y1={zero} y2={zero} className={s.axisLine} />
        {refLines.map((r, i) => <HRef key={`r${i}`} r={r} y={sv(r.value)} x1={m.left} x2={W - m.right} />)}
        {props.axisLabel ? (
          <text transform={`translate(14 ${(m.top + H - m.bottom) / 2}) rotate(-90)`} textAnchor="middle" className={s.axisTitle}>
            {props.axisLabel}
          </text>
        ) : null}
      </>
    );
  } else {
    const maxChars = props.maxLabelChars ?? 28;
    const labels = groups.map(g => truncate(g.label, maxChars));
    const rowH = props.rowHeight ?? (k > 1 ? 16 * k + 14 : 34);
    const m = {
      top: 12,
      right: showValues ? 24 + Math.max(24, ...groups.flatMap(g => g.items.map(it => textWidth(textOf(it))))) : 24,
      bottom: 34 + (props.axisLabel ? 24 : 0),
      left: 16 + Math.max(24, ...labels.map(l => textWidth(l, 14))),
    };
    H = props.height ?? m.top + Math.max(1, n) * rowH + m.bottom;
    const plotBottom = H - m.bottom;
    const sh = linear(dom, [m.left, W - m.right]);
    const zero = sh(clamp(0, lo, hi));
    body = (
      <>
        {ticks.map(t => (
          <g key={`t${t.value}`}>
            <line x1={sh(t.value)} x2={sh(t.value)} y1={m.top} y2={plotBottom} className={s.grid} />
            <text x={sh(t.value)} y={plotBottom + 22} textAnchor="middle" className={s.tick}>{t.label}</text>
          </g>
        ))}
        {groups.map((g, i) => {
          const y0 = m.top + i * rowH;
          const inner = rowH * 0.68;
          const bh = inner / k;
          return wrap(
            g,
            <>
              <text x={m.left - 12} y={y0 + rowH / 2} dy="0.35em" textAnchor="end" className={s.barLabel}
                data-tip={g.tip ?? (labels[i] !== g.label ? g.label : undefined)}>
                {labels[i]}
              </text>
              {g.items.map((it, j) => {
                const y = y0 + (rowH - inner) / 2 + j * bh;
                if (!isNum(it.value)) {
                  return showValues ? (
                    <text key={it.key} x={zero + 6} y={y + bh / 2} dy="0.35em" className={s.valueLabel}>—</text>
                  ) : null;
                }
                const xv = sh(clamp(it.value, lo, hi));
                const left = Math.min(xv, zero);
                const w = Math.max(1, Math.abs(xv - zero));
                return (
                  <g key={it.key}>
                    <rect x={left} y={y + 1} width={w} height={Math.max(1, bh - 2)} rx={Math.min(4, bh / 4)}
                      className={s.bar} style={{ fill: colorOf(it, it.value) }} data-tip={it.tip} />
                    {showValues ? (
                      <text x={it.value < 0 ? left - 6 : left + w + 6} y={y + bh / 2} dy="0.35em"
                        textAnchor={it.value < 0 ? 'end' : 'start'} className={s.valueLabel}>
                        {textOf(it)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
            </>,
          );
        })}
        <line x1={zero} x2={zero} y1={m.top} y2={plotBottom} className={s.axisLine} />
        {refLines.map((r, i) => <VRef key={`r${i}`} r={r} x={sh(r.value)} y1={m.top} y2={plotBottom} right={W - m.right} />)}
        {props.axisLabel ? (
          <text x={(m.left + W - m.right) / 2} y={H - 6} textAnchor="middle" className={s.axisTitle}>{props.axisLabel}</text>
        ) : null}
      </>
    );
  }

  return (
    <figure className={`${s.figure} ${className ?? ''}`}>
      {legend ? <div className={s.legendSlot}>{legend}</div> : null}
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio={props.preserveAspectRatio ?? 'xMidYMid meet'}
        className={s.svg} role="img" aria-label={ariaLabel}>
        {body}
        {n === 0 ? <text x={W / 2} y={H / 2} textAnchor="middle" className={s.empty}>No data yet</text> : null}
      </svg>
    </figure>
  );
}
```

**File:** `web/components/sera/charts/Legend.tsx:1` (create)
**Code:**
```tsx
import type { CSSProperties } from 'react';
import s from './charts.module.css';
import type { LineSeries } from './LineChart';
import { colorAt } from './scale';

export type LegendShape = 'line' | 'dash' | 'dot' | 'ring' | 'zone';
export type LegendItem = {
  label: string;
  /** CSS colour, normally a token: 'var(--coral)'. */
  color: string;
  /** Default 'line'. 'zone' is a soft rectangle for shaded regions. */
  shape?: LegendShape;
  tip?: string;
};

const SHAPE: Record<LegendShape, string> = {
  line: s.sw_line,
  dash: s.sw_dash,
  dot: s.sw_dot,
  ring: s.sw_ring,
  zone: s.sw_zone,
};

const swatchStyle = (it: LegendItem): CSSProperties =>
  it.shape === 'dash' || it.shape === 'ring' ? { borderColor: it.color } : { background: it.color };

/** Key for a chart. Plain HTML, so it can sit in a chart's legend slot or anywhere in a Section. */
export function Legend({ items, className }: { items: readonly LegendItem[]; className?: string }) {
  return (
    <ul className={`${s.legend} ${className ?? ''}`}>
      {items.map((it, i) => (
        <li key={`${i}-${it.label}`} className={s.legendItem} data-tip={it.tip}>
          <span aria-hidden="true" className={`${s.swatch} ${SHAPE[it.shape ?? 'line']}`} style={swatchStyle(it)} />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

/** Legend items matching LineChart's own colour and dash choices. */
export function legendFromSeries(series: readonly LineSeries[]): LegendItem[] {
  return series.map((se, i) => ({
    label: se.label,
    color: se.color ?? colorAt(i),
    shape: se.dash ? 'dash' : 'line',
    tip: se.tip,
  }));
}
```
**Impact:** none (new).

### Step 10: Chart render tests
**File:** `web/components/sera/charts/charts.test.tsx:1` (create)
**Change:** These tests server-render each chart with `react-dom/server` and check for:
- no `NaN`
- the viewBox
- ticks, labels, tips, links and colours
- the empty states

vitest needs no config for this. It picks up `*.test.tsx`, applies the tsconfig `jsx: react-jsx`, and returns hashed class names for CSS modules. This was verified.
**Code:**
```tsx
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { BarChart, barGroups } from './BarChart';
import { Legend, legendFromSeries } from './Legend';
import { LineChart, type LineSeries } from './LineChart';
import { ScatterChart } from './ScatterChart';
import { fmtMultiple, fmtNumber, fmtPct } from './scale';

const DATES = ['1993-01-29', '1999-12-31', '2007-06-29', '2015-10-16'];
const curve = (k: number): [string, number][] => DATES.map((d, i) => [d, 1 + k * i]);
const count = (html: string, needle: string) => html.split(needle).length - 1;

describe('LineChart', () => {
  const series: LineSeries[] = [
    { id: 'a', label: 'M0001 v1', points: curve(0.5), endLabel: true, tip: 'M0001 variant 1' },
    { id: 'spy', label: 'SPY', points: curve(0.4), dash: '1 5', color: 'var(--ink-3)', endLabel: true },
  ];

  it('draws date series with year ticks, a reference line and end labels', () => {
    const html = renderToStaticMarkup(
      <LineChart series={series} ariaLabel="Growth of 1" yFormat={fmtMultiple(1)} refLines={[{ value: 1, label: 'Start' }]} />,
    );
    expect(html).not.toContain('NaN');
    expect(html).toContain('viewBox="0 0 960 360"');
    expect(html).toContain('role="img"');
    expect(html).toContain('aria-label="Growth of 1"');
    expect(html).toContain('>1994<');
    expect(html).toContain('>2014<');
    expect(html).toContain('data-tip="M0001 variant 1"');
    expect(html).toContain('>Start<');
    expect(html).toContain('>SPY<');
    expect(html).toContain('stroke-dasharray="1 5"');
  });

  it('fills an underwater area and breaks the line at nulls', () => {
    const dd: LineSeries = {
      id: 'dd', label: 'Drawdown', area: true, color: 'var(--neg)',
      points: [['1993-01-29', 0], ['2000-01-31', -0.12], ['2003-01-31', null], ['2008-12-31', -0.3], ['2015-10-16', 0]],
    };
    const html = renderToStaticMarkup(<LineChart series={[dd]} ariaLabel="Drawdown" yFormat={fmtPct(0)} includeZero />);
    expect(html).not.toContain('NaN');
    expect(html).toMatch(/d="M[^"]*Z"/);
    expect(html).toContain('>−30%<');
  });

  it('draws numeric step lines with per-point tips', () => {
    const best: LineSeries = { id: 'b', label: 'Best so far', step: true, dots: true, points: [[1, 2], [5, 3, 'Trial 5'], [9, 4]] };
    const html = renderToStaticMarkup(<LineChart series={[best]} ariaLabel="Progress" xLabel="Trial" yLabel="Hurdles" />);
    expect(html).not.toContain('NaN');
    expect(count(html, '<circle')).toBe(3);
    expect(html).toContain('data-tip="Trial 5"');
    expect(html).toContain('>Trial<');
  });

  it('says so when there is no data', () => {
    const html = renderToStaticMarkup(<LineChart series={[]} ariaLabel="Nothing" />);
    expect(html).toContain('No data yet');
    expect(html).not.toContain('NaN');
  });
});

describe('ScatterChart', () => {
  it('shades regions, draws reference lines and links points', () => {
    const html = renderToStaticMarkup(
      <ScatterChart
        ariaLabel="Where every try landed"
        points={[
          { id: 'M0001-a', x: 0.12, y: -0.003, tip: 'M0001 a', href: '/sera/methods/M0001', color: 'var(--coral)' },
          { id: 'H-x', x: 0.42, y: 0.02, ring: true, label: 'best' },
          { id: 'skip', x: null, y: 0.1 },
        ]}
        regions={[{ x1: 0.15, y0: 0, label: 'Pass zone' }]}
        refX={[{ value: 0.15, label: 'Max fall 15%' }]}
        refY={[{ value: 0, label: 'Same as SPY' }]}
        xFormat={fmtPct(0)}
        yFormat={fmtPct(1)}
        xLabel="Worst fall"
        yLabel="Growth vs SPY"
      />,
    );
    expect(html).not.toContain('NaN');
    expect(html).toContain('viewBox="0 0 960 440"');
    expect(html).toContain('href="/sera/methods/M0001"');
    expect(html).toContain('data-tip="M0001 a"');
    expect(html).toContain('>Pass zone<');
    expect(html).toContain('>Max fall 15%<');
    expect(html).toContain('>best<');
    expect(count(html, '<circle')).toBe(2);
  });

  it('says so when no point has both coordinates', () => {
    const html = renderToStaticMarkup(<ScatterChart ariaLabel="Empty" points={[{ id: 'a', x: null, y: 1 }]} />);
    expect(html).toContain('No data yet');
    expect(html).not.toContain('NaN');
  });
});

describe('BarChart', () => {
  it('draws signed grouped vertical bars with a reference line', () => {
    const html = renderToStaticMarkup(
      <BarChart
        ariaLabel="Year by year"
        signed
        format={fmtPct(0)}
        refLines={[{ value: 0.1, label: 'Ten percent' }]}
        groups={[
          { id: '1994', label: '1994', items: [{ key: 'm', value: -0.05, tip: 'Method 1994' }, { key: 'spy', value: 0.012, color: 'var(--ink-3)' }] },
          { id: '1995', label: '1995', items: [{ key: 'm', value: 0.2 }, { key: 'spy', value: 0.37, color: 'var(--ink-3)' }] },
        ]}
      />,
    );
    expect(html).not.toContain('NaN');
    expect(html).toContain('fill:var(--neg)');
    expect(html).toContain('fill:var(--pos)');
    expect(html).toContain('fill:var(--ink-3)');
    expect(html).toContain('>1994<');
    expect(html).toContain('data-tip="Method 1994"');
    expect(html).toContain('>Ten percent<');
  });

  it('draws horizontal bars with values, links and truncated labels', () => {
    const html = renderToStaticMarkup(
      <BarChart
        orientation="horizontal"
        ariaLabel="Hurdles"
        format={fmtNumber(0)}
        maxLabelChars={20}
        groups={barGroups([
          { id: 'spy', label: 'Beats SPY total return over the whole period', value: 12, href: '/sera/methods' },
          { id: 'dd', label: 'Max DD', value: 40 },
          { id: 'none', label: 'Nothing', value: null },
        ])}
      />,
    );
    expect(html).not.toContain('NaN');
    expect(html).toContain('viewBox="0 0 960 148"');
    expect(html).toContain('>12<');
    expect(html).toContain('>40<');
    expect(html).toContain('>—<');
    expect(html).toContain('href="/sera/methods"');
    expect(html).toContain('>Beats SPY total ret…<');
    expect(html).toContain('data-tip="Beats SPY total return over the whole period"');
  });

  it('says so when there are no bars', () => {
    const html = renderToStaticMarkup(<BarChart ariaLabel="Empty" groups={[]} />);
    expect(html).toContain('No data yet');
    expect(html).not.toContain('NaN');
  });
});

describe('Legend', () => {
  it('mirrors the series colours and dashes', () => {
    const items = legendFromSeries([
      { id: 'a', label: 'Method', points: [] },
      { id: 'spy', label: 'SPY', points: [], dash: '1 5', color: 'var(--ink-3)', tip: 'SPY with dividends' },
    ]);
    expect(items).toEqual([
      { label: 'Method', color: 'var(--ink)', shape: 'line', tip: undefined },
      { label: 'SPY', color: 'var(--ink-3)', shape: 'dash', tip: 'SPY with dividends' },
    ]);
    const html = renderToStaticMarkup(<Legend items={[...items, { label: 'Pass zone', color: 'var(--sky)', shape: 'zone' }]} />);
    expect(html).toContain('>Method<');
    expect(html).toContain('data-tip="SPY with dividends"');
    expect(html).toContain('border-color:var(--ink-3)');
    expect(html).toContain('background:var(--sky)');
  });
});
```
**Impact:** none (new).

### Step 11: Term, Stat, Section, PageHeader
**File:** `web/components/sera/Term.tsx:1` (create)
**Change:** The component takes `term` and `definition` and does **not** import `web/lib/sera/glossary.ts`; pages pass the definition in. The definition is also present as visually hidden text, so screen readers get it. The span is focusable.
**Code:**
```tsx
import type { ReactNode } from 'react';
import s from './Term.module.css';

export type TermProps = {
  /** The word as the glossary knows it, e.g. 'CAGR'. */
  term: string;
  /** One plain sentence; shown as the tooltip and read to screen readers. Pages take it from the glossary. */
  definition: string;
  /** What to print, if not `term` itself (e.g. 'worst fall' for 'max drawdown'). */
  children?: ReactNode;
};

/** A jargon word with a dotted underline; hover (or long-press) shows its plain definition. */
export function Term({ term, definition, children }: TermProps) {
  return (
    <span className={s.term} data-tip={definition} tabIndex={0}>
      {children ?? term}
      <span className={s.sr}>{` (${term}: ${definition})`}</span>
    </span>
  );
}
```

**File:** `web/components/sera/Term.module.css:1` (create)
**Code:**
```css
.term {
  text-decoration: underline dotted;
  text-decoration-color: var(--ink-3);
  text-decoration-thickness: 1.5px;
  text-underline-offset: 4px;
  cursor: help;
}
.term:hover { text-decoration-color: var(--coral); }
.term:focus-visible { outline: 2px solid var(--coral); outline-offset: 2px; border-radius: 4px; }

.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  white-space: nowrap;
}
```

**File:** `web/components/sera/Stat.tsx:1` (create)
**Code:**
```tsx
import type { ReactNode } from 'react';
import s from './Stat.module.css';

export type StatProps = {
  /** Already formatted: '58', '+1.2%', '4 of 6'. */
  value: string;
  label: ReactNode;
  /** Colours the number (--pos / --neg). */
  tone?: 'pos' | 'neg';
  /** Tooltip on the whole tile. */
  tip?: string;
  /** A smaller second line under the label. */
  sub?: ReactNode;
  /** 'lg' (default) 52px number, 'md' 34px. */
  size?: 'lg' | 'md';
};

/** KPI tile: a big tabular number, its label, and an optional plain-language line under it. */
export function Stat({ value, label, tone, tip, sub, size = 'lg' }: StatProps) {
  return (
    <div className={s.stat} data-tip={tip} tabIndex={tip ? 0 : undefined}>
      <span className={`num ${s.value} ${size === 'md' ? s.md : ''} ${tone ?? ''}`}>{value}</span>
      <span className={s.label}>{label}</span>
      {sub ? <span className={s.sub}>{sub}</span> : null}
    </div>
  );
}
```

**File:** `web/components/sera/Stat.module.css:1` (create)
**Code:**
```css
.stat { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.stat[data-tip] { cursor: help; }
.stat:focus-visible { outline: 2px solid var(--coral); outline-offset: 4px; border-radius: 12px; }
.value { font-size: 52px; line-height: 0.95; letter-spacing: -0.04em; white-space: nowrap; }
.md { font-size: 34px; letter-spacing: -0.03em; }
.label { font-size: 15px; line-height: 1.35; color: var(--ink); }
.sub { font-size: 14px; line-height: 1.4; color: var(--ink-2); }
```

**File:** `web/components/sera/Section.tsx:1` (create)
**Change:** This is the Seer v2 sheet: the global `.sheet` (40 px radius) plus `.bg-*`. It has an eyebrow, an `h2` title, a plain caption, and an aside slot (Legend, segmented filter, icon link). It sets `--chart-halo` to its own background. `SectionGrid` lays sheets out in desktop columns and stacks them below 1024 px.
**Code:**
```tsx
import type { CSSProperties, ReactNode } from 'react';
import s from './Section.module.css';

/** The Seer v2 sheet backgrounds (global .bg-* classes). */
export type SectionBg = 'sheet' | 'lav' | 'butter' | 'sky' | 'stone' | 'coral';

export type SectionProps = {
  eyebrow?: string;
  title?: string;
  /** One plain sentence: what the content shows and how to read it (plan invariant 6). May hold <Term>s. */
  caption?: ReactNode;
  /** Default 'sheet'. */
  bg?: SectionBg;
  /** Top-right of the header: a Legend, a segmented filter, an icon link. */
  aside?: ReactNode;
  /** Anchor id; also links the heading for screen readers. */
  id?: string;
  className?: string;
  children?: ReactNode;
};

/** One rounded 40px sheet: eyebrow, title, plain caption, then content. Charts inside pick up its background. */
export function Section({ eyebrow, title, caption, bg = 'sheet', aside, id, className, children }: SectionProps) {
  const titleId = id && title ? `${id}-title` : undefined;
  const style = { '--chart-halo': `var(--${bg})` } as CSSProperties;
  return (
    <section id={id} className={`sheet bg-${bg} ${s.section} ${className ?? ''}`} style={style} aria-labelledby={titleId}>
      {eyebrow || title || caption || aside ? (
        <header className={s.head}>
          <div className={s.titles}>
            {eyebrow ? <span className={`eyebrow ${s.eyebrow}`}>{eyebrow}</span> : null}
            {title ? <h2 id={titleId} className={s.title}>{title}</h2> : null}
            {caption ? <p className={s.caption}>{caption}</p> : null}
          </div>
          {aside ? <div className={s.aside}>{aside}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

/** Desktop grid of Sections. `columns` is a grid-template-columns value; one column below 1024 px. */
export function SectionGrid({ columns, className, children }: { columns?: string; className?: string; children: ReactNode }) {
  const style = columns ? ({ '--cols': columns } as CSSProperties) : undefined;
  return (
    <div className={`${s.grid} ${className ?? ''}`} style={style}>
      {children}
    </div>
  );
}
```

**File:** `web/components/sera/Section.module.css:1` (create)
**Code:**
```css
/* Overrides the mobile .sheet padding (globals.css) with desktop spacing. */
.section { padding: 36px 40px 40px; gap: 24px; min-width: 0; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.titles { display: flex; flex-direction: column; gap: 8px; min-width: 0; max-width: 820px; }
.eyebrow { color: var(--ink-2); }
.title { font-size: 30px; line-height: 1.1; letter-spacing: -0.025em; }
.caption { font-size: 17px; line-height: 1.5; color: var(--ink-2); }
.aside { flex: none; display: flex; align-items: center; gap: 10px; }

.grid {
  display: grid;
  grid-template-columns: var(--cols, repeat(2, minmax(0, 1fr)));
  gap: 16px;
  align-items: stretch;
}

@media (max-width: 1023.98px) {
  .section { padding: 28px 22px 32px; }
  .head { flex-direction: column; }
  .grid { grid-template-columns: minmax(0, 1fr); }
}
```

**File:** `web/components/sera/PageHeader.tsx:1` (create)
**Change:** It follows the pattern of `components/AppHeader.tsx`, an inline `'use server'` sign-out form, at desktop scale:
- a coral-dot eyebrow
- a 52 px title
- a plain lede
- an "As of Oct 4, 2026" pill, the calendar date of `snapshot.asOf`
- an icon-only sign-out button

Sign-out lands on `/signin?next=%2Fsera`, so signing in again returns to Sera.
**Code:**
```tsx
import { CalendarClock, LogOut } from 'lucide-react';
import type { ReactNode } from 'react';
import { signOut } from '@/auth';
import s from './PageHeader.module.css';

export type PageHeaderProps = {
  eyebrow: string;
  title: string;
  /** One or two plain sentences under the title. */
  lede?: ReactNode;
  /** The snapshot's asOf (ISO date or timestamp); shown as 'As of Oct 4, 2026'. */
  asOf?: string;
  /** Extra controls left of the as-of pill (icon-only). */
  aside?: ReactNode;
};

const DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' });

/** '2026-10-04T13:05:00+07:00' or '2026-10-04' -> 'Oct 4, 2026': the calendar date as written. */
function asOfLabel(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : DAY.format(d);
}

/** Top of every Sera page: eyebrow, big title, plain lede; as-of date and sign-out on the right. */
export function PageHeader({ eyebrow, title, lede, asOf, aside }: PageHeaderProps) {
  return (
    <header className={s.header}>
      <div className={s.titles}>
        <span className={`eyebrow ${s.eyebrow}`}>{eyebrow}</span>
        <h1 className={s.title}>{title}</h1>
        {lede ? <p className={s.lede}>{lede}</p> : null}
      </div>
      <div className={s.aside}>
        {aside}
        {asOf ? (
          <span className={`pill-outline num ${s.asOf}`} data-tip="When the lab record shown here was last written">
            <CalendarClock size={17} strokeWidth={1.5} aria-hidden="true" />
            As of {asOfLabel(asOf)}
          </span>
        ) : null}
        <form action={async () => { 'use server'; await signOut({ redirectTo: '/signin?next=%2Fsera' }); }}>
          <button type="submit" className="icon-btn" data-tip="Sign out" aria-label="Sign out">
            <LogOut size={21} strokeWidth={1.5} />
          </button>
        </form>
      </div>
    </header>
  );
}
```

**File:** `web/components/sera/PageHeader.module.css:1` (create)
**Code:**
```css
.header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  padding: 40px 8px 20px 4px;
}
.titles { display: flex; flex-direction: column; gap: 10px; min-width: 0; max-width: 900px; }
.eyebrow { display: inline-flex; align-items: center; gap: 10px; color: var(--ink-2); }
.eyebrow::before { content: ''; width: 10px; height: 10px; border-radius: 999px; background: var(--coral); }
.title { font-size: 52px; line-height: 1.02; letter-spacing: -0.04em; }
.lede { font-size: 19px; line-height: 1.5; color: var(--ink-2); max-width: 760px; }
.aside { flex: none; display: flex; align-items: center; gap: 10px; }
.asOf { height: 52px; color: var(--ink); cursor: help; }

@media (max-width: 1023.98px) {
  .header { flex-direction: column; align-items: flex-start; gap: 18px; padding: 24px 4px 12px; }
  .title { font-size: 36px; }
  .lede { font-size: 17px; }
}
```
**Impact:** none (new).

### Step 12: The Sera rail
**File:** `web/components/sera/SeraNav.tsx:1` (create)
**Change:** This is a client component, because it needs `usePathname`. It holds:
- the wordmark "Sera." with a coral dot
- the five tabs in the same dark pill as Seer's rail: Overview `LayoutDashboard`, Methods `FlaskConical`, Journal `NotebookPen`, Ideas `Lightbulb`, How it works `Workflow`
- an outlined `Eye` icon link "Back to Seer", pushed to the foot of the rail

Every link is icon-only with `aria-label` + `data-tip`, and the active tab gets `aria-current="page"`. Overview is active only on `/sera` exactly; each other tab is active on its path and anything below it.
**Code:**
```tsx
'use client';

import { Eye, FlaskConical, LayoutDashboard, Lightbulb, NotebookPen, Workflow } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './SeraNav.module.css';

const TABS = [
  { href: '/sera', icon: LayoutDashboard, tip: 'Overview' },
  { href: '/sera/methods', icon: FlaskConical, tip: 'Methods' },
  { href: '/sera/journal', icon: NotebookPen, tip: 'Journal' },
  { href: '/sera/ideas', icon: Lightbulb, tip: 'Ideas' },
  { href: '/sera/how', icon: Workflow, tip: 'How it works' },
];

/** Sera's rail: wordmark, five icon-only section tabs, and a way back to Seer. A top bar below 1024 px. */
export function SeraNav() {
  const path = usePathname() ?? '';
  return (
    <aside className={s.rail}>
      <span className={s.wordmark}>
        Sera<span className={s.dot}>.</span>
      </span>
      <nav className={s.tabs} aria-label="Sera sections">
        {TABS.map(({ href, icon: Icon, tip }) => {
          const active = href === '/sera' ? path === '/sera' : path === href || path.startsWith(`${href}/`);
          return (
            <Link key={href} href={href} className={active ? s.active : s.tab}
              data-tip={tip} aria-label={tip} aria-current={active ? 'page' : undefined}>
              <Icon size={22} strokeWidth={active ? 1.75 : 1.5} />
            </Link>
          );
        })}
      </nav>
      <Link href="/" className={`icon-btn ${s.back}`} data-tip="Back to Seer" aria-label="Back to Seer">
        <Eye size={21} strokeWidth={1.5} />
      </Link>
    </aside>
  );
}
```

**File:** `web/components/sera/SeraNav.module.css:1` (create)
**Code:**
```css
/* Same rail as Seer's Nav (Nav.module.css), always shown: Sera is desktop-first, not desktop-only. */
.rail {
  position: sticky;
  top: 0;
  height: 100dvh;
  flex: none;
  width: 104px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 28px 0;
  gap: 28px;
}

.wordmark { font-size: 24px; font-weight: 500; letter-spacing: -0.05em; }
.dot { color: var(--coral); }

.tabs {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border-radius: 999px;
  background: var(--bar);
}

.tab, .active {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 52px;
  min-width: 52px;
  border-radius: 999px;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  transition: background 0.12s;
}
.tab { color: var(--bar-ink); }
.tab:hover { background: rgba(255, 255, 255, 0.1); }
.active { background: var(--coral); color: var(--on-coral); }
.tab:focus-visible, .active:focus-visible { outline: 2px solid var(--coral); outline-offset: 2px; }

.back { margin-top: auto; }

/* Below 1024 px: a top bar, not designed further (plan: desktop only for now). */
@media (max-width: 1023.98px) {
  .rail {
    z-index: 40;
    width: 100%;
    height: auto;
    flex-direction: row;
    padding: calc(10px + var(--safe-top)) 16px 10px;
    gap: 16px;
    background: var(--bg);
  }
  .tabs { flex-direction: row; padding: 5px; }
  .tab, .active { height: 44px; min-width: 44px; }
  .back { margin-top: 0; margin-left: auto; }
}
```
**Impact:** none (new).

### Step 13: Layout, shell, not-found
**File:** `web/app/sera/layout.tsx:1` (create)
**Change:** `await requireSera()`, then the shell. `/sera` sits outside the `(app)` route group, so Seer's `Nav` and its `currentUser()` redirect do not apply here; this layout is the only gate.
**Code:**
```tsx
import type { Metadata } from 'next';
import { SeraNav } from '@/components/sera/SeraNav';
import { requireSera } from '@/lib/sera/gate';
import s from './sera.module.css';

export const metadata: Metadata = { title: { default: 'Sera', template: '%s · Sera' } };

/** Sera, the method lab: gated to SERA_EMAIL (invariant 3), desktop shell with its own rail. */
export default async function SeraLayout({ children }: { children: React.ReactNode }) {
  await requireSera();
  return (
    <div className={s.shell}>
      <SeraNav />
      <main className={s.main}>
        <div className={s.column}>{children}</div>
      </main>
    </div>
  );
}
```

**File:** `web/app/sera/sera.module.css:1` (create)
**Code:**
```css
.shell { min-height: 100dvh; display: flex; }

.main { flex: 1; min-width: 0; padding: 0 40px 56px 12px; }

/* The content column: wide but bounded, so charts stay readable on big monitors. */
.column {
  width: 100%;
  max-width: 1360px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.notFound { padding-top: 40px; }

@media (max-width: 1023.98px) {
  .shell { flex-direction: column; }
  .main { padding: 0 16px 40px; }
}
```

**File:** `web/app/sera/not-found.tsx:1` (create)
**Change:** This catches `notFound()` thrown by `/sera` pages, such as Phase 5's unknown method id, and renders inside the shell. The one control is an icon-only link back to the overview.
**Code:**
```tsx
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Section } from '@/components/sera/Section';
import s from './sera.module.css';

/** notFound() from a /sera page (e.g. an unknown method id), inside the Sera shell. */
export default function SeraNotFound() {
  return (
    <div className={s.notFound}>
      <Section
        bg="butter"
        eyebrow="Not found"
        title="Nothing lives at this address."
        caption="The method or page may have been renamed. The overview lists everything the lab has tried."
        aside={
          <Link href="/sera" className="icon-btn" data-tip="Back to the overview" aria-label="Back to the overview">
            <ArrowLeft size={21} strokeWidth={1.5} />
          </Link>
        }
      />
    </div>
  );
}
```
**Impact:** A request to `/sera` itself 404s until Phase 4 adds `page.tsx`, because no route matches yet. The tree builds either way.

### Step 14: Sera link on Seer's desktop rail
**File:** `web/components/Nav.tsx:3,16,20-23` (modify; the whole file after the change)
**Change:**
- Import `Telescope`. It is unused by Seer's tabs and differs from Sera's own tab icons.
- `Nav` takes `showSera`. When it is true, an outlined icon link to `/sera` sits at the foot of the **desktop rail only**. The mobile pill bar keeps its four tabs and its 276 px width.
**Code:**
```tsx
'use client';

import { Briefcase, History, LayoutGrid, Telescope, Trophy } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './Nav.module.css';

const TABS = [
  { href: '/', icon: LayoutGrid, tip: 'Today' },
  { href: '/positions', icon: Briefcase, tip: 'Positions' },
  { href: '/leaderboard', icon: Trophy, tip: 'Leaderboard' },
  { href: '/history', icon: History, tip: 'History' },
];

/** Floating pill tab bar on mobile, vertical rail on desktop. Icon-only. `showSera` adds Sera to the desktop rail. */
export function Nav({ showSera = false }: { showSera?: boolean }) {
  const path = usePathname();
  return (
    <>
      <aside className={`${s.rail} desk-only`}>
        <span className={s.wordmark}>Seer.</span>
        <Tabs path={path} vertical />
        {showSera && (
          <Link href="/sera" className={`icon-btn ${s.sera}`} data-tip="Sera, the method lab" aria-label="Sera, the method lab">
            <Telescope size={21} strokeWidth={1.5} />
          </Link>
        )}
      </aside>
      <nav className={`${s.bar} mobile-only`} aria-label="Sections" data-tip-anchor>
        <Tabs path={path} />
      </nav>
    </>
  );
}

function Tabs({ path, vertical }: { path: string; vertical?: boolean }) {
  return (
    <div className={vertical ? s.vtabs : s.tabs}>
      {TABS.map(({ href, icon: Icon, tip }) => {
        const active = href === '/' ? path === '/' : path.startsWith(href);
        return (
          <Link key={href} href={href} className={active ? s.active : s.tab}
            data-tip={tip} aria-label={tip} aria-current={active ? 'page' : undefined}>
            <Icon size={22} strokeWidth={active ? 1.75 : 1.5} />
          </Link>
        );
      })}
    </div>
  );
}
```

**File:** `web/components/Nav.module.css:68` (append after `.wordmark`, which ends at line 67)
**Code:**
```css

/* Desktop rail only: the way into Sera, at the foot of the rail, for the Sera account. */
.sera { margin-top: auto; }
```

**File:** `web/app/(app)/layout.tsx:1-14` (modify; the whole file after the change)
**Code:**
```tsx
import { redirect } from 'next/navigation';
import { currentUser } from '@/auth';
import { Nav } from '@/components/Nav';
import { isSeraUser } from '@/lib/sera/access';
import s from './shell.module.css';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await currentUser();
  if (!user) redirect('/signin');
  return (
    <div className={s.shell}>
      <Nav showSera={isSeraUser(user.email)} />
      <main className={s.main}>{children}</main>
    </div>
  );
}
```
**Impact:** `Nav`'s prop is optional (default `false`), so no other call site breaks. There are none today.

### Step 15: Sign-in honours `next`
**File:** `web/app/signin/page.tsx` (modify):
- line 3: add the import
- lines 8–10: read `next`
- line 33: `redirectTo: dest`

**Change:** Read `next`, sanitise it with `safeNext`, and use it for the already-signed-in redirect and for `signIn('google', { redirectTo })`. The inline server action captures `dest`; Next binds closure values into the action. The `denied` path in `auth.ts` (`/signin?denied=…`) is unchanged, and a refused account loses `next`, which is fine. The whole file after the change:
**Code:**
```tsx
import { ChevronRight, UserX } from 'lucide-react';
import { redirect } from 'next/navigation';
import { currentUser, signIn } from '@/auth';
import { safeNext } from '@/lib/allow';
import s from './signin.module.css';

const WORDS = ['Strategic', 'Econometric', 'Ensemble', 'Resolver', 'Patience', 'Discipline', 'Risk', 'Limits', 'Targets', 'Stops', 'Signal'];

type Search = { denied?: string; error?: string; next?: string | string[] };

export default async function SignIn({ searchParams }: { searchParams: Promise<Search> }) {
  const { denied, error, next } = await searchParams;
  // Where to land after sign-in: an internal path only (e.g. /sera from the Sera gate), else Today.
  const dest = safeNext(next);
  if (await currentUser()) redirect(dest);
  const refused = denied !== undefined || error === 'AccessDenied';

  return (
    <main className={s.splash}>
      <div className={s.art} aria-hidden="true">
        <div className={s.words}>{WORDS.map(w => <span key={w}>{w}</span>)}</div>
        <div className={s.eye} />
        <span className={s.mark}>Seer.</span>
      </div>
      <h1 className={s.srOnly}>Seer sign-in</h1>

      <div className={s.bottom}>
        {refused && (
          <div className={s.refused} role="alert">
            <span className={s.refusedIcon}><UserX size={20} /></span>
            <div className={s.refusedText}>
              <span className={s.refusedTitle}>This account isn’t allowed</span>
              {denied && <span className={s.refusedSub}>{denied}</span>}
              <span className={s.refusedSub}>Seer is private to one Google account. Try again with that one.</span>
            </div>
          </div>
        )}
        <form action={async () => { 'use server'; await signIn('google', { redirectTo: dest }); }}>
          <button type="submit" className={s.google} data-tip="Sign in with Google" aria-label="Sign in with Google">
            <span className={s.gdot}>
              <svg width="26" height="26" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
                <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
                <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
                <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
              </svg>
            </span>
            <span className={s.chev}><ChevronRight size={24} /></span>
          </button>
        </form>
      </div>
    </main>
  );
}
```
**Impact:**
- A plain `/signin` visit behaves as before: `dest` is `/`.
- `/signin?next=%2Fsera` returns to `/sera`.
- `?next=//evil.example` falls back to `/`. Auth.js's default redirect callback also restricts `redirectTo` to the same origin.

## Verification

**Build:** after Step 0's `npm ci`: `cd web && npx tsc --noEmit`, then `NEXT_TELEMETRY_DISABLED=1 npx next build`. The build needs no env. The route table shows no `/sera` entry until Phase 4 adds the page.
**Tests:** `cd web && npx vitest run`. Expect 13 files and 123 tests. The new ones are `lib/sera/access.test.ts` (3), `lib/allow.test.ts` (5 in total, 3 of them new), `components/sera/charts/scale.test.ts` (24) and `components/sera/charts/charts.test.tsx` (10).
**Manual check:** These need Phase 4's page for `/sera` itself, or any `/sera/*` page. With `npm run dev` and a real `.env.local`:
1. Signed out, `/sera` should 307 to `/signin?next=%2Fsera`. Signing in should land back on `/sera`.
2. Signed in as the owner on desktop, Seer's rail should show the Telescope link at its foot, opening `/sera`.
3. In Sera, the rail should show the "Sera." wordmark, the five tabs with tooltips, the active tab in coral, and the Eye link back to `/`.
4. Below 1024 px, the rail should become a top bar and the content a single column.
5. A Term's tooltip should wrap at 340 px.
**Exit criteria:**
- `tsc` and `vitest` are green.
- `app/sera/layout.tsx` gates with `requireSera()` per invariant 3.
- Every chart renders from plain props with no snapshot import: `grep -r "lib/sera/lab\|data/lab.json" web/components/sera` finds nothing.
- Every control added is an icon-only Lucide link or button with `aria-label` + `data-tip`.

## Handoffs

1. **Phases 4, 5 and 6: call the gate in each page.** Each `/sera` page should start with `await requireSera('/sera/…')` from `@/lib/sera/gate`.
   - **Why:** Layouts are not re-rendered on client-side navigation. Per Next's own guidance, a hand-crafted RSC request for a child segment can render the page without running the layout's check.
   - **Cost:** One line per page.
   - **Risk if skipped:** Low. The repo and `lab.sqlite` are public by choice.

   **Adopted by the reconciler:** Phases 4, 5 and 6 call it at the top of every page (`/sera`, `/sera/methods`, `/sera/methods/[id]`, `/sera/journal`, `/sera/ideas`, `/sera/how`). This phase only provides it.
2. **Phases 4, 5, 6: API differences from what their drafts assumed (resolved by the reconciler).** Their call sites were rewritten to this phase's exact exports: `Term` `term`+`definition` (pages feed `GLOSSARY` through a local `T` wrapper; this phase still never imports `glossary.ts`), `ScatterChart` `regions`/`refX`/`refY`/`xDomain`/`yDomain`/`TickSpec` with point `id`s and `color` strings, `LineChart` tuple points with `id`/`color`/`step`/`area`/`dash`, `BarChart` `groups` (+ `barGroups`) with `domain`/`valueText`, `Legend` `color`/`shape`, string `PageHeader.title`, and `requireSera` instead of `currentUser()`. Nothing in this phase changes.
3. **Phase 2: formatter overlap (none).** Phase 2 adds no `web/lib/sera/format.ts`; it reuses `web/lib/format.ts`. Pages use `charts/scale.ts`'s `fmt*` for ticks and their own view helpers for text.
4. **Phase 6: the diagrams.** `web/components/sera/diagrams/` (Pipeline, Windows) can reuse `charts.module.css` classes (`.tick`, `.axisTitle`, `.refLabel`) or carry its own module. This phase creates nothing there.
5. **Phase 7: docs.** `web/package_readme.md` should document:
   - the `/sera` gate (`SERA_EMAIL` in `lib/sera/access.ts`, on top of `ALLOWED_EMAIL`)
   - `?next=` on `/signin`
   - the chart kit's location and conventions (from the Interface Contract above)
6. **Out of scope, noted:**
   - There is no root `app/not-found.tsx`, so strangers who hit a 404 see Next's default page.
   - Seer's mobile pill bar has no Sera entry, by design (R1, desktop only).

## Rollback

Revert this phase's commit. Alternatively, by hand:
- Delete `web/app/sera/`, `web/components/sera/`, `web/lib/sera/access.ts`, `access.test.ts` and `gate.ts`.
- Restore from `c138b08`: `web/components/Nav.tsx`, `Nav.module.css`, `web/app/(app)/layout.tsx`, `web/app/signin/page.tsx`, `web/components/tooltip.ts`, `web/lib/allow.ts`, `allow.test.ts`.

Phases 4–6 import from this phase, so roll them back first. Nothing in Phases 1, 2 or 7 depends on this phase's code.
