> Adopted from `/home/miftah/seer/.workflows/orchestration/random-twin-yardstick/PLAN.md` phase 3. Source: `.workflows/plan/random-twin-yardstick/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: The yardstick record and `lab yardstick`

**Plan set:** `RANDOM_TWIN_YARDSTICK_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-125454-Y7RT_code_analyzer.md`
**Satisfies:** R1. Each recorded stock-picking arm gets a random-book yardstick of its own setup, measured once per store, cached, and counted against nothing.
**Criteria:** R1.1, R1.2, R1.5, R1.6
**Depends on:** Phase 1 (`store.role_of_trial`, `store.RoleRow`, `store.insert_roles`, `CONTROL_LABEL` in `verdict`), Phase 2 (`lab/yardstick.py`: `RULE_ID`, `DRAWS`, `STATUS_*`, `Measurement`, `Unreproducible`, `measure`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab` (`store.py`) and `engine/src/seer_engine/commands` (`lab.py`)

---

## Goal

After this phase the lab can measure any recorded dev arm against `yardstick.DRAWS` random twins of itself with `lab yardstick`. It records the result as one append-only `trial_yardstick` row per (trial, rule, store), and it never inserts a trial, moves N or spends a look. If an arm recorded on the loaded store no longer reproduces its trade count and return, the command refuses with exit 2 and writes nothing for it. The store also gains the readers later phases build on: `yardstick_of`, `yardstick_clears`, `yardstick_due`, the 0.90 bar and its label. Nothing in this phase changes what `store.verdict` says. Phase 4 does that.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `store.YARDSTICK_MIN_PERCENTILE = 0.90` (`lab/store.py`, directly after phase 1's `CONTROL_LABEL = "not a control arm"`, which phase 1 places after `is_luck_label`)
- `store.YARDSTICK_LABEL = "beats 90% of random twins"`, derived as `f"beats {YARDSTICK_MIN_PERCENTILE:.0%} of random twins"`
- `store.YARDSTICK_STATUSES = ("measured", "not-applicable", "unmatched")`. This is a literal mirror of `yardstick.STATUS_MEASURED / STATUS_NOT_APPLICABLE / STATUS_UNMATCHED`, and a test pins the two equal.
- `store._YARDSTICK_TABLE`, `store._YARDSTICK_TRIGGERS`, and their three statements in `_SCHEMA`. They create the table `trial_yardstick(trial_n, rule_id, store_fingerprint, status, draws, arm_rate, beaten, percentile, rates_json, trade_ratio, turnover_ratio, reproduced, git_sha, measured, PRIMARY KEY (trial_n, rule_id, store_fingerprint))`, append-only by trigger.
- `store.YardstickRow` (frozen dataclass, the 14 columns in table order), `YardstickRow.from_measurement(m, *, trial_n, rule_id, store_fingerprint, checked, git_sha, measured)`, and `store.YARDSTICK_COLUMNS`
- `store.has_yardstick(conn, trial_n, rule_id, store_fingerprint) -> bool` (False when the table is absent)
- `store.yardstick_of(conn, trial_n) -> sqlite3.Row | None` (the latest row by `measured`, then by rowid; None when the table or the row is absent)
- `store.insert_yardstick(conn, row) -> bool` (False, writing nothing, when the key exists. The caller holds the transaction.)
- `store.yardstick_clears(row: Mapping[str, Any] | sqlite3.Row | None) -> bool | None` — accepts **any** mapping addressable by column name: a `sqlite3.Row` from `yardstick_of`, a plain `dict`, and `dataclasses.asdict(YardstickRow)` (phase 4 calls it on all three; one clearing rule)
- `store.yardstick_due(conn, trial, *, at=None) -> bool`
- `commands/lab.py`: the `lab yardstick` subparser, `_positive_count`, `_YardstickArm`, `_yardstick_trials`, `_yardstick_arms`, `_yardstick_control_refusal`, `_yardstick_status`, `_yardstick_line`, `_yardstick_footer`, `_yardstick`, the `"yardstick"` entry in `_HANDLERS`, and a module-level `import json`
- `engine/tests/test_lab_yardstick_record.py` (new)
**Signature changes:** none
**Requires (from earlier phases):**
- Phase 1: `store.role_of_trial(conn, trial_n) -> str | None` (None when the table or the row is absent), `store.RoleRow(trial_n, role, source, measured)` and `store.insert_roles(conn, rows)`. Only the test file uses the last two. `store.verdict` appends `CONTROL_LABEL` for a recorded control. `yardstick_due` does not rely on that, but it stays correct with it.
- Phase 2: `yardstick.RULE_ID: str`, `yardstick.DRAWS: int`, `yardstick.STATUS_MEASURED / STATUS_NOT_APPLICABLE / STATUS_UNMATCHED` equal to the three strings above, `yardstick.Unreproducible(Exception)` built from a message string, and `yardstick.Measurement` with keyword fields `status, draws, arm_rate, beaten, percentile, rates, trade_ratio, turnover_ratio, reproduced`. **Phase 2's `Measurement.__post_init__` is the source of truth for its shape (Decision D11)**, and every check in this phase mirrors it:
  - `rates` is a tuple of float, sorted ascending, twins with no rate left out (never None inside)
  - a `not-applicable` measurement has `draws == 0`, `beaten == 0`, `percentile is None`, `rates == ()`, `trade_ratio is None`, `turnover_ratio is None`; `arm_rate` may be a number or None
  - a `measured` **or** `unmatched` one has `draws >= 1`, `0 <= beaten <= draws` and `percentile == beaten / draws` (never None), and `len(rates) <= draws`
  - `reproduced` is None when `expect` is None, and None for a bracket (`DESIGN_V0`) arm, which reads `not-applicable` and is never re-run, so `expect` cannot fire for it (Decision D12)
  - `yardstick.measure(market, dividends, spy_dividends, candidate, *, initial_idr, contributions, draws=DRAWS, jobs=1, expect=None)` returns the same `Measurement` for any `jobs` and raises `Unreproducible` when `expect` is given and the re-run differs.
**Leaves alone (owned by others):** `store.verdict`, `store.best_dev_eligible`, `store.published_verdict`, the snapshot functions and `SNAPSHOT_VERSION` (phases 4 and 5); `runner.run_method` and `runner.trial_rows` (phases 1 and 4); `lab/hardgate.py` (phase 4); `lab/yardstick.py` (phase 2: called, never edited); the `trial_roles` table and `lab roles` / `lab reevaluate --demote` (phase 1); `web/` (phase 5); `lab/lab.sqlite` and `web/data/lab.json` (never committed by this phase).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py:57` | modify | module docstring: one bullet for `trial_yardstick` directly after phase 1's `trial_roles` bullet |
| `engine/src/seer_engine/lab/store.py:189` | modify | `YARDSTICK_MIN_PERCENTILE`, `YARDSTICK_LABEL` directly after phase 1's `CONTROL_LABEL = "not a control arm"` |
| `engine/src/seer_engine/lab/store.py:512` | modify | `YARDSTICK_STATUSES`, `_YARDSTICK_TABLE`, `_YARDSTICK_TRIGGERS` directly after phase 1's `_ROLES_TRIGGERS` tuple |
| `engine/src/seer_engine/lab/store.py:666` | modify | the three statements in `_SCHEMA` directly after phase 1's `{_ROLES_TRIGGERS[1]};` paragraph, before `CREATE TRIGGER IF NOT EXISTS trials_no_update` |
| `engine/src/seer_engine/lab/store.py:2731` | modify | the `trial yardstick` section directly after phase 1's `trial roles` section (ends with `unroled_dev_trials`), before `# ---- ideas_seen` |
| `engine/src/seer_engine/commands/lab.py:162` | modify | module docstring: the `lab yardstick` entry directly after the `lab twins` entry (phase 1 edits a different entry, `lab reevaluate`, at :27) |
| `engine/src/seer_engine/commands/lab.py:191-214` | modify | `import json` among the stdlib imports |
| `engine/src/seer_engine/commands/lab.py:245` | modify | `_positive_count` after `_positive_n` (phase 4 reuses it for `lab run --jobs`) |
| `engine/src/seer_engine/commands/lab.py:925` | modify | the `yardstick` subparser directly after the `twins` subparser (phase 1's `roles` subparser sits elsewhere, after `reevaluate`) |
| `engine/src/seer_engine/commands/lab.py:3653` | modify | the yardstick handler and its helpers directly after `_twins`, before `_exposure` (phase 1's handlers sit elsewhere, after `_reevaluate`) |
| `engine/src/seer_engine/commands/lab.py:4216` | modify | `"yardstick": _yardstick,` in `_HANDLERS` directly after `"twins": _twins,` (phase 1's `"roles"` sits after `"reevaluate"`, ten lines up) |
| `engine/tests/test_lab_yardstick_record.py` | create | the table, the helpers and the command |
| `.claude/skills/verify-seer/features/lab-cli.md` | modify | `lab yardstick` sub-feature, drive lines, gotcha |

Line numbers are today's (HEAD `f83fb237`). Phase 1 lands first and inserts above several of them. Each step names the anchor text **as phase 1 leaves the file** rather than relying on the number.

## Implementation Steps

### Step 1: Name the bar and its label
**File:** `engine/src/seer_engine/lab/store.py:189`. Phase 1 placed its role constants directly after the `is_luck_label` function; the last of them is the line `CONTROL_LABEL = "not a control arm"`. The insertion goes directly after that line, before the `# The N the luck test deflates by` comment.
**Change:** add the bar and the label. The label is derived from the bar, the same way `DSR_LABEL` is derived from `DSR_MIN`.
**Code:**
```python


# The random-twin yardstick's bar (RANDOM_TWIN_YARDSTICK_PLAN.md Decision D9): an arm clears its
# yardstick when it out-earned at least this share of its random twins -- books that replay the
# arm's own decisions with every picked name swapped for a randomly drawn index member of similar
# trading size (lab/yardstick.py). "Roughly the top tenth of random books" in the words of the
# review the owner asked to have built. Not a CLI flag and not a policy: one number, cited, moved
# only by editing this line, exactly as DSR_MIN is.
YARDSTICK_MIN_PERCENTILE = 0.90

# The yardstick's failure label, derived from the bar rather than retyped, for the reason
# DSR_LABEL is derived from DSR_MIN: the label and the threshold can never disagree. Any screen
# that reads the yardstick writes this string, and ``yardstick_due`` recognises it.
YARDSTICK_LABEL = f"beats {YARDSTICK_MIN_PERCENTILE:.0%} of random twins"
```
**Impact:** two new module constants. Nothing reads them yet except the code added below.

### Step 2: Define the side table
**File:** `engine/src/seer_engine/lab/store.py:512`. Phase 1 placed `_ROLES_TABLE` and `_ROLES_TRIGGERS` directly after the `_FOLDS_TRIGGERS` tuple. The insertion goes directly after the closing `)` of `_ROLES_TRIGGERS` (whose second entry raises `'trial_roles are append-only: a role row is never deleted'`), before the `#: The backfill's capital rule` comment.
**Change:** add the status list, the table DDL and its two triggers as separate constants, following the side-table pattern (one definition shared by `_SCHEMA` and by any test that strips it back out). The DDL and the trigger messages must not contain the words `supersedes`, `doc_key`, `trial_moments`, `method_folds`, `method_amendments` or `trial_provenance`, because `test_lab_snapshot.py`'s old-schema strippers assert those words are absent from the stripped `_SCHEMA`.
**Code:**
```python

# The random-twin yardstick of one dev trial, measured on one research store under one draw rule
# (RANDOM_TWIN_YARDSTICK_PLAN.md phase 3). ``lab yardstick`` writes it, and nothing it writes is
# a trial: no ``trials`` row, no change to the luck gate's N, no test-window look. That is
# requirement R1.2, and it is why this is a side table rather than a column.
#
# **The key is (trial, rule, store), and a repeat writes nothing.** ``rule_id`` is
# ``yardstick.RULE_ID`` -- the draw rule's version, so a later rule is a new measurement rather
# than a rewrite of this one -- and ``store_fingerprint`` is the research store the twins were
# simulated on, because a twin's return is a statement about those prices and no other. A second
# measurement of the same arm on the same store under the same rule would be the same number
# again, so ``insert_yardstick`` refuses it by returning False (R1.5). A third measurement on a
# rebuilt store is a new row. ``yardstick_of`` reads the newest.
#
# ``status`` is one of three words (``lab/yardstick.py`` decides which):
#
# - ``measured``        the twins ran and the arm out-earned ``beaten`` of ``draws`` of them;
#                       ``percentile`` is that share.
# - ``not-applicable``  the arm holds no picked stock (an ETF-only or cash-only book), or is a
#                       bracket (``DESIGN_V0``) arm with no book decisions to replay, so there is
#                       no name to swap and no twin was simulated: ``draws`` and ``beaten`` are 0
#                       and there is no share and no shape ratio.
# - ``unmatched``       the twins ran but did not trade like the arm -- median trade count or
#                       turnover outside 0.5x..2.0x of the arm's own -- so their returns are not a
#                       fair yardstick and the row never counts as clearing it. It still carries
#                       its draws and its share, exactly as a measured row does.
#
# ``reproduced`` says whether the arm itself was re-run and matched its recorded trade count and
# return: 1 when it was checked on the store the trial was recorded on, NULL on any other store
# (nothing to check against) and NULL for a bracket arm, which is never re-run. A 0 is never
# written -- an arm that does not reproduce is refused and records nothing (R1.6) -- but the
# column admits it so a reader never has to guess what NULL means. ``rates_json`` carries every
# twin's rate, sorted ascending as ``yardstick.Measurement.rates`` holds them, so the distribution
# is cached, not just its summary.
#
# The CHECKs mirror ``yardstick.Measurement.__post_init__`` (plan Decision D11): a not-applicable
# row has no draws, no twins beaten, no share and no ratio; a measured or unmatched row has at
# least one draw and a share.
YARDSTICK_STATUSES: tuple[str, ...] = ("measured", "not-applicable", "unmatched")

_YARDSTICK_TABLE = f"""CREATE TABLE IF NOT EXISTS trial_yardstick (
    trial_n           INTEGER NOT NULL REFERENCES trials(n),
    rule_id           TEXT NOT NULL CHECK (length(trim(rule_id)) > 0),
    store_fingerprint TEXT NOT NULL CHECK (length(trim(store_fingerprint)) > 0),
    status            TEXT NOT NULL CHECK (status IN ({_quoted(YARDSTICK_STATUSES)})),
    draws             INTEGER NOT NULL CHECK (draws >= 0),
    arm_rate          REAL,
    beaten            INTEGER NOT NULL CHECK (beaten >= 0 AND beaten <= draws),
    percentile        REAL CHECK (percentile IS NULL OR (percentile >= 0 AND percentile <= 1)),
    rates_json        TEXT NOT NULL,
    trade_ratio       REAL,
    turnover_ratio    REAL,
    reproduced        INTEGER CHECK (reproduced IS NULL OR reproduced IN (0, 1)),
    git_sha           TEXT NOT NULL CHECK (length(trim(git_sha)) > 0),
    measured          TEXT NOT NULL CHECK (length(trim(measured)) > 0),
    PRIMARY KEY (trial_n, rule_id, store_fingerprint),
    CHECK (status <> 'not-applicable' OR (draws = 0 AND beaten = 0 AND percentile IS NULL
                                          AND trade_ratio IS NULL AND turnover_ratio IS NULL)),
    CHECK (status = 'not-applicable' OR (draws >= 1 AND percentile IS NOT NULL))
)"""
_YARDSTICK_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS trial_yardstick_no_update BEFORE UPDATE ON trial_yardstick
BEGIN SELECT RAISE(ABORT, 'trial_yardstick is append-only: a yardstick row is never updated'); END""",
    """CREATE TRIGGER IF NOT EXISTS trial_yardstick_no_delete BEFORE DELETE ON trial_yardstick
BEGIN SELECT RAISE(ABORT, 'trial_yardstick is append-only: a yardstick row is never deleted'); END""",
)
```
**Impact:** constants only. They take effect in Step 3.

### Step 3: Create the table on connect
**File:** `engine/src/seer_engine/lab/store.py:666`, inside `_SCHEMA`. As phase 1 leaves it, `{_FOLDS_TRIGGERS[1]};` is followed by phase 1's three paragraphs `{_ROLES_TABLE};`, `{_ROLES_TRIGGERS[0]};`, `{_ROLES_TRIGGERS[1]};`, then `CREATE TRIGGER IF NOT EXISTS trials_no_update`. The insertion goes directly after `{_ROLES_TRIGGERS[1]};` and its blank line, before `CREATE TRIGGER IF NOT EXISTS trials_no_update`.
**Change:** add three statements. Each is followed by `;` and a blank line, the layout `test_lab_snapshot.py`'s strippers rely on. `SCHEMA_VERSION` stays `"8"` and `_migrate` is not touched: `connect` runs `_SCHEMA` on every open, so `CREATE TABLE IF NOT EXISTS` adds the table to an existing v8 database, and an older checkout never sees it.
**Code** (the lines to insert, at the indentation of the surrounding `_SCHEMA` text):
```
{_YARDSTICK_TABLE};

{_YARDSTICK_TRIGGERS[0]};

{_YARDSTICK_TRIGGERS[1]};

```
**Impact:** every `store.connect` creates `trial_yardstick` when it is missing. `connect_readonly` creates nothing, so the readers below must tolerate its absence. A parallel Sera checkout on old code opens the database unchanged (no version bump), and its own `_SCHEMA` never names the table.

### Step 4: Add the record, its readers and the due rule
**File:** `engine/src/seer_engine/lab/store.py:2731`. Phase 1 added a `# --- trial roles` section directly after `insert_folds`; it ends with `unroled_dev_trials`, whose last line is `    return conn.execute(sql + " ORDER BY t.n", params).fetchall()`. The insertion goes directly after that line, before `# --------------------------------------------------------------------------- ideas_seen`.
**Change:** add the row type, its column list, the existence check, the reader, the insert, the bar test and the due rule.
**Code:**
```python


# --------------------------------------------------------------------------- trial yardstick


@dataclass(frozen=True)
class YardstickRow:
    """One random-twin yardstick of one dev trial, on one store, under one draw rule.

    The database half of ``yardstick.Measurement``; ``from_measurement`` is the one place the
    simulator's value becomes a row, so ``lab yardstick`` and any later writer record the same
    columns the same way. See ``_YARDSTICK_TABLE`` for what each column means.

    - ``trial_n``            the dev ``trials.n`` the twins were drawn for.
    - ``rule_id``            ``yardstick.RULE_ID``: the draw rule's version.
    - ``store_fingerprint``  ``ResearchData.fingerprint`` of the store the twins ran on.
    - ``status``             one of ``YARDSTICK_STATUSES``.
    - ``draws``              how many twins were simulated (0 when not applicable).
    - ``arm_rate``           the arm's own rate on that store (money-weighted return when funded,
                             CAGR otherwise -- the rate ``make_row`` ranks on).
    - ``beaten``             how many twins the arm out-earned; ties count against the arm. 0
                             when not applicable (no twin was drawn).
    - ``percentile``         ``beaten`` as a share of the twins; None only when not applicable.
    - ``rates_json``         every twin's rate, as a JSON list, sorted ascending (the order
                             ``yardstick.Measurement.rates`` holds them in).
    - ``trade_ratio``        median twin trade count over the arm's.
    - ``turnover_ratio``     median twin turnover over the arm's.
    - ``reproduced``         True when the arm was re-run on its recording store and matched its
                             recorded trade count and return; None when there was nothing to
                             check against (another store) or nothing was re-run (a bracket arm,
                             which reads not-applicable).
    - ``git_sha``, ``measured``  the code and the moment of the measurement.
    """

    trial_n: int
    rule_id: str
    store_fingerprint: str
    status: str
    draws: int
    arm_rate: float | None
    beaten: int
    percentile: float | None
    rates_json: str
    trade_ratio: float | None
    turnover_ratio: float | None
    reproduced: bool | None
    git_sha: str
    measured: str

    @classmethod
    def from_measurement(
        cls,
        m: Any,
        *,
        trial_n: int,
        rule_id: str,
        store_fingerprint: str,
        checked: bool,
        git_sha: str,
        measured: str,
    ) -> YardstickRow:
        """The row for ``m`` (a ``yardstick.Measurement``), typed for the table.

        ``m`` is duck-typed rather than imported: this module never imports the simulator, which
        pulls in the whole book engine, because importing ``store`` is something the entire lab
        does. ``checked`` says whether ``expect`` was passed to ``measure`` -- whether the trial was
        recorded on this store -- and ``reproduced`` is NULL whenever it was not, whatever ``m``
        carries, so "not checked" can never be written as "checked and passed".

        **The one constructor of a row from a reading.** ``lab yardstick`` calls it with the
        trial's real number; ``runner.run_method`` (phase 4) calls it with ``trial_n=0`` before
        the trial is inserted and stamps the number with ``dataclasses.replace`` afterwards, as it
        does every other side row. ``insert_yardstick`` refuses the ``0`` if it ever reaches it.
        """
        return cls(
            trial_n=int(trial_n),
            rule_id=str(rule_id),
            store_fingerprint=str(store_fingerprint),
            status=str(m.status),
            draws=int(m.draws),
            arm_rate=None if m.arm_rate is None else float(m.arm_rate),
            beaten=int(m.beaten),
            percentile=None if m.percentile is None else float(m.percentile),
            rates_json=json.dumps([float(r) for r in m.rates], separators=(",", ":")),
            trade_ratio=None if m.trade_ratio is None else float(m.trade_ratio),
            turnover_ratio=None if m.turnover_ratio is None else float(m.turnover_ratio),
            reproduced=None if not checked or m.reproduced is None else bool(m.reproduced),
            git_sha=str(git_sha),
            measured=str(measured),
        )


YARDSTICK_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(YardstickRow))


def _has_yardstick_table(conn: sqlite3.Connection) -> bool:
    """Whether this database has the ``trial_yardstick`` table at all.

    ``connect`` always creates it, so a False here is a ``connect_readonly`` caller on a database
    no yardstick-aware code has opened for writing -- the snapshot sync guard reading the
    committed file is one. Every reader below answers "nothing recorded" in that case, as
    ``funding_of`` does for a database that predates ``trial_funding``.
    """
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'trial_yardstick'"
    ).fetchone() is not None


def has_yardstick(
    conn: sqlite3.Connection, trial_n: int, rule_id: str, store_fingerprint: str
) -> bool:
    """Whether trial ``trial_n`` already has a yardstick under ``rule_id`` on ``store_fingerprint``.

    The key ``insert_yardstick`` refuses on. ``lab yardstick`` asks before it simulates anything,
    so a repeat costs no backtest as well as writing no row. False when the table is absent.
    """
    if not _has_yardstick_table(conn):
        return False
    return conn.execute(
        "SELECT 1 FROM trial_yardstick WHERE trial_n = ? AND rule_id = ? AND store_fingerprint = ?",
        (int(trial_n), str(rule_id), str(store_fingerprint)),
    ).fetchone() is not None


def yardstick_of(conn: sqlite3.Connection, trial_n: int) -> sqlite3.Row | None:
    """The latest recorded yardstick of trial ``trial_n``, or None when it has none.

    "Latest" is the newest ``measured`` stamp, ties broken by insertion order: one trial can carry
    several rows -- one per store and draw rule -- and the newest is the one that describes the
    store and the rule the lab uses now. None when the table itself is absent (a
    ``connect_readonly`` caller; see ``_has_yardstick_table``), which reads the same as "never
    measured" because that is exactly what it is.
    """
    if not _has_yardstick_table(conn):
        return None
    return conn.execute(
        "SELECT * FROM trial_yardstick WHERE trial_n = ? ORDER BY measured DESC, rowid DESC LIMIT 1",
        (int(trial_n),),
    ).fetchone()


def insert_yardstick(conn: sqlite3.Connection, row: YardstickRow) -> bool:
    """Record one yardstick (the caller holds the transaction). False, writing nothing, on a repeat.

    A repeat is the same (trial, rule, store) key: the same measurement again, which the lab keeps
    once (R1.5). It is answered with False rather than an error so a sweep can be re-run after an
    interruption and skip what it already did. The caller holds ``begin_immediate``, so the check
    and the insert are one step against a parallel session.

    Refused with ``LabError``, before anything is written:

    - the pre-insert sentinel ``0`` or any trial number the lab does not hold;
    - a ``test``-window trial: the yardstick grades a selection among dev results, and a test look
      is a single pre-registered measurement with no selection in it;
    - a status outside ``YARDSTICK_STATUSES``, or a row whose shape contradicts its status (the
      same rule the table's CHECKs hold, stated as a sentence rather than a constraint name, and
      the rule ``yardstick.Measurement.__post_init__`` holds for the reading it came from).
    """
    n = int(row.trial_n)
    if n <= 0:
        raise LabError(
            f"a yardstick needs the trial number of a recorded trial, got {row.trial_n!r}"
        )
    trial = conn.execute("SELECT window FROM trials WHERE n = ?", (n,)).fetchone()
    if trial is None:
        raise LabError(f"no trial #{n}: a yardstick is recorded for a trial the lab holds")
    if str(trial[0]) != "dev":
        raise LabError(
            f"trial #{n} is a {trial[0]} look, not a dev arm: the yardstick grades a selection "
            "among dev results, and a test-window look has no selection in it"
        )
    if row.status not in YARDSTICK_STATUSES:
        raise LabError(
            f"trial #{n}: yardstick status must be one of {YARDSTICK_STATUSES}, got {row.status!r}"
        )
    if row.status == "not-applicable" and (
        row.draws != 0
        or row.beaten != 0
        or row.percentile is not None
        or row.trade_ratio is not None
        or row.turnover_ratio is not None
    ):
        raise LabError(
            f"trial #{n}: a not-applicable yardstick simulated no twin, so it has no draws, no "
            f"twins beaten, no share and no shape ratio (draws={row.draws}, "
            f"beaten={row.beaten!r}, percentile={row.percentile!r})"
        )
    if row.status != "not-applicable" and (
        row.draws < 1
        or row.percentile is None
        or row.beaten is None
        or not 0 <= row.beaten <= row.draws
    ):
        raise LabError(
            f"trial #{n}: a {row.status} yardstick needs its twins and the share the arm beat "
            f"(draws={row.draws}, beaten={row.beaten!r}, percentile={row.percentile!r})"
        )
    if has_yardstick(conn, n, row.rule_id, row.store_fingerprint):
        return False
    cols = ", ".join(f'"{c}"' for c in YARDSTICK_COLUMNS)
    marks = ", ".join("?" for _ in YARDSTICK_COLUMNS)
    values = [getattr(row, c) for c in YARDSTICK_COLUMNS]
    values[YARDSTICK_COLUMNS.index("trial_n")] = n
    values[YARDSTICK_COLUMNS.index("reproduced")] = (
        None if row.reproduced is None else int(bool(row.reproduced))
    )
    conn.execute(f"INSERT INTO trial_yardstick ({cols}) VALUES ({marks})", values)
    return True


def yardstick_clears(row: Mapping[str, Any] | sqlite3.Row | None) -> bool | None:
    """Does this yardstick reading clear the bar? None when there is no reading at all.

    ``row`` is anything addressable by column name: the ``sqlite3.Row`` ``yardstick_of``
    returns, a plain ``dict``, or ``dataclasses.asdict(YardstickRow)`` -- ``runner.trial_rows``
    judges the reading it is about to insert, and ``lab yardstick`` the row it just built, so
    every caller asks this one function and there is one clearing rule. Only ``status`` and
    ``percentile`` are read.

    - True:  ``measured`` with ``percentile >= YARDSTICK_MIN_PERCENTILE``, or ``not-applicable``
             (a book with no picked stock has no name a twin could swap, so there is nothing for
             it to beat and nothing it failed).
    - False: ``measured`` below the bar, ``unmatched`` (its twins did not trade like it, so their
             returns say nothing fair about it, and an unfair yardstick is never a pass), and any
             status this code does not know.
    - None:  ``row`` is None -- never measured. What that means is the caller's decision; this
             function never reads a missing measurement as a pass.
    """
    if row is None:
        return None
    status = str(row["status"])
    if status == "not-applicable":
        return True
    if status == "measured":
        pct = row["percentile"]
        return pct is not None and float(pct) >= YARDSTICK_MIN_PERCENTILE
    return False


def yardstick_due(
    conn: sqlite3.Connection,
    trial: Mapping[str, Any] | sqlite3.Row,
    *,
    at: Gate | None = None,
) -> bool:
    """Is ``trial`` an arm whose yardstick is worth measuring? Whether it already has one is not
    asked here -- that depends on the store, which ``has_yardstick`` answers.

    Due means all three:

    - a **dev** row (a test look is never graded against twins);
    - **not a recorded control** (``role_of_trial``): a control was registered to be beaten, and a
      yardstick for it would grade the comparison book rather than an idea;
    - its ``verdict`` fails **nothing but the yardstick itself** -- ``failed`` is empty, or holds
      only ``YARDSTICK_LABEL``. An arm that already misses SPY, the drawdown screen, the luck test
      or any other condition cannot be rescued by its twins, so measuring it would spend minutes of
      simulation to change no reading. The second half is what keeps this right once the yardstick
      is itself a condition in ``verdict``: an arm whose only failure is "no yardstick yet" or "a
      failing yardstick on another store" is exactly the arm that needs one.

    ``at`` is the gate, resolved once by a caller judging many trials.
    """
    if str(trial["window"]) != "dev":
        return False
    # control_shape.ROLE_CONTROL, spelled out: this module does not import control_shape, and
    # test_lab_yardstick_record pins the two equal.
    if role_of_trial(conn, int(trial["n"])) == "control":
        return False
    failed = verdict(conn, trial, at=at).failed
    return all(label == YARDSTICK_LABEL for label in failed)
```
**Impact:** new public API. `verdict`, `best_dev_eligible` and the snapshot are untouched, so invariant 5 holds trivially in this phase. `yardstick_due` calls phase 1's `role_of_trial` and the existing `verdict`. Both are resolved at call time, so test monkeypatches work.

### Step 5: Document the table in the module docstring
**File:** `engine/src/seer_engine/lab/store.py:57`. Phase 1 added a `trial_roles` bullet directly after the `method_folds` bullet; it ends `` ``role_of_trial`` answers None when it is absent.``. The insertion goes directly after that line, before the blank line and `Schema versions`.
**Change:** add one bullet. The schema-versions paragraph is not touched, because no version moves.
**Code:**
```
- ``trial_yardstick``: the random-twin yardstick of one dev trial -- the share of
  ``yardstick.DRAWS`` random twin books (the arm's own decisions replayed with every picked name
  swapped for an index member of similar trading size) that the arm out-earned, with every twin's
  rate kept as JSON. One row per (trial, draw rule, research store); a repeat writes nothing.
  It is a measurement of an arm already counted, never a trial: no ``trials`` row, no N, no
  look. Added by ``CREATE TABLE IF NOT EXISTS`` on connect, with no schema version of its own, so
  older checkouts sharing the database through ``SEER_LAB_DB`` open it unchanged. Triggers refuse
  every UPDATE and DELETE.
```
**Impact:** documentation only.

### Step 6: A positive-count argument type
**File:** `engine/src/seer_engine/commands/lab.py:245`, directly after `_positive_n` (which ends `    return value`), before `def add_arguments`.
**Code:**
```python


def _positive_count(text: str) -> int:
    """``--jobs J`` / ``--limit N``: a whole number of at least 1, refused by argparse otherwise,
    so a zero or a negative never reaches the simulator as "no workers" or "no arms"."""
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, got {value}")
    return value
```
**Impact:** new private helper used only by Step 7.

### Step 7: The `lab yardstick` subparser
**File:** `engine/src/seer_engine/commands/lab.py:925`. The insertion goes directly after the `twins` subparser's last line, `                   help="which window's recordings to compare (default: dev)")` (phase 1 does not touch this region; its `roles` subparser sits after `reevaluate`). It goes before `    s = sub.add_parser("idea", ...)`.
**Change:** add the subparser. No `help=` string contains a literal `%`. `description=` is not interpolated, but it carries no `%` either. `--dry-run` is declared here with `default=argparse.SUPPRESS`, so that `lab yardstick --dry-run` works and the global `python -m seer_engine --dry-run lab yardstick ...` is not reset to False by this subparser's default.
**Code:**
```python

    s = sub.add_parser(
        "yardstick",
        # No literal `%` in any `help=` string below: argparse %-interpolates every `help=`.
        help="measure recorded dev arms against random twins of themselves; no trial, no N",
        description=(
            "For each chosen dev arm, simulate the lab's fixed number of random twin books that "
            "replay the arm's own decisions -- the same dates, weights, entries and exits -- with "
            "every picked name replaced by a randomly drawn index member of similar trading size, "
            "and record the share of twins the arm out-earned (lab/yardstick.py). One row per "
            "arm, draw rule and research store goes to trial_yardstick; a repeat on the same store "
            "is skipped before anything is simulated. Nothing here is a trial: no trials row, no "
            "change to the luck gate's N and no test-window look. When the arm was recorded on "
            "the loaded store, the arm itself is re-run first and must reproduce its recorded "
            "trade count and return; one that does not is refused (exit 2) and nothing is written "
            "for it. Named methods and --pending take the due arms only: eligible at today's bars "
            "(or failing only on the yardstick), and not a control. --arm forces one arm, but "
            "never a control."
        ),
    )
    s.add_argument("method", nargs="*", metavar="M0562",
                   help="methods whose due arms to measure")
    pick = s.add_mutually_exclusive_group()
    pick.add_argument("--arm", default=None, metavar="M0562-W60-B100",
                      help="measure this one recorded dev arm whether or not it is due "
                           "(a control is still refused)")
    pick.add_argument("--pending", action="store_true",
                      help="every due arm in the lab that has no yardstick on this store yet, "
                           "oldest trial first")
    s.add_argument("--limit", type=_positive_count, default=None, metavar="N",
                   help="measure at most N arms this run (default: all of them); the rest are "
                        "left for the next run, which skips what this one recorded")
    s.add_argument("--jobs", type=_positive_count, default=1, metavar="J",
                   help="worker processes for the twins (default 1). The result is identical "
                        "for any J; only the time changes")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"dev-window research store (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE); a test-window or survivorship-check store is refused",
    )
    s.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS,
                   help="measure and print, and write nothing (the global --dry-run does the "
                        "same)")
```
**Impact:** `lab yardstick --help` formats. The positional `method` is not in the mutually exclusive group, so the handler checks that exactly one of the three selectors is given.

### Step 8: The handler and its helpers
**File:** `engine/src/seer_engine/commands/lab.py:3653`. The insertion goes directly after `_twins`, which ends with `    return 0` after the `recorded dev trials {n_before} -> ...` print (phase 1 does not touch this region; its `_demote` and `_roles_cmd` sit after `_reevaluate`). It goes before `def _exposure(conn, args) -> int:`.
**Change:** add the handler. Measurement runs outside any write lock. Each arm's row is inserted in its own short `begin_immediate` transaction, so an interrupted `--pending` sweep keeps what it finished and never holds the lab-wide lock while simulating. The capital, the funding and the method file are resolved before the store is loaded, so a refusal costs no store load. The store is not pinned with `hardgate.pin_dev_store`: a yardstick is keyed by the store it ran on, and measuring on another store is legal (recorded with `reproduced` NULL). The pin exists to keep trials comparable, and this writes no trial.
**Code:**
```python


class _YardstickArm(NamedTuple):
    """One arm ``lab yardstick`` will measure: its ``trials`` row, the ``Candidate`` its committed
    method file declares, and the capital and funding its recorded run was given -- the three
    inputs a re-run needs to be the same book (``runner.recorded_capital``)."""

    trial: object
    candidate: object
    capital: object
    contributions: object


def _yardstick_control_refusal(candidate_id: str, how: str) -> store.LabError:
    return store.LabError(
        f"{candidate_id} is a control arm ({how}): it was registered to be beaten, and a "
        f"yardstick for it would grade the comparison book rather than an idea. Nothing was "
        f"measured"
    )


def _yardstick_trials(conn, args, at: store.Gate) -> tuple[list, bool]:
    """The dev trial rows ``lab yardstick`` was asked about, and whether ``--arm`` forced them.

    Exactly one selector: method ids (their due arms), ``--arm`` (one arm, due or not), or
    ``--pending`` (every due arm in the lab, oldest trial first). Everything here reads the
    database only -- no method file, no store -- so a bad request is refused in milliseconds.
    """
    from seer_engine.lab import control_shape

    methods = list(dict.fromkeys(args.method or ()))
    arm_id = getattr(args, "arm", None)
    pending = bool(getattr(args, "pending", False))
    if sum((bool(methods), arm_id is not None, pending)) != 1:
        raise store.LabError(
            "lab yardstick: say which arms -- method ids for their due arms, --arm for one named "
            "arm, or --pending for every due arm in the lab -- and exactly one of the three"
        )
    if arm_id is not None:
        row = conn.execute(
            "SELECT * FROM trials WHERE candidate_id = ? AND window = 'dev'", (arm_id,)
        ).fetchone()
        if row is None:
            raise store.LabError(
                f"no recorded dev arm called {arm_id!r}: --arm takes a candidate id `lab run` "
                f"recorded, like M0562-W60-B100. Nothing was measured"
            )
        if store.role_of_trial(conn, int(row["n"])) == control_shape.ROLE_CONTROL:
            raise _yardstick_control_refusal(arm_id, "as recorded")
        return [row], True
    if pending:
        rows = conn.execute("SELECT * FROM trials WHERE window = 'dev' ORDER BY n").fetchall()
    else:
        rows = []
        for mid in methods:
            if store.get_method(conn, mid) is None:
                raise store.LabError(
                    f"no method {mid} in the lab: nothing to measure, and reading that as "
                    f"'nothing due' would be a false all-clear"
                )
            rows.extend(t for t in store.trials_of(conn, mid) if t["window"] == "dev")
    return [t for t in rows if store.yardstick_due(conn, t, at=at)], False


def _yardstick_arms(conn, trials, *, forced: bool) -> tuple[list[_YardstickArm], list[tuple[str, str]]]:
    """Resolve each trial to the arm a re-run needs, before any store is loaded.

    An arm with no readable method file (the P7a seed rows have none), no recorded capital, or a
    rationale that marks it a control while no role is recorded for it yet (before ``lab roles
    --backfill``) is skipped with its reason when it came from a sweep, and refused (exit 2) when
    ``--arm`` named it: a named arm the command cannot measure is an answer the caller must see.
    """
    from seer_engine.lab import control_shape, runner

    arms: list[_YardstickArm] = []
    skipped: list[tuple[str, str]] = []
    for t in trials:
        cid = str(t["candidate_id"])
        n = int(t["n"])
        try:
            _method, _path, candidate = runner.resolve_candidate(cid)
            capital = runner.recorded_capital(conn, n)
        except store.LabError as e:
            if forced:
                raise
            skipped.append((cid, str(e)))
            continue
        if (
            store.role_of_trial(conn, n) is None
            and control_shape.role_of(candidate) == control_shape.ROLE_CONTROL
        ):
            if forced:
                raise _yardstick_control_refusal(cid, "by its rationale")
            skipped.append((cid, "a control arm by its rationale (`lab roles --backfill` records it)"))
            continue
        arms.append(_YardstickArm(t, candidate, capital, runner.recorded_contributions(conn, n)))
    return arms, skipped


def _yardstick_status(row: store.YardstickRow) -> str:
    """The reading of one row in words, through ``store.yardstick_clears`` -- the one pass rule."""
    from seer_engine.lab import yardstick

    if row.status == yardstick.STATUS_NOT_APPLICABLE:
        return "not applicable: the arm holds no picked stock"
    if row.status == yardstick.STATUS_UNMATCHED:
        return "unmatched: the twins did not trade like the arm, never a pass"
    if store.yardstick_clears(dataclasses.asdict(row)):
        return f"clears the bar ({store.YARDSTICK_LABEL})"
    return f"below the bar ({store.YARDSTICK_LABEL})"


_YARDSTICK_HEAD = (
    f"{'arm':<30} {'twins':>5} {'beaten':>16} {'median twin':>11} {'arm rate':>9} "
    f"{'trades':>7}  {'draw set':<12}  status"
)


def _yardstick_line(candidate_id: str, row: store.YardstickRow, note: str) -> str:
    """One table row. ``draw set`` is the first 12 hex of sha256(rates_json): two runs of the same
    arm on the same store print the same value whatever ``--jobs`` was, which is the check a
    reader can make by eye. The one printer of a reading: ``lab run`` (phase 4) logs the readings
    it took with this same function, so a reading reads the same wherever it was taken."""
    rates = [float(r) for r in json.loads(row.rates_json) if r is not None]
    median = statistics.median(rates) if rates else None
    beaten = "-" if not row.draws else f"{row.beaten}/{row.draws} ({fmt_pct(row.percentile)})"
    ratio = "-" if row.trade_ratio is None else f"{fmt_num(row.trade_ratio)}x"
    digest = (
        hashlib.sha256(row.rates_json.encode("utf-8")).hexdigest()[:12] if row.draws else "-"
    )
    return (
        f"{candidate_id:<30} {row.draws:>5} {beaten:>16} {fmt_pct(median):>11} "
        f"{fmt_pct(row.arm_rate):>9} {ratio:>7}  {digest:<12}  {_yardstick_status(row)}{note}"
    )


def _yardstick_footer(conn, n_before: int, looks_before: int) -> None:
    print(
        f"Lab N (dev trials): {n_before} before, {store.dev_trial_count(conn)} after; luck gate "
        f"N = {store.gate(conn).n}; test-window looks used: {looks_before} before, "
        f"{store.test_looks(conn)} after. A yardstick measures an arm already counted; it is "
        f"never a trial."
    )


def _yardstick(conn, args) -> int:
    """``lab yardstick``: measure recorded dev arms against random twins of themselves.

    Requirement R1 of RANDOM_TWIN_YARDSTICK_PLAN.md. The simulation is ``yardstick.measure``
    (phase 2); this command chooses the arms, gives each one the capital and funding its recorded
    run had, and records what came back.

    **Nothing it writes is a trial (R1.2).** One ``trial_yardstick`` row per arm, draw rule and
    store, through ``store.insert_yardstick`` and nothing else: no ``trials`` row, no moments, no
    funding, no status, no journal entry. N and the looks are printed before and after.

    **A repeat writes nothing and simulates nothing (R1.5).** ``store.has_yardstick`` is asked
    before the twins run, and ``insert_yardstick`` asks again under the write lock for a parallel
    session that got there first. ``--jobs`` changes only the time: ``measure`` returns the same
    value for any J, and J is not part of the row.

    **An arm that does not reproduce is refused (R1.6).** When the trial was recorded on the
    loaded store, ``expect=(trades, total_return)`` makes ``measure`` re-run the arm first and
    raise ``yardstick.Unreproducible`` if the re-run differs: twins built from a book other than
    the recorded one would grade the wrong book. That arm records nothing, the sweep goes on to
    the next, and the command exits 2. On any other store there is nothing to check against;
    ``expect`` is None and the row's ``reproduced`` is NULL. A bracket (``DESIGN_V0``) arm is
    never re-run: ``measure`` answers ``not-applicable`` with ``reproduced`` None even when
    ``expect`` is given, so R1.6 cannot fire for it, and it is recorded ``not-applicable`` with
    ``reproduced`` NULL (plan Decision D12). There is no book to reproduce, so there is nothing
    to refuse.

    **Simulation never holds the lock.** Each arm is measured with no transaction open and
    recorded in its own short ``begin_immediate``, so a parallel ``lab run`` waits milliseconds,
    not minutes, and an interrupted sweep keeps every arm it finished.

    Unlike most ``lab`` subcommands, the global ``--dry-run`` is honoured: it measures and prints
    and writes nothing, which is what makes "the same result whatever --jobs" checkable by
    running once each way.
    """
    from seer_engine.lab import runner, yardstick

    g = store.gate(conn)
    trials, forced = _yardstick_trials(conn, args, g)
    arms, skipped = _yardstick_arms(conn, trials, forced=forced)
    dry_run = bool(getattr(args, "dry_run", False))
    jobs = int(getattr(args, "jobs", 1) or 1)
    limit = getattr(args, "limit", None)
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    for cid, why in skipped:
        print(f"skipped {cid}: {why}")
    if not arms:
        print("\nnothing to measure: no arm asked about is due -- eligible at today's bars and "
              "not a control.")
        _yardstick_footer(conn, n_before, looks_before)
        return 0

    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    try:
        purpose = research.declared_purpose(Path(args.store))
    except ValueError:
        purpose = None  # missing or unreadable: research.load_store below names the problem
    if purpose is not None:
        raise runner.survivorship_refusal("lab yardstick", purpose)
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{args.store}: {e}. `lab yardstick` measures on the dev window and nothing else, so "
            f"a test-window store is refused here"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    runner.refuse_survivorship_store(data, "lab yardstick")
    fp = str(data.fingerprint)

    measured_before = {
        int(a.trial["n"])
        for a in arms
        if store.has_yardstick(conn, int(a.trial["n"]), yardstick.RULE_ID, fp)
    }
    for a in arms:
        if int(a.trial["n"]) in measured_before:
            print(f"{a.trial['candidate_id']}: already measured on store {fp[:12]} under "
                  f"{yardstick.RULE_ID}; not measured again")
    todo = [a for a in arms if int(a.trial["n"]) not in measured_before]
    left = 0
    if limit is not None and len(todo) > limit:
        left = len(todo) - limit
        todo = todo[:limit]
    git_sha = runner.git_head(config.REPO_ROOT)

    recorded = 0
    refused: list[str] = []
    if todo:
        print(f"\nRandom-twin yardstick, rule {yardstick.RULE_ID}, {yardstick.DRAWS} twins per "
              f"arm, store {fp[:12]}, {jobs} job(s)")
        print(_YARDSTICK_HEAD)
    for a in todo:
        cid = str(a.trial["candidate_id"])
        n = int(a.trial["n"])
        checked = str(a.trial["store_fingerprint"]) == fp and a.trial["total_return"] is not None
        expect = (int(a.trial["trades"]), float(a.trial["total_return"])) if checked else None
        log.info("%s (trial #%d): measuring against %d twins", cid, n, yardstick.DRAWS)
        try:
            m = yardstick.measure(
                data.market, data.dividends, data.spy_dividends, a.candidate,
                initial_idr=a.capital, contributions=a.contributions,
                draws=yardstick.DRAWS, jobs=jobs, expect=expect,
            )
        except yardstick.Unreproducible as e:
            msg = (
                f"{cid} (trial #{n}) does not reproduce on store {fp[:12]}, the store it was "
                f"recorded on: {e}. Twins replay the arm's own decisions, so a yardstick built on "
                f"a re-run that differs from the record would grade a different book. Nothing was "
                f"written for it"
            )
            refused.append(msg)
            print(f"{cid:<30} refused: does not reproduce its recorded trades and return")
            continue
        row = store.YardstickRow.from_measurement(
            m, trial_n=n, rule_id=yardstick.RULE_ID, store_fingerprint=fp, checked=checked,
            git_sha=git_sha, measured=store.now_iso(),
        )
        if dry_run:
            note = "  (dry run: not recorded)"
        else:
            store.begin_immediate(conn)
            with conn:
                wrote = store.insert_yardstick(conn, row)
            if wrote:
                recorded += 1
                note = ""
            else:
                note = "  (already recorded by a parallel session; kept theirs)"
        print(_yardstick_line(cid, row, note))

    print()
    print(
        f"{recorded} arm(s) recorded, {len(measured_before)} already measured on this store, "
        f"{len(skipped)} skipped, {len(refused)} refused"
        + (f", {left} due arm(s) left for a later run (--limit {limit})" if left else "")
        + ("; dry run: nothing was written" if dry_run else "")
    )
    _yardstick_footer(conn, n_before, looks_before)
    if refused:
        for msg in refused:
            log.error("%s", msg)
        return 2
    return 0
```
**Impact:** `lab yardstick` exists. The names it uses that are not already imported at the top of `commands/lab.py` are `json` (Step 9) and the local imports above. `dataclasses`, `hashlib`, `statistics`, `time`, `NamedTuple`, `Path`, `os`, `config`, `research`, `dev`, `fmt_num`, `fmt_pct`, `store` and `log` are already module-level in `commands/lab.py` (lines 193-216).

### Step 9: Module-level `json` import, the handler entry and the docstring
**File:** `engine/src/seer_engine/commands/lab.py`
**Change 9a** (line 195): in the stdlib import block, add `import json` directly after `import hashlib`. The block then reads:
```python
import argparse
import dataclasses
import hashlib
import json
import logging
import math
import os
import re
import statistics
import sys
import time
```
`_run`'s own local `import json` (line 1923) stays as it is. Removing it would be a drive-by.

**Change 9b** (line 4216, one lower after phase 1): in `_HANDLERS`, directly after `"twins": _twins,` add (phase 1's `"roles": _roles_cmd,` sits after `"reevaluate": _reevaluate,`, above this):
```python
    "yardstick": _yardstick,
```

**Change 9c** (line 162): in the module docstring, directly after the `lab twins` entry, which ends `... No trial row, no status change: N\n                                    and the looks do not move`, add (phase 1's `lab roles` entry sits after its `lab reevaluate` entry near the top of the docstring, not here):
```
    lab yardstick M0562 [M0007 ...] | --arm M0562-W60-B100 | --pending [--limit N]
                  [--jobs J] [--store DIR] [--dry-run]
                                    measure recorded dev arms against random twins of
                                    themselves: books that replay the arm's own decisions with
                                    every picked name swapped for a randomly drawn index member
                                    of similar trading size (lab/yardstick.py). One
                                    trial_yardstick row per arm, draw rule and store, never a
                                    trial: N and the looks do not move, and a repeat on the same
                                    store simulates and writes nothing. Methods and --pending take
                                    the due arms (eligible today, not a control); --arm forces one.
                                    An arm recorded on the loaded store that no longer reproduces
                                    its trade count and return is refused (exit 2) and nothing is
                                    written for it
```
**Impact:** the command is reachable as `python -m seer_engine lab yardstick`.

### Step 10: Tests
**File:** `engine/tests/test_lab_yardstick_record.py` (new)
**Change:** cover the table, the helpers and the command. The simulator is replaced at its boundary (`yardstick.measure`) by a deterministic stand-in. What is under test is what the lab records and refuses, not how twins are drawn. Phase 2's `test_lab_yardstick.py` owns that.

The fixture's trials are eligible in their numbers at a gate whose N equals the dev row count, the trick `test_lab_store.py::test_best_dev_eligible_is_the_highest_mar_and_breaks_ties_on_the_trial_number` uses. The fixture sets `store.DSR_POLICY = "all-trials"` (so `store.gate(conn)` resolves N to the dev row count) and asserts each verdict, so a drift fails loudly in the fixture rather than silently in a test. `RoleRow(trial_n, role, source, measured)`, `insert_roles` and `role_of_trial` are phase 1's, used as phase 1 defines them.

**Code:**
```python
"""``trial_yardstick`` and ``lab yardstick`` (RANDOM_TWIN_YARDSTICK_PLAN.md phase 3).

The record half of the random-twin yardstick: the append-only side table, its readers, the bar,
the due rule, and the command that measures recorded dev arms and records what it found. The
simulator is phase 2's ``lab/yardstick.py`` with its own tests; here it is replaced at its boundary
by a deterministic stand-in, because what is under test is what the lab RECORDS -- one row per arm
and store, never a trial, never a look -- and what it REFUSES, not how twins are drawn.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from labkit import smoke_data, stamp_provenance

from seer_engine import cli, research
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import control_shape, runner, store, yardstick
from seer_engine.lab import method as method_mod
from seer_engine.lab.method import Method
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
FP = "fp-recorded"
OTHER_FP = "fp-rebuilt"
CONTROL_RATIONALE = "Control: hash draw of 20, seed 1, matched to M0001-A"

# (method, suffix, sharpe, max drawdown). Distinct Sharpes give the lab a trial-Sharpe variance, so
# every DSR is evaluable; C fails the 50% drawdown screen; M0001-E is a control by its rationale.
ROWS = (
    ("M0001", "A", 0.80, 0.20),
    ("M0001", "B", 0.94, 0.20),
    ("M0001", "C", 1.10, 0.55),
    ("M0001", "D", 1.20, 0.20),
    ("M0001", "E", 1.46, 0.20),
    ("M0002", "A", 0.70, 0.20),
    ("M0002", "B", 1.30, 0.20),
)
ELIGIBLE = {"M0001-A", "M0001-B", "M0001-D", "M0001-E", "M0002-A", "M0002-B"}


def _trial(mid: str, suffix: str, sharpe: float, max_drawdown: float) -> store.TrialRow:
    return store.TrialRow(
        method_id=mid, candidate_id=f"{mid}-{suffix}", config_digest=f"{mid}-{suffix}",
        config_text="t", rules_id="r", allocator_id="a", window="dev", start="2000-01-03",
        end="2015-10-16", store_fingerprint=FP, git_sha="abc",
        run_at="2026-11-01T00:00:00+00:00", total_return=1.0, cagr=0.1,
        max_drawdown=max_drawdown, profit_factor=1.5, trades=200, sharpe=sharpe, exposure=0.9,
        turnover=1.0, worst_year=2008, worst_year_return=-0.2, spy_tr_return=0.5,
        spy_tr_cagr=0.07, mar=0.5, failed="", eligible=True, dsr=0.95,
        n_trials_at_run=len(ROWS), curve_json="[]",
    )


def _cand(cid: str, n: int, rationale: str = "the idea arm") -> Candidate:
    return Candidate(
        id=cid, family=cid.split("-")[0], rules=MONTHLY_HOLD_FRAC, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale=rationale, added=date(2026, 11, 1), owner_inputs=(),
    )


def _methods() -> dict:
    out = {}
    for mid in ("M0001", "M0002"):
        cands = tuple(
            _cand(f"{m}-{s}", 10 + i, CONTROL_RATIONALE if f"{m}-{s}" == "M0001-E" else "the idea arm")
            for i, (m, s, _sr, _dd) in enumerate(ROWS)
            if m == mid
        )
        out[mid] = (
            Method(id=mid, name=f"{mid} test method", family="test", source_kind="knowledge",
                   source_ref="", hypothesis="h", expected_failure="f", candidates=cands),
            HERE,
        )
    return out


def _build(path: Path) -> tuple[sqlite3.Connection, dict[str, int]]:
    """A lab holding ROWS as recorded dev trials, every one with provenance at 10M IDR."""
    conn = store.connect(path)
    with conn:
        for mid in ("M0001", "M0002"):
            store.add_method(conn, id=mid, name="n", family="f", source_kind="knowledge",
                             hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(*r) for r in ROWS])
        stamp_provenance(conn, ns)
    return conn, {f"{m}-{s}": n for (m, s, _sr, _dd), n in zip(ROWS, ns, strict=True)}


@pytest.fixture()
def wired(monkeypatch):
    """Everything outside the database the command reads, pinned for the test."""
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    monkeypatch.setattr(method_mod, "discover", _methods)
    monkeypatch.setattr(runner, "git_head", lambda cwd: "test-sha")


@pytest.fixture()
def lab(tmp_path, wired):
    path = tmp_path / "lab.sqlite"
    conn, ns = _build(path)
    g = store.gate(conn)
    assert g.n == len(ROWS), "the fixture's DSRs read back exactly only at N = the dev row count"
    for row in store.trials_of(conn, "M0001") + store.trials_of(conn, "M0002"):
        assert store.verdict(conn, row, at=g).eligible is (row["candidate_id"] in ELIGIBLE)
    assert control_shape.role_of(_methods()["M0001"][0].candidates[4]) == control_shape.ROLE_CONTROL
    yield conn, path, ns
    conn.close()


@pytest.fixture(scope="module")
def smoke():
    return smoke_data()


def _serve(monkeypatch, data) -> None:
    monkeypatch.setattr(research, "load_store", lambda *a, **k: data)


def _never_load(monkeypatch) -> None:
    def boom(*a, **k):
        raise AssertionError("the research store must not be loaded for this request")

    monkeypatch.setattr(research, "load_store", boom)


def _stand_in(calls: list, *, beaten: int = 18, raises: Exception | None = None):
    """A deterministic ``yardstick.measure``: same answer for any ``jobs``, every call logged."""

    def measure(market, dividends, spy_dividends, candidate, *, initial_idr, contributions,
                draws=yardstick.DRAWS, jobs=1, expect=None):
        calls.append({"candidate": candidate.id, "initial_idr": initial_idr,
                      "contributions": contributions, "draws": draws, "jobs": jobs,
                      "expect": expect})
        if raises is not None:
            raise raises
        return yardstick.Measurement(
            status=yardstick.STATUS_MEASURED, draws=draws, arm_rate=0.12,
            beaten=min(beaten, draws), percentile=min(beaten, draws) / draws,
            rates=tuple(0.001 * i for i in range(draws)), trade_ratio=1.02, turnover_ratio=0.97,
            reproduced=None if expect is None else True,
        )

    return measure


def _argv(path: Path, tmp_path: Path, *rest: str) -> list[str]:
    return ["lab", "--db", str(path), "yardstick", *rest, "--store", str(tmp_path / "store")]


def _rows(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM trial_yardstick ORDER BY trial_n, store_fingerprint").fetchall()


def _untouched(conn) -> tuple:
    """Everything a yardstick must leave as it found it (R1.2)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        store.gate(conn).n,
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM insights").fetchone()[0],
        tuple(tuple(r) for r in conn.execute("SELECT id, status, analysis FROM methods ORDER BY id")),
    )


def _row(trial_n: int, **kw) -> store.YardstickRow:
    base = dict(
        trial_n=trial_n, rule_id="yardstick-test", store_fingerprint=FP, status="measured",
        draws=20, arm_rate=0.12, beaten=18, percentile=0.9, rates_json="[]", trade_ratio=1.0,
        turnover_ratio=1.0, reproduced=True, git_sha="abc", measured="2026-11-13T00:00:00+00:00",
    )
    base.update(kw)
    return store.YardstickRow(**base)


# ---- the table ---------------------------------------------------------------------------------


def test_the_table_arrives_without_a_schema_version_and_is_append_only(lab):
    conn, _, ns = lab
    assert store.schema_version(conn) == store.SCHEMA_VERSION == "8"
    with conn:
        assert store.insert_yardstick(conn, _row(ns["M0001-A"])) is True
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE trial_yardstick SET beaten = 20")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM trial_yardstick")


def test_the_status_list_is_the_engines():
    assert store.YARDSTICK_STATUSES == (
        yardstick.STATUS_MEASURED, yardstick.STATUS_NOT_APPLICABLE, yardstick.STATUS_UNMATCHED,
    )


def test_the_label_is_derived_from_the_bar():
    assert store.YARDSTICK_MIN_PERCENTILE == 0.90
    assert store.YARDSTICK_LABEL == "beats 90% of random twins"
    assert f"{store.YARDSTICK_MIN_PERCENTILE:.0%}" in store.YARDSTICK_LABEL


def test_the_control_role_spelled_in_store_is_control_shapes():
    assert control_shape.ROLE_CONTROL == "control"


def test_a_repeat_on_the_same_key_writes_nothing_and_another_store_is_a_new_row(lab):
    conn, _, ns = lab
    n = ns["M0001-A"]
    with conn:
        assert store.insert_yardstick(conn, _row(n)) is True
        assert store.insert_yardstick(conn, _row(n, beaten=3, percentile=0.15)) is False
        assert store.insert_yardstick(conn, _row(n, store_fingerprint=OTHER_FP)) is True
        assert store.insert_yardstick(conn, _row(n, rule_id="yardstick-other")) is True
    assert conn.execute("SELECT count(*) FROM trial_yardstick").fetchone()[0] == 3
    kept = conn.execute(
        "SELECT beaten FROM trial_yardstick WHERE trial_n = ? AND rule_id = 'yardstick-test' "
        "AND store_fingerprint = ?", (n, FP),
    ).fetchone()[0]
    assert kept == 18, "the first measurement is the one kept"
    assert store.has_yardstick(conn, n, "yardstick-test", FP)
    assert not store.has_yardstick(conn, n, "yardstick-test", "fp-never")


@pytest.mark.parametrize(
    ("kw", "match"),
    [
        (dict(trial_n=0), "trial number of a recorded trial"),
        (dict(trial_n=999), "no trial #999"),
        (dict(status="passed"), "must be one of"),
        (dict(status="not-applicable", draws=5, beaten=0, percentile=None), "simulated no twin"),
        (dict(status="not-applicable", draws=0, beaten=0, percentile=None, trade_ratio=1.0,
              turnover_ratio=None), "simulated no twin"),
        (dict(status="measured", percentile=None), "needs its twins"),
        (dict(status="unmatched", draws=0, beaten=0, percentile=None), "needs its twins"),
        (dict(status="measured", beaten=21), "needs its twins"),
    ],
)
def test_insert_refuses_what_the_record_cannot_mean(lab, kw, match):
    conn, _, ns = lab
    with pytest.raises(store.LabError, match=match):
        store.insert_yardstick(conn, _row(ns["M0001-A"], **kw))
    assert conn.execute("SELECT count(*) FROM trial_yardstick").fetchone()[0] == 0


def test_insert_refuses_a_test_window_look(lab):
    conn, _, ns = lab
    look = dataclasses.replace(
        _trial("M0001", "A", 0.80, 0.20), config_digest="M0001-A-test", window="test"
    )
    with conn:
        (n,) = store.insert_trials(conn, [look])
    with pytest.raises(store.LabError, match="not a dev arm"):
        store.insert_yardstick(conn, _row(n))


def test_a_not_applicable_row_records_no_draws(lab):
    conn, _, ns = lab
    with conn:
        assert store.insert_yardstick(conn, _row(
            ns["M0001-A"], status="not-applicable", draws=0, beaten=0, percentile=None,
            arm_rate=0.1, trade_ratio=None, turnover_ratio=None, reproduced=None,
        ))
    got = store.yardstick_of(conn, ns["M0001-A"])
    assert (got["status"], got["draws"], got["beaten"], got["percentile"], got["reproduced"]) == (
        "not-applicable", 0, 0, None, None)


def test_from_measurement_takes_every_shape_the_engine_returns():
    """Decision D11: phase 2's ``Measurement`` constructor is the source of truth for a reading's
    shape, and every shape it admits becomes a row ``insert_yardstick`` accepts."""
    na = yardstick.Measurement(
        status=yardstick.STATUS_NOT_APPLICABLE, draws=0, arm_rate=0.1, beaten=0,
        percentile=None, rates=(), trade_ratio=None, turnover_ratio=None, reproduced=None,
    )
    odd = yardstick.Measurement(
        status=yardstick.STATUS_UNMATCHED, draws=4, arm_rate=0.1, beaten=3, percentile=0.75,
        rates=(0.01, 0.02, 0.03, 0.2), trade_ratio=2.6, turnover_ratio=1.0, reproduced=True,
    )
    for m, checked in ((na, True), (odd, True), (odd, False)):
        row = store.YardstickRow.from_measurement(
            m, trial_n=1, rule_id="r", store_fingerprint="fp", checked=checked, git_sha="g",
            measured="2026-11-14T00:00:00+00:00",
        )
        assert (row.status, row.draws, row.beaten, row.percentile) == (
            m.status, m.draws, m.beaten, m.percentile)
        assert row.reproduced is (None if not checked or m.reproduced is None else True)
    assert store.YardstickRow.from_measurement(
        na, trial_n=1, rule_id="r", store_fingerprint="fp", checked=True, git_sha="g", measured="t",
    ).rates_json == "[]"


def test_yardstick_of_is_the_newest_row(lab):
    conn, _, ns = lab
    n = ns["M0001-B"]
    assert store.yardstick_of(conn, n) is None
    with conn:
        store.insert_yardstick(conn, _row(n, measured="2026-11-13T00:00:00+00:00", beaten=4,
                                          percentile=0.2))
        store.insert_yardstick(conn, _row(n, store_fingerprint=OTHER_FP,
                                          measured="2026-11-14T00:00:00+00:00", beaten=19,
                                          percentile=0.95))
    got = store.yardstick_of(conn, n)
    assert (got["store_fingerprint"], got["beaten"]) == (OTHER_FP, 19)


def test_the_readers_answer_nothing_on_a_database_without_the_table(tmp_path):
    """A connect_readonly caller on a database no yardstick-aware code has opened for writing."""
    schema = store._SCHEMA
    for ddl in (store._YARDSTICK_TABLE, *store._YARDSTICK_TRIGGERS):
        assert f"{ddl};\n\n" in schema
        schema = schema.replace(f"{ddl};\n\n", "")
    assert "trial_yardstick" not in schema
    path = tmp_path / "old.sqlite"
    raw = sqlite3.connect(path)
    raw.executescript(schema)
    raw.commit()
    raw.close()
    ro = store.connect_readonly(path)
    try:
        assert store.yardstick_of(ro, 1) is None
        assert store.has_yardstick(ro, 1, "yardstick-v1", FP) is False
    finally:
        ro.close()


# ---- the bar and the due rule ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("row", "clears"),
    [
        (None, None),
        ({"status": "measured", "percentile": 0.90}, True),
        ({"status": "measured", "percentile": 0.95}, True),
        ({"status": "measured", "percentile": 0.895}, False),
        ({"status": "measured", "percentile": None}, False),
        ({"status": "not-applicable", "percentile": None}, True),
        ({"status": "unmatched", "percentile": 0.99}, False),
        ({"status": "something-new", "percentile": 0.99}, False),
    ],
)
def test_yardstick_clears(row, clears):
    assert store.yardstick_clears(row) is clears


def test_yardstick_clears_reads_a_row_a_dict_and_a_dataclass_alike(lab):
    """Phase 4 asks this on the ``sqlite3.Row`` ``yardstick_of`` returns, on plain dicts and on
    ``dataclasses.asdict(YardstickRow)``: one clearing rule, whatever the mapping."""
    conn, _, ns = lab
    passing, failing = _row(ns["M0001-A"]), _row(ns["M0001-B"], beaten=4, percentile=0.2)
    with conn:
        store.insert_yardstick(conn, passing)
        store.insert_yardstick(conn, failing)
    for row, clears in ((passing, True), (failing, False)):
        assert store.yardstick_clears(store.yardstick_of(conn, row.trial_n)) is clears
        assert store.yardstick_clears(dataclasses.asdict(row)) is clears
        assert store.yardstick_clears(
            {"status": row.status, "percentile": row.percentile}) is clears


def test_yardstick_due_is_an_eligible_dev_arm(lab):
    conn, _, ns = lab
    g = store.gate(conn)
    due = {
        t["candidate_id"]
        for t in store.trials_of(conn, "M0001") + store.trials_of(conn, "M0002")
        if store.yardstick_due(conn, t, at=g)
    }
    # M0001-E is eligible and a control by its rationale, but no role is RECORDED for it yet, and
    # yardstick_due reads the record only. The command skips it by its rationale (see below).
    assert due == ELIGIBLE
    row = store.trials_of(conn, "M0001")[0]
    assert store.yardstick_due(conn, {**dict(row), "window": "test"}, at=g) is False


def test_a_recorded_control_is_never_due_and_never_forced(lab, tmp_path, monkeypatch):
    conn, path, ns = lab
    with conn:
        store.insert_roles(conn, [store.RoleRow(
            trial_n=ns["M0001-B"], role="control", source="backfill", measured="test fixture",
        )])
    row = conn.execute("SELECT * FROM trials WHERE n = ?", (ns["M0001-B"],)).fetchone()
    assert store.yardstick_due(conn, row) is False
    _never_load(monkeypatch)
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-B")) == 2
    assert _rows(conn) == []


def test_an_arm_failing_only_on_the_yardstick_is_still_due(lab, monkeypatch):
    """Stays right once the yardstick is a condition in verdict (phase 4)."""
    conn, _, ns = lab
    row = conn.execute("SELECT * FROM trials WHERE n = ?", (ns["M0001-A"],)).fetchone()

    def reads(*failed):
        return lambda conn, trial, *, at=None, policy=None: store.Verdict(
            dsr=0.95, failed=failed, eligible=not failed, n=len(ROWS), policy="all-trials",
            derived=True,
        )

    monkeypatch.setattr(store, "verdict", reads(store.YARDSTICK_LABEL))
    assert store.yardstick_due(conn, row) is True
    monkeypatch.setattr(store, "verdict", reads(store.YARDSTICK_LABEL, store.DSR_LABEL))
    assert store.yardstick_due(conn, row) is False


# ---- the command -------------------------------------------------------------------------------


def test_cli_measures_each_due_arm_once_and_records_no_trial(lab, smoke, tmp_path, monkeypatch, capsys):
    conn, path, ns = lab
    before = _untouched(conn)
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "M0001")) == 0
    out = capsys.readouterr().out
    # C fails the drawdown screen; E is a control by its rationale and is skipped with a reason.
    assert [c["candidate"] for c in calls] == ["M0001-A", "M0001-B", "M0001-D"]
    assert "skipped M0001-E: a control arm by its rationale" in out
    for c in calls:
        assert c["draws"] == yardstick.DRAWS and c["jobs"] == 1
        assert c["initial_idr"] == Decimal("10000000") and c["contributions"] is None
        assert c["expect"] == (200, 1.0), "recorded on the loaded store: reproduce it first"
    rows = _rows(conn)
    assert [r["trial_n"] for r in rows] == [ns["M0001-A"], ns["M0001-B"], ns["M0001-D"]]
    for r in rows:
        assert (r["rule_id"], r["store_fingerprint"], r["status"]) == (yardstick.RULE_ID, FP, "measured")
        assert (r["draws"], r["beaten"], r["reproduced"], r["git_sha"]) == (yardstick.DRAWS, 18, 1, "test-sha")
    assert "3 arm(s) recorded" in out and "never a trial" in out
    assert _untouched(conn) == before

    # A repeat on the same store simulates nothing and writes nothing (R1.5).
    assert cli.main(_argv(path, tmp_path, "M0001")) == 0
    out = capsys.readouterr().out
    assert len(calls) == 3
    assert len(_rows(conn)) == 3
    assert "already measured on store" in out and "0 arm(s) recorded" in out
    assert _untouched(conn) == before


def test_another_store_is_a_new_row_with_nothing_to_reproduce(lab, smoke, tmp_path, monkeypatch):
    conn, path, ns = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=OTHER_FP))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A")) == 0
    assert calls[0]["expect"] is None
    (row,) = _rows(conn)
    assert (row["store_fingerprint"], row["reproduced"]) == (OTHER_FP, None)


def test_an_arm_that_does_not_reproduce_is_refused_with_exit_2_and_nothing_written(
    lab, smoke, tmp_path, monkeypatch, capsys
):
    conn, path, ns = lab
    before = _untouched(conn)
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(
        calls, raises=yardstick.Unreproducible("199 trades against 200 recorded"),
    ))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A")) == 2
    assert calls[0]["expect"] == (200, 1.0)
    assert _rows(conn) == []
    assert "does not reproduce" in capsys.readouterr().out
    assert _untouched(conn) == before


def test_a_not_applicable_arm_on_its_recording_store_is_recorded_with_reproduced_null(
    lab, smoke, tmp_path, monkeypatch
):
    """Decision D12: a bracket (or ETF-only) arm reads not-applicable and the engine never re-runs
    a bracket arm, so ``reproduced`` comes back None even with ``expect`` given. R1.6 cannot fire
    for it, and the row says "not checked", never "checked and passed"."""
    conn, path, ns = lab
    calls: list = []

    def measure(market, dividends, spy_dividends, candidate, *, initial_idr, contributions,
                draws=yardstick.DRAWS, jobs=1, expect=None):
        calls.append(expect)
        return yardstick.Measurement(
            status=yardstick.STATUS_NOT_APPLICABLE, draws=0, arm_rate=None, beaten=0,
            percentile=None, rates=(), trade_ratio=None, turnover_ratio=None, reproduced=None,
        )

    monkeypatch.setattr(yardstick, "measure", measure)
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A")) == 0
    assert calls == [(200, 1.0)], "recorded on the loaded store: expect was passed"
    (row,) = _rows(conn)
    assert (row["status"], row["draws"], row["beaten"], row["percentile"], row["reproduced"]) == (
        "not-applicable", 0, 0, None, None)
    assert store.yardstick_clears(row) is True


def test_a_refused_arm_does_not_stop_the_sweep_but_the_exit_is_2(lab, smoke, tmp_path, monkeypatch):
    conn, path, ns = lab
    calls: list = []
    good = _stand_in(calls)

    def measure(market, dividends, spy_dividends, candidate, **kw):
        if candidate.id == "M0001-B":
            calls.append({"candidate": candidate.id})
            raise yardstick.Unreproducible("return differs")
        return good(market, dividends, spy_dividends, candidate, **kw)

    monkeypatch.setattr(yardstick, "measure", measure)
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "M0001")) == 2
    assert [r["trial_n"] for r in _rows(conn)] == [ns["M0001-A"], ns["M0001-D"]]


def test_arm_forces_an_arm_that_is_not_due_but_never_a_control(lab, smoke, tmp_path, monkeypatch):
    conn, path, ns = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-C")) == 0  # fails drawdown, forced
    assert [r["trial_n"] for r in _rows(conn)] == [ns["M0001-C"]]
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-E")) == 2  # control by its rationale
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-Z")) == 2  # no such arm
    assert [c["candidate"] for c in calls] == ["M0001-C"]
    assert len(_rows(conn)) == 1


def test_pending_takes_the_oldest_due_arms_first_and_limit_caps_them(
    lab, smoke, tmp_path, monkeypatch, capsys
):
    conn, path, ns = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    assert cli.main(_argv(path, tmp_path, "--pending", "--limit", "2")) == 0
    assert [c["candidate"] for c in calls] == ["M0001-A", "M0001-B"]
    assert "due arm(s) left for a later run" in capsys.readouterr().out
    assert cli.main(_argv(path, tmp_path, "--pending")) == 0
    assert [c["candidate"] for c in calls] == ["M0001-A", "M0001-B", "M0001-D", "M0002-A", "M0002-B"]
    assert len(_rows(conn)) == 5


@pytest.mark.parametrize("where", ["global", "local"])
def test_dry_run_measures_and_writes_nothing(lab, smoke, tmp_path, monkeypatch, capsys, where):
    conn, path, ns = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
    argv = _argv(path, tmp_path, "--arm", "M0001-A")
    argv = ["--dry-run", *argv] if where == "global" else [*argv, "--dry-run"]
    assert cli.main(argv) == 0
    assert len(calls) == 1
    assert _rows(conn) == []
    assert "dry run: not recorded" in capsys.readouterr().out


def test_jobs_reaches_the_simulator_and_never_the_record(tmp_path, wired, smoke, monkeypatch):
    """R1.5's command half: J is passed through and is not part of what is recorded."""
    recorded = []
    for jobs in ("1", "3"):
        path = tmp_path / f"jobs{jobs}" / "lab.sqlite"
        conn, _ns = _build(path)
        calls: list = []
        monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
        _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP))
        assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A", "--jobs", jobs)) == 0
        assert calls[0]["jobs"] == int(jobs)
        (row,) = _rows(conn)
        recorded.append({k: row[k] for k in row.keys() if k != "measured"})
        conn.close()
    assert recorded[0] == recorded[1]


def test_a_survivorship_check_store_is_refused(lab, smoke, tmp_path, monkeypatch):
    conn, path, _ = lab
    calls: list = []
    monkeypatch.setattr(yardstick, "measure", _stand_in(calls))
    _serve(monkeypatch, dataclasses.replace(smoke, fingerprint=FP, purpose="survivorship-check"))
    assert cli.main(_argv(path, tmp_path, "--arm", "M0001-A")) == 2
    assert calls == [] and _rows(conn) == []


@pytest.mark.parametrize(
    "rest",
    [
        (),                                 # no selector
        ("M0001", "--pending"),             # two selectors
        ("M0001", "--arm", "M0001-A"),      # two selectors
        ("M0099",),                         # no such method
        ("--arm", "M0099-A"),               # no such arm
    ],
)
def test_a_bad_request_is_exit_2_before_any_store(lab, tmp_path, monkeypatch, rest):
    conn, path, _ = lab
    _never_load(monkeypatch)
    assert cli.main(_argv(path, tmp_path, *rest)) == 2
    assert _rows(conn) == []


def test_nothing_due_loads_no_store(tmp_path, wired, monkeypatch, capsys):
    path = tmp_path / "lab.sqlite"
    conn, _ = _build(path)
    with conn:
        store.add_method(conn, id="M0003", name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="registered")
    _never_load(monkeypatch)
    assert cli.main(_argv(path, tmp_path, "M0003")) == 0
    assert "nothing to measure" in capsys.readouterr().out
    conn.close()


def test_the_yardstick_help_strings_still_format(capsys):
    """argparse %-interpolates every help= string; a bare % there kills `lab --help`."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "yardstick", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "--pending" in out and "--jobs" in out
```
**Impact:** about 30 tests, all on `tmp_path` databases. They never open `lab/lab.sqlite` or the real store, and never reach the network. If phase 2's `ResearchData` / `smoke_data()` field names differ (`purpose`, `fingerprint`), adjust only the `dataclasses.replace` calls.

### Step 11: The feature map
**File:** `.claude/skills/verify-seer/features/lab-cli.md`
**Change 11a**, sub-features (line 6): phase 1 rewrote the `- Write (to the run's private copy only): ...` bullet; as phase 1 leaves it, it ends `` `reevaluate --demote` (moves a dev-eligible method with no eligible non-control arm today to rejected, with a dated note in its analysis; no trial row changes).``. Append the text below directly after that final `.` (same line):
```
 `yardstick` (`lab yardstick MNNNN | --arm CANDIDATE | --pending [--limit N] [--jobs J] [--dry-run]`: random twins of a recorded dev arm, one `trial_yardstick` row per arm and store, never a trial; a repeat prints "already measured" and writes nothing).
```
**Change 11b**, refused (line 7; phase 1 does not touch this bullet): insert into the `- Refused: ...` bullet directly after `no arm metric printed)` and before `; \`lab test\``:
```
; `lab yardstick --arm` on a control arm, an unknown arm or method, or an arm recorded on the loaded store that no longer reproduces its trade count and return (exit 2, nothing written)
```
**Change 11c**, drive lines: insert directly after the line `$V lab RUN twins M0001-TYPO   # exit 2: ...` (line 22; phase 1's five drive lines sit lower, directly before `$V lab RUN test M0007`, and are not touched). Phase 4 later inserts one `$V lab RUN status` line directly before the first line below and one directly after the last:
```
$V lab RUN yardstick --arm M0562-W60-B100 --jobs 2 --dry-run   # one table row: twins = yardstick.DRAWS, "beaten" b/DRAWS, a 12-hex "draw set", "(dry run: not recorded)"; exit 0; minutes
$V lab RUN yardstick --arm M0562-W60-B100 --jobs 2   # the same row without the note; "1 arm(s) recorded"; "Lab N (dev trials): X before, X after"; exit 0
$V lab RUN yardstick --arm M0562-W60-B100            # "already measured on store ...; not measured again", "0 arm(s) recorded"; exit 0; no twins simulated
$V labsql RUN "select trial_n, rule_id, status, draws, beaten, reproduced from trial_yardstick"   # one row, reproduced 1 when the trial was recorded on this store
```
**Change 11d**, gotchas: append a bullet at the end of `## Gotchas`, directly after phase 1's last bullet (`- Run \`lab roles --backfill\` before \`lab reevaluate --demote\`. ...`):
```
- `lab yardstick` loads the dev store from the main checkout and simulates `yardstick.DRAWS` twins per arm: a few minutes per arm at `--jobs 1`. Run it in the background (Bash `run_in_background`), not under a 10-minute foreground timeout. An arm recorded on another store than the one loaded is measured without the reproduction check and records `reproduced` NULL. `--arm` refuses a control by its recorded role or, before `lab roles --backfill`, by its rationale.
```
**Impact:** the feature map names the new user-facing command (CLAUDE.md: a user-facing change updates its entry in the same commit).

## Principles applied

- Make illegal states unrepresentable: the table's CHECKs refuse a `not-applicable` row with draws or a share, a `measured` row without them, `beaten > draws`, a percentile outside 0..1 and a `reproduced` other than 0, 1 or NULL. `insert_yardstick` states the same rules as sentences. `YardstickRow.from_measurement` forces `reproduced` to NULL whenever no reproduction was asked for, so "not checked" can never be stored as "passed". The status list is a literal in SQL, pinned equal to the engine's constants by a test.
- Boundary discipline: `--jobs` and `--limit` are validated once by argparse (`_positive_count`). The three selectors are checked once at the top of the handler. A `Measurement` becomes a row in exactly one place (`from_measurement`), which phase 4's writer reuses instead of rebuilding the columns.
- Laziness protocol: no new module and no draws flag. `runner.resolve_candidate`, `recorded_capital`, `recorded_contributions`, `refuse_survivorship_store` and the `_run` store-loading pattern are reused as they are. The store is not pinned with `hardgate.pin_dev_store`, because the row is keyed by store and no trial is written.
- Sequence into verifiable units: measuring happens with no lock held, and each arm commits in its own short `begin_immediate`. An interrupted `--pending` sweep therefore keeps what it finished, and a rerun skips it (`has_yardstick` before any simulation).
- Test behavior, not implementation: the tests replace only phase 2's simulator at its public boundary. They assert on the rows in the database, the exit codes and the N, trial-count and look invariants, never on private calls of the code under test.
- Encode lessons in structure: `YARDSTICK_LABEL` is derived from `YARDSTICK_MIN_PERCENTILE`, as `DSR_LABEL` is from `DSR_MIN`, the lesson of the 110 rows that carry a stale luck label. `yardstick_due` already accepts a verdict whose only failure is that label, so phase 4 cannot make every arm "not due" by adding it.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/random-twin-yardstick && (test -x engine/.venv/bin/python || (python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]')) && engine/.venv/bin/ruff check engine`
**Tests:** `engine/.venv/bin/pytest engine/tests/test_lab_yardstick_record.py -n0 && engine/.venv/bin/pytest engine/tests -k "lab_"`
**Proof:** the real `lab yardstick` command on a throwaway copy of the committed lab, against the main checkout's real dev store, then read back from the lab copy.
- Harness: `.claude/skills/verify-seer` (`V=.claude/skills/verify-seer/scripts/verify.sh`, run from the worktree). Start with `$V up --no-web --empty` and note `RUN`. Every long `$V lab RUN yardstick ...` drive goes in a Bash `run_in_background` call and is waited on by its exit notification, never polled. Before J1, record the baseline:
  - `$V labsql RUN "select count(*), sum(window='dev'), sum(window='test') from trials"`
  - `$V lab RUN status`, keeping its `N the luck gate judges at` line
  - `$V labsql RUN "select n, store_fingerprint from trials where candidate_id='M0562-W60-B100' and window='dev'"`
  - `python3 -c "import json;print(json.load(open('/home/miftah/seer/engine/.research/manifest.json'))['fingerprint'])"`

  Read these values back; do not quote numbers from this plan. The arm was chosen because it is a treatment arm ("60-session winners") that holds picked stocks, and at HEAD `f83fb237` it was recorded on the store the main checkout holds. If the two fingerprints differ at verification time, J2's `reproduced` expectation becomes NULL and J4 still proves R1.6.
- Feature-map entries: `.claude/skills/verify-seer/features/lab-cli.md`
- Journeys:
  - **J1** · traces R1.5 — run this FIRST, before J2: `$V lab RUN yardstick --arm M0562-W60-B100 --jobs 1 --dry-run`, then `$V labsql RUN "select count(*) from trial_yardstick"` → passes when the first exits 0 and prints one table row for `M0562-W60-B100` ending `(dry run: not recorded)`, and the count is 0. Keep that row's `beaten` (b/DRAWS) and `draw set` values for J2.
  - **J2** · traces R1.1, R1.2, R1.5 — `$V lab RUN yardstick --arm M0562-W60-B100 --jobs 2`, then:
    - `$V labsql RUN "select trial_n, rule_id, store_fingerprint, status, draws, beaten, percentile, reproduced, length(rates_json) > 2 from trial_yardstick"`
    - `engine/.venv/bin/python -c "from seer_engine.lab import yardstick; print(yardstick.RULE_ID, yardstick.DRAWS)"`
    - the three baseline reads again

    It passes when all of these hold:
    - The command exits 0 and its table row has the same `beaten` and `draw set` values as J1's (same result at `--jobs 1` and `--jobs 2`).
    - It prints `1 arm(s) recorded`.
    - `trial_yardstick` holds exactly one row: `trial_n` = the baseline `n` of `M0562-W60-B100`, `rule_id` = `yardstick.RULE_ID`, `store_fingerprint` = the manifest fingerprint, `status` in (`measured`, `unmatched`), `draws` = `yardstick.DRAWS`, `0 <= beaten <= draws`, `percentile` = `beaten / draws`, and the rates list is non-empty.
    - `reproduced` is 1 when the trial's `store_fingerprint` equals the manifest's, and NULL otherwise.
    - The trial counts, the `N the luck gate judges at` line and the test-look count are identical to the baseline, and the command's own footer says `X before, X after` for both.
  - **J3** · traces R1.5 — after J2, `$V lab RUN yardstick --arm M0562-W60-B100 --jobs 2` again, then `$V labsql RUN "select count(*) from trial_yardstick"` → passes when it exits 0 within about a store load (no twins simulated), prints `already measured on store` and `0 arm(s) recorded`, and the count is still 1.
  - **J4** · traces R1.6 — `engine/.venv/bin/pytest -n0 "engine/tests/test_lab_yardstick_record.py::test_an_arm_that_does_not_reproduce_is_refused_with_exit_2_and_nothing_written" "engine/tests/test_lab_yardstick_record.py::test_a_refused_arm_does_not_stop_the_sweep_but_the_exit_is_2" "engine/tests/test_lab_yardstick_record.py::test_a_not_applicable_arm_on_its_recording_store_is_recorded_with_reproduced_null"` → passes when all three pass. In the first two, an arm recorded on the loaded store whose re-run raises `Unreproducible` makes `lab yardstick` exit 2 with no `trial_yardstick` row for that arm, and the trial count, N and looks are unchanged. In the third, a not-applicable reading (the bracket case, which is never re-run) is recorded with `reproduced` NULL and exit 0 (Decision D12). The real store cannot be made to diverge without editing a frozen record, so this criterion is proven on the fixture lab through `cli.main`, the same entry point the CLI uses.
  - **J5** · traces R1.1, R1.2, R1.5, R1.6 — `engine/.venv/bin/pytest -n0 engine/tests/test_lab_yardstick_record.py` → passes when every test passes. This includes:
    - due-arm selection (an ineligible arm and a control are not measured)
    - `--pending` order and `--limit`
    - idempotence on the key
    - `jobs` passed through and absent from the row
    - `expect` passed only on the recording store
    - exit 2 on `Unreproducible`
    - the unchanged trial count, `gate(conn).n` and `test_looks`
- Neighbor check: `$V lab RUN show M0562`, `$V lab RUN twins M0488` and `$V lab RUN status` all exit 0 with output shaped as `features/lab-cli.md` describes. `engine/.venv/bin/pytest engine/tests/test_lab_snapshot.py engine/tests/test_lab_store.py -n0` passes; the old-schema strippers in `test_lab_snapshot.py` must still assert cleanly with the new statements in `_SCHEMA`. `sha1sum lab/lab.sqlite` is unchanged and `git status --porcelain lab web/data` lists nothing. Finish with `$V down RUN`.
- Cost: no paid drives (no LLM, no `--net`). CPU only: J1 and J2 each simulate `yardstick.DRAWS` twins of one arm over the dev window after a ~12 s store load. That is a few minutes each and depends on phase 2's speed; J3 is a store load and nothing else.

**Exit criteria:** `lab yardstick --arm M0562-W60-B100` on a verify-seer lab copy writes exactly one `trial_yardstick` row with `draws = yardstick.DRAWS`, prints the same result at `--jobs 1` and `--jobs 2`, writes nothing on a repeat, and leaves the trial count, the luck gate's N and the test looks unchanged. A non-reproducing arm exits 2 with nothing written. `ruff check engine` is clean and every `test_lab_*` file passes.

**Commit (explicit paths only; never `git commit -a`; `lab/lab.sqlite` is never staged — invariant 2; J1-J3 write only the verify-seer copy):**
```bash
cd /home/miftah/.worktrees/seer/random-twin-yardstick
git status --porcelain lab web/data   # must print nothing; if lab.sqlite shows: git checkout -- lab/lab.sqlite
git add engine/src/seer_engine/lab/store.py engine/src/seer_engine/commands/lab.py \
        engine/tests/test_lab_yardstick_record.py .claude/skills/verify-seer/features/lab-cli.md
git commit -m "lab: the yardstick record and lab yardstick (random-twin-yardstick phase 3)"
```

## Handoffs

- **Phase 4 (R2):** add `YARDSTICK_LABEL` to `store.verdict` and `runner.trial_rows`, add `YARDSTICK_SINCE`, measure inside `runner.run_method` and add the hard-gate clause. Phase 4 should:
  - record its in-run measurements with `store.YardstickRow.from_measurement(..., trial_n=0, checked=True, ...)` and `store.insert_yardstick` inside the run's transaction, so `lab run` and `lab yardstick` write identical rows (settled at reconcile: phase 4 has no row builder of its own);
  - validate `lab run --jobs` with this phase's `_positive_count` and log each reading with this phase's `_yardstick_line(candidate_id, row, note)` (settled at reconcile: phase 4 adds no `_job_count` and no second `_yardstick_line`);
  - read with `store.yardstick_of` and `store.yardstick_clears`, which takes any mapping.

  `yardstick_due` already treats a verdict failing only on `YARDSTICK_LABEL` as due, so it needs no change. The backfill runbook (`docs/runbooks/yardstick-backfill.md`) and the explore and Sera skill text belong to phase 4. The runbook should order `lab roles --backfill` before `lab yardstick --pending`. Without it the command still skips controls by their rationale, but recorded roles are the record.
- **Phase 5 (R2.4):** the snapshot's per-trial `yardstick` object reads `store.yardstick_of(conn, n)`, which returns None on a read-only connection to a database without the table. `medianRate` is the median of `json.loads(rates_json)`, the same value `lab yardstick` prints. A not-applicable row stores `beaten = 0`; the snapshot publishes it as null (phase 5's `_snapshot_yardstick`).
- **Phase 2 (R1.1, R1.3, R1.4, R1.5):** the twin draw itself, `unmatched` and `not-applicable` (R1.3, R1.4) and engine-level jobs-invariance belong to phase 2's own tests. This plan's table CHECKs, `insert_yardstick` and `from_measurement` mirror phase 2's `Measurement.__post_init__` exactly (Decision D11; listed under **Requires**), and `test_from_measurement_takes_every_shape_the_engine_returns` pins that.
- **Phase 1 (R3):** `store.role_of_trial`, `store.RoleRow(trial_n, role, source, measured)` and `store.insert_roles` are used by name, as phase 1 defines them.
- **Not taken (drive-by):** `_run`'s local `import json` (commands/lab.py:1923) becomes redundant once `json` is imported at module level. It is left in place, because removing it is a cleanup outside this phase.

## Rollback

Revert this phase's commit or commits (`git revert <sha>`). The table is created with `CREATE TABLE IF NOT EXISTS` and no schema version moves, so reverted code still opens any database that holds a `trial_yardstick` table, and nothing reads it. Rows already written stay, because the table is append-only, and they are inert. Nothing in `trials`, `methods`, `lab/lab.sqlite` on `main` or `web/data/lab.json` is changed by this phase, so there is nothing else to undo.
