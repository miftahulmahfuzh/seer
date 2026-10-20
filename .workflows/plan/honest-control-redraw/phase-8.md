# Phase 8: Close-out — which verdicts survived their honest control

**Plan set:** `HONEST_CONTROL_REDRAW_PLAN.md`
**Analysis:** `docs/analyzer/20261019-181712-C4K9_code_analyzer.md`
**Satisfies:** R3 (report which of the nine standing verdicts survive their honest control, in
`trial_funding.mwr`, including margins that worsen or reverse) and R4 (`lab promote` must actually
stop refusing the nine — this phase is the *proof*, phase 2 is the *change*)
**Depends on:** Phases 1, 2, 3, 4, 5, 6, 7 — all of them
**Difficulty:** NORMAL
**Package:** repo (`docs/plans/`, `lab/`, `web/data/`, git)

---

## Goal

After this phase the branch is on `main`, `lab/lab.sqlite` and `web/data/lab.json` are committed
and agree row for row, and there is one document —
`docs/plans/HANDOVER_20261019-the-honest-control.md` — that states, for each of the nine blocked
methods, the margin before and the margin after an honestly-shaped control, in
`trial_funding.mwr` against SPY TR 7.19%/yr on the same deposits, with one sentence per method
saying whether the standing verdict survived. Four `lab insight` rows journal the two family
findings, the D17 supersession, and the measured fact that the matched-draw rule beat M0241's
1.372x. The lab's test-window look count is still 4 and no method id was spent.

This phase runs **no** `lab run`, **no** `lab promote`, **no** `lab test`, and edits **no** source
file. It measures what already landed, writes it down, and lands the set.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `docs/plans/HANDOVER_20261019-the-honest-control.md` (new file, this phase only)
- four `insights` rows (ids 471..474 if nothing else writes the journal first — the ids are
  measured, not assumed)
- one merge commit on `main` (`merge(honest-control-redraw): 8 phases -- honest-control-redraw`)
- one lab commit on `main` carrying `lab/lab.sqlite` + `web/data/lab.json` + the handover
- optionally one `chore(orch)` commit pruning the set, matching the gate-reading-cadence
  precedent (`465fcfd`)

**Signature changes:** none.

**Requires (from earlier phases):**
- Phase 1: `engine/src/seer_engine/lab/control_draw.py` exists and is committed; the measured
  trade/turnover ratios of the matched-draw rule on both poles (M0227 0.07x pole, M0243 3.01x
  pole) are recorded in phase 1's plan file or its capture directory, including the comparison
  against M0241's 1.372x / 1.131x. **Phase 8 reads those numbers; it does not re-derive them from
  a backtest.** If phase 1 left no written ratio, phase 8 re-derives both ratios read-only from
  `trials` (`sqlite3 … mode=ro`) and says so in the handover's attribution line.
- Phase 2: `control_shape.refusals()` excludes a superseded finding and `lab control` prints the
  superseded arm with the id of the arm that superseded it — **and, where the two differ, the
  superseding arm's own resolved target beside it** (`<new-id> -> <its target>`), because the
  `<target-id>-PLC` convention deliberately re-points a replacement. **Phase 8 must read
  `.workflows/plan/honest-control-redraw/phase-2.md` for the exact literal phase 2 chose** (the
  reconciled index says "`superseded by <id>`") and grep for that literal, never for a guessed
  one.
- Phase 2's rule is an **explicit declaration**, not a target match: a refused or warned arm is
  retired only by a band-clean placebo that NAMES it in `Candidate.supersedes`. So a missing
  supersession in Step 3a's sweep has two possible causes and Phase 8 must say which: the new arm
  missed the match band, or the new arm's declaration is wrong or absent. The index's
  **supersession mapping** is the fourteen-row ground truth to check the declarations against.
- Phase 1: `backtest.dev.Candidate.supersedes` exists as a defaulted, validated field.
- Phases 1, 3, 4, 5, 6, 7: each wrote
  `.workflows/plan/honest-control-redraw/phase-N-results.md` and committed it. **That is the
  set's one results-file convention and the only place Phase 8 collects a phase's numbers
  from.** Phase 1's doubles as the GO/STOP gate the fan-out read. Phase 2 writes none: it
  measures nothing and records no trial.
- Phase 2: `hardgate.mis_shaped_controls` no longer returns a superseded finding, so
  `hardgate.check` no longer raises on D17 for a method that holds a band-clean control for the
  same target.
- Phases 1, 3, 4, 5, 6, 7: fourteen `-PLC` trials recorded on the dev window under nine
  `method_amendments` rows, and each method file's `Amendment` block committed on
  `feature/honest-control-redraw` **before** its run.
- Every phase: `pytest engine/tests` and `ruff check engine` green on the branch at the moment
  that phase finished.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/control_draw.py` (Phase 1)
- `engine/src/seer_engine/lab/control_shape.py`, `hardgate.py`,
  `engine/src/seer_engine/commands/lab.py` (Phase 2)
- every `engine/src/seer_engine/lab/methods/m0*.py` (Phases 1, 3, 4, 5, 6, 7)
- every `engine/tests/test_lab_*.py` (Phases 1, 2)

---

## Files

| File | Action | What changes |
|---|---|---|
| `docs/plans/HANDOVER_20261019-the-honest-control.md` | create | the whole close-out document; skeleton in Step 5 below |
| `lab/lab.sqlite` (at `/home/miftah/seer`) | commit | the fourteen trials, nine amendment rows and four insights that phases 1,3–7 and this phase wrote; written only by `lab` commands, never edited |
| `web/data/lab.json` (at `/home/miftah/seer`) | regenerate + commit | `lab stage` rewrites it from the whole database so CI's row-for-row check passes |
| `docs/plans/HONEST_CONTROL_REDRAW_PLAN.md` | modify | **Status:** `planned` → `landed`, and the Reconciliation Log's close-out line; header edit only, no phase text is rewritten |

No source file is touched. If this phase finds itself editing anything under
`engine/src/`, it has gone out of scope and must stop.

---

## Implementation Steps

### Step 0: The environment, set once, used by every command below

**File:** none — this is the shell preamble every later step assumes.
**Change:** every command in this phase runs with these exact values. The worktree has no venv and
no research store; the main checkout owns both, and it owns the lab database.

**Code:**

```bash
# --- paths -----------------------------------------------------------------
MAIN=/home/miftah/seer
WT=/home/miftah/.worktrees/seer/honest-control-redraw
PY=/home/miftah/seer/engine/.venv/bin/python
CAP=/tmp/honest-control
KEEP=/home/miftah/.cache/seer-captures-honest-control

# --- lab environment -------------------------------------------------------
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
unset SEER_RESEARCH_TEST_STORE          # invariant 6: the test store is never read

mkdir -p "$CAP" "$KEEP"

# --- the read-only hash, recorded before and after EVERY `lab` command ------
labhash() { git -C "$MAIN" hash-object lab/lab.sqlite; }
```

Two rules that hold for every command in this phase, from the lab's own scars:

1. **Never judge a `lab` command by a piped exit code.** Redirect to a capture file and echo `$?`
   on its own line. A `grep` or `head` in the pipeline owns the status
   (memory `seer-lab-note-double-append-from-grep-exit-code`). Every capture below is written as
   `… > "$CAP/NN-name.txt" 2>&1; echo "exit=$?" >> "$CAP/NN-name.txt"`.
2. **Any `lab` command migrates `lab.sqlite` on connect, even a pure read.** Hash before, hash
   after, and if a read-only command moved the hash while writing nothing, that is the migration
   and it is expected — record both hashes in the capture rather than restoring, because by this
   phase the database is being committed anyway. A `sqlite3 "file:…?mode=ro"` query never
   migrates and is the right tool for every count in this phase.

**Impact:** nothing is written yet. Everything after this inherits these variables.

---

### Step 1: Prove the set is complete — or detect that it is not

**File:** `/home/miftah/seer/lab/lab.sqlite` (read-only), `$WT/.workflows/plan/honest-control-redraw/*.md`
**Change:** before merging anything, establish from the *database* (not from a plan file's claim)
which of the fourteen honest controls actually exist. This is also the partial-set detector; see
Step 9.

**Code:**

```bash
labhash | tee "$CAP/00-hash-before.txt"
# expected at the base commit, before any phase ran:
#   3969f1fa5d2066a42ed47716dd05a66050073592

sqlite3 "file:$SEER_LAB_DB?mode=ro" <<'SQL' > "$CAP/01-counts.tsv" 2>&1
.mode tabs
.headers on
SELECT 'dev_trials'   AS what, count(*) AS n FROM trials WHERE window = 'dev'
UNION ALL SELECT 'test_window_looks', count(*) FROM trials WHERE window = 'test'
UNION ALL SELECT 'methods',           count(*) FROM methods
UNION ALL SELECT 'amendments',        count(*) FROM method_amendments
UNION ALL SELECT 'insights',          count(*) FROM insights
UNION ALL SELECT 'max_insight_id',    max(id)  FROM insights;
SQL

sqlite3 "file:$SEER_LAB_DB?mode=ro" <<'SQL' > "$CAP/02-plc-arms.tsv" 2>&1
.mode tabs
.headers on
SELECT t.method_id, t.candidate_id, t.n, t.trades,
       round(t.turnover, 4)        AS turnover,
       round(f.mwr * 100, 4)       AS mwr_pct,
       round(f.spy_tr_mwr * 100, 4) AS spy_tr_pct
FROM trials t LEFT JOIN trial_funding f ON f.trial_n = t.n
WHERE t.window = 'dev'
  AND t.method_id IN ('M0047','M0201','M0202','M0208','M0215','M0221','M0225','M0227','M0243')
ORDER BY t.method_id, t.n;
SQL

sqlite3 "file:$SEER_LAB_DB?mode=ro" <<'SQL' > "$CAP/03-amendments.tsv" 2>&1
.mode tabs
.headers on
SELECT method_id, seq, added, run_at, substr(source_sha, 1, 12) AS sha12,
       substr(replace(why, char(10), ' '), 1, 90) AS why90
FROM method_amendments ORDER BY method_id, seq;
SQL
```

**The completeness check, stated as the exact set of fourteen candidate ids that must appear in
`02-plc-arms.tsv`:**

| phase | method | new control arm(s) | the book each controls |
|---|---|---|---|
| 1 | M0227 | `M0227-S20-PLC` | `M0227-S20` |
| 1 | M0243 | `M0243-NEAR20-PLC` | `M0243-NEAR20` |
| 3 | M0221 | `M0221-C50-PLC` | `M0221-C50` |
| 3 | M0225 | `M0225-C50-PLC` | `M0225-C50` |
| 4 | M0047 | `M0047-MV10-PLC`, `M0047-MV20-PLC` | `M0047-MV10`, `M0047-MV20` |
| 5 | M0201 | `M0201-Y20-MV10-PLC1`, `M0201-Y20-MV10-PLC2` | `M0201-Y20-MV10` |
| 5 | M0202 | `M0202-Y20-HALF-PLC1`, `M0202-Y20-HALF-PLC2`, `M0202-Y20-HALF-FAST-PLC1` | `M0202-Y20-HALF` (×2), `M0202-Y20-HALF-FAST` |
| 6 | M0208 | `M0208-CGO-N20-PLC` | `M0208-CGO-N20` |
| 7 | M0215 | `M0215-CTRL-PLC`, `M0215-CAP4-PLC` | `M0215-CTRL`, `M0215-CAP4` |

```bash
cat > "$CAP/expected-plc.txt" <<'IDS'
M0047-MV10-PLC
M0047-MV20-PLC
M0201-Y20-MV10-PLC1
M0201-Y20-MV10-PLC2
M0202-Y20-HALF-FAST-PLC1
M0202-Y20-HALF-PLC1
M0202-Y20-HALF-PLC2
M0208-CGO-N20-PLC
M0215-CAP4-PLC
M0215-CTRL-PLC
M0221-C50-PLC
M0225-C50-PLC
M0227-S20-PLC
M0243-NEAR20-PLC
IDS

cut -f2 "$CAP/02-plc-arms.tsv" | grep -- '-PLC' | sort > "$CAP/actual-plc.txt"
diff "$CAP/expected-plc.txt" "$CAP/actual-plc.txt" > "$CAP/04-completeness.txt" 2>&1
echo "exit=$?" >> "$CAP/04-completeness.txt"
```

**Expected on a complete set:** `exit=0`, `01-counts.tsv` reads
`dev_trials 850` (836 + 14), `test_window_looks 4`, `methods 275` (unchanged — an amendment costs
no method id), `amendments 12` (3 + 9), `insights 470`.

**If the diff is non-empty**, the set is partial. Do **not** stop: go to Step 9, then come back and
run Steps 2 onward over whatever exists. The counts above become
`836 + (number of arms actually recorded)` and `3 + (number of amendment rows actually written)`,
and the handover says which books do and do not now hold an honest control.

**Also read, for attribution: the six results files, which are the set's one convention.**

```bash
for n in 1 3 4 5 6 7; do
  f="$WT/.workflows/plan/honest-control-redraw/phase-$n-results.md"
  echo "===== phase-$n-results.md ====="
  if [ -f "$f" ]; then cat "$f"; else echo "MISSING -- phase $n left no results file"; fi
done > "$CAP/05a-results-files.txt" 2>&1
cat "$CAP/05a-results-files.txt"
```

A missing results file is **not** evidence that the phase did not run, and the database is still
the authority: Step 1's `04-completeness.txt` is what decides which arms exist. A file that is
missing while its arms are recorded means the phase landed its measurement and skipped its
write-up, and Phase 8 re-derives those numbers read-only from `21-margins.tsv` and says so in
the attribution line. A file that is present while its arms are absent means the phase wrote up
a run that did not record — trust the database and say so.

**And, for attribution:** the phase plan files on the branch.

```bash
for n in 1 2 3 4 5 6 7; do
  echo "===== phase $n ====="
  sed -n '1,40p' "$WT/.workflows/plan/honest-control-redraw/phase-$n.md"
done > "$CAP/05-phase-headers.txt" 2>&1
grep -rn 'superseded' "$WT/.workflows/plan/honest-control-redraw/phase-2.md" \
  > "$CAP/06-supersede-literal.txt" 2>&1

# the fourteen declarations, read off the method files rather than off any plan's claim
PYTHONPATH=$WT/engine/src "$PY" - <<'PYEOF' > "$CAP/06b-declarations.txt" 2>&1
from seer_engine.lab import method
for mid in ("M0047","M0201","M0202","M0208","M0215","M0221","M0225","M0227","M0243"):
    m = method.load(mid) if hasattr(method, "load") else None
    mod = __import__(
        f"seer_engine.lab.methods", fromlist=["*"]
    )
    # fall back to the registry walk every lab command uses
for mid, c in sorted(
    (c.family, c) for mm in method.discover() for c in mm.all_candidates()
    if getattr(c, "supersedes", ())
):
    print(f"{c.id:28s} supersedes {', '.join(c.supersedes)}")
PYEOF
cat "$CAP/06b-declarations.txt"
```

`06b-declarations.txt` must list **fourteen** rows and they must match the index's supersession
mapping row for row. A declaration that is absent or misspelled is the one failure mode that
leaves a band-clean arm recorded and its method still blocked, and it is invisible in
`11-control.txt` except as a missing `superseded by`. (The exact `method.discover()` spelling is
whatever that module exposes; the point of the capture is the fourteen pairs, not the script.)

`06-supersede-literal.txt` is how this phase learns the exact string phase 2 prints. Grep for that
literal in Step 3, never for a remembered one.

**Impact:** nothing written. The database's hash is unchanged (`sqlite3 … mode=ro` does not
migrate) — confirm with a second `labhash` and record both in `00-hash-before.txt`.

---

### Step 2: Merge the branch into `main` — first, before `lab stage`

**File:** git, in `/home/miftah/seer`
**Change:** land every code change on `main` *before* the database that refers to it is committed.

**Why this order and no other.** `lab/lab.sqlite` on `main` will, after `lab stage`, carry fourteen
`trials` rows and nine `method_amendments` rows whose `source_sha` names a method file that exists
only on the branch. Committing the database first would put `main` in a state where the lab claims
to have run code `main` does not contain, and where
`test_lab_methods.py`'s sha freeze (and `runner.pending_amendment`'s field-by-field prefix check)
would fail on a fresh clone. Merging first removes that window entirely. The gate-reading-cadence
set landed in exactly this order (`6b77e5d` merge, then `ed684e0` the lab commit) and that is the
precedent being followed.

**Code:**

```bash
# 1. The main checkout must be on `main`, and its ONLY dirty paths may be the two the lab writes.
git -C "$MAIN" rev-parse --abbrev-ref HEAD          # must print: main
git -C "$MAIN" status --porcelain > "$CAP/07-main-status-before.txt" 2>&1
cat "$CAP/07-main-status-before.txt"
# Expected: exactly ` M lab/lab.sqlite` (phases 1,3-7 wrote it), and nothing else.
# `web/data/lab.json` is NOT expected to be dirty yet: only `lab stage` rewrites it.
# Anything else dirty belongs to another session -- STOP and ask before merging.

# 2. Make sure `main` is current, WITHOUT a rebase. A rebase replays a stale lab.sqlite over the
#    live shared file other sessions are writing (memory: seer-rebase-replays-stale-lab-sqlite).
git -C "$MAIN" fetch origin
git -C "$MAIN" rev-list --count HEAD..origin/main > "$CAP/08-behind.txt" 2>&1
cat "$CAP/08-behind.txt"
```

If `08-behind.txt` reads `0`, go straight to the merge. If it is non-zero, `main` moved under us;
integrate it into the **branch** with a merge (never a rebase), from the worktree, then come back:

```bash
# ONLY when 08-behind.txt is non-zero:
git -C "$WT" fetch origin
git -C "$WT" merge --no-edit origin/main            # a merge, never `pull --rebase`
git -C "$MAIN" merge --ff-only origin/main          # lab.sqlite is untracked by the branch, so
                                                    # a dirty lab.sqlite does not block this
```

Then the merge itself:

```bash
git -C "$MAIN" merge --no-ff feature/honest-control-redraw \
  -m "merge(honest-control-redraw): 8 phases -- honest-control-redraw

Fourteen control arms re-drawn at the shape of the book each controls, as
amendments under nine existing method ids -- no new method id, no extra N,
no test-window look. D17 now supersedes a handicapped control when the same
book holds a band-clean one, so the nine stop being refused on an arm that
has already been replaced.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  > "$CAP/09-merge.txt" 2>&1
echo "exit=$?" >> "$CAP/09-merge.txt"
cat "$CAP/09-merge.txt"
```

**Impact:** `main`'s working tree now holds `control_draw.py`, the phase-2 changes to
`control_shape.py` / `hardgate.py` / `commands/lab.py`, the nine amended method files, the new
tests, the phase plan files and the analysis document. `lab/lab.sqlite` is still dirty and
uncommitted; `web/data/lab.json` is still the pre-batch export. The tree is therefore
**expected to be red on exactly one test** right now
(`test_the_committed_snapshot_is_the_export_of_the_committed_database`), and Step 4 fixes that
before Step 5 asserts green. Do not run the full suite here.

---

### Step 3: The verification sweep, on `main`, after the merge

**File:** `/home/miftah/seer` (the merged checkout) — read-only against the lab
**Change:** nothing. This is the measurement the handover is written from.

Every command below runs from `$MAIN` with `PYTHONPATH=$MAIN/engine/src` — the merged checkout is
now the code under test, and PYTHONPATH must name it or pytest and the lab CLI silently use the
installed package instead (memory `seer-worktree-tests-need-pythonpath`).

#### 3a. `lab control` on the nine

```bash
labhash > "$CAP/10-hash-pre-control.txt"
PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab control \
  M0047 M0201 M0202 M0208 M0215 M0221 M0225 M0227 M0243 \
  > "$CAP/11-control.txt" 2>&1
echo "exit=$?" >> "$CAP/11-control.txt"
labhash > "$CAP/12-hash-post-control.txt"
cat "$CAP/11-control.txt"
```

**What must be true in `11-control.txt`:**

- `exit=0`.
- Each of the fourteen new `-PLC` arms is listed with verdict `ok` — meaning inside
  `WARN_BAND = (0.80, 1.25)` on **both** the trade-count ratio and the turnover ratio
  (`control_shape.py:240`). An arm that reads `warn` is inside `REFUSE_BAND` but outside the match
  band: that is a miss of R1's bar and goes in the handover as a miss, not as a success.
- Each of the fourteen **old** arms (`M0047-PLC1-MV10`, `M0047-PLC1-MV20`, `M0201-PLC1-MV10`,
  `M0201-PLC2-MV10`, `M0202-PLC1-HALF`, `M0202-PLC2-HALF`, `M0202-PLC1-HALF-FAST`,
  `M0208-HASH-N20`, `M0215-HASH`, `M0215-HASH-CAP4`, `M0221-R50`, `M0225-R50`, `M0227-R20`,
  `M0243-NEAR20-R`) is still **printed with its ratios** and carries phase 2's supersession
  marker. Grep for the literal `06-supersede-literal.txt` gave you:

```bash
LIT=$(grep -o 'superseded by[^`"]*' "$CAP/06-supersede-literal.txt" | head -1 | cut -c1-14)
grep -c "$LIT" "$CAP/11-control.txt" > "$CAP/13-superseded-count.txt" 2>&1
cat "$CAP/13-superseded-count.txt"   # expected: 14 on a complete set
```

- The report's closing block lists **no** refusal for any of the nine.
- The standing resolution of each new arm is `sibling-stem`, not `first-declared` — that is the
  whole reason the arms are named `<target-id>-PLC`, and it is what repairs the two
  mis-resolutions. Confirm the `rung` column says so for all fourteen.

#### 3b. The hard gate, RUN but never moved

Two read-only routes. Run both; they answer different questions.

**Route 1 — the lab-wide picture, `lab status`.** `_hard_gate_states`
(`commands/lab.py:1214-1270`) calls `hardgate.summary` and `hardgate.check` once per
`dev-eligible` method and prints the refusal sentence under
*"Refused by the hard gate"* (`_promotable_now`, `commands/lab.py:1329-1420`). It opens no research
store, runs no backtest, and writes no trial, funding, status or journal row — the docstring says
so in those words. It is the sanctioned way to exercise the gate without `lab promote`.

```bash
labhash > "$CAP/14-hash-pre-status.txt"
PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab status > "$CAP/15-status.txt" 2>&1
echo "exit=$?" >> "$CAP/15-status.txt"
labhash > "$CAP/16-hash-post-status.txt"
sed -n '/Promotable now/,/Latest insights/p' "$CAP/15-status.txt"
```

**Route 2 — the gate, per method, on a connection that cannot write.**
`store.connect_readonly` (`lab/store.py:666`) opens `mode=ro` with *no schema and no migration*,
and `hardgate.geometry` / `summary` / `check` only read. This route names the clause per method,
including a method `lab status` would omit because `store.best_dev_eligible` returned `None` for
it.

```bash
PYTHONPATH=$MAIN/engine/src "$PY" - <<'PYEOF' > "$CAP/17-gate-nine.txt" 2>&1
from pathlib import Path
from seer_engine.lab import hardgate, store

db = Path("/home/miftah/seer/lab/lab.sqlite")
conn = store.connect_readonly(db)          # mode=ro: no migration, no write, ever
try:
    try:
        geo = hardgate.geometry(conn)
    except store.LabError as e:
        geo = None
        print(f"geometry unavailable: {e}")
    for mid in ("M0047", "M0201", "M0202", "M0208", "M0215", "M0221", "M0225", "M0227", "M0243"):
        row = conn.execute("SELECT status FROM methods WHERE id = ?", (mid,)).fetchone()
        status = None if row is None else row["status"]
        summary = " ".join(str(hardgate.summary(conn, mid, geo)).split())
        off = hardgate.mis_shaped_controls(conn, mid)
        try:
            hardgate.check(conn, mid)
        except store.LabError as e:
            verdict = "REFUSED: " + " ".join(str(e).split())
        else:
            verdict = "TAKEN: the hard gate would promote this today"
        print(f"{mid}  status={status}")
        print(f"       summary: {summary}")
        print(f"       D17 refusals still live: {len(off)} {[f.control_id for f in off]}")
        print(f"       {verdict}")
        print()
finally:
    conn.close()
PYEOF
echo "exit=$?" >> "$CAP/17-gate-nine.txt"
cat "$CAP/17-gate-nine.txt"
labhash > "$CAP/18-hash-post-gate.txt"
```

**What must be true in `17-gate-nine.txt`:**

- `D17 refusals still live: 0 []` for all nine. That is R4, proven.
- Every `REFUSED:` line that remains names a **different** clause — the walk-forward fold
  majority, the variant's own curve, the kin rule, or D10's price fingerprint. Copy each such
  sentence verbatim into the handover's table; naming which clause now blocks each method is an
  exit criterion, not a footnote.
- `18-hash-post-gate.txt` equals `16-hash-post-status.txt`: a `connect_readonly` run cannot move
  the file.

**A `lab promote` or a `lab test` at this step would be a serious error.** `lab promote`
pre-registers a variant and moves a status; `lab test` spends one of the four remaining looks and
can never be undone. Neither is run. Neither appears anywhere in this phase.

#### 3c. The counts, re-derived read-only

```bash
sqlite3 "file:$SEER_LAB_DB?mode=ro" <<'SQL' > "$CAP/19-counts-after.tsv" 2>&1
.mode tabs
.headers on
SELECT 'dev_trials'        AS what, count(*) AS n FROM trials WHERE window = 'dev'
UNION ALL SELECT 'test_window_looks', count(*) FROM trials WHERE window = 'test'
UNION ALL SELECT 'methods',           count(*) FROM methods
UNION ALL SELECT 'amendments',        count(*) FROM method_amendments
UNION ALL SELECT 'insights',          count(*) FROM insights
UNION ALL SELECT 'next_free_id',      NULL;
SQL
cat "$CAP/19-counts-after.tsv"

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab next-id > "$CAP/20-next-id.txt" 2>&1
echo "exit=$?" >> "$CAP/20-next-id.txt"
```

**Expected on a complete set:** `dev_trials 850`, `test_window_looks 4` (**this number is an exit
criterion — if it is not 4, something spent a look and the handover's first line must say so**),
`methods 275`, `amendments 12`, `insights 470` (the four this phase adds come later, in Step 6),
`next-id M0262` — unchanged from the gate-reading-cadence handover, because an amendment costs no
method id. The N the luck gate judges at (policy `methods`) is expected to stay **164** for the
same reason; read it off `15-status.txt`'s
`N the luck gate judges at (policy methods):` line rather than computing it.

#### 3d. The margin table, in `trial_funding.mwr` and nothing else

```bash
sqlite3 "file:$SEER_LAB_DB?mode=ro" <<'SQL' > "$CAP/21-margins.tsv" 2>&1
.mode tabs
.headers on
SELECT t.method_id, t.candidate_id, t.n, t.trades,
       round(t.turnover, 4)         AS turnover,
       round(f.mwr * 100, 4)        AS mwr_pct,
       round(f.spy_tr_mwr * 100, 4) AS spy_tr_pct,
       round(t.max_drawdown * 100, 2) AS worst_fall_pct
FROM trials t JOIN trial_funding f ON f.trial_n = t.n
WHERE t.window = 'dev'
  AND t.method_id IN ('M0047','M0201','M0202','M0208','M0215','M0221','M0225','M0227','M0243')
ORDER BY t.method_id, t.n;
SQL
cat "$CAP/21-margins.tsv"
```

`mwr` is the money-weighted return on the owner's own monthly deposits — what `lab show` prints as
"your money earned". `total_return` and `cagr` are **not** quoted anywhere in the handover: these
books are funded, and the curve-shape columns count the owner's deposits as gains
(memory `seer-funded-book-cagr-is-a-lie`). Confirm that `spy_tr_pct` reads **7.19** for every row;
if any row differs, that trial is funded on a different deposit schedule and its margin is not
comparable — say so rather than quoting it.

**Impact:** nothing written to the lab. Hashes `12`, `16` and `18` may differ from `00` only by a
migration-on-connect from `lab control` / `lab status`; record the pair and move on, because this
phase commits the database anyway.

---

### Step 4: `lab stage` — once, here, and nowhere else

**File:** `/home/miftah/seer/lab/lab.sqlite`, `/home/miftah/seer/web/data/lab.json`
**Change:** regenerate `web/data/lab.json` from the whole database and `git add` both files under
an exclusive lock.

**Code:**

```bash
labhash > "$CAP/22-hash-pre-stage.txt"
PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab stage > "$CAP/23-stage.txt" 2>&1
echo "exit=$?" >> "$CAP/23-stage.txt"
labhash > "$CAP/24-hash-post-stage.txt"
cat "$CAP/23-stage.txt"
git -C "$MAIN" status --porcelain > "$CAP/25-main-status-staged.txt" 2>&1
cat "$CAP/25-main-status-staged.txt"
```

**What must be true:** `23-stage.txt` prints
`staged /home/miftah/seer/lab/lab.sqlite` and `staged /home/miftah/seer/web/data/lab.json` with
`exit=0`; `25-main-status-staged.txt` shows both files as **staged** (`M ` in the first column).

Three facts about `lab stage` that this step depends on and that nothing else in the set may
disturb:

- It writes the snapshot beside **the database's own repo** (`store.snapshot_path`), so with
  `SEER_LAB_DB` pointing at `/home/miftah/seer/lab/lab.sqlite` it stages the **main checkout's**
  pair, never the worktree's (memory `seer-lab-stage-targets-the-main-checkout`). Running it from
  the worktree is therefore safe and lands in the same place; running it from `$MAIN` is clearer
  and is what this step does.
- It takes `BEGIN EXCLUSIVE` and rolls back, so a parallel session's half-written transaction can
  never be what gets committed.
- It is the only command in the whole plan set permitted to run it (invariant 8). If an earlier
  phase ran it, the earlier staging is simply superseded by this one; note it in the handover's
  leftovers and move on.

**Impact:** `web/data/lab.json` now equals `lab export-json` of `lab/lab.sqlite` byte for byte,
which is exactly what `test_the_committed_snapshot_is_the_export_of_the_committed_database`
(`engine/tests/test_lab_snapshot.py:1054`) asserts. The tree is now green-able, which Step 5
checks.

---

### Step 5: The full suite and the lint, on `main`, after staging

**File:** `/home/miftah/seer` — the merged, staged checkout
**Change:** nothing; this is the guard the plan index calls for.

**Code:**

```bash
docker start seer-pg >/dev/null 2>&1 || \
  docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres

PYTHONPATH=$MAIN/engine/src "$PY" -m ruff check "$MAIN/engine" > "$CAP/26-ruff.txt" 2>&1
echo "exit=$?" >> "$CAP/26-ruff.txt"
tail -3 "$CAP/26-ruff.txt"

PYTHONPATH=$MAIN/engine/src "$PY" -m pytest "$MAIN/engine/tests" -q -rs \
  > "$CAP/27-pytest.txt" 2>&1
echo "exit=$?" >> "$CAP/27-pytest.txt"
tail -20 "$CAP/27-pytest.txt"

# The CI agreement check, named on its own so the handover can cite it by test id.
PYTHONPATH=$MAIN/engine/src "$PY" -m pytest \
  "$MAIN/engine/tests/test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database" \
  -q > "$CAP/28-snapshot-agreement.txt" 2>&1
echo "exit=$?" >> "$CAP/28-snapshot-agreement.txt"
cat "$CAP/28-snapshot-agreement.txt"
```

**What must be true:**

- `26-ruff.txt` ends `exit=0`. CI lints bugs only (E9 and F minus F401), from
  `engine/pyproject.toml`.
- `27-pytest.txt` ends `exit=0`, with `0 failed`. The Postgres tests must **run**, not skip: CI
  fails the build when they skip, and the guard greps for conftest's exact wording
  (`PG_TEST_URL is not set; start Postgres with`). Check `-rs`'s skip list has no line matching
  that signature.
- `28-snapshot-agreement.txt` passes. This is the row-for-row agreement between
  `web/data/lab.json` and `lab/lab.sqlite` that the plan index requires, and it is the CI check:
  it opens the committed database `mode=ro`, re-exports it, and compares byte for byte, failing
  with the message *"run `python -m seer_engine lab stage` (or `lab export-json`) and commit both
  files"*.
- `PYTHONPATH` resolves `config.REPO_ROOT = Path(__file__).resolve().parents[3]` to `$MAIN`, which
  is what makes `store.COMMITTED_DB` the file `lab stage` just wrote. Running this suite with the
  worktree on `PYTHONPATH` would compare the **worktree's** stale pair and prove nothing.

**If pytest is red:** stop. Do not commit. Read the failure; a sha-freeze failure in
`test_lab_methods.py` means a method file was edited **after** its `lab run --amend` recorded its
sha, which is an earlier phase's bug and must be resolved there, not papered over here.

**Impact:** the merged tree is proven green before anything is committed or pushed.

---

### Step 6: The four lab insights — written once, verified once

**File:** `/home/miftah/seer/lab/lab.sqlite` (via `lab insight`)
**Change:** four rows appended to the append-only `insights` journal.

**The hazard, stated before the commands.** `insights` carries append-only triggers: a row written
twice cannot be deleted. A piped `lab` command hides its exit code behind the pipe's last stage,
and a retried `lab note --file` is the known way this lab has double-appended an analysis it then
could not remove (memory `seer-lab-note-double-append-from-grep-exit-code`). So every insight
below is written with **no pipe**, its stdout redirected to a capture file, `$?` echoed on its own
line, and the new row's id read back from that file. `_insight`
(`commands/lab.py:3110-3118`) prints the new id and nothing else, so the capture is one integer.
**Never re-run an insight whose capture holds an integer.** If a capture holds an integer *and* a
non-zero exit, read the journal before deciding — the row went in.

Write each body to a file first so the exact text is on disk and reviewable before it becomes
permanent.

```bash
mkdir -p "$CAP/insights"
```

**Insight 1 — family A.** `--kind observation`.

```bash
cat > "$CAP/insights/A-family.txt" <<'TXT'
Five of the nine D17-blocked books carried a control that traded far too LITTLE -- 0.07x to
0.55x the book's own trade count (M0227-R20 at 0.07x, M0225-R50 0.19x, M0221-R50 0.21x,
M0215-HASH 0.34x, M0047-PLC1 0.55x). The mechanism was one error repeated: the draw's hash
carried no date term at all, or was re-keyed on a quarter, so the control's book changed only
when the eligible pool did. A control that trades a fifteenth as often pays a fifteenth of the
fee bill, so it is not the book's shape with the identity removed -- it is a cheaper strategy,
and every margin quoted against it was a margin against a handicap.

Pre-registered direction, written into each Amendment before any result was seen: an honestly
shaped control pays the real fee bill, so it earns LESS, so the book's lead WIDENS or its deficit
NARROWS. Measured on the re-drawn arms, in trial_funding.mwr against SPY TR 7.19%/yr on the same
deposits:

{the five-method family-A scoreboard, copied verbatim from the handover's family table:
 method, old margin, new margin, moved as predicted yes/no -- from 21-margins.tsv}

Score: {k} of 5 methods moved in the pre-registered direction. The two hardest cases were M0221
and M0225, where the handicapped control already BEAT its book (-1.09 and -0.89 pts): family A
predicts the deficit narrows, and that prediction is the one worth checking first, because it is
the one that could have turned a losing book into a winning one and did {not}.

One consequence to state rather than bury: M0047-EQ now has NO control arm at all. Its only two
placebos were size-weighted arms the ladder mis-aimed at it by first-declared, and both were
replaced by arms aimed at MV10 and MV20 where they belong. So the standing sentence about EQ's
+3.80-point lead over its placebo is WITHDRAWN rather than re-measured: it was never supported
by a correctly-aimed control. A method arm with no placebo produces an empty findings tuple and
is not refused, so this is consistent with D17 and is not a gap to be filled with a third arm.

Source: docs/plans/HANDOVER_20261019-the-honest-control.md, capture 21-margins.tsv.
TXT

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight \
  --kind observation \
  --title "An under-trading control is a cheaper strategy, not a shape-matched one" \
  --file "$CAP/insights/A-family.txt" \
  > "$CAP/29-insight-A.txt" 2>&1
echo "exit=$?" >> "$CAP/29-insight-A.txt"
cat "$CAP/29-insight-A.txt"
```

**Insight 2 — family B.** `--kind observation`.

```bash
cat > "$CAP/insights/B-family.txt" <<'TXT'
Four of the nine D17-blocked books carried a control that traded far too MUCH -- 2.25x to 5.20x
(M0208-HASH-N20 at 4.41x trades and 5.20x turnover, M0243-NEAR20-R 3.01x, M0201 2.27x,
M0202 2.25x). The mechanism is the mirror image of family A: the draw was re-keyed on the MONTH
using m0187.draw(seed, symbol, data_date), so the whole control book was redrawn at every
decision while the real book's ranking persisted. M0243's own file records the overshoot in
prose -- "M0227's own placebo used a sticky hash order and traded 41 times in twenty years ...
this one is redrawn each month" -- so the author saw family A, corrected by hand, and landed in
family B. One sentence, two errors, and the lesson is that the re-key period must be DERIVED from
the book it controls, never chosen.

Pre-registered direction: an over-trading control over-pays its fees, so an honestly shaped
replacement earns MORE, so the book's lead NARROWS or REVERSES.

{the four-method family-B scoreboard, copied verbatim from the handover's family table:
 method, old margin, new margin, moved as predicted yes/no -- from 21-margins.tsv}

Score: {k} of 4 methods moved in the pre-registered direction. M0208 was the arm most at risk:
+5.87 pts was the lab's biggest quoted placebo margin and it was quoted against an opponent that
traded 4.41x as often. {What it reads now, and whether the verdict survives.}

Source: docs/plans/HANDOVER_20261019-the-honest-control.md, capture 21-margins.tsv.
TXT

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight \
  --kind observation \
  --title "An over-trading control over-pays its fees, and the lead it concedes is fee drag" \
  --file "$CAP/insights/B-family.txt" \
  > "$CAP/30-insight-B.txt" 2>&1
echo "exit=$?" >> "$CAP/30-insight-B.txt"
cat "$CAP/30-insight-B.txt"
```

**Insight 3 — the D17 supersession.** `--kind synthesis`.

```bash
cat > "$CAP/insights/D17-supersede.txt" <<'TXT'
D17 refused a method on any recorded control arm outside [0.50, 2.00] on trades or turnover, and
a recorded arm is recorded forever -- trials carries append-only triggers. So the remedy D17's
own refusal message names ("re-draw it and amend") could never clear the refusal it caused: nine
dev-eligible methods would have stayed blocked by an arm that had already been replaced.

The rule now has a supersession clause. A REFUSE or WARN finding is superseded -- reported, never
dropped -- when the same method holds another placebo arm that is itself clean on both axes AND
that NAMES it in its own pre-registered declaration (Candidate.supersedes, read duck-typed
through control_shape.SUPERSEDES_ATTR). refusals() excludes it; `lab control` still prints it
with its ratios, names the arm that superseded it, and prints that arm's own resolved target
beside it where the two differ.

DECLARED, and deliberately not inferred from the target. "Another clean placebo on the same
target_id" was the obvious rule and it fails in both directions on these very nine. Too strict:
the <target-id>-PLC naming re-points a re-drawn arm at the book it actually controls, so
M0047-MV10-PLC resolves to M0047-MV10 while the arm it replaces resolves, on the ladder's
weakest rung, to M0047-EQ -- target equality would have left M0047 and M0202 blocked after every
measurement was taken. Too loose: M0215-HASH and M0215-HASH-CAP4 both resolve to M0215-CTRL, so
one honest control of CTRL would have excused an arm whose job is to price what a cap does. A
resolution the module itself labels a guess is not a fact to build a gate rule on; a declaration
written before any result exists is.

What this deliberately does NOT change: the bands do not move (WARN_BAND stays 0.80-1.25,
REFUSE_BAND stays 0.50-2.00); a `warn` SUPERSEDER does not excuse anything; an arm that declares
nothing excuses nothing, which is every arm the lab held before this batch; an unresolved or
unrecorded arm is still never a refusal; and there is still no override. A test asserts the
clause is a no-op on the lab as it stood before any honest control existed -- all nine still
failed D17 then, and no arm declared anything at all.

The cost of getting this wrong would have been paying nine method ids to re-run nine books that
needed no re-running, so the rule change is also the cheap half of the job.

Source: lab/hardgate.py (D17), lab/control_shape.py, phase 2 of
docs/plans/HONEST_CONTROL_REDRAW_PLAN.md.
TXT

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight \
  --kind synthesis \
  --title "D17 now supersedes: an honest control retires the handicapped one it replaced" \
  --file "$CAP/insights/D17-supersede.txt" \
  > "$CAP/31-insight-D17.txt" 2>&1
echo "exit=$?" >> "$CAP/31-insight-D17.txt"
cat "$CAP/31-insight-D17.txt"
```

**Insight 4 — the matched-draw rule beat M0241's 1.372x.** `--kind observation`.

```bash
cat > "$CAP/insights/matched-draw.txt" <<'TXT'
The lab's previous best shape-matched placebo was M0241's cohort mirror (m0241.placebo_book): for
each trailing calendar month it counted how many eligible members really split that month and
drew that many names in a hash order seeded on that month. Its own docstring claimed the monthly
draws were stable enough that turnover matched. Measured, it lands at 1.372x trades and 1.131x
turnover -- inside the refuse band but OUTSIDE the 0.80-1.25 match band. So the state of the art
was a warn, and a rule that merely imitated it would not have cleared the bar.

control_draw.py derives the churn instead of imitating it: at each decision session it recomputes
the real arm's own selection at this and at the previous decision session, takes the entry count
e as the size of the set difference, keeps n - e of its own held names in a date-free hash order,
and draws e fresh names from the same eligible pool. The entry count per rebalance is matched BY
CONSTRUCTION, not empirically, which is why it holds at both poles of the failure rather than at
one.

Measured on the two poles, where the hand-chosen draws read 0.07x and 3.01x:
{M0227-S20-PLC trade ratio and turnover ratio, from 11-control.txt}
{M0243-NEAR20-PLC trade ratio and turnover ratio, from 11-control.txt}
Across all {14} re-drawn arms the worst axis of any arm reads {worst ratio}, against M0241's
1.372x.

The transferable rule: a control's re-key period must be derived from the book it controls, each
rebalance, from that book's own calendar. Choosing the period by hand produced BOTH families of
failure in this lab -- sticky at 0.07x and churny at 5.20x -- from the same author correcting the
first by hand and overshooting into the second.

Source: docs/plans/HANDOVER_20261019-the-honest-control.md, captures 11-control.txt and
phase 1's own measurement; engine/src/seer_engine/lab/control_draw.py.
TXT

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight \
  --kind observation \
  --title "A derived churn beats a hand-chosen re-key period, at both poles at once" \
  --file "$CAP/insights/matched-draw.txt" \
  > "$CAP/32-insight-draw.txt" 2>&1
echo "exit=$?" >> "$CAP/32-insight-draw.txt"
cat "$CAP/32-insight-draw.txt"
```

Every `{…}` above is a **measurement slot**, and each one names the capture file it is filled
from. Fill all of them from `21-margins.tsv` and `11-control.txt` **before** running the
`lab insight` command for that body — the journal is append-only and an insight with an unfilled
slot is permanent.

**The verification that each insight exists exactly once:**

```bash
sqlite3 "file:$SEER_LAB_DB?mode=ro" <<'SQL' > "$CAP/33-insights-check.tsv" 2>&1
.mode tabs
.headers on
SELECT id, kind, title, length(body) AS body_len, added
FROM insights WHERE id > 470 ORDER BY id;
SELECT title, count(*) AS copies FROM insights
WHERE id > 470 GROUP BY title HAVING count(*) > 1;
SQL
cat "$CAP/33-insights-check.tsv"
```

**What must be true:** exactly four rows with ids `471..474` (or four consecutive ids above
whatever `01-counts.tsv` recorded as `max_insight_id`), the four titles above, and the duplicate
query returns **no rows**. If any title appears twice, do not try to delete it — the triggers
refuse — write the correction into the handover's leftovers as a known double-append and say
which id is the duplicate.

`lab stage` ran in Step 4, before these four rows existed, so **`lab stage` must run once more
after this step** to pick them up. That is not a second staging of the batch; it is the same
staging repeated over four extra rows, and the snapshot test in Step 8 is what enforces it.

```bash
PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab stage > "$CAP/34-stage-2.txt" 2>&1
echo "exit=$?" >> "$CAP/34-stage-2.txt"
cat "$CAP/34-stage-2.txt"
labhash > "$CAP/35-hash-post-stage-2.txt"
```

*(An alternative that avoids the re-stage is to write the insights **before** Step 4. It is not
chosen, because the insight bodies quote numbers that Step 3's sweep produces, and this phase
would rather stage twice than journal a number it has not yet measured.)*

**Impact:** four permanent journal rows; `web/data/lab.json` regenerated to include them.

---

### Step 7: Write the handover

**File:** `/home/miftah/seer/docs/plans/HANDOVER_20261019-the-honest-control.md` (new)
**Change:** the close-out document, in the voice of
`docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md`.

**The voice, stated so it is matched and not approximated.** Read the gate-reading-cadence
handover first. Four properties define its style and all four are mandatory here:

1. **Attribution per number.** Every figure names the capture file or the query it came from, in
   the sentence or in an italic note under the table. The gate-cadence handover's model line is
   *"Phase 3 never wrote a `16-final.txt`, so these six counts were re-derived here by a read-only
   `sqlite3 "file:…?mode=ro"` query … with the file's `git hash-object` checked identical before
   and after."*
2. **Plain language, no hedging, and the finding first.** Headings are sentences, not labels.
   A result that went against the pre-registration is stated as the result, in bold, in the first
   paragraph of its section.
3. **The arithmetic is shown when a reader could want to check it** — `12.3314 − 11.2825 =
   +1.0489` is the model.
4. **A "what is now dead" section and a numbered "Leftovers, in priority order" section**, the
   second carrying forward every live item from the gate-cadence handover's own list.

**Code — the document skeleton. Every `{…}` is a measurement slot and names its source; every
other word is final prose.**

````markdown
# Handover — fourteen honest controls, and which of nine verdicts survived them

**Written:** 2026-10-19 · **Branch:** `feature/honest-control-redraw` (merged to `main`)
**Method ids spent:** **none.** Nine `Amendment` blocks under nine existing ids ·
**Next free id:** {from 20-next-id.txt, expected M0262}

**The lab after this run**

| | |
|---|---|
| dev trials | **{from 19-counts-after.tsv}** (836 + {14}) |
| test-window looks used | **4 — unchanged. None was spent.** |
| methods | **275 — unchanged.** An amendment appends under an existing id |
| amendments | **{from 19-counts-after.tsv}** (3 + {9}) |
| insights | **{from 33-insights-check.tsv}** (470 + 4) |
| N the luck gate judges at (policy: methods) | **{from 15-status.txt}** — expected unchanged at 164, because no method was added |
| next free id | **{from 20-next-id.txt}** |

*Every count re-derived by a read-only `sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro"`
query (captures `01-counts.tsv` before, `19-counts-after.tsv` after), which never migrates the
file. `git hash-object lab/lab.sqlite` was `3969f1fa5d2066a42ed47716dd05a66050073592` at the base
commit and `{from 35-hash-post-stage-2.txt}` when this handover was written; the moves in between
are the fourteen recorded trials, nine amendment rows and four insights, and each `lab` command's
before/after pair is captured in `/home/miftah/.cache/seer-captures-honest-control`. Every
percentage in this document is `trial_funding.mwr` — the money-weighted return on the owner's own
monthly deposits, what `lab show` prints as "your money earned" — against **7.19%/yr** for the
same deposits put into SPY TR. `total_return` and `cagr` are not quoted anywhere: these books are
funded and those columns count the owner's deposits as gains.*

---

## What this session established

Nine dev-eligible methods were blocked by D17 — fourteen control arms whose trade count or
turnover did not match the arm they controlled. Each one was re-drawn at the book's own shape as
an `Amendment` under the existing method id, which costs no method id, no extra N and no
test-window look, and the margin was re-stated against the honest opponent.

{One paragraph: the headline. How many of the nine standing verdicts survived, how many narrowed,
how many reversed. State the single most surprising result in bold.}

### The nine books, before and after

| method | the book | old control | old margin | new control | new margin | did the verdict survive? |
|---|---|---|---|---|---|---|
| M0047 | `M0047-MV10` (11.15) | `M0047-PLC1-MV10` (9.87) | **+1.28** | `M0047-MV10-PLC` ({mwr}) | **{Δ}** | {one sentence} |
| M0047 | `M0047-MV20` (10.42) | `M0047-PLC1-MV20` (9.88) | **+0.54** | `M0047-MV20-PLC` ({mwr}) | **{Δ}** | {one sentence} |
| M0201 | `M0201-Y20-MV10` (9.54) | `M0201-PLC1-MV10` (10.26) | **−0.72** | `M0201-Y20-MV10-PLC1` ({mwr}) | **{Δ}** | {one sentence} |
| M0201 | `M0201-Y20-MV10` (9.54) | `M0201-PLC2-MV10` (8.06) | **+1.48** | `M0201-Y20-MV10-PLC2` ({mwr}) | **{Δ}** | {one sentence} |
| M0202 | `M0202-Y20-HALF` (12.65) | `M0202-PLC1-HALF` (11.30) | **+1.35** | `M0202-Y20-HALF-PLC1` ({mwr}) | **{Δ}** | {one sentence} |
| M0202 | `M0202-Y20-HALF` (12.65) | `M0202-PLC2-HALF` (9.56) | **+3.09** | `M0202-Y20-HALF-PLC2` ({mwr}) | **{Δ}** | {one sentence} |
| M0202 | `M0202-Y20-HALF-FAST` (12.14) | `M0202-PLC1-HALF-FAST` (11.38) | **+0.76** | `M0202-Y20-HALF-FAST-PLC1` ({mwr}) | **{Δ}** | {one sentence} |
| M0208 | `M0208-CGO-N20` (13.88) | `M0208-HASH-N20` (8.01) | **+5.87** | `M0208-CGO-N20-PLC` ({mwr}) | **{Δ}** | {one sentence} |
| M0215 | `M0215-CTRL` (10.62) | `M0215-HASH` (8.66) | **+1.96** | `M0215-CTRL-PLC` ({mwr}) | **{Δ}** | {one sentence} |
| M0215 | `M0215-CAP4` (10.34) | `M0215-HASH-CAP4` (8.62) | **+1.72** | `M0215-CAP4-PLC` ({mwr}) | **{Δ}** | {one sentence} |
| M0221 | `M0221-C50` (5.63) | `M0221-R50` (6.72) | **−1.09** | `M0221-C50-PLC` ({mwr}) | **{Δ}** | {one sentence} |
| M0225 | `M0225-C50` (5.85) | `M0225-R50` (6.74) | **−0.89** | `M0225-C50-PLC` ({mwr}) | **{Δ}** | {one sentence} |
| M0227 | `M0227-S20` (12.95) | `M0227-R20` (7.73) | **+5.22** | `M0227-S20-PLC` ({mwr}) | **{Δ}** | {one sentence} |
| M0243 | `M0243-NEAR20` (10.45) | `M0243-NEAR20-R` (4.38) | **+6.07** | `M0243-NEAR20-PLC` ({mwr}) | **{Δ}** | {one sentence} |

*Every `mwr` at full precision from `21-margins.tsv`; the old margins reproduce the figures the
analysis document re-derived on 2026-10-19 from the same two columns. A positive margin means the
book earned more than its control; a negative one means the control won.*

### The family scoreboard: did the two pre-registered directions hold?

Both directions were written into each `Amendment`'s `hypothesis` and committed **before** any
result was seen. They are not post-hoc readings.

**Family A — the control traded 0.07x to 0.55x, so it under-paid its fees.** Prediction: an
honest control earns **less**, so the book's lead **widens** or its deficit **narrows**.
Five methods, seven arms: M0047 (2), M0215 (2), M0221, M0225, M0227.

| method | old margin | new margin | moved as predicted? |
|---|---|---|---|
{seven rows from 21-margins.tsv}

**{k} of 5 methods and {j} of 7 arms moved in the pre-registered direction.**
{One paragraph on what the misses mean, if any. M0221 and M0225 are the hardest case in this
family, because there the handicapped control already BEAT the book — the prediction there is
that the deficit narrows, and whether it closed is what decides whether the cap-weighted
yardstick is worth anything at all.}

**Family B — the control traded 2.25x to 5.20x, so it over-paid.** Prediction: an honest control
earns **more**, so the book's lead **narrows or reverses**. Four methods, seven arms: M0201 (2),
M0202 (3), M0208, M0243.

| method | old margin | new margin | moved as predicted? |
|---|---|---|---|
{seven rows from 21-margins.tsv}

**{k} of 4 methods and {j} of 7 arms moved in the pre-registered direction.**
{One paragraph. M0208 carried the lab's biggest quoted placebo margin, +5.87 pts against an
opponent trading 4.41x as often; say what it reads now.}

**What a split verdict would mean, and whether we got one.** The two families are the same error
with the sign flipped — the draw's re-key period chosen by hand rather than derived — so a run in
which both directions held is evidence that the fee bill, not the signal, was most of what the
old margins measured. {State which happened.}

### The two mis-resolutions, repaired

`control_shape.resolve_target` walks four rungs and reports which one it used. Two of the fourteen
old arms resolved by `first-declared`, the weakest rung, which is the ladder honestly reporting a
guess. Naming every new arm `<target-id>-PLC` makes `sibling-stem` — the strongest rung — name the
intended book, and both guesses are now gone.

- **`M0047-PLC1-MV10` and `-MV20` resolved to `M0047-EQ`.** They are *size*-weighted placebos and
  their true targets are `M0047-MV10` and `M0047-MV20`. Numerically the shapes barely differ
  (1606 vs 1600 trades), but the quoted margin does: against `M0047-EQ` (13.67) the lead read
  **+3.80 pts**; against the true target `M0047-MV10` (11.15) it reads **+1.28 pts**. The new
  arms are `M0047-MV10-PLC` and `M0047-MV20-PLC`, resolved by `sibling-stem`, and the margins
  above are stated against the true targets.

  **And so `M0047-EQ` ends this plan set with no control arm at all.** That is the correct
  outcome and not an omission. Its only placebos were the two size-weighted arms above, aimed at
  it by the ladder's weakest rung; their replacements are aimed where they belong. The standing
  sentence about EQ's **+3.80-point lead over its placebo is withdrawn, not re-measured** — it
  was never supported by a correctly-aimed control, and the repair is to stop quoting it rather
  than to manufacture an arm for it. A method arm with no placebo produces an empty findings
  tuple, which `control_shape.findings` documents as the correct answer and not an error, so EQ
  is not refused for having none: this is consistent with D17 rather than an exception to it.

  It also explains why the D17 rule is a **declaration** and not a target match. The arms that
  retire `M0047-PLC1-MV10` and `-MV20` resolve to `MV10` and `MV20`, not to `EQ`, so a rule
  keyed on target equality would have retired neither and M0047 would have stayed blocked after
  all fourteen measurements had been taken. `lab control` prints both targets on a superseded
  row for exactly this reason.
- **`M0202-PLC1-HALF-FAST` resolved to `M0202-Y20-HALF`** because its own stem
  (`M0202-PLC1-HALF`) is itself a placebo and is excluded from `_eligible_targets`. Against
  `M0202-Y20-HALF` (12.65) its margin read **+1.27 pts**; against the true target
  `M0202-Y20-HALF-FAST` (12.14) it reads **+0.76 pts**. The new arm is
  `M0202-Y20-HALF-FAST-PLC1`.

*Both pairs of old/new numbers from `21-margins.tsv`; the resolution rungs from `11-control.txt`.*

### M0215's difference-in-differences, re-stated on the honest pair

M0215's own method file sets the success condition in these words: *"a capped variant beats CTRL
funded with the worst fall at or under 20%, a positive or less negative 2009-2015 edge and a
majority of folds, and its gain over CTRL is larger than HASH-CAP4's over HASH (so the cap helps
the raise book specifically)"* (`m0215_sector_capped_calm_raisers.py:274-277`). It is a
comparison **between two placebos**, so a mis-shaped placebo pair invalidates it twice over.

On the old pair:

    (CAP4 − CTRL)            = 10.34 − 10.62 = −0.28
    (HASH-CAP4 − HASH)       =  8.62 −  8.66 = −0.04
    difference-in-differences = −0.28 − (−0.04) = −0.24     → the condition FAILED

On the honest pair:

    (CAP4 − CTRL)                 = 10.34 − 10.62 = −0.28   (unchanged; neither book moved)
    (CAP4-PLC − CTRL-PLC)         = {mwr} − {mwr} = {Δ}
    difference-in-differences      = {−0.28 − Δ} = {DiD}    → {HOLDS / still FAILS}

{One sentence: whether the cap helps the raise book specifically, now that the comparison is
between two placebos of the right shape. If it still fails, say that a mis-shaped placebo was
never the reason it failed, which is itself worth knowing.}

### What the D17 supersession changed, and what it deliberately did not

{Two paragraphs, from phase 2's plan and its tests.}

**Changed.** A `REFUSE` finding is now superseded — reported, never dropped — when the same method
holds another placebo arm that resolves to the same `target_id` and is itself inside
`REFUSE_BAND`. `refusals()` excludes it, so `hardgate.check` stops raising on an arm that has
already been replaced. Without this, D17's own refusal message ("re-draw it and amend") named a
remedy the code could not honour, because `trials` is append-only and the mis-shaped arm is
recorded forever.

**Deliberately not changed.** The bands did not move: `WARN_BAND` is still `(0.80, 1.25)` and
`REFUSE_BAND` still `(0.50, 2.00)`, and they are still the log-symmetric bands cut from the lab's
own control arms. A `warn` sibling excuses nothing. A sibling resolving to a *different* target
excuses nothing. An `unresolved` or `unrecorded` arm is still never a refusal. The superseded arm
stays visible in `lab control` with its ratios and the id of the arm that superseded it. And there
is still **no override** on the hard gate — this is the rule change D17's own text invites, argued
for in the commit, not a bypass.

A test asserts the clause is a **no-op on the lab as it stood before this run**: with the
pre-batch database, all nine methods still failed D17. {Name the test.}

### Does the gate take the nine now?

| method | D17 refusals still live | what the hard gate says today |
|---|---|---|
{nine rows from 17-gate-nine.txt: the D17 count — which must be 0 — and either
 "TAKEN" or the verbatim sentence of whichever OTHER clause now refuses it}

**D17 refuses none of the nine.** {One paragraph on which clauses now stand in the way — the
walk-forward fold majority, the variant's own curve, the kin rule, D10's price fingerprint — and
how many of the nine the gate would actually take. Say plainly that this plan set unblocked the
D17 clause and promised nothing about the others; whether anything is promoted is the owner's
call on a separate day, and nothing here was promoted.}

*From `17-gate-nine.txt`, a `store.connect_readonly` (`mode=ro`) run of `hardgate.summary`,
`hardgate.mis_shaped_controls` and `hardgate.check` per method. No status moved, no
pre-registration was written, and `lab promote` was not invoked.*

### The rule that did it

{Two to four paragraphs on `control_draw.py`: what the derived churn is, why it beats a
hand-chosen re-key period, the measured ratios on both poles against M0241's 1.372x / 1.131x,
and the worst axis across all fourteen arms. This is the part the next session reuses, so it is
written as a rule and not as a narrative. Numbers from `11-control.txt` and phase 1's own
measurement.}

---

## What is now dead, and must not be bought with another method id

- **Hand-choosing a control's re-key period.** It produced both families of failure in this lab,
  from the same author correcting one by hand and overshooting into the other. The period is
  derived from the controlled book's own calendar, each rebalance, by `control_draw.py`. Do not
  spend an id re-deriving this.
- **M0241's cohort mirror as the state of the art.** 1.372x trades / 1.131x turnover — a warn, not
  a match. Superseded by the derived churn. Its own docstring's claim that "the monthly draws are
  stable between rebalances, so the turnover matches too" is measured and wrong, and the file is a
  closed record that must not be edited to say so.
- {Anything a measured margin reversal kills outright — one bullet per method whose standing
  verdict did not survive, naming what the old margin was taken to prove and what it actually
  measured.}

## Leftovers, in priority order

1. {Any book whose re-drawn arm landed in `warn` rather than `ok`, with its measured ratios and
   what a second, differently-constructed draw would have to do. A second amendment is admissible
   only for a missed SHAPE, never for a disliked margin — invariant 4.}
2. **Whether to promote any of the nine.** This set unblocked the D17 clause and nothing else.
   {List the methods the gate would now take, if any.} Promotion is the owner's call on a separate
   day and is not implied by anything here.
3. **M0261, already queued** — *"Does the safety gate's best reading speed hold on a second book,
   or was the zig-zag luck about calendar dates?"* Carried forward from the gate-reading-cadence
   handover, item 2, unchanged.
4. **The two-month gate rung (`k = 2`), deferred to an `Amendment` under M0260 — free in method
   ids.** Carried forward from the gate-reading-cadence handover, item 3, unchanged. This set is
   the proof that amendments are cheap and work.
5. **Insight 457's practical conclusion still stands on the site** ("weight by company size"),
   withdrawn by 462 but, `insights` being append-only, still visible to the owner. Carried forward
   from the gate-reading-cadence handover, item 6.
6. **P2-ENG-N3LB** — `name_count.py`'s docstring still calls the dev trial count "the lab's N",
   which the 2026-10-08 policy move made wrong. Carried forward, item 7.
7. **P3-ENG-V2KQ** — append a dated §7.3 revision to the lab design doc recording the N policy
   move to methods. Carried forward, item 8.
8. **`sim.rules.PRESETS` has no weekly fractional Gotrade preset.** Academic for M0260's book;
   carried forward, item 9, in case a weekly arm wins somewhere.
9. **The buyback holdability problem.** Carried forward, item 5: an 11.4 pt/yr lead that falls
   55-85% is a containment problem, not a gate problem.

## Environment notes that save an hour

- **The worktree has no venv and no research store.** `PY=/home/miftah/seer/engine/.venv/bin/python`,
  `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`. Never rebuild a store.
- **`PYTHONPATH=<checkout>/engine/src`, and it decides which `lab.sqlite` the tests read.**
  `config.REPO_ROOT = Path(__file__).resolve().parents[3]`, so `store.COMMITTED_DB` follows
  PYTHONPATH. The snapshot test compares the pair in whichever checkout PYTHONPATH names.
- **`lab stage` targets the checkout that owns the database**, and its commit takes **no
  pathspec**: a pathspec re-reads the working tree and defeats the staging.
- **Merge before you stage.** A lab database committed ahead of the method files it refers to puts
  `main` in a state where a fresh clone fails the sha freeze.
- **Never judge a `lab` command by a piped exit code**, and never retry an append-only write
  (`lab insight`, `lab note --file`) on the strength of one: redirect, echo `$?`, read the id back.
- **A `sqlite3 "file:…?mode=ro"` query never migrates the database; any `lab` command does**, even
  a read. `store.connect_readonly` is the Python equivalent and is what the hard-gate sweep used.
- **The captures live in `/tmp/honest-control`, copied to
  `/home/miftah/.cache/seer-captures-honest-control`** because `/tmp` does not survive a reboot.
  `17-gate-nine.txt` is the only place the per-method hard-gate clause is printed with the D17
  count beside it; no `lab` command prints that pair.
````

**Impact:** one new document, written before the lab commit so it lands in the same commit as the
database it describes.

---

### Step 8: Commit, and push

**File:** `/home/miftah/seer` — the staged index
**Change:** one commit carrying the database, the snapshot, the handover and the plan-index status
move; then the push.

**Code:**

```bash
# The plan index's status, on main after the merge.
#   Status: planned  ->  Status: landed
"$PY" - <<'PYEOF'
from pathlib import Path
p = Path("/home/miftah/seer/docs/plans/HONEST_CONTROL_REDRAW_PLAN.md")
t = p.read_text(encoding="utf-8")
assert "**Status:** planned" in t, "the index's status line is not where it was"
p.write_text(t.replace("**Status:** planned", "**Status:** landed", 1), encoding="utf-8")
print("status -> landed")
PYEOF

# The handover and the index join the index `lab stage` already built. `lab stage` git-added
# lab/lab.sqlite and web/data/lab.json; these two are added by pathspec because `lab stage`
# knows nothing about them.
git -C "$MAIN" add -- docs/plans/HANDOVER_20261019-the-honest-control.md \
                      docs/plans/HONEST_CONTROL_REDRAW_PLAN.md
git -C "$MAIN" status --porcelain > "$CAP/36-index.txt" 2>&1
cat "$CAP/36-index.txt"
# Expected, all staged (first column M or A):
#   M  lab/lab.sqlite
#   M  web/data/lab.json
#   A  docs/plans/HANDOVER_20261019-the-honest-control.md
#   M  docs/plans/HONEST_CONTROL_REDRAW_PLAN.md

# THE COMMIT TAKES NO PATHSPEC. `git commit -- <paths>` re-reads the working tree and defeats
# what `lab stage` staged under its exclusive lock (memory: seer-lab-stage-commit-needs-the-index).
git -C "$MAIN" commit -m "chore(lab): close out the honest-control-redraw plan set

Fourteen control arms re-drawn at the shape of the book each controls, under
nine amendments on nine existing method ids. No method id spent, N unchanged,
and the test-window look count is still 4.

Four insights journalled: the two family findings, the D17 supersession, and
the measurement that the derived-churn draw beats M0241's 1.372x at both poles.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  > "$CAP/37-commit.txt" 2>&1
echo "exit=$?" >> "$CAP/37-commit.txt"
cat "$CAP/37-commit.txt"

# One last agreement check against what is actually committed, before the push.
PYTHONPATH=$MAIN/engine/src "$PY" -m pytest \
  "$MAIN/engine/tests/test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database" \
  -q > "$CAP/38-snapshot-final.txt" 2>&1
echo "exit=$?" >> "$CAP/38-snapshot-final.txt"
cat "$CAP/38-snapshot-final.txt"

git -C "$MAIN" push origin main > "$CAP/39-push.txt" 2>&1
echo "exit=$?" >> "$CAP/39-push.txt"
cat "$CAP/39-push.txt"
```

**If the push is rejected** because `main` moved: **do not `pull --rebase`.** A rebase replays a
stale `lab.sqlite` over the live shared database other sessions are writing. Instead:

```bash
git -C "$MAIN" fetch origin
git -C "$MAIN" merge --no-edit origin/main
PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab stage > "$CAP/40-restage.txt" 2>&1
echo "exit=$?" >> "$CAP/40-restage.txt"
git -C "$MAIN" commit -m "chore(lab): re-stage after merging origin/main

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  > "$CAP/41-recommit.txt" 2>&1 || true
# and check the trial ids are contiguous -- a lost row is the failure mode this guards:
sqlite3 "file:$SEER_LAB_DB?mode=ro" \
  "SELECT min(n), max(n), count(*), max(n) - min(n) + 1 AS span FROM trials;" \
  > "$CAP/42-contiguous.txt" 2>&1
cat "$CAP/42-contiguous.txt"   # count must equal span
git -C "$MAIN" push origin main >> "$CAP/39-push.txt" 2>&1
```

Finally, preserve the captures:

```bash
cp -a "$CAP/." "$KEEP/"
ls "$KEEP"
```

**Impact:** `main` carries the whole set. From here the plan is forward-only; a correction is a
new commit.

---

### Step 9: The partial-set contingency

**File:** none — this is a decision procedure, run at Step 1 and again if any later step disagrees
with it.
**Change:** what this phase writes when the set is incomplete.

**How to detect it, in three independent ways. Use all three; the database wins.**

1. **The database (authoritative).** `04-completeness.txt` from Step 1 is non-empty: at least one
   of the fourteen expected `-PLC` candidate ids has no recorded dev trial. This is the ground
   truth, because a phase can claim success in prose and still have failed to record a trial.
2. **The plan files.** Each phase's plan file carries exit criteria; a phase that stopped will have
   left a note. Phase 1's exit criteria say explicitly: *"If either lands outside, the phase stops,
   writes the measured ratios and the reason into the plan set, and does not fan out."* So grep the
   plan set:
   ```bash
   grep -rniE 'stopped|did not fan out|missed the band|BLOCKED|outside the (match|warn) band' \
     "$WT/.workflows/plan/honest-control-redraw/" \
     "$WT/docs/plans/HONEST_CONTROL_REDRAW_PLAN.md" > "$CAP/43-stop-notices.txt" 2>&1
   cat "$CAP/43-stop-notices.txt"
   ```
3. **`lab control`.** An arm that ran but landed in `warn` is present in the database and absent
   from no list — it is a *shape miss*, not a missing phase. Step 3a's capture distinguishes the
   two: a missing arm has no row at all; a missed arm has a row with verdict `warn` or `refuse`.

**The three states and what each changes in the document:**

| state | detection | what phase 8 does |
|---|---|---|
| **complete** | `04-completeness.txt` empty, all fourteen `ok` in `11-control.txt` | the document as skeletoned above |
| **shape miss** — an arm ran but landed outside `WARN_BAND` | the arm has a trial row; `11-control.txt` reads `warn` (or `refuse`) for it | the book's row in the main table reads the new margin **and** the measured ratios, flagged; the family scoreboard counts it as measured; the "what is now dead" section does **not** claim the rule is universal; **leftover item 1** names the book, its ratios and what a differently-constructed second draw would have to achieve. **No second amendment is written in this phase** |
| **missing phase** — one or more arms never ran | `04-completeness.txt` non-empty; `43-stop-notices.txt` names the phase | the title of the before/after table becomes "the {k} books that now hold an honest control"; a **second table** lists the books that do **not**, with the old margin, the old ratios and the named reason; the family scoreboard is scored out of the arms that ran, with the denominator stated (`{j} of {m} family-A arms that ran`, never of 7); **leftover item 1** becomes the unfinished books, in priority order |

**In every one of the three states, this phase still runs.** It merges, stages, commits, pushes and
cleans up. The reason is design §4: a plan set that measured nine books and landed seven honest
controls has produced seven honest measurements and one named miss, and all eight are findings. The
failure mode to avoid is a batch that sits unmerged on a branch while someone decides whether it is
good enough — the database already holds the trials, append-only and permanent, and the method
files that produced them must reach `main` or the lab claims results from code nobody can read.

**The one thing a partial set changes about the title and the first paragraph:** the headline is
*"{k} of nine books now hold an honest control, and here is what each one's margin did"* — the miss
is in the first sentence, not in a footnote. If phase 1 itself missed the band and phases 3–7 never
started, then the finding of the whole set is *"the derived-churn rule did not land inside
[0.80, 1.25] at {which pole}, measured {ratios}"*, the D17 supersession from phase 2 still lands on
its own (it writes nothing to the database and is independently useful), and the handover is a
one-page record of a rule that was proposed, measured and rejected — which is exactly what this lab
is built to produce.

**Impact:** none on the commands. This step changes what Step 7 writes.

---

### Step 10: Cleanup — the worktree and the branch, last

**File:** `/home/miftah/.worktrees/seer/honest-control-redraw`, branch
`feature/honest-control-redraw`
**Change:** removed, but only after the push has landed and only if nothing else is in the
worktree.

**Code:**

```bash
# 1. The push must have landed. Not "was attempted" -- landed.
grep -q 'exit=0' "$CAP/39-push.txt" && \
  git -C "$MAIN" rev-parse HEAD origin/main   # the two must print the same sha

# 2. Nothing else may be running in the worktree.
git -C "$MAIN" worktree list > "$CAP/44-worktrees.txt" 2>&1
cat "$CAP/44-worktrees.txt"
git -C "$WT" status --porcelain > "$CAP/45-wt-status.txt" 2>&1
cat "$CAP/45-wt-status.txt"          # must be empty
tmux ls 2>/dev/null | grep -i 'honest-control' > "$CAP/46-tmux.txt" 2>&1
cat "$CAP/46-tmux.txt"               # must be empty

# 3. Every branch commit must be an ancestor of main -- nothing is being thrown away.
git -C "$MAIN" log --oneline origin/main..feature/honest-control-redraw \
  > "$CAP/47-unmerged.txt" 2>&1
cat "$CAP/47-unmerged.txt"           # must be empty

# 4. Only then:
git -C "$MAIN" worktree remove "$WT"
git -C "$MAIN" branch -d feature/honest-control-redraw   # -d, never -D: it refuses unmerged work
git -C "$MAIN" worktree prune
git -C "$MAIN" worktree list
```

**Stop conditions, each of which means do not clean up:**

- `45-wt-status.txt` is non-empty — someone has uncommitted work in the worktree.
- `46-tmux.txt` names a live session — a swarm child is still running there.
- `47-unmerged.txt` is non-empty — the merge did not take every commit.
- `git branch -d` refuses — take the refusal at face value and investigate; **never** reach for
  `-D`.

Optionally, matching the gate-reading-cadence precedent (`465fcfd`), one final bookkeeping commit:

```bash
git -C "$MAIN" commit --allow-empty -m "chore(orch): honest-control-redraw landed -- prune the set

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git -C "$MAIN" push origin main
```

**Impact:** the worktree is gone and the branch is deleted. The database keeps every amendment,
which is correct: they are measurements.

---

## Verification

**Build:** there is nothing to build. The lint stands in for it:

```bash
PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/python \
  -m ruff check /home/miftah/seer/engine
```

**Tests:**

```bash
docker start seer-pg
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/python \
  -m pytest /home/miftah/seer/engine/tests -q -rs
```

Run on `main` **after** the merge and **after** `lab stage`, never between them. The Postgres
tests must run, not skip.

**Manual check:**

- `11-control.txt`: fourteen new arms `ok`, fourteen old arms printed with their ratios and the
  supersession marker, and no refusal in the closing block.
- `17-gate-nine.txt`: `D17 refusals still live: 0 []` on all nine, and every remaining refusal
  naming a different clause.
- `19-counts-after.tsv`: `test_window_looks` is **4**. This is the single number that, if wrong,
  invalidates the run.
- `33-insights-check.tsv`: four rows, four distinct titles, no duplicates.
- `38-snapshot-final.txt`: the CI agreement check passes against what is committed.
- The handover contains **no** `{` character — every measurement slot filled.
- `grep -rn 'total_return\|cagr' docs/plans/HANDOVER_20261019-the-honest-control.md` finds them
  only in the sentence explaining why they are not quoted.

**Exit criteria:**

1. `main` carries `control_draw.py`, the phase-2 changes, the nine amended method files, the new
   tests, the handover, and a `lab/lab.sqlite` / `web/data/lab.json` pair that agree row for row.
2. `pytest engine/tests` and `ruff check engine` are green on `main`, with Postgres running.
3. `hardgate.check` raises no D17 refusal for any of M0047, M0201, M0202, M0208, M0215, M0221,
   M0225, M0227, M0243 — proven by `17-gate-nine.txt`, with no `lab promote` and no `lab test`
   anywhere in the phase's captures.
4. The test-window look count is 4, the method count is 275, and `lab next-id` is unchanged.
5. Four insights exist, each exactly once.
6. The push has landed (`HEAD == origin/main`), the worktree is removed and the branch deleted.
7. `docs/plans/HANDOVER_20261019-the-honest-control.md` states, for every book that ran, the old
   margin, the new margin and whether the standing verdict survived — and, for every book that did
   not, why not.

---

## Handoffs

Work found while planning this phase and deliberately left:

- **Promoting any of the nine (nobody's, by design).** R4 is "`lab promote` must stop refusing the
  nine", not "promote them". Step 3b runs the gate read-only and never moves a status. Which
  methods are actually promoted is the owner's call on a separate day, and the handover's leftover
  item 2 says so. Spending a test-window look is forbidden outright by invariant 6.
- **A second amendment for any arm that missed `WARN_BAND` (not this phase, and arguably not this
  plan set).** Invariant 4 admits one only for a missed *shape*, never for a disliked margin.
  Phase 8 records the miss and its ratios in leftover item 1 and writes no code.
- **`lab reevaluate` on any of the nine.** None of the nine is `rejected`, so no edge is needed,
  and re-judging recorded trials is outside R3 and R4 both.
- **Updating `/sera` method pages whose prose quotes an old margin** (the
  `update-stale-sera-methods-page` skill's job). Fourteen margins moved, and the site's method
  pages are generated from `lab.json` — which this phase regenerates — but any hand-written prose
  on those pages that quotes "+5.87 pts against its placebo" is now stale. Record it as a leftover;
  it belongs to a separate session with that skill, not to a close-out that must not touch `web/`.
- **`name_count.py`'s stale docstring (P2-ENG-N3LB) and the lab design doc's §7.3 revision
  (P3-ENG-V2KQ).** Carried forward unchanged from the gate-reading-cadence handover. Touching them
  here would be scope creep into a documentation debt this plan set did not create.
- **Phase 1's measured ratios, if phase 1 left none written.** Phase 8 re-derives them read-only
  rather than re-running anything, and says in the attribution line that it did — but the better
  fix is for phase 1 to write them, and that is a note to phase 1, not a change here.

---

## Rollback

This phase has three stages with different rollbacks, and only the first two are reversible.

**Before the commit (Steps 1–7).** Everything is reversible.

```bash
git -C /home/miftah/seer merge --abort            # if the merge is in progress
git -C /home/miftah/seer reset --merge HEAD@{1}   # if the merge committed; never `reset --hard`,
                                                  # which would discard the dirty lab.sqlite
git -C /home/miftah/seer restore --staged -- lab/lab.sqlite web/data/lab.json
rm -f /home/miftah/seer/docs/plans/HANDOVER_20261019-the-honest-control.md
```

`lab/lab.sqlite` itself is **never** restored, reset or checked out. It holds fourteen trials that
earlier phases paid for and `git checkout -- lab/lab.sqlite` would destroy them. If the merge must
be undone, undo the merge and leave the database alone.

**After the four insights (Step 6) but before the commit.** The insights are already permanent:
`insights` carries append-only triggers on update and delete, and there is no edge back. The
rollback is a fifth insight that corrects the four — the same shape as insight 462 withdrawing 457.
Do not attempt a delete.

**After the push (Step 8).** Forward-only. A later correction is a new commit: a corrected
handover, a correcting insight, or a revert of the merge if the code is wrong. Reverting the merge
would leave `main` with a database describing method files `main` no longer has, so a revert must
also be followed by a fresh `lab stage` and an explicit note in the next handover saying the lab
holds amendments for files that were reverted. That is ugly enough that Step 5's green suite is the
real gate, and it runs before the commit for exactly this reason.

**The worktree and branch (Step 10).** Recoverable until `git branch -d` runs, and the `-d` form
refuses if anything is unmerged. After deletion the commits live in `main`'s history; recover a
file with `git show <sha>:<path>`.
