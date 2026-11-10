# Plan: Leaderboard desktop revamp

**Slug:** leaderboard-desktop-revamp
**Date:** 2026-11-10 09:02 WIB
**Analysis:** `.workflows/analyze/20261110-090235-LB7D_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/leaderboard-desktop-revamp`
**Branch:** `feature/leaderboard-desktop-revamp` (base: `HEAD` @ `22d1051`, equal to origin/main)
**Phases:** 3
**Status:** phase 2/3 complete
**Coordinator:** —

---

## Why

> check https://seertrade.site/leaderboard . we need to revamp the desktop UI fully.
> we added claude adversarial methods in here. but it fucked up the UI.
> my idea:
> 1. we need to make EVERY METHOD unique: unique in color, unique in icon.
> 2. the go live checklist has a list of icons at the top. make sure it only takes one row, right now, one icon flowed over to make a second row
> 3. my idea (you may propose a btter one) : change the list of thin boxes to just somekind of stacked cards (imagine a magician sliding a stack of cards across the table). active card (clicking a card) will make the cards pop forward, but still stay in place.

Then: "no need for my decisions. remove human in the loop." — the assistant's proposals (see analysis)
are the spec.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Every method unique in colour and in icon | 1 |
| R2 | Checklist icon switcher fits one row | 2 |
| R3 | Stacked cards; clicking pops the active stack forward in place (desktop revamp) | 3 |

## Scope

**In scope:** `web/` leaderboard page, its view helpers and CSS, `StrategySwitch`, `components/roster.ts`
icon resolution and its consumers, `globals.css` tint tokens, verify-seer leaderboard feature doc +
twin UI step.
**Out of scope:** engine and DB (twin rows keep their stored `icon`; the web resolves a unique display
icon), the `RetiredShelf` layout (beyond the new colours/icons), the mobile (< 1024 px) layout
(beyond the new colours/icons), every other page's layout.

## Invariants

1. `npx tsc --noEmit && npm test` pass in `web/` at the end of every phase.
2. Mobile (< 1024 px) leaderboard layout is unchanged apart from colours and icons.
3. Every button stays icon-only (Lucide) with `aria-label` and a `data-tip` tooltip (CLAUDE.md).
4. Every new colour token is defined for light and dark (`@media (prefers-color-scheme: dark)`, the
   file's existing pattern). Butter is never a strategy colour.
5. Ranking (`compare`) and checklist logic are untouched.
6. No two rows of `board.rows` share tint, line colour or display icon while research strategies ≤ 12.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 ✓ | Unique colour and icon per method | R1 | `web` | 13 | — | NORMAL | `.workflows/plan/leaderboard-desktop-revamp/phase-1.md` | P1-WEB-A59X | — |
| 2 ✓ | One-row checklist switcher | R2 | `web` | 7 | 1 | EASY | `.workflows/plan/leaderboard-desktop-revamp/phase-2.md` | P1-WEB-1PLT | — |
| 3 | Desktop card stacks | R3 | `web` | 7 | 1, 2 | HARD | `.workflows/plan/leaderboard-desktop-revamp/phase-3.md` | P1-WEB-B6MG | — |

Sequential on purpose: all three edit `leaderboard/page.tsx` and/or `leaderboard.module.css`, and
this laptop crashes running concurrent phase sessions.

### Phase 1 — Unique colour and icon per method
**Satisfies:** R1
**Owns:** six new partner tints in `globals.css` (`--iris/teal/moss/berry/orchid/amber`, each with
`--<x>-line` and `.bg-<x>`, light and dark), each the neighbour hue of one base tint (lav, sky, sage,
rose, plum, stone). `looks()` rewritten (`PARTNER_BGS`, `SLOT_BGS`, `PALETTE_SIZE`; `LOOK_PERIOD`
12 → 24): originals take `SLOT_BGS` in roster order (six bases, then partners last family first), a
twin takes its original's partner with a `TWIN_DASHES` stroke, or the first free slot when held;
sheets unique up to 12 research strategies, lines up to 24 claims. `view.test.ts` `looks` tests
rewritten plus a `globals.css` palette-token test. In `components/roster.ts`: `TWIN_ICON`,
`SPARE_ICONS`, `displayIcons`, `withDisplayIcons` (SPY keeps landmark; twin → partner icon; collision
→ next spare), applied in `leaderboard/page.tsx` (line 6 import; line 33 rebuilds `board` with display
icons), positions, history and `sean/plan`. verify-seer `leaderboard.md` (twin bullet rewritten once
to "partner colour, own icon", new uniqueness bullet, twin-step comment, two gotchas),
`positions-history.md`, and a rewritten `steps/leaderboard-twin.mjs`.
**Does not touch:** card layout and `card()` markup (its `strategyIcon(st.icon)` line stays), the
checklist `StrategySwitch` call, `StrategySwitch.*`, `leaderboard.module.css`, `RetiredShelf.tsx`,
engine, DB.
**Exit criteria:** `tsc` + `npm test` green; tests prove uniqueness of tint/line/icon over a
12-strategy roster with twins; the twin step fails on base with `card is not bg-teal` and passes
after; Positions/History serve `lucide-rocket` for the twin; the real board's 1440 screenshots show
every live card with its own sheet and icon.

### Phase 2 — One-row checklist switcher
**Satisfies:** R2
**Owns:** an opt-in `fit` prop on `StrategySwitch` (`--n` inline, `.fit` in its CSS module): at
≥ 1024 px a grid with one equal `minmax(0, 46px)` column per button, buttons round and shrinking
together to fit, **no floor** (≥ 32 px up to 8 strategies, ~23 px at 12), never wrapping; below
1024 px a `fit` row is the unchanged loose wrapping row. Its use (`fit`) on the leaderboard checklist
`StrategySwitch` (page.tsx line 163 after Phase 1); `.switch` reduced to `padding-bottom: 8px`
(leaderboard.module.css line 45); new `StrategySwitch.test.tsx`; new verify step
`leaderboard-switch-row.mjs`; one sentence and one command line in verify-seer `leaderboard.md`.
**Does not touch:** other StrategySwitch callers' look (default mode unchanged), the phone layout,
colours/icons, card layout, `.top`'s 380 px column.
**Exit criteria:** `tsc` + `npm test` green; at 1024/1280/1440 the switcher is one row with the real
count, 7 and 12 strategies (`leaderboard-switch-row.mjs` PASS); 390, `/positions` and `/history`
shots exit 0 unchanged.

### Phase 3 — Desktop card stacks
**Satisfies:** R3
**Owns:** `stacks()` in `view.ts` (+ `describe('stacks')`); in `page.tsx` the desktop (≥ 1024 px)
live-card section: one deck per family (`deck()`, `data-deck`/`data-open`), the original on top and
its twin tucked behind, offset up/right so its edge and partner colour peek out; the deck holding the
pick opens (one column per card, twin fanned out beside the original) and pops forward in its own
slot (raised, 2% larger, shadowed); the picked card is still the tab into the months sheet
(`tabEdge` over `decks.flat()`, `data-edge` replacing the `:first-child/:last-child` fillet rule);
`prefers-reduced-motion` disables the motion; every card stays a `Link` with `href`, `data-status`
and `aria-current`; whole codes (`breakable`) and chips inside the card; legend on one row
(`.legendLabel`); no horizontal scroll at 1280 and 1440; "No common window yet" printed once
(`second.desk`); `RetiredShelf` `cols={rowCols}` so the shelf keeps the row's column width. New
verify step `leaderboard-stack.mjs`; the twin-click line of Phase 1's `leaderboard-twin.mjs`; stack
bullet, journeys and the desktop-ellipsis gotcha in verify-seer `leaderboard.md`.
**Does not touch:** mobile layout, `RetiredShelf.tsx`, `.switch`/`StrategySwitch`, `.top`,
`globals.css`, `looks()`, `roster.ts`, compare/checklist logic.
**Exit criteria:** `tsc` + `npm test` green; `leaderboard-stack.mjs` PASS at 1280 light and 1440
dark; `shoot` at 1280/1440 with no horizontal scroll on demo and real roster; "No common window yet"
counts 1 on the `--empty` board; the 390 px fingerprint identical before and after.

## Reconciliation Log

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Index Phase 2 said switcher buttons "min ~32px"; phase 2 has no floor (~23 px at 12 in the 324 px row) | Contract drift (index vs plan) | Index Phase 2 section reworded: no floor, ≥ 32 px up to 8, ~23 px at 12 |
| 2 | Phase 3 wrote `card()`'s icon line as `const Icon = iconOf(st.id);`; no `iconOf` exists in page.tsx. Phase 1 leaves the line as `strategyIcon(st.icon)` and supplies display icons by rebuilding `board` at line 33 | Unmet assumption / broken-build phase | Phase 3 Step 4 now quotes `const Icon = strategyIcon(st.icon);`; phase 3 Requires states phase 1's real line-6 import and line-33 block |
| 3 | Phase 3 hedged that Phase 1 "may have changed" page.tsx's `./view` import and view.test.ts's import | File collision (quotes pre-change state) | Phase 3 3a states page.tsx's view import is unchanged by phase 1; Step 2 quotes phase 1's view.test.ts import list plus `stacks` |
| 4 | Phase 3 cited page.tsx/view.ts/view.test.ts line numbers at base; phase 1 adds 8 lines at page.tsx:33 and rewrites view.ts:34-121 and view.test.ts:1-110 | File collision | Phase 3 page.tsx numbers shifted +8 (102-108, 183-186, 224/226, 235-304, 307, 328-350); view.ts/view.test.ts located by anchor text |
| 5 | Phase 3 Step 9 edits `leaderboard-twin.mjs`, owned by phase 1, quoting the base file's line 39 | File collision / duplicate ownership | Assigned to phase 3 as an edit-after-peer; it quotes phase 1's rewritten click line (line 63 of phase 1's file). Phase 1 Handoffs and Step 10 Impact updated to say so |
| 6 | Phase 1's twin step asserts on `a[href][data-status]` and `nav[aria-label="Strategy"]` | Requirement check | Confirmed phase 3 keeps both (cards remain `Link` with `href` + `data-status`, SPY `article[data-status]`; switcher untouched); stated in phase 3 Step 9 |
| 7 | `RetiredShelf` `cols={live.length}` left unowned by phase 3; with decks the live row no longer has one column per card | Gap | Assigned to phase 3: `rowCols` (decks, plus extra columns of the open deck) via a shared `isOpen`; `cols={rowCols}`. `RetiredShelf.tsx` untouched |
| 8 | `leaderboard.md` edited by all three phases, each quoting base state; phase 3 anchored its new lines "after the twin bullet / after the twin.mjs line", the same anchors phase 1 rewrites and phase 2 appends after | File collision | Phase 1 rewrites the twin bullet once (the stale "in the original's colour" sentence); phase 2 quotes phase 1's twin.mjs line and its own sentence at line 14; phase 3 anchors after phase 1's uniqueness bullet and after phase 2's switch-row line, and is told not to reintroduce the stale sentence |
| 9 | Phase 2 Requires claimed phase 1 changed the checklist `strategies={...}` expression, and Step 1 hedged that phase 1 might change `StrategySwitch.tsx` | Contract drift / unmet assumption | Phase 2 Requires, Step 1 note, Step 4 and Handoffs restated: phase 1 leaves both as at base; the call sits at lines 162-163 |
| 10 | Phase 2 applied the one-row fit grid at every width, mobile included; invariant 2 holds the mobile leaderboard layout unchanged | Contract drift vs invariant | Decided on rung 1 (see Decisions): grid behind `@media (min-width: 1024px)`, loose row below; step file refuses < 1024 px; journey 3 and exit criteria changed to "390 unchanged" |
| 11 | Phase 2 edits `.switch` (css:45); phase 3 edits css after 78, line 206, after 219 and end of file; phase 3's overflow/legend fix could re-squeeze phase 2's 324 px checklist row | File collision check | No overlapping region. Phase 3 does not touch `.top`'s `minmax(0,1fr) 380px` grid or use `overflow` clipping; stated in phase 3 Step 7 Impact. Phase 3's neighbour check re-runs `leaderboard-switch-row.mjs` |
| 12 | Phase 3 said a switcher overflow culprit at Step 0 is "reported and left unfixed", which would leave its own no-scroll exit criterion unmeetable | Ordering | Phase 2's exit criteria already rule it out; phase 3 Handoffs now say stop and report it as a phase 2 regression |
| 13 | Phase 3's view.test.ts helper `row(id, twinOf, …)` shadows phase 1's new module-level `twinOf()` | File collision (cosmetic) | Parameter renamed to `of` |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Twin colour: adjacent partner hue vs fully separate colour | partner hue — unique but still reads as a pair | 5: user said "no need for my decisions", assistant's proposal stands |
| Cards: flat overlapping row vs one stack per family | one stack per family, with the user's pop-forward-in-place behaviour | 5: user invited "a better one"; proposal stands |
| Switcher: shrink to fit vs drop on desktop | shrink to fit (keep it) | 5: proposal's first choice; smallest change |
| Icon uniqueness: DB/engine change vs web display resolution | web display resolution, no migration | 6: CLAUDE.md "smallest change"; engine writes twin rows nightly |
| Colour stability: stored `color` column vs roster-order assignment | roster-order (family-based) assignment, no column | 6: smallest change; partner rule already keeps originals' colours stable when twins arrive |
| Switcher button floor: index's "min ~32px" vs phase 2's no floor | no floor; ≥ 32 px up to 8 strategies, ~23 px at 12 | 4: R2 "always fits on one row"; a 32 px floor cannot fit 12 in 324 px (428 px needed) |
| One-row fit on mobile too (phase 2's choice) vs desktop only | desktop only (≥ 1024 px); the phone keeps the loose wrapping row | 1: invariant 2, mobile leaderboard layout unchanged apart from colours and icons (agreed by rung 2: the index's Phase 2 exit criteria name 1024/1280/1440 only) |
| `RetiredShelf` `cols`: keep `live.length` vs follow the deck row | `cols={rowCols}`, the live row's real column count (decks, plus the open deck's extra columns) | 4: index Scope keeps the shelf layout unchanged, and that layout is "the shelf keeps the live row's column width" (`RetiredShelf` `cols` doc); `live.length` would change it to 8 narrow columns under 5–6 |
| `card()` icon: a phase-3 `iconOf(st.id)` helper vs phase 1's upstream `board` rebuild | keep `strategyIcon(st.icon)`; display icons arrive on `st.icon` | 3: phase 1's code block (the line-33 `board` rebuild) is the landed contract; no `iconOf` exists |

## Open Questions

None.

## Rollback

Each phase is one commit on the feature branch; revert it. Whole set: revert the merge commit on main.

## Next

    /implement -f .workflows/plan/LEADERBOARD_DESKTOP_REVAMP_PLAN.md --phase 1

    /analyze-orchestrator -f .workflows/plan/LEADERBOARD_DESKTOP_REVAMP_PLAN.md
