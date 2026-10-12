# Phase 5: The rest of the narrow layout

**Plan set:** `SERA_RESPONSIVE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-165855-R4C9_code_analyzer.md`
**Satisfies:** R1 (a *designed* narrow layout at 390/414) and R2 (zero horizontal scroll) — for
`/sera/ideas`, `/sera` and `/sera/how`
**Depends on:** Phase 1 (the narrow nav and the shell)
**Difficulty:** NORMAL
**Package:** `web/app/sera`
**Port:** 3125

---

## Goal

After this phase `/sera/ideas` measures exactly the viewport width at 390 and 414 (the grid track
no longer refuses to shrink below a non-wrapping chip), `/sera`'s five headline stat tiles stop
colliding on a phone (one tile per row at a size the longest value fits), and `/sera/how`'s two
960px diagrams carry a visible, theme-correct sign that they scroll sideways. Desktop at ≥1024px is
byte-for-byte what it is today, and `components/sera/Stat.module.css` — shared with `/sean` — is
not touched at all.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `overview.module.css`: one new `@media (max-width: 1023.98px)` block containing `.stats` and
  `.stats :global(.num)` — the file has **zero** narrow rules today, so this is a new breakpoint in
  a file no other phase owns.
- `how.module.css`: new declarations inside the **existing** `@media (max-width: 1023.98px)` block
  (`.card`, `.col`, `.rule`, `.ruleIcon`, and extra properties on `.diagram`).
- `ideas.module.css`: new declarations inside the **existing** `@media (max-width: 1023.98px)`
  block (`.tag`, `.needs`, `.card`, `.wish`, `.link`) and a changed value on `.cards, .groups`.

**Signature changes:** none. No TSX, no props, no exports, no markup. CSS only.

**Requires (from earlier phases):**
- Phase 1 removes the 456px `SeraNav` rail-as-a-row below 1024px. Every "measures exactly 390/414"
  exit criterion below is stated **after phase 1 has landed**. Before phase 1, the same work leaves
  `/sera/ideas` at 456 (not 476) and `/sera`, `/sera/how` at 456 — which is phase 1's residue, not
  a phase-5 failure.
- Phase 1 also **rewrites** `app/sera/sera.module.css`'s narrow block, so quote the post-change
  state: narrow `.main` becomes `padding: var(--safe-top) 16px var(--nav-clear)` and
  `.shell { flex-direction: column }` is deleted. Side padding stays **16px**, which is why the
  sheet is still 314px at 390 and 338px at 414 in every measurement below. The floating bar's
  bottom space is reserved **once**, there: this phase adds no second `padding-bottom`, no
  `.nav-clear` spacer and no show/hide media query of its own — `.desk-only` / `.mobile-only` is
  the element-level switch for the whole set. (`.diagram`'s `padding-bottom: 8px` in Step 3 is room
  for the scroll rail inside the scroller, not bottom space for the nav.) Nothing in this phase is
  position-dependent.

**Leaves alone (owned by others):**
- `app/globals.css` — `.chip { white-space: nowrap }` (`globals.css:195`) is global and correct.
  It is overridden **locally** on `.tag` / `.needs`, inside a narrow media query, in
  `ideas.module.css`. `globals.css` is not edited.
- **`components/sera/Stat.module.css` — reconciled out of this phase's Owns list and left
  unchanged.** The draft index gave it to phase 5; nothing in the set edits it now. See
  "Decision: no media query in `Stat.module.css`" below. Phases 3 and 4 may render `<Stat>` freely;
  this phase adds no breakpoint to it and no new class.
- `components/sera/Term.*` (phase 2 — the `.sr` containing-block fix).
- `components/sera/SeraNav.*`, `components/sera/PageHeader.*`, `app/sera/sera.module.css` (phase 1).
- `app/sera/methods/**` including `[id]/**` (phases 3 and 4).
- `components/sera/diagrams/*` — the SVG drawings and `diagrams.module.css` are correct; this phase
  styles only the `.diagram` **wrapper** that lives in `how.module.css`.
- `app/sera/journal/*`, `app/sera/gotrade/*` — measured: they already stack and need nothing.
- `app/sera/ideas/page.tsx`, `app/sera/how/page.tsx`, `app/sera/page.tsx` — **no markup change is
  needed.** Every fix below is reachable from the four stylesheets. The affordance in item C is
  CSS-only for exactly this reason.
- `/sean`, `/sean/plan`, `app/(app)/**` — out of scope for the whole plan set, and the
  `Stat.module.css` decision is what keeps them out of this phase's blast radius.

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/ideas/ideas.module.css` | modify | `:50-52` narrow block: `1fr` → `minmax(0, 1fr)`, wrapping `.tag`/`.needs` chips, phone padding on `.card`/`.wish`/`.link` |
| `web/app/sera/overview.module.css` | modify | new narrow block inserted after `:93`, before the `min-width: 1024px` block at `:95`: `.stats` to one column, `.stats :global(.num)` to 38px |
| `web/app/sera/how/how.module.css` | modify | `:36-43` narrow block: scroll affordance on `.diagram` (mask fade + scroll rail + `overscroll-behavior-x`), phone padding on `.card`/`.col`/`.rule` |
| `web/components/sera/Stat.module.css` | **not a file of this phase** | reconciled: removed from this phase's Owns list, so the phase is **3 files**, not 4. It is read-only precedent for the whole set — see the decision below |

## What the acceptance test can and cannot see

Read this before declaring victory on a green `npm run shoot`.

| item | route | visible to `shoot`? | how it is judged |
|---|---|---|---|
| **A** grid track minimum | `/sera/ideas` | **Yes.** Baseline 476 at 390 (86 over); after this phase + phase 1 it must be exactly 390 / 414. | the shoot's own horizontal-scroll check |
| **B** colliding stat tiles | `/sera` | **No.** `minmax(0, 1fr)` already stops the grid widening the document, so `/sera` passes the shoot today *while the two 52px numbers overlap.* | **the PNG only.** Open `/sera` at 390 light and dark and look at the five tiles. |
| **C** diagram scroll affordance | `/sera/how` | **No.** `.diagram { overflow-x: auto }` already contains the 960px svg; the bisection returns 456 = the nav alone. There is **no overflow bug here — do not "fix" working CSS.** | **the PNG only**, in both themes |
| **D** chips / rows / padding at 390 | `/sera/ideas`, `/sera/how` | partly — a wrapping `.needs` chip that overflowed its own 30px pill is a visual defect, not a document widener | the PNG |

A, B and C together are R1; only A moves an R2 number. **A green run on `/sera` and `/sera/how`
proves nothing about this phase.**

## Decision: no media query in `Stat.module.css`

The brief flagged `Stat.module.css` as the one place this phase would add a breakpoint to a shared
component, and asked for the list of pages that render `<Stat>` first. Here it is, measured by
grep over `web/`:

| call site | size used | in scope? |
|---|---|---|
| `app/sera/page.tsx:78, 83, 92, 101, 115` (five tiles inside `.stats`) | default `lg` (52px) | **yes — this phase** |
| `app/sean/OverviewBody.tsx:42` | `size="md"` (34px) | **no** — `/sean`, out of scope for the whole plan set |
| `app/sean/plan/page.tsx:114, 115, 118` | `size="md"` (34px) | **no** — `/sean/plan`, out of scope |

Adding `@media (max-width: 1023.98px) { .value { font-size: … } }` to `Stat.module.css` would be
wrong twice over:

1. It changes `/sean` and `/sean/plan` on a phone, and the plan's Scope section says no phase edits
   them.
2. It is a live trap. `.md` (`Stat.module.css:5`) and `.value` (`:4`) are both one class, so they
   tie on specificity and **source order decides**. A media block appended at the end of the file
   comes later in source order, so a narrow `.value { font-size: 38px }` would silently beat
   `.md { font-size: 34px }` and make `/sean`'s small tiles *bigger* on a phone.

The alternative used instead costs nothing and stays inside a file this phase owns alone:
`Stat.tsx:22` puts the **global** `num` class on the value span
(`className={`num ${s.value} …`}`), and `globals.css:136` defines `.num { font-variant-numeric:
tabular-nums }`. So `overview.module.css` can reach the number with `.stats :global(.num)` —
specificity `(0,2,0)`, which outranks `.value` `(0,1,0)` whatever the stylesheet order is, and is
scoped to the five tiles on `/sera` and nothing else. `ideas.module.css:4` already uses exactly
this idiom (`.tally :global(.chip)`), so it is the house style, not an invention.

One standing assumption this creates, written into the code as a comment: **`Stat.tsx` must keep
the `num` class on the value span.** If a later change removes it, `/sera`'s phone tiles silently
return to 52px (desktop is unaffected). Noted in Handoffs.

`.md`, `.twin` and `.mini` were checked as the brief asked: `.md` never appears inside `.stats`, so
`.stats :global(.num)` cannot reach it; `.twin` is already `flex-direction: column` and `.mini` is
already `min-width: 0` — the two `LineChart`s stack correctly at 390 and need nothing.

---

## Implementation Steps

### Step 1: `/sera/ideas` — let the grid track shrink, and let the chips wrap

**File:** `web/app/sera/ideas/ideas.module.css:50-52` (the whole existing narrow block)
**Item:** A and D. **Visible to the acceptance test.**

**Change:** Replace the three-line narrow block at the end of the file with the block below. Two
halves are both required, and the analysis measured each: `minmax(0, 1fr)` alone takes 476 → 458,
and `.tag { white-space: normal }` on top of it takes 458 → **456** (456 being the nav, which phase
1 removes).

The second half needs more than `white-space: normal`, though. `globals.css:186-196` gives `.chip`
a **fixed `height: 34px`** and `ideas.module.css:42` narrows `.tag` to `height: 30px`. A chip that
is allowed to wrap onto a second line inside a fixed-height stadium spills its own text out of the
pill, so the height has to become a floor rather than a fixed value. `.needs`
(`ideas.module.css:26`) already carries `white-space: normal` at every width while keeping
`height: 30px`, so it has the same latent defect today and gets the same treatment here.

**Code — complete final `web/app/sera/ideas/ideas.module.css`:**

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
  /*
   * One column, but written `minmax(0, 1fr)` rather than `1fr` on purpose. `1fr` is shorthand for
   * `minmax(auto, 1fr)`, and an `auto` track minimum is a *content* minimum: the track refuses to
   * shrink below its contents' min-content width. Inside `.group` that content is a `.chip`, and
   * `globals.css:195` gives every chip `white-space: nowrap`, so the chip has no min-content
   * narrower than its whole label — which held the track, and the page, at 476px on a 390px
   * viewport. `minmax(0, 1fr)` lets the track shrink to the column; the chips then have to be
   * allowed to wrap too, which is the rule below. Measured: 476 -> 458 here, 458 -> 456 there.
   * `.cards` carries the identical construction and is fixed the same way.
   */
  .cards, .groups { grid-template-columns: minmax(0, 1fr); }

  /*
   * The other half of the same fix. A chip that may wrap can no longer be a fixed-height pill, or
   * its second line spills out of the stadium — so 30px becomes a floor and the padding grows
   * vertically. `.needs` already wrapped at every width while keeping `height: 30px`, so it had
   * the same defect and gets the same treatment. `.chip`'s global `white-space: nowrap` stays
   * global and correct; it is only overridden here, on these two, below 1024px.
   */
  .tag, .needs {
    white-space: normal;
    height: auto;
    min-height: 30px;
    padding: 5px 14px;
    line-height: 1.3;
  }

  /* Phone spacing: the sheet is 314px wide at 390 and 338px at 414, so the cards and rows hand
     more of it to the text and less to their own chrome. */
  .card { padding: 20px 20px 18px; }
  .wish { gap: 12px; padding: 16px 18px; }
  .link { gap: 10px; }
}
```

**Impact:** `/sera/ideas` stops widening the document. Desktop is untouched — every changed
declaration is inside `@media (max-width: 1023.98px)`, and the base `.tag`, `.needs`, `.card`,
`.wish`, `.link` and `.groups` rules are byte-for-byte what they were. `page.tsx` is not touched:
the fix is entirely a CSS one, which is why the "touch `ideas/page.tsx` only if unavoidable"
escape hatch is not used.

---

### Step 2: `/sera` — one stat tile per row, at a size the longest value fits

**File:** `web/app/sera/overview.module.css` — insert a new block between `:93` (the last
`.status[data-status=…]` rule) and `:95` (`@media (min-width: 1024px)`).
**Item:** B. **Invisible to the acceptance test — judged from the PNG.**

**Change:** `overview.module.css` has **zero** `max-width: 1023.98px` rules today; `.stats`
(`overview.module.css:25` — note the analysis quotes `:33`, which is one commit stale; `:33` is
`.cards`) is `repeat(2, minmax(0, 1fr))` at every width below 1024, and `Stat.module.css:4` gives
the value `font-size: 52px; white-space: nowrap`. At 390 the sheet's inner width is
`390 − 32 (main padding) − 44 (Section narrow padding) = 314px`, so each column is ~145px and the
two 52px numbers overlap. `minmax(0, 1fr)` is what keeps the overlap from reaching the document, so
the shoot stays green while the tiles collide.

The designed answer is one tile per row. At 314px a single tile has the whole sheet, so the longest
value — `'none yet'`, eight characters, the fallback when no try has beaten SPY inside the drawdown
bar — fits comfortably at 38px, and each tile's plain-language `sub` sentence gets a full-width
line instead of a four-line ribbon in a 145px column. Two cramped columns is the defect; a
stacked list of five clear numbers is the fix. Row gap drops 22 → 20 so the stack stays compact.

**Code — complete final `web/app/sera/overview.module.css`:**

```css
/* Overview: one column below 1024px (readable, not designed); a 12-column sheet grid on desktop. */
.grid { display: flex; flex-direction: column; gap: 12px; }

.state, .landing, .hurdles, .closer, .luck, .families, .latest { min-width: 0; }

.stateBody { display: flex; flex-direction: column; gap: 24px; }

.story { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.storyMeta { font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-3); }

.prose { min-width: 0; font-size: 17px; line-height: 1.5; color: var(--ink); overflow-wrap: anywhere; }
.prose p { margin: 0 0 10px; }
.prose p:last-child { margin-bottom: 0; }
.prose h1, .prose h2, .prose h3, .prose h4 { margin: 14px 0 6px; font-size: 18px; font-weight: 500; letter-spacing: -0.01em; }
.prose ul, .prose ol { margin: 0 0 10px; padding-left: 20px; }
.prose li { margin: 2px 0; }
.prose strong { font-weight: 500; }
.prose code { font-size: 15px; padding: 1px 6px; border-radius: 8px; background: var(--stone); }
.prose a { text-decoration: underline; text-decoration-color: var(--outline); text-underline-offset: 3px; }
.prose [data-md-table] { overflow-x: auto; margin: 6px 0 10px; }
.prose table { width: 100%; border-collapse: collapse; font-size: 15px; }
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

/* Hurdles + Families: one grid of bar rows (label | track with bar and value) that grows to fill the sheet. */
.hurdles > .fillChart, .families > .fillChart { flex: 1; }
.fillChart {
  align-self: stretch;
  width: 100%;
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  column-gap: 12px;
  align-items: center;
}
.fillLabel { font-size: 13px; color: var(--ink); text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.fillTrack, .fillTicks { position: relative; margin-right: var(--fill-value); font-size: 13px; }
.fillTrack { align-self: stretch; border-left: 1.25px solid var(--outline); }
.fillGrid { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--hair); }
.fillBar {
  position: absolute;
  left: 0;
  top: 18%;
  bottom: 18%;
  min-width: 2px;
  border-radius: 0 6px 6px 0;
  transition: opacity 0.12s;
}
.fillBar:hover { opacity: 0.78; }
.fillValue {
  position: absolute;
  top: 50%;
  transform: translate(6px, -50%);
  white-space: nowrap;
  font-size: 13px;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.fillTicks { align-self: start; height: 26px; }
.fillTick { position: absolute; top: 8px; transform: translateX(-50%); font-size: 12px; color: var(--ink-2); font-variant-numeric: tabular-nums; }

/* Status chips: one quiet fill per stage of the pipeline. */
.status { height: 30px; padding: 0 12px; font-size: 14px; background: var(--chip-solid); }
.status[data-status='idea'], .status[data-status='registered'] { background: var(--lav); }
.status[data-status='rejected'], .status[data-status='test-failed'] { background: var(--sheet); color: var(--ink-2); }
.status[data-status='blocked-data'] { background: var(--sky); }
.status[data-status='dev-eligible'], .status[data-status='promoted'] { background: var(--butter); }
.status[data-status='test-passed'], .status[data-status='paper'] { background: var(--coral); color: var(--on-coral); }

/*
 * Phone. The sheet's inner width is 314px at a 390px viewport (390 − 32 main padding − 44 Section
 * padding) and 338px at 414. Two tiles in that space give each number ~145px, and Stat's value is
 * 52px with `white-space: nowrap`, so the two numbers overlap — they do *not* widen the document,
 * because `minmax(0, 1fr)` already caps the tracks. That is why `npm run shoot` passes on this
 * page while the tiles are broken, and why this block is judged from the screenshot rather than
 * from the run. One tile per row at 38px is the designed answer: the longest value the page can
 * print is 'none yet' (eight characters, the no-result fallback), which fits 314px with room, and
 * each tile's plain sentence gets a full-width line instead of a four-line ribbon.
 */
@media (max-width: 1023.98px) {
  .stats { grid-template-columns: minmax(0, 1fr); gap: 20px; }

  /*
   * The size is set from here, not from Stat.module.css, because that component is also rendered
   * by /sean and /sean/plan, which this plan set does not touch — and because `.value` and `.md`
   * tie on specificity there, so a media block appended to that file would silently outrank the
   * 34px `md` size those pages use. Stat.tsx puts the global `num` class on the value span, so
   * `.stats .num` (0,2,0) reaches it from here and beats `.value` (0,1,0) whatever the stylesheet
   * order is, scoped to these five tiles and nothing else. Keep `num` on that span.
   */
  .stats :global(.num) { font-size: 38px; }
}

@media (min-width: 1024px) {
  .grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 12px; align-items: stretch; }

  .state { grid-column: span 12; }
  .landing { grid-column: span 8; }
  .hurdles { grid-column: span 4; }
  .closer { grid-column: span 6; }
  .luck { grid-column: span 6; }
  .families { grid-column: span 5; }
  .latest { grid-column: span 7; }

  .stateBody { gap: 32px; }
  .stats { grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 24px; }
  .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (min-width: 1024px) and (max-width: 1239.98px) {
  .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (min-width: 1360px) {
  .prose { font-size: 18px; }
}
```

**Impact:** `/sera`'s stat tiles stop colliding at 390 and 414. The three existing `min-width`
blocks (1024, 1024–1239.98, 1360) are unchanged and still come last in the file, so 1280 renders
exactly as before — `.stats` there is still `repeat(5, minmax(0, 1fr))` with a 52px value. No
document-width number moves on this route, so the shoot's `/sera` result is identical before and
after; that is expected, not a failure.

---

### Step 3: `/sera/how` — say that the diagrams scroll, and give the cards the sheet

**File:** `web/app/sera/how/how.module.css:36-43` (the whole existing narrow block)
**Item:** C and D. **Invisible to the acceptance test — judged from the PNG, in both themes.**

**Change.** First, what is *not* changed: `how.module.css:41-42` already pairs
`.diagram { overflow-x: auto }` with `.diagram > svg { min-width: 960px }`, and it **works** — the
bisection on `/sera/how` returns 456 at 390, which is the nav alone. An `<svg>`'s children are not
absolutely positioned CSS boxes, so nothing escapes the clip the way `Term`'s `.sr` span does on
the method pages. The handover's claim that an inline SVG contributes to this page's overflow is
wrong, and the 960px floor is a deliberate readability choice (a 1240-unit drawing squeezed into
330px would be unreadable). Neither is touched.

What is left is R1: a 960px drawing inside a ~314px scroller with no visible sign that it scrolls.
Three additions, all on the wrapper:

1. **A right-edge mask fade.** `mask-image` is chosen over a gradient overlay *because of the
   theme requirement*: an overlay has to be painted in the colour it sits on, which would mean one
   value for light, one for dark, and another if the Section's tint ever changes — three chances to
   get it wrong. A mask removes paint instead of adding it, so it is automatically correct on
   `--sheet` in either theme and on any `bg-*` tint. It is applied to the scroll container, so the
   fade sits at the right edge of the **scrollport** and stays put as the drawing moves under it —
   the reader sees the drawing dissolve at the edge, which is the message. Right edge only: a
   symmetric fade would dim the left edge of the drawing at rest, where nothing is hidden, and
   would read as a rendering fault in the screenshot.
2. **An always-drawn scroll rail**, `scrollbar-width: thin` with `scrollbar-color: var(--outline)
   transparent`. `--outline` is a Seer v2 token defined in both themes (`#cfcabd` light, `#45423c`
   dark), so the rail is quiet and correct in both. Chromium and Firefox draw it permanently — it
   is what the reviewer will see in the PNG; iOS Safari keeps its overlay bar and ignores the
   property, which is where the fade carries the job alone.
3. **`overscroll-behavior-x: contain`**, so swiping the drawing to its end does not hand the
   gesture to the page or to the browser's back-swipe. One line, and it is the difference between
   a scroller that feels designed and one that fights the phone.

No markup is added, so `how/page.tsx` stays untouched and no new copy is introduced — invariant 8
is satisfied by not writing any new text at all.

**Phase 2's standing rule, discharged.** Phase 2 asked that any scroller which gains an absolutely
positioned child be given `position: relative` (or `contain: paint`) in the same rule as its
`overflow`, and named this affordance as the likeliest place that would bite. It does not: all
three additions are declarations **on the scroller itself**, there is no new element, and nothing
inside `.diagram` is absolutely positioned (an `<svg>`'s children are not CSS boxes). So `.diagram`
stays `position: static` and needs no guard. Had the fade been an absolutely positioned overlay,
it would have needed one — which is the second reason the mask won.

The card padding trims are item D: `.rule` spends 102px of a 314px sheet on its own chrome
(44px icon + 14px gap + 2 × 22px padding), which is a third of the line length.

**Code — complete final `web/app/sera/how/how.module.css`:**

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

  /* Phone spacing: the sheet is 314px wide at 390. A rule row was spending 102px of that on its
     own chrome (44px icon + 14px gap + 44px padding), a third of the line length. */
  .card, .col { padding: 20px; }
  .rule { gap: 12px; padding: 18px; }
  .ruleIcon { width: 40px; height: 40px; }

  /*
   * The diagrams are drawn for desktop; below 1024px they scroll sideways instead of shrinking
   * their text — a 1240-unit drawing squeezed into 314px would be unreadable. This scroller is
   * NOT an overflow bug: it already contains the svg (the page measures the nav width and nothing
   * more), because an <svg>'s children are not absolutely positioned CSS boxes and so none of
   * them escapes the clip. What was missing is any sign that it scrolls, which is what the three
   * additions below supply.
   *
   * The fade is a mask rather than a gradient overlay on purpose: an overlay must be painted in
   * whatever colour it sits on, so it would need one value for the light theme, one for dark, and
   * another for any sheet tint. A mask removes paint instead of adding it, so it is correct in
   * both themes and on any background with a single declaration. It is applied to the scroll
   * container, so it sits at the right edge of the scrollport and stays there while the drawing
   * moves under it. Right edge only — a fade on the left would dim the start of the drawing where
   * nothing is hidden, and read as a defect.
   *
   * `scrollbar-width: thin` draws a permanent rail in Chromium and Firefox (this is what shows in
   * the screenshots); iOS Safari ignores it and keeps its overlay bar, where the fade does the
   * work alone. `overscroll-behavior-x: contain` keeps a swipe that reaches the end of the
   * drawing from becoming a page scroll or a browser back gesture.
   */
  .diagram {
    overflow-x: auto;
    overscroll-behavior-x: contain;
    padding-bottom: 8px;
    -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 48px), transparent 100%);
    mask-image: linear-gradient(to right, #000 calc(100% - 48px), transparent 100%);
    scrollbar-width: thin;
    scrollbar-color: var(--outline) transparent;
  }
  .diagram > svg { min-width: 960px; }
}
```

**Impact:** `/sera/how` keeps measuring exactly the viewport width (no width number moves — the
scroller already contained the svg). The two diagrams gain a visible right-edge fade and a scroll
rail in both themes, and the hurdle cards, honesty rules and data columns get ~8–10px more line
length each. Desktop is untouched: every change is inside the existing
`@media (max-width: 1023.98px)` block, and the base `.diagram`, `.card`, `.col`, `.rule` and
`.ruleIcon` rules are byte-for-byte what they were.

---

### Step 4: `components/sera/Stat.module.css` — verify unchanged

**File:** `web/components/sera/Stat.module.css`
**Change:** none. Confirm with `git diff --name-only -- web/components/sera/Stat.module.css` that
the file does not appear in this phase's diff. If a later reviewer asks why the draft index listed
it under this phase and it was not edited, the answer is the "Decision" section above: it is rendered by `/sean` and `/sean/plan`, which the plan set keeps out
of scope, and `.value` / `.md` tie on specificity so an appended media block would silently enlarge
those pages' small tiles.
**Impact:** phases 3 and 4 may render `<Stat>` at either size with no coordination with this phase.

---

## Verification

Phase 5's port is **3125**. Concurrent phases share one worktree, so do not use `npm run dev:env`
(it hardcodes 3111).

**Build and tests**

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
npx tsc --noEmit && npm test
```

Both must be clean. No test in `web/` imports or asserts on any of these four stylesheets —
verified by grep: `grep -rln "module.css" --include='*.test.ts' --include='*.test.tsx' web/`
returns nothing, and the three nearby suites (`app/sera/overview.test.ts`,
`app/sera/ideas/view.test.ts`, `app/sera/how/view.test.ts`) test the pure view modules
(`overview.ts`, `ideas/view.ts`, `how/view.ts`), not CSS. **No test needs updating.** The
engine-mirrored constants (invariant 7) live in `lib/`, nowhere near this phase.

**The acceptance test — all seven routes, three widths, both themes**

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
node scripts/with-env.mjs npx next dev -p 3125 &
npm run shoot -- --base http://localhost:3125 --out .shots/p5 --width 390 --width 414 --width 1280 \
  /sera /sera/journal /sera/methods /sera/methods/M0102 /sera/ideas /sera/how /sera/gotrade
```

Take any 1280 baseline you want to compare against **before you edit**, into `.shots/p5-before`.
**Do not `git stash` for it:** five phase sessions share this one worktree and one git index, so a
bare stash pockets the *other* sessions' uncommitted work. Never stash, `reset --hard`, or
`git add -A` here; commit by pathspec. The per-phase `--out` directory is for the same reason —
`shoot`'s default `.shots/` would have concurrent runs overwriting each other's PNGs.

Use the `run-the-web-app` skill; it signs in without a human and self-renews. Never ask the owner
to sign in.

**Manual check — the half of the test that covers R1.** A green run does not evidence items B, C
or D. Open the PNGs at 390, **light and dark**:

1. `/sera` — the five stat tiles under "State of the search" are one per row, each number on its
   own line with its label and plain sentence under it, **nothing overlapping**. Compare against
   the baseline PNG, where two 52px numbers share a 314px sheet. The longest value case is
   "none yet" in the last tile when nothing has beaten SPY inside the drawdown bar.
2. `/sera/how` — both diagram sheets show the drawing fading out at the right edge, with a thin
   rail under it. The fade must look the same relative to the sheet in dark mode (it is a mask, so
   it cannot pick up a wrong colour — confirm that by eye anyway). The left edge of each drawing is
   **not** faded.
3. `/sera/how` — hurdle cards, honesty rules and the two data columns are one per row with the
   tighter padding; the rule icon circles are 40px.
4. `/sera/ideas` — concept tags wrap onto two lines inside their pills without the text escaping
   the stadium; the "needs" chip on a data-wishlist row does the same; the backlog cards and the
   concept groups are one per row.
5. `1280`, all three routes — compare against the `09515d1` baseline PNG. `/sera`'s stats are still
   five across with 52px numbers; `/sera/how`'s diagrams are full-width with no fade and no rail;
   `/sera/ideas` is still two columns.

**Exit criteria**

- `/sera/ideas` measures **exactly 390 at 390 and 414 at 414**, in both themes (from 476 / 62 over
  at the baseline). This is the only R2 number this phase moves.
- `/sera` and `/sera/how` measure exactly 390 / 414 — unchanged by this phase's own work; they get
  there because phase 1 removed the nav. If phase 1 has not landed in the tree you are testing,
  both read 456 and that is phase 1's residue.
- `/sera`'s stat tiles do not collide at 390 or 414, **read from the PNG**.
- `/sera/how`'s diagrams carry a visible scroll affordance at 390 and 414, in **both** themes,
  read from the PNG.
- 1280 is unchanged on `/sera`, `/sera/ideas` and `/sera/how`.
- `npx tsc --noEmit` and `npm test` clean.
- `git diff --name-only -- web/app/sera` lists exactly three files, all `.module.css`
  (`ideas/ideas.module.css`, `overview.module.css`, `how/how.module.css`). Check by pathspec: in a
  shared worktree a bare `git diff` also shows the peers' work.
- `web/components/sera/Stat.module.css` does **not** appear in this phase's diff.

**What else the shoot may report, and whose it is.** This phase lands on a tree where wave 1
(phases 1 and 2) has landed, so `/sera`, `/sera/journal`, `/sera/gotrade`, `/sera/how`,
`/sera/methods` and `/sera/methods/M0102` already measure exactly the viewport width —
`/sera/ideas` is the **last** overflowing route in the set, and this phase is what closes it. See
the plan index's *Residual-overflow ledger*, the single ledger the whole set is scored against: it
is this phase, not 3 or 4, that turns the shoot green. If `/sera/methods` or `/sera/methods/M0102`
is anything but exact when you run it, that is phase 3 or 4 mid-flight in the shared worktree, not
yours to chase — read the per-route lines, not the exit code. `/sera/journal` and `/sera/gotrade`
were measured clean and need nothing.

## Handoffs

Found while planning, deliberately left:

- **`.needs` wraps out of its pill at desktop too** (`ideas.module.css:26`: `white-space: normal`
  with `height: 30px`). This phase fixes it only below 1024px, because invariant 2 forbids changing
  how ≥1024px renders. Whether a long `blockedOn` string ever wraps at desktop depends on the data
  and was not measured. **Not an R1/R2 item — a follow-up card, not a phase.**
- **A truthful fade.** The right-edge mask on `/sera/how`'s diagrams stays on even when the reader
  has scrolled to the end. CSS scroll-driven animations (`animation-timeline: scroll(self inline)`)
  would let it recede, but they are not available on the owner's own device (an iPhone XS Max tops
  out at iOS 18; scroll-driven animations shipped in Safari 26), so the progressive enhancement
  would be invisible to him and is not worth the complexity here. Follow-up, not this phase.
- **`Stat.tsx` must keep the global `num` class on its value span.** `overview.module.css` reaches
  the narrow font size through `.stats :global(.num)`. If a future change drops `num`, `/sera`'s
  phone tiles silently return to 52px and collide again; desktop is unaffected, and the shoot would
  not catch it. Worth a line in the Stat docstring — **left to whoever next edits `Stat.tsx`**,
  since this phase changes no TSX.
- **Phases 3 and 4 may render `<Stat>` freely.** No breakpoint was added to `Stat.module.css`; if
  either phase needs a narrow stat size, it should scope it from its own stylesheet the same way
  (`:global(.num)` under a local parent) rather than add one to the shared component.
- **`/sera`'s `.fillChart`** (`overview.module.css:53-60`) uses a `max-content` first track with
  `white-space: nowrap` labels — a construction that *could* widen the page if a family name ever
  grows long. It measures clean today (the `/sera` bisection returns the nav and nothing else), so
  it is not touched. Watch it if a long family label is ever added.

## Rollback

`git revert <sha>` for this phase's single commit. Every change is additive CSS inside a
`@media (max-width: 1023.98px)` block in three page-level stylesheets; no markup, no component, no
shared file and no base rule is touched, so reverting restores the previous narrow layout and
cannot affect desktop, `/sean`, phases 1–4, or anything outside `web/app/sera`. No migration runs,
no `lab.sqlite` or `web/data/lab.json` write is involved.
