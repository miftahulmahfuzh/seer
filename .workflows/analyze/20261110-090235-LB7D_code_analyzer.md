# Code Analysis: Leaderboard desktop revamp (unique method identity, one-row switcher, card stacks)

**Type:** Feature Update
**Date:** 2026-11-10 09:02 WIB
**Session ID:** 20261110-090235-LB7D
**Plan:** `.workflows/plan/LEADERBOARD_DESKTOP_REVAMP_PLAN.md` (3 phases)
**Worktree:** `/home/miftah/.worktrees/seer/leaderboard-desktop-revamp`, branch `feature/leaderboard-desktop-revamp` (base HEAD 22d1051)

---

## User Input

### Original User Request

First message (the brainstorm):

> let's brainstorm:
> check https://seertrade.site/leaderboard . we need to revamp the desktop UI fully.
> we added claude adversarial methods in here. but it fucked up the UI.
> my idea:
> 1. we need to make EVERY METHOD unique: unique in color, unique in icon.
> 2. the go live checklist has a list of icons at the top. make sure it only takes one row, right now, one icon flowed over to make a second row
> 3. my idea (you may propose a btter one) : change the list of thin boxes to just somekind of stacked cards (imagine a magician sliding a stack of cards across the table). active card (clicking a card) will make the cards pop forward, but still stay in place.
>
> propose your opinions

The assistant proposed (and the owner then said "no need for my decisions. remove human in the loop.", so the proposals stand as the spec):

- Unique colour per method from a ~12-hue palette, a twin taking a hue *adjacent* to its original's so the pair still reads as a pair; a unique icon per method, twins included (not a shared "Claude" badge).
- Switcher: a grid of equal columns that shrinks buttons to fit one row.
- Cards: one stack (deck) per method family — the original on top, its Claude twin tucked behind and peeking out. Clicking a stack pops it forward while it stays in its slot and fans the twin out beside the original. Reduced motion respected; cards stay links with `aria-current`.

Then `/analyze` with no arguments, and mid-turn: "no need for my decisions. remove human in the loop."

### User-Provided Context

Desktop screenshot at 1440 px (light), taken this session from `npm run dev:env` against the real DB:
8 cards on the live row (SPY, C, COSK, COSK+Claude, RAW35, RAW35+Claude, A, A+Claude). Desktop
card names truncate to "C…", "R…", "A…"; chips ("Paper", "Not ranked") overflow the card edge;
the page scrolls 8 px horizontally (shoot.mjs PROBLEMS line); the checklist switcher shows 7
buttons and wraps the 7th onto a second row; the chart legend wraps to two rows; "No common
window yet" is printed twice in the chart sheet. COSK and COSK+Claude share teal and the
cloud-lightning icon; RAW35/RAW35+Claude share sage and zap; A/A+Claude share rose and sigma.

### User-Provided Files
none

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Every method is unique in colour and unique in icon |
| R2 | The go-live checklist's icon switcher always fits on one row |
| R3 | Replace the row of thin cards with stacked cards; clicking pops the active one forward while it stays in place (desktop revamp) |

---

## Detailed Requirements Understanding

**Problem.** The leaderboard's identity system was designed for ≤ 6 research strategies with twins
deliberately sharing their original's colour (`looks()` in `view.ts`) and the engine copying the
original's `icon` onto each twin row. Three twins (migration 027 + `ensure_twins`) doubled the card
count, so the desktop card row is too narrow, identities collide, and the switcher wraps.

**Success criteria.**
- No two strategies in `board.rows` (live and retired) share a card tint, a chart line colour, or an
  icon, for any roster up to the palette size (12 research strategies). Beyond that, lines stay
  unique by dash pattern (existing lap mechanism), as today.
- A twin's hue is the "partner" of its original's hue, so the pair still reads as related.
- The same unique icon shows for a strategy everywhere the site shows strategy icons (leaderboard
  switch + cards, positions, history, Sean's plan pickers).
- At ≥ 1024 px the checklist switcher is exactly one row for any count of strategies.
- At ≥ 1024 px the live cards render as one stack per family, names un-truncated, chips inside the
  card, no horizontal page scroll at 1280 and 1440, legend on one row.
- Mobile (< 1024 px) layout unchanged except the new colours/icons.

**Key considerations.**
- `view.ts` header promise "adding twins moves no other strategy's colour" was the reason for the
  shared look; it is replaced by the partner-hue rule, under which a twin still takes no *family*
  slot, so it still moves no other original's colour.
- Twins are created nightly by the engine (`paper/store.py ensure_twins` via `roster.plan_twins`),
  copying `icon` from the original. Changing the stored icon would need engine + migration work for a
  purely visual concern; the web can resolve a unique display icon from the roster instead.
- `verify-seer` feature map `leaderboard.md` and its UI step `steps/leaderboard-twin.mjs` assert
  "in the original's colour" — they must move with R1.
- Butter is reserved (checklist sheet on mobile); stays out of the rotation.
- Dark mode tokens are defined only under `@media (prefers-color-scheme: dark)` in `globals.css`;
  new tokens follow that same pattern.

**Assumptions.** Desktop breakpoint is the existing 1024 px. Retired cards on `RetiredShelf` stay a
flat row (out of scope beyond new colours/icons).

---

## Analysis Scope

### Discovered Related Files
- `web/app/(app)/leaderboard/page.tsx` — server component; chart sheet, checklist sheet (with `StrategySwitch`), months sheet, card row, `card()`, `Legend`, `buildChart`.
- `web/app/(app)/leaderboard/view.ts` — `CARD_BGS`, `LAP_DASHES`, `TWIN_DASHES`, `LOOK_PERIOD`, `Look`, `looks()`, `LOOK_FALLBACK`, `researchOf`, `compare`, …
- `web/app/(app)/leaderboard/view.test.ts` — `describe('looks')` lines 19-110 pin twin-shares-colour behaviour.
- `web/app/(app)/leaderboard/leaderboard.module.css` (231 lines) — `.top`, `.legend`, `.switch` (line 45, `display:flex; gap:6px`), `.cards`/`.card` (78-), desktop blocks at 127/139.
- `web/app/(app)/leaderboard/RetiredShelf.tsx`, `PickName.tsx`.
- `web/components/StrategySwitch.tsx` + `.module.css` — icon-only `Link` per strategy, `icon-btn md`, `strategyIcon(st.icon)`.
- `web/components/roster.ts` (+ `roster.test.ts`) — `ICONS` registry, `strategyIcon(name)`.
- `web/app/globals.css` — tint tokens lines 15-29 (light), 61-73 (dark), `.bg-*` classes 237-243, `desk-only` at 246.
- `web/lib/strategy.ts` — `attachedOriginal`.
- Other icon consumers: `web/app/(app)/positions/page.tsx:62`, `web/app/(app)/history/page.tsx:132,154`, `web/app/sean/plan/page.tsx:77`, `web/app/sean/plan/LinkPicker.tsx:36`, `web/lib/sean/planData.ts:26`.
- `.claude/skills/verify-seer/features/leaderboard.md`, `.claude/skills/verify-seer/features/steps/leaderboard-twin.mjs`.
- Engine (read only, not changed): `engine/src/seer_engine/paper/store.py:396 ensure_twins`, `paper/roster.py plan_twins`.

---

## Current Dataflow

### Entry: `GET /leaderboard?s=<id>` → `Leaderboard()` (`page.tsx:30`)
1. `leaderboard()` (lib/data) returns `board.rows` (strategy + metrics + curve), ordered by `sort`.
2. `live` / `retiredRows` split on `status`.
3. `looks(roster)` (`view.ts:87`) → `Map<id, Look>`: SPY plain sheet + dotted; each non-twin
   research strategy takes `CARD_BGS[i % 6]` with lap dash; a twin whose original is on the roster
   copies the original's `bg/tint/line` with a `TWIN_DASHES` stroke.
4. `buildChart` draws one path per row with `look.line/width/dash`; `Legend` draws swatch + `short`.
5. Checklist sheet: `StrategySwitch strategies={switchable}` (research rows of `shown`), each icon
   from `strategyIcon(st.icon)` — the DB icon, identical for a twin and its original.
6. Months sheet tinted by the pick's `look.bg`, `data-tab` first/last by position of pick in `live`.
7. Cards: `live.map(r => card(r, true))` in `.cards` (`display: contents` on mobile; desktop grid),
   each a `Link` to `?s=id` with `look.bg` and `--tint`; icon `strategyIcon(st.icon)`.

### Persistence
None written. Twin rows (incl. `icon`) are written nightly by the engine's `ensure_twins`.

---

## Key Data Structures
- `Look = { bg, tint, line, width, dash }` (`view.ts:68`).
- `RosterIn = { id, isChampion, isBenchmark, twinOf? }` (`view.ts:23`).
- `StrategySwitch` props `{ strategies: {id,name,icon}[], current, href, label, allTip?, seg? }`.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `CARD_BGS` | view.ts:49 | def | web |
| `LAP_DASHES`, `TWIN_DASHES`, `LOOK_PERIOD` | view.ts:52-62 | def | web |
| `looks()` | view.ts:87; page.tsx:41 | def · call | web |
| `describe('looks')` | view.test.ts:19-110 | test | web |
| `strategyIcon` | roster.ts; StrategySwitch.tsx; page.tsx:211; positions:62; history:132,154; sean/plan/page:77; LinkPicker:36 | def · call | web |
| `ICONS` | roster.ts | def | web |
| `--<tint>`, `--<tint>-line`, `.bg-<tint>` | globals.css:15-29, 61-73, 237-243 | config | web |
| `.switch`, `.cards`, `.card*`, `.legend` | leaderboard.module.css | style | web |
| "original's colour" | verify-seer/features/leaderboard.md, steps/leaderboard-twin.mjs | doc · test | skill |

## Impact Points
1. `globals.css` — six new partner tints + lines, light and dark (phase 1).
2. `view.ts` / `view.test.ts` — partner-hue `looks()` (phase 1).
3. `roster.ts` / `roster.test.ts` — unique display icon resolution (phase 1).
4. Icon consumers (leaderboard page, StrategySwitch callers, positions, history, sean/plan) — use the resolved icon (phase 1).
5. verify-seer leaderboard feature doc + twin step (phase 1, then phase 3 for the stack layout).
6. `StrategySwitch` + `leaderboard.module.css .switch` — one-row fit (phase 2).
7. `page.tsx` card section + `leaderboard.module.css` desktop card/legend/overflow (phase 3).

**This document describes. The plan files prescribe.**
