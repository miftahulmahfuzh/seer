# Todos: root (repo-wide)

**Package Path**: `.`
**Package Code**: ROOT
**Last Updated**: 2026-10-04 10:13:00
**Total Active Tasks**: 1

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 1
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 0
- Completed: 1

---

## Active Tasks

### [P0] Critical

### [P1] High
- [ ] **P1-ROOT-FOK3** Phase 13: Ship: CI lint, workflow, Neon, Vercel, docs
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `.github/workflows/engine-ci.yml` (ruff `select = ["E9", "F"]`, `ignore = ["F401"]` + `tsc --noEmit`), `engine/pyproject.toml` (ruff config, `ruff>=0.16,<0.17` dev dep), `.github/workflows/nightly.yml` ("Paper check" and "Explain" steps; `timeout-minutes` 30 → 45), applying `003` to Neon and a `paper --dry-run` against Neon, a **preview** `vercel deploy` of the worktree tree (production deploys from `main` on merge through the Git integration; seertrade.site is already live), `docs/runbooks/paper-trading.md` (operations + owner steps: LLM secrets, Google OAuth, Vercel env if missing, Add to Home Screen; no DNS step + the release checklist), `docs/runbooks/data-pipeline.md`, `docs/ROADMAP.md` (P0, P4 paper-only entry, P5, v0.1.0), `engine/package_readme.md` sections. Does not touch: source behavior. The README and the `v0.1.0` release are **not** in this phase (see After landing). Exit: CI commands pass locally; Neon at migration 003; dry-run paper on Neon succeeds; preview deploy URL and production URL recorded, remaining owner steps named in the runbook; docs updated.
  - **Status**: open
  - **Plan Set**: `PAPER_TRADING_SHIP_PLAN.md` (phase 13 of 13)
  - **Satisfies**: R6 — Ship: CI lint (P0), Vercel deploy, owner-step runbook, README + `v0.1.0` at release; R7 — Docs: engine readme, ROADMAP, paper runbook
  - **Depends on**: P1-ENG-N6UC, P1-ENG-HCYN, P1-ENG-79OL, P1-ENG-1BVI, P1-ENG-X99Y, P1-ENG-AYRQ, P1-ENG-0ZLD, P1-ENG-WBI7, P1-ENG-YEW4, P1-WEB-Y9MV, P1-WEB-0AHX, P1-WEB-DX8D
  - **Plan**: `.workflows/plan/P1-ROOT-FOK3.md`

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked

---

## Completed Tasks

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
