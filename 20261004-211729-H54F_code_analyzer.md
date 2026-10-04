# Code Analysis: seertrade.site/sera — the method lab, shown

**Type:** Feature Implementation
**Date:** 2026-10-04 21:17 WIB
**Session ID:** 20261004-211729-H54F
**Plan:** `SERA_LAB_SITE_PLAN.md` (7 phases)
**Worktree:** `/home/miftah/.worktrees/seer/sera-lab-site`, branch `feature/sera-lab-site`, base `origin/main` @ `c138b08` (local main clean and equal to origin)

---

## User Input

### Original User Request

```
sera feature --permission-mode bypassPermissions
for now, let's optimize the UI for desktop only.
we need to create another system like seertrade.site/sera . only accept mahfuzh74@gmail.com user to see this system.
here , we can see every experiment that we have done. as detailed as possible.
draw all the important graphs / diagram. explain everything concisely and in a non-technical manner, include your analysis on every method, your opinion.
your insights is really important in every explorations. maybe you think we need another feature, or source of data beside all we have right now. just write it all there, as our food for thought
make it as comprehensive as possible

Context (from the session that built the method lab, 2026-10-04): the experiment record is the committed SQLite file lab/lab.sqlite (tables methods, trials incl. month-end curve_json, ideas_seen, insights; access layer engine/src/seer_engine/lab/store.py, CLI engine/src/seer_engine/commands/lab.py; design docs/plans/2026-10-04-method-lab-design.md). It is updated by /explore-and-experiment-new-method and /sera-the-explorer and pushed to main, and every push to main deploys production on Vercel (web/, Next.js, Auth.js Google, ALLOWED_EMAIL). The web must never need a human step to show new experiments. Owner confirmed mahfuzh74@gmail.com is the right address. The iron rules: no human in the loop; follow the Seer v2 design language (memory: no vanilla UI, icon-only Lucide buttons with aria-label + tooltip).
```

### User-Provided Context
- The owner earlier stated two iron rules for the lab skills: "WE NEVER STOP TRYING, WE NEVER GIVE UP" and "NO HUMAN IN THE LOOP".
- The owner confirmed in chat that `mahfuzh74@gmail.com` is the intended address.

### User-Provided Files
None (`@` files).

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Optimize the UI for desktop only (for now) |
| R2 | A separate system at seertrade.site/sera, visible only to mahfuzh74@gmail.com |
| R3 | Show every experiment done so far, as detailed as possible (and keep showing new ones with no human step) |
| R4 | Draw all the important graphs and diagrams |
| R5 | Explain everything concisely and non-technically, including an analysis and opinion on every method |
| R6 | Insights from every exploration, plus food for thought: needed features and other data sources |
| R7 | Make it as comprehensive as possible |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** The method lab's whole record (methods, trials with month-end equity curves, analyses, verdicts, ideas, the insights journal) lives in `lab/lab.sqlite`. It is readable only through the Python CLI or an xlsx export. The owner wants a private, desktop-first web section at `/sera`, inside the existing Next.js app on Vercel, that presents that record comprehensively: charts, diagrams, plain-language explanations, per-method analysis and opinion, and the cross-cutting insights. It must stay current automatically as the explore and sera skills push new results.

**Success Criteria.**
- `https://seertrade.site/sera` renders for mahfuzh74@gmail.com only. Signed-out visitors go to sign-in; any other account is refused.
- Every method (lab `M*` and historical `H-*`) and every trial is reachable, each method with a detail view.
- Charts:
  - return vs drawdown against the gate
  - equity vs SPY
  - drawdown
  - year by year
  - which conditions pass
  - progress over time
  - families
  - the pipeline and windows as diagrams
- Text is plain-language. Each method shows its hypothesis, expected failure, analysis, verdict and opinion. Insights are grouped as food for thought (data wishes, feature wishes, risks, observations, hypotheses, syntheses).
- A push from a skill session that changes the lab updates the site with no manual step.
- The desktop layout (≥ 1024 px) is the designed one and follows Seer v2 tokens and the icon-only button rule.

**Key Considerations.**
- The web reads Neon only today (`lib/db.ts`). The lab is a SQLite file in git, not in Neon.
- Vercel builds from git on every push to `main`. The CI `paths` filter does not include `lab/**`.
- `ALLOWED_EMAIL` is already `mahfuzh74@gmail.com` (`web/.env.local`, root `.env.local`). `auth.ts`'s `signIn` callback refuses every other account.
- The analysis text in the DB is markdown written by Claude sessions. There is no markdown renderer in `web/`.
- No chart library is installed. Existing charts are hand-built SVG (`leaderboard/page.tsx` `buildChart`).
- SPY's total-return curve is not stored per trial. Trials store `spy_tr_return` and `spy_tr_cagr` only. A month-end SPY total-return curve 1993-01-29 → 2015-10-16 exists in the committed `docs/backtests/2026-10-04-p7a-dev-exploration-curves.csv` (column `spy_tr`).
- `insights.kind` is constrained by a CHECK to five kinds. There is no kind for a batch synthesis.

---

## Analysis Scope

### Explicitly Mentioned Files
- `lab/lab.sqlite`, `engine/src/seer_engine/lab/store.py`, `engine/src/seer_engine/commands/lab.py`, `docs/plans/2026-10-04-method-lab-design.md`

### Discovered Related Files
- `engine/src/seer_engine/lab/{method,runner,seed}.py`; `engine/tests/test_lab_{store,runner,methods}.py`, `engine/tests/labkit.py`
- `.claude/skills/explore-and-experiment-new-method/SKILL.md`, `.claude/skills/sera-the-explorer/SKILL.md`
- `web/auth.ts`, `web/lib/allow.ts`, `web/app/layout.tsx`, `web/app/(app)/layout.tsx`, `web/app/(app)/shell.module.css`
- `web/components/{Nav,AppHeader,TooltipLayer}.tsx`, `web/components/tooltip.ts`, `web/components/Nav.module.css`
- `web/app/globals.css` (Seer v2 tokens, `.icon-btn`, `.sheet`, `.chip`, `.eyebrow`, `.desk-only`)
- `web/app/(app)/leaderboard/page.tsx` (SVG chart pattern), `web/app/signin/page.tsx`
- `web/package.json`, `web/tsconfig.json`, `web/vercel.json`, `.github/workflows/engine-ci.yml`
- `docs/backtests/2026-10-04-p7a-dev-exploration-curves.csv`, `docs/design/Seer v2.dc.html`

---

## Current Dataflow

### Entry Point: a lab write (skill session)

**Location:** `engine/src/seer_engine/commands/lab.py` (`run`, `note`, `idea`, `insight`, `block`, `drop`, `seen`, `stage`)
**Trigger:** `python -m seer_engine lab <cmd>` run by the explore / sera skills
**Next Step:** `seer_engine.lab.store` writes `lab/lab.sqlite` (or `$SEER_LAB_DB`)

### Processing Chain
1. `store.connect(path)` (`store.py`): opens SQLite with `timeout=120`, runs `_SCHEMA` (CREATE TABLE/TRIGGER IF NOT EXISTS), inserts `TRANSITIONS`, and sets `meta.schema_version='1'` with INSERT OR IGNORE. No migration path exists for changing an existing table.
2. `runner.run_method` (`runner.py`): runs candidates through `dev.run_registry`, then calls `store.begin_immediate`, `trial_rows` (computing DSR with N = all dev trials), `insert_trials`, and sets method status.
3. `lab note` → `store.append_analysis` (dated `### YYYY-MM-DD` section appended); `lab insight` → `store.add_insight`.
4. `lab stage` (`commands/lab.py::_stage`): `BEGIN EXCLUSIVE`, `git add lab.sqlite`, rollback.
5. The skill commits and pushes `main`. Vercel builds `web/` on that push. CI runs only if `engine/**`, `db/**`, `web/**` or `.github/workflows/**` changed.

### Data Persistence (lab/lab.sqlite, schema_version 1)
- `methods(id, name, family, parent_id, source_kind, source_ref, hypothesis, status, analysis, verdict, blocked_on, source_sha, created, updated)`. `hypothesis` for lab methods ends with `\n\nExpected failure: …` (`runner._hypothesis`).
- `trials(n, method_id, candidate_id, config_digest, config_text, rules_id, allocator_id, window, start, "end", store_fingerprint, git_sha, run_at, total_return, cagr, max_drawdown, profit_factor, trades, sharpe, exposure, turnover, worst_year, worst_year_return, spy_tr_return, spy_tr_cagr, mar, failed, eligible, dsr, n_trials_at_run, curve_json)`. `curve_json` is `[[iso_date, equity/start], …]` month-end. `failed` is a `"; "`-joined list of `FAILURE_LABELS` plus `"DSR >= 0.95"`.
- `ideas_seen(key, method_id, note, added)`; `insights(id, kind ∈ {observation, hypothesis, data-wish, feature-wish, risk}, title, body, method_id, added)`.
- Current contents: 17 methods (14 `H-*` rejected, `M0001` rejected, `M0002`/`M0003` idea), 58 dev trials, 0 test trials, 4 insights, 54+2 seen keys.

### Exit Points
- `lab export` → gitignored `lab/lab.xlsx`; `lab status`/`show` → stdout. **Nothing reaches the web.**

### Entry Point: the web request
**Location:** `web/app/(app)/layout.tsx`
**Trigger:** GET on any `(app)` route
**Validation:** `currentUser()` (`auth.ts`) → `isAllowed(email, ALLOWED_EMAIL)` (`lib/allow.ts`); `redirect('/signin')` otherwise.
**Next Step:** the page calls `lib/data.ts` → `sql` (`lib/db.ts`, `@neondatabase/serverless`, `DATABASE_URL`).
- `/signin` (`app/signin/page.tsx`): redirects a signed-in user to `/`; `signIn('google', { redirectTo: '/' })`. No `next`/callback parameter.
- Layout: `Nav` renders a desktop rail (`.rail`, `desk-only`, width 104 px, wordmark "Seer.", 4 icon tabs with `data-tip`) and a mobile pill bar. `.main` gets `padding: 0 20px 20px 0` at ≥ 1024 px.
- Charts: `leaderboard/page.tsx` `buildChart` builds SVG `path` strings in a 340×170 viewBox with `preserveAspectRatio="none"` and `vectorEffect="non-scaling-stroke"`; grid lines on `var(--hair)`, zero line dashed `var(--outline)`, colours from `--line-*` tokens.

---

## Key Data Structures

### `store.TrialRow` (`engine/src/seer_engine/lab/store.py`)
Dataclass mirroring the `trials` columns; `TRIAL_COLUMNS` is the field order.

### `store` constants
`SOURCE_KINDS`, `STATUSES`, `TRANSITIONS`, `WINDOWS`, `INSIGHT_KINDS` (5), `DSR_MIN=0.95`, `DSR_LABEL`, `DB_PATH` (env `SEER_LAB_DB`), `COMMITTED_DB`, `XLSX_PATH`, `SCHEMA_VERSION="1"`.

### `seed.py` constants
`P7A_CURVES` (the CSV with `spy_tr`, `spy_price` columns), `P7A_FINGERPRINT`, `P7A_FAMILIES`, `HISTORICAL`.

### Gate constants (`engine/src/seer_engine/backtest/tuning.py`, `dev.py`)
`tuning.MAX_DRAWDOWN` (0.15), `tuning.MIN_PROFIT_FACTOR` (1.3), `dev._MIN_TRADES` (100), `dev.DEV_END` (2015-10-16), `dev.FAILURE_LABELS`.

### Web view-model style (`web/lib/data.ts`)
Typed `export type` objects built by pure helpers in `lib/*.ts`, each with a `*.test.ts` (vitest, no DB).

---

## Dependencies

### Configuration / Environment / External Services
- Vercel: builds `web/` on every push to `main` (Git integration, region `sin1`). Env `ALLOWED_EMAIL`, `AUTH_*`, `DATABASE_URL`.
- Auth.js v5 beta (`next-auth`), Google provider, JWT sessions.
- No chart or markdown dependency in `web/package.json`. Dependencies: next 16, react 19, lucide-react, @neondatabase/serverless, next-auth.
- CI: `.github/workflows/engine-ci.yml`, with `engine` (ruff + pytest) and `web` (`tsc --noEmit` + `vitest run`) jobs; the paths filter excludes `lab/**`.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `INSIGHT_KINDS` | engine/src/seer_engine/lab/store.py | def (CHECK in `_SCHEMA`) | engine |
| `_SCHEMA` / `connect` | engine/src/seer_engine/lab/store.py | def | engine |
| `_stage` | engine/src/seer_engine/commands/lab.py | def | engine |
| `export_xlsx`, `summary_rows` | engine/src/seer_engine/lab/store.py | def | engine |
| `P7A_CURVES` | engine/src/seer_engine/lab/seed.py | config | engine |
| `isAllowed`, `currentUser` | web/lib/allow.ts, web/auth.ts | def | web |
| `AppLayout` | web/app/(app)/layout.tsx | def | web |
| `Nav` / `TABS` | web/components/Nav.tsx | def | web |
| `SignIn` | web/app/signin/page.tsx | def | web |
| `buildChart` | web/app/(app)/leaderboard/page.tsx | def (pattern) | web |
| CI paths | .github/workflows/engine-ci.yml | config | ci |
| skills' commit steps | .claude/skills/{explore-and-experiment-new-method,sera-the-explorer}/SKILL.md | doc | skills |

## Impact Points (files that WILL need changes)
1. `engine/src/seer_engine/lab/store.py`: schema v2 (`synthesis` insight kind via migration), JSON snapshot export. Phase 1.
2. `engine/src/seer_engine/commands/lab.py`: `export-json`; `stage` also writes and stages the snapshot. Phase 1.
3. `engine/tests/test_lab_*.py`: snapshot determinism, a sync guard, migration. Phase 1.
4. `web/data/lab.json` (new, generated). Phase 1.
5. `web/lib/sera/*` (new): types, loader, derivations, markdown. Phase 2.
6. `web/app/sera/*` (new): layout and gate (phase 3); overview (4); methods (5); journal, ideas, how-it-works (6).
7. `web/components/sera/*` (new): shell rail and chart primitives. Phase 3.
8. `web/components/Nav.tsx`, `web/app/signin/page.tsx`: the Sera link and the post-sign-in `next` path. Phase 3.
9. `.github/workflows/engine-ci.yml`, both `SKILL.md`, `docs/ROADMAP.md`, `web/package_readme.md`. Phase 7.

**This document describes. The plan files prescribe.**
