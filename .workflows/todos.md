# Todos: root (repo-wide)

**Package Path**: `.`
**Package Code**: ROOT
**Last Updated**: 2026-10-07 14:16:00
**Total Active Tasks**: 0

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 0
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 0
- Completed: 5

---

## Active Tasks

### [P0] Critical

### [P1] High

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

---

## Completed Tasks

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
