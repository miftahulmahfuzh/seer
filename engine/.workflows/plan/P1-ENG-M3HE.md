> Adopted from `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` phase 5. Source: `.workflows/plan/fundamental-panel-coverage/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: Measure, report honestly, and retire the runbook snippet

**Plan set:** `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md`
**Analysis:** `20261005-133648-2XUM_code_analyzer.md`
**Satisfies:** R4 (honest reporting, §8.3) and R5 (§6.1, verified not implemented)
**Depends on:** Phase 1, Phase 2, Phase 3, Phase 4
**Difficulty:** NORMAL
**Package:** `docs` (plus `engine/package_readme.md` and one `engine/src` docstring)

---

## Runtime preamble — run this before every command in this phase

Reconciled set-wide (see the index's `## Decisions`, row C2). The worktree has **no venv of its
own**, and `/home/miftah/seer/engine/.venv` is an *editable* install whose
`__editable__.seer_engine-0.1.0.pth` contains the literal `/home/miftah/seer/engine/src` — the
**main checkout**. `engine/pyproject.toml`'s `[tool.pytest.ini_options]` sets only
`testpaths = ["tests"]` and **no `pythonpath`**, so pytest resolves `seer_engine` through that
same editable install. Without the block below, every command in this phase — `pytest`
included — silently exercises `main`'s code and reads `main`'s `engine/data/`.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/fundamental-panel-coverage
export SEER_PY=/home/miftah/seer/"$SEER_PY"
export PYTHONPATH=$SEER_WT/engine/src          # searched before anything `site` adds
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

**Reuse main's venv; do not build one in the worktree.** `PYTHONPATH` wins over the `.pth`
(measured), carries `cik.DATA_DIR` (`Path(cik.__file__).parents[2] / "data"`) to the worktree
with it, and applies uniformly to `pytest` and to `python -m seer_engine`. A second venv would
mean a second dependency resolution, and invariant 1 pins this set to the `2dad9ff` baseline of
2216 passed / 332 skipped measured in *this* interpreter.
`engine/scripts/build_ticker_cik.py:40` does its own
`sys.path.insert(0, Path(__file__).resolve().parents[1] / "src")`, so the generator
self-resolves when invoked by its worktree path — that rescues the generator and nothing else.

**This phase touches a database, so it also needs (index `## Decisions`, row C3):**

```bash
export SEER_ENV_FILE=/home/miftah/seer/.env.local-train     # ABSOLUTE, always
export SEER_TRAIN_URL=postgresql://postgres:pg@localhost:55432/postgres
```

`config.env_file()` returns `Path(override)` verbatim and resolves a relative path against the
**cwd**. `.env*` is gitignored, so the worktree holds no `.env.local-train`: a relative
`SEER_ENV_FILE=.env.local-train` loads nothing, `DATABASE_URL_UNPOOLED` falls through to the
ambient environment, and the ambient one points at **Neon**. Invariant 8 forbids any Neon
write. Prove the resolved DSN before anything writes:

```bash
"$SEER_PY" -c "import os, seer_engine.config as c; c.load_env(); u = os.environ['DATABASE_URL_UNPOOLED']; assert 'localhost:55432' in u, f'REFUSING: {u}'; print('DSN ok:', u)"
```

Two more constants this phase uses everywhere:

```bash
export SEER_MAIN=/home/miftah/seer
export SEER_STORE=$SEER_MAIN/engine/.research     # the store exists ONLY in the main checkout
```

Every `research_store` invocation in this phase passes `--store "$SEER_STORE"` **explicitly**.
With the preamble exported, `config.REPO_ROOT` is the worktree, so `research.STORE_DIR` would
otherwise point at `<worktree>/engine/.research`, which does not exist.

---

## Goal

After this phase the panel's dev-window coverage is a **measured number produced by engine code**,
pasted verbatim into `docs/runbooks/data-pipeline.md` and into §4 of the decision doc, next to an
explicit statement that the number does **not** make a fundamentals method testable on the dev
window. The runbook's two copy-paste Python gates are gone, replaced by
`research_store --coverage`. The M0005 docstring stops telling an operator to run a vacuous
manifest check and says instead that the id is spent. §6.1 is confirmed closed by running its
tests, not by re-writing its code. The refreshed store is published to Blob and its content hash
recorded.

**This phase writes no code.** It runs four commands, verifies one already-landed fix, and edits
four documents plus one docstring.

---

## Interface Contract

**Deletes:**
- `docs/runbooks/data-pipeline.md` — the `python -c "...manifest.json...['files']"` one-liner
  (`:190-192`) and the `python - <<'EOF'` coverage snippet (`:209-224`). Both are copy-paste
  Python gates that the engine now owns.
- `docs/runbooks/data-pipeline.md:229-235` — the 2026-10-05 measured table.
- `docs/runbooks/data-pipeline.md:160-163` — the re-vendoring recipe's steps 1–2, whose
  *"the automated pass resolved 98 of 133 (94 exact, 4 fuzzy)"* counts phase 2's re-scope
  invalidates. Replaced by a pointer to `engine/data/SOURCES.md`, which phase 2 owns and keeps
  current, so this phase states no figure it did not run (invariant 10). See Step 8b.
- `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py:18-28` — the
  `python -c` manifest gate inside the "READ THIS BEFORE RUNNING" preamble.

**Renames:** none.

**Creates:**
- `docs/runbooks/data-pipeline.md` — a measured coverage block dated at run time, carrying the
  refreshed store's fingerprint.
- `docs/plans/2026-10-05-fundamental-panel-coverage.md` §4 — an annotation block under the
  accounting table.
- `engine/package_readme.md` — three insertions (the `--coverage` flag, the refresh flag, the
  current store's fingerprint).

**Signature changes:** none. No `engine/src` symbol changes.

**Requires (from earlier phases):**
- **Phase 1:** `python -m seer_engine research_store --coverage` exists, loads a store, and prints
  a per-year rankable table plus one fraction. It is run, never edited.
  `fundamentals.coverage.MIN_DEV_COVERAGE == 0.80` is the floor named in the prose. **Its measure
  samples MONTHLY with `top = 20` and `max_stale_days = 400`** and that is the set's one
  definition of coverage — phase 1 measured **0.0378** on the pre-fix 2026-10-05 store with it.
  The analysis's `0.025` (semiannual) and the decision doc's `4%` (a span estimate) are different
  definitions and must never be quoted as this measure. **The measure is an UPPER BOUND**: it
  reads no bars, so it applies neither index membership on the date nor
  `min_price`/`min_dollar_volume`, each of which can only remove symbols. Every sentence this
  phase writes around the number says so (index `## Decisions`, row C8).
- **Phase 2:** `engine/data/ticker_cik.csv` carries real first-membership intervals
  (795 → 913 symbols). Its final row count fills slot `M14`.
- **Phase 3:** the local train database at `.env.local-train` holds facts filed from 2009-01-01,
  and the phase's summary reports facts-by-`filed`-year for 2009–2012. Those four counts fill
  slots `M8`–`M11`.
- **Phase 4:** `research_store` has a fundamentals-only refresh flag that copies `bars.csv`,
  `dividends.csv`, `fx.csv` and `unserved.csv` byte for byte. Its exact spelling fills slot
  `M15`. It is run, never edited.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/fundamentals/**`, `commands/research_store.py`, `commands/lab.py`,
  `lab/runner.py` (Phase 1)
- `engine/src/seer_engine/cik.py`, `engine/scripts/**`, `engine/data/**` (Phase 2)
- `engine/src/seer_engine/commands/fundamentals.py` (Phase 3)
- `engine/src/seer_engine/research.py` (Phase 4)
- `engine/tests/**` — this phase runs tests, adds none
- every `docs/plans/*.md` except §4 of `2026-10-05-fundamental-panel-coverage.md`
- the database (read-only, and only through Phase 4's refresh), and Neon (untouched)

---

## Hard boundaries (restated because this phase is the one that could cross them)

1. **`lab run` is never invoked.** Not `M0005`, not any method, not with `--allow-coverage`, not
   in a dry run. The gate that Phase 1 added is exercised by Phase 1's own tests, not here.
2. **No method id, idea or variation is minted.** `source_kind='variation'`, `parent_id='M0005'`
   is written down as the *shape a future re-test must take*; nothing in this phase creates it.
3. **The post-2015 held-out test window is not touched.** The lab has never used it
   (`test-window looks used: 0`), it can be spent once, and spending it is a separate decision
   with its own doc.
4. **The dev window is not shortened or forked** for fundamentals methods. That is §5's other
   candidate and it is deferred.
5. **No paid vendor for pre-2009 fundamentals is proposed or priced.** §4: impossible at any
   price from EDGAR; Compustat is out of scope.
6. **No sentence written by this phase claims the test problem is solved.** Invariant 10: no
   figure is stated that was not run. Every number in the docs this phase writes comes from a
   slot filled by a command whose output is pasted into
   `$SCRATCH/phase5-transcript.txt` first.

---

## Measurement slots

Every number this phase writes into a document is a **slot**. A slot is filled by pasting a
command's output; it is never estimated, rounded from memory, or carried over from the baseline.
If a command does not run, its slot stays empty and the sentence containing it is not written.

| Slot | What it is | Filled by |
|---|---|---|
| `<<RUNDATE>>` | the date the measurement ran, `YYYY-MM-DD` | `date -I` at Step 1 |
| `<<M1_NEW_FP>>` | the refreshed store's 64-hex fingerprint | Step 4, `research_store --verify` |
| `<<M2_PANEL_SYMBOLS>>` | symbols the refreshed panel holds | Step 5, `--coverage` header |
| `<<M3_COVERAGE_TABLE>>` | the per-date rankable table, **verbatim** | Step 5, `--coverage` |
| `<<M4_COVERAGE_FRACTION>>` | the single dev-window fraction, as printed | Step 5, `--coverage` |
| `<<M5_FIRST_COVERED>>` | first sample date reaching ≥ 20 rankable | Step 5, read off `M3` |
| `<<M6_FIXA_FRACTION>>` | same measure, facts filtered to `filed >= 2013-01-01` | Step 6 |
| `<<M7_BASELINE_FRACTION>>` | same measure against the pre-fix store `e597367b…` | Step 2 |
| `<<M8_FACTS_2009>>` … `<<M11_FACTS_2012>>` | facts by `filed` year, 2009–2012 | Phase 3's summary |
| `<<M12_FACT_ROWS>>` | `fundamentals.csv` data rows in the refreshed store | Step 4 |
| `<<M13_PUSH>>` | the push's `fingerprint` + `mb` | Step 11 |
| `<<M14_TICKER_ROWS>>` | symbols in the re-vendored `ticker_cik.csv` | Phase 2's summary |
| `<<M15_REFRESH_FLAG>>` | Phase 4's refresh flag, exact spelling | Phase 4's plan / `--help` |

`M8`–`M11` and `M14` come from sibling phases' summaries. If a sibling's summary does not carry
its number, **do not guess it**: drop the sentence that needs it and record the gap in the
phase summary as "Phase N under-delivered: <what was missing>". The honesty clause applies to
upstream gaps as much as to the headline number.

---

## Files

| File | Action | What changes |
|---|---|---|
| `docs/runbooks/data-pipeline.md` | modify | `:188-256` replaced (Step 8) — both Python gates become `research_store --coverage`; the 2026-10-05 table becomes the measured one; the presence-is-not-coverage lesson is kept. **Plus, assigned by the reconciler (Step 8b): `:12,:15,:44,:51` and `:151-175`** — the stale "ever-members since 2015-01-02" scope lines and the duplicated re-vendoring recipe |
| `docs/plans/2026-10-05-fundamental-panel-coverage.md` | modify | §4's table `:153-160` only — `~14%` / `~30%` become measurements, plus an annotation block. Sections 1,2,3,5,6,7,8 untouched |
| `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` | modify | docstring `:18-28` only — the manifest one-liner becomes the coverage gate; M0005 declared spent. `METHOD`, `ADDED`, the six `Candidate`s and every parameter untouched |
| `engine/package_readme.md` | modify | `:324-325` usage line, a `--coverage` bullet after `:339`, a refresh bullet after `:1346`, a current-store line after `:1350` |
| `engine/.research/` *(untracked, main checkout)* | replace | Phase 4's refresh swaps in a new `fundamentals.csv` and a new fingerprint; the four bar/dividend/fx/unserved files survive byte-identical |
| Vercel Blob `seer/research-store/<fp>.tar.gz` | create | `sync_store.py push --keep 0` |

---

## Implementation Steps

### Step 0: Environment preflight — the facts the executing session must not discover at 3am

**File:** none (shell only)
**Change:** the worktree is **not** runnable as it stands. Three measured facts, and the
reconciled answer to each:

1. **The worktree has no venv, and main's is an editable install of main.**
   `site-packages/__editable__.seer_engine-0.1.0.pth` contains `/home/miftah/seer/engine/src`,
   and `engine/pyproject.toml` sets no `pythonpath` for pytest. Running
   `"$SEER_PY" -m seer_engine …` from the worktree therefore imports **main's**
   `seer_engine`, which has neither Phase 1's `--coverage` nor Phase 4's refresh; the command
   fails with `unrecognized arguments` and the obvious-but-wrong conclusion is "Phase 1 did not
   land". **RECONCILED (index `## Decisions`, row C2): export `PYTHONPATH` over main's venv — do
   NOT build a worktree venv.** The earlier draft of this step built one; a second venv means a
   second dependency resolution and the `2dad9ff` baseline of 2216/332 stops being comparable,
   which invariant 1 pins. See the **Runtime preamble**.
2. **`config.REPO_ROOT = Path(__file__).resolve().parents[3]`** (`engine/src/seer_engine/config.py:17`)
   follows the *source*, not the venv, so with `PYTHONPATH` set it is already the **worktree
   root**. `research.STORE_DIR` therefore resolves to `<worktree>/engine/.research`, which does
   not exist, and `config.env_file()`'s default to `<worktree>/.env.local`, which does not
   either — the worktree carries only `.env.example`.
3. **The store lives only in the main checkout**: `$SEER_STORE`
   (bars.csv 135 MB, fundamentals.csv 101 MB, + dividends/fx/unserved/manifest).

Consequences, and they are not optional:

- run the **Runtime preamble** (`PYTHONPATH`, main's venv, `cd "$SEER_WT"`);
- pass `--store "$SEER_STORE"` **explicitly** on every `research_store` invocation;
- pass `SEER_ENV_FILE` as an **absolute** path, and prove the resolved DSN before any write.

**Code:**

```bash
set -euo pipefail
# $SEER_WT / $SEER_PY / $PYTHONPATH / $SEER_ENV_FILE / $SEER_TRAIN_URL / $SEER_MAIN /
# $SEER_STORE all come from the Runtime preamble above. Re-export them in a fresh shell.
SCRATCH=$(mktemp -d /tmp/phase5-XXXX)
echo "scratch: $SCRATCH"
cd "$SEER_WT"

# 1. The worktree's code is what runs.
"$SEER_PY" -c "import pathlib, seer_engine, seer_engine.config as c; print('module:', pathlib.Path(seer_engine.__file__).resolve()); print('REPO_ROOT:', c.REPO_ROOT)"
# both must name /home/miftah/.worktrees/seer/fundamental-panel-coverage

# 2. Phases 1 and 4 really landed in THIS tree.
"$SEER_PY" -m seer_engine research_store --help | tee "$SCRATCH/research_store-help.txt"
grep -q -- '--coverage' "$SCRATCH/research_store-help.txt" || {
  echo 'REFUSING: phase 1 has not landed in this worktree'; exit 1; }
grep -q -- '--refresh-fundamentals' "$SCRATCH/research_store-help.txt" || {
  echo 'REFUSING: phase 4 has not landed in this worktree'; exit 1; }
# Record phase 4's refresh flag verbatim -> slot M15.
grep -E '^\s+--' "$SCRATCH/research_store-help.txt"

# 3. The env file resolves to the LOCAL database, not Neon.
test -f "$SEER_ENV_FILE" || { echo "REFUSING: $SEER_ENV_FILE missing"; exit 1; }
"$SEER_PY" -c "import os, seer_engine.config as c; c.load_env(); u = os.environ['DATABASE_URL_UNPOOLED']; assert 'localhost:55432' in u, f'REFUSING: {u}'; print('DSN ok:', u)"
PGPASSWORD=pg psql -h localhost -p 55432 -U postgres -d postgres -c 'select 1' >/dev/null \
  || { echo 'REFUSING: the seer-pg container is not up on 55432'; exit 1; }

# 4. The store is where this phase expects it.
ls -la "$SEER_STORE"
```

**Impact:** nothing is written. A failure here stops the phase before it touches the store, and
`git status` stays clean — no venv is created.

---

### Step 1: Protect the rollback before replacing anything

**File:** none (shell only)
**Change:** the plan index's draft said the Blob push "adds an object and deletes nothing".
**That was not true by default, and the index has been corrected** (`## Decisions`, row C4b).
`~/.claude/skills/sync-research-store/sync_store.py` has
`KEEP_VERSIONS = 3` and `cmd_push` calls `_prune(tok, keep=args.keep)` after the upload
(`sync_store.py:294`). If the remote already holds three versions, pushing a fourth **deletes the
oldest**, which may be `e597367b…` — the object the whole rollback story rests on. So: list
first, keep a local copy, and push with `--keep 0`.

**Code:**

```bash
S=~/.claude/skills/sync-research-store/sync_store.py
cd "$SEER_MAIN"                      # sync_store resolves the MAIN checkout regardless of cwd
python3 "$S" status | tee "$SCRATCH/store-status-before.json"
python3 "$S" list   | tee "$SCRATCH/store-list-before.json"
# Confirm e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3 is listed.
# If it is NOT listed, STOP: there is no remote rollback. Push it first (it is the
# current store, so a plain `push` is a no-op or publishes exactly it), then continue.

# Belt and braces: a local copy OUTSIDE the repo, so `git status` stays clean.
BACKUP=/home/miftah/.seer-store-backup-e597367b
test -d "$BACKUP" || cp -a "$SEER_STORE" "$BACKUP"
du -sh "$BACKUP"
date -I | tee "$SCRATCH/rundate.txt"          # -> slot RUNDATE
```

**Impact:** ~236 MB of disk outside the repo. Nothing in the repo changes. Delete `$BACKUP` only
after Step 11 reports a successful push.

---

### Step 2: Measure the PRE-fix store with the SAME measure, so the before/after is comparable

**File:** none (shell only)
**Change:** the recorded baseline (`2.5%`, 1/40 dates) was measured with **semiannual** sampling
and the runbook's `4%` is a **span estimate** (9 months of 19.8 years). Phase 1's measure samples
**monthly** with a 400-day staleness gate. Three different definitions would make the before/after
meaningless, so run Phase 1's measure once against the untouched store **before** the refresh.

**Code:**

```bash
cd "$SEER_WT"
"$SEER_PY" -m seer_engine research_store --coverage --store "$SEER_STORE" \
  2>&1 | tee "$SCRATCH/coverage-before.txt"
```

Read the single fraction off the last lines → slot `M7_BASELINE_FRACTION`. Expect it to be near
zero; the pre-fix panel cannot rank anybody before 2015-01.

**Impact:** read-only. If `--coverage` needs a `--store` spelling other than `--store`, take it
from Step 0's `--help` dump; do not improvise a path default.

---

### Step 3: Run Phase 4's fundamentals-only refresh against the real store

**File:** none (shell only)
**Change:** rebuild `fundamentals.csv` from the re-ingested local train database, carrying
`bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` over byte for byte. `--with-fundamentals`
must **not** be used: it goes through `build_store`, which always downloads every symbol's bars
from yfinance first, replacing all 2,490,793 bar rows with whatever yfinance answers today and
breaking comparability with the 64 recorded trials (§7).

**Code:**

```bash
cd "$SEER_WT"
sha256sum "$SEER_STORE"/bars.csv "$SEER_STORE"/dividends.csv "$SEER_STORE"/fx.csv "$SEER_STORE"/unserved.csv \
  | tee "$SCRATCH/copied-files-before.sha"

# The DSN guard from Step 0 must have passed in THIS shell before this line runs.
SEER_ENV_FILE=/home/miftah/seer/.env.local-train \
"$SEER_PY" -m seer_engine research_store <<M15_REFRESH_FLAG>> --store "$SEER_STORE" \
  2>&1 | tee "$SCRATCH/refresh.txt"
echo "exit: $?"
```

Notes the executing session must honour:

- **`SEER_ENV_FILE` is absolute, and it is repeated on the command line even though the preamble
  exports it** (index `## Decisions`, row C3). `config.env_file()` returns `Path(override)`
  verbatim and resolves a relative path against the **cwd**; `.env*` is gitignored, so the
  worktree has no `.env.local-train`. A relative `SEER_ENV_FILE=.env.local-train` — which is what
  the decision doc §3 and the draft index both wrote — loads nothing,
  `DATABASE_URL_UNPOOLED` falls through to the ambient environment, and **the ambient one points
  at Neon**, which invariant 8 forbids writing to. `_read_facts()` only *reads*, so the worst case
  here is a panel built from Neon's deliberately-truncated tables — an empty `fundamentals.csv`
  pushed to Blob as if it were the fix. Run the Step 0 DSN guard in the same shell first.
- `<<M15_REFRESH_FLAG>>` is Phase 4's flag, read from Step 0's `--help` dump. Do not invent it.
- Phase 4 guarantees "nothing is written on failure" via the `.tmp` / `.old` swap. A non-zero
  exit therefore leaves the 2026-10-05 store in place; re-read Phase 4's plan rather than
  re-running blind.

**Impact:** `engine/.research/` in the **main checkout** is replaced. The fingerprint changes.
This is the only destructive act in the phase, and `$BACKUP` plus the Blob object are both still
intact at this point.

---

### Step 4: Verify the refreshed store and record its fingerprint

**File:** none (shell only)
**Change:** prove the four copied files survived byte-identical, prove the store still verifies,
and capture the new fingerprint.

**Code:**

```bash
cd "$SEER_WT"
sha256sum -c "$SCRATCH/copied-files-before.sha"      # all four must print OK

"$SEER_PY" -m seer_engine research_store --verify --store "$SEER_STORE" \
  2>&1 | tee "$SCRATCH/verify-after.txt"
# -> slot M1_NEW_FP (the 64-hex fingerprint it prints)
# It must NOT equal e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3.

python3 - <<'PY' | tee -a "$SCRATCH/verify-after.txt"
import json, pathlib
m = json.loads(pathlib.Path("/home/miftah/seer/engine/.research/manifest.json").read_text())
print("fingerprint:", m["fingerprint"])
print({k: v for k, v in m.items() if k != "files"})
PY

# fundamentals.csv data rows -> slot M12_FACT_ROWS
echo "fact rows: $(( $(wc -l < "$SEER_STORE"/fundamentals.csv) - 1 ))" | tee -a "$SCRATCH/verify-after.txt"
```

**Impact:** read-only. A `sha256sum -c` failure on any of the four copied files means Phase 4's
contract was violated; stop and hand it back to Phase 4 rather than pushing the result.

---

### Step 5: Run the coverage gate and capture its output verbatim

**File:** none (shell only)
**Change:** this is the phase's deliverable. The output is captured to a file first, and the
documents quote **that file**, never a remembered number.

**Code:**

```bash
cd "$SEER_WT"
"$SEER_PY" -m seer_engine research_store --coverage --store "$SEER_STORE" \
  2>&1 | tee "$SCRATCH/coverage-after.txt"
cat "$SCRATCH/coverage-after.txt"
```

From that single file read off:

- `<<M2_PANEL_SYMBOLS>>` — the panel's symbol count as printed;
- `<<M3_COVERAGE_TABLE>>` — the per-date table, copied **character for character**, including
  any rows that are zero;
- `<<M4_COVERAGE_FRACTION>>` — the single fraction, in the units the command prints them;
- `<<M5_FIRST_COVERED>>` — the first sampled date whose rankable count reaches 20.

**Impact:** read-only. **If the fraction is disappointing, that is the number that goes into the
documents.** There is no second run, no re-parameterisation, and no selecting a more flattering
sample grid.

---

### Step 6: Measure "Fix A alone", because §4's table has a row for it

**File:** none (shell only)
**Change:** §4's `+ Fix A` row must stop being an estimate. Fix A and Fix B were applied
together, so the engine has no path that rebuilds the panel at the old `filed` floor. But the
measure Phase 1 shipped is **pure** — it takes a panel — and the refreshed store's
`fundamentals.csv` carries each fact's `filed` date. Filtering that file to `filed >= 2013-01-01`
in memory and re-running the same measure is exactly "what Fix A alone would have reached", and
it costs no database, no network and no file write.

**Code:**

```bash
cd "$SEER_WT"
cat > "$SCRATCH/fixa_only.py" <<'PY'
"""Fix A alone: the re-vendored intervals with the OLD 2013-01-01 filed floor.

Reads the refreshed store's fundamentals.csv, drops every fact filed before 2013-01-01,
builds a panel from what is left and runs the SAME measure research_store --coverage runs.
Writes nothing, opens no connection.

The three names below were checked against the tree by the reconciler, because the draft of
this step had all three wrong:

  * `research._read_fundamentals` returns a FundamentalPanel, not a sequence of Facts, so it
    cannot be filtered by `filed`. The text -> Fact path is `backtest.io.facts_from_frame`,
    which `research._read_fundamentals` itself calls, and the frame must be read with exactly
    the dtypes it uses (research.py:276-282) or the cells arrive as the wrong types.
  * `research.FundamentalPanel` does not exist: research.py:58 imports it as `Panel`. The
    public name lives in `seer_engine.fundamentals`.
  * `coverage.measure` returns a `Coverage`; `coverage.format_report` is what prints readably.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from seer_engine import research
from seer_engine.backtest.io import facts_from_frame
from seer_engine.fundamentals import FACT_COLUMNS, FundamentalPanel, coverage

FLOOR = date(2013, 1, 1)
STORE = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/miftah/seer/engine/.research")

frame = pd.read_csv(
    STORE / research.FUNDAMENTALS_FILE,
    dtype={c: str for c in FACT_COLUMNS} | {"val": np.float64},
    na_filter=False,
    float_precision="round_trip",
)
full = facts_from_frame(frame)
kept = tuple(f for f in full if f.filed >= FLOOR)
print(f"facts: {len(full)} total, {len(kept)} filed >= {FLOOR} ({len(full) - len(kept)} dropped)")

panel = FundamentalPanel.from_facts(kept)
print(coverage.format_report(coverage.measure(panel)))
PY

"$SEER_PY" "$SCRATCH/fixa_only.py" "$SEER_STORE" 2>&1 | tee "$SCRATCH/coverage-fix-a.txt"
```

Read `<<M6_FIXA_FRACTION>>` off the `covered N of M sampled dates = 0.xxxx` line — the same line
`--coverage` prints, from the same code, so the two rows of §4's table are comparable by
construction. It is an **upper bound** on the same terms as `M4`.

**Before running it, confirm the three imported names still exist** — this phase runs after
phase 1 and may be reading a module that moved:
`"$SEER_PY" -c "from seer_engine.fundamentals import FACT_COLUMNS, FundamentalPanel, coverage; from seer_engine.backtest.io import facts_from_frame; print('ok', coverage.DEFAULT_TOP, coverage.default_max_stale_days())"`

**Fallback, and it is an acceptable outcome:** if Phase 1's measure does not accept a panel
directly, or the panel cannot be built from a filtered `Fact` tuple without a store round-trip,
**do not fabricate the number.** Write the `+ Fix A` row as:

> **not separately measured** — Fix A and Fix B were applied together and the engine has no path
> that rebuilds the panel at the old `filed` floor

and say so in the phase summary. An unmeasured row stated as unmeasured satisfies Invariant 10;
a plausible-looking `~14%` does not.

**Impact:** read-only, in-memory, no file written outside `$SCRATCH`.

---

### Step 7: Verify R5 (§6.1) — a check, not an implementation

**File:** `engine/src/seer_engine/paper/store.py:1025-1063`, `engine/tests/test_paper_store.py:554-595`
**Change:** none. Confirm what `2dad9ff` already landed, and record one correction to this
phase's own brief.

**Measured at the base commit `2dad9ff`:**

- `load_market_window(conn, since, *, cache_dir=bio.CACHE_DIR)` builds
  `Market(history=…, membership=…, fx=…, fundamentals=bio.load_panel(conn, cache_dir=cache_dir))`
  at `paper/store.py:1058-1063`. The field is present.
- There are **exactly three** `Market(` construction sites in `engine/src`, and all three pass
  `fundamentals=`: `backtest/io.py:156`, `paper/store.py:1058`, `research.py:583`.
- `2dad9ff` added **three** tests, not two. The draft brief for this phase named
  `test_market_window_panel_is_empty_when_the_facts_tables_are_absent`; **no test by that name
  exists anywhere in the tree** — it came from an uncommitted draft. **The reconciler has
  corrected it at source**: the plan index's phase-5 `Owns` section and the analysis document's
  §6.1 reference table now carry the real name and the real line number (index `## Decisions`,
  row C4c). The three tests that do exist, at `engine/tests/test_paper_store.py:554`, `:573` and
  `:585`, are:
  - `test_market_window_carries_the_fundamental_panel_not_an_empty_one`
  - `test_market_window_panel_equals_the_full_loads_panel`
  - `test_market_window_panel_is_empty_when_no_facts_are_stored`

  The third is the one the brief meant; its docstring is "Production's state: 005 applied,
  `fundamental_facts` deliberately truncated". The second is a bonus the brief did not know
  about: it asserts windowing the bars does not window the facts, which is what SUE's
  `MIN_QUARTERS` lookback needs. **Record the corrected names; do not rename the tests.**

**Code:**

```bash
cd "$SEER_WT"
grep -rn 'Market(' engine/src/seer_engine --include='*.py' | grep -v 'EMPTY\|#'
# must list exactly three sites, each followed by a fundamentals= argument

PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
"$SEER_PY" -m pytest engine/tests/test_paper_store.py -q \
  -k 'market_window and (panel or fundamental)' 2>&1 | tee "$SCRATCH/r5-tests.txt"
# expect: 3 passed
```

**Impact:** none on the tree. §6.1 is recorded as **closed** in the phase summary, with the three
test names and the three construction sites as the evidence. **No new code is written for R5.**

---

### Step 8: Replace the runbook's two Python gates and its 2026-10-05 table

**File:** `docs/runbooks/data-pipeline.md:188-256`
**Change:** keep lines 176-187 (the `### The lab and fundamentals` heading and the
`load_store`/optional-file paragraph) exactly as they are. Replace lines **188 through 256**
with the block below. Line 258 onward (`Tests: PG_TEST_URL=… …`) is untouched.

The lesson prose is kept — it is the part that is still true and it is why M0005 was spent. What
goes is the copy-paste Python and the superseded numbers.

**Code:**

```markdown
**Before any fundamentals method, measure the panel's COVERAGE. Do not check for its presence.**

```bash
"$SEER_PY" -m seer_engine research_store --coverage
```

That prints, for the store at `engine/.research`, how many symbols the panel can actually rank on
each sampled dev-window date, and one fraction: the share of **monthly** sample dates on which it
can rank at least `top` names (default 20) from facts filed within `max_stale_days` of the date
(400, taken from `FundamentalParams`'s own default rather than restated). It is the same
eligibility gate `strategies/f_fundamental.py` applies, so the number predicts *rankability*
rather than mere fact-existence.

**The number is an upper bound.** The measure is pure: it takes a panel and reads no bars, so it
applies neither index membership on the date nor `min_price`, twenty sessions of history or
`min_dollar_volume` — every one of which can only remove symbols. A fraction *below* the floor is
therefore conclusive (the panel cannot rank); a fraction *above* it is necessary and not
sufficient. The command's own last output line says so.

`lab run` runs the same measure after it loads the store and **refuses** a method whose allocator
is `MarketAware` when the fraction is below `fundamentals.coverage.MIN_DEV_COVERAGE` (0.80). A
price-only method is never refused — M0001 and M0004 rank on price and must stay runnable against
a store with no panel at all. `--allow-coverage F` lowers the floor for one run and prints the
measured number loudly; it is an acknowledgement, not a bypass, and it does not suppress the
table.

**The gate this replaced was vacuous, and M0005 was spent proving it.** It asked "does
`manifest.json` list `fundamentals.csv`" — binary where the risk is continuous: a store carrying
a panel over a sliver of the dev window passes it. MEASURED 2026-10-05 — M0005 ran against the
store `e597367b…`, whose panel covered **2015-01-06..2015-10-16, about 9 months of the 19.8-year
dev window**. All six variants were recorded, all six "failed", and the verdict measured
cash-holding, not the factor premia. The tell was in the output: 15–32 trades over 19.8 years
against a `>= 100` gate, and "worst year 1996 +0.0%" for a year the book could not have held
anything.

**Presence is never evidence of coverage anywhere in this subsystem.** `panel.as_of(symbol, t)`
**always returns a `Snapshot`** — an empty husk with `observations == {}` when nothing is known —
so it never returns `None`, and `sum(1 for s in syms if panel.as_of(s, t) is not None)` counts
every symbol in every year and measures nothing. That is deliberate and defensible: the
fundamentals layer answers every query and encodes "I know nothing yet" as *empty content*, which
is what lets `Market` carry `EMPTY_PANEL` and every allocator keep working. The cost is that every
existence check here is a lie. **Check content, not presence.**

**What the measure reports now.** MEASURED `<<RUNDATE>>`, store `<<M1_NEW_FP>>`,
`<<M2_PANEL_SYMBOLS>>` panel symbols — after Fix A (`ticker_cik.csv` re-vendored from the clamped
2015-01-02 scope date to each symbol's real first-membership interval, 795 → `<<M14_TICKER_ROWS>>`
symbols) and Fix B (both ingest floors lowered to 2009-01-01):

```
<<M3_COVERAGE_TABLE>>
```

Dev-window coverage, as an **upper bound**: **`<<M4_COVERAGE_FRACTION>>`**. The first sampled
date on which the panel can rank 20 names is `<<M5_FIRST_COVERED>>`. The same measure run against
the pre-fix store (`e597367b…`) reports **`<<M7_BASELINE_FRACTION>>`**.

Three numbers are in circulation for "coverage" and only one of them is this measure. **This
one** is monthly sampling, `top = 20`, `max_stale_days = 400`, 1996-01-02 .. 2015-10-16, content
checked through `Snapshot.observations`. The `2.5%` recorded in the 2026-10-05 analysis was a
**semiannual** sample (1 of 40 dates); the `4%` in `docs/plans/2026-10-05-fundamental-panel-coverage.md`
§4 is a **span estimate** (nine months of 19.8 years). Do not compare across them.

**This does not make a fundamentals method testable on the dev window, and nothing here should be
read as saying it does.** The dev window opens **1996-01-03**. XBRL does not exist before roughly
**2009**, so about **thirteen of its nineteen years are permanently uncoverable from EDGAR** — at
any price, by any amount of work. (Compustat sells point-in-time pre-2009 fundamentals; it is
expensive, licence-encumbered, carries its own restatement-vintage problems, and is **out of
scope**.) A book that holds cash for most of the window cannot reach the lab's `>= 100 trades`
gate, so **that gate remains unreachable for a fundamentals method on this dev window.** Fix A
and Fix B made the *data* honest; they did not make the *test* valid.

**The test-window decision is UNMADE and out of scope.** The only window on which these premia
could be tested validly is the post-2015 held-out test window, which this lab has never used
(`test-window looks used: 0`). It can be spent exactly once, and spending it is a separate
decision with its own doc. Giving fundamentals methods a shorter dev window of their own is the
other candidate and is also deferred: it breaks comparability with the 64 trials recorded against
1996–2015 and changes the DSR's `N`.

**M0005 is `rejected` and its six `config_digest`s are spent.** The hypothesis is untested, not
refuted. A re-test is a **new** method with `source_kind='variation'` and `parent_id='M0005'`, and
it must not be minted until the gate above reports a number worth testing.

**Refreshing the panel without re-downloading bars.** `research_store --with-fundamentals` goes
through `build_store`, which always downloads every symbol's bars first: it would replace all
2,490,793 bar rows with whatever yfinance answers today and produce a different fingerprint,
breaking comparability with every recorded trial. Use the fundamentals-only refresh instead:

```bash
# From the repo root. SEER_ENV_FILE is resolved against your cwd, so run it from there or
# give it an absolute path -- a relative one that misses falls through to the ambient
# DATABASE_URL_UNPOOLED, which is Neon.
SEER_ENV_FILE=.env.local-train \
  engine/.venv/bin/python -m seer_engine research_store <<M15_REFRESH_FLAG>>
engine/.venv/bin/python -m seer_engine research_store --verify     # the new fingerprint
engine/.venv/bin/python -m seer_engine research_store --coverage   # the new number
python3 ~/.claude/skills/sync-research-store/sync_store.py push --keep 0
```

It copies `bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` byte for byte, writes a new
`fundamentals.csv`, re-seals and swaps atomically; only the panel and the fingerprint change.
`push --keep 0` matters: a plain `push` prunes to the newest three versions
(`sync_store.py:294` calls `_prune(tok, keep=args.keep)` with `KEEP_VERSIONS = 3`), and the
version it drops is the oldest — possibly the one you would roll back to.
```

**Impact:** the runbook stops shipping executable Python that a reader can paste and
mis-measure with. The §1.3 lesson survives verbatim in the "Presence is never evidence"
paragraph. Three fenced code blocks shrink to three one-line commands.

---

### Step 8b: Retire the runbook's stale `ticker_cik.csv` scope lines and its duplicated recipe

**File:** `docs/runbooks/data-pipeline.md:12`, `:15`, `:44`, `:51`, `:151-175`
**Change:** assigned to this phase by the reconciler. Phase 2 moves `cik.SINCE` from 2015-01-02
to 2009-01-01 and re-scopes the file from 795 to 913 symbols; phase 2 owns `engine/data/SOURCES.md`
and updates it, but **nobody owned these runbook lines** and they are false the moment phase 2
lands. This phase owns `docs/runbooks/data-pipeline.md`, so they are its.

**8b-i — the scope lines.** `grep -n '2015-01-02' docs/runbooks/data-pipeline.md` and fix only
the ones describing the **ticker→CIK map / fundamentals** scope (`:15`, `:51` in the draft
numbering). **Lines 12 and 44 describe BARS**, whose `backfill` `DEFAULT_START` is genuinely
still 2015-01-02 and is a different constant that phase 2 explicitly did not move. Changing them
would be a false claim about the bars pipeline. Check each line's subject before touching it:

```bash
cd "$SEER_WT"
grep -n '2015-01-02\|ever-member' docs/runbooks/data-pipeline.md | head -20
```

The fundamentals-scope lines become *"every S&P 500 / Nasdaq-100 ever-member on or after
2009-01-01 (`seer_engine.cik.SINCE`), `<<M14_TICKER_ROWS>>` symbols"*. If phase 2's summary does
not carry its symbol count, write *"`seer_engine.cik.SINCE`, currently 2009-01-01"* and no
number — the slot rule applies here as everywhere.

**8b-ii — the duplicated recipe, `:151-175`.** Replace the numbered steps 1–6 with a pointer.
The runbook's copy says *"the automated pass resolved 98 of 133 (94 exact, 4 fuzzy)"*, a count
taken over a 133-symbol delisted residue that phase 2's 795 → 913 re-scope moves; it also knows
nothing of phase 2's `EARLY` screen or its `MANUAL` empty-start sentinel. **Do not restate the
new counts here** — that would be stating a figure this phase did not run (invariant 10), and
phase 2 already keeps them current in exactly one place. Replace the body of the section,
keeping its heading and its opening "a ticker alone never identifies a company" paragraph, with:

```markdown
The recipe lives in **`engine/data/SOURCES.md`**, under `ticker_cik.csv` — one copy, kept
current by whoever re-vendors the file, carrying the live row and tier counts, the three refusal
lists (`UNRESOLVED`, `SCREEN`, `EARLY`), the `MANUAL` empty-start sentinel and the rule that an
`end_date` is never pushed forward. Do not duplicate it here; a second copy goes stale silently
and this one did.

Two things that are true whatever the counts say, and are the reason the file is hand-audited:

- **Read every fuzzy row by hand before committing it.** The shipped file carries *zero* fuzzy
  rows deliberately: the automated name screen once matched "Harman International" to AMERICAN
  INTERNATIONAL INDUSTRIES (`0001073146`) — a different company entirely; the real HAR is
  `0000800459`. A fuzzy name match is a suggestion, never evidence.
- **Validate before committing:** `engine/.venv/bin/pytest engine/tests/test_cik.py -q`. It
  checks the header, rejects overlapping intervals and a CIK that is not 10 digits, and asserts
  each recycled ticker resolves to the company that held it during its membership rather than to
  the current holder.

Then update the sha256 block in `engine/data/SOURCES.md`, and re-ingest the changed tickers'
facts under their corrected CIKs with
`engine/.venv/bin/python -m seer_engine fundamentals --symbols <the changed tickers>` —
`--symbols` ignores `fundamentals_log`, which is what makes it the tool for this.
```

**Impact:** the runbook stops carrying a second, drifting copy of a recipe phase 2 keeps
correct, and stops claiming a scope the tree no longer has. No number this phase did not measure
is written. `git diff docs/runbooks/data-pipeline.md` now has two hunks: this one and Step 8's.

---

### Step 9: Replace §4's estimates with measurements, and annotate the table

**File:** `docs/plans/2026-10-05-fundamental-panel-coverage.md:153-160`
**Change:** §4's accounting table **only**. The `today — 4%` row is left exactly as recorded
(it is a span estimate from 2026-10-05, not this measure, and the brief forbids changing it).
Sections 1, 2, 3, 5, 6, 7 and 8 are history and are not touched — not a word, not a heading.

Replace from `Honest accounting of what the two fixes reach:` through the table's last row:

**Code:**

```markdown
Honest accounting of what the two fixes reach:

| State | Cost | Coverage of the 19.8-year dev window |
|---|---|---|
| today | — | **4%** (zero until 2015) |
| + Fix A (re-vendor intervals) | a CSV regeneration, no downloads | **`<<M6_FIXA_FRACTION>>`** (2013 →), **measured, upper bound** |
| + Fix B (`--since-filed 2009`) | ~13 min, 776 free requests, ~250 MB **local** | **`<<M4_COVERAGE_FRACTION>>`** (2009 →), **measured, upper bound**, XBRL-limited |
| 1996–2008 | impossible at any price | — |

> **Measured `<<RUNDATE>>`**, replacing the `~14%` and `~30%` estimates this table shipped with.
> Store `<<M1_NEW_FP>>` (the 2026-10-05 store was `e597367b…`), `<<M2_PANEL_SYMBOLS>>` panel
> symbols, `<<M12_FACT_ROWS>>` facts. "Coverage" is `research_store --coverage`'s measure: the
> fraction of monthly sample dates from 1996-01-02 to 2015-10-16 on which the panel can rank at
> least 20 symbols whose newest fact was filed within 400 days — the same eligibility gate
> `f_fundamental` applies, so it predicts rankability rather than fact-existence. **It is an
> upper bound**: the measure reads no bars, so index membership on the date, `min_price` and
> `min_dollar_volume` are not applied and can only remove symbols from it. The `+ Fix A`
> row is that same measure over the same refreshed panel with facts filtered to
> `filed >= 2013-01-01`, which is what Fix A alone would have reached. The `today` row's `4%` is
> left as it was recorded — it is a span estimate (9 months of 19.8 years), not this measure;
> running this measure against the pre-fix store `e597367b…` reports
> **`<<M7_BASELINE_FRACTION>>`**.
>
> What Fix B actually recovered, by `filed` year, against the ~90k/year the 2013-onward baseline
> holds: 2009 `<<M8_FACTS_2009>>`, 2010 `<<M9_FACTS_2010>>`, 2011 `<<M10_FACTS_2011>>`,
> 2012 `<<M11_FACTS_2012>>`. XBRL phased in by filer size — large accelerated filers from roughly
> FY2009, all filers by FY2011 — so the early years are partial and size-biased by construction.
>
> **This does not solve the test problem, and §5 below still stands unchanged.** The dev window
> opens 1996-01-03 and no XBRL exists before roughly 2009, so about thirteen of its nineteen
> years are permanently uncoverable from this source. `>= 100 trades` over a window most of which
> holds cash is not reachable, so **the `>= 100 trades` gate remains unreachable for a
> fundamentals method on this dev window**. The test-window decision of §5 remains **unmade** and
> out of scope.
```

**Impact:** §4 stops carrying two numbers nobody measured. The decision record's conclusion is
unchanged — and the annotation says so explicitly, so a later reader cannot mistake a measured
coverage improvement for a solved test problem.

---

### Step 10: The M0005 docstring preamble — point it at the gate, and say the id is spent

**File:** `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py:18-28`
**Change:** replace the "READ THIS BEFORE RUNNING" paragraph and its `python -c` one-liner.
Lines 1-17 (the title, Source, Idea and allocator paragraphs) and line 29's closing `"""` frame
it; **everything from line 31 down — the imports, `ADDED`, `VALUE`…`COMPOSITE_RANK`, `_v`,
`METHOD`, the six `Candidate`s, `seen_keys` — is untouched.** Changing any of them would change
the file's `source_sha`, and the id is already spent.

**Code:** the complete replacement for lines 18–28 (the docstring's last paragraph; the
`"""` on line 29 stays):

```python
READ THIS BEFORE RUNNING -- THERE IS NOTHING HERE LEFT TO RUN. M0005 is ``rejected``: its six
trials are recorded and its six ``config_digest``s are spent. ``runner.preflight`` refuses a
second run of any method and refuses a repeated digest on the dev window, so this file is a
record, not a runnable candidate. The hypothesis is **untested, not refuted** -- the panel the
six trials ranked on covered about 4% of the dev window, so what they measured was a book
holding cash, not the factor premia. ``lab show M0005`` carries the full analysis as two notes.

A re-test is therefore a NEW method with ``source_kind='variation'`` and ``parent_id='M0005'``,
and it must not be minted until the coverage gate reports a number worth testing::

    python -m seer_engine research_store --coverage

That prints the panel's rankable count on each sampled dev-window date and one fraction: the
share of dates on which it can rank at least ``top`` names from facts filed within
``max_stale_days``. ``lab run`` runs the same measure after it loads the store and REFUSES any
method whose allocator is ``MarketAware`` -- ``FUNDAMENTAL`` is one -- when that fraction is
below ``fundamentals.coverage.MIN_DEV_COVERAGE``; ``--allow-coverage F`` lowers the floor for a
single run and prints the number loudly.

The gate this replaced was ``'fundamentals.csv' in manifest['files']`` -- binary where the risk
is continuous, so a store carrying a panel over a sliver of the window passed it. That check is
what spent this id, and ``docs/plans/2026-10-05-fundamental-panel-coverage.md`` section 1.3 is
why it is gone. Note also that ``panel.as_of`` ALWAYS returns a ``Snapshot``, an empty husk with
``observations == {}`` when nothing is known: presence is never evidence of coverage here.

Measured <<RUNDATE>> after Fix A and Fix B: <<M4_COVERAGE_FRACTION>> of sampled dev-window dates
can rank 20 names, and that figure is an UPPER BOUND -- the measure reads no bars, so index
membership, ``min_price`` and ``min_dollar_volume`` are not applied and can only remove symbols
from it. That is better data, not a valid test. The dev window opens 1996-01-03 and
XBRL does not exist before roughly 2009, so the ``>= 100 trades`` gate stays unreachable for a
fundamentals method on this window whatever the ingest does -- see section 5 of that doc, and do
not read the improved number as permission to mint the variation.
```

**Impact:** an operator who opens this file is told the id is spent and is handed the engine's
gate instead of a manifest lookup. `engine/tests/test_strategy_purity.py` and the lab's method
tests read `METHOD`, not the docstring, so nothing in the suite changes. If a test pins this
file's `source_sha`, **stop** — a docstring edit would move it; report that and leave the file
alone (grep: `grep -rn 'm0005' engine/tests | grep -i 'sha\|digest'`).

---

### Step 11: `engine/package_readme.md` — the new command and the current store

**File:** `engine/package_readme.md:324-325`, after `:339`, after `:1346`, after `:1350`
**Change:** four insertions. (Measured: `package_readme.md` carries **no** `fundamentals` or
`lab` command section and **no** ingest floor dates — `grep -n '2013-01-01\|since-filed'` returns
nothing — so "the new floors" has no home here beyond the store section. Do not invent one.)

**11a — the usage block at `:324-325`:**

```
python -m seer_engine research_store [--dry-run] [-v] [--store STORE] [--batch-size BATCH_SIZE] [--verify]
                                    [--with-fundamentals] [<<M15_REFRESH_FLAG>>] [--coverage]
```

**11b — a new bullet immediately after the `--with-fundamentals` bullet (after `:339`):**

```markdown
- **`<<M15_REFRESH_FLAG>>`** (fundamental-panel-coverage) rewrites `fundamentals.csv` **only**:
  `bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` are carried over from the existing
  store byte for byte and every `_COUNT_KEYS` value with them, so the panel changes and the bar
  history does not. It exists because `build_store` always downloads every symbol's bars first,
  and two yfinance crawls on two days give two different fingerprints — which would break
  comparability with the trials already recorded. It needs `DATABASE_URL_UNPOOLED` (set
  `SEER_ENV_FILE` to the train env file) and re-seals and swaps atomically; nothing is written
  on failure.
- **`--coverage`** (fundamental-panel-coverage) loads the store and prints, for each sampled
  dev-window date, how many symbols the panel can actually rank — a symbol counts only when
  `as_of` returns a snapshot with **non-empty `observations`** whose newest fact was filed within
  `max_stale_days` — plus one fraction over the window. `as_of` never returns `None`, so a
  presence check measures nothing; this is the content check, and it is the same measure
  `lab run` refuses on below `fundamentals.coverage.MIN_DEV_COVERAGE`. No network, no database.
  It reads no bars, so membership, `min_price` and `min_dollar_volume` are not applied and the
  fraction is an **upper bound**: below the floor is conclusive, above it is necessary and not
  sufficient.
```

**11c — a new bullet after `run_checks` (after `:1346`):**

```markdown
- the fundamentals-only refresh (fundamental-panel-coverage): reuses an existing store's four
  required files byte for byte, writes a new `fundamentals.csv`, re-seals and `_swap_in`s. The
  manifest's copied counts (`bar_rows`, `dividend_rows`, `fx_rows`, `symbols_requested`,
  `symbols_served`) are carried over, never re-derived from a download.
```

**11d — after the committed-store block (after `:1350`), a new line. The existing
`**The committed store**` line stays: it is the phase-4/phase-13 record and is history.**

```markdown
**The current train/eval store** (fundamental-panel-coverage, `<<RUNDATE>>`): fingerprint
`<<M1_NEW_FP>>`, superseding `e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3`.
Same bars — the refresh copied them byte for byte — with a panel rebuilt from facts filed since
2009-01-01 against the re-vendored `ticker_cik.csv`. Dev-window coverage `<<M4_COVERAGE_FRACTION>>`
(`research_store --coverage`); it was `<<M7_BASELINE_FRACTION>>` before. That is better data and
not a valid test: the dev window opens in 1996 and XBRL starts around 2009, so a fundamentals
method still cannot reach the lab's `>= 100 trades` gate on it. The store syncs between machines
with `/sync-research-store` (`push`/`pull`, content-addressed on this fingerprint, Vercel Blob);
push it with `--keep 0`, because a plain `push` prunes to the newest three versions.

Both coverage figures above are **upper bounds** — the measure reads no bars, so membership,
`min_price` and `min_dollar_volume` are not applied.
```

**Impact:** the readme documents the two new flags and names the store a reader will find on
disk. Phases 1 and 4 do not touch `package_readme.md` (their file lists in the index do not
include it), so there is no conflict.

---

### Step 12: Push the refreshed store and record the content hash

**File:** none (shell only)
**Change:** publish the store so the other laptop gets the same fingerprint instead of rebuilding
a different one.

**Code:**

```bash
S=~/.claude/skills/sync-research-store/sync_store.py
cd "$SEER_MAIN"
python3 "$S" status | tee "$SCRATCH/store-status-pre-push.json"
python3 "$S" push --keep 0 | tee "$SCRATCH/store-push.json"
python3 "$S" list  | tee "$SCRATCH/store-list-after.json"
```

Record from `store-push.json`: `fingerprint` (must equal `<<M1_NEW_FP>>`), `pathname`
(`seer/research-store/<fp>.tar.gz`), `mb` → slot `<<M13_PUSH>>`. Confirm in
`store-list-after.json` that
`e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3` is **still listed**.

`--keep 0` is not optional: `cmd_push` otherwise prunes to `KEEP_VERSIONS = 3`
(`sync_store.py:294, 379`), and the object it drops is the oldest — possibly the one this phase's
rollback depends on. The skill also refuses to push a store that does not verify, which is a
second check on Step 4.

Only after `store-push.json` reports success: `rm -rf /home/miftah/.seer-store-backup-e597367b`
(optional — keeping it costs 236 MB and buys a rollback that needs no network).

**Impact:** one new Blob object. Nothing is deleted. Neon is untouched. No repo file changes.

---

### Step 13: Full suite, clean tree

**File:** none
**Change:** prove the phase broke nothing and left nothing behind.

**Code:**

```bash
cd "$SEER_WT"
"$SEER_PY" -m pytest engine/tests -q 2>&1 | tail -5

PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
"$SEER_PY" -m pytest engine/tests -q 2>&1 | tail -5

git status --porcelain
git diff --stat
```

`conftest.py` gives every DB test a throwaway schema `t_<hex>` and never touches `public`, where
the training facts live, so the second run is safe against the same container that Phase 3 wrote
to.

**Impact:** `git status --porcelain` must list only the four modified files. `engine/.venv/` and
`engine/.research/` are gitignored; `$SCRATCH` and `$BACKUP` are outside the repo by construction.

---

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/fundamental-panel-coverage && "$SEER_PY" -c 'import seer_engine'`
(after Step 0 creates the venv — the worktree ships without one)

**Tests:**

```bash
"$SEER_PY" -m pytest engine/tests -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  "$SEER_PY" -m pytest engine/tests -q
```

**The test delta, not an absolute.** This phase adds **+0** tests: it runs the suite, it does not
extend it. The only `engine/src` change it makes is a docstring. The number on screen is whatever
phases 1 (+27), 2 (+5), 3 (+0) and 4 (+13) left behind — off the `2dad9ff` baseline of 2216
passed / 332 skipped that is **2261 passed, 332 skipped** with all four merged, but report the
inherited figure as measured rather than asserting it. The binding rule is invariant 1: the
passing count may only go up, and no existing test may change its result. The 332 skips are the
DB tests with `PG_TEST_URL` unset; with it exported the skip count drops and nothing fails.

**Manual check:**

1. `grep -n 'python -c\|<<.EOF' docs/runbooks/data-pipeline.md` finds **no** coverage or manifest
   snippet in the `### The lab and fundamentals` section.
1b. `grep -n '98 of 133' docs/runbooks/data-pipeline.md` returns nothing, and
   `grep -n '2015-01-02' docs/runbooks/data-pipeline.md` returns only lines whose subject is
   **bars** (`backfill`'s `DEFAULT_START`, which phase 2 deliberately did not move).
2. `grep -n 'python -c' engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` returns
   nothing.
3. `git diff docs/plans/2026-10-05-fundamental-panel-coverage.md` touches **only** lines inside
   §4. If the diff reaches §1, §2, §3, §5, §6, §7 or §8, revert and redo.
4. `git diff engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` touches **only**
   lines 18–28. If `METHOD`, `ADDED`, any `FundamentalParams` or any `Candidate` appears in the
   diff, revert and redo.
5. `grep -c '<<' docs/runbooks/data-pipeline.md docs/plans/2026-10-05-fundamental-panel-coverage.md engine/package_readme.md engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py`
   returns **0** for every file: an unfilled slot that ships is a worse failure than a bad number.
6. `git log --oneline -1` on this phase's commit; `git status --porcelain` lists only the four
   modified files.

**Exit criteria:**

- `research_store --coverage` ran against the store refreshed from Phase 3's facts, and its
  output is in the runbook character for character, with the run date and the store's new
  fingerprint next to it.
- §4's `+ Fix A` and `+ Fix B` rows carry measurements (or, for `+ Fix A`, the explicit words
  "not separately measured" and why), and the table is annotated with the date, the fingerprint
  and the definition of "coverage" used.
- Both the manifest one-liner and the coverage snippet are gone from the runbook and from the
  M0005 docstring; `research_store --coverage` stands in their place.
- The runbook and §4 each state, in these terms: the dev window opens 1996-01-03 and no XBRL
  exists before ~2009, so roughly thirteen of its nineteen years are permanently uncoverable;
  the `>= 100 trades` gate is therefore still unreachable for a fundamentals method on this dev
  window; the test-window decision remains unmade and out of scope.
- §6.1 is recorded closed, with the three test names and three `Market(` sites as evidence, and
  **no new code**.
- The store is pushed, `e597367b…` is still listed remotely, and the push's fingerprint is
  recorded.
- Full suite green with and without `PG_TEST_URL`; `git status` clean of strays.
- **No `lab run` was invoked, no method id was minted, the test window was not touched.**

---

## Handoffs

Found while planning; deliberately not done here.

1. **RESOLVED — `SEER_ENV_FILE` is absolute, set-wide.** The draft index and the decision doc §3
   both wrote the relative `SEER_ENV_FILE=.env.local-train`; `.env*` is gitignored so the file
   does not exist in the worktree, `config.env_file()` resolves a relative path against the cwd,
   and `DATABASE_URL_UNPOOLED` then falls through to the ambient environment, which points at
   **Neon** — an invariant-8 violation waiting for a quiet night. Every phase that touches a
   database now uses `/home/miftah/seer/.env.local-train` and proves the resolved DSN names
   `localhost:55432` before writing. Phases 3, 4 and 5 all carry it. Index `## Decisions`, row C3.
2. **RESOLVED — `PYTHONPATH`, not a worktree venv, set-wide.** The worktree has no
   `engine/.venv`, the main checkout's is an editable install of the main checkout
   (`__editable__.seer_engine-0.1.0.pth` → `/home/miftah/seer/engine/src`), and
   `engine/pyproject.toml` sets no pytest `pythonpath`, so every unguarded command — pytest
   included — runs main's code and reads main's `engine/data/`. All five phases now open with the
   same **Runtime preamble**: `PYTHONPATH=$SEER_WT/engine/src` over the main checkout's venv, and
   **no worktree venv is built**, so the 2216/332 baseline stays measured in one interpreter.
   Index `## Decisions`, row C2.
3. **RESOLVED — `sync_store.py push` prunes by default** (`KEEP_VERSIONS = 3`, `cmd_push` calls
   `_prune(tok, keep=args.keep)` at `sync_store.py:294`). The draft index's Rollback paragraph
   claimed the push "adds an object and deletes nothing"; **the index has been corrected**, and
   what actually makes the rollback safe is this phase's `--keep 0` plus the local backup at
   `/home/miftah/.seer-store-backup-e597367b`, taken outside the repo in Step 1. Index
   `## Decisions`, row C4b.
4. **`engine/package_readme.md:1348`'s "committed store" fingerprint
   `5451195f…`** predates `e597367b…` by two stores. Left as the historical record and a new line
   added beside it rather than rewritten, because it names a specific earlier phase's artefact.
   A future readme pass may want to reconcile the two.
5. **`http.get_json` takes no `headers` argument** (decision doc §6.3). Conditional on a phase
   already touching `http.py`; none does, and this one certainly does not.
6. **RESOLVED — `docs/runbooks/data-pipeline.md` §"Re-vendoring `engine/data/ticker_cik.csv`"
   (`:151-175`) is now this phase's**, together with the stale scope lines at `:12,:15,:44,:51`.
   It is the one gap in this plan set's Impact-Point coverage, and rule 5 assigns it to the phase
   that already owns the file. The honesty objection stands and is honoured: **Step 8b replaces
   the stale counts with a pointer to `engine/data/SOURCES.md`** — which phase 2 owns and keeps
   current — rather than restating a figure this phase did not run. No number is invented.
7. **TMUS / DXC / LDOS membership hulls open before the ticker existed** (phase 2 found them;
   same class of defect as `NDOI`). It is a `engine/data/membership_overrides.csv` problem, a
   different subsystem, and **out of this plan set's scope**: no phase owns it, no card id is
   invented for it, and it is recorded as a follow-up in the index's `## Decisions`, row C7i.
   Do not fold it in here.

---

## Rollback

This phase alone, in order of what it touched:

1. **The documents.** One commit. `git revert <sha>` restores all four files, including the
   runbook snippet and §4's estimates.
2. **The store on disk.** It is gitignored, so git does not carry it. Either
   `cp -a /home/miftah/.seer-store-backup-e597367b /home/miftah/seer/engine/.research` (if the
   backup from Step 1 was kept — instant, no network), or
   `python3 ~/.claude/skills/sync-research-store/sync_store.py pull` after re-pointing the remote
   pointer at `e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3`. `pull` refuses
   to install a store whose fingerprint does not match the pointer, and it is atomic: it extracts
   to `.research.incoming-<pid>`, verifies there, and only then swaps.
3. **The Blob object.** `push --keep 0` added one object and deleted none, so there is nothing to
   undo. If quota matters, `python3 $S prune --keep N` is reversible only by re-pushing a store
   you still hold — prune nothing until the other laptop has pulled.
4. **The database.** Untouched by this phase: it is read only, and only through Phase 4's
   refresh. Phase 3's rollback is Phase 3's.
5. **Neon.** Never contacted.
6. **Method ids and trials.** Nothing to roll back: `lab run` was never invoked, no method was
   minted, no `config_digest` was spent, and the post-2015 test window was not touched. That is
   the point of the boundaries above — this phase is, by construction, the reversible one.

`$SCRATCH` and `$BACKUP` are outside git; `rm -rf` them freely. **No venv was created** — the
set-wide rule is `PYTHONPATH` over the main checkout's venv — so there is none to remove.
