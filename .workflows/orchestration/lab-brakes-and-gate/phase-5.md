# Phase 5: Pre-register, run, record, stage and write up

**Plan set:** `LAB_BRAKES_AND_GATE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-124247-B4K9_code_analyzer.md`
**Satisfies:** R1 (the brakes-off variants become recorded lab trials) — R2 (the shared SPY 200-day
gate is interrogated, on two books and across the roster) — **R3** (the hard constraint is *held*
here, not just built: Steps 2 and 8 read `store.gate`, `store.pending_gate` and
`npolicy.dev_method_count` before and after six real trials on the real committed database, and
that before/after pair is R3's only end-to-end evidence; phase 1 proves the property on a tmp
fixture — reconciler, C19) — R4 (the usual lab rules are held while doing it: the commit is the
pre-registration, `lab stage` for any database commit, Postgres for the suite, no hard-gate
override, the test window is never touched)
**Depends on:** Phase 2 (`lab gate`), Phase 3 (M0030's amendment block), Phase 4 (M0053's new
params dataclass, new allocator and amendment block) — and, transitively through all three,
Phase 1 (the amendment mechanism and `lab run --amend`)
**Difficulty:** NORMAL
**Package:** `lab/`, `docs/backtests/`, `web/data/`

---

## Goal

After this phase the lab **holds** the two configurations the exposure diagnostic found and could
not record: M0030's residual-momentum satellite at full size, and M0053's overnight book with the
weekly brake off — each pre-registered by a commit, run on the dev window, and recorded as trials
under their own existing method ids. The shared SPY 200-day gate is recorded three more ways
(`M0030-SAT100-NOGATE`, `M0030-C50A-NOGATE`, `M0053-RESON20-TV16-NOGATE`) and priced across the
whole roster by `lab gate`. And the number that made all of this worth doing is measured before and
after and written down: **the luck hurdle did not move.** `store.gate(conn)` reads `Gate(n=74,
policy='methods')` on both sides of six new trials.

**This phase writes no Python and edits no engine source.** It commits files phases 3 and 4 wrote,
runs commands phases 1 and 2 built, reads the answer, writes prose, and commits the database
through `lab stage`.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Deletes:** none
**Renames:** none

**Creates:**

- `docs/backtests/2026-10-12-brakes-and-gate.md` — the write-up. Named to this directory's
  convention (`YYYY-MM-DD-slug.md`, as `2026-10-12-exposure-diagnostic.md` and
  `2026-10-08-how-many-names.md` are).
- `docs/backtests/2026-10-12-brakes-and-gate-grid.csv` — **committed**, the six new trials at full
  precision, exported read-only from `trials` + `trial_funding` + `trial_provenance` + `trial_moments`.
- `docs/backtests/2026-10-12-brakes-and-gate-gate-grid.csv` — **committed, unconditionally.**
  Phase 2 ships `--csv PATH` (reconciler, C11; confirmed against phase 2's Step 3 subparser and
  its `_gate` handler, which calls `gp.write_csv(reports, run, Path(args.csv))`). This is the
  machine-readable half of R2's lab-wide pricing and it is a deliverable, not a conditional.
- **6 new rows in `trials`** — `n` 359..364, three under `method_id = 'M0030'` and three under
  `method_id = 'M0053'`, written by `lab run --amend`. Nothing else writes a trial in this phase.
- 6 new rows in `trial_provenance`, 6 in `trial_moments`, and 6 in `trial_funding` (every one of
  these six runs is funded; see **The funding caveat** below).
- 1 new row in `method_amendments` per method (2 rows) — written by phase 1's `run_method`
  amendment path, not by hand.
- `insights` rows: whatever `lab gate` journals for itself (expect one `observation` per method it
  prices, unless `--no-journal`), plus **exactly two** written by hand with `lab insight`: one
  `observation` carrying the N check before/after, and one `synthesis` carrying the finding.
- `web/data/lab.json` — **regenerated wholesale** by `lab stage`.

**Signature changes:** none.

**Requires (from earlier phases) — this phase is written against these and does not guess them:**

- **Phase 1:** `lab run --amend MNNNN` exists and
  1. accepts a method whose status is `dev-eligible` instead of refusing with
     *"{id} is already dev-eligible: a method runs once"*;
  2. records the new trials under the **existing** `method_id`, so
     `store.pending_gate(conn, 'M0030', 3)` stays `Gate(74)`;
  3. leaves `methods.source_sha` exactly as it is (trigger `methods_source_sha_once`,
     `store.py:490`) and appends the amendment's own sha to `method_amendments`;
  4. **never writes `methods.status` on the amendment path — phase 1's Decision P2.** This plan
     filed it as the most likely way the phase dies; the reconciler verified phase 1 and it is
     **already resolved** (C2). The risk was real: `runner.run_method` (`runner.py:492`) computes
     `status = "dev-eligible" if any(r.trial.eligible for r in ran) else "rejected"`, both M0030
     and M0053 read `dev-eligible` today, `store.TRANSITIONS` (`store.py:92-113`) has **no**
     `dev-eligible -> rejected` edge, and the trigger `methods_status_forward` (`store.py:477`)
     raises `ABORT 'method status may only move forward along TRANSITIONS'`. D5 predicts exactly
     that input — all six candidates ineligible on max drawdown — so an unpinned status would
     abort the whole insert transaction and record nothing.

     Phase 1 closes it at the source. Its `run_method` keeps the `status` computation (the CLI
     prints it) but calls `store.update_method(..., source_sha=..., status=status)` **only on the
     `if amendment is None` branch**; on the amendment branch it writes a `method_amendments` row
     and touches neither column. Its Decision P2 states the reason — `store.reevaluate_method` is
     the one door on `rejected -> dev-eligible` and it has its own guards and its own appended
     analysis, so letting `run_method` take that decision would put a second, silent door beside
     it. Its `test_an_amendment_records_its_sha_and_leaves_methods_source_sha_alone` asserts
     `status == status_before` across an amendment run.

     **What this phase checks, rather than fears:** Step 6 and Step 7 read the status back after
     each run and assert it is still `dev-eligible`. If either run instead aborts on the status
     trigger, P2 did not hold and it is a phase 1 defect — stop and report, do not patch
     `runner.py`. The failure table below keeps the branch for that reason; it is a verification,
     not a predicted outcome.
- **Phase 2:** `lab gate` exists, is report-only, and writes at most `insights` rows. Its surface,
  confirmed by the reconciler against phase 2's Step 3 subparser (C11):

  ```
  python -m seer_engine lab [--db PATH] gate [IDS...] [--all] [--only IDS] [--store DIR]
                                             [--csv PATH] [--gated-only] [--no-journal] [--dry-run]
  ```

  `IDS` is `nargs="*"` and exactly one of positional ids or `--all` must be given. `--csv` exists,
  so Step 9's gate grid is unconditional. Step 9 still reads `--help` first, as a cheap check that
  the phase that landed matches the phase that was planned — but it no longer branches on it.
- **Phase 3:** `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py` carries one
  `Amendment` dated 2026-10-12 with exactly the three candidates `M0030-SAT100`,
  `M0030-SAT100-NOGATE`, `M0030-C50A-NOGATE`, its own hypothesis and its own expected-failure text,
  and the file's existing three recorded candidates untouched.
- **Phase 4:** `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py` carries
  a new frozen params dataclass, a new allocator with a unique `id`, and one `Amendment` dated
  2026-10-12 with exactly `M0053-TOTON20-NOBRAKE`, `M0053-RESON20-NOBRAKE`,
  `M0053-RESON20-TV16-NOGATE`; `WeeklyOnParams`, `WeeklyOvernightAllocator`, `WEEKLYON`, `TOTON20`,
  `TOTON30` and the five recorded candidates untouched.
- All four phases are merged onto `feature/lab-brakes-and-gate`, `ruff check engine` is clean and
  `pytest engine/tests` is green with Postgres up.

**Leaves alone (owned by others):**

- Everything under `engine/src/` and `engine/tests/` — phases 1-4. **Hard stop rule:** if a run
  exposes a bug in any of them, report it and stop. Do not edit engine source from this phase; a
  fix is a follow-up commit on top of the owning phase, not a silent amendment here.
- `engine/src/seer_engine/commands/lab.py`'s ten `Lab N (dev trials) is now …` strings
  (`commands/lab.py:1399, 1684, 1718, 1739, 1785, 1817, 1870, 1923, 2238, 2287`). `lab run` prints
  one of them at `:1399` on every run in this phase. It will say **357** and then **360** (354 dev
  trial rows today, plus three per run), which is the row count, **not** the gate's N (74). Quote it in the transcript, never in the write-up, and never
  "fix" it — R5 and phase 6 own it.
- `docs/plans/2026-10-04-method-lab-design.md` and
  `docs/plans/2026-10-12-lab-n-and-amendments-owner-decision.md` — phase 6.
- `docs/plans/LAB_BRAKES_AND_GATE_PLAN.md` — the coordinator/reconciler.
- `.workflows/todos.md` — see **Handoffs**.

---

## Absolute prohibitions, restated as executable rules

These come from the owner's own words and bind every step below.

| Rule | How this plan holds it |
|---|---|
| **Never touch the test window** | No `lab test` and no `lab promote` appears anywhere below. `lab promote` is doubly forbidden: it writes a pre-registration into `docs/lab/prereg/` and is the gateway to a look. `engine/.research-test` is never named; every store-taking command passes `--store /home/miftah/seer/engine/.research`, which `research.load_store` refuses if its window is not `research.DEV_WINDOW`. Step 13 asserts `store.test_looks(conn) == 4` and `git status --short docs/lab/` is empty. |
| **No hard-gate override** | `lab walkforward` is *read* at Step 10 for the write-up's durability section. `hardgate` is not called, not configured, not bypassed, and `MIN_FOLDS` is not touched. If the methods lose their folds, that is the result and it goes in the write-up. |
| **No new method id** | `lab next-id` appears nowhere. Every trial lands under `M0030` or `M0053`. Step 8 and Step 11 prove `dev_method_count` is still 74. |
| **`lab stage` for any database commit** | `git add lab/lab.sqlite` appears nowhere. Step 12 runs `lab stage`, which writes `web/data/lab.json` and git-adds both under an exclusive lock (`commands/lab.py:2381`). CI checks the two agree row for row. |

---

## Environment, fixed for every command below

Set this once; every step assumes it.

```bash
export WT=/home/miftah/.worktrees/seer/lab-brakes-and-gate
export PY=/home/miftah/seer/engine/.venv/bin/python
export RUFF=/home/miftah/seer/engine/.venv/bin/ruff
export STORE=/home/miftah/seer/engine/.research     # NOT in the worktree. Never rebuilt.
export PYTHONPATH=$WT/engine/src                     # or the CLI and pytest silently use main
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
export RUNDIR=/tmp/brakes-and-gate-20261012          # transcripts; never committed
mkdir -p "$RUNDIR"
cd "$WT"
```

Why each:

- **`PYTHONPATH=$WT/engine/src`** — without it the main checkout's `seer_engine` is imported,
  `lab run --amend` and `lab gate` do not exist there, and `pytest` silently tests `main`. It also
  makes `config.REPO_ROOT` resolve to **this worktree**, so `store.DB_PATH` is `$WT/lab/lab.sqlite`
  and `store.snapshot_path` is `$WT/web/data/lab.json`. That is what we want.
- **`STORE`** — the research store is not in worktrees. Dev store, fingerprint `77c37d553508…`,
  prices `5451195f…`. **Never rebuild it on a fingerprint mismatch alone**: a rebuild costs ~30
  minutes and drops `market_series.csv` and `dividend_announcements.csv`. If `hardgate.pin_dev_store`
  refuses the store's *price* fingerprint, that is a real refusal — stop and report, do not rebuild.
- **`RUNDIR` under `/tmp`** — transcripts are working material. Use the session scratchpad if you
  have one; the only rule is that it is **not** inside `$WT`.

`SEER_LAB_DB` and `SEER_RESEARCH_STORE` are **unset and must stay unset**: `--store` is passed
explicitly and the database we want is this worktree's own `lab/lab.sqlite`.

Postgres must be up or CI fails on the skip:

```bash
docker start seer-pg || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
```

---

## Baseline, measured 2026-10-12 on this worktree at base commit `d3c1ec4`

Taken with a `mode=ro` connection, so the act of reading did not migrate the file.

| Thing | Value |
|---|---|
| `lab/lab.sqlite` md5 | `4a34ddb823ec88a5e86afeb5d7e1b7c9` |
| `lab/lab.sqlite` blob on `origin/main` | `232b3d8f02acc70c75d9612840e654e20d19998d` |
| `store.gate(conn)` | `Gate(n=74, policy='methods')` |
| `npolicy.dev_method_count(conn)` | `74` |
| `store.pending_gate(conn, 'M0030', 3)` | `Gate(n=74, policy='methods')` |
| `store.pending_gate(conn, 'M0053', 3)` | `Gate(n=74, policy='methods')` |
| `store.dev_trial_count(conn)` | `354` (ROWS) |
| `store.test_looks(conn)` | `4` |
| `trials` (all windows) | `358`, `max(n) = 358` |
| `trial_moments` / `trial_funding` / `trial_provenance` | `244` / `230` / `358` |
| `insights` | `190`, `max(id) = 190` |
| `methods` | `130` — idea 50, rejected 59, dev-eligible 15, test-failed 4, blocked-data 2 |
| `M0030` | status `dev-eligible`, `source_sha` `3b6aad38e1f1…` |
| `M0053` | status `dev-eligible`, `source_sha` `2289c49024df…` |

### The recorded trials these amendments sit beside

```
M0030-C70T  n=126  initial 20,000,000 IDR  UNFUNDED  dd 18.77%  pf 3.699  trades 1614  eligible 0
M0030-C50T  n=127  initial 20,000,000 IDR  UNFUNDED  dd 18.56%  pf 2.793  trades 1615  eligible 0
M0030-C50A  n=128  initial 20,000,000 IDR  UNFUNDED  dd 33.98%  pf 2.118  trades 1606  eligible 0
M0053-TOTON20-TV14 n=167  10,000,000 IDR  funded  dd 16.33%  pf 2.117  trades 1100  eligible 1
M0053-TOTON20-TV16 n=168  10,000,000 IDR  funded  dd 18.78%  pf 2.159  trades 1100  eligible 1
M0053-TOTON20-TV18 n=169  10,000,000 IDR  funded  dd 21.04%  pf 2.127  trades 1100  eligible 0
M0053-TOTON30-TV16 n=170  10,000,000 IDR  funded  dd 18.99%  pf 2.268  trades 1551  eligible 1
M0053-RESON20-TV16 n=171  10,000,000 IDR  funded  dd 17.53%  pf 1.829  trades 1500  eligible 1
```

### **The funding caveat — read this before writing one number of the write-up**

`trial_funding` holds rows for `trial_n` **129..358 only** (230 rows). **M0030's three recorded
trials (126, 127, 128) carry no funding row at all**: they were lump-sum runs of 20,000,000 IDR,
recorded before the lab runner was funded on 2026-10-08. M0053's five (167..171) are funded at
10,000,000 IDR plus 5,000,000 IDR on the 25th of each month, 237 deposits.

The six trials this phase records all run at today's `backtest.runner.INITIAL_IDR` =
**10,000,000 IDR on the owner's real schedule**, funded. Therefore:

- **M0053's three amendment candidates are directly comparable** to M0053's five recorded ones:
  same capital, same schedule, same cost model. Compare them freely.
- **M0030's three amendment candidates are NOT comparable to M0030's recorded C70T/C50T/C50A**, and
  they are **not comparable to the exposure grid's `M0030-*-FULL` row either** — that row
  (`+7.5` whole, `+2.7` for 2009–2015, **20.4% worst fall**, 15.4%/yr) was measured unfunded at
  20,000,000 IDR, because the diagnostic re-runs each trial at *its own recorded* capital and
  funding. D5's prediction of "20.4% against a 20% bar" is a **lump-sum** figure. The funded
  version may land either side of 20%. Say so in the write-up, and never put a funded return and
  an unfunded one in the same column.
- Report the **money-weighted return against deposit-matched SPY** (`trial_funding.mwr` vs
  `trial_funding.spy_tr_mwr`), not CAGR. A funded book's CAGR is a lie.

### What D5 predicts, and the exact rows it was read from

From the committed `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv`, the `full` arm:

| source row | worst fall | profit factor | trades | 2009–2015 lead | return/yr | funded? |
|---|---:|---:|---:|---:|---:|---|
| `M0030-C70T / C50T / C50A` — all three identical | **20.408%** | 2.113 | 1607 | **+2.65** | 15.44% | no, 20M |
| `M0053-TOTON20-TV14 / TV16 / TV18` — all three identical | **22.788%** | 2.374 | 1100 | **+0.82** | 14.88% | yes, 10M |
| `M0053-RESON20-TV16` | **22.414%** | 2.024 | 1500 | **+0.54** | 14.41% | yes, 10M |
| `M0053-TOTON30-TV16` (not a candidate here) | 23.624% | 2.406 | 1551 | −0.93 | 13.54% | yes, 10M |

Against `tuning.MAX_DRAWDOWN = 0.20`, `tuning.MIN_PROFIT_FACTOR = 1.3`, `dev._MIN_TRADES = 100`
and `store.DSR_MIN = 0.90`: every candidate clears beats-SPY, profit factor and trade count, and
**every one is predicted to breach max drawdown** — M0030's by about 0.4 points (on an unfunded
measurement), M0053's by 2.4 to 2.8. That prediction is what phases 3 and 4 wrote into their
`expected_failure`. **The result is the finding, either way round.**

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py` | **commit only** | Phase 3 wrote it. This phase makes its commit, which is the pre-registration. Not edited here. |
| `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py` | **commit only** | Phase 4 wrote it. Same. Not edited here. |
| `lab/lab.sqlite` | modify (append-only) | 6 `trials` (359–364), 6 `trial_provenance`, 6 `trial_moments`, 6 `trial_funding`, 2 `method_amendments`, and the `insights` `lab gate` writes plus 2 written by hand. Two `methods.analysis` appends and two `methods.verdict` updates. **No `source_sha` rewrite, no backwards status move, no row deleted.** |
| `web/data/lab.json` | regenerate | by `lab stage`, from the database above. Never edited by hand. |
| `docs/backtests/2026-10-12-brakes-and-gate.md` | create | the write-up (skeleton below) |
| `docs/backtests/2026-10-12-brakes-and-gate-grid.csv` | create | the six new trials at full precision |
| `docs/backtests/2026-10-12-brakes-and-gate-gate-grid.csv` | create | `lab gate --csv` output. Unconditional — phase 2 ships `--csv` (reconciler, C11). |

**Seven files at most**, and nothing else may appear in any commit of this phase. `git diff --cached
--name-only` is checked before each of the four commits.

---

## Ordering constraints (stated explicitly, because they are not negotiable)

1. Phases 1–4 are merged onto the branch and the suite is green. **Step 0.**
2. The two method files are **committed** — by pathspec, never `git add -A`; this repo runs
   parallel sessions sharing one index. **Step 4 and Step 5.** The commit *is* the
   pre-registration: `runner.registry_problem` refuses an uncommitted or dirty method file.
3. `lab run --amend M0030`, then `lab run --amend M0053`, **serially**. They share `lab.sqlite`
   and `insert_trials` takes a write transaction; two at once is a lock fight, or worse, two
   interleaved `n` sequences. **Step 6 and Step 7.**
4. `lab gate`, `lab walkforward`, the journal entries and the verdicts. **Steps 9, 10, 11.**
5. `lab stage`, then the database commit. **Step 12.**
6. The write-up commit. **Step 13.**

---

## Implementation Steps

### Step 0: Gate — phases 1–4 landed, and the tree is green

**File:** none — this is a gate.
**Change:** refuse to start until everything this phase depends on is actually on the branch.

```bash
cd "$WT"
git status --short
git log --oneline -12
$PY -c "import pathlib,sys; sys.exit(0)"

# Phase 1: the amendment mechanism
grep -n "amend" engine/src/seer_engine/commands/lab.py | head
grep -n "class Amendment\|amendments" engine/src/seer_engine/lab/method.py | head
grep -n "method_amendments" engine/src/seer_engine/lab/store.py | head

# Phase 2: the gate probe
test -f engine/src/seer_engine/lab/gate_probe.py && echo "gate_probe.py: present" || echo "MISSING"

# Phases 3 and 4: the amendment blocks
grep -n "SAT100\|C50A-NOGATE" engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py
grep -n "NOBRAKE\|RESON20-TV16-NOGATE" engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py
```

Then read the **live** CLI surfaces rather than trusting this plan's spelling of them:

```bash
cd "$WT" && $PY -m seer_engine lab run --help
cd "$WT" && $PY -m seer_engine lab gate --help
```

**The commands in Steps 6, 7 and 9 are written against phases 1 and 2's frozen contracts.** This
`--help` read is belt and braces. If `--help` shows a different spelling, **use what `--help`
prints**, record the difference under **Drift** in the report, and say so: a surface that moved
after its phase landed is a finding about that phase, not a licence to improvise. Do not invent a
flag `--help` does not show.

Prove the tree is green before putting anything in the database:

```bash
docker start seer-pg
cd "$WT" && $RUFF check engine
cd "$WT" && $PY -m pytest engine/tests -n auto 2>&1 | tail -20
```

**Expected:** ruff clean (CI lints bugs only: E9 and F, minus F401); pytest green. The suite was
**4364 passed / 3 skipped** on `main` @ `d3c1ec4`; phases 1–4 add tests, so expect more passes and
**exactly 3 skips** (the opt-in live-store tests). **More than 3 skips means Postgres is not
reachable — CI fails on that.** Re-measure the number; do not carry 4364 forward as an assertion.

A lab subcommand migrates `lab/lab.sqlite` on connect even for a read, and `lab run --help` may
have done so. Restore it by explicit path before the baseline is taken:

```bash
cd "$WT" && git status --short lab/lab.sqlite && git checkout -- lab/lab.sqlite && md5sum lab/lab.sqlite
```

**Expected:** `4a34ddb823ec88a5e86afeb5d7e1b7c9`.

**On failure:** if any phase artefact is missing, `--help` fails, the suite is red, or the md5 is
not `4a34ddb8…` — **stop and report.** Everything downstream writes to an append-only database.

**Impact:** nothing written.

---

### Step 1: Confirm `lab/lab.sqlite` has not moved on `origin/main`

**File:** none — this is a gate.
**Change:** another session's rows must not be clobbered by this branch's copy.

```bash
cd "$WT"
git fetch origin          # fetch ONLY. Never `git pull --rebase` here.
git rev-parse origin/main:lab/lab.sqlite
```

**Expected:** `232b3d8f02acc70c75d9612840e654e20d19998d`.

If it prints anything else, `origin/main` has a newer lab database than this branch's copy.
**STOP and report.** Do not merge, do not rebase, do not write. Committing this branch's older
`lab/lab.sqlite` silently deletes whatever rows the other session recorded. **A rebase replays a
stale `lab.sqlite`**: if a push is later rejected and you `pull --rebase`, the live shared database
other sessions are writing gets overwritten — re-run `lab stage` afterwards and check trial `n` is
contiguous (Step 14).

**Impact:** nothing written. This is the only cheap moment to catch a clobber.

---

### Step 2: The N check, BEFORE — the headline deliverable, first reading

**File:** writes `$RUNDIR/n-before.txt` and `$RUNDIR/counts-before.txt`.
**Change:** none. Read-only, `mode=ro`, so the file is not migrated.

Write the probe once; it is used again at Steps 8 and 11 unchanged.

```bash
cat > "$RUNDIR/ncheck.py" <<'PY'
import sqlite3, sys
from seer_engine.lab import store, npolicy

db = sys.argv[1]
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
print("gate                :", store.gate(conn))
print("dev_method_count    :", npolicy.dev_method_count(conn))
print("pending M0030 k=3   :", store.pending_gate(conn, "M0030", 3))
print("pending M0053 k=3   :", store.pending_gate(conn, "M0053", 3))
print("dev_trial_count     :", store.dev_trial_count(conn))
print("test_looks          :", store.test_looks(conn))
conn.close()
PY

cd "$WT" && $PY "$RUNDIR/ncheck.py" "$WT/lab/lab.sqlite" | tee "$RUNDIR/n-before.txt"
```

**Expected output, exactly — this was measured on this worktree on 2026-10-12:**

```
gate                : Gate(n=74, policy='methods')
dev_method_count    : 74
pending M0030 k=3   : Gate(n=74, policy='methods')
pending M0053 k=3   : Gate(n=74, policy='methods')
dev_trial_count     : 354
test_looks          : 4
```

A `mode=ro` connection cannot migrate the database; `store.gate`, `store.pending_gate`,
`npolicy.dev_method_count`, `store.dev_trial_count` and `store.test_looks` are all pure SELECTs.
`conn.row_factory = sqlite3.Row` is required (`npolicy._dev_curves` reads rows by name).

And the full table census, same connection style:

```bash
cd "$WT"
sqlite3 "file:lab/lab.sqlite?mode=ro" <<'SQL' | tee "$RUNDIR/counts-before.txt"
.mode list
.headers off
SELECT 'trials',           count(*) FROM trials;
SELECT 'max_trial_n',      coalesce(max(n),0) FROM trials;
SELECT 'dev_trials',       count(*) FROM trials WHERE window = 'dev';
SELECT 'test_looks',       count(*) FROM trials WHERE window = 'test';
SELECT 'distinct_dev_methods', count(DISTINCT method_id) FROM trials WHERE window = 'dev';
SELECT 'trial_moments',    count(*) FROM trial_moments;
SELECT 'trial_funding',    count(*) FROM trial_funding;
SELECT 'trial_provenance', count(*) FROM trial_provenance;
SELECT 'insights',         count(*) FROM insights;
SELECT 'max_insight_id',   coalesce(max(id),0) FROM insights;
SELECT 'methods_total',    count(*) FROM methods;
SELECT 'methods:' || status, count(*) FROM methods GROUP BY status ORDER BY status;
SELECT 'M0030_sha',        substr(source_sha,1,12) FROM methods WHERE id = 'M0030';
SELECT 'M0053_sha',        substr(source_sha,1,12) FROM methods WHERE id = 'M0053';
SQL
md5sum lab/lab.sqlite | tee -a "$RUNDIR/counts-before.txt"
```

**Expected:** the Baseline table above, exactly — `trials|358`, `max_trial_n|358`,
`dev_trials|354`, `test_looks|4`, `distinct_dev_methods|74`, `insights|190`, `max_insight_id|190`,
`M0030_sha|3b6aad38e1f1`, `M0053_sha|2289c49024df`, md5 `4a34ddb8…`.

**On failure:** any line differing from the Baseline means the working copy is not at the base
state. **STOP and report**; reconcile before writing.

**Impact:** none. These two files are the evidence Steps 8, 11 and 14 diff against.

---

### Step 3: Prove the six digests are free, and the eight recorded ones unchanged

**File:** writes `$RUNDIR/digests.txt`.
**Change:** none. Read-only.

Two separate things are checked here, and both are cheap insurance against a wasted run.

```bash
cat > "$RUNDIR/digests.py" <<'PY'
import sqlite3, sys
from seer_engine.lab.method import config_digest, discover

db = sys.argv[1]
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
methods = discover()

NEW = {
    "M0030": ("M0030-SAT100", "M0030-SAT100-NOGATE", "M0030-C50A-NOGATE"),
    "M0053": ("M0053-TOTON20-NOBRAKE", "M0053-RESON20-NOBRAKE", "M0053-RESON20-TV16-NOGATE"),
}

ok = True
for mid in ("M0030", "M0053"):
    method, path = methods[mid]
    print(f"\n== {mid}  ({path.name}) ==")
    print("-- recorded candidates: every digest must still match the lab's record")
    for c in method.candidates:
        d = config_digest(c)
        row = conn.execute(
            "SELECT config_digest FROM trials WHERE candidate_id = ? AND window = 'dev'", (c.id,)
        ).fetchone()
        rec = row["config_digest"] if row else None
        same = (rec == d)
        ok &= bool(rec) and same
        print(f"   {c.id:<28} {d[:12]}  recorded {str(rec)[:12]}  {'OK' if same else 'CHANGED'}")
    print("-- amendment candidates: every digest must be FREE (no dev trial claims it)")
    amended = [c for a in method.amendments for c in a.candidates]
    names = tuple(c.id for c in amended)
    if names != NEW[mid]:
        ok = False
        print(f"   !! candidate ids are {names}, expected {NEW[mid]}")
    for c in amended:
        d = config_digest(c)
        hit = conn.execute(
            "SELECT candidate_id FROM trials WHERE config_digest = ? AND window = 'dev'", (d,)
        ).fetchone()
        ok &= hit is None
        print(f"   {c.id:<28} {d[:12]}  {'FREE' if hit is None else 'CLAIMED by ' + hit[0]}")

conn.close()
print("\nALL CHECKS PASS" if ok else "\nFAILED")
sys.exit(0 if ok else 1)
PY

cd "$WT" && $PY "$RUNDIR/digests.py" "$WT/lab/lab.sqlite" | tee "$RUNDIR/digests.txt"
```

**Expected:** every recorded candidate `OK` (three for M0030, five for M0053 — invariant 3 of the
index: *no recorded configuration's digest moved*), every amendment candidate `FREE`, and
`ALL CHECKS PASS`. The index's D4 table pre-computed four of the six:
`M0030-SAT100` → `542c1b9e439a…`, `M0030-SAT100-NOGATE` → `5d00ec7cafc0…`,
`M0053-RESON20-TV16-NOGATE` → `76de74aab178…`. These are a cross-check, not a requirement: what
matters is `FREE`.

**On `CHANGED`:** a recorded candidate's digest moved. That means a params dataclass or an
allocator id that recorded history depends on was edited. **STOP immediately and report it as a
phase 3 or phase 4 defect** (index invariant 3). Nothing is run.

**On `CLAIMED`:** a proposed candidate repeats a configuration that already ran. `runner.preflight`
would refuse it at Step 6 anyway with *"{c.id} repeats {other}, which already ran on the dev
window"*. **STOP and report** — the owning phase picks a different parameter, not this one.

**On `AttributeError: 'Method' object has no attribute 'amendments'`:** phase 1 did not land.
**STOP.**

**Impact:** none.

---

### Step 4: Commit M0030's method file — this commit is the pre-registration

**File:** `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py`
**Change:** stage it **by pathspec** and commit. Nothing else.

Read the amendment's hypothesis and expected-failure text one last time before committing. Once
this commit exists, the prediction is on the record and cannot be edited without invalidating the
pre-registration:

```bash
cd "$WT" && sed -n '1,200p' engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py
```

It must say, in its own words, that all three candidates are **predicted ineligible on max
drawdown** (index D5), and it must name what each prices (§4.1 for `SAT100`, §4.2 for the two
`NOGATE` arms).

```bash
cd "$WT"
git add -- engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py
git diff --cached --name-only        # MUST be exactly that one path
git commit -F - <<'MSG'
lab: M0030 amendment pre-registered — the parked market money is the drag

The exposure diagnostic found that M0030's own picks, at full size with the
market core taken out, led deposit-matched SPY by 7.5 points a year over the
whole development window and by 2.7 points from 2009 — the only positive
post-2009 figure anywhere in that grid, against the book as it actually ran
trailing by 1.7. That was a diagnostic column: nothing in the lab held "the
satellite at full size", so nothing could walk it forward or ever look at it on
the held-out years.

This amendment makes it a real, pre-registered variant of M0030 — three of
them. The satellite alone, filling the book. The same book with the shared
200-day market switch removed. And the recorded always-on-core version with
that switch removed from both halves, which is the control for what the switch
is worth once the core no longer needs it.

A variant of a method the lab already holds costs nothing in the luck hurdle:
that hurdle counts methods, and it reads 74 either way. A new method id would
have raised it to 75 for all 130 methods at once.

Written before the run, and expected to fail: the diagnostic puts the full-size
book's worst fall at 20.4%, against the owner's 20% limit, so all three are
predicted ineligible on that one condition while clearing the others. The
finding is not a promotion. It is that the only recent edge this lab has found
lives above the risk limit — recorded now, instead of inferred from a column.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
```

**Check:** `git status --short` shows `lab/lab.sqlite` possibly dirty (migrations from Step 0) and
phase 4's M0053 file still uncommitted. Nothing else staged.

**On failure:** if `git diff --cached --name-only` shows more than that one path, `git restore
--staged` the extras and redo. **Never `git add -A` and never `git add .`** — parallel sessions
share this index.

**Impact:** M0030's amendment is now pre-registered. `registry_problem` will accept the file.

---

### Step 5: Commit M0053's method file — the second pre-registration

**File:** `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py`
**Change:** stage by pathspec, commit.

```bash
cd "$WT" && sed -n '1,60p;180,320p' engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py
```

Confirm by eye before committing: `WeeklyOnParams`, `WeeklyOvernightAllocator`, `WEEKLYON`,
`TOTON20`, `TOTON30` and the five recorded candidates are byte-identical to what Step 3 just
digested as `OK`; the new allocator has its own `id` distinct from `"M0053"`; the amendment's
expected-failure text names the 22.4–22.8% predicted worst fall.

```bash
cd "$WT"
git add -- engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py
git diff --cached --name-only        # MUST be exactly that one path
git commit -F - <<'MSG'
lab: M0053 amendment pre-registered — the brake sells the jumpiness that pays

The weekly volatility brake was added to this book to fix one thing: a 22.8%
fall in the summer of 1998. It fixed it, and the exposure diagnostic showed
what it cost. With the brake off, the same picks led deposit-matched SPY by
7.7 points a year over the whole window and by 0.8 points from 2009; braked,
the book trails by 3.0 to 4.7 points over that recent stretch. The brake is
selling exactly the jumpiness that pays.

This amendment records three variants of the existing method rather than a new
method id, which costs nothing in the luck hurdle. Two take the brake off — on
the total-momentum pool and on the residual pool — using a new, separate
parameter type and a new allocator, so that not one recorded configuration of
this book changes its fingerprint. The third leaves the brake exactly where it
is and removes the shared 200-day market switch instead, which is the roster's
single most-shared rule and the one the lab's own control says has been a drag
every year since 2009.

Written before the run, and expected to fail: unbraked, the diagnostic puts the
worst fall at 22.4% to 22.8% against a 20% limit. All three are predicted
ineligible on that condition alone while clearing beats-the-market, the
gains-to-losses ratio and the trade count. That prediction is the point. If it
holds, this book's edge is real and lives above the owner's risk limit, and the
lab will have it on the record instead of in a diagnostic column.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
```

**Impact:** both amendments are pre-registered. Nothing has run.

---

### Step 6: `lab run --amend M0030`

**File:** `lab/lab.sqlite` (3 trials, 3 provenance, 3 moments, 3 funding, 1 amendment row).
**Change:** the first execution of this phase.

```bash
cd "$WT"
$PY -m seer_engine lab run --amend M0030 --store "$STORE" 2>&1 | tee "$RUNDIR/run-m0030.txt"
echo "exit=${PIPESTATUS[0]}"
```

Every flag, and why:

- **`--amend`** is phase 1's. Without it `runner.preflight` raises
  *"M0030 is already dev-eligible: a method runs once"* and exits 2.
- **`--store "$STORE"`** points at the main checkout's dev store. `research.load_store` refuses a
  store whose window is not `research.DEV_WINDOW`, and `_run` refuses one with a `purpose` marker
  before loading a byte — so a test or survivorship store cannot slip in. Pass it explicitly
  anyway. Never `engine/.research-test`.
- **No `--allow-coverage`** — but **measure that before relying on it** (reconciler, C15). Phase 1
  widened `runner.market_aware_candidates` to read `method.all_candidates()`, so
  `preflight_data`'s fundamentals coverage gate now runs over the amendment's candidates as well
  as the originals. If any of M0030's six candidates ranks on `Market.fundamentals`,
  `preflight_data` re-measures the panel against **today's** dev store (fingerprint
  `77c37d55…`) rather than the one M0030's recorded trials ran on, and may refuse or report below
  the floor. `--allow-coverage` is an **acknowledgement, not a silencer**: it lowers the floor and
  prints that the trials measure the panel rather than the hypothesis, and the method id is spent
  either way. Run this read-only check before Step 6 and act on what it says, not on an
  assumption:

  ```bash
  cd "$WT" && $PY - <<'PY'
  from seer_engine.lab import runner
  from seer_engine.lab.method import discover
  ms = discover()
  for mid in ("M0030", "M0053"):
      m, _ = ms[mid]
      print(mid, "fundamentals-ranking variants:",
            runner.market_aware_candidates(m, "fundamentals") or "(none)")
      print(mid, "series-ranking variants:    ",
            runner.market_aware_candidates(m, "series") or "(none)")
  PY
  ```

  **Expected `(none)` on both lines for both methods** — M0030's allocators are `TIMING` and
  `RESIDMOM` (price-only) and M0053's are `WEEKLYON` and phase 4's `FULLON` (also price-only), so
  the coverage gate should not be reached at all. If either line is non-empty, **stop before Step
  6** and report: the gate will fire, a coverage report will print, and the decision about whether
  to run anyway at a lowered floor is the owner's, not this phase's. If a coverage report appears
  during the run despite an empty reading here, read it and stop — do not lower the floor.
- **No `--db`.** The default resolves to `$WT/lab/lab.sqlite` through `PYTHONPATH`.
- **Foreground, with `tee`.** Do not background it: the open write transaction must not outlive the
  step, and Step 7 must not start while it holds the lock.

**Runtime:** ~10 s to load the store plus three dev-window runs. The exposure diagnostic measured
comparable runs at 1.8–5.4 s each; expect well under five minutes.

**What to read in the output:**

1. `research store 77c37d5535 loaded` — the dev store, correct fingerprint. If it reads something
   else, **do not rebuild**: stop and report. `hardgate.pin_dev_store` checks the **price**
   fingerprint (`5451195f…`) separately, and no flag skips it.
2. `M0030: 3 trial(s) recorded, status dev-eligible` — three trials, status unchanged.
3. The `_show` table: three new rows `M0030-SAT100`, `M0030-SAT100-NOGATE`, `M0030-C50A-NOGATE`
   with their worst fall, profit factor, trades, DSR and eligibility.
4. `Lab N (dev trials) is now 357; test-window looks used: 4` — **this is the ROW count printed by
   one of the ten §5.1 strings (`commands/lab.py:1399`), not the gate's N.** Record it in the
   transcript. Never quote it in the write-up. Never fix it.

**Exit codes:** 0 ok · **2 the lab's rules refused the request** · 1 an error.

**Failure branches, in full:**

| What you see | What it means | What to do |
|---|---|---|
| exit 2, *"M0030 is already dev-eligible: a method runs once"* | **Phase 1's amendment path did not land**, or `--amend` did not reach `preflight`. | **STOP.** This is the single refusal that ends the phase. Report it as a phase 1 defect. Do not touch `runner.py`. |
| exit 2, *"{candidate} repeats {other}, which already ran"* | a digest collision Step 3 should have caught. | **STOP.** Report to the owning method phase; it picks a different parameter. |
| exit 2, *"M0030: … must be priced at Gotrade's real fees"* | `real_costs.real_cost_problem` refused. It should not: `requires_real_cost` exempts ids ≤ M0030 (`real_costs.py:54-69`) and D7 relies on that. | **STOP and report.** Do not change `rules` to make it pass — that would make the new candidates incomparable with M0030's recorded three, which is the whole reason D7 chose `MONTHLY_HOLD_FRAC`. |
| exit 2, a store refusal (`pin_dev_store`, purpose marker, window) | the store is not the one the lab's record was measured on. | **STOP and report. Never rebuild the store on a fingerprint mismatch alone** — ~30 minutes, and it drops `market_series.csv` and `dividend_announcements.csv`. |
| exit 1, `sqlite3.IntegrityError: method status may only move forward along TRANSITIONS` | **Should be unreachable** (reconciler, C2): phase 1's Decision P2 means `run_method` writes no `status` at all on the amendment path, and its own test asserts the status is unchanged across an amendment run. If this fires, P2 did not land. The whole transaction aborted and **nothing was recorded**. | **STOP.** A **phase 1 defect**. Report it with the traceback. Do not patch `runner.py` from this phase. `git checkout -- lab/lab.sqlite` restores the committed copy — safe here only because nothing else has written to it on this branch. |
| exit 1, `source_sha is set once, when the method runs` | `run_method` tried to rewrite `methods.source_sha`. | **STOP.** Phase 1 defect, same handling. |
| exit 1, anything else | an error. | **STOP**, keep `$RUNDIR/run-m0030.txt`, report. |

**Impact:** `lab/lab.sqlite` holds 357 dev trials and is dirty in git. **Do not commit it yet.**

---

### Step 7: `lab run --amend M0053`

**File:** `lab/lab.sqlite` (3 more trials and their companion rows).
**Change:** the second execution. **Only after Step 6 has exited and released the lock.**

```bash
cd "$WT"
$PY -m seer_engine lab run --amend M0053 --store "$STORE" 2>&1 | tee "$RUNDIR/run-m0053.txt"
echo "exit=${PIPESTATUS[0]}"
```

Same flags, same reasons, same failure table as Step 6 — with one difference: **M0053 is bound to
Gotrade's real fees.** `requires_real_cost` applies from M0031 on, so its candidates must carry
`MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE`. If `real_cost_problem` refuses here, phase 4 used the
wrong rules object — **stop and report**, do not relax the cost model.

**Runtime:** M0053 runs weekly, with 1100–1500 trades per variant; expect longer than M0030 but
still minutes, not tens of minutes.

**What to read:** `M0053: 3 trial(s) recorded, status dev-eligible`, the `_show` table with
`M0053-TOTON20-NOBRAKE`, `M0053-RESON20-NOBRAKE`, `M0053-RESON20-TV16-NOGATE`, and
`Lab N (dev trials) is now 360` (again: ROWS).

**Impact:** `lab/lab.sqlite` holds **360** dev trials, `max(n) = 364`.

---

### Step 8: The N check, AFTER the runs — the headline deliverable, second reading

**File:** writes `$RUNDIR/n-after.txt`, `$RUNDIR/counts-after.txt`.
**Change:** none. Read-only.

**This is the point of the whole plan set. If it fails, the phase stops rather than committing.**

```bash
cd "$WT" && $PY "$RUNDIR/ncheck.py" "$WT/lab/lab.sqlite" | tee "$RUNDIR/n-after.txt"
diff "$RUNDIR/n-before.txt" "$RUNDIR/n-after.txt"
```

**Expected — the only acceptable diff is the `dev_trial_count` line, `354 -> 360`:**

```
gate                : Gate(n=74, policy='methods')      <- UNCHANGED
dev_method_count    : 74                                 <- UNCHANGED
pending M0030 k=3   : Gate(n=74, policy='methods')      <- UNCHANGED
pending M0053 k=3   : Gate(n=74, policy='methods')      <- UNCHANGED
dev_trial_count     : 360                                <- 354 + 6 ROWS, by design
test_looks          : 4                                  <- UNCHANGED
```

Then the census:

```bash
cd "$WT"
sqlite3 "file:lab/lab.sqlite?mode=ro" <<'SQL' | tee "$RUNDIR/counts-after.txt"
.mode list
.headers off
SELECT 'trials',           count(*) FROM trials;
SELECT 'max_trial_n',      coalesce(max(n),0) FROM trials;
SELECT 'dev_trials',       count(*) FROM trials WHERE window = 'dev';
SELECT 'test_looks',       count(*) FROM trials WHERE window = 'test';
SELECT 'distinct_dev_methods', count(DISTINCT method_id) FROM trials WHERE window = 'dev';
SELECT 'trial_moments',    count(*) FROM trial_moments;
SELECT 'trial_funding',    count(*) FROM trial_funding;
SELECT 'trial_provenance', count(*) FROM trial_provenance;
SELECT 'insights',         count(*) FROM insights;
SELECT 'max_insight_id',   coalesce(max(id),0) FROM insights;
SELECT 'methods_total',    count(*) FROM methods;
SELECT 'methods:' || status, count(*) FROM methods GROUP BY status ORDER BY status;
SELECT 'M0030_sha',        substr(source_sha,1,12) FROM methods WHERE id = 'M0030';
SELECT 'M0053_sha',        substr(source_sha,1,12) FROM methods WHERE id = 'M0053';
SQL
diff "$RUNDIR/counts-before.txt" "$RUNDIR/counts-after.txt"
```

**Expected diff, and nothing else:** `trials` 358→364, `max_trial_n` 358→364, `dev_trials`
354→360, `trial_moments` 244→250, `trial_funding` 230→236, `trial_provenance` 358→364, and the
md5 line. **`test_looks` stays 4. `distinct_dev_methods` stays 74. The whole `methods:` block is
unchanged — 15 dev-eligible, 59 rejected. `M0030_sha` is still `3b6aad38e1f1` and `M0053_sha` is
still `2289c49024df`.**

And the six rows themselves:

```bash
cd "$WT"
sqlite3 -header -column "file:lab/lab.sqlite?mode=ro" "
SELECT t.n, t.method_id, t.candidate_id, round(t.max_drawdown,4) dd, round(t.profit_factor,3) pf,
       t.trades, round(t.dsr,4) dsr, t.n_trials_at_run, t.eligible, t.failed,
       p.initial_idr, substr(p.price_fingerprint,1,12) prices,
       round(f.mwr,4) mwr, round(f.spy_tr_mwr,4) spy_mwr, f.deposits_n
FROM trials t
LEFT JOIN trial_provenance p ON p.trial_n = t.n
LEFT JOIN trial_funding   f ON f.trial_n = t.n
WHERE t.n > 358 ORDER BY t.n;" | tee "$RUNDIR/new-trials.txt"
```

**Check every one of these:**

- six rows, `n` **359..364**, contiguous with 358;
- `method_id` is `M0030` ×3 then `M0053` ×3 — **no new method id anywhere**;
- `n_trials_at_run` is **74** on all six (the gate the DSR was deflated by — this is the number
  that proves the hurdle did not move, recorded in the row itself);
- `initial_idr` is `10000000` and `prices` is `5451195f…` on all six;
- `deposits_n` is non-null on all six (every run is funded; `mwr` and `spy_tr_mwr` are the
  money-weighted pair the write-up reports).

**If `gate(conn).n` comes back 75 or 76 — the shape failed. STOP.** Do not run `lab stage`, do not
commit. A moved N means a trial landed under a method id the lab had not seen, which is exactly
what R3 forbids. Report which id, with `SELECT DISTINCT method_id FROM trials WHERE window='dev'
EXCEPT SELECT ...` to find it. The database is append-only and the row cannot be removed; the
recovery is to leave `lab/lab.sqlite` **uncommitted**, `git checkout -- lab/lab.sqlite`, and hand
the finding back.

**If `test_looks` is not 4, or any row appeared with `window='test'`:** the test window was
touched. **STOP immediately and report.** This is the gravest possible failure of this phase.

**Impact:** none written. This is the evidence the write-up's headline rests on.

---

### Step 9: `lab gate` — price the shared SPY 200-day gate across the roster

**File:** `lab/lab.sqlite` (`insights` only), and conditionally
`docs/backtests/2026-10-12-brakes-and-gate-gate-grid.csv`.
**Change:** phase 2's report-only diagnostic, run over the roster.

Read the surface first (Step 0 did this; do it again now that the database has moved):

```bash
cd "$WT" && $PY -m seer_engine lab gate --help
```

Then run it over the five live books, M0030 and M0053 included, so the two new `NOGATE` trials are
priced in the same table as every other gated book:

```bash
cd "$WT"
$PY -m seer_engine lab gate M0024 M0028 M0030 M0044 M0053 \
  --store "$STORE" \
  --csv "$WT/docs/backtests/2026-10-12-brakes-and-gate-gate-grid.csv" \
  2>&1 | tee "$RUNDIR/gate.txt"
echo "exit=${PIPESTATUS[0]}"
```

- **Those five ids** are the handover §2 live space. M0024 matters particularly: it holds the lab's
  only recorded gated/ungated control pair (`M0024-SAME-N20` vs `M0024-SAME-N20-NOTREND`), which is
  the measurement R2 started from — gated **+2.7**/yr whole-window vs ungated **+1.0**, but
  **−5.4** vs **+1.5** after 2009.
- **`--csv` exists** (phase 2's Step 3; reconciler C11), so the gate grid is written every time
  and committed with the write-up. If `--help` disagrees with the surface quoted above, phase 2
  did not land as planned: **stop and report it**, rather than silently transcribing a table.
- **Do not pass `--no-journal`**: the observations are a deliverable.
- **Do not pass `--gated-only`**: the empty-decision cross-check that keeps a "no gate" verdict
  honest is part of what R2 asked for. Phase 2 offers it only as a way to cut a very long sweep
  down, and five named methods is not a long sweep.
- **Do not pass `--all`** here. Phase 2 measured `--all` at ~519 backtests over 300 live recorded
  variants; the five named books are the handover §2 live space and the question R2 actually
  asked. If the owner later wants the roster-wide sweep, it is its own run.

**Report-only check, immediately after:**

```bash
cd "$WT" && $PY "$RUNDIR/ncheck.py" "$WT/lab/lab.sqlite"
```

**Expected:** identical to `$RUNDIR/n-after.txt` — `Gate(n=74)`, `dev_trial_count 360`,
`test_looks 4`. `lab gate` must move **nothing but `insights`**. If `dev_trial_count` moved,
phase 2's command is not report-only: **STOP and report it as a phase 2 defect.**

**Impact:** a handful of `insights` rows; the gate CSV, if the flag exists.

---

### Step 10: `lab walkforward` — read only, for the durability section

**File:** none written.
**Change:** none. This command loads no research store and writes nothing.

```bash
cd "$WT"
$PY -m seer_engine lab walkforward M0030 M0053 2>&1 | tee "$RUNDIR/walkforward.txt"
```

It slices the recorded monthly curves into folds against the recorded SPY benchmark curve
(`commands/lab.py:2067`). The six new trials carry `curve_json`, so they appear in the table
alongside the recorded ones.

**No `--min-train-years` and no `--eval-years`.** The defaults are the geometry the hard gate uses;
changing them to make a method look better is exactly the override this phase is forbidden from
attempting. **`hardgate` is not called and `MIN_FOLDS` is not touched.** If the brakes-off variants
lose a majority of folds, **that is the result** and it goes in the write-up's durability section
as a second, independent reason the lab should not chase them.

A `WARNING` line above a row means that method's curves were measured on prices other than the
benchmark's (hardgate D10). Note it; a report warns where the gate refuses.

**Impact:** `lab/lab.sqlite` may be migrated on connect (it is already dirty). Nothing else.

---

### Step 11: The journal and the two verdicts

**File:** `lab/lab.sqlite` — two `insights` rows, two `methods.analysis` appends, two
`methods.verdict` updates.
**Change:** the owner-facing record of what was found.

First the analysis notes. `methods.analysis` is append-only by trigger
(`methods_analysis_grows`, `store.py:482`) and `methods.hypothesis` is **frozen** once a method
leaves `idea` (`methods_hypothesis_frozen`, `store.py:486`) — so the amendment's hypothesis lives in
`method_amendments` and in the committed file, never in `methods.hypothesis`. Write the note to a
file and append it:

```bash
cd "$WT"
cat > "$RUNDIR/m0030-note.md" <<'NOTE'
2026-10-12 amendment: the satellite at full size, with and without the market switch.

<three to six sentences, written AFTER reading $RUNDIR/new-trials.txt: what each of the three
candidates did, whether the predicted drawdown breach happened, and what the two NOGATE arms say
about the 200-day switch on this book. Plain language. No ids, digests or code beyond the
candidate names the lab itself prints.>
NOTE

$PY -m seer_engine lab note M0030 --file "$RUNDIR/m0030-note.md"
```

and the same for M0053 with `$RUNDIR/m0053-note.md`.

Then the verdicts. `lab note --verdict` sets `methods.verdict`, which is the sentence the owner
reads on `seertrade.site/sera`. **Write it against the pre-registered prediction, both ways round,
and do not present a failed drawdown as a disappointment.** Shape:

```bash
cd "$WT"
$PY -m seer_engine lab note M0030 --verdict "<one or two plain sentences: what the full-size
satellite earned on the owner's money against deposit-matched SPY, its worst fall against the 20%
limit, and what that means — the edge is real and sits above the risk limit, or the prediction was
wrong and it clears.>"

$PY -m seer_engine lab note M0053 --verdict "<the same for the brake-off and gate-off arms.>"
```

**A verdict is set, never rewritten to flatter.** Both methods stay `dev-eligible`; `lab note`
touches no status.

Then two journal entries, written by hand:

```bash
cd "$WT"
$PY -m seer_engine lab insight --kind observation \
  --title "Six new trials, and the luck hurdle did not move" \
  --body "The lab recorded six new development trials today, three on each of two books it
already held, and the hurdle those trials are judged against stayed exactly where it was: 74. It
counts methods, not trials, so adding versions to a book the lab already has is free, and only a
brand-new book raises the bar for every book at once. The count of development trial rows went
from 354 to 360; that is a different number and it is not the hurdle. The held-out years were not
touched: the look budget reads 4, as it has since it was last spent." \
  --method M0030

$PY -m seer_engine lab insight --kind synthesis \
  --title "<the finding, in the owner's words>" \
  --file "$RUNDIR/synthesis.md"
```

`store.INSIGHT_KINDS` is `observation, hypothesis, data-wish, feature-wish, risk, synthesis` —
use no other. `lab insight` prints the new id; record both ids.

**Re-check N after writing:**

```bash
cd "$WT" && $PY "$RUNDIR/ncheck.py" "$WT/lab/lab.sqlite"
```

**Expected:** unchanged — `Gate(n=74)`, `dev_trial_count 360`, `test_looks 4`.

**Impact:** the record now reads as a measurement with a verdict, not a pile of rows.

---

### Step 12: `lab stage`, then the database commit

**File:** `lab/lab.sqlite` + `web/data/lab.json`.
**Change:** the only path by which this phase commits a database.

```bash
cd "$WT"
$PY -m seer_engine lab stage
git diff --cached --name-only
```

**Expected staged paths, exactly two:** `lab/lab.sqlite` and `web/data/lab.json`.

`lab stage` (`commands/lab.py:2381`) takes `BEGIN EXCLUSIVE`, writes the snapshot with
`store.write_snapshot` and `git add`s both while holding the lock, so a parallel session's
half-written transaction can never be what gets committed. **Never `git add lab/lab.sqlite` by
hand.** CI checks that `lab.sqlite` and `web/data/lab.json` agree row for row.

Spot-check that the snapshot carries the right hurdle before committing:

```bash
cd "$WT" && $PY -c "
import json, pathlib
d = json.loads(pathlib.Path('web/data/lab.json').read_text())
g = d.get('gate', {})
print('gate:', g)
print('dsrN:', g.get('dsrN'), 'basis:', g.get('dsrNBasis'))
"
```

**Expected:** `dsrN` is **74** and the basis names the `methods` policy. If it reads 354 or 360,
the snapshot is quoting the row count: **STOP and report** — that is a phase 1/phase 2 defect in
the snapshot writer, not something this phase edits.

```bash
cd "$WT"
git commit -F - <<'MSG'
lab: the brakes off and the market switch off, on the two books that had an edge

Ran both amendments on the development window and recorded six new trials, three
on each book, under the ids the lab already held. The hurdle those trials are
judged against did not move: it counts books, not runs, and it read 74 before
and 74 after. The held-out years were not touched.

<Replace with four to eight plain sentences once the results are in: what the
full-size satellite did on the owner's money against deposit-matched SPY and
how far it fell; what the unbraked overnight book did and how far it fell;
whether the pre-registered prediction of a drawdown breach held; and what the
three switch-off arms, plus the roster-wide pricing, say about the one rule
four of the five live books share. State the result against the prediction,
both ways round.>

Six trials, six funding rows, six provenance rows, six sets of luck inputs, two
amendment records, and the journal. No status moved, no fingerprint of any
earlier run changed, no look was spent.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
```

**If this is a rejection on push later and you reach for `pull --rebase`: don't, without
re-staging.** A rebase replays a stale `lab.sqlite` over the live shared database other sessions
are writing. If it has already happened, re-run `lab stage` and re-check trial `n` contiguity
(Step 14).

**Impact:** the database is committed. The lab now holds the six trials.

---

### Step 13: The write-up and its grid

**File:** `docs/backtests/2026-10-12-brakes-and-gate.md`,
`docs/backtests/2026-10-12-brakes-and-gate-grid.csv`, and conditionally the gate grid from Step 9.

First export the grid, read-only, at full precision:

```bash
cd "$WT"
sqlite3 -header -csv "file:lab/lab.sqlite?mode=ro" "
SELECT t.n, t.method_id, t.candidate_id, t.config_digest, t.rules_id, t.allocator_id,
       t.window, t.start, t.end, t.store_fingerprint, t.git_sha, t.run_at,
       t.total_return, t.cagr, t.max_drawdown, t.profit_factor, t.trades, t.sharpe,
       t.exposure, t.turnover, t.worst_year, t.worst_year_return,
       t.spy_tr_return, t.spy_tr_cagr, t.mar, t.failed, t.eligible, t.dsr, t.n_trials_at_run,
       p.initial_idr, p.price_fingerprint,
       f.mwr, f.spy_tr_mwr, f.deposits_usd, f.deposits_n, f.schedule,
       m.sr_daily, m.t, m.skew, m.kurt, m.var_trials, m.n_at_run
FROM trials t
LEFT JOIN trial_provenance p ON p.trial_n = t.n
LEFT JOIN trial_funding   f ON f.trial_n = t.n
LEFT JOIN trial_moments   m ON m.trial_n = t.n
WHERE t.method_id IN ('M0030','M0053') AND t.window = 'dev'
ORDER BY t.n;" > docs/backtests/2026-10-12-brakes-and-gate-grid.csv

wc -l docs/backtests/2026-10-12-brakes-and-gate-grid.csv   # 1 header + 14 rows (8 recorded + 6 new)
```

The grid carries **all fourteen** dev trials of the two books, recorded and new, so a reader can
see the amendment beside what it amends — with `initial_idr` and `deposits_n` in the row, which is
how the funding caveat stays visible instead of being a footnote.

**Then write `docs/backtests/2026-10-12-brakes-and-gate.md`** to this skeleton. The model is
`docs/backtests/2026-10-12-exposure-diagnostic.md`: plain language for the owner, **no ids,
digests or code in the prose** beyond the candidate names the lab itself prints, every figure
dated and attributed to what it was measured on.

````markdown
# The brakes off, and the market switch off

**Measured:** 2026-10-12 · **Window:** 1996-01-03 → 2015-10-16 (the lab's development window)
**Research store:** `77c37d553508` (dev, unmarked) · **Prices:** `5451195fd552`
**Money:** 10,000,000 IDR to start, 5,000,000 IDR on the 25th of each month — the owner's real schedule
**Grid:** [`2026-10-12-brakes-and-gate-grid.csv`](2026-10-12-brakes-and-gate-grid.csv) — the same rows at full precision
**Commands:** `lab run --amend M0030`, `lab run --amend M0053`, `lab gate M0024 M0028 M0030 M0044 M0053`

## The short answer
<One paragraph, written last. What the two books did with the brakes off, against deposit-matched
SPY and against the 20% limit; whether the pre-registered prediction held; and the one sentence the
owner should take away. If the prediction held — and it is expected to — the finding is NOT a
disappointment: the only recent edge in this lab exists only above the owner's risk limit, and the
lab now holds that as a record rather than inferring it from a diagnostic column. Say that plainly.>

## Why this was measured
<The exposure diagnostic found exactly two configurations anywhere in its grid with a positive edge
over the market in the most recent third of the window, and both of them were diagnostic columns —
arrangements that existed in memory for the length of one run and that the lab did not hold. So
nothing could carry them forward, test them on the held-out years, or ever act on them. And four of
the five live books share one rule — stop buying when the market is below its long-term average —
which produced the same thirty-five point lead in 2008 for every one of them and has been a drag
every year since 2009. This measurement turns both findings into things the lab holds.>

## What it cost, and why that is the headline
<The luck hurdle counts books, not runs. Adding versions to a book the lab already has is free; a
new book raises the bar for all 130 at once. Measured before: 74. Measured after six new runs: 74.
The count of trial rows went 354 → 360, which is a different number. The held-out years were not
opened: the look budget reads 4, unchanged. Give the exact before/after readings.>

## How it was measured
<The amendment mechanism in one paragraph of plain words: a book the lab has already run can gain
a dated, written-down set of new versions, committed before they run, recorded under the book's own
name. What each of the six versions is. The funding the runs received. The fees each book pays —
M0030 at the flat cost its earlier versions were measured at, M0053 at Gotrade's real fees, which
is why the two books' numbers are not directly comparable to each other. Name the grid the §4.2
roster-wide pricing came from — `2026-10-12-brakes-and-gate-gate-grid.csv`, committed beside this
file.>

## What was predicted, before anything ran
<Quote the two amendments' own expected-failure text: every candidate predicted ineligible on the
worst-fall condition — the satellite near 20.4%, the unbraked overnight book at 22.4-22.8%, against
a 20% limit — while clearing beats-the-market, the gains-to-losses ratio and the trade count. This
section exists so the next section can be read as a test rather than a story.>

## What happened
<The six results. For each: money-weighted return on the owner's deposits, the same measure for
deposit-matched SPY, the worst fall, gains-to-losses, trades, the luck score and the hurdle it was
judged against (74), and whether it cleared. Judge each against the prediction **both ways round**:
name every condition the prediction got right and every one it got wrong. If a candidate cleared
when it was predicted to fail, say so first and loudly.>

### The funding caveat
<M0030's three earlier versions were lump-sum runs of 20,000,000 IDR with no monthly top-up,
recorded before the lab's runner was funded. The three new ones are funded at 10,000,000 IDR plus
5,000,000 a month. So the new numbers cannot be put in the same column as the old ones, and the
20.4% worst fall the diagnostic reported for this book was itself a lump-sum figure. M0053's five
earlier versions and its three new ones share the same money and the same fees and ARE comparable.
State this before any table that could be misread.>

## The market switch, priced across the roster
<R2's half. The lab's own recorded control: with the switch, the book led by 2.7 points a year over
the whole window; without it, 1.0 — but after 2009 the switched version trailed by 5.4 while the
unswitched one led by 1.5. What the three new switch-off versions say on these two books. What
`lab gate` found across all five live books. The point the owner needs: this is ONE rule, read on
the SAME index on the SAME dates, and it is most of what four separate-looking books have in
common — so changing it moves all of them at once.>

### One of the lab's "controls" was never a control
<Reconciler C14, from phase 2's own measurement of 2026-10-12. The lab has a recorded pair on
M0001 that it has treated as a clean switch-on/switch-off comparison. It is not one: the
switched-off sibling also widens the book's own volatility window from 63 sessions to 126, so the
recorded pair moves two things at once and nothing in it isolates the switch. Phase 2's probe
excludes it from the set it validates itself against (`IMPURE_CONTROLS`, with that reason and that
date beside it) and is the clean comparison M0001 never had. Say this plainly and in the owner's
language — he has been reading a two-variable comparison as a one-variable one — and name what the
probe says instead. The other five recorded pairs the probe reproduces exactly, so this is one
bad control, not a bad method.>

### What the gate probe could not price
<Phase 2 measured, 2026-10-12: of the lab's 354 recorded dev trial rows, 300 are still in a method
file; of those, 225 carry the switch and transform cleanly, 69 carry no switch the probe can see,
and 6 carry it and refuse to run without it. Those six are listed by name in the probe's output
with the reason each refused. Say that they were **not** guessed at — a number that looks like a
switched-off result and is not one is worse than no number — and that 54 recorded variants no
longer have a method file at all.>

## Does it survive out of sample
<The walk-forward reading from `lab walkforward M0030 M0053`: how many folds each version won, and
how that compares with what the promotion gate requires. The gate was not run and nothing was
promoted. If the brakes-off versions lose a majority of folds, that is a second, independent reason
not to chase them, and it belongs here.>

## Every version, recorded and new
<The full table: all fourteen development versions of the two books, recorded and new, with the
committed grid beside this file at full precision. Columns: version, what it is in plain words,
money-weighted return, deposit-matched SPY, worst fall, gains-to-losses, trades, luck score,
clears. Mark which rows are funded and which are not.>

## What this changes
<Three or four sentences for the owner. What he should and should not do with this. The standing
rule on survivorship-free data — buy it only when a method clears dev-eligible AND a majority of
walk-forward folds AND a positive 2009-2015 edge — and whether anything here moved that needle.
If the drawdown breach held, the honest answer is that the third condition is now met by
configurations that fail the first, which is new information and not nothing.>

## What was and was not recorded
<The exact ledger: six development trials recorded under the two existing book names, their funding
and luck inputs, two amendment records, the journal entries, and the two verdicts. The hurdle
before and after. The look budget before and after. No new book was created, no earlier run's
fingerprint changed, no status moved, no promotion was attempted, and the held-out years were never
opened.>
````

Then commit:

```bash
cd "$WT"
git add -- docs/backtests/2026-10-12-brakes-and-gate.md \
           docs/backtests/2026-10-12-brakes-and-gate-grid.csv \
           docs/backtests/2026-10-12-brakes-and-gate-gate-grid.csv
git diff --cached --name-only        # exactly three paths under docs/backtests/ and nothing else
git commit -F - <<'MSG'
docs: the brakes off and the market switch off, measured

<Replace with the write-up's short answer, four to eight sentences in the
owner's language, plus the before/after hurdle reading.>

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
```

**Impact:** the phase's four commits are in place.

---

### Step 14: Final verification

**File:** none.
**Change:** none.

```bash
cd "$WT"

# 1. The suite, with Postgres up. CI fails if DB tests skip.
docker start seer-pg
$RUFF check engine
$PY -m pytest engine/tests -n auto 2>&1 | tail -20

# 2. The N check, one last time, from the committed database.
$PY "$RUNDIR/ncheck.py" "$WT/lab/lab.sqlite"

# 3. lab.sqlite and web/data/lab.json agree row for row (what CI checks).
$PY -m seer_engine lab export-json --out "$RUNDIR/lab-recheck.json"
diff <($PY -m json.tool "$RUNDIR/lab-recheck.json") <($PY -m json.tool web/data/lab.json) \
  && echo "snapshot agrees"

# 4. Trial n is contiguous, 1..364 with no hole.
sqlite3 "file:lab/lab.sqlite?mode=ro" \
  "SELECT count(*), min(n), max(n) FROM trials;
   SELECT 'HOLE AT ' || (t.n + 1) FROM trials t
    WHERE t.n < (SELECT max(n) FROM trials)
      AND NOT EXISTS (SELECT 1 FROM trials u WHERE u.n = t.n + 1);"

# 5. Nothing was written to the test window or the pre-registration directory.
sqlite3 "file:lab/lab.sqlite?mode=ro" "SELECT count(*) FROM trials WHERE window='test';"
git status --short docs/lab/
git log --oneline --name-only -4

# 6. Working tree clean, branch ahead by exactly this phase's commits.
git status --short
```

**Expected:** ruff clean; pytest green with exactly 3 skips; `Gate(n=74, policy='methods')`,
`dev_trial_count 360`, `test_looks 4`; `snapshot agrees`; `364|1|364` with no `HOLE AT` line;
`4` test trials; `git status --short docs/lab/` empty; four commits touching only the seven files
in the Files table.

**On a snapshot mismatch:** re-run `lab stage` and `git commit --amend` the database commit. Never
hand-edit `web/data/lab.json`.

---

## Verification

**Build:** `cd $WT && /home/miftah/seer/engine/.venv/bin/ruff check engine`
(CI lints bugs only: E9 and F, minus F401.)

**Tests:**
```bash
docker start seer-pg
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd /home/miftah/.worktrees/seer/lab-brakes-and-gate
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -n auto
```
Green, with **exactly 3 skips** (the opt-in live-store tests). More skips means Postgres is not
reachable and CI will fail.

**Manual check:** `$RUNDIR/n-before.txt` and `$RUNDIR/n-after.txt` differ on **one line only**
(`dev_trial_count 354 -> 360`). `web/data/lab.json`'s `gate.dsrN` reads 74.

**Exit criteria:**

1. `M0030` and `M0053` each carry three new dev trials (`n` 359..364) under their **own**
   `method_id`, each with `n_trials_at_run = 74`, `initial_idr = 10000000`, a `trial_funding` row
   and a `trial_moments` row.
2. `store.gate(conn) == Gate(n=74, policy='methods')` and `npolicy.dev_method_count(conn) == 74`,
   measured before and after and both recorded.
3. `store.test_looks(conn) == 4`, unchanged, and `docs/lab/prereg/` is untouched.
4. `methods.source_sha` is unchanged for both methods; both still read `dev-eligible`; the whole
   `methods:` status census is unchanged.
5. The write-up states the result against the pre-registered hypothesis and expected failure,
   **both ways round**, and does not present a failed drawdown as a disappointment.
6. `lab stage` has run; `lab.sqlite` and `web/data/lab.json` agree row for row.
7. `ruff check engine` is clean and `pytest engine/tests` is green with Postgres up.
8. No engine source file appears in any commit of this phase.

---

## Handoffs

- **`.workflows/todos.md`** — a completed-task entry for this plan set, and the header counters.
  Not owned by this phase; left for the completion handler or the coordinator that merges the set,
  so two phases do not collide on one file.
- **`docs/plans/LAB_BRAKES_AND_GATE_PLAN.md`** — the Reconciliation Log and the phase table's
  Status column. The reconciler and the coordinator own it.
- **R5 / §5.1 — the ten `Lab N (dev trials) is now …` strings.** This phase *sees* them fire twice,
  at Step 6 and Step 7, printing 357 and 360 where the hurdle is 74. It changes nothing and quotes
  nothing from them in the write-up. **Phase 6** puts them to the owner.
- **The design doc's dated revision recording the amendment rule** — `docs/plans/2026-10-04-method-lab-design.md`. **Phase 6.**
- **Anything the runs expose about phases 1–4's code** — a crash, an abort on the status trigger, a
  gate probe that is not report-only, a digest that moved. Reported, never patched here.
- **`docs/backtests/package_readme.md` or the engine readme pointer to the new write-up**, if this
  repo keeps one — left to the readme updater that runs after the set lands, so it can name all six
  phases' output at once.
- **Anything the results suggest doing next** — a different brake setting that might clear 20%, a
  roster-wide removal of the 200-day switch, a `sera-the-explorer` batch. **None of it is done
  here.** Searching for a passing setting after seeing the result is exactly what design §4
  forbids. Write it into the write-up's "What this changes" as a question for the owner.

---

## Rollback

This phase is **four commits** on `feature/lab-brakes-and-gate`:

1. the M0030 pre-registration (one method file),
2. the M0053 pre-registration (one method file),
3. the database (`lab/lab.sqlite` + `web/data/lab.json`),
4. the write-up (two or three files under `docs/backtests/`).

`git revert` them newest-first. Commits 1, 2 and 4 are text-only and revert cleanly.

Commit 3 is the only one that needs care. The lab is append-only, and **the committed blob is the
record**: reverting restores the previous `lab/lab.sqlite` wholesale, which is a legitimate
rollback of this branch but silently drops the six trials. After any revert or any rebase that
replays a stale database:

```bash
cd "$WT"
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage
sqlite3 "file:lab/lab.sqlite?mode=ro" \
  "SELECT 'HOLE AT ' || (t.n + 1) FROM trials t
    WHERE t.n < (SELECT max(n) FROM trials)
      AND NOT EXISTS (SELECT 1 FROM trials u WHERE u.n = t.n + 1);"
```

`lab stage` must be re-run so `web/data/lab.json` agrees row for row again, and trial `n` must come
back contiguous.

**As a whole:** delete the branch and the worktree. Nothing outside the branch is written —
`/home/miftah/seer/engine/.research` is read-only to every step here and is never rebuilt, and no
step touches `main`.

**What cannot be rolled back:** nothing. This phase never spends a test-window look, never writes a
pre-registration file into `docs/lab/prereg/`, and never mints a method id — the three things in
this repository that are genuinely one-way.
