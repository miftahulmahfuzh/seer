# Method lab — design

Status: validated in brainstorming, 2026-10-04.

**Goal.** Keep searching for a strategy that beats SPY under design §1, with no end date, without
fooling ourselves. One `/explore-and-experiment-new-method` run explores one idea end to end and
logs it to a central, append-only lab database. Iron rule: we never stop trying; every run queues
at least one next idea.

**The risk is overfitting, not running out of ideas.** Thousands of trials on one dataset will
produce lucky winners. The lab counts every trial ever run and deflates each result by that
count (deflated Sharpe ratio), and the untouched test window (2015-10-19 → data end) is spent
one counted look at a time.

Owner decisions (2026-10-04): tracker = SQLite committed in the repo; promotion = luck-check then
one test-window look; scope = one idea with 1–6 fixed variants per run.

## 1. Lab database — `lab/lab.sqlite` (committed)

Accessed only through `seer_engine.lab.store` (stdlib `sqlite3`).

- **`methods`**: one row per idea. `id` (`M0001`…), `name`, `family` (free text), `parent_id`
  (variation of), `source_kind` (`paper`/`blog`/`github`/`knowledge`/`variation`/`backlog`/`seed`),
  `source_ref`, `hypothesis` (written before the run), `status`, `analysis` (markdown, appended),
  `verdict`, `created`, `updated`.
  Status moves forward only: `idea` → `registered` → `ran` → `rejected` | `dev-eligible` →
  `promoted` → `test-passed` | `test-failed` → `paper`. Side exit: `blocked-data` (needs data
  the store does not hold).
- **`trials`**: one row per backtest; this table is the multiple-testing count. Method, candidate
  id and digest, params, rules id, window (`dev`/`test`), start, end, store fingerprint, git sha,
  run time, metrics (return, CAGR, max DD, PF, trades, Sharpe, exposure, turnover, worst year,
  SPY TR return, MAR), failed conditions, eligible, DSR, `n_trials_at_run`, month-end equity
  curve. Append-only, enforced by triggers. At most one `test` trial per digest.
- **`ideas_seen`**: dedupe index of explored sources/fingerprints.
- **Seed:** P7a's 54 candidates as trials 1–54; A, A2 and B as historical methods.
- **View:** `python -m seer_engine lab export` → gitignored `lab/lab.xlsx` (one sheet per table
  plus a leaderboard by MAR); `sqlite3 lab/lab.sqlite` for queries.

## 2. Plug-and-play

- A method is one file, `engine/src/seer_engine/lab/methods/mNNNN_<slug>.py`, exporting
  `METHOD = Method(...)` with 1–6 fixed `Candidate`s. New signal logic is an `Allocator` in the
  same file, or an existing allocator with new params. `TradeRules`, the book engine, costs,
  dividends and whole-share sizing are reused unchanged.
- `Candidate` ids accept lab ids (`M0007-V2`) and lab families. The P7a registry and its cap
  stay frozen as a historical record.
- `python -m seer_engine lab run M0007`: refuses an uncommitted method file (the commit is the
  pre-registration), refuses a digest that already has a trial, runs each candidate through
  `dev.run_candidate` on the research store (dev window ≤ 2015-10-16, D9 guard intact), computes
  DSR with lab-wide N, inserts trials, advances the method status, prints a summary.
- A parametrized test runs the `allocatorkit` contract checks over every lab method.
- Ideas needing data the store lacks (fundamentals, intraday, options, sentiment) are logged as
  `blocked-data` with what is missing.
- ML methods get an expanding-window refit wrapper, built when the first one needs it.

## 3. Promotion

- **Dev-eligible** = the five P7a D8 conditions (beats SPY TR, max DD ≤ 15%, PF ≥ 1.3, ≥ 100
  trades, no owner inputs) **and** DSR ≥ 0.95 with N = all lab trials.
- The best dev-eligible variant by MAR (one per method) is pre-registered in
  `docs/lab/prereg/MNNNN.md`, committed and pushed before any test number exists.
- `python -m seer_engine lab test <candidate>` runs it **once** on the test window; the database
  refuses a second look. The test-window store is built the first time something is promoted,
  never before. Every summary shows "test-window looks used: k".
- Fail → `test-failed`, final. Pass → `test-passed`, and the skill stops for the owner: a paper
  roster entry (new id, own clock) is the owner's call; real money still needs all of design §1.

## 4. The skill

`.claude/skills/explore-and-experiment-new-method/SKILL.md`. One run:

1. Preflight: clean `main`, pull, engine venv, research store, lock file.
2. `lab status`: N, test looks used, families tried, near-misses, backlog, blocked-data.
3. Choose one idea (variation of a near-miss, web research, knowledge, or backlog), testable and
   not in `ideas_seen`; write the hypothesis and the expected failure mode first.
4. Register: method file (+ allocator, + tests); commit = pre-registration.
5. `lab run`.
6. Analysis + verdict into the database.
7. Queue at least one next idea.
8. Promote if dev-eligible.
9. Commit + push; short report.

Guardrails: never edit `DEV_END`, design §1/§5, the paper roster or the P7a registry; never
delete or rewrite a trial; never touch the test window outside step 8; never tune after seeing a
result within a method (tuning is a new variation method with new trials). Nonstop:
`/loop /explore-and-experiment-new-method`.

## 5. Tests and build order

Tests: store (schema, append-only triggers, forward-only status, one test look per digest,
export), runner (dirty-tree and duplicate refusals, D9, DSR with lab-wide N, rows), method
contract test, seed import digests.

Build: (1) store, (2) `Method` + discovery + ids + contract test, (3) `lab` CLI
(`run`/`status`/`note`/`idea`/`export`), (4) seed import and committed DB, (5) `SKILL.md`,
(6) a first real run. `lab test` and the test-window store are specified here and built on first
promotion.

## 6. Revision 2026-10-04 (owner): no human in the loop, Sera, the journal

- **No human in the loop.** Both skills decide everything themselves and never ask: idea,
  variants, promotion (they build `lab test` and the test-window store on first need) and, on a
  test pass, a paper-roster entry with its own clock. Assumptions are written into the analysis.
  Design §1 and the no-real-money rule are unchanged.
- **`/sera-the-explorer <num-methods>`** coordinates up to 4 explore sessions at once, each in its
  own worktree (`explore/MNNNN`) and tmux window via `swarm.py launch`. It reserves diverse ideas
  as `idea` rows, refills slots as children finish, verifies each child, promotes serially,
  cleans up and writes a batch synthesis. Children share the main checkout's database through
  `SEER_LAB_DB` and commit only their method files; only Sera commits `lab/lab.sqlite`, through
  `lab stage` (git add under the write lock). `BEGIN IMMEDIATE` makes id allocation and the
  lab-wide N atomic across sessions.
- **`insights`**: an append-only journal (`observation`, `hypothesis`, `data-wish`,
  `feature-wish`, `risk`), the food-for-thought record that seertrade.site/sera shows.
