> Adopted from `/home/miftah/seer/.workflows/orchestration/lab-exposure-diagnostic/PLAN.md` phase 2. Source: `.workflows/plan/lab-exposure-diagnostic/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Run it over the five, and journal the answer

**Plan set:** `LAB_EXPOSURE_DIAGNOSTIC_PLAN.md`
**Analysis:** `docs/analyzer/20261012-100551-X4P9_code_analyzer.md`
**Satisfies:** R2 (run the diagnostic over the five surviving kin-clean dev-eligible methods and
journal the answer) — R3 (hold the report-only constraint while doing it)
**Depends on:** Phase 1 — `lab exposure` must be committed and green before a single step below runs
**Difficulty:** NORMAL
**Package:** `lab/`, `docs/backtests/`, `web/data/`, `.workflows/`

---

## Goal

After this phase the lab can answer, in the owner's own words, the question the handover's §2
asks: of the five methods that are still alive, how much of each book's money was ever in its own
picks, and what did those picks do against the market once the parked money and the brakes were
taken away. Five plain-words observations and one synthesis are in the journal, a one-paragraph
verdict and the full grid are in `docs/backtests/2026-10-12-exposure-diagnostic.md` with its
committed companion `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv`, and the lab's N
(354 dev trials) and its test-window look budget (4) are exactly where they were.

**This phase writes no Python.** It runs the command phase 1 built, reads the answer, writes
prose, and commits the database through `lab stage`.

---

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `docs/backtests/2026-10-12-exposure-diagnostic.md` (new file, the write-up + the full grid).
  The name follows this directory's existing convention exactly: `YYYY-MM-DD-slug.md` with a
  committed companion `-grid.csv`, as `2026-10-08-how-many-names.md` and
  `2026-10-08-how-many-names-grid.csv` do.
- `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` (new file, **committed**) — the
  machine-readable variant x arm x era grid, written straight there by `lab exposure --csv` at
  Step 3 rather than into a scratch directory.
- 5 `observation` rows in `lab/lab.sqlite` `insights` — **written by `lab exposure` itself**, one
  per method, not by hand
- 1 `synthesis` row in `lab/lab.sqlite` `insights` — written by hand with `lab insight`
- 1 completed task entry in `.workflows/todos.md`
- `web/data/lab.json` is **regenerated wholesale** by `lab stage` (it already exists; its content
  changes because six insight rows were added)

**Signature changes:** none

**Requires (from earlier phases):** phase 1's frozen CLI surface, copied verbatim from its
Interface Contract — this plan's commands are written against it, not guessed:

```
lab exposure M0030 [M0024 ...] [--only IDS] [--store DIR] [--csv PATH] [--no-journal]
```

- positional `method` ids, one or more; `--only IDS` (alias `--candidate`) narrows to named
  recorded variants; `--store DIR` is the dev store (a test-window store is refused); `--csv PATH`
  writes the full variant x arm grid at full precision; `--no-journal` writes nothing at all.
- Exit codes: 0 ok, 2 a lab refusal, 1 anything else.
- It prints four arms per recorded variant (`recorded`, `picks`, `picks, full`, `parked` — the
  `parked` column only where the inner allocator declares something it holds), the per-era grid,
  and a closing line giving N (dev trials) and the test-window looks before and after.
- Unless `--no-journal`, it writes **exactly one `observation` per named method and nothing else**
  — five rows for the five ids here, `insights` 184 -> 189. The `synthesis` is written by hand at
  Step 7.
- Phase 1: `engine/src/seer_engine/lab/exposure.py` and `engine/tests/test_lab_exposure.py` exist,
  `ruff check engine` is clean and `pytest engine/tests` is green.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/exposure.py` (Phase 1)
- `engine/src/seer_engine/commands/lab.py` (Phase 1)
- `engine/tests/test_lab_exposure.py` (Phase 1)
- everything else under `engine/`, `web/` (apart from the generated `web/data/lab.json`), `db/`,
  `docs/plans/LAB_EXPOSURE_DIAGNOSTIC_PLAN.md`

**Hard stop rule.** If the run exposes a bug in phase 1's code — a crash, an arm that is
obviously wrong, a report-only violation — **report it and stop**. Do not edit
`engine/src/seer_engine/lab/exposure.py`. A fix is a follow-up commit on top of phase 1, not a
silent amendment to a finished phase.

---

## Files

| File | Action | What changes |
|---|---|---|
| `lab/lab.sqlite` | modify (append-only) | 5 `observation` rows written by the command + 1 `synthesis` row written by `lab insight`; insights go 184 → 190. Nothing else. |
| `web/data/lab.json` | regenerate | by `lab stage`, from the database above |
| `docs/backtests/2026-10-12-exposure-diagnostic.md` | create | the verdict paragraph, in plain words, and the full method × variant × arm × era grid |
| `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` | create | the machine-readable grid, written by `lab exposure --csv` at Step 3 and committed beside the write-up, per this directory's existing convention |
| `.workflows/todos.md` | modify | one completed task entry appended at the top of `## Completed Tasks`, plus the header counters |

**Five files**, and nothing else may appear in the commit. Verify with
`git diff --cached --name-only` at Step 9.

---

## Baseline, measured 2026-10-12 at base commit `85f65bd`

These are the numbers Step 2 must reproduce. They were read with a read-only connection, so the
file was not migrated to read them.

| Thing | Value |
|---|---|
| `lab/lab.sqlite` blob on `origin/main` | `3d2f4301191b6c3229c92b0df849e15ae31c5097` |
| `trials` (all) | 358 |
| `trials WHERE window='dev'` — **the lab's N** | 354 |
| `trials WHERE window='test'` — the look budget | 4 |
| `trial_moments` | 244 |
| `trial_funding` | 230 |
| `trial_provenance` | 358 |
| `insights` | 184 |
| `methods` | 130 — `idea` 50, `rejected` 59, `dev-eligible` 15, `test-failed` 4, `blocked-data` 2 |

The five methods and their recorded dev variants (23 trials in total — the whole run is
23 × 4 arms, which the analysis measured at 1.8–5.4 s per run, so under ten minutes plus one
10 s store load):

| Method | Family | Dev variants | Eligible variants |
|---|---|---|---|
| M0024 | `stock-seasonality` | `SAME-N20`, `NET-N20`, `SAME-N40`, `SAME-N20-NOTREND`, `SAME-N20-RANKSUM`, `SAME-N20-BLEND-RM` (6) | none |
| M0028 | `stock-short-term-reversal` | `CALM-RESID`, `CALM-RAW`, `PLAIN-RESID`, `CALM-RESID-N10`, `BLEND-RM` (5) | `BLEND-RM` |
| M0030 | `stock-core-satellite` | `C70T`, `C50T`, `C50A` (3) | none |
| M0044 | `stock-momentum-attention` | `TV22-N21`, `TV18-N21`, `TV14-N21`, `NOBRAKE` (4) | `TV14-N21` |
| M0053 | `stock-overnight-intraday` | `TOTON20-TV14`, `TOTON20-TV16`, `TOTON20-TV18`, `TOTON30-TV16`, `RESON20-TV16` (5) | all but `TOTON20-TV18` |

Two of these are free cross-checks worth looking at when the answer comes back:

- **M0030 is parked SPY by construction** (an SPY core with a residual-momentum satellite). A
  large park share there is the *expected* result, not a finding. The finding for M0030 is what
  the satellite alone did — the `-FULL` arm.
- **M0044 already has a recorded `NOBRAKE` variant.** Its `-FULL` arm on any braked variant should
  land close to the recorded `NOBRAKE` row's shape. They are not identical runs and must not be
  compared number-for-number (invariant 8), but a wild divergence is a reason to look twice at the
  wrapper before trusting the rest of the grid.

---

## Environment, fixed for every command below

Every command in this plan runs from the worktree root with these three things set. Copy this
block into the shell once; it is assumed by every step.

```bash
export WT=/home/miftah/.worktrees/seer/lab-exposure-diagnostic
export PY=/home/miftah/seer/engine/.venv/bin/python
export STORE=/home/miftah/seer/engine/.research          # NOT in the worktree — never rebuild it
export PYTHONPATH=$WT/engine/src                          # or pytest/the CLI silently uses main
export RUNDIR=/tmp/exposure-20261012                      # transcripts and the CSV; never committed
mkdir -p "$RUNDIR"
cd "$WT"
```

Why each one:

- `PYTHONPATH=$WT/engine/src` — without it the main checkout's `seer_engine` is imported and
  `lab exposure` does not exist there. It also makes `config.REPO_ROOT` resolve to **this
  worktree** (`config.py:17`, `parents[3]`), so `store.DB_PATH` is `$WT/lab/lab.sqlite` and
  `store.snapshot_path` is `$WT/web/data/lab.json`. That is what we want: this phase commits from
  this worktree.
- `STORE` — the research store is not in worktrees. A rebuild is ~30 minutes for nothing.
- `RUNDIR` under `/tmp` — the raw CSV and the terminal transcript are working material, not repo
  artefacts. If your session has a scratchpad directory, use that instead; the only rule is that
  it is **not** inside `$WT`.

`SEER_LAB_DB` and `SEER_RESEARCH_STORE` are **unset** and must stay unset: `--store` is passed
explicitly, and the database we want is this worktree's own `lab/lab.sqlite`.

---

## Implementation Steps

### Step 0: Confirm phase 1 landed, and read its CLI surface verbatim

**File:** none — this is a gate
**Change:** refuse to start until phase 1 is actually on this branch and green.

```bash
cd "$WT"
git status --short
git log --oneline -3
test -f engine/src/seer_engine/lab/exposure.py && echo "exposure.py: present" || echo "MISSING"
test -f engine/tests/test_lab_exposure.py       && echo "test file: present"  || echo "MISSING"
sed -n '1,200p' .workflows/plan/lab-exposure-diagnostic/phase-1.md
```

Then read the **live** CLI surface rather than trusting this plan's spelling of it:

```bash
cd "$WT" && $PY -m seer_engine lab exposure --help
```

**The flag names in Step 3 below are phase 1's frozen CLI surface**, copied from its Interface
Contract: positional method ids, `--only IDS` (alias `--candidate`), `--store DIR`, `--csv PATH`,
`--no-journal`; exit 0 ok, 2 a lab refusal, 1 anything else. This `--help` read is belt and
braces, not the source of those commands — Step 3 is correct as written and does not depend on
this step. If `--help` nevertheless shows a different spelling, **use what `--help` prints**,
record the difference under **Drift** in the todos entry at Step 10, and say so in the report: a
surface that moved after phase 1 landed is a finding about phase 1, not a licence to improvise.
Do not invent a flag that `--help` does not show, and do not pass `--no-journal` (this phase wants
the five observations).

Then prove the tree is green before putting anything in the database:

```bash
docker start seer-pg || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd "$WT" && /home/miftah/seer/engine/.venv/bin/ruff check engine
cd "$WT" && PYTHONPATH=$WT/engine/src $PY -m pytest engine/tests -n auto 2>&1 | tail -20
```

**A `lab` subcommand migrates `lab/lab.sqlite` on connect, so even a read can dirty it.** Before
going on, restore it, so Step 1's blob check and Step 2's baseline are both taken against the
committed copy rather than a file this phase has already touched:

```bash
cd "$WT" && git status --short lab/lab.sqlite && git checkout -- lab/lab.sqlite
```

**Impact:** Nothing yet. If `exposure.py` is missing, or `--help` fails, or the suite is red,
**stop here and report**. Everything downstream writes to an append-only database.

---

### Step 1: Confirm `lab/lab.sqlite` has not moved on `origin/main`

**File:** none — this is a gate
**Change:** another session's journal rows must not be clobbered by this branch's copy.

```bash
cd "$WT"
git fetch origin                     # fetch only. NEVER `git pull --rebase --autostash` here:
                                     # it rewrites lab.sqlite under an open connection.
git rev-parse origin/main:lab/lab.sqlite
```

**Expected:** `3d2f4301191b6c3229c92b0df849e15ae31c5097` — the blob at base commit `85f65bd`.

If it prints anything else, `origin/main` has a newer lab database than this branch's copy.
**STOP and report.** Do not merge, do not rebase, do not write. Committing this branch's older
`lab/lab.sqlite` would silently delete whatever rows the other session journaled. The recovery is
a `git merge --ff-only` **before** any write, by a session that owns the decision — not this one,
mid-plan.

**Impact:** Nothing. This is the only cheap moment to catch a clobber.

---

### Step 2: Snapshot the database BEFORE, read-only

**File:** none — writes `$RUNDIR/before.txt`
**Change:** an independent record of the report-only invariant, taken without migrating the file.

`lab exposure` prints its own before/after line for N and the look budget. That line is the
command's claim about itself. This step is the **independent** check, and it is taken with
`mode=ro` so the act of checking does not itself dirty `lab/lab.sqlite` (any `lab` subcommand
migrates on connect; `sqlite3` with `mode=ro` does not).

```bash
cd "$WT"
sqlite3 "file:lab/lab.sqlite?mode=ro" <<'SQL' | tee "$RUNDIR/before.txt"
.mode list
.headers off
SELECT 'trials',           count(*) FROM trials;
SELECT 'dev_trials_N',     count(*) FROM trials WHERE window = 'dev';
SELECT 'test_looks',       count(*) FROM trials WHERE window = 'test';
SELECT 'trial_moments',    count(*) FROM trial_moments;
SELECT 'trial_funding',    count(*) FROM trial_funding;
SELECT 'trial_provenance', count(*) FROM trial_provenance;
SELECT 'insights',         count(*) FROM insights;
SELECT 'methods_total',    count(*) FROM methods;
SELECT 'methods:' || status, count(*) FROM methods GROUP BY status ORDER BY status;
SQL
```

**Expected output, exactly:**

```
trials|358
dev_trials_N|354
test_looks|4
trial_moments|244
trial_funding|230
trial_provenance|358
insights|184
methods_total|130
methods:blocked-data|2
methods:dev-eligible|15
methods:idea|50
methods:rejected|59
methods:test-failed|4
```

If any line differs from the Baseline table, the working copy is not at the base state. **STOP and
report** — reconcile before writing.

**Impact:** None. `$RUNDIR/before.txt` is the evidence Step 4 diffs against.

---

### Step 3: Run the diagnostic over the five

**File:** `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` (created here), plus the
transcript `$RUNDIR/exposure.txt`
**Change:** 23 recorded variants × 4 arms re-run on the dev store; 5 observations journaled by the
command; the committed grid CSV written in place.

```bash
cd "$WT"
$PY -m seer_engine lab exposure M0024 M0028 M0030 M0044 M0053 \
  --store "$STORE" \
  --csv "$WT/docs/backtests/2026-10-12-exposure-diagnostic-grid.csv" \
  2>&1 | tee "$RUNDIR/exposure.txt"
echo "exit=$?"
```

Notes on each piece:

- **The five ids, in this order.** They are the handover §2 live space: seasonality,
  short-term reversal, core-satellite, momentum-attention, overnight-intraday. No sixth id.
- **`--store "$STORE"`** points at the main checkout. The command refuses a store whose window is
  not `research.DEV_WINDOW`, so a test-window store cannot be passed by accident — but pass the
  dev store explicitly anyway, and never `engine/.research-test`.
- **No `--no-journal`.** The five observations are a deliverable.
- **`--csv` points straight into the repo**, not into `$RUNDIR`. `docs/backtests/` keeps a
  committed `-grid.csv` beside every write-up (`2026-10-08-how-many-names-grid.csv`), so this grid
  is a deliverable rather than working material; it is committed unchanged at Step 9.
- **No `--only`.** The variant selector (`--only IDS`, alias `--candidate`) narrows to named
  recorded variants. Leave it off: the write-up's grid wants every recorded dev variant of each of
  the five.
- **No `--db`.** The default resolves to `$WT/lab/lab.sqlite` through `PYTHONPATH`.

**Exit codes:** 0 ok · 2 the lab's rules refused the request · 1 an error.
A **2** is a finding, not an obstacle: record what was refused, do not route around it, and do not
touch `lab/hardgate.py` or any environment variable to get past it.

**Long run.** Expect roughly 10 s to load the store plus 92 runs at 1.8–5.4 s — on the order of
five to eight minutes. Run it in the foreground with `tee`; do not background it, because the open
database connection must not outlive the step.

**If it crashes or an arm is obviously broken:** stop, keep `$RUNDIR/exposure.txt`, and report.
Per the hard stop rule, phase 2 does not fix phase 1's module.

**Impact:** `lab/lab.sqlite` now has 5 more `insights` rows (184 → 189) and is dirty in git (it
migrated on connect). Nothing else in it moved.
`docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` exists and is untracked.

---

### Step 4: Verify the report-only invariant independently

**File:** none — writes `$RUNDIR/after.txt`
**Change:** prove, without trusting the command's own claim, that nothing but `insights` moved.

```bash
cd "$WT"
sqlite3 "file:lab/lab.sqlite?mode=ro" <<'SQL' | tee "$RUNDIR/after.txt"
.mode list
.headers off
SELECT 'trials',           count(*) FROM trials;
SELECT 'dev_trials_N',     count(*) FROM trials WHERE window = 'dev';
SELECT 'test_looks',       count(*) FROM trials WHERE window = 'test';
SELECT 'trial_moments',    count(*) FROM trial_moments;
SELECT 'trial_funding',    count(*) FROM trial_funding;
SELECT 'trial_provenance', count(*) FROM trial_provenance;
SELECT 'insights',         count(*) FROM insights;
SELECT 'methods_total',    count(*) FROM methods;
SELECT 'methods:' || status, count(*) FROM methods GROUP BY status ORDER BY status;
SQL

diff "$RUNDIR/before.txt" "$RUNDIR/after.txt"
```

**The only acceptable diff is the `insights` line, 184 → 189.** Everything else must be byte
identical — in particular `dev_trials_N|354` and `test_looks|4`, which are the §3 constraint, and
the whole `methods:` block, which proves no status moved.

Then check nothing crept in outside the tables that are counted:

```bash
cd "$WT"
sqlite3 "file:lab/lab.sqlite?mode=ro" \
  "SELECT id, kind, method_id, substr(title,1,70) FROM insights ORDER BY id DESC LIMIT 6;"
git status --short docs/lab/ 2>/dev/null   # must print nothing: no pre-registration file
```

Expect five rows of kind `observation`, one each for M0024, M0028, M0030, M0044, M0053, and the
sixth row being insight 184 (the pre-existing one). Record the five new ids — they go in the
todos entry.

**If `dev_trials_N` or `test_looks` moved, or any trial-side table grew:** the report-only
invariant is broken. **STOP and report immediately.** Do not `lab stage`, do not commit. The
database is append-only by trigger, so the rows cannot be removed — the correct recovery is to
leave `lab/lab.sqlite` uncommitted (`git checkout -- lab/lab.sqlite` restores the committed copy,
which is safe here only because nothing else has written to this branch's copy) and hand the
finding back.

**Impact:** The invariant is now evidenced by two independent sources: the command's own line in
`$RUNDIR/exposure.txt` and this diff.

---

### Step 5: Read the answer

**File:** none — reading
**Change:** turn the terminal output and the CSV into the one paragraph the handover asked for.

```bash
cd "$WT"
less "$RUNDIR/exposure.txt"
column -s, -t docs/backtests/2026-10-12-exposure-diagnostic-grid.csv | less -S
head -1 docs/backtests/2026-10-12-exposure-diagnostic-grid.csv   # the exact column names
```

What to pull out, per method, for the **headline variant** (the best recorded *eligible* variant
by MAR; where none is eligible — M0024 and M0030 — the best by MAR, which is
`M0024-SAME-N20-BLEND-RM` at 0.697 and `M0030-C50T` at 0.682):

1. **The share of the book that was ever in its own picks** — the `-PICKS` arm's own exposure.
   This is the headline number of the whole exercise, the generalisation of M0107's
   "HOST 70.4% invested, NONE 41.9%".
2. **The share of decision sessions on which the inner allocator returned nothing** — the part
   that *cannot* be undone. A whole-book gate that returns no targets empties the book, and no
   re-weighting wrapper can invent the basket a gated-off allocator would have produced. For
   M0024, whose trend gate is worth about 25 points of exposure (`SAME-N20` 0.652 against
   `SAME-N20-NOTREND` 0.898), this number is the honest half of the answer and must be reported,
   not glossed.
3. **The `-FULL` arm's lead over SPY, per era** — 1996–2002, 2003–2008, 2008 alone, 2009–2015,
   plus the whole window. This is the fair selection test: the picks, at full size, brakes off,
   against deposit-matched SPY.
4. **The `-PARK` arm's lead, per era**, where the park set is non-empty. Where it is empty the
   report says so in a sentence; do not invent a column.
5. **The mean number of names held** in the `-FULL` arm, which is the honest caveat on an
   uncapped rescale.

Then decide the verdict. The three honest shapes, and all three are publishable:

- **"All four are mostly parked market money."** The four non-core methods' `-FULL` arms trail
  deposit-matched SPY in every era, or hold so little of their own picks that the whole-book number
  is market beta. Then the lab's live space is empty and the handover's §2 worst case is confirmed.
- **"Three of four hold up."** The `-FULL` arms lead SPY in most eras on a book that was mostly in
  its own picks. Then the hole was specific to the dividend family.
- **Mixed, and reported as mixed.** Most likely. Say which method is which, era by era, and do not
  average a positive and a negative into a shrug.

Two readings that are forbidden:

- **Never compare an arm to the recorded trial row.** Measured 2026-10-12: `M0030-C50T` re-runs to
  `9.583603` against a recorded `9.583723`, and its SPY TR to `3.466805` against a recorded
  `3.514206`; the store fingerprint moved today (`399d0d25` → `77c37d55`). The reproduction check
  the command prints is information. Every conclusion compares **arm against arm**, inside one run.
- **Never compare absolute returns across methods.** M0024 and M0030 ran lump-sum (no
  `trial_funding` row); M0028, M0044 and M0053 ran funded on `OWNER_MONTHLY`. Only the **lead over
  SPY in points a year** is comparable across the five.

The context to read the answer against (from the handover, for the one family already closed):
M0107's parked-SPY control showed its picks behind 4.4 points a year in 1996–2002, ahead about
1 point in 2003–2008, behind 5.7 points from 2009, with the timed SPY holding worth about 9 points
a year early on and the switch on top of it about 0.4. That is what "no picking edge at all" looks
like in this grid.

**Impact:** None to the repo. This is the step the rest of the phase depends on being done
honestly.

---

### Step 6: Write `docs/backtests/2026-10-12-exposure-diagnostic.md`

**File:** `docs/backtests/2026-10-12-exposure-diagnostic.md` (new)
**Change:** the write-up and the full grid. The committed grid CSV is already in place from Step 3.

**Language rule (plan invariant 11, as narrowed in reconciliation).** `docs/backtests/` is a
**developer-facing record**, not a page the owner reads on the site. CLAUDE.md's rule binds "text
the owner reads (site summaries, Sera pages)", and the existing files in this directory already
name methods by id (`2026-10-08-how-many-names.md`). So:

- **The short-answer paragraph at the top is plain English** and must stand on its own without a
  single id, suffix, digest or backticked identifier. That paragraph is what the owner reads, and
  it is what answers the handover's §2 question.
- **The body, the per-book sections and the grid tables may name method and variant ids** beside
  the plain-words label, exactly as the rest of this directory does. The committed grid CSV names
  ids by construction, and that is correct.
- **The journal — the five observations and the synthesis — and anything bound for Sera stay
  strictly plain words with no ids.** That is where the rule actually binds, and the command
  already writes the observations that way.

Use these labels throughout, and keep them consistent between the write-up and the journal entries
(in the write-up an id may follow the label; in the journal it may not):

| Method | Call it |
|---|---|
| M0024 | the seasonality book — buys what did best in this calendar month last year |
| M0028 | the bounce book — buys last month's biggest fallers among calm, uptrending stocks |
| M0030 | the market-core book — holds the market itself and adds a momentum sleeve on top |
| M0044 | the quiet-blend book — the low-turnover blend under a volatility brake |
| M0053 | the overnight book — momentum winners whose gain came overnight, under a weekly brake |

And these for the four arms:

| Arm | Call it |
|---|---|
| recorded | **as recorded** — the book exactly as the lab holds it |
| `-PICKS` | **its own picks only** — the parked market holding removed, the picks left at the size the method gave them, the rest sitting in cash |
| `-FULL` | **its own picks at full size** — the same picks filling the whole book, brakes off |
| `-PARK` | **the parked money only** — just the market holding, filling the book |

The skeleton, to be filled from Step 5 (every `<…>` is a number or a sentence you read, never a
guess):

````markdown
# What the five live books actually picked

**Measured:** 2026-10-12 · **Window:** 1996-01-03 → 2015-10-16 (the lab's development window)
**Research store:** <the fingerprint the run printed>

## The short answer

<ONE paragraph. It must answer, in plain words: of the four books that are not the market-core
one, do any have a picking edge once the money parked in the market and the volatility brakes are
taken away — or is the lab's live space empty? Say which, name each book by its label above, and
give the lead over the market in points a year for the eras that carry the verdict. If the answer
is mixed, say mixed and say which book is which. If it is "all four are mostly parked market
money", say exactly that — it is as publishable as the good answer, and it is the finding the
handover asked for.>

## Why this was measured

Every number the lab records about a book is a number about the whole book: what it returned, how
far it fell, how much of the time it was invested. None of them separates the two different things
a book is made of — the names it **picked**, and the money it **parked** in the market or left as
cash. A book whose picks have no edge can still post a good whole-book number when most of its
money is market beta, and until now the lab could not see the difference.

That is exactly what happened to the dividend family: thirty-five variations over three batches,
and when a control arm finally stripped the parked market holding out, the picks lost to the
market in every era — behind 4.4 points a year through 2002, ahead about a point to 2008, behind
5.7 points from 2009. The family is closed. This measurement asks the same question of everything
still alive.

## How it was measured

Each book was re-run four ways, on the same window, at the same starting money and the same
monthly top-up it was originally recorded with. Only one thing changed between the four: what the
book was allowed to hold.

- **As recorded** — the book exactly as the lab holds it. The reference.
- **Its own picks only** — the parked market holding dropped, the picks kept at the size the book
  gave them, the rest left in cash. This is the share of the money that was ever in the book's own
  names.
- **Its own picks at full size** — the same picks, rescaled to fill the whole book, with the
  brakes off. This is the fair test of the picking itself.
- **The parked money only** — just the market holding, filling the book. What the spare money
  earned on its own.

The market comparison receives the same deposits on the same days, so "ahead" and "behind" below
compare two accounts holding the same money. The eras are the same split that exposed the problem
in the dividend family: 1996–2002, 2003–2008, 2008 on its own, and 2009 to the end of the
development window.

## What it could not see

<A short section, always present.> A safety rule that works by holding **nothing at all** cannot
be undone by this measurement. When a book's rule says "not today", it hands back no names, and no
amount of re-weighting can invent the basket it would have bought if the rule had been off. So
instead of faking that, the measurement reports **how often each book held nothing** — and that
number is in the grid below. For the seasonality book this matters most: its market-trend rule is
worth about twenty-five points of how-invested-it-was, so a large part of its cash is the rule
firing, not unfilled slots.

<One sentence on the reproduction check: the re-runs no longer land exactly on the recorded rows
because the price store changed today, so every comparison here is between the four arms of one
run, never against a number the lab recorded earlier.>

## Book by book

### <the seasonality book>

<Two to four sentences: how much of its money was in its own picks; how often it held nothing;
what its picks at full size did against the market, era by era; and whether the parked money or
the picks carried the whole-book number.>

| | as recorded | its own picks only | its own picks at full size | the parked money only |
|---|---:|---:|---:|---:|
| share of money in its own names | | | | |
| share of days it held nothing | | | | |
| names held, on average | | | | |
| return a year, whole window | | | | |
| the market, same money | | | | |
| worst fall | | | | |

Lead over the market, in points a year:

| | whole window | 1996–2002 | 2003–2008 | 2008 | 2009–2015 |
|---|---:|---:|---:|---:|---:|
| as recorded | | | | | |
| its own picks only | | | | | |
| its own picks at full size | | | | | |
| the parked money only | | | | | |

### <the bounce book>

<same two tables>

### <the market-core book>

<same two tables, plus a sentence saying that this book holds the market on purpose, so a large
parked share is the design and not the finding; the finding here is what the momentum sleeve did
on its own.>

### <the quiet-blend book>

<same two tables, plus a sentence saying this book parks nothing, so "its own picks at full size"
is simply the same picks with the volatility brake switched off.>

### <the overnight book>

<same two tables, same brake sentence.>

## Every version tested

<One table, every variant of every book, one row per variant per arm. Give each variant a
plain-words gloss — "twenty names, ranked on the same month", "forty names", "the blend with the
momentum book" — with its lab id beside it, as the rest of this directory does. Columns: the share
of money in its own names, the share of days it held nothing, the return a year, the market on the
same money, the worst fall, and the lead in each of the four eras. Open the section with a line
linking the committed grid beside this file — `2026-10-12-exposure-diagnostic-grid.csv` — which
carries the same rows at full precision.>

## What this changes

<Two or three sentences. If the live space is empty, say what that means for the next batch — the
handover's §4.2 already decided that another exploration batch waits until this measurement is in,
with a slate informed by what survives. If something survives, say what the next measurement on it
should be.>
````

The machine-readable grid is already at `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv`
from Step 3 and is committed beside this write-up, matching `2026-10-08-how-many-names.md` and
`2026-10-08-how-many-names-grid.csv`. Do not move it to `$RUNDIR` and do not regenerate it by
hand: the markdown grid and the CSV must be the same run.

**Impact:** One new untracked markdown file; the CSV is already there from Step 3.

---

### Step 7: Journal the synthesis

**File:** `lab/lab.sqlite` (one `synthesis` row)
**Change:** the batch-level entry; the five per-method observations were already written by the
command in Step 3.

Write the body to a file first, so the plain-language rule is easy to check before it is appended
to an append-only table.

```bash
cat > "$RUNDIR/synthesis.md" <<'TEXT'
<Three to six short paragraphs, plain words, no ids, no digests, no code, no percentages of
precision the owner cannot use. Same book labels as the write-up. It must say:

  - what was asked: how much of each live book's money was ever in its own names, and what those
    names did against the market once the parked money and the brakes were removed;
  - what came back, book by book, in one clause each;
  - the verdict on the live space — empty, partly alive, or alive, and which books are which;
  - what the measurement could not see: a rule that holds nothing cannot be switched off, so the
    share of days each book held nothing is reported instead;
  - that nothing was recorded as a trial, so the luck hurdle did not move and no look at the
    held-out years was spent.>
TEXT

cd "$WT"
$PY -m seer_engine lab insight \
  --kind synthesis \
  --title "<a plain-words title, no ids — e.g. 'What the five live books actually picked'>" \
  --file "$RUNDIR/synthesis.md"
```

`lab insight` prints the new insight's number. Record it.

Rules it must satisfy:

- `--kind synthesis` is one of `INSIGHT_KINDS` (`lab/store.py:115`); it is the right kind for a
  batch-level reading. The five per-method entries are `observation` and already exist.
- **No `--method`.** This entry is about the batch, not one method. The per-method link is already
  carried by the five observations.
- Exactly one of `--body` or `--file` (`commands/lab.py:2276`); use `--file`.
- The insights table is append-only by trigger. **Read it once more before running this** — a
  wrong entry cannot be deleted, only corrected by a later entry.

**Impact:** `insights` goes 189 → 190.

---

### Step 8: Stage the database

**File:** `lab/lab.sqlite`, `web/data/lab.json`
**Change:** regenerate the web snapshot and git-add both, under the write lock.

```bash
cd "$WT"
$PY -m seer_engine lab stage
git status --short
```

`lab stage` writes `web/data/lab.json` from the staged database and `git add`s both files while
holding an exclusive lock, so the two can never disagree. **CI checks that they agree row for row,
and fails any commit that carries `lab/lab.sqlite` without `web/data/lab.json`.** This is the only
sanctioned way to commit the database — never `git add lab/lab.sqlite` by hand.

Sanity check that the snapshot really picked up the six new rows:

```bash
cd "$WT" && python3 -c "
import json;d=json.load(open('web/data/lab.json'));print('insights in snapshot:', len(d['insights']))"
```

Expect **190**.

**Impact:** Two files staged.

---

### Step 9: Commit, by explicit pathspec

**File:** the five files of the Files table
**Change:** one commit.

```bash
cd "$WT"
git add -- docs/backtests/2026-10-12-exposure-diagnostic.md \
           docs/backtests/2026-10-12-exposure-diagnostic-grid.csv \
           .workflows/todos.md
git diff --cached --name-only
```

**Expected, exactly five paths and no others:**

```
.workflows/todos.md
docs/backtests/2026-10-12-exposure-diagnostic-grid.csv
docs/backtests/2026-10-12-exposure-diagnostic.md
lab/lab.sqlite
web/data/lab.json
```

If `docs/plans/LAB_EXPOSURE_DIAGNOSTIC_PLAN.md`, `docs/analyzer/…`, `.workflows/plan/…` or
anything under `engine/` is in that list, unstage it (`git restore --staged -- <path>`) before
committing. **Never `git add -A` or `git add .`** — a `lab` subcommand dirties files as a side
effect of connecting, and the orchestration plan index lives on main and is ticked there, not here.

Then:

```bash
cd "$WT"
git commit -m "$(cat <<'MSG'
lab: the five live methods, measured on their own picks

Ran the new exposure diagnostic over the lab's whole live space — the five
kin-clean dev-eligible methods — re-running every recorded dev variant four
ways: as recorded, with the parked market holding dropped, with the surviving
picks rescaled to fill the book and the brakes off, and with only the parked
money. <One sentence giving the answer.>

Report only: no trial, no moments, no funding, no provenance, no status change.
Dev trials stayed at 354 and the test-window looks at 4, checked with a
read-only connection before and after as well as by the command's own line.
Five observations and one synthesis journaled.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

The message follows the repo's register (`lab: M00NN pre-registered — …`,
`lab: insight 184 — …`): lowercase `lab:` prefix, a plain-words subject, and a body that says what
was measured and what was found without ids in the prose.

Push only after the todos entry (Step 10) is in — or amend. Do **not** merge to main here unless
this phase is the plan set's last and no coordinator is tracking it; the swarm coordinator owns the
merge.

**Impact:** The journal rows are now permanent. The database is append-only by trigger — a wrong
reading is corrected by a **new** insight that says so, never by editing or deleting one.

---

### Step 10: Record the task

**File:** `.workflows/todos.md` — append under `## Completed Tasks`, and update the header
**Change:** one completed entry, in the file's existing shape.

Mint a TaskID first and check it is free:

```bash
cd "$WT" && grep -c 'P2-ROOT-' .workflows/todos.md && grep -n 'ROOT-EXP' .workflows/todos.md
```

Pick `P2-ROOT-<4 random uppercase alphanumerics>` that does not already appear in the file. Then
insert this block as the **first** entry under `## Completed Tasks` (line 36 region, directly above
the `P2-ROOT-FCG9` entry), filling every `<…>`:

```markdown
- [x] **P2-ROOT-<ID>** Phase 2: Run the exposure diagnostic over the five, and journal the answer
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Context**: Owns `lab/lab.sqlite` (five `observation` rows written by `lab exposure` itself, one per method, plus one `synthesis` written by hand), `web/data/lab.json` (regenerated by `lab stage`), `docs/backtests/2026-10-12-exposure-diagnostic.md`, `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` and `.workflows/todos.md`. Touches no Python: phase 1 owns `engine/src/seer_engine/lab/exposure.py`, the additive edit to `engine/src/seer_engine/commands/lab.py` and `engine/tests/test_lab_exposure.py`. Ran `lab exposure M0024 M0028 M0030 M0044 M0053 --store /home/miftah/seer/engine/.research --csv docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` against the main checkout's research store — 23 recorded dev variants × 4 arms. Exit criteria: the report-only invariant verified independently of the command's own claim with a read-only `sqlite3` connection before and after (dev trials 354 → 354, test-window looks 4 → 4, `trial_moments` 244, `trial_funding` 230, `trial_provenance` 358, `methods` by status unchanged, `insights` 184 → 190 the only movement); five observations and one synthesis in plain words with no ids; `lab stage` run so the commit carries `lab/lab.sqlite` and `web/data/lab.json` together; the write-up answers the handover's §2 question in one paragraph.
  - **Status**: completed
  - **Plan Set**: `LAB_EXPOSURE_DIAGNOSTIC_PLAN.md` (phase 2 of 2)
  - **Satisfies**: R2 — Run the §4.1 exposure diagnostic over the five surviving kin-clean dev-eligible methods and journal the answer; R3 — Hold the §3/§6 constraints: report-only, N unmoved, no test-window look, `lab stage` for any database commit, no hard-gate override
  - **Depends on**: <phase 1's TaskID, or "phase 1 of this set">
  - **Plan**: `.workflows/plan/lab-exposure-diagnostic/phase-2.md`
  - **Completed**: 2026-10-12 <HH:MM>
  - **Method**: /implement
  - **Files**: `lab/lab.sqlite`, `web/data/lab.json`, `docs/backtests/2026-10-12-exposure-diagnostic.md`, `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv`, `.workflows/todos.md`
  - **Result**: <one sentence: the answer the grid gave — is the lab's live space empty, partly alive, or alive, and which books are which.>
  - **Journal**: observations <five ids>, synthesis <id>
  - **Drift**:
    - <any difference between the flags this plan named and what `lab exposure --help` actually showed, per Step 0>
  - **Decided**:
    - <anything the plan left to judgement, and how it went — e.g. which variant was taken as each method's headline where none is eligible>
  - **Commit**: `<sha>`
```

Then update the header block at the top of the file:

- `**Last Updated**: 2026-10-12 <HH:MM>`
- `- Completed: 18` → `- Completed: 19`

`**Total Active Tasks**: 0` and the P0–P4 counters stay at 0: this task is completed, not active.

**Impact:** The repo's task record matches reality. Amend the Step 9 commit
(`git commit --amend --no-edit` after `git add -- .workflows/todos.md`) if the commit was already
made, then push.

---

## Verification

**Build:** `cd "$WT" && /home/miftah/seer/engine/.venv/bin/ruff check engine`
— must be clean. This phase changes no Python, so it is clean if phase 1 was; run it anyway,
because the commit is the one that lands.

**Tests:**
```bash
docker start seer-pg
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd "$WT" && PYTHONPATH=$WT/engine/src /home/miftah/seer/engine/.venv/bin/python \
  -m pytest engine/tests -n auto
```
Green, with **no DB test skipping** (CI fails if they skip). Note that
`engine/tests/test_lab_snapshot.py` reads the committed database and the committed
`web/data/lab.json`; it is the test that catches a `lab stage` that was skipped or that staged the
wrong snapshot, so a failure there means Step 8 did not happen properly.

**Manual check:**
1. `diff "$RUNDIR/before.txt" "$RUNDIR/after.txt"` differs on the `insights` line only.
2. `git show --stat HEAD` lists exactly five files.
3. The write-up's **short answer** paragraph is plain English — no ids, no digests, no backticked
   identifiers. Check that section alone, not the whole file: under the narrowed invariant 11 the
   body and the grid may name ids, as the rest of `docs/backtests/` does.
   ```bash
   sed -n '/^## The short answer$/,/^## Why this was measured$/p' \
     docs/backtests/2026-10-12-exposure-diagnostic.md | grep -nE 'M0[0-9]{3}|[0-9a-f]{8}|`'
   ```
   Must print nothing.
4. The journal is where the plain-language rule binds without exception — the synthesis body and
   the five observations the command wrote. Both greps must print nothing:
   ```bash
   grep -nE "M0[0-9]{3}|[0-9a-f]{8}" "$RUNDIR/synthesis.md"
   sqlite3 "file:lab/lab.sqlite?mode=ro" \
     "SELECT title || ' ' || body FROM insights ORDER BY id DESC LIMIT 6;" \
     | grep -nE "M0[0-9]{3}|[0-9a-f]{8}"
   ```
5. `sqlite3 "file:lab/lab.sqlite?mode=ro" "SELECT count(*) FROM trials WHERE window='test';"` → 4.
6. The committed grid is the run's own CSV, not a hand copy:
   `head -1 docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` is the command's `CSV_HEADER`
   and `wc -l` is 1 + one row per (variant, arm) measured.

**Exit criteria:**
- `lab exposure M0024 M0028 M0030 M0044 M0053 --store /home/miftah/seer/engine/.research
  --csv docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` ran to completion against the main
  checkout's research store, exit 0, and that CSV is committed.
- Dev trials 354 before and after; test-window looks 4 before and after; `trial_moments`,
  `trial_funding`, `trial_provenance` and the `methods` status counts unchanged — verified by a
  read-only `sqlite3` diff, not only by the command's own printed line.
- Five `observation` rows (one per method) and one `synthesis` row are in `insights`, in plain
  words naming no ids.
- `docs/backtests/2026-10-12-exposure-diagnostic.md` exists, carries the full method × variant ×
  arm × era grid, links its committed companion
  `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv`, and answers the handover's §2 question
  — do the four non-core books have a picking edge, or is the lab's live space empty — in one
  plain-English paragraph at the top (no ids, no digests there), honestly, including a mixed
  answer reported as mixed, and states what the diagnostic could not see.
- One commit holds exactly `lab/lab.sqlite`, `web/data/lab.json`,
  `docs/backtests/2026-10-12-exposure-diagnostic.md`,
  `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` and `.workflows/todos.md`.
- `ruff check engine` clean and `pytest engine/tests` green with Postgres up.

---

## Handoffs

- **A backfill across all 130 methods.** Decision D4 scoped this run to the named five. The
  command takes ids, so a full backfill is one command away and costs nothing in N. Worth doing
  once the five have been read, especially over the closed families, to check the diagnostic says
  about the dividend family what the hand-built control arm said.
- **Any bug found in `lab exposure`.** Report it; do not fix it here. A fix is a follow-up commit
  on top of phase 1.
- **What the answer implies for the next batch.** Handover §4.2 decided another exploration batch
  waits until this measurement is in, with a slate informed by what survives. Choosing that slate
  is not this phase's work; the write-up's closing section says what it should be informed by.
- **The idle-cash interest rule (§5.1), the store-rebuild guard (§5.2), EODHD (§5.3), the queued
  lab ideas M0110–M0116 (§5.5) and the data jobs (§5.6)** are all out of scope and named in the
  handover as later.

---

## Rollback

- **The journal rows cannot be undone.** `insights` is append-only by trigger, by design. A wrong
  reading is corrected the way the lab corrects every reading: a **new** insight that says so, and
  a note on the method. Never edit or delete a row.
- **Before the Step 9 commit**, everything is reversible:
  `git checkout -- lab/lab.sqlite web/data/lab.json` restores the committed copies (safe here only
  because nothing else wrote to this branch's copy — check `git status` first), and
  `rm docs/backtests/2026-10-12-exposure-diagnostic.md
  docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` plus
  `git checkout -- .workflows/todos.md` removes the prose and the grid.
- **After the commit**, `git revert <sha>` undoes the write-up, the todos entry, and restores the
  previous `lab/lab.sqlite` and `web/data/lab.json` blobs together — which is a legitimate revert
  only because this branch is the only writer. If `origin/main` has moved on the database in the
  meantime (Step 1's check), revert only
  `docs/backtests/2026-10-12-exposure-diagnostic.md`,
  `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` and `.workflows/todos.md`, and leave the
  database alone.
- **`$RUNDIR`** holds the full transcript and the before/after snapshots (the CSV now lives in the
  repo). Keep it until
  the commit is pushed; it is the only copy of the raw evidence.
