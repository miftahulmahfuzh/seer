> Adopted from `docs/plans/FOLD_VERDICT_AND_FALL_LABEL_PLAN.md` phase 1. Source: `.workflows/plan/fold-verdict-and-fall-label/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: The fold verdict on every `lab run`

**Plan set:** `FOLD_VERDICT_AND_FALL_LABEL_PLAN.md`
**Analysis:** `docs/analyzer/20261013-082101-K09L_code_analyzer.md`
**Satisfies:** R1 — *make walk-forward part of every `lab run` verdict; a new recorded column plus a report path, never an edit of recorded rows; decide explicitly whether a lost fold majority gates or annotates*
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` (with `engine/src/seer_engine/commands`)

---

## Goal

After this phase, every `lab run` — the ordinary path and the `--amend` path — ends by scoring the
method's whole walk-forward record against the lab's shared geometry, **inside the same
transaction that recorded the trials**, writing one row into a new append-only `method_folds`
side table and printing it in the run's verdict. A researcher learns at run time what previously
only surfaced at `lab promote`, and the record is kept rather than recomputed. Nothing is refused
that was not refused before: the fold majority is still a gate only at `lab promote`.

---

## The decisions this phase is built on

These are binding. They are repeated here because the module docstrings this phase writes must
argue them, and the next researcher reads the code, not the plan.

### D1 — A lost fold majority **annotates**; it does not gate

A method that loses a majority of its walk-forward folds at `lab run` still records its trials,
still keeps `TrialRow.eligible` exactly as `trial_rows` computed it, and still moves its status by
the existing rule. The run is not refused. Three reasons, each checkable:

1. **The handover says so.** Section 2 item 1: *"closed trial rows are frozen, so this is a new
   column/report path, never an edit of recorded rows."* A per-trial `eligible` that folded in the
   fold record would be an edit of the recorded row's meaning.
2. **The test window is already protected.** `hardgate.check` (`hardgate.py:1216`) already refuses
   a lost fold majority at `lab promote`, `store.TRANSITIONS` admits exactly one edge into
   `promoted` (`dev-eligible -> promoted`), and `runner.preflight_test` refuses any method that is
   not `promoted`. A second gate at `lab run` adds no protection — it only costs method ids.
3. **The fold record is a method-level, time-varying property.** It is computed from *every*
   recorded dev curve of the method plus the benchmark, so an amendment recorded tomorrow changes
   it. `store.verdict`'s stated promise is that *"a verdict is comparable across time"*; a per-trial
   `eligible` column that depended on a quantity which moves when a sibling trial is appended would
   break exactly that.

The printed output must say this in plain words, so the reader is not left guessing whether the
run was secretly weakened. The sentence lives in one place — `hardgate.FoldVerdict.note()` — and
both `lab run` and `lab show` print it from there.

### D2 — The verdict is **recorded**, not merely printed

The handover asked for a new column. `method_folds` is that column, shaped as a side table for
exactly the reason `trial_funding`, `trial_provenance` and `method_amendments` are: `ALTER TABLE`
on a closed table would move every recorded row's bytes, and one column could not hold a per-fold
list.

### D3 — The verdict does **not** reach `web/data/lab.json`, and `SNAPSHOT_VERSION` stays at 5

`store.snapshot` reads `methods`, `trials`, `insights` and `ideas_seen` only. A new side table
changes none of its bytes. This is **proved, not asserted** — see *Verification, step V5* — and the
proof goes in the commit body of the database commit.

### D6 — The run keeps running when the verdict cannot be computed

`lab run` completes and records the **reason** when any of these holds: there is no `REF-SPY-HOLD`
dev trial carrying a curve; the benchmark curve yields fewer than `hardgate.MIN_FOLDS` (4) folds;
the method has no dev trial carrying a curve; a curve's price fingerprint is not the benchmark's
(D10). `hardgate.pin_dev_store`'s own docstring is explicit that *"a fresh lab has to be able to
run before it has a benchmark"*, and `hardgate.summary` (`:1180`) is the standing precedent for a
lenient sibling of a strict rule. There is a test for the no-benchmark case.

### D15 (new, to be written into `hardgate.py`'s module docstring)

The new lenient sibling and its place beside (F). Full text in Step 4.

---

## CRITICAL HAZARD: the schema bump is a one-way door

`store._migrate` refuses a version it does not know (`store.py:770`). Once the committed
`lab/lab.sqlite` reads `schema_version = '7'`, **every lab command running pre-phase-1 code raises
`LabError` on connect** — including `lab stage`, `lab show`, `lab insight` and `lab run`. The
migration is forward-only and automatic, so:

- **Safe:** new code opening the old (v6) database — it migrates it in place.
- **Fatal:** the migrated (v7) database reaching a checkout whose code is still at v6.

Therefore:

- The source commit lands **first**, the database commit **second**, and the two are pushed in the
  same push. Never push the database commit with the source commit still local.
- **Peer phases 3, 4 and 5 all declare `Depends on: 1` for exactly this reason.** Phase 3 appends
  an insight, phase 4 reads the lab, phase 5 runs a method — every one of them opens
  `lab/lab.sqlite`, and every one of them must be running this phase's code when it does.
- Rollback backs out **both commits together, newest first** (see *Rollback*).

---

## Interface Contract

**Creates (`store.py`):**

- `store.SCHEMA_VERSION` moves `"6"` -> `"7"` (`store.py:86`) — *a value change other phases
  observe, not a new symbol*
- `store._FOLDS_TABLE` (`store.py`, new, beside `_AMENDMENTS_TABLE` at `:359`)
- `store._FOLDS_TRIGGERS: tuple[str, ...]` (new, beside `_AMENDMENTS_TRIGGERS` at `:371`)
- `store.FoldRow` — frozen dataclass, 14 fields (new, in a `method folds` section after the
  `method amendments` section at `:2140`)
- `store.FOLD_COLUMNS: tuple[str, ...]` = `tuple(f.name for f in fields(FoldRow))`
- `store.folds_of(conn, method_id) -> list[sqlite3.Row]`
- `store.latest_folds(conn, method_id) -> sqlite3.Row | None`
- `store.insert_folds(conn, row: FoldRow) -> None`
- `store._v6_to_v7(conn) -> None` (new, after `_v5_to_v6` at `:713`)

**Creates (`hardgate.py`):**

- `hardgate.FoldVerdict` — frozen, slotted dataclass with fields
  `method, bench_n, total, scored, won, majority, stable, picks_json, summary, reason`;
  property `scoreable`; methods `line()`, `note()`; classmethod `from_row(row)`
- `hardgate.fold_verdict(conn, method_id, geo=None) -> FoldVerdict` — **lenient**: never raises
  `store.LabError`
- `hardgate._picks_json(picks) -> str` and `hardgate._finite(x) -> float | None` (private helpers)

**Creates (`runner.py`):**

- `runner.Run` — frozen dataclass `(ran: tuple[Ran, ...], folds: store.FoldRow,
  verdict: hardgate.FoldVerdict)`

**Signature changes:**

- `runner.run_method(...) -> list[Ran]` becomes `runner.run_method(...) -> Run`.
  Four call sites use the return value and are all updated by this phase:
  `commands/lab.py:1489`, `tests/test_lab_runner.py:73`, `:283`, `:297`.
  Every other call site discards it and is untouched.

**Modifies (behaviour only, no signature):**

- `commands/lab.py:_show` (`:1399`) — one extra line when the method has a recorded verdict
- `commands/lab.py:_run` (`:1440`) — a fold block after `_show`
- `store.py`'s module docstring and `_SCHEMA` (the new table/triggers appended at `store.py:524`)
- `hardgate.py`'s module docstring (a `(D15)` paragraph before the closing `"""` at `:452`)

**Requires (from earlier phases):** none — this phase is a root of the dependency graph.

**Leaves alone (owned by others, or deliberately frozen):**

- `hardgate.check` (`:1216`), `hardgate.geometry` (`:595`), `hardgate.fold_record` (`:792`),
  `hardgate.variant_record` (`:840`), `hardgate.fold_summary`, `hardgate.summary` (`:1180`) —
  **not one byte**
- `runner.trial_rows` (`:451`), `store.TrialRow`, `TrialRow.eligible`, `TrialRow.failed`,
  `store.verdict`, `store.published_verdict`
- `store.snapshot`, `store.snapshot_json`, `store.SNAPSHOT_VERSION` (stays 5), everything under
  `web/`
- `lab/tree_rank.py` (Phase 2), `lab/turnover.py` + the `turnover` subparser (Phase 4),
  `lab/methods/*` (Phase 5), `sim/`, `docs/backtests/`
- `engine/tests/test_tree_rank.py` (Phase 2), `engine/tests/test_lab_turnover.py` (Phase 4)

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | module docstring (`:33`, `:70`); `SCHEMA_VERSION` `:86`; `_FOLDS_TABLE`/`_FOLDS_TRIGGERS` after `:382`; `_SCHEMA` after `:524`; `_v6_to_v7` after `:731`; `_migrate` ladder `:733-781`; `FoldRow` + readers + `insert_folds` after `:2267` |
| `engine/src/seer_engine/lab/hardgate.py` | modify | `import math` in the import block (`:456`); a `(D15)` paragraph before the docstring's closing `"""` (`:452`); `FoldVerdict`, `_finite`, `_picks_json`, `fold_verdict` inserted between `:1200` and `:1202` |
| `engine/src/seer_engine/lab/runner.py` | modify | module docstring step 4 (`:19-23`); `Run` dataclass after `Ran` (`:110`); `run_method` docstring and body (`:586-740`); return type |
| `engine/src/seer_engine/commands/lab.py` | modify | `_show` (`:1399`, one block before the `verdict`/`analysis` prints); `_run` (`:1489-1493`, the `run_method` call and a fold block) |
| `engine/tests/test_lab_fold_verdict.py` | create | 13 new tests — the whole of R1's behaviour |
| `engine/tests/test_lab_snapshot.py` | modify | `_without_folds` + `V6_SCHEMA` (`:28-39`); three `== "6"` assertions (`:133`, `:377`, `:454`); the new v6->v7 migration test and the snapshot-identity test appended after `:487` |
| `engine/tests/test_lab_runner.py` | modify | three call sites take `.ran` (`:73`, `:283`, `:297`) |
| `lab/lab.sqlite` | modify | migrated v6 -> v7 on connect, then `lab stage` |
| `web/data/lab.json` | modify | re-staged by `lab stage` (expected to be **byte-identical**) |

---

## Implementation Steps

### Step 1: the `method_folds` table, its triggers and the schema version

**File:** `engine/src/seer_engine/lab/store.py:86` and `:383` (immediately after
`_AMENDMENTS_TRIGGERS` ends and before the `BACKFILL_LUMP_SUM_IDR` comment block at `:375`).

**Change:** bump `SCHEMA_VERSION`, and add the new table and triggers copying the
`_AMENDMENTS_TABLE` / `_AMENDMENTS_TRIGGERS` shape exactly.

**Code — replace line 86:**

```python
SCHEMA_VERSION = "7"  # 2: synthesis kind; 3: trial_moments; 4: trial_funding; 5: trial_provenance; 6: method_amendments; 7: method_folds (see _migrate)
```

**Code — insert after line 382 (the closing `)` of `_AMENDMENTS_TRIGGERS`), before the
`#: The backfill's capital rule` comment:**

```python
# The walk-forward record of one batch of trials, as it read the moment that batch was recorded
# (schema v7). Written by ``runner.run_method`` inside the very transaction that inserts the
# trials, so the curves the run just produced are in the record it keeps.
#
# **It annotates; it does not gate.** A method that loses a majority of its folds here still
# records its trials, still keeps whatever ``trials.eligible`` ``runner.trial_rows`` computed, and
# still moves its status by the existing rule. The fold majority remains a refusal at
# ``lab promote`` only (``hardgate.check``), and ``runner.preflight_test`` refuses any method that
# is not ``promoted``, so the one counted look is already behind that gate. Three reasons this is
# the right side of the line, all checkable:
#
# - the handover (HANDOVER_20261013-measure-the-constraint.md §2.1) asked for "a new column/report
#   path, never an edit of recorded rows";
# - a second gate at run time protects nothing the promote gate does not already protect, and
#   would spend method ids to say so;
# - the record is a **method-level, time-varying** property -- it is scored over *every* recorded
#   dev curve of the method against the benchmark, so an amendment recorded tomorrow changes it.
#   ``store.verdict`` promises that a verdict is "comparable across time"; a per-trial column that
#   moved when a sibling row was appended would break exactly that promise.
#
# A side table, not a column on ``methods`` or ``trials``, for the reason ``trial_funding``,
# ``trial_provenance`` and ``method_amendments`` are: ``ALTER TABLE ... ADD COLUMN`` would move
# every recorded row's bytes, and one column could not hold a list of folds.
#
# ``seq`` starts at 1 and is contiguous per method, exactly as ``method_amendments.seq`` is, so
# the recorded verdicts are a prefix of the method's run history and ``latest_folds`` has a
# definite answer. ``run_at`` is the run's, not the moment of the computation: it is the same
# ``run_at`` every trial of that batch carries, which is what joins this row to them.
#
# Either the numbers or the reason, never both and never neither -- the final CHECK. A lab with no
# ``REF-SPY-HOLD`` benchmark, a geometry too thin for ``hardgate.MIN_FOLDS``, a method with no
# curve, or a price fingerprint that is not the benchmark's (D10) all land in the second case, and
# the run completes anyway: a fresh lab has to be able to run before it has a benchmark
# (``hardgate.pin_dev_store``).
_FOLDS_TABLE = """CREATE TABLE IF NOT EXISTS method_folds (
    method_id    TEXT NOT NULL REFERENCES methods(id),
    seq          INTEGER NOT NULL CHECK (seq >= 1),
    run_at       TEXT NOT NULL CHECK (length(trim(run_at)) > 0),
    git_sha      TEXT NOT NULL CHECK (length(trim(git_sha)) > 0),
    bench_n      INTEGER REFERENCES trials(n),
    folds_total  INTEGER CHECK (folds_total IS NULL OR folds_total >= 0),
    folds_scored INTEGER CHECK (folds_scored IS NULL OR folds_scored >= 0),
    folds_won    INTEGER CHECK (folds_won IS NULL OR folds_won >= 0),
    majority     INTEGER CHECK (majority IS NULL OR majority IN (0, 1)),
    stable       INTEGER CHECK (stable IS NULL OR stable IN (0, 1)),
    picks_json   TEXT NOT NULL,
    summary      TEXT NOT NULL CHECK (length(trim(summary)) > 0),
    reason       TEXT,
    recorded     TEXT NOT NULL CHECK (length(trim(recorded)) > 0),
    PRIMARY KEY (method_id, seq),
    CHECK ((reason IS NULL) <> (folds_scored IS NULL))
)"""
_FOLDS_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS method_folds_no_update BEFORE UPDATE ON method_folds
BEGIN SELECT RAISE(ABORT, 'method_folds are append-only: a recorded fold verdict is never updated'); END""",
    """CREATE TRIGGER IF NOT EXISTS method_folds_no_delete BEFORE DELETE ON method_folds
BEGIN SELECT RAISE(ABORT, 'method_folds are append-only: a recorded fold verdict is never deleted'); END""",
)
```

**Impact:** `SCHEMA_VERSION` moving is the one-way door. Nothing else in this step is observable
until Step 2 wires the DDL into `_SCHEMA`.

---

### Step 2: the schema script and the module docstring

**File:** `engine/src/seer_engine/lab/store.py:524` (just after `{_AMENDMENTS_TRIGGERS[1]};` and
its blank line, before the `trials_no_update` trigger).

**Change:** add the three statements to `_SCHEMA`, in the same one-per-paragraph layout the test
fixtures' `_without_*` strippers rely on.

**Code — insert after line 525 (the blank line following `{_AMENDMENTS_TRIGGERS[1]};`):**

```
{_FOLDS_TABLE};

{_FOLDS_TRIGGERS[0]};

{_FOLDS_TRIGGERS[1]};

```

so the region reads:

```
{_AMENDMENTS_TABLE};

{_AMENDMENTS_TRIGGERS[0]};

{_AMENDMENTS_TRIGGERS[1]};

{_FOLDS_TABLE};

{_FOLDS_TRIGGERS[0]};

{_FOLDS_TRIGGERS[1]};

CREATE TRIGGER IF NOT EXISTS trials_no_update BEFORE UPDATE ON trials
```

> **The blank line between each statement is load-bearing.** `test_lab_snapshot.py`'s
> `_without_moments` / `_without_provenance` / `_without_amendments` (and the `_without_folds`
> Step 9 adds) strip `f"{ddl};\n\n"` and assert that exact string is present. A statement laid out
> any other way makes those fixtures fail loudly, which is the intent.

**Change:** the module docstring. Add the table to the table list and to the schema-version
sentence.

**Code — insert after the `method_amendments` bullet (`store.py:33-39`), before the
`Schema versions` paragraph:**

```
- ``method_folds``: one row per *batch* of trials -- one per ``lab run``, one per ``--amend`` run
  -- carrying that method's whole walk-forward record as it read the moment the batch was
  recorded: how many folds the lab's geometry yields, how many could be scored, how many the
  method won, whether the training slices kept choosing the same variant, and the per-fold detail
  as JSON. When the record could not be computed at all -- no ``REF-SPY-HOLD`` benchmark, a
  geometry thinner than ``hardgate.MIN_FOLDS``, no curve, or prices that are not the benchmark's
  (hardgate D10) -- the row carries the **reason** instead and the run still completes. **It
  annotates; it does not gate**: the fold majority is a refusal at ``lab promote``
  (``hardgate.check``) and nowhere else, and no ``trials`` column changed meaning when this table
  arrived. Triggers refuse every UPDATE and DELETE.
```

**Code — replace the `Schema versions` sentence's tail (`store.py:46-47`):**

```
``method_amendments`` side table (empty: nothing is backfilled, because no amendment predates it);
7 adds the ``method_folds`` side table (empty for the same reason: the verdict of a run that has
already happened cannot be recomputed as it was, because the lab has recorded curves since).
``connect`` migrates an older database in place; ``connect_readonly`` never does.
```

**Impact:** a fresh database now creates `method_folds`. `_SCHEMA` is also re-run by `connect` on
every open, so an already-migrated database is a no-op.

---

### Step 3: the `_v6_to_v7` ladder step

**File:** `engine/src/seer_engine/lab/store.py:731` (after `_v5_to_v6` ends, before `def _migrate`)
and `:733-781` (`_migrate` itself).

**Code — insert after `_v5_to_v6` (line 731), before `def _migrate`:**

```python
def _v6_to_v7(conn: sqlite3.Connection) -> None:
    """Add the ``method_folds`` side table and its two append-only triggers.

    Purely additive, exactly as ``_v2_to_v3``, ``_v3_to_v4`` and ``_v5_to_v6`` were and for the
    same reason: no ``methods``, ``trials``, ``trial_moments``, ``trial_funding``,
    ``trial_provenance`` or ``method_amendments`` row is read, written, rebuilt or re-keyed, no
    column is altered, no verdict moves. A v6 database that migrates and is then never written
    again differs from its v6 self only by an empty table, two triggers and the
    ``schema_version`` string, which
    ``test_connect_migrates_a_v6_database_adding_method_folds_and_touching_no_row`` pins.

    **Nothing is backfilled, and nothing can be.** A fold record is scored over every dev curve
    the method has *today*; re-scoring a run that happened in 2026-10 would give the record the
    lab would compute now, not the one that run would have recorded, and writing that into a row
    stamped with that run's ``run_at`` would be a fabricated measurement. The table therefore
    starts empty and fills from the next ``lab run`` onwards, and ``latest_folds`` answering None
    is the honest "this method ran before the lab kept this" -- the same shape ``funding_of``
    answers for the 128 trials that predate ``trial_funding``.

    In particular ``trials.eligible`` is not read and not written here. The fold record annotates;
    it has never decided a trial's eligibility and this migration does not make it start.
    """
    conn.execute(_FOLDS_TABLE)
    for trigger in _FOLDS_TRIGGERS:
        conn.execute(trigger)
```

**Code — replace `_migrate`'s docstring paragraph and ladder (`store.py:734-746` and `:762-769`):**

The docstring's second paragraph becomes:

```
    A ladder: each step moves the database up exactly one version, so a v1 database reaches v7 in
    one open by running all six steps in order. v1 -> v2 adds the ``synthesis`` insight kind
    (``_v1_to_v2``); v2 -> v3 adds the ``trial_moments`` side table (``_v2_to_v3``); v3 -> v4 adds
    the ``trial_funding`` side table (``_v3_to_v4``); v4 -> v5 adds the ``trial_provenance`` side
    table and backfills it (``_v4_to_v5``) -- after v3 -> v4, because the backfill reads
    ``trial_funding``; v5 -> v6 adds the ``method_amendments`` side table (``_v5_to_v6``); v6 -> v7
    adds the ``method_folds`` side table (``_v6_to_v7``), empty, because a past run's fold record
    cannot be recomputed as it read. A version this code does not know is refused rather than
    guessed at -- **which makes this a one-way door for every other checkout**: a v7 database
    opened by v6 code raises ``LabError`` on connect, so the code and the migrated committed
    database must land together.
```

and the ladder gains one rung, so the block reads:

```python
        if version == "5":
            _v5_to_v6(conn)
            version = "6"
        if version == "6":
            _v6_to_v7(conn)
            version = "7"
        if version != SCHEMA_VERSION:
```

**Impact:** opening the committed v6 `lab/lab.sqlite` with this code migrates it in place. That is
the moment the one-way door closes — see *Order of operations*.

---

### Step 4: `FoldRow`, `FOLD_COLUMNS`, `folds_of`, `latest_folds`, `insert_folds`

**File:** `engine/src/seer_engine/lab/store.py:2268` — a new section between the end of
`insert_amendment` (line 2267) and the `ideas_seen` section header (line 2269).

**Code — insert at line 2268:**

```python

# --------------------------------------------------------------------------- method folds


@dataclass(frozen=True)
class FoldRow:
    """One batch's walk-forward record, as it read when that batch was recorded (schema v7).

    The database half of ``hardgate.FoldVerdict``. One row per ``lab run`` -- the ordinary path
    and the ``--amend`` path alike -- written by ``runner.run_method`` in the very transaction
    that inserts the trials, so the curves that run produced are inside the record it keeps. A
    rolled-back run leaves neither the trials nor this row.

    **It annotates; it does not gate.** Nothing in this row feeds ``trials.eligible``,
    ``store.verdict`` or ``methods.status``. The fold majority is a refusal at ``lab promote``
    (``hardgate.check``) and nowhere else; ``runner.preflight_test`` refuses any method that is not
    ``promoted``, so the one counted look is already behind that gate. See ``_FOLDS_TABLE`` above
    for the three reasons the line is drawn here.

    - ``method_id``    the method this batch belongs to. It exists by the time the row is written:
                       ``run_method`` adds the method before it inserts the trials.
    - ``seq``          1 for the first recorded run, 2 for the first amendment, contiguous --
                       exactly ``method_amendments.seq``'s shape, so ``latest_folds`` is the
                       highest ``seq`` and the history has no holes.
    - ``run_at``       the run's timestamp: the same ``run_at`` every trial of this batch carries,
                       which is what joins this row to them. Not the moment of the computation --
                       that is ``recorded``.
    - ``git_sha``      the repository HEAD the run was made at.
    - ``bench_n``      the ``trials.n`` of the ``REF-SPY-HOLD`` row the folds were cut from
                       (``hardgate.Geometry.bench_n``), so a reader can find the yardstick rather
                       than look it up again and risk naming a different one. None when the lab had
                       no benchmark.
    - ``folds_total``  how many folds the lab's shared geometry yields. None when there was no
                       geometry at all.
    - ``folds_scored`` how many of them could be scored for this method; ``folds_won`` how many it
                       beat the de-funded benchmark on. **None exactly when ``reason`` is set** --
                       the table's last CHECK.
    - ``majority``     ``walkforward.Record.majority``: did it win a strict majority of the folds
                       it was scoreable on. ``stable``: did the training slices keep choosing the
                       same variant.
    - ``picks_json``   the per-fold detail as compact JSON -- one object per fold with the fold's
                       dates, the variant the training slice picked, its training MAR, the pick's
                       and the benchmark's evaluation-slice total returns, and whether it beat.
                       ``"[]"`` when nothing could be scored. Kept rather than recomputed because
                       the record is **time-varying**: it is scored over every dev curve the method
                       has, so the same question asked after the next amendment gives a different
                       answer, and this row is the answer *that run* got.
    - ``summary``      the one display line (``walkforward.Record.summary()``: ``"3 of 4 folds"``,
                       or ``"3 of 4 folds, pick changed"``), or ``"not scoreable (...)"``.
    - ``reason``       why the record could not be computed, or None when it could. Set exactly
                       when ``folds_scored`` is None.
    - ``recorded``     an ISO timestamp: when this row was written.
    """

    method_id: str
    seq: int
    run_at: str
    git_sha: str
    bench_n: int | None
    folds_total: int | None
    folds_scored: int | None
    folds_won: int | None
    majority: bool | None
    stable: bool | None
    picks_json: str
    summary: str
    reason: str | None
    recorded: str


FOLD_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(FoldRow))


def folds_of(conn: sqlite3.Connection, method_id: str) -> list[sqlite3.Row]:
    """Every recorded fold verdict of ``method_id``, oldest first; ``[]`` when it has none.

    A database on schema v1-v6 has no ``method_folds`` table at all and answers ``[]`` the same
    way -- ``connect`` migrates, so that can only be a ``connect_readonly`` caller or a raw
    read-only connection. ``amendments_of``, ``provenance_of``, ``moments_of`` and ``funding_of``
    all carry the same branch for the same reason.

    ``[]`` is also the honest answer for every method the lab ran before this table existed: the
    v6 -> v7 migration backfills nothing, because a past run's record cannot be recomputed as it
    read (see ``_v6_to_v7``).
    """
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'method_folds'"
    ).fetchone() is None:
        return []
    return list(conn.execute(
        "SELECT * FROM method_folds WHERE method_id = ? ORDER BY seq", (str(method_id),)
    ))


def latest_folds(conn: sqlite3.Connection, method_id: str) -> sqlite3.Row | None:
    """The newest recorded fold verdict of ``method_id``, or None when it has none.

    "Newest" is the highest ``seq``, not the latest ``recorded``: ``seq`` is contiguous and
    assigned under the run's own write lock, so it orders the batches even when two sessions
    stamp the same second. ``lab show`` prints this one; it is what the method's last run saw.
    """
    rows = folds_of(conn, method_id)
    return rows[-1] if rows else None


def insert_folds(conn: sqlite3.Connection, row: FoldRow) -> None:
    """Record one batch's fold verdict (the caller holds the transaction).

    Append-only, contiguous and prefix-shaped, exactly as ``insert_amendment`` is: ``seq`` must be
    one past the highest this method already has, so the recorded verdicts can never be a set with
    a hole in it. The method must already exist -- ``run_method`` adds it before it inserts the
    trials, and a verdict about a method the database has never heard of is not a record of
    anything.

    The "numbers or a reason, never both" rule is enforced here as well as by the table's CHECK,
    because a Python caller deserves a sentence rather than a constraint name. ``majority`` and
    ``stable`` are booleans in the dataclass and 0/1 in the table; the conversion is here, in one
    place, so no caller has to remember it.
    """
    if get_method(conn, row.method_id) is None:
        raise LabError(
            f"no method {row.method_id}: a fold verdict is recorded for a method the lab knows"
        )
    scoreable = row.reason is None
    if scoreable != (row.folds_scored is not None):
        raise LabError(
            f"{row.method_id}: a fold verdict carries either the numbers or the reason it has "
            f"none, never both and never neither (reason={row.reason!r}, "
            f"folds_scored={row.folds_scored!r})"
        )
    have = folds_of(conn, row.method_id)
    expected = len(have) + 1
    if row.seq != expected:
        raise LabError(
            f"{row.method_id}: fold verdict seq must be {expected} (it has {len(have)} "
            f"recorded), got {row.seq}. method_folds is append-only and contiguous, so the "
            f"recorded verdicts stay a prefix of the method's run history"
        )
    cols = ", ".join(f'"{c}"' for c in FOLD_COLUMNS)
    marks = ", ".join("?" for _ in FOLD_COLUMNS)
    conn.execute(
        f"INSERT INTO method_folds ({cols}) VALUES ({marks})",
        [
            str(row.method_id), int(row.seq), row.run_at, row.git_sha,
            None if row.bench_n is None else int(row.bench_n),
            None if row.folds_total is None else int(row.folds_total),
            None if row.folds_scored is None else int(row.folds_scored),
            None if row.folds_won is None else int(row.folds_won),
            None if row.majority is None else int(bool(row.majority)),
            None if row.stable is None else int(bool(row.stable)),
            row.picks_json, row.summary, row.reason, row.recorded,
        ],
    )
```

**Impact:** `FOLD_COLUMNS` is derived from `fields(FoldRow)`, so the INSERT's value list above
must stay in dataclass field order. It is, and the test
`test_the_fold_columns_are_the_dataclass_fields_in_order` pins it.

---

### Step 5: `hardgate.FoldVerdict` and `hardgate.fold_verdict`

**File:** `engine/src/seer_engine/lab/hardgate.py:456` (the import block), `:452` (the docstring's
closing `"""`), and `:1201` (the blank line between `summary` and `check`).

**Change (a) — add `math` to the imports.** Replace line 456 (`import json`) with:

```python
import json
import math
```

**Change (b) — the `(D15)` decision paragraph.** Insert immediately before line 452 (the closing
`"""` of the module docstring), after the `(D13) still holds.` paragraph:

```
**(D15) Does `lab run` see the folds, and does a lost majority refuse it? -- it SEES them and
RECORDS them; it does not refuse.** Until now a researcher met the fold record only at
``lab promote``, after the method id was spent and often after the dev verdict had already been
written up. ``fold_verdict`` is a third sibling beside ``fold_record`` (strict, for the gate) and
``summary`` (display-only, for ``lab status``): **lenient and structured**. It catches
``store.LabError`` the way ``summary`` does, and returns either the record's numbers or the reason
there are none, as a value ``runner.run_method`` writes into ``store.method_folds`` inside the
same transaction as the trials.

It is **evidence, not a gate**, and the distinction is the whole of the decision:

- The handover that asked for this (HANDOVER_20261013-measure-the-constraint.md §2.1) asked for "a
  new column/report path, never an edit of recorded rows".
- ``check`` below already refuses a lost fold majority at ``lab promote``; ``store.TRANSITIONS``
  admits exactly one edge into ``promoted``; and ``runner.preflight_test`` refuses any method that
  is not ``promoted``. The test window is therefore already behind this rule, and a second gate at
  run time would only spend method ids to say what the first one already says.
- The record is **method-level and time-varying** -- scored over every recorded dev curve of the
  method against the benchmark -- so an amendment recorded tomorrow changes it. ``store.verdict``
  promises a verdict is "comparable across time"; a per-trial ``eligible`` that moved when a
  sibling row was appended would break that promise outright.

And it must never refuse the run, because the lab has to be able to bootstrap: ``pin_dev_store``
below is explicit that "a fresh lab has to be able to run before it has a benchmark". A lab with no
``REF-SPY-HOLD`` trial, a benchmark curve too short for ``MIN_FOLDS``, a method with no curve, or a
price fingerprint that is not the benchmark's (D10) each record the reason and the run completes.
``check`` is not touched by any of this and keeps its present behaviour exactly.
```

**Change (c) — the new code.** Insert at line 1201 (the blank line after `summary`'s
`return f"{folds}; kin {kin}"`, before `def check`), so that `summary` ends, then this block, then
`def check` unchanged:

```python


def _finite(x: float | None) -> float | None:
    """``x`` when it is a real, finite number; None otherwise.

    ``picks_json`` goes through ``json.dumps``, which writes a non-finite float as the bare token
    ``Infinity`` -- not JSON, and not something ``json.loads`` in another language will read. MAR
    is a ratio with a drawdown underneath it, so infinity is reachable on a curve that never fell.
    None is the honest answer and the one every other recorded column already uses for "there is
    no number here".
    """
    if x is None:
        return None
    v = float(x)
    return v if math.isfinite(v) else None


def _picks_json(picks: Sequence[wf.FoldPick]) -> str:
    """The per-fold detail of a record, as the JSON ``store.method_folds.picks_json`` keeps.

    Written out rather than left to be recomputed, because the record is **time-varying**: it is
    scored over every dev curve the method has, so the same question asked after the next
    amendment lands gives a different answer. These numbers are what the folds said on the day the
    batch ran, and they stay that.

    Compact separators and no key sorting: the key order is the one a reader wants (when, what was
    picked, what it did, what the benchmark did, who won), and the bytes are a record, so they are
    written the same way every time.
    """
    out = [
        {
            "fold": p.fold.index,
            "train_end": p.fold.train_end.isoformat(),
            "eval_start": p.fold.eval_start.isoformat(),
            "eval_end": p.fold.eval_end.isoformat(),
            "picked": p.picked,
            "train_mar": _finite(p.train_mar),
            "got": None if p.got is None else _finite(p.got.total_return),
            "bench": None if p.bench is None else _finite(p.bench.total_return),
            "beat": p.beat,
        }
        for p in picks
    ]
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, slots=True)
class FoldVerdict:
    """A method's walk-forward record as a value a run can record: the numbers, **or** the reason.

    The third sibling, beside the strict ``fold_record`` (the gate's) and the display-only
    ``summary`` (``lab status``'s). ``fold_record`` raises when the record cannot be built, which
    is right for a gate and wrong for a run: ``lab run`` must complete on a lab that has no
    benchmark yet. So this one carries the refusal as data.

    ``reason`` is None exactly when the numbers are present. Everything downstream -- the table's
    last CHECK, ``store.insert_folds``'s own check, ``scoreable`` -- restates that one invariant,
    deliberately, because a half-filled record is the failure mode worth three guards.

    ``picks_json`` is a string rather than a tuple of ``wf.FoldPick`` so this value round-trips
    through the database unchanged: ``from_row`` rebuilds exactly what ``fold_verdict`` produced,
    and ``lab show`` and ``lab run`` therefore print the same sentences from the same source.

    **It annotates; it does not gate.** See (D15) in this module's docstring.
    """

    method: str
    bench_n: int | None
    total: int | None
    scored: int | None
    won: int | None
    majority: bool | None
    stable: bool | None
    picks_json: str
    summary: str
    reason: str | None

    @property
    def scoreable(self) -> bool:
        return self.reason is None

    def line(self) -> str:
        """One line for a report: ``"3 of 4 folds"``, or the reason there is no number.

        When the method was scoreable on fewer folds than the geometry yields, the geometry's
        count is named too -- that gap is (D2)'s refusal at ``lab promote``, and a researcher who
        sees it at run time can fix it before the id is spent.
        """
        if self.reason is not None:
            return f"not scoreable ({self.reason})"
        if self.total is not None and self.scored is not None and self.scored < self.total:
            return f"{self.summary} (the benchmark's geometry yields {self.total})"
        return self.summary

    def note(self) -> str:
        """One plain sentence: what this record means for promotion, and that it gated nothing.

        The single source of that sentence. ``lab run`` prints it from the value it just recorded
        and ``lab show`` prints it from the row it read back, so the two can never drift and the
        reader is never left guessing whether the run was quietly weakened.
        """
        if self.reason is not None:
            return (
                "The folds could not be scored, so the reason was recorded instead of a record. "
                "Nothing was refused: `lab run` annotates, and `lab promote` is where a lost fold "
                "majority actually refuses."
            )
        if not self.scored:
            # Measured, not hypothetical: a method whose curve starts inside the last fold's
            # training slice -- the smoke fixture's 2014-2015 curve against the lab's 1993-2015
            # benchmark -- yields four folds and nothing to score on any of them. `Record.majority`
            # is False there, and printing the lost-majority warning for it would be a lie: the
            # method did not lose the folds, it was never in them.
            return (
                "The lab's folds could be cut, but none of them could be scored for this method "
                "-- its curve does not reach back far enough for any training slice to choose "
                "on. Nothing was refused here; thin evidence is a refusal at `lab promote`, "
                "which requires a method to be scoreable on every fold the geometry yields."
            )
        if self.majority:
            return (
                "A majority of the scoreable folds went this method's way, so the fold condition "
                "of the promote gate would pass today. It is re-checked at `lab promote`, which "
                "is where it is a gate; here it is evidence."
            )
        return (
            "This method lost a majority of its walk-forward folds. That does NOT make these "
            "trials ineligible and nothing was refused -- `lab promote` is where the fold "
            "majority is a gate, and `lab test` refuses anything that is not promoted, so the "
            "test window is already behind it. Read the line as the warning it is: a method that "
            "wins its twenty-year dev average and loses the folds is a selection, not an edge."
        )

    @classmethod
    def from_row(cls, row: Mapping[str, object] | sqlite3.Row) -> FoldVerdict:
        """Rebuild the verdict a run recorded, from its ``store.method_folds`` row.

        The inverse of what ``runner.run_method`` writes, field for field, so ``lab show`` prints
        exactly the sentences ``lab run`` printed. ``majority`` and ``stable`` come back out of
        SQLite as 0/1 integers and are turned back into booleans here, in the one place that knows
        the table stores them that way.
        """
        def opt_int(key: str) -> int | None:
            v = row[key]
            return None if v is None else int(v)  # type: ignore[arg-type]

        def opt_bool(key: str) -> bool | None:
            v = row[key]
            return None if v is None else bool(v)

        reason = row["reason"]
        return cls(
            method=str(row["method_id"]),
            bench_n=opt_int("bench_n"),
            total=opt_int("folds_total"),
            scored=opt_int("folds_scored"),
            won=opt_int("folds_won"),
            majority=opt_bool("majority"),
            stable=opt_bool("stable"),
            picks_json=str(row["picks_json"]),
            summary=str(row["summary"]),
            reason=None if reason is None else str(reason),
        )


def fold_verdict(
    conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None
) -> FoldVerdict:
    """``method_id``'s walk-forward record as a value, never a refusal. See (D15).

    The lenient, structured sibling of ``fold_record``. It calls exactly the gate's own functions
    -- ``geometry`` for the shared folds, ``fold_record`` for the de-funded scoring against them --
    so the number a run records and the number ``lab promote`` later checks are the same
    arithmetic, not two implementations of it. What differs is only what happens when that
    arithmetic cannot be done: the gate raises and this returns the sentence.

    ``store.LabError`` is caught from both calls, exactly as ``summary`` catches it, and for the
    same reason one layer down: ``runner.run_method`` must finish and record a trial batch on a
    lab that has no ``REF-SPY-HOLD`` benchmark yet, a benchmark curve too short for ``MIN_FOLDS``,
    a method whose curves are empty, or a price fingerprint that is not the benchmark's (D10).
    Every one of those is a real state of a working lab, not a bug, and none of them is a reason
    to throw away a completed backtest.

    When a ``geo`` is passed and the refusal came from ``fold_record``, the geometry's fold count
    still goes into the record: "the lab yields four folds and this method could be scored on none
    of them" is a more useful row than one with two blanks.

    Nothing here is a gate. ``check`` is untouched and still refuses the same promotions it did.
    """
    known = geo
    try:
        if known is None:
            known = geometry(conn)
        record = fold_record(conn, method_id, known)
    except store.LabError as e:
        reason = str(e)
        return FoldVerdict(
            method=method_id,
            bench_n=None if known is None else known.bench_n,
            total=None if known is None else len(known.folds),
            scored=None,
            won=None,
            majority=None,
            stable=None,
            picks_json="[]",
            summary=f"not scoreable ({reason})",
            reason=reason,
        )
    return FoldVerdict(
        method=method_id,
        bench_n=known.bench_n,
        total=len(known.folds),
        scored=len(record.scored),
        won=record.won,
        majority=record.majority,
        stable=record.stable,
        picks_json=_picks_json(record.picks),
        summary=record.summary(),
        reason=None,
    )
```

**Change (d) — `Mapping` in the imports.** `from_row` annotates `Mapping`; the module currently
imports only `Sequence` from `collections.abc` (line 459). Replace it with:

```python
from collections.abc import Mapping, Sequence
```

**Impact:** three new public names in `hardgate` and two private helpers. `fold_record`,
`variant_record`, `summary`, `fold_summary` and `check` are not edited.

---

### Step 6: `runner.Run` and the recording in `run_method`

**File:** `engine/src/seer_engine/lab/runner.py:110` (after the `Ran` dataclass), `:19-23` (the
module docstring's step 4), and `:586-740` (`run_method`).

**Change (a) — the module docstring.** Replace the `lab run` step 4 paragraph (`runner.py:19-23`)
with:

```
4. Eligible = the five P7a D8 conditions and ``store.DSR_LABEL`` (DSR >= 0.90 since 2026-10-07;
   LAB_LUCK_GATE_PLAN.md Decision D1). Insert the trials, set the method's ``source_sha`` and
   status (``dev-eligible`` when any trial is eligible, else ``rejected``), all in one
   transaction. ``store.verdict`` re-reads a recorded trial against the same threshold and N, so
   a verdict is comparable across time rather than frozen at its run date.
5. Score the method's whole walk-forward record against the lab's shared geometry and record it
   (``hardgate.fold_verdict`` -> ``store.method_folds``), **in that same transaction**, so the
   curves this batch just produced are inside the record it keeps and a rolled-back run leaves
   neither. **This annotates; it does not gate** (hardgate D15): no trial becomes ineligible, no
   status moves differently, and the run completes and records the *reason* when the record cannot
   be computed at all -- a fresh lab with no ``REF-SPY-HOLD`` benchmark has to be able to run. The
   fold majority stays a refusal at ``lab promote`` (``hardgate.check``), which is where it has
   always been and where ``lab test`` already depends on it.
```

**Change (b) — the `Run` dataclass.** Insert after `Ran` (runner.py line 110, before
`def _ordinal`):

```python
@dataclass(frozen=True)
class Run:
    """What one ``lab run`` produced: the variants it recorded, and the fold verdict it recorded.

    ``run_method`` returned a bare ``list[Ran]`` until the fold verdict existed. It returns this
    instead, rather than writing the row and making the caller go and read it back, so the command
    prints the object it wrote: ``lab run`` and ``lab show`` cannot end up disagreeing about what
    the folds said, because one is the value and the other is ``FoldVerdict.from_row`` of the very
    row that value produced.

    ``ran`` is a tuple, not a list: nothing downstream mutates it and a run's batch is a record.
    ``folds`` is the row as it was written -- ``seq`` included -- and ``verdict`` is the structured
    value it was written from, carrying the display sentences (``line``, ``note``).
    """

    ran: tuple[Ran, ...]
    folds: store.FoldRow
    verdict: "hardgate.FoldVerdict"


```

and extend the `TYPE_CHECKING` block (runner.py:85-86) so the annotation resolves for a type
checker without importing `hardgate` at module scope:

```python
if TYPE_CHECKING:  # typing only: prereg is imported inside the functions that use it, so
    from seer_engine.lab import hardgate, prereg  # importing `runner` never pulls in git or the docs tree
```

> **Why `hardgate` is not a module-level import.** `hardgate.trial_deposits` imports
> `seer_engine.lab.runner` *inside the function body* precisely to keep the two modules'
> import-time graph acyclic. Importing `hardgate` at `runner`'s module scope would work today and
> would make the next edit to either module a 50/50 bet. The local import in `run_method` below
> costs one dictionary lookup per run and keeps the invariant mechanical. `from __future__ import
> annotations` is already in force at `runner.py:65`, so the quoted annotation is never evaluated.

**Change (c) — the recording.** In `run_method`'s body, insert immediately after the
`store.insert_provenance(...)` call (which currently ends at runner.py:717, just before
`if amendment is None:`):

```python
        # The fold verdict of this batch, computed HERE: after the trials, their moments, their
        # funding and their provenance are all in, and inside this same transaction. Three things
        # make that the only correct place.
        #
        # - **This connection sees its own uncommitted rows.** `hardgate.fold_record` reads
        #   `trials.curve_json` for every dev trial of the method, so the curves this run has just
        #   recorded are in the record. Computing it before the inserts would score the method as
        #   it was yesterday.
        # - **After `insert_provenance`, not before.** The record's price rule (hardgate D10) reads
        #   `trial_provenance.price_fingerprint` for every curve it scores and fails closed on a
        #   trial that has none. Run one line earlier and every trial of this very batch would be
        #   reported as "has no provenance row", which is true for a few microseconds and
        #   misleading forever.
        # - **Inside the transaction.** A trial batch and the verdict on it are one record or
        #   neither, exactly as the moments, the funding and the provenance are.
        #
        # It ANNOTATES; it does not gate (hardgate D15). `fold_verdict` is lenient by
        # construction: no `REF-SPY-HOLD` benchmark, a geometry thinner than `hardgate.MIN_FOLDS`,
        # a method with no curve, or prices that are not the benchmark's all record the REASON and
        # the run still completes. A fresh lab has to be able to run before it has a benchmark
        # (`hardgate.pin_dev_store`). Nothing here reads or writes `trials.eligible` or
        # `methods.status`, and `hardgate.check` -- the real gate, at `lab promote` -- is untouched.
        from seer_engine.lab import hardgate  # local: see the `Run` docstring on the import graph

        verdict = hardgate.fold_verdict(conn, method.id)
        folds = store.FoldRow(
            method_id=method.id,
            seq=len(store.folds_of(conn, method.id)) + 1,
            run_at=ran[0].trial.run_at if ran else store.now_iso(),
            git_sha=git_sha,
            bench_n=verdict.bench_n,
            folds_total=verdict.total,
            folds_scored=verdict.scored,
            folds_won=verdict.won,
            majority=verdict.majority,
            stable=verdict.stable,
            picks_json=verdict.picks_json,
            summary=verdict.summary,
            reason=verdict.reason,
            recorded=store.now_iso(),
        )
        store.insert_folds(conn, folds)
```

**Change (d) — the signature and the return.** Replace the signature line
(`runner.py:586-595`) and the final `return ran` (`runner.py:740`):

```python
def run_method(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    data: research.ResearchData,
    *,
    git_sha: str,
    require_commit: bool = True,
    amend: bool = False,
) -> Run:
```

and the last line of the function (after the `for key in method.seen_keys:` loop, outside the
`with conn:` block):

```python
    return Run(ran=tuple(ran), folds=folds, verdict=verdict)
```

**Change (e) — `run_method`'s docstring.** Append this paragraph after the existing `amend=True`
bullet list (runner.py:624, before the closing `"""`):

```
    Both paths end by recording the method's walk-forward record for this batch -- one
    ``store.method_folds`` row, inside the same transaction, computed after the provenance so the
    curves just recorded are in it and their prices are known (``hardgate.fold_verdict``). The
    row and the value it was built from come back on the returned ``Run``, so the command that
    prints the verdict prints the object that was written. **It annotates; it does not gate**
    (hardgate D15): no trial's ``eligible`` moves, no status moves differently, and a lab with no
    benchmark records the reason and completes. The fold majority is still a refusal at
    ``lab promote`` and nowhere else.
```

**Impact:** the return type changes. Four call sites, all updated in this phase (Steps 7 and 9).
`ran` inside the function is still the local `list[Ran]`, so nothing else in the body moves.

---

### Step 7: `lab run` and `lab show` print it

**File:** `engine/src/seer_engine/commands/lab.py:1399` (`_show`) and `:1489` (`_run`).

**Change (a) — `_show`.** Insert after the trials loop and before the
`if m["verdict"]:` block (commands/lab.py line 1431):

```python
    # The walk-forward record this method's last `lab run` recorded (store.method_folds, schema
    # v7). None -- so no line -- for a method that has not run, and for every method that ran
    # before the table existed: the migration backfills nothing, because a past run's record
    # cannot be recomputed as it read (store._v6_to_v7).
    #
    # Printed through `hardgate.FoldVerdict.from_row`, which is the exact inverse of what the run
    # wrote, so this line and the one `lab run` printed are the same sentence from the same code.
    folds_row = store.latest_folds(conn, m["id"])
    if folds_row is not None:
        from seer_engine.lab import hardgate

        v = hardgate.FoldVerdict.from_row(folds_row)
        print(f"\nWalk-forward, recorded at the run of {folds_row['run_at']}: {v.line()}")
```

**Change (b) — `_run`.** Replace lines 1489-1493:

```python
    ran = runner.run_method(
        conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT), amend=amend
    )
    status = store.get_method(conn, method.id)["status"]
    log.info("%s: %d trial(s) recorded, status %s (%.1fs)", method.id, len(ran), status, time.perf_counter() - t0)
```

with:

```python
    done = runner.run_method(
        conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT), amend=amend
    )
    ran = done.ran
    status = store.get_method(conn, method.id)["status"]
    log.info("%s: %d trial(s) recorded, status %s (%.1fs)", method.id, len(ran), status, time.perf_counter() - t0)
```

and insert the fold block after the `Lab N (dev trials) is now ...` print (line 1496), before the
`if amendment is not None:` block:

```python
    # The run's walk-forward verdict, printed from the value that was just recorded (R1). This is
    # the part a researcher never used to see until `lab promote`, by which time the method id was
    # spent and the dev write-up was already written.
    #
    # It ANNOTATES; it does not gate (hardgate D15, store._FOLDS_TABLE). `done.verdict.note()` is
    # the single source of that sentence, and `lab show` prints the same one back off the row, so
    # the two can never drift. Nothing below refuses anything: a lost majority is a warning here
    # and a refusal at `lab promote`.
    v = done.verdict
    print(f"\nWalk-forward on the lab's shared folds: {v.line()}")
    print(f"  {v.note()}")
    for p in json.loads(v.picks_json):
        got = fmt_signed_pct(p["got"]) if p["got"] is not None else "-"
        bench = fmt_signed_pct(p["bench"]) if p["bench"] is not None else "-"
        mark = "-" if p["beat"] is None else ("won" if p["beat"] else "lost")
        print(
            f"  fold {p['fold']}  train to {p['train_end']}, score {p['eval_start']}.."
            f"{p['eval_end']}: {p['picked'] or '(no variant had enough history)'} "
            f"{got} vs SPY TR {bench}  {mark}"
        )
    print(
        "  Folds share training data, so they are a sanity check, never a significance test, and "
        "nothing here enters a DSR."
    )
```

**Change (c) — the `json` import.** `commands/lab.py` imports `json` locally inside `_walkforward`
(`:2189`) rather than at module scope. Add the same local import at the top of `_run`'s body,
beside the existing `from seer_engine.lab import hardgate, runner` (line 1441):

```python
def _run(conn, args) -> int:
    import json

    from seer_engine.lab import hardgate, runner
    from seer_engine.lab.method import discover
```

**Impact:** `lab run`'s stdout grows a fold block; `lab show`'s grows one line for a method that
has a recorded verdict. `lab status`, `lab walkforward` and `lab promote` are untouched.

> **`lab run` calls `_show`, so its output carries `line()` twice** — once in the method card and
> once at the head of the fold block. That is deliberate and should not be "fixed" by threading a
> flag through `_show`: `_show` is called with a hand-built `Namespace` from `_run` and from the
> hard-gate tests, and a keyword that changes its output is a second way for the two commands to
> disagree. One repeated eight-word line is cheaper than that.

---

### Step 8: the new test module

**File:** `engine/tests/test_lab_fold_verdict.py` (new).

**Code — the complete file:**

```python
"""R1: the walk-forward verdict every ``lab run`` now computes, records and prints.

The decision these tests pin is the one the handover asked to be made explicitly: a lost fold
majority **annotates** a run, it does not gate it (hardgate D15, store._FOLDS_TABLE). So the
assertions come in two halves -- the record is written, complete and append-only; and nothing
about eligibility, status or the promote gate moved because of it.

Every test builds its own temp lab. The fixtures are the hard gate's own (a ``REF-SPY-HOLD`` dev
trial whose span yields four folds, methods whose curves compound at a stated annual rate), so a
number here and a number in ``test_lab_hardgate.py`` mean the same thing.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from labkit import LAB_PRICE_FINGERPRINT, smoke_data, stamp_provenance
from seer_engine.backtest import regime
from seer_engine.backtest.dev import Candidate
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
SAME_PRICES = LAB_PRICE_FINGERPRINT
OTHER_PRICES = "e" * 64
BENCH_SPAN = (date(1993, 2, 1), date(2015, 10, 16))
DEV_SPAN = (date(1996, 1, 2), date(2015, 10, 16))


@pytest.fixture(autouse=True)
def _at_the_policy_these_fixtures_were_recorded_under(monkeypatch):
    """The same pin ``test_lab_hardgate.py`` carries: these labs are shaped like one recorded
    under ``all-trials``, which is what their ``n_trials_at_run`` values mean."""
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _months(start: date, end: date) -> list[date]:
    out, d = [], date(start.year, start.month, 1)
    while True:
        nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
        last = nxt - timedelta(days=1)
        if last > end:
            return out
        if last >= start:
            out.append(last)
        d = nxt


def _curve(months: list[date], annual: float) -> str:
    out, v = [], 1.0
    for d in months:
        out.append([d.isoformat(), round(v, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="",
        eligible=True, dsr=0.97, n_trials_at_run=60, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _benchmark(conn, *, prices: str | None = SAME_PRICES, curve_json: str | None = None) -> int:
    """The lab's REF-SPY-HOLD dev trial; returns its ``trials.n``."""
    with conn:
        store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="H-P7A-REF", candidate_id=regime.BENCH_CANDIDATE,
            config_digest="ref-spy-hold", start="1993-02-01", end="2015-10-16",
            store_fingerprint="5451195f",
            curve_json=_curve(_months(*BENCH_SPAN), 0.08) if curve_json is None else curve_json,
        )])
        stamp_provenance(conn, ns, price_fingerprint=prices)
    return int(ns[0])


def _method_with_curve(conn, mid="M0001", *, annual=0.15, prices=SAME_PRICES,
                       curve_json: str | None = None) -> None:
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family="trend", source_kind="knowledge",
                         hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=_curve(_months(*DEV_SPAN), annual) if curve_json is None else curve_json,
        )])
        stamp_provenance(conn, ns, price_fingerprint=prices)
        store.update_method(conn, mid, status="dev-eligible")


# ---- the store side: the table is a side table and it is append-only -------------------------


def test_the_fold_columns_are_the_dataclass_fields_in_order(conn):
    """``FOLD_COLUMNS`` is derived from ``fields(FoldRow)``, and ``insert_folds`` lists its values
    in that same order. A field reordered in the dataclass without the INSERT following would
    silently write every value into the wrong column, so the two are compared here rather than
    trusted."""
    assert store.FOLD_COLUMNS == (
        "method_id", "seq", "run_at", "git_sha", "bench_n", "folds_total", "folds_scored",
        "folds_won", "majority", "stable", "picks_json", "summary", "reason", "recorded",
    )
    cols = [r[1] for r in conn.execute("PRAGMA table_info(method_folds)")]
    assert tuple(cols) == store.FOLD_COLUMNS


def test_a_recorded_fold_verdict_is_append_only_and_contiguous(conn):
    _method_with_curve(conn)
    row = store.FoldRow(
        method_id="M0001", seq=1, run_at="2026-10-13T00:00:00+00:00", git_sha="abc",
        bench_n=None, folds_total=None, folds_scored=None, folds_won=None, majority=None,
        stable=None, picks_json="[]", summary="not scoreable (no benchmark)",
        reason="no benchmark", recorded="2026-10-13T00:00:01+00:00",
    )
    with conn:
        store.insert_folds(conn, row)
    assert len(store.folds_of(conn, "M0001")) == 1
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE method_folds SET summary = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM method_folds")
    with pytest.raises(store.LabError, match="seq must be 2"):
        with conn:
            store.insert_folds(conn, row)


def test_a_half_filled_verdict_is_refused_by_the_store_and_by_the_table(conn):
    """Numbers or a reason, never both and never neither -- the one invariant three guards
    restate (the dataclass docstring, ``insert_folds``, and the table's last CHECK)."""
    _method_with_curve(conn)
    both = store.FoldRow(
        method_id="M0001", seq=1, run_at="r", git_sha="g", bench_n=1, folds_total=4,
        folds_scored=4, folds_won=3, majority=True, stable=True, picks_json="[]",
        summary="3 of 4 folds", reason="and also a reason", recorded="x",
    )
    with pytest.raises(store.LabError, match="either the numbers or the reason"):
        with conn:
            store.insert_folds(conn, both)
    neither = store.FoldRow(
        method_id="M0001", seq=1, run_at="r", git_sha="g", bench_n=None, folds_total=None,
        folds_scored=None, folds_won=None, majority=None, stable=None, picks_json="[]",
        summary="?", reason=None, recorded="x",
    )
    with pytest.raises(store.LabError, match="either the numbers or the reason"):
        with conn:
            store.insert_folds(conn, neither)


def test_a_verdict_for_an_unknown_method_is_refused(conn):
    with pytest.raises(store.LabError, match="no method M9999"):
        with conn:
            store.insert_folds(conn, store.FoldRow(
                method_id="M9999", seq=1, run_at="r", git_sha="g", bench_n=None,
                folds_total=None, folds_scored=None, folds_won=None, majority=None, stable=None,
                picks_json="[]", summary="s", reason="r", recorded="x",
            ))


def test_latest_folds_is_the_newest_seq(conn):
    _method_with_curve(conn)
    for seq in (1, 2, 3):
        with conn:
            store.insert_folds(conn, store.FoldRow(
                method_id="M0001", seq=seq, run_at=f"r{seq}", git_sha="g", bench_n=None,
                folds_total=None, folds_scored=None, folds_won=None, majority=None, stable=None,
                picks_json="[]", summary=f"s{seq}", reason=f"why {seq}", recorded="x",
            ))
    assert store.latest_folds(conn, "M0001")["summary"] == "s3"
    assert store.latest_folds(conn, "M0002") is None


# ---- the lenient verdict: numbers, or the reason there are none ------------------------------


def test_the_verdict_is_the_strict_records_own_numbers(conn):
    """``fold_verdict`` must not be a second implementation of the gate's arithmetic: it calls
    ``geometry`` and ``fold_record``, and its numbers are theirs."""
    _benchmark(conn)
    _method_with_curve(conn, annual=0.15)
    geo = hardgate.geometry(conn)
    record = hardgate.fold_record(conn, "M0001", geo)
    v = hardgate.fold_verdict(conn, "M0001")
    assert v.scoreable and v.reason is None
    assert (v.won, v.scored, v.total) == (record.won, len(record.scored), len(geo.folds))
    assert (v.majority, v.stable) == (record.majority, record.stable)
    assert v.summary == record.summary()
    assert v.bench_n == geo.bench_n
    picks = json.loads(v.picks_json)
    assert len(picks) == len(record.picks)
    assert [p["beat"] for p in picks] == [p.beat for p in record.picks]


def test_no_benchmark_is_a_reason_and_never_a_refusal(conn):
    """D6, at the level of the function. ``fold_record`` raises here; ``fold_verdict`` does not."""
    _method_with_curve(conn)
    with pytest.raises(store.LabError):
        hardgate.fold_record(conn, "M0001")
    v = hardgate.fold_verdict(conn, "M0001")
    assert not v.scoreable
    assert regime.BENCH_CANDIDATE in v.reason
    assert (v.scored, v.won, v.total, v.bench_n) == (None, None, None, None)
    assert v.picks_json == "[]"
    assert v.line().startswith("not scoreable (")


def test_a_geometry_too_thin_for_min_folds_is_a_reason(conn):
    """``hardgate.MIN_FOLDS`` is 4; a benchmark spanning twelve years yields fewer."""
    _benchmark(conn, curve_json=_curve(_months(date(2004, 1, 1), date(2015, 10, 16)), 0.08))
    _method_with_curve(conn)
    v = hardgate.fold_verdict(conn, "M0001")
    assert not v.scoreable and str(hardgate.MIN_FOLDS) in v.reason


def test_a_method_with_no_curve_is_a_reason_and_the_geometry_still_counts(conn):
    """The geometry survived, so its fold count is recorded even though nothing could be scored:
    "the lab yields four folds and this method could be scored on none" is the useful row."""
    _benchmark(conn)
    _method_with_curve(conn, curve_json="[]")
    v = hardgate.fold_verdict(conn, "M0001")
    assert not v.scoreable and "no dev trial carrying a monthly curve" in v.reason
    assert v.total == len(hardgate.geometry(conn).folds) == 4
    assert v.scored is None


def test_prices_that_are_not_the_benchmarks_are_a_reason(conn):
    """D10 refuses the comparison; the run records why rather than crashing."""
    _benchmark(conn)
    _method_with_curve(conn, prices=OTHER_PRICES)
    v = hardgate.fold_verdict(conn, "M0001")
    assert not v.scoreable and "cannot be scored against" in v.reason


def test_a_verdict_round_trips_through_its_recorded_row(conn):
    """``lab run`` prints the value and ``lab show`` prints ``from_row`` of the row that value
    produced, so the two must be the same object field for field."""
    _benchmark(conn)
    _method_with_curve(conn)
    v = hardgate.fold_verdict(conn, "M0001")
    with conn:
        store.insert_folds(conn, store.FoldRow(
            method_id="M0001", seq=1, run_at="2026-10-13T00:00:00+00:00", git_sha="g",
            bench_n=v.bench_n, folds_total=v.total, folds_scored=v.scored, folds_won=v.won,
            majority=v.majority, stable=v.stable, picks_json=v.picks_json, summary=v.summary,
            reason=v.reason, recorded="2026-10-13T00:00:01+00:00",
        ))
    assert hardgate.FoldVerdict.from_row(store.latest_folds(conn, "M0001")) == v


# ---- the decision: it annotates, it does not gate ---------------------------------------------


def test_a_lost_majority_annotates_and_the_note_says_so(conn):
    """D1 in the words the reader actually sees. A lost majority prints a warning that names
    where the gate really is, and never claims the run was refused."""
    _benchmark(conn)
    _method_with_curve(conn, annual=0.02)  # under the benchmark's 8%: loses every fold
    v = hardgate.fold_verdict(conn, "M0001")
    assert v.scoreable and not v.majority and v.won == 0
    note = v.note()
    assert "does NOT make these trials ineligible" in note
    assert "`lab promote`" in note and "`lab test`" in note
    assert "refused" not in v.line()


def test_the_promote_gate_still_refuses_what_it_refused_before(conn):
    """The other half of D1: adding the record did not weaken the gate. The same lab whose run
    would only be annotated is still refused at ``lab promote``."""
    _benchmark(conn)
    _method_with_curve(conn, annual=0.02)
    assert hardgate.fold_verdict(conn, "M0001").scoreable
    with pytest.raises(store.LabError, match="strict majority"):
        hardgate.check(conn, "M0001")


# ---- the run records it, in the trials' own transaction ---------------------------------------


def _cand(cid: str, n: int = 50) -> Candidate:
    """A real ``Candidate``, spelled as ``test_lab_runner.py:30`` spells one.

    ``MONTHLY_HOLD`` and ``TIMING`` are what the existing runner tests use, and they clear
    ``runner.preflight``'s real-fee check (``real_cost_problem``), which runs even with
    ``require_commit=False``.
    """
    return Candidate(
        id=cid, family="M0001", rules=MONTHLY_HOLD, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=date(2026, 10, 4), owner_inputs=(),
    )


def _lab_method(mid: str = "M0001", cands=None, **kw) -> Method:
    base = dict(id=mid, name="n", family="trend", source_kind="knowledge", source_ref="",
                hypothesis="h", expected_failure="f",
                candidates=tuple(cands or (_cand(f"{mid}-A"),)))
    base.update(kw)
    return Method(**base)


def _on_lab_prices():
    """``smoke_data()`` claiming the prices the lab's recorded benchmark was measured on.

    **Measured, and the reason this helper exists.** ``labkit.smoke_data`` names its prices
    ``"smoke"``, while the seeded ``REF-SPY-HOLD`` trial carries the P7a fingerprint. A run on the
    bare fixture is therefore refused by hardgate (D10) and records *that* as its reason -- which
    is true, is itself worth a test (below), and is not what the rest of these tests are about.
    One ``dataclasses.replace`` says the prices match, which is the state ``lab run`` enforces in
    production through ``hardgate.pin_dev_store`` before any backtest runs.
    """
    return dataclasses.replace(smoke_data(), price_fingerprint=store.P7A_PRICE_FINGERPRINT)


@pytest.fixture()
def seeded(tmp_path):
    """A seeded lab -- the P7a record, whose ``REF-SPY-HOLD`` trial is the real benchmark and
    yields exactly four folds (measured 2026-10-13: ``len(hardgate.geometry(conn).folds) == 4``,
    which is ``hardgate.MIN_FOLDS``)."""
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


def test_a_run_records_exactly_one_fold_row_stamped_like_its_trials(seeded):
    done = runner.run_method(seeded, _lab_method(), HERE, _on_lab_prices(), git_sha="deadbeef",
                             require_commit=False)
    rows = store.folds_of(seeded, "M0001")
    assert len(rows) == 1
    row = rows[0]
    assert int(row["seq"]) == 1
    assert row["git_sha"] == "deadbeef"
    assert {row["run_at"]} == {t["run_at"] for t in store.trials_of(seeded, "M0001")}
    assert done.folds.method_id == "M0001" and done.folds.seq == 1
    assert hardgate.FoldVerdict.from_row(row) == done.verdict


def test_the_verdict_scores_the_curves_the_run_just_recorded(seeded):
    """The transaction property, as a before/after.

    Before the run, M0001 has no row at all and the record cannot be built. After it, the recorded
    row carries no reason and names the benchmark trial the folds were cut from -- which is only
    possible because the verdict was computed on a connection that can see its own uncommitted
    trials and their provenance.

    **Measured on this fixture:** four folds are cut and *none* of them can be scored, because the
    smoke market starts 2013-12-02 and its monthly curve runs 2014-02-28..2015-10-16, inside the
    last fold's training slice. That is a scoreable-but-empty record, not a refusal -- summary
    ``"no fold could be scored"``, ``folds_scored == 0``, four picks with ``picked`` None -- and
    the assertions below say so rather than pretending a two-year curve wins folds.
    """
    assert not hardgate.fold_verdict(seeded, "M0001").scoreable
    runner.run_method(seeded, _lab_method(), HERE, _on_lab_prices(), git_sha="x",
                      require_commit=False)
    row = store.latest_folds(seeded, "M0001")
    assert row["reason"] is None
    assert int(row["bench_n"]) == hardgate.geometry(seeded).bench_n
    assert int(row["folds_total"]) == len(hardgate.geometry(seeded).folds) == hardgate.MIN_FOLDS
    assert int(row["folds_scored"]) == 0 and int(row["folds_won"]) == 0
    assert row["summary"] == "no fold could be scored"
    picks = json.loads(row["picks_json"])
    assert len(picks) == 4 and all(p["picked"] is None for p in picks)
    # And the sentence the reader gets says "never in the folds", not "lost the folds".
    note = hardgate.FoldVerdict.from_row(row).note()
    assert "none of them could be scored" in note and "lost a majority" not in note


def test_a_run_whose_store_prices_are_not_the_benchmarks_records_that_reason(seeded):
    """D10 at run level, on the bare ``smoke_data()`` fixture -- whose prices are ``"smoke"`` and
    the seeded benchmark's are the P7a store's. In production ``hardgate.pin_dev_store`` refuses
    such a store before any backtest; here the run is made directly, and the point is that the
    verdict records the mismatch instead of crashing a completed batch."""
    done = runner.run_method(seeded, _lab_method(), HERE, smoke_data(), git_sha="x",
                             require_commit=False)
    row = store.latest_folds(seeded, "M0001")
    assert row["reason"] is not None and "cannot be scored against" in row["reason"]
    assert row["folds_scored"] is None and row["picks_json"] == "[]"
    assert int(row["folds_total"]) == 4  # the geometry survived; only the comparison did not
    assert len(done.ran) == 1  # and the batch was still recorded


def test_a_rolled_back_run_leaves_neither_the_trials_nor_the_verdict(seeded, monkeypatch):
    """One record or neither. ``mark_seen`` is the last statement inside the ``with conn:`` block,
    so making it raise aborts a run whose trials, side rows and fold verdict are all written."""
    before_trials = store.dev_trial_count(seeded)

    def boom(*_a, **_k):
        raise RuntimeError("abort the run after everything is written")

    monkeypatch.setattr(store, "mark_seen", boom)
    m = _lab_method(seen_keys=("concept:rollback",))
    with pytest.raises(RuntimeError):
        runner.run_method(seeded, m, HERE, _on_lab_prices(), git_sha="x", require_commit=False)
    assert store.dev_trial_count(seeded) == before_trials
    assert store.folds_of(seeded, "M0001") == []
    assert store.get_method(seeded, "M0001") is None


def test_a_run_on_a_lab_with_no_benchmark_completes_and_records_the_reason(conn):
    """D6, end to end and the one the plan names explicitly. An empty lab has no ``REF-SPY-HOLD``
    trial, so no fold can be scored -- and the run must still finish, because a fresh lab has to
    be able to run before it has a benchmark (``hardgate.pin_dev_store``)."""
    assert hardgate.benchmark_n(conn) is None
    done = runner.run_method(conn, _lab_method(), HERE, smoke_data(), git_sha="x",
                             require_commit=False)
    assert len(done.ran) == 1
    assert store.get_method(conn, "M0001")["status"] in ("rejected", "dev-eligible")
    row = store.latest_folds(conn, "M0001")
    assert row is not None and row["reason"] is not None
    assert regime.BENCH_CANDIDATE in row["reason"]
    assert row["folds_scored"] is None and row["folds_total"] is None
    assert row["picks_json"] == "[]" and row["bench_n"] is None
    # The annotation changed nothing about the trials it annotates.
    assert [bool(t["eligible"]) for t in store.trials_of(conn, "M0001")] == [
        r.trial.eligible for r in done.ran
    ]


def test_the_amend_path_records_a_second_verdict(seeded):
    """An amendment is a second batch under the same method id, so it is a second row at seq 2 --
    and the first row is untouched, because the table is append-only."""
    runner.run_method(seeded, _lab_method(), HERE, _on_lab_prices(), git_sha="x",
                      require_commit=False)
    first = dict(store.latest_folds(seeded, "M0001"))
    amended = _lab_method(amendments=(Amendment(
        added=date(2026, 10, 13), why="a second question", hypothesis="h2",
        expected_failure="f2", candidates=(_cand("M0001-B", n=20),),
    ),))
    runner.run_method(seeded, amended, HERE, _on_lab_prices(), git_sha="y",
                      require_commit=False, amend=True)
    rows = store.folds_of(seeded, "M0001")
    assert [int(r["seq"]) for r in rows] == [1, 2]
    assert dict(rows[0]) == first
    assert rows[1]["git_sha"] == "y"


# ---- what the commands print -------------------------------------------------------------


def test_lab_show_prints_the_recorded_verdict(seeded, capsys):
    runner.run_method(seeded, _lab_method(), HERE, _on_lab_prices(), git_sha="x",
                      require_commit=False)
    capsys.readouterr()
    lab_cmd._show(seeded, argparse.Namespace(method="M0001"))
    out = capsys.readouterr().out
    row = store.latest_folds(seeded, "M0001")
    assert "Walk-forward, recorded at the run of" in out
    assert hardgate.FoldVerdict.from_row(row).line() in out


def test_lab_show_prints_no_fold_line_for_a_method_that_has_none(seeded, capsys):
    """Every one of the 145 methods the lab ran before schema v7 is in this state, and a line that
    says nothing is worse than no line."""
    lab_cmd._show(seeded, argparse.Namespace(method="H-P7A-F1"))
    assert "Walk-forward" not in capsys.readouterr().out
```

**Impact:** 19 new tests. Three of them —
`test_a_run_on_a_lab_with_no_benchmark_completes_and_records_the_reason` (D6),
`test_a_lost_majority_annotates_and_the_note_says_so` (D1) and
`test_the_promote_gate_still_refuses_what_it_refused_before` (D1's other half) — are the ones the
plan index's exit criteria name.

> **Numbers in these fixtures were measured on 2026-10-13, not assumed.** On the seeded lab,
> `hardgate.geometry(conn)` cuts exactly **4** folds from the real `REF-SPY-HOLD` trial #1
> (`bench_n == 1`), which is `hardgate.MIN_FOLDS` on the nose. `labkit.smoke_data()` names its
> prices `"smoke"` while that benchmark carries the **P7a** fingerprint, so a run on the bare
> fixture records the D10 mismatch as its reason — `_on_lab_prices()` is what the tests that want
> numbers use. And a run on matching prices produces a **scoreable but empty** record
> (`folds_total=4, folds_scored=0, summary="no fold could be scored"`), because the smoke market
> starts 2013-12-02 and its monthly curve runs 2014-02-28..2015-10-16, entirely inside the last
> fold's training slice. That case is exactly why `FoldVerdict.note()` needs its `not self.scored`
> branch: `Record.majority` is `False` there, and the lost-majority warning would be a lie.
>
> If `Method`'s or `Candidate`'s constructor has moved since, read
> `engine/tests/test_lab_runner.py:30-43` and `engine/tests/test_lab_amendments.py` for the
> spellings actually in use and follow them. The *assertions* are the contract; the fixture
> plumbing is not.

---

### Step 9: the existing tests that must move

**File (a):** `engine/tests/test_lab_snapshot.py`.

**Change 1 — the schema strippers.** Replace lines 28-39 (`_without_amendments` and the
`V5_SCHEMA = _without_amendments(store._SCHEMA)` line) with:

```python
def _without_folds(schema: str) -> str:
    """``schema`` as it read at v6: the ``method_folds`` table and its triggers removed.

    Derived from ``store._SCHEMA`` exactly as the three strippers below are, and chained ahead of
    them, so a "v5" fixture does not quietly carry a v7 table. The assertions fail loudly if the
    statements stop being laid out one per paragraph, which is what makes the strip exact.
    """
    for ddl in (store._FOLDS_TABLE, *store._FOLDS_TRIGGERS):
        assert f"{ddl};\n\n" in schema
        schema = schema.replace(f"{ddl};\n\n", "")
    assert "method_folds" not in schema
    return schema


def _without_amendments(schema: str) -> str:
    """``schema`` as it read at v5: the ``method_amendments`` table and its triggers removed.

    Derived from ``store._SCHEMA`` exactly as ``_without_moments`` and ``_without_provenance`` are,
    for the same reason: a fixture that is supposed to be an older database must not quietly carry
    a newer table.
    """
    for ddl in (store._AMENDMENTS_TABLE, *store._AMENDMENTS_TRIGGERS):
        assert f"{ddl};\n\n" in schema
        schema = schema.replace(f"{ddl};\n\n", "")
    assert "method_amendments" not in schema
    return schema


V6_SCHEMA = _without_folds(store._SCHEMA)
V5_SCHEMA = _without_amendments(V6_SCHEMA)
```

**Change 2 — the three pinned version numbers.** `"6"` becomes `"7"` at lines 133, 377 and 454:

```python
        assert store.schema_version(conn) == store.SCHEMA_VERSION == "7"
```

**Change 3 — the v6 -> v7 migration test.** Append after
`test_connect_migrates_a_v5_database_adding_method_amendments_and_touching_no_row` (ends line 487):

```python
def _folds_schema(conn) -> list[tuple[str, str, str]]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'method_folds' "
        "ORDER BY type, name"
    )]


def _v6_db(path):
    """A schema-v6 database: one method that has run, one dev trial, no method_folds table."""
    c = sqlite3.connect(path)
    c.executescript(V6_SCHEMA)
    c.executemany("INSERT INTO transitions (src, dst) VALUES (?, ?)", store.TRANSITIONS)
    c.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '6')")
    c.execute(
        "INSERT INTO methods (id, name, family, source_kind, hypothesis, status, source_sha, "
        "created, updated) VALUES ('M0001', 'n', 'f', 'knowledge', 'h', 'dev-eligible', ?, "
        "'2026-10-01T00:00:00+00:00', '2026-10-01T00:00:00+00:00')",
        ("a" * 64,),
    )
    c.execute(
        'INSERT INTO trials (method_id, candidate_id, config_digest, config_text, rules_id, '
        'allocator_id, window, start, "end", store_fingerprint, git_sha, run_at, trades, '
        "sharpe, mar, failed, eligible, dsr, n_trials_at_run, curve_json) VALUES "
        "('M0001', 'M0001-A', 'd1', 't', 'r', 'a', 'dev', '2000-01-03', '2015-10-16', 'fp', "
        "'abc', '2026-10-05T00:00:00+00:00', 200, 0.945, 0.82, '', 0, 0.9, 110, '[]')"
    )
    c.execute(
        "INSERT INTO trial_provenance (trial_n, initial_idr, price_fingerprint, source, measured) "
        "VALUES (1, '20000000', NULL, 'backfill', '2026-10-09T00:00:00+00:00')"
    )
    c.commit()
    c.close()


def test_connect_migrates_a_v6_database_adding_method_folds_and_touching_no_row(tmp_path):
    """v6 -> v7 is purely additive: a table, two triggers, a version string, and nothing else.

    No method row and no trial row moves, and in particular ``trials.eligible`` is not touched:
    the fold verdict annotates, it has never decided eligibility, and this migration does not make
    it start. Nothing is backfilled either -- a past run's fold record cannot be recomputed as it
    read, so ``latest_folds`` answering None for every method that predates the table is the
    honest answer, not a gap.
    """
    db = tmp_path / "lab.sqlite"
    _v6_db(db)
    before = _trials_bytes(db)
    methods_before = sqlite3.connect(db).execute("SELECT * FROM methods ORDER BY id").fetchall()

    conn = store.connect(db)
    fresh = store.connect(tmp_path / "fresh.sqlite")
    try:
        assert store.schema_version(conn) == store.SCHEMA_VERSION == "7"
        assert _trials_bytes(db) == before
        assert [tuple(r) for r in conn.execute("SELECT * FROM methods ORDER BY id")] == [
            tuple(r) for r in methods_before
        ]
        assert _folds_schema(conn) == _folds_schema(fresh)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT count(*) FROM method_folds").fetchone()[0] == 0
        assert store.folds_of(conn, "M0001") == []
        assert store.latest_folds(conn, "M0001") is None
        with conn:
            store.insert_folds(conn, store.FoldRow(
                method_id="M0001", seq=1, run_at="2026-10-13T00:00:00+00:00", git_sha="deadbeef",
                bench_n=None, folds_total=None, folds_scored=None, folds_won=None, majority=None,
                stable=None, picks_json="[]", summary="not scoreable (no benchmark)",
                reason="no benchmark", recorded="2026-10-13T00:00:01+00:00",
            ))
        assert store.latest_folds(conn, "M0001")["git_sha"] == "deadbeef"
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE method_folds SET summary = 'x'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM method_folds")
        assert _trials_bytes(db) == before
    finally:
        conn.close()
        fresh.close()

    again = store.connect(db)  # idempotent: a second connect adds nothing
    try:
        assert store.schema_version(again) == store.SCHEMA_VERSION
        assert again.execute("SELECT count(*) FROM method_folds").fetchone()[0] == 1
        assert _trials_bytes(db) == before
    finally:
        again.close()


@pytest.mark.skipif(not store.COMMITTED_DB.is_file(), reason="no committed lab database here")
def test_the_v6_to_v7_migration_moves_not_one_byte_of_the_web_snapshot(tmp_path):
    """Decision D3, as a test rather than a claim.

    ``store.snapshot`` reads ``methods``, ``trials``, ``insights`` and ``ideas_seen`` only, so a
    new side table cannot change its bytes -- but "cannot" is an argument and this is the
    measurement, taken on a copy of the committed lab (the original is never opened for writing).
    ``SNAPSHOT_VERSION`` therefore does not move, ``web/data/lab.json`` is unchanged by this
    phase, and nothing under ``web/`` is touched.
    """
    db = tmp_path / "lab.sqlite"
    shutil.copyfile(store.COMMITTED_DB, db)
    ro = store.connect_readonly(db)
    try:
        before = store.snapshot_json(ro)
    finally:
        ro.close()
    store.connect(db).close()  # migrates in place, whatever version the committed file is at
    ro = store.connect_readonly(db)
    try:
        assert store.schema_version(ro) == store.SCHEMA_VERSION == "7"
        assert store.snapshot_json(ro) == before
    finally:
        ro.close()
    assert store.SNAPSHOT_VERSION == 5
```

**File (b):** `engine/tests/test_lab_runner.py` — three call sites take `.ran`.

- line 73: `ran = runner.run_method(conn, m, Path(__file__), data, git_sha="deadbeef", require_commit=False).ran`
- line 283: `ran = runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False).ran`
- line 297: `ran = runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False).ran`

No other test uses the return value; `test_lab_remeasure.py:73`'s `_run` helper returns it and
every caller discards it, so it needs no change.

**Impact:** `test_lab_snapshot.py` gains two tests and loses none. The three `"6"` assertions are
the tripwire that makes the schema bump deliberate.

---

## Verification

Run every command from the worktree. **This worktree has no `engine/.venv` and no
`engine/.research/`** — use the main checkout's interpreter and store.

**V1 — lint:**

```bash
/home/miftah/seer/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine
```

Expected: `All checks passed!` (CI is bugs only: E9 and F, minus F401).

**V2 — the suite.** `docker start seer-pg` first if the container is down:

```bash
docker start seer-pg
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

Expected: green, with **the skip count quoted beside the pass count** in the write-up — e.g.
`NNNN passed, MM skipped in SSs`. **Without `PG_TEST_URL` 385 tests skip silently and CI fails the
run; without `PYTHONPATH` pytest imports the main checkout and tests the wrong code.** If the skip
count is at or above 385, the environment is wrong, not the code.

**V3 — the new module alone, while iterating:**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q -n0 \
  tests/test_lab_fold_verdict.py tests/test_lab_snapshot.py tests/test_lab_runner.py \
  tests/test_lab_hardgate.py tests/test_lab_amendments.py tests/test_lab_remeasure.py
```

**V4 — the ladder runs v1 -> v7 in one open, and a v7 database does not migrate again.** Covered
by `test_connect_migrates_a_v1_database_keeping_rows_and_triggers` (which asserts
`== store.SCHEMA_VERSION`) and by each migration test's `again = store.connect(db)` block.

**V5 — the snapshot is byte-identical across the migration (Decision D3).** Run this on a **copy**
of the committed database and paste the output into the database commit's body:

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
import hashlib, shutil, tempfile
from pathlib import Path
from seer_engine.lab import store

src = Path("/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/lab/lab.sqlite")
tmp = Path(tempfile.mkdtemp()) / "lab.sqlite"
shutil.copyfile(src, tmp)

ro = store.connect_readonly(tmp)
v_before, before = store.schema_version(ro), store.snapshot_json(ro)
ro.close()

store.connect(tmp).close()          # migrates the COPY v6 -> v7

ro = store.connect_readonly(tmp)
v_after, after = store.schema_version(ro), store.snapshot_json(ro)
ro.close()

print("schema_version before:", v_before)
print("schema_version after :", v_after)
print("snapshot sha256 before:", hashlib.sha256(before.encode("utf-8")).hexdigest())
print("snapshot sha256 after :", hashlib.sha256(after.encode("utf-8")).hexdigest())
print("byte-identical:", before == after)
print("SNAPSHOT_VERSION:", store.SNAPSHOT_VERSION)
committed = Path("/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/web/data/lab.json")
print("web/data/lab.json sha256:", hashlib.sha256(committed.read_bytes()).hexdigest())
print("export matches committed file:", committed.read_bytes() == after.encode("utf-8"))
PY
```

Expected:

```
schema_version before: 6
schema_version after : 7
snapshot sha256 before: <X>
snapshot sha256 after : <X>          # the same hex string
byte-identical: True
SNAPSHOT_VERSION: 5
web/data/lab.json sha256: <X>
export matches committed file: True
```

If `export matches committed file` is `False`, a **peer phase is mid-write** and the committed
`lab.json` is already behind its database — stop and reconcile with the coordinator rather than
staging on top of it.

**V6 — `lab show` and `lab run` print it.** Covered by
`test_lab_show_prints_the_recorded_verdict` and
`test_lab_show_prints_no_fold_line_for_a_method_that_has_none`. A manual look at `lab show` on the
migrated database (which will print no fold line, because nothing has run under v7 yet):

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab show M0130
```

**V7 — `test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database`.**
This test reads the **working tree** database, so it goes red whenever any concurrent session is
mid-write. **Do not treat a red there as this phase's failure without checking.** The real check is
the git blob comparison:

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label && \
git show HEAD:lab/lab.sqlite | sha256sum && \
git show HEAD:web/data/lab.json | sha256sum && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
import hashlib, subprocess, tempfile
from pathlib import Path
from seer_engine.lab import store
blob = subprocess.run(["git", "show", "HEAD:lab/lab.sqlite"], capture_output=True,
                      cwd="/home/miftah/.worktrees/seer/fold-verdict-and-fall-label").stdout
tmp = Path(tempfile.mkdtemp()) / "lab.sqlite"
tmp.write_bytes(blob)
ro = store.connect_readonly(tmp)
print("committed db version:", store.schema_version(ro))
print("export of committed db sha256:",
      hashlib.sha256(store.snapshot_json(ro).encode("utf-8")).hexdigest())
ro.close()
PY
```

The `web/data/lab.json` blob's sha256 must equal the "export of committed db" sha256, and the
committed db version must read `7`.

**Exit criteria (restated as observable facts):**

1. `store.SCHEMA_VERSION == "7"`; a v1 database reaches v7 in one `connect`; a v7 database
   reconnected migrates nothing.
2. `lab run` on a method writes exactly one `method_folds` row in the same transaction as its
   trials; a rolled-back run leaves neither.
3. A lab with no `REF-SPY-HOLD` benchmark, or a geometry thinner than `hardgate.MIN_FOLDS`,
   completes the run and records the reason. Tested.
4. The `--amend` path writes a row at `seq = 2` and leaves `seq = 1` byte-identical.
5. `lab show MNNNN` prints the recorded verdict; `lab run`'s stdout carries it plus the plain
   sentence that the gate is still at `lab promote`.
6. `store.snapshot_json` is byte-identical across the migration on the committed database —
   **proved by V5 and quoted in the commit body**; `SNAPSHOT_VERSION` is still 5; `web/` untouched.
7. `hardgate.check` is unchanged and still refuses a lost majority — tested directly.
8. `lab stage` has run; `lab/lab.sqlite` and `web/data/lab.json` are committed together with no
   pathspec; the git-blob check in V7 passes.
9. `ruff` clean; the suite green with the skip count quoted beside the pass count.

---

## Order of operations (the one-way door)

Do these in order. Do not reorder 3 and 4.

1. **Source and tests.** Make every change in Steps 1-9. Run V1, V2, V3.
2. **Commit the source** — explicit pathspec, `-m` **before** `--`, and `git add --` first for the
   new test file:

   ```bash
   cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
   git add -- engine/tests/test_lab_fold_verdict.py
   git commit -m "lab: record the walk-forward verdict on every run

   Every lab run now scores the method's whole fold record against the lab's shared
   geometry and writes it to a new append-only method_folds side table, in the same
   transaction as the trials, and prints it. A lost fold majority ANNOTATES: no trial
   becomes ineligible, no status moves differently, and the fold majority is still a
   refusal at lab promote and nowhere else (hardgate D15). A lab with no benchmark,
   too thin a geometry, no curve or prices that are not the benchmark's records the
   reason and the run completes.

   Schema 6 -> 7. This is a one-way door: a v7 database opened by older code raises
   LabError, so the migrated lab/lab.sqlite lands in the very next commit and the two
   are pushed together.

   Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
     -- engine/src/seer_engine/lab/store.py \
        engine/src/seer_engine/lab/hardgate.py \
        engine/src/seer_engine/lab/runner.py \
        engine/src/seer_engine/commands/lab.py \
        engine/tests/test_lab_fold_verdict.py \
        engine/tests/test_lab_snapshot.py \
        engine/tests/test_lab_runner.py
   git show --stat HEAD      # the file list must equal exactly those seven paths
   git log -1                # the message must be yours
   ```

3. **Run V5** (the snapshot proof, on a copy). Keep the output.
4. **Migrate and stage the committed database.** Opening it with `store.connect` migrates it:

   ```bash
   cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
   git status --short        # must be clean apart from this phase's own leftovers
   PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
   /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage
   git status --short        # lab/lab.sqlite and web/data/lab.json staged; lab.json expected unchanged
   git commit -m "lab: migrate the committed lab to schema 7 (method_folds)

   Empty table, two append-only triggers, one version string. Nothing is backfilled:
   a past run's fold record cannot be recomputed as it read, because the lab has
   recorded curves since, so latest_folds answering None for every method that ran
   before today is the honest answer.

   The web snapshot does not move one byte -- store.snapshot reads methods, trials,
   insights and ideas_seen only. Measured on a copy of this file:

     schema_version before: 6
     schema_version after : 7
     snapshot sha256 before: <paste V5's hash>
     snapshot sha256 after : <paste V5's hash>
     byte-identical: True
     SNAPSHOT_VERSION: 5

   Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
   ```

   **No pathspec on this commit.** `lab stage` writes `web/data/lab.json` and `git add`s it with
   the database under one exclusive lock, so the index is self-consistent by construction; a
   pathspec commit re-reads the working tree and can pair a newer `lab.sqlite` with an older
   `lab.json`. Check `git status --short` first so a bare commit sweeps nothing else.

5. **Run V2 again** (the suite, on the migrated database) and **V7** (the git-blob check).
6. **Push both commits together.** Never push step 2's commit without step 4's following it in the
   same push, and never push step 4's alone.

### Rules every command in this phase obeys, and that any subagent you dispatch must be told verbatim

> This worktree and its git index are shared by every concurrent phase session.
> **`git reset --hard`, `git clean`, `git checkout .` and every bare-path form are BANNED.**
> Every commit except the lab-database one is by explicit pathspec with `-m` **before** `--`, and
> `git add -- <newfile>` first for a file this phase creates. The lab-database commit is
> `lab stage && git commit` with **no** pathspec. Verify with `git show --stat HEAD` that the file
> list equals the allowlist and `git log -1` carries your own message. Write the
> `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` trailer out verbatim; do not substitute
> your own model name.

Other standing rules this phase runs under:

- `lab.sqlite` **migrates on connect even for a read**. To inspect it without dirtying it, use
  `sqlite3 'file:lab/lab.sqlite?mode=ro' ...` or `store.connect_readonly`. After step 4 that no
  longer matters for this phase, but it matters while steps 1-3 are in flight.
- The **test window is never read**. No `lab test`, no `lab promote`, and `engine/.research-test`
  is never named.
- `argparse` `help=` strings are %-interpolated. This phase adds no parser, so there is nothing to
  escape — but do not introduce one.

---

## Handoffs

Work found while planning this phase and deliberately left where it belongs:

- **Publishing the fold verdict to `/sera` (R1's "report path", web half).** Not in this set
  (Decision D3). `store.snapshot` would gain a `folds` block and `SNAPSHOT_VERSION` would move to
  6, which is a `web/` change the handover did not ask for. The table is there when someone wants
  it. **Not any phase in this set.**
- **Backfilling `method_folds` for the 145 methods that ran before it.** Deliberately impossible
  as a *record* — a re-score today gives the record the lab computes now, not the one that run
  would have seen — but a separate "fold record as of today, for every method" **report** would be
  cheap and useful. **Not any phase in this set**; it is a new idea for the todos.
- **`lab status`'s fold column still recomputes through `hardgate.summary`** rather than reading
  the recorded row. Leaving it alone is correct: `lab status` is a *today* view and the recorded
  row is a *then* record, and conflating them would be a worse report. Noted so the next reader
  does not "fix" it.
- **Phase 2 (`lab/tree_rank.py`, R2)** is untouched here: no label, no allocator, no params class.
- **Phase 4 (`lab/turnover.py` + the `turnover` subparser, R3)** adds the only new subparser in
  this set; this phase adds none, so there is no `_HANDLERS`-table conflict between us. (The
  dispatch table in `commands/lab.py:2637` is named `_HANDLERS`, not `COMMANDS` — phase 4 verified
  this; the index's and the analysis's `COMMANDS` was wrong.)
- **Phase 5 (R2's method file)** will be the first run to actually write a `method_folds` row on
  the committed lab. Its write-up is asked to quote the printed fold verdict — that line comes
  from `hardgate.FoldVerdict.line()` and `note()`, which this phase owns.
- **Phases 3, 4 and 5 must all run on this phase's code**, because every one of them opens
  `lab/lab.sqlite` and it will be at v7. That is why they depend on phase 1.

---

## Rollback

This phase is two commits and they come out together, **newest first**:

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
git revert --no-edit <sha of the database commit>
git revert --no-edit <sha of the source commit>
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python -c "
from seer_engine.lab import store
ro = store.connect_readonly()
print('schema_version:', store.schema_version(ro)); ro.close()"
```

The last command must print `schema_version: 6`. **Reverting the source without the database
leaves the lab unopenable** — v6 code refuses a v7 file — so the pairing is not optional, and
`git revert` of the database commit must land before anyone runs a lab command on the old code.

`git reset --hard` is banned here even for a rollback: peers' work in progress lives in this same
tree.

Nothing else needs undoing. No recorded row was edited, `web/data/lab.json` did not move, no
method id was spent, and no test-window look was touched.
