# Plan: Sera's narrow-width layout — the design that was deferred

**Slug:** sera-responsive
**Date:** 2026-10-12 16:58:55 +07
**Analysis:** `docs/analyzer/20261012-165855-R4C9_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/sera-responsive`
**Branch:** `feature/sera-responsive` (base: `origin/main` @ `09515d1`)
**Phases:** 5
**Status:** planned
**Coordinator:** —

---

## Why

The owner's words (handover §1):

> fully revamp xsmax UI to improve responsive UI/UX user experience

"xsmax" is the iPhone XS Max — 414 × 896 CSS px. 390 is the floor to hold; 414 is the owner's own
device; hold both.

The handover's framing, which governs this whole plan (§2):

> Sera was **deliberately** shipped desktop-first with a placeholder narrow layout. Everything in
> §3 follows from that one decision. Do not write the plan as "fix N overflow bugs" — write it as
> "design the narrow layout that was deferred", and let the overflows be the acceptance test.

And the warning that keeps a green run honest (§4):

> **Read the PNGs too** — a green exit only means nothing threw, and "doesn't overflow" is not the
> same as "is good on a phone", which is what the owner actually asked for.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | A **designed** narrow layout at 390 and 414 — the deferred design finished, so Sera is good to use on a phone, not merely non-overflowing | 1, 3, 4, 5 |
| R2 | **Zero horizontal scroll** at 390, 414 and 1280 in both themes on all seven Sera routes — `npm run shoot` green | 1, 2, 5 move the numbers; 3 and 4 hold them |

**Read the R2 row literally.** The analysis found exactly three root causes and they account for
100% of R2: the nav (phase 1), the `Term.sr` containing-block escape (phase 2), and `/sera/ideas`'
grid-track minimum (phase 5). Those three phases are what turn the shoot green. Phases 3 and 4 are
R1 work on routes phases 1 and 2 have already paid for; their R2 duty is to **hold** their route at
exactly the viewport width, not to move a number. Both plans' exit criteria now say so, and both
Satisfies lines carry the word *holds*. See the **Residual-overflow ledger** below.

## Scope

**In scope:** `/sera/**` only — `components/sera/*`, `app/sera/**`. Narrow-width layout and the one
containing-block bug that makes two of those pages scroll.

**Out of scope, and why:**

- **`/sean` and `app/(app)/**`** — a different nav (`components/Nav.tsx`), never measured for this
  work. Handover §2: *"Do not assume they share the problem or the fix. Measure before widening
  scope."* No phase edits them. `components/Nav.*` and `app/globals.css` are **read-only
  precedent**: this plan reuses `.desk-only`, `.mobile-only`, `--nav-clear` and `data-tip-anchor`
  exactly as they are and adds nothing to them.
- **Desktop (≥1024px)** — measured clean at 1280 on all seven routes (0px overflow everywhere). It
  is not part of the ask and must not drift.
- **The lab, the engine, method numbers** — all current at `d5783df`. The `N` chip bug was fixed
  there; don't reopen it.
- **`app/sera/methods/view.ts`** and **`view.test.ts`** — the row model both method pages import
  (`[id]/page.tsx:20`, `from '../view'`). It already supplies everything a card layout needs, and
  freezing it is what lets phases 3 and 4 run concurrently (**D6**). If a change would make you
  edit `view.test.ts`, you have crossed into `view.ts`: back it out and compute the value in the
  page instead.
- **`components/sera/Stat.module.css`** — rendered by `/sean` and `/sean/plan` as well as `/sera`,
  and `.value` / `.md` tie on specificity so an appended media block would silently enlarge their
  tiles. No phase edits it; `/sera`'s narrow stat size comes from `overview.module.css` as
  `.stats :global(.num)` (**D5**).
- **`app/sera/journal/*` and `app/sera/gotrade/*`** — measured: they already stack correctly at
  narrow widths and need nothing.

## Invariants

Every phase holds all of these. They come from `CLAUDE.md` and handover §5.

1. **The tree builds and tests pass at the end of each phase**: `npx tsc --noEmit && npm test` from
   `web/`, both clean.
2. **Desktop ≥1024px is unchanged.** Every new rule is inside `@media (max-width: 1023.98px)`, or
   is a `.mobile-only` element. A phase that changes how 1280 renders has wandered. Verify with a
   1280 shot every time.
3. **Read `node_modules/next/dist/docs/` before writing web code.** Next 16 and React 19 are newer
   than your training data; `web/AGENTS.md` repeats it.
4. **Every button stays icon-only** (Lucide) **with both an `aria-label` and a `data-tip` tooltip.**
   A responsive pass is exactly where someone adds a text button or drops a tooltip. Don't.
5. **Follow the Seer v2 design** (`docs/design/Seer v2.dc.html`) and the app's own existing
   vocabulary — `.sheet`, `.chip`, `.icon-btn`, `.seg`, `.card`, the colour tokens. A narrow layout
   that looks like Bootstrap is a failed phase even if it stops scrolling.
6. **Reuse, never fork, the shared phone primitives.** `.desk-only` / `.mobile-only`,
   `--nav-clear` / `.nav-clear`, `--safe-top` / `--safe-bottom`, `data-tip-anchor` all already
   exist in `app/globals.css` and `components/tooltip.ts`. No phase adds a second set.
7. **No phase touches the engine-mirrored constants** (drawdown bar, contribution schedule, fee
   minimums, resize band) — a test asserts the TS and Python sides match.
8. **Text the owner reads stays plain** — no ids, digests or code — if a phase reflows or
   truncates copy.
9. **`/sera` stays read-only** over the committed `web/data/lab.json`. No phase reads Neon or
   writes `lab/lab.sqlite`.
10. **Accessibility does not regress.** `Term`'s visually-hidden `.sr` text, `aria-label`s,
    `aria-current`, and `scope` on table headers all survive. If a phase renders a card list
    *beside* a table, exactly one of the two is exposed to assistive tech at a time.

## The acceptance test

It already exists and fails the run on horizontal scroll at any width. Do not invent another.

```bash
# phase N uses port 312N and writes to .shots/pN — concurrent phases share one worktree and would
# otherwise fight over 3111 and overwrite each other's PNGs in the default .shots/
cd web && node scripts/with-env.mjs npx next dev -p 312N &
npm run shoot -- --base http://localhost:312N --out .shots/pN --width 390 --width 414 --width 1280 \
  /sera /sera/journal /sera/methods /sera/methods/M0102 /sera/ideas /sera/how /sera/gotrade
```

Green = no page scrolls sideways at any of the three widths, in both themes. **Then read the
PNGs** — that is the half of the test that covers R1. Use the `run-the-web-app` skill; it signs in
without a human and self-renews. Never ask the owner to sign in.

The worktree is already prepared and verified: `web/node_modules` is **hardlinked** (`cp -al`, not
symlinked — a symlink passes `vitest` and `tsc` then breaks `next build` with a misleading
"filesystem root" error) and `.env.local` is in place. A shoot from the worktree has been confirmed
to reproduce the measured 66px.

## Baseline — measured on `09515d1`, the numbers every phase is scored against

`document.documentElement.scrollWidth − viewport`:

| route | @390 | @414 | @1280 | cause |
|---|---:|---:|---:|---|
| `/sera` | 66 | 42 | 0 | nav |
| `/sera/journal` | 66 | 42 | 0 | nav |
| `/sera/gotrade` | 66 | 42 | 0 | nav |
| `/sera/how` | 66 | 42 | 0 | nav |
| `/sera/ideas` | 86 | 62 | 0 | nav + grid track minimum |
| `/sera/methods` | 569 | 545 | 0 | nav + the `Term.sr` containing-block escape |
| `/sera/methods/M0102` | 458 | 434 | 0 | nav + the `Term.sr` containing-block escape |

Three root causes account for all of it. With all three fixed, every route measured exactly the
viewport width. See the analysis for the bisection and the live before→after numbers.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Port | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|------|--------|------|
| 1 | The narrow nav and the shell | R1, R2 | `web/components/sera`, `web/app/sera` | 5 | — | HARD | 3121 | `.workflows/plan/sera-responsive/phase-1.md` | — | — |
| 2 | Term's hidden span stops escaping its scroller | R2 | `web/components/sera` | 1 | — | EASY | 3122 | `.workflows/plan/sera-responsive/phase-2.md` | — | — |
| 3 | `/sera/methods`: cards on a phone, table on a desk | R1 (holds R2) | `web/app/sera/methods` | 2 | 1, 2 | HARD | 3123 | `.workflows/plan/sera-responsive/phase-3.md` | — | — |
| 4 | `/sera/methods/[id]`: the variants table, same treatment | R1 (holds R2) | `web/app/sera/methods/[id]` | 2 | 1, 2 | HARD | 3124 | `.workflows/plan/sera-responsive/phase-4.md` | — | — |
| 5 | The rest of the narrow layout | R1, R2 | `web/app/sera` | **3** | 1 | NORMAL | 3125 | `.workflows/plan/sera-responsive/phase-5.md` | — | — |

Waves, by the `Depends on` DAG: **wave 1 = {1, 2}** (no shared file), **wave 2 = {3, 4, 5}**.
Dependencies point backward only. No two phases in a wave edit the same file — rechecked file by
file at reconciliation, and the reason the boundaries below are stated as sharply as they are:

| file | phase |
|---|---|
| `components/sera/SeraNav.tsx`, `SeraNav.module.css`, `PageHeader.tsx`, `PageHeader.module.css`, `app/sera/sera.module.css` | 1 |
| `components/sera/Term.module.css` | 2 |
| `app/sera/methods/methods.module.css`, `app/sera/methods/page.tsx` | 3 |
| `app/sera/methods/[id]/method.module.css`, `app/sera/methods/[id]/page.tsx` | 4 |
| `app/sera/ideas/ideas.module.css`, `app/sera/overview.module.css`, `app/sera/how/how.module.css` | 5 |
| `app/sera/methods/view.ts`, `view.test.ts`, `components/sera/Stat.module.css`, `app/globals.css`, `components/Nav.*`, `components/tooltip.ts` | **nobody — frozen / read-only precedent** |

Phase 5 is **3 files, not 4**: `components/sera/Stat.module.css` left its Owns list at
reconciliation (decision **D5**), so no phase in the set edits it.

### Running order, ports and output directories

Five sessions share one worktree and one git index. That makes three rules, and every plan now
carries them:

- **Ports.** Phase N takes `312N` — `npm run dev:env` hardcodes 3111 and would have the five
  fighting over it. Every verification block passes `--base http://localhost:312N`.
- **Shot directories.** Every shoot passes `--out .shots/pN` (baselines to `.shots/pN-before`).
  `shoot`'s default is `.shots/`, which concurrent runs would overwrite under each other.
- **Git.** No phase may `git stash`, `reset --hard`, or `git add -A` — a bare stash pockets the
  other sessions' uncommitted work. Baselines are shot **before** editing; diffs and commits are
  taken by pathspec.

### Residual-overflow ledger — the one ledger the whole set is scored against

`document.documentElement.scrollWidth` at a 390px viewport (the absolute number, not `shoot`'s
delta; the same absolute figures hold at 414, because every cause is viewport-independent). Each
column is the state **after** that phase lands on the one before it. No phase may re-derive these.

| route | `09515d1` | after P1 | after P2 (wave 1 complete) | after P5 | after P3 / P4 |
|---|---:|---:|---:|---:|---:|
| `/sera` | 456 | **exact** | exact | exact | exact |
| `/sera/journal` | 456 | **exact** | exact | exact | exact |
| `/sera/gotrade` | 456 | **exact** | exact | exact | exact |
| `/sera/how` | 456 | **exact** | exact | exact | exact |
| `/sera/ideas` | 476 | 476 | 476 | **exact** | exact |
| `/sera/methods` | 959 | 959 | **exact** | exact | exact (held by P3) |
| `/sera/methods/M0102` | 848 | 848 | **exact** | exact | exact (held by P4) |

"exact" = the viewport width, i.e. `shoot` reports nothing. Read it this way:

- **Phase 1 alone** (its own plan's table) leaves 476 / 959 / 848 on three routes. Phase 2 is wave 1
  and stands on `09515d1`, so its own plan quotes 456 everywhere with the nav still present. Both
  are correct for the tree each is measured in; the column above is the combined wave-1 state.
- **The shoot goes fully green after phases 1, 2 and 5** — before 3 and 4 run. That is expected,
  not a sign 3 and 4 are unnecessary: they are R1, and R1 is read from the PNGs.
- A wave-2 session that sees an unexpected number is probably looking at a peer's in-flight edit in
  the shared worktree. Read the per-route lines, not the exit code, and never cross a boundary to
  make the run green early.

### Phase 1 — The narrow nav and the shell
**Satisfies:** R1, R2
**Owns:** `components/sera/SeraNav.tsx`, `components/sera/SeraNav.module.css`,
`app/sera/sera.module.css`, `components/sera/PageHeader.tsx`, `components/sera/PageHeader.module.css`
**Does not touch:** anything under `app/sera/methods`, `app/sera/ideas`, `app/sera/overview*`,
`components/sera/Term.*`, `components/Nav.*`, `app/globals.css`
**Exit criteria:** `/sera`, `/sera/journal`, `/sera/gotrade`, `/sera/how` measure exactly 390 at
390 and 414 at 414, in both themes. 1280 renders identically to `09515d1`. The six section tabs and
a way back to Seer are all reachable on a phone, each icon-only with `aria-label` + tooltip, and
the journal badge is not clipped. `/sera/methods` and `/sera/ideas` still overflow — that is
phases 2–5's work, not a phase-1 failure (**Residual-overflow ledger**: 476 / 959 / 848).

**Contract to phases 3, 4 and 5** (all three now quote the post-change state, not `09515d1`):
narrow content width is **358px @390 / 382px @414**; `.main`'s narrow **side padding stays 16px**;
the floating bar's bottom space is reserved **once**, on `.main`, as `var(--nav-clear)` — no phase
adds a second `padding-bottom` or a `.nav-clear` spacer div; `.desk-only` / `.mobile-only` is the
element-level 1024px switch and no phase writes a show/hide media query of its own.

### Phase 2 — Term's hidden span stops escaping its scroller
**Satisfies:** R2
**Owns:** `components/sera/Term.module.css`
**Does not touch:** `components/sera/Term.tsx` (the markup and the `.sr` text are correct and are
an accessibility feature — invariant 10), and no page file
**Exit criteria:** with phase 1 not yet merged, `/sera/methods` measures 456 at 390 (from 959) and
`/sera/methods/M0102` measures 456 (from 848) — i.e. only the nav remains. Every page that renders
a `<Term>` (`/sera`, `/sera/how`, `/sera/methods`, `/sera/methods/[id]`) renders visually
unchanged at 1280, and the glossary tooltip and its screen-reader text both still work.

**What phase 2 is still buying, now that phases 3 and 4 hide both tables below 1024px.** Phase 3
reports — correctly — that hiding the methods table also removes the five `<th>` `Term.sr` spans,
so `/sera/methods` reaches 456 at 390 with or without this phase; after the reconciler's label
alignment neither card renders a `<Term>` at all. That is an observation about **one width**, not a
case for dropping phase 2, and phase 3's plan now says so in those words. Phase 2 still buys:
(1) **the wave-1 exit itself** — phases 3 and 4 are wave 2 and depend on it, and without it
`/sera/methods/M0102` sits at 848 and `/sera/methods` at 959 for the whole of wave 1, which is the
ledger above; (2) **the 1024px-and-up band**, where both tables still render inside `position:
static` scrollers holding five to nine `.sr` spans whose containing block is `section.sheet`
outside them — phases 3 and 4 change nothing there by construction (invariant 2), and `shoot`
samples 1280 but no width between 1024 and 1280; (3) **`/sera/methods/[id]`**, which phase 4's own
measurements call unfixable from phase 4 (*"this page measures 848 at 390 regardless of anything
phase 4 does"*); (4) **every future scroller** — five `position: static` scrollers survive this set
(`overview.module.css .prose [data-md-table]`, `journal.module.css .body [data-md-table]`,
`[id]/method.module.css .prose [data-md-table]` and `.config`, `how.module.css .diagram`), and one
declaration in `Term.module.css` covers all of them where two `.tableWrap` patches cover two.

**Phase 2's standing rule, carried into the other phases:** any scroller a later phase keeps or
adds that gains an absolutely positioned child needs `position: relative` (or `contain: paint`) in
the same rule as its `overflow`. Discharged: phase 3 declined it on `.tableWrap` with a stated
reason (hidden below 1024, 0px at 1280); phase 4 measured zero absolutely-positioned descendants in
all four of its scrollers (`.tableWrap`, `.prose [data-md-table]`, `.config`, the charts); phase 5's
`/sera/how` affordance is `mask-image` + `scrollbar-width` + `overscroll-behavior-x` — declarations
on the scroller itself, no new element, no absolutely positioned child.

### Phase 3 — `/sera/methods`: cards on a phone, table on a desk
**Satisfies:** R1 — and **holds** R2 on `/sera/methods`
**Owns:** `app/sera/methods/methods.module.css`, `app/sera/methods/page.tsx`
**Does not touch:** `app/sera/methods/view.ts` and `view.test.ts` (**frozen** — shared with phase
4; if a derived value is needed, compute it locally in `page.tsx`), and everything under
`app/sera/methods/[id]/`
**Exit criteria:** `/sera/methods` measures exactly 390/414 in both themes — a number phases 1 and
2 already moved, so this is a hold, not a gain. Below 1024px the reader sees a readable card per
method rather than a 1200px table in a scroller; above 1024px the table is byte-for-byte what it is
today, and the 1280 PNGs are pixel-identical to a baseline taken before editing. Exactly one of the
two presentations is exposed to assistive tech. `/sera/ideas` may still report 476 until phase 5
lands — that is the ledger, not a phase-3 failure, and must not be fixed from here.

### Phase 4 — `/sera/methods/[id]`: the variants table, same treatment
**Satisfies:** R1 — and **holds** R2 on `/sera/methods/[id]`
**Owns:** `app/sera/methods/[id]/method.module.css`, `app/sera/methods/[id]/page.tsx`
**Does not touch:** `app/sera/methods/view.ts` and `view.test.ts` (**frozen** — shared with phase
3), `app/sera/methods/methods.module.css`, `app/sera/methods/page.tsx`, and the chart components
**Exit criteria:** `/sera/methods/M0102` measures exactly 390/414 in both themes, and so does at
least one method page with a `Redone realistically` block (M0007), one with the heaviest markdown
prose (M0084) and one that was never tested (M0040, the control that must not change) — all four
already exact after wave 1, so all four are holds. 1280 pixel-identical to a baseline taken before
editing. The best-variant row stays visually distinguished in the card presentation as `.bestRow`
does in the table, and is additionally **named** by a `Best` chip, because a tint alone cannot
label a card whose neighbours are off-screen. The narrow cards use phase 3's class names and card
geometry for the pieces both pages share. `/sera/ideas` may still report 476 until phase 5 lands.

### Phase 5 — The rest of the narrow layout
**Satisfies:** R1, R2
**Owns:** `app/sera/ideas/ideas.module.css`, `app/sera/overview.module.css`,
`app/sera/how/how.module.css` — **three files**
**Does not touch:** `components/sera/Stat.module.css` (**D5** — reconciled out of this phase's Owns
list; the narrow stat size is reached from `overview.module.css` as `.stats :global(.num)`),
`app/globals.css` (`.chip`'s `white-space: nowrap` is global and correct — override it locally on
`.tag`), `components/sera/diagrams/*` (the SVGs themselves are fine), `app/sera/ideas/page.tsx`,
`app/sera/how/page.tsx` and `app/sera/page.tsx` (no markup change is needed; the phase is CSS only)
**Exit criteria:** `/sera/ideas` measures exactly 390/414 in both themes — the **last** R2 number
in the set, so this phase is what turns the shoot fully green. `/sera` and `/sera/how` measure
exactly 390/414 too, but they got there in phase 1. On `/sera` the stat tiles no longer collide at
390 — invisible to the shoot, which already passes there, so it is judged from the PNG. The
`/sera/how` diagrams carry a visible affordance that they scroll sideways, correct in both themes,
and it adds no absolutely positioned child (phase 2's standing rule). 1280 unchanged on all three.
`components/sera/Stat.module.css` does not appear in the diff.

## Reconciliation Log

Seventeen conflicts found across the five plans; seventeen resolved by editing the plan files. No
conflict was deferred. Rows 1–15 are round 1; rows 16–17 are the two defects the round-2 audit
found and fixed. Round 2 re-verified every row above against the worktree.

| # | Class | Conflict | Resolution |
|---|---|---|---|
| 1 | File collision | None. Rechecked file by file: wave 1 = {`SeraNav.*`, `PageHeader.*`, `sera.module.css`} vs {`Term.module.css`}; wave 2 = {`methods/*`} vs {`methods/[id]/*`} vs {`ideas`, `overview`, `how`}. | No change. The ownership table under **Phases** is now explicit, including the frozen/read-only row. |
| 2 | File collision (process) | `shoot` writes to `web/.shots/` by default. Five concurrent sessions would overwrite each other's PNGs while a reviewer reads them. | Every verification block now passes `--out .shots/pN` (baselines `.shots/pN-before`). Recorded under *Running order*. |
| 3 | Duplicate / destructive work | Phases 2 and 3 took their 1280 baseline with a bare `git stash`. Five sessions share one worktree **and one git index** — a bare stash pockets the peers' uncommitted work. | Both rewritten to phase 4's idiom: shoot the baseline **before** editing, into `.shots/pN-before`. All five plans now forbid `stash`, `reset --hard` and `git add -A`, and take diffs and commits by pathspec. |
| 4 | File collision (quoted state) | Phase 3's `Requires` quoted phase 1's **pre-change** `.main` padding (`0 16px 40px`, `sera.module.css:19`). Phase 1 rewrites that block. | Phase 3 now quotes the post-change value and the part phase 1 pins: side padding stays 16px → 358px @390, 382px @414. Phase 5's `Requires` given the same treatment. |
| 5 | Unmet assumption | Phase 1's contract (one `--nav-clear` reservation, no spacer, no second switch) was stated by phase 1 but not echoed by 3, 4 or 5. | Verified none of them breaks it, and written into 3's and 5's `Requires`. (Phase 5's `.diagram { padding-bottom: 8px }` is room for the scroll rail inside the scroller, not nav space — noted in place.) |
| 6 | Contract drift / gap | Phase 4's exit criterion 2 demanded a fully green shoot on **all ten routes**, which no wave-2 phase can deliver: `/sera/ideas` is phase 5's. | Rewritten against the **Residual-overflow ledger**, which is new in this index and is now the single ledger all five plans point at. Phases 3 and 5 aligned to it too. |
| 7 | Contract drift | Phases 3 and 4 claimed `Satisfies: R2` while their own measurements show both routes are already exact after wave 1. | R2's work is phases 1, 2 and 5 (the analysis' three root causes). Phases 3 and 4 now read *"holds R2 … a number phases 1 and 2 moved and this phase must not spend"*, in their Satisfies lines, exit criteria, and the index's Requirements and Phases tables. No `R` lost an owner. |
| 8 | Duplicate work (alleged) | The phase-2-is-redundant trap: phase 3 observes `/sera/methods` reaches 456 with or without phase 2 once the table is hidden. | Phase 2 kept, unchanged in scope. A new section in phase 2 (*"This phase is not made redundant by phases 3 and 4"*) and a matching paragraph in this index state the four things it still buys: the wave-1 exit, the ≥1024px band where both tables still render in `position: static` scrollers, `/sera/methods/[id]` before phase 4, and every future scroller. Phase 3's note rewritten from "not blocked in practice" to "hard dependency". Confirmed phase 4 makes the **opposite** argument and does not need the same correction. |
| 9 | Ordering / masking | Neither phase's exit criteria may depend on the other's masking. | Checked: phase 3 scores only `/sera/methods`, phase 4 only the four method pages; both now state their route is a hold, and both name `/sera/ideas` as the route they must not fix. |
| 10 | Duplicate work (naming) | Phases 3 and 4 invented two vocabularies for the same card: `.cards/.card/.cardHead/.stats/.stat/.statLabel/.statValue` vs `.vCards/.vCard/.vHead/.vGrid/.vCell/.vLabel/.vValue`. | Phase 4 edited to phase 3's names for the seven ideas both pages have; `v`-prefixed names kept only for variant-only pieces (`.vName`, `.vBest`, `.vWhen`, `.vLead*`, `.vNote`, `.vMore*`, `.vMarks`, `.vMark`). Verified `method.module.css` has no existing `.card`/`.cards`/`.stat*`, so the `v` prefix was a free choice, not forced. `CardStat` stays phase 3's local helper name, deliberately not `Stat`. |
| 11 | Duplicate work (geometry) | Same card, two geometries: phase 3 `border-radius: 28px`, `padding: 16px 18px 14px`; phase 4 `22px`, `14px 16px 16px`, and a different label style (`0.06em`/`--ink-2` vs `0.12em`/`--ink-3`). | Phase 4 edited to phase 3's values. 28px on `var(--stone)` is Sera's narrow card in `ideas`, `journal`, `overview` and `how`; the 22px came from `.tech`, a disclosure panel rather than a list of records. The label is `ideas.module.css .label` verbatim on both pages. Rung: surrounding convention. |
| 12 | Contract drift (within phase 4) | Phase 4's Step 6 asserted *"one breakpoint per stylesheet"* while its Step 5 put the card rules at the file's top level, outside any query. | Steps 5 and 6 merged into one Step 5: a single `@media (max-width: 1023.98px)` block appended at the end of `method.module.css`, carrying the cards, the prose-cell wrap and the two rules rescued from the deleted `34rem` query. Matches phase 3's convention and makes the desktop-safety audit one grep. |
| 13 | Gap / impact point re-owned | Impact point 9 names `components/sera/Stat.module.css`; phase 5 proved editing it would change `/sean` and would silently beat `.md`'s 34px on source order. | Accepted (**D5**). The impact point is served from `overview.module.css` via `.stats :global(.num)`. `Stat.module.css` removed from phase 5's Owns list — **phase 5 is 3 files, not 4** — and moved to the frozen/read-only row. No impact point and no Reference List entry is left unowned. |
| 14 | Gap (process) | Phase 2's header carried no `Port:` line and phase 3's said `Dev port:`. | Normalised to `**Port:** 312N` on all five. Every verification block passes `--base http://localhost:312N`; verified 3121–3125, one each. |
| 15 | Stale citations | The analysis' Reference List cites `methods.module.css:34` (actually `:11`), `overview.module.css:33` (`.cards`; `.stats` is `:25`) and `SeraNav.module.css:88-104` (the file is 98 lines; the block is `:75-98`). | Verified all three against the worktree and corrected in the plans that depend on them (2, 5 and 1 respectively). The analysis itself is a record and is left alone. |
| 16 | Stale citation (round 2) | A fourth stale Reference List cite survived round 1: phase 5's Step 3 prose said `how.module.css:40-44` pairs `.diagram { overflow-x: auto }` with `.diagram > svg { min-width: 960px }`. The file is **43 lines**; the pair is `:41-42` and the narrow block is `:36-43`. | Corrected to `:41-42` in phase 5. Its Files table and Step 3 header already said `:36-43` and were right. The analysis keeps the old number, as a dated record. No contract moved. |
| 17 | Contract drift (round 2) | Phase 5's header still read `**Package:** web/app/sera, web/components/sera` — stale from before **D5** took `components/sera/Stat.module.css` out of its Owns list. The index's Phases table says `web/app/sera`. | Phase 5's header corrected to `web/app/sera`. Its Owns list, Files table and the "3 files, not 4" line were already right; only the header had not been brought along. No file changed owner. |

**Contract changed — round 1:** yes — conflicts 10, 11 and 12 moved creations (class names) and a
block boundary inside phase 4, and conflicts 7 and 13 moved requirement attribution and a file out
of a phase's Owns list. Nothing moved **between** phases except `Stat.module.css`, which moved to
nobody. That is what bought the second pass.

**Contract changed — round 2: no.** Both round-2 repairs are text corrections inside phase 5: a
line-number citation and a stale `Package:` header. No symbol was created, deleted or renamed; no
file changed owner; no `R` moved; no exit criterion, ledger cell or `Satisfies` line changed value.
The set is stable and no third round is needed.

## Decisions

Every fork this set met, the branch taken, and the rung of the ladder that decided it
(stated invariant → phase exit criteria → the plans' code blocks → this index's Why and
Requirements → the user's raw input → surrounding convention). An executor reads this instead of
asking.

| # | The fork | The choice | Rung |
|---|---|---|---|
| **D1** | What shape is the narrow nav — a wrapped rail, a top bar, or something else? | **Seer's own `mobile-only` fixed bottom pill bar**, the one `components/Nav.tsx:46` already ships, reusing `.desk-only` / `.mobile-only`, `--nav-clear`, `--safe-top` / `--safe-bottom` and `data-tip-anchor` exactly as they are. Six tabs at Seer's 52px metrics: `6 × 52 + 5 × 4 + 2 × 8 = 348px`, measured to fit 390 with 21px of gutter and 414 with 33px. | **Stated invariant 5** — follow Seer v2 and the app's own vocabulary; the app already ships this nav, so inventing a second idiom is the failure mode the invariant names. |
| **D2** | Does the "Sera." wordmark survive below 1024px? | **No.** Seer's own `.bar` carries none, and `PageHeader`'s eyebrow names the section on all seven routes (verified at every call site). Dropping it is what pays for the sixth tab at full size. | Surrounding convention (`Nav.module.css`), with the eyebrow verified in the code. |
| **D3** | Where does back-to-Seer go, once the bar has no room for it? | **In `PageHeader`'s `.aside`, `mobile-only` — but route-guarded.** *Amended by phase 1, which found what the decision could not have known:* `PageHeader` is **not** Sera's. It is also imported by `app/sean/page.tsx`, `sean/plan/page.tsx` and `sean/trades/page.tsx`, and `/sean` is out of scope, so an unconditional control would appear there. `PageHeader` is a server component carrying an inline `'use server'` action and cannot read the URL (`use-pathname.md`: *"Reading the current URL from a Server Component is not supported."*), so the guard lives in a second export, `SeraBackLink`, from the already-`'use client'` `SeraNav.tsx` — a file phase 1 owns. Outside `/sera/**` it returns `null`. | The amendment's rung is **the surrounding code**: the shared import was measured, and Next 16's own docs settle where the guard can live. The underlying placement is unchanged. |
| **D4** | Do the two method tables become cards below 1024px, or stay tables in a scroller? Handover §6 put this to the owner as an open question. | **Cards below 1024px on both; at ≥1024px both stay byte-for-byte the tables they are today.** | **The user's raw input** — *"fully revamp xsmax UI to improve responsive UI/UX user experience"* — plus surrounding convention: every other Sera page (`ideas`, `journal`, `overview`, `how`) already uses cards at narrow width. The measured cost is stated in phase 3 (the methods list's element count roughly doubles) and accepted. |
| **D5** | Where does `/sera`'s narrow stat size come from — a media query in `components/sera/Stat.module.css`, or `overview.module.css`? | **`overview.module.css`, as `.stats :global(.num)`. `Stat.module.css` is NOT edited by any phase.** Two load-bearing reasons: `Stat` is also rendered by `app/sean/OverviewBody.tsx` and `sean/plan/page.tsx`, which are out of scope; and `.value` `(0,1,0)` and `.md` `(0,1,0)` tie on specificity, so a media block appended to that file would come later in source order and silently beat `.md`'s 34px on those pages. `.stats :global(.num)` is `(0,2,0)` and wins regardless of order; `ideas.module.css:4` already uses the idiom. | **Stated invariant** (the Scope section's "no phase edits `/sean`"), with the specificity trap measured. Standing assumption it creates: `Stat.tsx` must keep the global `num` class on its value span — recorded in phase 5's Handoffs and in the stylesheet comment. |
| **D6** | May phases 3 and 4 touch `app/sera/methods/view.ts` / `view.test.ts`, which both method pages import? | **No — frozen for the whole set.** Both planners confirmed they need nothing from it; every derived value either already exports or is computed locally in the page. | **Stated invariant** (Scope), and it is the mechanical reason phases 3 and 4 can run concurrently in one shared worktree and one git index. If a change would make you edit `view.test.ts`, you have crossed into `view.ts`: back it out, do not edit the test. |
| **D7** | Two card vocabularies for one idea: phase 3's `.cards/.card/.cardHead/.stats/.stat/.statLabel/.statValue` or phase 4's `.vCards/.vCard/.vHead/.vGrid/.vCell/.vLabel/.vValue`; and 28px vs 22px radius with two different label styles. | **Phase 3's names and geometry win** for the seven pieces both pages have, and for the label (`ideas.module.css .label` verbatim). Phase 4 keeps `v`-prefixed names only for pieces a variant card has and a method card does not. Verified the `v` prefix was not forced: `method.module.css` has no `.card`, `.cards` or `.stat*` today. | **Surrounding convention** — 28px on `var(--stone)` is Sera's narrow card in four stylesheets, while 22px came from `.tech`, a disclosure panel. CSS modules are scoped, so this was never a technical collision; it was a design-language one. |
| **D8** | On a narrow card, is a measure labelled with the table's abbreviation inside a `<Term>` (`Max DD`, `PF`, `DSR`) or with the glossary's plain words? | **Plain words, no `<Term>`, on both pages:** `Max drawdown`, `Profit factor`, `Luck check`, `Growth a year`, `What your money earned`. `<T>` stays exactly as it is in both desk tables' `<th>`s. | **Stated invariant 8** (text the owner reads stays plain — the table abbreviates only because of a measured column budget a card does not have), reinforced by the fact that the other direction is foreclosed: phase 3's card is one card-wide link, and a `<Term>`'s `tabIndex={0}` span under that overlay is both unreachable and a focus trap. The glossary itself is unchanged and still reachable from `/sera/how`. |
| **D9** | Does `.tableWrap` get `position: relative` as well as the `Term` fix? | **No. The containing-block fix lives in `Term.module.css` and nowhere else.** Phase 3 declined it explicitly (hidden below 1024, 0px at 1280, and it would be a desktop-affecting change for no measured benefit); phase 4 measured zero absolutely-positioned descendants in all four of its scrollers; phase 5's affordance adds none. | **Plan invariant 6** (reuse, never fork) plus the analysis' measurement — `.term { position: relative }` and `.tableWrap { position: relative }` both give 456, and the `Term` fix covers five further `position: static` scrollers the scroller-side patch would not. |
| **D10** | Does the R2 ledger allow a wave-2 phase to chase a green exit code? | **No.** R2's numbers are moved by phases 1, 2 and 5 only; 3 and 4 hold theirs. The **Residual-overflow ledger** above is the single source, and a phase that made someone else's route green has crossed a boundary. | **Phase exit criteria** — phase 1's "a PARTIAL green is the pass" was the only plan that stated its residue correctly, so the other four were brought onto its ledger rather than the reverse. |
| **D11** | How does each session take its 1280 baseline and write its PNGs, given one shared worktree? | **Shoot the baseline before editing, into `.shots/pN-before`; every run takes `--out .shots/pN`; no `git stash`, `reset --hard` or `git add -A`; diff and commit by pathspec.** | **Surrounding convention / the stated constraint** — the index already says concurrent phases share one worktree; phase 4 was the only plan that had drawn the consequence, so the other four were brought to it. |

## Open Questions

**None.** Every fork above was decided and its rung recorded. Nothing in this set is irreversible:
each phase is one commit of additive CSS inside a `max-width: 1023.98px` query or on a
`mobile-only` element, `git revert` restores the previous narrow layout without moving desktop, no
migration runs, and `lab/lab.sqlite` and `web/data/lab.json` are never written. Every requirement id
has at least one owning phase.

## Notes — found by the planners, deliberately NOT work for this set

Neither belongs to any phase. Each is worth its own card.

- **`components/sean/SeanNav.tsx` carries the same deferred narrow layout.** Its own comment says
  *"Same build as SeraNav"*, so `/sean` still shows a placeholder top bar on a phone. The Scope
  section puts `/sean` out of this set — handover §2: *"Do not assume they share the problem or the
  fix. Measure before widening scope."* Phase 1's `SeraBackLink` route guard exists precisely so
  `/sean` does not drift while this set lands.
- **`methods.module.css:7` `.counts .num` is a dead rule.** It compiles `.num` to a hashed local
  class while the markup applies the **global** `num` (`page.tsx:74-78`), so it has never matched.
  The fix is `.counts :global(.num)` — and applying it would change desktop pixels for the first
  time (the count numbers would become `--ink` and 500-weight), which invariant 2 forbids in this
  set. Left exactly as it is.

## Rollback

Each phase is one commit on `feature/sera-responsive` and every change is additive CSS inside a
`max-width: 1023.98px` media query or a `.mobile-only` element, so `git revert <sha>` restores the
previous narrow layout without touching desktop. Commit **by pathspec** — the five sessions share
one worktree and one git index, so `git add -A` would sweep up the peers' work. Phase 2 is a single declaration and reverts
alone. The whole set backs out with `git branch -D feature/sera-responsive` and
`git worktree remove`; nothing outside `web/` is touched, no migration runs, and `lab.sqlite` and
`web/data/lab.json` are never written.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/SERA_RESPONSIVE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/SERA_RESPONSIVE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/SERA_RESPONSIVE_PLAN.md
