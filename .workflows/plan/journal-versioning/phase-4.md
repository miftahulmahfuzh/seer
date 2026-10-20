# Phase 4: Export: snapshot emits the chain; TS mirror; document counts

**Plan set:** `JOURNAL_VERSIONING_PLAN.md`
**Analysis:** `docs/analyzer/20261020-162050-J7K2_code_analyzer.md`
**Satisfies:** R1 — the owner sees *one document labelled with its version* instead of four cards. This phase publishes the version number and the chain links; phase 5 renders them.
**Depends on:** Phase 1 (schema 8: `insights.supersedes`, `insights.doc_key`, `insights_one_successor`, `store.set_supersedes`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab` (+ `web/lib/sera`)

---

## Goal

After this phase `web/data/lab.json` carries, for every journal row, the link it was written
with (`supersedes`, `docKey`) **and the two facts a reader would otherwise have to walk a linked
list to learn** (`version`, `supersededBy`). The chain is walked exactly once, in Python, at
export time. `summary.insights` becomes a count of **documents** — rows nothing supersedes — with
the raw row count published beside it as `insightRows`, so the owner's headline number stops
inflating on a re-run. `web/lib/sera/types.ts` mirrors all of it, and `lab status`'s "Latest
insights" list shows heads only.

At this phase's commit every row still has `supersedes IS NULL` (phase 6 has not run), so every
insight is its own document at `version: 1` and `summary.insights == insightRows == 500`. That is
the correct, boring state — and it is why the tests below build chains in a fixture rather than
leaning on the committed database.

---

## Interface Contract

**Creates:**
- `store._insight_chains(rows) -> tuple[dict[int, int], dict[int, int]]` (`lab/store.py`, new, after `_dicts`) — `(version_by_id, successor_by_id)`
- `store._opt_int(x) -> int | None` (`lab/store.py`, new, beside `_num`)
- `store.INSIGHT_DOCUMENTS_SQL` (`lab/store.py`, new, beside `summary_rows`)
- `store.insight_document_count(conn) -> int` (`lab/store.py`, new, beside `summary_rows`)
- JSON field `insights[].supersedes` (`int | null`)
- JSON field `insights[].docKey` (`string | null`)
- JSON field `insights[].version` (`int`, >= 1)
- JSON field `insights[].supersededBy` (`int | null`)
- JSON field `summary.insightRows` (`int`)
- TS fields `LabInsight.supersedes`, `.docKey`, `.version`, `.supersededBy` (`web/lib/sera/types.ts`)
- TS field `LabSnapshot['summary'].insightRows` (`web/lib/sera/types.ts`)

**Signature changes:** none. `store.snapshot(conn)` and `store.summary_rows(conn)` keep their signatures; their *values* change.

**Semantic changes (this is the breaking part, and it is deliberate):**
- `snapshot()["summary"]["insights"]` — count of **rows** -> count of **documents (heads)**
- `store.SNAPSHOT_VERSION` — `5` -> `6`; `LabSnapshot['version']` literal type `5` -> `6`
- `summary_rows`'s `("insights", N)` row -> **two** rows, `("journal documents", N)` and `("journal entries (every version counts)", N)`

**Deletes:** nothing.
**Renames:** nothing. (`summary.insights` keeps its name and changes meaning; `insightRows` is the new home of the old meaning.)

**Requires (from Phase 1):**
- `store.SCHEMA_VERSION == "8"`
- `insights.supersedes INTEGER REFERENCES insights(id)` and `insights.doc_key TEXT` exist on the committed database, **NULL on all 500 rows**
- the partial unique index `insights_one_successor` guarantees **at most one successor per row** — my `supersededBy` is a single id, not a list, and that is why
- `store.set_supersedes` refuses a link to a **higher** id, to itself, and across `method_id` — my `version` derivation is a single forward pass in id order and that is why it terminates
- phase 1 has already rewritten `test_the_v6_to_v7_migration_moves_not_one_byte_of_the_web_snapshot` (`test_lab_snapshot.py:593`) for v7->v8. **I change exactly one line inside it** — the trailing `assert store.SNAPSHOT_VERSION == 5` (line 616 today) — and nothing else in that function. See Step 8.

**Leaves alone (owned by others):**
- `web/app/sera/journal/view.ts`, `page.tsx`, `JournalSeen.tsx`, `seen-client.ts`, `journal.module.css` — Phase 5
- `web/app/sera/journal/view.test.ts` — Phase 5 owns the file. **I touch exactly the 4 default lines inside the `ins()` factory at lines 8-14**, because `LabInsight` gaining required fields makes `npx tsc --noEmit` red otherwise. Declared here so the reconciler can see the overlap; the merge is additive.
- `engine/src/seer_engine/commands/lab.py` — everything but **line 843**. Phases 2 and 3 own `_insight`, `_link` and the parser.
- `store.py`'s schema, triggers, `_migrate`, `add_insight`, `set_supersedes` — Phase 1
- `lab/real_costs.py`, `survivorship_check.py`, `gate_probe.py`, `exposure.py`, `prereg.py` — Phase 3
- `lab/lab.sqlite` row data — Phase 6 (I regenerate `web/data/lab.json`, I write no row)
- `engine/src/seer_engine/lab/hardgate.py` — a concurrent session owns it

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | `_opt_int`; `INSIGHT_DOCUMENTS_SQL` + `insight_document_count`; `summary_rows` splits the insight row in two; `SNAPSHOT_VERSION` 5->6 with its ledger comment; `_insight_chains`; `snapshot` hoists the insight rows, derives the chain, publishes four new per-row fields and `summary.insightRows` |
| `engine/src/seer_engine/commands/lab.py` | modify | **line 843 only** — "Latest insights" selects heads |
| `engine/tests/test_lab_snapshot.py` | modify | contract test learns the four fields and `insightRows`; `SNAPSHOT_VERSION` assertions move to 6; **three new tests** for the derivation, the document count, and the unmigrated-database path |
| `web/lib/sera/types.ts` | modify | `LabSnapshot.version` literal 5->6 and its ledger comment; `summary.insightRows`; `LabInsight` gains four documented fields |
| `web/app/sera/overview.test.ts` | modify | `insight()` factory gains the four fields; `snap()` gains `version: 6` and `summary.insightRows` |
| `web/app/sera/journal/view.test.ts` | modify | `ins()` factory gains the four defaults (4 lines; Phase 5 owns the rest of the file) |
| `web/data/lab.json` | regenerate | `lab stage` output; **+32,018 bytes** (see Step 10) |

---

## Implementation Steps

### Step 1: a JSON-safe optional integer
**File:** `engine/src/seer_engine/lab/store.py:2763` (immediately after `_num`, before `_dicts`)
**Change:** add a sibling to `_num` for nullable integer columns. `supersedes` is an `INTEGER`
column that is NULL on most rows; `_num` would round it to a float and publish `2.0` where the
reader wants `2`.
**Code:**
```python
def _opt_int(x: Any) -> int | None:
    """A nullable integer column as JSON: None stays None, anything else becomes ``int``.

    ``_num``'s sibling for columns that are counts or row ids rather than measurements.
    ``supersedes`` is an ``INTEGER`` foreign key and must reach the web as ``2``, not ``2.0``:
    the reader compares it against ``id``, which is published as an int."""
    return None if x is None else int(x)
```
**Impact:** none on its own; used by Step 5.

---

### Step 2: the document count, defined once
**File:** `engine/src/seer_engine/lab/store.py:2692` (immediately before `def summary_rows`)
**Change:** name the definition of "a journal document" in SQL, once, and expose a counter.
**Code:**
```python
# A journal *document* is a chain of ``insights`` rows linked by ``supersedes``; its **head** is
# the row nothing supersedes -- the current version. Counting heads instead of rows is the
# owner's complaint answered in a number: before this, re-running a command that auto-journals
# pushed the count up by one even when the new row said the same thing as the old one. Rows are
# still worth printing (they are what the append-only store actually holds), so both are
# published, under names that cannot be mistaken for each other.
#
# This SQL needs schema v8. ``summary_rows`` is only ever called on a connection opened through
# ``connect`` (``lab status``, ``export_xlsx``), which migrates first, so that is safe here --
# and deliberately NOT safe enough for ``snapshot``, which must also answer on an unmigrated
# read-only database. ``snapshot`` therefore counts heads from the rows it has already read.
INSIGHT_DOCUMENTS_SQL = (
    "SELECT count(*) FROM insights i "
    "WHERE NOT EXISTS (SELECT 1 FROM insights s WHERE s.supersedes = i.id)"
)


def insight_document_count(conn: sqlite3.Connection) -> int:
    """How many journal documents the lab holds: insight rows that nothing supersedes.

    Requires schema v8. For a connection that may predate it, derive the count from the exported
    rows instead (``snapshot`` does)."""
    return int(conn.execute(INSIGHT_DOCUMENTS_SQL).fetchone()[0])
```
**Impact:** new API surface only.

---

### Step 3: `summary_rows` publishes both counts
**File:** `engine/src/seer_engine/lab/store.py:2693-2707` (whole function)
**Change:** the `("insights", count(*))` row becomes two rows with unambiguous labels. This row
is the first thing `lab status` prints and the first row of the xlsx summary sheet; leaving one
label over a changed meaning is exactly the mistake the `dev trials` comment above it records.
**Code:**
```python
def summary_rows(conn: sqlite3.Connection) -> list[tuple[str, Any]]:
    by_status = conn.execute("SELECT status, count(*) FROM methods GROUP BY status ORDER BY status").fetchall()
    out: list[tuple[str, Any]] = [
        # The label used to read "N for the DSR", which was true only under the ``all-trials``
        # policy. ``DSR_POLICY`` has been ``methods`` since 2026-10-08, so the gate judges at
        # ``npolicy.effective_n``, a number several times smaller -- and this row, the first the
        # reader sees, was overstating the lab's single most important gate input fivefold.
        # The count is still worth printing (it is the lab's size), but it is not N.
        ("dev trials (one row per recorded backtest)", dev_trial_count(conn)),
        ("test-window looks used", test_looks(conn)),
        ("methods", int(conn.execute("SELECT count(*) FROM methods").fetchone()[0])),
        # Two numbers, never one. The old single ``insights`` row counted rows and so rose every
        # time a command re-journalled the same observation; "journal documents" is the number
        # the owner means when he asks how much is in the journal. They are equal until a chain
        # exists, and the gap between them is the amount of re-run that has happened since.
        ("journal documents", insight_document_count(conn)),
        ("journal entries (every version counts)",
         int(conn.execute("SELECT count(*) FROM insights").fetchone()[0])),
    ]
    out += [(f"methods {r[0]}", r[1]) for r in by_status]
    return out
```
**Impact:** `lab status` prints one more line; the xlsx summary sheet gains a row. No test asserts
these labels (checked: `engine/tests` only asserts `wb.sheetnames` at `test_lab_store.py:319`).

---

### Step 4: bump `SNAPSHOT_VERSION` and record why
**File:** `engine/src/seer_engine/lab/store.py:2744-2745` (append to the ledger comment, change the value)
**Change:** the snapshot grows four per-insight fields and one summary field, and
`summary.insights` changes meaning. Every previous addition of a derived field moved this number
(2 the derived verdict, 4 `luckGated`, 5 `mwr`), and this one *also* silently redefines an
existing field, which is the stronger reason.
**Code:** replace line 2745 (`SNAPSHOT_VERSION = 5`) with the comment paragraph below plus the
new value, leaving lines 2726-2744 exactly as they are:
```python
#
# 6 adds the journal's version chain: every insight publishes ``supersedes`` and ``docKey`` as
# written, plus two fields derived here and nowhere else -- ``version`` (its depth in the chain,
# 1 for a row that supersedes nothing) and ``supersededBy`` (the id of the row that replaced it,
# null when this row is the current one). They are derived at export time on purpose:
# ``web/app/sera/journal/view.ts`` is a file of pure helpers with no data access, and chasing a
# linked list once per card inside a React component is the shape that makes a reader slow and
# wrong at the same time. 6 also splits the journal count in two: ``summary.insights`` now counts
# **documents** (heads) and ``summary.insightRows`` counts rows. The old field kept its name and
# changed its meaning, which is exactly why this number moved -- a consumer pinned to 5 is
# reading "insights" as a row count and must be told.
SNAPSHOT_VERSION = 6
```
**Impact:** `test_the_snapshot_follows_the_contract` and the migration test's tail assertion both
move (Step 8). `web/lib/sera/types.ts`'s literal type moves (Step 9).

---

### Step 5: walk the chain once
**File:** `engine/src/seer_engine/lab/store.py:2771` (immediately after `_dicts`, before `_snapshot_method`)
**Change:** add the derivation.
**Code:**
```python
def _insight_chains(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[dict[int, int], dict[int, int]]:
    """``(version_by_id, successor_by_id)`` for a set of ``insights`` rows, in one pass.

    A journal *document* is a chain of rows linked by ``supersedes``: each row supersedes at most
    one predecessor, and ``insights_one_successor`` (schema v8) makes sure at most one row
    supersedes any given predecessor. The chain is therefore a simple path, and the two things a
    reader wants from it are:

    * ``version`` -- how deep in its chain a row sits. 1 for a row that supersedes nothing, 2 for
      the row that replaced it, and so on. This is the number the owner asked for: *"we will say
      this is the fourth version"*.
    * ``supersededBy`` -- the id of the row that replaced this one, absent when the row is the
      **head** (the current version, and the only one ``/sera/journal`` shows by default).

    Derived here rather than in the web, because ``web/app/sera/journal/view.ts`` is documented as
    pure helpers with no data access, and a component that walks a linked list per card does the
    work once per render for every reader instead of once per export.

    Terminating by construction: ``version`` is resolved in ascending id order and
    ``store.set_supersedes`` refuses a link to anything but a **lower** id, so a predecessor is
    always already resolved when its successor is reached. Nothing recurses and nothing loops, so
    a database hand-edited past that guard yields a wrong number -- never a hang. Rows whose
    ``supersedes`` points at an id this set does not contain are treated as chain starts.
    """
    predecessor: dict[int, int | None] = {}
    successor: dict[int, int] = {}
    for r in rows:
        rid = int(r["id"])
        raw = r.get("supersedes")
        prev = None if raw is None else int(raw)
        predecessor[rid] = prev
        if prev is not None:
            successor[prev] = rid
    version: dict[int, int] = {}
    for rid in sorted(predecessor):
        prev = predecessor[rid]
        version[rid] = 1 if prev is None else version.get(prev, 0) + 1
    return version, successor
```
**Impact:** pure function, no I/O. `Iterable` and `Mapping` are already imported in this module
(used by `_snapshot_method` and `curve_json`).

---

### Step 6: `snapshot` reads the insight rows once and derives from them
**File:** `engine/src/seer_engine/lab/store.py:2953` (after `bench = seed.benchmark_curves()`, before `gate_block, g = _gate_n(conn)`)
**Change:** hoist the `SELECT * FROM insights` that today sits inline in the return literal at
line 3005, so the rows can be counted and walked before the dict is built.
**Code:**
```python
    bench = seed.benchmark_curves()
    # Read once, derive once. ``.get`` rather than ``[...]`` on the two v8 columns is load-bearing:
    # this function is documented to answer on a read-only connection to a database that has not
    # been migrated, and ``test_the_snapshot_reads_a_v1_database_read_only_and_migration_does_not
    # _change_it`` asserts the v1 export is byte-identical to the export after migration. A v1 row
    # has no ``supersedes``; it is a document of one, at version 1, exactly like a migrated row
    # whose column is NULL -- so the bytes match.
    insight_rows = _dicts(conn, "SELECT * FROM insights ORDER BY id")
    insight_version, insight_successor = _insight_chains(insight_rows)
    insight_documents = sum(1 for i in insight_rows if int(i["id"]) not in insight_successor)
    gate_block, g = _gate_n(conn)
```
**Impact:** one fewer query (the inline `_dicts` call is removed in Step 7); determinism
unchanged — the same database still gives the same bytes.

---

### Step 7: publish the chain and both counts
**File:** `engine/src/seer_engine/lab/store.py:2988` and `:3002-3006`
**Change:** `summary.insights` becomes the document count, `summary.insightRows` is added
immediately after it (key order is the published byte order, so it goes next to the number it
qualifies), and the insights block gains four fields.
**Code — replace line 2988:**
```python
            # Documents, not rows: a re-run that supersedes its own previous note leaves this
            # number where it was, which is the whole point. ``insightRows`` beside it is what
            # the append-only store actually holds.
            "insights": insight_documents,
            "insightRows": len(insight_rows),
```
**Code — replace lines 3002-3006:**
```python
        # ``supersedes`` and ``docKey`` as the writer recorded them; ``version`` and
        # ``supersededBy`` derived by ``_insight_chains`` above. A head is a row with
        # ``supersededBy: null`` -- that is the test ``/sera/journal`` applies to decide what to
        # show, and it is a field read rather than a graph walk precisely so the reader can stay
        # a pure function.
        "insights": [
            {"id": int(i["id"]), "kind": i["kind"], "title": i["title"], "body": i["body"],
             "methodId": i["method_id"], "added": i["added"],
             "supersedes": _opt_int(i.get("supersedes")), "docKey": i.get("doc_key"),
             "version": insight_version[int(i["id"])],
             "supersededBy": insight_successor.get(int(i["id"]))}
            for i in insight_rows
        ],
```
**Impact:** `web/data/lab.json` bytes change — expected, and regenerated in Step 10.

---

### Step 8: the engine tests
**File:** `engine/tests/test_lab_snapshot.py`

**8a — the migration test's tail (`:616`).** Phase 1 has rewritten this function for v7->v8.
Change only its last line:
```python
    assert store.SNAPSHOT_VERSION == 6
```
Nothing else in `test_the_v6_to_v7_migration_moves_not_one_byte_of_the_web_snapshot` (whatever
phase 1 renamed it to) is mine. The migration itself still moves no bytes at this phase: the
committed database is already v8 when this test runs, so both exports in it are v8 exports.

**8b — the contract test (`:740`, `:769`, `:816`).** Three edits.

`:740`:
```python
    assert s["version"] == 6
```

`:769` (the summary assertion) — the fixture `lab` adds two insights, neither linked, so both
numbers read 2:
```python
    assert {k: v for k, v in summary.items() if k != "byStatus"} == {
        "devTrials": 55, "testLooks": 0, "methods": 15, "labMethods": 1, "historicalMethods": 14,
        "insights": 2, "insightRows": 2,
    }
```

`:816` (the insights assertion) — replace the single line with a full key check and the chain
fields, so the contract test is what fails when a field is dropped:
```python
    INSIGHT_KEYS = {"id", "kind", "title", "body", "methodId", "added",
                    "supersedes", "docKey", "version", "supersededBy"}
    assert all(set(i) == INSIGHT_KEYS for i in s["insights"])
    assert [(i["id"], i["kind"], i["methodId"]) for i in s["insights"]] == [(1, "observation", "M0001"), (2, "synthesis", None)]
    # Nothing in this fixture is linked, so every row is its own document at version 1 -- the
    # state of the committed lab at this phase too, before the backfill runs.
    assert all(i["supersedes"] is None and i["docKey"] is None for i in s["insights"])
    assert all(i["version"] == 1 and i["supersededBy"] is None for i in s["insights"])
```
(Define `INSIGHT_KEYS` beside `METHOD_KEYS`/`TRIAL_KEYS` at module level, `:82-89`, rather than
inside the test, to match the file's shape. The block above shows it inline for readability;
place it at module level:)
```python
INSIGHT_KEYS = {"id", "kind", "title", "body", "methodId", "added",
                "supersedes", "docKey", "version", "supersededBy"}
```

**8c — three new tests.** Append after `test_the_snapshot_follows_the_contract` (`:824`).

```python
def test_a_chain_of_insights_publishes_one_document_and_counts_its_versions(lab):
    """The owner's request, as the export sees it: three rows on one topic become one document at
    version 3, with the two earlier rows published as the history behind it.

    The chain is built here rather than read from the committed lab on purpose -- at this phase
    nothing in `lab/lab.sqlite` is linked yet (the backfill is a later phase), so a test that
    leaned on it would assert nothing.
    """
    with lab:
        a = store.add_insight(lab, kind="observation", title="Width", body="v1", method_id="M0001")
        b = store.add_insight(lab, kind="observation", title="Width", body="v2", method_id="M0001")
        c = store.add_insight(lab, kind="observation", title="Width", body="v3", method_id="M0001")
        store.set_supersedes(lab, b, a)
        store.set_supersedes(lab, c, b)
    s = store.snapshot(lab)
    chain = {i["id"]: i for i in s["insights"] if i["id"] in (a, b, c)}
    assert [chain[a]["version"], chain[b]["version"], chain[c]["version"]] == [1, 2, 3]
    assert chain[a]["supersededBy"] == b and chain[b]["supersededBy"] == c
    assert chain[c]["supersededBy"] is None          # the head: the one the journal shows
    assert chain[a]["supersedes"] is None and chain[b]["supersedes"] == a and chain[c]["supersedes"] == b
    # Five rows, three of them one document: the count the owner reads does not move when a
    # command re-journals the same observation.
    assert s["summary"]["insightRows"] == 5
    assert s["summary"]["insights"] == 3
    assert store.insight_document_count(lab) == s["summary"]["insights"]


def test_two_variants_under_one_title_stay_two_documents(lab):
    """The measured failure the design exists to avoid, asserted at the export.

    `real_costs` titles on the method name, so three arms of one method -- M0260-M-NATIVE,
    -M-G12, -M-G3 -- wrote three rows under one identical title 25 seconds apart. They are three
    measurements, not a triple-write. Unlinked rows publish as separate documents however alike
    their titles are, and this test is here so that a later "helpful" change to the export cannot
    quietly collapse a measurement off the page.
    """
    with lab:
        for body in ("23.8% / 1.98", "25.6% / 1.62", "33.6% / 1.60"):
            store.add_insight(lab, kind="observation", title="Real costs", body=body, method_id="M0001")
    s = store.snapshot(lab)
    same_title = [i for i in s["insights"] if i["title"] == "Real costs"]
    assert len(same_title) == 3
    assert all(i["version"] == 1 and i["supersededBy"] is None for i in same_title)
    assert s["summary"]["insights"] == s["summary"]["insightRows"] == 5


def test_the_chain_fields_are_published_for_a_database_that_predates_them(tmp_path):
    """``snapshot`` answers on an unmigrated read-only connection, and the chain fields must not
    be what breaks that: a v1 row has no ``supersedes`` column at all, and publishes exactly what
    a migrated row with a NULL one publishes -- a document of one, at version 1.

    This is the stronger half of ``test_the_snapshot_reads_a_v1_database_read_only_and_migration
    _does_not_change_it``: that test asserts the bytes do not move, this one says what they say.
    """
    db = tmp_path / "lab" / "lab.sqlite"
    db.parent.mkdir()
    _v1_db(db)
    ro = store.connect_readonly(db)
    try:
        insights = store.snapshot(ro)["insights"]
    finally:
        ro.close()
    assert [i["id"] for i in insights] == [1, 2, 3]
    assert all(set(i) == INSIGHT_KEYS for i in insights)
    assert all(i["supersedes"] is None and i["docKey"] is None for i in insights)
    assert all(i["version"] == 1 and i["supersededBy"] is None for i in insights)
```
**Impact:** `test_a_chain_of_insights_publishes_one_document_and_counts_its_versions` is the only
test in this phase that depends on phase 1's `store.set_supersedes`. If phase 1's signature turns
out to be `set_supersedes(conn, row_id, predecessor_id)` in the other order, flip the two
arguments — the assertion is what matters.

---

### Step 9: the TS mirror and its two test fixtures
**File:** `web/lib/sera/types.ts:3-10` — the snapshot version ledger and literal:
```ts
export type LabSnapshot = {
  /**
   * 2 added the derived verdict to every trial (`failedNow` / `eligibleNow` / `dsrNow`);
   * 3 added `paper`, which names the lab method behind each roster entry;
   * 4 added `luckGated`, which says whether the luck hurdle applies to a trial at all;
   * 5 added `mwr` / `spyTrMwr`, what a funded trial's money actually earned;
   * 6 added the journal's version chain (`supersedes` / `docKey` / `version` / `supersededBy`)
   *   and split the journal count: `summary.insights` now counts documents, not rows.
   */
  version: 6;
```

**File:** `web/lib/sera/types.ts:38-45` — the summary block:
```ts
  summary: {
    devTrials: number;
    testLooks: number;
    methods: number;
    labMethods: number;
    historicalMethods: number;
    /**
     * Journal **documents**: insight rows that nothing supersedes. A re-run that supersedes its
     * own previous note leaves this number where it was. Counted rows until snapshot 5.
     */
    insights: number;
    /** Journal rows, every version of every document. `insights` is the one to show a reader. */
    insightRows: number;
    byStatus: Record<string, number>;
  };
```

**File:** `web/lib/sera/types.ts:207-214` — `LabInsight`:
```ts
/**
 * One journal row. Rows are linked into **documents** by `supersedes`: a re-run of the command
 * that wrote a note appends a new row pointing at the old one rather than a sibling, and
 * `/sera/journal` renders the chain as one document labelled with its version.
 *
 * The store is append-only and stays that way — superseding *adds* a row, it never rewrites one.
 * `version` and `supersededBy` are derived by the engine at export time (`store._insight_chains`)
 * so that nothing here has to walk a linked list: show rows with `supersededBy === null`, and
 * reach the history through `supersedes`.
 */
export type LabInsight = {
  id: number;
  kind: 'observation' | 'hypothesis' | 'data-wish' | 'feature-wish' | 'risk' | 'synthesis';
  title: string;
  body: string;
  methodId: string | null;
  added: string;
  /** The row this one replaces, or null when it starts a document. Always a lower `id`. */
  supersedes: number | null;
  /**
   * The writer-computed identity of the document this row is a version of
   * (`real-costs:M0260-M-G3`, `prereg:M0022`). Null on rows written by hand and on every row
   * written before snapshot 6. Never a display string — it is a key.
   */
  docKey: string | null;
  /** Depth in the chain: 1 for a row that supersedes nothing, 2 for the row that replaced it. */
  version: number;
  /** The row that replaced this one, or null when this row is the head — the current version. */
  supersededBy: number | null;
};
```

**File:** `web/app/sera/overview.test.ts:81-88` — the `insight()` factory:
```ts
const insight = (id: number, kind: LabInsight['kind'], added: string): LabInsight => ({
  id,
  kind,
  title: `${kind} ${id}`,
  body: `Body of ${id}`,
  methodId: null,
  added,
  supersedes: null,
  docKey: null,
  version: 1,
  supersededBy: null,
});
```

**File:** `web/app/sera/overview.test.ts:90` — `version: 5,` becomes `version: 6,`.

**File:** `web/app/sera/overview.test.ts:115` — the summary fixture:
```ts
  summary: { devTrials: 4, testLooks: 0, methods: 4, labMethods: 2, historicalMethods: 2, insights: 0, insightRows: 0, byStatus: {} },
```

**File:** `web/app/sera/journal/view.test.ts:8-14` — the `ins()` factory. **Four added lines, and
nothing else in this file is mine** (phase 5 owns it):
```ts
const ins = (over: Partial<LabInsight> & Pick<LabInsight, 'id' | 'kind'>): LabInsight => ({
  title: `t${over.id}`,
  body: 'b',
  methodId: null,
  added: '2026-10-04T10:00:00+00:00',
  supersedes: null,
  docKey: null,
  version: 1,
  supersededBy: null,
  ...over,
});
```
**Impact:** `npx tsc --noEmit` stays clean. `web/lib/sera/lab.ts:38` casts through `unknown`, so
the 9.7 MB JSON is never structurally checked against these types — the mirror is enforced by
`test_lab_snapshot.py`'s byte guard and by review, as it was before.

---

### Step 10: `lab status` shows heads
**File:** `engine/src/seer_engine/commands/lab.py:843`
**Change:** one line. The "Latest insights" list is the owner's at-a-glance read of the journal;
after a re-run it would show the superseded row and its replacement side by side saying the same
thing, which is his complaint reproduced inside the CLI. Heads only.
**Code:**
```python
    for i in conn.execute(
        "SELECT * FROM insights i "
        "WHERE NOT EXISTS (SELECT 1 FROM insights s WHERE s.supersedes = i.id) "
        "ORDER BY i.id DESC LIMIT 8"
    ):
```
Line 844 (the `out.append(f"  [{i['kind']}] ...")`) is **left exactly as it is**. No version label
is added: the status block is a what-is-new list, not a document browser, and a depth number
costs a recursive CTE here to tell the owner something he can only act on at `/sera/journal`,
where phase 5 puts it on a chip. Keeping the edit to one line also keeps this phase out of the
way of phases 2 and 3, which own the rest of `commands/lab.py`.
**Impact:** at this phase the output is byte-identical (nothing is linked yet). It becomes correct
the moment phase 6 lands, with no further change.

---

### Step 11: regenerate the snapshot, then run the suite
**File:** `web/data/lab.json` (generated)
**Change:** `lab stage`. **This order is not negotiable** —
`test_the_committed_snapshot_is_the_export_of_the_committed_database`
(`test_lab_snapshot.py:1054`) asserts the committed JSON is byte-for-byte the export of the
committed database, so it is **red by design** from Step 7 until this runs.

```bash
cd /home/miftah/.worktrees/seer/journal-versioning
sha256sum lab/lab.sqlite                       # record it
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine \
  lab --db "$PWD/lab/lab.sqlite" stage
sha256sum lab/lab.sqlite                       # must be unchanged
```
`--db` with an absolute path inside the worktree is required: `store.DB_PATH` falls back to
`config.REPO_ROOT`, and from a worktree `lab stage` otherwise regenerates and stages the **main
checkout** at `/home/miftah/seer`. `store.snapshot_path` puts the JSON beside the database's own
repo, and `_stage` runs `git add` with `cwd=path.parent`, so both land in this worktree.

**If the two hashes differ:** `lab stage` opens `BEGIN EXCLUSIVE` (and `connect` migrates on
connect), which can rewrite pages even though `_stage` rolls back. This phase writes **no row**,
so restore the database and keep only the JSON:
```bash
git checkout -- lab/lab.sqlite
git add web/data/lab.json
```
Then commit **by index** — `git commit -m "…"`, never `git commit -- <paths>`, which re-reads the
working tree and defeats the staging.

**Expected size delta, measured on today's file:** `web/data/lab.json` is 9,672,655 bytes, of
which the `insights` block is 907,841. Four fields on 500 unlinked rows add exactly 64 bytes per
row (`,"supersedes":null,"docKey":null,"version":1,"supersededBy":null`) = **32,000 bytes**, plus
`,"insightRows":500` = 18. Total **+32,018 bytes (+0.33%)**; the insights block grows 3.5%.
`page.tsx:71-74`'s concern is that the 0.89 MB of titles and bodies never reaches the browser —
these four scalars per row are server-side only and do not change that: `unseenByKind` still
crosses as one integer per unseen insight.

Then, and only then:
```bash
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests
```
**Impact:** the one generated file in this phase.

---

## Verification

**Build:**
```bash
cd /home/miftah/.worktrees/seer/journal-versioning
engine/.venv/bin/ruff check engine
cd web && npx tsc --noEmit
```

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/journal-versioning
# Step 11 FIRST. `lab stage` then test, never the reverse.
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests/test_lab_snapshot.py -n0   # the whole file, serial
cd web && npm test
```
Without `PYTHONPATH=engine/src` pytest silently tests the main checkout instead of this branch.

**Manual check:**
```bash
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab --db "$PWD/lab/lab.sqlite" status | head -12
python3 -c "
import json; d=json.load(open('web/data/lab.json'))
print('snapshot version', d['version'])
print('documents', d['summary']['insights'], 'rows', d['summary']['insightRows'])
i=d['insights'][0]; print(sorted(i))
assert d['summary']['insights'] == d['summary']['insightRows'] == len(d['insights']) == 500
assert all(x['version']==1 and x['supersededBy'] is None for x in d['insights'])
print('ok')
"
```
`lab status` must show `journal documents 500` and `journal entries (every version counts) 500`.
No `/sera/journal` screenshots are needed here — nothing rendered changes until phase 5.

**Exit criteria:**
1. `web/data/lab.json` is the byte-for-byte export of `lab/lab.sqlite` and carries
   `"version":6`, `summary.insightRows`, and all four chain fields on all 500 insights.
2. Every insight publishes `version: 1`, `supersededBy: null` — correct, because phase 6 has not
   run.
3. `npx tsc --noEmit` clean, `npm test` green, `pytest engine/tests` green, `ruff check` clean.
4. `lab/lab.sqlite` is byte-identical to its state before this phase: this phase writes no row.
5. The test-window look count still reads **4** (`lab status`, line "test-window looks used").

---

## Handoffs

- **Phase 5 (R1, R5) — the whole reader.** `view.ts`, `page.tsx`, `JournalSeen.tsx`,
  `journal.module.css`, and the rest of `view.test.ts`. The interface is exactly the four fields
  and `summary.insightRows` documented in `types.ts`. The contract it should build on: *a head is
  a row with `supersededBy === null`*; *its history is reached by following `supersedes` backwards*;
  *`version` is already computed, do not count anything*. `kindCounts`, `unseenCounts`,
  `journalGroups`, `badgeTip`, the "N entries in all" line and `page.tsx`'s `unseenByKind` all
  still count rows after this phase — that is R5 and it is phase 5's, not mine.
- **Phase 5 — the "Revised" marker.** `view.ts:46-52`'s `SEEN_COPY.marker = 'New'` is untouched
  here. A superseded document reappears as unseen because its head id changed, which is desirable
  and must read "Revised"; `supersedes !== null` on the head is the test for it, and it is now a
  published field.
- **Phase 6 — the backfill.** Five links makes `summary.insights` read 495 against
  `insightRows` 500, and M0179's chain `320 -> 499 -> 500` publishes `version: 3` on row 500 with
  no further export change. The `lab.json` that phase regenerates will differ from mine by those
  rows only.
- **Phase 2 — `lab link`.** `store.set_supersedes` is phase 1's and `lab link` is phase 2's; my
  derivation assumes both of their guarantees (lower id, one successor, same method) and asserts
  neither. Phase 1's dedicated trigger module is where those belong.
- **Not done, deliberately:** `real_costs` titles on `cmp.method_name` while carrying
  `cmp.candidate_id` at `real_costs.py:226`. Fixing the generated title so three arms of M0260
  read as three different things is phase 3's `doc_key` work (R2), not an export change. I only
  assert, in `test_two_variants_under_one_title_stay_two_documents`, that the export does not
  collapse them.
- **Not done, deliberately:** `web/app/sera/overview.ts:77`'s `newest()` picks the newest insight
  for the overview page and will happily pick a superseded row once chains exist. It is not on
  `/sera/journal`, no phase owns it, and it is correct today (nothing is linked). Worth a card
  after phase 6: *overview's "newest insight" should prefer a head*.

---

## Rollback

`git revert` the single commit. `web/data/lab.json` reverts with it, back to the export the v8
database produces under snapshot 5 — which is valid, because this phase writes no database row
and `supersedes`/`doc_key` are NULL everywhere at this point. Nothing downstream has consumed the
new fields yet (phase 5 has not landed), so the revert is clean in either order.

The one thing to check after a revert: `web/data/lab.json` and `lab/lab.sqlite` must still agree.
Run `pytest engine/tests/test_lab_snapshot.py -k committed_snapshot -n0`; if it is red, re-run
Step 11's `lab stage` on the reverted code and commit the JSON alone.
