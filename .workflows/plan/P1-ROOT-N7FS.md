> Adopted from `/home/miftah/seer/.workflows/orchestration/journal-versioning/PLAN.md` phase 6. Source: `.workflows/plan/journal-versioning/phase-6.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 6: Backfill the 5 byte-identical pairs, 500→499 first

**Plan set:** `JOURNAL_VERSIONING_PLAN.md`
**Analysis:** `docs/analyzer/20261020-162050-J7K2_code_analyzer.md`
**Satisfies:** R3 — thread the duplicates that already exist, so the owner stops reading the same note twice
**Depends on:** Phase 2 (`lab link`), which depends on Phase 1 (schema 8)
**Difficulty:** NORMAL
**Package:** `lab/` (data only — **no source file is edited in this phase**)

---

## Goal

After this phase, five rows in `lab/lab.sqlite` carry a `supersedes` link they did not carry
before, and **nothing else in the journal has changed**. The 500 rows become 495 documents:
M0179's note is one document at version 3, and M0131's, M0024's and M0127's are one document each
at version 2. The 499/500 pair the owner pointed at is threaded, and the proof that no `body` was
touched is a recorded digest, not an assurance.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none.
**Renames:** none.
**Creates:** no symbol. Five `UPDATE insights SET supersedes = ?` writes on rows `230, 290, 498,
499, 500` of the committed `lab/lab.sqlite`, plus whatever byte change that makes to
`web/data/lab.json` (possibly none — see §"The lab.json diff may be empty").
**Signature changes:** none.

**Requires (from earlier phases):**

- **Phase 1** — `lab/lab.sqlite` is committed at `SCHEMA_VERSION = "8"`, the `insights` table has
  `supersedes INTEGER REFERENCES insights(id)` and `doc_key TEXT`, the narrowed
  `insights_no_update` trigger permits `supersedes` `NULL`→value exactly once, the partial unique
  index `insights_one_successor` exists, and `store.set_supersedes` validates (predecessor id <
  successor id, not self, exists, same `method_id`).
- **Phase 2** — `lab link <successor-id> --supersedes <predecessor-id>` exists as a `lab`
  subcommand, routes through `store.set_supersedes`, exits **0** on success and **2** on a rules
  refusal.

  > **ASSUMPTION, stated because `phase-2.md` did not exist when this plan was written.** The
  > invocation above is taken verbatim from the plan index (`JOURNAL_VERSIONING_PLAN.md` §Phase 2:
  > *"`lab link ID --supersedes ID` (set the link on an existing row — the backfill tool phase 6
  > runs)"*). The argument order assumed here is **`lab link <row-that-is-newer>
  > --supersedes <row-it-replaces>`**, i.e. the positional is the *successor*, matching
  > `store.set_supersedes(conn, id, supersedes)` and matching `lab insight --supersedes ID` where
  > the new row names the old one. **Step 2 of this phase verifies that reading against
  > `lab link --help` before any write**, and the five commands in Step 4 must be re-ordered if
  > phase 2 chose the opposite order. If `lab link` is missing a capability this phase needs, that
  > is a **phase 2 gap**: report it to the coordinator, do not patch `commands/lab.py` here.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/lab/store.py` (Phase 1)
- `engine/src/seer_engine/commands/lab.py` (Phase 2)
- `real_costs.py`, `survivorship_check.py`, `exposure.py`, `gate_probe.py`, `prereg.py` (Phase 3)
- `store.snapshot`, `web/lib/sera/types.ts` (Phase 4)
- `web/app/sera/journal/*` (Phase 5)
- `engine/src/seer_engine/lab/hardgate.py` — the concurrent `analyze-fold-selector` session owns it
- every `insights` row that is **not** one of `230, 290, 498, 499, 500`

---

## Files

| File | Action | What changes |
|---|---|---|
| `lab/lab.sqlite` | modify (data) | `insights.supersedes` set on exactly 5 rows: `230→227`, `290→289`, `498→493`, `499→320`, `500→499`. No other column on any row. |
| `web/data/lab.json` | regenerate | written by `lab stage`; the diff is **empty unless Phase 4 has already landed** (see below) |

No source file is touched. `git diff --stat` for this phase's commit must list at most those two
paths.

---

## Measured ground truth (read out of `lab/lab.sqlite` on 2026-10-20 at base `15a9a9a`)

`PRAGMA table_info(insights)` → `id, kind, title, body, method_id, added` (schema_version 7,
pre-Phase-1). 500 rows, ids 1..500 contiguous.

**The twelve title collisions, and why only five are linkable.** Grouping all 500 rows by
`(method_id, title)` gives ten groups of size > 1, holding twelve rows beyond their group's first:

| ids | method | bodies identical? | verdict |
|---|---|---|---|
| 48, 54 | M0007 | **no** | different variants — leave as siblings |
| 50, 52 | M0008 | **no** | `M0008-C10` vs `M0008-N30-C07` — leave as siblings |
| 51, 53 | M0022 | **no** | different variants — leave as siblings |
| 125, 126 | — (no method) | **no** | 126 supersedes 125 *in prose*; still not byte-identical — out of scope |
| 227, 230 | M0131 | **yes** | **link** |
| 289, 290 | M0024 | **yes** | **link** |
| 320, 499, 500 | M0179 | **yes** | **link twice** |
| 390, 391 | — (no method) | **no** | leave as siblings |
| 466, 467, 468 | M0260 | **no** | `M0260-M-NATIVE` / `-M-G12` / `-M-G3`, trials n=835/838/836 — **three measurements**; linking them would hide two |
| 493, 498 | M0127 | **yes** | **link** |

Grouping instead by `(method_id, kind, title, body)` — byte-identical in **both** text columns —
gives exactly four groups, and exactly the five successor rows this phase links:

```
method=M0131 kind=observation ids=[227, 230]
method=M0024 kind=observation ids=[289, 290]
method=M0179 kind=observation ids=[320, 499, 500]
method=M0127 kind=observation ids=[493, 498]
```

Per-pair detail, all five confirmed `title_same=True body_same=True method_same=True
kind_same=True`:

| pair | method | kind | body length | added (predecessor → successor) |
|---|---|---|---|---|
| 227 → 230 | M0131 | observation | 1740 / 1740 | 2026-10-14T05:20:21Z → 2026-10-14T05:21:55Z |
| 289 → 290 | M0024 | observation | 872 / 872 | 2026-10-16T13:39:41Z → 2026-10-16T13:40:07Z |
| 493 → 498 | M0127 | observation | 1087 / 1087 | 2026-10-20T08:24:45Z → 2026-10-20T08:52:25Z |
| 320 → 499 | M0179 | observation | 1095 / 1095 | 2026-10-17T09:37:11Z → 2026-10-20T08:54:02Z |
| 499 → 500 | M0179 | observation | 1095 / 1095 | 2026-10-20T08:54:02Z → 2026-10-20T09:09:09Z |

Every pair shares `method_id`, so `store.set_supersedes`'s cross-method refusal cannot fire; every
predecessor id is lower than its successor's, so the id-ordering refusal cannot fire; no
predecessor is named twice, so `insights_one_successor` cannot fire.

**Content digest at base `15a9a9a`, over `(id, kind, title, body, method_id, added)` for all 500
rows ordered by id:**

```
rows=500 digest=04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed
```

This number is the spine of the phase. It is unchanged by Phase 1 (the v7→v8 rebuild copies every
row with its id) and it must be unchanged by this phase. Step 1 re-measures it; Step 6 asserts it.

**What Phase 5 will have to render** — these four chains are the *only* ones that will exist when
this branch lands, so the reader has exactly this much to show:

| document head | version | chain (oldest → newest) | kind |
|---|---|---|---|
| 230 | 2 | 227 → 230 | observation |
| 290 | 2 | 289 → 290 | observation |
| 498 | 2 | 493 → 498 | observation |
| 500 | **3** | 320 → 499 → 500 | observation |

495 heads, 5 non-head rows, 500 rows total. No chain is longer than 3 and no document has siblings
that also need a version chip.

---

## The environment, and the trap that eats this phase

The worktree `/home/miftah/.worktrees/seer/journal-versioning` has **no `engine/.venv`**. The only
venv on this machine is the main checkout's, and `seer_engine` installed there resolves to
`/home/miftah/seer/engine/src/seer_engine`, which makes:

```
config.REPO_ROOT            = /home/miftah/seer          # Path(__file__).resolve().parents[3]
store.DB_PATH               = /home/miftah/seer/lab/lab.sqlite
store.snapshot_path(DB_PATH)= /home/miftah/seer/web/data/lab.json
```

Running `lab link` that way would **write the main checkout's live shared database** — the one the
concurrent `analyze-fold-selector` session may be using — and `lab stage` would `git add` into
`main`, not onto this branch. That is the failure mode this phase must not have.

`PYTHONPATH` fixes it, verified in this worktree:

```
PYTHONPATH=/home/miftah/.worktrees/seer/journal-versioning/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -c "..."
→ REPO_ROOT:    /home/miftah/.worktrees/seer/journal-versioning
→ DB_PATH:      /home/miftah/.worktrees/seer/journal-versioning/lab/lab.sqlite
→ snapshot_path:/home/miftah/.worktrees/seer/journal-versioning/web/data/lab.json
```

**Define these once and use them in every command below.** Each Bash call is a new shell, so
re-export them in every call rather than assuming they persist.

```bash
export WT=/home/miftah/.worktrees/seer/journal-versioning
export PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$WT/engine/src
unset SEER_LAB_DB                 # must NOT point at the main checkout for this phase
export DB=$WT/lab/lab.sqlite
export LAB="$PY -m seer_engine lab --db $DB"
```

`--db $DB` is belt and braces on top of `PYTHONPATH`; pass it anyway, because a single missing
`PYTHONPATH` in one shell would otherwise silently retarget `main`.

### Concurrency

- **This worktree's `lab/lab.sqlite` is a branch copy, not the shared live database.** No explorer
  session writes to it. `SEER_LAB_DB` must stay unset here; exporting it to the main checkout is
  what would make this phase collide with `analyze-fold-selector`.
- **Merely connecting migrates.** `store.connect` runs `_migrate` and `executescript(_SCHEMA)`
  inside a write transaction, so *any* `lab` subcommand — including a read — can dirty the file.
  That is why every verification read in this plan goes through `sqlite3` with
  `file:...?mode=ro`, never through a `lab` command, and why Step 1 hashes the file before and
  after each read-only block.
- **Peer phase sessions share this worktree and therefore share one git index.** Phase 4 also runs
  `lab stage` on this same database. Step 5 checks `git diff --cached --name-only` before
  committing and does not blind-commit the index.
- **`pull --rebase` after a rejected push replays a stale `lab.sqlite`.** If the push in Step 7 is
  rejected, do **not** reflexively rebase: a rebase replays this branch's `lab.sqlite` blob over
  whatever the remote now holds. Re-read §Rollback → "If the push is rejected" before doing
  anything.

---

## Implementation Steps

### Step 1: Record the before-state, read-only

**File:** `lab/lab.sqlite:insights` (rows 1–500) — read only, nothing is written.
**Change:** capture four numbers that Step 6 re-measures: the content digest, the row count, the
file hash, and the test-window look count. Write the digest helper to the scratchpad, not to the
repo.

**Code:**

```bash
export WT=/home/miftah/.worktrees/seer/journal-versioning
export DB=$WT/lab/lab.sqlite
export SCRATCH=/tmp/claude-1000/-home-miftah-seer/225c5782-57d5-4a31-af53-62001edc6d75/scratchpad
mkdir -p "$SCRATCH"

cat > "$SCRATCH/insight_digest.py" <<'PY'
"""Digest of the five protected insight columns across every row, ordered by id.

Phase 6 of journal-versioning writes exactly one column, `supersedes`, on exactly five rows.
Equality of this digest before and after is the strongest available proof that the narrowed
`insights_no_update` trigger did its job on real data: not one body, title, kind, method_id or
added moved. Opened read-only (`mode=ro`) so that measuring never migrates the file.
"""
import hashlib
import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1]).resolve()
con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
rows = con.execute(
    "SELECT id, kind, title, body, method_id, added FROM insights ORDER BY id"
).fetchall()
h = hashlib.sha256()
for row in rows:
    for col in row:
        h.update(b"\x00" if col is None else str(col).encode("utf-8"))
        h.update(b"\x1f")
    h.update(b"\x1e")
con.close()
print(f"rows={len(rows)} digest={h.hexdigest()}")
PY

sha256sum "$DB" | tee "$SCRATCH/before.dbhash"
python3 "$SCRATCH/insight_digest.py" "$DB" | tee "$SCRATCH/before.digest"
python3 -c "
import json, sys
d = json.load(open('$WT/web/data/lab.json'))
print('summary.insights =', d['summary']['insights'])
print('summary.testLooks =', d['summary']['testLooks'])
print('len(insights) =', len(d['insights']))
"
sha256sum "$DB"   # unchanged by the reads above
```

**Expected, if Phase 1 has landed as specified:**

```
rows=500 digest=04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed
summary.testLooks = 4
```

`summary.insights` reads `500` if Phase 4 has not landed and `500` still if it has (nothing is
linked yet). The `sha256sum` printed last must equal the first — if it moved, something connected
with a `lab` command; `git checkout -- lab/lab.sqlite` and start again.

**STOP condition:** if the digest is **not**
`04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed`, a row's content has changed
since `15a9a9a`. That is an invariant-2 violation somewhere upstream. Report it to the coordinator
and write nothing.

**Impact:** none — this step is pure measurement.

---

### Step 2: Verify the five pairs, and verify `lab link`'s argument order

**File:** `lab/lab.sqlite:insights` — read only.
**Change:** re-assert, out of the live file rather than out of this plan, that each pair is
byte-identical in `title` **and** `body` and matches on `method_id` and `kind`; and read
`lab link --help` to confirm which positional is the successor.

**Code:**

```bash
export WT=/home/miftah/.worktrees/seer/journal-versioning
export DB=$WT/lab/lab.sqlite

python3 - "$DB" <<'PY'
import sqlite3
import sys
from pathlib import Path

PAIRS = [(227, 230), (289, 290), (493, 498), (320, 499), (499, 500)]  # predecessor -> successor

db = Path(sys.argv[1]).resolve()
con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
cols = [r[1] for r in con.execute("PRAGMA table_info(insights)")]
print("columns:", cols)
assert "supersedes" in cols, "phase 1 has not landed: no supersedes column"

total, lo, hi = con.execute("SELECT count(*), min(id), max(id) FROM insights").fetchone()
print(f"rows={total} ids {lo}..{hi}")
assert (total, lo, hi) == (500, 1, 500), "row set moved since 2026-10-20"

ok = True
for pred, succ in PAIRS:
    a = con.execute(
        "SELECT id, kind, title, body, method_id, supersedes FROM insights WHERE id = ?", (pred,)
    ).fetchone()
    b = con.execute(
        "SELECT id, kind, title, body, method_id, supersedes FROM insights WHERE id = ?", (succ,)
    ).fetchone()
    if a is None or b is None:
        print(f"{pred}->{succ}: MISSING ROW"); ok = False; continue
    checks = {
        "title identical": a[2] == b[2],
        "body identical": a[3] == b[3],
        "kind identical": a[1] == b[1],
        "method identical": a[4] == b[4],
        "predecessor id is lower": pred < succ,
        "successor not already linked": b[5] is None,
    }
    bad = [k for k, v in checks.items() if not v]
    status = "OK" if not bad else "REFUSE: " + ", ".join(bad)
    print(f"{pred}->{succ} method={a[4]} kind={a[1]} len={len(a[3])} {status}")
    ok = ok and not bad

# No predecessor may already have a successor (insights_one_successor is a unique index).
taken = dict(con.execute("SELECT supersedes, id FROM insights WHERE supersedes IS NOT NULL"))
for pred, succ in PAIRS:
    if pred in taken and taken[pred] != succ:
        print(f"REFUSE: {pred} is already superseded by {taken[pred]}"); ok = False
con.close()
print("ALL FIVE PAIRS VERIFIED" if ok else "DO NOT PROCEED")
sys.exit(0 if ok else 1)
PY

# Confirm the CLI's argument order before writing anything.
export PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$WT/engine/src
unset SEER_LAB_DB
$PY -m seer_engine lab link --help
```

**Impact:** none written. If the script prints `DO NOT PROCEED`, **stop and report** — the row ids
here were measured on 2026-10-20 at `15a9a9a`, and although insight ids only ever grow (so these
five are stable), a concurrent session appending rows is exactly why this check exists rather than
trusting the table above.

If `lab link --help` shows the positional is the **predecessor** rather than the successor, swap
every pair in Step 4 and say so in the commit's body.

---

### Step 3: Rehearse the whole backfill on a throwaway copy

**File:** `$SCRATCH/rehearsal.sqlite` — a copy. The real database is not opened for writing.
**Change:** run the exact five commands against a copy first. `lab link` has no `--dry-run` of its
own (`cli.py`'s `--dry-run` is not threaded through `commands/lab.py:run`, which calls
`store.connect(args.db)` and dispatches), and the `supersedes` link is **frozen once set** — so a
wrong link cannot be undone except by restoring the file. A rehearsal costs seconds and makes the
real run a repeat of something that already worked.

**Code:**

```bash
export WT=/home/miftah/.worktrees/seer/journal-versioning
export PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$WT/engine/src
unset SEER_LAB_DB
export SCRATCH=/tmp/claude-1000/-home-miftah-seer/225c5782-57d5-4a31-af53-62001edc6d75/scratchpad

cp "$WT/lab/lab.sqlite" "$SCRATCH/rehearsal.sqlite"
R="$PY -m seer_engine lab --db $SCRATCH/rehearsal.sqlite"

set -e
$R link 230 --supersedes 227   # M0131
$R link 290 --supersedes 289   # M0024
$R link 498 --supersedes 493   # M0127
$R link 499 --supersedes 320   # M0179, rung 1
$R link 500 --supersedes 499   # M0179, rung 2 — after 499 is itself linked
set +e

python3 "$SCRATCH/insight_digest.py" "$SCRATCH/rehearsal.sqlite"
python3 - "$SCRATCH/rehearsal.sqlite" <<'PY'
import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1]).resolve()
con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
links = con.execute(
    "SELECT id, supersedes FROM insights WHERE supersedes IS NOT NULL ORDER BY id"
).fetchall()
heads = con.execute(
    "SELECT count(*) FROM insights a "
    "WHERE NOT EXISTS (SELECT 1 FROM insights b WHERE b.supersedes = a.id)"
).fetchone()[0]
print("links:", links)
print("heads (documents):", heads, "of", con.execute("SELECT count(*) FROM insights").fetchone()[0], "rows")
PY
```

**Expected:**

```
links: [(230, 227), (290, 289), (498, 493), (499, 320), (500, 499)]
heads (documents): 495 of 500 rows
rows=500 digest=04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed
```

Every `link` prints nothing but its own success and exits `0`. **An exit code of 2 on any of the
five means the lab refused the request** — stop, read the message, and report it; do not retry
with different arguments.

Also rehearse the refusals once, to confirm Phase 1's guard rails are live before trusting them
with the real file:

```bash
$R link 500 --supersedes 320 ; echo "expect 2, got $?"   # 500 already linked: value -> value
$R link 230 --supersedes 230 ; echo "expect 2, got $?"   # self
$R link 227 --supersedes 230 ; echo "expect 2, got $?"   # predecessor id is higher
$R link 290 --supersedes 227 ; echo "expect 2, got $?"   # 227 already has a successor
```

**Impact:** the rehearsal file is disposable. Delete it at the end of the phase. Nothing in the
repository changes.

---

### Step 4: Run the five links on the real database

**File:** `lab/lab.sqlite:insights` rows `230, 290, 498, 499, 500` — the only rows written in this
whole phase.
**Change:** set `supersedes` on five rows, in this exact order. The order matters for the M0179
chain: `320 → 499` is linked **before** `499 → 500`, so the chain builds oldest-first and a reader
walking back from the head finds `500 → 499 → 320` in one pass.

**Code:**

```bash
export WT=/home/miftah/.worktrees/seer/journal-versioning
export PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$WT/engine/src
unset SEER_LAB_DB
export DB=$WT/lab/lab.sqlite
LAB="$PY -m seer_engine lab --db $DB"

set -e
$LAB link 230 --supersedes 227   # M0131: "A slower target for the learned ranker" — version 2
$LAB link 290 --supersedes 289   # M0024: "Same-month seasonality"                 — version 2
$LAB link 498 --supersedes 493   # M0127: "Rebalance on the slot, not the account" — version 2
$LAB link 499 --supersedes 320   # M0179: "Companies that crash with the market"   — version 2
$LAB link 500 --supersedes 499   # M0179: the row the owner pointed at             — version 3
set +e
```

Run them **one at a time** and check `$?` after each. `set -e` stops the block on the first
non-zero, which is what you want: a refusal part-way through leaves a partially linked database
that Step 6's verification will catch, and §Rollback restores it with one `git checkout`.

**Impact:** `lab/lab.sqlite` now differs from `HEAD`. `git diff --stat` shows it as a binary
change. Nothing else in the tree has moved yet.

---

### Step 5: `lab stage`, then commit by index

**File:** `lab/lab.sqlite`, `web/data/lab.json`.
**Change:** regenerate the web snapshot under the write lock, `git add` both, inspect the index,
commit.

**Order is not negotiable.** `test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database`
(`engine/tests/test_lab_snapshot.py:1054`) compares `web/data/lab.json` byte-for-byte against the
export of `lab/lab.sqlite`. Between Step 4 and `lab stage` that test is **red by design**. Stage
first, test second (Step 6), never the reverse.

**Code:**

```bash
export WT=/home/miftah/.worktrees/seer/journal-versioning
export PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$WT/engine/src
unset SEER_LAB_DB
export DB=$WT/lab/lab.sqlite

$PY -m seer_engine lab --db $DB stage
# must print exactly:
#   staged /home/miftah/.worktrees/seer/journal-versioning/lab/lab.sqlite
#   staged /home/miftah/.worktrees/seer/journal-versioning/web/data/lab.json
# If either path names /home/miftah/seer, PYTHONPATH was lost: `git -C /home/miftah/seer reset`
# the two paths, restore that checkout's files, and start this step again.

git -C "$WT" diff --cached --name-only
```

**The index check, and why it is here.** Phases 1–5 run in this same worktree and therefore share
one git index. `lab stage` adds exactly `lab/lab.sqlite` and `web/data/lab.json`; a peer session
may have staged its own files in between.

- If `git diff --cached --name-only` prints **exactly** `lab/lab.sqlite` and `web/data/lab.json`
  (or only `lab/lab.sqlite`, see below), commit by index:

  ```bash
  git -C "$WT" commit -m "lab: the journal's five identical re-runs are now versions, not new entries

Five journal entries said exactly what the entry before them said, word for word, because a
command was run twice. They are now linked to the entry they repeat, so Sera shows one note with
a version on it instead of the same note twice. M0179's reads version 3; M0131's, M0024's and
M0127's read version 2.

Nothing was rewritten. Only the link between entries changed: every title, body, kind, method and
date is byte-for-byte what it was, checked by hashing all five across all 500 entries before and
after. The seven other entries that share a title are different measurements of different
variants, and they stay separate on purpose.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
  ```

- If other paths are staged, **do not unstage them** — that would break the peer that staged them.
  Wait for that session to commit, re-run `lab stage`, and re-check. Only if the contamination
  persists, fall back to `git commit -- lab/lab.sqlite web/data/lab.json` and then immediately
  re-run the snapshot guard in Step 6 — a pathspec commit re-reads the working tree and loses the
  consistency `lab stage`'s exclusive lock bought.

**Never** `git add -A`, `git stash`, or `git reset --hard` in this worktree: peers are working in it.

**The `lab.json` diff may be empty, and that is correct.** `store.snapshot` builds each insight
field-by-field at `store.py:3002-3006`:

```python
"insights": [
    {"id": int(i["id"]), "kind": i["kind"], "title": i["title"], "body": i["body"],
     "methodId": i["method_id"], "added": i["added"]}
    for i in _dicts(conn, "SELECT * FROM insights ORDER BY id")
],
```

It does not publish `supersedes`, and `summary.insights` at `store.py:2988` is
`count("SELECT count(*) FROM insights")` — a row count. **Phase 4 owns both of those.** So:

- **If Phase 4 has not landed yet**, `lab stage` rewrites `web/data/lab.json` to identical bytes,
  `git add` stages nothing for it, and the commit carries `lab/lab.sqlite` alone. That does **not**
  violate the plan set's invariant 7 ("every commit that moves `lab.sqlite` also carries
  `lab.json`"): the snapshot is still exactly the export of the database, which is the thing the
  invariant and `test_the_committed_snapshot_is_the_export_of_the_committed_database` actually
  check. Record it in the commit body as "the published snapshot is unchanged; Phase 4 publishes
  the link".
- **If Phase 4 has landed**, `lab.json` gains `supersedes`/`docKey`/`version`/`supersededBy` on the
  five rows and `summary.insights` drops `500 → 495`. Both files are in the commit.

**Impact:** one commit on `feature/journal-versioning` carrying data only.

---

### Step 6: Prove the content did not move

**File:** none written. This is the exit-criteria measurement, and the scope asks for it as an
explicit recorded step rather than an assumption.
**Change:** re-measure the digest, the links, the head count and the look count, and assert each.

**Code:**

```bash
export WT=/home/miftah/.worktrees/seer/journal-versioning
export DB=$WT/lab/lab.sqlite
export SCRATCH=/tmp/claude-1000/-home-miftah-seer/225c5782-57d5-4a31-af53-62001edc6d75/scratchpad

echo "BEFORE: $(cat $SCRATCH/before.digest)"
echo "AFTER : $(python3 "$SCRATCH/insight_digest.py" "$DB")"

python3 - "$DB" "$WT/web/data/lab.json" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

EXPECT_LINKS = [(230, 227), (290, 289), (498, 493), (499, 320), (500, 499)]
EXPECT_DIGEST = "04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed"

db = Path(sys.argv[1]).resolve()
con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)

links = con.execute(
    "SELECT id, supersedes FROM insights WHERE supersedes IS NOT NULL ORDER BY id"
).fetchall()
assert [tuple(r) for r in links] == EXPECT_LINKS, f"links are {links}, expected {EXPECT_LINKS}"

rows = con.execute("SELECT count(*) FROM insights").fetchone()[0]
heads = con.execute(
    "SELECT count(*) FROM insights a "
    "WHERE NOT EXISTS (SELECT 1 FROM insights b WHERE b.supersedes = a.id)"
).fetchone()[0]
assert (rows, heads) == (500, 495), f"{heads} documents from {rows} rows"

# Walk every chain from its head and print the version each document reads.
def chain(head):
    out, cur = [head], head
    while True:
        prev = con.execute("SELECT supersedes FROM insights WHERE id = ?", (cur,)).fetchone()[0]
        if prev is None:
            return list(reversed(out))
        out.append(prev)
        cur = prev

for head in (230, 290, 498, 500):
    c = chain(head)
    method = con.execute("SELECT method_id FROM insights WHERE id = ?", (head,)).fetchone()[0]
    print(f"{method}: head {head} is version {len(c)} — chain {' -> '.join(map(str, c))}")

assert len(chain(500)) == 3, "M0179's note must read version 3"
for head in (230, 290, 498):
    assert len(chain(head)) == 2, f"head {head} must read version 2"

# No row may carry doc_key: phase 3 writes that on NEW rows; phase 6 writes none.
if "doc_key" in [r[1] for r in con.execute("PRAGMA table_info(insights)")]:
    n = con.execute("SELECT count(*) FROM insights WHERE doc_key IS NOT NULL").fetchone()[0]
    print(f"rows carrying doc_key: {n} (phase 6 writes none on existing rows)")
con.close()

snap = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
print("summary.testLooks =", snap["summary"]["testLooks"])
print("summary.insights  =", snap["summary"]["insights"], "(495 once phase 4 lands; 500 before)")
assert snap["summary"]["testLooks"] == 4, "this phase must not spend a test-window look"
assert len(snap["insights"]) == 500, "every row still publishes; only the rendering collapses"
print("OK")
PY
```

**Expected:**

```
BEFORE: rows=500 digest=04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed
AFTER : rows=500 digest=04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed
M0131: head 230 is version 2 — chain 227 -> 230
M0024: head 290 is version 2 — chain 289 -> 290
M0127: head 498 is version 2 — chain 493 -> 498
M0179: head 500 is version 3 — chain 320 -> 499 -> 500
summary.testLooks = 4
OK
```

**The two digests being equal is the deliverable of this step.** It is the strongest available
proof that the narrowed `insights_no_update` trigger did its job on real data: five `UPDATE`
statements ran, and not one byte of `kind`, `title`, `body`, `method_id` or `added` moved on any of
the 500 rows. Paste both lines into the phase's report.

**Impact:** none. Pure measurement.

---

### Step 7: Tests, then push

**Code:**

```bash
export WT=/home/miftah/.worktrees/seer/journal-versioning
export PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$WT/engine/src
unset SEER_LAB_DB
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres

cd "$WT" && "$PY" -m pytest engine/tests
```

If Postgres is not up, `docker start seer-pg` (or the `docker run` line in `CLAUDE.md`) first — CI
fails if the DB tests skip.

Then push the branch. **Do not rebase reflexively if the push is rejected** — see §Rollback.

---

## Verification

**Build:** nothing to build — no source file is edited. `engine/.venv/bin/ruff check engine` is a
no-op for this phase and may be skipped; run it only to confirm the tree is clean.

**Tests:**

```bash
export WT=/home/miftah/.worktrees/seer/journal-versioning
export PYTHONPATH=$WT/engine/src
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd "$WT" && /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests
```

The one test that is specifically at stake:

```bash
cd "$WT" && PYTHONPATH=$WT/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest \
  engine/tests/test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database -n0
```

It must be **red between Step 4 and Step 5** and **green after Step 5**. If it is green before
`lab stage`, `PYTHONPATH` was wrong and it tested the main checkout.

**Manual check:**

1. `git -C "$WT" show --stat HEAD` lists `lab/lab.sqlite` and (if Phase 4 landed)
   `web/data/lab.json`, and **nothing else**.
2. `git -C "$WT" status --short` shows no stray modification to any `engine/` or `web/` source file.
3. `git -C /home/miftah/seer status --short` shows `lab/` and `web/data/` untouched — proof the
   main checkout's live database was never written.
4. If Phase 5 has landed, `/sera/journal` renders four cards with a version chip and the "N
   entries in all" line reads **495**. If it has not, that check belongs to Phase 5 and is not this
   phase's exit criterion.

**Exit criteria:**

- `SELECT id, supersedes FROM insights WHERE supersedes IS NOT NULL ORDER BY id` returns exactly
  `[(230, 227), (290, 289), (498, 493), (499, 320), (500, 499)]`.
- Head count is **495 documents from 500 rows** (asserted in SQL, independently of whether Phase 4
  has published the number into `lab.json`).
- M0179's note reads **version 3**; M0131's, M0024's and M0127's read **version 2**.
- The content digest over `(id, kind, title, body, method_id, added)` across all 500 rows is
  **unchanged**: `04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed`.
- `summary.testLooks` still reads **4**.
- `pytest engine/tests` green after `lab stage`.
- One commit, data only, no source file in its diff.

---

## Handoffs

**To Phase 2 (`lab link`), if it is still open:**

- This phase needs nothing but `lab link <successor> --supersedes <predecessor>` and exit code 2 on
  refusal. If phase 2 can cheaply print the resulting chain (`500 supersedes 499 supersedes 320 —
  version 3`) on success, it would make Step 4 self-verifying. Not required.
- `cli.py`'s global `--dry-run` is **not** threaded through `commands/lab.py:run` (it calls
  `store.connect(args.db)` and dispatches directly). Phase 6 works around this with a rehearsal on
  a copy. If phase 2 wants to honour `--dry-run` on `link`, that is phase 2's call and would
  simplify this phase — **but it is not a blocker and this phase must not add it.**

**To Phase 4 (export), satisfying R1 — not R3, so not mine:**

- `store.snapshot` builds each insight explicitly at `store.py:3002-3006` and does **not** publish
  `supersedes`; `summary.insights` at `store.py:2988` is a row count. Until phase 4 changes both,
  this phase's backfill is invisible in `web/data/lab.json`. Phase 4 should re-run `lab stage`
  after landing, which will then produce the real `500 → 495` diff.
- Phase 4's snapshot contract test now has four real chains in the committed database to assert
  against, not just synthetic fixtures — the table in §"What Phase 5 will have to render" is the
  expected output.

**To Phase 5 (reader), satisfying R1/R5 — not mine:**

- The committed journal will contain exactly **four** chains, maximum depth **3**. Phase 5's
  disclosure component never has to render more than two hidden versions. 495 heads, 331
  observations becoming 326 observation documents.
- The 7 rows deliberately left as siblings (`48/54`, `50/52`, `51/53`, `125/126`, `390/391`,
  `466/467/468`) will still render as separate cards with near-identical titles. That is correct
  and is **not** a phase 5 bug: M0260's three are `-M-NATIVE`, `-M-G12` and `-M-G3`, three
  different measurements. If the owner asks why M0260 still shows three cards, that is the answer.

**To Phase 3 (auto-link), satisfying R2 — not mine:**

- `126` supersedes `125` **in prose**, inside the body text ("*This replaces the entry just before
  it, which miscounted the pairs as 20…*"). It is not byte-identical, so this phase leaves it
  alone. Linking it is a judgment call about document identity, which is what `doc_key` exists to
  avoid making by hand. Recorded here so it is not lost; **deliberately not done**.

**Found and deliberately left undone (no phase owns it; raise with the owner, not in this branch):**

- `real_costs.py:226` has `cmp.candidate_id` available and titles on `cmp.method_name` instead,
  which is what generated M0260's three colliding titles in the first place. Phase 3 fixes the
  linking; it does not fix the *titles*, so those three cards will keep reading alike. A one-line
  title change would fix the display — and it would also change what future generated titles look
  like, so it is a separate decision.

---

## Rollback

**This phase alone, before the commit:**

```bash
cd /home/miftah/.worktrees/seer/journal-versioning
git restore --staged --worktree lab/lab.sqlite web/data/lab.json
```

The `supersedes` link is frozen once written (the narrowed trigger refuses value→different-value
and value→NULL), so restoring the file is the **only** way back. There is no `lab unlink` and
Phase 2 is not asked to build one.

**After the commit:**

```bash
git -C /home/miftah/.worktrees/seer/journal-versioning revert --no-edit <sha>
```

`git revert` restores the previous `lab.sqlite` blob wholesale. Because this phase wrote only
`supersedes` on five rows, the revert costs nothing: no content was touched, so no content can be
lost. Then re-run `lab stage` on the reverted database and verify Step 6's digest again.

**If the push is rejected.** Do **not** run `git pull --rebase` reflexively. A rebase replays this
branch's `lab.sqlite` blob on top of whatever the remote now holds, which overwrites rows another
session appended in the meantime. Instead:

1. `git fetch origin` and inspect what moved: `git log --oneline HEAD..origin/feature/journal-versioning`.
2. If the remote's `lab/lab.sqlite` moved, hash both sides and compare row counts and `max(id)`
   with a `mode=ro` connection before deciding anything.
3. If you do rebase, afterwards **re-run `lab stage`**, re-run Step 6's verification in full, and
   confirm `trials.n` is still contiguous
   (`SELECT count(*), max(n) FROM trials` — the two must agree).

**Whole-branch rollback** is governed by the plan index: schema 8 is the one-way door and it is
Phase 1's, not this phase's. Nothing here deepens it.
