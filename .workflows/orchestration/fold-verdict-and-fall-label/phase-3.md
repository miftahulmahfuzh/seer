# Phase 3: The correcting journal entry

**Plan set:** `FOLD_VERDICT_AND_FALL_LABEL_PLAN.md`
**Analysis:** `docs/analyzer/20261013-082101-K09L_code_analyzer.md`
**Satisfies:** R4 — the lab journal narrows its own earlier claim about learning models, in the
owner's plain language, on `seertrade.site/sera`
**Depends on:** Phase 1 (schema v6 → v7, in the source *and* in the committed database)
**Difficulty:** EASY
**Package:** `lab/` (the committed database and its web export)

---

## Goal

The lab journal's entry on the learning model ends with a sentence that claims more than its test
can support: "Learning tools do not fix this lab's real problem, the 2008-sized fall, and here they
did not even pick better stocks." After this phase a newer journal entry stands beside it, narrowing
the first clause to exactly what was tried — one kind of model, one thing to predict, the twenty
most-traded big companies, buying only, after Gotrade's real fees, out of signals the lab already
had — keeping the second clause, which the test does support, and naming what was never tested at
all. Nothing is edited: the journal is append-only and the correction is a newer row.

**This phase writes exactly one `insights` row.** It runs no backtest, spends no test-window look,
adds no method, and changes no source file.

---

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:** one `insights` row — the next free id (**219** as of 2026-10-13, when
`max(id) FROM insights` is 218; do not hardcode it, read it back from the command's own stdout).
Two files move in the commit: `lab/lab.sqlite` and `web/data/lab.json`.
**Signature changes:** none
**Requires (from earlier phases):**
- Phase 1: `store.SCHEMA_VERSION == "7"` in
  `engine/src/seer_engine/lab/store.py`, **and** the committed `lab/lab.sqlite` already migrated to
  `schema_version = '7'` and committed with its `web/data/lab.json`. Both halves, not one.
  See **Step 0** — this is a blocking gate, not a warning.
**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/store.py`, `hardgate.py`, `runner.py`, `commands/lab.py`,
  `engine/tests/*` (Phase 1)
- `engine/src/seer_engine/lab/tree_rank.py` (Phase 2)
- `engine/src/seer_engine/lab/turnover.py`, `docs/backtests/2026-10-13-chart-model-turnover.md`
  (Phase 4)
- `engine/src/seer_engine/lab/methods/*`, `docs/backtests/2026-10-13-learn-the-fall.md` (Phase 5)
- **Insight 217 and every other existing row.** Append-only by trigger. A plan or an implementation
  that proposes an `UPDATE` is wrong and the database will refuse it
  (`insights are append-only: add a newer one instead`).

---

## Files

| File | Action | What changes |
|---|---|---|
| `lab/lab.sqlite` | modify (append) | one new row in `insights`; nothing else |
| `web/data/lab.json` | regenerate | `lab stage` re-exports it: one new entry in `insights[]`, and `asOf` moves to the new row's `added` timestamp (`store.snapshot` takes `asOf` from `max(added) FROM insights` among others, `store.py:2617`) |
| `/tmp/claude-*/scratchpad/insight-correction.md` | create (outside the repo) | the body text handed to `--file`; **never** committed, never written inside the worktree |

No source file is touched. No test is touched. No file under `web/` **source** is touched — only
the generated `web/data/lab.json`, and only through `lab stage`.

---

## Implementation Steps

Throughout, these two shell variables stand for the paths; the implementer should set them once per
shell (the shell does not persist between tool calls, so re-set them):

```bash
WT=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label
PY=/home/miftah/seer/engine/.venv/bin/python
```

`$PY` is the **main checkout's** venv binary; the worktree has no venv of its own. Every invocation
below prefixes `PYTHONPATH=$WT/engine/src` so the worktree's source is imported, not the main
checkout's editable install. Without it this phase would run Phase 1's code from the wrong tree.

---

### Step 0: Verify Phase 1 has landed. If it has not, WAIT.

**File:** none — this is a gate.

`store.connect` migrates `lab.sqlite` on open, **even for a read**, and `store._migrate`
(`engine/src/seer_engine/lab/store.py:734`) refuses a version it does not know:

```
raise LabError(
    f"lab database schema version {found!r} is unknown to this code "
    f"(expects {SCHEMA_VERSION})"
)
```

So there are four states and only one of them is safe to run in.

**Run:**

```bash
WT=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label
grep -n '^SCHEMA_VERSION' $WT/engine/src/seer_engine/lab/store.py
sqlite3 "file:$WT/lab/lab.sqlite?mode=ro" "SELECT value FROM meta WHERE key='schema_version';"
```

**Decision table:**

| source `SCHEMA_VERSION` | committed db `schema_version` | What it means | What to do |
|---|---|---|---|
| `"7"` | `7` | Phase 1 fully landed | **Proceed to Step 1.** |
| `"6"` | `6` | Phase 1 has not landed at all (this is the state at the time of writing, `a737aff`) | **Wait.** Do not run `lab insight`. |
| `"6"` | `7` | Phase 1's database commit landed, its source did not (or was reverted) | **Wait.** `lab insight` would raise `LabError` and exit 2. |
| `"7"` | `6` | Phase 1's source landed, its database commit did not | **Wait.** `lab insight` would silently run Phase 1's v6→v7 migration and fold it into *this* phase's commit, which is Phase 1's work appearing under Phase 3's message. |

**Do not work around any of these.** Do not pass `--db` at a different database, do not stash, do
not check out Phase 1's source yourself, do not migrate the database by hand. The correct action in
three of the four rows is to stop and report "phase 3 blocked: phase 1 not landed (source=X, db=Y)".

**Impact:** nothing is written. This step exists because getting it wrong corrupts another phase's
commit or hard-fails.

---

### Step 1: Capture the baseline, read-only.

**File:** none — reads only.

`lab.sqlite` migrates on connect even for a read, so **every** inspection in this phase goes through
`sqlite3 'file:...?mode=ro'` or `store.connect_readonly`. Never `store.connect`, never a bare
`sqlite3 lab/lab.sqlite`.

**Run:**

```bash
WT=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label
sha256sum $WT/lab/lab.sqlite $WT/web/data/lab.json
python3 - "$WT/lab/lab.sqlite" <<'PY'
import hashlib, sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
q = lambda s: c.execute(s).fetchone()[0]
print("schema_version    ", q("SELECT value FROM meta WHERE key='schema_version'"))
print("insights          ", q("SELECT count(*) FROM insights"))
print("max insight id    ", q("SELECT max(id) FROM insights"))
print("dev_trial_count   ", q("SELECT count(*) FROM trials WHERE window='dev'"))
print("test_looks        ", q("SELECT count(*) FROM trials WHERE window='test'"))
b = q("SELECT body FROM insights WHERE id=217")
t = q("SELECT title FROM insights WHERE id=217")
print("217 body sha256   ", hashlib.sha256(b.encode()).hexdigest(), len(b), "chars")
print("217 title sha256  ", hashlib.sha256(t.encode()).hexdigest())
PY
```

**Expected output** (measured read-only on the worktree database at `a737aff`, 2026-10-13; the trial
counts and the 217 hashes must be *identical* at this step and again at Step 6 — only `insights` and
`max insight id` may move, and only by one):

```
schema_version     7                 <- after phase 1; it is 6 before, which Step 0 already refused
insights           218
max insight id     218
dev_trial_count    394
test_looks         4
217 body sha256    70a438de7392533396297c3cdb1822e7087f30a87189a52a3a41ba4da33ba9e1 731 chars
217 title sha256   3d19cc0c7fb1b80b957a4d479c115fec1934b8df31c50ea88ecfae4d509dc2f2
```

If `insights` is **not** 218, a peer session has appended one since this plan was written. That is
fine and expected — record the number you actually see and carry *your* baseline forward. The
invariant is "exactly one higher at the end", not "219".

If `test_looks` is anything but `4`, **stop**: something has spent a test-window look and that is a
much bigger problem than this phase.

Also check the index is clean of peers before you start writing, because Step 5 commits by index:

```bash
cd $WT && git status --short && git diff --cached --name-only
```

Both should be empty or show only untracked files that are not yours (e.g. another phase's
scratch). If `git diff --cached --name-only` is **non-empty**, a peer has staged work in the shared
index. Do not commit over it: wait for that session, or ask the coordinator. Note the result
either way — Step 5 depends on it.

**Impact:** none. This is the evidence that Step 6 compares against.

---

### Step 2: Write the body file.

**File:** `/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/insight-correction.md` — a
scratchpad path **outside** the repository. The worktree is shared with peer phase sessions and an
untracked `.md` file in it is noise in everyone's `git status`; it is also a file that must never be
committed.

**Change:** write the exact bytes below. `store.add_insight` (`lab/store.py:2295`) calls
`body.strip()`, so a trailing newline is harmless, but nothing else about the text may drift —
this is the deliverable.

**Code** (write with a quoted heredoc so the shell interpolates nothing):

```bash
BODY=/tmp/claude-1000/-home-miftah-seer/$SESSION/scratchpad/insight-correction.md
mkdir -p "$(dirname "$BODY")"
cat > "$BODY" <<'EOF'
An earlier entry here ended by saying that learning tools do not fix this lab's real problem, the 2008-sized fall. That sentence claimed more than the test behind it can carry, and this entry narrows it. The journal only ever adds, so the earlier note stands exactly as it was written and this one says what it should have said.

What we actually tried was one kind of learning model, asked one question: out of the twenty most heavily traded big American companies, which will do best over the next month. It was only ever allowed to buy, never to bet against anything, and it held every name it picked in equal amounts. It paid Gotrade's real fees. And it was built out of the same seven signals this lab already computes, each of which had already failed on its own. A model of that sort can only recombine what it is handed. It cannot invent a signal nobody gave it.

The second half of the old sentence holds, and we are not softening it. On that test the model picked worse than simply holding the twenty most-traded big companies, and the less it trusted its own forecasts the better it did. For this kind of model, on these signals, among big companies, buying only, after our real fees, there is no stock-picking skill to be had. That is a real result.

The leap from there to the fall does not hold. The model was never asked to see a fall coming; it was asked to rank next month's winners. It was never allowed to decide how much of the money should be in the market at all, which is still the job of our one old safety rule, the one that steps aside when the market falls below its 200-day average. And it never saw small companies or the other side of a trade, which is where the published research that suggested this idea finds most of its edge in the first place. None of that was tested here, so none of it was ruled out.

So the honest version of the claim is narrower and duller than the one we wrote. Recombining the signals we already have, among big companies, buying only, after fees, adds nothing to our stock picking. Whether a model pointed at the fall itself, asked how much to hold rather than what to hold, can do better is still an open question, and it is the one worth asking next.
EOF
```

**Why this text, clause by clause** — the implementer must not paraphrase it, but should be able to
check it:

| Requirement from the handover / plan index | Where it lands |
|---|---|
| honest about being a correction, not a new finding | paragraph 1, and "the honest version of the claim is narrower and duller than the one we wrote" |
| append-only, 217 untouched | paragraph 1, "the journal only ever adds, so the earlier note stands exactly as it was written" |
| one model family | "one kind of learning model" |
| one label | "which will do best over the next month" |
| one universe | "the twenty most heavily traded big American companies" |
| long-only | "only ever allowed to buy, never to bet against anything" |
| equal weight | "held every name it picked in equal amounts" |
| after Gotrade fees | "It paid Gotrade's real fees" |
| built from signals the lab already had, each already failed alone | "the same seven signals this lab already computes, each of which had already failed on its own" |
| a tree can only recombine what it is given | "can only recombine what it is handed. It cannot invent a signal nobody gave it" |
| **keeps** the supported second clause | paragraph 3 in full |
| never asked to predict the fall | "never asked to see a fall coming" |
| never allowed to size the book | "never allowed to decide how much of the money should be in the market at all" |
| never given small caps or the short side — where the literature's edge lives | "never saw small companies or the other side of a trade, which is where the published research ... finds most of its edge" |
| the handover's honest sentence | paragraph 5, sentence 2 |
| the open question is the fall-labelled model (phase 5's direction) | paragraph 5, final sentence |

**Banned vocabulary check** — grep the file and expect zero hits:

```bash
grep -nEi 'M0[0-9]{3}|digest|DSR|walk.?forward|gradient|boost|HistGradient|Sharpe|drawdown|long-only|short side|small-cap|cross-section|hyperparameter|out-of-sample|insight 2|tree_rank|allocator|[0-9a-f]{12}' "$BODY"
```

(`drawdown` is banned here on purpose: the owner-facing word in this journal is "fall", which the
text uses. "2008-sized fall" is a quotation of the earlier entry's own phrasing and is correct.)

Also confirm the file is plain ASCII, so nothing depends on the shell's encoding:

```bash
LC_ALL=C grep -n '[^ -~]' "$BODY" || echo "ASCII clean"
```

**Impact:** nothing is written to the lab yet.

---

### Step 3: Append the row.

**File:** `lab/lab.sqlite` — the `insights` table only.
**Change:** one `INSERT`, through the CLI. `_insight` (`engine/src/seer_engine/commands/lab.py:2572`)
reads the file, calls `store.add_insight` inside `with conn:` and prints the new row id.

`--kind` must be one of `store.INSIGHT_KINDS` (`lab/store.py:123`):
`observation`, `hypothesis`, `data-wish`, `feature-wish`, `risk`, `synthesis`. **Use
`observation`** — this is a statement about what the lab measured and what it licenses, like 217
itself. It is not a `hypothesis` (nothing here is proposed for testing), not a `synthesis` (that
kind is reserved for the state of the search after a batch of methods).

`--method M0130` attaches the row to the same method as 216, 217 and 218, so the correction appears
on that method's own `/sera` page beside the claim it narrows. The id lives in the `method_id`
column, never in the owner-facing body. `store.add_insight` validates it against `methods`.

**Code:**

```bash
WT=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label
PY=/home/miftah/seer/engine/.venv/bin/python
BODY=/tmp/claude-1000/-home-miftah-seer/$SESSION/scratchpad/insight-correction.md

cd $WT && PYTHONPATH=$WT/engine/src $PY -m seer_engine lab --db $WT/lab/lab.sqlite \
  insight \
  --kind observation \
  --method M0130 \
  --title "Correcting ourselves: we tested one learning model, not whether learning can help" \
  --file "$BODY"
```

Argument-order notes, from `add_arguments` (`commands/lab.py:160`): `--db` belongs to the **`lab`
parser**, so it goes *before* the `insight` subcommand. `--db` is passed explicitly rather than
relying on `store.DB_PATH`, which resolves `SEER_LAB_DB` or `config.REPO_ROOT / "lab" / "lab.sqlite"`
— that would also be correct here, but peer sessions in this worktree may export `SEER_LAB_DB` and
an explicit path removes the ambiguity.

**Never pass `--dry-run`.** It rolls back all writes; the command would print an id and leave the
database unchanged.

**Expected stdout:** a single integer — the new row's id, `219` if the baseline was 218.
Record it; the rest of the phase refers to it as `<ID>`.

**Exit code:** 0. Exit code 2 means the lab refused the request — read the message:
- `insight kind must be one of (...)` — the `--kind` is not in `INSIGHT_KINDS`.
- `no method M0130` — `--method` named a method the database does not hold. Do not drop `--method`
  to get past it; find out why.
- `lab database schema version '6' is unknown to this code (expects '7')` — Step 0's gate was
  skipped or Phase 1 regressed. Stop.
- `give exactly one of --body or --file` — both or neither were given.

**Impact:** the database is now one row ahead of its committed `web/data/lab.json`. Until Step 4
runs, `test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database`
reads the working-tree database and fails. That is the expected mid-phase state, not a defect.

---

### Step 4: Re-export and stage.

**File:** `web/data/lab.json` (regenerated), then both files staged.
**Change:** `lab stage` (`commands/lab.py:2582`) takes `BEGIN EXCLUSIVE`, writes the snapshot next
to the database's own checkout (`store.snapshot_path` derives `<repo>/web/data/lab.json` from the
database path, so the worktree's own `web/data/lab.json` is the one written), `git add`s both, then
rolls back the lock. It writes nothing to the database.

**Code:**

```bash
cd $WT && PYTHONPATH=$WT/engine/src $PY -m seer_engine lab --db $WT/lab/lab.sqlite stage
```

**Expected stdout:**

```
staged /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/lab/lab.sqlite
staged /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/web/data/lab.json
```

**Impact:** the index now holds a self-consistent pair. Do not run `lab export-json` separately and
do not `git add` either file by hand — `lab stage` exists so that the two can never be staged out of
step.

---

### Step 5: Commit, with no pathspec.

**File:** the git index.
**Change:** one commit carrying exactly `lab/lab.sqlite` and `web/data/lab.json`.

The lab database is committed **by index, never by pathspec**: `git commit -- <paths>` re-reads the
working tree for those paths and can pair a newer `lab.sqlite` with an older `lab.json`, which CI's
row-for-row check then fails. `lab stage` already made the index self-consistent; a bare commit
publishes exactly that.

Because the index is bare-committed, first prove it holds nothing else:

```bash
cd $WT && git diff --cached --name-only
```

**Expected — exactly these two lines and nothing more:**

```
lab/lab.sqlite
web/data/lab.json
```

If a third path appears, a peer session staged something between Step 1 and here. **Do not commit.**
Do not unstage their work. Stop, report, and coordinate — their file and yours would land under your
message otherwise.

Then:

```bash
cd $WT && git commit -F - <<'EOF'
lab: narrow the learning-model claim to what it actually tested

An earlier journal entry ended "Learning tools do not fix this lab's real
problem, the 2008-sized fall, and here they did not even pick better stocks."
The second clause is supported by the run behind it. The first is an overreach
from one configuration: one model family, one label, the top twenty of a
large-cap screen, long-only, equal weight, after Gotrade's real fees, on
signals the lab already computed and that had each already failed alone. The
model was never asked to forecast the fall, never allowed to size the book, and
never shown small caps or the short side -- the regime the source literature's
edge actually lives in.

Insights are append-only, so this is a newer entry, not an edit. Insight 217 is
byte-identical: body sha256 70a438de7392533396297c3cdb1822e7087f30a87189a52a3a41ba4da33ba9e1.

No run, no method, no test-window look. store.test_looks(conn) = 4, unchanged.
store.dev_trial_count(conn) = 394, unchanged. insights <baseline> -> <baseline + 1>.

Staged with `lab stage`, so web/data/lab.json is the export of lab/lab.sqlite.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

The implementer must **substitute the numbers actually measured in Steps 1 and 6** into that message
before committing — the `394`, the `4`, the `218 -> 219` and the sha256 are the values measured on
the worktree at `a737aff` and are the message's evidence, not decoration. If a peer appended an
insight first, the counts differ and the message must say what was seen.

If `pusher` is dispatched for this commit, write the `Co-Authored-By` trailer out verbatim in its
prompt and tell it not to substitute its own model name, and say verbatim in that prompt:

> `git reset --hard`, `git clean`, `git checkout .` and every bare-path form are banned in this
> worktree. Stage nothing yourself; the index is already correct. Commit it with no pathspec.

**Impact:** `lab/lab.sqlite` and `web/data/lab.json` are published together. The commit is revertible
on its own (see **Rollback**).

---

## Verification

**Build:** nothing is compiled; no source file changed. For completeness:

```bash
/home/miftah/seer/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine
```

Expect `All checks passed!` — and expect it to be **unchanged from before this phase**, since no
`.py` file moved.

**Tests:**

```bash
docker start seer-pg 2>/dev/null
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
  PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

Quote the **skip count beside the pass count** (plan-set invariant 1). Without `PG_TEST_URL` ~385
tests skip silently and CI fails the run; without `PYTHONPATH` pytest imports the main checkout and
tests the wrong tree.

### Reading `test_lab_snapshot.py` honestly

`test_the_committed_snapshot_is_the_export_of_the_committed_database`
(`engine/tests/test_lab_snapshot.py:925`) reads **`store.COMMITTED_DB` in the working tree**, not the
committed blob. It goes red whenever *any* session in this shared worktree is mid-write — including
a peer phase running `lab run`. **A red there is not evidence that this phase's commit is bad.**

The real check compares the git blobs. Run it after Step 5:

```bash
WT=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label
TMP=$(mktemp -d)
cd $WT
git show HEAD:lab/lab.sqlite    > $TMP/lab.sqlite
git show HEAD:web/data/lab.json > $TMP/lab.json
PYTHONPATH=$WT/engine/src /home/miftah/seer/engine/.venv/bin/python - "$TMP/lab.sqlite" "$TMP/lab.json" <<'PY'
import sys
from pathlib import Path
from seer_engine.lab import store
db, js = Path(sys.argv[1]), Path(sys.argv[2])
ro = store.connect_readonly(db)
try:
    expected = store.snapshot_json(ro)
finally:
    ro.close()
committed = js.read_text(encoding="utf-8")
print("committed blobs agree row for row:", committed == expected)
PY
rm -rf $TMP
```

**Expected:** `committed blobs agree row for row: True`. That is what CI checks and it is
independent of whatever any peer session is doing to the working tree right now.

### The things that must not have moved

Run the Step 1 script again against the working-tree database, read-only:

```bash
WT=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label
python3 - "$WT/lab/lab.sqlite" <<'PY'
import hashlib, sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
q = lambda s: c.execute(s).fetchone()[0]
print("schema_version    ", q("SELECT value FROM meta WHERE key='schema_version'"))
print("insights          ", q("SELECT count(*) FROM insights"))
print("max insight id    ", q("SELECT max(id) FROM insights"))
print("dev_trial_count   ", q("SELECT count(*) FROM trials WHERE window='dev'"))
print("test_looks        ", q("SELECT count(*) FROM trials WHERE window='test'"))
b = q("SELECT body FROM insights WHERE id=217")
print("217 body sha256   ", hashlib.sha256(b.encode()).hexdigest(), len(b), "chars")
print("217 title sha256  ",
      hashlib.sha256(q("SELECT title FROM insights WHERE id=217").encode()).hexdigest())
PY
```

| Reading | Before | After | Rule |
|---|---|---|---|
| `schema_version` | `7` | `7` | unchanged — this phase does not migrate |
| `insights` | the Step 1 baseline (218 on 2026-10-13) | baseline + 1 | **exactly one higher** — never an absolute |
| `max insight id` | the Step 1 baseline (218 on 2026-10-13) | baseline + 1 | one higher, and equal to `<ID>`, what Step 3 printed |
| `dev_trial_count` | 394 | 394 | unchanged — no run happened |
| `test_looks` | 4 | **4** | unchanged — the test window was never read |
| 217 body sha256 | `70a438de…a9e1` | identical | 217 is frozen |
| 217 title sha256 | `3d19cc0c…c2f2` | identical | 217 is frozen |

Then prove the row is the one intended, and that it carries no forbidden vocabulary **as stored**
(not just as drafted):

```bash
WT=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label
sqlite3 -separator '|' "file:$WT/lab/lab.sqlite?mode=ro" \
  "SELECT id, kind, method_id, added, title FROM insights ORDER BY id DESC LIMIT 1;"
sqlite3 "file:$WT/lab/lab.sqlite?mode=ro" "SELECT body FROM insights ORDER BY id DESC LIMIT 1;" \
  | grep -nEi 'M0[0-9]{3}|digest|DSR|walk.?forward|gradient|boost|Sharpe|drawdown|hyperparameter|[0-9a-f]{12}' \
  || echo "plain-language check: clean"
```

**Expected:** `<ID>|observation|M0130|<today's UTC timestamp>|Correcting ourselves: we tested one
learning model, not whether learning can help`, then `plain-language check: clean`.

And confirm it reaches the site's data:

```bash
cd $WT && python3 -c "
import json
d = json.load(open('web/data/lab.json'))
i = d['insights'][-1]
print(d['version'], len(d['insights']), i['id'], i['kind'], i['methodId'])
print(i['title'])
print(d['asOf'], '==', i['added'])
"
```

**Expected:** `5 <ID> <ID> observation M0130`, the title, and `asOf` equal to the new row's `added`
(`store.snapshot` takes `asOf` from the newest of `methods.updated`, `trials.run_at`,
`insights.added`, `ideas_seen.added`). `version` stays `5` — `SNAPSHOT_VERSION` does not move in
this plan set (Decision D3).

**Manual check:** read the stored body back out and read it as the owner would — no ids, no code,
no statistics, and a reader who has just read the earlier entry understands that this one narrows
it rather than contradicting it.

```bash
sqlite3 "file:$WT/lab/lab.sqlite?mode=ro" "SELECT body FROM insights ORDER BY id DESC LIMIT 1;"
```

**Exit criteria:**
1. `SELECT count(*) FROM insights` is **exactly one** higher than the Step 1 baseline.
2. Insight 217's `body` and `title` hash to the Step 1 values, byte for byte.
3. `test_looks` is 4 and `dev_trial_count` is unchanged, both quoted in the commit body.
4. The stored body contains no method id, no digest, no code identifier, no "DSR", no
   "walk-forward", no "gradient-boosted" and no statistics jargon.
5. The committed `lab/lab.sqlite` and `web/data/lab.json` blobs agree row for row (the git-blob
   recipe above prints `True`).
6. `git show --stat HEAD` lists exactly `lab/lab.sqlite` and `web/data/lab.json`, and `git log -1`
   carries this phase's message.
7. `git status --short` shows no stray file this phase created inside the worktree (the body file
   lives in the scratchpad).
8. `ruff` and the suite are as green as they were before the phase, with the skip count quoted.

---

## Handoffs

- **Phase 1 owns the schema move.** This phase only consumes v7. If Step 0 finds the ladder
  half-landed, that is Phase 1's work to finish, not this phase's to patch.
- **Phase 5 writes its own journal entry** for the fall-labelled method's result (R2), plus
  `docs/backtests/2026-10-13-learn-the-fall.md`. This phase deliberately does **not** pre-announce
  that result: its last sentence poses the open question and stops. If Phase 5 lands first, nothing
  here changes — the journal is a timeline and both entries stand.
- **Phase 4's turnover write-up** (R3) may deserve a journal entry of its own about what the fee
  schedule costs a fast model. That is Phase 4's call and Phase 4's row, not this one's. This phase
  must not append it.
- **Insight 211's synthesis** ("the lab has been losing a race it never knew it had entered") and
  insight 207's hypothesis about reshuffling are both older claims that a future reader may want
  narrowed in the same way. Noticed, deliberately not done here: this phase's `satisfies` is R4,
  which is scoped to 217's first clause alone.
- **`web/` rendering is not touched.** If `/sera` renders a five-paragraph insight body badly, that
  is a web change nobody in this plan set owns (Scope: "`web/` is not touched"). Report it; do not
  fix it from here.

---

## Rollback

This phase is one commit touching two files, so:

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
git log --oneline -3                       # find this phase's sha
git revert --no-edit <sha>
```

A revert restores both files together, which keeps the row-for-row check true. It is safe **only
while Phase 1's database commit is still in place and no later lab commit has landed on top** — a
revert of an older database blob would discard whatever a peer appended after it. If any lab commit
sits above this one, do not revert: append a superseding insight instead, which is what the journal
is designed for.

`git reset --hard`, `git clean`, `git checkout .` and every bare-path form are **banned** in this
worktree — peer phase sessions have work in progress in the same tree and the same index. Say that
verbatim in any subagent prompt.

**What cannot be rolled back:** the `insights` row itself. The table refuses `DELETE`
(`insights are append-only`) and refuses `UPDATE`
(`insights are append-only: add a newer one instead`). Reverting the commit rewinds the committed
*file*, but if the row has already been pushed and another session has pulled and appended on top of
it, the row is permanent. That is the journal's design: the correction for a bad correction is a
third entry, in plain language, saying so.
