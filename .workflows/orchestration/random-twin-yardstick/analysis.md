# Code Analysis: the lab's dev screen, control arms and method status

**Type:** Feature Implementation
**Date:** 2026-11-13 12:54 WIB
**Session ID:** 20261113-125454-Y7RT
**Plan:** `.workflows/plan/RANDOM_TWIN_YARDSTICK_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/seer/random-twin-yardstick` on `feature/random-twin-yardstick` (base `origin/main` @ `f83fb237`)

---

## User Input

### Original User Request

> you idea so we can implement them robustly

### User-Provided Context

The request follows a codebase review in the same session. "You idea" refers to the review's one
recommendation, and "them" to its three numbered parts, quoted here verbatim because they are what
the request points at:

> 1. **A random-book yardstick per setup.** For each combination of pool, book size, cadence,
>    weighting and safety switch, run a few hundred random books once and cache the distribution.
>    These count against nothing.
> 2. **Judge ideas against it.** An arm passes only if it beats roughly the top tenth of random
>    books on its own setup, in place of today's "beats SPY and clears the luck score".
> 3. **Derive status from treatment arms only.** Arm roles already exist (the hard gate reads them
>    to refuse promoting a control); the status line just ignores them.

The review also said: "this changes the screen for every recorded method, so it needs a dated owner
revision and a re-judging pass, not a quiet code change."

### User-Provided Files

None.

### Requirement IDs

| ID | What the user asked for (verbatim) |
|---|---|
| R1 | "you idea so we can implement them robustly" — part 1: "A random-book yardstick per setup. For each combination of pool, book size, cadence, weighting and safety switch, run a few hundred random books once and cache the distribution. These count against nothing." |
| R2 | "you idea so we can implement them robustly" — part 2: "Judge ideas against it. An arm passes only if it beats roughly the top tenth of random books on its own setup, in place of today's 'beats SPY and clears the luck score'." |
| R3 | "you idea so we can implement them robustly" — part 3: "Derive status from treatment arms only. Arm roles already exist (the hard gate reads them to refuse promoting a control); the status line just ignores them." |

#### Acceptance Criteria

| ID | Pattern | Criterion |
|---|---|---|
| R1.1 | event | WHEN `lab yardstick <method>` is run for a recorded dev arm that holds picked stocks THE SYSTEM SHALL simulate `YARDSTICK_DRAWS` random twin books that replay that arm's own decisions (same dates, weights, entries and exits) with every picked name replaced by a randomly drawn index member of similar trading size, and record the share of twins the arm out-earned. |
| R1.2 | ubiquitous | THE SYSTEM SHALL record a yardstick measurement without inserting a `trials` row, changing the luck count N, or spending a test-window look. |
| R1.3 | unwanted | IF the twins' median trade count or turnover falls outside 0.50x–2.00x of the arm's own THEN THE SYSTEM SHALL record the measurement as `unmatched`, which never counts as clearing the yardstick. |
| R1.4 | unwanted | IF the arm's decisions hold no picked stock at all (an ETF-only or cash-only book) THEN THE SYSTEM SHALL record the yardstick as `not-applicable` and simulate no twins. |
| R1.5 | ubiquitous | THE SYSTEM SHALL produce the identical yardstick result for the same arm on the same research store, whatever the `--jobs` value, and SHALL NOT append a second row when the measurement is repeated. |
| R1.6 | unwanted | IF the arm's trial was recorded on the loaded store and re-running the arm does not reproduce its recorded trade count and return THEN THE SYSTEM SHALL refuse with exit code 2 and record nothing. |
| R2.1 | event | WHEN `lab run` records a non-control arm that clears every other screen condition THE SYSTEM SHALL measure its yardstick before recording and record the arm eligible only if it out-earned at least `YARDSTICK_MIN_PERCENTILE` (0.90) of its twins. |
| R2.2 | state | WHILE a dev arm's latest yardstick measurement is below the bar or `unmatched` THE SYSTEM SHALL report that arm not eligible in `store.verdict`, with the yardstick label in its failure list. |
| R2.3 | unwanted | IF `lab promote` is asked to promote a method whose chosen arm has no measured yardstick that clears the bar (and is not `not-applicable`) THEN THE SYSTEM SHALL refuse with exit code 2 and write nothing. |
| R2.4 | event | WHEN the lab snapshot is exported THE SYSTEM SHALL publish each arm's role and yardstick reading, and the method page SHALL show the yardstick as a seventh condition in plain words with no ids or code. |
| R3.1 | event | WHEN `lab run` finishes a new method THE SYSTEM SHALL set its status to `dev-eligible` only if at least one non-control arm is eligible, and to `rejected` otherwise. |
| R3.2 | state | WHILE an arm is recorded as a control THE SYSTEM SHALL report it not eligible in `store.verdict` and SHALL never choose it in `store.best_dev_eligible`. |
| R3.3 | event | WHEN `lab reevaluate --demote` is run on a `dev-eligible` method that has no eligible non-control arm at today's bars THE SYSTEM SHALL move it to `rejected`, append a dated note to its analysis, and leave every trial row untouched. |
| R3.4 | event | WHEN `lab roles --backfill` is run THE SYSTEM SHALL record the role of every recorded dev arm whose method file can be read, once, and SHALL skip arms it cannot read without failing. |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** The lab's dev screen (`backtest/dev.py:make_row` plus the luck
label appended in `lab/runner.py:trial_rows`) compares every arm with SPY and with zero. It never
compares an arm with what a no-skill book of the same shape earns. Measured this session on the
committed `lab/lab.sqlite` (HEAD `f83fb237`, store fingerprint `640fc25e5c7b…` for the current
store):

- 45 dev trials belong to the two deliberately meaningless families (`placebo-hash-order`,
  `blind-draw-baseline`). 42 beat SPY (median excess CAGR +2.08 points a year) and 14 were recorded
  eligible.
- Of 2,051 dev trials on the main window (start 1996-01-03), 362 were recorded eligible.
- At today's bars (`store.verdict`, gate N = 415, policy `methods`), 256 dev arms in 125 methods
  read eligible. By `control_shape.role_of`, 64 of those 256 are control arms, 185 treatment and 7
  dose. 192 non-control arms in 97 methods remain.
- 182 methods carry status `dev-eligible`. 94 of them have an eligible non-control arm today.
- No method has ever reached `promoted`, `test-passed` or `paper`. Six test looks are spent, all
  `test-failed`.

So three things are missing: a measured no-skill distribution per arm (R1), a screen condition
that reads it (R2), and a status that ignores arms registered to be beaten (R3).

**What "per setup" has to mean in this codebase.** There is no machine-readable "setup". Every
method file defines its own `Allocator` and its own params dataclass
(`lab/methods/mNNNN_*.py`, 407 files); a random arm is hand-written per method (for example
`TimeParams(N20, "blind", 5621, 100, 40)` in `m0562_*.py`). Nothing can enumerate "pool, book size,
cadence, weighting, switch" for an arbitrary allocator. What every arm does expose, uniformly, is
its **sequence of decisions**: `backtest/book_runner.py:428` calls
`allocator.targets_prepared(prepared, members, data_date, mine, params)` on every rank or resize
session and receives a tuple of `Target(symbol, weight, last, limit, stop, take)`. Measured this
session with a read-only probe on `M0562-W60-B100`: wrapping the allocator in a recorder and
replaying the recorded targets through a second allocator reproduced the arm exactly (money-weighted
return 0.1494087982869519 both times, 203 trades both times, 237 decisions), in 1.5 s against 2.6 s
for the first run. A twin built by replaying those decisions with the picked names swapped
therefore has the arm's dates, weights, entry and exit counts, keep-band drift and cash months by
construction, for any allocator, with no per-method code.

**Success Criteria.** The fourteen acceptance criteria above. In one sentence each: a yardstick can
be measured for any recorded stock-picking arm, deterministically and without touching N (R1); new
arms are gated on it at `lab run`, old arms once measured, and promotion fails closed without it
(R2); controls never make a method `dev-eligible` and never get chosen, and stale `dev-eligible`
statuses have a door back to `rejected` (R3).

**Key Considerations.**

- `trials` is append-only by trigger; `eligible` and `failed` are frozen at run date. The lab
  already separates the record from the verdict: `store.verdict` (store.py:1810) re-derives every
  condition at today's bars and `_snapshot_trial` (store.py:3178) publishes it as `failedNow` /
  `eligibleNow`. A new condition belongs in `store.verdict`, where `best_dev_eligible`,
  `reevaluate_method`, the snapshot and the web already read.
- `store._migrate` (store.py:964) documents that a schema version bump "is a one-way door for every
  other checkout": old code raises on connect. Parallel Sera sessions run old checkouts against the
  shared DB through `SEER_LAB_DB`. Side tables created with `CREATE TABLE IF NOT EXISTS` inside
  `_SCHEMA` need no version bump; every existing side-table reader (`funding_of`, store.py:2294)
  already answers None when its table is absent.
- `lab/lab.sqlite` and `web/data/lab.json` change on `main` many times a day (124 of 272 commits in
  the last week touched `lab.sqlite`, per the review's sub-agent; not re-measured here). A feature
  branch that commits either file conflicts at merge.
- `run_method` computes `trial_rows` inside `store.begin_immediate` (runner.py:725). Anything slow
  placed there blocks every parallel session.
- Status only moves along `store.TRANSITIONS` (store.py:123), enforced by a trigger that reads the
  `transitions` table (store.py:679). There is no edge out of `dev-eligible` except `promoted`.
- `control_shape.role_of` (control_shape.py:587) reads an arm's role from its one-line rationale.
  It is total and pure. `treatment` is a residue, `control` is the only role anything refuses on
  (hardgate D18, hardgate.py:2143-2172). 54 dev trials (the P7a seed rows) have no readable method
  file.
- A percentile among twins does not correct for the lab having tried 415 methods; the deflated
  Sharpe does. The two answer different questions.
- Machine: 24 cores, 11 GiB RAM, 5 GiB free at measurement. Store load 12.2 s.

**Assumptions.**

- A1. "Similar trading size" is the member's rank by median dollar volume (close × volume) over the
  trailing 63 bars at the decision date. `History` (strategies/base.py:34) carries `close` and
  `volume` for every symbol; `Market.market_value` has gaps for multi-class companies.
- A2. The comparison statistic is the rate `make_row` already ranks on: money-weighted return when
  the run was funded, CAGR otherwise (dev.py:463).
- A3. Re-judging the 192 already-eligible non-control arms is lab operation on `main` after the
  code lands, not a code phase: it writes the shared DB.

---

## Analysis Scope

### Explicitly Mentioned Files

None.

### Discovered Related Files

- `engine/src/seer_engine/lab/runner.py` — `trial_rows` (524), `run_method` (659), status line (752)
- `engine/src/seer_engine/lab/store.py` — `TRANSITIONS` (123), `DSR_MIN`/`DSR_LABEL` (168-179), `_SCHEMA` (560), `connect` (707), `_migrate` (964), `best_dev_eligible` (1367), `Verdict` (1433), `owner_failures` (1589), `verdict` (1810), `published_verdict` (1881), `_blocking` (1957), `reevaluate_method` (2014), side-table rows (2160-2735), `_snapshot_trial` (3178), `snapshot` (3286), `SNAPSHOT_VERSION` (3069)
- `engine/src/seer_engine/lab/control_shape.py` — `ROLES` (420), `role_of` (587), `REFUSE_BAND` (440)
- `engine/src/seer_engine/lab/hardgate.py` — `promoted_arm_role` (1144), `promoted_variant` (1397), `check` (2064; D18 at 2143, D19 at 2178, D16 at 2187, D17 at 2202, kin at 2233)
- `engine/src/seer_engine/lab/control_draw.py` — the hand-applied matched draw (v1 351, v2 shadow 500)
- `engine/src/seer_engine/lab/method.py` — `Method`, `discover` (207), `config_digest` (51)
- `engine/src/seer_engine/lab/remeasure.py` — re-runs a recorded trial at its recorded capital and funding
- `engine/src/seer_engine/backtest/dev.py` — `FAILURE_LABELS` (87), `Candidate` (180), `make_row` (432), `run_candidate` (607), `run_registry` (641)
- `engine/src/seer_engine/backtest/book_runner.py` — `run_book` (290), allocator call (421-428)
- `engine/src/seer_engine/strategies/allocator.py` — `Allocator` protocol (57), `prepare_for` (116)
- `engine/src/seer_engine/strategies/base.py` — `History` (34), `Target`
- `engine/src/seer_engine/commands/lab.py` — subcommand parser (248), `_run` (1922), `_promote` (2181), `_reevaluate` (2233), `_control` (3522)
- `engine/src/seer_engine/research.py` — `load_store` (1334), `STORE_DIR` (82)
- `web/lib/sera/derive.ts` — `CONDITION_KEYS` (26), `FAILURE_LABEL` (37), `conditionOk` (134)
- `web/lib/sera/types.ts`, `web/lib/sera/lab.test.ts`, `web/lib/sera/glossary.ts`, `web/app/sera/overview.ts` (130), `web/app/sera/methods/view.ts` (31), `web/app/sera/methods/[id]/page.tsx`, `web/app/sera/how/view.ts`
- `engine/tests/test_lab_*.py` (50 files; `labkit.py` is the shared fixture kit)
- `docs/plans/2026-10-04-method-lab-design.md` (latest revision is §9, 2026-10-12)
- `.claude/skills/explore-and-experiment-new-method/`, `.claude/skills/sera-the-explorer/`, `.claude/skills/verify-seer/features/lab-cli.md` and `sera.md`

---

## Current Dataflow

### Entry Point: `lab run MNNNN`

**Location:** `engine/src/seer_engine/commands/lab.py:1922` (`_run`)
**Trigger:** CLI, `python -m seer_engine lab run MNNNN [--amend]`
**Input:** a committed method file; the research store at `SEER_RESEARCH_STORE` or `engine/.research`
**Validation:** `runner.preflight` (committed file, not already run, no repeated digest), `preflight_data`, `refuse_survivorship_store`
**Next Step:** `runner.run_method` at `lab/runner.py:659`

### Processing Chain

1. **`runner.run_method`** — `lab/runner.py:659`
   - Simulates every candidate through `dev.run_registry` (runner.py:721), outside any DB lock, funded on `OWNER_MONTHLY`.
   - `dev._run` → `book_runner.run_book` → on each rank session `allocator.targets_prepared(...)` (book_runner.py:428) → fills, snapshots.
   - `dev.make_row` (dev.py:432) decides the five D8 conditions: beats SPY TR, max DD ≤ `DEV_MAX_DRAWDOWN` (0.50), PF ≥ 1.3, ≥ 100 trades, no owner inputs.
2. **`store.begin_immediate`** — runner.py:725. Everything below is one transaction under the lab-wide write lock.
3. **`runner.trial_rows`** — runner.py:524
   - N from `store.pending_gate` (store.py:1521); DSR per arm; appends `store.DSR_LABEL` when DSR is None or below `DSR_MIN` (runner.py:611).
   - `eligible = not failed` (runner.py:641).
4. **Repeat check** — `twins.repeats` / `twins.refused` (runner.py:744).
5. **Status** — runner.py:752: `"dev-eligible" if any(r.trial.eligible for r in ran) else "rejected"`. No role is consulted.
6. **Inserts** — `insert_trials`, `insert_moments`, `insert_funding`, `insert_provenance` (runner.py:774-807), then the fold record (`hardgate.fold_verdict` → `insert_folds`, 832-849), then `update_method(status=...)` (851) or `insert_amendment` (856). An amendment never moves status.

### Entry Point: the derived verdict

**Location:** `lab/store.py:1810` (`verdict`)
**Callers:** `best_dev_eligible` (1412), `reevaluate_method` (2067), `published_verdict` (1903) → `snapshot` → `web/data/lab.json`, and `commands/lab.py` status and luck reports.
**Transform:** four owner thresholds re-derived from the row's columns (`owner_failures`, 1589), `owner inputs` carried from the recorded string, DSR re-evaluated at the gate's current N (`dsr_at`, 1734). Returns `Verdict(dsr, failed, eligible, n, policy, derived)`.

### Entry Point: `lab promote MNNNN`

**Location:** `commands/lab.py:2181` → `hardgate.check` (hardgate.py:2064) → `prereg.promote_method`
**Order of refusals:** folds scoreable, fold majority, promoted variant's own folds (D11), control arm (D18), book twin (D19), survivorship fall (D16), mis-shaped control (D17), failed kin.
**The chosen arm:** `hardgate.promoted_variant` (1397) → `store.best_dev_eligible` (1367): highest MAR among arms whose `verdict` is eligible, no role filter.

### Entry Point: `lab reevaluate [MNNNN]`

**Location:** `commands/lab.py:2233` → `store.reevaluate` (2140) → `reevaluate_method` (2014)
**Edge taken:** `rejected → dev-eligible` only, when a dev trial is eligible under `verdict` and passes the independent `_blocking` re-check. Appends a dated `# Re-evaluation` section to `analysis`. No other status is touched.

### Entry Point: the web snapshot

**Location:** `store.snapshot` (3286), written by `lab stage` (`commands/lab.py:4142`) to `web/data/lab.json`
**Per trial:** `_snapshot_trial` (3178) publishes the record (`failed`, `eligible`, `dsr`) and the verdict (`failedNow`, `eligibleNow`, `dsrNow`, `luckGated`).
**Consumers:** `web/lib/sera/lab.ts` imports the JSON; `derive.conditionOk` (derive.ts:134) reads `failedNow` against `CONDITION_KEYS = ['spy','drawdown','pf','trades','owner','dsr']`; `overview.ts:130` counts `eligibleNow`; `methods/view.ts:31` treats status `dev-eligible` as alive. `lab.test.ts:60` asserts every published failure label is a known one.

### Data Persistence

**Database:** `lab/lab.sqlite` (SQLite, committed, append-only by trigger). Tables: `methods` (653 rows), `trials` (2,242), `trial_moments` (2,126), `trial_funding` (2,114), `trial_provenance` (2,242), `method_amendments` (29), `method_folds` (362), `insights` (1,066), `ideas_seen` (863), `transitions` (12), `meta` (1; `schema_version = 8`).
**Shared access:** `SEER_LAB_DB` points parallel sessions at one file; `begin_immediate` serialises writers.
**Derived file:** `web/data/lab.json` (23 MB), which CI holds row-for-row equal to the DB.

### Exit Points

- `lab run`: exit 0 with per-arm log lines; exit 2 on a lab-rule refusal; exit 1 on an error.
- `lab promote`: writes a pre-registration file and moves status, or exit 2 with the refusing clause.
- Snapshot: `web/data/lab.json`, read by `/sera` at build time.

---

## Key Data Structures

### `backtest.dev.Candidate` — `backtest/dev.py:180`
**Fields:** `id, family, rules: TradeRules, allocator, params, rationale, added, owner_inputs, supersedes=()`
**Used In:** every method file; `run_registry`; `control_shape.role_of` reads `rationale`.

### `strategies.allocator.Allocator` (Protocol) — `strategies/allocator.py:57`
**Members:** `id`, `lookback(params)`, `symbols(params)`, `holds(params)`, `uses_members(params)`, `targets(...)`, `prepare(history)`, `targets_prepared(prepared, members, data_date, held, params)`. `prepare` takes no params; `run_registry` prepares once per allocator id and refuses two objects sharing an id.

### `strategies.base.Target`
**Fields (observed):** `symbol, weight: Decimal, last: Decimal, limit, stop, take`.

### `lab.store.TrialRow` — `lab/store.py:1282`; `Verdict` — `lab/store.py:1433`; `Gate` — `lab/store.py:1421`

### Side-table pattern — `lab/store.py:323-520`
Each side table is a `_X_TABLE` string plus a `_X_TRIGGERS` tuple (no update, no delete) included in `_SCHEMA`, a frozen `XRow` dataclass, `X_COLUMNS`, `insert_x`, and a reader that returns None when the table does not exist.

### `lab.control_shape` roles — `control_shape.py:415-420`
`ROLE_CONTROL = "control"`, `ROLE_DOSE = "dose"`, `ROLE_IDEA = "idea"`, `ROLE_TREATMENT = "treatment"`.

---

## Dependencies

### Configuration
- `store.DSR_MIN = 0.90`, `store.DSR_POLICY = "methods"`, `tuning.DEV_MAX_DRAWDOWN = 0.50`, `tuning.MIN_PROFIT_FACTOR`, `dev._MIN_TRADES = 100`, `control_shape.REFUSE_BAND = (0.5, 2.0)`, `control_shape.WARN_BAND = (0.8, 1.25)`.

### Environment
- `SEER_LAB_DB`, `SEER_RESEARCH_STORE`; `engine/.research/` (gitignored, 275 MB).

### External Services
- None on these paths. Tests must never reach production (autouse fixture).

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `status = "dev-eligible" if any(...)` | `lab/runner.py:752` | def | engine/lab |
| `failed.append(store.DSR_LABEL)` | `lab/runner.py:611` | def | engine/lab |
| `store.begin_immediate(conn)` in `run_method` | `lab/runner.py:725` | call | engine/lab |
| `TRANSITIONS` | `lab/store.py:123` | def | engine/lab |
| `transitions` trigger | `lab/store.py:679` | def | engine/lab |
| `_SCHEMA` | `lab/store.py:560` | def | engine/lab |
| `best_dev_eligible` | `lab/store.py:1367` | def | engine/lab |
| `verdict` | `lab/store.py:1810` | def | engine/lab |
| `published_verdict` | `lab/store.py:1881` | def | engine/lab |
| `reevaluate_method` | `lab/store.py:2014` | def | engine/lab |
| `funding_of` (absent-table pattern) | `lab/store.py:2294` | def | engine/lab |
| `_snapshot_trial` | `lab/store.py:3178` | def | engine/lab |
| `SNAPSHOT_VERSION = 7` | `lab/store.py:3069` | config | engine/lab |
| `role_of` | `lab/control_shape.py:587` | def | engine/lab |
| `REFUSE_BAND` | `lab/control_shape.py:440` | config | engine/lab |
| `promoted_arm_role` | `lab/hardgate.py:1144` | def | engine/lab |
| `check` (D18 clause) | `lab/hardgate.py:2143` | def | engine/lab |
| `discover` | `lab/method.py:207` | def | engine/lab |
| `config_digest` | `lab/method.py:51` | def | engine/lab |
| `recorded_contributions`, `recorded_capital` | `lab/runner.py:165,177` | def | engine/lab |
| `run_candidate` | `backtest/dev.py:607` | def | engine/backtest |
| `make_row` rate rule | `backtest/dev.py:463` | def | engine/backtest |
| `targets_prepared` call | `backtest/book_runner.py:428` | call | engine/backtest |
| `add_arguments` (lab subparsers) | `commands/lab.py:248` | def | engine/commands |
| `_run`, `_promote`, `_reevaluate` | `commands/lab.py:1922,2181,2233` | def | engine/commands |
| `_arm_roles` | `commands/lab.py:2919` | def | engine/commands |
| `CONDITION_KEYS`, `FAILURE_LABEL`, `conditionOk` | `web/lib/sera/derive.ts:26,37,134` | def | web |
| known-labels assertion | `web/lib/sera/lab.test.ts:60` | test | web |
| `ALIVE_STATUSES` | `web/app/sera/methods/view.ts:31` | def | web |
| `eligibleNow` headline count | `web/app/sera/overview.ts:130` | call | web |
| lab tests | `engine/tests/test_lab_runner.py`, `test_lab_store.py`, `test_lab_hardgate.py`, `test_lab_snapshot.py`, `test_lab_status.py`, `test_lab_gate_wording.py`, `test_lab_control_shape.py`, `labkit.py` | test | engine/tests |
| lab design, latest revision §9 | `docs/plans/2026-10-04-method-lab-design.md:514` | doc | docs |
| lab CLI feature map | `.claude/skills/verify-seer/features/lab-cli.md` | doc | skills |
| explore and Sera skills | `.claude/skills/explore-and-experiment-new-method/`, `.claude/skills/sera-the-explorer/` | doc | skills |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/lab/store.py` — role and yardstick side tables, verdict conditions, the `dev-eligible → rejected` edge, the demotion door, snapshot fields (phases 1, 3, 4, 5)
2. `engine/src/seer_engine/lab/runner.py` — role rows and role-aware status (phase 1); yardstick measurement before the lock and its label (phase 4)
3. `engine/src/seer_engine/lab/yardstick.py` — new module: recorder, twin schedule, draws (phase 2)
4. `engine/src/seer_engine/commands/lab.py` — `lab roles`, `lab reevaluate` demotion (phase 1); `lab yardstick` (phase 3); `lab run` wiring (phase 4)
5. `engine/src/seer_engine/lab/hardgate.py` — yardstick clause in `check` (phase 4)
6. `engine/tests/` — new `test_lab_roles.py`, `test_lab_yardstick.py`, `test_lab_yardstick_record.py`, `test_lab_yardstick_gate.py`; touched `test_lab_runner.py`, `test_lab_store.py`, `test_lab_hardgate.py`, `test_lab_snapshot.py` (phases 1-5)
7. `web/lib/sera/types.ts`, `derive.ts`, `glossary.ts`, `fixture.ts`, their tests, `web/app/sera/methods/[id]/page.tsx`, `web/app/sera/how/view.ts`, `web/data/lab.json` (phase 5)
8. `docs/plans/2026-10-04-method-lab-design.md` — dated revision §10 (phase 4)
9. `.claude/skills/explore-and-experiment-new-method/`, `.claude/skills/sera-the-explorer/`, `.claude/skills/verify-seer/features/lab-cli.md`, `sera.md`, `docs/runbooks/` (phases 3, 4, 5)

**This document describes. The plan files prescribe.**
