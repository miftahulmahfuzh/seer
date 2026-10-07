> Adopted from `DELISTING_STRESS_ROSTER_RULES_PLAN.md` phase 2. Source: `.workflows/plan/delisting-stress-roster-rules/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Run it, and record what it found

**Plan set:** `DELISTING_STRESS_ROSTER_RULES_PLAN.md`
**Analysis:** `20261007-170515-0CU0_code_analyzer.md`
**Satisfies:** R1 — the owner gets a number for how bad a delisting would have to have been before
the lab's edge is an artefact of missing dead companies, and a plain-language judgement on whether
a loss that bad is believable.
**Depends on:** Phase 1 (the harness: `engine/src/seer_engine/delisting.py`,
`engine/scripts/delisting_stress.py`, `engine/tests/test_delisting.py`)
**Difficulty:** NORMAL
**Package:** `docs/plans`, `lab` (plus `web/data`, see the Interface Contract — it is forced by a
test, not chosen)

---

## Goal

Phase 1 built the stress harness but has never pointed it at the real roster. After this phase the
break-even delisting return exists as a measured number for each of the four quant roster entries,
it is written into `docs/plans/2026-10-03-seer-design.md` in §12's voice — in a **new section
appended at the file's tail, numbered at write time** — and it is in the lab journal as one
`insights` row of kind `risk`. Design §12's closing sentence ("*A test that isolates the mechanism
… remains unrun and is the right next step*") stops being a promise.

This phase writes **no code**. It runs a program, reads its output, and writes two documents.

---

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- one new `## <N>.` section at the **tail** of `docs/plans/2026-10-03-seer-design.md`, where `<N>`
  is resolved at write time by reading the file (see Step 5). **Expected `14`, not hardcoded.**
- one row in `insights` in `lab/lab.sqlite` (`kind='risk'`, `method_id` NULL).
- a regenerated `web/data/lab.json`.

**Signature changes:** none.

**Requires (from Phase 1)** — **reconciled 2026-10-07 against phase 1's actual
`_parse()`**, so the spellings below are phase 1's, not this phase's guesses. Confirm them once
with `delisting_stress.py --help` (Step 0b) before the long run:

| Flag phase 1 defines | What phase 2 passes | Why |
|---|---|---|
| `engine/scripts/delisting_stress.py`, runnable under the engine venv | — | the whole phase is invocations of it |
| `--entry NAME` — **repeatable (`action="append"`), NOT comma-separated**; takes a roster name (`RMW-FR`) or a lab candidate id (`M0022-W-TV16`) | four separate `--entry` flags, one per candidate id | the run is roster-scoped, not whole-lab. **An earlier draft of this plan wrote `--candidates a,b,c`; no such flag exists and a comma-joined value would be read as one unknown id** |
| `--hazard {unserved\|all\|NUMBER}` — default `unserved` | **`unserved`** for the base run, **`all`** for the sensitivity | phase 1 computes both rates from the store's own membership (4.00158%/yr and 5.09113%/yr). Passing the symbol uses the measured value and prints its provenance; passing a rounded `0.040` would substitute an estimate for a measurement and print *"given on the command line"* |
| `--returns LIST` — comma-separated, each in `[-1, 0]` | the eight-point grid in Step 3 | the break-even is solved over the grid |
| `--seeds N` (default 100) and `--seed0 N` (default 0) | `--seeds 100`, `--seed0` left at its default | the across-seed spread is half the deliverable |
| `--jobs N` — **default 1**, fork pool, Linux only | `--jobs 6`, after the memory check in Step 1 | phase 1 kept the default at 1 so a careless run on a small box cannot swap; this phase opts in explicitly |
| `--store PATH`, defaulting to `$SEER_RESEARCH_STORE` or `research.STORE_DIR` | `--store "$STORE"`, **and** `SEER_RESEARCH_STORE` exported | **load-bearing** — the worktree has no `engine/.research`; see Step 0c. This is the convention `commands/lab.py:150` and `:214` already use |
| `--csv PATH` — one row per run; refuses to write inside `engine/.research` or `lab/` | a scratch path on every run | **phase 1's Handoffs name the `--csv` output as what phase 2 consumes.** Step 4 reads the numbers out of it instead of transcribing them from a terminal table by eye |
| `--smoke` — one entry, two returns, two seeds | not used; Step 1 spells out an equivalent run with the memory measurement attached | `--smoke` forces `--jobs 1` and its own entry, which Step 1 wants to override |
| `--decline-sessions N` (default 1 = abrupt death) | left at the default | the abrupt death is the conservative base case the index's Decisions table chose |

**Output phase 2 consumes**, also phase 1's to shape: a `=== 1. the delisting hazard … ===` block,
a `=== 2. the stressed runs ===` header, then per entry a `=== NAME  (CANDIDATE) ===` block
carrying an `unstressed:` line, one row per assumed return, and a
`break-even delisting return: …` line (or `NONE on this grid`) followed by a `per seed:` spread
line. The `--csv` columns are `entry, candidate, delisting_return, seed, deaths, start, cagr,
max_drawdown, total_return, trades, spy_cagr, edge_points_per_year, beats_spy`; the unstressed
reference run is the row whose `delisting_return` and `seed` are **empty**.

If `--store` is absent and `$SEER_RESEARCH_STORE` is not honoured, Step 0c's symlink fallback
applies. If any spelling above still disagrees with `--help`, **use `--help`'s and tell the
reconciler** — the flag spellings are phase 1's to choose; the **parameter values** below are this
phase's and must not be changed.

**Leaves alone (owned by others):**
- `docs/plans/2026-10-03-seer-design.md` §1, §5, §11, §12 — and **`seer-fc`'s new §13**. This phase
  appends; it never inserts and never renumbers an existing heading.
- `docs/plans/2026-10-04-method-lab-design.md` (Phase 3).
- `engine/src/seer_engine/delisting.py`, `engine/scripts/delisting_stress.py`,
  `engine/tests/test_delisting.py` (Phase 1 — consumed, not amended).
- every file `seer-fc` claimed: `backtest/metrics.py`, `backtest/tuning.py`, `backtest/report.py`,
  `backtest/b_report.py`, `backtest/wf_report.py`, `web/lib/golive.ts`, `web/lib/metrics.ts`,
  `web/lib/golive.test.ts`, `engine/tests/test_backtest_{tuning,metrics,b_walkforward,report,b_report}.py`.
- `engine/.research` — read only, never written.
- `trials` in `lab/lab.sqlite` — not read-write, not appended, not re-judged.

**One contract item the plan index does not list, and the reconciler must take:**
`web/data/lab.json` is a **third** file this phase must change. `engine/tests/test_lab_snapshot.py:449`
(`test_the_committed_snapshot_is_the_export_of_the_committed_database`) asserts, byte for byte,
that `web/data/lab.json` is `lab export-json` of `lab/lab.sqlite`. Appending an `insights` row
without regenerating the snapshot **fails the suite**, so the index's "Files: 2" is 3. The file is
**not** on `seer-fc`'s claim list (they claimed `web/lib/*`, not `web/data/*`), so this is an
addition to the record, not a conflict — but it is a shared file and the reconciler should know.

---

## Files

| File | Action | Line reference | What changes |
|---|---|---|---|
| `docs/plans/2026-10-03-seer-design.md` | modify (append only) | after the file's **last** line — **284** on the branch as merged to `ba8a05b`, the tail of `seer-fc`'s §13 (an earlier draft said 227, which was the file before §13 landed). Take `wc -l` at write time | one new `## <N>.` section, text in Step 6 |
| `lab/lab.sqlite` | modify (append only) | `insights` table | one row, `kind='risk'`; count goes 32 → 33 |
| `web/data/lab.json` | regenerate | whole file | forced by `test_lab_snapshot.py:449` |

No file under `engine/src`, `engine/scripts`, `engine/tests`, `web/lib` or `web/app` is touched.

---

## Implementation Steps

Throughout, these three paths are constants:

```
WT=/home/miftah/.worktrees/seer/delisting-stress-roster-rules
PY=/home/miftah/seer/engine/.venv/bin/python
STORE=/home/miftah/seer/engine/.research
```

`$PY` is the **main checkout's** virtualenv (the only one that exists). `$STORE` is the **main
checkout's** research store (gitignored, 135 MB of bars, never copied into a worktree).

### Step 0: Get the branch current, and prove the ground before running anything

#### Step 0a — merge `origin/main` first, so `seer-fc`'s §13 is present
**File:** none (git)
**Change:** this is the step that makes the section-number lookup in Step 5 meaningful. `seer-fc`
is adding a **§13** to the same design doc in the shared checkout. If this phase writes its section
before that lands, it will take the number 13 and collide.
**Code:**
```bash
cd "$WT"
git fetch origin
git merge --no-edit origin/main
# If the merge touches docs/plans/2026-10-03-seer-design.md, inspect it:
git log --oneline -3 -- docs/plans/2026-10-03-seer-design.md
grep -n '^## ' docs/plans/2026-10-03-seer-design.md
```
**Impact:** **the merge has already been done once** — the reconciler brought this branch up to
`origin/main` @ `ba8a05b` on 2026-10-07, and `## 13. Revision 2026-10-07 (owner): go-live item 1 is
18 months, and counts no trades` is present at line 232 of a 284-line file. Run the commands anyway
(a peer may have landed more since) and expect the heading list to end at `## 13.`. Re-run
`git fetch origin && git merge --no-edit origin/main` immediately before Step 5; Step 5 resolves
the number from whatever the file holds at that moment.

**Merge, never rebase.** This worktree is shared with the other phases of this set running
concurrently; a rebase would rewrite their commits out from under them.

#### Step 0b — confirm Phase 1 has landed and read its real interface
**File:** `engine/scripts/delisting_stress.py` (read only)
**Change:** none.
**Code:**
```bash
cd "$WT"
test -f engine/scripts/delisting_stress.py || { echo "PHASE 1 HAS NOT LANDED - STOP"; exit 1; }
PYTHONPATH="$WT/engine/src" "$PY" engine/scripts/delisting_stress.py --help
```
**Impact:** every command below is written against the Interface Contract's expected flags.
Reconcile them with this `--help` output before running the long job, not after.

#### Step 0c — make the research store reachable from the worktree
**File:** none (filesystem)
**Change:** `seer_engine.config.REPO_ROOT` is derived from the module's own file path
(`config.py:17`, `Path(__file__).resolve().parents[3]`). With `PYTHONPATH` pointed at the
worktree's `engine/src`, `REPO_ROOT` becomes the **worktree**, and `research.STORE_DIR` becomes
`$WT/engine/.research`, **which does not exist**. Two ways out, in order of preference:
**Code:**
```bash
# Preferred: the store is passed in, the same way `lab run` already takes it.
export SEER_RESEARCH_STORE="$STORE"
# ...and/or pass --store "$STORE" explicitly on the command line (see Step 3).

# Fallback, only if phase 1's script honours neither: a symlink.
ln -sfn "$STORE" "$WT/engine/.research"
```
**Impact:** the symlink fallback has a trap. `.gitignore:21` reads `engine/.research/` **with a
trailing slash**, which matches a directory and *not* a symlink, so the link will show as untracked
in `git status`. It must never be committed. This is exactly why the final commit in Step 9 uses an
**explicit path allowlist** rather than `git add -A`. Remove the link when the phase is done:
`rm -f "$WT/engine/.research"`.

#### Step 0d — record the lab baseline
**File:** none (read only)
**Change:** none. These three numbers are the phase's own guard rails and are re-read in Step 10.
**Code:**
```bash
cd /home/miftah/seer
PYTHONPATH="$WT/engine/src" "$PY" -m seer_engine lab --db "$WT/lab/lab.sqlite" status | head -8
```
**Impact:** **re-measured by the reconciler on 2026-10-07 on this branch merged up to `ba8a05b`**
— the merge did not move any of them:
```
dev trials (N for the DSR): 110
test-window looks used: 0
methods: 37
insights: 32
```
After this phase: **N must still be 110**, **test-window looks must still be 0**, and **insights
must be 33**. Any other combination means something went wrong and the phase is not done.
Note the `--db` flag goes **before** the `status` subcommand (`commands/lab.py:114`), and passing
it explicitly matters: `store.DB_PATH` honours `$SEER_LAB_DB` (`lab/store.py:60`), which parallel
explorer sessions point at the main checkout. This phase's insight belongs in the **worktree's**
committed copy.

---

### Step 1: Smoke the harness against one entry before spending two hours

**File:** none (a run)
**Change:** one cheap invocation that proves the plumbing — store found, candidate resolved,
perturbation applied, table printed — before the real job.
**Code:**
```bash
cd "$WT"
SCRATCH=$(mktemp -d /tmp/delisting-stress.XXXX)   # or this session's scratchpad directory
export SEER_RESEARCH_STORE="$STORE"

PYTHONPATH="$WT/engine/src" "$PY" engine/scripts/delisting_stress.py \
  --store "$STORE" \
  --entry M0007-N20-RAW \
  --hazard unserved \
  --returns 0.00,-0.30 \
  --seeds 2 \
  --jobs 1 \
  --csv "$SCRATCH/smoke.csv" \
  2>&1 | tee "$SCRATCH/smoke.txt"
```
**Impact:** expect store load plus five runs (one unstressed baseline + 2 returns × 2 seeds).
**Budget 60–90 s, not 20.** Phase 1's P4 measured, on this machine under concurrent swarm load,
`load_store` at 23–28 s and each candidate run at **5–11 s** — the analysis's M1 figures (11.3 s and
2–3 s) were taken on a quiet machine and a swarm will not see them. If it does not print a table,
**stop and report the failure.** Do not proceed to Step 3 and do not, under any circumstance, write
numbers into Step 6's template that did not come out of a run.

`0.00` is in the smoke grid deliberately: it is the row Step 4 and Step 6 must keep **separate**
from the unstressed line, and seeing both printed once here is the cheapest way to learn what that
gap looks like before the long run.

**Also measure the memory of one worker here**, because Step 3's `--jobs` choice depends on it and
the machine has 15 GB total / ~11 GB available:
```bash
/usr/bin/time -v env PYTHONPATH="$WT/engine/src" "$PY" engine/scripts/delisting_stress.py \
  --store "$STORE" --entry M0007-N20-RAW --hazard unserved --returns -0.30 --seeds 2 --jobs 1 \
  2>&1 | grep -i "maximum resident"
```
Phase 1 measured this already — 942 MB for the loaded store, ~1,010 MB peak with a prepared panel,
so roughly 940 MB shared plus ~150 MB private per fork worker. Re-measure anyway: the number is
what `--jobs` is chosen from.
Pick `--jobs` as `min(6, floor(available_GB / peak_worker_GB))`. 22 cores are available, so the
binding constraint is memory, not CPU. **6 is the planned value; lower it if the measurement says
to, and say so in the commit message.**

---

### Step 2: Confirm the four candidate ids resolve

**File:** `engine/scripts/survivorship_coverage.py:47-48` (read only — the authority for the
mapping between roster label and lab variant)
**Change:** none.
**Code:**
```bash
cd "$WT"
sed -n '46,49p' engine/scripts/survivorship_coverage.py
```
**Impact:** the four pairs this phase runs, verbatim from that file and from analysis M3:

| roster entry | lab variant | what it is, in plain words |
|---|---|---|
| `RMW-FR` | `M0022-W-TV16` | the weekly-brake book |
| `RAW-FR` | `M0007-N20-RAW` | the raw-momentum book |
| `MOM-FR` | `M0002-REL-85` | the regime-scaled total-return momentum book |
| `MVW-FR` | `M0008-N30-C07` | the min-variance-weighted book |

The fifth roster entry is not a quant book and is not stressed. If any id fails to resolve, stop:
a renamed variant means the store or the registry has moved under this plan and the analysis's
assumptions need re-checking, not working around.

---

### Step 3: The main Monte Carlo — base hazard, 4.0%/yr

**File:** none (a run)
**Change:** the measurement the whole phase exists to take.
**Code:**
```bash
cd "$WT"
export SEER_RESEARCH_STORE="$STORE"

PYTHONPATH="$WT/engine/src" "$PY" engine/scripts/delisting_stress.py \
  --store "$STORE" \
  --entry M0022-W-TV16 \
  --entry M0007-N20-RAW \
  --entry M0002-REL-85 \
  --entry M0008-N30-C07 \
  --hazard unserved \
  --returns 0.00,-0.10,-0.20,-0.30,-0.50,-0.70,-0.90,-1.00 \
  --seeds 100 \
  --jobs 6 \
  --csv "$SCRATCH/base-hazard-unserved.csv" \
  2>&1 | tee "$SCRATCH/base-hazard-unserved.txt"
```
`--entry` is repeatable and is **not** comma-separated — four flags, not one joined value.

**Impact:** 4 candidates × 8 assumed returns × 100 seeds = **3,200 runs**, plus 4 unstressed
baseline runs.

**Budget it on the loaded-machine number, not the quiet one.** The analysis's M1 measured 2–3 s a
run on an idle box; phase 1's P4 re-measured the same four candidates at **5–11 s a run** while the
machine carried several swarm sessions, which is what this plan will actually meet. So:

| | at M1's 2–3 s (quiet) | at P4's 5–11 s (**plan on this**) |
|---|---|---|
| single-threaded | ≈ 2.7 h | **≈ 4.5–9.8 h** |
| at `--jobs 6` | ≈ 25–30 min | **≈ 50 min – 1 h 45** |

Start it in the background and let it finish; do not shorten the seed count to save time — the
across-seed spread is half the deliverable, and a break-even computed from 10 seeds is a number
with no error bar, which is exactly the kind of thing §12's voice refuses to print. If the wall
clock is a problem, raise `--jobs` within the memory budget measured in Step 1; never lower
`--seeds`.

**Why these parameter values, so a later reader does not "tidy" them:**
- `--hazard unserved` selects the **measured unserved-exit rate** — phase 1 recomputes it from
  the store's own membership on every run rather than taking a number from this plan (M2: 404 of
  514 in-window index exits had no bars, against ~10,096 member-years; the exact value is
  4.00158%/yr, which M2 printed rounded as 4.001% and the harness prints as 4.002%). It is the
  rate at which the ranking universe lost a name the backtest could never see die. **Pass the word,
  not a rounded number**: `--hazard 0.040` would be accepted but would substitute an estimate for
  a measurement and would print its provenance as *"given on the command line"*.
- the return grid runs from `0.00` (the engine's **current implicit assumption** — a vanished name
  is force-closed at its last mark, `sim/book.py:742-785`) down to `-1.00` (a total wipeout). The
  break-even lies somewhere on that line or past its end; either answer is informative.
- `--seeds 100` because which names die is random and the answer must not be one draw's luck.

### Step 3b: The sensitivity — all-exit hazard, 5.1%/yr

**File:** none (a run)
**Change:** the upper bound on how often death is injected.
**Code:**
```bash
cd "$WT"
PYTHONPATH="$WT/engine/src" "$PY" engine/scripts/delisting_stress.py \
  --store "$STORE" \
  --entry M0022-W-TV16 \
  --entry M0007-N20-RAW \
  --entry M0002-REL-85 \
  --entry M0008-N30-C07 \
  --hazard all \
  --returns 0.00,-0.10,-0.20,-0.30,-0.50,-0.70,-0.90,-1.00 \
  --seeds 100 \
  --jobs 6 \
  --csv "$SCRATCH/sensitivity-hazard-all.csv" \
  2>&1 | tee "$SCRATCH/sensitivity-hazard-all.txt"
```
**Impact:** another **≈ 50 min – 1 h 45** at `--jobs 6` on the loaded-machine budget above.
`--hazard all` selects M2's **all-exit** hazard (5.09113%/yr, recomputed by the harness) — every
name that left the index inside the window, whether or not the free feed kept its bars. Injecting at that rate is
deliberately pessimistic: it kills more names than actually went unpriced. If the sensitivity's
break-even is close to the base run's, the finding is robust and the section says so; if it is far
shallower, the section says *that*, plainly.

**If either run fails — a crash, an unresolved candidate id, a missing store, a truncated CSV —
the phase stops here and reports the failure.** There is no acceptable substitute for the
measurement, and a fabricated number in the design doc is worse than an unfinished phase — this doc
is the owner's record of what is actually known.

**A completed run that reports `break-even delisting return: NONE on this grid` is NOT a failure.**
It is a first-class, expected result and the strongest answer this test can give. Phase 1's
`break_even(points)` returns `None` by design when the mean edge is still positive at the most
negative point on the grid, and its docstring says the solver *"refuses to extrapolate past the data
it has"*; `_print_entry` prints that case in words, followed by a `per seed:` line saying how many
seeds never broke even. Phase 1's own smoke run already saw it: on `M0022-W-TV16` at `r = -100%` —
a total loss on every injected delisting — CAGR was 8.23%/yr against SPY total-return 7.92%/yr, a
mean edge of **+0.32 points a year**, with one of two seeds crossing at −81.5% and the other never
crossing. So expect a close call on RMW-FR and expect `NONE` to be a live outcome for some or all
four entries. Carry it into Step 4 as *"worse than −100%, i.e. never"*, and write Step 6's **first**
verdict branch. **Never stop on it, and never extrapolate a number to fill the cell.**

---

### Step 4: Read the result out into a working table

**File:** `$SCRATCH/results.md` (scratch, never committed)
**Change:** read the **per-run** numbers the design section needs — the unstressed CAGR, the
`r = 0` CAGR, the thinning cost and the deaths per draw — **out of the two `--csv` files**, not off
the terminal by eye. Do not round away the spread.

**Three quantities are not CSV columns and must come from the tee'd stdout instead**, because the
CSV carries one row per run and phase 1 solves these across runs: the **break-even** (`break-even
delisting return: …`, or `NONE on this grid`), the **across-seed spread** (`  per seed: median …,
p10 …, p90 …`) and **`{{SURVIVORS}}`** (`eligible to be killed: N priced survivors over …
member-years`). Grep them out of the transcripts rather than retyping them:

```bash
grep -E '^=== |^eligible to be killed|^break-even|^  per seed' \
  "$SCRATCH/base-hazard-unserved.txt" "$SCRATCH/sensitivity-hazard-all.txt"
```

**Six numbers per entry, not three.** Phase 1's Handoffs are explicit that the `r = 0` row is
**not** the unstressed row and that the gap between them is not small, so this table carries both
and Step 6 prints both:

**Code:**
```bash
# the unstressed reference run is the row with an EMPTY delisting_return and an EMPTY seed
awk -F, 'NR==1 || $3=="" ' "$SCRATCH/base-hazard-unserved.csv"

# the r = 0 cell, per entry: mean CAGR and mean edge across the 100 seeds
"$PY" - "$SCRATCH/base-hazard-unserved.csv" <<'PY2'
import csv, statistics, sys
rows = list(csv.DictReader(open(sys.argv[1])))
base = {r["entry"]: r for r in rows if r["delisting_return"] == ""}
for entry in dict.fromkeys(r["entry"] for r in rows):
    zero = [r for r in rows if r["entry"] == entry and r["delisting_return"] == "0.0000"]
    b = base[entry]
    print(f"{entry:7s} unstressed CAGR {float(b['cagr'])*100:6.2f}%  edge {float(b['edge_points_per_year']):+5.2f}"
          f"   |  r=0 CAGR {statistics.mean(float(r['cagr']) for r in zero)*100:6.2f}%"
          f"  edge {statistics.mean(float(r['edge_points_per_year']) for r in zero):+5.2f}"
          f"  |  thinning cost {float(b['cagr'])*100 - statistics.mean(float(r['cagr']) for r in zero)*100:5.2f} pts/yr")
    killed = [int(r["deaths"]) for r in rows if r["entry"] == entry and r["delisting_return"] != ""]
    print(f"        deaths per draw: mean {statistics.mean(killed):6.1f}   (this fills DEATHS_PER_SEED)")
PY2
```

Fill this, one row per entry:

```
entry   variant        unstressed   r=0 CAGR   thinning   break-even   across-seed   break-even
                       CAGR/yr      /yr        cost       (unserved)   spread        (all)
RMW-FR  M0022-W-TV16   ...          ...        ...        ...          ...           ...
RAW-FR  M0007-N20-RAW  ...          ...        ...        ...          ...           ...
MOM-FR  M0002-REL-85   ...          ...        ...        ...          ...           ...
MVW-FR  M0008-N30-C07  ...          ...        ...        ...          ...           ...
```

**Impact:** these rows are the only new facts in this phase. Everything else in Step 6 is already
measured and quoted from the analysis.

**The `thinning cost` column is a finding in its own right and must not be folded into the
break-even.** Phase 1 measured it at roughly **one point of CAGR a year** on `M0022-W-TV16`
(unstressed 11.68%/yr against 10.72%/yr at `r = 0`, two seeds). That is the price of having ~150
fewer names to rank over twenty years, **before any delisting loss is assumed at all**. It means
`r = 0` is *not* "no stress", and a section that presents it as the unstressed baseline would
understate what the test found. Report the two as separate rows, always.

"Break-even" is defined for the reader in Step 6's prose as: **the assumed delisting return at
which the book's advantage over total-return SPY falls to zero.** If the harness reports it as
"not reached within the grid" for an entry, that is a legitimate and strong result — write
"worse than −100%, i.e. never" and say what it means, do not extrapolate past the grid.

---

### Step 5: Resolve the section number by reading the file — do not trust "14"

**File:** `docs/plans/2026-10-03-seer-design.md`
**Change:** none yet; this step only computes `<N>`.
**Code:**
```bash
cd "$WT"
git fetch origin && git merge --no-edit origin/main     # one last time; seer-fc may have landed §13 while the Monte Carlo ran
grep -n '^## [0-9]' docs/plans/2026-10-03-seer-design.md
LAST=$(grep -o '^## [0-9]\+' docs/plans/2026-10-03-seer-design.md | grep -o '[0-9]\+' | sort -n | tail -1)
NEXT=$((LAST + 1))
echo "existing highest section: $LAST ; this phase writes section: $NEXT"
```
**Impact:** **re-measured by the reconciler on 2026-10-07 against the branch merged up to
`origin/main` @ `ba8a05b`:** `seer-fc`'s section **has landed**. The file is **284 lines** and its
headings run `## 1.` … `## 13. Revision 2026-10-07 (owner): go-live item 1 is 18 months, and
counts no trades`. So `LAST` is **13** and `NEXT` is **14**, with no gap and no contingency.

**The number printed by the command above still wins**, because another session may append
between now and the write — but the "§13 has not landed yet" branch of this step is dead and the
implementer should not plan around it. If `LAST` comes back as anything other than 13, something
landed while the Monte Carlo ran: take `LAST + 1`, and say so in the commit message. A gap in the
numbering is a cosmetic flaw; a collision is a merge conflict in the owner's design record.

**No collision with phase 3 is possible.** Phase 3 appends to a *different* file
(`docs/plans/2026-10-04-method-lab-design.md`, where it takes §8). The two phases never open the
same document.

---

### Step 6: Append the new section at the file's tail

**File:** `docs/plans/2026-10-03-seer-design.md` — **appended after the final line**, which on the
branch as merged to `ba8a05b` is **line 284**, the tail of `seer-fc`'s §13. (An earlier draft of
this plan said line 227; that was the file before §13 landed.) Take `wc -l` at write time.
**Change:** append the text below. Replace every `{{...}}` with a number from Step 4. Leave nothing
in braces. **Append — never insert, never renumber an existing heading.**
**Code:**
```bash
cd "$WT"
# write the finished section to a scratch file first, then append in one move
printf '\n' >> docs/plans/2026-10-03-seer-design.md
cat "$SCRATCH/section.md" >> docs/plans/2026-10-03-seer-design.md
tail -5 docs/plans/2026-10-03-seer-design.md
```

The exact contents of `$SCRATCH/section.md`, with placeholders marked:

````markdown
## {{N}}. Measured 2026-10-07: how bad a delisting would have to be before the edge goes

§12 measured the hole and ended by naming the test it could not do: *"injecting synthetic
delistings at the historical rate and solving for the break-even delisting return — remains unrun
and is the right next step if a decision ever turns on this."* This section is that test. It was
run because the era contrast in §12 is confounded with market regime and therefore cannot tell
"better data" from "different market"; this one is not, because it changes the data and holds the
market fixed.

**The question, in plain words.** Our price history is missing 522 companies that were in the index
and have since vanished. The worry is that the books look good only because the companies that went
to zero are invisible to them. We cannot buy the missing prices, so we ask the question backwards:
**how much would each of those companies have had to lose, on the day it disappeared, before the
book's advantage over the market disappears too?** That number is the break-even delisting return.
If it is a loss so severe that no plausible set of real delistings reaches it, the hole does not
explain the edge.

**What was injected, and at what rate.** Companies were killed off at random inside the ranking
universe — the name stops being priced from its death date, and any position in it is closed at a
rewritten final mark. The rate was **measured, not assumed**: from the store's own point-in-time
membership, 514 symbols left the index inside the dev window across roughly **10,096 member-years**,
which is an exit rate of **5.1% a year**; **4.0% a year** of it is the part a free feed drops
entirely (404 names with no bars at all). The main run injects at **4.0%/yr** — the rate at which
the universe lost a name we could never have watched die. **5.1%/yr** is carried as the pessimistic
sensitivity.

**First, the part that costs something even when nobody loses anything.** Taking companies out of
the pool at the historical rate makes the books worse **before any assumed loss is applied at
all**, simply because there are fewer names left to choose from. The table below therefore shows
three different things and they must not be read as one: what each book returned untouched, what it
returned once companies started disappearing but every holder was paid the last price anyone saw,
and how bad the loss would have to get before the advantage runs out.

| entry | the book | return/yr untouched | return/yr with companies vanishing, paid in full | the cost of a thinner pool |
|---|---|---|---|---|
| RMW-FR | weekly brake | {{CAGR_RMW}} | {{CAGR0_RMW}} | {{THIN_RMW}} |
| RAW-FR | raw momentum | {{CAGR_RAW}} | {{CAGR0_RAW}} | {{THIN_RAW}} |
| MOM-FR | regime-scaled momentum | {{CAGR_MOM}} | {{CAGR0_MOM}} | {{THIN_MOM}} |
| MVW-FR | min-variance weights | {{CAGR_MVW}} | {{CAGR0_MVW}} | {{THIN_MVW}} |

The last column is roughly {{THIN_WORDS}} a year, and **none of it is a delisting loss**. It is the
price of ranking from a pool that keeps losing names — about {{DEATHS_PER_SEED}} companies removed
over the twenty years. It matters here because it is easy to mistake the middle column for "no
stress", and it is not: **no stress is the first column.**

**Then, the break-even.** Break-even delisting return per roster entry, {{SEEDS}} random draws of
who dies per assumed return:

| entry | the book | break-even at 4.0%/yr | spread across draws | break-even at 5.1%/yr |
|---|---|---|---|---|
| RMW-FR | weekly brake | {{BE_RMW}} | {{SPREAD_RMW}} | {{BE51_RMW}} |
| RAW-FR | raw momentum | {{BE_RAW}} | {{SPREAD_RAW}} | {{BE51_RAW}} |
| MOM-FR | regime-scaled momentum | {{BE_MOM}} | {{SPREAD_MOM}} | {{BE51_MOM}} |
| MVW-FR | min-variance weights | {{BE_MVW}} | {{SPREAD_MVW}} | {{BE51_MVW}} |

Read a row like this: a {{BE_RAW}} break-even for RAW-FR means every disappearing company it held
would have had to lose {{BE_RAW_WORDS}} of its value, on the way out, every time, across twenty
years, before the book stops beating the market. The break-even is measured against the market, so
the cost of the thinner pool is already inside it — which is part of why it lands where it does.

**Is a loss that bad plausible? {{VERDICT_HEADLINE}}.**
{{VERDICT_PARAGRAPH}}

**What the backtest has been assuming all along, now visible.** When a company stops being priced
mid-run, the simulator closes the position **at its last known price** and calls the trade forced
(`sim/book.py`, `close_book_unpriced`). That is a delisting return of exactly **0%** — sold whole at
the last close. It has been invisible until now only because no symbol in the store disappears
mid-window. It is the zero on the left-hand end of the grid above, and it is the assumption this
whole section is stress-testing. **It is not the same thing as "no delistings":** the zero column
still has companies disappearing out of the ranking pool, which is what the first table above
measures. Nothing in this section should be read as saying a 0% delisting return is free.

**The limits of this test, stated rather than buried — four of them.**

1. **The death is abrupt.** The injected company goes from fully priced to gone with no warning, so
   the book gets no chance to sell it on the way down. Every one of these strategies has a trend
   gate that would, in reality, have been pushing it out of a falling name for weeks. So the
   break-even above is an **upper bound on the damage**: reality is kinder than this test, and the
   real break-even is a *worse* loss than the number printed. We chose it that way on purpose — a
   test meant to reassure should be run in the direction that makes reassurance hard.
2. **It cannot touch 118 of the 522 missing names.** The hole splits in two, which §12 could not
   see because it counted the 522 as one number. **404** names left the index inside the window and
   have no bars — those are the survivorship case proper, and those are what this test injects.
   The other **118 were still index members on the last day of the dev window and have no bars at
   all.** They never died inside the window; they died afterwards, and the free data source dropped
   them retroactively. **No delisting injection can model those 118**, because the thing that is
   missing is a twenty-year price path, not a death. Their effect is not flattery — it is a thinner
   pool to rank from, for twenty years — and it stays unmeasured by this section.
3. **It injects the historical *rate*, not the historical *count*.** The hazard is applied to the
   {{SURVIVORS}} companies that are still priced and still in the index — the only ones a
   simulation can take away — which kills about {{DEATHS_PER_SEED}} of them per draw. History
   actually lost 404 unpriced names. The test says what that rate of disappearance costs inside the
   universe the books could really rank from; it does not and cannot restore the 404, because there
   are not that many priced names left to remove.
4. **It is the dev window only.** This changes nothing about the test window, which is still
   completely unspent.

**What this cost.** Nothing that matters. The stress harness re-runs the backtest in memory against
a perturbed copy of the price history; it **records no lab trial**, so the luck test's trial count
**N stays at 110**; it **spends no test-window look**, so the count stays at 0; and it writes
nothing to `engine/.research`, so no recorded trial's configuration fingerprint moves. It can be
re-run any time the question comes back.

**What it does not change.** The decision not to buy survivorship-free data (§12) stands or falls on
this number, and the owner should reread §12's last paragraph with it in hand. Nothing on the paper
roster moves on the strength of a diagnostic.
````

**Impact:** this is the only prose the owner will read about the stress test. Three writing rules
bind it, from handover §6 and from §12's own habits:
- **Numbers only with their meaning.** Every figure above has a sentence saying what it would mean
  if it were true. Keep that pairing when filling the placeholders.
- **No jargon without a gloss.** "Break-even delisting return", "hazard" and "member-years" are each
  explained in the sentence that introduces them. Do not add a new unexplained term.
- **No ids or digests.** The lab variant ids (`M0022-W-TV16` etc.) appear in the design doc's §12
  already, so a single parenthetical there is in keeping — but the **insight body in Step 7 carries
  none at all**.

**Filling `{{VERDICT_HEADLINE}}` and `{{VERDICT_PARAGRAPH}}` — the judgement, not a number.**
The implementing session writes this from the measured break-even, using these anchors. Pick the
branch the measurement lands in; do not hedge across two.

- **Break-even not reached within the grid (worse than −100%).** Headline: *"No — it cannot be
  reached at all."* Paragraph: a delisting return worse than −100% is impossible; a shareholder
  cannot lose more than everything. So at the measured rate of disappearance, there is no
  assumption about delisting losses, however extreme, under which the missing companies account for
  these books' advantage. That is the strongest answer this test can give, and it closes the
  question §12 left open.
- **Break-even between about −60% and −100%.** Headline: *"Almost certainly not."* Paragraph: this
  would require nearly every company that left the index to have been close to a total loss on its
  way out. Most index exits are not deaths — they are mergers, acquisitions and buyouts, which pay
  shareholders, often at a premium. Of the 522 missing names, **32** carry the `Q` bankruptcy
  suffix. Thirty-two names cannot carry an average loss of this size across 404 exits.
- **Break-even between about −30% and −60%.** Headline: *"Unlikely, but no longer unimaginable."*
  Paragraph: say plainly that this is the uncomfortable middle — such an average loss is not
  physically impossible across a population that includes 32 bankruptcies, though it is well above
  what a mostly-merger exit population would produce. Recommend that §12's "revisit when a decision
  actually hinges on it" be treated as now hinging, and that the paid-feed question be put back to
  the owner.
- **Break-even shallower than about −30%.** Headline: *"Yes — and that is a problem."* Paragraph:
  say it without softening. A loss that mild is entirely plausible for a population of delistings,
  which means the missing companies **could** account for the edge and the era contrast in §12 was
  not enough. Recommend the paid feed be reconsidered immediately, note that doing so resets all 110
  recorded trials and their luck scores, and note that forward paper trading is unaffected by this
  worry either way because its survivors are not yet known.

In every branch, add one sentence on whether the 5.1%/yr sensitivity changes the answer.

---

### Step 7: Append the lab insight

**File:** `lab/lab.sqlite`, `insights` table
**Change:** one row, `kind='risk'`, no `--method` (the finding is about four entries, not one
method, and a `method_id` would misfile it).
**Code:**
```bash
cd /home/miftah/seer
cat > "$SCRATCH/insight-body.md" <<'BODY'
Our price history is missing 522 companies that were once in the index and have since vanished,
and the worry has always been that the strategies look good only because the companies that went
to zero are invisible to them. We cannot buy the missing prices, so we asked the question
backwards: how much would each of those companies have had to lose on the day it disappeared
before the strategy's advantage over the market disappears too?

Companies were killed off at random inside the ranking universe, at a rate measured from our own
index membership rather than guessed: 4.0% a year is the rate at which the universe lost a company
whose prices we never had, and 5.1% a year is the rate at which it lost any company at all, both
measured across about ten thousand company-years. Each strategy was re-run a hundred times at each
assumed loss.

The answer: the loss would have to be {{PLAIN_RANGE}} on every vanishing company, every time, for
twenty years, before these strategies stop beating the market. {{VERDICT_SENTENCE}}

One thing worth separating out. Even when every vanishing company is sold whole at the last price
anyone saw - no loss at all - the strategies still earn about {{THIN_WORDS}} a year less than they
do untouched, simply because there are fewer companies left to choose from. That is the price of a
thinner pool, not the price of a delisting, and it is already there before any loss is assumed.

Two things this cannot tell us, and they matter. First, the simulated company dies with no warning,
so the strategy gets no chance to sell on the way down - in reality its trend rules would have been
pushing it out for weeks. That makes this an upper bound on the damage: the real answer is kinder
than the one above. Second, of the 522 missing companies only 404 actually left the index inside
the period we tested, and those are the ones we simulated. The other 118 were still in the index on
the last day and are simply absent from our prices - they died later and were dropped from the
record afterwards. Nothing we inject can model them, because what is missing there is twenty years
of prices, not a death. Their cost is a thinner pool to choose from, and it stays unmeasured.

This cost nothing: it recorded no trial, so the luck test's trial count is unchanged; it spent none
of the held-back test period; and it left the price store untouched.
BODY

PYTHONPATH="$WT/engine/src" "$PY" -m seer_engine lab --db "$WT/lab/lab.sqlite" insight \
  --kind risk \
  --title "{{INSIGHT_TITLE}}" \
  --file "$SCRATCH/insight-body.md"
```
**Run Step 8 immediately after this command, with nothing in between** — not a test run, not a
commit, not a break. Between the insert and the regeneration, `test_lab_snapshot.py:449` is red for
**every** session in this shared worktree, phase 5's included (see Handoffs).

**Impact:** prints the new row's id. The `insights` table refuses UPDATE and DELETE by trigger
(`lab/store.py:198-201`), so **a wrong insight is corrected by appending a newer one, never by
deleting**. Proofread the body before running the command, not after.

Placeholders in the body:
- `{{PLAIN_RANGE}}` — the break-even in words, no percent sign mathematics: e.g. *"more than
  everything the company was worth — which is impossible"*, or *"about three-quarters of the
  company's value"*. One phrase covering all four entries if they cluster; a sentence per entry if
  they do not.
- `{{THIN_WORDS}}` — the cost of the thinner pool in plain words, e.g. *"about one percentage
  point"*. The same figure as the design section's `{{THIN_*}}` column. **Not** rolled into
  `{{PLAIN_RANGE}}`: they are different costs and the owner must be able to tell them apart.
- `{{VERDICT_SENTENCE}}` — one sentence, the same judgement as the design section's headline.
- `{{INSIGHT_TITLE}}` — a plain sentence, no ids, no digests, under ~90 characters. For example:
  *"A vanishing company would have to lose nearly everything before it explains our edge"*.

**Hard rules on the body, from handover §6 and the plan index's invariant 7:**
- **no method ids, no candidate ids, no config digests, no file paths** — the body above contains
  none, and the placeholders must not introduce any;
- no "DSR", "MAR", "hazard", "Monte Carlo", "break-even" — each of those is either glossed away or
  absent above; keep it that way;
- the body is the owner's reading copy, not a log line.

---

### Step 8: Regenerate the web snapshot

**File:** `web/data/lab.json`
**Change:** regenerate so it is byte-for-byte the export of the database it now describes.
**Code:**
```bash
cd /home/miftah/seer
PYTHONPATH="$WT/engine/src" "$PY" -m seer_engine lab --db "$WT/lab/lab.sqlite" export-json
cd "$WT" && git diff --stat web/data/lab.json
```
**Impact:** without this, `engine/tests/test_lab_snapshot.py:449` fails with its own instruction
("*web/data/lab.json is not the export of lab/lab.sqlite: run `python -m seer_engine lab stage`*").
`export-json` with no `--out` writes `<the database's repo>/web/data/lab.json`
(`lab/store.py:1691`, `snapshot_path`), which with `--db` pointed at the worktree is the worktree's
copy — that is why `--db` is passed rather than relying on `$SEER_LAB_DB`.

`lab stage` would also work and would `git add` both files, but it stages under a lock and its
`git add` is broader than this phase's allowlist. Prefer `export-json` plus the explicit `git add`
in Step 9.

---

### Step 9: Commit with an explicit path allowlist

**File:** none (git)
**Change:** three paths, named. Never `git add -A` — this worktree may be shared with other phases
of the same plan set running concurrently, and Step 0c may have left an untracked `engine/.research`
symlink in it.
**Code:**
```bash
cd "$WT"
rm -f engine/.research          # only if Step 0c's fallback symlink was used
git add docs/plans/2026-10-03-seer-design.md lab/lab.sqlite web/data/lab.json
git status --short
git commit -F - <<'MSG'
docs(design): what a delisting would have to cost before the edge is an illusion

§12 measured the survivorship hole and named the test it could not run. This runs it:
synthetic delistings injected into the ranking universe at the measured 4.0%/yr
unserved-exit rate (5.1%/yr as the pessimistic sensitivity), 100 seeds per assumed
delisting return, over the four quant roster entries, solving for the loss at which
each book's advantage over total-return SPY reaches zero.

The injected death is abrupt, so the number is an upper bound on the damage. The
section says what the test cannot answer: 118 of the 522 missing names were still
index members at the window's end and have no bars at all, and no delisting injection
can model a missing price path.

No lab trial recorded, N still 110, 0 test-window looks spent, engine/.research
untouched. The new section is appended at the file's tail with its number resolved at
write time; §1, §11, §12 and §13 are not touched.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```
**Impact:** `git status --short` before the commit must show exactly those three paths staged and
no `engine/.research`. If it shows more, something outside this phase's scope got picked up.

---

### Step 10: Prove the guard rails held

**File:** none
**Change:** none.
**Code:**
```bash
cd /home/miftah/seer
PYTHONPATH="$WT/engine/src" "$PY" -m seer_engine lab --db "$WT/lab/lab.sqlite" status | head -8
```
**Impact:** must read:
```
dev trials (N for the DSR): 110      <- unchanged
test-window looks used: 0            <- unchanged
methods: 37                          <- unchanged
insights: 33                         <- was 32
```
Any other reading is a failure of the phase, not a detail.

---

## Verification

**Build:** there is nothing to build — this phase adds no code. The equivalent check is that the
appended markdown did not corrupt the file:
```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
grep -n '^## ' docs/plans/2026-10-03-seer-design.md   # headings strictly ascending, no duplicates
grep -c '{{' docs/plans/2026-10-03-seer-design.md     # must print 0 - no placeholder survived
```

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest tests -q
```
Expect **0 failed, 0 skipped**. The branch baseline is **3197 collected** — re-counted by the
reconciler at `ba8a05b`, so `seer-fc`'s go-live commit did not change it. This phase adds no test,
but it runs in a shared worktree **after** phases 1 and 4 have landed theirs, so the number will be
**3197 plus phase 1's `test_delisting.py` plus phase 4's 3**. What this phase asserts is
`0 failed, 0 skipped` and a count no lower than 3197 — never a specific total. **A run reporting
`385 skipped` means
`PG_TEST_URL` was not exported and the result is worthless** — a confident green missing a third of
the suite (handover §7). **A run that does not set `PYTHONPATH` silently tests the main checkout,
not this branch.** Both flags, every time.

The test that specifically guards this phase's work is
`engine/tests/test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database`.
If it fails, Step 8 was skipped.

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine
/home/miftah/seer/engine/.venv/bin/ruff check --no-cache src tests    # All checks passed
```

**Manual check:** read the appended section end to end as the owner would — someone who is not a
quant. Every number has its meaning beside it; no term is used before it is explained; the three
stated limits are all present and are not softened. Then read the insight body on its own and
confirm it contains no id, no digest, no file path, and no unglossed jargon.

**Exit criteria:**
1. An answer to the break-even question is printed in the new design section for each of RMW-FR,
   RAW-FR, MOM-FR and MVW-FR — **either a break-even delisting return, or an explicit "not reached
   on this grid: worse than −100%, i.e. never"**, which is phase 1's `break_even(...) -> None` case
   and a legitimate, expected result — with the 4.0%/yr injection rate named, the seed count named,
   and the across-seed spread shown. No cell is filled by extrapolating past the grid.
2. The section states a plain-language judgement on whether a loss that bad is plausible, in one of
   the four branches in Step 6, without hedging across two.
3. The section states that the injected death is abrupt and that this makes the figure an upper
   bound on the damage.
4. The section states that 118 of the 522 missing names cannot be modelled by any delisting
   injection, and why.
5. **The section reports the true unstressed run and the `r = 0` run as separate rows**, names the
   gap between them as the cost of a thinner ranking pool (phase 1 measured it at roughly one point
   of CAGR a year), and nowhere presents `r = 0` as "no stress". The insight body carries the same
   separation in plain words.
6. The section states that the harness injects the historical *rate* into the ~409 priced
   survivors, not the historical *count* of 404 unpriced exits, and says why it cannot do the
   latter.
7. The section's number is the next free one, taken from the file — **14** on the branch as merged
   to `ba8a05b` — and `## 13.` is untouched. `git diff` shows **only appended lines** in that file.
8. `lab status` reads N = 110, 0 test-window looks, 37 methods, 33 insights.
9. The commit's file list equals the three-path allowlist exactly, and `engine/.research` is not
   tracked. (`git status` will also show peer phases' in-flight work — the worktree is shared;
   check the **commit**, not the status.)
10. The full suite passes with `PYTHONPATH` and `PG_TEST_URL` set, **0 failed and 0 skipped**, at a
   count no lower than the branch baseline of 3197.

---

## Handoffs

- **Phase 1 owns the harness, including its flag names.** If `--help` disagrees with the Interface
  Contract above, use `--help`'s spelling and tell the reconciler — do not patch
  `delisting_stress.py` from this phase.
- **The paid-feed decision (§12's last paragraph) is the owner's, not this phase's.** If the
  judgement lands in the third or fourth branch of Step 6, the section *recommends* a revisit and
  stops there. No phase of this plan set buys data or rebuilds `engine/.research` (plan index,
  *Out of scope*).
- **The 118 unmodellable names are an open measurement, left deliberately open.** Quantifying what
  a 20-year-thinner ranking pool costs would need synthetic price paths for 118 companies, which
  fabricates the one thing no free source can supply. It is named in the design section as a known
  unmeasured limit and is not scheduled here. If anyone picks it up, it is a new requirement, not
  part of R1.
- **The roster is not touched by this phase**, whatever the break-even says. Whether a finding like
  this may ever move a roster entry is Phase 3's rule (R4) and Phase 5's verdict (R3). A shallow
  break-even would be evidence *for the lab's record*, and this phase deliberately does not reach
  for the roster with it.
- **`web/data/lab.json` is a third file**, forced by `test_lab_snapshot.py:449`, against the plan
  index's "Files: 2". Flagged to the reconciler in the Interface Contract.
- **Cross-phase sequencing with Phase 5.** Phase 5 also lands in the wave after its dependency.
  Both phases write disjoint paths — Phase 5 writes only `docs/handover/` and conditionally
  `paper/roster.py` — so there is no file collision. **There is, however, a one-command window in
  which the shared worktree is red:** between Step 7 (the insight is written to `lab/lab.sqlite`)
  and Step 8 (`web/data/lab.json` is regenerated), `test_lab_snapshot.py:449` fails for *every*
  session in the worktree, phase 5's verification included. **Run Steps 7 and 8 back to back, with
  nothing between them**, and do not start a full-suite run inside that window. If phase 5 reports
  a snapshot failure, check whether this phase was mid-window before investigating anything else. If Phase 5's conditional roster edit *does*
  land, it will need its own `export-json`; that is Phase 5's problem, not this one's.

---

## Rollback

This phase is three appends and nothing else, so undoing it is clean — with one permanent
exception, which is the lab's own rule and not an accident of this plan.

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
git revert --no-edit <this phase's commit sha>
```

That restores `docs/plans/2026-10-03-seer-design.md` to its pre-phase tail, `lab/lab.sqlite` to its
32-insight state and `web/data/lab.json` to its matching export, and it is safe because the phase
appended only — no existing design section and no recorded trial was edited.

**The exception.** If the *content* of the insight turns out to be wrong after it has been pushed,
it is **not** deleted. `insights` refuses DELETE by trigger (`lab/store.py:200-201`) and the lab's
standing rule is that a wrong journal entry is corrected by appending a newer one. Write a second
`risk` insight that says what the first one got wrong and why, and leave the first in place. This
plan does not make an exception to that rule.

**What never needs rolling back:** no database was migrated, no `config_digest` moved, no trial was
written, no test-window look was spent, and `engine/.research` was never opened for writing. If
Step 0c's symlink was created and somehow committed, remove it with
`git rm --cached engine/.research` — but Step 9's path allowlist exists so that cannot happen.
