# Package: ROOT (seer)

**Location**: `.` (repository root)
**Last Updated**: 2026-10-08 (lab-realistic-gate, phase 3 (P1-ROOT-RDX2): a new
`/redo-sera-experiments` skill that mints one pre-registered, realistically-costed "variation twin"
per named lab method, as a batch)

## Overview

The ROOT package is everything in the repository that is not owned by `engine/` or `web/`, each of
which carries its own `package_readme.md`. It holds no application source. What it holds instead is
the machinery that *drives* the application: the Claude Code skills that run Seer's method lab, the
GitHub Actions that run the nightly pipeline, the Postgres migrations the engine writes through, the
method lab's own SQLite database, the workflow bookkeeping (`todos.md`, plans, orchestration), and
the design/handover/runbook documentation.

Its "API" is therefore not functions but **entry points a human or an agent invokes**: a slash
command, a workflow dispatch, a migration file, a runbook step.

**Key Responsibilities:**
- The five lab skills under `.claude/skills/` — exploring new methods, redoing existing ones
  honestly, fanning a batch out, moving the research store between machines, and repairing a stale
  published method page
- The scheduled and manual GitHub Actions under `.github/workflows/` — CI, nightly, universe,
  backfill, repick, sean, watch
- The forward-only Neon schema under `db/migrations/`, plus one-off operational SQL in `db/ops/`
- `lab/lab.sqlite`, the method lab's append-only record of every idea, trial, note and insight
- Task and plan bookkeeping under `.workflows/` (`todos.md`, `plan/`, `orchestration/`)
- Long-form documentation under `docs/` — the roadmap, design notes, backtests, handovers,
  pre-registrations and runbooks
- Repo-wide configuration: `.env.example`, `.gitignore`, `.gitattributes`, `.vercelignore`

## Exported API

The root's exported surface is its **invocable entry points**.

### Skills (`.claude/skills/<name>/SKILL.md`)

Each directory holds one `SKILL.md` with YAML frontmatter (`name`, `description`) and becomes the
slash command `/<name>`.

#### `/redo-sera-experiments`

```
/redo-sera-experiments M0022,M0020,M0019
/redo-sera-experiments https://seertrade.site/sera/methods/M0007
/redo-sera-experiments M0022,https://seertrade.site/sera/methods/M0020,M0007-N20-RAW
```

Purpose: redo one or more existing lab methods **the way the owner actually trades** — fractional
shares, Gotrade's real fitted fee schedule (`cost_model="gotrade"`), and his real funding plan
(5,000,000 IDR arriving on the 25th of each month on top of the opening book) — and report every
result beside its parent in a single batch table.

Arguments: one comma-separated list. Each item may be a bare `MNNNN` id, a full
`seertrade.site/sera/methods/MNNNN` URL, or a pinned candidate id such as `M0007-N20-RAW`; the forms
may be mixed in one invocation, with or without spaces after the commas. Parsing is **per item, not
across the whole string**, so a candidate id keeps its variant suffix. Items are deduped by parent
id, first occurrence winning. A single method is the one-element batch — there is no separate path
for it.

What it produces, per method: one **variation twin** — a new method whose `source_kind` is
`variation`, whose `parent_id` is the original, and whose `source_ref` begins with the marker
`redo-sera-experiments:`. Each twin goes through its own reserve -> write file -> commit -> run
cycle, where the commit *is* the pre-registration (`lab run` refuses an uncommitted method file).

What it deliberately does **not** do: delete or purge the original, even when asked to in those
words. Three reasons, stated in the skill in the owner's own plain terms: the old numbers are a
correct answer to a different question and are what makes the cost of realism measurable; deleting a
past try shrinks the luck discount and so silently raises **every other** method's score; and the
schema forbids it outright (`trials_no_delete`, `trials_no_update`, `methods_no_delete`).

Side effects: writes new method files under `engine/src/seer_engine/lab/methods/`, one git commit per
twin, rows in `lab/lab.sqlite` via `lab idea` / `lab run` / `lab note` / `lab insight`, and exactly
one `lab stage` + publish at the end of the batch.

Isolation: **per item, not per process.** Any failure or refusal inside one item — a missing method,
an `H-` seed id with no method file, a parent already fractional at real fees, a digest collision, a
failed run — is journaled, recorded as a skip, and the batch continues. A bad id costs one row of the
report, never the batch.

Resume: the state *is* the database and git, so there is no progress file. A classification pass
reads each parent's marker-bearing twin and places it in one of five states — not started; reserved
with no file; file written but uncommitted; committed but not run; done — and picks up from there.
Re-minting or deleting a twin that already ran is forbidden, because a pre-registration rewritten
after seeing a number is not a pre-registration.

Execution model: **serial, in the main checkout** (`/home/miftah/seer`), deliberately *not*
`sera-the-explorer`'s worktree fan-out. The research store is gitignored and exists only there; only
one session may commit the lab database; `lab run`'s committed-file check runs in the method file's
own directory and only agrees with the importable `seer_engine` when venv and sources are the same
tree; and a redo is minutes of mechanical work with no research between items.

#### `/explore-and-experiment-new-method`

Purpose: research, implement, pre-register and run a genuinely new method, then analyse, promote or
queue a follow-up variation. Also the per-method worker a Sera batch spawns via `--method MNNNN`.
Ships `method_template.py`, the fallback starting point when a twin cannot reuse its parent's
allocator.

#### `/sera-the-explorer`

Purpose: coordinate `<num-methods>` parallel `/explore-and-experiment-new-method` child sessions,
each in its own worktree, and make itself the sole committer of the lab database. Also resumes or
reports on a batch already running.

#### `/sync-research-store`

Purpose: move `engine/.research/` between machines through Vercel Blob, content-addressed on the
manifest fingerprint, instead of rebuilding it from Neon (~30 minutes plus a yfinance crawl). The
store is the train/eval input `lab run` reads; it never opens Neon.

#### `/update-stale-sera-methods-page`

Purpose: repair a page on `seertrade.site/sera` that reads a number against a bar the lab no longer
holds — after `DSR_MIN`, `MAX_DRAWDOWN`, `MIN_PROFIT_FACTOR` or the N policy moves. One rule: no
number on the page may be read against a bar from a different day.

### GitHub Actions (`.github/workflows/`)

| Workflow | Trigger | Purpose |
|---|---|---|
| `engine-ci.yml` | push on `engine/**` | the engine test suite; also fails a lab database commit that arrives without its `web/data/lab.json` snapshot |
| `nightly.yml` | schedule (after the NYSE close, in Eastern terms) | the nightly pipeline: bars, FX, picks, veto, paper |
| `universe.yml` | schedule, 00:30 UTC Monday (07:30 WIB) | the weekly point-in-time universe rebuild |
| `watch.yml` | schedule, 14:23 UTC daily (21:23 WIB) | one line a day carrying four facts: session stepped, picks published, CI green, paper paused |
| `backfill.yml` | `workflow_dispatch` (start/end inputs) | historical bar backfill |
| `repick.yml` | `workflow_dispatch` (dry-run input) | re-run the pick step for a session |
| `sean.yml` | `workflow_dispatch` (dry-run input) | the Gotrade tracker run |

### Database schema (`db/migrations/`)

Forward-only, numbered, applied in order: `001_init` through `017_roster_real_fees`, covering the
engine tables, paper trading, the news veto, fundamentals, the roster, the fractional book, the
journal, Sean, contributions and real fees. `db/ops/` holds dated one-off operational SQL that is not
part of the schema sequence.

### The lab database (`lab/lab.sqlite`)

The method lab's record: `methods`, `trials`, notes, insights and funding rows. Marked `binary` in
`.gitattributes`. **Append-only by schema** — deletes and updates on methods and trials are blocked
by triggers, which is what makes the luck discount honest. Only `lab stage` may commit it, and every
such commit must also carry `web/data/lab.json` or CI fails.

### Workflow bookkeeping (`.workflows/`)

- `todos.md` — the task board; one entry per TaskID with context, status, plan link, files touched,
  drift and decisions
- `plan/` — one `<TaskID>.md` execution plan per task, plus per-plan-set subdirectories holding the
  phase sources those copies are adopted from
- `orchestration/` — per-plan-set coordination state for multi-session swarms
- `package_readme.md` — this file

### Documentation (`docs/`)

`ROADMAP.md`; `plans/` (dated design documents, including the method lab design and the P7b
pre-registration — plus the `*_PLAN.md` plan sets, see below); `analyzer/` (the `/analyze`
reports those plan sets are built from); `design/` (UI prototypes); `backtests/` (dated results
with their CSV and SVG); `handover/` (dated session handovers); `lab/prereg/` (pre-registrations);
`runbooks/` (`data-pipeline.md`, `paper-trading.md`, `monitoring.md`).

### Plan sets and their analyses

`docs/plans/*_PLAN.md` are plan sets, one per feature programme (e.g.
`LAB_REALISTIC_GATE_PLAN.md`); `docs/analyzer/YYYYMMDD-HHMMSS-XXXX_code_analyzer.md` are the
`/analyze` reports they are built from. Each plan names its analysis in an `**Analysis:**` line.

Both lived at the repo root until 2026-10-09, when forty-three of them had made the root
unreadable. `/analyze` now files them under `docs/` in any repo that has a `docs/` tree, so new
sessions land here without being told. Two naming conventions share `docs/plans/`: dated design
documents (`2026-10-04-method-lab-design.md`) and these `SCREAMING_SNAKE_PLAN.md` indexes.

## Internal Architecture

### Data Flow

```
/analyze  ->  docs/analyzer/<timestamp>_code_analyzer.md
                  |
              docs/plans/<NAME>_PLAN.md
                                                      |
                                        .workflows/plan/<set>/phase-N.md
                                                      |
                              .workflows/plan/<TaskID>.md  +  .workflows/todos.md entry
                                                      |
                                           /do  ->  source edits  ->  commit
                                                      |
                                       readme-updater  ->  package_readme.md
```

The lab's own flow is separate and runs through the skills:

```
lab idea (reserve id + hypothesis)
   -> write engine/src/seer_engine/lab/methods/mNNNN_*.py
   -> git commit the file            <- this commit IS the pre-registration
   -> lab run MNNNN --store engine/.research
   -> lab note / lab insight
   -> lab stage  (once)  ->  lab/lab.sqlite + web/data/lab.json  ->  push  ->  site redeploys
```

### Entry points

A human or agent enters at a slash command, a workflow dispatch, or a `/do <TaskID>`. Nothing in this
package is imported by code.

## Dependencies

### Internal

- `engine/` — every skill drives `python -m seer_engine lab …` from `engine/.venv`; migrations in
  `db/` describe tables the engine writes
- `web/` — `web/data/lab.json` is the published snapshot of `lab/lab.sqlite`; the site redeploys from
  each push

### External

- Claude Code — the skill runtime (`.claude/skills/`)
- GitHub Actions — the scheduler and CI
- Neon (Postgres) — the production database the migrations target
- Vercel — hosting for `web/`, and the Blob store `/sync-research-store` ships through
- Third-party data: Massive (bars), Finnhub (company news and earnings dates), SEC EDGAR
  (fundamentals, which requires a contact address in `SEC_CONTACT_EMAIL`)

### Configuration

`.env.example` lists every key: `LLM_*`, `VERCEL_*`, `DATABASE_URL` / `DATABASE_URL_UNPOOLED`,
`AUTH_*`, `ALLOWED_EMAIL`, `MASSIVE_API_KEY`, `FINNHUB_API_KEY`, `SEC_CONTACT_EMAIL`. Real values
live in `.env.local`, which `.gitignore` excludes along with `engine/.research*`, `engine/.cache/`,
`lab/lab.xlsx` and `.workflows/sera/`.

## Reverse Dependencies

Nothing imports this package. Its consumers are:

- **The owner and agent sessions** — through the five slash commands
- **GitHub Actions** — running the workflows on schedule and on dispatch
- **The engine** — reading `db/migrations/` as the schema of record
- **The site** — redeploying from pushes that carry `web/data/lab.json`

## Concurrency

The repository is worked by **several Claude Code sessions at once**, across a main checkout at
`/home/miftah/seer` and worktrees under `/home/miftah/.worktrees/seer/`. There is no process-level
locking; the invariants are conventions the skills enforce.

Guarantees and their rules:

- **The git index is shared** across the main checkout and every worktree. Commit by explicit
  pathspec. Never `git add -A`, never `git reset --hard`.
- **The stash stack is shared.** Never bare `git stash` / `git stash pop`.
- **One committer for the lab database.** Only `lab stage` commits `lab/lab.sqlite`, and always
  together with `web/data/lab.json`. Never `git checkout`, `git restore` or `git stash` the database —
  it is a binary another session may be mid-write in; return to clean with a `pull`.
- **`/sera-the-explorer` parallelises; `/redo-sera-experiments` does not.** Sera's children are full
  research sessions worth isolating; a redo is mechanical, needs the store that exists only in the
  main checkout, and would funnel through one committer anyway.

## Error Handling

The analogue of error types here is **refusals**, and the governing distinction is per-item versus
per-batch.

- `/redo-sera-experiments` refuses **per item** and continues: a method the lab does not have, an
  `H-` seed id with no method file, an item containing no `MNNNN`, a parent already fractional at
  real fees, a digest collision, a failed run. Each is recorded with its reason and reported as a
  row.
- It refuses **permanently** to purge or delete, to re-run a parent under new funding (funding is a
  property of the lab's era, not of a configuration, so the re-run is the same configuration), to
  nudge a parameter around a digest collision, or to delete and re-mint a twin that already ran.
- It never asks. No skill in this package holds a prompt open; the only allowed stop is terminal —
  missing tooling or a permission the session does not have — and it is reported, not queued behind a
  question.

## Performance

- `lab run` is the expensive step: minutes per method, serialised at the database.
- Rebuilding `engine/.research/` from Neon is ~30 minutes plus a yfinance crawl; `/sync-research-store`
  exists to avoid paying it twice.
- The engine suite is parallelised with `pytest-xdist`; without it the suite runs serial and takes
  roughly five times as long.

## Usage

### Redo a batch of methods honestly

```
/redo-sera-experiments M0022,M0020,M0019
```

Runs in the main checkout. Prints the resolved plan — the parents it will twin, in order, and every
item it is skipping with its reason — then works through them one at a time, publishing once at the
end.

### Lab quick reference

```
lab show M0007        # a parent, its trials, its verdict
lab status            # the live method count, the live luck bar, test looks used
lab luck --limit 0    # read-only: every recorded DSR re-scored at today's count
lab costs M0007       # report only: flat fees vs Gotrade's real ones
lab idea …            # reserve an id and a hypothesis; prints the new id
lab run MNNNN --store /home/miftah/seer/engine/.research
lab stage             # once, at the end: snapshot + git-add the database
```

### Gotchas

- **The research store is not in any worktree.** Point `--store` at the main checkout; a rebuild is
  half an hour for nothing.
- **Every `lab` subcommand migrates the database on connect, so even a read dirties the file.** When
  a column no command prints is needed, open `lab/lab.sqlite` read-only
  (`file:…?mode=ro`, `uri=True`) instead.
- **`tests/test_lab_snapshot.py` fails whenever the database changed without a `lab stage`** — the
  signature of a batch interrupted before it published. Stage, commit the database with its snapshot,
  push, and re-run the tests. Always test *after* staging.
- **Tests run in a worktree need `PYTHONPATH` pointing at that worktree's `engine/src`**, or pytest
  silently tests the main checkout instead of the branch.
- **A method file's module number must equal its `METHOD.id`** (`m0032_*.py` ↔ `id="M0032"`), or
  `discover()` raises for the whole lab, not just that method.
- **Never type a luck bar or a method count into prose.** They are the owner's dials and they move;
  read them from `lab status` at run time.
- **Never fetch a `seertrade.site` URL.** The site is behind the Sera gate and the repo holds
  everything the page is built from.
- **Promotion is not a redo's job.** It spends the one counted look per method and belongs to
  `/explore-and-experiment-new-method` or to Sera — and when it happens, promote the twin, never the
  original.

## Notes

The luck gate's N counts **distinct methods with a dev trial**, not trial rows (changed 2026-10-08).
This is what makes batched redos safe: a three-method batch adds three to the count, one per idea,
rather than one per variant per method. The skills read the policy, the count and the bar from
`lab status` / `lab luck` at run time and hard-code none of them, so a later policy change leaves
them correct.

## Documentation Created: 2026-10-08

Initial creation, prompted by P1-ROOT-RDX2 (phase 3 of `LAB_REALISTIC_GATE_PLAN.md`), which added
`.claude/skills/redo-sera-experiments/SKILL.md` — the only file that task touched.
