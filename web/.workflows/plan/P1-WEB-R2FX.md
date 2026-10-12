> Adopted from `/home/miftah/seer/.workflows/orchestration/sera-responsive/PLAN.md` phase 2. Source: `.workflows/plan/sera-responsive/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Term's hidden span stops escaping its scroller

**Plan set:** `SERA_RESPONSIVE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-165855-R4C9_code_analyzer.md`
**Satisfies:** R2 — one of its three root causes: the `Term.sr` containing-block escape, which is
the whole of `/sera/methods`' and `/sera/methods/[id]`'s overflow above the nav, and the cover for
every `position: static` scroller that will ever hold a glossary term
**Depends on:** none (wave 1, alongside phase 1)
**Difficulty:** EASY
**Package:** `web/components/sera`
**Port:** 3122

---

## Goal

`Term`'s visually-hidden `.sr` span becomes a child of a positioned `.term`, so it is clipped by
whatever scroll container it sits in instead of escaping to `section.sheet` and widening the
document. After this phase `/sera/methods` and `/sera/methods/M0102` stop reporting a ~500–570px
horizontal scroll and report only the nav's 66px (at 390) — the single remaining R2 cause, which
is phase 1's. Nothing renders differently at any width, in either theme.

## The bug, in one paragraph (already proven — do not re-derive)

`Term.tsx:18` renders `<span class={s.sr}>` with `position: absolute` inside every glossary term.
A scroll container only clips an absolutely positioned descendant when it is in that descendant's
**containing-block chain**. Both method tables' `.tableWrap` scrollers are `position: static`
(`methods.module.css:11`, `[id]/method.module.css:33` — verified in this worktree; the analysis's
Reference List cite of `methods.module.css:34` is stale), so the nearest positioned ancestor of each
`.sr` is `section.sheet` (`app/globals.css:218`, `position: relative`) — **outside** the scroller.
The five `.sr` spans in the methods table header therefore contribute to the *section's* scrollable
overflow; the last one's right edge measured **959px**, which is the document's `scrollWidth`
exactly. The analysis' decisive control: `.tableWrap { overflow: hidden }` changed the number by
**zero**. This is not an overflow-value problem, so the obvious "add `overflow-x: auto`" fix the
handover warned about provably could not work.

Measured candidates (analysis §"Candidate fixes, measured live"):

| applied | `/sera/methods` @390 `scrollWidth` |
|---|---:|
| baseline | 959 |
| `.tableWrap { position: relative }` | 456 |
| `.tableWrap { contain: paint }` | 456 |
| `.tableWrap { overflow: hidden }` | **959 — no change** |
| `.term { position: relative }` | **456** |

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:** none (no new class, no new selector — one declaration added to an existing rule)
**Signature changes:** none. `Term`'s props, markup, `data-tip`, `tabIndex` and `.sr` text are
untouched; `.term` and `.sr` keep their names and remain CSS-module-scoped to
`components/sera/Term.module.css`.
**Modifies:** `.term` in `web/components/sera/Term.module.css:1-7` gains `position: relative`
(plus the explanatory comment above the rule).
**Requires (from earlier phases):** nothing. This phase is wave 1 and stands alone on `09515d1`.
**Leaves alone (owned by others):**
- `components/sera/SeraNav.*`, `app/sera/sera.module.css`, `components/sera/PageHeader.*` (Phase 1)
- `app/sera/methods/methods.module.css`, `app/sera/methods/page.tsx` (Phase 3)
- `app/sera/methods/[id]/method.module.css`, `app/sera/methods/[id]/page.tsx` (Phase 4)
- `app/sera/ideas/*`, `app/sera/overview.module.css`, `components/sera/Stat.module.css`,
  `app/sera/how/how.module.css` (Phase 5)
- `components/sera/Term.tsx` — the `.sr` span and its text are an accessibility feature
  (plan invariant 10). **Read-only this phase.**
- `app/globals.css`, `components/Nav.*`, `components/tooltip.ts` — read-only precedent for the
  whole plan set.

## Files

| File | Action | What changes |
|---|---|---|
| `web/components/sera/Term.module.css` | modify | `.term` gains `position: relative`, with the prose comment that explains why |

That is the whole phase. One file, one declaration, one comment.

## Implementation Steps

### Step 1: Make `.term` the containing block for its own `.sr`

**File:** `web/components/sera/Term.module.css:1-7` (the `.term` rule, at the top of the file)

**Change:** Add `position: relative` to `.term`, preceded by a prose comment in the house style
(`CLAUDE.md`: *"Modules carry prose docstrings that explain why the code is shaped the way it is"*).
The rule is incomprehensible without its reason — a future reader sees a `position: relative` with
no offsets on an inline span and deletes it as dead weight, which silently reopens a 569px
horizontal scroll on `/sera/methods`.

**Code:** the complete new contents of `web/components/sera/Term.module.css`:

```css
/* A glossary word: a dotted underline, plus a visually-hidden copy of its definition for screen
   readers. `.sr` is `position: absolute`, and an absolutely positioned box is only clipped by an
   ancestor scroller that is in its *containing-block* chain -- an `overflow` value alone does
   nothing. Sera's scrollers (`methods.module.css .tableWrap`, `[id]/method.module.css .tableWrap`,
   the `[data-md-table]` wrappers in the prose) are all `position: static`, so without the rule
   below each `.sr` resolves its containing block all the way out to `.sheet`
   (`globals.css`, `position: relative`), escapes the scroller, and widens the whole document:
   `/sera/methods` measured a 959px scrollWidth at a 390px viewport, the last `.sr`'s right edge
   to the pixel. `position: relative` here -- no offsets, so nothing moves -- makes `.term` itself
   the containing block, which puts `.sr` back inside the scroller where it is clipped normally.
   Remove it and both method pages scroll sideways on a phone again. Fixing it here rather than in
   each scroller is deliberate: it covers every scroller that will ever hold a <Term>. */
.term {
  position: relative;
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

**Impact:** `/sera/methods` `scrollWidth` 959 -> 456 at 390; `/sera/methods/M0102` 848 -> 456.
No visual change anywhere (argued and verified below). Nothing else in the tree reads `.term` —
the class is CSS-module-scoped and its only consumer is `Term.tsx:16`.

### Step 2 (verification only, no edit): confirm nothing else is touched

`Term` is rendered from exactly five call sites, all through a local `T()` helper over
`GLOSSARY`:

- `app/sera/page.tsx:42`
- `app/sera/how/page.tsx:29`
- `app/sera/methods/page.tsx:24`
- `app/sera/methods/[id]/page.tsx:43`
- `components/sera/Section.tsx:10` (a docstring mention — `Section`'s `note` prop *may hold*
  `<Term>`s; no render of its own)

None of them is edited by this phase. Phases 3 and 4 own two of those files; this phase must not
open them even to look for a follow-on fix.

## Why `position: relative` is a visual no-op — the argument, then the check

**The argument.** `.term` is an inline span whose entire painted appearance is a dotted underline
(`text-decoration`, its colour, thickness and offset) plus a `cursor` and a `:focus-visible`
outline. `position: relative` with **no** `top`/`right`/`bottom`/`left` offsets leaves the box at
its static position, so every glyph and the underline paint at the same coordinates. It does not
create a stacking context (that needs a `z-index` other than `auto`, or `isolation`, or a
transform/filter/opacity — `.term` has none of those). It does make `.term` a *positioned* box, so
it paints in the positioned-descendants step of the painting algorithm rather than with in-flow
inline content. Since `.term` has no background, border or box-shadow, and its only child beyond
the text is the 1px clipped `.sr`, there is nothing whose paint order could become visible. The
one thing that genuinely changes is the containing block for `.sr` — which is the whole point.

**The check.** Do not take the argument on faith; shoot it.

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
node scripts/with-env.mjs npx next dev -p 3122 &
# every route that renders a <Term>, desktop width, both themes
# BEFORE touching the file:
npm run shoot -- --base http://localhost:3122 --out .shots/p2-before --width 1280 \
  /sera /sera/how /sera/methods /sera/methods/M0102
# then make the one-line change and:
npm run shoot -- --base http://localhost:3122 --out .shots/p2-after --width 1280 \
  /sera /sera/how /sera/methods /sera/methods/M0102
```

Then **read the four PNGs per theme** (eight files) and confirm each glossary term still shows its
dotted underline at the same place, the same colour, on the same line, with no reflow of the
sentence around it, and diff the two directories — the PNGs should be identical apart from any
non-determinism in the charts.

**Take the baseline before you edit; do not `git stash` for it.** Five phase sessions share this
one worktree and one git index, so a bare stash pockets the *other* sessions' uncommitted work.
Never stash, `reset --hard`, or `git add -A` here, and give every shoot its own `--out .shots/pN`
so concurrent runs do not overwrite each other's PNGs.

Use the `run-the-web-app` skill for the server and sign-in; it self-renews the session and never
asks the owner to sign in. In this worktree the shoot needs `SEER_ENV_FILE` pointed at the
worktree's `.env.local` (see the plan index: `web/node_modules` is hardlinked and `.env.local` is
already in place, and a shoot from here has been confirmed to reproduce the measured numbers).

## Both of `Term`'s behaviours must still work

### 1. The `data-tip` tooltip

`components/tooltip.ts` is a document-level delegated handler: `mouseover`/`touchstart` find the
nearest `[data-tip]` with `closest()`, then `showTip` creates a **`position: fixed`** div appended
to `document.body` and positions it from `el.getBoundingClientRect()` plus `innerWidth`. A `fixed`
element's containing block is the viewport, not any ancestor — and `.term` creates no stacking
context and no transform, which are the only ways a relatively positioned ancestor could capture a
`fixed` descendant. The tip is not a descendant of `.term` at all. `getBoundingClientRect()` on a
`relative` box with no offsets returns the same rect as on a `static` one. So the tooltip is
untouched by construction.

**How to check anyway:** with the dev server on 3122, open `/sera/methods` and hover a header term
(e.g. `CAGR`, `max drawdown`). Confirm the caption appears above the word, in the dark pill/box
style, wrapping to the rounded multi-line box for the long glossary sentences (`tooltip.ts`
switches at 48 characters), and that it clears itself after 2.5s. On a touch viewport
(`--width 390`), long-press a term for ~450ms and confirm the caption shows and that the press
does not also fire a click. Then scroll the method table sideways and confirm the caption hides —
`tooltip.ts` listens for `scroll` in capture mode precisely because the tip is `fixed`; this is the
one tooltip path that interacts with the scroller the bug lives in, so it is worth a look.

### 2. The screen-reader text

`Term.tsx:18` still renders `<span class={s.sr}>{` (${term}: ${definition})`}</span>` — this phase
does not open that file. `.sr` keeps `width/height: 1px`, `overflow: hidden`, `clip` and
`clip-path: inset(50%)`, which is what hides it visually while leaving it in the accessibility
tree; `position: relative` on the *parent* changes none of those. (Plan invariant 10: `Term`'s
visually-hidden text survives.)

**How to check:** in the browser devtools on `/sera/methods`, inspect any header `<th>` and
confirm the `.sr` span is present in the DOM, has no `aria-hidden`, has non-empty text of the form
` (CAGR: …)`, and that its computed `position` is still `absolute` while its computed box is
1×1 clipped. Devtools' Accessibility pane should show the `.term` span's accessible name as the
printed word followed by the parenthesised definition. A `getComputedStyle` one-liner in the
console is enough:

```js
const t = document.querySelector('[data-tip]'); const sr = t.lastElementChild;
[getComputedStyle(t).position, getComputedStyle(sr).position, sr.getBoundingClientRect().width, sr.textContent]
// expect: ["relative", "absolute", 1, " (…: …)"]
```

A cheaper regression guard that works without a browser: `npx tsc --noEmit && npm test` — `Term.tsx`
is unchanged, so every test that renders a page containing a `<Term>` keeps asserting on the same
HTML. See "Tests that assert on `Term`" below for what that actually covers.

## This phase is not made redundant by phases 3 and 4 — read this before dropping it

Phase 3 reports, correctly, that hiding the methods table below 1024px also removes the five `<th>`
`Term.sr` spans, so `/sera/methods` would reach 456 at 390 with or without this phase. Phase 4's
card does the same for the variants table, and after the reconciler's label alignment neither card
renders a `<Term>` at all. **That is an observation about one viewport width, not a case for
dropping this phase.** Four reasons, in order of weight:

1. **Wave order.** Phases 3 and 4 are wave 2 and both declare `Depends on: 1, 2`. This phase is
   wave 1. Between wave 1 landing and wave 2 landing, `/sera/methods/M0102` sits at **848** and
   `/sera/methods` at **959** unless this one-line fix is in — and the plan index's
   *Residual-overflow ledger* is written on the assumption it is. Drop this phase and the whole
   wave-1 exit, and therefore the whole set's scoring, comes apart.
2. **The band where the table still renders.** `.desk-only` / `.mobile-only` switch at 1024px, so
   from 1024px upward the 1200px / 1240px tables render exactly as they do today — scrollers that
   are still `position: static`, still holding five to nine `.sr` spans whose containing block is
   `section.sheet` outside them. Phases 3 and 4 change nothing in that band by construction
   (invariant 2 forbids it). The escape is live there whenever the last `.sr`'s right edge passes
   the viewport, and `shoot` samples 1280 but no width between 1024 and 1280. This phase is the
   only thing covering it.
3. **`/sera/methods/[id]` is not phase 4's to fix.** Phase 4's own measurements table is explicit:
   *"Without it this page measures 848 at 390 regardless of anything phase 4 does."* Phase 4 moves
   no R2 number; every number on that route was paid by phases 1 and 2.
4. **Every future scroller.** Five `position: static` scrollers remain in Sera after this set
   (`overview.module.css .prose [data-md-table]`, `journal.module.css .body [data-md-table]`,
   `[id]/method.module.css .prose [data-md-table]` and `.config`, `how.module.css .diagram`). Any
   of them may hold a `<Term>` tomorrow. One declaration in `Term.module.css` covers all of them;
   two `.tableWrap` patches cover two.

## The alternative: also hardening the two `.tableWrap` rules — ruled on

**Ruling: do not. Fix it only in `Term`, and only in this phase.**

Reasons, in order of weight:

1. **Measured sufficiency.** `.term { position: relative }` alone takes `/sera/methods` 959 -> 456
   and `/sera/methods/M0102` 848 -> 456 — identical to what `.tableWrap { position: relative }`
   achieves. The scroller-side rule adds nothing on these two routes.
2. **Coverage.** Patching the two `.tableWrap` rules fixes two scrollers. Patching `Term` fixes
   every scroller that will ever hold a glossary term. Sera has five further `position: static`
   scrollers today that a `<Term>` could land in: `app/sera/overview.module.css:20`
   (`.prose [data-md-table]`), `app/sera/journal/journal.module.css:30`
   (`.body [data-md-table]`), `app/sera/methods/[id]/method.module.css:80`
   (`.prose [data-md-table]`) and `:125` (`.config`), and `app/sera/how/how.module.css:41`
   (`.diagram`, inside the narrow media block). None of them would be covered by a `.tableWrap`
   patch.
3. **Plan invariant 6 — reuse, never fork.** Two rules that both exist to fix the same defect is a
   fork of the fix; the next person changes one and not the other.
4. **Ownership.** `methods.module.css` is phase 3's and `[id]/method.module.css` is phase 4's.
   This phase may not edit either — the wave-1/wave-2 file split is what lets 3 and 4 run
   concurrently, and a phase-2 edit in their files would collide on merge.

**Note for phases 3, 4 and 5** (a note, not a request to do anything this phase can verify): the
containing-block rule is general. If you *keep* a scroller, or add a new one, and it will ever
contain an absolutely positioned descendant that is not a `<Term>`, give that scroller
`position: relative` (or `contain: paint` — both measured equivalent) in the same rule that gives
it `overflow`. Phases 3 and 4 are replacing these tables with cards below 1024px, so the two
`.tableWrap` scrollers stop mattering *at narrow widths* — which is another reason not to
pre-emptively patch rules that are about to be hidden, and no reason at all to skip the `Term`
fix (see the section above). Phase 5's `.diagram` scroller
(`how.module.css:41`) currently contains only inline SVGs with no absolutely positioned children,
so it needs nothing today; if the "visible affordance that it scrolls sideways" were built as an
absolutely positioned fade or arrow, that affordance would have to be positioned against a
`position: relative` wrapper, not against the scroller's static box. **Checked by the reconciler:
phase 5's affordance is `mask-image` + `scrollbar-width` + `overscroll-behavior-x` — declarations
on the scroller itself, with no new element and no absolutely positioned child — so this rule is
satisfied and phase 5 needs no `position: relative`.** Phase 4 made the same call explicitly for
its own four scrollers and measured zero absolutely-positioned descendants in each.

Surveyed and clear: the other three visually-hidden `.sr` rules in Sera
(`app/sera/journal/journal.module.css:61` used at `journal/page.tsx:156`,
`app/sera/ideas/ideas.module.css:44` used at `ideas/page.tsx:109`,
`app/sera/gotrade/gotrade.module.css:84` used in `GotradeEditor.tsx:24,29`) are each rendered
*outside* any scroller, which is why the baseline shows no unexplained overflow on those routes.
They are not a second instance of this bug and need no change. Do not "harmonise" them — that is
scope creep across three other phases' files.

## Tests that assert on `Term`

Grepped `web/**/*.test.*` and `web/**/*.spec.*` (49 files; none under `components/sera/Term*`):

- **No test file references `Term`, `Term.module.css`, `.term`, or `Term`'s `.sr`.** There is no
  `Term.test.tsx`.
- The only `data-tip` assertions are in `components/sera/charts/charts.test.tsx:29,51,84,117,142,164`
  and `app/sean/OverviewBody.test.tsx:28-32`. Both are about chart points and `/sean`'s icon-only
  controls — neither renders a `<Term>`, and neither reads CSS.
- `app/sera/overview.test.ts`, `app/sera/how/view.test.ts`, `app/sera/methods/view.test.ts`,
  `lib/sera/glossary.test.ts` cover the data the `T()` helpers read (`GLOSSARY[k].term` /
  `.plain`), not the component or its stylesheet.

So `npm test` cannot catch a regression here and cannot be broken by this change; it is a
build-and-no-collateral-damage gate only. The real gate is the shoot numbers below.

## Verification

Run from the worktree. Port **3122** (phase N uses 312N; concurrent phases share one worktree and
would otherwise fight over 3111).

**Build + tests:**

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
npx tsc --noEmit && npm test
```

Both must be clean. No source file changes type, so a failure here means something unrelated.

**The acceptance test — all seven routes, three widths, both themes:**

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
node scripts/with-env.mjs npx next dev -p 3122 &
npm run shoot -- --base http://localhost:3122 --out .shots/p2 --width 390 --width 414 --width 1280 \
  /sera /sera/journal /sera/methods /sera/methods/M0102 /sera/ideas /sera/how /sera/gotrade
```

**The shoot will still exit non-zero, and that is the expected result for this phase.** Read this
before judging the run. `shoot.mjs:105-106` reports
`document.documentElement.scrollWidth − clientWidth` and flags anything over 1px, so it prints the
*delta*, while the analysis quotes absolute `scrollWidth`. Phase 1 (the nav) is **not** merged
when this phase runs, so the nav's 66px/42px remains on every route by design.

Exit numbers, with phase 1 NOT merged:

| route | @390 before | @390 after | shoot prints after | @414 after |
|---|---:|---:|---|---:|
| `/sera/methods` | 959 (`scrolls 569px`) | **456** | `scrolls 66px horizontally` | 456 (`scrolls 42px`) |
| `/sera/methods/M0102` | 848 (`scrolls 458px`) | **456** | `scrolls 66px horizontally` | 456 (`scrolls 42px`) |
| `/sera` | 456 | 456 (unchanged) | `scrolls 66px` | 456 |
| `/sera/journal` | 456 | 456 (unchanged) | `scrolls 66px` | 456 |
| `/sera/gotrade` | 456 | 456 (unchanged) | `scrolls 66px` | 456 |
| `/sera/how` | 456 | 456 (unchanged) | `scrolls 66px` | 456 |
| `/sera/ideas` | 476 | 476 (unchanged) | `scrolls 86px` | 476 |
| all seven @1280 | 0 | **0** | nothing | — |

Read it this way:

- **Pass** = `/sera/methods` and `/sera/methods/M0102` have dropped to exactly the same residue as
  the four plain routes (66 at 390, 42 at 414) — i.e. only the nav is left on the two heaviest
  pages. The two four-figure numbers are gone.
- **Fail** = either method route still prints a three-figure delta, or any route at **1280**
  prints anything at all (that would mean the change disturbed desktop, violating plan invariant 2).
- A non-zero shoot exit is **not** this phase failing. The remaining 66/42 is phase 1's nav and the
  extra 20 on `/sera/ideas` is phase 5's grid track. Do not chase either from here.

**Manual check (the half the shoot cannot see):**

1. The eight 1280px PNGs from the no-op check above — glossary terms render identically.
2. Hover and long-press a glossary term; tooltip appears, wraps, auto-hides, hides on scroll.
3. Devtools console one-liner above returns `["relative", "absolute", 1, " (…: …)"]`.
4. `git diff` is one file and shows exactly one added declaration plus the comment block.

**Exit criteria:** `/sera/methods` measures `scrollWidth` **456** at 390 (down from 959) and
`/sera/methods/M0102` measures **456** (down from 848), both in light and dark, with the same
numbers at 414 relative to that viewport; all seven routes still measure exactly 1280 at 1280;
`npx tsc --noEmit && npm test` clean; the glossary tooltip and the `.sr` screen-reader text both
still work; the diff is `web/components/sera/Term.module.css` and nothing else.

## Handoffs

- **Phases 3 and 4 — the scroller-side guard, deliberately not done here.**
  `app/sera/methods/methods.module.css:11` and `app/sera/methods/[id]/method.module.css:33` are
  still `position: static` scrollers after this phase. They no longer leak anything, because the
  only absolutely positioned descendants they held were `Term`'s `.sr` spans. If either phase adds
  an absolutely positioned element inside a scroller it keeps (a sticky first column's shadow, a
  scroll-affordance fade, a card badge), give that scroller `position: relative` in the same rule
  as its `overflow`. Serves R2, their requirement, in their files.
- **Phase 5 — `.diagram` (`how.module.css:41`) and `.prose [data-md-table]`
  (`overview.module.css:20`).** Same rule, same reason; both are `position: static` scrollers and
  both are clean today. The "visible affordance that the diagram scrolls sideways" in phase 5's
  exit criteria is the likely place a new absolutely positioned child appears. R1/R2, phase 5.
- **Nobody — the three other `.sr` rules** (`journal.module.css:61`, `ideas.module.css:44`,
  `gotrade.module.css:84`) duplicate the visually-hidden recipe with slightly different
  declarations (`margin: -1px; border: 0`, which `Term`'s lacks). Consolidating them into one
  shared utility would be a real cleanup, but it touches three phases' files for no measured
  benefit and no requirement in this set. Left undone on purpose; raise it as its own card if the
  owner wants it.
- **`components/sera/Term.tsx` — untouched and should stay that way.** The `.sr` span is an
  accessibility feature (plan invariant 10), not the bug. The bug was always the stylesheet.

## Rollback

```bash
cd /home/miftah/.worktrees/seer/sera-responsive
git revert <phase-2 sha>          # or, before committing:
git checkout -- web/components/sera/Term.module.css
```

One file, one declaration, no dependants. Reverting restores the 959/848 scrollWidths on the two
method pages and changes nothing else — no other phase's work is built on this rule, and nothing
in the tree reads `.term` outside `Term.tsx`. If phases 3 and 4 have already landed card layouts
that hide the tables below 1024px, the revert may be invisible at 390 and only reappear at
intermediate widths where a scroller still renders; in that case prefer fixing forward.
