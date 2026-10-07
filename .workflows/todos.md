# Todos: root (repo-wide)

**Package Path**: `.`
**Package Code**: ROOT
**Last Updated**: 2026-10-07 23:21
**Total Active Tasks**: 6

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 6
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 3
- Completed: 9

---

## Active Tasks

### [P0] Critical

### [P1] High

- [ ] **P1-ROOT-UNS5** Phase 2: Sean section, Sean buttons (rail + phone header), Trades upload
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/components/Nav.tsx` + `Nav.module.css` (Sean `icon-btn` class `.sean` directly above Sera, Lucide `Wallet`, tip/aria "Sean, your real trades", both in a `.foot` wrapper taking over `margin-top:auto`; `.sera` deleted); `web/components/AppHeader.tsx` + `.module.css` (now `async`; owner-only, mobile-only `Wallet` icon button beside Sign out, class `.sean`; call sites unchanged); `web/app/(app)/layout.tsx` (`owner` = Sera's check, `showSean`); `web/lib/sean/gate.ts` (`requireSean`, `isSeanCaller`); `web/lib/sean/data.ts` (server-only, owned by this phase alone: `orders()`, `ledgerOrders()`/`LedgerRow` for Phases 3 and 5, `ownerSymbols()`, `orderById()`, `orderIdBySha()`, `saveOrder()`, `removeOrder()`); `web/lib/sean/dispatch.ts` (`dispatchSeanMarks()`, best effort); `web/components/sean/SeanNav.tsx` + css; `web/app/sean/{layout,not-found,sean.module.css,page (placeholder),plan/page (placeholder)}`; `web/app/api/sean/orders/route.ts` (contract C); `web/app/sean/trades/{page, Uploader, DeleteOrder, actions, view(+test), upload(+test), trades.module.css}`; Vercel env `LLM_API_KEY`/`LLM_VISION_BASE_URL`/`LLM_VISION_MODEL` if missing. Uploader: browser unzips with `readZip`, re-encodes only non-JPEGs or JPEGs over ~1 MB (long side ≤ 2400 px, short side never under 560 px), hashes, posts three at a time; reader/network failures kept and re-sent by a retry icon button. Does not touch Phase 1's `web/lib/sean` modules, `reminders.ts`, `overviewData.ts`, `planData.ts`; engine. Exit: `tsc`, vitest, `next build` green; owner sees Sean above Sera on desktop and the Sean header button on a phone, and the three tabs; images or the zip upload with per-file status three at a time; duplicates report as already saved; a reader/network failure can be retried; delete works; a non-owner gets 404 on `/sean/*` and the API; `vercel env ls` lists the three `LLM_*` names.
  - **Status**: open
  - **Plan Set**: `SEAN_GOTRADE_TRACKER_PLAN.md` (phase 2 of 7)
  - **Satisfies**: R1 — A new system called Sean, reached by a Sean button placed above the Sera button in the Seer UI; R3 — Upload Buy/Sell Order Summary screenshots; Sean parses them with glm-4.6v, the run-insights way
  - **Depends on**: P1-ROOT-AUY5
  - **Unblocked**: 2026-10-07 - P1-ROOT-AUY5 (phase 1) completed; its `web/lib/sean` modules and migration 015 now exist on `feature/sean-gotrade-tracker`.
  - **Plan**: `.workflows/plan/P1-ROOT-UNS5.md`

- [ ] **P1-ROOT-8JIM** Phase 3: Overview: P&L graph and holdings
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `web/app/sean/page.tsx` (replaces Phase 2's placeholder), `web/app/sean/overview.ts` + `overview.test.ts` (pure view model over Phase 1's ledger), `web/app/sean/OverviewBody.tsx` + `OverviewBody.test.tsx`, `web/app/sean/overview.module.css`, `web/lib/sean/overviewData.ts` (new: `equity()`, `marks()`); reads orders through Phase 2's `ledgerOrders()`. Content: stats row (total P&L, realized, unrealized, fees paid, fees as % of money traded); `LineChart` of daily `pnl_usd` from `sean_equity` (faint dashed cumulative fees, break-even line) plus a live point for today (New York date) when an order is newer than the last nightly session; when `sean_equity` is empty, `pnlSeries` over the orders' New York trade dates at last order prices with a caption that prices come nightly; holdings table (shares, average cost with buying fees, last price — italic when it is the order price — value, P&L `.pos/.neg`); empty state with an icon button to Trades. Does not touch `data.ts`, Trades, Plan, `Nav`, `AppHeader`, engine; shares no file with Phase 5. Exit: `tsc`, vitest (`overview.test.ts`, `OverviewBody.test.tsx`: zero, one, many orders; nightly series with and without a live point) and `next build` green; `/sean` no longer shows the placeholder.
  - **Status**: blocked
  - **Plan Set**: `SEAN_GOTRADE_TRACKER_PLAN.md` (phase 3 of 7)
  - **Satisfies**: R2 — Sean tracks all of the owner's Gotrade trading activity and shows a profit-and-loss graph
  - **Depends on**: P1-ROOT-AUY5, P1-ROOT-UNS5
  - **Plan**: `.workflows/plan/P1-ROOT-8JIM.md`

- [ ] **P1-ROOT-5YLK** Phase 4: Engine: marks and the daily P&L series
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sean/{__init__,ledger,marks,equity}.py`, `engine/src/seer_engine/commands/sean.py` (subcommand `marks`; `_HANDLERS = {"marks": _marks}` of `(conn, args) -> int`), tests `test_sean_{ledger,marks,command}.py` (ledger against Phase 1's `fixtures/ledger.json`, pro-rata oversell), `.github/workflows/sean.yml` (`workflow_dispatch`, optional `dry_run` input, no required input, group `sean-writer`, runs migrate + `sean marks`), one `Sean marks` step at the end of `nightly.yml` (`continue-on-error: true`). Does not touch `sim/`, `lab/`, `paper/`, web, migrations. Exit: ruff + full pytest green with nothing skipped; `python -m seer_engine sean marks` against an empty `sean_orders` exits 0 with no network call; both workflow files parse.
  - **Status**: open
  - **Plan Set**: `SEAN_GOTRADE_TRACKER_PLAN.md` (phase 4 of 7)
  - **Satisfies**: R2 — Sean tracks all of the owner's Gotrade trading activity and shows a profit-and-loss graph
  - **Depends on**: P1-ROOT-AUY5
  - **Unblocked**: 2026-10-07 - P1-ROOT-AUY5 (phase 1) completed; its `web/lib/sean` modules and migration 015 now exist on `feature/sean-gotrade-tracker`.
  - **Plan**: `.workflows/plan/P1-ROOT-5YLK.md`

- [ ] **P1-ROOT-XA2W** Phase 5: Plan: link a roster method, buy/sell reminders
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `web/lib/sean/reminders.ts` + test (pure: plan orders = New York trade date on/after `since`; sells for plan holdings no longer picked, buys sized `weight × planSize`, add/trim only for resizing rule sets — incl. the two `-gotrade` presets — when the gap ≥ max($10, 1% of the plan); done = a matching order whose New York trade date is on/after the decision session, or a mark); `web/lib/sean/planData.ts` (new: `linkableMethods`, `link`, `latestTargets`, `reminderMarks`, `latestCloses`, `planState`, React-`cache`d `openReminderCount`); `web/app/sean/plan/{page, view(+test), actions (via isSeanCaller), LinkPicker, PlanSettings, plan.module.css}` (replaces the placeholder); `planOpen` into `SeanNav`; the coral dot + "· N to do" words on both Sean buttons — `Nav.tsx` (`seanOpen` prop via `(app)/layout.tsx`) and `AppHeader.tsx` (reads the cached count). Rules: only active, non-benchmark `engine='book'` roster rows are linkable; `since` defaults to the method's latest decision session; pre-plan holdings never get a sell reminder; plain sentences, no ids. Does not touch `data.ts`, Overview files, `overviewData.ts`, Trades upload, `cadence.ts`, engine. Exit: reminder and view tests green (fresh link, the real Oct 7 follow-through, month turnover, partial follow-through, an after-midnight-WIB order, resize band, pre-plan holdings untouched, marked done); `tsc`, full vitest, `next build` green.
  - **Status**: blocked
  - **Plan Set**: `SEAN_GOTRADE_TRACKER_PLAN.md` (phase 5 of 7)
  - **Satisfies**: R4 — Connect Sean to one roster method (RAW today); Sean reminds the owner to buy / sell by it
  - **Depends on**: P1-ROOT-AUY5, P1-ROOT-UNS5
  - **Plan**: `.workflows/plan/P1-ROOT-XA2W.md`

- [ ] **P1-ROOT-8S6O** Phase 6: Engine: Gotrade fee schedule as a cost-model lever
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sim/costs.py` (`GOTRADE` schedule of four dated `FeeRegime`s fitted to the receipts — current regime since 2026-06-16: trading 0.2% half-up, min $0.10; regulatory 0.054% rounded up, cap $0.11, sells +0.04% up; PPN 11% of the printed fees, half-down; `fee_parts(side, amount, on=None)`, `GOTRADE.current`, `gotrade_cash`, `gotrade_shares_for`); `TradeRules.cost_model: Literal['flat','gotrade'] = 'flat'` in `LEVERS_SINCE_PINS`, validated (`gotrade` needs the default `cost_rate`; never for `DESIGN_V0`); `rule_owner_inputs` does not flag it; `describe_rules` line; `sim/book.py` money functions dispatch on the model (every simulated fill at the current regime); lab SPY benchmark and `dev._run` pay the candidate's model; `engine/tests/fixtures/gotrade_fees.json` (fee-only rows); tests incl. `test_sim_costs.py` and `test_cost_model_pins.py` (every committed lab digest recomputes byte for byte). Adds no preset. Does not touch `DESIGN_V0`/bracket engine (`sim/model.py`, `sizing.py`, `lifecycle.py`), `paper/` (paper benchmark stays flat), web. Exit: ruff + full pytest green incl. `test_registry`, `test_lab_methods`, `test_paper_roster`, `test_cost_model_pins`; every current-regime receipt reproduced to the cent; a gotrade book run on $28 slots pays more than flat.
  - **Status**: in_progress
  - **Plan Set**: `SEAN_GOTRADE_TRACKER_PLAN.md` (phase 6 of 7)
  - **Satisfies**: R5 — Real Gotrade costs feed method exploration and the Sera lab's profit-and-loss
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ROOT-8S6O.md`

- [ ] **P1-ROOT-GB56** Phase 7: Lab: calibrate from real orders, measure methods at real cost
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `engine/src/seer_engine/sean/calibrate.py` + `commands/sean.py` subcommand `calibrate` (replays `fee_parts` on each receipt's WIB date; exit 1 when an order since `GOTRADE.current.since` is off by more than a cent); `engine/src/seer_engine/lab/real_costs.py` + `lab costs MNNNN` (report only: no trial, N unchanged, one journal observation); `runner.preflight` refuses a flat-cost variant from M0031; the two real-fee presets `MONTHLY_HOLD_FRAC_GOTRADE` / `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` appended to `PRESETS` (rules.py after Phase 6) with their pins in `test_sim_rules.py` and Phase 6's `test_cost_model_pins.py`; `web/lib/cadence.ts` `SPLIT_CADENCE_RULES` + test learn `monthly-rank-weekly-resize-frac-gotrade`; tests `test_sean_calibrate.py`, `test_lab_costs.py`; both lab skills + `method_template.py`; design doc costs line + §15. Does not touch `sim/costs.py` numbers, `sim/book.py`, `backtest/*` (Phase 6); Phase 4's `marks` code; other web files; existing trial rows; `lab/lab.sqlite`. Exit: ruff + full pytest green (DB tests with `PG_TEST_URL`); `web/lib/cadence.test.ts` green; `sean calibrate` exits 0 on the fee fixture and 1 on a drifted receipt; `lab costs` writes exactly one insight and leaves trials, moments, methods, N and looks unchanged; `lab run` refuses a flat-cost M0031 and accepts one on `MONTHLY_HOLD_FRAC_GOTRADE`; `lab costs M0007` runs locally (`SEER_LAB_COSTS_LIVE=1`, skipped in CI).
  - **Status**: blocked
  - **Plan Set**: `SEAN_GOTRADE_TRACKER_PLAN.md` (phase 7 of 7)
  - **Satisfies**: R5 — Real Gotrade costs feed method exploration and the Sera lab's profit-and-loss
  - **Depends on**: P1-ROOT-5YLK, P1-ROOT-8S6O
  - **Plan**: `.workflows/plan/P1-ROOT-GB56.md`

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

---

## Completed Tasks

- [x] **P1-ROOT-AUY5** Phase 1: Sean core: schema, screenshot reader, ledger
  - **Difficulty**: HARD
  - **Type**: Feature
  - **Context**: Owns `db/migrations/015_sean.sql` (contract A verbatim + header comment); `web/lib/sean/` pure modules: `types.ts`, `money.ts` (receipt text → numbers, `roundHalfUp`/`cents`/`fixed`, WIB date+time → ISO `…+07:00`), `extractJson.ts` (verbatim port), `prompt.ts` (model transcribes printed strings; code converts), `vision.ts` (`visionConfigFromEnv`, `callVisionWithFetch`, `readOrderWithFetch`, `repairOrderWithFetch`, text-aware token floor `ceil(text chars / 3) + 150 per image` that fails closed, `VisionTokenFloorError`, `VisionTransportError`), `order.ts` (`toOrder(raw)`; checks total = amount ± fees within $0.01, amount ≈ price × shares within `$0.01 + shares × $0.005`, partial fills sum to shares; refuses every status but Filled), `readOrder.ts` (`readOrder(visionDeps(cfg), imageB64, budgetMs = 55_000)`, never throws for a model problem; one repair that re-sends the image, budget-gated; `isReaderDown(code)` splits 502 from 422; `READ_MESSAGES` plain words), `ledger.ts` (contract B: `LedgerOrder`, `Close`, `Holding`, `PnlPoint`, `orderSession`, `buildLedger`, `pnlSeries`, `pnlAt`), `unzip.ts` (`readZip`, `ZipError`, stored + deflate, CRC-checked, skips folders/`__MACOSX`/`.DS_Store`), `fixtures/ledger.json` (shared with Phase 4's pytest), `fixtures/receipts.json` (4 real receipts), seven colocated test files (92 tests), live smoke script `web/scripts/sean-vision-smoke.mjs` (not CI). Does not touch any page, route, component, Nav; engine; `web/package.json`. Exit: `tsc` clean; vitest green (all 4 fixture receipts convert; the ledger reproduces `fixtures/ledger.json` to the cent); `015_sean.sql` applies after 001–014 on a fresh schema and re-applies as a no-op (`engine/tests/test_migrate.py`); `next build` green; nothing outside `db/migrations/015_sean.sql`, `web/lib/sean/`, `web/scripts/sean-vision-smoke.mjs` changed.
  - **Status**: completed
  - **Plan Set**: `SEAN_GOTRADE_TRACKER_PLAN.md` (phase 1 of 7)
  - **Satisfies**: R2 — Sean tracks all of the owner's Gotrade trading activity and shows a profit-and-loss graph; R3 — Upload Buy/Sell Order Summary screenshots; Sean parses them with glm-4.6v, the run-insights way
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ROOT-AUY5.md`
  - **Completed**: 2026-10-07 23:21
  - **Method**: /do
  - **Files**: db/migrations/015_sean.sql, web/lib/sean/types.ts, web/lib/sean/money.ts, web/lib/sean/money.test.ts, web/lib/sean/extractJson.ts, web/lib/sean/extractJson.test.ts, web/lib/sean/prompt.ts, web/lib/sean/vision.ts, web/lib/sean/vision.test.ts, web/lib/sean/order.ts, web/lib/sean/order.test.ts, web/lib/sean/fixtures/receipts.json, web/lib/sean/readOrder.ts, web/lib/sean/readOrder.test.ts, web/lib/sean/ledger.ts, web/lib/sean/ledger.test.ts, web/lib/sean/fixtures/ledger.json, web/lib/sean/unzip.ts, web/lib/sean/unzip.test.ts, web/scripts/sean-vision-smoke.mjs
  - **Verified**: `tsc --noEmit` clean; `vitest run lib/sean` 7 files, 92/92 passed; full vitest 472 passed, 1 failed (`lib/sera/lab.test.ts` 'publishes a verdict that agrees with the gate' - the known-red at base c2d2891 named in plan invariant 1, not caused by this phase); `next build` green; `engine/tests/test_migrate.py` 31 passed (015 applies after 001-014 and re-applies as a no-op).
  - **Drift**: none - all 20 files written verbatim from the plan's code blocks; no existing file modified
  - **Decided**: Step 3 task creation with phase 6 running concurrently in the same worktree -> phase 1 created all 7 tasks, phase 6 acked and skipped (tie-break: narrower blast radius, one writer)
  - **Decided**: Optional live smoke script (costs vision tokens) -> not run; the plan measured 30/30 while planning and it is marked optional, not an exit criterion (rung 2)


- [x] **P1-ROOT-T8MK** Phase 2: Run it, and record what it found
  - **Difficulty**: NORMAL
  - **Type**: Update
  - **Context**: Owns the actual Monte Carlo run and its results: a new section appended at the tail of `docs/plans/2026-10-03-seer-design.md` in §12's voice (expected §14, numbered at write time), one `kind='risk'` `insights` row in `lab/lab.sqlite`, and `web/data/lab.json` regenerated with `lab export-json` because `engine/tests/test_lab_snapshot.py:449` pins it byte-for-byte to the database. It appends only — no edit to design §1, §5, §11, §12 or §13, and no code. Exit: a break-even delisting return — or an explicit "not reached on this grid", which is an expected result and not a stop condition — for each of RMW-FR, RAW-FR, MOM-FR and MVW-FR, with the assumed hazard, seed count and spread shown; the true unstressed run and the `r = 0` run reported as separate rows with the gap named as the cost of a thinner ranking pool; the section says the harness injects the historical rate into the ~409 priced survivors rather than restoring the historical count, states plainly whether the break-even is plausible and what the test cannot answer; the insight and `lab.json` land in the same breath; `lab status` reads 110 / 0 / 37 / 33; the full suite passes at 0 failed, 0 skipped.
  - **Status**: completed
  - **Plan Set**: `DELISTING_STRESS_ROSTER_RULES_PLAN.md` (phase 2 of 5)
  - **Satisfies**: R1 — Q1 — settle where the delisting stress test lives and what it needs, build it, run it, and report the break-even delisting return with a judgement on whether that number is plausible
  - **Depends on**: P1-ENG-D7XQ
  - **Unblocked**: 2026-10-07 18:16 — P1-ENG-D7XQ (phase 1) landed; the harness, its CLI spellings and the `--csv` schema phase 2 consumes now exist on `feature/delisting-stress-roster-rules`.
  - **Plan**: `.workflows/plan/P1-ROOT-T8MK.md`
  - **Completed**: 2026-10-07 19:32
  - **Method**: /do
  - **Files**: docs/plans/2026-10-03-seer-design.md, lab/lab.sqlite, web/data/lab.json
  - **Verified**: Full suite with worktree `PYTHONPATH` + `PG_TEST_URL` -> 3229 passed, 0 failed, 0 skipped, 58.09s (>= the 3197 branch baseline; xdist active). `ruff check --no-cache src tests` -> All checks passed. `lab status` -> 110 dev trials / 0 test-window looks / 37 methods / 33 insights (insights was 32; everything else unmoved, so no trial recorded and no test-window look spent). `grep -c '{{'` on the design doc -> 0, no placeholder survived; `git diff --numstat` on it -> `133 0`, append-only, and SS1, SS11, SS12, SS13 are untouched. `engine/.research` does not exist in the worktree, so nothing was written to the research store and there is no symlink to commit.
  - **Drift**: No drift. Every flag in phase 2's Interface Contract matched `delisting_stress.py --help` verbatim (--entry repeatable, --hazard unserved|all|NUMBER, --returns, --seeds, --seed0, --jobs default 1, --store, --csv, --decline-sessions, --smoke), and the --csv column names/order/units matched phase 1's declared schema exactly, including the empty delisting_return/seed on the unstressed row.
  - **Drift**: Step 0c's symlink fallback was NOT needed: --store plus SEER_RESEARCH_STORE were both honoured, so no untracked engine/.research exists in the worktree.
  - **Drift**: Runtime came in well under budget: the machine was idle, so each of the two 3,204-run jobs took 29.9 min at --jobs 6 against the plan's 50 min - 1 h 45 estimate. Peak RSS measured at 1.01 GB/worker, so --jobs 6 was kept as planned.
  - **Decided**: Phase plan Step 9 says commit here; /implement Step 4 says the main context performs no git operations and pusher commits from the modified_files allowlist -> delegated the commit to pusher with the path allowlist (rung: /implement Step 4 is the governing command spec, and invariant 8's 'explicit path allowlist, never git add -A' is satisfied exactly by pusher's paths).
  - **Decided**: MVW-FR's base run is NONE on the mean edge (+0.11 pts/yr at r=-100%) but 45 of its 100 draws DO break even, and the 5.1%/yr sensitivity solves it at -85.8% -> kept Step 6's branch-1 headline ('No - it cannot be reached at all') and stated the per-draw and sensitivity caveats in their own sentences rather than softening the headline or hedging into branch 2 (rung 3: phase 1's break_even() is defined on the mean edge across seeds; rung 2: exit criterion 1 requires the across-seed spread be shown).
  - **Decided**: The insight body's VERDICT_SENTENCE runs to two sentences rather than one, to carry the 5.1%/yr exception for the two thin-margin entries (rung 1: invariant 7 - numbers only with their meaning; a flat one-sentence 'impossible' would have overstated MVW-FR's margin).
  - **Decided**: `engine/package_readme.md` is NOT edited by this phase and the debt is carried to the set's coordinator, following phase 1's recorded precedent in this same set (rung 4: the index's phase-2 row declares Files: 3 and the plan's Files table states no file outside the three paths is touched; rung 6: phase 1 left the same debt with a detailed coordinator note). `readme-updater` therefore ran in **advisory mode** and wrote nothing. The outstanding debt is phase 1's list (`delisting.py` missing from the Layout tree, its eight-name `__all__` missing an Exported API H3, and an internal-module-graph bullet) PLUS one line this phase now answers: `engine/package_readme.md:1957` says 'yfinance has no delisted tickers, so ... single-stock dev results are optimistic (D4)' - that claim now has its measured answer in design SS14 and should be revised to point at it.
  - **Decided**: This phase's commit sweeps the root bookkeeping its four siblings deliberately left uncommitted - `.workflows/todos.md` (phases 2, 3 and 5's rows) and the plan index's row/Status ticks - because phase 2 is the set's last unfinished phase and the deferral reason is gone. MEASURED at `swarm.py:1413-1421`: `land --step cleanup` writes only a *filename list* of dirt to `worktree-dirt.txt` and then force-removes the worktree, so it commits nothing; 'left for land to sweep' had no sweeper but this one (rung 1: the dispatching constraint permits the bookkeeping lines and forbids only a peer's *in-flight* edit, and no peer is in flight - phases 1, 3, 4, 5 are all `done`; rung 2: phases 3 and 5 named land as the sweeper). `engine/.workflows/todos.md` and the four peer `P1-*.md` plan files stay OUT, being another package's file and other phases' documents, and are reported to the coordinator as still-uncommitted instead.
  - **Decided**: `.workflows/plan/P1-ROOT-T8MK.md` IS included in the allowlist though it is untracked. It is this task's own plan file, it is the path this row's `**Plan**` field cites, and the repo tracks all 116 of its siblings - leaving it untracked means `land --step cleanup` force-deletes the only record of what phase 2 was asked to do, and the row would cite a path that does not exist (tie-break: asymmetric cost - one extra small markdown file in the commit is recoverable, a destroyed plan file is not). The four peer plan files are not mine and stay out.

- [x] **P1-ROOT-W5GD** Phase 5: MOM-FR, judged under the rule
  - **Difficulty**: NORMAL
  - **Type**: Update
  - **Context**: Owns a new `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md` carrying the verdict on MOM-FR and the evidence behind it; it edits `paper/roster.py` only if the verdict is "swap", and then only under a new id with its own paper clock. It does not amend phase 3's rule, `lab/lab.sqlite` or any started entry's `spec_digest`. Exit: the verdict is stated plainly with the lab evidence (26 candidates clear all five owner conditions today; MOM-FR is 12th by DSR and 8th by MAR); it records that Q3's "slowest path to a verdict (20.7 months)" indictment is now void, since every entry reaches a verdict at 18 months flat; it weighs the family diversity MOM-FR alone holds against the higher lab scores of the weekly-brake alternatives; and it applies phase 3's rule by name at the real section number read from the file, with every `§<RULE>` / `<RULE-TITLE>` placeholder resolved so `grep -n 'RULE'` returns nothing. The full suite passes at 0 failed, 0 skipped.
  - **Status**: completed
  - **Plan Set**: `DELISTING_STRESS_ROSTER_RULES_PLAN.md` (phase 5 of 5)
  - **Satisfies**: R3 — Q3 — settle whether `MOM-FR` is the weakest of the five, and whether a better occupant of that slot exists in the lab
  - **Depends on**: P1-ROOT-K3VD
  - **Plan**: `.workflows/plan/P1-ROOT-W5GD.md`
  - **Completed**: 2026-10-07 18:22
  - **Method**: /implement
  - **Files**: docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md
  - **Decided**: The plan's verbatim §3 profit-factor gloss carried a corrupted currency glyph ('it makes ₂.33 on winners for every ₂ lost on losers') → written as '$2.33 on winners for every $1 lost on losers' (rung 1: invariant 7, prose the owner reads stays plain — over rung 3's instruction to reproduce the plan's code block verbatim)
  - **Decided**: Phase 3's rule resolved by reading the file, not assumed: §8, 'The roster replacement rule (2026-10-07)', refusals R1–R3 (§8.2) and triggers T1–T5 (§8.3) — all eight carried into the document's §2 table under phase 3's own names (rung 3: the plan's Step 1 code block)
  - **Decided**: Step 4 (the conditional roster edit) did NOT fire: the verdict is keep. paper/roster.py, engine/tests/test_paper_roster.py and db/migrations/ are unchanged, verified with git status

- [x] **P1-ROOT-K3VD** Phase 3: The roster replacement rule
  - **Difficulty**: NORMAL
  - **Type**: Update
  - **Context**: Owns a new top-level section (expected §8) of `docs/plans/2026-10-04-method-lab-design.md` stating when a paper roster entry may be replaced, extending §7.4's recorded paper-vs-lab divergence. Touches no code, no database, no lab trial; N stays 110. Exit: the rule names its own triggers (T1-T5) and refusals (R1-R3); is built on 18 months flat (the owner's revised item 1), not the superseded 14.9/19.4/20.7-month table; states that a falling DSR alone is never a reason to replace an entry, citing lab design §7.3's measured ratchet; says what happens to the replaced entry's record; is dated and attributed; names NO roster entry as a thing to be replaced (judging MOM-FR is phase 5's work under R3). Full suite passes 0 failed / 0 skipped.
  - **Status**: completed
  - **Plan Set**: `DELISTING_STRESS_ROSTER_RULES_PLAN.md` (phase 3 of 5)
  - **Satisfies**: R4 — Q4: write the rule for when a roster entry may be replaced, before the first one looks bad
  - **Depends on**: —
  - **Plan**: `.workflows/plan/P1-ROOT-K3VD.md`
  - **Completed**: 2026-10-07 18:11
  - **Method**: /do
  - **Files**: docs/plans/2026-10-04-method-lab-design.md
  - **Decided**: Section number for the appended rule: §8, text used verbatim with no renumbering (rung 3, the plan's code block — confirmed by measurement: highest existing top-level heading was `## 7.`, file was 281 lines, exactly the plan's expected output)
  - **Decided**: Step 3 task creation scoped to phase 3's task only, not all five phases (rung 1, invariant 8 — phases 1 and 4 are spawned concurrently and would race on the same todos.md; tie-break: narrower blast radius)
  - **Decided**: Phase 3's package `docs/plans` has no own .workflows/todos.md, so the task lives in the ROOT package (rung 6, existing convention — the prior docs phase landed as P1-ROOT-FWWQ there)
  - **Decided**: Commit allowlist is the one docs path alone; `.workflows/todos.md` excluded despite holding this task's row (rung 2, phase 3 exit criterion 9 — committing it would sweep two siblings' concurrently-written entries)

- [x] **P1-ROOT-FWWQ** Phase 7: Docs, the pre-registration wording, and the site's gate
  - **Difficulty**: NORMAL
  - **Type**: Update
  - **Context**: Owns design §3's definition of dev-eligible amended to both moved thresholds, with the correlation evidence and the date, and §7's dated revision (7.1 the luck bar, 7.2 the N left alone, 7.3 the deferred ratchet, 7.4 paper membership, 7.5 pointing at §1's drawdown change, 7.6 the seed re-run) in `docs/plans/2026-10-04-method-lab-design.md`; `prereg.py`'s baked N wording and `docs/lab/prereg/README.md`; `SKILL.md`; `engine/package_readme.md`; the snapshot `gate` block gaining the policy name, its N and its evidence; and the sera site's gate display, including matching both threshold-bearing failure labels by prefix in `derive.ts`. Does not touch engine behavior, either threshold, the policy default, any recorded trial, design §1 or `web/lib/metrics.ts` (both phase 8's). Shares seven files with phase 8, which lands first, and quotes the post-phase-8 state (`maxDrawdown: 0.2` already in place). Exit: no doc states a bar the lab does not apply; `derive.ts` reads both `DSR >= …` and `max DD <= …` by prefix and both prefixes are pinned to the engine; the sera site shows the policy and its N next to the luck bar; `npm run build` and `vitest` pass in `web/`; `pytest` green.
  - **Status**: completed
  - **Plan Set**: `LAB_LUCK_GATE_PLAN.md` (phase 7 of 9)
  - **Satisfies**: R1 — The gate admits nothing at 110 trials and the bar rises with every exploration regardless of merit — 110 correlated variant rows deflated as 110 independent trials.
  - **Depends on**: P1-ENG-B6Y5, P1-ENG-EH4K
  - **Plan**: `.workflows/plan/P1-ROOT-FWWQ.md`
  - **Completed**: 2026-10-07 14:16
  - **Method**: /do
  - **Files**: docs/plans/2026-10-04-method-lab-design.md, docs/lab/prereg/README.md, docs/ROADMAP.md, .claude/skills/explore-and-experiment-new-method/SKILL.md, engine/package_readme.md, engine/src/seer_engine/lab/prereg.py, engine/src/seer_engine/lab/store.py, engine/tests/test_lab_gate_wording.py, engine/tests/test_lab_prereg.py, engine/tests/test_lab_snapshot.py, web/lib/sera/types.ts, web/lib/sera/lab.ts, web/lib/sera/lab.test.ts, web/lib/sera/derive.ts, web/lib/sera/derive.test.ts, web/lib/sera/fixture.ts, web/lib/sera/glossary.ts, web/app/sera/overview.ts, web/app/sera/overview.test.ts, web/app/sera/page.tsx, web/app/sera/methods/view.ts, web/app/sera/methods/view.test.ts, web/app/sera/methods/[id]/page.tsx, web/app/sera/how/view.ts, web/app/sera/how/view.test.ts, web/data/lab.json, .workflows/todos.md, .workflows/plan/P1-ROOT-FWWQ.md
  - **Drift**: engine/package_readme.md had already been rewritten by phase 4 at the two regions the plan quoted (:1868-1874 gate_text bullet and :2420). Applied the plan's reconciled wording onto phase 4's current text rather than the pre-phase-4 text the plan quoted; the plan's version is now the more accurate of the two because Step 2 stopped gate_text using store.DSR_LABEL.
  - **Drift**: Plan Step 16's Impact note claimed glossary.test.ts asserts only that every condition key has a term. It also asserts exactly one sentence per entry, which the plan's two-sentence prose broke.
  - **Drift**: Phase 8's H2 handoff named package_readme.md drawdown RULE lines by line number; phase 4's additions had shifted them. Classified by content instead: six rule statements moved 15%->20%, and the VERDICT/history lines plus every backticked recorded label left untouched, as H2 directed.
  - **Decided**: SKILL.md's stale 15% drawdown guardrail row and its 'under the 15% limit' example, flagged by phase 8's H2 but not named in my plan's Step 7 -> fixed alongside the luck-bar row (rung 2: phase 7's exit criterion is 'no doc states a bar the lab does not apply', and SKILL.md is in this phase's Owns).
  - **Decided**: Four phase-4 package_readme.md lines quoting the recorded 'DSR >= 0.95' label tripped Step 9's new guard -> the guard now skips matches inside backtick code spans, instead of rewriting phase 4's prose (rung 3: the guard's own docstring already exempts recorded strings as 'quoting data, not stating the rule'; rewriting them would falsify what the append-only rows hold).
  - **Decided**: Step 16's glossary prose vs glossary.test.ts's one-sentence-per-entry assertion -> prose reworded to one sentence each, test untouched (tie-break rule: a failing verification is never settled by relaxing the check).
  - **Decided**: docs/ROADMAP.md:75 stated 'DSR >= 0.95 at N joins the five D8 hurdles' as the live rule -> fixed to 0.90 with the date and a pointer to design 7.1 (rung 2: exit criterion 1 requires 0.95-as-the-gate to survive only in the design document). ROADMAP.md:78's 'DSR 0.90 at N = 58' left as history, exactly as the plan's Handoffs direct. ROADMAP.md was deliberately NOT added to the guard's SCANNED list, which the plan chose on purpose.

- [x] **P1-ROOT-MO5N** Phase 7: Keep it current: CI, skills, docs
  - **Difficulty**: EASY
  - **Type**: Feature
  - **Context**: Owns `.github/workflows/engine-ci.yml` (`lab/**` in both path filters), `.claude/skills/explore-and-experiment-new-method/SKILL.md` (solo mode commits through `lab stage`, full pytest after staging, plain-language analysis with explicit `My opinion:`), `.claude/skills/sera-the-explorer/SKILL.md` (every `lab stage` commit includes `web/data/lab.json`, preflight tests after staging, batch synthesis via `--kind synthesis`), `docs/ROADMAP.md` (P8 entry for the method lab and Sera), `web/package_readme.md` (Sera section matching the reconciled tree). Does not touch code. Exit: docs accurate to the merged code; CI green.
  - **Status**: completed
  - **Plan Set**: `SERA_LAB_SITE_PLAN.md` (phase 7 of 7)
  - **Satisfies**: R3 — Show every experiment, as detailed as possible, kept current with no human step; R5 — Concise, non-technical explanations, with analysis and opinion on every method; R6 — Insights from every exploration; food for thought on features and data sources; R7 — As comprehensive as possible (cross-cutting)
  - **Depends on**: P1-ENG-6QQA, P1-WEB-RL9Z, P1-WEB-9ANC, P1-WEB-08WD
  - **Plan**: `.workflows/plan/P1-ROOT-MO5N.md`
  - **Completed**: 2026-10-04 22:29
  - **Method**: /do
  - **Files**: .github/workflows/engine-ci.yml, .claude/skills/explore-and-experiment-new-method/SKILL.md, .claude/skills/sera-the-explorer/SKILL.md, docs/ROADMAP.md, web/package_readme.md
  - **Drift**: web/package_readme.md had already been updated by phases 2-6's readme-updater, so Step 7's layout/test-line blocks were not pasted verbatim (they would duplicate). Followed intent: added the missing Overview page.tsx/overview.ts and data/lab.json to the layout, the Overview sentence, a new '## Sera (/sera)' section (routes, access gate, data source and how it stays current), the Sera config line, the vitest line now says sera/*, and three gotchas (generated lab.json, relative imports, escape-first markdown).
  - **Decided**: Plan text 'He is not a quant' (explore skill step 7) -> reworded to 'and is not a quant' (no pronoun), since the owner's pronouns are not stated (rung 6: convention)

- [x] **P1-ROOT-ZEOM** Phase 7: Ship: Veto workflow step, live smoke, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `.github/workflows/nightly.yml` (`Veto` step after `Nightly`, before `Paper`; `continue-on-error: true`; `timeout-minutes: 10`; env `FINNHUB_API_KEY`, `LLM_*` from secrets; job stays 45 min); a live smoke (local, scratchpad, never committed, no database) of the phase-3 clients + K1 prompt/parser for 10 liquid symbols with timings recorded in the runbook; `engine/package_readme.md` (`veto` incl. H1, `finnhub`, `strategies.c`, store additions, migration 004); `docs/runbooks/paper-trading.md` (the veto step, failure states quoting phase 6's exact strings, owner steps for `FINNHUB_API_KEY` and `LLM_*`, C's clock, `--require-sessions` counting C, reset procedures that keep `news_vetoes`); `docs/ROADMAP.md` (P6 with D11's wording); `.env.example` comment. Does not touch: source behaviour; `web/**` (incl. `web/package_readme.md`, phase 6's); Neon; GitHub secrets. Exit: `actionlint`-clean YAML (or the YAML assertion), CI commands pass locally, smoke timings recorded, no `‹` left in the docs, docs updated, diff limited to the five files and free of secrets.
  - **Status**: completed
  - **Plan Set**: `STRATEGY_C_NEWS_VETO_PLAN.md` (phase 7 of 7)
  - **Satisfies**: R3 — Workflow: `Veto` step between `Nightly` and `Paper`, inside the 45-minute job; R5 — Docs: engine readme, paper runbook (veto step, failures, owner steps, C's clock), ROADMAP P6 (D11)
  - **Depends on**: P1-ENG-QRXI, P1-ENG-IIZE, P1-WEB-8YO3
  - **Plan**: `.workflows/plan/P1-ROOT-ZEOM.md`
  - **Completed**: 2026-10-04 18:36
  - **Method**: /do
  - **Files**: .github/workflows/nightly.yml, docs/runbooks/paper-trading.md, engine/package_readme.md, docs/ROADMAP.md, .env.example
  - **Drift**:
    - None in the target files (all anchor lines matched HEAD). The live smoke script was run from the session scratchpad and NOT committed, as planned.
  - **Decided**:
    - Runbook Measured table label for Finnhub company-news: the plan's prose said the time 'includes the client's >= 1 s spacing', but the smoke measured 0.26-0.36 s because the spacing had already passed during the previous LLM call. The label now says so (and the readme Performance line likewise); calendar/earnings keeps 'includes the spacing' (1.26 s). Rung 6 / honest reporting: measured values over an expectation in prose.

- [x] **P1-ROOT-FOK3** Phase 13: Ship: CI lint, workflow, Neon, Vercel, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `.github/workflows/engine-ci.yml` (ruff `select = ["E9", "F"]`, `ignore = ["F401"]` + `tsc --noEmit`), `engine/pyproject.toml` (ruff config, `ruff>=0.16,<0.17` dev dep), `.github/workflows/nightly.yml` ("Paper check" and "Explain" steps; `timeout-minutes` 30 → 45), applying `003` to Neon and a `paper --dry-run` against Neon, a **preview** `vercel deploy` of the worktree tree (production deploys from `main` on merge through the Git integration; seertrade.site is already live), `docs/runbooks/paper-trading.md` (operations + owner steps: LLM secrets, Google OAuth, Vercel env if missing, Add to Home Screen; no DNS step + the release checklist), `docs/runbooks/data-pipeline.md`, `docs/ROADMAP.md` (P0, P4 paper-only entry, P5, v0.1.0), `engine/package_readme.md` sections. Does not touch: source behavior. The README and the `v0.1.0` release are **not** in this phase (see After landing). Exit: CI commands pass locally; Neon at migration 003; dry-run paper on Neon succeeds; preview deploy URL and production URL recorded, remaining owner steps named in the runbook; docs updated.
  - **Status**: completed
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 13 of 13)
  - **Satisfies**: R6 — Ship: CI lint (P0), Vercel deploy, owner-step runbook, README + `v0.1.0` at release; R7 — Docs: engine readme, ROADMAP, paper runbook
  - **Depends on**: P1-ENG-N6UC, P1-ENG-HCYN, P1-ENG-79OL, P1-ENG-1BVI, P1-ENG-X99Y, P1-ENG-AYRQ, P1-ENG-0ZLD, P1-ENG-WBI7, P1-ENG-YEW4, P1-WEB-Y9MV, P1-WEB-0AHX, P1-WEB-DX8D
  - **Plan**: `.workflows/plan/P1-ROOT-FOK3.md`
  - **Completed**: 2026-10-04 10:22
  - **Method**: /do
  - **Files**: engine/pyproject.toml, .github/workflows/engine-ci.yml, .github/workflows/nightly.yml, docs/runbooks/paper-trading.md, docs/runbooks/data-pipeline.md, docs/ROADMAP.md, engine/package_readme.md
  - **Drift**:
    - paper -v logs only each strategy's start on a first night (no per-decision lines); the runbook ship check records that honestly instead of the plan's expected 'A sized picks / not a decision session' log lines. No source change.
    - Web suite is 9 files / 65 tests (plan's token example was illustrative).

- [x] **P1-ROOT-2QEA** Phase 5: Workflows, seed guard, runbook, live run on Neon
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `.github/workflows/{engine-ci,nightly,universe,backfill}.yml`, `web/scripts/seed-demo.mjs` (refuse when > 100 real bars), `docs/runbooks/data-pipeline.md` (exit codes, split handling), `docs/ROADMAP.md` P1 line, data-only appends to `engine/data/membership_overrides.csv` on `universe check` drift, and the live Neon execution (migrate → universe refresh (purges demo) → universe check → backfill with pinned `--end` → `--retry-failed` → nightly ×2 + dry run with checksums → web read path → storage size), recorded in the runbook. Does not touch `engine/**` code, `git push`, `gh secret set`, `web/app`, `web/components`, `web/lib`. Exit: workflows pass `actionlint` (or YAML parse); CI fails if any engine test is skipped; seed refuses on Neon after backfill; Neon has migration 002 and no demo rows; `bars` covers every fetchable ever-member since 2015-01-02 with unfetchable ones in `backfill_log` and the runbook, under 400 MB; two nightly runs and one dry run leave identical fingerprints and the single real `runs` row equals `dates.run_dates(now)`; runbook acceptance checklist ticked with evidence; nothing pushed, no secret set.
  - **Status**: completed
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 5 of 5)
  - **Satisfies**: R1 — Backfill 10+ years of split-adjusted daily bars for every ever-member (yfinance), logging unfetchable symbols; R3 — Nightly Actions job: Massive bars + Frankfurter FX + `runs` row with correct dates; failed fetch → `failed` run, no partial bars; R5 — First real engine write deletes all demo data atomically
  - **Depends on**: P1-ENG-853Z, P1-ENG-L73U, P1-ENG-GF8Y
  - **Plan**: `.workflows/plan/P1-ROOT-2QEA.md`
  - **Completed**: 2026-10-03 13:28
  - **Method**: /do
  - **Files**: .github/workflows/engine-ci.yml, .github/workflows/nightly.yml, .github/workflows/universe.yml, .github/workflows/backfill.yml, web/scripts/seed-demo.mjs, docs/runbooks/data-pipeline.md, docs/ROADMAP.md
  - **Drift**:
    - No drift. engine/data/membership_overrides.csv untouched: universe check showed no drift (SP500 503/503, NDX 101/101 identical).
    - Live nightly run 1 made no Massive call (the backfill already reached data_date 2026-10-02). A read-only Massive grouped-daily probe confirmed the key works and its closes match yfinance (SPY 769.64 etc.).
    - GPS (Gap Inc., now GAP) is logged empty: a rename with no ticker_aliases row (Phase 2 data). It is not a current member, so it does not matter for P1. Recorded in the runbook.

---

## Archive
