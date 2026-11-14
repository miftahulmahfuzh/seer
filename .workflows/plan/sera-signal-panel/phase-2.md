# Phase 2: Panel record: tables, published verdict, snapshot key

**Plan set:** `SERA_SIGNAL_PANEL_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-200537-K7P2_code_analyzer.md`
**Satisfies:** R2, R3, R6. The lab keeps every panel reading once and works out from them which signals clear stage one (the correction across all of them, with twins collapsed). The web snapshot publishes the result.
**Criteria:** R2.3, R3.2, R6.1, R6.3
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` (plus `web/lib/sera` types)

---

## Goal

After this phase `lab/lab.sqlite` gains two append-only tables, `panel_signals` and `panel_results`, created on connect with no schema version bump. `lab/panel_verdict.py` computes each recorded panel's verdict when it is read: a Benjamini-Hochberg correction over every distinct pick set on the current dev store, the 2009-2015 spread and the survivorship slope, with identical pick sets counted once and the later one marked as a twin. `web/data/lab.json` moves to snapshot 9 with a last `panel` key. With no rows, or no tables at all, that key holds an empty `signals` list.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `store.PANEL_KINDS = ("signal", "replay")`, `store.PANEL_STORE_ROLES = ("dev", "survivorship")`, `store.PANEL_ERAS = ("all", "pre2009", "2009-2015")` (`store.py`, after `_YARDSTICK_TRIGGERS`)
- tables `panel_signals`, `panel_results` with triggers `panel_signals_no_update`, `panel_signals_no_delete`, `panel_results_no_update`, `panel_results_no_delete` (`_PANEL_SIGNALS_TABLE`, `_PANEL_SIGNALS_TRIGGERS`, `_PANEL_RESULTS_TABLE`, `_PANEL_RESULTS_TRIGGERS`, pasted into `_SCHEMA`). The columns are exactly the index's shared contract. This phase adds CHECKs: a `signal` row has an `S####` id and no `method_id`. A `replay` row has a `method_id`, and its id starts `<method_id>-`. `era` and `store_role` come from closed lists. `ic_mean` and `ic_t` are both NULL or both set. `months >= 1`, `0 <= top_turnover <= 1`, and the text columns are non-empty.
- `store.PanelSignalRow`, `store.PanelResultRow` (with `PanelResultRow.from_era(stats, *, signal_id, rule_id, store_role, store_fingerprint, picks_hash, git_sha, measured)`, duck-typed on phase 1's `EraStats` field names), `store.PANEL_SIGNAL_COLUMNS`, `store.PANEL_RESULT_COLUMNS`
- `store.insert_panel_signal(conn, row) -> bool`: True means inserted. False means the same id from the same `source_sha` already exists, and nothing is written. The same id from a different `source_sha` is refused with `LabError`. A replay must name a dev `trials.candidate_id` of its `method_id`.
- `store.insert_panel_results(conn, rows) -> int`: returns the number inserted. A repeat of a key (signal, rule, store, era) is skipped silently. `LabError` comes before anything is written for: an unknown signal, a non-finite number, half an IC pair, an IC on a replay, an unknown era or role, a fingerprint already recorded under the other role, or eras of one reading with different `picks_hash`.
- `store.panel_signals(conn) -> list[dict]` (ORDER BY id), `store.panel_results(conn, signal_id=None) -> list[dict]` (ORDER BY measured, rowid: oldest first), `store.has_panel(conn, signal_id, rule_id, store_fingerprint) -> bool`, `store.next_signal_id(conn, taken=()) -> str`. Every reader answers `[]` / `False` / `"S0001"` when the tables are absent. Readers return `dict`s, indexable by column name the way `sqlite3.Row` is, and independent of the connection's row factory.
- `seer_engine/lab/panel_verdict.py`: `RULE_ID = "panel-v1"`, `FDR = 0.10`, `Verdict(signal_id, clears, q, reasons, twin_of)`, `Readings(dev, survivorship)`, `one_sided_p(t, months) -> float`, `bh_qvalues(pvalues) -> list[float]`, `current_dev_fingerprint(conn) -> str | None`, `readings(conn, *, dev_fingerprint=None) -> dict[str, Readings]`, `published(conn, *, dev_fingerprint=None) -> dict[str, Verdict]`, and the reason sentences `UNMEASURED_REASON`, `TWIN_REASON`, `SLOPE_REASON`, `CHANCE_REASON`, `RECENT_MISSING_REASON`, `RECENT_REASON`, `SURVIVORSHIP_MISSING_REASON`, `SURVIVORSHIP_REASON`
- snapshot key `panel` (last top-level key): `{"rule", "fdr", "signals": [{"id", "kind", "name", "family", "methodId", "clears", "q", "reasons", "twinOf", "dev", "survivorship"}]}`. Each of `dev` and `survivorship` is `{"all", "pre2009", "recent"}` or null, and each era is `{"months", "ic", "icT", "spread", "spreadT", "slope", "slopeT", "turnover"}` or null. Signals come sorted by dev whole-window slope, highest first; unmeasured ones go last, and ties sort by id. **Refinement of the index contract:** `dev` may be null, for a signal not measured on the current dev store, and an era may be null.
- web: `LabPanel`, `LabPanelSignal`, `LabPanelStore`, `LabPanelEra`, `PanelKind`, `PANEL_KINDS` in `web/lib/sera/types.ts`; `LabSnapshot.panel`
**Signature changes:**
- `store.SNAPSHOT_VERSION = 8` -> `9`
- `LabSnapshot.version: 8` -> `9`
- `store._dicts(conn, sql)` -> `store._dicts(conn, sql, params=())`. This is backwards compatible, and every existing caller is unchanged.
- **Refinement of the index contract:** `next_signal_id(conn)` gains an optional `taken` iterable. With it, phase 3 can pass the ids of signal files that are committed but not yet panelled.
**Requires (from earlier phases):** nothing. This phase depends on no phase and does not import `lab/signal.py` or `lab/panel.py`. `RULE_ID` and `PANEL_ERAS` duplicate `panel.RULE_ID` / `panel.ERAS` on purpose; phase 3, the first phase that imports both modules, owns the test that pins the two pairs equal.
**Units and missing eras (reconciled):** `spread_top` is annualised, `fm_slope` is monthly. An era with fewer than 12 measured months has no row; `published` reads a missing dev `2009-2015` row or a missing survivorship `all` row as a failed condition with a plain-words reason, and the snapshot's `dev`, `survivorship` and any era object may be null. `store_fingerprint` is the store's full `ResearchData.fingerprint`.
**Leaves alone (owned by others):** `lab/signal.py`, `lab/signals/`, `lab/panel.py` (Phase 1); `commands/lab.py` (Phases 3, 4); `lab/panel_replay.py` (Phase 4); `method.py`, `runner.py`, `hardgate.py`, `signal_book.py` (Phase 5); every page and component under `web/app` and `web/components`, `web/lib/sera/lab.ts`, `web/lib/sera/fixture.ts` (Phase 6); skills, `CLAUDE.md`, `README.md` (Phase 7). `lab/lab.sqlite` is left byte-identical to the base commit (see Step 9).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | module docstring bullets (:74); vocab and table constants after `:693`; `_SCHEMA` paste after `:859`; panel API section before the `web snapshot` banner `:3842`; `_dicts` params `:3928`; `SNAPSHOT_VERSION = 9` and its history paragraph `:3889-3898`; `snapshot` docstring `:4171-4175` and the `panel` key after `"paper"` `:4323`; `_snapshot_panel*` after `_snapshot_books` `:4360` |
| `engine/src/seer_engine/lab/panel_verdict.py` | create | FDR, Student-t p-value, BH q-values, twins, `published` |
| `engine/tests/test_lab_panel_record.py` | create | tables, inserts, refusals, readers without tables, p-value, BH, verdicts, twins, snapshot block |
| `engine/tests/test_lab_snapshot.py` | modify | `:673` version 9; `:945-947` key list gains `"panel"`, version 9 |
| `engine/tests/test_lab_books.py` | modify | `:315` version 9 |
| `engine/tests/test_lab_gate_wording.py` | modify | pin `PANEL_KINDS` web == engine (after `:324`) |
| `web/lib/sera/types.ts` | modify | `version: 9`, history line, `panel: LabPanel`; panel types and `PANEL_KINDS` appended after `:379` |
| `web/lib/sera/lab.test.ts` | modify | `:6` import, `:10-14` version and key list, one new `it` for the panel shape |
| `web/app/sera/overview.test.ts` | modify | `:104` `version: 9`; `panel` literal after `books` (`:151`) |
| `web/data/lab.json` | regenerate | export of the base `lab/lab.sqlite` with this code (version 9, empty `panel`) |
| `.workflows/plan/sera-signal-panel/phase-2-drive.py` | create | Proof script: records panels in a copy, prints verdicts, exports through the CLI |

## Implementation Steps

Run everything from the worktree. Throughout: `W=/home/miftah/.worktrees/seer/sera-signal-panel`, `PY="env PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python"`.

### Step 1: Vocabulary and the two tables
**File:** `engine/src/seer_engine/lab/store.py:693` (insert directly after the closing `)` of `_YARDSTICK_TRIGGERS`, before `#: The backfill's capital rule`)
**Change:** add the three vocabularies and the two table/trigger pairs, following the `trial_yardstick` pattern.
**Code:**
```python

# The stock-by-month signal panel (SERA_SIGNAL_PANEL_PLAN.md phase 2): stage one of the lab. A
# stock-picking idea is measured here -- does its ranking order next month's returns across the
# index? -- before it is ever simulated as a book. Two tables, both written only by ``lab panel``
# and ``lab panel-replay`` (phases 3 and 4), and neither of them is a trial: no ``trials`` row, no
# change to the luck gate's N, no test-window look. The panel carries its own multiple-testing
# correction (``lab/panel_verdict.py``) and that correction is never stored, because it moves
# every time another panel is recorded.
#
# ``panel_signals`` is one row per thing measured. A ``signal`` is a committed file under
# ``lab/signals/`` and its id is ``S0001``; a ``replay`` is one recorded dev arm of a method that
# already ran, re-read as a pick set, and its id is that arm's own candidate id (``M0614-V1``)
# with ``method_id`` naming the method. The two CHECKs make the mixed cases unrepresentable: a
# signal that names a method, a replay that does not, a replay whose id is some other method's
# arm. ``source_sha`` is the file the measurement read -- the signal file, or the method file of a
# replay -- and ``insert_panel_signal`` refuses the same id from a different file, because a
# signal is frozen once it has been panelled exactly as a method is frozen once it has run.
#
# ``panel_results`` is one row per (signal, panel rule, research store, era). ``rule_id`` is
# ``panel_verdict.RULE_ID``, so a later rule is a new measurement rather than a rewrite;
# ``store_fingerprint`` is the store the reading was taken on -- its full ``ResearchData.fingerprint``
# (the manifest's ``"fingerprint"``, what ``trials.store_fingerprint`` holds), not its price
# fingerprint, so a refreshed optional file means a re-panel, which is cheap -- and ``store_role``
# says which of the two stores that is. A repeat of the key writes nothing (``insert_panel_results`` skips it), so a
# sweep interrupted half way can simply be run again. ``ic_mean`` / ``ic_t`` are NULL together: a
# replay is a set of picks with no score to rank, so it has no rank correlation. ``picks_hash`` is
# the same on every era of one reading (it hashes the whole month-by-month top bucket), and it is
# what makes two panels twins.
#
# **No schema version**, for the reason ``trial_roles`` gave: ``CREATE TABLE IF NOT EXISTS`` adds
# both tables to an existing v8 database on connect, every reader answers empty when they are
# absent, and a version bump is a one-way door for every parallel checkout.
PANEL_KINDS: tuple[str, ...] = ("signal", "replay")
PANEL_STORE_ROLES: tuple[str, ...] = ("dev", "survivorship")
#: Mirrors ``panel.ERAS`` (phase 1): the whole dev window, the years before 2009, and 2009-2015.
PANEL_ERAS: tuple[str, ...] = ("all", "pre2009", "2009-2015")

_PANEL_SIGNALS_TABLE = f"""CREATE TABLE IF NOT EXISTS panel_signals (
    id               TEXT PRIMARY KEY,
    kind             TEXT NOT NULL CHECK (kind IN ({_quoted(PANEL_KINDS)})),
    name             TEXT NOT NULL CHECK (length(trim(name)) > 0),
    family           TEXT NOT NULL CHECK (length(trim(family)) > 0),
    hypothesis       TEXT NOT NULL CHECK (length(trim(hypothesis)) > 0),
    expected_failure TEXT NOT NULL CHECK (length(trim(expected_failure)) > 0),
    source_kind      TEXT NOT NULL CHECK (source_kind IN ({_quoted(SOURCE_KINDS)})),
    source_ref       TEXT NOT NULL DEFAULT '',
    method_id        TEXT REFERENCES methods(id),
    source_sha       TEXT NOT NULL CHECK (length(trim(source_sha)) > 0),
    created          TEXT NOT NULL CHECK (length(trim(created)) > 0),
    CHECK (kind <> 'signal' OR (id GLOB 'S[0-9][0-9][0-9][0-9]' AND method_id IS NULL)),
    CHECK (kind <> 'replay' OR (method_id IS NOT NULL
                                AND substr(id, 1, length(method_id) + 1) = method_id || '-'))
)"""
_PANEL_SIGNALS_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS panel_signals_no_update BEFORE UPDATE ON panel_signals
BEGIN SELECT RAISE(ABORT, 'panel_signals are append-only: a panel signal row is never updated'); END""",
    """CREATE TRIGGER IF NOT EXISTS panel_signals_no_delete BEFORE DELETE ON panel_signals
BEGIN SELECT RAISE(ABORT, 'panel_signals are append-only: a panel signal row is never deleted'); END""",
)

_PANEL_RESULTS_TABLE = f"""CREATE TABLE IF NOT EXISTS panel_results (
    signal_id         TEXT NOT NULL REFERENCES panel_signals(id),
    rule_id           TEXT NOT NULL CHECK (length(trim(rule_id)) > 0),
    store_role        TEXT NOT NULL CHECK (store_role IN ({_quoted(PANEL_STORE_ROLES)})),
    store_fingerprint TEXT NOT NULL CHECK (length(trim(store_fingerprint)) > 0),
    era               TEXT NOT NULL CHECK (era IN ({_quoted(PANEL_ERAS)})),
    months            INTEGER NOT NULL CHECK (months >= 1),
    mean_pool         REAL NOT NULL CHECK (mean_pool >= 0),
    mean_scored       REAL NOT NULL CHECK (mean_scored >= 0),
    ic_mean           REAL,
    ic_t              REAL,
    spread_top        REAL NOT NULL,
    spread_t          REAL NOT NULL,
    fm_slope          REAL NOT NULL,
    fm_t              REAL NOT NULL,
    top_turnover      REAL NOT NULL CHECK (top_turnover >= 0 AND top_turnover <= 1),
    picks_hash        TEXT NOT NULL CHECK (length(trim(picks_hash)) > 0),
    git_sha           TEXT NOT NULL CHECK (length(trim(git_sha)) > 0),
    measured          TEXT NOT NULL CHECK (length(trim(measured)) > 0),
    PRIMARY KEY (signal_id, rule_id, store_fingerprint, era),
    CHECK ((ic_mean IS NULL) = (ic_t IS NULL))
)"""
_PANEL_RESULTS_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS panel_results_no_update BEFORE UPDATE ON panel_results
BEGIN SELECT RAISE(ABORT, 'panel_results are append-only: a panel reading is never updated'); END""",
    """CREATE TRIGGER IF NOT EXISTS panel_results_no_delete BEFORE DELETE ON panel_results
BEGIN SELECT RAISE(ABORT, 'panel_results are append-only: a panel reading is never deleted'); END""",
)
```
**Impact:** constants only, so nothing runs yet. `SOURCE_KINDS` (`:128`) and `_quoted` (`:321`) are defined above this point.

### Step 2: Paste the tables into `_SCHEMA`
**File:** `engine/src/seer_engine/lab/store.py:859`
**Change:** after the line `{_YARDSTICK_TRIGGERS[1]};` and its following blank line, and before `CREATE TRIGGER IF NOT EXISTS trials_no_update`, insert:
**Code:**
```python
{_PANEL_SIGNALS_TABLE};

{_PANEL_SIGNALS_TRIGGERS[0]};

{_PANEL_SIGNALS_TRIGGERS[1]};

{_PANEL_RESULTS_TABLE};

{_PANEL_RESULTS_TRIGGERS[0]};

{_PANEL_RESULTS_TRIGGERS[1]};

```
**Impact:** every `store.connect` now creates both tables. `panel_signals` must come before `panel_results`, which references it. The `methods` table is created earlier in the same script. `connect_readonly` creates nothing, which is the tables-absent case every reader handles. Check: `$PY -c "from seer_engine.lab import store; import tempfile,os; c=store.connect(os.path.join(tempfile.mkdtemp(),'x.sqlite')); print(sorted(r[0] for r in c.execute(\"select name from sqlite_master where name like 'panel_%'\")))"` prints the two tables and four triggers.

### Step 3: Module docstring
**File:** `engine/src/seer_engine/lab/store.py:74` (after the `trial_yardstick` bullet ending `every UPDATE and DELETE.`, before the blank line and `Schema versions`)
**Code:**
```python
- ``panel_signals`` and ``panel_results``: stage one of the lab, the stock-by-month signal panel.
  One ``panel_signals`` row per thing measured -- a committed signal file (``S0001``) or a replay
  of a recorded dev arm (its candidate id, with ``method_id`` set) -- and one ``panel_results``
  row per (signal, panel rule, research store, era) with the reading: months, rank correlation,
  top-minus-pool spread and the controlled slope, each with its t-statistic. Neither is a trial:
  no N, no look. Which signals *clear* is never stored; ``lab/panel_verdict.py`` works it out on
  read, because the false-discovery correction moves with every panel added. Created by ``CREATE
  TABLE IF NOT EXISTS`` on connect with no schema version, and every reader answers empty when
  they are absent. Triggers refuse every UPDATE and DELETE.
```
**Impact:** docs only.

### Step 4: `_dicts` takes parameters
**File:** `engine/src/seer_engine/lab/store.py:3928`
**Change:** replace the whole `_dicts` function with:
**Code:**
```python
def _dicts(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """Rows as dicts, whatever the connection's row_factory."""
    cur = conn.execute(sql, tuple(params))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]
```
**Impact:** existing callers pass no `params` and behave exactly as before. `Sequence` and `Any` are already imported (`:112`, `:117`).

### Step 5: The panel API
**File:** `engine/src/seer_engine/lab/store.py:3842`. Insert directly **before** the line `# --------------------------------------------------------------------------- web snapshot`, after `as_mapping`.
**Code:**
```python
# --------------------------------------------------------------------------- signal panel


@dataclass(frozen=True)
class PanelSignalRow:
    """One thing the panel measured: a registered signal, or a replay of a recorded dev arm.

    - ``id``                ``S0001`` for a signal; the replayed arm's candidate id for a replay.
    - ``kind``              one of ``PANEL_KINDS``.
    - ``name``, ``family``  what it ranks on, in plain words, and the family it belongs to.
    - ``hypothesis``, ``expected_failure``  as pre-registered in the file.
    - ``source_kind``, ``source_ref``  where the idea came from (``SOURCE_KINDS``).
    - ``method_id``         the method a replay belongs to; None for a signal.
    - ``source_sha``        sha256 of the file the measurement read (signal file or method file).
    - ``created``           when the row was first recorded; the twin rule's "earlier".
    """

    id: str
    kind: str
    name: str
    family: str
    hypothesis: str
    expected_failure: str
    source_kind: str
    source_ref: str
    method_id: str | None
    source_sha: str
    created: str


@dataclass(frozen=True)
class PanelResultRow:
    """One era of one panel reading, on one research store, under one panel rule.

    The database half of phase 1's ``panel.EraStats``; ``from_era`` is the one place a reading
    becomes a row. Every rate is a fraction. ``spread_top`` is annualised; ``fm_slope`` is
    **monthly**, never annualised: the mean next-month return per standard deviation of score (or
    per pick, for a replay) after the momentum, beta, size and volatility controls. A reader that
    prints a yearly slope multiplies by 12 and never prints the two as one unit. Each ``*_t`` is
    that series' t-statistic over
    ``months``. ``ic_mean`` / ``ic_t`` are None together, and always None for a replay.
    """

    signal_id: str
    rule_id: str
    store_role: str
    store_fingerprint: str
    era: str
    months: int
    mean_pool: float
    mean_scored: float
    ic_mean: float | None
    ic_t: float | None
    spread_top: float
    spread_t: float
    fm_slope: float
    fm_t: float
    top_turnover: float
    picks_hash: str
    git_sha: str
    measured: str

    @classmethod
    def from_era(
        cls,
        stats: Any,
        *,
        signal_id: str,
        rule_id: str,
        store_role: str,
        store_fingerprint: str,
        picks_hash: str,
        git_sha: str,
        measured: str,
    ) -> PanelResultRow:
        """The row for ``stats`` (a ``panel.EraStats``), typed for the table.

        Duck-typed rather than imported, for the reason ``YardstickRow.from_measurement`` is: the
        whole lab imports ``store``, and ``panel`` pulls in the research loader. The fields read
        are ``era``, ``months``, ``mean_pool``, ``mean_scored``, ``ic_mean``, ``ic_t``,
        ``spread_top``, ``spread_t``, ``fm_slope``, ``fm_t`` and ``top_turnover``.
        """
        return cls(
            signal_id=str(signal_id),
            rule_id=str(rule_id),
            store_role=str(store_role),
            store_fingerprint=str(store_fingerprint),
            era=str(stats.era),
            months=int(stats.months),
            mean_pool=float(stats.mean_pool),
            mean_scored=float(stats.mean_scored),
            ic_mean=None if stats.ic_mean is None else float(stats.ic_mean),
            ic_t=None if stats.ic_t is None else float(stats.ic_t),
            spread_top=float(stats.spread_top),
            spread_t=float(stats.spread_t),
            fm_slope=float(stats.fm_slope),
            fm_t=float(stats.fm_t),
            top_turnover=float(stats.top_turnover),
            picks_hash=str(picks_hash),
            git_sha=str(git_sha),
            measured=str(measured),
        )


PANEL_SIGNAL_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(PanelSignalRow))
PANEL_RESULT_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(PanelResultRow))


def _is_signal_id(text: str) -> bool:
    """``S`` and four ASCII digits: the shape a signal file's id takes (``lab/signal.py``)."""
    s = str(text)
    return len(s) == 5 and s[0] == "S" and s[1:].isascii() and s[1:].isdigit()


def _has_panel_tables(conn: sqlite3.Connection) -> bool:
    """Whether this database has both panel tables.

    ``connect`` always creates them, so False means a ``connect_readonly`` caller on a database
    no panel-aware code has opened for writing -- the snapshot sync guard reading the committed
    file is one. Every reader below then answers "nothing recorded", which is what it is.
    """
    names = {
        str(r[0])
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('panel_signals', 'panel_results')"
        )
    }
    return names == {"panel_signals", "panel_results"}


def panel_signals(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every recorded panel signal and replay, by id. Empty when the tables are absent."""
    if not _has_panel_tables(conn):
        return []
    return _dicts(conn, "SELECT * FROM panel_signals ORDER BY id")


def panel_results(conn: sqlite3.Connection, signal_id: str | None = None) -> list[dict[str, Any]]:
    """Every recorded panel reading (or one signal's), oldest first. Empty when the tables are absent.

    Oldest first -- ``measured``, then insertion order -- so a reader that keeps the last row it
    sees for a key holds the newest one. ``panel_verdict`` relies on that.
    """
    if not _has_panel_tables(conn):
        return []
    if signal_id is None:
        return _dicts(conn, "SELECT * FROM panel_results ORDER BY measured, rowid")
    return _dicts(
        conn,
        "SELECT * FROM panel_results WHERE signal_id = ? ORDER BY measured, rowid",
        (str(signal_id),),
    )


def has_panel(conn: sqlite3.Connection, signal_id: str, rule_id: str, store_fingerprint: str) -> bool:
    """Whether ``signal_id`` already has a reading under ``rule_id`` on ``store_fingerprint``.

    ``lab panel`` asks before it measures, so a repeat costs no panel run as well as writing no
    row. False when the tables are absent.
    """
    if not _has_panel_tables(conn):
        return False
    return conn.execute(
        "SELECT 1 FROM panel_results WHERE signal_id = ? AND rule_id = ? AND store_fingerprint = ? "
        "LIMIT 1",
        (str(signal_id), str(rule_id), str(store_fingerprint)),
    ).fetchone() is not None


def next_signal_id(conn: sqlite3.Connection, taken: Iterable[str] = ()) -> str:
    """The next free ``S0001``-style id: one above the highest recorded **and** named in ``taken``.

    ``taken`` is for the caller that also knows the signal files on disk: a file is committed
    before it is panelled, so the database alone would hand a second session an id a committed
    file already holds. Anything in ``taken`` that is not a signal id is ignored. A replay's id
    is an arm's candidate id and never consumes a signal number.
    """
    used = [int(str(s)[1:]) for s in taken if _is_signal_id(s)]
    if _has_panel_tables(conn):
        row = conn.execute(
            "SELECT max(CAST(substr(id, 2) AS INTEGER)) FROM panel_signals WHERE kind = 'signal'"
        ).fetchone()
        if row[0] is not None:
            used.append(int(row[0]))
    return f"S{max(used, default=0) + 1:04d}"


def insert_panel_signal(conn: sqlite3.Connection, row: PanelSignalRow) -> bool:
    """Record one panel signal (the caller holds the transaction). False, writing nothing, on a repeat.

    A repeat is the same id from the same ``source_sha``: the same file panelled again, which a
    re-run sweep does. The same id from a **different** file is refused -- a panelled signal is
    frozen, so a changed idea takes a new id, exactly as a changed method does.

    Refused with ``LabError`` before anything is written, the table's CHECKs stated as sentences:
    a kind outside ``PANEL_KINDS``; an empty name, family, hypothesis, expected failure, sha or
    timestamp; a ``source_kind`` outside ``SOURCE_KINDS``; a signal whose id is not ``S####`` or
    that names a method; a replay that names no method, whose id is not one of that method's arms,
    or whose arm has no dev trial -- a replay re-reads an arm the lab recorded, nothing else.
    """
    sid = str(row.id)
    if row.kind not in PANEL_KINDS:
        raise LabError(f"panel signal {sid}: kind must be one of {PANEL_KINDS}, got {row.kind!r}")
    for col in ("name", "family", "hypothesis", "expected_failure", "source_sha", "created"):
        if not str(getattr(row, col) or "").strip():
            raise LabError(f"panel signal {sid}: {col} is empty")
    if row.source_kind not in SOURCE_KINDS:
        raise LabError(
            f"panel signal {sid}: source_kind must be one of {SOURCE_KINDS}, got {row.source_kind!r}"
        )
    if row.kind == "signal":
        if not _is_signal_id(sid):
            raise LabError(f"a signal's id is S followed by four digits, got {sid!r}")
        if row.method_id is not None:
            raise LabError(
                f"signal {sid} names method {row.method_id}: only a replay belongs to a method"
            )
    else:
        mid = row.method_id
        if not mid:
            raise LabError(
                f"replay {sid} names no method: a replay is one recorded arm of a method"
            )
        if not sid.startswith(f"{mid}-"):
            raise LabError(
                f"replay {sid} is not an arm of {mid}: a replay's id is the candidate id it replays"
            )
        if conn.execute(
            "SELECT 1 FROM trials WHERE candidate_id = ? AND method_id = ? AND window = 'dev'",
            (sid, mid),
        ).fetchone() is None:
            raise LabError(
                f"replay {sid}: no dev trial of {mid} has that arm; a replay re-reads an arm the "
                "lab recorded"
            )
    existing = conn.execute(
        "SELECT kind, source_sha FROM panel_signals WHERE id = ?", (sid,)
    ).fetchone()
    if existing is not None:
        if (str(existing[0]), str(existing[1])) == (row.kind, str(row.source_sha)):
            return False
        raise LabError(
            f"{sid} is already recorded from a different file (sha {str(existing[1])[:12]}): a "
            "panelled signal is frozen, so a changed idea takes a new id"
        )
    cols = ", ".join(f'"{c}"' for c in PANEL_SIGNAL_COLUMNS)
    marks = ", ".join("?" for _ in PANEL_SIGNAL_COLUMNS)
    conn.execute(
        f"INSERT INTO panel_signals ({cols}) VALUES ({marks})",
        [getattr(row, c) for c in PANEL_SIGNAL_COLUMNS],
    )
    return True


def _check_panel_result(row: PanelResultRow, kind: str) -> None:
    """Refuse a row that cannot be a reading, with a sentence rather than a constraint name."""
    sid = row.signal_id
    for col in ("rule_id", "store_fingerprint", "picks_hash", "git_sha", "measured"):
        if not str(getattr(row, col) or "").strip():
            raise LabError(f"panel result {sid}: {col} is empty")
    if row.store_role not in PANEL_STORE_ROLES:
        raise LabError(
            f"panel result {sid}: store_role must be one of {PANEL_STORE_ROLES}, got {row.store_role!r}"
        )
    if row.era not in PANEL_ERAS:
        raise LabError(f"panel result {sid}: era must be one of {PANEL_ERAS}, got {row.era!r}")
    if int(row.months) < 1:
        raise LabError(
            f"panel result {sid} {row.era}: measured no month, and a reading with no months is "
            "not recorded"
        )
    for col in ("mean_pool", "mean_scored", "spread_top", "spread_t", "fm_slope", "fm_t", "top_turnover"):
        value = getattr(row, col)
        if value is None or not math.isfinite(float(value)):
            raise LabError(
                f"panel result {sid} {row.era}: {col} must be a finite number, got {value!r}"
            )
    if float(row.mean_pool) < 0 or float(row.mean_scored) < 0:
        raise LabError(f"panel result {sid} {row.era}: a pool size is never negative")
    if not 0.0 <= float(row.top_turnover) <= 1.0:
        raise LabError(
            f"panel result {sid} {row.era}: top_turnover is a share of the top bucket, between 0 "
            f"and 1, got {row.top_turnover!r}"
        )
    if (row.ic_mean is None) != (row.ic_t is None):
        raise LabError(
            f"panel result {sid} {row.era}: the rank correlation and its t-statistic are recorded "
            "together or not at all"
        )
    if row.ic_mean is not None:
        for col in ("ic_mean", "ic_t"):
            value = getattr(row, col)
            if not math.isfinite(float(value)):
                raise LabError(
                    f"panel result {sid} {row.era}: {col} must be a finite number, got {value!r}"
                )
        if kind == "replay":
            raise LabError(
                f"replay {sid} has a rank correlation: a replay is a pick set with no score to rank"
            )


def insert_panel_results(conn: sqlite3.Connection, rows: Iterable[PanelResultRow]) -> int:
    """Record panel readings (the caller holds the transaction). Returns how many were new.

    A row whose key -- (signal, rule, store, era) -- is already recorded is skipped: the same
    reading again, which a re-run sweep produces. Every row is checked before any is written, so
    a refused batch leaves nothing behind. Refused with ``LabError``:

    - a signal that is not recorded (record the signal first, in the same transaction);
    - a row that cannot be a reading (``_check_panel_result``);
    - a store fingerprint already recorded under the other role: one store is either the dev
      store or the survivorship store, never both;
    - eras of one reading (signal, rule, store) with different ``picks_hash``: the hash covers
      the whole month-by-month pick series, so it cannot differ by era.
    """
    batch = list(rows)
    kinds: dict[str, str] = {}
    for row in batch:
        sid = str(row.signal_id)
        if sid not in kinds:
            found = conn.execute("SELECT kind FROM panel_signals WHERE id = ?", (sid,)).fetchone()
            if found is None:
                raise LabError(f"no panel signal {sid}: record the signal before its results")
            kinds[sid] = str(found[0])
        _check_panel_result(row, kinds[sid])
    role_of: dict[str, str] = {}
    hash_of: dict[tuple[str, str, str], str] = {}
    for row in batch:
        fp = str(row.store_fingerprint)
        role = role_of.get(fp)
        if role is None:
            got = conn.execute(
                "SELECT store_role FROM panel_results WHERE store_fingerprint = ? LIMIT 1", (fp,)
            ).fetchone()
            role = str(row.store_role) if got is None else str(got[0])
            role_of[fp] = role
        if role != row.store_role:
            raise LabError(
                f"store {fp[:12]} is recorded as the {role} store; it cannot also be the "
                f"{row.store_role} store"
            )
        key = (str(row.signal_id), str(row.rule_id), fp)
        prior = hash_of.get(key)
        if prior is None:
            got = conn.execute(
                "SELECT picks_hash FROM panel_results WHERE signal_id = ? AND rule_id = ? "
                "AND store_fingerprint = ? LIMIT 1",
                key,
            ).fetchone()
            prior = str(row.picks_hash) if got is None else str(got[0])
            hash_of[key] = prior
        if prior != row.picks_hash:
            raise LabError(
                f"{row.signal_id}: every era of one reading shares its pick set, but {row.era} "
                f"carries a different one on store {fp[:12]}"
            )
    cols = ", ".join(f'"{c}"' for c in PANEL_RESULT_COLUMNS)
    marks = ", ".join("?" for _ in PANEL_RESULT_COLUMNS)
    inserted = 0
    for row in batch:
        if conn.execute(
            "SELECT 1 FROM panel_results WHERE signal_id = ? AND rule_id = ? "
            "AND store_fingerprint = ? AND era = ?",
            (row.signal_id, row.rule_id, row.store_fingerprint, row.era),
        ).fetchone() is not None:
            continue
        values = [getattr(row, c) for c in PANEL_RESULT_COLUMNS]
        values[PANEL_RESULT_COLUMNS.index("months")] = int(row.months)
        conn.execute(f"INSERT INTO panel_results ({cols}) VALUES ({marks})", values)
        inserted += 1
    return inserted
```
**Impact:** this adds an API and changes no existing behaviour. Check: `engine/.venv/bin/ruff check engine` with the worktree's ruff, as in Verification.

### Step 6: `lab/panel_verdict.py`
**File:** `engine/src/seer_engine/lab/panel_verdict.py` (new)
**Code:**
```python
"""The signal panel's published verdict: which recorded panels clear stage one of the lab.

A panel **clears** when all three of these hold, and the three are exactly the readings the owner
asked the panel for (SERA_SIGNAL_PANEL_PLAN.md, Decisions: "The panel bar"):

1. on the current dev store, over the whole window, its controlled slope -- next month's return
   on the signal once momentum, beta, size and volatility are allowed for -- is positive, and its
   one-sided p-value survives a Benjamini-Hochberg correction at ``FDR`` across **every distinct
   pick set ever recorded on that store**, replays of already-run methods included;
2. on the same store, its top bucket beat the pool from 2009 to 2015 (the era the lab's dev
   window says least about and the owner's real money says most about);
3. on the survivorship store, with the delisted companies put back, its whole-window controlled
   slope is still positive.

**Computed on read, never stored.** The correction is a statement about the whole population of
panels, so it moves every time a panel is recorded -- a q-value written into a row would be wrong
the next day. ``store.snapshot`` and ``lab panel-map`` call ``published`` at export or print
time, as the luck gate's N is resolved at export time rather than stored.

**Twins.** Two panels whose top buckets are identical in every month (equal ``picks_hash``) are
one experiment run twice. The correction counts the pick set **once**, carried by the panel
recorded first (``panel_signals.created``, ties broken by id); every later one reads as a twin of
it, never clears in its own name, and shows its first's q-value. Without this, re-recording one
idea under ten names would buy ten tickets in the correction, and replaying a family of methods
that pick the same names would dilute every other signal's q-value with copies.

**Why Student's t, and why here.** ``fm_t`` is the t-statistic of a mean of ``months`` monthly
slopes, so its null distribution is Student's t on ``months - 1`` degrees of freedom. The lab
declares no scipy (invariant 8: no new runtime dependency), so the tail is the regularised
incomplete beta function evaluated by its continued fraction -- about thirty lines, checked
against scipy in the tests where scipy happens to be installed.

``RULE_ID`` names the panel rule whose readings are judged together; readings under any other
rule are ignored, because a correction across two different measurements is not a correction.
It must equal ``panel.RULE_ID`` (phase 1).

The reasons are sentences the owner reads on ``/sera/signals``: plain words, no ids, no numbers.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from seer_engine.lab import store

RULE_ID = "panel-v1"
FDR = 0.10

WHOLE = "all"
RECENT = "2009-2015"

UNMEASURED_REASON = "it has not been measured on the current price history"
TWIN_REASON = (
    "it picks exactly the same stocks every month as an earlier signal, so it is counted once, "
    "as that one"
)
SLOPE_REASON = (
    "once momentum, market sensitivity, size and volatility are allowed for, the stocks it ranks "
    "highest did no better than the rest"
)
CHANCE_REASON = "its edge is no bigger than luck produces when this many ideas have been tried"
# A missing era row means phase 1 measured fewer than ``panel.MIN_ERA_MONTHS`` (12) months there,
# or never measured that store: either way the condition fails, in words (reconciled, Decisions).
RECENT_MISSING_REASON = "there are not enough months from 2009 to 2015 to say whether it worked then"
RECENT_REASON = "its top picks did not beat the rest of the index from 2009 to 2015"
SURVIVORSHIP_MISSING_REASON = (
    "it has not been measured over enough months with the companies that later disappeared put back"
)
SURVIVORSHIP_REASON = "with the companies that later disappeared put back, its edge goes away"

_MAX_ITER = 10_000
_TINY = 1e-300


@dataclass(frozen=True)
class Verdict:
    """One recorded panel, judged against every other one as the lab stands now.

    ``q`` is the Benjamini-Hochberg q-value of its pick set (a twin shows its first's), None when
    it has no whole-window reading on the dev store being judged. ``reasons`` names every failed
    condition in plain words and is empty exactly when ``clears``. ``twin_of`` is the id of the
    earlier panel with the identical pick set, or None.
    """

    signal_id: str
    clears: bool
    q: float | None
    reasons: tuple[str, ...]
    twin_of: str | None


@dataclass(frozen=True)
class Readings:
    """One panel's rows by era: on the dev store being judged, and on the newest survivorship
    store it was measured on. An era with no row is absent from its mapping."""

    dev: Mapping[str, Mapping[str, Any]]
    survivorship: Mapping[str, Mapping[str, Any]]


def _beta_fraction(a: float, b: float, x: float) -> float:
    """The continued fraction of the incomplete beta function (modified Lentz)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > _TINY else _TINY)
    h = d
    for m in range(1, _MAX_ITER + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _regularized_beta(a: float, b: float, x: float) -> float:
    """I_x(a, b), the regularised incomplete beta function, for a, b > 0."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_fraction(a, b, x) / a
    return 1.0 - front * _beta_fraction(b, a, 1.0 - x) / b


def one_sided_p(t: float, months: int) -> float:
    """P(T > t) for Student's t on ``months - 1`` degrees of freedom: the chance of a slope at
    least this far above zero if the signal does nothing.

    1.0 -- never significant -- when there are fewer than two months (no spread to divide by) or
    the statistic is not finite.
    """
    df = int(months) - 1
    t = float(t)
    if df < 1 or not math.isfinite(t):
        return 1.0
    tail = 0.5 * _regularized_beta(0.5 * df, 0.5, df / (df + t * t))
    return tail if t > 0 else 1.0 - tail


def bh_qvalues(pvalues: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg q-values, in the input's order, capped at 1.

    The q-value of the k-th smallest of m p-values is the smallest ``p_(j) * m / j`` over every
    j >= k: the lowest false-discovery rate at which that hypothesis would still be rejected.
    """
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: (float(pvalues[i]), i))
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, float(pvalues[i]) * m / rank)
        q[i] = running
    return q


def current_dev_fingerprint(conn: sqlite3.Connection) -> str | None:
    """The dev store the newest dev reading under ``RULE_ID`` was taken on, or None.

    What "the current dev store" means to a reader that has not loaded one -- the snapshot and
    ``lab panel-map``. A caller that has loaded the store passes its fingerprint to ``published``
    instead, and that wins.
    """
    newest: str | None = None
    for r in store.panel_results(conn):  # oldest first: the last match is the newest
        if r["store_role"] == "dev" and r["rule_id"] == RULE_ID:
            newest = str(r["store_fingerprint"])
    return newest


def readings(
    conn: sqlite3.Connection, *, dev_fingerprint: str | None = None
) -> dict[str, Readings]:
    """Every recorded panel's rows under ``RULE_ID``, by era, keyed by signal id.

    ``dev`` holds the rows on ``dev_fingerprint`` (``current_dev_fingerprint`` when None);
    ``survivorship`` holds the rows on the newest survivorship store that panel was measured on.
    Empty when the tables are absent.
    """
    fp = dev_fingerprint if dev_fingerprint is not None else current_dev_fingerprint(conn)
    dev: dict[str, dict[str, Mapping[str, Any]]] = {}
    sv_rows: dict[str, list[Mapping[str, Any]]] = {}
    for r in store.panel_results(conn):
        if r["rule_id"] != RULE_ID:
            continue
        sid = str(r["signal_id"])
        if r["store_role"] == "dev":
            if fp is not None and str(r["store_fingerprint"]) == fp:
                dev.setdefault(sid, {})[str(r["era"])] = r
        else:
            sv_rows.setdefault(sid, []).append(r)
    out: dict[str, Readings] = {}
    for s in store.panel_signals(conn):
        sid = str(s["id"])
        rows = sv_rows.get(sid, [])
        newest_fp = str(rows[-1]["store_fingerprint"]) if rows else None
        sv = {str(r["era"]): r for r in rows if str(r["store_fingerprint"]) == newest_fp}
        out[sid] = Readings(dev=dev.get(sid, {}), survivorship=sv)
    return out


def published(
    conn: sqlite3.Connection, *, dev_fingerprint: str | None = None
) -> dict[str, Verdict]:
    """Every recorded panel's verdict, keyed by signal id, judged on ``dev_fingerprint``
    (``current_dev_fingerprint`` when None). Empty when no panel is recorded or the tables are
    absent. See the module docstring for the three conditions and the twin rule.
    """
    signals = store.panel_signals(conn)
    if not signals:
        return {}
    fp = dev_fingerprint if dev_fingerprint is not None else current_dev_fingerprint(conn)
    reads = readings(conn, dev_fingerprint=fp)

    first_of_picks: dict[str, str] = {}
    twin_of: dict[str, str] = {}
    pvalue: dict[str, float] = {}  # one entry per distinct pick set, keyed by its first panel
    for s in sorted(signals, key=lambda s: (str(s["created"]), str(s["id"]))):
        sid = str(s["id"])
        whole = reads[sid].dev.get(WHOLE)
        if whole is None:
            continue
        picks = str(whole["picks_hash"])
        if picks in first_of_picks:
            twin_of[sid] = first_of_picks[picks]
            continue
        first_of_picks[picks] = sid
        pvalue[sid] = one_sided_p(float(whole["fm_t"]), int(whole["months"]))
    firsts = list(pvalue)
    q_of = dict(zip(firsts, bh_qvalues([pvalue[f] for f in firsts])))

    out: dict[str, Verdict] = {}
    for s in signals:
        sid = str(s["id"])
        r = reads[sid]
        whole = r.dev.get(WHOLE)
        if whole is None:
            out[sid] = Verdict(sid, False, None, (UNMEASURED_REASON,), None)
            continue
        if sid in twin_of:
            first = twin_of[sid]
            out[sid] = Verdict(sid, False, q_of[first], (TWIN_REASON,), first)
            continue
        q = q_of[sid]
        reasons: list[str] = []
        if not float(whole["fm_slope"]) > 0:
            reasons.append(SLOPE_REASON)
        elif q > FDR:
            reasons.append(CHANCE_REASON)
        recent = r.dev.get(RECENT)
        if recent is None:
            reasons.append(RECENT_MISSING_REASON)
        elif not float(recent["spread_top"]) > 0:
            reasons.append(RECENT_REASON)
        sv_whole = r.survivorship.get(WHOLE)
        if sv_whole is None:
            reasons.append(SURVIVORSHIP_MISSING_REASON)
        elif not float(sv_whole["fm_slope"]) > 0:
            reasons.append(SURVIVORSHIP_REASON)
        out[sid] = Verdict(sid, not reasons, q, tuple(reasons), None)
    return out
```
**Impact:** this is a new module. It imports `store` at module level, and `store` imports it only inside `_snapshot_panel` (Step 8), so there is no import cycle at load. The p-value code was checked against `scipy.stats.t.sf` during planning over df in {1, 2, 5, 10, 30, 199, 1000} and t in [-3, 8]. The worst relative error was 5.1e-13.

### Step 7: Snapshot version 9
**File:** `engine/src/seer_engine/lab/store.py:3895-3898`
**Change:** replace these three lines
```python
# confusion the method page must never make. Both fields are null when their table is absent or
# holds no row for the trial, which was every trial the committed lab held when this version shipped.
SNAPSHOT_VERSION = 8
```
with
```python
# confusion the method page must never make. Both fields are null when their table is absent or
# holds no row for the trial, which was every trial the committed lab held when this version shipped.
#
# 9 adds ``panel``, the last top-level key: stage one of the lab, every signal and replayed arm
# measured on the stock-by-month panel (``panel_signals`` / ``panel_results``), each with its
# readings by store and era and the verdict ``panel_verdict.published`` works out at export time
# -- whether it clears, its q-value in the false-discovery correction, the plain-words reasons it
# does not, and the earlier panel it is a twin of. The verdict is derived here and never stored,
# for the reason ``books`` is: the correction reads the whole population and moves with every panel
# recorded, and a React component may not run it. ``2009-2015`` is published as ``recent``, a key
# the web can name. Empty ``signals`` when the tables are absent or hold no row, which was the
# committed lab when this version shipped.
SNAPSHOT_VERSION = 9
```

### Step 8: Publish the `panel` key
**File:** `engine/src/seer_engine/lab/store.py`

(a) `:4171-4175`, the `snapshot` docstring. Replace
```python
    a database that has not been migrated -- the tables added since, ``trial_funding``,
    ``trial_roles`` and ``trial_yardstick``, are reached only through ``funding_of``,
    ``role_of_trial`` and ``yardstick_of``, each of which answers None when its table does not
    exist. Gate and data
```
with
```python
    a database that has not been migrated -- the tables added since, ``trial_funding``,
    ``trial_roles`` and ``trial_yardstick``, are reached only through ``funding_of``,
    ``role_of_trial`` and ``yardstick_of``, each of which answers None when its table does not
    exist, and ``panel_signals`` / ``panel_results`` only through ``panel_signals``,
    ``panel_results`` and ``panel_verdict`` (which reads through them), which answer empty. Gate and data
```

(b) `:4318-4324`, the end of the returned dict. Replace
```python
            for sid, p in sorted(roster.LAB_PROVENANCE.items())
            if sid in {e.id for e in roster.active()}
        ],
    }
```
with
```python
            for sid, p in sorted(roster.LAB_PROVENANCE.items())
            if sid in {e.id for e in roster.active()}
        ],
        # Snapshot 9: stage one of the lab. Readings as recorded, verdicts as judged now.
        "panel": _snapshot_panel(conn),
    }
```

(c) After `_snapshot_books` (ends `:4360` with `return {"firing": block(firing), "testLooks": block(looks)}`), insert:
```python


#: The panel's era names as the web reads them. ``2009-2015`` is not a name a reader can write as
#: ``x.y``, so it is published as ``recent``; the order is ``PANEL_ERAS``'.
_PANEL_ERA_KEYS: tuple[tuple[str, str], ...] = tuple(zip(PANEL_ERAS, ("all", "pre2009", "recent")))


def _snapshot_panel_era(r: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """One ``panel_results`` row as the web reads it, or None when that era has no row."""
    if r is None:
        return None
    return {
        "months": int(r["months"]),
        "ic": _num(r["ic_mean"]),
        "icT": _num(r["ic_t"]),
        "spread": _num(r["spread_top"]),
        "spreadT": _num(r["spread_t"]),
        "slope": _num(r["fm_slope"]),
        "slopeT": _num(r["fm_t"]),
        "turnover": _num(r["top_turnover"]),
    }


def _snapshot_panel_store(eras: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    """One store's readings by era, or None when the panel was never measured on that store."""
    if not eras:
        return None
    return {key: _snapshot_panel_era(eras.get(era)) for era, key in _PANEL_ERA_KEYS}


def _snapshot_panel(conn: sqlite3.Connection) -> dict[str, Any]:
    """The ``panel`` block: the rule, the false-discovery rate, and every recorded panel.

    One dev store is resolved once (``panel_verdict.current_dev_fingerprint``) and handed to both
    the readings and the verdicts, so a row's numbers and its verdict always describe the same
    store. Signals are ranked by their dev whole-window controlled slope, highest first, as
    ``lab panel-map`` ranks them; a panel not measured on that store goes last; ties go by id, so
    the export stays deterministic. Empty ``signals`` when the tables are absent or hold no row.
    """
    from seer_engine.lab import panel_verdict as _pv

    fp = _pv.current_dev_fingerprint(conn)
    reads = _pv.readings(conn, dev_fingerprint=fp)
    verdicts = _pv.published(conn, dev_fingerprint=fp)
    rows: list[dict[str, Any]] = []
    for s in panel_signals(conn):
        sid = str(s["id"])
        v = verdicts[sid]
        r = reads[sid]
        rows.append({
            "id": sid,
            "kind": s["kind"],
            "name": s["name"],
            "family": s["family"],
            "methodId": s["method_id"],
            "clears": v.clears,
            "q": _num(v.q),
            "reasons": list(v.reasons),
            "twinOf": v.twin_of,
            "dev": _snapshot_panel_store(r.dev),
            "survivorship": _snapshot_panel_store(r.survivorship),
        })

    def rank(row: Mapping[str, Any]) -> tuple[bool, float, str]:
        whole = (row["dev"] or {}).get("all")
        slope = None if whole is None else whole["slope"]
        return (slope is None, -(slope or 0.0), str(row["id"]))

    rows.sort(key=rank)
    return {"rule": _pv.RULE_ID, "fdr": _pv.FDR, "signals": rows}
```
**Impact:** every export now ends with `"panel":{"rule":"panel-v1","fdr":0.1,"signals":[...]}`. On a database with no panel tables, or tables with no rows, the block is byte-identical: both read as empty. So `test_the_v6_to_v7_migration_moves_not_one_byte_of_the_web_snapshot` (`test_lab_snapshot.py:648`) and the v1 read-only test still hold. The committed-snapshot test (`:1346`) fails until Step 9 regenerates the JSON.

### Step 9: Regenerate `web/data/lab.json` inside the worktree. `lab/lab.sqlite` stays byte-identical.
**Files:** `web/data/lab.json` (regenerated), `lab/lab.sqlite` (restored by path)
**Change:** export with the new code. The command cannot reach `/home/miftah/seer`, for three independent reasons, each verified from the code:
1. `PYTHONPATH=$W/engine/src` makes `config.REPO_ROOT` (`config.py:17`, `Path(__file__).parents[3]`) the worktree. `store.COMMITTED_DB` and `store.DB_PATH` (`store.py:121-124`) therefore point at `$W/lab/lab.sqlite`. This was measured during planning: the import printed `/home/miftah/.worktrees/seer/sera-signal-panel/lab/lab.sqlite` for both.
2. `--db $W/lab/lab.sqlite` is explicit. `commands/lab.py:1141` connects to `args.db`, and `_export_json` (`:4764`) writes `args.out` when given, otherwise `store.snapshot_path(args.db)`, which is `<db>/../../web/data/lab.json`.
3. `--out $W/web/data/lab.json` is explicit.

`lab stage` is **never** used. It runs `git add` with `cwd` set to the DB's parent, and from a worktree with the shared `SEER_LAB_DB` it stages the main checkout.
**Code:**
```bash
W=/home/miftah/.worktrees/seer/sera-signal-panel
cd "$W"
git -C /home/miftah/seer status --porcelain -- lab web/data          # record: expect empty
sha256sum /home/miftah/seer/lab/lab.sqlite "$W/lab/lab.sqlite"       # record both
SEER_LAB_DB="$W/lab/lab.sqlite" SEER_ENV_FILE="$W/.no-env" PYTHONPATH="$W/engine/src" \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --db "$W/lab/lab.sqlite" \
  export-json --out "$W/web/data/lab.json"
# The export's store.connect added the two empty panel tables to the DB. Put the file back by
# path: the JSON is the same bytes either way (an absent table and an empty one both publish
# "signals":[]), and test_the_committed_snapshot_is_the_export_of_the_committed_database proves it.
git -C "$W" checkout -- lab/lab.sqlite
sha256sum /home/miftah/seer/lab/lab.sqlite "$W/lab/lab.sqlite"       # both equal to the recorded values
git -C /home/miftah/seer status --porcelain -- lab web/data          # still empty
git -C "$W" status --porcelain -- lab web/data                       # only " M web/data/lab.json"
```
**Why the DB is restored rather than committed with empty tables (reconciled, Decisions):** the snapshot does not need the tables, so a phase-2 branch that carries the binary DB adds merge risk and nothing else (memory: *Lab commands migrate lab.sqlite on connect*; *Landing a binary lab.sqlite conflict*). The `git checkout` line stays. The tables arrive on `main` at landing, when invariant 7's export connects to `main`'s DB. The JSON bytes are identical either way.
**Impact:** the only regenerated file is `web/data/lab.json`. Its diff is `"version":8` -> `"version":9` and a trailing `,"panel":{"rule":"panel-v1","fdr":0.1,"signals":[]}` before the closing brace.

### Step 10: Engine test pins
**File:** `engine/tests/test_lab_snapshot.py:671-673`. Replace
```python
    # 7 when this was written; 8 since the random-twin fields (an additive change to the trials,
    # not to this migration). The claim above is about the migration, and still holds.
    assert store.SNAPSHOT_VERSION == 8
```
with
```python
    # 7 when this was written; 8 since the random-twin fields (an additive change to the trials,
    # not to this migration); 9 since the signal panel's ``panel`` key, another additive change.
    # The claim above is about the migration, and still holds.
    assert store.SNAPSHOT_VERSION == 9
```
**File:** `engine/tests/test_lab_snapshot.py:945-947`. Replace
```python
    assert list(s) == ["version", "asOf", "gate", "data", "summary", "benchmark", "books",
                       "methods", "trials", "insights", "ideasSeen", "paper"]
    assert s["version"] == 8
```
with
```python
    assert list(s) == ["version", "asOf", "gate", "data", "summary", "benchmark", "books",
                       "methods", "trials", "insights", "ideasSeen", "paper", "panel"]
    assert s["version"] == 9
```
**File:** `engine/tests/test_lab_books.py:315`. Replace
```python
    assert snap["version"] == 8  # 7 when books arrived; 8 added role and yardstick per trial
```
with
```python
    assert snap["version"] == 9  # 7 when books arrived; 8 added role and yardstick; 9 the panel
```
**File:** `engine/tests/test_lab_gate_wording.py`. Insert after the end of `test_the_web_mirrors_the_engines_arm_roles_and_reading_statuses` (`:324`, the line `    }` closing the YARDSTICK set), before the `# ---...--- the lab journal's newest note` banner:
```python


def test_the_web_mirrors_the_engines_panel_kinds() -> None:
    """The kinds of panel row snapshot 9 publishes, as typed in ``web/lib/sera/types.ts``."""
    rel = "web/lib/sera/types.ts"
    src = (config.REPO_ROOT / rel).read_text(encoding="utf-8")
    assert _ts_string_list(src, "PANEL_KINDS", rel) == set(store.PANEL_KINDS)
```
**Impact:** with Steps 7-9, these pins pass. The gate-wording pin goes red until Step 12 adds `PANEL_KINDS` to `types.ts`, so land Steps 10 and 12 together.

### Step 11: `engine/tests/test_lab_panel_record.py`
**File:** `engine/tests/test_lab_panel_record.py` (new)
**Code:**
```python
"""The panel record (SERA_SIGNAL_PANEL_PLAN.md phase 2): two append-only tables, the verdict
worked out from them on read, and the ``panel`` key the web reads.

Every test builds its own temp lab, and nothing here loads a research store or runs a panel. The
rows are written by hand with the numbers each test needs, because what is under test is what
the lab does with a reading once it has one -- keep it once, judge it against every other
reading, publish it -- and not how the reading was taken (phase 1's ``test_lab_panel.py``).
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import replace
from types import SimpleNamespace

import pytest

from seer_engine.lab import panel_verdict, store

DEV_FP = "dev-fp"
SV_FP = "sv-fp"


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _signal(conn, sid, *, second, sha="a" * 64):
    row = store.PanelSignalRow(
        id=sid, kind="signal", name=f"ranks on idea {second}", family="test-family",
        hypothesis="h", expected_failure="f", source_kind="knowledge", source_ref="",
        method_id=None, source_sha=sha, created=f"2026-11-13T00:00:{second:02d}+00:00",
    )
    with conn:
        return store.insert_panel_signal(conn, row)


def _rows(sid, *, role="dev", fp=DEV_FP, t=4.0, slope=0.004, recent_spread=0.03, picks=None,
          ic=True, eras=store.PANEL_ERAS, measured="2026-11-13T01:00:00+00:00"):
    return [
        store.PanelResultRow(
            signal_id=sid, rule_id=panel_verdict.RULE_ID, store_role=role, store_fingerprint=fp,
            era=era, months=200 if era == "all" else 100, mean_pool=480.0, mean_scored=470.0,
            ic_mean=0.02 if ic else None, ic_t=t if ic else None,
            spread_top=recent_spread if era == "2009-2015" else 0.03, spread_t=t,
            fm_slope=slope, fm_t=t, top_turnover=0.3, picks_hash=picks or f"picks-{sid}",
            git_sha="abc", measured=measured,
        )
        for era in eras
    ]


def _panel(conn, sid, *, second, sv_slope=0.003, picks=None, **dev):
    """A signal with a dev reading on DEV_FP and a whole-window survivorship reading on SV_FP."""
    _signal(conn, sid, second=second)
    with conn:
        store.insert_panel_results(conn, _rows(sid, picks=picks, **dev))
        store.insert_panel_results(conn, _rows(
            sid, role="survivorship", fp=SV_FP, slope=sv_slope, picks=picks, eras=("all",),
        ))


def _recorded_arm(conn, mid="M0614", cid="M0614-V1"):
    with conn:
        store.add_method(conn, id=mid, name="n", family="stock-momentum",
                         source_kind="knowledge", hypothesis="h", status="registered")
        store.insert_trials(conn, [store.TrialRow(
            method_id=mid, candidate_id=cid, config_digest=f"d-{cid}", config_text="t",
            rules_id="MONTHLY_HOLD", allocator_id="X", window="dev", start="1996-01-02",
            end="2015-10-16", store_fingerprint="fp", git_sha="abc",
            run_at="2026-10-06T00:00:00+00:00", total_return=1.0, cagr=0.1, max_drawdown=0.2,
            profit_factor=1.5, trades=200, sharpe=0.8, exposure=0.9, turnover=1.0,
            worst_year=2008, worst_year_return=-0.2, spy_tr_return=1.0, spy_tr_cagr=0.08,
            mar=0.5, failed="", eligible=True, dsr=0.95, n_trials_at_run=10, curve_json="[]",
        )])


# ------------------------------------------------------------------------------- the record


def test_connect_creates_both_tables_and_neither_lets_a_row_change(conn):
    _panel(conn, "S0001", second=1)
    for sql in ("UPDATE panel_signals SET name = 'x'", "DELETE FROM panel_signals",
                "UPDATE panel_results SET fm_t = 0", "DELETE FROM panel_results"):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            with conn:
                conn.execute(sql)
    assert [s["id"] for s in store.panel_signals(conn)] == ["S0001"]
    assert len(store.panel_results(conn)) == 4


def test_a_signal_records_once_and_a_repeat_from_the_same_file_writes_nothing(conn):
    assert _signal(conn, "S0001", second=1) is True
    assert _signal(conn, "S0001", second=2) is False
    assert [(s["id"], s["created"]) for s in store.panel_signals(conn)] == [
        ("S0001", "2026-11-13T00:00:01+00:00")]


def test_a_signal_id_already_recorded_from_another_file_is_refused(conn):
    _signal(conn, "S0001", second=1)
    with pytest.raises(store.LabError, match="different file"):
        _signal(conn, "S0001", second=2, sha="b" * 64)


@pytest.mark.parametrize("over, match", [
    (dict(id="M0001-A"), "S followed by four digits"),
    (dict(id="S12"), "S followed by four digits"),
    (dict(method_id="M0001"), "only a replay"),
    (dict(kind="book"), "kind must be one of"),
    (dict(name="  "), "name is empty"),
    (dict(source_kind="tweet"), "source_kind"),
])
def test_a_malformed_signal_row_is_refused_before_anything_is_written(conn, over, match):
    base = dict(id="S0001", kind="signal", name="n", family="f", hypothesis="h",
                expected_failure="e", source_kind="knowledge", source_ref="", method_id=None,
                source_sha="a" * 64, created="2026-11-13T00:00:00+00:00")
    base.update(over)
    with pytest.raises(store.LabError, match=match):
        with conn:
            store.insert_panel_signal(conn, store.PanelSignalRow(**base))
    assert store.panel_signals(conn) == []


def test_a_replay_is_a_recorded_dev_arm_of_its_method_and_has_no_rank_correlation(conn):
    _recorded_arm(conn)
    common = dict(kind="replay", name="the arm's own picks", family="stock-momentum",
                  hypothesis="h", expected_failure="e", source_kind="variation", source_ref="",
                  source_sha="c" * 64, created="2026-11-13T00:00:00+00:00")
    for sid, mid, match in (("M0614-V9", "M0614", "no dev trial"),
                            ("M0614-V1", None, "names no method"),
                            ("M0615-V1", "M0614", "not an arm of M0614")):
        with pytest.raises(store.LabError, match=match):
            with conn:
                store.insert_panel_signal(conn, store.PanelSignalRow(id=sid, method_id=mid, **common))
    with conn:
        assert store.insert_panel_signal(
            conn, store.PanelSignalRow(id="M0614-V1", method_id="M0614", **common))
    with pytest.raises(store.LabError, match="no score to rank"):
        with conn:
            store.insert_panel_results(conn, _rows("M0614-V1"))
    with conn:
        assert store.insert_panel_results(conn, _rows("M0614-V1", ic=False)) == 3
    assert store.panel_signals(conn)[0]["method_id"] == "M0614"
    assert store.next_signal_id(conn) == "S0001"  # a replay never consumes a signal number


def test_readings_record_once_per_era_and_store_and_a_rerun_records_nothing(conn):
    _signal(conn, "S0001", second=1)
    assert not store.has_panel(conn, "S0001", panel_verdict.RULE_ID, DEV_FP)
    with conn:
        assert store.insert_panel_results(conn, _rows("S0001")) == 3
    assert store.has_panel(conn, "S0001", panel_verdict.RULE_ID, DEV_FP)
    assert not store.has_panel(conn, "S0001", panel_verdict.RULE_ID, SV_FP)
    with conn:
        assert store.insert_panel_results(conn, _rows("S0001", t=9.0)) == 0
    assert {r["fm_t"] for r in store.panel_results(conn, "S0001")} == {4.0}
    with conn:
        assert store.insert_panel_results(conn, _rows("S0001", role="survivorship", fp=SV_FP)) == 3
    assert len(store.panel_results(conn)) == 6
    assert store.panel_results(conn, "S0002") == []


@pytest.mark.parametrize("over, match", [
    (dict(fm_t=math.nan), "finite"),
    (dict(spread_top=math.inf), "finite"),
    (dict(ic_t=None), "together"),
    (dict(era="2016"), "era must be one of"),
    (dict(store_role="test"), "store_role"),
    (dict(months=0), "no month"),
    (dict(top_turnover=1.5), "top_turnover"),
    (dict(picks_hash=""), "picks_hash is empty"),
    (dict(signal_id="S0009"), "record the signal"),
])
def test_a_row_that_cannot_be_a_reading_is_refused_and_nothing_is_written(conn, over, match):
    _signal(conn, "S0001", second=1)
    with pytest.raises(store.LabError, match=match):
        with conn:
            store.insert_panel_results(conn, [replace(_rows("S0001")[0], **over)])
    assert store.panel_results(conn) == []


def test_one_store_keeps_one_role_and_one_reading_keeps_one_pick_set(conn):
    _signal(conn, "S0001", second=1)
    _signal(conn, "S0002", second=2)
    with conn:
        store.insert_panel_results(conn, _rows("S0001"))
    with pytest.raises(store.LabError, match="the dev store"):
        with conn:
            store.insert_panel_results(conn, _rows("S0002", role="survivorship", fp=DEV_FP))
    mixed = _rows("S0002")[:2] + _rows("S0002", picks="other")[2:]
    with pytest.raises(store.LabError, match="pick set"):
        with conn:
            store.insert_panel_results(conn, mixed)
    assert store.panel_results(conn, "S0002") == []


def test_the_next_signal_id_is_one_above_every_recorded_and_every_named_id(conn):
    assert store.next_signal_id(conn) == "S0001"
    _signal(conn, "S0004", second=1)
    assert store.next_signal_id(conn) == "S0005"
    assert store.next_signal_id(conn, taken=["S0002", "S0007", "M0614-V1", "notes"]) == "S0008"


def test_a_row_is_built_from_a_panel_reading_by_field_name():
    stats = SimpleNamespace(era="2009-2015", months=82, mean_pool=455.5, mean_scored=440.0,
                            ic_mean=None, ic_t=None, spread_top=0.04, spread_t=2.1,
                            fm_slope=0.003, fm_t=2.5, top_turnover=0.25)
    row = store.PanelResultRow.from_era(
        stats, signal_id="S0001", rule_id="panel-v1", store_role="dev", store_fingerprint="fp",
        picks_hash="h", git_sha="g", measured="m",
    )
    assert (row.era, row.months, row.ic_mean, row.ic_t, row.fm_t) == ("2009-2015", 82, None, None, 2.5)


def test_without_the_panel_tables_every_reader_answers_empty_and_the_snapshot_has_no_signals(
    conn, tmp_path,
):
    """R6.3. Parallel sessions run older checkouts against the shared database, and the committed
    ``lab/lab.sqlite`` itself has no panel table until a lab command connects to it on ``main``.
    An absent table and an empty one must publish the same bytes."""
    with_tables = store.snapshot_json(conn)
    _panel(conn, "S0001", second=1)
    old = tmp_path / "old.sqlite"
    dst = sqlite3.connect(old)
    conn.backup(dst)
    dst.execute("DROP TABLE panel_results")
    dst.execute("DROP TABLE panel_signals")
    dst.commit()
    dst.close()
    ro = store.connect_readonly(old)
    try:
        assert store.panel_signals(ro) == [] and store.panel_results(ro) == []
        assert not store.has_panel(ro, "S0001", panel_verdict.RULE_ID, DEV_FP)
        assert store.next_signal_id(ro) == "S0001"
        assert panel_verdict.current_dev_fingerprint(ro) is None
        assert panel_verdict.published(ro) == {}
        snap = store.snapshot(ro)
    finally:
        ro.close()
    assert list(snap)[-1] == "panel"
    assert snap["panel"] == {"rule": "panel-v1", "fdr": 0.1, "signals": []}
    assert json.loads(with_tables)["panel"] == snap["panel"]


# ------------------------------------------------------------------------------- the verdict


@pytest.mark.parametrize("t, months, p", [
    (2.0, 11, 0.036694), (2.228139, 11, 0.025), (1.812461, 11, 0.05),
    (0.0, 11, 0.5), (-2.0, 11, 1 - 0.036694), (12.706205, 2, 0.025),
])
def test_the_one_sided_p_value_is_students_t_on_months_minus_one(t, months, p):
    assert panel_verdict.one_sided_p(t, months) == pytest.approx(p, abs=2e-6)


def test_a_reading_too_short_or_broken_is_never_significant():
    assert panel_verdict.one_sided_p(5.0, 1) == 1.0
    assert panel_verdict.one_sided_p(math.nan, 200) == 1.0


def test_the_p_value_agrees_with_scipy_where_scipy_is_installed():
    stats = pytest.importorskip("scipy.stats")
    for df in (1, 2, 5, 10, 30, 199, 1000):
        for t in (-3.0, -1.0, 0.0, 0.5, 1.5, 2.0, 3.0, 5.0, 8.0):
            assert panel_verdict.one_sided_p(t, df + 1) == pytest.approx(
                float(stats.t.sf(t, df)), rel=1e-8, abs=1e-12)


def test_benjamini_hochberg_q_values_come_back_in_input_order():
    assert panel_verdict.bh_qvalues([]) == []
    assert panel_verdict.bh_qvalues([0.01, 0.04, 0.03, 0.005]) == pytest.approx(
        [0.02, 0.04, 0.04, 0.02])
    assert panel_verdict.bh_qvalues([0.9, 0.95]) == pytest.approx([0.95, 0.95])


def test_a_panel_clears_only_when_all_three_readings_agree(conn):
    _panel(conn, "S0001", second=1)                                  # strong everywhere
    _panel(conn, "S0002", second=2, slope=-0.004, t=-4.0)            # wrong sign after controls
    _panel(conn, "S0003", second=3, recent_spread=-0.01)             # nothing since 2009
    _panel(conn, "S0004", second=4, sv_slope=-0.001)                 # the dead erase it
    _panel(conn, "S0005", second=5, eras=("all", "pre2009"))         # no 2009-2015 months
    _signal(conn, "S0006", second=6)
    with conn:
        store.insert_panel_results(conn, _rows("S0006"))             # never run with the dead
    v = panel_verdict.published(conn)
    assert v["S0001"].clears and v["S0001"].reasons == () and v["S0001"].twin_of is None
    assert v["S0001"].q < panel_verdict.FDR
    assert v["S0002"].reasons == (panel_verdict.SLOPE_REASON,)
    assert v["S0003"].reasons == (panel_verdict.RECENT_REASON,)
    assert v["S0004"].reasons == (panel_verdict.SURVIVORSHIP_REASON,)
    assert v["S0005"].reasons == (panel_verdict.RECENT_MISSING_REASON,)
    assert v["S0006"].reasons == (panel_verdict.SURVIVORSHIP_MISSING_REASON,)
    assert not any(v[s].clears for s in ("S0002", "S0003", "S0004", "S0005", "S0006"))
    # Text the owner reads: no ids, digests or code.
    for verdict in v.values():
        for reason in verdict.reasons:
            assert not re.search(r"\b[SM]\d{4}\b|[0-9a-f]{12}|_", reason), reason


def test_identical_pick_sets_count_once_and_every_later_one_is_a_twin_of_the_first(conn):
    """R3.2. Thirty re-recordings of one modest edge buy it no extra tickets: it is judged as
    one panel, and so it still clears."""
    _panel(conn, "S0001", second=1, t=2.2, slope=0.002, picks="same")
    for i in range(2, 32):
        _panel(conn, f"S{i:04d}", second=i, t=2.2, slope=0.002, picks="same")
    v = panel_verdict.published(conn)
    assert v["S0001"].clears and v["S0001"].twin_of is None
    assert v["S0001"].q == pytest.approx(panel_verdict.one_sided_p(2.2, 200))  # m = 1
    for i in range(2, 32):
        twin = v[f"S{i:04d}"]
        assert (twin.clears, twin.twin_of, twin.reasons) == (
            False, "S0001", (panel_verdict.TWIN_REASON,))
        assert twin.q == v["S0001"].q


def test_the_first_of_a_pick_set_is_the_earliest_recorded_not_the_lowest_id(conn):
    _panel(conn, "S0009", second=1, picks="shared")
    _panel(conn, "S0003", second=2, picks="shared")
    v = panel_verdict.published(conn)
    assert v["S0003"].twin_of == "S0009" and v["S0009"].twin_of is None


def test_distinct_pick_sets_each_count_and_crowd_out_a_modest_edge(conn):
    """R2.3. The same modest edge, beside thirty distinct nulls, is no longer distinguishable
    from luck: the correction runs across every distinct recorded panel."""
    _panel(conn, "S0001", second=1, t=2.2, slope=0.002)
    assert panel_verdict.published(conn)["S0001"].clears
    for i in range(2, 32):
        _panel(conn, f"S{i:04d}", second=i, t=0.0, slope=0.0)
    v = panel_verdict.published(conn)
    assert not v["S0001"].clears
    assert v["S0001"].reasons == (panel_verdict.CHANCE_REASON,)
    assert v["S0001"].q == pytest.approx(panel_verdict.one_sided_p(2.2, 200) * 31)


def test_the_verdict_reads_the_newest_dev_store_unless_it_is_told_which(conn):
    _panel(conn, "S0001", second=1)
    _signal(conn, "S0002", second=2)
    with conn:
        store.insert_panel_results(
            conn, _rows("S0002", fp="newer-dev", measured="2026-11-14T00:00:00+00:00"))
    assert panel_verdict.current_dev_fingerprint(conn) == "newer-dev"
    v = panel_verdict.published(conn)
    assert v["S0001"].reasons == (panel_verdict.UNMEASURED_REASON,) and v["S0001"].q is None
    assert v["S0002"].reasons == (panel_verdict.SURVIVORSHIP_MISSING_REASON,)
    told = panel_verdict.published(conn, dev_fingerprint=DEV_FP)
    assert told["S0001"].clears
    assert told["S0002"].reasons == (panel_verdict.UNMEASURED_REASON,)


# ------------------------------------------------------------------------------- the snapshot


def test_the_snapshot_publishes_every_panel_ranked_by_slope_with_its_verdict(conn):
    """R6.1: snapshot 9's last key, readings as recorded and verdicts as judged now."""
    _panel(conn, "S0001", second=1, slope=0.001)
    _panel(conn, "S0002", second=2, slope=0.006)
    _panel(conn, "S0003", second=3, slope=0.006, picks="picks-S0002")  # twin of S0002
    _signal(conn, "S0004", second=4)                                    # recorded, never measured
    s = store.snapshot(conn)
    assert s["version"] == store.SNAPSHOT_VERSION == 9
    assert list(s)[-1] == "panel"
    panel = s["panel"]
    assert (panel["rule"], panel["fdr"]) == ("panel-v1", 0.1)
    assert [x["id"] for x in panel["signals"]] == ["S0002", "S0003", "S0001", "S0004"]
    top = panel["signals"][0]
    assert list(top) == ["id", "kind", "name", "family", "methodId", "clears", "q", "reasons",
                         "twinOf", "dev", "survivorship"]
    assert (top["kind"], top["clears"], top["twinOf"], top["methodId"], top["reasons"]) == (
        "signal", True, None, None, [])
    assert list(top["dev"]) == ["all", "pre2009", "recent"]
    assert top["dev"]["all"] == {"months": 200, "ic": 0.02, "icT": 4.0, "spread": 0.03,
                                 "spreadT": 4.0, "slope": 0.006, "slopeT": 4.0, "turnover": 0.3}
    assert top["dev"]["recent"]["months"] == 100
    assert top["survivorship"]["all"]["slope"] == 0.003
    assert top["survivorship"]["recent"] is None
    twin = panel["signals"][1]
    assert (twin["twinOf"], twin["clears"], twin["q"]) == ("S0002", False, top["q"])
    never = panel["signals"][3]
    assert (never["dev"], never["survivorship"], never["q"], never["clears"]) == (
        None, None, None, False)
    json.loads(store.snapshot_json(conn))  # strict JSON
```
**Impact:** this is a new test module. It uses only the public API and `store.snapshot`, and nothing is mocked.

### Step 12: Web types
**File:** `web/lib/sera/types.ts:13-16`. Replace
```ts
   * 8 added each trial's `role` and `yardstick` (its random-twin reading) and the gate's
   *   `yardstickMin` / `yardstickDraws` — the seventh condition, and which arms are comparison books.
   */
  version: 8;
```
with
```ts
   * 8 added each trial's `role` and `yardstick` (its random-twin reading) and the gate's
   *   `yardstickMin` / `yardstickDraws` — the seventh condition, and which arms are comparison books;
   * 9 added `panel` — stage one of the lab: every signal measured on the stock-by-month panel,
   *   with its verdict worked out at export time.
   */
  version: 9;
```
**File:** `web/lib/sera/types.ts:83-84`. Replace
```ts
  books: { firing: LabBook[]; testLooks: LabBook[] };
};
```
(the end of `LabSnapshot`) with
```ts
  books: { firing: LabBook[]; testLooks: LabBook[] };
  /**
   * Stage one of the lab (snapshot 9): every stock-picking idea measured on the stock-by-month
   * panel, best controlled slope first, each with its verdict. Empty until a panel is recorded.
   */
  panel: LabPanel;
};
```
**File:** `web/lib/sera/types.ts:379` (append after the last line, `export const YARDSTICK_STATUSES = …`)
```ts

/** What a panel row is (`lab.store.PANEL_KINDS`): a registered signal, or a replay of an arm the lab already ran. */
export type PanelKind = 'signal' | 'replay';

/** Mirrors `lab.store.PANEL_KINDS`; pinned by `engine/tests/test_lab_gate_wording.py`. */
export const PANEL_KINDS = ['signal', 'replay'] as const satisfies readonly PanelKind[];

/**
 * One era of one panel reading (`store._snapshot_panel_era`). Every rate is a fraction, not a
 * percentage. `ic` / `icT` are null for a replay: an arm's picks are a set with no score to rank.
 */
export type LabPanelEra = {
  /** Months measured. */
  months: number;
  /** Mean monthly rank correlation between the score and next month's return. */
  ic: number | null;
  icT: number | null;
  /** The top bucket's return over the whole pool's, annualised. */
  spread: number;
  spreadT: number;
  /**
   * Next month's return per 1 sd of score (or per pick, for a replay) once momentum, beta, size and
   * volatility are allowed for. MONTHLY, unlike `spread`: a yearly figure is `slope * 12`, and the
   * two are never shown as one unit.
   */
  slope: number;
  slopeT: number;
  /** Mean share of the top bucket replaced each month. */
  turnover: number;
};

/** One store's readings by era; an era with no months is null. `recent` is 2009 to 2015. */
export type LabPanelStore = {
  all: LabPanelEra | null;
  pre2009: LabPanelEra | null;
  recent: LabPanelEra | null;
};

/** One recorded panel and its verdict (`store._snapshot_panel`, `lab.panel_verdict.published`). */
export type LabPanelSignal = {
  /** `S0001` for a signal; the arm's own id for a replay. Never shown to the owner. */
  id: string;
  kind: PanelKind;
  /** What it ranks on, in plain words. */
  name: string;
  family: string;
  /** The method a replay re-reads; null for a signal. */
  methodId: string | null;
  /** Whether it clears stage one. Never true for a twin. */
  clears: boolean;
  /** Its false-discovery q-value across every distinct pick set; null when not measured on the current history. */
  q: number | null;
  /** Each condition it missed, as a plain sentence written by the engine; empty exactly when it clears. */
  reasons: string[];
  /** The earlier panel that picks exactly the same stocks every month, or null. */
  twinOf: string | null;
  /** On the current dev price history; null when not measured there. */
  dev: LabPanelStore | null;
  /** With the companies that later disappeared put back; null when not measured that way. */
  survivorship: LabPanelStore | null;
};

/** The panel block: the rule, the false-discovery rate it is judged at, and every recorded panel. */
export type LabPanel = { rule: string; fdr: number; signals: LabPanelSignal[] };
```
**Impact:** `LabSnapshot.panel` is required. The only hand-built `LabSnapshot` in `web/` is `overview.test.ts`'s `snap()`, which Step 13 updates. `lib/sera/lab.ts` casts the JSON and needs no change. Before writing, read `web/AGENTS.md`. These are type-only edits and touch no Next API.

### Step 13: Web tests
**File:** `web/lib/sera/lab.test.ts:6`. Replace
```ts
import { ARM_ROLES, DSR_POLICIES, INSIGHT_KINDS, METHOD_STATUSES, SOURCE_KINDS, YARDSTICK_STATUSES } from './types';
```
with
```ts
import { ARM_ROLES, DSR_POLICIES, INSIGHT_KINDS, METHOD_STATUSES, PANEL_KINDS, SOURCE_KINDS, YARDSTICK_STATUSES } from './types';
```
**File:** `web/lib/sera/lab.test.ts:10-14`. Replace
```ts
    expect(lab.version).toBe(8);
    expect(Object.keys(lab).sort()).toEqual(
      ['asOf', 'benchmark', 'books', 'data', 'gate', 'ideasSeen', 'insights', 'methods', 'paper',
        'summary', 'trials', 'version'].sort(),
    );
```
with
```ts
    expect(lab.version).toBe(9);
    expect(Object.keys(lab).sort()).toEqual(
      ['asOf', 'benchmark', 'books', 'data', 'gate', 'ideasSeen', 'insights', 'methods', 'panel',
        'paper', 'summary', 'trials', 'version'].sort(),
    );
```
**File:** `web/lib/sera/lab.test.ts`. Insert immediately before the line `  it('collapses the spent looks and the buy signal to distinct strategies', () => {`:
```ts
  it('publishes the panel block in its contract shape, empty or not', () => {
    // Snapshot 9. The committed lab may hold no panel yet, so this reads the shape, never a count.
    expect(lab.panel.rule.length).toBeGreaterThan(0);
    expect(lab.panel.fdr > 0 && lab.panel.fdr < 1).toBe(true);
    expect(Array.isArray(lab.panel.signals)).toBe(true);
    for (const s of lab.panel.signals) {
      expect(PANEL_KINDS).toContain(s.kind);
      expect(s.clears && s.twinOf !== null).toBe(false);
      expect(s.clears).toBe(s.reasons.length === 0);
    }
  });

```
**File:** `web/app/sera/overview.test.ts:104`. Replace `  version: 8,` (inside `const snap = …`) with `  version: 9,`.
**File:** `web/app/sera/overview.test.ts:151`. Replace
```ts
  books: { firing: [], testLooks: [] },
  ...over,
```
with
```ts
  books: { firing: [], testLooks: [] },
  panel: { rule: 'panel-v1', fdr: 0.1, signals: [] },
  ...over,
```
**Impact:** `tsc` is green again. vitest reads the regenerated `web/data/lab.json` (version 9, with `panel`).

### Step 14: The proof drive script
**File:** `.workflows/plan/sera-signal-panel/phase-2-drive.py` (new). This is a lever: the verifier reruns it instead of trusting the diff.
**Code:**
```python
"""Phase 2 proof drive: record panels in a COPY of a lab database, print the published verdicts,
then export the snapshot through the real `lab export-json` CLI and print its `panel` block.

usage: PYTHONPATH=<worktree>/engine/src python phase-2-drive.py SOURCE_DB OUT_DIR --crowd twins|nulls

SOURCE_DB is opened read-only (sqlite backup into OUT_DIR/lab.sqlite) and never written.
--crowd twins  adds 30 panels with S0003's exact pick set: the correction still counts 3 sets.
--crowd nulls  adds 30 distinct do-nothing panels: the correction counts 33 sets.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from seer_engine.lab import panel_verdict, store

DEV_FP, SV_FP = "dev-fp-proof", "sv-fp-proof"


def rows(sid, *, role, fp, t, slope, recent, picks, ic=True):
    return [
        store.PanelResultRow(
            signal_id=sid, rule_id=panel_verdict.RULE_ID, store_role=role, store_fingerprint=fp,
            era=era, months=200 if era == "all" else 100, mean_pool=480.0, mean_scored=470.0,
            ic_mean=0.02 if ic else None, ic_t=t if ic else None,
            spread_top=recent if era == "2009-2015" else 0.03, spread_t=t, fm_slope=slope,
            fm_t=t, top_turnover=0.3, picks_hash=picks, git_sha="proof",
            measured="2026-11-13T00:00:00+00:00",
        )
        for era in store.PANEL_ERAS
    ]


def record(conn, sid, second, *, t, slope, recent, sv_slope, picks, kind="signal",
           method_id=None, source_kind="knowledge"):
    row = store.PanelSignalRow(
        id=sid, kind=kind, name=f"proof idea {second}", family="proof", hypothesis="h",
        expected_failure="f", source_kind=source_kind, source_ref="", method_id=method_id,
        source_sha="0" * 64, created=f"2026-11-13T00:00:{second:02d}+00:00",
    )
    assert store.insert_panel_signal(conn, row)
    ic = kind == "signal"
    store.insert_panel_results(conn, rows(sid, role="dev", fp=DEV_FP, t=t, slope=slope,
                                          recent=recent, picks=picks, ic=ic))
    store.insert_panel_results(conn, rows(sid, role="survivorship", fp=SV_FP, t=t,
                                          slope=sv_slope, recent=recent, picks=picks, ic=ic))
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_db")
    ap.add_argument("out_dir")
    ap.add_argument("--crowd", choices=("twins", "nulls"), required=True)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    db = out / "lab.sqlite"
    db.unlink(missing_ok=True)
    src = sqlite3.connect(f"{Path(args.source_db).resolve().as_uri()}?mode=ro", uri=True)
    dst = sqlite3.connect(db)
    src.backup(dst)
    src.close()
    dst.close()

    conn = store.connect(db)
    arm = conn.execute(
        "SELECT t.candidate_id, t.method_id, m.source_kind FROM trials t "
        "JOIN methods m ON m.id = t.method_id WHERE t.window = 'dev' AND m.family LIKE 'stock-%' "
        "ORDER BY t.n LIMIT 1"
    ).fetchone()
    trials_before = conn.execute("SELECT count(*) FROM trials").fetchone()[0]
    store.begin_immediate(conn)
    first = record(conn, "S0001", 1, t=4.0, slope=0.004, recent=0.03, sv_slope=0.003, picks="A")
    record(conn, "S0002", 2, t=4.0, slope=0.004, recent=0.03, sv_slope=0.003, picks="A")
    record(conn, "S0003", 3, t=2.2, slope=0.002, recent=0.01, sv_slope=0.001, picks="C")
    for i in range(4, 34):
        if args.crowd == "twins":
            record(conn, f"S{i:04d}", i, t=2.2, slope=0.002, recent=0.01, sv_slope=0.001, picks="C")
        else:
            record(conn, f"S{i:04d}", i, t=0.0, slope=0.0, recent=0.0, sv_slope=0.0,
                   picks=f"N{i}")
    record(conn, str(arm["candidate_id"]), 34, t=0.0, slope=0.0, recent=0.0, sv_slope=0.0,
           picks="R", kind="replay", method_id=str(arm["method_id"]),
           source_kind=str(arm["source_kind"]))
    conn.commit()
    print("repeat insert of S0001 ->", store.insert_panel_signal(conn, first))
    print("trials before", trials_before, "after", conn.execute("SELECT count(*) FROM trials").fetchone()[0])
    print("panel_signals", len(store.panel_signals(conn)), "panel_results", len(store.panel_results(conn)))
    for sid, v in panel_verdict.published(conn).items():
        if sid in ("S0001", "S0002", "S0003", "S0004", "S0033") or sid == arm["candidate_id"]:
            q = "-" if v.q is None else f"{v.q:.4f}"
            print(f"{sid} clears={v.clears} q={q} twin_of={v.twin_of} reasons={' | '.join(v.reasons)}")
    conn.close()

    env = dict(os.environ, SEER_LAB_DB=str(db), SEER_ENV_FILE=str(out / "no.env"))
    code = subprocess.run(
        [sys.executable, "-m", "seer_engine", "lab", "--db", str(db), "export-json",
         "--out", str(out / "lab.json")],
        env=env,
    ).returncode
    print("export-json exit", code)
    snap = json.loads((out / "lab.json").read_text(encoding="utf-8"))
    panel = snap["panel"]
    by = {s["id"]: s for s in panel["signals"]}
    rid = str(arm["candidate_id"])
    print("version", snap["version"], "last key", list(snap)[-1])
    print("rule", panel["rule"], "fdr", panel["fdr"], "signals", len(panel["signals"]))
    print("first ranked", panel["signals"][0]["id"], "clears", panel["signals"][0]["clears"])
    print("S0002 twinOf", by["S0002"]["twinOf"], "S0003 clears", by["S0003"]["clears"])
    print("S0001 dev eras", list(by["S0001"]["dev"]))
    print("replay", rid, "kind", by[rid]["kind"], "methodId", by[rid]["methodId"],
          "ic", by[rid]["dev"]["all"]["ic"])
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
```
**Impact:** this script runs only against a copy. The expected numbers were computed during planning with Step 6's p-value code. S0003's one-sided p is 0.014479. With `twins` the correction counts 3 sets, so q is about 0.0217 and S0003 clears. With `nulls` it counts 33 sets, so q is about 0.239 and S0003 fails as chance. S0001's p is 4.46e-5, so it clears in both modes.

## Principles applied

- Make illegal states unrepresentable: the table CHECKs tie `kind` to the id's shape and to `method_id`. A signal that names a method, a replay with no method, and a replay carrying another method's id cannot be stored. `ic_mean`/`ic_t` are NULL together. `era`/`store_role` are closed lists. The insert also refuses one fingerprint under two roles and two pick sets within one reading. Nothing downstream re-checks these.
- Boundary discipline: every validation happens once, in `insert_panel_signal` / `insert_panel_results`, with finite numbers, an IC pair and a recorded dev arm for replays. `panel_verdict.published` and `_snapshot_panel` trust the stored rows and do no re-validation.
- Laziness protocol: `_dicts` gains a `params` argument instead of a new row helper. Phase 2 adds no snapshot builder to `fixture.ts`, because nothing in it would call one. `asOf` is left alone. The p-value is roughly thirty lines of `math` instead of a new scipy dependency. `lab/lab.sqlite` is restored after the export instead of being carried as a binary diff.
- Build the lever: Step 14's drive script records two scenarios in a DB copy and exports through the CLI. The correction's population rule (twins counted once, distinct nulls counted) is rerunnable evidence, not a diff to trust.
- Test behavior, not implementation: the tests go through the public insert, read and verdict API and `store.snapshot`. Nothing is mocked, and `_snapshot_panel` and `_check_panel_result` are never called directly.
- Encode lessons in structure: the web mirrors engine vocabularies, and they have drifted before (memory: *An engine test mirrors the web Overview selector*). `PANEL_KINDS` is therefore pinned web == engine in `test_lab_gate_wording.py` instead of being left to a comment.

## Verification

**Setup (once):**
```bash
W=/home/miftah/.worktrees/seer/sera-signal-panel
[ -d "$W/web/node_modules" ] || cp -al /home/miftah/seer/web/node_modules "$W/web/node_modules"   # hardlink, never symlink
docker start seer-pg >/dev/null 2>&1 || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
```
**Build:** `cd $W && /home/miftah/seer/engine/.venv/bin/ruff check engine && cd web && npx tsc --noEmit`
**Tests:**
```bash
cd $W/engine && PYTHONPATH=$W/engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -n 2 -q \
  tests/test_lab_panel_record.py tests/test_lab_snapshot.py tests/test_lab_books.py tests/test_lab_gate_wording.py
cd $W/web && npm test
```
**Proof:** the real export of the real committed DB, the harness's real connect on a lab copy, and two scripted record-then-export drives on copies.
- Harness: `.claude/skills/verify-seer` for the connect-creates-tables journey (`$V lab RUN status` plus `$V labsql`). `lab export-json` is refused by the harness, so the export journeys run the CLI directly against a scratch copy, with `SEER_LAB_DB` and `--db` and `--out` all pointing into the scratchpad or the worktree.
- Feature-map entries: `none`. This phase adds no command and no page. The snapshot key first becomes visible on `/sera/signals` (phase 6, `features/sera.md`), and the commands that write rows belong to phase 3 (`features/signal-panel.md`).
- Journeys:
  - **J1** · traces R6.1, R6.3 — `cd $W/engine && PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n0 -q tests/test_lab_snapshot.py -k committed_snapshot_is_the_export && /home/miftah/seer/engine/.venv/bin/python -c "import json; s=json.load(open('$W/web/data/lab.json')); print(s['version'], list(s)[-1], json.dumps(s['panel'],separators=(',',':')))" && git -C $W diff --quiet HEAD -- lab/lab.sqlite && echo DB-UNCHANGED && git -C /home/miftah/seer status --porcelain -- lab web/data | wc -l` → passes when the test is 1 passed, the print is `9 panel {"rule":"panel-v1","fdr":0.1,"signals":[]}`, `DB-UNCHANGED` prints (the committed DB has no panel tables and its export still byte-matches), and the main-checkout porcelain count is `0`
  - **J2** · traces R6.3 — `V=$W/.claude/skills/verify-seer/scripts/verify.sh; cd $W && $V up --no-web --empty` (note `RUN=`), then `$V lab $RUN status` (exit 0), then `$V labsql $RUN "select name from sqlite_master where type='table' and name like 'panel_%' order by name"` and `$V labsql $RUN "select (select count(*) from panel_signals), (select count(*) from panel_results)"`, then `SEER_LAB_DB=~/.local/state/seer-verify/$RUN/lab.sqlite SEER_ENV_FILE=~/.local/state/seer-verify/$RUN/engine.env PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --db ~/.local/state/seer-verify/$RUN/lab.sqlite export-json --out /tmp/claude-1000/-home-miftah-seer/0d2098e9-bbe5-4e92-b0ba-770ec551e754/scratchpad/p2-with-tables.json && /home/miftah/seer/engine/.venv/bin/python -c "import json; a=json.load(open('/tmp/claude-1000/-home-miftah-seer/0d2098e9-bbe5-4e92-b0ba-770ec551e754/scratchpad/p2-with-tables.json'))['panel']; b=json.load(open('$W/web/data/lab.json'))['panel']; print(a==b, a)"`, then `$V down $RUN` → passes when labsql lists `panel_results` and `panel_signals` (the real CLI connect created them on the copy), the counts read `0|0`, and the last print is `True {'rule': 'panel-v1', 'fdr': 0.1, 'signals': []}`. Tables with no rows publish exactly what the table-less committed DB publishes.
  - **J3** · traces R2.3, R3.2, R6.1 — `S=/tmp/claude-1000/-home-miftah-seer/0d2098e9-bbe5-4e92-b0ba-770ec551e754/scratchpad/p2-twins; cd $W && PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python .workflows/plan/sera-signal-panel/phase-2-drive.py $W/lab/lab.sqlite $S --crowd twins` → passes when it prints `repeat insert of S0001 -> False`, `trials before T after T` (same T), `panel_signals 34 panel_results 204` (34 signals x 2 stores x 3 eras), `S0001 clears=True`, `S0002 clears=False … twin_of=S0001`, `S0003 clears=True q=0.0217`, `S0004 … twin_of=S0003` and `S0033 … twin_of=S0003`, the replay line `clears=False` with the "did no better than the rest" reason, `export-json exit 0`, `version 9 last key panel`, `rule panel-v1 fdr 0.1 signals 34`, `first ranked S0001 clears True`, `S0002 twinOf S0001 S0003 clears True`, `S0001 dev eras ['all', 'pre2009', 'recent']`, and `replay <M####-…> kind replay methodId <M####> ic None`. Afterwards `git -C $W status --porcelain -- lab` prints nothing
  - **J4** · traces R2.3, R3.2 — `S=/tmp/claude-1000/-home-miftah-seer/0d2098e9-bbe5-4e92-b0ba-770ec551e754/scratchpad/p2-nulls; cd $W && PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python .workflows/plan/sera-signal-panel/phase-2-drive.py $W/lab/lab.sqlite $S --crowd nulls` → passes when it prints `S0001 clears=True`, `S0002 … twin_of=S0001`, and `S0003 clears=False q=0.2389` (±0.0005) with the reason "its edge is no bigger than luck produces when this many ideas have been tried", plus `S0003 clears False` in the export lines. The same S0003 rows clear in J3, where the 30 extra panels are twins, and fail here, where they are 30 distinct panels: the correction counts distinct pick sets, not rows
  - **J5** · traces R2.3, R3.2 — `cd $W/engine && PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n0 -q tests/test_lab_panel_record.py -k "students_t or scipy or benjamini or twin or crowd"` → passes when every selected test passes (the scipy cross-check runs, not skips: `scipy 1.18.1` is in the venv)
- Neighbor check: snapshot 8's random-twin and role fields and the books block are the existing exports most likely to break when the snapshot shape moves. `cd $W/engine && PYTHONPATH=$W/engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres /home/miftah/seer/engine/.venv/bin/python -m pytest -n 2 -q tests/test_lab_snapshot.py tests/test_lab_books.py tests/test_lab_yardstick.py tests/test_lab_yardstick_record.py tests/test_lab_roles.py && cd $W/web && npx tsc --noEmit && npm test` → all green. The `/sera` overview builds its fixture snapshot with the new `panel` literal, and `lab.test.ts` reads the regenerated JSON
- Cost: no paid drives. J2 needs the local verify Postgres container and no network.

**Exit criteria:** `store.connect` creates `panel_signals` and `panel_results`, both refusing UPDATE and DELETE. Rows insert once, and a repeat writes nothing. `panel_verdict.published` clears exactly the panels whose three readings agree, with twins collapsed in the correction (J3 vs J4). `web/data/lab.json` is snapshot 9, ending in `"panel":{"rule":"panel-v1","fdr":0.1,"signals":[]}`, and byte-equal to the export of the unchanged `lab/lab.sqlite`. `ruff`, the four engine test files, `tsc` and vitest are green.

## Handoffs

- **Phase 1 (signal registry and evaluator):** `panel.RULE_ID` must equal `panel_verdict.RULE_ID` (`"panel-v1"`), and `panel.ERAS` must equal `store.PANEL_ERAS` (`("all", "pre2009", "2009-2015")`). This phase defines its own copies because it does not depend on phase 1. `EraStats` must keep the field names `PanelResultRow.from_era` reads: `era, months, mean_pool, mean_scored, ic_mean, ic_t, spread_top, spread_t, fm_slope, fm_t, top_turnover`. Every number must be finite. `top_turnover` must be in [0, 1], and `ic_mean`/`ic_t` must be None together, always None in picks mode. `PanelReading.picks_hash` must be non-empty. The reconciler should have phase 3 add one assertion test, `panel.RULE_ID == panel_verdict.RULE_ID and panel.ERAS == store.PANEL_ERAS`, because phase 3 is the first phase that sees both modules.
- **Phase 3 (`lab panel`, `lab panel-map`, `lab next-signal-id`):** the printing halves of **R2.3** and **R3.2** are phase 3's to prove: `lab panel-map` prints every recorded panel ranked by controlled slope, with the verdict and twin from `panel_verdict.published`, which phase 2 computes and proves (J3-J5). Phase 3 builds rows with `PanelResultRow.from_era` and writes `insert_panel_signal` plus `insert_panel_results` in one `store.begin_immediate` transaction. It calls `has_panel` before measuring, passes the loaded dev store's fingerprint as `published(conn, dev_fingerprint=...)` when it has one, and passes the discovered signal ids to `next_signal_id(conn, taken=...)`. `insert_panel_signal` refuses an id already recorded from a different `source_sha`. That check sits alongside phase 3's `registry_problem` check and does not replace it.
- **Phase 4 (replay):** a replay row's `id` is the candidate id, `method_id` is its method, and `kind` is `"replay"`. The candidate must be a dev trial of that method, or the insert refuses it. `ic_mean`/`ic_t` are None. Every one of the 1,720 dev arms of `stock-%` methods, measured read-only on the base DB, already has an id prefixed by its method id. Take `hypothesis` and `expected_failure` from the method row split on `store.EXPECTED_FAILURE_SEP`: all 321 `stock-%` methods with dev trials carry that separator (measured). Take `source_kind` from the method row and `source_sha` from `store.latest_source_sha` (or the method file's sha).
- **Phase 5 (panel gate):** read `panel_verdict.published(conn, dev_fingerprint=<the loaded dev store's fingerprint>)[signal_id].clears`. A twin never clears, so a method should name the first signal of its pick set.
- **Phase 6 (`/sera/signals`):** import `LabPanel`, `LabPanelSignal`, `LabPanelStore`, `LabPanelEra` and `PANEL_KINDS` from `web/lib/sera/types.ts`. `dev` and `survivorship` may be null, and so may any era. `reasons` are engine-written plain sentences, so show them as given. `id`, `methodId` and `twinOf` are ids, so never render them. Signals arrive sorted by dev whole-window slope. The `/sera/signals` empty-state half of **R6.3** is phase 6's. `asOf` does not move when only panel rows change. If the page needs a measured date, that is a later snapshot field, not part of this phase. No snapshot builder was added to `fixture.ts`; phase 6 adds one if its tests need it.
- **Landing (invariant 7, reconciled):** this branch carries **no** change to `lab/lab.sqlite` (Step 9 restores it by `git checkout`); it carries only the regenerated `web/data/lab.json`. At landing, take `main`'s `lab/lab.sqlite` untouched as it is at that moment, run `lab export-json` on it with the landed code (Step 9's command with `W` set to the landing checkout, without the restore line), and commit `web/data/lab.json`, and `lab/lab.sqlite` only if its bytes changed (the connect adds the two empty tables), by explicit path. Never merge either file, and never use `lab stage` from a worktree.

## Rollback

Revert this phase's commit, then rerun Step 9's export with the reverted code, which brings back the version-8 snapshot, and commit `web/data/lab.json` by path. If the tables have already reached a database (after landing, the first lab command creates them), they stay, empty or append-only, and unread. Older code ignores them because it never names them, and no schema version moved.
