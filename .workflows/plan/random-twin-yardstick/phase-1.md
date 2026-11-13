# Phase 1: Roles in the record, role-aware status and the demotion door

**Plan set:** `RANDOM_TWIN_YARDSTICK_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-125454-Y7RT_code_analyzer.md`
**Satisfies:** R3 — "Derive status from treatment arms only. Arm roles already exist (the hard gate reads them to refuse promoting a control); the status line just ignores them."
**Criteria:** R3.1, R3.2, R3.3, R3.4
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

Every dev arm's role (`control`, `dose`, `idea`, `treatment`, read by `control_shape.role_of`
from its rationale) is recorded beside its trial in a new append-only `trial_roles` side table.
`lab run` writes it and fails every control arm with `store.CONTROL_LABEL`, so only a non-control
arm can make a method `dev-eligible`; `store.verdict` refuses a recorded control, so
`best_dev_eligible` never chooses one. `lab roles --backfill` records the roles of the arms the
lab already holds, and `lab reevaluate --demote` is the one narrow door from `dev-eligible` back
to `rejected`.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `store.TRIAL_ROLES = ("control", "dose", "idea", "treatment")` (`lab/store.py`, after `is_luck_label`, ~line 190) — pinned equal to `control_shape.ROLES` by a test
- `store.CONTROL_ROLE = "control"`, `store.ROLE_SOURCES = ("recorded", "backfill")` (same place)
- `store.CONTROL_LABEL = "not a control arm"` (same place)
- `store._ROLES_TABLE`, `store._ROLES_TRIGGERS` (after `_FOLDS_TRIGGERS`, ~line 513) and their three statements in `_SCHEMA` (after `{_FOLDS_TRIGGERS[1]};`, ~line 666). Table `trial_roles(trial_n INTEGER PRIMARY KEY REFERENCES trials(n), role TEXT NOT NULL CHECK (role IN ('control','dose','idea','treatment')), source TEXT NOT NULL CHECK (source IN ('recorded','backfill')), measured TEXT NOT NULL)`, triggers `trial_roles_no_update`, `trial_roles_no_delete`
- `store.TRANSITIONS` edge `("dev-eligible", "rejected")` (inserted after `("dev-eligible", "promoted")`)
- `store.DEMOTION_MARKER = "Demoted under the "`, `store.demote_method(conn, method_id) -> Reevaluation`, `store.demote(conn, method_ids=None) -> list[Reevaluation]` (after `store.reevaluate`, ~line 2154)
- `store.RoleRow(trial_n, role, source, measured)`, `store.ROLE_COLUMNS`, `store.role_of_trial(conn, trial_n) -> str | None`, `store.insert_roles(conn, rows) -> None`, `store.unroled_dev_trials(conn, method_ids=None) -> list[sqlite3.Row]` (new section `# --- trial roles` after `insert_folds`, before `# --- ideas_seen`, ~line 2731)
- `runner.Ran.role: str | None = None` (new last field)
- CLI: `lab reevaluate --demote [MNNNN ...]`, `lab roles [MNNNN ...] [--backfill]`; handlers `commands.lab._demote`, `commands.lab._roles_cmd` (after `_reevaluate`, ~line 2297); `_HANDLERS["roles"]`
- `engine/tests/test_lab_roles.py` (new)

**Signature changes:**
- `store.Reevaluation` gains two defaulted trailing fields: `eligible_now: tuple[str, ...] = ()`, `controls: int = 0`. Every existing constructor still works.
- `store.reevaluate_method(conn, method_id)` signature unchanged; behaviour: a `rejected` method whose `analysis` carries `DEMOTION_MARKER` is also unblocked by a dev trial that is eligible under `verdict` today **even though its recorded `eligible` is 1** (the independent `_blocking` re-check still applies). Without it a method demoted on a recorded-eligible arm could never come back, and the index's Rollback promise ("plain `lab reevaluate` moves back any that clear today's bars") would be false (Step 9b). **Phase 4 edits the `_blocking(...)` call in this same loop; the lines this step changes are outside the snippet phase 4 replaces.**
- `store.verdict(...)` signature unchanged; behaviour: appends `CONTROL_LABEL` after the luck label when `role_of_trial(conn, trial["n"]) == "control"`. Label order is now: owner conditions, luck label, `CONTROL_LABEL`. **Phase 4 appends `YARDSTICK_LABEL` after `CONTROL_LABEL`.**
- `runner.trial_rows(...)` signature unchanged; behaviour: appends `store.CONTROL_LABEL` to a control arm's `failed` after the luck label, and sets `Ran.role`.
- `runner.run_method(...)` signature unchanged; behaviour: inserts one `trial_roles` row (`source='recorded'`, `measured=trial.run_at`) per trial, after `insert_provenance` and before the fold verdict, on both the first-run and the `--amend` path.

**Requires (from earlier phases):** none.

**Leaves alone (owned by others):** anything named `yardstick` (phases 2-4); `lab/hardgate.py` (D18 stays an independent refusal, phase 4 edits it); the snapshot functions `store.py:3069-3487` and `SNAPSHOT_VERSION` (phase 5); `web/` (phase 5); `engine/tests/test_lab_snapshot.py` (phase 5, see Handoffs); `lab/lab.sqlite` (never committed); every recorded method file.

**Where my additions sit, for phases 3 and 4 to quote the post-phase-1 files:**
- `store.py`: role constants directly after `is_luck_label`; `_ROLES_TABLE`/`_ROLES_TRIGGERS` directly after `_FOLDS_TRIGGERS`; the three role statements are the last side-table statements in `_SCHEMA`, immediately before `CREATE TRIGGER IF NOT EXISTS trials_no_update`; `DEMOTION_MARKER`/`demote_method`/`demote` directly after `reevaluate`; the `trial roles` section directly after `insert_folds`. Phase 3's `trial_yardstick` table/triggers go after `_ROLES_TRIGGERS` and after the role statements in `_SCHEMA`; its helpers section goes after the `trial roles` section.
- `runner.py`: the control-label lines sit immediately after `failed.append(store.DSR_LABEL)` in `trial_rows`; the `insert_roles` block sits immediately after the `insert_provenance` block in `run_method`.
- `commands/lab.py`: the `roles` parser sits immediately after the `reevaluate` parser (before `"test"`); `_demote` and `_roles_cmd` sit immediately after `_reevaluate` (before `_test_plan`); `"roles": _roles_cmd` sits after `"reevaluate"` in `_HANDLERS`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | `trial_roles` table + helpers, role constants, `CONTROL_LABEL` in `verdict`, the `dev-eligible -> rejected` edge, `demote_method`/`demote`, two `Reevaluation` fields, the demoted-method clause in `reevaluate_method` (the way back), docstrings |
| `engine/src/seer_engine/lab/runner.py` | modify | `trial_rows` fails control arms and carries `Ran.role`; `run_method` records role rows; docstrings |
| `engine/src/seer_engine/commands/lab.py` | modify | `lab reevaluate --demote`, `lab roles [--backfill]`, module docstring, `_HANDLERS` |
| `engine/tests/test_lab_roles.py` | create | every R3 criterion, invariant 5, the help strings |
| `.claude/skills/verify-seer/features/lab-cli.md` | modify | the two new user-facing commands and how to drive them |

No existing test file needs an edit, checked one by one: `test_lab_store.py:158` (`test_status_only_moves_forward`) moves out of `rejected` only; `test_paper_roster.py:730` (`_lab_reachable`) gains `rejected` as reachable from `dev-eligible`, which only widens what it accepts; `test_lab_hardgate.py`'s D18 fixtures insert trials by hand (no role row) and the committed-lab tests open `mode=ro` (no table); `test_lab_runner.py`'s candidates carry `rationale="test"` (a treatment); `test_lab_snapshot.py`'s fixture lab has no role row, so `LIVE_LABELS` holds (Handoffs).

## Implementation Steps

### Step 1: Role constants and the control label
**File:** `engine/src/seer_engine/lab/store.py:190` (directly after the `is_luck_label` function, before the `# The N the luck test deflates by` comment)
**Change:** add the four constants. They must sit above `_quoted`'s first use in a table f-string (`_ROLES_TABLE`, Step 3); `_quoted` itself is defined at line 238 and is only called at module import inside f-strings defined below it, so placing these at ~190 is safe.
**Code:**
```python
#: The roles ``control_shape.role_of`` can answer, spelled here as literals because this module
#: imports nothing from the lab at module scope (see ``OWNER_INPUTS_LABEL``) and the
#: ``trial_roles`` CHECK needs them when ``_SCHEMA`` is built. ``test_lab_roles`` pins this tuple
#: to ``control_shape.ROLES``, so the two cannot drift apart.
TRIAL_ROLES: tuple[str, ...] = ("control", "dose", "idea", "treatment")

#: The one role anything refuses on: an arm registered to be beaten.
CONTROL_ROLE = "control"

#: How a ``trial_roles`` row came to be: written by the run that recorded the trial
#: (``recorded``), or added after the fact by ``lab roles --backfill`` from the method file as it
#: reads now (``backfill``).
ROLE_SOURCES: tuple[str, ...] = ("recorded", "backfill")

# The failure label of an arm registered to be beaten (random-twin-yardstick R3, 2026-11-13). It
# is not a seventh screen condition and no threshold sits behind it: it says the arm's *role*
# forbids eligibility whatever its numbers, so a method is never ``dev-eligible`` on the strength
# of its own placebo, paired baseline or mirror. ``runner.trial_rows`` writes it into a new
# control's ``trials.failed`` and ``verdict`` appends it for every trial whose ``trial_roles`` row
# says ``control`` -- after the luck label, so the conditions keep their order -- and the record
# and the verdict therefore agree on the run date. Worded as the condition the arm misses, the
# way every other label is ("beats SPY TR", "PF >= 1.3").
CONTROL_LABEL = "not a control arm"
```
**Impact:** none on its own.

### Step 2: The edge back out of `dev-eligible`
**File:** `engine/src/seer_engine/lab/store.py:140` (inside `TRANSITIONS`, directly after `("dev-eligible", "promoted"),`)
**Change:** add the edge. `connect` inserts `TRANSITIONS` with `INSERT OR IGNORE` on every open (store.py:727), so an existing database gains the row on its next connect with no migration; `methods_status_forward` (store.py:677) then admits the update.
**Code:**
```python
    ("dev-eligible", "promoted"),
    # The one edge back out of ``dev-eligible`` (random-twin-yardstick R3, 2026-11-13). Admitted
    # only by ``demote_method``, and only for a method none of whose dev trials reads eligible
    # under ``verdict`` today -- most often because the only arms that ever cleared the screen
    # were control arms, which ``verdict`` refuses once their role is recorded. Like the
    # ``rejected -> dev-eligible`` edge above, it erases no verdict: the trials stay in the
    # append-only ``trials`` table, untouched, and the demotion is *appended* to the analysis.
    ("dev-eligible", "rejected"),
```
(The existing `("dev-eligible", "promoted"),` line is shown for placement and is not duplicated.)
**Impact:** the transition trigger now admits `dev-eligible -> rejected`. `test_paper_roster._lab_reachable` widens accordingly (still passes).

### Step 3: The `trial_roles` table and its triggers
**File:** `engine/src/seer_engine/lab/store.py:513` (directly after the closing `)` of `_FOLDS_TRIGGERS`, before the `#: The backfill's capital rule` comment)
**Change:** add the DDL constants.
**Code:**
```python
# The trial_roles side table and its two triggers (random-twin-yardstick R3, 2026-11-13).
#
# **What it records and why.** An arm's role is its author's one-line rationale, read by
# ``control_shape.role_of``; it lives in the method file and nowhere in ``trials``. The hard gate
# reads it at ``lab promote`` (hardgate D18), but ``verdict``, ``best_dev_eligible`` and the
# ``lab run`` status line did not, so a method whose only eligible arm was its own placebo read
# ``dev-eligible``. Recording the role beside the trial lets ``verdict`` refuse a control from the
# database alone -- no method import on every read, and the same answer on a read-only snapshot
# connection.
#
# A side table, not a column on ``trials``, for the reason every side table above is one:
# ``ALTER TABLE trials ADD COLUMN`` would move every recorded row's bytes. ``trial_n`` is the
# primary key, so a trial has at most one role and INSERT is the whole lifecycle; the two CHECKs
# refuse a role ``role_of`` cannot answer and a source nobody writes.
#
# **No schema version.** Unlike every table above, this one arrived without a migration step:
# ``_SCHEMA`` runs on every ``connect`` and ``CREATE TABLE IF NOT EXISTS`` adds it to an existing
# v8 database in place. A version bump is a one-way door for every parallel checkout
# (``_migrate``); an additive table whose reader answers None when it is absent is not.
_ROLES_TABLE = f"""CREATE TABLE IF NOT EXISTS trial_roles (
    trial_n  INTEGER PRIMARY KEY REFERENCES trials(n),
    role     TEXT NOT NULL CHECK (role IN ({_quoted(TRIAL_ROLES)})),
    source   TEXT NOT NULL CHECK (source IN ({_quoted(ROLE_SOURCES)})),
    measured TEXT NOT NULL CHECK (length(trim(measured)) > 0)
)"""
_ROLES_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS trial_roles_no_update BEFORE UPDATE ON trial_roles
BEGIN SELECT RAISE(ABORT, 'trial_roles are append-only: a role row is never updated'); END""",
    """CREATE TRIGGER IF NOT EXISTS trial_roles_no_delete BEFORE DELETE ON trial_roles
BEGIN SELECT RAISE(ABORT, 'trial_roles are append-only: a role row is never deleted'); END""",
)
```
**File:** `engine/src/seer_engine/lab/store.py:666` (inside `_SCHEMA`, directly after the `{_FOLDS_TRIGGERS[1]};` paragraph and its blank line, before `CREATE TRIGGER IF NOT EXISTS trials_no_update`)
**Code:** (one statement per paragraph, the layout `test_lab_snapshot.py`'s strippers rely on)
```
{_ROLES_TABLE};

{_ROLES_TRIGGERS[0]};

{_ROLES_TRIGGERS[1]};

```
**Impact:** every `connect` creates the table if missing. `SCHEMA_VERSION` stays `"8"`. The old-version fixtures in `test_lab_snapshot.py` are derived from `_SCHEMA` and so now carry an empty `trial_roles`; no assertion there enumerates tables, so they pass.

### Step 4: Module docstring — the new table
**File:** `engine/src/seer_engine/lab/store.py:57` (end of the `Tables:` list, directly after the `method_folds` bullet's last line `Triggers refuse every UPDATE and DELETE.`, before the blank line and `Schema versions`)
**Code:**
```
- ``trial_roles``: the part one dev trial's arm plays in its method's experiment -- ``control``,
  ``dose``, ``idea`` or ``treatment``, read by ``control_shape.role_of`` from the arm's one-line
  rationale -- recorded so that ``verdict`` can refuse a control arm without opening a method
  file. ``lab run`` writes one row per trial in its own transaction (``source='recorded'``);
  ``lab roles --backfill`` adds the rows for trials recorded before the table existed whose
  method file can still be read (``source='backfill'``). At most one row per trial, keyed by
  ``trials.n``. Triggers refuse every UPDATE and DELETE. **No schema version came with it**: the
  table is created by ``CREATE TABLE IF NOT EXISTS`` inside ``_SCHEMA`` on every connect, and
  ``role_of_trial`` answers None when it is absent.
```
**Impact:** docs only.

### Step 5: The role helpers
**File:** `engine/src/seer_engine/lab/store.py:2731` (new section directly after the end of `insert_folds`, before `# --------------------------------------------------------------------------- ideas_seen`)
**Code:**
```python
# --------------------------------------------------------------------------- trial roles


@dataclass(frozen=True)
class RoleRow:
    """The part one dev trial's arm plays in its method's experiment (``_ROLES_TABLE``).

    - ``trial_n``  the ``trials.n`` this describes. ``insert_trials`` assigns it, so
                   ``run_method`` builds the row after the insert; ``insert_roles`` refuses the
                   pre-insert sentinel ``0``.
    - ``role``     one of ``TRIAL_ROLES``: ``control_shape.role_of`` on the arm's rationale.
    - ``source``   ``"recorded"`` when the run that recorded the trial wrote it, from the
                   candidate it had just simulated; ``"backfill"`` when ``lab roles --backfill``
                   added it later from the method file as it reads now.
    - ``measured`` an ISO timestamp: the trial's own ``run_at`` for a recorded row, the moment
                   of the backfill for a backfilled one.
    """

    trial_n: int
    role: str
    source: str
    measured: str


ROLE_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(RoleRow))


def role_of_trial(conn: sqlite3.Connection, trial_n: int) -> str | None:
    """The recorded role of one trial's arm (one of ``TRIAL_ROLES``), or None when it has none.

    None is the normal answer for every trial recorded before the table existed whose role has
    not been backfilled -- the P7a seed rows never will be, having no method file -- and for every
    test-window look, which ``lab run`` does not record. It means "not known", never "not a
    control": ``verdict`` then judges the trial exactly as it did before roles were recorded.

    A database opened read-only by a checkout that never created the table has no
    ``trial_roles`` at all, and is answered the same way, exactly as ``funding_of`` answers for
    ``trial_funding`` -- ``snapshot`` runs on ``connect_readonly`` and must keep working there.
    """
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'trial_roles'"
    ).fetchone() is None:
        return None
    row = conn.execute(
        "SELECT role FROM trial_roles WHERE trial_n = ?", (int(trial_n),)
    ).fetchone()
    return None if row is None else str(row[0])


def insert_roles(conn: sqlite3.Connection, rows: Sequence[RoleRow]) -> None:
    """Record the role of trials that already exist (the caller holds the transaction).

    Append-only and one row per trial: a trial that already has a role is refused rather than
    overwritten, so ``lab roles --backfill`` is made idempotent by asking ``unroled_dev_trials``
    for what is still missing instead of racing the triggers. The role and the source are checked
    here, once, with a sentence a reader can act on; the table's CHECKs are the floor under it.
    ``trial_n`` must be a real trial number -- the foreign key enforces that the trial exists, and
    the explicit check turns the pre-insert sentinel ``0`` into a readable refusal.
    """
    cols = ", ".join(f'"{c}"' for c in ROLE_COLUMNS)
    marks = ", ".join("?" for _ in ROLE_COLUMNS)
    for r in rows:
        if r.trial_n <= 0:
            raise LabError(
                f"roles need the trial number insert_trials assigned, got {r.trial_n!r}: insert "
                "the trial first, then record its role"
            )
        if r.role not in TRIAL_ROLES:
            raise LabError(
                f"trial {r.trial_n}: {r.role!r} is not a role control_shape.role_of can answer "
                f"({', '.join(TRIAL_ROLES)})"
            )
        if r.source not in ROLE_SOURCES:
            raise LabError(
                f"trial {r.trial_n}: source {r.source!r} is not one of {', '.join(ROLE_SOURCES)}"
            )
        if role_of_trial(conn, r.trial_n) is not None:
            raise LabError(
                f"trial {r.trial_n} already has a recorded role: trial_roles is append-only, and "
                "a second role for one arm would be two answers to one question"
            )
        conn.execute(
            f"INSERT INTO trial_roles ({cols}) VALUES ({marks})",
            [getattr(r, c) for c in ROLE_COLUMNS],
        )


def unroled_dev_trials(
    conn: sqlite3.Connection, method_ids: Sequence[str] | None = None
) -> list[sqlite3.Row]:
    """Every dev trial with no ``trial_roles`` row, in trial order; only ``method_ids``' when given.

    What ``lab roles --backfill`` still has to read, and what ``lab reevaluate --demote`` warns
    about: a control arm in this list still counts as eligible, because ``verdict`` refuses only a
    role it can read from the record. On a database without the table every dev trial is listed.
    An empty ``method_ids`` lists nothing.
    """
    have_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'trial_roles'"
    ).fetchone() is not None
    sql = "SELECT t.* FROM trials t WHERE t.window = 'dev'"
    params: list[Any] = []
    if have_table:
        sql += " AND NOT EXISTS (SELECT 1 FROM trial_roles r WHERE r.trial_n = t.n)"
    if method_ids is not None:
        ids = [str(m) for m in method_ids]
        if not ids:
            return []
        sql += f" AND t.method_id IN ({', '.join('?' for _ in ids)})"
        params.extend(ids)
    return conn.execute(sql + " ORDER BY t.n", params).fetchall()
```
**Impact:** new API only.

### Step 6: `verdict` refuses a recorded control
**File:** `engine/src/seer_engine/lab/store.py:1433-1450` (`Verdict` docstring, first paragraph)
**Change:** replace the first paragraph of the `Verdict` docstring with:
```
    ``failed`` is the ordered tuple of failure labels (``trials.failed`` is the same list,
    "; "-joined): owner conditions first in ``dev.FAILURE_LABELS`` order, then the luck label,
    then ``CONTROL_LABEL`` for a trial recorded as a control arm. ``eligible`` is
    ``failed == ()``, always.
```
**File:** `engine/src/seer_engine/lab/store.py:1810-1878` (`verdict`)
**Change:** add one docstring paragraph and the control rule. Full replacement of the function:
**Code:**
```python
def verdict(
    conn: sqlite3.Connection,
    trial: Mapping[str, Any] | sqlite3.Row,
    *,
    at: Gate | None = None,
    policy: str | None = None,
) -> Verdict:
    """``trial``'s eligibility as it reads now: every condition, at the bars in force now.

    ``trial`` is a ``trials`` row (anything addressable by column name, including a
    ``sqlite3.Row``) carrying ``n``, ``dsr``, ``sharpe``, ``failed``, ``n_trials_at_run`` and the
    four metric columns. Meaningful for ``window = 'dev'`` rows: a test trial's DSR is recorded
    and is not a condition, because a pre-registered look has no selection among results to
    deflate.

    The recorded columns are the lab's history and are never written (design §1, plan invariant
    3). This is the *read*: what the same trial is judged as today, by the bars the lab holds
    today, rather than by the bars in force on its run date. That is R2's comparability, obtained
    without rewriting anything.

    **Nothing is ever returned verbatim.** Every one of the six conditions is decided here:

    - the four **threshold** owner conditions are re-derived from this row's recorded columns by
      ``owner_failures``, against the live ``tuning.DEV_MAX_DRAWDOWN`` /
      ``tuning.MIN_PROFIT_FACTOR`` / ``dev._MIN_TRADES``, so a trial recorded under the old 15%
      drawdown bar reads against today's 50% dev screen. The drawdown number here is the
      **screen** and not the owner's real-money ``tuning.MAX_DRAWDOWN``: the two were separated on
      2026-10-14 (design §18), and this function answers what is worth studying;
    - ``owner inputs`` is carried from the recorded string, because it is not a threshold and no
      constant re-decides it;
    - the **luck** test is decided on ``dsr_at(conn, trial, g.n)`` -- this trial's DSR **at the
      gate's current N**, never at the N it happened to be run under.

    **The luck test is always evaluated at the current N, and that is the whole of R2.** An
    earlier draft re-thresholded the recorded ``dsr`` only when ``n_trials_at_run`` already
    equalled the gate's N, and returned the row verbatim otherwise. That rule is **superseded and
    must not be implemented**: it would admit ``M0007-N20-RAW`` on a DSR of 0.9138 computed at
    N = 85 while judging ``M0022``'s variants on DSRs computed at N = 110 -- a candidate admitted
    for having been tried *earlier*, which is precisely the leaderboard-mixes-bars defect R2
    names and precisely the self-deception the lab exists to prevent. Re-evaluated at today's
    N = 110, ``M0007-N20-RAW`` is **0.8985** and does not clear 0.90.

    **A DSR that cannot be evaluated fails the luck test.** ``dsr_at`` returns None for the 54
    P7a seed rows, whose ``dsr`` is NULL by construction, and ``verdict`` then appends the luck
    label -- the same rule ``runner.trial_rows`` applies to a new trial
    (``if dsr is None or dsr < DSR_MIN``). Without it, ``F9-SPY200M70-MOM30`` (19.2% drawdown,
    MAR 0.64, no recorded DSR) would become eligible the moment the drawdown bar moved, on the
    strength of a luck test nobody ever ran. ``derived`` is False exactly in this case, and
    ``dsr`` is None with it.

    **A recorded control arm is never eligible** (random-twin-yardstick R3). When this trial's
    ``trial_roles`` row says ``control`` -- an arm registered to be beaten -- ``CONTROL_LABEL`` is
    appended after the luck label, whatever its numbers. It is the label ``runner.trial_rows``
    writes into a new control's ``failed``, so the record and this read agree on the run date,
    and ``best_dev_eligible`` stops choosing controls with no rule of its own. A trial with no
    role row, and every trial on a database without the table, reads exactly as it did before
    the table existed.

    ``at`` resolves the gate once for a caller judging many trials. ``policy`` names a different
    policy for a read-only comparison (phase 5's ``lab luck``); the write paths never pass it.
    """
    g = gate(conn, policy) if at is None else at
    dsr = dsr_at(conn, trial, g.n)
    # Four re-derived from this row's columns against the live constants, one (`owner inputs`)
    # carried from the recorded string. Never parsed out of `failed` -- that string names the
    # bars in force on the run date, which are not today's. `beats SPY TR` is money-weighted for
    # a trial that received deposits (`trial_funding`) and the recorded total-return comparison
    # for every one that did not, which is all 128 recorded trials.
    failed = owner_failures(trial, funding_of(conn, trial["n"]))
    # The same rule runner.trial_rows applies to a new trial: a DSR that is None is a luck test
    # that was not passed. Nothing is admitted for being unmeasurable.
    if dsr is None or dsr < DSR_MIN:
        failed = failed + (DSR_LABEL,)
    # An arm registered to be beaten never makes its method eligible, whatever its numbers. Read
    # from the recorded role, never from the method file, so this read opens nothing; a trial with
    # no role row (or a database without the table) is judged exactly as before.
    if role_of_trial(conn, trial["n"]) == CONTROL_ROLE:
        failed = failed + (CONTROL_LABEL,)
    return Verdict(
        dsr=dsr, failed=failed, eligible=not failed, n=g.n, policy=g.policy,
        derived=dsr is not None,
    )
```
**Impact:** every reader of `verdict` (`best_dev_eligible`, `reevaluate_method`, `published_verdict` → snapshot `failedNow`/`eligibleNow`, `lab status`, `remeasure`) reads a recorded control as not eligible. No role row anywhere → byte-identical verdicts (invariant 5; J2 proves it).

### Step 7: `best_dev_eligible` docstring
**File:** `engine/src/seer_engine/lab/store.py:1385-1391` (`best_dev_eligible` docstring, directly after the paragraph that ends `` ``M0022-W-TV16`` (MAR 0.816, DSR 0.916) is not.``)
**Change:** insert one paragraph; the code is unchanged.
**Code:**
```
    **A recorded control arm is never the answer** (random-twin-yardstick R3), and this function
    has no rule of its own for it: ``verdict`` appends ``CONTROL_LABEL`` to every trial whose
    ``trial_roles`` row says ``control``, so such a row is simply not eligible here. A trial with
    no role row is judged exactly as before -- which is why ``lab roles --backfill`` exists, and
    why hardgate D18 still reads the method file at ``lab promote`` as a second, independent
    refusal.
```
**Impact:** docs only; behaviour comes from Step 6.

### Step 8: `Reevaluation` gains two defaulted fields
**File:** `engine/src/seer_engine/lab/store.py:1942-1954`
**Code:**
```python
@dataclass(frozen=True)
class Reevaluation:
    """What ``reevaluate_method`` or ``demote_method`` found, and whether it moved the method."""

    method_id: str
    status_before: str
    status_after: str
    moved: bool
    gate: Gate
    unblocked: tuple[str, ...]  # candidate ids now eligible that the recorded column rejects
    derived: int                # dev trials whose DSR was evaluated at the gate's N
    unjudgeable: int            # dev trials with no evaluable DSR -- they fail the luck test
    dev_trials: int
    eligible_now: tuple[str, ...] = ()  # candidate ids eligible under ``verdict`` now (demotion)
    controls: int = 0                   # dev trials recorded as control arms (demotion)
```
**Impact:** the two `Reevaluation(...)` calls in `reevaluate_method` stay valid (keyword args, defaults).

### Step 9: The demotion door
**File:** `engine/src/seer_engine/lab/store.py:2154` (directly after `reevaluate`, before `# --- trial moments`)
**Code:**
```python
# The first words of the analysis section ``demote_method`` appends. Like ``REEVALUATION_MARKER``
# it is not an idempotence key: the edge it guards leads out of the only status it may be taken
# from, so a method is demoted at most once per stay in ``dev-eligible``.
DEMOTION_MARKER = "Demoted under the "


def demote_method(conn: sqlite3.Connection, method_id: str) -> Reevaluation:
    """Move a ``dev-eligible`` method none of whose dev trials reads eligible today to ``rejected``.

    The mirror of ``reevaluate_method``, and **as narrow**. It may take exactly one edge, from
    exactly one status, for exactly one reason:

    - the method must read ``dev-eligible`` now. Any other status is left alone and ``moved`` is
      False -- a ``promoted`` method in particular is a pre-registration, a promise this function
      never unpicks.
    - it must have at least one dev trial. A method with none has nothing to be judged on and is
      left where it is rather than demoted on an absence.
    - **no** dev trial of it may be eligible under ``verdict`` at the gate in force now. That one
      rule covers both ways a status goes stale: a method whose only eligible arms were control
      arms, which ``verdict`` refuses once their ``trial_roles`` row exists, and a method whose
      arms have since sunk under the luck bar as N grew.

    It is deliberately **not** run by plain ``lab reevaluate``. Demotion is an explicit act
    (``lab reevaluate --demote``, plan Decision D6), for the reason ``reevaluate_method`` is
    narrow: a sweep that could move a method either way on every call would let a status flicker
    with every Sera batch.

    It reads roles from ``trial_roles`` only. A control arm with no role row still counts as an
    eligible arm here, so a sweep run before ``lab roles --backfill`` can only demote too little,
    never too much; ``lab reevaluate --demote`` says so when it sees one.

    Nothing in ``trials`` is written: no row is inserted, updated or deleted, so the lab's N does
    not move and ``test_looks`` is untouched. What is written is one dated section appended to
    ``analysis`` (append-only by trigger), in the owner's plain words because the method page
    shows it, and the ``status`` column. Both happen in the caller's transaction, so a crash
    leaves neither.

    The caller holds the transaction (``begin_immediate`` / ``with conn``), as every other writer
    in this module does.
    """
    from seer_engine.backtest import tuning  # for the drawdown screen named in the analysis text

    row = get_method(conn, method_id)
    if row is None:
        raise LabError(f"no method {method_id}")
    status = str(row["status"])
    trials = conn.execute(
        "SELECT * FROM trials WHERE method_id = ? AND window = 'dev' ORDER BY n", (method_id,)
    ).fetchall()
    g = gate(conn)
    eligible_now: list[str] = []
    derived = 0
    controls = 0
    for t in trials:
        v = verdict(conn, t, at=g)
        derived += 1 if v.derived else 0
        if role_of_trial(conn, t["n"]) == CONTROL_ROLE:
            controls += 1
        if v.eligible:
            eligible_now.append(str(t["candidate_id"]))
    found = Reevaluation(
        method_id=method_id,
        status_before=status,
        status_after=status,
        moved=False,
        gate=g,
        unblocked=(),
        derived=derived,
        unjudgeable=len(trials) - derived,
        dev_trials=len(trials),
        eligible_now=tuple(eligible_now),
        controls=controls,
    )
    if status != "dev-eligible" or not trials or eligible_now:
        return found

    k = len(trials)
    runs = "1 run" if k == 1 else f"{k} runs"
    if controls == 0:
        why = (
            "None of them is a comparison arm: each misses at least one condition at today's bars."
        )
    elif controls == k:
        why = (
            "Every one of them is a comparison arm, registered in advance to be beaten, and a "
            "comparison arm never counts."
        )
    else:
        arms = (
            "1 of them is a comparison arm" if controls == 1
            else f"{controls} of them are comparison arms"
        )
        why = (
            f"{arms}, registered in advance to be beaten, which never count; each of the others "
            f"misses at least one condition at today's bars."
        )
    lines = [
        "# Re-evaluation",
        "",
        f"{DEMOTION_MARKER}bars in force on {date.today().isoformat()}: the luck test (a "
        f"deflated Sharpe of at least {DSR_MIN:.2f}, with the lab's count of tries at {g.n}), "
        f"the {tuning.DEV_MAX_DRAWDOWN:.0%} drawdown screen, and the rule that a comparison arm "
        f"never makes a method worth studying.",
        "",
        f"None of this method's {runs} on the study window clears every condition today. {why}",
        "",
        "Nothing recorded changed: every run keeps the numbers and the verdict it was given on "
        "its own day. Status moves from dev-eligible back to rejected.",
    ]
    append_analysis(conn, method_id, "\n".join(lines))
    update_method(conn, method_id, status="rejected")
    return Reevaluation(
        method_id=method_id,
        status_before=status,
        status_after="rejected",
        moved=True,
        gate=g,
        unblocked=(),
        derived=derived,
        unjudgeable=len(trials) - derived,
        dev_trials=len(trials),
        eligible_now=(),
        controls=controls,
    )


def demote(
    conn: sqlite3.Connection, method_ids: Sequence[str] | None = None
) -> list[Reevaluation]:
    """``demote_method`` over ``method_ids``, or over every ``dev-eligible`` method when None.

    The caller holds the transaction, so the whole sweep is one atomic unit: either every method
    it demotes moves, or none does.
    """
    if method_ids is None:
        method_ids = [
            str(r[0])
            for r in conn.execute(
                "SELECT id FROM methods WHERE status = 'dev-eligible' ORDER BY id"
            )
        ]
    return [demote_method(conn, m) for m in method_ids]
```
**Impact:** new write path, reached only through `lab reevaluate --demote`.

### Step 9b: The way back — `reevaluate_method` reconsiders a demoted method's recorded-eligible arms
**File:** `engine/src/seer_engine/lab/store.py:2014-2131` (`reevaluate_method`, today's text; Step 9 adds nothing inside it)
**Why:** `reevaluate_method` unblocks only trials whose *recorded* `eligible` is 0 (`if not bool(t["eligible"]):`). A method `demote_method` moved `dev-eligible -> rejected` usually got there through an arm recorded eligible (1) that no longer reads eligible -- a control once its role was recorded, or an arm that sank under the luck bar or (phase 4) lost to its twins. Without this step such a method could never come back, even when that very arm clears every condition again. The door must be reversible (plan Decision D10).
**Change 1 (docstring):** in the bullet list, replace the bullet
```
    - at least one of its dev trials must be eligible under the derived verdict and not already
      recorded eligible.
```
with
```
    - at least one of its dev trials must be eligible under the derived verdict and not already
      recorded eligible -- or, for a method ``demote_method`` moved here (its analysis carries
      ``DEMOTION_MARKER``), eligible under the derived verdict whatever it recorded, because a
      demotion is the one way a method reaches ``rejected`` while holding a recorded-eligible arm,
      and the way back must be open to that same arm (random-twin-yardstick, Decision D10).
```
**Change 2 (body):** directly after `status = str(row["status"])`, insert
```python
    # A method demote_method moved here may hold arms recorded eligible (1) that read eligible
    # again today. They unblock it too; any other rejected method keeps the narrow rule.
    demoted = DEMOTION_MARKER in str(row["analysis"] or "")
```
and replace
```python
        if not bool(t["eligible"]):
            unblocked.append(str(t["candidate_id"]))
            verdicts[str(t["candidate_id"])] = v
```
with
```python
        if demoted or not bool(t["eligible"]):
            unblocked.append(str(t["candidate_id"]))
            verdicts[str(t["candidate_id"])] = v
```
`DEMOTION_MARKER` is defined after `reevaluate` (Step 9) and resolved at call time. The independent `_blocking` re-check above these lines is untouched and still runs first for every derived-eligible trial, so this widens the *which arm* rule, never the *which numbers* rule. Phase 4 later replaces the `blocking = _blocking(...)` / `raise LabError(...)` lines in this loop; those lines are not changed here.
**Impact:** plain `lab reevaluate` moves a demoted method back to `dev-eligible` the moment any of its non-control arms clears every condition again; a rejected method that was never demoted is judged exactly as before. Proven by `test_plain_reevaluate_takes_a_demoted_method_back_when_its_arm_clears_again` (Step 14, journey J6).

### Step 10: `trial_rows` fails control arms and carries the role
**File:** `engine/src/seer_engine/lab/runner.py:90`
**Change:** import `control_shape` (already imported at module scope by `twins`, which `runner` imports, so no new cycle).
**Code:**
```python
from seer_engine.lab import control_shape, store, twins
```
**File:** `engine/src/seer_engine/lab/runner.py:102-122` (`Ran`)
**Code:**
```python
@dataclass(frozen=True)
class Ran:
    """One finished variant: its database row, its dev row, and the DSR's inputs.

    ``moments`` carries ``trial_n=0`` until ``insert_trials`` assigns the real trial number;
    ``run_method`` stamps it and records it. It is None exactly when ``daily_moments`` returned
    None for this variant, which is exactly when ``trial.dsr`` is None -- a trial that never had
    a deflated Sharpe has no inputs to keep. It defaults to None so a caller that only cares
    about the trial can still build a ``Ran`` positionally.

    ``funding`` is the same pattern for the same reason: ``trial_n=0`` until the insert, stamped
    with ``dataclasses.replace`` afterwards, and None exactly when the variant received no
    deposit. **The existence of the row is the funded flag** (``store.FundingRow``), so None here
    must produce no row at all rather than a row of zeroes -- ``trial_funding`` CHECKs
    ``deposits_usd > 0`` and ``deposits_n >= 1`` and would refuse one.

    ``role`` is ``control_shape.role_of`` on the candidate, set by ``trial_rows`` and recorded by
    ``run_method`` as the trial's ``trial_roles`` row. None only for a ``Ran`` built by hand,
    which records no role.
    """

    trial: store.TrialRow
    row: DevRow
    moments: store.MomentsRow | None = None
    funding: store.FundingRow | None = None
    role: str | None = None
```
**File:** `engine/src/seer_engine/lab/runner.py:578` (`trial_rows` docstring: append a paragraph after the `schedule` paragraph, before the closing `"""`)
**Code:**
```
    **A control arm is never eligible** (random-twin-yardstick R3). ``control_shape.role_of``
    reads each candidate's role from its rationale -- the reader the hard gate's D18 uses at
    ``lab promote`` -- and an arm registered to be beaten gets ``store.CONTROL_LABEL`` after the
    luck label, so its ``eligible`` is False whatever its numbers. That one line is the whole of
    the role-aware status: ``run_method``'s ``dev-eligible``/``rejected`` rule reads
    ``trial.eligible`` and needs no second rule. The role travels on ``Ran.role`` so
    ``run_method`` records it beside the trial (``store.RoleRow``), which is what lets
    ``store.verdict`` say the same thing later without opening the method file.
```
**File:** `engine/src/seer_engine/lab/runner.py:610-612` and `:655`
**Change:** after the luck label, add the control label; pass the role on.
**Code:** (replaces lines 610-612)
```python
        failed = list(row.failed)
        if dsr is None or dsr < store.DSR_MIN:
            failed.append(store.DSR_LABEL)
        # R3: an arm registered to be beaten never makes its method eligible, whatever its
        # numbers. After the luck label, the order `store.verdict` reads it back in.
        role = control_shape.role_of(c)
        if role == control_shape.ROLE_CONTROL:
            failed.append(store.CONTROL_LABEL)
```
(replaces line 655)
```python
        out.append(Ran(trial=trial, row=row, moments=mom, funding=fund, role=role))
```
**Impact:** a new control arm's `trials.failed` ends with `not a control arm` and `eligible` is 0. `test_lab_runner.py`'s candidates (`rationale="test"`) read as treatment and are unaffected.

### Step 11: `run_method` records the roles; the status line comment
**File:** `engine/src/seer_engine/lab/runner.py:752`
**Change:** comment only; the expression is unchanged.
**Code:**
```python
        # Role-aware without a rule of its own: `trial_rows` already failed every control arm with
        # `store.CONTROL_LABEL`, so only a non-control arm can make this method dev-eligible.
        status = "dev-eligible" if any(r.trial.eligible for r in ran) else "rejected"
```
**File:** `engine/src/seer_engine/lab/runner.py:807` (directly after the `store.insert_provenance(conn, [...])` call closes, before the `# The fold verdict of this batch, computed HERE` comment)
**Code:**
```python
        # Each arm's role, read from the candidate this run just simulated, in this same
        # transaction (random-twin-yardstick R3). `store.verdict` reads it to refuse a control arm
        # without importing the method file. Both paths record it -- a first run and `--amend` --
        # and a batch refused above leaves none, because nothing has been written yet.
        store.insert_roles(conn, [
            store.RoleRow(trial_n=n, role=r.role, source="recorded", measured=r.trial.run_at)
            for n, r in zip(ns, ran, strict=True)
            if r.role is not None
        ])
```
**File:** `engine/src/seer_engine/lab/runner.py:22-26` (module docstring, item 4)
**Code:** (replaces item 4)
```
4. Eligible = the five P7a D8 conditions and ``store.DSR_LABEL`` (DSR >= 0.90 since 2026-10-07;
   LAB_LUCK_GATE_PLAN.md Decision D1), and never for an arm whose rationale reads as a control
   (``store.CONTROL_LABEL``; random-twin-yardstick R3). Insert the trials and each arm's role
   (``store.trial_roles``), set the method's ``source_sha`` and status (``dev-eligible`` when any
   trial is eligible -- so only a non-control arm can make it -- else ``rejected``), all in one
   transaction. ``store.verdict`` re-reads a recorded trial against the same threshold, N and
   role, so a verdict is comparable across time rather than frozen at its run date.
```
**Impact:** every new `lab run` and `lab run --amend` writes one `trial_roles` row per trial. R3.1 holds with no change to the status expression.

### Step 12: `lab reevaluate --demote` and `lab roles` — parser and docstring
**File:** `engine/src/seer_engine/commands/lab.py:27-31` (module docstring, the `lab reevaluate` entry)
**Code:** (replaces the five-line `lab reevaluate [M0022 ...]` entry; the lines after it are unchanged)
```
    lab reevaluate [M0022 ...]      re-judge recorded dev trials against the bars in force now
                                    (store.DSR_MIN, store.DSR_POLICY, tuning.MAX_DRAWDOWN) and
                                    move a method they unblock from rejected to dev-eligible.
                                    Reads only: no store, no backtest, no trial row, no look. A
                                    trial whose DSR cannot be evaluated at the gate's N fails the
                                    luck test and is reported as such
    lab reevaluate --demote [M0022 ...]
                                    the way back: move a dev-eligible method none of whose dev
                                    trials reads eligible today -- a recorded control arm never
                                    does -- to rejected, with a dated note in its analysis. No
                                    trial row is touched. Default: every dev-eligible method
    lab roles [M0022 ...] [--backfill]
                                    each recorded dev arm's role (control, dose, idea,
                                    treatment) and where it came from; --backfill records the
                                    role of every dev arm that has none and whose method file
                                    can still be read, once, and skips the rest. No trial row,
                                    no status change: N and the looks do not move
```
**File:** `engine/src/seer_engine/commands/lab.py:323-331` (the `reevaluate` parser) — replaced, and the `roles` parser added directly after it (before `s = sub.add_parser("test", ...)`)
**Code:** (no `%` in any `help=`: argparse %-interpolates them)
```python
    s = sub.add_parser(
        "reevaluate",
        help="re-judge recorded dev trials against the current luck bar; moves a method "
             "rejected -> dev-eligible when the bars in force today clear every condition, or "
             "with --demote dev-eligible -> rejected when no non-control arm does",
    )
    s.add_argument(
        "method", nargs="*", metavar="M0022",
        help="methods to re-evaluate (default: every method that reads rejected, or with "
             "--demote every method that reads dev-eligible)",
    )
    s.add_argument(
        "--demote", action="store_true",
        help="take the one edge back instead: move a dev-eligible method none of whose dev "
             "trials reads eligible at the bars in force today -- a recorded control arm never "
             "does -- to rejected, and append a dated note to its analysis. No trial row is "
             "written. Run `lab roles --backfill` first, or an unrecorded control still counts",
    )

    s = sub.add_parser(
        "roles",
        help="each recorded dev arm's role and where it came from; --backfill records the missing",
        description=(
            "An arm's role -- control, dose, idea or treatment -- is its author's one-line "
            "rationale, read by control_shape.role_of. `lab run` records it beside every trial it "
            "writes, and the lab's verdict reads that record: an arm registered to be beaten "
            "never makes its method dev-eligible and is never the arm `lab promote` would "
            "choose. Trials recorded before roles were kept have none. Without --backfill this "
            "writes nothing: with method ids it lists every dev arm of those methods, its "
            "recorded role and source, or what its method file reads now; without ids it counts "
            "the recorded roles by role and source and the dev arms that still have none. "
            "--backfill reads every method file once and records, in one transaction, the role "
            "of every dev arm that has none and whose method file declares an arm with its id. "
            "An arm it cannot read -- the P7a seed rows, which predate method files, or an id "
            "the file no longer declares -- is skipped and counted, never guessed. A second run "
            "records nothing. No trial row is touched, so the lab's N and the test-window looks "
            "cannot move."
        ),
    )
    s.add_argument(
        "method", nargs="*", metavar="M0022",
        help="methods to list arm by arm (default: a summary over every dev arm; with "
             "--backfill, every method)",
    )
    s.add_argument(
        "--backfill", action="store_true",
        help="record the role of every dev arm that has none, read from its method file as it "
             "is now. Arms whose file or arm cannot be read are skipped and counted. Idempotent: "
             "an arm that has a role is never written twice",
    )
```
**Impact:** `lab --help`, `lab reevaluate --help`, `lab roles --help` format (J6 runs them).

### Step 13: `lab reevaluate --demote` and `lab roles` — handlers
**File:** `engine/src/seer_engine/commands/lab.py:2233-2296` (`_reevaluate`, full replacement: one docstring paragraph and the first two lines of the body are new; the rest is verbatim)
**Code:**
```python
def _reevaluate(conn, args) -> int:
    """`lab reevaluate [M0022 ...]`: re-judge recorded dev trials against the current luck bar
    and move anything the moved bars were blocking to dev-eligible.

    No research store is loaded, no backtest runs, no trial row is inserted: this reads the dev
    trials the lab already has, re-decides every condition for each, and takes at most the one
    edge `rejected -> dev-eligible`. The test window is not touched and the look count it prints
    is the one it found.

    Every trial with a recorded DSR is re-judged **at the gate's current N**, either exactly from
    `trial_moments` or by re-evaluating the recorded DSR there (`store.dsr_at`). A trial whose
    DSR cannot be evaluated at all -- the 54 P7a seed rows, whose `dsr` is NULL by construction --
    fails the luck test, exactly as a new trial with no computable DSR does, and is counted and
    named per method rather than passed over in silence.

    Neither the threshold nor the policy is a flag: the write path always uses `store.DSR_MIN`
    and `store.DSR_POLICY`, so the gate cannot be loosened per invocation. To see what another
    policy would say without changing anything, use the read-only `lab luck`.

    The pairing is deliberate and the names are deliberately not neighbours: **`lab reevaluate`
    writes** (it can move a method across `rejected -> dev-eligible`) and **`lab luck` reads**
    (it prints the gate's state and its sensitivity to N, and touches nothing).

    `--demote` takes the other edge instead, `dev-eligible -> rejected`, and is a separate act
    (`_demote`): plain `lab reevaluate` never demotes anything (plan Decision D6).

    Like every other `lab` subcommand, the global `--dry-run` is ignored. The whole sweep is one
    transaction: either every method it unblocks moves, or none does.
    """
    if getattr(args, "demote", False):
        return _demote(conn, args)
    store.begin_immediate(conn)
    with conn:
        results = store.reevaluate(conn, args.method or None)
    if not results:
        print("nothing to re-evaluate: no method reads rejected")
        return 0
    g = results[0].gate
    print(f"luck bar: {store.DSR_LABEL}   N policy: {g.policy}, N = {g.n}   "
          f"({store.dev_trial_count(conn)} dev trial rows on the books)")
    print()
    moved = 0
    for r in results:
        if r.moved:
            moved += 1
            print(f"  {r.method_id}: {r.status_before} -> {r.status_after}  "
                  f"({', '.join(r.unblocked)})")
        elif r.dev_trials == 0:
            print(f"  {r.method_id}: no dev trial (dropped before running); unchanged")
        elif r.derived == 0:
            print(f"  {r.method_id}: none of its {r.dev_trials} dev trial(s) has an evaluable "
                  f"DSR (the P7a seed recorded none), so each fails the luck test and the "
                  f"verdict is unchanged ({r.status_before})")
        else:
            extra = (
                "" if r.unjudgeable == 0
                else f" ({r.unjudgeable} have no recorded DSR and so fail the luck test)"
            )
            print(f"  {r.method_id}: re-judged {r.derived} of {r.dev_trials} dev trial(s) at "
                  f"N = {r.gate.n} against {store.DSR_LABEL}{extra}; still {r.status_before}")
    print()
    print(f"{moved} method(s) moved rejected -> dev-eligible; "
          f"test-window looks used: {store.test_looks(conn)}")
    if moved:
        # `export-json`, not `stage`: `lab stage` also `git add`s, and the swarm shares one
        # worktree, so this phase stages its own path allowlist by hand (Decision D10).
        print("Re-export the web snapshot with "
              "`python -m seer_engine lab export-json`, and commit it with lab/lab.sqlite.")
    return 0
```
**File:** `engine/src/seer_engine/commands/lab.py:2297` (directly after `_reevaluate`, before `def _test_plan`)
**Code:**
```python
def _demote(conn, args) -> int:
    """`lab reevaluate --demote [M0022 ...]`: the one edge back, dev-eligible -> rejected.

    `store.demote_method` decides, one method at a time, inside one transaction for the whole
    sweep: a method moves only when it reads dev-eligible and none of its dev trials is eligible
    under `store.verdict` at the gate in force now. Nothing is loaded, nothing is run and no trial
    row is written, so N and the test-window looks are what they were.

    A control arm counts as a control only once its role is recorded (`trial_roles`), so a sweep
    run before `lab roles --backfill` demotes too little, never too much. The number of dev arms
    in the swept methods that have no recorded role is printed so that order is visible.
    """
    store.begin_immediate(conn)
    with conn:
        results = store.demote(conn, args.method or None)
        unroled = store.unroled_dev_trials(conn, [r.method_id for r in results])
    if not results:
        print("nothing to demote: no method reads dev-eligible")
        return 0
    g = results[0].gate
    print(f"luck bar: {store.DSR_LABEL}   N policy: {g.policy}, N = {g.n}   "
          f"drawdown screen: {tuning.DEV_MAX_DRAWDOWN:.0%}   a recorded control arm never counts")
    print()
    moved = 0
    for r in results:
        if r.moved:
            moved += 1
            print(f"  {r.method_id}: {r.status_before} -> {r.status_after}  (no dev trial reads "
                  f"eligible today; {r.controls} of {r.dev_trials} recorded as control arms)")
        elif r.status_before != "dev-eligible":
            print(f"  {r.method_id}: reads {r.status_before}; only a dev-eligible method is "
                  f"demoted, unchanged")
        elif r.dev_trials == 0:
            print(f"  {r.method_id}: no dev trial to judge it on; unchanged")
        else:
            print(f"  {r.method_id}: still dev-eligible ({', '.join(r.eligible_now)})")
    if unroled:
        print()
        print(f"{len(unroled)} dev arm(s) of these methods have no recorded role, so a control "
              f"arm among them still counts as eligible here. Run `lab roles --backfill`, then "
              f"`lab reevaluate --demote` again.")
    print()
    print(f"{moved} method(s) moved dev-eligible -> rejected; "
          f"test-window looks used: {store.test_looks(conn)}")
    if moved:
        print("Re-export the web snapshot with "
              "`python -m seer_engine lab export-json`, and commit it with lab/lab.sqlite.")
    return 0


def _roles_cmd(conn, args) -> int:
    """`lab roles [M0022 ...] [--backfill]`: each recorded dev arm's role, and the backfill.

    An arm's role -- control, dose, idea or treatment -- is its author's one-line rationale, read
    by `control_shape.role_of`. `lab run` records it beside every trial it writes (`trial_roles`,
    source `recorded`), and `store.verdict` reads that record to refuse a control arm. Trials
    recorded before the table existed have none, and this command is how they get one.

    Without `--backfill` it writes nothing. With method ids it lists every dev arm of those
    methods: its recorded role and source, or, for an arm with none, what its method file reads
    now. Without ids it prints the recorded roles counted by role and source, and how many dev
    arms still have none.

    The method files are read once, through `_roles` -- the reader `lab twins` and `lab status`
    already use -- and *before* the write lock, because `discover()` imports every method module
    and a parallel `lab run` must not wait on that. `--backfill` then asks again, under the lock,
    which dev arms have no role (a parallel run may have recorded some), and writes one
    `source='backfill'` row for each whose method file declares an arm with its id, in one
    transaction. An arm it cannot read -- the P7a seed rows, which predate method files, or an id
    the file no longer declares -- is skipped and counted, never guessed. A second run writes
    nothing: an arm that has a role is never offered again. No `trials` row is touched, so N and
    the test-window looks do not move.
    """
    wanted = [str(m) for m in args.method]
    for mid in wanted:
        if store.get_method(conn, mid) is None:
            raise store.LabError(f"no method {mid}")
    scope = wanted or None
    pending = store.unroled_dev_trials(conn, scope)
    read = _roles(sorted({str(t["method_id"]) for t in pending}))

    def key(t) -> tuple[str, str]:
        return str(t["method_id"]), str(t["candidate_id"])

    if args.backfill:
        store.begin_immediate(conn)
        with conn:
            pending = store.unroled_dev_trials(conn, scope)
            stamp = store.now_iso()
            rows = [
                store.RoleRow(
                    trial_n=int(t["n"]), role=read[key(t)], source="backfill", measured=stamp
                )
                for t in pending
                if key(t) in read
            ]
            store.insert_roles(conn, rows)
        unread = sorted({str(t["method_id"]) for t in pending if key(t) not in read})
        named = ", ".join(unread[:10]) + (
            f" and {len(unread) - 10} more" if len(unread) > 10 else ""
        )
        print(f"recorded {len(rows)} role(s) (source backfill); skipped "
              f"{len(pending) - len(rows)} dev arm(s) whose method file or arm cannot be read"
              + (f" (in {named})" if unread else ""))
        for role, count in sorted(Counter(r.role for r in rows).items()):
            print(f"  {role:<10} {count}")
        return 0

    if wanted:
        for mid in wanted:
            print(mid)
            for t in conn.execute(
                "SELECT t.n, t.candidate_id, r.role, r.source FROM trials t "
                "LEFT JOIN trial_roles r ON r.trial_n = t.n "
                "WHERE t.method_id = ? AND t.window = 'dev' ORDER BY t.n",
                (mid,),
            ):
                cid = str(t["candidate_id"])
                if t["role"] is not None:
                    print(f"  {cid:<32} {t['role']:<10} {t['source']}")
                    continue
                now = read.get((mid, cid))
                said = (
                    "no method file declares this arm" if now is None
                    else f"its method file reads {now}; `lab roles --backfill` records it"
                )
                print(f"  {cid:<32} {'-':<10} not recorded ({said})")
        return 0

    print(f"dev arms: {store.dev_trial_count(conn)}")
    for role, source, count in conn.execute(
        "SELECT r.role, r.source, count(*) FROM trial_roles r JOIN trials t ON t.n = r.trial_n "
        "WHERE t.window = 'dev' GROUP BY r.role, r.source ORDER BY r.role, r.source"
    ):
        print(f"  {role:<10} {source:<9} {count}")
    readable = sum(1 for t in pending if key(t) in read)
    print(f"  no role recorded: {len(pending)} ({readable} readable now, which "
          f"`lab roles --backfill` records; {len(pending) - readable} cannot be read)")
    return 0
```
**File:** `engine/src/seer_engine/commands/lab.py:4205` (`_HANDLERS`, directly after `"reevaluate": _reevaluate,`)
**Code:**
```python
    "roles": _roles_cmd,
```
**Impact:** `Counter` and `tuning` are already imported at module scope (`commands/lab.py:206`, `:211`). `_roles` (line 2890) is resolved at call time. `lab roles` and `lab reevaluate --demote` are not in `verify.sh`'s `LAB_DENY`, so the harness can drive them against its private copy.

### Step 14: Tests
**File:** `engine/tests/test_lab_roles.py` (new)
**Code:**
```python
"""Arm roles in the record (random-twin-yardstick phase 1, R3).

An arm registered to be beaten -- a placebo, a paired baseline, a mirror -- never makes its
method ``dev-eligible``. This file proves the four halves of that: ``lab run`` records each arm's
role and lets only a non-control arm decide the status (R3.1); ``store.verdict`` refuses a
recorded control and ``best_dev_eligible`` therefore never chooses one (R3.2); ``lab reevaluate
--demote`` moves a stale ``dev-eligible`` method back to ``rejected`` without touching a trial
(R3.3); and ``lab roles --backfill`` records the role of every readable recorded arm, once
(R3.4). Plus plan invariant 5: a database with no role row reads exactly as it did.

Every test builds its own temp lab. Nothing here opens the committed ``lab/lab.sqlite``.
"""

from __future__ import annotations

import argparse
import dataclasses
import sqlite3
import types
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine.backtest import dev as dev_module
from seer_engine.backtest.dev import Candidate
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import control_shape, runner, store
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
R_IDEA = "The idea: the twenty strongest names in the pool, equal slots, nothing timed"
R_CONTROL = "Control: the same book with the brake taken out, nothing else changed"

# `_lab` records exactly N dev rows, and every one carries n_trials_at_run=N, so judged at
# Gate(N) the derived DSR is the recorded one (``recover_dsr``'s identity) and an eligibility
# assertion means what it says.
N = 5
G = store.Gate(n=N, policy="all-trials")
STAMP = "2026-11-13T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _clean_gate_cache():
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


@pytest.fixture()
def all_trials(monkeypatch):
    """For the paths that resolve the gate themselves (``demote_method``, the CLI): judge `_lab`
    by its row count, the policy its rows were stamped under, so ``gate(conn).n == N``."""
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


# ---- a hand-built lab ------------------------------------------------------------------------


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="r", allocator_id="a", window="dev", start="2000-01-03", end="2015-10-16",
        store_fingerprint="fp", git_sha="abc", run_at=STAMP,
        total_return=1.0, cagr=0.1, max_drawdown=0.12, profit_factor=1.5, trades=200,
        sharpe=0.94, exposure=0.9, turnover=1.0, worst_year=2008, worst_year_return=-0.2,
        spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.8, failed="", eligible=True,
        dsr=0.9156, n_trials_at_run=N, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


# A 55% fall, outside the 50% dev screen: an owner-condition miss whatever the role.
DD_MISS = dict(max_drawdown=0.55, sharpe=1.46, mar=0.1,
               failed=dev_module.FAILURE_LABELS[1], eligible=False)

ROLES = {"M0001-A": "idea", "M0001-CTRL": "control", "M0002-A": "idea",
         "M0002-CTRL": "control", "M0003-A": "treatment"}


def _lab(conn) -> None:
    """Three methods, five dev trials, no role recorded yet.

    - M0001 (dev-eligible): its idea misses the drawdown screen; its control clears every
      condition -- the stale shape R3.3 exists for.
    - M0002 (dev-eligible): idea and control both clear every condition; the control out-MARs it.
    - M0003 (rejected): one arm, a drawdown miss.
    """
    for mid, path in (("M0001", ("registered", "dev-eligible")),
                      ("M0002", ("registered", "dev-eligible")),
                      ("M0003", ("registered", "rejected"))):
        with conn:
            store.add_method(conn, id=mid, name=f"name {mid}", family="fam",
                             source_kind="knowledge", hypothesis="h")
            for s in path:
                store.update_method(conn, mid, status=s)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="d1a", **DD_MISS),
            _trial(candidate_id="M0001-CTRL", config_digest="d1c", mar=0.95),
            _trial(method_id="M0002", candidate_id="M0002-A", config_digest="d2a"),
            _trial(method_id="M0002", candidate_id="M0002-CTRL", config_digest="d2c", mar=0.95),
            _trial(method_id="M0003", candidate_id="M0003-A", config_digest="d3a", **DD_MISS),
        ])


def _n(conn, cid: str) -> int:
    return int(conn.execute(
        "SELECT n FROM trials WHERE candidate_id = ? AND window = 'dev'", (cid,)
    ).fetchone()[0])


def _row(conn, cid: str):
    return conn.execute(
        "SELECT * FROM trials WHERE candidate_id = ? AND window = 'dev'", (cid,)
    ).fetchone()


def _record_roles(conn, roles=ROLES, source="recorded") -> None:
    with conn:
        store.insert_roles(conn, [
            store.RoleRow(trial_n=_n(conn, cid), role=role, source=source, measured=STAMP)
            for cid, role in roles.items()
        ])


def _trials_table(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")]


def _lab_cli(db: Path, *argv: str) -> int:
    """The real parser and the real handler, as `python -m seer_engine lab ...` runs them."""
    p = argparse.ArgumentParser(prog="lab")
    lab_cmd.add_arguments(p)
    return lab_cmd.run(p.parse_args(["--db", str(db), *argv]))


@dataclass(frozen=True)
class _Arm:
    """An arm as `control_shape` reads one: an id and its author's one line."""

    id: str
    rationale: str


def _declare(monkeypatch, **by_method: list) -> None:
    """Make `method.discover()` see these arms and no others (the seam `_roles` reads through)."""
    from seer_engine.lab import method as method_mod

    files = {
        mid: (types.SimpleNamespace(id=mid, all_candidates=lambda arms=arms: tuple(arms)),
              Path(f"{mid}.py"))
        for mid, arms in by_method.items()
    }
    monkeypatch.setattr(method_mod, "discover", lambda: files)


# ---- the record ------------------------------------------------------------------------------


def test_the_store_names_the_roles_control_shape_answers():
    assert store.TRIAL_ROLES == control_shape.ROLES
    assert store.CONTROL_ROLE == control_shape.ROLE_CONTROL
    assert not store.is_luck_label(store.CONTROL_LABEL)


def test_trial_roles_arrives_on_connect_without_a_schema_version(conn):
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'trial_roles'"
    ).fetchone() is not None
    assert store.SCHEMA_VERSION == "8" and store.schema_version(conn) == "8"


def test_a_role_row_is_checked_once_and_is_append_only(conn):
    _lab(conn)
    n = _n(conn, "M0001-CTRL")
    with pytest.raises(store.LabError, match="insert_trials assigned"):
        store.insert_roles(conn, [store.RoleRow(0, "control", "recorded", STAMP)])
    with pytest.raises(store.LabError, match="not a role"):
        store.insert_roles(conn, [store.RoleRow(n, "placebo", "recorded", STAMP)])
    with pytest.raises(store.LabError, match="source 'guess'"):
        store.insert_roles(conn, [store.RoleRow(n, "control", "guess", STAMP)])
    with conn:
        store.insert_roles(conn, [store.RoleRow(n, "control", "recorded", STAMP)])
    assert store.role_of_trial(conn, n) == "control"
    with pytest.raises(store.LabError, match="already has a recorded role"):
        store.insert_roles(conn, [store.RoleRow(n, "idea", "backfill", STAMP)])
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with conn:
            conn.execute("UPDATE trial_roles SET role = 'idea' WHERE trial_n = ?", (n,))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with conn:
            conn.execute("DELETE FROM trial_roles WHERE trial_n = ?", (n,))
    assert store.role_of_trial(conn, n) == "control"


def test_role_of_trial_is_none_without_a_row_or_without_the_table(conn, tmp_path):
    _lab(conn)
    assert store.role_of_trial(conn, _n(conn, "M0001-A")) is None
    old = sqlite3.connect(tmp_path / "old.sqlite")
    try:
        old.execute("CREATE TABLE trials (n INTEGER PRIMARY KEY)")
        assert store.role_of_trial(old, 1) is None
    finally:
        old.close()


# ---- R3.2: a recorded control is never eligible and never chosen ------------------------------


def test_a_recorded_control_reads_not_eligible_after_every_other_label(conn):
    _lab(conn)
    _record_roles(conn)
    v = store.verdict(conn, _row(conn, "M0002-CTRL"), at=G)
    # Its numbers clear every condition, its luck test included: the role is the only reason.
    assert v.derived is True and v.dsr == pytest.approx(0.9156, abs=1e-12)
    assert v.failed == (store.CONTROL_LABEL,) and v.eligible is False
    assert store.verdict(conn, _row(conn, "M0002-A"), at=G).eligible is True
    # A control that also misses the luck test: the role label still comes last.
    with conn:
        store.insert_trials(conn, [_trial(method_id="M0002", candidate_id="M0002-PLC",
                                          config_digest="d2p", dsr=0.5, mar=0.2)])
        store.insert_roles(conn, [store.RoleRow(_n(conn, "M0002-PLC"), "control", "recorded",
                                                STAMP)])
    assert store.verdict(conn, _row(conn, "M0002-PLC"), at=G).failed == (
        store.DSR_LABEL, store.CONTROL_LABEL,
    )


def test_best_dev_eligible_never_chooses_a_recorded_control(conn):
    _lab(conn)
    # Before any role is recorded the control out-MARs the idea and is chosen, exactly as today.
    assert store.best_dev_eligible(conn, "M0002", at=G)["candidate_id"] == "M0002-CTRL"
    assert store.best_dev_eligible(conn, "M0001", at=G)["candidate_id"] == "M0001-CTRL"
    _record_roles(conn)
    assert store.best_dev_eligible(conn, "M0002", at=G)["candidate_id"] == "M0002-A"
    assert store.best_dev_eligible(conn, "M0001", at=G) is None


def test_with_no_role_row_every_verdict_reads_as_it_did(conn):
    """Plan invariant 5: no role row, or no table at all, and nothing moves."""
    _lab(conn)
    expected = {"M0001-A": False, "M0001-CTRL": True, "M0002-A": True, "M0002-CTRL": True,
                "M0003-A": False}

    def read() -> dict[str, store.Verdict]:
        return {cid: store.verdict(conn, _row(conn, cid), at=G) for cid in expected}

    no_rows = read()
    assert {cid: v.eligible for cid, v in no_rows.items()} == expected
    assert all(store.CONTROL_LABEL not in v.failed for v in no_rows.values())
    with conn:
        conn.execute("DROP TABLE trial_roles")
    assert read() == no_rows


# ---- R3.3: the demotion door -----------------------------------------------------------------


def test_demote_moves_a_method_whose_only_eligible_arm_is_a_control(conn, all_trials):
    _lab(conn)
    _record_roles(conn)
    before = _trials_table(conn)
    n_before, looks_before = store.gate(conn).n, store.test_looks(conn)
    with conn:
        r = store.demote_method(conn, "M0001")
    assert r.moved is True
    assert (r.status_before, r.status_after) == ("dev-eligible", "rejected")
    assert r.eligible_now == () and r.controls == 1 and r.dev_trials == 2
    m = store.get_method(conn, "M0001")
    assert m["status"] == "rejected"
    assert store.DEMOTION_MARKER in m["analysis"]
    assert f"### {date.today().isoformat()}" in m["analysis"]
    assert "comparison arm" in m["analysis"]
    assert _trials_table(conn) == before
    assert store.gate(conn).n == n_before and store.test_looks(conn) == looks_before


def test_demote_leaves_a_method_that_has_an_eligible_non_control_arm(conn, all_trials):
    _lab(conn)
    _record_roles(conn)
    analysis = store.get_method(conn, "M0002")["analysis"]
    with conn:
        r = store.demote_method(conn, "M0002")
    assert r.moved is False and r.eligible_now == ("M0002-A",)
    assert store.get_method(conn, "M0002")["status"] == "dev-eligible"
    assert store.get_method(conn, "M0002")["analysis"] == analysis


def test_demote_moves_only_from_dev_eligible_and_only_once(conn, all_trials):
    _lab(conn)
    _record_roles(conn)
    with conn:
        assert store.demote_method(conn, "M0003").moved is False      # already rejected
        assert store.demote_method(conn, "M0001").moved is True
    after = store.get_method(conn, "M0001")["analysis"]
    with conn:
        again = store.demote_method(conn, "M0001")
    assert again.moved is False and again.status_before == "rejected"
    assert store.get_method(conn, "M0001")["analysis"] == after
    with conn:
        store.add_method(conn, id="M0004", name="n", family="f", source_kind="knowledge",
                         hypothesis="h")
        store.update_method(conn, "M0004", status="registered")
        store.update_method(conn, "M0004", status="dev-eligible")
        assert store.demote_method(conn, "M0004").moved is False      # no dev trial to judge
    assert store.get_method(conn, "M0004")["status"] == "dev-eligible"
    with pytest.raises(store.LabError, match="no method M0999"):
        store.demote_method(conn, "M0999")


def test_an_unrecorded_control_still_counts_so_demotion_can_only_under_reach(conn, all_trials):
    _lab(conn)                                                         # no role rows
    with conn:
        r = store.demote_method(conn, "M0001")
    assert r.moved is False and r.eligible_now == ("M0001-CTRL",)
    assert store.get_method(conn, "M0001")["status"] == "dev-eligible"


def test_demote_sweeps_every_dev_eligible_method(conn, all_trials):
    _lab(conn)
    _record_roles(conn)
    with conn:
        results = store.demote(conn)
    assert [r.method_id for r in results] == ["M0001", "M0002"]
    assert [r.method_id for r in results if r.moved] == ["M0001"]


def test_plain_reevaluate_takes_a_demoted_method_back_when_its_arm_clears_again(
    conn, all_trials, monkeypatch
):
    """The door is reversible (Decision D10). M0002-A was recorded eligible (1), so without the
    demotion marker ``reevaluate_method`` would never look at it again."""
    _lab(conn)
    _record_roles(conn)
    monkeypatch.setattr(store, "DSR_MIN", 0.95)      # M0002-A's 0.9156 now misses the luck bar
    with conn:
        assert store.demote_method(conn, "M0002").moved is True
    assert _row(conn, "M0002-A")["eligible"] == 1
    monkeypatch.setattr(store, "DSR_MIN", 0.90)      # the bar moves back
    with conn:
        r = store.reevaluate_method(conn, "M0002")
    assert r.moved is True and r.unblocked == ("M0002-A",)   # never the control
    m = store.get_method(conn, "M0002")
    assert m["status"] == "dev-eligible"
    assert store.DEMOTION_MARKER in m["analysis"] and store.REEVALUATION_MARKER in m["analysis"]
    # A rejected method that was never demoted keeps the narrow rule: M0003's one arm misses the
    # drawdown screen and stays rejected.
    with conn:
        assert store.reevaluate_method(conn, "M0003").moved is False


def test_the_edge_back_is_a_transition_and_nothing_else_opened(conn):
    assert ("dev-eligible", "rejected") in store.TRANSITIONS
    assert conn.execute(
        "SELECT 1 FROM transitions WHERE src = 'dev-eligible' AND dst = 'rejected'"
    ).fetchone() is not None
    _lab(conn)
    with conn:
        store.update_method(conn, "M0002", status="rejected")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0003", status="promoted")


def test_reevaluate_demote_moves_the_stale_method_and_plain_reevaluate_does_not(
    tmp_path, all_trials, capsys
):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab(c)
    _record_roles(c)
    before = _trials_table(c)
    c.close()

    assert _lab_cli(db, "reevaluate") == 0
    c = store.connect(db)
    assert store.get_method(c, "M0001")["status"] == "dev-eligible"   # plain never demotes
    c.close()
    capsys.readouterr()

    assert _lab_cli(db, "reevaluate", "--demote") == 0
    out = capsys.readouterr().out
    assert "M0001: dev-eligible -> rejected" in out
    assert "M0002: still dev-eligible (M0002-A)" in out
    assert "1 method(s) moved dev-eligible -> rejected" in out
    c = store.connect(db)
    assert store.get_method(c, "M0001")["status"] == "rejected"
    assert store.get_method(c, "M0002")["status"] == "dev-eligible"
    assert _trials_table(c) == before
    c.close()

    assert _lab_cli(db, "reevaluate", "--demote") == 0
    assert "0 method(s) moved dev-eligible -> rejected" in capsys.readouterr().out
    assert _lab_cli(db, "reevaluate", "--demote", "M0999") == 2


# ---- R3.4: the backfill ----------------------------------------------------------------------


def test_backfill_records_every_readable_arm_once_and_skips_the_rest(tmp_path, monkeypatch,
                                                                     all_trials, capsys):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    seed(c)                                       # the P7a seed trials: no method file, ever
    _lab(c)
    with c:
        # A test-window look of M0001-A: never given a role.
        store.insert_trials(c, [_trial(candidate_id="M0001-A", config_digest="d1a",
                                       window="test")])
        # A role the run itself recorded: never offered to the backfill.
        store.insert_roles(c, [store.RoleRow(_n(c, "M0002-A"), "idea", "recorded", STAMP)])
    before = _trials_table(c)
    dev_before, n_before = store.dev_trial_count(c), store.gate(c).n
    c.close()
    # M0001's file declares both arms; M0002's only its idea; M0003 has no file at all.
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-CTRL", R_CONTROL)],
             M0002=[_Arm("M0002-A", R_IDEA)])

    assert _lab_cli(db, "roles", "--backfill") == 0
    out = capsys.readouterr().out
    skipped = dev_before - 3
    assert "recorded 2 role(s)" in out and f"skipped {skipped} dev arm(s)" in out
    c = store.connect(db)
    got = {r["candidate_id"]: (r["window"], r["role"], r["source"]) for r in c.execute(
        "SELECT t.candidate_id, t.window, r.role, r.source FROM trial_roles r "
        "JOIN trials t ON t.n = r.trial_n"
    )}
    assert got == {
        "M0001-A": ("dev", "idea", "backfill"),
        "M0001-CTRL": ("dev", "control", "backfill"),
        "M0002-A": ("dev", "idea", "recorded"),
    }
    assert _trials_table(c) == before
    assert store.dev_trial_count(c) == dev_before and store.gate(c).n == n_before
    c.close()

    assert _lab_cli(db, "roles", "--backfill") == 0                    # idempotent
    assert "recorded 0 role(s)" in capsys.readouterr().out
    c = store.connect(db)
    assert c.execute("SELECT count(*) FROM trial_roles").fetchone()[0] == 3
    c.close()

    assert _lab_cli(db, "roles") == 0
    assert f"no role recorded: {skipped} (0 readable now" in capsys.readouterr().out


def test_roles_lists_a_method_arm_by_arm_and_refuses_an_unknown_one(tmp_path, monkeypatch,
                                                                    capsys):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab(c)
    _record_roles(c, {"M0001-CTRL": "control"})
    c.close()
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA), _Arm("M0001-CTRL", R_CONTROL)])
    assert _lab_cli(db, "roles", "M0999") == 2
    assert _lab_cli(db, "roles", "M0001") == 0
    lines = {line.split()[0]: line for line in capsys.readouterr().out.splitlines()
             if line.startswith("  ")}
    assert "control" in lines["M0001-CTRL"] and "recorded" in lines["M0001-CTRL"]
    assert "not recorded" in lines["M0001-A"] and "reads idea" in lines["M0001-A"]


def test_the_new_help_text_formats(capsys):
    p = argparse.ArgumentParser(prog="lab")
    lab_cmd.add_arguments(p)
    for argv in (["roles", "--help"], ["reevaluate", "--help"]):
        with pytest.raises(SystemExit) as e:
            p.parse_args(argv)
        assert e.value.code == 0
    assert "--backfill" in capsys.readouterr().out


# ---- R3.1: `lab run` records roles and only a non-control arm decides the status -------------


def _cand(cid: str, rules=MONTHLY_HOLD, n: int = 50, rationale: str = "test") -> Candidate:
    return Candidate(
        id=cid, family=cid.split("-")[0], rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale=rationale, added=date(2026, 10, 4), owner_inputs=(),
    )


IDEA = _cand("M0001-A")
CONTROL = _cand("M0001-B", rules=DAILY_SWITCH, n=20, rationale=R_CONTROL)


def _method(cands=(IDEA, CONTROL), amendments=()) -> Method:
    return Method(id="M0001", name="SMA test", family="trend", source_kind="knowledge",
                  source_ref="", hypothesis="h", expected_failure="f",
                  candidates=tuple(cands), amendments=tuple(amendments))


@pytest.fixture()
def seeded(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


def _force(monkeypatch, *, eligible: set[str]) -> None:
    """Make the D8 screen say what the test needs, and nothing else.

    The smoke market cannot be steered into clearing D8, so each simulated row is rewritten on its
    way out of ``dev.run_registry``: an arm in ``eligible`` clears all five conditions, every other
    arm misses one (the trade count). ``DSR_MIN`` drops below any DSR, so the luck test passes for
    every arm. What is left to decide eligibility is exactly the rule under test -- the role.
    """
    real = dev_module.run_registry
    trades = next(label for label in dev_module.FAILURE_LABELS if "trades" in label)

    def run_registry(*a, on_result=None, **k):
        def hook(i, result, row):
            if row.candidate.id in eligible:
                row = dataclasses.replace(row, failed=(), eligible=True, beats_spy=True)
            else:
                row = dataclasses.replace(row, failed=(trades,), eligible=False, beats_spy=True)
            on_result(i, result, row)

        return real(*a, on_result=hook, **k)

    monkeypatch.setattr(dev_module, "run_registry", run_registry)
    monkeypatch.setattr(store, "DSR_MIN", -1.0)


def _role_row(conn, n: int):
    return conn.execute("SELECT * FROM trial_roles WHERE trial_n = ?", (n,)).fetchone()


def test_a_method_whose_only_eligible_arm_is_its_control_is_rejected(seeded, data, monkeypatch):
    assert control_shape.role_of(CONTROL) == control_shape.ROLE_CONTROL      # the premise
    assert control_shape.role_of(IDEA) != control_shape.ROLE_CONTROL
    _force(monkeypatch, eligible={"M0001-B"})
    done = runner.run_method(seeded, _method(), HERE, data, git_sha="x", require_commit=False)
    by_id = {r.trial.candidate_id: r for r in done.ran}
    assert by_id["M0001-B"].trial.failed == store.CONTROL_LABEL
    assert by_id["M0001-B"].trial.eligible is False
    assert store.get_method(seeded, "M0001")["status"] == "rejected"
    rows = {r["candidate_id"]: r for r in store.trials_of(seeded, "M0001")}
    assert rows["M0001-B"]["eligible"] == 0 and rows["M0001-B"]["failed"] == store.CONTROL_LABEL
    for cid, role in (("M0001-A", control_shape.role_of(IDEA)), ("M0001-B", "control")):
        got = _role_row(seeded, rows[cid]["n"])
        assert (got["role"], got["source"], got["measured"]) == (role, "recorded",
                                                                 rows[cid]["run_at"])
    # ...and the verdict reads the record back the same way.
    assert store.verdict(seeded, rows["M0001-B"]).failed[-1] == store.CONTROL_LABEL


def test_a_method_with_an_eligible_non_control_arm_is_dev_eligible(seeded, data, monkeypatch):
    _force(monkeypatch, eligible={"M0001-A", "M0001-B"})
    done = runner.run_method(seeded, _method(), HERE, data, git_sha="x", require_commit=False)
    by_id = {r.trial.candidate_id: r for r in done.ran}
    assert by_id["M0001-A"].trial.eligible is True and by_id["M0001-A"].trial.failed == ""
    assert by_id["M0001-B"].trial.eligible is False
    assert store.get_method(seeded, "M0001")["status"] == "dev-eligible"


def test_an_amendment_records_its_arms_roles_and_moves_no_status(seeded, data, monkeypatch):
    _force(monkeypatch, eligible={"M0001-A", "M0001-C"})
    runner.run_method(seeded, _method(), HERE, data, git_sha="x", require_commit=False)
    amended = _method(amendments=(Amendment(
        added=date(2026, 10, 12), why="a later control", hypothesis="the idea beats its foil",
        expected_failure="the foil keeps up",
        candidates=(_cand("M0001-C", n=75, rationale=R_CONTROL),),
    ),))
    runner.run_method(seeded, amended, HERE, data, git_sha="y", require_commit=False, amend=True)
    c = store.trials_of(seeded, "M0001")[-1]
    assert c["candidate_id"] == "M0001-C" and c["failed"] == store.CONTROL_LABEL
    got = _role_row(seeded, c["n"])
    assert (got["role"], got["source"]) == ("control", "recorded")
    assert store.get_method(seeded, "M0001")["status"] == "dev-eligible"   # unchanged
```
**Impact:** new file; no fixture touches the committed database.

### Step 15: Feature map
**File:** `.claude/skills/verify-seer/features/lab-cli.md:5-6`
**Change:** replace the `Read:` and `Write` bullets (lines 5 and 6) with:
```
- Read: `lab status` (near-miss and closest-to-eligible rows end in `[role; = first-recorded twin]` tags), `lab show MNNNN`, `lab next-id`, `lab luck`, `lab twins MNNNN|CANDIDATE ...` (which arms are a book the lab already recorded under another id), `lab roles [MNNNN ...]` (each dev arm's recorded role -- control, dose, idea, treatment -- and its source, or what its method file reads now; no ids: counts by role and source) and the report-only commands (`costs`, `timing`, `kin`, ...).
- Write (to the run's private copy only): `lab idea` (prints the id on stdout and the five closest methods by shared words on stderr, then the control arms those methods already hold, by first recording ("Controls those methods already hold ...")), `note`, `insight`, `block`/`unblock`, `drop`, `run` (a committed method on the dev window; prints a `Book twins:` block after the mirror pairs; records each arm's role, and a control arm is recorded `not a control arm` and never makes the method dev-eligible), `roles --backfill` (one role row per dev arm that has none and whose method file can be read; a second run records 0), `reevaluate --demote` (moves a dev-eligible method with no eligible non-control arm today to rejected, with a dated note in its analysis; no trial row changes).
```
**File:** `.claude/skills/verify-seer/features/lab-cli.md` (in the `Driving it with verify.sh` block, directly before the `$V lab RUN test M0007` line)
**Code:**
```sh
$V lab RUN roles --backfill   # "recorded R role(s) (source backfill); skipped K dev arm(s) whose method file or arm cannot be read (in H-..., ...)"; exit 0
$V labsql RUN "select role, source, count(*) from trial_roles group by 1, 2"   # the R rows, source backfill
$V lab RUN roles --backfill   # "recorded 0 role(s)": idempotent
$V lab RUN roles M0202        # one line per dev arm: candidate, role, source (its placebo arms read control)
$V lab RUN reevaluate --demote   # "M method(s) moved dev-eligible -> rejected"; trials unchanged (labsql count before = after)
```
**File:** `.claude/skills/verify-seer/features/lab-cli.md` (`## Gotchas`, new last bullet)
**Code:**
```
- Run `lab roles --backfill` before `lab reevaluate --demote`. A control arm counts as a control only once its role is recorded, so a demotion before the backfill under-reaches (it never over-reaches); the command prints how many arms of the swept methods still have no role.
```
**Impact:** docs only.

## Principles applied

- Laziness protocol: the role-aware status is one label appended in `runner.trial_rows`; the `run_method` status expression (runner.py:752) and `best_dev_eligible` are not edited, because both already read eligibility.
- Laziness protocol: the backfill reuses `commands.lab._roles` (the method-file role reader `lab twins` and `lab status` already use), and demotion returns the existing `Reevaluation` with two defaulted fields instead of a new result type.
- Make illegal states unrepresentable: `trial_roles.trial_n` is the primary key (one role per arm), `role` and `source` are CHECKed against `TRIAL_ROLES`/`ROLE_SOURCES`, and triggers refuse UPDATE/DELETE, so a second or edited role cannot be stored.
- Boundary discipline: roles are validated once, in `insert_roles`, with a readable refusal; `verdict` trusts the stored value and only compares it to `CONTROL_ROLE`.
- Encode lessons in structure: `store.TRIAL_ROLES` is a literal copy of `control_shape.ROLES` (store imports nothing from the lab at module scope), so a test pins the two equal instead of a comment asking people to keep them in sync.
- Test behavior, not implementation: the tests assert the observable record (status, `trials.failed`, `trial_roles` rows, verdicts, CLI exit codes and output), never that `role_of` was called.
- Prove it works: Proof drives `lab roles --backfill` and `lab reevaluate --demote` against the verify-seer copy of the real lab, and reads the result back from the database.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/random-twin-yardstick && (test -x engine/.venv/bin/python || (python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]')) && engine/.venv/bin/ruff check engine`
(The worktree has no `engine/.venv` today; main's venv would test the wrong tree.)

**Tests:** `cd /home/miftah/.worktrees/seer/random-twin-yardstick && engine/.venv/bin/pytest engine/tests/test_lab_*.py engine/tests/test_paper_roster.py engine/tests/test_promote_command.py`
then the whole suite, which needs Postgres for the DB tests: `docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests`

**Proof:** the real lab CLI against the verify-seer private copy of the committed lab, read back with `labsql`, plus the pytest journeys for what a verify run cannot drive (`lab run` needs a committed method file).
- Harness: `.claude/skills/verify-seer` (`V=.claude/skills/verify-seer/scripts/verify.sh`, run from the worktree root)
- Feature-map entries: `.claude/skills/verify-seer/features/lab-cli.md`
- Journeys (J3, J4 and J5 run in this order in one RUN from `$V up --no-web --empty`; note the printed `RUN=`):
  - **J1** · traces R3.1 — `engine/.venv/bin/pytest -n0 engine/tests/test_lab_roles.py -k "only_eligible_arm_is_its_control or eligible_non_control_arm_is_dev_eligible or amendment_records_its_arms_roles"` → passes when it reports `3 passed`: a run whose only forced-eligible arm is its `Control:` arm records the method `rejected` with that arm's `failed` = `not a control arm`; with a treatment also eligible it records `dev-eligible`; an `--amend` control arm gets a `recorded` role row and the status does not move.
  - **J2** · traces R3.2 — `engine/.venv/bin/pytest -n0 engine/tests/test_lab_roles.py -k "recorded_control_reads_not_eligible or never_chooses_a_recorded_control or no_role_row_every_verdict"` → passes when it reports `3 passed`: a recorded control whose numbers clear every condition reads `failed == ("not a control arm",)`; `best_dev_eligible` returns the control before roles are recorded and the idea (or None) after; with no role row, and with the table dropped, every verdict equals the pre-role verdict field for field.
  - **J3** · traces R3.4 — `$V labsql RUN "select count(*), max(n), sum(eligible), sum(length(failed)) from trials"` (T0), then `$V lab RUN roles --backfill`, then `$V labsql RUN "select count(*) from trial_roles"` (R), `$V labsql RUN "select count(*) from trials t where t.window='dev' and not exists (select 1 from trial_roles r where r.trial_n=t.n)"` (K), `$V labsql RUN "select count(*) from trials where window='dev'"` (D), `$V labsql RUN "select count(*) from trial_roles r join trials t on t.n=r.trial_n where t.method_id like 'H-%' or t.window='test'"`, then `$V lab RUN roles --backfill` again and `$V labsql RUN "select count(*) from trial_roles"` and the T0 query again → passes when the first backfill exits 0 printing `recorded R role(s)` and `skipped K dev arm(s)` with R > 0 and R + K = D, the H-%/test query prints 0, the second backfill exits 0 printing `recorded 0 role(s)` with the role count still R, and the T0 row is byte-identical before and after.
  - **J4** · traces R3.3 — after J3 in the same RUN: `$V labsql RUN "select count(*) from methods where status='dev-eligible'"` (E0), `$V lab RUN reevaluate --demote`, `$V labsql RUN "select count(*) from methods where status='dev-eligible'"` (E1), `$V labsql RUN "select count(*) from methods where status='rejected' and analysis like '%Demoted under the %'"` (Dm), `$V labsql RUN "select substr(analysis, instr(analysis, 'Demoted under the') - 40, 120) from methods where analysis like '%Demoted under the %' limit 1"`, the J3 T0 query, then `$V lab RUN reevaluate --demote` again → passes when the first demote exits 0 and prints `M method(s) moved dev-eligible -> rejected` with M ≥ 1, E0 − E1 = M = Dm, the excerpt shows `### <today's date>` and `# Re-evaluation` before the marker, the T0 row equals J3's, and the second demote prints `0 method(s) moved dev-eligible -> rejected`.
  - **J5** · traces R3.2 — after J3 in the same RUN, read-only against the run's copy: `SEER_ENV_FILE=$HOME/.local/state/seer-verify/$RUN/engine.env PYTHONPATH=$PWD/engine/src engine/.venv/bin/python - "$HOME/.local/state/seer-verify/$RUN/lab.sqlite" <<'PY'` with body `import sys, sqlite3` / `from seer_engine.lab import store` / `c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True); c.row_factory = sqlite3.Row` / `g = store.gate(c)` / `ctl = c.execute("select t.* from trials t join trial_roles r on r.trial_n = t.n where r.role = 'control' and t.window = 'dev'").fetchall()` / `bad = [t["candidate_id"] for t in ctl if store.verdict(c, t, at=g).eligible or store.verdict(c, t, at=g).failed[-1] != store.CONTROL_LABEL]` / `mids = [r[0] for r in c.execute("select distinct method_id from trials where window = 'dev'")]` / `chosen = [store.best_dev_eligible(c, m, at=g) for m in mids]` / `picked = [r["candidate_id"] for r in chosen if r is not None and store.role_of_trial(c, r["n"]) == "control"]` / `print(len(ctl), "controls;", len(bad), "read eligible;", len(picked), "chosen")` / `PY` → passes when it prints `<k> controls; 0 read eligible; 0 chosen` with k > 0.
  - **J6** · traces R3.3, R3.4 — `engine/.venv/bin/pytest -n0 engine/tests/test_lab_roles.py -k "demote or backfill or roles_lists or help_text or edge_back or role_row or arrives_on_connect or names_the_roles or role_of_trial"` → passes when every selected test passes: `--demote` moves only the stale method and leaves every trial row and the gate's N unchanged, plain `lab reevaluate` never demotes but does take a demoted method back once its recorded-eligible arm clears again (`test_plain_reevaluate_takes_a_demoted_method_back_when_its_arm_clears_again`), `--backfill` writes exactly the readable arms (never a seed, test-window or already-recorded arm) and a second run writes 0, and the new help strings format.
- Neighbor check: `engine/.venv/bin/pytest engine/tests/test_lab_gate_policy.py engine/tests/test_lab_hardgate.py engine/tests/test_lab_status.py engine/tests/test_lab_snapshot.py engine/tests/test_lab_amendments.py engine/tests/test_lab_repeat_refusal.py engine/tests/test_lab_runner.py engine/tests/test_paper_roster.py` all pass, and `$V lab RUN status` (after J4) exits 0 with its `Promotion path` block; then `sha1sum lab/lab.sqlite; git status --porcelain lab web/data` shows the committed lab hash unchanged and nothing listed (restore with `git checkout -- lab/lab.sqlite` if a local command touched it).
- Cost: none. No paid drive, no `--net`, no `--llm`. `lab roles --backfill` imports every method module once (seconds); J5 walks every dev method once.

**Exit criteria:** a method whose only eligible arm is a control records `rejected` (J1); a recorded control reads not eligible and `best_dev_eligible` never returns one, on fixtures and on the real lab copy (J2, J5); `lab reevaluate --demote` moves the stale methods, appends the dated note and changes no trial row, and plain `lab reevaluate` can take a demoted method back (J4, J6); `lab roles --backfill` records every readable dev arm once and skips the rest without failing (J3, J6); with no role row every verdict is unchanged (J2); `ruff check engine` is clean and every lab test file passes.

**Commit (explicit paths only; never `git commit -a`; `lab/lab.sqlite` is never staged — invariant 2):**
```bash
cd /home/miftah/.worktrees/seer/random-twin-yardstick
git checkout -- lab/lab.sqlite 2>/dev/null; git status --porcelain lab web/data   # must print nothing
git add engine/src/seer_engine/lab/store.py engine/src/seer_engine/lab/runner.py \
        engine/src/seer_engine/commands/lab.py engine/tests/test_lab_roles.py \
        .claude/skills/verify-seer/features/lab-cli.md
git commit -m "lab: arm roles in the record, role-aware status and the demotion door (random-twin-yardstick phase 1)"
```

## Handoffs

- **Phase 5 (web, snapshot):** `store.verdict` now appends `not a control arm` to a recorded control's `failedNow`, and `lab run` writes it into a new control's `failed`. The web pin `web/lib/sera/lab.test.ts:56-70` ("writes every failure label in a shape conditionOk can read") will fail as soon as `web/data/lab.json` carries the label — after the backfill, or after any `lab run` of a control arm on this code. Phase 5 owns teaching `web/lib/sera/derive.ts` (`FAILURE_LABEL` / `conditionOk`) the label and showing a control as a comparison book; it should also add `store.CONTROL_LABEL` to `LIVE_LABELS` in `engine/tests/test_lab_snapshot.py:133` (its fixture lab has no role row today, so phase 1 does not need it) and publish `role` from `store.role_of_trial`.
- **Phase 3 (yardstick record):** `yardstick_due` can exclude controls through `store.role_of_trial(conn, n) == store.CONTROL_ROLE`, or simply through `verdict(...).failed`, which for a recorded control already holds `CONTROL_LABEL` and so is never "empty or only `YARDSTICK_LABEL`". Placement for its additions is under **Interface Contract**.
- **Phase 4 (yardstick as a condition):** append `YARDSTICK_LABEL` after `CONTROL_LABEL` in both `store.verdict` and `runner.trial_rows`; measure only non-control arms (`Ran.role` / `control_shape.role_of(c)` is already computed in `trial_rows`). Design §10 and the backfill runbook should state the R3 rule and the order `lab roles --backfill` → `lab yardstick --pending` → `lab reevaluate --demote`. The explore and Sera skill text should say that a method whose only eligible arm is a control now records `rejected`. `hardgate.py`'s D18 docstring still says `best_dev_eligible` has "no role filter"; a test pins that phrase, so it is left as written.
- **Resolved at reconcile (Decision D10):** the index's Rollback says "plain `lab reevaluate` moves back any that clear today's bars". `reevaluate_method` used to unblock only trials whose *recorded* `eligible` is 0, so that sentence was false for a method demoted on a recorded-eligible arm. Step 9b makes it true; the Rollback sentence stays.
- **Not done, read-only reports:** `lab luck`'s `_eligible_at` (commands/lab.py:1235) and `lab status`'s near-miss rows do not consult roles. They print, they decide nothing; left as they are.

## Rollback

`git revert` this phase's commit(s). The reverted code still opens any database this phase touched: `trial_roles` stays (append-only, unread) because it was created with `IF NOT EXISTS` and no schema version moved, and the extra `transitions` row stays (no old code path uses it). Methods already moved by `--demote` stay `rejected` after a revert, and the reverted `reevaluate_method` no longer reconsiders their recorded-eligible arms; while this phase is live, plain `lab reevaluate` takes such a method back once one of its arms clears every condition again (Step 9b). Never commit `lab/lab.sqlite` from this phase; if a local command touched it, `git checkout -- lab/lab.sqlite`.
