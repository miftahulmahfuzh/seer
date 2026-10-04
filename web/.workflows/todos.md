# Todos: web

**Package Path**: `web`
**Package Code**: WEB
**Last Updated**: 2026-10-04 09:31:37
**Total Active Tasks**: 3

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 1
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 2
- Completed: 0

---

## Active Tasks

### [P0] Critical

### [P1] High
- [ ] **P1-WEB-Y9MV** Phase 10: Web data layer, monthly math, demo seed
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/lib/strategy.ts` (`Engine`, `Gate`, `engineOf`, `parseGate`, `shortLabel`); `web/lib/data.ts` (`Strategy` with `engine/rulesId/paperStart/gate/isPaper/short`; `Holding` with `kind/key/orderId/maxDays` for both engines and the benchmark; `pendingOrders()` → `Pending`/`PendingOrder`; `Trade.key/strategyShort/ExitReason`; leaderboard pnls per engine; `RunStatus.latestStatus/paperStatus/paperError/paperFinishedAt`; `monthly(id, sessionDate)` → `MonthlyTable`); `web/lib/monthly.ts` (new, pure) + `monthly.test.ts` hand-checked fixture; `web/lib/metrics.ts` `checklist(m, spy, gate)` 6th item "Backtest gate passed"; `web/lib/slots.ts` (`slotCount`, `cardBg`; no 4-slot assumption for book); `web/scripts/seed-demo.mjs` in the new shape (gate notes = `roster.py` texts); Step 10 minimal compile fixes to `page.tsx`, `positions/page.tsx`, `leaderboard/page.tsx` (these land before phases 11/12). Does not touch: page components beyond the Step 10 fixes (phases 11, 12), engine. Exit: vitest green incl. monthly fixture (month boundaries, partial first/current month, no-trade months, SPY same months); `tsc --noEmit` clean.
  - **Status**: open
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 10 of 13)
  - **Satisfies**: R4 — Web: Today SPY-champion state, paper labels, book positions/trades, monthly table, leaderboard incl. book strategies, checklist honesty, no 4-slot assumption; R2 — Migration `003` (D6) + roster `strategies` rows with `paper_start` and frozen spec (D4); demo seed in the new shape
  - **Depends on**: P1-ENG-N6UC
  - **Plan**: `.workflows/plan/P1-WEB-Y9MV.md`

- [ ] **P1-WEB-0AHX** Phase 11: Web: Today, Positions, History
  - **Difficulty**: HARD
  - **Type**: Update
  - **Context**: Owns `app/(app)/page.tsx` + `today.module.css` (SPY-champion no-buys state; stale/failed still first), `positions/*` (strategy switcher, paper chip, bracket/book/benchmark cards by `Holding.kind`, `pendingOrders` sheet, paper-step warning), `history/*` (roster-driven filters, book exit reasons signal/forced, paper chip, `Trade.key`), new shared `components/StrategySwitch.tsx` (icon-only links, `?s=`, `href`/`label` props), `components/PaperChip.tsx`, and `components/roster.ts` (only `strategyIcon`, `selectStrategy`, `sharesLabel`: short labels and the paper flag stay phase 10's). The three pages are replaced whole, starting from phase 10 Step 10's versions. Does not touch: leaderboard, `web/lib/*` (consumes phase 10's API; a missing field is added in phase 10's plan, not here). Exit: vitest + `tsc --noEmit` green; screens render on demo data at 414 pt and desktop, light and dark.
  - **Status**: blocked
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 11 of 13)
  - **Satisfies**: R4 — Web: Today SPY-champion state, paper labels, book positions/trades, monthly table, leaderboard incl. book strategies, checklist honesty, no 4-slot assumption
  - **Depends on**: P1-WEB-Y9MV
  - **Plan**: `.workflows/plan/P1-WEB-0AHX.md`

- [ ] **P1-WEB-DX8D** Phase 12: Web: Leaderboard, monthly table, checklist
  - **Difficulty**: HARD
  - **Type**: Update
  - **Context**: Owns `app/(app)/leaderboard/page.tsx` + `leaderboard.module.css` + `view.ts`/`view.test.ts` (leaderboard-only helpers: looks, best research, score line, month rows over phase 10's `MonthlyTable`): roster-driven colors/cards (no hardcoded A/B/C), SPY crown, checklist per research strategy via phase 11's `StrategySwitch`/`selectStrategy`/`strategyIcon` with `checklist(m, spy, gate)` and an honest score line, "Month by month" sheet from `monthly(id, run.sessionDate)` (Return, SPY, Trades, Worst drop; since-start row; partial-month marker). Does not touch: other screens, `web/lib/*`. Exit: as phase 11, on the Leaderboard.
  - **Status**: blocked
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 12 of 13)
  - **Satisfies**: R4 — Web: Today SPY-champion state, paper labels, book positions/trades, monthly table, leaderboard incl. book strategies, checklist honesty, no 4-slot assumption
  - **Depends on**: P1-WEB-0AHX
  - **Plan**: `.workflows/plan/P1-WEB-DX8D.md`

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

---

## Completed Tasks

---

## Archive
