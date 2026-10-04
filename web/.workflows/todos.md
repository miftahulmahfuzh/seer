# Todos: web

**Package Path**: `web`
**Package Code**: WEB
**Last Updated**: 2026-10-04 22:02:40
**Total Active Tasks**: 4

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 4
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 4
- Completed: 5

---

## Active Tasks

### [P0] Critical

### [P1] High
- [ ] **P1-WEB-5767** Phase 2: Web data layer for the snapshot
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `web/lib/sera/` (relative imports only): `types.ts` (contract types), `lab.ts` (loads `../../data/lab.json`; `methodById`, `trialsOf`, `insightsOf`, `childrenOf`), pure `derive.ts` (per-trial gate checks from the engine's `failed`, misses, closest-to-eligible, best variant per method, funnel counts, progress over trial number, family aggregates, parent/child links, rebased SPY TR, drawdown series, calendar-year returns), `glossary.ts`, escape-first `markdown.ts`, test-only `fixture.ts` (reuses `web/lib/format.ts`), and a `*.test.ts` for each. Does not touch pages, components, engine. Exit: tsc + vitest green; every derivation unit-tested on a fixture snapshot; `lab.ts` type-checks against the real `web/data/lab.json`.
  - **Status**: open
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 2 of 7)
  - **Satisfies**: R3 — Show every experiment, as detailed as possible, kept current with no human step; R5 — Concise, non-technical explanations, with analysis and opinion on every method; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: P1-ENG-6QQA
  - **Plan**: `.workflows/plan/P1-WEB-5767.md`
- [ ] **P1-WEB-RL9Z** Phase 4: Overview page
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/app/sera/page.tsx` (calls `requireSera('/sera')`), `overview.module.css`, `overview.ts` (+test; pure shaping into phase 3's chart props). Sections: State of the search (latest `synthesis` insight, KPI tiles), Where every try landed (max DD vs CAGR-minus-SPY scatter with pass zone), Which hurdles are hardest (funnel bars), Are we getting closer? (progress lines), The luck bar (DSR vs N, 0.95 line), Families explored, Latest methods. Does not touch shell, chart kit, lib. Exit: tsc + vitest green; `next build` compiles the route; no hard-coded gate number.
  - **Status**: blocked
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 4 of 7)
  - **Satisfies**: R1 — Optimize the UI for desktop only (for now); R4 — Draw all the important graphs and diagrams; R5 — Concise, non-technical explanations, with analysis and opinion on every method; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: P1-WEB-5767, P1-WEB-EQ4I
  - **Plan**: `.workflows/plan/P1-WEB-RL9Z.md`
- [ ] **P1-WEB-9ANC** Phase 5: Methods list + method detail
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/app/sera/methods/page.tsx` + `methods.module.css`, `web/app/sera/methods/[id]/page.tsx` + `method.module.css`, `view.ts` (+test); both pages call `requireSera(<own path>)`. List: every method with status, family, source, best variant (CAGR vs SPY, max DD, PF, trades, DSR, n/6), verdict, icon-only `?show=all|lab|historical|alive` filter. Detail: header with parent/children, hypothesis, expected failure, verdict, variants table with per-condition marks, growth-of-1 vs rebased SPY TR, underwater drawdown, year-by-year bars, variants vs gate, rendered analysis markdown, related insights, full per-trial technical detail; `generateStaticParams` over all methods, `notFound()` for unknown ids. Does not touch shell, chart kit, lib. Exit: tsc + vitest green; `next build` compiles both routes; every method id resolves; unknown id renders the Sera not-found page.
  - **Status**: blocked
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 5 of 7)
  - **Satisfies**: R1 — Optimize the UI for desktop only (for now); R3 — Show every experiment, as detailed as possible, kept current with no human step; R4 — Draw all the important graphs and diagrams; R5 — Concise, non-technical explanations, with analysis and opinion on every method; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: P1-WEB-5767, P1-WEB-EQ4I
  - **Plan**: `.workflows/plan/P1-WEB-9ANC.md`
- [ ] **P1-WEB-08WD** Phase 6: Journal, Ideas, How it works
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/app/sera/journal/page.tsx`, `web/app/sera/ideas/page.tsx`, `web/app/sera/how/page.tsx` (one CSS module + tested `view.ts` each; each calls `requireSera(<own path>)`) and `web/components/sera/diagrams/` (`geometry.ts` +test, Pipeline, Windows). Journal: insights grouped by plain headings per kind (synthesis first), kind filter, newest first, method links. Ideas: `idea` backlog, blocked-on-data as a data wishlist, `ideasSeen` reading list. How it works: pipeline and time-windows diagrams, each hurdle with its threshold from `snapshot.gate`, honesty rules, data the lab has/lacks, glossary. Does not touch shell, chart kit, lib, other pages. Exit: tsc + vitest green; the three routes compile in `next build`.
  - **Status**: blocked
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 6 of 7)
  - **Satisfies**: R1 — Optimize the UI for desktop only (for now); R4 — Draw all the important graphs and diagrams; R5 — Concise, non-technical explanations, with analysis and opinion on every method; R6 — Insights from every exploration; food for thought on features and data sources; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: P1-WEB-5767, P1-WEB-EQ4I
  - **Plan**: `.workflows/plan/P1-WEB-08WD.md`

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

---

## Completed Tasks

- [x] **P1-WEB-EQ4I** Phase 3: Sera shell, access gate, chart kit
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/lib/sera/access.ts` (+test; `SERA_EMAIL`, `isSeraUser`), `web/lib/sera/gate.ts` (`requireSera(next)`), `web/lib/allow.ts` (+test; `safeNext`), `web/components/tooltip.ts` (wrapping tips, `\n` breaks), `web/app/sera/layout.tsx` + `sera.module.css` (gate per invariant 3 + desktop shell: Sera rail, icon-only tabs Overview/Methods/Journal/Ideas/How it works/back to Seer; ~1360 px column, single column below 1024 px), `web/components/sera/` (`SeraNav`, `PageHeader`, `Section`/`SectionGrid`, `Stat`, `Term`, `charts/` scale (+test), parts, LineChart, ScatterChart, BarChart, Legend (+render tests): hand-built SVG, Seer v2 colors), `web/components/Nav.tsx` + `web/app/(app)/layout.tsx` (desktop-rail Sera link when `isSeraUser`), `web/app/signin/page.tsx` (honour safe `next`), `web/app/sera/not-found.tsx`. Does not touch phase 2's lib files, any `/sera` page.tsx, `components/sera/diagrams/`. Exit: tsc + vitest green; `next build` compiles; layout gate per invariant 3; charts render from plain props (no snapshot import).
  - **Status**: done
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 3 of 7)
  - **Satisfies**: R1 — Optimize the UI for desktop only (for now); R2 — A separate system at seertrade.site/sera, visible only to mahfuzh74@gmail.com; R4 — Draw all the important graphs and diagrams; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: none
  - **Plan**: `.workflows/plan/P1-WEB-EQ4I.md`
  - **Completed**: 2026-10-04 22:02
  - **Method**: /do
  - **Files**: web/lib/sera/access.ts, web/lib/sera/access.test.ts, web/lib/sera/gate.ts, web/lib/allow.ts, web/lib/allow.test.ts, web/components/tooltip.ts, web/components/sera/ (charts/{scale.ts,scale.test.ts,charts.module.css,parts.tsx,LineChart.tsx,ScatterChart.tsx,BarChart.tsx,Legend.tsx,charts.test.tsx}, Term, Stat, Section, PageHeader, SeraNav), web/app/sera/ (layout.tsx, sera.module.css, not-found.tsx), web/components/Nav.tsx, web/components/Nav.module.css, web/app/(app)/layout.tsx, web/app/signin/page.tsx
  - **Drift**: No code drift: every whole-file block applied cleanly at 85bdc04; tooltip.ts showTip and Nav.module.css edits applied at the planned anchors.
  - **Decided**:
    - Task creation raced with phase 1's session in the same worktree → used the TaskID phase 1 already minted (P1-WEB-EQ4I) rather than minting a duplicate (tie-break: narrower blast radius).
    - Commit only phase 3's paths; phase 1's uncommitted engine/lab work in the shared worktree is left untouched (tie-break: never widen scope).
- [x] **P1-WEB-8YO3** Phase 6: Web: C everywhere, Vetoed tonight, D9 row, demo seed
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/lib/strategy.ts` (+test), `web/lib/metrics.ts` (+test), new `web/lib/vetoes.ts` (+test, incl. `noCheckLine`), `web/lib/data.ts` (`checksNews`, `vetoes()`), `web/app/(app)/leaderboard/view.ts` (+test) + `page.tsx` (butter/coral 4th look, `monthsBg`, `scoreOf(items, gate)`, 5 card columns), `web/app/(app)/positions/page.tsx` + `positions.module.css` ("Vetoed tonight"), `web/components/WhyToggle.tsx` (optional `label`/`missing`), `web/components/roster.ts` (comment) + `roster.test.ts`, `web/scripts/seed-demo.mjs` (C row with `applicable: false`, C portfolio on its own clock, six verdict rows, `news_vetoes` in the TRUNCATE), `web/package_readme.md` (Step 16). Does not touch: engine, Today (`app/(app)/page.tsx`). Exit: vitest (10 files, 83 tests) + `tsc --noEmit` green; seed applies onto 001–004 locally; screens render on demo data at 414 pt and desktop, light and dark; the no-rows state reads the neutral `noCheckLine`; Today still shows no buys.
  - **Status**: done
  - **Plan Set**: `STRATEGY_C_NEWS_VETO_PLAN.md` (phase 6 of 7)
  - **Satisfies**: R4 — Web: C in every roster view, "Vetoed tonight" on Positions, D9 checklist row, demo seed
  - **Depends on**: P1-ENG-4I4B
  - **Plan**: `.workflows/plan/P1-WEB-8YO3.md`
  - **Completed**: 2026-10-04 18:23
  - **Method**: /do
  - **Files**: web/lib/strategy.ts, web/lib/strategy.test.ts, web/lib/metrics.ts, web/lib/metrics.test.ts, web/lib/vetoes.ts, web/lib/vetoes.test.ts, web/lib/data.ts, web/app/(app)/leaderboard/view.ts, web/app/(app)/leaderboard/view.test.ts, web/app/(app)/leaderboard/page.tsx, web/app/(app)/positions/page.tsx, web/app/(app)/positions/positions.module.css, web/components/WhyToggle.tsx, web/components/roster.ts, web/components/roster.test.ts, web/scripts/seed-demo.mjs, web/package_readme.md
  - **Drift**: none — all three diffs applied cleanly; positions reference diff dry-run clean against HEAD
  - **Decided**: none needed — plan applied verbatim; Open Questions empty

- [x] **P1-WEB-DX8D** Phase 12: Web: Leaderboard, monthly table, checklist
  - **Difficulty**: HARD
  - **Type**: Update
  - **Context**: Owns `app/(app)/leaderboard/page.tsx` + `leaderboard.module.css` + `view.ts`/`view.test.ts` (leaderboard-only helpers: looks, best research, score line, month rows over phase 10's `MonthlyTable`): roster-driven colors/cards (no hardcoded A/B/C), SPY crown, checklist per research strategy via phase 11's `StrategySwitch`/`selectStrategy`/`strategyIcon` with `checklist(m, spy, gate)` and an honest score line, "Month by month" sheet from `monthly(id, run.sessionDate)` (Return, SPY, Trades, Worst drop; since-start row; partial-month marker). Does not touch: other screens, `web/lib/*`. Exit: as phase 11, on the Leaderboard.
  - **Status**: done
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 12 of 13)
  - **Satisfies**: R4 — Web: Today SPY-champion state, paper labels, book positions/trades, monthly table, leaderboard incl. book strategies, checklist honesty, no 4-slot assumption
  - **Depends on**: P1-WEB-0AHX
  - **Plan**: `.workflows/plan/P1-WEB-DX8D.md`
  - **Completed**: 2026-10-04 10:07
  - **Method**: /do
  - **Files**: web/app/(app)/leaderboard/view.ts, web/app/(app)/leaderboard/view.test.ts, web/app/(app)/leaderboard/page.tsx, web/app/(app)/leaderboard/leaderboard.module.css
  - **Drift**: none — phase 10/11 exports matched Requires A1–A6 exactly; plan code blocks applied verbatim
  - **Decided**: Manual render check (plan Verification 'Manual check' 1–7) skipped → web reads via @neondatabase/serverless neon() HTTP driver, so a local render needs the live Neon DB and `db:seed-demo` would write demo rows into it; not seeding production. Exit criteria tsc/vitest verified; view.ts scoreOf tests enforce 'never Ready for real money unless all six pass' (tie-break: reversible option / narrower blast radius)

- [x] **P1-WEB-0AHX** Phase 11: Web: Today, Positions, History
  - **Difficulty**: HARD
  - **Type**: Update
  - **Context**: Owns `app/(app)/page.tsx` + `today.module.css` (SPY-champion no-buys state; stale/failed still first), `positions/*` (strategy switcher, paper chip, bracket/book/benchmark cards by `Holding.kind`, `pendingOrders` sheet, paper-step warning), `history/*` (roster-driven filters, book exit reasons signal/forced, paper chip, `Trade.key`), new shared `components/StrategySwitch.tsx` (icon-only links, `?s=`, `href`/`label` props), `components/PaperChip.tsx`, and `components/roster.ts` (only `strategyIcon`, `selectStrategy`, `sharesLabel`: short labels and the paper flag stay phase 10's). The three pages are replaced whole, starting from phase 10 Step 10's versions. Does not touch: leaderboard, `web/lib/*` (consumes phase 10's API; a missing field is added in phase 10's plan, not here). Exit: vitest + `tsc --noEmit` green; screens render on demo data at 414 pt and desktop, light and dark.
  - **Status**: done
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 11 of 13)
  - **Satisfies**: R4 — Web: Today SPY-champion state, paper labels, book positions/trades, monthly table, leaderboard incl. book strategies, checklist honesty, no 4-slot assumption
  - **Depends on**: P1-WEB-Y9MV
  - **Plan**: `.workflows/plan/P1-WEB-0AHX.md`
  - **Completed**: 2026-10-04 09:58
  - **Method**: /do
  - **Files**: web/components/roster.ts, web/components/roster.test.ts, web/components/StrategySwitch.tsx, web/components/StrategySwitch.module.css, web/components/PaperChip.tsx, web/components/PaperChip.module.css, web/app/(app)/page.tsx, web/app/(app)/today.module.css, web/app/(app)/positions/page.tsx, web/app/(app)/positions/positions.module.css, web/app/(app)/history/page.tsx, web/app/(app)/history/history.module.css

- [x] **P1-WEB-Y9MV** Phase 10: Web data layer, monthly math, demo seed
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/lib/strategy.ts` (`Engine`, `Gate`, `engineOf`, `parseGate`, `shortLabel`); `web/lib/data.ts` (`Strategy` with `engine/rulesId/paperStart/gate/isPaper/short`; `Holding` with `kind/key/orderId/maxDays` for both engines and the benchmark; `pendingOrders()` → `Pending`/`PendingOrder`; `Trade.key/strategyShort/ExitReason`; leaderboard pnls per engine; `RunStatus.latestStatus/paperStatus/paperError/paperFinishedAt`; `monthly(id, sessionDate)` → `MonthlyTable`); `web/lib/monthly.ts` (new, pure) + `monthly.test.ts` hand-checked fixture; `web/lib/metrics.ts` `checklist(m, spy, gate)` 6th item "Backtest gate passed"; `web/lib/slots.ts` (`slotCount`, `cardBg`; no 4-slot assumption for book); `web/scripts/seed-demo.mjs` in the new shape (gate notes = `roster.py` texts); Step 10 minimal compile fixes to `page.tsx`, `positions/page.tsx`, `leaderboard/page.tsx` (these land before phases 11/12). Does not touch: page components beyond the Step 10 fixes (phases 11, 12), engine. Exit: vitest green incl. monthly fixture (month boundaries, partial first/current month, no-trade months, SPY same months); `tsc --noEmit` clean.
  - **Status**: done
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 10 of 13)
  - **Satisfies**: R4 — Web: Today SPY-champion state, paper labels, book positions/trades, monthly table, leaderboard incl. book strategies, checklist honesty, no 4-slot assumption; R2 — Migration `003` (D6) + roster `strategies` rows with `paper_start` and frozen spec (D4); demo seed in the new shape
  - **Depends on**: P1-ENG-N6UC
  - **Plan**: `.workflows/plan/P1-WEB-Y9MV.md`
  - **Completed**: 2026-10-04 09:49
  - **Method**: /do
  - **Files**: web/lib/strategy.ts, web/lib/strategy.test.ts, web/lib/metrics.ts, web/lib/metrics.test.ts, web/lib/monthly.ts, web/lib/monthly.test.ts, web/lib/slots.ts, web/lib/slots.test.ts, web/lib/data.ts, web/scripts/seed-demo.mjs, web/app/(app)/page.tsx, web/app/(app)/positions/page.tsx, web/app/(app)/leaderboard/page.tsx

---

## Archive
