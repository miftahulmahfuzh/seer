# Phase 7: Keep it current: CI, skills, docs

**Plan set:** `SERA_LAB_SITE_PLAN.md`
**Analysis:** `20261004-211729-H54F_code_analyzer.md`
**Satisfies:** R3, R5, R6, R7. R3: new experiments reach seertrade.site/sera with no human step, and CI checks every lab commit. R5: the skills write analysis and opinion in plain language for the owner. R6: Sera's batch synthesis is a real `synthesis` insight and becomes the site's headline. R7 (cross-cutting): the docs describe the whole section.
**Depends on:** Phase 1, 4, 5, 6 (and 2, 3 through them)
**Difficulty:** EASY
**Package:** `.github`, `.claude/skills`, `docs`, `web` (docs only)

---

## Goal

When this phase lands, every lab commit runs CI, so phase 1's sync guard (committed `web/data/lab.json` == export of committed `lab/lab.sqlite`) is checked on commits that touch only `lab/`. Both lab skills commit the database only through `lab stage`, which also regenerates and stages `web/data/lab.json`, so every push to `main` redeploys an up-to-date `/sera`. The skills tell the writer that the owner reads the analysis, insights and synthesis on seertrade.site/sera, so they are written plainly and each analysis ends with a "My opinion:" paragraph. The ROADMAP and `web/package_readme.md` describe the method lab and the Sera site.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:** nothing (docs sections only: ROADMAP `## P8 — Method lab + Sera`, package_readme `## Sera (/sera)`).
**Signature changes:** none.
**Workflow text changes (skills):**
- explore solo mode: commits go through `lab stage`, and the commit includes both `lab/lab.sqlite` and `web/data/lab.json`. A child commits neither.
- explore step 7 (analysis): plain, non-technical language, with a final paragraph that starts `My opinion:`.
- explore step 8 (insights): plain, non-technical language.
- explore and sera: the full engine `pytest` (which includes the snapshot sync guard) runs only after `lab stage` (phase 1 handoff).
- sera: every `lab stage` commit includes `web/data/lab.json`.
- sera step 7: `lab insight --kind synthesis` (was `--kind observation`), and it becomes the headline of seertrade.site/sera.
**CI:** `.github/workflows/engine-ci.yml` `on.push.paths` and `on.pull_request.paths` gain `'lab/**'`.
**Requires (from earlier phases):**
- Phase 1: `python -m seer_engine lab export-json [--out web/data/lab.json]` exists. `lab stage` writes `web/data/lab.json` under the same exclusive lock and `git add`s both `lab/lab.sqlite` and `web/data/lab.json`. `lab insight --kind synthesis` is accepted (schema v2). An engine test asserts committed `web/data/lab.json` == `snapshot_json` of committed `lab/lab.sqlite`. `web/data/lab.json` is committed.
- Phase 2: `web/lib/sera/{types,lab,derive,glossary,markdown}.ts` (+ tests).
- Phase 3: `web/lib/sera/access.ts` (`SERA_EMAIL`, `isSeraUser`), `web/app/sera/layout.tsx` (+ `sera.module.css`, `not-found.tsx`), `web/components/sera/{SeraNav,PageHeader,Section,Term}.tsx`, `web/components/sera/charts/{scale.ts,LineChart,ScatterChart,BarChart,Legend}.tsx`, the Sera link on the desktop rail in `components/Nav.tsx`, and the sign-in `next` path.
- Phases 4–6: the routes `/sera`, `/sera/methods`, `/sera/methods/[id]`, `/sera/journal`, `/sera/ideas`, `/sera/how`, and `web/components/sera/diagrams/{Pipeline,Windows}.tsx`.
**Leaves alone (owned by others):** all code under `engine/`, all of `web/` except `web/package_readme.md`, and `lab/lab.sqlite`. The method-lab design doc `docs/plans/2026-10-04-method-lab-design.md` is out of scope (see Handoffs).

## Files

| File | Action | What changes |
|---|---|---|
| `.github/workflows/engine-ci.yml:4-15` | modify | add `'lab/**'` to the push and pull_request path filters |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md:32,36-37,76-87,92,96,116,131,135-143` | modify | solo commits go through `lab stage` (both files); run the full pytest only after `lab stage`; plain language plus `My opinion:` in the analysis; plain insights; quick reference |
| `.claude/skills/sera-the-explorer/SKILL.md:33-35,41-42,53,77,81-88,101` | modify | `lab stage` commits include `web/data/lab.json`; preflight tests run after `lab stage`; the batch insight is `--kind synthesis` and becomes the site's headline |
| `docs/ROADMAP.md:73` (between the P7b and P4 sections) | modify | new `## P8 — Method lab + Sera` section |
| `web/package_readme.md:4,15-21,23-69,232-249,272-277,279-292` | modify | Last Updated; responsibilities; layout; new `## Sera (/sera)` section; config/test lines; gotchas |

Line numbers are for `origin/main` @ `c138b08`. None of phases 1–6 edits these five files, so the numbers still hold after they land.

## Implementation Steps

### Step 0: Confirm what the earlier phases produced
**File:** none (read-only)
**Change:** These docs describe merged code, so check the facts first:
```bash
WT=/home/miftah/.worktrees/seer/sera-lab-site
PY="env -u SEER_LAB_DB PYTHONPATH=$WT/engine/src /home/miftah/seer/engine/.venv/bin/python"   # a worktree has no venv; SEER_LAB_DB must be unset
cd $WT/engine
$PY -m seer_engine lab --help | grep -E 'export-json|stage'
$PY -m seer_engine lab insight --help | grep -o synthesis
cd $WT
ls web/data/lab.json web/lib/sera web/components/sera web/components/sera/charts web/components/sera/diagrams
find web/app/sera -type f | sort
```
The reconciled plans ship `app/sera/overview.ts`, `app/sera/methods/view.ts`, `app/sera/{journal,ideas,how}/view.ts`, `lib/sera/{types,lab,derive,glossary,markdown,fixture,access,gate}.ts` and `components/sera/{SeraNav,PageHeader,Section,Stat,Term}.tsx`. If a file name still differs from the names used in Steps 6–7, make the `web/package_readme.md` layout block match the tree. Do not change the tree to fit the doc. If `lab stage` does not stage `web/data/lab.json`, stop: phase 1 is not merged, and this phase must not land before it.
**Impact:** none.

### Step 1: CI runs on lab-only commits
**File:** `.github/workflows/engine-ci.yml:3-15`
**Change:** Add `'lab/**'` to both path filters. A lab-only commit (`lab/lab.sqlite` + `web/data/lab.json`) already matches `web/**` through the JSON. The explicit `lab/**` also covers a commit that wrongly changes only the database, which is exactly what the sync guard has to catch.
**Old:**
```yaml
on:
  push:
    paths:
      - 'engine/**'
      - 'db/**'
      - 'web/**'
      - '.github/workflows/**'
  pull_request:
    paths:
      - 'engine/**'
      - 'db/**'
      - 'web/**'
      - '.github/workflows/**'
  workflow_dispatch:
```
**New:**
```yaml
on:
  push:
    paths:
      - 'engine/**'
      - 'db/**'
      - 'lab/**'
      - 'web/**'
      - '.github/workflows/**'
  pull_request:
    paths:
      - 'engine/**'
      - 'db/**'
      - 'lab/**'
      - 'web/**'
      - '.github/workflows/**'
  workflow_dispatch:
```
**Impact:** CI now runs on database-only commits, so a lab commit without a matching `web/data/lab.json` fails the engine job (phase 1's sync guard). Nothing else changes.

### Step 2: Explore skill: commits go through `lab stage`
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:32`
**Old:**
```markdown
| commits | method file, then `lab/lab.sqlite`, to `main` | method file only; **never commit `lab/lab.sqlite`** (the coordinator does) |
```
**New:**
```markdown
| commits | method file, then `lab stage` (`lab/lab.sqlite` + `web/data/lab.json`), to `main` | method file only; **never commit `lab/lab.sqlite` or `web/data/lab.json`** (the coordinator does) |
```

**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:92`
**Old:**
```markdown
    - Solo: commit and push `lab/lab.sqlite` with anything new, then give a short report: idea, result vs SPY, verdict, insight, next idea, N, test looks.
```
**New:**
```markdown
    - Solo: run `lab stage`. It takes the database's write lock, regenerates `web/data/lab.json`
      (the snapshot seertrade.site/sera is built from) and `git add`s both files. Never
      `git add lab/lab.sqlite` by hand. Commit both files and push; Vercel redeploys the site from
      that push. Then give a short report: idea, result vs SPY, verdict, insight, next idea, N, test looks.
```

**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:96`
**Old:**
```markdown
      is gone, the database already holds everything, so just stop. Never commit `lab/lab.sqlite`.
```
**New:**
```markdown
      is gone, the database already holds everything, so just stop. Never commit `lab/lab.sqlite`
      or `web/data/lab.json`.
```

**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:116`
**Old:**
```markdown
   Commit, push, verify. **Real money stays out of scope:** design §1 needs ≥ 3 months and
```
**New:**
```markdown
   Commit (the database through `lab stage`), push, verify. **Real money stays out of scope:** design §1 needs ≥ 3 months and
```

**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:36-37`
**Old:**
```markdown
Run every command from the checkout root (`engine/` for pytest). In child mode, `export` both
variables first in every shell.
```
**New:**
```markdown
Run every command from the checkout root (`engine/` for pytest). In child mode, `export` both
variables first in every shell.

`tests/test_lab_snapshot.py` checks that `web/data/lab.json` is the export of `lab/lab.sqlite`.
After any lab write (`run`, `note`, `insight`, `idea`, …) it fails until `lab stage` regenerates
the JSON, by design. So solo: run the full engine `pytest` only **after** `lab stage`. The
contract test in step 5 (`tests/test_lab_methods.py`) is unaffected. A child never stages: its
own checkout's database is untouched (it writes the shared one through `SEER_LAB_DB`), so the
check stays green there, and `lab stage` writes the JSON into the checkout that owns the database.
```

**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:131`
**Old:**
```markdown
| "Child: commit lab.sqlite too" | Never. A binary file committed by two sessions is a conflict nobody can merge. |
```
**New:**
```markdown
| "Child: commit lab.sqlite too" | Never, and never `web/data/lab.json` either. A binary file committed by two sessions is a conflict nobody can merge. |
| "Solo: `git add lab/lab.sqlite` is quicker" | Always `lab stage`. It is the only thing that keeps `web/data/lab.json` in sync, and CI fails a lab commit without it. |
```
**Impact:** Text only. The solo commit path now matches invariant 2.

### Step 3: Explore skill: plain analysis with an explicit opinion, plain insights
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:76-87`
**Old:**
```markdown
7. **Analyze honestly** in a scratch file, then `lab note MNNNN --file F --verdict "<one line>"`.
   The page at seertrade.site/sera shows this to the owner, so write plainly. Cover:
   - result vs total-return SPY, and which conditions failed and by how much
   - DSR at N
   - worst year and when the drawdown hit
   - **why**: the mechanism, not just the numbers
   - whether the hypothesis held and whether the expected failure happened
   - comparison with the parent or near misses
   - your **opinion**: is this direction worth more trials?
8. **Journal at least one insight**: `lab insight --kind observation|hypothesis|data-wish|feature-wish|risk
   --title … --body … --method MNNNN`. Useful kinds: what this taught about markets, data you
   wish the lab had, a feature that would make the search better, a risk you noticed.
```
**New:**
```markdown
7. **Analyze honestly** in a scratch file, then `lab note MNNNN --file F --verdict "<one line>"`.
   The owner reads the analysis and the verdict on seertrade.site/sera (the method's page). He is
   not a quant. Write plainly: short sentences, everyday words, numbers with their meaning ("lost
   at most 13% from a peak, under the 15% limit"), and a plain gloss on any term you can't avoid
   (CAGR, drawdown, profit factor, DSR). Markdown is fine. Cover:
   - result vs total-return SPY, and which conditions failed and by how much
   - DSR at N, in words: how likely the result is real rather than luck after N tries
   - worst year and when the drawdown hit
   - **why**: the mechanism, not just the numbers
   - whether the hypothesis held and whether the expected failure happened
   - comparison with the parent or near misses
   - end with a paragraph that starts **`My opinion:`**. Say plainly whether this direction is
     worth more trials, what you would try next, and why. Commit to a view; no hedging.
   The verdict is one plain line the site shows next to the method's name.
8. **Journal at least one insight**: `lab insight --kind observation|hypothesis|data-wish|feature-wish|risk
   --title … --body … --method MNNNN`. Useful kinds: what this taught about markets, data you
   wish the lab had, a feature that would make the search better, a risk you noticed. The owner
   reads these on seertrade.site/sera (Journal and Ideas) as food for thought. Write them as plainly
   as the analysis: a title that says the point, and a body that says why it matters and what to do about it.
   (`synthesis` is Sera's batch summary; a single run never uses it.)
```
**Impact:** Text only. The analysis and insights shown on `/sera/methods/[id]`, `/sera/journal` and `/sera/ideas` are written for the owner.

### Step 4: Explore skill: quick reference
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:135-143`
**Old:**
````markdown
```
lab status | lab show M0007 | lab next-id | lab seen --find momentum
lab run M0007                     # needs a committed method file
lab note M0007 --file /tmp/a.md --verdict "..."
lab insight --kind data-wish --title "Quarterly fundamentals" --body "..." --method M0007
lab idea --name "..." --family ... --source-kind variation --parent M0007 --hypothesis "..."
lab block M0012 --on "quarterly fundamentals"   lab drop M0013 --why "duplicate of M0004"
lab export                        # lab/lab.xlsx (gitignored)
```
````
**New:**
````markdown
```
lab status | lab show M0007 | lab next-id | lab seen --find momentum
lab run M0007                     # needs a committed method file
lab note M0007 --file /tmp/a.md --verdict "..."
lab insight --kind data-wish --title "Quarterly fundamentals" --body "..." --method M0007
lab idea --name "..." --family ... --source-kind variation --parent M0007 --hypothesis "..."
lab block M0012 --on "quarterly fundamentals"   lab drop M0013 --why "duplicate of M0004"
lab stage                         # solo only: writes web/data/lab.json, git-adds it and lab/lab.sqlite
lab export                        # lab/lab.xlsx (gitignored)
lab export-json                   # web/data/lab.json without staging (lab stage already does this)
```
````
**Impact:** Text only.

### Step 5: Sera skill: `lab stage` commits include the snapshot; the synthesis kind
**File:** `.claude/skills/sera-the-explorer/SKILL.md:33-35`
**Old:**
```markdown
Only Sera commits `lab/lab.sqlite`, and always through `lab stage`, which takes the write lock
so a child's half-written transaction is never committed. Children commit only their method
files, straight to `main`. These are distinct new files, so a rebase never conflicts.
```
**New:**
```markdown
Only Sera commits `lab/lab.sqlite`, and always through `lab stage`, which takes the write lock
so a child's half-written transaction is never committed. Under the same lock it regenerates
`web/data/lab.json`, the snapshot seertrade.site/sera is built from, and stages both files.
**Every `lab stage` commit includes `web/data/lab.json`.** CI fails a database commit without it,
and Vercel redeploys the site from each push. Children commit only their method files,
straight to `main`. These are distinct new files, so a rebase never conflicts.
```

**File:** `.claude/skills/sera-the-explorer/SKILL.md:41-42`
**Old:**
```markdown
2. **Preflight** in `$REPO`: `git pull --rebase --autostash`. Lab tests green
   (`cd engine && .venv/bin/python -m pytest -q tests/test_lab_*.py`). `engine/.research/`
```
**New:**
```markdown
2. **Preflight** in `$REPO`: `git pull --rebase --autostash`. Lab tests green
   (`cd engine && .venv/bin/python -m pytest -q tests/test_lab_*.py`). The snapshot check in
   `test_lab_snapshot.py` fails whenever `lab/lab.sqlite` changed without `lab stage` (for example
   after an interrupted batch). If that is the only failure, run `lab stage`, commit both files,
   push, and run the tests again. Always test after staging, never before. `engine/.research/`
```

**File:** `.claude/skills/sera-the-explorer/SKILL.md:53`
**Old:**
```markdown
   - Then `lab stage` + commit + push ("lab: sera <stamp> reserves M00xx, M00yy").
```
**New:**
```markdown
   - Then `lab stage` + commit (`lab/lab.sqlite` and `web/data/lab.json`) + push ("lab: sera <stamp> reserves M00xx, M00yy").
```

**File:** `.claude/skills/sera-the-explorer/SKILL.md:77`
**Old:**
```markdown
   - `lab stage` + commit + push the database ("lab: M00xx <verdict>").
```
**New:**
```markdown
   - `lab stage` + commit + push the database and its snapshot, `lab/lab.sqlite` and `web/data/lab.json` ("lab: M00xx <verdict>").
```

**File:** `.claude/skills/sera-the-explorer/SKILL.md:81-88`
**Old:**
```markdown
7. **Synthesize** when num-methods children are closed out. Add **one batch insight**
   (`lab insight --kind observation --title "Sera <stamp>: <theme>" --body …`) covering:
   - what the batch taught across methods
   - which directions look alive and which look dead
   - what data or features would unlock the most
   - what the next batch should try

   Then `lab stage`, commit, push. End with a short report:
```
**New:**
```markdown
7. **Synthesize** when num-methods children are closed out. Add **one batch insight**
   (`lab insight --kind synthesis --title "Sera <stamp>: <theme>" --body …`). The newest
   synthesis is the headline of seertrade.site/sera, the first thing the owner reads, so write it
   plainly, in everyday words. Cover:
   - what the batch taught across methods
   - which directions look alive and which look dead
   - what data or features would unlock the most
   - what the next batch should try

   Then `lab stage`, commit (`lab/lab.sqlite` and `web/data/lab.json`), push. The site picks the
   synthesis up from that push with no other step. End with a short report:
```

**File:** `.claude/skills/sera-the-explorer/SKILL.md:101`
**Old:**
```markdown
| "`git add lab/lab.sqlite`" | Always `lab stage`. A child may be mid-write. |
```
**New:**
```markdown
| "`git add lab/lab.sqlite`" | Always `lab stage`. A child may be mid-write, and only `lab stage` keeps `web/data/lab.json` in sync. |
```
**Impact:** Text only. The batch synthesis becomes a `synthesis` row, which phase 4's overview headline and phase 6's "Batch summaries" journal group look for. Nothing else in the workflow changes.

### Step 6: ROADMAP: P8 section
**File:** `docs/ROADMAP.md:73`. Insert after the last P7b bullet (line 72, `  - new ideas appended to the registry under D6 …`) and its blank line, before `## P4 — Nightly forward paper trading …` (line 74).
**Old** (the anchor, lines 72–74):
```markdown
  - new ideas appended to the registry under D6 (each committed before its dev run, every try reported) in a new handover; the answers to the owner-input questions (ETFs, fractional shares, market-on-open, fees, leverage, T-bills) may make more candidates eligible

## P4 — Nightly forward paper trading · paper-only (owner option (b), 2026-10-04); no real-money recommendations; §1 unchanged · code landed 2026-10-04; the clock starts with the first scheduled nightly after the merge ([runbook](runbooks/paper-trading.md))
```
**New:**
```markdown
  - new ideas appended to the registry under D6 (each committed before its dev run, every try reported) in a new handover; the answers to the owner-input questions (ETFs, fractional shares, market-on-open, fees, leverage, T-bills) may make more candidates eligible

## P8 — Method lab + Sera · lab running since 2026-10-04 (no method eligible yet); Sera site at [seertrade.site/sera](https://seertrade.site/sera) ([design](plans/2026-10-04-method-lab-design.md))
- The search goes on after P7a as a **method lab**: `lab/lab.sqlite`, a committed SQLite file (never Neon) with tables `methods`, `trials` (each with its month-end equity curve), `ideas_seen` and `insights`. Trials and insights are append-only (triggers). It was seeded with P7a's 54 trials as 14 historical methods (`H-*`), and every new trial counts toward N, the number of tries that deflates each result (DSR ≥ 0.95 at N joins the five D8 hurdles). Access: `engine/src/seer_engine/lab/store.py`; CLI: `python -m seer_engine lab …`; schema v2 adds the `synthesis` insight kind
- A method is one pre-registered file, `engine/src/seer_engine/lab/methods/mNNNN_<slug>.py`, committed and pushed before `lab run` touches the dev window (1993 → 2015-10-16). The test window (2015-10-19 → today) is spent one counted look at a time, only through promotion of a `dev-eligible` method. Design §1 and the D8 hurdles do not move
- Two skills, **no human in the loop**: `/explore-and-experiment-new-method` explores one idea end to end (pre-register, run, plain-language analysis ending in "My opinion:", at least one insight, at least one queued idea). `/sera-the-explorer <n>` runs n of them in parallel (at most 4 at a time, one worktree and tmux window each), promotes eligible methods herself, and closes each batch with one `synthesis` insight
- **M0001** (momentum scaled by its own realized volatility, 4 variants): the first lab trials to pass max DD ≤ 15%, PF ≥ 1.3 and ≥ 100 trades together (best `M0001-TV12`: max DD 12.9%, PF 2.27, 1,130 trades). They failed only on beating SPY: CAGR 7.6% vs total-return SPY 7.9%, DSR 0.90 at N = 58. Rejected; M0002 and M0003 (asymmetric and dynamic momentum scaling) queued
- **Sera site** (`/sera`, desktop-first, private to `mahfuzh74@gmail.com`; any other account gets a 404): Overview (latest synthesis, every trial against the gate, hurdle funnel, progress, luck bar, families), Methods and one page per method (charts vs SPY, the analysis and opinion, every trial's detail), Journal, Ideas and How it works. It reads `web/data/lab.json`, which `lab stage` regenerates under the database's write lock and stages with it on every lab commit; Vercel deploys it on the push to `main`. CI runs on `lab/**` and an engine test fails any commit whose JSON does not match its database
- **Done when:** never, by design: the lab keeps searching. It feeds P7b-style test looks and the paper roster only through promotion

## P4 — Nightly forward paper trading · paper-only (owner option (b), 2026-10-04); no real-money recommendations; §1 unchanged · code landed 2026-10-04; the clock starts with the first scheduled nightly after the merge ([runbook](runbooks/paper-trading.md))
```
**Impact:** Docs only. Before writing the M0001 numbers, check them against `$PY -m seer_engine lab show M0001` (Step 0's command). They were taken from the DB at `c138b08`: TV12 CAGR 0.0762, max DD 0.1292, PF 2.27, 1,130 trades, SPY TR CAGR 0.0792, DSR 0.90; N = 58.

### Step 7: `web/package_readme.md`: Sera documentation
Six edits. Every file name in the layout block must match Step 0's listing.

**7a. Last Updated** (`web/package_readme.md:4`)
**Old:**
```markdown
**Last Updated**: 2026-10-04 (P1-WEB-DX8D, paper-trading-ship phase 12: roster-driven Leaderboard with SPY crown, per-research-strategy six-item checklist via `StrategySwitch` with an honest score line, and a "Month by month" sheet; helpers in `leaderboard/view.ts`)
```
**New:**
```markdown
**Last Updated**: 2026-10-04 (sera-lab-site phase 7: the private `/sera` method-lab section, which reads the committed snapshot `data/lab.json`; SERA_EMAIL gate; `lib/sera`, `components/sera`)
```

**7b. Overview / responsibilities** (`web/package_readme.md:8-21`). Replace the paragraph at 8-13 and add one bullet after line 21.
**Old:**
```markdown
`seer-web` is Seer's private web app: a Next.js 16 / React 19 front end that reads the Neon
(Postgres) tables written by the Python engine (`engine/`) and shows tonight's picks, open
holdings, closed trades and the strategy leaderboard. It never trades and never computes
signals; it is a read model over `strategies`, `runs`, `orders`, `book_positions`,
`book_targets`, `book_trades`, `equity_snapshots`, `paper_state`, `bars` and `fx_rates`, plus one
write (`action_dismissals`).
```
**New:**
```markdown
`seer-web` is Seer's private web app: a Next.js 16 / React 19 front end that reads the Neon
(Postgres) tables written by the Python engine (`engine/`) and shows tonight's picks, open
holdings, closed trades and the strategy leaderboard. It never trades and never computes
signals; it is a read model over `strategies`, `runs`, `orders`, `book_positions`,
`book_targets`, `book_trades`, `equity_snapshots`, `paper_state`, `bars` and `fx_rates`, plus one
write (`action_dismissals`). A second, separate section, **Sera** (`/sera`), shows the method lab
from a committed JSON snapshot (`data/lab.json`), not from Neon.
```
**Old** (line 21):
```markdown
- Migrations runner shared with the engine (`scripts/migrate.mjs`) and a demo seeder (`scripts/seed-demo.mjs`)
```
**New:**
```markdown
- Migrations runner shared with the engine (`scripts/migrate.mjs`) and a demo seeder (`scripts/seed-demo.mjs`)
- Sera (`/sera`): the method lab's whole record (every method, trial, analysis, insight and idea) with charts and plain-language explanations, for `SERA_EMAIL` only (see [Sera](#sera-sera))
```

**7c. Layout** (`web/package_readme.md:34-69`). Insert the Sera tree into the code block.
**Old** (lines 48-49):
```markdown
      leaderboard/view.test.ts  vitest suite for view.ts
  components/               AppHeader (eye mark left of the titles, mobile only), Nav, CopyButton, RefreshButton, WhyToggle, TooltipLayer, tooltip
```
**New:**
```markdown
      leaderboard/view.test.ts  vitest suite for view.ts
    sera/                   the method lab (desktop-first; SERA_EMAIL only; reads data/lab.json, never Neon)
      layout.tsx            gate (signed out -> /signin?next=…, other account -> notFound) + Sera rail shell
      sera.module.css, not-found.tsx
      page.tsx              Overview: latest synthesis, KPI tiles, trial scatter vs the gate, hurdle funnel, progress, luck bar, families, latest methods
      overview.ts (+ test)  pure shaping of the snapshot into chart-kit props; overview.module.css
      methods/page.tsx      every method with its best variant, filter ?show=all|lab|historical|alive
      methods/[id]/page.tsx one method: idea, expected failure, verdict, variants vs the six conditions, growth vs SPY, drawdown, year by year, analysis, insights, trial detail
      methods/view.ts (+ test), methods.module.css, [id]/method.module.css
      journal/page.tsx      insights grouped by kind, ?kind= filter, newest first (+ view.ts, test, journal.module.css)
      ideas/page.tsx        backlog (#backlog), blocked-on-data wishlist (#blocked), reading list from ideasSeen (#reading) (+ view.ts, test, ideas.module.css)
      how/page.tsx          pipeline and windows diagrams, hurdles from snapshot.gate, honesty rules, data, glossary (+ view.ts, test, how.module.css)
      Every page calls requireSera('<its path>') first; the layout gates too.
  data/
    lab.json                GENERATED by `python -m seer_engine lab stage` / `lab export-json`; never edit by hand
  components/               AppHeader (eye mark left of the titles, mobile only), Nav, CopyButton, RefreshButton, WhyToggle, TooltipLayer, tooltip
    sera/                   SeraNav (icon-only rail tabs), PageHeader, Section (+ SectionGrid), Stat, Term (term + definition -> data-tip)
      charts/               scale.ts (+ test), parts, LineChart, ScatterChart, BarChart, Legend (+ charts.test.tsx): hand-built SVG, plain props only
      diagrams/             geometry.ts (+ test), Pipeline, Windows (How it works)
```
**Old** (line 64):
```markdown
    allow.ts                isAllowed                                              (pure)
```
**New:**
```markdown
    allow.ts                isAllowed, safeNext (internal ?next= paths only)       (pure)
    sera/                   the lab snapshot's types, loader and pure derivations
      types.ts              LabSnapshot, LabMethod, LabTrial, LabInsight, LabSeen (the data/lab.json contract)
      lab.ts                imports ../../data/lab.json (relative: vitest has no @/ alias), cast once; methodById, trialsOf, insightsOf, childrenOf
      derive.ts             gate checks per trial, misses, closest to eligible, best variant, funnel, progress, families, SPY rebase, drawdown, calendar years (pure)
      glossary.ts           plain-language terms, status and insight-kind labels   (pure)
      markdown.ts           escape-first markdown -> HTML for analysis text        (pure)
      access.ts             SERA_EMAIL, isSeraUser                                 (pure)
      gate.ts               requireSera(next): the /sera gate (server only)
      fixture.ts            test-only builders
      *.test.ts             vitest suites
```

**7d. New section** (`web/package_readme.md`: insert after the Data Flow section, before `## Dependencies` at line 251).
**Old** (the anchor, lines 249–251):
```markdown
- Leaderboard: `leaderboard`, `runStatus`, then `monthly(pick.id, run.sessionDate)`. Every card, chart line and legend entry comes from the roster via `looks`. The big figure is the champion (crowned; SPY today); the second figure is the best research strategy on paper while the champion is the benchmark, else SPY. The checklist and month sheet follow `pick = selectStrategy(researchOf(roster), ?s)`; a `StrategySwitch` over research strategies shows when there are two or more (SPY is not selectable here, it is the SPY column). Checklist is `checklist(pick.metrics, spy.totalReturn, pick.strategy.gate)` scored by `scoreOf`; the gate's `note` prints under it. "Month by month" lists the since-start row then months newest first, with a `CircleDashed` partial-month marker while the next session is in that month.

## Dependencies
```
**New:**
```markdown
- Leaderboard: `leaderboard`, `runStatus`, then `monthly(pick.id, run.sessionDate)`. Every card, chart line and legend entry comes from the roster via `looks`. The big figure is the champion (crowned; SPY today); the second figure is the best research strategy on paper while the champion is the benchmark, else SPY. The checklist and month sheet follow `pick = selectStrategy(researchOf(roster), ?s)`; a `StrategySwitch` over research strategies shows when there are two or more (SPY is not selectable here, it is the SPY column). Checklist is `checklist(pick.metrics, spy.totalReturn, pick.strategy.gate)` scored by `scoreOf`; the gate's `note` prints under it. "Month by month" lists the since-start row then months newest first, with a `CircleDashed` partial-month marker while the next session is in that month.

## Sera (/sera)

The method lab, shown: every method and trial the lab has run (the 14 historical `H-*` methods
seeded from P7a and every lab `M*` method), with charts and plain-language explanations, the
analysis and opinion on each method, and the insights journal. It is desktop-first. Below
1024 px the pages stack in one column, readable but not designed.

### Routes

| Route | What it shows |
|---|---|
| `/sera` | Overview: the latest `synthesis` insight as the headline (else the latest insight); KPI tiles; every dev trial as max DD vs CAGR minus SPY, with the pass zone shaded; how many trials pass each hurdle; progress over trial number; each trial's DSR vs the 0.95 line; families; latest methods |
| `/sera/methods` | every method with status, family, source and best variant (CAGR vs SPY, max DD, PF, trades, DSR, conditions passed n/6) and verdict; icon-only filter `?show=all\|lab\|historical\|alive` |
| `/sera/methods/[id]` | one method: idea, what could go wrong, verdict, parent and children, variants against the six conditions, growth of 1 vs total-return SPY, drawdown, year by year, its variants against the gate, the rendered analysis, related insights, each trial's full technical detail. `generateStaticParams` covers every method; unknown id -> `notFound()` |
| `/sera/journal` | insights grouped as Batch summaries (synthesis), What we learned, Ideas worth testing, Data we wish we had, Features to build, Risks we see; `?kind=<kind>` filter (e.g. `/sera/journal?kind=data-wish`), newest first |
| `/sera/ideas` | the backlog (`idea`, `#backlog`), ideas blocked on data (a data wishlist, `#blocked`), and the reading list from `ideasSeen` (`url:` keys as links, `concept:` keys as tags, `#reading`) |
| `/sera/how` | the pipeline and time-window diagrams, each hurdle with its threshold from `snapshot.gate`, the honesty rules, the data the lab has and lacks, and the glossary |

### Access gate

`requireSera(next)` (`lib/sera/gate.ts`) guards every `/sera/**` route on top of the app-wide
`ALLOWED_EMAIL` sign-in. `app/sera/layout.tsx` calls it, and so does every page with its own path,
because a layout is not re-run on client-side navigation. Signed out ->
`redirect('/signin?next=<path>')`; `/signin` honours `?next=` through `safeNext` (`lib/allow.ts`,
internal paths only), so sign-in returns there. Signed in as anyone but `SERA_EMAIL` -> `notFound()`,
so the section's existence is never revealed. `SERA_EMAIL = 'mahfuzh74@gmail.com'` is a constant in `lib/sera/access.ts`, not an env
var; `isSeraUser(email)` matches it trimmed and case-insensitively. The same check shows the Sera
link on Seer's desktop rail (`components/Nav.tsx`).

### Data source and how it stays current

```
skill session (explore / sera) -> lab/lab.sqlite
  -> python -m seer_engine lab stage   (exclusive lock: writes web/data/lab.json, git-adds both)
  -> commit + push main -> CI (engine sync guard, web tsc + vitest) and Vercel production build
  -> lib/sera/lab.ts bundles data/lab.json at build time -> /sera pages (rendered per request, since the gate reads the session)
```

- `data/lab.json` is the `LabSnapshot` contract (`lib/sera/types.ts`): `version`, `asOf`, `gate`,
  `data`, `summary`, `benchmark` (month-end SPY total-return and price, 1993 → 2015-10-16),
  `methods`, `trials` (with month-end curves), `insights`, `ideasSeen`. It is deterministic: the
  same database always gives the same bytes, and it holds no wall-clock time.
- No human step: every lab commit goes through `lab stage`, so the JSON travels with the database.
  An engine test fails any commit whose JSON differs from `lab export-json` of the committed
  database, and CI runs on `lab/**` as well as `web/**`.
- The web never computes a trading result. It only reshapes and draws the snapshot. Gate
  thresholds come from `snapshot.gate`, never from numbers in web code.

### Code layout

- `lib/sera/`: `types.ts` (contract), `lab.ts` (the one import of the JSON), `derive.ts` (pure
  reshaping for the charts and tables; pass/fail always read from the engine's `trial.failed`),
  `glossary.ts` (plain definitions, status and kind labels), `markdown.ts` (escape-first renderer
  for analysis text: headings, paragraphs, emphasis, code, lists, pipe tables, http(s) links),
  `access.ts` (`SERA_EMAIL`, `isSeraUser`), `gate.ts` (`requireSera`). Tested modules use relative
  imports, because vitest has no `@/` alias; pages import through `@/`.
- `components/sera/`: the shell (`SeraNav` rail with wordmark "Sera.", icon-only tabs, a link back
  to Seer), `PageHeader`, `Section` (a sheet with eyebrow, title and a one-sentence plain caption),
  `Stat`, `Term` (takes `term` + `definition`; pages feed it from `GLOSSARY`), `charts/`
  (hand-built SVG from plain props, Seer v2 colour tokens as CSS strings, `data-tip` on points) and
  `diagrams/` (Pipeline, Windows).
- Pages under `app/sera/` are server components. Each has a pure, tested helper module
  (`overview.ts` or `view.ts`) that shapes `lab` into chart-kit props. No chart or markdown
  dependency was added. Tooltips over 48 characters wrap (`components/tooltip.ts`).

## Dependencies
```

**7e. Configuration and tests** (`web/package_readme.md:274,277`)
**Old** (line 274):
```markdown
- `DATABASE_URL` (app, pooled HTTP), `DATABASE_URL_UNPOOLED` (scripts), `ALLOWED_EMAIL`, NextAuth Google credentials. Scripts read `web/.env.local` via `node --env-file`.
```
**New:**
```markdown
- `DATABASE_URL` (app, pooled HTTP), `DATABASE_URL_UNPOOLED` (scripts), `ALLOWED_EMAIL`, NextAuth Google credentials. Scripts read `web/.env.local` via `node --env-file`.
- Sera needs no env var: `SERA_EMAIL` is a constant (`lib/sera/access.ts`), and its data is the committed `data/lab.json`. Regenerate the JSON with `python -m seer_engine lab stage` (writes and stages it with `lab/lab.sqlite`) or `lab export-json` (writes only). In a worktree, run them as `env -u SEER_LAB_DB PYTHONPATH=<worktree>/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine …`.
```
**Old** (line 277):
```markdown
- `npm test`: vitest over the pure modules (`strategy`, `metrics`, `vetoes`, `monthly`, `slots`, `session`, `format`, `allow`), `components/roster` and `app/(app)/leaderboard/view`.
```
**New:**
```markdown
- `npm test`: vitest over the pure modules (`strategy`, `metrics`, `vetoes`, `monthly`, `slots`, `session`, `format`, `allow`), `components/roster`, `app/(app)/leaderboard/view`, `lib/sera/*`, `components/sera/charts/scale` and the Sera page helpers.
```

**7f. Gotchas** (`web/package_readme.md:292`)
**Old:**
```markdown
- `StrategySwitch` takes `href` as a function, so it must stay a server component (functions cannot cross into a client component).
```
**New:**
```markdown
- `StrategySwitch` takes `href` as a function, so it must stay a server component (functions cannot cross into a client component).
- `data/lab.json` is generated. Never edit it by hand or commit it without its database: the engine sync guard fails the build. A lab change reaches `/sera` only by being committed and pushed, because the snapshot is bundled at build time.
- `/sera` for any account but `SERA_EMAIL` is a 404 by design, not a bug. A signed-out visitor is sent to `/signin?next=<the /sera path>`.
- `lib/sera/*` and the page helper modules import each other relatively: vitest has no `@/` alias. Only `page.tsx` files and components use `@/`.
- Sera's markdown renderer escapes HTML first. Analysis text is never trusted as HTML.
```
**Impact:** Docs only.

## Verification

**Build:** none (no code changed). YAML check: `python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/engine-ci.yml')); on=d[True] if True in d else d['on']; assert 'lab/**' in on['push']['paths'] and 'lab/**' in on['pull_request']['paths']; print('ok')"`
**Tests:** unchanged suites must still pass. Engine: `cd $WT/engine && /home/miftah/seer/engine/.venv/bin/ruff check src tests && env -u SEER_LAB_DB PYTHONPATH=$WT/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q` (a worktree has no venv; `SEER_LAB_DB` must be unset). Web: `cd $WT/web && npm ci && npx tsc --noEmit && npx vitest run` (never symlink main's `node_modules`).
**Manual check:**
- `grep -n "kind synthesis" .claude/skills/sera-the-explorer/SKILL.md` gives one hit; `grep -n "kind observation --title \"Sera" .claude/skills/sera-the-explorer/SKILL.md` gives none.
- `grep -n "My opinion:" .claude/skills/explore-and-experiment-new-method/SKILL.md` gives one hit.
- `grep -n "web/data/lab.json" .claude/skills/*/SKILL.md` gives hits in both skills.
- `grep -in "after staging\|only \*\*after\*\* .lab stage" .claude/skills/*/SKILL.md` gives a hit in each skill (tests run after `lab stage`).
- Every path in the package_readme layout block exists: `ls` each one.
- `lab show M0001` agrees with the ROADMAP's M0001 numbers.
- After the push, the CI run for the merge commit is green.
**Exit criteria:** CI's path filter includes `lab/**` for push and pull_request. Both skills commit the database only through `lab stage`, with `web/data/lab.json`. The explore analysis requires a `My opinion:` paragraph in plain language, and its insights are plain. Sera's synthesis uses `--kind synthesis`. ROADMAP has the P8 section, and `web/package_readme.md` documents `/sera` and matches the merged tree. CI is green.

## Handoffs

- **`docs/plans/2026-10-04-method-lab-design.md`** (not in this phase's scope): §1 line 36 lists `lab export` (xlsx) as the only view, and §6 says only Sera commits `lab/lab.sqlite`. Neither mentions `web/data/lab.json`, `lab export-json` or the `synthesis` kind. A follow-up revision note (§7) should add them. Left for a later docs pass, or for phase 1 if the reconciler prefers (it owns the engine side of those facts). R3.
- **`engine/package_readme.md`** (checked by the reconciler): it does not document the `lab` CLI at `c138b08`, so nothing there goes stale. No phase edits it.
- **Existing synthesis-like insights** (confirmed by the reconciler): phase 1's migration copies the 4 existing insights with their kinds unchanged (its test asserts the rows are identical), so the Overview falls back to the latest insight until Sera's first batch writes a `synthesis`. R6, Phase 1/4.
- Step 3's `My opinion:` convention is free text. If phase 5 wants to style that paragraph, it can match the literal prefix. This phase only guarantees the skill asks for it. R5, Phase 5.

## Rollback

`git revert <phase-7 commit>`. The five files are docs and one CI yaml, and nothing depends on them at build or runtime. Reverting the CI change only stops CI from running on database-only commits. Reverting the skill text sends the solo explore path back to `git add lab/lab.sqlite`, which would let the snapshot drift (the sync guard would then fail on the next code-touching commit). Revert phase 7 together with phase 1, or not at all.
