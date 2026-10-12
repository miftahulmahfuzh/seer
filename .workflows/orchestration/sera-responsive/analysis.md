# Code Analysis: Sera's narrow-width layout

**Type:** Feature Implementation (the narrow layout Sera deferred)
**Date:** 2026-10-12 16:58:55 +07
**Session ID:** 20261012-165855-R4C9
**Plan:** `docs/plans/SERA_RESPONSIVE_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/seer/sera-responsive` — branch `feature/sera-responsive`, base `origin/main` @ `09515d1`

---

## User Input

### Original User Request

    /analyze -f docs/plans/HANDOVER_20261012-sera-responsive.md --permission-mode bypassPermissions

The handover file is the specification. Its §1 carries the owner's own words:

> fully revamp xsmax UI to improve responsive UI/UX user experience

"xsmax" is the iPhone XS Max — 414 × 896 CSS px. The repo's screenshot tool already defaults to
390 (iPhone 12/13/14 class) and 1280. The handover's instruction: **treat 390 as the floor to
hold and 414 as the owner's own device, and hold both.**

### User-Provided Context

The handover's framing fact, which this analysis confirms and which must survive into the plan:

> Sera was **deliberately** shipped desktop-first with a placeholder narrow layout. […] Do not
> write the plan as "fix N overflow bugs" — write it as "design the narrow layout that was
> deferred", and let the overflows be the acceptance test.

`components/sera/SeraNav.module.css` says so itself, in two comments:

```css
/* Same rail as Seer's Nav (Nav.module.css), always shown: Sera is desktop-first, not desktop-only. */
/* Below 1024 px: a top bar, not designed further (plan: desktop only for now). */
```

### User-Provided Files

- `docs/plans/HANDOVER_20261012-sera-responsive.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | A **designed** narrow layout for Sera at 390 and 414 — the deferred design, finished, so the pages are good to use on a phone and not merely non-overflowing. |
| R2 | **Zero horizontal scroll** at 390, 414 and 1280 in both themes, on all seven Sera routes — `npm run shoot` green, which is the existing mechanical acceptance test (handover §4). |

R1 is the owner's sentence. R2 is the handover's own exit criterion, and it is separate because a
page can satisfy R2 while failing R1 — `/sera` already scrolls only 66px and still puts a cut-off
tab bar across the top. Handover §4 says this in as many words: *"a green exit only means nothing
threw, and 'doesn't overflow' is not the same as 'is good on a phone'."*

---

## Detailed Requirements Understanding

**Problem statement.** Below 1024px Sera has no designed layout. `SeraNav`'s rail becomes a
non-wrapping flex row that measures 456px wide regardless of viewport; two data tables carry
`min-width: 1200px`/`1240px`; and three stylesheets have no narrow-width rules at all. The owner
uses the section on a 414px phone.

**Success criteria.**

1. `npm run shoot --width 390 --width 414 --width 1280` over all seven Sera routes reports no
   PROBLEMS, in both themes. (R2 — mechanical.)
2. The narrow layout is *designed*, following Seer v2 and the app's own existing phone idiom
   rather than a generic fallback: icon-only Lucide buttons with `aria-label` + `data-tip`, the
   project's sheet/chip/card vocabulary, plain language. (R1 — read the PNGs.)
3. Desktop at 1280 renders **byte-for-byte as it does today**. It is already clean (measured
   below) and is not part of the ask.

**Key considerations / constraints** (handover §5, all from `CLAUDE.md` and load-bearing):

- Read `node_modules/next/dist/docs/` before writing web code — Next 16 / React 19 are newer than
  training data. `web/AGENTS.md` repeats it.
- Every button is icon-only (Lucide) with an `aria-label` **and** a tooltip. A responsive pass is
  exactly where someone adds a text button or drops a tooltip.
- Follow `docs/design/Seer v2.dc.html`; avoid generic styling. A narrow layout that looks like
  Bootstrap is a failed phase even if it stops scrolling.
- `web/` mirrors engine constants (drawdown bar, contribution schedule, fee minimums, resize band)
  and a test asserts they match. Layout work must not go near them.
- `/sera` is read-only over the committed `web/data/lab.json`. No phase needs the database, and
  none writes `lab/lab.sqlite`.

**Assumptions stated.** The dev-only Next.js indicator (the dark circle marked "N" in the
bottom-left of every screenshot below) is Next 16's dev-tools badge, not a layout defect. It does
not appear in `next build` output and no phase should chase it.

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/plans/HANDOVER_20261012-sera-responsive.md`

### Discovered Related Files

| File | How it was reached |
|---|---|
| `web/components/sera/SeraNav.tsx` / `.module.css` | handover §3a; the 456px element |
| `web/app/sera/layout.tsx`, `web/app/sera/sera.module.css` | the shell SeraNav sits in |
| `web/components/sera/Term.tsx` / `.module.css` | **bisected to**, not named in the handover — the actual cause of both tables' overflow |
| `web/app/sera/methods/methods.module.css`, `methods/page.tsx` | handover §3b |
| `web/app/sera/methods/[id]/method.module.css`, `[id]/page.tsx` | handover §3b |
| `web/app/sera/methods/view.ts` | imported by **both** method pages (`[id]/page.tsx` line 20: `from '../view'`) — a shared-file hazard between two otherwise independent phases |
| `web/app/sera/ideas/ideas.module.css` | handover §3; bisected to `.groups` → `.group` → `ul.tags` → `li.chip.tag` |
| `web/app/sera/how/how.module.css`, `components/sera/diagrams/diagrams.module.css` | handover §3 claims an SVG overflow here — **measured clean** |
| `web/app/sera/overview.module.css`, `components/sera/Stat.module.css` | found by auditing which Sera stylesheets carry no narrow-width rules |
| `web/components/Nav.tsx` / `Nav.module.css` | **the design precedent** — Seer's main app already ships a finished phone nav |
| `web/app/globals.css` | `.desk-only` / `.mobile-only`, `--nav-clear`, `--safe-top` / `--safe-bottom`, `.sheet`, `.chip`, `.icon-btn`, `.seg` |
| `web/components/tooltip.ts` | `data-tip-anchor`, named in its own comment as "the mobile tab bar" |
| `web/scripts/shoot.mjs`, `web/scripts/session.mjs` | the acceptance test and its sign-in |
| `web/components/sera/Section.tsx` / `.module.css`, `PageHeader.tsx` / `.module.css` | every Sera page's wrappers |

---

## Measurement method

Everything numeric below was measured on this tree, not inferred. Handover §8 asked for the
throwaway diagnostic to be rebuilt; it was, in three forms, and all three are reproduced verbatim
in **Appendix A** so any phase can recreate them. They are **not committed** — they lived in
`web/scripts/_*.mjs` (so `playwright` resolves from `web/node_modules`, handover §8 trap 1) and
were deleted; the tree is clean.

1. **`_overflow-probe.mjs`** — walks `document.querySelectorAll('*')`, reports every element whose
   `getBoundingClientRect().right` passes the viewport, and — the refinement that cracked it —
   reports whether any ancestor actually clips it, so an element already contained by a scroller
   is excluded instead of drowning the signal.
2. **`_bisect-overflow.mjs`** — hides each child in turn and watches
   `document.documentElement.scrollWidth`, descending into whichever child is responsible. This is
   what found the real cause; `getBoundingClientRect` alone cannot see it.
3. **`_try-fixes.mjs` / `_try2.mjs` / `_try3.mjs`** — apply a candidate fix to the live page and
   re-measure, so every fix in the plan has a before→after number attached.

Run against `npm run dev:env` on `http://localhost:3111`, signed in via
`ensureState('http://localhost:3111')` from `web/scripts/session.mjs`.

---

## Current Dataflow

Sera is a read-only render of one committed JSON file. There is no request-time data flow worth
tracing for this work; the flow that matters is **layout**, so that is what is documented.

### Entry Point: `app/sera/layout.tsx`

**Location:** `web/app/sera/layout.tsx:36`
**Trigger:** every `/sera/**` request. `requireSera()` gates on `SERA_EMAIL`.
**Renders:**

```
div.shell  (sera.module.css: min-height 100dvh; display:flex)
├── <SeraNav journalUnseen={n} />          → aside.rail
└── main.main (flex:1; min-width:0; padding: 0 40px 56px 12px)
    └── div.column (width:100%; max-width:1360px; margin:0 auto; flex column; gap:16px)
        └── {children}                      → PageHeader + Sections
```

At `max-width: 1023.98px` the shell flips to `flex-direction: column` and `.main` becomes
`padding: 0 16px 40px`. That is the entire narrow-width design that exists today.

### The nav, below 1024px

`SeraNav.module.css:88-104`. `.rail` becomes a flex **row** that does not wrap, holding:

| part | width |
|---|---|
| `padding-left` | 16 |
| `.wordmark` "Sera." | 52 |
| `gap` | 16 |
| `.tabs` — 6 × 44px tab + 5 × 6px gap + 2 × 5px padding | 304 |
| `.back` (`margin-left: auto`) | 52 |
| `padding-right` | 16 |
| **total** | **456** |

Measured `.back` right edge = **456px at every viewport**, which is exactly the 66px reported at
390 and the 42px at 414. (The handover says "7 tabs"; there are 6 tabs plus the back button. Same
456.)

### The two tables

`methods.module.css:34` — `.tableWrap { overflow-x: auto; margin: 0 -8px }`, `.table { min-width:
1200px; table-layout: fixed }`, 11 columns.
`[id]/method.module.css:33` — `.tableWrap { overflow-x: auto; margin: 0 -6px }`, `.table {
min-width: 1240px }`.

Markup is `div.tableWrap > table.table` in both (`methods/page.tsx:85`, `[id]/page.tsx:377`).

### Exit Points

`npm run shoot` is the acceptance test and already fails the run on horizontal scroll at any
width. It needs no new tooling.

---

## The one real bug, and its disproof of the obvious theory

The handover (§3b) left this unsolved and warned against guessing:

> `/sera/methods/[id]` **already has** `.tableWrap { overflow-x: auto }` … and the page still
> overflows. … A phase that "adds overflow-x: auto" without explaining the 929-vs-1289 gap has not
> understood the bug.

### First correction: the handover's split of the two tables is wrong

§3b calls `/sera/methods` "straightforward … **no** `overflow-x` container". It has one.
Measured on this tree at 390:

```
div[methods.tableWrap]  overflowX=auto  rect.right=360  clientW=330  scrollW=1200
```

The wrapper is present and is clipping (`clientW` 330 ≪ `scrollW` 1200) — and the document still
reports `scrollWidth=959`. **Both** tables have the same wrapper and the same unexplained gap.
There is one puzzle here, not one puzzle and one easy case.

### The bisection

`_bisect-overflow.mjs` on `/sera/methods` @390:

```
baseline scrollWidth=959 viewport=390
div[sera.shell]      hiding it -> 390   scrollW=959 clientW=390 overflowX=visible
  main[sera.main]    hiding it -> 456   scrollW=959 clientW=390 overflowX=visible
    div[sera.column] hiding it -> 456   scrollW=943 clientW=358 overflowX=visible
      section[sheet] hiding it -> 456   scrollW=943 clientW=358 overflowX=visible  position=relative
        div[methods.tableWrap]  hiding it -> 456   scrollW=1200 clientW=330 overflowX=auto  position=static
```

Note the two numbers that do not belong: `section` has `clientWidth=358` but
`scrollWidth=**943**`, and `.tableWrap` is `position: **static**`.

### The cause, confirmed to the pixel

`components/sera/Term.tsx` renders, inside every glossary term, a visually-hidden span:

```css
/* components/sera/Term.module.css */
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
```

Five of those sit in the table's header cells. A scroll container only clips descendants for which
it is in the **containing-block chain**. `.tableWrap` is `position: static`, so it is *not* the
containing block for an absolutely positioned descendant; the nearest positioned ancestor is
`section.sheet` (`globals.css:218 — .sheet { position: relative }`), which is **outside** the
scroller. The `.sr` spans therefore escape the clip and contribute to the *section's* scrollable
overflow instead.

Measured, with each `.sr`'s own containing-block ancestor resolved:

```
abs descendants inside .tableWrap: 5
  span.Term.sr right=660  cb-positioned-ancestor=section.sheet …
  span.Term.sr right=775  cb-positioned-ancestor=section.sheet …
  span.Term.sr right=835  cb-positioned-ancestor=section.sheet …
  span.Term.sr right=905  cb-positioned-ancestor=section.sheet …
  span.Term.sr right=959  cb-positioned-ancestor=section.sheet …   ← document scrollWidth = 959
```

The last span's right edge is **959**, which is the document's `scrollWidth` exactly. The section's
943 is that 959 less `.main`'s 16px left padding. The gap the handover could not explain is
accounted for to the pixel.

### Candidate fixes, measured live

| applied to `.tableWrap` | `/sera/methods` @390 |
|---|---|
| *(nothing — baseline)* | 959 |
| `position: relative` | **456** |
| `contain: paint` | **456** |
| `overflow: hidden` | 959 |
| remove the 5 abs-positioned descendants | **456** |

`overflow: hidden` changing nothing is the decisive result: the defect is **not** about the
overflow value, so "add `overflow-x: auto`" — the fix the handover warned about — provably could
not have worked. It is about which element is the containing block.

### The fix the plan takes: one line, in `Term`, not in each scroller

Patching `.tableWrap` fixes two scrollers. Patching `Term` fixes every scroller that will ever
hold a glossary term — and `overview.module.css`, `journal.module.css` and `[id]/method.module.css`
all define further `position: static` scrollers (`.prose [data-md-table]`, `.body [data-md-table]`,
`.config`). Measured:

```
span[Term.term] { position: relative }
  /sera/methods        959 -> 456
  /sera/methods/M0102  848 -> 456
```

`.term` is an inline span whose only styling is a dotted underline; giving it `position: relative`
with no offsets changes nothing visually and makes it the containing block for its own `.sr` child,
which is then inside the scroller and clipped normally.

**456 is the nav**, on both routes — i.e. after this one line, the only thing left on the two
heaviest pages is the nav.

---

## Everything else, measured

`document.documentElement.scrollWidth − viewport`, on `main` @ `09515d1`:

| route | @390 | @414 | @1280 | what the bisection blames |
|---|---:|---:|---:|---|
| `/sera` | 66 | 42 | **0** | nav only (`.back` right edge 456) |
| `/sera/journal` | 66 | 42 | **0** | nav only |
| `/sera/gotrade` | 66 | 42 | **0** | nav only |
| `/sera/how` | 66 | 42 | **0** | nav only |
| `/sera/ideas` | 86 | 62 | **0** | nav (456) + `.group` right edge 476 |
| `/sera/methods` | 569 | 545 | **0** | nav (456) + the `Term.sr` escape (959) |
| `/sera/methods/M0102` | 458 | 434 | **0** | nav (456) + the `Term.sr` escape (848) |

### Second correction: `/sera/how`'s SVG does not overflow

The handover blames "the nav top bar **plus** an inline SVG diagram at `min-width: 960px`". The
bisection returns **456 — nav only**. `how.module.css` already contains

```css
@media (max-width: 1023.98px) { .diagram { overflow-x: auto; } .diagram > svg { min-width: 960px; } }
```

and that wrapper works, because an `<svg>`'s children are not absolutely positioned CSS boxes and
so nothing escapes the clip the way `Term.sr` does. The diagram is a **readability** problem on a
phone (a 960px drawing inside a 330px scroller, with no visible affordance that it scrolls), not an
overflow problem. It belongs to R1, not R2.

### Third correction: `/sera/ideas` is a grid-track minimum, not a "non-wrapping idea row"

Bisection @390: `div[ideas.groups] clientW=314` but `div[ideas.group] clientW=**438**` →
`ul[ideas.tags] clientW=402` → `li.chip.tag`.

`ideas.module.css:62` sets `.groups { grid-template-columns: repeat(2, minmax(0, 1fr)) }` and the
narrow media query relaxes it to `grid-template-columns: 1fr`. `1fr` is `minmax(**auto**, 1fr)`,
and an `auto` track minimum is content-based — so the track cannot shrink below the group's
min-content, which is set by the widest `.chip`, and `globals.css:195` gives every `.chip`
`white-space: nowrap`. Measured:

| applied | `/sera/ideas` @390 |
|---|---:|
| *(baseline)* | 476 |
| `.groups { grid-template-columns: minmax(0, 1fr) }` | 458 |
| …plus `.tag { white-space: normal }` | **456** |

Both halves are needed; `minmax(0,1fr)` alone leaves the chip itself 2px over.

### The whole set, with all three fixes applied at once

`_try2.mjs`, all seven routes @390, with the nav merely forced to wrap (a *proof* that the nav is
the remaining cause, **not** the designed fix):

```
/sera                 456 -> 390
/sera/journal         456 -> 390
/sera/gotrade         456 -> 390
/sera/how             456 -> 390
/sera/ideas           476 -> 390
/sera/methods         959 -> 390
/sera/methods/M0102   848 -> 390
```

Every route reaches exactly the viewport width. Three root causes account for 100% of R2.

---

## What R2 does not catch — the R1 findings

Read from the 390px screenshots (`npm run shoot --theme light --width 390`).

**The nav, as shipped.** The bar runs the full width with the wordmark on the left; the back button
is pushed entirely off-screen and the sixth tab is cut by the viewport edge. The journal badge
("99+") is clipped by the bar's own top edge. There is no way back to Seer on a phone at all.

**`/sera/methods`.** Inside the working scroller the reader sees `STATUS` and a truncated `METHOD`
column and nothing else, with no affordance that nine more columns exist to the right. An
11-column, 1200px table is not usable on a 390px screen even when it is perfectly contained —
which is exactly handover §6's point:

> A 1240px table of 15 columns inside a horizontal scroller is technically compliant and still
> miserable to read on a phone.

**`/sera/methods/[id]`.** The same, worse: `min-width: 1240px`, `white-space: nowrap` on every cell.

**`/sera` overview.** `overview.module.css:33` — `.stats { grid-template-columns: repeat(2,
minmax(0,1fr)) }` with no narrow override, and `Stat.module.css` gives `.value` `font-size: 52px;
white-space: nowrap`. Two 52px numbers share a 314px sheet. `minmax(0,1fr)` keeps it from
overflowing the document, so **R2 passes while the tiles collide** — the clearest case in the set
of green-but-bad.

**`/sera/how`.** A 960px diagram in a 330px scroller, no scroll affordance.

### Which stylesheets have no narrow-width design at all

| stylesheet | `max-width:1023.98` rules | `min-width:1024` rules |
|---|---:|---:|
| `app/sera/overview.module.css` | **0** | 2 |
| `app/sera/methods/methods.module.css` | **0** | 1 |
| `app/sera/methods/[id]/method.module.css` | **0** | 1 |
| `components/sera/Stat.module.css` | **0** | 0 |
| `components/sera/Term.module.css` | **0** | 0 |
| `components/sera/charts/charts.module.css` | **0** | 0 |
| `components/sera/diagrams/diagrams.module.css` | **0** | 0 |
| `app/sera/sera.module.css` | 1 | 0 |
| `app/sera/gotrade/gotrade.module.css` | 1 | 0 |
| `app/sera/how/how.module.css` | 1 | 0 |
| `app/sera/ideas/ideas.module.css` | 1 | 0 |
| `app/sera/journal/journal.module.css` | 1 | 0 |
| `components/sera/PageHeader.module.css` | 1 | 0 |
| `components/sera/Section.module.css` | 1 | 0 |
| `components/sera/SeraNav.module.css` | 1 | 0 |

`journal` and `gotrade` already stack sensibly (`.cards → 1fr`, `.bar → column`; `.add` wraps,
`.ticker` goes full width) and need nothing. The zeroes are the work.

---

## The design precedent the plan must follow

This is the single most important discovery for R1, and the handover does not mention it.

**Seer's main app already ships a finished phone navigation**, and Sera should adopt it rather than
invent a second idiom — which is what "follow the Seer v2 design and avoid generic styling"
requires.

`components/Nav.tsx:46` renders two navs and switches them with the global helpers:

```tsx
<aside className={`${s.rail} desk-only`}>  …wordmark, vertical tabs, foot links… </aside>
<nav   className={`${s.bar} mobile-only`} aria-label="Sections" data-tip-anchor> …tabs… </nav>
```

```css
/* Nav.module.css — the mobile bar */
.bar { position: fixed; left: 50%; transform: translateX(-50%);
       bottom: max(11px, calc((var(--safe-bottom) - 4px) * 0.7));
       width: 276px; height: 68px; border-radius: 999px; background: var(--bar);
       padding: 8px; z-index: 50; box-shadow: 0 10px 30px rgba(0,0,0,0.18); }
.tabs { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; height: 100%; }
.tab, .active { height: 52px; min-width: 52px; border-radius: 999px; }
```

The supporting pieces already exist in `globals.css` and are reusable as they stand:

| piece | where | what it does |
|---|---|---|
| `.desk-only` / `.mobile-only` | `globals.css:245-250` | the 1024px switch, `!important` |
| `--nav-clear: calc(150px + var(--safe-bottom))` | `globals.css:46` | bottom space a fixed bar needs |
| `.nav-clear` spacer | `globals.css:229`, hidden ≥1024 at `:233` | used by `app/(app)/page.tsx:168`, `positions/page.tsx:169`, `leaderboard/page.tsx:268` |
| `--safe-top` / `--safe-bottom` | `globals.css:44-45` | `env(safe-area-inset-*)` |
| `data-tip-anchor` | `components/tooltip.ts` | its own comment: *"the mobile tab bar"* — makes a caption clear the whole bar, not just one tab |

`tooltip.ts` already carries the mobile-tab-bar case. Sera's bar gets correct tooltips for free by
setting the same attribute.

**Geometry, measured rather than asserted.** Sera has 6 section tabs plus a back-to-Seer control.
Dropping the wordmark on the phone (Seer's own `.bar` has none — `PageHeader` already prints
"SERA · THE METHOD LAB") leaves 6 slots at Seer's full 52px tab size:

```
6 × 52 + 5 × 4 gap + 2 × 8 padding = 348px
```

Simulated live, rail hidden and a 348px fixed bar in its place:

```
/sera  @390  456 -> 390   bar gutter each side = 21px
/sera  @414  456 -> 414   bar gutter each side = 33px
```

It fits at the 390 floor with 21px to spare, at Seer's exact tab metrics, with no new size tokens.

---

## Key Data Structures

No data structures change. The work is CSS and presentational JSX. The row model the tables render
is already computed by `app/sera/methods/view.ts` (`methodRows`, `MethodRow`, `marks`, `pct1`,
`pfText`, …) and is **sufficient for a card layout as it stands** — no new derivation is needed,
which is what keeps the two table phases from colliding in that shared file.

---

## Dependencies

**Configuration / environment.** `SERA_EMAIL` gates `/sera` (`lib/sera/gate.ts`). The acceptance
test signs itself in via `web/scripts/session.mjs` and self-renews; nobody asks the owner to sign
in.

**External services.** None for `/sera` — it reads the committed `web/data/lab.json`. The layout's
journal badge reads Neon via `unseenCount` and already swallows its own failure.

**Toolchain, verified in the worktree.** `web/node_modules` was hardlinked (`cp -al`, **not**
symlinked — a symlink passes `vitest` and `tsc` and then breaks `next build` with a misleading
"filesystem root" error) and `.env.local` copied in. Verified end to end from the worktree:

```
$ node scripts/with-env.mjs npx next dev -p 3121        → Ready in 263ms
$ npm run shoot -- --base http://localhost:3121 --width 390 /sera
  with-env: 20 variable(s) from …/sera-responsive/.env.local
  auth: minted a new week, saved to …/sera-responsive/web/.auth/state.json
  PROBLEMS: /sera [light 390] scrolls 66px horizontally
```

The worktree reproduces the measured 66px, so every phase has a working acceptance test on arrival.

**Port collision — an orchestration hazard.** `npm run dev:env` hardcodes `-p 3111`. Five
concurrent phase sessions would fight over it, and the owner's own server may hold it. `shoot`
accepts `--base`, and `next dev -p N` works from the worktree (verified above), so **each phase
must take its own port**. The plan assigns one per phase.

---

## Reference List

Every site that this work touches.

| Symbol / key | File:line | Kind | Owning phase |
|---|---|---|---|
| `.rail` narrow media block | `components/sera/SeraNav.module.css:88-104` | def | 1 |
| `SeraNav()` markup | `components/sera/SeraNav.tsx:33-58` | def | 1 |
| `TABS` (6 entries) | `components/sera/SeraNav.tsx:7-14` | def | 1 |
| `.back` | `components/sera/SeraNav.module.css:46`, `:96` | def | 1 |
| `.shell` / `.main` / `.column` | `app/sera/sera.module.css:1-12` | def | 1 |
| `.shell` narrow block | `app/sera/sera.module.css:16-19` | def | 1 |
| `<PageHeader>` aside / sign-out | `components/sera/PageHeader.tsx:34-45` | def | 1 |
| `.header` narrow block | `components/sera/PageHeader.module.css:16-20` | def | 1 |
| `.bar`, `.tabs`, `.tab` (precedent) | `components/Nav.module.css:1-48` | ref (read-only) | 1 |
| `Nav()` dual render (precedent) | `components/Nav.tsx:26-50` | ref (read-only) | 1 |
| `.desk-only` / `.mobile-only` | `app/globals.css:245-250` | ref (read-only) | 1 |
| `--nav-clear`, `.nav-clear` | `app/globals.css:46`, `:229`, `:233` | ref (read-only) | 1 |
| `data-tip-anchor` | `components/tooltip.ts` (`showTip`) | ref (read-only) | 1 |
| `.sr` | `components/sera/Term.module.css:11-18` | def | **2** |
| `.term` | `components/sera/Term.module.css:1-7` | def | **2** |
| `<Term>` render | `components/sera/Term.tsx:16-21` | def | 2 |
| `Term` call sites | `app/sera/page.tsx`, `how/page.tsx`, `methods/page.tsx`, `[id]/page.tsx`, `components/sera/Section.tsx` | call | 2 (verify only) |
| `.tableWrap` / `.table` + 11 `.c*` widths | `app/sera/methods/methods.module.css:34-60` | def | 3 |
| `<table className={s.table}>` + `Row()` / `Dots()` | `app/sera/methods/page.tsx:85-186` | def | 3 |
| `.tableWrap` / `.table` | `app/sera/methods/[id]/method.module.css:33-47` | def | 4 |
| variants `<table>` | `app/sera/methods/[id]/page.tsx:377-453` | def | 4 |
| `methodRows`, `MethodRow`, `marks`, `pct1`, `pfText`, … | `app/sera/methods/view.ts` | **shared by 3 and 4** | **neither — frozen** |
| `.groups` + narrow block | `app/sera/ideas/ideas.module.css:62`, `:84-86` | def | 5 |
| `.tag` | `app/sera/ideas/ideas.module.css:65` | def | 5 |
| `.chip { white-space: nowrap }` | `app/globals.css:186-196` | ref (read-only) | 5 |
| `.stats` | `app/sera/overview.module.css:33` | def | 5 |
| `.value` / `.md` | `components/sera/Stat.module.css:4-5` | def | 5 |
| `.diagram` narrow block | `app/sera/how/how.module.css:40-44` | def | 5 |
| `shoot.mjs` horizontal-scroll check | `web/scripts/shoot.mjs` | test (read-only) | all |

---

## Impact Points (files that WILL need changes)

1. `web/components/sera/SeraNav.tsx` — dual render (`desk-only` rail + `mobile-only` bottom bar). **P1**
2. `web/components/sera/SeraNav.module.css` — replace the placeholder top-bar block with the bar. **P1**
3. `web/app/sera/sera.module.css` — narrow shell: no rail row, reserve `--nav-clear`. **P1**
4. `web/components/sera/PageHeader.tsx` + `.module.css` — a `mobile-only` back-to-Seer beside sign-out, since the bar drops it. **P1**
5. `web/components/sera/Term.module.css` — `.term { position: relative }`: the containing-block fix. **P2**
6. `web/app/sera/methods/methods.module.css` + `page.tsx` — cards below 1024, table above. **P3**
7. `web/app/sera/methods/[id]/method.module.css` + `page.tsx` — same for the variants table. **P4**
8. `web/app/sera/ideas/ideas.module.css` — `minmax(0,1fr)` + wrapping tags. **P5**
9. `web/app/sera/overview.module.css` + `web/components/sera/Stat.module.css` — one stat column, smaller value. **P5**
10. `web/app/sera/how/how.module.css` — a visible affordance on the scrolling diagram. **P5**

**Explicitly NOT changed** (measured clean or out of scope): `app/sera/journal/*`,
`app/sera/gotrade/*`, `components/sera/Section.module.css`, `components/sera/charts/*`,
`components/sera/diagrams/diagrams.module.css`, `app/sera/methods/view.ts`, `app/globals.css`,
`components/Nav.*`, `/sean`, `app/(app)/**`, the engine, the lab.

---

## Appendix A — the diagnostics, for rebuilding

Handover §8 asked that these be reproducible. Both traps it names are real and were hit:
the script **must** live in `web/` (playwright resolves from `web/node_modules`), and
`ensureState(base)` **must** be given the base URL or it throws `Invalid URL` from inside
`cookieFor`.

### A1 — which subtree widens the document (the one that cracked it)

```js
// web/scripts/_bisect-overflow.mjs   — run: node scripts/with-env.mjs node scripts/_bisect-overflow.mjs /sera/methods 390
import { chromium } from 'playwright';
import { ensureState } from './session.mjs';

const BASE = 'http://localhost:3111';
const [route, w] = [process.argv[2], Number(process.argv[3] || 390)];

const { state } = await ensureState(BASE);
const browser = await chromium.launch();
const page = await (await browser.newContext({ storageState: state })).newPage();
await page.setViewportSize({ width: w, height: 896 });
await page.goto(BASE + route, { waitUntil: 'networkidle' });

const report = await page.evaluate((vw) => {
  const de = document.documentElement;
  const sw = () => de.scrollWidth;
  const name = n => {
    const cls = (typeof n.className === 'string' ? n.className : '').trim().split(/\s+/)
      .map(c => c.replace(/-module__[A-Za-z0-9]+__/, '.')).slice(0, 3).join(' ');
    return n.tagName.toLowerCase() + (cls ? `[${cls}]` : '');
  };
  const lines = [];
  const base = sw();
  lines.push(`baseline scrollWidth=${base} viewport=${vw}`);
  let node = document.body;
  for (let depth = 0; depth < 14; depth++) {
    const kids = [...node.children];
    if (!kids.length) break;
    let culprit = null, without = null;
    for (const k of kids) {
      const prev = k.style.display;
      k.style.display = 'none';
      const now = sw();
      k.style.display = prev;
      if (now < base - 1 && (culprit === null || now < without)) { culprit = k; without = now; }
    }
    if (!culprit) {
      const cs = getComputedStyle(node);
      lines.push(`${'  '.repeat(depth)}STOP at ${name(node)} — no single child explains it`);
      lines.push(`${'  '.repeat(depth)}  rect.right=${Math.round(node.getBoundingClientRect().right)} scrollWidth=${node.scrollWidth} clientWidth=${node.clientWidth} overflowX=${cs.overflowX}`);
      break;
    }
    const cs = getComputedStyle(culprit);
    lines.push(`${'  '.repeat(depth)}${name(culprit)}  hiding it -> ${without}  (rect.right=${Math.round(culprit.getBoundingClientRect().right)} scrollW=${culprit.scrollWidth} clientW=${culprit.clientWidth} overflowX=${cs.overflowX} pos=${cs.position} minW=${cs.minWidth})`);
    node = culprit;
  }
  return lines.join('\n');
}, w);
console.log(`\n### ${route} @${w}\n${report}`);
await browser.close();
```

### A2 — offenders nothing clips, plus each absolute descendant's containing block

```js
// web/scripts/_overflow-probe.mjs — the key refinement is `if (clipper) continue;`
const probe = () => {
  const vw = document.documentElement.clientWidth;
  const doc = document.documentElement.scrollWidth;
  const path = el => { /* …tag.class chain, 9 deep… */ };
  const out = [];
  for (const el of document.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (r.right <= vw + 0.5) continue;
    let clipper = null;
    for (let n = el.parentElement; n; n = n.parentElement) {
      const ox = getComputedStyle(n).overflowX;
      if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') { clipper = n; break; }
    }
    if (clipper) continue;              // an ancestor scroller contains it: not a doc widener
    const cs = getComputedStyle(el);
    out.push({ sel: path(el), right: Math.round(r.right), minW: cs.minWidth, ws: cs.whiteSpace, pos: cs.position });
  }
  return { vw, doc, overflow: doc - vw, offenders: out };
};

// and, inside a suspect scroller, what each absolute descendant is actually positioned against:
const cbOf = a => { for (let n = a.parentElement; n; n = n.parentElement)
  if (getComputedStyle(n).position !== 'static') return n; return null; };
```

### A3 — measure a candidate fix instead of arguing about it

```js
// web/scripts/_try2.mjs
const run = async (route, w, css, label) => {
  await page.setViewportSize({ width: w, height: 896 });
  await page.goto(BASE + route, { waitUntil: 'networkidle' });
  const before = await page.evaluate(() => document.documentElement.scrollWidth);
  await page.addStyleTag({ content: css });
  const after = await page.evaluate(() => document.documentElement.scrollWidth);
  console.log(`${route} @${w}  ${label.padEnd(46)} ${before} -> ${after}`);
};
await run('/sera/methods', 390,
  `span[class*="Term-module"][class*="term"] { position: relative; }`,
  'Term { position: relative }');                                     // 959 -> 456
```

**This document describes. The plan files prescribe.**
