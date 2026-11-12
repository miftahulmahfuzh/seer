# Plan: Leaderboard chart legend — left-aligned toggles that highlight lines

**Slug:** leaderboard-legend-toggles
**Date:** 2026-11-12 09:45
**Analysis:** `.workflows/analyze/20261112-094511-L7G2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/leaderboard-legend-toggles`
**Branch:** `feature/leaderboard-legend-toggles` (base: `origin/main` @ `ac5a46b`)
**Phases:** 1
**Status:** complete
**Coordinator:** —

---

## Why

> there is a legend about which line is which, drag this legend to the leftmost side of the box. so it is aligned left. make sure it is aligned vertically at the start of the character with the SPY, champion text
>
> second, i want this legend to be able to be clicked (function as a button). it will act like a toggle (active state and inactive state) in which activating it will highlight (you can propose how we can highlight the line cleanly) the correspending graph line. we can activate all lines in the graph. but mostly, i will use this toggle to activate two methods line so i can compare them easier.
>
> third, we can click a card. clicking a card (activating a card in any way) will automatically highlight its correspending graph line (and change its correspending legend button to be in active state) as well. but, i can deactivate this highlighted line after by clicking the correspending legend button.

Answers to the follow-up: card click **adds** to the highlighted set (not replace); toggles live in **page memory only** (not the URL).

Accepted highlight proposal: with ≥1 active, active lines keep their colour, ~1px thicker, drawn on top; every other line fades to ~20% opacity. Active legend item gets a soft tint pill; inactive items fade while anything is active. Nothing active = today's chart exactly. SPY is toggleable.

## Requirements

| ID | What the user asked for (verbatim) | Phases |
|---|---|---|
| R1 | there is a legend about which line is which, drag this legend to the leftmost side of the box. so it is aligned left. make sure it is aligned vertically at the start of the character with the SPY, champion text | 1 |
| R2 | second, i want this legend to be able to be clicked (function as a button). it will act like a toggle (active state and inactive state) in which activating it will highlight (you can propose how we can highlight the line cleanly) the correspending graph line. we can activate all lines in the graph. but mostly, i will use this toggle to activate two methods line so i can compare them easier. | 1 |
| R3 | third, we can click a card. clicking a card (activating a card in any way) will automatically highlight its correspending graph line (and change its correspending legend button to be in active state) as well. but, i can deactivate this highlighted line after by clicking the correspending legend button. — "Add." / "memory only for now." | 1 |

### Acceptance Criteria

| ID | Pattern | Criterion | Phases | Journeys |
|---|---|---|---|---|
| R1.1 | state | WHILE the viewport is at least 1024px wide THE SYSTEM SHALL render the chart legend on its own row below the headline figures, its first swatch's left edge within 1px of the left edge of the champion label ("SPY, champion") | 1 | P1.J1 |
| R1.2 | state | WHILE the viewport is at least 1024px wide THE SYSTEM SHALL keep the legend on a single row (no wrap) | 1 | P1.J1 |
| R2.1 | event | WHEN the owner clicks a legend item THE SYSTEM SHALL flip that item's `aria-pressed` between true and false | 1 | P1.J2, P1.J9 |
| R2.2 | state | WHILE one or more legend items are active THE SYSTEM SHALL draw each active strategy's line in its own colour, about 1px thicker, above every inactive line, and fade every inactive line to about 20% opacity | 1 | P1.J3 |
| R2.3 | state | WHILE no legend item is active THE SYSTEM SHALL draw every line exactly as today (own colour, own width, full opacity) | 1 | P1.J5 |
| R2.4 | ubiquitous | THE SYSTEM SHALL let every legend item, SPY included, be active at the same time | 1 | P1.J4 |
| R3.1 | event | WHEN the owner picks a card (lands on or navigates to `/leaderboard?s=X`) THE SYSTEM SHALL add X to the active set, marking its line highlighted and its legend item `aria-pressed="true"`, without removing strategies already active | 1 | P1.J6 |
| R3.2 | event | WHEN the owner clicks the picked strategy's active legend item THE SYSTEM SHALL un-highlight its line while the card stays picked (`aria-current` and the checklist unchanged) | 1 | P1.J7 |
| R3.3 | event | WHEN the page is reloaded THE SYSTEM SHALL start from only the picked strategy active (no state from the URL or storage) | 1 | P1.J8 |

## Scope

**In scope:** a new client component `web/app/(app)/leaderboard/ChartPanel.tsx` (owns the highlight set, the svg lines and both legends), its test, `page.tsx` wiring (drop the server `Legend`), `leaderboard.module.css` legend/toggle/highlight styles, the verify-seer feature map entry and a new Playwright step.
**Out of scope:** `buildChart`'s maths, the cards, the checklist, `StrategySwitch`, URL params, `/sera` charts (`components/sera/charts/*`), engine.

## Invariants

1. With nothing active the chart renders byte-identical stroke colours, widths and dashes to today, at full opacity.
2. A card pick still navigates exactly as today (`<Link href="/leaderboard?s=X" scroll={false}>`); nothing about cards, checklist or month table changes.
3. Highlight state is never read from or written to the URL or browser storage.
4. `npx tsc --noEmit && npm test` pass in `web/`.
5. Legend item ids/labels/tooltips are the same strategies, codes and full names (retired tip suffix kept) as today's `Legend`.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | ChartPanel: left legend row, toggle highlight, pick seeds it | R1, R2, R3 | `web/app/(app)/leaderboard` | 6 | — | NORMAL | `.workflows/plan/leaderboard-legend-toggles/phase-1.md` | P2-WEB-SF4E ✓ | — |

### Phase 1 — ChartPanel: left legend row, toggle highlight, pick seeds it
**Satisfies:** R1, R2, R3 (one component holds all three; splitting would leave a toggle with no state or a state with no toggle — the coupling is real)
**Owns:** `ChartPanel.tsx` (new), `ChartPanel.test.tsx` (new), `page.tsx` chartSheet + `Legend` removal, `leaderboard.module.css`, `.claude/skills/verify-seer/features/leaderboard.md`, `.claude/skills/verify-seer/features/steps/leaderboard-legend.mjs` (new).
**Does not touch:** `view.ts` logic, cards, checklist, `StrategySwitch`, `components/sera/charts/*`.
**Exit criteria:** every criterion above passes its journey; tsc + vitest green; screenshots at 1440 and 390, light and dark.

## Reconciliation Log

single phase — nothing to reconcile

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| CLAUDE.md "every button is icon-only" vs a legend toggle that must show the strategy code | text toggle buttons with `aria-pressed`, `aria-label` and `data-tip` (full name) | 5: user's raw input — the legend items themselves are the requested buttons, and the owner accepted the exception in the discussion turn |
| Card click: add vs replace | add | 5: user's answer "alright, Add." |
| Persistence | page memory only | 5: user's answer "memory only for now." |
| How a pick reaches client state | ChartPanel takes `pickId` prop; on change (soft navigation keeps the component mounted) it adds the id — the "adjust state when a prop changes" render-time pattern, not a URL read | 6: convention (React + app-router soft nav) |
| Alignment anchor for R1.1 ("start of the character with the SPY, champion text") | the champion label's left edge (crown), which is the same `.pad` edge as "−3.7%" | 5: user's raw input + screenshot — figure and label start on one edge |
| Landing with no `?s=` | the default pick (the card already shown as picked) starts highlighted | 5: "clicking a card (activating a card in any way)" — a default-picked card is active |
| Desktop legend position | its own row after the window line, directly above the chart | 6: convention — keeps the window line beside the figure it qualifies; R1.1 still holds |
| SPY's active pill tint (`var(--sheet)` is invisible on the sheet) | `var(--chip-plain)` for `bg-sheet` looks | 6: convention (`.card:global(.bg-sheet) .icon` does the same) |

## Open Questions

## Rollback

Revert the phase commit; no data or schema involved.

## Next

    /implement -f .workflows/plan/LEADERBOARD_LEGEND_TOGGLES_PLAN.md --phase 1
