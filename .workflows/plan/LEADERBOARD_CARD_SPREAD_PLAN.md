# Plan: Leaderboard card spread

**Slug:** leaderboard-card-spread
**Date:** 2026-11-12 07:58 WIB
**Analysis:** `.workflows/analyze/20261112-075853-LCS1_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/leaderboard-card-spread`
**Branch:** `feature/leaderboard-card-spread` (base: `origin/main` @ `650b355`)
**Phases:** 1
**Status:** complete
**Coordinator:** —

---

## Why

> can we change this to something like a straight horizontal spread of cards?
> and if we click a card, it will still fixed in its position, but it is brought to the top.
> we tried to revamp the UI sometime ago . but turns out the result is trash.
> there is a stupid pairing where when i click a card like COSK-FR-GT-CX , then COSK-FR-GT will pop up a little bit as well. remove this .
> … i want it to look like a spread of cards dimana satu kartu sedikit menutup kartu yang lain, dan seterusnya
>
> fucking beautiful. one preference by me is that we do "left covers right" because this way user can always see the baseline: SPY and can easily compare it with other active card.

The visual reference is the prototype the owner approved: https://claude.ai/artifact/QVEoySe8Q1jjmtLsK7hUyD (source `/tmp/claude-1000/-home-miftah-seer/7860c0df-22cc-462e-b6d4-62858a0ec26a/scratchpad/card-spread.html`, in "left covers right" mode at 40% overlap).

## Requirements

| ID | What the user asked for (verbatim) | Phases |
|---|---|---|
| R1 | "can we change this to something like a straight horizontal spread of cards?" … "i want it to look like a spread of cards dimana satu kartu sedikit menutup kartu yang lain, dan seterusnya" | 1 |
| R2 | "one preference by me is that we do "left covers right" because this way user can always see the baseline: SPY and can easily compare it with other active card." | 1 |
| R3 | "and if we click a card, it will still fixed in its position, but it is brought to the top." | 1 |
| R4 | "there is a stupid pairing where when i click a card like COSK-FR-GT-CX , then COSK-FR-GT will pop up a little bit as well. remove this ." | 1 |

### Acceptance Criteria

| ID | Pattern | Criterion | Phases | Journeys |
|---|---|---|---|---|
| R1.1 | state | WHILE the viewport is at least 1024px wide THE SYSTEM SHALL render every live strategy card in one horizontal row in board order, each card after the first starting 60% of a card width after the previous card's left edge (40% overlap), all cards equal width, the row filling its container without horizontal scroll | 1 | P1.J1, P1.J7 |
| R1.2 | state | WHILE the viewport is narrower than 1024px THE SYSTEM SHALL render the live cards as the existing single column, with no overlap | 1 | P1.J6 |
| R1.3 | state | WHILE the viewport is at least 1024px wide THE SYSTEM SHALL show each card's code and total return inside the part of the card that no neighbour covers | 1 | P1.J3, P1.J7 |
| R2.1 | state | WHILE the viewport is at least 1024px wide THE SYSTEM SHALL stack each card that is not picked above every card to its right | 1 | P1.J2 |
| R2.2 | ubiquitous | THE SYSTEM SHALL keep the SPY card above every other card, the picked one included, so no other card covers any part of it | 1 | P1.J2, P1.J7 |
| R3.1 | event | WHEN the owner clicks a research card THE SYSTEM SHALL navigate to `/leaderboard?s=<id>`, raise that card above every card except SPY, and give it the front card's shadow | 1 | P1.J4, P1.J5, P1.J7 |
| R3.2 | event | WHEN the owner clicks a card THE SYSTEM SHALL leave the position and size of every card in the row unchanged (no translate, no scale, no column added) | 1 | P1.J4 |
| R3.3 | event | WHEN the owner picks a card THE SYSTEM SHALL keep driving the go-live checklist, the month-by-month sheet and the chart from that pick exactly as before, with the picked card still the tab that meets the month-by-month sheet | 1 | P1.J5 |
| R4.1 | event | WHEN the owner clicks a Claude twin's card THE SYSTEM SHALL leave its original's card exactly where and how it was (no raise, no shadow, no move) | 1 | P1.J4 |
| R4.2 | ubiquitous | THE SYSTEM SHALL render an original and its Claude twin as two independent cards with no deck wrapper, no tucked twin and no peek strip | 1 | P1.J1 |

## Scope

**In scope:** the desktop (≥1024px) live card row on `/leaderboard`, the deletion of `stacks()` and its tests, and the verify-seer leaderboard entry and its desktop step.
**Out of scope:** the mobile column (<1024px), the retired shelf's look (only its `--cols` input changes), the chart, the checklist, the month table's contents, every other page, and the broader "whole UI" revamp (the owner asked to do this one thing first).

## Invariants

1. The tree builds and `npx tsc --noEmit && npm test` pass in `web/`.
2. Below 1024px, `/leaderboard` renders exactly as it does on `origin/main` @ 650b355.
3. No client component is added. The z-order comes from the server-known pick, in the style attribute.
4. `attachedOriginal`, `orderTwins`, `looks`, `displayIcons` and twin colours and icons are untouched.
5. A user-facing change updates its verify-seer feature-map entry in the same commit (CLAUDE.md).
6. UI conventions hold: Lucide icons, `data-tip` tooltips, Seer v2 tokens, nothing generic.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 ✅ | Flat overlapping card spread | R1, R2, R3, R4 | `web/app/(app)/leaderboard` + verify-seer | 6 | — | NORMAL | `.workflows/plan/leaderboard-card-spread/phase-1.md` | P2-WEB-A129 | — |

### Phase 1 — Flat overlapping card spread
**Satisfies:** R1, R2, R3, R4 (one phase: all four are one CSS and markup change to one row and cannot ship apart without leaving the decks half removed)
**Owns:** `page.tsx`, `leaderboard.module.css`, `view.ts` (`stacks` removal), `view.test.ts`, `features/leaderboard.md`, `steps/leaderboard-stack.mjs` → `steps/leaderboard-spread.mjs`
**Does not touch:** `lib/strategy.ts`, `lib/data.ts`, `components/*`, `RetiredShelf.tsx` (only its `cols` prop value changes, at the call site), anything below 1024px
**Exit criteria:** every criterion above traced and passing. tsc and vitest green. The verify-seer spread step PASSes at 1280 and 1440. Screenshots at 1440 light and dark plus 390 dark look like the approved prototype.

## Reconciliation Log

| Conflict | Phases | Resolution |
|---|---|---|

single phase — nothing to reconcile

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Left covers right hides each card's left 40%, where the code and return sit today | On the desktop row the card's contents are mirrored: icon top-left, code, chips, total return and metrics right-aligned, so the uncovered right 60% carries them (R1.3) | 5: user's raw input ("easily compare it with other active card" needs each card readable) |
| Should the picked card rise above SPY? | No. SPY is always topmost and the pick rises above every other card. SPY is never a pick | 5: user's raw input ("always see the baseline: SPY") |
| A picked card raised in place covers its left neighbour's right 40% | Accepted. The neighbour keeps its name as a tooltip. Owner reviews it in the screenshots | 5: "fixed in its position, but it is brought to the top" |
| Keep the tab (picked card meets the month sheet) or drop it for the prototype's free-floating shadow | Keep the tab. The front shadow is cast up and sideways only, never onto the sheet | 2: exit criterion R3.3 "exactly as before" |
| Card width | Fill the row: width = 100% / (1 + (n−1)·0.6), so there is never horizontal scroll | 6: convention (the row never scrolled) |
| Retired shelf `cols` (counted decks) | `live.length` | 6: convention (the shelf keeps the live row's count) |
| `leaderboard-stack.mjs` | Replaced by `leaderboard-spread.mjs`. The entry's commands and gotchas are rewritten | 1: invariant 5 |

## Open Questions

## Handoffs (for the completion handler)

- `web/package_readme.md` still describes `stacks()`, decks, `rowCols` and `leaderboard-stack.mjs`. The readme-updater should refresh it.
- `leaderboard-twin.mjs:76-78`: its comment calls the twin "tucked". The click still lands, so only the comment is stale.

## Rollback

One commit on `feature/leaderboard-card-spread`. Revert it to restore the decks.

## Next

    /implement -f .workflows/plan/LEADERBOARD_CARD_SPREAD_PLAN.md --phase 1
