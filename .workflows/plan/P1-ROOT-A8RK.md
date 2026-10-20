> Adopted from `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md` phase 6. Source: `.workflows/plan/control-draw-remedies/phase-6.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 6: The R1 verdict, the sentences, and the close-out

**Plan set:** `CONTROL_DRAW_REMEDIES_PLAN.md`
**Analysis:** `docs/analyzer/20261020-113306-C7K4_code_analyzer.md`
**Satisfies:** **R2** (confront, in writing, that remedy 2 is a second mechanism and that R1 as the
brief reads it cannot be met) · **R3** (state plainly that this bought honest controls and not
promotions) · **R4** (frozen records, no test-window look, every correction an append or a new row)
**Depends on:** Phase 3 (M0208 re-drawn under the shadow) and Phase 5 (the weight rule and the arms
it earned — or its one-paragraph STOP). Phases 1 and 4 are read through 3 and 5's results files.
**Difficulty:** NORMAL
**Package:** `docs/plans/` + `lab/lab.sqlite` + `web/data/lab.json` (**no** file under `engine/src`)

---

## Goal

After this phase there is one document — `docs/plans/HANDOVER_20261020-control-draw-remedies.md` —
that states the R1 verdict (two rules on two axes; R1 as literally written is unmeetable and no
further work makes it meetable), says in plain language that the hard gate takes none of the nine
and that this set bought honest **controls** and not promotions, and carries every owner-facing
sentence the set moved, corrected. The lab's own journal carries the set's findings as `insights`
rows; `lab/lab.sqlite` and `web/data/lab.json` are committed together and agree row for row; the
test-window look count is still **4**; and leftovers 1, 2 and 3 of the honest-control handover are
each closed **with a result**, including a STOP if that is what phase 4 measured.

This phase runs **no** `lab run`, **no** `lab test`, **no** `lab promote`, and edits **no** source
file. It sweeps, writes, journals, stages, commits and pushes — in that order and no other.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing. No row, no file, no sentence is removed. A wrong `insights` row can only be
superseded by a later one; a wrong `methods.analysis` section can only be followed by a dated
correction; only `methods.verdict` is genuinely replaceable.

**Renames:** nothing.

**Creates:**
- `docs/plans/HANDOVER_20261020-control-draw-remedies.md` — **new, this phase only**
- `.workflows/plan/control-draw-remedies/phase-6-results.md` — **new** (may be a short pointer at
  the handover; see Step 10)
- `.workflows/plan/control-draw-remedies/insights/*.txt` + `insights/README.md` — **new**, the
  insight bodies and the one-command-each form, written before any of them is run
- **2 to 4 `insights` rows**, ids `{479..}` — measured at Step 7, never assumed
- **0 to 4 corrected `methods.verdict` strings** and the matching dated `methods.analysis`
  sections, written by `lab note` — the exact set is decided by Step 3's sweep, not by this plan
- one `lab:` commit on `main` carrying `lab/lab.sqlite` + `web/data/lab.json` + the handover + the
  insight bodies + the results file

**Signature changes:** none. This phase changes no code.

**Requires (from earlier phases)** — see *Inputs required* below for the exact format:
- **Phase 3:** M0208's measured trade/turnover ratios under the shadow, D17's re-read state for
  M0208, and whether the published sentence moved (and to what).
- **Phase 5:** the arms it drew with their `lab control` ratios and supersession outcomes — or the
  single paragraph saying phase 4 stopped and nothing was drawn.
- **Phase 1 (through phase 3's results file):** the per-chassis shadow table and the chosen K.
- **Phase 4 (through phase 5's results file, and from `phase-4-results.md` directly):** the
  **four** assignment rules' numbers — A (month-keyed entry order), B (date-free keep ladder),
  C (the control's own values re-shaped), D (keeps first, entrants last down the sorted vector) —
  and the yes/no on `≤ 0.5563` turnover for M0221, plus the yes/no on M0201's 0.0059 gap, stated
  independently of each other.

**Leaves alone (owned by others):**
- `engine/src/**` — **every file**, including `control_draw.py` (Phase 2), `control_weight.py`
  (Phase 5) and every method file. This phase reads them and quotes them; it edits none.
- The `trials`, `method_amendments`, `candidates` rows phases 3 and 5 recorded. Frozen (I2).
- `.workflows/plan/control-draw-remedies/phase-{1,3,4,5}-results.md` — read, never edited.

---

## Files

| File | Action | What changes |
|---|---|---|
| `docs/plans/HANDOVER_20261020-control-draw-remedies.md` | create | the whole close-out; skeleton in Step 6 |
| `.workflows/plan/control-draw-remedies/insights/README.md` | create | the one-command-each, never-piped form (Step 7) |
| `.workflows/plan/control-draw-remedies/insights/R1-two-rules.txt` | create | insight body |
| `.workflows/plan/control-draw-remedies/insights/shadow.txt` | create | insight body |
| `.workflows/plan/control-draw-remedies/insights/weight-vector.txt` | create | insight body |
| `.workflows/plan/control-draw-remedies/insights/d17-inert.txt` | create (conditional) | insight body — only if Step 7a finds no near-duplicate already journalled |
| `.workflows/plan/control-draw-remedies/phase-6-results.md` | create | what this phase measured and what it left (Step 10) |
| `lab/lab.sqlite` | modify (via `lab note`, `lab insight`, `lab stage`) | corrected verdicts, appended analysis sections, new insight rows |
| `web/data/lab.json` | modify (via `lab stage` only) | the export of the above; CI checks it agrees row for row |

**No file under `engine/src` appears in this table, and none may.**

---

## Inputs required from other phases

Each upstream phase leaves its numbers in
`.workflows/plan/control-draw-remedies/phase-N-results.md`. This phase **reads those files and the
database**; it re-derives nothing from a backtest. Where a results file is missing, the database is
the authority (`sqlite3 … mode=ro` over `trials`) and the handover's attribution line says so.

**From Phase 3 (`phase-3-results.md`) — required, in this shape:**

```yaml
phase: 3
shadow_K: {integer}                     # the replay depth phase 1 chose and phase 2 implemented
m0208:
  new_arm_id: "{e.g. M0208-CGO-N20-PLC2}"
  trial_n: {integer}
  trades: {integer}                     # the arm's own
  turnover: {float}
  trade_ratio: {float}                  # against M0208-CGO-N20's 624 / 3.0614
  turnover_ratio: {float}
  band_verdict: "ok | warn | refuse"    # control_shape.band_verdict on the worse axis
  mwr_pct: {float}                      # trial_funding.mwr * 100
  margin_vs_book: {float}               # 13.879 - mwr_pct, signed
  supersedes: ["M0208-CGO-N20-PLC" | ]  # declared only if band-clean
  d17_live_refusals_after: [...]        # hardgate.mis_shaped_controls(conn, "M0208")
  published_sentence_moved: true|false
  new_verdict_text: "{the exact string lab note set, or '' if the phase left it a floor}"
other_chassis_redrawn: [ {method_id, arm_id, ratios, band_verdict}, ... ]   # may be empty
looks_before: 4
looks_after: 4
db_hash_before: "{sha1}"
db_hash_after: "{sha1}"
```

**From Phase 5 (`phase-5-results.md`) — required, in one of two shapes:**

```yaml
# SHAPE A -- phase 4 cleared, phase 5 drew arms
phase: 5
phase_4_verdict: "cleared"
winning_rule: "A | B | C | D"           # the assignment rule phase 4 measured best
branch_key: "G-entry | G-ladder | G-size | G-bottom"   # phase 5's own key for that rule
m0221:
  new_arm_id: "...";  trade_ratio: {f}; turnover_ratio: {f}; band_verdict: "ok|warn|refuse"
  mwr_pct: {f};  margin_vs_book: {f}    # signed; replaces the standing -0.42 range
  supersedes: ["M0221-R50"] | []
m0225: { ...same shape, or "not drawn" with the reason }
m0201: { ...same shape, or "not drawn -- the rule did not close the 0.0059 gap" }
looks_before: 4 ; looks_after: 4 ; db_hash_before: "..." ; db_hash_after: "..."
```

```yaml
# SHAPE B -- phase 4 stopped
phase: 5
phase_4_verdict: "STOP"
measured:
  rule_A: { m0221_turnover_ratio: {f}, m0221_trade_ratio: {f} }
  rule_B: { ... }
  rule_C: { ... }
  rule_D: { ... }
  best_turnover_ratio: {f}              # against the 1.25x bar (<= 0.5563 absolute turnover)
  m0201_gap_closed: true|false
reason: "{one sentence, plain}"
arms_drawn: none
code_written: none
looks_before: 4 ; looks_after: 4
```

**If a results file is absent or partial:** do not block. Re-derive what exists read-only from
`trials ⋈ trial_funding` (Step 2d), write the handover from the database, and say in the
attribution line which numbers came from a results file and which from the database.

---

## Implementation Steps

Order is not advisory. **sweep → notes → handover → insights → stage → commit → push.** Each
reason is stated where it binds.

### Step 0: The environment, set once, used by every command below

**File:** none — the shell preamble every later step assumes.
**Change:** nothing is written. Each `Bash` call is a new shell, so re-paste this block at the top
of every call rather than trusting a variable to survive.

**Code:**

```bash
# --- paths -----------------------------------------------------------------
MAIN=/home/miftah/seer
PY=/home/miftah/seer/engine/.venv/bin/python
SRC=/home/miftah/seer/engine/src
CAP=/tmp/control-draw-remedies
INS=$MAIN/.workflows/plan/control-draw-remedies/insights

# --- lab environment -------------------------------------------------------
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
unset SEER_RESEARCH_TEST_STORE          # I1: the test-window store is never read in this set
DB=$SEER_LAB_DB

mkdir -p "$CAP" "$CAP/analysis" "$INS"

# --- the hash, recorded before and after every `lab` command (I5) ----------
labhash() { git -C "$MAIN" hash-object lab/lab.sqlite; }
```

**Four rules that bind every command in this phase:**

1. **No pipe on a `lab` command (I4).** `grep`, `head` and `tee` own a pipeline's exit status. Every
   `lab` invocation below is written
   `… > "$CAP/NN-name.txt" 2>&1; echo "exit=$?" >> "$CAP/NN-name.txt"` and the capture is read with
   `cat` afterwards. **Never retry a `lab note` or `lab insight` on a non-zero exit without reading
   the journal first** — `insights` carries append-only triggers on `UPDATE` and `DELETE`
   (`store.py`: `insights_no_update`, `insights_no_delete`) and a duplicate append is permanent.
2. **`--dry-run` does not protect a `lab note` or a `lab insight`.** Measured in
   `commands/lab.py`: only `lab test` (line 2089) and `lab gate-probe` (line 3008) read
   `args.dry_run`; `_note` and `_insight` commit inside `with conn:` regardless. The only safe
   rehearsal is a **copy**: `SEER_LAB_DB=$CAP/rehearse.sqlite` over `cp "$DB" "$CAP/rehearse.sqlite"`.
3. **Any `lab` command may migrate `lab.sqlite` on connect, even a read; a
   `sqlite3 "file:…?mode=ro"` query never does (I5).** Every count in this phase is taken with
   `sqlite3 … mode=ro` or `store.connect_readonly`. Hash before and after anyway.
4. **`lab test` is never invoked and `SEER_RESEARCH_TEST_STORE` is never set (I1).** Looks must read
   4 before and 4 after, asserted at Steps 2 and 9.

**Impact:** nothing written.

---

### Step 1: Read what phases 3 and 5 handed over

**File:** `.workflows/plan/control-draw-remedies/phase-{1,3,4,5}-results.md` (read-only)
**Change:** nothing. This is the phase's input, and the first thing that can go wrong is assuming
a number a phase never measured.

**Code:**

```bash
for n in 1 3 4 5; do
  f="$MAIN/.workflows/plan/control-draw-remedies/phase-$n-results.md"
  echo "===== phase-$n-results.md ====="
  if [ -f "$f" ]; then cat "$f"; else echo "MISSING -- phase $n left no results file"; fi
done > "$CAP/01-results-files.txt" 2>&1
cat "$CAP/01-results-files.txt"
```

**Expected exit:** `0` from `cat`. A `MISSING` line is **not** a stop: the database decides which
arms exist (Step 2d), and the handover's attribution line records which numbers came from where.

**Impact:** none. Fill the `Inputs required` slots above from this capture before going on.

---

### Step 2: The read-only state of the lab, before anything is written

**File:** `lab/lab.sqlite` (read-only)
**Change:** nothing. Every number in the handover's *"The lab after this run"* table is re-derived
here and again at Step 9 — not copied from the honest-control handover, which is already stale:
measured at `main` @ `e3aeeff` the lab reads **855 dev trials, 4 looks, 276 methods, 11 amendments,
478 insights, trial ids 1..859, N = 165** against that document's 849 / 275 / 11 / 470 / 853 / 164.

**Code:**

```bash
labhash > "$CAP/02-hash-before.txt"; cat "$CAP/02-hash-before.txt"
# at main @ e3aeeff this reads 607b78cf69c8e4e3a68a1e84c85eedfd1040c754; phases 3 and 5
# will have moved it -- record whatever it is, do not expect that value.

sqlite3 "file:$DB?mode=ro" <<'SQL' > "$CAP/03-counts.tsv" 2>&1
.mode tabs
.headers on
SELECT 'dev_trials'        AS what, count(*) AS n FROM trials WHERE window = 'dev'
UNION ALL SELECT 'test_window_looks', count(*) FROM trials WHERE window = 'test'
UNION ALL SELECT 'methods',           count(*) FROM methods
UNION ALL SELECT 'amendments',        count(*) FROM method_amendments
UNION ALL SELECT 'insights',          count(*) FROM insights
UNION ALL SELECT 'max_insight_id',    max(id)  FROM insights
UNION ALL SELECT 'max_trial_n',       max(n)   FROM trials
UNION ALL SELECT 'trial_rows',        count(*) FROM trials;
SQL
cat "$CAP/03-counts.tsv"
echo "exit=$?"
```

**Assert, and stop if either fails:**
- `test_window_looks` is **4**. If it is not, invariant I1 was broken upstream: stop, write
  nothing, and report. **This is the one condition that halts the phase.**
- `max_trial_n` equals `trial_rows` — trial ids contiguous. If they are not, a rebase replayed a
  stale `lab.sqlite` over the live file (memory `seer-rebase-replays-stale-lab-sqlite`); stop and
  repair before writing anything.

**2b — N, the number the luck gate judges at.** `npolicy.effective_n` counts *methods* since the
2026-10-08 policy move, not trial rows.

```bash
PYTHONPATH=$SRC "$PY" - <<'PYEOF' > "$CAP/04-n.txt" 2>&1
from seer_engine.lab import npolicy, store
conn = store.connect_readonly()
print("dev_method_count", npolicy.dev_method_count(conn))
print("effective_n", npolicy.effective_n(conn))
PYEOF
echo "exit=$?"; cat "$CAP/04-n.txt"; labhash
```

`store.connect_readonly` opens `mode=ro` with no schema and no migration, so the hash printed here
must equal `02-hash-before.txt`. Measured at `e3aeeff`: `dev_method_count 165`,
`NCount(n=165, policy='methods', trial_rows=855, distinct_methods=165, …)`.

**2c — D17 and the hard gate, re-read for the nine.** This is the evidence behind R3. It calls the
gate's own functions read-only; `lab promote` is **not** invoked and no status moves.

```bash
PYTHONPATH=$SRC "$PY" - <<'PYEOF' > "$CAP/05-hardgate.txt" 2>&1
from seer_engine.lab import hardgate, store, control_shape
conn = store.connect_readonly()
nine = ("M0047","M0201","M0202","M0208","M0215","M0221","M0225","M0227","M0243")
geo = hardgate.geometry(conn)
for mid in nine:
    off = hardgate.mis_shaped_controls(conn, mid)
    live = tuple(f.control for f in off) if off else ()
    rec = hardgate.fold_record(conn, mid, geo)
    cand = hardgate.promoted_variant(conn, mid)
    own = hardgate.variant_record(conn, mid, cand, geo) if cand else None
    kin = hardgate.failed_kin(conn, mid) if hasattr(hardgate, "failed_kin") else hardgate.failed_kin(mid)
    try:
        hardgate.check(conn, mid)
        said = "TAKEN: the hard gate would promote this today"
    except store.LabError as exc:
        said = "REFUSED: " + " ".join(str(exc).split())
    print(f"--- {mid}")
    print(f"    D17 live refusals : {live}")
    print(f"    folds (picks)     : {rec.summary()}")
    print(f"    variant           : {cand} -> {own.summary() if own else '-'}")
    print(f"    failed kin        : {kin}")
    print(f"    {said}")
PYEOF
echo "exit=$?"; cat "$CAP/05-hardgate.txt"; labhash
```

**What this capture must show, and what the handover asserts from it (R3):**
- `hardgate.check` **REFUSES all nine**. If any one reads `TAKEN`, the handover says so loudly and
  the phase still writes no promotion — promotion is the owner's call on a separate day (D8).
- The clause order in `hardgate.check` (read at `hardgate.py:1749`) is
  **fold count → fold majority → the promoted variant's own folds → survivorship drawdown → D17 →
  kin**, and `check` raises at the **first** failing clause. So a method that loses the fold
  majority never reaches D17: for **M0201, M0221 and M0225** a live D17 refusal is **inert** — it
  is never the sentence `lab promote` prints, and clearing it changes nothing about any of them.
- **M0208 is the only method of the nine whose operative clause is D17**, and `failed_kin(M0208)`
  returns `('M0002',)` — a method that has already read **test-failed**. The clause immediately
  behind D17 refuses it too.
- **Do not write a sentence that implies a promotion** anywhere in this phase's output (D8).

`hardgate.failed_kin`'s exact spelling is read off the module at run time; the capture is the
point, not the call. If the signature differs, call it the way `hardgate.check` itself does.

**2d — the arms in play, read off `trials`, not off a plan's claim.**

```bash
sqlite3 "file:$DB?mode=ro" <<'SQL' > "$CAP/06-arms.tsv" 2>&1
.mode tabs
.headers on
SELECT t.method_id, t.candidate_id, t.n, t.trades,
       round(t.turnover, 4)         AS turnover,
       round(f.mwr * 100, 4)        AS mwr_pct,
       round(f.spy_tr_mwr * 100, 4) AS spy_tr_pct
FROM trials t LEFT JOIN trial_funding f ON f.trial_n = t.n
WHERE t.window = 'dev'
  AND t.method_id IN ('M0047','M0201','M0202','M0208','M0215','M0221','M0225','M0227','M0243')
ORDER BY t.method_id, t.n;
SQL
cat "$CAP/06-arms.tsv"; echo "exit=$?"

PYTHONPATH=$SRC "$PY" -m seer_engine lab control \
  M0047 M0201 M0202 M0208 M0215 M0221 M0225 M0227 M0243 \
  > "$CAP/07-control.txt" 2>&1
echo "exit=$?" >> "$CAP/07-control.txt"
cat "$CAP/07-control.txt"; labhash > "$CAP/08-hash-post-control.txt"; cat "$CAP/08-hash-post-control.txt"
```

**Expected exit:** `exit=0` in `07-control.txt`. `lab control` is the only command that compares a
recorded column to a recorded column (I8), and it is the authority for every ratio quoted in the
handover. It opens the database through `store.connect`, so it **may** migrate the file; if
`08-hash-post-control.txt` differs from `02-hash-before.txt` while nothing was written, that is the
migration and it is expected — record both hashes and carry on, because this phase commits the
database anyway.

**Impact:** nothing written to the database. Every number the handover needs is now on disk.

---

### Step 3: The sweep — discover every owner-facing sentence this set moved

**File:** `lab/lab.sqlite` (read-only)
**Change:** nothing yet. **This step exists because the previous close-out found FOUR sentences its
six phases had missed, and three of the four lived in `methods.verdict` — which is what the owner
reads first on `/sera`.** The three sentences named in this phase's brief are a floor on what the
sweep must find, never the list.

**3a — dump every verdict and every analysis, for all methods, not just the nine.**

```bash
sqlite3 "file:$DB?mode=ro" -noheader <<'SQL' > "$CAP/10-verdicts.tsv" 2>&1
.mode tabs
SELECT id, status, replace(replace(coalesce(verdict,''), char(10), ' '), char(13), ' ')
FROM methods ORDER BY id;
SQL
wc -l "$CAP/10-verdicts.tsv"

for m in $(sqlite3 "file:$DB?mode=ro" -noheader "SELECT id FROM methods ORDER BY id;"); do
  sqlite3 "file:$DB?mode=ro" -noheader \
    "SELECT coalesce(analysis,'') FROM methods WHERE id='$m';" > "$CAP/analysis/$m.txt"
done
ls "$CAP/analysis" | wc -l
```

**Expected:** one line per method in `10-verdicts.tsv` and one file per method under
`$CAP/analysis/` — **276** of each at `e3aeeff`, more if phases 3 or 5 added a method (they should
not; an amendment costs no method id).

**3b — pass one: the figures this set moved.** Build the term list from Step 1's results files —
every number phase 3 or phase 5 changed — and seed it with the three the brief names.

```bash
cat > "$CAP/terms-figures.txt" <<'TERMS'
at least 4.3
4.3 points
a quarter less
provisional
fairest control
0.4 points
between 0 and 0.4
1.95
0.890
0.89 points
-0.42
0.0059
TERMS
# ADD, before running: every figure phase 3 and phase 5 moved, from Step 1's capture.

grep -n -i -F -f "$CAP/terms-figures.txt" "$CAP/10-verdicts.tsv" > "$CAP/11-hits-verdict.txt"
echo "grep exit=$?" >> "$CAP/11-hits-verdict.txt"
grep -rn -i -F -f "$CAP/terms-figures.txt" "$CAP/analysis/" > "$CAP/12-hits-analysis.txt"
echo "grep exit=$?" >> "$CAP/12-hits-analysis.txt"
cat "$CAP/11-hits-verdict.txt" "$CAP/12-hits-analysis.txt"
```

A `grep` exit of `1` means *no match*, not an error. These greps are not `lab` commands, so a
pipeline here is harmless — but they are still written unpiped so the status is readable.

**3c — pass two: the vocabulary of a control comparison, across all methods.** Pass one only finds
sentences whose figure we already know. Pass two is what catches the ones no phase named.

```bash
cat > "$CAP/terms-vocab.txt" <<'TERMS'
blind draw
blind picks
meaningless book
random picks
same shape
placebo
control arm
the control
paying the same fees
at the same exposure
TERMS

grep -n -i -F -f "$CAP/terms-vocab.txt" "$CAP/10-verdicts.tsv" > "$CAP/13-vocab-verdict.txt"
echo "grep exit=$?" >> "$CAP/13-vocab-verdict.txt"
grep -rn -i -F -f "$CAP/terms-vocab.txt" "$CAP/analysis/" > "$CAP/14-vocab-analysis.txt"
echo "grep exit=$?" >> "$CAP/14-vocab-analysis.txt"
wc -l "$CAP/13-vocab-verdict.txt" "$CAP/14-vocab-analysis.txt"
```

**3d — the review list, written by hand from 3b and 3c.** For each hit, decide one of three things
and record which, with the evidence:

| decision | what it means | what Step 4 does |
|---|---|---|
| **MOVED** | the set measured a new number for this sentence | correct it — verdict and/or a dated analysis section |
| **STANDS** | the sentence is about an arm this set did not re-draw, and is still true | nothing; say so in the handover's *"one that did not move"* |
| **STILL UNMEASURED** | the set tried and stopped (e.g. a phase-4 STOP leaves M0225 with no honest control) | nothing in the database; the handover says it is still unmeasured and why |

```bash
cat > "$CAP/15-review.tsv" <<'REVIEW'
method	where	decision	the sentence as it reads today	what it must read
REVIEW
# one row per hit, filled by hand. `where` is VERDICT or ANALYSIS.
cat "$CAP/15-review.tsv"
```

**Known candidates, as they read at `main` @ `e3aeeff` — a floor on the list, not the list:**

- **M0208, VERDICT.** *"… beat SPY on the deposits (+13.9% vs +7.2% a year) and a meaningless book
  by at least 4.3 points a year - provisional, and a floor rather than a measurement, because even
  the fairest control the lab can draw here still trades a quarter less than the book; the earlier
  figure of 6 points came from a control that traded four times as often and is withdrawn."**
  Phase 3 decides whether this is still a floor. If its new arm is band-clean, the floor language
  comes out and a measured figure goes in; if the arm reads `warn`, the floor **stays** and the
  handover says the shadow moved it from 0.73× to `{ratio}` without reaching the band.
- **M0221, ANALYSIS** (around the paragraph reading *"the fifty biggest by size trail a blind draw
  of their own shape by a small amount that this lab has not pinned down, somewhere around 0.4
  points a year, measured against a control …"*). Phase 5 either pins the number or confirms it
  cannot be pinned. **Note: `methods.analysis` is append-only** — the correction is a **new dated
  section**, never an edit to that paragraph.
- **M0225.** The **−0.890** deficit against `M0225-R50` (0.195× trades / 0.424× turnover) is quoted
  in `docs/plans/HANDOVER_20261019-the-honest-control.md` and is computed from `trials`; at
  `e3aeeff` the sweep finds **no** sentence in M0225's own verdict or analysis that quotes it. **Do
  not invent one.** Record what the sweep actually finds: if M0225 has no honest control after
  phase 5, the handover states that the deficit is still only quotable against a fifth-as-active
  arm and that the lab publishes no owner-facing claim resting on it.
- Anything pass two turns up in a method **outside the nine**. The previous sweep's lesson is that
  these exist.

**Impact:** nothing written. `15-review.tsv` is the input to Step 4 and is quoted in the handover.

---

### Step 4: The notes — correct the sentences, one command at a time

**File:** `lab/lab.sqlite` (write)
**Change:** for each **MOVED** row of `15-review.tsv`, one `lab note`. This is the first write of
the phase.

**What `lab note` does, read off `commands/lab.py:_note` and `store.append_analysis`:**
- `--file F` **appends** a dated section to `methods.analysis`. The record is append-only
  (`methods_analysis_grows`): the old paragraph stays and the new one follows it. `append_analysis`
  refuses a section identical to the newest one, which is the guard against exactly the retry that
  double-appended M0245.
- `--verdict V` **replaces** `methods.verdict` outright. This is the owner's first line on `/sera`.
- Both in one transaction (`with conn:`), and `_note` prints one confirmation line after the commit
  — *"M0208: analysis appended (N characters); verdict set to "…"."* That line is what a capture is
  read for.
- **I12: no ids, no digests, no code in either string.** Not `M0208-CGO-N20-PLC`, not
  `matched-draw-v2`, not `control_draw`. Plain language: *"a meaningless book of the same shape"*,
  *"a blind draw that trades as often as the book does"*.

**4a — write each body to its own file first.** Never inline a multi-paragraph body on a command
line.

```bash
mkdir -p "$CAP/notes"
cat > "$CAP/notes/M0208.txt" <<'NOTE'
### 2026-10-20

{One to three plain-language paragraphs. What changed about the control, what the book's lead
against it now is, and -- if it is still a floor -- that it is still a floor and by how much the
control now misses. No ids, no digests, no code. Say what was withdrawn and what replaces it.}
NOTE
cat "$CAP/notes/M0208.txt"
```

Repeat for every MOVED method. The leading `### 2026-10-20` is the author's own section head and
`append_analysis` treats it as such — write it once and never twice.

**4b — rehearse on a copy, because `--dry-run` does not protect this command.**

```bash
cp "$DB" "$CAP/rehearse.sqlite"
SEER_LAB_DB="$CAP/rehearse.sqlite" PYTHONPATH=$SRC "$PY" -m seer_engine lab note M0208 \
  --file "$CAP/notes/M0208.txt" \
  --verdict "{the exact new verdict string}" \
  > "$CAP/20-rehearse-M0208.txt" 2>&1
echo "exit=$?" >> "$CAP/20-rehearse-M0208.txt"
cat "$CAP/20-rehearse-M0208.txt"
sqlite3 "file:$CAP/rehearse.sqlite?mode=ro" "SELECT verdict FROM methods WHERE id='M0208';"
rm -f "$CAP/rehearse.sqlite"
```

**Expected exit:** `exit=0` and one confirmation line. A non-zero exit here costs nothing — the
copy is thrown away. Fix the body or the verdict and rehearse again.

**4c — the real note, one command per method, no pipe.**

```bash
labhash > "$CAP/21-hash-pre-note.txt"

PYTHONPATH=$SRC "$PY" -m seer_engine lab note M0208 \
  --file "$CAP/notes/M0208.txt" \
  --verdict "{the exact new verdict string}" \
  > "$CAP/22-note-M0208.txt" 2>&1
echo "exit=$?" >> "$CAP/22-note-M0208.txt"
cat "$CAP/22-note-M0208.txt"
```

**Expected exit:** `exit=0`, and the capture's first line reads
`M0208: analysis appended (N characters); verdict set to "…".`

**If the exit is non-zero: do not retry.** Read the journal first — the write may have landed:

```bash
sqlite3 "file:$DB?mode=ro" -noheader \
  "SELECT verdict FROM methods WHERE id='M0208';" > "$CAP/23-check-M0208.txt" 2>&1
sqlite3 "file:$DB?mode=ro" -noheader \
  "SELECT substr(analysis, -600) FROM methods WHERE id='M0208';" >> "$CAP/23-check-M0208.txt" 2>&1
cat "$CAP/23-check-M0208.txt"
```

If the new verdict and the new section are both there, the command succeeded and something after
the commit failed; **do not run it again**. If neither is there, the transaction rolled back and a
retry is safe. If exactly one is there, that is impossible under `with conn:` — stop and report.

Then the same block for M0221, M0225 and any other MOVED method, each as its own command with its
own capture file (`24-note-M0221.txt`, `26-note-M0225.txt`, …).

**Impact:** `methods.verdict` replaced and `methods.analysis` grown for each MOVED method.
`lab/lab.sqlite` is now dirty and `web/data/lab.json` is stale, so
`engine/tests/test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database`
is **expected red** from here until Step 8. **Do not run the test suite between Step 4 and Step 8.**

---

### Step 5: Re-read the corrected text as the owner will see it

**File:** `lab/lab.sqlite` (read-only)
**Change:** nothing. One pass to catch an id, a digest or a bit of code that slipped into a
sentence (I12).

```bash
sqlite3 "file:$DB?mode=ro" -noheader <<'SQL' > "$CAP/30-verdicts-after.tsv" 2>&1
.mode tabs
SELECT id, replace(coalesce(verdict,''), char(10), ' ') FROM methods
WHERE id IN ('M0047','M0201','M0202','M0208','M0215','M0221','M0225','M0227','M0243') ORDER BY id;
SQL
cat "$CAP/30-verdicts-after.tsv"

# I12 tripwire: an id, a digest or a code identifier in owner-facing text.
grep -n -E 'M[0-9]{4}-|[0-9a-f]{12}|matched-draw|control_draw|control_weight|_PLC|\bPLC[0-9]?\b|WARN_BAND|D1[0-9]\b' \
  "$CAP/30-verdicts-after.tsv" > "$CAP/31-i12-verdict.txt"
echo "grep exit=$?" >> "$CAP/31-i12-verdict.txt"
cat "$CAP/31-i12-verdict.txt"

for m in $(cut -f1 "$CAP/15-review.tsv" | tail -n +2 | sort -u); do
  sqlite3 "file:$DB?mode=ro" -noheader \
    "SELECT substr(analysis, -2000) FROM methods WHERE id='$m';" > "$CAP/32-tail-$m.txt" 2>&1
done
grep -n -E 'M[0-9]{4}-|[0-9a-f]{12}|matched-draw|control_draw|control_weight|_PLC|WARN_BAND|D1[0-9]\b' \
  "$CAP"/32-tail-*.txt > "$CAP/33-i12-analysis.txt"
echo "grep exit=$?" >> "$CAP/33-i12-analysis.txt"
cat "$CAP/33-i12-analysis.txt"
```

**Expected:** `grep exit=1` on both tripwires — **no match**. A match is a sentence to rewrite.
Because `methods.verdict` is replaceable, a bad verdict is fixed with a second `lab note --verdict`;
because `methods.analysis` is **not**, a bad analysis section can only be followed by a dated
correction on a later day. Which is the whole reason Step 4b rehearses on a copy.

**Impact:** none.

---

### Step 6: Write the handover

**File:** `docs/plans/HANDOVER_20261020-control-draw-remedies.md` (new)
**Change:** the whole document. It follows the shape of
`docs/plans/HANDOVER_20261019-the-honest-control.md` section for section — that document is the
model, and it is 524 lines, so this one is allowed to be long. Every `{…}` below is a measurement
slot filled from `$CAP`, never from memory and never from a plan file's expectation.

**The skeleton, in full — every heading, every slot:**

````markdown
# Handover — the held-set shadow, the weight vector, and the R1 verdict

**Written:** 2026-10-20 · **Branch:** `main` (no worktree — Decision D1: pre-registration and the
database must be committed on the same branch)
**Method ids spent:** **{none | N}.** {M} new `Amendment` block(s) under existing ids ·
**Next free id:** {unchanged | …}

**The lab after this run**

| | |
|---|---|
| dev trials | **{n}** ({before} + {added}) |
| test-window looks used | **4 — unchanged. None was spent.** |
| methods | **{n} — unchanged.** An amendment appends under an existing id |
| amendments | **{n}** ({before} + {written by this set}) |
| insights | **{n}** ({before} + {journalled here}) |
| N the luck gate judges at (policy: methods) | **{n}** {unchanged, because no method was added} |
| trial ids | 1..{max}, **contiguous** (count {n} = span {n}) |
| `git hash-object lab/lab.sqlite` | {before} → {after} |

*Every count re-derived on 2026-10-20 by a read-only `sqlite3
"file:/home/miftah/seer/lab/lab.sqlite?mode=ro"` query, which never migrates the file, and by
`npolicy.effective_n` through `store.connect_readonly`. {Which `lab` command moved the hash and
why.} Every percentage in this document is `trial_funding.mwr` — the money-weighted return on the
owner's own monthly deposits, what `lab show` prints as "your money earned" — against **{spy}%/yr**
for the same deposits in SPY TR, the recorded `spy_tr_mwr` of every row read. `total_return` and
`cagr` are not quoted anywhere: these books are funded and those columns count the owner's deposits
as gains.*

---

## What this session established

{Three to six paragraphs. The two remedies, what each measured, and the one-line headline. If
phase 4 stopped, the headline says so here and not in a footnote.}

---

## The R1 verdict: two rules on two axes

{This section is R2's deliverable and it is not buried. Three sub-sections, below.}

### R1 as the brief reads it cannot be met — and no further work will make it meetable

Two structural facts, both measured:

1. **Turnover on a weight-varying book is not in name space at all.** `M0221-E50` holds
   `M0221-C50`'s **exact** fifty names and records its **exact** 360 trades, and still turns over
   **{0.7126} against {0.4450} — {1.60}×**. No rule that decides *which names* a control holds can
   reach that, however the entry count is derived. The matched draw is a name rule by construction.
   {Phase 4's FOUR assignment rules (A, B, C, D) and what each measured, as further evidence.}
2. **A weight vector cannot be produced by a shared module.** Each chassis computes its own —
   `m0221.weights` (market value under a 10 % ceiling), `m0047.size_weights` (size under a
   ceiling), `m0201`'s per-company sizing with class splitting. A shared module has no way to
   produce any of them; only the chassis can. Whatever is shared is the **assignment** of a vector
   the chassis hands over, never the vector.

### R1 in the sense `control_draw` already satisfies it is met, and is the most remedy 2 can aim at

`matched_partition` is one shared, tested ordering contract that five chassis each adapt with their
own slot count, sector cap or keep band — and the lab already calls that one rule. {What phase 5
built, or what phase 4's STOP means instead.} By the standard already in force in this module, one
shared contract plus a thin per-chassis adapter **is** one reusable rule.

### So: two rules on two axes. A name rule and a weight rule. Said plainly.

{Two or three sentences in the owner's register. The layout says what the prose says: a name rule
in `control_draw.py`, a weight rule {in `control_weight.py` | that was measured and not built}. A
single module named after one of them would have been a paper-over.}

---

## Remedy 1 — the held-set shadow

**What it was:** {the 0.487× estimate on M0208, in one paragraph.}
**The replay depth K:** {from phase 1} — costing {K × 26} bars against M0208-A1's headroom of 194.

### What the shadow changed, chassis by chassis

| chassis | true entries | v1 estimate | shadow estimate | ratio | verdict | re-drawn? |
|---|---|---|---|---|---|---|
| M0047 | {…} | {…} | {…} | {…} | {shadow is a measured no-op} | no |
| M0201 | … | | | | | |
| M0202 | … | | | | | |
| M0208 | {phase 1's measured true count — see the note below} | {304 — 0.487×} | {…} | {…} | **{shadow needed}** | **yes** |
| M0215 | … | | | | | |
| M0221 | … | | | | | |
| M0225 | … | | | | | |
| M0227 | … | | | | | |
| M0243 | … | | | | | |

**The "624 real entries" figure, and this phase's duty to it (C6).** The honest-control close-out
recorded *"304 estimated entries against the real book's 624"*. `M0208-CGO-N20`'s recorded
`trials.trades` is **also 624**, and an entry count and a trade count are not the same quantity — a
book that takes in `e` names and lets `e` go makes about `2e` basket changes before fills and
resizes. Phase 1's forward replay and phase 3's own anchor both measure the true entry count
directly. **This phase owns the correction.** Read both results files and do one of two things:

- if the measured true count is ~624, write the figure plainly and say it was confirmed;
- if it is ~1248, say in one plain sentence that the earlier figure conflated an entry count with a
  trade count, that **the ratio (0.487×) is unaffected and remains the finding**, and correct it
  here. Then check with Step 3's sweep whether any `methods.verdict` or `methods.analysis` string
  quotes the figure; **at `e3aeeff` the sweep finds none**, so the correction belongs in this
  handover and in an `insight`, and **no `lab note` is warranted for it alone**.

### M0208, re-drawn

| | trades | turnover | ratio | verdict | its own `mwr` | margin |
|---|---|---|---|---|---|---|
| the book `M0208-CGO-N20` | 624 | 3.0614 | — | — | 13.879 | — |
| the arm it was quoted against before | 455 | 2.3130 | 0.729 / 0.756 | warn | 9.532 | +4.346 |
| **the shadow draw** | {…} | {…} | {…} | **{…}** | {…} | **{…}** |

**The bar:** `WARN_BAND` is 0.80–1.25 on **both** axes and `band_verdict` is **inclusive**, so
`0.80 × 624 = 499.2` means the arm needed **≥ 500 trades** (499 reads `warn`) and
**≥ 2.4492 turnover**. On this equal-slot chassis turnover runs at **1.0362×** trades, so the
**high** side binds on turnover: ≤ 1.25 turnover ratio is ≤ 1.2063 trades ratio, i.e. **≤ 752**
trades. **The band-clean window is 500 … 752 trades / 2.4492 … 3.8268 turnover.**
{Whether it got there, and what that means for the published sentence.}

### What happened to the thirteen arms drawn under the old contract

**Nothing.** v1 kept its body byte for byte (I3), every recorded arm kept its allocator id, and
phase 2's golden-vector test now makes an accidental in-place edit go red — which nothing would
have caught before, because a module body is outside `config_digest`.

---

## Remedy 2 — the weight vector

{If phase 4 cleared:} the assignment rule, the arms it earned, the ratios they read, and which
handicapped arms they retired.
{If phase 4 STOPPED — write it as a result, not an apology:}

| rule | what it assigns | M0221 trades × | M0221 turnover × | inside the band? |
|---|---|---|---|---|
| the shipped matched draw | the control's own sizes | 1.031 | **1.951** | no |
| **(A)** the real book's sorted vector, month-keyed order | {…} | {…} | {…} | {…} |
| **(B)** the same vector in the date-free keep order | {…} | {…} | {…} | {…} |
| **(C)** the control's own sizes, ceiling re-shaped | {…} | {…} | {…} | {…} |
| **(D)** keeps first in keep order, entrants last down the sorted vector | {…} | {…} | {…} | {…} |

**The bar was ≤ 0.5563 turnover (1.25×) with trades inside 0.8–1.25×.** {Result.} Four rules were
measured and then the phase stopped, which is what its plan told it to do. **This is a measured
dead end, and it closes leftover 2 with a number instead of carrying it a third time.** {What that
means for M0221 and M0225: the standing readings stay as they are, and why.}

---

## Does the gate take any of the nine? No — and this set never claimed it would

{This section is R3 and it is a hard requirement of the phase.}

| method | D17 refusals still live | what `hardgate.check` says today | the clause that reports it |
|---|---|---|---|
| M0047 | {…} | REFUSED | {…} |
| M0201 | {…} | REFUSED | wins {2} of {4} folds — **raised before D17** |
| M0202 | {…} | REFUSED | {…} |
| M0208 | {…} | REFUSED | **{D17 | kin}** |
| M0215 | {…} | REFUSED | {…} |
| M0221 | {…} | REFUSED | wins {1} of {4} folds — **raised before D17** |
| M0225 | {…} | REFUSED | wins {1} of {4} folds — **raised before D17** |
| M0227 | {…} | REFUSED | {…} |
| M0243 | {…} | REFUSED | {…} |

**`hardgate.check` short-circuits at the first failing clause, in this order: fold count → fold
majority → the promoted variant's own folds → survivorship drawdown → D17 → kin.** So three of the
four live D17 refusals — **M0201, M0221 and M0225** — are **inert**: never the sentence `lab
promote` prints, and clearing one would change nothing about any of them. **M0208 is the only
method of the nine whose operative clause is D17**, and `failed_kin(M0208)` returns `('M0002',)`, a
method that has already read **test-failed** — so the clause immediately behind D17 refuses it too.

**This set bought honest controls. It bought no promotions, and it could not.** Promotion is the
owner's call on a separate day and nothing in this document implies it.

---

## What is withdrawn — every owner-facing sentence this set moved

*Found by sweeping `methods.verdict` **and** `methods.analysis` across all {276} methods, in two
passes: the figures this set moved, then the vocabulary of a control comparison. The previous
close-out's lesson is that a phase-named list is a floor — it missed four, three of them in the
verdict string, which is what the owner reads first.*

### Named by the phases

1. {…}

### Found by the sweep

{…}

### Sentences that stand, and why

{…}

### Still unmeasured, and saying so is the honest answer

{e.g. M0225, if phase 4 stopped: its shortfall against a blind draw of its own shape is still only
quotable against an arm that trades a fifth as often, and no owner-facing sentence rests on it.}

---

## What is now dead, and must not be bought with another method id

- {…}
- {…}

---

## Leftovers, in priority order

### Closed by this set, with a result each

1. **`M0225-C50-PLC` was never drawn** (honest-control leftover 1) — **{closed: … | still open,
   and here is the measured reason}**.
2. **The weight-vector remedy** (leftover 2) — **{closed with a number: …}**.
3. **`control_draw.matched_names` should carry a shadow of the real held set forward**
   (leftover 3) — **{closed: …}**.
4. **Four `lab insight` rows written and not journalled** (leftover 4) — **closed before this set
   began.** Verified read-only: insights **471–474**, added 2026-10-20 — *"An under-trading control
   is a cheaper strategy, not a shape-matched one"*, *"An over-trading control's handicap is
   arbitrary, not a fee drag of known sign"*, *"D17 now supersedes: an honest control retires the
   handicapped one it replaced"*, *"A derived churn beats a hand-chosen re-key period, at both
   poles at once"*. Commit `316c5cc`.
5. **Eight published sentences needed correcting on `/sera`** (leftover 5) — **closed before this
   set began.** Verified by reading `methods.verdict` for the nine: M0201's, M0202's, M0208's and
   M0227's now carry the corrections. Commits `a8c07de` and `ef972c1`.
6. **M0261** (leftover 7) — **closed.** Ran and recorded; commits `7cb6201` and `e3aeeff`.

*(Each of 4, 5 and 6 was **verified read-only at Step 9**, not assumed from the earlier
handover's text.)*

### Carried forward, unchanged

7. **Whether to promote any of the nine.** The gate takes none, and for eight of the nine the
   operative refusal is the walk-forward fold majority, which no amount of control re-drawing
   touches. The owner's call on a separate day. *(was leftover 6)*
8. **The two-month gate rung (`k = 2`), deferred to an `Amendment` under M0260 — free in method
   ids.** *(was leftover 8)*
9. **Insight 457's practical conclusion still stands on the site** ("weight by company size"),
   withdrawn by 462 but, `insights` being append-only, still visible to the owner. *(was 9)*
10. **P2-ENG-N3LB** — `name_count.py`'s docstring still calls the dev trial count "the lab's N",
    which the 2026-10-08 policy move made wrong. *(was 10)*
11. **P3-ENG-V2KQ** — append a dated §7.3 revision to the lab design doc recording the N policy
    move to methods. *(was 11)*
12. **`sim.rules.PRESETS` has no weekly fractional Gotrade preset.** *(was 12)*
13. **The buyback holdability problem** — an 11.4 pt/yr lead that falls 55–85 % is a containment
    problem, not a gate problem. *(was 13)*

### New, from this set

14. **The membership convention is a second, independent defect of the matched draw, and it is NOT
    what R1 asked for.** Every method file that feeds `control_draw` reads **today's** member list
    at the earlier date. Phase 1 priced it on its own — it is exactly the gap between its
    `(b) SHIPPED` column and its `(c) K = 1` column — and measured it at **0.034 on M0047** in
    validation (shipped 0.966 against an exactly-1.000 one-step replay). **No replay depth closes
    it**, because the replay reads the same member list the shipped rule does, which is why phase 2
    was explicitly forbidden from folding it into the shadow and added no `members` argument
    anywhere in the v2 block. Carried here as its own item with phase 1's number attached, sized
    and specific. *(Fill the final number from `phase-1-results.md`'s membership-decomposition
    table, which prices it per chassis.)*
15. {anything else this set found and left — e.g. the `entry_w` diagnostic phase 4 handed over for
    `control_shape`, or widening `labkit.smoke_market` past 473 bars if phase 1's K curve was still
    climbing at K = 8.}

---

## What this close-out did NOT do, and why

- **It promoted nothing and implied no promotion.** {…}
- **It spent no test-window look.** Looks read 4 before and 4 after, asserted. {…}
- **It edited no recorded trial, no recorded `Amendment` block and no closed record.** A re-draw is
  a new arm under a new amendment, and that is what phases 3 and 5 did. {…}
- **It did not re-draw {the chassis the shadow was a measured no-op on}.** A measured no-op is not
  a second rule, and drawing one spends compute to measure nothing (Decision D4).
- **It did not re-draw M0047's honest arms.** They already read 0.99/0.92 and 0.98/0.89 — band-clean
  and superseding; re-drawing retires nothing (Decision D6).
- {Anything else this phase chose not to do.}

---

## Environment notes that save an hour

- **No worktree.** This set was planned and run in the main checkout, `/home/miftah/seer`, on
  `main`. `PY=/home/miftah/seer/engine/.venv/bin/python`,
  `PYTHONPATH=/home/miftah/seer/engine/src`, `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`.
  **Never rebuild a store.**
- **`--dry-run` does not protect a `lab note` or a `lab insight`.** Only `lab test` and
  `lab gate-probe` read `args.dry_run`; `_note` and `_insight` commit inside `with conn:`
  regardless. Rehearse on a copy with `SEER_LAB_DB` instead.
- **A `sqlite3 "file:…?mode=ro"` query never migrates the database; any `lab` command can** — even
  a read. `store.connect_readonly` is the Python equivalent and leaves
  `git hash-object lab/lab.sqlite` unmoved.
- **`hardgate.check` short-circuits at the first failing clause** — fold count → fold majority →
  the promoted variant's own folds → survivorship drawdown → **D17** → kin. A method can carry a
  live D17 refusal that `lab promote` never prints. Read `mis_shaped_controls` directly rather than
  inferring D17's state from the refusal message.
- **`lab stage` targets the checkout that owns the database, and its commit takes no pathspec.** A
  pathspec re-reads the working tree and defeats the staging.
- **`methods.analysis` is append-only and `insights` is append-only; only `methods.verdict` can be
  replaced.** A correction to an analysis is a new dated section. `append_analysis` refuses a
  section identical to the newest one — that guard is the only thing standing between a confused
  retry and a permanent duplicate.
- **The honest-control handover's count table is stale.** It reads 849 / 275 / 11 / 470 / 853 /
  N=164; at `main` @ `e3aeeff`, before this set, the lab read **855 / 276 / 11 / 478 / 859 /
  N=165**. Re-derive, never copy.
````

**Impact:** a new untracked file. Nothing in the database changed at this step.

---

### Step 7: The insights — journalled LAST, one command at a time, exit read directly

**File:** `lab/lab.sqlite` (write), `.workflows/plan/control-draw-remedies/insights/*`
**Change:** 2 to 4 appended `insights` rows. **`insights` carries append-only triggers on `UPDATE`
and `DELETE` (`insights_no_update`, `insights_no_delete`), so a retried append is permanent** — this
is the single most irreversible act in the phase, which is why it is last before the stage.

**7a — check for a near-duplicate before writing anything.** Four rows already journal the
honest-control set's findings (471–474) and four more journal M0261's (475–478).

```bash
sqlite3 "file:$DB?mode=ro" -header \
  "SELECT id, kind, substr(added,1,10) AS added, title FROM insights WHERE id > 460 ORDER BY id;" \
  > "$CAP/40-existing-insights.txt" 2>&1
cat "$CAP/40-existing-insights.txt"

grep -n -i -E 'control|placebo|shape|turnover|weight|draw' "$CAP/40-existing-insights.txt" \
  > "$CAP/41-near-dupes.txt"
echo "grep exit=$?" >> "$CAP/41-near-dupes.txt"
cat "$CAP/41-near-dupes.txt"
```

**If an existing row already says what a planned one would say, do not write it.** A superseding row
is appropriate only when this set *measured something that contradicts it*, and then the body says
which row it supersedes and why.

**7b — write each body to its own file, then a README beside them.** Copy the previous set's
layout exactly: `.workflows/plan/honest-control-redraw/insights/` held four `.txt` bodies plus a
`README.md` giving the one-command-each, never-piped form, and it worked.

```bash
cat > "$INS/R1-two-rules.txt" <<'BODY'
{The R1 finding. Turnover on a weight-varying book is not in name space: identical names,
identical trades, 1.60x. A weight vector cannot come from a shared module because each chassis
computes its own. So a control needs two rules on two axes, and "one reusable rule" was never
available for the weight axis. What a future set should therefore not try to build.}
BODY

cat > "$INS/shadow.txt" <<'BODY'
{The held-set shadow. What a freshly-derived stand-in costs on a keep-band chassis, what carrying
the held set across decisions recovered, and the measured per-chassis table that says where it is
a no-op. The transferable rule.}
BODY

cat > "$INS/weight-vector.txt" <<'BODY'
{The weight vector: the four assignment rules (A, B, C, D), their numbers, and the verdict -- including a STOP
as a result. Why attaching a foreign vector may RAISE turnover (two uncorrelated drifts cross the
1%-of-equity band more often than one tracked drift), and what the measurement showed.}
BODY

# CONDITIONAL -- only if 7a found no near-duplicate already journalled:
cat > "$INS/d17-inert.txt" <<'BODY'
{The gate's clause order: a method can carry a live D17 refusal that `lab promote` never prints,
because the fold majority is tested first. Read mis_shaped_controls directly. Three of four live
refusals were inert, and the fourth stands behind the kin rule.}
BODY

cat > "$INS/README.md" <<'READMEEOF'
# The insights this set journalled, and the exact form that was run

`insights` carries append-only triggers on UPDATE and DELETE. A retried append is permanent.
So: **no pipe**, redirect stdout to a capture file, echo `$?` on its own line, and read the new
row's id back from that file. `_insight` prints the new id and nothing else.
**Never re-run an insight whose capture holds an integer** — if a capture holds an integer *and*
a non-zero exit, read the journal before deciding, because the row went in.

```bash
MAIN=/home/miftah/seer
PY=$MAIN/engine/.venv/bin/python
CAP=/tmp/control-draw-remedies; mkdir -p "$CAP"
export SEER_LAB_DB=$MAIN/lab/lab.sqlite
D=$MAIN/.workflows/plan/control-draw-remedies/insights

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight --kind synthesis \
  --title "{title 1}" \
  --file "$D/R1-two-rules.txt" > "$CAP/50-insight-R1.txt" 2>&1; echo "exit=$?" >> "$CAP/50-insight-R1.txt"

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight --kind observation \
  --title "{title 2}" \
  --file "$D/shadow.txt" > "$CAP/51-insight-shadow.txt" 2>&1; echo "exit=$?" >> "$CAP/51-insight-shadow.txt"

PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab insight --kind observation \
  --title "{title 3}" \
  --file "$D/weight-vector.txt" > "$CAP/52-insight-weight.txt" 2>&1; echo "exit=$?" >> "$CAP/52-insight-weight.txt"

# then verify, and only then stage
sqlite3 "file:$SEER_LAB_DB?mode=ro" "SELECT id, kind, title FROM insights WHERE id > {max_before} ORDER BY id;"
PYTHONPATH=$MAIN/engine/src "$PY" -m seer_engine lab stage
```
READMEEOF
```

**Titles must be what the measurement showed, not what the plan hoped.** The previous set changed
one title at write time for exactly this reason — a pre-registered title its own measurement
refuted is not published as if it held. `--kind` is one of
`observation, hypothesis, data-wish, feature-wish, risk, synthesis` (`store.INSIGHT_KINDS`).
`--method MNNNN` may be passed to attach a row to a method; omit it for a cross-method finding.

**7c — run them, one command per call, exit read directly.**

```bash
labhash > "$CAP/45-hash-pre-insight.txt"
MAXB=$(sqlite3 "file:$DB?mode=ro" -noheader "SELECT max(id) FROM insights;")
echo "max insight id before: $MAXB"

PYTHONPATH=$SRC "$PY" -m seer_engine lab insight --kind synthesis \
  --title "{title 1}" \
  --file "$INS/R1-two-rules.txt" > "$CAP/50-insight-R1.txt" 2>&1
echo "exit=$?" >> "$CAP/50-insight-R1.txt"
cat "$CAP/50-insight-R1.txt"
```

**Expected:** the capture holds **one integer** (the new row's id, `MAXB + 1`) and then `exit=0`.
**If the capture holds an integer and a non-zero exit, the row went in — do not re-run it.** If it
holds no integer and a non-zero exit, read the journal before deciding:

```bash
sqlite3 "file:$DB?mode=ro" -header \
  "SELECT id, kind, title FROM insights WHERE id > $MAXB ORDER BY id;"
```

Then the next insight, in its own `Bash` call, with its own capture file. **Never two in one
command.**

**7d — verify exactly the intended rows landed.**

```bash
sqlite3 "file:$DB?mode=ro" -header \
  "SELECT id, kind, substr(added,1,10) AS added, title FROM insights WHERE id > $MAXB ORDER BY id;" \
  > "$CAP/55-insights-after.txt" 2>&1
cat "$CAP/55-insights-after.txt"
sqlite3 "file:$DB?mode=ro" -noheader \
  "SELECT count(*), count(DISTINCT title) FROM insights WHERE id > $MAXB;"
```

**Expected:** the row count equals the number of commands run, and `count(*) = count(DISTINCT
title)` — no duplicate title.

**Impact:** `insights` grown. Irreversibly.

---

### Step 8: `lab stage` — last, after every note and every insight

**File:** `lab/lab.sqlite`, `web/data/lab.json`
**Change:** `web/data/lab.json` is rewritten as the export of the database, and both files are
`git add`ed, **under an exclusive lock** so a parallel session's half-written transaction can never
be what gets committed (`commands/lab.py:_stage`).

**Why last:** CI runs
`test_the_committed_snapshot_is_the_export_of_the_committed_database`, which compares the committed
snapshot to the committed database row for row. A stage before the final write leaves them
disagreeing. Stage once, at the end.

**Why it targets this checkout:** `_stage` resolves `args.db`, writes the snapshot to
`store.snapshot_path(path)` beside the database's own repo, and `git add`s with `cwd=path.parent`.
`SEER_LAB_DB` points at `/home/miftah/seer/lab/lab.sqlite`, so both files are staged in
`/home/miftah/seer` — the checkout that owns the database (I6, memory
`seer-lab-stage-targets-the-main-checkout`).

```bash
labhash > "$CAP/60-hash-pre-stage.txt"
PYTHONPATH=$SRC "$PY" -m seer_engine lab stage > "$CAP/61-stage.txt" 2>&1
echo "exit=$?" >> "$CAP/61-stage.txt"
cat "$CAP/61-stage.txt"
labhash > "$CAP/62-hash-post-stage.txt"; cat "$CAP/62-hash-post-stage.txt"

git -C "$MAIN" diff --cached --name-only > "$CAP/63-staged.txt" 2>&1
cat "$CAP/63-staged.txt"
```

**Expected exit:** `exit=0`. `63-staged.txt` must contain **exactly** `lab/lab.sqlite` and
`web/data/lab.json` at this point.

**Impact:** both files staged. The index now holds the lab's two files and nothing else.

---

### Step 9: Re-derive the counts, assert the looks, fill the handover's table

**File:** `lab/lab.sqlite` (read-only), the handover (edit)
**Change:** every `{…}` in the handover's *"The lab after this run"* table is replaced with a
number measured **after** every write.

```bash
sqlite3 "file:$DB?mode=ro" <<'SQL' > "$CAP/70-counts-after.tsv" 2>&1
.mode tabs
.headers on
SELECT 'dev_trials'        AS what, count(*) AS n FROM trials WHERE window = 'dev'
UNION ALL SELECT 'test_window_looks', count(*) FROM trials WHERE window = 'test'
UNION ALL SELECT 'methods',           count(*) FROM methods
UNION ALL SELECT 'amendments',        count(*) FROM method_amendments
UNION ALL SELECT 'insights',          count(*) FROM insights
UNION ALL SELECT 'max_trial_n',       max(n)   FROM trials
UNION ALL SELECT 'trial_rows',        count(*) FROM trials;
SQL
cat "$CAP/70-counts-after.tsv"

PYTHONPATH=$SRC "$PY" - <<'PYEOF' > "$CAP/71-n-after.txt" 2>&1
from seer_engine.lab import npolicy, store
conn = store.connect_readonly()
print("effective_n", npolicy.effective_n(conn))
PYEOF
cat "$CAP/71-n-after.txt"

diff "$CAP/03-counts.tsv" "$CAP/70-counts-after.tsv" > "$CAP/72-counts-delta.txt" 2>&1
echo "diff exit=$?" >> "$CAP/72-counts-delta.txt"
cat "$CAP/72-counts-delta.txt"
```

**Assert, and say so in the handover:**
- `test_window_looks` is **4** — the same value Step 2 read. **4 → 4, asserted (I1).**
- `methods` is **unchanged** — an amendment appends under an existing id and costs no method id.
- `insights` grew by exactly the number of commands Step 7c ran.
- `max_trial_n == trial_rows` — still contiguous.

**9b — verify the three leftovers this handover declares closed before the set began.** Do not take
them from the earlier handover's text.

```bash
sqlite3 "file:$DB?mode=ro" -header \
  "SELECT id, substr(added,1,10) AS added, title FROM insights WHERE id BETWEEN 471 AND 474 ORDER BY id;"
sqlite3 "file:$DB?mode=ro" -noheader \
  "SELECT id, substr(verdict,1,160) FROM methods WHERE id IN ('M0201','M0202','M0208','M0227');"
sqlite3 "file:$DB?mode=ro" -noheader \
  "SELECT count(*) FROM trials WHERE method_id = 'M0261';"
git -C "$MAIN" log --oneline -8
```

**Expected:** four insight rows 471–474 added 2026-10-20 (honest-control leftover 4 closed);
M0201/M0202/M0208/M0227's verdicts carrying the corrections (leftover 5 closed); M0261 holding
recorded trials and `e3aeeff` in the log (leftover 7 closed). Anything that does **not** check out
goes back onto the carried-forward list with the evidence.

**9c — fill every `{…}` in the handover.** A remaining `{` in the file is a bug; grep for it:

```bash
grep -n '{' "$MAIN/docs/plans/HANDOVER_20261020-control-draw-remedies.md" > "$CAP/73-slots.txt"
echo "grep exit=$?" >> "$CAP/73-slots.txt"
cat "$CAP/73-slots.txt"
```

**Expected:** `grep exit=1` — no unfilled slot left.

**Impact:** the handover is complete. Nothing written to the database.

---

### Step 10: The results file, the commit, the push

**File:** `.workflows/plan/control-draw-remedies/phase-6-results.md` (new), git
**Change:** one commit on `main` carrying the database, the snapshot, the handover, the insight
bodies and the results file.

**10a — the results file.** Short; the handover is the document.

```bash
cat > "$MAIN/.workflows/plan/control-draw-remedies/phase-6-results.md" <<'RESEOF'
# Phase 6 results — the R1 verdict, the sentences, and the close-out

**The document:** `docs/plans/HANDOVER_20261020-control-draw-remedies.md`

- **Sentences swept:** {n} methods' verdicts and {n} analyses, two passes.
- **Sentences moved:** {list, with where each lived: VERDICT or ANALYSIS}.
- **Sentences that stand:** {list}.
- **Insights journalled:** ids {…}, titles {…}.
- **Looks:** 4 → 4, asserted.
- **`git hash-object lab/lab.sqlite`:** {before} → {after}.
- **The gate:** refuses all nine; three of four live D17 refusals inert; M0208's operative clause
  is D17 and the kin rule stands behind it. **No promotion was made or implied.**
- **Left for the coordinator:** {…}
RESEOF
cat "$MAIN/.workflows/plan/control-draw-remedies/phase-6-results.md"
```

**10b — stage the prose, then commit with NO pathspec.**

```bash
git -C "$MAIN" add -- \
  docs/plans/HANDOVER_20261020-control-draw-remedies.md \
  .workflows/plan/control-draw-remedies/

git -C "$MAIN" diff --cached --name-only > "$CAP/80-staged-final.txt" 2>&1
cat "$CAP/80-staged-final.txt"
git -C "$MAIN" status --porcelain > "$CAP/81-status.txt" 2>&1
cat "$CAP/81-status.txt"
```

**Check `80-staged-final.txt` before committing.** It must hold `lab/lab.sqlite`,
`web/data/lab.json`, the handover, and the files under
`.workflows/plan/control-draw-remedies/` — **and nothing else**. If a foreign path is staged (a
parallel session's work), unstage **only that path**:

```bash
git -C "$MAIN" restore --staged -- "{the foreign path}"   # never lab/lab.sqlite or web/data/lab.json
```

Then the commit. **No pathspec (I6):** `git commit -- <paths>` re-reads the working tree and
defeats `lab stage`'s locked snapshot (memory `seer-lab-stage-commit-needs-the-index`).

```bash
git -C "$MAIN" commit --no-verify -F - <<'MSGEOF' > "$CAP/82-commit.txt" 2>&1
lab: the held-set shadow and the weight vector — two rules on two axes

{One paragraph, plain: what the shadow recovered, what the weight vector measured (including a
STOP as a result), and that the hard gate takes none of the nine. Say that this bought honest
controls and no promotions.}

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSGEOF
echo "exit=$?" >> "$CAP/82-commit.txt"
cat "$CAP/82-commit.txt"
```

Drop `--no-verify` unless a hook is known to re-read the working tree; the previous set's lab
commits (`a8c07de`, `316c5cc`) landed without it.

**Expected exit:** `exit=0`. Commit-message style matches the log: `lab: …` in lower case with an
em dash, as in `lab: M0261 — which month you read the safety gate beats how often you read it`.

**10c — the suite, green, after the stage and the commit.**

```bash
cd "$MAIN" && PYTHONPATH=$SRC engine/.venv/bin/python -m pytest engine/tests \
  > "$CAP/83-pytest.txt" 2>&1
echo "exit=$?" >> "$CAP/83-pytest.txt"
tail -30 "$CAP/83-pytest.txt"
```

**Expected exit:** `exit=0`. The one test this phase can break is
`test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database`, and
Step 8 is what keeps it green. If it is red, `lab stage` did not run last — re-run Step 8 and amend.
DB tests need Postgres; if `PG_TEST_URL` is unset they skip, and CI fails on a skip, so export it:
`export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres` with the container running.

**10d — push.**

```bash
git -C "$MAIN" push origin main > "$CAP/84-push.txt" 2>&1
echo "exit=$?" >> "$CAP/84-push.txt"
cat "$CAP/84-push.txt"
```

**Expected exit:** `exit=0`. **If the push is rejected, do NOT `git pull --rebase`** — a rebase
replays a stale `lab.sqlite` over the live shared file other sessions are writing (memory
`seer-rebase-replays-stale-lab-sqlite`). Fetch, **merge** `origin/main`, re-run `lab stage` so the
snapshot matches the merged database, re-check that trial `n` is still contiguous, commit the
re-stage, and push again.

**Impact:** the set is on `main`.

---

## Verification

**Build:** nothing to build — this phase changes no source. `engine/.venv/bin/ruff check engine`
should still be clean (it was before; nothing here touches it).

**Tests:**
```bash
cd /home/miftah/seer && PYTHONPATH=/home/miftah/seer/engine/src \
  engine/.venv/bin/python -m pytest engine/tests
```
Green, including `test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database`
and `test_every_recorded_configuration_still_digests_to_its_recorded_digest`. Run it only **after**
Step 8; between Step 4 and Step 8 the snapshot test is expected red and running it proves nothing.

**Manual check:**
- `cat $CAP/30-verdicts-after.tsv` — read every corrected verdict aloud as the owner would. No id,
  no digest, no code, no bar name (I12). The I12 tripwires at Step 5 must both read `grep exit=1`.
- `grep -c '{' docs/plans/HANDOVER_20261020-control-draw-remedies.md` — zero unfilled slots.
- The handover contains, in plain words, each of: *the gate takes none of the nine*; *three of the
  four live D17 refusals are inert*; *M0208's operative clause is D17 and the kin rule stands
  behind it*; *this bought honest controls, not promotions*; *two rules on two axes*; *R1 as the
  brief reads it cannot be met and no further work will make it meetable*.
- `git log --oneline -3` shows the `lab: …` commit at the top of `main` and `git status --porcelain`
  is clean apart from anything a parallel session owns.

**Exit criteria:**
1. `docs/plans/HANDOVER_20261020-control-draw-remedies.md` exists on `main`, committed and pushed,
   with every section of Step 6's skeleton present and every measurement slot filled from a capture
   in `$CAP`.
2. The R1 verdict is in it, under its own heading, with both structural reasons and the `E50`
   numbers — and the sentence *two rules on two axes*.
3. R3 is in it, in plain words, with the clause-order table: the gate takes none of the nine, three
   of four live D17 refusals are inert, M0208's is the operative one and the kin rule stands behind
   it. **No sentence anywhere in this phase's output implies a promotion.**
4. Every sentence the sweep marked MOVED is corrected in `methods.verdict` and/or as a dated
   `methods.analysis` section, in plain language with no ids, digests or code.
5. Honest-control leftovers **1, 2 and 3 are each closed with a result** — a STOP counts — and
   leftovers 4, 5 and 7 are recorded as closed **having been verified read-only**, with 6 and
   8..13 carried forward unchanged.
6. The insights are journalled, one command each, no pipe, with the new ids read back from the
   captures; `count(*) = count(DISTINCT title)` over the new rows.
7. `lab stage` ran **last**; `lab/lab.sqlite` and `web/data/lab.json` are committed together by a
   commit that took **no pathspec**; `pytest engine/tests` is green.
8. **Test-window looks read 4 before and 4 after, asserted and stated in the handover.**
   `git hash-object lab/lab.sqlite` is recorded before and after.

---

## Handoffs

- **Anything found in the sweep that belongs to a *method* this set did not touch.** If pass two
  turns up a control-comparison sentence in a method outside the nine whose control this set never
  re-drew, **do not re-draw it here** — that is a trial, and this phase runs none. Record it as a
  new leftover with the method id and the sentence.
- **Promotion of anything (R-none).** Explicitly out of scope and explicitly disclaimed. The owner
  decides on a separate day.
- **The walk-forward fold majority**, the operative refusal for eight of the nine. No control
  re-draw touches it; it is not this set's work and not this phase's sentence to write.
- **`control_weight.py`'s module docstring and tests** — Phase 5 owns them. If phase 5's docstring
  claims "one reusable rule" where this phase's verdict says two, **do not edit the file**: record
  the discrepancy as a leftover for the coordinator.
- **Honest-control leftovers 8–13** are carried forward verbatim. None is work for this phase, and
  a drive-by fix to `name_count.py`'s docstring (leftover 10) would break this phase's own rule
  that it touches no file under `engine/src`.
- **The plan index's Reconciliation Log and the set's `ledger.json`**, if the coordinator keeps one
  — coordinator-owned, as `b0ddc00` and `20513b4` were in the previous set.
- **A `chore(orch)` pruning commit**, if the coordinator wants one. Not this phase's.

---

## Rollback

| what | how to undo it |
|---|---|
| the handover, the results file, the insight bodies | `git rm` them, or `git revert` the commit. Pure prose; nothing depends on them. |
| `methods.verdict` | **Reversible.** A further `lab note --verdict "<the old string>"` restores it. The old string is in `$CAP/10-verdicts.tsv`, taken before any write — **keep that capture**. |
| `methods.analysis` | **Not reversible.** The record is append-only (`methods_analysis_grows`). A wrong section can only be followed by a dated correction on a later day. This is why Step 4b rehearses on a copy. |
| `insights` rows | **Not reversible.** `insights_no_update` and `insights_no_delete` are triggers. A wrong row can only be superseded by a later one that names it. This is why Step 7 is last, one command at a time, exit read directly. |
| `web/data/lab.json` | Regenerated by `lab stage` from whatever the database says. Never edited by hand. |
| the commit | `git revert` restores the prose and the snapshot, but **not** the database rows: `trials`, `insights` and the analysis are append-only by trigger, and that is the point. A revert on `main` would leave `lab.sqlite` disagreeing with `web/data/lab.json` until `lab stage` runs again. |
| the push | Do not force-push `main`. Land a follow-up commit instead. |

**The one thing that cannot be undone and must therefore not be got wrong: an insight row and an
analysis section. Rehearse both on a copy; `--dry-run` does not protect either.**
