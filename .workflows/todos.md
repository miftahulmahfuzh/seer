# Todos: root (repo-wide)

**Package Path**: `.`
**Package Code**: ROOT
**Last Updated**: 2026-10-03 12:50:26
**Total Active Tasks**: 1

TaskID format: `P{Priority}-{PackageCode}-{4CharID}` (4CharID = 4 random uppercase alphanumerics, unique).

## Quick Stats
- P0 Critical: 0
- P1 High: 0
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 1
- Completed: 0

---

## Active Tasks

### [P0] Critical

### [P1] High

### [P2] Medium

### [P3] Low

### [P4] Backlog

### 🚫 Blocked
- [ ] **P1-ROOT-2QEA** Phase 5: Workflows, seed guard, runbook, live run on Neon
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `.github/workflows/{engine-ci,nightly,universe,backfill}.yml`, `web/scripts/seed-demo.mjs` (refuse when > 100 real bars), `docs/runbooks/data-pipeline.md` (exit codes, split handling), `docs/ROADMAP.md` P1 line, data-only appends to `engine/data/membership_overrides.csv` on `universe check` drift, and the live Neon execution (migrate → universe refresh (purges demo) → universe check → backfill with pinned `--end` → `--retry-failed` → nightly ×2 + dry run with checksums → web read path → storage size), recorded in the runbook. Does not touch `engine/**` code, `git push`, `gh secret set`, `web/app`, `web/components`, `web/lib`. Exit: workflows pass `actionlint` (or YAML parse); CI fails if any engine test is skipped; seed refuses on Neon after backfill; Neon has migration 002 and no demo rows; `bars` covers every fetchable ever-member since 2015-01-02 with unfetchable ones in `backfill_log` and the runbook, under 400 MB; two nightly runs and one dry run leave identical fingerprints and the single real `runs` row equals `dates.run_dates(now)`; runbook acceptance checklist ticked with evidence; nothing pushed, no secret set.
  - **Status**: blocked
  - **Plan Set**: `ENGINE_DATA_PIPELINE_PLAN.md` (phase 5 of 5)
  - **Satisfies**: R1 — Backfill 10+ years of split-adjusted daily bars for every ever-member (yfinance), logging unfetchable symbols; R3 — Nightly Actions job: Massive bars + Frankfurter FX + `runs` row with correct dates; failed fetch → `failed` run, no partial bars; R5 — First real engine write deletes all demo data atomically
  - **Depends on**: P1-ENG-853Z, P1-ENG-L73U, P1-ENG-GF8Y
  - **Plan**: `.workflows/plan/P1-ROOT-2QEA.md`

---

## Completed Tasks

---

## Archive
