# Code Analysis: The unbuilt promotion path

**Type:** Feature Implementation
**Date:** 2026-10-06 11:57:23
**Session ID:** 20261006-115723-B7K2
**Plan:** `BUILD_PROMOTION_PATH_PLAN.md` (4 phases)
**Worktree:** `/home/miftah/.worktrees/seer/build-promotion-path` — branch `feature/build-promotion-path` (base `origin/main` @ `2d03fd1`)

---

## User Input

### Original User Request

```
the unbuilt promotion path
```

### User-Provided Context

No files, no error text. The phrase names a gap this session reported at the end of batch
`sera-20261006-1137`: a method that reaches `dev-eligible` cannot currently be promoted,
because `lab test`, the test-window store and `docs/lab/prereg/` do not exist.

The governing specification is therefore not the prompt but the design document,
`docs/plans/2026-10-04-method-lab-design.md`, §3 (Promotion), §5 (build order) and §6
(the 2026-10-04 owner revision). §5 states the position explicitly:

> `lab test` and the test-window store are specified here and built on first promotion.

So this work is *scheduled*, not *new*: the requirement IDs below are a restatement of §3,
not an invention of this analysis.

**One conflict between sections, resolved by date.** §3 ends "a paper roster entry (new id, own
clock) is the owner's call". §6, the later owner revision, says both skills decide everything
themselves and never ask, naming promotion and "on a test pass, a paper-roster entry with its
own clock" among them. §6 is the revision and governs. (Recorded as decision D1 in the index.)

### User-Provided Files

None.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | A test-window research store the lab can run against — sessions 2015-10-19 → latest, built the way `research.build_store` builds the dev store (same files, manifest and checks), built on first promotion and never before |
| R2 | `python -m seer_engine lab test <candidate>` — refuses unless a pre-registration file exists and is committed, runs **once**, records a `test` trial, sets the method `test-passed` or `test-failed` |
| R3 | Pre-registration: the best dev-eligible variant by MAR, one per method, written to `docs/lab/prereg/MNNNN.md` with id, digest, gate, window and date, committed and pushed **before any test number exists** |

**Not a requirement — already built, verified during this analysis.** The paper-roster half of
§3/§6 exists: `commands/promote.py` (465+ lines) drives it and `lab.store.record_promotion`
(`store.py:395`) records it, including the `('test-passed', 'paper')` transition, idempotence
on re-run, and a `move_status=False` escape for a roster taking a method the lab did not pass.
It was exercised in production on M0005/FND. Phase 4 wires `lab test` to hand off to it; nothing
in it is rebuilt.

---

## Detailed Requirements Understanding

**Problem statement.** The lab can run a method on the dev window and classify it, but the
`dev-eligible → promoted → test-passed|test-failed` segment of the status machine has no code
behind it. The database already models that segment; only the runner, the store and the gate
file are missing.

**What makes this non-trivial** is not the CLI surface. It is that the entire backtest stack is
pinned to a single constant, `DEV_END = 2015-10-16`, which is simultaneously:

- the **dev window's end**, and
- the **D9 safety guard** — the mechanism that makes it impossible to peek at unseen data.

Every public entry point in `backtest/dev.py` refuses input dated after it, and `research.py`
refuses to *load* a store built for a different one. Running the test window therefore means
running the thing the guard exists to prevent. The work is to make the window a parameter
while keeping the guard absolute at every call site that is not an authorised, counted look.

**Success criteria.**

1. A dev `lab run` behaves identically to today — same windows, same digests, same refusals.
   The 110 existing lab/research tests pass unchanged, including the three that pin `DEV_END`.
2. `engine/.research-test` can be built, is gitignored, verifies by fingerprint like the dev
   store, and holds no session before 2015-10-19.
3. `lab test <candidate>` cannot run without a committed pre-registration file, cannot run
   twice (enforced in the database, not only in the command), and leaves the method at
   `test-passed` or `test-failed`.
4. `test-window looks used: k` is correct and visible in `lab status` and the web snapshot.
5. No path exists by which a dev run can read a post-2015-10-16 bar.

**Key constraints, from design §4 guardrails.** Never edit `DEV_END`; never edit design §1/§5;
never delete or rewrite a trial; never touch the test window outside promotion. "Never edit
`DEV_END`" is read here as *never change its value and never weaken what it guards* —
generalising the window while leaving `DEV_END` as the dev binding satisfies both readings, and
is the only reading under which §3 is buildable at all.

**Assumption, stated.** The test window's end is the latest session available from yfinance at
build time, recorded in the manifest, not a fixed date. Design §3 says "2015-10-19 → data end".
A fixed end would go stale and silently change the meaning of a recorded test trial.

---

## Analysis Scope

### Explicitly Mentioned Files

None.

### Discovered Related Files

- `docs/plans/2026-10-04-method-lab-design.md` — §3, §5, §6: the specification
- `engine/src/seer_engine/research.py` (`:63` `DEV_END`, `:67` `STORE_DIR`) — store build/load
- `engine/src/seer_engine/backtest/dev.py` (`:53` `DEV_END`) — D9 guards, candidate windows
- `engine/src/seer_engine/lab/store.py` — schema, statuses, trial insert, `test_looks`
- `engine/src/seer_engine/lab/runner.py` — `lab run`'s dev pipeline, the model for `lab test`
- `engine/src/seer_engine/commands/lab.py` — CLI subcommand wiring
- `engine/src/seer_engine/commands/research_store.py` — store build CLI
- `engine/src/seer_engine/commands/promote.py` — paper roster (exists, reused)
- `engine/tests/test_research_store.py`, `test_fundamentals_coverage.py` — the `DEV_END` pins
- `engine/data/sp500_history.csv`, `ndx_history.csv`, `spy_dividends.csv` — test-window inputs

---

## Current Dataflow

### Entry Point: `python -m seer_engine lab run MNNNN`

**Location:** `engine/src/seer_engine/commands/lab.py:64` (subparser) → `lab/runner.py:196`
**Trigger:** CLI, one method id.

1. `runner.preflight()` (`runner.py:48`) — refuses an uncommitted method file (the commit is the
   pre-registration), refuses a method that already ran, refuses any candidate whose
   `config_digest` already has a `dev` trial (`store.has_trial`, `runner.py:65`).
2. `runner.preflight_data()` (`runner.py:86`) — coverage check.
3. `research.load_store(STORE_DIR)` → `ResearchData`.
4. `dev.run_registry(market, dividends, spy_dividends, candidates, on_result=…)`
   (`runner.py:218` → `dev.py:413`). Per candidate: `candidate_window(market, c)` returns
   `(start, DEV_END)`; **every input is checked against `DEV_END` first**.
5. `runner.trial_rows()` (`runner.py:136`) — DSR per trial with
   `n_trials = store.dev_trial_count(conn) + len(results)` (`runner.py:148`), i.e. lab-wide N.
6. `store.insert_trials()` with `window="dev"` (`runner.py:167`).
7. Status → `dev-eligible` if any trial eligible, else `rejected` (`runner.py:223`).

### The D9 guard — the central obstacle

**Location:** `engine/src/seer_engine/backtest/dev.py:53`

```python
DEV_END = date(2015, 10, 16)  # last dev session; 2015-10-19 opens the P7b test window
```

Enforced at `dev.py:84` (`check_dev_session`), `:95` (bars), `:109`/`:118` (dividends),
`:97` (FX), `:215` (`candidate_window`, which returns `(start, DEV_END)` as the hard end).
Each raises `DevWindowError`. **A `Market` holding one 2015-10-19 bar fails every one of them**,
so the test window is unreachable without changing this module.

**The constant is duplicated and pinned.** `research.py:63` carries its own copy, commented
`# == backtest.dev.DEV_END (phase 9 tests the equality)`, and
`engine/tests/test_fundamentals_coverage.py:107` asserts
`coverage.WINDOW_END == dev.DEV_END == research.DEV_END`. Any change must keep that equality
true, which rules out redefining either constant and argues for adding a window *parameter*
alongside them.

### `research.py` — DEV_END is woven through the store, not just its edge

`load_store` (`:633`) raises when the manifest "was built for another DEV_END or STORE_START",
and re-checks at data level that no bar, dividend or FX row is after `DEV_END`. The manifest
records `dev_end` (confirmed in the live store: `"dev_end": "2015-10-16"`).

Four further functions bake the window in:

| Function | Location | What it does with `DEV_END` |
|---|---|---|
| `_overlaps_window` | `:156` | `iv.start_date <= DEV_END and (end is None or end > MEMBERSHIP_START)` |
| `requested_symbols` | `:160` | ETFs ∪ members overlapping `[MEMBERSHIP_START, DEV_END]` |
| `research_membership` | `:166` | keeps overlapping intervals; **an end after `DEV_END` becomes `None`** |
| `unserved_by_year` | `:183` | iterates `MEMBERSHIP_START.year .. DEV_END.year` |
| `UNSERVED_REASON` | `:98` | an f-string embedding `STORE_START..DEV_END` |

`research_membership`'s clamp is the subtle one. For the dev store, "a membership interval
ending after `DEV_END` becomes open-ended" is correct — the company is a member on every dev
session. Reused unchanged for a test store it would be **wrong**: a company that left the index
in 2018 would read as a member through 2026. The test store needs the same clamp against *its
own* window end.

**Universe selection differs too.** `requested_symbols` returns ever-members of
`[1996-01-02, 2015-10-16]`. The test window's members are a different set — every company that
joined the S&P 500 after October 2015 is absent from it. A test store built on the dev universe
would hold a stale index and quietly bias the one look we get.

### Data availability — the test window is buildable

| Input | Coverage | Verdict |
|---|---|---|
| `engine/data/sp500_history.csv` | 1996-01-02 → **2026-08-18** (517 rows after `DEV_END`) | sufficient |
| `engine/data/ndx_history.csv` | present | sufficient |
| `engine/data/spy_dividends.csv` | **2015-03-20 → 2026-09-18** | covers the whole test window |
| Daily bars | yfinance, same call shape as the dev build | available |
| USD/IDR FX | Frankfurter, same as dev | available |

Nothing needs Neon. The build is a crawl of the same shape as the dev store's.

### `lab/store.py` — the database half is already built

This is the significant finding for scope. Already present and tested:

| Capability | Location |
|---|---|
| `WINDOWS = ("dev", "test")` | `:75` |
| `UNIQUE(config_digest, window)` and `UNIQUE(candidate_id, window)` | `:169`, `:170` |
| statuses `promoted`, `test-passed`, `test-failed`, `paper` | `:57`, `:71`, `:72`, `:73` |
| forward-only status trigger | `:195` |
| append-only trials (UPDATE/DELETE refused) | `:186`, `:189` |
| `has_trial(conn, digest, window)` | `:525` |
| `insert_trials` rejecting an unknown window and a duplicate | `:534`–`:544` |
| `test_looks(conn)` | `:558`, surfaced at `:669` and in the snapshot at `:833` |
| `record_promotion` incl. `test-passed → paper` | `:395` |

**"The database refuses a second look" (§3) is already true**: `UNIQUE(config_digest, window)`
plus the append-only triggers enforce it at the schema level. No migration is required.

### Exit points / state

- **Database:** `lab/lab.sqlite` — one appended `trials` row (`window='test'`), one `methods`
  status move, analysis growth. Never rewritten (triggers).
- **Filesystem:** `engine/.research-test/` (gitignored), `docs/lab/prereg/MNNNN.md` (committed).
- **Web:** `web/data/lab.json` via `lab stage`; `testLooks` already wired (`store.py:833`).

---

## Key Data Structures

### `TrialRow` — `engine/src/seer_engine/lab/store.py:487`
Carries `window: str` (`:496`) already. A test trial is the same row with `window="test"`.
**Open point for phase 4:** `n_trials_at_run` and DSR on a test trial. `runner.py:148` counts
**dev** trials only (`store.dev_trial_count`), and `store.dev_daily_sharpes` feeds the variance
term. A test trial is not part of the multiple-testing count — it is the out-of-sample check on
one already-counted configuration — so it must not increment N. Decision D2 in the index.

### `ResearchData` / manifest — `research.py:129`
Manifest keys observed live: `files` (per-file sha256), `fingerprint`, `dev_end`, `store_start`,
`bar_rows`, `dividend_rows`, `fx_rows`, `symbols_requested`, `symbols_served`.
A test manifest needs a window identity that `load_store` can verify and refuse to confuse with
a dev store — otherwise a mis-pointed `SEER_RESEARCH_STORE` runs the dev pipeline on test data.

---

## Dependencies

**Configuration / environment:** `SEER_LAB_DB`, `SEER_RESEARCH_STORE` (used by Sera's children);
`research.STORE_DIR` default `engine/.research`. A test store needs its own env/flag path.
**External services:** yfinance (bars), Frankfurter (FX) — build time only; `load_store` is
offline by contract.
**Gitignore:** `engine/.research` is ignored; `engine/.research-test` must be added.

---

## Reference List — every site bound to the window

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `DEV_END` | `backtest/dev.py:53` | def | backtest |
| `check_dev_session` | `backtest/dev.py:84` | guard | backtest |
| bar guard | `backtest/dev.py:95` | guard | backtest |
| FX guard | `backtest/dev.py:97` | guard | backtest |
| dividend guards | `backtest/dev.py:109`, `:118` | guard | backtest |
| `candidate_window` | `backtest/dev.py:215` | def | backtest |
| `run_candidate` | `backtest/dev.py:392` | def | backtest |
| `run_registry` | `backtest/dev.py:413` | def | backtest |
| `DEV_END` | `research.py:63` | def (pinned equal) | research |
| `UNSERVED_REASON` | `research.py:98` | const | research |
| `_overlaps_window` | `research.py:156` | def | research |
| `requested_symbols` | `research.py:160` | def | research |
| `research_membership` | `research.py:166` | def | research |
| `unserved_by_year` | `research.py:183` | def | research |
| `build_store` | `research.py` (CLI `commands/research_store.py:161`) | def | research |
| `load_store` | `research.py:633` | def | research |
| `STORE_DIR` | `research.py:67` | const | research |
| `DEV_END` equality assert | `tests/test_fundamentals_coverage.py:107` | test | tests |
| `DEV_END` value assert | `tests/test_research_store.py:152` | test | tests |
| post-`DEV_END` refusal | `tests/test_research_store.py:412` | test | tests |
| `preflight` | `lab/runner.py:48` | def | lab |
| dev-trial N | `lab/runner.py:148` | call | lab |
| `window="dev"` | `lab/runner.py:167` | call | lab |
| CLI subparsers | `commands/lab.py:60`–`:121` | wiring | commands |
| `test_looks` | `lab/store.py:558` | def (exists) | lab |
| `record_promotion` | `lab/store.py:395` | def (exists) | lab |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/backtest/dev.py` — window becomes a parameter defaulting to
   `DEV_END`; guards check against the passed end. **Phase 1.**
2. `engine/src/seer_engine/research.py` — window threaded through universe, membership clamp,
   unserved tally, build and load; manifest gains a window identity. **Phase 1, 2.**
3. `engine/src/seer_engine/commands/research_store.py` — a flag to build the test store.
   **Phase 2.**
4. `.gitignore` — `engine/.research-test`. **Phase 2.**
5. `docs/lab/prereg/` (new) + writer/validator — **Phase 3.**
6. `engine/src/seer_engine/lab/runner.py` — a test-window runner beside the dev one. **Phase 4.**
7. `engine/src/seer_engine/commands/lab.py` — `promote` and `test` subcommands. **Phases 3, 4.**
8. `engine/tests/` — new tests per phase; the three `DEV_END` pins must keep passing unchanged.

**This document describes. The plan files prescribe.**
