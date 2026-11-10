> Adopted from `.workflows/plan/LEADERBOARD_DESKTOP_REVAMP_PLAN.md` phase 2. Source: `.workflows/plan/leaderboard-desktop-revamp/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: One-row checklist switcher

**Plan set:** `LEADERBOARD_DESKTOP_REVAMP_PLAN.md`
**Analysis:** `.workflows/analyze/20261110-090235-LB7D_code_analyzer.md`
**Satisfies:** R2. The go-live checklist's icon switcher always fits on one row.
**Depends on:** Phase 1
**Difficulty:** EASY
**Package:** `web`

---

## Goal

`StrategySwitch` gets an opt-in `fit` mode. In that mode the icons sit in a CSS grid with one column per
icon. Each column is at most the normal 46px button, the buttons stay round (aspect-ratio 1) and get
smaller only when the row would otherwise overflow, and the row never wraps. The leaderboard checklist
sheet turns `fit` on. The grid applies at ≥ 1024 px only: below that a `fit` row is the same loose
wrapping row as today (plan invariant 2, mobile unchanged; see Decisions in the plan index). Every other
caller (positions, history) renders exactly as it does today.

## Measured facts this plan rests on (read from the code at `22d1051`)

- The checklist sheet is the fixed `380px` second column of `.top` at ≥ 1024 px
  (`leaderboard.module.css:140`), padded `28px` (`:150`), so the switcher row is **324px** wide at
  1024, 1280 and 1440 alike. The page width does not change it.
- On mobile the sheet is `padding: 28px 24px` (`globals.css:217-225`) and the shell adds no side
  padding, so at 390 px the row is **342px**. Mobile is out of this phase's reach (invariant 2): below
  1024 px the `fit` row keeps today's wrapping flex layout, so the 390 numbers below are for reference.
- Today: `.icon-btn.md` = 46×46 (`globals.css:168`), `StrategySwitch`'s `.group` is
  `flex-wrap: wrap; gap: 6px`. 7 buttons need 7·46 + 6·6 = **358px**, more than both 324 and 342.
  That is the wrap the owner saw, and it happens on the phone as well.
- With `fit`: columns are `minmax(0, 46px)` and gap is `min(6px, 48px / n)`:
  - n = 7 → gap 6, button (324 − 36)/7 ≈ **41.1px** desktop, (342 − 36)/7 ≈ **43.7px** at 390.
  - n = 12 → gap 4, button (324 − 44)/12 ≈ **23.3px** desktop, (342 − 44)/12 ≈ **24.8px** at 390.
  - When n buttons fit at 46px (n ≤ 6 on desktop), the tracks hit their 46px ceiling and the row
    looks exactly like today's flex row: 46px buttons, 6px gaps, left-aligned.
  - These numbers are computed from the CSS, not yet measured in a browser. The Proof journeys
    measure them.
- A "min ~32px" floor cannot hold for 12 icons in 324px: 12·32 + 11·4 = 428. This plan sets **no
  floor**, because one row is the requirement and a floor would bring back the wrap. 32px holds up to
  8 icons (8·32 + 7·6 = 298; 9 need 9·32 + 8·5.3 ≈ 330 > 324). The plan index now says "shrinks to
  fit; ≥ 32px up to 8 strategies, ~23px at 12" (reconciled).

## Interface Contract

**Deletes:** the `display: flex; gap: 6px;` declarations of `.switch` (`web/app/(app)/leaderboard/leaderboard.module.css:45`). The rule stays, with `padding-bottom` only.
**Renames:** none
**Creates:** prop `fit?: boolean` on `StrategySwitch` (`web/components/StrategySwitch.tsx`); CSS class `.fit` in `web/components/StrategySwitch.module.css`; inline custom property `--n` on the `fit` nav; test file `web/components/StrategySwitch.test.tsx`; verify-seer steps file `.claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs`
**Signature changes:** `StrategySwitch({ strategies, current, href, label, allTip, seg })` → `StrategySwitch({ strategies, current, href, label, allTip, seg, fit })`. Additive and optional, so no caller has to change.
**Requires (from earlier phases):** Phase 1 leaves the checklist sheet's `StrategySwitch` call in `leaderboard/page.tsx` exactly as it is at `22d1051` (`strategies={switchable}`), only 8 lines lower (lines 162-163), because it replaced line 33 with a 9-line block that rebuilds `board` with display icons; `switchable` therefore already carries the unique icons. Phase 1 does not touch `StrategySwitch.tsx`, `StrategySwitch.module.css` or the `.switch` rule.
**Leaves alone (owned by others):** colours, tints and icons, including `strategyIcon` / the resolver and what `strategies` holds (Phase 1). The card section, `.cards`/`.card*`/`.legend` and every other desktop rule in `leaderboard.module.css` (Phase 3). `.top`'s 380px column (nobody's: Phase 3 may resize it, and fit adapts to any width). `positions/page.tsx` and `history/page.tsx` (they stay in default mode).
**Shared file note:** `.claude/skills/verify-seer/features/leaderboard.md` is edited by Phases 1, 2 and 3. Phase 2 changes **only** the sentence "The checklist switches strategy with its own icon row." in "How to get to it" and adds **one** command line to the "Driving it" block.

## Files

| File | Action | What changes |
|---|---|---|
| `web/components/StrategySwitch.tsx` | modify (whole file, 43 lines) | add `fit` prop, grid class and `--n` inline style |
| `web/components/StrategySwitch.module.css` | modify (line 1, append) | add `.fit` rules (loose row below 1024 px, grid at ≥ 1024 px). `.group` is unchanged |
| `web/components/StrategySwitch.test.tsx` | create | default markup unchanged, fit markup carries `--n` and all items, seg wins over fit |
| `web/app/(app)/leaderboard/leaderboard.module.css` | modify line 45 | `.switch` becomes a plain block wrapper |
| `web/app/(app)/leaderboard/page.tsx` | modify line 163 (checklist sheet, as Phase 1 leaves it) | add `fit` to the checklist `StrategySwitch` |
| `.claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs` | create | desktop browser journey: one row at the real count, at 7 and at 12; positions unchanged |
| `.claude/skills/verify-seer/features/leaderboard.md` | modify (one sentence + one command) | feature map says the row shrinks to fit |

## Implementation Steps

### Step 1: Add the `fit` mode to `StrategySwitch`
**File:** `web/components/StrategySwitch.tsx:1-43` (replace the whole file)
**Change:** New optional `fit` prop. When `fit` is set and `seg` is not, the nav gets `s.fit` and the
inline style `--n: <item count>`, where the count includes the leading ListFilter button when `allTip`
is set. `seg` wins over `fit`, because the `.seg` pill sizes its own buttons through `--seg-btn`
(history's filters do that). If neither is set, the output is the same element, class and attributes
as today, with no `style` attribute, which keeps the default markup byte-identical.
**Code:**
```tsx
import { ListFilter } from 'lucide-react';
import Link from 'next/link';
import type { CSSProperties } from 'react';
import { strategyIcon } from './roster';
import s from './StrategySwitch.module.css';

export const ALL = 'all';

type Props = {
  /** Roster rows in display order. */
  strategies: { id: string; name: string; icon: string }[];
  /** The selected id, or ALL when `allTip` is set and nothing is filtered. */
  current: string;
  /** Builds each link's href (keep other query params there). */
  href: (id: string) => string;
  /** Accessible name of the group. */
  label: string;
  /** When set, a leading ListFilter button with id ALL and this tooltip. */
  allTip?: string;
  /** Draw as a `.seg` pill track instead of loose wrapping circles. Wins over `fit`. */
  seg?: boolean;
  /**
   * Desktop (≥ 1024px): one row, always: one grid column per button, each at most the usual 46px,
   * and all of them shrinking together once the row is too narrow, instead of wrapping onto a
   * second line. Below 1024px it is the loose wrapping row.
   */
  fit?: boolean;
};

/**
 * Icon-only strategy switcher: one Link per roster strategy with its own Lucide icon,
 * tooltip and aria-label = its name, aria-current on the selected one.
 * Server component: `href` is a function prop.
 *
 * `fit` exists for the leaderboard's go-live checklist, a fixed 324px row on desktop. The Claude
 * twins took the roster to seven research strategies, and the seventh 46px circle wrapped onto a
 * row of its own. The roster can reach twelve, so the buttons have to give up size: the count goes
 * to CSS as `--n`, and the CSS sets the columns and the gap from it. The phone layout is left as
 * it was (the leaderboard's mobile layout is not part of the desktop revamp), so below 1024px a
 * `fit` row wraps like the default one. The other callers keep the loose wrapping row. They have
 * room, and their markup is the same as before `fit` existed.
 */
export function StrategySwitch({ strategies, current, href, label, allTip, seg, fit }: Props) {
  const items = [
    ...(allTip ? [{ id: ALL, tip: allTip, Icon: ListFilter }] : []),
    ...strategies.map(st => ({ id: st.id, tip: st.name, Icon: strategyIcon(st.icon) })),
  ];
  const fitted = fit && !seg;
  return (
    <nav className={seg ? 'seg' : fitted ? s.fit : s.group} aria-label={label}
      style={fitted ? ({ '--n': items.length } as CSSProperties) : undefined}>
      {items.map(({ id, tip, Icon }) => {
        const on = current === id;
        return (
          <Link key={id} href={href(id)} replace scroll={false} className="icon-btn md"
            data-tip={tip} aria-label={tip} aria-current={on ? 'true' : undefined}>
            <Icon size={19} strokeWidth={on ? 2 : 1.5} />
          </Link>
        );
      })}
    </nav>
  );
}
```
Phase 1 does not touch this file (its callers pass display icon names through the unchanged
`{icon: string}` prop), so the file quoted above is the base `22d1051` file plus this step's additions:
the `CSSProperties` import, the `fit` prop with its doc, the docstring paragraph, `fitted`, and the
`className`/`style` change on `<nav>`.
**Impact:** Additive. Positions and history pass neither `fit` nor a new prop, so their HTML is unchanged.

### Step 2: The `.fit` grid
**File:** `web/components/StrategySwitch.module.css:1` (keep line 1 as it is, append below)
**Change:** Add the fit rules. Below 1024 px `.fit` is the same loose wrapping row as `.group`
(invariant 2: the mobile leaderboard layout is unchanged); the grid is inside the desktop media query.
The `:global(.icon-btn.md)` selector has specificity (0,3,0), which beats
globals' `.icon-btn.md` (0,2,0) whichever stylesheet loads first. It overrides only size and flex. Border,
background, colour, hover, `:focus-visible` and `[aria-current='true']` all still come from globals, so
the picked button still renders ink-filled. The tooltip (`components/tooltip.ts`) places itself from the
element's own rect, so a smaller button only moves where the pill appears.
**Code (whole file after the change):**
```css
.group { display: flex; flex-wrap: wrap; gap: 6px; }

/* Phone: the loose row, exactly as .group (the leaderboard's mobile layout is not part of the
   desktop revamp). */
.fit { display: flex; flex-wrap: wrap; gap: 6px; }

/* Desktop: one row whatever the count. Each column is at most the usual 46px button, so a row that
   fits looks exactly like .group. When it does not fit, every column gives up the same width
   (minmax(0, ...) has no floor) rather than one button wrapping onto a line of its own. The gap
   tightens from 6px to 4px as the row fills: 48px / n is 6 or more up to eight buttons and 4px
   at twelve. --n is the button count, set inline by StrategySwitch. */
@media (min-width: 1024px) {
  .fit {
    display: grid;
    grid-template-columns: repeat(var(--n, 1), minmax(0, 46px));
    gap: min(6px, calc(48px / var(--n, 1)));
    align-items: start;
  }
  .fit > :global(.icon-btn.md) {
    width: 100%;
    height: auto;
    min-width: 0;
    aspect-ratio: 1;
  }
  /* The 19px icon stays 19px until the button is under ~38px, then it takes half the button. */
  .fit > :global(.icon-btn.md) svg {
    width: min(19px, 50%);
    height: auto;
    aspect-ratio: 1;
  }
}
```
**Impact:** Only elements with the hashed `.fit` class are affected.

### Step 3: `.switch` stops being a flex row
**File:** `web/app/(app)/leaderboard/leaderboard.module.css:45`
**Change:** `.switch` holds just the nav. As a flex container it sized the nav to the nav's max-content
width and shrank it from there, and with a `minmax(0, …)` grid that minimum is close to zero. A block
wrapper gives the nav the sheet's full content width, which is the width the grid divides. The
`gap: 6px` was never used, since the nav is the only child.
**Code:**
```css
.switch { padding-bottom: 8px; }
```
(was: `.switch { display: flex; gap: 6px; padding-bottom: 8px; }`)
**Impact:** No other rule reads `.switch`, and it has no desktop override (checked: the only match in the file is line 45). On mobile the visible row is unchanged: the nav is still a wrapping flex row, now as wide as the sheet instead of shrink-wrapped by a flex parent, which breaks it at the same buttons. Phase 3's leaderboard.module.css edits (after line 78, line 206, after line 219, end of file) do not touch line 45.

### Step 4: Turn `fit` on for the checklist sheet
**File:** `web/app/(app)/leaderboard/page.tsx` in `checklistSheet`, lines 162-163 as Phase 1 leaves
the file (lines 154-155 at `22d1051`; Phase 1's 9-line `board` block at line 33 moves it down 8).
Find the `StrategySwitch` inside `<div className={s.switch}>`.
**Change:** Add `fit` after `label="Strategy"`. Change nothing else in the element. Phase 1 leaves the
element as it is at `22d1051`.
**Code:** the line that today reads
```tsx
            href={id => `/leaderboard?s=${encodeURIComponent(id)}`} label="Strategy" />
```
becomes
```tsx
            href={id => `/leaderboard?s=${encodeURIComponent(id)}`} label="Strategy" fit />
```
After Phase 1 and this step, the block (lines 160-165) reads:
```tsx
      {pick && switchable.length > 1 && (
        <div className={s.switch}>
          <StrategySwitch strategies={switchable} current={pick.id}
            href={id => `/leaderboard?s=${encodeURIComponent(id)}`} label="Strategy" fit />
        </div>
      )}
```
**Decision (reconciled): the one-row grid is desktop only.** The phone row is 342px, and 7 × 46 + 36 =
358, so it wraps there too, but plan invariant 2 holds the mobile leaderboard layout unchanged apart
from colours and icons, and the index's Phase 2 exit criteria name only 1024/1280/1440. The split costs
one media query in `StrategySwitch.module.css` (Step 2), not a second render. Recorded in the plan
index's Decisions.
**Impact:** The leaderboard checklist switcher only.

### Step 5: Unit test for the component contract
**File:** `web/components/StrategySwitch.test.tsx` (new)
**Change:** Render with `renderToStaticMarkup`, which is the existing pattern in `PaperChip.test.tsx` and
`RetiredShelf.test.tsx`. `next/link` is stubbed to a plain `<a>`, because no existing test renders a
real app-router `Link` outside a router. The stub is the component's dependency, not the unit under
test. The tests check observable markup: default mode has no inline style and keeps the wrapping
class, `fit` carries the right `--n` and every item, and `seg` wins over `fit`. Whether one row really
renders is a layout question, and the browser journey in Proof answers it.
**Code:**
```tsx
import type { AnchorHTMLAttributes, ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('next/link', () => ({
  default: ({ href, children, replace: _r, scroll: _s, ...rest }:
    AnchorHTMLAttributes<HTMLAnchorElement> & { href: string; replace?: boolean; scroll?: boolean; children?: ReactNode }) =>
    <a href={href} {...rest}>{children}</a>,
}));

import { StrategySwitch } from './StrategySwitch';
import s from './StrategySwitch.module.css';

const roster = (n: number) =>
  Array.from({ length: n }, (_, i) => ({ id: `S${i}`, name: `Strategy ${i}`, icon: 'zap' }));
const navOpen = (html: string) => html.match(/^<nav[^>]*>/)?.[0] ?? '';
const links = (html: string) => html.match(/<a /g)?.length ?? 0;
const href = (id: string) => `/leaderboard?s=${id}`;

describe('StrategySwitch', () => {
  it('default mode: the loose wrapping row, no inline style', () => {
    const html = renderToStaticMarkup(
      <StrategySwitch strategies={roster(7)} current="S0" href={href} label="Strategy" />);
    const nav = navOpen(html);
    expect(nav).not.toContain('style=');
    expect(nav).toContain(`class="${s.group}"`);
    expect(links(html)).toBe(7);
  });

  it('fit: one column per button, the count handed to CSS as --n', () => {
    for (const n of [7, 12]) {
      const html = renderToStaticMarkup(
        <StrategySwitch strategies={roster(n)} current="S1" href={href} label="Strategy" fit />);
      const nav = navOpen(html);
      expect(nav).toContain(`class="${s.fit}"`);
      expect(nav).toContain(`style="--n:${n}"`);
      expect(links(html)).toBe(n);
      // Still icon-only, named and tipped, with the pick marked.
      expect(html).toContain('aria-label="Strategy 1" aria-current="true"');
      expect(html).toContain(`data-tip="Strategy ${n - 1}"`);
    }
  });

  it('fit counts the leading all-strategies button', () => {
    const html = renderToStaticMarkup(
      <StrategySwitch strategies={roster(7)} current="all" href={href} label="Strategy filter" allTip="All strategies" fit />);
    expect(navOpen(html)).toContain('style="--n:8"');
    expect(links(html)).toBe(8);
  });

  it('seg wins over fit: the pill sizes its own buttons', () => {
    const html = renderToStaticMarkup(
      <StrategySwitch strategies={roster(7)} current="S0" href={href} label="Strategy" seg fit />);
    const nav = navOpen(html);
    expect(nav).toContain('class="seg"');
    expect(nav).not.toContain('style=');
  });
});
```
If vitest's CSS-module stub gives `s.group`/`s.fit` as `undefined` (it does not process CSS by default),
the `class="${s.group}"` assertions fail on a `class="undefined"` string. In that case replace those two
assertions with `expect(nav).not.toBe(navOpen(<the fit render>))`, comparing the default nav tag with the
fit nav tag. Keep the `style` assertions as they are, since they carry the contract. Run the file first
to see which case applies.
**Impact:** New test file only.

### Step 6: Browser journey for one row
**File:** `.claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs` (new)
**Change:** A `verify.sh ui` steps file, desktop widths only (it refuses a viewport under 1024 px). The demo roster has fewer than 7 research strategies, so after
checking the real row the journey clones the last button in the live DOM until there are 7 and then 12,
sets `--n` to match (as the server would), and measures the real CSS at the run's viewport width. It
also checks the neighbour: `/positions`' default-mode switcher is still a wrapping flex row of 46px
buttons.
**Code:**
```js
// R2 (leaderboard-desktop-revamp phase 2): the go-live checklist's strategy switcher is one row at any
// count on desktop (below 1024px it is the unchanged loose row). Demo data has fewer than 7 research
// strategies, so after checking the real row this clones buttons in the live DOM up to 7 and 12, sets
// --n the way StrategySwitch would, and measures the real stylesheet. Run at each desktop width:
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs --width 1280
const SHEET_NAV = 'section:has(> div > nav[aria-label="Strategy"]) nav[aria-label="Strategy"]';

const measure = page => page.locator(SHEET_NAV).first().evaluate(nav => {
  const sheet = nav.closest('section');
  const pad = parseFloat(getComputedStyle(sheet).paddingRight);
  const contentRight = sheet.getBoundingClientRect().right - pad;
  const btns = [...nav.querySelectorAll(':scope > a')].map(a => {
    const r = a.getBoundingClientRect();
    const svg = a.querySelector('svg').getBoundingClientRect();
    return { top: Math.round(r.top), left: r.left, right: r.right, w: r.width, h: r.height, icon: svg.width,
      current: a.getAttribute('aria-current') === 'true', bg: getComputedStyle(a).backgroundColor };
  });
  return { n: btns.length, btns, contentRight, overflow: nav.scrollWidth - nav.clientWidth };
});

const check = (m, label) => {
  const rows = new Set(m.btns.map(b => b.top));
  if (rows.size !== 1) throw new Error(`${label}: ${m.n} buttons sit on ${rows.size} rows (tops ${[...rows].join(',')})`);
  if (m.overflow > 1) throw new Error(`${label}: row overflows its nav by ${m.overflow}px`);
  const last = m.btns[m.btns.length - 1];
  if (last.right > m.contentRight + 1) throw new Error(`${label}: last button ends ${last.right - m.contentRight}px past the sheet's padding`);
  for (const b of m.btns) {
    if (Math.abs(b.w - b.h) > 1) throw new Error(`${label}: a button is not round (${b.w}x${b.h})`);
    if (b.w < 20) throw new Error(`${label}: a button shrank to ${b.w}px`);
    if (b.w > 46.5) throw new Error(`${label}: a button grew past 46px (${b.w})`);
    if (b.icon > b.w - 4) throw new Error(`${label}: icon ${b.icon}px does not fit its ${b.w}px button`);
  }
  const widths = m.btns.map(b => b.w);
  if (Math.max(...widths) - Math.min(...widths) > 1) throw new Error(`${label}: unequal buttons ${widths.join(',')}`);
  const cur = m.btns.find(b => b.current);
  if (!cur || cur.bg === 'rgba(0, 0, 0, 0)') throw new Error(`${label}: the picked button lost its ink fill`);
  return `${label}: ${m.n} buttons, one row, ${widths[0].toFixed(1)}px each, icon ${m.btns[0].icon.toFixed(1)}px`;
};

const growTo = (page, n) => page.locator(SHEET_NAV).first().evaluate((nav, n) => {
  const proto = [...nav.querySelectorAll(':scope > a')].find(a => a.getAttribute('aria-current') !== 'true');
  while (nav.querySelectorAll(':scope > a').length < n) {
    const c = proto.cloneNode(true);
    const k = nav.querySelectorAll(':scope > a').length;
    c.setAttribute('aria-label', `Clone ${k}`); c.setAttribute('data-tip', `Clone ${k}`);
    nav.appendChild(c);
  }
  nav.style.setProperty('--n', String(n));
}, n);

export default async ({ page, base, shot, log }) => {
  if ((page.viewportSize()?.width ?? 0) < 1024) throw new Error('run at --width 1024, 1280 or 1440: the one-row fit is desktop only');
  await page.goto(base + '/leaderboard', { waitUntil: 'networkidle' });
  await page.locator(SHEET_NAV).first().waitFor();

  log(check(await measure(page), 'real roster'));
  const first = page.locator(`${SHEET_NAV} > a`).first();
  const tip = await first.getAttribute('data-tip');
  await first.hover();
  await page.getByRole('tooltip').filter({ hasText: tip }).waitFor({ timeout: 5000 });
  log(`tooltip "${tip}" shows on hover`);
  await page.mouse.move(0, 0);

  for (const n of [7, 12]) {
    await growTo(page, n);
    log(check(await measure(page), `${n} strategies`));
    await page.locator(SHEET_NAV).first().scrollIntoViewIfNeeded();
    await shot(`switch-${n}`);
  }

  // Neighbour: positions keeps the default loose row (46px circles, flex-wrap), untouched by fit.
  await page.goto(base + '/positions', { waitUntil: 'networkidle' });
  const pos = await page.locator('nav[aria-label="Strategy"]').first().evaluate(nav => ({
    display: getComputedStyle(nav).display, wrap: getComputedStyle(nav).flexWrap, style: nav.getAttribute('style'),
    w: nav.querySelector('a').getBoundingClientRect().width,
  }));
  if (pos.display !== 'flex' || pos.wrap !== 'wrap' || pos.style !== null || Math.abs(pos.w - 46) > 0.5)
    throw new Error(`positions switcher changed: ${JSON.stringify(pos)}`);
  log('positions: default switcher unchanged (flex, wrap, 46px, no inline style)');
};
```
**Impact:** New verification file only. It is not run by CI.

### Step 7: Feature map
**File:** `.claude/skills/verify-seer/features/leaderboard.md`, the "How to get to it" paragraph (line 13 at `22d1051`; Phase 1 adds one line above it, so line 14 as Phase 1 leaves the file) and the `Driving it with verify.sh` code block.
**Change:** Replace only the sentence `The checklist switches strategy with its own icon row.` with:
```markdown
The checklist switches strategy with its own icon row: on desktop always one row, its round buttons shrinking together once the strategies outnumber the 46px circles the sheet can hold (about 41px at 7 strategies, about 23px at 12); on a phone it wraps as before.
```
and add this line to the `Driving it with verify.sh` block, directly after the `leaderboard-twin.mjs` line, which Phase 1 leaves reading
`$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs   # order, partner colour, own icon, unique sheets and icons, dash, chip, rule 5; result: PASS`:
```sh
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs --width 1280   # one row at the real count, at 7 and at 12; positions unchanged
```
**Impact:** Doc only. Phases 1 and 3 edit other sentences of this file.

## Principles applied

- Laziness protocol: a single opt-in boolean on the existing component plus one CSS rule set, and no new switcher component. `minmax(0, 46px)` columns mean a row that already fits looks the same; the grid sits behind the 1024 px query so the phone layout is untouched.
- Make illegal states unrepresentable: `seg` and `fit` both size buttons. Rather than leaving the combination undefined, `seg` explicitly wins (`fitted = fit && !seg`) and a test pins it, so the two sizing systems can never stack.
- Subtract before you add: `.switch` loses `display:flex; gap` (dead gap, and a flex wrapper that would have starved the grid) instead of gaining more flex overrides.
- Prove it works / Test behavior, not implementation: the unit test only pins the markup contract (`--n`, class, item count). The one-row claim is measured in a real browser at 1024/1280/1440 with 7 and 12 buttons, with tops, widths, overflow and the sheet's padding edge read from the rendered page; 390 is checked unchanged by screenshot.
- Fix root causes: the cause is traced to `StrategySwitch.module.css:1` (`flex-wrap: wrap`) together with fixed `.icon-btn.md` 46px (`globals.css:168`) in a fixed 324px row. The journey reproduces it at 7 before the fix.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/leaderboard-desktop-revamp/web && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/leaderboard-desktop-revamp/web && npm test` (and alone: `npx vitest run components/StrategySwitch.test.tsx`)
**Proof:**
- Harness: `.claude/skills/verify-seer` (`scripts/verify.sh`), run from the worktree root. If `web/node_modules` is missing in the worktree, hard-link it (memory: a symlink breaks `next build`) before `up`.
- Feature-map entries: `.claude/skills/verify-seer/features/leaderboard.md`
- Journeys (`V=.claude/skills/verify-seer/scripts/verify.sh`, `RUN` = the id `$V up` prints):
  1. **Reproduce (before the fix).** On a checkout without this phase (`git stash` the phase, or run against the Phase-1 commit): `$V up`, then `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs --width 1280`. Expected: **FAIL** with `7 strategies: 7 buttons sit on 2 rows`. (If the steps file is not in that checkout yet, copy it into the scratchpad and pass that path.) `$V down RUN` after.
  2. **One row, desktop.** With the phase applied: `$V up`, then run the steps file at `--width 1024`, `--width 1280` and `--width 1440` (`--theme light` once, the default dark for the others). Passing end state for each: `result: PASS`, with log lines `real roster: N buttons, one row, 46.0px each`, `7 strategies: 7 buttons, one row, ~41px each` and `12 strategies: 12 buttons, one row, ~23px each, icon ~11-12px`, plus `tooltip "<name>" shows on hover`. Open `evidence/*switch-12*.png` and check visually that there are 12 round icons on one line inside the sheet.
  3. **Phone unchanged.** `$V shoot RUN --theme light --width 390 /leaderboard` exits 0, and the PNG shows the checklist switcher as the same loose row of 46px circles as before (the demo roster fits it on one line). The steps file refuses `--width 390` by design.
  4. **Screenshots with no horizontal scroll:** `$V shoot RUN --theme both --width 390 --width 1024 --width 1280 --width 1440 /leaderboard` exits 0 (shoot fails on horizontal scroll and console errors).
- Neighbor check: the same steps file ends on `/positions` and asserts its default switcher is still `display:flex; flex-wrap:wrap`, with 46px buttons and no inline style. Pass log line: `positions: default switcher unchanged`. Also `$V shoot RUN --width 390 --width 1280 '/history'`, which must exit 0 (history uses `seg` and must not take on `fit`).
- Cost: none (no LLM drives).
**Exit criteria:** `tsc` and `npm test` are green. `leaderboard-switch-row.mjs` passes at 1024, 1280 and 1440 with the real roster, 7 and 12 buttons on one row, the picked button ink-filled and its tooltip shown. The 390 leaderboard shot exits 0 with the switcher unchanged. `/positions` and `/history` shots pass unchanged.

## Handoffs

- **Plan index (reconciled):** the Phase 2 section now says "shrinks to fit, no floor; ≥ 32px up to 8 strategies, ~23px at 12", desktop only.
- **Phase 3:** if the stack layout changes `.top`'s `380px` checklist column, fit adapts automatically. Phase 3's screenshots should still show the switcher on one row, and re-running `leaderboard-switch-row.mjs` covers it.
- **Phase 1:** `leaderboard-twin.mjs` is untouched here. Phase 1 adds no prop to `StrategySwitch` and does not change its `strategies` element type.

## Rollback

Revert this phase's single commit. Because `fit` is opt-in, reverting just the `page.tsx` line (Step 4)
returns the leaderboard to the old wrapping row and leaves the component change harmless.
