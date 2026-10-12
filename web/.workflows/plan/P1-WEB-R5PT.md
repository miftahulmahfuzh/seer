> Adopted from `/home/miftah/seer/.workflows/orchestration/sera-responsive/PLAN.md` phase 1. Source: `.workflows/plan/sera-responsive/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: The narrow nav and the shell

**Plan set:** `SERA_RESPONSIVE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-165855-R4C9_code_analyzer.md`
**Satisfies:** R1 (a *designed* narrow layout — Sera's phone navigation), R2 (zero horizontal scroll, for the four routes whose only cause is the nav)
**Depends on:** none
**Difficulty:** HARD
**Package:** `web/components/sera`, `web/app/sera`
**Port:** 3121

---

## Goal

Below 1024px Sera stops rendering a 456px-wide non-wrapping rail across the top of the viewport and
instead ships Seer's own finished phone navigation: the `desk-only` rail stays exactly as it is, and
a `mobile-only` floating pill bar carries the six section tabs at Seer's exact 52px metrics. The
shell reserves the bar's space with the existing `--nav-clear` token, and the way back to Seer moves
beside the sign-out button in `PageHeader`. After this phase `/sera`, `/sera/journal`,
`/sera/gotrade` and `/sera/how` measure exactly the viewport width at 390 and 414; 1280 is
byte-identical to `09515d1`.

## Interface Contract

**Creates:**
- `SeraNav.module.css` `.bar` — the fixed bottom pill, 348px × 68px, `z-index: 50`
- `SeraNav.module.css` `.barTabs` — `grid-template-columns: repeat(6, 1fr)`, the bar's inner tab grid
- `SeraNav.tsx` `Tabs` (module-private) — the six links, shared by rail and bar
- `SeraNav.tsx` `SeraBackLink` (**exported, client**) — the `mobile-only` back-to-Seer `icon-btn`,
  rendered by `PageHeader`; returns `null` outside `/sera/**`
- `SeraNav.tsx` `inSera(path)` (module-private predicate)

**Deletes:**
- `SeraNav.module.css` the whole `@media (max-width: 1023.98px)` block (`SeraNav.module.css:75-98`
  — the file is 98 lines; the analysis's Reference List cite of `:88-104` is stale)
  — the placeholder top bar, the 44px tab override, the `.back` reflow, **and** the narrow `.badge`
  override
- `app/sera/sera.module.css:18` — `.shell { flex-direction: column }` inside the narrow block

**Renames:** none. (`.tabs` keeps its meaning — the *rail's* vertical pill. The bar's grid is a new
class, `.barTabs`, precisely so no existing selector is renamed.)

**Signature changes:**
- `SeraNav()` returns a React fragment (`<aside> + <nav>`) instead of a single `<aside>`. Its props
  are unchanged (`{ journalUnseen?: number }`), so `app/sera/layout.tsx:40` needs **no edit**.
- `PageHeader()` props are unchanged. Its `.aside` gains one more child.

**Changed (CSS surface other phases must know about):**
- `app/sera/sera.module.css` narrow `.main`: `padding: 0 16px 40px` → `padding: var(--safe-top) 16px var(--nav-clear)`.
  Side padding is **unchanged at 16px**, so the narrow content width at 390 is still 358px and at
  414 still 382px. The bottom reservation for the floating bar is made **once, here**.
- `PageHeader.module.css` narrow `.aside` gains `flex-wrap: wrap`.
- The `≥1024` `.main { padding: 0 40px 56px 12px }` is **untouched** — correct beside the 104px
  rail, measured clean at 1280.

**Requires (from earlier phases):** none — this is wave 1.

**Leaves alone (owned by others):**
- `components/sera/Term.*` (Phase 2)
- `app/sera/methods/**` (Phases 3, 4)
- `app/sera/ideas/*`, `app/sera/overview.module.css`, `components/sera/Stat.module.css`,
  `app/sera/how/how.module.css` (Phase 5)
- `app/globals.css`, `components/Nav.tsx`, `components/Nav.module.css`, `components/tooltip.ts` —
  **read-only precedent**, reused verbatim, nothing added to them
- `app/sera/layout.tsx` — no change needed
- `app/sean/**`, `components/sean/SeanNav.*` — out of scope for the whole plan set

## Files

| File | Action | What changes |
|---|---|---|
| `web/components/sera/SeraNav.tsx` | modify | dual render: `desk-only` rail + `mobile-only` fixed bar; tab markup factored into one `Tabs`; new exported `SeraBackLink` |
| `web/components/sera/SeraNav.module.css` | modify | drop the narrow media block entirely; add `.bar` and `.barTabs` at Seer's metrics |
| `web/app/sera/sera.module.css` | modify | narrow `.main` reserves `--nav-clear` and takes over `--safe-top`; narrow `.shell` column flip deleted |
| `web/components/sera/PageHeader.tsx` | modify | render `<SeraBackLink />` in `.aside`, immediately before the sign-out form |
| `web/components/sera/PageHeader.module.css` | modify | narrow `.aside` wraps |

---

## The four decisions this plan implements, and why each is safe

These were handed down; this section records the *mechanical* reason each works on this tree, so
`/implement` does not have to re-derive it.

**D1 — Seer's own bottom pill bar.** `components/Nav.tsx:46` already ships exactly this shape.
`app/(app)/shell.module.css` is **byte-identical** to `app/sera/sera.module.css`'s base rules
(`.shell { min-height: 100dvh; display: flex }`, `.main { flex: 1; min-width: 0 }`) and has **no**
narrow `flex-direction: column` rule at all — the bar works there as a `position: fixed` child of
that same flex shell. A fixed-position child of a flex container is not a flex item, and nothing in
the `body → div.shell` chain sets `transform`, `filter`, `perspective`, `contain` or `will-change`
(checked: `globals.css:120-129` and `sera.module.css:1`), so the bar positions against the viewport.
This is precedent, not a guess.

**D2 — no wordmark below 1024.** `PageHeader` prints the eyebrow on all seven routes
(`app/sera/page.tsx:62`, `journal/page.tsx:87`, `methods/page.tsx:54`, `methods/[id]/page.tsx:67`,
`ideas/page.tsx:26`, `gotrade/page.tsx:24`, `how/page.tsx:45` — verified, every one). The section is
still named.

**D3 — back-to-Seer in `PageHeader`'s aside — with one correction the decision could not have
known.** `PageHeader` is **not** Sera-only. It is imported by `app/sean/page.tsx:2`,
`app/sean/plan/page.tsx:4` and `app/sean/trades/page.tsx:2` as well. An unconditional
`mobile-only` "Back to Seer" would appear on `/sean`, which this plan set puts out of scope
(index §Scope) and which already reaches `/` through Seer's own four-tab bar. The control is
therefore route-guarded. Since `PageHeader` is a **server** component carrying an inline
`'use server'` action (`PageHeader.tsx:42`) it cannot call `usePathname` itself, and
`node_modules/next/dist/docs/01-app/03-api-reference/04-functions/use-pathname.md` is explicit:
*"Reading the current URL from a Server Component is not supported."* The guard therefore lives in a
small client component exported from `SeraNav.tsx` — a file I own that is **already** `'use client'`
and already imports `Link`, `Eye` and `usePathname`. A server component rendering a client component
is the documented composition pattern
(`node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`).
There is no `middleware.ts`/`proxy.ts` and no `rewrites` in `next.config` (verified), so the
hydration caveat that doc raises for rewritten routes does not apply.

**Geometry.** `6 × 52 + 5 × 4 gap + 2 × 8 padding = 348px`. Measured live with the rail hidden:
`/sera @390 → 390` (21px gutter each side), `/sera @414 → 414` (33px gutter). Not re-derived here.

---

## Implementation Steps

### Step 1: `SeraNav.tsx` — dual render, shared tabs, and the guarded back link
**File:** `web/components/sera/SeraNav.tsx` (whole file, replacing lines 1-58)
**Change:** the component returns a fragment: the existing rail with `desk-only` added, plus a new
`mobile-only` fixed bar carrying the same six tabs. The tab markup — badge, tooltip, `aria-label`,
`aria-current` — is factored into one module-private `Tabs` so rail and bar can never drift
(the same shape `components/Nav.tsx:53` uses). A second export, `SeraBackLink`, carries the back
control that the bar no longer has room for.

Both containers are `<nav aria-label="Sera sections">`. That is **two** identically-labelled
landmarks in the markup, and it is deliberate: `.desk-only` / `.mobile-only` are
`display: none !important` (`globals.css:245-250`), and a `display: none` subtree is removed from
the accessibility tree entirely — so exactly one of the two is ever exposed, which is invariant 10's
rule applied to navigation. (`components/Nav.tsx` instead makes its rail container a plain `div`,
leaving desktop with no sections landmark at all; Sera keeps one at both widths.)

**Code:**
```tsx
'use client';

import { Ban, Eye, FlaskConical, LayoutDashboard, Lightbulb, NotebookPen, Workflow } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './SeraNav.module.css';

const TABS = [
  { href: '/sera', icon: LayoutDashboard, tip: 'Overview' },
  { href: '/sera/methods', icon: FlaskConical, tip: 'Methods' },
  { href: '/sera/journal', icon: NotebookPen, tip: 'Journal' },
  { href: '/sera/ideas', icon: Lightbulb, tip: 'Ideas' },
  { href: '/sera/gotrade', icon: Ban, tip: 'Not on Gotrade' },
  { href: '/sera/how', icon: Workflow, tip: 'How it works' },
];

/** The one tab that carries an unseen badge. The others count nothing. */
const BADGED = '/sera/journal';

/** A count fit to print: a whole number above zero, or 0, which renders no badge at all. */
const badgeCount = (n: number): number => (Number.isFinite(n) && n > 0 ? Math.floor(n) : 0);

/** Inside the lab. PageHeader is shared with /sean, which has its own way home and must not grow a second. */
const inSera = (path: string): boolean => path === '/sera' || path.startsWith('/sera/');

/**
 * Sera's navigation, in two shapes, the same two Seer's own Nav ships (components/Nav.tsx):
 * a vertical rail on a desk, and a floating pill bar at the bottom of a phone. The 1024 px switch
 * is globals.css's `.desk-only` / `.mobile-only`, not a media query here — one switch for the
 * whole app, so the nav can never disagree with the stylesheets about where the break is.
 *
 * The phone bar carries the six section tabs and nothing else. It has no wordmark because Seer's
 * bar has none either and because PageHeader already prints "Sera · the method lab" as the eyebrow
 * at the top of every page; dropping it is what leaves room for all six tabs at the rail's full
 * 52 px size (6 × 52 + 5 × 4 gap + 2 × 8 padding = 348 px, which clears the 390 px floor with
 * 21 px of gutter either side). The way back to Seer moved out of the bar for the same reason and
 * now sits beside sign-out in PageHeader — see SeraBackLink below.
 *
 * `journalUnseen` is the number of journal entries not yet seen, read server-side in
 * app/sera/layout.tsx. It exists so a new entry is visible from the other Sera pages, not only
 * from /sera/journal, where the seven badges already say it. Zero (or absent) means no badge --
 * unlike the Journal's own badges, which keep a muted zero pill to keep the row of seven even.
 */
export function SeraNav({ journalUnseen = 0 }: { journalUnseen?: number }) {
  const path = usePathname() ?? '';
  return (
    <>
      <aside className={`${s.rail} desk-only`}>
        <span className={s.wordmark}>
          Sera<span className={s.dot}>.</span>
        </span>
        <nav className={s.tabs} aria-label="Sera sections">
          <Tabs path={path} unseen={journalUnseen} />
        </nav>
        <Link href="/" className={`icon-btn ${s.back}`} data-tip="Back to Seer" aria-label="Back to Seer">
          <Eye size={21} strokeWidth={1.5} />
        </Link>
      </aside>
      {/* data-tip-anchor: tooltip.ts lifts a caption clear of the whole bar rather than one 52 px
          tab, which is what stops a long-press caption landing on top of its neighbours. */}
      <nav className={`${s.bar} mobile-only`} aria-label="Sera sections" data-tip-anchor>
        <div className={s.barTabs}>
          <Tabs path={path} unseen={journalUnseen} />
        </div>
      </nav>
    </>
  );
}

/**
 * The six tabs themselves, rendered into whichever container asked for them. One definition, so a
 * tooltip, an aria-label or the Journal badge cannot end up right in the rail and wrong in the bar.
 */
function Tabs({ path, unseen }: { path: string; unseen: number }) {
  return (
    <>
      {TABS.map(({ href, icon: Icon, tip }) => {
        const active = href === '/sera' ? path === '/sera' : path === href || path.startsWith(`${href}/`);
        const n = href === BADGED ? badgeCount(unseen) : 0;
        return (
          <Link key={href} href={href} className={active ? s.active : s.tab}
            data-tip={n > 0 ? `${tip} · ${n} new` : tip}
            aria-label={n > 0 ? `${tip}, ${n} new` : tip}
            aria-current={active ? 'page' : undefined}>
            <Icon size={22} strokeWidth={active ? 1.75 : 1.5} />
            {n > 0 && <span className={s.badge} aria-hidden="true">{n > 99 ? '99+' : n}</span>}
          </Link>
        );
      })}
    </>
  );
}

/**
 * The way back to Seer on a phone. The bar below 1024 px is six section tabs and no more, so this
 * leaves-the-area control goes where the other one already is: beside sign-out in PageHeader's
 * aside. The desktop rail keeps its own `.back` and never renders this.
 *
 * It is a client component on purpose. PageHeader is a server component (it holds the sign-out
 * server action) and is shared with /sean, which reaches home through Seer's own tab bar and must
 * not grow a second route out; a server component cannot read the pathname, so the route test lives
 * here. Rendered outside /sera it is nothing at all.
 */
export function SeraBackLink() {
  const path = usePathname() ?? '';
  if (!inSera(path)) return null;
  return (
    <Link href="/" className="icon-btn mobile-only" data-tip="Back to Seer" aria-label="Back to Seer">
      <Eye size={21} strokeWidth={1.5} />
    </Link>
  );
}
```
**Impact:** `app/sera/layout.tsx:40` is unchanged — `SeraNav` still takes the same one prop and the
fragment's two children simply become two children of `div.shell`. `/sean` and `app/(app)/**` render
identically: `SeraBackLink` returns `null` there. Both new exports are icon-only with an
`aria-label` **and** a `data-tip` (invariant 4).

### Step 2: `SeraNav.module.css` — the placeholder top bar out, Seer's pill bar in
**File:** `web/components/sera/SeraNav.module.css` (whole file, replacing lines 1-98)
**Change:** three things, and nothing else.

1. The leading comment and `.rail` are unchanged except for their prose — the rail is now
   `desk-only`, so its "always shown" comment is no longer true.
2. `.bar` and `.barTabs` are added, copied from `components/Nav.module.css:1-20` with one number
   changed: `width: 276px` (4 tabs) becomes `348px` (6 tabs), and the grid is `repeat(6, 1fr)`
   instead of `repeat(4, 1fr)`. Everything else — `bottom`, `height`, `border-radius`, `background`,
   `padding`, `z-index`, `box-shadow`, `gap` — is Seer's value verbatim. `.tab` / `.active` are
   reused as they stand; in a 348px bar, `(348 − 16 padding − 20 gap) / 6 = 52px`, so the grid
   track lands on exactly the `min-width: 52px` the rail already uses.
3. **The whole `@media (max-width: 1023.98px)` block is deleted** — every line of it. The rail is
   hidden by `.desk-only` and the bar by `.mobile-only`, so no media query is needed in this file at
   all, and the 44px tab override and the `.back` reflow have nothing left to act on.

**The badge** (item 2 of the brief, answered exactly): the narrow `.badge` override at
`SeraNav.module.css:88-97` is deleted and **no narrow badge CSS replaces it**. The desktop metrics
(`top: -2px; right: -2px; min-width: 20px; height: 20px`) now apply at every width, which is what
the 52px tab in the bar wants. The arithmetic for "fully inside, not clipped":

- `.bar` has `padding: 8px`, so a tab's top edge is **8px** below the bar's own top edge.
- the badge is `top: -2px` against that tab → its top edge is **6px** inside the bar.
- its `box-shadow: 0 0 0 2px var(--bar)` ring extends 2px further → **4px** inside the bar.
- `.bar`'s background is `var(--bar)`, the same token `.tabs` uses on the rail, so the ring reads as
  a clean 2px separation rather than a halo, in both themes, and on the active tab the existing
  `.active .badge` inversion still applies.
- `.bar` sets no `overflow`, so nothing clips in any case; and the Journal tab is the third of six,
  nowhere near the pill's rounded ends.

Horizontally: `right: -2px` pushes the badge 2px into the 4px gap to the next tab, which is why the
rail's 2px (not the old narrow block's 3px) is the right number here too.

**Code:**
```css
/* Sera's rail: the same one Seer's Nav ships (Nav.module.css), shown on a desk.
   Below 1024 px globals.css's `.desk-only` takes it out entirely and `.bar` below takes over.
   `display: flex` lives in the base rule, so -- unlike Nav's rail, which has none and needs a
   `display: flex !important` at >=1024 to get one back -- no override is needed here. */
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

/* The rail's vertical tab pill. The bar's horizontal one is .barTabs. */
.tabs {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border-radius: 999px;
  background: var(--bar);
}

/* Sera's phone navigation: Seer's own floating pill (Nav.module.css .bar), at Seer's own metrics.
   The only number that differs is the width, because Sera has six sections where Seer has four:
   6 x 52 tab + 5 x 4 gap + 2 x 8 padding = 348 px, which fits the 390 px floor with 21 px of
   gutter each side and 414 with 33 px. There is no wordmark and no back button in here on purpose
   -- that is what pays for the sixth tab at full size (SeraNav.tsx). */
.bar {
  position: fixed;
  left: 50%;
  bottom: max(11px, calc((var(--safe-bottom) - 4px) * 0.7));
  transform: translateX(-50%);
  width: 348px;
  height: 68px;
  border-radius: 999px;
  background: var(--bar);
  padding: 8px;
  z-index: 50;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
}

.barTabs {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 4px;
  height: 100%;
}

/* One tab, whichever pill holds it. In .barTabs the 1fr track resolves to exactly 52 px, so the
   bar and the rail show the same button at the same size. */
.tab, .active {
  position: relative;
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

/* Unseen journal entries. A sibling of the Journal page's own badge
   (app/sera/journal/journal.module.css .badge): same coral pill, same tabular numerals,
   sized for the 52 px tab and ringed so it reads off the tab strip. There is no
   `.zero` variant on purpose -- a zero count renders no badge at all (SeraNav.tsx).

   One size at every width, deliberately. The tab is 52 px in the rail and 52 px in the bar, and
   in the bar this pill sits 6 px below the bar's own top edge (8 px padding less the 2 px offset),
   4 px once its ring is counted -- inside the pill, not cut by it, which is what the shipped
   top-bar placeholder got wrong. The ring is var(--bar), which is the bar's background as well as
   the rail pill's, so it separates cleanly in both themes. */
.badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--coral);
  color: var(--on-coral);
  box-shadow: 0 0 0 2px var(--bar);
  font-size: 11.5px;
  line-height: 20px;
  text-align: center;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}
/* On the active tab the button is already --coral: invert, or the badge disappears into it. */
.active .badge {
  background: var(--on-coral);
  color: var(--coral);
  box-shadow: 0 0 0 2px var(--coral);
}
```
**Impact:** at ≥1024 the only selectors that can match are the ones that matched before
(`.rail`, `.wordmark`, `.dot`, `.tabs`, `.tab`, `.active`, `.back`, `.badge`) with identical
declarations, so desktop cannot move. `.bar` and `.barTabs` only ever appear on an element that also
carries `mobile-only`.

### Step 3: `app/sera/sera.module.css` — the narrow shell reserves the bar's space, once
**File:** `web/app/sera/sera.module.css` (whole file, replacing lines 1-20)
**Change:** the narrow block loses `.shell { flex-direction: column }` and `.main`'s narrow padding
becomes `var(--safe-top) 16px var(--nav-clear)`.

Three decisions recorded, since the brief asks for one mechanism applied once:

1. **Bottom space: `padding-bottom: var(--nav-clear)` on `.main`, not a `.nav-clear` spacer div.**
   Both idioms exist in the app — `app/(app)/today.module.css:17` and
   `app/(app)/history/history.module.css:38` use the padding; `app/(app)/page.tsx:168`,
   `positions/page.tsx:169` and `leaderboard/page.tsx:268` use the spacer. The spacer needs markup
   in each page, and all seven Sera pages belong to other phases (or to none). The padding needs one
   line in the one file that already owns Sera's page box. One line it is.
   `--nav-clear` is `calc(150px + var(--safe-bottom))` (`globals.css:46`) against a bar that is 68px
   tall sitting 11px off the bottom, so the last line of content clears the pill by ~71px.
2. **Top space: `.main` takes over `var(--safe-top)`.** The deleted narrow `.rail` carried
   `padding: calc(10px + var(--safe-top)) …`, and the root layout sets `viewportFit: 'cover'`
   (`app/layout.tsx:18`), so with the top bar gone *something* has to clear the notch. The app's own
   shell puts it on `main` — `app/(app)/shell.module.css:11` is literally
   `padding-top: var(--safe-top)` — so Sera's `main` does the same. In the headless shoot
   `env(safe-area-inset-top)` is `0px`, so this changes no measured number and no PNG; it is correct
   on the owner's actual XS Max.
3. **`.shell { flex-direction: column }` is deleted.** It existed to stack the rail above the main
   column. At narrow the rail is now `display: none` and the bar is `position: fixed` (not a flex
   item), so `.shell` holds `main` alone and row vs column is identical. The proof that this is
   safe rather than clever: `app/(app)/shell.module.css` has the same `.shell { min-height: 100dvh;
   display: flex }`, hosts the same fixed bar, and carries no column flip at any width.

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

/* Below 1024 px neither half of the nav is in flow: the rail is `desk-only` (display: none) and
   the tab bar is a fixed floating pill. So the shell holds `main` alone and needs no column flip
   -- the main app's shell (app/(app)/shell.module.css) is the same two rules and has never had one.
   What `main` does need is the space the fixed bar sits over, and the notch the old top bar used
   to clear. Both come from the tokens that already exist: --nav-clear, the way
   app/(app)/today.module.css and history/history.module.css reserve it, and --safe-top, the way
   app/(app)/shell.module.css does. Reserved once, here, rather than as a spacer in each of the
   seven Sera pages; no page should add its own. The >=1024 padding above is untouched -- it is
   measured correct beside the 104 px rail. */
@media (max-width: 1023.98px) {
  .main { padding: var(--safe-top) 16px var(--nav-clear); }
}
```
**Impact:** narrow side padding is unchanged at 16px, so every Sera page's available content width
is what phases 3-5 measured it to be (358px at 390, 382px at 414). Bottom padding grows from 40px to
150px. Desktop untouched.

### Step 4: `PageHeader.tsx` — the back control beside sign-out
**File:** `web/components/sera/PageHeader.tsx` (whole file, replacing lines 1-50)
**Change:** import `SeraBackLink` and render it in `.aside`, immediately before the sign-out form,
so the two "leave this page" controls sit together on the right. Nothing else moves; props,
the as-of pill and the server action are untouched.

**Code:**
```tsx
import { CalendarClock, LogOut } from 'lucide-react';
import type { ReactNode } from 'react';
import { signOut } from '@/auth';
import { SeraBackLink } from './SeraNav';
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

/**
 * Top of every Sera page: eyebrow, big title, plain lede; as-of date and sign-out on the right.
 *
 * Below 1024 px the header is also the top of the page -- Sera's rail is gone and its tab bar
 * floats at the bottom -- so the eyebrow is what names the section there, and the way back to Seer
 * joins sign-out in the aside because the six-tab bar has no room for it (SeraBackLink renders
 * nothing on a desk, and nothing outside /sera: this header is Sean's too).
 */
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
        <SeraBackLink />
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
**Impact:** at ≥1024 the extra element is `display: none !important`, so desktop is unchanged on all
ten PageHeader call sites. On `/sean/**` it is `null` at every width. On `/sera/**` below 1024 the
aside row becomes, at most, `[as-of pill] [back] [sign-out]`.

### Step 5: `PageHeader.module.css` — the narrow aside wraps
**File:** `web/components/sera/PageHeader.module.css:16-20` (the narrow block)
**Change:** add `flex-wrap: wrap` to `.aside` inside the media query. **`.header`'s narrow
`padding: 24px 4px 12px` does not change** — item 4 of the brief, answered: the notch is now
`main`'s job (Step 3), matching `app/(app)/shell.module.css`, so putting `var(--safe-top)` here as
well would double it on `/sean`, whose shell is a separate file this phase does not own. And 24px
above the eyebrow is right for the top of a page: Seer's own phone pages start their first sheet at
`--safe-top` with 28px of sheet padding, so ~24-28px is the house measure.

`flex-wrap` is insurance, not a fix. Measured at 390 the row is the as-of pill (~176px) + 10 + 52 +
10 + 52 ≈ 300px in a 366px box, so it does not wrap today. But this phase is what adds the third
control to that row, and `.aside` is `flex: none` — without `wrap`, a longer date, a page that
starts passing the `aside` prop, or a larger text setting would push the document sideways instead
of onto a second line. Wrapping works here because `.header` is `flex-direction: column` with
`align-items: flex-start` at this width, so `.aside`'s width is `fit-content`, capped at the
available 366px.

**Code** (the complete narrow block, replacing lines 16-20):
```css
@media (max-width: 1023.98px) {
  /* The top of the page: the rail is gone and the tab bar floats at the bottom, so this header
     is what names the section. 24 px above the eyebrow is the house measure for a page top; the
     notch is cleared by .main (app/sera/sera.module.css), not here, because /sean uses this same
     header behind its own shell. */
  .header { flex-direction: column; align-items: flex-start; gap: 18px; padding: 24px 4px 12px; }
  .title { font-size: 36px; }
  .lede { font-size: 17px; }
  /* Three controls now, once the phone's way back to Seer joins the as-of pill and sign-out
     (SeraBackLink). They measure ~300 px in a 366 px row at 390 px, so they do not wrap today --
     this is what makes a longer date or a page's own `aside` fall to a second line instead of
     scrolling the page sideways. */
  .aside { flex-wrap: wrap; }
}
```
**Impact:** desktop unchanged (the rule is inside the media query). `.aside`'s base
`flex: none; display: flex; align-items: center; gap: 10px` (line 13) is untouched.

---

## Existing tests

Grepped `web/**/*.test.ts(x)` — 48 test files, listed in full and checked:

```
grep -rln 'SeraNav|PageHeader|Back to Seer|Sera sections' --include='*.test.ts' --include='*.test.tsx' .
→ no matches
```

**No test asserts on `SeraNav` or `PageHeader` markup, and none needs updating.** The two component
tests that exist (`app/(app)/leaderboard/PickName.test.tsx`, `components/sera/charts/charts.test.tsx`,
`app/sean/OverviewBody.test.tsx`) render unrelated components; every other Sera test is a pure
`view.ts` / `lib/` unit test. The only Sera test near this phase's blast radius is
`app/sera/journal/seen-client.test.ts`, which tests the seen-marking client module and never mounts
the nav.

Two **untracked** diagnostic leftovers exist in the worktree from the analysis run —
`web/scripts/_probe4.mjs` and `web/scripts/_probe4b.mjs`. They are not this phase's files; do not
commit them with phase 1.

---

## Verification

**Build:**
```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web && npx tsc --noEmit
```

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web && npm test
```

**The acceptance test** (port 3121 — this phase's own, because concurrent phases share the worktree
and `npm run dev:env` hardcodes 3111):
```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
node scripts/with-env.mjs npx next dev -p 3121 &
npm run shoot -- --base http://localhost:3121 --out .shots/p1 --width 390 --width 414 --width 1280 \
  /sera /sera/journal /sera/methods /sera/methods/M0102 /sera/ideas /sera/how /sera/gotrade
```
`--out .shots/pN` matters as much as the port: five sessions share this worktree and `shoot`'s
default `.shots/` would have them overwriting each other's PNGs mid-read. For the same reason,
**never `git stash`, `reset --hard`, or `git add -A` here** — a bare stash pockets the other
sessions' uncommitted work. Commit by pathspec.

`shoot` runs both themes and fails the run on horizontal scroll at any width. Use the
`run-the-web-app` skill; it signs in without a human and self-renews. Never ask the owner to sign in.

**Expected result — exact, and a PARTIAL green is the pass.** `document.documentElement.scrollWidth`
after this phase, derived from the analysis's measured causes (nav 456 removed; the `Term.sr`
escape and the ideas grid-track minimum untouched):

| route | @390 | @414 | @1280 | phase-1 verdict |
|---|---:|---:|---:|---|
| `/sera` | **390** | **414** | 1280 | must be exact |
| `/sera/journal` | **390** | **414** | 1280 | must be exact |
| `/sera/gotrade` | **390** | **414** | 1280 | must be exact |
| `/sera/how` | **390** | **414** | 1280 | must be exact |
| `/sera/ideas` | 476 | 476 | 1280 | **still overflows — Phase 5's work** |
| `/sera/methods` | 959 | 959 | 1280 | **still overflows — Phase 2's work** |
| `/sera/methods/M0102` | 848 | 848 | 1280 | **still overflows — Phase 2's work** |

These three numbers are rows of the plan index's **Residual-overflow ledger**, which is the one
ledger the whole set is scored against. Do not re-derive them here or anywhere else.

Say it plainly so nobody "fixes" it here: **`/sera/methods`, `/sera/methods/[id]` and `/sera/ideas`
will still report PROBLEMS after this phase.** Their remaining causes are the `Term.sr`
containing-block escape (Phase 2) and the `1fr` grid-track minimum plus `.chip`'s `white-space:
nowrap` (Phase 5), neither of which is in this phase's five files. A phase-1 run that made them
green would mean scope was crossed. The pass condition is: **the four nav-only routes are exact, and
the other three have dropped to exactly their non-nav cause (476 / 959 / 848 — not 476+66 etc.).**
Those three numbers are the proof that the nav stopped contributing.

**Manual check — read the PNGs** (this is the R1 half, and a green shoot does not cover it):
- at 390 and 414, light and dark: all six tabs visible inside one floating pill, centred, with
  roughly 21px (390) / 33px (414) of gutter each side, nothing cut by the viewport edge;
- the Journal tab's coral badge sits **inside** the pill, with its ring reading cleanly against the
  bar in both themes — not cut by the bar's top edge as the shipped top bar cut it;
- a back-to-Seer eye button beside the sign-out button in the header row, on every Sera page;
- no "Sera." wordmark and no top bar at narrow widths; the eyebrow names the section instead;
- the last content on each page clears the floating pill rather than disappearing behind it;
- at 1280, every page pixel-identical to `09515d1` — rail, wordmark, back button, badge all in place
  and no back button in the header.
- `/sean` at 390/414/1280 is unchanged (it shares `PageHeader`): **no** eye button in its header.
  Shoot `/sean` once to confirm, even though it is not a Sera route.

**Exit criteria:**
1. `npx tsc --noEmit` and `npm test` both clean.
2. `/sera`, `/sera/journal`, `/sera/gotrade`, `/sera/how` measure **exactly** 390 at 390 and 414 at
   414, in both themes.
3. `/sera/ideas`, `/sera/methods`, `/sera/methods/M0102` measure exactly 476 / 959 / 848 at both
   narrow widths — the nav's 456 is gone from every route.
4. All seven routes measure 1280 at 1280 and render identically to `09515d1`.
5. All six section tabs and a way back to Seer are reachable on a phone, each icon-only with both an
   `aria-label` and a `data-tip`, and the journal badge is not clipped.
6. `/sean` renders exactly as it did at `09515d1`, at every width.

---

## Handoffs

- **Do not reserve bottom space again.** `.main`'s narrow `padding-bottom: var(--nav-clear)` is the
  one mechanism for the whole section (Step 3). Phases 3, 4 and 5 must not add a `.nav-clear`
  spacer div or a second `padding-bottom: var(--nav-clear)` on a page wrapper — that would double
  150px of dead space at the foot of the page.
- **`/sera/methods` and `/sera/methods/[id]` still overflow** at 959 and 848 (R2) — Phase 2 fixes
  the cause (`Term.module.css` `.term { position: relative }`), Phases 3 and 4 then design the card
  presentations (R1). Not touched here.
- **`/sera/ideas` still overflows** at 476 (R2) — Phase 5 owns `minmax(0, 1fr)` and the wrapping
  tag. Not touched here.
- **`/sera`'s two 52px stat values still collide at 390** (R1, invisible to the shoot) — Phase 5
  owns `overview.module.css` `.stats` and `Stat.module.css` `.value`.
- **`/sera/how`'s 960px diagram has no scroll affordance** (R1) — Phase 5.
- **Finding, not work: `components/sean/SeanNav.tsx` carries the same deferred narrow layout** (its
  own comment says *"Same build as SeraNav"*), and `/sean` therefore still shows a placeholder top
  bar on a phone. The plan index puts `/sean` out of scope for this whole set — handover §2: *"Do
  not assume they share the problem or the fix."* This phase deliberately does not touch it, and
  `SeraBackLink`'s route guard exists precisely so `/sean` does not drift. Worth a separate card.
- **Correction to decision D3 for the reconciler:** D3 assumed `PageHeader` is Sera's. It is shared
  with three `/sean` pages, so the back control is route-guarded through a client component exported
  from `SeraNav.tsx` rather than rendered unconditionally. This keeps the change inside the five
  owned files and keeps `/sean` byte-identical. No other phase is affected.
- `web/scripts/_probe4.mjs` and `_probe4b.mjs` are untracked analysis leftovers. Leave them out of
  this phase's commit; whoever finishes the set should delete them.

## Rollback

This phase is one commit touching five files, all under `web/`. To undo it alone:

```bash
git -C /home/miftah/.worktrees/seer/sera-responsive revert <phase-1-sha>
```

or, if it has not been committed yet:

```bash
git -C /home/miftah/.worktrees/seer/sera-responsive checkout 09515d1 -- \
  web/components/sera/SeraNav.tsx \
  web/components/sera/SeraNav.module.css \
  web/app/sera/sera.module.css \
  web/components/sera/PageHeader.tsx \
  web/components/sera/PageHeader.module.css
```

Nothing outside `web/` is touched: no migration runs, no engine file changes, and `lab/lab.sqlite`
and `web/data/lab.json` are never written. Every behavioural change is inside
`@media (max-width: 1023.98px)` or on an element carrying `mobile-only`, so reverting restores the
previous narrow placeholder without ever having moved desktop. The revert is independent of phases
2-5: phase 2 is one declaration in a file this phase does not open, and phases 3-5 only rely on
`.main`'s narrow side padding, which this phase leaves at 16px either way.
