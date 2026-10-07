# Todos: web

**Package Path**: `web`
**Package Code**: WEB
**Last Updated**: 2026-10-07
**Total Active Tasks**: 1

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 1
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 0
- Completed: 16

---

## Active Tasks

### [P0] Critical

### [P1] High
- [ ] **P1-WEB-Z5LP** Phase 5: The rail badge and the package readme
  - **Difficulty**: EASY
  - **Type**: Feature
  - **Context**: Owns `web/app/sera/layout.tsx` (calls `unseenCount(lab.insights.map(i => i.id))` and renders no badge on `null` or `0`, never `seenInsightIds`), `web/components/sera/SeraNav.tsx` and `SeraNav.module.css` (the Journal tab's optional rail badge, correct in both layouts), and `web/package_readme.md` (the exception to the "Sera never reads Neon" sentence, plus every file this set added in the Layout tree). Exit: the rail's number equals the `all` badge on `/sera/journal`, including when `journal_seen` holds an id outside the snapshot; a failed read shows no badge rather than the full inventory; the rail renders in both the >=1024px rail and the below-1024px top bar; `npx tsc --noEmit && npm test` clean.
  - **Status**: open
  - **Plan Set**: `JOURNAL_UNSEEN_BADGES_PLAN.md` (phase 5 of 5)
  - **Satisfies**: R3 — The notification number on each of the seven tab icons is the true count of unseen items for that tab, so a new number on a tab is a real signal worth getting excited about
  - **Depends on**: P1-WEB-K3QM, P1-WEB-SSGU, P1-WEB-M2WF, P1-WEB-Q8DV
  - **Plan**: `.workflows/plan/P1-WEB-Z5LP.md`
  - **Note (from P1-WEB-M2WF readme check, 2026-10-07)**: readme-updater found four `web/package_readme.md` claims this set invalidates that are NOT in this task's Owns list — check them too: `:12` "plus one write (`action_dismissals`)" and `:418` "the engine owns writes to every table except `action_dismissals`" both omit `journal_seen` (strained by phase 1's `markInsightsSeen`, live once phase 4 lands); `:334` `journalGroups(insights, filter)` gained phase 2's trailing seen-set parameter; `:374` "`/sera/journal` ... newest first" becomes imprecise once phase 4 marks entries seen. `:422` ("the only write is an idempotent `INSERT ... ON CONFLICT DO NOTHING`") happens to stay true and needs no edit.
  - **Note (from P1-WEB-Q8DV readme check, 2026-10-07)**: a second readme-updater pass found five MORE `web/package_readme.md` claims phase 4 invalidates, none overlapping the M2WF note above: `:438` the `npm test` enumeration lists only `view` helpers and now misses `app/sera/journal/seen-client` (32 new cases); `:343-348` the Data Flow block has no arrow for the Journal's write path (browser island -> `sendBeacon`/`fetch` POST `/api/sera/journal/seen` -> `markInsightsSeen` -> `journal_seen`), which is a route handler rather than a server action and hangs off `/sera`, not `app/(app)`; `:21` "each page keeps its logic in a pure, tested `view.ts`" — Journal now has two pure modules (`view.ts` + `seen-client.ts`) and `/sera/journal` is the first Sera page mounting a `'use client'` island, so `SeraNav.tsx` is no longer the section's only client component; `:325-339` Key modules has no bullet for `seen-client.ts` or `JournalSeen.tsx`, though every other `app/sera/*/view.ts` has one; `:426-429` Error Handling says failures propagate, but the seen write is the app's first deliberately silent path (a failed POST is swallowed and the ids requeue while the badge stays optimistically counted down). Borderline: `:420-422` "the only write" is now singular-but-two, and the client adds a `MAX_BATCH = 50` queue that a `pagehide` beacon can race. Candidate gotchas: the two caps (`MAX_BATCH = 50` client flush trigger vs `MAX_SEEN_BATCH = 500` server limit) are not the same thing; phase 1's route accepts `text/plain` ONLY because `sendBeacon` sends a Blob, so narrowing it to JSON would silently break unload flushes; the arrow-click listener is capture-phase on `document` so it fires before `Link` navigates away; and `view.ts` must stay server-free because `JournalSeen.tsx` imports `badgeTip` from it.

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

---

## Completed Tasks

- [x] **P1-WEB-K3QM** Phase 1: Seen-state storage, server read/write, and the POST endpoint
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `db/migrations/012_journal_seen.sql` (`journal_seen`: `insight_id` PK, `seen_at`, a `via` column constrained to 'view' or 'click', no foreign key since insights live in the engine's SQLite lab store), new server-only `web/lib/sera/seen.ts` (`seenInsightIds`, `unseenCount` returning `null` on a failed read, `markInsightsSeen`, `normalizeSeenIds`/`parseSeenVia`, `MAX_SEEN_BATCH = 500`) and new `web/app/api/sera/journal/seen/route.ts` (Sera-gated POST that also accepts a `text/plain` sendBeacon body). Exit: the migration applies cleanly and idempotently on top of `011_rmw.sql`; the reads never throw against an unreachable database; `markInsightsSeen` is idempotent; the route answers 204 / 404 / 400; nothing in the app calls it yet, `journal_seen` stays out of `DEMO_TABLES`, and the tree builds.
  - **Status**: done
  - **Plan Set**: `JOURNAL_UNSEEN_BADGES_PLAN.md` (phase 1 of 5)
  - **Satisfies**: R2 — A working definition and mechanism for "seen": a click on an item's redirect-arrow marks it seen, and items with no arrow are marked seen some other way
  - **Plan**: `.workflows/plan/P1-WEB-K3QM.md`
  - **Completed**: 2026-10-07 11:27
  - **Method**: /do
  - **Files**: db/migrations/012_journal_seen.sql, web/lib/sera/seen.ts, web/app/api/sera/journal/seen/route.ts, web/.workflows/todos.md, web/.workflows/plan/P1-WEB-K3QM.md, web/.workflows/plan/P1-WEB-M2WF.md, web/.workflows/plan/P1-WEB-Q8DV.md, web/.workflows/plan/P1-WEB-Z5LP.md
  - **Drift**:
    - None. The tree matched everything the plan quoted: db/migrations held 001-011 (011_rmw.sql highest), web/lib/sera had no seen.ts, web/app/api held only auth/[...nextauth]/route.ts, and every imported symbol existed (sql from @/lib/db, isAllowed from @/lib/allow, isSeraUser from @/lib/sera/access, auth from @/auth). The route's gate mirrors lib/sera/gate.ts's requireSera predicate pair exactly.
  - **Decided**:
    - Which package tracker holds the five tasks: phase 1's Package column names db/migrations, web/lib/sera and web/app/api, and only `web` has a .workflows/ tracker -> all five tasks in web/.workflows/todos.md (code WEB). Rung 6, surrounding code convention.
    - engine/pyproject.toml's addopts is `-ra -n auto` and the main checkout's venv has no pytest-xdist, so the plan's migration-test command failed with `unrecognized arguments: -n` -> overrode with `-o addopts=-ra` rather than installing a package (the plan forbids installing). Rung 6, and the plan's own environment note.
    - The migration tests skip without PG_TEST_URL, which would not establish the phase's apply-cleanly/idempotent exit criterion -> found the already-running seer-pg container and ran them for real against Postgres. Rung 2, phase exit criteria; a skipped check is not a passed one.

- [x] **P1-WEB-SSGU** Phase 2: Unseen-aware pure view layer: counts and the unseen/seen partition
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `web/app/sera/journal/view.ts` (pure shaping: `unseenCounts`, `badgeTip`, `SEEN_COPY`, `journalGroups` with an optional trailing `ReadonlySet<number>` seen-set; `JournalGroup` gains `items`/`unseen`/`seen`/`unseenCount` and keeps `entries`) and `web/app/sera/journal/view.test.ts`. Exit: `npx vitest run app/sera/journal` passes with no DB and no DOM; those four symbols are exported with the signatures phase 3 consumes; `npx tsc --noEmit` is clean with `page.tsx` byte-identical to its pre-phase state; `view.ts` imports nothing beyond `lib/sera/glossary` and `lib/sera/types`.
  - **Status**: done
  - **Plan Set**: `JOURNAL_UNSEEN_BADGES_PLAN.md` (phase 2 of 5)
  - **Satisfies**: R1 — Within every tab's content, unseen items sit at the top sorted newest-to-oldest, and seen items are pushed down below them; R3 — The notification number on each of the seven tab icons is the true count of unseen items for that tab, so a new number on a tab is a real signal worth getting excited about
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-WEB-SSGU.md`
  - **Completed**: 2026-10-07 11:27
  - **Method**: /do
  - **Files**: web/app/sera/journal/view.ts, web/app/sera/journal/view.test.ts, web/.workflows/todos.md, web/.workflows/plan/P1-WEB-SSGU.md
  - **Drift**: No code drift: `view.ts` and `page.tsx` were byte-identical to what phase-2.md quotes. One plan-prose miscount — phase-2.md's Impact and exit criteria say the suite goes to 29 cases, but its own verbatim code block yields 30. The code block was applied unchanged (ladder rung 3 outranks surrounding prose); the real number is 30.
  - **Decided**: Step 3 scope in a concurrent swarm wave: mint tasks for all five phases, or only phase 2's? → only phase 2's (rung: tie-break "narrower blast radius" — ladder rungs 1-5 are silent on bookkeeping, and phase 1 was running Step 3 against the same web/.workflows/todos.md, so two sessions each writing five entries would duplicate every TaskID in the set).

- [x] **P1-WEB-M2WF** Phase 3: The page renders unseen counts, the boundary, and per-card state
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `web/app/sera/journal/page.tsx` (force-dynamic, `await seenInsightIds()` into `seenIds`, the seven options carrying unseen counts plus `heading`/`total` fed to `badgeTip`, each section rendering `g.unseen` then the boundary then `g.seen`, and `InsightCard` carrying `data-insight-id`/`data-unseen` with a `data-seen-click` redirect arrow) and `journal.module.css` (the unseen marker, the boundary divider, and the `.card[data-seen-now] .new` fade phase 4 triggers). Exit: seen cards sit below the boundary inside their section and the badges drop by exactly that many; an all-seen or all-unseen section renders no stray boundary; the seven tabs keep their order, icons, `aria-current` and styling with `badgeTip`'s tooltips; `npx tsc --noEmit && npm test` clean.
  - **Status**: done
  - **Plan Set**: `JOURNAL_UNSEEN_BADGES_PLAN.md` (phase 3 of 5)
  - **Satisfies**: R1 — Within every tab's content, unseen items sit at the top sorted newest-to-oldest, and seen items are pushed down below them; R3 — The notification number on each of the seven tab icons is the true count of unseen items for that tab, so a new number on a tab is a real signal worth getting excited about
  - **Depends on**: P1-WEB-K3QM, P1-WEB-SSGU
  - **Plan**: `.workflows/plan/P1-WEB-M2WF.md`
  - **Completed**: 2026-10-07 11:39
  - **Method**: /do
  - **Files**: web/app/sera/journal/page.tsx, web/app/sera/journal/journal.module.css, web/.workflows/todos.md, JOURNAL_UNSEEN_BADGES_PLAN.md
  - **Drift**:
    - None. Phase 1's lib/sera/seen.ts and phase 2's view.ts both matched the plan's reconciled contract tables exactly (SEEN_COPY, badgeTip, unseenCounts, three-parameter journalGroups with unseen/seen/items/unseenCount, seenInsightIds). Step 7's shape check passed with no adaptation.
  - **Decided**:
    - `npx next build` (Turbopack) panics in this worktree with 'Symlink [project]/node_modules is invalid, it points out of the filesystem root' -> verified the build with `npx next build --webpack` instead, which passes and confirms /sera/journal renders as dynamic. Rung 2 (phase exit criteria are `npx tsc --noEmit && npm test`, both clean). Measured, not assumed: the same Turbopack panic reproduces on the base tree with both changed files reverted, so it tests the plan's mandated node_modules symlink rather than this phase's code. The plan's Environment note forbids npm ci/npm install, so the symlink stays.

- [x] **P1-WEB-Q8DV** Phase 4: The client island: dwell, click, batch, flush, live countdown
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns new pure `web/app/sera/journal/seen-client.ts` (the policy constants including `MAX_BATCH = 50`, which must stay at or below phase 1's `MAX_SEEN_BATCH = 500`, the dedupe queue, and the on-screen decision) with `seen-client.test.ts`, new `'use client'` `JournalSeen.tsx` (one IntersectionObserver, dwell timers cancelled when a card leaves or the tab goes hidden, arrow clicks marked `via: 'click'`, debounced and capped flushes plus `sendBeacon` on pagehide, and a live badge countdown rewritten through phase 2's `badgeTip`), and four surgical edits to `page.tsx` to mount the island. Exit: only entries actually on screen get marked and a background tab marks nothing; cards never move while the page is open and a retired marker fades without shifting its title; tooltips track their badges; `npx tsc --noEmit && npm test` clean.
  - **Status**: done
  - **Plan Set**: `JOURNAL_UNSEEN_BADGES_PLAN.md` (phase 4 of 5)
  - **Satisfies**: R2 — A working definition and mechanism for "seen": a click on an item's redirect-arrow marks it seen, and items with no arrow are marked seen some other way; R3 — The notification number on each of the seven tab icons is the true count of unseen items for that tab, so a new number on a tab is a real signal worth getting excited about
  - **Depends on**: P1-WEB-K3QM, P1-WEB-SSGU, P1-WEB-M2WF
  - **Plan**: `.workflows/plan/P1-WEB-Q8DV.md`
  - **Completed**: 2026-10-07 12:05
  - **Method**: /do
  - **Files**: web/app/sera/journal/seen-client.ts, web/app/sera/journal/seen-client.test.ts, web/app/sera/journal/JournalSeen.tsx, web/app/sera/journal/page.tsx, web/.workflows/todos.md, JOURNAL_UNSEEN_BADGES_PLAN.md
  - **Decided**:
    - The plan's `seen-client.test.ts` `unseen()` helper does not compile (TS2352: `Object.fromEntries` widens to a string index signature, which TS will not assert onto `Readonly<Record<InsightKind, readonly number[]>>`) -> built the record with an explicit loop over `INSIGHT_KINDS` plus one `{} as Record<...>` assertion. Rung 1: invariant 1 "the tree builds" outranks a code block that does not; the idiom matches `badgeCounts`' own `const out = {} as Record<BadgeKey, number>` in the same file. No assertion or intent in the test changed.

- [x] **P1-WEB-10T8** Phase 3: Positions page: monthly pick / weekly size copy and buy/add/trim cell
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns: new `web/lib/cadence.ts` (`SPLIT_CADENCE_RULES` = `monthly-rank-weekly-resize`, `monthly-rank-weekly-resize-tbill`, `monthly-rank-weekly-resize-frac`; `picksMonthlySizesWeekly`, `RESIZE_BAND = 0.01`, `sizeChange`, `heldUsd`, `orderSizeChange`, `sizeLabel`, `sizeTip`) and `web/lib/cadence.test.ts`; in `web/app/(app)/positions/page.tsx` the three monthly sentences (158, 166, 374) branching on it, and for such a strategy a full-width per-order `SizeCell` comparing the target dollars (weight × equity) with what is held now: "Buy about $X" (symbol not held — the band does not apply), "Add about $X", "Trim about $X", or "No change" when the gap is under 1% of equity (the engine's `RESIZE_BAND`), each with a plain-words tooltip; `.cellWide` in `positions.module.css`. Exit criteria: non-split strategies render exactly as before; for a split-cadence strategy the sentences speak of a monthly pick and a weekly size check and each book order shows Buy / Add / Trim about $X or No change; vitest and tsc green.
  - **Status**: done
  - **Plan Set**: `PAPER_SPLIT_CADENCE_PLAN.md` (phase 3 of 3)
  - **Satisfies**: R6 — Positions page: plain words "picks monthly, adjusts weekly"; on a resize week shows what to trim or top up
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-WEB-10T8.md`
  - **Completed**: 2026-10-07 01:49
  - **Method**: /do
  - **Files**: web/lib/cadence.ts, web/lib/cadence.test.ts, web/app/(app)/positions/page.tsx, web/app/(app)/positions/positions.module.css, web/.workflows/todos.md, web/.workflows/plan/P1-WEB-10T8.md
  - **Decided**:
    - Step 3 creates every phase's task -> only phase 3's (web) created; the phase 1 session runs concurrently in the same worktree and owns engine bookkeeping (tie-break: narrower blast radius)
    - Invariant 1 engine pytest/ruff at end of phase -> not run by this phase: phase 1's in-progress engine edits share the worktree, and this phase changes no engine file (rung 6 / narrower blast radius)

- [x] **P1-WEB-YJSP** Phase 5: Show reasons on the site
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `web/lib/why.ts` + `why.test.ts`, `web/lib/data.ts` (evidence on PendingOrder, Pick, PreviewPick via `to_jsonb(...)->'evidence'`), Positions `OrderRow`/`WouldPick`, Today `PickCard`, `WhyToggle.tsx` + CSS (facts list), `web/scripts/seed-demo.mjs` (demo evidence in phase 1's exact wording), `web/package_readme.md`; no engine edits. Exit: K5 behaviour (LLM text, else facts list, "unavailable" only when both missing; "Would pick now" rows get a "Why it's on the list" toggle; C's news-check line stays); vitest covers the fallback helper; tsc clean; screens checked at 414 pt light and dark, icon-only buttons, no ids/codes.
  - **Status**: done
  - **Plan Set**: `WHY_THIS_PICK_PIPELINE_PLAN.md` (phase 5 of 5)
  - **Satisfies**: R5, R6, R8 — C keeps its news-check reason as a second line; "Would pick now" rows get reasons too, if cheap; Plain words for a non-trader; no ids/codes on the site
  - **Depends on**: P1-ENG-H5LC
  - **Plan**: `.workflows/plan/P1-WEB-YJSP.md`
  - **Completed**: 2026-10-06 22:34
  - **Method**: /do
  - **Files**: web/lib/why.ts, web/lib/why.test.ts, web/lib/data.ts, web/components/WhyToggle.tsx, web/components/WhyToggle.module.css, web/app/(app)/positions/page.tsx, web/app/(app)/page.tsx, web/scripts/seed-demo.mjs, web/package_readme.md
  - **Drift**:
    - Trivial only: picks() doc comment said 'Unchanged; returns [] for SPY' — replaced per plan.
    - Demo strategy subtitle 'Top 20 by 12-1 momentum, monthly' (seed-demo.mjs:75) still contains the 12-1 code; out of the plan's step list, left as is (demo only).
    - Manual check: production had no 'would pick now' rows (F4/F1/FND started paper 2026-10-06), so that toggle was not seen on screen; it reuses the same WhyToggle/.facts path verified on C's rows.
  - **Decided**:
    - Pass B temporary edit restored by file backup copy instead of staging web first → backup/cp (narrower blast radius: index shared with a concurrent phase-3 session)

- [x] **P1-WEB-5767** Phase 2: Web data layer for the snapshot
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns new `web/lib/sera/` (relative imports only): `types.ts` (contract types), `lab.ts` (loads `../../data/lab.json`; `methodById`, `trialsOf`, `insightsOf`, `childrenOf`), pure `derive.ts` (per-trial gate checks from the engine's `failed`, misses, closest-to-eligible, best variant per method, funnel counts, progress over trial number, family aggregates, parent/child links, rebased SPY TR, drawdown series, calendar-year returns), `glossary.ts`, escape-first `markdown.ts`, test-only `fixture.ts` (reuses `web/lib/format.ts`), and a `*.test.ts` for each. Does not touch pages, components, engine. Exit: tsc + vitest green; every derivation unit-tested on a fixture snapshot; `lab.ts` type-checks against the real `web/data/lab.json`.
  - **Status**: done
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 2 of 7)
  - **Satisfies**: R3 — Show every experiment, as detailed as possible, kept current with no human step; R5 — Concise, non-technical explanations, with analysis and opinion on every method; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: P1-ENG-6QQA
  - **Plan**: `.workflows/plan/P1-WEB-5767.md`
  - **Completed**: 2026-10-04 22:10
  - **Method**: /do
  - **Files**: web/lib/sera/types.ts, web/lib/sera/lab.ts, web/lib/sera/derive.ts, web/lib/sera/glossary.ts, web/lib/sera/markdown.ts, web/lib/sera/fixture.ts, web/lib/sera/derive.test.ts, web/lib/sera/glossary.test.ts, web/lib/sera/markdown.test.ts, web/lib/sera/lab.test.ts
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
- [x] **P1-WEB-RL9Z** Phase 4: Overview page
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/app/sera/page.tsx` (calls `requireSera('/sera')`), `overview.module.css`, `overview.ts` (+test; pure shaping into phase 3's chart props). Sections: State of the search (latest `synthesis` insight, KPI tiles), Where every try landed (max DD vs CAGR-minus-SPY scatter with pass zone), Which hurdles are hardest (funnel bars), Are we getting closer? (progress lines), The luck bar (DSR vs N, 0.95 line), Families explored, Latest methods. Does not touch shell, chart kit, lib. Exit: tsc + vitest green; `next build` compiles the route; no hard-coded gate number.
  - **Status**: done
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 4 of 7)
  - **Satisfies**: R1 — Optimize the UI for desktop only (for now); R4 — Draw all the important graphs and diagrams; R5 — Concise, non-technical explanations, with analysis and opinion on every method; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: P1-WEB-5767, P1-WEB-EQ4I
  - **Plan**: `.workflows/plan/P1-WEB-RL9Z.md`
  - **Completed**: 2026-10-04 22:12
  - **Method**: /do
  - **Files**: web/app/sera/overview.ts, web/app/sera/overview.test.ts, web/app/sera/page.tsx, web/app/sera/overview.module.css
- [x] **P1-WEB-9ANC** Phase 5: Methods list + method detail
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/app/sera/methods/page.tsx` + `methods.module.css`, `web/app/sera/methods/[id]/page.tsx` + `method.module.css`, `view.ts` (+test); both pages call `requireSera(<own path>)`. List: every method with status, family, source, best variant (CAGR vs SPY, max DD, PF, trades, DSR, n/6), verdict, icon-only `?show=all|lab|historical|alive` filter. Detail: header with parent/children, hypothesis, expected failure, verdict, variants table with per-condition marks, growth-of-1 vs rebased SPY TR, underwater drawdown, year-by-year bars, variants vs gate, rendered analysis markdown, related insights, full per-trial technical detail; `generateStaticParams` over all methods, `notFound()` for unknown ids. Does not touch shell, chart kit, lib. Exit: tsc + vitest green; `next build` compiles both routes; every method id resolves; unknown id renders the Sera not-found page.
  - **Status**: done
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 5 of 7)
  - **Satisfies**: R1 — Optimize the UI for desktop only (for now); R3 — Show every experiment, as detailed as possible, kept current with no human step; R4 — Draw all the important graphs and diagrams; R5 — Concise, non-technical explanations, with analysis and opinion on every method; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: P1-WEB-5767, P1-WEB-EQ4I
  - **Plan**: `.workflows/plan/P1-WEB-9ANC.md`
  - **Completed**: 2026-10-04 22:13
  - **Method**: /do
  - **Files**: web/app/sera/methods/view.ts, web/app/sera/methods/view.test.ts, web/app/sera/methods/page.tsx, web/app/sera/methods/methods.module.css, web/app/sera/methods/[id]/page.tsx, web/app/sera/methods/[id]/method.module.css
- [x] **P1-WEB-08WD** Phase 6: Journal, Ideas, How it works
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/app/sera/journal/page.tsx`, `web/app/sera/ideas/page.tsx`, `web/app/sera/how/page.tsx` (one CSS module + tested `view.ts` each; each calls `requireSera(<own path>)`) and `web/components/sera/diagrams/` (`geometry.ts` +test, Pipeline, Windows). Journal: insights grouped by plain headings per kind (synthesis first), kind filter, newest first, method links. Ideas: `idea` backlog, blocked-on-data as a data wishlist, `ideasSeen` reading list. How it works: pipeline and time-windows diagrams, each hurdle with its threshold from `snapshot.gate`, honesty rules, data the lab has/lacks, glossary. Does not touch shell, chart kit, lib, other pages. Exit: tsc + vitest green; the three routes compile in `next build`.
  - **Status**: done
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 6 of 7)
  - **Satisfies**: R1 — Optimize the UI for desktop only (for now); R4 — Draw all the important graphs and diagrams; R5 — Concise, non-technical explanations, with analysis and opinion on every method; R6 — Insights from every exploration; food for thought on features and data sources; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: P1-WEB-5767, P1-WEB-EQ4I
  - **Plan**: `.workflows/plan/P1-WEB-08WD.md`
  - **Completed**: 2026-10-04 22:30
  - **Method**: /do
  - **Files**: web/components/sera/diagrams/geometry.ts, web/components/sera/diagrams/geometry.test.ts, web/components/sera/diagrams/diagrams.module.css, web/components/sera/diagrams/Pipeline.tsx, web/components/sera/diagrams/Windows.tsx, web/app/sera/journal/view.ts, web/app/sera/journal/view.test.ts, web/app/sera/journal/journal.module.css, web/app/sera/journal/page.tsx, web/app/sera/ideas/view.ts, web/app/sera/ideas/view.test.ts, web/app/sera/ideas/ideas.module.css, web/app/sera/ideas/page.tsx, web/app/sera/how/view.ts, web/app/sera/how/view.test.ts, web/app/sera/how/how.module.css, web/app/sera/how/page.tsx

- [x] **P1-WEB-C6PK** Phase 4: The leaderboard re-sorts honestly, and shows retired horsemen
  - **Difficulty**: NORMAL
  - **Type**: Update
  - **Context**: Owns `web/lib/data.ts` (project `status`, `paper_end`), `web/app/(app)/leaderboard/{view.ts,page.tsx,leaderboard.module.css}` and `web/app/(app)/leaderboard/view.test.ts`. Does not touch engine code, migrations or `web/lib/sera/*`. Exit: `bestResearch`'s raw-`totalReturn` max is **deleted** and replaced by a faithful TypeScript port of phase 3's `compare` (D10) — same `MIN_COMMON_SESSIONS = 63`, same `MIN_RANKED = 2`, same selection rule, same rank key, same statuses — and the window is **shown in the UI**, not just computed, with no Calmar and no configurable rank key, since a knob is a drift vector between two implementations that must agree; with fewer than 63 shared sessions the page says `No common window yet` and `N of 63 sessions shared by every strategy` and shows **no** "best" figure, which is D8 working rather than a regression; a retired strategy renders with its history intact and a visible retired marker, excluded from the window and from "best" without being hidden (D9); `looks` handles a roster longer than `CARD_BGS`/`LINES` (4) without two strategies colliding on one look and without assuming exactly four research strategies; `web/lib/data.ts` projects `status`, `paper_end` and `COALESCE(params->'spec'->>'object', object_name)`, so a just-promoted row is not missing a display fact for its first night; and `npm test` is **+18** on what the phase inherited, with `npm run build` and `npx tsc --noEmit` passing.
  - **Status**: done
  - **Plan Set**: `ROSTER_PROMOTION_PIPELINE_PLAN.md` (phase 4 of 6)
  - **Satisfies**: R3 — A robust pipeline to compare and "re-sort" the horsemen, so a better method can be recognised as better
  - **Depends on**: P1-ENG-7KQ2, P1-ENG-7V3C
  - **Plan**: `.workflows/plan/P1-WEB-C6PK.md`
  - **Completed**: 2026-10-05 18:22
  - **Method**: /do
  - **Files**: web/lib/data.ts, web/app/(app)/leaderboard/view.ts, web/app/(app)/leaderboard/page.tsx, web/app/(app)/leaderboard/leaderboard.module.css, web/app/(app)/leaderboard/view.test.ts
  - **Decided**:
    - Verify the TS port against the Python oracle without breaking the pinned +18/5-file contract -> ran phase 3's `compare.py` on the exact test fixtures in a scratch file, then folded the oracle-derived figures (totalReturn, cagr, maxDrawdown, sharpe, inception) into the EXISTING "ranks over the sessions every compared strategy shares" test instead of keeping a sixth test file (rung 2, the phase's exit criteria, which pin `npm test` at +18 and the Interface Contract's "No new file is created").
    - The plan's manual browser check (`npm run dev`, `/leaderboard` at 414pt and desktop) -> NOT RUN: this worktree carries no web `.env`, so the app has no database credentials and `npm run dev` cannot reach Neon regardless of this change. The window row is unconditional JSX fed by `windowLine`, whose both branches ("Ranked over ..." and "No common window yet") are pinned by tests (rung 3, the phase plan's code blocks). Flagged for a human pass on a credentialed environment.

---

## Archive
