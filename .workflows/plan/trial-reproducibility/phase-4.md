# Phase 4: Verify on copies, record the finding, stage the migrated lab

**Plan set:** `TRIAL_REPRODUCIBILITY_PLAN.md`
**Analysis:** `20261009-192826-T7RQ_code_analyzer.md`
**Satisfies:** R3, R4 — the drift on a method curve is re-measured end to end on the finished code
and written down where the owner and the explore loop read it; the 58-trial `5451195fd552`
cohort is marked (annotated by the 152 backfilled provenance rows that `lab stage` commits), not
re-run. Also R1 and R2, their written half: §5.1 asks to "state the options, measure what each
costs, pick, and say why" — the handover note, the runbook and the lab insight are where the
policy (R1) and the warn-or-refuse answer (R2) are stated with their measurements, and Step 6d
keeps the skills from steering a missing store into the refusal R1's pin creates.
**Depends on:** Phase 2, Phase 3 (and Phase 1 through Phase 2)
**Difficulty:** NORMAL
**Package:** docs, `lab/lab.sqlite`, `web/data/lab.json`

---

## Goal

After this phase the committed `lab/lab.sqlite` on the branch is at schema 5 with exactly one
`trial_provenance` row for each of its 152 trials, the lab journal carries one plain-words
observation stating what was measured (M1–M6), `web/data/lab.json` is its export, and the
runbook, the package readme and the handover say what the lab now records and refuses. Every claim
in that text has first been re-measured on scratch copies with the finished code of phases 1–3 —
at today's `INITIAL_IDR`, which this phase never touches.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- one row in `insights` of the committed `lab/lab.sqlite` (kind `observation`, no `method_id`),
  title "Old results stopped matching because the starting amount changed, not the prices";
- 152 `trial_provenance` rows in the committed `lab/lab.sqlite`, written by phase 2's 4→5
  migration when `lab insight` opens it — not by any code of this phase;
- doc text: a new subsection "### Starting capital, price fingerprints and rebuilds" in
  `docs/runbooks/data-pipeline.md`; a new subsection "### lab: per-trial provenance and
  comparability (trial-reproducibility)" plus four smaller edits in `engine/package_readme.md`;
  a dated "Resolved" note under §5.1 of `docs/plans/HANDOVER_20261009.md`; store-acquisition
  guidance in three skills (`.claude/skills/sync-research-store/SKILL.md`,
  `explore-and-experiment-new-method/SKILL.md`, `redo-sera-experiments/SKILL.md`, Step 6d).
**Signature changes:** none. No source file is edited.
**Requires (from earlier phases):**
- `backtest/dev.py` `initial_idr` keyword on `run_registry` (Phase 1).
- `lab/store.py` `SCHEMA_VERSION = "5"`, table `trial_provenance(trial_n, initial_idr,
  price_fingerprint, source, measured)`, migration 4→5 backfill run by `store.connect`, and
  `connect_readonly` accepting a v5 file (Phase 2).
- `runner.recorded_capital`, and `lab remeasure` (dev + seed paths) and `lab costs` re-running at
  the recorded capital (Phase 2).
- `hardgate.trial_deposits` de-funding by recorded capital (Phase 2).
- `hardgate.fold_record` refusing on a price-fingerprint mismatch or unknown; `lab walkforward` /
  `lab regime` warnings; `lab run` refusing a dev store whose price fingerprint differs from the
  benchmark trial's, or is unknown (Phase 3).
- The doc text below names exactly what phases 2 and 3 define (checked by the reconciler against
  their plans): `research.price_fingerprint_of`, `ResearchData.price_fingerprint` (a field,
  `str | None`), `store.ProvenanceRow`, `store.insert_provenance`, `store.provenance_of`,
  `store.P7A_PRICE_FINGERPRINT`, `runner.recorded_capital`, `remeasure.plan_capital`;
  `hardgate.comparability`, `hardgate.mismatches`, `hardgate.benchmark_n`,
  `hardgate.pin_dev_store`, `hardgate.Geometry.bench_n`, decision **(D10)** in
  `lab/hardgate.py`'s module docstring; `commands/lab.py:_comparability_warnings`. **If the
  landed code spells one differently, the docs follow the code** — fix the names in this phase's
  text, never the code.
**Leaves alone (owned by others):** every file under `engine/src/` and `engine/tests/` (Phases
1–3); `trial_moments` on the committed database (out of scope, M6); `INITIAL_IDR`; method
statuses; the test window.

## Files

| File | Action | What changes |
|---|---|---|
| `lab/lab.sqlite` | modify (via `lab insight` + `lab stage` only) | migrated v4→v5 (adds `trial_provenance` + 152 backfill rows), one `observation` insight appended |
| `web/data/lab.json` | modify (via `lab stage` only) | regenerated export: the new insight appears |
| `docs/runbooks/data-pipeline.md` | modify, insert before line 358 (`## Environment and secrets`) | new subsection on store vs price fingerprint, recorded capital, rebuild refused |
| `engine/package_readme.md` | modify: line 4; after line 49; line 1570; after line 1069; before line 2655 | Last Updated; Overview bullet; `INITIAL_IDR` note; `lab costs` note; new provenance/comparability subsection |
| `docs/plans/HANDOVER_20261009.md` | modify, insert after line 143 (the blank line ending §5.1, before `### 5.2` at line 144) | dated "Resolved" note answering §5.1's four questions with the measurements |
| `.claude/skills/sync-research-store/SKILL.md` | modify, append to "## When a rebuild is the right answer instead" | a rebuild that changes prices is refused by `lab run` (D10) |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify, line 49-50 (One run, step 1) | a missing store is pulled, not built |
| `.claude/skills/redo-sera-experiments/SKILL.md` | modify, line 165 | a missing store is pulled first; a build may be refused |

## Implementation Steps

Shell conventions used in every step (copy them into one shell session):

```bash
W=/home/miftah/.worktrees/seer/trial-reproducibility
PY=/home/miftah/seer/engine/.venv/bin/python
STORE=/home/miftah/seer/engine/.research
S=$(mktemp -d)        # scratch; use the session's scratchpad directory instead if it has one
lab() { (cd "$W" && env -u SEER_LAB_DB PYTHONPATH="$W/engine/src" "$PY" -m seer_engine lab "$@"); }
```

`env -u SEER_LAB_DB` matters: a set `SEER_LAB_DB` would point the default `--db` at another
checkout. Every command below also passes `--db` explicitly. The worktree's `lab/lab.sqlite`
(the branch's copy) is the only database this phase writes; `/home/miftah/seer/lab/lab.sqlite`
is never opened.

### Step 1: Preconditions — the tree is phases 1–3, the committed DB is untouched, the store is the expected one
**File:** none (checks only)
**Change:** stop the phase if any check fails.
**Code:**
```bash
cd "$W"
git log --oneline e5eda52..HEAD            # phase 1, 2 and 3 commits present
git status --short -- lab/lab.sqlite web/data/lab.json   # must print nothing
ls "$W"/lab/lab.sqlite-wal "$W"/lab/lab.sqlite-journal 2>/dev/null   # must print nothing
"$PY" - "$W/lab/lab.sqlite" <<'EOF'
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
v = c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
n = c.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
t90 = c.execute("SELECT candidate_id, total_return FROM trials WHERE n = 90").fetchone()
assert v == "4", f"committed DB is at schema {v}; expected the untouched v4"
assert n == 152, n
assert t90 == ("M0011-RAW20-TV14-N21", 6.601965843303558), t90
print("committed DB ok: schema 4, 152 trials, trial #90", t90)
EOF
"$PY" -c 'import json,sys; m=json.load(open(sys.argv[1])); print(m["fingerprint"])' "$STORE/manifest.json"
# must print 399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8
(cd "$W/engine" && PYTHONPATH="$PWD/src" "$PY" -m pytest -q)   # green before anything is written
```
**Impact:** none. If the store fingerprint differs, M1–M4 were measured on a different store:
stop and report to the orchestrator rather than continue.

### Step 2: Migrate a copy and check the backfill is the rule (R4)
**File:** scratch copy `$S/migrate.sqlite`
**Change:** open a copy with the branch's code (which migrates it to v5) and check the 152
provenance rows against M3 and the fingerprint map.
**Code:**
```bash
cp "$W/lab/lab.sqlite" "$S/migrate.sqlite"
lab --db "$S/migrate.sqlite" next-id >/dev/null       # any command: connect() migrates
"$PY" - "$S/migrate.sqlite" <<'EOF'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
assert c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "5"
rows = c.execute(
    "SELECT t.n, t.window, t.store_fingerprint, CAST(p.initial_idr AS INTEGER), "
    "p.price_fingerprint, p.source, f.trial_n IS NOT NULL "
    "FROM trials t LEFT JOIN trial_provenance p ON p.trial_n = t.n "
    "LEFT JOIN trial_funding f ON f.trial_n = t.n ORDER BY t.n").fetchall()
assert len(rows) == 152
P7A = "5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a"
bad = []
for n, win, sfp, cap, pfp, src, funded in rows:
    want_cap = 10_000_000 if funded else 20_000_000
    if sfp[:12] in ("5451195fd552", "e597367bb680", "399d0d254c7a"):
        want_pfp = P7A
    elif sfp[:12] == "56e83810e82e":
        want_pfp = sfp
    else:
        want_pfp = None
    if (cap, pfp, src) != (want_cap, want_pfp, "backfill"):
        bad.append((n, win, sfp[:12], cap, pfp and pfp[:12], src))
assert not bad, bad
print("152 provenance rows; capital and price fingerprint follow the rule:",
      c.execute("SELECT CAST(initial_idr AS INTEGER), COUNT(*) FROM trial_provenance GROUP BY 1").fetchall(),
      c.execute("SELECT substr(price_fingerprint,1,12), COUNT(*) FROM trial_provenance GROUP BY 1").fetchall())
EOF
```
Expected: `[(10000000, 24), (20000000, 128)]` and `[(None, 2), ('5451195fd552', 148), ('56e83810e82e', 2)]`.
**Impact:** none on the committed database.

### Step 3: Re-run the recorded trials at today's `INITIAL_IDR` (R3, R4)
**File:** three fresh scratch copies.
**Change:** each `lab remeasure` writes `trial_moments` — on its own copy only.
**Code:**
```bash
(cd "$W" && PYTHONPATH="$W/engine/src" "$PY" -c 'from seer_engine.backtest.runner import INITIAL_IDR; print(INITIAL_IDR)')
# must print 10000000 -- today's default, untouched
for M in M0011 M0007 H-P7A; do
  cp "$W/lab/lab.sqlite" "$S/remeasure-$M.sqlite"
  lab --db "$S/remeasure-$M.sqlite" remeasure "$M" --store "$STORE" | tee "$S/remeasure-$M.txt"
  echo "$M exit ${PIPESTATUS[0]}"                    # each must be 0
done
```
Expected: `M0011 exit 0`, `M0007 exit 0`, `H-P7A exit 0`; the H-P7A report says all 54 seed trials
reproduced (six metrics within `METRIC_TOL`, trades exact). Any non-zero exit: stop the phase,
attach the report to the orchestrator — the insight below would then be false.

**Informational (does not gate the phase):** the four non-seed trials of the `5451195fd552`
cohort are M0001's (#55–#58), which M4 did not cover.
```bash
cp "$W/lab/lab.sqlite" "$S/remeasure-M0001.sqlite"
lab --db "$S/remeasure-M0001.sqlite" remeasure M0001 --store "$STORE" | tee "$S/remeasure-M0001.txt"; echo "M0001 exit ${PIPESTATUS[0]}"
```
Record which of the two sentences in Step 8 applies.
**Impact:** none on the committed database.

### Step 4: `lab costs` flat column equals trial #90 (R3)
**File:** scratch copy `$S/costs.sqlite`
**Change:** the flag is `--candidate` (`commands/lab.py:255`). `lab costs` appends an insight —
on the copy.
**Code:**
```bash
cp "$W/lab/lab.sqlite" "$S/costs.sqlite"
lab --db "$S/costs.sqlite" costs M0011 --candidate M0011-RAW20-TV14-N21 --store "$STORE" | tee "$S/costs.txt"
grep -E '^  total return +\+660\.2% ' "$S/costs.txt"
grep -F 'recorded dev trial #90 (flat): total return +660.2%; the flat re-run reproduces it' "$S/costs.txt"
```
Both greps must match. `reproduces it` is `real_costs.Comparison.reproduced` at `REPRO_TOL = 1e-9`
relative against `6.601965843303558`, which is the exact check; the `+660.2%` is its printout.
**Impact:** none on the committed database.

### Step 5: `lab status` unchanged against the base commit (Invariant 5)
**File:** two scratch copies; base code extracted from `e5eda52`.
**Code:**
```bash
mkdir -p "$S/base" && git -C "$W" archive e5eda52 engine/src | tar -x -C "$S/base"
cp "$W/lab/lab.sqlite" "$S/status-base.sqlite"; cp "$W/lab/lab.sqlite" "$S/status-new.sqlite"
(cd "$S/base" && env -u SEER_LAB_DB PYTHONPATH="$S/base/engine/src" "$PY" -m seer_engine lab --db "$S/status-base.sqlite" status) > "$S/status-base.txt"
lab --db "$S/status-new.sqlite" status > "$S/status-new.txt"
diff "$S/status-base.txt" "$S/status-new.txt" && echo "status identical"
grep -A1 'Promotable now' "$S/status-new.txt"      # next line: "    (none)"
```
Expected: `status identical`. If the diff is non-empty, every differing line must be a line the
plan set deliberately added (none is planned). A changed refusal reason on any of the seven
dev-eligible methods breaks Invariant 5: stop and report.
**Impact:** none on the committed database.

### Step 6: Write the docs
**Files and exact text:** see Steps 6a–6d (three docs, three skills). Pure markdown; no source file.

#### Step 6a: `docs/runbooks/data-pipeline.md` — insert before line 358 (`## Environment and secrets`)
Insert after the line `Without \`PG_TEST_URL\` the DB tests are skipped with a reason.` and its
following blank line, so the new block is followed by one blank line and then
`## Environment and secrets`:

```markdown
### Starting capital, price fingerprints and rebuilds

The lab's 152 trials carry three different `trials.store_fingerprint` values, and on 2026-10-09
that looked like three different stores. **It is not.** `research.fingerprint_of` hashes the whole
`files` map of `manifest.json`, so adding or refreshing `fundamentals.csv` moves the fingerprint
without moving a single bar. MEASURED 2026-10-09: the fingerprint of the current store's four
price files alone (`bars.csv`, `dividends.csv`, `fx.csv`, `unserved.csv`, `fundamentals.csv` left
out) is `5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a` — exactly the P7a
store's. `e597367b…` added the 2015-only panel and `399d0d25…` rebuilt the panel from 2009 with
`--refresh-fundamentals`, which copies the price files byte for byte. **The dev store's prices
have never changed.**

So the lab keeps two fingerprints and they answer different questions:

| | what it hashes | what it is for |
|---|---|---|
| store fingerprint (`trials.store_fingerprint`, `ResearchData.fingerprint`) | every file in the manifest, panel included | re-running a method that reads the fundamentals panel: only the same store fingerprint reproduces it |
| price fingerprint (`trial_provenance.price_fingerprint`, `ResearchData.price_fingerprint`, `research.price_fingerprint_of`) | the four price files only | comparing recorded curves: two curves are comparable when their price fingerprints are equal |

**Starting capital is recorded per trial.** What actually broke reproduction was not the store but
`backtest.runner.INITIAL_IDR`, which `d79fc83` moved from 20,000,000 to 10,000,000 IDR on
2026-10-08. Whole-share lot rounding makes capital a result-moving input, and before schema 5
nothing recorded it — a curve is normalised to opening cash. `lab/lab.sqlite` schema 5 adds the
append-only `trial_provenance` table: one row per trial with `initial_idr` and
`price_fingerprint`. New trials write it in the same transaction as the trial
(`source = 'recorded'`); the 152 trials that existed at migration were back-filled
(`source = 'backfill'`) by a rule that is exact on all of them, checked against git ancestry of
`d79fc83`: a lump-sum trial ran at 20,000,000, a funded trial (one with a `trial_funding` row) at
10,000,000. The price fingerprint was back-filled as `5451195f…` for all 148 dev trials, as
itself for the two test trials on `56e83810…`, and as unknown (NULL) for the two on `bbe7abfb…`,
whose file map is not on this machine. `lab remeasure` and `lab costs` re-run a recorded trial at
its recorded capital; `INITIAL_IDR` is only the default for a **new** run.

**A rebuild is refused by `lab run`.** `build_store` re-downloads every bar, and yfinance answers
differently from one day to the next, so a rebuilt store gets a new price fingerprint. `lab run`
compares the loaded store's price fingerprint with the one recorded for the `REF-SPY-HOLD`
benchmark trial and refuses, before any backtest, when they differ or when the store names no
price fingerprint (`hardgate.pin_dev_store`; the rule is decision D10 in `lab/hardgate.py`) — a
trial recorded on a rebuilt store could not be compared with the benchmark, and the hard gate
would refuse it anyway. There is no flag to run anyway. To move machines, **copy** the store (`.claude/skills/sync-research-store/`),
which keeps both fingerprints. A fundamentals-only refresh (`--refresh-fundamentals`) changes the
store fingerprint and leaves the price fingerprint alone, so `lab run` still accepts it.

**What the gate and the reports do with it.** The hard gate refuses (`lab promote` exits 2) when
the benchmark's price fingerprint and any of the method's dev trials' price fingerprints differ or
are unknown; it fails closed and has no override. `lab walkforward` and `lab regime` only report,
so they print a warning line for such a method instead. MEASURED 2026-10-09: the rule strands 0
trials and changes 0 verdicts on the committed lab, because every dev trial shares one price
fingerprint; refusing on `store_fingerprint` instead would have closed every promotion path.
```

#### Step 6b: `engine/package_readme.md` — five edits

**(i) Line 4** — replace the whole line (it begins `**Last Updated**: 2026-10-08 (lab-realistic-gate, R2 (P1-ENG-FND7)`) with:

```markdown
**Last Updated**: 2026-10-09 (trial-reproducibility: every trial records its starting capital and its price fingerprint in the append-only `trial_provenance` table (schema 5, 152 trials back-filled by an exact rule); `lab remeasure` and `lab costs` re-run a recorded trial at its recorded capital and `hardgate.trial_deposits` de-funds by it; the hard gate refuses a comparison across price fingerprints, `lab walkforward` / `lab regime` warn, and `lab run` refuses a rebuilt dev store. Before that, lab-realistic-gate R2 (P1-ENG-FND7): `lab run` and `lab test` run every candidate on the owner's real funding and record a `trial_funding` row per funded trial)
```

**(ii) After line 49** (the Overview bullet beginning `- The search is run on the owner's real money`) insert one new bullet line:

```markdown
- Recorded trials reproduce, and the gate compares like with like (trial-reproducibility): the lab could not re-run its own record — `lab costs M0011` read +545.3% where trial #90 records +660.2%, and the 152 trials carried three store fingerprints. Measured, the store never moved its prices (the three fingerprints differ only in `fundamentals.csv`); what moved was `INITIAL_IDR`, 20,000,000 -> 10,000,000 in `d79fc83`, which no trial recorded and which whole-share rounding makes result-moving. `lab/store.py` schema 5 adds the append-only `trial_provenance` table (`initial_idr`, `price_fingerprint`, `source` `'recorded'`/`'backfill'`), written by `lab run` / `lab test` in the trial's own transaction and back-filled for every older trial (lump-sum -> 20M, funded -> 10M, exact on all 152); `research.price_fingerprint_of` hashes the four price files only. Every re-run of a recorded trial runs at `runner.recorded_capital`, which is how `lab remeasure M0007`, `M0011` and all 54 `H-P7A` seed trials reproduce exactly on today's store with `INITIAL_IDR` unchanged. Comparability is keyed on the price fingerprint, not the store fingerprint: `hardgate.fold_record` refuses a mismatch or an unknown, `lab walkforward` / `lab regime` warn, and `lab run` refuses a dev store whose price fingerprint is not the benchmark's. It strands 0 trials and changes 0 verdicts today. Recovered `trial_moments` were deliberately not written to the committed lab (they would move `H-P7A-F9` and two DSRs; that judgement belongs to the explore loop)
```

**(iii) Line 1570** — the `backtest.runner` bullet ends `... and a 20M lump would price a cheaper world than the owner\n  lives in.` Replace `  lives in.` (line 1570) with:

```markdown
  lives in. Because it changed once, it is not the capital of a recorded trial: a trial's capital
  is its `trial_provenance.initial_idr`, and every path that re-runs or de-funds a recorded trial
  reads that (`lab.runner.recorded_capital`). `INITIAL_IDR` is only the default for a new run.
```

**(iv) After line 1069** (the `lab costs` bullet ending `... the flat/Gotrade comparison stays a comparison of one variant at two fee models and nothing\n  else.`) — insert a new bullet line immediately after line 1069 (`  else.`), before the bullet `- Writes no \`trials\` or \`trial_moments\` row ...`:

```markdown
- Since trial-reproducibility it also runs at the trial's **recorded capital**
  (`runner.recorded_capital`), not the live `INITIAL_IDR`. Measured 2026-10-09: the +545.3% that
  `lab costs M0011` printed against trial #90's +660.2% was the flat re-run starting at 10M where
  the trial started at 20M; at the recorded capital the flat column reads +660.2% and the report
  says the re-run reproduces it.
```

**(v) Before line 2655** (`### lab: the N policy for the luck gate (lab-luck-gate phase 1)`) — insert this subsection, with one blank line before the existing heading:

```markdown
### lab: per-trial provenance and comparability (trial-reproducibility)

Two inputs make a re-run of a recorded trial the same measurement and no `trials` column carries
them: the **starting capital** and the **price data**. Both are now recorded, once per trial, in an
added table — `trials` itself is still append-only and was not touched.

- **`trial_provenance`** (`lab/store.py`, schema 5): `trial_n` (primary key, foreign key to
  `trials.n`), `initial_idr` (TEXT, NOT NULL), `price_fingerprint` (TEXT, NULL = unknown),
  `source` (`'recorded'` | `'backfill'`), `measured`. Held append-only by
  `trial_provenance_no_update` and `trial_provenance_no_delete`, the `trial_funding` precedent.
  Surface: `store.ProvenanceRow`, `store.insert_provenance()`, `store.provenance_of()`.
- **Written in the trial's own transaction.** `runner.run_method` and `runner.run_test` insert a
  `source='recorded'` row beside every trial inside the same `BEGIN IMMEDIATE`, with the capital
  the run was actually given (passed to `dev.run_registry(initial_idr=...)` explicitly) and
  `ResearchData.price_fingerprint`. `lab.seed` writes a `source='backfill'` row for each of the 54
  seed trials of a fresh database (20,000,000 IDR, the P7a price fingerprint): P7a ran before the
  lab, so those are a stated fact about that run, not something the run wrote.
- **Back-filled by migration 4 -> 5**, `source='backfill'`, for every trial without a row. Capital
  by a rule that is exact on all 152 trials of the committed lab — checked with
  `git merge-base --is-ancestor d79fc83 <git_sha>` over its 26 distinct shas: no `trial_funding`
  row (trials #1..#128, all before `d79fc83`) -> 20,000,000; a `trial_funding` row (#129..#152,
  all after) -> 10,000,000. Price fingerprint by the known map: `5451195f…`, `e597367b…` and
  `399d0d25…` -> `5451195f…` (proven: the current store's four price files hash to it); the test
  store `56e83810…` -> itself; anything else (the test store `bbe7abfb…`, whose file map is not
  on this machine) -> NULL.
- **`research.price_fingerprint_of(files)`** is `fingerprint_of` over the price files only
  (`bars.csv`, `dividends.csv`, `fx.csv`, `unserved.csv`), and `ResearchData.price_fingerprint` is
  it for a loaded store. The whole-store `fingerprint` still moves when `fundamentals.csv` is added
  or refreshed; the price fingerprint does not. Use the store fingerprint to reproduce a method
  that reads the fundamentals panel, the price fingerprint to compare recorded curves.
- **`runner.recorded_capital(conn, n) -> Decimal`**, beside `recorded_contributions`. It raises
  `store.LabError` for a trial with no provenance row rather than guess. `lab remeasure` (dev and
  seed paths) and `lab costs` pass it to `dev.run_registry(initial_idr=...)`; `lab remeasure`
  refuses, before loading any store, a set of trials recorded at two different capitals
  (`remeasure.plan_capital`: one `run_registry` call runs one capital);
  `hardgate.trial_deposits` divides a deposit by it, not by the live `INITIAL_IDR`, so the next
  change to that constant cannot silently mis-de-fund every funded trial the gate reads.
- **The comparability rule** — decision **(D10)** in `lab/hardgate.py`'s module docstring.
  `hardgate.fold_record` — hence `check`, `fold_summary` and `summary` — refuses with
  `store.LabError` when the `REF-SPY-HOLD` benchmark trial's price fingerprint (the row
  `hardgate.benchmark_n` names and `Geometry.bench_n` carries), or any of the method's dev
  trials', is unknown or differs from the benchmark's. Fail closed, no override. The check itself
  is `hardgate.mismatches(conn, bench_n, rows)`, one sentence per incomparable trial;
  `hardgate.comparability(conn, method_id, geo)` is that check over exactly the rows the gate
  scores. The report-only commands reuse `mismatches` through
  `commands/lab.py:_comparability_warnings`: `lab walkforward` and `lab regime` print one
  `WARNING` line per such method and carry on. `lab run` calls `hardgate.pin_dev_store` and
  refuses, before any backtest, a dev store whose price fingerprint differs from the benchmark
  trial's or is unknown (the benchmark comparison is skipped only on a database with no benchmark
  trial, which the gate refuses anyway). The key is deliberately **not**
  `trials.store_fingerprint`: keyed on it, the rule would have refused every promotion, because the
  benchmark was recorded on `5451195f…` and every M-method on `399d0d25…` or `e597367b…` with the
  same prices.
- **What it cost, measured 2026-10-09 on the committed lab.** 0 trials stranded, 0 verdicts
  changed, `lab status` byte-identical (`Promotable now: (none)`); `lab remeasure M0007`, `M0011`
  and `H-P7A` (54 of 54, six metrics within `METRIC_TOL`, trades exact) reproduce on today's store
  with `INITIAL_IDR` at 10,000,000. At 10M without the recorded capital the same 54 all diverged.
- **Deliberately not done.** The moments those re-runs recover were not written to the committed
  lab. With them, `H-P7A-F9` becomes re-evaluable (`rejected` -> `dev-eligible` through
  `lab reevaluate`) and `M0007-N20-RAW` reads DSR 0.978 (from 0.952), `M0011-RAW20-TV14-N21`
  0.973 (from 0.943). No status moves by itself; the judgement is the explore loop's (insight of
  2026-10-09, "Old results stopped matching because the starting amount changed, not the prices").
```

#### Step 6c: `docs/plans/HANDOVER_20261009.md` — insert after line 143
At `e5eda52`, line 141 begins `**Hard constraints.**`, line 142 is `and \`test-passed\` are final; \`TRANSITIONS\` has no edge out of either. Do not invent one.`,
line 143 is blank, line 144 is `### 5.2 ...`. Insert after line 143 (so the note sits between that
blank line and `### 5.2`, followed by one blank line). Anchor on the text, not the number:

```markdown
**Resolved 2026-10-09 (`TRIAL_REPRODUCIBILITY_PLAN.md`, analysis `20261009-192826-T7RQ_code_analyzer.md`).**
The premise turned out to be wrong, and measuring it is what answered the four questions.

- **The store never drifted.** The three fingerprints differ only in `fundamentals.csv`: the
  current store's four price files hash to exactly `5451195fd552…`. What moved was
  `INITIAL_IDR`, 20M -> 10M in `d79fc83` on 2026-10-08, which no trial recorded. The +545.3% vs
  +660.2% of `lab costs M0011` was the re-run starting at 10M against a trial that started at
  20M; re-run at its recorded capital the flat column reads +660.2% and reproduces trial #90.
- **Q1, the policy.** Measured cost of each: (a) pin the store — strands 0, adopted as `lab run`
  refusing a dev store whose *price* fingerprint is not the benchmark's; (b) re-run the benchmark
  — strands 0 but is unnecessary, `REF-SPY-HOLD` reproduces at its own capital; (c) refuse across
  `store_fingerprint` — would close every promotion path, rejected as the wrong key; (c′) refuse
  across *price* fingerprint — strands 0, adopted in the hard gate, fail closed, no override;
  (d) record enough to re-derive — strands 0, adopted: the missing input was capital, now in the
  append-only `trial_provenance` table with the price fingerprint.
- **Q2, is `trials.store_fingerprint` enough?** No — it over-reports: every price-only method looks
  drifted when only the fundamentals panel changed. The comparability key is the price
  fingerprint. `hardgate` **refuses** on a mismatch or an unknown; `lab walkforward` and
  `lab regime`, which only report, **warn**.
- **Q3, how far does it reach on a method curve?** Nowhere, once capital is honoured. At 10M all 54
  `H-P7A` seed trials diverged (e.g. `F9-SPY200M70-MOM30` 8.786 recorded vs 8.032, 17 fewer
  trades); at their recorded 20M all 54 reproduce within `METRIC_TOL`, trades exact, and so do
  every variant of M0007 and M0011. The "+1.83% higher" benchmark figure above was not store
  drift: the benchmark reproduces bit-for-bit within the 6-dp CSV it was imported from.
- **Q4, the 58-trial `5451195fd552` cohort.** No re-run needed: its 54 seed trials reproduce at
  their recorded capital (Q3). It is marked by annotation, not by rewriting: the schema-5
  migration gave every one of the lab's 152 trials one back-filled `trial_provenance` row
  (capital by the exact rule lump-sum -> 20M, funded -> 10M; price fingerprint `5451195f…` for
  all 148 dev trials), and `trials` was not touched.
- **Left on purpose:** the `trial_moments` those re-runs recover were not written. They would make
  `H-P7A-F9` re-evaluable and lift `M0007-N20-RAW`'s DSR 0.952 -> 0.978 and
  `M0011-RAW20-TV14-N21`'s 0.943 -> 0.973. That is a verdict-level call for the explore loop; the
  lab insight of the same date says so in plain words.
```

**M0001 sentence (Step 3's informational check)** — append exactly one of these to the end of
the Q4 bullet's last sentence (after `and \`trials\` was not touched.`):
- exit 0: ` M0001's four trials in the cohort (#55..#58) reproduce too.`
- non-zero: ` M0001's four trials in the cohort (#55..#58) were re-run and did not reproduce; the report is in the phase-4 session notes and nothing was concluded from them.`

**Impact:** docs only.

#### Step 6d: the skills stop steering a missing store into the pin

Phase 3's `lab run` refuses a dev store whose prices are not the benchmark's. Three skills tell an
unattended session to **build** a missing store, which re-fetches prices and can be refused — the
explore loop would then stop on a refusal its own instructions walked it into. Pure markdown; the
refusal message itself already names the sync skill, so these edits only make the first try the
right one.

**(i) `.claude/skills/sync-research-store/SKILL.md`** — append one paragraph at the end of the
section `## When a rebuild is the right answer instead` — it is the last section of the file, so
append after its last line (`machine followed by a \`push\`, not a \`pull\`.`), separated by one
blank line:

```markdown
**A rebuild that changes prices is refused by `lab run`** (trial-reproducibility, decision D10 in
`lab/hardgate.py`). `lab run` compares the store's *price* fingerprint — the four price files,
`fundamentals.csv` left out — with the one the lab's `REF-SPY-HOLD` benchmark trial recorded, and
refuses before any backtest when they differ. A fundamentals-only refresh
(`--refresh-fundamentals`) leaves the price files alone, so it is safe to push; a full rebuild
re-fetches prices and is not a way to bring newer data into the lab. Moving the lab's prices is a
change argued in git (a new benchmark trial and an edit to D10), not a store push.
```

**(ii) `.claude/skills/explore-and-experiment-new-method/SKILL.md`** — in `## One run`, step 1,
replace

```markdown
   only your own paths. Pull. If `engine/.research/` is missing, build it
   (`python -m seer_engine research_store`, a few minutes).
```

with

```markdown
   only your own paths. Pull. If `engine/.research/` is missing, pull it with
   `/sync-research-store` rather than building it: `lab run` refuses a dev store whose prices are
   not the ones the lab's benchmark was measured on (D10 in `lab/hardgate.py`), and a fresh build
   re-fetches prices. Build (`python -m seer_engine research_store`) only when no copy exists
   anywhere; a refused build records nothing and spends no method id.
```

**(iii) `.claude/skills/redo-sera-experiments/SKILL.md`** — replace the first sentence of the
paragraph at line 165,

```markdown
If `$STORE` is missing, build it (`$PY -m seer_engine research_store`, a few minutes) or pull it with
`/sync-research-store`.
```

with

```markdown
If `$STORE` is missing, pull it with `/sync-research-store`; build it (`$PY -m seer_engine
research_store`) only when no copy exists, because `lab run` refuses a store whose prices are not
the lab benchmark's (D10 in `lab/hardgate.py`).
```

(the rest of that paragraph, from "Never point `--store` into a worktree", is unchanged).

**Impact:** docs only. `calculate-assets` builds a **test**-window store, which nothing pins; it
is left alone.

### Step 7: Check no Sera / orchestration session owns the database right now
**File:** none
**Code:**
```bash
tmux list-windows -a -F '#{session_name}:#{window_name}' 2>/dev/null | grep -E '(^|:)(sera|orch)-' && echo "BUSY" || echo "clear"
```
**Change:** if it prints `BUSY`, do **not** write the database: Sera commits `lab/lab.sqlite` and
pushes `main` after every child. Wait until the window closes (re-check every few minutes, e.g.
with a Monitor until-loop) or report to the orchestrator and stop. Do not race it. (One exception: a window that is this plan set's own coordinator — named for
`trial-reproducibility` — does not write `lab/lab.sqlite`; say so in the report and continue. Any
other `sera-*` / `orch-*` window means wait or stop.)
**Impact:** none.

### Step 8: Append the observation to the committed database, then stage
**File:** `$W/lab/lab.sqlite` (the branch's copy), `$W/web/data/lab.json`
**Change:** `lab insight` opens the database with `store.connect`, which runs phase 2's 4→5
migration (the 152 backfill rows) and then appends the insight. `lab stage` regenerates the
snapshot and `git add`s both files under the write lock. Nothing else is run on this database: no
`remeasure`, `costs`, `reevaluate`, `promote`, `test`, `run` or `seed`.
**Code:**
```bash
cat > "$S/insight-body.md" <<'EOF'
On 9 October the lab looked as if its own records could not be trusted. Re-running one recorded method gave a 545% return where the record said 660%, and the lab's 152 results had been saved against three different versions of the price history -- including the market yardstick every method is judged against. Before changing anything we measured what had actually moved.

**The price history never changed.** The three versions differ only in the separate file of company accounts (earnings and balance sheets), which was added on 5 October and widened the same day. Leave that file out and all three are the same price history to the last byte. Every method that trades on prices alone, and the market yardstick, has been tested on one unchanging history since 4 October.

**What changed was the starting amount.** On 8 October the simulated account's opening sum moved from 20 million rupiah to 10 million, to match the owner's real account. Nothing recorded which sum each result had started from, and because the simulation buys whole shares, a smaller account buys a different number of shares and ends somewhere else. That alone explains 545% against 660%: the re-run started with 10 million, the record with 20 million. The rule turned out to be exact for all 152 results: every result that started with one lump of money began at 20 million, and every result fed the monthly top-up began at 10 million.

**Re-run from their own starting sum, the old results match exactly.** All 54 of the original results from 4 October, the market yardstick among them, come out the same as their records to the sixth decimal with the same number of trades, on today's data, with today's 10 million default left alone. Started at 10 million, all 54 came out different; started at their own 20 million, none did. Every variant of M0007 and of M0011 matches too, and the 660% re-run now reads 660%. The earlier note that the yardstick "ends 1.83% higher" on today's data was not a change in the data: the yardstick reproduces once it starts from its own sum.

**So how far did the drift reach on a method, not just on the market?** Nowhere. Once the starting amount is honoured, nothing in the record moved, and none of today's verdicts changes.

**What each way of fixing it would have cost.** Freezing the price history and treating a rebuild as a deliberate event strands nothing. Re-running the yardstick strands nothing, but is unnecessary because it already reproduces. Refusing to compare any two results saved under different version labels would have closed every road to promotion, because the yardstick carries the 4 October label and every newer method a later one, though the prices are identical. Refusing only when the prices themselves differ strands nothing today. Recording enough to re-run each result strands nothing, and needed exactly one number the lab had never kept: the starting amount.

**What the lab does now.** Every result, old and new, carries its starting amount and a label for the price history alone, with the company accounts left out. The 152 existing results were filled in from the rule above and marked as filled in; not one recorded result was changed. Every re-run of a recorded result starts from its own sum. The go-ahead check refuses to compare a method with the market yardstick unless both ran on the same price history, and refuses when it cannot tell; the two report-only readouts warn instead of refusing. A new run on a rebuilt price history is refused before it starts. No method can be promoted today, before or after.

**One thing left undone on purpose.** Re-running the old results also recovers the inputs the luck test needs, which the oldest results never stored. Saving them would change how three things read, though not any status: one of the original 4 October families, currently rejected (H-P7A-F9), would become eligible to be judged again, and the luck score of M0007's best variant would rise from 0.952 to 0.978 and M0011's from 0.943 to 0.973. That is a judgement about the lab's verdicts rather than about whether its records hold, so it is left for the next round of exploration to decide.
EOF
lab --db "$W/lab/lab.sqlite" insight --kind observation \
  --title "Old results stopped matching because the starting amount changed, not the prices" \
  --file "$S/insight-body.md"            # prints the new insight id; note it
lab --db "$W/lab/lab.sqlite" stage       # prints: staged .../lab/lab.sqlite, staged .../web/data/lab.json
```
The insight does not mention M0001, so Step 3's informational check never changes its text.

Then verify the committed database:
```bash
"$PY" - "$W/lab/lab.sqlite" <<'EOF'
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
assert c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "5"
assert c.execute("SELECT COUNT(*) FROM trials").fetchone()[0] == 152
assert c.execute("SELECT COUNT(*), COUNT(DISTINCT trial_n) FROM trial_provenance").fetchone() == (152, 152)
assert c.execute("SELECT COUNT(*) FROM trial_provenance WHERE source <> 'backfill'").fetchone()[0] == 0
assert c.execute("SELECT COUNT(*) FROM trial_moments").fetchone()[0] == 38   # unchanged
assert c.execute("SELECT COUNT(*) FROM trial_funding").fetchone()[0] == 24   # unchanged
print(c.execute("SELECT id, kind, title FROM insights ORDER BY id DESC LIMIT 1").fetchone())
EOF
git -C "$W" diff --cached --name-only    # exactly: lab/lab.sqlite, web/data/lab.json
```
**Impact:** the committed database is now schema 5. Reverting this phase's commit restores v4
byte for byte.

### Step 9: Full suite, with the staged database
**Code:**
```bash
(cd "$W/engine" && PYTHONPATH="$PWD/src" "$PY" -m pytest -q)
(cd "$W/engine" && PYTHONPATH="$PWD/src" "$PY" -m pytest -q tests/test_lab_snapshot.py tests/test_lab_gate_wording.py tests/test_lab_status.py)
lab --db "$S/status-new.sqlite" status >/dev/null   # sanity; the committed DB is NOT opened by status
```
`lab status` is run on a copy, never the committed file: any `lab` command migrates and may dirty
it (handover §7.4). To read the committed status without writing, copy it first:
```bash
cp "$W/lab/lab.sqlite" "$S/final.sqlite" && lab --db "$S/final.sqlite" status | grep -A1 'Promotable now'
```
Expected: the next line is `    (none)`.

### Step 10: Commit by pathspec
**Code:**
```bash
cd "$W"
git add -- docs/runbooks/data-pipeline.md engine/package_readme.md docs/plans/HANDOVER_20261009.md \
  .claude/skills/sync-research-store/SKILL.md \
  .claude/skills/explore-and-experiment-new-method/SKILL.md \
  .claude/skills/redo-sera-experiments/SKILL.md
git diff --cached --name-only | sort
# exactly:
#   .claude/skills/explore-and-experiment-new-method/SKILL.md
#   .claude/skills/redo-sera-experiments/SKILL.md
#   .claude/skills/sync-research-store/SKILL.md
#   docs/plans/HANDOVER_20261009.md
#   docs/runbooks/data-pipeline.md
#   engine/package_readme.md
#   lab/lab.sqlite
#   web/data/lab.json
cat > "$S/commit-msg.txt" <<'EOF'
docs(lab): recorded trials reproduce at their recorded capital; stage the v5 lab

Handover §5.1 asked whether the lab's records drifted with the research store. Measured on
scratch copies with phases 1-3 landed: the three store fingerprints carry byte-identical price
files (they differ only in `fundamentals.csv`); what moved was `INITIAL_IDR` (20M -> 10M in
`d79fc83`). At the recorded capital `lab remeasure M0011`, `M0007` and `H-P7A` (54/54) exit 0 on
today's store with `INITIAL_IDR` unchanged, `lab costs M0011` flat column reads trial #90's
+660.2%, and `lab status` is unchanged (Promotable now: (none)).

- `lab/lab.sqlite`: migrated to schema 5 by `lab insight` (152 back-filled `trial_provenance`
  rows: lump-sum -> 20M, funded -> 10M; price fingerprint 5451195f for all dev trials), plus one
  plain-words observation. No trial, `trial_moments` or status row written.
- `web/data/lab.json`: regenerated by `lab stage`.
- runbook, package readme, handover: store vs price fingerprint, recorded capital, the gate's
  comparability rule, `lab run` refusing a rebuilt store, and §5.1's four questions answered.
- skills (sync-research-store, explore, redo-sera): a missing store is pulled, not rebuilt,
  because `lab run` now refuses a store on other prices.

Recovered moments were deliberately not written (they would make H-P7A-F9 re-evaluable and lift
two DSRs); that call is the explore loop's.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
git commit -F "$S/commit-msg.txt"
```
Do **not** push `main` and do not merge: pushing `main` redeploys seertrade.site, and the merge
is the orchestrator's. Never `git add -A`; the untracked plan/analysis files at the worktree root
belong to the orchestrator.

## Verification

**Build:** none (no source change).
**Tests:** `cd /home/miftah/.worktrees/seer/trial-reproducibility/engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q`
**Manual check:** Steps 2–5 outputs on scratch copies; Step 8's assertions on the committed file;
`git show --stat HEAD` lists exactly the eight paths of Step 10.
**Exit criteria:** on scratch copies, `lab remeasure M0011`, `M0007`, `H-P7A` exit 0 at
`INITIAL_IDR = 10000000`, and `lab costs M0011 --candidate M0011-RAW20-TV14-N21` prints a flat
total return of +660.2% with "the flat re-run reproduces it"; `lab status` is identical to the
`e5eda52` base and says `Promotable now: (none)`; the committed `lab/lab.sqlite` is schema 5 with
152 `trial_provenance` rows (all `backfill`), 152 trials, 38 `trial_moments`, 24 `trial_funding`,
and one new `observation` insight; `test_lab_snapshot` passes and the full suite passes; the three skills
no longer tell a session to build a missing dev store first; one commit holding exactly the eight
paths of Step 10.

## Handoffs

- **Merge conflict on a binary database (orchestrator).** If `main`'s `lab/lab.sqlite` moves
  after `e5eda52` before this branch merges (a Sera batch), do not pick a side of the binary
  conflict. Take `main`'s database, run Step 7, then repeat Step 8 on it (the migration is
  idempotent; the insight is appended once more only if it is not already there) and `lab stage`.
  As of planning, `main` has not moved `lab/lab.sqlite` since `e5eda52`.
- **Writing the recovered `trial_moments` (explore loop, out of scope).** Named in the insight
  with what it changes: `H-P7A-F9` re-evaluable; `M0007-N20-RAW` DSR 0.952 -> 0.978;
  `M0011-RAW20-TV14-N21` 0.943 -> 0.973.
- **M0005 (`e597367b…`, fundamentals method) cannot be reproduced from the price fingerprint.**
  Its panel was the 2015-only one, replaced in place by `--refresh-fundamentals`. Re-running it
  would need the old whole-store fingerprint. Nothing re-runs it today and no gate reads it as
  comparable on anything but prices, so this is recorded in the runbook text, not acted on. If
  Phase 2's `lab remeasure` does not already refuse a fundamentals method on a store-fingerprint
  mismatch, that is a follow-up for a later card (not R3/R4).
- **The `bbe7abfb…` test store's price fingerprint is NULL** on this machine. A §5.3 follow-up
  (sync the test store) can supply its file map; no comparison reads test trials against the dev
  benchmark, so nothing waits on it.
- **Name drift.** Reconciled against phases 2 and 3's plans (see Requires). If the landed code
  still differs, the docs follow the code.

## Rollback

`git revert <phase-4 commit>` restores `lab/lab.sqlite` (v4, no insight), `web/data/lab.json`,
the three docs and the three skills byte for byte; the migration only added a table and rows, and phases 1–3's
code still opens a v4 file (it migrates on connect). Scratch copies need no cleanup beyond
deleting `$S`.
